"""
Main Window for Soccer Analysis GUI
Orchestrates all GUI components and tabs
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
from pathlib import Path
from typing import Optional

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
        
        # Set window icon
        self._set_window_icon()
        
        self._setup_window()
        
        # Initialize all variables
        self._init_variables()
        
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
        """Show setup wizard as tutorial on first run"""
        response = messagebox.askyesno(
            "Welcome to Soccer Analysis Tool!",
            "Welcome! Let's get you started with the Interactive Setup Wizard.\n\n"
            "This wizard will guide you through:\n"
            "• Setting up your video\n"
            "• Calibrating the field\n"
            "• Tagging players\n"
            "• Configuring team colors\n\n"
            "Would you like to start the setup wizard now?",
            icon='question'
        )
        if response:
            self.open_setup_wizard()
    
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
        
        # Advanced tracking
        self.use_harmonic_mean = tk.BooleanVar(value=True)
        self.use_expansion_iou = tk.BooleanVar(value=True)
        self.enable_soccer_reid_training = tk.BooleanVar(value=False)
        self.use_enhanced_kalman = tk.BooleanVar(value=True)
        self.use_ema_smoothing = tk.BooleanVar(value=True)
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
    
    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_container = ttk.Frame(self.root, padding="2")
        main_container.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Title frame
        title_frame = ttk.Frame(main_container)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        main_container.columnconfigure(0, weight=1)
        
        title_label = ttk.Label(title_frame, text="Soccer Video Analysis Tool", 
                               font=("Arial", 16, "bold"))
        title_label.pack(side=tk.LEFT, padx=(0, 20))
        
        # Project name display
        project_name_frame = ttk.Frame(title_frame)
        project_name_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(project_name_frame, text="Project:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        self.project_name_label = ttk.Label(project_name_frame, textvariable=self.current_project_name, 
                                           font=("Arial", 10), foreground="blue")
        self.project_name_label.pack(side=tk.LEFT)
        
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
    
    def _create_scrollable_tab(self, tab_name: str) -> ttk.Frame:
        """Create a scrollable tab frame"""
        tab_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(tab_frame, text=tab_name)
        
        # Create scrollable canvas
        canvas = tk.Canvas(tab_frame, highlightthickness=0, bg="white", relief=tk.FLAT)
        scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Create content frame inside canvas
        content_frame = ttk.Frame(canvas, padding="10")
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
    
    def _create_right_panel(self, main_container: ttk.Frame):
        """Create right panel with action buttons"""
        right_container = ttk.Frame(main_container)
        # Extend panel to cover all rows (title, notebook, progress, status, log)
        right_container.grid(row=0, column=1, rowspan=6, sticky="nsew", padx=(10, 0))
        main_container.columnconfigure(1, weight=0)
        main_container.rowconfigure(1, weight=1)
        # Allow right container to expand vertically
        right_container.rowconfigure(0, weight=1)
        
        # Create scrollable canvas for right panel
        # Increased width to use more space to the right of the log
        right_canvas = tk.Canvas(right_container, width=280, borderwidth=0, highlightthickness=0)
        right_scrollbar = ttk.Scrollbar(right_container, orient="vertical", command=right_canvas.yview)
        right_canvas.configure(yscrollcommand=right_scrollbar.set)
        
        right_scrollbar.pack(side="right", fill="y")
        right_canvas.pack(side="left", fill="both", expand=True)
        
        # Frame inside canvas
        right_panel = ttk.LabelFrame(right_canvas, text="Tools & Actions", padding="10")
        right_canvas_window = right_canvas.create_window((0, 0), window=right_panel, anchor="nw")
        
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
        
        # Analysis Controls
        ttk.Label(right_panel, text="Analysis Controls:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.preview_button = ttk.Button(right_panel, text="Preview (15 sec)", 
                                         command=self.preview_analysis, width=20)
        self.preview_button.grid(row=1, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.preview_frames_button = ttk.Button(right_panel, text="Preview Frames", 
                                                command=self.preview_frames, width=20)
        self.preview_frames_button.grid(row=2, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.start_button = ttk.Button(right_panel, text="Start Analysis", 
                                      command=self.start_analysis, width=20)
        self.start_button.grid(row=3, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.stop_button = ttk.Button(right_panel, text="Stop Analysis", 
                                     command=self.stop_analysis, state=tk.DISABLED, width=20)
        self.stop_button.grid(row=4, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.conflict_resolution_button = ttk.Button(right_panel, text="Conflict Resolution", 
                                                    command=self.open_conflict_resolution, width=20)
        self.conflict_resolution_button.grid(row=5, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Analysis & Results
        ttk.Label(right_panel, text="Analysis & Results:", font=("Arial", 9, "bold")).grid(row=6, column=0, sticky=tk.W, pady=(15, 5))
        
        self.open_folder_button = ttk.Button(right_panel, text="Open Output Folder", 
                                             command=self.open_output_folder, state=tk.DISABLED, width=20)
        self.open_folder_button.grid(row=7, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.analyze_csv_button = ttk.Button(right_panel, text="Analyze CSV Data", 
                                             command=self.analyze_csv, width=20)
        self.analyze_csv_button.grid(row=8, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.analytics_selection_button = ttk.Button(right_panel, text="Analytics Selection", 
                                                     command=self.open_analytics_selection, width=20)
        self.analytics_selection_button.grid(row=9, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.setup_checklist_button = ttk.Button(right_panel, text="Setup Checklist", 
                                                 command=self.open_setup_checklist, width=20)
        self.setup_checklist_button.grid(row=10, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.evaluate_tracking_button = ttk.Button(right_panel, text="Evaluate Tracking Metrics", 
                                                    command=self.evaluate_tracking_metrics, width=20)
        self.evaluate_tracking_button.grid(row=11, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Anchor Frame Tools
        ttk.Label(right_panel, text="Anchor Frame Tools:", font=("Arial", 9, "bold")).grid(row=12, column=0, sticky=tk.W, pady=(15, 5))
        
        self.convert_tracks_anchor_button = ttk.Button(right_panel, text="Convert Tracks → Anchors", 
                                                       command=self.convert_tracks_to_anchors, width=20)
        self.convert_tracks_anchor_button.grid(row=13, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.convert_tags_anchor_button = ttk.Button(right_panel, text="Convert Tags → Anchors", 
                                                     command=self.convert_tags_to_anchors, width=20)
        self.convert_tags_anchor_button.grid(row=14, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.fix_anchor_frames_button = ttk.Button(right_panel, text="Fix Failed Anchors", 
                                                   command=self.fix_failed_anchor_frames, width=20)
        self.fix_anchor_frames_button.grid(row=15, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.optimize_anchor_frames_button = ttk.Button(right_panel, text="Optimize Anchors", 
                                                        command=self.optimize_anchor_frames, width=20)
        self.optimize_anchor_frames_button.grid(row=16, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.clear_anchor_frames_button = ttk.Button(right_panel, text="Clear Anchor Frames", 
                                                     command=self.clear_anchor_frames, width=20)
        self.clear_anchor_frames_button.grid(row=17, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Player Management
        ttk.Label(right_panel, text="Player Management:", font=("Arial", 9, "bold")).grid(row=18, column=0, sticky=tk.W, pady=(15, 5))
        
        self.interactive_learning_button = ttk.Button(right_panel, text="Interactive Player Learning", 
                                                      command=self.open_interactive_learning, width=20)
        self.interactive_learning_button.grid(row=19, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.track_review_button = ttk.Button(right_panel, text="Track Review & Assign", 
                                             command=self.open_track_review, width=20)
        self.track_review_button.grid(row=20, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.clear_gallery_refs_button = ttk.Button(right_panel, text="Clear Gallery References", 
                                                    command=self.clear_gallery_references, width=20)
        self.clear_gallery_refs_button.grid(row=21, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.consolidate_ids_button = ttk.Button(right_panel, text="Consolidate IDs", 
                                                command=self.consolidate_ids, width=20)
        self.consolidate_ids_button.grid(row=22, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.export_reid_button = ttk.Button(right_panel, text="Export ReID Model", 
                                             command=self.export_reid_model, width=20)
        self.export_reid_button.grid(row=23, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Setup & Calibration
        ttk.Label(right_panel, text="Setup & Calibration:", font=("Arial", 9, "bold")).grid(row=24, column=0, sticky=tk.W, pady=(15, 5))
        
        self.color_helper_button = ttk.Button(right_panel, text="Color Helper", 
                                              command=self.open_color_helper, width=20)
        self.color_helper_button.grid(row=25, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.field_calibration_button = ttk.Button(right_panel, text="Calibrate Field", 
                                                   command=self.open_field_calibration, width=20)
        self.field_calibration_button.grid(row=26, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        if create_tooltip:
            create_tooltip(self.field_calibration_button,
                          TOOLTIP_DATABASE.get("calibrate_field", {}).get("text", "Calibrate field boundaries and dimensions"),
                          TOOLTIP_DATABASE.get("calibrate_field", {}).get("detailed"))
        
        self.setup_wizard_button = ttk.Button(right_panel, text="Setup Wizard", 
                                             command=self.open_setup_wizard, width=20)
        self.setup_wizard_button.grid(row=27, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        if create_tooltip:
            create_tooltip(self.setup_wizard_button,
                          TOOLTIP_DATABASE.get("setup_wizard", {}).get("text", "Open Interactive Setup Wizard"),
                          TOOLTIP_DATABASE.get("setup_wizard", {}).get("detailed"))
        
        # Player Gallery
        ttk.Label(right_panel, text="Player Gallery:", font=("Arial", 9, "bold")).grid(row=28, column=0, sticky=tk.W, pady=(15, 5))
        
        self.tag_players_gallery_button = ttk.Button(right_panel, text="Tag Players (Gallery)", 
                                                     command=self.open_tag_players_gallery, width=20)
        self.tag_players_gallery_button.grid(row=29, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.gallery_seeder_button = ttk.Button(right_panel, text="Player Gallery Seeder", 
                                                command=self.open_gallery_seeder, width=20)
        self.gallery_seeder_button.grid(row=30, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Video Tools
        ttk.Label(right_panel, text="Video Tools:", font=("Arial", 9, "bold")).grid(row=31, column=0, sticky=tk.W, pady=(15, 5))
        
        self.video_splicer_button = ttk.Button(right_panel, text="Video Splicer", 
                                              command=self.open_video_splicer, width=20)
        self.video_splicer_button.grid(row=32, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Viewers
        ttk.Label(right_panel, text="Viewers:", font=("Arial", 9, "bold")).grid(row=33, column=0, sticky=tk.W, pady=(15, 5))
        
        self.playback_viewer_button = ttk.Button(right_panel, text="Playback Viewer", 
                                                 command=self.open_playback_viewer, width=20)
        self.playback_viewer_button.grid(row=34, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        if create_tooltip:
            create_tooltip(self.playback_viewer_button,
                          TOOLTIP_DATABASE.get("playback_viewer", {}).get("text", "Open playback viewer for analyzed video"),
                          TOOLTIP_DATABASE.get("playback_viewer", {}).get("detailed"))
        
        self.speed_tracking_button = ttk.Button(right_panel, text="Speed Tracking", 
                                               command=self.open_speed_tracking, width=20)
        self.speed_tracking_button.grid(row=35, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Project Management
        ttk.Label(right_panel, text="Project Management:", font=("Arial", 9, "bold")).grid(row=36, column=0, sticky=tk.W, pady=(15, 5))
        
        self.create_project_button = ttk.Button(right_panel, text="Create New Project", 
                                               command=self.create_new_project, width=20)
        self.create_project_button.grid(row=37, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.save_project_button = ttk.Button(right_panel, text="Save Project", 
                                              command=self.save_project, width=20)
        self.save_project_button.grid(row=38, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.save_project_as_button = ttk.Button(right_panel, text="Save Project As...", 
                                                 command=self.save_project_as, width=20)
        self.save_project_as_button.grid(row=39, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.load_project_button = ttk.Button(right_panel, text="Load Project", 
                                              command=self.load_project, width=20)
        self.load_project_button.grid(row=40, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.rename_project_button = ttk.Button(right_panel, text="Rename Project", 
                                                command=self.rename_project, width=20)
        self.rename_project_button.grid(row=41, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        right_panel.columnconfigure(0, weight=1)
    
    def _create_progress_and_status(self, main_container: ttk.Frame):
        """Create enhanced progress bar and status label with time estimates"""
        # Progress frame
        progress_frame = ttk.Frame(main_container)
        progress_frame.grid(row=2, column=0, sticky="ew", pady=10, padx=5)
        progress_frame.columnconfigure(0, weight=1)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                            maximum=100, length=400)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        # Cancel button (hidden initially)
        self.cancel_button = ttk.Button(progress_frame, text="Cancel", 
                                        command=self._request_cancel, state=tk.DISABLED)
        self.cancel_button.grid(row=0, column=1, padx=5)
        
        # Status frame with detailed information
        status_frame = ttk.Frame(main_container)
        status_frame.grid(row=3, column=0, sticky="ew", pady=5, padx=5)
        status_frame.columnconfigure(0, weight=1)
        
        # Main status label
        self.status_label = ttk.Label(status_frame, text="Ready", 
                                     font=("Arial", 10))
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Detailed status label (time estimates, speed, etc.)
        self.detailed_status_label = ttk.Label(status_frame, text="", 
                                               font=("Arial", 8), foreground="gray")
        self.detailed_status_label.grid(row=1, column=0, sticky=tk.W, pady=(2, 0))
        
        # Progress percentage label
        self.progress_percent_label = ttk.Label(status_frame, text="", 
                                                font=("Arial", 9, "bold"))
        self.progress_percent_label.grid(row=0, column=1, sticky=tk.E, padx=(10, 0))
    
    def _create_log_output(self, main_container: ttk.Frame):
        """Create log output area"""
        log_label = ttk.Label(main_container, text="Processing Log:", 
                             font=("Arial", 10, "bold"))
        log_label.grid(row=4, column=0, sticky=tk.W, pady=(10, 5))
        
        # Reduced height from 12 to 6 to give more space to main selection area
        self.log_text = scrolledtext.ScrolledText(main_container, height=6, width=60, 
                                                  wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=5, column=0, sticky="ew", pady=5)
        # Removed weight=1 so log doesn't expand, allowing notebook area to be larger
        # main_container.rowconfigure(5, weight=1)  # Commented out to prevent expansion
    
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
        """Create menu bar with Edit menu for undo/redo"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
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
            self.log_message(f"Output will be saved to: {filename}")
            self._check_and_enable_output_buttons()
            self._update_undo_redo_states()
            
            # Show success toast
            if self.toast_manager:
                self.toast_manager.success(f"Output file set: {os.path.basename(filename)}")
    
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
        """Preview analysis (15 seconds)"""
        try:
            # Delegate to legacy implementation
            from legacy.soccer_analysis_gui import SoccerAnalysisGUI as LegacyGUI
            legacy_gui = LegacyGUI(self.root)
            legacy_gui.preview_analysis()
        except Exception as e:
            self.log_message(f"Preview analysis error: {e}")
            messagebox.showerror("Error", f"Could not run preview: {e}")
    
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
    
    def start_analysis(self):
        """Start full analysis with enhanced progress tracking"""
        try:
            # Validate inputs before starting
            if not self.input_file.get():
                messagebox.showwarning("No Input File", "Please select an input video file first.")
                return
            
            if not os.path.exists(self.input_file.get()):
                messagebox.showerror("File Not Found", f"Input file not found:\n{self.input_file.get()}")
                return
            
            # Check disk space (rough estimate)
            try:
                import shutil
                free_space = shutil.disk_usage(os.path.dirname(self.input_file.get())).free
                # Estimate 500MB per minute of video (conservative)
                video_duration = 0  # TODO: Get actual duration
                estimated_size = 500 * 1024 * 1024 * 10  # 5GB default estimate
                if free_space < estimated_size:
                    response = messagebox.askyesno(
                        "Low Disk Space",
                        f"Warning: Low disk space detected.\n\n"
                        f"Free space: {free_space / (1024**3):.1f} GB\n"
                        f"Estimated needed: {estimated_size / (1024**3):.1f} GB\n\n"
                        f"Continue anyway?",
                        icon='warning'
                    )
                    if not response:
                        return
            except:
                pass  # Skip disk space check if it fails
            
            # Initialize progress tracker
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
            
            # Enable cancel button
            if hasattr(self, 'cancel_button'):
                self.cancel_button.config(state=tk.NORMAL)
            
            # Delegate to legacy implementation
            from legacy.soccer_analysis_gui import SoccerAnalysisGUI as LegacyGUI
            legacy_gui = LegacyGUI(self.root)
            # Copy current settings to legacy GUI
            for attr in ['input_file', 'output_file', 'ball_tracking_enabled', 'player_tracking_enabled']:
                if hasattr(self, attr):
                    setattr(legacy_gui, attr, getattr(self, attr))
            legacy_gui.start_analysis()
            
            # Start progress update loop
            self._start_progress_updates()
            
        except Exception as e:
            self.log_message(f"Start analysis error: {e}")
            messagebox.showerror("Error", f"Could not start analysis: {e}")
            import traceback
            traceback.print_exc()
    
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
        """Analyze CSV data"""
        try:
            try:
                from analytics_selection_gui import AnalyticsSelectionGUI
            except ImportError:
                try:
                    from legacy.analytics_selection_gui import AnalyticsSelectionGUI
                except ImportError:
                    messagebox.showerror("Error", "Could not import analytics_selection_gui.py")
                    return
            
            csv_file = filedialog.askopenfilename(
                title="Select CSV File to Analyze",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if csv_file:
                analytics_window = tk.Toplevel(self.root)
                analytics_window.title("CSV Analysis")
                analytics_window.geometry("1200x800")
                app = AnalyticsSelectionGUI(analytics_window, csv_file)
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
                    messagebox.showerror("Error", "Could not import analytics_selection_gui.py")
                    return
            
            analytics_window = tk.Toplevel(self.root)
            analytics_window.title("Analytics Selection")
            analytics_window.geometry("1000x700")
            analytics_window.transient(self.root)
            
            app = AnalyticsSelectionGUI(analytics_window)
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
                    messagebox.showerror("Error", "Could not import setup_checklist.py")
                    return
            
            checklist_window = tk.Toplevel(self.root)
            checklist_window.title("Setup Checklist")
            checklist_window.geometry("800x600")
            checklist_window.transient(self.root)
            
            app = SetupChecklist(checklist_window)
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
                    messagebox.showerror("Error", "Could not import convert_tracks_to_anchor_frames.py")
                    return
            
            convert_tracks_to_anchor_frames_gui(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Could not convert tracks: {e}")
            import traceback
            traceback.print_exc()
    
    def convert_tags_to_anchors(self):
        """Convert tags to anchor frames - same as track converter"""
        self.open_track_converter()
    
    def fix_failed_anchor_frames(self):
        """Fix failed anchor frames"""
        try:
            try:
                from fix_failed_anchor_frames import fix_failed_anchor_frames_gui
            except ImportError:
                try:
                    from legacy.fix_failed_anchor_frames import fix_failed_anchor_frames_gui
                except ImportError:
                    messagebox.showerror("Error", "Could not import fix_failed_anchor_frames.py")
                    return
            
            fix_failed_anchor_frames_gui(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Could not fix anchor frames: {e}")
            import traceback
            traceback.print_exc()
    
    def optimize_anchor_frames(self):
        """Optimize anchor frames"""
        try:
            try:
                from optimize_anchor_frames import optimize_anchor_frames_gui
            except ImportError:
                try:
                    from legacy.optimize_anchor_frames import optimize_anchor_frames_gui
                except ImportError:
                    messagebox.showerror("Error", "Could not import optimize_anchor_frames.py")
                    return
            
            optimize_anchor_frames_gui(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Could not optimize anchor frames: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_anchor_frames(self):
        """Clear anchor frames"""
        # Warning dialog for destructive action
        response = messagebox.askyesno(
            "⚠️ Warning: Clear Anchor Frames",
            "Are you sure you want to clear ALL anchor frames?\n\n"
            "This will:\n"
            "• Remove all manually tagged player positions\n"
            "• Delete all anchor frame data\n"
            "• Reset player identification for this video\n\n"
            "This action cannot be undone!\n\n"
            "Do you want to continue?",
            icon='warning'
        )
        
        if not response:
            return
        
        try:
            # Find anchor frame files
            anchor_files = []
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
                base_name = os.path.splitext(video_path)[0]
                anchor_files.append(f"{base_name}_anchor_frames.json")
                anchor_files.append(f"PlayerTagsSeed-{os.path.basename(base_name)}.json")
            
            for anchor_file in anchor_files:
                if os.path.exists(anchor_file):
                    os.remove(anchor_file)
                    self.log_message(f"Removed: {anchor_file}")
            
            # Show success confirmation
            messagebox.showinfo("Success", "All anchor frames have been cleared successfully.")
            
            # Show success toast
            if self.toast_manager:
                self.toast_manager.success("Anchor frames cleared")
        except Exception as e:
            messagebox.showerror("Error", f"Could not clear anchor frames: {e}")
            
            # Show error toast
            if self.toast_manager:
                self.toast_manager.error(f"Failed to clear anchor frames: {str(e)[:50]}")
    
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
                from track_review_assign import TrackReviewAssign
            except ImportError:
                try:
                    from legacy.track_review_assign import TrackReviewAssign
                except ImportError:
                    messagebox.showerror("Error", "Could not import track_review_assign.py")
                    return
            
            review_window = tk.Toplevel(self.root)
            review_window.title("Track Review & Assign")
            review_window.geometry("1600x1050")
            review_window.transient(self.root)
            
            video_path = None
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
            
            app = TrackReviewAssign(review_window, video_path=video_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open track review: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_gallery_references(self):
        """Clear gallery references"""
        # Warning dialog for destructive action
        response = messagebox.askyesno(
            "⚠️ Warning: Clear Gallery References",
            "Are you sure you want to clear ALL gallery references?\n\n"
            "This will:\n"
            "• Remove all player profiles from the gallery\n"
            "• Delete all stored player features\n"
            "• Remove cross-video recognition data\n\n"
            "This action cannot be undone!\n\n"
            "Do you want to continue?",
            icon='warning'
        )
        
        if not response:
            return
        
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            gallery.clear_all()
            gallery.save()
            
            # Show success confirmation
            messagebox.showinfo("Success", "All gallery references have been cleared successfully.")
            
            # Show success toast
            if self.toast_manager:
                self.toast_manager.success("Gallery references cleared")
            
            self.log_message("Gallery references cleared")
        except Exception as e:
            messagebox.showerror("Error", f"Could not clear gallery: {e}")
            
            # Show error toast
            if self.toast_manager:
                self.toast_manager.error(f"Failed to clear gallery: {str(e)[:50]}")
    
    def consolidate_ids(self):
        """Consolidate track IDs"""
        try:
            try:
                from consolidate_ids import consolidate_ids_gui
            except ImportError:
                try:
                    from legacy.consolidate_ids import consolidate_ids_gui
                except ImportError:
                    messagebox.showerror("Error", "Could not import consolidate_ids.py")
                    return
            
            consolidate_ids_gui(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Could not consolidate IDs: {e}")
            import traceback
            traceback.print_exc()
    
    def export_reid_model(self):
        """Export ReID model"""
        try:
            output_file = filedialog.asksaveasfilename(
                title="Export ReID Model",
                defaultextension=".pth",
                filetypes=[("PyTorch models", "*.pth"), ("All files", "*.*")]
            )
            if output_file:
                try:
                    from export_reid_model import export_reid_model
                except ImportError:
                    try:
                        from legacy.export_reid_model import export_reid_model
                    except ImportError:
                        messagebox.showerror("Error", "Could not import export_reid_model.py")
                        return
                
                export_reid_model(output_file)
                messagebox.showinfo("Success", f"ReID model exported to {output_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export ReID model: {e}")
            import traceback
            traceback.print_exc()
    
    def open_color_helper(self):
        """Open color helper for team/ball colors"""
        try:
            try:
                from combined_color_helper import ColorHelperGUI
            except ImportError:
                try:
                    from legacy.combined_color_helper import ColorHelperGUI
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
            
            app = ColorHelperGUI(color_window, video_path=video_path)
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
                from video_splicer import VideoSplicerGUI
            except ImportError:
                try:
                    from legacy.video_splicer import VideoSplicerGUI
                except ImportError:
                    messagebox.showerror("Error", "Could not import video_splicer.py")
                    return
            
            splicer_window = tk.Toplevel(self.root)
            splicer_window.title("Video Splicer")
            splicer_window.geometry("1200x800")
            splicer_window.transient(self.root)
            
            app = VideoSplicerGUI(splicer_window)
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
    
    def open_setup_wizard(self):
        """Open interactive setup wizard for player tagging"""
        # Use unified viewer in setup mode
        self.open_unified_viewer(mode='setup')
    
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
        
        # Get video and CSV paths from project if available
        if not video_path and hasattr(self, 'input_file_var'):
            video_path = self.input_file_var.get()
        if not csv_path and hasattr(self, 'output_file_var'):
            csv_path = self.output_file_var.get()
        
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
            calibration_window.geometry("1200x800")
            calibration_window.transient(self.root)
            
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
            
            if project_path is None:
                filename = filedialog.askopenfilename(
                    title="Load Project",
                    filetypes=[("Project files", "*.json"), ("All files", "*.*")]
                )
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
        # TODO: Implement preview update
        pass
    
    def _check_and_enable_output_buttons(self):
        """Check if output files exist and enable buttons"""
        # TODO: Implement check
        pass
    
    def _update_focus_players_ui(self):
        """Update focus players UI"""
        # TODO: Implement
        pass

