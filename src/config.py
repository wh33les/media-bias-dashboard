# config.py
"""
Configuration settings for the influence collector with standardized API management
Supports both quota-based APIs (YouTube) and rate-limited APIs (Wikipedia)
"""

# Logging level: "DEBUG", "INFO", "WARNING", "ERROR"
log_level = "INFO"  # Set to INFO to see quota tracking

# File paths
input_file = "tests/test_data.csv"
output_file = "tests/test_results.csv"

# Cache settings
cache_dir = "tests/cache_files"
save_frequency = 10  # Save progress every N items

# Scorers configuration (scores should add up to 100)
scorers_config = {
    "heuristics": 60,  # Heuristics for all media types (default)
    "wikipedia": 40,  # Influence for all media types (free, rate-limited)
    "youtube": 0,  # YouTube channels (quota-based, temporarily disabled)
    "similarweb": 0,  # Websites (paid, not implemented)
    "listen_notes": 0,  # Podcast data (paid, not implemented)
}

# API settings
user_agent = "media-bias-dashboard/1.0 (https://github.com/wh33les/media-bias-dashboard; contact via GitHub) Python-requests/2.32.4"
timeout_seconds = 5
request_delay = 0.1  # Seconds between requests

# Quota management thresholds
warning_threshold = 0.8  # Warn at 80% of limit
stop_threshold = 0.9  # Stop at 90% of limit

# ----------

# Heuristics config
# Scoring defaults
prominence_scores = {"tier1": 95, "tier2": 75, "tier3": 55, "unknown": 25}

# Source prominence tiers - Demonstrates domain expertise
tier1_domains = [
    # Top-tier podcasts/audio (massive listener base)
    "joe rogan",
    "the daily",
    "this american life",
    "npr",
    # Major TV networks & flagship news programs
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
    # Cable news personalities
    "anderson cooper",
    "rachel maddow",
    "tucker carlson",
    "sean hannity",
    "morning joe",
    "don lemon",
    "chris cuomo",
    # High-traffic web sources
    "daily mail",
    "dailymail",
    "huffpost",
    "huffington post",
    "buzzfeed",
    "tmz",
    "reddit",
    # Premier newspapers & digital news
    "new york times",
    "nytimes",
    "washington post",
    "washingtonpost",
    "wall street journal",
    "wsj",
    "usa today",
    "usatoday",
    # Wire services & news agencies
    "reuters",
    "associated press",
    "ap news",
    "bloomberg",
]

tier2_domains = [
    # Digital-native & political media
    "politico",
    "vox",
    "axios",
    "thehill",
    "the hill",
    "slate",
    "salon",
    "breitbart",
    "daily wire",
    "jacobin",
    "mother jones",
    # Popular podcasts & personalities
    "pod save america",
    "radiolab",
    "serial",
    "conan",
    "marc maron",
    "bill maher",
    "stephen colbert",
    "trevor noah",
    "john oliver",
    # Regional major sources & public broadcasting
    "pbs",
    "npr",
    "bbc",
    "guardian",
    "independent",
    # Tech & business media
    "techcrunch",
    "wired",
    "ars technica",
    "verge",
    "engadget",
    "fortune",
    "forbes",
    "business insider",
    # Entertainment & culture
    "entertainment weekly",
    "variety",
    "hollywood reporter",
    "rolling stone",
    "pitchfork",
    "vulture",
]

tier3_indicators = [
    # Generic media indicators
    "podcast",
    "show",
    "radio",
    "news",
    "television",
    "tv",
    "daily",
    "weekly",
    "times",
    "post",
    "herald",
    "tribune",
    "blog",
    "substack",
    "newsletter",
    "channel",
    # Platform indicators
    "youtube",
    "spotify",
    "apple podcasts",
    "soundcloud",
    "medium",
    "wordpress",
    "blogspot",
    # Content type indicators
    "review",
    "commentary",
    "analysis",
    "opinion",
    "editorial",
]

# # ML Engineering Enhancement: Add confidence scoring for better feature engineering
# confidence_multipliers = {
#     "exact_match": 1.0,  # Exact domain match in tier lists
#     "partial_match": 0.85,  # Partial match with high confidence
#     "keyword_match": 0.7,  # Keyword indicators match
#     "unknown": 0.5,  # Low confidence fallback
# }
