"""
SoccerID - Professional Soccer Video Analysis Tool
Part of the SportID family (SoccerID, BasketballID, HockeyID, etc.)
"""

__version__ = "2.0.0"
__sport__ = "soccer"

# Import main entry points
try:
    from .main import main
    from .gui.main_window import SoccerAnalysisGUI
    
    __all__ = ['main', 'SoccerAnalysisGUI']
except ImportError:
    # During migration, some imports may fail
    __all__ = []
