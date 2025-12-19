"""
Main entry point for Soccer Analysis Tool
"""

import sys
import os
from pathlib import Path

# Add current directory to path for imports
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

def main():
    """Main entry point"""
    import tkinter as tk
    
    # Show splash screen first
    try:
        from soccer_analysis.utils.splash_screen import show_splash_screen
    except ImportError:
        show_splash_screen = None
    
    # Create root window (hidden initially)
    root = tk.Tk()
    root.withdraw()  # Hide until splash is done
    
    # Show splash screen
    splash = None
    if show_splash_screen:
        try:
            splash = show_splash_screen(duration=2000, root=root)
            root.update()  # Update to show splash
        except Exception as e:
            print(f"Could not show splash screen: {e}")
    
    # Try to import from new structure first, then legacy
    try:
        from soccer_analysis.gui.main_window import SoccerAnalysisGUI
    except ImportError:
        try:
            # Try legacy import
            from legacy.soccer_analysis_gui import SoccerAnalysisGUI
        except ImportError:
            # Final fallback - direct import
            try:
                from soccer_analysis_gui import SoccerAnalysisGUI
            except ImportError:
                raise ImportError(
                    "Could not import SoccerAnalysisGUI. "
                    "Please ensure the GUI module is available."
                )
    
    # Create main application
    app = SoccerAnalysisGUI(root)
    
    # Close splash screen if still open
    if splash:
        try:
            splash.close()
        except:
            pass
    
    # Show main window
    root.deiconify()
    root.mainloop()

if __name__ == "__main__":
    main()

