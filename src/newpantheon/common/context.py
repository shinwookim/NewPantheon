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
