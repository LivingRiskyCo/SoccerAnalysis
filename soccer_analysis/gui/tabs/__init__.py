"""
GUI Tab Components
"""

from .gallery_tab import GalleryTab
from .roster_tab import RosterTab
from .event_detection_tab import EventDetectionTab
from .analysis_tab import AnalysisTab
from .visualization_tab import VisualizationTab
from .tracking_tab import TrackingTab
from .advanced_tab import AdvancedTab

# Try to import RecognitionTab (may not be available)
try:
    from .recognition_tab import RecognitionTab
    RECOGNITION_AVAILABLE = True
except ImportError:
    RecognitionTab = None
    RECOGNITION_AVAILABLE = False

# Try to import MLTab (may not be available)
try:
    from .ml_tab import MLTab
    ML_TAB_AVAILABLE = True
except ImportError:
    MLTab = None
    ML_TAB_AVAILABLE = False

__all__ = [
    'GalleryTab', 
    'RosterTab', 
    'EventDetectionTab', 
    'AnalysisTab',
    'VisualizationTab',
    'TrackingTab',
    'AdvancedTab'
]

if RECOGNITION_AVAILABLE:
    __all__.append('RecognitionTab')

if ML_TAB_AVAILABLE:
    __all__.append('MLTab')
