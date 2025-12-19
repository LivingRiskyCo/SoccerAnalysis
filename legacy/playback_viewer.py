"""
Playback Viewer with Toggleable Overlays
Loads original video and CSV tracking data to render overlays in real-time
"""

import cv2
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import json
import os
from collections import deque, OrderedDict
import threading
import time
from datetime import datetime
from hd_overlay_renderer import HDOverlayRenderer
from event_tracker import EventTracker
from event_timeline_viewer import EventTimelineViewer
from event_marker_system import EventMarkerSystem, EventMarker, EventType

try:
    import supervision as sv
    SUPERVISION_AVAILABLE = True
except ImportError:
    SUPERVISION_AVAILABLE = False
    print("Warning: supervision not available. Some features may be limited.")


class PlaybackViewer:
    def __init__(self, root, video_path=None, csv_path=None, initial_frame=None, highlight_ids=None, 
                 comparison_mode=False, frame1=None, frame2=None, id1=None, id2=None, 
                 viz_settings=None):
        self.root = root
        self.root.title("Soccer Video Playback Viewer")
        
        # Calculate window size to fit screen
        try:
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            
            # Use 95% of screen size for better fit, with larger defaults for better video visibility
            if comparison_mode:
                # Larger window for comparison mode to accommodate zoomed views
                window_width = min(int(screen_width * 0.95), 1920)  # Increased from 1600
                window_height = min(int(screen_height * 0.95), 1080)  # Increased from 900
            else:
                window_width = min(int(screen_width * 0.95), 1600)  # Increased from 1400
                window_height = min(int(screen_height * 0.95), 1000)  # Increased from 900
            
            # Center the window on screen
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        except:
            # Fallback to fixed size if screen size detection fails
            if comparison_mode:
                self.root.geometry("1920x1080")  # Increased from 1600x900
            else:
                self.root.geometry("1600x1000")  # Increased from 1200x800
        
        # Make window resizable
        self.root.resizable(True, True)
        
        # Set minimum window size - ensure it's wide enough for controls panel and video visibility
        if comparison_mode:
            self.root.minsize(1600, 800)  # Increased from 1400x600 for better video visibility
        else:
            self.root.minsize(1400, 700)  # Increased from 1200x600 for better video visibility
        
        # Window state tracking
        self.is_maximized = False
        self.is_fullscreen = False
        self.normal_geometry = None  # Store normal window geometry before maximizing
        self.always_on_top = tk.BooleanVar(value=False)  # Default to False - no persistent stay on top
        
        # Performance optimization: throttle resize events
        self._resize_pending = False
        self._resize_timer = None
        
        # Playback scheduling - prevent overlapping play() calls
        self._play_after_id = None
        self._play_in_progress = False

        # FRAME BUFFERING: Preload frames to overcome 60ms loading bottleneck
        self.frame_buffer = OrderedDict()  # frame_num -> frame_data (OrderedDict for popitem(last=False))
        self.buffer_size = 320  # Increased to 320 frames ahead for smoother playback
        self.buffer_thread = None
        self.buffer_active = False
        self.buffer_cap = None  # Separate VideoCapture for buffer thread
        self._last_buffer_debug = 0  # For debug output throttling
        self._last_buffer_size = 0  # For buffer change detection  # Prevent concurrent play() calls
        
        # Don't set topmost by default - let user control it via checkbox
        
        # Video and data
        self.video_path = video_path
        self.csv_path = csv_path
        self.cap = None
        self.df = None
        # Convert highlight_ids to integers for consistent comparison
        self.highlight_ids = [int(id) for id in highlight_ids] if highlight_ids else []  # IDs to highlight
        
        # Comparison mode (side-by-side frames)
        self.comparison_mode = comparison_mode
        self.frame1 = int(frame1) if frame1 is not None else None
        self.frame2 = int(frame2) if frame2 is not None else None
        self.id1 = int(id1) if id1 is not None else None
        self.id2 = int(id2) if id2 is not None else None
        
        # Video properties
        self.fps = 30.0
        self.total_frames = 0
        self.current_frame_num = 0
        self.width = 0
        self.height = 0
        self.original_video_width = 0  # Original video dimensions (before transforms)
        self.original_video_height = 0
        
        # Playback state
        self.is_playing = False
        self.playback_speed = 1.0
        self.last_frame_time = 0
        self.last_rendered_frame_num = -1  # Track last rendered frame to avoid redundant rendering
        self.overlay_settings_hash = None  # Track overlay settings to detect changes
        self.cached_canvas_size = None  # Cache canvas size to avoid repeated update_idletasks()
        self.render_mode = None  # 'metadata' or 'csv' - determined once for consistency
        # Profiling state
        self.profiling_stats = {
            "metadata_time": 0.0,
            "metadata_count": 0,
            "csv_time": 0.0,
            "csv_count": 0,
            "frame_time": 0.0,
            "frame_count": 0,
            "hd_prepare_time": 0.0,
            "hd_prepare_count": 0,
            "field_zones_time": 0.0,
            "field_zones_count": 0,
            "trajectories_time": 0.0,
            "trajectories_count": 0,
            "players_time": 0.0,
            "players_count": 0,
            "ball_time": 0.0,
            "ball_count": 0,
            "downscale_time": 0.0,
            "downscale_count": 0,
        }
        self._profile_last_log_frame = 0
        self._cached_viz_settings_override = None  # Cache viz settings to avoid rebuilding every frame
        self._viz_settings_changed = True  # Flag to track when settings change
        self.overlay_render_mode = tk.StringVar(value="csv")  # 'metadata' or 'csv' - CSV is faster and more reliable
        self.overlay_metadata_stride = 2  # Number of frames to skip between heavy metadata renders
        self.overlay_worker_event = threading.Event()
        self.overlay_worker_running = True
        self.overlay_render_lock = threading.Lock()
        self.overlay_render_request = None
        self.overlay_render_result = None
        self.overlay_last_rendered_frame = -1
        self.overlay_worker_thread = threading.Thread(target=self._overlay_worker_loop, daemon=True)
        self.overlay_worker_thread.start()
        # HD UPGRADE: Use HD quality with advanced blending for better graphics
        # render_scale=2.0 provides 2x resolution for crisp rendering
        # quality="hd" enables HD preset (2x scale, anti-aliasing, better fonts)
        # enable_advanced_blending=True enables glow, shadows, gradients, and other effects
        self.csv_hd_renderer = HDOverlayRenderer(
            render_scale=2.0, 
            quality="hd", 
            enable_advanced_blending=True
        )
        
        # Frame buffering for smooth playback - INCREASED for better performance
        # Optimized for 60fps videos (will auto-adjust based on detected FPS)
        self.frame_buffer = OrderedDict()  # frame_num -> frame_data
        self.buffer_max_size = 240  # Buffer up to 240 frames (4 seconds at 60fps, 8 seconds at 30fps) - INCREASED for smoother playback
        self.buffer_min_size = 80  # Start buffering when below this - INCREASED for 60fps
        self.buffer_read_ahead = 120  # Read this many frames ahead (2 seconds at 60fps) - INCREASED for real-time playback
        self.buffer_thread = None
        self.buffer_thread_running = False
        self.buffer_lock = threading.Lock()
        
        # Rendered frame cache (frames with overlays already applied) - NEW for performance
        self.rendered_frame_cache = OrderedDict()  # frame_num -> (rendered_frame, settings_hash)
        self.rendered_cache_max_size = 60  # Cache up to 60 rendered frames (1 second at 60fps, 2 seconds at 30fps)
        self.rendered_cache_lock = threading.Lock()
        
        # AGGRESSIVE Display downscaling for MUCH faster PhotoImage conversion during playback
        self.playback_downscale_factor = 0.25  # 0.25 = 25% size (16x faster conversion for 4K->960p)
        # For 4K video: 0.25 = ~960x540, 0.33 = ~1267x711, 0.5 = ~1920x1080
        self.playback_downscale_enabled = True  # CRITICAL: Enable downscaling during playback for speed
        self.last_sequential_frame = -1  # Track last frame read sequentially
        
        # Overlay toggles
        self.show_players = tk.BooleanVar(value=True)
        self.show_player_boxes = tk.BooleanVar(value=False)  # Default to False - user wants only circles
        self.show_player_circles = tk.BooleanVar(value=True)  # Default to True - user wants team-colored circles
        self.show_player_labels = tk.BooleanVar(value=True)
        self.show_yolo_boxes = tk.BooleanVar(value=False)  # Show raw YOLO detection boxes (before tracking)
        self.show_ball = tk.BooleanVar(value=True)
        self.show_ball_trail = tk.BooleanVar(value=True)
        self.show_ball_label = tk.BooleanVar(value=True)
        
        # Perspective view (top-down/bird's-eye view)
        self.show_perspective_view = tk.BooleanVar(value=False)
        self.homography_matrix = None
        self.field_dims = None  # (field_length, field_width) in meters
        
        # Pixel measurement tool
        self.measurement_mode = tk.BooleanVar(value=False)
        self.measurement_type = tk.StringVar(value="line")  # "line" or "box"
        self.measure_start = None  # (x, y) in canvas coordinates
        self.measure_end = None  # (x, y) in canvas coordinates
        self.measure_line_id = None  # Canvas line/rectangle ID for measurement
        
        # Visualization options (matching main GUI)
        self.viz_style = tk.StringVar(value="box")
        self.viz_color_mode = tk.StringVar(value="team")
        
        # Enhanced feet marker visualization (matching main GUI)
        self.feet_marker_style = tk.StringVar(value="circle")
        self.feet_marker_opacity = tk.IntVar(value=255)
        self.feet_marker_enable_glow = tk.BooleanVar(value=False)
        self.feet_marker_glow_intensity = tk.IntVar(value=50)
        self.feet_marker_enable_shadow = tk.BooleanVar(value=False)
        self.feet_marker_shadow_offset = tk.IntVar(value=3)
        self.feet_marker_shadow_opacity = tk.IntVar(value=128)
        self.feet_marker_enable_gradient = tk.BooleanVar(value=False)
        self.feet_marker_enable_pulse = tk.BooleanVar(value=False)
        self.feet_marker_pulse_speed = tk.DoubleVar(value=2.0)
        self.feet_marker_enable_particles = tk.BooleanVar(value=False)
        self.feet_marker_particle_count = tk.IntVar(value=5)
        self.feet_marker_vertical_offset = tk.IntVar(value=50)  # Vertical offset in pixels
        
        # Ellipse visualization (for foot-based tracking)
        self.ellipse_width = tk.IntVar(value=20)  # Width of ellipse at feet (pixels)
        self.ellipse_height = tk.IntVar(value=12)  # Height of ellipse at feet (pixels)
        self.ellipse_outline_thickness = tk.IntVar(value=0)  # White border thickness around ellipse (pixels, 0 = no border)
        
        # Box appearance customization (matching main GUI)
        self.box_shrink_factor = tk.DoubleVar(value=0.10)
        self.box_thickness = tk.IntVar(value=2)
        self.use_custom_box_color = tk.BooleanVar(value=False)
        self.box_color_rgb = tk.StringVar(value="0,255,0")  # Box color as "R,G,B" (green default)
        # Individual R, G, B components for spinbox controls (synced with box_color_rgb)
        self.box_color_r = tk.IntVar(value=0)
        self.box_color_g = tk.IntVar(value=255)
        self.box_color_b = tk.IntVar(value=0)
        self.player_viz_alpha = tk.IntVar(value=255)
        
        # Label customization (matching main GUI)
        self.use_custom_label_color = tk.BooleanVar(value=False)
        self.label_color_rgb = tk.StringVar(value="255,255,255")  # Label color as "R,G,B" (white default)
        # Individual R, G, B components for spinbox controls (synced with label_color_rgb)
        self.label_color_r = tk.IntVar(value=255)
        self.label_color_g = tk.IntVar(value=255)
        self.label_color_b = tk.IntVar(value=255)
        self.label_font_scale = tk.DoubleVar(value=0.7)
        self.label_type = tk.StringVar(value="full_name")
        self.label_custom_text = tk.StringVar(value="Player")
        self.label_font_face = tk.StringVar(value="FONT_HERSHEY_SIMPLEX")
        
        # Prediction/decay visualization (matching main GUI)
        self.prediction_duration = tk.DoubleVar(value=1.5)
        self.prediction_size = tk.IntVar(value=5)
        self.prediction_color_r = tk.IntVar(value=255)
        self.prediction_color_g = tk.IntVar(value=255)
        self.prediction_color_b = tk.IntVar(value=0)
        self.prediction_color_alpha = tk.IntVar(value=255)
        self.prediction_style = tk.StringVar(value="dot")
        
        # Data storage
        self.player_data = {}  # frame_num -> {player_id: (x, y, team, name)}
        self.ball_data = {}  # frame_num -> (x, y)
        self.ball_trail = deque(maxlen=64)  # Recent ball positions
        self.player_trails = {}  # player_id -> deque of (frame_num, x, y) positions for breadcrumb trail
        self.analytics_data = {}  # frame_num -> {player_id: {analytics_dict}}
        
        # Player trail (breadcrumb) settings
        self.show_player_trail = tk.BooleanVar(value=False)
        self.player_trail_length = tk.IntVar(value=30)  # Number of positions to show
        self.player_trail_size = tk.IntVar(value=3)  # Size of breadcrumb dots
        self.player_trail_fade = tk.BooleanVar(value=True)  # Fade older positions
        self.player_trail_color_r = tk.IntVar(value=255)
        self.player_trail_color_g = tk.IntVar(value=255)
        self.player_trail_color_b = tk.IntVar(value=0)
        
        # Overlay metadata system
        self.overlay_metadata = None
        self.overlay_renderer = None
        self.use_overlay_metadata = tk.BooleanVar(value=False)  # Metadata is opt-in only (slower, experimental)
        self.show_trajectories = tk.BooleanVar(value=False)
        self.show_field_zones = tk.BooleanVar(value=False)
        self.show_ball_possession = tk.BooleanVar(value=True)
        self.show_predicted_boxes = tk.BooleanVar(value=False)
        self.analytics_position = tk.StringVar(value="with_player")  # "with_player", "top_left", "top_right", "bottom_left", "bottom_right", "top_banner", "bottom_banner", "left_bar", "right_bar"
        # Analytics font and color customization
        self.analytics_font_scale = tk.DoubleVar(value=1.0)  # Increased default for better readability
        self.analytics_font_thickness = tk.IntVar(value=2)  # Font thickness (1-5, default: 2 for better readability)
        self.analytics_font_face = tk.StringVar(value="FONT_HERSHEY_SIMPLEX")
        self.use_custom_analytics_color = tk.BooleanVar(value=True)  # Default to custom color for better contrast
        self.analytics_color_rgb = tk.StringVar(value="255,255,255")  # Analytics color as "R,G,B" (white default)
        self.analytics_title_color_rgb = tk.StringVar(value="255,255,0")  # Title color as "R,G,B" (yellow default)
        # Individual R, G, B components for analytics colors (synced with RGB strings)
        self.analytics_color_r = tk.IntVar(value=255)
        self.analytics_color_g = tk.IntVar(value=255)
        self.analytics_color_b = tk.IntVar(value=255)
        self.analytics_title_color_r = tk.IntVar(value=255)
        self.analytics_title_color_g = tk.IntVar(value=255)
        self.analytics_title_color_b = tk.IntVar(value=0)
        
        # Analytics banner/bar size controls
        self.analytics_banner_height = tk.IntVar(value=500)  # Height for top/bottom banners (pixels)
        self.analytics_bar_width = tk.IntVar(value=250)  # Width for left/right bars (pixels)
        self.analytics_panel_width = tk.IntVar(value=300)  # Width for corner panels
        self.analytics_panel_height = tk.IntVar(value=200)  # Height for corner panels
        
        # Team colors
        self.team_colors = None
        self.player_names = {}
        
        # Event tracking (will be initialized after video is loaded to get correct FPS)
        self.event_tracker = None
        self.event_timeline_viewer = None
        
        # Event marker system
        self.event_marker_system = EventMarkerSystem(video_path=self.video_path)
        self.event_marker_visible = tk.BooleanVar(value=True)
        self.current_event_type = tk.StringVar(value="pass")
        
        # Analytics preferences
        self.analytics_preferences = self.load_analytics_preferences()
        self.show_analytics = tk.BooleanVar(value=len([k for k, v in self.analytics_preferences.items() if v]) > 0)
        self.focused_player_id = None  # ID of focused player for detailed view
        self.show_focused_player_panel = tk.BooleanVar(value=False)
        
        # Current frame
        self.current_frame = None
        
        # File watching for CSV auto-reload
        self.csv_last_modified = None
        self.watch_csv_enabled = tk.BooleanVar(value=True)
        self.watch_thread = None
        self.watch_running = False
        
        # Zoom state (for comparison mode and single frame mode)
        self.zoom_level = 1.0  # Zoom level for single frame mode
        self.zoom_level1 = 1.0  # Zoom level for canvas1
        self.zoom_level2 = 1.0  # Zoom level for canvas2
        self.pan_x = 0  # Pan offset for single frame mode
        self.pan_y = 0  # Pan offset for single frame mode
        self.pan_x1 = 0  # Pan offset for canvas1
        self.pan_y1 = 0  # Pan offset for canvas1
        self.pan_x2 = 0  # Pan offset for canvas2
        self.pan_y2 = 0  # Pan offset for canvas2
        self.is_panning = False  # Whether single frame canvas is being panned (left-click, when zoomed)
        self.is_right_panning = False  # Whether single frame canvas is being panned (right-click, always available)
        self.is_panning1 = False  # Whether canvas1 is being panned
        self.is_panning2 = False  # Whether canvas2 is being panned
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.pan_start_x1 = 0
        self.pan_start_y1 = 0
        self.pan_start_x2 = 0
        self.pan_start_y2 = 0
        self.original_display_frame = None  # Store original frame for zoom (single mode)
        self.original_display_frame1 = None  # Store original frame for zoom
        self.original_display_frame2 = None  # Store original frame for zoom
        
        # Load visualization settings from main GUI if provided
        if viz_settings:
            self._load_viz_settings(viz_settings)
        
        self.create_widgets()
        self.load_configs()
        
        # Cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Auto-load if paths provided
        # CRITICAL FIX: Use after() to ensure widgets are fully created before loading video
        if self.video_path:
            if os.path.exists(self.video_path):
                # Schedule load_video to run after widgets are fully initialized
                # Use a proper function reference to avoid lambda closure issues
                video_path_to_load = self.video_path
                def load_video_delayed():
                    try:
                        self.load_video(video_path_to_load)
                    except Exception as e:
                        print(f"⚠ Warning: Could not auto-load video: {e}")
                self.root.after(100, load_video_delayed)
            else:
                # Video path provided but file doesn't exist
                print(f"⚠ Warning: Video file not found: {self.video_path}")
                self.video_path = None
        if self.csv_path and os.path.exists(self.csv_path):
            self.root.after(200, lambda: self.load_csv(self.csv_path))
            if self.comparison_mode:
                # Comparison mode - render both frames
                self.root.after(300, self.render_overlays)
            else:
                # Single frame mode
                def initialize_frame():
                    if initial_frame is not None:
                        self.current_frame_num = initial_frame
                        try:
                            if hasattr(self, 'frame_var') and self.frame_var:
                                self.frame_var.set(initial_frame)
                        except:
                            pass
                    self.current_frame = self.load_frame()
                    self.render_overlays()
                self.root.after(300, initialize_frame)
            
            # Debug: Log highlight IDs and check if they're in the current frame
            if self.highlight_ids:
                print(f"DEBUG: Highlighting IDs: {self.highlight_ids}")
                if self.current_frame_num in self.player_data:
                    frame_ids = list(self.player_data[self.current_frame_num].keys())
                    print(f"DEBUG: Frame {self.current_frame_num} has player IDs: {frame_ids}")
                    highlighted_in_frame = [id for id in self.highlight_ids if id in frame_ids]
                    print(f"DEBUG: Highlighted IDs in this frame: {highlighted_in_frame}")
        
    def create_widgets(self):
        """Create GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top: File selection and window controls
        file_frame = ttk.LabelFrame(main_frame, text="Load Files", padding="10")
        file_frame.pack(fill=tk.X, pady=5)
        
        # Left side: File operations
        file_buttons_frame = ttk.Frame(file_frame)
        file_buttons_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(file_buttons_frame, text="Load Video", command=self.load_video, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_buttons_frame, text="Load CSV", command=self.load_csv, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_buttons_frame, text="Load Metadata", command=self.load_metadata_manual, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_buttons_frame, text="Reload CSV", command=self.reload_csv, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_buttons_frame, text="Export Video", command=self.export_video, width=15).pack(side=tk.LEFT, padx=5)
        
        # Auto-reload checkbox
        ttk.Checkbutton(file_buttons_frame, text="Auto-reload CSV", variable=self.watch_csv_enabled).pack(side=tk.LEFT, padx=5)
        
        # Right side: Window controls
        window_controls_frame = ttk.Frame(file_frame)
        window_controls_frame.pack(side=tk.RIGHT, padx=(5, 5))  # Explicit right padding for alignment
        
        # Always on top toggle
        ttk.Checkbutton(window_controls_frame, text="Always on Top", variable=self.always_on_top,
                       command=self.toggle_always_on_top).pack(side=tk.LEFT, padx=5)
        
        # Window state buttons
        self.maximize_button = ttk.Button(window_controls_frame, text="Maximize", command=self.maximize_window, width=10)
        self.maximize_button.pack(side=tk.LEFT, padx=2)
        ttk.Button(window_controls_frame, text="Minimize", command=self.minimize_window, width=10).pack(side=tk.LEFT, padx=2)
        self.fullscreen_button = ttk.Button(window_controls_frame, text="Full Screen", command=self.toggle_fullscreen, width=10)
        self.fullscreen_button.pack(side=tk.LEFT, padx=2)
        
        # Status label in the middle
        self.status_label = ttk.Label(file_frame, text="No video loaded", foreground="gray")
        self.status_label.pack(side=tk.LEFT, padx=10, expand=True)
        
        # Playback controls bar (horizontal, above video display)
        playback_controls_bar = ttk.Frame(main_frame, padding="5")
        playback_controls_bar.pack(fill=tk.X, pady=(5, 0))
        
        # Play/Pause button
        self.play_button = ttk.Button(playback_controls_bar, text="▶ Play", command=self.toggle_playback, width=10)
        self.play_button.pack(side=tk.LEFT, padx=2)
        
        # First/Last frame buttons
        ttk.Button(playback_controls_bar, text="⏮ First", command=self.go_to_first, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_controls_bar, text="⏭ Last", command=self.go_to_last, width=8).pack(side=tk.LEFT, padx=2)
        
        # Previous/Next frame buttons
        ttk.Button(playback_controls_bar, text="◀◀", command=self.prev_frame, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_controls_bar, text="▶▶", command=self.next_frame, width=4).pack(side=tk.LEFT, padx=2)
        
        # Frame slider
        self.frame_var = tk.IntVar()
        ttk.Label(playback_controls_bar, text="Frame:").pack(side=tk.LEFT, padx=(10, 2))
        self.frame_slider = ttk.Scale(playback_controls_bar, from_=0, to=100, 
                                     orient=tk.HORIZONTAL, variable=self.frame_var,
                                     command=self.on_slider_change, length=200)
        self.frame_slider.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.frame_label = ttk.Label(playback_controls_bar, text="Frame: 0 / 0", width=15)
        self.frame_label.pack(side=tk.LEFT, padx=2)
        
        # Goto frame entry
        ttk.Label(playback_controls_bar, text="Goto:").pack(side=tk.LEFT, padx=(10, 2))
        self.goto_frame_var = tk.StringVar()
        self.goto_frame_entry = ttk.Entry(playback_controls_bar, textvariable=self.goto_frame_var, width=8)
        self.goto_frame_entry.pack(side=tk.LEFT, padx=2)
        self.goto_frame_entry.bind("<Return>", lambda e: self.goto_frame())
        self.goto_frame_entry.bind("<KP_Enter>", lambda e: self.goto_frame())  # Numeric keypad Enter
        ttk.Button(playback_controls_bar, text="Go", command=self.goto_frame, width=4).pack(side=tk.LEFT, padx=2)
        
        # Speed control
        ttk.Label(playback_controls_bar, text="Speed:").pack(side=tk.LEFT, padx=(10, 2))
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_spin = ttk.Spinbox(playback_controls_bar, from_=0.25, to=4.0, increment=0.25,
                                 textvariable=self.speed_var, width=8)
        speed_spin.pack(side=tk.LEFT, padx=2)
        # CRITICAL FIX: Add trace to update speed immediately when value changes
        self.speed_var.trace_add('write', lambda *args: self.update_speed())
        speed_spin.bind("<KeyRelease>", lambda e: self.update_speed())
        speed_spin.bind("<ButtonRelease>", lambda e: self.update_speed())
        
        # Overlay mode selector
        ttk.Label(playback_controls_bar, text="Mode:").pack(side=tk.LEFT, padx=(10, 2))
        overlay_combo = ttk.Combobox(playback_controls_bar, textvariable=self.overlay_render_mode,
                                     values=["csv", "metadata"], state="readonly", width=10)
        overlay_combo.pack(side=tk.LEFT, padx=2)
        self.overlay_render_mode.trace_add('write', lambda *args: self._on_overlay_mode_change())
        
        # Buffer status display
        ttk.Label(playback_controls_bar, text="Buffer:").pack(side=tk.LEFT, padx=(10, 2))
        self.buffer_status_label = ttk.Label(playback_controls_bar, text="0/0 frames", width=15, foreground="gray")
        self.buffer_status_label.pack(side=tk.LEFT, padx=2)
        
        # Middle: Video display
        display_frame = ttk.Frame(main_frame)
        display_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Use grid for better control over layout - ensures controls panel is always visible
        # CRITICAL: Column 0 (canvas) expands, Column 1 (controls) fixed width
        display_frame.columnconfigure(0, weight=1, minsize=400)  # Canvas column expands but has minimum
        display_frame.columnconfigure(1, weight=0, minsize=400)  # Controls column fixed width - NO EXPANSION
        display_frame.columnconfigure(2, weight=0, minsize=0)  # Focused panel column - no minimum (only takes space when panel is visible)
        display_frame.rowconfigure(0, weight=1)  # Row expands to fill height
        
        # Controls panel (right side) with tabbed interface
        # Use a regular Frame with visible background to ensure it's always visible
        # Align right edge with full screen button (padx right = 5 to match window_controls_frame)
        controls_panel_bg = tk.Frame(display_frame, width=400, bg="lightgray", relief=tk.RAISED, borderwidth=2)
        controls_panel_bg.grid(row=0, column=1, sticky="nsew", padx=(5, 5))  # Explicit right padding to align with full screen button
        controls_panel_bg.grid_propagate(False)
        controls_panel_bg.configure(width=400)
        
        # Create notebook for tabs
        self.controls_notebook = ttk.Notebook(controls_panel_bg)
        self.controls_notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Tab 1: Playback & Overlays
        playback_tab = ttk.Frame(self.controls_notebook, padding="0")
        self.controls_notebook.add(playback_tab, text="Playback & Overlays")
        
        # Tab 2: Visualization
        visualization_tab = ttk.Frame(self.controls_notebook, padding="0")
        self.controls_notebook.add(visualization_tab, text="Visualization")
        
        # Tab 3: Analytics
        analytics_tab = ttk.Frame(self.controls_notebook, padding="0")
        self.controls_notebook.add(analytics_tab, text="Analytics")
        
        # Create scrollable frame for playback tab
        # Use grid for better control over layout
        scroll_canvas_playback = tk.Canvas(playback_tab, highlightthickness=0, bg="white", relief=tk.FLAT, borderwidth=0)
        scrollbar_playback = ttk.Scrollbar(playback_tab, orient="vertical", command=scroll_canvas_playback.yview)
        scrollable_frame_playback = ttk.Frame(scroll_canvas_playback, padding="0")
        
        canvas_window_id_playback = scroll_canvas_playback.create_window((0, 0), window=scrollable_frame_playback, anchor="nw")
        scroll_canvas_playback.configure(yscrollcommand=scrollbar_playback.set)
        
        # Use grid for precise layout control
        scroll_canvas_playback.grid(row=0, column=0, sticky="nsew")
        scrollbar_playback.grid(row=0, column=1, sticky="ns")
        playback_tab.grid_rowconfigure(0, weight=1)
        playback_tab.grid_columnconfigure(0, weight=1)
        playback_tab.grid_columnconfigure(1, weight=0)
        
        def update_scroll_playback_width(event=None):
            try:
                # Force update to get accurate measurements
                playback_tab.update_idletasks()
                scroll_canvas_playback.update_idletasks()
                scrollbar_playback.update_idletasks()
                
                # Use tab width as the base measurement
                tab_width = playback_tab.winfo_width()
                if tab_width > 1:
                    # Get actual scrollbar width
                    scrollbar_width = scrollbar_playback.winfo_width() if scrollbar_playback.winfo_exists() else 17
                    # Set scrollable frame width to fill available space exactly
                    # Use tab width minus scrollbar width (no padding since tab padding is 0)
                    available_width = tab_width - scrollbar_width
                    if available_width > 0:
                        scroll_canvas_playback.itemconfig(canvas_window_id_playback, width=available_width)
            except:
                pass
        
        def configure_scroll_playback_region(event=None):
            try:
                scroll_canvas_playback.configure(scrollregion=scroll_canvas_playback.bbox("all"))
            except:
                pass
        
        # Bind to both tab and canvas configure events
        playback_tab.bind('<Configure>', update_scroll_playback_width)
        scroll_canvas_playback.bind('<Configure>', update_scroll_playback_width)
        scrollable_frame_playback.bind("<Configure>", lambda e: (configure_scroll_playback_region(e), update_scroll_playback_width(e)))
        
        # Initial width update after a short delay to ensure everything is rendered
        playback_tab.after(100, update_scroll_playback_width)
        
        def _on_mousewheel_playback(event):
            scroll_canvas_playback.yview_scroll(int(-1*(event.delta/120)), "units")
        scroll_canvas_playback.bind("<MouseWheel>", _on_mousewheel_playback)
        scroll_canvas_playback.bind("<Button-4>", lambda e: scroll_canvas_playback.yview_scroll(-1, "units"))
        scroll_canvas_playback.bind("<Button-5>", lambda e: scroll_canvas_playback.yview_scroll(1, "units"))
        
        # Create scrollable frame for visualization tab
        scroll_canvas_viz = tk.Canvas(visualization_tab, highlightthickness=0, bg="white", relief=tk.FLAT, borderwidth=0)
        scrollbar_viz = ttk.Scrollbar(visualization_tab, orient="vertical", command=scroll_canvas_viz.yview)
        scrollable_frame_viz = ttk.Frame(scroll_canvas_viz, padding="0")
        
        canvas_window_id_viz = scroll_canvas_viz.create_window((0, 0), window=scrollable_frame_viz, anchor="nw")
        scroll_canvas_viz.configure(yscrollcommand=scrollbar_viz.set)
        
        scroll_canvas_viz.grid(row=0, column=0, sticky="nsew")
        scrollbar_viz.grid(row=0, column=1, sticky="ns")
        visualization_tab.grid_rowconfigure(0, weight=1)
        visualization_tab.grid_columnconfigure(0, weight=1)
        visualization_tab.grid_columnconfigure(1, weight=0)
        
        def update_scroll_viz_width(event=None):
            try:
                visualization_tab.update_idletasks()
                scroll_canvas_viz.update_idletasks()
                scrollbar_viz.update_idletasks()
                
                # Use tab width as the base measurement
                tab_width = visualization_tab.winfo_width()
                if tab_width > 1:
                    scrollbar_width = scrollbar_viz.winfo_width() if scrollbar_viz.winfo_exists() else 17
                    available_width = tab_width - scrollbar_width
                    if available_width > 0:
                        scroll_canvas_viz.itemconfig(canvas_window_id_viz, width=available_width)
            except:
                pass
        
        def configure_scroll_viz_region(event=None):
            try:
                scroll_canvas_viz.configure(scrollregion=scroll_canvas_viz.bbox("all"))
            except:
                pass
        
        visualization_tab.bind('<Configure>', update_scroll_viz_width)
        scroll_canvas_viz.bind('<Configure>', update_scroll_viz_width)
        scrollable_frame_viz.bind("<Configure>", lambda e: (configure_scroll_viz_region(e), update_scroll_viz_width(e)))
        visualization_tab.after(100, update_scroll_viz_width)
        
        def _on_mousewheel_viz(event):
            scroll_canvas_viz.yview_scroll(int(-1*(event.delta/120)), "units")
        scroll_canvas_viz.bind("<MouseWheel>", _on_mousewheel_viz)
        scroll_canvas_viz.bind("<Button-4>", lambda e: scroll_canvas_viz.yview_scroll(-1, "units"))
        scroll_canvas_viz.bind("<Button-5>", lambda e: scroll_canvas_viz.yview_scroll(1, "units"))
        
        # Create scrollable frame for analytics tab
        # Use grid for better control over layout
        scroll_canvas_analytics = tk.Canvas(analytics_tab, highlightthickness=0, bg="white", relief=tk.FLAT, borderwidth=0)
        scrollbar_analytics = ttk.Scrollbar(analytics_tab, orient="vertical", command=scroll_canvas_analytics.yview)
        scrollable_frame_analytics = ttk.Frame(scroll_canvas_analytics, padding="0")
        
        canvas_window_id_analytics = scroll_canvas_analytics.create_window((0, 0), window=scrollable_frame_analytics, anchor="nw")
        scroll_canvas_analytics.configure(yscrollcommand=scrollbar_analytics.set)
        
        # Use grid for precise layout control
        scroll_canvas_analytics.grid(row=0, column=0, sticky="nsew")
        scrollbar_analytics.grid(row=0, column=1, sticky="ns")
        analytics_tab.grid_rowconfigure(0, weight=1)
        analytics_tab.grid_columnconfigure(0, weight=1)
        analytics_tab.grid_columnconfigure(1, weight=0)
        
        def update_scroll_analytics_width(event=None):
            try:
                # Force update to get accurate measurements
                analytics_tab.update_idletasks()
                scroll_canvas_analytics.update_idletasks()
                scrollbar_analytics.update_idletasks()
                
                # Use tab width as the base measurement
                tab_width = analytics_tab.winfo_width()
                if tab_width > 1:
                    # Get actual scrollbar width
                    scrollbar_width = scrollbar_analytics.winfo_width() if scrollbar_analytics.winfo_exists() else 17
                    # Set scrollable frame width to fill available space exactly
                    # Use tab width minus scrollbar width (no padding since tab padding is 0)
                    available_width = tab_width - scrollbar_width
                    if available_width > 0:
                        scroll_canvas_analytics.itemconfig(canvas_window_id_analytics, width=available_width)
            except:
                pass
        
        def configure_scroll_analytics_region(event=None):
            try:
                scroll_canvas_analytics.configure(scrollregion=scroll_canvas_analytics.bbox("all"))
            except:
                pass
        
        # Bind to both tab and canvas configure events
        analytics_tab.bind('<Configure>', update_scroll_analytics_width)
        scroll_canvas_analytics.bind('<Configure>', update_scroll_analytics_width)
        scrollable_frame_analytics.bind("<Configure>", lambda e: (configure_scroll_analytics_region(e), update_scroll_analytics_width(e)))
        
        # Initial width update after a short delay to ensure everything is rendered
        analytics_tab.after(100, update_scroll_analytics_width)
        
        def _on_mousewheel_analytics(event):
            scroll_canvas_analytics.yview_scroll(int(-1*(event.delta/120)), "units")
        scroll_canvas_analytics.bind("<MouseWheel>", _on_mousewheel_analytics)
        scroll_canvas_analytics.bind("<Button-4>", lambda e: scroll_canvas_analytics.yview_scroll(-1, "units"))
        scroll_canvas_analytics.bind("<Button-5>", lambda e: scroll_canvas_analytics.yview_scroll(1, "units"))
        
        # Store reference to analytics scrollable frame for later use
        self.analytics_scrollable_frame = scrollable_frame_analytics
        
        # Build analytics tab content
        self.build_analytics_tab()
        
        # Use scrollable_frame_playback for playback tab widgets
        controls_panel_inner = scrollable_frame_playback
        
        # Video canvas(es) - single or side-by-side for comparison
        if self.comparison_mode:
            # Two canvases for side-by-side comparison
            canvas_frame = ttk.Frame(display_frame)
            canvas_frame.grid(row=0, column=0, sticky="nsew")
            
            self.canvas1 = tk.Canvas(canvas_frame, bg="black", cursor="crosshair")
            self.canvas1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            # Bind mouse events for zoom and pan
            self.canvas1.bind("<Button-1>", lambda e: self.on_canvas1_click(e))
            self.canvas1.bind("<B1-Motion>", lambda e: self.on_canvas1_drag(e))
            self.canvas1.bind("<ButtonRelease-1>", lambda e: self.on_canvas1_release(e))
            self.canvas1.bind("<MouseWheel>", lambda e: self.on_canvas1_wheel(e))
            self.canvas1.bind("<Button-4>", lambda e: self.on_canvas1_wheel(e))  # Linux
            self.canvas1.bind("<Button-5>", lambda e: self.on_canvas1_wheel(e))  # Linux
            
            self.canvas2 = tk.Canvas(canvas_frame, bg="black", cursor="crosshair")
            self.canvas2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            # Bind mouse events for zoom and pan
            self.canvas2.bind("<Button-1>", lambda e: self.on_canvas2_click(e))
            self.canvas2.bind("<B1-Motion>", lambda e: self.on_canvas2_drag(e))
            self.canvas2.bind("<ButtonRelease-1>", lambda e: self.on_canvas2_release(e))
            self.canvas2.bind("<MouseWheel>", lambda e: self.on_canvas2_wheel(e))
            self.canvas2.bind("<Button-4>", lambda e: self.on_canvas2_wheel(e))  # Linux
            self.canvas2.bind("<Button-5>", lambda e: self.on_canvas2_wheel(e))  # Linux
            
            # Labels for each frame
            label_frame = ttk.Frame(canvas_frame)
            label_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
            
            self.frame1_label = ttk.Label(label_frame, text="Frame: 0", font=("Arial", 10, "bold"))
            self.frame1_label.pack(side=tk.LEFT, padx=10)
            
            self.frame2_label = ttk.Label(label_frame, text="Frame: 0", font=("Arial", 10, "bold"))
            self.frame2_label.pack(side=tk.LEFT, padx=10)
            
            self.canvas = self.canvas1  # Keep for compatibility
        else:
            # Single canvas with zoom/pan support
            # Create a container frame for the canvas with explicit width constraint
            self.canvas_container = tk.Frame(display_frame, bg="black")  # Use regular Frame, not ttk
            self.canvas_container.grid(row=0, column=0, sticky="nsew")  # Expand to fill all available space
            self.canvas_container.grid_propagate(False)  # Prevent expansion beyond set width/height
            
            # Canvas container should expand to fill available space
            # Grid will handle the sizing automatically with column weights
            def update_canvas_width(event=None, force=False):
                """Update canvas width with throttling to prevent excessive updates"""
                try:
                    # Throttle resize events to avoid performance issues
                    if not force:
                        if self._resize_pending:
                            return  # Already have a pending resize
                        self._resize_pending = True
                        # Cancel any existing timer
                        if self._resize_timer:
                            self.root.after_cancel(self._resize_timer)
                        # Schedule update after a short delay
                        self._resize_timer = self.root.after(150, lambda: update_canvas_width(force=True))
                        return
                    
                    # Clear pending flag
                    self._resize_pending = False
                    self._resize_timer = None
                    
                    display_width = display_frame.winfo_width()
                    display_height = display_frame.winfo_height()
                    if display_width > 1 and display_height > 1:
                        # In fullscreen mode, use full width minus controls
                        if self.is_fullscreen:
                            # In fullscreen, controls are still visible but canvas gets more space
                            focused_panel_width = 300 if (hasattr(self, 'focused_panel') and self.focused_panel and 
                                                          hasattr(self, 'show_focused_player_panel') and 
                                                          self.show_focused_player_panel.get()) else 0
                            max_width = display_width - 400 - focused_panel_width - 15
                        else:
                            # Normal mode: total width - controls (400) - focused panel (300 if visible) - padding (15)
                            focused_panel_width = 300 if (hasattr(self, 'focused_panel') and self.focused_panel and 
                                                          hasattr(self, 'show_focused_player_panel') and 
                                                          self.show_focused_player_panel.get()) else 0
                            max_width = display_width - 400 - focused_panel_width - 15
                        
                        # Use full height of display_frame (minus any padding)
                        max_height = display_height - 10  # Small padding
                        
                        if max_width > 0 and max_height > 0:
                            # Only update if size actually changed
                            current_width = self.canvas_container.winfo_width()
                            current_height = self.canvas_container.winfo_height()
                            if abs(current_width - max_width) > 5 or abs(current_height - max_height) > 5:  # Only update if change is significant
                                self.canvas_container.configure(width=max_width, height=max_height)
                                # Invalidate cached canvas size when container resizes
                                self.cached_canvas_size = None
                                if self.current_frame_num == 0:
                                    print(f"📐 CANVAS CONTAINER: {max_width}x{max_height} (display: {display_width}x{display_height})")
                except:
                    pass
            
            # Store function for later use
            self._update_canvas_width = update_canvas_width
            
            # Bind to display_frame resize events
            display_frame.bind('<Configure>', update_canvas_width)
            
            # Invalidate cached canvas size on resize
            def invalidate_canvas_cache(event=None):
                self.cached_canvas_size = None
            display_frame.bind('<Configure>', invalidate_canvas_cache)
            
            # Run after initial render (only once, with force flag)
            self.root.after_idle(lambda: update_canvas_width(force=True))
            self.root.after(200, lambda: update_canvas_width(force=True))  # One delayed update for initial sizing
            
            self.canvas = tk.Canvas(self.canvas_container, bg="black", cursor="crosshair", highlightthickness=0)
            self.canvas.pack(fill=tk.BOTH, expand=True)
            # Bind mouse events for zoom and pan
            self.canvas.bind("<Button-1>", self.on_canvas_click)
            self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
            self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
            # Right-click pan (always available, even when not zoomed)
            self.canvas.bind("<Button-3>", self.on_canvas_right_click)
            self.canvas.bind("<B3-Motion>", self.on_canvas_right_drag)
            self.canvas.bind("<ButtonRelease-3>", self.on_canvas_right_release)
            self.canvas.bind("<MouseWheel>", self.on_canvas_wheel)
            self.canvas.bind("<Button-4>", self.on_canvas_wheel)  # Linux
            self.canvas.bind("<Button-5>", self.on_canvas_wheel)  # Linux
        
        # Use scrollable_frame_playback for playback tab widgets
        controls_panel_inner = scrollable_frame_playback
        
        # Note: Playback controls have been moved to horizontal bar above video display
        # (See playback_controls_bar created above the display_frame)
        
        # Zoom controls (for single frame mode only)
        if not self.comparison_mode:
            zoom_frame = ttk.LabelFrame(controls_panel_inner, text="Zoom & Pan", padding="10")
            zoom_frame.pack(fill=tk.X, pady=5)
            
            zoom_buttons_frame = ttk.Frame(zoom_frame)
            zoom_buttons_frame.pack(fill=tk.X, pady=2)
            ttk.Button(zoom_buttons_frame, text="🔍+", command=lambda: self.zoom_single(1.2), width=6).pack(side=tk.LEFT, padx=2)
            ttk.Button(zoom_buttons_frame, text="🔍-", command=lambda: self.zoom_single(1/1.2), width=6).pack(side=tk.LEFT, padx=2)
            ttk.Button(zoom_buttons_frame, text="Reset", command=self.reset_zoom_single, width=8).pack(side=tk.LEFT, padx=2)
            
            self.zoom_label = ttk.Label(zoom_frame, text="1.0x", font=("Arial", 9))
            self.zoom_label.pack(pady=2)
            ttk.Label(zoom_frame, text="Mouse wheel: zoom\nClick & drag: pan", 
                     font=("Arial", 7), foreground="gray").pack(pady=2)
        
        # Overlay controls
        overlay_frame = ttk.LabelFrame(controls_panel_inner, text="Overlays", padding="10")
        overlay_frame.pack(fill=tk.X, pady=5)
        self.overlay_frame = overlay_frame  # Store reference for warning label
        
        # Warning for analyzed videos (check after video is loaded)
        # This will be updated when video loads
        self.analyzed_video_warning = None
        
        # Players
        ttk.Checkbutton(overlay_frame, text="Show Players", 
                       variable=self.show_players,
                       command=self.update_display).pack(anchor=tk.W, pady=2)
        
        player_opts_frame = ttk.Frame(overlay_frame)
        player_opts_frame.pack(fill=tk.X, padx=20, pady=2)
        
        ttk.Checkbutton(player_opts_frame, text="Boxes", 
                       variable=self.show_player_boxes,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(player_opts_frame, text="Feet Markers (Circles)", 
                       variable=self.show_player_circles,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Label(player_opts_frame, text="  ⚠ Style controlled by 'Feet Marker Style & Effects' below", 
                 font=("Arial", 7), foreground="gray").pack(anchor=tk.W, padx=5)
        ttk.Checkbutton(player_opts_frame, text="Labels", 
                       variable=self.show_player_labels,
                       command=self.update_display).pack(anchor=tk.W)
        
        # Show raw YOLO detection boxes (before tracking)
        ttk.Checkbutton(overlay_frame, text="Show YOLO Detection Boxes (Raw)", 
                       variable=self.show_yolo_boxes,
                       command=self.update_display).pack(anchor=tk.W, pady=2, padx=20)
        ttk.Label(overlay_frame, text="(shows raw YOLO detections before tracking, in orange)", 
                 font=("Arial", 7), foreground="gray").pack(anchor=tk.W, padx=40)
        
        # Ball
        ttk.Checkbutton(overlay_frame, text="Show Ball", 
                       variable=self.show_ball,
                       command=self.update_display).pack(anchor=tk.W, pady=(10, 2))
        
        ball_opts_frame = ttk.Frame(overlay_frame)
        ball_opts_frame.pack(fill=tk.X, padx=20, pady=2)
        
        ttk.Checkbutton(ball_opts_frame, text="Trail", 
                       variable=self.show_ball_trail,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(ball_opts_frame, text="Label", 
                       variable=self.show_ball_label,
                       command=self.update_display).pack(anchor=tk.W)
        
        # Ball possession indicator
        ttk.Checkbutton(overlay_frame, text="Show Ball Possession", 
                       variable=self.show_ball_possession,
                       command=self.update_display).pack(anchor=tk.W, pady=(10, 2))
        
        # Player Trail (Breadcrumb Trail) - shows where players have traveled
        trail_frame = ttk.Frame(overlay_frame)
        trail_frame.pack(fill=tk.X, padx=20, pady=2)
        ttk.Checkbutton(trail_frame, text="Show Player Trail (Breadcrumbs)", 
                       variable=self.show_player_trail,
                       command=self.update_display).pack(anchor=tk.W)
        
        # Trail settings (only show if enabled)
        trail_settings_frame = ttk.Frame(trail_frame)
        trail_settings_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Trail length
        length_frame = ttk.Frame(trail_settings_frame)
        length_frame.pack(fill=tk.X, pady=1)
        ttk.Label(length_frame, text="Length:", width=12, anchor=tk.W).pack(side=tk.LEFT)
        trail_length_spin = ttk.Spinbox(length_frame, from_=5, to=100, increment=5,
                                       textvariable=self.player_trail_length, width=8,
                                       command=self.update_display)
        trail_length_spin.pack(side=tk.LEFT, padx=2)
        trail_length_spin.bind('<KeyRelease>', lambda e: self.update_display())
        ttk.Label(length_frame, text="(number of positions)", 
                 font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Trail size
        size_frame = ttk.Frame(trail_settings_frame)
        size_frame.pack(fill=tk.X, pady=1)
        ttk.Label(size_frame, text="Size (px):", width=12, anchor=tk.W).pack(side=tk.LEFT)
        trail_size_spin = ttk.Spinbox(size_frame, from_=2, to=10, increment=1,
                                     textvariable=self.player_trail_size, width=8,
                                     command=self.update_display)
        trail_size_spin.pack(side=tk.LEFT, padx=2)
        trail_size_spin.bind('<KeyRelease>', lambda e: self.update_display())
        
        # Fade option
        ttk.Checkbutton(trail_settings_frame, text="Fade older positions", 
                       variable=self.player_trail_fade,
                       command=self.update_display).pack(anchor=tk.W, pady=2)
        
        ttk.Label(trail_frame, text="(shows breadcrumb trail of where each player has traveled)", 
                 font=("Arial", 7), foreground="gray").pack(anchor=tk.W, padx=5, pady=(0, 2))
        
        # Lost Track Predictions (for tracks that disappear)
        predicted_frame = ttk.Frame(overlay_frame)
        predicted_frame.pack(fill=tk.X, padx=20, pady=2)
        ttk.Checkbutton(predicted_frame, text="Show Lost Track Predictions", 
                       variable=self.show_predicted_boxes,
                       command=self.update_display).pack(anchor=tk.W)
        
        # Prediction box settings (only show if enabled)
        pred_settings_frame = ttk.Frame(predicted_frame)
        pred_settings_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Duration
        duration_frame = ttk.Frame(pred_settings_frame)
        duration_frame.pack(fill=tk.X, pady=1)
        ttk.Label(duration_frame, text="Duration (s):", width=12, anchor=tk.W).pack(side=tk.LEFT)
        pred_duration_spin = ttk.Spinbox(duration_frame, from_=0.5, to=5.0, increment=0.1,
                                        textvariable=self.prediction_duration, width=8, format="%.1f",
                                        command=self.update_display)
        pred_duration_spin.pack(side=tk.LEFT, padx=2)
        pred_duration_spin.bind('<KeyRelease>', lambda e: self.update_display())
        
        # Style
        style_frame = ttk.Frame(pred_settings_frame)
        style_frame.pack(fill=tk.X, pady=1)
        ttk.Label(style_frame, text="Style:", width=12, anchor=tk.W).pack(side=tk.LEFT)
        pred_style_combo = ttk.Combobox(style_frame, textvariable=self.prediction_style,
                                       values=["dot", "box", "cross", "x", "arrow", "diamond"],
                                       state="readonly", width=12)
        pred_style_combo.pack(side=tk.LEFT, padx=2)
        pred_style_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        # Size
        size_frame = ttk.Frame(pred_settings_frame)
        size_frame.pack(fill=tk.X, pady=1)
        ttk.Label(size_frame, text="Size (px):", width=12, anchor=tk.W).pack(side=tk.LEFT)
        pred_size_spin = ttk.Spinbox(size_frame, from_=3, to=20, increment=1,
                                    textvariable=self.prediction_size, width=8,
                                    command=self.update_display)
        pred_size_spin.pack(side=tk.LEFT, padx=2)
        pred_size_spin.bind('<KeyRelease>', lambda e: self.update_display())
        
        ttk.Label(predicted_frame, text="(shows predicted positions for tracks that disappear off-screen)", 
                 font=("Arial", 7), foreground="gray").pack(anchor=tk.W, padx=5, pady=(0, 2))
        
        # Advanced overlays (if overlay metadata available)
        ttk.Checkbutton(overlay_frame, text="Show Trajectories", 
                       variable=self.show_trajectories,
                       command=self.update_display).pack(anchor=tk.W, pady=(10, 2))
        
        ttk.Checkbutton(overlay_frame, text="Show Field Zones", 
                       variable=self.show_field_zones,
                       command=self.update_display).pack(anchor=tk.W, pady=2)
        
        # Analytics overlay
        analytics_overlay_frame = ttk.Frame(overlay_frame)
        analytics_overlay_frame.pack(fill=tk.X, padx=20, pady=2)
        ttk.Checkbutton(analytics_overlay_frame, text="Show Analytics", 
                       variable=self.show_analytics,
                       command=self.update_display).pack(anchor=tk.W, pady=(10, 2))
        
        # Analytics Position (only show if analytics is enabled)
        analytics_pos_frame = ttk.Frame(analytics_overlay_frame)
        analytics_pos_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(analytics_pos_frame, text="Position:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        analytics_pos_combo = ttk.Combobox(analytics_pos_frame, textvariable=self.analytics_position,
                                          values=["with_player", "top_left", "top_right", "bottom_left", "bottom_right",
                                                 "top_banner", "bottom_banner", "left_bar", "right_bar"],
                                          state="readonly", width=18)
        analytics_pos_combo.pack(side=tk.LEFT, padx=2)
        analytics_pos_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        ttk.Label(analytics_pos_frame, text="(with_player=next to each player, or use banners/bars/corners)", 
                 font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Analytics banner/bar size controls
        analytics_size_frame = ttk.Frame(analytics_overlay_frame)
        analytics_size_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Banner height (for top/bottom banners)
        banner_height_frame = ttk.Frame(analytics_size_frame)
        banner_height_frame.pack(fill=tk.X, pady=1)
        ttk.Label(banner_height_frame, text="Banner Height (px):", width=18, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        banner_height_spin = ttk.Spinbox(banner_height_frame, from_=50, to=500, increment=10,
                                         textvariable=self.analytics_banner_height, width=8,
                                         command=self.update_display)
        banner_height_spin.pack(side=tk.LEFT, padx=2)
        banner_height_spin.bind('<KeyRelease>', lambda e: self.update_display())
        ttk.Label(banner_height_frame, text="(for top/bottom banners)", 
                 font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Bar width (for left/right bars)
        bar_width_frame = ttk.Frame(analytics_size_frame)
        bar_width_frame.pack(fill=tk.X, pady=1)
        ttk.Label(bar_width_frame, text="Bar Width (px):", width=18, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        bar_width_spin = ttk.Spinbox(bar_width_frame, from_=100, to=800, increment=10,
                                    textvariable=self.analytics_bar_width, width=8,
                                    command=self.update_display)
        bar_width_spin.pack(side=tk.LEFT, padx=2)
        bar_width_spin.bind('<KeyRelease>', lambda e: self.update_display())
        ttk.Label(bar_width_frame, text="(for left/right bars)", 
                 font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Panel size (for corner panels)
        panel_size_frame = ttk.Frame(analytics_size_frame)
        panel_size_frame.pack(fill=tk.X, pady=1)
        ttk.Label(panel_size_frame, text="Panel Width (px):", width=18, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        panel_width_spin = ttk.Spinbox(panel_size_frame, from_=150, to=600, increment=10,
                                      textvariable=self.analytics_panel_width, width=8,
                                      command=self.update_display)
        panel_width_spin.pack(side=tk.LEFT, padx=2)
        panel_width_spin.bind('<KeyRelease>', lambda e: self.update_display())
        
        ttk.Label(panel_size_frame, text="Height:", width=8, anchor=tk.W).pack(side=tk.LEFT, padx=(10, 2))
        panel_height_spin = ttk.Spinbox(panel_size_frame, from_=100, to=500, increment=10,
                                       textvariable=self.analytics_panel_height, width=8,
                                       command=self.update_display)
        panel_height_spin.pack(side=tk.LEFT, padx=2)
        panel_height_spin.bind('<KeyRelease>', lambda e: self.update_display())
        ttk.Label(panel_size_frame, text="(for corner panels)", 
                 font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Analytics Font Size Control
        analytics_font_frame = ttk.Frame(analytics_size_frame)
        analytics_font_frame.pack(fill=tk.X, pady=1)
        ttk.Label(analytics_font_frame, text="Analytics Font Size:", width=18, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        analytics_font_spin = ttk.Spinbox(analytics_font_frame, from_=0.3, to=4.0, increment=0.1,
                                         textvariable=self.analytics_font_scale, width=8, format="%.1f",
                                         command=self.update_display)
        analytics_font_spin.pack(side=tk.LEFT, padx=2)
        analytics_font_spin.bind('<KeyRelease>', lambda e: self.update_display())
        ttk.Label(analytics_font_frame, text="(0.3=small, 1.0=normal, 4.0=very large)", 
                 font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Analytics Font Thickness Control
        analytics_thickness_frame = ttk.Frame(analytics_size_frame)
        analytics_thickness_frame.pack(fill=tk.X, pady=1)
        ttk.Label(analytics_thickness_frame, text="Font Thickness:", width=18, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        analytics_thickness_spin = ttk.Spinbox(analytics_thickness_frame, from_=1, to=5, increment=1,
                                              textvariable=self.analytics_font_thickness, width=8,
                                              command=self.update_display)
        analytics_thickness_spin.pack(side=tk.LEFT, padx=2)
        analytics_thickness_spin.bind('<KeyRelease>', lambda e: self.update_display())
        ttk.Label(analytics_thickness_frame, text="(1=thin, 3=normal, 5=very thick, for better readability)", 
                 font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Analytics Color Controls
        analytics_color_check_frame = ttk.Frame(analytics_size_frame)
        analytics_color_check_frame.pack(fill=tk.X, pady=1)
        ttk.Checkbutton(analytics_color_check_frame, text="Use Custom Analytics Color", 
                       variable=self.use_custom_analytics_color, command=self.update_display).pack(side=tk.LEFT, padx=2)
        ttk.Label(analytics_color_check_frame, text="(for better contrast - white recommended)", 
                 font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Analytics Color - Color Picker
        analytics_color_rgb_frame = ttk.Frame(analytics_size_frame)
        analytics_color_rgb_frame.pack(fill=tk.X, pady=1)
        from color_picker_utils import create_color_picker_widget
        if not hasattr(self, 'analytics_color_rgb'):
            self.analytics_color_rgb = tk.StringVar(value="255,255,255")
        color_picker_frame, _ = create_color_picker_widget(
            analytics_color_rgb_frame,
            self.analytics_color_rgb,
            label_text="Color:",
            initial_color=(255, 255, 255),
            on_change_callback=lambda rgb: self.update_display()
        )
        color_picker_frame.pack(side=tk.LEFT, padx=2)
        ttk.Label(analytics_color_rgb_frame, text="(white for best contrast)", 
                 font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Visualization content moved to Visualization tab section (after viz_padding_frame is defined)
        
        # Perspective view (top-down/bird's-eye view)
        ttk.Separator(overlay_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        ttk.Checkbutton(overlay_frame, text="📐 Top-Down View (Perspective)", 
                       variable=self.show_perspective_view,
                       command=self.toggle_perspective_view).pack(anchor=tk.W, pady=2)
        self.perspective_info_label = ttk.Label(overlay_frame, 
                                                text="Requires field calibration",
                                                font=("Arial", 7), 
                                                foreground="gray")
        self.perspective_info_label.pack(anchor=tk.W, padx=20)
        
        # Pixel measurement tool
        measurement_frame = ttk.LabelFrame(overlay_frame, text="📏 Pixel Measurement Tool", padding="10")
        measurement_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(measurement_frame, text="Enable Measurement Tool", 
                       variable=self.measurement_mode,
                       command=self.toggle_measurement_mode).pack(anchor=tk.W, pady=2)
        
        # Measurement type selector
        type_frame = ttk.Frame(measurement_frame)
        type_frame.pack(fill=tk.X, pady=5)
        ttk.Label(type_frame, text="Mode:").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Line (Distance)", variable=self.measurement_type,
                       value="line", command=self.update_measurement_info).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Box (Area)", variable=self.measurement_type,
                       value="box", command=self.update_measurement_info).pack(side=tk.LEFT, padx=5)
        
        self.measurement_info_label = ttk.Label(measurement_frame, 
                                                 text="Click & drag on video to measure",
                                                 font=("Arial", 8), 
                                                 foreground="gray")
        self.measurement_info_label.pack(anchor=tk.W, padx=5, pady=2)
        self.measurement_result_label = ttk.Label(measurement_frame, 
                                                  text="",
                                                  font=("Arial", 9, "bold"), 
                                                  foreground="blue")
        self.measurement_result_label.pack(anchor=tk.W, padx=5, pady=(2, 0))
        
        # Focused Player Mode
        ttk.Checkbutton(overlay_frame, text="Focused Player Mode", 
                       variable=self.show_focused_player_panel,
                       command=self.toggle_focused_player_panel).pack(anchor=tk.W, pady=(10, 2))
        
        # Zoom controls (only in comparison mode)
        if self.comparison_mode:
            zoom_frame = ttk.LabelFrame(controls_panel_inner, text="Zoom Controls", padding="10")
            zoom_frame.pack(fill=tk.X, pady=5)
            
            # Zoom for left view (canvas1)
            ttk.Label(zoom_frame, text="Left View:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 2))
            zoom1_frame = ttk.Frame(zoom_frame)
            zoom1_frame.pack(fill=tk.X, pady=2)
            ttk.Button(zoom1_frame, text="🔍+", command=lambda: self.zoom_canvas(1, 1.2), width=6).pack(side=tk.LEFT, padx=2)
            ttk.Button(zoom1_frame, text="🔍-", command=lambda: self.zoom_canvas(1, 1/1.2), width=6).pack(side=tk.LEFT, padx=2)
            ttk.Button(zoom1_frame, text="Reset", command=lambda: self.reset_zoom(1), width=6).pack(side=tk.LEFT, padx=2)
            self.zoom_label1 = ttk.Label(zoom1_frame, text="1.0x", font=("Arial", 8))
            self.zoom_label1.pack(side=tk.LEFT, padx=5)
            ttk.Label(zoom_frame, text="(Mouse wheel to zoom, drag to pan)", font=("Arial", 7), foreground="gray").pack(anchor=tk.W, pady=(0, 5))
            
            # Zoom for right view (canvas2)
            ttk.Label(zoom_frame, text="Right View:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(5, 2))
            zoom2_frame = ttk.Frame(zoom_frame)
            zoom2_frame.pack(fill=tk.X, pady=2)
            ttk.Button(zoom2_frame, text="🔍+", command=lambda: self.zoom_canvas(2, 1.2), width=6).pack(side=tk.LEFT, padx=2)
            ttk.Button(zoom2_frame, text="🔍-", command=lambda: self.zoom_canvas(2, 1/1.2), width=6).pack(side=tk.LEFT, padx=2)
            ttk.Button(zoom2_frame, text="Reset", command=lambda: self.reset_zoom(2), width=6).pack(side=tk.LEFT, padx=2)
            self.zoom_label2 = ttk.Label(zoom2_frame, text="1.0x", font=("Arial", 8))
            self.zoom_label2.pack(side=tk.LEFT, padx=5)
            ttk.Label(zoom_frame, text="(Mouse wheel to zoom, drag to pan)", font=("Arial", 7), foreground="gray").pack(anchor=tk.W)
        else:
            # Initialize zoom labels to None for single frame mode (not used)
            self.zoom_label1 = None
            self.zoom_label2 = None
        
        # ========== VISUALIZATION TAB ==========
        # Visualization controls in separate tab
        # Add padding container frame to maintain spacing
        viz_padding_frame = ttk.Frame(scrollable_frame_viz, padding="5")
        viz_padding_frame.pack(fill=tk.BOTH, expand=True)
        
        # Visualization Settings Title
        viz_title_frame = ttk.LabelFrame(viz_padding_frame, text="Visualization Settings", padding="10")
        viz_title_frame.pack(fill=tk.X, pady=5)
        ttk.Label(viz_title_frame, text="These settings control HOW overlays are styled. Enable overlays in 'Playback & Overlays' tab first.", 
                 font=("Arial", 8), foreground="gray", wraplength=350).pack(anchor=tk.W, pady=2)
        
        # Feet Marker Style & Effects
        feet_marker_frame = ttk.LabelFrame(viz_padding_frame, text="Feet Marker Style & Effects", padding="5")
        feet_marker_frame.pack(fill=tk.X, pady=5)
        
        # Feet Marker Style
        style_frame = ttk.Frame(feet_marker_frame)
        style_frame.pack(fill=tk.X, pady=2)
        ttk.Label(style_frame, text="Style:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        style_combo = ttk.Combobox(style_frame, textvariable=self.feet_marker_style,
                                   values=["circle", "ellipse", "diamond", "star", "hexagon", "ring", "glow", "pulse", "arrow", "none"],
                                   state="readonly", width=15)
        style_combo.pack(side=tk.LEFT, padx=2)
        style_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        # Feet Marker Opacity
        opacity_frame = ttk.Frame(feet_marker_frame)
        opacity_frame.pack(fill=tk.X, pady=2)
        ttk.Label(opacity_frame, text="Opacity:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        opacity_spin = ttk.Spinbox(opacity_frame, from_=0, to=255, increment=5,
                                   textvariable=self.feet_marker_opacity, width=8, command=self.update_display)
        opacity_spin.pack(side=tk.LEFT, padx=2)
        opacity_spin.bind('<KeyRelease>', lambda e: self.update_display())
        
        # Feet Marker Effects
        ttk.Label(feet_marker_frame, text="Effects:", font=("Arial", 8, "bold")).pack(anchor=tk.W, pady=(5, 2))
        
        # Glow
        glow_frame = ttk.Frame(feet_marker_frame)
        glow_frame.pack(fill=tk.X, pady=1)
        ttk.Checkbutton(glow_frame, text="Glow", variable=self.feet_marker_enable_glow,
                       command=self.update_display).pack(side=tk.LEFT, padx=2)
        ttk.Label(glow_frame, text="Intensity:").pack(side=tk.LEFT, padx=(10, 2))
        glow_intensity = ttk.Spinbox(glow_frame, from_=0, to=100, increment=5,
                                     textvariable=self.feet_marker_glow_intensity, width=6, command=self.update_display)
        glow_intensity.pack(side=tk.LEFT, padx=2)
        glow_intensity.bind('<KeyRelease>', lambda e: self.update_display())
        
        # Shadow
        shadow_frame = ttk.Frame(feet_marker_frame)
        shadow_frame.pack(fill=tk.X, pady=1)
        ttk.Checkbutton(shadow_frame, text="Shadow", variable=self.feet_marker_enable_shadow,
                       command=self.update_display).pack(side=tk.LEFT, padx=2)
        ttk.Label(shadow_frame, text="Offset:").pack(side=tk.LEFT, padx=(10, 2))
        shadow_offset = ttk.Spinbox(shadow_frame, from_=1, to=10, increment=1,
                                   textvariable=self.feet_marker_shadow_offset, width=6, command=self.update_display)
        shadow_offset.pack(side=tk.LEFT, padx=2)
        shadow_offset.bind('<KeyRelease>', lambda e: self.update_display())
        ttk.Label(shadow_frame, text="Opacity:").pack(side=tk.LEFT, padx=(5, 2))
        shadow_opacity = ttk.Spinbox(shadow_frame, from_=0, to=255, increment=10,
                                    textvariable=self.feet_marker_shadow_opacity, width=6, command=self.update_display)
        shadow_opacity.pack(side=tk.LEFT, padx=2)
        shadow_opacity.bind('<KeyRelease>', lambda e: self.update_display())
        
        # Gradient, Pulse, Particles
        ttk.Checkbutton(feet_marker_frame, text="Gradient Fill", variable=self.feet_marker_enable_gradient,
                       command=self.update_display).pack(anchor=tk.W, pady=1)
        
        pulse_frame = ttk.Frame(feet_marker_frame)
        pulse_frame.pack(fill=tk.X, pady=1)
        ttk.Checkbutton(pulse_frame, text="Pulse", variable=self.feet_marker_enable_pulse,
                       command=self.update_display).pack(side=tk.LEFT, padx=2)
        ttk.Label(pulse_frame, text="Speed:").pack(side=tk.LEFT, padx=(10, 2))
        pulse_speed = ttk.Spinbox(pulse_frame, from_=0.5, to=5.0, increment=0.1,
                                 textvariable=self.feet_marker_pulse_speed, width=6, format="%.1f", command=self.update_display)
        pulse_speed.pack(side=tk.LEFT, padx=2)
        pulse_speed.bind('<KeyRelease>', lambda e: self.update_display())
        
        particle_frame = ttk.Frame(feet_marker_frame)
        particle_frame.pack(fill=tk.X, pady=1)
        ttk.Checkbutton(particle_frame, text="Particles", variable=self.feet_marker_enable_particles,
                       command=self.update_display).pack(side=tk.LEFT, padx=2)
        ttk.Label(particle_frame, text="Count:").pack(side=tk.LEFT, padx=(10, 2))
        particle_count = ttk.Spinbox(particle_frame, from_=3, to=20, increment=1,
                                     textvariable=self.feet_marker_particle_count, width=6, command=self.update_display)
        particle_count.pack(side=tk.LEFT, padx=2)
        particle_count.bind('<KeyRelease>', lambda e: self.update_display())
        
        # Vertical Offset
        offset_frame = ttk.Frame(feet_marker_frame)
        offset_frame.pack(fill=tk.X, pady=2)
        ttk.Label(offset_frame, text="Vertical Offset:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        vertical_offset_spin = ttk.Spinbox(offset_frame, from_=-50, to=50, increment=1,
                                          textvariable=self.feet_marker_vertical_offset, width=8, command=self.update_display)
        vertical_offset_spin.pack(side=tk.LEFT, padx=2)
        vertical_offset_spin.bind('<KeyRelease>', lambda e: self.update_display())
        ttk.Label(offset_frame, text="px (negative=above, positive=below)", font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Ellipse Settings (for foot-based tracking)
        ellipse_frame = ttk.LabelFrame(viz_padding_frame, text="Ellipse Settings (Foot Markers)", padding="5")
        ellipse_frame.pack(fill=tk.X, pady=5)
        
        ellipse_width_frame = ttk.Frame(ellipse_frame)
        ellipse_width_frame.pack(fill=tk.X, pady=2)
        ttk.Label(ellipse_width_frame, text="Width (px):", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        ellipse_width_spin = ttk.Spinbox(ellipse_width_frame, from_=10, to=50, increment=2,
                                         textvariable=self.ellipse_width, width=8, command=self.update_display)
        ellipse_width_spin.pack(side=tk.LEFT, padx=2)
        ellipse_width_spin.bind('<KeyRelease>', lambda e: self.update_display())
        
        ellipse_height_frame = ttk.Frame(ellipse_frame)
        ellipse_height_frame.pack(fill=tk.X, pady=2)
        ttk.Label(ellipse_height_frame, text="Height (px):", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        ellipse_height_spin = ttk.Spinbox(ellipse_height_frame, from_=6, to=30, increment=2,
                                         textvariable=self.ellipse_height, width=8, command=self.update_display)
        ellipse_height_spin.pack(side=tk.LEFT, padx=2)
        ellipse_height_spin.bind('<KeyRelease>', lambda e: self.update_display())
        
        ellipse_outline_frame = ttk.Frame(ellipse_frame)
        ellipse_outline_frame.pack(fill=tk.X, pady=2)
        ttk.Label(ellipse_outline_frame, text="Outline (px):", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        ellipse_outline_spin = ttk.Spinbox(ellipse_outline_frame, from_=0, to=10, increment=1,
                                          textvariable=self.ellipse_outline_thickness, width=8, command=self.update_display)
        ellipse_outline_spin.pack(side=tk.LEFT, padx=2)
        ellipse_outline_spin.bind('<KeyRelease>', lambda e: self.update_display())
        ttk.Label(ellipse_outline_frame, text="(0 = no border)", font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Box Settings
        box_frame = ttk.LabelFrame(viz_padding_frame, text="Box Settings", padding="5")
        box_frame.pack(fill=tk.X, pady=5)
        
        shrink_frame = ttk.Frame(box_frame)
        shrink_frame.pack(fill=tk.X, pady=2)
        ttk.Label(shrink_frame, text="Shrink Factor:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        shrink_spin = ttk.Spinbox(shrink_frame, from_=0.0, to=0.5, increment=0.05,
                                 textvariable=self.box_shrink_factor, width=8, format="%.2f", command=self.update_display)
        shrink_spin.pack(side=tk.LEFT, padx=2)
        shrink_spin.bind('<KeyRelease>', lambda e: self.update_display())
        
        thickness_frame = ttk.Frame(box_frame)
        thickness_frame.pack(fill=tk.X, pady=2)
        ttk.Label(thickness_frame, text="Thickness:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        thickness_spin = ttk.Spinbox(thickness_frame, from_=1, to=10, increment=1,
                                     textvariable=self.box_thickness, width=8, command=self.update_display)
        thickness_spin.pack(side=tk.LEFT, padx=2)
        thickness_spin.bind('<KeyRelease>', lambda e: self.update_display())
        
        alpha_frame = ttk.Frame(box_frame)
        alpha_frame.pack(fill=tk.X, pady=2)
        ttk.Label(alpha_frame, text="Fill Opacity:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        alpha_spin = ttk.Spinbox(alpha_frame, from_=0, to=255, increment=10,
                                textvariable=self.player_viz_alpha, width=8, command=self.update_display)
        alpha_spin.pack(side=tk.LEFT, padx=2)
        alpha_spin.bind('<KeyRelease>', lambda e: self.update_display())
        
        ttk.Checkbutton(box_frame, text="Use Custom Box Color", variable=self.use_custom_box_color,
                       command=self.update_display).pack(anchor=tk.W, pady=2)
        
        box_color_frame = ttk.Frame(box_frame)
        box_color_frame.pack(fill=tk.X, padx=20, pady=2)
        
        # Use color picker instead of spinboxes
        from color_picker_utils import create_color_picker_widget
        color_picker_frame, _ = create_color_picker_widget(
            box_color_frame,
            self.box_color_rgb,
            label_text="Box Color:",
            initial_color=(0, 255, 0),
            on_change_callback=lambda rgb: self.update_display()
        )
        color_picker_frame.pack(side=tk.LEFT, padx=2)
        
        # Sync individual R, G, B components with RGB string
        # Use a flag to prevent circular updates
        self._syncing_box_color = False
        
        def sync_rgb_from_components(*args):
            """Update RGB string when individual components change"""
            if self._syncing_box_color:
                return
            try:
                r = self.box_color_r.get()
                g = self.box_color_g.get()
                b = self.box_color_b.get()
                self._syncing_box_color = True
                self.box_color_rgb.set(f"{r},{g},{b}")
                self._syncing_box_color = False
            except:
                self._syncing_box_color = False
        
        self.box_color_r.trace('w', sync_rgb_from_components)
        self.box_color_g.trace('w', sync_rgb_from_components)
        self.box_color_b.trace('w', sync_rgb_from_components)
        
        # Sync individual components from RGB string
        def sync_components_from_rgb(*args):
            """Update individual components when RGB string changes"""
            if self._syncing_box_color:
                return
            try:
                from color_picker_utils import rgb_string_to_tuple
                r, g, b = rgb_string_to_tuple(self.box_color_rgb.get(), default=(0, 255, 0))
                self._syncing_box_color = True
                self.box_color_r.set(r)
                self.box_color_g.set(g)
                self.box_color_b.set(b)
                self._syncing_box_color = False
            except:
                self._syncing_box_color = False
        
        self.box_color_rgb.trace_add('write', sync_components_from_rgb)
        
        # Player Labels
        label_frame = ttk.LabelFrame(viz_padding_frame, text="Player Labels", padding="5")
        label_frame.pack(fill=tk.X, pady=5)
        
        label_type_frame = ttk.Frame(label_frame)
        label_type_frame.pack(fill=tk.X, pady=2)
        ttk.Label(label_type_frame, text="Label Type:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        label_type_combo = ttk.Combobox(label_type_frame, textvariable=self.label_type,
                                        values=["full_name", "last_name", "jersey", "team", "custom"],
                                        state="readonly", width=15)
        label_type_combo.pack(side=tk.LEFT, padx=2)
        label_type_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        font_frame = ttk.Frame(label_frame)
        font_frame.pack(fill=tk.X, pady=2)
        ttk.Label(font_frame, text="Font Face:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        font_face_combo = ttk.Combobox(font_frame, textvariable=self.label_font_face,
                                      values=["FONT_HERSHEY_SIMPLEX", "FONT_HERSHEY_PLAIN", "FONT_HERSHEY_DUPLEX",
                                             "FONT_HERSHEY_COMPLEX", "FONT_HERSHEY_TRIPLEX", "FONT_HERSHEY_COMPLEX_SMALL",
                                             "FONT_HERSHEY_SCRIPT_SIMPLEX", "FONT_HERSHEY_SCRIPT_COMPLEX"],
                                      state="readonly", width=20)
        font_face_combo.pack(side=tk.LEFT, padx=2)
        font_face_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        font_scale_frame = ttk.Frame(label_frame)
        font_scale_frame.pack(fill=tk.X, pady=2)
        ttk.Label(font_scale_frame, text="Font Size:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=2)
        font_scale_spin = ttk.Spinbox(font_scale_frame, from_=0.3, to=2.0, increment=0.1,
                                     textvariable=self.label_font_scale, width=8, format="%.1f", command=self.update_display)
        font_scale_spin.pack(side=tk.LEFT, padx=2)
        font_scale_spin.bind('<KeyRelease>', lambda e: self.update_display())
        
        ttk.Checkbutton(label_frame, text="Use Custom Label Color", variable=self.use_custom_label_color,
                       command=self.update_display).pack(anchor=tk.W, pady=2)
        
        label_color_frame = ttk.Frame(label_frame)
        label_color_frame.pack(fill=tk.X, padx=20, pady=2)
        
        # Use color picker instead of spinboxes
        from color_picker_utils import create_color_picker_widget
        color_picker_frame, _ = create_color_picker_widget(
            label_color_frame,
            self.label_color_rgb,
            label_text="Label Color:",
            initial_color=(255, 255, 255),
            on_change_callback=lambda rgb: self.update_display()
        )
        color_picker_frame.pack(side=tk.LEFT, padx=2)
        
        # Sync individual R, G, B components with RGB string for labels
        self._syncing_label_color = False
        
        def sync_label_rgb_from_components(*args):
            """Update RGB string when individual label components change"""
            if self._syncing_label_color:
                return
            try:
                r = self.label_color_r.get()
                g = self.label_color_g.get()
                b = self.label_color_b.get()
                self._syncing_label_color = True
                self.label_color_rgb.set(f"{r},{g},{b}")
                self._syncing_label_color = False
            except:
                self._syncing_label_color = False
        
        self.label_color_r.trace('w', sync_label_rgb_from_components)
        self.label_color_g.trace('w', sync_label_rgb_from_components)
        self.label_color_b.trace('w', sync_label_rgb_from_components)
        
        # Sync individual components from RGB string for labels
        def sync_label_components_from_rgb(*args):
            """Update individual label components when RGB string changes"""
            if self._syncing_label_color:
                return
            try:
                from color_picker_utils import rgb_string_to_tuple
                r, g, b = rgb_string_to_tuple(self.label_color_rgb.get(), default=(255, 255, 255))
                self._syncing_label_color = True
                self.label_color_r.set(r)
                self.label_color_g.set(g)
                self.label_color_b.set(b)
                self._syncing_label_color = False
            except:
                self._syncing_label_color = False
        
        self.label_color_rgb.trace_add('write', sync_label_components_from_rgb)
        
        # ========== ANALYTICS TAB ==========
        # Analytics controls in separate tab
        # Add padding container frame to maintain spacing
        analytics_padding_frame = ttk.Frame(scrollable_frame_analytics, padding="5")
        analytics_padding_frame.pack(fill=tk.BOTH, expand=True, padx=0)
        analytics_panel_inner = analytics_padding_frame
        
        # Analytics toggle
        analytics_toggle_frame = ttk.LabelFrame(analytics_panel_inner, text="Analytics Display", padding="10")
        analytics_toggle_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(analytics_toggle_frame, text="Show Analytics", 
                       variable=self.show_analytics,
                       command=self.update_display).pack(anchor=tk.W, pady=2)
        
        ttk.Label(analytics_toggle_frame, text="Select which analytics to display:", 
                 font=("Arial", 9)).pack(anchor=tk.W, pady=(10, 5))
        
        ttk.Button(analytics_toggle_frame, text="Select Analytics...", 
                  command=self.open_analytics_selection, width=20).pack(anchor=tk.W, pady=5)
        
        # Show current selections
        self.analytics_selections_label = ttk.Label(analytics_toggle_frame, 
                                                    text="No analytics selected", 
                                                    font=("Arial", 8), 
                                                    foreground="gray",
                                                    wraplength=350)
        self.analytics_selections_label.pack(anchor=tk.W, pady=5)
        
        # Analytics info
        info_frame = ttk.LabelFrame(analytics_panel_inner, text="Info", padding="10")
        info_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(info_frame, 
                 text="Analytics are displayed as text labels on players when enabled.\n"
                      "Use 'Select Analytics...' to choose which metrics to show.",
                 font=("Arial", 8),
                 foreground="gray",
                 justify=tk.LEFT,
                 wraplength=350).pack(anchor=tk.W, pady=2)
        
        # Event tracking controls
        if self.event_tracker:
            event_frame = ttk.LabelFrame(controls_panel_inner, text="Event Tracking", padding="10")
            event_frame.pack(fill=tk.X, pady=5)
            
            ttk.Button(event_frame, text="📊 Event Timeline", 
                      command=self.open_event_timeline).pack(fill=tk.X, pady=2)
            ttk.Button(event_frame, text="💾 Save Events", 
                      command=self.save_events).pack(fill=tk.X, pady=2)
            
            # Event shortcuts info
            shortcuts_text = (
                "Shortcuts:\n"
                "G - Goal\n"
                "S - Shot\n"
                "P - Pass\n"
                "F - Foul\n"
                "C - Corner\n"
                "K - Free Kick\n"
                "V - Save\n"
                "T - Tackle\n"
                "U - Substitution\n"
                "X - Custom Event"
            )
            ttk.Label(event_frame, text=shortcuts_text, 
                     font=("Arial", 8), foreground="gray",
                     justify=tk.LEFT).pack(anchor=tk.W, pady=5)
        
        # Event Marker System controls
        marker_frame = ttk.LabelFrame(controls_panel_inner, text="Event Markers", padding="10")
        marker_frame.pack(fill=tk.X, pady=5)
        
        # Event type selector
        ttk.Label(marker_frame, text="Event Type:").pack(anchor=tk.W, pady=2)
        event_type_combo = ttk.Combobox(marker_frame, textvariable=self.current_event_type,
                                       values=["pass", "shot", "goal", "tackle", "save", "corner", 
                                              "free_kick", "penalty", "offside", "custom"],
                                       state="readonly", width=15)
        event_type_combo.pack(fill=tk.X, pady=2)
        
        # Marker buttons
        marker_buttons_frame = ttk.Frame(marker_frame)
        marker_buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(marker_buttons_frame, text="➕ Mark Event", 
                  command=self.mark_event_at_current_frame).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(marker_buttons_frame, text="➖ Remove", 
                  command=self.remove_event_at_current_frame).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # Marker visibility toggle
        ttk.Checkbutton(marker_frame, text="Show Markers on Timeline", 
                       variable=self.event_marker_visible,
                       command=self.update_timeline_display).pack(anchor=tk.W, pady=2)
        
        # Marker management buttons
        marker_mgmt_frame = ttk.Frame(marker_frame)
        marker_mgmt_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(marker_mgmt_frame, text="💾 Save Markers", 
                  command=self.save_event_markers).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(marker_mgmt_frame, text="📂 Load Markers", 
                  command=self.load_event_markers).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(marker_mgmt_frame, text="🗑️ Clear All", 
                  command=self.clear_all_event_markers).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # Marker statistics
        self.marker_stats_label = ttk.Label(marker_frame, text="Markers: 0", 
                                           font=("Arial", 8), foreground="gray")
        self.marker_stats_label.pack(anchor=tk.W, pady=2)
        
        # Bind keyboard shortcuts
        self.root.bind('<space>', lambda e: self.toggle_playback())
        self.root.bind('<Left>', lambda e: self.prev_frame())
        self.root.bind('<Right>', lambda e: self.next_frame())
        
        # Event tracking keyboard shortcuts
        if self.event_tracker:
            self.root.bind('<KeyPress-g>', lambda e: self.mark_event('goal'))
            self.root.bind('<KeyPress-G>', lambda e: self.mark_event('goal'))
            self.root.bind('<KeyPress-s>', lambda e: self.mark_event('shot'))
            self.root.bind('<KeyPress-S>', lambda e: self.mark_event('shot'))
            self.root.bind('<KeyPress-p>', lambda e: self.mark_event('pass'))
            self.root.bind('<KeyPress-P>', lambda e: self.mark_event('pass'))
            self.root.bind('<KeyPress-f>', lambda e: self.mark_event('foul'))
            self.root.bind('<KeyPress-F>', lambda e: self.mark_event('foul'))
            self.root.bind('<KeyPress-c>', lambda e: self.mark_event('corner'))
            self.root.bind('<KeyPress-C>', lambda e: self.mark_event('corner'))
            self.root.bind('<KeyPress-k>', lambda e: self.mark_event('free_kick'))
            self.root.bind('<KeyPress-K>', lambda e: self.mark_event('free_kick'))
            self.root.bind('<KeyPress-v>', lambda e: self.mark_event('save'))
            self.root.bind('<KeyPress-V>', lambda e: self.mark_event('save'))
            self.root.bind('<KeyPress-t>', lambda e: self.mark_event('tackle'))
            self.root.bind('<KeyPress-T>', lambda e: self.mark_event('tackle'))
            self.root.bind('<KeyPress-u>', lambda e: self.mark_event('substitution'))
            self.root.bind('<KeyPress-U>', lambda e: self.mark_event('substitution'))
            self.root.bind('<KeyPress-x>', lambda e: self.mark_event('custom'))
            self.root.bind('<KeyPress-X>', lambda e: self.mark_event('custom'))
        
        self.root.focus_set()
        
    def load_configs(self):
        """Load team colors and player names"""
        # Load team colors
        if os.path.exists("team_color_config.json"):
            try:
                with open("team_color_config.json", 'r') as f:
                    self.team_colors = json.load(f)
            except:
                pass
        
        # Load player names
        if os.path.exists("player_names.json"):
            try:
                with open("player_names.json", 'r') as f:
                    self.player_names = json.load(f)
            except:
                pass
    
    def load_video(self, video_path=None):
        """Load video file (runs in background thread to prevent GUI freeze)"""
        if video_path is None:
            filename = filedialog.askopenfilename(
                title="Select Video File",
                filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v"), ("All files", "*.*")]
            )
            if not filename:
                return
            self.video_path = filename
        else:
            filename = video_path
            self.video_path = video_path
        
        # Show progress window
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Loading Video...")
        progress_window.geometry("400x100")
        progress_window.transient(self.root)
        progress_window.grab_set()
        progress_window.resizable(False, False)
        
        progress_label = ttk.Label(progress_window, text=f"Loading video: {os.path.basename(filename)}", font=("Arial", 10))
        progress_label.pack(pady=10)
        
        progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
        progress_bar.pack(pady=5, padx=20, fill=tk.X)
        progress_bar.start()
        
        def load_video_thread():
            """Load video in background thread"""
            try:
                self._load_video_worker(filename)
                # Update UI on main thread
                self.root.after(0, lambda: self._on_video_loaded(progress_window))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self._on_video_load_error(progress_window, error_msg))
        
        # Start loading in background thread
        thread = threading.Thread(target=load_video_thread, daemon=True)
        thread.start()
    
    def _load_video_worker(self, filename):
        """Worker function to load video (runs in background thread)"""
        # Try to use hardware-accelerated video decoding (NVIDIA GPU)
        # On Windows, try Media Foundation backend first (best hardware acceleration support on Windows 10+)
        # Then try DirectShow, then fall back to default backend
        cap = None
        backend_used = "default"
        
        # Try Media Foundation backend (Windows 10+, best hardware acceleration)
        try:
            if hasattr(cv2, 'CAP_MSMF'):
                cap = cv2.VideoCapture(filename, cv2.CAP_MSMF)
                if cap.isOpened():
                    backend_used = "Media Foundation (MSMF)"
                    print("✓ Using Media Foundation backend (supports hardware acceleration)")
        except:
            pass
        
        # If MSMF failed, try DirectShow backend
        if cap is None or not cap.isOpened():
            try:
                if cap:
                    cap.release()
                cap = cv2.VideoCapture(filename, cv2.CAP_DSHOW)
                if cap.isOpened():
                    backend_used = "DirectShow"
                    print("✓ Using DirectShow backend")
            except:
                pass
        
        # Final fallback to default backend
        if cap is None or not cap.isOpened():
            if cap:
                cap.release()
            cap = cv2.VideoCapture(filename)
            backend_used = "default"
            print("✓ Using default backend")
        
        # Check if video opened successfully
        if not cap or not cap.isOpened():
            error_msg = f"Could not open video: {filename}\n\nPossible reasons:\n• File is corrupted\n• Codec not supported\n• File path is invalid\n• File is being used by another program"
            raise Exception(error_msg)
        
        # Store cap in instance (safe to do from worker thread)
        self.cap = cap
        
        # Get video properties (safe to do from worker thread)
        # CRITICAL FIX: Ensure FPS is valid (some videos report incorrect FPS)
        detected_fps = self.cap.get(cv2.CAP_PROP_FPS)
        if detected_fps is None or detected_fps <= 0 or not np.isfinite(detected_fps):
            # Fallback to 30fps if detection fails
            detected_fps = 30.0
            print(f"⚠ Video FPS detection failed or invalid, using default 30fps")
        else:
            # Validate FPS is in reasonable range (5-120fps)
            if detected_fps < 5.0:
                print(f"⚠ Video FPS ({detected_fps:.2f}) seems too low, using 30fps default")
                detected_fps = 30.0
            elif detected_fps > 120.0:
                print(f"⚠ Video FPS ({detected_fps:.2f}) seems too high, capping at 120fps")
                detected_fps = 120.0
        self.fps = float(detected_fps)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # Store original video dimensions (before any transforms) for coordinate scaling
        self.original_video_width = self.width
        self.original_video_height = self.height
        
        # Initialize event tracker now that we have FPS
        if not self.event_tracker and self.video_path:
            self.event_tracker = EventTracker(self.video_path, self.fps)
            # Try to load existing events
            base_name = os.path.splitext(os.path.basename(self.video_path))[0]
            output_dir = os.path.dirname(self.video_path) or "."
            json_path = os.path.join(output_dir, f"{base_name}_events.json")
            if os.path.exists(json_path):
                self.event_tracker.load_events(json_path=json_path)
                print(f"✓ Loaded {len(self.event_tracker.events)} existing events")
        
        # Log detected FPS for debugging
        print(f"✓ Video loaded: {self.total_frames} frames @ {self.fps:.2f}fps ({self.width}x{self.height})")
        
        # Initialize event tracker now that we have FPS (safe in worker thread)
        if not self.event_tracker and self.video_path:
            self.event_tracker = EventTracker(self.video_path, self.fps)
            # Try to load existing events
            base_name = os.path.splitext(os.path.basename(self.video_path))[0]
            output_dir = os.path.dirname(self.video_path) or "."
            json_path = os.path.join(output_dir, f"{base_name}_events.json")
            if os.path.exists(json_path):
                self.event_tracker.load_events(json_path=json_path)
                print(f"✓ Loaded {len(self.event_tracker.events)} existing events")
    
    def _on_video_loaded(self, progress_window):
        """Callback when video is successfully loaded (runs on main thread)"""
        try:
            progress_window.destroy()
        except:
            pass
        
        # All UI updates happen here (on main thread)
        # Video properties are already set by worker thread
        # Clear and reset frame buffer for new video
        self.clear_frame_buffer()
        
        # Pre-load first few frames into buffer
        self._preload_initial_frames()
        
        # Start buffering thread
        self.start_buffer_thread()
        
        # Load field calibration for perspective view (after video dimensions are set)
        self.root.after(100, self.load_field_calibration)
        
        # Update UI widgets
        try:
            if hasattr(self, 'frame_slider') and self.frame_slider.winfo_exists():
                self.frame_slider.config(to=max(1, self.total_frames - 1))
                self.frame_var.set(0)
        except (tk.TclError, AttributeError):
            pass
        
        self.current_frame_num = 0
        
        try:
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.status_label.config(text=f"Video: {os.path.basename(self.video_path)} ({self.total_frames} frames @ {self.fps:.1f}fps)")
        except (tk.TclError, AttributeError):
            pass
        
        # Check if video is already analyzed and show warning
        video_basename = os.path.basename(self.video_path).lower()
        is_analyzed = "_analyzed" in video_basename or "_overlay" in video_basename
        if is_analyzed and hasattr(self, 'overlay_frame'):
            if hasattr(self, 'analyzed_video_warning') and self.analyzed_video_warning:
                try:
                    self.analyzed_video_warning.destroy()
                except:
                    pass
            try:
                self.analyzed_video_warning = ttk.Label(self.overlay_frame, 
                    text="⚠ Video already has overlays - overlay rendering disabled", 
                    font=("Arial", 8), foreground="orange")
                children = self.overlay_frame.winfo_children()
                if children:
                    self.analyzed_video_warning.pack(anchor=tk.W, pady=2, before=children[0])
                else:
                    self.analyzed_video_warning.pack(anchor=tk.W, pady=2)
            except Exception as e:
                print(f"Could not add analyzed video warning: {e}")
        
        # Load and render first frame
        try:
            if hasattr(self, 'canvas') and self.canvas.winfo_exists():
                self.current_frame = self.load_frame()
                if self.current_frame is not None:
                    self.render_overlays()
                else:
                    self.render_overlays()
        except (tk.TclError, AttributeError):
            pass
    
    def _on_video_load_error(self, progress_window, error_msg):
        """Callback when video loading fails (runs on main thread)"""
        try:
            progress_window.destroy()
        except:
            pass
        
        messagebox.showerror("Error", error_msg)
        self.cap = None
        self.current_frame = None
        
        try:
            if hasattr(self, 'canvas') and self.canvas.winfo_exists():
                self.canvas.delete("all")
                self.canvas.create_text(
                    self.canvas.winfo_width() // 2 if self.canvas.winfo_width() > 1 else 400,
                    self.canvas.winfo_height() // 2 if self.canvas.winfo_height() > 1 else 300,
                    text=f"⚠ Error loading video\n\n{os.path.basename(self.video_path) if self.video_path else 'Unknown'}\n\nPlease check the file and try again",
                    font=("Arial", 12),
                    fill="red",
                    justify=tk.CENTER
                )
        except:
            pass
    
    def load_csv(self, csv_path=None):
        """Load CSV tracking data (runs in background thread to prevent GUI freeze)"""
        if csv_path is None:
            filename = filedialog.askopenfilename(
                title="Select Tracking Data CSV",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not filename:
                return
            self.csv_path = filename
        else:
            filename = csv_path
            self.csv_path = csv_path
        
        # Show progress window
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Loading CSV...")
        progress_window.geometry("400x100")
        progress_window.transient(self.root)
        progress_window.grab_set()
        progress_window.resizable(False, False)
        
        progress_label = ttk.Label(progress_window, text=f"Loading CSV: {os.path.basename(filename)}", font=("Arial", 10))
        progress_label.pack(pady=10)
        
        progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
        progress_bar.pack(pady=5, padx=20, fill=tk.X)
        progress_bar.start()
        
        def load_csv_thread():
            """Load CSV in background thread"""
            try:
                self._load_csv_worker(filename)
                # Update UI on main thread
                self.root.after(0, lambda: self._on_csv_loaded(progress_window, filename))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self._on_csv_load_error(progress_window, error_msg))
        
        # Start loading in background thread
        thread = threading.Thread(target=load_csv_thread, daemon=True)
        thread.start()
    
    def _load_csv_worker(self, filename):
        """Worker function to load CSV (runs in background thread)"""
        # Clear previous metadata path so we can load new metadata for this CSV
        if hasattr(self, '_last_metadata_path'):
            if self._last_metadata_path != filename:
                self._last_metadata_path = None  # Different CSV - allow metadata loading
        
        # Check if file is empty before reading
        if os.path.getsize(filename) == 0:
            raise Exception(f"CSV file is empty: {os.path.basename(filename)}\n\nThis usually means the analysis didn't generate any tracking data.")
        
        # Skip comment lines (starting with '#') - these contain metadata
        self.df = pd.read_csv(filename, comment='#')
        
        # Check if DataFrame is empty
        if self.df.empty:
            raise Exception(f"CSV file contains no data: {os.path.basename(filename)}\n\nThis usually means the analysis didn't generate any tracking data.")
        
        # Check if it has frame column
        if 'frame' not in self.df.columns:
            # Assume index is frame number
            self.df['frame'] = self.df.index
        
        # Process player data
        self.player_data = {}
        # Check if CSV has bbox columns (x1, y1, x2, y2)
        has_bbox = all(col in self.df.columns for col in ['x1', 'y1', 'x2', 'y2'])
        
        if 'player_id' in self.df.columns:
                # OPTIMIZATION: Use vectorized operations instead of iterrows() for much faster CSV loading
                # Filter valid rows first (non-NaN frame and player_id)
                valid_mask = (
                    self.df['frame'].notna() & 
                    self.df['player_id'].notna() &
                    self.df['player_x'].notna() &
                    self.df['player_y'].notna()
                )
                valid_df = self.df[valid_mask].copy()
                
                if len(valid_df) > 0:
                    # Convert frame and player_id to int (vectorized)
                    valid_df['frame'] = valid_df['frame'].astype(int)
                    valid_df['player_id'] = valid_df['player_id'].astype(int)
                    
                    # Group by frame for efficient processing
                    for frame_num, frame_group in valid_df.groupby('frame'):
                        # Convert frame_num to int (groupby returns the group key)
                        frame_num_int = int(frame_num)
                        
                        if frame_num_int not in self.player_data:
                            self.player_data[frame_num_int] = {}
                        
                        # Process all players in this frame at once
                        for _, row in frame_group.iterrows():
                            player_id = int(row['player_id'])
                            x = float(row['player_x'])
                            y = float(row['player_y'])
                            
                            # Get bbox if available (for proper box rendering)
                            bbox = None
                            if has_bbox:
                                x1 = row.get('x1') if pd.notna(row.get('x1')) else None
                                y1 = row.get('y1') if pd.notna(row.get('y1')) else None
                                x2 = row.get('x2') if pd.notna(row.get('x2')) else None
                                y2 = row.get('y2') if pd.notna(row.get('y2')) else None
                                if all(v is not None for v in [x1, y1, x2, y2]):
                                    bbox = (float(x1), float(y1), float(x2), float(y2))
                            
                            # Get team if available
                            team = None
                            if 'team' in row and pd.notna(row['team']):
                                team = row['team']
                            
                            # Get player name (prioritize CSV, then player_names.json)
                            pid_str = str(player_id)
                            name = f"#{player_id}"  # Default fallback
                            
                            # 1. Try CSV player_name column first (most reliable)
                            if 'player_name' in row and pd.notna(row['player_name']):
                                csv_name = str(row['player_name']).strip()
                                if csv_name and csv_name != 'nan' and csv_name.lower() != 'none':
                                    name = csv_name
                                    # Update player_names map for analytics tab
                                    if not hasattr(self, 'player_names') or self.player_names is None:
                                        self.player_names = {}
                                    self.player_names[pid_str] = csv_name
                            
                            # 2. Fall back to player_names.json if CSV doesn't have name
                            if name == f"#{player_id}" and hasattr(self, 'player_names') and self.player_names:
                                name = self.player_names.get(pid_str, f"#{player_id}")
                            
                            # Store with bbox if available: (x, y, team, name, bbox)
                            # bbox is None if not available (will use fixed-size boxes)
                            self.player_data[frame_num_int][player_id] = (x, y, team, name, bbox)
        
        # Process ball data
        self.ball_data = {}
        
        # Ball analytics (Kinovea-style)
        self.ball_analytics = None
        self.ball_trajectory = None
        self.show_ball_trajectory = tk.BooleanVar(value=False)
        self.show_ball_speed_overlay = tk.BooleanVar(value=False)
        if 'ball_x' in self.df.columns and 'ball_y' in self.df.columns:
                # Get video dimensions for validation (use original video dimensions if available)
                video_width = getattr(self, 'original_video_width', None) or getattr(self, 'width', 3840)
                video_height = getattr(self, 'original_video_height', None) or getattr(self, 'height', 2160)
                
                # Track previous valid ball position for outlier detection
                prev_valid_ball = None
                max_jump_distance = 500  # Increased from 200 to 500 - ball can move fast (increased tolerance)
                skipped_out_of_bounds = 0
                skipped_jumps = 0
                skipped_detected_flag = 0
                
                # OPTIMIZATION: Use vectorized operations instead of iterrows() for faster CSV loading
                # Filter valid rows first (non-NaN frame, ball_x, and ball_y)
                valid_mask = (
                    self.df['frame'].notna() & 
                    self.df['ball_x'].notna() &
                    self.df['ball_y'].notna()
                )
                valid_df = self.df[valid_mask].copy()
                
                if len(valid_df) > 0:
                    # Convert frame to int (vectorized)
                    valid_df['frame'] = valid_df['frame'].astype(int)
                    
                    # Process ball data grouped by frame
                    for frame_num, frame_group in valid_df.groupby('frame'):
                        # Convert frame_num to int (groupby returns the group key)
                        frame_num_int = int(frame_num)
                        
                        # Take first valid ball position for each frame (in case of duplicates)
                        row = frame_group.iloc[0]
                        ball_x_float = float(row['ball_x'])
                        ball_y_float = float(row['ball_y'])
                        
                        # Check if coordinates are normalized (0-1) - if so, convert to pixels
                        if 0.0 <= ball_x_float <= 1.0 and 0.0 <= ball_y_float <= 1.0:
                            ball_x_float = ball_x_float * video_width
                            ball_y_float = ball_y_float * video_height
                        
                        # Check 1: Coordinates must be within reasonable bounds (with 20% margin - increased from 10%)
                        margin = 0.2
                        if (ball_x_float < -video_width * margin or ball_x_float > video_width * (1 + margin) or
                            ball_y_float < -video_height * margin or ball_y_float > video_height * (1 + margin)):
                            # Out of bounds - skip this detection
                            skipped_out_of_bounds += 1
                            if frame_num_int % 100 == 0:  # Log occasionally
                                print(f"⚠ Skipping ball detection at frame {frame_num_int}: out of bounds ({ball_x_float:.1f}, {ball_y_float:.1f})")
                            continue
                        
                        # Check 2: If we have a previous valid position, check for sudden jumps
                        # RELAXED: Only check if frames are close together (within 10 frames)
                        if prev_valid_ball is not None:
                            prev_x, prev_y = prev_valid_ball
                            jump_distance = np.sqrt((ball_x_float - prev_x)**2 + (ball_y_float - prev_y)**2)
                            
                            # Only apply jump check if this is a consecutive frame (or close)
                            # For sparse detections, allow larger jumps
                            if jump_distance > max_jump_distance:
                                skipped_jumps += 1
                                if frame_num_int % 100 == 0:  # Log occasionally
                                    print(f"⚠ Skipping ball detection at frame {frame_num_int}: sudden jump ({jump_distance:.1f}px from previous position)")
                                # Don't skip - allow it if it's the only detection we have
                                # Only skip if we have many detections (sparse tracking is better than no tracking)
                                if len(valid_df) > 100:  # Only apply strict jump filtering if we have many detections
                                    continue
                        
                        # Check 3: Check if ball_detected flag exists and is False
                        if 'ball_detected' in row.index and pd.notna(row.get('ball_detected')):
                            ball_detected = row['ball_detected']
                            if ball_detected is not None and (ball_detected == False or ball_detected == 0):
                                # Explicitly marked as not detected - skip
                                skipped_detected_flag += 1
                                continue
                        
                        # All checks passed - store valid ball position
                        self.ball_data[frame_num_int] = (ball_x_float, ball_y_float)
                        prev_valid_ball = (ball_x_float, ball_y_float)
                
                # Debug: Print ball data loading summary
                if len(self.ball_data) > 0:
                    sample_frames = sorted(list(self.ball_data.keys()))[:5]
                    print(f"✓ Loaded ball data: {len(self.ball_data)} frames with ball positions (out of {len(valid_df)} valid rows)")
                    if skipped_out_of_bounds > 0:
                        print(f"   ⚠ Skipped {skipped_out_of_bounds} frames: out of bounds")
                    if skipped_jumps > 0:
                        print(f"   ⚠ Skipped {skipped_jumps} frames: sudden jumps (relaxed for sparse tracking)")
                    if skipped_detected_flag > 0:
                        print(f"   ⚠ Skipped {skipped_detected_flag} frames: ball_detected=False")
                    print(f"   Sample frames: {sample_frames}")
                    for sample_frame in sample_frames[:3]:
                        ball_pos = self.ball_data[sample_frame]
                        print(f"   Frame {sample_frame}: ball at ({ball_pos[0]:.1f}, {ball_pos[1]:.1f})")
                else:
                    print(f"⚠ No ball data loaded - check CSV columns 'ball_x' and 'ball_y'")
                    print(f"   Total valid rows in CSV: {len(valid_df)}")
                    if len(valid_df) > 0:
                        print(f"   First few ball coordinates from CSV:")
                        for idx, row in valid_df.head(5).iterrows():
                            print(f"     Frame {int(row['frame'])}: ({row['ball_x']}, {row['ball_y']})")
        
        # Process analytics data
        self.analytics_data = {}
        # Auto-enable analytics if CSV has analytics columns
        has_analytics_columns = False
        if 'player_id' in self.df.columns:
            # All possible analytics columns (both metric and imperial units)
            # This matches the columns exported in combined_analysis_optimized.py
            analytics_columns = [
                # Speed columns (both units)
                'player_speed_mps', 'player_speed_mph', 'avg_speed_mps', 'avg_speed_mph', 
                'max_speed_mps', 'max_speed_mph', 'ball_speed_mps', 'ball_speed_mph',
                # Acceleration columns (both units)
                'player_acceleration_mps2', 'player_acceleration_fts2',
                # Distance columns (both units)
                'distance_to_ball_px', 'distance_traveled_m', 'distance_traveled_ft',
                'distance_from_center_m', 'distance_from_center_ft', 
                'distance_from_goal_m', 'distance_from_goal_ft',
                'distance_walking_m', 'distance_walking_ft', 
                'distance_jogging_m', 'distance_jogging_ft',
                'distance_running_m', 'distance_running_ft', 
                'distance_sprinting_m', 'distance_sprinting_ft',
                'nearest_teammate_dist_m', 'nearest_teammate_dist_ft', 
                'nearest_opponent_dist_m', 'nearest_opponent_dist_ft',
                # Position columns (both units)
                'player_x_m', 'player_x_ft', 'player_y_m', 'player_y_ft',
                'field_position_x_pct', 'field_position_y_pct',
                # Other analytics
                'player_movement_angle', 'ball_trajectory_angle',
                'field_zone', 'sprint_count', 'possession_time_s',
                'direction_changes', 'time_stationary_s', 'acceleration_events'
            ]
            
            for _, row in self.df.iterrows():
                # Skip rows with NaN frame numbers
                if pd.isna(row.get('frame')):
                    continue
                
                try:
                    frame_num = int(row['frame'])
                except (ValueError, TypeError):
                    # Skip rows with invalid frame numbers
                    continue
                
                if pd.notna(row.get('player_id')):
                    player_id = int(row['player_id'])
                    
                    if frame_num not in self.analytics_data:
                        self.analytics_data[frame_num] = {}
                    
                    # Extract all available analytics for this player
                    analytics = {}
                    for col in analytics_columns:
                        if col in self.df.columns and pd.notna(row.get(col)):
                            analytics[col] = row[col]
                    
                    if analytics:
                        self.analytics_data[frame_num][player_id] = analytics
                        has_analytics_columns = True
        
        # Store analytics flag for callback
        self._csv_has_analytics = has_analytics_columns
        
        # Update last modified time for file watching
        if os.path.exists(filename):
            self.csv_last_modified = os.path.getmtime(filename)
        
        # Try to load overlay metadata if available (safe in worker thread)
        self.load_overlay_metadata(filename)
    
    def _on_csv_loaded(self, progress_window, filename):
        """Callback when CSV is successfully loaded (runs on main thread)"""
        try:
            progress_window.destroy()
        except:
            pass
        
        # All UI updates happen here (on main thread)
        # Check if data was loaded
        player_frames = len(self.player_data)
        ball_frames = len(self.ball_data)
        
        status_msg = f"CSV loaded: {player_frames} frames with players, {ball_frames} frames with ball"
        if self.overlay_metadata:
            status_msg += f" | Overlay metadata: {len(self.overlay_metadata.overlays)} frames"
        if player_frames == 0 and ball_frames == 0:
            status_msg += " ⚠ No tracking data found - YOLO may not have detected any players/ball"
            messagebox.showwarning("No Tracking Data", 
                "The CSV file contains no player or ball tracking data.\n\n"
                "This usually means:\n"
                "• YOLO didn't detect any players (check confidence threshold)\n"
                "• The video frames don't contain visible players\n"
                "• The analysis failed to generate tracking data\n\n"
                "Try:\n"
                "• Lowering the YOLO confidence threshold\n"
                "• Running analysis on a different part of the video\n"
                "• Checking if the analyzed video file has overlays drawn on it")
        
        try:
            if hasattr(self, 'status_label') and self.status_label:
                try:
                    if self.status_label.winfo_exists():
                        current_text = self.status_label.cget('text')
                        self.status_label.config(text=f"{current_text} | {status_msg}")
                except (tk.TclError, AttributeError):
                    try:
                        if hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
                            self.status_label.config(text=status_msg)
                    except:
                        pass
        except:
            pass
        
        # Auto-enable analytics display if we have analytics data
        if getattr(self, '_csv_has_analytics', False) and hasattr(self, 'show_analytics'):
            try:
                if hasattr(self.show_analytics, 'winfo_exists') and self.show_analytics.winfo_exists():
                    if not self.show_analytics.get():
                        self.show_analytics.set(True)
            except:
                pass
        
        # Start file watching if enabled
        try:
            if hasattr(self, 'watch_csv_enabled') and self.watch_csv_enabled is not None:
                try:
                    if hasattr(self.watch_csv_enabled, 'winfo_exists') and self.watch_csv_enabled.winfo_exists():
                        watch_enabled = self.watch_csv_enabled.get()
                        if watch_enabled and not self.watch_running:
                            self.start_file_watching()
                except:
                    pass
        except:
            pass
        
        # Reload analytics preferences when CSV loads
        try:
            self.analytics_preferences = self.load_analytics_preferences()
            selected_count = len([k for k, v in self.analytics_preferences.items() if v])
            if selected_count > 0:
                try:
                    if hasattr(self, 'analytics_selections_label') and self.analytics_selections_label is not None:
                        if hasattr(self.analytics_selections_label, 'winfo_exists') and self.analytics_selections_label.winfo_exists():
                            self.update_analytics_selections_label()
                except:
                    pass
        except Exception as e:
            print(f"⚠ Could not reload analytics preferences: {e}")
        
        # Check if CSV has analytics columns
        try:
            if self.df is not None:
                analytics_columns = [
                    'player_speed_mps', 'player_speed_mph', 'avg_speed_mps', 'avg_speed_mph', 
                    'max_speed_mps', 'max_speed_mph', 'ball_speed_mps', 'ball_speed_mph',
                    'player_acceleration_mps2', 'player_acceleration_fts2',
                    'distance_to_ball_px', 'distance_traveled_m', 'distance_traveled_ft',
                    'distance_from_center_m', 'distance_from_center_ft', 
                    'distance_from_goal_m', 'distance_from_goal_ft',
                    'distance_walking_m', 'distance_walking_ft', 
                    'distance_jogging_m', 'distance_jogging_ft',
                    'distance_running_m', 'distance_running_ft', 
                    'distance_sprinting_m', 'distance_sprinting_ft',
                    'nearest_teammate_dist_m', 'nearest_teammate_dist_ft', 
                    'nearest_opponent_dist_m', 'nearest_opponent_dist_ft',
                    'player_x_m', 'player_x_ft', 'player_y_m', 'player_y_ft',
                    'field_position_x_pct', 'field_position_y_pct',
                    'player_movement_angle', 'ball_trajectory_angle',
                    'field_zone', 'sprint_count', 'possession_time_s',
                    'direction_changes', 'time_stationary_s', 'acceleration_events'
                ]
                all_analytics_cols = [col for col in self.df.columns if col in analytics_columns]
                if len(all_analytics_cols) > 0:
                    print(f"✓ Analytics: Found {len(all_analytics_cols)} analytics column(s) in CSV")
        except Exception:
            pass
        
        # Update focused player list if panel exists
        try:
            if hasattr(self, 'show_focused_player_panel') and self.show_focused_player_panel is not None:
                if hasattr(self.show_focused_player_panel, 'winfo_exists') and self.show_focused_player_panel.winfo_exists():
                    if self.show_focused_player_panel.get():
                        if hasattr(self, 'focused_panel') and self.focused_panel is not None:
                            if hasattr(self.focused_panel, 'winfo_exists') and self.focused_panel.winfo_exists():
                                self.update_focused_player_list()
        except:
            pass
        
        # Reload frame and render
        if not self.comparison_mode:
            try:
                self.current_frame = self.load_frame()
                self.render_overlays()
            except Exception as e:
                print(f"⚠ Error loading frame/overlay: {e}")
    
    def _on_csv_load_error(self, progress_window, error_msg):
        """Callback when CSV loading fails (runs on main thread)"""
        try:
            progress_window.destroy()
        except:
            pass
        
        messagebox.showerror("Error", error_msg)
    
    def reload_csv(self):
        """Reload CSV file if it's already loaded"""
        if not self.csv_path or not os.path.exists(self.csv_path):
            messagebox.showwarning("No CSV", "No CSV file loaded. Please load a CSV file first.")
            return
        
        try:
            self.load_csv(self.csv_path)
            messagebox.showinfo("Reloaded", f"CSV file reloaded successfully.\n{len(self.player_data)} frames with players")
        except Exception as e:
            messagebox.showerror("Error", f"Could not reload CSV: {e}")
    
    def start_file_watching(self):
        """Start background thread to watch for CSV file changes"""
        if self.watch_running:
            return
        
        if not self.csv_path or not os.path.exists(self.csv_path):
            return
        
        self.watch_running = True
        self.watch_thread = threading.Thread(target=self._watch_csv_file, daemon=True)
        self.watch_thread.start()
    
    def stop_file_watching(self):
        """Stop file watching thread"""
        self.watch_running = False
        if self.watch_thread:
            self.watch_thread.join(timeout=1.0)
    
    def _watch_csv_file(self):
        """Background thread to watch for CSV file changes"""
        while self.watch_running:
            try:
                if self.watch_csv_enabled.get() and self.csv_path and os.path.exists(self.csv_path):
                    current_mtime = os.path.getmtime(self.csv_path)
                    if self.csv_last_modified is not None and current_mtime > self.csv_last_modified:
                        # File has changed, reload it
                        self.csv_last_modified = current_mtime
                        # Schedule reload on main thread
                        self.root.after(0, self._auto_reload_csv)
                time.sleep(1.0)  # Check every second
            except Exception as e:
                # Silently handle errors (file might be deleted, etc.)
                time.sleep(1.0)
    
    def _auto_reload_csv(self):
        """Auto-reload CSV when file changes (called on main thread)"""
        if self.csv_path and os.path.exists(self.csv_path):
            try:
                self.load_csv(self.csv_path)
                # Update status without showing popup (less intrusive)
                current_text = self.status_label.cget('text')
                if "Auto-reloaded" not in current_text:
                    self.status_label.config(text=f"{current_text} | Auto-reloaded at {datetime.now().strftime('%H:%M:%S')}")
            except Exception as e:
                # Silently fail - user can manually reload if needed
                pass
    
    def load_frame(self, frame_num=None):
        """Load and display current frame (or specific frame for comparison mode)"""
        if self.cap is None:
            return
        
        if frame_num is None:
            frame_num = self.current_frame_num
        
        # Try to get frame from buffer first
        with self.buffer_lock:
            if frame_num in self.frame_buffer:
                frame = self.frame_buffer[frame_num]
                # Move to end (most recently used)
                self.frame_buffer.move_to_end(frame_num)
                return frame.copy()
        
        # Frame not in buffer - load it
        # If we're reading sequentially (next frame), use sequential read (faster)
        if frame_num == self.last_sequential_frame + 1:
            # Sequential read - faster than seeking
            ret, frame = self.cap.read()
            if ret:
                self.last_sequential_frame = frame_num
                # Add to buffer
                with self.buffer_lock:
                    self._add_to_buffer(frame_num, frame)
                return frame.copy()
        else:
            # Random access - need to seek
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = self.cap.read()
            if ret:
                self.last_sequential_frame = frame_num
                # Add to buffer
                with self.buffer_lock:
                    self._add_to_buffer(frame_num, frame)
                return frame.copy()
    
        return None
    
    def _add_to_buffer(self, frame_num, frame):
        """Add frame to buffer, maintaining max size"""
        self.frame_buffer[frame_num] = frame.copy()
        
        # Remove oldest frames if buffer is too large
        while len(self.frame_buffer) > self.buffer_max_size:
            self.frame_buffer.popitem(last=False)  # Remove oldest
    
    def _buffer_worker(self):
        """Background thread to pre-load frames ahead of current position"""
        while self.buffer_thread_running:
            try:
                if self.cap is None or not self.is_playing:
                    time.sleep(0.1)
                    continue
                
                # Get current frame and direction
                current_frame = self.current_frame_num
                target_frame = current_frame + self.buffer_read_ahead
                
                # Check if we need to buffer
                with self.buffer_lock:
                    buffer_size = len(self.frame_buffer)
                    # Check if target frame is already buffered
                    if target_frame in self.frame_buffer:
                        time.sleep(0.05)  # Short sleep if already buffered
                        continue
                
                # Only buffer if we're playing forward and buffer is not full
                if buffer_size < self.buffer_max_size and target_frame < self.total_frames:
                    # Try to read sequentially from last position
                    if self.last_sequential_frame >= 0 and target_frame > self.last_sequential_frame:
                        # Continue sequential read
                        frames_to_read = target_frame - self.last_sequential_frame
                        if frames_to_read <= 5:  # Only if close (avoid long seeks)
                            for _ in range(frames_to_read):
                                if not self.buffer_thread_running:
                                    break
                                ret, frame = self.cap.read()
                                if ret:
                                    frame_num = self.last_sequential_frame + 1
                                    self.last_sequential_frame = frame_num
                                    with self.buffer_lock:
                                        self._add_to_buffer(frame_num, frame)
                                else:
                                    break
                    else:
                        # Need to seek - only do this if buffer is getting low
                        if buffer_size < self.buffer_min_size:
                            self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                            ret, frame = self.cap.read()
                            if ret:
                                with self.buffer_lock:
                                    self._add_to_buffer(target_frame, frame)
                                self.last_sequential_frame = target_frame
                
                time.sleep(0.01)  # Small sleep to avoid CPU spinning
            except Exception as e:
                # Silently handle errors (video might be closed, etc.)
                time.sleep(0.1)
    
    def start_buffer_thread(self):
        """Start the background frame buffering thread"""
        if self.buffer_thread is None or not self.buffer_thread.is_alive():
            self.buffer_thread_running = True
            self.buffer_thread = threading.Thread(target=self._buffer_worker, daemon=True)
            self.buffer_thread.start()
    
    def stop_buffer_thread(self):
        """Stop the background frame buffering thread"""
        self.buffer_thread_running = False
        if self.buffer_thread is not None:
            self.buffer_thread.join(timeout=1.0)
    
    def clear_frame_buffer(self):
        """Clear the frame buffer (e.g., when video changes)"""
        with self.buffer_lock:
            self.frame_buffer.clear()
        self.last_sequential_frame = -1
    
    def _preload_initial_frames(self):
        """Pre-load initial frames into buffer for faster startup"""
        if self.cap is None:
            return
        
        # Pre-load initial frames - scale based on FPS (more frames for higher FPS)
        # At 60fps, preload ~20 frames (0.33 seconds), at 30fps preload ~10 frames (0.33 seconds)
        preload_count = min(max(10, int(self.fps / 3)), self.total_frames)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        for i in range(preload_count):
            ret, frame = self.cap.read()
            if ret:
                with self.buffer_lock:
                    self._add_to_buffer(i, frame)
                self.last_sequential_frame = i
            else:
                break
    
    def render_overlays(self, frame=None, frame_num=None, highlight_id=None, canvas=None):
        """Render overlays on current frame (or specific frame for comparison mode)"""
        if self.comparison_mode:
            # Render side-by-side comparison
            self.render_comparison()
        else:
            # Render single frame
            self.render_single_frame()
    
    def render_single_frame(self):
        """Render single frame mode - optimized to reduce stuttering"""
        if self.current_frame_num % 60 == 0:  # Only log every 60 frames
            print(f"🎬 RENDER: frame {self.current_frame_num}, cap={self.cap is not None}, opened={self.cap.isOpened() if self.cap else False}, current_frame={self.current_frame is not None}")

        # Check if video is loaded
        if self.cap is None or not self.cap.isOpened():
            if self.current_frame_num % 60 == 0:
                print(f"⚠ VIDEO NOT LOADED: cap={self.cap}, opened={self.cap.isOpened() if self.cap else False}")
            # Video not loaded - show message on canvas
            try:
                if hasattr(self, 'canvas') and self.canvas.winfo_exists():
                    self.canvas.delete("all")
                    self.canvas.create_text(
                        self.canvas.winfo_width() // 2 if self.canvas.winfo_width() > 1 else 400,
                        self.canvas.winfo_height() // 2 if self.canvas.winfo_height() > 1 else 300,
                        text="⚠ No video loaded\n\nPlease load a video file using 'Load Video' button",
                        font=("Arial", 14),
                        fill="red",
                        justify=tk.CENTER
                    )
            except:
                pass
            return
        
        if self.current_frame is None:
            if self.current_frame_num % 60 == 0:
                print(f"📥 LOADING FRAME: {self.current_frame_num}")
            # Try to load the frame
            self.current_frame = self.load_frame()
            if self.current_frame is None:
                if self.current_frame_num % 60 == 0:
                    print(f"❌ FRAME LOAD FAILED: {self.current_frame_num}")
                # Frame loading failed - show error
                try:
                    if hasattr(self, 'canvas') and self.canvas.winfo_exists():
                        self.canvas.delete("all")
                        self.canvas.create_text(
                            self.canvas.winfo_width() // 2 if self.canvas.winfo_width() > 1 else 400,
                            self.canvas.winfo_height() // 2 if self.canvas.winfo_height() > 1 else 300,
                            text=f"⚠ Failed to load frame {self.current_frame_num}\n\nVideo may be corrupted or frame is out of range",
                            font=("Arial", 12),
                            fill="orange",
                            justify=tk.CENTER
                        )
                except:
                    pass
                return
        
        # Skip rendering if this frame was already rendered (unless overlay settings changed)
        # The overlay_settings_hash is managed by play() method - if it's None, settings changed
        if self.current_frame_num == self.last_rendered_frame_num and self.overlay_settings_hash is not None:
                return  # No changes, skip rendering
        
        # OPTIMIZATION: Check rendered frame cache first (if settings haven't changed)
        cached_frame_used = False
        settings_hash = self.overlay_settings_hash
        if settings_hash is not None:
            with self.rendered_cache_lock:
                if self.current_frame_num in self.rendered_frame_cache:
                    cached_frame, cached_hash = self.rendered_frame_cache[self.current_frame_num]
                    if cached_hash == settings_hash:
                        # Use cached rendered frame - skip expensive rendering
                        display_frame = cached_frame.copy()
                        # Move to end (most recently used)
                        self.rendered_frame_cache.move_to_end(self.current_frame_num)
                        # Skip to display update (skip overlay rendering)
                        cached_frame_used = True
        
        # Safety check: ensure current_frame is valid before rendering
        if self.current_frame is None or self.current_frame.size == 0:
            print(f"⚠ Error: current_frame is None or empty for frame {self.current_frame_num}")
            return
        
        # Only render overlays if not using cached frame
        if not cached_frame_used:
            frame_for_worker = self.current_frame.copy()
            display_frame = self.current_frame.copy()
            overlay_mode = self.overlay_render_mode.get()
            overlay_result = None  # Initialize overlay_result
            if overlay_mode == "metadata":
                self._request_overlay_render(self.current_frame_num, frame_for_worker)
                overlay_result = self._get_overlay_result(self.current_frame_num)
            if overlay_result is not None:
                display_frame = overlay_result
            elif self.show_players.get() or self.show_ball.get() or self.show_trajectories.get() or self.show_field_zones.get():
                # OPTIMIZATION: Skip expensive effects during playback for speed
                display_frame = self.render_overlays_on_frame(
                    self.current_frame.copy(),
                    self.current_frame_num,
                    force_mode="csv",
                    skip_expensive_effects=self.is_playing  # Skip expensive effects during playback
                )

            # Cache rendered frame for future use
            if settings_hash is not None:
                with self.rendered_cache_lock:
                    self.rendered_frame_cache[self.current_frame_num] = (display_frame.copy(), settings_hash)
                    # Remove oldest frames if cache is too large
                    while len(self.rendered_frame_cache) > self.rendered_cache_max_size:
                        self.rendered_frame_cache.popitem(last=False)
        
        # Safety check: ensure frame is valid after rendering
        if display_frame is None or display_frame.size == 0:
            print(f"⚠ Error: Failed to render frame {self.current_frame_num} - display_frame is None or empty")
            # Try to use original frame without overlays
            if self.current_frame is not None and self.current_frame.size > 0:
                print(f"   Attempting to use original frame without overlays")
                display_frame = self.current_frame.copy()
            else:
                print(f"   Cannot render - no valid frame available")
                return  # Can't render anything
        
        # OPTIMIZED: Cache canvas size to avoid expensive update_idletasks() calls
        # Only recalculate if canvas size might have changed (window resize, etc.)
        if self.cached_canvas_size is None:
            # Get canvas container size (not canvas itself) to fit video to allocated space
            # This prevents the canvas from expanding beyond its allocated area
            if hasattr(self, 'canvas_container'):
                canvas_container = self.canvas_container
            else:
                canvas_container = self.canvas.master
            
            # OPTIMIZED: Only call update_idletasks() if we really need to
            # Try getting size first without forcing update
            container_width = canvas_container.winfo_width()
            container_height = canvas_container.winfo_height()
            
            # If container hasn't been rendered yet, try canvas size
            if container_width <= 1 or container_height <= 1:
                container_width = self.canvas.winfo_width()
                container_height = self.canvas.winfo_height()
            
            # Only force update if we still don't have valid size
            if container_width <= 1 or container_height <= 1:
                canvas_container.update_idletasks()
                container_width = canvas_container.winfo_width()
                container_height = canvas_container.winfo_height()
            
            # If still no size, use canvas directly
            if container_width <= 1 or container_height <= 1:
                self.canvas.update_idletasks()
                container_width = self.canvas.winfo_width()
                container_height = self.canvas.winfo_height()
            
            # If still no size, use default
            if container_width <= 1 or container_height <= 1:
                container_width = 800
                container_height = 600
            
            self.cached_canvas_size = (container_width, container_height)
        
        # Use cached size
        container_width, container_height = self.cached_canvas_size
        
        # Use container dimensions for fitting
        canvas_width = container_width
        canvas_height = container_height
        
        # DEBUG: Log canvas size for troubleshooting
        if self.current_frame_num == 0:
            print(f"🖼️ Canvas size: {canvas_width}x{canvas_height}, Video: {self.width}x{self.height}")

        # Calculate display size to fit canvas while maintaining aspect ratio
        aspect_ratio = self.width / self.height if self.height > 0 else 16/9
        canvas_aspect = canvas_width / canvas_height if canvas_height > 0 else 16/9
        
        if aspect_ratio > canvas_aspect:
            # Video is wider - fit to width
            display_width = canvas_width
            display_height = int(display_width / aspect_ratio)
        else:
            # Video is taller - fit to height
            display_height = canvas_height
            display_width = int(display_height * aspect_ratio)
        
        # DEBUG: Log display size before downscaling
        if self.current_frame_num == 0:
            print(f"🖼️ Display size before downscale: {display_width}x{display_height}")

        # OPTIMIZATION: Apply downscaling only if it doesn't make the frame too small
        # Scale to fit canvas first, then apply minimal downscaling for performance if needed
        if self.playback_downscale_enabled and self.playback_downscale_factor < 1.0:
            # Calculate what the size would be after downscaling
            downscaled_width = int(display_width * self.playback_downscale_factor)
            downscaled_height = int(display_height * self.playback_downscale_factor)
            
            # Only apply downscaling if the result is still reasonable (at least 80% of canvas)
            # This ensures the video fills the canvas properly and looks good
            min_width = int(canvas_width * 0.8)  # At least 80% of canvas width
            min_height = int(canvas_height * 0.8)  # At least 80% of canvas height
            
            if downscaled_width >= min_width and downscaled_height >= min_height:
                # Downscale is acceptable - apply it
                display_width = downscaled_width
                display_height = downscaled_height
                if self.current_frame_num == 0:
                    print(f"🖼️ Applied downscaling: {display_width}x{display_height} (factor: {self.playback_downscale_factor})")
            else:
                # Downscaling would make frame too small - use full canvas size for best quality
                # This ensures video fills the canvas properly
                display_width = canvas_width
                display_height = canvas_height
                if self.current_frame_num == 0:
                    print(f"🖼️ Using full canvas size: {display_width}x{display_height} (downscaling disabled to fit canvas)")

        # Ensure display size is valid and positive
        display_width = max(1, display_width)
        display_height = max(1, display_height)
        
        # Safety check before resize
        if display_frame is None or display_frame.size == 0:
            print(f"⚠ Error: Invalid frame before resize for frame {self.current_frame_num}")
            return
        
        display_frame = cv2.resize(display_frame, (display_width, display_height))
        
        # Safety check before color conversion
        if display_frame is None or display_frame.size == 0:
            print(f"⚠ Error: Invalid frame after resize for frame {self.current_frame_num}")
            return
        
        # Convert BGR to RGB for display (OpenCV uses BGR, Tkinter uses RGB)
        try:
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        except cv2.error as e:
            print(f"⚠ Error converting frame color for frame {self.current_frame_num}: {e}")
            print(f"   Frame shape: {display_frame.shape if display_frame is not None else 'None'}")
            return
        
        # Store original for zoom
        self.original_display_frame = display_frame.copy()
        
        # Apply zoom and pan
        display_frame = self.apply_zoom_pan_single(display_frame)
        
        # CRITICAL FIX: Update canvas size to match display size to ensure proper fitting
        # This ensures the canvas matches the video size, preventing left side from being cut off
        self.canvas.config(width=canvas_width, height=canvas_height)
        
        # Update canvas
        # Safety check: ensure display_frame is valid before converting to image
        if display_frame is None or display_frame.size == 0:
            print(f"⚠ Error: display_frame is invalid before canvas update for frame {self.current_frame_num}")
            return
        
        try:
            # PROFILE: Measure PhotoImage conversion time (bottleneck for large frames)
            photo_start = time.time()
            if self.current_frame_num % 60 == 0:  # Only log every 60 frames
                print(f"🖼️ CONVERTING: frame {self.current_frame_num}, shape={display_frame.shape}, dtype={display_frame.dtype}")
            image = Image.fromarray(display_frame)
            photo = ImageTk.PhotoImage(image=image)
            photo_time = (time.time() - photo_start) * 1000  # ms

            if self.current_frame_num % 60 == 0:  # Only log every 60 frames
                print(f"✅ PHOTOIMAGE CREATED: {photo_time:.1f}ms, size={image.size}")

            # Log PhotoImage conversion time every 60 frames
            if self.current_frame_num % 60 == 0:
                frame_shape = display_frame.shape if display_frame is not None else "None"
                print(f"🖼️ PhotoImage: {photo_time:.1f}ms for {frame_shape} (downscale: {self.playback_downscale_factor:.2f}x)")

        except Exception as e:
            print(f"❌ PHOTOIMAGE ERROR: frame {self.current_frame_num}, {e}")
            print(f"   Frame shape: {display_frame.shape if display_frame is not None else 'None'}")
            print(f"   Frame dtype: {display_frame.dtype if display_frame is not None else 'None'}")
            return
        
        # CRITICAL: Always keep a reference to prevent garbage collection
        # Store in a list to keep multiple references if needed
        if not hasattr(self, '_canvas_img_refs'):
            self._canvas_img_refs = []
        self._canvas_img_refs.clear()  # Clear old references
        self._canvas_img_refs.append(photo)  # Keep reference to prevent GC
        
        # OPTIMIZED: Use itemconfig if image already exists, otherwise create new
        # This reduces flickering compared to delete("all")
        # CRITICAL FIX: Check item type before using itemconfig - text items don't support -image option
        existing_items = self.canvas.find_all()
        image_item_id = None
        
        # Find existing image item (if any)
        for item_id in existing_items:
            try:
                item_type = self.canvas.type(item_id)
                if item_type == "image":
                    image_item_id = item_id
                    break
            except:
                continue
        
        # CRITICAL FIX: Center image at canvas center (not display center) to ensure proper fitting
        # The image should be centered in the canvas, which matches the container size
        image_x = canvas_width // 2
        image_y = canvas_height // 2
        
        if self.current_frame_num % 60 == 0:  # Only log every 60 frames
            print(f"🎨 CANVAS UPDATE: frame {self.current_frame_num}, canvas_size={canvas_width}x{canvas_height}, image_pos=({image_x},{image_y})")

        if image_item_id is not None:
            # Update existing image item position and image
            try:
                self.canvas.coords(image_item_id, image_x, image_y)
                self.canvas.itemconfig(image_item_id, image=photo)
            except tk.TclError as e:
                if self.current_frame_num % 60 == 0:
                    print(f"⚠ ITEMCONFIG FAILED: {e}, recreating image")
                # If itemconfig fails, delete and recreate
                self.canvas.delete(image_item_id)
                self.canvas.create_image(image_x, image_y,
                                         image=photo, anchor=tk.CENTER)
        else:
            # No image item exists - delete any text/other items and create new image
            if existing_items:
                self.canvas.delete("all")
            # Create new image item centered in canvas
            new_item = self.canvas.create_image(image_x, image_y,
                                     image=photo, anchor=tk.CENTER)
        
        # Mark this frame as rendered
        self.last_rendered_frame_num = self.current_frame_num
        # Update zoom label if it exists
        if hasattr(self, 'zoom_label') and self.zoom_label:
            self.zoom_label.config(text=f"{self.zoom_level:.1f}x")
        
        # Update frame label
        if hasattr(self, 'frame_label') and self.frame_label:
            self.frame_label.config(text=f"Frame: {self.current_frame_num} / {self.total_frames - 1}")
    
    def render_comparison(self):
        """Render side-by-side comparison of two frames"""
        if self.frame1 is None or self.frame2 is None:
            return
        
        # Load both frames
        frame1_img = self.load_frame(self.frame1)
        frame2_img = self.load_frame(self.frame2)
        
        if frame1_img is None or frame2_img is None:
            return
        
        # Render overlays on each frame with respective highlight IDs
        display_frame1 = self.render_overlays_on_frame(frame1_img.copy(), self.frame1, highlight_id=self.id1)
        display_frame2 = self.render_overlays_on_frame(frame2_img.copy(), self.frame2, highlight_id=self.id2)
        
        # Resize for display (side-by-side, each takes half width)
        # Use larger display size for better visibility when zoomed
        display_height = 700  # Increased from 600 for better visibility
        aspect_ratio = self.width / self.height
        display_width = int(display_height * aspect_ratio)
        
        # Each frame gets half the available width (larger for zoom)
        max_width = 600  # Increased from 450 for better visibility
        if display_width > max_width:
            display_width = max_width
            display_height = int(display_width / aspect_ratio)
        
        display_frame1 = cv2.resize(display_frame1, (display_width, display_height))
        display_frame2 = cv2.resize(display_frame2, (display_width, display_height))
        
        display_frame1 = cv2.cvtColor(display_frame1, cv2.COLOR_BGR2RGB)
        display_frame2 = cv2.cvtColor(display_frame2, cv2.COLOR_BGR2RGB)
        
        # Store original frames for zoom
        self.original_display_frame1 = display_frame1.copy()
        self.original_display_frame2 = display_frame2.copy()
        self.original_display_width = display_width
        self.original_display_height = display_height
        
        # Apply zoom and pan
        display_frame1 = self.apply_zoom_pan(display_frame1, 1)
        display_frame2 = self.apply_zoom_pan(display_frame2, 2)
        
        # Update canvases
        image1 = Image.fromarray(display_frame1)
        photo1 = ImageTk.PhotoImage(image=image1)
        
        image2 = Image.fromarray(display_frame2)
        photo2 = ImageTk.PhotoImage(image=image2)
        
        self.canvas1.delete("all")
        # Canvas size stays at display size (zoom is applied to image, not canvas)
        self.canvas1.config(width=display_width, height=display_height)
        self.canvas1.create_image(display_width // 2, display_height // 2, 
                                   image=photo1, anchor=tk.CENTER)
        # Keep a reference to the PhotoImage object to prevent garbage collection
        if not hasattr(self, '_canvas1_images'):
            self._canvas1_images = []
        self._canvas1_images.clear()
        self._canvas1_images.append(photo1)

        self.canvas2.delete("all")
        # Canvas size stays at display size (zoom is applied to image, not canvas)
        self.canvas2.config(width=display_width, height=display_height)
        self.canvas2.create_image(display_width // 2, display_height // 2, 
                                   image=photo2, anchor=tk.CENTER)
        # Keep a reference to the PhotoImage object to prevent garbage collection
        if not hasattr(self, '_canvas2_images'):
            self._canvas2_images = []
        self._canvas2_images.clear()
        self._canvas2_images.append(photo2)
        
        # Update frame labels
        id1_text = f" (ID {self.id1})" if self.id1 is not None else ""
        id2_text = f" (ID {self.id2})" if self.id2 is not None else ""
        self.frame1_label.config(text=f"Frame: {self.frame1}{id1_text}")
        self.frame2_label.config(text=f"Frame: {self.frame2}{id2_text}")
    
    def load_metadata_manual(self):
        """Manually load overlay metadata file."""
        if not hasattr(self, 'video_path') or self.video_path is None:
            messagebox.showwarning("No Video", "Please load a video file first before loading metadata.")
            return
        
        filename = filedialog.askopenfilename(
            title="Select Overlay Metadata File",
            filetypes=[("JSON files", "*.json"), ("Metadata files", "*_overlay_metadata.json"), ("All files", "*.*")]
        )
        if not filename:
            return
        
        try:
            from overlay_metadata import OverlayMetadata
            from overlay_renderer import OverlayRenderer
            
            # Reset render mode when loading new metadata (forces re-evaluation)
            self.render_mode = None
            
            self.overlay_metadata = OverlayMetadata.load(filename)
            # Get quality settings from metadata (with defaults)
            viz_settings = self.overlay_metadata.visualization_settings
            overlay_quality = viz_settings.get("overlay_quality", "hd")
            render_scale = viz_settings.get("render_scale", 1.0)
            enable_advanced_blending = viz_settings.get("enable_advanced_blending", True)
            enable_motion_blur = viz_settings.get("enable_motion_blur", False)
            motion_blur_amount = viz_settings.get("motion_blur_amount", 1.0)
            use_professional_text = viz_settings.get("use_professional_text", True)
            
            # PERFORMANCE FIX: Disable HD rendering by default for smooth playback
            # HD rendering (render_scale > 1.0) is very expensive and causes stuttering
            # Users can re-enable it if they want, but default to fast SD rendering
            use_hd_for_playback = False  # Disable HD for playback performance (was: overlay_quality != "sd")
            render_scale = 1.0  # Force render scale to 1.0 for performance
            enable_advanced_blending = False  # Disable advanced blending for performance
            enable_motion_blur = False  # Disable motion blur for performance (very expensive)
            use_professional_text = False  # Disable professional text for performance (PIL is slower)
            
            self.overlay_renderer = OverlayRenderer(
                self.overlay_metadata,
                use_hd=use_hd_for_playback,
                render_scale=render_scale,
                quality="sd",  # Force SD quality for performance
                enable_advanced_blending=enable_advanced_blending,
                enable_motion_blur=enable_motion_blur,
                motion_blur_amount=motion_blur_amount,
                use_professional_text=use_professional_text,
                enable_profiling=True
            )
            
            # Update status
            frame_count = len(self.overlay_metadata.overlays)
            coverage = (frame_count / self.total_frames * 100) if self.total_frames > 0 else 0
            messagebox.showinfo(
                "Metadata Loaded",
                f"Successfully loaded overlay metadata:\n\n"
                f"• {frame_count} frames with overlay data\n"
                f"• {coverage:.1f}% coverage\n"
                f"• File: {os.path.basename(filename)}\n\n"
                f"Metadata rendering will be used when available."
            )
            print(f"✓ Manually loaded overlay metadata: {frame_count} frames from {os.path.basename(filename)}")
            
            # Refresh display to use metadata
            self.update_display()
            
        except json.JSONDecodeError as json_err:
            messagebox.showerror(
                "Invalid Metadata",
                f"The metadata file is corrupted:\n\n"
                f"Error: {json_err}\n"
                f"Location: line {json_err.lineno}, column {json_err.colno}\n\n"
                f"You may need to re-run analysis to regenerate the metadata file."
            )
            self.overlay_metadata = None
            self.overlay_renderer = None
        except Exception as e:
            error_msg = str(e)
            # CRITICAL FIX: Handle specific error messages more gracefully
            if "unknown option" in error_msg.lower() or "-image" in error_msg:
                # This error might come from a subprocess call or argument parsing issue
                # Try to provide more helpful error message
                print(f"⚠ Could not load overlay metadata: {error_msg}")
                print(f"   This might be due to a corrupted metadata file or missing dependencies.")
                print(f"   Try re-running analysis to regenerate the metadata file.")
                messagebox.showwarning(
                    "Metadata Load Error",
                    f"Could not load overlay metadata:\n\n{error_msg}\n\n"
                    f"This might be due to:\n"
                    f"• Corrupted metadata file\n"
                    f"• Missing dependencies\n"
                    f"• Incompatible metadata format\n\n"
                    f"Try re-running analysis to regenerate the metadata file."
                )
            else:
                messagebox.showerror("Error", f"Could not load overlay metadata:\n{e}")
                print(f"⚠ Could not load overlay metadata: {e}")
                self.overlay_metadata = None
                self.overlay_renderer = None
    
    def load_overlay_metadata(self, csv_path: str):
        """Load overlay metadata if available (auto-loads when CSV is loaded)."""
        try:
            # Reset render mode when loading new metadata (forces re-evaluation)
            self.render_mode = None
            
            # Prevent duplicate loading - if we already loaded metadata for this CSV, skip
            if hasattr(self, '_last_metadata_path') and self._last_metadata_path == csv_path:
                if hasattr(self, 'overlay_metadata') and self.overlay_metadata is not None:
                    return  # Already loaded
            
            # Look for overlay metadata file (same name as CSV but with _overlay_metadata.json)
            metadata_path = csv_path.replace('_tracking_data.csv', '_overlay_metadata.json')
            if not os.path.exists(metadata_path):
                # Try alternative naming
                metadata_path = csv_path.replace('.csv', '_overlay_metadata.json')
            
            if os.path.exists(metadata_path):
                from overlay_metadata import OverlayMetadata
                from overlay_renderer import OverlayRenderer
                
                try:
                    self.overlay_metadata = OverlayMetadata.load(metadata_path)
                    # OPTIMIZATION: Use SD rendering (not HD) for fastest, most fluid playback
                    # HD rendering involves upscaling/downscaling which causes stuttering
                    # SD rendering uses direct OpenCV drawing (fastest approach)
                    overlay_quality = self.overlay_metadata.visualization_settings.get("overlay_quality", "sd")
                    use_hd_for_playback = False  # Disable HD for playback performance
                    # PERFORMANCE FIX: Disable all expensive features for smooth playback
                    enable_advanced_blending = False
                    enable_motion_blur = False
                    use_professional_text = False
                    self.overlay_renderer = OverlayRenderer(
                        self.overlay_metadata,
                        use_hd=use_hd_for_playback,  # False = SD rendering (fastest)
                        render_scale=1.0,
                        quality="sd",  # Force SD quality
                        enable_advanced_blending=enable_advanced_blending,
                        enable_motion_blur=enable_motion_blur,
                        motion_blur_amount=1.0,
                        use_professional_text=use_professional_text,
                        enable_profiling=True
                    )
                    self._last_metadata_path = csv_path  # Remember we loaded this
                    print(f"✓ Loaded overlay metadata: {len(self.overlay_metadata.overlays)} frames")
                except json.JSONDecodeError as json_err:
                    print(f"⚠ Overlay metadata JSON is corrupted: {json_err}")
                    print(f"   File: {metadata_path}")
                    print(f"   Location: line {json_err.lineno}, column {json_err.colno}")
                    print(f"   You may need to re-run analysis to regenerate the metadata file.")
                    self.overlay_metadata = None
                    self.overlay_renderer = None
                except Exception as e:
                    error_msg = str(e)
                    # CRITICAL FIX: Handle specific error messages more gracefully
                    if "unknown option" in error_msg.lower() or "-image" in error_msg:
                        print(f"⚠ Could not load overlay metadata: {error_msg}")
                        print(f"   This might be due to a corrupted metadata file or missing dependencies.")
                        print(f"   Try re-running analysis to regenerate the metadata file.")
                    else:
                        print(f"⚠ Could not load overlay metadata: {e}")
                    self.overlay_metadata = None
                    self.overlay_renderer = None
            else:
                self.overlay_metadata = None
                self.overlay_renderer = None
        except Exception as e:
            print(f"⚠ Could not load overlay metadata: {e}")
            self.overlay_metadata = None
            self.overlay_renderer = None
    
    def load_field_calibration(self):
        """Load field calibration and compute homography matrix for perspective view"""
        try:
            # Try to import the functions we need
            try:
                from combined_analysis_optimized import load_field_calibration, compute_homography_matrix
            except ImportError:
                # If import fails, try direct import
                import combined_analysis_optimized
                load_field_calibration = combined_analysis_optimized.load_field_calibration
                compute_homography_matrix = combined_analysis_optimized.compute_homography_matrix
            
            # Load calibration data using the same function as the analysis
            calibration_data = load_field_calibration()
            
            if calibration_data is None:
                print(f"⚠ No field calibration found - Perspective view unavailable")
                if hasattr(self, 'perspective_info_label'):
                    self.perspective_info_label.config(
                        text="No calibration found - use 'Calibrate Field'",
                        foreground="red"
                    )
                self.homography_matrix = None
                self.field_dims = None
                return
            
            if "points" not in calibration_data or len(calibration_data.get("points", [])) < 4:
                print(f"⚠ Field calibration incomplete - need at least 4 points")
                if hasattr(self, 'perspective_info_label'):
                    self.perspective_info_label.config(
                        text="Calibration incomplete - need 4+ points",
                        foreground="orange"
                    )
                self.homography_matrix = None
                self.field_dims = None
                return
            
            # Compute homography matrix
            # Use video dimensions if available, otherwise use default
            frame_width = self.width if hasattr(self, 'width') and self.width > 0 else None
            frame_height = self.height if hasattr(self, 'height') and self.height > 0 else None
            
            self.homography_matrix, self.field_dims = compute_homography_matrix(
                calibration_data, frame_width, frame_height
            )
            
            if self.homography_matrix is not None and self.field_dims is not None:
                print(f"✓ Field calibration loaded - Perspective view available")
                print(f"   Field dimensions: {self.field_dims[0]:.1f}m x {self.field_dims[1]:.1f}m")
                if hasattr(self, 'perspective_info_label'):
                    self.perspective_info_label.config(
                        text=f"Field: {self.field_dims[0]:.1f}m x {self.field_dims[1]:.1f}m",
                        foreground="green"
                    )
            else:
                print(f"⚠ Could not compute homography from field calibration")
                print(f"   Calibration data: {calibration_data.keys()}")
                print(f"   Points: {len(calibration_data.get('points', []))} points")
                if hasattr(self, 'perspective_info_label'):
                    self.perspective_info_label.config(
                        text="Calibration invalid - check field points",
                        foreground="orange"
                    )
                self.homography_matrix = None
                self.field_dims = None
                
        except Exception as e:
            print(f"⚠ Could not load field calibration: {e}")
            import traceback
            traceback.print_exc()
            self.homography_matrix = None
            self.field_dims = None
            if hasattr(self, 'perspective_info_label'):
                self.perspective_info_label.config(
                    text=f"Error loading calibration: {str(e)[:30]}...",
                    foreground="red"
                )
    
    def toggle_perspective_view(self):
        """Toggle perspective view on/off"""
        if self.show_perspective_view.get():
            if self.homography_matrix is None:
                messagebox.showwarning(
                    "Perspective View Unavailable",
                    "Field calibration is required for perspective view.\n\n"
                    "Please calibrate the field using 'Calibrate Field' in the main GUI."
                )
                self.show_perspective_view.set(False)
                return
        self.update_display()
    
    def apply_perspective_transform(self, frame):
        """Apply perspective transformation to create top-down view"""
        if self.homography_matrix is None or self.field_dims is None:
            return frame
        
        try:
            field_length, field_width = self.field_dims
            
            # Calculate output size (in pixels, assuming ~10 pixels per meter for good resolution)
            pixels_per_meter = 10
            output_width = int(field_length * pixels_per_meter)
            output_height = int(field_width * pixels_per_meter)
            
            # Apply perspective transformation
            warped = cv2.warpPerspective(frame, self.homography_matrix, (output_width, output_height))
            
            return warped
        except Exception as e:
            print(f"⚠ Error applying perspective transform: {e}")
            return frame
    
    def render_overlays_on_frame(self, display_frame, frame_num, highlight_id=None, force_mode=None, skip_expensive_effects=False):
        """Render overlays on a specific frame - uses consistent rendering mode to prevent bouncing
        
        Args:
            skip_expensive_effects: If True, skip expensive visual effects (glow, shadow, particles, pulse) for faster rendering during playback
        """
        # OPTIMIZATION: Early return if nothing to render
        # Note: Don't check show_analytics here - analytics can be shown even if players/ball are hidden
        if not self.show_players.get() and not self.show_ball.get() and not self.show_trajectories.get() and not self.show_field_zones.get() and not self.show_analytics.get():
            return display_frame  # Skip all rendering if nothing to show
        # Apply perspective transformation if enabled (before overlays)
        if self.show_perspective_view.get() and self.homography_matrix is not None:
            display_frame = self.apply_perspective_transform(display_frame)
            # Update dimensions for perspective view
            if display_frame is not None and display_frame.size > 0:
                self.width = display_frame.shape[1]
                self.height = display_frame.shape[0]
        
        # CRITICAL FIX: Check if video is already analyzed (has overlays baked in)
        # If video filename contains "_analyzed" or "_overlay", skip overlay rendering to avoid double-rendering
        if self.video_path:
            video_basename = os.path.basename(self.video_path).lower()
            if "_analyzed" in video_basename or "_overlay" in video_basename:
                # If video is already analyzed, skip overlay rendering to avoid double-rendering
                # The video already has all overlays (gray ellipses, labels, etc.) baked in
                # Return frame as-is to prevent drawing overlays on top of existing overlays
                return display_frame
        
        # CSV MODE: Default to fast CSV rendering (metadata is opt-in only)
        # Metadata mode is experimental and slower - only use if explicitly selected
        frame_start = time.perf_counter()
        mode = self._choose_render_mode(frame_num, force_mode)
        # Only use metadata if explicitly selected AND enabled
        if mode == 'metadata' and self.use_overlay_metadata.get() and (self.overlay_metadata is not None and 
                                  self.overlay_renderer is not None and
                                  frame_num in self.overlay_metadata.overlays):
            # Try hybrid mode: metadata for visuals, CSV for analytics
            if self.overlay_metadata is not None and frame_num in self.overlay_metadata.overlays:
                try:
                    # OPTIMIZATION: Early return if nothing to render
                    if not self.show_players.get() and not self.show_ball.get():
                        self._record_frame_duration(frame_start, frame_num)
                        return display_frame
                    
                    frame_copy = display_frame.copy()
                    
                    # Build visualization settings override (cached)
                    if not hasattr(self, '_cached_viz_settings_override') or self._viz_settings_changed:
                        viz_settings_override = {
                            # Style settings
                            "viz_style": self.viz_style.get(),
                            "viz_color_mode": self.viz_color_mode.get(),
                            # Show/hide settings
                            "show_bounding_boxes": self.show_player_boxes.get(),
                            "show_circles_at_feet": self.show_player_circles.get(),
                            "show_player_labels": self.show_player_labels.get(),
                            # Box settings
                            "box_thickness": self._safe_get_int(self.box_thickness, 2),
                            "box_shrink_factor": self._safe_get_double(self.box_shrink_factor, 0.2),
                            "player_viz_alpha": self._safe_get_int(self.player_viz_alpha, 255),
                            "use_custom_box_color": self.use_custom_box_color.get(),
                            "box_color": self._get_box_color_bgr() if self.use_custom_box_color.get() else None,
                            # Label settings
                            "label_type": self.label_type.get(),
                            "label_font_face": self.label_font_face.get(),
                            "label_font_scale": self._safe_get_double(self.label_font_scale, 0.6),
                            "use_custom_label_color": self.use_custom_label_color.get(),
                            "label_color": self._get_label_color_bgr() if self.use_custom_label_color.get() else None,
                            "label_custom_text": self.label_custom_text.get(),
                            # Feet marker settings
                            "feet_marker_style": self.feet_marker_style.get(),
                            "feet_marker_opacity": self._safe_get_int(self.feet_marker_opacity, 255),
                            "feet_marker_enable_glow": self.feet_marker_enable_glow.get(),
                            "feet_marker_glow_intensity": self._safe_get_int(self.feet_marker_glow_intensity, 50),
                            "feet_marker_enable_shadow": self.feet_marker_enable_shadow.get(),
                            "feet_marker_shadow_offset": self._safe_get_int(self.feet_marker_shadow_offset, 3),
                            "feet_marker_shadow_opacity": self._safe_get_int(self.feet_marker_shadow_opacity, 128),
                            "feet_marker_enable_gradient": self.feet_marker_enable_gradient.get(),
                            "feet_marker_enable_pulse": self.feet_marker_enable_pulse.get(),
                            "feet_marker_pulse_speed": self._safe_get_double(self.feet_marker_pulse_speed, 2.0),
                            "feet_marker_enable_particles": self.feet_marker_enable_particles.get(),
                            "feet_marker_particle_count": self._safe_get_int(self.feet_marker_particle_count, 5),
                            "feet_marker_vertical_offset": self._safe_get_int(self.feet_marker_vertical_offset, 50),
                            # Prediction settings
                            "prediction_duration": self._safe_get_int(self.prediction_duration, 30),
                            "prediction_size": self._safe_get_int(self.prediction_size, 5),
                            "prediction_style": self.prediction_style.get(),
                            "prediction_color": (self._safe_get_int(self.prediction_color_b, 0), self._safe_get_int(self.prediction_color_g, 0), self._safe_get_int(self.prediction_color_r, 255)),
                            "prediction_color_alpha": self._safe_get_int(self.prediction_color_alpha, 128),
                        }
                        self._cached_viz_settings_override = viz_settings_override
                        self._viz_settings_changed = False
                    else:
                        viz_settings_override = self._cached_viz_settings_override
                    
                    # HYBRID MODE: Render visual enhancements from metadata (trajectories, effects, zones, etc.)
                    # BUT skip analytics - CSV will handle analytics separately
                    render_start = time.perf_counter()
                    rendered_frame = self.overlay_renderer.render_frame(
                        frame_copy,
                        frame_num,
                        show_players=self.show_players.get(),
                        show_ball=self.show_ball.get(),
                        show_trajectories=self.show_trajectories.get(),
                        show_field_zones=self.show_field_zones.get(),
                        show_analytics=False,  # CRITICAL: CSV handles analytics, not metadata
                        show_ball_possession=self.show_ball_possession.get(),
                        show_predicted_boxes=self.show_predicted_boxes.get(),
                        show_yolo_boxes=self.show_yolo_boxes.get(),
                        viz_settings_override=viz_settings_override
                    )
                    
                    duration = time.perf_counter() - render_start
                    self.profiling_stats["metadata_time"] += duration
                    self.profiling_stats["metadata_count"] += 1
                    self._accumulate_overlay_profile(self.overlay_renderer.last_profile)
                    
                    # HYBRID MODE: Now add CSV analytics on top of metadata visuals
                    # This gives us best of both: rich visuals + fast analytics
                    if self.show_analytics.get() and hasattr(self, 'analytics_data') and frame_num in self.analytics_data:
                        # Use CSV rendering for analytics only (overlay on top of metadata visuals)
                        rendered_frame = self._render_analytics_from_csv(rendered_frame, frame_num)
                    
                    self._record_frame_duration(frame_start, frame_num)
                    return rendered_frame
                except Exception as e:
                    # Fallback to CSV-only if metadata renderer fails
                    if frame_num % 100 == 0:
                        print(f"⚠ Metadata renderer error on frame {frame_num}: {e}, falling back to CSV-only")
                    csv_start = time.perf_counter()
                    csv_result = self._render_overlays_from_csv(display_frame, frame_num, highlight_id)
                    duration = time.perf_counter() - csv_start
                    self.profiling_stats["csv_time"] += duration
                    self.profiling_stats["csv_count"] += 1
                    self._record_frame_duration(frame_start, frame_num)
                    return csv_result
            else:
                # Frame not in metadata - use CSV rendering (with HD upgrade)
                csv_start = time.perf_counter()
                csv_result = self._render_overlays_from_csv(display_frame, frame_num, highlight_id)
                duration = time.perf_counter() - csv_start
                self.profiling_stats["csv_time"] += duration
                self.profiling_stats["csv_count"] += 1
                self._record_frame_duration(frame_start, frame_num)
                return csv_result
        else:
            # Use CSV-based rendering for all frames (with HD upgrade)
            csv_start = time.perf_counter()
            csv_result = self._render_overlays_from_csv(display_frame, frame_num, highlight_id)
            duration = time.perf_counter() - csv_start
            self.profiling_stats["csv_time"] += duration
            self.profiling_stats["csv_count"] += 1
            self._record_frame_duration(frame_start, frame_num)
            return csv_result

    def _record_frame_duration(self, frame_start, frame_num):
        """Record total time spent processing a frame and log if needed."""
        duration = time.perf_counter() - frame_start
        self.profiling_stats["frame_time"] += duration
        self.profiling_stats["frame_count"] += 1
        self._maybe_log_profile(frame_num)

    def _accumulate_overlay_profile(self, profile):
        """Collect overlay renderer timing breakdowns."""
        if not profile:
            return
        stats = self.profiling_stats
        for key, value in profile.items():
            count_key = key.replace("_time", "_count")
            stats[key] = stats.get(key, 0.0) + value
            stats[count_key] = stats.get(count_key, 0) + 1

    def _maybe_log_profile(self, frame_num):
        """Log profiling summary every 200 frames for diagnostics."""
        if frame_num - self._profile_last_log_frame < 200:
            return
        stats = self.profiling_stats
        total_frames = stats["frame_count"]
        if total_frames == 0:
            return
        avg_frame = stats["frame_time"] / total_frames
        meta_avg = stats["metadata_time"] / max(1, stats["metadata_count"])
        csv_avg = stats["csv_time"] / max(1, stats["csv_count"])
        hd_avg = stats["hd_prepare_time"] / max(1, stats["hd_prepare_count"])
        field_avg = stats["field_zones_time"] / max(1, stats["field_zones_count"])
        traj_avg = stats["trajectories_time"] / max(1, stats["trajectories_count"])
        players_avg = stats["players_time"] / max(1, stats["players_count"])
        ball_avg = stats["ball_time"] / max(1, stats["ball_count"])
        downscale_avg = stats["downscale_time"] / max(1, stats["downscale_count"])
        print(
            f"🧪 Profiling frame {frame_num}: avg frame={avg_frame*1000:.2f}ms "
            f"(metadata avg={meta_avg*1000:.2f}ms/{stats['metadata_count']} calls, "
            f"csv avg={csv_avg*1000:.2f}ms/{stats['csv_count']} calls; "
            f"hd prep avg={hd_avg*1000:.2f}ms, field={field_avg*1000:.2f}ms, "
            f"traj={traj_avg*1000:.2f}ms, players={players_avg*1000:.2f}ms, "
            f"ball={ball_avg*1000:.2f}ms, downscale={downscale_avg*1000:.2f}ms)"
        )
        self._profile_last_log_frame = frame_num

    def _request_overlay_render(self, frame_num, frame):
        """Queue a metadata overlay render request."""
        if frame is None:
            return
        if self.overlay_metadata is None or len(getattr(self.overlay_metadata, 'overlays', {})) == 0:
            return
        if self.overlay_render_mode.get() != "metadata":
            return
        with self.overlay_render_lock:
            self.overlay_render_request = (frame_num, frame)
        self.overlay_worker_event.set()

    def _get_overlay_result(self, frame_num):
        """Return the latest rendered metadata frame if it matches or is close."""
        with self.overlay_render_lock:
            result = self.overlay_render_result
        if not result:
            return None
        rendered_frame_num, rendered_frame = result
        if frame_num >= rendered_frame_num and frame_num - rendered_frame_num < self.overlay_metadata_stride:
            return rendered_frame
        return None

    def _overlay_worker_loop(self):
        """Background thread that renders metadata overlays so the main thread stays responsive."""
        while self.overlay_worker_running:
            self.overlay_worker_event.wait(timeout=0.1)
            self.overlay_worker_event.clear()
            if not self.overlay_worker_running:
                break
            with self.overlay_render_lock:
                request = self.overlay_render_request
                self.overlay_render_request = None
            if not request:
                continue
            frame_num, frame = request
            if frame_num - self.overlay_last_rendered_frame < self.overlay_metadata_stride:
                continue
            try:
                rendered = self.render_overlays_on_frame(frame, frame_num, force_mode="metadata")
                with self.overlay_render_lock:
                    self.overlay_render_result = (frame_num, rendered)
                    self.overlay_last_rendered_frame = frame_num
            except Exception as e:
                print(f"⚠ Overlay worker failed to render frame {frame_num}: {e}")

    def _stop_overlay_worker(self):
        """Signal the overlay worker to stop and wait for it."""
        self.overlay_worker_running = False
        self.overlay_worker_event.set()
        if hasattr(self, 'overlay_worker_thread') and self.overlay_worker_thread.is_alive():
            self.overlay_worker_thread.join(timeout=0.5)

    def _choose_render_mode(self, frame_num, force_mode=None):
        """Choose rendering mode (metadata vs csv), respecting overrides."""
        if force_mode:
            self.render_mode = force_mode
            return force_mode
        if self.overlay_render_mode.get() == "csv":
            if self.render_mode != "csv":
                self.render_mode = "csv"
            return "csv"
        if self.render_mode is None:
            self._auto_determine_render_mode(frame_num)
        return self.render_mode

    def _auto_determine_render_mode(self, frame_num):
        """Auto-detect render mode based on available metadata, analytics, etc."""
        # METADATA IS OPT-IN ONLY: Default to fast CSV mode
        # Metadata mode is experimental and slower - only use if explicitly enabled
        
        # Check if user explicitly wants metadata mode (must be selected in dropdown AND enabled)
        if (self.overlay_render_mode.get() == "metadata" and
            self.use_overlay_metadata.get() and
            self.overlay_renderer is not None and
            self.overlay_metadata is not None and
            len(self.overlay_metadata.overlays) > 0):
            total_frames = getattr(self, 'total_frames', 0)
            if total_frames > 0:
                coverage = len(self.overlay_metadata.overlays) / total_frames
                # Require high coverage (60%+) for metadata mode
                if coverage > 0.6:
                    self.render_mode = 'metadata'  # Will use hybrid mode (metadata visuals + CSV analytics)
                    if frame_num == 0:
                        print(f"✓ Using metadata mode (experimental, slower): {len(self.overlay_metadata.overlays)}/{total_frames} frames, {coverage*100:.1f}% coverage")
                    return self.render_mode
                else:
                    self.render_mode = 'csv'
                    if frame_num == 0:
                        print(f"ℹ Overlay metadata coverage too low ({coverage*100:.1f}% < 60%) - using CSV-only mode (fast & reliable)")
                    return self.render_mode
            else:
                self.render_mode = 'csv'
                if frame_num == 0:
                    print(f"ℹ Cannot determine total frames - using CSV-only mode (fast & reliable)")
                return self.render_mode
        
        # Default to CSV (fast & reliable)
        self.render_mode = 'csv'
        if frame_num == 0:
            if self.overlay_render_mode.get() == "metadata" and not self.use_overlay_metadata.get():
                print("ℹ Metadata mode selected but disabled - using CSV-only mode (fast & reliable)")
            elif self.overlay_render_mode.get() != "metadata":
                print("ℹ Using CSV-only mode (fast & reliable, HD graphics enabled)")
            elif self.overlay_metadata is None:
                print("ℹ No overlay metadata found - using CSV-only mode (fast & reliable)")
            elif len(self.overlay_metadata.overlays) == 0:
                print("ℹ Overlay metadata is empty - using CSV-only mode (fast & reliable)")
        return self.render_mode

    def _on_overlay_mode_change(self, *args):
        """Reset state when overlay mode toggle changes."""
        with self.overlay_render_lock:
            self.overlay_render_request = None
            self.overlay_render_result = None
            self.overlay_last_rendered_frame = -1
        self.render_mode = None
        self.overlay_settings_hash = None
        self._viz_settings_changed = True
        self.update_display()
    
    def _draw_enhanced_feet_marker_simple(self, frame, center, axes, style, color, opacity,
                                          enable_glow, glow_intensity, enable_shadow,
                                          shadow_offset, shadow_opacity, enable_pulse,
                                          pulse_speed, frame_num, enable_particles, particle_count,
                                          outline_thickness=0):
        """
        Simplified enhanced feet marker rendering for CSV mode.
        This is a basic implementation - for full features, use overlay metadata mode.
        """
        import math
        x, y = center
        axes_w, axes_h = axes
        
        # Apply pulse effect if enabled
        if enable_pulse:
            pulse_phase = (frame_num * pulse_speed / self.fps) % (2 * math.pi)
            pulse_scale = 1.0 + 0.2 * math.sin(pulse_phase)  # 20% size variation
            axes_w = int(axes_w * pulse_scale)
            axes_h = int(axes_h * pulse_scale)
        
        # Draw shadow if enabled
        if enable_shadow:
            shadow_color = (0, 0, 0)  # Black shadow
            shadow_x = x + shadow_offset
            shadow_y = y + shadow_offset
            # Draw shadow with opacity
            overlay = frame.copy()
            cv2.ellipse(overlay, (shadow_x, shadow_y), (axes_w, axes_h), 0, 0, 360, shadow_color, -1)
            cv2.addWeighted(overlay, shadow_opacity / 255.0, frame, 
                           1 - (shadow_opacity / 255.0), 0, frame)
        
        # Draw glow if enabled
        if enable_glow:
            glow_size = int(glow_intensity / 10)  # Scale glow intensity
            for i in range(glow_size, 0, -1):
                glow_alpha = (glow_intensity / 100.0) * (1.0 - i / glow_size)
                glow_color = tuple(int(c * (1.0 + glow_alpha)) for c in color)
                cv2.ellipse(frame, (x, y), (axes_w + i, axes_h + i), 0, 0, 360, glow_color, 2)
        
        # Calculate base size from width and height settings
        # Use average for circular shapes, or use both dimensions for shapes that support it
        base_radius = (axes_w + axes_h) // 2  # Average radius for circular shapes
        max_radius = max(axes_w, axes_h)  # Maximum radius for some shapes
        
        # Draw main marker based on style
        if style == "none":
            # Don't draw anything - just skip
            pass
        elif style == "circle":
            # Circle: use average of width and height for true circle
            circle_radius = base_radius
            if opacity < 255:
                overlay = frame.copy()
                cv2.circle(overlay, (x, y), circle_radius, color, -1)
                cv2.addWeighted(overlay, opacity / 255.0, frame, 1 - (opacity / 255.0), 0, frame)
            else:
                cv2.circle(frame, (x, y), circle_radius, color, -1)
        elif style == "diamond":
            # Draw diamond shape - uses both width and height
            points = np.array([
                [x, y - axes_h],
                [x + axes_w, y],
                [x, y + axes_h],
                [x - axes_w, y]
            ], np.int32)
            if opacity < 255:
                overlay = frame.copy()
                cv2.fillPoly(overlay, [points], color)
                cv2.addWeighted(overlay, opacity / 255.0, frame, 1 - (opacity / 255.0), 0, frame)
            else:
                cv2.fillPoly(frame, [points], color)
        elif style == "star":
            # Draw simple star (5-point) - use average radius for consistent sizing
            import math
            outer_radius = base_radius
            inner_radius = base_radius // 2
            points = []
            for i in range(10):
                angle = i * math.pi / 5
                if i % 2 == 0:
                    r = outer_radius
                else:
                    r = inner_radius
                px = int(x + r * math.cos(angle))
                py = int(y + r * math.sin(angle))
                points.append([px, py])
            if opacity < 255:
                overlay = frame.copy()
                cv2.fillPoly(overlay, [np.array(points, np.int32)], color)
                cv2.addWeighted(overlay, opacity / 255.0, frame, 1 - (opacity / 255.0), 0, frame)
            else:
                cv2.fillPoly(frame, [np.array(points, np.int32)], color)
        elif style == "hexagon":
            # Draw hexagon - use average radius for consistent sizing
            import math
            hex_radius = base_radius
            points = []
            for i in range(6):
                angle = i * math.pi / 3
                px = int(x + hex_radius * math.cos(angle))
                py = int(y + hex_radius * math.sin(angle))
                points.append([px, py])
            if opacity < 255:
                overlay = frame.copy()
                cv2.fillPoly(overlay, [np.array(points, np.int32)], color)
                cv2.addWeighted(overlay, opacity / 255.0, frame, 1 - (opacity / 255.0), 0, frame)
            else:
                cv2.fillPoly(frame, [np.array(points, np.int32)], color)
        if style == "arrow":
            # Draw arrow pointing up - uses height for length, width for base
            arrow_length = axes_h * 2
            arrow_width = axes_w
            points = np.array([
                [x, y - arrow_length],  # Tip
                [x - arrow_width // 2, y - arrow_length // 2],  # Left base
                [x - arrow_width // 4, y - arrow_length // 2],  # Left inner
                [x - arrow_width // 4, y],  # Left bottom
                [x + arrow_width // 4, y],  # Right bottom
                [x + arrow_width // 4, y - arrow_length // 2],  # Right inner
                [x + arrow_width // 2, y - arrow_length // 2],  # Right base
            ], np.int32)
            if opacity < 255:
                overlay = frame.copy()
                cv2.fillPoly(overlay, [points], color)
                cv2.addWeighted(overlay, opacity / 255.0, frame, 1 - (opacity / 255.0), 0, frame)
            else:
                cv2.fillPoly(frame, [points], color)
        elif style == "ring":
            # Draw ring (hollow circle) - use average for circular ring
            ring_radius = base_radius
            if opacity < 255:
                overlay = frame.copy()
                cv2.circle(overlay, (x, y), ring_radius, color, 3)
                cv2.addWeighted(overlay, opacity / 255.0, frame, 1 - (opacity / 255.0), 0, frame)
            else:
                cv2.circle(frame, (x, y), ring_radius, color, 3)
        elif style == "ellipse":
            # Ellipse: use both width and height dimensions
            if opacity < 255:
                overlay = frame.copy()
                cv2.ellipse(overlay, (x, y), (axes_w, axes_h), 0, 0, 360, color, -1)
                cv2.addWeighted(overlay, opacity / 255.0, frame, 1 - (opacity / 255.0), 0, frame)
            else:
                cv2.ellipse(frame, (x, y), (axes_w, axes_h), 0, 0, 360, color, -1)
        else:
            # Fallback for glow, pulse, etc. - use average for circular shape
            fallback_radius = base_radius
            if opacity < 255:
                overlay = frame.copy()
                cv2.circle(overlay, (x, y), fallback_radius, color, -1)
                cv2.addWeighted(overlay, opacity / 255.0, frame, 1 - (opacity / 255.0), 0, frame)
            else:
                cv2.circle(frame, (x, y), fallback_radius, color, -1)
        
        # Draw particles if enabled
        if enable_particles:
            import random
            random.seed(frame_num)  # Deterministic particles
            for _ in range(particle_count):
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(axes_w, axes_w * 2)
                px = int(x + distance * math.cos(angle))
                py = int(y + distance * math.sin(angle))
                cv2.circle(frame, (px, py), 2, color, -1)
        
        # Draw outline only if thickness > 0
        # Use appropriate shape for outline based on style
        if outline_thickness > 0:
            if style == "circle" or style == "ring":
                # Circular outline for circle and ring
                outline_radius = base_radius
                cv2.circle(frame, (x, y), outline_radius, (255, 255, 255), outline_thickness)
            elif style == "ellipse":
                # Elliptical outline for ellipse
                cv2.ellipse(frame, (x, y), (axes_w, axes_h), 0, 0, 360, (255, 255, 255), outline_thickness)
            else:
                # For other shapes, draw a circular outline as fallback
                outline_radius = base_radius
                cv2.circle(frame, (x, y), outline_radius, (255, 255, 255), outline_thickness)
    
    def _render_overlays_from_csv(self, display_frame, frame_num, highlight_id=None):
        """Render overlays from CSV data (original method)"""
        # Safety check: ensure frame is valid
        if display_frame is None:
            print(f"⚠ Error: display_frame is None for frame {frame_num}")
            return None
        
        if display_frame.size == 0:
            print(f"⚠ Error: display_frame is empty for frame {frame_num}")
            return display_frame
        
        # Ensure frame is in BGR format (OpenCV format)
        if len(display_frame.shape) != 3 or display_frame.shape[2] != 3:
            print(f"⚠ Error: Invalid frame shape {display_frame.shape} for frame {frame_num}")
            return display_frame
        
        # Draw ball trail with interpolation for sparse detections
        if self.show_ball_trail.get() and self.ball_data:
            # Build trail from recent frames with interpolation
            trail_points = []
            trail_frames = []
            h, w = display_frame.shape[:2]
            
            for i in range(max(0, frame_num - 64), frame_num + 1):
                if i in self.ball_data:
                    ball_pos = self.ball_data[i]
                    # Scale ball coordinates if needed (same logic as players)
                    ball_x_float, ball_y_float = float(ball_pos[0]), float(ball_pos[1])
                    
                    # Check if coordinates need scaling (same as player coordinate scaling)
                    if hasattr(self, 'original_video_width') and hasattr(self, 'original_video_height') and self.original_video_width > 0 and self.original_video_height > 0:
                        scale_x = w / self.original_video_width if self.original_video_width != w else 1.0
                        scale_y = h / self.original_video_height if self.original_video_height != h else 1.0
                        if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                            ball_x_float = ball_x_float * scale_x
                            ball_y_float = ball_y_float * scale_y
                    elif hasattr(self, 'width') and hasattr(self, 'height') and self.width > 0 and self.height > 0:
                        scale_x = w / self.width if self.width != w else 1.0
                        scale_y = h / self.height if self.height != h else 1.0
                        if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                            ball_x_float = ball_x_float * scale_x
                            ball_y_float = ball_y_float * scale_y
                    
                    # Clamp to frame bounds
                    ball_x_scaled = int(max(0, min(ball_x_float, w - 1)))
                    ball_y_scaled = int(max(0, min(ball_y_float, h - 1)))
                    trail_points.append((ball_x_scaled, ball_y_scaled))
                    trail_frames.append(i)
            
            if len(trail_points) > 1:
                # Interpolate between points to handle gaps in detection
                interpolated_points = []
                for idx in range(len(trail_points) - 1):
                    p1 = trail_points[idx]
                    p2 = trail_points[idx + 1]
                    f1 = trail_frames[idx]
                    f2 = trail_frames[idx + 1]
                    
                    # Add first point
                    interpolated_points.append(p1)
                    
                    # Interpolate if gap is small (<= 10 frames) to avoid long jumps
                    if f2 - f1 <= 10 and f2 > f1:
                        # Linear interpolation between frames
                        for f in range(f1 + 1, f2):
                            t = (f - f1) / (f2 - f1)
                            interp_x = int(p1[0] * (1 - t) + p2[0] * t)
                            interp_y = int(p1[1] * (1 - t) + p2[1] * t)
                            interpolated_points.append((interp_x, interp_y))
                
                # Add last point
                if len(trail_points) > 0:
                    interpolated_points.append(trail_points[-1])
                
                # Draw trail with fade effect (newer = brighter) using HD renderer
                if len(interpolated_points) > 1:
                    for i in range(len(interpolated_points) - 1):
                        # Fade effect: newer points are brighter
                        fade_factor = i / max(1, len(interpolated_points) - 1)
                        alpha = 0.3 + 0.7 * (1 - fade_factor)  # 0.3 to 1.0
                        trail_color = (int(255 * alpha), 0, 0)  # Red with fade
                        thickness = max(1, int(3 * alpha))
                        cv2.line(display_frame, interpolated_points[i], interpolated_points[i+1], 
                                trail_color, thickness)
        
        # Draw ball trajectory overlay (Kinovea-style) - before drawing current ball
        if self.show_ball_trajectory.get() and self.ball_trajectory:
            self._draw_ball_trajectory_overlay(display_frame, frame_num)
        
        # Draw ball with consistent color scheme and coordinate scaling
        if self.show_ball.get() and frame_num in self.ball_data:
            ball_pos = self.ball_data[frame_num]
            ball_x_float, ball_y_float = float(ball_pos[0]), float(ball_pos[1])
            h, w = display_frame.shape[:2]
            
            # Check if coordinates are normalized (0-1) or pixel coordinates
            # If coordinates are between 0-1, they're normalized (scale up)
            if 0.0 <= ball_x_float <= 1.0 and 0.0 <= ball_y_float <= 1.0:
                # Normalized coordinates - scale up to pixel coordinates
                ball_x_float = ball_x_float * w
                ball_y_float = ball_y_float * h
            # Scale ball coordinates if needed (same logic as players)
            elif hasattr(self, 'original_video_width') and hasattr(self, 'original_video_height') and self.original_video_width > 0 and self.original_video_height > 0:
                scale_x = w / self.original_video_width if self.original_video_width != w else 1.0
                scale_y = h / self.original_video_height if self.original_video_height != h else 1.0
                if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                    ball_x_float = ball_x_float * scale_x
                    ball_y_float = ball_y_float * scale_y
            elif hasattr(self, 'width') and hasattr(self, 'height') and self.width > 0 and self.height > 0:
                scale_x = w / self.width if self.width != w else 1.0
                scale_y = h / self.height if self.height != h else 1.0
                if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                    ball_x_float = ball_x_float * scale_x
                    ball_y_float = ball_y_float * scale_y
            
            # Clamp to frame bounds
            ball_x = int(max(0, min(ball_x_float, w - 1)))
            ball_y = int(max(0, min(ball_y_float, h - 1)))
            
            # Debug: Log ball drawing for first few frames
            if frame_num < 5 or frame_num % 100 == 0:
                print(f"[DEBUG] Frame {frame_num}: Drawing ball at ({ball_x}, {ball_y}) from original ({ball_pos[0]:.1f}, {ball_pos[1]:.1f}), display_size={w}x{h}")
            
            ball_color = (0, 0, 255)  # Red (consistent with trail)
            ball_radius = 12
            
            # Draw ball with HD renderer for better quality
            self.csv_hd_renderer.draw_crisp_circle(
                display_frame, 
                (ball_x, ball_y), 
                ball_radius, 
                ball_color, 
                3
            )
            # Draw inner circle for better visibility
            self.csv_hd_renderer.draw_crisp_circle(
                display_frame, 
                (ball_x, ball_y), 
                ball_radius - 3, 
                (255, 255, 255), 
                -1
            )
            
            if self.show_ball_label.get():
                self.csv_hd_renderer.draw_crisp_text(
                    display_frame,
                    "Ball",
                    (ball_x + 18, ball_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    ball_color,
                    2,
                    outline_color=(255, 255, 255),
                    outline_thickness=2
                )
        
        # Draw ball possession indicator (triangle above player closest to ball)
        if self.show_ball_possession.get() and frame_num in self.ball_data and frame_num in self.player_data:
            ball_pos = self.ball_data[frame_num]
            ball_x_float, ball_y_float = float(ball_pos[0]), float(ball_pos[1])
            h, w = display_frame.shape[:2]
            
            # Scale ball coordinates (same as above)
            if hasattr(self, 'original_video_width') and hasattr(self, 'original_video_height') and self.original_video_width > 0 and self.original_video_height > 0:
                scale_x = w / self.original_video_width if self.original_video_width != w else 1.0
                scale_y = h / self.original_video_height if self.original_video_height != h else 1.0
                if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                    ball_x_float = ball_x_float * scale_x
                    ball_y_float = ball_y_float * scale_y
            elif hasattr(self, 'width') and hasattr(self, 'height') and self.width > 0 and self.height > 0:
                scale_x = w / self.width if self.width != w else 1.0
                scale_y = h / self.height if self.height != h else 1.0
                if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                    ball_x_float = ball_x_float * scale_x
                    ball_y_float = ball_y_float * scale_y
            
            ball_x = int(max(0, min(ball_x_float, w - 1)))
            ball_y = int(max(0, min(ball_y_float, h - 1)))
            players = self.player_data[frame_num]
            
            # Find player closest to ball (using scaled coordinates)
            min_distance = float('inf')
            closest_player_id = None
            closest_player_pos = None
            
            for player_id, player_info in players.items():
                if len(player_info) >= 2:
                    # Player coordinates are already scaled in the player rendering section above
                    # But we need to get the scaled coordinates here too
                    px_float, py_float = float(player_info[0]), float(player_info[1])
                    
                    # Scale player coordinates if needed (same logic as player rendering)
                    if hasattr(self, 'original_video_width') and hasattr(self, 'original_video_height') and self.original_video_width > 0 and self.original_video_height > 0:
                        scale_x = w / self.original_video_width if self.original_video_width != w else 1.0
                        scale_y = h / self.original_video_height if self.original_video_height != h else 1.0
                        if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                            px_float = px_float * scale_x
                            py_float = py_float * scale_y
                    elif hasattr(self, 'width') and hasattr(self, 'height') and self.width > 0 and self.height > 0:
                        scale_x = w / self.width if self.width != w else 1.0
                        scale_y = h / self.height if self.height != h else 1.0
                        if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                            px_float = px_float * scale_x
                            py_float = py_float * scale_y
                    
                    px = int(max(0, min(px_float, w - 1)))
                    py = int(max(0, min(py_float, h - 1)))
                    
                    # Calculate distance to ball (in scaled coordinates)
                    distance = np.sqrt((ball_x - px)**2 + (ball_y - py)**2)
                    if distance < min_distance:
                        min_distance = distance
                        closest_player_id = player_id
                        closest_player_pos = (px, py)
            
            # Draw possession indicator if player is close enough (within 50 pixels in scaled coordinates)
            # Adjust threshold based on frame size (50px at 4K = ~12px at 1080p)
            possession_threshold = max(30, int(50 * min(w, h) / 3840))  # Scale threshold with resolution
            if closest_player_id is not None and closest_player_pos is not None and min_distance < possession_threshold:
                px, py = closest_player_pos
                player_id_int = int(closest_player_id) if not isinstance(closest_player_id, int) else closest_player_id
                
                # Get player color for triangle
                player_name = None
                if len(players[closest_player_id]) >= 3:
                    team = players[closest_player_id][2]
                    if len(players[closest_player_id]) >= 4:
                        player_name = players[closest_player_id][3]  # Name is 4th element
                    elif hasattr(self, 'player_names') and self.player_names:
                        player_name = self.player_names.get(str(player_id_int))
                    triangle_color = self.get_player_color(player_id_int, team, player_name)
                else:
                    triangle_color = (255, 0, 0)  # Blue default
                
                # Draw upward triangle above player (ball possession indicator)
                triangle_size = max(8, int(10 * min(w, h) / 3840))  # Scale triangle size with resolution
                triangle_top = (px, py - triangle_size - 5)
                triangle_left = (px - triangle_size, py - 5)
                triangle_right = (px + triangle_size, py - 5)
                triangle_points = np.array([triangle_top, triangle_left, triangle_right], np.int32)
                
                # Draw filled triangle
                cv2.fillPoly(display_frame, pts=[triangle_points], color=triangle_color)
                # Draw white outline for visibility
                cv2.polylines(display_frame, pts=[triangle_points], isClosed=True, color=(255, 255, 255), thickness=2)
        
        # Draw raw YOLO detection boxes (before tracking) if enabled
        if self.show_yolo_boxes.get():
            # Try to get raw YOLO detections from overlay metadata
            raw_yolo_detections = None
            if (self.overlay_metadata is not None and 
                frame_num in self.overlay_metadata.overlays):
                overlay_data = self.overlay_metadata.overlays[frame_num]
                if isinstance(overlay_data, dict):
                    raw_yolo_detections = overlay_data.get('raw_yolo_detections')
            
            # Also try to get from CSV data if not in metadata (for CSV rendering mode)
            # Note: CSV doesn't store raw YOLO detections, so this is only for metadata mode
            
            # Draw raw YOLO boxes in orange (BGR format: (0, 165, 255))
            if raw_yolo_detections is not None and raw_yolo_detections.get('xyxy') is not None:
                yolo_box_color = (0, 165, 255)  # Orange
                yolo_box_thickness = 1  # Thinner than tracked boxes
                xyxy_list = raw_yolo_detections['xyxy']
                if isinstance(xyxy_list, list) and len(xyxy_list) > 0:
                    boxes_drawn = 0
                    for xyxy in xyxy_list:
                        if isinstance(xyxy, list) and len(xyxy) == 4:
                            try:
                                x1, y1, x2, y2 = map(int, xyxy)
                                # Validate coordinates
                                if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0:
                                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), yolo_box_color, yolo_box_thickness)
                                    boxes_drawn += 1
                            except (ValueError, TypeError) as e:
                                # Skip invalid coordinates
                                continue
                    # Debug: Only print once per 100 frames to avoid spam
                    if frame_num % 100 == 0 and boxes_drawn > 0:
                        print(f"✓ Drawn {boxes_drawn} YOLO boxes on frame {frame_num}")
                # Suppress warning - it's normal for some frames to not have YOLO data
                # Only log if we're in metadata mode and the frame should have data
                elif (frame_num % 1000 == 0 and 
                      self.overlay_metadata is not None and 
                      frame_num in self.overlay_metadata.overlays):
                    # Only warn if frame is in metadata but missing YOLO data (unexpected)
                    print(f"⚠ YOLO boxes enabled but xyxy data is empty or invalid on frame {frame_num}")
            # Suppress warnings - it's normal for frames to not have YOLO data
            # Only log once at startup if metadata is loaded but YOLO data is missing
            elif frame_num == 0 and self.overlay_metadata is not None:
                # Only warn once at frame 0 if metadata exists but YOLO data is missing
                if frame_num not in self.overlay_metadata.overlays:
                    # This is expected - not all frames have metadata
                    pass
                elif raw_yolo_detections is None:
                    # Warn once that YOLO data isn't available in metadata
                    print(f"ℹ YOLO boxes enabled but raw_yolo_detections not available in overlay metadata")
                    print(f"   → YOLO boxes will only show for frames with raw detection data")
        
        # Draw players
        # OPTIMIZATION: Interpolate missing frames to reduce blinking
        # If current frame has no data, try nearby frames for smoother playback
        frame_data = self.player_data.get(frame_num, {})
        if not frame_data and self.show_players.get():
            # Try previous frame (within 5 frames) for interpolation
            for offset in range(1, 6):
                prev_frame = frame_num - offset
                if prev_frame >= 0 and prev_frame in self.player_data:
                    frame_data = self.player_data[prev_frame].copy()
                    break
        
        # DEBUG: Only log when debug is enabled (can be toggled with 'd' key)
        debug_enabled = getattr(self.root, '_debug_enabled', False) if self.root else False
        if debug_enabled and (frame_num < 3 or (frame_num % 60 == 0)):
            print(f"[DEBUG] Frame {frame_num}: show_players={self.show_players.get()}, show_circles={self.show_player_circles.get()}, frame_data={len(frame_data) if frame_data else 0} players")
            if not frame_data:
                print(f"  ⚠ No player data for frame {frame_num}")
                # Check if any nearby frames have data (only for very first frames)
                if frame_num < 3:
                    nearby_frames = [frame_num + i for i in range(-5, 6) if frame_num + i >= 0]
                    nearby_data = [f for f in nearby_frames if f in self.player_data]
                    if nearby_data:
                        print(f"  → Nearest frames with data: {nearby_data[:5]}")
        
        if self.show_players.get() and frame_data:
            players = frame_data
            
            # CRITICAL DEBUG: Log when entering player loop
            if frame_num < 3:
                print(f"[DEBUG] Frame {frame_num}: Entering player loop with {len(players)} players")
            
            for player_id, player_info in players.items():
                # CRITICAL DEBUG: Log each player
                if frame_num < 3:
                    print(f"[DEBUG] Frame {frame_num}: Processing player {player_id}, info={player_info}")
                # Handle both old format (x, y, team, name) and new format (x, y, team, name, bbox)
                if len(player_info) == 5:
                    x, y, team, name, bbox = player_info
                else:
                    x, y, team, name = player_info
                    bbox = None
                
                # CRITICAL FIX: Validate and scale coordinates to match display frame resolution
                # Coordinates from CSV are in original video resolution, but display_frame may be different
                h, w = display_frame.shape[:2]
                
                # Check if coordinates are normalized (0-1) or pixel coordinates
                x_float = float(x)
                y_float = float(y)
                
                # Detect coordinate system:
                # 1. If coordinates are between 0-1, they're normalized (scale up)
                # 2. If coordinates are > display frame size, they're in original video resolution (scale down)
                # 3. If coordinates match display frame size, they're already correct
                
                # Check if coordinates are normalized (0-1 range)
                if 0.0 <= x_float <= 1.0 and 0.0 <= y_float <= 1.0:
                    # Normalized coordinates - scale up to pixel coordinates
                    x_float = x_float * w
                    y_float = y_float * h
                # Check if coordinates are in original video resolution (need scaling)
                # CRITICAL: Use original video dimensions, not transformed dimensions (perspective view changes self.width/height)
                elif hasattr(self, 'original_video_width') and hasattr(self, 'original_video_height') and self.original_video_width > 0 and self.original_video_height > 0:
                    # Scale coordinates from original video resolution to display frame resolution
                    scale_x = w / self.original_video_width if self.original_video_width != w else 1.0
                    scale_y = h / self.original_video_height if self.original_video_height != h else 1.0
                    
                    # Only scale if there's a significant difference (more than 10%)
                    if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                        x_float = x_float * scale_x
                        y_float = y_float * scale_y
                # Fallback: Use current width/height if original dimensions not available
                elif hasattr(self, 'width') and hasattr(self, 'height') and self.width > 0 and self.height > 0:
                    # Scale coordinates from current frame resolution to display frame resolution
                    scale_x = w / self.width if self.width != w else 1.0
                    scale_y = h / self.height if self.height != h else 1.0
                    
                    # Only scale if there's a significant difference (more than 10%)
                    if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                        x_float = x_float * scale_x
                        y_float = y_float * scale_y
                
                # Clamp coordinates to display frame bounds (prevent drawing off-screen)
                x = int(max(0, min(x_float, w - 1)))
                y = int(max(0, min(y_float, h - 1)))
                
                # Ensure player_id is an integer for comparison
                player_id_int = int(player_id)
                
                # Get player name for per-player visualization settings
                player_name = None
                if len(player_info) >= 4:
                    player_name = player_info[3]  # Name is 4th element
                elif hasattr(self, 'player_names') and self.player_names:
                    player_name = self.player_names.get(str(player_id_int))
                
                # Get color (check per-player settings first, then team color)
                color = self.get_player_color(player_id_int, team, player_name)
                
                # CRITICAL DEBUG: Log after getting color
                if frame_num < 3:
                    print(f"[DEBUG] Frame {frame_num}, Player {player_id_int}: Got color={color}, show_player_boxes={self.show_player_boxes.get()}")
                
                # CRITICAL FIX: Draw feet markers FIRST, before bounding boxes
                # This ensures feet markers are drawn even if bounding box validation causes a continue
                # NEW SYSTEM: Draw feet markers using Visualization Settings (takes precedence)
                # The "Circles" checkbox controls whether feet markers are shown at all
                if self.show_player_circles.get():
                    # Debug logging only for first frame (reduced spam)
                    if frame_num == 0:
                        print(f"[DEBUG] Frame {frame_num}, Player {player_id_int}: Drawing feet marker. x={x}, y={y}, show_circles={self.show_player_circles.get()}")
                    
                    # Check for per-player visualization settings first, then fall back to defaults
                    feet_marker_style = self.feet_marker_style.get()  # Default from playback viewer
                    feet_marker_opacity = self._safe_get_int(self.feet_marker_opacity, 255)
                    feet_marker_enable_glow = self.feet_marker_enable_glow.get()
                    feet_marker_glow_intensity = self._safe_get_int(self.feet_marker_glow_intensity, 50)
                    feet_marker_enable_shadow = self.feet_marker_enable_shadow.get()
                    feet_marker_shadow_offset = self._safe_get_int(self.feet_marker_shadow_offset, 3)
                    feet_marker_shadow_opacity = self._safe_get_int(self.feet_marker_shadow_opacity, 128)
                    feet_marker_enable_pulse = self.feet_marker_enable_pulse.get()
                    feet_marker_pulse_speed = self._safe_get_double(self.feet_marker_pulse_speed, 2.0)
                    feet_marker_enable_particles = self.feet_marker_enable_particles.get()
                    feet_marker_particle_count = self._safe_get_int(self.feet_marker_particle_count, 5)
                    feet_marker_vertical_offset = self._safe_get_int(self.feet_marker_vertical_offset, 50)
                    
                    # Check for per-player visualization settings (if player_name is available)
                    if player_name:
                        try:
                            # Use main gallery cache instead of separate cache
                            if not hasattr(self, '_player_gallery') or self._player_gallery is None:
                                from player_gallery import PlayerGallery
                                self._player_gallery = PlayerGallery()
                            player = self._player_gallery.get_player(player_name) if self._player_gallery else None
                            if player and player.visualization_settings:
                                viz = player.visualization_settings
                                # Override with player-specific settings if they exist, otherwise keep defaults
                                feet_marker_style = viz.get("feet_marker_style", feet_marker_style)
                                feet_marker_opacity = viz.get("feet_marker_opacity", feet_marker_opacity)
                                feet_marker_enable_glow = viz.get("feet_marker_enable_glow", feet_marker_enable_glow)
                                feet_marker_glow_intensity = viz.get("feet_marker_glow_intensity", feet_marker_glow_intensity)
                                feet_marker_enable_shadow = viz.get("feet_marker_enable_shadow", feet_marker_enable_shadow)
                                feet_marker_shadow_offset = viz.get("feet_marker_shadow_offset", feet_marker_shadow_offset)
                                feet_marker_shadow_opacity = viz.get("feet_marker_shadow_opacity", feet_marker_shadow_opacity)
                                feet_marker_enable_pulse = viz.get("feet_marker_enable_pulse", feet_marker_enable_pulse)
                                feet_marker_pulse_speed = viz.get("feet_marker_pulse_speed", feet_marker_pulse_speed)
                                feet_marker_enable_particles = viz.get("feet_marker_enable_particles", feet_marker_enable_particles)
                                feet_marker_particle_count = viz.get("feet_marker_particle_count", feet_marker_particle_count)
                                feet_marker_vertical_offset = viz.get("feet_marker_vertical_offset", feet_marker_vertical_offset)
                        except Exception:
                            pass  # Fall through to defaults
                    
                    # CRITICAL: Skip drawing if style is "none"
                    if feet_marker_style == "none":
                        if frame_num < 3 or (frame_num % 30 == 0):
                            print(f"[DEBUG] Frame {frame_num}, Player {player_id_int}: Skipping feet marker - style is 'none'")
                        pass  # Don't draw anything
                    else:
                        try:
                            # CRITICAL FIX: Use y directly as foot position (y is already the foot position from CSV)
                            foot_y = y + feet_marker_vertical_offset
                            
                            # Get ellipse size (try metadata first, then use defaults)
                            if (self.overlay_metadata is not None and 
                                hasattr(self.overlay_metadata, 'visualization_settings')):
                                viz_settings = self.overlay_metadata.visualization_settings
                                ellipse_width = viz_settings.get("ellipse_width", 20)
                                ellipse_height = viz_settings.get("ellipse_height", 12)
                                ellipse_outline_thickness = viz_settings.get("ellipse_outline_thickness", 3)
                            else:
                                # Try to get from playback viewer's own settings
                                if hasattr(self, 'ellipse_width'):
                                    ellipse_width = self._safe_get_int(self.ellipse_width, 20)
                                else:
                                    ellipse_width = 20
                                if hasattr(self, 'ellipse_height'):
                                    ellipse_height = self._safe_get_int(self.ellipse_height, 12)
                                else:
                                    ellipse_height = 12
                                ellipse_outline_thickness = self._safe_get_int(self.ellipse_outline_thickness, 3) if hasattr(self, 'ellipse_outline_thickness') else 3
                            
                            # Scale ellipse size based on frame width
                            scale_factor = max(1.0, display_frame.shape[1] / 1920.0)
                            scaled_width = int(ellipse_width * scale_factor)
                            scaled_height = int(ellipse_height * scale_factor)
                            axes = (int(scaled_width / 2), int(scaled_height / 2))
                            # Always use team color for circles (ignore any custom box color)
                            ellipse_color = color
                            
                            # Debug logging only for first frame (reduced spam)
                            if frame_num == 0:
                                print(f"[DEBUG] Frame {frame_num}, Player {player_id_int}: Drawing feet marker")
                                print(f"  x={x}, y={y}, foot_y={foot_y} (offset={feet_marker_vertical_offset})")
                                print(f"  Style={feet_marker_style}, axes={axes}, color={ellipse_color}")
                                print(f"  show_circles={self.show_player_circles.get()}, show_players={self.show_players.get()}")
                            
                            # ALWAYS use enhanced rendering with new system settings
                            self._draw_enhanced_feet_marker_simple(
                                display_frame, (x, foot_y), axes, feet_marker_style,
                                ellipse_color, feet_marker_opacity, feet_marker_enable_glow,
                                feet_marker_glow_intensity, feet_marker_enable_shadow,
                                feet_marker_shadow_offset, feet_marker_shadow_opacity,
                                feet_marker_enable_pulse, feet_marker_pulse_speed,
                                self.current_frame_num, feet_marker_enable_particles,
                                feet_marker_particle_count, ellipse_outline_thickness
                            )
                        except Exception as e:
                            # Log error but don't crash
                            if frame_num % 30 == 0:
                                print(f"[ERROR] Failed to draw feet marker for player {player_id_int} at frame {frame_num}: {e}")
                                import traceback
                                traceback.print_exc()
                
                # SEPARATE CONTROLS: Draw bounding boxes and circles independently (user requested)
                # Draw bounding box if enabled
                if self.show_player_boxes.get():
                    # CRITICAL DEBUG: Log when entering bounding box section
                    if frame_num < 3:
                        print(f"[DEBUG] Frame {frame_num}, Player {player_id_int}: Entering bounding box section")
                    # CRITICAL FIX: Use actual bbox coordinates from CSV if available, otherwise use fixed-size box
                    if bbox is not None:
                        # Use actual bbox coordinates from CSV
                        # Scale bbox coordinates to match display frame resolution
                        bbox_x1, bbox_y1, bbox_x2, bbox_y2 = bbox
                        
                        # Scale bbox coordinates if video resolution differs from display frame
                        # CRITICAL: Use original video dimensions, not transformed dimensions (perspective view changes self.width/height)
                        if hasattr(self, 'original_video_width') and hasattr(self, 'original_video_height') and self.original_video_width > 0 and self.original_video_height > 0:
                            scale_x = w / self.original_video_width if self.original_video_width != w else 1.0
                            scale_y = h / self.original_video_height if self.original_video_height != h else 1.0
                            
                            # Only scale if there's a significant difference (more than 10%)
                            if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                                bbox_x1 = bbox_x1 * scale_x
                                bbox_y1 = bbox_y1 * scale_y
                                bbox_x2 = bbox_x2 * scale_x
                                bbox_y2 = bbox_y2 * scale_y
                        # Fallback: Use current width/height if original dimensions not available
                        elif hasattr(self, 'width') and hasattr(self, 'height') and self.width > 0 and self.height > 0:
                            scale_x = w / self.width if self.width != w else 1.0
                            scale_y = h / self.height if self.height != h else 1.0
                            
                            # Only scale if there's a significant difference (more than 10%)
                            if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                                bbox_x1 = bbox_x1 * scale_x
                                bbox_y1 = bbox_y1 * scale_y
                                bbox_x2 = bbox_x2 * scale_x
                                bbox_y2 = bbox_y2 * scale_y
                        
                        x1, y1, x2, y2 = int(bbox_x1), int(bbox_y1), int(bbox_x2), int(bbox_y2)
                        
                        # CRITICAL: Validate bbox coordinates BEFORE clamping - check for swapped coordinates or invalid values
                        # Check original coordinates first to catch issues before clamping masks them
                        if bbox_x1 >= bbox_x2 or bbox_y1 >= bbox_y2:
                            # Coordinates are swapped or invalid - skip this box
                            if frame_num < 5 or (frame_num % 100 == 0):
                                print(f"[DEBUG] Invalid bbox coordinates for player {player_id_int} at frame {frame_num}: x1={bbox_x1}, y1={bbox_y1}, x2={bbox_x2}, y2={bbox_y2}")
                            continue
                        
                        # CRITICAL: Check if bbox is too large BEFORE scaling/clamping (catch coordinate system errors early)
                        # Maximum reasonable box size: 20% of original video frame
                        original_w = self.original_video_width if hasattr(self, 'original_video_width') and self.original_video_width > 0 else w
                        original_h = self.original_video_height if hasattr(self, 'original_video_height') and self.original_video_height > 0 else h
                        original_box_width = abs(bbox_x2 - bbox_x1)
                        original_box_height = abs(bbox_y2 - bbox_y1)
                        max_original_box_width = original_w * 0.2
                        max_original_box_height = original_h * 0.2
                        
                        if original_box_width > max_original_box_width or original_box_height > max_original_box_height:
                            # Box is suspiciously large even before scaling - skip it and log
                            if frame_num < 5 or (frame_num % 100 == 0):
                                print(f"[DEBUG] Skipping oversized bbox for player {player_id_int} at frame {frame_num}: original width={original_box_width} ({original_box_width/original_w*100:.1f}% of {original_w}x{original_h}), height={original_box_height} ({original_box_height/original_h*100:.1f}%)")
                                print(f"[DEBUG]   Original bbox from CSV: {bbox}")
                            continue
                        
                        # Now clamp to frame bounds to prevent drawing off-screen
                        x1 = max(0, min(x1, w - 1))
                        y1 = max(0, min(y1, h - 1))
                        x2 = max(x1 + 1, min(x2, w))
                        y2 = max(y1 + 1, min(y2, h))
                        # Recalculate after clamping
                        box_width = x2 - x1
                        box_height = y2 - y1
                        
                        # CRITICAL: Final validation after clamping - ensure box is still reasonable
                        max_box_width = w * 0.2
                        max_box_height = h * 0.2
                        if box_width > max_box_width or box_height > max_box_height:
                            # Box is still too large after clamping - skip it
                            if frame_num < 5 or (frame_num % 100 == 0):
                                print(f"[DEBUG] Skipping oversized bbox after clamping for player {player_id_int} at frame {frame_num}: width={box_width} ({box_width/w*100:.1f}% of frame), height={box_height} ({box_height/h*100:.1f}%)")
                            continue
                        
                        # CRITICAL: Check if bbox is too small (likely foot-based bbox, not full player bbox)
                        # Typical full player bbox should be at least 60px wide and 120px tall
                        # If bbox is too small, expand it to reasonable size
                        min_box_width = 60
                        min_box_height = 120
                        if box_width > 0 and box_height > 0:
                            # Scale minimum sizes based on video resolution
                            if hasattr(self, 'original_video_width') and self.original_video_width > 0:
                                scale_factor = w / self.original_video_width
                                min_box_width = int(min_box_width * scale_factor)
                                min_box_height = int(min_box_height * scale_factor)
                            
                            # If bbox is too small, expand it around the center
                            if box_width < min_box_width or box_height < min_box_height:
                                center_x = (x1 + x2) / 2
                                center_y = (y1 + y2) / 2
                                # Expand to minimum size, but keep center point
                                x1 = int(center_x - min_box_width / 2)
                                y1 = int(center_y - min_box_height / 2)
                                x2 = int(center_x + min_box_width / 2)
                                y2 = int(center_y + min_box_height / 2)
                                # Recalculate after expansion
                                box_width = x2 - x1
                                box_height = y2 - y1
                        
                        if box_width > 0 and box_height > 0:
                            tl = (x1, y1)
                            br = (x2, y2)
                            self.csv_hd_renderer.draw_crisp_rectangle(display_frame, tl, br, color, thickness=2)
                    else:
                        # Fallback: Use reasonable-sized box around foot position (player is taller than wide)
                        # Scale box size based on video resolution (typical player: ~80px wide, ~160px tall)
                        h, w = display_frame.shape[:2]
                        # Use original video dimensions for scaling if available
                        if hasattr(self, 'original_video_width') and self.original_video_width > 0:
                            scale_factor = w / self.original_video_width
                        else:
                            scale_factor = 1.0
                        
                        # Typical player bbox: 80px wide, 160px tall (scaled to video resolution)
                        box_width = int(80 * scale_factor)
                        box_height = int(160 * scale_factor)
                        
                        # CRITICAL: Validate fallback box size before drawing
                        max_box_width = w * 0.2
                        max_box_height = h * 0.2
                        if box_width > max_box_width or box_height > max_box_height:
                            # Fallback box is too large - skip it
                            if frame_num % 100 == 0:  # Only log every 100 frames
                                print(f"[DEBUG] Skipping oversized fallback bbox for player {player_id_int} at frame {frame_num}: width={box_width} ({box_width/w*100:.1f}% of frame), height={box_height} ({box_height/h*100:.1f}% of frame)")
                            continue
                        
                        # Center box horizontally on x, but anchor vertically at foot position (y)
                        # y is the foot position, so box should extend upward from there
                        tl = (x - box_width // 2, y - box_height)  # Top-left: centered horizontally, full height above foot
                        br = (x + box_width // 2, y)  # Bottom-right: centered horizontally, at foot position
                        
                        # Clamp to frame bounds
                        tl = (max(0, min(tl[0], w - 1)), max(0, min(tl[1], h - 1)))
                        br = (max(tl[0] + 1, min(br[0], w)), max(tl[1] + 1, min(br[1], h)))
                        
                        # Final validation: ensure box is reasonable size after clamping
                        final_width = br[0] - tl[0]
                        final_height = br[1] - tl[1]
                        if final_width > max_box_width or final_height > max_box_height:
                            continue  # Skip if still too large after clamping
                        
                        self.csv_hd_renderer.draw_crisp_rectangle(display_frame, tl, br, color, thickness=2)
                
                # NOTE: Feet markers are now drawn BEFORE bounding boxes (see line ~3905)
                # This ensures they are drawn even if bounding box validation causes a continue
                    # Check for per-player visualization settings first, then fall back to defaults
                    feet_marker_style = self.feet_marker_style.get()  # Default from playback viewer
                    
                    # CRITICAL DEBUG: Log after getting style
                    if frame_num < 3:
                        print(f"[DEBUG] Frame {frame_num}, Player {player_id_int}: Got feet_marker_style='{feet_marker_style}'")
                    feet_marker_opacity = self._safe_get_int(self.feet_marker_opacity, 255)
                    feet_marker_enable_glow = self.feet_marker_enable_glow.get()
                    feet_marker_glow_intensity = self._safe_get_int(self.feet_marker_glow_intensity, 50)
                    feet_marker_enable_shadow = self.feet_marker_enable_shadow.get()
                    feet_marker_shadow_offset = self._safe_get_int(self.feet_marker_shadow_offset, 3)
                    feet_marker_shadow_opacity = self._safe_get_int(self.feet_marker_shadow_opacity, 128)
                    feet_marker_enable_pulse = self.feet_marker_enable_pulse.get()
                    feet_marker_pulse_speed = self._safe_get_double(self.feet_marker_pulse_speed, 2.0)
                    feet_marker_enable_particles = self.feet_marker_enable_particles.get()
                    feet_marker_particle_count = self._safe_get_int(self.feet_marker_particle_count, 5)
                    feet_marker_vertical_offset = self._safe_get_int(self.feet_marker_vertical_offset, 50)
                    
                    # Check for per-player visualization settings (if player_name is available)
                    if player_name:
                        try:
                            # Use main gallery cache instead of separate cache
                            if not hasattr(self, '_player_gallery') or self._player_gallery is None:
                                from player_gallery import PlayerGallery
                                self._player_gallery = PlayerGallery()
                            player = self._player_gallery.get_player(player_name) if self._player_gallery else None
                            if player and player.visualization_settings:
                                viz = player.visualization_settings
                                # Override with player-specific settings if they exist, otherwise keep defaults
                                feet_marker_style = viz.get("feet_marker_style", feet_marker_style)
                                feet_marker_opacity = viz.get("feet_marker_opacity", feet_marker_opacity)
                                feet_marker_enable_glow = viz.get("feet_marker_enable_glow", feet_marker_enable_glow)
                                feet_marker_glow_intensity = viz.get("feet_marker_glow_intensity", feet_marker_glow_intensity)
                                feet_marker_enable_shadow = viz.get("feet_marker_enable_shadow", feet_marker_enable_shadow)
                                feet_marker_shadow_offset = viz.get("feet_marker_shadow_offset", feet_marker_shadow_offset)
                                feet_marker_shadow_opacity = viz.get("feet_marker_shadow_opacity", feet_marker_shadow_opacity)
                                feet_marker_enable_pulse = viz.get("feet_marker_enable_pulse", feet_marker_enable_pulse)
                                feet_marker_pulse_speed = viz.get("feet_marker_pulse_speed", feet_marker_pulse_speed)
                                feet_marker_enable_particles = viz.get("feet_marker_enable_particles", feet_marker_enable_particles)
                                feet_marker_particle_count = viz.get("feet_marker_particle_count", feet_marker_particle_count)
                                feet_marker_vertical_offset = viz.get("feet_marker_vertical_offset", feet_marker_vertical_offset)
                        except Exception:
                            pass  # Fall through to defaults
                    
                    # CRITICAL DEBUG: Always log for first few frames
                    if frame_num < 3:
                        print(f"[DEBUG] Frame {frame_num}, Player {player_id_int}: feet_marker_style='{feet_marker_style}', show_circles={self.show_player_circles.get()}")
                    
                    # CRITICAL: Skip drawing if style is "none"
                    if feet_marker_style == "none":
                        if frame_num < 3 or (frame_num % 30 == 0):
                            print(f"[DEBUG] Frame {frame_num}, Player {player_id_int}: Skipping feet marker - style is 'none'")
                        pass  # Don't draw anything
                    else:
                        try:
                            # CRITICAL FIX: Use y directly as foot position (y is already the foot position from CSV)
                            # The vertical offset should be minimal or zero by default for proper tracking
                            # Default offset of 50 pushes marker too far down - use 0 or small negative value
                            foot_y = y + feet_marker_vertical_offset

                            # Get ellipse size (try metadata first, then use defaults)
                            if (self.overlay_metadata is not None and
                                hasattr(self.overlay_metadata, 'visualization_settings')):
                                viz_settings = self.overlay_metadata.visualization_settings
                                ellipse_width = viz_settings.get("ellipse_width", 20)
                                ellipse_height = viz_settings.get("ellipse_height", 12)
                                ellipse_outline_thickness = viz_settings.get("ellipse_outline_thickness", 3)
                            else:
                                # Try to get from playback viewer's own settings
                                if hasattr(self, 'ellipse_width'):
                                    ellipse_width = self._safe_get_int(self.ellipse_width, 20)
                                else:
                                    ellipse_width = 20
                                if hasattr(self, 'ellipse_height'):
                                    ellipse_height = self._safe_get_int(self.ellipse_height, 12)
                                else:
                                    ellipse_height = 12
                                ellipse_outline_thickness = self._safe_get_int(self.ellipse_outline_thickness, 3) if hasattr(self, 'ellipse_outline_thickness') else 3

                            # Scale ellipse size based on frame width
                            scale_factor = max(1.0, display_frame.shape[1] / 1920.0)
                            scaled_width = int(ellipse_width * scale_factor)
                            scaled_height = int(ellipse_height * scale_factor)
                            axes = (int(scaled_width / 2), int(scaled_height / 2))
                            # Always use team color for circles (ignore any custom box color)
                            ellipse_color = color

                            # Debug logging only for first frame (reduced spam)
                            if frame_num == 0:
                                print(f"[DEBUG] Frame {frame_num}, Player {player_id_int}: Drawing feet marker")
                                print(f"  x={x}, y={y}, foot_y={foot_y} (offset={feet_marker_vertical_offset})")
                                print(f"  Style={feet_marker_style}, axes={axes}, color={ellipse_color}")
                                print(f"  show_circles={self.show_player_circles.get()}, show_players={self.show_players.get()}")

                            # ALWAYS use enhanced rendering with new system settings
                            # This ensures all visualization settings take effect
                            self._draw_enhanced_feet_marker_simple(
                                display_frame, (x, foot_y), axes, feet_marker_style,
                                ellipse_color, feet_marker_opacity, feet_marker_enable_glow,
                                feet_marker_glow_intensity, feet_marker_enable_shadow,
                                feet_marker_shadow_offset, feet_marker_shadow_opacity,
                                feet_marker_enable_pulse, feet_marker_pulse_speed,
                                self.current_frame_num, feet_marker_enable_particles,
                                feet_marker_particle_count, ellipse_outline_thickness
                            )
                        except Exception as e:
                            # Log error but don't crash
                            if frame_num % 30 == 0:
                                print(f"[ERROR] Failed to draw feet marker for player {player_id_int} at frame {frame_num}: {e}")
                                import traceback
                                traceback.print_exc()
                
                # Highlight if matches specific highlight_id
                should_highlight = False
                if highlight_id is not None:
                    should_highlight = (player_id_int == highlight_id)
                elif self.highlight_ids:
                    should_highlight = (player_id_int in self.highlight_ids)
                
                if should_highlight:
                    # Draw much more prominent highlight for highlighted IDs
                    if self.show_player_boxes.get():
                        box_size = 40
                        outer_tl = (x - box_size - 8, y - box_size - 8)
                        outer_br = (x + box_size + 8, y + box_size + 8)
                        inner_tl = (x - box_size - 4, y - box_size - 4)
                        inner_br = (x + box_size + 4, y + box_size + 4)
                        self.csv_hd_renderer.draw_crisp_rectangle(display_frame, outer_tl, outer_br, (0, 255, 255), thickness=6)
                        self.csv_hd_renderer.draw_crisp_rectangle(display_frame, inner_tl, inner_br, (0, 255, 255), thickness=3)
                    if self.show_player_circles.get():
                        foot_y = y
                        # Draw multiple ellipses for visibility
                        ellipse_width = 20
                        ellipse_height = 12
                        scale_factor = max(1.0, display_frame.shape[1] / 1920.0)
                        scaled_width = int(ellipse_width * scale_factor)
                        scaled_height = int(ellipse_height * scale_factor)
                        axes_large = (int(scaled_width / 2) + 8, int(scaled_height / 2) + 8)
                        axes_normal = (int(scaled_width / 2), int(scaled_height / 2))
                        cv2.ellipse(display_frame, (x, foot_y), axes_large, 0, 0, 360, (0, 255, 255), 6)  # Yellow highlight - outer
                        cv2.ellipse(display_frame, (x, foot_y), axes_normal, 0, 0, 360, (0, 255, 255), 3)  # Yellow highlight - inner
                
                # Draw label
                label_y_offset = 0
                if self.show_player_labels.get():
                    # CRITICAL FIX: Ensure label is always a string
                    if name:
                        label = str(name) if not isinstance(name, str) else name
                    else:
                        label = f"#{player_id_int}"
                    
                    # Make label much more prominent for highlighted IDs
                    is_highlighted = should_highlight
                    if is_highlighted:
                        font_scale = 1.0
                        thickness = 3
                        label_color = (0, 0, 0)  # Black text on yellow background
                    else:
                        font_scale = 0.6
                        thickness = 2
                        label_color = color
                    
                    # Calculate text size for both highlighted and non-highlighted cases
                    (text_width, text_height), baseline = cv2.getTextSize(
                        str(label), cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
                    )
                    
                    if is_highlighted:
                        # Draw background rectangle for highlighted labels
                        cv2.rectangle(display_frame,
                                     (x + 40, y - text_height - 5),
                                     (x + 40 + text_width + 10, y + 5),
                                     (0, 255, 255), -1)  # Yellow filled background
                    
                    self.csv_hd_renderer.draw_crisp_text(
                        display_frame,
                        str(label),  # CRITICAL FIX: Ensure label is string
                        (x + 45, y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        font_scale,
                        label_color,
                        thickness,
                        outline_color=(0, 0, 0),
                        outline_thickness=2
                    )
                    label_y_offset = text_height + 5
                
                # Update player trail (breadcrumb trail) - add current position
                if self.show_player_trail.get():
                    if player_id_int not in self.player_trails:
                        # Initialize trail with max length
                        max_trail_length = self.player_trail_length.get()
                        self.player_trails[player_id_int] = deque(maxlen=max_trail_length)
                    # Add current position to trail
                    self.player_trails[player_id_int].append((frame_num, x, y))
                
                # Draw analytics if enabled and position is "with_player"
                # (Other positions are handled separately after all players are drawn)
                analytics_pos = self.analytics_position.get() if hasattr(self, 'analytics_position') else "with_player"
                # CRITICAL FIX: Find nearest frame with analytics if current frame is missing
                analytics_frame_num = frame_num
                if self.show_analytics.get() and analytics_pos == "with_player" and hasattr(self, 'analytics_data'):
                    if frame_num not in self.analytics_data:
                        # Find nearest frame with analytics (within ±5 frames)
                        nearest_frame = None
                        min_distance = float('inf')
                        for existing_frame in self.analytics_data.keys():
                            distance = abs(existing_frame - frame_num)
                            if distance < min_distance and distance <= 5:
                                min_distance = distance
                                nearest_frame = existing_frame
                        if nearest_frame is not None:
                            analytics_frame_num = nearest_frame
                    
                    if (analytics_frame_num in self.analytics_data and 
                        player_id_int in self.analytics_data[analytics_frame_num]):
                        # Detect if using imperial units (check CSV column names)
                        use_imperial = 'player_speed_mph' in self.df.columns if self.df is not None else False
                        
                        analytics_lines = self.get_analytics_text(player_id_int, analytics_frame_num, use_imperial)
                    if analytics_lines:
                        # Draw analytics text below player label (or below box if no label)
                        # Position: right side of player box, below label
                        analytics_y = y + label_y_offset + 20  # More spacing
                        # Use customizable font settings
                        font_scale = self._safe_get_double(self.analytics_font_scale, 1.0) if hasattr(self, 'analytics_font_scale') else 1.0
                        # For "with_player" mode, use slightly smaller scale but still respect user settings
                        font_scale = font_scale * 0.7  # Scale down for "with_player" mode
                        thickness = self._safe_get_int(self.analytics_font_thickness, 2) if hasattr(self, 'analytics_font_thickness') else 2
                        line_height = int(13 * font_scale / 0.45)  # Scale line height with font
                        
                        # Get font face
                        font_face_str = self.analytics_font_face.get() if hasattr(self, 'analytics_font_face') else "FONT_HERSHEY_SIMPLEX"
                        font_face = getattr(cv2, font_face_str, cv2.FONT_HERSHEY_SIMPLEX)
                        
                        # Get analytics color (default to white for better contrast)
                        if hasattr(self, 'use_custom_analytics_color') and self.use_custom_analytics_color.get():
                            analytics_color = (
                                self._get_analytics_color_bgr()
                            )
                        else:
                            analytics_color = (255, 255, 255)  # Default white for maximum contrast
                        
                        # Draw background for analytics (semi-transparent)
                        if len(analytics_lines) > 0:
                            max_line_width = 0
                            for line in analytics_lines:
                                (w, h), _ = cv2.getTextSize(line, font_face, font_scale, thickness)
                                max_line_width = max(max_line_width, w)
                            
                            # Draw semi-transparent background
                            # Safety check: ensure coordinates are valid
                            rect_x1 = x + 40
                            rect_y1 = analytics_y - 2
                            rect_x2 = x + 40 + max_line_width + 8
                            rect_y2 = analytics_y + len(analytics_lines) * line_height + 2
                            
                            # Ensure coordinates are within frame bounds
                            h, w = display_frame.shape[:2]
                            rect_x1 = max(0, min(rect_x1, w - 1))
                            rect_y1 = max(0, min(rect_y1, h - 1))
                            rect_x2 = max(rect_x1 + 1, min(rect_x2, w))
                            rect_y2 = max(rect_y1 + 1, min(rect_y2, h))
                            
                            if rect_x2 > rect_x1 and rect_y2 > rect_y1:
                                overlay = display_frame.copy()
                                cv2.rectangle(overlay,
                                             (rect_x1, rect_y1),
                                             (rect_x2, rect_y2),
                                             (0, 0, 0), -1)  # Black background
                                cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
                        
                        # Draw analytics text with better thickness and contrast
                        for i, line in enumerate(analytics_lines[:5]):  # Limit to 5 lines to avoid clutter
                            text_y = analytics_y + i * line_height
                            self.csv_hd_renderer.draw_crisp_text(
                                display_frame,
                                line,
                                (x + 44, text_y),
                                font_face,
                                font_scale,
                                analytics_color,
                                thickness,
                                outline_color=(0, 0, 0),
                                outline_thickness=max(1, thickness // 2)  # Thicker outline for better contrast
                            )
        
        # Draw analytics in panel/banner/bar position if enabled and not "with_player"
        if self.show_analytics.get() and frame_num in self.analytics_data:
            analytics_pos = self.analytics_position.get() if hasattr(self, 'analytics_position') else "with_player"
            if frame_num == 0:
                print(f"[DEBUG] Analytics check: show_analytics={self.show_analytics.get()}, frame in data={frame_num in self.analytics_data}, position='{analytics_pos}'")
            if analytics_pos != "with_player":
                self._render_analytics_panel(display_frame, frame_num, analytics_pos)
            elif frame_num == 0:
                print(f"[DEBUG] Analytics position is 'with_player', skipping panel render")
        
        # Draw player trails (breadcrumb trails) if enabled
        if self.show_player_trail.get() and self.player_trails:
            trail_size = self._safe_get_int(self.player_trail_size, 3)
            trail_fade = self.player_trail_fade.get()
            trail_color = (
                self._safe_get_int(self.player_trail_color_b, 0),
                self._safe_get_int(self.player_trail_color_g, 255),
                self._safe_get_int(self.player_trail_color_r, 255)
            )
            
            for player_id_int, trail_positions in self.player_trails.items():
                if len(trail_positions) < 2:
                    continue  # Need at least 2 positions to draw a trail
                
                # Get player color (use team color if available)
                player_color = trail_color  # Default to trail color
                if frame_num in self.player_data and player_id_int in self.player_data[frame_num]:
                    player_info = self.player_data[frame_num][player_id_int]
                    if len(player_info) >= 3:
                        team = player_info[2]
                        player_color = self.get_player_color(player_id_int, team)
                
                # Draw trail (breadcrumb dots)
                positions_list = list(trail_positions)
                for i, (trail_frame, trail_x, trail_y) in enumerate(positions_list):
                    # Skip if this position is in the future (shouldn't happen, but safety check)
                    if trail_frame > frame_num:
                        continue
                    
                    # Calculate fade based on age (older = more faded)
                    if trail_fade:
                        # Fade based on position in trail (0 = newest, 1 = oldest)
                        fade_factor = 1.0 - (i / len(positions_list))
                        fade_factor = max(0.3, fade_factor)  # Don't fade completely (min 30% opacity)
                    else:
                        fade_factor = 1.0
                    
                    # Apply fade to color
                    faded_color = tuple(int(c * fade_factor) for c in player_color)
                    
                    # Draw breadcrumb dot
                    trail_x_int = int(trail_x)
                    trail_y_int = int(trail_y)
                    
                    # Ensure coordinates are within frame bounds
                    h, w = display_frame.shape[:2]
                    if 0 <= trail_x_int < w and 0 <= trail_y_int < h:
                        cv2.circle(display_frame, (trail_x_int, trail_y_int), trail_size, faded_color, -1)
                        # Optional: draw outline for visibility
                        if trail_size > 2:
                            cv2.circle(display_frame, (trail_x_int, trail_y_int), trail_size, (255, 255, 255), 1)
        
        # Draw predicted boxes (for lost tracks) if enabled
        if self.show_predicted_boxes.get() and self.player_data:
            # Debug: Log once per 100 frames to verify prediction rendering is active
            if frame_num % 100 == 0:
                print(f"  🎯 Prediction boxes enabled: checking {len(self.player_data)} frames of player data")
            # Build track history from CSV data (only up to current frame)
            # Track history: track_id -> list of (frame_num, x, y) positions
            track_history = {}
            # Only look at frames up to and including current frame to determine lost tracks
            for hist_frame_num, frame_players in self.player_data.items():
                if hist_frame_num > frame_num:
                    continue  # Skip future frames
                for player_id, player_info in frame_players.items():
                    if len(player_info) >= 2:
                        x, y = player_info[0], player_info[1]
                        player_id_int = int(player_id) if not isinstance(player_id, int) else player_id
                        if player_id_int not in track_history:
                            track_history[player_id_int] = []
                        track_history[player_id_int].append((hist_frame_num, x, y))
            
            # Check if current frame has any players (to detect lost tracks)
            current_frame_players = set()
            if frame_num in self.player_data:
                for pid in self.player_data[frame_num].keys():
                    pid_int = int(pid) if not isinstance(pid, int) else pid
                    current_frame_players.add(pid_int)
            
            # For each track, find where it was last seen and predict forward
            prediction_duration_frames = int(self.prediction_duration.get() * self.fps) if self.fps > 0 else 30
            prediction_size = self._safe_get_int(self.prediction_size, 5)
            prediction_style = self.prediction_style.get()
            prediction_color = (
                self._safe_get_int(self.prediction_color_b, 0),
                self._safe_get_int(self.prediction_color_g, 0),
                self._safe_get_int(self.prediction_color_r, 255)
            )
            prediction_alpha = self._safe_get_int(self.prediction_color_alpha, 128) / 255.0
            
            for track_id, positions in track_history.items():
                if len(positions) < 2:
                    continue  # Need at least 2 positions to predict
                
                # Sort by frame number
                positions.sort(key=lambda p: p[0])
                last_frame, last_x, last_y = positions[-1]
                
                # Check if track is lost (not in current frame but was seen recently)
                # Track is "lost" if:
                # 1. It's not in the current frame
                # 2. It was last seen before the current frame
                # 3. It's within the prediction duration window
                track_id_int = int(track_id) if not isinstance(track_id, int) else track_id
                is_lost = (track_id_int not in current_frame_players and 
                          last_frame < frame_num and 
                          frame_num <= last_frame + prediction_duration_frames)
                
                # Debug output (only first time per track)
                if is_lost and not hasattr(self, '_prediction_debug_logged'):
                    self._prediction_debug_logged = set()
                if is_lost and track_id_int not in getattr(self, '_prediction_debug_logged', set()):
                    self._prediction_debug_logged.add(track_id_int)
                    print(f"  🎯 Prediction: Track #{track_id_int} lost at frame {frame_num} (last seen: {last_frame}, predicting {frame_num - last_frame} frames ahead)")
                
                if is_lost:
                    # Calculate velocity from last 2 positions
                    if len(positions) >= 2:
                        prev_frame, prev_x, prev_y = positions[-2]
                        if prev_frame < last_frame:
                            # Calculate velocity (pixels per frame)
                            frames_diff = last_frame - prev_frame
                            if frames_diff > 0:
                                vx = (last_x - prev_x) / frames_diff
                                vy = (last_y - prev_y) / frames_diff
                                
                                # Predict position at current frame
                                frames_ahead = frame_num - last_frame
                                pred_x = last_x + vx * frames_ahead
                                pred_y = last_y + vy * frames_ahead
                                
                                # Apply fade (more recent = brighter)
                                fade_factor = 1.0 - (frames_ahead / prediction_duration_frames)
                                fade_factor = max(0.0, min(1.0, fade_factor))
                                alpha = prediction_alpha * fade_factor
                                
                                # Draw prediction marker
                                pred_x_int = int(pred_x)
                                pred_y_int = int(pred_y)
                                
                                # Ensure coordinates are within frame bounds
                                h, w = display_frame.shape[:2]
                                if 0 <= pred_x_int < w and 0 <= pred_y_int < h:
                                    # Apply alpha to color
                                    faded_color = tuple(int(c * alpha) for c in prediction_color)
                                    
                                    # Draw based on style
                                    if prediction_style == "dot":
                                        cv2.circle(display_frame, (pred_x_int, pred_y_int), prediction_size, faded_color, -1)
                                        cv2.circle(display_frame, (pred_x_int, pred_y_int), prediction_size, (255, 255, 255), 1)
                                    elif prediction_style == "box":
                                        half_size = prediction_size
                                        cv2.rectangle(display_frame,
                                                    (pred_x_int - half_size, pred_y_int - half_size),
                                                    (pred_x_int + half_size, pred_y_int + half_size),
                                                    faded_color, 2)
                                    elif prediction_style == "cross":
                                        half_size = prediction_size
                                        cv2.line(display_frame,
                                               (pred_x_int - half_size, pred_y_int),
                                               (pred_x_int + half_size, pred_y_int),
                                               faded_color, 2)
                                        cv2.line(display_frame,
                                               (pred_x_int, pred_y_int - half_size),
                                               (pred_x_int, pred_y_int + half_size),
                                               faded_color, 2)
                                    elif prediction_style == "x":
                                        half_size = int(prediction_size * 0.7)
                                        cv2.line(display_frame,
                                               (pred_x_int - half_size, pred_y_int - half_size),
                                               (pred_x_int + half_size, pred_y_int + half_size),
                                               faded_color, 2)
                                        cv2.line(display_frame,
                                               (pred_x_int - half_size, pred_y_int + half_size),
                                               (pred_x_int + half_size, pred_y_int - half_size),
                                               faded_color, 2)
                                    elif prediction_style == "arrow":
                                        # Draw arrow pointing in direction of movement
                                        arrow_size = prediction_size
                                        if frames_ahead > 0:
                                            # Calculate arrow direction from velocity
                                            angle = np.arctan2(vy, vx)
                                            arrow_tip = (
                                                int(pred_x_int + arrow_size * np.cos(angle)),
                                                int(pred_y_int + arrow_size * np.sin(angle))
                                            )
                                            arrow_left = (
                                                int(pred_x_int - arrow_size * 0.5 * np.cos(angle - np.pi/2)),
                                                int(pred_y_int - arrow_size * 0.5 * np.sin(angle - np.pi/2))
                                            )
                                            arrow_right = (
                                                int(pred_x_int - arrow_size * 0.5 * np.cos(angle + np.pi/2)),
                                                int(pred_y_int - arrow_size * 0.5 * np.sin(angle + np.pi/2))
                                            )
                                            points = np.array([arrow_tip, arrow_left, arrow_right], np.int32)
                                            cv2.fillPoly(display_frame, [points], faded_color)
                                        else:
                                            # No movement, draw simple triangle
                                            points = np.array([
                                                [pred_x_int, pred_y_int - arrow_size],
                                                [pred_x_int - arrow_size // 2, pred_y_int],
                                                [pred_x_int + arrow_size // 2, pred_y_int]
                                            ], np.int32)
                                            cv2.fillPoly(display_frame, [points], faded_color)
                                    elif prediction_style == "diamond":
                                        half_size = prediction_size
                                        points = np.array([
                                            [pred_x_int, pred_y_int - half_size],
                                            [pred_x_int + half_size, pred_y_int],
                                            [pred_x_int, pred_y_int + half_size],
                                            [pred_x_int - half_size, pred_y_int]
                                        ], np.int32)
                                        cv2.fillPoly(display_frame, [points], faded_color)
        
        return display_frame
    
    def _render_analytics_from_csv(self, display_frame, frame_num):
        """
        Render analytics from CSV on top of existing frame (for hybrid mode).
        This allows metadata to handle visuals while CSV handles analytics.
        """
        if not self.show_analytics.get() or not hasattr(self, 'analytics_data'):
            return display_frame
        
        # CRITICAL FIX: Check for analytics data in current frame, or try to find nearest frame with data
        # This ensures analytics update even if some frames are missing data
        if frame_num not in self.analytics_data:
            # Try to find nearest frame with analytics (within ±5 frames for smooth playback)
            nearest_frame = None
            min_distance = float('inf')
            for existing_frame in self.analytics_data.keys():
                distance = abs(existing_frame - frame_num)
                if distance < min_distance and distance <= 5:  # Only use nearby frames
                    min_distance = distance
                    nearest_frame = existing_frame
            if nearest_frame is not None:
                frame_num = nearest_frame  # Use nearest frame's analytics
            else:
                return display_frame  # No nearby analytics data
        
        # Render analytics in "with_player" position
        analytics_pos = self.analytics_position.get() if hasattr(self, 'analytics_position') else "with_player"
        if analytics_pos == "with_player":
            # Render analytics with each player (from CSV player data)
            if frame_num in self.player_data:
                for player_id, player_info in self.player_data[frame_num].items():
                    if len(player_info) >= 2:
                        player_id_int = int(player_id) if not isinstance(player_id, int) else player_id
                        if player_id_int in self.analytics_data[frame_num]:
                            x, y = player_info[0], player_info[1]
                            # Use same analytics rendering logic as _render_overlays_from_csv
                            use_imperial = 'player_speed_mph' in self.df.columns if self.df is not None else False
                            analytics_lines = self.get_analytics_text(player_id_int, analytics_frame_num, use_imperial)
                            if analytics_lines:
                                analytics_y = y + 40  # Position below player
                                font_scale = self._safe_get_double(self.analytics_font_scale, 1.0) if hasattr(self, 'analytics_font_scale') else 1.0
                                font_scale = font_scale * 0.7  # Scale down for "with_player" mode
                                thickness = self._safe_get_int(self.analytics_font_thickness, 2) if hasattr(self, 'analytics_font_thickness') else 2
                                line_height = int(13 * font_scale / 0.45)
                                
                                font_face_str = self.analytics_font_face.get() if hasattr(self, 'analytics_font_face') else "FONT_HERSHEY_SIMPLEX"
                                font_face = getattr(cv2, font_face_str, cv2.FONT_HERSHEY_SIMPLEX)
                                
                                if hasattr(self, 'use_custom_analytics_color') and self.use_custom_analytics_color.get():
                                    analytics_color = (
                                        self._safe_get_int(self.analytics_color_b, 255),
                                        self._safe_get_int(self.analytics_color_g, 255),
                                        self._safe_get_int(self.analytics_color_r, 255)
                                    )
                                else:
                                    analytics_color = (255, 255, 255)
                                
                                # Draw background for analytics
                                if len(analytics_lines) > 0:
                                    max_line_width = 0
                                    for line in analytics_lines:
                                        (w, h), _ = cv2.getTextSize(line, font_face, font_scale, thickness)
                                        max_line_width = max(max_line_width, w)
                                    
                                    rect_x1 = x + 40
                                    rect_y1 = analytics_y - 2
                                    rect_x2 = x + 40 + max_line_width + 8
                                    rect_y2 = analytics_y + len(analytics_lines) * line_height + 2
                                    
                                    h, w = display_frame.shape[:2]
                                    rect_x1 = max(0, min(rect_x1, w - 1))
                                    rect_y1 = max(0, min(rect_y1, h - 1))
                                    rect_x2 = max(rect_x1 + 1, min(rect_x2, w))
                                    rect_y2 = max(rect_y1 + 1, min(rect_y2, h))
                                    
                                    if rect_x2 > rect_x1 and rect_y2 > rect_y1:
                                        overlay = display_frame.copy()
                                        cv2.rectangle(overlay, (rect_x1, rect_y1), (rect_x2, rect_y2), (0, 0, 0), -1)
                                        cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
                                
                                # Draw analytics text using HD renderer
                                for i, line in enumerate(analytics_lines[:5]):
                                    text_y = analytics_y + i * line_height
                                    self.csv_hd_renderer.draw_crisp_text(
                                        display_frame,
                                        line,
                                        (x + 44, text_y),
                                        font_face,
                                        font_scale,
                                        analytics_color,
                                        thickness,
                                        outline_color=(0, 0, 0),
                                        outline_thickness=max(1, thickness // 2)
                                    )
        else:
            # Render analytics in panel/banner/bar position
            self._render_analytics_panel(display_frame, frame_num, analytics_pos)
        
        return display_frame
    
    def _render_analytics_panel(self, display_frame, frame_num, position):
        """Render analytics in a panel/banner/bar at the specified position."""
        # Debug: Log position on first frame
        if frame_num == 0:
            print(f"[DEBUG] _render_analytics_panel called with position='{position}' (type: {type(position)})")
            # Reset debug flags on first frame to ensure logging works
            if hasattr(self, '_banner_layout_logged'):
                delattr(self, '_banner_layout_logged')
            if hasattr(self, '_banner_columns_logged'):
                delattr(self, '_banner_columns_logged')
        # CRITICAL FIX: Try to find nearest frame with analytics data if current frame is missing
        # This ensures analytics update smoothly during playback even if some frames lack data
        original_frame_num = frame_num
        if frame_num not in self.analytics_data:
            # Try to find nearest frame with analytics (within ±5 frames for smooth playback)
            nearest_frame = None
            min_distance = float('inf')
            for existing_frame in self.analytics_data.keys():
                distance = abs(existing_frame - frame_num)
                if distance < min_distance and distance <= 5:  # Only use nearby frames
                    min_distance = distance
                    nearest_frame = existing_frame
            if nearest_frame is not None:
                frame_num = nearest_frame  # Use nearest frame's analytics
            else:
                # No nearby analytics data - skip rendering for this frame
                if frame_num % 100 == 0:  # Only log every 100 frames to avoid spam
                    print(f"⚠ DEBUG: Frame {original_frame_num} not in analytics_data (keys: {list(self.analytics_data.keys())[:5]}...)")
                return
        
        if not self.analytics_data[frame_num]:
            if frame_num % 100 == 0:
                print(f"⚠ DEBUG: Frame {frame_num} has empty analytics_data")
            return
        
        # Detect if using imperial units
        use_imperial = 'player_speed_mph' in self.df.columns if self.df is not None else False
        
        # Collect analytics for all players in this frame (with player colors)
        all_analytics = []
        for player_id, analytics_dict in self.analytics_data[frame_num].items():
            player_id_int = int(player_id)
            # Get player name
            player_name = f"Player #{player_id_int}"
            if hasattr(self, 'player_names') and self.player_names:
                player_name = self.player_names.get(str(player_id_int), player_name)
            elif hasattr(self, 'player_data') and frame_num in self.player_data:
                if player_id_int in self.player_data[frame_num]:
                    player_info = self.player_data[frame_num][player_id_int]
                    if len(player_info) >= 4:
                        player_name = player_info[3]  # Name is 4th element
            
            # Get player team for color lookup
            player_team = None
            if hasattr(self, 'player_data') and frame_num in self.player_data:
                if player_id_int in self.player_data[frame_num]:
                    player_info = self.player_data[frame_num][player_id_int]
                    if len(player_info) >= 3:
                        player_team = player_info[2]  # Team is 3rd element
            
            # Get player color (matching foot tracker color - use same method as foot trackers)
            # This ensures analytics player name color matches the foot tracker color exactly
            player_color = (255, 255, 255)  # Default white
            try:
                # Use the same get_player_color method as foot trackers (checks per-player settings first)
                if hasattr(self, 'get_player_color'):
                    player_color = self.get_player_color(player_id_int, player_team, player_name)
                    # Debug: Verify color matches foot tracker color (log for first few frames)
                    if original_frame_num <= 2:
                        print(f"[DEBUG] Player {player_id_int} ({player_name[:20]}): banner color={player_color} (BGR) - should match foot tracker color")
                elif hasattr(self, 'team_colors') and self.team_colors:
                    # Fallback: use team-based color if get_player_color method not available
                    from combined_analysis_optimized import get_player_color
                    viz_color_mode = "team"  # Default to team colors
                    if hasattr(self, 'viz_color_mode') and hasattr(self.viz_color_mode, 'get'):
                        viz_color_mode = self.viz_color_mode.get()
                    player_color = get_player_color(player_id_int, player_team, viz_color_mode, self.team_colors)
            except (ImportError, AttributeError, Exception):
                # Fallback: use team-based color if available
                if player_team and hasattr(self, 'team_colors') and self.team_colors and 'team_colors' in self.team_colors:
                    team_name_lower = player_team.lower() if player_team else ""
                    for team_key in ["team1", "team2"]:
                        team_data = self.team_colors['team_colors'].get(team_key, {})
                        if team_data.get('name', '').lower() == team_name_lower:
                            tracker_color = team_data.get('tracker_color_bgr', None)
                            if tracker_color and isinstance(tracker_color, (list, tuple)) and len(tracker_color) >= 3:
                                player_color = tuple(tracker_color[:3])
                                break
            
            # Get analytics text for this player
            analytics_lines = self.get_analytics_text(player_id_int, frame_num, use_imperial)
            if analytics_lines:
                all_analytics.append((player_name, analytics_lines, player_color, player_id_int))
        
        if not all_analytics:
            # Debug: Log why banner is empty
            if frame_num == 0 or frame_num % 100 == 0:  # Log on first frame and every 100 frames
                print(f"⚠ DEBUG: Analytics banner empty at frame {frame_num} - no analytics lines returned")
                print(f"   Analytics preferences: {self.analytics_preferences}")
                print(f"   Analytics data keys for frame: {list(self.analytics_data[frame_num].keys()) if frame_num in self.analytics_data else 'N/A'}")
            return
        
        # STATIC ORDERING: Sort by player ID (or name) to keep positions consistent across frames
        # This prevents players from switching positions in the banner as they move
        all_analytics.sort(key=lambda x: (x[3], x[0]))  # Sort by player_id_int, then player_name
        
        # FIXED COLUMN ASSIGNMENT: Maintain consistent column positions across frames
        # Initialize column mapping on first frame or when new players appear
        if not hasattr(self, '_player_column_map'):
            self._player_column_map = {}  # player_id -> column_index
            self._column_player_map = {}  # column_index -> player_id (reverse mapping)
        
        # Update column mapping: assign columns to players in sorted order
        # This ensures players stay in the same column even if some are missing in a frame
        current_player_ids = {x[3] for x in all_analytics}  # Set of player IDs in current frame
        
        # If we have new players or the mapping is empty, rebuild it
        if not self._player_column_map or not current_player_ids.issubset(self._player_column_map.keys()):
            # Rebuild mapping: assign columns to all known players in sorted order
            all_known_players = sorted(set(list(self._player_column_map.keys()) + list(current_player_ids)))
            self._player_column_map = {player_id: idx for idx, player_id in enumerate(all_known_players)}
            self._column_player_map = {idx: player_id for player_id, idx in self._player_column_map.items()}
        
        # Reorder all_analytics to match fixed column assignments
        # Create a dictionary for quick lookup
        analytics_by_id = {x[3]: x for x in all_analytics}
        
        # Build ordered list based on column assignments (only include players present in current frame)
        ordered_analytics = []
        for col_idx in sorted(self._column_player_map.keys()):
            player_id = self._column_player_map[col_idx]
            if player_id in analytics_by_id:
                ordered_analytics.append(analytics_by_id[player_id])
        
        # Replace all_analytics with ordered version
        all_analytics = ordered_analytics
        
        h, w = display_frame.shape[:2]
        
        # Calculate position and size based on setting (similar to statistics overlay)
        # Use configurable sizes from GUI
        banner_height = self._safe_get_int(self.analytics_banner_height, 500) if hasattr(self, 'analytics_banner_height') else 500
        bar_width = self._safe_get_int(self.analytics_bar_width, 250) if hasattr(self, 'analytics_bar_width') else 250
        panel_width = self._safe_get_int(self.analytics_panel_width, 300) if hasattr(self, 'analytics_panel_width') else 300
        panel_height = self._safe_get_int(self.analytics_panel_height, 200) if hasattr(self, 'analytics_panel_height') else 200
        default_panel_size = (panel_width, panel_height)
        
        # Normalize position value (strip whitespace, handle case)
        original_position = position
        position = str(position).strip().lower() if position else "with_player"
        if frame_num == 0:
            print(f"[DEBUG] Position normalization: '{original_position}' -> '{position}'")
        
        if position == "top_banner":
            # Clamp banner height to reasonable range (not larger than screen)
            banner_height = min(banner_height, h - 20)  # Leave at least 20px margin
            pos = (0, 0)
            panel_size = (w, banner_height)
        elif position == "bottom_banner":
            # Clamp banner height to reasonable range
            banner_height = min(banner_height, h - 20)  # Leave at least 20px margin
            pos = (0, h - banner_height)
            panel_size = (w, banner_height)
        elif position == "left_bar":
            # Clamp bar width to reasonable range (not larger than screen)
            bar_width = min(bar_width, w - 20)  # Leave at least 20px margin
            pos = (0, 0)
            panel_size = (bar_width, h)
        elif position == "right_bar":
            # Clamp bar width to reasonable range
            bar_width = min(bar_width, w - 20)  # Leave at least 20px margin
            pos = (w - bar_width, 0)
            panel_size = (bar_width, h)
        elif position == "top_left":
            pos = (10, 10)
            panel_size = default_panel_size
        elif position == "top_right":
            # Clamp panel width to fit on screen
            panel_width = min(panel_width, w - 20)
            pos = (w - panel_width - 10, 10)
            panel_size = (panel_width, panel_height)
        elif position == "bottom_left":
            # Clamp panel height to fit on screen
            panel_height = min(panel_height, h - 20)
            pos = (10, h - panel_height - 10)
            panel_size = (panel_width, panel_height)
        else:  # bottom_right
            # Clamp panel size to fit on screen
            panel_width = min(panel_width, w - 20)
            panel_height = min(panel_height, h - 20)
            pos = (w - panel_width - 10, h - panel_height - 10)
            panel_size = (panel_width, panel_height)
        
        # Draw panel background (semi-transparent)
        overlay = display_frame.copy()
        cv2.rectangle(overlay, pos, (pos[0] + panel_size[0], pos[1] + panel_size[1]), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
        
        # Draw analytics content using customizable font and color settings
        font_scale = self._safe_get_double(self.analytics_font_scale, 1.0) if hasattr(self, 'analytics_font_scale') else 1.0
        thickness = self._safe_get_int(self.analytics_font_thickness, 2) if hasattr(self, 'analytics_font_thickness') else 2
        
        # Get font face (must be defined before line_height calculation)
        font_face_str = self.analytics_font_face.get() if hasattr(self, 'analytics_font_face') else "FONT_HERSHEY_SIMPLEX"
        font_face = getattr(cv2, font_face_str, cv2.FONT_HERSHEY_SIMPLEX)
        
        # Calculate line height based on font size (more compact for banners)
        # Use actual text height calculation instead of fixed multiplier
        (text_width, text_height), baseline = cv2.getTextSize("Test", font_face, font_scale, thickness)
        line_height = text_height + 10  # Add 10px spacing between lines for better readability
        title_font_scale = font_scale * 1.2  # Title slightly larger
        title_thickness = max(2, thickness + 1)  # Title slightly thicker
        
        # Get analytics color (default to white for better contrast)
        # Use proper color retrieval method that handles RGB string conversion
        # Debug: Always log color retrieval for first few frames to diagnose issues
        if original_frame_num <= 2:
            print(f"[DEBUG] Getting analytics color: original_frame={original_frame_num}, position='{position}'")
            print(f"[DEBUG]   use_custom_analytics_color exists: {hasattr(self, 'use_custom_analytics_color')}")
            if hasattr(self, 'use_custom_analytics_color'):
                print(f"[DEBUG]   use_custom_analytics_color value: {self.use_custom_analytics_color.get()}")
            if hasattr(self, 'analytics_color_rgb'):
                print(f"[DEBUG]   analytics_color_rgb: '{self.analytics_color_rgb.get()}'")
        
        if hasattr(self, 'use_custom_analytics_color') and self.use_custom_analytics_color.get():
            try:
                analytics_color = self._get_analytics_color_bgr()
                # Debug: Log color retrieval for first few frames
                if original_frame_num <= 2:
                    rgb_string = self.analytics_color_rgb.get() if hasattr(self, 'analytics_color_rgb') else 'N/A'
                    print(f"[DEBUG] Analytics color retrieved: RGB string='{rgb_string}', BGR tuple={analytics_color}")
            except Exception as e:
                # Fallback if color retrieval fails
                analytics_color = (255, 255, 255)  # White in BGR
                if original_frame_num <= 2:
                    print(f"[ERROR] Failed to get analytics color: {e}, using white fallback")
                    import traceback
                    traceback.print_exc()
        else:
            analytics_color = (255, 255, 255)  # Default white for maximum contrast (BGR format)
            if original_frame_num <= 2:
                print(f"[DEBUG] Using default white analytics color (custom color disabled)")
        
        # Get title color
        title_color = (
            self._safe_get_int(self.analytics_title_color_b, 0) if hasattr(self, 'analytics_title_color_b') else 0,
            self._safe_get_int(self.analytics_title_color_g, 255) if hasattr(self, 'analytics_title_color_g') else 255,
            self._safe_get_int(self.analytics_title_color_r, 255) if hasattr(self, 'analytics_title_color_r') else 255
        )
        
        # Start position for text (with padding) - more compact for banners
        text_x = pos[0] + 10
        if position in ["top_banner", "bottom_banner"]:
            # For banners, position text relative to banner height
            # Use a percentage of banner height for top padding (e.g., 5% of banner height)
            banner_padding = max(15, int(panel_size[1] * 0.05))  # At least 15px, or 5% of banner height
            text_y = pos[1] + banner_padding
        else:
            text_y = pos[1] + 25  # Keep original padding for panels
            # Draw title for panels only (skip for banners to save space)
            title = "Player Analytics"
            self.csv_hd_renderer.draw_crisp_text(
                display_frame, title, (text_x, text_y),
                font_face, title_font_scale,
                title_color, title_thickness,
                outline_color=(0, 0, 0), outline_thickness=1
            )
            text_y += 25
        
        # Draw analytics for each player
        max_players = 8 if position in ["top_banner", "bottom_banner"] else 10
        max_players = 6 if position in ["left_bar", "right_bar"] else max_players
        
        # HORIZONTAL COLUMN LAYOUT: For banner positions, display players in columns
        # Debug: Check if we're in banner mode
        is_banner = position in ["top_banner", "bottom_banner"]
        if frame_num == 0:
            print(f"[DEBUG] Banner check: position='{position}', is_banner={is_banner}, all_analytics count={len(all_analytics)}")
            print(f"[DEBUG] Panel size: {panel_size}, pos: {pos}, text_y: {text_y}")
        
        if is_banner:
            # Determine optimal number of columns (4-5 evenly spaced across full banner)
            total_players = len(all_analytics)
            
            if frame_num == 0:
                print(f"[DEBUG] Banner mode: total_players={total_players}, max_players={max_players}, position='{position}'")
            
            # Always try to show 4-5 columns if we have enough players
            if total_players >= 4:
                target_columns = min(5, total_players, max_players)
            else:
                target_columns = min(total_players, max_players)
            num_players = min(total_players, target_columns, max_players)
            
            # Ensure we show at least 1 player if we have any analytics
            if num_players == 0 and total_players > 0:
                num_players = 1
            
            if frame_num == 0:
                print(f"[DEBUG] Banner: target_columns={target_columns}, num_players={num_players}, total_players={total_players}")
            
            if num_players > 0:
                # Use all available width, divide evenly with spacing between columns
                total_padding = 20  # 10px on each side
                column_spacing = 20  # Space between columns (increased for better separation)
                
                # Calculate available width for columns (total width minus padding)
                available_width = panel_size[0] - total_padding
                
                # Subtract spacing between columns (only if more than 1 column)
                if num_players > 1:
                    available_width -= column_spacing * (num_players - 1)
                
                # Calculate column width (divide available width evenly)
                column_width = available_width // num_players
                
                # Debug: Always log on first frame to see what's happening
                if not hasattr(self, '_banner_layout_logged'):
                    self._banner_layout_logged = True
                    print(f"[DEBUG] Banner analytics layout:")
                    print(f"  Position: {position}, Total players: {total_players}, Showing: {num_players}")
                    print(f"  Panel size: {panel_size[0]}x{panel_size[1]}")
                    print(f"  Column width: {column_width}, Spacing: {column_spacing}")
                    print(f"  Available width: {available_width}, Padding: {total_padding}")
                
                # Calculate max lines per player based on available banner height
                # Account for title, player name, and spacing
                # text_y is relative to panel start, so available height is panel_size[1] - (text_y - pos[1]) - 15
                text_y_offset = text_y - pos[1]  # Offset from panel top
                available_height = panel_size[1] - text_y_offset - 15  # Leave 15px bottom margin
                # Use a more generous calculation: allow all analytics lines to show
                # Each line needs about line_height * 0.8 pixels (with compact spacing)
                lines_per_pixel = 1.0 / (line_height * 0.8)  # Lines per pixel
                max_lines = max(len(all_analytics[0][1]) if all_analytics and len(all_analytics[0]) > 1 else 10, 
                               int(available_height * lines_per_pixel))  # Show all analytics or fit in banner
                if original_frame_num <= 1:
                    print(f"[DEBUG] max_lines calculation: available_height={available_height}, line_height={line_height}, text_y_offset={text_y_offset}, max_lines={max_lines}")
                
                # Debug: Log all column positions before drawing (only once)
                if not hasattr(self, '_banner_columns_logged'):
                    self._banner_columns_logged = True
                    print(f"  Column positions (showing {num_players} of {total_players} players):")
                    for test_idx in range(num_players):
                        test_col_x = pos[0] + 10 + (test_idx * (column_width + column_spacing))
                        test_player_name = all_analytics[test_idx][0] if test_idx < len(all_analytics) else "N/A"
                        print(f"    Column {test_idx} ({test_player_name[:20]}): x={test_col_x}, width={column_width}, right={test_col_x + column_width}")
                
                # Debug column drawing removed - no longer needed
                
                # Draw each player in their own column (horizontally, evenly spaced across full banner)
                # Use original_frame_num for debug logging since frame_num might be modified
                h_frame, w_frame = display_frame.shape[:2]
                if original_frame_num <= 1:  # Log for first 2 frames
                    print(f"[DEBUG] About to draw {num_players} players in banner. text_y={text_y}, pos={pos}, panel_size={panel_size}, frame={original_frame_num}, display_frame_size={w_frame}x{h_frame}")
                    
                    # Draw a test rectangle to verify banner area is visible
                    test_rect_color = (0, 255, 0) if position == "bottom_banner" else (255, 0, 0)  # Green for bottom, red for top
                    cv2.rectangle(display_frame, pos, (pos[0] + panel_size[0], pos[1] + panel_size[1]), test_rect_color, 3)
                    print(f"[DEBUG] Drew test rectangle at {pos} with size {panel_size}, color={test_rect_color}")
                
                for col_idx, (player_name, analytics_lines, player_color, player_id) in enumerate(all_analytics[:num_players]):
                    # Calculate column X position with proper spacing
                    # Evenly distribute columns across full banner width
                    # Formula: start_pos + padding + (column_index * (column_width + spacing))
                    col_x = pos[0] + 10 + (col_idx * (column_width + column_spacing))
                    col_y = text_y
                    
                    if original_frame_num <= 1 and col_idx < 2:
                        print(f"[DEBUG] Drawing player {col_idx} ({player_name[:20]}): col_x={col_x}, col_y={col_y}, color={player_color}, analytics_lines={len(analytics_lines)}")
                    
                    # Calculate the right edge of this column to ensure no overflow
                    col_right_edge = col_x + column_width
                    
                    # Ensure column doesn't exceed panel bounds
                    if col_right_edge > pos[0] + panel_size[0] - 10:
                        # This shouldn't happen with correct calculation, but log if it does
                        if frame_num % 100 == 0:
                            print(f"[WARNING] Column {col_idx} exceeds bounds: x={col_x}, width={column_width}, right={col_right_edge}, panel_width={panel_size[0]}")
                        break  # Don't draw beyond panel bounds
                    
                    # Draw player name header in player's track color (compact)
                    name_font_scale = font_scale * 0.95  # Slightly smaller for compact fit
                    
                    # Truncate player name if too long for column
                    max_name_width = column_width - 5  # Leave 5px margin
                    (name_width, _), _ = cv2.getTextSize(player_name, font_face, name_font_scale, max(thickness, 2))
                    display_name = player_name
                    if name_width > max_name_width:
                        truncated_name = player_name
                        while name_width > max_name_width and len(truncated_name) > 3:
                            truncated_name = truncated_name[:-1]
                            (name_width, _), _ = cv2.getTextSize(truncated_name + "...", font_face, name_font_scale, max(thickness, 2))
                        display_name = truncated_name + "..." if truncated_name != player_name else player_name
                    
                    try:
                        # Ensure coordinates are within frame bounds
                        h_frame, w_frame = display_frame.shape[:2]
                        if col_x < 0 or col_x >= w_frame or col_y < 0 or col_y >= h_frame:
                            if original_frame_num <= 1:
                                print(f"[WARNING] Text coordinates out of bounds: ({col_x}, {col_y}), frame size: {w_frame}x{h_frame}")
                        else:
                            # OPTIMIZED: Use cv2.putText for banner mode to ensure color works correctly
                            # Get text size for background rectangle (cache to avoid recalculation)
                            (name_w, name_h), _ = cv2.getTextSize(display_name, font_face, name_font_scale, max(thickness, 2))
                            name_bg_y1 = col_y - name_h - 3
                            name_bg_y2 = col_y + 3
                            name_bg_x1 = col_x - 3
                            name_bg_x2 = col_x + name_w + 3
                            
                            # Draw simple filled rectangle (much faster than copy + addWeighted)
                            cv2.rectangle(display_frame, (name_bg_x1, name_bg_y1), (name_bg_x2, name_bg_y2), (0, 0, 0), -1)
                            
                            # Ensure player_color is valid (BGR tuple, 0-255)
                            if not isinstance(player_color, tuple) or len(player_color) != 3:
                                player_color = (255, 255, 255)  # White fallback
                            player_color = tuple(max(0, min(255, int(c))) for c in player_color)
                            
                            # Debug: Log color being used for first few frames
                            if original_frame_num <= 2 and col_idx < 2:
                                print(f"[DEBUG] About to draw player name: color={player_color} (BGR), name='{display_name}'")
                                print(f"[DEBUG]   Position: ({col_x}, {col_y}), font_scale={name_font_scale}, thickness={max(thickness, 2)}")
                            
                            # Draw text with outline for visibility (same approach as analytics lines)
                            name_outline_thickness = max(2, thickness + 1)
                            # Draw black outline first
                            for dx, dy in [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]:
                                cv2.putText(
                                    display_frame, display_name, (col_x + dx, col_y + dy),
                                    font_face, name_font_scale,
                                    (0, 0, 0), name_outline_thickness,  # Black outline
                                    cv2.LINE_AA
                                )
                            # Draw main text with player's track color
                            cv2.putText(
                                display_frame, display_name, (col_x, col_y),
                                font_face, name_font_scale,
                                player_color, max(thickness, 2),
                                cv2.LINE_AA
                            )
                            if original_frame_num <= 1 and col_idx < 2:  # Log for first 2 frames
                                print(f"[DEBUG] Drew player name '{display_name}' at ({col_x}, {col_y}), color={player_color}, frame={original_frame_num}, frame_size={w_frame}x{h_frame}")
                    except Exception as e:
                        print(f"[ERROR] Failed to draw player name '{display_name}': {e}")
                        import traceback
                        traceback.print_exc()
                    
                    col_y += int(line_height * 0.8)  # Compact spacing after name (80% of line height)
                    
                    # Draw analytics lines in this column (compact)
                    analytics_font_scale = font_scale * 0.85  # Smaller font for analytics to fit more
                    analytics_thickness = max(2, thickness)  # Ensure minimum thickness of 2 for visibility
                    
                    # Debug: Always log analytics info for first 2 frames
                    if original_frame_num <= 1 and col_idx < 2:
                        print(f"[DEBUG] About to draw analytics for player {col_idx} ({player_name[:20]}). analytics_lines count={len(analytics_lines)}, max_lines={max_lines}, col_y={col_y}, panel_bottom={pos[1] + panel_size[1] - 10}")
                        print(f"[DEBUG] Analytics color: {analytics_color} (BGR format), font_scale={analytics_font_scale}, thickness={max(1, thickness - 1)}")
                        if len(analytics_lines) > 0:
                            print(f"[DEBUG] First few analytics lines: {analytics_lines[:3]}")
                        else:
                            print(f"[WARNING] analytics_lines is EMPTY for player {col_idx} ({player_name[:20]})")
                        
                        # Draw a test rectangle to verify coordinates are correct
                        test_rect_x1 = col_x
                        test_rect_y1 = col_y
                        test_rect_x2 = col_x + 200
                        test_rect_y2 = col_y + 50
                        cv2.rectangle(display_frame, (test_rect_x1, test_rect_y1), (test_rect_x2, test_rect_y2), (0, 255, 255), 2)  # Cyan rectangle
                        print(f"[DEBUG] Drew test rectangle at ({test_rect_x1}, {test_rect_y1}) to ({test_rect_x2}, {test_rect_y2}) in CYAN")
                    
                    # CRITICAL: Check if analytics_lines is empty - if so, skip the loop
                    if len(analytics_lines) == 0:
                        if original_frame_num <= 1 and col_idx < 2:
                            print(f"[WARNING] Skipping analytics loop - analytics_lines is empty for player {col_idx}")
                        continue  # Skip to next player if no analytics
                    
                    # Draw analytics lines
                    analytics_drawn_count = 0
                    for line_idx, line in enumerate(analytics_lines[:max_lines]):
                        # Check bounds before drawing
                        if col_y + line_height > pos[1] + panel_size[1] - 10:
                            if original_frame_num <= 1 and col_idx < 2:
                                print(f"[DEBUG] Skipping analytics line {line_idx} - would exceed panel bounds: col_y={col_y}, line_height={line_height}, panel_bottom={pos[1] + panel_size[1] - 10}")
                            break  # Don't draw beyond panel bounds
                        
                        # Truncate line if it's too long for column width (strict enforcement)
                        max_line_width = column_width - 5  # Leave 5px margin on each side
                        (line_width, _), _ = cv2.getTextSize(line, font_face, analytics_font_scale, max(1, thickness - 1))
                        
                        # Ensure text doesn't exceed column boundary
                        if line_width > max_line_width:
                            # Truncate line to fit within column
                            truncated_line = line
                            while line_width > max_line_width and len(truncated_line) > 3:
                                truncated_line = truncated_line[:-1]
                                (line_width, _), _ = cv2.getTextSize(truncated_line + "...", font_face, analytics_font_scale, max(1, thickness - 1))
                            line = truncated_line + "..." if truncated_line != line else line
                        
                        # Double-check: ensure text position + width doesn't exceed column boundary
                        final_x = col_x
                        (final_width, _), _ = cv2.getTextSize(line, font_face, analytics_font_scale, max(1, thickness - 1))
                        if final_x + final_width > col_right_edge - 5:
                            # Further truncate if needed
                            while final_x + final_width > col_right_edge - 5 and len(line) > 3:
                                if line.endswith("..."):
                                    line = line[:-4]
                                else:
                                    line = line[:-1]
                                (final_width, _), _ = cv2.getTextSize(line + "...", font_face, analytics_font_scale, max(1, thickness - 1))
                            if not line.endswith("..."):
                                line = line + "..."
                        
                        # Draw text with explicit color check and background for visibility
                        try:
                            # Verify color is valid (ensure it's BGR tuple)
                            if not isinstance(analytics_color, tuple) or len(analytics_color) != 3:
                                print(f"[ERROR] Invalid analytics_color: {analytics_color}, using white")
                                analytics_color = (255, 255, 255)  # White in BGR
            
                            # Ensure color values are valid (0-255)
                            analytics_color = tuple(max(0, min(255, int(c))) for c in analytics_color)
                            
                            # Safety check: If color is too dark (close to black), force to white for visibility
                            # Check if average brightness is less than 50 (out of 255)
                            avg_brightness = sum(analytics_color) / 3.0
                            if avg_brightness < 50:
                                if original_frame_num <= 1 and col_idx < 2:
                                    print(f"[WARNING] Analytics color too dark ({analytics_color}, avg={avg_brightness:.1f}), forcing to white")
                                analytics_color = (255, 255, 255)  # Force white for visibility
                            
                            # OPTIMIZED: Use only crisp renderer (no expensive copy/addWeighted/nested loops)
                            # Get text size for background rectangle (cache to avoid recalculation)
                            (text_w, text_h), baseline = cv2.getTextSize(
                                line, font_face, analytics_font_scale, analytics_thickness
                            )
                            
                            # Draw simple filled rectangle (much faster than copy + addWeighted)
                            bg_y1 = col_y - text_h - 3
                            bg_y2 = col_y + 3
                            bg_x1 = final_x - 3
                            bg_x2 = final_x + text_w + 3
                            cv2.rectangle(display_frame, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)
                            
                            # Always use cv2.putText for banner mode to ensure color works correctly
                            # (crisp renderer may have color issues in banner mode)
                            # Debug: Log color being used for first few frames
                            if original_frame_num <= 2 and col_idx < 2 and line_idx < 2:
                                print(f"[DEBUG] About to draw text: color={analytics_color} (BGR), line='{line[:30]}...'")
                                print(f"[DEBUG]   Position: ({final_x}, {col_y}), font_scale={analytics_font_scale}, thickness={analytics_thickness}")
                            
                            # Draw text with outline for visibility
                            outline_thickness = max(2, analytics_thickness + 1)
                            # Draw black outline first
                            for dx, dy in [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]:
                                cv2.putText(
                                    display_frame, line, (final_x + dx, col_y + dy),
                                    font_face, analytics_font_scale,
                                    (0, 0, 0), outline_thickness,  # Black outline
                                    cv2.LINE_AA
                                )
                            # Draw main text with user-selected color
                            cv2.putText(
                                display_frame, line, (final_x, col_y),
                                font_face, analytics_font_scale,
                                analytics_color, analytics_thickness,
                                cv2.LINE_AA
                            )
                            text_drawn = True
                            
                            analytics_drawn_count += 1
                            if original_frame_num <= 1 and col_idx < 2 and line_idx < 3:
                                print(f"[DEBUG] Drew analytics line {line_idx}: '{line[:40]}...' at ({final_x}, {col_y})")
                                print(f"[DEBUG]   Color used: {analytics_color} (BGR format)")
                                print(f"[DEBUG]   Text size: {text_w}x{text_h}, font_scale={analytics_font_scale}, thickness={analytics_thickness}")
                                print(f"[DEBUG]   Background rect: ({bg_x1}, {bg_y1}) to ({bg_x2}, {bg_y2})")
                                # Draw a small dot at the text position to verify coordinates
                                cv2.circle(display_frame, (final_x, col_y), 5, (255, 0, 255), -1)  # Magenta dot
                        except Exception as e:
                            print(f"[ERROR] Failed to draw analytics line {line_idx}: {e}")
                            import traceback
                            traceback.print_exc()
                        col_y += int(line_height * 1.1)  # Line spacing (110% of line height for better readability)
                    
                    # Debug: Report how many analytics lines were drawn
                    if original_frame_num <= 1 and col_idx < 2:
                        print(f"[DEBUG] Finished drawing analytics for player {col_idx}: drew {analytics_drawn_count} lines out of {len(analytics_lines)} available (max_lines={max_lines})")
                    
                    # Add track ID at the bottom of the analytics column for diagnosis
                    try:
                        # Calculate position at bottom of column (with some margin from panel bottom)
                        track_id_y = pos[1] + panel_size[1] - 15  # 15px from bottom
                        track_id_text = f"Track ID: {player_id}"
                        
                        # Get text size for track ID
                        (track_id_w, track_id_h), _ = cv2.getTextSize(
                            track_id_text, font_face, analytics_font_scale * 0.75, analytics_thickness
                        )
                        
                        # Ensure track ID fits in column
                        track_id_x = col_x
                        if track_id_x + track_id_w > col_right_edge - 5:
                            # Truncate if needed
                            while track_id_x + track_id_w > col_right_edge - 5 and len(track_id_text) > 10:
                                track_id_text = track_id_text[:-1]
                                (track_id_w, track_id_h), _ = cv2.getTextSize(
                                    track_id_text, font_face, analytics_font_scale * 0.75, analytics_thickness
                                )
                        
                        # OPTIMIZED: Use only crisp renderer (no expensive copy/addWeighted/nested loops)
                        # Draw simple filled rectangle (much faster than copy + addWeighted)
                        track_id_bg_y1 = track_id_y - track_id_h - 2
                        track_id_bg_y2 = track_id_y + 2
                        track_id_bg_x1 = track_id_x - 2
                        track_id_bg_x2 = track_id_x + track_id_w + 2
                        cv2.rectangle(display_frame, (track_id_bg_x1, track_id_bg_y1), (track_id_bg_x2, track_id_bg_y2), (0, 0, 0), -1)
                        
                        # Use cv2.putText for banner mode to ensure color works correctly (same fix as analytics text)
                        # Use analytics_color to match other analytics text, or light gray if analytics_color is too dark
                        track_id_color = analytics_color  # Use same color as analytics text
                        # Ensure color is valid (BGR tuple, 0-255)
                        if not isinstance(track_id_color, tuple) or len(track_id_color) != 3:
                            track_id_color = (200, 200, 200)  # Light gray fallback
                        track_id_color = tuple(max(0, min(255, int(c))) for c in track_id_color)
                        
                        # Safety check: If color is too dark, use light gray for visibility
                        avg_brightness = sum(track_id_color) / 3.0
                        if avg_brightness < 100:  # If too dark, use light gray
                            track_id_color = (200, 200, 200)  # Light gray for track ID
                        
                        # Draw text with outline for visibility (same approach as analytics lines)
                        track_id_outline_thickness = max(2, analytics_thickness + 1)
                        # Draw black outline first
                        for dx, dy in [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]:
                            cv2.putText(
                                display_frame, track_id_text, (track_id_x + dx, track_id_y + dy),
                                font_face, analytics_font_scale * 0.75,
                                (0, 0, 0), track_id_outline_thickness,  # Black outline
                                cv2.LINE_AA
                            )
                        # Draw main text with track ID color
                        cv2.putText(
                            display_frame, track_id_text, (track_id_x, track_id_y),
                            font_face, analytics_font_scale * 0.75,
                            track_id_color, analytics_thickness,
                            cv2.LINE_AA
                        )
                    except Exception as e:
                        if original_frame_num <= 1:
                            print(f"[ERROR] Failed to draw track ID for player {player_id}: {e}")
            else:
                if frame_num == 0:
                    print(f"[DEBUG] Banner: num_players={num_players}, skipping banner draw (no players)")
        else:
            # VERTICAL LAYOUT: For non-banner positions (panels/bars), keep vertical stacking
            for player_name, analytics_lines, player_color, player_id in all_analytics[:max_players]:
                # Player name header in player's track color
                self.csv_hd_renderer.draw_crisp_text(
                    display_frame, f"--- {player_name} ---", (text_x, text_y),
                    font_face, font_scale,
                    player_color, max(thickness + 1, 3),  # Use player's track color
                    outline_color=(0, 0, 0), outline_thickness=max(1, thickness // 2)
                )
                text_y += int(line_height * 0.9)  # Tighter spacing after player name
                
                # Analytics lines (limit to 3-4 lines per player depending on position)
                max_lines = 3 if position in ["left_bar", "right_bar"] else 4
                for line in analytics_lines[:max_lines]:
                    if text_y + line_height > pos[1] + panel_size[1] - 10:
                        break  # Don't draw beyond panel bounds
                    self.csv_hd_renderer.draw_crisp_text(
                        display_frame, line, (text_x + 10, text_y),
                        font_face, font_scale * 0.9,
                        analytics_color, thickness,
                        outline_color=(0, 0, 0), outline_thickness=max(1, thickness // 2)
                    )
                    text_y += int(line_height * 0.7)  # Tighter line spacing (70% of line height)
                
                text_y += 5  # Spacing between players
    
    def load_analytics_preferences(self):
        """Load analytics preferences from file"""
        prefs_file = "analytics_preferences.json"
        if os.path.exists(prefs_file):
            try:
                with open(prefs_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load analytics preferences: {e}")
        return {}
    
    def format_analytics_value(self, key, value, use_imperial=False):
        """Format analytics value for display"""
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return None
        
        # Check if we should use imperial units
        if use_imperial:
            # Use imperial column if available
            if key == 'current_speed' or key == 'player_speed_mps':
                return f"{value:.1f} mph" if 'mph' in str(value) or isinstance(value, (int, float)) else str(value)
            elif key == 'distance_traveled' or key == 'distance_traveled_m':
                return f"{value:.1f} ft" if isinstance(value, (int, float)) else str(value)
            # Add more imperial conversions as needed
        
        # Format based on key
        if 'speed' in key.lower() or 'mph' in key.lower():
            if isinstance(value, (int, float)):
                return f"{value:.1f} mph" if 'mph' in key else f"{value:.1f} m/s"
        elif 'distance' in key.lower() or 'dist' in key.lower():
            if isinstance(value, (int, float)):
                return f"{value:.1f} ft" if 'ft' in key else f"{value:.1f} m"
        elif 'angle' in key.lower():
            if isinstance(value, (int, float)):
                return f"{value:.0f}°"
        elif 'time' in key.lower():
            if isinstance(value, (int, float)):
                return f"{value:.1f}s"
        elif 'pct' in key.lower() or 'percent' in key.lower():
            if isinstance(value, (int, float)):
                return f"{value:.1f}%"
        elif 'count' in key.lower() or 'events' in key.lower() or 'changes' in key.lower():
            return f"{int(value)}"
        
        return str(value)
    
    def get_analytics_text(self, player_id, frame_num, use_imperial=False):
        """Get formatted analytics text for a player"""
        if frame_num not in self.analytics_data or player_id not in self.analytics_data[frame_num]:
            return []
        
        analytics = self.analytics_data[frame_num][player_id].copy()  # Make a copy to modify
        
        # Load event counts from player gallery if not already in analytics
        if not any(key.startswith('pass_count') or key.startswith('shot_count') or 
                   key.startswith('tackle_count') or key.startswith('goal_count') or 
                   key.startswith('total_events') for key in analytics.keys()):
            try:
                # Get player name
                player_name = f"Player #{player_id}"
                if hasattr(self, 'player_names') and self.player_names:
                    player_name = self.player_names.get(str(player_id), player_name)
                elif hasattr(self, 'player_data') and frame_num in self.player_data:
                    if player_id in self.player_data[frame_num]:
                        player_info = self.player_data[frame_num][player_id]
                        if len(player_info) >= 4:
                            player_name = player_info[3]  # Name is 4th element
                
                # Load event counts from gallery (use cached instance)
                if not hasattr(self, '_player_gallery') or self._player_gallery is None:
                    try:
                        from player_gallery import PlayerGallery
                        self._player_gallery = PlayerGallery()
                    except Exception as e:
                        self._player_gallery = None
                
                event_counts = None
                if self._player_gallery is not None:
                    try:
                        event_counts = self._player_gallery.get_player_event_counts(player_name)
                    except:
                        pass
                
                if event_counts:
                    analytics['pass_count'] = event_counts.get('pass', 0)
                    analytics['shot_count'] = event_counts.get('shot', 0)
                    analytics['tackle_count'] = event_counts.get('tackle', 0)
                    analytics['goal_count'] = event_counts.get('goal', 0)
                    analytics['total_events'] = sum(event_counts.values())
            except Exception as e:
                # Silently fail if gallery not available
                pass
        
        lines = []
        
        # Map preference keys to CSV column names
        preference_to_column = {
            'current_speed': ['player_speed_mph', 'player_speed_mps'],
            'average_speed': ['avg_speed_mph', 'avg_speed_mps'],
            'max_speed': ['max_speed_mph', 'max_speed_mps'],
            'acceleration': ['player_acceleration_fts2', 'player_acceleration_mps2'],
            'distance_traveled': ['distance_traveled_ft', 'distance_traveled_m'],
            'distance_to_ball': ['distance_to_ball_px'],
            'distance_from_center': ['distance_from_center_ft', 'distance_from_center_m'],
            'distance_from_goal': ['distance_from_goal_ft', 'distance_from_goal_m'],
            'nearest_teammate': ['nearest_teammate_dist_ft', 'nearest_teammate_dist_m'],
            'nearest_opponent': ['nearest_opponent_dist_ft', 'nearest_opponent_dist_m'],
            'field_zone': ['field_zone'],
            'field_position': ['field_position_x_pct', 'field_position_y_pct'],
            'movement_angle': ['player_movement_angle'],
            'possession_time': ['possession_time_s'],
            'time_stationary': ['time_stationary_s'],
            'sprint_count': ['sprint_count'],
            'direction_changes': ['direction_changes'],
            'acceleration_events': ['acceleration_events'],
            'distance_walking': ['distance_walking_ft', 'distance_walking_m'],
            'distance_jogging': ['distance_jogging_ft', 'distance_jogging_m'],
            'distance_running': ['distance_running_ft', 'distance_running_m'],
            'distance_sprinting': ['distance_sprinting_ft', 'distance_sprinting_m'],
            'pass_count': ['pass_count'],  # Event counts from player gallery
            'shot_count': ['shot_count'],
            'tackle_count': ['tackle_count'],
            'goal_count': ['goal_count'],
            'total_events': ['total_events']
        }
        
        # Build display labels
        display_labels = {
            'current_speed': 'Speed',
            'average_speed': 'Avg Speed',
            'max_speed': 'Max Speed',
            'acceleration': 'Accel',
            'distance_traveled': 'Dist Traveled',
            'distance_to_ball': 'Dist to Ball',
            'distance_from_center': 'Dist from Center',
            'distance_from_goal': 'Dist from Goal',
            'nearest_teammate': 'Nearest Teammate',
            'nearest_opponent': 'Nearest Opponent',
            'field_zone': 'Zone',
            'field_position': 'Position',
            'movement_angle': 'Angle',
            'possession_time': 'Possession',
            'time_stationary': 'Stationary',
            'sprint_count': 'Sprints',
            'direction_changes': 'Dir Changes',
            'acceleration_events': 'Accel Events',
            'distance_walking': 'Walk',
            'distance_jogging': 'Jog',
            'distance_running': 'Run',
            'distance_sprinting': 'Sprint',
            'pass_count': 'Passes',
            'shot_count': 'Shots',
            'tackle_count': 'Tackles',
            'goal_count': 'Goals',
            'total_events': 'Total Events'
        }
        
        # Only show analytics that are enabled in preferences
        # If preferences are empty, don't show any analytics (user must select them)
        if not self.analytics_preferences:
            # Return empty list if no preferences are set - user must configure analytics first
            return []
        else:
            # Use preferences to filter analytics
            for pref_key, enabled in self.analytics_preferences.items():
                if not enabled:
                    continue
                
                if pref_key in preference_to_column:
                    columns = preference_to_column[pref_key]
                    value = None
                    
                    # Try to find value in analytics dict
                    for col in columns:
                        if col in analytics:
                            value = analytics[col]
                            break
                    
                    if value is not None:
                        # For speed metrics, prefer non-zero current speed over max speed if both are selected
                        if pref_key == 'max_speed':
                            # Check if current_speed is also selected and has a non-zero value
                            if 'current_speed' in self.analytics_preferences and self.analytics_preferences['current_speed']:
                                current_speed_cols = preference_to_column.get('current_speed', [])
                                for col in current_speed_cols:
                                    if col in analytics:
                                        current_val = analytics[col]
                                        if isinstance(current_val, (int, float)) and abs(current_val) > 0.01:
                                            # Current speed has a value, skip max speed to avoid clutter
                                            continue
                        
                        # Skip zero values for speed/acceleration (likely means no data yet)
                        if pref_key in ['current_speed', 'average_speed', 'max_speed', 'acceleration']:
                            if isinstance(value, (int, float)) and abs(value) < 0.01:
                                continue  # Skip very small values (essentially zero)
                        
                        formatted = self.format_analytics_value(pref_key, value, use_imperial)
                        if formatted:
                            label = display_labels.get(pref_key, pref_key)
                            
                            # Special handling for field_position (x/y)
                            if pref_key == 'field_position':
                                x_pct = analytics.get('field_position_x_pct')
                                y_pct = analytics.get('field_position_y_pct')
                                if x_pct is not None and y_pct is not None:
                                    lines.append(f"{label}: {x_pct:.1f}%, {y_pct:.1f}%")
                            else:
                                lines.append(f"{label}: {formatted}")
        
        return lines
    
    def open_analytics_selection(self):
        """Open Analytics Selection window"""
        try:
            from analytics_selection_gui import AnalyticsSelectionGUI
            
            # Define callbacks
            def apply_callback(preferences):
                """Apply preferences immediately and update display"""
                self.analytics_preferences = preferences
                # Update show_analytics checkbox
                has_selections = len([k for k, v in preferences.items() if v]) > 0
                if hasattr(self, 'show_analytics') and self.show_analytics is not None:
                    try:
                        if hasattr(self.show_analytics, 'winfo_exists') and self.show_analytics.winfo_exists():
                            self.show_analytics.set(has_selections)
                    except (tk.TclError, AttributeError, RuntimeError):
                        pass
                # Update selections label
                if hasattr(self, 'analytics_selections_label'):
                    self.update_analytics_selections_label()
                # Immediately update display
                if hasattr(self, 'canvas') and self.canvas is not None:
                    try:
                        if hasattr(self.canvas, 'winfo_exists') and self.canvas.winfo_exists():
                            self.render_overlays()
                            self.update_display()
                    except (tk.TclError, AttributeError, RuntimeError):
                        pass
            
            def save_to_project_callback(preferences):
                """Save preferences to project file"""
                # Try to find main GUI instance to save project
                # Check if parent window has a reference to main GUI
                main_gui = None
                try:
                    # Look for main GUI in root window's children or attributes
                    if hasattr(self.root, 'main_gui'):
                        main_gui = self.root.main_gui
                    # Or try to find it via window hierarchy
                    elif hasattr(self.root, 'winfo_children'):
                        for child in self.root.winfo_children():
                            if hasattr(child, 'main_gui'):
                                main_gui = child.main_gui
                                break
                except:
                    pass
                
                # If we found main GUI, save project
                if main_gui and hasattr(main_gui, 'analytics_preferences'):
                    main_gui.analytics_preferences = preferences
                    # Save project if project path exists
                    if hasattr(main_gui, 'current_project_path') and main_gui.current_project_path:
                        try:
                            main_gui.save_project()
                        except Exception as e:
                            print(f"Warning: Could not save project: {e}")
                else:
                    # Fallback: just apply preferences
                    apply_callback(preferences)
            
            analytics_window = AnalyticsSelectionGUI(
                self.root,
                apply_callback=apply_callback,
                save_to_project_callback=save_to_project_callback
            )
        except ImportError as e:
            messagebox.showerror("Error", f"Could not import analytics_selection_gui.py:\n{e}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Analytics Selection window:\n{e}")
    
    def reload_analytics_preferences(self):
        """Reload analytics preferences from file"""
        try:
            self.analytics_preferences = self.load_analytics_preferences()
            # Update show_analytics checkbox if preferences changed
            has_selections = len([k for k, v in self.analytics_preferences.items() if v]) > 0
            
            # CRITICAL: Check if widget exists before accessing
            try:
                if hasattr(self, 'show_analytics') and self.show_analytics is not None:
                    if hasattr(self.show_analytics, 'winfo_exists'):
                        if self.show_analytics.winfo_exists():
                            if has_selections != self.show_analytics.get():
                                self.show_analytics.set(has_selections)
            except (tk.TclError, AttributeError, RuntimeError):
                # Widget not available - skip
                pass
            
            # Update selections label in Analytics tab
            if hasattr(self, 'analytics_selections_label'):
                self.update_analytics_selections_label()
            
            # Only update display if widgets are ready
            try:
                if hasattr(self, 'canvas') and self.canvas is not None:
                    if hasattr(self.canvas, 'winfo_exists'):
                        if self.canvas.winfo_exists():
                            self.update_display()
            except (tk.TclError, AttributeError, RuntimeError):
                # Widgets not ready - skip display update
                pass
        except Exception as e:
            # Don't let analytics preference reload break the app
            print(f"⚠ Could not reload analytics preferences: {e}")
            pass
    
    def update_analytics_selections_label(self):
        """Update the analytics selections label in the Analytics tab"""
        if hasattr(self, 'analytics_selections_label') and self.analytics_selections_label is not None:
            try:
                # CRITICAL: Check if widget exists before accessing
                if hasattr(self.analytics_selections_label, 'winfo_exists'):
                    if not self.analytics_selections_label.winfo_exists():
                        # Widget was destroyed
                        return
                
                # Check if analytics_preferences exists
                if not hasattr(self, 'analytics_preferences') or self.analytics_preferences is None:
                    return
                
                selected = [k for k, v in self.analytics_preferences.items() if v]
                if selected:
                    # Format nicely - show first few, then count
                    if len(selected) <= 5:
                        text = f"Selected: {', '.join(selected)}"
                    else:
                        text = f"Selected: {', '.join(selected[:5])}... ({len(selected)} total)"
                    self.analytics_selections_label.config(text=text, foreground="black")
                else:
                    self.analytics_selections_label.config(text="No analytics selected", foreground="gray")
            except (tk.TclError, AttributeError, RuntimeError):
                # Widget was destroyed or doesn't exist - skip
                pass
            except Exception:
                # Any other error - skip
                pass
    
    def toggle_focused_player_panel(self):
        """Toggle focused player panel visibility"""
        if self.show_focused_player_panel.get():
            self.create_focused_player_panel()
        else:
            self.destroy_focused_player_panel()
        # Update canvas width to account for focused panel visibility
        if hasattr(self, '_update_canvas_width'):
            self._update_canvas_width()
        self.update_display()
    
    def create_focused_player_panel(self):
        """Create focused player details panel"""
        if hasattr(self, 'focused_panel') and self.focused_panel:
            return  # Already created
        
        # Create side panel for focused player details
        if not self.comparison_mode:
            # Add panel to the right of controls using grid (display_frame uses grid layout)
            main_frame = self.root.winfo_children()[0]  # Get main frame
            display_frame = main_frame.winfo_children()[1]  # Get display frame
            
            self.focused_panel = ttk.LabelFrame(display_frame, text="Focused Player Analytics", padding="10", width=300)
            # Use grid instead of pack since display_frame uses grid layout
            # Update column 2 minsize when panel is created
            display_frame.columnconfigure(2, weight=0, minsize=300)
            self.focused_panel.grid(row=0, column=2, sticky="nsew", padx=5)
            self.focused_panel.grid_propagate(False)
            
            # Player selection
            select_frame = ttk.Frame(self.focused_panel)
            select_frame.pack(fill=tk.X, pady=5)
            ttk.Label(select_frame, text="Select Player:").pack(side=tk.LEFT)
            self.focused_player_var = tk.StringVar()
            self.focused_player_combo = ttk.Combobox(select_frame, textvariable=self.focused_player_var, 
                                                    state="readonly", width=15)
            self.focused_player_combo.pack(side=tk.LEFT, padx=5)
            self.focused_player_combo.bind("<<ComboboxSelected>>", self.on_focused_player_selected)
            
            # Analytics display area
            self.focused_analytics_text = tk.Text(self.focused_panel, height=20, width=30, wrap=tk.WORD, 
                                                  font=("Courier", 9))
            self.focused_analytics_text.pack(fill=tk.BOTH, expand=True, pady=5)
            
            # Update player list
            self.update_focused_player_list()
    
    def destroy_focused_player_panel(self):
        """Destroy focused player panel"""
        if hasattr(self, 'focused_panel') and self.focused_panel:
            try:
                # Reset column 2 minsize to 0 when panel is destroyed
                main_frame = self.root.winfo_children()[0]  # Get main frame
                display_frame = main_frame.winfo_children()[1]  # Get display frame
                display_frame.columnconfigure(2, weight=0, minsize=0)
                self.focused_panel.destroy()
            except:
                pass
            self.focused_panel = None
    
    def update_focused_player_list(self):
        """Update the list of available players for focused mode"""
        try:
            if not hasattr(self, 'focused_player_combo') or not self.focused_player_combo:
                return
            
            # Check if widget still exists
            try:
                if not self.focused_player_combo.winfo_exists():
                    return
            except (tk.TclError, AttributeError):
                # Widget has been destroyed
                return
            
            # Build player list
            players = set()
            for frame_data in self.player_data.values():
                for player_id, (x, y, team, name) in frame_data.items():
                    players.add((player_id, name or f"#{player_id}"))
            
            player_list = sorted([f"{name} (#{pid})" for pid, name in players])
            
            # Update combobox values
            try:
                self.focused_player_combo['values'] = player_list
            except (tk.TclError, AttributeError, RuntimeError):
                # Widget was destroyed during operation or invalid command
                pass
        except Exception:
            # Catch any other errors
            pass
    
    def on_focused_player_selected(self, event=None):
        """Handle focused player selection"""
        try:
            selection = self.focused_player_var.get()
            if selection:
                # Extract player ID from selection (format: "Name (#ID)")
                try:
                    player_id_str = selection.split("(#")[1].rstrip(")")
                    self.focused_player_id = int(player_id_str)
                    self.update_focused_player_analytics()
                except (ValueError, IndexError):
                    self.focused_player_id = None
        except (tk.TclError, AttributeError):
            # Widget was destroyed, ignore
            pass
    
    def update_focused_player_analytics(self):
        """Update focused player analytics display"""
        if not hasattr(self, 'focused_analytics_text') or not self.focused_analytics_text:
            return
        
        try:
            # Check if widget still exists
            if not self.focused_analytics_text.winfo_exists():
                return
        except (tk.TclError, AttributeError):
            # Widget has been destroyed
            return
        
        try:
            if self.focused_player_id is None or self.current_frame_num not in self.analytics_data:
                self.focused_analytics_text.delete(1.0, tk.END)
                self.focused_analytics_text.insert(1.0, "No analytics data available")
                return
            
            if self.focused_player_id not in self.analytics_data[self.current_frame_num]:
                self.focused_analytics_text.delete(1.0, tk.END)
                self.focused_analytics_text.insert(1.0, f"Player #{self.focused_player_id}\nNo data for this frame")
                return
        except (tk.TclError, AttributeError):
            # Widget was destroyed during operation
            return
        
        # Detect if using imperial units
        use_imperial = 'player_speed_mph' in self.df.columns if self.df is not None else False
        
        analytics = self.analytics_data[self.current_frame_num][self.focused_player_id]
        
        # Get player name
        player_name = f"#{self.focused_player_id}"
        if self.current_frame_num in self.player_data and self.focused_player_id in self.player_data[self.current_frame_num]:
            _, _, _, name = self.player_data[self.current_frame_num][self.focused_player_id]
            if name:
                player_name = name
        
        # Build detailed analytics text
        text = f"Player: {player_name}\n"
        text += f"Frame: {self.current_frame_num}\n"
        text += "=" * 30 + "\n\n"
        
        # Group analytics by category
        speed_metrics = []
        distance_metrics = []
        position_metrics = []
        activity_metrics = []
        zone_metrics = []
        
        preference_to_column = {
            'current_speed': ['player_speed_mph', 'player_speed_mps'],
            'average_speed': ['avg_speed_mph', 'avg_speed_mps'],
            'max_speed': ['max_speed_mph', 'max_speed_mps'],
            'acceleration': ['player_acceleration_fts2', 'player_acceleration_mps2'],
            'distance_traveled': ['distance_traveled_ft', 'distance_traveled_m'],
            'distance_to_ball': ['distance_to_ball_px'],
            'distance_from_center': ['distance_from_center_ft', 'distance_from_center_m'],
            'distance_from_goal': ['distance_from_goal_ft', 'distance_from_goal_m'],
            'nearest_teammate': ['nearest_teammate_dist_ft', 'nearest_teammate_dist_m'],
            'nearest_opponent': ['nearest_opponent_dist_ft', 'nearest_opponent_dist_m'],
            'field_zone': ['field_zone'],
            'field_position': ['field_position_x_pct', 'field_position_y_pct'],
            'movement_angle': ['player_movement_angle'],
            'possession_time': ['possession_time_s'],
            'time_stationary': ['time_stationary_s'],
            'sprint_count': ['sprint_count'],
            'direction_changes': ['direction_changes'],
            'acceleration_events': ['acceleration_events'],
            'distance_walking': ['distance_walking_ft', 'distance_walking_m'],
            'distance_jogging': ['distance_jogging_ft', 'distance_jogging_m'],
            'distance_running': ['distance_running_ft', 'distance_running_m'],
            'distance_sprinting': ['distance_sprinting_ft', 'distance_sprinting_m']
        }
        
        display_labels = {
            'current_speed': 'Current Speed',
            'average_speed': 'Average Speed',
            'max_speed': 'Max Speed',
            'acceleration': 'Acceleration',
            'distance_traveled': 'Distance Traveled',
            'distance_to_ball': 'Distance to Ball',
            'distance_from_center': 'Distance from Center',
            'distance_from_goal': 'Distance from Goal',
            'nearest_teammate': 'Nearest Teammate',
            'nearest_opponent': 'Nearest Opponent',
            'field_zone': 'Field Zone',
            'field_position': 'Field Position',
            'movement_angle': 'Movement Angle',
            'possession_time': 'Possession Time',
            'time_stationary': 'Time Stationary',
            'sprint_count': 'Sprint Count',
            'direction_changes': 'Direction Changes',
            'acceleration_events': 'Acceleration Events',
            'distance_walking': 'Distance Walking',
            'distance_jogging': 'Distance Jogging',
            'distance_running': 'Distance Running',
            'distance_sprinting': 'Distance Sprinting'
        }
        
        # Collect all analytics (show all, not just selected)
        for pref_key in preference_to_column.keys():
            columns = preference_to_column[pref_key]
            value = None
            for col in columns:
                if col in analytics:
                    value = analytics[col]
                    break
            
            if value is not None:
                formatted = self.format_analytics_value(pref_key, value, use_imperial)
                if formatted:
                    label = display_labels.get(pref_key, pref_key)
                    
                    # Categorize
                    if 'speed' in pref_key or 'acceleration' in pref_key:
                        speed_metrics.append(f"{label}: {formatted}")
                    elif 'distance' in pref_key or 'dist' in pref_key:
                        distance_metrics.append(f"{label}: {formatted}")
                    elif 'zone' in pref_key or 'position' in pref_key or 'angle' in pref_key:
                        position_metrics.append(f"{label}: {formatted}")
                    elif 'walking' in pref_key or 'jogging' in pref_key or 'running' in pref_key or 'sprinting' in pref_key:
                        zone_metrics.append(f"{label}: {formatted}")
                    else:
                        activity_metrics.append(f"{label}: {formatted}")
        
        # Build formatted text
        if speed_metrics:
            text += "SPEED METRICS:\n"
            text += "\n".join(speed_metrics) + "\n\n"
        if distance_metrics:
            text += "DISTANCE METRICS:\n"
            text += "\n".join(distance_metrics) + "\n\n"
        if position_metrics:
            text += "POSITION METRICS:\n"
            text += "\n".join(position_metrics) + "\n\n"
        if zone_metrics:
            text += "SPEED ZONES:\n"
            text += "\n".join(zone_metrics) + "\n\n"
        if activity_metrics:
            text += "ACTIVITY METRICS:\n"
            text += "\n".join(activity_metrics) + "\n\n"
        
        if not (speed_metrics or distance_metrics or position_metrics or zone_metrics or activity_metrics):
            text += "No analytics data available"
        
        try:
            self.focused_analytics_text.delete(1.0, tk.END)
            self.focused_analytics_text.insert(1.0, text)
        except (tk.TclError, AttributeError):
            # Widget was destroyed during operation
            pass
    
    def _get_box_color_bgr(self):
        """Get box color in BGR format for OpenCV"""
        from color_picker_utils import rgb_string_to_tuple
        r, g, b = rgb_string_to_tuple(self.box_color_rgb.get(), default=(0, 255, 0))
        return (b, g, r)  # BGR format
    
    def _get_label_color_bgr(self):
        """Get label color in BGR format for OpenCV"""
        from color_picker_utils import rgb_string_to_tuple
        r, g, b = rgb_string_to_tuple(self.label_color_rgb.get(), default=(255, 255, 255))
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
    
    def get_player_color(self, player_id, team, player_name=None):
        """Get color for player based on visualization mode, checking per-player settings first"""
        # CRITICAL: Check for per-player visualization settings first
        if player_name:
            # Check player gallery for custom settings
            try:
                # Use main gallery cache instead of separate cache
                if not hasattr(self, '_player_gallery') or self._player_gallery is None:
                    from player_gallery import PlayerGallery
                    self._player_gallery = PlayerGallery()
                player = self._player_gallery.get_player(player_name) if self._player_gallery else None
                if player and player.visualization_settings:
                    viz = player.visualization_settings
                    if viz.get("use_custom_color") and viz.get("custom_color_rgb"):
                        rgb = viz["custom_color_rgb"]
                        # Convert RGB to BGR for OpenCV
                        return (rgb[2], rgb[1], rgb[0])
            except Exception:
                pass  # Fall through to default behavior
            
            # Check roster manager for custom settings
            try:
                from team_roster_manager import TeamRosterManager
                if not hasattr(self, '_roster_manager_cache'):
                    self._roster_manager_cache = TeamRosterManager()
                player_data = self._roster_manager_cache.roster.get(player_name, {})
                viz = player_data.get("visualization_settings", {})
                if viz.get("use_custom_color") and viz.get("custom_color_rgb"):
                    rgb = viz["custom_color_rgb"]
                    # Convert RGB to BGR for OpenCV
                    return (rgb[2], rgb[1], rgb[0])
            except Exception:
                pass  # Fall through to default behavior
        
        # Fall back to default color mode
        color_mode = self.viz_color_mode.get()
        
        # Try to get team color first (most common case)
        if team:
            # Handle various team name formats
            team_lower = str(team).lower().strip()
            if team_lower in ["team1", "team 1", "gray", "grey", "team1_name"]:
                return (128, 128, 128)  # Gray in BGR
            elif team_lower in ["team2", "team 2", "blue", "team2_name"]:
                return (255, 0, 0)  # Blue in BGR
            # Try direct team name matching
            elif "gray" in team_lower or "grey" in team_lower:
                return (128, 128, 128)  # Gray in BGR
            elif "blue" in team_lower:
                return (255, 0, 0)  # Blue in BGR
        
        # If team color mode is enabled but no team found, try gradient
        if color_mode == "team":
            # Fall back to gradient if team not available
            hue = (int(player_id) * 137) % 180
            color_hsv = np.uint8([[[hue, 255, 255]]])
            color_bgr = cv2.cvtColor(color_hsv, cv2.COLOR_HSV2BGR)[0][0]
            return tuple(map(int, color_bgr))
        
        if color_mode == "gradient":
            hue = (int(player_id) * 137) % 180
            color_hsv = np.uint8([[[hue, 255, 255]]])
            color_bgr = cv2.cvtColor(color_hsv, cv2.COLOR_HSV2BGR)[0][0]
            return tuple(map(int, color_bgr))
        
        # Default: use gray instead of purple (less jarring)
        return (128, 128, 128)  # Gray default (instead of purple)
    
    def toggle_playback(self):
        """Toggle play/pause"""
        if self.cap is None:
            return
        
        print(f"🎮 TOGGLE PLAYBACK: was_playing={self.is_playing}, new_state={not self.is_playing}")

        self.is_playing = not self.is_playing
        
        if self.is_playing:
            self.play_button.config(text="⏸ Pause")
            # Reset timing when starting playback to ensure accurate frame rate
            self.last_frame_time = time.time()
            print(f"▶ STARTING PLAYBACK: frame={self.current_frame_num}, last_frame_time={self.last_frame_time}")
            # Cancel any pending play call to prevent overlaps when restarting
            if hasattr(self, '_play_after_id') and self._play_after_id is not None:
                try:
                    self.root.after_cancel(self._play_after_id)
                except:
                    pass
            self._play_after_id = None
            # Ensure buffer thread is running for smooth playback
            self.start_buffer_thread()
            # Check if buffer thread is actually alive and restart if needed
            if self.buffer_thread and not self.buffer_thread.is_alive():
                print("⚠ Buffer thread died, restarting...")
                self.start_buffer_thread()
            self.play()
        else:
            self.play_button.config(text="▶ Play")
            print("⏸ PAUSING PLAYBACK")
            # Cancel any pending play call when pausing
            if hasattr(self, '_play_after_id') and self._play_after_id is not None:
                try:
                    self.root.after_cancel(self._play_after_id)
                except:
                    pass
            self._play_after_id = None
    
    def play(self):
        """Start playback"""
        print(f"🎬 PLAY() CALLED: frame={self.current_frame_num}, is_playing={self.is_playing}, in_progress={getattr(self, '_play_in_progress', False)}")
        play_start = time.time()  # PROFILE: Track total play() execution time

        # Prevent concurrent play() calls
        if self._play_in_progress:
            print("⚠ BLOCKED: Play already in progress")
            return  # Already playing, ignore this call
        self._play_in_progress = True
        
        try:
            print("▶ ENTERING PLAY METHOD")

            # Check if video is loaded
            if self.cap is None or not self.cap.isOpened():
                messagebox.showwarning("No Video", "Please load a video file first using the 'Load Video' button.")
                return

            """Playback loop - optimized to reduce stuttering"""
            if not self.is_playing or self.cap is None:
                return
            
            current_time = time.time()
            # CRITICAL FIX: Read speed directly from variable each frame to ensure it's always current
            # This prevents stale speed values if update_speed() wasn't called
            # Use safe getter to handle empty fields while typing
            current_speed = self.playback_speed  # Default to current playback speed
            if hasattr(self, 'speed_var'):
                current_speed = self._safe_get_double(self.speed_var, self.playback_speed)
            if current_speed != self.playback_speed:
                self.playback_speed = current_speed
            # Ensure speed is valid
            if self.playback_speed <= 0:
                self.playback_speed = 1.0
                if hasattr(self, 'speed_var'):
                    self.speed_var.set(1.0)
            
            # CRITICAL FIX: Ensure FPS is valid before calculating frame_time
            if self.fps <= 0 or not np.isfinite(self.fps):
                self.fps = 30.0  # Fallback to 30fps
            # CRITICAL FIX: Clamp FPS to reasonable range (5-120fps) to prevent extreme frame times
            if self.fps < 5.0:
                self.fps = 30.0  # Too slow, use default
            elif self.fps > 120.0:
                self.fps = 120.0  # Cap at 120fps for performance
            frame_time = 1.0 / (self.fps * self.playback_speed)
            
            # Debug: Log speed changes occasionally
            if self.current_frame_num % 300 == 0:  # Every 300 frames (~10 seconds at 30fps)
                print(f"✓ Playback: frame {self.current_frame_num}, speed {self.playback_speed:.2f}x, fps {self.fps:.2f}, frame_time {frame_time*1000:.2f}ms")
            
            # Check if overlay settings changed (throttle to reduce CPU usage)
            overlay_changed = False
            # Only check overlay settings every 100ms to reduce CPU usage
            # Use a simple attribute to track last check time
            if not hasattr(self, '_last_overlay_check_time'):
                self._last_overlay_check_time = 0
            if current_time - self._last_overlay_check_time >= 0.1:  # Check every 100ms
                self._last_overlay_check_time = current_time
            # Calculate hash of current overlay settings
            settings_hash = hash((
                self.show_players.get(),
                self.show_player_boxes.get(),
                self.show_player_circles.get(),
                self.show_player_labels.get(),
                self.show_ball.get(),
                self.show_ball_trail.get(),
                self.show_trajectories.get(),
                self.show_field_zones.get(),
                self.show_analytics.get(),
                # Feet marker settings
                self.feet_marker_style.get(),
                self._safe_get_int(self.feet_marker_opacity, 255),
                self.feet_marker_enable_glow.get(),
                self._safe_get_int(self.feet_marker_glow_intensity, 50),
                self.feet_marker_enable_shadow.get(),
                self._safe_get_int(self.feet_marker_shadow_offset, 3),
                self._safe_get_int(self.feet_marker_shadow_opacity, 128),
                self.feet_marker_enable_gradient.get(),
                self.feet_marker_enable_pulse.get(),
                self._safe_get_double(self.feet_marker_pulse_speed, 2.0),
                self.feet_marker_enable_particles.get(),
                self._safe_get_int(self.feet_marker_particle_count, 5),
                self._safe_get_int(self.feet_marker_vertical_offset, 50),
                # Box settings
                self._safe_get_double(self.box_shrink_factor, 0.2),
                self._safe_get_int(self.box_thickness, 2),
                self.use_custom_box_color.get(),
                self.box_color_rgb.get(),
                self._safe_get_int(self.player_viz_alpha, 255),
                # Label settings
                self.use_custom_label_color.get(),
                self.label_color_rgb.get(),
                self._safe_get_double(self.label_font_scale, 0.6),
                self.label_type.get(),
                self.label_custom_text.get(),
                self.label_font_face.get(),
                # Prediction settings
                self._safe_get_int(self.prediction_duration, 30),
                self._safe_get_int(self.prediction_size, 5),
                self._safe_get_int(self.prediction_color_r, 255),
                self._safe_get_int(self.prediction_color_g, 0),
                self._safe_get_int(self.prediction_color_b, 0),
                self._safe_get_int(self.prediction_color_alpha, 128),
                self.prediction_style.get(),
                tuple(self.highlight_ids) if self.highlight_ids else None
            ))
            if settings_hash != self.overlay_settings_hash:
                overlay_changed = True
                self.overlay_settings_hash = settings_hash
                self._viz_settings_changed = True  # Invalidate cached viz settings
            
            # CRITICAL: Check pause state before frame advancement for immediate responsiveness
            if not self.is_playing:
                return
            
            # Check for frame update (respects FPS and playback speed)
            # CRITICAL FIX: Frame-by-frame smooth playback (no chunking)
            frame_advanced = False
            time_since_last_frame = current_time - self.last_frame_time
            
            timing_start = time.time()  # PROFILE: Frame advancement timing

            # Advance ONE frame at a time for smooth, fluid playback
            # This ensures each frame is displayed before moving to the next
            # SPECIAL CASE: Always advance immediately when playback starts/restarts
            should_advance = (time_since_last_frame >= frame_time) or (self.is_playing and time_since_last_frame < 1.0)
            print(f"⏱️ TIMING: time_since_last={time_since_last_frame*1000:.1f}ms, frame_time={frame_time*1000:.1f}ms, should_advance={should_advance} (restarting={self.is_playing and time_since_last_frame < 1.0})")
            if should_advance:
                print("✅ TIME TO ADVANCE FRAME")
                # Only advance one frame at a time for smooth playback
                if self.current_frame_num < self.total_frames - 1:
                    print(f"📈 ADVANCING: frame {self.current_frame_num} → {self.current_frame_num + 1}")
                    frame_load_start = time.time()
                    self.current_frame_num += 1
                    self.frame_var.set(self.current_frame_num)
                    # Load frame with buffering (should be instant if preloaded)
                    self.current_frame = self.load_frame_buffered()
                    frame_load_time = (time.time() - frame_load_start) * 1000

                    # CRITICAL: Frame loading is the bottleneck (58-70ms for 4K video)
                    # With buffering, this should be near-instant for sequential playback
                    if frame_load_time > 10:  # Only warn if still slow
                        print(f"🐌 SLOW FRAME LOAD: {frame_load_time:.1f}ms (target: <10ms with buffering)")

                    # Update timing for this single frame
                    self.last_frame_time += frame_time

                    # If we're significantly behind, reset timing to prevent excessive catch-up
                    # But still maintain smooth frame-by-frame advancement
                    if self.last_frame_time < current_time - frame_time * 2:
                        self.last_frame_time = current_time - frame_time
            
                    frame_advanced = True
                    # When frame advances, we need to re-render
                    overlay_changed = True
            else:
                # Reached end of video - stop playback
                self.is_playing = False
                # Cancel any pending play call
                if hasattr(self, '_play_after_id') and self._play_after_id is not None:
                    try:
                        self.root.after_cancel(self._play_after_id)
                    except:
                        pass
                self._play_after_id = None
                if hasattr(self, 'play_button'):
                    try:
                        if self.play_button.winfo_exists():
                            self.play_button.config(text="▶ Play")
                    except:
                        pass
                return

            timing_frame_logic = (time.time() - timing_start) * 1000

            # Initialize render timing if not set
            timing_render = 0.0
            # If time_since_last_frame < frame_time, we just wait for next call (don't do anything)
            
            # CRITICAL: Check pause state before rendering to avoid unnecessary work
            if not self.is_playing:
                return

            render_start = time.time()  # PROFILE: Rendering timing
            
            # Only render if frame advanced OR overlay settings changed
            # CRITICAL: Render synchronously for frame-by-frame smooth playback
            # This ensures each frame is fully rendered before advancing to the next
            if frame_advanced or overlay_changed:
                if self.current_frame is not None:
                    # Render immediately (synchronously) for smooth frame-by-frame playback
                    # This ensures each frame is fully displayed before moving to the next
                    self.render_overlays()
                    self.update_display(skip_render=True)  # Skip render since we already called render_overlays()

            timing_render = (time.time() - render_start) * 1000
            
            # CRITICAL: Final check before scheduling next update - ensures immediate pause response
            if not self.is_playing:
                return

            # DEBUG: Show timing breakdown every 60 frames
            play_total_time = (time.time() - play_start) * 1000
            if self.current_frame_num % 60 == 0:
                print(f"🎯 PLAY TIMING: frame={self.current_frame_num}, total={play_total_time:.1f}ms, frame_logic={timing_frame_logic:.2f}ms, render={timing_render:.2f}ms, target_fps={1.0/frame_time:.1f}")
            
            # Update buffer status label (throttled to avoid excessive updates)
            if not hasattr(self, '_last_buffer_gui_update') or time.time() - self._last_buffer_gui_update > 0.5:
                self._update_buffer_status_label()
                self._last_buffer_gui_update = time.time()

            # Schedule next update (prevent overlapping calls)
            # CRITICAL FIX: Smooth frame-by-frame timing with overlap prevention
            # Use frame_time for consistent, smooth playback (one frame per frame_time)
            if self.is_playing:
                print(f"🔄 SCHEDULING NEXT: delay={max(1, int(frame_time * 1000))}ms")
                # Cancel any pending play call to prevent overlaps
                if hasattr(self, '_play_after_id') and self._play_after_id is not None:
                    try:
                        self.root.after_cancel(self._play_after_id)
                    except:
                        pass  # Ignore if already executed

                # Schedule next frame update based on frame_time for smooth playback
                # This ensures consistent frame timing without chunking
                refresh_delay = max(1, int(frame_time * 1000))  # Convert to milliseconds
                self._play_after_id = self.root.after(refresh_delay, self.play)
            else:
                print("⏸ NOT SCHEDULING: playback paused")
                refresh_delay = 100  # ~10Hz when paused (sufficient for UI responsiveness, saves CPU)
                self._play_after_id = self.root.after(refresh_delay, self.play)

        finally:
            # Always reset the in-progress flag, even if an exception occurred
            self._play_in_progress = False
    
    def next_frame(self):
        """Go to next frame - optimized for fast sequential playback"""
        if self.current_frame_num < self.total_frames - 1:
            self.current_frame_num += 1
            self.frame_var.set(self.current_frame_num)
            # CRITICAL: Load frame immediately - buffer should have it for sequential playback
            # Sequential reads are fast, and buffer should have pre-loaded frames
            self.current_frame = self.load_frame()
            # Render overlays and update display when manually stepping frames
            if self.current_frame is not None:
                self.render_overlays()
                self.update_display()  # Update focused player analytics
            # Update analytics tab display
            if hasattr(self, 'update_analytics_display'):
                self.update_analytics_display()
    
    def prev_frame(self):
        """Go to previous frame"""
        if self.current_frame_num > 0:
            self.current_frame_num -= 1
            self.frame_var.set(self.current_frame_num)
            self.current_frame = self.load_frame()
            if self.current_frame is not None:
                self.render_overlays()
                self.update_display()  # Update focused player analytics
            # Update analytics tab display
            if hasattr(self, 'update_analytics_display'):
                self.update_analytics_display()
    
    def go_to_first(self):
        """Go to first frame"""
        self.current_frame_num = 0
        self.frame_var.set(0)
        self.current_frame = self.load_frame()
        if self.current_frame is not None:
            self.render_overlays()
            self.update_display()  # Update focused player analytics
        # Update analytics tab display
        if hasattr(self, 'update_analytics_display'):
            self.update_analytics_display()
    
    def go_to_last(self):
        """Go to last frame"""
        self.current_frame_num = max(0, self.total_frames - 1)
        self.frame_var.set(self.current_frame_num)
        self.current_frame = self.load_frame()
        if self.current_frame is not None:
            self.render_overlays()
            self.update_display()  # Update focused player analytics
        # Update analytics tab display
        if hasattr(self, 'update_analytics_display'):
            self.update_analytics_display()
    
    def goto_frame(self):
        """Jump to a specific frame number entered by user"""
        try:
            frame_text = self.goto_frame_var.get().strip()
            if not frame_text:
                return
            
            frame_num = int(frame_text)
            
            # Validate frame number
            if frame_num < 0:
                frame_num = 0
            elif frame_num >= self.total_frames:
                frame_num = max(0, self.total_frames - 1)
            
            # Jump to frame
            self.current_frame_num = frame_num
            self.frame_var.set(frame_num)
            # Reset sequential read tracking on manual seek
            self.last_sequential_frame = -1
            self.current_frame = self.load_frame()
            
            if self.current_frame is not None:
                self.render_overlays()
                self.update_display()  # Update focused player analytics
            
            # Update analytics tab display
            if hasattr(self, 'update_analytics_display'):
                self.update_analytics_display()
            
            # Clear the entry field after successful jump
            self.goto_frame_var.set("")
            
        except ValueError:
            # Invalid input - show error and clear field
            self.goto_frame_var.set("")
            if hasattr(self, 'root'):
                try:
                    from tkinter import messagebox
                    messagebox.showerror("Invalid Frame Number", 
                                        f"Please enter a valid frame number (0 to {self.total_frames - 1})")
                except:
                    pass
        except Exception as e:
            print(f"[ERROR] Failed to goto frame: {e}")
            self.goto_frame_var.set("")
    
    def mark_event(self, event_type: str):
        """Mark an event at the current frame"""
        if not self.event_tracker:
            return
        
        # Get player info from current frame
        player_id = None
        player_name = None
        team = None
        x_pos = None
        y_pos = None
        
        # Try to get player info from CSV data
        if self.df is not None and not self.df.empty:
            frame_data = self.df[self.df['frame_num'] == self.current_frame_num]
            if not frame_data.empty:
                # Get first player in frame (or focused player if available)
                if self.focused_player_id is not None:
                    player_frame = frame_data[frame_data['track_id'] == self.focused_player_id]
                    if not player_frame.empty:
                        player_id = int(self.focused_player_id)
                        player_name = self.player_names.get(player_id, f"Player {player_id}")
                        x_pos = float(player_frame['x'].iloc[0]) if 'x' in player_frame.columns else None
                        y_pos = float(player_frame['y'].iloc[0]) if 'y' in player_frame.columns else None
                else:
                    # Get first player
                    first_row = frame_data.iloc[0]
                    player_id = int(first_row['track_id']) if 'track_id' in first_row else None
                    if player_id:
                        player_name = self.player_names.get(player_id, f"Player {player_id}")
                        x_pos = float(first_row['x']) if 'x' in first_row else None
                        y_pos = float(first_row['y']) if 'y' in first_row else None
                        
                        # Try to get team from team_colors
                        if self.team_colors and player_id in self.team_colors:
                            team = self.team_colors[player_id].get('team_name', None)
        
        # Normalize positions (0-1 range)
        if x_pos is not None and self.width > 0:
            x_pos = x_pos / self.width
        if y_pos is not None and self.height > 0:
            y_pos = y_pos / self.height
        
        # Add event to both systems
        if self.event_tracker:
            event = self.event_tracker.add_event(
            event_type=event_type,
            frame_num=self.current_frame_num,
            player_id=player_id,
            player_name=player_name,
            team=team,
            x_position=x_pos,
            y_position=y_pos
        )
        
        # Show confirmation
        messagebox.showinfo("Event Marked", 
                          f"Event '{event_type}' marked at frame {self.current_frame_num}\n"
                          f"Time: {event.timestamp:.2f}s")
        
        # Refresh timeline if open
        if self.event_timeline_viewer and self.event_timeline_viewer.window.winfo_exists():
            self.event_timeline_viewer._refresh()
    
    def mark_event_at_current_frame(self):
        """Mark an event at the current frame using the event marker system"""
        if not self.video_path or self.current_frame_num < 0:
            return
        
        event_type_str = self.current_event_type.get()
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            messagebox.showerror("Invalid Event Type", f"Unknown event type: {event_type_str}")
            return
        
        # Get player info from current frame
        player_id = None
        player_name = None
        team = None
        position = None
        
        if self.df is not None and not self.df.empty:
            frame_data = self.df[self.df['frame_num'] == self.current_frame_num]
            if not frame_data.empty:
                if self.focused_player_id is not None:
                    player_frame = frame_data[frame_data['track_id'] == self.focused_player_id]
                    if not player_frame.empty:
                        player_id = int(self.focused_player_id)
                        player_name = self.player_names.get(player_id, f"Player {player_id}")
                        x_pos = float(player_frame['x'].iloc[0]) if 'x' in player_frame.columns else None
                        y_pos = float(player_frame['y'].iloc[0]) if 'y' in player_frame.columns else None
                        if x_pos is not None and y_pos is not None:
                            # Normalize positions
                            if self.width > 0 and self.height > 0:
                                position = (x_pos / self.width, y_pos / self.height)
                else:
                    first_row = frame_data.iloc[0]
                    player_id = int(first_row['track_id']) if 'track_id' in first_row else None
                    if player_id:
                        player_name = self.player_names.get(player_id, f"Player {player_id}")
                        x_pos = float(first_row['x']) if 'x' in first_row else None
                        y_pos = float(first_row['y']) if 'y' in first_row else None
                        if x_pos is not None and y_pos is not None and self.width > 0 and self.height > 0:
                            position = (x_pos / self.width, y_pos / self.height)
                        if self.team_colors and player_id in self.team_colors:
                            team = self.team_colors[player_id].get('team_name', None)
        
        # Create marker
        timestamp = self.current_frame_num / self.fps if self.fps > 0 else self.current_frame_num / 30.0
        marker = EventMarker(
            frame_num=self.current_frame_num,
            event_type=event_type,
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            team=team,
            position=position,
            confidence=1.0
        )
        
        self.event_marker_system.add_marker(marker)
        self.update_marker_statistics()
        self.update_timeline_display()
        
        messagebox.showinfo("Event Marked", 
                          f"Marked {event_type_str} at frame {self.current_frame_num}\n"
                          f"Player: {player_name or 'Unknown'}")
    
    def remove_event_at_current_frame(self):
        """Remove event marker(s) at the current frame"""
        markers = self.event_marker_system.get_markers_at_frame(self.current_frame_num)
        if not markers:
            messagebox.showinfo("No Markers", f"No event markers at frame {self.current_frame_num}")
            return
        
        if len(markers) == 1:
            # Single marker - remove it
            event_type = markers[0].event_type
            self.event_marker_system.remove_marker(self.current_frame_num, event_type)
            messagebox.showinfo("Marker Removed", f"Removed {event_type.value} marker at frame {self.current_frame_num}")
        else:
            # Multiple markers - ask which one
            marker_types = [m.event_type.value for m in markers]
            from tkinter import simpledialog
            choice = simpledialog.askstring(
                "Remove Marker",
                f"Multiple markers at frame {self.current_frame_num}:\n" +
                "\n".join(f"{i+1}. {t}" for i, t in enumerate(marker_types)) +
                "\n\nEnter number to remove (or 'all' for all):"
            )
            if choice:
                if choice.lower() == 'all':
                    self.event_marker_system.remove_marker(self.current_frame_num)
                    messagebox.showinfo("Markers Removed", f"Removed all markers at frame {self.current_frame_num}")
                else:
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(markers):
                            event_type = markers[idx].event_type
                            self.event_marker_system.remove_marker(self.current_frame_num, event_type)
                            messagebox.showinfo("Marker Removed", f"Removed {event_type.value} marker")
                    except ValueError:
                        pass
        
        self.update_marker_statistics()
        self.update_timeline_display()
    
    def save_event_markers(self):
        """Save event markers to file"""
        if not self.event_marker_system.markers:
            messagebox.showinfo("No Markers", "No event markers to save")
            return
        
        if self.video_path:
            default_path = self.event_marker_system.save_to_file()
            messagebox.showinfo("Markers Saved", f"Saved {len(self.event_marker_system.markers)} markers to:\n{default_path}")
        else:
            filename = filedialog.asksaveasfilename(
                title="Save Event Markers",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if filename:
                self.event_marker_system.save_to_file(filename)
                messagebox.showinfo("Markers Saved", f"Saved {len(self.event_marker_system.markers)} markers")
    
    def load_event_markers(self):
        """Load event markers from file"""
        if self.video_path:
            # Try auto-detecting marker file
            video_dir = os.path.dirname(os.path.abspath(self.video_path))
            video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
            default_path = os.path.join(video_dir, f"{video_basename}_event_markers.json")
            
            if os.path.exists(default_path):
                if self.event_marker_system.load_from_file(default_path):
                    messagebox.showinfo("Markers Loaded", 
                                      f"Loaded {len(self.event_marker_system.markers)} markers from:\n{default_path}")
                    self.update_marker_statistics()
                    self.update_timeline_display()
                    return
        
        filename = filedialog.askopenfilename(
            title="Load Event Markers",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            if self.event_marker_system.load_from_file(filename):
                messagebox.showinfo("Markers Loaded", f"Loaded {len(self.event_marker_system.markers)} markers")
                self.update_marker_statistics()
                self.update_timeline_display()
            else:
                messagebox.showerror("Load Failed", "Could not load event markers from file")
    
    def clear_all_event_markers(self):
        """Clear all event markers"""
        if not self.event_marker_system.markers:
            messagebox.showinfo("No Markers", "No event markers to clear")
            return
        
        if messagebox.askyesno("Clear All Markers", 
                             f"Are you sure you want to clear all {len(self.event_marker_system.markers)} markers?"):
            self.event_marker_system.clear_markers()
            self.update_marker_statistics()
            self.update_timeline_display()
            messagebox.showinfo("Markers Cleared", "All event markers have been cleared")
    
    def update_marker_statistics(self):
        """Update the marker statistics display"""
        stats = self.event_marker_system.get_statistics()
        total = stats['total_markers']
        by_type = stats.get('by_type', {})
        
        if total == 0:
            self.marker_stats_label.config(text="Markers: 0")
        else:
            type_str = ", ".join([f"{k}: {v}" for k, v in by_type.items()])
            self.marker_stats_label.config(text=f"Markers: {total} ({type_str})")
    
    def update_timeline_display(self):
        """Update the timeline slider to show event markers"""
        if not self.event_marker_visible.get():
            return
        
        # This will be called when markers are added/removed
        # The timeline display update will happen in the slider rendering
        # For now, just trigger a redraw
        if hasattr(self, 'frame_slider'):
            # Force slider update
            self.on_slider_change(self.frame_var.get())
    
    def open_event_timeline(self):
        """Open event timeline viewer"""
        if not self.event_tracker:
            messagebox.showwarning("No Event Tracker", "Event tracking is not available for this video")
            return
        
        # Close existing timeline if open
        if self.event_timeline_viewer and self.event_timeline_viewer.window.winfo_exists():
            self.event_timeline_viewer.window.focus()
            return
        
        # Create new timeline viewer
        self.event_timeline_viewer = EventTimelineViewer(
            self.root, 
            self.event_tracker,
            self.video_path,
            self.fps
        )
        
        # Set jump callback
        def jump_to_frame(frame_num):
            self.current_frame_num = frame_num
            self.frame_var.set(frame_num)
            self.current_frame = self.load_frame()
            if self.current_frame is not None:
                self.render_overlays()
                self.update_display()
        
        self.event_timeline_viewer.set_jump_callback(jump_to_frame)
    
    def save_events(self):
        """Save events to file"""
        if not self.event_tracker:
            messagebox.showwarning("No Event Tracker", "Event tracking is not available for this video")
            return
        
        if not self.event_tracker.events:
            messagebox.showinfo("No Events", "No events to save")
            return
        
        try:
            output_dir = os.path.dirname(self.video_path) if self.video_path else "."
            json_path, csv_path = self.event_tracker.save_events(output_dir)
            messagebox.showinfo("Events Saved", 
                              f"Events saved to:\n{os.path.basename(json_path)}\n{os.path.basename(csv_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save events: {e}")
    
    def on_slider_change(self, value):
        """Handle slider change"""
        frame_num = int(float(value))
        if frame_num != self.current_frame_num:
            self.current_frame_num = frame_num
            # Reset sequential read tracking on manual seek
            self.last_sequential_frame = -1
            self.current_frame = self.load_frame()
            if self.current_frame is not None:
                self.render_overlays()
                self.update_display()  # Update focused player analytics
            # Update analytics tab display
            if hasattr(self, 'update_analytics_display'):
                self.update_analytics_display()
    
    def update_speed(self):
        """Update playback speed - safely handles empty/invalid input"""
        old_speed = self.playback_speed
        # Use safe getter to handle empty fields while typing
        new_speed = self._safe_get_double(self.speed_var, self.playback_speed)
        
        # CRITICAL FIX: Ensure speed is valid (prevent division by zero or negative values)
        if new_speed <= 0 or not np.isfinite(new_speed):
            new_speed = 1.0
            self.speed_var.set(1.0)
        
        self.playback_speed = float(new_speed)
        
        # Debug: Log speed changes (only log if actually changed to avoid spam)
        if abs(old_speed - self.playback_speed) > 0.01:
            print(f"✓ Playback speed updated: {old_speed:.2f}x → {self.playback_speed:.2f}x")
            # Force immediate frame update to reflect speed change
            if self.is_playing:
                self.last_frame_time = 0  # Reset timing to allow immediate frame advance
    
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
    
    def update_display(self, skip_render=False):
        """Update display when overlay options change - settings take effect immediately"""
        # Invalidate settings hash to force re-render with new settings
        self.overlay_settings_hash = None
        self._viz_settings_changed = True  # Invalidate cached viz settings
        
        # Update ball analytics display
        if hasattr(self, 'ball_trajectory') and self.ball_trajectory:
            self.update_ball_analytics_display()
        
        if self.current_frame is None:
            self.current_frame = self.load_frame()
        if self.current_frame is not None and not skip_render:
            self.render_overlays()
    
    def apply_zoom_pan_single(self, frame):
        """Apply zoom and pan to single frame mode"""
        if self.zoom_level == 1.0 and self.pan_x == 0 and self.pan_y == 0:
            return frame
        
        h, w = frame.shape[:2]
        
        # Calculate zoomed dimensions
        new_w = int(w * self.zoom_level)
        new_h = int(h * self.zoom_level)
        
        # Resize frame
        zoomed = cv2.resize(frame, (new_w, new_h))
        
        # Get canvas container size (not canvas itself) to prevent expansion beyond allocated space
        if hasattr(self, 'canvas_container'):
            canvas_container = self.canvas_container
        else:
            canvas_container = self.canvas.master
        canvas_container.update_idletasks()
        container_width = canvas_container.winfo_width()
        container_height = canvas_container.winfo_height()
        
        # If container hasn't been rendered yet, use canvas size as fallback
        if container_width <= 1 or container_height <= 1:
            self.canvas.update_idletasks()
            container_width = self.canvas.winfo_width()
            container_height = self.canvas.winfo_height()
        
        if container_width <= 1 or container_height <= 1:
            container_width = w
            container_height = h
        
        # Use container dimensions
        canvas_width = container_width
        canvas_height = container_height
        
        # Calculate crop region (centered, then panned)
        crop_x = int((new_w - canvas_width) / 2 - self.pan_x)
        crop_y = int((new_h - canvas_height) / 2 - self.pan_y)
        
        # Ensure crop region is within bounds
        crop_x = max(0, min(crop_x, new_w - canvas_width))
        crop_y = max(0, min(crop_y, new_h - canvas_height))
        
        # Crop to canvas size
        if crop_x + canvas_width <= new_w and crop_y + canvas_height <= new_h:
            cropped = zoomed[crop_y:crop_y+canvas_height, crop_x:crop_x+canvas_width]
        else:
            # Fallback if crop goes out of bounds
            cropped = cv2.resize(frame, (canvas_width, canvas_height))
        
        return cropped
    
    def on_canvas_click(self, event):
        """Handle left-click on single canvas (for panning when zoomed or measurement)"""
        if self.measurement_mode.get():
            # Measurement mode: start measurement
            self.measure_start = (event.x, event.y)
            self.measure_end = None
            # Clear previous measurement line/box
            if self.measure_line_id:
                self.canvas.delete(self.measure_line_id)
                self.measure_line_id = None
        elif self.zoom_level > 1.0:
            # Already zoomed - start panning with left-click
            self.is_panning = True
            self.pan_start_x = event.x
            self.pan_start_y = event.y
    
    def on_canvas_drag(self, event):
        """Handle left-drag on single canvas (for panning or measurement)"""
        if self.measurement_mode.get() and self.measure_start:
            # Measurement mode: update measurement line/box
            self.measure_end = (event.x, event.y)
            
            # Clear previous line/box
            if self.measure_line_id:
                self.canvas.delete(self.measure_line_id)
            
            # Calculate pixel dimensions in video coordinates
            video_x1, video_y1 = self.canvas_to_video_coords(self.measure_start[0], self.measure_start[1])
            video_x2, video_y2 = self.canvas_to_video_coords(self.measure_end[0], self.measure_end[1])
            
            width = abs(video_x2 - video_x1)
            height = abs(video_y2 - video_y1)
            area = width * height
            distance = ((video_x2 - video_x1)**2 + (video_y2 - video_y1)**2)**0.5
            
            # Draw measurement based on type
            if self.measurement_type.get() == "box":
                # Draw rectangle (box)
                x1, y1 = min(self.measure_start[0], self.measure_end[0]), min(self.measure_start[1], self.measure_end[1])
                x2, y2 = max(self.measure_start[0], self.measure_end[0]), max(self.measure_start[1], self.measure_end[1])
                self.measure_line_id = self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline="yellow", width=2, fill="", tags="measurement"
                )
                # Update measurement label for box mode
                self.measurement_result_label.config(
                    text=f"Width: {width:.0f}px | Height: {height:.0f}px | Area: {area:.0f}px²"
                )
            else:
                # Draw line
                self.measure_line_id = self.canvas.create_line(
                    self.measure_start[0], self.measure_start[1],
                    self.measure_end[0], self.measure_end[1],
                    fill="yellow", width=2, tags="measurement"
                )
                # Update measurement label for line mode
                self.measurement_result_label.config(
                    text=f"Width: {width:.0f}px | Height: {height:.0f}px | Distance: {distance:.0f}px"
            )
        elif self.is_panning and self.zoom_level > 1.0:
            # Left-click panning (only when zoomed)
            self._handle_pan_drag(event)
    
    def on_canvas_release(self, event):
        """Handle left mouse release on single canvas"""
        if self.measurement_mode.get():
            # Finalize measurement
            if self.measure_start and self.measure_end:
                video_x1, video_y1 = self.canvas_to_video_coords(self.measure_start[0], self.measure_start[1])
                video_x2, video_y2 = self.canvas_to_video_coords(self.measure_end[0], self.measure_end[1])
                
                width = abs(video_x2 - video_x1)
                height = abs(video_y2 - video_y1)
                area = width * height
                distance = ((video_x2 - video_x1)**2 + (video_y2 - video_y1)**2)**0.5
                
                # Update measurement label with final values based on mode
                if self.measurement_type.get() == "box":
                    self.measurement_result_label.config(
                        text=f"Width: {width:.0f}px | Height: {height:.0f}px | Area: {area:.0f}px²"
                    )
                else:
                    self.measurement_result_label.config(
                        text=f"Width: {width:.0f}px | Height: {height:.0f}px | Distance: {distance:.0f}px"
                    )
        self.is_panning = False
    
    def on_canvas_right_click(self, event):
        """Handle right-click on canvas (always available for panning)"""
        # Right-click always starts panning (even when not zoomed, allows panning at 1.0x zoom)
        self.is_right_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
    
    def on_canvas_right_drag(self, event):
        """Handle right-drag on canvas (panning)"""
        if self.is_right_panning:
            self._handle_pan_drag(event)
    
    def on_canvas_right_release(self, event):
        """Handle right mouse release on canvas"""
        self.is_right_panning = False
    
    def _handle_pan_drag(self, event):
        """Common panning logic for both left and right mouse drag"""
        # Calculate drag distance
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        
        # Update pan offset (inverse direction for natural panning)
        self.pan_x -= dx
        self.pan_y -= dy
        
        # Update start position for next drag
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        
        self.render_overlays()
    
    def canvas_to_video_coords(self, canvas_x, canvas_y):
        """Convert canvas coordinates to video pixel coordinates (accounting for zoom/pan)"""
        # Get video dimensions
        if not hasattr(self, 'width') or not hasattr(self, 'height') or self.width <= 0 or self.height <= 0:
            return int(canvas_x), int(canvas_y)
        
        original_frame_width = self.width
        original_frame_height = self.height
        
        # Get canvas size
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return int(canvas_x), int(canvas_y)
        
        # Step 1: Calculate how the frame was resized to fit canvas (before zoom/pan)
        # This matches the logic in update_display()
        aspect_ratio = original_frame_width / original_frame_height
        container_aspect = canvas_width / canvas_height
        
        if aspect_ratio > container_aspect:
            # Frame is wider - fit to width
            display_width = canvas_width
            display_height = int(canvas_width / aspect_ratio)
        else:
            # Frame is taller - fit to height
            display_height = canvas_height
            display_width = int(canvas_height * aspect_ratio)
        
        # Step 2: Calculate scale factor from original frame to displayed frame
        scale_x = display_width / original_frame_width
        scale_y = display_height / original_frame_height
        
        # Step 3: Account for zoom (the displayed frame is then zoomed)
        zoomed_display_width = display_width * self.zoom_level
        zoomed_display_height = display_height * self.zoom_level
        
        # Step 4: The zoomed frame is centered, then panned, then cropped to canvas size
        # The image is placed at canvas center (see create_image call)
        canvas_center_x = canvas_width / 2
        canvas_center_y = canvas_height / 2
        
        # Step 5: Calculate where the click is relative to the zoomed frame center
        # The zoomed frame is centered at canvas center, then panned
        relative_x = canvas_x - canvas_center_x
        relative_y = canvas_y - canvas_center_y
        
        # Step 6: Account for pan (pan moves the view, so we add it back)
        # Pan is in the opposite direction of movement
        zoomed_x = relative_x + self.pan_x
        zoomed_y = relative_y + self.pan_y
        
        # Step 7: Convert from zoomed display coordinates to original display coordinates
        display_x = zoomed_x / self.zoom_level
        display_y = zoomed_y / self.zoom_level
        
        # Step 8: Convert from display coordinates to original video coordinates
        video_x = display_x / scale_x
        video_y = display_y / scale_y
        
        # Step 9: Clamp to video bounds
        video_x = max(0, min(original_frame_width - 1, video_x))
        video_y = max(0, min(original_frame_height - 1, video_y))
        
        return int(video_x), int(video_y)
    
    def toggle_measurement_mode(self):
        """Toggle pixel measurement mode"""
        if self.measurement_mode.get():
            self.canvas.config(cursor="crosshair")
            self.update_measurement_info()
        else:
            self.canvas.config(cursor="")
            self.measurement_info_label.config(text="Click & drag on video to measure", foreground="gray")
            self.measurement_result_label.config(text="")
            # Clear measurement line/box
            if self.measure_line_id:
                self.canvas.delete(self.measure_line_id)
                self.measure_line_id = None
            self.measure_start = None
            self.measure_end = None
    
    def update_measurement_info(self):
        """Update measurement info label based on current mode"""
        if self.measurement_mode.get():
            if self.measurement_type.get() == "box":
                self.measurement_info_label.config(
                    text="Click & drag to draw a box and measure area", 
                    foreground="blue"
                )
            else:
                self.measurement_info_label.config(
                    text="Click & drag to draw a line and measure distance", 
                    foreground="blue"
                )
    
    def on_canvas_wheel(self, event):
        """Handle mouse wheel on single canvas (for zoom)"""
        if event.delta > 0 or event.num == 4:
            # Zoom in
            self.zoom_level = min(5.0, self.zoom_level * 1.2)
        else:
            # Zoom out
            self.zoom_level = max(0.5, self.zoom_level / 1.2)
        
        # Reset pan when zooming to 1.0
        if self.zoom_level == 1.0:
            self.pan_x = 0
            self.pan_y = 0
        
        self.render_overlays()
        
        # Update focused player analytics if panel is visible
        if self.show_focused_player_panel.get() and self.focused_player_id is not None:
            self.update_focused_player_analytics()
    
    def export_video(self):
        """Export video with overlays rendered into the video file"""
        if not self.video_path or not os.path.exists(self.video_path):
            messagebox.showerror("Error", "Please load a video file first.")
            return
        
        # Store video path in local variable after validation to help type checker
        video_path: str = self.video_path
        
        if not self.csv_path or not os.path.exists(self.csv_path):
            messagebox.showwarning("Warning", "No CSV file loaded. Video will be exported without overlays.")
            use_overlays = False
        else:
            use_overlays = True
        
        # Ask for output file
        output_path = filedialog.asksaveasfilename(
            title="Save Video With Overlays",
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        
        if not output_path:
            return
        
        # Confirm export
        result = messagebox.askyesno(
            "Export Video",
            f"Export video with current overlay settings?\n\n"
            f"Video: {os.path.basename(video_path)}\n"
            f"Output: {os.path.basename(output_path)}\n"
            f"Frames: {self.total_frames}\n\n"
            f"This may take a while. Continue?",
            icon='question'
        )
        
        if not result:
            return
        
        # Create progress window
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Exporting Video")
        progress_window.geometry("400x150")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        progress_label = ttk.Label(progress_window, text="Preparing export...", font=("Arial", 10))
        progress_label.pack(pady=10)
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100, length=350)
        progress_bar.pack(pady=10)
        
        status_label = ttk.Label(progress_window, text="", font=("Arial", 9))
        status_label.pack(pady=5)
        
        progress_window.update()
        
        # Export in background thread
        def export_thread():
            try:
                # Open input video
                cap = cv2.VideoCapture(video_path)
                if cap is None or not cap.isOpened():
                    messagebox.showerror("Error", f"Could not open input video:\n{video_path}")
                    progress_window.after(0, progress_window.destroy)
                    return

                # Get video properties
                # CRITICAL FIX: Use the same FPS that the viewer detected (self.fps) to ensure consistency
                # The video file might report incorrect FPS, so use what we've already validated
                detected_fps = cap.get(cv2.CAP_PROP_FPS)
                # Use viewer's validated FPS if available, otherwise use detected FPS
                if hasattr(self, 'fps') and self.fps > 0 and np.isfinite(self.fps):
                    fps = self.fps  # Use viewer's validated FPS
                    print(f"✓ Export: Using viewer's validated FPS: {fps:.2f} (detected: {detected_fps:.2f})")
                else:
                    # Fallback to detected FPS with validation
                    if detected_fps is None or detected_fps <= 0 or not np.isfinite(detected_fps):
                        fps = 30.0  # Default fallback
                        print(f"⚠ Export: FPS detection failed, using default 30fps")
                    else:
                        fps = float(detected_fps)
                        print(f"✓ Export: Using detected FPS: {fps:.2f}")
                
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
                # Create video writer
                fourcc = getattr(cv2, 'VideoWriter_fourcc')(*'mp4v')
                out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                
                if not out.isOpened():
                    raise Exception("Could not create output video file")
                
                frame_num = 0
                start_time = time.time()
                
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    # Render overlays if enabled
                    if use_overlays:
                        frame = self.render_overlays_on_frame(frame.copy(), frame_num, force_mode="metadata")
                    
                    # Write frame
                    out.write(frame)
                    
                    frame_num += 1
                    
                    # Update progress
                    progress = (frame_num / total_frames) * 100
                    progress_var.set(progress)
                    
                    elapsed = time.time() - start_time
                    fps_current = frame_num / elapsed if elapsed > 0 else 0
                    eta = (total_frames - frame_num) / fps_current if fps_current > 0 else 0
                    
                    status_text = f"Frame {frame_num}/{total_frames} ({progress:.1f}%) | Speed: {fps_current:.1f} fps | ETA: {eta:.0f}s"
                    status_label.config(text=status_text)
                    
                    progress_window.update()
                
                # Cleanup
                cap.release()
                out.release()
                
                # Close progress window
                progress_window.after(0, progress_window.destroy)
                
                # Show success message
                self.root.after(0, lambda: messagebox.showinfo(
                    "Export Complete",
                    f"Video exported successfully!\n\n"
                    f"Output: {output_path}\n"
                    f"Frames: {frame_num}\n"
                    f"Time: {time.time() - start_time:.1f}s"
                ))
                
            except Exception as e:
                progress_window.after(0, progress_window.destroy)
                self.root.after(0, lambda: messagebox.showerror("Export Error", f"Could not export video:\n\n{str(e)}"))
        
        # Start export thread
        thread = threading.Thread(target=export_thread, daemon=True)
        thread.start()
    
    def start_buffer_thread(self):
        """Start background frame buffering for smooth playback"""
        if self.buffer_thread and self.buffer_thread.is_alive():
            print("🔄 Buffer thread already running")
            return  # Already running

        print(f"🚀 STARTING frame buffer thread (preload {self.buffer_size} frames with separate VideoCapture)")
        self.buffer_active = True
        self.buffer_thread = threading.Thread(target=self._buffer_worker, daemon=True)
        self.buffer_thread.start()
        print(f"✅ Buffer thread started successfully")

    def stop_buffer_thread(self):
        """Stop the frame buffering thread"""
        self.buffer_active = False
        if self.buffer_thread:
            self.buffer_thread.join(timeout=1.0)

    def _buffer_worker(self):
        """Background worker to preload frames"""
        print(f"🔄 Buffer worker started - current_frame={self.current_frame_num}")

        # Create separate VideoCapture for buffer thread to avoid conflicts
        if self.buffer_cap is None and self.video_path:
            try:
                # Try MSMF backend first (best for Windows)
                self.buffer_cap = cv2.VideoCapture(self.video_path, cv2.CAP_MSMF)
                if not self.buffer_cap.isOpened():
                    self.buffer_cap.release()
                    # Fallback to DirectShow
                    self.buffer_cap = cv2.VideoCapture(self.video_path, cv2.CAP_DSHOW)
                    if not self.buffer_cap.isOpened():
                        self.buffer_cap.release()
                        # Last resort: default backend
                        self.buffer_cap = cv2.VideoCapture(self.video_path)
            except Exception as e:
                print(f"⚠ Failed to create buffer VideoCapture: {e}")
                return

        if self.buffer_cap is None or not self.buffer_cap.isOpened():
            print("⚠ Buffer VideoCapture failed to open")
            return

        while self.buffer_active:
            try:
                # Debug: Show buffer worker is active (less frequent)
                if time.time() - self._last_buffer_debug > 3.0:  # Every 3 seconds
                    print(f"🔄 BUFFER WORKER: active, current_frame={self.current_frame_num}, buffer_size={len(self.frame_buffer)}")
                    self._last_buffer_debug = time.time()

                # Determine which frames to preload (close ahead + well ahead)
                # Buffer both near frames (for immediate access) and far frames (for sustained playback)
                near_start = self.current_frame_num + 1  # Start from next frame
                near_end = min(self.current_frame_num + 50, self.total_frames - 1)  # Next 50 frames (increased for larger buffer)
                far_start = self.current_frame_num + 60  # Start further ahead (after near range)
                far_end = min(self.current_frame_num + self.buffer_size + 20, self.total_frames - 1)

                # Combine near and far frame ranges
                target_frames = set(range(near_start, near_end + 1)) | set(range(far_start, far_end + 1))

                # Debug: Show target ranges occasionally (less frequent)
                if time.time() - self._last_buffer_debug > 3.0:  # Every 3 seconds
                    near_range = set(range(near_start, near_end + 1))
                    far_range = set(range(far_start, far_end + 1))
                    print(f"🎯 TARGET FRAMES: near {near_start}-{near_end} ({len(near_range)}), far {far_start}-{far_end} ({len(far_range)}), total {len(target_frames)}")
                    self._last_buffer_debug = time.time()

                # Debug: Show buffering progress (reduced spam - only when buffer changes significantly)
                current_buffer_size = len(self.frame_buffer)
                if not hasattr(self, '_last_buffer_size') or abs(current_buffer_size - self._last_buffer_size) >= 20:  # Only when buffer size changes by 20+ frames
                    print(f"🔄 Buffer status: {current_buffer_size} frames buffered, range {min(self.frame_buffer.keys()) if self.frame_buffer else 'none'} - {max(self.frame_buffer.keys()) if self.frame_buffer else 'none'}, current_frame={self.current_frame_num}")
                    self._last_buffer_size = current_buffer_size
                    self._last_buffer_debug = time.time()
                
                # Update GUI buffer status label (throttled to avoid excessive updates)
                if not hasattr(self, '_last_buffer_gui_update') or time.time() - self._last_buffer_gui_update > 0.5:  # Update every 0.5 seconds
                    self.root.after(0, self._update_buffer_status_label)  # Schedule on main thread
                    self._last_buffer_gui_update = time.time()

                # Preload frames that aren't already in buffer (both near and far ahead)
                # CRITICAL: Prioritize immediate next frames (current+1, current+2, etc.) for instant playback
                immediate_frames = [f for f in range(near_start, min(near_start + 10, near_end + 1)) if f not in self.frame_buffer]
                other_frames = [f for f in target_frames if f not in self.frame_buffer and f not in immediate_frames]
                
                # Process immediate frames first, then others
                frames_to_load = immediate_frames + other_frames

                if frames_to_load:
                    # Buffer aggressively when needed - load more frames when behind
                    # Prioritize immediate frames: load all immediate frames first, then batch others
                    if immediate_frames:
                        # Load all immediate frames first (these are critical for smooth playback)
                        batch_size = len(immediate_frames)
                        if len(immediate_frames) > 0:
                            print(f"⚡ PRIORITY BUFFERING: {len(immediate_frames)} immediate frames (next {near_start}-{near_start + len(immediate_frames) - 1})")
                    else:
                        # No immediate frames needed, batch load others
                        batch_size = 20 if len(frames_to_load) > 15 else 10
                        if len(frames_to_load) > 5:
                            print(f"🔄 BUFFERING: {len(frames_to_load)} frames needed, loading {min(batch_size, len(frames_to_load))} now (target: near {near_start}-{near_end}, far {far_start}-{far_end})")
                    
                    for frame_num in frames_to_load[:batch_size]:
                        if not self.buffer_active:  # Check if we should stop
                            break

                        # Use buffer_cap to load frame (no position conflicts with main thread)
                        self.buffer_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                        ret, frame = self.buffer_cap.read()

                        if ret and frame is not None:
                            self.frame_buffer[frame_num] = frame.copy()
                        else:
                            print(f"⚠ Failed to buffer frame {frame_num}")

                # Limit buffer size and clean up old frames aggressively
                max_buffer_size = self.buffer_size * 2
                if len(self.frame_buffer) > max_buffer_size:
                    print(f"🧹 CLEANING BUFFER: {len(self.frame_buffer)} > {max_buffer_size}, removing old frames")

                # Remove frames that are too far behind current position (keep only recent + future frames)
                frames_to_keep = [f for f in self.frame_buffer.keys() if f >= self.current_frame_num - 10]  # Keep 10 frames behind
                if len(frames_to_keep) < len(self.frame_buffer):
                    old_count = len(self.frame_buffer)
                    # Preserve OrderedDict type when cleaning
                    new_buffer = OrderedDict()
                    for k, v in self.frame_buffer.items():
                        if k in frames_to_keep:
                            new_buffer[k] = v
                    self.frame_buffer = new_buffer
                    print(f"🧹 CLEANED BUFFER: removed {old_count - len(self.frame_buffer)} old frames, kept {len(self.frame_buffer)}")

                # If still too large, remove oldest frames
                while len(self.frame_buffer) > max_buffer_size:
                    oldest_frame = min(self.frame_buffer.keys())
                    del self.frame_buffer[oldest_frame]
                    print(f"🧹 REMOVED OLDEST: frame {oldest_frame}")

                # Sleep only if we have plenty buffered frames, otherwise work continuously
                frames_ahead = len([f for f in self.frame_buffer.keys() if f > self.current_frame_num])
                if frames_ahead >= 45:  # If we have 45+ frames ahead, we can sleep
                    time.sleep(0.001)  # Tiny sleep to not hog CPU
                elif frames_ahead >= 20:  # Good buffer level
                    time.sleep(0.0005)  # Micro sleep
                # Otherwise, continue buffering immediately (no sleep)

            except Exception as e:
                print(f"⚠ Buffer thread error: {e}")
                break

        # Clean up buffer VideoCapture
        if self.buffer_cap is not None:
            try:
                self.buffer_cap.release()
            except:
                pass
            self.buffer_cap = None

        print("🔄 Buffer worker stopped")

    def load_frame_buffered(self, frame_num=None):
        """Load frame with buffering - instant if preloaded, fallback to loading"""
        if frame_num is None:
            frame_num = self.current_frame_num

        # Check if buffer thread is alive
        buffer_thread_alive = self.buffer_thread and self.buffer_thread.is_alive()

        # Debug: Show buffer status
        buffer_range = f"{min(self.frame_buffer.keys()) if self.frame_buffer else 'empty'}-{max(self.frame_buffer.keys()) if self.frame_buffer else 'empty'}"
        buffer_status = f"buffer_size={len(self.frame_buffer)}, range={buffer_range}, thread_alive={buffer_thread_alive}"

        # Check if frame is in buffer
        if frame_num in self.frame_buffer:
            frame = self.frame_buffer[frame_num]
            print(f"⚡ BUFFER HIT: frame {frame_num} loaded instantly ({buffer_status})")
            return frame
        else:
            # Not in buffer, load normally (will be slow)
            print(f"🐌 BUFFER MISS: frame {frame_num} loading slowly... ({buffer_status})")
            start_time = time.time()
            frame = self.load_frame(frame_num)
            load_time = (time.time() - start_time) * 1000
            print(f"🐌 FRAME LOAD TIME: {load_time:.1f}ms for frame {frame_num}")

            # Add to buffer for future use
            if frame is not None:
                self.frame_buffer[frame_num] = frame.copy()
            return frame
    
    def _update_buffer_status_label(self):
        """Update the buffer status label in the GUI"""
        try:
            if not hasattr(self, 'buffer_status_label') or not self.buffer_status_label.winfo_exists():
                return
            
            buffer_size = len(self.frame_buffer)
            buffer_max = getattr(self, 'buffer_size', 320)  # Default to 320 if not set
            
            # Calculate fill percentage
            fill_pct = int((buffer_size / buffer_max) * 100) if buffer_max > 0 else 0
            
            # Determine color based on fill level
            if fill_pct < 30:
                color = "red"
            elif fill_pct < 60:
                color = "orange"
            else:
                color = "green"
            
            # Update label text and color
            status_text = f"{buffer_size}/{buffer_max} ({fill_pct}%)"
            self.buffer_status_label.config(text=status_text, foreground=color)
        except (tk.TclError, AttributeError):
            pass  # Widget may not exist yet

    def on_closing(self):
        """Handle window closing - stop file watching and cleanup"""
        # Stop buffer thread
        self.stop_buffer_thread()
        self.stop_file_watching()
        self._stop_overlay_worker()
        if self.cap:
            self.cap.release()
        if self.buffer_cap:
            self.buffer_cap.release()
        self.root.destroy()
    
    def apply_zoom_pan(self, frame, canvas_num):
        """Apply zoom and pan to a frame"""
        if canvas_num == 1:
            zoom = self.zoom_level1
            pan_x = self.pan_x1
            pan_y = self.pan_y1
        else:
            zoom = self.zoom_level2
            pan_x = self.pan_x2
            pan_y = self.pan_y2
        
        if zoom == 1.0 and pan_x == 0 and pan_y == 0:
            return frame
        
        h, w = frame.shape[:2]
        
        # Calculate zoomed dimensions
        new_w = int(w * zoom)
        new_h = int(h * zoom)
        
        # Resize frame
        zoomed = cv2.resize(frame, (new_w, new_h))
        
        # Calculate crop region (centered, then panned)
        # Pan offset is in display coordinates, so we need to scale it
        crop_x = int((new_w - w) / 2 - pan_x)
        crop_y = int((new_h - h) / 2 - pan_y)
        
        # Ensure crop region is within bounds
        crop_x = max(0, min(crop_x, new_w - w))
        crop_y = max(0, min(crop_y, new_h - h))
        
        # Crop to original size
        if crop_x + w <= new_w and crop_y + h <= new_h:
            cropped = zoomed[crop_y:crop_y+h, crop_x:crop_x+w]
        else:
            # Fallback if crop goes out of bounds
            cropped = frame
        
        return cropped
    
    def apply_zoom_pan_single(self, frame):
        """Apply zoom and pan to a frame for single frame mode"""
        if self.zoom_level == 1.0 and self.pan_x == 0 and self.pan_y == 0:
            return frame
        
        h, w = frame.shape[:2]
        
        # Calculate zoomed dimensions
        new_w = int(w * self.zoom_level)
        new_h = int(h * self.zoom_level)
        
        # Resize frame
        zoomed = cv2.resize(frame, (new_w, new_h))
        
        # Calculate crop region (centered, then panned)
        # Pan offset is in display coordinates, so we need to scale it
        crop_x = int((new_w - w) / 2 - self.pan_x)
        crop_y = int((new_h - h) / 2 - self.pan_y)
        
        # Ensure crop region is within bounds
        crop_x = max(0, min(crop_x, new_w - w))
        crop_y = max(0, min(crop_y, new_h - h))
        
        # Crop to original size
        if crop_x + w <= new_w and crop_y + h <= new_h:
            cropped = zoomed[crop_y:crop_y+h, crop_x:crop_x+w]
        else:
            # Fallback if crop goes out of bounds
            cropped = frame
        
        return cropped
    
    def zoom_canvas(self, canvas_num, zoom_factor):
        """Zoom in/out on a canvas"""
        if canvas_num == 1:
            self.zoom_level1 = max(0.5, min(5.0, self.zoom_level1 * zoom_factor))
            if self.zoom_label1 is not None:
                self.zoom_label1.config(text=f"{self.zoom_level1:.1f}x")
        else:
            self.zoom_level2 = max(0.5, min(5.0, self.zoom_level2 * zoom_factor))
            if self.zoom_label2 is not None:
                self.zoom_label2.config(text=f"{self.zoom_level2:.1f}x")
        
        self.render_overlays()
    
    def zoom_single(self, zoom_factor):
        """Zoom in/out on single frame canvas"""
        self.zoom_level = max(0.5, min(5.0, self.zoom_level * zoom_factor))
        if hasattr(self, 'zoom_label') and self.zoom_label:
            self.zoom_label.config(text=f"{self.zoom_level:.1f}x")
        # Reset pan when zooming to 1.0
        if self.zoom_level == 1.0:
            self.pan_x = 0
            self.pan_y = 0
        self.render_overlays()
    
    def reset_zoom_single(self):
        """Reset zoom and pan for single frame canvas"""
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        if hasattr(self, 'zoom_label') and self.zoom_label:
            self.zoom_label.config(text="1.0x")
        self.render_overlays()
    
    def reset_zoom(self, canvas_num):
        """Reset zoom and pan for a canvas"""
        if canvas_num == 1:
            self.zoom_level1 = 1.0
            self.pan_x1 = 0
            self.pan_y1 = 0
            if self.zoom_label1 is not None:
                self.zoom_label1.config(text="1.0x")
        else:
            self.zoom_level2 = 1.0
            self.pan_x2 = 0
            self.pan_y2 = 0
            if self.zoom_label2 is not None:
                self.zoom_label2.config(text="1.0x")
        
        self.render_overlays()
    
    def on_canvas1_click(self, event):
        """Handle click on canvas1 (for panning when zoomed, or zoom to point)"""
        if self.zoom_level1 > 1.0:
            # Already zoomed - start panning
            self.is_panning1 = True
            self.pan_start_x1 = event.x
            self.pan_start_y1 = event.y
        else:
            # Not zoomed - zoom in at click point (optional, can be enabled)
            # For now, just enable panning mode
            pass
    
    def on_canvas1_drag(self, event):
        """Handle drag on canvas1 (for panning)"""
        if self.is_panning1 and self.zoom_level1 > 1.0:
            # Calculate drag distance
            dx = event.x - self.pan_start_x1
            dy = event.y - self.pan_start_y1
            
            # Update pan offset (inverse direction for natural panning)
            self.pan_x1 -= dx
            self.pan_y1 -= dy
            
            # Update start position for next drag
            self.pan_start_x1 = event.x
            self.pan_start_y1 = event.y
            
            self.render_overlays()
    
    def on_canvas1_release(self, event):
        """Handle release on canvas1"""
        self.is_panning1 = False
    
    def on_canvas1_wheel(self, event):
        """Handle mouse wheel on canvas1 (for zoom)"""
        if event.delta > 0 or event.num == 4:  # Zoom in
            self.zoom_canvas(1, 1.2)
        else:  # Zoom out
            self.zoom_canvas(1, 1/1.2)
    
    def on_canvas2_click(self, event):
        """Handle click on canvas2 (for panning when zoomed, or zoom to point)"""
        if self.zoom_level2 > 1.0:
            # Already zoomed - start panning
            self.is_panning2 = True
            self.pan_start_x2 = event.x
            self.pan_start_y2 = event.y
        else:
            # Not zoomed - zoom in at click point (optional, can be enabled)
            # For now, just enable panning mode
            pass
    
    def on_canvas2_drag(self, event):
        """Handle drag on canvas2 (for panning)"""
        if self.is_panning2 and self.zoom_level2 > 1.0:
            # Calculate drag distance
            dx = event.x - self.pan_start_x2
            dy = event.y - self.pan_start_y2
            
            # Update pan offset (inverse direction for natural panning)
            self.pan_x2 -= dx
            self.pan_y2 -= dy
            
            # Update start position for next drag
            self.pan_start_x2 = event.x
            self.pan_start_y2 = event.y
            
            self.render_overlays()
    
    def maximize_window(self):
        """Maximize or restore the window"""
        if not self.is_maximized:
            # Exit fullscreen first if active
            if self.is_fullscreen:
                self.toggle_fullscreen()
            
            # Store current geometry before maximizing
            self.normal_geometry = self.root.geometry()
            # Maximize window
            self.root.state('zoomed')  # Windows
            try:
                self.root.attributes('-zoomed', True)  # Linux
            except:
                pass
            self.is_maximized = True
            # Update button text
            if hasattr(self, 'maximize_button'):
                self.maximize_button.config(text="Restore")
            
            # Force canvas resize after maximize
            self.root.after(100, self._force_canvas_resize)
        else:
            # Restore to normal size
            if self.normal_geometry:
                self.root.geometry(self.normal_geometry)
            else:
                # Fallback to default size
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                window_width = min(int(screen_width * 0.95), 1400)
                window_height = min(int(screen_height * 0.95), 900)
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
                self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            try:
                self.root.attributes('-zoomed', False)  # Linux
            except:
                pass
            self.root.state('normal')  # Windows
            self.is_maximized = False
            # Update button text
            if hasattr(self, 'maximize_button'):
                self.maximize_button.config(text="Maximize")
            
            # Force canvas resize after restore
            self.root.after(100, self._force_canvas_resize)
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if not self.is_fullscreen:
            # Exit maximize first if active
            if self.is_maximized:
                self.maximize_window()
            
            # Store normal geometry before going fullscreen
            if not self.normal_geometry:
                self.normal_geometry = self.root.geometry()
            
            # Enter fullscreen
            self.root.attributes('-fullscreen', True)
            self.is_fullscreen = True
            if hasattr(self, 'fullscreen_button'):
                self.fullscreen_button.config(text="Exit Full Screen")
            
            # Hide controls panel in fullscreen (optional - can be toggled)
            # For now, keep controls visible but make them smaller
            self.root.after(100, self._force_canvas_resize)
        else:
            # Exit fullscreen
            self.root.attributes('-fullscreen', False)
            self.is_fullscreen = False
            if hasattr(self, 'fullscreen_button'):
                self.fullscreen_button.config(text="Full Screen")
            
            # Restore geometry if available
            if self.normal_geometry:
                self.root.geometry(self.normal_geometry)
            
            self.root.after(100, self._force_canvas_resize)
        
        # Bind Escape key to exit fullscreen
        if self.is_fullscreen:
            self.root.bind('<Escape>', lambda e: self.toggle_fullscreen())
        else:
            self.root.unbind('<Escape>')
    
    def _force_canvas_resize(self):
        """Force canvas to resize and update display"""
        try:
            # Invalidate cached canvas size
            self.cached_canvas_size = None
            
            # Update canvas width calculation (with force flag to bypass throttling)
            if hasattr(self, '_update_canvas_width'):
                self._update_canvas_width(force=True)
            
            # Only re-render if we have a frame loaded and are not currently playing
            # This prevents unnecessary renders during window operations
            if (hasattr(self, 'current_frame') and self.current_frame is not None and 
                not self.is_playing):
                # Use after() to defer render slightly, allowing window to finish resizing
                self.root.after(200, self.render_overlays)
        except Exception as e:
            print(f"Error forcing canvas resize: {e}")
    
    def _load_viz_settings(self, viz_settings):
        """Load visualization settings from main GUI"""
        try:
            # Feet marker settings
            if 'feet_marker_style' in viz_settings:
                self.feet_marker_style.set(viz_settings['feet_marker_style'])
            if 'feet_marker_opacity' in viz_settings:
                self.feet_marker_opacity.set(viz_settings['feet_marker_opacity'])
            if 'feet_marker_enable_glow' in viz_settings:
                self.feet_marker_enable_glow.set(viz_settings['feet_marker_enable_glow'])
            if 'feet_marker_glow_intensity' in viz_settings:
                self.feet_marker_glow_intensity.set(viz_settings['feet_marker_glow_intensity'])
            if 'feet_marker_enable_shadow' in viz_settings:
                self.feet_marker_enable_shadow.set(viz_settings['feet_marker_enable_shadow'])
            if 'feet_marker_shadow_offset' in viz_settings:
                self.feet_marker_shadow_offset.set(viz_settings['feet_marker_shadow_offset'])
            if 'feet_marker_shadow_opacity' in viz_settings:
                self.feet_marker_shadow_opacity.set(viz_settings['feet_marker_shadow_opacity'])
            if 'feet_marker_enable_gradient' in viz_settings:
                self.feet_marker_enable_gradient.set(viz_settings['feet_marker_enable_gradient'])
            if 'feet_marker_enable_pulse' in viz_settings:
                self.feet_marker_enable_pulse.set(viz_settings['feet_marker_enable_pulse'])
            if 'feet_marker_pulse_speed' in viz_settings:
                self.feet_marker_pulse_speed.set(viz_settings['feet_marker_pulse_speed'])
            if 'feet_marker_enable_particles' in viz_settings:
                self.feet_marker_enable_particles.set(viz_settings['feet_marker_enable_particles'])
            if 'feet_marker_particle_count' in viz_settings:
                self.feet_marker_particle_count.set(viz_settings['feet_marker_particle_count'])
            if 'feet_marker_vertical_offset' in viz_settings:
                self.feet_marker_vertical_offset.set(viz_settings['feet_marker_vertical_offset'])
            
            # Box settings
            if 'box_shrink_factor' in viz_settings:
                self.box_shrink_factor.set(viz_settings['box_shrink_factor'])
            if 'box_thickness' in viz_settings:
                self.box_thickness.set(viz_settings['box_thickness'])
            if 'use_custom_box_color' in viz_settings:
                self.use_custom_box_color.set(viz_settings['use_custom_box_color'])
            # Handle box_color_rgb (new format) or individual components (old format)
            if 'box_color_rgb' in viz_settings:
                self.box_color_rgb.set(viz_settings['box_color_rgb'])
                # Sync individual components from RGB string
                try:
                    from color_picker_utils import rgb_string_to_tuple
                    r, g, b = rgb_string_to_tuple(viz_settings['box_color_rgb'], default=(0, 255, 0))
                    self.box_color_r.set(r)
                    self.box_color_g.set(g)
                    self.box_color_b.set(b)
                except Exception as sync_err:
                    # Silently fail - components will use defaults
                    pass
            elif 'box_color_r' in viz_settings:
                # Old format: individual components
                self.box_color_r.set(viz_settings['box_color_r'])
            if 'box_color_g' in viz_settings:
                self.box_color_g.set(viz_settings['box_color_g'])
            if 'box_color_b' in viz_settings:
                self.box_color_b.set(viz_settings['box_color_b'])
                # Update RGB string from individual components
                try:
                    self.box_color_rgb.set(f"{self.box_color_r.get()},{self.box_color_g.get()},{self.box_color_b.get()}")
                except:
                    pass
            if 'player_viz_alpha' in viz_settings:
                self.player_viz_alpha.set(viz_settings['player_viz_alpha'])
            
            # Label settings
            if 'use_custom_label_color' in viz_settings:
                self.use_custom_label_color.set(viz_settings['use_custom_label_color'])
            # Handle label_color_rgb (new format) or individual components (old format)
            if 'label_color_rgb' in viz_settings:
                self.label_color_rgb.set(viz_settings['label_color_rgb'])
                # Sync individual components from RGB string
                try:
                    from color_picker_utils import rgb_string_to_tuple
                    r, g, b = rgb_string_to_tuple(viz_settings['label_color_rgb'], default=(255, 255, 255))
                    self.label_color_r.set(r)
                    self.label_color_g.set(g)
                    self.label_color_b.set(b)
                except Exception as sync_err:
                    # Silently fail - components will use defaults
                    pass
            elif 'label_color_r' in viz_settings:
                # Old format: individual components
                self.label_color_r.set(viz_settings['label_color_r'])
            if 'label_color_g' in viz_settings:
                self.label_color_g.set(viz_settings['label_color_g'])
            if 'label_color_b' in viz_settings:
                self.label_color_b.set(viz_settings['label_color_b'])
                # Update RGB string from individual components
                try:
                    self.label_color_rgb.set(f"{self.label_color_r.get()},{self.label_color_g.get()},{self.label_color_b.get()}")
                except:
                    pass
            if 'label_font_scale' in viz_settings:
                self.label_font_scale.set(viz_settings['label_font_scale'])
            if 'label_type' in viz_settings:
                self.label_type.set(viz_settings['label_type'])
            if 'label_custom_text' in viz_settings:
                self.label_custom_text.set(viz_settings['label_custom_text'])
            if 'label_font_face' in viz_settings:
                self.label_font_face.set(viz_settings['label_font_face'])
            
            # Prediction settings
            if 'prediction_duration' in viz_settings:
                self.prediction_duration.set(viz_settings['prediction_duration'])
            if 'prediction_size' in viz_settings:
                self.prediction_size.set(viz_settings['prediction_size'])
            if 'prediction_color_r' in viz_settings:
                self.prediction_color_r.set(viz_settings['prediction_color_r'])
            if 'prediction_color_g' in viz_settings:
                self.prediction_color_g.set(viz_settings['prediction_color_g'])
            if 'prediction_color_b' in viz_settings:
                self.prediction_color_b.set(viz_settings['prediction_color_b'])
            if 'prediction_color_alpha' in viz_settings:
                self.prediction_color_alpha.set(viz_settings['prediction_color_alpha'])
            if 'prediction_style' in viz_settings:
                self.prediction_style.set(viz_settings['prediction_style'])
            
            # Style settings
            if 'viz_style' in viz_settings:
                self.viz_style.set(viz_settings['viz_style'])
            if 'viz_color_mode' in viz_settings:
                self.viz_color_mode.set(viz_settings['viz_color_mode'])
            
            # Show/hide settings
            if 'show_bounding_boxes' in viz_settings:
                self.show_player_boxes.set(viz_settings['show_bounding_boxes'])
            if 'show_circles_at_feet' in viz_settings:
                self.show_player_circles.set(viz_settings['show_circles_at_feet'])
            if 'show_player_labels' in viz_settings:
                self.show_player_labels.set(viz_settings['show_player_labels'])
            if 'show_yolo_boxes' in viz_settings:
                self.show_yolo_boxes.set(viz_settings['show_yolo_boxes'])
            if 'show_predicted_boxes' in viz_settings:
                self.show_predicted_boxes.set(viz_settings['show_predicted_boxes'])
            if 'show_ball_possession' in viz_settings:
                self.show_ball_possession.set(viz_settings['show_ball_possession'])
            if 'analytics_position' in viz_settings:
                self.analytics_position.set(viz_settings['analytics_position'])
            if 'analytics_font_scale' in viz_settings:
                self.analytics_font_scale.set(viz_settings['analytics_font_scale'])
            if 'analytics_font_face' in viz_settings:
                self.analytics_font_face.set(viz_settings['analytics_font_face'])
            if 'use_custom_analytics_color' in viz_settings:
                self.use_custom_analytics_color.set(viz_settings['use_custom_analytics_color'])
            # Handle analytics_color_rgb (new format) or individual components (old format)
            if 'analytics_color_rgb' in viz_settings:
                self.analytics_color_rgb.set(viz_settings['analytics_color_rgb'])
                # Sync individual components from RGB string
                try:
                    from color_picker_utils import rgb_string_to_tuple
                    r, g, b = rgb_string_to_tuple(viz_settings['analytics_color_rgb'], default=(255, 255, 255))
                    self.analytics_color_r.set(r)
                    self.analytics_color_g.set(g)
                    self.analytics_color_b.set(b)
                except Exception as sync_err:
                    pass
            elif 'analytics_color_r' in viz_settings:
                # Old format: individual components
                self.analytics_color_r.set(viz_settings['analytics_color_r'])
            if 'analytics_color_g' in viz_settings:
                self.analytics_color_g.set(viz_settings['analytics_color_g'])
            if 'analytics_color_b' in viz_settings:
                self.analytics_color_b.set(viz_settings['analytics_color_b'])
                # Update RGB string from individual components
                try:
                    self.analytics_color_rgb.set(f"{self.analytics_color_r.get()},{self.analytics_color_g.get()},{self.analytics_color_b.get()}")
                except:
                    pass
            
            # Handle analytics_title_color_rgb (new format) or individual components (old format)
            if 'analytics_title_color_rgb' in viz_settings:
                self.analytics_title_color_rgb.set(viz_settings['analytics_title_color_rgb'])
                # Sync individual components from RGB string
                try:
                    from color_picker_utils import rgb_string_to_tuple
                    r, g, b = rgb_string_to_tuple(viz_settings['analytics_title_color_rgb'], default=(255, 255, 0))
                    self.analytics_title_color_r.set(r)
                    self.analytics_title_color_g.set(g)
                    self.analytics_title_color_b.set(b)
                except Exception as sync_err:
                    pass
            elif 'analytics_title_color_r' in viz_settings:
                # Old format: individual components
                self.analytics_title_color_r.set(viz_settings['analytics_title_color_r'])
            if 'analytics_title_color_g' in viz_settings:
                self.analytics_title_color_g.set(viz_settings['analytics_title_color_g'])
            if 'analytics_title_color_b' in viz_settings:
                self.analytics_title_color_b.set(viz_settings['analytics_title_color_b'])
                # Update RGB string from individual components
                try:
                    self.analytics_title_color_rgb.set(f"{self.analytics_title_color_r.get()},{self.analytics_title_color_g.get()},{self.analytics_title_color_b.get()}")
                except:
                    pass
        except Exception as e:
            print(f"⚠ Warning: Could not load visualization settings: {e}")
            import traceback
            traceback.print_exc()
    
    def minimize_window(self):
        """Minimize the window"""
        try:
            # Try to minimize - may fail if window is transient
            self.root.iconify()
        except tk.TclError as e:
            # If window is transient (child window), we can't minimize it
            # Instead, just lower it behind other windows
            if "transient" in str(e).lower() or "iconify" in str(e).lower():
                self.root.lower()
                # Optionally remove transient attribute to allow minimizing
                try:
                    self.root.transient("")  # Remove transient attribute
                    self.root.iconify()  # Now try to minimize again
                except:
                    pass  # If that fails, just lower it
            else:
                raise  # Re-raise if it's a different error
    
    def toggle_always_on_top(self):
        """Toggle always on top attribute"""
        self.root.attributes('-topmost', self.always_on_top.get())
    
    def build_analytics_tab(self):
        """Build the Analytics tab with stats and analytics display"""
        if not hasattr(self, 'analytics_scrollable_frame'):
            return
        
        analytics_frame = self.analytics_scrollable_frame
        
        # Current Frame Stats Section
        current_frame_frame = ttk.LabelFrame(analytics_frame, text="Current Frame Stats", padding="10")
        current_frame_frame.pack(fill=tk.X, pady=5, padx=5)
        
        self.current_frame_stats_label = ttk.Label(current_frame_frame, 
                                                   text="Frame: 0\nNo data available",
                                                   font=("Arial", 9),
                                                   justify=tk.LEFT,
                                                   wraplength=350)
        self.current_frame_stats_label.pack(anchor=tk.W, pady=2)
        
        # Player Selection Section
        player_select_frame = ttk.LabelFrame(analytics_frame, text="Player Statistics", padding="10")
        player_select_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(player_select_frame, text="Select Player:", font=("Arial", 9)).pack(anchor=tk.W, pady=2)
        
        self.player_select_var = tk.StringVar(value="All Players")
        self.player_select_combo = ttk.Combobox(player_select_frame, 
                                                textvariable=self.player_select_var,
                                                state="readonly",
                                                width=30)
        self.player_select_combo.pack(fill=tk.X, pady=2)
        self.player_select_combo.bind("<<ComboboxSelected>>", self.on_player_select_change)
        
        # Player Stats Display
        self.player_stats_text = tk.Text(player_select_frame, 
                                         height=15, 
                                         width=40,
                                         wrap=tk.WORD,
                                         font=("Courier", 9),
                                         relief=tk.SUNKEN,
                                         borderwidth=1)
        self.player_stats_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollbar for player stats
        player_stats_scrollbar = ttk.Scrollbar(player_select_frame, 
                                               orient=tk.VERTICAL,
                                               command=self.player_stats_text.yview)
        self.player_stats_text.configure(yscrollcommand=player_stats_scrollbar.set)
        player_stats_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Summary Statistics Section
        summary_frame = ttk.LabelFrame(analytics_frame, text="Video Summary Statistics", padding="10")
        summary_frame.pack(fill=tk.X, pady=5, padx=5)
        
        self.summary_stats_label = ttk.Label(summary_frame,
                                            text="Load CSV to see summary statistics",
                                            font=("Arial", 9),
                                            justify=tk.LEFT,
                                            wraplength=350)
        self.summary_stats_label.pack(anchor=tk.W, pady=2)
        
        # Update button
        ttk.Button(summary_frame, 
                  text="Refresh Statistics",
                  command=self.update_analytics_display).pack(pady=5)
        
        # Ball Analytics Section (Kinovea-style)
        ball_analytics_frame = ttk.LabelFrame(analytics_frame, text="⚽ Ball Analytics (Kinovea-style)", padding="10")
        ball_analytics_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Current ball stats
        self.ball_speed_label = ttk.Label(ball_analytics_frame, text="Speed: -- m/s (-- mph)", 
                                          font=("Arial", 10, "bold"))
        self.ball_speed_label.pack(anchor=tk.W, pady=2)
        
        self.ball_distance_label = ttk.Label(ball_analytics_frame, text="Distance: -- m (-- ft)", 
                                            font=("Arial", 9))
        self.ball_distance_label.pack(anchor=tk.W, pady=2)
        
        self.ball_acceleration_label = ttk.Label(ball_analytics_frame, text="Acceleration: -- m/s²", 
                                                 font=("Arial", 9))
        self.ball_acceleration_label.pack(anchor=tk.W, pady=2)
        
        # Trajectory visualization controls
        ttk.Separator(ball_analytics_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(ball_analytics_frame, text="Show Ball Trajectory Overlay", 
                       variable=self.show_ball_trajectory,
                       command=self.update_display).pack(anchor=tk.W, pady=2)
        
        ttk.Checkbutton(ball_analytics_frame, text="Show Speed Color Coding", 
                       variable=self.show_ball_speed_overlay,
                       command=self.update_display).pack(anchor=tk.W, pady=2)
        
        # Action buttons
        button_frame = ttk.Frame(ball_analytics_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="Calculate Trajectory", 
                  command=self.calculate_ball_trajectory, width=18).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(button_frame, text="View Statistics", 
                  command=self.show_ball_trajectory_stats, width=18).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(button_frame, text="Export (Kinovea)", 
                  command=self.export_ball_trajectory, width=18).pack(side=tk.LEFT, padx=2)
        
        # Trajectory stats display
        self.ball_trajectory_stats_text = tk.Text(ball_analytics_frame, 
                                                  height=8, 
                                                  width=40,
                                                  wrap=tk.WORD,
                                                  font=("Courier", 8),
                                                  relief=tk.SUNKEN,
                                                  borderwidth=1,
                                                  state=tk.DISABLED)
        self.ball_trajectory_stats_text.pack(fill=tk.BOTH, expand=True, pady=5)
    
    def on_player_select_change(self, event=None):
        """Handle player selection change in analytics tab"""
        self.update_analytics_display()
    
    def update_analytics_display(self):
        """Update the analytics display in the Analytics tab"""
        # Update current frame stats
        if hasattr(self, 'current_frame_stats_label'):
            frame_num = self.current_frame_num
            stats_text = f"Frame: {frame_num} / {self.total_frames}\n"
            
            if hasattr(self, 'analytics_data') and self.analytics_data and frame_num in self.analytics_data:
                players_in_frame = len(self.analytics_data[frame_num])
                stats_text += f"Players in frame: {players_in_frame}\n"
                
                # Show ball detection status
                # ball_data is structured as frame_num -> (x, y) tuple
                if hasattr(self, 'ball_data') and self.ball_data and frame_num in self.ball_data:
                    ball_info = self.ball_data[frame_num]
                    # Handle both tuple (x, y) and dict formats
                    if ball_info is not None:
                        if isinstance(ball_info, tuple) and len(ball_info) >= 2:
                            # Tuple format: (x, y)
                            ball_x, ball_y = ball_info[0], ball_info[1]
                            if ball_x is not None and ball_y is not None:
                                stats_text += f"Ball detected: Yes\n"
                                stats_text += f"Ball position: ({ball_x:.1f}, {ball_y:.1f})\n"
                            else:
                                stats_text += f"Ball detected: No\n"
                        elif isinstance(ball_info, dict):
                            # Dictionary format: {'x': x, 'y': y}
                            if ball_info.get('x') is not None:
                                stats_text += f"Ball detected: Yes\n"
                                stats_text += f"Ball position: ({ball_info.get('x', 0):.1f}, {ball_info.get('y', 0):.1f})\n"
                            else:
                                stats_text += f"Ball detected: No\n"
                        else:
                            stats_text += f"Ball detected: No\n"
                    else:
                        stats_text += f"Ball detected: No\n"
                else:
                    stats_text += f"Ball detected: No\n"
            else:
                stats_text += "No analytics data for this frame"
            
            self.current_frame_stats_label.config(text=stats_text)
        
        # Update player statistics
        if hasattr(self, 'player_stats_text') and hasattr(self, 'player_select_var'):
            self.player_stats_text.delete(1.0, tk.END)
            
            selected_player = self.player_select_var.get()
            
            if not hasattr(self, 'analytics_data') or not self.analytics_data:
                self.player_stats_text.insert(tk.END, "No analytics data loaded.\nLoad CSV to see player statistics.")
                return
            
            # Update player list in combobox
            all_player_ids = set()
            for frame_data in self.analytics_data.values():
                all_player_ids.update(frame_data.keys())
            
            # Get player name mapping from multiple sources
            player_names_map = {}
            
            # 1. Try to load from CSV if available (player_name column)
            if hasattr(self, 'df') and self.df is not None:
                if 'player_name' in self.df.columns:
                    for _, row in self.df.iterrows():
                        if pd.notna(row.get('player_id')) and pd.notna(row.get('player_name')):
                            pid_str = str(int(row['player_id']))
                            player_name = str(row['player_name']).strip()
                            if player_name and player_name != 'nan' and player_name.lower() != 'none':
                                player_names_map[pid_str] = player_name
            
            # 2. Load from player_names.json (if exists)
            if hasattr(self, 'player_names') and self.player_names:
                for pid_str, name in self.player_names.items():
                    # Handle case where name might be a list or other non-string type
                    if name:
                        # Convert to string if needed
                        if isinstance(name, list):
                            name = name[0] if len(name) > 0 else str(name)
                        elif not isinstance(name, str):
                            name = str(name)
                        # Now check if it's a valid name
                        if name.strip() and name.lower() != 'none':
                            player_names_map[pid_str] = name
            
            # 3. Try to load from player gallery (cache to avoid repeated loading)
            if not hasattr(self, '_player_gallery') or self._player_gallery is None:
                try:
                    from player_gallery import PlayerGallery
                    import logging
                    # Temporarily suppress INFO logs to avoid spam
                    logger = logging.getLogger('player_gallery')
                    old_level = logger.level
                    logger.setLevel(logging.WARNING)
                    self._player_gallery = PlayerGallery()
                    logger.setLevel(old_level)
                    # Only print once if we successfully loaded
                    if not hasattr(self, '_gallery_loaded_logged'):
                        print(f"✓ Loaded {len(self._player_gallery.players)} players from gallery")
                        self._gallery_loaded_logged = True
                except Exception as e:
                    self._player_gallery = None  # Mark as failed to avoid retrying
        
            if self._player_gallery is not None:
                try:
                    # Get track-to-player mappings from gallery
                    for pid in all_player_ids:
                        pid_str = str(pid)
                        if pid_str not in player_names_map:
                            # Try to find player by track ID in gallery
                            players = self._player_gallery.list_players()
                            for player_id, player_name in players:
                                # Check if this player has this track ID in their reference frames
                                profile = self._player_gallery.get_player(player_id)
                                if profile and profile.reference_frames:
                                    for ref_frame in profile.reference_frames:
                                        if ref_frame.get('track_id') == pid:
                                            player_names_map[pid_str] = player_name
                                            break
                except Exception as e:
                    pass  # Gallery lookup failed, continue with existing names
            
            # Build consolidated player list (group by name, show unique players)
            # Create a mapping of player_name -> list of track_ids
            name_to_ids = {}
            for pid in sorted(all_player_ids):
                pid_str = str(pid)
                player_name = player_names_map.get(pid_str, f"Player #{pid}")
                if player_name not in name_to_ids:
                    name_to_ids[player_name] = []
                name_to_ids[player_name].append(pid)
            
            # Build player list: "All Players" + unique player names (sorted)
            if all_player_ids:
                player_list = ["All Players"] + sorted(name_to_ids.keys())
                if list(self.player_select_combo['values']) != player_list:
                    self.player_select_combo['values'] = player_list
                    if selected_player not in player_list:
                        self.player_select_var.set("All Players")
                        selected_player = "All Players"
            
            # Display statistics
            if selected_player == "All Players":
                # Show stats for all players in current frame
                frame_num = self.current_frame_num
                if frame_num in self.analytics_data:
                    self.player_stats_text.insert(tk.END, f"=== Frame {frame_num} - All Players ===\n\n")
                    
                    # Group by player name (consolidate multiple track IDs for same player)
                    players_by_name = {}
                    for player_id in sorted(self.analytics_data[frame_num].keys()):
                        player_name = player_names_map.get(str(player_id), f"Player #{player_id}")
                        analytics = self.analytics_data[frame_num][player_id]
                        
                        # Consolidate: if multiple track IDs have same name, combine their analytics
                        if player_name not in players_by_name:
                            players_by_name[player_name] = {
                                'analytics': analytics,
                                'track_ids': [player_id]
                            }
                        else:
                            # Multiple track IDs for same player - merge analytics
                            players_by_name[player_name]['track_ids'].append(player_id)
                            # Use the most recent/complete analytics
                            players_by_name[player_name]['analytics'] = analytics
                    
                    # Display consolidated players
                    for player_name in sorted(players_by_name.keys()):
                        entry = players_by_name[player_name]
                        track_ids = entry['track_ids']
                        analytics = entry['analytics']
                        
                        # Show track IDs if multiple
                        if len(track_ids) > 1:
                            self.player_stats_text.insert(tk.END, f"--- {player_name} (Tracks: {', '.join([f'#{tid}' for tid in track_ids])}) ---\n")
                        else:
                            self.player_stats_text.insert(tk.END, f"--- {player_name} ---\n")
                        self.display_player_analytics(analytics, track_ids[0])
                        self.player_stats_text.insert(tk.END, "\n")
                else:
                    self.player_stats_text.insert(tk.END, f"No data for frame {frame_num}")
            else:
                # Show stats for selected player (by name) across all frames
                # Find all track IDs that match this player name
                matching_track_ids = []
                for pid in all_player_ids:
                    pid_str = str(pid)
                    player_name = player_names_map.get(pid_str, f"Player #{pid}")
                    if player_name == selected_player:
                        matching_track_ids.append(pid)
                
                if not matching_track_ids:
                    self.player_stats_text.insert(tk.END, f"No data found for {selected_player}")
                    return
                
                player_name = selected_player
                
                # Show track IDs if multiple
                if len(matching_track_ids) > 1:
                    self.player_stats_text.insert(tk.END, f"=== {player_name} (Tracks: {', '.join([f'#{tid}' for tid in matching_track_ids])}) - All Frames ===\n\n")
                else:
                    self.player_stats_text.insert(tk.END, f"=== {player_name} - All Frames ===\n\n")
                
                # Collect all analytics for all track IDs of this player
                all_analytics = []
                frames_with_data = []
                for frame_num, frame_data in self.analytics_data.items():
                    for track_id in matching_track_ids:
                        if track_id in frame_data:
                            all_analytics.append(frame_data[track_id])
                            frames_with_data.append(frame_num)
                
                if all_analytics:
                    # Calculate summary statistics
                    self.player_stats_text.insert(tk.END, f"Frames with data: {len(frames_with_data)}\n")
                    self.player_stats_text.insert(tk.END, f"Frame range: {min(frames_with_data)} - {max(frames_with_data)}\n\n")
                    
                    # Calculate averages and maxes
                    summary = self.calculate_player_summary(all_analytics)
                    self.display_summary_stats(summary)
                    
                    # Show current frame stats (use first matching track ID)
                    if self.current_frame_num in self.analytics_data:
                        for track_id in matching_track_ids:
                            if track_id in self.analytics_data[self.current_frame_num]:
                                self.player_stats_text.insert(tk.END, f"\n--- Current Frame ({self.current_frame_num}) ---\n")
                                self.display_player_analytics(self.analytics_data[self.current_frame_num][track_id], track_id)
                                break
                else:
                    self.player_stats_text.insert(tk.END, f"No data found for {player_name}")
        
        # Update summary statistics
        if hasattr(self, 'summary_stats_label') and hasattr(self, 'analytics_data') and self.analytics_data:
            summary_text = self.calculate_video_summary()
            self.summary_stats_label.config(text=summary_text)
    
    def display_player_analytics(self, analytics, player_id):
        """Display analytics for a single player"""
        use_imperial = hasattr(self, 'df') and self.df is not None and 'player_speed_mph' in self.df.columns
        
        # Speed metrics
        if 'player_speed_mph' in analytics or 'player_speed_mps' in analytics:
            speed = analytics.get('player_speed_mph') if use_imperial else analytics.get('player_speed_mps')
            if speed is not None and not (isinstance(speed, float) and np.isnan(speed)):
                unit = "mph" if use_imperial else "m/s"
                self.player_stats_text.insert(tk.END, f"Speed: {speed:.2f} {unit}\n")
        
        if 'max_speed_mph' in analytics or 'max_speed_mps' in analytics:
            max_speed = analytics.get('max_speed_mph') if use_imperial else analytics.get('max_speed_mps')
            if max_speed is not None and not (isinstance(max_speed, float) and np.isnan(max_speed)):
                unit = "mph" if use_imperial else "m/s"
                self.player_stats_text.insert(tk.END, f"Max Speed: {max_speed:.2f} {unit}\n")
        
        if 'avg_speed_mph' in analytics or 'avg_speed_mps' in analytics:
            avg_speed = analytics.get('avg_speed_mph') if use_imperial else analytics.get('avg_speed_mps')
            if avg_speed is not None and not (isinstance(avg_speed, float) and np.isnan(avg_speed)):
                unit = "mph" if use_imperial else "m/s"
                self.player_stats_text.insert(tk.END, f"Avg Speed: {avg_speed:.2f} {unit}\n")
        
        # Distance metrics
        if 'distance_traveled_ft' in analytics or 'distance_traveled_m' in analytics:
            distance = analytics.get('distance_traveled_ft') if use_imperial else analytics.get('distance_traveled_m')
            if distance is not None and not (isinstance(distance, float) and np.isnan(distance)):
                unit = "ft" if use_imperial else "m"
                self.player_stats_text.insert(tk.END, f"Distance: {distance:.2f} {unit}\n")
        
        if 'distance_to_ball_px' in analytics:
            dist_to_ball = analytics.get('distance_to_ball_px')
            if dist_to_ball is not None and not (isinstance(dist_to_ball, float) and np.isnan(dist_to_ball)):
                self.player_stats_text.insert(tk.END, f"Distance to Ball: {dist_to_ball:.1f} px\n")
        
        # Position metrics
        if 'field_position_x_pct' in analytics and 'field_position_y_pct' in analytics:
            x_pct = analytics.get('field_position_x_pct')
            y_pct = analytics.get('field_position_y_pct')
            if x_pct is not None and y_pct is not None:
                if not (isinstance(x_pct, float) and np.isnan(x_pct)) and not (isinstance(y_pct, float) and np.isnan(y_pct)):
                    self.player_stats_text.insert(tk.END, f"Field Position: ({x_pct:.1f}%, {y_pct:.1f}%)\n")
        
        if 'field_zone' in analytics:
            zone = analytics.get('field_zone')
            if zone and not (isinstance(zone, float) and np.isnan(zone)):
                self.player_stats_text.insert(tk.END, f"Field Zone: {zone}\n")
        
        # Other metrics
        if 'sprint_count' in analytics:
            sprints = analytics.get('sprint_count')
            if sprints is not None and not (isinstance(sprints, float) and np.isnan(sprints)):
                self.player_stats_text.insert(tk.END, f"Sprints: {int(sprints)}\n")
        
        if 'possession_time_s' in analytics:
            possession = analytics.get('possession_time_s')
            if possession is not None and not (isinstance(possession, float) and np.isnan(possession)):
                self.player_stats_text.insert(tk.END, f"Possession Time: {possession:.2f} s\n")
        
        if 'player_acceleration_fts2' in analytics or 'player_acceleration_ms2' in analytics:
            accel = analytics.get('player_acceleration_fts2') if use_imperial else analytics.get('player_acceleration_ms2')
            if accel is not None and not (isinstance(accel, float) and np.isnan(accel)):
                unit = "ft/s²" if use_imperial else "m/s²"
                self.player_stats_text.insert(tk.END, f"Acceleration: {accel:.2f} {unit}\n")
    
    def calculate_player_summary(self, all_analytics):
        """Calculate summary statistics for a player across all frames"""
        summary = {}
        use_imperial = hasattr(self, 'df') and self.df is not None and 'player_speed_mph' in self.df.columns
        
        # Speed summary
        speeds = []
        max_speeds = []
        avg_speeds = []
        for analytics in all_analytics:
            speed_key = 'player_speed_mph' if use_imperial else 'player_speed_mps'
            if speed_key in analytics:
                val = analytics[speed_key]
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    speeds.append(val)
            
            max_key = 'max_speed_mph' if use_imperial else 'max_speed_mps'
            if max_key in analytics:
                val = analytics[max_key]
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    max_speeds.append(val)
            
            avg_key = 'avg_speed_mph' if use_imperial else 'avg_speed_mps'
            if avg_key in analytics:
                val = analytics[avg_key]
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    avg_speeds.append(val)
        
        if speeds:
            summary['avg_speed'] = np.mean(speeds)
            summary['max_speed'] = np.max(speeds)
        if max_speeds:
            summary['overall_max_speed'] = np.max(max_speeds)
        if avg_speeds:
            summary['overall_avg_speed'] = np.mean(avg_speeds)
        
        # Distance summary
        distances = []
        for analytics in all_analytics:
            dist_key = 'distance_traveled_ft' if use_imperial else 'distance_traveled_m'
            if dist_key in analytics:
                val = analytics[dist_key]
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    distances.append(val)
        
        if distances:
            summary['total_distance'] = np.max(distances)  # Should be cumulative
            summary['avg_distance_per_frame'] = np.mean(distances)
        
        return summary
    
    def display_summary_stats(self, summary):
        """Display summary statistics"""
        use_imperial = hasattr(self, 'df') and self.df is not None and 'player_speed_mph' in self.df.columns
        unit_speed = "mph" if use_imperial else "m/s"
        unit_dist = "ft" if use_imperial else "m"
        
        self.player_stats_text.insert(tk.END, "--- Summary Statistics ---\n")
        
        if 'overall_max_speed' in summary:
            self.player_stats_text.insert(tk.END, f"Overall Max Speed: {summary['overall_max_speed']:.2f} {unit_speed}\n")
        if 'overall_avg_speed' in summary:
            self.player_stats_text.insert(tk.END, f"Overall Avg Speed: {summary['overall_avg_speed']:.2f} {unit_speed}\n")
        if 'total_distance' in summary:
            self.player_stats_text.insert(tk.END, f"Total Distance: {summary['total_distance']:.2f} {unit_dist}\n")
    
    def calculate_video_summary(self):
        """Calculate summary statistics for the entire video"""
        if not hasattr(self, 'analytics_data') or not self.analytics_data:
            return "Load CSV to see summary statistics"
        
        total_frames = len(self.analytics_data)
        total_players = set()
        for frame_data in self.analytics_data.values():
            total_players.update(frame_data.keys())
        
        summary = f"Total Frames: {total_frames}\n"
        summary += f"Unique Players: {len(total_players)}\n"
        summary += f"Players: {', '.join([f'#{pid}' for pid in sorted(total_players)])}"
        
        return summary
    
    def on_canvas2_release(self, event):
        """Handle release on canvas2"""
        self.is_panning2 = False
    
    def on_canvas2_wheel(self, event):
        """Handle mouse wheel on canvas2 (for zoom)"""
        if event.delta > 0 or event.num == 4:  # Zoom in
            self.zoom_canvas(2, 1.2)
        else:  # Zoom out
            self.zoom_canvas(2, 1/1.2)
    
    def calculate_ball_trajectory(self):
        """Calculate ball trajectory analytics (Kinovea-style)"""
        if not self.csv_path or not os.path.exists(self.csv_path):
            messagebox.showwarning("No CSV", "Please load a CSV file first")
            return
        
        try:
            from ball_analytics import BallAnalytics
            
            # Get FPS
            fps = self.fps if self.fps > 0 else 30.0
            
            # Initialize analytics
            self.ball_analytics = BallAnalytics(self.csv_path, fps=fps)
            
            # Load ball data
            ball_data = self.ball_analytics.load_ball_data()
            
            if not ball_data:
                messagebox.showwarning("No Ball Data", "No ball tracking data found in CSV")
                return
            
            # Calculate trajectory
            self.ball_trajectory = self.ball_analytics.calculate_trajectory_analytics(ball_data)
            
            if not self.ball_trajectory:
                messagebox.showwarning("Error", "Could not calculate trajectory")
                return
            
            # Update display
            self.update_ball_analytics_display()
            
            # Enable trajectory overlay
            self.show_ball_trajectory.set(True)
            
            messagebox.showinfo("Success", 
                              f"Ball trajectory calculated!\n"
                              f"Points: {len(self.ball_trajectory.frames)}\n"
                              f"Duration: {self.ball_trajectory.timestamps[-1] - self.ball_trajectory.timestamps[0]:.2f}s")
            
            # Update display to show trajectory
            self.update_display()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate trajectory: {e}")
            import traceback
            traceback.print_exc()
    
    def update_ball_analytics_display(self):
        """Update ball analytics display labels"""
        if not self.ball_trajectory or self.current_frame_num not in self.ball_trajectory.frames:
            # Try to find nearest frame
            if self.ball_trajectory:
                nearest_idx = None
                min_dist = float('inf')
                for i, frame in enumerate(self.ball_trajectory.frames):
                    dist = abs(frame - self.current_frame_num)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_idx = i
                
                if nearest_idx is not None and min_dist <= 10:  # Within 10 frames
                    idx = nearest_idx
                else:
                    # No nearby frame, clear display
                    if hasattr(self, 'ball_speed_label'):
                        self.ball_speed_label.config(text="Speed: -- m/s (-- mph)")
                    if hasattr(self, 'ball_distance_label'):
                        self.ball_distance_label.config(text="Distance: -- m (-- ft)")
                    if hasattr(self, 'ball_acceleration_label'):
                        self.ball_acceleration_label.config(text="Acceleration: -- m/s²")
                    return
            else:
                return
        else:
            idx = self.ball_trajectory.frames.index(self.current_frame_num)
        
        # Update labels
        speed = self.ball_trajectory.speeds[idx]
        distance = self.ball_trajectory.distances[idx] if idx < len(self.ball_trajectory.distances) else 0
        acceleration = self.ball_trajectory.accelerations[idx] if idx < len(self.ball_trajectory.accelerations) else 0
        
        if hasattr(self, 'ball_speed_label'):
            self.ball_speed_label.config(text=f"Speed: {speed:.2f} m/s ({speed*2.237:.1f} mph)")
        if hasattr(self, 'ball_distance_label'):
            self.ball_distance_label.config(text=f"Distance: {distance:.2f} m ({distance*3.281:.1f} ft)")
        if hasattr(self, 'ball_acceleration_label'):
            self.ball_acceleration_label.config(text=f"Acceleration: {acceleration:.2f} m/s²")
    
    def show_ball_trajectory_stats(self):
        """Show comprehensive ball trajectory statistics"""
        if not self.ball_trajectory:
            messagebox.showwarning("No Trajectory", "Please calculate trajectory first")
            return
        
        try:
            stats = self.ball_analytics.get_statistics(self.ball_trajectory)
            
            stats_text = f"""
Ball Trajectory Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Speed:
  Maximum: {stats['max_speed']:.2f} m/s ({stats['max_speed']*2.237:.1f} mph)
  Average: {stats['avg_speed']:.2f} m/s ({stats['avg_speed']*2.237:.1f} mph)
  Minimum: {stats['min_speed']:.2f} m/s ({stats['min_speed']*2.237:.1f} mph)

Distance:
  Total: {stats['total_distance']:.2f} m ({stats['total_distance']*3.281:.1f} ft)

Acceleration:
  Maximum: {stats['max_acceleration']:.2f} m/s²
  Average: {stats['avg_acceleration']:.2f} m/s²
  Minimum: {stats['min_acceleration']:.2f} m/s²

Duration: {stats['duration']:.2f} seconds
Data Points: {stats['num_points']} frames
"""
            
            # Update text widget
            if hasattr(self, 'ball_trajectory_stats_text'):
                self.ball_trajectory_stats_text.config(state=tk.NORMAL)
                self.ball_trajectory_stats_text.delete(1.0, tk.END)
                self.ball_trajectory_stats_text.insert(1.0, stats_text)
                self.ball_trajectory_stats_text.config(state=tk.DISABLED)
            
            # Also show in message box
            messagebox.showinfo("Ball Trajectory Statistics", stats_text)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show statistics: {e}")
            import traceback
            traceback.print_exc()
    
    def export_ball_trajectory(self):
        """Export ball trajectory in Kinovea-compatible format"""
        if not self.ball_trajectory:
            messagebox.showwarning("No Trajectory", "Please calculate trajectory first")
            return
        
        try:
            # Get output filename
            if self.csv_path:
                base_name = os.path.splitext(os.path.basename(self.csv_path))[0]
                default_filename = f"{base_name}_ball_trajectory.csv"
                default_dir = os.path.dirname(self.csv_path)
            else:
                default_filename = "ball_trajectory.csv"
                default_dir = os.getcwd()
            
            output_path = filedialog.asksaveasfilename(
                title="Export Ball Trajectory (Kinovea format)",
                defaultextension=".csv",
                initialfile=default_filename,
                initialdir=default_dir,
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if output_path:
                success = self.ball_analytics.export_kinovea_format(self.ball_trajectory, output_path)
                if success:
                    messagebox.showinfo("Success", f"Trajectory exported to:\n{output_path}")
                else:
                    messagebox.showerror("Error", "Failed to export trajectory")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _draw_ball_trajectory_overlay(self, display_frame, current_frame_num):
        """Draw Kinovea-style trajectory overlay with speed color coding"""
        if not self.ball_trajectory:
            return display_frame
        
        h, w = display_frame.shape[:2]
        
        # Draw trajectory path up to current frame
        for i in range(len(self.ball_trajectory.positions) - 1):
            frame1 = self.ball_trajectory.frames[i]
            frame2 = self.ball_trajectory.frames[i + 1]
            
            # Only draw if both frames are before or at current frame
            if frame2 <= current_frame_num:
                pos1 = self.ball_trajectory.positions[i]
                pos2 = self.ball_trajectory.positions[i + 1]
                
                # Scale coordinates if needed
                x1, y1 = float(pos1[0]), float(pos1[1])
                x2, y2 = float(pos2[0]), float(pos2[1])
                
                # Scale if needed (same logic as ball drawing)
                if hasattr(self, 'original_video_width') and hasattr(self, 'original_video_height') and self.original_video_width > 0 and self.original_video_height > 0:
                    scale_x = w / self.original_video_width if self.original_video_width != w else 1.0
                    scale_y = h / self.original_video_height if self.original_video_height != h else 1.0
                    if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                        x1, y1 = x1 * scale_x, y1 * scale_y
                        x2, y2 = x2 * scale_x, y2 * scale_y
                
                # Clamp to bounds
                x1 = int(max(0, min(x1, w - 1)))
                y1 = int(max(0, min(y1, h - 1)))
                x2 = int(max(0, min(x2, w - 1)))
                y2 = int(max(0, min(y2, h - 1)))
                
                # Color by speed if enabled
                if self.show_ball_speed_overlay.get() and i < len(self.ball_trajectory.speeds):
                    speed = self.ball_trajectory.speeds[i]
                    # Color scale: blue (slow) -> green -> yellow -> red (fast)
                    # 0 m/s = blue, 10 m/s = red
                    speed_normalized = min(1.0, speed / 10.0)
                    if speed_normalized < 0.33:
                        # Blue to green
                        r = int(0)
                        g = int(255 * (speed_normalized / 0.33))
                        b = int(255 * (1 - speed_normalized / 0.33))
                    elif speed_normalized < 0.67:
                        # Green to yellow
                        t = (speed_normalized - 0.33) / 0.34
                        r = int(255 * t)
                        g = 255
                        b = 0
                    else:
                        # Yellow to red
                        t = (speed_normalized - 0.67) / 0.33
                        r = 255
                        g = int(255 * (1 - t))
                        b = 0
                    color = (b, g, r)  # BGR format
                else:
                    color = (0, 255, 255)  # Yellow default
                
                # Draw line
                cv2.line(display_frame, (x1, y1), (x2, y2), color, 2)
        
        # Draw current position with speed indicator
        if current_frame_num in self.ball_trajectory.frames:
            idx = self.ball_trajectory.frames.index(current_frame_num)
            pos = self.ball_trajectory.positions[idx]
            speed = self.ball_trajectory.speeds[idx] if idx < len(self.ball_trajectory.speeds) else 0
            
            # Scale coordinates
            x, y = float(pos[0]), float(pos[1])
            if hasattr(self, 'original_video_width') and hasattr(self, 'original_video_height') and self.original_video_width > 0 and self.original_video_height > 0:
                scale_x = w / self.original_video_width if self.original_video_width != w else 1.0
                scale_y = h / self.original_video_height if self.original_video_height != h else 1.0
                if abs(scale_x - 1.0) > 0.1 or abs(scale_y - 1.0) > 0.1:
                    x, y = x * scale_x, y * scale_y
            
            x = int(max(0, min(x, w - 1)))
            y = int(max(0, min(y, h - 1)))
            
            # Draw speed text
            if self.show_ball_speed_overlay.get():
                speed_text = f"{speed:.1f} m/s"
                cv2.putText(display_frame, speed_text, (x + 15, y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(display_frame, speed_text, (x + 15, y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        
        return display_frame


def main():
    root = tk.Tk()
    app = PlaybackViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()

