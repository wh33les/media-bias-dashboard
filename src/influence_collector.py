# influence_collector.py
"""
Multi-Medium Influence Collector (Simplified Configurable Version)
Works reliably for Web Articles, TV Shows, AND Podcasts
SAVES PROGRESS TO DISK - can resume if interrupted!

Simple configuration via config.py file
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

        # Create cache managers for each enabled API (appears in later conditionals)
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

        # Conditionally import and initialize APIs with their cache managers
        if "wikipedia" in self.enabled_scorers:
            from apis.wikipedia_api import WikipediaAPI

            # Create dedicated cache manager for Wikipedia
            self.api_managers["wikipedia"] = APIManager("Wikipedia")
            self.wikipedia_api = WikipediaAPI(
                api_manager=self.api_managers["wikipedia"]
            )
            logging.info("Wikipedia API initialized")

        if "youtube" in self.enabled_scorers:
            from apis.youtube_api import YouTubeAPI

            # Create dedicated cache manager for YouTube
            self.api_managers["youtube"] = APIManager("YouTube")
            self.youtube_api = YouTubeAPI(api_manager=self.api_managers["youtube"])
            logging.info("YouTube API initialized")

        if "similarweb" in self.enabled_scorers:
            # TODO: Implement SimilarWeb API
            self.api_managers["similarweb"] = APIManager("SimilarWeb")
            # self.similarweb_api = SimilarWebAPI(cache_manager=self.api_managers["similarweb"])
            logging.info("SimilarWeb API enabled but not yet implemented")

        if "listen_notes" in self.enabled_scorers:
            # TODO: Implement Listen Notes API
            self.api_managers["listen_notes"] = APIManager("Listen Notes")
            # self.listen_notes_api = ListenNotesAPI(cache_manager=self.api_managers["listen_notes"])
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

        # TODO: Add other scorer scores when implemented
        # if "youtube" in self.enabled_scorers:
        #     youtube_score = all_metrics.get("youtube_score", 0)
        #     youtube_weight = self.enabled_scorers["youtube"] / 100
        #     final_score += (youtube_score / 100) * youtube_weight

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
                ["youtube_subscriber_count", "youtube_view_count", "youtube_score"]
            )

        # Add other scorer columns as needed...
        return columns

    def process_all_media_types(self, df):
        """Process all sources"""
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
                    all_metrics.update(wiki_data)

                # Get YouTube data if enabled
                if "youtube" in self.enabled_scorers and hasattr(self, "youtube_api"):
                    youtube_data = self.youtube_api.get_youtube_metrics(
                        clean_source_name, url
                    )
                    all_metrics.update(youtube_data)

                # Future APIs can be added here...

            except Exception as e:
                # Handle rate limit exceptions from any API
                if self.RateLimitExceeded and isinstance(e, self.RateLimitExceeded):
                    print(
                        f"Rate limit reached. Processed {idx} sources. Run again to continue."
                    )

                    # Save all caches when any API hits rate limit
                    self.save_all_caches_to_disk()
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
            numeric_columns.extend(["youtube_subscribers", "youtube_score"])

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

    def show_summary(self, df):
        """Show results summary"""
        print("\n" + "=" * 60)
        print("MULTI-MEDIUM INFLUENCE ANALYSIS RESULTS")
        print("=" * 60)

        total_sources = len(df)
        processed = df["robust_influence_score"].notna().sum()
        print(f"Processed: {processed}/{total_sources} sources")

        # Add detailed API call information - efficient version:
        if self.api_managers:
            # Quick check without detailed processing
            total_calls = sum(mgr.api_call_count for mgr in self.api_managers.values())

            if total_calls > 0:
                # Get detailed info (earliest_start, api_details) without recalculating total_calls
                _, earliest_start, api_details = self._get_api_stats()
                print(f"Total API calls made: {total_calls}")

                if earliest_start is not None:
                    elapsed_hours = (
                        datetime.now() - earliest_start
                    ).total_seconds() / 3600
                    print(f"Runtime: {elapsed_hours:.2f} hours")

                # Show per-API breakdown
                if api_details:
                    print("API breakdown:")
                    for detail in api_details:
                        print(f"  - {detail}")
            else:
                # APIs enabled but no calls made (all cache hits)
                print(f"Total API calls made: 0 (all data served from cache)")
                print("Enabled APIs:")
                for api_name, mgr in self.api_managers.items():
                    cache_entries = len(mgr.cache_data)
                    print(f"  - {api_name}: {cache_entries} cached entries")
        else:
            # No APIs enabled at all (heuristics only)
            print(f"Total API calls made: 0 (heuristics-only processing)")
            print(f"Enabled scorers: {', '.join(self.enabled_scorers.keys())}")

        # Top 10 overall
        print(f"\nTOP INFLUENCE SCORES:")
        valid_df = df.dropna(subset=["robust_influence_score"])
        if len(valid_df) > 0:
            top_10 = valid_df.nlargest(10, "robust_influence_score")
            for i, (_, row) in enumerate(top_10.iterrows(), 1):
                score = row["robust_influence_score"]
                media_type = row["Mediatype"]
                wiki = "[WIKI]" if row.get("has_wikipedia_page") else ""
                print(
                    f"{i:2}. {row['Moniker'][:35]}... ({score:.1f}) [{media_type}] {wiki}"
                )

    def _get_api_stats(self):
        """Get aggregated API statistics from all enabled APIs"""
        total_calls = 0
        earliest_start = None
        api_details = []

        for api_name, api_manager in self.api_managers.items():
            calls = api_manager.api_call_count
            total_calls += calls

            if calls > 0:  # Only include APIs that were actually used
                api_details.append(f"{api_name}: {calls} calls")

                if (
                    earliest_start is None
                    or api_manager.session_start_time < earliest_start
                ):
                    earliest_start = api_manager.session_start_time

        return total_calls, earliest_start, api_details


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
