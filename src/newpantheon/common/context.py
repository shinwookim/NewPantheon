"""
Provides contexts for use in various Pantheon components.
Mostly common directories
"""

from pathlib import Path
import sys

src_dir = Path(__file__).resolve().parent.parent
base_dir = src_dir.parent
sys.path.append(str(src_dir))
tmp_dir = base_dir / "tmp"

default_config_location: Path = src_dir / "experiments" / "default_config.yml"
