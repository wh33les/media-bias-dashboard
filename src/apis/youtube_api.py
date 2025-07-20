#!/usr/bin/env python3
"""
YouTube API Client
Gets YouTube channel and video metrics including subscriber counts, view counts, and engagement
"""

import requests
import time
import logging
import re
import os
from urllib.parse import parse_qs, urlparse


class YouTubeAPI:
    """YouTube Data API v3 client for video and channel metrics"""

    def __init__(self, api_key=None, api_manager=None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.session = requests.Session()
        self.cache = {}
        self.api_manager = api_manager

        if not self.api_key:
            logging.warning(
                "YouTube API key not found. Set YOUTUBE_API_KEY environment variable."
            )

    def _extract_channel_info(self, url, source_name):
        """Extract channel ID or username from URL or source name"""
        if not url:
            return None, None

        # Direct YouTube URL patterns
        youtube_patterns = [
            r"youtube\.com/channel/([^/?]+)",
            r"youtube\.com/c/([^/?]+)",
            r"youtube\.com/user/([^/?]+)",
            r"youtube\.com/@([^/?]+)",
            r"youtu\.be/([^/?]+)",
        ]

        for pattern in youtube_patterns:
            match = re.search(pattern, url)
            if match:
                identifier = match.group(1)
                # Determine if it's a channel ID (starts with UC) or username
                if identifier.startswith("UC") and len(identifier) == 24:
                    return identifier, "id"
                else:
                    return identifier, "username"

        # If no YouTube URL, try to infer from source name
        return self._infer_youtube_channel(source_name), "search"

    def _infer_youtube_channel(self, source_name):
        """Try to infer YouTube channel from source name"""
        # Clean up source name for search
        search_term = source_name

        # Remove common suffixes
        search_term = re.sub(r"\s*\(.*?\)\s*", "", search_term)
        search_term = re.sub(r":\s*.*$", "", search_term)

        # Add "official" to help find official channels
        return f"{search_term} official"

    def _make_request(self, endpoint, params=None):
        """Make API request with error handling"""
        if not self.api_key:
            return None

        url = f"{self.base_url}/{endpoint}"
        request_params = {"key": self.api_key}
        if params:
            request_params.update(params)

        try:
            response = self.session.get(url, params=request_params, timeout=10)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                error_data = response.json()
                if "quotaExceeded" in str(error_data):
                    logging.warning("YouTube API quota exceeded")
                else:
                    logging.warning(f"YouTube API forbidden: {error_data}")
                return None
            elif response.status_code == 404:
                logging.debug("YouTube: Channel/video not found")
                return None
            else:
                logging.warning(
                    f"YouTube API error {response.status_code}: {response.text[:200]}"
                )
                return None

        except requests.RequestException as e:
            logging.error(f"YouTube request failed: {e}")
            return None

    def get_youtube_metrics(self, source_name, url=None):
        """Get YouTube channel or video metrics"""
        cache_key = f"{source_name}_{url}".lower()

        # Check cache
        if cache_key in self.cache:
            logging.info(f"YouTube cache hit: {source_name}")
            return self.cache[cache_key]

        logging.info(f"Fetching YouTube data for: {source_name}")
        metrics = {}

        # Try to find YouTube channel
        channel_info, lookup_type = self._extract_channel_info(url, source_name)

        if channel_info:
            if lookup_type == "id":
                channel_data = self._get_channel_by_id(channel_info)
            elif lookup_type == "username":
                channel_data = self._get_channel_by_username(channel_info)
            else:  # search
                channel_data = self._search_channel(channel_info)

            if channel_data:
                metrics.update(channel_data)

                # Get recent videos data
                channel_id = metrics.get("youtube_channel_id")
                if channel_id:
                    video_metrics = self._get_recent_videos_metrics(channel_id)
                    if video_metrics:
                        metrics.update(video_metrics)

        # Cache results
        self.cache[cache_key] = metrics

        return metrics

    def _get_channel_by_id(self, channel_id):
        """Get channel data by channel ID"""
        params = {"part": "snippet,statistics,brandingSettings", "id": channel_id}

        data = self._make_request("channels", params)
        if not data or "items" not in data or not data["items"]:
            return {}

        return self._parse_channel_data(data["items"][0])

    def _get_channel_by_username(self, username):
        """Get channel data by username"""
        params = {
            "part": "snippet,statistics,brandingSettings",
            "forUsername": username,
        }

        data = self._make_request("channels", params)
        if not data or "items" not in data or not data["items"]:
            return {}

        return self._parse_channel_data(data["items"][0])

    def _search_channel(self, query):
        """Search for channel by name"""
        params = {
            "part": "snippet",
            "q": query,
            "type": "channel",
            "maxResults": 5,
            "order": "relevance",
        }

        data = self._make_request("search", params)
        if not data or "items" not in data or not data["items"]:
            return {}

        # Get the first channel result
        channel_id = data["items"][0]["snippet"]["channelId"]
        return self._get_channel_by_id(channel_id)

    def _parse_channel_data(self, channel_item):
        """Parse channel data from YouTube API response"""
        metrics = {}

        # Basic info
        metrics["youtube_channel_id"] = channel_item["id"]
        metrics["youtube_channel_title"] = channel_item["snippet"]["title"]
        metrics["youtube_channel_description"] = channel_item["snippet"]["description"][
            :200
        ]  # Truncate

        # Publication date
        if "publishedAt" in channel_item["snippet"]:
            pub_date = channel_item["snippet"]["publishedAt"]
            metrics["youtube_channel_created"] = pub_date

            # Calculate channel age in years
            from datetime import datetime

            try:
                created_date = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                age_years = (
                    datetime.now().replace(tzinfo=created_date.tzinfo) - created_date
                ).days / 365.25
                metrics["youtube_channel_age_years"] = round(age_years, 1)
            except:
                pass

        # Statistics
        if "statistics" in channel_item:
            stats = channel_item["statistics"]

            # Subscriber count
            subscriber_count = stats.get("subscriberCount")
            if subscriber_count is not None:
                sub_count = int(subscriber_count)
                metrics["youtube_subscribers"] = sub_count
                # Scale subscriber count to influence score (0-100)
                if sub_count >= 10000000:  # 10M+
                    metrics["youtube_subscriber_score"] = 100
                elif sub_count >= 1000000:  # 1M+
                    metrics["youtube_subscriber_score"] = 80
                elif sub_count >= 100000:  # 100K+
                    metrics["youtube_subscriber_score"] = 60
                elif sub_count >= 10000:  # 10K+
                    metrics["youtube_subscriber_score"] = 40
                elif sub_count >= 1000:  # 1K+
                    metrics["youtube_subscriber_score"] = 20
                else:
                    metrics["youtube_subscriber_score"] = 10

            # Video count
            video_count = stats.get("videoCount")
            if video_count is not None:
                metrics["youtube_video_count"] = int(video_count)

            # Total view count
            view_count = stats.get("viewCount")
            if view_count is not None:
                total_views = int(view_count)
                metrics["youtube_total_views"] = total_views

                # Calculate average views per video
                if video_count and int(video_count) > 0:
                    avg_views = total_views / int(video_count)
                    metrics["youtube_avg_views_per_video"] = int(avg_views)

        # Branding/verification
        if "brandingSettings" in channel_item:
            branding = channel_item["brandingSettings"]
            if "channel" in branding:
                channel_branding = branding["channel"]

                # Check for custom URL (indicates established channel)
                if "customUrl" in channel_branding:
                    metrics["youtube_has_custom_url"] = True
                    metrics["youtube_custom_url"] = channel_branding["customUrl"]
                else:
                    metrics["youtube_has_custom_url"] = False

        return metrics

    def _get_recent_videos_metrics(self, channel_id, max_results=10):
        """Get metrics for recent videos from the channel"""
        # Get recent video IDs
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "maxResults": max_results,
            "order": "date",
            "type": "video",
        }

        search_data = self._make_request("search", params)
        if not search_data or "items" not in search_data:
            return {}

        video_ids = [
            item["id"]["videoId"]
            for item in search_data["items"]
            if "videoId" in item["id"]
        ]

        if not video_ids:
            return {}

        # Get detailed video statistics
        params = {"part": "statistics,snippet", "id": ",".join(video_ids)}

        videos_data = self._make_request("videos", params)
        if not videos_data or "items" not in videos_data:
            return {}

        # Calculate aggregate metrics
        total_views = 0
        total_likes = 0
        total_comments = 0
        video_count = len(videos_data["items"])

        for video in videos_data["items"]:
            if "statistics" in video:
                stats = video["statistics"]
                total_views += int(stats.get("viewCount", 0))
                total_likes += int(stats.get("likeCount", 0))
                total_comments += int(stats.get("commentCount", 0))

        metrics = {}

        if video_count > 0:
            metrics["youtube_recent_videos_count"] = video_count
            metrics["youtube_recent_avg_views"] = int(total_views / video_count)
            metrics["youtube_recent_avg_likes"] = int(total_likes / video_count)
            metrics["youtube_recent_avg_comments"] = int(total_comments / video_count)

            # Calculate engagement rate
            if total_views > 0:
                engagement_rate = ((total_likes + total_comments) / total_views) * 100
                metrics["youtube_engagement_rate"] = round(engagement_rate, 3)

                # Engagement score (0-100)
                if engagement_rate >= 5:
                    metrics["youtube_engagement_score"] = 100
                elif engagement_rate >= 2:
                    metrics["youtube_engagement_score"] = 80
                elif engagement_rate >= 1:
                    metrics["youtube_engagement_score"] = 60
                elif engagement_rate >= 0.5:
                    metrics["youtube_engagement_score"] = 40
                else:
                    metrics["youtube_engagement_score"] = 20

        return metrics

    def is_enabled(self):
        """Check if API is properly configured"""
        return bool(self.api_key)

    def get_supported_media_types(self):
        """Return supported media types"""
        return ["TV/Video", "Podcast/Audio"]  # Some podcasts also have YouTube channels


# Example usage:
if __name__ == "__main__":
    # Set your API key as environment variable: YOUTUBE_API_KEY
    api = YouTubeAPI()

    if api.is_enabled():
        # Test with sample channels
        test_sources = [
            ("CNN", "https://www.youtube.com/user/CNN"),
            ("Fox News", "https://www.youtube.com/user/FoxNewsChannel"),
            (
                "The Joe Rogan Experience",
                "https://www.youtube.com/channel/UCzQUP1qoWDoEbmsQxvdjxgQ",
            ),
        ]

        for name, url in test_sources:
            print(f"\n=== {name} ===")
            metrics = api.get_youtube_metrics(name, url)
            for key, value in metrics.items():
                print(f"  {key}: {value}")
    else:
        print("YouTube API key not configured")
