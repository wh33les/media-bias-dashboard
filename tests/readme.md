# Test Files

This directory contains test datasets and validation materials for the Media Bias Dashboard project.

## Test Data

### `test_data.csv`
- **Purpose**: Small subset (19 sources) for rapid testing and development
- **Content**: Mix of Web/Articles, TV/Video, and Podcast/Audio sources
- **Use case**: Quick validation of API integrations and scoring algorithms

### `test_results.csv`
- **Purpose**: Expected output from processing test_data.csv
- **Content**: Includes Wikipedia metrics, influence scores, and prominence ratings
- **Use case**: Regression testing to ensure consistent results

## Visualization

### `test_data.twb`
- **Purpose**: Tableau workbook for testing data visualization components
- **Content**: Bias vs. Reliability scatter plot with influence scoring
- **Features**: Custom color palette, interactive tooltips, bias categorization

## Running Tests

To run tests with the small dataset:

1. **Update `config.py`:**
   ```python
   # Change these lines in config.py:
   input_file = "tests/test_data.csv"
   output_file = "tests/test_results.csv" 
   cache_dir = "tests/cache_files"
   ```

2. **Run the collector:**
   ```bash
   python src/influence_collector.py
   ```

## Cache Management

Test runs use separate cache files in `tests/cache_files/` to:
- Prevent test data from polluting production caches
- Ensure reproducible test results
- Speed up test iterations with smaller cache files

## Test Configuration

The system can be configured for testing by:
1. Reducing API quotas in `config.py`
2. Enabling only free APIs
3. Using smaller datasets for faster iteration
4. Using isolated test cache directory (`tests/cache_files/`)