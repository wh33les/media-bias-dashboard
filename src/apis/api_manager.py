# api_manager.py
"""
Standardized API Manager for handling caching, rate limiting, and quota tracking
Works consistently across all APIs with different cost structures
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
        daily_quota_limit=None,
        hourly_limit=None,
        warning_threshold=None,
        stop_threshold=None,
    ):
        """
        Initialize API manager with standardized quota and rate limiting

        Args:
            api_name: Name of the API (used for logging and determining limits)
            cache_filename: Name of the cache file (uses config default if None)
            daily_quota_limit: Daily quota limit (e.g., 10000 for YouTube, None for rate-limited APIs)
            hourly_limit: Maximum API calls per hour (for rate-limited APIs)
            warning_threshold: Fraction of limit to warn at (e.g., 0.8 for 80%)
            stop_threshold: Fraction of limit to stop at (e.g., 0.9 for 90%)
        """
        # Store API name for logging
        self.api_name = api_name

        # Quota and rate limiting settings
        self.daily_quota_limit = daily_quota_limit
        api_dict_key = api_name.lower().replace(" ", "_")
        self.hourly_limit = hourly_limit or config.api_rate_limits.get(
            api_dict_key, 100
        )
        self.warning_threshold = warning_threshold or config.warning_threshold
        self.stop_threshold = stop_threshold or config.stop_threshold

        # Tracking metrics
        self.api_call_count = 0
        self.quota_units_used = 0
        self.session_start_time = datetime.now()

        # Setup cache file path
        os.makedirs(config.cache_dir, exist_ok=True)
        cache_filename = cache_filename or config.api_cache_files.get(
            api_dict_key, f"{api_dict_key}_cache.pkl"
        )
        self.cache_file_path = os.path.join(config.cache_dir, cache_filename)

        # Load cache data from disk into memory
        self.cache_data = self._load_cache_from_disk()

        # Log initialization with quota/rate info
        if self.daily_quota_limit is not None:
            logging.info(
                f"{self.api_name}: Quota-based API (limit: {self.daily_quota_limit:,} units/day) - "
                f"{len(self.cache_data)} entries loaded from cache"
            )
        else:
            logging.info(
                f"{self.api_name}: Rate-limited API (limit: {self.hourly_limit} calls/hour) - "
                f"{len(self.cache_data)} entries loaded from cache"
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

    def log_api_call(self, description="", quota_cost=1, call_type="standard"):
        """
        Standardized API call logging with quota/rate awareness

        Args:
            description: Description of the API call
            quota_cost: Cost in quota units (1 for most calls, 100+ for expensive calls)
            call_type: Type of call ("search", "details", "bulk", etc.)
        """
        self.api_call_count += 1
        self.quota_units_used += quota_cost

        # Different logging strategies based on quota system
        if self.daily_quota_limit:
            self._log_quota_based_call(description, quota_cost, call_type)
        else:
            self._log_rate_limited_call(description, quota_cost, call_type)

    def _log_quota_based_call(self, description, quota_cost, call_type):
        """Log calls for quota-based APIs (like YouTube)"""
        if self.daily_quota_limit is None:
            # Fallback to rate-limited logging if no quota limit set
            self._log_rate_limited_call(description, quota_cost, call_type)
            return

        quota_percent = (self.quota_units_used / self.daily_quota_limit) * 100

        # Choose priority based on cost
        if quota_cost >= 100:
            priority = "EXPENSIVE"
        elif quota_cost >= 10:
            priority = "MEDIUM"
        else:
            priority = "CHEAP"

        logging.info(
            f"{self.api_name} {priority}: {description} "
            f"(Cost: {quota_cost} units | Total: {self.quota_units_used:,}/{self.daily_quota_limit:,} "
            f"= {quota_percent:.1f}%)"
        )

        # Quota warnings
        if quota_percent >= 95:
            logging.error(f"{self.api_name} QUOTA CRITICAL: {quota_percent:.1f}% used!")
        elif quota_percent >= 80:
            logging.warning(f"{self.api_name} quota high: {quota_percent:.1f}% used")

    def _log_rate_limited_call(self, description, quota_cost, call_type):
        """Log calls for rate-limited APIs (like Wikipedia)"""
        elapsed_hours = (
            datetime.now() - self.session_start_time
        ).total_seconds() / 3600

        if elapsed_hours >= 1.0:
            calls_per_hour = self.api_call_count / elapsed_hours
            logging.info(
                f"{self.api_name} {description} "
                f"(Call #{self.api_call_count} | Rate: {calls_per_hour:.0f}/hour)"
            )
        else:
            logging.info(
                f"{self.api_name} {description} " f"(Call #{self.api_call_count})"
            )

    def is_rate_limit_exceeded(self, upcoming_cost=1):
        """Check if upcoming call would exceed limits"""
        if self.daily_quota_limit is not None:
            # Quota-based check
            would_use = self.quota_units_used + upcoming_cost
            return would_use > (self.daily_quota_limit * self.stop_threshold)
        else:
            # Rate-based check (existing logic)
            return self._check_rate_limit()

    def _check_rate_limit(self):
        """Check rate limits for non-quota APIs"""
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

    def get_usage_summary(self):
        """Get standardized usage summary"""
        if self.daily_quota_limit is not None:
            usage_percent = (self.quota_units_used / self.daily_quota_limit) * 100
            return {
                "type": "quota",
                "api_name": self.api_name,
                "calls": self.api_call_count,
                "quota_used": self.quota_units_used,
                "quota_limit": self.daily_quota_limit,
                "usage_percent": usage_percent,
                "status": (
                    "critical"
                    if usage_percent >= 95
                    else "warning" if usage_percent >= 80 else "good"
                ),
            }
        else:
            elapsed_hours = (
                datetime.now() - self.session_start_time
            ).total_seconds() / 3600
            rate = self.api_call_count / max(elapsed_hours, 0.1)
            return {
                "type": "rate_limited",
                "api_name": self.api_name,
                "calls": self.api_call_count,
                "rate": rate,
                "rate_limit": self.hourly_limit,
                "status": "good",
            }

    @staticmethod
    def check_api_keys(api_names):
        """
        Check which APIs have configured keys in environment variables

        Args:
            api_names: List of API names to check (e.g., ['youtube', 'similarweb'])

        Returns:
            dict: {'configured': [...], 'missing': [...]}
        """
        import os

        # Standard environment variable naming convention: {API_NAME}_API_KEY
        configured = []
        missing = []

        for api_name in api_names:
            env_var_name = f"{api_name.upper()}_API_KEY"
            if os.getenv(env_var_name):
                configured.append(api_name)
            else:
                missing.append(api_name)

        return {"configured": configured, "missing": missing}
