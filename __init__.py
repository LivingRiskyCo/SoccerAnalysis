"""
Soccer Analysis Tool - Refactored Codebase
"""

__version__ = "2.0.0"

# Import main entry points
from .main import main
from .gui.main_window import SoccerAnalysisGUI

__all__ = ['main', 'SoccerAnalysisGUI']

