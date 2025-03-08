import logging
import re
from datetime import datetime, timezone
try:
    from dateutil import parser as date_parser
except ImportError:
    # Simple fallback parser if dateutil not available
    import datetime as dt
    def parse_date(date_string):
        return dt.datetime.strptime(date_string, '%Y-%m-%d').date()
else:
    def parse_date(date_string):
        return date_parser.parse(date_string).date()

from anime.models import Episode

logger = logging.getLogger(__name__)

class EpisodeService:
    """Service for processing and managing anime episodes"""
    
    @staticmethod
    def process_episodes(anime, jikan_data, anilist_data=None):
        """Process episodes data for anime"""
        try:
            # Get the Jikan API fetcher for episodes
            from .api_fetchers import JikanAPIFetcher, AnilistAPIFetcher
            jikan_fetcher = JikanAPIFetcher()
            
            # Fetch full episodes data from Jikan API if we have mal_id
            if anime.mal_id:
                jikan_episodes = jikan_fetcher.fetch_all_anime_episodes(anime.mal_id)
            else:
                jikan_episodes = []
            
            # Check if we got any episodes from Jikan fetcher
            if jikan_episodes:
                EpisodeService.process_jikan_episodes(anime, jikan_episodes)
                logger.info(f"Processed {len(jikan_episodes)} episodes from Jikan API for anime '{anime.title_ukrainian}'")
            else:
                # Fall back to episodes in main anime data if available
                if jikan_data and jikan_data.get('episodes'):
                    basic_episodes = jikan_data.get('episodes', [])
                    EpisodeService.process_basic_episodes(anime, basic_episodes, jikan_data.get('episodes_count', 0))
            
            # Additionally process streaming episodes from Anilist API which often have more images
            if anilist_data:
                # Process streaming episodes for thumbnails
                if anilist_data.get('streamingEpisodes'):
                    EpisodeService.process_anilist_streaming_episodes(anime, anilist_data['streamingEpisodes'])
                    
                # Process airing schedule if available (for upcoming episodes)
                if anilist_data.get('airingSchedule') and anilist_data['airingSchedule'].get('nodes'):
                    EpisodeService.process_anilist_airing_schedule(anime, anilist_data['airingSchedule']['nodes'])
                    
                # Process next airing episode if available
                if anilist_data.get('nextAiringEpisode'):
                    EpisodeService.process_next_airing_episode(anime, anilist_data['nextAiringEpisode'])
                
        except Exception as e:
            logger.error(f"Error processing episodes: {str(e)}")
            logger.error(f"Error details: {repr(e)}")
    
    @staticmethod
    def process_jikan_episodes(anime, jikan_episodes):
        """Process episodes data from Jikan API"""
        if not jikan_episodes:
            return
            
        for ep_data in jikan_episodes:
            ep_number = ep_data.get('mal_id')
            if not ep_number:
                continue
                
            # Try to find existing episode
            episode = Episode.objects.filter(
                anime=anime,
                number=ep_number
            ).first()
            
            if not episode:
                episode = Episode(
                    anime=anime,
                    number=ep_number
                )
            
            # Set episode details
            if ep_data.get('title'):
                episode.title = ep_data['title']
                
            if ep_data.get('title_japanese'):
                episode.title_japanese = ep_data['title_japanese']
                
            if ep_data.get('title_romanji'):
                episode.title_romanji = ep_data['title_romanji']
            
            if ep_data.get('filler'):
                episode.is_filler = ep_data['filler']
                
            if ep_data.get('recap'):
                episode.is_recap = ep_data['recap']
            
            # Try to parse aired date
            if ep_data.get('aired'):
                try:
                    episode.release_date = parse_date(ep_data['aired'])
                except Exception as e:
                    logger.warning(f"Could not parse aired date '{ep_data['aired']}': {str(e)}")
            
            # Set score if available
            if ep_data.get('score') is not None:
                try:
                    episode.score = float(ep_data['score'])
                except (ValueError, TypeError):
                    pass
            
            # Set duration to default if not specified
            if not episode.duration:
                episode.duration = anime.duration_per_episode or 24  # Default duration
            
            # Save the episode
            episode.save()
    
    @staticmethod
    def process_basic_episodes(anime, episodes_data=None, episodes_count=0):
        """Process basic episode data or create placeholder episodes"""
        # Check if we already have episodes
        existing_episodes_count = Episode.objects.filter(anime=anime).count()
        
        if existing_episodes_count > 0:
            logger.info(f"Anime '{anime.title_ukrainian}' already has {existing_episodes_count} episodes. Skipping placeholder creation.")
            return
            
        # If we have a known episode count but no episode data, create placeholders
        if episodes_count > 0:
            for i in range(1, episodes_count + 1):
                Episode.objects.create(
                    anime=anime,
                    number=i,
                    title=f"Епізод {i}",
                    duration=anime.duration_per_episode or 24,
                    release_date=datetime.now()
                )
            logger.info(f"Created {episodes_count} placeholder episodes for anime '{anime.title_ukrainian}'")
        
    @staticmethod
    def process_anilist_streaming_episodes(anime, streaming_episodes):
        """Process streaming episodes from Anilist to get thumbnails"""
        if not streaming_episodes:
            return
            
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
                        number=ep_number
                    ).first()
                    
                    # If episode exists, update its thumbnail
                    if episode and stream_ep.get('thumbnail'):
                        episode.thumbnail_url = stream_ep['thumbnail']
                        if not episode.title or episode.title == f"Епізод {ep_number}":
                            episode.title = stream_ep.get('title', f"Епізод {ep_number}")
                        if stream_ep.get('url'):
                            # Store the streaming URL in appropriate quality field if empty
                            if not episode.video_url_720p:
                                episode.video_url_720p = stream_ep['url']
                        episode.save()
                        logger.info(f"Updated episode info for {anime.title_ukrainian} episode {ep_number}")
                    # If episode doesn't exist, create it with available data
                    elif stream_ep.get('thumbnail'):
                        episode = Episode(
                            anime=anime,
                            number=ep_number,
                            title=stream_ep.get('title', f"Епізод {ep_number}"),
                            duration=anime.duration_per_episode or 24,
                            thumbnail_url=stream_ep['thumbnail'],
                            release_date=datetime.now()
                        )
                        if stream_ep.get('url'):
                            episode.video_url_720p = stream_ep['url']
                        episode.save()
                        logger.info(f"Created new episode with thumbnail for {anime.title_ukrainian} episode {ep_number}")
                        
            except Exception as e:
                logger.error(f"Error processing streaming episode {stream_ep.get('title')}: {str(e)}")
                continue
    
    @staticmethod
    def process_anilist_airing_schedule(anime, airing_nodes):
        """Process airing schedule from Anilist to get episode air dates"""
        if not airing_nodes:
            return
        
        for node in airing_nodes:
            try:
                ep_number = node.get('episode')
                if not ep_number:
                    continue
                
                # Find or create episode
                episode = Episode.objects.filter(
                    anime=anime,
                    number=ep_number
                ).first()
                
                if not episode:
                    episode = Episode(
                        anime=anime,
                        number=ep_number,
                        title=f"Епізод {ep_number}",
                        duration=anime.duration_per_episode or 24
                    )
                
                # Set airing date from timestamp
                if node.get('airingAt'):
                    episode.release_date = datetime.fromtimestamp(
                        node['airingAt'], 
                        tz=timezone.utc
                    ).date()
                
                episode.save()
                logger.debug(f"Updated airing date for {anime.title_ukrainian} episode {ep_number}")
                
            except Exception as e:
                logger.error(f"Error processing airing schedule node: {str(e)}")
                continue
    
    @staticmethod
    def process_next_airing_episode(anime, next_episode_data):
        """Process next airing episode from Anilist"""
        try:
            ep_number = next_episode_data.get('episode')
            if not ep_number:
                return
                
            # Find or create episode
            episode = Episode.objects.filter(
                anime=anime,
                number=ep_number
            ).first()
            
            if not episode:
                episode = Episode(
                    anime=anime,
                    number=ep_number,
                    title=f"Епізод {ep_number}",
                    duration=anime.duration_per_episode or 24
                )
            
            # Set airing date from timestamp
            if next_episode_data.get('airingAt'):
                episode.release_date = datetime.fromtimestamp(
                    next_episode_data['airingAt'],
                    tz=timezone.utc
                ).date()
            
            episode.save()
            logger.info(f"Updated next airing episode {ep_number} for {anime.title_ukrainian}")
            
        except Exception as e:
            logger.error(f"Error processing next airing episode: {str(e)}")
