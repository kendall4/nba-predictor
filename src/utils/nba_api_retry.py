"""
Retry utilities for NBA API calls with exponential backoff
Handles timeouts and rate limiting gracefully
"""

import time
import functools
from typing import Callable, Any, Optional
import warnings

def retry_nba_api_call(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    suppress_errors: bool = False
):
    """
    Decorator to retry NBA API calls with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 10.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        suppress_errors: If True, suppress error messages after retries fail (default: False)
    
    Returns:
        Decorated function that retries on timeout/connection errors
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if it's a timeout or connection error
                    error_str = str(e).lower()
                    is_timeout = (
                        'timeout' in error_str or
                        'read timed out' in error_str or
                        'connection' in error_str or
                        'HTTPSConnectionPool' in str(e)
                    )
                    
                    # If it's not a retryable error, raise immediately
                    if not is_timeout and attempt < max_retries:
                        # Still retry non-timeout errors, but fewer times
                        if attempt >= 1:  # Allow 1 retry for non-timeout errors
                            raise
                    
                    # If we've exhausted retries, raise or return None
                    if attempt >= max_retries:
                        if suppress_errors:
                            # Only log once at the end if suppressing
                            return None
                        else:
                            # Re-raise the last exception
                            raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        initial_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    # Add jitter to avoid thundering herd
                    import random
                    jitter = random.uniform(0, delay * 0.1)
                    total_delay = delay + jitter
                    
                    if not suppress_errors:
                        warnings.warn(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {str(e)[:100]}. "
                            f"Retrying in {total_delay:.2f}s...",
                            UserWarning
                        )
                    
                    time.sleep(total_delay)
            
            # Should never reach here, but just in case
            if suppress_errors:
                return None
            raise last_exception
        
        return wrapper
    return decorator


def safe_nba_api_call(func: Callable, *args, suppress_errors: bool = True, **kwargs) -> Optional[Any]:
    """
    Safely execute an NBA API call with automatic retries
    
    Args:
        func: The function to call (e.g., PlayerGameLog.get_data_frames)
        *args: Positional arguments for the function
        suppress_errors: If True, return None on failure instead of raising
        **kwargs: Keyword arguments for the function
    
    Returns:
        Result of function call, or None if suppress_errors=True and call failed
    """
    max_retries = 3
    initial_delay = 1.5
    
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            is_timeout = (
                'timeout' in error_str or
                'read timed out' in error_str or
                'connection' in error_str or
                'HTTPSConnectionPool' in str(e)
            )
            
            if attempt >= max_retries:
                if suppress_errors:
                    return None
                raise
            
            if is_timeout or attempt < 2:  # Retry timeouts more, other errors less
                delay = min(initial_delay * (2 ** attempt), 10.0)
                time.sleep(delay)
    
    if suppress_errors:
        return None
    return None

