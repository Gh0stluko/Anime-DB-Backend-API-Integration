import requests
import logging
import time
import traceback
from datetime import datetime

from .api_rate_limiter import rate_limited

# Set up dedicated logger with increased detail
logger = logging.getLogger(__name__)

class JikanAPIFetcher:
    """Service for fetching anime data from Jikan API (MyAnimeList)"""
    BASE_URL = "https://api.jikan.moe/v4"
    MAX_LIMIT = 25  # Додано константу для максимального ліміту
    
    def __init__(self):
        self.session = requests.Session()
    
    @rate_limited(api_name="Jikan")
    def fetch_top_anime(self, page=1, limit=25, retries=3, delay=2):
        """Fetch top anime from Jikan API"""
        # Обмежуємо limit максимальним значенням
        limit = min(limit, self.MAX_LIMIT)
        
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
    
    def fetch_anime_episodes(self, mal_id, page=1, retries=3, delay=2):
        """Fetch episodes for a specific anime from Jikan API"""
        url = f"{self.BASE_URL}/anime/{mal_id}/episodes?page={page}"
        logger.info(f"Fetching episodes for anime ID {mal_id} from URL: {url}")
        
        for attempt in range(retries):
            try:
                response = self.session.get(url)
                response.raise_for_status()
                response_json = response.json()
                
                # Enhanced debugging output
                logger.debug(f"Jikan API episodes response structure: {list(response_json.keys())}")
                
                if 'data' not in response_json:
                    logger.error(f"Unexpected API response format for episodes. Keys: {list(response_json.keys())}")
                    if 'error' in response_json:
                        logger.error(f"API Error: {response_json['error']}")
                    
                    if attempt < retries - 1:
                        logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                        time.sleep(delay)
                        continue
                    return [], None
                
                # Get pagination info for potential future requests
                pagination = response_json.get('pagination', {})
                has_next_page = pagination.get('has_next_page', False)
                
                return response_json['data'], pagination
                
            except requests.RequestException as e:
                logger.error(f"Error fetching episodes for anime ID {mal_id}: {str(e)}")
                if attempt < retries - 1:
                    logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                    time.sleep(delay)
                else:
                    return [], None
    
    def fetch_all_anime_episodes(self, mal_id, max_pages=3, retries=3, delay=2):
        """Fetch all episodes for a specific anime by making multiple paginated requests"""
        all_episodes = []
        page = 1
        
        while page <= max_pages:
            episodes, pagination = self.fetch_anime_episodes(mal_id, page, retries, delay)
            all_episodes.extend(episodes)
            
            if not pagination or not pagination.get('has_next_page', False):
                break
                
            page += 1
            # Add a small delay between requests to avoid rate limiting
            time.sleep(1)
        
        logger.info(f"Fetched {len(all_episodes)} episodes for anime ID {mal_id}")
        return all_episodes


class AnilistAPIFetcher:
    """Service for fetching anime data from Anilist API"""
    API_URL = "https://graphql.anilist.co"
    
    @rate_limited(api_name="Anilist")
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
                    nextAiringEpisode {
                        airingAt
                        timeUntilAiring
                        episode
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

    @rate_limited(api_name="Anilist")
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
                nextAiringEpisode {
                    airingAt
                    timeUntilAiring
                    episode
                }
                trailer {
                    id
                    site
                    thumbnail
                }
                airingSchedule {
                    nodes {
                        episode
                        airingAt
                        timeUntilAiring
                    }
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

    def fetch_anime_episodes(self, anilist_id, retries=3, delay=2):
        """Fetch episodes for a specific anime from Anilist API"""
        query = '''
        query ($id: Int) {
            Media(id: $id, type: ANIME) {
                id
                idMal
                title {
                    romaji
                    english
                    native
                }
                streamingEpisodes {
                    title
                    thumbnail
                    url
                    site
                }
                airingSchedule {
                    nodes {
                        episode
                        airingAt
                        timeUntilAiring
                    }
                }
                nextAiringEpisode {
                    airingAt
                    timeUntilAiring
                    episode
                }
            }
        }
        '''
        
        variables = {
            'id': anilist_id
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
                    logger.error(f"Unexpected Anilist API response format for ID {anilist_id}: {response_json}")
                    if 'errors' in response_json:
                        logger.error(f"API Errors: {response_json['errors']}")
                    
                    if attempt < retries - 1:
                        logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                        time.sleep(delay)
                        continue
                    return None
                
                return response_json['data']['Media']
            except requests.RequestException as e:
                logger.error(f"Error fetching episodes from Anilist by ID {anilist_id}: {str(e)}")
                if attempt < retries - 1:
                    logger.info(f"Retrying in {delay} seconds... (Attempt {attempt+1}/{retries})")
                    time.sleep(delay)
                else:
                    return None
