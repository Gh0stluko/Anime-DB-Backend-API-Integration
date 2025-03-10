import logging
import traceback
import time
from celery import shared_task
from django.db import models
from django.utils import timezone
from .models import Anime, UpdateLog
from .services.anime_fetcher import JikanAPIFetcher, AnilistAPIFetcher, AnimeProcessor
from .services.update_scheduler import UpdateScheduler
from .services.api_rate_limiter import APIRateLimiter
from .services.image_service import ImageService

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
        
        # Record updates for processed anime
        for anime in processed_anime:
            UpdateScheduler.record_update_attempt(
                anime=anime,
                update_type='full',
                success=True
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
        
        # Record updates for all processed anime
        for anime in processed_anime:
            UpdateScheduler.record_update_attempt(
                anime=anime,
                update_type='full',
                success=True
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
            
        # Record the update
        if processed_anime and len(processed_anime) > 0:
            UpdateScheduler.record_update_attempt(
                anime=processed_anime[0],
                update_type='full',
                success=True
            )
        
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
                anime = processor.process_anilist_anime(anime_data)
                if anime:
                    UpdateScheduler.record_update_attempt(
                        anime=anime,
                        update_type='full',
                        success=True
                    )
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
    """Task to update screenshots for anime"""
    logger.info(f"Starting screenshots update task (mal_id: {mal_id}, count: {count})")
    
    try:
        if (mal_id):
            # Update specific anime by ID
            anime = Anime.objects.filter(mal_id=mal_id).first()
            if anime:
                jikan_fetcher = JikanAPIFetcher()
                anilist_fetcher = AnilistAPIFetcher()
                
                jikan_data = jikan_fetcher.fetch_anime_details(mal_id)
                anilist_data = anilist_fetcher.fetch_anime_by_id(mal_id)
                
                ImageService.process_screenshots(anime, jikan_data, anilist_data)
                
                # Record update
                UpdateScheduler.record_update_attempt(
                    anime=anime,
                    update_type='images',
                    success=True
                )
                
                return f"Updated screenshots for anime {anime.title_ukrainian}"
            else:
                return f"Anime with MAL ID {mal_id} not found"
        else:
            # Update batch of anime with few screenshots
            processed = 0
            count = count or 20  # Default to 20 if not specified
            
            # Use annotate to count screenshots instead of filter with count lookup
            anime_with_few_screenshots = Anime.objects.annotate(
                screenshots_count=models.Count('screenshots')
            ).filter(screenshots_count__lt=5).order_by('?')[:count]
            
            for anime in anime_with_few_screenshots:
                try:
                    if anime.mal_id:
                        # Fetch data from APIs
                        jikan_fetcher = JikanAPIFetcher()
                        anilist_fetcher = AnilistAPIFetcher()
                        
                        jikan_data = jikan_fetcher.fetch_anime_details(anime.mal_id)
                        anilist_data = anilist_fetcher.fetch_anime_by_id(anime.mal_id)
                        
                        # Process screenshots
                        ImageService.process_screenshots(anime, jikan_data, anilist_data)
                        
                        # Record update
                        UpdateScheduler.record_update_attempt(
                            anime=anime,
                            update_type='images',
                            success=True
                        )
                        
                        processed += 1
                        # Add a small delay to avoid overwhelming APIs
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"Error updating screenshots for anime {anime.title_ukrainian}: {str(e)}")
            
            return f"Updated screenshots for {processed} anime"
    except Exception as ex:
        logger.error(f"Unexpected error in update_anime_screenshots_task: {str(ex)}")
        logger.error(traceback.format_exc())
        # Retry the task with exponential backoff
        raise self.retry(exc=ex, countdown=60 * (2 ** self.request.retries))

@shared_task(bind=True, max_retries=3)
def update_anime_episodes_task(self, mal_id=None, count=None):
    """Task to update episodes for anime"""
    logger.info(f"Updating episodes for anime (mal_id: {mal_id}, count: {count})")
    
    try:
        jikan_fetcher = JikanAPIFetcher()
        anilist_fetcher = AnilistAPIFetcher()
        
        if mal_id:
            # Process a specific anime
            anime = Anime.objects.filter(mal_id=mal_id).first()
            if not anime:
                return f"Anime with MAL ID {mal_id} not found"
                
            # Fetch data
            jikan_data = jikan_fetcher.fetch_anime_details(mal_id)
            anilist_data = anilist_fetcher.fetch_anime_by_id(mal_id)
            
            # Process episodes
            if jikan_data or anilist_data:
                AnimeProcessor._process_episodes(anime, jikan_data, anilist_data)
                
                # Record the update
                UpdateScheduler.record_update_attempt(
                    anime=anime,
                    update_type='episodes',
                    success=True
                )
                
                return f"Successfully updated episodes for anime '{anime.title_ukrainian}'"
            else:
                return f"No data found for anime with MAL ID {mal_id}"
        else:
            # Use our prioritized scheduler
            candidates = UpdateScheduler.get_update_candidates(
                batch_size=count or 20,
                update_type='episodes'
            )
            
            if not candidates:
                return "No anime found for episode updates"
                
            updated_count = 0
            for anime in candidates:
                if anime.mal_id:
                    try:
                        # Fetch data
                        jikan_data = jikan_fetcher.fetch_anime_details(anime.mal_id)
                        anilist_data = anilist_fetcher.fetch_anime_by_id(anime.mal_id)
                        
                        # Process episodes
                        if jikan_data or anilist_data:
                            AnimeProcessor._process_episodes(anime, jikan_data, anilist_data)
                            
                            # Record the update
                            UpdateScheduler.record_update_attempt(
                                anime=anime,
                                update_type='episodes',
                                success=True
                            )
                            
                            updated_count += 1
                    except Exception as e:
                        logger.error(f"Error updating episodes for anime {anime.title_ukrainian} (ID: {anime.mal_id}): {str(e)}")
                        # Record the failure
                        UpdateScheduler.record_update_attempt(
                            anime=anime,
                            update_type='episodes',
                            success=False,
                            error_message=str(e)
                        )
                        continue
            
            return f"Successfully updated episodes for {updated_count} of {len(candidates)} anime"
    except Exception as ex:
        logger.error(f"Unexpected error in update_anime_episodes_task: {str(ex)}")
        logger.error(traceback.format_exc())
        # Retry with exponential backoff
        raise self.retry(exc=ex, countdown=60 * (2 ** self.request.retries))

@shared_task(bind=True)
def update_anime_by_priority_task(self, batch_size=None, update_type='full'):
    """Task to update anime based on priority and schedule"""
    logger.info(f"Starting priority-based anime updates ({update_type}, batch_size: {batch_size})")
    
    try:
        # Get candidates for update
        candidates = UpdateScheduler.get_update_candidates(
            batch_size=batch_size,
            update_type=update_type
        )
        
        if not candidates:
            logger.info("No anime found for scheduled update")
            return "No anime found for scheduled update"
        
        logger.info(f"Found {len(candidates)} anime to update")
        
        # Initialize API fetchers
        jikan_fetcher = JikanAPIFetcher()
        anilist_fetcher = AnilistAPIFetcher()
        
        successful_updates = 0
        failed_updates = 0
        
        for anime in candidates:
            try:
                logger.info(f"Updating {anime.title_ukrainian} (ID: {anime.id}, MAL ID: {anime.mal_id})")
                
                if not anime.mal_id:
                    logger.warning(f"Anime {anime.title_ukrainian} has no MAL ID. Skipping.")
                    continue
                
                # Check for API rate limiting
                if APIRateLimiter.check_rate_limit("Jikan") or APIRateLimiter.check_rate_limit("Anilist"):
                    logger.warning("API rate limits reached. Pausing updates.")
                    break
                
                # Fetch data
                jikan_data = jikan_fetcher.fetch_anime_details(anime.mal_id)
                anilist_data = anilist_fetcher.fetch_anime_by_id(anime.mal_id)
                
                if not jikan_data and not anilist_data:
                    error_msg = f"Failed to fetch data for {anime.title_ukrainian}"
                    logger.error(error_msg)
                    UpdateScheduler.record_update_attempt(
                        anime=anime,
                        update_type=update_type,
                        success=False,
                        error_message=error_msg
                    )
                    failed_updates += 1
                    continue
                
                # Process the data based on update type
                if update_type == 'full':
                    updated_anime = AnimeProcessor.process_combined_anime(jikan_data, anilist_data)
                    if updated_anime:
                        UpdateScheduler.record_update_attempt(
                            anime=updated_anime,
                            update_type=update_type,
                            success=True
                        )
                        successful_updates += 1
                    else:
                        UpdateScheduler.record_update_attempt(
                            anime=anime,
                            update_type=update_type,
                            success=False,
                            error_message="Failed to process anime data"
                        )
                        failed_updates += 1
                elif update_type == 'metadata':
                    # Only update basic info
                    try:
                        if jikan_data:
                            AnimeProcessor._apply_jikan_data(anime, jikan_data)
                        if anilist_data:
                            AnimeProcessor._enhance_with_anilist_data(anime, anilist_data)
                        anime.save()
                        UpdateScheduler.record_update_attempt(
                            anime=anime,
                            update_type=update_type,
                            success=True
                        )
                        successful_updates += 1
                    except Exception as e:
                        logger.error(f"Error updating metadata: {str(e)}")
                        UpdateScheduler.record_update_attempt(
                            anime=anime,
                            update_type=update_type,
                            success=False,
                            error_message=str(e)
                        )
                        failed_updates += 1
                elif update_type == 'episodes':
                    # Only update episodes
                    try:
                        AnimeProcessor._process_episodes(anime, jikan_data, anilist_data)
                        UpdateScheduler.record_update_attempt(
                            anime=anime,
                            update_type=update_type,
                            success=True
                        )
                        successful_updates += 1
                    except Exception as e:
                        logger.error(f"Error updating episodes: {str(e)}")
                        UpdateScheduler.record_update_attempt(
                            anime=anime,
                            update_type=update_type,
                            success=False,
                            error_message=str(e)
                        )
                        failed_updates += 1
                elif update_type == 'images':
                    # Only update screenshots
                    try:
                        AnimeProcessor._process_screenshots(anime, jikan_data, anilist_data)
                        UpdateScheduler.record_update_attempt(
                            anime=anime,
                            update_type=update_type,
                            success=True
                        )
                        successful_updates += 1
                    except Exception as e:
                        logger.error(f"Error updating images: {str(e)}")
                        UpdateScheduler.record_update_attempt(
                            anime=anime,
                            update_type=update_type,
                            success=False,
                            error_message=str(e)
                        )
                        failed_updates += 1
                
            except Exception as e:
                logger.error(f"Error updating anime {anime.title_ukrainian}: {str(e)}")
                logger.error(traceback.format_exc())
                UpdateScheduler.record_update_attempt(
                    anime=anime,
                    update_type=update_type,
                    success=False,
                    error_message=str(e)
                )
                failed_updates += 1
        
        return f"Updated {successful_updates} anime successfully ({failed_updates} failed)"
    
    except Exception as ex:
        logger.error(f"Unexpected error in update_anime_by_priority_task: {str(ex)}")
        logger.error(traceback.format_exc())
        # Don't retry automatically - this task will run again on schedule
        return f"Error: {str(ex)}"

@shared_task(bind=True)
def recalculate_update_priorities_task(self):
    """Task to recalculate update priorities for all anime"""
    try:
        count = UpdateScheduler.recalculate_priorities()
        return f"Recalculated priorities for {count} anime"
    except Exception as ex:
        logger.error(f"Error in recalculate_update_priorities_task: {str(ex)}")
        logger.error(traceback.format_exc())
        return f"Error: {str(ex)}"

@shared_task(bind=True)
def reschedule_updates_task(self):
    """Task to reschedule next update time for all anime"""
    try:
        count = UpdateScheduler.reschedule_updates()
        return f"Rescheduled updates for {count} anime"
    except Exception as ex:
        logger.error(f"Error in reschedule_updates_task: {str(ex)}")
        logger.error(traceback.format_exc())
        return f"Error: {str(ex)}"

@shared_task(name="test_celery_task")
def test_celery_task():
    """Тестове завдання для перевірки роботи Celery"""
    logger.info("Починаємо виконання тестового завдання Celery...")
    
    # Імітація тривалої роботи
    time.sleep(2)
    
    logger.info("Тестове завдання Celery успішно виконано!")
    return {"status": "success", "message": "Тестове завдання виконано успішно!"}

@shared_task(bind=True)
def force_update_scheduled_anime_task(self, anime_ids=None, update_type='full'):
    """
    Задача для примусового оновлення аніме, які вже заплановані на оновлення.
    
    Args:
        anime_ids: Список ID аніме для оновлення. Якщо None, оновлюються всі заплановані аніме.
        update_type: Тип оновлення ('full', 'metadata', 'episodes', 'images').
    
    Returns:
        Результат оновлення.
    """
    logger.info(f"Примусове оновлення аніме (IDs: {anime_ids}, тип: {update_type})")
    
    try:
        if anime_ids:
            # Оновлення конкретних аніме за ID
            anime_list = Anime.objects.filter(id__in=anime_ids)
            logger.info(f"Знайдено {anime_list.count()} аніме за ID")
        else:
            # Оновлення всіх аніме, які вже заплановані (next_update_scheduled <= now)
            now = timezone.now()
            anime_list = Anime.objects.filter(next_update_scheduled__lte=now)
            logger.info(f"Знайдено {anime_list.count()} запланованих аніме для оновлення")
        
        if not anime_list.exists():
            return "Не знайдено аніме для оновлення"
        
        # Використовуємо існуючу задачу оновлення для кожного аніме
        updated_count = 0
        failed_count = 0
        
        # Ініціалізація API клієнтів
        jikan_fetcher = JikanAPIFetcher()
        anilist_fetcher = AnilistAPIFetcher()
        
        for anime in anime_list:
            try:
                logger.info(f"Оновлюємо аніме: {anime.title_ukrainian} (ID: {anime.id})")
                
                # Перевірка наявності MAL ID
                if not anime.mal_id:
                    logger.warning(f"Аніме {anime.title_ukrainian} не має MAL ID. Пропускаємо.")
                    failed_count += 1
                    continue
                
                # Перевірка лімітів API
                if APIRateLimiter.check_rate_limit("Jikan") or APIRateLimiter.check_rate_limit("Anilist"):
                    logger.warning("Досягнуто лімітів API. Призупиняємо оновлення.")
                    break
                
                # Отримання даних з API
                jikan_data = jikan_fetcher.fetch_anime_details(anime.mal_id)
                anilist_data = anilist_fetcher.fetch_anime_by_id(anime.mal_id)
                
                if not jikan_data and not anilist_data:
                    logger.error(f"Не вдалося отримати дані для {anime.title_ukrainian}")
                    UpdateScheduler.record_update_attempt(
                        anime=anime,
                        update_type=update_type,
                        success=False,
                        error_message="Не вдалося отримати дані з API"
                    )
                    failed_count += 1
                    continue
                
                # Оновлення аніме відповідно до типу оновлення
                success = False
                
                if update_type == 'full':
                    updated_anime = AnimeProcessor.process_combined_anime(jikan_data, anilist_data)
                    if updated_anime:
                        success = True
                elif update_type == 'metadata':
                    if jikan_data:
                        AnimeProcessor._apply_jikan_data(anime, jikan_data)
                    if anilist_data:
                        AnimeProcessor._enhance_with_anilist_data(anime, anilist_data)
                    anime.save()
                    success = True
                elif update_type == 'episodes':
                    AnimeProcessor._process_episodes(anime, jikan_data, anilist_data)
                    success = True
                elif update_type == 'images':
                    ImageService.process_screenshots(anime, jikan_data, anilist_data)
                    success = True
                
                # Запис результату оновлення
                UpdateScheduler.record_update_attempt(
                    anime=anime,
                    update_type=update_type,
                    success=success,
                    error_message="" if success else "Помилка обробки даних"
                )
                
                if success:
                    updated_count += 1
                else:
                    failed_count += 1
                
                # Затримка для запобігання перевантаженню API
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Помилка оновлення аніме {anime.title_ukrainian}: {str(e)}")
                UpdateScheduler.record_update_attempt(
                    anime=anime,
                    update_type=update_type,
                    success=False,
                    error_message=str(e)
                )
                failed_count += 1
        
        return f"Успішно оновлено {updated_count} аніме, невдалих оновлень: {failed_count}"
    
    except Exception as ex:
        logger.error(f"Непередбачена помилка в force_update_scheduled_anime_task: {str(ex)}")
        logger.error(traceback.format_exc())
        return f"Помилка: {str(ex)}"
