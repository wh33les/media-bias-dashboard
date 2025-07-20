# File: src/__init__.py
"""
Initialize the src package and load config globally
This makes all imports work cleanly and safely
"""
import sys
import importlib.util
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Load config once and make it globally available
config_path = current_dir / "config.py"

if config_path.exists():
    spec = importlib.util.spec_from_file_location("config", config_path)
    if spec is not None and spec.loader is not None:
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        sys.modules["config"] = config
    else:
        print(f"Warning: Could not load config from {config_path}")
else:
    print(f"Warning: Config file not found at {config_path}")
