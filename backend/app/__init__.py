"""
VisionAI Backend Application.

Enterprise-grade AI-powered video surveillance and analytics platform.
"""

import sys
from pathlib import Path

# Ensure bundled vendor dependencies (such as google-genai) are resolvable
_vendor_dir = Path(__file__).resolve().parent / "vendor"
if _vendor_dir.is_dir() and str(_vendor_dir) not in sys.path:
    sys.path.insert(0, str(_vendor_dir))

__version__ = "1.0.0"
__author__ = "VisionAI Team"
__description__ = "AI-powered video surveillance and analytics platform"
