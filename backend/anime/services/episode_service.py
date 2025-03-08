import logging
import re
from datetime import datetime
from anime.models import Season, Episode

logger = logging.getLogger(__name__)

class EpisodeService:
    """Service for processing and managing anime episodes and seasons"""
    
    @staticmethod
    def process_seasons_and_episodes(anime, jikan_data, anilist_data=None):
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
                EpisodeService.process_jikan_episodes(anime, jikan_episodes)
            
            # Additionally try to get streaming episodes from Anilist for thumbnails
            if anilist_data and anilist_data.get('streamingEpisodes'):
                EpisodeService.process_anilist_streaming_episodes(anime, anilist_data['streamingEpisodes'])
                
        except Exception as e:
            logger.error(f"Error processing seasons and episodes: {str(e)}")
            logger.error(f"Error details: {repr(e)}")
    
    @staticmethod
    def process_jikan_episodes(anime, jikan_episodes):
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
    def process_anilist_streaming_episodes(anime, streaming_episodes):
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
