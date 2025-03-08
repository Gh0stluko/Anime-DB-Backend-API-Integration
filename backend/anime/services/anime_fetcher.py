import requests
import logging
import time
import traceback
import tempfile
import os
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from urllib.request import urlopen
from io import BytesIO
from datetime import datetime
from django.utils.text import slugify
from anime.models import Anime, Genre, AnimeScreenshot, Season, Episode
from .translation_service import TranslationService  # Додаємо імпорт сервісу перекладу
import re
import concurrent.futures
from django.db.models import Count

# Set up dedicated logger with increased detail
logger = logging.getLogger(__name__)

class JikanAPIFetcher:
    """Service for fetching anime data from Jikan API (MyAnimeList)"""
    BASE_URL = "https://api.jikan.moe/v4"
    
    def __init__(self):
        self.session = requests.Session()
    
    def fetch_top_anime(self, page=1, limit=25, retries=3, delay=2):
        """Fetch top anime from Jikan API"""
        url = f"{self.BASE_URL}/top/anime?page={page}&limit={limit}"
        logger.info(f"Fetching top anime from URL: {url}")
        print(f"DEBUG: Requesting {url}")
        
        for attempt in range(retries):
            try:
                response = self.session.get(url)
                response.raise_for_status()
                response_json = response.json()
                
                # Enhanced debugging output
                logger.debug(f"Jikan API response structure: {list(response_json.keys())}")
                logger.debug(f"Response status code: {response.status_code}")
                logger.debug(f"Response headers: {response.headers}")
                
                if 'data' not in response_json:
                    logger.error(f"Unexpected API response format. Keys: {list(response_json.keys())}")
                    logger.error(f"Full response: {response_json}")
                    if 'error' in response_json:
                        logger.error(f"API Error: {response_json['error']}")
                    
                    # If this is not the last retry, wait and try again
                    if attempt < retries - 1:
                        logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                        time.sleep(delay)
                        continue
                    return []
                
                return response_json['data']
            except requests.RequestException as e:
                logger.error(f"Error fetching top anime: {str(e)}")
                logger.error(f"Exception details: {traceback.format_exc()}")
                if attempt < retries - 1:
                    logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                    time.sleep(delay)
                else:
                    return []
    
    def fetch_seasonal_anime(self, year=None, season=None, retries=3, delay=2):
        """Fetch seasonal anime from Jikan API"""
        # Default to current season if not specified
        if not year or not season:
            current_month = datetime.now().month
            year = datetime.now().year
            
            # Map month to season
            if 1 <= current_month <= 3:
                season = 'winter'
            elif 4 <= current_month <= 6:
                season = 'spring'
            elif 7 <= current_month <= 9:
                season = 'summer'
            else:
                season = 'fall'
        
        url = f"{self.BASE_URL}/seasons/{year}/{season}"
        
        for attempt in range(retries):
            try:
                response = self.session.get(url)
                response.raise_for_status()
                response_json = response.json()
                
                # Log the response structure for debugging
                logger.debug(f"Jikan API seasonal response structure: {list(response_json.keys())}")
                
                if 'data' not in response_json:
                    logger.error(f"Unexpected API response format. Keys: {list(response_json.keys())}")
                    if 'error' in response_json:
                        logger.error(f"API Error: {response_json['error']}")
                    
                    if attempt < retries - 1:
                        logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                        time.sleep(delay)
                        continue
                    return []
                
                return response_json['data']
            except requests.RequestException as e:
                logger.error(f"Error fetching seasonal anime: {str(e)}")
                if attempt < retries - 1:
                    logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                    time.sleep(delay)
                else:
                    return []
    
    def fetch_anime_details(self, mal_id, retries=3, delay=2):
        """Fetch detailed information about a specific anime"""
        url = f"{self.BASE_URL}/anime/{mal_id}/full"
        
        for attempt in range(retries):
            try:
                response = self.session.get(url)
                response.raise_for_status()
                response_json = response.json()
                
                # Log the response structure for debugging
                logger.debug(f"Jikan API details response structure: {list(response_json.keys())}")
                
                if 'data' not in response_json:
                    logger.error(f"Unexpected API response format. Keys: {list(response_json.keys())}")
                    if 'error' in response_json:
                        logger.error(f"API Error: {response_json['error']}")
                    
                    if attempt < retries - 1:
                        logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                        time.sleep(delay)
                        continue
                    return None
                
                return response_json['data']
            except requests.RequestException as e:
                logger.error(f"Error fetching anime details for ID {mal_id}: {str(e)}")
                if attempt < retries - 1:
                    logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                    time.sleep(delay)
                else:
                    return None


