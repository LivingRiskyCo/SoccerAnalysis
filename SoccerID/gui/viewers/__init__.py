"""
Viewers package - includes unified viewer and legacy viewers
"""

from .unified_viewer import UnifiedViewer

# Legacy imports for backward compatibility
try:
    from .setup_wizard import SetupWizard
except ImportError:
    SetupWizard = None

try:
    from .playback_viewer import PlaybackViewer
except ImportError:
    PlaybackViewer = None

__all__ = ['UnifiedViewer', 'SetupWizard', 'PlaybackViewer']
