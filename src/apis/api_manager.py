# api_manager.py
"""
API Manager for handling caching and rate limiting
Generic module that can be used by any API client
"""

import pickle
import os
import logging
from datetime import datetime

import config


class RateLimitExceeded(Exception):
    """Raised when API rate limits are exceeded"""

    pass


class APIManager:
    def __init__(
        self,
        api_name,
        cache_filename=None,
        hourly_limit=None,
        warning_threshold=None,
        stop_threshold=None,
    ):
        """
        Initialize API manager with caching and rate limiting

        Args:
            api_name: Name of the API (used for logging and determining rate limits)
            cache_filename: Name of the cache file (uses config default if None)
            hourly_limit: Maximum API calls per hour (uses config default if None)
            warning_threshold: Fraction of limit to warn at (e.g., 0.8 for 80%)
            stop_threshold: Fraction of limit to stop at (e.g., 0.9 for 90%)
        """
        # Store API name for logging
        self.api_name = api_name

        # Setup cache file path
        os.makedirs(config.cache_dir, exist_ok=True)
        api_dict_key = api_name.lower().replace(" ", "_")
        cache_filename = cache_filename or config.api_cache_files.get(
            api_dict_key, f"{api_dict_key}_cache.pkl"
        )
        self.cache_file_path = os.path.join(config.cache_dir, cache_filename)

        # Load cache data from disk into memory
        self.cache_data = self._load_cache_from_disk()

        # Rate limiting settings - normalize API name for config lookup
        self.hourly_limit = hourly_limit or config.api_rate_limits.get(
            api_dict_key, 100
        )
        self.warning_threshold = warning_threshold or config.warning_threshold
        self.stop_threshold = stop_threshold or config.stop_threshold

        # Track API calls
        self.api_call_count = 0
        self.session_start_time = datetime.now()

        logging.info(
            f"{self.api_name}: {len(self.cache_data)} entries loaded from {cache_filename}"
        )
        logging.info(
            f"{self.api_name}: Rate limit set to {self.hourly_limit} calls/hour"
        )

    def _load_cache_from_disk(self):
        """Load cache data from disk file into memory"""
        try:
            if os.path.exists(self.cache_file_path):
                with open(self.cache_file_path, "rb") as f:
                    return pickle.load(f)
                logging.debug(f"Loaded cache from {self.cache_file_path}")
        except Exception as e:
            logging.warning(f"Could not load {self.cache_file_path}: {e}")
        return {}

    def get_from_cache(self, key):
        """Get item from in-memory cache"""
        return self.cache_data.get(key)

    def add_to_cache(self, key, value):
        """Add item to in-memory cache (does not write to disk)"""
        self.cache_data[key] = value

    def is_in_cache(self, key):
        """Check if key exists in in-memory cache"""
        return key in self.cache_data

    def save_cache_to_disk(self):
        """Save in-memory cache to disk file"""
        try:
            with open(self.cache_file_path, "wb") as f:
                pickle.dump(self.cache_data, f)
            logging.debug(
                f"Saved {len(self.cache_data)} entries to {self.cache_file_path}"
            )
        except Exception as e:
            logging.error(f"Could not save {self.cache_file_path}: {e}")

    def log_api_call(self, description=""):
        """Log API call with current count and rate"""
        self.api_call_count += 1
        elapsed_hours = (
            datetime.now() - self.session_start_time
        ).total_seconds() / 3600

        if elapsed_hours >= 1.0:
            calls_per_hour = self.api_call_count / elapsed_hours
            logging.info(
                f"{self.api_name} Call #{self.api_call_count}: {description} (Rate: {calls_per_hour:.0f}/hour)"
            )
        else:
            logging.info(f"{self.api_name} Call #{self.api_call_count}: {description}")

    def is_rate_limit_exceeded(self):
        """Check rate limits and save cache if approaching limit"""
        elapsed_hours = (
            datetime.now() - self.session_start_time
        ).total_seconds() / 3600

        # Simple logic: if less than 1 hour, just check total calls
        if elapsed_hours < 1.0:
            warning_threshold = self.hourly_limit * self.warning_threshold
            stop_threshold = self.hourly_limit * self.stop_threshold

            if self.api_call_count > warning_threshold:
                logging.warning(
                    f"{self.api_name}: High API usage: {self.api_call_count} calls in {elapsed_hours:.2f} hours (warning at {warning_threshold})"
                )

            if self.api_call_count > stop_threshold:
                logging.error(
                    f"{self.api_name}: Approaching rate limit! Saving progress..."
                )
                self.save_cache_to_disk()
                return True
        else:
            # After 1 hour, use calls per hour calculation
            calls_per_hour = self.api_call_count / elapsed_hours
            warning_threshold = self.hourly_limit * self.warning_threshold
            stop_threshold = self.hourly_limit * self.stop_threshold

            if calls_per_hour > warning_threshold:
                logging.warning(
                    f"{self.api_name}: High API usage: {calls_per_hour:.0f} calls/hour (limit: {self.hourly_limit})"
                )

            if calls_per_hour > stop_threshold:
                logging.error(
                    f"{self.api_name}: Approaching rate limit! Saving progress..."
                )
                self.save_cache_to_disk()
                return True

        return False
