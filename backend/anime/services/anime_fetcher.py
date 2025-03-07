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
from anime.models import Anime, Genre, AnimeScreenshot
import re

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
                        large
                    }
                    bannerImage
                    format
                    status
                    episodes
                    seasonYear
                    season
                    averageScore
                    genres
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
    def process_jikan_anime(anime_data):
        """Process anime data from Jikan API and save to database"""
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
                elif trailer_data.get('url') and 'youtube.com' in trailer_data['url']:
                    # Try to extract YouTube ID from URL
                    try:
                        url_parts = trailer_data['url'].split('/')
                        if 'watch?v=' in trailer_data['url']:
                            # Format: youtube.com/watch?v=XXXX
                            youtube_id = trailer_data['url'].split('watch?v=')[1].split('&')[0]
                            anime.youtube_trailer = youtube_id
                        elif 'youtu.be' in trailer_data['url']:
                            # Format: youtu.be/XXXX
                            youtube_id = url_parts[-1]
                            anime.youtube_trailer = youtube_id
                    except Exception as e:
                        logger.error(f"Failed to extract YouTube ID from URL: {str(e)}")
            
            # Handle duration if available
            if anime_data.get('duration'):
                logger.debug(f"Anime duration: {anime_data['duration']}")
            
            # Handle airing information
            if anime_data.get('aired'):
                aired_info = anime_data['aired']
                logger.debug(f"Aired info: {aired_info}")
                
                # You could extract start and end dates if needed
                if aired_info.get('from'):
                    logger.debug(f"Started airing on: {aired_info['from']}")
                if aired_info.get('to'):
                    logger.debug(f"Finished airing on: {aired_info['to']}")
            
            # Handle status
            status_map = {
                'Airing': 'ongoing',
                'Currently Airing': 'ongoing',
                'Finished Airing': 'completed',
                'Not yet aired': 'announced',
                'Currently Airing': 'ongoing'
            }
            anime.status = status_map.get(anime_data.get('status'), 'ongoing')
            
            # Handle type
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
