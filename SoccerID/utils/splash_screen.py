"""
Splash Screen for Soccer Analysis Tool
Shows on application startup
"""

import tkinter as tk
from PIL import Image, ImageTk
import os
import sys
import time
from pathlib import Path


class SplashScreen:
    """Splash screen window shown at startup"""
    
    def __init__(self, root=None, duration=2000):
        """
        Initialize splash screen
        
        Args:
            root: Optional parent window (creates new if None)
            duration: How long to show splash screen in milliseconds
        """
        self.duration = duration
        self.root = root if root else tk.Tk()
        self._start_time = time.time()
        
        # Hide main window if it's the root
        if root is None:
            self.root.withdraw()
        
        # Create splash window - use standalone Toplevel to ensure visibility
        # Even if root is hidden, the splash should be visible
        if root:
            self.splash = tk.Toplevel(root)
            # If root is hidden, make splash independent
            if not root.winfo_viewable():
                self.splash.transient(None)  # Make it independent
        else:
            self.splash = tk.Toplevel()
        
        self.splash.title("Soccer Video Analysis Tool")
        self.splash.overrideredirect(True)  # Remove window decorations
        
        # Make sure splash is visible even if root is hidden
        if root and root.winfo_viewable():
            self.splash.transient(root)
        else:
            self.splash.transient(None)  # Independent window
        
        self.splash.lift()  # Bring to front immediately
        try:
            self.splash.focus_force()  # Force focus to ensure visibility
        except:
            pass
        
        # Find splash screen image
        splash_path = self._find_splash_image()
        
        if splash_path and os.path.exists(splash_path):
            # Load and display image
            try:
                img = Image.open(splash_path)
                photo = ImageTk.PhotoImage(img)
                
                # Create label with image
                label = tk.Label(self.splash, image=photo, bg='#143214')
                label.image = photo  # Keep a reference
                label.pack()
                
                # Set window size to image size and center immediately
                self.splash.geometry(f"{img.width}x{img.height}")
                self.splash.update_idletasks()  # Force update to get actual size
                
                # Center window on screen
                self._center_window()
            except Exception as e:
                print(f"Could not load splash image: {e}")
                # Fallback: Create simple text splash
                self._create_text_splash()
                self.splash.update_idletasks()
                self._center_window()
        else:
            # Fallback: Create simple text splash
            self._create_text_splash()
            self.splash.update_idletasks()
            self._center_window()
        
        # Make window stay on top
        self.splash.attributes('-topmost', True)
        
        # Force window to appear
        self.splash.update_idletasks()
        self.splash.update()
        
        # Make sure it's really visible
        try:
            self.splash.deiconify()  # Ensure window is shown
        except:
            pass
        
        # Auto-close after duration (if duration > 0)
        if duration > 0:
            self.splash.after(duration, self.close)
    
    def _find_splash_image(self):
        """Find splash screen image in various locations"""
        # Get the root directory (where splash_screen.png should be)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Navigate up: utils -> soccer_analysis -> soccer_analysis -> root
        root_dir = Path(script_dir).parent.parent.parent
        
        possible_paths = [
            os.path.join(root_dir, 'splash_screen.png'),  # Root directory (most likely)
            'splash_screen.png',  # Current working directory
            os.path.join(os.getcwd(), 'splash_screen.png'),  # Current working directory (absolute)
            os.path.join(script_dir, '..', '..', '..', 'splash_screen.png'),  # Relative from utils
            os.path.join(script_dir, '..', '..', 'splash_screen.png'),  # Alternative relative
        ]
        
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return abs_path
        
        return None
    
    def _create_text_splash(self):
        """Create a simple text-based splash screen"""
        self.splash.configure(bg='#143214')
        self.splash.geometry('600x300')
        
        # Title
        title_label = tk.Label(
            self.splash,
            text="Soccer Video Analysis Tool",
            font=('Arial', 24, 'bold'),
            fg='white',
            bg='#143214'
        )
        title_label.pack(pady=40)
        
        # Subtitle
        subtitle_label = tk.Label(
            self.splash,
            text="Professional Player Tracking & Analytics",
            font=('Arial', 14),
            fg='#CCCCCC',
            bg='#143214'
        )
        subtitle_label.pack(pady=10)
        
        # Version
        version_label = tk.Label(
            self.splash,
            text="Version 2.0",
            font=('Arial', 10),
            fg='#999999',
            bg='#143214'
        )
        version_label.pack(pady=20)
        
        # Loading
        loading_label = tk.Label(
            self.splash,
            text="Loading...",
            font=('Arial', 10),
            fg='#999999',
            bg='#143214'
        )
        loading_label.pack(pady=10)
    
    def _center_window(self):
        """Center splash window on screen"""
        self.splash.update_idletasks()
        
        width = self.splash.winfo_width()
        height = self.splash.winfo_height()
        
        screen_width = self.splash.winfo_screenwidth()
        screen_height = self.splash.winfo_screenheight()
        
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self.splash.geometry(f"{width}x{height}+{x}+{y}")
    
    def close(self):
        """Close splash screen"""
        try:
            self.splash.destroy()
        except:
            pass
    
    def show(self):
        """Show splash screen (already shown on init)"""
        try:
            self.splash.update_idletasks()
            self.splash.update()
            self.splash.lift()
            self.splash.focus_force()
            # Also update root if available
            if self.root:
                self.root.update_idletasks()
                self.root.update()
        except:
            pass


def show_splash_screen(duration=2000, root=None):
    """
    Convenience function to show splash screen
    
    Args:
        duration: How long to show in milliseconds (0 = until manually closed)
        root: Optional parent window
    
    Returns:
        SplashScreen instance
    """
    try:
        splash = SplashScreen(root=root, duration=duration)
        splash.show()
        return splash
    except Exception as e:
        print(f"Error creating splash screen: {e}")
        import traceback
        traceback.print_exc()
        return None

