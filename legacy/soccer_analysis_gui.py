"""
Soccer Analysis GUI Application
User-friendly interface for processing soccer practice videos
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import cast, Tuple, Optional
# Import cv2 at module level for use in preview and other methods
try:
    import cv2
except ImportError:
    cv2 = None  # Will be imported locally in methods that need it

# Import quick wins features
try:
    from gui_quick_wins import (
        ProgressTracker, UndoManager, RecentProjectsManager,
        AutoSaveManager, KeyboardShortcuts, create_tooltip,
        generate_video_thumbnail
    )
    QUICK_WINS_AVAILABLE = True
except ImportError:
    QUICK_WINS_AVAILABLE = False
    print("⚠ Quick wins features not available")

# Ensure we can import from the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Defer heavy imports until needed (makes GUI load faster)
# We'll import combined_analysis when the user actually starts processing
combined_analysis = None
OPTIMIZED_AVAILABLE = False

def load_analysis_module():
    """Lazy load the analysis module - only when needed"""
    global combined_analysis, OPTIMIZED_AVAILABLE
    
    if combined_analysis is not None:
        return True  # Already loaded
    
    # Prefer optimized version if available
    try:
        from combined_analysis_optimized import combined_analysis_optimized as combined_analysis
        OPTIMIZED_AVAILABLE = True
        return True
    except ImportError:
        try:
            from combined_analysis import combined_analysis
            OPTIMIZED_AVAILABLE = False
            return True
        except ImportError as e:
            error_msg = f"Could not import combined_analysis.py.\n\n"
            error_msg += f"Error: {str(e)}\n\n"
            error_msg += f"Current directory: {os.getcwd()}\n"
            error_msg += f"Script directory: {current_dir}\n"
            error_msg += f"Make sure combined_analysis.py is in the same folder as soccer_analysis_gui.py"
            messagebox.showerror("Import Error", error_msg)
            return False


class SoccerAnalysisGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Soccer Video Analysis Tool")
        # Set initial window size (will be adjusted after widgets are created)
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # Update window to get screen dimensions
        self.root.update_idletasks()
        
        # Set window size to fit on screen (maximize to screen size if needed)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        # Use 90% of screen size, but cap at reasonable max
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
        self.root.after_idle(self.root.attributes, '-topmost', False)  # Drop after initial focus
        
        # Variables
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.current_project_name = tk.StringVar(value="No Project")  # Track current project name
        self.current_project_path = None  # Track current project file path
        self.video_type = tk.StringVar(value="practice")  # "practice" or "game"
        self.explicit_anchor_file = tk.StringVar()  # Optional explicit PlayerTagsSeed file path
        self.dewarp_enabled = tk.BooleanVar(value=False)  # Default to False - phones auto-correct fisheye
        self.remove_net_enabled = tk.BooleanVar(value=False)  # Default to False - enable if needed
        self.ball_tracking_enabled = tk.BooleanVar(value=True)
        self.ball_min_size = tk.IntVar(value=3)  # Minimum ball size in pixels
        self.ball_max_size = tk.IntVar(value=20)  # Maximum ball size in pixels
        self.ball_trail_length = tk.IntVar(value=20)  # Ball trail length in frames
        self.player_tracking_enabled = tk.BooleanVar(value=True)
        self.csv_export_enabled = tk.BooleanVar(value=True)
        self.yolo_confidence = tk.DoubleVar(value=0.25)  # YOLO confidence threshold
        self.yolo_iou_threshold = tk.DoubleVar(value=0.45)  # YOLO IOU threshold
        self.use_imperial_units = tk.BooleanVar(value=False)  # Convert distances to feet and speeds to mph
        self.watch_only = tk.BooleanVar(value=False)  # Watch-only mode: learn without saving video
        self.show_live_viewer = tk.BooleanVar(value=False)  # Show live viewer during watch-only mode
        self.focus_players_enabled = tk.BooleanVar(value=False)  # Focus on specific players (faster learning)
        self.focused_player = None  # Single player name to focus on (None = all players)
        self.batch_focus_analyze = tk.BooleanVar(value=False)  # Batch analyze each active player
        self.analytics_preferences = {}  # Analytics selection preferences
        # Overlay system options
        self.save_base_video = tk.BooleanVar(value=False)  # Save base video without overlays
        self.export_overlay_metadata = tk.BooleanVar(value=True)  # Export overlay metadata
        self.enable_video_encoding = tk.BooleanVar(value=True)  # Enable video encoding
        self.overlay_quality = tk.StringVar(value="hd")  # Overlay quality: "sd", "hd", "4k"
        self.render_scale = tk.DoubleVar(value=1.0)  # Render scale multiplier for HD overlays
        # Video game quality graphics settings
        self.enable_advanced_blending = tk.BooleanVar(value=True)  # Enable advanced blending modes
        self.enable_motion_blur = tk.BooleanVar(value=False)  # Enable motion blur for fast objects
        self.motion_blur_amount = tk.DoubleVar(value=1.0)  # Motion blur intensity (0.0-2.0)
        self.use_professional_text = tk.BooleanVar(value=True)  # Use PIL-based professional text rendering
        # Enhanced graphics features
        self.enable_text_gradient = tk.BooleanVar(value=False)  # Enable gradient text
        self.enable_text_glow = tk.BooleanVar(value=False)  # Enable text glow effect
        self.enable_text_pulse = tk.BooleanVar(value=False)  # Enable pulsing text
        self.enable_glow_pulse = tk.BooleanVar(value=False)  # Enable pulsing glow effects
        self.enable_color_shift = tk.BooleanVar(value=False)  # Enable color-shifting glow
        self.enable_gradient_boxes = tk.BooleanVar(value=False)  # Enable gradient-filled boxes
        self.enable_particle_trails = tk.BooleanVar(value=False)  # Enable particle motion trails
        self.graphics_quality_preset = tk.StringVar(value="hd")  # Quality preset: "sd", "hd", "4k"
        self.buffer_size = tk.IntVar(value=64)
        self.batch_size = tk.IntVar(value=8)
        self.use_yolo_streaming = tk.BooleanVar(value=False)  # YOLO streaming mode option
        self.preview_max_frames = tk.IntVar(value=360)  # Maximum frames to process in preview mode (default: 360 = 15 seconds at 24fps)
        self.show_ball_trail = tk.BooleanVar(value=True)  # Option to show/hide trail
        self.trail_length = tk.IntVar(value=20)  # Number of trail points to display (default: 20, tighter)
        self.trail_buffer = tk.IntVar(value=20)  # Trail buffer size (default: 20 frames)
        self.track_thresh = tk.DoubleVar(value=0.25)  # YOLO detection threshold (lower = more detections, default 0.25 for better player coverage)
        self.match_thresh = tk.DoubleVar(value=0.6)  # Matching threshold (basic: 0.6 - more lenient for smooth tracking)
        self.track_buffer = tk.IntVar(value=50)  # ByteTrack buffer frames (legacy, not used if buffer_seconds > 0)
        self.track_buffer_seconds = tk.DoubleVar(value=5.0)  # Buffer time in seconds (default: 5.0s - keeps tracks alive longer to prevent ID loss)
        self.min_track_length = tk.IntVar(value=5)  # Minimum frames before track activates (default: 5 - more stable, prevents early ID switching)
        
        # Minimum detection size settings (configurable, no hardcoded values)
        self.min_bbox_area = tk.IntVar(value=200)  # Minimum bbox area in pixels² (default: 200)
        self.min_bbox_width = tk.IntVar(value=10)  # Minimum bbox width in pixels (default: 10)
        self.min_bbox_height = tk.IntVar(value=15)  # Minimum bbox height in pixels (default: 15)
        # Note: For very small objects, you can lower these values. A 12px wide object needs at least 1px height to have any area.
        self.tracker_type = tk.StringVar(value="deepocsort")  # Default to deepocsort (OC-SORT + appearance Re-ID) for best tracking
        self.video_fps = tk.DoubleVar(value=0.0)  # 0 = auto-detect from video, manual override if needed
        self.output_fps = tk.DoubleVar(value=0.0)  # 0 = same as input
        self.temporal_smoothing = tk.BooleanVar(value=True)  # Enable temporal smoothing
        self.process_every_nth = tk.IntVar(value=1)  # Process every Nth frame (BASIC: 1 = process ALL frames - no skipping!)
        self.yolo_resolution = tk.StringVar(value="full")  # YOLO processing resolution
        self.foot_based_tracking = tk.BooleanVar(value=True)  # Use foot-based tracking
        self.use_reid = tk.BooleanVar(value=True)  # Enable Re-ID for better ID persistence
        self.reid_similarity_threshold = tk.DoubleVar(value=0.55)  # Re-ID similarity threshold (default: 0.55 - adjustable 0.25-0.75)
        self.gallery_similarity_threshold = tk.DoubleVar(value=0.40)  # Gallery similarity threshold (default: 0.40 - adjustable 0.25-0.75, for cross-video player matching)
        self.osnet_variant = tk.StringVar(value="osnet_x1_0")  # OSNet variant: osnet_x1_0, osnet_ain_x1_0, osnet_ibn_x1_0, etc.
        # Fine-tuning parameters for occlusion handling and track consistency
        self.occlusion_recovery_seconds = tk.DoubleVar(value=3.0)  # Occlusion recovery time in seconds (default: 3.0s)
        self.occlusion_recovery_distance = tk.IntVar(value=250)  # Occlusion recovery distance in pixels (default: 250)
        self.reid_check_interval = tk.IntVar(value=30)  # Re-ID check interval in frames (default: 30)
        self.reid_confidence_threshold = tk.DoubleVar(value=0.75)  # Re-ID confidence threshold to skip checks (default: 0.75)
        self.use_boxmot_backend = tk.BooleanVar(value=True)  # Use BoxMOT optimized backends (ONNX/TensorRT) for faster inference
        self.use_gsi = tk.BooleanVar(value=False)  # Enable Gaussian Smoothed Interpolation for smoother tracks
        self.gsi_interval = tk.IntVar(value=20)  # Maximum frame gap to interpolate for GSI
        self.gsi_tau = tk.DoubleVar(value=10.0)  # Time constant for Gaussian smoothing in GSI
        
        # Advanced tracking features (based on academic research)
        self.use_harmonic_mean = tk.BooleanVar(value=True)  # Use Harmonic Mean for association (Deep HM-SORT)
        self.use_expansion_iou = tk.BooleanVar(value=True)  # Use Expansion IOU with motion prediction (Deep HM-SORT)
        self.enable_soccer_reid_training = tk.BooleanVar(value=False)  # Enable soccer-specific Re-ID training
        self.use_enhanced_kalman = tk.BooleanVar(value=True)  # Enhanced Kalman filtering
        self.use_ema_smoothing = tk.BooleanVar(value=True)  # EMA smoothing
        self.confidence_filtering = tk.BooleanVar(value=True)  # Confidence-based filtering
        self.adaptive_confidence = tk.BooleanVar(value=True)  # Adaptive confidence threshold
        self.use_optical_flow = tk.BooleanVar(value=False)  # Use optical flow for motion prediction
        self.enable_velocity_constraints = tk.BooleanVar(value=True)  # Enable velocity constraints to prevent impossible jumps
        
        # Advanced tracking options
        self.track_referees = tk.BooleanVar(value=False)  # Track referees and bench players
        self.max_players = tk.IntVar(value=12)  # Maximum field players (11 + coach)
        self.enable_substitutions = tk.BooleanVar(value=True)  # Enable substitution handling
        
        # Visualization options
        self.viz_style = tk.StringVar(value="box")  # "box", "circle", "both", "star", "diamond", "hexagon", "arrow" (legacy - kept for compatibility)
        self.viz_color_mode = tk.StringVar(value="team")  # "team", "single", "gradient"
        self.viz_team_colors = tk.BooleanVar(value=True)  # Use team colors if available
        
        # SEPARATE CONTROLS: Bounding boxes vs Circles at feet (user requested separation)
        self.show_bounding_boxes = tk.BooleanVar(value=True)  # Show bounding boxes around players
        self.show_circles_at_feet = tk.BooleanVar(value=True)  # Show team-colored circles at player feet
        
        # Ellipse visualization (for foot-based tracking)
        self.ellipse_width = tk.IntVar(value=20)  # Width of ellipse at feet (pixels)
        self.ellipse_height = tk.IntVar(value=12)  # Height of ellipse at feet (pixels)
        self.ellipse_outline_thickness = tk.IntVar(value=3)  # White border thickness around ellipse (pixels)
        
        # Enhanced feet marker visualization (high-quality graphics)
        self.feet_marker_style = tk.StringVar(value="circle")  # Style: "circle", "diamond", "star", "hexagon", "ring", "glow", "pulse"
        self.feet_marker_opacity = tk.IntVar(value=255)  # Opacity for feet markers (0-255, separate from box opacity)
        self.feet_marker_enable_glow = tk.BooleanVar(value=False)  # Enable glow effect
        self.feet_marker_glow_intensity = tk.IntVar(value=70)  # Glow intensity (0-100, default: 70 for better visibility)
        # ENHANCEMENT: Direction arrow and player trail
        self.show_direction_arrow = tk.BooleanVar(value=False)  # Show direction arrow under feet
        self.show_player_trail = tk.BooleanVar(value=False)  # Show player trail/breadcrumb
        self.direction_arrow_color = None  # Arrow color (None = white default)
        self.feet_marker_enable_shadow = tk.BooleanVar(value=False)  # Enable shadow effect
        self.feet_marker_shadow_offset = tk.IntVar(value=3)  # Shadow offset in pixels
        self.feet_marker_shadow_opacity = tk.IntVar(value=128)  # Shadow opacity (0-255)
        self.feet_marker_enable_gradient = tk.BooleanVar(value=False)  # Enable gradient fill
        self.feet_marker_enable_pulse = tk.BooleanVar(value=False)  # Enable pulse animation
        self.feet_marker_pulse_speed = tk.DoubleVar(value=2.0)  # Pulse animation speed (cycles per second)
        self.feet_marker_enable_particles = tk.BooleanVar(value=False)  # Enable particle effects
        self.feet_marker_particle_count = tk.IntVar(value=5)  # Number of particles
        self.feet_marker_vertical_offset = tk.IntVar(value=50)  # Vertical offset in pixels (negative = above feet, positive = below feet)
        self.show_ball_possession = tk.BooleanVar(value=True)  # Show triangle when player has ball
        self.box_shrink_factor = tk.DoubleVar(value=0.10)  # Box shrink factor (0.0 = no shrink, 0.20 = 20% shrink on each side)
        
        # Broadcast-level graphics settings
        self.trajectory_smoothness = tk.StringVar(value="bezier")  # "linear", "bezier", "spline"
        self.player_graphics_style = tk.StringVar(value="standard")  # "minimal", "standard", "broadcast"
        self.use_rounded_corners = tk.BooleanVar(value=True)  # Use rounded corners for bounding boxes
        self.use_gradient_fill = tk.BooleanVar(value=False)  # Use gradient fill for bounding boxes
        self.corner_radius = tk.IntVar(value=5)  # Corner radius for rounded rectangles
        self.show_jersey_badge = tk.BooleanVar(value=False)  # Show circular jersey number badge
        self.show_statistics = tk.BooleanVar(value=False)  # Show broadcast-style statistics overlay
        self.statistics_position = tk.StringVar(value="top_left")  # "top_left", "top_right", "bottom_left", "bottom_right"
        # Statistics panel size (for corner panels only - banners/bars use fixed sizes)
        self.statistics_panel_width = tk.IntVar(value=250)  # Panel width in pixels
        self.statistics_panel_height = tk.IntVar(value=150)  # Panel height in pixels
        # Statistics panel appearance
        self.statistics_bg_alpha = tk.DoubleVar(value=0.75)  # Background opacity (0.0 to 1.0)
        self.statistics_bg_color_rgb = tk.StringVar(value="0,0,0")  # Background color as "R,G,B" (black default)
        self.statistics_text_color_rgb = tk.StringVar(value="255,255,255")  # Text color as "R,G,B" (white default)
        self.statistics_title_color_rgb = tk.StringVar(value="255,255,0")  # Title color as "R,G,B" (yellow default)
        self.analytics_position = tk.StringVar(value="with_player")  # "with_player", "top_left", "top_right", "bottom_left", "bottom_right", "top_banner", "bottom_banner", "left_bar", "right_bar"
        # Analytics font and color customization
        self.analytics_font_scale = tk.DoubleVar(value=1.0)  # Analytics font size (default: 1.0 for better readability)
        self.analytics_font_thickness = tk.IntVar(value=2)  # Font thickness (1-5, default: 2 for better readability)
        self.analytics_font_face = tk.StringVar(value="FONT_HERSHEY_SIMPLEX")  # Analytics font face
        self.use_custom_analytics_color = tk.BooleanVar(value=True)  # Default to custom color for better contrast
        self.analytics_color_rgb = tk.StringVar(value="255,255,255")  # Analytics color as "R,G,B" (white default)
        self.analytics_title_color_rgb = tk.StringVar(value="255,255,0")  # Title color as "R,G,B" (yellow default)
        self.show_heat_map = tk.BooleanVar(value=False)  # Show player position heat map
        self.heat_map_alpha = tk.DoubleVar(value=0.4)  # Heat map opacity (0.0 to 1.0)
        self.heat_map_color_scheme = tk.StringVar(value="hot")  # "hot", "cool", "green"
        self.ball_graphics_style = tk.StringVar(value="standard")  # "standard", "broadcast"
        self.overlay_quality_preset = tk.StringVar(value="hd")  # "sd", "hd", "4k", "broadcast"
        
        # Box appearance customization
        self.box_thickness = tk.IntVar(value=2)  # Box border thickness in pixels (default: 2)
        self.use_custom_box_color = tk.BooleanVar(value=False)  # Use custom color instead of team colors
        self.box_color_rgb = tk.StringVar(value="0,255,0")  # Box color as "R,G,B" (green default)
        self.player_viz_alpha = tk.IntVar(value=255)  # Opacity for player boxes/ellipses (0-255, 255 = fully opaque)
        
        # Label color customization
        self.use_custom_label_color = tk.BooleanVar(value=False)  # Use custom color for labels instead of team colors
        self.label_color_rgb = tk.StringVar(value="255,255,255")  # Label color as "R,G,B" (white default)
        
        self.show_player_labels = tk.BooleanVar(value=True)  # Show player name/ID labels (can hide to reduce clutter)
        self.show_yolo_boxes = tk.BooleanVar(value=False)  # Show raw YOLO detection boxes (before tracking)
        self.label_font_scale = tk.DoubleVar(value=0.7)  # Label font size (default: 0.7, OpenCV scale typically 0.3-1.0)
        self.label_type = tk.StringVar(value="full_name")  # Label type: "full_name", "last_name", "jersey", "team", "custom"
        self.label_custom_text = tk.StringVar(value="Player")  # Custom text for all labels
        self.label_font_face = tk.StringVar(value="FONT_HERSHEY_SIMPLEX")  # Font face: "FONT_HERSHEY_SIMPLEX", "FONT_HERSHEY_PLAIN", "FONT_HERSHEY_DUPLEX", "FONT_HERSHEY_COMPLEX", "FONT_HERSHEY_TRIPLEX", "FONT_HERSHEY_COMPLEX_SMALL", "FONT_HERSHEY_SCRIPT_SIMPLEX", "FONT_HERSHEY_SCRIPT_COMPLEX"
        self.show_predicted_boxes = tk.BooleanVar(value=False)  # Show predicted boxes for lost tracks (DISABLED: False - no trailing dots)
        self.prediction_duration = tk.DoubleVar(value=1.5)  # Prediction duration in seconds (BASIC: 1.5s - longer = smoother)
        self.prediction_size = tk.IntVar(value=5)  # Size of predicted boxes/dots (pixels)
        self.prediction_color_r = tk.IntVar(value=255)  # Red component for prediction color
        self.prediction_color_g = tk.IntVar(value=255)  # Green component for prediction color
        self.prediction_color_b = tk.IntVar(value=0)  # Blue component for prediction color (yellow default)
        self.prediction_color_alpha = tk.IntVar(value=255)  # Alpha/opacity component (0-255, 255 = fully opaque)
        self.prediction_style = tk.StringVar(value="dot")  # Style: "dot", "box", "cross", "x", "arrow", "diamond"
        self.ball_min_radius = tk.IntVar(value=5)  # Minimum ball radius in pixels (default: 5)
        self.ball_max_radius = tk.IntVar(value=50)  # Maximum ball radius in pixels (default: 50)
        self.preserve_audio = tk.BooleanVar(value=True)  # Preserve audio from original video (default: True)
        
        self.processing = False
        self.process_thread = None
        
        # Initialize instance variables that may be accessed later
        self.last_output_file = None  # Store last output file path for CSV loading
        self.live_viewer_controls = None  # Live viewer controls window
        self.live_viewer_retry_count = 0  # Retry counter for live viewer
        self.live_viewer_max_retries = 20  # Max retries for live viewer
        self.live_viewer_start_time = None  # Start time for timeout tracking
        self.live_viewer_timeout = 30  # Timeout in seconds
        self._player_stats_window = None  # Player stats window
        self._player_stats_app = None  # Player stats app
        self._gallery_seeder_window = None  # Gallery seeder window
        self._video_splicer_window = None  # Video splicer window
        # Video splicer instance variables (initialized in create_video_splicer)
        self.video_path_var = None
        self.video_info_text = None
        self.split_mode = None
        self.time_frame = None
        self.chunk_duration_var = None
        self.size_frame = None
        self.chunk_size_var = None
        self.split_points_text = None
        self.resolution_var = None
        self.custom_res_frame = None
        self.custom_width_var = None
        self.custom_height_var = None
        self.fps_var = None
        self.custom_fps_frame = None
        self.custom_fps_var = None
        self.output_dir_var = None
        self.splicer_progress_var = None
        self.splicer_progress_bar = None
        self.splicer_status_text = None
        self.splicer_start_button = None
        self.splicer_stop_button = None
        self._splicer = None
        self._splicer_processing = False
        
        self.create_widgets()
        
        # Initialize quick wins features
        if QUICK_WINS_AVAILABLE:
            self.undo_manager = UndoManager()
            self.recent_projects = RecentProjectsManager()
            self.keyboard_shortcuts = KeyboardShortcuts(self.root)
            # Load auto-save preference
            auto_save_enabled = self._load_auto_save_preference()
            self.auto_save = AutoSaveManager(self.save_project, interval_seconds=300)
            self.auto_save.set_enabled(auto_save_enabled)
            self.progress_tracker = None  # Will be created when needed
            
            # Setup keyboard shortcuts
            self._setup_keyboard_shortcuts()
            
            # Setup menu bar
            self._create_menu_bar()
            
            # Start auto-save (it will respect the enabled state)
            self.auto_save.start()
            
            # Show "What's New" on first run
            self.root.after(1000, self._check_whats_new)
            
            # Add tooltips to key widgets
            self._add_tooltips()
        else:
            self.undo_manager = None
            self.recent_projects = None
            self.keyboard_shortcuts = None
            self.auto_save = None
        
        # Auto-load last project after GUI is ready
        self.root.after(500, self.auto_load_last_project)
        
    def create_widgets(self):
        # Main container with two columns: left for content, right for buttons
        # CRITICAL FIX: Reduced top padding from 10 to 2 to fix large spacing from title bar
        main_container = ttk.Frame(self.root, padding="2")
        main_container.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Create tabbed interface instead of scrollable frame
        # Title frame (outside tabs, always visible)
        title_frame = ttk.Frame(main_container)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        main_container.columnconfigure(0, weight=1)
        
        title_label = ttk.Label(title_frame, text="Soccer Video Analysis Tool", 
                               font=("Arial", 16, "bold"))
        title_label.pack(side=tk.LEFT, padx=(0, 20))
        
        # Current project name display
        project_name_frame = ttk.Frame(title_frame)
        project_name_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(project_name_frame, text="Project:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        self.project_name_label = ttk.Label(project_name_frame, textvariable=self.current_project_name, 
                                           font=("Arial", 10), foreground="blue")
        self.project_name_label.pack(side=tk.LEFT)
        
        # Create notebook for tabs
        self.main_notebook = ttk.Notebook(main_container)
        self.main_notebook.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        main_container.rowconfigure(1, weight=1)
        
        # CRITICAL FIX: Right column needs to span both title and notebook rows
        # Store row reference for right column positioning
        self.right_column_start_row = 0
        
        # Create tabs
        # Tab 1: General (File selection, basic options) - with scrollbar
        general_tab = ttk.Frame(self.main_notebook)
        self.main_notebook.add(general_tab, text="📁 General")
        
        # Create scrollable canvas for General tab
        general_canvas = tk.Canvas(general_tab, highlightthickness=0, bg="white", relief=tk.FLAT)
        general_scrollbar = ttk.Scrollbar(general_tab, orient="vertical", command=general_canvas.yview)
        general_canvas.configure(yscrollcommand=general_scrollbar.set)
        
        general_scrollbar.pack(side="right", fill="y")
        general_canvas.pack(side="left", fill="both", expand=True)
        
        # Create frame inside canvas for content
        general_content = ttk.Frame(general_canvas, padding="10")
        general_canvas_window = general_canvas.create_window((0, 0), window=general_content, anchor="nw")
        general_content.columnconfigure(1, weight=1)
        
        # Configure scrolling
        def configure_general_scroll(event=None):
            general_canvas.configure(scrollregion=general_canvas.bbox("all"))
            # Make canvas window fill width
            canvas_width = event.width if event else general_canvas.winfo_width()
            general_canvas.itemconfig(general_canvas_window, width=canvas_width)
        
        general_content.bind("<Configure>", configure_general_scroll)
        general_canvas.bind("<Configure>", configure_general_scroll)
        
        # Enable mousewheel scrolling
        def on_general_mousewheel(event):
            general_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_general_mousewheel(event):
            general_canvas.bind_all("<MouseWheel>", on_general_mousewheel)
        
        def unbind_general_mousewheel(event):
            general_canvas.unbind_all("<MouseWheel>")
        
        general_canvas.bind("<Enter>", bind_general_mousewheel)
        general_canvas.bind("<Leave>", unbind_general_mousewheel)
        
        # Use general_content instead of general_tab for all widgets
        general_tab = general_content
        
        # Tab 2: Analysis (Analysis options, ball settings, YOLO settings)
        analysis_tab = ttk.Frame(self.main_notebook, padding="10")
        self.main_notebook.add(analysis_tab, text="⚙️ Analysis")
        analysis_tab.columnconfigure(1, weight=1)
        
        # ========== ANALYSIS TAB CONTENT ==========
        analysis_row = 0
        
        # Ball Tracking Settings
        ball_frame = ttk.LabelFrame(analysis_tab, text="Ball Tracking Settings", padding="10")
        ball_frame.grid(row=analysis_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        analysis_row += 1
        
        ttk.Checkbutton(ball_frame, text="Track Ball (detection + CSV export)", 
                       variable=self.ball_tracking_enabled).grid(row=0, column=0, sticky=tk.W, pady=5)
        
        # Ball size detection range
        ball_size_frame = ttk.Frame(ball_frame)
        ball_size_frame.grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(ball_size_frame, text="Ball Size Range (pixels):").pack(side=tk.LEFT, padx=5)
        ball_min_spinbox = ttk.Spinbox(ball_size_frame, from_=3, to=20, increment=1,
                                      textvariable=self.ball_min_size, width=8)
        ball_min_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(ball_size_frame, text="to").pack(side=tk.LEFT, padx=5)
        ball_max_spinbox = ttk.Spinbox(ball_size_frame, from_=20, to=100, increment=5,
                                      textvariable=self.ball_max_size, width=8)
        ball_max_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(ball_size_frame, text="(min to max diameter for ball detection)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
        
        # Ball trail settings
        trail_frame = ttk.Frame(ball_frame)
        trail_frame.grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(trail_frame, text="Show Ball Trail (red lines overlay)", 
                       variable=self.show_ball_trail).pack(side=tk.LEFT, padx=5)
        ttk.Label(trail_frame, text="Length:").pack(side=tk.LEFT, padx=(20, 2))
        trail_length_spinbox = ttk.Spinbox(trail_frame, from_=5, to=100, increment=5,
                                          textvariable=self.ball_trail_length, width=6)
        trail_length_spinbox.pack(side=tk.LEFT, padx=2)
        ttk.Label(trail_frame, text="frames", foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
        
        # YOLO Detection Settings
        yolo_frame = ttk.LabelFrame(analysis_tab, text="YOLO Detection Settings", padding="10")
        yolo_frame.grid(row=analysis_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        analysis_row += 1
        
        # Confidence threshold
        conf_frame = ttk.Frame(yolo_frame)
        conf_frame.grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(conf_frame, text="Confidence Threshold:").pack(side=tk.LEFT, padx=5)
        conf_spinbox = ttk.Spinbox(conf_frame, from_=0.1, to=1.0, increment=0.05,
                                  textvariable=self.yolo_confidence, width=8, format="%.2f")
        conf_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(conf_frame, text="(0.1 = more detections, 1.0 = only very confident)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
        
        # IOU threshold
        iou_frame = ttk.Frame(yolo_frame)
        iou_frame.grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(iou_frame, text="IOU Threshold:").pack(side=tk.LEFT, padx=5)
        iou_spinbox = ttk.Spinbox(iou_frame, from_=0.1, to=1.0, increment=0.05,
                                 textvariable=self.yolo_iou_threshold, width=8, format="%.2f")
        iou_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(iou_frame, text="(Non-Maximum Suppression threshold)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
        
        # Batch size
        batch_frame = ttk.Frame(yolo_frame)
        batch_frame.grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Label(batch_frame, text="Batch Size:").pack(side=tk.LEFT, padx=5)
        batch_spinbox = ttk.Spinbox(batch_frame, from_=1, to=32, 
                                   textvariable=self.batch_size, width=8)
        batch_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(batch_frame, text="(higher = faster but uses more memory)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
        
        # YOLO Resolution
        yolo_res_frame = ttk.Frame(yolo_frame)
        yolo_res_frame.grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Label(yolo_res_frame, text="YOLO Resolution:").pack(side=tk.LEFT, padx=5)
        yolo_res_combo = ttk.Combobox(yolo_res_frame, textvariable=self.yolo_resolution,
                                     values=["640", "720", "1080", "full"], width=10, state="readonly")
        yolo_res_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(yolo_res_frame, text="(lower = faster, higher = more accurate)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
        
        # Player Gallery Matching Settings
        gallery_frame = ttk.LabelFrame(analysis_tab, text="Player Gallery Matching", padding="10")
        gallery_frame.grid(row=analysis_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        analysis_row += 1
        
        gallery_frame.columnconfigure(0, weight=0, minsize=200)  # Label column
        gallery_frame.columnconfigure(1, weight=0, minsize=100)  # Control column
        gallery_frame.columnconfigure(2, weight=1, minsize=300)   # Help text column
        
        # Gallery Similarity Threshold
        ttk.Label(gallery_frame, text="Gallery Similarity Threshold:", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        gallery_thresh_spinbox = ttk.Spinbox(gallery_frame, from_=0.20, to=0.75, increment=0.05,
                                             textvariable=self.gallery_similarity_threshold, width=8, format="%.2f",
                                             command=lambda: self._validate_gallery_threshold())
        gallery_thresh_spinbox.grid(row=0, column=1, padx=5, pady=5)
        gallery_thresh_spinbox.bind('<KeyRelease>', lambda e: self._validate_gallery_threshold())
        ttk.Label(gallery_frame, text="(0.20-0.75, for matching players across videos, default: 0.40)", wraplength=350).grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Processing Settings
        process_frame = ttk.LabelFrame(analysis_tab, text="Processing Settings", padding="10")
        process_frame.grid(row=analysis_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        analysis_row += 1
        
        ttk.Checkbutton(process_frame, text="Apply Dewarping (Fix Fisheye Distortion)", 
                       variable=self.dewarp_enabled).grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(process_frame, text="Remove Net (essential for safety net recordings)", 
                       variable=self.remove_net_enabled).grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(process_frame, text="Track Players (YOLO detection + tracking)",
                       variable=self.player_tracking_enabled).grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(process_frame, text="Export CSV (tracking data)",
                       variable=self.csv_export_enabled).grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(process_frame, text="Use Imperial Units (feet & mph) - American units",
                       variable=self.use_imperial_units).grid(row=4, column=0, sticky=tk.W, pady=5)
        
        # Tab 3: Visualization (All visualization controls) - with scrollbar
        viz_tab_container = ttk.Frame(self.main_notebook)
        self.main_notebook.add(viz_tab_container, text="🎨 Visualization")
        
        # Create scrollable canvas for Visualization tab
        viz_canvas = tk.Canvas(viz_tab_container, highlightthickness=0, bg="white", relief=tk.FLAT)
        viz_scrollbar = ttk.Scrollbar(viz_tab_container, orient="vertical", command=viz_canvas.yview)
        viz_canvas.configure(yscrollcommand=viz_scrollbar.set)
        
        viz_scrollbar.pack(side="right", fill="y")
        viz_canvas.pack(side="left", fill="both", expand=True)
        
        # Create frame inside canvas for content
        viz_tab = ttk.Frame(viz_canvas, padding="10")
        viz_canvas_window = viz_canvas.create_window((0, 0), window=viz_tab, anchor="nw")
        viz_tab.columnconfigure(1, weight=1)
        
        # Configure scrolling
        def configure_viz_scroll(event=None):
            viz_canvas.configure(scrollregion=viz_canvas.bbox("all"))
            # Make canvas window fill width
            canvas_width = event.width if event else viz_canvas.winfo_width()
            viz_canvas.itemconfig(viz_canvas_window, width=canvas_width)
        
        viz_tab.bind("<Configure>", configure_viz_scroll)
        viz_canvas.bind("<Configure>", configure_viz_scroll)
        
        # Enable mousewheel scrolling
        def on_viz_mousewheel(event):
            viz_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_viz_mousewheel(event):
            viz_canvas.bind_all("<MouseWheel>", on_viz_mousewheel)
        
        def unbind_viz_mousewheel(event):
            viz_canvas.unbind_all("<MouseWheel>")
        
        viz_canvas.bind("<Enter>", bind_viz_mousewheel)
        viz_canvas.bind("<Leave>", unbind_viz_mousewheel)
        
        # Tab 4: Tracking (Tracking stability settings) - with scrollbar
        tracking_tab_container = ttk.Frame(self.main_notebook)
        self.main_notebook.add(tracking_tab_container, text="🎯 Tracking")
        
        # Create scrollable canvas for Tracking tab
        tracking_canvas = tk.Canvas(tracking_tab_container, highlightthickness=0, bg="white", relief=tk.FLAT)
        tracking_scrollbar = ttk.Scrollbar(tracking_tab_container, orient="vertical", command=tracking_canvas.yview)
        tracking_canvas.configure(yscrollcommand=tracking_scrollbar.set)
        
        tracking_scrollbar.pack(side="right", fill="y")
        tracking_canvas.pack(side="left", fill="both", expand=True)
        
        # Create frame inside canvas for content
        tracking_tab = ttk.Frame(tracking_canvas, padding="10")
        tracking_canvas_window = tracking_canvas.create_window((0, 0), window=tracking_tab, anchor="nw")
        tracking_tab.columnconfigure(1, weight=1)
        
        # Configure scrolling
        def configure_tracking_scroll(event=None):
            tracking_canvas.configure(scrollregion=tracking_canvas.bbox("all"))
            # Make canvas window fill width
            canvas_width = event.width if event else tracking_canvas.winfo_width()
            tracking_canvas.itemconfig(tracking_canvas_window, width=canvas_width)
        
        tracking_tab.bind("<Configure>", configure_tracking_scroll)
        tracking_canvas.bind("<Configure>", configure_tracking_scroll)
        
        # Enable mousewheel scrolling
        def on_tracking_mousewheel(event):
            tracking_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_tracking_mousewheel(event):
            tracking_canvas.bind_all("<MouseWheel>", on_tracking_mousewheel)
        
        def unbind_tracking_mousewheel(event):
            tracking_canvas.unbind_all("<MouseWheel>")
        
        tracking_canvas.bind("<Enter>", bind_tracking_mousewheel)
        tracking_canvas.bind("<Leave>", unbind_tracking_mousewheel)
        
        # Tab 5: Advanced (Watch-only, focus players, overlay system) - with scrollbar
        advanced_tab_container = ttk.Frame(self.main_notebook)
        self.main_notebook.add(advanced_tab_container, text="🔧 Advanced")
        
        # Create scrollable canvas for Advanced tab
        advanced_canvas = tk.Canvas(advanced_tab_container, highlightthickness=0, bg="white", relief=tk.FLAT)
        advanced_scrollbar = ttk.Scrollbar(advanced_tab_container, orient="vertical", command=advanced_canvas.yview)
        advanced_canvas.configure(yscrollcommand=advanced_scrollbar.set)
        
        advanced_scrollbar.pack(side="right", fill="y")
        advanced_canvas.pack(side="left", fill="both", expand=True)
        
        # Create frame inside canvas for content
        advanced_tab = ttk.Frame(advanced_canvas, padding="10")
        advanced_canvas_window = advanced_canvas.create_window((0, 0), window=advanced_tab, anchor="nw")
        advanced_tab.columnconfigure(1, weight=1)
        
        # Configure scrolling
        def configure_advanced_scroll(event=None):
            advanced_canvas.configure(scrollregion=advanced_canvas.bbox("all"))
            # Make canvas window fill width
            canvas_width = event.width if event else advanced_canvas.winfo_width()
            advanced_canvas.itemconfig(advanced_canvas_window, width=canvas_width)
        
        advanced_tab.bind("<Configure>", configure_advanced_scroll)
        advanced_canvas.bind("<Configure>", configure_advanced_scroll)
        
        # Enable mousewheel scrolling
        def on_advanced_mousewheel(event):
            advanced_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_advanced_mousewheel(event):
            advanced_canvas.bind_all("<MouseWheel>", on_advanced_mousewheel)
        
        def unbind_advanced_mousewheel(event):
            advanced_canvas.unbind_all("<MouseWheel>")
        
        advanced_canvas.bind("<Enter>", bind_advanced_mousewheel)
        advanced_canvas.bind("<Leave>", unbind_advanced_mousewheel)
        
        # Tab 6: Event Detection (Automated event detection from CSV)
        event_tab_container = ttk.Frame(self.main_notebook)
        self.main_notebook.add(event_tab_container, text="📊 Event Detection")
        
        # Create scrollable canvas for Event Detection tab
        event_canvas = tk.Canvas(event_tab_container, highlightthickness=0, bg="white", relief=tk.FLAT)
        event_scrollbar = ttk.Scrollbar(event_tab_container, orient="vertical", command=event_canvas.yview)
        event_canvas.configure(yscrollcommand=event_scrollbar.set)
        
        event_scrollbar.pack(side="right", fill="y")
        event_canvas.pack(side="left", fill="both", expand=True)
        
        # Create frame inside canvas for content
        event_tab = ttk.Frame(event_canvas, padding="10")
        event_canvas_window = event_canvas.create_window((0, 0), window=event_tab, anchor="nw")
        event_tab.columnconfigure(1, weight=1)
        
        # Configure scrolling
        def configure_event_scroll(event=None):
            event_canvas.configure(scrollregion=event_canvas.bbox("all"))
            canvas_width = event.width if event else event_canvas.winfo_width()
            event_canvas.itemconfig(event_canvas_window, width=canvas_width)
        
        event_tab.bind("<Configure>", configure_event_scroll)
        event_canvas.bind("<Configure>", configure_event_scroll)
        
        # Enable mousewheel scrolling
        def on_event_mousewheel(event):
            event_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_event_mousewheel(event):
            event_canvas.bind_all("<MouseWheel>", on_event_mousewheel)
        
        def unbind_event_mousewheel(event):
            event_canvas.unbind_all("<MouseWheel>")
        
        event_canvas.bind("<Enter>", bind_event_mousewheel)
        event_canvas.bind("<Leave>", unbind_event_mousewheel)
        
        # ========== EVENT DETECTION TAB CONTENT ==========
        self._create_event_detection_tab(event_tab)
        
        # ========== ADVANCED TAB CONTENT ==========
        advanced_row = 0
        
        # Watch-Only Mode
        watch_frame = ttk.LabelFrame(advanced_tab, text="Watch-Only Mode", padding="10")
        watch_frame.grid(row=advanced_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        advanced_row += 1
        
        ttk.Checkbutton(watch_frame, text="Watch-Only Mode (learn from video, no output saved)",
                       variable=self.watch_only,
                       command=self._update_focus_players_ui).grid(row=0, column=0, sticky=tk.W, pady=5)
        watch_help_label = ttk.Label(watch_frame, 
                                     text="Faster processing - learns player features & team colors, saves to player_gallery.json & team_color_config.json",
                                     foreground="dark gray", font=("Arial", 8), wraplength=500)
        watch_help_label.grid(row=1, column=0, sticky=tk.W, padx=(20, 0), pady=(0, 5))
        ttk.Checkbutton(watch_frame, text="Show Live Viewer (watch learning in real-time)",
                       variable=self.show_live_viewer).grid(row=2, column=0, sticky=tk.W, padx=(20, 0), pady=5)
        
        # Focus Players (only shown if watch-only is enabled)
        self.focus_players_frame = ttk.LabelFrame(advanced_tab, text="Focus Players (Watch-Only)", padding="10")
        # Will be shown/hidden based on watch_only state
        
        # Overlay System
        overlay_frame = ttk.LabelFrame(advanced_tab, text="Overlay System (Base Video + Overlays)", padding="10")
        overlay_frame.grid(row=advanced_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        advanced_row += 1
        
        # Base video option
        base_video_frame = ttk.Frame(overlay_frame)
        base_video_frame.grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(base_video_frame, text="Save Base Video (clean video without overlays)",
                       variable=self.save_base_video).pack(side=tk.LEFT)
        base_video_help = ttk.Label(base_video_frame, 
                                    text="(Usually not needed - you already have the original video)",
                                    font=("Arial", 8), foreground="gray")
        base_video_help.pack(side=tk.LEFT, padx=(10, 0))
        
        ttk.Checkbutton(overlay_frame, text="Export Overlay Metadata (for separate rendering)",
                       variable=self.export_overlay_metadata).grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(overlay_frame, text="Enable Video Encoding (save analyzed video with overlays)",
                       variable=self.enable_video_encoding).grid(row=2, column=0, sticky=tk.W, pady=5)
        
        # Overlay quality and render scale
        overlay_quality_label = ttk.Label(overlay_frame, text="Overlay Quality & Render Settings:",
                                         font=("Arial", 9, "bold"))
        overlay_quality_label.grid(row=3, column=0, sticky=tk.W, pady=(10, 5))
        
        # Quality setting
        quality_frame = ttk.Frame(overlay_frame)
        quality_frame.grid(row=4, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        ttk.Label(quality_frame, text="Quality:", width=12, anchor=tk.W).pack(side=tk.LEFT)
        quality_combo = ttk.Combobox(quality_frame, textvariable=self.overlay_quality,
                                    values=["sd", "hd", "4k"], width=8, state="readonly")
        quality_combo.pack(side=tk.LEFT, padx=(0, 15))
        
        # Render scale setting
        scale_frame = ttk.Frame(overlay_frame)
        scale_frame.grid(row=5, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        ttk.Label(scale_frame, text="Render Scale:", width=12, anchor=tk.W).pack(side=tk.LEFT)
        render_scale_spin = ttk.Spinbox(scale_frame, from_=0.5, to=4.0, increment=0.1,
                                       textvariable=self.render_scale, width=8)
        render_scale_spin.pack(side=tk.LEFT, padx=(0, 8))
        scale_help = ttk.Label(scale_frame, 
                              text="(1.0 = original, 2.0 = 2x resolution for HD)",
                              font=("Arial", 8), foreground="gray")
        scale_help.pack(side=tk.LEFT)
        
        # Video Game Quality Graphics Settings
        quality_graphics_label = ttk.Label(overlay_frame, text="Video Game Quality Graphics:",
                                          font=("Arial", 9, "bold"))
        quality_graphics_label.grid(row=6, column=0, sticky=tk.W, pady=(15, 5))
        
        # Advanced blending modes
        ttk.Checkbutton(overlay_frame, text="Enable Advanced Blending Modes (glow, screen, additive effects)",
                       variable=self.enable_advanced_blending, command=self.update_preview).grid(row=7, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        blending_help = ttk.Label(overlay_frame,
                                 text="(additive glow, screen blending, overlay modes for professional effects)",
                                 font=("Arial", 8), foreground="gray")
        blending_help.grid(row=8, column=0, sticky=tk.W, padx=(40, 0), pady=(0, 5))
        
        # Professional text rendering
        ttk.Checkbutton(overlay_frame, text="Use Professional Text Rendering (PIL-based with outlines & shadows)",
                       variable=self.use_professional_text, command=self.update_preview).grid(row=9, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        text_help = ttk.Label(overlay_frame,
                             text="(high-quality fonts, smooth edges, drop shadows - requires Pillow)",
                             font=("Arial", 8), foreground="gray")
        text_help.grid(row=10, column=0, sticky=tk.W, padx=(40, 0), pady=(0, 5))
        
        # Motion blur settings
        motion_blur_frame = ttk.Frame(overlay_frame)
        motion_blur_frame.grid(row=11, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        ttk.Checkbutton(motion_blur_frame, text="Enable Motion Blur",
                       variable=self.enable_motion_blur, command=self.update_preview).pack(side=tk.LEFT)
        ttk.Label(motion_blur_frame, text="Intensity:").pack(side=tk.LEFT, padx=(15, 5))
        motion_blur_spin = ttk.Spinbox(motion_blur_frame, from_=0.0, to=2.0, increment=0.1,
                                      textvariable=self.motion_blur_amount, width=6, format="%.1f", command=self.update_preview)
        motion_blur_spin.pack(side=tk.LEFT)
        motion_blur_spin.bind('<KeyRelease>', lambda e: self.update_preview())
        motion_blur_spin.bind('<ButtonRelease>', lambda e: self.update_preview())
        motion_blur_help = ttk.Label(overlay_frame,
                                    text="(blur trails for fast-moving objects based on velocity - adds ~10-20% overhead)",
                                    font=("Arial", 8), foreground="gray")
        motion_blur_help.grid(row=12, column=0, sticky=tk.W, padx=(40, 0), pady=(0, 5))
        
        # Enhanced graphics features
        enhanced_label = ttk.Label(overlay_frame, text="Enhanced Graphics Features:",
                                 font=("Arial", 9, "bold"))
        enhanced_label.grid(row=13, column=0, sticky=tk.W, pady=(15, 5))
        
        # Quality preset
        quality_frame = ttk.Frame(overlay_frame)
        quality_frame.grid(row=14, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        ttk.Label(quality_frame, text="Quality Preset:").pack(side=tk.LEFT, padx=(0, 5))
        quality_combo = ttk.Combobox(quality_frame, textvariable=self.graphics_quality_preset,
                                    values=("sd", "hd", "4k"), width=8, state="readonly")
        quality_combo.pack(side=tk.LEFT)
        quality_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview())
        
        # Text enhancements
        ttk.Checkbutton(overlay_frame, text="Enable Text Gradient (color gradient in text)",
                       variable=self.enable_text_gradient, command=self.update_preview).grid(row=15, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        ttk.Checkbutton(overlay_frame, text="Enable Text Glow (glowing text effect)",
                       variable=self.enable_text_glow, command=self.update_preview).grid(row=16, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        ttk.Checkbutton(overlay_frame, text="Enable Text Pulse (pulsing text animation)",
                       variable=self.enable_text_pulse, command=self.update_preview).grid(row=17, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        
        # Glow enhancements
        ttk.Checkbutton(overlay_frame, text="Enable Pulsing Glow (animated glow effects)",
                       variable=self.enable_glow_pulse, command=self.update_preview).grid(row=18, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        ttk.Checkbutton(overlay_frame, text="Enable Color-Shifting Glow (rainbow glow effects)",
                       variable=self.enable_color_shift, command=self.update_preview).grid(row=19, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        
        # Box/ellipse enhancements
        ttk.Checkbutton(overlay_frame, text="Enable Gradient Boxes (gradient-filled bounding boxes)",
                       variable=self.enable_gradient_boxes, command=self.update_preview).grid(row=20, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        ttk.Checkbutton(overlay_frame, text="Enable Particle Trails (motion trail particles)",
                       variable=self.enable_particle_trails, command=self.update_preview).grid(row=21, column=0, sticky=tk.W, pady=5, padx=(20, 0))
        
        enhanced_help = ttk.Label(overlay_frame,
                                 text="(Advanced visual effects for professional broadcast-quality graphics)",
                                 font=("Arial", 8), foreground="gray")
        enhanced_help.grid(row=22, column=0, sticky=tk.W, padx=(40, 0), pady=(0, 5))
        
        # Store reference for later updates
        self.scrollable_frame = general_tab  # For backward compatibility
        
        # ========== GENERAL TAB ==========
        main_frame = general_tab
        row = 0
        
        # Input file selection
        ttk.Label(main_frame, text="Input Video:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.input_file, width=50).grid(
            row=row, column=1, sticky="ew", padx=5, pady=5)
        self.input_file_button = ttk.Button(main_frame, text="Browse", command=self.browse_input_file)
        self.input_file_button.grid(row=row, column=2, padx=5, pady=5)
        row += 1
        
        # Output file selection
        ttk.Label(main_frame, text="Output Video:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.output_file, width=50).grid(
            row=row, column=1, sticky="ew", padx=5, pady=5)
        self.output_file_button = ttk.Button(main_frame, text="Browse", command=self.browse_output_file)
        self.output_file_button.grid(row=row, column=2, padx=5, pady=5)
        row += 1
        
        # Video Type (Practice vs Game)
        video_type_frame = ttk.Frame(main_frame)
        video_type_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5)
        row += 1
        ttk.Label(video_type_frame, text="Video Type:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        video_type_combo = ttk.Combobox(video_type_frame, textvariable=self.video_type, 
                                        values=["practice", "game"], state="readonly", width=12)
        video_type_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(video_type_frame, text="(Practice: flexible team switches | Game: strict uniform validation)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=5)
        
        # Anchor File Selection (Optional)
        anchor_frame = ttk.Frame(main_frame)
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
        
        # Preset Modes
        preset_frame = ttk.LabelFrame(main_frame, text="⚡ Quick Presets", padding="10")
        preset_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        row += 1
        preset_frame.columnconfigure(0, weight=1)
        preset_frame.columnconfigure(1, weight=1)
        
        # Performance Mode Button
        perf_button = ttk.Button(preset_frame, text="🚀 Performance Mode", 
                                command=self.apply_performance_mode, width=25)
        perf_button.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W+tk.E)
        perf_label = ttk.Label(preset_frame, 
                              text="Optimized for speed (2-3x faster)\n• Process every 2nd frame\n• 720p YOLO resolution\n• Larger batch size\n• Disabled foot tracking",
                              font=("Arial", 8), foreground="darkgreen", justify=tk.LEFT)
        perf_label.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # High Quality Mode Button
        quality_button = ttk.Button(preset_frame, text="✨ High Quality Mode", 
                                   command=self.apply_high_quality_mode, width=25)
        quality_button.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W+tk.E)
        quality_label = ttk.Label(preset_frame, 
                                 text="Maximum accuracy & quality\n• Process all frames\n• Full/1080p resolution\n• Enhanced smoothing\n• Foot-based tracking",
                                 font=("Arial", 8), foreground="darkblue", justify=tk.LEFT)
        quality_label.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Separator
        ttk.Separator(main_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=15)
        row += 1
        
        # Options frame
        options_label = ttk.Label(main_frame, text="Analysis Options:", 
                                 font=("Arial", 12, "bold"))
        options_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        row += 1
        
        # Note: Analysis options (dewarping, net removal, ball/player tracking, CSV export, units) 
        #       moved to Analysis tab
        # Note: Overlay system moved to Advanced tab
        # Note: Watch-only mode moved to Advanced tab
        live_viewer_help_label = ttk.Label(main_frame, 
                                          text="   Displays video with player tracking while learning (press 'q' to close)",
                                          foreground="dark gray", font=("Arial", 8), wraplength=400)
        live_viewer_help_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=(30, 0), pady=(0, 5))
        row += 1
        
        # Focus Players mode (watch-only)
        focus_frame = ttk.Frame(main_frame)
        focus_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=(30, 0), pady=(0, 3))
        row += 1
        ttk.Checkbutton(focus_frame, text="Focus on Specific Player (faster learning)",
                       variable=self.focus_players_enabled,
                       command=self._update_focus_players_ui).pack(side=tk.LEFT)
        
        # Player selection dropdown (initially hidden)
        self.focus_players_frame = ttk.Frame(main_frame)
        self.focus_players_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=(50, 0), pady=(0, 5))
        row += 1
        
        ttk.Label(self.focus_players_frame, text="Select player to focus on:", font=("Arial", 8)).pack(anchor=tk.W, pady=(0, 5))
        
        # Dropdown (Combobox) for single player selection
        self.focused_player_var = tk.StringVar()
        self.focus_player_combo = ttk.Combobox(self.focus_players_frame, 
                                               textvariable=self.focused_player_var,
                                               width=30, state="readonly",
                                               font=("Arial", 9))
        self.focus_player_combo.pack(anchor=tk.W, fill=tk.X, pady=(0, 5))
        # Update focused_player when selection changes
        self.focus_player_combo.bind('<<ComboboxSelected>>', lambda e: self._update_focused_player())
        
        # Button to load/refresh players
        ttk.Button(self.focus_players_frame, text="Load Active Players", 
                  command=self._load_active_players_for_focus, width=20).pack(anchor=tk.W, pady=(5, 0))
        
        # Initially hide focus players UI
        self._update_focus_players_ui()
        
        focus_help_label = ttk.Label(main_frame, 
                                    text="   Only learns from selected player (5-10x faster). Still detects all players.",
                                    foreground="dark gray", font=("Arial", 8), wraplength=400)
        focus_help_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=(30, 0), pady=(0, 5))
        row += 1
        
        # Batch processing checkbox
        batch_focus_frame = ttk.Frame(main_frame)
        batch_focus_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=(30, 0), pady=(5, 3))
        row += 1
        ttk.Checkbutton(batch_focus_frame, text="Focus analyze each player on active roster for selected video",
                       variable=self.batch_focus_analyze,
                       command=self._update_batch_focus_ui).pack(side=tk.LEFT)
        
        batch_focus_help_label = ttk.Label(main_frame, 
                                          text="   Automatically runs analysis for each active player (one at a time).",
                                          foreground="dark gray", font=("Arial", 8), wraplength=400)
        batch_focus_help_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, padx=(30, 0), pady=(0, 5))
        row += 1
        
        # Preserve Audio checkbox - moved to correct position after focus_help_label
        ttk.Checkbutton(main_frame, text="Preserve Audio (copy audio from original video)",
                       variable=self.preserve_audio).grid(row=row, column=0, columnspan=3,
                                                         sticky=tk.W, pady=5)
        row += 1
        
        # Buffer size
        buffer_frame = ttk.Frame(main_frame)
        buffer_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=10, padx=(20, 0))
        row += 1
        ttk.Label(buffer_frame, text="Ball Trail Length:", font=("Arial", 9), width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        buffer_spinbox = ttk.Spinbox(buffer_frame, from_=16, to=128, 
                                     textvariable=self.buffer_size, width=10)
        buffer_spinbox.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(buffer_frame, text="(frames - ball trail history length)",
                 foreground="gray", font=("Arial", 8), wraplength=300).pack(side=tk.LEFT)
        
        # Show ball trail option (only visible if ball tracking is enabled)
        trail_frame = ttk.Frame(main_frame)
        trail_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5, padx=(20, 0))
        row += 1
        ttk.Checkbutton(trail_frame, text="Show Ball Trail (red lines overlay)", 
                       variable=self.show_ball_trail).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(trail_frame, text="(only if Track Ball is enabled)", 
                 foreground="gray", font=("Arial", 8), wraplength=200).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(trail_frame, text="Note: Trail is rendered into video (not toggleable during playback)", 
                 foreground="orange", font=("Arial", 7), wraplength=300).pack(side=tk.LEFT)
        
        # Trail length and buffer controls - use vertical layout for better readability
        trail_settings_frame = ttk.Frame(main_frame)
        trail_settings_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5, padx=(20, 0))
        row += 1
        
        # Trail Length row
        trail_length_row = ttk.Frame(trail_settings_frame)
        trail_length_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(trail_length_row, text="Trail Length (points):", font=("Arial", 9), width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        trail_length_spinbox = ttk.Spinbox(trail_length_row, from_=5, to=100, increment=5,
                                          textvariable=self.trail_length, width=10)
        trail_length_spinbox.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(trail_length_row, text="(shorter = less visual clutter, default: 20)",
                 foreground="gray", font=("Arial", 8), wraplength=300).pack(side=tk.LEFT)

        # Trail Buffer row
        trail_buffer_row = ttk.Frame(trail_settings_frame)
        trail_buffer_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(trail_buffer_row, text="Trail Buffer (frames):", font=("Arial", 9), width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        trail_buffer_spinbox = ttk.Spinbox(trail_buffer_row, from_=10, to=128, increment=5,
                                          textvariable=self.trail_buffer, width=10)
        trail_buffer_spinbox.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(trail_buffer_row, text="(max trail history, default: 20)",
                 foreground="gray", font=("Arial", 8), wraplength=300).pack(side=tk.LEFT)

        # Ball detection size controls - CRITICAL FIX: Separate rows to avoid conflict
        # Ball Min Radius
        ball_min_frame = ttk.Frame(main_frame)
        ball_min_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5, padx=(20, 0))
        row += 1
        ttk.Label(ball_min_frame, text="Ball Min Radius (pixels):", font=("Arial", 9), width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        ball_min_spinbox = ttk.Spinbox(ball_min_frame, from_=3, to=20, increment=1,
                                       textvariable=self.ball_min_radius, width=10)
        ball_min_spinbox.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(ball_min_frame, text="(minimum ball size to detect, default: 5)",
                 foreground="gray", font=("Arial", 8), wraplength=300).pack(side=tk.LEFT)

        # Ball Max Radius
        ball_max_frame = ttk.Frame(main_frame)
        ball_max_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5, padx=(20, 0))
        row += 1
        ttk.Label(ball_max_frame, text="Ball Max Radius (pixels):", font=("Arial", 9), width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        ball_max_spinbox = ttk.Spinbox(ball_max_frame, from_=20, to=100, increment=5,
                                       textvariable=self.ball_max_radius, width=10)
        ball_max_spinbox.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(ball_max_frame, text="(maximum ball size to detect, default: 50)",
                 foreground="gray", font=("Arial", 8), wraplength=300).pack(side=tk.LEFT)
        
        # Batch size (for GPU optimization) - always show, will be enabled if optimized available
        batch_frame = ttk.Frame(main_frame)
        batch_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5)
        row += 1
        ttk.Label(batch_frame, text="YOLO Batch Size:").pack(side=tk.LEFT, padx=5)
        batch_spinbox = ttk.Spinbox(batch_frame, from_=1, to=32, 
                                  textvariable=self.batch_size, width=10)
        batch_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(batch_frame, text="(higher = more GPU usage)").pack(side=tk.LEFT, padx=5)
        
        # YOLO streaming mode option
        streaming_checkbox = ttk.Checkbutton(batch_frame, text="YOLO Streaming Mode", 
                                            variable=self.use_yolo_streaming)
        streaming_checkbox.pack(side=tk.LEFT, padx=(20, 5))
        ttk.Label(batch_frame, text="(memory-efficient, primarily for direct video paths)").pack(side=tk.LEFT, padx=5)
        
        # Visualization style options (only shown if player tracking is enabled)
        # ========== VISUALIZATION TAB ==========
        viz_frame = ttk.LabelFrame(viz_tab, text="Player Visualization Style", padding="10")
        viz_frame.grid(row=0, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        viz_tab.columnconfigure(0, weight=1)
        
        # Configure viz_frame columns for proper spacing
        # INCREASED COLUMN WIDTHS: Better spacing for RGB controls and labels
        viz_frame.columnconfigure(0, weight=0, minsize=220)  # Label column - increased from 200
        viz_frame.columnconfigure(1, weight=0, minsize=120)  # Control column - increased from 100
        viz_frame.columnconfigure(2, weight=1, minsize=400)   # Help text/RGB column - increased from 300 for better RGB control visibility
        
        # SEPARATE CONTROLS: Bounding boxes and circles at feet (user requested)
        ttk.Label(viz_frame, text="Player Visualization:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        viz_control_frame = ttk.Frame(viz_frame)
        viz_control_frame.grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Show bounding boxes checkbox
        show_boxes_check = ttk.Checkbutton(viz_control_frame, text="✓ Show Bounding Boxes",
                                          variable=self.show_bounding_boxes, command=self.update_preview)
        show_boxes_check.pack(side=tk.LEFT, padx=5)
        
        # Show circles at feet checkbox  
        show_circles_check = ttk.Checkbutton(viz_control_frame, text="✓ Show Team-Colored Circles at Feet",
                                            variable=self.show_circles_at_feet, command=self.update_preview)
        show_circles_check.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(viz_frame, text="(Circles always use team colors, boxes use custom color if enabled)", 
                 foreground="gray", font=("Arial", 7)).grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        
        # Color mode
        ttk.Label(viz_frame, text="Color Mode:", font=("Arial", 9)).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        color_frame = ttk.Frame(viz_frame)
        color_frame.grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Radiobutton(color_frame, text="Team Colors", variable=self.viz_color_mode, value="team",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(color_frame, text="Single Color", variable=self.viz_color_mode, value="single",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(color_frame, text="Gradient (by ID)", variable=self.viz_color_mode, value="gradient",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(viz_frame, text="(Team colors require Team Color Helper to be configured)", 
                 foreground="gray", font=("Arial", 7)).grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        
        # Legacy visualization style removed - users should use the checkboxes above instead
        
        # Ellipse size controls (for foot-based tracking)
        ttk.Label(viz_frame, text="Ellipse Width (pixels):", font=("Arial", 9)).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        ellipse_width_spinbox = ttk.Spinbox(viz_frame, from_=10, to=50, increment=2,
                                            textvariable=self.ellipse_width, width=8, command=self.update_preview)
        ellipse_width_spinbox.grid(row=4, column=1, padx=5, pady=5)
        # Bind to value changes for real-time updates
        ellipse_width_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        ellipse_width_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(width of ellipse at feet, default: 20)", wraplength=280).grid(row=4, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(viz_frame, text="Ellipse Height (pixels):", font=("Arial", 9)).grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        ellipse_height_spinbox = ttk.Spinbox(viz_frame, from_=6, to=30, increment=2,
                                             textvariable=self.ellipse_height, width=8, command=self.update_preview)
        ellipse_height_spinbox.grid(row=5, column=1, padx=5, pady=5)
        # Bind to value changes for real-time updates
        ellipse_height_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        ellipse_height_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(height of ellipse at feet, default: 12)", wraplength=280).grid(row=5, column=2, sticky=tk.W, padx=5)
        
        # Ellipse Outline Thickness (white border)
        ttk.Label(viz_frame, text="Ellipse Border Thickness (pixels):", font=("Arial", 9)).grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        ellipse_outline_spinbox = ttk.Spinbox(viz_frame, from_=0, to=10, increment=1,
                                             textvariable=self.ellipse_outline_thickness, width=8, command=self.update_preview)
        ellipse_outline_spinbox.grid(row=6, column=1, padx=5, pady=5)
        ellipse_outline_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        ellipse_outline_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(white border thickness around ellipse, default: 3)", wraplength=280).grid(row=6, column=2, sticky=tk.W, padx=5)
        
        # ========== ENHANCED FEET MARKER VISUALIZATION ==========
        ttk.Separator(viz_frame, orient=tk.HORIZONTAL).grid(row=7, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        ttk.Label(viz_frame, text="Feet Marker Style & Effects:", font=("Arial", 9, "bold")).grid(row=8, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Feet Marker Style
        ttk.Label(viz_frame, text="Feet Marker Style:", font=("Arial", 9)).grid(row=9, column=0, sticky=tk.W, padx=5, pady=5)
        feet_style_combo = ttk.Combobox(viz_frame, textvariable=self.feet_marker_style, 
                                       values=["circle", "ellipse", "diamond", "star", "hexagon", "ring", "glow", "pulse"],
                                       width=15, state="readonly")
        feet_style_combo.grid(row=9, column=1, padx=5, pady=5)
        feet_style_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(visual style for feet markers, default: circle)", wraplength=280).grid(row=9, column=2, sticky=tk.W, padx=5)
        
        # Feet Marker Opacity (separate from box opacity)
        ttk.Label(viz_frame, text="Feet Marker Opacity:", font=("Arial", 9)).grid(row=10, column=0, sticky=tk.W, padx=5, pady=5)
        feet_opacity_spinbox = ttk.Spinbox(viz_frame, from_=0, to=255, increment=5,
                                          textvariable=self.feet_marker_opacity, width=8, command=self.update_preview)
        feet_opacity_spinbox.grid(row=10, column=1, padx=5, pady=5)
        feet_opacity_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        feet_opacity_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(0=transparent, 255=opaque, separate from box opacity)", wraplength=280).grid(row=10, column=2, sticky=tk.W, padx=5)
        
        # Feet Marker Effects Section
        ttk.Label(viz_frame, text="Feet Marker Effects:", font=("Arial", 9, "bold")).grid(row=11, column=0, sticky=tk.W, padx=5, pady=(10, 5))
        
        # Glow Effect
        glow_frame = ttk.Frame(viz_frame)
        glow_frame.grid(row=12, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        ttk.Checkbutton(glow_frame, text="Enable Glow", variable=self.feet_marker_enable_glow,
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Label(glow_frame, text="Intensity:").pack(side=tk.LEFT, padx=(20, 2))
        glow_intensity_spinbox = ttk.Spinbox(glow_frame, from_=0, to=100, increment=5,
                                            textvariable=self.feet_marker_glow_intensity, width=6, command=self.update_preview)
        glow_intensity_spinbox.pack(side=tk.LEFT, padx=2)
        glow_intensity_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        glow_intensity_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(glow_frame, text="(soft outer glow effect, 0-100)", foreground="gray", font=("Arial", 7)).pack(side=tk.LEFT, padx=10)
        
        # Shadow Effect
        shadow_frame = ttk.Frame(viz_frame)
        shadow_frame.grid(row=13, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        ttk.Checkbutton(shadow_frame, text="Enable Shadow", variable=self.feet_marker_enable_shadow,
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Label(shadow_frame, text="Offset:").pack(side=tk.LEFT, padx=(20, 2))
        shadow_offset_spinbox = ttk.Spinbox(shadow_frame, from_=1, to=10, increment=1,
                                           textvariable=self.feet_marker_shadow_offset, width=6, command=self.update_preview)
        shadow_offset_spinbox.pack(side=tk.LEFT, padx=2)
        shadow_offset_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        shadow_offset_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(shadow_frame, text="Opacity:").pack(side=tk.LEFT, padx=(10, 2))
        shadow_opacity_spinbox = ttk.Spinbox(shadow_frame, from_=0, to=255, increment=10,
                                            textvariable=self.feet_marker_shadow_opacity, width=6, command=self.update_preview)
        shadow_opacity_spinbox.pack(side=tk.LEFT, padx=2)
        shadow_opacity_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        shadow_opacity_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(shadow_frame, text="(drop shadow effect)", foreground="gray", font=("Arial", 7)).pack(side=tk.LEFT, padx=10)
        
        # Gradient Fill
        ttk.Checkbutton(viz_frame, text="Enable Gradient Fill", variable=self.feet_marker_enable_gradient,
                       command=self.update_preview).grid(row=14, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(viz_frame, text="(gradient from team color to transparent)", foreground="gray", font=("Arial", 7)).grid(row=14, column=2, sticky=tk.W, padx=5)
        
        # Pulse Animation
        pulse_frame = ttk.Frame(viz_frame)
        pulse_frame.grid(row=15, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        ttk.Checkbutton(pulse_frame, text="Enable Pulse Animation", variable=self.feet_marker_enable_pulse,
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Label(pulse_frame, text="Speed:").pack(side=tk.LEFT, padx=(20, 2))
        pulse_speed_spinbox = ttk.Spinbox(pulse_frame, from_=0.5, to=5.0, increment=0.1,
                                         textvariable=self.feet_marker_pulse_speed, width=6, format="%.1f", command=self.update_preview)
        pulse_speed_spinbox.pack(side=tk.LEFT, padx=2)
        pulse_speed_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        pulse_speed_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(pulse_frame, text="(breathing/pulsing effect, cycles/sec)", foreground="gray", font=("Arial", 7)).pack(side=tk.LEFT, padx=10)
        
        # Particle Effects
        particle_frame = ttk.Frame(viz_frame)
        particle_frame.grid(row=16, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        ttk.Checkbutton(particle_frame, text="Enable Particle Effects", variable=self.feet_marker_enable_particles,
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Label(particle_frame, text="Count:").pack(side=tk.LEFT, padx=(20, 2))
        particle_count_spinbox = ttk.Spinbox(particle_frame, from_=3, to=20, increment=1,
                                            textvariable=self.feet_marker_particle_count, width=6, command=self.update_preview)
        particle_count_spinbox.pack(side=tk.LEFT, padx=2)
        particle_count_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        particle_count_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(particle_frame, text="(small particles around feet markers)", foreground="gray", font=("Arial", 7)).pack(side=tk.LEFT, padx=10)
        
        # Vertical Offset (position adjustment)
        offset_frame = ttk.Frame(viz_frame)
        offset_frame.grid(row=17, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        ttk.Label(offset_frame, text="Vertical Offset:").pack(side=tk.LEFT, padx=5)
        vertical_offset_spinbox = ttk.Spinbox(offset_frame, from_=-50, to=50, increment=1,
                                             textvariable=self.feet_marker_vertical_offset, width=8, command=self.update_preview)
        vertical_offset_spinbox.pack(side=tk.LEFT, padx=2)
        vertical_offset_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        vertical_offset_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(offset_frame, text="pixels (negative = above feet, positive = below feet)", foreground="gray", font=("Arial", 7)).pack(side=tk.LEFT, padx=10)
        
        ttk.Separator(viz_frame, orient=tk.HORIZONTAL).grid(row=18, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        
        # Box Shrink Factor (for tighter boxes)
        ttk.Label(viz_frame, text="Box Shrink Factor:", font=("Arial", 9)).grid(row=19, column=0, sticky=tk.W, padx=5, pady=5)
        box_shrink_spinbox = ttk.Spinbox(viz_frame, from_=0.0, to=0.30, increment=0.01,
                                         textvariable=self.box_shrink_factor, width=8, format="%.2f", command=self.update_preview)
        box_shrink_spinbox.grid(row=19, column=1, padx=5, pady=5)
        # Bind to value changes for real-time updates
        box_shrink_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        box_shrink_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(0.0 = no shrink, 0.10 = 10% shrink on each side, default: 0.10)", wraplength=280).grid(row=19, column=2, sticky=tk.W, padx=5)
        
        # Box Thickness (border thickness)
        ttk.Label(viz_frame, text="Box Thickness (pixels):", font=("Arial", 9)).grid(row=20, column=0, sticky=tk.W, padx=5, pady=5)
        box_thickness_spinbox = ttk.Spinbox(viz_frame, from_=1, to=10, increment=1,
                                           textvariable=self.box_thickness, width=8, command=self.update_preview)
        box_thickness_spinbox.grid(row=20, column=1, padx=5, pady=5)
        # Bind to value changes for real-time updates
        box_thickness_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        box_thickness_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(border thickness, default: 2)", wraplength=280).grid(row=20, column=2, sticky=tk.W, padx=5)
        
        # Opacity Control (applies to both team colors and custom colors)
        ttk.Label(viz_frame, text="Box Fill Opacity:", font=("Arial", 9)).grid(row=21, column=0, sticky=tk.W, padx=5, pady=5)
        opacity_spinbox = ttk.Spinbox(viz_frame, from_=0, to=255, increment=5,
                                     textvariable=self.player_viz_alpha, width=8, command=self.update_preview)
        opacity_spinbox.grid(row=21, column=1, padx=5, pady=5)
        opacity_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        opacity_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(0=transparent, 255=opaque, affects team colors & custom colors)", wraplength=280).grid(row=21, column=2, sticky=tk.W, padx=5)
        
        # ========== BROADCAST-LEVEL GRAPHICS ==========
        ttk.Separator(viz_frame, orient=tk.HORIZONTAL).grid(row=22, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        ttk.Label(viz_frame, text="Broadcast-Level Graphics:", font=("Arial", 9, "bold")).grid(row=23, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Trajectory Smoothness
        ttk.Label(viz_frame, text="Trajectory Smoothness:", font=("Arial", 9)).grid(row=24, column=0, sticky=tk.W, padx=5, pady=5)
        trajectory_smoothness_combo = ttk.Combobox(viz_frame, textvariable=self.trajectory_smoothness,
                                                   values=["linear", "bezier", "spline"],
                                                   width=15, state="readonly")
        trajectory_smoothness_combo.grid(row=24, column=1, padx=5, pady=5)
        trajectory_smoothness_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(linear=fast, bezier=smooth curves, spline=very smooth)", wraplength=280).grid(row=24, column=2, sticky=tk.W, padx=5)
        
        # Player Graphics Style
        ttk.Label(viz_frame, text="Player Graphics Style:", font=("Arial", 9)).grid(row=25, column=0, sticky=tk.W, padx=5, pady=5)
        player_style_combo = ttk.Combobox(viz_frame, textvariable=self.player_graphics_style,
                                          values=["minimal", "standard", "broadcast"],
                                          width=15, state="readonly")
        player_style_combo.grid(row=25, column=1, padx=5, pady=5)
        player_style_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(minimal=basic, standard=default, broadcast=TV quality)", wraplength=280).grid(row=25, column=2, sticky=tk.W, padx=5)
        
        # Rounded Corners
        ttk.Checkbutton(viz_frame, text="Use Rounded Corners", variable=self.use_rounded_corners,
                       command=self.update_preview).grid(row=26, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(rounded corners for bounding boxes)", wraplength=280).grid(row=26, column=2, sticky=tk.W, padx=5)
        
        # Corner Radius
        ttk.Label(viz_frame, text="Corner Radius (pixels):", font=("Arial", 9)).grid(row=27, column=0, sticky=tk.W, padx=5, pady=5)
        corner_radius_spinbox = ttk.Spinbox(viz_frame, from_=0, to=20, increment=1,
                                           textvariable=self.corner_radius, width=8, command=self.update_preview)
        corner_radius_spinbox.grid(row=27, column=1, padx=5, pady=5)
        corner_radius_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        corner_radius_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(radius for rounded corners, default: 5)", wraplength=280).grid(row=27, column=2, sticky=tk.W, padx=5)
        
        # Gradient Fill
        ttk.Checkbutton(viz_frame, text="Use Gradient Fill", variable=self.use_gradient_fill,
                       command=self.update_preview).grid(row=28, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(gradient fill for bounding boxes)", wraplength=280).grid(row=28, column=2, sticky=tk.W, padx=5)
        
        # Jersey Badge
        ttk.Checkbutton(viz_frame, text="Show Jersey Number Badge", variable=self.show_jersey_badge,
                       command=self.update_preview).grid(row=29, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(circular badge with jersey number)", wraplength=280).grid(row=29, column=2, sticky=tk.W, padx=5)
        
        # Ball Graphics Style
        ttk.Label(viz_frame, text="Ball Graphics Style:", font=("Arial", 9)).grid(row=30, column=0, sticky=tk.W, padx=5, pady=5)
        ball_style_combo = ttk.Combobox(viz_frame, textvariable=self.ball_graphics_style,
                                        values=["standard", "broadcast"],
                                        width=15, state="readonly")
        ball_style_combo.grid(row=30, column=1, padx=5, pady=5)
        ball_style_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(standard=basic, broadcast=velocity color coding)", wraplength=280).grid(row=30, column=2, sticky=tk.W, padx=5)
        
        # Statistics Overlay Section
        ttk.Separator(viz_frame, orient=tk.HORIZONTAL).grid(row=31, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        
        # Show Statistics Overlay
        ttk.Checkbutton(viz_frame, text="Show Statistics Overlay", variable=self.show_statistics,
                       command=self.update_preview).grid(row=32, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(broadcast-style statistics panel)", wraplength=280).grid(row=32, column=2, sticky=tk.W, padx=5)
        
        # Statistics Position
        ttk.Label(viz_frame, text="Statistics Position:", font=("Arial", 9)).grid(row=33, column=0, sticky=tk.W, padx=5, pady=5)
        stats_position_combo = ttk.Combobox(viz_frame, textvariable=self.statistics_position,
                                           values=["top_left", "top_right", "bottom_left", "bottom_right",
                                                  "top_banner", "bottom_banner", "left_bar", "right_bar"],
                                           width=15, state="readonly")
        stats_position_combo.grid(row=33, column=1, padx=5, pady=5)
        stats_position_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(corner panels, full-width banners, or full-height bars)", wraplength=280).grid(row=33, column=2, sticky=tk.W, padx=5)
        
        # Statistics Panel Size (for corner panels only)
        ttk.Label(viz_frame, text="Panel Width:", font=("Arial", 9)).grid(row=34, column=0, sticky=tk.W, padx=5, pady=5)
        stats_width_spinbox = ttk.Spinbox(viz_frame, from_=100, to=800, increment=10,
                                         textvariable=self.statistics_panel_width, width=8, command=self.update_preview)
        stats_width_spinbox.grid(row=34, column=1, padx=5, pady=5)
        stats_width_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(for corner panels only, banners/bars use fixed sizes)", wraplength=280).grid(row=34, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(viz_frame, text="Panel Height:", font=("Arial", 9)).grid(row=35, column=0, sticky=tk.W, padx=5, pady=5)
        stats_height_spinbox = ttk.Spinbox(viz_frame, from_=50, to=600, increment=10,
                                          textvariable=self.statistics_panel_height, width=8, command=self.update_preview)
        stats_height_spinbox.grid(row=35, column=1, padx=5, pady=5)
        stats_height_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(for corner panels only)", wraplength=280).grid(row=35, column=2, sticky=tk.W, padx=5)
        
        # Statistics Background Opacity
        ttk.Label(viz_frame, text="Background Opacity:", font=("Arial", 9)).grid(row=36, column=0, sticky=tk.W, padx=5, pady=5)
        stats_bg_alpha_spinbox = ttk.Spinbox(viz_frame, from_=0.0, to=1.0, increment=0.05,
                                            textvariable=self.statistics_bg_alpha, width=8, format="%.2f", command=self.update_preview)
        stats_bg_alpha_spinbox.grid(row=36, column=1, padx=5, pady=5)
        stats_bg_alpha_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(0.0=transparent, 1.0=opaque, default: 0.75)", wraplength=280).grid(row=36, column=2, sticky=tk.W, padx=5)
        
        # Statistics Background Color - Color Picker
        stats_bg_color_frame = ttk.Frame(viz_frame)
        stats_bg_color_frame.grid(row=37, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        from color_picker_utils import create_color_picker_widget
        color_picker_frame, _ = create_color_picker_widget(
            stats_bg_color_frame,
            self.statistics_bg_color_rgb,
            label_text="Background Color:",
            initial_color=(0, 0, 0),
            on_change_callback=lambda rgb: self.update_preview()
        )
        color_picker_frame.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(stats_bg_color_frame, text="(default: black)", wraplength=200).pack(side=tk.LEFT, padx=10)
        
        # Statistics Text Color - Color Picker
        stats_text_color_frame = ttk.Frame(viz_frame)
        stats_text_color_frame.grid(row=38, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        from color_picker_utils import create_color_picker_widget
        color_picker_frame, _ = create_color_picker_widget(
            stats_text_color_frame,
            self.statistics_text_color_rgb,
            label_text="Text Color:",
            initial_color=(255, 255, 255),
            on_change_callback=lambda rgb: self.update_preview()
        )
        color_picker_frame.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(stats_text_color_frame, text="(default: white)", wraplength=200).pack(side=tk.LEFT, padx=10)
        
        # Statistics Title Color - Color Picker
        stats_title_color_frame = ttk.Frame(viz_frame)
        stats_title_color_frame.grid(row=39, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        from color_picker_utils import create_color_picker_widget
        color_picker_frame, _ = create_color_picker_widget(
            stats_title_color_frame,
            self.statistics_title_color_rgb,
            label_text="Title Color:",
            initial_color=(255, 255, 0),
            on_change_callback=lambda rgb: self.update_preview()
        )
        color_picker_frame.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(stats_title_color_frame, text="(default: yellow)", wraplength=200).pack(side=tk.LEFT, padx=10)
        
        # Heat Map Section
        ttk.Separator(viz_frame, orient=tk.HORIZONTAL).grid(row=40, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        
        # Show Heat Map
        ttk.Checkbutton(viz_frame, text="Show Heat Map", variable=self.show_heat_map,
                       command=self.update_preview).grid(row=41, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(player position heat map overlay)", wraplength=280).grid(row=41, column=2, sticky=tk.W, padx=5)
        
        # Heat Map Opacity
        ttk.Label(viz_frame, text="Heat Map Opacity:", font=("Arial", 9)).grid(row=42, column=0, sticky=tk.W, padx=5, pady=5)
        heat_map_alpha_spinbox = ttk.Spinbox(viz_frame, from_=0.0, to=1.0, increment=0.1,
                                            textvariable=self.heat_map_alpha, width=8, format="%.1f", command=self.update_preview)
        heat_map_alpha_spinbox.grid(row=42, column=1, padx=5, pady=5)
        heat_map_alpha_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        heat_map_alpha_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(0.0=transparent, 1.0=opaque, default: 0.4)", wraplength=280).grid(row=42, column=2, sticky=tk.W, padx=5)
        
        # Heat Map Color Scheme
        ttk.Label(viz_frame, text="Heat Map Color:", font=("Arial", 9)).grid(row=43, column=0, sticky=tk.W, padx=5, pady=5)
        heat_map_color_combo = ttk.Combobox(viz_frame, textvariable=self.heat_map_color_scheme,
                                            values=["hot", "cool", "green"],
                                            width=15, state="readonly")
        heat_map_color_combo.grid(row=43, column=1, padx=5, pady=5)
        heat_map_color_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(hot=red/yellow, cool=blue/cyan, green=green)", wraplength=280).grid(row=43, column=2, sticky=tk.W, padx=5)
        
        # Analytics Section
        ttk.Separator(viz_frame, orient=tk.HORIZONTAL).grid(row=44, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        ttk.Label(viz_frame, text="Analytics Display:", font=("Arial", 9, "bold")).grid(row=45, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Analytics Position
        ttk.Label(viz_frame, text="Analytics Position:", font=("Arial", 9)).grid(row=46, column=0, sticky=tk.W, padx=5, pady=5)
        analytics_position_combo = ttk.Combobox(viz_frame, textvariable=self.analytics_position,
                                               values=["with_player", "top_left", "top_right", "bottom_left", "bottom_right",
                                                      "top_banner", "bottom_banner", "left_bar", "right_bar"],
                                               width=15, state="readonly")
        analytics_position_combo.grid(row=46, column=1, padx=5, pady=5)
        analytics_position_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(with_player=next to each player, or use banners/bars/corners)", wraplength=280).grid(row=46, column=2, sticky=tk.W, padx=5)
        
        # Analytics Font Scale
        ttk.Label(viz_frame, text="Analytics Font Scale:", font=("Arial", 9)).grid(row=47, column=0, sticky=tk.W, padx=5, pady=5)
        analytics_font_scale_spinbox = ttk.Spinbox(viz_frame, from_=0.3, to=4.0, increment=0.1,
                                                   textvariable=self.analytics_font_scale, width=8, format="%.1f", command=self.update_preview)
        analytics_font_scale_spinbox.grid(row=47, column=1, padx=5, pady=5)
        analytics_font_scale_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        analytics_font_scale_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(0.3=small, 1.0=normal, 4.0=very large, works in CSV & metadata formats)", wraplength=280).grid(row=47, column=2, sticky=tk.W, padx=5)
        
        # Analytics Font Thickness
        ttk.Label(viz_frame, text="Analytics Font Thickness:", font=("Arial", 9)).grid(row=48, column=0, sticky=tk.W, padx=5, pady=5)
        analytics_font_thickness_spinbox = ttk.Spinbox(viz_frame, from_=1, to=5, increment=1,
                                                      textvariable=self.analytics_font_thickness, width=8, command=self.update_preview)
        analytics_font_thickness_spinbox.grid(row=48, column=1, padx=5, pady=5)
        analytics_font_thickness_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        analytics_font_thickness_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(1=thin, 3=normal, 5=very thick, for better readability)", wraplength=280).grid(row=48, column=2, sticky=tk.W, padx=5)
        
        # Analytics Font Face
        ttk.Label(viz_frame, text="Analytics Font Face:", font=("Arial", 9)).grid(row=49, column=0, sticky=tk.W, padx=5, pady=5)
        analytics_font_face_combo = ttk.Combobox(viz_frame, textvariable=self.analytics_font_face,
                                                values=["FONT_HERSHEY_SIMPLEX", "FONT_HERSHEY_PLAIN", "FONT_HERSHEY_DUPLEX",
                                                       "FONT_HERSHEY_COMPLEX", "FONT_HERSHEY_TRIPLEX", "FONT_HERSHEY_COMPLEX_SMALL",
                                                       "FONT_HERSHEY_SCRIPT_SIMPLEX", "FONT_HERSHEY_SCRIPT_COMPLEX"],
                                                width=20, state="readonly")
        analytics_font_face_combo.grid(row=49, column=1, padx=5, pady=5)
        analytics_font_face_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(font style)", wraplength=280).grid(row=49, column=2, sticky=tk.W, padx=5)
        
        # Analytics Color Customization
        ttk.Checkbutton(viz_frame, text="Use Custom Analytics Color", variable=self.use_custom_analytics_color,
                       command=self.update_preview).grid(row=50, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(recommended: white (255,255,255) for best contrast)", wraplength=280).grid(row=50, column=2, sticky=tk.W, padx=5)
        
        # Analytics Color RGB
        analytics_color_frame = ttk.Frame(viz_frame)
        analytics_color_frame.grid(row=51, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        from color_picker_utils import create_color_picker_widget
        color_picker_frame, _ = create_color_picker_widget(
            analytics_color_frame,
            self.analytics_color_rgb,
            label_text="Analytics Color:",
            initial_color=(255, 255, 255),
            on_change_callback=lambda rgb: self.update_preview()
        )
        color_picker_frame.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(analytics_color_frame, text="(default: white)", wraplength=200).pack(side=tk.LEFT, padx=10)
        
        # Analytics Title Color RGB (for panel headers) - Color Picker
        analytics_title_color_frame = ttk.Frame(viz_frame)
        analytics_title_color_frame.grid(row=52, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        color_picker_frame2, _ = create_color_picker_widget(
            analytics_title_color_frame,
            self.analytics_title_color_rgb,
            label_text="Title Color:",
            initial_color=(255, 255, 0),
            on_change_callback=lambda rgb: self.update_preview()
        )
        color_picker_frame2.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(analytics_title_color_frame, text="(for panel/banner headers, default: yellow)", foreground="gray", font=("Arial", 7)).pack(side=tk.LEFT, padx=10)
        
        # Quality Preset
        ttk.Separator(viz_frame, orient=tk.HORIZONTAL).grid(row=53, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        ttk.Label(viz_frame, text="Overlay Quality Preset:", font=("Arial", 9)).grid(row=54, column=0, sticky=tk.W, padx=5, pady=5)
        quality_preset_combo = ttk.Combobox(viz_frame, textvariable=self.overlay_quality_preset,
                                            values=["sd", "hd", "4k", "broadcast"],
                                            width=15, state="readonly")
        quality_preset_combo.grid(row=54, column=1, padx=5, pady=5)
        quality_preset_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(sd=fast, hd=balanced, 4k=high quality, broadcast=maximum)", wraplength=280).grid(row=54, column=2, sticky=tk.W, padx=5)
        
        # ========== CUSTOM COLORS & LABELS ==========
        ttk.Separator(viz_frame, orient=tk.HORIZONTAL).grid(row=55, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        ttk.Label(viz_frame, text="Custom Colors & Labels:", font=("Arial", 9, "bold")).grid(row=56, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Custom Box Color
        use_custom_color_check = ttk.Checkbutton(viz_frame, text="Use Custom Box Color",
                                                 variable=self.use_custom_box_color, command=self.update_preview)
        use_custom_color_check.grid(row=57, column=0, sticky=tk.W, padx=5, pady=5)
        
        # RGB color controls (for custom color only)
        color_control_frame = ttk.Frame(viz_frame)
        color_control_frame.grid(row=57, column=1, columnspan=2, sticky=tk.W, padx=(20, 5), pady=5)
        
        from color_picker_utils import create_color_picker_widget
        color_picker_frame, _ = create_color_picker_widget(
            color_control_frame,
            self.box_color_rgb,
            label_text="Box Color:",
            initial_color=(0, 255, 0),
            on_change_callback=lambda rgb: self.update_preview()
        )
        color_picker_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(viz_frame, text="(RGB color controls for custom box color)", wraplength=280).grid(row=57, column=2, sticky=tk.W, padx=5)
        
        # Show player labels (to reduce clutter)
        show_labels_check = ttk.Checkbutton(viz_frame, text="Show Player Labels",
                                           variable=self.show_player_labels, command=self.update_preview)
        show_labels_check.grid(row=58, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(uncheck to hide all player name/ID labels and reduce clutter)", wraplength=280).grid(row=58, column=2, sticky=tk.W, padx=5)
        
        # Label type
        ttk.Label(viz_frame, text="Label Type:", font=("Arial", 9)).grid(row=59, column=0, sticky=tk.W, padx=5, pady=5)
        label_type_frame = ttk.Frame(viz_frame)
        label_type_frame.grid(row=59, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Radiobutton(label_type_frame, text="Full Name", variable=self.label_type, value="full_name",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(label_type_frame, text="Last Name", variable=self.label_type, value="last_name",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(label_type_frame, text="Jersey #", variable=self.label_type, value="jersey",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(label_type_frame, text="Team", variable=self.label_type, value="team",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(label_type_frame, text="Custom", variable=self.label_type, value="custom",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(viz_frame, text="(what to display on player labels)", wraplength=280).grid(row=59, column=2, sticky=tk.W, padx=5)
        
        # Custom label text (only shown when custom is selected)
        self.custom_label_frame = ttk.Frame(viz_frame)
        self.custom_label_frame.grid(row=60, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        ttk.Label(self.custom_label_frame, text="Custom Text:", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        custom_text_entry = ttk.Entry(self.custom_label_frame, textvariable=self.label_custom_text, width=20)
        custom_text_entry.pack(side=tk.LEFT, padx=5)
        custom_text_entry.bind('<KeyRelease>', lambda e: self.update_preview())
        ttk.Label(self.custom_label_frame, text="(text to show for all players, e.g., 'Opponent', 'Gray')").pack(side=tk.LEFT, padx=5)
        self._update_label_type_ui()  # Initial state
        
        # Label font options
        ttk.Label(viz_frame, text="Label Font:", font=("Arial", 9)).grid(row=61, column=0, sticky=tk.W, padx=5, pady=5)
        font_frame = ttk.Frame(viz_frame)
        font_frame.grid(row=61, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(font_frame, text="Face:").pack(side=tk.LEFT, padx=2)
        font_face_combo = ttk.Combobox(font_frame, textvariable=self.label_font_face,
                                      values=["FONT_HERSHEY_SIMPLEX", "FONT_HERSHEY_PLAIN", "FONT_HERSHEY_DUPLEX",
                                             "FONT_HERSHEY_COMPLEX", "FONT_HERSHEY_TRIPLEX", "FONT_HERSHEY_COMPLEX_SMALL",
                                             "FONT_HERSHEY_SCRIPT_SIMPLEX", "FONT_HERSHEY_SCRIPT_COMPLEX"],
                                      state="readonly", width=20)
        font_face_combo.pack(side=tk.LEFT, padx=5)
        font_face_combo.bind("<<ComboboxSelected>>", lambda e: self.update_preview())
        
        ttk.Label(font_frame, text="Size:").pack(side=tk.LEFT, padx=(10, 2))
        label_font_spinbox = ttk.Spinbox(font_frame, from_=0.3, to=1.5, increment=0.1,
                                         textvariable=self.label_font_scale, width=8, format="%.1f", command=self.update_preview)
        # Note: OpenCV font scale is typically 0.3-1.0, values above 1.0 are very large
        label_font_spinbox.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(viz_frame, text="(font style and size for labels, OpenCV scale: 0.3-1.0 recommended, default: 0.7)", wraplength=280).grid(row=61, column=2, sticky=tk.W, padx=5)
        
        # Label Color Controls
        use_custom_label_color_check = ttk.Checkbutton(viz_frame, text="Use Custom Label Color",
                                                       variable=self.use_custom_label_color, command=self.update_preview)
        use_custom_label_color_check.grid(row=62, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(override team colors with custom color)", wraplength=280).grid(row=62, column=2, sticky=tk.W, padx=5)
        
        label_color_control_frame = ttk.Frame(viz_frame)
        # Color picker inline to the left in column 1
        label_color_control_frame.grid(row=62, column=1, sticky=tk.W, padx=5, pady=5)
        
        from color_picker_utils import create_color_picker_widget
        color_picker_frame, _ = create_color_picker_widget(
            label_color_control_frame,
            self.label_color_rgb,
            label_text="Label Color:",
            initial_color=(255, 255, 255),
            on_change_callback=lambda rgb: self.update_preview()
        )
        color_picker_frame.pack(side=tk.LEFT, padx=(0, 0))
        
        # Ball possession indicator
        ball_possession_check = ttk.Checkbutton(viz_frame, text="Show Ball Possession Indicator",
                                               variable=self.show_ball_possession, command=self.update_preview)
        ball_possession_check.grid(row=63, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(blue triangle above player when they have ball)", wraplength=280).grid(row=63, column=2, sticky=tk.W, padx=5)
        
        # ENHANCEMENT: Direction arrow and player trail
        ttk.Separator(viz_frame, orient=tk.HORIZONTAL).grid(row=64, column=0, columnspan=3, sticky=tk.EW, pady=(15, 10))
        ttk.Label(viz_frame, text="Motion Visualization", font=("Arial", 9, "bold")).grid(row=65, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        
        # Show direction arrow
        show_direction_arrow_check = ttk.Checkbutton(viz_frame, text="Show Direction Arrow",
                                                    variable=self.show_direction_arrow, command=self.update_preview)
        show_direction_arrow_check.grid(row=66, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(arrow under feet pointing in direction of travel)", wraplength=280).grid(row=66, column=2, sticky=tk.W, padx=5)
        
        # Show player trail
        show_player_trail_check = ttk.Checkbutton(viz_frame, text="Show Player Trail (Breadcrumb)",
                                                variable=self.show_player_trail, command=self.update_preview)
        show_player_trail_check.grid(row=67, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(trail behind player showing movement path)", wraplength=280).grid(row=67, column=2, sticky=tk.W, padx=5)
        
        # Enhanced glow for feet markers (make it more prominent)
        enhanced_glow_check = ttk.Checkbutton(viz_frame, text="Enhanced Glow on Feet Markers",
                                             variable=self.feet_marker_enable_glow, command=self.update_preview)
        enhanced_glow_check.grid(row=68, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(glowing effect around feet markers for better visibility)", wraplength=280).grid(row=68, column=2, sticky=tk.W, padx=5)
        
        # ========== TRACK ID DECAY VISUALIZATION ==========
        ttk.Separator(viz_frame, orient=tk.HORIZONTAL).grid(row=69, column=0, columnspan=3, sticky=tk.EW, pady=(15, 10))
        ttk.Label(viz_frame, text="Track ID Decay Visualization", font=("Arial", 9, "bold")).grid(row=70, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        
        # Show predicted boxes (track ID decay)
        show_predicted_check = ttk.Checkbutton(viz_frame, text="Show Predicted Boxes",
                                              variable=self.show_predicted_boxes, command=self.update_preview)
        show_predicted_check.grid(row=71, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(uncheck to hide trailing dots/boxes from track ID decay)", wraplength=280).grid(row=71, column=2, sticky=tk.W, padx=5)
        
        # Prediction duration
        ttk.Label(viz_frame, text="Prediction Duration (seconds):", font=("Arial", 9)).grid(row=72, column=0, sticky=tk.W, padx=5, pady=5)
        prediction_duration_spinbox = ttk.Spinbox(viz_frame, from_=0.0, to=2.0, increment=0.1,
                                                  textvariable=self.prediction_duration, width=8, format="%.1f", command=self.update_preview)
        prediction_duration_spinbox.grid(row=72, column=1, padx=5, pady=5)
        # Bind to value changes for real-time updates
        prediction_duration_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        prediction_duration_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(how long to show predicted boxes after track is lost, default: 0.3s)", wraplength=280).grid(row=72, column=2, sticky=tk.W, padx=5)
        
        # Prediction style
        ttk.Label(viz_frame, text="Prediction Style:", font=("Arial", 9)).grid(row=73, column=0, sticky=tk.W, padx=5, pady=5)
        prediction_style_frame = ttk.Frame(viz_frame)
        prediction_style_frame.grid(row=73, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Create two rows for radio buttons to fit all options
        style_row1 = ttk.Frame(prediction_style_frame)
        style_row1.pack(side=tk.TOP, anchor=tk.W)
        style_row2 = ttk.Frame(prediction_style_frame)
        style_row2.pack(side=tk.TOP, anchor=tk.W, pady=(5, 0))
        
        ttk.Radiobutton(style_row1, text="Dot", variable=self.prediction_style, value="dot",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(style_row1, text="Box", variable=self.prediction_style, value="box",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(style_row1, text="Cross", variable=self.prediction_style, value="cross",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(style_row2, text="X", variable=self.prediction_style, value="x",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(style_row2, text="Arrow", variable=self.prediction_style, value="arrow",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(style_row2, text="Diamond", variable=self.prediction_style, value="diamond",
                       command=self.update_preview).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(viz_frame, text="(visual style for predicted boxes, default: dot)", wraplength=280).grid(row=73, column=2, sticky=tk.W, padx=5, pady=(0, 5))
        
        # Prediction color
        ttk.Label(viz_frame, text="Prediction Color:", font=("Arial", 9)).grid(row=74, column=0, sticky=tk.W, padx=5, pady=5)
        prediction_color_frame = ttk.Frame(viz_frame)
        prediction_color_frame.grid(row=74, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(prediction_color_frame, text="R:", foreground="red").pack(side=tk.LEFT, padx=2)
        ttk.Spinbox(prediction_color_frame, from_=0, to=255, increment=5,
                   textvariable=self.prediction_color_r, width=5, command=self.update_preview).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(prediction_color_frame, text="G:", foreground="green").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Spinbox(prediction_color_frame, from_=0, to=255, increment=5,
                   textvariable=self.prediction_color_g, width=5, command=self.update_preview).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(prediction_color_frame, text="B:", foreground="blue").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Spinbox(prediction_color_frame, from_=0, to=255, increment=5,
                   textvariable=self.prediction_color_b, width=5, command=self.update_preview).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(prediction_color_frame, text="A:", foreground="gray").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Spinbox(prediction_color_frame, from_=0, to=255, increment=5,
                   textvariable=self.prediction_color_alpha, width=5, command=self.update_preview).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(viz_frame, text="(RGBA color of predicted markers, A=opacity, default: yellow, 255=opaque)").grid(row=74, column=2, sticky=tk.W, padx=5)
        
        # Prediction size
        ttk.Label(viz_frame, text="Prediction Size (pixels):", font=("Arial", 9)).grid(row=75, column=0, sticky=tk.W, padx=5, pady=5)
        prediction_size_spinbox = ttk.Spinbox(viz_frame, from_=3, to=15, increment=1,
                                             textvariable=self.prediction_size, width=8, command=self.update_preview)
        prediction_size_spinbox.grid(row=75, column=1, padx=5, pady=5)
        # Bind to value changes for real-time updates
        prediction_size_spinbox.bind('<KeyRelease>', lambda e: self.update_preview())
        prediction_size_spinbox.bind('<ButtonRelease>', lambda e: self.update_preview())
        ttk.Label(viz_frame, text="(size of predicted markers, default: 5)", wraplength=280).grid(row=75, column=2, sticky=tk.W, padx=5)
        
        # Show raw YOLO detection boxes
        show_yolo_check = ttk.Checkbutton(viz_frame, text="Show YOLO Detection Boxes (Raw)",
                                         variable=self.show_yolo_boxes, command=self.update_preview)
        show_yolo_check.grid(row=76, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(viz_frame, text="(shows raw YOLO detections before tracking, in orange)", 
                 font=("Arial", 7), foreground="gray", wraplength=280).grid(row=76, column=2, sticky=tk.W, padx=5)
        
        # ========== LIVE PREVIEW ==========
        ttk.Separator(viz_frame, orient=tk.HORIZONTAL).grid(row=77, column=0, columnspan=3, sticky=tk.EW, pady=15)
        ttk.Label(viz_frame, text="Live Preview:", font=("Arial", 10, "bold")).grid(row=78, column=0, columnspan=3, sticky=tk.W, padx=5, pady=(5, 10))
        
        preview_frame = ttk.LabelFrame(viz_frame, text="Visualization Preview (Updates Live)", padding="10")
        preview_frame.grid(row=57, column=0, columnspan=3, sticky=tk.W+tk.E, padx=5, pady=5)
        preview_frame.columnconfigure(0, weight=1)
        
        # Create preview canvas (larger to show both player and decay preview)
        self.preview_canvas = tk.Canvas(preview_frame, width=500, height=300, bg="black", highlightthickness=2, highlightbackground="gray")
        self.preview_canvas.grid(row=0, column=0, padx=5, pady=5)
        
        # Add label below preview
        preview_help = ttk.Label(preview_frame, 
                                text="Preview updates automatically as you change visualization settings above",
                                foreground="gray", font=("Arial", 8), justify=tk.CENTER)
        preview_help.grid(row=1, column=0, pady=(5, 0))
        
        # Store preview canvas reference for updates
        self.preview_image = None
        
        # Update preview initially and add callbacks to spinboxes
        self.root.after(100, self.update_preview)
        
        # Add trace callbacks to update preview when settings change
        self.ellipse_width.trace('w', lambda *args: self.update_preview())
        self.ellipse_height.trace('w', lambda *args: self.update_preview())
        self.ellipse_outline_thickness.trace('w', lambda *args: self.update_preview())
        self.box_shrink_factor.trace('w', lambda *args: self.update_preview())
        self.box_thickness.trace('w', lambda *args: self.update_preview())
        # Color picker variables automatically trigger update_preview via on_change_callback
        self.box_color_rgb.trace_add('write', lambda *args: self.update_preview())
        self.label_color_rgb.trace_add('write', lambda *args: self.update_preview())
        self.analytics_color_rgb.trace_add('write', lambda *args: self.update_preview())
        self.analytics_title_color_rgb.trace_add('write', lambda *args: self.update_preview())
        self.statistics_bg_color_rgb.trace_add('write', lambda *args: self.update_preview())
        self.statistics_text_color_rgb.trace_add('write', lambda *args: self.update_preview())
        self.statistics_title_color_rgb.trace_add('write', lambda *args: self.update_preview())
        
        self.player_viz_alpha.trace('w', lambda *args: self.update_preview())
        self.use_custom_box_color.trace('w', lambda *args: self.update_preview())
        self.show_player_labels.trace('w', lambda *args: self.update_preview())
        self.label_font_scale.trace('w', lambda *args: self.update_preview())
        self.use_custom_label_color.trace('w', lambda *args: self.update_preview())
        self.show_predicted_boxes.trace('w', lambda *args: self.update_preview())
        self.prediction_duration.trace('w', lambda *args: self.update_preview())
        self.prediction_style.trace('w', lambda *args: self.update_preview())
        self.prediction_size.trace('w', lambda *args: self.update_preview())
        self.show_yolo_boxes.trace('w', lambda *args: self.update_preview())
        self.prediction_color_r.trace('w', lambda *args: self.update_preview())
        self.prediction_color_g.trace('w', lambda *args: self.update_preview())
        self.prediction_color_b.trace('w', lambda *args: self.update_preview())
        self.prediction_color_alpha.trace('w', lambda *args: self.update_preview())
        # Video game quality settings
        self.enable_advanced_blending.trace('w', lambda *args: self.update_preview())
        self.use_professional_text.trace('w', lambda *args: self.update_preview())
        self.enable_motion_blur.trace('w', lambda *args: self.update_preview())
        self.motion_blur_amount.trace('w', lambda *args: self.update_preview())
        
        # Add trace callbacks for new separate controls
        self.show_bounding_boxes.trace('w', lambda *args: self.update_preview())
        self.show_circles_at_feet.trace('w', lambda *args: self.update_preview())
        self.label_type.trace('w', lambda *args: self.update_preview())
        self.label_custom_text.trace('w', lambda *args: self.update_preview())
        self.label_font_face.trace('w', lambda *args: self.update_preview())
        
        # Analytics settings for preview
        self.analytics_font_scale.trace('w', lambda *args: self.update_preview())
        if hasattr(self, 'analytics_font_thickness'):
            self.analytics_font_thickness.trace('w', lambda *args: self.update_preview())
        if hasattr(self, 'analytics_font_face'):
            self.analytics_font_face.trace('w', lambda *args: self.update_preview())
        if hasattr(self, 'analytics_position'):
            self.analytics_position.trace('w', lambda *args: self.update_preview())
        if hasattr(self, 'use_custom_analytics_color'):
            self.use_custom_analytics_color.trace('w', lambda *args: self.update_preview())
        # Analytics colors use color picker with automatic callbacks
        # Note: analytics_title_color_rgb is already traced on line 1767
        self.show_ball_possession.trace('w', lambda *args: self.update_preview())
        self.viz_color_mode.trace('w', lambda *args: self.update_preview())  # Color mode affects preview
        
        # Player tracking stability controls
        # ========== TRACKING TAB ==========
        tracking_frame = ttk.LabelFrame(tracking_tab, text="Player Tracking Stability", padding="10")
        tracking_frame.grid(row=0, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        tracking_tab.columnconfigure(0, weight=1)
        
        # Configure tracking_frame columns for proper spacing
        tracking_frame.columnconfigure(0, weight=0, minsize=180)  # Label column - fixed width
        tracking_frame.columnconfigure(1, weight=0, minsize=100)  # Control column - fixed width
        tracking_frame.columnconfigure(2, weight=1, minsize=300)   # Help text column - expands
        
        # Track threshold
        ttk.Label(tracking_frame, text="Detection Threshold:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        track_thresh_spinbox = ttk.Spinbox(tracking_frame, from_=0.1, to=0.5, increment=0.05,
                                           textvariable=self.track_thresh, width=8)
        track_thresh_spinbox.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(lower = more detections, default: 0.20)", wraplength=280).grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Match threshold
        ttk.Label(tracking_frame, text="Match Threshold:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        match_thresh_spinbox = ttk.Spinbox(tracking_frame, from_=0.5, to=1.0, increment=0.1,
                                           textvariable=self.match_thresh, width=8)
        match_thresh_spinbox.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(higher = stricter matching, default: 0.6)", wraplength=280).grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # Track buffer time (CRITICAL for preventing blinking - more intuitive than frames)
        ttk.Label(tracking_frame, text="Track Buffer Time (Seconds):", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        track_buffer_seconds_spinbox = ttk.Spinbox(tracking_frame, from_=1.0, to=15.0, increment=0.5,
                                                   textvariable=self.track_buffer_seconds, width=10, format="%.1f")
        track_buffer_seconds_spinbox.grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(how long to keep lost tracks alive, higher = less blinking, default: 5.0s)", 
                 foreground="darkgreen", wraplength=280).grid(row=2, column=2, sticky=tk.W, padx=5)
        # Show frame-based examples
        buffer_info = ttk.Label(tracking_frame, 
                               text="At 24fps: 5.0s = 120 frames | At 60fps: 5.0s = 300 frames | At 120fps: 5.0s = 600 frames", 
                               font=("Arial", 7), foreground="gray")
        buffer_info.grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=5, pady=(0, 5))
        
        # Legacy track buffer (frames) - kept for backward compatibility but less prominent
        ttk.Label(tracking_frame, text="Track Buffer (Frames, Legacy):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        track_buffer_spinbox = ttk.Spinbox(tracking_frame, from_=30, to=500, increment=10,
                                          textvariable=self.track_buffer, width=10)
        track_buffer_spinbox.grid(row=4, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(only used if Buffer Time = 0, otherwise auto-calculated)", 
                 font=("Arial", 7), foreground="gray", wraplength=280).grid(row=4, column=2, sticky=tk.W, padx=5)
        
        # Tracker type
        ttk.Label(tracking_frame, text="Tracker Type:", font=("Arial", 9, "bold")).grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        # Check if BoxMOT is available
        boxmot_available = False
        try:
            # Try importing boxmot directly first to see if it's available
            try:
                from boxmot import DeepOcSort
                boxmot_available = True
                print(f"✓ BoxMOT detected in GUI (direct import)")
            except ImportError as e:
                print(f"⚠ BoxMOT not installed: {e}")
                print(f"   Python executable: {sys.executable}")
                print(f"   Python path: {sys.path[:3]}")
                # Try to see if boxmot is in a different location
                try:
                    import importlib.util
                    spec = importlib.util.find_spec("boxmot")
                    if spec:
                        print(f"   BoxMOT found at: {spec.origin}")
                    else:
                        print(f"   BoxMOT spec not found")
                except:
                    pass
                boxmot_available = False
            except Exception as e:
                print(f"⚠ BoxMOT import error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                boxmot_available = False
            
            # Also try wrapper import for consistency
            if boxmot_available:
                try:
                    from boxmot_tracker_wrapper import BOXMOT_AVAILABLE
                    if not BOXMOT_AVAILABLE:
                        print(f"⚠ BoxMOT wrapper reports unavailable")
                        boxmot_available = False
                except Exception as e:
                    print(f"⚠ BoxMOT wrapper import error: {e}")
                    # Don't fail if wrapper has issues, boxmot itself works
        except Exception as e:
            print(f"⚠ BoxMOT detection failed: {e}")
            import traceback
            traceback.print_exc()
            boxmot_available = False
        
        if boxmot_available:
            tracker_options = ["bytetrack", "ocsort", "deepocsort", "strongsort", "botsort"]
            tracker_tooltip = "bytetrack: Fast motion-based\nocsort: Better occlusion handling\ndeepocsort: OC-SORT + appearance (recommended)\nstrongsort: Best accuracy, slower\nbotsort: ByteTrack + appearance"
            print(f"✓ BoxMOT trackers available: {tracker_options}")
        else:
            tracker_options = ["bytetrack", "ocsort"]
            tracker_tooltip = "bytetrack: Fast motion-based\nocsort: Better occlusion handling\n\n(Install boxmot for more options: pip install boxmot)"
            print(f"⚠ BoxMOT not available, showing standard trackers only: {tracker_options}")
        
        # Tracker type change handler - warn if Re-ID is disabled but tracker requires it
        def on_tracker_type_change(event=None):
            tracker = self.tracker_type.get()
            if not self.use_reid.get():
                if tracker in ["deepocsort", "strongsort", "botsort"]:
                    print("  ⚠ Warning: Tracker '{}' includes Re-ID features, but Re-ID is disabled. Consider using 'bytetrack' or 'ocsort' for pure tracking.".format(tracker))
        
        tracker_type_combo = ttk.Combobox(tracking_frame, textvariable=self.tracker_type,
                                         values=tracker_options, state="readonly", width=15)
        tracker_type_combo.grid(row=5, column=1, padx=5, pady=5)
        tracker_type_combo.bind('<<ComboboxSelected>>', on_tracker_type_change)
        
        # Store reference for potential updates
        self.tracker_type_combo = tracker_type_combo
        # Update tooltip based on BoxMOT availability
        if boxmot_available:
            tracker_help_text = "(DeepOCSORT/StrongSORT: best for occlusions, ByteTrack: fastest, OC-SORT: balanced)"
        else:
            tracker_help_text = "(OC-SORT: better for scrums/bunched players, ByteTrack: faster for open play)"
        ttk.Label(tracking_frame, text=tracker_help_text, 
                 foreground="darkgreen", wraplength=280).grid(row=5, column=2, sticky=tk.W, padx=5)
        
        # Video FPS (for analysis settings)
        ttk.Label(tracking_frame, text="Video FPS:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        video_fps_spinbox = ttk.Spinbox(tracking_frame, from_=0, to=240, increment=1,
                                        textvariable=self.video_fps, width=8)
        video_fps_spinbox.grid(row=6, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(0 = auto-detect, set manually if detection is wrong)", wraplength=280).grid(row=6, column=2, sticky=tk.W, padx=5)
        
        # Output FPS
        ttk.Label(tracking_frame, text="Output FPS:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
        output_fps_spinbox = ttk.Spinbox(tracking_frame, from_=0, to=120, increment=1,
                                         textvariable=self.output_fps, width=8)
        output_fps_spinbox.grid(row=7, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(0 = same as input, lower = smaller file)", wraplength=280).grid(row=7, column=2, sticky=tk.W, padx=5)
        
        # Temporal smoothing
        temporal_smoothing_check = ttk.Checkbutton(tracking_frame, text="Temporal Smoothing",
                                                   variable=self.temporal_smoothing)
        temporal_smoothing_check.grid(row=8, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(smooths player positions for better stability)", wraplength=280).grid(row=8, column=2, sticky=tk.W, padx=5)
        
        # Process every Nth frame
        ttk.Label(tracking_frame, text="Process Every Nth Frame:").grid(row=9, column=0, sticky=tk.W, padx=5, pady=5)
        process_nth_spinbox = ttk.Spinbox(tracking_frame, from_=1, to=4, increment=1,
                                          textvariable=self.process_every_nth, width=8)
        process_nth_spinbox.grid(row=9, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(1 = all frames, 4 = every 4th frame for 120fps→30fps)", wraplength=280).grid(row=9, column=2, sticky=tk.W, padx=5)
        
        # YOLO Processing Resolution
        ttk.Label(tracking_frame, text="YOLO Resolution:").grid(row=10, column=0, sticky=tk.W, padx=5, pady=5)
        yolo_res_combo = ttk.Combobox(tracking_frame, textvariable=self.yolo_resolution, 
                                     values=["full", "1080p", "720p"], width=10, state="readonly")
        yolo_res_combo.grid(row=10, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(lower = faster, full = best quality)", wraplength=280).grid(row=10, column=2, sticky=tk.W, padx=5)
        
        # Foot-based tracking
        foot_tracking_check = ttk.Checkbutton(tracking_frame, text="Foot-Based Tracking",
                                             variable=self.foot_based_tracking)
        foot_tracking_check.grid(row=11, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(uses foot position as stable anchor)", wraplength=280).grid(row=11, column=2, sticky=tk.W, padx=5)
        
        # Re-ID change handler - disable Harmonic Mean if Re-ID is disabled
        def on_reid_change():
            if not self.use_reid.get():
                # If Re-ID is disabled, disable Harmonic Mean (requires Re-ID)
                if self.use_harmonic_mean.get():
                    self.use_harmonic_mean.set(False)
                    print("  ℹ Re-ID disabled - Harmonic Mean automatically disabled (requires Re-ID)")
                # Warn if using deepocsort (includes Re-ID)
                if self.tracker_type.get() in ["deepocsort", "strongsort", "botsort"]:
                    print(f"  ⚠ Warning: Tracker type '{self.tracker_type.get()}' includes Re-ID features. Consider switching to 'bytetrack' or 'ocsort' for pure tracking without Re-ID.")
        
        # Re-ID (Re-identification)
        reid_check = ttk.Checkbutton(tracking_frame, text="Re-ID (Re-identification)",
                                    variable=self.use_reid, command=on_reid_change)
        reid_check.grid(row=12, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(better ID persistence during occlusions)", wraplength=280).grid(row=12, column=2, sticky=tk.W, padx=5)
        
        # Re-ID similarity threshold
        ttk.Label(tracking_frame, text="Re-ID Similarity Threshold:").grid(row=13, column=0, sticky=tk.W, padx=5, pady=5)
        reid_thresh_spinbox = ttk.Spinbox(tracking_frame, from_=0.25, to=0.9, increment=0.05,
                                         textvariable=self.reid_similarity_threshold, width=8, format="%.2f")
        reid_thresh_spinbox.grid(row=13, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(0.25-0.9, higher = stricter matching, default: 0.55)", wraplength=280).grid(row=13, column=2, sticky=tk.W, padx=5)
        
        # Gallery similarity threshold
        ttk.Label(tracking_frame, text="Gallery Similarity Threshold:").grid(row=14, column=0, sticky=tk.W, padx=5, pady=5)
        gallery_thresh_spinbox = ttk.Spinbox(tracking_frame, from_=0.25, to=0.75, increment=0.05,
                                             textvariable=self.gallery_similarity_threshold, width=8, format="%.2f")
        gallery_thresh_spinbox.grid(row=14, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(0.25-0.75, for cross-video player matching, default: 0.40)", wraplength=280).grid(row=14, column=2, sticky=tk.W, padx=5)
        
        # OSNet variant selection
        ttk.Label(tracking_frame, text="OSNet Variant:").grid(row=15, column=0, sticky=tk.W, padx=5, pady=5)
        osnet_variant_combo = ttk.Combobox(tracking_frame, textvariable=self.osnet_variant,
                                           values=["osnet_x1_0", "osnet_ain_x1_0", "osnet_ibn_x1_0", "osnet_x0_75", "osnet_x0_5", "osnet_x0_25"],
                                           state="readonly", width=15)
        osnet_variant_combo.grid(row=15, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(x1_0: standard, ain: attention, ibn: normalization, x0.75/x0.5/x0.25: lighter)", wraplength=280).grid(row=15, column=2, sticky=tk.W, padx=5)
        
        # BoxMOT optimized backend
        boxmot_backend_check = ttk.Checkbutton(tracking_frame, text="Use BoxMOT Optimized Backend",
                                              variable=self.use_boxmot_backend)
        boxmot_backend_check.grid(row=16, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(ONNX/TensorRT/OpenVINO for faster inference)", wraplength=280).grid(row=16, column=2, sticky=tk.W, padx=5)
        
        # GSI (Gaussian Smoothed Interpolation)
        gsi_check = ttk.Checkbutton(tracking_frame, text="GSI Smoothing (Gaussian Smoothed Interpolation)",
                                   variable=self.use_gsi)
        gsi_check.grid(row=17, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(smoother tracks, fills gaps, requires sklearn)", wraplength=280).grid(row=17, column=2, sticky=tk.W, padx=5)
        
        # GSI parameters (only show if GSI is enabled)
        gsi_params_frame = ttk.Frame(tracking_frame)
        gsi_params_frame.grid(row=18, column=0, columnspan=3, sticky=tk.W, padx=(25, 5), pady=2)
        ttk.Label(gsi_params_frame, text="GSI Interval:").pack(side=tk.LEFT, padx=(0, 5))
        gsi_interval_spinbox = ttk.Spinbox(gsi_params_frame, from_=5, to=50, increment=5,
                                          textvariable=self.gsi_interval, width=6)
        gsi_interval_spinbox.pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(gsi_params_frame, text="GSI Tau:").pack(side=tk.LEFT, padx=(0, 5))
        
        gsi_tau_spinbox = ttk.Spinbox(gsi_params_frame, from_=5.0, to=20.0, increment=1.0,
                                     textvariable=self.gsi_tau, width=6, format="%.1f")
        gsi_tau_spinbox.pack(side=tk.LEFT)
        ttk.Label(gsi_params_frame, text="(interval: max gap to interpolate, tau: smoothing strength)", 
                 font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=(10, 0))
        
        # Advanced Tracking Features (based on academic research)
        ttk.Separator(tracking_frame, orient=tk.HORIZONTAL).grid(row=19, column=0, columnspan=3, sticky=tk.EW, pady=10)
        ttk.Label(tracking_frame, text="Advanced Tracking Features", font=("Arial", 9, "bold")).grid(row=20, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        
        # Harmonic Mean association (Deep HM-SORT)
        # Auto-enables Re-ID when selected (required for Harmonic Mean)
        def on_harmonic_mean_change():
            if self.use_harmonic_mean.get():
                # Auto-enable Re-ID if Harmonic Mean is selected (required for Harmonic Mean)
                if not self.use_reid.get():
                    self.use_reid.set(True)
                    print("  ℹ Harmonic Mean selected - Re-ID automatically enabled (required)")
        
        harmonic_mean_check = ttk.Checkbutton(tracking_frame, text="Use Harmonic Mean Association",
                                             variable=self.use_harmonic_mean, command=on_harmonic_mean_change)
        harmonic_mean_check.grid(row=21, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(Deep HM-SORT: better association decisions - auto-enables Re-ID)", 
                 font=("Arial", 8), foreground="darkblue", wraplength=280).grid(row=21, column=2, sticky=tk.W, padx=5)
        
        # Expansion IOU (Deep HM-SORT)
        expansion_iou_check = ttk.Checkbutton(tracking_frame, text="Use Expansion IOU",
                                             variable=self.use_expansion_iou)
        expansion_iou_check.grid(row=22, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(motion prediction for fast-moving players)", 
                 font=("Arial", 8), foreground="darkblue", wraplength=280).grid(row=22, column=2, sticky=tk.W, padx=5)
        
        # Soccer-specific Re-ID training
        soccer_reid_check = ttk.Checkbutton(tracking_frame, text="Enable Soccer-Specific Re-ID Training",
                                           variable=self.enable_soccer_reid_training)
        soccer_reid_check.grid(row=23, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(prepare data for fine-tuning on soccer players)", 
                 font=("Arial", 8), foreground="darkgreen", wraplength=280).grid(row=23, column=2, sticky=tk.W, padx=5)
        
        # Enhanced Kalman filtering
        enhanced_kalman_check = ttk.Checkbutton(tracking_frame, text="Enhanced Kalman Filtering",
                                                variable=self.use_enhanced_kalman)
        enhanced_kalman_check.grid(row=24, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(additional smoothing layer for jitter reduction)", wraplength=280).grid(row=24, column=2, sticky=tk.W, padx=5)
        
        # EMA smoothing
        ema_smoothing_check = ttk.Checkbutton(tracking_frame, text="EMA Smoothing",
                                              variable=self.use_ema_smoothing)
        ema_smoothing_check.grid(row=25, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(better than simple average, confidence-weighted)", wraplength=280).grid(row=25, column=2, sticky=tk.W, padx=5)
        
        # Confidence filtering
        confidence_filter_check = ttk.Checkbutton(tracking_frame, text="Confidence Filtering",
                                                  variable=self.confidence_filtering)
        confidence_filter_check.grid(row=26, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(filter detections below 0.10 confidence, OFF = keep all detections)", wraplength=280).grid(row=26, column=2, sticky=tk.W, padx=5)
        
        # Adaptive confidence
        adaptive_conf_check = ttk.Checkbutton(tracking_frame, text="Adaptive Confidence Threshold",
                                            variable=self.adaptive_confidence)
        adaptive_conf_check.grid(row=27, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(adjust threshold based on detection consistency)", wraplength=280).grid(row=27, column=2, sticky=tk.W, padx=5)
        
        # Optical Flow
        optical_flow_check = ttk.Checkbutton(tracking_frame, text="Use Optical Flow",
                                            variable=self.use_optical_flow)
        optical_flow_check.grid(row=28, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(motion prediction to reduce tracking blinking, adds ~5-10% overhead)", 
                 font=("Arial", 8), foreground="darkblue", wraplength=280).grid(row=28, column=2, sticky=tk.W, padx=5)
        
        # Velocity Constraints
        velocity_constraints_check = ttk.Checkbutton(tracking_frame, text="Enable Velocity Constraints",
                                                     variable=self.enable_velocity_constraints)
        velocity_constraints_check.grid(row=29, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(prevent impossible jumps in tracking, recommended: ON)", wraplength=280).grid(row=29, column=2, sticky=tk.W, padx=5)
        
        # Enable substitutions
        subs_check = ttk.Checkbutton(tracking_frame, text="Enable Substitution Handling",
                                    variable=self.enable_substitutions)
        subs_check.grid(row=30, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(handle players coming on/off field)", wraplength=280).grid(row=30, column=2, sticky=tk.W, padx=5)
        
        # Re-ID Check Interval
        ttk.Label(tracking_frame, text="Re-ID Check Interval (frames):").grid(row=31, column=0, sticky=tk.W, padx=5, pady=5)
        reid_check_interval_spinbox = ttk.Spinbox(tracking_frame, from_=10, to=120, increment=10,
                                                  textvariable=self.reid_check_interval, width=8)
        reid_check_interval_spinbox.grid(row=31, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(how often to check Re-ID for tracks, default: 30 frames)", wraplength=280).grid(row=31, column=2, sticky=tk.W, padx=5)
        
        # Re-ID Confidence Threshold
        ttk.Label(tracking_frame, text="Re-ID Confidence Threshold:").grid(row=32, column=0, sticky=tk.W, padx=5, pady=5)
        reid_confidence_spinbox = ttk.Spinbox(tracking_frame, from_=0.5, to=0.95, increment=0.05,
                                              textvariable=self.reid_confidence_threshold, width=8, format="%.2f")
        reid_confidence_spinbox.grid(row=32, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(skip Re-ID checks if track confidence above this, default: 0.75)", wraplength=280).grid(row=32, column=2, sticky=tk.W, padx=5)
        
        # Min track length
        ttk.Label(tracking_frame, text="Min Track Length:").grid(row=33, column=0, sticky=tk.W, padx=5, pady=5)
        min_track_length_spinbox = ttk.Spinbox(tracking_frame, from_=1, to=20, increment=1,
                                              textvariable=self.min_track_length, width=8)
        min_track_length_spinbox.grid(row=33, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(frames before track activates, higher = more stable, default: 5)", wraplength=280).grid(row=33, column=2, sticky=tk.W, padx=5)
        
        # Minimum detection size settings
        ttk.Separator(tracking_frame, orient=tk.HORIZONTAL).grid(row=34, column=0, columnspan=3, sticky=tk.EW, pady=10)
        ttk.Label(tracking_frame, text="Minimum Detection Size:", font=("Arial", 9, "bold")).grid(row=35, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(tracking_frame, text="Min Area (px²):").grid(row=36, column=0, sticky=tk.W, padx=5, pady=5)
        min_area_spinbox = ttk.Spinbox(tracking_frame, from_=1, to=2000, increment=1,
                                      textvariable=self.min_bbox_area, width=8)
        min_area_spinbox.grid(row=36, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(minimum bbox area, lower = detect smaller objects, default: 200)", wraplength=280).grid(row=36, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(tracking_frame, text="Min Width (px):").grid(row=37, column=0, sticky=tk.W, padx=5, pady=5)
        min_width_spinbox = ttk.Spinbox(tracking_frame, from_=1, to=100, increment=1,
                                       textvariable=self.min_bbox_width, width=8)
        min_width_spinbox.grid(row=37, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(minimum bbox width, default: 10)", wraplength=280).grid(row=37, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(tracking_frame, text="Min Height (px):").grid(row=38, column=0, sticky=tk.W, padx=5, pady=5)
        min_height_spinbox = ttk.Spinbox(tracking_frame, from_=1, to=100, increment=1,
                                        textvariable=self.min_bbox_height, width=8)
        min_height_spinbox.grid(row=38, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(minimum bbox height, default: 15. Note: 0px height = 0px² area)", wraplength=280).grid(row=38, column=2, sticky=tk.W, padx=5)
        
        # Advanced tracking options
        # Fine-tuning section for occlusion handling and track consistency
        ttk.Separator(tracking_frame, orient=tk.HORIZONTAL).grid(row=39, column=0, columnspan=3, sticky=tk.EW, pady=10)
        fine_tuning_label = ttk.Label(tracking_frame, text="Occlusion & Fine-Tuning Parameters:", 
                                     font=("Arial", 9, "bold"))
        fine_tuning_label.grid(row=40, column=0, columnspan=3, sticky=tk.W, padx=5, pady=(5, 5))
        
        # Occlusion recovery time (seconds)
        ttk.Label(tracking_frame, text="Occlusion Recovery Time (s):").grid(row=41, column=0, sticky=tk.W, padx=5, pady=5)
        occlusion_recovery_spinbox = ttk.Spinbox(tracking_frame, from_=1.0, to=10.0, increment=0.5,
                                                 textvariable=self.occlusion_recovery_seconds, width=8, format="%.1f")
        occlusion_recovery_spinbox.grid(row=41, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(how long to search for disappeared players, default: 3.0s)", wraplength=280).grid(row=41, column=2, sticky=tk.W, padx=5)
        
        # Occlusion recovery distance (pixels)
        ttk.Label(tracking_frame, text="Occlusion Recovery Distance (px):").grid(row=42, column=0, sticky=tk.W, padx=5, pady=5)
        occlusion_distance_spinbox = ttk.Spinbox(tracking_frame, from_=100, to=500, increment=25,
                                                 textvariable=self.occlusion_recovery_distance, width=8)
        occlusion_distance_spinbox.grid(row=42, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(max pixel distance for recovery, default: 250px)", wraplength=280).grid(row=42, column=2, sticky=tk.W, padx=5)
        
        # Separator before Advanced Tracking section
        ttk.Separator(tracking_frame, orient=tk.HORIZONTAL).grid(row=43, column=0, columnspan=3, sticky=tk.EW, pady=10)
        ttk.Label(tracking_frame, text="Advanced Tracking:", font=("Arial", 10, "bold")).grid(row=44, column=0, columnspan=3, sticky=tk.W, padx=5, pady=(5, 5))
        
        # Track referees
        track_refs_check = ttk.Checkbutton(tracking_frame, text="Track Referees & Bench Players",
                                          variable=self.track_referees)
        track_refs_check.grid(row=45, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(include referees and bench players in tracking)", wraplength=280).grid(row=45, column=2, sticky=tk.W, padx=5)
        
        # Max players
        ttk.Label(tracking_frame, text="Max Field Players:").grid(row=46, column=0, sticky=tk.W, padx=5, pady=5)
        max_players_spinbox = ttk.Spinbox(tracking_frame, from_=8, to=20, increment=1,
                                         textvariable=self.max_players, width=8)
        max_players_spinbox.grid(row=46, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(11 players + coach = 12, adjust for substitutions)", wraplength=280).grid(row=46, column=2, sticky=tk.W, padx=5)
        
        # Separator (moved after tracking_frame which is now on row 29)
        # Note: tracking_frame contains many rows internally (up to row 42), so separator goes after it
        separator_row = 31
        ttk.Separator(main_frame, orient="horizontal").grid(
            row=separator_row, column=0, columnspan=3, sticky="ew", pady=15)

        # Control buttons moved to right panel (see right_panel section below)
        
        # Progress bar (check if optimized is available after lazy load)
        # We'll check this dynamically when needed
        progress_row = 32
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, 
                                            maximum=100, length=400)
        self.progress_bar.grid(row=progress_row, column=0, columnspan=3, sticky="ew", 
                              pady=10, padx=5)

        # Status label
        status_row = progress_row + 1
        self.status_label = ttk.Label(main_frame, text="Ready", 
                                     font=("Arial", 10))
        self.status_label.grid(row=status_row, column=0, columnspan=3, pady=10)
        
        # Right side panel for action buttons (scrollable)
        # CRITICAL FIX: Extend right column to full window height by spanning both rows
        right_container = ttk.Frame(main_container)
        right_container.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(10, 0))
        main_container.columnconfigure(1, weight=0)  # Don't expand right panel
        main_container.rowconfigure(1, weight=1)  # Allow notebook to expand vertically
        
        # Create canvas with scrollbar for right panel
        right_canvas = tk.Canvas(right_container, width=250, borderwidth=0, highlightthickness=0)
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
        
        # Make canvas window fill width
        def configure_right_canvas(event):
            canvas_width = event.width
            right_canvas.itemconfig(right_canvas_window, width=canvas_width)
        
        right_canvas.bind("<Configure>", configure_right_canvas)
        
        # Enable mousewheel scrolling for right panel
        def on_right_mousewheel(event):
            right_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel(event):
            right_canvas.bind_all("<MouseWheel>", on_right_mousewheel)
        
        def unbind_mousewheel(event):
            right_canvas.unbind_all("<MouseWheel>")
        
        right_canvas.bind("<Enter>", bind_mousewheel)
        right_canvas.bind("<Leave>", unbind_mousewheel)
        
        # Analysis Controls section (moved from bottom)
        ttk.Label(right_panel, text="Analysis Controls:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.preview_button = ttk.Button(right_panel, text="Preview (15 sec)", 
                                         command=self.preview_analysis, width=20)
        self.preview_button.grid(row=1, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Preview settings
        preview_settings_frame = ttk.Frame(right_panel)
        preview_settings_frame.grid(row=2, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        ttk.Label(preview_settings_frame, text="Preview Frames:", font=("Arial", 8)).pack(side=tk.LEFT, padx=(0, 5))
        preview_frames_spinbox = ttk.Spinbox(preview_settings_frame, from_=60, to=1800, increment=60,
                                            textvariable=self.preview_max_frames, width=8)
        preview_frames_spinbox.pack(side=tk.LEFT)
        ttk.Label(preview_settings_frame, text="(frames)", font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=(5, 0))
        
        self.start_button = ttk.Button(right_panel, text="Start Analysis", 
                                      command=self.start_analysis, width=20)
        self.start_button.grid(row=3, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.stop_button = ttk.Button(right_panel, text="Stop Analysis", 
                                     command=self.stop_analysis, state=tk.DISABLED, width=20)
        self.stop_button.grid(row=4, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Conflict Resolution button (opens Live Viewer Controls)
        self.conflict_resolution_button = ttk.Button(right_panel, text="Open Conflict Resolution", 
                                                    command=self.open_conflict_resolution, width=20)
        self.conflict_resolution_button.grid(row=5, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Analysis & Results section
        ttk.Label(right_panel, text="Analysis & Results:", font=("Arial", 9, "bold")).grid(row=6, column=0, sticky=tk.W, pady=(15, 5))
        
        self.open_folder_button = ttk.Button(right_panel, text="Open Output Folder", 
                                             command=self.open_output_folder, state=tk.DISABLED, width=20)
        self.open_folder_button.grid(row=7, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.analyze_csv_button = ttk.Button(right_panel, text="Analyze CSV Data", 
                                             command=self.analyze_csv, state=tk.NORMAL, width=20)
        self.analyze_csv_button.grid(row=8, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Check if output files exist and enable buttons (after widgets are created)
        self.root.after(100, self._check_and_enable_output_buttons)
        
        self.analytics_selection_button = ttk.Button(right_panel, text="Analytics Selection", 
                                                     command=self.open_analytics_selection, width=20)
        self.analytics_selection_button.grid(row=9, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.setup_checklist_button = ttk.Button(right_panel, text="📋 Setup Checklist", 
                                                 command=self.open_setup_checklist, width=20)
        self.setup_checklist_button.grid(row=10, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.evaluate_hota_button = ttk.Button(right_panel, text="Evaluate Tracking Metrics", 
                                                command=self.evaluate_hota, width=20)
        self.evaluate_hota_button.grid(row=11, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.convert_tracks_button = ttk.Button(right_panel, text="Convert Tracks → Anchor Frames", 
                                                command=self.convert_tracks_to_anchor_frames, width=20)
        self.convert_tracks_button.grid(row=12, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.convert_tags_to_anchors_button = ttk.Button(right_panel, text="Convert Tags → Anchor Frames", 
                                                         command=self.convert_existing_tags_to_anchors, width=20)
        self.convert_tags_to_anchors_button.grid(row=13, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.interactive_learning_button = ttk.Button(right_panel, text="🎓 Interactive Player Learning", 
                                                      command=self.run_interactive_learning, width=20)
        self.interactive_learning_button.grid(row=14, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.fix_anchor_frames_button = ttk.Button(right_panel, text="Fix Failed Anchor Frames", 
                                                    command=self.fix_failed_anchor_frames, width=20)
        self.fix_anchor_frames_button.grid(row=15, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.optimize_anchor_frames_button = ttk.Button(right_panel, text="Optimize Anchor Frames", 
                                                         command=self.optimize_anchor_frames, width=20)
        self.optimize_anchor_frames_button.grid(row=16, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.clear_anchor_frames_button = ttk.Button(right_panel, text="Clear Anchor Frames", 
                                                      command=self.clear_anchor_frames, width=20)
        self.clear_anchor_frames_button.grid(row=17, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.clear_gallery_refs_button = ttk.Button(right_panel, text="Clear Gallery References", 
                                                     command=self.clear_gallery_references, width=20)
        self.clear_gallery_refs_button.grid(row=18, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.track_review_button = ttk.Button(right_panel, text="Track Review & Assign", 
                                             command=self.open_track_review, width=20)
        self.track_review_button.grid(row=19, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.player_stats_button = ttk.Button(right_panel, text="Player Management", 
                                             command=self.open_player_stats, width=20)
        self.player_stats_button.grid(row=20, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # ReID Model Export
        self.export_reid_model_button = ttk.Button(right_panel, text="Export ReID Model", 
                                                   command=self.export_reid_model, width=20)
        self.export_reid_model_button.grid(row=21, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.consolidate_ids_button = ttk.Button(right_panel, text="Consolidate IDs", 
                                                 command=self.open_consolidate_ids, width=20)
        self.consolidate_ids_button.grid(row=22, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Post-Analysis Workflow section
        ttk.Label(right_panel, text="Post-Analysis Workflow:", font=("Arial", 9, "bold")).grid(row=23, column=0, sticky=tk.W, pady=(15, 5))
        
        self.post_analysis_workflow_button = ttk.Button(right_panel, text="🚀 Quick-Start Workflow", 
                                                        command=self.open_post_analysis_workflow, width=20)
        self.post_analysis_workflow_button.grid(row=24, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Setup & Calibration section
        ttk.Label(right_panel, text="Setup & Calibration:", font=("Arial", 9, "bold")).grid(row=25, column=0, sticky=tk.W, pady=(15, 5))
        
        self.ball_color_helper_button = ttk.Button(right_panel, text="Color Helper (Ball & Team)", 
                                                     command=self.open_ball_color_helper, width=20)
        self.ball_color_helper_button.grid(row=26, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Combined color helper replaces both ball and team helpers
        # Team colors are now in the combined helper (Color Helper button)
        
        self.field_calibration_button = ttk.Button(right_panel, text="Calibrate Field", 
                                                    command=self.open_field_calibration, width=20)
        self.field_calibration_button.grid(row=27, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.setup_wizard_button = ttk.Button(right_panel, text="Setup Wizard", 
                                              command=self.open_setup_wizard, width=20)
        self.setup_wizard_button.grid(row=28, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Player Gallery section (NEW!)
        ttk.Label(right_panel, text="Player Gallery:", font=("Arial", 9, "bold")).grid(row=29, column=0, sticky=tk.W, pady=(15, 5))
        
        self.player_gallery_seeder_button = ttk.Button(right_panel, text="Tag Players (Gallery)", 
                                                       command=self.open_player_gallery_seeder, width=20)
        self.player_gallery_seeder_button.grid(row=30, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Info label about gallery integration
        ttk.Label(right_panel, text="(Gallery view integrated in Player Management)", 
                 foreground="gray", font=("Arial", 7)).grid(row=31, column=0, sticky=tk.W, padx=5, pady=2)
        
        # Video Tools section
        ttk.Label(right_panel, text="Video Tools:", font=("Arial", 9, "bold")).grid(row=32, column=0, sticky=tk.W, pady=(15, 5))
        
        self.video_splicer_button = ttk.Button(right_panel, text="Video Splicer", 
                                               command=self.open_video_splicer, width=20)
        self.video_splicer_button.grid(row=33, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Viewers section
        ttk.Label(right_panel, text="Viewers:", font=("Arial", 9, "bold")).grid(row=34, column=0, sticky=tk.W, pady=(15, 5))
        
        self.playback_viewer_button = ttk.Button(right_panel, text="Playback Viewer", 
                                                 command=self.open_playback_viewer, width=20)
        self.playback_viewer_button.grid(row=35, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.speed_tracking_button = ttk.Button(right_panel, text="Speed Tracking", 
                                                 command=self.open_speed_tracking, width=20)
        self.speed_tracking_button.grid(row=36, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Project management section
        ttk.Label(right_panel, text="Project Management:", font=("Arial", 9, "bold")).grid(row=37, column=0, sticky=tk.W, pady=(15, 5))
        
        self.create_project_button = ttk.Button(right_panel, text="Create New Project", 
                                               command=self.create_new_project, width=20)
        self.create_project_button.grid(row=38, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.save_project_button = ttk.Button(right_panel, text="Save Project", 
                                              command=self.save_project, width=20)
        self.save_project_button.grid(row=39, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.load_project_button = ttk.Button(right_panel, text="Load Project", 
                                              command=self.load_project, width=20)
        self.load_project_button.grid(row=40, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.save_project_as_button = ttk.Button(right_panel, text="Save Project As...", 
                                                 command=self.save_project_as, width=20)
        self.save_project_as_button.grid(row=41, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        self.rename_project_button = ttk.Button(right_panel, text="Rename Project", 
                                                command=self.rename_project, width=20)
        self.rename_project_button.grid(row=42, column=0, padx=5, pady=3, sticky=tk.W+tk.E)
        
        # Configure right panel column to expand buttons
        right_panel.columnconfigure(0, weight=1)
        
        # Log output (in main_frame on left side)
        log_row = status_row + 1
        log_label = ttk.Label(main_frame, text="Processing Log:", 
                             font=("Arial", 10, "bold"))
        log_label.grid(row=log_row, column=0, columnspan=3, sticky=tk.W, pady=(10, 5))
        
        log_text_row = log_row + 1
        self.log_text = scrolledtext.ScrolledText(main_frame, height=12, width=60, 
                                                  wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=log_text_row, column=0, columnspan=3, sticky="nsew", 
                          pady=5)
        main_frame.rowconfigure(log_text_row, weight=1)  # Make log area expandable
        
        # Add extra padding at bottom to extend past "Ready"
        bottom_padding = ttk.Frame(main_frame, height=20)
        bottom_padding.grid(row=log_text_row + 1, column=0, columnspan=3, sticky="ew")
        
    def browse_input_file(self):
        filename = filedialog.askopenfilename(
            title="Select Input Video",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v *.mpg *.mpeg"), ("MOV files", "*.mov"), ("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        if filename:
            self.input_file.set(filename)
            # Auto-generate output filename
            if not self.output_file.get():
                base_name = os.path.splitext(filename)[0]
                self.output_file.set(f"{base_name}_analyzed.mp4")
            self.log_message(f"Selected input: {filename}")
            # Check if output files exist and enable buttons
            self._check_and_enable_output_buttons()
    
    def browse_output_file(self):
        filename = filedialog.asksaveasfilename(
            title="Save Output Video As",
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        if filename:
            self.output_file.set(filename)
            self.log_message(f"Output will be saved to: {filename}")
            # Check if output files exist and enable buttons
            self._check_and_enable_output_buttons()
    
    def browse_anchor_file(self):
        """Browse for PlayerTagsSeed anchor file"""
        filename = filedialog.askopenfilename(
            title="Select PlayerTagsSeed File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.explicit_anchor_file.set(filename)
            self.log_message(f"Selected anchor file: {filename}")
    
    def log_message(self, message):
        """Add message to log output"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
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
        response = messagebox.askyesno("Preview Analysis", 
                                      f"Preview will process 15 seconds (360 frames at 24fps) of your video.\n\n"
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
            pass  # Module not available, that's okay
        
        # Start preview in separate thread
        self.processing = True
        self.start_button.config(state=tk.DISABLED)
        self.preview_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.status_label.config(text="Previewing...")
        
        preview_thread = threading.Thread(target=self.run_preview_analysis, args=(preview_output,), daemon=True)
        preview_thread.start()
    
    def run_preview_analysis(self, preview_output):
        """Run preview analysis on a small sample"""
        try:
            import cv2
            
            # Load analysis module if not already loaded
            if not load_analysis_module():
                self.root.after(0, self.preview_complete, False, "Failed to load analysis module")
                return
            
            # Preview mode requires optimized version
            if not OPTIMIZED_AVAILABLE:
                self.root.after(0, self.preview_complete, False, "Preview mode requires optimized analysis. Please ensure combined_analysis_optimized.py is available.")
                return
            
            # Get video info to determine preview length
            cap = cv2.VideoCapture(self.input_file.get())
            if not cap.isOpened():
                self.root.after(0, self.preview_complete, False, "Could not open video file")
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
            # Preview mode always uses optimized analysis (it's required for preview)
            # combined_analysis is actually combined_analysis_optimized when OPTIMIZED_AVAILABLE is True
            # pyright: ignore - function signature is dynamically loaded, all parameters are valid
            # type: ignore - suppress parameter errors for dynamically loaded function
            combined_analysis(  # type: ignore
                    input_path=self.input_file.get(),
                    output_path=preview_output,
                    dewarp=self.dewarp_enabled.get(),
                    track_ball_flag=self.ball_tracking_enabled.get(),
                    track_players_flag=self.player_tracking_enabled.get(),
                    export_csv=self.csv_export_enabled.get(),  # Respect GUI setting (CSV export slows preview significantly)
                    use_imperial_units=self.use_imperial_units.get(),  # type: ignore
                    buffer=self.buffer_size.get(),
                    batch_size=self.batch_size.get(),  # type: ignore
                    ball_min_radius=self.ball_min_radius.get(),  # type: ignore
                    ball_max_radius=self.ball_max_radius.get(),  # type: ignore
                    remove_net=self.remove_net_enabled.get(),  # type: ignore
                    show_ball_trail=self.show_ball_trail.get(),  # type: ignore
                    track_thresh=self.track_thresh.get(),  # type: ignore
                    match_thresh=self.match_thresh.get(),  # type: ignore
                    track_buffer=self.track_buffer.get(),  # type: ignore
                    track_buffer_seconds=self.track_buffer_seconds.get(),  # type: ignore
                    min_track_length=self.min_track_length.get(),  # type: ignore
                    min_bbox_area=self.min_bbox_area.get(),  # type: ignore
                    min_bbox_width=self.min_bbox_width.get(),  # type: ignore
                    min_bbox_height=self.min_bbox_height.get(),  # type: ignore
                    tracker_type=self.tracker_type.get(),  # type: ignore
                    viz_style=self.viz_style.get(),  # type: ignore
                    viz_color_mode=self.viz_color_mode.get(),  # type: ignore
                    preserve_audio=False,  # Skip audio for faster preview  # type: ignore
                    video_fps=fps,  # type: ignore
                    output_fps=fps,  # type: ignore
                    process_every_nth_frame=self.process_every_nth.get(),  # type: ignore
                    temporal_smoothing=self.temporal_smoothing.get(),  # type: ignore
                    yolo_resolution=self.yolo_resolution.get(),  # type: ignore
                    foot_based_tracking=self.foot_based_tracking.get(),  # type: ignore
                    use_reid=self.use_reid.get(),  # type: ignore
                    reid_similarity_threshold=self.reid_similarity_threshold.get(),  # type: ignore
                    gallery_similarity_threshold=self.gallery_similarity_threshold.get(),  # type: ignore
                    osnet_variant=self.osnet_variant.get(),  # type: ignore
                    use_boxmot_backend=self.use_boxmot_backend.get(),  # type: ignore
                    occlusion_recovery_seconds=self.occlusion_recovery_seconds.get(),  # type: ignore
                    occlusion_recovery_distance=self.occlusion_recovery_distance.get(),  # type: ignore
                    reid_check_interval=self.reid_check_interval.get(),  # type: ignore
                    reid_confidence_threshold=self.reid_confidence_threshold.get(),  # type: ignore
                    use_harmonic_mean=self.use_harmonic_mean.get(),  # type: ignore
                    use_expansion_iou=self.use_expansion_iou.get(),  # type: ignore
                    enable_soccer_reid_training=self.enable_soccer_reid_training.get(),  # type: ignore
                    use_enhanced_kalman=self.use_enhanced_kalman.get(),  # type: ignore
                    use_ema_smoothing=self.use_ema_smoothing.get(),  # type: ignore
                    confidence_filtering=self.confidence_filtering.get(),  # type: ignore
                    adaptive_confidence=self.adaptive_confidence.get(),  # type: ignore
                    use_optical_flow=self.use_optical_flow.get(),  # type: ignore
                    enable_velocity_constraints=self.enable_velocity_constraints.get(),  # type: ignore
                    track_referees=self.track_referees.get(),  # type: ignore
                    max_players=self.max_players.get(),  # type: ignore
                    enable_substitutions=self.enable_substitutions.get(),  # type: ignore
                    ellipse_width=self.ellipse_width.get(),  # type: ignore
                    ellipse_height=self.ellipse_height.get(),  # type: ignore
                    ellipse_outline_thickness=self.ellipse_outline_thickness.get(),  # type: ignore
                    show_ball_possession=self.show_ball_possession.get(),  # type: ignore
                    box_shrink_factor=self.box_shrink_factor.get(),  # type: ignore
                    show_player_labels=self.show_player_labels.get(),  # type: ignore
                    show_yolo_boxes=self.show_yolo_boxes.get(),  # type: ignore
                    label_font_scale=self.label_font_scale.get(),  # type: ignore
                    label_type=self.label_type.get(),  # type: ignore
                    label_custom_text=self.label_custom_text.get(),  # type: ignore
                    label_font_face=self.label_font_face.get(),  # type: ignore
                    show_predicted_boxes=self.show_predicted_boxes.get(),  # type: ignore
                    prediction_duration=self.prediction_duration.get(),  # type: ignore
                    prediction_style=self.prediction_style.get(),  # Style: "dot", "box", "cross", "x", "arrow", "diamond"  # type: ignore
                    prediction_size=self.prediction_size.get(),  # type: ignore
                    prediction_color=(self.prediction_color_b.get(), self.prediction_color_g.get(), self.prediction_color_r.get()),  # type: ignore
                    player_viz_alpha=self.player_viz_alpha.get(),  # Opacity for player boxes/ellipses (0-255)  # type: ignore
                    trail_length=self.trail_length.get(),  # type: ignore
                    trail_buffer=self.trail_buffer.get(),  # type: ignore
                    use_yolo_streaming=self.use_yolo_streaming.get(),  # type: ignore
                    box_thickness=self.box_thickness.get(),  # Box border thickness  # type: ignore
                    box_color=self._get_box_color_bgr() if self.use_custom_box_color.get() else None,  # Custom box color in BGR format  # type: ignore
                    label_color=self._get_label_color() if self.use_custom_label_color.get() else None,  # Custom label color in BGR format  # type: ignore
                    show_bounding_boxes=self.show_bounding_boxes.get(),  # Show bounding boxes (separate from circles)  # type: ignore
                    show_circles_at_feet=self.show_circles_at_feet.get(),  # Show team-colored circles at feet  # type: ignore
                    # Enhanced feet marker visualization
                    feet_marker_style=self.feet_marker_style.get(),  # Style: "circle", "diamond", "star", "hexagon", "ring", "glow", "pulse"  # type: ignore
                    feet_marker_opacity=self.feet_marker_opacity.get(),  # Opacity for feet markers (0-255)  # type: ignore
                    feet_marker_enable_glow=self.feet_marker_enable_glow.get(),  # Enable glow effect  # type: ignore
                    feet_marker_glow_intensity=self.feet_marker_glow_intensity.get(),  # Glow intensity (0-100)  # type: ignore
                    feet_marker_enable_shadow=self.feet_marker_enable_shadow.get(),  # Enable shadow effect  # type: ignore
                    feet_marker_shadow_offset=self.feet_marker_shadow_offset.get(),  # Shadow offset in pixels  # type: ignore
                    feet_marker_shadow_opacity=self.feet_marker_shadow_opacity.get(),  # Shadow opacity (0-255)  # type: ignore
                    feet_marker_enable_gradient=self.feet_marker_enable_gradient.get(),  # Enable gradient fill  # type: ignore
                    feet_marker_enable_pulse=self.feet_marker_enable_pulse.get(),  # Enable pulse animation  # type: ignore
                    feet_marker_pulse_speed=self.feet_marker_pulse_speed.get(),  # Pulse animation speed (cycles/sec)  # type: ignore
                    feet_marker_enable_particles=self.feet_marker_enable_particles.get(),  # Enable particle effects  # type: ignore
                    feet_marker_particle_count=self.feet_marker_particle_count.get(),  # Number of particles  # type: ignore
                    feet_marker_vertical_offset=self.feet_marker_vertical_offset.get(),  # Vertical offset in pixels  # type: ignore
                    # Broadcast-level graphics settings
                    trajectory_smoothness=self.trajectory_smoothness.get(),  # "linear", "bezier", "spline"  # type: ignore
                    player_graphics_style=self.player_graphics_style.get(),  # "minimal", "standard", "broadcast"  # type: ignore
                    use_rounded_corners=self.use_rounded_corners.get(),  # Use rounded corners  # type: ignore
                    use_gradient_fill=self.use_gradient_fill.get(),  # Use gradient fill  # type: ignore
                    corner_radius=self.corner_radius.get(),  # Corner radius for rounded rectangles  # type: ignore
                    show_jersey_badge=self.show_jersey_badge.get(),  # Show jersey number badge  # type: ignore
                    ball_graphics_style=self.ball_graphics_style.get(),  # "standard", "broadcast"  # type: ignore
                    show_statistics=self.show_statistics.get(),  # Show statistics overlay  # type: ignore
                    statistics_position=self.statistics_position.get(),  # Statistics panel position  # type: ignore
                    show_heat_map=self.show_heat_map.get(),  # Show heat map  # type: ignore
                    heat_map_alpha=self.heat_map_alpha.get(),  # Heat map opacity  # type: ignore
                    heat_map_color_scheme=self.heat_map_color_scheme.get(),  # Heat map color scheme  # type: ignore
                    overlay_quality_preset=self.overlay_quality_preset.get(),  # Quality preset  # type: ignore
                    viz_settings_override={  # Statistics panel customization  # type: ignore
                        "statistics_panel_size": (self.statistics_panel_width.get(), self.statistics_panel_height.get()),
                        "statistics_bg_alpha": self.statistics_bg_alpha.get(),
                        "statistics_bg_color": self._get_statistics_bg_color_bgr(),  # BGR
                        "statistics_text_color": self._get_statistics_text_color_bgr(),  # BGR
                        "statistics_title_color": self._get_statistics_title_color_bgr(),  # BGR
                    },
                    preview_mode=True,  # Enable preview mode  # type: ignore
                    preview_max_frames=preview_frames,  # Limit to preview frames  # type: ignore
                    watch_only=self.watch_only.get(),  # Watch-only mode: learn without saving video  # type: ignore
                    show_live_viewer=self.show_live_viewer.get(),  # Show live viewer during watch-only mode  # type: ignore
                    focused_players=[self.focused_player] if (self.watch_only.get() and self.focus_players_enabled.get() and self.focused_player) else None,  # Focus on specific player  # type: ignore
                    save_base_video=self.save_base_video.get(),  # Save base video without overlays  # type: ignore
                    export_overlay_metadata=self.export_overlay_metadata.get(),  # Export overlay metadata  # type: ignore
                    enable_video_encoding=self.enable_video_encoding.get(),  # Enable video encoding  # type: ignore
                    overlay_quality=self.overlay_quality.get(),  # Overlay quality: "sd", "hd", "4k"  # type: ignore
                    render_scale=self.render_scale.get(),  # Render scale multiplier for HD overlays  # type: ignore
                    enable_advanced_blending=self.enable_advanced_blending.get(),  # Enable advanced blending modes  # type: ignore
                    enable_motion_blur=self.enable_motion_blur.get(),  # Enable motion blur  # type: ignore
                    motion_blur_amount=self.motion_blur_amount.get(),  # Motion blur intensity  # type: ignore
                    use_professional_text=self.use_professional_text.get(),  # Use PIL-based text rendering  # type: ignore
                    progress_callback=self.update_progress  # Progress callback for GUI updates  # type: ignore
                )
            
            # Update UI on completion
            self.root.after(0, self.preview_complete, True, preview_output)
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            error_msg = f"Error during preview: {str(e)}"
            self.log_message(error_msg)
            self.log_message("Full traceback:")
            self.log_message(error_traceback)
            # Show full error in message box for debugging
            self.root.after(0, self.preview_complete, False, f"{error_msg}\n\nFull error:\n{error_traceback}")
    
    def preview_complete(self, success, message_or_path):
        """Called when preview completes"""
        self.processing = False
        self.start_button.config(state=tk.NORMAL)
        self.preview_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_var.set(100)
        
        if success:
            preview_path = message_or_path
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
                    # Open in playback viewer (not external player)
                    self.open_in_playback_viewer(preview_path)
        else:
            self.status_label.config(text="Preview error")
            messagebox.showerror("Preview Error", message_or_path)
    
    def start_analysis(self):
        """Start the analysis process in a separate thread"""
        if not self.validate_inputs():
            return
        
        if self.processing:
            messagebox.showinfo("Info", "Analysis is already in progress.")
            return
        
        # Check for field calibration if ball tracking is enabled
        if self.ball_tracking_enabled.get():
            calibration_exists = (os.path.exists("field_calibration.json") or 
                                 (os.path.exists("calibration.npy") and 
                                  os.path.exists("calibration_metadata.npy")))
            
            if not calibration_exists:
                response = messagebox.askyesno(
                    "Field Calibration Not Found",
                    "Field calibration not found. This helps filter out sideline balls.\n\n"
                    "Would you like to:\n"
                    "• Calibrate field now (recommended for better ball tracking)\n"
                    "• Continue without calibration (less accurate)\n\n"
                    "Click 'Yes' to calibrate field, or 'No' to continue without it."
                )
                if response:
                    # Open field calibration tool
                    self.open_field_calibration()
                    return  # User will need to start analysis again after calibration
        
        # Check for batch processing
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
            batch_thread = threading.Thread(target=self._run_batch_focus_analysis, 
                                            args=(video_path, active_players),
                                            daemon=True)
            batch_thread.start()
            return
        
        # Disable start button, enable stop button
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.open_folder_button.config(state=tk.DISABLED)
        # analyze_csv_button stays enabled - users can analyze any CSV file
        self.processing = True
        self.progress_var.set(0)
        self.status_label.config(text="Processing...")
        
        # Initialize progress tracker if available
        if QUICK_WINS_AVAILABLE:
            self.progress_tracker = ProgressTracker(
                total=100,  # Will be updated with actual frame count
                label=self.status_label,
                progress_bar=self.progress_bar
            )
        
        # Clear log
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
        self.log_message(f"Preserve Audio: {self.preserve_audio.get()}")
        self.log_message(f"Ball Trail Length: {self.buffer_size.get()}")
        self.log_message(f"Ball Size Range: {self.ball_min_radius.get()}-{self.ball_max_radius.get()} pixels")
        # Load module to check if optimized is available
        load_analysis_module()
        if OPTIMIZED_AVAILABLE:
            self.log_message(f"YOLO Batch Size: {self.batch_size.get()}")
        self.log_message("=" * 60)
        
        # Clear any previous stop requests
        try:
            import shared_state
            shared_state.clear_analysis_stop()
        except ImportError:
            pass
        
        # Start analysis in separate thread
        self.process_thread = threading.Thread(target=self.run_analysis, daemon=True)
        self.process_thread.start()
        
        # Launch live viewer controls window if:
        # 1. Watch-only mode with live viewer is enabled
        # NOTE: Conflict resolution is NOT auto-launched - use "Open Conflict Resolution" button manually
        should_launch = False
        launch_reason = ""
        
        if self.watch_only.get() and self.show_live_viewer.get():
            should_launch = True
            launch_reason = "Watch-only mode with live viewer enabled"
        
        if should_launch:
            self.log_message(f"📺 {launch_reason} - will launch controls window")
            self.log_message(f"   → Watch-only checkbox: {self.watch_only.get()}")
            self.log_message(f"   → Show live viewer checkbox: {self.show_live_viewer.get() if hasattr(self, 'show_live_viewer') else 'N/A'}")
            self.log_message(f"   → Track players checkbox: {self.player_tracking_enabled.get()}")
            self.log_message("   → Waiting for analysis to initialize (this may take a few seconds)...")
            # Wait longer for dynamic_settings to be initialized (analysis needs to start first)
            # Analysis startup can take 5-10 seconds (loading models, etc.)
            # Try multiple times with increasing delays
            self.live_viewer_retry_count = 0
            self.live_viewer_max_retries = 30  # Increased to 30 seconds for slower systems
            # Start with 3 second delay to give analysis time to initialize
            # The analysis thread needs to: load models, initialize dynamic_settings, etc.
            self.root.after(3000, self.launch_live_viewer_controls)
        else:
            # Debug: log why window isn't launching
            if not self.watch_only.get() and not self.player_tracking_enabled.get():
                self.log_message("ℹ Live viewer not launching: watch-only mode and player tracking are both disabled")
            elif self.watch_only.get() and not (hasattr(self, 'show_live_viewer') and self.show_live_viewer.get()):
                self.log_message("ℹ Enable 'Show Live Viewer' checkbox to see live viewer during watch-only mode")
            elif not self.watch_only.get() and self.player_tracking_enabled.get():
                self.log_message("ℹ Conflict resolution available - use 'Open Conflict Resolution' button to open manually")
    
    def update_progress(self, frame_count, total_frames, progress_pct):
        """Update progress bar (called from analysis thread)"""
        self.root.after(0, lambda: self.progress_var.set(int(progress_pct)))
        
        # Use ProgressTracker if available for enhanced progress display
        if QUICK_WINS_AVAILABLE and hasattr(self, 'progress_tracker') and self.progress_tracker:
            # Update total if it changed
            if self.progress_tracker.total != total_frames:
                self.progress_tracker.total = total_frames
            
            # Update progress with message
            message = f"Processing frame {frame_count} of {total_frames}"
            self.root.after(0, lambda: self.progress_tracker.update(frame_count, message))
        else:
            # Fallback to basic progress display
            self.root.after(0, lambda: self.status_label.config(text=f"Processing... {int(progress_pct)}% ({frame_count}/{total_frames} frames)"))
    
    def run_analysis(self):
        """Run the analysis (called in separate thread)"""
        try:
            # Load analysis module if not already loaded
            if not load_analysis_module():
                self.root.after(0, self.analysis_complete, False, "Failed to load analysis module")
                return
            
            # Call the combined analysis function
            if OPTIMIZED_AVAILABLE:
                # Use optimized version with batch processing
                # pyright: ignore - function signature is dynamically loaded, all parameters are valid
                # type: ignore - suppress parameter errors for dynamically loaded function
                combined_analysis(  # type: ignore
                    input_path=self.input_file.get(),
                    output_path=self.output_file.get(),
                    dewarp=self.dewarp_enabled.get(),
                    track_ball_flag=self.ball_tracking_enabled.get(),
                    track_players_flag=self.player_tracking_enabled.get(),
                    export_csv=self.csv_export_enabled.get(),
                    use_imperial_units=self.use_imperial_units.get(),  # type: ignore
                    buffer=self.buffer_size.get(),
                    batch_size=self.batch_size.get(),  # type: ignore
                    ball_min_radius=self.ball_min_radius.get(),  # type: ignore
                    ball_max_radius=self.ball_max_radius.get(),  # type: ignore
                    show_live_viewer=self.show_live_viewer.get() if hasattr(self, 'show_live_viewer') else False,  # type: ignore
                    remove_net=self.remove_net_enabled.get(),  # type: ignore
                    show_ball_trail=self.show_ball_trail.get(),  # type: ignore
                    track_thresh=self.track_thresh.get(),  # type: ignore
                    match_thresh=self.match_thresh.get(),  # type: ignore
                    track_buffer=self.track_buffer.get(),  # type: ignore
                    track_buffer_seconds=self.track_buffer_seconds.get(),  # type: ignore
                    min_track_length=self.min_track_length.get(),  # type: ignore
                    tracker_type=self.tracker_type.get(),  # type: ignore
                    video_fps=self.video_fps.get() if self.video_fps.get() > 0 else None,  # type: ignore
                    output_fps=self.output_fps.get() if self.output_fps.get() > 0 else None,  # type: ignore
                    temporal_smoothing=self.temporal_smoothing.get(),  # type: ignore
                    process_every_nth_frame=self.process_every_nth.get(),  # type: ignore
                    yolo_resolution=self.yolo_resolution.get(),  # type: ignore
                    foot_based_tracking=self.foot_based_tracking.get(),  # type: ignore
                    use_reid=self.use_reid.get(),  # type: ignore
                    reid_similarity_threshold=self.reid_similarity_threshold.get(),  # type: ignore
                    gallery_similarity_threshold=self.gallery_similarity_threshold.get(),  # type: ignore
                    osnet_variant=self.osnet_variant.get(),  # type: ignore
                    use_boxmot_backend=self.use_boxmot_backend.get(),  # type: ignore
                    occlusion_recovery_seconds=self.occlusion_recovery_seconds.get(),  # type: ignore
                    occlusion_recovery_distance=self.occlusion_recovery_distance.get(),  # type: ignore
                    reid_check_interval=self.reid_check_interval.get(),  # type: ignore
                    reid_confidence_threshold=self.reid_confidence_threshold.get(),  # type: ignore
                    use_harmonic_mean=self.use_harmonic_mean.get(),  # type: ignore
                    use_expansion_iou=self.use_expansion_iou.get(),  # type: ignore
                    enable_soccer_reid_training=self.enable_soccer_reid_training.get(),  # type: ignore
                    use_enhanced_kalman=self.use_enhanced_kalman.get(),  # type: ignore
                    use_ema_smoothing=self.use_ema_smoothing.get(),  # type: ignore
                    confidence_filtering=self.confidence_filtering.get(),  # type: ignore
                    adaptive_confidence=self.adaptive_confidence.get(),  # type: ignore
                    use_optical_flow=self.use_optical_flow.get(),  # type: ignore
                    enable_velocity_constraints=self.enable_velocity_constraints.get(),  # type: ignore
                    track_referees=self.track_referees.get(),  # type: ignore
                    max_players=self.max_players.get(),  # type: ignore
                    enable_substitutions=self.enable_substitutions.get(),  # type: ignore
                    viz_style=self.viz_style.get(),  # type: ignore
                    viz_color_mode=self.viz_color_mode.get(),  # type: ignore
                    ellipse_width=self.ellipse_width.get(),  # type: ignore
                    ellipse_height=self.ellipse_height.get(),  # type: ignore
                    ellipse_outline_thickness=self.ellipse_outline_thickness.get(),  # type: ignore
                    show_ball_possession=self.show_ball_possession.get(),  # type: ignore
                    box_shrink_factor=self.box_shrink_factor.get(),  # type: ignore
                    show_player_labels=self.show_player_labels.get(),  # type: ignore
                    show_yolo_boxes=self.show_yolo_boxes.get(),  # type: ignore
                    label_font_scale=self.label_font_scale.get(),  # type: ignore
                    label_type=self.label_type.get(),  # type: ignore
                    label_custom_text=self.label_custom_text.get(),  # type: ignore
                    label_font_face=self.label_font_face.get(),  # type: ignore
                    show_predicted_boxes=self.show_predicted_boxes.get(),  # Show predicted boxes for lost tracks  # type: ignore
                    prediction_duration=self.prediction_duration.get(),  # Prediction duration in seconds  # type: ignore
                    prediction_style=self.prediction_style.get(),  # Style: "dot", "box", "cross", "x", "arrow", "diamond"  # type: ignore
                    prediction_size=self.prediction_size.get(),  # Size of predicted markers  # type: ignore
                    prediction_color=(self.prediction_color_b.get(), self.prediction_color_g.get(), self.prediction_color_r.get()),  # Color of predicted markers  # type: ignore
                    trail_length=self.trail_length.get(),  # Number of trail points to display  # type: ignore
                    trail_buffer=self.trail_buffer.get(),  # Trail buffer size  # type: ignore
                    use_yolo_streaming=self.use_yolo_streaming.get(),  # type: ignore
                    preserve_audio=self.preserve_audio.get(),  # Preserve audio from original video  # type: ignore
                    box_thickness=self.box_thickness.get(),  # Box border thickness  # type: ignore
                    box_color=self._get_box_color_bgr() if self.use_custom_box_color.get() else None,  # Custom box color in BGR format  # type: ignore
                    label_color=self._get_label_color() if self.use_custom_label_color.get() else None,  # Custom label color in BGR format  # type: ignore
                    player_viz_alpha=self.player_viz_alpha.get(),  # Opacity for player boxes/ellipses (0-255)  # type: ignore
                    show_bounding_boxes=self.show_bounding_boxes.get(),  # Show bounding boxes (separate from circles)  # type: ignore
                    show_circles_at_feet=self.show_circles_at_feet.get(),  # Show team-colored circles at feet  # type: ignore
                    # Enhanced feet marker visualization
                    feet_marker_style=self.feet_marker_style.get(),  # Style: "circle", "diamond", "star", "hexagon", "ring", "glow", "pulse"  # type: ignore
                    feet_marker_opacity=self.feet_marker_opacity.get(),  # Opacity for feet markers (0-255)  # type: ignore
                    feet_marker_enable_glow=self.feet_marker_enable_glow.get(),  # Enable glow effect  # type: ignore
                    feet_marker_glow_intensity=self.feet_marker_glow_intensity.get(),  # Glow intensity (0-100)  # type: ignore
                    feet_marker_enable_shadow=self.feet_marker_enable_shadow.get(),  # Enable shadow effect  # type: ignore
                    feet_marker_shadow_offset=self.feet_marker_shadow_offset.get(),  # Shadow offset in pixels  # type: ignore
                    feet_marker_shadow_opacity=self.feet_marker_shadow_opacity.get(),  # Shadow opacity (0-255)  # type: ignore
                    feet_marker_enable_gradient=self.feet_marker_enable_gradient.get(),  # Enable gradient fill  # type: ignore
                    feet_marker_enable_pulse=self.feet_marker_enable_pulse.get(),  # Enable pulse animation  # type: ignore
                    feet_marker_pulse_speed=self.feet_marker_pulse_speed.get(),  # Pulse animation speed (cycles/sec)  # type: ignore
                    feet_marker_enable_particles=self.feet_marker_enable_particles.get(),  # Enable particle effects  # type: ignore
                    feet_marker_particle_count=self.feet_marker_particle_count.get(),  # Number of particles  # type: ignore
                    feet_marker_vertical_offset=self.feet_marker_vertical_offset.get(),  # Vertical offset in pixels  # type: ignore
                    # Broadcast-level graphics settings
                    trajectory_smoothness=self.trajectory_smoothness.get(),  # "linear", "bezier", "spline"  # type: ignore
                    player_graphics_style=self.player_graphics_style.get(),  # "minimal", "standard", "broadcast"  # type: ignore
                    use_rounded_corners=self.use_rounded_corners.get(),  # Use rounded corners  # type: ignore
                    use_gradient_fill=self.use_gradient_fill.get(),  # Use gradient fill  # type: ignore
                    corner_radius=self.corner_radius.get(),  # Corner radius for rounded rectangles  # type: ignore
                    show_jersey_badge=self.show_jersey_badge.get(),  # Show jersey number badge  # type: ignore
                    ball_graphics_style=self.ball_graphics_style.get(),  # "standard", "broadcast"  # type: ignore
                    show_statistics=self.show_statistics.get(),  # Show statistics overlay  # type: ignore
                    statistics_position=self.statistics_position.get(),  # Statistics panel position  # type: ignore
                    show_heat_map=self.show_heat_map.get(),  # Show heat map  # type: ignore
                    heat_map_alpha=self.heat_map_alpha.get(),  # Heat map opacity  # type: ignore
                    heat_map_color_scheme=self.heat_map_color_scheme.get(),  # Heat map color scheme  # type: ignore
                    overlay_quality_preset=self.overlay_quality_preset.get(),  # Quality preset  # type: ignore
                    viz_settings_override={  # Statistics panel customization  # type: ignore
                        "statistics_panel_size": (self.statistics_panel_width.get(), self.statistics_panel_height.get()),
                        "statistics_bg_alpha": self.statistics_bg_alpha.get(),
                        "statistics_bg_color": self._get_statistics_bg_color_bgr(),  # BGR
                        "statistics_text_color": self._get_statistics_text_color_bgr(),  # BGR
                        "statistics_title_color": self._get_statistics_title_color_bgr(),  # BGR
                    },
                    watch_only=self.watch_only.get(),  # Watch-only mode: learn without saving video  # type: ignore
                    video_type=self.video_type.get(),  # "practice" or "game" - controls team locking behavior  # type: ignore
                    focused_players=[self.focused_player] if (self.watch_only.get() and self.focus_players_enabled.get() and self.focused_player) else None,  # Focus on specific player  # type: ignore
                    save_base_video=self.save_base_video.get(),  # Save base video without overlays  # type: ignore
                    export_overlay_metadata=self.export_overlay_metadata.get(),  # Export overlay metadata  # type: ignore
                    enable_video_encoding=self.enable_video_encoding.get(),  # Enable video encoding  # type: ignore
                    overlay_quality=self.overlay_quality.get(),  # Overlay quality: "sd", "hd", "4k"  # type: ignore
                    render_scale=self.render_scale.get(),  # Render scale multiplier for HD overlays  # type: ignore
                    enable_advanced_blending=self.enable_advanced_blending.get(),  # Enable advanced blending modes  # type: ignore
                    enable_motion_blur=self.enable_motion_blur.get(),  # Enable motion blur  # type: ignore
                    motion_blur_amount=self.motion_blur_amount.get(),  # Motion blur intensity  # type: ignore
                    use_professional_text=self.use_professional_text.get(),  # Use PIL-based text rendering  # type: ignore
                    explicit_anchor_file=self.explicit_anchor_file.get() if hasattr(self, 'explicit_anchor_file') and self.explicit_anchor_file.get() else None  # Optional explicit anchor file path  # type: ignore
                )
            else:
                # Use standard version
                # pyright: ignore - function signature is dynamically loaded, all parameters are valid
                combined_analysis(  # pyright: ignore
                    input_path=self.input_file.get(),
                    output_path=self.output_file.get(),
                    dewarp=self.dewarp_enabled.get(),
                    track_ball_flag=self.ball_tracking_enabled.get(),
                    track_players_flag=self.player_tracking_enabled.get(),
                    export_csv=self.csv_export_enabled.get(),
                    buffer=self.buffer_size.get()
                )
            
            # Check if analysis was stopped
            try:
                import shared_state
                was_stopped = shared_state.is_analysis_stop_requested()
                if was_stopped:
                    # Analysis was stopped by user
                    self.root.after(0, self.analysis_complete, False, "Analysis stopped by user")
                    return
            except ImportError:
                pass
            
            # Update UI on completion
            self.root.after(0, self.analysis_complete, True, "Analysis completed successfully!")
            
        except Exception as e:
            error_msg = f"Error during analysis: {str(e)}"
            self.log_message(error_msg)
            self.root.after(0, self.analysis_complete, False, error_msg)
    
    def analysis_complete(self, success, message):
        """Called when analysis completes"""
        self.processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        # Check if it was stopped
        was_stopped = False
        try:
            import shared_state
            was_stopped = shared_state.is_analysis_stop_requested()
            shared_state.clear_analysis_stop()
        except ImportError:
            pass
        
        self.progress_var.set(100)
        
        # Finish progress tracker if available
        if QUICK_WINS_AVAILABLE and hasattr(self, 'progress_tracker') and self.progress_tracker:
            if was_stopped:
                self.progress_tracker.finish("Stopped by user")
            elif success:
                self.progress_tracker.finish("Analysis complete!")
            else:
                self.progress_tracker.finish("Analysis failed")
        
        if was_stopped:
            # Analysis was stopped by user
            self.status_label.config(text="Stopped by user")
            self.log_message("=" * 60)
            self.log_message("Analysis stopped by user")
            self.log_message("   → Gallery and team colors saved (checkpoint)")
            self.log_message("   → You can adjust settings and restart analysis")
            self.log_message("=" * 60)
        elif success:
            # Analysis completed successfully
            self.status_label.config(text="Completed successfully!")
            # Check and enable output buttons based on file existence
            self._check_and_enable_output_buttons()
            
            self.log_message("=" * 60)
            self.log_message("Analysis completed successfully!")
            self.log_message(f"Output video: {self.output_file.get()}")
            if self.csv_export_enabled.get():
                csv_file = self.output_file.get().replace('.mp4', '_tracking_data.csv')
                heatmap_file = self.output_file.get().replace('.mp4', '_heatmap.png')
                self.log_message(f"CSV data: {csv_file}")
                self.log_message(f"Heatmap: {heatmap_file}")
            self.log_message("=" * 60)
            
            # Store output file path for CSV loading feature
            self.last_output_file = self.output_file.get()
            
            # Show success message with options
            msg = "Analysis completed successfully!\n\n"
            msg += f"Output: {os.path.basename(self.output_file.get())}\n"
            if self.csv_export_enabled.get():
                msg += "\nWould you like to:\n"
                msg += "1. Open output folder\n"
                msg += "2. Analyze CSV data\n"
            messagebox.showinfo("Success", msg)
        else:
            self.status_label.config(text="Error occurred")
            messagebox.showerror("Error", message)
    
    def _widget_exists(self, widget_attr):
        """Check if widget exists and is valid"""
        if not hasattr(self, widget_attr):
            return False
        try:
            widget = getattr(self, widget_attr)
            return widget.winfo_exists()
        except (tk.TclError, AttributeError):
            return False
    
    def launch_live_viewer_controls(self):
        """Launch the live viewer controls window"""
        try:
            # Initialize start time on first call
            if self.live_viewer_start_time is None:
                import time
                self.live_viewer_start_time = time.time()
            
            # Check timeout
            import time
            if time.time() - self.live_viewer_start_time > self.live_viewer_timeout:
                self.log_message("⚠ Live viewer launch timeout (30 seconds)")
                self.live_viewer_start_time = None  # Reset for next attempt
                self.live_viewer_retry_count = 0
                return
            
            self.log_message(f"🔍 Attempting to launch live viewer controls (attempt {getattr(self, 'live_viewer_retry_count', 0) + 1})...")
            
            from live_viewer_controls import LiveViewerControls
            
            # Try to get dynamic_settings from shared state
            dynamic_settings = None
            try:
                # First try shared_state module (preferred)
                import shared_state
                dynamic_settings = shared_state.get_dynamic_settings()
                if dynamic_settings:
                    self.log_message("✓ Found dynamic_settings in shared_state")
                else:
                    self.log_message("⚠ shared_state.get_dynamic_settings() returned None")
            except ImportError as e:
                self.log_message(f"⚠ shared_state module not found: {e}")
                # Fallback to module-level variable
                try:
                    import combined_analysis_optimized as analysis_module
                    dynamic_settings = getattr(analysis_module, '_current_dynamic_settings', None)
                    if dynamic_settings:
                        self.log_message("✓ Found dynamic_settings in analysis_module (fallback)")
                    else:
                        self.log_message("⚠ analysis_module._current_dynamic_settings not found")
                except Exception as e:
                    self.log_message(f"⚠ Error accessing analysis module: {e}")
            
            if dynamic_settings:
                # Launch control window
                try:
                    self.log_message(f"📺 Opening Live Viewer Controls window...")
                    self.live_viewer_controls = LiveViewerControls(
                        self.root, 
                        dynamic_settings,
                        on_settings_update=self.on_settings_update
                    )
                    # Store reference in shared_state so analysis can update it
                    try:
                        import shared_state
                        shared_state.set_live_viewer_controls(self.live_viewer_controls)
                    except:
                        pass
                    self.log_message("✓ Live Viewer Controls window opened successfully")
                    self.live_viewer_start_time = None  # Reset on success
                    self.live_viewer_retry_count = 0
                    return  # Success, don't retry
                except Exception as e:
                    self.log_message(f"⚠ Error creating live viewer controls window: {e}")
                    import traceback
                    self.log_message(f"   Traceback: {traceback.format_exc()}")
                    # Don't retry on creation errors - they won't be fixed by waiting
                    return
            else:
                # Retry after a delay if not ready yet
                if not hasattr(self, 'live_viewer_retry_count'):
                    self.live_viewer_retry_count = 0
                if not hasattr(self, 'live_viewer_max_retries'):
                    self.live_viewer_max_retries = 10
                
                self.live_viewer_retry_count += 1
                if self.live_viewer_retry_count < self.live_viewer_max_retries:
                    # Log retry attempt
                    if self.live_viewer_retry_count == 1:
                        self.log_message("⏳ Waiting for live viewer to initialize...")
                    elif self.live_viewer_retry_count % 5 == 0:
                        self.log_message(f"⏳ Still waiting for analysis to initialize... (attempt {self.live_viewer_retry_count}/{self.live_viewer_max_retries})")
                        self.log_message("   → Analysis may still be loading models (this can take 10-30 seconds)")
                    # Retry after 1 second
                    self.root.after(1000, self.launch_live_viewer_controls)
                else:
                    self.log_message("⚠ Could not launch live viewer controls - dynamic_settings not available after multiple retries")
                    self.log_message("   This may happen if:")
                    self.log_message("   • Analysis hasn't started yet (check console for errors)")
                    self.log_message("   • Analysis is still loading models (try waiting longer)")
                    self.log_message("   • shared_state module is not working correctly")
                    self.log_message("   → You can manually open Conflict Resolution from the Tools menu")
                    self.live_viewer_start_time = None  # Reset on failure
                    self.live_viewer_retry_count = 0
        except ImportError as e:
            self.log_message(f"⚠ Could not import live_viewer_controls: {e}")
            self.log_message("   Make sure live_viewer_controls.py is in the same directory")
            import traceback
            self.log_message(f"   Traceback: {traceback.format_exc()}")
        except Exception as e:
            self.log_message(f"⚠ Error launching live viewer controls: {e}")
            import traceback
            self.log_message(f"   Traceback: {traceback.format_exc()}")
    
    def on_settings_update(self, setting_name, value):
        """Callback when settings are updated from control window"""
        self.log_message(f"✓ Setting updated: {setting_name} = {value}")
    
    def open_conflict_resolution(self):
        """Manually open the conflict resolution / Live Viewer Controls window"""
        try:
            from live_viewer_controls import LiveViewerControls
            self.log_message("🔍 Opening Conflict Resolution window...")
            
            # Try to get dynamic_settings, but allow window to open without it
            dynamic_settings = None
            try:
                import shared_state
                dynamic_settings = shared_state.get_dynamic_settings()
            except:
                pass
            
            # If no dynamic_settings, create a minimal placeholder so window can open
            # This allows conflict resolution to work even when analysis isn't running
            if dynamic_settings is None:
                # Create a minimal placeholder settings object for conflict resolution
                # The Player Corrections tab doesn't need full dynamic_settings - it works independently
                class PlaceholderSettings:
                    """Minimal placeholder for DynamicSettings when analysis isn't running"""
                    def __init__(self):
                        self.paused = False
                    def get_current_settings(self):
                        return {}
                    def update_settings(self, **kwargs):
                        pass
                
                dynamic_settings = PlaceholderSettings()
                self.log_message("ℹ Opening conflict resolution (analysis not running - limited features)")
            
            # Launch window
            try:
                self.live_viewer_controls = LiveViewerControls(
                    self.root,
                    dynamic_settings,
                    on_settings_update=self.on_settings_update
                )
                # Update window title if analysis not running
                if dynamic_settings is None or not hasattr(dynamic_settings, 'track_ball_flag'):
                    self.live_viewer_controls.window.title("Conflict Resolution - Player Corrections")
                # Store reference in shared_state
                try:
                    import shared_state
                    shared_state.set_live_viewer_controls(self.live_viewer_controls)
                except:
                    pass
                self.log_message("✓ Conflict Resolution window opened successfully")
            except Exception as e:
                self.log_message(f"⚠ Error creating conflict resolution window: {e}")
                messagebox.showerror("Error", f"Could not open conflict resolution window:\n{e}")
        except ImportError as e:
            messagebox.showerror("Error", f"Could not open conflict resolution window:\n{e}\n\nMake sure live_viewer_controls.py is available.")
        except Exception as e:
            messagebox.showerror("Error", f"Error opening conflict resolution window:\n{e}")
    
    def stop_analysis(self):
        """Stop the analysis gracefully"""
        if self.processing:
            response = messagebox.askyesno("Confirm", 
                                         "Are you sure you want to stop the analysis?\n\n"
                                         "The current frame will finish processing, then analysis will stop gracefully.")
            if response:
                # Set stop flag via shared_state
                try:
                    import shared_state
                    shared_state.request_analysis_stop()
                    self.log_message("⏹ Stop requested - analysis will terminate after current frame...")
                    self.status_label.config(text="Stopping...")
                except ImportError:
                    # Fallback: just set processing flag
                    self.processing = False
                    self.status_label.config(text="Stopped")
                    self.log_message("Analysis stop requested (shared_state not available - may take longer to stop)")
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
    
    def _check_and_enable_output_buttons(self):
        """Check if output files exist and enable buttons accordingly"""
        output_path = self.output_file.get()
        if output_path and os.path.exists(output_path):
            # Output file exists - enable open folder button
            if hasattr(self, 'open_folder_button'):
                self.open_folder_button.config(state=tk.NORMAL)
            
            # Check if CSV file exists (for informational purposes, but button stays enabled)
            csv_file = output_path.replace('.mp4', '_tracking_data.csv')
            # Note: analyze_csv_button stays enabled so users can select any CSV file
        else:
            # No output file or file doesn't exist - disable open folder button only
            if hasattr(self, 'open_folder_button'):
                self.open_folder_button.config(state=tk.DISABLED)
            # analyze_csv_button stays enabled - users can select any CSV file
    
    def open_output_folder(self):
        """Open the output folder in file explorer"""
        output_path = self.output_file.get()
        if output_path:
            folder = os.path.dirname(os.path.abspath(output_path))
            if os.path.exists(folder):
                os.startfile(folder)  # Windows
            else:
                messagebox.showerror("Error", f"Output folder does not exist: {folder}")
        else:
            messagebox.showwarning("Warning", "No output file specified.")
    
    def evaluate_hota(self):
        """Evaluate comprehensive tracking metrics (HOTA, MOTA, IDF1) for tracking quality"""
        try:
            from tracking_metrics_evaluator import evaluate_tracking_metrics
            import tkinter.filedialog as filedialog
            import os
            
            # Ask user to select CSV file
            csv_file = filedialog.askopenfilename(
                title="Select Tracking CSV File",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if not csv_file:
                return
            
            # Check for anchor frames (ground truth)
            video_dir = os.path.dirname(csv_file)
            csv_basename = os.path.basename(csv_file)
            
            # Try to find PlayerTagsSeed file (auto-discovery)
            anchor_file = None
            if os.path.exists(video_dir):
                for filename in os.listdir(video_dir):
                    # Look for PlayerTagsSeed-*.json files
                    if filename.startswith("PlayerTagsSeed-") and filename.endswith(".json"):
                        candidate_path = os.path.join(video_dir, filename)
                        # Verify it's a valid anchor frames file
                        try:
                            import json
                            with open(candidate_path, 'r') as f:
                                data = json.load(f)
                                if 'anchor_frames' in data or 'video_path' in data:
                                    anchor_file = candidate_path
                                    break
                        except:
                            continue
            
            # Evaluate all metrics (HOTA, MOTA, IDF1)
            results = evaluate_tracking_metrics(csv_file, anchor_file)
            
            # Display results in a window
            result_window = tk.Toplevel(self.root)
            result_window.title("Comprehensive Tracking Metrics Evaluation")
            result_window.geometry("700x600")
            result_window.transient(self.root)
            
            # Create scrollable text widget
            text_frame = ttk.Frame(result_window)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            scrollbar = ttk.Scrollbar(text_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            text_widget = tk.Text(text_frame, yscrollcommand=scrollbar.set, 
                                 font=("Courier New", 10), wrap=tk.WORD)
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=text_widget.yview)
            
            # Format results
            if 'error' in results:
                text_widget.insert(tk.END, f"Error: {results['error']}\n")
            else:
                text_widget.insert(tk.END, "=" * 60 + "\n")
                text_widget.insert(tk.END, "Comprehensive Tracking Metrics Evaluation\n")
                text_widget.insert(tk.END, "All metrics work together with Re-ID\n")
                text_widget.insert(tk.END, "=" * 60 + "\n\n")
                
                text_widget.insert(tk.END, "📊 HOTA (Higher Order Tracking Accuracy):\n")
                text_widget.insert(tk.END, f"   Overall HOTA Score: {results.get('HOTA', 0):.4f} (higher is better, max: 1.0)\n")
                text_widget.insert(tk.END, f"   Detection Accuracy (DetA): {results.get('DetA', 0):.4f}\n")
                text_widget.insert(tk.END, f"   Association Accuracy (AssA): {results.get('AssA', 0):.4f}\n")
                text_widget.insert(tk.END, f"   Detection: Recall={results.get('DetRe', 0):.4f}, Precision={results.get('DetPr', 0):.4f}\n")
                text_widget.insert(tk.END, f"   Association: Recall={results.get('AssRe', 0):.4f}, Precision={results.get('AssPr', 0):.4f}\n\n")
                
                text_widget.insert(tk.END, "📊 MOTA (Multiple Object Tracking Accuracy):\n")
                text_widget.insert(tk.END, f"   MOTA Score: {results.get('MOTA', 0):.4f} (higher is better, max: 1.0)\n")
                text_widget.insert(tk.END, f"   MOTP (Precision): {results.get('MOTP', 0):.4f}\n")
                text_widget.insert(tk.END, f"   False Negatives: {results.get('FN', 0)}\n")
                text_widget.insert(tk.END, f"   False Positives: {results.get('FP', 0)}\n")
                text_widget.insert(tk.END, f"   ID Switches: {results.get('IDSW', 0)}\n")
                text_widget.insert(tk.END, f"   Ground Truth: {results.get('GT', 0)}\n\n")
                
                text_widget.insert(tk.END, "📊 IDF1 (ID F1 Score):\n")
                text_widget.insert(tk.END, f"   IDF1 Score: {results.get('IDF1', 0):.4f} (higher is better, max: 1.0)\n")
                text_widget.insert(tk.END, f"   ID Precision: {results.get('IDP', 0):.4f}\n")
                text_widget.insert(tk.END, f"   ID Recall: {results.get('IDR', 0):.4f}\n")
                text_widget.insert(tk.END, f"   ID True Positives: {results.get('IDTP', 0)}\n")
                text_widget.insert(tk.END, f"   ID False Positives: {results.get('IDFP', 0)}\n")
                text_widget.insert(tk.END, f"   ID False Negatives: {results.get('IDFN', 0)}\n\n")
                
                text_widget.insert(tk.END, "=" * 60 + "\n")
                text_widget.insert(tk.END, "\nInterpretation:\n")
                text_widget.insert(tk.END, "• HOTA: Balanced detection and association accuracy\n")
                text_widget.insert(tk.END, "• MOTA: Traditional tracking accuracy (penalizes FP, FN, ID switches)\n")
                text_widget.insert(tk.END, "• IDF1: ID consistency over time (measures ID maintenance)\n")
                text_widget.insert(tk.END, "• Re-ID: Improves tracking during analysis, all metrics evaluate results\n")
                text_widget.insert(tk.END, "• Higher scores indicate better tracking performance\n")
            
            text_widget.config(state=tk.DISABLED)
            
            # Close button
            ttk.Button(result_window, text="Close", command=result_window.destroy).pack(pady=10)
            
        except ImportError:
            messagebox.showerror("Error", "Tracking metrics evaluator not available.\nPlease ensure tracking_metrics_evaluator.py is in the project directory.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to evaluate tracking metrics:\n{str(e)}")
    
    def convert_tracks_to_anchor_frames(self):
        """Convert tracking CSV data to anchor frames (ground truth)"""
        try:
            import json
            import os
            from pathlib import Path
            
            # Ask user to select CSV file
            csv_file = filedialog.askopenfilename(
                title="Select Tracking CSV File",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if not csv_file:
                return
            
            # Ask user to select video file
            video_file = filedialog.askopenfilename(
                title="Select Video File (for anchor frame format)",
                filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
            )
            
            if not video_file:
                return
            
            # Determine output path (same directory as CSV, with video name)
            # CRITICAL: Must use PlayerTagsSeed-{video_name}.json format for auto-detection
            video_name = Path(video_file).stem
            output_dir = Path(csv_file).parent
            default_output = output_dir / f"PlayerTagsSeed-{video_name}.json"
            
            # Ask user for output location (but enforce correct naming)
            output_file = filedialog.asksaveasfilename(
                title="Save Anchor Frames As (must be PlayerTagsSeed-{video_name}.json)",
                defaultextension=".json",
                initialfile=default_output.name,
                initialdir=str(output_dir),
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if not output_file:
                return
            
            # Enforce correct filename format for auto-detection
            output_path = Path(output_file)
            expected_name = f"PlayerTagsSeed-{video_name}.json"
            
            # If user chose a different name, warn and suggest correct name
            if output_path.name != expected_name:
                response = messagebox.askyesno(
                    "Filename Format",
                    f"The system expects: {expected_name}\n\n"
                    f"You chose: {output_path.name}\n\n"
                    f"For automatic detection, the file should be named:\n"
                    f"PlayerTagsSeed-{{video_name}}.json\n\n"
                    f"Would you like to use the correct name instead?\n"
                    f"(Recommended for auto-detection)"
                )
                
                if response:
                    # Use correct name in same directory
                    output_file = str(output_path.parent / expected_name)
                else:
                    # Warn user that auto-detection might not work
                    messagebox.showwarning(
                        "Auto-Detection Warning",
                        f"Using custom filename: {output_path.name}\n\n"
                        f"The system may not automatically detect this file.\n"
                        f"Make sure to manually specify it when evaluating metrics."
                    )
            
            # Show progress window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Converting Tracks to Anchor Frames")
            progress_window.geometry("500x200")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            progress_label = ttk.Label(progress_window, text="Converting tracks...", font=("Arial", 10))
            progress_label.pack(pady=20)
            
            progress_text = scrolledtext.ScrolledText(progress_window, height=6, width=60, wrap=tk.WORD)
            progress_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
            
            # Show settings dialog for filtering options
            settings_window = tk.Toplevel(self.root)
            settings_window.title("Anchor Frame Conversion Settings")
            settings_window.geometry("450x250")
            settings_window.transient(self.root)
            settings_window.grab_set()
            
            ttk.Label(settings_window, text="Filtering Options (to prevent too many anchor frames):", 
                     font=("Arial", 10, "bold")).pack(pady=10)
            
            # Frame interval
            frame_interval_frame = ttk.Frame(settings_window)
            frame_interval_frame.pack(pady=5, padx=20, fill=tk.X)
            ttk.Label(frame_interval_frame, text="Frame Interval (every Nth frame):").pack(side=tk.LEFT)
            frame_interval_var = tk.IntVar(value=30)  # Default: every 30 frames (~1 per second at 30fps)
            ttk.Spinbox(frame_interval_frame, from_=1, to=300, textvariable=frame_interval_var, width=10).pack(side=tk.RIGHT)
            ttk.Label(frame_interval_frame, text="(1 = all frames, 30 = ~1/sec at 30fps)").pack(side=tk.RIGHT, padx=5)
            
            # Max frames
            max_frames_frame = ttk.Frame(settings_window)
            max_frames_frame.pack(pady=5, padx=20, fill=tk.X)
            ttk.Label(max_frames_frame, text="Max Frames (limit):").pack(side=tk.LEFT)
            max_frames_var = tk.StringVar(value="500")  # Default: 500 frames max
            ttk.Entry(max_frames_frame, textvariable=max_frames_var, width=12).pack(side=tk.RIGHT)
            ttk.Label(max_frames_frame, text="(empty = no limit)").pack(side=tk.RIGHT, padx=5)
            
            # Info label
            info_label = ttk.Label(settings_window, 
                text="⚠ Too many anchor frames can slow down analysis.\nRecommended: 30 frame interval, 500 max frames",
                font=("Arial", 9), foreground="orange")
            info_label.pack(pady=10)
            
            conversion_params = {}
            
            def apply_settings():
                frame_interval = frame_interval_var.get()
                max_frames_str = max_frames_var.get().strip()
                try:
                    max_frames = int(max_frames_str) if max_frames_str else None
                except ValueError:
                    max_frames = None
                
                conversion_params['frame_interval'] = frame_interval
                conversion_params['max_frames'] = max_frames
                conversion_params['min_confidence'] = None  # Not implemented in GUI yet
                
                settings_window.destroy()
            
            def cancel_settings():
                conversion_params['cancelled'] = True
                settings_window.destroy()
            
            button_frame = ttk.Frame(settings_window)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Apply", command=apply_settings).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=cancel_settings).pack(side=tk.LEFT, padx=5)
            
            # Wait for user to close settings window
            settings_window.wait_window()
            
            if conversion_params.get('cancelled'):
                progress_window.destroy()
                return
            
            def do_conversion():
                try:
                    # Import converter function
                    from convert_tracks_to_anchor_frames import convert_csv_to_anchor_frames
                    
                    progress_text.insert(tk.END, f"Reading CSV: {os.path.basename(csv_file)}\n")
                    if conversion_params.get('frame_interval', 1) > 1:
                        progress_text.insert(tk.END, f"Frame sampling: Every {conversion_params['frame_interval']} frames\n")
                    if conversion_params.get('max_frames'):
                        progress_text.insert(tk.END, f"Max frames limit: {conversion_params['max_frames']}\n")
                    progress_window.update()
                    
                    result = convert_csv_to_anchor_frames(
                        csv_file, video_file, output_file,
                        frame_interval=conversion_params.get('frame_interval', 1),
                        max_frames=conversion_params.get('max_frames'),
                        min_confidence=conversion_params.get('min_confidence')
                    )
                    
                    if result:
                        progress_text.insert(tk.END, f"\n✅ Success!\n")
                        progress_text.insert(tk.END, f"Anchor frames saved to:\n{result}\n")
                        progress_text.insert(tk.END, f"\nThe anchor frames will be automatically loaded during analysis.\n")
                        progress_text.insert(tk.END, f"All tracks will have 1.00 confidence (ground truth).\n")
                        
                        # Add close button
                        def close_window():
                            progress_window.destroy()
                            messagebox.showinfo("Success", 
                                f"Converted tracks to anchor frames!\n\n"
                                f"Saved to: {result}\n\n"
                                f"The anchor frames will be automatically loaded during analysis.")
                        
                        close_button = ttk.Button(progress_window, text="Close", command=close_window)
                        close_button.pack(pady=10)
                    else:
                        progress_text.insert(tk.END, f"\n❌ Conversion failed!\n")
                        progress_text.insert(tk.END, f"\nPossible reasons:\n")
                        progress_text.insert(tk.END, f"• No player mappings found in player_gallery.json\n")
                        progress_text.insert(tk.END, f"• CSV doesn't have matching player names\n")
                        progress_text.insert(tk.END, f"• All tracks were filtered out by settings\n")
                        progress_text.insert(tk.END, f"\nCheck the error messages above for details.\n")
                        progress_text.insert(tk.END, f"\nTip: Make sure player_gallery.json has track_history\n")
                        progress_text.insert(tk.END, f"or run analysis first to populate the gallery.\n")
                        
                        close_button = ttk.Button(progress_window, text="Close", command=progress_window.destroy)
                        close_button.pack(pady=10)
                        
                except ImportError as e:
                    progress_text.insert(tk.END, f"❌ Error: Could not import converter module.\n")
                    progress_text.insert(tk.END, f"Make sure convert_tracks_to_anchor_frames.py is in the project directory.\n")
                    progress_text.insert(tk.END, f"Error: {str(e)}\n")
                    
                    close_button = ttk.Button(progress_window, text="Close", command=progress_window.destroy)
                    close_button.pack(pady=10)
                    
                except Exception as e:
                    progress_text.insert(tk.END, f"❌ Error during conversion:\n{str(e)}\n")
                    import traceback
                    error_details = traceback.format_exc()
                    progress_text.insert(tk.END, f"\nError details:\n{error_details}\n")
                    import traceback
                    progress_text.insert(tk.END, traceback.format_exc())
                    
                    close_button = ttk.Button(progress_window, text="Close", command=progress_window.destroy)
                    close_button.pack(pady=10)
            
            # Run conversion in separate thread
            import threading
            thread = threading.Thread(target=do_conversion, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start conversion:\n{str(e)}")
    
    def run_interactive_learning(self):
        """Run interactive player learning - identify unknown players quickly"""
        try:
            from interactive_player_learning import run_interactive_learning_gui
            from tkinter import filedialog
            
            # Ask user to select CSV file
            csv_file = filedialog.askopenfilename(
                title="Select Tracking CSV File",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if not csv_file:
                return
            
            # Ask user to select video file
            video_file = filedialog.askopenfilename(
                title="Select Video File (for showing player frames)",
                filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
            )
            
            if not video_file:
                return
            
            # Run interactive learning
            run_interactive_learning_gui(csv_file, video_file, "player_gallery.json")
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import interactive learning module.\n\n"
                               f"Make sure interactive_player_learning.py is in the project directory.\n\n"
                               f"Error: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Error during interactive learning:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
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
            
            # Smart file detection: If user selected wrong file, try to find the correct one
            input_dir = os.path.dirname(input_file)
            input_basename = os.path.basename(input_file)
            
            # Check if selected file has player_mappings OR anchor_frames
            try:
                with open(input_file, 'r') as f:
                    test_data = json.load(f)
                has_mappings = bool(test_data.get("player_mappings"))
                has_anchor_frames = bool(test_data.get("anchor_frames"))
            except:
                has_mappings = False
                has_anchor_frames = False
            
            # If no mappings or anchor_frames found, try to find PlayerTagsSeed file in same directory
            if not has_mappings and not has_anchor_frames:
                # Extract video name from filename (e.g., "part001.json" -> "part001")
                video_name = os.path.splitext(input_basename)[0]
                # Remove common prefixes/suffixes
                if video_name.startswith("part"):
                    video_name = video_name
                elif "_" in video_name:
                    video_name = video_name.split("_")[0]
                
                # Try to find PlayerTagsSeed file
                possible_files = [
                    os.path.join(input_dir, f"PlayerTagsSeed-{video_name}.json"),
                    os.path.join(input_dir, f"PlayerTagsSeed-{input_basename}"),
                    os.path.join(input_dir, "PlayerTagsSeed-part001.json"),  # Common fallback
                ]
                
                # Also search directory for any PlayerTagsSeed files
                if os.path.isdir(input_dir):
                    for file in os.listdir(input_dir):
                        if file.startswith("PlayerTagsSeed-") and file.endswith(".json"):
                            possible_files.append(os.path.join(input_dir, file))
                
                # Try each possible file
                found_file = None
                for candidate_file in possible_files:
                    if os.path.exists(candidate_file):
                        try:
                            with open(candidate_file, 'r') as f:
                                candidate_data = json.load(f)
                            if candidate_data.get("player_mappings") or candidate_data.get("anchor_frames"):
                                found_file = candidate_file
                                break
                        except:
                            continue
                
                if found_file:
                    # Count tags from either format
                    mappings_count = len(candidate_data.get('player_mappings', {}))
                    anchor_count = sum(len(anchors) for anchors in candidate_data.get('anchor_frames', {}).values() if isinstance(anchors, list))
                    total_tags = mappings_count + anchor_count
                    
                    response = messagebox.askyesno(
                        "File Not Found",
                        f"The selected file '{input_basename}' doesn't contain player_mappings or anchor_frames.\n\n"
                        f"Found '{os.path.basename(found_file)}' with {total_tags} player tags.\n\n"
                        f"Use this file instead?",
                        icon='question'
                    )
                    if response:
                        input_file = found_file
                    else:
                        return
                else:
                    messagebox.showerror(
                        "No Player Tags Found",
                        f"The selected file '{input_basename}' doesn't contain player_mappings or anchor_frames.\n\n"
                        f"Please select a PlayerTagsSeed-*.json file that contains player tags.\n\n"
                        f"Look for files named:\n"
                        f"• PlayerTagsSeed-*.json (with anchor_frames)\n"
                        f"• seed_config.json (with player_mappings)\n"
                        f"• Or any file saved from the Setup Wizard or Player Gallery Seeder"
                    )
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
            interval_var = tk.IntVar(value=150)  # Default: 150 frames (matches protection window)
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
                from convert_existing_tags_to_anchors import convert_tags_to_anchors
                
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
                    
            except ImportError:
                messagebox.showerror(
                    "Error",
                    "Could not import converter module.\n\n"
                    "Make sure convert_existing_tags_to_anchors.py is in the project directory."
                )
            except Exception as e:
                messagebox.showerror("Error", f"Error during conversion:\n{str(e)}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")
    
    def fix_failed_anchor_frames(self):
        """Fix anchor frames that failed to match during analysis"""
        try:
            import os
            from pathlib import Path
            
            # Ask user to select anchor frames JSON file
            anchor_file = filedialog.askopenfilename(
                title="Select Anchor Frames JSON File",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if not anchor_file:
                return
            
            # Show analysis first
            from fix_failed_anchor_frames import analyze_anchor_frame_issues, fix_anchor_frames
            
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Fixing Anchor Frames")
            progress_window.geometry("600x400")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            progress_text = scrolledtext.ScrolledText(progress_window, height=15, width=70, wrap=tk.WORD)
            progress_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
            
            def do_fix():
                try:
                    progress_text.insert(tk.END, "📊 Analyzing anchor frames...\n")
                    progress_window.update()
                    
                    issues = analyze_anchor_frame_issues(anchor_file)
                    
                    if issues:
                        progress_text.insert(tk.END, f"\n📈 Analysis Results:\n")
                        progress_text.insert(tk.END, f"   - Total frames: {issues['total_frames']}\n")
                        progress_text.insert(tk.END, f"   - Frames with 'Unknown Player': {issues['frames_with_unknown']}\n")
                        progress_text.insert(tk.END, f"   - Frames with >15 anchors: {issues['frames_with_many_anchors']}\n")
                        progress_text.insert(tk.END, f"   - Missing bbox: {issues['missing_bbox']}\n")
                        progress_text.insert(tk.END, f"   - Missing track_id: {issues['missing_track_id']}\n")
                        progress_text.insert(tk.END, f"   - Bbox size issues: {len(issues['bbox_size_issues'])}\n")
                        progress_window.update()
                    
                    progress_text.insert(tk.END, f"\n🔧 Fixing anchor frames...\n")
                    progress_window.update()
                    
                    # Create backup and fix
                    success = fix_anchor_frames(anchor_file, None, fix_unknown=True, fix_bbox_sizes=True)
                    
                    if success:
                        progress_text.insert(tk.END, f"\n✅ Success! Anchor frames fixed.\n")
                        progress_text.insert(tk.END, f"   - Backup created: {anchor_file.replace('.json', '_backup.json')}\n")
                        progress_text.insert(tk.END, f"   - Fixed file: {anchor_file}\n")
                        progress_text.insert(tk.END, f"\nRe-run analysis to see improved matching.\n")
                        
                        def close_window():
                            progress_window.destroy()
                            messagebox.showinfo("Success", 
                                f"Fixed anchor frames!\n\n"
                                f"Backup saved, fixes applied.\n"
                                f"Re-run analysis to see improved matching.")
                        
                        close_button = ttk.Button(progress_window, text="Close", command=close_window)
                        close_button.pack(pady=10)
                    else:
                        progress_text.insert(tk.END, f"\n❌ Fix failed - check errors above\n")
                        close_button = ttk.Button(progress_window, text="Close", command=progress_window.destroy)
                        close_button.pack(pady=10)
                        
                except ImportError as e:
                    progress_text.insert(tk.END, f"❌ Error: Could not import fix_failed_anchor_frames.py\n")
                    progress_text.insert(tk.END, f"Make sure the file is in the project directory.\n")
                    progress_text.insert(tk.END, f"Error: {str(e)}\n")
                    close_button = ttk.Button(progress_window, text="Close", command=progress_window.destroy)
                    close_button.pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open anchor frame fixer:\n{e}")
    
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
                    from optimize_anchor_frames import optimize_anchor_frames, store_occlusion_anchors_per_player, load_anchor_frames, detect_occlusion_points
                    
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
                    
                    close_button = ttk.Button(progress_window, text="Close", command=progress_window.destroy)
                    close_button.pack(pady=10)
                    
                except ImportError as e:
                    progress_text.insert(tk.END, f"❌ Error: Could not import optimize_anchor_frames.py\n")
                    progress_text.insert(tk.END, f"Make sure the file is in the project directory.\n")
                    progress_text.insert(tk.END, f"Error: {str(e)}\n")
                    close_button = ttk.Button(progress_window, text="Close", command=progress_window.destroy)
                    close_button.pack(pady=10)
                except Exception as e:
                    progress_text.insert(tk.END, f"❌ Error during optimization:\n{str(e)}\n")
                    import traceback
                    progress_text.insert(tk.END, traceback.format_exc())
                    close_button = ttk.Button(progress_window, text="Close", command=progress_window.destroy)
                    close_button.pack(pady=10)
            
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
                                # Use safe JSON saving with corruption protection
                                try:
                                    from json_utils import safe_json_save
                                    from pathlib import Path
                                    safe_json_save(Path(seed_config_path), data, create_backup=True, validate=True)
                                except ImportError:
                                    # Fallback to standard JSON if json_utils not available
                                    with open(seed_config_path, 'w', encoding='utf-8') as f:
                                        json.dump(data, f, indent=2, ensure_ascii=False)
                                
                                progress_text.insert(tk.END, f"  ✓ Cleared anchor_frames from seed_config.json\n")
                        except Exception as e:
                            progress_text.insert(tk.END, f"  ⚠ Error clearing seed_config.json: {e}\n")
                    
                    progress_text.insert(tk.END, f"\n✅ Done!\n")
                    progress_text.insert(tk.END, f"   Deleted: {deleted_count} file(s)\n")
                    progress_text.insert(tk.END, f"   Backed up: {backed_up_count} file(s)\n")
                    progress_text.insert(tk.END, f"\n💡 Next steps:\n")
                    progress_text.insert(tk.END, f"   1. Run analysis WITHOUT anchor frames (faster!)\n")
                    progress_text.insert(tk.END, f"   2. After analysis completes, use 'Track Review & Assign' tool\n")
                    progress_text.insert(tk.END, f"   3. Assign player names to tracks\n")
                    progress_text.insert(tk.END, f"   4. Save as anchor frames (creates new, optimized anchor frames)\n")
                    
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
    
    def export_reid_model(self):
        """Open dialog to export ReID model to optimized format"""
        try:
            from tkinter import filedialog, messagebox
            from reid_model_export import export_model
            
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
                        # Show export location and usage info
                        export_path = Path(result) if isinstance(result, str) else result
                        if export_path.is_file():
                            location_msg = f"Model exported successfully!\n\nLocation:\n{export_path}\n\n"
                        else:
                            location_msg = f"Model exported successfully!\n\nLocation:\n{export_path}\n\n"
                        
                        usage_msg = (
                            "💡 Automatic Usage:\n"
                            "The exported model will be automatically detected\n"
                            "and used by ReIDTracker when you run analysis.\n"
                            "No manual import needed!\n\n"
                            f"BoxMOT will prefer {format_var.get().upper()} over\n"
                            "PyTorch for faster inference."
                        )
                        
                        messagebox.showinfo("Export Successful", 
                                          location_msg + usage_msg)
                    else:
                        messagebox.showerror("Export Failed", 
                                           "Model export failed. Check console for details.")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Error during export:\n{e}")
            
            ttk.Button(format_window, text="Export", command=do_export).pack(pady=15)
            ttk.Button(format_window, text="Cancel", command=format_window.destroy).pack()
            
        except ImportError:
            messagebox.showerror("Export Not Available", 
                               "ReID model export requires BoxMOT.\n\n"
                               "Install with: pip install boxmot")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open export dialog:\n{e}")
    
    def open_track_review(self):
        """Open Track Review & Player Assignment tool"""
        try:
            from track_review_assigner import TrackReviewAssigner
            self.track_review_window = TrackReviewAssigner(self.root)
            self.log_message("✓ Opened Track Review & Player Assignment tool")
        except ImportError as e:
            messagebox.showerror("Error", f"Could not import track_review_assigner.py:\n{e}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Track Review tool:\n{e}")
    
    def analyze_csv(self):
        """Run CSV analysis script - always prompts user to select CSV file"""
        from tkinter import filedialog
        
        # Always prompt user to select CSV file
        csv_file = filedialog.askopenfilename(
            title="Select CSV file to analyze",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not csv_file:
            return  # User cancelled
        
        if not os.path.exists(csv_file):
            messagebox.showerror("Error", f"CSV file not found: {csv_file}")
            return
        
        try:
            # Try to import and run analyze_csv
            import subprocess
            script_path = os.path.join(os.path.dirname(__file__), 'analyze_csv.py')
            if os.path.exists(script_path):
                self.log_message("=" * 60)
                self.log_message("Running CSV analysis...")
                self.log_message("=" * 60)
                
                # Run in separate thread to avoid blocking GUI
                def run_analysis():
                    try:
                        result = subprocess.run(
                            [sys.executable, script_path, csv_file],
                            capture_output=True,
                            text=True,
                            cwd=os.path.dirname(script_path)
                        )
                        self.root.after(0, lambda: self.log_message(result.stdout))
                        if result.returncode == 0:
                            self.root.after(0, lambda: messagebox.showinfo(
                                "Success", 
                                f"CSV analysis complete!\n\nCharts saved in:\n{os.path.dirname(csv_file)}"
                            ))
                        else:
                            self.root.after(0, lambda: messagebox.showerror(
                                "Error", 
                                f"CSV analysis failed:\n{result.stderr}"
                            ))
                    except Exception as e:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Error", 
                            f"Failed to run CSV analysis: {str(e)}"
                        ))
                
                threading.Thread(target=run_analysis, daemon=True).start()
            else:
                messagebox.showerror("Error", f"CSV analysis script not found: {script_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not run CSV analysis: {e}")
            import traceback
            traceback.print_exc()
    
    def open_analytics_selection(self):
        """Open Analytics Selection window"""
        try:
            from analytics_selection_gui import AnalyticsSelectionGUI
            
            # Define callbacks
            def apply_callback(preferences):
                """Apply preferences immediately"""
                self.update_analytics_preferences(preferences)
            
            def save_to_project_callback(preferences):
                """Save preferences to project file"""
                self.analytics_preferences = preferences
                # Save project if project path exists
                if self.current_project_path:
                    try:
                        self.save_project()
                        self.log_message("✓ Analytics preferences saved to project")
                    except Exception as e:
                        self.log_message(f"⚠ Could not save project: {e}")
                else:
                    # Just update preferences if no project file
                    self.update_analytics_preferences(preferences)
            
            self.analytics_selection_window = AnalyticsSelectionGUI(
                self.root,
                apply_callback=apply_callback,
                save_to_project_callback=save_to_project_callback
            )
            self.log_message("✓ Opened Analytics Selection window")
        except ImportError as e:
            messagebox.showerror("Error", f"Could not import analytics_selection_gui.py:\n{e}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Analytics Selection window:\n{e}")
            import traceback
            traceback.print_exc()
    
    def update_analytics_preferences(self, preferences):
        """Update analytics preferences (called by AnalyticsSelectionGUI)"""
        self.analytics_preferences = preferences
        self.log_message(f"✓ Analytics preferences updated: {len([k for k, v in preferences.items() if v])} metrics selected")
    
    def open_setup_checklist(self):
        """Open Setup Checklist window"""
        try:
            from setup_checklist import open_setup_checklist
            open_setup_checklist(self.root)
            self.log_message("✓ Opened Setup Checklist")
        except ImportError as e:
            messagebox.showerror("Error", f"Could not import setup_checklist.py:\n{e}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Setup Checklist:\n{e}")
            import traceback
            traceback.print_exc()
    
    def open_ball_color_helper(self):
        """Open combined color detection helper (Ball & Team)"""
        try:
            from combined_color_helper import CombinedColorHelper
            
            helper_window = tk.Toplevel(self.root)
            helper_window.transient(self.root)  # Make it a child of main window
            helper_window.lift()  # Bring to front
            helper_window.attributes('-topmost', True)  # Keep on top
            helper_window.focus_force()  # Focus the window
            
            def apply_ball_colors_callback(config):
                """Callback to apply ball colors to analysis"""
                self.log_message(f"Ball color config saved: {config.get('color1', {}).get('name', 'Color 1')}/{config.get('color2', {}).get('name', 'Color 2')}")
                self.log_message(f"Config file: ball_color_config.json")
            
            def apply_team_colors_callback(config, team1_name, team2_name):
                """Callback to apply team colors to analysis"""
                self.log_message(f"Team color config saved: {team1_name} / {team2_name}")
                self.log_message(f"Config file: team_color_config.json")
            
            # Create combined helper (it handles both ball and team colors)
            helper = CombinedColorHelper(helper_window, callback=None)
            
            # Store reference to helper for callbacks
            def apply_ball_wrapper():
                helper.apply_ball_colors()
                apply_ball_colors_callback({
                    "color1": {
                        "name": helper.ball_color1_entry.get(),
                        "hsv_ranges": helper.ball_hsv_ranges["color1"]
                    },
                    "color2": {
                        "name": helper.ball_color2_entry.get(),
                        "hsv_ranges": helper.ball_hsv_ranges["color2"]
                    }
                })
            
            def apply_team_wrapper():
                helper.apply_team_colors()
                apply_team_colors_callback(
                    {
                        "team_colors": {
                            "team1": {
                                "name": helper.team1_entry.get(),
                                "hsv_ranges": helper.team_colors["team1"]["hsv_ranges"]
                            },
                            "team2": {
                                "name": helper.team2_entry.get(),
                                "hsv_ranges": helper.team_colors["team2"]["hsv_ranges"]
                            }
                        }
                    },
                    helper.team1_entry.get(),
                    helper.team2_entry.get()
                )
            
            # Find and replace button commands after a short delay (to ensure widgets are created)
            def update_buttons():
                # Find the notebook
                for widget in helper.root.winfo_children():
                    if isinstance(widget, ttk.Frame):
                        for child in widget.winfo_children():
                            if isinstance(child, ttk.Notebook):
                                # Find the ball tab
                                try:
                                    ball_tab = child.nametowidget(child.tabs()[0])
                                    for ball_widget in ball_tab.winfo_children():
                                        if isinstance(ball_widget, ttk.Button):
                                            text = ball_widget.cget("text")
                                            if "Apply Ball" in text:
                                                ball_widget.config(command=apply_ball_wrapper)
                                except:
                                    pass
                                
                                # Find the team tab
                                try:
                                    team_tab = child.nametowidget(child.tabs()[1])
                                    for team_widget in team_tab.winfo_children():
                                        if isinstance(team_widget, ttk.Button):
                                            text = team_widget.cget("text")
                                            if "Apply Team" in text:
                                                team_widget.config(command=apply_team_wrapper)
                                except:
                                    pass
            
            # Update buttons after widgets are fully created
            helper.root.after(100, update_buttons)
            
        except ImportError as e:
            messagebox.showerror("Error", f"Could not import combined color helper: {str(e)}\nMake sure combined_color_helper.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open color helper: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def open_field_calibration(self):
        """Open field calibration GUI tool"""
        try:
            from calibrate_field_gui import FieldCalibrationGUI
            
            # Get video path if available
            video_path = None
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
                if not os.path.exists(video_path):
                    video_path = None
                    messagebox.showwarning("Warning", 
                                         "Video file not found. Please load a video first, or use 'Load Image' in the calibration tool.")
            
            # Open GUI-based calibration tool with video path
            calibration_window = FieldCalibrationGUI(self.root, video_path=video_path)
            if video_path:
                self.log_message(f"Field calibration GUI opened with video: {os.path.basename(video_path)}")
            else:
                self.log_message("Field calibration GUI opened (no video loaded)")
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import calibrate_field_gui: {str(e)}\n\n"
                               "Make sure calibrate_field_gui.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open field calibration: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def open_speed_tracking(self):
        """Open speed tracking tool"""
        try:
            from track_speed_coverage import track_speed_coverage
            
            # Check if calibration exists
            if not os.path.exists("calibration.npy"):
                response = messagebox.askyesno(
                    "Calibration Required",
                    "Field calibration not found!\n\n"
                    "You need to calibrate the field first.\n\n"
                    "Would you like to calibrate now?\n\n"
                    "(Click 'No' if you want to process without calibration)"
                )
                if response:
                    self.open_field_calibration()
                    return
            
            # Ask for input video
            input_path = filedialog.askopenfilename(
                title="Select Input Video for Speed Tracking",
                filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v *.mpg *.mpeg"), ("All files", "*.*")]
            )
            if not input_path:
                return
            
            # Generate output path
            base_name = os.path.splitext(input_path)[0]
            output_path = f"{base_name}_speed_tracked.mp4"
            
            # Confirm output path
            output_path = filedialog.asksaveasfilename(
                title="Save Speed Tracked Video",
                defaultextension=".mp4",
                initialfile=os.path.basename(output_path),
                filetypes=[("Video files", "*.mp4"), ("All files", "*.*")]
            )
            if not output_path:
                return
            
            # Ask for sprint threshold
            sprint_threshold = simpledialog.askfloat("Sprint Threshold", 
                                                     "Enter sprint threshold in mph (default: 15.0):\n\n"
                                                     "Players exceeding this speed will be marked in sprint zones.",
                                                     initialvalue=15.0, minvalue=1.0, maxvalue=30.0)
            if sprint_threshold is None:
                sprint_threshold = 15.0
            
            # Run speed tracking
            self.log_message("="*60)
            self.log_message("Starting Speed Tracking & Field Coverage Analysis")
            self.log_message("="*60)
            self.log_message(f"Input: {input_path}")
            self.log_message(f"Output: {output_path}")
            self.log_message(f"Sprint threshold: {sprint_threshold} mph")
            self.log_message("="*60)
            
            # Run in separate thread
            def run_speed_tracking():
                try:
                    track_speed_coverage(input_path, output_path, use_mph=True, 
                                       sprint_threshold_mph=sprint_threshold)
                    self.log_message("✓ Speed tracking complete!")
                    messagebox.showinfo("Success", 
                                      "Speed tracking complete!\n\n"
                                      f"Video saved: {output_path}\n"
                                      f"Speed data CSV: {output_path.replace('.mp4', '_speed_data.csv')}\n"
                                      f"Field coverage: {output_path.replace('.mp4', '_field_coverage.png')}")
                except Exception as e:
                    error_msg = f"Speed tracking failed: {str(e)}"
                    self.log_message(f"Error: {error_msg}")
                    messagebox.showerror("Error", error_msg)
            
            thread = threading.Thread(target=run_speed_tracking, daemon=True)
            thread.start()
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import track_speed_coverage.py: {str(e)}\n\n"
                               "Make sure track_speed_coverage.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open speed tracking: {str(e)}")
    
    def open_team_color_helper(self):
        """Open team color detection helper"""
        try:
            from team_color_detector import TeamColorDetector
            
            helper_window = tk.Toplevel(self.root)
            helper_window.title("Team Color Detection Helper")
            helper_window.geometry("900x750")
            helper_window.transient(self.root)  # Make it a child of main window
            
            # Ensure window opens on top
            helper_window.lift()
            helper_window.attributes('-topmost', True)
            helper_window.focus_force()
            # Remove topmost after a brief delay to allow normal window management
            helper_window.after(200, lambda: helper_window.attributes('-topmost', False))
            
            def apply_team_colors(team_colors, team1_name, team2_name):
                """Callback to apply team colors to analysis"""
                # Already saved by team_color_detector.py
                self.log_message(f"Team colors applied: {team1_name} vs {team2_name}")
                
            detector = TeamColorDetector(helper_window, callback=apply_team_colors)
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import team color detector: {str(e)}\n\n"
                               "Make sure team_color_detector.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open team color helper: {str(e)}")
            import traceback
            traceback.print_exc()
    
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
            stats_window.transient(self.root)  # Make it a child of main window
            
            # Store reference to prevent garbage collection
            self._player_stats_window = stats_window
            
            # Calculate centered position relative to parent window
            self.root.update_idletasks()  # Ensure parent window dimensions are accurate
            
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
            
            # Ensure window is on screen (fallback to screen center if parent is off-screen)
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
            
            self._create_gallery_tab(gallery_tab)
            
            # Tab 2: Per-Video Player Names (traditional)
            names_tab = ttk.Frame(notebook, padding="10")
            notebook.add(names_tab, text="📝 Per-Video Names")
            
            # Try to load traditional player stats GUI in this tab
            try:
                from player_stats_gui import PlayerStatsGUI
                app = PlayerStatsGUI(names_tab)
                self._player_stats_app = app
            except Exception as e:
                # Fallback if PlayerStatsGUI not available
                ttk.Label(names_tab, text=f"Traditional player stats not available.\n\n{str(e)}", 
                         font=("Arial", 10)).pack(pady=20)
            
            # Tab 3: Team Roster Management
            roster_tab = ttk.Frame(notebook, padding="10")
            notebook.add(roster_tab, text="👥 Team Roster")
            
            self._create_roster_tab(roster_tab)
            
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
            
            # If we have a CSV file from recent analysis, try to load it
            # Priority: consolidated CSV > tracking data CSV > speed data CSV
            if hasattr(self, 'last_output_file') and self.last_output_file:
                base_name = os.path.splitext(self.last_output_file)[0]
                
                # First, try to find consolidated CSV (common names)
                consolidated_files = [
                    f"{base_name}_consolidated.csv",
                    f"{base_name}_tracking_data_consolidated.csv",
                    "conolidated.csv",  # Common typo/abbreviation
                    "consolidated.csv"
                ]
                
                csv_file = None
                for consolidated_file in consolidated_files:
                    if os.path.exists(consolidated_file):
                        csv_file = consolidated_file
                        break
                
                # If no consolidated file found, try regular tracking data
                if not csv_file:
                    csv_file = f"{base_name}_tracking_data.csv"
                    if not os.path.exists(csv_file):
                        # Try speed data CSV
                        csv_file = f"{base_name}_speed_tracked_speed_data.csv"
                        if not os.path.exists(csv_file):
                            csv_file = None
                
                if csv_file and os.path.exists(csv_file):
                    app.csv_path_var.set(csv_file)
                    # Load CSV after a brief delay to ensure window is fully initialized
                    stats_window.after(100, app.load_csv)
            
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
    
    def open_consolidate_ids(self):
        """Open ID consolidation tool"""
        try:
            from consolidate_player_ids import IDConsolidationGUI
            
            consolidate_window = tk.Toplevel(self.root)
            consolidate_window.title("Player ID Consolidation")
            consolidate_window.geometry("1200x800")
            consolidate_window.transient(self.root)  # Make it a child of main window
            
            app = IDConsolidationGUI(consolidate_window)
            
            # Ensure window stays visible (don't set topmost permanently)
            consolidate_window.lift()
            consolidate_window.focus_force()
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import consolidate_player_ids.py: {str(e)}\n\n"
                               "Make sure consolidate_player_ids.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open ID consolidation tool: {str(e)}")
    
    def open_post_analysis_workflow(self):
        """Open Post-Analysis Workflow Quick-Start Guide"""
        try:
            # Check if window already exists
            if hasattr(self, '_workflow_window') and self._workflow_window and self._workflow_window.winfo_exists():
                self._workflow_window.lift()
                self._workflow_window.focus_force()
                return
            
            self._workflow_window = tk.Toplevel(self.root)
            self._workflow_window.title("🚀 Post-Analysis Workflow Quick-Start")
            self._workflow_window.geometry("800x700")
            self._workflow_window.transient(self.root)
            
            # Create main frame with padding
            main_frame = ttk.Frame(self._workflow_window, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            title_label = ttk.Label(main_frame, text="Post-Analysis Player Tagging Workflow", 
                                   font=("Arial", 14, "bold"))
            title_label.pack(pady=(0, 10))
            
            # Description
            desc_text = ("This workflow guides you through tagging players after analysis.\n"
                        "Each step opens the appropriate tool in the recommended order.")
            desc_label = ttk.Label(main_frame, text=desc_text, 
                                  font=("Arial", 9), foreground="gray", justify=tk.CENTER)
            desc_label.pack(pady=(0, 20))
            
            # Create scrollable frame for workflow steps
            canvas = tk.Canvas(main_frame, highlightthickness=0)
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Workflow steps
            steps = [
                {
                    "step": "Step 1: Run Analysis",
                    "description": "Run analysis with player tracking (disable gallery matching for clean data)",
                    "button": None,
                    "action": None
                },
                {
                    "step": "Step 2: Consolidate IDs",
                    "description": "Merge duplicate track IDs (same player, different IDs)",
                    "button": "Open Consolidate IDs",
                    "action": self.open_consolidate_ids
                },
                {
                    "step": "Step 3: Track Review & Assign",
                    "description": "Tag players to track IDs with full context (main tagging step)",
                    "button": "Open Track Review",
                    "action": self.open_track_review
                },
                {
                    "step": "Step 4: Interactive Player Learning",
                    "description": "Auto-tag any remaining unknown players (catches missed tracks)",
                    "button": "Open Interactive Learning",
                    "action": self.run_interactive_learning
                },
                {
                    "step": "Step 5: Tag Players (Gallery)",
                    "description": "Build verified player gallery from tagged tracks",
                    "button": "Open Gallery Seeder",
                    "action": self.open_player_gallery_seeder
                },
                {
                    "step": "Step 6: Optimize Anchor Frames",
                    "description": "Clean up and optimize anchor frames (optional)",
                    "button": "Open Optimize",
                    "action": self.optimize_anchor_frames
                },
                {
                    "step": "Step 7: Evaluate Tracking Metrics",
                    "description": "Measure tracking quality (HOTA, MOTA, IDF1)",
                    "button": "Open Metrics",
                    "action": self.evaluate_hota
                }
            ]
            
            # Create step widgets
            for idx, step_info in enumerate(steps, 1):
                step_frame = ttk.LabelFrame(scrollable_frame, text=step_info["step"], padding="10")
                step_frame.pack(fill=tk.X, pady=5, padx=5)
                
                # Description
                desc_label = ttk.Label(step_frame, text=step_info["description"], 
                                      font=("Arial", 9), wraplength=600)
                desc_label.pack(anchor=tk.W, pady=(0, 5))
                
                # Button if available
                if step_info["button"] and step_info["action"]:
                    button = ttk.Button(step_frame, text=step_info["button"], 
                                       command=lambda a=step_info["action"]: self._open_workflow_tool(a))
                    button.pack(anchor=tk.W)
            
            # Pack canvas and scrollbar
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Enable mousewheel scrolling
            def on_mousewheel(event):
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            canvas.bind_all("<MouseWheel>", on_mousewheel)
            
            # Help text
            help_frame = ttk.Frame(main_frame)
            help_frame.pack(fill=tk.X, pady=(10, 0))
            
            help_text = ("💡 Tip: Complete steps in order for best results.\n"
                        "Each tool opens in a separate window - you can keep this guide open.")
            help_label = ttk.Label(help_frame, text=help_text, 
                                  font=("Arial", 8), foreground="blue", justify=tk.CENTER)
            help_label.pack()
            
            # Close button
            close_button = ttk.Button(main_frame, text="Close", 
                                    command=self._workflow_window.destroy)
            close_button.pack(pady=(10, 0))
            
            self._workflow_window.lift()
            self._workflow_window.focus_force()
            
            self.log_message("✓ Opened Post-Analysis Workflow Quick-Start")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not open workflow guide: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _open_workflow_tool(self, tool_function):
        """Helper to open workflow tool and log it"""
        try:
            tool_function()
            self.log_message(f"✓ Opened tool from workflow guide")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open tool: {str(e)}")
    
    def open_player_gallery_seeder(self):
        """Open Player Gallery Seeder for tagging players"""
        try:
            # Check if window already exists
            if hasattr(self, '_gallery_seeder_window') and self._gallery_seeder_window and self._gallery_seeder_window.winfo_exists():
                self._gallery_seeder_window.lift()
                self._gallery_seeder_window.focus_force()
                return
            
            from player_gallery_seeder import PlayerGallerySeeder
            
            self._gallery_seeder_window = tk.Toplevel(self.root)
            self._gallery_seeder_window.transient(self.root)  # Make it a child of main window
            
            app = PlayerGallerySeeder(self._gallery_seeder_window)
            self._gallery_seeder_app = app  # Store app instance for later access
            
            # Ensure window stays visible
            self._gallery_seeder_window.lift()
            self._gallery_seeder_window.focus_force()
            
            self.log_message("✓ Opened Player Gallery Seeder - Tag players for cross-video recognition")
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import player_gallery_seeder.py: {str(e)}\n\n"
                               "Make sure player_gallery_seeder.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Player Gallery Seeder: {str(e)}")
    
    def open_video_splicer(self):
        """Open Video Splicer tool"""
        try:
            # Check if window already exists
            if hasattr(self, '_video_splicer_window') and self._video_splicer_window and self._video_splicer_window.winfo_exists():
                self._video_splicer_window.lift()
                self._video_splicer_window.focus_force()
                return
            
            from video_splicer import VideoSplicer
            
            self._video_splicer_window = tk.Toplevel(self.root)
            self._video_splicer_window.title("Video Splicer")
            self._video_splicer_window.geometry("800x950")
            self._video_splicer_window.transient(self.root)
            
            # Create VideoSplicer instance
            splicer = VideoSplicer()
            
            # Create UI
            self._create_video_splicer_ui(self._video_splicer_window, splicer)
            
            # Ensure window stays visible
            self._video_splicer_window.lift()
            self._video_splicer_window.focus_force()
            
            self.log_message("✓ Opened Video Splicer - Split videos into smaller chunks")
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import video_splicer.py: {str(e)}\n\n"
                               "Make sure video_splicer.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Video Splicer: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _create_video_splicer_ui(self, parent, splicer):
        """Create the video splicer UI"""
        # Create canvas with scrollbar for scrolling
        canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Main container inside canvas
        main_frame = ttk.Frame(canvas, padding="10")
        canvas_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")
        
        # Configure canvas scrolling
        def configure_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        main_frame.bind("<Configure>", configure_scroll_region)
        
        # Make canvas resize with window
        def configure_canvas(event):
            canvas.itemconfig(canvas_window, width=event.width)
        
        canvas.bind("<Configure>", configure_canvas)
        
        # Enable mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Video selection
        video_frame = ttk.LabelFrame(main_frame, text="Video File", padding="10")
        video_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.video_path_var = tk.StringVar()
        ttk.Entry(video_frame, textvariable=self.video_path_var, width=60, state='readonly').pack(side=tk.LEFT, padx=5)
        ttk.Button(video_frame, text="Browse...", command=lambda: self._splicer_load_video(splicer)).pack(side=tk.LEFT, padx=5)
        
        # Video info display
        self.video_info_text = tk.Text(video_frame, height=4, width=70, state='disabled', font=("Courier", 9))
        self.video_info_text.pack(fill=tk.X, pady=(10, 0))
        
        # Split mode selection
        mode_frame = ttk.LabelFrame(main_frame, text="Split Mode", padding="10")
        mode_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.split_mode = tk.StringVar(value="time")
        ttk.Radiobutton(mode_frame, text="Time-based (fixed duration)", variable=self.split_mode, value="time").pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Size-based (fixed file size)", variable=self.split_mode, value="size").pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Manual (custom split points)", variable=self.split_mode, value="manual").pack(anchor=tk.W)
        
        # Split settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Split Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Time-based settings
        self.time_frame = ttk.Frame(settings_frame)
        self.time_frame.pack(fill=tk.X, pady=5)
        ttk.Label(self.time_frame, text="Chunk Duration:").pack(side=tk.LEFT, padx=5)
        self.chunk_duration_var = tk.DoubleVar(value=5.0)
        ttk.Spinbox(self.time_frame, from_=0.1, to=60.0, increment=0.5, textvariable=self.chunk_duration_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(self.time_frame, text="minutes").pack(side=tk.LEFT, padx=5)
        
        # Size-based settings
        self.size_frame = ttk.Frame(settings_frame)
        self.size_frame.pack(fill=tk.X, pady=5)
        ttk.Label(self.size_frame, text="Chunk Size:").pack(side=tk.LEFT, padx=5)
        self.chunk_size_var = tk.DoubleVar(value=500.0)
        ttk.Spinbox(self.size_frame, from_=10, to=2000, increment=50, textvariable=self.chunk_size_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(self.size_frame, text="MB").pack(side=tk.LEFT, padx=5)
        
        # Manual settings
        manual_container = ttk.Frame(settings_frame)
        manual_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        ttk.Label(manual_container, text="Split Points (seconds, one per line):").pack(anchor=tk.W)
        self.split_points_text = tk.Text(manual_container, height=6, width=40)
        self.split_points_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Output settings
        output_frame = ttk.LabelFrame(main_frame, text="Output Settings", padding="10")
        output_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Resolution
        res_frame = ttk.Frame(output_frame)
        res_frame.pack(fill=tk.X, pady=5)
        ttk.Label(res_frame, text="Resolution:").pack(side=tk.LEFT, padx=5)
        self.resolution_var = tk.StringVar(value="Original")
        resolution_combo = ttk.Combobox(res_frame, textvariable=self.resolution_var, 
                                        values=["Original", "1080p (1920x1080)", "720p (1280x720)", "480p (854x480)", "Custom"],
                                        state="readonly", width=20)
        resolution_combo.pack(side=tk.LEFT, padx=5)
        
        # Custom resolution
        self.custom_res_frame = ttk.Frame(output_frame)
        ttk.Label(self.custom_res_frame, text="Custom:").pack(side=tk.LEFT, padx=5)
        self.custom_width_var = tk.IntVar(value=1920)
        self.custom_height_var = tk.IntVar(value=1080)
        ttk.Spinbox(self.custom_res_frame, from_=320, to=7680, textvariable=self.custom_width_var, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Label(self.custom_res_frame, text="x").pack(side=tk.LEFT)
        ttk.Spinbox(self.custom_res_frame, from_=240, to=4320, textvariable=self.custom_height_var, width=8).pack(side=tk.LEFT, padx=2)
        resolution_combo.bind("<<ComboboxSelected>>", lambda e: self._update_resolution_ui())
        
        # Frame rate
        fps_frame = ttk.Frame(output_frame)
        fps_frame.pack(fill=tk.X, pady=5)
        ttk.Label(fps_frame, text="Frame Rate:").pack(side=tk.LEFT, padx=5)
        self.fps_var = tk.StringVar(value="Original")
        fps_combo = ttk.Combobox(fps_frame, textvariable=self.fps_var,
                               values=["Original", "60 fps", "30 fps", "24 fps", "Custom"],
                               state="readonly", width=20)
        fps_combo.pack(side=tk.LEFT, padx=5)
        
        # Custom FPS
        self.custom_fps_frame = ttk.Frame(output_frame)
        ttk.Label(self.custom_fps_frame, text="Custom FPS:").pack(side=tk.LEFT, padx=5)
        self.custom_fps_var = tk.DoubleVar(value=30.0)
        ttk.Spinbox(self.custom_fps_frame, from_=1.0, to=120.0, increment=1.0, textvariable=self.custom_fps_var, width=10).pack(side=tk.LEFT, padx=5)
        fps_combo.bind("<<ComboboxSelected>>", lambda e: self._update_fps_ui())
        
        # Output directory
        dir_frame = ttk.Frame(output_frame)
        dir_frame.pack(fill=tk.X, pady=5)
        ttk.Label(dir_frame, text="Output Directory:").pack(side=tk.LEFT, padx=5)
        self.output_dir_var = tk.StringVar()
        ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="Browse...", command=self._splicer_browse_output_dir).pack(side=tk.LEFT, padx=5)
        
        # Estimate display
        estimate_frame = ttk.Frame(output_frame)
        estimate_frame.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(estimate_frame, text="Estimated Output Files:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        self.estimate_label = ttk.Label(estimate_frame, text="Load a video to see estimate", 
                                        foreground="blue", font=("Arial", 9))
        self.estimate_label.pack(side=tk.LEFT, padx=5)
        
        # Progress and status
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.splicer_progress_var = tk.DoubleVar(value=0.0)
        self.splicer_progress_bar = ttk.Progressbar(progress_frame, variable=self.splicer_progress_var, maximum=100.0)
        self.splicer_progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        self.splicer_status_text = scrolledtext.ScrolledText(progress_frame, height=8, width=70, state='disabled', font=("Courier", 9))
        self.splicer_status_text.pack(fill=tk.BOTH, expand=True)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.splicer_start_button = ttk.Button(button_frame, text="Start Splitting", 
                                              command=lambda: self._splicer_start(splicer), state=tk.DISABLED)
        self.splicer_start_button.pack(side=tk.LEFT, padx=5)
        
        self.splicer_stop_button = ttk.Button(button_frame, text="Stop", 
                                              command=lambda: self._splicer_stop(splicer), state=tk.DISABLED)
        self.splicer_stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Close", command=parent.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Store references
        self._splicer = splicer
        self._splicer_processing = False
        
        # Update UI based on mode
        self.split_mode.trace('w', lambda *args: self._update_split_mode_ui())
        self._update_split_mode_ui()
        self._update_resolution_ui()
        self._update_fps_ui()
        
        # Set up trace callbacks to update estimate when settings change
        self.chunk_duration_var.trace('w', lambda *args: self._update_estimate(splicer))
        self.chunk_size_var.trace('w', lambda *args: self._update_estimate(splicer))
        self.resolution_var.trace('w', lambda *args: (self._update_resolution_ui(), self._update_estimate(splicer)))
        self.custom_width_var.trace('w', lambda *args: self._update_estimate(splicer))
        self.custom_height_var.trace('w', lambda *args: self._update_estimate(splicer))
        self.fps_var.trace('w', lambda *args: (self._update_fps_ui(), self._update_estimate(splicer)))
        self.custom_fps_var.trace('w', lambda *args: self._update_estimate(splicer))
        
        # Bind text changes for manual split points
        self.split_points_text.bind('<KeyRelease>', lambda e: self._update_estimate(splicer))
        self.split_points_text.bind('<ButtonRelease>', lambda e: self._update_estimate(splicer))
    
    def _update_label_type_ui(self):
        """Show/hide custom text entry based on label type selection"""
        if hasattr(self, 'custom_label_frame'):
            if self.label_type.get() == "custom":
                self.custom_label_frame.grid()
            else:
                self.custom_label_frame.grid_remove()
    
    def _update_split_mode_ui(self):
        """Update UI based on selected split mode"""
        mode = self.split_mode.get()
        self.time_frame.pack_forget() if mode != "time" else self.time_frame.pack(fill=tk.X, pady=5)
        self.size_frame.pack_forget() if mode != "size" else self.size_frame.pack(fill=tk.X, pady=5)
        # Manual frame is always visible (split_points_text)
        # Update estimate when mode changes
        if hasattr(self, '_splicer'):
            self._update_estimate(self._splicer)
    
    def _update_resolution_ui(self):
        """Update resolution UI based on selection"""
        if self.resolution_var.get() == "Custom":
            self.custom_res_frame.pack(fill=tk.X, pady=5)
        else:
            self.custom_res_frame.pack_forget()
    
    def _update_fps_ui(self):
        """Update FPS UI based on selection"""
        if self.fps_var.get() == "Custom":
            self.custom_fps_frame.pack(fill=tk.X, pady=5)
        else:
            self.custom_fps_frame.pack_forget()
    
    def _update_estimate(self, splicer):
        """Calculate and display estimated number of output files"""
        if not hasattr(self, 'estimate_label'):
            return
        
        # Check if video is loaded
        info = splicer.get_video_info()
        if not info:
            self.estimate_label.config(text="Load a video to see estimate", foreground="blue")
            return
        
        try:
            import numpy as np
            
            # Get output resolution
            out_width = info['width']
            out_height = info['height']
            if self.resolution_var.get() != "Original":
                if self.resolution_var.get() == "Custom":
                    out_width = self.custom_width_var.get()
                    out_height = self.custom_height_var.get()
                else:
                    res_map = {
                        "1080p (1920x1080)": (1920, 1080),
                        "720p (1280x720)": (1280, 720),
                        "480p (854x480)": (854, 480)
                    }
                    res = res_map.get(self.resolution_var.get())
                    if res:
                        out_width, out_height = res
            
            # Get output FPS
            out_fps = info['fps']
            if self.fps_var.get() != "Original":
                if self.fps_var.get() == "Custom":
                    out_fps = self.custom_fps_var.get()
                else:
                    fps_map = {
                        "60 fps": 60.0,
                        "30 fps": 30.0,
                        "24 fps": 24.0
                    }
                    out_fps = fps_map.get(self.fps_var.get(), info['fps'])
            
            mode = self.split_mode.get()
            total_duration = info['duration_seconds']
            total_size_mb = info['file_size_mb']
            
            if mode == "time":
                # Time-based: simple division
                chunk_duration_minutes = self.chunk_duration_var.get()
                chunk_duration_seconds = chunk_duration_minutes * 60.0
                if chunk_duration_seconds > 0:
                    num_files = int(np.ceil(total_duration / chunk_duration_seconds))
                    estimate_text = f"~{num_files} files (based on {chunk_duration_minutes:.1f} min chunks)"
                else:
                    estimate_text = "Invalid chunk duration"
                    
            elif mode == "size":
                # Size-based: estimate based on bitrate scaling
                chunk_size_mb = self.chunk_size_var.get()
                if chunk_size_mb > 0 and total_duration > 0:
                    # Estimate bitrate (MB per second) from original
                    mb_per_second = total_size_mb / total_duration
                    
                    # Adjust for resolution change
                    resolution_scale = (out_width * out_height) / (info['width'] * info['height'])
                    mb_per_second *= resolution_scale
                    
                    # Adjust for FPS change
                    fps_scale = out_fps / info['fps']
                    mb_per_second *= fps_scale
                    
                    # Calculate chunk duration
                    chunk_duration_seconds = chunk_size_mb / mb_per_second if mb_per_second > 0 else 60.0
                    
                    # Calculate number of files
                    num_files = int(np.ceil(total_duration / chunk_duration_seconds))
                    chunk_duration_minutes = chunk_duration_seconds / 60.0
                    estimate_text = f"~{num_files} files (~{chunk_duration_minutes:.1f} min per chunk at {out_width}x{out_height} @ {out_fps:.1f} fps)"
                else:
                    estimate_text = "Invalid chunk size"
                    
            else:  # manual
                # Manual: count split points
                split_text = self.split_points_text.get(1.0, tk.END).strip()
                split_points = [float(x.strip()) for x in split_text.split('\n') if x.strip() and x.strip().replace('.', '').replace('-', '').isdigit()]
                num_files = len(split_points) + 1
                estimate_text = f"{num_files} files ({len(split_points)} split point{'s' if len(split_points) != 1 else ''})"
            
            self.estimate_label.config(text=estimate_text, foreground="green")
            
        except Exception as e:
            self.estimate_label.config(text=f"Error calculating estimate: {str(e)}", foreground="red")
    
    def _splicer_load_video(self, splicer):
        """Load video file for splicing"""
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            if splicer.load_video(file_path):
                self.video_path_var.set(file_path)
                info = splicer.get_video_info()
                
                # Display video info
                self.video_info_text.config(state='normal')
                self.video_info_text.delete(1.0, tk.END)
                info_text = f"Duration: {info['duration_seconds']:.1f} seconds ({info['duration_seconds']/60:.1f} minutes)\n"
                info_text += f"Size: {info['file_size_mb']:.1f} MB\n"
                info_text += f"Resolution: {info['width']}x{info['height']}\n"
                info_text += f"Frame Rate: {info['fps']:.2f} fps"
                self.video_info_text.insert(1.0, info_text)
                self.video_info_text.config(state='disabled')
                
                # Set default output directory
                if not self.output_dir_var.get():
                    output_dir = os.path.join(os.path.dirname(file_path), "spliced")
                    self.output_dir_var.set(output_dir)
                
                self.splicer_start_button.config(state=tk.NORMAL)
                self._splicer_log("✓ Video loaded successfully")
                self._update_estimate(splicer)
            else:
                messagebox.showerror("Error", "Could not load video file")
        except Exception as e:
            messagebox.showerror("Error", f"Error loading video: {str(e)}")
    
    def _splicer_browse_output_dir(self):
        """Browse for output directory"""
        dir_path = filedialog.askdirectory(title="Select Output Directory")
        if dir_path:
            self.output_dir_var.set(dir_path)
    
    def _splicer_log(self, message):
        """Add message to status log"""
        self.splicer_status_text.config(state='normal')
        self.splicer_status_text.insert(tk.END, message + "\n")
        self.splicer_status_text.see(tk.END)
        self.splicer_status_text.config(state='disabled')
    
    def _splicer_progress_callback(self, message, percent):
        """Progress callback for video splicer"""
        if message:
            self._splicer_log(message)
        if percent is not None:
            self.splicer_progress_var.set(percent)
            self._video_splicer_window.update_idletasks()
    
    def _splicer_start(self, splicer):
        """Start video splitting"""
        if not self.video_path_var.get():
            messagebox.showerror("Error", "Please select a video file first")
            return
        
        output_dir = self.output_dir_var.get()
        if not output_dir:
            messagebox.showerror("Error", "Please select an output directory")
            return
        
        try:
            # Get resolution
            resolution = None
            if self.resolution_var.get() != "Original":
                if self.resolution_var.get() == "Custom":
                    resolution = (self.custom_width_var.get(), self.custom_height_var.get())
                else:
                    # Parse resolution string
                    res_map = {
                        "1080p (1920x1080)": (1920, 1080),
                        "720p (1280x720)": (1280, 720),
                        "480p (854x480)": (854, 480)
                    }
                    resolution = res_map.get(self.resolution_var.get())
            
            # Get FPS
            fps = None
            if self.fps_var.get() != "Original":
                if self.fps_var.get() == "Custom":
                    fps = self.custom_fps_var.get()
                else:
                    fps_map = {
                        "60 fps": 60.0,
                        "30 fps": 30.0,
                        "24 fps": 24.0
                    }
                    fps = fps_map.get(self.fps_var.get())
            
            # Set progress callback
            splicer.set_progress_callback(self._splicer_progress_callback)
            
            # Disable start button
            self.splicer_start_button.config(state=tk.DISABLED)
            self.splicer_stop_button.config(state=tk.NORMAL)
            self._splicer_processing = True
            
            # Run in thread
            def split_thread():
                try:
                    mode = self.split_mode.get()
                    
                    if mode == "time":
                        duration_minutes = self.chunk_duration_var.get()
                        duration_seconds = duration_minutes * 60.0
                        output_files = splicer.split_by_time(duration_seconds, output_dir, resolution, fps)
                    elif mode == "size":
                        size_mb = self.chunk_size_var.get()
                        output_files = splicer.split_by_size(size_mb, output_dir, resolution, fps)
                    else:  # manual
                        split_text = self.split_points_text.get(1.0, tk.END).strip()
                        split_points = [float(x.strip()) for x in split_text.split('\n') if x.strip()]
                        output_files = splicer.split_manual(split_points, output_dir, resolution, fps)
                    
                    # Success
                    self._video_splicer_window.after(0, lambda: self._splicer_complete(output_files))
                    
                except Exception as e:
                    self._video_splicer_window.after(0, lambda: self._splicer_error(str(e)))
            
            import threading
            thread = threading.Thread(target=split_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error starting split: {str(e)}")
            self.splicer_start_button.config(state=tk.NORMAL)
            self.splicer_stop_button.config(state=tk.DISABLED)
            self._splicer_processing = False
    
    def _splicer_complete(self, output_files):
        """Handle completion of video splitting"""
        self._splicer_processing = False
        self.splicer_start_button.config(state=tk.NORMAL)
        self.splicer_stop_button.config(state=tk.DISABLED)
        
        message = f"✓ Successfully created {len(output_files)} video chunks!"
        self._splicer_log(message)
        messagebox.showinfo("Success", message)
    
    def _splicer_error(self, error_msg):
        """Handle error during video splitting"""
        self._splicer_processing = False
        self.splicer_start_button.config(state=tk.NORMAL)
        self.splicer_stop_button.config(state=tk.DISABLED)
        
        self._splicer_log(f"✗ Error: {error_msg}")
        messagebox.showerror("Error", f"Video splitting failed:\n\n{error_msg}")
    
    def _splicer_stop(self, splicer):
        """Stop video splitting (placeholder - would need to implement cancellation)"""
        self._splicer_log("⚠ Stop requested (current chunk will finish)")
        # Note: Full cancellation would require more complex implementation
    
    def _create_gallery_tab(self, parent_frame):
        """Create the player gallery tab content"""
        try:
            from player_gallery import PlayerGallery
            
            gallery = PlayerGallery()
            stats = gallery.get_stats()
            players = gallery.list_players()
            
            # Main container with scrollbar
            main_container = ttk.Frame(parent_frame)
            main_container.pack(fill=tk.BOTH, expand=True)
            
            # Top info section
            info_frame = ttk.Frame(main_container)
            info_frame.pack(fill=tk.X, pady=(0, 15))
            
            # Title and description
            title_frame = ttk.Frame(info_frame)
            title_frame.pack(fill=tk.X)
            
            ttk.Label(title_frame, text="Player Gallery", font=("Arial", 16, "bold")).pack(side=tk.LEFT)
            ttk.Label(title_frame, text="  Cross-Video Player Recognition", 
                     font=("Arial", 10), foreground="gray").pack(side=tk.LEFT, padx=10)
            
            # Statistics box
            stats_frame = ttk.LabelFrame(info_frame, text="Gallery Statistics", padding="10")
            stats_frame.pack(fill=tk.X, pady=(10, 0))
            
            stats_grid = ttk.Frame(stats_frame)
            stats_grid.pack(fill=tk.X)
            
            ttk.Label(stats_grid, text="Total Players:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=5)
            ttk.Label(stats_grid, text=str(stats['total_players']), font=("Arial", 9)).grid(row=0, column=1, sticky=tk.W)
            
            ttk.Label(stats_grid, text="With Re-ID Features:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky=tk.W, padx=5)
            ttk.Label(stats_grid, text=str(stats['players_with_features']), font=("Arial", 9), 
                     foreground="green" if stats['players_with_features'] > 0 else "red").grid(row=1, column=1, sticky=tk.W)
            
            ttk.Label(stats_grid, text="With Reference Frames:", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky=tk.W, padx=5)
            ttk.Label(stats_grid, text=str(stats['players_with_reference_frames']), font=("Arial", 9)).grid(row=2, column=1, sticky=tk.W)
            
            ttk.Label(stats_grid, text="Gallery File:", font=("Arial", 9, "bold")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=(5, 0))
            ttk.Label(stats_grid, text=stats['gallery_path'], font=("Arial", 8), 
                     foreground="blue").grid(row=3, column=1, sticky=tk.W, columnspan=2, pady=(5, 0))
            
            # Action buttons
            button_frame = ttk.Frame(info_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            ttk.Button(button_frame, text="➕ Add New Player", 
                      command=lambda: self._add_new_player_to_gallery(parent_frame), width=18).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="📸 Tag New Players", 
                      command=self.open_player_gallery_seeder, width=18).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🔧 Backfill Features", 
                      command=self.backfill_gallery_features, width=18).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🔍 Match Unnamed Anchors", 
                      command=self.match_unnamed_anchor_frames, width=28).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🧹 Remove False Matches", 
                      command=lambda: self.remove_false_matches_from_gallery(parent_frame), width=28).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🗑️ Remove Missing Frames", 
                      command=lambda: self.remove_missing_reference_frames(parent_frame), width=28).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🗑️ Delete Selected", 
                      command=lambda: self._delete_selected_player_from_gallery(parent_frame, listbox, player_list_data), width=18).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🔄 Refresh", 
                      command=lambda: self._refresh_gallery_tab(parent_frame), width=12).pack(side=tk.LEFT, padx=5)
            
            # Player list
            list_frame = ttk.LabelFrame(main_container, text="Players in Gallery", padding="10")
            list_frame.pack(fill=tk.BOTH, expand=True)
            
            # Create scrollable listbox
            list_container = ttk.Frame(list_frame)
            list_container.pack(fill=tk.BOTH, expand=True)
            
            scrollbar = ttk.Scrollbar(list_container)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            listbox = tk.Listbox(list_container, yscrollcommand=scrollbar.set, 
                                font=("Courier New", 10), height=20)
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            
            # Store player list for selection handling
            player_list_data = []
            
            # Populate list
            if players:
                listbox.insert(tk.END, "✓/✗  Player Name                Jersey  Team      Ref Frames  Confidence")
                listbox.insert(tk.END, "─" * 95)
                
                for player_id, player_name in players:
                    profile = gallery.get_player(player_id)
                    jersey = f"#{profile.jersey_number:>3}" if profile.jersey_number else "    "
                    team = f"{profile.team[:10]:10}" if profile.team else " " * 10
                    has_features = "✓" if profile.features is not None else "✗"
                    
                    # Get reference frame count
                    ref_frames_count = len(profile.reference_frames) if profile.reference_frames else 0
                    ref_frames_display = f"{ref_frames_count:>4}"
                    
                    # Get confidence metrics
                    confidence_metrics = gallery.get_player_confidence_metrics(player_id)
                    overall_conf = confidence_metrics['overall_confidence']
                    
                    # Color-code confidence (high=green, medium=yellow, low=red)
                    if overall_conf >= 0.7:
                        conf_display = f"High ({overall_conf:.2f})"
                        conf_color = "green"
                    elif overall_conf >= 0.4:
                        conf_display = f"Med ({overall_conf:.2f})"
                        conf_color = "orange"
                    else:
                        conf_display = f"Low ({overall_conf:.2f})"
                        conf_color = "red"
                    
                    line = f" {has_features}  {player_name:30} {jersey}  {team}  {ref_frames_display:>11}  {conf_display:15}"
                    listbox.insert(tk.END, line)
                    # Tag with color for confidence
                    if overall_conf >= 0.7:
                        listbox.itemconfig(listbox.size() - 1, {'fg': 'green'})
                    elif overall_conf >= 0.4:
                        listbox.itemconfig(listbox.size() - 1, {'fg': 'orange'})
                    else:
                        listbox.itemconfig(listbox.size() - 1, {'fg': 'red'})
                    
                    player_list_data.append((player_id, player_name))
                
                # Add double-click handler to view player details
                def on_player_select(event):
                    selection = listbox.curselection()
                    if selection and len(selection) > 0:
                        index = selection[0]
                        # Skip header rows (0 and 1)
                        if index > 1 and (index - 2) < len(player_list_data):
                            player_id, player_name = player_list_data[index - 2]
                            self._show_player_details(gallery, player_id, parent_frame)
                
                listbox.bind('<Double-Button-1>', on_player_select)
                
                # Right-click context menu for delete
                context_menu = tk.Menu(listbox, tearoff=0)
                
                def show_context_menu(event):
                    selection = listbox.curselection()
                    if selection and len(selection) > 0:
                        index = selection[0]
                        if index > 1 and (index - 2) < len(player_list_data):
                            # Clear existing menu items
                            context_menu.delete(0, tk.END)
                            
                            # Store index in closure
                            selected_index = index
                            
                            # Add menu items with proper closures
                            context_menu.add_command(label="View/Edit Details", 
                                                   command=lambda: self._show_player_details_from_list(listbox, player_list_data, gallery, parent_frame, selected_index))
                            context_menu.add_separator()
                            context_menu.add_command(label="🗑️ Delete Player", 
                                                   command=lambda: self._delete_selected_player_from_gallery(parent_frame, listbox, player_list_data, selected_index))
                            
                            try:
                                context_menu.tk_popup(event.x_root, event.y_root)
                            finally:
                                context_menu.grab_release()
                
                listbox.bind('<Button-3>', show_context_menu)  # Right-click
            else:
                listbox.insert(tk.END, "")
                listbox.insert(tk.END, "  No players in gallery yet!")
                listbox.insert(tk.END, "")
                listbox.insert(tk.END, "  Click 'Tag New Players' to add players for")
                listbox.insert(tk.END, "  cross-video recognition.")
            
            # Legend
            legend_text = """
Legend:
  ✓ = Player has Re-ID features (will be auto-recognized in videos)
  ✗ = Player without features (manual identification only)
  
Double-click a player to view/edit details
Right-click for context menu (Delete, etc.)
To add players: Click 'Tag New Players' button above
"""
            ttk.Label(list_frame, text=legend_text, justify=tk.LEFT, 
                     foreground="gray", font=("Arial", 8)).pack(pady=(10, 0))
            
        except ImportError as e:
            ttk.Label(parent_frame, 
                     text=f"⚠ Player Gallery not available\n\n{str(e)}\n\nMake sure player_gallery.py is in the same folder.",
                     justify=tk.CENTER, font=("Arial", 10)).pack(expand=True)
        except Exception as e:
            ttk.Label(parent_frame, 
                     text=f"Error loading Player Gallery:\n\n{str(e)}",
                     justify=tk.CENTER, font=("Arial", 10)).pack(expand=True)
    
    def _create_roster_tab(self, parent_frame):
        """Create the team roster management tab"""
        try:
            from team_roster_manager import TeamRosterManager
            
            # Initialize roster manager
            roster_manager = TeamRosterManager()
            
            # Main container
            main_container = ttk.Frame(parent_frame)
            main_container.pack(fill=tk.BOTH, expand=True)
            
            # Top controls
            controls_frame = ttk.LabelFrame(main_container, text="Roster Management", padding="10")
            controls_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Import/Export buttons
            import_export_frame = ttk.Frame(controls_frame)
            import_export_frame.pack(fill=tk.X, pady=5)
            
            ttk.Button(import_export_frame, text="📥 Import from CSV", 
                      command=lambda: self._import_roster_csv(roster_manager, parent_frame)).pack(side=tk.LEFT, padx=5)
            ttk.Button(import_export_frame, text="📤 Export to CSV", 
                      command=lambda: self._export_roster_csv(roster_manager)).pack(side=tk.LEFT, padx=5)
            ttk.Button(import_export_frame, text="➕ Add Player", 
                      command=lambda: self._add_roster_player(roster_manager, parent_frame)).pack(side=tk.LEFT, padx=5)
            ttk.Button(import_export_frame, text="🔄 Refresh", 
                      command=lambda: self._refresh_roster_tab(parent_frame)).pack(side=tk.LEFT, padx=5)
            
            # Video linking
            link_frame = ttk.LabelFrame(controls_frame, text="Link Video to Roster", padding="10")
            link_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(link_frame, text="Select video and players to link:").pack(side=tk.LEFT, padx=5)
            ttk.Button(link_frame, text="🔗 Link Video", 
                      command=lambda: self._link_video_to_roster(roster_manager)).pack(side=tk.LEFT, padx=5)
            
            # Roster list
            list_frame = ttk.LabelFrame(main_container, text="Team Roster", padding="10")
            list_frame.pack(fill=tk.BOTH, expand=True)
            
            # Scrollable listbox
            list_container = ttk.Frame(list_frame)
            list_container.pack(fill=tk.BOTH, expand=True)
            
            scrollbar = ttk.Scrollbar(list_container)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            listbox = tk.Listbox(list_container, yscrollcommand=scrollbar.set,
                                font=("Courier New", 10), height=20)
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            
            # Store roster data
            roster_list_data = []
            
            # Populate roster
            self._populate_roster_list(listbox, roster_manager, roster_list_data)
            
            # Right-click context menu
            context_menu = tk.Menu(listbox, tearoff=0)
            
            def show_context_menu(event):
                selection = listbox.curselection()
                if selection and len(selection) > 0:
                    index = selection[0]
                    if index > 1 and (index - 2) < len(roster_list_data):
                        context_menu.delete(0, tk.END)
                        selected_index = index
                        player_name = roster_list_data[selected_index - 2]
                        context_menu.add_command(label="✏️ Edit Player", 
                                               command=lambda: self._edit_roster_player(roster_manager, player_name, parent_frame))
                        context_menu.add_separator()
                        context_menu.add_command(label="🗑️ Delete Player", 
                                               command=lambda: self._delete_roster_player(roster_manager, player_name, parent_frame))
                        try:
                            context_menu.tk_popup(event.x_root, event.y_root)
                        finally:
                            context_menu.grab_release()
            
            listbox.bind('<Button-3>', show_context_menu)
            
            # Store references for refresh
            parent_frame._roster_manager = roster_manager
            parent_frame._roster_listbox = listbox
            parent_frame._roster_list_data = roster_list_data
            
        except ImportError as e:
            ttk.Label(parent_frame, 
                     text=f"⚠ Team Roster Manager not available\n\n{str(e)}\n\nMake sure team_roster_manager.py is in the same folder.",
                     justify=tk.CENTER, font=("Arial", 10)).pack(expand=True)
        except Exception as e:
            ttk.Label(parent_frame, 
                     text=f"Error loading Team Roster:\n\n{str(e)}",
                     justify=tk.CENTER, font=("Arial", 10)).pack(expand=True)
    
    def _populate_roster_list(self, listbox, roster_manager, roster_list_data):
        """Populate the roster listbox"""
        listbox.delete(0, tk.END)
        roster_list_data.clear()
        
        roster = roster_manager.roster
        if not roster or (len(roster) == 1 and 'videos' in roster):
            listbox.insert(tk.END, "")
            listbox.insert(tk.END, "  No players in roster yet!")
            listbox.insert(tk.END, "")
            listbox.insert(tk.END, "  Click 'Add Player' or 'Import from CSV' to add players.")
            return
        
        # Header
        listbox.insert(tk.END, "Name                    Jersey    Team            Position    Active")
        listbox.insert(tk.END, "─" * 80)
        
        # Sort players by name
        players = [(name, data) for name, data in roster.items() if name != 'videos']
        players.sort(key=lambda x: x[0])
        
        for player_name, player_data in players:
            jersey = player_data.get('jersey_number', '') or ''
            team = (player_data.get('team', '') or '')[:15]
            position = (player_data.get('position', '') or '')[:10]
            active = "Yes" if player_data.get('active', True) else "No"
            
            line = f"{player_name:23} {jersey:8} {team:15} {position:10} {active:6}"
            listbox.insert(tk.END, line)
            roster_list_data.append(player_name)
    
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
    
    def _add_roster_player(self, roster_manager, parent_frame):
        """Add a new player to the roster"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Player to Roster")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Add Player", font=("Arial", 14, "bold")).pack(pady=(0, 20))
        
        form_frame = ttk.Frame(main_frame)
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
        viz_frame = ttk.LabelFrame(form_frame, text="Visualization Settings (Optional)", padding="5")
        viz_frame.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=5, padx=5)
        
        # Custom color - Color Picker
        from color_picker_utils import create_color_picker_widget
        custom_color_var = tk.StringVar()
        color_picker_frame, _ = create_color_picker_widget(
            viz_frame,
            custom_color_var,
            label_text="Custom Color:",
            initial_color=None,
            on_change_callback=None
        )
        color_picker_frame.grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        
        # Box thickness
        ttk.Label(viz_frame, text="Box Thickness:").grid(row=1, column=0, sticky=tk.W, padx=5)
        box_thickness_var = tk.IntVar(value=2)
        ttk.Spinbox(viz_frame, from_=1, to=10, textvariable=box_thickness_var, width=10).grid(row=1, column=1, padx=5, sticky=tk.W)
        
        # Show glow
        show_glow_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(viz_frame, text="Show Glow Effect", variable=show_glow_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        # Glow intensity
        ttk.Label(viz_frame, text="Glow Intensity:").grid(row=3, column=0, sticky=tk.W, padx=5)
        glow_intensity_var = tk.IntVar(value=50)
        ttk.Spinbox(viz_frame, from_=0, to=100, textvariable=glow_intensity_var, width=10).grid(row=3, column=1, padx=5, sticky=tk.W)
        
        # Show trail
        show_trail_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(viz_frame, text="Show Movement Trail", variable=show_trail_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        # Label style
        ttk.Label(viz_frame, text="Label Style:").grid(row=5, column=0, sticky=tk.W, padx=5)
        label_style_var = tk.StringVar(value="full_name")
        ttk.Combobox(viz_frame, textvariable=label_style_var, 
                    values=["full_name", "jersey", "initials", "number"], 
                    width=12, state="readonly").grid(row=5, column=1, padx=5, sticky=tk.W)
        
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
                    from team_roster_manager import TeamRosterManager
                    roster_manager_temp = TeamRosterManager()
                    rgb = roster_manager_temp._parse_color_string(custom_color_str)
                    if rgb:
                        viz_settings["use_custom_color"] = True
                        viz_settings["custom_color_rgb"] = rgb
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
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Add", command=add).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _edit_roster_player(self, roster_manager, player_name, parent_frame):
        """Edit a player in the roster"""
        player_data = roster_manager.roster.get(player_name, {})
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Player: {player_name}")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=f"Edit: {player_name}", font=("Arial", 14, "bold")).pack(pady=(0, 20))
        
        form_frame = ttk.Frame(main_frame)
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
        viz_frame = ttk.LabelFrame(form_frame, text="Visualization Settings (Optional)", padding="5")
        viz_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=5, padx=5)
        
        # Load existing visualization settings
        viz = player_data.get("visualization_settings", {})
        
        # Custom color - Color Picker
        from color_picker_utils import create_color_picker_widget
        custom_color_var = tk.StringVar()
        initial_color = None
        if viz.get("custom_color_rgb"):
            rgb = viz["custom_color_rgb"]
            if isinstance(rgb, list) and len(rgb) == 3:
                initial_color = tuple(rgb)
                custom_color_var.set(f"{rgb[0]},{rgb[1]},{rgb[2]}")
        color_picker_frame, _ = create_color_picker_widget(
            viz_frame,
            custom_color_var,
            label_text="Custom Color:",
            initial_color=initial_color,
            on_change_callback=None
        )
        color_picker_frame.grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        
        # Box thickness
        ttk.Label(viz_frame, text="Box Thickness:").grid(row=1, column=0, sticky=tk.W, padx=5)
        box_thickness_var = tk.IntVar(value=viz.get("box_thickness", 2))
        ttk.Spinbox(viz_frame, from_=1, to=10, textvariable=box_thickness_var, width=10).grid(row=1, column=1, padx=5, sticky=tk.W)
        
        # Show glow
        show_glow_var = tk.BooleanVar(value=viz.get("show_glow", False))
        ttk.Checkbutton(viz_frame, text="Show Glow Effect", variable=show_glow_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        # Glow intensity
        ttk.Label(viz_frame, text="Glow Intensity:").grid(row=3, column=0, sticky=tk.W, padx=5)
        glow_intensity_var = tk.IntVar(value=viz.get("glow_intensity", 50))
        ttk.Spinbox(viz_frame, from_=0, to=100, textvariable=glow_intensity_var, width=10).grid(row=3, column=1, padx=5, sticky=tk.W)
        
        # Show trail
        show_trail_var = tk.BooleanVar(value=viz.get("show_trail", False))
        ttk.Checkbutton(viz_frame, text="Show Movement Trail", variable=show_trail_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        # Label style
        ttk.Label(viz_frame, text="Label Style:").grid(row=5, column=0, sticky=tk.W, padx=5)
        label_style_var = tk.StringVar(value=viz.get("label_style", "full_name"))
        ttk.Combobox(viz_frame, textvariable=label_style_var, 
                    values=["full_name", "jersey", "initials", "number"], 
                    width=12, state="readonly").grid(row=5, column=1, padx=5, sticky=tk.W)
        
        def save():
            # Parse visualization settings
            viz_settings = {}
            custom_color_str = custom_color_var.get().strip()
            if custom_color_str:
                try:
                    from team_roster_manager import TeamRosterManager
                    roster_manager_temp = TeamRosterManager()
                    rgb = roster_manager_temp._parse_color_string(custom_color_str)
                    if rgb:
                        viz_settings["use_custom_color"] = True
                        viz_settings["custom_color_rgb"] = rgb
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
        
        button_frame = ttk.Frame(main_frame)
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
        if not video_path:
            return
        
        # Get list of players
        players = [name for name in roster_manager.roster.keys() if name != 'videos']
        if not players:
            messagebox.showwarning("No Players", "No players in roster to link")
            return
        
        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Link Video to Players")
        dialog.geometry("400x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=f"Link: {os.path.basename(video_path)}", 
                 font=("Arial", 12, "bold")).pack(pady=(0, 10))
        ttk.Label(main_frame, text="Select players in this video:").pack(pady=(0, 10))
        
        # Scrollable listbox with checkboxes
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, selectmode=tk.MULTIPLE)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        for player in sorted(players):
            listbox.insert(tk.END, player)
        
        def link():
            selection = listbox.curselection()
            selected_players = [players[i] for i in selection]
            if selected_players:
                roster_manager.link_video_to_roster(video_path, selected_players)
                messagebox.showinfo("Success", f"Linked video to {len(selected_players)} players")
                dialog.destroy()
            else:
                messagebox.showwarning("No Selection", "Please select at least one player")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Link", command=link).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _refresh_roster_tab(self, parent_frame):
        """Refresh the roster tab"""
        if hasattr(parent_frame, '_roster_manager') and hasattr(parent_frame, '_roster_listbox'):
            self._populate_roster_list(
                parent_frame._roster_listbox,
                parent_frame._roster_manager,
                parent_frame._roster_list_data
            )
    
    def _add_new_player_to_gallery(self, parent_frame):
        """Open dialog to add a new player to the gallery"""
        try:
            from player_gallery import PlayerGallery
            import numpy as np
            
            gallery = PlayerGallery()
            
            # Create dialog window
            dialog = tk.Toplevel(self.root)
            dialog.title("Add New Player")
            dialog.geometry("500x300")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Main frame
            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(main_frame, text="Add New Player to Gallery", 
                     font=("Arial", 14, "bold")).pack(pady=(0, 20))
            
            # Form fields
            form_frame = ttk.Frame(main_frame)
            form_frame.pack(fill=tk.X, pady=10)
            
            # Player Name (required)
            ttk.Label(form_frame, text="Player Name *:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=8)
            name_var = tk.StringVar()
            name_entry = ttk.Entry(form_frame, textvariable=name_var, width=30)
            name_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=8)
            name_entry.focus()
            
            # Jersey Number (optional)
            ttk.Label(form_frame, text="Jersey Number:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=8)
            jersey_var = tk.StringVar()
            jersey_entry = ttk.Entry(form_frame, textvariable=jersey_var, width=30)
            jersey_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=8)
            
            # Team (optional)
            ttk.Label(form_frame, text="Team:", font=("Arial", 10)).grid(row=2, column=0, sticky=tk.W, padx=5, pady=8)
            team_var = tk.StringVar()
            team_entry = ttk.Entry(form_frame, textvariable=team_var, width=30)
            team_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=8)
            
            # Visualization settings section
            viz_frame = ttk.LabelFrame(form_frame, text="Visualization Settings (Optional)", padding="5")
            viz_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=5, padx=5)
            
            # Custom color
            ttk.Label(viz_frame, text="Custom Color (R,G,B):").grid(row=0, column=0, sticky=tk.W, padx=5)
            custom_color_var = tk.StringVar()
            ttk.Entry(viz_frame, textvariable=custom_color_var, width=15).grid(row=0, column=1, padx=5, sticky=tk.W)
            ttk.Label(viz_frame, text="(e.g., 255,0,0 for red)", font=("Arial", 7), foreground="gray").grid(row=0, column=2, sticky=tk.W)
            
            # Box thickness
            ttk.Label(viz_frame, text="Box Thickness:").grid(row=1, column=0, sticky=tk.W, padx=5)
            box_thickness_var = tk.IntVar(value=2)
            ttk.Spinbox(viz_frame, from_=1, to=10, textvariable=box_thickness_var, width=10).grid(row=1, column=1, padx=5, sticky=tk.W)
            
            # Show glow
            show_glow_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(viz_frame, text="Show Glow Effect", variable=show_glow_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5)
            
            # Glow intensity
            ttk.Label(viz_frame, text="Glow Intensity:").grid(row=3, column=0, sticky=tk.W, padx=5)
            glow_intensity_var = tk.IntVar(value=50)
            ttk.Spinbox(viz_frame, from_=0, to=100, textvariable=glow_intensity_var, width=10).grid(row=3, column=1, padx=5, sticky=tk.W)
            
            # Show trail
            show_trail_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(viz_frame, text="Show Movement Trail", variable=show_trail_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5)
            
            # Label style
            ttk.Label(viz_frame, text="Label Style:").grid(row=5, column=0, sticky=tk.W, padx=5)
            label_style_var = tk.StringVar(value="full_name")
            ttk.Combobox(viz_frame, textvariable=label_style_var, 
                        values=["full_name", "jersey", "initials", "number"], 
                        width=12, state="readonly").grid(row=5, column=1, padx=5, sticky=tk.W)
            
            # Info label
            info_label = ttk.Label(main_frame, 
                              text="Note: Player will be added without Re-ID features.\n"
                                   "Use 'Tag New Players' or run analysis to add features later.",
                              font=("Arial", 8), foreground="gray", justify=tk.LEFT)
            info_label.pack(pady=10)
            
            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(20, 0))
            
            def add_player():
                name = name_var.get().strip()
                if not name:
                    messagebox.showerror("Error", "Player name is required!")
                    return
                
                # Check if player already exists
                existing_players = gallery.list_players()
                for player_id, player_name in existing_players:
                    if player_name.lower() == name.lower():
                        messagebox.showerror("Error", f"Player '{name}' already exists in the gallery!")
                        return
                
                try:
                    # Create dummy feature vector (512-dim, all zeros) - will be updated when features are added
                    dummy_features = np.zeros(512, dtype=np.float32)
                    
                    # Parse visualization settings
                    viz_settings = None
                    custom_color_str = custom_color_var.get().strip()
                    if custom_color_str or box_thickness_var.get() != 2 or show_glow_var.get() or show_trail_var.get() or label_style_var.get() != "full_name":
                        viz_settings = {}
                        if custom_color_str:
                            try:
                                from team_roster_manager import TeamRosterManager
                                roster_manager_temp = TeamRosterManager()
                                rgb = roster_manager_temp._parse_color_string(custom_color_str)
                                if rgb:
                                    viz_settings["use_custom_color"] = True
                                    viz_settings["custom_color_rgb"] = rgb
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
                    
                    # Add player to gallery
                    jersey = jersey_var.get().strip() if jersey_var.get().strip() else None
                    team = team_var.get().strip() if team_var.get().strip() else None
                    
                    player_id = gallery.add_player(
                        name=name,
                        features=dummy_features,
                        jersey_number=jersey,
                        team=team,
                        visualization_settings=viz_settings
                    )
                    
                    messagebox.showinfo("Success", f"Player '{name}' added to gallery!\n\n"
                                                  f"You can now:\n"
                                                  f"• Use 'Tag New Players' to add reference images\n"
                                                  f"• Run analysis to automatically add Re-ID features\n"
                                                  f"• Use 'Backfill Features' to extract features from existing videos")
                    
                    dialog.destroy()
                    
                    # Refresh the gallery tab
                    self._refresh_gallery_tab(parent_frame)
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to add player: {e}")
                    import traceback
                    traceback.print_exc()
            
            ttk.Button(button_frame, text="Add Player", command=add_player, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=5)
            
            # Bind Enter key to add player
            name_entry.bind("<Return>", lambda e: add_player())
            jersey_entry.bind("<Return>", lambda e: add_player())
            team_entry.bind("<Return>", lambda e: add_player())
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open add player dialog: {e}")
            import traceback
            traceback.print_exc()
    
    def remove_false_matches_from_gallery(self, parent_frame=None):
        """
        Remove false matches from the player gallery based on similarity and confidence thresholds.
        This helps clean up incorrectly matched images and reference frames.
        """
        try:
            from player_gallery import PlayerGallery
            from tkinter import messagebox
            
            # Ask user for confirmation and threshold settings
            dialog = tk.Toplevel(self.root)
            dialog.title("Remove False Matches")
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.focus_set()
            
            # Set dialog size and position (larger for better button visibility)
            dialog.geometry("600x350")
            dialog.resizable(False, False)
            
            # Center the dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
            y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{x}+{y}")
            
            # Instructions
            info_label = ttk.Label(dialog, 
                                 text="Remove false matches from the gallery.\n"
                                      "This will remove reference frames and images with low similarity/confidence.",
                                 font=("Arial", 9), wraplength=350, justify=tk.LEFT)
            info_label.pack(pady=15, padx=20)
            
            # Threshold settings
            settings_frame = ttk.LabelFrame(dialog, text="Quality Thresholds", padding="15")
            settings_frame.pack(pady=15, padx=25, fill=tk.X)
            
            # Similarity threshold
            ttk.Label(settings_frame, text="Min Similarity:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            similarity_var = tk.DoubleVar(value=0.3)
            similarity_spinbox = ttk.Spinbox(settings_frame, from_=0.0, to=1.0, increment=0.05,
                                           textvariable=similarity_var, width=10)
            similarity_spinbox.grid(row=0, column=1, padx=5, pady=5)
            ttk.Label(settings_frame, text="(lower = more aggressive cleanup)", 
                     font=("Arial", 8), foreground="gray").grid(row=0, column=2, sticky=tk.W, padx=5)
            
            # Confidence threshold
            ttk.Label(settings_frame, text="Min Confidence:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
            confidence_var = tk.DoubleVar(value=0.4)
            confidence_spinbox = ttk.Spinbox(settings_frame, from_=0.0, to=1.0, increment=0.05,
                                            textvariable=confidence_var, width=10)
            confidence_spinbox.grid(row=1, column=1, padx=5, pady=5)
            ttk.Label(settings_frame, text="(lower = more aggressive cleanup)", 
                     font=("Arial", 8), foreground="gray").grid(row=1, column=2, sticky=tk.W, padx=5)
            
            # Warning label
            warning_label = ttk.Label(dialog, 
                                     text="⚠ This action cannot be undone. Make sure you have a backup!",
                                     font=("Arial", 9, "bold"), foreground="red", wraplength=500)
            warning_label.pack(pady=15)
            
            # Buttons - larger size with clear Apply/Confirm button
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=20, padx=20, fill=tk.X)
            
            def execute_cleanup():
                min_similarity = similarity_var.get()
                min_confidence = confidence_var.get()
                
                # Final confirmation
                confirm = messagebox.askyesno(
                    "Confirm Cleanup",
                    f"This will remove all reference frames and images with:\n"
                    f"• Similarity < {min_similarity:.2f}\n"
                    f"• Confidence < {min_confidence:.2f}\n\n"
                    f"Continue?",
                    parent=dialog
                )
                
                if not confirm:
                    return
                
                dialog.destroy()
                
                # Perform cleanup
                try:
                    gallery = PlayerGallery()
                    gallery.remove_false_matches(
                        min_similarity_threshold=min_similarity,
                        min_confidence_threshold=min_confidence
                    )
                    
                    # Show success message
                    messagebox.showinfo(
                        "Cleanup Complete",
                        "False matches have been removed from the gallery.\n"
                        "The gallery has been saved.",
                        parent=self.root
                    )
                    
                    # Refresh gallery tab if it exists
                    if parent_frame is not None:
                        self._refresh_gallery_tab(parent_frame)
                    else:
                        # Try to find and refresh the gallery tab
                        try:
                            if hasattr(self, 'controls_notebook'):
                                for tab_id in self.controls_notebook.tabs():
                                    tab_text = self.controls_notebook.tab(tab_id, "text")
                                    if "Gallery" in tab_text or "Player" in tab_text:
                                        tab_frame = self.controls_notebook.nametowidget(tab_id)
                                        self._refresh_gallery_tab(tab_frame)
                                        break
                        except Exception:
                            pass
                    
                    self.log_message(f"✓ Removed false matches (similarity < {min_similarity:.2f}, confidence < {min_confidence:.2f})")
                    
                except Exception as e:
                    messagebox.showerror(
                        "Error",
                        f"Failed to remove false matches:\n{str(e)}",
                        parent=self.root
                    )
        
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import player_gallery.py: {str(e)}\n\n"
                               "Make sure player_gallery.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not remove false matches: {str(e)}")
    
    def remove_missing_reference_frames(self, parent_frame=None):
        """Remove reference frames that point to missing video files"""
        try:
            from player_gallery import PlayerGallery
            
            gallery = PlayerGallery()
            
            # Ask user to confirm
            response = messagebox.askyesno(
                "Remove Missing Reference Frames",
                "This will scan all players and remove reference frames that point to:\n"
                "• Missing video files (deleted or moved)\n"
                "• Invalid frame numbers\n"
                "• Invalid video paths\n\n"
                "This helps keep the gallery clean and prevents errors.\n\n"
                "Continue?",
                parent=self.root
            )
            
            if not response:
                return
            
            # Show progress
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Removing Missing Frames")
            progress_window.geometry("500x150")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            progress_text = scrolledtext.ScrolledText(progress_window, height=6, wrap=tk.WORD)
            progress_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            progress_text.insert(tk.END, "Scanning players for missing reference frames...\n")
            progress_window.update()
            
            # Remove missing frames
            try:
                total_removed, players_cleaned = gallery.remove_missing_reference_frames(verify_video_files=True)
                
                progress_text.insert(tk.END, f"\n✓ Cleanup complete!\n")
                progress_text.insert(tk.END, f"• Removed {total_removed} missing reference frames\n")
                progress_text.insert(tk.END, f"• Cleaned {players_cleaned} players\n")
                progress_text.see(tk.END)
                
                # Show success message
                messagebox.showinfo(
                    "Cleanup Complete",
                    f"Removed {total_removed} missing reference frames from {players_cleaned} players.\n"
                    "The gallery has been saved.",
                    parent=self.root
                )
                
                # Refresh gallery tab if it exists
                if parent_frame is not None:
                    self._refresh_gallery_tab(parent_frame)
                else:
                    # Try to find and refresh the gallery tab
                    try:
                        if hasattr(self, 'controls_notebook'):
                            for tab_id in self.controls_notebook.tabs():
                                tab_text = self.controls_notebook.tab(tab_id, "text")
                                if "Gallery" in tab_text or "Player" in tab_text:
                                    tab_frame = self.controls_notebook.nametowidget(tab_id)
                                    self._refresh_gallery_tab(tab_frame)
                                    break
                    except Exception:
                        pass
                
                self.log_message(f"✓ Removed {total_removed} missing reference frames from {players_cleaned} players")
                
            except Exception as e:
                progress_text.insert(tk.END, f"\n✗ Error: {str(e)}\n")
                messagebox.showerror("Error", f"Could not remove missing frames:\n\n{str(e)}", parent=self.root)
            
            # Close progress window after a delay
            progress_window.after(2000, progress_window.destroy)
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import player_gallery.py: {str(e)}\n\n"
                               "Make sure player_gallery.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not remove missing reference frames: {str(e)}")
            self.log_message(f"⚠ Error removing missing reference frames: {e}")
    
    def _refresh_gallery_tab(self, parent_frame):
        """Refresh the gallery tab content"""
        # Clear all widgets
        for widget in parent_frame.winfo_children():
            widget.destroy()
        # Force reload gallery from disk by creating a new instance
        # This ensures we get the latest saved changes
        try:
            from player_gallery import PlayerGallery
            # Create a new gallery instance to force reload from disk
            gallery = PlayerGallery()
            # Recreate the tab with fresh data
            self._create_gallery_tab(parent_frame)
        except Exception as e:
            print(f"⚠ Error refreshing gallery tab: {e}")
            # Still try to recreate even if reload fails
            self._create_gallery_tab(parent_frame)
    
    def backfill_gallery_features(self):
        """Extract Re-ID features from existing player tags in analyzed videos"""
        try:
            from player_gallery import PlayerGallery
            import cv2
            import json
            import pandas as pd
            import numpy as np
            from reid_tracker import ReIDTracker, TORCHREID_AVAILABLE
            
            if not TORCHREID_AVAILABLE:
                messagebox.showerror("Re-ID Not Available", 
                                    "Re-ID tracker is not available. Install torchreid to extract features.")
                return
            
            # Load gallery
            gallery = PlayerGallery()
            
            # Ask user to select a video file (or use current input)
            video_path = None
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
                if not os.path.exists(video_path):
                    video_path = None
            
            if not video_path:
                video_path = filedialog.askopenfilename(
                    title="Select Video File",
                    filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
                )
            
            if not video_path or not os.path.exists(video_path):
                return
            
            # Ask user if they want to manually select CSV or auto-detect
            video_dir = os.path.dirname(video_path)
            video_basename = os.path.splitext(os.path.basename(video_path))[0]
            
            # First, try to auto-detect CSV
            base_name = os.path.splitext(video_path)[0]
            csv_candidates = [
                f"{base_name}_tracking_data.csv",
                f"{base_name}_analyzed_tracking_data.csv",
                f"{base_name}_tracking_data_analyzed.csv",
                os.path.join(video_dir, f"{video_basename}_tracking_data.csv"),
                os.path.join(video_dir, f"{video_basename}_analyzed_tracking_data.csv"),
                os.path.join(video_dir, f"{video_basename}_tracking_data_analyzed.csv"),
            ]
            
            # Search for any CSV with "tracking" in the name in the video directory
            csv_path = None
            for candidate in csv_candidates:
                if os.path.exists(candidate):
                    csv_path = candidate
                    break
            
            # If still not found, search directory for tracking CSVs
            if not csv_path and os.path.exists(video_dir):
                try:
                    for filename in os.listdir(video_dir):
                        if 'tracking' in filename.lower() and filename.endswith('.csv'):
                            # Check if it matches the video name pattern
                            if video_basename.replace('_analyzed', '').replace('_preview', '') in filename or \
                               filename.startswith(video_basename.split('_')[0]):
                                csv_path = os.path.join(video_dir, filename)
                                break
                except:
                    pass
            
            # If auto-detection failed, ask user to select CSV manually
            if not csv_path or not os.path.exists(csv_path):
                # Show helpful message and ask user to select CSV
                response = messagebox.askyesno(
                    "Select CSV File",
                    f"Could not auto-detect tracking CSV for:\n{os.path.basename(video_path)}\n\n"
                    f"Would you like to select the CSV file manually?\n\n"
                    f"(Looking for CSV with tracking data and player names)"
                )
                
                if response:
                    csv_path = filedialog.askopenfilename(
                        title="Select Tracking CSV File",
                        initialdir=video_dir,
                        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                        initialfile=f"{video_basename}_tracking_data.csv"
                    )
                else:
                    return
                
                if not csv_path or not os.path.exists(csv_path):
                    messagebox.showerror("No Tracking Data", 
                                       "No CSV file selected.\n\n"
                                       "Please ensure:\n"
                                       "1. Analysis has been run on this video\n"
                                       "2. CSV file contains 'player_name' column (from Per-Video Names)")
                    return
            else:
                # Auto-detected CSV - ask user to confirm or choose different one
                response = messagebox.askyesno(
                    "CSV File Detected",
                    f"Auto-detected CSV file:\n{os.path.basename(csv_path)}\n\n"
                    f"Use this file, or select a different one?",
                    detail="Click 'Yes' to use the detected file, or 'No' to choose a different CSV."
                )
                
                if not response:
                    # User wants to choose different CSV
                    csv_path = filedialog.askopenfilename(
                        title="Select Tracking CSV File",
                        initialdir=video_dir,
                        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                        initialfile=os.path.basename(csv_path)
                    )
                    
                    if not csv_path or not os.path.exists(csv_path):
                        messagebox.showerror("No Tracking Data", 
                                           "No CSV file selected.")
                        return
            
            # Find PlayerTagsSeed file (PRIMARY SOURCE - has bbox info!)
            # First try exact match for current video
            seed_file = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
            if not os.path.exists(seed_file):
                # Try to find matching PlayerTagsSeed file by checking video_path
                # Don't auto-load files from different videos - user should explicitly choose
                seed_file = None
                potential_files = []
                if os.path.isdir(video_dir):
                    for f in os.listdir(video_dir):
                        if f.startswith('PlayerTagsSeed-') and f.endswith('.json'):
                            potential_files.append(os.path.join(video_dir, f))
                
                # Check each potential file to see if it matches current video
                current_video_path = None
                # Try to find actual video file path
                video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
                for ext in video_extensions:
                    potential_video = os.path.join(video_dir, video_basename + ext)
                    if os.path.exists(potential_video):
                        current_video_path = os.path.normpath(os.path.abspath(potential_video))
                        break
                
                # Check each potential file
                for candidate_file in potential_files:
                    try:
                        with open(candidate_file, 'r') as f:
                            candidate_data = json.load(f)
                        candidate_video_path = candidate_data.get('video_path', '')
                        if candidate_video_path and current_video_path:
                            candidate_normalized = os.path.normpath(os.path.abspath(candidate_video_path))
                            if candidate_normalized == current_video_path:
                                seed_file = candidate_file
                                break
                    except:
                        continue
                
                # If no matching file found, don't auto-load - proceed without seed file
                if not seed_file:
                    print(f"ℹ No matching PlayerTagsSeed file found for {video_basename} - proceeding without seed file")
            
            # Load PlayerTagsSeed file if available (has anchor frames with bbox!)
            seed_data = None
            anchor_frames_from_seed = {}
            if seed_file and os.path.exists(seed_file):
                try:
                    with open(seed_file, 'r') as f:
                        seed_data = json.load(f)
                    anchor_frames_from_seed = seed_data.get('anchor_frames', {})
                    if anchor_frames_from_seed:
                        print(f"✓ Found PlayerTagsSeed file with {sum(len(v) for v in anchor_frames_from_seed.values() if isinstance(v, list))} anchor frames (has bbox info!)")
                        
                        # VALIDATION: Check if seed file is from a different video
                        seed_video_path = seed_data.get('video_path', '')
                        if seed_video_path:
                            # Normalize paths for comparison
                            seed_video_normalized = os.path.normpath(os.path.abspath(seed_video_path))
                            current_video_normalized = os.path.normpath(os.path.abspath(csv_path.replace('_analyzed_tracking_data.csv', '')))
                            # Try to find actual video file
                            video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
                            for ext in video_extensions:
                                potential_video = current_video_normalized + ext
                                if os.path.exists(potential_video):
                                    current_video_normalized = os.path.normpath(os.path.abspath(potential_video))
                                    break
                            
                            if seed_video_normalized != current_video_normalized:
                                warning_msg = (
                                    f"⚠ WARNING: PlayerTagsSeed file is from a different video!\n\n"
                                    f"Seed file: {os.path.basename(seed_file)}\n"
                                    f"Original video: {os.path.basename(seed_video_path)}\n"
                                    f"Current video: {os.path.basename(csv_path)}\n\n"
                                    f"RISKS:\n"
                                    f"• Track IDs may not match (but bbox info will be used if available)\n"
                                    f"• Player names may be incorrect if different players are in this video\n"
                                    f"• Re-ID gallery could get wrong player associations\n\n"
                                    f"Continue anyway? (Only safe if same players appear in both videos)"
                                )
                                response = messagebox.askyesno("Video Mismatch Warning", warning_msg)
                                if not response:
                                    seed_data = None
                                    anchor_frames_from_seed = {}
                                    print("⚠ User cancelled - not using PlayerTagsSeed from different video")
                except Exception as e:
                    print(f"⚠ Could not load PlayerTagsSeed file: {e}")
                    seed_data = None
                    anchor_frames_from_seed = {}
            
            # Find anchor frames file (optional, secondary source)
            anchor_path = f"{base_name}_anchor_frames.json"
            if not os.path.exists(anchor_path):
                anchor_path = None  # Anchor frames are optional
            
            # Load CSV to find tagged players
            try:
                df = pd.read_csv(csv_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not read CSV: {e}")
                return
            
            # Check if CSV has player_name column (or alternative column names)
            # ENHANCED: Check for multiple possible column names
            player_name_col = None
            possible_names = ['player_name', 'name', 'player', 'playerName', 'Player Name', 'Name']
            for col_name in possible_names:
                if col_name in df.columns:
                    player_name_col = col_name
                    break
            
            # AUTO-USE anchor frames if available (has bbox - no CSV track_id needed!)
            if anchor_frames_from_seed and len(anchor_frames_from_seed) > 0:
                print(f"✓ Auto-using PlayerTagsSeed anchor frames (has bbox info - no CSV track_id needed!)")
                player_frames = {}  # player_name -> [(frame_num, track_id, bbox, team, jersey)]
                player_info = {}  # player_name -> {'team': team, 'jersey': jersey}
                
                # Extract from anchor frames (has bbox!)
                for frame_str, anchors in anchor_frames_from_seed.items():
                    try:
                        frame_num = int(frame_str)
                    except:
                        continue
                    
                    if not isinstance(anchors, list):
                        continue
                    
                    for anchor in anchors:
                        player_name = anchor.get('player_name', '').strip()
                        if not player_name or player_name.startswith('Player '):
                            continue  # Skip unnamed anchors
                        
                        track_id = anchor.get('track_id')
                        bbox = anchor.get('bbox')
                        team = anchor.get('team', '')
                        jersey = anchor.get('jersey_number', None)
                        
                        if player_name not in player_frames:
                            player_frames[player_name] = []
                            player_info[player_name] = {'team': team, 'jersey': jersey}
                        
                        # Anchor frames have bbox - use it directly!
                        player_frames[player_name].append((frame_num, track_id, bbox, team, jersey))
                
                print(f"✓ Extracted {len(player_frames)} players from anchor frames (with bbox info)")
                player_name_col = None  # Will use player_frames from anchor frames
            
            elif not player_name_col:
                # Check if PlayerTagsSeed file exists as alternative source
                seed_file_check = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
                if not os.path.exists(seed_file_check):
                    # Try with part number
                    for part_file in os.listdir(video_dir):
                        if part_file.startswith('PlayerTagsSeed-') and part_file.endswith('.json'):
                            seed_file_check = os.path.join(video_dir, part_file)
                            break
                
                if os.path.exists(seed_file_check):
                    # Use PlayerTagsSeed file instead
                    try:
                        with open(seed_file_check, 'r') as f:
                            seed_data_check = json.load(f)
                        
                        # Check if it has player_mappings
                        if 'player_mappings' in seed_data_check and seed_data_check['player_mappings']:
                            # Ask user if they want to use PlayerTagsSeed file
                            response = messagebox.askyesno(
                                "Use PlayerTagsSeed File?",
                                f"CSV doesn't have player_name column, but found:\n{os.path.basename(seed_file_check)}\n\n"
                                f"This file has {len(seed_data_check['player_mappings'])} player tags.\n\n"
                                f"Would you like to use this file instead?\n\n"
                                f"(You can also save player names to CSV in Per-Video Names tab)"
                            )
                            
                            if response:
                                # Use PlayerTagsSeed file - extract from anchor frames (has bbox!) or player_mappings
                                print(f"✓ Using PlayerTagsSeed file: {os.path.basename(seed_file_check)}")
                                
                                # Initialize player_frames and player_info here (before CSV processing)
                                player_frames = {}  # player_name -> [(frame_num, track_id, bbox, team, jersey)]
                                player_info = {}  # player_name -> {'team': team, 'jersey': jersey}
                                
                                # Check for anchor frames in this file
                                anchor_frames_check = seed_data_check.get('anchor_frames', {})
                                
                                # PRIORITY 1: Use anchor_frames from PlayerTagsSeed (has bbox info!)
                                if anchor_frames_check and len(anchor_frames_check) > 0:
                                    print(f"  📋 Using anchor frames from PlayerTagsSeed (has bbox info)")
                                    for frame_str, anchors in anchor_frames_check.items():
                                        try:
                                            frame_num = int(frame_str)
                                        except:
                                            continue
                                        
                                        if not isinstance(anchors, list):
                                            continue
                                        
                                        for anchor in anchors:
                                            player_name = anchor.get('player_name', '').strip()
                                            if not player_name or player_name.startswith('Player '):
                                                continue  # Skip unnamed anchors
                                            
                                            track_id = anchor.get('track_id')
                                            bbox = anchor.get('bbox')
                                            team = anchor.get('team', '')
                                            jersey = anchor.get('jersey_number', None)
                                            
                                            if player_name not in player_frames:
                                                player_frames[player_name] = []
                                                player_info[player_name] = {'team': team, 'jersey': jersey}
                                            
                                            # Anchor frames have bbox - use it directly!
                                            player_frames[player_name].append((frame_num, track_id, bbox, team, jersey))
                                    
                                    print(f"✓ Extracted {len(player_frames)} players from anchor frames (with bbox info)")
                                    player_name_col = None  # Will use player_frames from anchor frames
                                
                                # PRIORITY 2: Fallback to player_mappings if no anchor frames
                                elif 'player_mappings' in seed_data_check:
                                    player_mappings = seed_data_check.get('player_mappings', {})
                                    if player_mappings:
                                        print(f"  📋 Using player_mappings from PlayerTagsSeed (will try to find bbox from CSV)")
                                        # Try to find bbox from CSV using track_id
                                        track_id_col = None
                                        for col in ['track_id', 'tracker_id', 'player_id', 'id']:
                                            if col in df.columns:
                                                track_id_col = col
                                                break
                                        
                                        if track_id_col:
                                            for track_id_str, mapping in player_mappings.items():
                                                try:
                                                    track_id = int(track_id_str)
                                                except:
                                                    continue
                                                
                                                # Extract player info
                                                if isinstance(mapping, list) and len(mapping) >= 1:
                                                    player_name = mapping[0]
                                                    team = mapping[1] if len(mapping) > 1 else ""
                                                    jersey = mapping[2] if len(mapping) > 2 else None
                                                else:
                                                    player_name = str(mapping) if mapping else ""
                                                    team = ""
                                                    jersey = None
                                                
                                                if not player_name or not player_name.strip():
                                                    continue
                                                
                                                if player_name not in player_frames:
                                                    player_frames[player_name] = []
                                                    player_info[player_name] = {'team': team, 'jersey': jersey}
                                                
                                                # Find all frames with this track_id in CSV
                                                track_df = df[df[track_id_col] == track_id]
                                                for idx, row in track_df.iterrows():
                                                    frame_num = int(row.get('frame', row.get('frame_num', 0)))
                                                    bbox = None
                                                    if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                                                        bbox = [float(row['x1']), float(row['y1']), float(row['x2']), float(row['y2'])]
                                                    player_frames[player_name].append((frame_num, track_id, bbox, team, jersey))
                                            
                                            print(f"✓ Extracted {len(player_frames)} players from player_mappings")
                                            player_name_col = None
                                        else:
                                            messagebox.showerror("No Track ID Column", 
                                                               f"CSV doesn't have track_id column.\n\n"
                                                               f"Available columns: {', '.join(df.columns.tolist()[:10])}\n\n"
                                                               f"PlayerTagsSeed anchor frames would work better (has bbox info).")
                                            return
                                    else:
                                        messagebox.showerror("No Player Data", 
                                                           f"PlayerTagsSeed file has no anchor_frames or player_mappings.")
                                        return
                                else:
                                    messagebox.showerror("No Player Data", 
                                                       f"PlayerTagsSeed file has no usable player data.")
                                    return
                            else:
                                return
                        else:
                            raise ValueError("PlayerTagsSeed file has no player_mappings")
                    except Exception as e:
                        print(f"⚠ Could not use PlayerTagsSeed file: {e}")
                        seed_data_check = None
                
                if not player_name_col:
                    # Show available columns to help debug
                    available_cols = ', '.join(df.columns.tolist()[:10])  # Show first 10 columns
                    if len(df.columns) > 10:
                        available_cols += f" ... ({len(df.columns)} total columns)"
                    
                    messagebox.showinfo("No Player Tags", 
                                       f"This CSV doesn't have a player name column.\n\n"
                                       f"Looking for: {', '.join(possible_names)}\n\n"
                                       f"Available columns: {available_cols}\n\n"
                                       f"To fix this:\n"
                                       f"1. In 'Per-Video Names' tab, tag players and SAVE\n"
                                       f"2. Or use Setup Wizard to tag players\n"
                                       f"3. Or use 'Convert Tags → Anchor Frames' tool")
                    return
            
            # Load anchor frames if available (optional - used as additional source)
            # Note: If using PlayerTagsSeed, we already have player_frames, but anchor frames can add more
            anchor_frames = {}
            if anchor_path and os.path.exists(anchor_path):
                try:
                    with open(anchor_path, 'r') as f:
                        anchor_data = json.load(f)
                        # Handle both formats: direct anchor_frames dict or PlayerTagsSeed format
                        if 'anchor_frames' in anchor_data:
                            anchor_frames = anchor_data['anchor_frames']
                        elif isinstance(anchor_data, dict) and any(isinstance(v, list) for v in anchor_data.values()):
                            anchor_frames = anchor_data
                except Exception as e:
                    print(f"⚠ Could not load anchor frames: {e}")
                    anchor_frames = {}  # Continue without anchor frames
            
            # Initialize Re-ID tracker (use GUI settings)
            reid_tracker = ReIDTracker(
                feature_dim=128,  # Will be auto-detected by model
                similarity_threshold=self.reid_similarity_threshold.get(),
                use_torchreid=True,
                osnet_variant=self.osnet_variant.get(),
                use_boxmot_backend=self.use_boxmot_backend.get()
            )
            
            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                messagebox.showerror("Error", f"Could not open video: {video_path}")
                return
            
            # Progress dialog
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Backfilling Features")
            progress_window.geometry("500x200")
            progress_window.transient(self.root)
            
            progress_label = ttk.Label(progress_window, text="Extracting Re-ID features from tagged players...", 
                                      font=("Arial", 10))
            progress_label.pack(pady=20)
            
            progress_var = tk.StringVar(value="Scanning frames...")
            status_label = ttk.Label(progress_window, textvariable=progress_var, font=("Arial", 9))
            status_label.pack(pady=10)
            
            progress_window.update()
            
            # Process: Find unique player-frame combinations
            # ENHANCED: Store team and jersey info from per-video names
            # Initialize player_frames - may already be populated from PlayerTagsSeed anchor frames
            if 'player_frames' not in locals() or not player_frames:
                player_frames = {}  # player_name -> [(frame_num, track_id, bbox, team, jersey)]
                player_info = {}  # player_name -> {'team': team, 'jersey': jersey} (most common values)
            
            # Check if we're using anchor frames from PlayerTagsSeed (has bbox - no CSV needed!)
            using_anchor_frames = (player_name_col is None and len(player_frames) > 0)
            
            # From CSV - use per-video names that user has tagged (only if we have player_name_col and not using anchor frames)
            if player_name_col and not using_anchor_frames:
                for idx, row in df.iterrows():
                    frame_num = int(row.get('frame', row.get('frame_num', 0)))
                    track_id = row.get('track_id', row.get('tracker_id', None))
                    player_name = row.get(player_name_col, '').strip()  # Use detected column name
                    
                    if player_name and player_name != '' and not player_name.startswith('Player '):
                        if player_name not in player_frames:
                            player_frames[player_name] = []
                            player_info[player_name] = {'team': None, 'jersey': None}
                        
                        # Get bbox from CSV
                        bbox = None
                        if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                            bbox = [float(row['x1']), float(row['y1']), float(row['x2']), float(row['y2'])]
                        
                        # Get team and jersey from CSV (per-video names)
                        team = row.get('team', row.get('team_name', '')).strip() if 'team' in row or 'team_name' in row else None
                        jersey = row.get('jersey', row.get('jersey_number', '')).strip() if 'jersey' in row or 'jersey_number' in row else None
                        
                        player_frames[player_name].append((frame_num, track_id, bbox, team, jersey))
                        
                        # Store most common team/jersey for this player
                        if team and team != '':
                            player_info[player_name]['team'] = team
                        if jersey and jersey != '':
                            player_info[player_name]['jersey'] = jersey
            
            # From additional anchor frames file (if not already using PlayerTagsSeed anchor frames)
            # Merge with player_frames from CSV/PlayerTagsSeed
            if not using_anchor_frames:
                for frame_num_str, tags in anchor_frames.items():
                    try:
                        frame_num = int(frame_num_str)
                        for tag in tags:
                            player_name = tag.get('player_name', '').strip()
                            if player_name and not player_name.startswith('Player '):  # Skip unnamed anchors
                                if player_name not in player_frames:
                                    player_frames[player_name] = []
                                    if player_name not in player_info:
                                        player_info[player_name] = {'team': None, 'jersey': None}
                                bbox = tag.get('bbox', None)
                                track_id = tag.get('track_id', None)
                                team = tag.get('team', '')
                                jersey = tag.get('jersey_number', None)
                                player_frames[player_name].append((frame_num, track_id, bbox, team, jersey))
                                
                                # Update player_info if team/jersey available
                                if team:
                                    player_info[player_name]['team'] = team
                                if jersey:
                                    player_info[player_name]['jersey'] = jersey
                    except:
                        continue
            
            # Check if we have any players to process
            if not player_frames:
                messagebox.showinfo("No Players Found", 
                                   "No players found to extract features from.\n\n"
                                   "Please ensure:\n"
                                   "1. PlayerTagsSeed file has player_mappings\n"
                                   "2. Or CSV has player_name column\n"
                                   "3. Or anchor frames have player names")
                return
            
            # Extract features for each player
            total_players = len(player_frames)
            processed_players = 0
            features_added = 0
            
            for player_name, frames_list in player_frames.items():
                processed_players += 1
                progress_var.set(f"Processing {player_name} ({processed_players}/{total_players})...")
                progress_window.update()
                
                # Get or create player in gallery
                player_id = None
                for pid, profile in gallery.players.items():
                    if profile.name == player_name:
                        player_id = pid
                        break
                
                if not player_id:
                    # Create player without features first, using team/jersey from per-video names
                    player_team = player_info.get(player_name, {}).get('team')
                    player_jersey = player_info.get(player_name, {}).get('jersey')
                    player_id = gallery.add_player(
                        name=player_name,
                        features=None,  # Will add features below
                        jersey_number=player_jersey if player_jersey else None,
                        team=player_team if player_team else None
                    )
                    if player_team or player_jersey:
                        print(f"  📝 Created player '{player_name}' with team={player_team}, jersey={player_jersey} from per-video names")
                
                # ENHANCED: Auto-select highest quality frames instead of first N frames
                # Deduplicate by (frame_num, track_id) but keep team/jersey info
                unique_frames = {}
                for frame_num, track_id, bbox, team, jersey in frames_list:
                    key = (frame_num, track_id)
                    if key not in unique_frames:
                        unique_frames[key] = (frame_num, track_id, bbox, team, jersey)
                
                # Score each frame by quality metrics
                scored_frames = []
                for frame_num, track_id, bbox, team, jersey in unique_frames.values():
                    quality_score = 0.0
                    
                    if bbox and len(bbox) >= 4:
                        # Calculate quality metrics
                        x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
                        width = abs(x2 - x1)
                        height = abs(y2 - y1)
                        area = width * height
                        aspect_ratio = height / width if width > 0 else 0
                        
                        # Quality factors (higher is better):
                        # 1. Bbox size (larger = closer/clearer view) - weight: 50%
                        # 2. Aspect ratio (players are taller than wide, ~1.5-2.5 is ideal) - weight: 20%
                        # 3. Frame position (earlier frames may be better for initial tagging) - weight: 10%
                        # 4. Valid bbox (not None, has dimensions) - weight: 20%
                        
                        # Normalize area score (assume max reasonable area is 500x500 = 250000)
                        area_score = min(1.0, area / 250000.0) * 0.5
                        
                        # Aspect ratio score (prefer 1.5-2.5 range for players)
                        if 1.2 <= aspect_ratio <= 2.8:
                            aspect_score = 0.2  # Ideal range
                        elif 1.0 <= aspect_ratio <= 3.5:
                            aspect_score = 0.15  # Acceptable range
                        else:
                            aspect_score = 0.05  # Less ideal
                        
                        # Frame position score (slight preference for earlier frames, but quality matters more)
                        frame_score = max(0.0, (1000 - frame_num) / 1000.0) * 0.1 if frame_num < 1000 else 0.05
                        
                        # Valid bbox bonus
                        valid_score = 0.2 if area > 1000 and width > 20 and height > 20 else 0.0
                        
                        quality_score = area_score + aspect_score + frame_score + valid_score
                    else:
                        # No bbox = lower quality
                        quality_score = 0.1
                    
                    scored_frames.append((quality_score, frame_num, track_id, bbox, team, jersey))
                
                # Sort by quality score (highest first) and take top 5
                scored_frames.sort(key=lambda x: x[0], reverse=True)
                frames_to_process = [(f, t, b, tm, j) for _, f, t, b, tm, j in scored_frames[:5]]
                
                if len(scored_frames) > 5:
                    print(f"  🎯 Selected top 5 quality frames for '{player_name}' (from {len(scored_frames)} total frames)")
                
                for frame_num, track_id, bbox, team, jersey in frames_to_process:
                    try:
                        # Seek to frame
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                        ret, frame = cap.read()
                        if not ret:
                            continue
                        
                        # If no bbox, try to find it from CSV for this frame (only if CSV is available)
                        if (bbox is None or len(bbox) < 4) and df is not None and len(df) > 0:
                            # Try to find bbox from CSV
                            frame_col = 'frame' if 'frame' in df.columns else 'frame_num'
                            if frame_col in df.columns:
                                frame_df = df[df[frame_col] == frame_num]
                                if track_id is not None:
                                    # Try to match by track_id if available
                                    track_id_col = None
                                    for col in ['track_id', 'tracker_id', 'player_id', 'id']:
                                        if col in df.columns:
                                            track_id_col = col
                                            break
                                    
                                    if track_id_col:
                                        track_df = frame_df[frame_df[track_id_col] == track_id]
                                        if len(track_df) > 0:
                                            row = track_df.iloc[0]
                                        elif len(frame_df) > 0:
                                            row = frame_df.iloc[0]  # Fallback to any frame match
                                        else:
                                            row = None
                                    else:
                                        row = frame_df.iloc[0] if len(frame_df) > 0 else None
                                else:
                                    row = frame_df.iloc[0] if len(frame_df) > 0 else None
                                
                                if row is not None:
                                    if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                                        bbox = [float(row['x1']), float(row['y1']), float(row['x2']), float(row['y2'])]
                        
                        if bbox is None or len(bbox) < 4:
                            # Skip this frame if we still don't have bbox
                            if processed_players == 1:  # Only log for first player to avoid spam
                                print(f"  ⚠ Skipping frame {frame_num} for '{player_name}' - no bbox available")
                            continue
                        
                        # Create detection
                        try:
                            import supervision as sv
                            xyxy = np.array([[bbox[0], bbox[1], bbox[2], bbox[3]]], dtype=np.float32)
                            detections = sv.Detections(xyxy=xyxy)
                            
                            # Extract features (need team_colors and ball_colors parameters)
                            # Initialize empty team/ball colors for backfill
                            team_colors = None
                            ball_colors = None
                            features = reid_tracker.extract_features(frame, detections, team_colors, ball_colors)
                            
                            if features is not None and len(features) > 0:
                                feature_vector = features[0]
                                
                                # Create reference frame dict
                                reference_frame = {
                                    'video_path': video_path,
                                    'frame_num': frame_num,
                                    'bbox': bbox,
                                    'confidence': 1.0,
                                    'similarity': 1.0,
                                    'player_name': player_name
                                }
                                
                                # Update player with features AND reference frame
                                # This sets profile.features (required for get_stats to count it!)
                                gallery.update_player(
                                    player_id=player_id,
                                    features=feature_vector,  # This sets profile.features
                                    reference_frame=reference_frame,  # This adds to reference_frames
                                    team=team if team else None,
                                    jersey_number=jersey if jersey else None
                                )
                                # Note: update_player now saves automatically for manual edits (name/jersey/team)
                                # But for batch feature updates, we save at the end (line 6126)
                                
                                features_added += 1
                        except Exception as e:
                            continue
                    except Exception as e:
                        continue
            
            cap.release()
            gallery.save_gallery()
            
            progress_window.destroy()
            
            messagebox.showinfo("Backfill Complete", 
                              f"✓ Extracted features for {features_added} reference frames\n"
                              f"✓ Processed {processed_players} players from per-video names\n"
                              f"✓ Team and jersey info imported from CSV\n\n"
                              f"Click 'Refresh' to see updated gallery status.\n\n"
                              f"Gallery matching is now enabled for future videos!")
            
            # Refresh gallery tab if it's open
            try:
                if hasattr(self, '_player_management_window') and self._player_management_window.winfo_exists():
                    # Find the gallery tab and refresh it
                    for widget in self._player_management_window.winfo_children():
                        if isinstance(widget, ttk.Notebook):
                            for tab_id in widget.tabs():
                                tab_frame = widget.nametowidget(tab_id)
                                # Check if this is the gallery tab by looking for gallery-specific widgets
                                try:
                                    # Try to find gallery frame by checking children
                                    for child in tab_frame.winfo_children():
                                        if isinstance(child, tk.Frame) or isinstance(child, ttk.Frame):
                                            # Check if this frame has gallery content
                                            for grandchild in child.winfo_children():
                                                if "Players in Gallery" in str(grandchild) or "Gallery Statistics" in str(grandchild):
                                                    self._refresh_gallery_tab(tab_frame)
                                                    print("✓ Gallery tab refreshed automatically")
                                                    return
                                except:
                                    pass
            except Exception as e:
                print(f"⚠ Could not auto-refresh gallery tab: {e}")
                # Not critical - user can click Refresh button
            
        except ImportError as e:
            messagebox.showerror("Error", f"Could not import required modules: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Backfill failed: {e}")
            import traceback
            traceback.print_exc()
    
    def match_unnamed_anchor_frames(self):
        """Match unnamed anchor frames (Player 51, Player 100, etc.) to known players using Re-ID"""
        try:
            from player_gallery import PlayerGallery
            import cv2
            import json
            import pandas as pd
            import numpy as np
            from reid_tracker import ReIDTracker, TORCHREID_AVAILABLE
            
            if not TORCHREID_AVAILABLE:
                messagebox.showerror("Re-ID Not Available", 
                                    "Re-ID tracker is not available. Install torchreid to match players.")
                return
            
            # Ask user to select PlayerTagsSeed file
            video_path = None
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
                if not os.path.exists(video_path):
                    video_path = None
            
            if not video_path:
                video_path = filedialog.askopenfilename(
                    title="Select Video File",
                    filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
                )
            
            if not video_path or not os.path.exists(video_path):
                return
            
            # Find PlayerTagsSeed file
            video_dir = os.path.dirname(video_path)
            video_basename = os.path.splitext(os.path.basename(video_path))[0]
            seed_file = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
            
            if not os.path.exists(seed_file):
                # Try to find any PlayerTagsSeed file
                for f in os.listdir(video_dir):
                    if f.startswith('PlayerTagsSeed-') and f.endswith('.json'):
                        seed_file = os.path.join(video_dir, f)
                        break
            
            if not os.path.exists(seed_file):
                seed_file = filedialog.askopenfilename(
                    title="Select PlayerTagsSeed JSON File",
                    initialdir=video_dir,
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                )
            
            if not seed_file or not os.path.exists(seed_file):
                return
            
            # Load PlayerTagsSeed file
            with open(seed_file, 'r') as f:
                seed_data = json.load(f)
            
            # VALIDATION: Check if seed file is from a different video
            seed_video_path = seed_data.get('video_path', '')
            if seed_video_path:
                seed_video_normalized = os.path.normpath(os.path.abspath(seed_video_path))
                current_video_normalized = os.path.normpath(os.path.abspath(video_path))
                if seed_video_normalized != current_video_normalized:
                    warning_msg = (
                        f"⚠ WARNING: PlayerTagsSeed file is from a different video!\n\n"
                        f"Seed file: {os.path.basename(seed_file)}\n"
                        f"Original video: {os.path.basename(seed_video_path)}\n"
                        f"Current video: {os.path.basename(video_path)}\n\n"
                        f"RISKS:\n"
                        f"• Track IDs may not match (but bbox info will be used if available)\n"
                        f"• Player names may be incorrect if different players are in this video\n"
                        f"• Re-ID matching could assign wrong players to tracks\n"
                        f"• Gallery could get polluted with incorrect associations\n\n"
                        f"Continue anyway? (Only safe if same players appear in both videos)"
                    )
                    response = messagebox.askyesno("Video Mismatch Warning", warning_msg)
                    if not response:
                        return
            
            anchor_frames = seed_data.get('anchor_frames', {})
            if not anchor_frames:
                messagebox.showinfo("No Anchor Frames", "No anchor frames found in this file.")
                return
            
            # Find unnamed anchor frames (Player 51, Player 100, etc.)
            unnamed_anchors = []  # [(frame_num, anchor_entry, track_id)]
            for frame_str, anchors in anchor_frames.items():
                if not isinstance(anchors, list):
                    continue
                for anchor in anchors:
                    player_name = anchor.get('player_name', '')
                    if player_name and (player_name.startswith('Player ') or player_name.isdigit()):
                        try:
                            frame_num = int(frame_str)
                            track_id = anchor.get('track_id')
                            unnamed_anchors.append((frame_num, anchor, track_id))
                        except:
                            continue
            
            if not unnamed_anchors:
                messagebox.showinfo("No Unnamed Anchors", "All anchor frames already have player names.")
                return
            
            # Load player gallery
            gallery = PlayerGallery()
            stats = gallery.get_stats()
            if stats['players_with_features'] == 0:
                messagebox.showwarning("No Gallery Features", 
                                     "Player gallery has no Re-ID features.\n\n"
                                     "Please run 'Backfill Features' first to extract features from named players.")
                return
            
            # Initialize Re-ID tracker (use GUI settings)
            reid_tracker = ReIDTracker(
                feature_dim=128,  # Will be auto-detected by model
                similarity_threshold=self.reid_similarity_threshold.get(),
                use_torchreid=True,
                osnet_variant=self.osnet_variant.get(),
                use_boxmot_backend=self.use_boxmot_backend.get()
            )
            
            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                messagebox.showerror("Error", f"Could not open video: {video_path}")
                return
            
            # Progress dialog
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Matching Unnamed Anchor Frames")
            progress_window.geometry("500x200")
            progress_window.transient(self.root)
            
            progress_label = ttk.Label(progress_window, text=f"Matching {len(unnamed_anchors)} unnamed anchor frames to known players...", 
                                      font=("Arial", 10))
            progress_label.pack(pady=20)
            
            progress_var = tk.StringVar(value="Initializing...")
            status_label = ttk.Label(progress_window, textvariable=progress_var, font=("Arial", 9))
            status_label.pack(pady=10)
            
            progress_window.update()
            
            # Process each unnamed anchor
            matches_found = 0
            matches_updated = 0
            
            for idx, (frame_num, anchor, track_id) in enumerate(unnamed_anchors):
                progress_var.set(f"Processing {idx+1}/{len(unnamed_anchors)}: Frame {frame_num}, Track #{track_id}")
                progress_window.update()
                
                try:
                    # Seek to frame
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    
                    # Get bbox from anchor or try to find from CSV
                    bbox = anchor.get('bbox')
                    if not bbox:
                        # Try to find bbox from CSV if available
                        csv_path = os.path.join(video_dir, f"{video_basename}_analyzed_tracking_data.csv")
                        if os.path.exists(csv_path):
                            try:
                                df = pd.read_csv(csv_path)
                                frame_df = df[df['frame'] == frame_num]
                                track_df = frame_df[frame_df['track_id'] == track_id]
                                if len(track_df) > 0:
                                    # Get first row as dict to avoid type checker issues with iloc
                                    rows = track_df.to_dict('records')
                                    if rows and len(rows) > 0:
                                        row = rows[0]
                                        if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                                            bbox = [float(row['x1']), float(row['y1']), float(row['x2']), float(row['y2'])]
                            except:
                                pass
                    
                    if not bbox or len(bbox) < 4:
                        continue
                    
                    # Extract Re-ID features
                    import supervision as sv
                    xyxy = np.array([[bbox[0], bbox[1], bbox[2], bbox[3]]], dtype=np.float32)
                    detections = sv.Detections(xyxy=xyxy)
                    
                    team_colors = None
                    ball_colors = None
                    features = reid_tracker.extract_features(frame, detections, team_colors, ball_colors)
                    
                    if features is None or len(features) == 0:
                        continue
                    
                    feature_vector = features[0]
                    
                    # Match to gallery (use GUI threshold, slightly lower for unnamed anchors)
                    match_threshold = max(0.25, self.reid_similarity_threshold.get() - 0.1)
                    match_result = gallery.match_player(
                        features=feature_vector,
                        similarity_threshold=match_threshold,  # Lower threshold for matching unnamed anchors
                        return_all=False
                    )
                    # Type narrowing: when return_all=False, result is Tuple[Optional[str], Optional[str], float]
                    # Use explicit indexing and cast to help type checker understand the tuple structure
                    if isinstance(match_result, tuple) and len(match_result) == 3:
                        # Cast to help type checker: when return_all=False, result is always a tuple
                        result_tuple = cast(Tuple[Optional[str], Optional[str], float], match_result)
                        player_id = result_tuple[0]
                        matched_name = result_tuple[1]
                        # Third element is guaranteed to be float when return_all=False
                        similarity_float = float(result_tuple[2])
                    else:
                        # Fallback (shouldn't happen with return_all=False)
                        player_id, matched_name, similarity_float = None, None, 0.0
                    
                    if matched_name and similarity_float >= match_threshold:
                        # Update anchor frame with matched player name
                        anchor['player_name'] = matched_name
                        anchor['matched_via_reid'] = True
                        anchor['reid_similarity'] = similarity_float
                        matches_found += 1
                        
                        # Also update team/jersey if available from gallery
                        if player_id:
                            profile = gallery.players.get(player_id)
                            if profile:
                                if profile.team and not anchor.get('team'):
                                    anchor['team'] = profile.team
                                if profile.jersey_number and not anchor.get('jersey_number'):
                                    anchor['jersey_number'] = profile.jersey_number
                        
                        matches_updated += 1
                
                except Exception as e:
                    print(f"⚠ Error matching anchor frame {frame_num}: {e}")
                    continue
            
            cap.release()
            
            # Save updated PlayerTagsSeed file with JSON protection
            if matches_updated > 0:
                try:
                    from json_utils import safe_json_save
                    from pathlib import Path
                    safe_json_save(Path(seed_file), seed_data, create_backup=True, validate=True)
                except ImportError:
                    # Fallback to standard JSON if json_utils not available
                    with open(seed_file, 'w', encoding='utf-8') as f:
                        json.dump(seed_data, f, indent=2, ensure_ascii=False)
            
            progress_window.destroy()
            
            match_threshold = max(0.25, self.reid_similarity_threshold.get() - 0.1)
            messagebox.showinfo("Matching Complete", 
                              f"✓ Processed {len(unnamed_anchors)} unnamed anchor frames\n"
                              f"✓ Matched {matches_found} to known players (similarity ≥ {match_threshold:.2f})\n"
                              f"✓ Updated {matches_updated} anchor frames with player names\n\n"
                              f"Updated: {os.path.basename(seed_file)}")
            
        except ImportError as e:
            messagebox.showerror("Error", f"Could not import required modules: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Matching failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _extract_profile_image(self, ref_frame: dict):
        """
        Extract profile image from a reference frame.
        
        Args:
            ref_frame: Reference frame dict with video_path, frame_num, bbox
            
        Returns:
            PIL ImageTk.PhotoImage or None if extraction fails
        """
        try:
            import cv2
            import numpy as np
            from PIL import Image, ImageTk
            
            video_path = ref_frame.get('video_path')
            frame_num = ref_frame.get('frame_num')
            bbox = ref_frame.get('bbox')
            
            if not video_path or frame_num is None or not bbox or len(bbox) < 4:
                print(f"  Missing required data: video_path={bool(video_path)}, frame_num={frame_num}, bbox={bool(bbox)}")
                return None
            
            # Check if video path exists (try both absolute and relative)
            video_exists = os.path.exists(video_path)
            if not video_exists:
                # Try to find video file in common locations
                video_basename = os.path.basename(video_path)
                possible_paths = [
                    video_path,  # Original path
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), video_basename),  # Same dir as script
                    os.path.join(os.getcwd(), video_basename),  # Current working directory
                ]
                
                found_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        found_path = path
                        print(f"  Video file found at alternative location: {path}")
                        video_path = path
                        break
                
                if not found_path:
                    print(f"  Video file not found: {video_path}")
                    print(f"    Looking for: {video_basename}")
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
            # Ensure coordinates are within frame bounds
            h, w = frame.shape[:2]
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            
            if x2 <= x1 or y2 <= y1:
                return None
            
            # Crop to bbox
            cropped = frame[y1:y2, x1:x2]
            
            # Validation: Check if image is mostly green (field) - if so, it's probably wrong
            # Convert to HSV to detect green field
            hsv = cv2.cvtColor(cropped, cv2.COLOR_BGR2HSV)
            # Green field typically: H=40-80, S=50-255, V=50-255
            # Create mask for green pixels
            lower_green = np.array([40, 50, 50])
            upper_green = np.array([80, 255, 255])
            green_mask = cv2.inRange(hsv, lower_green, upper_green)
            green_ratio = np.sum(green_mask > 0) / (cropped.shape[0] * cropped.shape[1])
            
            # If more than 70% green, this is probably field, not a player (relaxed from 60%)
            if green_ratio > 0.7:
                # This is likely a field-only image, skip it
                print(f"  Image rejected: too much green field ({green_ratio:.2%})")
                return None
            
            # Validation: Check aspect ratio (players should be taller than wide)
            h, w = cropped.shape[:2]
            if w > 0:
                aspect_ratio = h / w
                # If wider than tall (aspect < 1.0), probably not a player
                if aspect_ratio < 1.0:
                    return None
                # If too square (aspect < 1.2), less likely to be a good player view
                if aspect_ratio < 1.2:
                    # Still allow but prefer taller images
                    pass
            
            # Validation: Check minimum size (relaxed from 50 to 30 for smaller players)
            if h < 30 or w < 30:
                print(f"  Image rejected: too small ({w}x{h})")
                return None
            
            # Resize to reasonable size for display (max 250x300 for better quality)
            max_width = 250
            max_height = 300
            if h > max_height or w > max_width:
                scale = min(max_height / h, max_width / w)
                new_w = int(w * scale)
                new_h = int(h * scale)
                cropped = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Convert BGR to RGB for PIL
            cropped_rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image
            pil_image = Image.fromarray(cropped_rgb)
            
            # Convert to ImageTk for display
            return ImageTk.PhotoImage(pil_image)
            
        except Exception as e:
            # Print detailed error for debugging image extraction failures
            video_path = ref_frame.get('video_path', 'unknown') if ref_frame else 'unknown'
            frame_num = ref_frame.get('frame_num', '?') if ref_frame else '?'
            print(f"  ⚠ Error extracting profile image from {os.path.basename(video_path)} frame {frame_num}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_foot_region_image(self, ref_frame: dict):
        """
        Extract foot/shoe region image from a reference frame.
        Foot region is the bottom 20-40% of the bounding box (60-80% from top).
        
        Args:
            ref_frame: Reference frame dict with video_path, frame_num, bbox
            
        Returns:
            PIL ImageTk.PhotoImage or None if extraction fails
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
            # Ensure coordinates are within frame bounds
            frame_h, frame_w = frame.shape[:2]
            x1 = max(0, min(x1, frame_w))
            y1 = max(0, min(y1, frame_h))
            x2 = max(0, min(x2, frame_w))
            y2 = max(0, min(y2, frame_h))
            
            if x2 <= x1 or y2 <= y1:
                return None
            
            # Calculate foot region (bottom 10-30% of bbox, i.e., 70-90% from top)
            # This captures the feet/shoes area, not shorts (which are at 60-80%)
            bbox_height = y2 - y1
            foot_y1 = int(y1 + bbox_height * 0.70)  # Start at 70% from top (bottom 30%)
            foot_y2 = int(y1 + bbox_height * 0.90)  # End at 90% from top (bottom 10%)
            
            # Clamp to frame boundaries
            foot_y1 = max(0, min(foot_y1, frame_h))
            foot_y2 = max(foot_y1 + 1, min(foot_y2, frame_h))
            
            if foot_y2 <= foot_y1 or x2 <= x1:
                return None
            
            # Extract foot region
            foot_crop = frame[foot_y1:foot_y2, x1:x2]
            
            if foot_crop.size == 0:
                return None
            
            # Validation: Check minimum size
            h, w = foot_crop.shape[:2]
            if h < 8 or w < 8:
                return None
            
            # Resize to reasonable size for display (wider than tall, like feet)
            max_width = 200
            max_height = 100
            if h > max_height or w > max_width:
                scale = min(max_height / h, max_width / w)
                new_w = int(w * scale)
                new_h = int(h * scale)
                foot_crop = cv2.resize(foot_crop, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Convert BGR to RGB for PIL
            foot_crop_rgb = cv2.cvtColor(foot_crop, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image
            pil_image = Image.fromarray(foot_crop_rgb)
            
            # Convert to ImageTk for display
            return ImageTk.PhotoImage(pil_image)
            
        except Exception as e:
            return None
            # Silently fail if extraction fails
            return None
    
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
            detail_window.geometry("800x900")
            detail_window.minsize(700, 800)
            detail_window.transient(self.root)
            
            # Create scrollable frame for content
            canvas = tk.Canvas(detail_window)
            scrollbar = ttk.Scrollbar(detail_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Main frame (now inside scrollable frame)
            main_frame = ttk.Frame(scrollable_frame, padding="15")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            ttk.Label(main_frame, text=profile.name, font=("Arial", 16, "bold")).pack(pady=(0, 10))
            
            # Profile images (best reference frame + foot region)
            profile_image_frame = ttk.LabelFrame(main_frame, text="Player Images", padding="10")
            profile_image_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Container for images side by side
            images_container = ttk.Frame(profile_image_frame)
            images_container.pack(fill=tk.X, pady=5)
            
            try:
                best_frame = None
                profile_img = None
                foot_img = None
                
                # Debug: Check reference frames availability
                ref_frames_available = profile.reference_frames is not None and len(profile.reference_frames) > 0
                if not ref_frames_available:
                    print(f"⚠ No reference frames found for player '{profile.name}' (player_id: {player_id})")
                    print(f"   reference_frames is: {profile.reference_frames}")
                
                # Score all reference frames to find the highest quality one
                if profile.reference_frames and len(profile.reference_frames) > 0:
                    scored_frames = []
                    for ref_frame in profile.reference_frames:
                        if not ref_frame.get('video_path') or not ref_frame.get('bbox'):
                            continue
                        
                        bbox = ref_frame.get('bbox', [])
                        if len(bbox) < 4:
                            continue
                        
                        # Calculate quality score (with validation)
                        try:
                            if len(bbox) < 4:
                                continue
                            width = abs(float(bbox[2]) - float(bbox[0]))
                            height = abs(float(bbox[3]) - float(bbox[1]))
                            if width <= 0 or height <= 0 or not (isinstance(width, (int, float)) and isinstance(height, (int, float))):
                                continue
                        except (IndexError, ValueError, TypeError) as e:
                            # Skip invalid bbox
                            continue
                        
                        aspect_ratio = height / width
                        area = width * height
                        
                        # Quality scoring factors:
                        # 1. Size (larger is better) - weight: 1.0
                        # 2. Aspect ratio (prefer 1.5-2.5 for players) - weight: 0.5
                        # 3. Confidence (if available) - weight: 2.0
                        # 4. Minimum size threshold (50x50)
                        
                        if width >= 50 and height >= 50:
                            size_score = area / 10000.0  # Normalize to reasonable range
                            
                            # Aspect ratio score (prefer 1.5-2.5)
                            if 1.5 <= aspect_ratio <= 2.5:
                                aspect_score = 1.0
                            elif 1.2 <= aspect_ratio < 1.5 or 2.5 < aspect_ratio <= 3.0:
                                aspect_score = 0.7
                            else:
                                aspect_score = 0.3
                            
                            # Confidence score (if available)
                            confidence = ref_frame.get('confidence', 0.5)
                            conf_score = confidence
                            
                            # Combined score
                            total_score = (size_score * 1.0) + (aspect_score * 0.5) + (conf_score * 2.0)
                            
                            scored_frames.append((total_score, ref_frame))
                    
                    # Sort by score (highest first)
                    scored_frames.sort(key=lambda x: x[0], reverse=True)
                    
                    # FIRST: Try to use stored best_body_image if available (highest quality)
                    profile_img = None
                    best_frame = None
                    if profile.best_body_image and profile.best_body_image.get('image_data'):
                        try:
                            import base64
                            from PIL import Image, ImageTk
                            import io
                            # Decode base64 image data
                            image_data = profile.best_body_image.get('image_data')
                            if isinstance(image_data, str):
                                image_bytes = base64.b64decode(image_data)
                                pil_image = Image.open(io.BytesIO(image_bytes))
                                profile_img = ImageTk.PhotoImage(pil_image)
                                best_frame = profile.best_body_image
                                print(f"✓ Using stored best body image for {profile.name} (quality: {profile.best_body_image.get('quality', 0):.2f})")
                        except Exception as e:
                            print(f"⚠ Could not decode stored best_body_image: {e}")
                    
                    # FALLBACK: Try frames in order of quality if no stored image
                    if not profile_img:
                        debug_info = []
                        for score, ref_frame in scored_frames[:10]:  # Try top 10
                            video_path = ref_frame.get('video_path', '')
                            frame_num = ref_frame.get('frame_num', '?')
                            debug_info.append(f"Trying: {os.path.basename(video_path)} frame {frame_num} (score: {score:.2f})")
                            
                            profile_img = self._extract_profile_image(ref_frame)
                            if profile_img:
                                best_frame = ref_frame
                                # Also extract foot region from the same frame
                                foot_img = self._extract_foot_region_image(ref_frame)
                                
                                # If foot image extraction failed, try using foot_reference_frames if available
                                if not foot_img and profile.foot_reference_frames and len(profile.foot_reference_frames) > 0:
                                    # Try to find a foot reference frame from the same video/frame
                                    for foot_ref in profile.foot_reference_frames:
                                        if (foot_ref.get('video_path') == ref_frame.get('video_path') and 
                                            foot_ref.get('frame_num') == ref_frame.get('frame_num')):
                                            # Use the dedicated foot reference frame
                                            foot_img = self._extract_foot_region_image(foot_ref)
                                            if foot_img:
                                                break
                                    
                                    # If still no foot image, try the first available foot reference frame
                                    if not foot_img:
                                        for foot_ref in profile.foot_reference_frames[:5]:  # Try first 5
                                            foot_img = self._extract_foot_region_image(foot_ref)
                                            if foot_img:
                                                break
                                
                                debug_info.append(f"✓ Successfully extracted image from {os.path.basename(video_path)} frame {frame_num}")
                                break
                            else:
                                debug_info.append(f"✗ Failed to extract from {os.path.basename(video_path)} frame {frame_num}")
                    
                    # If no image found, show debug info
                    if not profile_img:
                        if debug_info:
                            print(f"⚠ Image extraction failed for player '{profile.name}':")
                            for info in debug_info:
                                print(f"  {info}")
                        else:
                            print(f"⚠ No valid reference frames found for player '{profile.name}'")
                            print(f"   Total reference frames: {len(profile.reference_frames) if profile.reference_frames else 0}")
                            if profile.reference_frames:
                                print(f"   First frame sample: {profile.reference_frames[0] if len(profile.reference_frames) > 0 else 'N/A'}")
                
                # Display images side by side
                if profile_img and best_frame:
                    # Player image (left side)
                    player_img_frame = ttk.Frame(images_container)
                    player_img_frame.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
                    
                    ttk.Label(player_img_frame, text="Full Player", font=("Arial", 9, "bold")).pack()
                    img_label = ttk.Label(player_img_frame, image=profile_img)
                    img_label.image = profile_img  # type: ignore[attr-defined]  # Keep a reference
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
                        foot_label.image = foot_img  # type: ignore[attr-defined]  # Keep a reference
                        foot_label.pack(pady=5)
                        
                        ttk.Label(foot_img_frame, text="Bottom 10-30% of bbox\n(Feet/shoes area, key identification feature)", 
                                font=("Arial", 7), justify=tk.CENTER, foreground="blue").pack()
                    else:
                        # Show placeholder if foot region couldn't be extracted
                        foot_img_frame = ttk.Frame(images_container)
                        foot_img_frame.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
                        
                        ttk.Label(foot_img_frame, text="Foot/Shoe Region", font=("Arial", 9, "bold")).pack()
                        ttk.Label(foot_img_frame, text="Not available\n(Region too small or invalid)", 
                                font=("Arial", 7), foreground="gray", justify=tk.CENTER).pack(pady=20)
                else:
                    # Provide more helpful error message
                    error_text = "No valid profile image found\n\n"
                    if not profile.reference_frames or len(profile.reference_frames) == 0:
                        error_text += "• No reference frames available for this player\n"
                        error_text += "• Run analysis with Re-ID enabled to collect reference frames\n"
                        error_text += "• Or use 'Convert Tracks → Anchor Frames' to add reference frames"
                    else:
                        error_text += f"• Found {len(profile.reference_frames)} reference frame(s)\n"
                        error_text += "• Images may be rejected due to:\n"
                        error_text += "  - Video file not found at stored path\n"
                        error_text += "  - Image too small or invalid bbox\n"
                        error_text += "  - Image contains too much field (green)\n"
                        error_text += "  - Check console for detailed error messages"
                    
                    ttk.Label(images_container, text=error_text, 
                            font=("Arial", 9), foreground="gray", justify=tk.LEFT).pack(pady=10)
            except Exception as e:
                # Show error message with details
                import traceback
                error_details = traceback.format_exc()
                print(f"Error loading player images: {error_details}")
                error_msg = f"Error loading images: {str(e)}\n\nCheck console for details."
                ttk.Label(images_container, text=error_msg, 
                        font=("Arial", 8), foreground="red", justify=tk.LEFT).pack()
            
            # Player info
            info_frame = ttk.LabelFrame(main_frame, text="Player Information", padding="10")
            info_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Editable fields
            ttk.Label(info_frame, text="Player Name:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            name_var = tk.StringVar(value=profile.name if profile.name else "")
            name_entry = ttk.Entry(info_frame, textvariable=name_var, width=25)
            name_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
            
            ttk.Label(info_frame, text="Jersey Number:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
            jersey_var = tk.StringVar(value=profile.jersey_number if profile.jersey_number else "")
            jersey_entry = ttk.Entry(info_frame, textvariable=jersey_var, width=10)
            jersey_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
            
            ttk.Label(info_frame, text="Team:", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
            team_var = tk.StringVar(value=profile.team if profile.team else "")
            team_entry = ttk.Entry(info_frame, textvariable=team_var, width=20)
            team_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
            
            # Read-only info
            ttk.Label(info_frame, text="Has Re-ID Features:", font=("Arial", 9, "bold")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
            has_features_text = "✓ Yes (can be auto-recognized)" if profile.features is not None else "✗ No (manual only)"
            ttk.Label(info_frame, text=has_features_text, 
                     foreground="green" if profile.features is not None else "red").grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
            
            ttk.Label(info_frame, text="Reference Frames:", font=("Arial", 9, "bold")).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
            ref_count = len(profile.reference_frames) if profile.reference_frames else 0
            ttk.Label(info_frame, text=str(ref_count)).grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
            
            # Confidence metrics section
            confidence_metrics = gallery.get_player_confidence_metrics(player_id)
            overall_conf = confidence_metrics['overall_confidence']
            
            # Confidence frame
            conf_frame = ttk.LabelFrame(main_frame, text="Confidence Metrics", padding="10")
            conf_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Overall confidence with color coding
            ttk.Label(conf_frame, text="Overall Confidence:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            conf_color = "green" if overall_conf >= 0.7 else ("orange" if overall_conf >= 0.4 else "red")
            conf_text = f"{overall_conf:.3f} ({'High' if overall_conf >= 0.7 else ('Medium' if overall_conf >= 0.4 else 'Low')})"
            ttk.Label(conf_frame, text=conf_text, foreground=conf_color, font=("Arial", 9, "bold")).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
            
            # Detailed metrics
            ttk.Label(conf_frame, text="Avg Similarity:", font=("Arial", 9)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(conf_frame, text=f"{confidence_metrics['avg_similarity']:.3f}").grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
            
            ttk.Label(conf_frame, text="Ref Frame Count:", font=("Arial", 9)).grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(conf_frame, text=str(confidence_metrics['ref_frame_count'])).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
            
            ttk.Label(conf_frame, text="Avg Detection Conf:", font=("Arial", 9)).grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(conf_frame, text=f"{confidence_metrics['avg_detection_confidence']:.3f}").grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
            
            # Warning if confidence is low
            if overall_conf < 0.4:
                warning_text = "⚠ Low confidence - consider adding more/better quality video"
                ttk.Label(conf_frame, text=warning_text, foreground="red", font=("Arial", 8, "italic")).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5, 0))
            
            ttk.Label(info_frame, text="Created:", font=("Arial", 9, "bold")).grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
            created = profile.created_at[:19] if profile.created_at else "Unknown"
            ttk.Label(info_frame, text=created, font=("Arial", 8)).grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
            
            ttk.Label(info_frame, text="Last Updated:", font=("Arial", 9, "bold")).grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
            updated = profile.updated_at[:19] if profile.updated_at else "Unknown"
            ttk.Label(info_frame, text=updated, font=("Arial", 8)).grid(row=6, column=1, sticky=tk.W, padx=5, pady=5)
            
            # Reference frames list
            if ref_count > 0:
                ref_frame = ttk.LabelFrame(main_frame, text="Reference Frames", padding="10")
                ref_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
                
                # Create frame for listbox and scrollbar
                listbox_frame = ttk.Frame(ref_frame)
                listbox_frame.pack(fill=tk.BOTH, expand=True)
                
                # Create scrollbar
                ref_scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
                ref_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                
                # Create listbox with scrollbar
                ref_listbox = tk.Listbox(listbox_frame, height=10, font=("Arial", 8), 
                                        yscrollcommand=ref_scrollbar.set)
                ref_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                ref_scrollbar.config(command=ref_listbox.yview)
                
                # Store reference frames data for access
                # Sort by frame number (low to high) for easier management
                # Store tuples of (original_index, ref) to maintain mapping for deletion
                ref_frames_data = []
                sorted_refs = []
                for i, ref in enumerate(profile.reference_frames):
                    frame_num = ref.get('frame_num', 0)
                    # Convert to int for sorting, use 0 if invalid
                    try:
                        frame_num_int = int(frame_num) if frame_num is not None else 0
                    except (ValueError, TypeError):
                        frame_num_int = 0
                    sorted_refs.append((frame_num_int, i, ref))
                
                # Sort by frame number (low to high)
                sorted_refs.sort(key=lambda x: x[0])
                
                # Display sorted frames and store mapping
                for display_idx, (frame_num_int, original_idx, ref) in enumerate(sorted_refs):
                    video_name = os.path.basename(ref.get('video_path', 'unknown')) if ref.get('video_path') else 'unknown'
                    frame_num = ref.get('frame_num', '?')
                    ref_listbox.insert(tk.END, f"{display_idx+1}. {video_name} - Frame {frame_num}")
                    # Store tuple: (original_gallery_index, ref_data)
                    ref_frames_data.append((original_idx, ref))
                
                def open_frame_in_viewer():
                    """Open the selected reference frame in the gallery seeder"""
                    selection = ref_listbox.curselection()
                    if not selection:
                        messagebox.showwarning("No Selection", "Please select a reference frame to view.")
                        return
                    
                    display_idx = selection[0]
                    if display_idx < 0 or display_idx >= len(ref_frames_data):
                        messagebox.showerror("Error", "Invalid frame selection.")
                        return
                    
                    # Get original index and ref data (with additional safety check)
                    try:
                        original_idx, ref = ref_frames_data[display_idx]
                    except (IndexError, ValueError) as e:
                        messagebox.showerror("Error", f"Invalid frame selection: {str(e)}")
                        return
                    video_path = ref.get('video_path')
                    frame_num = ref.get('frame_num')
                    
                    if not video_path or frame_num is None:
                        messagebox.showerror("Error", "Reference frame missing video path or frame number.")
                        return
                    
                    if not os.path.exists(video_path):
                        messagebox.showerror("Error", f"Video file not found:\n{video_path}")
                        return
                    
                    try:
                        # Open or get existing gallery seeder window
                        if not hasattr(self, '_gallery_seeder_window') or not self._gallery_seeder_window or not self._gallery_seeder_window.winfo_exists():
                            from player_gallery_seeder import PlayerGallerySeeder
                            self._gallery_seeder_window = tk.Toplevel(self.root)
                            self._gallery_seeder_window.transient(self.root)
                            app = PlayerGallerySeeder(self._gallery_seeder_window)
                            self._gallery_seeder_app = app  # Store app instance
                        else:
                            # Get the existing app instance
                            app = getattr(self, '_gallery_seeder_app', None)
                            
                            # If we can't find the app, recreate the window
                            if not app or not hasattr(app, 'jump_to_frame'):
                                if hasattr(self, '_gallery_seeder_window') and self._gallery_seeder_window:
                                    self._gallery_seeder_window.destroy()
                                from player_gallery_seeder import PlayerGallerySeeder
                                self._gallery_seeder_window = tk.Toplevel(self.root)
                                self._gallery_seeder_window.transient(self.root)
                                app = PlayerGallerySeeder(self._gallery_seeder_window)
                                self._gallery_seeder_app = app  # Store app instance
                        
                        # Get bbox from reference frame if available
                        highlight_bbox = None
                        if 'bbox' in ref and ref['bbox']:
                            bbox = ref['bbox']
                            if isinstance(bbox, list) and len(bbox) == 4:
                                highlight_bbox = tuple(bbox)  # (x1, y1, x2, y2)
                        
                        # Jump to the frame with highlighting and player detection
                        if hasattr(app, 'jump_to_frame'):
                            app.jump_to_frame(int(frame_num), video_path, 
                                            highlight_bbox=highlight_bbox,
                                            detect_all_players=True)
                            self._gallery_seeder_window.lift()
                            self._gallery_seeder_window.focus_force()
                            messagebox.showinfo("Frame Opened", 
                                              f"Opened {os.path.basename(video_path)} at frame {frame_num}.\n\n"
                                              "The player is highlighted in green.\n"
                                              "Other detected players are shown in orange.\n\n"
                                              "You can click on any player to tag them.")
                        else:
                            messagebox.showerror("Error", "Could not access gallery seeder.")
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not open frame:\n\n{str(e)}")
                
                def delete_selected_frames():
                    """Delete the selected reference frame(s) - supports multiple selection"""
                    selection = ref_listbox.curselection()
                    if not selection:
                        messagebox.showwarning("No Selection", "Please select reference frame(s) to delete.\n\nTip: Hold Shift and click to select multiple frames.")
                        return
                    
                    # Get all selected display indices and their original gallery indices
                    # Need to collect original indices first, then sort in reverse for deletion
                    selected_original_indices = []
                    selected_refs_info = []
                    for display_idx in selection:
                        if display_idx < 0 or display_idx >= len(ref_frames_data):
                            continue
                        original_idx, ref = ref_frames_data[display_idx]
                        selected_original_indices.append(original_idx)
                        video_name = os.path.basename(ref.get('video_path', 'unknown')) if ref.get('video_path') else 'unknown'
                        frame_num = ref.get('frame_num', '?')
                        selected_refs_info.append((video_name, frame_num))
                    
                    if not selected_original_indices:
                        messagebox.showwarning("No Selection", "Invalid selection.")
                        return
                    
                    # Sort original indices in reverse order for deletion (delete from end to start)
                    selected_original_indices.sort(reverse=True)
                    
                    if len(selected_original_indices) == 1:
                        video_name, frame_num = selected_refs_info[0]
                        message = f"Delete reference frame?\n\nVideo: {video_name}\nFrame: {frame_num}\n\nThis cannot be undone!"
                    else:
                        message = f"Delete {len(selected_original_indices)} selected reference frames?\n\nThis cannot be undone!"
                    
                    result = messagebox.askyesno("Confirm Delete", message, icon='warning')
                    
                    if result:
                        try:
                            deleted_count = 0
                            errors = []
                            
                            # Delete using original gallery indices (from end to start)
                            for original_idx in selected_original_indices:
                                # Find the ref info for this original index
                                ref_info = None
                                for orig_idx, ref in ref_frames_data:
                                    if orig_idx == original_idx:
                                        ref_info = ref
                                        break
                                
                                if ref_info is None:
                                    errors.append(f"Could not find frame at index {original_idx}")
                                    continue
                                
                                video_name = os.path.basename(ref_info.get('video_path', 'unknown')) if ref_info.get('video_path') else 'unknown'
                                frame_num = ref_info.get('frame_num', '?')
                                
                                # Remove from gallery using original index
                                success = gallery.remove_reference_frame(player_id, original_idx)
                                
                                if success:
                                    deleted_count += 1
                                else:
                                    errors.append(f"Frame {frame_num} from {video_name}")
                            
                            # Refresh the list (re-sort after deletion)
                            ref_listbox.delete(0, tk.END)
                            ref_frames_data.clear()
                            
                            # Reload profile to get updated reference frames
                            profile = gallery.get_player(player_id)
                            if profile and profile.reference_frames:
                                # Re-sort by frame number
                                sorted_refs = []
                                for i, ref in enumerate(profile.reference_frames):
                                    frame_num = ref.get('frame_num', 0)
                                    try:
                                        frame_num_int = int(frame_num) if frame_num is not None else 0
                                    except (ValueError, TypeError):
                                        frame_num_int = 0
                                    sorted_refs.append((frame_num_int, i, ref))
                                
                                sorted_refs.sort(key=lambda x: x[0])
                                
                                for display_idx, (frame_num_int, original_idx, ref) in enumerate(sorted_refs):
                                    video_name = os.path.basename(ref.get('video_path', 'unknown')) if ref.get('video_path') else 'unknown'
                                    frame_num = ref.get('frame_num', '?')
                                    ref_listbox.insert(tk.END, f"{display_idx+1}. {video_name} - Frame {frame_num}")
                                    ref_frames_data.append((original_idx, ref))
                            
                            # Update reference frame count in info section
                            ref_count = len(profile.reference_frames) if profile.reference_frames else 0
                            # Find and update the label (it's at row 4, column 1)
                            for widget in info_frame.grid_slaves(row=4, column=1):
                                if isinstance(widget, ttk.Label):
                                    widget.config(text=str(ref_count))
                                    break
                            
                            if deleted_count > 0:
                                if len(selected_original_indices) == 1:
                                    video_name, frame_num = selected_refs_info[0]
                                    messagebox.showinfo("Success", f"Deleted reference frame {frame_num} from {video_name}")
                                else:
                                    messagebox.showinfo("Success", f"Deleted {deleted_count} reference frame(s).")
                            
                            if errors:
                                messagebox.showwarning("Partial Success", 
                                                     f"Deleted {deleted_count} frame(s), but {len(errors)} failed:\n\n" + 
                                                     "\n".join(errors[:5]) + 
                                                     ("\n..." if len(errors) > 5 else ""))
                            
                            # If no frames left, close the reference frames section
                            if ref_count == 0:
                                ref_frame.destroy()
                        except Exception as e:
                            messagebox.showerror("Error", f"Could not delete reference frame(s):\n\n{str(e)}")
                
                def delete_all_frames():
                    """Delete all reference frames for this player"""
                    if not ref_frames_data:
                        messagebox.showwarning("No Frames", "No reference frames to delete.")
                        return
                    
                    result = messagebox.askyesno(
                        "Confirm Delete All",
                        f"Delete ALL {len(ref_frames_data)} reference frames for {profile.name}?\n\n"
                        f"This cannot be undone!",
                        icon='warning'
                    )
                    
                    if result:
                        try:
                            # Delete all frames using original indices (from end to start)
                            deleted_count = 0
                            # Get all original indices and sort in reverse
                            all_original_indices = [orig_idx for orig_idx, _ in ref_frames_data]
                            all_original_indices.sort(reverse=True)
                            
                            for original_idx in all_original_indices:
                                success = gallery.remove_reference_frame(player_id, original_idx)
                                if success:
                                    deleted_count += 1
                            
                            # Refresh the list
                            ref_listbox.delete(0, tk.END)
                            ref_frames_data.clear()
                            
                            # Update reference frame count
                            ref_count = 0
                            for widget in info_frame.grid_slaves(row=4, column=1):
                                if isinstance(widget, ttk.Label):
                                    widget.config(text="0")
                                    break
                            
                            messagebox.showinfo("Success", f"Deleted all {deleted_count} reference frames.")
                            
                            # Close the reference frames section
                            ref_frame.destroy()
                        except Exception as e:
                            messagebox.showerror("Error", f"Could not delete all reference frames:\n\n{str(e)}")
                
                def delete_frames_above_threshold():
                    """Delete all reference frames above a specified frame number threshold"""
                    if not ref_frames_data:
                        messagebox.showwarning("No Frames", "No reference frames to delete.")
                        return
                    
                    # Get the highest frame number to show as default
                    max_frame = 0
                    for _, ref in ref_frames_data:
                        frame_num = ref.get('frame_num', 0)
                        try:
                            frame_num_int = int(frame_num) if frame_num is not None else 0
                            max_frame = max(max_frame, frame_num_int)
                        except (ValueError, TypeError):
                            pass
                    
                    # Create a simple dialog to get threshold
                    threshold_dialog = tk.Toplevel(detail_window)
                    threshold_dialog.title("Delete Frames Above Threshold")
                    threshold_dialog.transient(detail_window)
                    threshold_dialog.grab_set()
                    threshold_dialog.geometry("400x150")
                    
                    ttk.Label(threshold_dialog, text=f"Delete all frames above frame number:", 
                             font=("Arial", 9)).pack(pady=10)
                    
                    threshold_var = tk.StringVar(value=str(max_frame // 2))  # Default to half of max
                    threshold_entry = ttk.Entry(threshold_dialog, textvariable=threshold_var, width=20, font=("Arial", 10))
                    threshold_entry.pack(pady=5)
                    threshold_entry.select_range(0, tk.END)
                    threshold_entry.focus()
                    
                    info_label = ttk.Label(threshold_dialog, 
                                          text=f"Frames range from 0 to {max_frame}",
                                          font=("Arial", 8), foreground="gray")
                    info_label.pack(pady=5)
                    
                    def confirm_delete_above():
                        try:
                            threshold = int(threshold_var.get())
                            
                            # Find frames above threshold
                            frames_to_delete = []
                            for display_idx, (original_idx, ref) in enumerate(ref_frames_data):
                                frame_num = ref.get('frame_num', 0)
                                try:
                                    frame_num_int = int(frame_num) if frame_num is not None else 0
                                    if frame_num_int > threshold:
                                        frames_to_delete.append((original_idx, ref, frame_num_int))
                                except (ValueError, TypeError):
                                    pass
                            
                            if not frames_to_delete:
                                messagebox.showinfo("No Frames", f"No frames found above frame {threshold}.")
                                threshold_dialog.destroy()
                                return
                            
                            # Confirm deletion
                            result = messagebox.askyesno(
                                "Confirm Delete",
                                f"Delete {len(frames_to_delete)} reference frame(s) above frame {threshold}?\n\n"
                                f"This cannot be undone!",
                                icon='warning'
                            )
                            
                            if result:
                                threshold_dialog.destroy()
                                
                                # Sort by original index in reverse for deletion
                                frames_to_delete.sort(key=lambda x: x[0], reverse=True)
                                
                                deleted_count = 0
                                errors = []
                                
                                for original_idx, ref, frame_num_int in frames_to_delete:
                                    success = gallery.remove_reference_frame(player_id, original_idx)
                                    if success:
                                        deleted_count += 1
                                    else:
                                        video_name = os.path.basename(ref.get('video_path', 'unknown')) if ref.get('video_path') else 'unknown'
                                        errors.append(f"Frame {frame_num_int} from {video_name}")
                                
                                # Refresh the list
                                ref_listbox.delete(0, tk.END)
                                ref_frames_data.clear()
                                
                                # Reload and re-sort
                                profile = gallery.get_player(player_id)
                                if profile and profile.reference_frames:
                                    sorted_refs = []
                                    for i, ref in enumerate(profile.reference_frames):
                                        frame_num = ref.get('frame_num', 0)
                                        try:
                                            frame_num_int = int(frame_num) if frame_num is not None else 0
                                        except (ValueError, TypeError):
                                            frame_num_int = 0
                                        sorted_refs.append((frame_num_int, i, ref))
                                    
                                    sorted_refs.sort(key=lambda x: x[0])
                                    
                                    for display_idx, (frame_num_int, original_idx, ref) in enumerate(sorted_refs):
                                        video_name = os.path.basename(ref.get('video_path', 'unknown')) if ref.get('video_path') else 'unknown'
                                        frame_num = ref.get('frame_num', '?')
                                        ref_listbox.insert(tk.END, f"{display_idx+1}. {video_name} - Frame {frame_num}")
                                        ref_frames_data.append((original_idx, ref))
                                
                                # Update count
                                ref_count = len(profile.reference_frames) if profile.reference_frames else 0
                                for widget in info_frame.grid_slaves(row=4, column=1):
                                    if isinstance(widget, ttk.Label):
                                        widget.config(text=str(ref_count))
                                        break
                                
                                if deleted_count > 0:
                                    messagebox.showinfo("Success", f"Deleted {deleted_count} reference frame(s) above frame {threshold}.")
                                
                                if errors:
                                    messagebox.showwarning("Partial Success", 
                                                         f"Deleted {deleted_count} frame(s), but {len(errors)} failed:\n\n" + 
                                                         "\n".join(errors[:5]) + 
                                                         ("\n..." if len(errors) > 5 else ""))
                                
                                if ref_count == 0:
                                    ref_frame.destroy()
                        except ValueError:
                            messagebox.showerror("Error", "Please enter a valid frame number.")
                    
                    button_frame = ttk.Frame(threshold_dialog)
                    button_frame.pack(pady=10)
                    ttk.Button(button_frame, text="Delete", command=confirm_delete_above).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="Cancel", command=threshold_dialog.destroy).pack(side=tk.LEFT, padx=5)
                    
                    # Bind Enter key
                    threshold_entry.bind('<Return>', lambda e: confirm_delete_above())

                # Use an external variable to track last selection for Shift-click range selection
                last_ref_selection = {'index': None}

                def on_listbox_click(event):
                    """Handle click with Shift key for range selection"""
                    current = ref_listbox.nearest(event.y)
                    
                    if event.state & 0x1:  # Shift key pressed
                        if last_ref_selection['index'] is not None:
                            # Select range from last selection to current
                            start = min(last_ref_selection['index'], current)
                            end = max(last_ref_selection['index'], current)
                            ref_listbox.selection_clear(0, tk.END)
                            ref_listbox.selection_set(start, end)
                            # Update last selection to the end of the range
                            last_ref_selection['index'] = end
                        else:
                            # No previous selection, just select current
                            last_ref_selection['index'] = current
                    else:
                        # Regular click - update last selection
                        last_ref_selection['index'] = current
                
                ref_listbox.bind('<Button-1>', on_listbox_click)
                ref_listbox.bind('<Double-Button-1>', lambda e: open_frame_in_viewer())
                
                # Add buttons for reference frame actions
                ref_button_frame = ttk.Frame(ref_frame)
                ref_button_frame.pack(fill=tk.X, pady=(5, 0))
                
                ttk.Button(ref_button_frame, text="View Frame", command=open_frame_in_viewer, width=15).pack(side=tk.LEFT, padx=5)
                ttk.Button(ref_button_frame, text="Delete Selected", command=delete_selected_frames, width=15).pack(side=tk.LEFT, padx=5)
                ttk.Button(ref_button_frame, text="Delete Above Frame...", command=delete_frames_above_threshold, width=18).pack(side=tk.LEFT, padx=5)
                ttk.Label(ref_button_frame, text="(Hold Shift to select multiple)", font=("Arial", 8), foreground="gray").pack(side=tk.LEFT, padx=5)
                ttk.Button(ref_button_frame, text="Delete All", command=delete_all_frames, width=15).pack(side=tk.RIGHT, padx=5)
            
            # Action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            def save_changes():
                try:
                    new_name = name_var.get().strip() or None
                    new_jersey = jersey_var.get().strip() or None
                    new_team = team_var.get().strip() or None
                    
                    # Validate name is not empty
                    if not new_name:
                        messagebox.showerror("Error", "Player name cannot be empty!")
                        return
                    
                    gallery.update_player(
                        player_id=player_id,
                        name=new_name,
                        jersey_number=new_jersey,
                        team=new_team
                    )
                    
                    # IMPORTANT: Save gallery to disk immediately when user makes manual changes
                    gallery.save_gallery()
                    
                    messagebox.showinfo("Success", f"Updated {new_name} successfully!")
                    detail_window.destroy()
                    self._refresh_gallery_tab(parent_frame)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not update player:\n\n{str(e)}")
            
            def delete_player():
                result = messagebox.askyesno(
                    "Confirm Delete", 
                    f"Are you sure you want to delete '{profile.name}' from the gallery?\n\nThis cannot be undone!",
                    icon='warning'
                )
                
                if result:
                    try:
                        gallery.remove_player(player_id)
                        messagebox.showinfo("Success", f"Deleted {profile.name} from gallery")
                        detail_window.destroy()
                        self._refresh_gallery_tab(parent_frame)
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not delete player:\n\n{str(e)}")
            
            ttk.Button(button_frame, text="💾 Save Changes", command=save_changes, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🗑️ Delete Player", command=delete_player, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Close", command=detail_window.destroy, width=10).pack(side=tk.RIGHT, padx=5)
            
            detail_window.lift()
            detail_window.focus_force()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not show player details:\n\n{str(e)}")
    
    def _delete_selected_player_from_gallery(self, parent_frame, listbox, player_list_data, index=None):
        """Delete the selected player from the gallery"""
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            
            # Get index from parameter or from listbox selection
            if index is None:
                selection = listbox.curselection()
                if not selection or len(selection) == 0:
                    messagebox.showwarning("No Selection", "Please select a player to delete.")
                    return
                index = selection[0]
            
            # Skip header rows (0 and 1)
            if index <= 1 or (index - 2) >= len(player_list_data):
                messagebox.showwarning("Invalid Selection", "Please select a valid player.")
                return
            
            player_id, player_name = player_list_data[index - 2]
            profile = gallery.get_player(player_id)
            
            # Confirm deletion
            result = messagebox.askyesno(
                "Confirm Delete", 
                f"Are you sure you want to delete '{player_name}' from the gallery?\n\n"
                f"This will permanently remove:\n"
                f"• All Re-ID features\n"
                f"• All reference frames ({len(profile.reference_frames) if profile.reference_frames else 0} frames)\n"
                f"• All player data\n\n"
                f"This cannot be undone!",
                icon='warning'
            )
            
            if result:
                try:
                    gallery.remove_player(player_id)
                    messagebox.showinfo("Success", f"Deleted '{player_name}' from gallery")
                    # Refresh the gallery tab
                    self._refresh_gallery_tab(parent_frame)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not delete player:\n\n{str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete player:\n\n{str(e)}")
    
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
    
    def preview_box_color(self):
        """Preview the selected box color in a popup window"""
        from color_picker_utils import rgb_string_to_tuple
        r, g, b = rgb_string_to_tuple(self.box_color_rgb.get(), default=(0, 255, 0))
        
        # Create preview window
        preview_window = tk.Toplevel(self.root)
        preview_window.title("Box Color Preview")
        preview_window.geometry("300x200")
        preview_window.transient(self.root)
        
        # Convert RGB to hex color for tkinter
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        
        # Main frame
        main_frame = ttk.Frame(preview_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Color Preview", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        # Color preview box
        color_frame = tk.Frame(main_frame, bg=hex_color, width=200, height=100, relief=tk.RAISED, borderwidth=3)
        color_frame.pack(pady=10)
        color_frame.pack_propagate(False)  # Maintain size
        
        # RGB values
        rgb_text = f"RGB: ({r}, {g}, {b})\nHex: {hex_color}"
        ttk.Label(main_frame, text=rgb_text, justify=tk.CENTER).pack(pady=5)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=preview_window.destroy).pack(pady=10)
        
        preview_window.lift()
    
    def preview_label_color(self):
        """Preview the selected label color in a popup window"""
        # Get color values with error handling
        from color_picker_utils import rgb_string_to_tuple
        r, g, b = rgb_string_to_tuple(self.label_color_rgb.get(), default=(255, 255, 255))
        
        # Create preview window
        preview_window = tk.Toplevel(self.root)
        preview_window.title("Label Color Preview")
        preview_window.geometry("300x200")
        preview_window.transient(self.root)
        
        # Convert RGB to hex color for tkinter
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        
        # Main frame
        main_frame = ttk.Frame(preview_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Label Color Preview", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        # Color preview box
        color_frame = tk.Frame(main_frame, bg=hex_color, width=200, height=100, relief=tk.RAISED, borderwidth=3)
        color_frame.pack(pady=10)
        color_frame.pack_propagate(False)  # Maintain size
        
        # RGB values
        rgb_text = f"RGB: ({r}, {g}, {b})\nHex: {hex_color}"
        ttk.Label(main_frame, text=rgb_text, justify=tk.CENTER).pack(pady=5)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=preview_window.destroy).pack(pady=10)
        
        preview_window.lift()
        preview_window.focus_force()
    
    def _get_label_color(self):
        """Get label color with error handling for empty/invalid values."""
        from color_picker_utils import rgb_string_to_tuple
        r, g, b = rgb_string_to_tuple(self.label_color_rgb.get(), default=(255, 255, 255))
        return (b, g, r)  # BGR format for OpenCV
    
    def _get_box_color_bgr(self):
        """Get box color in BGR format for OpenCV"""
        from color_picker_utils import rgb_string_to_tuple
        r, g, b = rgb_string_to_tuple(self.box_color_rgb.get(), default=(0, 255, 0))
        return (b, g, r)  # BGR format
    
    def _get_analytics_color_bgr(self):
        """Get analytics color in BGR format for OpenCV"""
        from color_picker_utils import rgb_string_to_tuple
        r, g, b = rgb_string_to_tuple(self.analytics_color_rgb.get(), default=(255, 255, 255))
        return (b, g, r)  # BGR format
    
    def _get_analytics_title_color_bgr(self):
        """Get analytics title color in BGR format for OpenCV"""
        from color_picker_utils import rgb_string_to_tuple
        r, g, b = rgb_string_to_tuple(self.analytics_title_color_rgb.get(), default=(255, 255, 0))
        return (b, g, r)  # BGR format
    
    def _get_statistics_bg_color_bgr(self):
        """Get statistics background color in BGR format for OpenCV"""
        from color_picker_utils import rgb_string_to_tuple
        r, g, b = rgb_string_to_tuple(self.statistics_bg_color_rgb.get(), default=(0, 0, 0))
        return (b, g, r)  # BGR format
    
    def _get_statistics_text_color_bgr(self):
        """Get statistics text color in BGR format for OpenCV"""
        from color_picker_utils import rgb_string_to_tuple
        r, g, b = rgb_string_to_tuple(self.statistics_text_color_rgb.get(), default=(255, 255, 255))
        return (b, g, r)  # BGR format
    
    def _get_statistics_title_color_bgr(self):
        """Get statistics title color in BGR format for OpenCV"""
        from color_picker_utils import rgb_string_to_tuple
        r, g, b = rgb_string_to_tuple(self.statistics_title_color_rgb.get(), default=(255, 255, 0))
        return (b, g, r)  # BGR format
    
    def _safe_get_int(self, var, default=0):
        """Safely get integer value from IntVar, handling empty Spinbox fields"""
        try:
            return var.get()
        except (tk.TclError, ValueError):
            return default
    
    def _safe_get_double(self, var, default=0.0):
        """Safely get float value from DoubleVar, handling empty Spinbox fields"""
        try:
            return var.get()
        except (tk.TclError, ValueError):
            return default
    
    def update_preview(self):
        """Update the preview canvas to show what the annotation will look like"""
        if not hasattr(self, 'preview_canvas'):
            return
        try:
            if not self.preview_canvas.winfo_exists():
                return
        except:
            return
        
        try:
            import cv2
            import numpy as np
            from PIL import Image, ImageTk
            
            # Create a black background (simulating video frame) - larger for both previews
            preview_img = np.zeros((250, 400, 3), dtype=np.uint8)
            
            # Debug: Draw a test rectangle to verify preview is working
            # cv2.rectangle(preview_img, (10, 10), (390, 240), (128, 128, 128), 2)  # Gray border
            
            # Get current settings (using safe getters to handle empty Spinbox fields)
            viz_style = self.viz_style.get()  # Legacy support
            color_mode = self.viz_color_mode.get()
            use_custom = self.use_custom_box_color.get()
            box_thickness = self._safe_get_int(self.box_thickness, 2)
            box_shrink = self._safe_get_double(self.box_shrink_factor, 0.10)
            show_labels = self.show_player_labels.get()
            show_ball = self.show_ball_possession.get()
            ellipse_w = self._safe_get_int(self.ellipse_width, 20)
            ellipse_h = self._safe_get_int(self.ellipse_height, 12)
            ellipse_outline = self._safe_get_int(self.ellipse_outline_thickness, 3)
            show_predicted = self.show_predicted_boxes.get()
            prediction_style = self.prediction_style.get()
            prediction_size = self._safe_get_int(self.prediction_size, 5)
            # NEW: Separate controls for bounding boxes and circles
            show_bounding_boxes = self.show_bounding_boxes.get()
            show_circles_at_feet = self.show_circles_at_feet.get()
            label_type = self.label_type.get()
            label_custom_text = self.label_custom_text.get()
            label_font_face = self.label_font_face.get()
            try:
                prediction_alpha = self.prediction_color_alpha.get()
                if prediction_alpha == "" or prediction_alpha is None:
                    prediction_alpha = 255  # Default to fully opaque
            except (tk.TclError, ValueError):
                prediction_alpha = 255  # Default to fully opaque
            # Get base color (BGR)
            try:
                pred_b = self.prediction_color_b.get()
                pred_g = self.prediction_color_g.get()
                pred_r = self.prediction_color_r.get()
                # Handle empty strings (default to 0)
                base_prediction_color = (
                    int(pred_b) if pred_b and str(pred_b).strip() else 0,
                    int(pred_g) if pred_g and str(pred_g).strip() else 0,
                    int(pred_r) if pred_r and str(pred_r).strip() else 0
                )
            except (ValueError, tk.TclError):
                # Fallback to default color if parsing fails
                base_prediction_color = (0, 255, 255)  # Default yellow
            # Apply opacity by blending with background (black)
            alpha_factor = prediction_alpha / 255.0
            prediction_color = tuple(int(c * alpha_factor) for c in base_prediction_color)
            
            # Determine base color
            if use_custom:
                try:
                    from color_picker_utils import rgb_string_to_tuple
                    r_val, g_val, b_val = rgb_string_to_tuple(self.box_color_rgb.get(), default=(0, 255, 0))
                    base_color = (b_val, g_val, r_val)  # BGR format
                except (ValueError, tk.TclError):
                    # Fallback to default color if parsing fails
                    base_color = (0, 255, 0)  # Default green
            elif color_mode == "team":
                base_color = (0, 255, 0)  # Green for team 1
            elif color_mode == "single":
                base_color = (255, 0, 255)  # Magenta
            else:  # gradient
                base_color = (255, 165, 0)  # Orange
            
            # Apply opacity to color
            try:
                player_viz_alpha = self.player_viz_alpha.get()
                if player_viz_alpha == "" or player_viz_alpha is None:
                    player_viz_alpha = 255  # Default to fully opaque
            except (tk.TclError, ValueError):
                player_viz_alpha = 255  # Default to fully opaque
            if player_viz_alpha < 255:
                alpha_factor = player_viz_alpha / 255.0
                color = tuple(int(c * alpha_factor) for c in base_color)
            else:
                color = base_color
            
            # Draw a sample player annotation in the center (top area)
            center_x, center_y = 200, 100
            box_width, box_height = 80, 120
            
            # Apply shrink factor
            if box_shrink > 0:
                box_width = int(box_width * (1 - box_shrink * 2))
                box_height = int(box_height * (1 - box_shrink * 2))
            
            x1 = center_x - box_width // 2
            y1 = center_y - box_height // 2
            x2 = center_x + box_width // 2
            y2 = center_y + box_height // 2
            
            # Draw bounding box if enabled (NEW: separate control)
            if show_bounding_boxes:
                cv2.rectangle(preview_img, (x1, y1), (x2, y2), color, box_thickness)
            # Legacy support: if new controls not used, fall back to viz_style
            elif viz_style in ["box", "both"]:
                cv2.rectangle(preview_img, (x1, y1), (x2, y2), color, box_thickness)
            
            # Draw enhanced feet marker if enabled (NEW: separate control, uses video game quality features)
            if show_circles_at_feet:
                foot_y = y2 + self.feet_marker_vertical_offset.get()  # Apply vertical offset
                ellipse_center = (center_x, int(foot_y))
                # Scale ellipse for preview (smaller than actual)
                preview_ellipse_w = int(ellipse_w * 0.5)  # Scale down for preview
                preview_ellipse_h = int(ellipse_h * 0.5)
                axes = (preview_ellipse_w // 2, preview_ellipse_h // 2)
                
                # Always use team color for circles (simulate team color in preview)
                team_color = (0, 255, 0) if color_mode == "team" else color  # Green for team 1 (BGR)
                
                # Use enhanced feet marker rendering with video game quality features
                try:
                    from overlay_renderer import OverlayRenderer
                    from overlay_metadata import OverlayMetadata
                    # Create minimal metadata for preview (provide dummy values for required args)
                    temp_metadata = OverlayMetadata(
                        video_path="preview",  # Dummy path for preview
                        fps=30.0,  # Dummy FPS
                        total_frames=100  # Dummy frame count
                    )
                    # Set basic visualization settings
                    temp_metadata.visualization_settings = {
                        "feet_marker_style": self.feet_marker_style.get(),
                        "feet_marker_opacity": self.feet_marker_opacity.get(),
                        "feet_marker_enable_glow": self.feet_marker_enable_glow.get(),
                        "feet_marker_glow_intensity": self.feet_marker_glow_intensity.get(),
                        "feet_marker_enable_shadow": self.feet_marker_enable_shadow.get(),
                        "feet_marker_shadow_offset": self.feet_marker_shadow_offset.get(),
                        "feet_marker_shadow_opacity": self.feet_marker_shadow_opacity.get(),
                        "feet_marker_enable_gradient": self.feet_marker_enable_gradient.get(),
                        "feet_marker_enable_pulse": self.feet_marker_enable_pulse.get(),
                        "feet_marker_pulse_speed": self.feet_marker_pulse_speed.get(),
                        "feet_marker_enable_particles": self.feet_marker_enable_particles.get(),
                        "feet_marker_particle_count": self.feet_marker_particle_count.get(),
                    }
                    
                    # Create renderer instance for preview
                    temp_renderer = OverlayRenderer(
                        temp_metadata, 
                        use_hd=True, 
                        render_scale=1.0, 
                        quality=self.overlay_quality.get(),
                        enable_advanced_blending=self.enable_advanced_blending.get(),
                        enable_motion_blur=self.enable_motion_blur.get(),
                        motion_blur_amount=self.motion_blur_amount.get(),
                        use_professional_text=self.use_professional_text.get()
                    )
                    
                    # Draw enhanced feet marker with all effects
                    temp_renderer._draw_enhanced_feet_marker(
                        preview_img, ellipse_center, axes, 
                        self.feet_marker_style.get(), team_color, self.feet_marker_opacity.get(),
                        self.feet_marker_enable_glow.get(), self.feet_marker_glow_intensity.get(),
                        self.feet_marker_enable_shadow.get(), self.feet_marker_shadow_offset.get(),
                        self.feet_marker_shadow_opacity.get(),
                        self.feet_marker_enable_gradient.get(), self.feet_marker_enable_pulse.get(),
                        self.feet_marker_pulse_speed.get(), 0,  # frame_num=0 for static preview
                        self.feet_marker_enable_particles.get(), self.feet_marker_particle_count.get(),
                        ellipse_outline
                    )
                except Exception as e:
                    # Fallback to basic rendering if enhanced rendering fails
                    import traceback
                    print(f"⚠ Preview: Enhanced feet marker rendering failed, using basic: {e}")
                    traceback.print_exc()
                    # Draw basic filled ellipse at feet
                    cv2.ellipse(preview_img, ellipse_center, axes, 0, 0, 360, team_color, -1)  # Filled
                    # Draw white outline with adjustable thickness
                    cv2.ellipse(preview_img, ellipse_center, axes, 0, 0, 360, (255, 255, 255), ellipse_outline)
            # Legacy support: if new controls not used, fall back to viz_style
            elif viz_style in ["circle", "both"]:
                # Draw circle at center
                radius = min(box_width, box_height) // 2
                cv2.circle(preview_img, (center_x, center_y), radius, color, box_thickness)
                # Also draw ellipse at feet for legacy support
                foot_y = y2
                ellipse_center = (center_x, int(foot_y))
                preview_ellipse_w = int(ellipse_w * 0.5)
                preview_ellipse_h = int(ellipse_h * 0.5)
                axes = (preview_ellipse_w // 2, preview_ellipse_h // 2)
                cv2.ellipse(preview_img, ellipse_center, axes, 0, 0, 360, color, -1)
                cv2.ellipse(preview_img, ellipse_center, axes, 0, 0, 360, (255, 255, 255), ellipse_outline)
            
            if viz_style == "star":
                # Draw 5-pointed star
                points = []
                outer_radius = min(box_width, box_height) // 2
                inner_radius = outer_radius // 2
                for i in range(10):
                    angle = i * np.pi / 5
                    if i % 2 == 0:
                        r = outer_radius
                    else:
                        r = inner_radius
                    px = int(center_x + r * np.cos(angle - np.pi / 2))
                    py = int(center_y + r * np.sin(angle - np.pi / 2))
                    points.append([px, py])
                pts = np.array(points, np.int32)
                cv2.fillPoly(preview_img, [pts], color)
                cv2.polylines(preview_img, [pts], True, (255, 255, 255), box_thickness)
            
            if viz_style == "diamond":
                # Draw diamond (rotated square)
                points = np.array([
                    [center_x, y1],  # Top
                    [x2, center_y],  # Right
                    [center_x, y2],  # Bottom
                    [x1, center_y]   # Left
                ], np.int32)
                cv2.fillPoly(preview_img, [points], color)
                cv2.polylines(preview_img, [points], True, (255, 255, 255), box_thickness)
            
            if viz_style == "hexagon":
                # Draw hexagon
                points = []
                radius = min(box_width, box_height) // 2
                for i in range(6):
                    angle = i * np.pi / 3
                    px = int(center_x + radius * np.cos(angle))
                    py = int(center_y + radius * np.sin(angle))
                    points.append([px, py])
                pts = np.array(points, np.int32)
                cv2.fillPoly(preview_img, [pts], color)
                cv2.polylines(preview_img, [pts], True, (255, 255, 255), box_thickness)
            
            if viz_style == "arrow":
                # Draw arrow pointing up
                arrow_size = min(box_width, box_height) // 2
                points = np.array([
                    [center_x, y1],  # Top point
                    [center_x - arrow_size // 2, y1 + arrow_size // 2],  # Left
                    [center_x - arrow_size // 4, y1 + arrow_size // 2],  # Left inner
                    [center_x - arrow_size // 4, y2],  # Bottom left
                    [center_x + arrow_size // 4, y2],  # Bottom right
                    [center_x + arrow_size // 4, y1 + arrow_size // 2],  # Right inner
                    [center_x + arrow_size // 2, y1 + arrow_size // 2]   # Right
                ], np.int32)
                cv2.fillPoly(preview_img, [points], color)
                cv2.polylines(preview_img, [points], True, (255, 255, 255), box_thickness)
            
            # Draw ball possession indicator if enabled
            if show_ball:
                triangle_size = 10
                triangle_points = np.array([
                    [center_x, y1 - triangle_size - 5],
                    [center_x - triangle_size, y1 - 5],
                    [center_x + triangle_size, y1 - 5]
                ], np.int32)
                cv2.fillPoly(preview_img, [triangle_points], (255, 0, 0))  # Blue
            
            # Draw label if enabled
            if show_labels:
                # Get label text based on selected type (use variable already retrieved)
                if label_type == "full_name":
                    label = "John Smith"
                elif label_type == "last_name":
                    label = "Smith"
                elif label_type == "jersey":
                    label = "#10"
                elif label_type == "team":
                    label = "Gray"
                else:  # custom
                    label = label_custom_text or "Player"
                
                font_scale = self._safe_get_double(self.label_font_scale, 0.7)
                thickness = max(1, int(font_scale))
                
                # Get font face (use variable already retrieved)
                font_face = getattr(cv2, label_font_face, cv2.FONT_HERSHEY_SIMPLEX)
                
                # Use custom label color if enabled, otherwise use team/box color
                if self.use_custom_label_color.get():
                    label_color = self._get_label_color()  # BGR format with error handling
                else:
                    label_color = color
                
                # Use professional text rendering if enabled
                if self.use_professional_text.get():
                    try:
                        from hd_overlay_renderer import HDOverlayRenderer
                        # Create temporary HD renderer for preview
                        hd_renderer = HDOverlayRenderer(
                            render_scale=1.0,
                            quality=self.overlay_quality.get(),
                            enable_advanced_blending=self.enable_advanced_blending.get()
                        )
                        # Use PIL-based professional text rendering
                        label_pos = (x2 + 5, center_y)
                        hd_renderer.draw_crisp_text_pil(
                            preview_img, label, label_pos, 
                            font_scale=font_scale * 0.4,
                            color=label_color,  # BGR format
                            thickness=thickness,
                            outline_color=(0, 0, 0),  # Black outline
                            outline_width=1
                        )
                    except Exception as e:
                        # Fallback to basic OpenCV text if professional rendering fails
                        cv2.putText(preview_img, label, (x2 + 5, center_y), 
                                   font_face, font_scale * 0.4, label_color, thickness)
                else:
                    # Use basic OpenCV text rendering
                    cv2.putText(preview_img, label, (x2 + 5, center_y), 
                               font_face, font_scale * 0.4, label_color, thickness)
            
            # Draw track ID decay preview (bottom area) if enabled
            if show_predicted:
                # Draw a trail of fading predicted markers
                decay_center_x = 200
                decay_start_y = 180
                
                # Draw 5 fading markers showing decay over time
                num_markers = 5
                for i in range(num_markers):
                    marker_x = decay_center_x - (i * 15)  # Spacing between markers
                    marker_y = decay_start_y
                    
                    # Calculate fade (more recent = brighter)
                    fade_factor = 1.0 - (i / num_markers) * 0.7  # Fade from 100% to 30%
                    # Apply both time-based fade and opacity setting
                    combined_alpha = fade_factor * (prediction_alpha / 255.0)
                    faded_color = tuple(int(c * combined_alpha) for c in base_prediction_color)
                    
                    # Draw based on selected style
                    if prediction_style == "dot":
                        cv2.circle(preview_img, (marker_x, marker_y), prediction_size, faded_color, -1)
                        cv2.circle(preview_img, (marker_x, marker_y), prediction_size, (255, 255, 255), 1)
                    elif prediction_style == "box":
                        half_size = prediction_size
                        cv2.rectangle(preview_img, (marker_x - half_size, marker_y - half_size),
                                    (marker_x + half_size, marker_y + half_size), faded_color, 2)
                    elif prediction_style == "cross":
                        half_size = prediction_size
                        cv2.line(preview_img, (marker_x - half_size, marker_y), (marker_x + half_size, marker_y), faded_color, 2)
                        cv2.line(preview_img, (marker_x, marker_y - half_size), (marker_x, marker_y + half_size), faded_color, 2)
                    elif prediction_style == "x":
                        half_size = int(prediction_size * 0.7)
                        cv2.line(preview_img, (marker_x - half_size, marker_y - half_size),
                                (marker_x + half_size, marker_y + half_size), faded_color, 2)
                        cv2.line(preview_img, (marker_x - half_size, marker_y + half_size),
                                (marker_x + half_size, marker_y - half_size), faded_color, 2)
                    elif prediction_style == "arrow":
                        # Draw arrow pointing up
                        arrow_size = prediction_size
                        points = np.array([
                            [marker_x, marker_y - arrow_size],  # Top point
                            [marker_x - arrow_size // 2, marker_y],  # Left
                            [marker_x + arrow_size // 2, marker_y]   # Right
                        ], np.int32)
                        cv2.fillPoly(preview_img, [points], faded_color)
                    elif prediction_style == "diamond":
                        half_size = prediction_size
                        points = np.array([
                            [marker_x, marker_y - half_size],  # Top
                            [marker_x + half_size, marker_y],   # Right
                            [marker_x, marker_y + half_size],   # Bottom
                            [marker_x - half_size, marker_y]    # Left
                        ], np.int32)
                        cv2.fillPoly(preview_img, [points], faded_color)
                        cv2.polylines(preview_img, [points], True, (255, 255, 255), 1)
                
                # Add label
                cv2.putText(preview_img, "Track Decay", (decay_center_x - 60, decay_start_y + 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            
            # Draw analytics banner preview (if analytics position is set to banner/panel)
            analytics_pos = self.analytics_position.get() if hasattr(self, 'analytics_position') else "with_player"
            if analytics_pos in ["top_banner", "bottom_banner", "top_left", "top_right", "bottom_left", "bottom_right"]:
                # Get analytics font settings
                analytics_font_scale = self.analytics_font_scale.get()
                analytics_font_thickness = self.analytics_font_thickness.get() if hasattr(self, 'analytics_font_thickness') else 2
                analytics_font_face_str = self.analytics_font_face.get() if hasattr(self, 'analytics_font_face') else "FONT_HERSHEY_SIMPLEX"
                analytics_font_face = getattr(cv2, analytics_font_face_str, cv2.FONT_HERSHEY_SIMPLEX)
                
                # Get analytics color (default to white for better contrast)
                if hasattr(self, 'use_custom_analytics_color') and self.use_custom_analytics_color.get():
                    try:
                        analytics_color = self._get_analytics_color_bgr()
                    except Exception:
                        analytics_color = (255, 255, 255)  # Default white fallback
                else:
                    analytics_color = (255, 255, 255)  # Default white for maximum contrast
                
                # Get title color
                try:
                    title_color = self._get_analytics_title_color_bgr()
                except Exception:
                    title_color = (0, 255, 255)  # Default yellow in BGR format
                
                # Draw analytics banner preview at top
                banner_height = 60
                overlay = preview_img.copy()
                cv2.rectangle(overlay, (0, 0), (400, banner_height), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.6, preview_img, 0.4, 0, preview_img)
                
                # Draw title with thickness
                title = "Player Analytics"
                title_font_scale = analytics_font_scale * 1.2
                title_thickness = max(2, analytics_font_thickness + 1)
                cv2.putText(preview_img, title, (10, 25),
                           analytics_font_face, title_font_scale, title_color, title_thickness)
                
                # Draw sample analytics text with thickness
                sample_lines = [
                    "--- Player #10 ---",
                    "Speed: 5.2 m/s",
                    "Distance: 45.3 m"
                ]
                text_y = 45
                line_height = int(18 * analytics_font_scale / 0.5)
                for line in sample_lines[:2]:  # Show 2 lines
                    # Draw outline first for better contrast
                    cv2.putText(preview_img, line, (20, text_y),
                               analytics_font_face, analytics_font_scale * 0.9, (0, 0, 0), analytics_font_thickness + 1)
                    # Draw main text
                    cv2.putText(preview_img, line, (20, text_y),
                               analytics_font_face, analytics_font_scale * 0.9, analytics_color, analytics_font_thickness)
                    text_y += line_height
            
            # Convert to RGB for display
            preview_img_rgb = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)
            
            # Convert to PhotoImage and display
            image = Image.fromarray(preview_img_rgb)
            photo = ImageTk.PhotoImage(image=image)
            
            # Clear canvas and display new image
            self.preview_canvas.delete("all")
            # Center the image in the canvas (canvas is 400x250, image is 400x250)
            self.preview_canvas.create_image(200, 125, image=photo, anchor=tk.CENTER)
            self.preview_image = photo  # Keep a reference - CRITICAL: prevents garbage collection
            self.preview_canvas.update_idletasks()  # Force canvas update
            
        except Exception as e:
            # Log error for debugging
            import traceback
            print(f"⚠ Preview update error: {e}")
            print(traceback.format_exc())
            # Try to show error message on canvas
            try:
                self.preview_canvas.delete("all")
                self.preview_canvas.create_text(200, 125, text=f"Preview Error:\n{str(e)}", 
                                               fill="red", font=("Arial", 10))
            except:
                pass
    
    def view_player_gallery(self):
        """View Player Gallery statistics and contents"""
        try:
            from player_gallery import PlayerGallery
            
            gallery = PlayerGallery()
            stats = gallery.get_stats()
            players = gallery.list_players()
            
            # Create info window
            info_window = tk.Toplevel(self.root)
            info_window.title("Player Gallery")
            info_window.geometry("600x500")
            info_window.transient(self.root)
            
            # Main frame
            main_frame = ttk.Frame(info_window, padding="15")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            ttk.Label(main_frame, text="Player Gallery", font=("Arial", 14, "bold")).pack(pady=(0, 10))
            
            # Statistics
            stats_frame = ttk.LabelFrame(main_frame, text="Statistics", padding="10")
            stats_frame.pack(fill=tk.X, pady=(0, 15))
            
            stats_text = f"""Total Players: {stats['total_players']}
Players with Features: {stats['players_with_features']}
Players with Reference Frames: {stats['players_with_reference_frames']}

Gallery File: {stats['gallery_path']}"""
            
            ttk.Label(stats_frame, text=stats_text, justify=tk.LEFT, font=("Courier", 9)).pack()
            
            # Player list
            list_frame = ttk.LabelFrame(main_frame, text="Players in Gallery", padding="10")
            list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            # Scrollable listbox
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Courier", 10))
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            
            if players:
                for player_id, player_name in players:
                    profile = gallery.get_player(player_id)
                    jersey = f" #{profile.jersey_number}" if profile.jersey_number else ""
                    team = f" [{profile.team}]" if profile.team else ""
                    has_features = "✓" if profile.features is not None else "✗"
                    has_viz = "🎨" if profile.visualization_settings else ""
                    listbox.insert(tk.END, f"{has_features} {has_viz} {player_name}{jersey}{team}")
            else:
                listbox.insert(tk.END, "(No players in gallery yet)")
                listbox.insert(tk.END, "")
                listbox.insert(tk.END, "Use 'Tag Players (Gallery)' to add players!")
            
            # Info text
            info_text = """✓ = Player has Re-ID features (can be recognized)
✗ = Player added without features
🎨 = Player has custom visualization settings

Double-click a player to view/edit details"""
            
            ttk.Label(main_frame, text=info_text, justify=tk.LEFT, foreground="gray", font=("Arial", 8)).pack()
            
            # Double-click handler to edit player
            def on_player_double_click(event):
                selection = listbox.curselection()
                if not selection:
                    return
                
                idx = selection[0]
                if idx >= len(players):
                    return
                
                player_id, player_name = players[idx]
                profile = gallery.get_player(player_id)
                
                # Open edit dialog
                edit_dialog = tk.Toplevel(info_window)
                edit_dialog.title(f"Edit Player: {player_name}")
                edit_dialog.geometry("500x600")
                edit_dialog.transient(info_window)
                edit_dialog.grab_set()
                
                edit_frame = ttk.Frame(edit_dialog, padding="20")
                edit_frame.pack(fill=tk.BOTH, expand=True)
                
                ttk.Label(edit_frame, text=f"Edit: {player_name}", font=("Arial", 14, "bold")).pack(pady=(0, 20))
                
                # Basic info
                basic_frame = ttk.LabelFrame(edit_frame, text="Basic Information", padding="10")
                basic_frame.pack(fill=tk.X, pady=5)
                
                ttk.Label(basic_frame, text="Jersey Number:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
                jersey_var = tk.StringVar(value=profile.jersey_number or "")
                ttk.Entry(basic_frame, textvariable=jersey_var, width=20).grid(row=0, column=1, padx=5, pady=5)
                
                ttk.Label(basic_frame, text="Team:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
                team_var = tk.StringVar(value=profile.team or "")
                ttk.Entry(basic_frame, textvariable=team_var, width=20).grid(row=1, column=1, padx=5, pady=5)
                
                # Visualization settings
                viz_frame = ttk.LabelFrame(edit_frame, text="Visualization Settings", padding="10")
                viz_frame.pack(fill=tk.X, pady=5)
                
                # Load existing settings
                viz = profile.visualization_settings or {}
                
                # Custom color
                ttk.Label(viz_frame, text="Custom Color (R,G,B):").grid(row=0, column=0, sticky=tk.W, padx=5)
                custom_color_var = tk.StringVar()
                if viz.get("custom_color_rgb"):
                    rgb = viz["custom_color_rgb"]
                    custom_color_var.set(f"{rgb[0]},{rgb[1]},{rgb[2]}")
                ttk.Entry(viz_frame, textvariable=custom_color_var, width=15).grid(row=0, column=1, padx=5, sticky=tk.W)
                ttk.Label(viz_frame, text="(e.g., 255,0,0 for red)", font=("Arial", 7), foreground="gray").grid(row=0, column=2, sticky=tk.W)
                
                # Box thickness
                ttk.Label(viz_frame, text="Box Thickness:").grid(row=1, column=0, sticky=tk.W, padx=5)
                box_thickness_var = tk.IntVar(value=viz.get("box_thickness", 2))
                ttk.Spinbox(viz_frame, from_=1, to=10, textvariable=box_thickness_var, width=10).grid(row=1, column=1, padx=5, sticky=tk.W)
                
                # Show glow
                show_glow_var = tk.BooleanVar(value=viz.get("show_glow", False))
                ttk.Checkbutton(viz_frame, text="Show Glow Effect", variable=show_glow_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5)
                
                # Glow intensity
                ttk.Label(viz_frame, text="Glow Intensity:").grid(row=3, column=0, sticky=tk.W, padx=5)
                glow_intensity_var = tk.IntVar(value=viz.get("glow_intensity", 50))
                ttk.Spinbox(viz_frame, from_=0, to=100, textvariable=glow_intensity_var, width=10).grid(row=3, column=1, padx=5, sticky=tk.W)
                
                # Show trail
                show_trail_var = tk.BooleanVar(value=viz.get("show_trail", False))
                ttk.Checkbutton(viz_frame, text="Show Movement Trail", variable=show_trail_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5)
                
                # Label style
                ttk.Label(viz_frame, text="Label Style:").grid(row=5, column=0, sticky=tk.W, padx=5)
                label_style_var = tk.StringVar(value=viz.get("label_style", "full_name"))
                ttk.Combobox(viz_frame, textvariable=label_style_var, 
                            values=["full_name", "jersey", "initials", "number"], 
                            width=12, state="readonly").grid(row=5, column=1, padx=5, sticky=tk.W)
                
                def save_changes():
                    # Parse visualization settings
                    viz_settings = {}
                    custom_color_str = custom_color_var.get().strip()
                    if custom_color_str:
                        try:
                            from team_roster_manager import TeamRosterManager
                            roster_manager_temp = TeamRosterManager()
                            rgb = roster_manager_temp._parse_color_string(custom_color_str)
                            if rgb:
                                viz_settings["use_custom_color"] = True
                                viz_settings["custom_color_rgb"] = rgb
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
                    
                    # Update player
                    gallery.update_player(
                        player_id=player_id,
                        jersey_number=jersey_var.get().strip() or None,
                        team=team_var.get().strip() or None,
                        visualization_settings=viz_settings if viz_settings else None
                    )
                    gallery.save_gallery()
                    
                    messagebox.showinfo("Success", f"Updated player: {player_name}")
                    edit_dialog.destroy()
                    
                    # Refresh list
                    listbox.delete(0, tk.END)
                    for pid, pname in players:
                        prof = gallery.get_player(pid)
                        jersey = f" #{prof.jersey_number}" if prof.jersey_number else ""
                        team = f" [{prof.team}]" if prof.team else ""
                        has_features = "✓" if prof.features is not None else "✗"
                        has_viz = "🎨" if prof.visualization_settings else ""
                        listbox.insert(tk.END, f"{has_features} {has_viz} {pname}{jersey}{team}")
                
                button_frame = ttk.Frame(edit_frame)
                button_frame.pack(fill=tk.X, pady=(20, 0))
                
                ttk.Button(button_frame, text="Save", command=save_changes).pack(side=tk.RIGHT, padx=5)
                ttk.Button(button_frame, text="Cancel", command=edit_dialog.destroy).pack(side=tk.RIGHT, padx=5)
            
            listbox.bind('<Double-Button-1>', on_player_double_click)
            
            # Close button
            ttk.Button(main_frame, text="Close", command=info_window.destroy).pack(pady=(10, 0))
            
            info_window.lift()
            info_window.focus_force()
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import player_gallery.py: {str(e)}\n\n"
                               "Make sure player_gallery.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not view Player Gallery: {str(e)}")
    
    def open_in_playback_viewer(self, video_path):
        """Open specific video file in playback viewer"""
        try:
            from playback_viewer import PlaybackViewer
            
            if not os.path.exists(video_path):
                messagebox.showerror("Error", f"Video file not found: {video_path}")
                return
            
            viewer_window = tk.Toplevel(self.root)
            viewer_window.title(f"Playback Viewer - {os.path.basename(video_path)}")
            viewer_window.geometry("1200x800")
            viewer_window.transient(self.root)
            
            # Ensure window opens on top
            viewer_window.lift()
            viewer_window.attributes('-topmost', True)
            viewer_window.focus_force()
            viewer_window.after(200, lambda: viewer_window.attributes('-topmost', False))
            
            app = PlaybackViewer(viewer_window)
            
            # Load the specified video
            app.video_path = video_path
            viewer_window.after(100, lambda: app.load_video())
            
            # DON'T auto-load CSV - let user manually select which CSV they want
            # (They might want to load the preview CSV instead of the original CSV)
            # User can click "Load CSV" button to select the file they want
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import playback_viewer.py: {str(e)}\n\n"
                               "Make sure playback_viewer.py is in the same folder.")
            import traceback
            traceback.print_exc()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open playback viewer: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def open_playback_viewer(self):
        """Open playback viewer with toggleable overlays"""
        try:
            from playback_viewer import PlaybackViewer
            
            viewer_window = tk.Toplevel(self.root)
            viewer_window.title("Playback Viewer")
            viewer_window.geometry("1200x800")
            # Don't set transient - allows window to be minimized and managed independently
            # viewer_window.transient(self.root)  # Removed to allow minimize functionality
            
            # Ensure window opens properly without requiring main window to be minimized
            viewer_window.lift()
            viewer_window.focus_force()
            viewer_window.grab_set()  # Make it modal temporarily
            viewer_window.after(100, lambda: viewer_window.grab_release())  # Release after a moment
            
            # Collect visualization settings from main GUI
            viz_settings = {
                # Style settings
                'viz_style': self.viz_style.get(),
                'viz_color_mode': self.viz_color_mode.get(),
                'advanced_viz_style': getattr(self, 'advanced_viz_style', tk.StringVar(value="none")).get() if hasattr(self, 'advanced_viz_style') else "none",
                # Show/hide settings
                'show_bounding_boxes': self.show_bounding_boxes.get(),
                'show_circles_at_feet': self.show_circles_at_feet.get(),
                'show_player_labels': self.show_player_labels.get(),
                'show_yolo_boxes': self.show_yolo_boxes.get(),
                'show_predicted_boxes': self.show_predicted_boxes.get(),
                'show_ball_possession': self.show_ball_possession.get(),
                # Feet marker settings
                'feet_marker_style': self.feet_marker_style.get(),
                'feet_marker_opacity': self.feet_marker_opacity.get(),
                'feet_marker_enable_glow': self.feet_marker_enable_glow.get(),
                'feet_marker_glow_intensity': self.feet_marker_glow_intensity.get(),
                'feet_marker_enable_shadow': self.feet_marker_enable_shadow.get(),
                'feet_marker_shadow_offset': self.feet_marker_shadow_offset.get(),
                'feet_marker_shadow_opacity': self.feet_marker_shadow_opacity.get(),
                'feet_marker_enable_gradient': self.feet_marker_enable_gradient.get(),
                'feet_marker_enable_pulse': self.feet_marker_enable_pulse.get(),
                'feet_marker_pulse_speed': self.feet_marker_pulse_speed.get(),
                'feet_marker_enable_particles': self.feet_marker_enable_particles.get(),
                'feet_marker_particle_count': self.feet_marker_particle_count.get(),
                'feet_marker_vertical_offset': self.feet_marker_vertical_offset.get(),
                # Box settings
                'box_shrink_factor': self.box_shrink_factor.get(),
                'box_thickness': self.box_thickness.get(),
                'use_custom_box_color': self.use_custom_box_color.get(),
                'box_color_rgb': self.box_color_rgb.get(),  # Store as RGB string for compatibility
                'box_color_r': self._get_box_color_r(),  # Extract R component for playback viewer compatibility
                'box_color_g': self._get_box_color_g(),  # Extract G component for playback viewer compatibility
                'box_color_b': self._get_box_color_b(),  # Extract B component for playback viewer compatibility
                'player_viz_alpha': self.player_viz_alpha.get(),
                # Label settings
                'use_custom_label_color': self.use_custom_label_color.get(),
                'label_color_rgb': self.label_color_rgb.get(),
                'label_font_scale': self.label_font_scale.get(),
                'label_type': self.label_type.get(),
                'label_custom_text': self.label_custom_text.get(),
                'label_font_face': self.label_font_face.get(),
                # Prediction settings
                'prediction_duration': self.prediction_duration.get(),
                'prediction_size': self.prediction_size.get(),
                'prediction_color_r': self.prediction_color_r.get(),
                'prediction_color_g': self.prediction_color_g.get(),
                'prediction_color_b': self.prediction_color_b.get(),
                'prediction_color_alpha': self.prediction_color_alpha.get(),
                'prediction_style': self.prediction_style.get(),
                # Analytics position
                'analytics_position': self.analytics_position.get(),
            }
            
            app = PlaybackViewer(viewer_window, viz_settings=viz_settings)
            # Store reference to main GUI in viewer window for project saving
            viewer_window.main_gui = self
            
            # Try to auto-load video and CSV if available
            # CRITICAL FIX: Use after() to ensure widgets are fully created before loading video
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
                if os.path.exists(video_path):
                    app.video_path = video_path
                    # Schedule load_video to run after widgets are fully initialized (100ms delay)
                    # CRITICAL: Pass video_path to load_video() to avoid file dialog
                    def load_video_delayed():
                        try:
                            app.load_video(video_path)  # Pass video_path parameter
                        except Exception as e:
                            print(f"⚠ Warning: Could not auto-load video: {e}")
                            import traceback
                            traceback.print_exc()
                    viewer_window.after(100, load_video_delayed)
                    
                    # Try to find corresponding CSV - check multiple possible names
                    base_name = os.path.splitext(video_path)[0]
                    possible_csv_names = [
                        f"{base_name}_tracking_data.csv",
                        f"{base_name}.csv",
                        os.path.join(os.path.dirname(video_path), os.path.basename(base_name) + "_tracking_data.csv"),
                        os.path.join(os.path.dirname(video_path), os.path.basename(base_name) + ".csv"),
                    ]
                    
                    csv_path = None
                    for possible_csv in possible_csv_names:
                        if os.path.exists(possible_csv):
                            csv_path = possible_csv
                            break
                    
                    if csv_path:
                        app.csv_path = csv_path
                        # Schedule load_csv after load_video completes (500ms delay to ensure video loads first)
                        # CRITICAL: Pass csv_path to load_csv() to avoid file dialog
                        def load_csv_delayed():
                            try:
                                app.load_csv(csv_path)  # Pass csv_path parameter
                            except Exception as e:
                                print(f"⚠ Warning: Could not auto-load CSV: {e}")
                                import traceback
                                traceback.print_exc()
                        viewer_window.after(500, load_csv_delayed)
                    else:
                        # Log that CSV was not found (but don't show error - it's optional)
                        print(f"ℹ Info: No matching CSV found for video: {video_path}")
                        print(f"   Checked: {possible_csv_names[:2]}...")
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import playback_viewer.py: {str(e)}\n\n"
                               "Make sure playback_viewer.py is in the same folder.")
            import traceback
            traceback.print_exc()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open playback viewer: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def open_setup_wizard(self):
        """Open interactive setup wizard for player tagging"""
        try:
            from setup_wizard import SetupWizard
            
            wizard_window = tk.Toplevel(self.root)
            wizard_window.title("Setup Wizard")
            wizard_window.geometry("1600x1050")
            wizard_window.transient(self.root)
            
            # Ensure window opens on top
            wizard_window.lift()
            wizard_window.attributes('-topmost', True)
            wizard_window.focus_force()
            wizard_window.after(200, lambda: wizard_window.attributes('-topmost', False))
            
            # Get video path if available
            video_path = None
            if hasattr(self, 'input_file') and self.input_file.get():
                video_path = self.input_file.get()
                if not os.path.exists(video_path):
                    video_path = None
            
            # Pass video path to setup wizard for auto-loading
            app = SetupWizard(wizard_window, video_path=video_path)
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import setup_wizard.py: {str(e)}\n\n"
                               "Make sure setup_wizard.py is in the same folder.")
            import traceback
            traceback.print_exc()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open setup wizard: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_new_project(self):
        """Create a new project (reset project name)"""
        project_name = simpledialog.askstring(
            "Create New Project",
            "Enter project name:",
            initialvalue="New Project"
        )
        
        if project_name:
            self.current_project_name.set(project_name)
            self.current_project_path = None  # Clear project path for new project
            messagebox.showinfo("New Project Created", 
                              f"Project '{project_name}' created.\n\n"
                              "Configure your settings and use 'Save Project' to save.")
    
    def save_project(self):
        """Save current project configuration (to existing file if available)"""
        try:
            from project_manager import save_project
            
            # Use current project name if set, otherwise prompt
            project_name = self.current_project_name.get()
            if project_name == "No Project" or not project_name:
                # Get project name from input file or prompt
                project_name = "Untitled Project"
                if self.input_file.get():
                    # Use video filename as project name
                    video_name = os.path.splitext(os.path.basename(self.input_file.get()))[0]
                    project_name = video_name
                
                project_name = simpledialog.askstring(
                    "Save Project",
                    "Enter project name:",
                    initialvalue=project_name
                )
            
            if project_name:
                # If we have a current project path, save to that location
                # Otherwise, prompt for location (same as Save As)
                project_path = self.current_project_path if self.current_project_path else None
                
                result = save_project(project_name, project_path=project_path, gui_instance=self)
                if result:
                    project_path, saved_items = result
                    # Update current project path
                    self.current_project_path = project_path
                    # Update current project name display
                    self.current_project_name.set(project_name)
                    
                    # Add to recent projects
                    if QUICK_WINS_AVAILABLE and self.recent_projects:
                        self.recent_projects.add_project(project_path, project_name)
                        if hasattr(self, 'recent_menu'):
                            self._update_recent_projects_menu(self.recent_menu)
                    
                    # Build summary message
                    saved_list = []
                    if saved_items.get("analysis_settings"):
                        saved_list.append("• Analysis settings")
                    if saved_items.get("setup_wizard"):
                        saved_list.append("• Setup wizard data")
                    else:
                        saved_list.append("• Setup wizard data: Not found (use Setup Wizard to create)")
                    if saved_items.get("team_colors"):
                        saved_list.append("• Team colors")
                    if saved_items.get("ball_colors"):
                        saved_list.append("• Ball colors")
                    if saved_items.get("field_calibration"):
                        saved_list.append("• Field calibration")
                    if saved_items.get("player_names"):
                        saved_list.append(f"• Player names ({saved_items.get('player_count', 0)} players)")
                    if saved_items.get("analytics_preferences"):
                        saved_list.append("• Analytics preferences")
                    
                    summary_text = f"Project '{project_name}' saved successfully!\n\n"
                    summary_text += f"Saved to: {project_path}\n\n"
                    summary_text += "Saved configurations:\n"
                    summary_text += "\n".join(saved_list)
                    
                    messagebox.showinfo("Project Saved", summary_text)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save project: {e}")
            import traceback
            traceback.print_exc()
    
    def save_project_as(self):
        """Save project with a new name or location"""
        try:
            from project_manager import save_project
            
            # Always prompt for project name and location
            project_name = self.current_project_name.get()
            if project_name == "No Project" or not project_name:
                project_name = "Untitled Project"
                if self.input_file.get():
                    video_name = os.path.splitext(os.path.basename(self.input_file.get()))[0]
                    project_name = video_name
            
            project_name = simpledialog.askstring(
                "Save Project As",
                "Enter project name:",
                initialvalue=project_name
            )
            
            if project_name:
                # Always prompt for location (pass None to force file dialog)
                result = save_project(project_name, project_path=None, gui_instance=self)
                if result:
                    project_path, saved_items = result
                    # Update current project path and name
                    self.current_project_path = project_path
                    self.current_project_name.set(project_name)
                    
                    # Add to recent projects
                    if QUICK_WINS_AVAILABLE and self.recent_projects:
                        self.recent_projects.add_project(project_path, project_name)
                        if hasattr(self, 'recent_menu'):
                            self._update_recent_projects_menu(self.recent_menu)
                    
                    # Build summary message
                    saved_list = []
                    if saved_items.get("analysis_settings"):
                        saved_list.append("• Analysis settings")
                    if saved_items.get("setup_wizard"):
                        saved_list.append("• Setup wizard data")
                    else:
                        saved_list.append("• Setup wizard data: Not found (use Setup Wizard to create)")
                    if saved_items.get("team_colors"):
                        saved_list.append("• Team colors")
                    if saved_items.get("ball_colors"):
                        saved_list.append("• Ball colors")
                    if saved_items.get("field_calibration"):
                        saved_list.append("• Field calibration")
                    if saved_items.get("player_names"):
                        saved_list.append(f"• Player names ({saved_items.get('player_count', 0)} players)")
                    if saved_items.get("analytics_preferences"):
                        saved_list.append("• Analytics preferences")
                    
                    summary_text = f"Project '{project_name}' saved successfully!\n\n"
                    summary_text += f"Saved to: {project_path}\n\n"
                    summary_text += "Saved configurations:\n"
                    summary_text += "\n".join(saved_list)
                    
                    messagebox.showinfo("Project Saved", summary_text)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save project: {e}")
            import traceback
            traceback.print_exc()
    
    def rename_project(self):
        """Rename the current project"""
        try:
            current_name = self.current_project_name.get()
            if current_name == "No Project" or not current_name:
                messagebox.showwarning("No Project", "No project is currently loaded. Please create or load a project first.")
                return
            
            new_name = simpledialog.askstring(
                "Rename Project",
                "Enter new project name:",
                initialvalue=current_name
            )
            
            if new_name and new_name != current_name:
                # Update project name
                self.current_project_name.set(new_name)
                
                # If project is saved, offer to save with new name
                if self.current_project_path:
                    response = messagebox.askyesno(
                        "Save Renamed Project?",
                        f"Project renamed to '{new_name}'.\n\n"
                        "Would you like to save the project with the new name?\n\n"
                        "(This will create a new file - the old file will remain unchanged.)"
                    )
                    if response:
                        # Save with new name (will prompt for location)
                        self.save_project_as()
                else:
                    messagebox.showinfo(
                        "Project Renamed",
                        f"Project renamed to '{new_name}'.\n\n"
                        "Use 'Save Project' or 'Save Project As' to save with the new name."
                    )
        except Exception as e:
            messagebox.showerror("Error", f"Could not rename project: {e}")
            import traceback
            traceback.print_exc()
    
    def load_project(self):
        """Load project configuration"""
        try:
            from project_manager import load_project, get_project_summary
            
            # First, show project summary
            from tkinter import filedialog
            project_path = filedialog.askopenfilename(
                title="Load Project",
                filetypes=[("Project files", "*.json"), ("All files", "*.*")]
            )
            
            if not project_path:
                return
            
            # Get project summary
            summary = get_project_summary(project_path)
            if summary:
                summary_text = (
                    f"Project: {summary['project_name']}\n\n"
                    f"Contains:\n"
                    f"• Analysis settings: {'Yes' if summary['has_analysis_settings'] else 'No'}\n"
                    f"• Setup wizard data: {'Yes' if summary['has_setup_wizard'] else 'No'}\n"
                    f"• Team colors: {'Yes' if summary['has_team_colors'] else 'No'}\n"
                    f"• Ball colors: {'Yes' if summary['has_ball_colors'] else 'No'}\n"
                    f"• Field calibration: {'Yes' if summary['has_field_calibration'] else 'No'}\n"
                    f"• Player names: {'Yes' if summary['has_player_names'] else 'No'}\n"
                    f"  ({summary['player_count']} players)\n\n"
                    f"Loading will replace all current settings.\n\n"
                    f"Continue?"
                )
            else:
                summary_text = (
                    "Loading this project will replace all current settings.\n\n"
                    "This includes:\n"
                    "• Analysis settings\n"
                    "• Setup wizard data\n"
                    "• Team colors\n"
                    "• Ball colors\n"
                    "• Field calibration\n"
                    "• Player names\n\n"
                    "Continue?"
                )
            
            response = messagebox.askyesno("Load Project", summary_text)
            
            if response:
                project_data = load_project(project_path=project_path, gui_instance=self, restore_files=True)
                if project_data:
                    project_name = project_data.get("project_name", "Unknown")
                    # Update current project name and path
                    self.current_project_name.set(project_name)
                    self.current_project_path = project_path  # Track the loaded project path
                    
                    # Add to recent projects
                    if QUICK_WINS_AVAILABLE and self.recent_projects:
                        self.recent_projects.add_project(project_path, project_name)
                        if hasattr(self, 'recent_menu'):
                            self._update_recent_projects_menu(self.recent_menu)
                    
                    # Check if video file path needs updating
                    video_path = project_data.get("analysis_settings", {}).get("input_file", "")
                    video_note = ""
                    if video_path and not os.path.exists(video_path):
                        video_note = (
                            f"\n\n⚠ Note: Video file path in project:\n"
                            f"{video_path}\n"
                            f"File not found. Please update the video path in the main GUI."
                        )
                    
                    messagebox.showinfo(
                        "Project Loaded",
                        f"Project '{project_name}' loaded successfully!\n\n"
                        "All configurations have been restored.\n"
                        "You can now:\n"
                        "• Start analysis with these settings\n"
                        "• Use the Setup Wizard with loaded data\n"
                        "• Use team/ball color helpers with loaded colors"
                        + video_note
                    )
                    
                    # Check if output files exist and enable buttons
                    self._check_and_enable_output_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Could not load project: {e}")
            import traceback
            traceback.print_exc()
    
    def auto_load_last_project(self):
        """Auto-load the last saved/loaded project on startup"""
        try:
            from project_manager import get_last_project_path, load_project, get_project_summary
            
            last_project_path = get_last_project_path()
            if not last_project_path:
                return  # No last project to load
            
            # Get project summary
            summary = get_project_summary(last_project_path)
            if not summary:
                return
            
            project_name = summary.get("project_name", "Unknown")
            
            # Ask user if they want to load the last project
            summary_text = (
                f"Load last project '{project_name}'?\n\n"
                f"This project contains:\n"
                f"• Analysis settings: {'Yes' if summary['has_analysis_settings'] else 'No'}\n"
                f"• Setup wizard data: {'Yes' if summary['has_setup_wizard'] else 'No'}\n"
                f"• Team colors: {'Yes' if summary['has_team_colors'] else 'No'}\n"
                f"• Ball colors: {'Yes' if summary['has_ball_colors'] else 'No'}\n"
                f"• Field calibration: {'Yes' if summary['has_field_calibration'] else 'No'}\n"
                f"• Player names: {'Yes' if summary['has_player_names'] else 'No'}\n"
                f"  ({summary['player_count']} players)\n\n"
                f"Loading will restore all saved settings.\n\n"
                f"Load now?"
            )
            
            response = messagebox.askyesno("Auto-Load Last Project", summary_text)
            
            if response:
                project_data = load_project(project_path=last_project_path, gui_instance=self, restore_files=True)
                if project_data:
                    # Update current project name display
                    self.current_project_name.set(project_name)
                    # Show brief confirmation
                    self.log_message(f"✓ Auto-loaded project: {project_name}")
                    
                    # Check if video file path needs updating
                    video_path = project_data.get("analysis_settings", {}).get("input_file", "")
                    if video_path and not os.path.exists(video_path):
                        self.log_message(f"⚠ Video file not found: {video_path}")
                        self.log_message("  Please update the video path in the main GUI.")
        except Exception as e:
            # Silently fail for auto-load (don't interrupt startup)
            print(f"Could not auto-load last project: {e}")
    
    def _update_focus_players_ui(self):
        """Update focus players UI visibility"""
        if self.watch_only.get() and self.focus_players_enabled.get():
            self.focus_players_frame.grid()
            # Auto-load players when UI becomes visible
            if not self.focus_player_combo['values']:
                self._load_active_players_for_focus()
        else:
            self.focus_players_frame.grid_remove()
            self.focused_player = None
    
    def _update_batch_focus_ui(self):
        """Update batch focus UI - disable single player focus if batch is enabled"""
        if self.batch_focus_analyze.get():
            # Disable single player focus when batch is enabled
            self.focus_players_enabled.set(False)
            self._update_focus_players_ui()
            # Ensure watch-only is enabled for batch processing
            if not self.watch_only.get():
                self.watch_only.set(True)
                messagebox.showinfo("Watch-Only Mode Enabled", 
                                   "Watch-only mode has been enabled for batch processing.\n\n"
                                   "Batch processing runs in watch-only mode to learn from each player.")
    
    def _load_active_players_for_focus(self):
        """Load active players from roster and gallery into focus dropdown"""
        try:
            player_names = []
            
            # First, try to load from video-specific PlayerTagsSeed file (preferred)
            video_path = self.input_file.get()
            if video_path and os.path.exists(video_path):
                try:
                    import json
                    video_dir = os.path.dirname(os.path.abspath(video_path))
                    video_basename = os.path.splitext(os.path.basename(video_path))[0]
                    seed_file = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
                    
                    if os.path.exists(seed_file):
                        with open(seed_file, 'r') as f:
                            config = json.load(f)
                            player_roster = config.get("player_roster", {})
                            
                            if player_roster:
                                # Get active players from video-specific roster
                                for player_name, player_data in player_roster.items():
                                    if isinstance(player_data, dict) and player_data.get('active', True):
                                        if player_name not in player_names:
                                            player_names.append(player_name)
                except Exception as e:
                    print(f"⚠ Could not load from video-specific seed file: {e}")
            
            # Also try to load from global seed_config.json
            try:
                from combined_analysis_optimized import load_seed_config
                _, _, player_roster = load_seed_config()
                
                if player_roster:
                    # Get active players from seed config roster
                    for player_name, player_data in player_roster.items():
                        if isinstance(player_data, dict) and player_data.get('active', True):
                            if player_name not in player_names:
                                player_names.append(player_name)
            except Exception as e:
                print(f"⚠ Could not load from seed_config.json: {e}")
            
            # Also load from global roster manager
            try:
                from team_roster_manager import TeamRosterManager
                roster_manager = TeamRosterManager()
                roster = roster_manager.roster
                
                for player_name, player_data in roster.items():
                    if player_name == 'videos':
                        continue
                    if isinstance(player_data, dict) and player_data.get('active', True):
                        if player_name not in player_names:
                            player_names.append(player_name)
            except Exception as e:
                print(f"⚠ Could not load from global roster: {e}")
            
            # Fallback: load from player gallery if no roster available
            if not player_names:
                try:
                    from player_gallery import PlayerGallery
                    gallery = PlayerGallery()
                    players = gallery.list_players()
                    gallery_names = [player_name for _, player_name in players]
                    # Add all gallery players (assume active if no roster info)
                    for name in gallery_names:
                        if name not in player_names:
                            player_names.append(name)
                except Exception as e:
                    print(f"⚠ Could not load from player gallery: {e}")
            
            # Sort and update dropdown
            player_names.sort()
            self.focus_player_combo['values'] = tuple(['(All Players)'] + player_names)
            
            # Log how many players were loaded
            print(f"✓ Loaded {len(player_names)} active player(s) for focus dropdown")
            if player_names:
                print(f"   → Players: {', '.join(player_names[:10])}{'...' if len(player_names) > 10 else ''}")
            
            # Preserve current selection if it's still valid
            current = self.focused_player_var.get()
            if current and current in player_names:
                self.focused_player_var.set(current)
            else:
                self.focused_player_var.set('(All Players)')
                self.focused_player = None
                
        except Exception as e:
            messagebox.showerror("Error", f"Could not load players: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _update_focused_player(self):
        """Update focused_player from dropdown selection"""
        try:
            selected = self.focused_player_var.get()
            if selected and selected != '(All Players)':
                self.focused_player = selected
            else:
                self.focused_player = None
        except tk.TclError:
            self.focused_player = None
    
    def _get_active_players_for_video(self, video_path):
        """
        Get list of active players from roster for the specified video.
        
        Args:
            video_path: Path to the video file
        
        Returns:
            List of active player names
        """
        active_players = []
        
        # Try to load from seed config (video-specific)
        try:
            # Look for PlayerTagsSeed file in video directory
            import os
            video_dir = os.path.dirname(os.path.abspath(video_path))
            video_basename = os.path.splitext(os.path.basename(video_path))[0]
            seed_file = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
            
            if os.path.exists(seed_file):
                import json
                with open(seed_file, 'r') as f:
                    config = json.load(f)
                    player_roster = config.get("player_roster", {})
                    
                    for player_name, player_data in player_roster.items():
                        if isinstance(player_data, dict) and player_data.get('active', True):
                            active_players.append(player_name)
        except Exception as e:
            print(f"⚠ Could not load video-specific roster: {e}")
        
        # Also check global seed config
        if not active_players:
            try:
                from combined_analysis_optimized import load_seed_config
                _, _, player_roster = load_seed_config()
                
                if player_roster:
                    for player_name, player_data in player_roster.items():
                        if isinstance(player_data, dict) and player_data.get('active', True):
                            if player_name not in active_players:
                                active_players.append(player_name)
            except Exception:
                pass
        
        # Fallback: load from global roster manager
        if not active_players:
            try:
                from team_roster_manager import TeamRosterManager
                roster_manager = TeamRosterManager()
                roster = roster_manager.roster
                
                for player_name, player_data in roster.items():
                    if player_name == 'videos':
                        continue
                    if isinstance(player_data, dict) and player_data.get('active', True):
                        if player_name not in active_players:
                            active_players.append(player_name)
            except Exception:
                pass
        
        return sorted(active_players)
    
    def _run_batch_focus_analysis(self, video_path, active_players):
        """
        Run analysis for each active player in batch mode.
        
        Args:
            video_path: Path to the video file
            active_players: List of active player names
        """
        total_players = len(active_players)
        
        # Set up UI for batch processing
        self.root.after(0, lambda: self.start_button.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.stop_button.config(state=tk.NORMAL))
        self.root.after(0, lambda: setattr(self, 'processing', True))
        self.root.after(0, lambda: self.progress_var.set(0))
        
        # Clear log
        self.root.after(0, lambda: self.log_text.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.log_text.delete(1.0, tk.END))
        self.root.after(0, lambda: self.log_text.config(state=tk.DISABLED))
        
        try:
            # Load analysis module
            from soccer_analysis_gui import load_analysis_module, OPTIMIZED_AVAILABLE
            if not load_analysis_module():
                self.root.after(0, self.analysis_complete, False, "Failed to load analysis module")
                return
            
            for idx, player_name in enumerate(active_players, 1):
                # Update status
                status_msg = f"Batch Processing: Player {idx}/{total_players} - {player_name}"
                self.root.after(0, lambda msg=status_msg: self.status_label.config(text=msg))
                progress_pct = int((idx - 1) / total_players * 100)
                self.root.after(0, lambda p=progress_pct: self.progress_var.set(p))
                self.log_message("=" * 60)
                self.log_message(f"🎯 BATCH PROCESSING: Player {idx}/{total_players} - {player_name}")
                self.log_message("=" * 60)
                
                # Check if analysis was stopped
                try:
                    import shared_state
                    if shared_state.is_analysis_stop_requested():
                        self.log_message("Batch processing stopped by user")
                        self.root.after(0, self.analysis_complete, False, "Batch processing stopped")
                        return
                except ImportError:
                    pass
                
                # Run analysis for this player (in watch-only mode)
                try:
                    from combined_analysis_optimized import combined_analysis
                    
                    self.log_message(f"📹 Starting analysis for {player_name}...")
                    self.log_message(f"   → Video: {os.path.basename(video_path)}")
                    self.log_message(f"   → Focus mode: {player_name} only")
                    self.log_message(f"   → Watch-only: True (learning mode)")
                    
                    # Run analysis with this player focused - copy all parameters from run_analysis
                    result = combined_analysis(
                        input_path=video_path,
                        output_path=None,  # Watch-only mode - no output
                        dewarp=self.dewarp_enabled.get(),
                        track_ball_flag=self.ball_tracking_enabled.get(),
                        track_players_flag=self.player_tracking_enabled.get(),
                        export_csv=False,  # No CSV in batch mode
                        use_imperial_units=self.use_imperial_units.get(),
                        buffer=self.buffer_size.get(),
                        batch_size=self.batch_size.get(),
                        ball_min_radius=self.ball_min_radius.get(),
                        ball_max_radius=self.ball_max_radius.get(),
                        show_live_viewer=False,  # Disable live viewer for batch
                        remove_net=self.remove_net_enabled.get(),
                        show_ball_trail=self.show_ball_trail.get(),
                        track_thresh=self.track_thresh.get(),
                        match_thresh=self.match_thresh.get(),
                        track_buffer=self.track_buffer.get(),
                        track_buffer_seconds=self.track_buffer_seconds.get(),
                        min_track_length=self.min_track_length.get(),
                        tracker_type=self.tracker_type.get(),
                        video_fps=self.video_fps.get() if self.video_fps.get() > 0 else None,
                        output_fps=self.output_fps.get() if self.output_fps.get() > 0 else None,
                        temporal_smoothing=self.temporal_smoothing.get(),
                        process_every_nth_frame=self.process_every_nth.get(),
                        yolo_resolution=self.yolo_resolution.get(),
                        foot_based_tracking=self.foot_based_tracking.get(),
                        use_reid=self.use_reid.get(),
                        reid_similarity_threshold=self.reid_similarity_threshold.get(),
                        gallery_similarity_threshold=self.gallery_similarity_threshold.get(),
                        osnet_variant=self.osnet_variant.get(),
                        use_boxmot_backend=self.use_boxmot_backend.get(),
                        occlusion_recovery_seconds=self.occlusion_recovery_seconds.get(),
                        occlusion_recovery_distance=self.occlusion_recovery_distance.get(),
                        reid_check_interval=self.reid_check_interval.get(),
                        reid_confidence_threshold=self.reid_confidence_threshold.get(),
                        use_harmonic_mean=self.use_harmonic_mean.get(),
                        use_expansion_iou=self.use_expansion_iou.get(),
                        enable_soccer_reid_training=self.enable_soccer_reid_training.get(),
                        use_enhanced_kalman=self.use_enhanced_kalman.get(),
                        use_ema_smoothing=self.use_ema_smoothing.get(),
                        confidence_filtering=self.confidence_filtering.get(),
                        adaptive_confidence=self.adaptive_confidence.get(),
                        use_optical_flow=self.use_optical_flow.get(),
                        enable_velocity_constraints=self.enable_velocity_constraints.get(),
                        track_referees=self.track_referees.get(),
                        max_players=self.max_players.get(),
                        enable_substitutions=self.enable_substitutions.get(),
                        watch_only=True,  # Always watch-only for batch
                        focused_players=[player_name],  # Focus on this player
                        progress_callback=self.update_progress
                    )
                    
                    if result is None:
                        self.log_message(f"⚠ Analysis returned None for {player_name} - may have exited early")
                    else:
                        self.log_message(f"✓ Completed analysis for {player_name}")
                    
                except Exception as e:
                    error_msg = f"Error processing {player_name}: {str(e)}"
                    self.log_message(f"⚠ {error_msg}")
                    import traceback
                    error_details = traceback.format_exc()
                    self.log_message(f"Error details:\n{error_details}")
                    # Continue with next player even if one fails
                    continue
            
            # All players completed
            self.log_message("=" * 60)
            self.log_message(f"✅ BATCH PROCESSING COMPLETE: Processed {total_players} player(s)")
            self.log_message("=" * 60)
            
            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, self.analysis_complete, True, 
                           f"Batch processing complete: {total_players} player(s) processed")
            
        except Exception as e:
            error_msg = f"Batch processing error: {str(e)}"
            self.log_message(f"⚠ {error_msg}")
            self.root.after(0, self.analysis_complete, False, error_msg)

    def apply_performance_mode(self):
        """Apply Performance Mode settings - optimized for speed (2-3x faster)"""
        # Tracking settings
        self.process_every_nth.set(2)  # Process every 2nd frame (2x speedup)
        self.yolo_resolution.set("720p")  # Lower resolution (30-40% speedup)
        self.batch_size.set(20)  # Larger batch size (10-20% speedup)
        self.foot_based_tracking.set(False)  # Disable foot tracking (20-30% speedup)
        self.reid_check_interval.set(60)  # Less frequent Re-ID checks (5-10% speedup)
        
        # Output settings
        self.output_fps.set(0.0)  # Preserve input FPS (maintain full frame rate quality)
        
        # Detection settings
        self.track_thresh.set(0.25)  # Keep current threshold
        
        # Smoothing (can disable for more speed)
        self.temporal_smoothing.set(True)  # Keep enabled for stability
        self.use_enhanced_kalman.set(False)  # Disable for speed
        
        # Log the changes
        self.log_message("🚀 Performance Mode applied:")
        self.log_message("  • Process every 2nd frame (2x speedup)")
        self.log_message("  • YOLO resolution: 720p (30-40% speedup)")
        self.log_message("  • Batch size: 20 (10-20% speedup)")
        self.log_message("  • Foot-based tracking: Disabled (20-30% speedup)")
        self.log_message("  • Re-ID check interval: 60 frames (5-10% speedup)")
        self.log_message("  • Output FPS: Same as input (preserve full frame rate)")
        self.log_message("  Expected: 2-3x faster processing (~4-6 fps)")
        
        # Show confirmation
        import tkinter.messagebox as messagebox
        messagebox.showinfo("Performance Mode Applied", 
                           "Performance Mode settings have been applied!\n\n"
                           "Expected speedup: 2-3x faster\n"
                           "Settings optimized for speed while maintaining reasonable quality.")

    def _validate_gallery_threshold(self):
        """Ensure gallery similarity threshold is never below 0.20"""
        try:
            current_value = self.gallery_similarity_threshold.get()
            if current_value < 0.20:
                self.gallery_similarity_threshold.set(0.20)
                print(f"  ⚠ Gallery Similarity Threshold clamped to minimum 0.20 (was {current_value:.2f})")
        except (tk.TclError, ValueError):
            # Invalid value, set to default
            self.gallery_similarity_threshold.set(0.40)
    
    def apply_high_quality_mode(self):
        """Apply High Quality Mode settings - maximum accuracy & quality"""
        # Tracking settings
        self.process_every_nth.set(1)  # Process all frames (maximum accuracy)
        self.yolo_resolution.set("1080p")  # Higher resolution (better detection)
        self.batch_size.set(12)  # Moderate batch size (balance)
        self.foot_based_tracking.set(True)  # Enable foot tracking (more stable)
        self.reid_check_interval.set(20)  # More frequent Re-ID checks (better persistence)
        
        # Output settings
        self.output_fps.set(0.0)  # Same as input (preserve original frame rate)
        
        # Detection settings
        self.track_thresh.set(0.20)  # Lower threshold for more detections
        
        # Smoothing (enable all for best quality)
        self.temporal_smoothing.set(True)  # Enable temporal smoothing
        self.use_enhanced_kalman.set(True)  # Enable enhanced Kalman filtering
        
        # Match threshold (stricter for better quality)
        self.match_thresh.set(0.65)  # Slightly higher for better matching
        
        # Log the changes
        self.log_message("✨ High Quality Mode applied:")
        self.log_message("  • Process all frames (maximum accuracy)")
        self.log_message("  • YOLO resolution: 1080p (best detection quality)")
        self.log_message("  • Batch size: 12 (balanced)")
        self.log_message("  • Foot-based tracking: Enabled (stable tracking)")
        self.log_message("  • Re-ID check interval: 20 frames (better persistence)")
        self.log_message("  • Output FPS: Same as input (preserve quality)")
        self.log_message("  • Enhanced smoothing: Enabled")
        self.log_message("  • Detection threshold: 0.20 (more detections)")
        self.log_message("  Expected: Best quality, slower processing (~1.5-2 fps)")
        
        # Show confirmation
        import tkinter.messagebox as messagebox
        messagebox.showinfo("High Quality Mode Applied", 
                           "High Quality Mode settings have been applied!\n\n"
                           "Maximum accuracy and quality settings enabled.\n"
                           "Processing will be slower but with best results.")
    
    def _create_menu_bar(self):
        """Create menu bar with File, Edit, View menus"""
        if not QUICK_WINS_AVAILABLE:
            return
        
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Project", command=self.create_new_project, accelerator="Ctrl+N")
        file_menu.add_command(label="Open Project...", command=self.load_project, accelerator="Ctrl+O")
        file_menu.add_separator()
        
        # Recent projects submenu
        recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Open Recent", menu=recent_menu)
        self.recent_menu = recent_menu
        self._update_recent_projects_menu(recent_menu)
        
        file_menu.add_separator()
        file_menu.add_command(label="Save Project", command=self.save_project, accelerator="Ctrl+S")
        file_menu.add_command(label="Save Project As...", command=self.save_project_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self._undo_action, accelerator="Ctrl+Z", 
                            state=tk.DISABLED if not self.undo_manager.can_undo() else tk.NORMAL)
        edit_menu.add_command(label="Redo", command=self._redo_action, accelerator="Ctrl+Y",
                            state=tk.DISABLED if not self.undo_manager.can_redo() else tk.NORMAL)
        edit_menu.add_separator()
        edit_menu.add_command(label="Preferences...", command=self._show_preferences, accelerator="Ctrl+,")
        self.edit_menu = edit_menu
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Fullscreen", command=self._toggle_fullscreen, accelerator="F11")
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self._show_shortcuts)
        help_menu.add_command(label="What's New", command=self._show_whats_new)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self._show_about)
        
        self.menubar = menubar
        self.file_menu = file_menu
    
    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts"""
        if not QUICK_WINS_AVAILABLE:
            return
        
        # Register preferences shortcut (Ctrl+,)
        try:
            self.root.bind('<Control-comma>', lambda e: self._show_preferences())
        except:
            pass  # Some systems may not support this shortcut
        
        # File operations
        self.keyboard_shortcuts.register('Ctrl+o', self.load_project, "Open Project")
        self.keyboard_shortcuts.register('Ctrl+s', self.save_project, "Save Project")
        self.keyboard_shortcuts.register('Ctrl+Shift+s', self.save_project_as, "Save Project As")
        self.keyboard_shortcuts.register('Ctrl+n', self.create_new_project, "New Project")
        
        # Edit operations
        self.keyboard_shortcuts.register('Ctrl+z', self._undo_action, "Undo")
        self.keyboard_shortcuts.register('Ctrl+y', self._redo_action, "Redo")
        
        # Analysis operations
        self.keyboard_shortcuts.register('F5', self.start_analysis, "Start Analysis")
        self.keyboard_shortcuts.register('F6', self.stop_analysis, "Stop Analysis")
        self.keyboard_shortcuts.register('F7', self.preview_analysis, "Preview Analysis")
        
        # View operations
        self.keyboard_shortcuts.register('F11', self._toggle_fullscreen, "Toggle Fullscreen")
        
        # Escape key for closing dialogs (handled by dialog windows themselves)
        # Note: Individual dialogs should bind Escape to destroy themselves
    
    def _undo_action(self):
        """Undo last action"""
        if QUICK_WINS_AVAILABLE and self.undo_manager and self.undo_manager.undo():
            self._update_undo_redo_menu()
    
    def _redo_action(self):
        """Redo last undone action"""
        if QUICK_WINS_AVAILABLE and self.undo_manager and self.undo_manager.redo():
            self._update_undo_redo_menu()
    
    def _update_undo_redo_menu(self):
        """Update undo/redo menu states"""
        if QUICK_WINS_AVAILABLE and hasattr(self, 'edit_menu') and self.undo_manager:
            self.edit_menu.entryconfig("Undo", 
                state=tk.NORMAL if self.undo_manager.can_undo() else tk.DISABLED)
            self.edit_menu.entryconfig("Redo",
                state=tk.NORMAL if self.undo_manager.can_redo() else tk.DISABLED)
    
    def _update_recent_projects_menu(self, menu):
        """Update recent projects menu"""
        if not QUICK_WINS_AVAILABLE or not self.recent_projects:
            return
        
        menu.delete(0, tk.END)
        projects = self.recent_projects.get_projects()
        if not projects:
            menu.add_command(label="No recent projects", state=tk.DISABLED)
        else:
            for project in projects:
                menu.add_command(
                    label=f"{project['name']}",
                    command=lambda p=project['path']: self.load_project(p)
                )
    
    def _toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        self.root.attributes('-fullscreen', not self.root.attributes('-fullscreen'))
    
    def _show_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        if not QUICK_WINS_AVAILABLE:
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Keyboard Shortcuts")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        
        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        shortcuts = self.keyboard_shortcuts.get_shortcuts_list()
        content = "Keyboard Shortcuts\n\n"
        for shortcut in shortcuts:
            content += f"{shortcut['key']:20} - {shortcut['description']}\n"
        
        text.insert('1.0', content)
        text.config(state=tk.DISABLED)
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def _check_whats_new(self):
        """Check and show 'What's New' dialog on first run"""
        if not QUICK_WINS_AVAILABLE:
            return
        
        whats_new_file = Path("whats_new_shown.json")
        version = "2.0.0"  # Update this with each release
        
        try:
            if whats_new_file.exists():
                with open(whats_new_file, 'r') as f:
                    data = json.load(f)
                    if data.get('version') == version:
                        return  # Already shown
        except:
            pass
        
        # Show what's new
        self._show_whats_new()
        
        # Mark as shown
        try:
            with open(whats_new_file, 'w') as f:
                json.dump({'version': version, 'date': datetime.now().isoformat()}, f)
        except:
            pass
    
    def _show_whats_new(self):
        """Show 'What's New' dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("What's New")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, width=70, height=20)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        content = """What's New in Soccer Analysis Tool v2.0.0

🎉 New Features:
• Progress tracking with percentages and ETA
• Undo/Redo functionality (Ctrl+Z, Ctrl+Y)
• Keyboard shortcuts for common actions
• Recent projects menu
• Auto-save every 5 minutes
• Tooltips on all controls
• Enhanced error handling
• JSON corruption protection

🔧 Improvements:
• Better logging system
• Improved project management
• Enhanced user experience

📚 For more information, see the documentation.
"""
        text.insert('1.0', content)
        text.config(state=tk.DISABLED)
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def _show_preferences(self):
        """Show preferences dialog"""
        if not QUICK_WINS_AVAILABLE:
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Preferences")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Auto-save section
        auto_save_frame = ttk.LabelFrame(main_frame, text="Auto-Save", padding="10")
        auto_save_frame.pack(fill=tk.X, pady=10)
        
        auto_save_var = tk.BooleanVar(value=self.auto_save.is_enabled())
        auto_save_check = ttk.Checkbutton(
            auto_save_frame, 
            text="Enable auto-save (saves project every 5 minutes)",
            variable=auto_save_var
        )
        auto_save_check.pack(anchor=tk.W, pady=5)
        
        ttk.Label(
            auto_save_frame, 
            text="Auto-save helps prevent data loss by automatically saving your project.",
            foreground="gray",
            font=("Arial", 9)
        ).pack(anchor=tk.W, padx=25)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        def save_preferences():
            # Save auto-save preference
            self.auto_save.set_enabled(auto_save_var.get())
            self._save_auto_save_preference(auto_save_var.get())
            dialog.destroy()
        
        ttk.Button(button_frame, text="OK", command=save_preferences).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def _load_auto_save_preference(self) -> bool:
        """Load auto-save preference from file (default: True)"""
        prefs_file = "gui_preferences.json"
        if os.path.exists(prefs_file):
            try:
                with open(prefs_file, 'r') as f:
                    prefs = json.load(f)
                    return prefs.get('auto_save_enabled', True)
            except Exception as e:
                if QUICK_WINS_AVAILABLE:
                    from logger_config import get_logger
                    logger = get_logger(__name__)
                    logger.warning(f"Could not load preferences: {e}")
        return True  # Default to enabled
    
    def _save_auto_save_preference(self, enabled: bool):
        """Save auto-save preference to file"""
        prefs_file = "gui_preferences.json"
        try:
            prefs = {}
            if os.path.exists(prefs_file):
                try:
                    with open(prefs_file, 'r') as f:
                        prefs = json.load(f)
                except:
                    pass
            
            prefs['auto_save_enabled'] = enabled
            
            with open(prefs_file, 'w') as f:
                json.dump(prefs, f, indent=2)
            if QUICK_WINS_AVAILABLE:
                from logger_config import get_logger
                logger = get_logger(__name__)
                logger.info(f"Saved auto-save preference: {enabled}")
        except Exception as e:
            if QUICK_WINS_AVAILABLE:
                from logger_config import get_logger
                logger = get_logger(__name__)
                logger.error(f"Could not save preferences: {e}")
    
    def _show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About", 
            "Soccer Video Analysis Tool\n\n"
            "Version 2.0.0\n\n"
            "Advanced soccer video analysis with player tracking, "
            "Re-ID, and comprehensive analytics.")
    
    def _get_box_color_r(self):
        """Extract R component from box_color_rgb"""
        try:
            from color_picker_utils import rgb_string_to_tuple
            r, g, b = rgb_string_to_tuple(self.box_color_rgb.get(), default=(0, 255, 0))
            return r
        except:
            return 0
    
    def _get_box_color_g(self):
        """Extract G component from box_color_rgb"""
        try:
            from color_picker_utils import rgb_string_to_tuple
            r, g, b = rgb_string_to_tuple(self.box_color_rgb.get(), default=(0, 255, 0))
            return g
        except:
            return 255
    
    def _get_box_color_b(self):
        """Extract B component from box_color_rgb"""
        try:
            from color_picker_utils import rgb_string_to_tuple
            r, g, b = rgb_string_to_tuple(self.box_color_rgb.get(), default=(0, 255, 0))
            return b
        except:
            return 0
    
    def _create_event_detection_tab(self, parent):
        """Create the Event Detection tab UI"""
        # Event Detection Variables
        self.event_csv_file = tk.StringVar()
        self.event_min_confidence = tk.DoubleVar(value=0.5)
        self.event_min_ball_speed = tk.DoubleVar(value=3.0)
        self.event_min_pass_distance = tk.DoubleVar(value=5.0)
        self.event_possession_threshold = tk.DoubleVar(value=1.5)
        self.event_detect_passes = tk.BooleanVar(value=True)
        self.event_detect_shots = tk.BooleanVar(value=True)
        self.event_detect_goals = tk.BooleanVar(value=False)
        self.event_detect_zones = tk.BooleanVar(value=True)
        self.event_export_csv = tk.BooleanVar(value=True)
        self.event_goal_areas_file = tk.StringVar()
        
        row = 0
        
        # Title
        title_label = ttk.Label(parent, text="Automated Event Detection", 
                               font=("Arial", 14, "bold"))
        title_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        row += 1
        
        desc_label = ttk.Label(parent, 
                               text="Detect passes, shots, and analyze zone occupancy from existing CSV tracking data.\n"
                                    "No need to re-process videos - works with your existing analysis results.",
                               font=("Arial", 9), foreground="gray", justify=tk.LEFT)
        desc_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 15))
        row += 1
        
        # CSV File Selection
        csv_frame = ttk.LabelFrame(parent, text="CSV Tracking Data", padding="10")
        csv_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        csv_frame.columnconfigure(1, weight=1)
        row += 1
        
        ttk.Label(csv_frame, text="Tracking CSV File:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(csv_frame, textvariable=self.event_csv_file, width=50).grid(
            row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(csv_frame, text="Browse", 
                  command=self._browse_event_csv_file).grid(row=0, column=2, padx=5, pady=5)
        
        # Auto-detect CSV from output file
        ttk.Button(csv_frame, text="Auto-detect from Output", 
                  command=self._auto_detect_event_csv).grid(row=1, column=0, columnspan=3, pady=5)
        
        # Detection Parameters
        params_frame = ttk.LabelFrame(parent, text="Detection Parameters", padding="10")
        params_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        params_frame.columnconfigure(1, weight=1)
        row += 1
        
        # Confidence threshold
        ttk.Label(params_frame, text="Min Confidence:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        conf_spinbox = ttk.Spinbox(params_frame, from_=0.1, to=1.0, increment=0.05,
                                  textvariable=self.event_min_confidence, width=10, format="%.2f")
        conf_spinbox.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(params_frame, text="(0.1 = more detections, 1.0 = only very confident)", 
                 font=("Arial", 8), foreground="gray").grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Min ball speed
        ttk.Label(params_frame, text="Min Ball Speed (m/s):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        speed_spinbox = ttk.Spinbox(params_frame, from_=1.0, to=15.0, increment=0.5,
                                    textvariable=self.event_min_ball_speed, width=10, format="%.1f")
        speed_spinbox.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(params_frame, text="(Minimum ball speed during pass)", 
                 font=("Arial", 8), foreground="gray").grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # Min pass distance
        ttk.Label(params_frame, text="Min Pass Distance (m):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        dist_spinbox = ttk.Spinbox(params_frame, from_=2.0, to=30.0, increment=1.0,
                                   textvariable=self.event_min_pass_distance, width=10, format="%.1f")
        dist_spinbox.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(params_frame, text="(Minimum pass length in meters)", 
                 font=("Arial", 8), foreground="gray").grid(row=2, column=2, sticky=tk.W, padx=5)
        
        # Possession threshold
        ttk.Label(params_frame, text="Possession Threshold (m):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        poss_spinbox = ttk.Spinbox(params_frame, from_=0.5, to=5.0, increment=0.5,
                                   textvariable=self.event_possession_threshold, width=10, format="%.1f")
        poss_spinbox.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(params_frame, text="(Ball within this distance = possession)", 
                 font=("Arial", 8), foreground="gray").grid(row=3, column=2, sticky=tk.W, padx=5)
        
        # Event Types
        types_frame = ttk.LabelFrame(parent, text="Event Types", padding="10")
        types_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        row += 1
        
        ttk.Checkbutton(types_frame, text="Detect Passes", 
                       variable=self.event_detect_passes).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(types_frame, text="Detect Shots", 
                       variable=self.event_detect_shots).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(types_frame, text="Detect Goals", 
                       variable=self.event_detect_goals).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(types_frame, text="Analyze Zone Occupancy", 
                       variable=self.event_detect_zones).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Goal Area Designation
        goal_area_frame = ttk.LabelFrame(parent, text="Goal Area Designation", padding="10")
        goal_area_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        goal_area_frame.columnconfigure(1, weight=1)
        row += 1
        
        ttk.Label(goal_area_frame, text="Goal Areas JSON:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(goal_area_frame, textvariable=self.event_goal_areas_file, width=50).grid(
            row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(goal_area_frame, text="Browse", 
                  command=self._browse_goal_areas_file).grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Button(goal_area_frame, text="🎯 Designate Goal Areas", 
                  command=self._designate_goal_areas, width=25).grid(row=1, column=0, columnspan=3, pady=5)
        
        ttk.Button(goal_area_frame, text="Auto-detect from Video", 
                  command=self._auto_detect_goal_areas, width=25).grid(row=2, column=0, columnspan=3, pady=5)
        
        ttk.Label(goal_area_frame, 
                 text="Designate goal areas on the field to enable accurate shot and goal detection.\n"
                      "Click 'Designate Goal Areas' to mark goal boundaries on a video frame.\n"
                      "Or use 'Auto-detect' to find existing goal area files.",
                 font=("Arial", 8), foreground="gray", justify=tk.LEFT).grid(
            row=3, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        
        # Export Options
        export_frame = ttk.LabelFrame(parent, text="Export Options", padding="10")
        export_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        row += 1
        
        ttk.Checkbutton(export_frame, text="Export Events to CSV", 
                       variable=self.event_export_csv).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=row, column=0, columnspan=3, pady=15)
        row += 1
        
        self.event_detect_button = ttk.Button(button_frame, text="🔍 Run Event Detection", 
                                             command=self._run_event_detection, width=25)
        self.event_detect_button.pack(side=tk.LEFT, padx=5)
        
        self.event_view_results_button = ttk.Button(button_frame, text="📊 View Results", 
                                                   command=self._view_event_results, width=20, state=tk.DISABLED)
        self.event_view_results_button.pack(side=tk.LEFT, padx=5)
        
        self.event_view_pass_stats_button = ttk.Button(button_frame, text="⚽ Pass Statistics", 
                                                       command=self._view_pass_statistics, width=20, state=tk.DISABLED)
        self.event_view_pass_stats_button.pack(side=tk.LEFT, padx=5)
        
        # Results Display
        results_frame = ttk.LabelFrame(parent, text="Results", padding="10")
        results_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E+tk.N+tk.S, pady=5)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        parent.rowconfigure(row, weight=1)
        row += 1
        
        # Text widget with scrollbar for results
        results_text_frame = ttk.Frame(results_frame)
        results_text_frame.grid(row=0, column=0, sticky=tk.W+tk.E+tk.N+tk.S)
        results_text_frame.columnconfigure(0, weight=1)
        results_text_frame.rowconfigure(0, weight=1)
        
        self.event_results_text = scrolledtext.ScrolledText(results_text_frame, height=15, width=80,
                                                           font=("Courier", 9), wrap=tk.WORD)
        self.event_results_text.grid(row=0, column=0, sticky=tk.W+tk.E+tk.N+tk.S)
        
        # Store last results path and pass data
        self.event_last_results_path = None
        self.event_pass_data = None  # Store pass statistics data
    
    def _browse_event_csv_file(self):
        """Browse for CSV tracking file"""
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
    
    def _browse_goal_areas_file(self):
        """Browse for goal areas JSON file"""
        filename = filedialog.askopenfilename(
            title="Select Goal Areas JSON File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.event_goal_areas_file.set(filename)
    
    def _designate_goal_areas(self):
        """Open goal area designation tool"""
        # Get video file
        video_path = self.input_file.get()
        if not video_path or not os.path.exists(video_path):
            messagebox.showwarning("No Video", 
                                 "Please select a video file first to designate goal areas.")
            return
        
        try:
            from goal_area_designator import designate_goal_areas_interactive
            
            # Ask for frame number
            frame_num_str = simpledialog.askstring(
                "Frame Number",
                "Enter frame number to use for goal area designation:\n"
                "(Use a frame where goals are clearly visible)\n\n"
                "Frame number:",
                initialvalue="0"
            )
            
            if frame_num_str is None:
                return
            
            try:
                frame_num = int(frame_num_str)
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid frame number.")
                return
            
            # Run designation tool directly (OpenCV needs main thread)
            # Use after() to ensure Tkinter is ready
            def run_designation():
                try:
                    # This will block until user finishes, but that's OK for OpenCV
                    designator = designate_goal_areas_interactive(video_path, frame_num)
                    self._on_goal_areas_designated(designator)
                except Exception as e:
                    import traceback
                    error_msg = f"Error during goal area designation:\n{str(e)}\n\n{traceback.format_exc()}"
                    messagebox.showerror("Error", error_msg)
            
            # Schedule to run after a short delay to ensure GUI is ready
            self.root.after(100, run_designation)
            
        except Exception as e:
            import traceback
            error_msg = f"Error starting goal area designation:\n{str(e)}\n\n{traceback.format_exc()}"
            messagebox.showerror("Error", error_msg)
    
    def _on_goal_areas_designated(self, designator):
        """Handle completion of goal area designation"""
        if designator and designator.goal_areas:
            # Auto-save and set the file path
            output_path = designator.save_goal_areas()
            self.event_goal_areas_file.set(output_path)
            messagebox.showinfo("Success", 
                              f"Goal areas designated and saved!\n\n"
                              f"File: {output_path}\n"
                              f"Goals: {len(designator.goal_areas)}\n\n"
                              "You can now use this file for shot and goal detection.")
        elif designator:
            messagebox.showinfo("Cancelled", "Goal area designation was cancelled.")
    
    def _auto_detect_goal_areas(self):
        """Auto-detect goal areas JSON file from video file"""
        video_path = self.input_file.get()
        if not video_path or not os.path.exists(video_path):
            messagebox.showwarning("No Video", 
                                 "Please select a video file first to auto-detect goal areas.")
            return
        
        # Look for goal areas JSON in same directory as video
        video_dir = os.path.dirname(video_path)
        video_basename = os.path.splitext(os.path.basename(video_path))[0]
        
        # Try common filename patterns
        json_patterns = [
            f"goal_areas_{video_basename}.json",
            f"{video_basename}_goal_areas.json",
            "goal_areas.json"
        ]
        
        for pattern in json_patterns:
            json_path = os.path.join(video_dir, pattern)
            if os.path.exists(json_path):
                self.event_goal_areas_file.set(json_path)
                messagebox.showinfo("Goal Areas Found", f"Found goal areas file:\n{json_path}")
                return
        
        # If not found, let user know
        messagebox.showinfo("Goal Areas Not Found", 
                           f"Could not find goal areas file in:\n{video_dir}\n\n"
                           "Please designate goal areas first using 'Designate Goal Areas' button.")
        self._browse_event_csv_file()
    
    def _run_event_detection(self):
        """Run event detection on selected CSV file"""
        csv_path = self.event_csv_file.get()
        if not csv_path or not os.path.exists(csv_path):
            messagebox.showerror("Error", "Please select a valid CSV tracking file.")
            return
        
        # Disable button during processing
        self.event_detect_button.config(state=tk.DISABLED)
        self.event_results_text.delete(1.0, tk.END)
        self.event_results_text.insert(tk.END, "Running event detection...\n\n")
        self.root.update()
        
        # Run in thread to avoid blocking GUI
        def run_detection():
            try:
                from event_detector import EventDetector
                from event_marker_system import EventMarkerSystem
                
                # Initialize detector
                detector = EventDetector(csv_path)
                
                if not detector.load_tracking_data():
                    self.root.after(0, lambda: self._event_detection_error("Failed to load tracking data"))
                    return
                
                # Try to load event markers if available
                event_marker_system = None
                video_path = self.input_file.get()
                if video_path and os.path.exists(video_path):
                    event_marker_system = EventMarkerSystem(video_path=video_path)
                    video_dir = os.path.dirname(os.path.abspath(video_path))
                    video_basename = os.path.splitext(os.path.basename(video_path))[0]
                    marker_path = os.path.join(video_dir, f"{video_basename}_event_markers.json")
                    if os.path.exists(marker_path):
                        if event_marker_system.load_from_file(marker_path):
                            print(f"✓ Loaded {len(event_marker_system.markers)} event markers as anchor points")
                
                results = []
                results.append("=" * 60)
                results.append("Event Detection Results")
                results.append("=" * 60)
                results.append(f"CSV File: {os.path.basename(csv_path)}")
                if event_marker_system and event_marker_system.markers:
                    results.append(f"Event Markers: {len(event_marker_system.markers)} manual markers loaded")
                results.append("")
                
                # Detect passes with accuracy tracking
                pass_data = None
                if self.event_detect_passes.get():
                    # Use enhanced pass detection with accuracy
                    pass_data = detector.detect_passes_with_accuracy(
                        min_ball_speed=self.event_min_ball_speed.get(),
                        min_pass_distance=self.event_min_pass_distance.get(),
                        possession_threshold=self.event_possession_threshold.get(),
                        confidence_threshold=self.event_min_confidence.get()
                    )
                    
                    successful_passes = pass_data.get('successful_passes', [])
                    incomplete_passes = pass_data.get('incomplete_passes', [])
                    accuracy_metrics = pass_data.get('accuracy_metrics', {})
                    
                    detector.events.extend(successful_passes)
                    detector.events.extend(incomplete_passes)
                    
                    total_passes = len(successful_passes) + len(incomplete_passes)
                    completion_rate = accuracy_metrics.get('overall_completion_rate', 0.0) * 100
                    
                    results.append(f"📊 Pass Detection with Accuracy:")
                    results.append(f"  Total Passes: {total_passes}")
                    results.append(f"  Successful: {len(successful_passes)}")
                    results.append(f"  Incomplete: {len(incomplete_passes)}")
                    results.append(f"  Overall Completion Rate: {completion_rate:.1f}%")
                    
                    if successful_passes:
                        results.append("\nTop 10 successful passes (by confidence):")
                        sorted_passes = sorted(successful_passes, key=lambda x: x.confidence, reverse=True)
                        for i, pass_event in enumerate(sorted_passes[:10], 1):
                            receiver = pass_event.metadata.get('receiver_name') if pass_event.metadata else None
                            distance = pass_event.metadata.get('pass_distance_m', 0) if pass_event.metadata else 0
                            results.append(f"  {i:2d}. Frame {pass_event.frame_num:5d} ({pass_event.timestamp:6.1f}s) - "
                                         f"Conf: {pass_event.confidence:.2f} - "
                                         f"{pass_event.player_name or f'Player {pass_event.player_id}'} → "
                                         f"{receiver or 'Unknown'} ({distance:.1f}m)")
                    
                    if incomplete_passes:
                        results.append(f"\nIncomplete Passes/Interceptions: {len(incomplete_passes)}")
                        interceptions = [p for p in incomplete_passes if p.event_type == "interception"]
                        if interceptions:
                            results.append(f"  Interceptions: {len(interceptions)}")
                    
                    results.append("")
                
                # Detect shots (using goal areas if available)
                goal_areas_json = self.event_goal_areas_file.get() if self.event_goal_areas_file.get() else None
                if goal_areas_json and not os.path.exists(goal_areas_json):
                    goal_areas_json = None  # Invalid path, use defaults
                
                if self.event_detect_shots.get():
                    shots = detector.detect_shots(
                        goal_areas_json=goal_areas_json,
                        confidence_threshold=self.event_min_confidence.get()
                    )
                    detector.events.extend(shots)
                    
                    results.append(f"📊 Shot Detection: {len(shots)} shots found")
                    if goal_areas_json:
                        results.append(f"  Using goal areas from: {os.path.basename(goal_areas_json)}")
                    if shots:
                        results.append("\nTop 10 shots (by confidence):")
                        sorted_shots = sorted(shots, key=lambda x: x.confidence, reverse=True)
                        for i, shot_event in enumerate(sorted_shots[:10], 1):
                            speed = shot_event.metadata.get('ball_speed_mps', 0) if shot_event.metadata else 0
                            goal_area = shot_event.metadata.get('goal_area', 'default') if shot_event.metadata else 'default'
                            results.append(f"  {i:2d}. Frame {shot_event.frame_num:5d} ({shot_event.timestamp:6.1f}s) - "
                                         f"Conf: {shot_event.confidence:.2f} - "
                                         f"{shot_event.player_name or f'Player {shot_event.player_id}'} - "
                                         f"Speed: {speed:.1f} m/s - Goal: {goal_area}")
                    results.append("")
                
                # Detect goals (requires goal areas)
                if self.event_detect_goals.get():
                    if not goal_areas_json or not os.path.exists(goal_areas_json):
                        results.append("⚠ Goal Detection: No goal areas file specified or file not found.")
                        results.append("   Please designate goal areas first.")
                        results.append("")
                    else:
                        goals = detector.detect_goals(
                            goal_areas_json=goal_areas_json,
                            confidence_threshold=self.event_min_confidence.get()
                        )
                        detector.events.extend(goals)
                        
                        results.append(f"⚽ Goal Detection: {len(goals)} goals found")
                        results.append(f"  Using goal areas from: {os.path.basename(goal_areas_json)}")
                        if goals:
                            results.append("\nAll goals detected:")
                            sorted_goals = sorted(goals, key=lambda x: x.timestamp)
                            for i, goal_event in enumerate(sorted_goals, 1):
                                speed = goal_event.metadata.get('ball_speed_mps', 0) if goal_event.metadata else 0
                                goal_area = goal_event.metadata.get('goal_area', 'unknown') if goal_event.metadata else 'unknown'
                                time_in_goal = goal_event.metadata.get('time_in_goal_s', 0) if goal_event.metadata else 0
                                results.append(f"  {i:2d}. Frame {goal_event.frame_num:5d} ({goal_event.timestamp:6.1f}s) - "
                                             f"Conf: {goal_event.confidence:.2f} - "
                                             f"{goal_event.player_name or f'Player {goal_event.player_id}'} - "
                                             f"Speed: {speed:.1f} m/s - Goal: {goal_area} - "
                                             f"Time in goal: {time_in_goal:.2f}s")
                        results.append("")
                
                # Zone occupancy
                zone_stats = None
                if self.event_detect_zones.get():
                    zones = {
                        'defensive_third': (0.0, 0.0, 1.0, 0.33),
                        'midfield': (0.0, 0.33, 1.0, 0.67),
                        'attacking_third': (0.0, 0.67, 1.0, 1.0)
                    }
                    zone_stats = detector.detect_zone_occupancy(zones)
                    
                    results.append(f"📊 Zone Occupancy Analysis:")
                    if zone_stats:
                        results.append(f"  Found {len(zone_stats)} player-zone combinations")
                        results.append("\nTop 15 zone occupancies (by time):")
                        sorted_zones = sorted(zone_stats.items(), key=lambda x: x[1]['time'], reverse=True)
                        for key, stats in sorted_zones[:15]:
                            player_name = stats['player_name'] or f"Player {stats['player_id']}"
                            results.append(f"  {player_name:20s} - {stats['zone']:20s}: "
                                         f"{stats['time']:6.1f}s ({stats['frames']:4d} frames)")
                    results.append("")
                
                # Merge with event markers if available
                merged_events = None
                if event_marker_system and event_marker_system.markers:
                    # Convert detected events to dict format for merging
                    detected_events_dict = []
                    for event in detector.events:
                        detected_events_dict.append({
                            'event_type': event.event_type,
                            'frame_num': event.frame_num,
                            'timestamp': event.timestamp,
                            'confidence': event.confidence,
                            'player_id': event.player_id,
                            'player_name': event.player_name,
                            'team': event.team,
                            'start_pos': event.start_pos,
                            'end_pos': event.end_pos,
                            'metadata': event.metadata or {}
                        })
                    
                    # Merge markers with detected events
                    merged_events = event_marker_system.merge_with_detected_events(
                        detected_events_dict, 
                        merge_threshold_frames=5
                    )
                    
                    # Count manual vs detected
                    manual_count = sum(1 for e in merged_events if e.get('is_manual', False))
                    detected_count = sum(1 for e in merged_events if not e.get('is_manual', False))
                    results.append(f"\n📌 Event Marker Integration:")
                    results.append(f"  Manual markers: {manual_count}")
                    results.append(f"  Auto-detected: {detected_count}")
                    results.append(f"  Total events: {len(merged_events)}")
                
                # Summary
                results.append("=" * 60)
                results.append("Summary")
                results.append("=" * 60)
                if merged_events:
                    results.append(f"Total events (merged): {len(merged_events)}")
                    event_types = {}
                    for event in merged_events:
                        event_type = event.get('event_type', 'unknown')
                        event_types[event_type] = event_types.get(event_type, 0) + 1
                    results.append("\nEvents by type:")
                    for event_type, count in sorted(event_types.items()):
                        results.append(f"  {event_type}: {count}")
                    
                    avg_confidence = sum(e.get('confidence', 0) for e in merged_events) / len(merged_events) if merged_events else 0
                    results.append(f"\nAverage confidence: {avg_confidence:.2f}")
                else:
                    results.append(f"Total events detected: {len(detector.events)}")
                    if detector.events:
                        event_types = {}
                        for event in detector.events:
                            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
                        results.append("\nEvents by type:")
                        for event_type, count in sorted(event_types.items()):
                            results.append(f"  {event_type}: {count}")
                        
                        avg_confidence = sum(e.confidence for e in detector.events) / len(detector.events)
                        results.append(f"\nAverage confidence: {avg_confidence:.2f}")
                
                # Export if requested
                output_path = None
                if self.event_export_csv.get():
                    if merged_events:
                        # Export merged events
                        output_path = csv_path.replace('.csv', '_detected_events.csv')
                        self._export_merged_events(merged_events, output_path, detector.fps)
                        results.append(f"\n✓ Merged events exported to: {os.path.basename(output_path)}")
                    elif detector.events:
                        output_path = csv_path.replace('.csv', '_detected_events.csv')
                        detector.export_events(output_path)
                        results.append(f"\n✓ Events exported to: {os.path.basename(output_path)}")
                    self.event_last_results_path = output_path
                
                # Update UI
                results_text = "\n".join(results)
                self.root.after(0, lambda: self._event_detection_complete(results_text, output_path, pass_data))
                
            except Exception as e:
                import traceback
                error_msg = f"Error during event detection:\n{str(e)}\n\n{traceback.format_exc()}"
                self.root.after(0, lambda: self._event_detection_error(error_msg))
        
        # Start detection thread
        detection_thread = threading.Thread(target=run_detection, daemon=True)
        detection_thread.start()
    
    def _event_detection_complete(self, results_text, output_path, pass_data=None):
        """Update UI after event detection completes"""
        self.event_results_text.delete(1.0, tk.END)
        self.event_results_text.insert(tk.END, results_text)
        self.event_detect_button.config(state=tk.NORMAL)
        
        # Store pass data for statistics viewer
        self.event_pass_data = pass_data
        
        if output_path:
            self.event_view_results_button.config(state=tk.NORMAL)
        
        # Enable pass statistics button if we have pass data
        if pass_data and pass_data.get('successful_passes') or pass_data.get('incomplete_passes'):
            self.event_view_pass_stats_button.config(state=tk.NORMAL)
        else:
            self.event_view_pass_stats_button.config(state=tk.DISABLED)
    
    def _event_detection_error(self, error_msg):
        """Display error message"""
        self.event_results_text.delete(1.0, tk.END)
        self.event_results_text.insert(tk.END, f"ERROR:\n\n{error_msg}")
        self.event_detect_button.config(state=tk.NORMAL)
        messagebox.showerror("Event Detection Error", error_msg)
    
    def _view_event_results(self):
        """Open event results CSV file"""
        if self.event_last_results_path and os.path.exists(self.event_last_results_path):
            try:
                import subprocess
                import platform
                
                if platform.system() == 'Windows':
                    os.startfile(self.event_last_results_path)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.call(['open', self.event_last_results_path])
                else:  # Linux
                    subprocess.call(['xdg-open', self.event_last_results_path])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file:\n{e}")
        else:
            messagebox.showwarning("No Results", "No results file found. Run event detection first.")
    
    def _export_merged_events(self, merged_events, output_path, fps):
        """Export merged events (manual markers + detected) to CSV"""
        import pandas as pd
        
        rows = []
        for event in merged_events:
            row = {
                'frame': event.get('frame_num', 0),
                'timestamp': event.get('timestamp', 0),
                'event_type': event.get('event_type', 'unknown'),
                'confidence': event.get('confidence', 0),
                'player_id': event.get('player_id', ''),
                'player_name': event.get('player_name', ''),
                'team': event.get('team', ''),
                'is_manual': event.get('is_manual', False),
                'start_x': event.get('start_pos', (None, None))[0] if event.get('start_pos') else '',
                'start_y': event.get('start_pos', (None, None))[1] if event.get('start_pos') else '',
                'end_x': event.get('end_pos', (None, None))[0] if event.get('end_pos') else '',
                'end_y': event.get('end_pos', (None, None))[1] if event.get('end_pos') else '',
            }
            # Add metadata fields
            metadata = event.get('metadata', {})
            for key, value in metadata.items():
                row[f'metadata_{key}'] = value
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)
    
    def _view_pass_statistics(self):
        """Open pass statistics viewer window"""
        if not self.event_pass_data:
            messagebox.showwarning("No Pass Data", "No pass statistics available. Run event detection with pass detection enabled first.")
            return
        
        try:
            from pass_statistics_viewer import PassStatisticsViewer
            PassStatisticsViewer(self.root, self.event_pass_data)
        except Exception as e:
            import traceback
            error_msg = f"Error opening pass statistics viewer:\n{str(e)}\n\n{traceback.format_exc()}"
            messagebox.showerror("Error", error_msg)
    
    def _add_tooltips(self):
        """Add tooltips to key GUI widgets"""
        if not QUICK_WINS_AVAILABLE:
            return
        
        # Add tooltips to file selection buttons
        if hasattr(self, 'input_file_button'):
            create_tooltip(self.input_file_button, "Select the video file to analyze")
        if hasattr(self, 'output_file_button'):
            create_tooltip(self.output_file_button, "Select where to save the analyzed video")
        
        # Add tooltip to start button
        if hasattr(self, 'start_button'):
            create_tooltip(self.start_button, "Start the analysis process (F5)")
        
        # Add tooltip to stop button
        if hasattr(self, 'stop_button'):
            create_tooltip(self.stop_button, "Stop the current analysis (F6)")
        
        # Add tooltips to other important buttons
        if hasattr(self, 'open_folder_button'):
            create_tooltip(self.open_folder_button, "Open the output folder containing results")
        if hasattr(self, 'analyze_csv_button'):
            create_tooltip(self.analyze_csv_button, "Analyze the exported CSV data")
        if hasattr(self, 'analytics_selection_button'):
            create_tooltip(self.analytics_selection_button, "Select which analytics to display in the video")


def main():
    root = tk.Tk()
    app = SoccerAnalysisGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

