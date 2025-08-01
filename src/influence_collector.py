# influence_collector.py
"""
Multi-Medium Influence Collector with Standardized API Management
Works reliably for Web Articles, TV Shows, AND Podcasts
Features consistent quota tracking across all APIs
"""

import pandas as pd
import requests
import time
import logging
import os
from datetime import datetime

# Import configuration and base exception
import config


class RobustInfluenceCollector:
    def __init__(self):
        # Setup logging level from config FIRST
        log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        logging.basicConfig(
            level=log_levels.get(config.log_level, logging.WARNING),
            format="%(filename)s: %(levelname)s: %(message)s",
        )

        # Filter enabled scorers (non-zero weights)
        self.enabled_scorers = {k: v for k, v in config.scorers_config.items() if v > 0}

        # Validate scorer configuration weights
        total_weight = sum(self.enabled_scorers.values())
        if total_weight != 100:
            raise ValueError(
                f"Enabled scorer weights must sum to 100, got {total_weight}. Change in config.py."
            )

        # Validate prominence scores (always check, even if not used)
        max_score = max(config.prominence_scores.values())
        if max_score > 100:
            raise ValueError(f"Prominence scores cannot exceed 100, found {max_score}")

        logging.info(f"Enabled scorers and weights: {self.enabled_scorers}")

        # Create standardized API managers for each enabled API
        self.api_managers = {}

        # Initialize session only if we have APIs that make HTTP requests
        if any(k != "heuristics" for k in self.enabled_scorers.keys()):
            # Import APIManager only when APIs are actually enabled
            from apis.api_manager import APIManager, RateLimitExceeded

            self.RateLimitExceeded = RateLimitExceeded

            self.session = requests.Session()
            self.session.headers.update({"User-Agent": config.user_agent})
            logging.info("HTTP session initialized for API clients")

        else:
            # No APIs enabled - don't import APIManager at all
            self.RateLimitExceeded = None  # Needed for a later conditional
            logging.info(
                "No API clients enabled - skipping HTTP session and cache management setup"
            )

        # Initialize APIs with standardized quota management
        if "wikipedia" in self.enabled_scorers:
            from apis.wikipedia_api import WikipediaAPI

            # Wikipedia is rate-limited, not quota-based
            self.api_managers["wikipedia"] = APIManager(
                "Wikipedia",
                daily_quota_limit=None,  # No daily quota
                hourly_limit=200,  # Rate limited instead
            )
            self.wikipedia_api = WikipediaAPI(
                session=self.session, api_manager=self.api_managers["wikipedia"]
            )
            logging.info("Wikipedia API initialized with rate limiting")

        if "youtube" in self.enabled_scorers:
            from apis.youtube_api import YouTubeAPI

            # YouTube is quota-based (10,000 units per day)
            self.api_managers["youtube"] = APIManager(
                "YouTube",
                daily_quota_limit=10000,  # YouTube's daily quota
                hourly_limit=None,  # No hourly limit
            )
            self.youtube_api = YouTubeAPI(
                session=self.session, api_manager=self.api_managers["youtube"]
            )
            logging.info("YouTube API initialized with quota tracking")

        if "similarweb" in self.enabled_scorers:
            # TODO: Implement SimilarWeb API with appropriate limits
            self.api_managers["similarweb"] = APIManager(
                "SimilarWeb", daily_quota_limit=1000, hourly_limit=100  # Example quota
            )
            logging.info("SimilarWeb API enabled but not yet implemented")

        if "listen_notes" in self.enabled_scorers:
            # TODO: Implement Listen Notes API with appropriate limits
            self.api_managers["listen_notes"] = APIManager(
                "Listen Notes",
                daily_quota_limit=10000,  # Example quota
                hourly_limit=1000,
            )
            logging.info("Listen Notes API enabled but not yet implemented")

    def get_source_prominence_score(self, source_name):
        """Calculate prominence score using configured tiers"""
        clean_source_name = source_name.strip()
        name_lower = clean_source_name.lower()

        if any(domain in name_lower for domain in config.tier1_domains):
            score = config.prominence_scores["tier1"]
            logging.info(f"Tier 1 match: {clean_source_name} -> {score}")
        elif any(domain in name_lower for domain in config.tier2_domains):
            score = config.prominence_scores["tier2"]
            logging.info(f"Tier 2 match: {clean_source_name} -> {score}")
        elif any(indicator in name_lower for indicator in config.tier3_indicators):
            score = config.prominence_scores["tier3"]
            logging.info(f"Tier 3 match: {clean_source_name} -> {score}")
        else:
            score = config.prominence_scores["unknown"]
            logging.info(f"Unknown source: {clean_source_name} -> {score}")

        return {"source_prominence_score": min(100, score)}

    def calculate_robust_influence_score(self, all_metrics):
        """Calculate final influence score using only enabled scorers"""
        final_score = 0

        # Use enabled scorer weights
        if "heuristics" in self.enabled_scorers:
            prominence_score = all_metrics.get("source_prominence_score", 0)
            heuristics_weight = self.enabled_scorers["heuristics"] / 100
            final_score += prominence_score * heuristics_weight

        if "wikipedia" in self.enabled_scorers:
            wiki_score = all_metrics.get("wikipedia_score", 0)
            wikipedia_weight = self.enabled_scorers["wikipedia"] / 100
            final_score += wiki_score * wikipedia_weight

        if "youtube" in self.enabled_scorers:
            youtube_score = all_metrics.get("youtube_subscriber_score", 0)
            youtube_weight = self.enabled_scorers["youtube"] / 100
            final_score += youtube_score * youtube_weight

        # TODO: Add other scorer scores when implemented

        return min(100, final_score)

    def get_required_columns(self):
        """Dynamically determine which columns to add based on enabled scorers"""
        columns = ["robust_influence_score"]  # Always include final score

        if "heuristics" in self.enabled_scorers:
            columns.append("source_prominence_score")

        if "wikipedia" in self.enabled_scorers:
            columns.extend(
                [
                    "has_wikipedia_page",
                    "wikipedia_title",
                    "wikipedia_avg_daily_views",
                    "wikipedia_score",
                ]
            )

        if "youtube" in self.enabled_scorers:
            columns.extend(
                [
                    "youtube_subscriber_count",
                    "youtube_subscribers",
                    "youtube_subscriber_score",
                ]
            )

        # Add other scorer columns as needed...
        return columns

    def process_all_media_types(self, df):
        """Process all sources with standardized API management"""
        # Get dynamic columns based on enabled scorers
        new_columns = self.get_required_columns()
        new_cols_dict = {col: None for col in new_columns if col not in df.columns}
        df = df.assign(**new_cols_dict)

        for idx, row in df.iterrows():
            source_name = row["Moniker"]
            clean_source_name = source_name.strip()
            media_type = row["Mediatype"]
            url = row.get("Main Url", "")

            print(f"Processing {idx+1}/{len(df)}: {clean_source_name[:40]}...")

            all_metrics = {}

            try:
                # Get Wikipedia data if enabled
                if "wikipedia" in self.enabled_scorers and hasattr(
                    self, "wikipedia_api"
                ):
                    wiki_data = self.wikipedia_api.get_wikipedia_pageviews(
                        clean_source_name, media_type
                    )
                    all_metrics.update(wiki_data)  # type:ignore

                # Get YouTube data if enabled
                if "youtube" in self.enabled_scorers and hasattr(self, "youtube_api"):
                    youtube_data = self.youtube_api.get_youtube_metrics(
                        clean_source_name, url
                    )
                    all_metrics.update(youtube_data)  # type:ignore

                # Future APIs can be added here...

            except Exception as e:
                # Handle rate limit exceptions from any API
                if self.RateLimitExceeded and isinstance(e, self.RateLimitExceeded):
                    print(
                        f"Rate/quota limit reached at source {idx+1}. Processed {idx} sources. Run again to continue."
                    )

                    # Save all caches when any API hits rate limit
                    self.save_all_caches_to_disk()

                    # Show quota summary before stopping
                    self.show_quota_summary()
                    break
                raise

            # Get prominence score if enabled
            if "heuristics" in self.enabled_scorers:
                prominence_data = self.get_source_prominence_score(clean_source_name)
                all_metrics.update(prominence_data)

            # Calculate final score
            influence_score = self.calculate_robust_influence_score(all_metrics)
            all_metrics["robust_influence_score"] = round(influence_score, 2)

            # Update dataframe
            for key, value in all_metrics.items():
                if key in df.columns:
                    df.at[idx, key] = value

            # Sleep and cache (for APIs)
            if self.api_managers:
                time.sleep(config.request_delay)

                # Save progress periodically within the same API check
                if (idx + 1) % config.save_frequency == 0:
                    self.save_all_caches_to_disk()
                    logging.info(f"Cache files saved to disk ({idx + 1}/{len(df)})")

        # Final save - only if APIs exist
        if self.api_managers:  # Only save if there are API managers
            self.save_all_caches_to_disk()

        # Convert to proper numeric types for only the columns that exist
        numeric_columns = self._get_numeric_columns()
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def _get_numeric_columns(self):
        """Get numeric column names based on enabled scorers"""
        numeric_columns = ["robust_influence_score"]  # Always numeric

        if "heuristics" in self.enabled_scorers:
            numeric_columns.append("source_prominence_score")

        if "wikipedia" in self.enabled_scorers:
            numeric_columns.extend(["wikipedia_score", "wikipedia_avg_daily_views"])

        if "youtube" in self.enabled_scorers:
            numeric_columns.extend(["youtube_subscribers", "youtube_subscriber_score"])

        # Add other APIs as needed
        return numeric_columns

    def save_all_caches_to_disk(self):
        """Save all enabled API caches to disk"""
        if not hasattr(self, "api_managers") or not self.api_managers:
            logging.debug("No API managers to save")
            return

        for api_name, api_manager in self.api_managers.items():
            api_manager.save_cache_to_disk()
            logging.debug(f"Saved {api_name} cache")

    def show_quota_summary(self):
        """Show detailed quota usage summary for all APIs"""
        if not self.api_managers:
            return

        print(f"\n" + "=" * 60)
        print("API QUOTA/RATE USAGE SUMMARY")
        print("=" * 60)

        for api_name, api_manager in self.api_managers.items():
            summary = api_manager.get_usage_summary()

            print(f"\n{summary['api_name']}:")
            if summary["type"] == "quota":
                usage_pct = summary["usage_percent"]
                status_text = (
                    "CRITICAL"
                    if summary["status"] == "critical"
                    else "WARNING" if summary["status"] == "warning" else "OK"
                )
                print(f"  Status: {status_text}")
                print(
                    f"  Quota: {summary['quota_used']:,}/{summary['quota_limit']:,} units ({usage_pct:.1f}%)"
                )
                print(f"  API Calls: {summary['calls']}")
                remaining = summary["quota_limit"] - summary["quota_used"]
                print(f"  Remaining: {remaining:,} units")
            else:
                print(f"  API Calls: {summary['calls']}")
                print(
                    f"  Rate: {summary['rate']:.1f} calls/hour (limit: {summary['rate_limit']})"
                )

    def show_summary(self, df):
        """Show results summary with quota information"""
        print("\n" + "=" * 60)
        print("MULTI-MEDIUM INFLUENCE ANALYSIS RESULTS")
        print("=" * 60)

        total_sources = len(df)
        processed = df["robust_influence_score"].notna().sum()
        print(f"Processed: {processed}/{total_sources} sources")

        # Show quota summary
        self.show_quota_summary()

        # Top 10 overall
        print(f"\nTOP INFLUENCE SCORES:")
        valid_df = df.dropna(subset=["robust_influence_score"])
        if len(valid_df) > 0:
            top_10 = valid_df.nlargest(10, "robust_influence_score")
            for i, (_, row) in enumerate(top_10.iterrows(), 1):
                score = row["robust_influence_score"]
                media_type = row["Mediatype"]
                wiki = "[WIKI]" if row.get("has_wikipedia_page") else ""
                youtube = "[YT]" if row.get("youtube_subscribers", 0) > 0 else ""
                print(
                    f"{i:2}. {row['Moniker'][:35]}... ({score:.1f}) [{media_type}] {wiki} {youtube}"
                )


def main():
    """Main function"""
    print("ROBUST MULTI-MEDIUM INFLUENCE COLLECTOR")
    print("=" * 50)

    collector = RobustInfluenceCollector()

    try:
        df = pd.read_csv(config.input_file)
        print(f"Loaded {len(df)} sources from {config.input_file}")

        df_enhanced = collector.process_all_media_types(df)
        collector.show_summary(df_enhanced)

        df_enhanced.to_csv(config.output_file, index=False)
        print(f"\nResults saved to {config.output_file}")

    except FileNotFoundError:
        print(f"ERROR: File not found: {config.input_file}")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. Progress saved.")
        collector.save_all_caches_to_disk()
        return 1


if __name__ == "__main__":
    exit(main())
