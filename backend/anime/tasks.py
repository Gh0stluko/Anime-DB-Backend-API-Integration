import logging
import traceback
import sys
from celery import shared_task
from .services.anime_fetcher import JikanAPIFetcher, AnilistAPIFetcher, AnimeProcessor
from .models import Anime

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def fetch_top_anime_task(self, page=1, limit=25):
    """Task to fetch top anime from both Jikan and Anilist APIs"""
    logger.info(f"Fetching top anime from multiple sources (page {page}, limit {limit})")
    
    try:
        # Use the new combined fetching method
        processed_anime = AnimeProcessor.fetch_and_process_combined(
            page=page, 
            limit=limit, 
            mode="top"
        )
        
        if not processed_anime:
            error_msg = "Failed to fetch anime or no anime were successfully processed"
            logger.error(error_msg)
            return error_msg
        
        return f"Successfully processed {len(processed_anime)} top anime from multiple sources"
    except Exception as ex:
        logger.error(f"Unexpected error in fetch_top_anime_task: {str(ex)}")
        logger.error(traceback.format_exc())
        # Retry the task with exponential backoff
        raise self.retry(exc=ex, countdown=60 * (2 ** self.request.retries))

@shared_task(bind=True, max_retries=3)
def fetch_seasonal_anime_task(self, year=None, season=None):
    """Task to fetch seasonal anime from both Jikan and Anilist APIs"""
    logger.info(f"Fetching seasonal anime from multiple sources (year: {year}, season: {season})")
    
    try:
        # Use the new combined fetching method
        processed_anime = AnimeProcessor.fetch_and_process_combined(
            mode="seasonal"
        )
        
        if not processed_anime:
            error_msg = "Failed to fetch seasonal anime or no anime were successfully processed"
            logger.error(error_msg)
            return error_msg
        
        return f"Successfully processed {len(processed_anime)} seasonal anime from multiple sources"
    except Exception as ex:
        logger.error(f"Unexpected error in fetch_seasonal_anime_task: {str(ex)}")
        logger.error(traceback.format_exc())
        # Retry the task with exponential backoff
        raise self.retry(exc=ex, countdown=60 * (2 ** self.request.retries))

@shared_task(bind=True, max_retries=3)
def fetch_anime_details_task(self, mal_id):
    """Task to fetch detailed information about a specific anime from both sources"""
    logger.info(f"Fetching detailed information for anime with MAL ID {mal_id}")
    
    try:
        # Use the new combined fetching method with specific MAL ID
        processed_anime = AnimeProcessor.fetch_and_process_combined(
            mal_id=mal_id,
            mode="detail"
        )
        
        if not processed_anime:
            error_msg = f"Failed to fetch or process anime with MAL ID {mal_id}"
            logger.error(error_msg)
            return error_msg
        
        return f"Successfully processed anime with MAL ID {mal_id} from multiple sources"
    except Exception as ex:
        logger.error(f"Unexpected error in fetch_anime_details_task: {str(ex)}")
        logger.error(traceback.format_exc())
        # Retry the task with exponential backoff
        raise self.retry(exc=ex, countdown=60 * (2 ** self.request.retries))

# This task will remain for backward compatibility
@shared_task(bind=True, max_retries=3)
def fetch_popular_anilist_anime_task(self, page=1, per_page=25):
    """Task to fetch popular anime from Anilist API"""
    logger.info(f"Fetching popular anime from Anilist API (page {page}, per_page {per_page})")
    
    try:
        # For this task, we'll continue using just the Anilist fetcher for backward compatibility
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