class AnilistAPIFetcher:
    """Service for fetching anime data from Anilist API"""
    API_URL = "https://graphql.anilist.co"
    
    def fetch_popular_anime(self, page=1, per_page=25, retries=3, delay=2):
        """Fetch popular anime from Anilist"""
        query = '''
        query ($page: Int, $perPage: Int) {
            Page(page: $page, perPage: $perPage) {
                media(sort: POPULARITY_DESC, type: ANIME) {
                    id
                    idMal
                    title {
                        romaji
                        english
                        native
                    }
                    description
                    coverImage {
                        extraLarge
                        large
                        medium
                        color
                    }
                    bannerImage
                    format
                    status
                    episodes
                    duration
                    seasonYear
                    season
                    averageScore
                    popularity
                    genres
                    tags {
                        name
                        description
                    }
                    streamingEpisodes {
                        title
                        thumbnail
                        url
                        site
                    }
                    trailer {
                        id
                        site
                        thumbnail
                    }
                }
            }
        }
        '''
        
        variables = {
            'page': page,
            'perPage': per_page
        }
        
        for attempt in range(retries):
            try:
                response = requests.post(
                    self.API_URL,
                    json={'query': query, 'variables': variables}
                )
                response.raise_for_status()
                response_json = response.json()
                
                # Log the response structure
                logger.debug(f"Anilist API response structure: {list(response_json.keys())}")
                
                if 'data' not in response_json or 'Page' not in response_json['data'] or 'media' not in response_json['data']['Page']:
                    logger.error(f"Unexpected Anilist API response format: {response_json}")
                    if 'errors' in response_json:
                        logger.error(f"API Errors: {response_json['errors']}")
                    
                    if attempt < retries - 1:
                        logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                        time.sleep(delay)
                        continue
                    return []
                
                return response_json['data']['Page']['media']
            except requests.RequestException as e:
                logger.error(f"Error fetching anime from Anilist: {str(e)}")
                if attempt < retries - 1:
                    logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                    time.sleep(delay)
                else:
                    return []

    def fetch_anime_by_id(self, id_mal, retries=3, delay=2):
        """Fetch anime from Anilist by MyAnimeList ID"""
        query = '''
        query ($idMal: Int) {
            Media(idMal: $idMal, type: ANIME) {
                id
                idMal
                title {
                    romaji
                    english
                    native
                }
                description
                coverImage {
                    extraLarge
                    large
                    medium
                    color
                }
                bannerImage
                format
                status
                episodes
                duration
                seasonYear
                season
                averageScore
                popularity
                genres
                tags {
                    name
                    description
                }
                streamingEpisodes {
                    title
                    thumbnail
                    url
                    site
                }
                trailer {
                    id
                    site
                    thumbnail
                }
            }
        }
        '''
        
        variables = {
            'idMal': id_mal
        }
        
        for attempt in range(retries):
            try:
                response = requests.post(
                    self.API_URL,
                    json={'query': query, 'variables': variables}
                )
                response.raise_for_status()
                response_json = response.json()
                
                if 'data' not in response_json or 'Media' not in response_json['data']:
                    logger.error(f"Unexpected Anilist API response format for MAL ID {id_mal}: {response_json}")
                    if 'errors' in response_json:
                        logger.error(f"API Errors: {response_json['errors']}")
                    
                    if attempt < retries - 1:
                        logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                        time.sleep(delay)
                        continue
                    return None
                
                return response_json['data']['Media']
            except requests.RequestException as e:
                logger.error(f"Error fetching anime from Anilist by MAL ID {id_mal}: {str(e)}")
                if attempt < retries - 1:
                    logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                    time.sleep(delay)
                else:
                    return None


