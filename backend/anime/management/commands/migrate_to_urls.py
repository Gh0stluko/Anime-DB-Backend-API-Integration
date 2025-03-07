from django.core.management.base import BaseCommand
from anime.models import Anime, AnimeScreenshot, Episode
from django.db.models import Q

class Command(BaseCommand):
    help = 'Migrates image fields to URL fields for existing records'

    def handle(self, *args, **options):
        self.stdout.write('Starting migration of image fields to URLs...')
        
        # Process anime records
        anime_count = 0
        for anime in Anime.objects.filter(Q(poster__isnull=False) | Q(banner__isnull=False)):
            updated = False
            
            if anime.poster and not anime.poster_url:
                anime.poster_url = anime.poster.url
                updated = True
                
            if anime.banner and not anime.banner_url:
                anime.banner_url = anime.banner.url
                updated = True
                
            if updated:
                anime.save(update_fields=['poster_url', 'banner_url'])
                anime_count += 1
        
        # Process screenshots
        screenshot_count = 0
        for screenshot in AnimeScreenshot.objects.filter(image__isnull=False):
            if screenshot.image and not screenshot.image_url:
                screenshot.image_url = screenshot.image.url
                screenshot.save(update_fields=['image_url'])
                screenshot_count += 1
        
        # Process episodes
        episode_count = 0
        for episode in Episode.objects.filter(thumbnail__isnull=False):
            if episode.thumbnail and not episode.thumbnail_url:
                episode.thumbnail_url = episode.thumbnail.url
                episode.save(update_fields=['thumbnail_url'])
                episode_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully migrated images to URLs:\n'
            f'- {anime_count} anime records\n'
            f'- {screenshot_count} screenshots\n'
            f'- {episode_count} episodes'
        ))
