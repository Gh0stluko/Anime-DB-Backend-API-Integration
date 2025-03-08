"""
This module now serves as an entry point to the refactored anime services.
It imports and re-exports the main classes for backward compatibility.
"""

from .api_fetchers import JikanAPIFetcher, AnilistAPIFetcher
from .data_processor import AnimeProcessor
from .image_service import ImageService
from .episode_service import EpisodeService
from .translation_service import TranslationService

# Re-export classes to maintain backward compatibility
__all__ = [
    'JikanAPIFetcher',
    'AnilistAPIFetcher',
    'AnimeProcessor',
    'ImageService',
    'EpisodeService',
    'TranslationService'
]