class AnimeProcessor:
    """Process anime data from APIs and save to database"""
    
    @staticmethod
    def clean_title(title):
        """Clean and truncate titles to ensure they fit in database fields"""
        if not title:
            return ""
        # Remove any problematic characters
        cleaned_title = re.sub(r'[^\w\s\-_.,:;()\[\]{}]', '', title)
        # Truncate to a safe length
        return cleaned_title[:250] if len(cleaned_title) > 250 else cleaned_title
    
    @staticmethod
    def fetch_and_process_combined(mal_id=None, page=1, limit=25, mode="top"):
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
            jikan_data = [jikan_fetcher.fetch_anime_details(mal_id)]
            if jikan_data[0] is None:
                jikan_data = []
        elif mode == "top":
            jikan_data = jikan_fetcher.fetch_top_anime(page=page, limit=limit)
        elif mode == "seasonal":
            jikan_data = jikan_fetcher.fetch_seasonal_anime()
        else:
            jikan_data = []
        
        # Process each anime with combined data
        for anime_jikan in jikan_data:
            try:
                # Get MAL ID for cross-referencing
                mal_id = anime_jikan.get('mal_id')
                logger.info(f"Processing anime ID {mal_id} from Jikan")
                
                # Try to fetch the same anime from Anilist for additional data
                anilist_data = None
                if mal_id:
                    anilist_data = anilist_fetcher.fetch_anime_by_id(mal_id)
                    if anilist_data:
                        logger.info(f"Found matching anime on Anilist for MAL ID {mal_id}")
                
                # Process the combined data
                anime = AnimeProcessor.process_combined_anime(anime_jikan, anilist_data)
                if anime:
                    processed_anime.append(anime)
            except Exception as e:
                logger.error(f"Error processing combined anime data: {str(e)}")
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
            AnimeProcessor._process_screenshots(anime, jikan_data, anilist_data)
            
            # Process seasons and episodes if it's a TV series
            if anime.type == 'tv':
                AnimeProcessor._process_seasons_and_episodes(anime, jikan_data, anilist_data)
            
            return anime
        except Exception as e:
            logger.error(f"Error in process_combined_anime: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    @staticmethod
    def _apply_jikan_data(anime, data):
        """Apply basic data from Jikan API to anime object"""
        # Basic info
        anime.title_original = AnimeProcessor.clean_title(data['title'])
        anime.title_english = AnimeProcessor.clean_title(data.get('title_english', ''))
        anime.title_japanese = AnimeProcessor.clean_title(data.get('title_japanese', ''))
        
        # Handle newer API version with titles array
        if 'titles' in data and isinstance(data['titles'], list):
            for title_obj in data['titles']:
                if title_obj.get('type') == 'English':
                    anime.title_english = title_obj.get('title', anime.title_english)
                elif title_obj.get('type') == 'Japanese':
                    anime.title_japanese = title_obj.get('title', anime.title_japanese)
        
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
    
    @staticmethod
    def _process_screenshots(anime, jikan_data=None, anilist_data=None, max_screenshots=15, min_screenshots=5):
        """
        Process and save screenshots from both API sources, prioritizing streaming episodes
        
        Args:
            anime: Anime model instance
            jikan_data: Optional data from Jikan API
            anilist_data: Optional data from Anilist API
            max_screenshots: Maximum number of screenshots to add
            min_screenshots: Minimum number of screenshots to aim for
        """
        # Перевіряємо кількість існуючих скріншотів
        existing_count = AnimeScreenshot.objects.filter(anime=anime).count()
        
        # Якщо у аніме вже достатньо скріншотів, пропускаємо
        if existing_count >= max_screenshots:
            logger.info(f"Anime '{anime.title_original}' already has {existing_count} screenshots. Skipping.")
            return
        
        # Скільки скріншотів ще потрібно
        screenshots_needed = max(min_screenshots - existing_count, 0)
        screenshots_added = 0
        
        # Відстежуємо URL-адреси, які вже додані
        existing_urls = set(AnimeScreenshot.objects.filter(anime=anime).values_list('image_url', flat=True))
        
        # First, try to get screenshots from AniList's streaming episodes which have better thumbnails
        if anilist_data and anilist_data.get('streamingEpisodes'):
            for episode in anilist_data['streamingEpisodes']:
                if episode.get('thumbnail'):
                    thumbnail_url = episode['thumbnail']
                    # Перевіряємо, чи URL не є в базі даних
                    if thumbnail_url not in existing_urls:
                        title = episode.get('title', '')
                        screenshot = AnimeScreenshot(
                            anime=anime,
                            image_url=thumbnail_url,
                            description=f"Episode: {title}"
                        )
                        screenshot.save()
                        existing_urls.add(thumbnail_url)
                        screenshots_added += 1
                        
                        # Check if we have enough screenshots now
                        if screenshots_added >= screenshots_needed:
                            logger.info(f"Added {screenshots_added} new screenshots to anime '{anime.title_original}'")
                            return
        
        # Продовжуємо з іншими джерелами зображень, як і раніше...
        # ...existing code...
        
        # Try Anilist trailer thumbnail
        if anilist_data and anilist_data.get('trailer', {}).get('thumbnail'):
            thumbnail_url = anilist_data['trailer']['thumbnail']
            if thumbnail_url not in existing_urls:
                screenshot = AnimeScreenshot(
                    anime=anime,
                    image_url=thumbnail_url,
                    description="Trailer thumbnail"
                )
                screenshot.save()
                existing_urls.add(thumbnail_url)
                screenshots_added += 1
                if screenshots_added >= screenshots_needed:
                    return
        
        # Try Anilist cover images
        if anilist_data and anilist_data.get('coverImage'):
            for size_key in ['extraLarge', 'large', 'medium']:
                if anilist_data['coverImage'].get(size_key):
                    cover_url = anilist_data['coverImage'][size_key]
                    if cover_url not in existing_urls:
                        screenshot = AnimeScreenshot(
                            anime=anime,
                            image_url=cover_url,
                            description=f"Cover {size_key}"
                        )
                        screenshot.save()
                        existing_urls.add(cover_url)
                        screenshots_added += 1
                        if screenshots_added >= screenshots_needed:
                            return
        
        # Add Anilist banner as screenshot if available
        if anilist_data and anilist_data.get('bannerImage'):
            banner_url = anilist_data['bannerImage']
            if banner_url not in existing_urls:
                screenshot = AnimeScreenshot(
                    anime=anime,
                    image_url=banner_url,
                    description="Banner"
                )
                screenshot.save()
                existing_urls.add(banner_url)
                screenshots_added += 1
                if screenshots_added >= screenshots_needed:
                    return
        
        # Finally, use Jikan images
        if jikan_data and jikan_data.get('images'):
            for img_type in ['jpg', 'webp']:
                if jikan_data['images'].get(img_type):
                    for size in ['large_image_url', 'image_url', 'small_image_url']:
                        if jikan_data['images'][img_type].get(size):
                            image_url = jikan_data['images'][img_type][size]
                            if image_url not in existing_urls:
                                screenshot = AnimeScreenshot(
                                    anime=anime,
                                    image_url=image_url,
                                    description=f"{img_type} {size.replace('_image_url', '')}"
                                )
                                screenshot.save()
                                existing_urls.add(image_url)
                                screenshots_added += 1
                                if screenshots_added >= screenshots_needed:
                                    return
        
        logger.info(f"Added {screenshots_added} new screenshots to anime '{anime.title_original}'")
    
    @staticmethod
    def _process_seasons_and_episodes(anime, jikan_data, anilist_data=None):
        """Process seasons and episodes data for TV series"""
        try:
            # First check if this anime already has seasons
            existing_seasons_count = Season.objects.filter(anime=anime).count()
            
            # If no seasons exist and it's a TV series with episodes, create at least one season
            if existing_seasons_count == 0 and anime.episodes_count > 0:
                default_season = Season.objects.create(
                    anime=anime,
                    number=1,
                    title=f"Сезон 1",
                    year=anime.year
                )
                
                # Check if there are already individual episodes
                existing_episodes = Episode.objects.filter(anime=anime, season__isnull=True)
                if existing_episodes.exists():
                    # Associate existing episodes with the new season
                    for episode in existing_episodes:
                        episode.season = default_season
                        episode.save()
                else:
                    # Create episode placeholders based on episodes_count
                    for i in range(1, anime.episodes_count + 1):
                        Episode.objects.create(
                            anime=anime,
                            season=default_season,
                            number=i,
                            absolute_number=i,
                            title=f"Епізод {i}",
                            duration=24,  # Default duration
                            release_date=datetime.now()
                        )
                
                # Update the season's episode count
                default_season.update_episodes_count()
            
            # Try to get actual episode data from the API sources
            if jikan_data.get('episodes'):
                # Get episodes from Jikan if available
                jikan_episodes = jikan_data.get('episodes', [])
                AnimeProcessor._process_jikan_episodes(anime, jikan_episodes)
            
            # Additionally try to get streaming episodes from Anilist for thumbnails
            if anilist_data and anilist_data.get('streamingEpisodes'):
                AnimeProcessor._process_anilist_streaming_episodes(anime, anilist_data['streamingEpisodes'])
                
        except Exception as e:
            logger.error(f"Error processing seasons and episodes: {str(e)}")
            logger.error(traceback.format_exc())
    
    @staticmethod
    def _process_jikan_episodes(anime, jikan_episodes):
        """Process episodes data from Jikan API"""
        if not jikan_episodes:
            return
            
        # Get or create the first season
        default_season, created = Season.objects.get_or_create(
            anime=anime,
            number=1,
            defaults={
                'title': f"Сезон 1",
                'year': anime.year
            }
        )
        
        for ep_data in jikan_episodes:
            ep_number = ep_data.get('mal_id')
            if not ep_number:
                continue
                
            # Try to find existing episode
            episode = Episode.objects.filter(
                anime=anime,
                season=default_season,
                number=ep_number
            ).first()
            
            if not episode:
                episode = Episode(
                    anime=anime,
                    season=default_season,
                    number=ep_number,
                    absolute_number=ep_number
                )
            
            # Set episode details
            if ep_data.get('title'):
                episode.title = ep_data['title']
            
            if ep_data.get('filler'):
                episode.title += " (Filler)"
                
            if ep_data.get('recap'):
                episode.title += " (Recap)"
                
            if ep_data.get('duration'):
                # Extract minutes from duration string like "24 min"
                duration_str = ep_data['duration']
                if isinstance(duration_str, str):
                    try:
                        episode.duration = int(duration_str.split()[0])
                    except (ValueError, IndexError):
                        episode.duration = 24  # Default duration
                else:
                    episode.duration = 24
            
            # Save the episode
            episode.save()
            
        # Update the season's episode count
        default_season.update_episodes_count()
    
    @staticmethod
    def _process_anilist_streaming_episodes(anime, streaming_episodes):
        """Process streaming episodes from Anilist to get thumbnails"""
        if not streaming_episodes:
            return
            
        # Get default season
        default_season = Season.objects.filter(anime=anime, number=1).first()
        
        # Create a regex pattern to extract episode numbers from titles
        ep_pattern = re.compile(r'episode\s*(\d+)', re.IGNORECASE)
        
        for stream_ep in streaming_episodes:
            try:
                # Try to extract episode number from title
                title = stream_ep.get('title', '')
                match = ep_pattern.search(title)
                
                if match:
                    ep_number = int(match.group(1))
                    
                    # Try to find the episode
                    episode = Episode.objects.filter(
                        anime=anime,
                        number=ep_number,
                        season=default_season
                    ).first()
                    
                    # If episode exists, update its thumbnail
                    if episode and stream_ep.get('thumbnail'):
                        episode.thumbnail_url = stream_ep['thumbnail']
                        episode.save(update_fields=['thumbnail_url'])
                        logger.info(f"Updated thumbnail for {anime.title_ukrainian} episode {ep_number}")
                        
            except Exception as e:
                logger.error(f"Error processing streaming episode {stream_ep.get('title')}: {str(e)}")
                continue
    
    # Keep the original methods for backward compatibility
    @staticmethod
    def process_jikan_anime(anime_data):
        try:
            # Check if anime already exists by MAL ID
            existing_anime = Anime.objects.filter(mal_id=anime_data['mal_id']).first()
            
            if existing_anime:
                # Update existing anime
                anime = existing_anime
            else:
                # Create new anime
                anime = Anime()
                anime.mal_id = anime_data['mal_id']
            
            # Log the anime data keys for debugging
            logger.debug(f"Processing anime: {anime_data.get('title', 'Unknown')}")
            logger.debug(f"Available keys in anime data: {list(anime_data.keys())}")
            
            # Set basic info (with proper cleaning and truncation)
            anime.title_original = AnimeProcessor.clean_title(anime_data['title'])
            anime.title_english = AnimeProcessor.clean_title(anime_data.get('title_english', ''))
            anime.title_japanese = AnimeProcessor.clean_title(anime_data.get('title_japanese', ''))
            
            # Try to get title from titles array if available (newer API version)
            if 'titles' in anime_data and isinstance(anime_data['titles'], list):
                for title_obj in anime_data['titles']:
                    if title_obj.get('type') == 'English':
                        anime.title_english = title_obj.get('title', anime.title_english)
                    elif title_obj.get('type') == 'Japanese':
                        anime.title_japanese = title_obj.get('title', anime.title_japanese)
            
            # For Ukrainian title, we'll use the original title for now
            # In a real app, you might want to implement translation or manual entry
            anime.title_ukrainian = anime_data['title']
            
            # Get detailed description and information
            anime.description = anime_data.get('synopsis') or ''
            
            # Add background information if available
            if anime_data.get('background'):
                anime.description += f"\n\nBackground: {anime_data['background']}"
            
            # Set metadata
            anime.year = anime_data.get('year') or datetime.now().year
            anime.episodes_count = anime_data.get('episodes') or 0
            anime.rating = float(anime_data.get('score') or 0)
            
            # Process additional metadata if available
            if anime_data.get('popularity'):
                logger.debug(f"Anime popularity: {anime_data['popularity']}")
                
            if anime_data.get('rank'):
                logger.debug(f"Anime rank: {anime_data['rank']}")
            
            # Handle YouTube trailer with more detailed error handling
            if anime_data.get('trailer'):
                trailer_data = anime_data['trailer']
                logger.debug(f"Trailer data: {trailer_data}")
                
                if trailer_data.get('youtube_id'):
                    anime.youtube_trailer = trailer_data['youtube_id']
            type_map = {
                'TV': 'tv',
                'Movie': 'movie',
                'OVA': 'ova',
                'ONA': 'ona',
                'Special': 'special',
                'Music': 'special'
            }
            anime.type = type_map.get(anime_data.get('type'), 'tv')
            
            # Handle season
            if anime_data.get('season'):
                anime.season = anime_data['season'].lower()
            
            # Set image URLs directly from the API
            if anime_data.get('images'):
                if anime_data['images'].get('jpg'):
                    if anime_data['images']['jpg'].get('large_image_url'):
                        anime.poster_url = anime_data['images']['jpg']['large_image_url']
                    elif anime_data['images']['jpg'].get('image_url'):
                        anime.poster_url = anime_data['images']['jpg']['image_url']
                
                # For banner, use a different image if available, otherwise use the same as poster
                if anime_data.get('images', {}).get('jpg', {}).get('large_image_url'):
                    anime.banner_url = anime_data['images']['jpg']['large_image_url']
            
            # Generate a safe slug
            if not anime.slug:
                base_slug = slugify(anime.title_ukrainian)
                # Ensure the slug is not too long (max 250 chars to be safe)
                if len(base_slug) > 250:
                    base_slug = base_slug[:250]
                anime.slug = base_slug
            
            # Save the anime first so we can add M2M relationships
            anime.save()
            
            # Process genres
            if anime_data.get('genres'):
                for genre_data in anime_data['genres']:
                    genre_name = genre_data['name']
                    genre, created = Genre.objects.get_or_create(name=genre_name)
                    anime.genres.add(genre)
                    
            # Process themes if available
            if anime_data.get('themes'):
                for theme_data in anime_data['themes']:
                    theme_name = theme_data['name']
                    # We'll add themes as genres for now, but you could create a separate Theme model
                    theme_genre, created = Genre.objects.get_or_create(name=theme_name)
                    anime.genres.add(theme_genre)
                    
            # Process demographics if available
            if anime_data.get('demographics'):
                for demo_data in anime_data['demographics']:
                    demo_name = demo_data['name']
                    # We'll add demographics as genres for now
                    demo_genre, created = Genre.objects.get_or_create(name=demo_name)
                    anime.genres.add(demo_genre)
            
            # Add screenshots from the API
            if anime_data.get('images'):
                # Use available image URLs as screenshots
                if anime_data['images'].get('jpg', {}).get('large_image_url'):
                    image_url = anime_data['images']['jpg']['large_image_url']
                    
                    # Check if screenshot already exists
                    if not AnimeScreenshot.objects.filter(anime=anime, image_url=image_url).exists():
                        screenshot = AnimeScreenshot(
                            anime=anime,
                            image_url=image_url,
                            description="Main image"
                        )
                        screenshot.save()
                
                # Add other image variations as screenshots if available
                if anime_data['images'].get('webp', {}).get('large_image_url'):
                    image_url = anime_data['images']['webp']['large_image_url']
                    
                    # Check if screenshot already exists
                    if not AnimeScreenshot.objects.filter(anime=anime, image_url=image_url).exists():
                        screenshot = AnimeScreenshot(
                            anime=anime,
                            image_url=image_url,
                            description="WEBP version"
                        )
                        screenshot.save()
                        
                # Also add medium and small images as additional screenshots if available
                for img_type in ['jpg', 'webp']:
                    for size in ['image_url', 'small_image_url']:
                        if (anime_data['images'].get(img_type, {}).get(size) and 
                            anime_data['images'][img_type][size] != anime_data['images'][img_type].get('large_image_url')):
                            
                            image_url = anime_data['images'][img_type][size]
                            
                            if not AnimeScreenshot.objects.filter(anime=anime, image_url=image_url).exists():
                                screenshot = AnimeScreenshot(
                                    anime=anime,
                                    image_url=image_url,
                                    description=f"{img_type} {size.replace('_image_url', '')}"
                                )
                                screenshot.save()
            
        except Exception as e:
            logger.error(f"Error processing anime {anime_data.get('title', 'Unknown')}: {str(e)}")
            logger.error(traceback.format_exc())
            
        # Return the processed anime
        return anime
    
    @staticmethod
    def process_anilist_anime(anime_data):
        """Process anime data from Anilist API and save to database"""
        try:
            # Check if anime already exists by MAL ID (if available)
            existing_anime = None
            if anime_data.get('idMal'):
                existing_anime = Anime.objects.filter(mal_id=anime_data['idMal']).first()
            
            if existing_anime:
                # Update existing anime
                anime = existing_anime
            else:
                # Create new anime
                anime = Anime()
                anime.mal_id = anime_data.get('idMal')
            
            # Set basic info (with proper cleaning and truncation)
            anime.title_original = AnimeProcessor.clean_title(anime_data['title']['romaji'])
            anime.title_english = AnimeProcessor.clean_title(anime_data['title'].get('english', ''))
            
            # Add Japanese title handling
            if anime_data['title'].get('native'):
                anime.title_japanese = AnimeProcessor.clean_title(anime_data['title']['native'])
            
            # For Ukrainian title, we'll use the original title for now
            anime.title_ukrainian = anime_data['title']['romaji']
            
            anime.description = anime_data.get('description') or ''
            anime.year = anime_data.get('seasonYear') or datetime.now().year
            anime.episodes_count = anime_data.get('episodes') or 0
            
            # Convert score from 1-100 to 1-10
            if anime_data.get('averageScore'):
                anime.rating = float(anime_data['averageScore']) / 10
                
            # Handle trailer if available
            if anime_data.get('trailer'):
                trailer_data = anime_data['trailer']
                logger.debug(f"AniList trailer data: {trailer_data}")
                
                if trailer_data.get('id'):
                    anime.youtube_trailer = trailer_data['id']
                elif trailer_data.get('site') == 'youtube' and trailer_data.get('id'):
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
                
            # Set image URLs directly
            if anime_data.get('coverImage', {}).get('large'):
                anime.poster_url = anime_data['coverImage']['large']
            elif anime_data.get('coverImage', {}).get('medium'):
                anime.poster_url = anime_data['coverImage']['medium']
            
            if anime_data.get('bannerImage'):
                anime.banner_url = anime_data['bannerImage']
            
            # Generate a safe slug
            if not anime.slug:
                base_slug = slugify(anime.title_ukrainian)
                # Ensure the slug is not too long (max 250 chars to be safe)
                if len(base_slug) > 250:
                    base_slug = base_slug[:250]
                anime.slug = base_slug
            
            # Save the anime first so we can add M2M relationships
            anime.save()
            
            # Process genres
            if anime_data.get('genres'):
                for genre_name in anime_data['genres']:
                    genre, created = Genre.objects.get_or_create(name=genre_name)
                    anime.genres.add(genre)
                    
            # Process tags if available
            if anime_data.get('tags'):
                for tag_data in anime_data['tags']:
                    if tag_data.get('name'):
                        tag_genre, created = Genre.objects.get_or_create(name=tag_data['name'])
                        anime.genres.add(tag_genre)
            
            # Add screenshots directly using URLs
            if anime_data.get('coverImage'):
                # Use all available cover image sizes
                for size_key in ['large', 'medium', 'small', 'extraLarge']:
                    if anime_data['coverImage'].get(size_key):
                        cover_url = anime_data['coverImage'][size_key]
                        if not AnimeScreenshot.objects.filter(anime=anime, image_url=cover_url).exists():
                            screenshot = AnimeScreenshot(
                                anime=anime,
                                image_url=cover_url,
                                description=f"Cover {size_key}"
                            )
                            screenshot.save()
                    
            # Add banner as a screenshot if available
            if anime_data.get('bannerImage'):
                banner_url = anime_data.get('bannerImage')
                if not AnimeScreenshot.objects.filter(anime=anime, image_url=banner_url).exists():
                    screenshot = AnimeScreenshot(
                        anime=anime,
                        image_url=banner_url,
                        description="Banner"
                    )
                    screenshot.save()
            
        except Exception as e:
            logger.error(f"Error processing anime {anime_data.get('title', {}).get('romaji', 'Unknown')}: {str(e)}")
            logger.error(traceback.format_exc())
            
        # Return the processed anime
        return anime

