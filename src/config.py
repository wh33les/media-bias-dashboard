# config.py
"""
Configuration settings for the influence collector
Simple Python config - easy to modify and can include comments
"""

# Logging level: "DEBUG", "INFO", "WARNING", "ERROR"
log_level = "INFO"  # Quiet by default

# File paths
input_file = "data/test_data.csv"
output_file = "data/test_results.csv"

# Cache settings
cache_dir = "cache_files"
save_frequency = 10  # Save progress every N items

# Heurestics and APIs (scores should add up to 100)
scorers_config = {
    "heuristics": 30,  # Heuristics for all media types (default)
    "wikipedia": 70,  # Influence for all media types (free)
    "youtube": 0,  # YouTube channels (free but needs a key, https://console.cloud.google.com/))
    "similarweb": 0,  # Websites (paid, https://account.similarweb.com/)
    "listen_notes": 0,  # Podcast data (paid, https://www.listennotes.com/api/)
}

# API settings
user_agent = "media-bias-dashboard/1.0 (https://github.com/wh33les/data-visualization-portfolio; contact via GitHub) Python-requests/2.32.4"
timeout_seconds = 5
request_delay = 0.1  # Seconds between requests

# API cache filenames
api_cache_files = {
    "wikipedia": "wikipedia_cache.pkl",
    "youtube": "youtube_cache.pkl",
    "similarweb": "similarweb_cache.pkl",
    "listen_notes": "listen_notes_cache.pkl",
}

# API rate limits (calls per hour)
api_rate_limits = {
    "wikipedia": 10,
    "youtube": 10000,
    "similarweb": 100,
    "listen_notes": 1000,
}

warning_threshold = 0.8  # Warn at 80% of limit
stop_threshold = 0.9  # Stop at 90% of limit

# Heuristics config
# Scoring defaults
prominence_scores = {"tier1": 90, "tier2": 70, "tier3": 50, "unknown": 30}

# Source prominence tiers
tier1_domains = [
    # Top-tier podcasts/audio (massive listener base)
    "joe rogan",
    "the daily",
    "this american life",
    # Major TV networks & news programs
    "cnn",
    "fox news",
    "msnbc",
    "abc",
    "nbc",
    "cbs",
    "bbc",
    "60 minutes",
    "world news tonight",
    "nbc nightly news",
    "abc news",
    # High-traffic web sources
    "daily mail",
    "dailymail",
    "buzzfeed",
    "huffpost",
    "huffington post",
    "nytimes",
    "new york times",
    "washingtonpost",
    "washington post",
    "usatoday",
    "usa today",
    "tmz",
    # Wire services
    "reuters",
    "associated press",
    "ap news",
    # Public broadcasting
    "npr",
]

tier2_domains = [
    # Digital-native media
    "politico",
    "vox",
    "axios",
    "thehill",
    "the hill",
    "slate",
    # Cable news personalities
    "anderson cooper",
    "rachel maddow",
    "morning joe",
    "tucker carlson",
    # Popular podcasts
    "pod save america",
    "radiolab",
    "serial",
    # Other significant sources
    "pbs",
    "wapo",
    "ny times",
]

tier3_indicators = [
    "podcast",
    "show",
    "radio",
    "news",
    "television",
    "tv",
]
