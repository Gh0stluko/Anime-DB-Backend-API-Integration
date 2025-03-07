import logging
import traceback
import sys
from celery import shared_task
from .services.anime_fetcher import JikanAPIFetcher, AnilistAPIFetcher, AnimeProcessor

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def fetch_top_anime_task(self, page=1, limit=25):
    """Task to fetch top anime from Jikan API"""
    logger.info(f"Fetching top anime from Jikan API (page {page}, limit {limit})")
    
    try:
        fetcher = JikanAPIFetcher()
        processor = AnimeProcessor()
        
        # Fetch data from API with enhanced error logging
        logger.debug("Creating fetcher instance and calling fetch_top_anime")
        anime_list = fetcher.fetch_top_anime(page=page, limit=limit)
        
        if not anime_list:
            error_msg = "Failed to fetch anime list or received an empty list"
            logger.error(error_msg)
            logger.error(f"Python version: {sys.version}")
            return error_msg
        
        # Process and save each anime
        processed_count = 0
        logger.info(f"Received {len(anime_list)} anime to process")
        for idx, anime_data in enumerate(anime_list):
            try:
                logger.debug(f"Processing anime {idx+1}/{len(anime_list)}: {anime_data.get('title', 'Unknown')}")
                processor.process_jikan_anime(anime_data)
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing anime {anime_data.get('title')}: {str(e)}")
                logger.error(traceback.format_exc())
        
        return f"Processed {processed_count} anime from Jikan API"
    except Exception as ex:
        logger.error(f"Unexpected error in fetch_top_anime_task: {str(ex)}")
        logger.error(traceback.format_exc())
        # Retry the task with exponential backoff
        raise self.retry(exc=ex, countdown=60 * (2 ** self.request.retries))

@shared_task(bind=True, max_retries=3)
def fetch_seasonal_anime_task(self, year=None, season=None):
    """Task to fetch seasonal anime from Jikan API"""
    logger.info(f"Fetching seasonal anime from Jikan API (year: {year}, season: {season})")
    
    try:
        fetcher = JikanAPIFetcher()
        processor = AnimeProcessor()
        
        # Fetch data from API
        anime_list = fetcher.fetch_seasonal_anime(year=year, season=season)
        
        if not anime_list:
            logger.error("Failed to fetch seasonal anime list or received an empty list")
            return "Failed to fetch seasonal anime list from Jikan API"
        
        # Process and save each anime
        processed_count = 0
        for anime_data in anime_list:
            try:
                processor.process_jikan_anime(anime_data)
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing anime {anime_data.get('title')}: {str(e)}")
                logger.debug(traceback.format_exc())
        
        return f"Processed {processed_count} seasonal anime from Jikan API"
    except Exception as ex:
        logger.error(f"Unexpected error in fetch_seasonal_anime_task: {str(ex)}")
        logger.debug(traceback.format_exc())
        # Retry the task with exponential backoff
        raise self.retry(exc=ex, countdown=60 * (2 ** self.request.retries))

@shared_task(bind=True, max_retries=3)
def fetch_anime_details_task(self, mal_id):
    """Task to fetch detailed information about a specific anime"""
    logger.info(f"Fetching detailed information for anime with ID {mal_id}")
    
    try:
        fetcher = JikanAPIFetcher()
        processor = AnimeProcessor()
        
        # Fetch data from API
        anime_data = fetcher.fetch_anime_details(mal_id)
        
        if not anime_data:
            logger.error(f"Failed to fetch anime with ID {mal_id}")
            return f"Failed to fetch anime with ID {mal_id}"
        
        # Process and save anime
        try:
            processor.process_jikan_anime(anime_data)
            return f"Successfully processed anime with ID {mal_id}"
        except Exception as e:
            logger.error(f"Error processing anime with ID {mal_id}: {str(e)}")
            logger.debug(traceback.format_exc())
            return f"Error processing anime with ID {mal_id}: {str(e)}"
    except Exception as ex:
        logger.error(f"Unexpected error in fetch_anime_details_task: {str(ex)}")
        logger.debug(traceback.format_exc())
        # Retry the task with exponential backoff
        raise self.retry(exc=ex, countdown=60 * (2 ** self.request.retries))

@shared_task(bind=True, max_retries=3)
def fetch_popular_anilist_anime_task(self, page=1, per_page=25):
    """Task to fetch popular anime from Anilist API"""
    logger.info(f"Fetching popular anime from Anilist API (page {page}, per_page {per_page})")
    
    try:
        fetcher = AnilistAPIFetcher()
        processor = AnimeProcessor()
        
        # Fetch data from API
        anime_list = fetcher.fetch_popular_anime(page=page, per_page=per_page)
        
        if not anime_list:
            logger.error("Failed to fetch anime list from Anilist or received an empty list")
            return "Failed to fetch anime list from Anilist API"
        
        # Process and save each anime
        processed_count = 0
        for anime_data in anime_list:
            try:
                processor.process_anilist_anime(anime_data)
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing anime {anime_data.get('title', {}).get('romaji')}: {str(e)}")
                logger.debug(traceback.format_exc())
        
        return f"Processed {processed_count} anime from Anilist API"
    except Exception as ex:
        logger.error(f"Unexpected error in fetch_popular_anilist_anime_task: {str(ex)}")
        logger.debug(traceback.format_exc())
        # Retry the task with exponential backoff
        raise self.retry(exc=ex, countdown=60 * (2 ** self.request.retries))