@shared_task(bind=True, max_retries=3)
def update_anime_screenshots_task(self, mal_id=None, count=None):
    """
    Задача для оновлення скріншотів аніме
    
    Args:
        mal_id: ID аніме на MyAnimeList (якщо вказано, оновлюються скріншоти лише для цього аніме)
        count: Кількість аніме для оновлення (якщо mal_id не вказано)
    
    Returns:
        str: Повідомлення про результат виконання
    """
    logger.info(f"Оновлення скріншотів для аніме (mal_id: {mal_id}, count: {count})")
    
    try:
        jikan_fetcher = JikanAPIFetcher()
        anilist_fetcher = AnilistAPIFetcher()
        
        if mal_id:
            # Обробка одного аніме за mal_id
            anime = Anime.objects.filter(mal_id=mal_id).first()
            if not anime:
                return f"Аніме з ID {mal_id} не знайдено в базі даних"
            
            # Отримання даних з API
            jikan_data = jikan_fetcher.fetch_anime_details(mal_id)
            anilist_data = anilist_fetcher.fetch_anime_by_id(mal_id)
            
            # Обробка скріншотів для конкретного аніме
            if jikan_data or anilist_data:
                AnimeProcessor._process_screenshots(anime, jikan_data, anilist_data)
                return f"Скріншоти успішно оновлено для аніме '{anime.title_ukrainian}'"
            else:
                return f"Не знайдено даних в API для аніме з ID {mal_id}"
        else:
            # Обробка кількох аніме з бази даних
            if not count:
                count = 10  # За замовчуванням обробляємо 10 аніме
            
            # Отримуємо аніме з найменшою кількістю скріншотів
            animes_to_update = Anime.objects.annotate(
                screenshots_count=models.Count('screenshots')
            ).order_by('screenshots_count')[:count]
            
            updated_count = 0
            for anime in animes_to_update:
                if anime.mal_id:
                    try:
                        # Отримання даних з API
                        jikan_data = jikan_fetcher.fetch_anime_details(anime.mal_id)
                        anilist_data = anilist_fetcher.fetch_anime_by_id(anime.mal_id)
                        
                        # Обробка скріншотів
                        if jikan_data or anilist_data:
                            AnimeProcessor._process_screenshots(anime, jikan_data, anilist_data)
                            updated_count += 1
                    except Exception as e:
                        logger.error(f"Помилка при оновленні скріншотів для аніме {anime.title_ukrainian} (ID: {anime.mal_id}): {str(e)}")
                        continue
            
            return f"Успішно оновлено скріншоти для {updated_count} з {animes_to_update.count()} аніме"
    except Exception as ex:
        logger.error(f"Несподівана помилка в update_anime_screenshots_task: {str(ex)}")
        logger.error(traceback.format_exc())
        # Повторний запуск задачі з експоненційним відкатом
        raise self.retry(exc=ex, countdown=60 * (2 ** self.request.retries))

@shared_task(bind=True, max_retries=3)
def update_anime_episodes_task(self, mal_id):
    """Task to fetch and update episode data for a specific anime"""
    logger.info(f"Fetching episode data for anime with MAL ID {mal_id}")
    
    try:
        # Get the anime from the database
        anime = Anime.objects.filter(mal_id=mal_id).first()
        if not anime:
            error_msg = f"Anime with MAL ID {mal_id} not found in the database"
            logger.error(error_msg)
            return error_msg
            
        # Fetch detailed anime data
        jikan_fetcher = JikanAPIFetcher()
        anilist_fetcher = AnilistAPIFetcher()
        
        jikan_data = jikan_fetcher.fetch_anime_details(mal_id)
        anilist_data = anilist_fetcher.fetch_anime_by_id(mal_id)
        
        if jikan_data or anilist_data:
            # Process seasons and episodes
            if anime.type == 'tv':
                AnimeProcessor._process_seasons_and_episodes(anime, jikan_data, anilist_data)
                
            return f"Successfully updated episodes for anime {anime.title_ukrainian} (MAL ID: {mal_id})"
        else:
            return f"Failed to fetch data for anime with MAL ID {mal_id}"
            
    except Exception as ex:
        logger.error(f"Unexpected error in update_anime_episodes_task: {str(ex)}")
        logger.error(traceback.format_exc())
        # Retry the task with exponential backoff
        raise self.retry(exc=ex, countdown=60 * (2 ** self.request.retries))
