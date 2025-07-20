#!/usr/bin/env python3
"""
Wikipedia API module for collecting pageview data and interest scores
"""

import requests
import logging
from urllib.parse import quote
import re

import config
from .api_manager import APIManager, RateLimitExceeded


class WikipediaAPI:
    def __init__(self, session=None, api_manager=None):
        # Use provided session or create new one
        if session:
            self.session = session
        else:
            self.session = requests.Session()
            self.session.headers.update({"User-Agent": config.user_agent})

        if api_manager is None:
            raise ValueError("api_manager is required for WikipediaAPI")
        self.api_manager = api_manager

    def _clean_search_term(self, term):
        """Clean search term"""
        clean = re.sub(r"\s*\([^)]+\)$", "", term)  # Remove (parentheses)
        clean = re.sub(r":\s*.*$", "", clean)  # Remove : suffixes
        return clean.strip()

    def get_wikipedia_pageviews(self, source_name, media_type):
        """Get Wikipedia pageviews with caching"""
        # Clean the source name first
        clean_source_name = source_name.strip()
        cache_key = f"{clean_source_name}_{media_type}"

        if self.api_manager.is_in_cache(cache_key):
            logging.info(f"Wikipedia cache HIT: {clean_source_name}")
            return self.api_manager.get_from_cache(cache_key)

        if self.api_manager.is_rate_limit_exceeded():
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

            for term in search_terms:
                try:
                    search_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(term)}"
                    response = self.session.get(
                        search_url, timeout=config.timeout_seconds
                    )

                    # Use the API manager logging method:
                    self.api_manager.log_api_call(f"Wikipedia summary for '{term}'")

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("type") == "standard":
                            # Get pageviews
                            page_title = data.get("title")
                            pageviews_url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{quote(page_title)}/daily/20240101/20241231"

                            pv_response = self.session.get(
                                pageviews_url, timeout=config.timeout_seconds
                            )

                            # Use the API manager logging method:
                            self.api_manager.log_api_call(
                                f"Wikipedia pageviews for '{page_title}'"
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
                                    break

                except requests.RequestException as e:
                    logging.debug(f"Network error for '{term}': {e}")
                    continue

        except Exception as e:
            logging.debug(f"Wikipedia error for {clean_source_name}: {e}")

        finally:
            self.api_manager.add_to_cache(cache_key, result)

        return result
