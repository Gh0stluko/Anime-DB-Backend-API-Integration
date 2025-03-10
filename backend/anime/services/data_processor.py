import logging
import traceback
import re
from datetime import datetime
from django.utils.text import slugify
from django.db import models

from anime.models import Anime, Genre
from .translation_service import TranslationService
from .api_fetchers import JikanAPIFetcher, AnilistAPIFetcher
from .image_service import ImageService
from .episode_service import EpisodeService

# Set up dedicated logger with increased detail
logger = logging.getLogger(__name__)

class AnimeProcessor:
    """Process anime data from APIs and save to database"""
    
    @staticmethod
    def clean_title(title):
        """Clean and truncate titles to ensure they fit in database fields"""
        if not title:
            return ""
            
        # Для японських названий не видаляємо ієрогліфи
        if any('\u3040' <= c <= '\u30ff' or '\u3400' <= c <= '\u4dbf' or '\u4e00' <= c <= '\u9fff' for c in title):
            # Тільки обрізаємо довжину для японських назв, не фільтруючи символи
            return title[:250] if len(title) > 250 else title
            
        # Для не-японських назв застосовуємо фільтрацію проблемних символів
        cleaned_title = re.sub(r'[^\w\s\-_.,:;()\[\]{}]', '', title)
        return cleaned_title[:250] if len(cleaned_title) > 250 else cleaned_title
    
    @classmethod
    def fetch_and_process_combined(cls, page=1, limit=25, mode="top", mal_id=None, year=None, season=None):
        """Fetch and process anime data from multiple sources"""
        # Переконуємося, що limit не перевищує обмеження API
        limit = min(limit, 25)  # Jikan API підтримує максимум 25
        
        """
        Fetch anime data from both Jikan and Anilist APIs and combine the results
        
        Args:
            mal_id: Optional MyAnimeList ID for fetching a specific anime
            page: Page number for paginated results
            limit: Number of results per page
            mode: One of "top", "seasonal", or "detail" to determine fetch method
        
        Returns:
            List of processed anime objects
        """
        jikan_fetcher = JikanAPIFetcher()
        anilist_fetcher = AnilistAPIFetcher()
        processed_anime = []
        
        # Fetch anime data from Jikan API
        if mal_id:
            logger.info(f"Fetching anime with MAL ID {mal_id} from Jikan API")
            jikan_data = [jikan_fetcher.fetch_anime_details(mal_id)]
            if jikan_data[0] is None:
                logger.warning(f"Could not fetch anime with MAL ID {mal_id} from Jikan API")
                jikan_data = []
        elif mode == "top":
            logger.info(f"Fetching top anime from Jikan API (page {page}, limit {limit})")
            jikan_data = jikan_fetcher.fetch_top_anime(page=page, limit=limit)
        elif mode == "seasonal":
            logger.info("Fetching seasonal anime from Jikan API")
            jikan_data = jikan_fetcher.fetch_seasonal_anime()
        else:
            logger.warning(f"Unknown mode '{mode}', no anime data will be fetched")
            jikan_data = []
            
        logger.info(f"Received {len(jikan_data)} anime entries from Jikan API")
        
        # Instead of fetching individual Anilist data for each anime,
        # fetch a batch of popular anime from Anilist to use as supplementary data
        anilist_cache = {}
        
        # Only fetch from Anilist if we have Jikan data and not in "detail" mode (which is for specific anime)
        if jikan_data and mode in ["top", "seasonal"]:
            logger.info(f"Fetching batch of {limit} anime from Anilist API to use as supplementary data")
            anilist_batch = anilist_fetcher.fetch_popular_anime(page=page, per_page=limit)
            
            # Create a mapping of MAL IDs to Anilist data for easy lookup
            for anilist_entry in anilist_batch:
                if anilist_entry.get('idMal'):
                    anilist_cache[anilist_entry['idMal']] = anilist_entry
            
            logger.info(f"Cached {len(anilist_cache)} anime entries from Anilist API")
        
        # Process each anime with combined data
        for anime_jikan in jikan_data:
            try:
                # Get MAL ID for cross-referencing
                mal_id = anime_jikan.get('mal_id')
                logger.info(f"Processing anime ID {mal_id} from Jikan")
                
                # Try to get the anime from Anilist cache first
                anilist_data = None
                if mal_id and mal_id in anilist_cache:
                    anilist_data = anilist_cache[mal_id]
                    logger.info(f"Found anime ID {mal_id} in Anilist cache")
                # If not in cache and we have a MAL ID, fetch from Anilist API individually
                elif mal_id:
                    logger.info(f"Anime ID {mal_id} not in cache, fetching from Anilist API")
                    anilist_data = anilist_fetcher.fetch_anime_by_id(mal_id)
                    if anilist_data:
                        logger.info(f"Successfully fetched anime ID {mal_id} from Anilist API")
                    else:
                        logger.warning(f"Could not fetch anime ID {mal_id} from Anilist API")
                
                # Process the anime with combined data
                processed = AnimeProcessor.process_combined_anime(anime_jikan, anilist_data)
                if processed:
                    processed_anime.append(processed)
                    logger.info(f"Successfully processed anime '{processed.title_original}'")
                else:
                    logger.warning(f"Failed to process anime ID {mal_id}")
            except Exception as e:
                logger.error(f"Error processing anime: {str(e)}")
                logger.error(traceback.format_exc())
        
        return processed_anime
    
    @staticmethod
    def process_combined_anime(jikan_data, anilist_data=None):
        """
        Process anime by combining data from both Jikan and Anilist APIs
        
        Args:
            jikan_data: Anime data from Jikan API
            anilist_data: Optional anime data from Anilist API
        
        Returns:
            Processed Anime object
        """
        try:
            # Start with Jikan data as base
            mal_id = jikan_data.get('mal_id')
            
            # Check if anime already exists
            existing_anime = Anime.objects.filter(mal_id=mal_id).first() if mal_id else None
            
            if existing_anime:
                anime = existing_anime
            else:
                anime = Anime()
                if mal_id:
                    anime.mal_id = mal_id
            
            # Process Jikan data
            AnimeProcessor._apply_jikan_data(anime, jikan_data)
            
            # Apply Anilist data to enhance if available
            if anilist_data:
                AnimeProcessor._enhance_with_anilist_data(anime, anilist_data)
            
            # Save the anime to get an ID if it's new
            anime.save()
            
            # Process genres and other M2M relationships
            AnimeProcessor._process_genres(anime, jikan_data, anilist_data)
            
            # Process screenshots from both sources, prioritizing Anilist's streaming episodes
            ImageService.process_screenshots(anime, jikan_data, anilist_data)
            
            # Process episodes data - pass both API data to get maximum information
            EpisodeService.process_episodes(anime, jikan_data, anilist_data)
            
            return anime
        except Exception as e:
            logger.error(f"Error in process_combined_anime: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    @staticmethod
    def _apply_jikan_data(anime, data):
        """Apply basic data from Jikan API to anime object"""
        # Basic info
        anime.title_original = data['title']
        anime.title_english = data.get('title_english', '')
        
        # Для японських назв не застосовуємо clean_title, щоб зберегти ієрогліфи
        if data.get('title_japanese'):
            anime.title_japanese = data.get('title_japanese', '')
        
        # Handle newer API version with titles array
        if 'titles' in data and isinstance(data['titles'], list):
            for title_obj in data['titles']:
                if title_obj.get('type') == 'English':
                    anime.title_english = title_obj.get('title', anime.title_english)
                elif title_obj.get('type') == 'Japanese':
                    anime.title_japanese = title_obj.get('title', '')
        
        # Визначаємо мову оригіналу та перекладаємо назву на українську
        source_lang = 'ja' if anime.title_japanese else 'en'
        source_title = anime.title_japanese if anime.title_japanese else (anime.title_english or anime.title_original)
        
        # Якщо українська назва ще не заповнена або має значення за замовчуванням
        if not anime.title_ukrainian or anime.title_ukrainian == anime.title_original:
            try:
                # Перекладаємо назву на українську
                anime.title_ukrainian = TranslationService.translate_text(source_title, source_lang=source_lang)
                logger.info(f"Title translated to Ukrainian: {anime.title_ukrainian}")
            except Exception as e:
                logger.error(f"Failed to translate title: {str(e)}")
                # Залишаємо як fallback оригінальну назву, якщо не вдалося перекласти
                anime.title_ukrainian = data['title']
        
        # Description and metadata
        description_source = data.get('synopsis') or ''
        if data.get('background'):
            description_source += f"\n\nBackground: {data['background']}"
        
        # Перекладаємо опис на українську мову
        try:
            if description_source:
                # Визначаємо мову оригіналу опису
                desc_lang = TranslationService.detect_language(description_source)
                # Перекладаємо опис
                anime.description = TranslationService.translate_text(description_source, source_lang=desc_lang)
                logger.info(f"Description translated to Ukrainian, original language: {desc_lang}")
            else:
                anime.description = ""
        except Exception as e:
            logger.error(f"Failed to translate description: {str(e)}")
            anime.description = description_source  # Використовуємо оригінал, якщо не вдалося перекласти
        
        anime.year = data.get('year') or datetime.now().year
        anime.episodes_count = data.get('episodes') or 0
        anime.rating = float(data.get('score') or 0)
        
        # Handle trailer
        if data.get('trailer'):
            trailer_data = data['trailer']
            if trailer_data.get('youtube_id'):
                anime.youtube_trailer = trailer_data['youtube_id']
            elif trailer_data.get('url') and 'youtube.com' in trailer_data['url']:
                try:
                    if 'watch?v=' in trailer_data['url']:
                        youtube_id = trailer_data['url'].split('watch?v=')[1].split('&')[0]
                        anime.youtube_trailer = youtube_id
                    elif 'youtu.be' in trailer_data['url']:
                        youtube_id = trailer_data['url'].split('/')[-1]
                        anime.youtube_trailer = youtube_id
                except Exception as e:
                    logger.error(f"Failed to extract YouTube ID: {str(e)}")
        
        # Status and type
        status_map = {
            'Airing': 'ongoing',
            'Currently Airing': 'ongoing',
            'Finished Airing': 'completed',
            'Not yet aired': 'announced',
        }
        anime.status = status_map.get(data.get('status'), 'ongoing')
        
        type_map = {
            'TV': 'tv',
            'Movie': 'movie',
            'OVA': 'ova',
            'ONA': 'ona',
            'Special': 'special',
            'Music': 'special'
        }
        anime.type = type_map.get(data.get('type'), 'tv')
        
        # Season
        if data.get('season'):
            anime.season = data['season'].lower()
        
        # Images
        if data.get('images'):
            if data['images'].get('jpg'):
                if data['images']['jpg'].get('large_image_url'):
                    anime.poster_url = data['images']['jpg']['large_image_url']
                elif data['images']['jpg'].get('image_url'):
                    anime.poster_url = data['images']['jpg']['image_url']
            
            if data.get('images', {}).get('jpg', {}).get('large_image_url'):
                anime.banner_url = data['images']['jpg']['large_image_url']
        
        # Generate slug if needed
        if not anime.slug:
            base_slug = slugify(anime.title_ukrainian)
            if len(base_slug) > 250:
                base_slug = base_slug[:250]
            anime.slug = base_slug
        
        # Get duration per episode
        if data.get('duration'):
            try:
                duration_str = data['duration']
                if isinstance(duration_str, str):
                    # Extract minutes from duration string like "24 min"
                    duration_match = re.search(r'(\d+)', duration_str)
                    if duration_match:
                        anime.duration_per_episode = int(duration_match.group(1))
                    else:
                        anime.duration_per_episode = 24  # Default
                elif isinstance(duration_str, (int, float)):
                    anime.duration_per_episode = int(duration_str)
                else:
                    anime.duration_per_episode = 24
            except Exception:
                anime.duration_per_episode = 24
    
    @staticmethod
    def _enhance_with_anilist_data(anime, data):
        """Enhance anime object with additional data from Anilist"""
        # Only update fields if they're empty or if Anilist has better data
        
        # Enhanced title handling
        if data.get('title'):
            if not anime.title_english and data['title'].get('english'):
                anime.title_english = AnimeProcessor.clean_title(data['title']['english'])
            
            if not anime.title_japanese and data['title'].get('native'):
                anime.title_japanese = AnimeProcessor.clean_title(data['title']['native'])
        
        # Description - use Anilist's if it's longer and meaningful, and translate
        if data.get('description') and len(data['description']) > len(anime.description):
            try:
                # Визначаємо мову опису
                desc_lang = TranslationService.detect_language(data['description'])
                # Перекладаємо опис
                anime.description = TranslationService.translate_text(data['description'], source_lang=desc_lang)
                logger.info(f"Enhanced description translated to Ukrainian, original language: {desc_lang}")
            except Exception as e:
                logger.error(f"Failed to translate enhanced description: {str(e)}")
                anime.description = data['description']  # Використовуємо оригінал, якщо не вдалося перекласти
        
        # Year, episodes, and rating
        if not anime.year and data.get('seasonYear'):
            anime.year = data['seasonYear']
        
        if not anime.episodes_count and data.get('episodes'):
            anime.episodes_count = data['episodes']
        
        # Convert Anilist score (0-100) to our scale (0-10)
        if data.get('averageScore') and (not anime.rating or anime.rating == 0):
            anime.rating = float(data['averageScore']) / 10
        
        # Season
        if not anime.season and data.get('season'):
            anime.season = data['season'].lower()
        
        # Trailer
        if not anime.youtube_trailer and data.get('trailer'):
            trailer_data = data['trailer']
            if trailer_data.get('site') == 'youtube' and trailer_data.get('id'):
                anime.youtube_trailer = trailer_data['id']
        
        # Status
        if data.get('status'):
            status_map = {
                'RELEASING': 'ongoing',
                'FINISHED': 'completed',
                'NOT_YET_RELEASED': 'announced',
                'CANCELLED': 'dropped'
            }
            if anime.status not in ['completed', 'dropped']:  # Don't override these statuses
                anime.status = status_map.get(data['status'], anime.status)
        
        # Format/Type
        if data.get('format'):
            type_map = {
                'TV': 'tv',
                'MOVIE': 'movie',
                'OVA': 'ova',
                'ONA': 'ona',
                'SPECIAL': 'special',
                'MUSIC': 'special'
            }
            anime.type = type_map.get(data['format'], anime.type)
        
        # Images - Use Anilist's if available and better quality
        if data.get('coverImage', {}).get('extraLarge'):
            anime.poster_url = data['coverImage']['extraLarge']
        elif data.get('coverImage', {}).get('large') and not anime.poster_url:
            anime.poster_url = data['coverImage']['large']
        
        if data.get('bannerImage') and not anime.banner_url:
            anime.banner_url = data['bannerImage']

    @staticmethod
    def _process_genres(anime, jikan_data, anilist_data=None):
        """Process and save genres from both API sources"""
        # Process Jikan genres
        if jikan_data.get('genres'):
            for genre_data in jikan_data['genres']:
                genre_name = genre_data['name']
                genre, created = Genre.objects.get_or_create(name=genre_name)
                anime.genres.add(genre)
        
        # Process Jikan themes
        if jikan_data.get('themes'):
            for theme_data in jikan_data['themes']:
                theme_name = theme_data['name']
                theme_genre, created = Genre.objects.get_or_create(name=theme_name)
                anime.genres.add(theme_genre)
        
        # Process Jikan demographics
        if jikan_data.get('demographics'):
            for demo_data in jikan_data['demographics']:
                demo_name = demo_data['name']
                demo_genre, created = Genre.objects.get_or_create(name=demo_name)
                anime.genres.add(demo_genre)
        
        # Process Anilist genres if available
        if anilist_data and anilist_data.get('genres'):
            for genre_name in anilist_data['genres']:
                genre, created = Genre.objects.get_or_create(name=genre_name)
                anime.genres.add(genre)
        
        # Process Anilist tags if available
        if anilist_data and anilist_data.get('tags'):
            for tag_data in anilist_data['tags']:
                if tag_data.get('name'):
                    tag_genre, created = Genre.objects.get_or_create(name=tag_data['name'])
                    anime.genres.add(tag_genre)

    # Legacy methods for compatibility
    @staticmethod
    def process_jikan_anime(anime_data):
        """Process anime data from Jikan API and save to database (legacy method)"""
        try:
            # Check if anime already exists by MAL ID
            existing_anime = Anime.objects.filter(mal_id=anime_data['mal_id']).first()
            
            if existing_anime:
                anime = existing_anime
            else:
                anime = Anime()
                anime.mal_id = anime_data['mal_id']
            
            # Apply Jikan data
            AnimeProcessor._apply_jikan_data(anime, anime_data)
            
            # Save the anime
            anime.save()
            
            # Process genres
            AnimeProcessor._process_genres(anime, anime_data)
            
            # Process screenshots
            ImageService.process_screenshots(anime, anime_data)
            
            return anime
            
        except Exception as e:
            logger.error(f"Error processing anime {anime_data.get('title', 'Unknown')}: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    @staticmethod
    def process_anilist_anime(anime_data):
        """Process anime data from Anilist API and save to database (legacy method)"""
        try:
            # Check if anime already exists by MAL ID (if available)
            existing_anime = None
            if anime_data.get('idMal'):
                existing_anime = Anime.objects.filter(mal_id=anime_data['idMal']).first()
            
            if existing_anime:
                anime = existing_anime
            else:
                anime = Anime()
                anime.mal_id = anime_data.get('idMal')
            
            # Set basic info
            anime.title_original = AnimeProcessor.clean_title(anime_data['title']['romaji'])
            anime.title_english = AnimeProcessor.clean_title(anime_data['title'].get('english', ''))
            
            # Add Japanese title
            if anime_data['title'].get('native'):
                anime.title_japanese = AnimeProcessor.clean_title(anime_data['title']['native'])
            
            # For Ukrainian title, translate from Japanese or English
            source_lang = 'ja' if anime.title_japanese else 'en'
            source_title = anime.title_japanese if anime.title_japanese else (anime.title_english or anime.title_original)
            
            try:
                anime.title_ukrainian = TranslationService.translate_text(source_title, source_lang=source_lang)
            except Exception as e:
                logger.error(f"Failed to translate title: {str(e)}")
                anime.title_ukrainian = anime_data['title']['romaji']  # Fallback
            
            # Process description
            if anime_data.get('description'):
                try:
                    desc_lang = TranslationService.detect_language(anime_data['description'])
                    anime.description = TranslationService.translate_text(anime_data['description'], source_lang=desc_lang)
                except Exception as e:
                    logger.error(f"Failed to translate description: {str(e)}")
                    anime.description = anime_data.get('description', '')
            else:
                anime.description = ''
            
            # Set metadata
            anime.year = anime_data.get('seasonYear') or datetime.now().year
            anime.episodes_count = anime_data.get('episodes') or 0
            
            # Convert score from 1-100 to 1-10
            if anime_data.get('averageScore'):
                anime.rating = float(anime_data['averageScore']) / 10
            
            # Handle trailer
            if anime_data.get('trailer'):
                trailer_data = anime_data['trailer']
                if trailer_data.get('site') == 'youtube' and trailer_data.get('id'):
                    anime.youtube_trailer = trailer_data['id']
            
            # Handle status
            status_map = {
                'RELEASING': 'ongoing',
                'FINISHED': 'completed',
                'NOT_YET_RELEASED': 'announced',
                'CANCELLED': 'dropped'
            }
            anime.status = status_map.get(anime_data.get('status'), 'ongoing')
            
            # Handle type
            type_map = {
                'TV': 'tv',
                'MOVIE': 'movie',
                'OVA': 'ova',
                'ONA': 'ona',
                'SPECIAL': 'special',
                'MUSIC': 'special'
            }
            anime.type = type_map.get(anime_data.get('format'), 'tv')
            
            # Handle season
            if anime_data.get('season'):
                anime.season = anime_data['season'].lower()
                
            # Set image URLs
            if anime_data.get('coverImage', {}).get('large'):
                anime.poster_url = anime_data['coverImage']['large']
            elif anime_data.get('coverImage', {}).get('medium'):
                anime.poster_url = anime_data['coverImage']['medium']
            
            if anime_data.get('bannerImage'):
                anime.banner_url = anime_data['bannerImage']
            
            # Generate slug
            if not anime.slug:
                base_slug = slugify(anime.title_ukrainian)
                if len(base_slug) > 250:
                    base_slug = base_slug[:250]
                anime.slug = base_slug
            
            # Save anime
            anime.save()
            
            # Process genres
            AnimeProcessor._process_genres(anime, {}, anime_data)
            
            # Process screenshots
            ImageService.process_screenshots(anime, None, anime_data)
            
            return anime
            
        except Exception as e:
            logger.error(f"Error processing anime {anime_data.get('title', {}).get('romaji', 'Unknown')}: {str(e)}")
            logger.error(traceback.format_exc())
            return None
