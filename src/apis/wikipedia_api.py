#!/usr/bin/env python3
"""
Wikipedia API module using standardized BaseAPI
Collects pageview data and interest scores with consistent quota tracking
"""

import logging
import re
from urllib.parse import quote

import config
from .base_api import BaseAPI
from .api_manager import RateLimitExceeded


class WikipediaAPI(BaseAPI):
    """Wikipedia API with standardized quota tracking interface"""

    def __init__(self, session=None, api_manager=None):
        # Call parent constructor for common setup
        super().__init__("Wikipedia", session=session, api_manager=api_manager)

    def _define_api_costs(self):
        """
        Wikipedia API cost structure
        Wikipedia doesn't have quotas, so all calls cost 1 "unit" for rate limiting
        """
        return {
            "summary": 1,  # Page summary lookup
            "pageviews": 1,  # Pageview statistics
            "search": 1,  # Any search operation
            "standard": 1,  # Default cost
        }

    def is_enabled(self):
        """Wikipedia API is always enabled (no API key required)"""
        return True

    def get_supported_media_types(self):
        """Return supported media types"""
        return [
            "Web/Articles",
            "TV/Video",
            "Podcast/Audio",
        ]  # Wikipedia covers all types

    def _clean_search_term(self, term):
        """Clean search term for Wikipedia lookup"""
        clean = re.sub(r"\s*\([^)]+\)$", "", term)  # Remove (parentheses)
        clean = re.sub(r":\s*.*$", "", clean)  # Remove : suffixes
        return clean.strip()

    def get_wikipedia_pageviews(self, source_name, media_type):
        """Get Wikipedia pageviews with standardized caching and logging"""
        # Clean the source name first
        clean_source_name = source_name.strip()
        cache_key = f"{clean_source_name}_{media_type}"

        # Use standardized cache checking
        if self.is_cached(cache_key):
            logging.info(f"Wikipedia cache HIT: {clean_source_name}")
            return self.cache_get(cache_key)

        # Use standardized quota checking
        if self.check_quota_limit("search"):
            raise RateLimitExceeded("Wikipedia API rate limit reached")

        logging.info(f"Wikipedia cache MISS: fetching {clean_source_name}")
        result = {"has_wikipedia_page": False, "wikipedia_score": 0}

        try:
            base_name = self._clean_search_term(clean_source_name)
            search_terms = [clean_source_name, base_name]

            # Add media-specific variations
            if media_type == "TV/Video":
                search_terms.extend(
                    [f"{base_name} (TV program)", f"{base_name} (TV show)"]
                )
            elif media_type == "Podcast/Audio":
                search_terms.extend([f"{base_name} (podcast)", f"{base_name} podcast"])
            elif media_type == "Web/Articles":
                search_terms.extend([f"{base_name} (website)", f"{base_name}.com"])

            # Remove duplicates while preserving order
            unique_search_terms = list(dict.fromkeys(search_terms))

            logging.debug(
                f"Search terms for '{clean_source_name}': {unique_search_terms}"
            )

            for term in unique_search_terms:
                try:
                    search_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(term)}"
                    response = self.session.get(
                        search_url, timeout=config.timeout_seconds
                    )

                    # Use standardized logging
                    self.log_api_call(f"Summary for '{term}'", call_type="summary")

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("type") == "standard":
                            # Get pageviews
                            page_title = data.get("title")
                            pageviews_url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{quote(page_title)}/daily/20240101/20241231"

                            pv_response = self.session.get(
                                pageviews_url, timeout=config.timeout_seconds
                            )

                            # Use standardized logging
                            self.log_api_call(
                                f"Pageviews for '{page_title}'", call_type="pageviews"
                            )

                            if pv_response.status_code == 200:
                                pv_data = pv_response.json()
                                if pv_data.get("items"):
                                    total_views = sum(
                                        item["views"] for item in pv_data["items"]
                                    )
                                    avg_daily_views = total_views / len(
                                        pv_data["items"]
                                    )

                                    result = {
                                        "has_wikipedia_page": True,
                                        "wikipedia_title": page_title,
                                        "wikipedia_avg_daily_views": round(
                                            avg_daily_views
                                        ),
                                        "wikipedia_score": min(
                                            100, avg_daily_views / 100
                                        ),
                                    }
                                    logging.info(
                                        f"Found Wikipedia page: {page_title} ({avg_daily_views:.0f} daily views)"
                                    )
                                    break  # Stop after first successful match

                except Exception as e:
                    logging.debug(f"Network error for '{term}': {e}")
                    continue

        except Exception as e:
            logging.debug(f"Wikipedia error for {clean_source_name}: {e}")

        finally:
            # Use standardized cache setting
            self.cache_set(cache_key, result)

        return result
