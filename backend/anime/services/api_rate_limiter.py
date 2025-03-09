import time
import logging
import random
from functools import wraps
from datetime import datetime, timedelta

from django.utils import timezone
from ..models import APIUsageStatistics, APIRequestLog, UpdateStrategy

logger = logging.getLogger(__name__)

class APIRateLimiter:
    """Service for managing API request rates and preventing rate limit issues"""
    
    @staticmethod
    def get_api_stats(api_name):
        """Get or create API usage statistics"""
        stats, _ = APIUsageStatistics.objects.get_or_create(api_name=api_name)
        return stats
    
    @staticmethod
    def log_request(api_name, endpoint, parameters=None, response_code=None, success=False, error_message=""):
        """Log API request details"""
        # Update statistics
        stats = APIRateLimiter.get_api_stats(api_name)
        stats.increment(success=success)
        
        # Create detailed log
        APIRequestLog.objects.create(
            api_name=api_name,
            endpoint=endpoint,
            parameters=parameters,
            response_code=response_code,
            success=success,
            error_message=error_message
        )
    
    @staticmethod
    def check_rate_limit(api_name):
        """Check if API is currently rate-limited"""
        stats = APIRateLimiter.get_api_stats(api_name)
        
        # If rate-limited and time has passed, clear the limit
        if stats.is_rate_limited and stats.rate_limited_until:
            if timezone.now() > stats.rate_limited_until:
                stats.is_rate_limited = False
                stats.rate_limited_until = None
                stats.save()
                return False
            return True
            
        # Check against limits
        return stats.check_limits()
    
    @staticmethod
    def adaptive_wait(api_name):
        """Calculate adaptive wait time based on API usage pattern"""
        stats = APIRateLimiter.get_api_stats(api_name)
        strategy = UpdateStrategy.objects.filter(is_active=True).first()
        
        if not strategy:
            # Default conservative wait
            return random.uniform(1.0, 3.0)
        
        # Base wait time
        base_wait = 60 / strategy.api_requests_per_minute
        
        # Add jitter to prevent synchronized requests
        jitter = random.uniform(-0.3, 0.3) * base_wait
        
        # Calculate usage percentage
        daily_usage_percent = (stats.daily_count / strategy.api_requests_per_day) * 100
        
        # Exponential backoff as we approach limits
        if daily_usage_percent > 90:
            # Very close to limit, be very conservative
            backoff_factor = 5.0
        elif daily_usage_percent > 75:
            backoff_factor = 2.0
        elif daily_usage_percent > 50:
            backoff_factor = 1.5
        else:
            backoff_factor = 1.0
        
        wait_time = (base_wait * backoff_factor) + jitter
        
        # Ensure minimum wait time
        return max(0.5, wait_time)

def rate_limited(api_name):
    """Decorator for rate-limiting API calls"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check if we're already rate limited
            if APIRateLimiter.check_rate_limit(api_name):
                stats = APIRateLimiter.get_api_stats(api_name)
                wait_remaining = (stats.rate_limited_until - timezone.now()).total_seconds()
                logger.warning(f"{api_name} is currently rate-limited. Waiting for {wait_remaining:.1f} seconds")
                
                # If it's a short wait, we can wait it out
                if wait_remaining < 120:  # 2 minutes
                    time.sleep(wait_remaining + 1)  # Add 1 second buffer
                else:
                    raise Exception(f"{api_name} is rate-limited for too long ({wait_remaining:.1f}s). Skipping request.")
            
            # Calculate adaptive wait time
            wait_time = APIRateLimiter.adaptive_wait(api_name)
            time.sleep(wait_time)
            
            # Get endpoint from kwargs if available
            endpoint = kwargs.get('endpoint', func.__name__)
            
            try:
                result = func(*args, **kwargs)
                APIRateLimiter.log_request(
                    api_name=api_name,
                    endpoint=endpoint,
                    parameters=kwargs,
                    success=True
                )
                return result
            except Exception as e:
                APIRateLimiter.log_request(
                    api_name=api_name,
                    endpoint=endpoint,
                    parameters=kwargs,
                    success=False,
                    error_message=str(e)
                )
                raise
        
        return wrapper
    return decorator
