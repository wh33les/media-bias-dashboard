# base_api.py
"""
Base API class providing standardized interface for all APIs
Ensures consistent quota tracking, caching, and error handling
"""

import requests
import logging
from abc import ABC, abstractmethod

import config


class BaseAPI(ABC):
    """Standardized base class for all APIs"""

    def __init__(self, api_name, session=None, api_manager=None):
        """
        Initialize base API with standardized components

        Args:
            api_name: Name of the API (e.g., "YouTube", "Wikipedia")
            session: HTTP session (optional, will create default if None)
            api_manager: APIManager instance for quota/rate tracking
        """
        self.api_name = api_name
        self.session = session or self._create_default_session()
        self.api_manager = api_manager

        # Each API defines its own cost structure - ensure it's never None
        self.api_costs = self._define_api_costs() or {}

        if not self.api_manager:
            logging.warning(
                f"{self.api_name}: No API manager provided - quota tracking disabled"
            )

    def _create_default_session(self):
        """Create default HTTP session with user agent"""
        session = requests.Session()
        session.headers.update({"User-Agent": config.user_agent})
        return session

    @abstractmethod
    def _define_api_costs(self):
        """
        Each API defines its cost structure

        Returns:
            dict: Mapping of call types to quota costs
            Example: {"search": 100, "details": 1, "bulk": 50}
        """
        pass

    @abstractmethod
    def is_enabled(self):
        """
        Check if API is available and properly configured

        Returns:
            bool: True if API can be used
        """
        pass

    @abstractmethod
    def get_supported_media_types(self):
        """
        Return list of media types this API supports

        Returns:
            list: Media types like ["TV/Video", "Podcast/Audio", "Web/Articles"]
        """
        pass

    def log_api_call(self, description, call_type="standard"):
        """
        Standardized logging across all APIs

        Args:
            description: Description of what the API call does
            call_type: Type of call (must match keys in _define_api_costs)
        """
        if self.api_manager:
            # Defensive programming - handle case where api_costs might be None
            cost = (self.api_costs or {}).get(call_type, 1)
            self.api_manager.log_api_call(
                description, quota_cost=cost, call_type=call_type
            )
        else:
            # Fallback logging if no API manager
            logging.info(f"{self.api_name}: {description}")

    def check_quota_limit(self, call_type="standard"):
        """
        Standardized quota checking before making calls

        Args:
            call_type: Type of call to check quota for

        Returns:
            bool: True if quota would be exceeded
        """
        if self.api_manager:
            # Defensive programming - handle case where api_costs might be None
            cost = (self.api_costs or {}).get(call_type, 1)
            return self.api_manager.is_rate_limit_exceeded(cost)
        return False

    def is_cached(self, cache_key):
        """Check if item exists in cache"""
        if self.api_manager:
            return self.api_manager.is_in_cache(cache_key)
        return False

    def cache_get(self, cache_key):
        """Get item from cache"""
        if self.api_manager:
            return self.api_manager.get_from_cache(cache_key)
        return None

    def cache_set(self, cache_key, value):
        """Add item to cache"""
        if self.api_manager:
            self.api_manager.add_to_cache(cache_key, value)

    def get_usage_summary(self):
        """Get usage summary for this API"""
        if self.api_manager:
            return self.api_manager.get_usage_summary()
        return {
            "type": "unknown",
            "api_name": self.api_name,
            "calls": 0,
            "status": "no_tracking",
        }

    def save_cache(self):
        """Save cache to disk"""
        if self.api_manager:
            self.api_manager.save_cache_to_disk()
