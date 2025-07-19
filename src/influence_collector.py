#!/usr/bin/env python3
"""
Multi-Medium Influence Collector (Simplified Configurable Version)
Works reliably for Web Articles, TV Shows, AND Podcasts
Uses only stable, reliable data sources - no fragile APIs
SAVES PROGRESS TO DISK - can resume if interrupted!

Simple configuration via config.py file
"""

import pandas as pd
import requests
import time
import logging
from urllib.parse import quote
import re
import pickle
import os
from datetime import datetime

# Import configuration
import config


class RateLimitExceeded(Exception):
    """Raised when API rate limits are exceeded"""

    pass


class RobustInfluenceCollector:
    def __init__(self):
        # Setup logging level from config
        log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        logging.basicConfig(
            level=log_levels.get(config.log_level, logging.WARNING),
            format="%(levelname)s: %(message)s",
        )

        # Initialize session
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

        # Setup cache (Wikipedia only)
        os.makedirs(config.cache_dir, exist_ok=True)
        self.wikipedia_cache_file = os.path.join(
            config.cache_dir, "wikipedia_cache.pkl"
        )

        self.wikipedia_cache = self._load_cache(self.wikipedia_cache_file)

        # Track API calls
        self.api_call_count = 0
        self.session_start_time = datetime.now()

        logging.info(f"Cache: {len(self.wikipedia_cache)} Wikipedia entries")

    def _load_cache(self, cache_file):
        """Load cache from disk"""
        try:
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    return pickle.load(f)
        except Exception as e:
            logging.warning(f"Could not load {cache_file}: {e}")
        return {}

    def _save_cache(self, cache_data, cache_file):
        """Save cache to disk"""
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(cache_data, f)
            logging.debug(f"Saved {len(cache_data)} entries to {cache_file}")
        except Exception as e:
            logging.error(f"Could not save {cache_file}: {e}")

    def _log_api_call(self, description=""):
        """Log API call with current count and rate"""
        self.api_call_count += 1
        elapsed_hours = (
            datetime.now() - self.session_start_time
        ).total_seconds() / 3600

        if elapsed_hours >= 1.0:
            calls_per_hour = self.api_call_count / elapsed_hours
            logging.info(
                f"API Call #{self.api_call_count}: {description} (Rate: {calls_per_hour:.0f}/hour)"
            )
        else:
            logging.info(f"API Call #{self.api_call_count}: {description}")

    def _is_rate_limit_exceeded(self):
        """Check rate limits"""
        elapsed_hours = (
            datetime.now() - self.session_start_time
        ).total_seconds() / 3600

        # Simple logic: if less than 1 hour, just check total calls
        if elapsed_hours < 1.0:
            warning_threshold = config.wikipedia_hourly_limit * config.warning_threshold
            stop_threshold = config.wikipedia_hourly_limit * config.stop_threshold

            if self.api_call_count > warning_threshold:
                logging.warning(
                    f"High API usage: {self.api_call_count} calls in {elapsed_hours:.2f} hours (warning at {warning_threshold})"
                )

            if self.api_call_count > stop_threshold:
                logging.error("Approaching rate limit! Saving progress...")
                self._save_cache(self.wikipedia_cache, self.wikipedia_cache_file)
                return True
        else:
            # After 1 hour, use calls per hour calculation
            calls_per_hour = self.api_call_count / elapsed_hours
            warning_threshold = config.wikipedia_hourly_limit * config.warning_threshold
            stop_threshold = config.wikipedia_hourly_limit * config.stop_threshold

            if calls_per_hour > warning_threshold:
                logging.warning(
                    f"High API usage: {calls_per_hour:.0f} calls/hour (limit: {config.wikipedia_hourly_limit})"
                )

            if calls_per_hour > stop_threshold:
                logging.error("Approaching rate limit! Saving progress...")
                self._save_cache(self.wikipedia_cache, self.wikipedia_cache_file)
                return True

        return False

    def get_wikipedia_pageviews(self, source_name, media_type):
        """Get Wikipedia pageviews with caching"""
        # Clean the source name first
        clean_source_name = source_name.strip()
        cache_key = f"{clean_source_name}_{media_type}"

        if cache_key in self.wikipedia_cache:
            logging.info(f"Wikipedia cache HIT: {clean_source_name}")
            return self.wikipedia_cache[cache_key]

        if self._is_rate_limit_exceeded():
            raise RateLimitExceeded("Wikipedia API rate limit reached")

        logging.info(f"Wikipedia cache MISS: fetching {clean_source_name}")
        result = {"has_wikipedia_page": False, "wikipedia_interest_score": 0}

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

                    # Use the new logging method:
                    self._log_api_call(f"Wikipedia summary for '{term}'")

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("type") == "standard":
                            # Get pageviews
                            page_title = data.get("title")
                            pageviews_url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{quote(page_title)}/daily/20240101/20241231"

                            pv_response = self.session.get(
                                pageviews_url, timeout=config.timeout_seconds
                            )

                            # Use the new logging method:
                            self._log_api_call(
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
                                        "wikipedia_interest_score": min(
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
            self.wikipedia_cache[cache_key] = result
            self._save_cache(self.wikipedia_cache, self.wikipedia_cache_file)

        return result

    def _clean_search_term(self, term):
        """Clean search term"""
        clean = re.sub(r"\s*\([^)]+\)$", "", term)  # Remove (parentheses)
        clean = re.sub(r":\s*.*$", "", clean)  # Remove : suffixes
        return clean.strip()

    def get_source_prominence_score(self, source_name, url=None):
        """Calculate prominence score using configured tiers"""
        clean_source_name = source_name.strip()
        name_lower = clean_source_name.lower()

        if any(domain in name_lower for domain in config.tier1_domains):
            score = config.tier1_score
            logging.info(f"Tier 1 match: {clean_source_name} -> {score}")
        elif any(domain in name_lower for domain in config.tier2_domains):
            score = config.tier2_score
            logging.info(f"Tier 2 match: {clean_source_name} -> {score}")
        elif any(indicator in name_lower for indicator in config.tier3_indicators):
            score = config.tier3_score
            logging.info(f"Tier 3 match: {clean_source_name} -> {score}")
        else:
            score = config.unknown_source_score
            logging.info(f"Unknown source: {clean_source_name} -> {score}")

        return {"source_prominence_score": min(100, score)}

    def calculate_robust_influence_score(self, all_metrics):
        """Calculate final influence score"""
        wiki_score = all_metrics.get("wikipedia_interest_score", 0)
        prominence_score = all_metrics.get("source_prominence_score", 0)

        final_score = (wiki_score / 100) * config.wikipedia_weight + (
            prominence_score / 100
        ) * config.prominence_weight
        return min(100, final_score)

    def process_all_media_types(self, df):
        """Process all sources"""
        logging.info("Processing sources with reliable metrics...")

        new_columns = [
            "has_wikipedia_page",
            "wikipedia_title",
            "wikipedia_avg_daily_views",
            "wikipedia_interest_score",
            "source_prominence_score",
            "robust_influence_score",
        ]

        for col in new_columns:
            if col not in df.columns:
                df[col] = None

        for idx, row in df.iterrows():
            source_name = row["Moniker"]
            clean_source_name = source_name.strip()
            media_type = row["Mediatype"]
            url = row.get("Main Url", "")

            print(f"Processing {idx+1}/{len(df)}: {clean_source_name[:40]}...")

            all_metrics = {}

            try:
                # Get Wikipedia data
                wiki_data = self.get_wikipedia_pageviews(clean_source_name, media_type)
                all_metrics.update(wiki_data)

            except RateLimitExceeded:
                print(
                    f"Rate limit reached. Processed {idx} sources. Run again to continue."
                )
                self._save_cache(self.wikipedia_cache, self.wikipedia_cache_file)
                break

            # Get prominence score
            prominence_data = self.get_source_prominence_score(clean_source_name, url)
            all_metrics.update(prominence_data)

            # Calculate final score
            influence_score = self.calculate_robust_influence_score(all_metrics)
            all_metrics["robust_influence_score"] = round(influence_score, 2)

            # Update dataframe
            for key, value in all_metrics.items():
                if key in df.columns:
                    df.at[idx, key] = value

            time.sleep(config.request_delay)

            # Save progress periodically
            if (idx + 1) % config.save_frequency == 0:
                self._save_cache(self.wikipedia_cache, self.wikipedia_cache_file)
                logging.info(f"Progress saved ({idx + 1}/{len(df)})")

        # Final save and cleanup
        self._save_cache(self.wikipedia_cache, self.wikipedia_cache_file)

        # Convert to proper numeric types
        numeric_columns = [
            "robust_influence_score",
            "wikipedia_interest_score",
            "source_prominence_score",
            "wikipedia_avg_daily_views",
        ]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def show_summary(self, df):
        """Show results summary"""
        print("\n" + "=" * 60)
        print("MULTI-MEDIUM INFLUENCE ANALYSIS RESULTS")
        print("=" * 60)

        total_sources = len(df)
        processed = df["robust_influence_score"].notna().sum()
        print(f"Processed: {processed}/{total_sources} sources")

        # Add detailed API call information:
        elapsed_hours = (
            datetime.now() - self.session_start_time
        ).total_seconds() / 3600
        print(f"Total API calls made: {self.api_call_count}")
        print(f"Runtime: {elapsed_hours:.2f} hours")

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


def main():
    """Main function"""
    print("ROBUST MULTI-MEDIUM INFLUENCE COLLECTOR")
    print("=" * 50)

    collector = RobustInfluenceCollector()

    try:
        df = pd.read_csv(config.input_file)
        print(f"Loaded {len(df)} sources from {config.input_file}")
        logging.info(f"Input file: {config.input_file}")

        df_enhanced = collector.process_all_media_types(df)
        collector.show_summary(df_enhanced)

        df_enhanced.to_csv(config.output_file, index=False)
        print(f"\nResults saved to {config.output_file}")

    except FileNotFoundError:
        print(f"ERROR: File not found: {config.input_file}")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. Progress saved.")
        collector._save_cache(collector.wikipedia_cache, collector.wikipedia_cache_file)
        return 1


if __name__ == "__main__":
    exit(main())
