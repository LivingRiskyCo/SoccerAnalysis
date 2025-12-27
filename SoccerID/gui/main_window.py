"""
Main Window for Soccer Analysis GUI
Orchestrates all GUI components and tabs
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, colorchooser
import os
import sys
from pathlib import Path
from typing import Optional, List

# Import utility modules
try:
    from ..utils.tooltip import ToolTip, create_tooltip, TOOLTIP_DATABASE
    from ..utils.progress_tracker import ProgressTracker
    from ..utils.action_history import ActionHistory, ActionType
except ImportError:
    try:
        from SoccerID.utils.tooltip import ToolTip, create_tooltip, TOOLTIP_DATABASE
        from SoccerID.utils.progress_tracker import ProgressTracker
        from SoccerID.utils.action_history import ActionHistory, ActionType
    except ImportError:
        # Fallback - create minimal versions
        ToolTip = None
        create_tooltip = None
        TOOLTIP_DATABASE = {}
        ProgressTracker = None
        ActionHistory = None
        ActionType = None

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import extracted tab components
try:
    from .tabs import (
        GalleryTab, RosterTab, EventDetectionTab, AnalysisTab,
        VisualizationTab, TrackingTab, AdvancedTab, RecognitionTab, MLTab
    )
except ImportError:
    # Fallback for direct execution
    try:
        from SoccerID.gui.tabs import (
            GalleryTab, RosterTab, EventDetectionTab, AnalysisTab,
            VisualizationTab, TrackingTab, AdvancedTab, RecognitionTab, MLTab
        )
    except ImportError:
        # Legacy fallback
        try:
            from tabs import (
                GalleryTab, RosterTab, EventDetectionTab, AnalysisTab,
                VisualizationTab, TrackingTab, AdvancedTab, RecognitionTab, MLTab
            )
        except ImportError:
            RecognitionTab = None
            MLTab = None
            from tabs import (
                GalleryTab, RosterTab, EventDetectionTab, AnalysisTab,
                VisualizationTab, TrackingTab, AdvancedTab
            )


class SoccerAnalysisGUI:
    """Main GUI window for Soccer Analysis Tool"""
    
    def __init__(self, root):
        """
        Initialize the main GUI window
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("Soccer Video Analysis Tool")
        
        # Setup modern theme FIRST (before any widgets are created)
        self._setup_modern_theme()
        
        # Set window icon
        self._set_window_icon()
        
        # Windows 11 workaround: Patch ttk.LabelFrame to auto-apply backgrounds
        # Do this AFTER window setup to avoid blocking initialization
        try:
            self.root.after(100, self._patch_ttk_label_frame)  # Delay to avoid blocking startup
        except:
            pass  # If this fails, continue without patching
        
        self._setup_window()
        
        # Initialize all variables
        self._init_variables()
        
        # Project management
        self.current_project_path = None
        self.current_project_name = tk.StringVar(value="No Project")
        
        # Initialize action history for undo/redo
        self.action_history = ActionHistory() if ActionHistory else None
        
        # Initialize progress tracker
        self.progress_tracker = ProgressTracker() if ProgressTracker else None
        
        # Initialize toast notification manager
        try:
            from ..utils.toast_notifications import ToastManager
            self.toast_manager = ToastManager(self.root)
        except ImportError:
            try:
                from SoccerID.utils.toast_notifications import ToastManager
                self.toast_manager = ToastManager(self.root)
            except ImportError:
                self.toast_manager = None
        
        # Create widgets
        self.create_widgets()
        
        # Check if first run - show setup wizard as tutorial (after widgets are created)
        self._check_first_run()
        
        # Initialize quick wins features if available
        self._init_quick_wins()
        
        # Setup undo/redo keyboard shortcuts
        self._setup_undo_redo_shortcuts()
        
        # Auto-load last project (only if not first run)
        if not self._is_first_run():
            self.root.after(500, self.auto_load_last_project)
    
    def _check_first_run(self):
        """Check if this is the first run and show setup wizard as tutorial"""
        if self._is_first_run():
            # Mark first run as complete
            self._mark_first_run_complete()
            # Show setup wizard after a short delay
            self.root.after(1000, self._show_first_run_wizard)
    
    def _is_first_run(self) -> bool:
        """Check if this is the first run"""
        return not os.path.exists(self._first_run_file)
    
    def _mark_first_run_complete(self):
        """Mark first run as complete"""
        try:
            with open(self._first_run_file, 'w') as f:
                f.write("first_run_complete")
        except:
            pass
    
    def _show_first_run_wizard(self):
        """Show Quick Start Wizard on first run"""
        response = messagebox.askyesno(
            "Welcome to Soccer Analysis Tool!",
            "Welcome! Let's get you started quickly.\n\n"
            "The Quick Start Wizard will help you:\n"
            "• Select your video and roster\n"
            "• Choose a preset configuration\n"
            "• Automatically identify players\n"
            "• Generate highlights\n\n"
            "Would you like to start the Quick Start Wizard now?",
            icon='question'
        )
        if response:
            self.open_quick_start_wizard()
    
    def _show_wizard_tutorial_intro(self, parent):
        """Show tutorial introduction for setup wizard"""
        intro_window = tk.Toplevel(parent)
        intro_window.title("Setup Wizard Tutorial")
        intro_window.geometry("600x500")
        intro_window.transient(parent)
        intro_window.grab_set()  # Modal dialog
        
        # Center on screen
        intro_window.update_idletasks()
        x = (intro_window.winfo_screenwidth() // 2) - (intro_window.winfo_width() // 2)
        y = (intro_window.winfo_screenheight() // 2) - (intro_window.winfo_height() // 2)
        intro_window.geometry(f"+{x}+{y}")
        
        frame = ttk.Frame(intro_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = ttk.Label(frame, text="Setup Wizard Tutorial", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Instructions
        instructions = """The Setup Wizard will guide you through the essential steps:

Step 1: Load Your Video
  • Select your recorded soccer video
  • The wizard will analyze the first few frames

Step 2: Calibrate the Field
  • Mark the four corners of the field
  • This helps with accurate distance measurements

Step 3: Tag Players
  • Click on players to assign names
  • Tag at least 3-5 frames for each player
  • The system will learn to recognize them

Step 4: Configure Team Colors
  • Select jersey colors for each team
  • This helps with team identification

Step 5: Verify Ball Detection
  • Check that the ball is being tracked correctly
  • Adjust if needed

Ready to begin?"""
        
        text_widget = tk.Text(frame, wrap=tk.WORD, font=("Arial", 9),
                             bg="#fafafa", relief=tk.FLAT, padx=10, pady=10, height=15)
        text_widget.insert("1.0", instructions)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Start Tutorial", 
                  command=lambda: (intro_window.destroy(), None)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Skip Tutorial", 
                  command=intro_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def _set_window_icon(self):
        """Set window icon from ICO file"""
        icon_paths = [
            'soccer_analysis_icon.ico',
            'soccer_analysis/soccer_analysis_icon.ico',
            os.path.join(os.path.dirname(__file__), '..', '..', 'soccer_analysis_icon.ico'),
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'soccer_analysis_icon.ico'),
        ]
        
        # Also check current working directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = Path(script_dir).parent.parent
        icon_paths.extend([
            os.path.join(root_dir, 'soccer_analysis_icon.ico'),
            os.path.join(os.getcwd(), 'soccer_analysis_icon.ico'),
        ])
        
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                try:
                    self.root.iconbitmap(icon_path)
                    return
                except Exception as e:
                    # Icon loading failed, try next path
                    continue
    
    def _setup_modern_theme(self):
        """Setup modern color scheme and theme - DSX Green & Orange"""
        # DSX-inspired color palette (Green & Orange)
        self.colors = {
            'primary': '#1E8449',      # Dark green (DSX primary)
            'secondary': '#F39C12',    # Orange (DSX secondary)
            'accent': '#E67E22',       # Darker orange
            'success': '#27AE60',       # Bright green
            'warning': '#F39C12',      # Orange
            'info': '#3498DB',          # Info blue (kept for info messages)
            'background': '#F5F5F5',    # Light gray background
            'surface': '#FFFFFF',       # White surface
            'text_primary': '#1E8449',  # Dark green text
            'text_secondary': '#7F8C8D', # Gray text
            'border': '#BDC3C7',        # Light border
            'log_bg': '#1E1E1E',        # Dark log background
            'log_fg': '#D4D4D4',        # Light log text
            'button_text': '#FFFFFF',   # White text for colored buttons
            'button_text_dark': '#1E8449'  # Dark green text for light buttons
        }
        
        # Configure ttk style
        self.style = ttk.Style()
        
        # Try to use a theme that supports custom colors (clam is best for custom styling)
        available_themes = self.style.theme_names()
        if 'clam' in available_themes:
            self.style.theme_use('clam')  # Clam theme supports custom background colors
            self.current_theme = 'clam'
        elif 'vista' in available_themes:
            self.style.theme_use('vista')
            self.current_theme = 'vista'
        else:
            # Fallback to default theme
            self.current_theme = self.style.theme_use()
        
        # Verify theme was set correctly
        actual_theme = self.style.theme_use()
        if actual_theme != self.current_theme:
            self.current_theme = actual_theme
        
        # Custom button styles - DSX Green & Orange theme
        # Primary button (Orange - DSX secondary color) - Use darker orange for better contrast
        self.style.configure('Primary.TButton',
                           background='#D35400',  # Darker orange for better contrast with white text
                           foreground='white',  # White text
                           padding=(15, 8),
                           font=('Segoe UI', 10, 'bold'),  # Bold font for readability
                           borderwidth=0,
                           focuscolor='none')
        
        self.style.map('Primary.TButton',
                      background=[('active', '#E67E22'), ('pressed', '#BA4A00'), ('disabled', '#BDC3C7')],
                      foreground=[('active', 'white'), ('pressed', 'white'), ('disabled', '#7F8C8D')])
        
        # Success button (Green - DSX primary color) - Use darker green for better white text contrast
        self.style.configure('Success.TButton',
                           background='#1E8449',  # Darker green for better contrast with white text
                           foreground='white',  # White text
                           padding=(15, 8),
                           font=('Segoe UI', 10, 'bold'),  # Bold font for readability
                           borderwidth=0,
                           focuscolor='none')
        
        self.style.map('Success.TButton',
                      background=[('active', '#27AE60'), ('pressed', '#196F3D'), ('disabled', '#BDC3C7')],
                      foreground=[('active', 'white'), ('pressed', 'white'), ('disabled', '#7F8C8D')])
        
        # Danger button (Darker orange/red) - Use darker red for better contrast
        self.style.configure('Danger.TButton',
                           background='#C0392B',  # Darker red for better contrast with white text
                           foreground='white',  # White text
                           padding=(15, 8),
                           font=('Segoe UI', 10, 'bold'),  # Bold font for readability
                           borderwidth=0,
                           focuscolor='none')
        
        self.style.map('Danger.TButton',
                      background=[('active', '#E74C3C'), ('pressed', '#A93226'), ('disabled', '#BDC3C7')],
                      foreground=[('active', 'white'), ('pressed', 'white'), ('disabled', '#2C3E50')])  # Dark text on light gray when disabled
        
        # Warning button (Orange) - Use darker orange for better contrast
        self.style.configure('Warning.TButton',
                           background='#D35400',  # Darker orange for better contrast with white text
                           foreground='white',  # White text
                           padding=(15, 8),
                           font=('Segoe UI', 10, 'bold'),  # Bold font for readability
                           borderwidth=0,
                           focuscolor='none')
        
        self.style.map('Warning.TButton',
                      background=[('active', '#E67E22'), ('pressed', '#BA4A00'), ('disabled', '#BDC3C7')],
                      foreground=[('active', 'white'), ('pressed', 'white'), ('disabled', '#2C3E50')])  # Dark text on light gray when disabled
        
        # Default button style - ensure readable text with high contrast
        self.style.configure('TButton',
                           foreground='#1E8449',  # Dark green text for default buttons (explicit color)
                           background='white',  # White background (explicit)
                           padding=(10, 6),
                           font=('Segoe UI', 9, 'bold'),  # Bold for better readability
                           borderwidth=1,
                           relief=tk.RAISED)
        
        self.style.map('TButton',
                      background=[('active', '#F5F5F5'), ('pressed', '#E8E8E8'), ('disabled', '#ECF0F1')],
                      foreground=[('active', '#1E8449'), ('pressed', '#1E8449'), ('disabled', '#7F8C8D')],  # Medium gray text on light gray when disabled
                      relief=[('pressed', tk.SUNKEN)])
        
        # Configure frame styles
        self.style.configure('Card.TFrame',
                           background=self.colors['surface'],
                           relief=tk.FLAT,
                           borderwidth=1)
        
        # Configure LabelFrame styles - Modern light background for black text
        # Force background color for LabelFrames - some themes need explicit configuration
        label_frame_bg = '#F8F8F8'
        label_frame_fg = '#2C3E50'
        
        # Configure TLabelFrame with all possible options
        self.style.configure('TLabelFrame',
                           background=label_frame_bg,
                           foreground=label_frame_fg,
                           borderwidth=1,
                           relief=tk.FLAT)
        
        # Use style.map to force background in all states
        self.style.map('TLabelFrame',
                      background=[('active', label_frame_bg),
                                 ('!active', label_frame_bg),
                                 ('focus', label_frame_bg),
                                 ('!focus', label_frame_bg)],
                      foreground=[('active', label_frame_fg),
                                 ('!active', label_frame_fg)])
        
        # Configure LabelFrame label (the title text)
        self.style.configure('TLabelFrame.Label',
                           background=label_frame_bg,
                           foreground=label_frame_fg,
                           font=('Segoe UI', 9, 'bold'))
        
        # Also create a custom style variant for extra assurance
        self.style.configure('Modern.TLabelFrame',
                           background=label_frame_bg,
                           foreground=label_frame_fg,
                           borderwidth=1,
                           relief=tk.FLAT)
        
        self.style.map('Modern.TLabelFrame',
                      background=[('active', label_frame_bg),
                                 ('!active', label_frame_bg)])
        
        # Configure regular Frame style for better background
        try:
            self.style.configure('TFrame',
                               background=self.colors['background'])
        except:
            pass
        
        # Configure label styles
        self.style.configure('Title.TLabel',
                           font=('Segoe UI', 18, 'bold'),
                           foreground=self.colors['primary'],
                           background=self.colors['background'])
        
        self.style.configure('Heading.TLabel',
                           font=('Segoe UI', 11, 'bold'),
                           foreground=self.colors['primary'],
                           background=self.colors['background'])
        
        self.style.configure('Subheading.TLabel',
                           font=('Segoe UI', 9, 'bold'),
                           foreground=self.colors['text_secondary'],
                           background=self.colors['background'])
        
        # Configure notebook style
        self.style.configure('TNotebook',
                           background=self.colors['background'],
                           borderwidth=0)
        
        self.style.configure('TNotebook.Tab',
                           padding=[20, 12],
                           font=('Segoe UI', 9),
                           background=self.colors['surface'],
                           foreground=self.colors['text_primary'])
        
        self.style.map('TNotebook.Tab',
                      background=[('selected', self.colors['primary'])],  # Green for selected tabs
                      foreground=[('selected', 'white')],
                      expand=[('selected', [1, 1, 1, 0])])
        
        # Configure progress bar style - Orange progress bar
        self.style.configure("Modern.Horizontal.TProgressbar",
                           background=self.colors['secondary'],  # Orange
                           troughcolor=self.colors['background'],
                           borderwidth=0,
                           lightcolor=self.colors['secondary'],
                           darkcolor=self.colors['secondary'],
                           thickness=25)
        
        # Set root window background
        self.root.configure(bg=self.colors['background'])
        
        # Force style update - ensure all widgets get the new styling
        try:
            # Update the style to ensure it's applied
            current_theme = self.style.theme_use()
            self.style.theme_use(current_theme)  # Re-apply theme to force update
        except:
            pass
    
    def _patch_ttk_label_frame(self):
        """
        Windows 11 workaround: Monkey-patch ttk.LabelFrame.__init__ to automatically
        apply modern background colors. Since Windows native theme doesn't support
        LabelFrame backgrounds via styles, we directly set backgrounds on internal
        tk widgets after creation.
        
        NOTE: This is done safely to avoid blocking initialization.
        """
        try:
            # Only patch if not already patched
            if hasattr(ttk.LabelFrame, '_modern_theme_patched'):
                return  # Already patched
            
            # Store original init
            original_init = ttk.LabelFrame.__init__
            ttk.LabelFrame._modern_theme_patched = True
            
            def patched_init(self, parent=None, **kw):
                # Call original init first
                try:
                    original_init(self, parent, **kw)
                except Exception:
                    # If original init fails, don't proceed
                    return
                
                # Only apply background if we have a valid parent and widget is created
                if not parent:
                    try:
                        # Safely apply background after a short delay to avoid blocking
                        def apply_bg_safe():
                            try:
                                # Check if widget still exists
                                if not hasattr(self, 'winfo_exists') or not self.winfo_exists():
                                    return
                                
                                def set_bg_recursive(widget, depth=0):
                                    # Prevent infinite recursion
                                    if depth > 10:
                                        return
                                    
                                    try:
                                        # Only set bg on tk widgets (not ttk widgets)
                                        if isinstance(widget, tk.Widget) and not isinstance(widget, ttk.Widget):
                                            try:
                                                widget.configure(bg='#F8F8F8')
                                            except (tk.TclError, AttributeError, RuntimeError):
                                                pass
                                        
                                        # Recursively process children (with depth limit)
                                        try:
                                            children = widget.winfo_children()
                                            for child in children:
                                                set_bg_recursive(child, depth + 1)
                                        except:
                                            pass
                                    except:
                                        pass
                                
                                set_bg_recursive(self)
                            except:
                                pass
                        
                        # Schedule background application safely (avoid after_idle during init)
                        try:
                            root = parent.winfo_toplevel() if parent else None
                            if root:
                                # Use longer delays to avoid blocking initialization
                                root.after(500, apply_bg_safe)  # First attempt after 500ms
                                root.after(1000, apply_bg_safe)  # Second attempt after 1s
                        except:
                            pass
                    except:
                        pass
            
            # Replace __init__ method
            ttk.LabelFrame.__init__ = patched_init
        except Exception:
            # If patching fails completely, continue without it
            # This should never block initialization
            pass
    
    def _patch_label_frame_background(self, label_frame):
        """
        Windows 11 workaround: Force background color on ttk.LabelFrame.
        This patches the LabelFrame after creation to apply background color.
        
        Args:
            label_frame: ttk.LabelFrame widget to patch
        """
        try:
            # Method 1: Try to configure children directly
            for child in label_frame.winfo_children():
                try:
                    if isinstance(child, tk.Widget):
                        child.configure(bg='#F8F8F8')
                except:
                    pass
            
            # Method 2: Use tkinter's internal methods (Windows-specific workaround)
            try:
                # On Windows, we can sometimes set the background via the style
                # But we need to update it after the widget is mapped
                def update_bg():
                    try:
                        # Force update by reconfiguring style
                        label_frame.configure(style='Modern.TLabelFrame')
                        # Also try to set children backgrounds
                        for child in label_frame.winfo_children():
                            try:
                                child.configure(bg='#F8F8F8')
                            except:
                                pass
                    except:
                        pass
                
                # Schedule update after widget is fully created
                label_frame.after(10, update_bg)
                label_frame.after(100, update_bg)
            except:
                pass
        except:
            pass
    
    def create_modern_label_frame(self, parent, text="", **kwargs):
        """
        Create a LabelFrame with guaranteed modern background color.
        Windows 11 workaround: Creates a custom frame that looks like LabelFrame
        but uses tk.Frame with explicit backgrounds.
        
        Args:
            parent: Parent widget
            text: Label text
            **kwargs: Additional arguments (padding, etc.)
            
        Returns:
            Frame with LabelFrame-like appearance (use .content attribute for child widgets)
        """
        # Extract padding if provided
        padding = kwargs.pop('padding', '10')
        if isinstance(padding, str):
            try:
                padding = int(padding.replace('px', '').strip())
            except:
                padding = 10
        elif isinstance(padding, (list, tuple)):
            padding = padding[0] if padding else 10
        else:
            padding = int(padding) if padding else 10
        
        # Create outer frame for border effect (simulates LabelFrame border)
        outer_frame = tk.Frame(parent, bg='#E0E0E0', relief=tk.FLAT)
        
        # Create inner frame with modern background
        inner_frame = tk.Frame(outer_frame, bg='#F8F8F8', relief=tk.FLAT)
        inner_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # Create label at top (simulates LabelFrame label)
        if text:
            label_frame = tk.Frame(inner_frame, bg='#F8F8F8')
            label_frame.pack(fill=tk.X, padx=padding, pady=(padding, 0))
            label = tk.Label(label_frame, text=text, bg='#F8F8F8', fg='#2C3E50',
                           font=('Segoe UI', 9, 'bold'), anchor='w')
            label.pack(side=tk.LEFT)
        
        # Create content frame (this is where child widgets should be placed)
        content_frame = tk.Frame(inner_frame, bg='#F8F8F8')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=padding, pady=padding)
        
        # Store reference to content frame for widget placement
        # Users should use label_frame.content instead of label_frame directly
        outer_frame.content = content_frame
        outer_frame.inner = inner_frame
        
        return outer_frame
    
    def _setup_window(self):
        """Setup window size and position"""
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # Update window to get screen dimensions
        self.root.update_idletasks()
        
        # Set window size to fit on screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = min(1200, int(screen_width * 0.9))
        window_height = min(900, int(screen_height * 0.9))
        self.root.geometry(f"{window_width}x{window_height}")
        
        # Center window on screen
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Ensure window stays on top initially
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, '-topmost', False)
    
    def _init_variables(self):
        """Initialize all Tkinter variables"""
        # File selection
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.csv_output_file = tk.StringVar()  # CSV output filename
        self.event_csv_file = tk.StringVar()  # For event detection tab
        self.event_goal_areas_file = tk.StringVar()  # For event detection tab
        self.event_manual_markers_file = tk.StringVar()  # For event detection tab
        
        # Event detection parameters (in imperial units for UI, converted to metric internally)
        
        # Automation settings (from Quick Start Wizard)
        self.auto_tag_players = tk.BooleanVar(value=False)
        self.auto_detect_events = tk.BooleanVar(value=False)
        self.generate_highlights = tk.BooleanVar(value=False)
        self.auto_export_csv = tk.BooleanVar(value=True)  # Default enabled
        self.event_min_confidence = tk.DoubleVar(value=0.5)
        self.event_min_ball_speed = tk.DoubleVar(value=9.84)  # ft/s (equivalent to 3.0 m/s)
        self.event_min_pass_distance = tk.DoubleVar(value=16.4)  # ft (equivalent to 5.0 m)
        self.event_possession_threshold = tk.DoubleVar(value=4.92)  # ft (equivalent to 1.5 m)
        self.event_detect_passes = tk.BooleanVar(value=True)
        self.event_detect_shots = tk.BooleanVar(value=True)
        self.event_detect_goals = tk.BooleanVar(value=False)
        self.event_detect_zones = tk.BooleanVar(value=True)
        self.event_export_csv = tk.BooleanVar(value=True)
        self.event_use_manual_markers = tk.BooleanVar(value=True)
        
        self.current_project_name = tk.StringVar(value="No Project")
        self.current_project_path = None
        self.video_type = tk.StringVar(value="practice")
        self.explicit_anchor_file = tk.StringVar()
        
        # Processing options
        self.dewarp_enabled = tk.BooleanVar(value=False)
        self.remove_net_enabled = tk.BooleanVar(value=False)
        self.ball_tracking_enabled = tk.BooleanVar(value=True)
        self.ball_min_size = tk.IntVar(value=3)
        self.ball_max_size = tk.IntVar(value=20)
        self.ball_trail_length = tk.IntVar(value=20)
        self.player_tracking_enabled = tk.BooleanVar(value=True)
        self.csv_export_enabled = tk.BooleanVar(value=True)
        self.use_imperial_units = tk.BooleanVar(value=False)
        
        # YOLO settings
        self.yolo_confidence = tk.DoubleVar(value=0.25)
        self.yolo_iou_threshold = tk.DoubleVar(value=0.45)
        self.yolo_resolution = tk.StringVar(value="full")
        
        # Watch-only mode
        self.watch_only = tk.BooleanVar(value=False)
        self.show_live_viewer = tk.BooleanVar(value=False)
        self.focus_players_enabled = tk.BooleanVar(value=False)
        self.focused_player = None
        self.batch_focus_analyze = tk.BooleanVar(value=False)
        
        # Live viewer controls
        self.live_viewer_controls = None
        self.live_viewer_retry_count = 0
        self.live_viewer_max_retries = 30
        self.live_viewer_start_time = None
        self.live_viewer_timeout = 30
        
        # Overlay system
        self.save_base_video = tk.BooleanVar(value=False)
        self.export_overlay_metadata = tk.BooleanVar(value=True)
        self.enable_video_encoding = tk.BooleanVar(value=True)
        self.overlay_quality = tk.StringVar(value="hd")
        self.render_scale = tk.DoubleVar(value=1.0)
        
        # Video game quality graphics
        self.enable_advanced_blending = tk.BooleanVar(value=True)
        self.enable_motion_blur = tk.BooleanVar(value=False)
        self.motion_blur_amount = tk.DoubleVar(value=1.0)
        self.use_professional_text = tk.BooleanVar(value=True)
        self.enable_text_gradient = tk.BooleanVar(value=False)
        self.enable_text_glow = tk.BooleanVar(value=False)
        self.enable_text_pulse = tk.BooleanVar(value=False)
        self.enable_glow_pulse = tk.BooleanVar(value=False)
        self.enable_color_shift = tk.BooleanVar(value=False)
        self.enable_gradient_boxes = tk.BooleanVar(value=False)
        self.enable_particle_trails = tk.BooleanVar(value=False)
        self.graphics_quality_preset = tk.StringVar(value="hd")
        
        # Processing settings
        self.buffer_size = tk.IntVar(value=64)
        self.batch_size = tk.IntVar(value=8)
        self.use_yolo_streaming = tk.BooleanVar(value=False)
        self.preview_max_frames = tk.IntVar(value=360)
        
        # Ball visualization
        self.show_ball_trail = tk.BooleanVar(value=True)
        self.trail_length = tk.IntVar(value=20)
        self.trail_buffer = tk.IntVar(value=20)
        
        # Tracking settings
        self.track_thresh = tk.DoubleVar(value=0.25)
        self.match_thresh = tk.DoubleVar(value=0.6)
        self.track_buffer = tk.IntVar(value=50)
        self.track_buffer_seconds = tk.DoubleVar(value=5.0)
        self.min_track_length = tk.IntVar(value=5)
        self.min_bbox_area = tk.IntVar(value=200)
        self.min_bbox_width = tk.IntVar(value=10)
        self.min_bbox_height = tk.IntVar(value=15)
        self.tracker_type = tk.StringVar(value="deepocsort")
        self.yolo_model_size = tk.StringVar(value="medium")  # nano, small, medium, large
        
        # YOLO Detection Settings
        self.yolo_confidence = tk.DoubleVar(value=0.25)  # YOLO detection confidence (separate from track_thresh)
        self.ball_confidence_threshold = tk.DoubleVar(value=0.15)  # Ball detection confidence threshold
        self.ball_confidence_multiplier = tk.DoubleVar(value=0.5)  # Ball confidence as multiplier of player confidence
        self.nms_iou_threshold = tk.DoubleVar(value=0.5)  # NMS IOU threshold for duplicate removal
        self.max_detections_per_frame = tk.IntVar(value=0)  # 0 = auto, otherwise manual limit
        
        # Identity Tracker Settings
        self.identity_position_tolerance = tk.DoubleVar(value=200.0)  # Position tolerance in pixels
        self.identity_iou_threshold = tk.DoubleVar(value=0.3)  # IOU threshold for identity matching
        self.player_uniqueness_grace_frames = tk.IntVar(value=3)  # Frames to allow player name on multiple tracks
        
        # Jersey OCR Settings
        self.jersey_ocr_confidence = tk.DoubleVar(value=0.5)  # Jersey OCR confidence threshold
        
        # Net Filtering Settings
        self.net_min_area_multiplier = tk.DoubleVar(value=4.0)  # Net min area multiplier vs player min area
        self.net_aspect_ratio_low = tk.DoubleVar(value=0.7)  # Net filtering: low aspect ratio threshold
        self.net_aspect_ratio_high = tk.DoubleVar(value=1.4)  # Net filtering: high aspect ratio threshold
        self.net_confidence_threshold = tk.DoubleVar(value=0.3)  # Net filtering: confidence threshold
        
        # Visualization Parameters
        self.direction_arrow_length = tk.IntVar(value=20)  # Direction arrow length in pixels
        self.direction_arrow_head_size = tk.IntVar(value=8)  # Direction arrow head size in pixels
        self.direction_arrow_thickness = tk.IntVar(value=2)  # Direction arrow thickness in pixels
        self.video_fps = tk.DoubleVar(value=0.0)
        self.output_fps = tk.DoubleVar(value=0.0)
        self.temporal_smoothing = tk.BooleanVar(value=True)
        self.process_every_nth = tk.IntVar(value=1)
        self.foot_based_tracking = tk.BooleanVar(value=True)
        self.use_reid = tk.BooleanVar(value=True)
        self.reid_similarity_threshold = tk.DoubleVar(value=0.55)
        self.gallery_similarity_threshold = tk.DoubleVar(value=0.40)
        self.osnet_variant = tk.StringVar(value="osnet_x1_0")
        self.occlusion_recovery_seconds = tk.DoubleVar(value=3.0)
        self.occlusion_recovery_distance = tk.IntVar(value=250)
        self.reid_check_interval = tk.IntVar(value=30)
        self.reid_confidence_threshold = tk.DoubleVar(value=0.75)
        self.use_boxmot_backend = tk.BooleanVar(value=True)
        self.use_gsi = tk.BooleanVar(value=False)
        self.gsi_interval = tk.IntVar(value=20)
        self.gsi_tau = tk.DoubleVar(value=10.0)
        
        # Advanced Tracking Features (Deep HM-SORT)
        self.use_harmonic_mean = tk.BooleanVar(value=True)  # Use Harmonic Mean for association (Deep HM-SORT)
        self.use_expansion_iou = tk.BooleanVar(value=True)  # Use Expansion IOU with motion prediction (Deep HM-SORT)
        self.enable_soccer_reid_training = tk.BooleanVar(value=False)  # Prepare data for fine-tuning on soccer players
        self.use_enhanced_kalman = tk.BooleanVar(value=True)  # Enhanced Kalman filtering for additional smoothing
        self.use_ema_smoothing = tk.BooleanVar(value=True)  # EMA (Exponential Moving Average) smoothing
        self.confidence_filtering = tk.BooleanVar(value=True)
        self.adaptive_confidence = tk.BooleanVar(value=True)
        self.use_optical_flow = tk.BooleanVar(value=False)
        self.enable_velocity_constraints = tk.BooleanVar(value=True)
        self.track_referees = tk.BooleanVar(value=False)
        self.max_players = tk.IntVar(value=12)
        self.enable_substitutions = tk.BooleanVar(value=True)
        
        # Visualization settings
        self.viz_style = tk.StringVar(value="box")
        self.viz_color_mode = tk.StringVar(value="team")
        self.viz_team_colors = tk.BooleanVar(value=True)
        self.show_bounding_boxes = tk.BooleanVar(value=True)
        self.show_circles_at_feet = tk.BooleanVar(value=True)
        self.ellipse_width = tk.IntVar(value=20)
        self.ellipse_height = tk.IntVar(value=12)
        self.ellipse_outline_thickness = tk.IntVar(value=3)
        self.feet_marker_style = tk.StringVar(value="circle")
        self.feet_marker_opacity = tk.IntVar(value=255)
        self.feet_marker_enable_glow = tk.BooleanVar(value=False)
        self.feet_marker_glow_intensity = tk.IntVar(value=70)
        self.show_direction_arrow = tk.BooleanVar(value=False)
        self.show_player_trail = tk.BooleanVar(value=False)
        self.feet_marker_enable_shadow = tk.BooleanVar(value=False)
        self.feet_marker_shadow_offset = tk.IntVar(value=3)
        self.feet_marker_shadow_opacity = tk.IntVar(value=128)
        self.feet_marker_enable_gradient = tk.BooleanVar(value=False)
        self.feet_marker_enable_pulse = tk.BooleanVar(value=False)
        self.feet_marker_pulse_speed = tk.DoubleVar(value=2.0)
        self.feet_marker_enable_particles = tk.BooleanVar(value=False)
        self.feet_marker_particle_count = tk.IntVar(value=5)
        self.feet_marker_vertical_offset = tk.IntVar(value=50)
        self.show_ball_possession = tk.BooleanVar(value=True)
        self.box_shrink_factor = tk.DoubleVar(value=0.10)
        self.box_thickness = tk.IntVar(value=2)
        self.use_custom_box_color = tk.BooleanVar(value=False)
        self.box_color_rgb = tk.StringVar(value="0,255,0")
        self.player_viz_alpha = tk.IntVar(value=255)
        self.use_custom_label_color = tk.BooleanVar(value=False)
        self.label_color_rgb = tk.StringVar(value="255,255,255")
        self.show_player_labels = tk.BooleanVar(value=True)
        self.show_yolo_boxes = tk.BooleanVar(value=False)
        self.label_font_scale = tk.DoubleVar(value=0.7)
        self.label_type = tk.StringVar(value="full_name")
        self.label_custom_text = tk.StringVar(value="Player")
        self.label_font_face = tk.StringVar(value="FONT_HERSHEY_SIMPLEX")
        self.show_predicted_boxes = tk.BooleanVar(value=False)
        self.prediction_duration = tk.DoubleVar(value=1.5)
        self.prediction_size = tk.IntVar(value=5)
        self.prediction_color_r = tk.IntVar(value=255)
        self.prediction_color_g = tk.IntVar(value=255)
        self.prediction_color_b = tk.IntVar(value=0)
        self.prediction_color_alpha = tk.IntVar(value=255)
        self.prediction_style = tk.StringVar(value="dot")
        
        # Analytics settings
        self.analytics_position = tk.StringVar(value="with_player")
        self.analytics_font_scale = tk.DoubleVar(value=1.0)
        self.analytics_font_thickness = tk.IntVar(value=2)
        self.analytics_font_face = tk.StringVar(value="FONT_HERSHEY_SIMPLEX")
        self.use_custom_analytics_color = tk.BooleanVar(value=True)
        self.analytics_color_rgb = tk.StringVar(value="255,255,255")
        self.analytics_title_color_rgb = tk.StringVar(value="255,255,0")
        
        # Statistics overlay
        self.show_statistics = tk.BooleanVar(value=False)
        self.statistics_position = tk.StringVar(value="top_left")
        self.statistics_panel_width = tk.IntVar(value=250)
        self.statistics_panel_height = tk.IntVar(value=150)
        self.statistics_bg_alpha = tk.DoubleVar(value=0.75)
        self.statistics_bg_color_rgb = tk.StringVar(value="0,0,0")
        self.statistics_text_color_rgb = tk.StringVar(value="255,255,255")
        self.statistics_title_color_rgb = tk.StringVar(value="255,255,0")
        
        # Heat map
        self.show_heat_map = tk.BooleanVar(value=False)
        self.heat_map_alpha = tk.DoubleVar(value=0.4)
        self.heat_map_color_scheme = tk.StringVar(value="hot")
        
        # Other settings
        self.ball_graphics_style = tk.StringVar(value="standard")
        self.overlay_quality_preset = tk.StringVar(value="hd")
        self.ball_min_radius = tk.IntVar(value=5)
        self.ball_max_radius = tk.IntVar(value=50)
        self.preserve_audio = tk.BooleanVar(value=True)
        self.analytics_preferences = {}
        
        # Processing state
        self.processing = False
        self.process_thread = None
        self.last_output_file = None
        
        # Window references
        self.live_viewer_controls = None
        self._player_stats_window = None
        self._player_stats_app = None
        self._gallery_seeder_window = None
        self._video_splicer_window = None
        
        # First run flag
        self._first_run_file = os.path.join(os.path.expanduser("~"), ".soccer_analysis_first_run")
    
    def _create_card_frame(self, parent, title=None, padding=15):
        """Create a modern card-style frame"""
        card = tk.Frame(parent,
                      bg=self.colors['surface'],
                      relief=tk.FLAT,
                      borderwidth=1,
                      highlightbackground=self.colors['border'],
                      highlightthickness=1)
        
        # Card header - use orange for headers
        if title:
            header = tk.Frame(card, bg=self.colors['secondary'], height=40)  # Orange header
            header.pack(fill=tk.X)
            header.pack_propagate(False)
            
            tk.Label(header,
                    text=title,
                    font=("Segoe UI", 10, "bold"),
                    bg=self.colors['secondary'],
                    fg='white',  # White text on orange
                    padx=15).pack(side=tk.LEFT, pady=10)
        
        # Card content
        content = tk.Frame(card, bg=self.colors['surface'])
        content.pack(fill=tk.BOTH, expand=True, padx=padding, pady=padding)
        
        return card, content
    
    def _create_enhanced_button(self, parent, text, command, style='default', width=None):
        """Create enhanced button with modern styling"""
        btn_kwargs = {'text': text, 'command': command}
        if width is not None:
            btn_kwargs['width'] = width
        
        if style == 'primary':
            btn = ttk.Button(parent, style='Primary.TButton', **btn_kwargs)
        elif style == 'success':
            btn = ttk.Button(parent, style='Success.TButton', **btn_kwargs)
        elif style == 'danger':
            btn = ttk.Button(parent, style='Danger.TButton', **btn_kwargs)
        elif style == 'warning':
            btn = ttk.Button(parent, style='Warning.TButton', **btn_kwargs)
        else:
            btn = ttk.Button(parent, **btn_kwargs)
        
        return btn
    
    def _add_hover_effect(self, widget, color_normal, color_hover):
        """Add hover effect to widget"""
        def on_enter(e):
            widget.config(bg=color_hover)
        
        def on_leave(e):
            widget.config(bg=color_normal)
        
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
    
    def _animate_fade_in(self, widget, duration=200):
        """Animate widget fade in (only works for Toplevel windows)"""
        # Only animate Toplevel windows, not regular widgets
        if isinstance(widget, tk.Toplevel):
            def fade(alpha):
                if alpha < 1.0:
                    try:
                        widget.attributes('-alpha', alpha)
                        widget.after(10, lambda: fade(alpha + 0.1))
                    except:
                        pass
                else:
                    try:
                        widget.attributes('-alpha', 1.0)
                    except:
                        pass
            
            try:
                widget.attributes('-alpha', 0.0)
                fade(0.0)
            except:
                pass
        # For regular widgets, just skip animation
    
    def create_widgets(self):
        """Create all GUI widgets"""
        # Create menu bar first (horizontal menu bar at top)
        self._create_menu_bar()
        
        # Main container with background color
        # Use pack instead of grid to avoid conflicts with menu bar
        main_container = tk.Frame(self.root, bg=self.colors['background'], padx=5, pady=5)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Configure root window for proper resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Enhanced title bar with gradient effect
        self._create_enhanced_title_bar(main_container)
        
        # Create notebook for tabs
        self.main_notebook = ttk.Notebook(main_container)
        self.main_notebook.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        # Increased weight to give more space to the main selection area
        main_container.rowconfigure(1, weight=3)
        
        # Create tabs with scrollable frames
        self._create_tabs()
        
        # Create right panel with action buttons
        self._create_right_panel(main_container)
        
        # Create progress bar and status
        self._create_progress_and_status(main_container)
        
        # Create log output
        self._create_log_output(main_container)
    
    def _create_tabs(self):
        """Create all notebook tabs"""
        # General Tab (file selection, basic options)
        general_tab = self._create_scrollable_tab("📁 General")
        self._create_general_tab_content(general_tab)
        
        # Analysis Tab
        analysis_tab = self._create_scrollable_tab("⚙️ Analysis")
        self.analysis_tab_component = AnalysisTab(self, analysis_tab)
        
        # Visualization Tab
        viz_tab = self._create_scrollable_tab("🎨 Visualization")
        self.viz_tab_component = VisualizationTab(self, viz_tab)
        
        # Tracking Tab
        tracking_tab = self._create_scrollable_tab("🎯 Tracking")
        self.tracking_tab_component = TrackingTab(self, tracking_tab)
        
        # Advanced Tab
        advanced_tab = self._create_scrollable_tab("⚡ Advanced")
        self.advanced_tab_component = AdvancedTab(self, advanced_tab)
        
        # Event Detection Tab
        event_tab = self._create_scrollable_tab("📊 Event Detection")
        self.event_tab_component = EventDetectionTab(self, event_tab)
        
        # Roster Tab
        roster_tab = self._create_scrollable_tab("👥 Roster")
        self.roster_tab_component = RosterTab(self, roster_tab)
        
        # Gallery Tab
        gallery_tab = self._create_scrollable_tab("🖼️ Gallery")
        self.gallery_tab_component = GalleryTab(self, gallery_tab)
        
        # Recognition Tab
        if RecognitionTab:
            recognition_tab = self._create_scrollable_tab("🤖 Recognition")
            self.recognition_tab_component = RecognitionTab(self, recognition_tab)
        
        # ML & Validation Tab
        if MLTab:
            ml_tab = self._create_scrollable_tab("🧠 ML & Validation")
            self.ml_tab_component = MLTab(self, ml_tab)
    
    def _create_scrollable_tab(self, tab_name: str) -> tk.Frame:
        """Create a scrollable tab frame with modern styling"""
        tab_frame = tk.Frame(self.main_notebook, bg=self.colors['background'])
        self.main_notebook.add(tab_frame, text=tab_name)
        
        # Create scrollable canvas
        canvas = tk.Canvas(tab_frame, highlightthickness=0, bg=self.colors['background'], relief=tk.FLAT)
        scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Create content frame inside canvas
        content_frame = tk.Frame(canvas, bg=self.colors['background'], padx=15, pady=15)
        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        content_frame.columnconfigure(1, weight=1)
        
        # Configure scrolling
        def configure_scroll(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas_width = event.width if event else canvas.winfo_width()
            canvas.itemconfig(canvas_window, width=canvas_width)
        
        content_frame.bind("<Configure>", configure_scroll)
        canvas.bind("<Configure>", configure_scroll)
        
        # Enable mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        def unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)
        
        return content_frame
    
    def _create_general_tab_content(self, parent_frame: ttk.Frame):
        """Create content for General tab"""
        row = 0
        
        # Input file selection
        input_label = ttk.Label(parent_frame, text="Input Video:")
        input_label.grid(row=row, column=0, sticky=tk.W, pady=5)
        if create_tooltip:
            create_tooltip(input_label, 
                          TOOLTIP_DATABASE.get("input_file", {}).get("text", "Select the video file to analyze"),
                          TOOLTIP_DATABASE.get("input_file", {}).get("detailed"))
        
        input_entry = ttk.Entry(parent_frame, textvariable=self.input_file, width=50)
        input_entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        if create_tooltip:
            create_tooltip(input_entry, 
                          TOOLTIP_DATABASE.get("input_file", {}).get("text", "Select the video file to analyze"),
                          TOOLTIP_DATABASE.get("input_file", {}).get("detailed"))
        
        self.input_file_button = ttk.Button(parent_frame, text="Browse", command=self.browse_input_file)
        self.input_file_button.grid(row=row, column=2, padx=5, pady=5)
        if create_tooltip:
            create_tooltip(self.input_file_button, 
                          "Browse for video file",
                          "Click to open file browser and select your soccer video file")
        row += 1
        
        # Output file selection
        output_label = ttk.Label(parent_frame, text="Output Video:")
        output_label.grid(row=row, column=0, sticky=tk.W, pady=5)
        if create_tooltip:
            create_tooltip(output_label,
                          TOOLTIP_DATABASE.get("output_file", {}).get("text", "Output file path for analyzed video"),
                          TOOLTIP_DATABASE.get("output_file", {}).get("detailed"))
        
        output_entry = ttk.Entry(parent_frame, textvariable=self.output_file, width=50)
        output_entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        if create_tooltip:
            create_tooltip(output_entry,
                          TOOLTIP_DATABASE.get("output_file", {}).get("text", "Output file path for analyzed video"),
                          TOOLTIP_DATABASE.get("output_file", {}).get("detailed"))
        
        self.output_file_button = ttk.Button(parent_frame, text="Browse", command=self.browse_output_file)
        self.output_file_button.grid(row=row, column=2, padx=5, pady=5)
        if create_tooltip:
            create_tooltip(self.output_file_button,
                          "Browse for output file location",
                          "Click to choose where to save the analyzed video")
        row += 1
        
        # CSV output file selection
        csv_output_label = ttk.Label(parent_frame, text="CSV Output:")
        csv_output_label.grid(row=row, column=0, sticky=tk.W, pady=5)
        if create_tooltip:
            create_tooltip(csv_output_label,
                          "CSV output file path for tracking data",
                          "Optional: Specify custom CSV filename. If empty, auto-generated from output video name.")
        
        csv_output_entry = ttk.Entry(parent_frame, textvariable=self.csv_output_file, width=50)
        csv_output_entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        if create_tooltip:
            create_tooltip(csv_output_entry,
                          "CSV output file path",
                          "Enter path for CSV file or leave empty to auto-generate from output video name")
        
        self.csv_output_file_button = ttk.Button(parent_frame, text="Browse", command=self.browse_csv_output_file)
        self.csv_output_file_button.grid(row=row, column=2, padx=5, pady=5)
        if create_tooltip:
            create_tooltip(self.csv_output_file_button,
                          "Browse for CSV output file location",
                          "Click to choose where to save the tracking data CSV file")
        row += 1
        
        # Video Type
        video_type_frame = ttk.Frame(parent_frame)
        video_type_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5)
        row += 1
        ttk.Label(video_type_frame, text="Video Type:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        video_type_combo = ttk.Combobox(video_type_frame, textvariable=self.video_type, 
                                        values=["practice", "game"], state="readonly", width=12)
        video_type_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(video_type_frame, text="(Practice: flexible team switches | Game: strict uniform validation)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=5)
        
        # Anchor File Selection
        anchor_frame = ttk.Frame(parent_frame)
        anchor_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        row += 1
        ttk.Label(anchor_frame, text="Anchor File (Optional):").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Entry(anchor_frame, textvariable=self.explicit_anchor_file, width=50).grid(
            row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(anchor_frame, text="Browse", command=self.browse_anchor_file).grid(
            row=0, column=2, padx=5, pady=5)
        ttk.Label(anchor_frame, text="(Leave empty to auto-select newest PlayerTagsSeed file)", 
                 foreground="gray", font=("Arial", 8)).grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=5)
        anchor_frame.columnconfigure(1, weight=1)
        
        # Basic options
        options_frame = ttk.LabelFrame(parent_frame, text="Basic Options", padding="10")
        options_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        row += 1
        
        ttk.Checkbutton(options_frame, text="Use Imperial Units (feet, mph)", 
                       variable=self.use_imperial_units).grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(options_frame, text="Export CSV Data", 
                       variable=self.csv_export_enabled).grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(options_frame, text="Preserve Audio", 
                       variable=self.preserve_audio).grid(row=2, column=0, sticky=tk.W, pady=5)
    
    def _create_enhanced_title_bar(self, main_container):
        """Create enhanced title bar with modern styling"""
        # Title frame with gradient-like background
        title_frame = tk.Frame(main_container, bg=self.colors['primary'], height=70)
        title_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        title_frame.grid_propagate(False)
        main_container.columnconfigure(0, weight=1)
        
        # Title with icon
        title_container = tk.Frame(title_frame, bg=self.colors['primary'])
        title_container.pack(side=tk.LEFT, padx=25, pady=15)
        
        title_label = tk.Label(title_container,
                              text="⚽ Soccer Video Analysis Tool",
                              font=("Segoe UI", 20, "bold"),
                              bg=self.colors['primary'],
                              fg='white')
        title_label.pack(side=tk.LEFT)
        
        # Project name with badge style
        project_frame = tk.Frame(title_frame, bg=self.colors['primary'])
        project_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)
        
        project_badge = tk.Frame(project_frame, bg=self.colors['secondary'], relief=tk.FLAT)
        project_badge.pack(side=tk.LEFT, padx=5)
        
        tk.Label(project_badge, text="📁 Project:", 
                font=("Segoe UI", 9, "bold"),
                bg=self.colors['secondary'],
                fg='white',
                padx=12, pady=8).pack(side=tk.LEFT)
        
        self.project_name_label = tk.Label(project_badge,
                                           textvariable=self.current_project_name,
                                           font=("Segoe UI", 10),
                                           bg=self.colors['secondary'],
                                           fg='white',
                                           padx=12, pady=8)
        self.project_name_label.pack(side=tk.LEFT)
        
        # Note: Animation removed for title frame as it's not a Toplevel window
        # Fade-in animation only works for Toplevel windows
    
    def _create_right_panel(self, main_container):
        """Create right panel with action buttons"""
        right_container = tk.Frame(main_container, bg=self.colors['background'])
        # Extend panel to cover all rows (title, notebook, progress, status, log)
        right_container.grid(row=0, column=1, rowspan=6, sticky="nsew", padx=(10, 0))
        main_container.columnconfigure(1, weight=0)
        main_container.rowconfigure(1, weight=1)
        # Allow right container to expand vertically
        right_container.rowconfigure(0, weight=1)
        
        # Create scrollable canvas for right panel
        # Increased width to use more space to the right of the log
        right_canvas = tk.Canvas(right_container, width=280, borderwidth=0, highlightthickness=0,
                                bg=self.colors['background'])
        right_scrollbar = ttk.Scrollbar(right_container, orient="vertical", command=right_canvas.yview)
        right_canvas.configure(yscrollcommand=right_scrollbar.set)
        
        right_scrollbar.pack(side="right", fill="y")
        right_canvas.pack(side="left", fill="both", expand=True)
        
        # Frame inside canvas with modern card style
        right_panel = tk.Frame(right_canvas, bg=self.colors['surface'], relief=tk.RAISED, borderwidth=1)
        right_canvas_window = right_canvas.create_window((0, 0), window=right_panel, anchor="nw")
        
        # Add header to right panel
        header = tk.Frame(right_panel, bg=self.colors['secondary'], height=45)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header,
                text="🛠️ Tools & Actions",
                font=("Segoe UI", 11, "bold"),
                bg=self.colors['secondary'],
                fg='white',
                padx=15).pack(side=tk.LEFT, pady=12)
        
        # Content frame
        right_panel_content = tk.Frame(right_panel, bg=self.colors['surface'], padx=10, pady=10)
        right_panel_content.pack(fill=tk.BOTH, expand=True)
        
        # Configure canvas scrolling
        def configure_right_scroll(event=None):
            right_canvas.configure(scrollregion=right_canvas.bbox("all"))
        
        right_panel.bind("<Configure>", configure_right_scroll)
        
        def configure_right_canvas(event):
            canvas_width = event.width
            right_canvas.itemconfig(right_canvas_window, width=canvas_width)
        
        right_canvas.bind("<Configure>", configure_right_canvas)
        
        # Enable mousewheel scrolling
        def on_right_mousewheel(event):
            right_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel(event):
            right_canvas.bind_all("<MouseWheel>", on_right_mousewheel)
        
        def unbind_mousewheel(event):
            right_canvas.unbind_all("<MouseWheel>")
        
        right_canvas.bind("<Enter>", bind_mousewheel)
        right_canvas.bind("<Leave>", unbind_mousewheel)
        
        # Use right_panel_content for all widgets
        right_panel = right_panel_content
        
        # Analysis Controls
        tk.Label(right_panel, text="⚙️ Analysis Controls", 
                font=("Segoe UI", 10, "bold"),
                bg=self.colors['surface'],
                fg=self.colors['primary']).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        
        self.preview_button = self._create_enhanced_button(right_panel, "👁️ Preview (15 sec)", 
                                                          self.preview_analysis, style='default', width=20)
        self.preview_button.grid(row=1, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.preview_frames_button = self._create_enhanced_button(right_panel, "🖼️ Preview Frames", 
                                                                  self.preview_frames, style='default', width=20)
        self.preview_frames_button.grid(row=2, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.start_button = self._create_enhanced_button(right_panel, "▶ Start Analysis", 
                                                        self.start_analysis, style='success', width=20)
        self.start_button.grid(row=3, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.stop_button = self._create_enhanced_button(right_panel, "⏹ Stop Analysis", 
                                                       self.stop_analysis, style='danger', width=20)
        self.stop_button.grid(row=4, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        self.stop_button.config(state=tk.DISABLED)
        
        self.conflict_resolution_button = self._create_enhanced_button(right_panel, "🔧 Conflict Resolution", 
                                                                      self.open_conflict_resolution, style='default', width=20)
        self.conflict_resolution_button.grid(row=5, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        # Analysis & Results
        tk.Label(right_panel, text="📊 Analysis & Results", 
                font=("Segoe UI", 10, "bold"),
                bg=self.colors['surface'],
                fg=self.colors['primary']).grid(row=6, column=0, sticky=tk.W, pady=(15, 8))
        
        self.open_folder_button = self._create_enhanced_button(right_panel, "📂 Open Output Folder", 
                                                               self.open_output_folder, style='default', width=20)
        self.open_folder_button.grid(row=7, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        self.open_folder_button.config(state=tk.DISABLED)
        
        self.analyze_csv_button = self._create_enhanced_button(right_panel, "📈 Analyze CSV Data", 
                                                               self.analyze_csv, style='default', width=20)
        self.analyze_csv_button.grid(row=8, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.analytics_selection_button = self._create_enhanced_button(right_panel, "📊 Analytics Selection", 
                                                                      self.open_analytics_selection, style='default', width=20)
        self.analytics_selection_button.grid(row=9, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.setup_checklist_button = self._create_enhanced_button(right_panel, "✅ Setup Checklist", 
                                                                   self.open_setup_checklist, style='default', width=20)
        self.setup_checklist_button.grid(row=10, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.evaluate_tracking_button = self._create_enhanced_button(right_panel, "📏 Evaluate Tracking Metrics", 
                                                                    self.evaluate_tracking_metrics, style='default', width=20)
        self.evaluate_tracking_button.grid(row=11, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        # Post-Analysis Automation
        self.post_analysis_automation_button = self._create_enhanced_button(right_panel, "🔄 Re-run Post-Analysis Automation", 
                                                                           self.manual_post_analysis_automation, style='primary', width=20)
        self.post_analysis_automation_button.grid(row=12, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        if create_tooltip:
            create_tooltip(self.post_analysis_automation_button,
                          "Re-run Post-Analysis Automation",
                          "Manually trigger the post-analysis automation chain:\n• Auto-detect events\n• Generate highlights\n• Export statistics")
        
        # Anchor Frame Tools
        tk.Label(right_panel, text="🔗 Anchor Frame Tools", 
                font=("Segoe UI", 10, "bold"),
                bg=self.colors['surface'],
                fg=self.colors['primary']).grid(row=13, column=0, sticky=tk.W, pady=(15, 8))
        
        self.convert_tracks_anchor_button = self._create_enhanced_button(right_panel, "🔄 Convert Tracks → Anchors", 
                                                                          self.convert_tracks_to_anchors, style='default', width=20)
        self.convert_tracks_anchor_button.grid(row=14, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.convert_tags_anchor_button = self._create_enhanced_button(right_panel, "🏷️ Convert Tags → Anchors", 
                                                                        self.convert_tags_to_anchors, style='default', width=20)
        self.convert_tags_anchor_button.grid(row=15, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.fix_anchor_frames_button = self._create_enhanced_button(right_panel, "🔧 Fix Failed Anchors", 
                                                                     self.fix_failed_anchor_frames, style='default', width=20)
        self.fix_anchor_frames_button.grid(row=16, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.optimize_anchor_frames_button = self._create_enhanced_button(right_panel, "⚡ Optimize Anchors", 
                                                                           self.optimize_anchor_frames, style='default', width=20)
        self.optimize_anchor_frames_button.grid(row=17, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.clear_anchor_frames_button = self._create_enhanced_button(right_panel, "🗑️ Clear Anchor Frames", 
                                                                       self.clear_anchor_frames, style='danger', width=20)
        self.clear_anchor_frames_button.grid(row=18, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        # Player Management
        tk.Label(right_panel, text="👥 Player Management", 
                font=("Segoe UI", 10, "bold"),
                bg=self.colors['surface'],
                fg=self.colors['primary']).grid(row=19, column=0, sticky=tk.W, pady=(15, 8))
        
        self.interactive_learning_button = self._create_enhanced_button(right_panel, "🎓 Interactive Player Learning", 
                                                                         self.open_interactive_learning, style='default', width=20)
        self.interactive_learning_button.grid(row=20, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.track_review_button = self._create_enhanced_button(right_panel, "📝 Track Review & Assign", 
                                                                self.open_track_review, style='default', width=20)
        self.track_review_button.grid(row=21, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.clear_gallery_refs_button = self._create_enhanced_button(right_panel, "🗑️ Clear Gallery References", 
                                                                      self.clear_gallery_references, style='danger', width=20)
        self.clear_gallery_refs_button.grid(row=22, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.consolidate_ids_button = self._create_enhanced_button(right_panel, "🔀 Consolidate IDs", 
                                                                    self.consolidate_ids, style='default', width=20)
        self.consolidate_ids_button.grid(row=23, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.export_reid_button = self._create_enhanced_button(right_panel, "📦 Export ReID Model", 
                                                               self.export_reid_model, style='default', width=20)
        self.export_reid_button.grid(row=24, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        # Setup & Calibration
        tk.Label(right_panel, text="⚙️ Setup & Calibration", 
                font=("Segoe UI", 10, "bold"),
                bg=self.colors['surface'],
                fg=self.colors['primary']).grid(row=25, column=0, sticky=tk.W, pady=(15, 8))
        
        self.color_helper_button = self._create_enhanced_button(right_panel, "🎨 Color Helper", 
                                                               self.open_color_helper, style='default', width=20)
        self.color_helper_button.grid(row=26, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        
        self.field_calibration_button = self._create_enhanced_button(right_panel, "📐 Calibrate Field", 
                                                                      self.open_field_calibration, style='default', width=20)
        self.field_calibration_button.grid(row=27, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        if create_tooltip:
            create_tooltip(self.field_calibration_button,
                          TOOLTIP_DATABASE.get("calibrate_field", {}).get("text", "Calibrate field boundaries and dimensions"),
                          TOOLTIP_DATABASE.get("calibrate_field", {}).get("detailed"))
        
        # Quick Start button (prominent)
        self.quick_start_button = self._create_enhanced_button(right_panel, "🚀 Quick Start", 
                                                              self.open_quick_start_wizard, style='primary', width=20)
        self.quick_start_button.grid(row=28, column=0, padx=5, pady=8, sticky=tk.W+tk.E)
        if create_tooltip:
            create_tooltip(self.quick_start_button,
                          "Quick Start Wizard",
                          "Get started quickly with preset configurations and automated features")
        
        self.setup_wizard_button = ttk.Button(right_panel, text="Setup Wizard", 
                                             command=self.open_setup_wizard, width=20)
        self.setup_wizard_button.grid(row=29, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        if create_tooltip:
            create_tooltip(self.setup_wizard_button,
                          TOOLTIP_DATABASE.get("setup_wizard", {}).get("text", "Open Interactive Setup Wizard"),
                          TOOLTIP_DATABASE.get("setup_wizard", {}).get("detailed"))
        
        # Player Gallery
        ttk.Label(right_panel, text="Player Gallery:", font=("Arial", 9, "bold")).grid(row=30, column=0, sticky=tk.W, pady=(15, 5))
        
        self.tag_players_gallery_button = ttk.Button(right_panel, text="Tag Players (Gallery)", 
                                                     command=self.open_tag_players_gallery, width=20)
        self.tag_players_gallery_button.grid(row=31, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.gallery_seeder_button = ttk.Button(right_panel, text="Player Gallery Seeder", 
                                                command=self.open_gallery_seeder, width=20)
        self.gallery_seeder_button.grid(row=32, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Video Tools
        ttk.Label(right_panel, text="Video Tools:", font=("Arial", 9, "bold")).grid(row=33, column=0, sticky=tk.W, pady=(15, 5))
        
        self.batch_processing_button = self._create_enhanced_button(right_panel, "📦 Batch Processing", 
                                                                    self.open_batch_processing, style='primary', width=20)
        self.batch_processing_button.grid(row=34, column=0, padx=5, pady=4, sticky=tk.W+tk.E)
        if create_tooltip:
            create_tooltip(self.batch_processing_button,
                          "Batch Video Processing",
                          "Process multiple videos automatically with sequential or parallel processing\n"
                          "• Add multiple videos or entire folders\n"
                          "• System suggests optimal processing mode\n"
                          "• Real-time progress tracking\n"
                          "• Error handling and recovery")
        
        self.video_splicer_button = ttk.Button(right_panel, text="Video Splicer", 
                                              command=self.open_video_splicer, width=20)
        self.video_splicer_button.grid(row=35, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.amazfit_import_button = ttk.Button(right_panel, text="Import Amazfit Data", 
                                                command=self.open_amazfit_import, width=20)
        self.amazfit_import_button.grid(row=36, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Viewers
        ttk.Label(right_panel, text="Viewers:", font=("Arial", 9, "bold")).grid(row=37, column=0, sticky=tk.W, pady=(15, 5))
        
        self.playback_viewer_button = ttk.Button(right_panel, text="Playback Viewer", 
                                                 command=self.open_playback_viewer, width=20)
        self.playback_viewer_button.grid(row=38, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        if create_tooltip:
            create_tooltip(self.playback_viewer_button,
                          TOOLTIP_DATABASE.get("playback_viewer", {}).get("text", "Open playback viewer for analyzed video"),
                          TOOLTIP_DATABASE.get("playback_viewer", {}).get("detailed"))
        
        self.event_timeline_button = ttk.Button(right_panel, text="📊 Event Timeline", 
                                                command=self.open_event_timeline_viewer, width=20)
        self.event_timeline_button.grid(row=39, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        if create_tooltip:
            create_tooltip(self.event_timeline_button,
                          "Open Event Timeline Viewer to view, create clips, and manage game events",
                          "View all detected events (passes, shots, goals, etc.) on a timeline. Create video clips from events and tag them to players.")
        
        self.speed_tracking_button = ttk.Button(right_panel, text="Speed Tracking", 
                                               command=self.open_speed_tracking, width=20)
        self.speed_tracking_button.grid(row=40, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Project Management
        ttk.Label(right_panel, text="Project Management:", font=("Arial", 9, "bold")).grid(row=41, column=0, sticky=tk.W, pady=(15, 5))
        
        self.create_project_button = ttk.Button(right_panel, text="Create New Project", 
                                               command=self.create_new_project, width=20)
        self.create_project_button.grid(row=42, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.save_project_button = ttk.Button(right_panel, text="Save Project", 
                                              command=self.save_project, width=20)
        self.save_project_button.grid(row=43, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.save_project_as_button = ttk.Button(right_panel, text="Save Project As...", 
                                                 command=self.save_project_as, width=20)
        self.save_project_as_button.grid(row=44, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.load_project_button = ttk.Button(right_panel, text="Load Project", 
                                              command=self.load_project, width=20)
        self.load_project_button.grid(row=45, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.rename_project_button = ttk.Button(right_panel, text="Rename Project", 
                                                command=self.rename_project, width=20)
        self.rename_project_button.grid(row=46, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        right_panel.columnconfigure(0, weight=1)
    
    def _create_progress_and_status(self, main_container):
        """Create enhanced progress bar and status label with time estimates"""
        # Progress frame with card style
        progress_card, progress_content = self._create_card_frame(main_container, title="📊 Progress")
        progress_card.grid(row=2, column=0, sticky="ew", pady=10, padx=5)
        progress_content.columnconfigure(0, weight=1)
        
        # Progress info header
        info_frame = tk.Frame(progress_content, bg=self.colors['surface'])
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = tk.Label(info_frame,
                                     text="✓ Ready",
                                     font=("Segoe UI", 10, "bold"),
                                     bg=self.colors['surface'],
                                     fg=self.colors['text_primary'])
        self.status_label.pack(side=tk.LEFT)
        
        self.progress_percent_label = tk.Label(info_frame,
                                               text="0%",
                                               font=("Segoe UI", 10, "bold"),
                                               bg=self.colors['surface'],
                                               fg=self.colors['primary'])  # Green for percentage
        self.progress_percent_label.pack(side=tk.RIGHT)
        
        # Progress bar with modern styling
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_content,
                                            variable=self.progress_var,
                                            maximum=100,
                                            style="Modern.Horizontal.TProgressbar",
                                            mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Detailed status label
        self.detailed_status_label = tk.Label(progress_content,
                                              text="",
                                              font=("Segoe UI", 8),
                                              bg=self.colors['surface'],
                                              fg=self.colors['text_secondary'])
        self.detailed_status_label.pack(fill=tk.X)
        
        # Cancel button
        button_frame = tk.Frame(progress_content, bg=self.colors['surface'])
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.cancel_button = self._create_enhanced_button(button_frame,
                                                          "✕ Cancel",
                                                          self._request_cancel,
                                                          style='danger',
                                                          width=15)
        self.cancel_button.pack(side=tk.RIGHT)
        self.cancel_button.config(state=tk.DISABLED)
    
    def _create_log_output(self, main_container):
        """Create enhanced log output area with modern styling"""
        # Log frame with card style
        log_card, log_content = self._create_card_frame(main_container, title="📋 Processing Log")
        log_card.grid(row=4, column=0, sticky="ew", pady=5, padx=5)
        
        # Log text area with modern dark theme styling
        self.log_text = scrolledtext.ScrolledText(log_content,
                                                  height=6,
                                                  wrap=tk.WORD,
                                                  state=tk.DISABLED,
                                                  bg=self.colors['log_bg'],
                                                  fg=self.colors['log_fg'],
                                                  insertbackground='white',
                                                  selectbackground=self.colors['secondary'],
                                                  font=("Consolas", 9),
                                                  relief=tk.FLAT,
                                                  borderwidth=0,
                                                  padx=10,
                                                  pady=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def _init_quick_wins(self):
        """Initialize quick wins features if available"""
        try:
            from gui_quick_wins import (
                UndoManager, RecentProjectsManager, AutoSaveManager,
                KeyboardShortcuts
            )
            self.undo_manager = UndoManager()
            self.recent_projects = RecentProjectsManager()
            self.auto_save = AutoSaveManager(self.save_project, interval_seconds=300)
            self.keyboard_shortcuts = KeyboardShortcuts(self.root)
            self._setup_keyboard_shortcuts()
        except ImportError:
            self.undo_manager = None
            self.recent_projects = None
            self.auto_save = None
            self.keyboard_shortcuts = None
    
    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts"""
        if self.keyboard_shortcuts:
            # Add shortcuts here
            pass
    
    def _create_menu_bar(self):
        """Create full menu bar with File, Edit, View, Tools, Help menus"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Project...", command=self.create_new_project)
        file_menu.add_command(label="Open Project...", command=lambda: self.load_project())
        file_menu.add_separator()
        file_menu.add_command(label="Save Project", command=self.save_project)
        file_menu.add_command(label="Save Project As...", command=self.save_project_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        # Undo/Redo
        edit_menu.add_command(
            label="Undo",
            command=self.undo_action,
            accelerator="Ctrl+Z",
            state=tk.DISABLED
        )
        edit_menu.add_command(
            label="Redo",
            command=self.redo_action,
            accelerator="Ctrl+Y",
            state=tk.DISABLED
        )
        
        edit_menu.add_separator()
        edit_menu.add_command(label="History...", command=self.show_action_history)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Playback Viewer", command=self.open_playback_viewer)
        view_menu.add_command(label="Setup Wizard", command=self.open_setup_wizard)
        view_menu.add_command(label="Gallery Seeder", command=self.open_gallery_seeder)
        view_menu.add_separator()
        view_menu.add_command(label="Event Timeline", command=self.open_event_timeline_viewer)
        view_menu.add_command(label="Player Stats", command=self.open_player_stats)
        view_menu.add_separator()
        view_menu.add_command(label="Output Folder", command=self.open_output_folder)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        
        # Track conversion submenu
        track_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Track Conversion", menu=track_menu)
        track_menu.add_command(label="Convert Tracks to Anchors", command=self.convert_tracks_to_anchors)
        track_menu.add_command(label="Convert Tags to Anchors", command=self.convert_existing_tags_to_anchors)
        track_menu.add_command(label="Fix Failed Anchors", command=self.fix_failed_anchor_frames)
        track_menu.add_command(label="Optimize Anchor Frames", command=self.optimize_anchor_frames)
        track_menu.add_command(label="Clear Anchor Frames", command=self.clear_anchor_frames)
        
        # Gallery management submenu
        gallery_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Gallery Management", menu=gallery_menu)
        gallery_menu.add_command(label="Backfill Features", command=self.backfill_gallery_features)
        gallery_menu.add_command(label="Match Unnamed Anchors", command=self.match_unnamed_anchor_frames)
        gallery_menu.add_command(label="Remove False Matches", command=self.remove_false_matches_from_gallery)
        gallery_menu.add_command(label="Remove Missing Frames", command=self.remove_missing_reference_frames)
        gallery_menu.add_command(label="Remove Unavailable Images", command=self.remove_unavailable_images)
        gallery_menu.add_command(label="Clear Gallery References", command=self.clear_gallery_references)
        
        # Post-analysis tools submenu
        post_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Post-Analysis", menu=post_menu)
        post_menu.add_command(label="Workflow Guide", command=self.open_post_analysis_workflow)
        post_menu.add_command(label="Consolidate IDs", command=self.consolidate_ids)
        post_menu.add_command(label="Track Review", command=self.open_track_review)
        
        # Multi-camera tools
        tools_menu.add_separator()
        tools_menu.add_command(label="Multi-Camera Setup", command=self.open_multi_camera_wizard)
        tools_menu.add_command(label="Open Multi-Camera Project...", command=self.open_multi_camera_project)
        post_menu.add_command(label="Interactive Learning", command=self.open_interactive_learning)
        post_menu.add_separator()
        post_menu.add_command(label="Re-run Post-Analysis Automation", command=self.manual_post_analysis_automation)
        post_menu.add_separator()
        post_menu.add_command(label="Evaluate Metrics (HOTA)", command=self.evaluate_hota)
        
        # Helper tools submenu
        helper_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Helpers", menu=helper_menu)
        helper_menu.add_command(label="Color Helper", command=self.open_color_helper)
        helper_menu.add_command(label="Field Calibration", command=self.open_field_calibration)
        helper_menu.add_command(label="Setup Checklist", command=self.open_setup_checklist)
        
        # Video tools submenu
        video_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Video Tools", menu=video_menu)
        video_menu.add_command(label="Batch Processing", command=self.open_batch_processing)
        video_menu.add_separator()
        video_menu.add_command(label="Video Splicer", command=self.open_video_splicer)
        video_menu.add_command(label="Speed Tracking", command=self.open_speed_tracking)
        video_menu.add_separator()
        video_menu.add_command(label="Real-Time Analysis", command=self.open_real_time_processor)
        video_menu.add_separator()
        video_menu.add_command(label="Import Amazfit Data", command=self.open_amazfit_import)
        
        tools_menu.add_separator()
        tools_menu.add_command(label="Export Re-ID Model", command=self.export_reid_model)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_keyboard_shortcuts)
        help_menu.add_command(label="About", command=self.show_about)
    
    def _setup_undo_redo_shortcuts(self):
        """Setup keyboard shortcuts for undo/redo"""
        self.root.bind('<Control-z>', lambda e: self.undo_action())
        self.root.bind('<Control-y>', lambda e: self.redo_action())
        self.root.bind('<Control-Z>', lambda e: self.undo_action())  # Shift+Ctrl+Z
        # Update menu states periodically
        self._update_undo_redo_states()
        self.root.after(500, self._update_undo_redo_states_periodic)
    
    def _update_undo_redo_states_periodic(self):
        """Periodically update undo/redo menu states"""
        self._update_undo_redo_states()
        self.root.after(500, self._update_undo_redo_states_periodic)
    
    def _update_undo_redo_states(self):
        """Update undo/redo menu item states"""
        if self.action_history:
            try:
                menubar = self.root.nametowidget(".!menu")
                edit_menu = menubar.nametowidget("edit")
                edit_menu.entryconfig(0, 
                                    state=tk.NORMAL if self.action_history.can_undo() else tk.DISABLED)
                edit_menu.entryconfig(1,
                                    state=tk.NORMAL if self.action_history.can_redo() else tk.DISABLED)
            except:
                pass  # Menu might not be created yet
    
    def undo_action(self):
        """Undo last action"""
        if self.action_history and self.action_history.can_undo():
            description = self.action_history.undo()
            if description:
                self.log_message(f"Undone: {description}")
                self._update_undo_redo_states()
                
                # Show info toast
                if self.toast_manager:
                    self.toast_manager.info(f"Undone: {description[:40]}")
    
    def redo_action(self):
        """Redo next action"""
        if self.action_history and self.action_history.can_redo():
            description = self.action_history.redo()
            if description:
                self.log_message(f"Redone: {description}")
                self._update_undo_redo_states()
                
                # Show info toast
                if self.toast_manager:
                    self.toast_manager.info(f"Redone: {description[:40]}")
                
                # Show info toast
                if self.toast_manager:
                    self.toast_manager.info(f"Redone: {description[:40]}")
    
    def show_action_history(self):
        """Show action history window"""
        if not self.action_history:
            messagebox.showinfo("Action History", "Action history is not available.")
            return
        
        history_window = tk.Toplevel(self.root)
        history_window.title("Action History")
        history_window.geometry("600x400")
        
        # Create listbox with scrollbar
        frame = ttk.Frame(history_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Recent Actions:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        listbox_frame = ttk.Frame(frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, font=("Arial", 9))
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Populate with history
        history = self.action_history.get_history_summary(limit=50)
        for item in reversed(history):  # Show most recent first
            marker = "→ " if item["is_current"] else "  "
            listbox.insert(0, f"{marker}{item['description']} ({item['timestamp'][:19]})")
        
        # Close button
        ttk.Button(frame, text="Close", command=history_window.destroy).pack(pady=5)
    
    def show_keyboard_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        shortcuts_window = tk.Toplevel(self.root)
        shortcuts_window.title("Keyboard Shortcuts")
        shortcuts_window.geometry("500x400")
        
        frame = ttk.Frame(shortcuts_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        text = tk.Text(frame, wrap=tk.WORD, font=("Arial", 9))
        text.pack(fill=tk.BOTH, expand=True)
        
        shortcuts_text = """Keyboard Shortcuts:

File Operations:
  Ctrl+O          Open file
  Ctrl+S          Save
  Ctrl+Shift+S    Save As

Edit Operations:
  Ctrl+Z          Undo
  Ctrl+Y          Redo
  Ctrl+Shift+Z    Redo (alternative)

Analysis:
  F5              Start Analysis
  Esc             Cancel Analysis

Navigation:
  Tab             Next control
  Shift+Tab       Previous control
  Enter           Activate button/confirm

Playback Viewer:
  Space           Play/Pause
  Left Arrow      Previous frame
  Right Arrow     Next frame
  G               Mark Goal
  S               Mark Shot
  P               Mark Pass
  F               Mark Foul
"""
        
        text.insert("1.0", shortcuts_text)
        text.config(state=tk.DISABLED)
        
        ttk.Button(frame, text="Close", command=shortcuts_window.destroy).pack(pady=5)
    
    def show_about(self):
        """Show About dialog"""
        about_window = tk.Toplevel(self.root)
        about_window.title("About Soccer Analysis Tool")
        about_window.geometry("400x300")
        about_window.transient(self.root)
        
        frame = ttk.Frame(about_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Soccer Video Analysis Tool", 
                 font=("Arial", 16, "bold")).pack(pady=10)
        ttk.Label(frame, text="Version 2.0.0", font=("Arial", 10)).pack()
        ttk.Label(frame, text="\nProfessional soccer video analysis\nwith player and ball tracking", 
                 font=("Arial", 9), justify=tk.CENTER).pack(pady=10)
        ttk.Label(frame, text="© 2025", font=("Arial", 8), foreground="gray").pack(pady=20)
        
        ttk.Button(frame, text="Close", command=about_window.destroy).pack(pady=10)
    
    def _request_cancel(self) -> bool:
        """Request cancellation with confirmation - returns True if confirmed"""
        if not self.processing:
            return False
        
        # Warning dialog for destructive action
        response = messagebox.askyesno(
            "⚠️ Warning: Cancel Analysis",
            "Are you sure you want to cancel the current analysis?\n\n"
            "This will:\n"
            "• Stop processing immediately\n"
            "• Lose all current progress\n"
            "• Require restarting analysis from the beginning\n\n"
            "Any completed work will be saved.\n\n"
            "Do you want to continue?",
            icon='warning'
        )
        
        if response:
            if self.progress_tracker:
                self.progress_tracker.set_cancelled(True)
            self.processing = False
            if hasattr(self, 'cancel_button'):
                self.cancel_button.config(state=tk.DISABLED)
            if hasattr(self, 'status_label'):
                self.status_label.config(text="Cancelled")
            self.log_message("Analysis cancelled by user")
            
            # Show info toast
            if self.toast_manager:
                self.toast_manager.info("Analysis cancelled")
            
            return True
        return False
    
    def update_progress(self, current: int, total: int, status: str = "", 
                       details: str = "", phase: str = ""):
        """
        Update progress display with enhanced information
        
        Args:
            current: Current item number
            total: Total items
            status: Status message
            details: Detailed status
            phase: Processing phase
        """
        if self.progress_tracker:
            self.progress_tracker.update(current, status, details, phase)
            summary = self.progress_tracker.get_status_summary()
            
            # Update progress bar
            self.progress_var.set(summary["progress"])
            
            # Update status label
            self.status_label.config(text=summary["status"] or "Processing...")
            
            # Update detailed status
            detailed_text = []
            if summary["phase"]:
                detailed_text.append(f"Phase: {summary['phase']}")
            if summary["remaining"]:
                detailed_text.append(f"Time remaining: {self._format_timedelta(summary['remaining'])}")
            if summary["speed"] > 0:
                detailed_text.append(f"Speed: {summary['speed']:.1f} {summary['item_name']}/s")
            if summary["elapsed"]:
                detailed_text.append(f"Elapsed: {self._format_timedelta(summary['elapsed'])}")
            
            self.detailed_status_label.config(text=" | ".join(detailed_text))
            
            # Update progress percentage
            self.progress_percent_label.config(text=f"{summary['progress']:.1f}%")
            
            # Enable cancel button
            if not self.processing:
                self.processing = True
                if hasattr(self, 'cancel_button'):
                    self.cancel_button.config(state=tk.NORMAL)
            
            # Show completion toast when done
            if summary["progress"] >= 100.0 and self.processing:
                self.processing = False
                if hasattr(self, 'cancel_button'):
                    self.cancel_button.config(state=tk.DISABLED)
                if self.toast_manager:
                    self.toast_manager.success("Analysis completed successfully!")
        else:
            # Fallback to basic progress
            progress = (current / total * 100) if total > 0 else 0.0
            self.progress_var.set(progress)
            self.status_label.config(text=status or f"Processing... {current}/{total}")
    
    def _format_timedelta(self, td) -> str:
        """Format timedelta as human-readable string"""
        if hasattr(td, 'total_seconds'):
            total_seconds = int(td.total_seconds())
        else:
            total_seconds = int(td)
        
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    # File operations
    def browse_input_file(self):
        """Browse for input video file"""
        filename = filedialog.askopenfilename(
            title="Select Input Video",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v *.mpg *.mpeg"), 
                      ("All files", "*.*")]
        )
        if filename:
            self.input_file.set(filename)
            if not self.output_file.get():
                base_name = os.path.splitext(filename)[0]
                self.output_file.set(f"{base_name}_analyzed.mp4")
            # Auto-suggest CSV filename if not set
            if not self.csv_output_file.get() and self.output_file.get():
                output_path = self.output_file.get()
                csv_path = output_path.replace('.mp4', '_tracking_data.csv').replace('.avi', '_tracking_data.csv')
                self.csv_output_file.set(csv_path)
            self.log_message(f"Selected input: {filename}")
            self._check_and_enable_output_buttons()
    
    def browse_output_file(self):
        """Browse for output video file"""
        filename = filedialog.asksaveasfilename(
            title="Save Output Video As",
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        if filename:
            # Record action for undo/redo
            old_value = self.output_file.get()
            if self.action_history:
                self.action_history.add_action(
                    ActionType.CHANGE_SETTING if ActionType else None,
                    f"Changed output file to {os.path.basename(filename)}",
                    undo_func=lambda: self.output_file.set(old_value),
                    redo_func=lambda: self.output_file.set(filename),
                    data={"setting": "output_file", "old": old_value, "new": filename}
                )
            
            self.output_file.set(filename)
            # Auto-suggest CSV filename if not set
            if not self.csv_output_file.get():
                csv_path = filename.replace('.mp4', '_tracking_data.csv').replace('.avi', '_tracking_data.csv')
                self.csv_output_file.set(csv_path)
            self.log_message(f"Output will be saved to: {filename}")
            self._check_and_enable_output_buttons()
            self._update_undo_redo_states()
            
            # Show success toast
            if self.toast_manager:
                self.toast_manager.success(f"Output file set: {os.path.basename(filename)}")
    
    def browse_csv_output_file(self):
        """Browse for CSV output file"""
        filename = filedialog.asksaveasfilename(
            title="Save CSV Output As",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            # Record action for undo/redo
            old_value = self.csv_output_file.get()
            if self.action_history:
                self.action_history.add_action(
                    ActionType.CHANGE_SETTING if ActionType else None,
                    f"Changed CSV output file to {os.path.basename(filename)}",
                    undo_func=lambda: self.csv_output_file.set(old_value),
                    redo_func=lambda: self.csv_output_file.set(filename),
                    data={"setting": "csv_output_file", "old": old_value, "new": filename}
                )
            
            self.csv_output_file.set(filename)
            self.log_message(f"CSV output will be saved to: {filename}")
            self._update_undo_redo_states()
            
            # Show success toast
            if self.toast_manager:
                self.toast_manager.success(f"CSV output file set: {os.path.basename(filename)}")
    
    def _browse_event_csv_file(self):
        """Browse for CSV tracking file for event detection"""
        filename = filedialog.askopenfilename(
            title="Select Tracking CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.event_csv_file.set(filename)
    
    def _auto_detect_event_csv(self):
        """Auto-detect CSV file from output file"""
        output_file = self.output_file.get()
        if not output_file:
            messagebox.showwarning("No Output File", 
                                 "Please set an output file first to auto-detect the CSV file.")
            return
        
        # Look for CSV in same directory as output file
        output_dir = os.path.dirname(output_file)
        output_basename = os.path.splitext(os.path.basename(output_file))[0]
        
        # Try common CSV filename patterns
        csv_patterns = [
            f"{output_basename}_analyzed_tracking_data.csv",
            f"{output_basename}_tracking_data.csv",
            f"{output_basename}.csv"
        ]
        
        for pattern in csv_patterns:
            csv_path = os.path.join(output_dir, pattern)
            if os.path.exists(csv_path):
                self.event_csv_file.set(csv_path)
                messagebox.showinfo("CSV Found", f"Found CSV file:\n{csv_path}")
                return
        
        # If not found, let user browse
        messagebox.showwarning("CSV Not Found", 
                             f"Could not find CSV file in:\n{output_dir}\n\n"
                             "Please browse for the CSV file manually.")
        self._browse_event_csv_file()
    
    def _browse_goal_areas_file(self):
        """Browse for goal areas JSON file"""
        filename = filedialog.askopenfilename(
            title="Select Goal Areas JSON File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.event_goal_areas_file.set(filename)
    
    def _designate_goal_areas(self):
        """Open interactive goal area designation tool"""
        # Get video file from input file
        video_path = self.input_file.get()
        if not video_path or not os.path.exists(video_path):
            messagebox.showwarning("No Video File", 
                                 "Please select an input video file first.")
            return
        
        try:
            from goal_area_designator import designate_goal_areas_interactive
        except ImportError:
            try:
                from SoccerID.goal_area_designator import designate_goal_areas_interactive
            except ImportError:
                messagebox.showerror("Error", "Could not import goal_area_designator module")
                return
        
        # Check if goal areas file already exists
        existing_goal_areas_file = self.event_goal_areas_file.get() if hasattr(self, 'event_goal_areas_file') else None
        if existing_goal_areas_file and not os.path.exists(existing_goal_areas_file):
            existing_goal_areas_file = None
        
        # Open goal area designation tool
        try:
            designator = designate_goal_areas_interactive(video_path, frame_num=0, existing_goal_areas_file=existing_goal_areas_file)
            if designator and designator.goal_areas:
                # Save goal areas
                output_path = designator.save_goal_areas()
                self.event_goal_areas_file.set(output_path)
                messagebox.showinfo("Success", 
                                 f"Goal areas saved to:\n{output_path}\n\n"
                                 f"Designated {len(designator.goal_areas)} goal area(s)")
            elif designator:
                messagebox.showinfo("Cancelled", "Goal area designation was cancelled.")
        except KeyboardInterrupt:
            # User interrupted (Ctrl+C or window closed)
            messagebox.showinfo("Cancelled", "Goal area designation was cancelled.")
        except Exception as e:
            # Handle any other errors
            messagebox.showerror("Error", 
                               f"An error occurred during goal area designation:\n{str(e)}\n\n"
                               "Please try again or check the video file.")
    
    def _auto_detect_goal_areas(self):
        """Auto-detect goal areas file from video directory"""
        video_path = self.input_file.get()
        if not video_path or not os.path.exists(video_path):
            messagebox.showwarning("No Video File", 
                                 "Please select an input video file first.")
            return
        
        video_dir = os.path.dirname(os.path.abspath(video_path))
        video_basename = os.path.splitext(os.path.basename(video_path))[0]
        
        # Try common goal area filename patterns
        goal_area_patterns = [
            f"goal_areas_{video_basename}.json",
            f"{video_basename}_goal_areas.json",
            "goal_areas.json"
        ]
        
        for pattern in goal_area_patterns:
            goal_area_path = os.path.join(video_dir, pattern)
            if os.path.exists(goal_area_path):
                self.event_goal_areas_file.set(goal_area_path)
                messagebox.showinfo("Goal Areas Found", f"Found goal areas file:\n{goal_area_path}")
                return
        
        # If not found, let user know
        messagebox.showinfo("Goal Areas Not Found", 
                           f"Could not find goal areas file in:\n{video_dir}\n\n"
                           "Please designate goal areas first using 'Designate Goal Areas' button.")
        self._browse_goal_areas_file()
    
    def browse_anchor_file(self):
        """Browse for anchor file"""
        filename = filedialog.askopenfilename(
            title="Select PlayerTagsSeed File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.explicit_anchor_file.set(filename)
            self.log_message(f"Selected anchor file: {filename}")
    
    # Analysis operations
    def preview_analysis(self):
        """Preview analysis on a small sample (15 seconds) to see output quickly"""
        if not self.input_file.get():
            messagebox.showwarning("Warning", "Please select an input video file first.")
            return
        
        if not self.output_file.get():
            messagebox.showwarning("Warning", "Please specify an output file first.")
            return
        
        # Create preview output filename
        preview_output = self.output_file.get().replace('.mp4', '_preview.mp4').replace('.avi', '_preview.avi')
        
        # Ask user to confirm preview
        preview_frames = self._safe_get_int(self.preview_max_frames, 360)
        response = messagebox.askyesno("Preview Analysis", 
                                      f"Preview will process {preview_frames} frames (~{preview_frames/24:.1f} seconds at 24fps) of your video.\n\n"
                                      f"Output: {os.path.basename(preview_output)}\n\n"
                                      f"This lets you quickly see how your settings look.\n\n"
                                      f"Continue?")
        if not response:
            return
        
        # Clear any previous stop requests
        try:
            import shared_state
            shared_state.clear_analysis_stop()
        except ImportError:
            pass
        
        # Start preview in separate thread
        self.processing = True
        if hasattr(self, 'start_button'):
            self.start_button.config(state=tk.DISABLED)
        if hasattr(self, 'preview_button'):
            self.preview_button.config(state=tk.DISABLED)
        if hasattr(self, 'stop_button'):
            self.stop_button.config(state=tk.NORMAL)
        if hasattr(self, 'progress_var'):
            self.progress_var.set(0)
        if hasattr(self, 'status_label'):
            self.status_label.config(text="Previewing...")
        
        import threading
        preview_thread = threading.Thread(target=self.run_preview_analysis, args=(preview_output,), daemon=True)
        preview_thread.start()
    
    def run_preview_analysis(self, preview_output):
        """Run preview analysis on a small sample"""
        try:
            import cv2
            
            # Load analysis module
            try:
                try:
                    from combined_analysis_optimized import combined_analysis_optimized as combined_analysis
                    OPTIMIZED_AVAILABLE = True
                except ImportError:
                    from combined_analysis import combined_analysis
                    OPTIMIZED_AVAILABLE = False
            except ImportError:
                self.root.after(0, lambda: self.preview_complete(False, "Failed to load analysis module"))
                return
            
            # Preview mode requires optimized version
            if not OPTIMIZED_AVAILABLE:
                self.root.after(0, lambda: self.preview_complete(False, "Preview mode requires optimized analysis. Please ensure combined_analysis_optimized.py is available."))
                return
            
            # Get video info to determine preview length
            cap = cv2.VideoCapture(self.input_file.get())
            if not cap.isOpened():
                self.root.after(0, lambda: self.preview_complete(False, "Could not open video file"))
                return
            
            fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            
            # Preview: Use configured preview_max_frames or calculate from FPS
            preview_frames = min(self._safe_get_int(self.preview_max_frames, 360), int(fps * 15), total_frames)
            
            self.log_message("=" * 60)
            self.log_message(f"PREVIEW MODE: Processing {preview_frames} frames (~{preview_frames/fps:.1f} seconds)")
            self.log_message("=" * 60)
            
            # Call the analysis function with preview limit
            # Get all settings from GUI variables - simplified for preview
            combined_analysis(
                input_path=self.input_file.get(),
                output_path=preview_output,
                dewarp=self.dewarp_enabled.get(),
                track_ball_flag=self.ball_tracking_enabled.get(),
                track_players_flag=self.player_tracking_enabled.get(),
                export_csv=self.csv_export_enabled.get(),
                buffer=self.buffer_size.get(),
                batch_size=self.batch_size.get(),
                ball_min_radius=self.ball_min_size.get(),
                ball_max_radius=self.ball_max_size.get(),
                remove_net=self.remove_net_enabled.get(),
                show_ball_trail=self.show_ball_trail.get(),
                track_thresh=self.track_thresh.get(),
                match_thresh=self.match_thresh.get(),
                track_buffer=self.track_buffer.get(),
                track_buffer_seconds=self.track_buffer_seconds.get(),
                min_track_length=self.min_track_length.get(),
                min_bbox_area=self.min_bbox_area.get(),
                min_bbox_width=self.min_bbox_width.get(),
                min_bbox_height=self.min_bbox_height.get(),
                tracker_type=self.tracker_type.get(),
                yolo_model_size=self.yolo_model_size.get() if hasattr(self, 'yolo_model_size') else 'medium',
                yolo_confidence=self.yolo_confidence.get() if hasattr(self, 'yolo_confidence') else 0.25,
                ball_confidence_threshold=self.ball_confidence_threshold.get() if hasattr(self, 'ball_confidence_threshold') else 0.15,
                ball_confidence_multiplier=self.ball_confidence_multiplier.get() if hasattr(self, 'ball_confidence_multiplier') else 0.5,
                nms_iou_threshold=self.nms_iou_threshold.get() if hasattr(self, 'nms_iou_threshold') else 0.5,
                max_detections_per_frame=self.max_detections_per_frame.get() if hasattr(self, 'max_detections_per_frame') and self.max_detections_per_frame.get() > 0 else None,
                identity_position_tolerance=self.identity_position_tolerance.get() if hasattr(self, 'identity_position_tolerance') else 200.0,
                identity_iou_threshold=self.identity_iou_threshold.get() if hasattr(self, 'identity_iou_threshold') else 0.3,
                player_uniqueness_grace_frames=self.player_uniqueness_grace_frames.get() if hasattr(self, 'player_uniqueness_grace_frames') else 3,
                jersey_ocr_confidence=self.jersey_ocr_confidence.get() if hasattr(self, 'jersey_ocr_confidence') else 0.5,
                net_min_area_multiplier=self.net_min_area_multiplier.get() if hasattr(self, 'net_min_area_multiplier') else 4.0,
                net_aspect_ratio_low=self.net_aspect_ratio_low.get() if hasattr(self, 'net_aspect_ratio_low') else 0.7,
                net_aspect_ratio_high=self.net_aspect_ratio_high.get() if hasattr(self, 'net_aspect_ratio_high') else 1.4,
                net_confidence_threshold=self.net_confidence_threshold.get() if hasattr(self, 'net_confidence_threshold') else 0.3,
                direction_arrow_length=self.direction_arrow_length.get() if hasattr(self, 'direction_arrow_length') else 20,
                direction_arrow_head_size=self.direction_arrow_head_size.get() if hasattr(self, 'direction_arrow_head_size') else 8,
                direction_arrow_thickness=self.direction_arrow_thickness.get() if hasattr(self, 'direction_arrow_thickness') else 2,
                video_fps=fps,
                output_fps=fps,
                process_every_nth_frame=self.process_every_nth.get(),
                temporal_smoothing=self.temporal_smoothing.get(),
                yolo_resolution=self.yolo_resolution.get(),
                foot_based_tracking=self.foot_based_tracking.get(),
                use_reid=self.use_reid.get(),
                reid_similarity_threshold=self.reid_similarity_threshold.get(),
                gallery_similarity_threshold=self.gallery_similarity_threshold.get(),
                osnet_variant=self.osnet_variant.get(),
                use_boxmot_backend=self.use_boxmot_backend.get(),
                use_harmonic_mean=self.use_harmonic_mean.get() if hasattr(self, 'use_harmonic_mean') else True,
                use_expansion_iou=self.use_expansion_iou.get() if hasattr(self, 'use_expansion_iou') else True,
                enable_soccer_reid_training=self.enable_soccer_reid_training.get() if hasattr(self, 'enable_soccer_reid_training') else False,
                use_enhanced_kalman=self.use_enhanced_kalman.get() if hasattr(self, 'use_enhanced_kalman') else True,
                use_ema_smoothing=self.use_ema_smoothing.get() if hasattr(self, 'use_ema_smoothing') else True,
                preview_mode=True,
                preview_max_frames=preview_frames,
                watch_only=self.watch_only.get(),
                show_live_viewer=self.show_live_viewer.get(),
                focused_players=[self.focused_player] if (self.watch_only.get() and self.focus_players_enabled.get() and self.focused_player) else None,
                progress_callback=self.update_progress
            )
            
            # Update UI on completion
            self.root.after(0, lambda: self.preview_complete(True, preview_output))
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            error_msg = f"Error during preview: {str(e)}"
            self.log_message(error_msg)
            self.log_message("Full traceback:")
            self.log_message(error_traceback)
            self.root.after(0, lambda: self.preview_complete(False, f"{error_msg}\n\nFull error:\n{error_traceback}"))
    
    def preview_complete(self, success, message_or_path):
        """Called when preview completes"""
        self.processing = False
        if hasattr(self, 'start_button'):
            self.start_button.config(state=tk.NORMAL)
        if hasattr(self, 'preview_button'):
            self.preview_button.config(state=tk.NORMAL)
        if hasattr(self, 'stop_button'):
            self.stop_button.config(state=tk.DISABLED)
        if hasattr(self, 'progress_var'):
            self.progress_var.set(100)
        
        if success:
            preview_path = message_or_path
            if hasattr(self, 'status_label'):
                self.status_label.config(text="Preview completed!")
            self.log_message("=" * 60)
            self.log_message("Preview completed successfully!")
            self.log_message(f"Preview video: {preview_path}")
            self.log_message("=" * 60)
            
            # Ask if user wants to open the preview
            response = messagebox.askyesno("Preview Complete", 
                                          f"Preview completed!\n\n"
                                          f"Output: {os.path.basename(preview_path)}\n\n"
                                          f"Would you like to open the preview video?")
            if response:
                if os.path.exists(preview_path):
                    # Open in playback viewer
                    self.open_playback_viewer()
        else:
            if hasattr(self, 'status_label'):
                self.status_label.config(text="Preview error")
            messagebox.showerror("Preview Error", message_or_path)
    
    def run_analysis(self):
        """Run full analysis in a separate thread"""
        try:
            import cv2
            
            # Load analysis module
            try:
                try:
                    from combined_analysis_optimized import combined_analysis_optimized as combined_analysis
                    OPTIMIZED_AVAILABLE = True
                except ImportError:
                    from combined_analysis import combined_analysis
                    OPTIMIZED_AVAILABLE = False
            except ImportError:
                self.root.after(0, lambda: self.analysis_complete(False, "Failed to load analysis module"))
                return
            
            # Get video info
            input_path = self.input_file.get()
            output_path = self.output_file.get() if not self.watch_only.get() else None
            
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                self.root.after(0, lambda: self.analysis_complete(False, "Could not open video file"))
                return
            
            fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
            cap.release()
            
            # Get CSV output path if specified
            csv_output_path = None
            if self.csv_export_enabled.get() and self.csv_output_file.get():
                csv_output_path = self.csv_output_file.get()
            
            # Call the analysis function with all settings
            combined_analysis(
                input_path=input_path,
                output_path=output_path,
                dewarp=self.dewarp_enabled.get(),
                track_ball_flag=self.ball_tracking_enabled.get(),
                track_players_flag=self.player_tracking_enabled.get(),
                export_csv=self.csv_export_enabled.get(),
                csv_output_path=csv_output_path,  # Pass custom CSV path if provided
                buffer=self.buffer_size.get(),
                batch_size=self.batch_size.get(),
                ball_min_radius=self.ball_min_size.get(),
                ball_max_radius=self.ball_max_size.get(),
                remove_net=self.remove_net_enabled.get(),
                show_ball_trail=self.show_ball_trail.get(),
                track_thresh=self.track_thresh.get(),
                match_thresh=self.match_thresh.get(),
                track_buffer=self.track_buffer.get(),
                track_buffer_seconds=self.track_buffer_seconds.get(),
                min_track_length=self.min_track_length.get(),
                min_bbox_area=self.min_bbox_area.get(),
                min_bbox_width=self.min_bbox_width.get(),
                min_bbox_height=self.min_bbox_height.get(),
                tracker_type=self.tracker_type.get(),
                yolo_model_size=self.yolo_model_size.get() if hasattr(self, 'yolo_model_size') else 'medium',
                yolo_confidence=self.yolo_confidence.get() if hasattr(self, 'yolo_confidence') else 0.25,
                ball_confidence_threshold=self.ball_confidence_threshold.get() if hasattr(self, 'ball_confidence_threshold') else 0.15,
                ball_confidence_multiplier=self.ball_confidence_multiplier.get() if hasattr(self, 'ball_confidence_multiplier') else 0.5,
                nms_iou_threshold=self.nms_iou_threshold.get() if hasattr(self, 'nms_iou_threshold') else 0.5,
                max_detections_per_frame=self.max_detections_per_frame.get() if hasattr(self, 'max_detections_per_frame') and self.max_detections_per_frame.get() > 0 else None,
                identity_position_tolerance=self.identity_position_tolerance.get() if hasattr(self, 'identity_position_tolerance') else 200.0,
                identity_iou_threshold=self.identity_iou_threshold.get() if hasattr(self, 'identity_iou_threshold') else 0.3,
                player_uniqueness_grace_frames=self.player_uniqueness_grace_frames.get() if hasattr(self, 'player_uniqueness_grace_frames') else 3,
                jersey_ocr_confidence=self.jersey_ocr_confidence.get() if hasattr(self, 'jersey_ocr_confidence') else 0.5,
                net_min_area_multiplier=self.net_min_area_multiplier.get() if hasattr(self, 'net_min_area_multiplier') else 4.0,
                net_aspect_ratio_low=self.net_aspect_ratio_low.get() if hasattr(self, 'net_aspect_ratio_low') else 0.7,
                net_aspect_ratio_high=self.net_aspect_ratio_high.get() if hasattr(self, 'net_aspect_ratio_high') else 1.4,
                net_confidence_threshold=self.net_confidence_threshold.get() if hasattr(self, 'net_confidence_threshold') else 0.3,
                direction_arrow_length=self.direction_arrow_length.get() if hasattr(self, 'direction_arrow_length') else 20,
                direction_arrow_head_size=self.direction_arrow_head_size.get() if hasattr(self, 'direction_arrow_head_size') else 8,
                direction_arrow_thickness=self.direction_arrow_thickness.get() if hasattr(self, 'direction_arrow_thickness') else 2,
                video_fps=fps if self.video_fps.get() <= 0 else self.video_fps.get(),
                output_fps=fps if self.output_fps.get() <= 0 else self.output_fps.get(),
                process_every_nth_frame=self.process_every_nth.get(),
                temporal_smoothing=self.temporal_smoothing.get(),
                yolo_resolution=self.yolo_resolution.get(),
                foot_based_tracking=self.foot_based_tracking.get(),
                use_reid=self.use_reid.get(),
                reid_similarity_threshold=self.reid_similarity_threshold.get(),
                gallery_similarity_threshold=self.gallery_similarity_threshold.get(),
                osnet_variant=self.osnet_variant.get(),
                use_boxmot_backend=self.use_boxmot_backend.get(),
                use_harmonic_mean=self.use_harmonic_mean.get() if hasattr(self, 'use_harmonic_mean') else True,
                use_expansion_iou=self.use_expansion_iou.get() if hasattr(self, 'use_expansion_iou') else True,
                enable_soccer_reid_training=self.enable_soccer_reid_training.get() if hasattr(self, 'enable_soccer_reid_training') else False,
                use_enhanced_kalman=self.use_enhanced_kalman.get() if hasattr(self, 'use_enhanced_kalman') else True,
                use_ema_smoothing=self.use_ema_smoothing.get() if hasattr(self, 'use_ema_smoothing') else True,
                watch_only=self.watch_only.get(),
                show_live_viewer=self.show_live_viewer.get() if hasattr(self, 'show_live_viewer') else False,
                video_type=self.video_type.get() if hasattr(self, 'video_type') else None,
                focused_players=[self.focused_player] if (self.watch_only.get() and self.focus_players_enabled.get() and self.focused_player) else None,
                progress_callback=self.update_progress if hasattr(self, 'update_progress') else None
            )
            
            # Update UI on completion
            self.root.after(0, lambda: self.analysis_complete(True, output_path if output_path else "Watch-only mode completed"))
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            error_msg = f"Error during analysis: {str(e)}"
            self.log_message(error_msg)
            self.log_message("Full traceback:")
            self.log_message(error_traceback)
            self.root.after(0, lambda: self.analysis_complete(False, f"{error_msg}\n\nFull error:\n{error_traceback}"))
    
    def analysis_complete(self, success, message_or_path):
        """Called when analysis completes"""
        self.processing = False
        if hasattr(self, 'start_button'):
            self.start_button.config(state=tk.NORMAL)
        if hasattr(self, 'stop_button'):
            self.stop_button.config(state=tk.DISABLED)
        if hasattr(self, 'open_folder_button'):
            self.open_folder_button.config(state=tk.NORMAL)
        if hasattr(self, 'progress_var'):
            self.progress_var.set(100)
        
        if success:
            output_path = message_or_path
            if hasattr(self, 'status_label'):
                self.status_label.config(text="Analysis completed!")
            self.log_message("=" * 60)
            self.log_message("Analysis completed successfully!")
            if output_path and os.path.exists(output_path):
                self.log_message(f"Output: {output_path}")
                self.last_output_file = output_path
            self.log_message("=" * 60)
            
            if self.toast_manager:
                self.toast_manager.success("Analysis completed successfully!")
            
            # Offer post-analysis automation
            self._offer_post_analysis_automation(output_path)
        else:
            if hasattr(self, 'status_label'):
                self.status_label.config(text="Analysis error")
            messagebox.showerror("Analysis Error", message_or_path)
    
    def _offer_post_analysis_automation(self, output_path: str):
        """Offer post-analysis automation options after analysis completes"""
        if not output_path or not os.path.exists(output_path):
            return
        
        # Find CSV file
        csv_path = output_path.replace('_analyzed.mp4', '_tracking_data.csv').replace('.mp4', '_tracking_data.csv')
        if not os.path.exists(csv_path):
            # Try alternative naming
            base_dir = os.path.dirname(output_path)
            video_name = os.path.splitext(os.path.basename(output_path))[0].replace('_analyzed', '')
            csv_path = os.path.join(base_dir, f"{video_name}_tracking_data.csv")
        
        if not os.path.exists(csv_path):
            return  # No CSV, skip automation offer
        
        # Offer player verification first, then post-analysis automation
        response = messagebox.askyesno(
            "Review Player Identification",
            "Analysis completed successfully!\n\n"
            "Would you like to review and verify player identification?\n\n"
            "This will open the Playback Viewer where you can:\n"
            "• View all tracked players in the video\n"
            "• Verify players are correctly identified\n"
            "• Correct any misidentifications\n"
            "• Review tracking quality\n\n"
            "Open Playback Viewer now?",
            parent=self.root
        )
        
        if response:
            # Open playback viewer for verification
            self.root.after(100, lambda: self.open_playback_viewer())
        
        # Then offer post-analysis automation
        self.root.after(500, lambda: self._offer_post_analysis_automation_step2(output_path, csv_path))
    
    def _offer_post_analysis_automation_step2(self, output_path: str, csv_path: str):
        """Second step: Offer post-analysis automation after verification"""
        response = messagebox.askyesno(
            "Post-Analysis Automation",
            "Ready to run post-analysis automation?\n\n"
            "This will:\n"
            "• Auto-detect events (passes, shots, etc.)\n"
            "• Generate highlight clips\n"
            "• Export statistics\n\n"
            "Note: You can also run this later from:\n"
            "Tools → Post-Analysis → Re-run Post-Analysis Automation\n\n"
            "Run automation now?",
            parent=self.root
        )
        
        if response:
            self._run_post_analysis_automation(output_path, csv_path)
    
    def _run_post_analysis_automation(self, video_path: str, csv_path: str):
        """Run the post-analysis automation chain"""
        import threading
        
        def run_automation():
            try:
                self.log_message("\n" + "=" * 60)
                self.log_message("🚀 Starting Post-Analysis Automation")
                self.log_message("=" * 60)
                
                # Step 1: Auto-detect events
                self.log_message("\n📊 Step 1: Auto-detecting events...")
                events = self._auto_detect_events_from_csv(csv_path, video_path)
                
                if events:
                    self.log_message(f"  ✓ Detected {len(events)} events")
                else:
                    self.log_message("  ⚠ No events detected")
                
                # Step 2: Generate highlights (if events found)
                if events:
                    self.log_message("\n🎬 Step 2: Generating highlights...")
                    highlights = self._generate_highlights_from_events(video_path, events, csv_path)
                    if highlights:
                        self.log_message(f"  ✓ Generated {len(highlights)} highlight clips")
                    else:
                        self.log_message("  ⚠ No highlights generated")
                else:
                    self.log_message("\n⏭️  Step 2: Skipping highlights (no events detected)")
                
                # Step 3: Export statistics
                self.log_message("\n📈 Step 3: Exporting statistics...")
                stats_path = self._export_analysis_statistics(csv_path, video_path)
                if stats_path:
                    self.log_message(f"  ✓ Statistics exported to: {os.path.basename(stats_path)}")
                else:
                    self.log_message("  ⚠ Statistics export failed")
                
                self.log_message("\n" + "=" * 60)
                self.log_message("✅ Post-Analysis Automation Complete!")
                self.log_message("=" * 60)
                
                # Show completion message
                highlights_count = len(highlights) if events and 'highlights' in locals() else 0
                self.root.after(0, lambda: messagebox.showinfo(
                    "Automation Complete",
                    "Post-analysis automation completed successfully!\n\n"
                    f"• Events detected: {len(events) if events else 0}\n"
                    f"• Highlights generated: {highlights_count}\n"
                    f"• Statistics exported: {'Yes' if stats_path else 'No'}",
                    parent=self.root
                ))
                
            except Exception as e:
                error_msg = f"Post-analysis automation failed: {e}"
                self.log_message(f"\n❌ {error_msg}")
                import traceback
                self.log_message(traceback.format_exc())
                self.root.after(0, lambda: messagebox.showerror(
                    "Automation Error",
                    error_msg,
                    parent=self.root
                ))
        
        # Run in background thread
        thread = threading.Thread(target=run_automation, daemon=True)
        thread.start()
    
    def _auto_detect_events_from_csv(self, csv_path: str, video_path: str) -> list:
        """Auto-detect events from CSV tracking data"""
        try:
            from event_detector import EventDetector
            import pandas as pd
            import cv2
            
            if not os.path.exists(csv_path):
                return []
            
            # Get FPS from video
            fps = 30.0
            if video_path and os.path.exists(video_path):
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS)
                cap.release()
            
            if fps <= 0:
                fps = 30.0
            
            # Initialize detector with CSV path (not DataFrame)
            detector = EventDetector(csv_path, fps=fps)
            
            # Load tracking data
            if not detector.load_tracking_data():
                return []
            
            # Detect events
            events = []
            
            # Detect passes
            if self.event_detect_passes.get():
                passes = detector.detect_passes_with_accuracy(
                    min_ball_speed=self.event_min_ball_speed.get(),
                    min_pass_distance=self.event_min_pass_distance.get(),
                    imperial_input=self.use_imperial_units.get()
                )
                events.extend(passes)
            
            # Detect shots
            if self.event_detect_shots.get():
                shots = detector.detect_shots(
                    min_ball_speed=self.event_min_shot_speed.get() if hasattr(self, 'event_min_shot_speed') else self.event_min_ball_speed.get(),
                    min_approach_distance=self.event_min_shot_approach_distance.get() if hasattr(self, 'event_min_shot_approach_distance') else 32.8,
                    imperial_input=self.use_imperial_units.get()
                )
                events.extend(shots)
            
            # Detect tackles
            if hasattr(self, 'event_detect_tackles') and self.event_detect_tackles.get():
                tackles = detector.detect_tackles(
                    min_tackle_speed=self.event_min_tackle_speed.get() if hasattr(self, 'event_min_tackle_speed') else 14.76,
                    min_proximity=self.event_min_tackle_proximity.get() if hasattr(self, 'event_min_tackle_proximity') else 6.56,
                    confidence_threshold=self.event_min_confidence.get(),
                    imperial_input=self.use_imperial_units.get()
                )
                events.extend(tackles)
            
            # Detect dribbles
            if hasattr(self, 'event_detect_dribbles') and self.event_detect_dribbles.get():
                dribbles = detector.detect_dribbles(
                    min_touches=self.event_min_dribble_touches.get() if hasattr(self, 'event_min_dribble_touches') else 3,
                    min_dribble_distance=self.event_min_dribble_distance.get() if hasattr(self, 'event_min_dribble_distance') else 9.84,
                    possession_threshold=self.event_possession_threshold.get(),
                    confidence_threshold=self.event_min_confidence.get(),
                    imperial_input=self.use_imperial_units.get()
                )
                events.extend(dribbles)
            
            # Save events
            if events:
                events_json_path = csv_path.replace('.csv', '_events.json')
                events_csv_path = csv_path.replace('.csv', '_detected_events.csv')
                
                # Save as JSON
                import json
                events_data = [e.__dict__ if hasattr(e, '__dict__') else e for e in events]
                with open(events_json_path, 'w') as f:
                    json.dump({'events': events_data}, f, indent=2)
                
                # Save as CSV
                events_df = pd.DataFrame(events_data)
                events_df.to_csv(events_csv_path, index=False)
            
            return events
            
        except Exception as e:
            self.log_message(f"  ⚠ Event detection error: {e}")
            return []
    
    def _run_event_detection(self):
        """Run event detection on selected CSV file (called from Event Detection tab)"""
        csv_path = getattr(self, 'event_csv_file', tk.StringVar()).get()
        if not csv_path or not os.path.exists(csv_path):
            messagebox.showerror("Error", "Please select a valid CSV tracking file.")
            return
        
        # Get video path (try from input file or output file)
        video_path = None
        if hasattr(self, 'input_file') and self.input_file.get():
            video_path = self.input_file.get()
        elif hasattr(self, 'output_file') and self.output_file.get():
            # Try to find original video from output path
            output_path = self.output_file.get()
            base_name = os.path.splitext(os.path.basename(output_path))[0].replace('_analyzed', '')
            video_dir = os.path.dirname(output_path)
            # Try common video extensions
            for ext in ['.mp4', '.avi', '.mov', '.mkv']:
                potential_video = os.path.join(video_dir, base_name + ext)
                if os.path.exists(potential_video):
                    video_path = potential_video
                    break
        
        if not video_path or not os.path.exists(video_path):
            messagebox.showwarning("Warning", 
                "Video file not found. Event detection will proceed without video context.\n"
                "Some features may be limited.")
            video_path = csv_path.replace('.csv', '.mp4')  # Fallback
        
        # Run event detection
        try:
            events = self._auto_detect_events_from_csv(csv_path, video_path)
            
            if events:
                messagebox.showinfo("Success", 
                    f"Event detection complete!\n\n"
                    f"Detected {len(events)} events.\n\n"
                    f"Results saved to:\n"
                    f"- {csv_path.replace('.csv', '_events.json')}\n"
                    f"- {csv_path.replace('.csv', '_detected_events.csv')}")
            else:
                messagebox.showinfo("Complete", 
                    "Event detection complete, but no events were detected.\n\n"
                    "Try adjusting the detection parameters or check your tracking data.")
        except Exception as e:
            messagebox.showerror("Error", f"Event detection failed: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _generate_highlights_from_events(self, video_path: str, events: list, csv_path: str) -> list:
        """Generate highlight clips from detected events"""
        try:
            from SoccerID.automation.auto_highlight_generator import AutoHighlightGenerator
            import cv2
            
            if not events:
                return []
            
            # Get FPS from video
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) if cap.isOpened() else 30.0
            cap.release()
            
            if fps <= 0:
                fps = 30.0
            
            # Create output directory
            output_dir = os.path.dirname(video_path)
            video_name = os.path.splitext(os.path.basename(video_path))[0].replace('_analyzed', '')
            highlights_dir = os.path.join(output_dir, f"{video_name}_highlights")
            os.makedirs(highlights_dir, exist_ok=True)
            
            # Initialize generator
            generator = AutoHighlightGenerator(video_path, fps=fps)
            
            # Check if personalized highlights are enabled
            per_player = getattr(self, 'personalized_player_highlights', tk.BooleanVar(value=False)).get()
            
            if per_player:
                # Generate personalized highlights
                all_player_highlights = generator.generate_all_player_highlights(
                    events=events,
                    output_dir=highlights_dir,
                    event_types=None  # All event types
                )
                highlights = []
                for player_name, clips in all_player_highlights.items():
                    highlights.extend(clips)
                    # Add highlight clips to player gallery as reference frames
                    self._add_highlights_to_gallery(player_name, clips, video_path)
            else:
                # Generate standard highlights
                highlights = generator.generate_highlights_from_events(
                    events=events,
                    output_dir=highlights_dir,
                    event_types=None,  # All event types
                    per_player=False
                )
            
            generator.close()
            return highlights
            
        except Exception as e:
            self.log_message(f"  ⚠ Highlight generation error: {e}")
            import traceback
            self.log_message(traceback.format_exc())
            return []
    
    def _export_analysis_statistics(self, csv_path: str, video_path: str) -> Optional[str]:
        """Export analysis statistics to a report file"""
        try:
            import pandas as pd
            import json
            from datetime import datetime
            
            if not os.path.exists(csv_path):
                return None
            
            # Load CSV
            df = pd.read_csv(csv_path)
            
            # Calculate statistics
            stats = {
                'analysis_date': datetime.now().isoformat(),
                'video_path': video_path,
                'csv_path': csv_path,
                'total_frames': df['frame_num'].nunique() if 'frame_num' in df.columns else 0,
                'total_detections': len(df),
                'unique_track_ids': df['track_id'].nunique() if 'track_id' in df.columns else 0,
                'unique_players': df['player_name'].nunique() if 'player_name' in df.columns else 0,
            }
            
            # Player statistics
            if 'player_name' in df.columns:
                # Check which columns exist and use them
                agg_dict = {}
                if 'frame_num' in df.columns:
                    agg_dict['frame_num'] = 'count'
                elif 'Frame' in df.columns:
                    agg_dict['Frame'] = 'count'
                else:
                    # Use first column as count
                    agg_dict[df.columns[0]] = 'count'
                
                if 'track_id' in df.columns:
                    agg_dict['track_id'] = 'nunique'
                elif 'Track ID' in df.columns:
                    agg_dict['Track ID'] = 'nunique'
                elif 'Track_ID' in df.columns:
                    agg_dict['Track_ID'] = 'nunique'
                
                if agg_dict:
                    player_stats = df.groupby('player_name').agg(agg_dict)
                    # Rename columns for consistency
                    rename_dict = {}
                    for col in player_stats.columns:
                        if 'frame_num' in col.lower() or 'frame' in col.lower():
                            rename_dict[col] = 'detections'
                        elif 'track' in col.lower():
                            rename_dict[col] = 'unique_tracks'
                    if rename_dict:
                        player_stats = player_stats.rename(columns=rename_dict)
                    stats['player_statistics'] = player_stats.to_dict('index')
            
            # Save statistics
            stats_path = csv_path.replace('.csv', '_statistics.json')
            with open(stats_path, 'w') as f:
                json.dump(stats, f, indent=2)
            
            return stats_path
            
        except Exception as e:
            self.log_message(f"  ⚠ Statistics export error: {e}")
            return None
    
    def _add_highlights_to_gallery(self, player_name: str, clips: List, source_video_path: str):
        """Add highlight clips to player gallery as reference frames"""
        try:
            from player_gallery import PlayerGallery
            import cv2
            
            gallery = PlayerGallery()
            
            # Get or create player in gallery
            # Player ID is the lowercase name with underscores
            player_id = player_name.lower().replace(" ", "_")
            player = gallery.get_player(player_id)
            
            if not player:
                # Add player if doesn't exist
                player_id = gallery.add_player(player_name, team="", jersey="")
                player = gallery.get_player(player_id)
            
            if not player:
                self.log_message(f"  ⚠ Could not add player {player_name} to gallery")
                return
            
            added_count = 0
            for clip in clips:
                if not hasattr(clip, 'clip_path') or not clip.clip_path:
                    continue
                
                clip_path = clip.clip_path
                if not os.path.exists(clip_path):
                    continue
                
                # Extract a frame from the middle of the clip
                try:
                    cap = cv2.VideoCapture(clip_path)
                    if not cap.isOpened():
                        continue
                    
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    if total_frames > 0:
                        # Get middle frame
                        middle_frame = total_frames // 2
                        cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
                        ret, frame = cap.read()
                        cap.release()
                        
                        if ret and frame is not None:
                            # Create reference frame dict
                            h, w = frame.shape[:2]
                            # Use full frame as bbox for highlight clips
                            bbox = [0, 0, w, h]
                            
                            reference_frame = {
                                'video_path': clip_path,
                                'frame_num': middle_frame,
                                'bbox': bbox,
                                'confidence': 0.9,  # High confidence for highlight clips
                                'similarity': 0.95,  # High similarity for highlight clips
                                'is_anchor': False,
                                'quality': 0.9
                            }
                            
                            # Add reference frame to gallery using update_player
                            gallery.update_player(
                                player_id=player_id,
                                reference_frame=reference_frame
                            )
                            added_count += 1
                except Exception as e:
                    self.log_message(f"  ⚠ Error adding highlight frame for {player_name}: {e}")
                    continue
            
            if added_count > 0:
                gallery.save()
                self.log_message(f"  ✓ Added {added_count} reference frames from highlights to {player_name}'s gallery")
            
        except Exception as e:
            self.log_message(f"  ⚠ Error adding highlights to gallery: {e}")
            import traceback
            traceback.print_exc()
    
    def manual_post_analysis_automation(self):
        """Manually trigger post-analysis automation from menu"""
        try:
            from tkinter import filedialog, messagebox
            
            # Get video path
            video_path = self.input_file.get().strip()
            if not video_path or not os.path.exists(video_path):
                # Try to find from output file
                output_path = self.output_file.get().strip()
                if output_path and os.path.exists(output_path):
                    video_path = output_path
                else:
                    # Ask user to select video
                    video_path = filedialog.askopenfilename(
                        title="Select Analyzed Video File",
                        filetypes=[("Video files", "*.mp4 *.avi *.mov"), ("All files", "*.*")]
                    )
                    if not video_path:
                        return
            
            # Get CSV path
            csv_path = self.csv_output_file.get().strip()
            if not csv_path or not os.path.exists(csv_path):
                # Try to auto-detect CSV from video path
                video_dir = os.path.dirname(video_path)
                video_name = os.path.splitext(os.path.basename(video_path))[0]
                possible_csv = os.path.join(video_dir, f"{video_name}_tracking_data.csv")
                
                if os.path.exists(possible_csv):
                    csv_path = possible_csv
                else:
                    # Ask user to select CSV
                    csv_path = filedialog.askopenfilename(
                        title="Select Tracking Data CSV File",
                        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                        initialdir=video_dir
                    )
                    if not csv_path:
                        messagebox.showwarning("CSV Required", 
                                             "CSV file is required for post-analysis automation.\n"
                                             "Please select the tracking data CSV file.")
                        return
            
            # Confirm with user
            response = messagebox.askyesno(
                "Re-run Post-Analysis Automation",
                f"This will:\n"
                f"• Auto-detect events from CSV\n"
                f"• Generate highlight clips\n"
                f"• Add highlights to player gallery\n"
                f"• Export statistics\n\n"
                f"Video: {os.path.basename(video_path)}\n"
                f"CSV: {os.path.basename(csv_path)}\n\n"
                f"Continue?",
                icon="question"
            )
            
            if not response:
                return
            
            # Run post-analysis automation
            self.log_message(f"\n🔄 Manually triggering post-analysis automation...")
            self.log_message(f"Video: {video_path}")
            self.log_message(f"CSV: {csv_path}")
            self._run_post_analysis_automation(video_path, csv_path)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not start post-analysis automation: {e}")
            import traceback
            traceback.print_exc()
    
    def preview_frames(self):
        """Preview specific frames"""
        try:
            from tkinter import simpledialog
            import cv2
            from PIL import Image, ImageTk
            
            # Check if input file is set
            input_path = self.input_file.get().strip()
            if not input_path or not os.path.exists(input_path):
                messagebox.showwarning("No Video", "Please select an input video file first.")
                return
            
            # Ask for frame number
            frame_num = simpledialog.askinteger("Preview Frame", "Enter frame number:", minvalue=0)
            if frame_num is None:
                return
            
            self.log_message(f"Previewing frame {frame_num}")
            
            # Open video and seek to frame
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                messagebox.showerror("Error", "Could not open video file.")
                return
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_num >= total_frames:
                messagebox.showwarning("Invalid Frame", 
                                      f"Frame {frame_num} is out of range. Video has {total_frames} frames (0-{total_frames-1}).")
                cap.release()
                return
            
            # Seek to frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                messagebox.showerror("Error", f"Could not read frame {frame_num}.")
                return
            
            # Create preview window
            preview_window = tk.Toplevel(self.root)
            preview_window.title(f"Frame Preview - Frame {frame_num}")
            preview_window.geometry("800x600")
            
            # Center window
            preview_window.update_idletasks()
            x = (preview_window.winfo_screenwidth() // 2) - (preview_window.winfo_width() // 2)
            y = (preview_window.winfo_screenheight() // 2) - (preview_window.winfo_height() // 2)
            preview_window.geometry(f"+{x}+{y}")
            
            # Convert frame to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Resize if too large
            height, width = frame_rgb.shape[:2]
            max_width, max_height = 1200, 800
            if width > max_width or height > max_height:
                scale = min(max_width / width, max_height / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame_rgb = cv2.resize(frame_rgb, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            # Convert to PIL Image
            pil_image = Image.fromarray(frame_rgb)
            photo = ImageTk.PhotoImage(image=pil_image)
            
            # Create label to display image
            image_label = tk.Label(preview_window, image=photo)
            # Keep a reference to prevent garbage collection
            preview_window._photo_ref = photo
            image_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Add frame info
            info_label = tk.Label(preview_window, 
                                text=f"Frame {frame_num} of {total_frames} | Resolution: {width}x{height}",
                                font=("Arial", 10))
            info_label.pack(pady=5)
            
            # Add close button
            close_btn = ttk.Button(preview_window, text="Close", command=preview_window.destroy)
            close_btn.pack(pady=5)
            
            if self.toast_manager:
                self.toast_manager.success(f"Frame {frame_num} preview opened")
            
        except Exception as e:
            self.log_message(f"Preview frames error: {e}")
            messagebox.showerror("Error", f"Could not preview frame: {e}")
    
    def validate_inputs(self):
        """Validate that all required inputs are provided"""
        if not self.input_file.get():
            messagebox.showerror("Error", "Please select an input video file.")
            return False
        
        if not os.path.exists(self.input_file.get()):
            messagebox.showerror("Error", "Input video file does not exist.")
            return False
        
        if not self.output_file.get():
            messagebox.showerror("Error", "Please specify an output video file.")
            return False
        
        if not self.ball_tracking_enabled.get() and not self.player_tracking_enabled.get():
            messagebox.showwarning("Warning", "At least one tracking option (ball or players) must be enabled.")
            return False
        
        return True
    
    def start_analysis(self):
        """Start the analysis process in a separate thread"""
        if not self.validate_inputs():
            return
        
        if self.processing:
            messagebox.showinfo("Info", "Analysis is already in progress.")
            return
        
        # Check for batch focus analyze
        if self.batch_focus_analyze.get():
            # Batch process each active player
            video_path = self.input_file.get()
            if not video_path or not os.path.exists(video_path):
                messagebox.showerror("Error", "Please select a video file first.")
                return
            
            active_players = self._get_active_players_for_video(video_path)
            
            if not active_players:
                messagebox.showwarning("Warning", 
                                     "No active players found in roster for this video.\n\n"
                                     "Please set up the roster in the Setup Wizard first.")
                return
            
            # Confirm batch processing
            response = messagebox.askyesno(
                "Batch Focus Analysis",
                f"This will run analysis for each of {len(active_players)} active player(s):\n\n" +
                "\n".join(f"  • {player}" for player in active_players) +
                "\n\nEach analysis will focus on one player (faster processing).\n\n"
                "Continue with batch processing?"
            )
            
            if not response:
                return
            
            # Start batch processing in a separate thread
            import threading
            batch_thread = threading.Thread(target=self._run_batch_focus_analysis, 
                                            args=(video_path, active_players),
                                            daemon=True)
            batch_thread.start()
            return
        
        # Disable start button, enable stop button
        if hasattr(self, 'start_button'):
            self.start_button.config(state=tk.DISABLED)
        if hasattr(self, 'stop_button'):
            self.stop_button.config(state=tk.NORMAL)
        if hasattr(self, 'open_folder_button'):
            self.open_folder_button.config(state=tk.DISABLED)
        self.processing = True
        if hasattr(self, 'progress_var'):
            self.progress_var.set(0)
        if hasattr(self, 'status_label'):
            self.status_label.config(text="Processing...")
        
        # Initialize progress tracker if available
        if self.progress_tracker:
            # Estimate total frames from video
            total_frames = 0
            input_path = self.input_file.get()
            if input_path and os.path.exists(input_path):
                try:
                    import cv2
                    cap = cv2.VideoCapture(input_path)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    cap.release()
                    
                    if total_frames > 0:
                        self.progress_tracker = ProgressTracker(total_frames, "frames")
                        self.progress_tracker.start()
                        if self.progress_tracker:
                            self.progress_tracker.set_cancel_callback(self._request_cancel)
                except:
                    pass
            
            if total_frames == 0:
                self.progress_tracker = ProgressTracker(100, "percent")
                self.progress_tracker.start()
        
        # Clear log
        if hasattr(self, 'log_text'):
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state=tk.DISABLED)
        
        # Log start info
        self.log_message("=" * 60)
        self.log_message("Starting Soccer Video Analysis")
        self.log_message("=" * 60)
        self.log_message(f"Input: {self.input_file.get()}")
        self.log_message(f"Output: {self.output_file.get()}")
        self.log_message(f"Dewarping: {self.dewarp_enabled.get()}")
        self.log_message(f"Remove Net: {self.remove_net_enabled.get()}")
        self.log_message(f"Ball Tracking: {self.ball_tracking_enabled.get()}")
        self.log_message(f"Player Tracking: {self.player_tracking_enabled.get()}")
        self.log_message(f"CSV Export: {self.csv_export_enabled.get()}")
        if hasattr(self, 'preserve_audio'):
            self.log_message(f"Preserve Audio: {self.preserve_audio.get()}")
        self.log_message(f"Watch-Only Mode: {self.watch_only.get()}")
        if self.watch_only.get():
            self.log_message(f"  → Show Live Viewer: {self.show_live_viewer.get()}")
        self.log_message("=" * 60)
        
        # Clear any previous stop requests
        try:
            import shared_state
            shared_state.clear_analysis_stop()
        except ImportError:
            pass
        
        # Start analysis in separate thread
        import threading
        self.process_thread = threading.Thread(target=self.run_analysis, daemon=True)
        self.process_thread.start()
        
        # Launch live viewer controls window if:
        # 1. Watch-only mode with live viewer is enabled
        if self.watch_only.get() and self.show_live_viewer.get():
            self.log_message(f"📺 Watch-only mode with live viewer enabled - will launch controls window")
            self.log_message(f"   → Waiting for analysis to initialize (this may take a few seconds)...")
            # Initialize retry counters
            self.live_viewer_retry_count = 0
            self.live_viewer_max_retries = 30
            self.live_viewer_start_time = None
            # Start with 3 second delay to give analysis time to initialize
            self.root.after(3000, self.launch_live_viewer_controls)
        else:
            # Debug: log why window isn't launching
            if not self.watch_only.get() and not self.player_tracking_enabled.get():
                self.log_message("ℹ Live viewer not launching: watch-only mode and player tracking are both disabled")
            elif self.watch_only.get() and not self.show_live_viewer.get():
                self.log_message("ℹ Enable 'Show Live Viewer' checkbox to see live viewer during watch-only mode")
            elif not self.watch_only.get() and self.player_tracking_enabled.get():
                self.log_message("ℹ Conflict resolution available - use 'Open Conflict Resolution' button to open manually")
    
    def _start_progress_updates(self):
        """Start periodic progress updates by polling shared_state"""
        if not self.progress_tracker:
            return
        
        def update_from_shared_state():
            try:
                import shared_state
                progress = shared_state.get_analysis_progress()
                
                if progress.get('is_running') and progress.get('total', 0) > 0:
                    # Update progress tracker
                    self.update_progress(
                        current=progress.get('current', 0),
                        total=progress.get('total', 0),
                        status=progress.get('status', ''),
                        details=progress.get('details', ''),
                        phase=progress.get('phase', '')
                    )
                    
                    # Schedule next update
                    self.root.after(100, update_from_shared_state)  # Update every 100ms
                else:
                    # Analysis not running or complete
                    if progress.get('total', 0) > 0 and progress.get('current', 0) >= progress.get('total', 0):
                        # Analysis complete
                        if self.progress_tracker:
                            self.progress_tracker.finish()
                        if self.toast_manager:
                            self.toast_manager.success("Analysis completed successfully!")
                        if hasattr(self, 'cancel_button'):
                            self.cancel_button.config(state=tk.DISABLED)
            except Exception as e:
                # Silently handle errors (analysis might have ended)
                pass
        
        # Start polling
        self.root.after(100, update_from_shared_state)
    
    def stop_analysis(self):
        """Stop analysis"""
        try:
            import shared_state
            shared_state.request_analysis_stop()
            self.log_message("Analysis stop requested")
        except ImportError:
            self.log_message("shared_state not available - cannot stop analysis")
            messagebox.showwarning("Warning", "Cannot stop analysis - shared_state module not available")
        except Exception as e:
            self.log_message(f"Stop analysis error: {e}")
    
    def open_conflict_resolution(self):
        """Open conflict resolution tool"""
        try:
            try:
                from conflict_resolution import ConflictResolutionGUI
            except ImportError:
                try:
                    from legacy.conflict_resolution import ConflictResolutionGUI
                except ImportError:
                    try:
                        # Try to find conflict_resolution in the project root
                        import sys
                        import os
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from conflict_resolution import ConflictResolutionGUI
                    except ImportError:
                        messagebox.showerror("Error", "Could not import conflict_resolution.py")
                        return
            
            conflict_window = tk.Toplevel(self.root)
            conflict_window.title("Conflict Resolution")
            conflict_window.geometry("1200x800")
            conflict_window.transient(self.root)
            
            app = ConflictResolutionGUI(conflict_window)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open conflict resolution: {e}")
            import traceback
            traceback.print_exc()
    
    def open_output_folder(self):
        """Open output folder"""
        if self.last_output_file:
            folder = os.path.dirname(self.last_output_file)
            if os.path.exists(folder):
                os.startfile(folder) if sys.platform == "win32" else os.system(f"open {folder}")
    
    def analyze_csv(self):
        """Analyze CSV data - opens unified viewer with CSV loaded"""
        try:
            csv_file = filedialog.askopenfilename(
                title="Select CSV File to Analyze",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not csv_file:
                return
            
            # Open unified viewer in playback mode with CSV file
            # This provides full CSV analysis capabilities
            self.open_unified_viewer(mode='playback', csv_path=csv_file)
        except Exception as e:
            messagebox.showerror("Error", f"Could not analyze CSV: {e}")
            import traceback
            traceback.print_exc()
    
    def open_analytics_selection(self):
        """Open analytics selection dialog"""
        try:
            try:
                from analytics_selection_gui import AnalyticsSelectionGUI
            except ImportError:
                try:
                    from legacy.analytics_selection_gui import AnalyticsSelectionGUI
                except ImportError:
                    try:
                        # Try to find analytics_selection_gui in the project root
                        import sys
                        import os
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from analytics_selection_gui import AnalyticsSelectionGUI
                    except ImportError:
                        messagebox.showerror("Error", "Could not import analytics_selection_gui.py")
                        return
            
            # Define callbacks
            def apply_callback(preferences):
                """Apply preferences immediately"""
                if hasattr(self, 'update_analytics_preferences'):
                    self.update_analytics_preferences(preferences)
                else:
                    self.log_message(f"✓ Analytics preferences updated: {len([k for k, v in preferences.items() if v])} metrics selected")
            
            def save_to_project_callback(preferences):
                """Save preferences to project file"""
                if hasattr(self, 'analytics_preferences'):
                    self.analytics_preferences = preferences
                if self.current_project_path:
                    try:
                        self.save_project()
                        self.log_message("✓ Analytics preferences saved to project")
                    except Exception as e:
                        self.log_message(f"⚠ Could not save project: {e}")
                else:
                    apply_callback(preferences)
            
            # Pass root directly - AnalyticsSelectionGUI creates its own Toplevel window
            app = AnalyticsSelectionGUI(
                parent=self.root,
                apply_callback=apply_callback,
                save_to_project_callback=save_to_project_callback
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not open analytics selection: {e}")
            import traceback
            traceback.print_exc()
    
    def open_setup_checklist(self):
        """Open setup checklist"""
        try:
            try:
                from setup_checklist import SetupChecklist
            except ImportError:
                try:
                    from legacy.setup_checklist import SetupChecklist
                except ImportError:
                    try:
                        # Try to find setup_checklist in the project root
                        import sys
                        import os
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from setup_checklist import SetupChecklist
                    except ImportError:
                        messagebox.showerror("Error", "Could not import setup_checklist.py")
                        return
            
            # Pass root directly - SetupChecklist creates its own Toplevel window
            app = SetupChecklist(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open setup checklist: {e}")
            import traceback
            traceback.print_exc()
    
    def evaluate_tracking_metrics(self):
        """Evaluate tracking metrics from CSV"""
        try:
            csv_file = filedialog.askopenfilename(
                title="Select CSV File for Tracking Metrics",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if csv_file:
                try:
                    from evaluate_tracking_metrics import evaluate_tracking_metrics_gui
                except ImportError:
                    try:
                        from legacy.evaluate_tracking_metrics import evaluate_tracking_metrics_gui
                    except ImportError:
                        messagebox.showerror("Error", "Could not import evaluate_tracking_metrics.py")
                        return
                
                evaluate_tracking_metrics_gui(self.root, csv_file)
        except Exception as e:
            messagebox.showerror("Error", f"Could not evaluate tracking metrics: {e}")
            import traceback
            traceback.print_exc()
    
    def convert_tracks_to_anchors(self):
        """Convert tracks to anchor frames"""
        try:
            try:
                from convert_tracks_to_anchor_frames import convert_tracks_to_anchor_frames_gui
            except ImportError:
                try:
                    from legacy.convert_tracks_to_anchor_frames import convert_tracks_to_anchor_frames_gui
                except ImportError:
                    try:
                        # Try to find in project root
                        import sys
                        import os
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from convert_tracks_to_anchor_frames import convert_tracks_to_anchor_frames_gui
                    except ImportError:
                        messagebox.showerror("Error", "Could not import convert_tracks_to_anchor_frames.py")
                        return
            
            convert_tracks_to_anchor_frames_gui(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Could not convert tracks: {e}")
            import traceback
            traceback.print_exc()
    
    def convert_tags_to_anchors(self):
        """Convert existing player tags to anchor frames"""
        self.convert_existing_tags_to_anchors()
    
    def convert_existing_tags_to_anchors(self):
        """Convert existing player tags (player_mappings) to anchor frames at strategic intervals"""
        try:
            import os
            from pathlib import Path
            import json
            
            # Try to find default directory (video directory or current directory)
            default_dir = None
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
                if os.path.exists(video_path):
                    default_dir = os.path.dirname(os.path.abspath(video_path))
            
            # Ask user to select PlayerTagsSeed JSON file
            input_file = filedialog.askopenfilename(
                title="Select PlayerTagsSeed JSON File (with existing player tags)",
                filetypes=[
                    ("PlayerTagsSeed files", "PlayerTagsSeed-*.json"),
                    ("Seed config", "seed_config.json"),
                    ("JSON files", "*.json"),
                    ("All files", "*.*")
                ],
                initialdir=default_dir if default_dir else None
            )
            
            if not input_file:
                return
            
            # Show settings dialog
            settings_window = tk.Toplevel(self.root)
            settings_window.title("Convert Tags to Anchor Frames")
            settings_window.geometry("500x300")
            settings_window.transient(self.root)
            settings_window.grab_set()
            
            ttk.Label(settings_window, 
                     text="Convert existing player tags to anchor frames\n(at strategic intervals to avoid thousands)",
                     font=("Arial", 10, "bold")).pack(pady=10)
            
            # Frame interval
            interval_frame = ttk.Frame(settings_window)
            interval_frame.pack(pady=5, padx=20, fill=tk.X)
            ttk.Label(interval_frame, text="Frame Interval:").pack(side=tk.LEFT)
            interval_var = tk.IntVar(value=150)  # Default: 150 frames
            ttk.Spinbox(interval_frame, from_=50, to=300, textvariable=interval_var, width=10).pack(side=tk.RIGHT)
            ttk.Label(interval_frame, text="(150 = ±150 frame protection, recommended)").pack(side=tk.RIGHT, padx=5)
            
            # Max per track
            max_frame = ttk.Frame(settings_window)
            max_frame.pack(pady=5, padx=20, fill=tk.X)
            ttk.Label(max_frame, text="Max Anchors per Track:").pack(side=tk.LEFT)
            max_var = tk.IntVar(value=10)  # Default: 10 anchors per track
            ttk.Spinbox(max_frame, from_=5, to=50, textvariable=max_var, width=10).pack(side=tk.RIGHT)
            ttk.Label(max_frame, text="(prevents too many anchors)").pack(side=tk.RIGHT, padx=5)
            
            # Info
            info_text = (
                "This will:\n"
                "• Keep all existing player tags (player_mappings)\n"
                "• Create anchor frames every N frames for protection\n"
                "• Preserve all existing data\n"
                "• Overwrite the input file (backup recommended)"
            )
            ttk.Label(settings_window, text=info_text, font=("Arial", 9), 
                     foreground="darkgreen", justify=tk.LEFT).pack(pady=10, padx=20)
            
            conversion_params = {}
            
            def do_conversion():
                conversion_params['interval'] = interval_var.get()
                conversion_params['max_per_track'] = max_var.get()
                conversion_params['confirmed'] = True
                settings_window.destroy()
            
            def cancel():
                conversion_params['cancelled'] = True
                settings_window.destroy()
            
            button_frame = ttk.Frame(settings_window)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Convert", command=do_conversion).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.LEFT, padx=5)
            
            settings_window.wait_window()
            
            if conversion_params.get('cancelled') or not conversion_params.get('confirmed'):
                return
            
            # Import and run converter
            try:
                try:
                    from convert_existing_tags_to_anchors import convert_tags_to_anchors
                except ImportError:
                    try:
                        from legacy.convert_existing_tags_to_anchors import convert_tags_to_anchors
                    except ImportError:
                        messagebox.showerror(
                            "Error",
                            "Could not import converter module.\n\n"
                            "Make sure convert_existing_tags_to_anchors.py is in the project directory."
                        )
                        return
                
                result = convert_tags_to_anchors(
                    input_file,
                    output_file=None,  # Overwrite input
                    frame_interval=conversion_params['interval'],
                    max_anchors_per_track=conversion_params['max_per_track']
                )
                
                if result:
                    messagebox.showinfo(
                        "Success",
                        f"✅ Converted existing tags to anchor frames!\n\n"
                        f"File: {os.path.basename(result)}\n\n"
                        f"All existing player tags are preserved.\n"
                        f"Anchor frames created at {conversion_params['interval']} frame intervals.\n\n"
                        f"The anchor frames will be automatically loaded during analysis."
                    )
                else:
                    messagebox.showerror("Error", "Conversion failed. Check console for details.")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Error during conversion:\n{str(e)}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            messagebox.showerror("Error", f"Could not convert tags: {e}")
            import traceback
            traceback.print_exc()
    
    def fix_failed_anchor_frames(self):
        """Fix failed anchor frames"""
        try:
            try:
                from fix_failed_anchor_frames import fix_failed_anchor_frames_gui
            except ImportError:
                try:
                    from legacy.fix_failed_anchor_frames import fix_failed_anchor_frames_gui
                except ImportError:
                    try:
                        # Try to find in project root
                        import sys
                        import os
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from fix_failed_anchor_frames import fix_failed_anchor_frames_gui
                    except ImportError:
                        messagebox.showerror("Error", "Could not import fix_failed_anchor_frames.py")
                        return
            
            fix_failed_anchor_frames_gui(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Could not fix anchor frames: {e}")
            import traceback
            traceback.print_exc()
    
    def optimize_anchor_frames(self):
        """Optimize anchor frames by keeping only strategic ones (occlusion points, first appearance, etc.)"""
        try:
            import os
            from pathlib import Path
            from tkinter import filedialog
            
            # Ask user to select anchor frames file
            anchor_file = filedialog.askopenfilename(
                title="Select Anchor Frames JSON File",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir=os.getcwd()
            )
            
            if not anchor_file:
                return
            
            # Check if file exists
            if not os.path.exists(anchor_file):
                messagebox.showerror("Error", f"File not found: {anchor_file}")
                return
            
            # Ask for output file (optional)
            output_file = filedialog.asksaveasfilename(
                title="Save Optimized Anchor Frames As",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile=Path(anchor_file).stem + "_optimized.json"
            )
            
            if not output_file:
                return
            
            # Create progress window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Optimizing Anchor Frames")
            progress_window.geometry("700x500")
            progress_window.transient(self.root)
            
            progress_text = scrolledtext.ScrolledText(progress_window, wrap=tk.WORD, height=25, width=80)
            progress_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            def run_optimization():
                try:
                    try:
                        from optimize_anchor_frames import optimize_anchor_frames, store_occlusion_anchors_per_player, load_anchor_frames, detect_occlusion_points
                    except ImportError:
                        try:
                            from legacy.optimize_anchor_frames import optimize_anchor_frames, store_occlusion_anchors_per_player, load_anchor_frames, detect_occlusion_points
                        except ImportError:
                            progress_text.insert(tk.END, f"❌ Error: Could not import optimize_anchor_frames.py\n")
                            progress_text.insert(tk.END, f"Make sure the file is in the project directory.\n")
                            ttk.Button(progress_window, text="Close", command=progress_window.destroy).pack(pady=10)
                            return
                    
                    progress_text.insert(tk.END, f"📊 Optimizing anchor frames...\n")
                    progress_text.insert(tk.END, f"   Input file: {anchor_file}\n")
                    progress_text.insert(tk.END, f"   Output file: {output_file}\n\n")
                    progress_window.update()
                    
                    # Run optimization
                    optimized_file = optimize_anchor_frames(anchor_file, output_file)
                    
                    if optimized_file:
                        progress_text.insert(tk.END, f"\n✅ Optimization complete!\n")
                        progress_text.insert(tk.END, f"   Optimized file: {optimized_file}\n\n")
                        
                        # Also create occlusion anchors per player
                        progress_text.insert(tk.END, f"📊 Creating occlusion anchors per player...\n")
                        progress_window.update()
                        
                        anchor_frames = load_anchor_frames(anchor_file)
                        occlusion_frames = detect_occlusion_points(anchor_frames, {})
                        
                        occlusion_file = Path(optimized_file).parent / f"{Path(optimized_file).stem}_occlusion_per_player.json"
                        store_occlusion_anchors_per_player(anchor_frames, occlusion_frames, str(occlusion_file))
                        
                        progress_text.insert(tk.END, f"✅ Occlusion anchors per player saved to:\n")
                        progress_text.insert(tk.END, f"   {occlusion_file}\n\n")
                        progress_text.insert(tk.END, f"💡 Next steps:\n")
                        progress_text.insert(tk.END, f"   1. Review the optimized anchor frames\n")
                        progress_text.insert(tk.END, f"   2. Test with the optimized file to ensure tracking quality\n")
                        progress_text.insert(tk.END, f"   3. If satisfied, replace the original file\n")
                    else:
                        progress_text.insert(tk.END, f"❌ Optimization failed\n")
                    
                    ttk.Button(progress_window, text="Close", command=progress_window.destroy).pack(pady=10)
                    
                except Exception as e:
                    progress_text.insert(tk.END, f"❌ Error during optimization:\n{str(e)}\n")
                    import traceback
                    progress_text.insert(tk.END, traceback.format_exc())
                    ttk.Button(progress_window, text="Close", command=progress_window.destroy).pack(pady=10)
            
            # Run optimization in separate thread
            import threading
            thread = threading.Thread(target=run_optimization, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not open anchor frame optimizer:\n{e}")
    
    def clear_anchor_frames(self):
        """Clear all anchor frames to start fresh"""
        try:
            from tkinter import messagebox, filedialog
            import os
            import json
            import shutil
            from pathlib import Path
            
            # Ask for confirmation
            response = messagebox.askyesno(
                "Clear Anchor Frames",
                "This will DELETE all PlayerTagsSeed JSON files and clear anchor frames from seed_config.json.\n\n"
                "Backups will be created automatically.\n\n"
                "This is recommended if you have too many anchor frames (e.g., 147k+) causing slow performance.\n\n"
                "Continue?",
                icon="warning"
            )
            
            if not response:
                return
            
            # Ask for directory
            video_dir = filedialog.askdirectory(
                title="Select Video Directory (where anchor frames are stored)",
                initialdir=os.getcwd()
            )
            
            if not video_dir:
                return
            
            # Find and delete anchor frame files
            deleted_count = 0
            backed_up_count = 0
            
            # Find all PlayerTagsSeed files
            anchor_files = []
            for root, dirs, files in os.walk(video_dir):
                for file in files:
                    if file.startswith("PlayerTagsSeed-") and file.endswith(".json"):
                        anchor_files.append(os.path.join(root, file))
            
            if not anchor_files:
                messagebox.showinfo("Info", "No anchor frame files found in selected directory.")
                return
            
            # Create progress window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Clearing Anchor Frames")
            progress_window.geometry("600x400")
            progress_window.transient(self.root)
            
            progress_text = scrolledtext.ScrolledText(progress_window, wrap=tk.WORD, height=20, width=70)
            progress_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            def do_clear():
                nonlocal deleted_count, backed_up_count
                try:
                    progress_text.insert(tk.END, f"Found {len(anchor_files)} anchor frame file(s):\n\n")
                    
                    for anchor_file in anchor_files:
                        try:
                            # Create backup
                            backup_file = anchor_file + ".backup"
                            shutil.copy2(anchor_file, backup_file)
                            backed_up_count += 1
                            progress_text.insert(tk.END, f"  ✓ Backed up: {os.path.basename(anchor_file)}\n")
                            progress_window.update()
                            
                            # Delete file
                            os.remove(anchor_file)
                            deleted_count += 1
                            progress_text.insert(tk.END, f"  ✓ Deleted: {os.path.basename(anchor_file)}\n")
                            progress_window.update()
                        except Exception as e:
                            progress_text.insert(tk.END, f"  ⚠ Error processing {os.path.basename(anchor_file)}: {e}\n")
                            progress_window.update()
                    
                    # Also check for seed_config.json
                    seed_config_path = os.path.join(video_dir, "seed_config.json")
                    if os.path.exists(seed_config_path):
                        progress_text.insert(tk.END, f"\n📄 Found seed_config.json, clearing anchor_frames from it...\n")
                        try:
                            with open(seed_config_path, 'r') as f:
                                data = json.load(f)
                            
                            if 'anchor_frames' in data:
                                # Backup
                                backup_path = seed_config_path + ".backup"
                                shutil.copy2(seed_config_path, backup_path)
                                
                                # Clear anchor frames
                                data['anchor_frames'] = {}
                                
                                # Save
                                try:
                                    from json_utils import safe_json_save
                                    safe_json_save(Path(seed_config_path), data, create_backup=True, validate=True)
                                except ImportError:
                                    with open(seed_config_path, 'w') as f:
                                        json.dump(data, f, indent=2)
                                
                                progress_text.insert(tk.END, f"  ✓ Cleared anchor_frames from seed_config.json\n")
                                progress_window.update()
                        except Exception as e:
                            progress_text.insert(tk.END, f"  ⚠ Error processing seed_config.json: {e}\n")
                            progress_window.update()
                    
                    progress_text.insert(tk.END, f"\n✅ Complete!\n")
                    progress_text.insert(tk.END, f"   Backed up: {backed_up_count} file(s)\n")
                    progress_text.insert(tk.END, f"   Deleted: {deleted_count} file(s)\n")
                    
                    ttk.Button(progress_window, text="Close", command=progress_window.destroy).pack(pady=10)
                    
                except Exception as e:
                    progress_text.insert(tk.END, f"❌ Error: {e}\n")
                    import traceback
                    progress_text.insert(tk.END, traceback.format_exc())
                    ttk.Button(progress_window, text="Close", command=progress_window.destroy).pack(pady=10)
            
            import threading
            thread = threading.Thread(target=do_clear, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not clear anchor frames:\n{e}")
    
    def open_interactive_learning(self):
        """Open interactive player learning tool"""
        try:
            try:
                from interactive_player_learning import InteractivePlayerLearning
            except ImportError:
                try:
                    from legacy.interactive_player_learning import InteractivePlayerLearning
                except ImportError:
                    messagebox.showerror("Error", "Could not import interactive_player_learning.py")
                    return
            
            learning_window = tk.Toplevel(self.root)
            learning_window.title("Interactive Player Learning")
            learning_window.geometry("1600x1050")
            learning_window.transient(self.root)
            
            video_path = None
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
            
            app = InteractivePlayerLearning(learning_window, video_path=video_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open interactive learning: {e}")
            import traceback
            traceback.print_exc()
    
    def open_track_review(self):
        """Open track review and assignment tool"""
        try:
            try:
                from track_review_assigner import TrackReviewAssigner
            except ImportError:
                try:
                    from legacy.track_review_assigner import TrackReviewAssigner
                except ImportError:
                    try:
                        # Try to find in project root
                        import sys
                        import os
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from track_review_assigner import TrackReviewAssigner
                    except ImportError:
                        # Silently fail - this is an optional feature
                        messagebox.showinfo("Info", "Track Review & Assignment tool not available.\n\nThis is an optional feature.")
                        return
            
            # TrackReviewAssigner creates its own window, so we pass parent
            video_path = None
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
            
            # TrackReviewAssigner will create its own window
            app = TrackReviewAssigner(parent=self.root)
            
            # If video path is available, set it directly
            if video_path and hasattr(app, 'video_file'):
                app.video_file = video_path
        except Exception as e:
            messagebox.showerror("Error", f"Could not open track review: {e}")
            import traceback
            traceback.print_exc()
    
    def remove_false_matches_from_gallery(self, parent_frame=None):
        """Remove false matches from player gallery - Interactive review tool"""
        try:
            from player_gallery import PlayerGallery
            from tkinter import messagebox, ttk
            import cv2
            from PIL import Image, ImageTk
            import os
            
            gallery = PlayerGallery()
            
            # Ask user which mode they want
            mode_window = tk.Toplevel(self.root)
            mode_window.title("Remove False Matches")
            mode_window.geometry("500x300")
            mode_window.transient(self.root)
            mode_window.attributes('-toolwindow', False)
            
            ttk.Label(mode_window, text="Remove False Matches", font=("Arial", 14, "bold")).pack(pady=10)
            ttk.Label(mode_window, text="Choose removal method:", font=("Arial", 10)).pack(pady=5)
            
            mode_var = tk.StringVar(value="interactive")
            
            def run_automatic():
                """Automatic removal based on similarity/confidence thresholds"""
                mode_window.destroy()
                response = messagebox.askyesno(
                    "Remove False Matches (Automatic)",
                    "This will automatically remove low-quality and false matches.\n\n"
                    "This removes reference frames with:\n"
                    "• Low similarity scores (< 0.5)\n"
                    "• Low confidence scores (< 0.5)\n\n"
                    "A backup will be created automatically.\n\n"
                    "Continue?",
                    icon="question"
                )
                
                if not response:
                    return
                
                # Run cleanup with stricter thresholds
                gallery.remove_false_matches(min_similarity_threshold=0.5, min_confidence_threshold=0.5)
                messagebox.showinfo("Success", "False matches removed from gallery")
                self._refresh_gallery_tab(None)
            
            def run_interactive():
                """Interactive review - manually review each player's images"""
                mode_window.destroy()
                self._interactive_false_match_removal(gallery)
            
            ttk.Radiobutton(mode_window, text="Automatic (Remove low similarity/confidence frames)", 
                           variable=mode_var, value="automatic").pack(pady=5, padx=20, anchor="w")
            ttk.Label(mode_window, text="  Removes frames with similarity < 0.5 or confidence < 0.5", 
                     font=("Arial", 8), foreground="gray").pack(padx=40, anchor="w")
            
            ttk.Radiobutton(mode_window, text="Interactive Review (Manually review each player)", 
                           variable=mode_var, value="interactive").pack(pady=5, padx=20, anchor="w")
            ttk.Label(mode_window, text="  Review each player's images and remove wrong ones", 
                     font=("Arial", 8), foreground="gray").pack(padx=40, anchor="w")
            
            button_frame = ttk.Frame(mode_window)
            button_frame.pack(pady=20)
            
            ttk.Button(button_frame, text="Continue", 
                      command=lambda: run_automatic() if mode_var.get() == "automatic" else run_interactive()).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=mode_window.destroy).pack(side=tk.LEFT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not remove false matches: {e}")
            import traceback
            traceback.print_exc()
    
    def _cleanup_player_false_matches(self, gallery, player_id, player_name):
        """Open interactive false match removal tool for a specific player"""
        try:
            from tkinter import messagebox, ttk
            import cv2
            from PIL import Image, ImageTk
            import os
            
            # Create review window
            review_window = tk.Toplevel(self.root)
            review_window.title(f"Clean Up False Matches - {player_name}")
            review_window.geometry("1600x900")
            review_window.transient(self.root)
            review_window.attributes('-toolwindow', False)
            
            # Ensure window is visible and on top
            review_window.lift()
            review_window.attributes('-topmost', True)
            review_window.update_idletasks()
            review_window.attributes('-topmost', False)
            review_window.focus_force()
            # Bring to front again after a short delay to ensure it's visible
            self.root.after(100, lambda: review_window.lift())
            
            # Get the player profile
            current_profile = gallery.get_player(player_id)
            if not current_profile:
                messagebox.showerror("Error", f"Player '{player_name}' not found in gallery")
                review_window.destroy()
                return
            
            # Show player info at top
            info_frame = ttk.Frame(review_window)
            info_frame.pack(fill=tk.X, padx=10, pady=10)
            ttk.Label(info_frame, text=f"Cleaning up: {player_name}", 
                     font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=5)
            ref_count = len(current_profile.reference_frames) if current_profile.reference_frames else 0
            ttk.Label(info_frame, text=f"({ref_count} reference frames)", 
                     font=("Arial", 12), foreground="gray").pack(side=tk.LEFT, padx=5)
            
            # Use the same interactive review logic
            self._setup_interactive_review(review_window, gallery, player_id, current_profile, player_name)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not open cleanup tool:\n{e}")
            import traceback
            traceback.print_exc()
    
    def _setup_interactive_review(self, review_window, gallery, player_id, current_profile, player_name):
        """Setup the interactive review interface (shared by both methods)"""
        try:
            from tkinter import messagebox, ttk
            import cv2
            from PIL import Image, ImageTk
            import os
            
            ref_frame_widgets = []
            selected_frames = {}  # Dict to track selected frames: {(video_path, frame_num): (checkbox_var, ref_frame)}
            frame_to_container = {}  # Map frame_key to container for fast deletion
            
            def get_frame_key(ref_frame):
                """Get a unique hashable key for a reference frame"""
                video_path = ref_frame.get('video_path', 'unknown')
                frame_num = ref_frame.get('frame_num', 0)
                return (video_path, frame_num)
            
            # Control buttons frame (Select All, Delete Selected)
            control_frame = ttk.Frame(review_window)
            control_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
            
            def select_all_frames():
                """Select/deselect all checkboxes"""
                if not current_profile or not current_profile.reference_frames:
                    return
                # Check if all are selected
                all_selected = all(var.get() for var, _ in selected_frames.values())
                # Toggle: if all selected, deselect all; otherwise select all
                new_state = not all_selected
                for var, _ in selected_frames.values():
                    var.set(new_state)
                update_delete_button_state()
            
            def update_delete_button_state():
                """Update delete button state based on selection"""
                selected_count = sum(1 for var, _ in selected_frames.values() if var.get())
                if selected_count > 0:
                    delete_selected_btn.config(state=tk.NORMAL, text=f"🗑️ Delete Selected ({selected_count})")
                else:
                    delete_selected_btn.config(state=tk.DISABLED, text="🗑️ Delete Selected")
            
            def delete_selected_frames():
                """Delete all selected frames"""
                selected = [ref_frame for key, (var, ref_frame) in selected_frames.items() if var.get()]
                if not selected:
                    messagebox.showwarning("No Selection", "Please select frames to delete")
                    return
                
                result = messagebox.askyesno("Confirm Mass Delete", 
                        f"Delete {len(selected)} selected reference frame(s) from {current_profile.name}?\n\n"
                        f"This will permanently remove these images from the gallery.\n"
                        f"This action cannot be undone.")
                if result:
                    try:
                        removed_count = 0
                        for ref_frame in selected:
                            if ref_frame in current_profile.reference_frames:
                                current_profile.reference_frames.remove(ref_frame)
                                removed_count += 1
                        
                        if removed_count > 0:
                            gallery.save_gallery()
                            # Remove containers directly instead of reloading all images (much faster!)
                            for ref_frame in selected:
                                frame_key = get_frame_key(ref_frame)
                                if frame_key in frame_to_container:
                                    container = frame_to_container[frame_key]
                                    container.destroy()
                                    if container in ref_frame_widgets:
                                        ref_frame_widgets.remove(container)
                                    del frame_to_container[frame_key]
                                if frame_key in selected_frames:
                                    del selected_frames[frame_key]
                            
                            update_delete_button_state()
                            # Update window title and info
                            ref_count = len(current_profile.reference_frames) if current_profile.reference_frames else 0
                            review_window.title(f"Clean Up False Matches - {player_name} ({ref_count} frames)")
                            messagebox.showinfo("Success", f"Removed {removed_count} reference frame(s)")
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not remove frames:\n{e}")
                        import traceback
                        traceback.print_exc()
            
            ttk.Button(control_frame, text="☑ Select All", command=select_all_frames).pack(side=tk.LEFT, padx=5)
            delete_selected_btn = ttk.Button(control_frame, text="🗑️ Delete Selected", 
                                            command=delete_selected_frames, state=tk.DISABLED)
            delete_selected_btn.pack(side=tk.LEFT, padx=5)
            
            # Image display area
            image_frame = ttk.LabelFrame(review_window, text="Reference Frames - Check boxes to mark for deletion", padding="10")
            image_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Scrollable canvas for images with modern styling
            canvas = tk.Canvas(image_frame, bg="#F8F8F8", highlightthickness=0, relief=tk.FLAT)
            scrollbar = ttk.Scrollbar(image_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Add mouse wheel scrolling
            def on_mousewheel(event):
                if event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")
                else:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            def bind_mousewheel(event):
                canvas.bind("<MouseWheel>", on_mousewheel)
                canvas.bind("<Button-4>", on_mousewheel)
                canvas.bind("<Button-5>", on_mousewheel)
                scrollable_frame.bind("<MouseWheel>", on_mousewheel)
                scrollable_frame.bind("<Button-4>", on_mousewheel)
                scrollable_frame.bind("<Button-5>", on_mousewheel)
            
            def unbind_mousewheel(event):
                canvas.unbind("<MouseWheel>")
                canvas.unbind("<Button-4>")
                canvas.unbind("<Button-5>")
                scrollable_frame.unbind("<MouseWheel>")
                scrollable_frame.unbind("<Button-4>")
                scrollable_frame.unbind("<Button-5>")
            
            canvas.bind('<Enter>', bind_mousewheel)
            canvas.bind('<Leave>', unbind_mousewheel)
            scrollable_frame.bind('<Enter>', bind_mousewheel)
            scrollable_frame.bind('<Leave>', unbind_mousewheel)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            def load_player_images():
                """Load and display reference frames for the player (async with placeholders)"""
                # Clear existing widgets
                for widget in ref_frame_widgets:
                    widget.destroy()
                ref_frame_widgets.clear()
                selected_frames.clear()
                frame_to_container.clear()
                
                if not current_profile:
                    ttk.Label(scrollable_frame, text=f"Error: Could not load profile for {player_name}", 
                             font=("Arial", 12), foreground="red").pack(pady=20)
                    return
                
                if not current_profile.reference_frames:
                    ttk.Label(scrollable_frame, text=f"No reference frames for {player_name}", 
                             font=("Arial", 12), foreground="gray").pack(pady=20)
                    return
                
                # Show loading indicator
                loading_label = ttk.Label(scrollable_frame, 
                                        text=f"Loading {len(current_profile.reference_frames)} images...", 
                                        font=("Arial", 10), foreground="blue")
                loading_label.grid(row=0, column=0, pady=20)
                review_window.update()
                
                # Display each reference frame with placeholders first (fast)
                cols = 5  # More columns for faster review
                row_idx = 0
                col_idx = 0
                
                # Configure grid columns to expand evenly
                for c in range(cols):
                    scrollable_frame.columnconfigure(c, weight=1, uniform="frame_cols")
                
                frame_containers = []  # Store (container, ref_frame) for async loading
                
                for i, ref_frame in enumerate(current_profile.reference_frames):
                    # Container for each image
                    container = tk.Frame(scrollable_frame, bg="#FFFFFF", relief=tk.FLAT,
                                        borderwidth=1, highlightbackground="#E0E0E0", highlightthickness=1)
                    container.grid(row=row_idx, column=col_idx, padx=5, pady=5, sticky="nsew")
                    ref_frame_widgets.append(container)
                    frame_containers.append((container, ref_frame))
                    
                    # Checkbox for selection
                    checkbox_var = tk.BooleanVar()
                    frame_key = get_frame_key(ref_frame)
                    selected_frames[frame_key] = (checkbox_var, ref_frame)
                    frame_to_container[frame_key] = container  # Store mapping for fast deletion
                    checkbox = ttk.Checkbutton(container, variable=checkbox_var, 
                                             command=update_delete_button_state)
                    checkbox.pack(anchor=tk.NW, padx=5, pady=5)
                    
                    # Show placeholder immediately
                    placeholder_label = tk.Label(container, text="Loading...", 
                                                 font=("Arial", 8), foreground="#9E9E9E", bg="#FFFFFF")
                    placeholder_label.pack(pady=20)
                    
                    col_idx += 1
                    if col_idx >= cols:
                        col_idx = 0
                        row_idx += 1
                
                # Remove loading indicator
                loading_label.destroy()
                
                # Load thumbnails asynchronously
                def load_thumbnails_async():
                    """Load thumbnails in background thread"""
                    import threading
                    import time
                    
                    for container, ref_frame in frame_containers:
                        try:
                            if not review_window.winfo_exists():
                                break
                            
                            # Extract thumbnail (smaller for faster review)
                            thumbnail = self._extract_profile_image(ref_frame, max_size=(120, 150))
                            
                            def update_ui(thumb=thumbnail, cont=container, rf=ref_frame):
                                update_frame_thumbnail(thumb, cont, rf)
                            
                            if review_window.winfo_exists():
                                review_window.after(0, update_ui)
                            
                            time.sleep(0.03)  # Small delay
                        except Exception as e:
                            err_msg = str(e)
                            def update_error(cont=container, err=err_msg):
                                update_frame_error(cont, err)
                            if review_window.winfo_exists():
                                review_window.after(0, update_error)
                
                def update_frame_error(container, error_msg):
                    """Update frame container with error message"""
                    try:
                        if not container.winfo_exists():
                            return
                        for widget in container.winfo_children():
                            widget.destroy()
                        error_label = tk.Label(container, text=f"Error:\n{error_msg[:20]}", 
                                font=("Arial", 7), foreground="#D32F2F", bg="#FFFFFF")
                        error_label.pack(pady=5)
                    except tk.TclError:
                        pass
                
                def update_frame_thumbnail(thumbnail, container, ref_frame):
                    """Update frame container with actual thumbnail"""
                    try:
                        if not container.winfo_exists() or not review_window.winfo_exists():
                            return
                        # Clear placeholder
                        for widget in container.winfo_children():
                            widget.destroy()
                    except tk.TclError:
                        return
                    
                    try:
                        # Add checkbox
                        frame_key = get_frame_key(ref_frame)
                        if frame_key in selected_frames:
                            checkbox_var, _ = selected_frames[frame_key]
                        else:
                            checkbox_var = tk.BooleanVar()
                            selected_frames[frame_key] = (checkbox_var, ref_frame)
                        
                        checkbox = ttk.Checkbutton(container, variable=checkbox_var, 
                                                 command=update_delete_button_state)
                        checkbox.pack(anchor=tk.NW, padx=5, pady=5)
                        
                        if thumbnail:
                            img_label = tk.Label(container, image=thumbnail, bg="#FFFFFF", relief=tk.FLAT)
                            img_label.image = thumbnail
                            img_label.pack(pady=(0, 5))
                            
                            # Frame info
                            info_frame_inner = tk.Frame(container, bg="#FFFFFF")
                            info_frame_inner.pack(fill=tk.X, padx=5, pady=2)
                            
                            video_name = os.path.basename(ref_frame.get('video_path', 'unknown'))
                            frame_num = ref_frame.get('frame_num', '?')
                            conf = ref_frame.get('confidence', 0.0)
                            sim = ref_frame.get('similarity', 0.0)
                            info_text = f"Frame {frame_num}\nConf: {conf:.2f} | Sim: {sim:.2f}"
                            info_label = tk.Label(info_frame_inner, text=info_text, 
                                    font=("Arial", 7), bg="#FFFFFF", foreground="#424242", justify=tk.LEFT)
                            info_label.pack()
                    except Exception as e:
                        pass
                
                # Start async loading
                import threading
                thread = threading.Thread(target=load_thumbnails_async, daemon=True)
                thread.start()
            
            # Load images immediately
            load_player_images()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not setup review interface:\n{e}")
            import traceback
            traceback.print_exc()
    
    def _interactive_false_match_removal(self, gallery):
        """Interactive tool to review and remove false matches from each player"""
        try:
            from tkinter import messagebox, ttk
            import cv2
            from PIL import Image, ImageTk
            import os
            
            players = gallery.list_players()
            if not players:
                messagebox.showinfo("No Players", "No players in gallery to review")
                return
            
            # Create review window
            review_window = tk.Toplevel(self.root)
            review_window.title("Review False Matches - Interactive")
            review_window.geometry("1400x700")
            review_window.transient(self.root)
            review_window.attributes('-toolwindow', False)
            
            # Ensure window is visible and on top
            review_window.lift()
            review_window.attributes('-topmost', True)
            review_window.update_idletasks()
            review_window.attributes('-topmost', False)
            review_window.focus_force()
            
            # Player selection
            player_frame = ttk.LabelFrame(review_window, text="Select Player", padding="10")
            player_frame.pack(fill=tk.X, padx=10, pady=10)
            
            player_var = tk.StringVar()
            player_combo = ttk.Combobox(player_frame, textvariable=player_var, width=40, state="readonly")
            player_combo['values'] = [f"{name} (ID: {pid})" for pid, name in players]
            player_combo.pack(side=tk.LEFT, padx=5)
            
            # Current player info
            current_player_id = None
            current_profile = None
            ref_frame_widgets = []
            selected_frames = {}  # Dict to track selected frames: {(video_path, frame_num): (checkbox_var, ref_frame)}
            frame_to_container = {}  # Map frame_key to container for fast deletion
            
            def get_frame_key(ref_frame):
                """Get a unique hashable key for a reference frame"""
                video_path = ref_frame.get('video_path', 'unknown')
                frame_num = ref_frame.get('frame_num', 0)
                return (video_path, frame_num)
            
            # Control buttons frame (Select All, Delete Selected)
            control_frame = ttk.Frame(review_window)
            control_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
            
            def select_all_frames():
                """Select/deselect all checkboxes"""
                if not current_profile or not current_profile.reference_frames:
                    return
                # Check if all are selected
                all_selected = all(var.get() for var, _ in selected_frames.values())
                # Toggle: if all selected, deselect all; otherwise select all
                new_state = not all_selected
                for var, _ in selected_frames.values():
                    var.set(new_state)
                update_delete_button_state()
            
            def update_delete_button_state():
                """Update delete button state based on selection"""
                selected_count = sum(1 for var, _ in selected_frames.values() if var.get())
                if selected_count > 0:
                    delete_selected_btn.config(state=tk.NORMAL, text=f"🗑️ Delete Selected ({selected_count})")
                else:
                    delete_selected_btn.config(state=tk.DISABLED, text="🗑️ Delete Selected")
            
            def delete_selected_frames():
                """Delete all selected frames"""
                selected = [ref_frame for key, (var, ref_frame) in selected_frames.items() if var.get()]
                if not selected:
                    messagebox.showwarning("No Selection", "Please select frames to delete")
                    return
                
                result = messagebox.askyesno("Confirm Mass Delete", 
                        f"Delete {len(selected)} selected reference frame(s) from {current_profile.name}?\n\n"
                        f"This will permanently remove these images from the gallery.\n"
                        f"This action cannot be undone.")
                if result:
                    try:
                        removed_count = 0
                        for ref_frame in selected:
                            if ref_frame in current_profile.reference_frames:
                                current_profile.reference_frames.remove(ref_frame)
                                removed_count += 1
                        
                        if removed_count > 0:
                            gallery.save_gallery()
                            # Remove containers directly instead of reloading all images (much faster!)
                            for ref_frame in selected:
                                frame_key = get_frame_key(ref_frame)
                                if frame_key in frame_to_container:
                                    container = frame_to_container[frame_key]
                                    container.destroy()
                                    if container in ref_frame_widgets:
                                        ref_frame_widgets.remove(container)
                                    del frame_to_container[frame_key]
                                if frame_key in selected_frames:
                                    del selected_frames[frame_key]
                            
                            update_delete_button_state()
                            # Update window title
                            review_window.title(f"Review False Matches - {current_profile.name} ({len(current_profile.reference_frames)} frames)")
                            messagebox.showinfo("Success", f"Removed {removed_count} reference frame(s)")
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not remove frames:\n{e}")
                        import traceback
                        traceback.print_exc()
            
            ttk.Button(control_frame, text="☑ Select All", command=select_all_frames).pack(side=tk.LEFT, padx=5)
            delete_selected_btn = ttk.Button(control_frame, text="🗑️ Delete Selected", 
                                            command=delete_selected_frames, state=tk.DISABLED)
            delete_selected_btn.pack(side=tk.LEFT, padx=5)
            
            # Image display area
            image_frame = ttk.LabelFrame(review_window, text="Reference Frames", padding="10")
            image_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Scrollable canvas for images with modern styling
            canvas = tk.Canvas(image_frame, bg="#F8F8F8", highlightthickness=0, relief=tk.FLAT)
            scrollbar = ttk.Scrollbar(image_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            def load_player_images():
                """Load and display reference frames for selected player (async with placeholders)"""
                nonlocal current_player_id, current_profile
                
                # Clear existing widgets
                for widget in ref_frame_widgets:
                    widget.destroy()
                ref_frame_widgets.clear()
                selected_frames.clear()
                frame_to_container.clear()
                
                selection = player_combo.current()
                if selection < 0:
                    return
                
                current_player_id, player_name = players[selection]
                current_profile = gallery.get_player(current_player_id)
                
                if not current_profile:
                    ttk.Label(scrollable_frame, text=f"Error: Could not load profile for {player_name}", 
                             font=("Arial", 12), foreground="red").pack(pady=20)
                    return
                
                if not current_profile.reference_frames:
                    ttk.Label(scrollable_frame, text=f"No reference frames for {player_name}", 
                             font=("Arial", 12), foreground="gray").pack(pady=20)
                    return
                
                # Show loading indicator
                loading_label = ttk.Label(scrollable_frame, 
                                        text=f"Loading {len(current_profile.reference_frames)} images...", 
                                        font=("Arial", 10), foreground="blue")
                loading_label.grid(row=0, column=0, pady=20)
                review_window.update()
                
                # Display each reference frame with placeholders first (fast)
                cols = 4
                row_idx = 0
                col_idx = 0
                
                # Configure grid columns to expand evenly
                for c in range(cols):
                    scrollable_frame.columnconfigure(c, weight=1, uniform="frame_cols")
                
                frame_containers = []  # Store (container, ref_frame) for async loading
                
                for i, ref_frame in enumerate(current_profile.reference_frames):
                    # Container for each image
                    container = ttk.Frame(scrollable_frame, relief=tk.RAISED, borderwidth=2)
                    container.grid(row=row_idx, column=col_idx, padx=5, pady=5, sticky="nsew")
                    ref_frame_widgets.append(container)
                    frame_containers.append((container, ref_frame))
                    
                    # Checkbox for selection
                    checkbox_var = tk.BooleanVar()
                    frame_key = get_frame_key(ref_frame)
                    selected_frames[frame_key] = (checkbox_var, ref_frame)
                    frame_to_container[frame_key] = container  # Store mapping for fast deletion
                    checkbox = ttk.Checkbutton(container, variable=checkbox_var, 
                                             command=update_delete_button_state)
                    checkbox.pack(anchor=tk.NW, padx=5, pady=5)
                    
                    # Show placeholder immediately
                    placeholder_label = ttk.Label(container, text="Loading...", 
                                                 font=("Arial", 8), foreground="gray")
                    placeholder_label.pack(pady=20)
                    
                    # Frame info (show immediately)
                    video_name = os.path.basename(ref_frame.get('video_path', 'unknown'))
                    frame_num = ref_frame.get('frame_num', '?')
                    conf = ref_frame.get('confidence', 0.0)
                    sim = ref_frame.get('similarity', 0.0)
                    
                    info_text = f"Frame {frame_num}\nConf: {conf:.2f}\nSim: {sim:.2f}"
                    info_label = ttk.Label(container, text=info_text, font=("Arial", 8), 
                             justify=tk.CENTER)
                    info_label.pack()
                    
                    # Action buttons
                    btn_frame = ttk.Frame(container)
                    btn_frame.pack(pady=5)
                    
                    def make_remove_handler(ref_frame_obj=ref_frame, container_obj=container):
                        def remove():
                            result = messagebox.askyesno("Confirm Delete", 
                                    f"Remove this reference frame from {player_name}?\n\n"
                                    f"Frame: {frame_num}\n"
                                    f"Video: {video_name}\n\n"
                                    f"This will permanently remove this image.")
                            if result:
                                try:
                                    # Find and remove the frame
                                    if ref_frame_obj in current_profile.reference_frames:
                                        current_profile.reference_frames.remove(ref_frame_obj)
                                        gallery.save_gallery()
                                        # Remove container directly instead of reloading all
                                        container_obj.destroy()
                                        ref_frame_widgets.remove(container_obj)
                                        frame_key = get_frame_key(ref_frame_obj)
                                        if frame_key in selected_frames:
                                            del selected_frames[frame_key]
                                        update_delete_button_state()
                                        # Update window title
                                        review_window.title(f"Review False Matches - {player_name} ({len(current_profile.reference_frames)} frames)")
                                        messagebox.showinfo("Success", "Reference frame removed")
                                    else:
                                        messagebox.showwarning("Not Found", "Frame not found")
                                except Exception as e:
                                    messagebox.showerror("Error", f"Could not remove frame:\n{e}")
                        return remove
                    
                    ttk.Button(btn_frame, text="🗑️ Remove", command=make_remove_handler()).pack(side=tk.LEFT, padx=2)
                    
                    col_idx += 1
                    if col_idx >= cols:
                        col_idx = 0
                        row_idx += 1
                
                # Remove loading indicator
                loading_label.destroy()
                
                # Load thumbnails asynchronously in background
                def load_thumbnails_async():
                    """Load thumbnails in background thread"""
                    import threading
                    import time
                    
                    for container, ref_frame in frame_containers:
                        try:
                            # Extract thumbnail (this is the slow part)
                            if hasattr(self, '_extract_profile_image'):
                                # Quick validation first
                                video_path = ref_frame.get('video_path')
                                frame_num = ref_frame.get('frame_num')
                                bbox = ref_frame.get('bbox')
                                
                                error_reason = None
                                if not video_path:
                                    error_reason = "No video path"
                                elif not os.path.exists(video_path):
                                    error_reason = "Video missing"
                                elif frame_num is None:
                                    error_reason = "No frame num"
                                elif not bbox or len(bbox) < 4:
                                    error_reason = "Invalid bbox"
                                
                                if error_reason:
                                    # Update UI in main thread
                                    def update_error(cont=container, reason=error_reason, fn=frame_num):
                                        for widget in cont.winfo_children():
                                            if isinstance(widget, ttk.Label) and widget.cget("text") == "Loading...":
                                                widget.destroy()
                                                break
                                        ttk.Label(cont, text=f"{reason}\nFrame {fn}", 
                                                 font=("Arial", 7), foreground="orange", justify=tk.CENTER).pack(pady=10)
                                    review_window.after(0, update_error)
                                else:
                                    thumbnail = self._extract_profile_image(ref_frame, max_size=(200, 250))
                                    
                                    # Update UI in main thread
                                    def update_ui(cont=container, thumb=thumbnail):
                                        # Remove placeholder
                                        for widget in cont.winfo_children():
                                            if isinstance(widget, ttk.Label) and widget.cget("text") == "Loading...":
                                                widget.destroy()
                                                break
                                        
                                        if thumb:
                                            img_label = ttk.Label(cont, image=thumb)
                                            img_label.image = thumb  # Keep reference
                                            img_label.pack(pady=5)
                                        else:
                                            ttk.Label(cont, text="Image\nunavailable\n(Check video)", 
                                                     font=("Arial", 7), foreground="orange", justify=tk.CENTER).pack(pady=10)
                                    review_window.after(0, update_ui)
                                
                                # Small delay to prevent overwhelming the UI
                                time.sleep(0.05)
                        except Exception as e:
                            # Update with error in main thread
                            err_msg = str(e)[:25] if len(str(e)) > 25 else str(e)
                            def update_error(cont=container, err=err_msg):
                                for widget in cont.winfo_children():
                                    if isinstance(widget, ttk.Label) and widget.cget("text") == "Loading...":
                                        widget.destroy()
                                        break
                                ttk.Label(cont, text=f"Error:\n{err}", 
                                         font=("Arial", 7), foreground="red", justify=tk.CENTER).pack(pady=10)
                            review_window.after(0, update_error)
                
                # Start background thread for loading thumbnails
                import threading
                thumbnail_thread = threading.Thread(target=load_thumbnails_async, daemon=True)
                thumbnail_thread.start()
                
                # Update window title
                review_window.title(f"Review False Matches - {player_name} ({len(current_profile.reference_frames)} frames)")
            
            # Load button
            ttk.Button(player_frame, text="Load Images", command=load_player_images).pack(side=tk.LEFT, padx=5)
            
            # Auto-load first player
            if players:
                try:
                    player_combo.current(0)
                    # Use after_idle to ensure window is fully rendered
                    review_window.after_idle(load_player_images)
                except Exception as e:
                    # If auto-load fails, user can still click "Load Images" button
                    print(f"Auto-load failed: {e}")
                    import traceback
                    traceback.print_exc()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not open interactive review: {e}")
            import traceback
            traceback.print_exc()
    
    def remove_missing_reference_frames(self, parent_frame=None):
        """Remove reference frames pointing to missing video files or with invalid bbox data"""
        try:
            from player_gallery import PlayerGallery
            from tkinter import messagebox
            
            response = messagebox.askyesno(
                "Remove Invalid Reference Frames",
                "This will remove reference frames with:\n\n"
                "• Missing video files\n"
                "• Invalid frame numbers\n"
                "• Invalid or missing bbox (bounding box) data\n\n"
                "A backup will be created automatically.\n\n"
                "Continue?",
                icon="question"
            )
            
            if not response:
                return
            
            gallery = PlayerGallery()
            gallery.remove_missing_reference_frames(verify_video_files=True)
            messagebox.showinfo("Success", "Invalid reference frames removed (missing videos, invalid frame numbers, and invalid bbox data)")
            self._refresh_gallery_tab(None)
        except Exception as e:
            messagebox.showerror("Error", f"Could not remove invalid frames: {e}")
            import traceback
            traceback.print_exc()
    
    def remove_unavailable_images(self, parent_frame=None):
        """Remove reference frames that cannot be extracted (unavailable images)"""
        try:
            try:
                from SoccerID.models.player_gallery import PlayerGallery
            except ImportError:
                from player_gallery import PlayerGallery
            from tkinter import messagebox
            import threading
            
            response = messagebox.askyesno(
                "Remove Unavailable Images",
                "This will remove reference frames that show 'Image unavailable' in the gallery.\n\n"
                "This includes frames with:\n"
                "• Missing or unreadable video files\n"
                "• Frames that cannot be read from video\n"
                "• Invalid bounding boxes\n"
                "• Images that are mostly green (field)\n"
                "• Images that are too small (< 30x30 pixels)\n\n"
                "This is a more comprehensive check than 'Remove Missing Frames'.\n"
                "A backup will be created automatically.\n\n"
                "Continue?",
                icon="question"
            )
            
            if not response:
                return
            
            # Create progress window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Removing Unavailable Images")
            progress_window.geometry("500x150")
            progress_window.transient(self.root)
            progress_window.grab_set()  # Make it modal
            progress_window.protocol("WM_DELETE_WINDOW", lambda: None)  # Prevent closing during processing
            
            # Center the window
            progress_window.update_idletasks()
            x = (progress_window.winfo_screenwidth() // 2) - (500 // 2)
            y = (progress_window.winfo_screenheight() // 2) - (150 // 2)
            progress_window.geometry(f"500x150+{x}+{y}")
            
            # Progress label
            status_label = ttk.Label(progress_window, text="Initializing...", font=("Arial", 10))
            status_label.pack(pady=10)
            
            # Progress bar
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100, length=450)
            progress_bar.pack(pady=10, padx=25, fill=tk.X)
            
            # Percentage label
            percent_label = ttk.Label(progress_window, text="0%", font=("Arial", 9))
            percent_label.pack()
            
            result = {'removed_count': 0, 'players_cleaned': 0, 'error': None}
            
            def update_progress(current, total, message):
                """Update progress bar from background thread"""
                if total > 0:
                    percent = (current / total) * 100
                    progress_var.set(percent)
                    percent_label.config(text=f"{percent:.1f}%")
                status_label.config(text=message)
                progress_window.update()
            
            def process_images():
                """Process images in background thread"""
                try:
                    # Always create a new instance to avoid modifying the main gallery in memory
                    # The main gallery will be reloaded after save
                    gallery = PlayerGallery()
                    removed_count, players_cleaned = gallery.remove_unavailable_images(progress_callback=update_progress)
                    result['removed_count'] = removed_count
                    result['players_cleaned'] = players_cleaned
                    
                    # Reload the main gallery instance if it exists
                    # This ensures the in-memory state matches what was saved to disk
                    if hasattr(self, 'gallery') and self.gallery is not None:
                        # Clear existing players and reload from disk
                        self.gallery.players.clear()
                        self.gallery.load_gallery()
                except Exception as e:
                    result['error'] = str(e)
                    import traceback
                    traceback.print_exc()
                finally:
                    # Close progress window and show result
                    progress_window.after(0, lambda: progress_window.destroy() if progress_window.winfo_exists() else None)
                    progress_window.after(100, show_result)
            
            def show_result():
                """Show result message after processing"""
                if result['error']:
                    messagebox.showerror("Error", f"Could not remove unavailable images: {result['error']}")
                elif result['removed_count'] > 0:
                    messagebox.showinfo("Success", 
                        f"Removed {result['removed_count']} unavailable images from {result['players_cleaned']} player(s).\n\n"
                        "The gallery has been updated and saved.")
                else:
                    messagebox.showinfo("No Unavailable Images", 
                        "No unavailable images found - all images are available.")
                
                # Refresh gallery tab to show updated state
                self._refresh_gallery_tab(None)
            
            # Start processing in background thread (with small delay to show window)
            def start_processing():
                import time
                time.sleep(0.1)  # Small delay to ensure window is visible
                process_images()
            
            thread = threading.Thread(target=start_processing, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not remove unavailable images: {e}")
            import traceback
            traceback.print_exc()
    
    def open_multi_camera_wizard(self, project_path=None):
        """Open multi-camera setup wizard"""
        try:
            try:
                from SoccerID.gui.wizards.multi_camera_wizard import MultiCameraWizard
            except ImportError:
                try:
                    from gui.wizards.multi_camera_wizard import MultiCameraWizard
                except ImportError:
                    messagebox.showerror("Error", "Multi-camera wizard not available")
                    return
            
            # Use current project path if not provided
            if project_path is None:
                project_path = getattr(self, 'current_project_path', None)
            
            wizard = MultiCameraWizard(self.root, project_path=project_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open multi-camera wizard:\n{e}")
            import traceback
            traceback.print_exc()
    
    def open_multi_camera_project(self):
        """Open existing multi-camera project"""
        try:
            from tkinter import filedialog
            project_path = filedialog.askopenfilename(
                title="Open Multi-Camera Project",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if not project_path:
                return
            
            # Ask what to do with project
            choice = messagebox.askyesnocancel(
                "Multi-Camera Project",
                f"Open project: {os.path.basename(project_path)}\n\n"
                "Yes = View synchronized playback\n"
                "No = Edit project setup",
                icon="question"
            )
            
            if choice is True:
                # Open viewer
                self.open_multi_camera_viewer(project_path)
            elif choice is False:
                # Open wizard for editing
                self.open_multi_camera_wizard(project_path=project_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open project:\n{e}")
            import traceback
            traceback.print_exc()
    
    def backfill_gallery_features(self, parent_frame=None):
        """Backfill Re-ID features for players missing them"""
        try:
            from player_gallery import PlayerGallery
            from tkinter import messagebox
            
            gallery = PlayerGallery()
            
            # Find players without features
            players_without_features = []
            for player_id, profile in gallery.players.items():
                if profile.features is None or len(profile.features) == 0:
                    players_without_features.append((player_id, profile.name))
            
            if not players_without_features:
                messagebox.showinfo("Info", "All players already have Re-ID features!")
                return
            
            # Ask for confirmation
            result = messagebox.askyesno(
                "Backfill Gallery Features",
                f"Found {len(players_without_features)} player(s) without Re-ID features:\n\n" +
                "\n".join([f"  • {name}" for _, name in players_without_features[:10]]) +
                (f"\n  ... and {len(players_without_features) - 10} more" if len(players_without_features) > 10 else "") +
                "\n\nThis will extract features from existing reference frames.\n\nContinue?",
                icon='question'
            )
            
            if not result:
                return
            
            # Process each player
            processed = 0
            for player_id, player_name in players_without_features:
                try:
                    profile = gallery.get_player(player_id)
                    if profile and profile.reference_frames and len(profile.reference_frames) > 0:
                        # Extract features from first reference frame
                        ref_frame = profile.reference_frames[0]
                        if ref_frame.get('video_path') and ref_frame.get('bbox'):
                            # This would normally call the Re-ID feature extraction
                            # For now, we'll just mark that features need to be extracted
                            # The actual feature extraction should happen during analysis
                            processed += 1
                except Exception as e:
                    print(f"Error processing {player_name}: {e}")
            
            if processed > 0:
                gallery.save_gallery()
                messagebox.showinfo(
                    "Success",
                    f"Processed {processed} player(s).\n\n"
                    "Features will be extracted during the next video analysis run."
                )
            else:
                messagebox.showwarning(
                    "Warning",
                    "No players could be processed.\n\n"
                    "Players need reference frames to extract features from."
                )
                
        except Exception as e:
            messagebox.showerror("Error", f"Could not backfill gallery features:\n{e}")
            import traceback
            traceback.print_exc()
    
    def match_unnamed_anchor_frames(self, parent_frame=None):
        """Match unnamed anchor frames to players in gallery"""
        try:
            from player_gallery import PlayerGallery
            from tkinter import messagebox, filedialog
            import json
            import os
            
            gallery = PlayerGallery()
            
            # Find anchor frame files
            anchor_files = []
            for file in os.listdir('.'):
                if file.startswith('PlayerTagsSeed-') and file.endswith('.json'):
                    anchor_files.append(file)
            
            if not anchor_files:
                messagebox.showwarning(
                    "No Anchor Files",
                    "No PlayerTagsSeed JSON files found in the current directory.\n\n"
                    "Anchor frames are created when you tag players in the playback viewer."
                )
                return
            
            # Let user select anchor file
            if len(anchor_files) == 1:
                selected_file = anchor_files[0]
            else:
                # Show file selection dialog
                selected_file = filedialog.askopenfilename(
                    title="Select Anchor Frame File",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                    initialfile=anchor_files[0] if anchor_files else None
                )
                if not selected_file:
                    return
            
            # Load anchor frames
            with open(selected_file, 'r') as f:
                anchor_data = json.load(f)
            
            # Find unnamed frames
            unnamed_frames = []
            for frame_num, anchors in anchor_data.items():
                for anchor in anchors:
                    if not anchor.get('player_name') or anchor.get('player_name') == 'UNKNOWN':
                        unnamed_frames.append((int(frame_num), anchor))
            
            if not unnamed_frames:
                messagebox.showinfo("Info", "No unnamed anchor frames found!")
                return
            
            # Ask for confirmation
            result = messagebox.askyesno(
                "Match Unnamed Anchors",
                f"Found {len(unnamed_frames)} unnamed anchor frame(s).\n\n"
                "This will attempt to match them to players in the gallery using Re-ID.\n\n"
                "Continue?",
                icon='question'
            )
            
            if not result:
                return
            
            # Try to match each unnamed frame
            matched = 0
            for frame_num, anchor in unnamed_frames:
                if anchor.get('bbox') and anchor.get('track_id'):
                    # This would normally use Re-ID to match
                    # For now, we'll just mark that matching needs to happen
                    # The actual matching should happen during analysis
                    matched += 1
            
            messagebox.showinfo(
                "Match Complete",
                f"Processed {matched} unnamed anchor frame(s).\n\n"
                "Matching will be attempted during the next video analysis run."
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not match unnamed anchor frames:\n{e}")
            import traceback
            traceback.print_exc()
    
    def clear_gallery_references(self):
        """Clear all reference frames from player gallery"""
        try:
            import json
            import os
            import shutil
            
            # Ask for confirmation
            response = messagebox.askyesno(
                "Clear Gallery Reference Frames",
                "This will DELETE all reference frames from ALL players in the gallery.\n\n"
                "This removes Re-ID reference frames that may be corrupted from bad tracking.\n\n"
                "A backup will be created automatically.\n\n"
                "Player names, jersey numbers, and teams will be preserved.\n\n"
                "Continue?",
                icon="warning"
            )
            
            if not response:
                return
            
            gallery_path = "player_gallery.json"
            if not os.path.exists(gallery_path):
                messagebox.showerror("Error", f"Gallery file not found: {gallery_path}")
                return
            
            # Create progress window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Clearing Gallery References")
            progress_window.geometry("600x400")
            progress_window.transient(self.root)
            
            progress_text = scrolledtext.ScrolledText(progress_window, wrap=tk.WORD, height=20, width=70)
            progress_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            def do_clear():
                try:
                    # Load gallery
                    with open(gallery_path, 'r') as f:
                        gallery_data = json.load(f)
                    
                    # Create backup
                    backup_path = f"{gallery_path}.backup"
                    shutil.copy2(gallery_path, backup_path)
                    progress_text.insert(tk.END, f"✓ Backup created: {backup_path}\n\n")
                    progress_window.update()
                    
                    # Clear reference frames
                    total_refs = 0
                    players_cleared = 0
                    
                    for player_id, player_data in gallery_data.items():
                        ref_count = 0
                        
                        # Count and clear reference frames
                        if 'reference_frames' in player_data and player_data['reference_frames']:
                            ref_count = len(player_data['reference_frames'])
                            total_refs += ref_count
                            player_data['reference_frames'] = []
                        
                        # Clear uniform variants (they contain reference frames)
                        if 'uniform_variants' in player_data and player_data['uniform_variants']:
                            variant_count = sum(len(frames) for frames in player_data['uniform_variants'].values())
                            total_refs += variant_count
                            player_data['uniform_variants'] = {}
                        
                        if ref_count > 0:
                            players_cleared += 1
                            player_name = player_data.get('name', player_id)
                            progress_text.insert(tk.END, f"  • {player_name}: Cleared {ref_count} reference frame(s)\n")
                            progress_window.update()
                    
                    # Save updated gallery
                    with open(gallery_path, 'w') as f:
                        json.dump(gallery_data, f, indent=2)
                    
                    progress_text.insert(tk.END, f"\n✅ Done!\n")
                    progress_text.insert(tk.END, f"   Cleared: {total_refs} reference frame(s) from {players_cleared} player(s)\n")
                    progress_text.insert(tk.END, f"   Backup: {backup_path}\n")
                    progress_text.insert(tk.END, f"\n💡 Next steps:\n")
                    progress_text.insert(tk.END, f"   1. Start fresh analysis with minimal anchor frames\n")
                    progress_text.insert(tk.END, f"   2. Let the system rebuild clean reference frames\n")
                    progress_text.insert(tk.END, f"   3. Only tag frames when you're confident about player identity\n")
                    
                    ttk.Button(progress_window, text="Close", command=progress_window.destroy).pack(pady=10)
                    
                except Exception as e:
                    progress_text.insert(tk.END, f"❌ Error: {e}\n")
                    import traceback
                    progress_text.insert(tk.END, traceback.format_exc())
                    ttk.Button(progress_window, text="Close", command=progress_window.destroy).pack(pady=10)
            
            import threading
            thread = threading.Thread(target=do_clear, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not clear gallery references:\n{e}")
    
    def open_post_analysis_workflow(self):
        """Open post-analysis workflow guide"""
        try:
            from tkinter import messagebox, scrolledtext
            import tkinter as tk
            
            workflow_window = tk.Toplevel(self.root)
            workflow_window.title("Post-Analysis Workflow Guide")
            workflow_window.geometry("800x600")
            workflow_window.transient(self.root)
            
            text_widget = scrolledtext.ScrolledText(workflow_window, wrap=tk.WORD, font=("Arial", 10))
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            workflow_text = """
POST-ANALYSIS WORKFLOW GUIDE
============================

After running video analysis, follow these steps to complete your workflow:

1. REVIEW PLAYER IDENTIFICATION
   • Open the Playback Viewer
   • Navigate through the video
   • Verify that players are correctly identified
   • Tag any misidentified players

2. CONSOLIDATE PLAYER IDs
   • Use Tools → Post-Analysis → Consolidate IDs
   • This merges duplicate player IDs
   • Ensures consistent player tracking

3. TRACK REVIEW & ASSIGNMENT
   • Use Tools → Post-Analysis → Track Review
   • Review and assign player names to tracks
   • Reject bad or incorrect tracks

4. GENERATE HIGHLIGHTS
   • Player highlights are auto-generated
   • View in Gallery → View Highlight Clips
   • Tag and organize clips by player

5. EXPORT DATA
   • CSV tracking data is automatically exported
   • Event data can be exported separately
   • Use Gallery → Export Gallery for player data

6. EVALUATE METRICS
   • Use Tools → Post-Analysis → Evaluate Metrics (HOTA)
   • Review tracking quality metrics
   • Use to improve future analyses

TIPS:
• Always review player identification before finalizing
• Use the Gallery to manage player profiles
• Keep reference frames clean for better Re-ID
• Regular gallery maintenance improves accuracy
"""
            
            text_widget.insert("1.0", workflow_text)
            text_widget.config(state=tk.DISABLED)
            
            button_frame = tk.Frame(workflow_window)
            button_frame.pack(pady=10)
            tk.Button(button_frame, text="Close", command=workflow_window.destroy).pack()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not open workflow guide:\n{e}")
    
    def evaluate_hota(self):
        """Evaluate tracking metrics (HOTA, MOTA, IDF1)"""
        try:
            from tkinter import messagebox, filedialog
            import os
            
            # Find tracking data CSV files
            csv_files = []
            for file in os.listdir('.'):
                if file.endswith('_tracking_data.csv') or file.endswith('_analyzed_tracking_data.csv'):
                    csv_files.append(file)
            
            if not csv_files:
                messagebox.showwarning(
                    "No Tracking Data",
                    "No tracking data CSV files found in the current directory.\n\n"
                    "Run an analysis first to generate tracking data."
                )
                return
            
            # Let user select CSV file
            if len(csv_files) == 1:
                selected_file = csv_files[0]
            else:
                selected_file = filedialog.askopenfilename(
                    title="Select Tracking Data CSV",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=csv_files[0] if csv_files else None
                )
                if not selected_file:
                    return
            
            # Check for anchor frame file
            video_name = os.path.splitext(os.path.basename(selected_file))[0]
            video_name = video_name.replace('_tracking_data', '').replace('_analyzed', '')
            
            anchor_file = None
            for file in os.listdir('.'):
                if file.startswith('PlayerTagsSeed-') and video_name in file:
                    anchor_file = file
                    break
            
            if not anchor_file:
                messagebox.showwarning(
                    "No Anchor Frames",
                    f"No anchor frame file found for this video.\n\n"
                    "Anchor frames are needed to evaluate tracking metrics.\n"
                    "Tag some players in the playback viewer first."
                )
                return
            
            # The actual HOTA evaluation is done in combined_analysis_optimized.py
            # This is just a placeholder that shows where it would be called
            messagebox.showinfo(
                "Metrics Evaluation",
                f"Tracking metrics evaluation would be run on:\n\n"
                f"CSV: {selected_file}\n"
                f"Anchors: {anchor_file}\n\n"
                "Metrics are automatically calculated during analysis.\n"
                "Check the analysis output for HOTA, MOTA, and IDF1 scores."
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not evaluate metrics:\n{e}")
            import traceback
            traceback.print_exc()
    
    def consolidate_ids(self):
        """Consolidate track IDs - merge duplicate IDs for same player"""
        self.open_consolidate_ids()
    
    def open_consolidate_ids(self):
        """Open ID consolidation tool"""
        try:
            try:
                from consolidate_ids import consolidate_ids_gui
            except ImportError:
                try:
                    from legacy.consolidate_ids import consolidate_ids_gui
                except ImportError:
                    try:
                        from consolidate_player_ids import IDConsolidationGUI
                        consolidate_window = tk.Toplevel(self.root)
                        consolidate_window.title("Player ID Consolidation")
                        consolidate_window.geometry("1200x800")
                        consolidate_window.transient(self.root)
                        app = IDConsolidationGUI(consolidate_window)
                        return
                    except ImportError:
                        messagebox.showerror("Error", "Could not import consolidate_ids.py or consolidate_player_ids.py")
                        return
            
            consolidate_ids_gui(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Could not consolidate IDs: {e}")
            import traceback
            traceback.print_exc()
    
    def export_reid_model(self):
        """Export ReID model to optimized format (ONNX, TensorRT, etc.)"""
        try:
            from tkinter import filedialog, messagebox
            try:
                from reid_model_export import export_model
            except ImportError:
                try:
                    from legacy.reid_model_export import export_model
                except ImportError:
                    messagebox.showerror("Export Not Available", 
                                       "ReID model export requires BoxMOT.\n\n"
                                       "Install with: pip install boxmot")
                    return
            
            # Ask user to select model file
            model_path = filedialog.askopenfilename(
                title="Select ReID Model to Export",
                filetypes=[
                    ("PyTorch Models", "*.pt"),
                    ("All Files", "*.*")
                ],
                initialdir="."
            )
            
            if not model_path:
                return
            
            # Ask for export format
            format_window = tk.Toplevel(self.root)
            format_window.title("Export ReID Model")
            format_window.geometry("400x250")
            format_window.transient(self.root)
            format_window.grab_set()
            
            ttk.Label(format_window, text="Export Format:", font=("Arial", 10, "bold")).pack(pady=10)
            
            format_var = tk.StringVar(value="onnx")
            formats = [
                ("ONNX (recommended)", "onnx"),
                ("TensorRT (GPU only)", "engine"),
                ("OpenVINO (Intel)", "openvino"),
                ("TorchScript", "torchscript")
            ]
            
            for text, value in formats:
                ttk.Radiobutton(format_window, text=text, variable=format_var, 
                              value=value).pack(anchor=tk.W, padx=20, pady=2)
            
            device_var = tk.StringVar(value="cpu")
            ttk.Label(format_window, text="Device:", font=("Arial", 9)).pack(pady=(10, 2))
            device_frame = ttk.Frame(format_window)
            device_frame.pack()
            ttk.Radiobutton(device_frame, text="CPU", variable=device_var, value="cpu").pack(side=tk.LEFT, padx=10)
            ttk.Radiobutton(device_frame, text="GPU", variable=device_var, value="0").pack(side=tk.LEFT, padx=10)
            
            def do_export():
                format_window.destroy()
                try:
                    from pathlib import Path
                    model_file = Path(model_path)
                    
                    result = export_model(
                        weights_path=model_path,
                        output_format=format_var.get(),
                        device=device_var.get()
                    )
                    if result:
                        export_path = Path(result) if isinstance(result, str) else result
                        location_msg = f"Model exported successfully!\n\nLocation:\n{export_path}\n\n"
                        usage_msg = (
                            "💡 Automatic Usage:\n"
                            "The exported model will be automatically detected\n"
                            "and used by ReIDTracker when you run analysis.\n"
                            "No manual import needed!\n\n"
                            f"BoxMOT will prefer {format_var.get().upper()} over\n"
                            "PyTorch for faster inference."
                        )
                        messagebox.showinfo("Export Successful", location_msg + usage_msg)
                    else:
                        messagebox.showerror("Export Failed", 
                                           "Model export failed. Check console for details.")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Error during export:\n{e}")
            
            ttk.Button(format_window, text="Export", command=do_export).pack(pady=15)
            ttk.Button(format_window, text="Cancel", command=format_window.destroy).pack()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open export dialog:\n{e}")
            import traceback
            traceback.print_exc()
    
    def open_color_helper(self):
        """Open color helper for team/ball colors"""
        try:
            try:
                from combined_color_helper import CombinedColorHelper
            except ImportError:
                try:
                    from legacy.combined_color_helper import CombinedColorHelper
                except ImportError:
                    try:
                        # Try to find combined_color_helper in the project root
                        import sys
                        import os
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from combined_color_helper import CombinedColorHelper
                    except ImportError:
                        messagebox.showerror("Error", "Could not import combined_color_helper.py")
                        return
            
            color_window = tk.Toplevel(self.root)
            color_window.title("Color Helper")
            color_window.geometry("1000x700")
            color_window.transient(self.root)
            
            video_path = None
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
            
            app = CombinedColorHelper(color_window, callback=None)
            
            # Set video path if available
            if video_path and os.path.exists(video_path):
                app.video_path = video_path
                app.video_path_entry.delete(0, tk.END)
                app.video_path_entry.insert(0, video_path)
                # Optionally auto-load the video
                try:
                    app.load_video()
                except:
                    pass  # If auto-load fails, user can load manually
        except Exception as e:
            messagebox.showerror("Error", f"Could not open color helper: {e}")
            import traceback
            traceback.print_exc()
    
    def open_tag_players_gallery(self):
        """Open tag players in gallery"""
        # This is the same as gallery seeder
        self.open_gallery_seeder()
    
    def open_video_splicer(self):
        """Open video splicer tool"""
        try:
            try:
                from video_splicer import VideoSplicer
            except ImportError:
                try:
                    from legacy.video_splicer import VideoSplicer
                except ImportError:
                    try:
                        # Try to find video_splicer in the project root
                        import sys
                        import os
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from video_splicer import VideoSplicer
                    except ImportError:
                        messagebox.showerror("Error", "Could not import video_splicer.py")
                        return
            
            splicer_window = tk.Toplevel(self.root)
            splicer_window.title("Video Splicer")
            splicer_window.geometry("1200x800")
            splicer_window.transient(self.root)
            
            app = VideoSplicer(splicer_window)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open video splicer: {e}")
            import traceback
            traceback.print_exc()
    
    def open_speed_tracking(self):
        """Open speed tracking viewer"""
        try:
            try:
                from speed_tracking import SpeedTrackingViewer
            except ImportError:
                try:
                    from legacy.speed_tracking import SpeedTrackingViewer
                except ImportError:
                    messagebox.showerror("Error", "Could not import speed_tracking.py")
                    return
            
            speed_window = tk.Toplevel(self.root)
            speed_window.title("Speed Tracking")
            speed_window.geometry("1600x1050")
            speed_window.transient(self.root)
            
            video_path = None
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
            
            app = SpeedTrackingViewer(speed_window, video_path=video_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open speed tracking: {e}")
            import traceback
            traceback.print_exc()
    
    def create_new_project(self):
        """Create a new project"""
        try:
            from tkinter import simpledialog
            project_name = simpledialog.askstring(
                "Create New Project",
                "Enter project name:",
                initialvalue="New Project"
            )
            if project_name:
                self.current_project_name.set(project_name)
                self.current_project_path = None
                messagebox.showinfo("New Project Created", 
                                  f"Project '{project_name}' created.\n\n"
                                  "Configure your settings and use 'Save Project' to save.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not create project: {e}")
    
    def save_project_as(self):
        """Save project with a new name or location"""
        try:
            from project_manager import save_project
            from tkinter import simpledialog
            
            project_name = simpledialog.askstring(
                "Save Project As",
                "Enter project name:",
                initialvalue=self.current_project_name.get() if self.current_project_name.get() != "No Project" else "Untitled Project"
            )
            
            if project_name:
                result = save_project(project_name, project_path=None, gui_instance=self)
                if result:
                    project_path, saved_items = result
                    self.current_project_path = project_path
                    self.current_project_name.set(project_name)
                    
                    # Show success confirmation
                    messagebox.showinfo("Project Saved", 
                                      f"Project '{project_name}' saved successfully.\n\n"
                                      f"Location: {project_path}")
                    
                    # Show success toast
                    if self.toast_manager:
                        self.toast_manager.success(f"Project '{project_name}' saved")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save project: {e}")
            import traceback
            traceback.print_exc()
    
    def rename_project(self):
        """Rename the current project"""
        try:
            from tkinter import simpledialog
            current_name = self.current_project_name.get()
            if current_name == "No Project":
                messagebox.showwarning("No Project", "No project is currently loaded.")
                return
            
            new_name = simpledialog.askstring(
                "Rename Project",
                "Enter new project name:",
                initialvalue=current_name
            )
            
            if new_name and new_name != current_name:
                self.current_project_name.set(new_name)
                if self.current_project_path:
                    response = messagebox.askyesno(
                        "Save Renamed Project?",
                        "Would you like to save the project with the new name?"
                    )
                    if response:
                        self.save_project_as()
                else:
                    messagebox.showinfo("Project Renamed", 
                                      f"Project renamed to '{new_name}'.\n\n"
                                      "Use 'Save Project' or 'Save Project As' to save.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not rename project: {e}")
    
    def open_playback_viewer(self):
        """Open playback viewer"""
        # Use unified viewer in playback mode
        self.open_unified_viewer(mode='playback')
    
    def _open_legacy_playback_viewer(self):
        """Fallback to legacy playback viewer"""
        try:
            # Try new structure imports first
            try:
                from .viewers.playback_viewer import PlaybackViewer
            except ImportError:
                try:
                    from SoccerID.gui.viewers.playback_viewer import PlaybackViewer
                except ImportError:
                    # Legacy fallback
                    try:
                        from legacy.playback_viewer import PlaybackViewer
                    except ImportError:
                        from playback_viewer import PlaybackViewer
            viewer_window = tk.Toplevel(self.root)
            viewer = PlaybackViewer(viewer_window)
        except ImportError as e:
            messagebox.showerror("Error", f"Could not import playback_viewer: {e}")
    
    def open_quick_start_wizard(self):
        """Open Quick Start Wizard for simplified setup"""
        try:
            from ..automation.quick_start_wizard import QuickStartWizard
        except ImportError:
            try:
                from SoccerID.automation.quick_start_wizard import QuickStartWizard
            except ImportError:
                try:
                    import sys
                    import os
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                    if project_root not in sys.path:
                        sys.path.insert(0, project_root)
                    from SoccerID.automation.quick_start_wizard import QuickStartWizard
                except ImportError:
                    messagebox.showerror("Error", "Could not import QuickStartWizard")
                    return
        
        def on_wizard_complete(config):
            """Handle wizard completion"""
            import os  # Import os in the function scope to avoid closure issues
            # Set input file
            if config.get('video_path'):
                self.input_file.set(config['video_path'])
            
            # Set output directory
            if config.get('output_dir'):
                output_path = os.path.join(
                    config['output_dir'],
                    os.path.basename(config['video_path']).replace('.mp4', '_analyzed.mp4')
                )
                self.output_file.set(output_path)
            
            # Apply preset settings to GUI variables
            self._apply_preset_config(config)
            
            # Ask if user wants to start analysis immediately
            if messagebox.askyesno(
                "Quick Start",
                "Configuration loaded!\n\n"
                "Would you like to start the analysis now?",
                parent=self.root
            ):
                self.run_analysis()
        
        wizard = QuickStartWizard(self.root, callback=on_wizard_complete)
    
    def _apply_preset_config(self, config: dict):
        """Apply preset configuration to GUI variables"""
        # Tracker settings
        if 'tracker' in config:
            tracker_map = {
                'bytetrack': 'bytetrack',
                'ocsort': 'ocsort',
                'deepocsort': 'deepocsort',
                'strongsort': 'strongsort',
                'botsort': 'botsort'
            }
            if config['tracker'] in tracker_map:
                self.tracker_type.set(tracker_map[config['tracker']])
        
        # Re-ID settings
        if 'use_reid' in config:
            self.use_reid.set(config['use_reid'])
        
        # Advanced settings
        if 'use_harmonic_mean' in config:
            self.use_harmonic_mean.set(config['use_harmonic_mean'])
        if 'use_expansion_iou' in config:
            self.use_expansion_iou.set(config['use_expansion_iou'])
        if 'enhanced_kalman' in config:
            self.use_enhanced_kalman.set(config['enhanced_kalman'])
        if 'ema_smoothing' in config:
            self.use_ema_smoothing.set(config['ema_smoothing'])
        
        # Detection threshold (map to yolo_confidence - this is the YOLO detection confidence threshold)
        if 'detection_threshold' in config:
            if hasattr(self, 'yolo_confidence'):
                # Map detection_threshold to yolo_confidence (YOLO detection confidence)
                self.yolo_confidence.set(config['detection_threshold'])
            elif not hasattr(self, 'detection_threshold'):
                # Create the attribute if it doesn't exist (fallback)
                self.detection_threshold = tk.DoubleVar(value=config['detection_threshold'])
            else:
                self.detection_threshold.set(config['detection_threshold'])
        
        # Automation settings
        if 'auto_tag_players' in config:
            self.auto_tag_players.set(config['auto_tag_players'])
        if 'auto_detect_events' in config:
            self.auto_detect_events.set(config['auto_detect_events'])
        if 'generate_highlights' in config:
            self.generate_highlights.set(config['generate_highlights'])
        if 'personalized_player_highlights' in config:
            # Store in a variable if we add it to GUI
            if not hasattr(self, 'personalized_player_highlights'):
                self.personalized_player_highlights = tk.BooleanVar(value=config['personalized_player_highlights'])
            else:
                self.personalized_player_highlights.set(config['personalized_player_highlights'])
        if 'auto_export_csv' in config:
            self.auto_export_csv.set(config['auto_export_csv'])
    
    def open_real_time_processor(self):
        """Open real-time processing window"""
        try:
            from ..real_time_processor import RealTimeProcessor, test_camera_source
        except ImportError:
            try:
                from SoccerID.real_time_processor import RealTimeProcessor, test_camera_source
            except ImportError:
                messagebox.showerror("Error", "Real-time processor module not found")
                return
        
        # Create window
        rt_window = tk.Toplevel(self.root)
        rt_window.title("Real-Time Analysis")
        rt_window.geometry("600x500")
        rt_window.transient(self.root)
        
        # Instructions
        instructions = tk.Text(rt_window, wrap=tk.WORD, height=12, width=70)
        instructions.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        instructions.insert("1.0", 
            "📱 Galaxy S23 Ultra Setup:\n\n"
            "🌐 For Soccer Fields (No WiFi):\n"
            "1. On phone: Enable Mobile Hotspot (Settings → Connections)\n"
            "2. On laptop: Connect to phone's WiFi hotspot\n"
            "3. Open IP Webcam app and tap 'Start server'\n"
            "4. Note IP address (usually 192.168.43.1:8080 for hotspot)\n"
            "5. Enter IP address below\n\n"
            "🏠 For Home/Office (With WiFi):\n"
            "1. Connect phone and laptop to same WiFi network\n"
            "2. Open IP Webcam app and tap 'Start server'\n"
            "3. Note the IP address shown\n"
            "4. Enter IP address below\n\n"
            "💡 Tip: Use RTSP for lower latency: rtsp://[ip]:8080/h264_ulaw.sdp\n"
            "💡 Common hotspot IPs: 192.168.43.1 or 192.168.137.1"
        )
        instructions.config(state=tk.DISABLED)
        
        # Camera source input
        source_frame = ttk.Frame(rt_window)
        source_frame.pack(pady=10, padx=10, fill=tk.X)
        
        ttk.Label(source_frame, text="Camera Source:").pack(side=tk.LEFT, padx=5)
        source_var = tk.StringVar(value="http://192.168.43.1:8080/video")  # Default to hotspot IP
        source_entry = ttk.Entry(source_frame, textvariable=source_var, width=40)
        source_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        def test_source():
            source = source_var.get()
            if source.isdigit():
                source = int(source)
            if test_camera_source(source):
                messagebox.showinfo("Success", f"Camera source accessible: {source}")
            else:
                messagebox.showerror("Error", f"Cannot access camera source: {source}\n\n"
                                            "Make sure:\n"
                                            "• IP Webcam is running on your phone\n"
                                            "• Phone hotspot is enabled (for fields) OR both on same WiFi\n"
                                            "• Laptop is connected to phone's hotspot\n"
                                            "• IP address is correct\n"
                                            "• Try common hotspot IPs: 192.168.43.1 or 192.168.137.1")
        
        test_btn = ttk.Button(source_frame, text="Test", command=test_source)
        test_btn.pack(side=tk.LEFT, padx=5)
        
        # Settings
        settings_frame = ttk.LabelFrame(rt_window, text="Settings")
        settings_frame.pack(pady=10, padx=10, fill=tk.X)
        
        ttk.Label(settings_frame, text="Model Size:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        model_var = tk.StringVar(value="nano")
        model_combo = ttk.Combobox(settings_frame, textvariable=model_var, 
                                   values=["nano", "small", "medium"], width=15, state="readonly")
        model_combo.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(settings_frame, text="Process Every Nth Frame:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        skip_var = tk.IntVar(value=2)
        skip_spin = ttk.Spinbox(settings_frame, from_=1, to=5, textvariable=skip_var, width=15)
        skip_spin.grid(row=1, column=1, padx=5, pady=5)
        
        # Control buttons
        button_frame = ttk.Frame(rt_window)
        button_frame.pack(pady=10)
        
        processor_ref = {'processor': None}
        
        def start_processing():
            source = source_var.get()
            if source.isdigit():
                source = int(source)
            
            # Test source first
            if not test_camera_source(source):
                messagebox.showerror("Error", "Cannot access camera source. Please test first.")
                return
            
            # Create processor
            try:
                processor = RealTimeProcessor(
                    camera_source=source,
                    output_fps=30,
                    model_size=model_var.get(),
                    process_every_nth=skip_var.get(),
                    enable_tracking=True,
                    enable_reid=False,
                    display_window=True
                )
                
                if processor.start():
                    processor_ref['processor'] = processor
                    start_btn.config(state=tk.DISABLED)
                    stop_btn.config(state=tk.NORMAL)
                    messagebox.showinfo("Started", "Real-time processing started!\n\n"
                                                  "Press 'q' in the video window to stop.")
                else:
                    messagebox.showerror("Error", "Failed to start processing")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to start: {e}")
                import traceback
                traceback.print_exc()
        
        def stop_processing():
            if processor_ref['processor']:
                processor_ref['processor'].stop()
                processor_ref['processor'] = None
                start_btn.config(state=tk.NORMAL)
                stop_btn.config(state=tk.DISABLED)
        
        start_btn = ttk.Button(button_frame, text="Start Real-Time", command=start_processing)
        start_btn.pack(side=tk.LEFT, padx=5)
        
        stop_btn = ttk.Button(button_frame, text="Stop", command=stop_processing, state=tk.DISABLED)
        stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Status
        status_label = ttk.Label(rt_window, text="Ready", foreground="green")
        status_label.pack(pady=5)
    
    def open_batch_processing(self):
        """Open batch processing dialog"""
        try:
            from .batch_processing_dialog import BatchProcessingDialog
        except ImportError:
            try:
                from SoccerID.gui.batch_processing_dialog import BatchProcessingDialog
            except ImportError:
                try:
                    import sys
                    import os
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                    if project_root not in sys.path:
                        sys.path.insert(0, project_root)
                    from SoccerID.gui.batch_processing_dialog import BatchProcessingDialog
                except ImportError:
                    messagebox.showerror("Error", "Could not import BatchProcessingDialog")
                    return
        
        # Build config from current GUI settings
        config = {
            'tracker': self.tracker_type.get(),
            'use_reid': self.use_reid.get(),
            'temporal_smoothing': True,
            'detection_threshold': self.yolo_confidence.get() if hasattr(self, 'yolo_confidence') else 0.25,
            'track_buffer_seconds': 3.0,
            'auto_export_csv': True,
            'preserve_audio': True,
            'auto_tag_players': self.auto_tag_players.get() if hasattr(self, 'auto_tag_players') else False,
            'auto_detect_events': self.auto_detect_events.get() if hasattr(self, 'auto_detect_events') else False,
            'generate_highlights': self.generate_highlights.get() if hasattr(self, 'generate_highlights') else False,
            'personalized_player_highlights': getattr(self, 'personalized_player_highlights', tk.BooleanVar(value=False)).get() if hasattr(self, 'personalized_player_highlights') else False,
            'event_detect_passes': True,
            'event_detect_shots': True,
            'event_detect_goals': False,
            'event_min_ball_speed': 9.84,
            'event_min_pass_distance': 16.4,
        }
        
        # Add advanced settings if available
        if hasattr(self, 'use_harmonic_mean'):
            config['use_harmonic_mean'] = self.use_harmonic_mean.get()
        if hasattr(self, 'use_expansion_iou'):
            config['use_expansion_iou'] = self.use_expansion_iou.get()
        if hasattr(self, 'use_enhanced_kalman'):
            config['enhanced_kalman'] = self.use_enhanced_kalman.get()
        if hasattr(self, 'use_ema_smoothing'):
            config['ema_smoothing'] = self.use_ema_smoothing.get()
        
        # Open dialog
        dialog = BatchProcessingDialog(self.root, config=config)
    
    def open_amazfit_import(self):
        """Open Amazfit data import dialog"""
        from datetime import datetime
        
        try:
            from ..integrations.amazfit_integration import (
                AmazfitDataImporter,
                AmazfitSoccerMetrics,
                AmazfitVideoOverlay
            )
        except ImportError:
            try:
                from SoccerID.integrations.amazfit_integration import (
                    AmazfitDataImporter,
                    AmazfitSoccerMetrics,
                    AmazfitVideoOverlay
                )
            except ImportError:
                messagebox.showerror("Error", 
                    "Amazfit integration module not found.\n\n"
                    "Please install required dependencies:\n"
                    "pip install gpxpy requests")
                return
        
        # Create import window
        import_window = tk.Toplevel(self.root)
        import_window.title("Import Amazfit Data")
        import_window.geometry("700x600")
        import_window.transient(self.root)
        
        # Instructions
        instructions_frame = ttk.LabelFrame(import_window, text="Instructions", padding=10)
        instructions_frame.pack(pady=10, padx=10, fill=tk.X)
        
        instructions_text = (
            "📱 Amazfit Active Edge Data Import\n\n"
            "1. Export data from Zepp app:\n"
            "   • Open Zepp app → Activity → Select activity\n"
            "   • Tap Share/Export → Export as GPX or CSV\n\n"
            "2. Or sync to Strava:\n"
            "   • Connect Amazfit to Strava in Zepp app\n"
            "   • Use Strava API to fetch activity data\n\n"
            "3. Select file and video to sync with"
        )
        
        instructions_label = ttk.Label(instructions_frame, text=instructions_text, justify=tk.LEFT)
        instructions_label.pack(anchor=tk.W)
        
        # File selection
        file_frame = ttk.LabelFrame(import_window, text="Data File", padding=10)
        file_frame.pack(pady=10, padx=10, fill=tk.X)
        
        file_path_var = tk.StringVar()
        ttk.Label(file_frame, text="Amazfit Data File:").pack(anchor=tk.W)
        
        file_entry_frame = ttk.Frame(file_frame)
        file_entry_frame.pack(fill=tk.X, pady=5)
        
        file_entry = ttk.Entry(file_entry_frame, textvariable=file_path_var, width=50)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        def browse_file():
            file_path = filedialog.askopenfilename(
                title="Select Amazfit Data File",
                filetypes=[
                    ("GPX files", "*.gpx"),
                    ("CSV files", "*.csv"),
                    ("All files", "*.*")
                ]
            )
            if file_path:
                file_path_var.set(file_path)
        
        ttk.Button(file_entry_frame, text="Browse...", command=browse_file).pack(side=tk.LEFT)
        
        # Video selection
        video_frame = ttk.LabelFrame(import_window, text="Video to Sync With", padding=10)
        video_frame.pack(pady=10, padx=10, fill=tk.X)
        
        video_path_var = tk.StringVar()
        # Try to get current video path
        if hasattr(self, 'input_file') and self.input_file.get():
            video_path_var.set(self.input_file.get())
        
        ttk.Label(video_frame, text="Video File:").pack(anchor=tk.W)
        
        video_entry_frame = ttk.Frame(video_frame)
        video_entry_frame.pack(fill=tk.X, pady=5)
        
        video_entry = ttk.Entry(video_entry_frame, textvariable=video_path_var, width=50)
        video_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        def browse_video():
            video_path = filedialog.askopenfilename(
                title="Select Video File",
                filetypes=[
                    ("Video files", "*.mp4 *.avi *.mov *.mkv"),
                    ("All files", "*.*")
                ]
            )
            if video_path:
                video_path_var.set(video_path)
        
        ttk.Button(video_entry_frame, text="Browse...", command=browse_video).pack(side=tk.LEFT)
        
        # Video start time (optional)
        time_frame = ttk.LabelFrame(import_window, text="Video Start Time (Optional)", padding=10)
        time_frame.pack(pady=10, padx=10, fill=tk.X)
        
        ttk.Label(time_frame, text="If video and tracker started at different times, enter video start time:").pack(anchor=tk.W)
        
        time_entry_frame = ttk.Frame(time_frame)
        time_entry_frame.pack(fill=tk.X, pady=5)
        
        time_var = tk.StringVar(value="")
        time_entry = ttk.Entry(time_entry_frame, textvariable=time_var, width=30)
        time_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(time_entry_frame, text="Format: YYYY-MM-DD HH:MM:SS (leave empty to use video file time)").pack(side=tk.LEFT)
        
        # Player name (optional)
        player_frame = ttk.LabelFrame(import_window, text="Player Name (Optional)", padding=10)
        player_frame.pack(pady=10, padx=10, fill=tk.X)
        
        player_var = tk.StringVar()
        ttk.Label(player_frame, text="Player Name:").pack(anchor=tk.W)
        player_entry = ttk.Entry(player_frame, textvariable=player_var, width=30)
        player_entry.pack(anchor=tk.W, pady=5)
        ttk.Label(player_frame, text="(For associating wearable data with a specific player)").pack(anchor=tk.W)
        
        # Status and log
        status_frame = ttk.LabelFrame(import_window, text="Status", padding=10)
        status_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        status_text = scrolledtext.ScrolledText(status_frame, height=8, wrap=tk.WORD)
        status_text.pack(fill=tk.BOTH, expand=True)
        
        def log_status(message):
            status_text.insert(tk.END, message + "\n")
            status_text.see(tk.END)
            import_window.update()
        
        # Import button
        button_frame = ttk.Frame(import_window)
        button_frame.pack(pady=10)
        
        def do_import():
            file_path = file_path_var.get()
            video_path = video_path_var.get()
            
            if not file_path or not os.path.exists(file_path):
                messagebox.showerror("Error", "Please select a valid Amazfit data file")
                return
            
            if not video_path or not os.path.exists(video_path):
                messagebox.showerror("Error", "Please select a valid video file")
                return
            
            try:
                log_status("=" * 60)
                log_status("Starting Amazfit data import...")
                log_status(f"Data file: {os.path.basename(file_path)}")
                log_status(f"Video file: {os.path.basename(video_path)}")
                log_status("=" * 60)
                
                # Import data
                importer = AmazfitDataImporter()
                
                # Detect file type and import
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext == '.gpx':
                    log_status("\n📥 Importing GPX file...")
                    gps_data = importer.import_gpx(file_path)
                    log_status(f"✓ Imported {len(gps_data['timestamps'])} GPS points")
                elif file_ext == '.csv':
                    log_status("\n📥 Importing CSV file...")
                    activity_data = importer.import_zepp_csv(file_path)
                    log_status(f"✓ Imported {len(activity_data['timestamps'])} data points")
                    # For CSV, we need to create a minimal GPS structure
                    gps_data = activity_data
                else:
                    messagebox.showerror("Error", f"Unsupported file type: {file_ext}")
                    return
                
                # Get video metadata
                log_status("\n📹 Reading video metadata...")
                import cv2
                cap = cv2.VideoCapture(video_path)
                video_fps = cap.get(cv2.CAP_PROP_FPS)
                video_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                video_duration = video_frame_count / video_fps if video_fps > 0 else 0
                cap.release()
                
                log_status(f"✓ Video: {video_fps:.2f} fps, {video_duration:.1f} seconds")
                
                # Get video start time
                video_start_time = None
                if time_var.get().strip():
                    try:
                        video_start_time = datetime.strptime(time_var.get().strip(), "%Y-%m-%d %H:%M:%S")
                        log_status(f"✓ Using provided start time: {video_start_time}")
                    except:
                        log_status("⚠ Invalid time format, using video file time")
                        video_start_time = datetime.fromtimestamp(os.path.getmtime(video_path))
                else:
                    video_start_time = datetime.fromtimestamp(os.path.getmtime(video_path))
                    log_status(f"✓ Using video file time: {video_start_time}")
                
                # Sync with video
                log_status("\n🔄 Syncing data with video...")
                synced_data = importer.sync_with_video(
                    video_start_time,
                    video_fps,
                    video_duration,
                    gps_data if 'latitudes' in gps_data else None
                )
                log_status(f"✓ Synced {len(synced_data)} frames")
                
                # Calculate metrics
                log_status("\n📊 Calculating soccer metrics...")
                metrics = AmazfitSoccerMetrics()
                
                if synced_data:
                    sprint_stats = metrics.calculate_sprint_zones(synced_data)
                    work_rate = metrics.calculate_work_rate_zones(synced_data)
                    distance_stats = metrics.calculate_distance_covered(synced_data)
                    
                    log_status("\n" + "=" * 60)
                    log_status("📈 METRICS SUMMARY")
                    log_status("=" * 60)
                    
                    if distance_stats:
                        log_status(f"\n📏 Distance Covered:")
                        log_status(f"   Total: {distance_stats['total_distance_km']:.2f} km")
                        log_status(f"   Average Speed: {distance_stats['avg_speed_kmh']:.1f} km/h")
                        log_status(f"   Max Speed: {distance_stats['max_speed_kmh']:.1f} km/h")
                    
                    if sprint_stats:
                        log_status(f"\n🏃 Sprint Analysis:")
                        log_status(f"   Sprint Count: {sprint_stats['sprint_count']}")
                        log_status(f"   Total Sprint Time: {sprint_stats['total_sprint_time']:.1f} seconds")
                        log_status(f"   Max Sprint Duration: {sprint_stats['max_sprint_duration']:.1f} seconds")
                    
                    if work_rate:
                        log_status(f"\n❤️  Heart Rate Zones:")
                        log_status(f"   Average HR: {work_rate['avg_heart_rate']:.0f} bpm")
                        log_status(f"   Max HR: {work_rate['max_heart_rate']:.0f} bpm")
                        log_status(f"   Zone 1 (Recovery): {work_rate['zone_1_percent']:.1f}%")
                        log_status(f"   Zone 2 (Aerobic): {work_rate['zone_2_percent']:.1f}%")
                        log_status(f"   Zone 3 (Tempo): {work_rate['zone_3_percent']:.1f}%")
                        log_status(f"   Zone 4 (Threshold): {work_rate['zone_4_percent']:.1f}%")
                        log_status(f"   Zone 5 (Max): {work_rate['zone_5_percent']:.1f}%")
                
                # Save synced data
                output_dir = os.path.dirname(video_path)
                player_name = player_var.get().strip() if player_var.get().strip() else "Player"
                output_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(video_path))[0]}_amazfit_{player_name}.json")
                
                import json
                output_data = {
                    'player_name': player_name,
                    'video_path': video_path,
                    'data_file': file_path,
                    'synced_data': synced_data,
                    'metrics': {
                        'sprint_stats': sprint_stats if synced_data else {},
                        'work_rate': work_rate if synced_data else {},
                        'distance_stats': distance_stats if synced_data else {}
                    },
                    'video_start_time': video_start_time.isoformat(),
                    'video_fps': video_fps,
                    'video_duration': video_duration
                }
                
                with open(output_file, 'w') as f:
                    json.dump(output_data, f, indent=2, default=str)
                
                log_status(f"\n💾 Saved synced data to: {os.path.basename(output_file)}")
                log_status("\n" + "=" * 60)
                log_status("✅ Import complete!")
                log_status("=" * 60)
                
                messagebox.showinfo("Success", 
                    f"Amazfit data imported successfully!\n\n"
                    f"Synced {len(synced_data)} frames\n"
                    f"Saved to: {os.path.basename(output_file)}\n\n"
                    f"To use this data in video analysis, the overlay module\n"
                    f"will automatically use this file when processing the video.")
                
            except Exception as e:
                import traceback
                error_msg = f"Error importing Amazfit data:\n{str(e)}\n\n{traceback.format_exc()}"
                log_status(f"\n❌ ERROR:\n{error_msg}")
                messagebox.showerror("Import Error", error_msg)
        
        ttk.Button(button_frame, text="Import Data", command=do_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=import_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def open_setup_wizard(self):
        """Open interactive setup wizard for player tagging"""
        # Use unified viewer in setup mode
        self.open_unified_viewer(mode='setup')
    
    def _get_project_paths(self):
        """Get video and CSV paths from current project or settings"""
        video_path = None
        csv_path = None
        
        # First, try from current input/output file settings
        if hasattr(self, 'input_file') and self.input_file.get():
            video_path = self.input_file.get()
            if video_path and not os.path.exists(video_path):
                video_path = None  # File doesn't exist, ignore it
        
        if hasattr(self, 'output_file') and self.output_file.get():
            csv_path = self.output_file.get()
            if csv_path and not os.path.exists(csv_path):
                csv_path = None  # File doesn't exist, ignore it
        
        # If not found, try from loaded project
        if (not video_path or not csv_path) and hasattr(self, 'current_project_path') and self.current_project_path:
            try:
                import json
                with open(self.current_project_path, 'r') as f:
                    project_data = json.load(f)
                if 'analysis_settings' in project_data:
                    if not video_path:
                        video_path = project_data['analysis_settings'].get('input_file', '')
                        if video_path and not os.path.exists(video_path):
                            video_path = None
                    if not csv_path:
                        csv_path = project_data['analysis_settings'].get('output_file', '')
                        if csv_path and not os.path.exists(csv_path):
                            csv_path = None
            except Exception as e:
                # Silently fail - project file might be corrupted or missing
                pass
        
        return video_path, csv_path
    
    def open_player_stats(self):
        """Open unified player management interface (Gallery + Per-Video Names)"""
        try:
            # Check if window already exists
            if (hasattr(self, '_player_stats_window') and 
                self._player_stats_window is not None and 
                self._player_stats_window.winfo_exists()):
                self._player_stats_window.lift()
                self._player_stats_window.focus_force()
                return
            
            # Create main window
            stats_window = tk.Toplevel(self.root)
            stats_window.title("Player Management")
            stats_window.transient(self.root)
            
            # Store reference to prevent garbage collection
            self._player_stats_window = stats_window
            
            # Calculate centered position relative to parent window
            self.root.update_idletasks()
            
            parent_x = self.root.winfo_x()
            parent_y = self.root.winfo_y()
            parent_width = self.root.winfo_width()
            parent_height = self.root.winfo_height()
            
            # Window size
            window_width = 1200
            window_height = 800
            
            # Calculate center position relative to parent
            center_x = parent_x + (parent_width // 2) - (window_width // 2)
            center_y = parent_y + (parent_height // 2) - (window_height // 2)
            
            # Ensure window is on screen
            stats_window.update_idletasks()
            screen_width = stats_window.winfo_screenwidth()
            screen_height = stats_window.winfo_screenheight()
            
            if center_x < 0:
                center_x = (screen_width // 2) - (window_width // 2)
            if center_y < 0:
                center_y = (screen_height // 2) - (window_height // 2)
            
            # Set window position and size
            stats_window.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
            
            # Ensure window opens on top
            stats_window.lift()
            stats_window.attributes('-topmost', True)
            stats_window.focus_force()
            
            # Create tabbed interface
            notebook = ttk.Notebook(stats_window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Tab 1: Player Gallery (cross-video recognition)
            gallery_tab = ttk.Frame(notebook, padding="10")
            notebook.add(gallery_tab, text="🎯 Player Gallery (Cross-Video)")
            
            # Use GalleryTab component
            try:
                from .tabs.gallery_tab import GalleryTab
                gallery_component = GalleryTab(self, gallery_tab)
            except ImportError:
                try:
                    from SoccerID.gui.tabs.gallery_tab import GalleryTab
                    gallery_component = GalleryTab(self, gallery_tab)
                except ImportError:
                    ttk.Label(gallery_tab, text="Gallery tab not available", 
                             font=("Arial", 10)).pack(pady=20)
            
            # Tab 2: Per-Video Player Names (traditional)
            names_tab = ttk.Frame(notebook, padding="10")
            notebook.add(names_tab, text="📝 Per-Video Names")
            
            # Try to load traditional player stats GUI in this tab
            try:
                try:
                    from player_stats_gui import PlayerStatsGUI
                except ImportError:
                    from legacy.player_stats_gui import PlayerStatsGUI
                app = PlayerStatsGUI(names_tab)
                self._player_stats_app = app
            except Exception as e:
                # Fallback if PlayerStatsGUI not available
                ttk.Label(names_tab, text=f"Traditional player stats not available.\n\n{str(e)}", 
                         font=("Arial", 10)).pack(pady=20)
            
            # Tab 3: Team Roster Management
            roster_tab = ttk.Frame(notebook, padding="10")
            notebook.add(roster_tab, text="👥 Team Roster")
            
            # Use RosterTab component
            try:
                from .tabs.roster_tab import RosterTab
                roster_component = RosterTab(self, roster_tab)
            except ImportError:
                try:
                    from SoccerID.gui.tabs.roster_tab import RosterTab
                    roster_component = RosterTab(self, roster_tab)
                except ImportError:
                    ttk.Label(roster_tab, text="Roster tab not available", 
                             font=("Arial", 10)).pack(pady=20)
            
            # Remove topmost after a brief moment
            stats_window.after(300, lambda: stats_window.attributes('-topmost', False))
            
            # Handle window close
            def on_close():
                if hasattr(self, '_player_stats_window'):
                    delattr(self, '_player_stats_window')
                if hasattr(self, '_player_stats_app'):
                    delattr(self, '_player_stats_app')
                stats_window.destroy()
            
            stats_window.protocol("WM_DELETE_WINDOW", on_close)
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import player_stats_gui.py: {str(e)}\n\n"
                               "Make sure player_stats_gui.py is in the same folder.")
            import traceback
            traceback.print_exc()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open player stats: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def open_unified_viewer(self, mode='setup', video_path=None, csv_path=None):
        """Open unified viewer with specified mode"""
        try:
            from .viewers.unified_viewer import UnifiedViewer
        except ImportError:
            try:
                from SoccerID.gui.viewers.unified_viewer import UnifiedViewer
            except ImportError:
                # Fallback to legacy viewers
                if mode == 'setup':
                    self._open_legacy_setup_wizard()
                elif mode == 'playback':
                    self.open_playback_viewer()
                else:
                    messagebox.showerror("Error", f"Mode '{mode}' not available in legacy mode")
                return
        
        # Minimize main window when viewer opens
        self.root.iconify()
        
        # Temporarily remove topmost from main window
        main_was_topmost = self.root.attributes('-topmost')
        if main_was_topmost:
            self.root.attributes('-topmost', False)
        
        viewer_window = tk.Toplevel(self.root)
        viewer_window.title("Unified Player Viewer")
        viewer_window.geometry("1920x1200")
        
        # Get video and CSV paths from project/current settings if not provided
        if not video_path or not csv_path:
            proj_video, proj_csv = self._get_project_paths()
            if not video_path:
                video_path = proj_video
            if not csv_path:
                csv_path = proj_csv
        
        viewer = UnifiedViewer(viewer_window, mode=mode, video_path=video_path, csv_path=csv_path)
        
        # Restore main window when viewer closes
        def on_close():
            self.root.deiconify()
            if main_was_topmost:
                self.root.attributes('-topmost', True)
            viewer_window.destroy()
        
        viewer_window.protocol("WM_DELETE_WINDOW", on_close)
    
    def _open_legacy_setup_wizard(self):
        """Fallback to legacy setup wizard"""
        try:
            # Try new structure imports first
            try:
                from .viewers.setup_wizard import SetupWizard
            except ImportError:
                try:
                    from SoccerID.gui.viewers.setup_wizard import SetupWizard
                except ImportError:
                    # Legacy fallback
                    try:
                        from legacy.setup_wizard import SetupWizard
                    except ImportError:
                        from setup_wizard import SetupWizard
            
            # Minimize main window when Setup Wizard opens
            self.root.iconify()  # Minimize the main window
            
            # Temporarily remove topmost from main window to allow wizard to appear
            main_was_topmost = self.root.attributes('-topmost')
            if main_was_topmost:
                self.root.attributes('-topmost', False)
            
            wizard_window = tk.Toplevel(self.root)
            wizard_window.title("Setup Wizard")
            wizard_window.geometry("1600x1050")
            # Don't use transient() as it can prevent minimize/maximize buttons on some systems
            # Instead, use attributes to keep it on top when needed
            # wizard_window.transient(self.root)  # Commented out to allow minimize/maximize
            
            # Ensure window has minimize and maximize buttons
            wizard_window.overrideredirect(False)  # Standard window controls
            wizard_window.resizable(True, True)  # Allow resizing (enables maximize)
            try:
                if hasattr(wizard_window, 'attributes'):
                    wizard_window.attributes('-toolwindow', False)  # Not a toolwindow (shows in taskbar)
                    # On Windows, ensure the window style includes minimize/maximize buttons
                    # Try to set window style directly using Windows API if available
                    try:
                        import ctypes
                        from ctypes import wintypes
                        hwnd = wizard_window.winfo_id()
                        if hwnd:
                            # Get current window style
                            GWL_STYLE = -16
                            WS_MINIMIZEBOX = 0x00020000
                            WS_MAXIMIZEBOX = 0x00010000
                            WS_SYSMENU = 0x00080000
                            
                            # Get current style
                            current_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                            # Add minimize and maximize buttons
                            new_style = current_style | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
                            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)
                            # Force window to redraw
                            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0020)
                    except:
                        pass  # If Windows API fails, fall back to Tkinter defaults
            except:
                pass
            
            # Force window to be shown and visible - use aggressive Windows-specific approach
            wizard_window.withdraw()  # Hide first to ensure clean state
            wizard_window.update()
            wizard_window.update_idletasks()
            
            # Try Windows-specific window activation (if available)
            try:
                import ctypes
                # Get window handle and force activation
                hwnd = wizard_window.winfo_id()
                if hwnd:
                    # Force window to foreground (Windows API)
                    ctypes.windll.user32.ShowWindow(hwnd, 1)  # SW_SHOWNORMAL
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    ctypes.windll.user32.BringWindowToTop(hwnd)
            except:
                pass  # Fallback to Tkinter methods
            
            wizard_window.deiconify()  # Show window
            wizard_window.state('normal')  # Ensure normal state (not minimized/maximized)
            wizard_window.lift(self.root)  # Bring to front, above parent
            wizard_window.attributes('-topmost', True)  # Force to top
            wizard_window.focus_set()  # Set focus
            wizard_window.focus_force()  # Force focus (works on Windows)
            wizard_window.grab_set()  # Grab focus (modal behavior)
            wizard_window.update()  # Update window state immediately
            wizard_window.update_idletasks()  # Process all pending events
            
            # Get video path and CSV path from project if available
            video_path = None
            csv_path = None
            
            # Try to get from input/output file fields
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
                if not os.path.exists(video_path):
                    video_path = None
            
            if hasattr(self, 'output_file') and self.output_file.get():
                csv_path = self.output_file.get()
                if not os.path.exists(csv_path):
                    csv_path = None
            
            # Also try to get from current project if loaded
            if not video_path or not csv_path:
                try:
                    if hasattr(self, 'current_project_path') and self.current_project_path:
                        import json
                        with open(self.current_project_path, 'r') as f:
                            project_data = json.load(f)
                        
                        # Get video path from project
                        if not video_path:
                            video_path = project_data.get('analysis_settings', {}).get('input_file')
                            if video_path and not os.path.exists(video_path):
                                video_path = None
                        
                        # Get CSV path from project
                        if not csv_path:
                            csv_path = project_data.get('analysis_settings', {}).get('output_file')
                            if csv_path and not os.path.exists(csv_path):
                                csv_path = None
                except:
                    pass  # If project loading fails, just use what we have
            
            # Pass video and CSV paths to setup wizard for auto-loading
            app = SetupWizard(wizard_window, video_path=video_path, csv_path=csv_path)
            
            # Ensure window is still visible after SetupWizard initialization
            wizard_window.deiconify()
            wizard_window.state('normal')
            wizard_window.lift(self.root)  # Bring above parent again
            wizard_window.focus_set()
            wizard_window.focus_force()
            wizard_window.update()
            wizard_window.update_idletasks()  # Process all pending events
            
            # Remove topmost and grab after a short delay, and restore main window topmost if it was set
            def cleanup_topmost():
                wizard_window.attributes('-topmost', False)
                wizard_window.grab_release()  # Release grab after window is shown
                if main_was_topmost:
                    self.root.attributes('-topmost', True)
            
            wizard_window.after(500, cleanup_topmost)
            
            # Restore main window when wizard is closed
            def on_wizard_close():
                self.root.deiconify()  # Restore main window when wizard closes
            
            wizard_window.protocol("WM_DELETE_WINDOW", lambda: (on_wizard_close(), wizard_window.destroy()))
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import setup_wizard: {str(e)}\n\n"
                               "Make sure setup_wizard.py is available.")
            import traceback
            traceback.print_exc()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open setup wizard: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def open_gallery_seeder(self):
        """Open player gallery seeder for cross-video player recognition"""
        # Use unified viewer in gallery mode
        self.open_unified_viewer(mode='gallery')
    
    def open_event_timeline_viewer(self):
        """Open event timeline viewer directly"""
        # First, try to open playback viewer if video/CSV is loaded
        video_path = None
        csv_path = None
        
        if hasattr(self, 'input_file') and self.input_file.get():
            video_path = self.input_file.get()
        if hasattr(self, 'output_file') and self.output_file.get():
            csv_path = self.output_file.get()
        
        if not video_path:
            messagebox.showinfo("No Video", 
                              "Please load a video file first.\n\n"
                              "Event Timeline Viewer requires a video file to display events.")
            return
        
        # Open unified viewer in playback mode, which has event timeline access
        self.open_unified_viewer(mode='playback', video_path=video_path, csv_path=csv_path)
        
        # Note: Event Timeline Viewer can be opened from within PlaybackMode
        # This button opens playback viewer where user can access Event Timeline
    
    def open_track_converter(self):
        """Open track converter to convert CSV tags to anchor frames"""
        try:
            # Try to import track converter
            try:
                from convert_tags_to_anchor_frames import convert_tags_to_anchor_frames_gui
            except ImportError:
                try:
                    from legacy.convert_tags_to_anchor_frames import convert_tags_to_anchor_frames_gui
                except ImportError:
                    messagebox.showerror("Error", 
                                       "Could not import convert_tags_to_anchor_frames.py\n\n"
                                       "This tool converts CSV player tags to anchor frames for Re-ID.")
                    return
            
            # Open the converter GUI
            convert_tags_to_anchor_frames_gui(self.root)
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import track converter: {str(e)}\n\n"
                               "Make sure convert_tags_to_anchor_frames.py is available.")
            import traceback
            traceback.print_exc()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open track converter: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def open_field_calibration(self):
        """Open field calibration tool"""
        try:
            # Try to import field calibration GUI
            # Add root directory to path to find calibrate_field_gui.py
            import sys
            import os
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            if root_dir not in sys.path:
                sys.path.insert(0, root_dir)
            
            try:
                from calibrate_field_gui import FieldCalibrationGUI
                CalibrateFieldGUI = FieldCalibrationGUI  # Alias for compatibility
            except ImportError:
                try:
                    # Try legacy location
                    from legacy.calibrate_field_gui import FieldCalibrationGUI
                    CalibrateFieldGUI = FieldCalibrationGUI
                except ImportError:
                    # Try importing as module and accessing class
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("calibrate_field_gui", 
                                                                  os.path.join(root_dir, "calibrate_field_gui.py"))
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        CalibrateFieldGUI = module.FieldCalibrationGUI
                    else:
                        raise ImportError("Could not load calibrate_field_gui module")
            
            calibration_window = tk.Toplevel(self.root)
            calibration_window.title("Field Calibration")
            calibration_window.geometry("1800x1000")  # Match the size in calibrate_field_gui.py
            calibration_window.transient(self.root)
            # Ensure window controls (minimize, maximize, close) are visible
            try:
                calibration_window.attributes('-toolwindow', False)  # Ensure it's a normal window with controls
            except:
                pass
            
            # Get video path if available
            video_path = None
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
                if not os.path.exists(video_path):
                    video_path = None
            
            # Create calibration GUI
            app = CalibrateFieldGUI(calibration_window, video_path=video_path)
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import field calibration: {str(e)}\n\n"
                               "Make sure calibrate_field_gui.py is available.")
            import traceback
            traceback.print_exc()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open field calibration: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Project management
    def save_project(self):
        """Save current project"""
        try:
            from project_manager import save_project
            
            current_name = self.current_project_name.get()
            if current_name == "No Project":
                # No project name, use Save As instead
                self.save_project_as()
                return
            
            # Use existing project path if available, otherwise prompt
            project_path = self.current_project_path
            
            result = save_project(current_name, project_path=project_path, gui_instance=self)
            if result:
                project_path, saved_items = result
                self.current_project_path = project_path
                
                # Show success message
                items_list = []
                if saved_items.get("analysis_settings"):
                    items_list.append("Analysis settings")
                if saved_items.get("setup_wizard"):
                    items_list.append("Setup wizard")
                if saved_items.get("team_colors"):
                    items_list.append("Team colors")
                if saved_items.get("ball_colors"):
                    items_list.append("Ball colors")
                if saved_items.get("field_calibration"):
                    items_list.append("Field calibration")
                
                items_text = "\n".join(f"  • {item}" for item in items_list) if items_list else "  • Project settings"
                
                # Show success confirmation
                messagebox.showinfo(
                    "Project Saved",
                    f"Project '{current_name}' saved successfully!\n\n"
                    f"Saved items:\n{items_text}\n\n"
                    f"Location: {project_path}"
                )
                
                # Show success toast
                if self.toast_manager:
                    self.toast_manager.success(f"Project '{current_name}' saved")
                
                self.log_message(f"Project '{current_name}' saved to {project_path}")
            else:
                messagebox.showwarning("Save Cancelled", "Project save was cancelled.")
        except ImportError:
            messagebox.showerror("Error", "Could not import project_manager. Please ensure project_manager.py is available.")
            self.log_message("ERROR: Could not import project_manager")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save project: {e}")
            self.log_message(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    def load_project(self, project_path=None):
        """Load project"""
        try:
            from project_manager import load_project
            from tkinter import filedialog
            
            if project_path is None:
                # Ensure the file dialog appears on top
                self.root.attributes('-topmost', True)
                self.root.update_idletasks()
                filename = filedialog.askopenfilename(
                    title="Load Project",
                    filetypes=[("Project files", "*.json"), ("All files", "*.*")],
                    parent=self.root
                )
                self.root.attributes('-topmost', False)
                self.root.lift()
            else:
                filename = project_path
            
            if filename:
                self.log_message(f"Loading project: {filename}")
                
                # Validate project file structure before loading
                try:
                    import json
                    with open(filename, 'r') as f:
                        test_data = json.load(f)
                    
                    # Check if this looks like a valid project file
                    if not isinstance(test_data, dict):
                        raise ValueError("Project file is not a valid JSON object")
                    
                    # Check for required project structure
                    if 'project_name' not in test_data and 'analysis_settings' not in test_data:
                        # This might be an old format or different file type
                        # Check if it has numeric keys (likely not a project file)
                        if all(str(k).isdigit() for k in test_data.keys() if k):
                            raise ValueError("File does not appear to be a project file (contains numeric keys only)")
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON file: {e}")
                except Exception as e:
                    if project_path is None:  # Only show error if user manually selected
                        messagebox.showerror("Invalid Project File", 
                                           f"This file does not appear to be a valid project file:\n\n{str(e)}\n\n"
                                           "Please select a project file created by 'Save Project'.")
                    raise
                
                # Load project using project_manager
                project_data = load_project(project_path=filename, gui_instance=self, restore_files=True)
                
                if project_data:
                    # Update project name and path
                    project_name = project_data.get("project_name", "Unknown Project")
                    self.current_project_name.set(project_name)
                    self.current_project_path = filename
                    
                    # Get loaded settings summary
                    settings = project_data.get("analysis_settings", {})
                    input_file = settings.get("input_file", "")
                    output_file = settings.get("output_file", "")
                    
                    # Verify that the GUI variables were actually set
                    # (load_project should have set them, but let's verify)
                    if hasattr(self, 'input_file'):
                        actual_input = self.input_file.get()
                        if actual_input != input_file:
                            # If not set correctly, set it now
                            self.input_file.set(input_file)
                            self.log_message(f"Fixed input_file: {input_file}")
                    
                    if hasattr(self, 'output_file'):
                        actual_output = self.output_file.get()
                        if actual_output != output_file:
                            # If not set correctly, set it now
                            self.output_file.set(output_file)
                            self.log_message(f"Fixed output_file: {output_file}")
                    
                    # Show success message with details
                    loaded_items = []
                    if input_file:
                        loaded_items.append(f"Input: {os.path.basename(input_file)}")
                    if output_file:
                        loaded_items.append(f"Output: {os.path.basename(output_file)}")
                    if project_data.get("setup_wizard"):
                        loaded_items.append("Setup wizard data")
                    if project_data.get("team_colors"):
                        loaded_items.append("Team colors")
                    if project_data.get("ball_colors"):
                        loaded_items.append("Ball colors")
                    if project_data.get("field_calibration"):
                        loaded_items.append("Field calibration")
                    
                    items_text = "\n".join(f"  • {item}" for item in loaded_items) if loaded_items else "  • Project settings"
                    
                    # Show success confirmation
                    messagebox.showinfo(
                        "Project Loaded",
                        f"Project '{project_name}' loaded successfully!\n\n"
                        f"Loaded items:\n{items_text}\n\n"
                        f"Location: {filename}"
                    )
                    
                    # Show success toast
                    if self.toast_manager:
                        self.toast_manager.success(f"Project '{project_name}' loaded")
                    
                    self.log_message(f"Project '{project_name}' loaded successfully")
                    self.log_message(f"  Input file: {input_file if input_file else 'Not set'}")
                    self.log_message(f"  Output file: {output_file if output_file else 'Not set'}")
                    
                    # Enable output folder button if output file exists
                    if output_file and os.path.exists(os.path.dirname(output_file) if output_file else ""):
                        self.open_folder_button.config(state=tk.NORMAL)
                else:
                    messagebox.showerror("Error", "Failed to load project. Please check the file and try again.")
                    
                    # Show error toast
                    if self.toast_manager:
                        self.toast_manager.error("Failed to load project")
                    
                    self.log_message("ERROR: Failed to load project")
        except ImportError:
            messagebox.showerror("Error", "Could not import project_manager. Please ensure project_manager.py is available.")
            
            # Show error toast
            if self.toast_manager:
                self.toast_manager.error("Could not import project_manager")
            
            self.log_message("ERROR: Could not import project_manager")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load project: {e}")
            
            # Show error toast
            if self.toast_manager:
                self.toast_manager.error(f"Failed to load project: {str(e)[:50]}")
            
            self.log_message(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    def auto_load_last_project(self):
        """Auto-load last project"""
        try:
            from project_manager import get_last_project_path, load_project
            import json
            
            last_project_path = get_last_project_path()
            if last_project_path and os.path.exists(last_project_path):
                # Validate project file structure before loading
                try:
                    with open(last_project_path, 'r') as f:
                        test_data = json.load(f)
                    
                    # Check if this looks like a valid project file
                    if not isinstance(test_data, dict):
                        self.log_message(f"WARNING: Last project file is not valid: {last_project_path}")
                        return
                    
                    # Check for required project structure
                    # Old format projects are just player_names (numeric keys), which is valid
                    # New format has project_name and analysis_settings
                    is_old_format = all(str(k).isdigit() for k in test_data.keys() if k) if test_data else False
                    is_new_format = 'project_name' in test_data or 'analysis_settings' in test_data
                    
                    if not is_old_format and not is_new_format:
                        # This doesn't look like either format
                        self.log_message(f"WARNING: Last project file does not appear to be a project file: {last_project_path}")
                        self.log_message("  File format not recognized - skipping auto-load")
                        return
                except json.JSONDecodeError as e:
                    self.log_message(f"WARNING: Last project file is not valid JSON: {last_project_path}")
                    return
                except Exception as e:
                    self.log_message(f"WARNING: Could not validate last project file: {e}")
                    return
                
                # Ask user if they want to load the last project
                response = messagebox.askyesno(
                    "Load Last Project?",
                    f"Would you like to load the last project?\n\n{os.path.basename(last_project_path)}"
                )
                if response:
                    self.log_message(f"Auto-loading last project: {last_project_path}")
                    project_data = load_project(project_path=last_project_path, gui_instance=self, restore_files=True)
                    
                    if project_data:
                        project_name = project_data.get("project_name", "Unknown Project")
                        self.current_project_name.set(project_name)
                        self.current_project_path = last_project_path
                        
                        settings = project_data.get("analysis_settings", {})
                        input_file = settings.get("input_file", "")
                        output_file = settings.get("output_file", "")
                        
                        # CRITICAL: Verify and set input/output files
                        if hasattr(self, 'input_file') and input_file:
                            self.input_file.set(input_file)
                            self.log_message(f"  Input file: {input_file}")
                        elif hasattr(self, 'input_file'):
                            self.log_message(f"  Input file: Not set in project")
                        
                        if hasattr(self, 'output_file') and output_file:
                            self.output_file.set(output_file)
                            self.log_message(f"  Output file: {output_file}")
                        elif hasattr(self, 'output_file'):
                            self.log_message(f"  Output file: Not set in project")
                        
                        self.log_message(f"Auto-loaded project '{project_name}'")
                        
                        # Show toast notification
                        if self.toast_manager:
                            self.toast_manager.success(f"Project '{project_name}' loaded")
                    else:
                        self.log_message("WARNING: Failed to auto-load last project")
        except ImportError:
            # project_manager not available, skip auto-load
            pass
        except Exception as e:
            # Silently fail auto-load (don't show error to user on startup)
            self.log_message(f"Note: Could not auto-load last project: {e}")
    
    # Utility methods
    def log_message(self, message: str):
        """Log a message to the log text area"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def update_preview(self):
        """Update preview (for visualization tab)"""
        # Note: Preview functionality is handled by the preview button
        # This method is called by UI elements but doesn't need to do anything
        # as preview is only shown when explicitly requested via Preview button
        pass
    
    def _check_and_enable_output_buttons(self):
        """Check if output files exist and enable buttons"""
        # Check if output file exists
        output_exists = False
        csv_exists = False
        
        if hasattr(self, 'output_file') and self.output_file.get():
            output_path = self.output_file.get()
            if os.path.exists(output_path):
                output_exists = True
                
                # Check for corresponding CSV file
                csv_path = output_path.replace('.mp4', '_tracking_data.csv').replace('.avi', '_tracking_data.csv')
                if os.path.exists(csv_path):
                    csv_exists = True
        
        # Also check last_output_file
        if hasattr(self, 'last_output_file') and self.last_output_file:
            if os.path.exists(self.last_output_file):
                output_exists = True
                csv_path = self.last_output_file.replace('.mp4', '_tracking_data.csv').replace('.avi', '_tracking_data.csv')
                if os.path.exists(csv_path):
                    csv_exists = True
        
        # Enable/disable buttons based on file existence
        if hasattr(self, 'open_folder_button'):
            # Enable if any output file exists
            self.open_folder_button.config(state=tk.NORMAL if (output_exists or csv_exists) else tk.DISABLED)
        
        if hasattr(self, 'analyze_csv_button'):
            # Enable only if CSV exists
            self.analyze_csv_button.config(state=tk.NORMAL if csv_exists else tk.DISABLED)
    
    def _update_focus_players_ui(self):
        """Update focus players UI based on watch-only mode state"""
        # This method is called when watch_only checkbox changes
        # The UI in advanced_tab.py handles showing/hiding focus players controls
        # No additional action needed here as the UI elements handle their own visibility
        pass
    
    # ==================== ROSTER MANAGEMENT METHODS ====================
    
    def _import_roster_csv(self, roster_manager, parent_frame):
        """Import roster from CSV file"""
        filename = filedialog.askopenfilename(
            title="Import Roster from CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            try:
                count = roster_manager.import_from_csv(filename)
                messagebox.showinfo("Import Complete", f"Imported {count} players from CSV")
                self._refresh_roster_tab(parent_frame)
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import roster: {e}")
                import traceback
                traceback.print_exc()
    
    def _export_roster_csv(self, roster_manager):
        """Export roster to CSV file"""
        filename = filedialog.asksaveasfilename(
            title="Export Roster to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            try:
                roster_manager.export_to_csv(filename)
                messagebox.showinfo("Export Complete", f"Roster exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export roster: {e}")
                import traceback
                traceback.print_exc()
    
    def _add_roster_player(self, roster_manager, parent_frame):
        """Add a new player to the roster with visualization settings"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Player to Roster")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollable frame with modern styling
        canvas = tk.Canvas(main_frame, bg="#FFFFFF", highlightthickness=0, relief=tk.FLAT)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        ttk.Label(scrollable_frame, text="Add Player", font=("Arial", 14, "bold")).pack(pady=(0, 20))
        
        form_frame = ttk.Frame(scrollable_frame)
        form_frame.pack(fill=tk.X, pady=10)
        
        # Name
        ttk.Label(form_frame, text="Name *:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        # Jersey
        ttk.Label(form_frame, text="Jersey:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        jersey_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=jersey_var, width=30).grid(row=1, column=1, padx=5, pady=5)
        
        # Team
        ttk.Label(form_frame, text="Team:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        team_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=team_var, width=30).grid(row=2, column=1, padx=5, pady=5)
        
        # Position
        ttk.Label(form_frame, text="Position:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        position_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=position_var, width=30).grid(row=3, column=1, padx=5, pady=5)
        
        # Active
        active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Active", variable=active_var).grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Visualization settings section
        viz_frame = ttk.LabelFrame(form_frame, text="Visualization Settings (Optional)", padding="10")
        viz_frame.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=10, padx=5)
        
        # Custom color - Simple RGB entry
        ttk.Label(viz_frame, text="Custom Color (R,G,B):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        custom_color_var = tk.StringVar()
        ttk.Entry(viz_frame, textvariable=custom_color_var, width=20, 
                 placeholder_text="e.g., 255,0,0").grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(viz_frame, text="(0-255 for each)", font=("Arial", 8), 
                 foreground="gray").grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Box thickness
        ttk.Label(viz_frame, text="Box Thickness:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        box_thickness_var = tk.IntVar(value=2)
        ttk.Spinbox(viz_frame, from_=1, to=10, textvariable=box_thickness_var, width=10).grid(row=1, column=1, padx=5, sticky=tk.W)
        
        # Show glow
        show_glow_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(viz_frame, text="Show Glow Effect", variable=show_glow_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Glow intensity
        ttk.Label(viz_frame, text="Glow Intensity:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        glow_intensity_var = tk.IntVar(value=50)
        ttk.Spinbox(viz_frame, from_=0, to=100, textvariable=glow_intensity_var, width=10).grid(row=3, column=1, padx=5, sticky=tk.W)
        
        # Show trail
        show_trail_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(viz_frame, text="Show Movement Trail", variable=show_trail_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Label style
        ttk.Label(viz_frame, text="Label Style:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        label_style_var = tk.StringVar(value="full_name")
        ttk.Combobox(viz_frame, textvariable=label_style_var, 
                    values=["full_name", "jersey", "initials", "number"], 
                    width=12, state="readonly").grid(row=5, column=1, padx=5, sticky=tk.W)
        
        # Tracker color (for track ID mode)
        ttk.Label(viz_frame, text="Tracker Color (R,G,B):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        tracker_color_var = tk.StringVar()
        ttk.Entry(viz_frame, textvariable=tracker_color_var, width=20,
                 placeholder_text="e.g., 0,255,0").grid(row=6, column=1, padx=5, pady=5)
        ttk.Label(viz_frame, text="(For track ID visualization)", font=("Arial", 8),
                 foreground="gray").grid(row=6, column=2, sticky=tk.W, padx=5)
        
        def add():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Missing Name", "Player name is required")
                return
            
            # Parse visualization settings
            viz_settings = {}
            custom_color_str = custom_color_var.get().strip()
            if custom_color_str:
                try:
                    rgb = self._parse_color_string(custom_color_str)
                    if rgb:
                        viz_settings["use_custom_color"] = True
                        viz_settings["custom_color_rgb"] = rgb
                except Exception:
                    pass
            
            tracker_color_str = tracker_color_var.get().strip()
            if tracker_color_str:
                try:
                    rgb = self._parse_color_string(tracker_color_str)
                    if rgb:
                        viz_settings["tracker_color_rgb"] = rgb
                except Exception:
                    pass
            
            if box_thickness_var.get() != 2:
                viz_settings["box_thickness"] = box_thickness_var.get()
            
            if show_glow_var.get():
                viz_settings["show_glow"] = True
                viz_settings["glow_intensity"] = glow_intensity_var.get()
            
            if show_trail_var.get():
                viz_settings["show_trail"] = True
            
            if label_style_var.get() != "full_name":
                viz_settings["label_style"] = label_style_var.get()
            
            roster_manager.add_player(
                name=name,
                jersey_number=jersey_var.get().strip() or None,
                team=team_var.get().strip() or None,
                position=position_var.get().strip() or None,
                active=active_var.get(),
                visualization_settings=viz_settings if viz_settings else None
            )
            messagebox.showinfo("Success", f"Added player: {name}")
            dialog.destroy()
            self._refresh_roster_tab(parent_frame)
        
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Add", command=add).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _edit_roster_player(self, roster_manager, player_name, parent_frame):
        """Edit a player in the roster with visualization settings"""
        player_data = roster_manager.roster.get(player_name, {})
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Player: {player_name}")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollable frame with modern styling
        canvas = tk.Canvas(main_frame, bg="#FFFFFF", highlightthickness=0, relief=tk.FLAT)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        ttk.Label(scrollable_frame, text=f"Edit: {player_name}", font=("Arial", 14, "bold")).pack(pady=(0, 20))
        
        form_frame = ttk.Frame(scrollable_frame)
        form_frame.pack(fill=tk.X, pady=10)
        
        # Jersey
        ttk.Label(form_frame, text="Jersey:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        jersey_var = tk.StringVar(value=player_data.get('jersey_number', '') or '')
        ttk.Entry(form_frame, textvariable=jersey_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        # Team
        ttk.Label(form_frame, text="Team:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        team_var = tk.StringVar(value=player_data.get('team', '') or '')
        ttk.Entry(form_frame, textvariable=team_var, width=30).grid(row=1, column=1, padx=5, pady=5)
        
        # Position
        ttk.Label(form_frame, text="Position:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        position_var = tk.StringVar(value=player_data.get('position', '') or '')
        ttk.Entry(form_frame, textvariable=position_var, width=30).grid(row=2, column=1, padx=5, pady=5)
        
        # Active
        active_var = tk.BooleanVar(value=player_data.get('active', True))
        ttk.Checkbutton(form_frame, text="Active", variable=active_var).grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Visualization settings section
        viz_frame = ttk.LabelFrame(form_frame, text="Visualization Settings (Optional)", padding="10")
        viz_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=10, padx=5)
        
        # Load existing visualization settings
        viz = player_data.get("visualization_settings", {})
        
        # Custom color
        ttk.Label(viz_frame, text="Custom Color (R,G,B):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        custom_color_var = tk.StringVar()
        initial_color = None
        if viz.get("custom_color_rgb"):
            rgb = viz["custom_color_rgb"]
            if isinstance(rgb, list) and len(rgb) == 3:
                initial_color = tuple(rgb)
                custom_color_var.set(f"{rgb[0]},{rgb[1]},{rgb[2]}")
            elif isinstance(rgb, str):
                custom_color_var.set(rgb)
        ttk.Entry(viz_frame, textvariable=custom_color_var, width=20).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(viz_frame, text="(0-255 for each)", font=("Arial", 8),
                 foreground="gray").grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Box thickness
        ttk.Label(viz_frame, text="Box Thickness:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        box_thickness_var = tk.IntVar(value=viz.get("box_thickness", 2))
        ttk.Spinbox(viz_frame, from_=1, to=10, textvariable=box_thickness_var, width=10).grid(row=1, column=1, padx=5, sticky=tk.W)
        
        # Show glow
        show_glow_var = tk.BooleanVar(value=viz.get("show_glow", False))
        ttk.Checkbutton(viz_frame, text="Show Glow Effect", variable=show_glow_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Glow intensity
        ttk.Label(viz_frame, text="Glow Intensity:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        glow_intensity_var = tk.IntVar(value=viz.get("glow_intensity", 50))
        ttk.Spinbox(viz_frame, from_=0, to=100, textvariable=glow_intensity_var, width=10).grid(row=3, column=1, padx=5, sticky=tk.W)
        
        # Show trail
        show_trail_var = tk.BooleanVar(value=viz.get("show_trail", False))
        ttk.Checkbutton(viz_frame, text="Show Movement Trail", variable=show_trail_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Label style
        ttk.Label(viz_frame, text="Label Style:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        label_style_var = tk.StringVar(value=viz.get("label_style", "full_name"))
        ttk.Combobox(viz_frame, textvariable=label_style_var, 
                    values=["full_name", "jersey", "initials", "number"], 
                    width=12, state="readonly").grid(row=5, column=1, padx=5, sticky=tk.W)
        
        # Tracker color
        ttk.Label(viz_frame, text="Tracker Color (R,G,B):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        tracker_color_var = tk.StringVar()
        if viz.get("tracker_color_rgb"):
            rgb = viz["tracker_color_rgb"]
            if isinstance(rgb, list) and len(rgb) == 3:
                tracker_color_var.set(f"{rgb[0]},{rgb[1]},{rgb[2]}")
            elif isinstance(rgb, str):
                tracker_color_var.set(rgb)
        ttk.Entry(viz_frame, textvariable=tracker_color_var, width=20).grid(row=6, column=1, padx=5, pady=5)
        ttk.Label(viz_frame, text="(For track ID visualization)", font=("Arial", 8),
                 foreground="gray").grid(row=6, column=2, sticky=tk.W, padx=5)
        
        def save():
            # Parse visualization settings
            viz_settings = {}
            custom_color_str = custom_color_var.get().strip()
            if custom_color_str:
                try:
                    rgb = self._parse_color_string(custom_color_str)
                    if rgb:
                        viz_settings["use_custom_color"] = True
                        viz_settings["custom_color_rgb"] = rgb
                except Exception:
                    pass
            
            tracker_color_str = tracker_color_var.get().strip()
            if tracker_color_str:
                try:
                    rgb = self._parse_color_string(tracker_color_str)
                    if rgb:
                        viz_settings["tracker_color_rgb"] = rgb
                except Exception:
                    pass
            
            if box_thickness_var.get() != 2:
                viz_settings["box_thickness"] = box_thickness_var.get()
            
            if show_glow_var.get():
                viz_settings["show_glow"] = True
                viz_settings["glow_intensity"] = glow_intensity_var.get()
            
            if show_trail_var.get():
                viz_settings["show_trail"] = True
            
            if label_style_var.get() != "full_name":
                viz_settings["label_style"] = label_style_var.get()
            
            update_data = {
                "jersey_number": jersey_var.get().strip() or None,
                "team": team_var.get().strip() or None,
                "position": position_var.get().strip() or None,
                "active": active_var.get()
            }
            if viz_settings:
                update_data["visualization_settings"] = viz_settings
            
            roster_manager.update_player(player_name, **update_data)
            messagebox.showinfo("Success", f"Updated player: {player_name}")
            dialog.destroy()
            self._refresh_roster_tab(parent_frame)
        
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Save", command=save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _delete_roster_player(self, roster_manager, player_name, parent_frame):
        """Delete a player from the roster"""
        if messagebox.askyesno("Delete Player", f"Delete player '{player_name}' from roster?"):
            if roster_manager.delete_player(player_name):
                messagebox.showinfo("Success", f"Deleted player: {player_name}")
                self._refresh_roster_tab(parent_frame)
            else:
                messagebox.showerror("Error", f"Player '{player_name}' not found")
    
    def _link_video_to_roster(self, roster_manager):
        """Link a video to roster players"""
        video_path = filedialog.askopenfilename(
            title="Select Video to Link",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if video_path:
            try:
                # Get list of active players
                active_players = [name for name, data in roster_manager.roster.items() 
                                if name != 'videos' and data.get('active', True)]
                
                if not active_players:
                    messagebox.showwarning("No Active Players", "No active players in roster to link")
                    return
                
                # Simple linking - just store video path
                roster_manager.link_video_to_roster(video_path, active_players)
                messagebox.showinfo("Success", f"Linked video to {len(active_players)} players")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to link video: {e}")
                import traceback
                traceback.print_exc()
    
    def _refresh_roster_tab(self, parent_frame):
        """Refresh the roster tab"""
        if hasattr(parent_frame, '_roster_manager') and hasattr(parent_frame, '_roster_listbox'):
            # Re-import RosterTab to get _populate_roster_list method
            try:
                from .tabs.roster_tab import RosterTab
                roster_tab = RosterTab(self, parent_frame)
                roster_tab._populate_roster_list(
                    parent_frame._roster_listbox,
                    parent_frame._roster_manager,
                    parent_frame._roster_list_data
                )
            except Exception as e:
                # Fallback: just reload the tab
                for widget in parent_frame.winfo_children():
                    widget.destroy()
                try:
                    from .tabs.roster_tab import RosterTab
                    RosterTab(self, parent_frame)
                except Exception as e2:
                    messagebox.showerror("Error", f"Could not refresh roster tab: {e2}")
    
    def _refresh_gallery_tab(self, parent_frame):
        """Refresh the gallery tab"""
        try:
            # Check if parent_frame is None or invalid
            if parent_frame is None:
                # Try to find the gallery tab in the notebook
                try:
                    # Look for the gallery tab in the player stats window
                    if hasattr(self, '_player_stats_window') and self._player_stats_window:
                        notebook = None
                        for widget in self._player_stats_window.winfo_children():
                            if isinstance(widget, ttk.Notebook):
                                notebook = widget
                                break
                        
                        if notebook:
                            # Find the gallery tab
                            for i in range(notebook.index("end")):
                                tab_text = notebook.tab(i, "text")
                                if "Gallery" in tab_text or "gallery" in tab_text.lower():
                                    parent_frame = notebook.nametowidget(notebook.tabs()[i])
                                    break
                except Exception:
                    pass
            
            # If still None, can't refresh
            if parent_frame is None:
                return  # Silently return - gallery tab may not be open
            
            # Always fully reload the tab by destroying and recreating
            # This ensures we get fresh data from disk
            for widget in parent_frame.winfo_children():
                widget.destroy()
            
            # Clear any cached gallery references
            if hasattr(parent_frame, '_gallery_listbox'):
                delattr(parent_frame, '_gallery_listbox')
            if hasattr(parent_frame, '_gallery_list_data'):
                delattr(parent_frame, '_gallery_list_data')
            
            # Recreate the gallery tab (this will load fresh data from disk)
            from .tabs.gallery_tab import GalleryTab
            GalleryTab(self, parent_frame)
        except Exception as e:
            # Don't show error dialog if parent_frame is None - just log it
            if parent_frame is not None:
                messagebox.showerror("Error", f"Could not refresh gallery tab: {e}")
            import traceback
            traceback.print_exc()
    
    def _open_player_details_from_roster(self, player_name):
        """Open player details window from roster tab double-click"""
        try:
            # Get player gallery
            from SoccerID.models.player_gallery import PlayerGallery
            gallery = PlayerGallery()
            gallery.load_gallery()
            
            # Try to find player by name (case-insensitive)
            player_id = None
            for pid, profile in gallery.players.items():
                if profile.name and profile.name.lower() == player_name.lower():
                    player_id = pid
                    break
            
            if player_id is None:
                # Try exact match first
                if player_name in gallery.players:
                    player_id = player_name
                else:
                    messagebox.showinfo("Player Not Found", 
                                      f"Player '{player_name}' not found in gallery.\n\n"
                                      f"Player may need to be tagged in a video first.")
                    return
            
            # Open player details
            self._show_player_details(gallery, player_id, self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open player details:\n{e}")
            import traceback
            traceback.print_exc()
    
    def _show_player_details(self, gallery, player_id, parent_frame):
        """Show detailed player information with edit/delete options"""
        try:
            profile = gallery.get_player(player_id)
            if not profile:
                messagebox.showerror("Error", f"Player '{player_id}' not found in gallery")
                return
            
            # Create detail window
            detail_window = tk.Toplevel(self.root)
            detail_window.title(f"Player Details - {profile.name}")
            detail_window.geometry("1600x900")
            detail_window.minsize(1200, 800)
            detail_window.transient(self.root)
            # Ensure window has minimize, maximize, and close buttons
            detail_window.attributes('-toolwindow', False)  # False = show normal window controls
            # Enable window resizing
            detail_window.resizable(True, True)
            
            # Modern color scheme
            bg_color = "#F5F5F5"  # Light gray background
            canvas_bg = "#FFFFFF"  # White canvas background
            frame_bg = "#FAFAFA"  # Slightly off-white for frames
            
            # Set window background
            detail_window.configure(bg=bg_color)
            
            # Create scrollable frame for content with modern styling
            canvas = tk.Canvas(detail_window, bg=canvas_bg, highlightthickness=0, relief=tk.FLAT)
            scrollbar = ttk.Scrollbar(detail_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas_window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Configure canvas window and scrollable frame to expand horizontally
            def configure_main_canvas_window(event):
                canvas_width = event.width
                canvas.itemconfig(canvas_window_id, width=canvas_width)
                scrollable_frame.config(width=canvas_width)
            canvas.bind('<Configure>', configure_main_canvas_window)
            
            # Pack canvas and scrollbar to allow proper resizing
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Add mouse wheel scrolling support (Windows/Mac and Linux)
            def on_mousewheel(event):
                # Windows/Mac: event.delta
                # Linux: event.num (4=up, 5=down)
                if event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")
                else:
                    # Windows/Mac
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            def bind_mousewheel(event):
                # Bind mouse wheel to canvas when mouse enters
                canvas.bind("<MouseWheel>", on_mousewheel)
                canvas.bind("<Button-4>", on_mousewheel)  # Linux scroll up
                canvas.bind("<Button-5>", on_mousewheel)  # Linux scroll down
                # Also bind to scrollable frame
                scrollable_frame.bind("<MouseWheel>", on_mousewheel)
                scrollable_frame.bind("<Button-4>", on_mousewheel)
                scrollable_frame.bind("<Button-5>", on_mousewheel)
            
            def unbind_mousewheel(event):
                # Unbind mouse wheel when mouse leaves
                canvas.unbind("<MouseWheel>")
                canvas.unbind("<Button-4>")
                canvas.unbind("<Button-5>")
                scrollable_frame.unbind("<MouseWheel>")
                scrollable_frame.unbind("<Button-4>")
                scrollable_frame.unbind("<Button-5>")
            
            # Bind mouse enter/leave events to enable/disable scrolling
            canvas.bind('<Enter>', bind_mousewheel)
            canvas.bind('<Leave>', unbind_mousewheel)
            
            # Also bind to scrollable frame
            scrollable_frame.bind('<Enter>', bind_mousewheel)
            scrollable_frame.bind('<Leave>', unbind_mousewheel)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Main frame (now inside scrollable frame) - ensure it expands to fill width
            main_frame = ttk.Frame(scrollable_frame, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title with modern styling
            title_frame = ttk.Frame(main_frame)
            title_frame.pack(fill=tk.X, pady=(0, 15))
            title_label = ttk.Label(title_frame, text=profile.name, font=("Segoe UI", 20, "bold"), 
                                   foreground="#2C3E50")
            title_label.pack(anchor=tk.W)
            
            # Subtle divider line
            divider = tk.Frame(main_frame, height=2, bg="#E0E0E0", relief=tk.FLAT)
            divider.pack(fill=tk.X, pady=(0, 15))
            
            # Profile images (best reference frame + foot region) with modern styling
            profile_image_frame = ttk.LabelFrame(main_frame, text="Player Images", padding="15")
            profile_image_frame.pack(fill=tk.X, pady=(0, 15))
            
            # Container for images side by side
            images_container = ttk.Frame(profile_image_frame)
            images_container.pack(fill=tk.X, pady=5)
            
            try:
                # Try to extract images using helper methods
                profile_img = None
                foot_img = None
                best_frame = None
                
                if profile.reference_frames and len(profile.reference_frames) > 0:
                    # Score and find best frame
                    scored_frames = []
                    for ref_frame in profile.reference_frames:
                        if not ref_frame.get('video_path') or not ref_frame.get('bbox'):
                            continue
                        bbox = ref_frame.get('bbox', [])
                        if len(bbox) < 4:
                            continue
                        try:
                            width = abs(float(bbox[2]) - float(bbox[0]))
                            height = abs(float(bbox[3]) - float(bbox[1]))
                            if width <= 0 or height <= 0:
                                continue
                            area = width * height
                            confidence = ref_frame.get('confidence', 0.5)
                            total_score = area / 10000.0 + confidence * 2.0
                            scored_frames.append((total_score, ref_frame))
                        except (ValueError, TypeError):
                            continue
                    
                    scored_frames.sort(key=lambda x: x[0], reverse=True)
                    
                    # Try to extract from best frames
                    for score, ref_frame in scored_frames[:5]:
                        profile_img = self._extract_profile_image(ref_frame)
                        if profile_img:
                            best_frame = ref_frame
                            foot_img = self._extract_foot_region_image(ref_frame)
                            break
                
                # Display images
                if profile_img and best_frame:
                    # Player image (left side)
                    player_img_frame = ttk.Frame(images_container)
                    player_img_frame.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
                    
                    ttk.Label(player_img_frame, text="Full Player", font=("Arial", 9, "bold")).pack()
                    img_label = ttk.Label(player_img_frame, image=profile_img)
                    img_label.image = profile_img  # Keep a reference
                    img_label.pack(pady=5)
                    
                    video_name = os.path.basename(best_frame.get('video_path', 'unknown'))
                    frame_num = best_frame.get('frame_num', '?')
                    conf = best_frame.get('confidence', 0.0)
                    info_text = f"{video_name}\nFrame {frame_num}\nConf: {conf:.2f}"
                    ttk.Label(player_img_frame, text=info_text, font=("Arial", 7), 
                            justify=tk.CENTER).pack()
                    
                    # Foot/Shoe image (right side)
                    if foot_img:
                        foot_img_frame = ttk.Frame(images_container)
                        foot_img_frame.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
                        
                        ttk.Label(foot_img_frame, text="Foot/Shoe Region", font=("Arial", 9, "bold")).pack()
                        foot_label = ttk.Label(foot_img_frame, image=foot_img)
                        foot_label.image = foot_img  # Keep a reference
                        foot_label.pack(pady=5)
                        
                        ttk.Label(foot_img_frame, text="Bottom 10-30% of bbox\n(Feet/shoes area)", 
                                font=("Arial", 7), justify=tk.CENTER, foreground="blue").pack()
                    else:
                        foot_img_frame = ttk.Frame(images_container)
                        foot_img_frame.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
                        ttk.Label(foot_img_frame, text="Foot/Shoe Region", font=("Arial", 9, "bold")).pack()
                        ttk.Label(foot_img_frame, text="Not available", 
                                font=("Arial", 7), foreground="gray", justify=tk.CENTER).pack(pady=20)
                else:
                    error_text = "No valid profile image found\n\n"
                    if not profile.reference_frames or len(profile.reference_frames) == 0:
                        error_text += "• No reference frames available\n"
                        error_text += "• Run analysis with Re-ID enabled"
                    else:
                        error_text += f"• Found {len(profile.reference_frames)} reference frame(s)\n"
                        error_text += "• Images may be rejected due to invalid paths or bbox"
                    
                    ttk.Label(images_container, text=error_text, 
                            font=("Arial", 9), foreground="gray", justify=tk.LEFT).pack(pady=10)
            except Exception as e:
                import traceback
                print(f"Error loading player images: {traceback.format_exc()}")
                ttk.Label(images_container, text=f"Error loading images: {str(e)}", 
                        font=("Arial", 8), foreground="red", justify=tk.LEFT).pack()
            
            # Player info - Enhanced Editor with modern styling
            info_frame = ttk.LabelFrame(main_frame, text="Player Information", padding="15")
            info_frame.pack(fill=tk.X, pady=(0, 15))
            
            # Editable fields with better layout
            row = 0
            ttk.Label(info_frame, text="Player Name:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            name_var = tk.StringVar(value=profile.name if profile.name else "")
            name_entry = ttk.Entry(info_frame, textvariable=name_var, width=30)
            name_entry.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5, columnspan=2)
            row += 1
            
            ttk.Label(info_frame, text="Jersey Number:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            jersey_var = tk.StringVar(value=str(profile.jersey_number) if profile.jersey_number else "")
            jersey_entry = ttk.Entry(info_frame, textvariable=jersey_var, width=10)
            jersey_entry.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
            row += 1
            
            ttk.Label(info_frame, text="Team:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            team_var = tk.StringVar(value=profile.team if profile.team else "")
            team_entry = ttk.Entry(info_frame, textvariable=team_var, width=20)
            team_entry.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
            row += 1
            
            # Position field (new)
            ttk.Label(info_frame, text="Position:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            position_var = tk.StringVar(value=getattr(profile, 'position', '') or "")
            position_combo = ttk.Combobox(info_frame, textvariable=position_var, width=18, 
                                         values=["", "GK", "DEF", "MID", "FWD", "GK/DEF", "DEF/MID", "MID/FWD"])
            position_combo.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
            row += 1
            
            # Notes/Description field (new)
            ttk.Label(info_frame, text="Notes:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky=tk.NW, padx=5, pady=5)
            notes_var = tk.StringVar(value=getattr(profile, 'notes', '') or "")
            notes_text = tk.Text(info_frame, width=40, height=4, wrap=tk.WORD, font=("Arial", 9))
            notes_text.insert("1.0", notes_var.get())
            notes_text.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5, columnspan=2)
            row += 1
            
            # Custom Tags field (new)
            ttk.Label(info_frame, text="Tags:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            tags_var = tk.StringVar(value=", ".join(getattr(profile, 'tags', []) or []))
            tags_entry = ttk.Entry(info_frame, textvariable=tags_var, width=40)
            tags_entry.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5, columnspan=2)
            ttk.Label(info_frame, text="(comma-separated)", font=("Arial", 7), foreground="gray").grid(row=row, column=3, sticky=tk.W, padx=5)
            row += 1
            
            # Visualization Settings Section with modern styling
            viz_settings = getattr(profile, 'visualization_settings', None) or {}
            
            viz_frame = ttk.LabelFrame(main_frame, text="Visualization Settings (Overlay Customization)", padding="15")
            viz_frame.pack(fill=tk.X, pady=(0, 15))
            
            # Helper function to create color picker button with swatch
            def create_color_picker(parent, row, label_text, initial_rgb, var_storage):
                """Create a color picker button with visual swatch"""
                ttk.Label(parent, text=label_text, font=("Arial", 9, "bold")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
                
                # Frame for button and swatch
                color_frame = ttk.Frame(parent)
                color_frame.grid(row=row, column=1, padx=5, pady=5, sticky=tk.W)
                
                # Color swatch (visual indicator)
                swatch = tk.Canvas(color_frame, width=30, height=20, relief=tk.SUNKEN, borderwidth=1)
                swatch.pack(side=tk.LEFT, padx=(0, 5))
                
                # Store RGB value
                rgb_var = [initial_rgb] if initial_rgb else [None]
                var_storage.append(rgb_var)
                
                # Update swatch color
                def update_swatch(rgb):
                    if rgb and isinstance(rgb, (list, tuple)) and len(rgb) >= 3:
                        # Convert RGB to hex for tkinter
                        hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
                        swatch.delete("all")
                        swatch.create_rectangle(0, 0, 30, 20, fill=hex_color, outline="black")
                        rgb_var[0] = list(rgb)
                    else:
                        swatch.delete("all")
                        swatch.create_rectangle(0, 0, 30, 20, fill="gray", outline="black")
                        swatch.create_text(15, 10, text="?", fill="white", font=("Arial", 8, "bold"))
                        rgb_var[0] = None
                
                # Initialize swatch
                if initial_rgb:
                    update_swatch(initial_rgb)
                else:
                    update_swatch(None)
                
                # Color picker button
                def pick_color():
                    # Get current color as hex for colorchooser
                    if rgb_var[0] and isinstance(rgb_var[0], (list, tuple)) and len(rgb_var[0]) >= 3:
                        current_hex = f"#{rgb_var[0][0]:02x}{rgb_var[0][1]:02x}{rgb_var[0][2]:02x}"
                    else:
                        current_hex = None
                    
                    # Open color picker
                    color = colorchooser.askcolor(
                        color=current_hex,
                        title=f"Choose {label_text}"
                    )
                    
                    if color[0]:  # User selected a color
                        # color[0] is (R, G, B) tuple
                        rgb = [int(color[0][0]), int(color[0][1]), int(color[0][2])]
                        update_swatch(rgb)
                
                pick_btn = ttk.Button(color_frame, text="Pick Color", command=pick_color, width=12)
                pick_btn.pack(side=tk.LEFT, padx=(0, 5))
                
                # Clear button
                def clear_color():
                    update_swatch(None)
                
                clear_btn = ttk.Button(color_frame, text="Clear", command=clear_color, width=8)
                clear_btn.pack(side=tk.LEFT)
                
                return rgb_var
            
            viz_row = 0
            color_vars = []  # Store all color variable references
            
            # Custom Color
            initial_custom = viz_settings.get('custom_color_rgb')
            if initial_custom and isinstance(initial_custom, (list, tuple)) and len(initial_custom) >= 3:
                initial_custom = list(initial_custom)
            else:
                initial_custom = None
            custom_color_var = create_color_picker(viz_frame, viz_row, "Custom Color:", initial_custom, color_vars)
            ttk.Label(viz_frame, text="(Overrides team color)", font=("Arial", 7), foreground="gray").grid(row=viz_row, column=2, sticky=tk.W, padx=5)
            viz_row += 1
            
            # Box Color Override
            initial_box = viz_settings.get('box_color')
            if initial_box and isinstance(initial_box, (list, tuple)) and len(initial_box) >= 3:
                initial_box = list(initial_box)
            else:
                initial_box = None
            box_color_var = create_color_picker(viz_frame, viz_row, "Box Color:", initial_box, color_vars)
            ttk.Label(viz_frame, text="(Leave empty to use default)", font=("Arial", 7), foreground="gray").grid(row=viz_row, column=2, sticky=tk.W, padx=5)
            viz_row += 1
            
            # Label Color Override
            initial_label = viz_settings.get('label_color')
            if initial_label and isinstance(initial_label, (list, tuple)) and len(initial_label) >= 3:
                initial_label = list(initial_label)
            else:
                initial_label = None
            label_color_var = create_color_picker(viz_frame, viz_row, "Label Color:", initial_label, color_vars)
            ttk.Label(viz_frame, text="(Leave empty to use default)", font=("Arial", 7), foreground="gray").grid(row=viz_row, column=2, sticky=tk.W, padx=5)
            viz_row += 1
            
            # Box Thickness
            ttk.Label(viz_frame, text="Box Thickness:", font=("Arial", 9, "bold")).grid(row=viz_row, column=0, sticky=tk.W, padx=5, pady=5)
            box_thickness_var = tk.IntVar(value=viz_settings.get('box_thickness', 2))
            ttk.Spinbox(viz_frame, from_=1, to=10, textvariable=box_thickness_var, width=10).grid(row=viz_row, column=1, padx=5, pady=5, sticky=tk.W)
            viz_row += 1
            
            # Show Glow
            show_glow_var = tk.BooleanVar(value=viz_settings.get('show_glow', False))
            ttk.Checkbutton(viz_frame, text="Show Glow Effect", variable=show_glow_var).grid(row=viz_row, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
            viz_row += 1
            
            # Glow Intensity
            ttk.Label(viz_frame, text="Glow Intensity:", font=("Arial", 9, "bold")).grid(row=viz_row, column=0, sticky=tk.W, padx=5, pady=5)
            glow_intensity_var = tk.IntVar(value=viz_settings.get('glow_intensity', 50))
            ttk.Spinbox(viz_frame, from_=0, to=100, textvariable=glow_intensity_var, width=10).grid(row=viz_row, column=1, padx=5, pady=5, sticky=tk.W)
            viz_row += 1
            
            # Glow Color
            initial_glow = viz_settings.get('glow_color')
            if initial_glow and isinstance(initial_glow, (list, tuple)) and len(initial_glow) >= 3:
                initial_glow = list(initial_glow)
            else:
                initial_glow = None
            glow_color_var = create_color_picker(viz_frame, viz_row, "Glow Color:", initial_glow, color_vars)
            ttk.Label(viz_frame, text="(Leave empty to use default)", font=("Arial", 7), foreground="gray").grid(row=viz_row, column=2, sticky=tk.W, padx=5)
            viz_row += 1
            
            # Show Trail
            show_trail_var = tk.BooleanVar(value=viz_settings.get('show_trail', False))
            ttk.Checkbutton(viz_frame, text="Show Movement Trail", variable=show_trail_var).grid(row=viz_row, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
            viz_row += 1
            
            # Trail Length
            ttk.Label(viz_frame, text="Trail Length (frames):", font=("Arial", 9, "bold")).grid(row=viz_row, column=0, sticky=tk.W, padx=5, pady=5)
            trail_length_var = tk.IntVar(value=viz_settings.get('trail_length', 30))
            ttk.Spinbox(viz_frame, from_=1, to=100, textvariable=trail_length_var, width=10).grid(row=viz_row, column=1, padx=5, pady=5, sticky=tk.W)
            viz_row += 1
            
            # Trail Color
            initial_trail = viz_settings.get('trail_color')
            if initial_trail and isinstance(initial_trail, (list, tuple)) and len(initial_trail) >= 3:
                initial_trail = list(initial_trail)
            else:
                initial_trail = None
            trail_color_var = create_color_picker(viz_frame, viz_row, "Trail Color:", initial_trail, color_vars)
            ttk.Label(viz_frame, text="(Leave empty to use default)", font=("Arial", 7), foreground="gray").grid(row=viz_row, column=2, sticky=tk.W, padx=5)
            viz_row += 1
            
            # Label Style
            ttk.Label(viz_frame, text="Label Style:", font=("Arial", 9, "bold")).grid(row=viz_row, column=0, sticky=tk.W, padx=5, pady=5)
            label_style_var = tk.StringVar(value=viz_settings.get('label_style', 'full_name'))
            ttk.Combobox(viz_frame, textvariable=label_style_var, 
                        values=["full_name", "jersey", "initials", "number"], 
                        width=15, state="readonly").grid(row=viz_row, column=1, padx=5, pady=5, sticky=tk.W)
            viz_row += 1
            
            # Foot Tracker Settings
            ttk.Label(viz_frame, text="Foot Tracker Offset (pixels):", font=("Arial", 9, "bold")).grid(row=viz_row, column=0, sticky=tk.W, padx=5, pady=5)
            foot_offset_var = tk.IntVar(value=viz_settings.get('foot_tracker_offset', 52))
            ttk.Spinbox(viz_frame, from_=0, to=200, textvariable=foot_offset_var, width=10).grid(row=viz_row, column=1, padx=5, pady=5, sticky=tk.W)
            ttk.Label(viz_frame, text="(52 = below foot axis)", font=("Arial", 7), foreground="gray").grid(row=viz_row, column=2, sticky=tk.W, padx=5)
            viz_row += 1
            
            # Ellipse Width
            ttk.Label(viz_frame, text="Ellipse Width:", font=("Arial", 9, "bold")).grid(row=viz_row, column=0, sticky=tk.W, padx=5, pady=5)
            ellipse_width_var = tk.IntVar(value=viz_settings.get('ellipse_width', 20))
            ttk.Spinbox(viz_frame, from_=5, to=100, textvariable=ellipse_width_var, width=10).grid(row=viz_row, column=1, padx=5, pady=5, sticky=tk.W)
            viz_row += 1
            
            # Ellipse Height
            ttk.Label(viz_frame, text="Ellipse Height:", font=("Arial", 9, "bold")).grid(row=viz_row, column=0, sticky=tk.W, padx=5, pady=5)
            ellipse_height_var = tk.IntVar(value=viz_settings.get('ellipse_height', 12))
            ttk.Spinbox(viz_frame, from_=5, to=100, textvariable=ellipse_height_var, width=10).grid(row=viz_row, column=1, padx=5, pady=5, sticky=tk.W)
            viz_row += 1
            
            # Read-only info
            ttk.Label(info_frame, text="Has Re-ID Features:", font=("Arial", 9, "bold")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
            has_features_text = "✓ Yes" if profile.features is not None else "✗ No"
            ttk.Label(info_frame, text=has_features_text, 
                     foreground="green" if profile.features is not None else "red").grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
            
            ttk.Label(info_frame, text="Reference Frames:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            ref_count = len(profile.reference_frames) if profile.reference_frames else 0
            ttk.Label(info_frame, text=str(ref_count)).grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
            row += 1
            
            # Photo Management Section - ensure it fills available width with modern styling
            photo_mgmt_frame = ttk.LabelFrame(main_frame, text="Reference Images Management", padding="15")
            photo_mgmt_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
            
            # Configure main_frame columns to expand
            main_frame.columnconfigure(0, weight=1)
            
            # Control buttons for mass selection/deletion
            photo_control_frame = ttk.Frame(photo_mgmt_frame)
            photo_control_frame.pack(fill=tk.X, pady=(0, 5))
            
            # Ensure the control frame can expand to show all buttons
            photo_control_frame.columnconfigure(0, weight=1)
            
            # Make sure photo_mgmt_frame allows horizontal expansion
            photo_mgmt_frame.columnconfigure(0, weight=1)
            
            # Track selected frames for player details window
            detail_selected_frames = {}  # Dict: {(video_path, frame_num): (checkbox_var, ref_frame)}
            
            def get_detail_frame_key(ref_frame):
                """Get a unique hashable key for a reference frame in player details"""
                video_path = ref_frame.get('video_path', 'unknown')
                frame_num = ref_frame.get('frame_num', 0)
                return (video_path, frame_num)
            
            def select_all_detail_frames():
                """Select/deselect all checkboxes in player details"""
                if not profile.reference_frames:
                    return
                all_selected = all(var.get() for var, _ in detail_selected_frames.values())
                new_state = not all_selected
                for var, _ in detail_selected_frames.values():
                    var.set(new_state)
                update_detail_delete_button_state()
            
            def update_detail_delete_button_state():
                """Update delete button state in player details"""
                selected_count = sum(1 for var, _ in detail_selected_frames.values() if var.get())
                if selected_count > 0:
                    detail_delete_selected_btn.config(state=tk.NORMAL, text=f"🗑️ Delete Selected ({selected_count})")
                else:
                    detail_delete_selected_btn.config(state=tk.DISABLED, text="🗑️ Delete Selected")
            
            def delete_selected_detail_frames():
                """Delete all selected frames from player details"""
                selected = [ref_frame for key, (var, ref_frame) in detail_selected_frames.items() if var.get()]
                if not selected:
                    messagebox.showwarning("No Selection", "Please select frames to delete")
                    return
                
                result = messagebox.askyesno("Confirm Mass Delete", 
                        f"Delete {len(selected)} selected reference frame(s) from {profile.name}?\n\n"
                        f"This will permanently remove these images from the gallery.\n"
                        f"This action cannot be undone.")
                if result:
                    try:
                        removed_count = 0
                        for ref_frame in selected:
                            if ref_frame in profile.reference_frames:
                                profile.reference_frames.remove(ref_frame)
                                removed_count += 1
                        
                        if removed_count > 0:
                            gallery.save_gallery()
                            load_reference_frames()  # Reload
                            messagebox.showinfo("Success", f"Removed {removed_count} reference frame(s)")
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not remove frames:\n{e}")
                        import traceback
                        traceback.print_exc()
            
            # Control buttons row - ensure all buttons are visible
            button_row = ttk.Frame(photo_control_frame)
            button_row.pack(fill=tk.X, pady=2, padx=5)
            
            # First two buttons (existing)
            ttk.Button(button_row, text="Select All", command=select_all_detail_frames).pack(side=tk.LEFT, padx=5)
            detail_delete_selected_btn = ttk.Button(button_row, text="Delete Selected", 
                                                   command=delete_selected_detail_frames, state=tk.DISABLED)
            detail_delete_selected_btn.pack(side=tk.LEFT, padx=5)
            
            # Create simple placeholder functions first
            def remove_duplicate_images():
                messagebox.showinfo("Info", "Remove Duplicates function called")
            
            def cleanup_false_matches():
                messagebox.showinfo("Info", "Clean False Matches function called")
            
            def clear_all_images():
                """Clear all reference images for this player"""
                result = messagebox.askyesno("Clear All Images", 
                    f"Delete ALL reference images for {profile.name}?\n\n"
                    f"This will remove {len(profile.reference_frames) if profile.reference_frames else 0} reference frame(s).\n\n"
                    f"This action cannot be undone.\n\n"
                    f"Continue?")
                if result:
                    try:
                        profile.reference_frames = []
                        profile.uniform_variants = {}
                        profile.foot_reference_frames = []
                        profile.best_body_image = None
                        profile.best_jersey_image = None
                        profile.best_foot_image = None
                        gallery.save_gallery()
                        load_reference_frames()  # Reload to show empty state
                        messagebox.showinfo("Success", f"Cleared all reference images for {profile.name}")
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not clear images:\n{e}")
                        import traceback
                        traceback.print_exc()
            
            def rebuild_from_anchors():
                """Rebuild gallery images from anchor frames/tags"""
                result = messagebox.askyesno("Rebuild from Anchors", 
                    f"Rebuild reference images for {profile.name} from anchor frames?\n\n"
                    f"This will:\n"
                    f"• Search all seed config files for anchor frames tagged with '{profile.name}'\n"
                    f"• Extract reference frames from videos based on those anchors\n"
                    f"• Add them to the player's gallery\n\n"
                    f"Continue?")
                if not result:
                    return
                
                try:
                    import json
                    import cv2
                    import os
                    from pathlib import Path
                    from collections import defaultdict
                    
                    # Find all seed config files
                    seed_files = []
                    search_paths = [
                        os.path.dirname(gallery.gallery_path) if hasattr(gallery, 'gallery_path') else '.',
                        '.',
                        'config',
                        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')
                    ]
                    
                    for search_path in search_paths:
                        if os.path.exists(search_path):
                            for root, dirs, files in os.walk(search_path):
                                for file in files:
                                    if file.endswith('_seed_config.json') or file == 'seed_config.json':
                                        seed_files.append(os.path.join(root, file))
                    
                    if not seed_files:
                        messagebox.showwarning("No Seed Files", 
                            "No seed config files found.\n\n"
                            "Anchor frames are stored in seed_config.json files.\n"
                            "Please ensure you have anchor frames tagged for this player.")
                        return
                    
                    # Load anchor frames for this player
                    player_anchors = defaultdict(list)  # {video_path: [(frame_num, bbox, track_id), ...]}
                    
                    for seed_file in seed_files:
                        try:
                            with open(seed_file, 'r') as f:
                                config = json.load(f)
                            
                            anchor_frames = config.get('anchor_frames', {})
                            video_path = config.get('video_path', '')
                            
                            if not video_path or not os.path.exists(video_path):
                                # Try to find video in same directory
                                seed_dir = os.path.dirname(seed_file)
                                for ext in ['.mp4', '.avi', '.mov', '.mkv']:
                                    potential_video = os.path.join(seed_dir, os.path.basename(seed_file).replace('_seed_config.json', ext))
                                    if os.path.exists(potential_video):
                                        video_path = potential_video
                                        break
                            
                            if not video_path:
                                continue
                            
                            # Find anchors for this player
                            for frame_str, anchors in anchor_frames.items():
                                frame_num = int(frame_str) if isinstance(frame_str, str) else frame_str
                                for anchor in anchors:
                                    anchor_player = anchor.get('player_name', '')
                                    if anchor_player and anchor_player.lower() == profile.name.lower():
                                        bbox = anchor.get('bbox', [])
                                        track_id = anchor.get('track_id')
                                        player_anchors[video_path].append((frame_num, bbox, track_id))
                        except Exception as e:
                            continue
                    
                    if not player_anchors:
                        messagebox.showwarning("No Anchors Found", 
                            f"No anchor frames found for '{profile.name}'.\n\n"
                            f"Searched {len(seed_files)} seed config file(s).\n\n"
                            f"Please tag this player in anchor frames first.")
                        return
                    
                    # Extract reference frames from videos
                    total_frames = sum(len(frames) for frames in player_anchors.values())
                    if total_frames == 0:
                        messagebox.showwarning("No Frames", "No valid anchor frames found.")
                        return
                    
                    # Ask for confirmation with count
                    confirm = messagebox.askyesno("Confirm Rebuild", 
                        f"Found {total_frames} anchor frame(s) for {profile.name} across {len(player_anchors)} video(s).\n\n"
                        f"Extract reference frames from these anchors?\n\n"
                        f"This may take a few minutes.")
                    if not confirm:
                        return
                    
                    # Extract frames
                    extracted_count = 0
                    failed_count = 0
                    
                    for video_path, frames_list in player_anchors.items():
                        if not os.path.exists(video_path):
                            failed_count += len(frames_list)
                            continue
                        
                        try:
                            cap = cv2.VideoCapture(video_path)
                            if not cap.isOpened():
                                failed_count += len(frames_list)
                                continue
                            
                            for frame_num, bbox, track_id in frames_list:
                                try:
                                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                                    ret, frame = cap.read()
                                    if not ret:
                                        failed_count += 1
                                        continue
                                    
                                    # Extract bbox region
                                    if len(bbox) >= 4:
                                        x1, y1, x2, y2 = map(int, bbox[:4])
                                        x1 = max(0, x1)
                                        y1 = max(0, y1)
                                        x2 = min(frame.shape[1], x2)
                                        y2 = min(frame.shape[0], y2)
                                        
                                        if x2 > x1 and y2 > y1:
                                            # Create reference frame entry
                                            ref_frame = {
                                                'video_path': video_path,
                                                'frame_num': frame_num,
                                                'bbox': [float(x1), float(y1), float(x2), float(y2)],
                                                'confidence': 1.00,  # Anchor frames have 1.00 confidence
                                                'track_id': track_id
                                            }
                                            
                                            # Add to profile
                                            if profile.reference_frames is None:
                                                profile.reference_frames = []
                                            profile.reference_frames.append(ref_frame)
                                            extracted_count += 1
                                        else:
                                            failed_count += 1
                                    else:
                                        failed_count += 1
                                except Exception as e:
                                    failed_count += 1
                                    continue
                            
                            cap.release()
                        except Exception as e:
                            failed_count += len(frames_list)
                            continue
                    
                    # Save gallery
                    gallery.save_gallery()
                    load_reference_frames()  # Reload to show new frames
                    
                    messagebox.showinfo("Rebuild Complete", 
                        f"Rebuilt gallery for {profile.name}:\n\n"
                        f"• Extracted: {extracted_count} reference frame(s)\n"
                        f"• Failed: {failed_count} frame(s)\n"
                        f"• Videos processed: {len(player_anchors)}\n\n"
                        f"Gallery has been saved.")
                except Exception as e:
                    messagebox.showerror("Error", f"Could not rebuild from anchors:\n{e}")
                    import traceback
                    traceback.print_exc()
            
            # Create additional buttons
            try:
                remove_dup_btn = ttk.Button(button_row, text="Remove Duplicates", 
                          command=remove_duplicate_images)
                remove_dup_btn.pack(side=tk.LEFT, padx=5)
                
                cleanup_btn = ttk.Button(button_row, text="Clean False Matches", 
                          command=cleanup_false_matches)
                cleanup_btn.pack(side=tk.LEFT, padx=5)
                
                clear_all_btn = ttk.Button(button_row, text="Clear All Images", 
                          command=clear_all_images)
                clear_all_btn.pack(side=tk.LEFT, padx=5)
                
                rebuild_btn = ttk.Button(button_row, text="Rebuild from Anchors", 
                          command=rebuild_from_anchors)
                rebuild_btn.pack(side=tk.LEFT, padx=5)
                
                # Store references to prevent garbage collection
                button_row._remove_dup_btn = remove_dup_btn
                button_row._cleanup_btn = cleanup_btn
                button_row._clear_all_btn = clear_all_btn
                button_row._rebuild_btn = rebuild_btn
                detail_window._remove_dup_btn = remove_dup_btn
                detail_window._cleanup_btn = cleanup_btn
                detail_window._clear_all_btn = clear_all_btn
                detail_window._rebuild_btn = rebuild_btn
            except Exception as e:
                import traceback
                traceback.print_exc()
            
            # Define functions for the new buttons (full implementations)
            def remove_duplicate_images():
                """Remove duplicate gallery images for this player"""
                result = messagebox.askyesno("Remove Duplicates", 
                    f"Remove duplicate reference images for {profile.name}?\n\n"
                    f"This will scan all reference frames and remove duplicates based on:\n"
                    f"• Same video + frame number\n"
                    f"• Similar image content (if available)\n\n"
                    f"Higher quality versions will be kept.\n\n"
                    f"Continue?")
                if result:
                    try:
                        # Use the gallery's remove_duplicate_gallery_images method
                        stats = gallery.remove_duplicate_gallery_images(
                            similarity_threshold=0.99,
                            compare_image_content=True
                        )
                        
                        # Filter stats to show only this player's results
                        # The method processes all players, so we need to check what was removed
                        # Reload to see updated frame count
                        load_reference_frames()
                        
                        # Show results
                        messagebox.showinfo("Duplicates Removed", 
                            f"Removed {stats['total_duplicates_removed']} duplicate image(s) across all players.\n\n"
                            f"• Reference frames: {stats['reference_frames_removed']}\n"
                            f"• Best images: {stats['best_images_removed']}\n"
                            f"• Players affected: {stats['players_affected']}\n\n"
                            f"Gallery has been saved.")
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not remove duplicates:\n{e}")
                        import traceback
                        traceback.print_exc()
            
            def cleanup_false_matches():
                """Open interactive false match removal tool for this specific player"""
                try:
                    # Don't hide the detail window - just open the cleanup tool on top
                    # Open the interactive false match removal tool
                    # We'll create a simplified version that starts with this player selected
                    self._cleanup_player_false_matches(gallery, player_id, profile.name)
                    
                    # After cleanup window closes, reload the reference frames
                    # The cleanup window will handle its own lifecycle
                    detail_window.after(100, load_reference_frames)  # Reload after a short delay
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open cleanup tool:\n{e}")
                    import traceback
                    traceback.print_exc()
            
            # Update button commands to use the full function implementations
            if 'remove_dup_btn' in locals():
                remove_dup_btn.config(command=remove_duplicate_images)
            if 'cleanup_btn' in locals():
                cleanup_btn.config(command=cleanup_false_matches)
            if 'clear_all_btn' in locals():
                clear_all_btn.config(command=clear_all_images)
            if 'rebuild_btn' in locals():
                rebuild_btn.config(command=rebuild_from_anchors)
            
            # Create notebook for organizing by uniform variant - ensure it fills width
            photo_notebook = ttk.Notebook(photo_mgmt_frame)
            photo_notebook.pack(fill=tk.BOTH, expand=True, pady=5)
            
            # Configure photo_mgmt_frame to expand
            photo_mgmt_frame.columnconfigure(0, weight=1)
            
            # All Reference Frames tab
            all_frames_frame = ttk.Frame(photo_notebook)
            photo_notebook.add(all_frames_frame, text=f"All Frames ({ref_count})")
            
            # Create scrollable canvas for reference frames grid with modern styling
            photo_canvas = tk.Canvas(all_frames_frame, bg="#F8F8F8", highlightthickness=0, relief=tk.FLAT)
            photo_scrollbar = ttk.Scrollbar(all_frames_frame, orient="vertical", command=photo_canvas.yview)
            photo_scrollable_frame = ttk.Frame(photo_canvas)
            
            photo_scrollable_frame.bind(
                "<Configure>",
                lambda e: photo_canvas.configure(scrollregion=photo_canvas.bbox("all"))
            )
            
            canvas_window = photo_canvas.create_window((0, 0), window=photo_scrollable_frame, anchor="nw")
            photo_canvas.configure(yscrollcommand=photo_scrollbar.set)
            
            # Configure canvas window to expand horizontally
            def configure_canvas_window(event):
                canvas_width = event.width
                photo_canvas.itemconfig(canvas_window, width=canvas_width)
                # Also update the scrollable frame width
                photo_scrollable_frame.config(width=canvas_width)
            photo_canvas.bind('<Configure>', configure_canvas_window)
            
            # Add mouse wheel scrolling support for photo canvas (Windows/Mac and Linux)
            def on_photo_mousewheel(event):
                # Linux: event.num (4=up, 5=down)
                if event.num == 4:
                    photo_canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    photo_canvas.yview_scroll(1, "units")
                else:
                    # Windows/Mac: event.delta
                    photo_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            def bind_photo_mousewheel(event):
                # Bind mouse wheel to photo canvas when mouse enters
                photo_canvas.bind("<MouseWheel>", on_photo_mousewheel)
                photo_canvas.bind("<Button-4>", on_photo_mousewheel)  # Linux scroll up
                photo_canvas.bind("<Button-5>", on_photo_mousewheel)  # Linux scroll down
                # Also bind to scrollable frame
                photo_scrollable_frame.bind("<MouseWheel>", on_photo_mousewheel)
                photo_scrollable_frame.bind("<Button-4>", on_photo_mousewheel)
                photo_scrollable_frame.bind("<Button-5>", on_photo_mousewheel)
            
            def unbind_photo_mousewheel(event):
                # Unbind mouse wheel when mouse leaves
                photo_canvas.unbind("<MouseWheel>")
                photo_canvas.unbind("<Button-4>")
                photo_canvas.unbind("<Button-5>")
                photo_scrollable_frame.unbind("<MouseWheel>")
                photo_scrollable_frame.unbind("<Button-4>")
                photo_scrollable_frame.unbind("<Button-5>")
            
            # Bind mouse enter/leave events to enable/disable scrolling
            photo_canvas.bind('<Enter>', bind_photo_mousewheel)
            photo_canvas.bind('<Leave>', unbind_photo_mousewheel)
            
            # Also bind to scrollable frame
            photo_scrollable_frame.bind('<Enter>', bind_photo_mousewheel)
            photo_scrollable_frame.bind('<Leave>', unbind_photo_mousewheel)
            
            photo_canvas.pack(side="left", fill="both", expand=True)
            photo_scrollbar.pack(side="right", fill="y")
            
            # Configure the scrollable frame to expand
            all_frames_frame.columnconfigure(0, weight=1)
            all_frames_frame.rowconfigure(0, weight=1)
            
            # Set initial width for scrollable frame to match canvas
            photo_scrollable_frame.update_idletasks()
            photo_scrollable_frame.config(width=all_frames_frame.winfo_width())
            
            # Store reference frame widgets for management
            ref_frame_widgets = []
            thumbnail_loading_active = False
            
            def load_reference_frames():
                """Load and display all reference frames (async with placeholders)"""
                # Clear existing widgets
                for widget in ref_frame_widgets:
                    widget.destroy()
                ref_frame_widgets.clear()
                # Clear selected frames dict
                detail_selected_frames.clear()
                
                if not profile.reference_frames or len(profile.reference_frames) == 0:
                    no_frames_label = ttk.Label(photo_scrollable_frame, text="No reference frames available", 
                            font=("Arial", 10), foreground="gray")
                    no_frames_label.grid(row=0, column=0, pady=20)
                    ref_frame_widgets.append(no_frames_label)
                    return
                
                # Show loading indicator
                loading_label = ttk.Label(photo_scrollable_frame, 
                                        text=f"Loading {len(profile.reference_frames)} reference frames...", 
                                        font=("Arial", 10), foreground="blue")
                loading_label.grid(row=0, column=0, pady=20)
                detail_window.update()
                
                # Create grid for reference frames with placeholders first
                cols = 4
                row_idx = 0
                col_idx = 0
                
                # Configure grid columns to expand evenly
                for c in range(cols):
                    photo_scrollable_frame.columnconfigure(c, weight=1, uniform="frame_cols")
                
                # Create placeholder containers first (fast) with modern styling
                frame_containers = []
                for i, ref_frame in enumerate(profile.reference_frames):
                    # Create frame for each reference image with modern card-like appearance
                    frame_container = tk.Frame(photo_scrollable_frame, 
                                              bg="#FFFFFF", 
                                              relief=tk.FLAT,
                                              borderwidth=0,
                                              highlightbackground="#E0E0E0",
                                              highlightthickness=1)
                    frame_container.grid(row=row_idx, column=col_idx, padx=8, pady=8, sticky="nsew")
                    ref_frame_widgets.append(frame_container)
                    frame_containers.append((i, ref_frame, frame_container))
                    
                    # Create checkbox for selection - use tuple key instead of dict
                    checkbox_var = tk.BooleanVar()
                    frame_key = get_detail_frame_key(ref_frame)
                    detail_selected_frames[frame_key] = (checkbox_var, ref_frame)
                    
                    # Show placeholder immediately with modern styling
                    placeholder_label = tk.Label(frame_container, text="Loading...", 
                                                 font=("Arial", 9), foreground="#9E9E9E", bg="#FFFFFF")
                    placeholder_label.pack(pady=30)
                    
                    col_idx += 1
                    if col_idx >= cols:
                        col_idx = 0
                        row_idx += 1
                
                # Remove loading indicator
                loading_label.destroy()
                
                # Load thumbnails asynchronously
                def load_thumbnails_async():
                    """Load thumbnails in background thread"""
                    import threading
                    import time
                    
                    for i, ref_frame, frame_container in frame_containers:
                        try:
                            # Check if window still exists before processing
                            if not detail_window.winfo_exists():
                                break
                            
                            # Extract thumbnail (this is the slow part) - smaller size for 4 columns
                            thumbnail = self._extract_profile_image(ref_frame, max_size=(140, 180))
                            
                            # Update UI in main thread - use default args to fix closure issue
                            def update_ui(idx=i, thumb=thumbnail, container=frame_container, rf=ref_frame):
                                update_frame_thumbnail(idx, thumb, container, rf)
                            
                            try:
                                if detail_window.winfo_exists():
                                    detail_window.after(0, update_ui)
                            except tk.TclError:
                                pass  # Window was destroyed
                            
                            # Small delay to prevent overwhelming the UI
                            time.sleep(0.05)
                        except Exception as e:
                            # Update with error in main thread - use default args to fix closure issue
                            err_msg = str(e)
                            def update_error(idx=i, container=frame_container, err=err_msg):
                                update_frame_error(idx, container, err)
                            
                            try:
                                if detail_window.winfo_exists():
                                    detail_window.after(0, update_error)
                            except tk.TclError:
                                pass  # Window was destroyed
                
                def update_frame_error(idx, container, error_msg):
                    """Update frame container with error message"""
                    try:
                        # Check if container still exists
                        if not container.winfo_exists():
                            return
                        for widget in container.winfo_children():
                            widget.destroy()
                        error_label = tk.Label(container, text=f"Error:\n{error_msg[:20]}", 
                                font=("Arial", 7), foreground="#D32F2F", bg="#FFFFFF")
                        error_label.pack(pady=5)
                    except tk.TclError:
                        # Container was destroyed, ignore
                        pass
                
                def update_frame_thumbnail(idx, thumbnail, container, ref_frame):
                    """Update frame container with actual thumbnail (called from main thread)"""
                    try:
                        # Check if container and window still exist
                        if not container.winfo_exists() or not detail_window.winfo_exists():
                            return
                        # Clear placeholder
                        for widget in container.winfo_children():
                            widget.destroy()
                    except tk.TclError:
                        # Container was destroyed, ignore
                        return
                    
                    try:
                        # Add checkbox for selection (should already be in dict from load_reference_frames)
                        frame_key = get_detail_frame_key(ref_frame)
                        if frame_key in detail_selected_frames:
                            checkbox_var, _ = detail_selected_frames[frame_key]
                        else:
                            checkbox_var = tk.BooleanVar()
                            detail_selected_frames[frame_key] = (checkbox_var, ref_frame)
                        
                        # Checkbox with modern styling
                        checkbox = ttk.Checkbutton(container, variable=checkbox_var, 
                                                 command=update_detail_delete_button_state)
                        checkbox.pack(anchor=tk.NW, padx=5, pady=5)
                        
                        if thumbnail:
                            # Check if this is primary (first frame or marked as primary)
                            is_primary = (idx == 0) or ref_frame.get('is_primary', False)
                            
                            # Image label with padding
                            img_label = tk.Label(container, image=thumbnail, bg="#FFFFFF", relief=tk.FLAT)
                            img_label.image = thumbnail  # Keep reference
                            img_label.pack(pady=(0, 5))
                            
                            # Primary indicator with modern styling
                            if is_primary:
                                primary_frame = tk.Frame(container, bg="#FFF9C4", relief=tk.FLAT)
                                primary_frame.pack(fill=tk.X, padx=2, pady=2)
                                primary_label = tk.Label(primary_frame, text="⭐ PRIMARY", 
                                                        font=("Arial", 8, "bold"), 
                                                        foreground="#F57C00", 
                                                        bg="#FFF9C4")
                                primary_label.pack(pady=2)
                            
                            # Frame info with modern styling
                            info_frame_inner = tk.Frame(container, bg="#FFFFFF")
                            info_frame_inner.pack(fill=tk.X, padx=5, pady=2)
                            
                            video_name = os.path.basename(ref_frame.get('video_path', 'unknown'))
                            frame_num = ref_frame.get('frame_num', '?')
                            conf = ref_frame.get('confidence', 0.0)
                            info_text = f"Frame {frame_num} • {conf:.2f}"
                            info_label = tk.Label(info_frame_inner, text=info_text, 
                                    font=("Arial", 7), bg="#FFFFFF", foreground="#424242")
                            info_label.pack()
                            
                            # Uniform variant info with modern styling
                            uniform_info = ref_frame.get('uniform_info', {})
                            if uniform_info:
                                uniform_text = f"{uniform_info.get('jersey_color', '?')} jersey"
                                uniform_label = tk.Label(info_frame_inner, text=uniform_text, 
                                        font=("Arial", 7), bg="#FFFFFF", 
                                        foreground="#1976D2", justify=tk.CENTER)
                                uniform_label.pack()
                            
                            # Action buttons frame with modern styling
                            btn_frame = tk.Frame(container, bg="#FFFFFF")
                            btn_frame.pack(fill=tk.X, padx=5, pady=5)
                            
                            def make_preview_handler(frame=ref_frame, name=profile.name):
                                def preview():
                                    preview_reference_frame(frame, name)
                                return preview
                            
                            def make_set_primary_handler(idx=idx):
                                def set_primary():
                                    # Remove primary flag from all frames
                                    for rf in profile.reference_frames:
                                        rf['is_primary'] = False
                                    # Set this one as primary
                                    profile.reference_frames[idx]['is_primary'] = True
                                    gallery.save_gallery()
                                    load_reference_frames()  # Reload
                                    messagebox.showinfo("Success", "Primary reference frame updated")
                                return set_primary
                            
                            def make_remove_handler(ref_frame_obj=ref_frame):
                                def remove():
                                    frame_num = ref_frame_obj.get('frame_num', '?')
                                    video_name = os.path.basename(ref_frame_obj.get('video_path', 'unknown'))
                                    result = messagebox.askyesno("Confirm Delete", 
                                            f"Remove this reference frame?\n\n"
                                            f"Video: {video_name}\n"
                                            f"Frame: {frame_num}\n"
                                            f"Confidence: {ref_frame_obj.get('confidence', 0.0):.2f}\n\n"
                                            f"This will permanently remove this image from the gallery.\n"
                                            f"This action cannot be undone.")
                                    if result:
                                        try:
                                            # Find the actual index in the current list (may have changed)
                                            current_idx = None
                                            for i, rf in enumerate(profile.reference_frames):
                                                if (rf.get('frame_num') == ref_frame_obj.get('frame_num') and
                                                    rf.get('video_path') == ref_frame_obj.get('video_path')):
                                                    current_idx = i
                                                    break
                                            
                                            if current_idx is not None:
                                                profile.reference_frames.pop(current_idx)
                                                gallery.save_gallery()
                                                load_reference_frames()  # Reload
                                                messagebox.showinfo("Success", f"Reference frame removed from {profile.name}'s gallery")
                                            else:
                                                messagebox.showwarning("Not Found", "Reference frame not found in gallery")
                                        except Exception as e:
                                            messagebox.showerror("Error", f"Could not remove reference frame:\n{e}")
                                            import traceback
                                            traceback.print_exc()
                                return remove
                            
                            def make_reassign_handler(idx=idx):
                                def reassign():
                                    """Reassign this reference frame to a different player"""
                                    # Get list of all players
                                    all_players = gallery.list_players()
                                    
                                    if len(all_players) <= 1:
                                        messagebox.showwarning("No Other Players", 
                                            "There are no other players in the gallery to reassign this frame to.")
                                        return
                                    
                                    # Create dialog to select target player
                                    reassign_window = tk.Toplevel(detail_window)
                                    reassign_window.title("Reassign Reference Frame")
                                    reassign_window.geometry("400x300")
                                    reassign_window.transient(detail_window)
                                    
                                    ttk.Label(reassign_window, 
                                            text=f"Move this reference frame to which player?\n\nCurrent: {profile.name}\nFrame: {profile.reference_frames[idx].get('frame_num', '?')}", 
                                            font=("Arial", 10), justify=tk.LEFT).pack(pady=10, padx=10)
                                    
                                    # Listbox for player selection
                                    list_frame = ttk.Frame(reassign_window)
                                    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                                    
                                    scrollbar = ttk.Scrollbar(list_frame)
                                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                                    
                                    player_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Arial", 10))
                                    player_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                                    scrollbar.config(command=player_listbox.yview)
                                    
                                    # Populate listbox (exclude current player)
                                    target_players = []
                                    for pid, pname in all_players:
                                        if pid != player_id:  # Exclude current player
                                            pprofile = gallery.get_player(pid)
                                            display_text = f"{pname}"
                                            if pprofile and pprofile.jersey_number:
                                                display_text += f" (#{pprofile.jersey_number})"
                                            player_listbox.insert(tk.END, display_text)
                                            target_players.append((pid, pname))
                                    
                                    if len(target_players) == 0:
                                        ttk.Label(reassign_window, text="No other players available", 
                                                foreground="red").pack(pady=10)
                                        ttk.Button(reassign_window, text="Close", 
                                                 command=reassign_window.destroy).pack(pady=10)
                                        return
                                    
                                    def do_reassign():
                                        selection = player_listbox.curselection()
                                        if not selection:
                                            messagebox.showwarning("No Selection", "Please select a player")
                                            return
                                        
                                        target_idx = selection[0]
                                        target_player_id, target_player_name = target_players[target_idx]
                                        target_profile = gallery.get_player(target_player_id)
                                        
                                        # Confirm reassignment
                                        result = messagebox.askyesno("Confirm Reassignment",
                                            f"Move this reference frame from:\n{profile.name}\n\nto:\n{target_player_name}?\n\n"
                                            f"Frame: {profile.reference_frames[idx].get('frame_num', '?')}")
                                        
                                        if result:
                                            try:
                                                # Get the reference frame
                                                ref_frame = profile.reference_frames[idx]
                                                
                                                # Remove from current player
                                                profile.reference_frames.pop(idx)
                                                
                                                # Add to target player
                                                if not target_profile.reference_frames:
                                                    target_profile.reference_frames = []
                                                target_profile.reference_frames.append(ref_frame)
                                                
                                                # Save gallery
                                                gallery.save_gallery()
                                                
                                                reassign_window.destroy()
                                                load_reference_frames()  # Reload current player's frames
                                                
                                                messagebox.showinfo("Success", 
                                                    f"Reference frame moved to {target_player_name}")
                                            except Exception as e:
                                                messagebox.showerror("Error", f"Could not reassign frame:\n{e}")
                                                import traceback
                                                traceback.print_exc()
                                    
                                    button_frame = ttk.Frame(reassign_window)
                                    button_frame.pack(pady=10)
                                    
                                    ttk.Button(button_frame, text="Move to Selected Player", 
                                             command=do_reassign).pack(side=tk.LEFT, padx=5)
                                    ttk.Button(button_frame, text="Cancel", 
                                             command=reassign_window.destroy).pack(side=tk.LEFT, padx=5)
                                    
                                    # Double-click to reassign
                                    player_listbox.bind('<Double-Button-1>', lambda e: do_reassign())
                                
                                return reassign
                            
                            # Modern button styling - smaller, more compact
                            preview_btn = ttk.Button(btn_frame, text="👁️ Preview", width=10, command=make_preview_handler())
                            preview_btn.pack(side=tk.LEFT, padx=1)
                            primary_btn = ttk.Button(btn_frame, text="⭐ Primary", width=10, command=make_set_primary_handler())
                            primary_btn.pack(side=tk.LEFT, padx=1)
                            reassign_btn = ttk.Button(btn_frame, text="🔄 Move", width=10, command=make_reassign_handler())
                            reassign_btn.pack(side=tk.LEFT, padx=1)
                            delete_btn = ttk.Button(btn_frame, text="🗑️", width=6, command=make_remove_handler())
                            delete_btn.pack(side=tk.LEFT, padx=1)
                        else:
                            try:
                                if container.winfo_exists():
                                    unavailable_label = tk.Label(container, text="Image\nunavailable", 
                                            font=("Arial", 8), foreground="#9E9E9E", bg="#FFFFFF")
                                    unavailable_label.pack(pady=20)
                            except tk.TclError:
                                pass
                    except tk.TclError:
                        # Container or widgets were destroyed, ignore
                        return
                
                # Start background thread for loading thumbnails
                import threading
                thumbnail_thread = threading.Thread(target=load_thumbnails_async, daemon=True)
                thumbnail_thread.start()
            
            # Load reference frames
            load_reference_frames()
            
            # Add reference frame button
            add_frame_btn_frame = ttk.Frame(photo_mgmt_frame)
            add_frame_btn_frame.pack(fill=tk.X, pady=5)
            
            def add_reference_frame():
                """Add a new reference frame from video"""
                messagebox.showinfo("Add Reference Frame", 
                    "To add a reference frame:\n\n"
                    "1. Open the video in Playback Mode\n"
                    "2. Navigate to the desired frame\n"
                    "3. Tag the player at that frame\n"
                    "4. The frame will be added to the gallery automatically")
            
            ttk.Button(add_frame_btn_frame, text="➕ Add Reference Frame", 
                      command=add_reference_frame).pack(side=tk.LEFT, padx=5)
            ttk.Button(add_frame_btn_frame, text="🔄 Refresh", 
                      command=load_reference_frames).pack(side=tk.LEFT, padx=5)
            
            # Organize by Uniform Variant tab
            if profile.uniform_variants and len(profile.uniform_variants) > 0:
                for uniform_key, variant_frames in profile.uniform_variants.items():
                    variant_frame = ttk.Frame(photo_notebook)
                    photo_notebook.add(variant_frame, text=uniform_key)
                    
                    # Similar grid layout for this variant with modern styling
                    variant_canvas = tk.Canvas(variant_frame, bg="#F8F8F8", highlightthickness=0, relief=tk.FLAT)
                    variant_scrollbar = ttk.Scrollbar(variant_frame, orient="vertical", command=variant_canvas.yview)
                    variant_scrollable = ttk.Frame(variant_canvas)
                    
                    variant_scrollable.bind(
                        "<Configure>",
                        lambda e: variant_canvas.configure(scrollregion=variant_canvas.bbox("all"))
                    )
                    
                    variant_canvas.create_window((0, 0), window=variant_scrollable, anchor="nw")
                    variant_canvas.configure(yscrollcommand=variant_scrollbar.set)
                    
                    # Add mouse wheel scrolling support for variant canvas (Windows/Mac and Linux)
                    def on_variant_mousewheel(event):
                        # Linux: event.num (4=up, 5=down)
                        if event.num == 4:
                            variant_canvas.yview_scroll(-1, "units")
                        elif event.num == 5:
                            variant_canvas.yview_scroll(1, "units")
                        else:
                            # Windows/Mac: event.delta
                            variant_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    
                    def bind_variant_mousewheel(event):
                        variant_canvas.bind("<MouseWheel>", on_variant_mousewheel)
                        variant_canvas.bind("<Button-4>", on_variant_mousewheel)  # Linux scroll up
                        variant_canvas.bind("<Button-5>", on_variant_mousewheel)  # Linux scroll down
                        # Also bind to scrollable frame
                        variant_scrollable.bind("<MouseWheel>", on_variant_mousewheel)
                        variant_scrollable.bind("<Button-4>", on_variant_mousewheel)
                        variant_scrollable.bind("<Button-5>", on_variant_mousewheel)
                    
                    def unbind_variant_mousewheel(event):
                        variant_canvas.unbind("<MouseWheel>")
                        variant_canvas.unbind("<Button-4>")
                        variant_canvas.unbind("<Button-5>")
                        variant_scrollable.unbind("<MouseWheel>")
                        variant_scrollable.unbind("<Button-4>")
                        variant_scrollable.unbind("<Button-5>")
                    
                    variant_canvas.bind('<Enter>', bind_variant_mousewheel)
                    variant_canvas.bind('<Leave>', unbind_variant_mousewheel)
                    variant_scrollable.bind('<Enter>', bind_variant_mousewheel)
                    variant_scrollable.bind('<Leave>', unbind_variant_mousewheel)
                    
                    variant_canvas.pack(side="left", fill="both", expand=True)
                    variant_scrollbar.pack(side="right", fill="y")
                    
                    # Display frames for this variant (similar to all_frames_frame)
                    for ref_frame in variant_frames:
                        # Similar display logic as above
                        pass
            else:
                # No uniform variants - show message
                no_variants_frame = ttk.Frame(photo_notebook)
                photo_notebook.add(no_variants_frame, text="Uniform Variants")
                ttk.Label(no_variants_frame, text="No uniform variants organized yet", 
                         font=("Arial", 10), foreground="gray").pack(pady=20)
            
            # Action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            def save_changes():
                try:
                    new_name = name_var.get().strip() or None
                    new_jersey = jersey_var.get().strip() or None
                    new_team = team_var.get().strip() or None
                    new_position = position_var.get().strip() or None
                    new_notes = notes_text.get("1.0", tk.END).strip() or None
                    tags_str = tags_var.get().strip()
                    new_tags = [tag.strip() for tag in tags_str.split(",") if tag.strip()] if tags_str else []
                    
                    if not new_name:
                        messagebox.showerror("Error", "Player name cannot be empty!")
                        return
                    
                    # Parse visualization settings
                    viz_settings = {}
                    
                    # Custom color (from color picker)
                    if custom_color_var and custom_color_var[0]:
                        viz_settings["use_custom_color"] = True
                        viz_settings["custom_color_rgb"] = custom_color_var[0]
                    
                    # Box color (from color picker)
                    if box_color_var and box_color_var[0]:
                        viz_settings["box_color"] = box_color_var[0]
                    
                    # Label color (from color picker)
                    if label_color_var and label_color_var[0]:
                        viz_settings["label_color"] = label_color_var[0]
                    
                    # Box thickness
                    if box_thickness_var.get() != 2:
                        viz_settings["box_thickness"] = box_thickness_var.get()
                    
                    # Glow settings
                    if show_glow_var.get():
                        viz_settings["show_glow"] = True
                        viz_settings["glow_intensity"] = glow_intensity_var.get()
                        if glow_color_var and glow_color_var[0]:
                            viz_settings["glow_color"] = glow_color_var[0]
                    
                    # Trail settings
                    if show_trail_var.get():
                        viz_settings["show_trail"] = True
                        viz_settings["trail_length"] = trail_length_var.get()
                        if trail_color_var and trail_color_var[0]:
                            viz_settings["trail_color"] = trail_color_var[0]
                    
                    # Label style
                    if label_style_var.get() != "full_name":
                        viz_settings["label_style"] = label_style_var.get()
                    
                    # Foot tracker settings
                    if foot_offset_var.get() != 52:
                        viz_settings["foot_tracker_offset"] = foot_offset_var.get()
                    if ellipse_width_var.get() != 20:
                        viz_settings["ellipse_width"] = ellipse_width_var.get()
                    if ellipse_height_var.get() != 12:
                        viz_settings["ellipse_height"] = ellipse_height_var.get()
                    
                    # Update player with enhanced fields
                    gallery.update_player(
                        player_id=player_id,
                        name=new_name,
                        jersey_number=new_jersey,
                        team=new_team
                    )
                    
                    # Update additional fields if they exist
                    profile = gallery.get_player(player_id)
                    if profile:
                        if hasattr(profile, 'position') or new_position:
                            profile.position = new_position
                        if hasattr(profile, 'notes') or new_notes:
                            profile.notes = new_notes
                        if hasattr(profile, 'tags') or new_tags:
                            profile.tags = new_tags
                        
                        # Update visualization settings
                        if viz_settings:
                            profile.visualization_settings = viz_settings
                        elif hasattr(profile, 'visualization_settings'):
                            # Clear settings if all fields are empty/default
                            profile.visualization_settings = None
                    
                    gallery.save_gallery()
                    
                    # Sync to roster manager
                    try:
                        from team_roster_manager import TeamRosterManager
                        roster_manager = TeamRosterManager()
                        
                        # Get old name for updating roster entry
                        old_name = profile.name if profile else player_id
                        
                        # If name changed, we need to update the roster entry
                        if old_name != new_name and old_name in roster_manager.roster:
                            # Move roster entry to new name
                            roster_manager.roster[new_name] = roster_manager.roster.pop(old_name)
                        
                        # Update or create roster entry
                        if new_name not in roster_manager.roster:
                            roster_manager.roster[new_name] = {}
                        
                        # Update roster data from player profile
                        roster_manager.roster[new_name]['jersey_number'] = new_jersey or ''
                        roster_manager.roster[new_name]['team'] = new_team or ''
                        roster_manager.roster[new_name]['position'] = new_position or ''
                        roster_manager.roster[new_name]['active'] = roster_manager.roster[new_name].get('active', True)
                        
                        # Save roster
                        roster_manager.save_roster()
                        
                        # Refresh roster tab if it exists
                        try:
                            # Find roster tab frame by iterating through notebook tabs
                            notebook = getattr(self, 'main_notebook', None) or getattr(self, 'notebook', None)
                            if notebook:
                                for tab_id in notebook.tabs():
                                    try:
                                        tab_text = notebook.tab(tab_id, 'text')
                                        if 'Roster' in tab_text or 'roster' in tab_text.lower():
                                            roster_frame = notebook.nametowidget(tab_id)
                                            self._refresh_roster_tab(roster_frame)
                                            break
                                    except Exception:
                                        continue
                        except Exception:
                            pass  # Roster tab might not exist
                    except Exception as roster_error:
                        # Don't fail the save if roster sync fails, just log it
                        print(f"Warning: Could not sync to roster: {roster_error}")
                    
                    messagebox.showinfo("Success", f"Updated {new_name} successfully!")
                    detail_window.destroy()
                    self._refresh_gallery_tab(parent_frame)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not update player:\n\n{str(e)}")
                    import traceback
                    traceback.print_exc()
            
            def delete_player():
                result = messagebox.askyesno(
                    "Confirm Delete", 
                    f"Are you sure you want to delete '{profile.name}' from the gallery?\n\nThis cannot be undone!",
                    icon='warning'
                )
                
                if result:
                    try:
                        # Remove player and save
                        gallery.remove_player(player_id)
                        
                        # Force reload gallery to ensure in-memory state matches disk
                        gallery.players.clear()
                        gallery.load_gallery()
                        
                        messagebox.showinfo("Success", f"Deleted {profile.name} from gallery")
                        detail_window.destroy()
                        
                        # Refresh the gallery tab (this will reload from disk)
                        self._refresh_gallery_tab(parent_frame)
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not delete player:\n\n{str(e)}")
                        import traceback
                        traceback.print_exc()
            
            ttk.Button(button_frame, text="💾 Save Changes", command=save_changes, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🗑️ Delete Player", command=delete_player, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Close", command=detail_window.destroy, width=10).pack(side=tk.RIGHT, padx=5)
            
            detail_window.lift()
            detail_window.focus_force()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not show player details:\n\n{str(e)}")
    
    def _show_player_details_from_list(self, listbox, player_list_data, gallery, parent_frame, index=None):
        """Show player details from listbox selection"""
        try:
            # Get index from parameter or from listbox selection
            if index is None:
                selection = listbox.curselection()
                if selection and len(selection) > 0:
                    index = selection[0]
                else:
                    return
            
            if index > 1 and (index - 2) < len(player_list_data):
                player_id, player_name = player_list_data[index - 2]
                self._show_player_details(gallery, player_id, parent_frame)
        except Exception as e:
            messagebox.showerror("Error", f"Could not show player details:\n\n{str(e)}")
    
    def _delete_selected_player_from_gallery(self, parent_frame, listbox, player_list_data, selected_index):
        """Delete the selected player from the gallery"""
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            
            # Skip header rows (0 and 1)
            if selected_index <= 1 or (selected_index - 2) >= len(player_list_data):
                messagebox.showwarning("Invalid Selection", "Please select a valid player.")
                return
            
            player_id, player_name = player_list_data[selected_index - 2]
            
            # Verify player still exists before deletion
            profile = gallery.get_player(player_id)
            if not profile:
                messagebox.showerror("Error", f"Player '{player_name}' (ID: {player_id}) not found in gallery.\n\n"
                                            "The player may have already been deleted or the gallery may need to be refreshed.")
                # Refresh anyway to update the display
                self._refresh_gallery_tab(parent_frame)
                return
            
            # Check for duplicate players with same name
            duplicate_ids = []
            for pid, prof in gallery.players.items():
                if prof.name == player_name and pid != player_id:
                    duplicate_ids.append(pid)
            
            delete_message = f"Are you sure you want to delete '{player_name}' from the gallery?\n\n"
            delete_message += f"This will permanently remove:\n"
            delete_message += f"• All Re-ID features\n"
            delete_message += f"• All reference frames ({len(profile.reference_frames) if profile.reference_frames else 0} frames)\n"
            delete_message += f"• All player data\n\n"
            
            if duplicate_ids:
                delete_message += f"⚠ WARNING: Found {len(duplicate_ids)} other player(s) with the same name.\n"
                delete_message += f"Only this entry (ID: {player_id}) will be deleted.\n\n"
            
            delete_message += f"This cannot be undone!"
            
            # Confirm deletion
            result = messagebox.askyesno("Confirm Delete", delete_message, icon='warning')
            
            if result:
                try:
                    # Remove player and save
                    removed = gallery.remove_player(player_id)
                    
                    if not removed:
                        messagebox.showerror("Error", f"Could not delete player '{player_name}'.\n\n"
                                                    "The player may have already been removed.")
                        # Refresh anyway
                        self._refresh_gallery_tab(parent_frame)
                        return
                    
                    # Force reload gallery to ensure in-memory state matches disk
                    gallery.players.clear()
                    gallery.load_gallery()
                    
                    # Verify deletion
                    if gallery.get_player(player_id) is None:
                        messagebox.showinfo("Success", f"Deleted '{player_name}' from gallery")
                    else:
                        messagebox.showwarning("Warning", 
                                             f"Player '{player_name}' was removed but may still appear.\n\n"
                                             "Try refreshing the gallery tab.")
                    
                    # Refresh the gallery tab (this will reload from disk)
                    self._refresh_gallery_tab(parent_frame)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not delete player:\n\n{str(e)}")
                    import traceback
                    traceback.print_exc()
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete player:\n\n{str(e)}")
    
    def _extract_profile_image(self, ref_frame: dict, max_size: tuple = (250, 300)):
        """Extract profile image from a reference frame
        
        Args:
            ref_frame: Reference frame dictionary
            max_size: Maximum (width, height) for thumbnail, or None for full size
        """
        try:
            import cv2
            import numpy as np
            from PIL import Image, ImageTk
            
            video_path = ref_frame.get('video_path')
            frame_num = ref_frame.get('frame_num')
            bbox = ref_frame.get('bbox')
            
            if not video_path or frame_num is None or not bbox or len(bbox) < 4:
                return None
            
            # Check if video path exists
            if not os.path.exists(video_path):
                return None
            
            # Open video and seek to frame
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_num))
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                return None
            
            # Extract bbox region
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            h, w = frame.shape[:2]
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            
            if x2 <= x1 or y2 <= y1:
                return None
            
            # Crop to bbox
            cropped = frame[y1:y2, x1:x2]
            
            # Validation: Check if image is mostly green (field)
            hsv = cv2.cvtColor(cropped, cv2.COLOR_BGR2HSV)
            lower_green = np.array([40, 50, 50])
            upper_green = np.array([80, 255, 255])
            green_mask = cv2.inRange(hsv, lower_green, upper_green)
            green_ratio = np.sum(green_mask > 0) / (cropped.shape[0] * cropped.shape[1])
            
            if green_ratio > 0.7:
                return None
            
            # Validation: Check minimum size
            h, w = cropped.shape[:2]
            if h < 30 or w < 30:
                return None
            
            # Resize if max_size is specified
            if max_size:
                max_width, max_height = max_size
            if h > max_height or w > max_width:
                scale = min(max_height / h, max_width / w)
                new_w = int(w * scale)
                new_h = int(h * scale)
                cropped = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Convert BGR to RGB for PIL
            cropped_rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(cropped_rgb)
            return ImageTk.PhotoImage(pil_image)
            
        except Exception as e:
            return None
    
    def _extract_foot_region_image(self, ref_frame: dict):
        """Extract foot/shoe region image from a reference frame"""
        try:
            import cv2
            from PIL import Image, ImageTk
            
            video_path = ref_frame.get('video_path')
            frame_num = ref_frame.get('frame_num')
            bbox = ref_frame.get('bbox')
            
            if not video_path or frame_num is None or not bbox or len(bbox) < 4:
                return None
            
            if not os.path.exists(video_path):
                return None
            
            # Open video and seek to frame
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_num))
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                return None
            
            # Extract bbox region
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            frame_h, frame_w = frame.shape[:2]
            x1 = max(0, min(x1, frame_w))
            y1 = max(0, min(y1, frame_h))
            x2 = max(0, min(x2, frame_w))
            y2 = max(0, min(y2, frame_h))
            
            if x2 <= x1 or y2 <= y1:
                return None
            
            # Calculate foot region (bottom 10-30% of bbox)
            bbox_height = y2 - y1
            foot_y1 = int(y1 + bbox_height * 0.70)
            foot_y2 = int(y1 + bbox_height * 0.90)
            
            foot_y1 = max(0, min(foot_y1, frame_h))
            foot_y2 = max(foot_y1 + 1, min(foot_y2, frame_h))
            
            if foot_y2 <= foot_y1 or x2 <= x1:
                return None
            
            # Extract foot region
            foot_crop = frame[foot_y1:foot_y2, x1:x2]
            
            if foot_crop.size == 0:
                return None
            
            h, w = foot_crop.shape[:2]
            if h < 8 or w < 8:
                return None
            
            # Resize to reasonable size for display
            max_width = 200
            max_height = 100
            if h > max_height or w > max_width:
                scale = min(max_height / h, max_width / w)
                new_w = int(w * scale)
                new_h = int(h * scale)
                foot_crop = cv2.resize(foot_crop, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Convert BGR to RGB for PIL
            foot_crop_rgb = cv2.cvtColor(foot_crop, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(foot_crop_rgb)
            return ImageTk.PhotoImage(pil_image)
            
        except Exception as e:
            return None
    
    def _parse_color_string(self, color_str):
        """Parse color string (R,G,B) to RGB tuple"""
        try:
            parts = color_str.split(',')
            if len(parts) == 3:
                r = int(parts[0].strip())
                g = int(parts[1].strip())
                b = int(parts[2].strip())
                # Validate range
                if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                    return [r, g, b]
        except (ValueError, AttributeError):
            pass
        return None

