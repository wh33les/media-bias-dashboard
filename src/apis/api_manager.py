# api_manager.py
"""
Standardized API Manager for handling caching, rate limiting, and quota tracking
Works consistently across all APIs with different cost structures
NOW WITH PERSISTENT QUOTA TRACKING across script runs
"""

import pickle
import os
import logging
from datetime import datetime, date

import config


class RateLimitExceeded(Exception):
    """Raised when API rate limits are exceeded"""

    pass


class APIManager:
    def __init__(
        self,
        api_name,
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
        self.daily_quota_limit = api_config["daily_quota_limit"]
        self.hourly_limit = api_config["hourly_limit"]
        self.warning_threshold = config.warning_threshold
        self.stop_threshold = config.stop_threshold

        # Session tracking (for current run)
        self.session_start_time = datetime.now()
        self.session_api_calls = 0

        # Setup cache file path
        os.makedirs(config.cache_dir, exist_ok=True)
        api_dict_key = api_name.lower().replace(" ", "_")

        self.cache_file_path = os.path.join(
            config.cache_dir, f"{api_dict_key}_cache.pkl"
        )
        self.quota_file_path = os.path.join(
            config.cache_dir, f"{api_dict_key}_quota.pkl"
        )

        # Load persistent quota data and cache data
        self.quota_data = self._load_quota_data()
        self.cache_data = self._load_cache_from_disk()

        # Reset counters if new day/hour
        self._reset_expired_quotas()

        # Log initialization with quota/rate info
        if self.daily_quota_limit is not None:
            quota_used = self.quota_data.get("daily_quota_used", 0)
            logging.info(
                f"{self.api_name}: Quota-based API (used: {quota_used:,}/{self.daily_quota_limit:,} units today) - "
                f"{len(self.cache_data)} entries loaded from cache"
            )
        else:
            current_hour_calls = self.quota_data.get("hourly_calls", 0)
            logging.info(
                f"{self.api_name}: Rate-limited API (used: {current_hour_calls}/{self.hourly_limit} calls this hour) - "
                f"{len(self.cache_data)} entries loaded from cache"
            )

    def _load_quota_data(self):
        """Load persistent quota tracking data from disk"""
        try:
            if os.path.exists(self.quota_file_path):
                with open(self.quota_file_path, "rb") as f:
                    data = pickle.load(f)
                    logging.debug(f"Loaded quota data from {self.quota_file_path}")
                    return data
        except Exception as e:
            logging.warning(f"Could not load quota data {self.quota_file_path}: {e}")

        # Return default quota structure
        return {
            "daily_quota_used": 0,
            "daily_reset_date": date.today().isoformat(),
            "hourly_calls": 0,
            "hourly_reset_time": datetime.now()
            .replace(minute=0, second=0, microsecond=0)
            .isoformat(),
            "total_api_calls": 0,
        }

    def _save_quota_data(self):
        """Save persistent quota data to disk"""
        try:
            with open(self.quota_file_path, "wb") as f:
                pickle.dump(self.quota_data, f)
            logging.debug(f"Saved quota data to {self.quota_file_path}")
        except Exception as e:
            logging.error(f"Could not save quota data {self.quota_file_path}: {e}")

    def _reset_expired_quotas(self):
        """Reset quota counters if time periods have expired"""
        now = datetime.now()
        today = date.today()
        current_hour = now.replace(minute=0, second=0, microsecond=0)

        # Check if we need to reset daily quota
        stored_date = date.fromisoformat(
            self.quota_data.get("daily_reset_date", today.isoformat())
        )
        if today > stored_date:
            logging.info(
                f"{self.api_name}: New day detected - resetting daily quota (was {self.quota_data.get('daily_quota_used', 0)} units)"
            )
            self.quota_data["daily_quota_used"] = 0
            self.quota_data["daily_reset_date"] = today.isoformat()

        # Check if we need to reset hourly quota
        stored_hour = datetime.fromisoformat(
            self.quota_data.get("hourly_reset_time", current_hour.isoformat())
        )
        if current_hour > stored_hour:
            logging.info(
                f"{self.api_name}: New hour detected - resetting hourly calls (was {self.quota_data.get('hourly_calls', 0)} calls)"
            )
            self.quota_data["hourly_calls"] = 0
            self.quota_data["hourly_reset_time"] = current_hour.isoformat()

        # Save any resets
        self._save_quota_data()

    def _load_cache_from_disk(self):
        """Load cache data from disk file into memory"""
        try:
            if os.path.exists(self.cache_file_path):
                with open(self.cache_file_path, "rb") as f:
                    data = pickle.load(f)
                    logging.debug(f"Loaded cache from {self.cache_file_path}")
                    return data
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
        Standardized API call logging with PERSISTENT quota/rate tracking

        Args:
            description: Description of the API call
            quota_cost: Cost in quota units (1 for most calls, 100+ for expensive calls)
            call_type: Type of call ("search", "details", "bulk", etc.)
        """
        # Update session counters
        self.session_api_calls += 1

        # Update persistent counters
        self.quota_data["daily_quota_used"] += quota_cost
        self.quota_data["hourly_calls"] += 1
        self.quota_data["total_api_calls"] += 1

        # Save quota data immediately after each call
        self._save_quota_data()

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

        daily_used = self.quota_data["daily_quota_used"]
        quota_percent = (daily_used / self.daily_quota_limit) * 100

        # Choose priority based on cost
        if quota_cost >= 100:
            priority = "EXPENSIVE"
        elif quota_cost >= 10:
            priority = "MEDIUM"
        else:
            priority = "CHEAP"

        logging.info(
            f"{self.api_name} {priority}: {description} "
            f"(Cost: {quota_cost} units | Daily Total: {daily_used:,}/{self.daily_quota_limit:,} "
            f"= {quota_percent:.1f}%)"
        )

        # Quota warnings
        if quota_percent >= 95:
            logging.error(
                f"{self.api_name} QUOTA CRITICAL: {quota_percent:.1f}% used today!"
            )
        elif quota_percent >= 80:
            logging.warning(
                f"{self.api_name} quota high: {quota_percent:.1f}% used today"
            )

    def _log_rate_limited_call(self, description, quota_cost, call_type):
        """Log calls for rate-limited APIs (like Wikipedia)"""
        hourly_calls = self.quota_data["hourly_calls"]

        logging.info(
            f"{self.api_name} {description} "
            f"(Call #{hourly_calls} this hour | Session: #{self.session_api_calls})"
        )

    def is_rate_limit_exceeded(self, upcoming_cost=1):
        """Check if upcoming call would exceed limits using PERSISTENT data"""
        if self.daily_quota_limit is not None:
            # Quota-based check using persistent daily usage
            daily_used = self.quota_data["daily_quota_used"]
            would_use = daily_used + upcoming_cost
            return would_use > (self.daily_quota_limit * self.stop_threshold)
        else:
            # Rate-based check using persistent hourly usage
            hourly_calls = self.quota_data["hourly_calls"]
            return hourly_calls >= (self.hourly_limit * self.stop_threshold)

    def get_usage_summary(self):
        """Get standardized usage summary using PERSISTENT data"""
        if self.daily_quota_limit is not None:
            daily_used = self.quota_data["daily_quota_used"]
            usage_percent = (daily_used / self.daily_quota_limit) * 100
            return {
                "type": "quota",
                "api_name": self.api_name,
                "calls": self.quota_data["total_api_calls"],
                "quota_used": daily_used,
                "quota_limit": self.daily_quota_limit,
                "usage_percent": usage_percent,
                "status": (
                    "critical"
                    if usage_percent >= 95
                    else "warning" if usage_percent >= 80 else "good"
                ),
            }
        else:
            hourly_calls = self.quota_data["hourly_calls"]
            rate_percent = (hourly_calls / self.hourly_limit) * 100
            return {
                "type": "rate_limited",
                "api_name": self.api_name,
                "calls": self.quota_data["total_api_calls"],
                "hourly_calls": hourly_calls,
                "hourly_limit": self.hourly_limit,
                "rate_percent": rate_percent,
                "status": ("warning" if rate_percent >= 80 else "good"),
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
