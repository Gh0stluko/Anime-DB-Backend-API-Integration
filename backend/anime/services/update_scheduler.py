import logging
from datetime import datetime, timedelta

from django.utils import timezone
from django.db.models import Q, Count
from ..models import Anime, UpdateStrategy, UpdateLog

logger = logging.getLogger(__name__)

class UpdateScheduler:
    """Service for scheduling and prioritizing anime updates"""
    
    @staticmethod
    def get_active_strategy():
        """Get the active update strategy or create a default one"""
        strategy = UpdateStrategy.objects.filter(is_active=True).first()
        if not strategy:
            strategy = UpdateStrategy.objects.create(
                name="Стандартна стратегія",
                description="Автоматично створена стандартна стратегія",
                is_active=True
            )
        return strategy
    
    @staticmethod
    def recalculate_priorities():
        """Recalculate update priorities for all anime"""
        count = 0
        for anime in Anime.objects.all():
            old_priority = anime.update_priority
            new_priority = anime.calculate_update_priority()
            
            if old_priority != new_priority:
                anime.update_priority = new_priority
                anime.save(update_fields=['update_priority'])
                count += 1
        
        logger.info(f"Recalculated priorities for {count} anime")
        return count
    
    @staticmethod
    def reschedule_updates():
        """Reschedule next update time for all anime"""
        count = 0
        for anime in Anime.objects.all():
            anime.schedule_next_update()
            anime.save(update_fields=['next_update_scheduled'])
            count += 1
            
        logger.info(f"Rescheduled updates for {count} anime")
        return count
    
    @staticmethod
    def get_update_candidates(batch_size=None, update_type='full'):
        """Get anime candidates for update based on priority and schedule"""
        strategy = UpdateScheduler.get_active_strategy()
        
        if not batch_size:
            batch_size = strategy.batch_size
        
        # Base query for due updates
        due_for_update = Q(next_update_scheduled__lte=timezone.now()) | Q(next_update_scheduled__isnull=True)
        
        # Type-specific queries
        if update_type == 'metadata':
            type_query = Q(last_metadata_update__isnull=True) | Q(
                last_metadata_update__lt=timezone.now() - timedelta(days=7)
            )
        elif update_type == 'episodes':
            type_query = Q(status='ongoing') & (
                Q(last_episodes_update__isnull=True) | 
                Q(last_episodes_update__lt=timezone.now() - timedelta(days=1))
            )
        elif update_type == 'images':
            type_query = Q(screenshots__isnull=True) | Q(
                last_images_update__isnull=True,
                screenshots__count__lt=5
            )
        else:  # full update
            type_query = Q(last_full_update__isnull=True) | Q(
                last_full_update__lt=timezone.now() - timedelta(days=30)
            )
        
        # Prioritize:
        # 1. Ongoing anime that need updates
        # 2. Announced anime
        # 3. High priority anime
        # 4. Anime with few or no screenshots
        # 5. Recently added anime
        
        candidates = Anime.objects.annotate(
            screenshot_count=Count('screenshots')
        ).filter(
            due_for_update,
            type_query
        ).order_by(
            '-status',  # ongoing first
            '-update_priority', 
            'screenshot_count',
            '-created_at'
        )[:batch_size]
        
        return list(candidates)
    
    @staticmethod
    def record_update_attempt(anime, update_type, success=True, error_message=""):
        """Record an update attempt"""
        now = timezone.now()
        
        # Update anime tracking fields
        if success:
            if update_type == 'full':
                anime.last_full_update = now
            elif update_type == 'metadata':
                anime.last_metadata_update = now
            elif update_type == 'episodes':
                anime.last_episodes_update = now
            elif update_type == 'images':
                anime.last_images_update = now
                
            anime.update_failures = 0  # Reset failure counter on success
        else:
            anime.update_failures += 1
        
        # Schedule next update, with backoff for failures
        anime.schedule_next_update()
        if not success and anime.update_failures > 0:
            # Add exponential backoff based on failure count
            backoff_hours = min(2 ** anime.update_failures, 168)  # Max 1 week
            anime.next_update_scheduled = now + timedelta(hours=backoff_hours)
        
        # Update only the changed fields
        update_fields = ['update_failures', 'next_update_scheduled']
        if success:
            if update_type == 'full':
                update_fields.append('last_full_update')
            elif update_type == 'metadata':
                update_fields.append('last_metadata_update')
            elif update_type == 'episodes':
                update_fields.append('last_episodes_update')
            elif update_type == 'images':
                update_fields.append('last_images_update')
        
        anime.save(update_fields=update_fields)
        
        # Create log entry
        UpdateLog.objects.create(
            anime=anime,
            update_type=update_type,
            success=success,
            error_message=error_message
        )
