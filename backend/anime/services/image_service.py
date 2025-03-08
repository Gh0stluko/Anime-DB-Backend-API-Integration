import logging
from anime.models import AnimeScreenshot

logger = logging.getLogger(__name__)

class ImageService:
    """Service for processing and managing anime-related images"""
    
    @staticmethod
    def process_screenshots(anime, jikan_data=None, anilist_data=None, max_screenshots=15, min_screenshots=5):
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
