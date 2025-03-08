import os
import logging
from celery import Celery
from celery.signals import task_failure, worker_ready
from celery.schedules import crontab

# Configure logging
logger = logging.getLogger('celery')

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Create Celery app
app = Celery('anime_project')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Add broker connection retry setting to address deprecation warning
app.conf.broker_connection_retry_on_startup = True

# Discover tasks from all installed apps
app.autodiscover_tasks()

# Define periodic tasks
app.conf.beat_schedule = {
    'fetch-top-anime-daily': {
        'task': 'anime.tasks.fetch_top_anime_task',
        'schedule': crontab(hour=3, minute=0),  # Run daily at 3:00 AM
        'args': (1, 50),  # page 1, limit 50
    },
    'fetch-seasonal-anime-weekly': {
        'task': 'anime.tasks.fetch_seasonal_anime_task',
        'schedule': crontab(day_of_week=1, hour=4, minute=0),  # Run weekly on Monday at 4:00 AM
    }
}

# Add error signal handlers for better debugging
@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, args=None, 
                        kwargs=None, traceback=None, einfo=None, **kw):
    """Log detailed information about task failures"""
    logger.error(
        f"Task {sender.name} with id {task_id} failed: {exception}\n"
        f"Args: {args}\nKwargs: {kwargs}\n"
        f"Traceback:\n{einfo}"
    )

@worker_ready.connect
def at_worker_ready(sender, **k):
    """Log when worker is ready"""
    logger.info("Celery worker is ready: %s", sender)

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
