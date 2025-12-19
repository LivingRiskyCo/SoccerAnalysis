"""
Main entry point for Soccer Analysis Tool
"""

import sys
import os
from pathlib import Path

# Add parent directories to path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
root_dir = parent_dir.parent

# Add paths for imports
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))


def main():
    """Main entry point"""
    import tkinter as tk
    
    # Show splash screen first
    try:
        from .utils.splash_screen import show_splash_screen
    except ImportError:
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
            # Create splash with 0 duration (we'll close it manually after GUI loads)
            splash = show_splash_screen(duration=0, root=root)
            # Force splash to appear and process events
            if splash:
                splash.show()
            # Update root to process events and show splash
            root.update_idletasks()
            root.update()
            # Process a few more events to ensure splash is visible
            import time
            for _ in range(10):
                if splash and hasattr(splash, 'splash'):
                    splash.splash.update_idletasks()
                    splash.splash.update()
                root.update_idletasks()
                root.update()
                time.sleep(0.05)  # Small delay to ensure splash is drawn
        except Exception as e:
            print(f"Could not show splash screen: {e}")
            import traceback
            traceback.print_exc()
    
    # Try relative import first (when run as module), then absolute (when run as script)
    try:
        from .gui.main_window import SoccerAnalysisGUI
    except ImportError:
        # Fallback to absolute import when run as script
        try:
            from soccer_analysis.gui.main_window import SoccerAnalysisGUI
        except ImportError:
            # Final fallback - direct import
            from gui.main_window import SoccerAnalysisGUI
    
    # Create main application (this may take a moment)
    # Keep splash visible during GUI creation by processing events periodically
    app = None
    try:
        # Process events periodically during GUI creation to keep splash visible
        def create_gui():
            nonlocal app
            app = SoccerAnalysisGUI(root)
        
        # Run GUI creation in a way that allows splash to stay visible
        create_gui()
        
        # Process events a few more times to ensure GUI is ready
        for _ in range(3):
            root.update_idletasks()
            root.update()
    except Exception as e:
        print(f"Error creating GUI: {e}")
        import traceback
        traceback.print_exc()
    
    # Close splash screen after GUI is created (with a small delay to ensure GUI is visible)
    if splash:
        try:
            # Keep splash visible for at least 1.5 seconds total, then close
            def close_splash():
                try:
                    splash.close()
                except:
                    pass
            
            # Calculate elapsed time and ensure minimum display time
            import time
            start_time = getattr(splash, '_start_time', time.time())
            elapsed = time.time() - start_time
            remaining = max(0, 1.5 - elapsed)  # Ensure at least 1.5 seconds total
            if remaining > 0:
                root.after(int(remaining * 1000), close_splash)
            else:
                # Already been 1.5 seconds, close after brief delay
                root.after(200, close_splash)
        except:
            pass
    
    # Show main window
    root.deiconify()
    root.update_idletasks()
    root.update()
    root.mainloop()


if __name__ == "__main__":
    main()

