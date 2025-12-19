"""
Analysis Engine Modules
Broken down from combined_analysis_optimized.py for better organization
"""

__version__ = "2.0.0"

# Import main analysis function
try:
    from .core.analyzer import combined_analysis_optimized
    __all__ = ['combined_analysis_optimized']
except ImportError:
    # During migration, fallback to legacy
    __all__ = []

