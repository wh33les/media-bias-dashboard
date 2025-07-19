# config.py
"""
Configuration settings for the influence collector
Simple Python config - easy to modify and can include comments
"""

# File paths
input_file = "data/requested_data.csv"
output_file = "data/final_tableau_data.csv"

# Cache settings
cache_dir = "cache_files"
save_frequency = 10  # Save progress every N items

# API settings
user_agent = "media-bias-dashboard/1.0 (https://github.com/wh33les/data-visualization-portfolio; contact via GitHub) Python-requests/2.32.4"
timeout_seconds = 5
request_delay = 0.1  # Seconds between requests

# Rate limiting
wikipedia_hourly_limit = 500
warning_threshold = 0.8  # Warn at 80% of limit
stop_threshold = 0.9  # Stop at 90% of limit

# Scoring weights (must sum to 100)
wikipedia_weight = 70
prominence_weight = 30

# Scoring defaults
tier1_score = 90
tier2_score = 70
tier3_score = 50
unknown_source_score = 30

# Logging level: "DEBUG", "INFO", "WARNING", "ERROR"
log_level = "INFO"  # Quiet by default

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
