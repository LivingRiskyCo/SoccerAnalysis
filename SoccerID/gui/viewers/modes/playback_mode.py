"""
Playback Mode - Video playback with CSV overlays and analytics
Migrated from PlaybackViewer with full features
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
import json
import threading
import time
from collections import OrderedDict
import pandas as pd
from ..unified_viewer import BaseMode

# Try to import HD renderer
try:
    current_file = __file__
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(current_file)))))
    hd_path = os.path.join(parent_dir, 'hd_overlay_renderer.py')
    if os.path.exists(hd_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("hd_overlay_renderer", hd_path)
        hd_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hd_module)
        HDOverlayRenderer = hd_module.HDOverlayRenderer
        HD_RENDERER_AVAILABLE = True
    else:
        from hd_overlay_renderer import HDOverlayRenderer
        HD_RENDERER_AVAILABLE = True
except ImportError:
    HD_RENDERER_AVAILABLE = False
    HDOverlayRenderer = None

# Try to import event marker system
try:
    current_file = __file__
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(current_file)))))
    marker_path = os.path.join(parent_dir, 'SoccerID', 'events', 'marker_system.py')
    if os.path.exists(marker_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("marker_system", marker_path)
        marker_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(marker_module)
        EventMarkerSystem = marker_module.EventMarkerSystem
        EVENT_MARKER_AVAILABLE = True
    else:
        from event_marker_system import EventMarkerSystem
        EVENT_MARKER_AVAILABLE = True
except ImportError:
    EVENT_MARKER_AVAILABLE = False
    EventMarkerSystem = None


class PlaybackMode(BaseMode):
    """Playback viewer mode - for reviewing tracking data with analytics"""
    
    def __init__(self, parent_frame, viewer, video_manager, detection_manager, 
                 reid_manager, gallery_manager, csv_manager, anchor_manager):
        # Initialize attributes BEFORE calling super (which calls create_ui)
        # Analytics data
        self.analytics_data = {}  # frame_num -> {player_id: {analytics_dict}}
        self.analytics_preferences = {}  # Will be loaded after UI creation
        
        # Analytics UI variables (initialized before create_ui)
        self.show_analytics = tk.BooleanVar(value=False)
        self.analytics_position = tk.StringVar(value="with_player")
        
        # Analytics font settings
        self.analytics_font_scale = tk.DoubleVar(value=1.0)
        self.analytics_font_thickness = tk.IntVar(value=2)
        self.analytics_font_face = tk.StringVar(value="FONT_HERSHEY_SIMPLEX")
        self.use_custom_analytics_color = tk.BooleanVar(value=True)
        self.analytics_color_rgb = tk.StringVar(value="255,255,255")
        self.analytics_color_r = tk.IntVar(value=255)
        self.analytics_color_g = tk.IntVar(value=255)
        self.analytics_color_b = tk.IntVar(value=255)
        
        # Analytics panel sizes
        self.analytics_banner_height = tk.IntVar(value=500)
        self.analytics_bar_width = tk.IntVar(value=250)
        self.analytics_panel_width = tk.IntVar(value=300)
        self.analytics_panel_height = tk.IntVar(value=200)
        
        # HD renderer
        if HD_RENDERER_AVAILABLE:
            self.hd_renderer = HDOverlayRenderer(render_scale=2.0, quality="hd", enable_advanced_blending=True)
        else:
            self.hd_renderer = None
        
        # Event marker system (initialize after super() to access video_manager)
        self.event_marker_system = None
        self.event_marker_visible = tk.BooleanVar(value=True)
        self.current_event_type = tk.StringVar(value="pass")
        
        # Frame buffering
        self.frame_buffer = OrderedDict()
        self.buffer_max_size = 240
        self.buffer_min_size = 80
        self.buffer_read_ahead = 120
        self.buffer_thread = None
        self.buffer_thread_running = False
        self.buffer_lock = threading.Lock()
        self.last_sequential_frame = -1
        
        # Playback state
        self.is_playing = False
        self.play_after_id = None
        self.playback_speed = 1.0
        
        # Team colors
        self.team_colors = None
        
        # Player column mapping for consistent banner layout
        self._player_column_map = {}
        self._column_player_map = {}
        
        # File watching for CSV auto-reload
        self.csv_last_modified = None
        self.watch_csv_enabled = tk.BooleanVar(value=True)
        self.watch_thread = None
        self.watch_running = False
        
        # UI variables that will be created in create_ui() - initialize as None for safety
        self.frame_var = None
        self.status_label = None
        self.frame_slider = None
        self.frame_label = None
        self.goto_frame_var = None
        self.goto_frame_entry = None
        self.speed_var = None
        self.buffer_status_label = None
        self.play_button = None
        self.canvas = None
        self.heatmap_player_combo = None  # Will be created in _create_analytics_tab
        
        # Window controls (needed in create_ui)
        self.always_on_top = tk.BooleanVar(value=False)
        self.is_maximized = False
        self.is_fullscreen = False
        
        # Player trails (needed in create_ui)
        self.show_player_trail = tk.BooleanVar(value=False)
        self.player_trail_length = tk.IntVar(value=30)
        self.player_trail_size = tk.IntVar(value=3)
        self.player_trail_fade = tk.BooleanVar(value=True)
        self.player_trails = {}  # player_id -> deque of positions
        
        # Lost track predictions (needed in create_ui)
        self.show_predicted_boxes = tk.BooleanVar(value=False)
        self.prediction_duration = tk.DoubleVar(value=1.5)
        self.prediction_size = tk.IntVar(value=5)
        self.prediction_style = tk.StringVar(value="dot")
        
        # Field zones (needed in create_ui)
        self.show_field_zones = tk.BooleanVar(value=False)
        
        # Ball trail (needed in create_ui)
        self.show_ball_trail = tk.BooleanVar(value=True)
        self.ball_trail = []  # List of recent ball positions
        
        # Overlay metadata (needed in create_ui)
        self.use_overlay_metadata = tk.BooleanVar(value=False)
        self.overlay_render_mode = tk.StringVar(value="csv")
        
        # Heatmaps (needed in create_ui)
        self.show_heatmap = tk.BooleanVar(value=False)
        self.heatmap_type = tk.StringVar(value="position")  # position, speed, acceleration, possession
        self.heatmap_opacity = tk.DoubleVar(value=0.5)
        self.heatmap_radius = tk.IntVar(value=30)
        self.heatmap_player_id = tk.StringVar(value="all")  # "all" or specific player ID
        self.heatmap_time_range = tk.IntVar(value=300)  # frames to include in heatmap
        
        # Overlay visibility toggles (needed in create_ui)
        self.show_players_var = tk.BooleanVar(value=True)
        self.show_ball_var = tk.BooleanVar(value=True)
        self.show_labels_var = tk.BooleanVar(value=True)
        self.show_trajectories_var = tk.BooleanVar(value=False)
        
        # Separate controls for boxes and circles (like legacy viewer)
        self.show_bounding_boxes = tk.BooleanVar(value=True)  # Show bounding boxes
        self.show_circles_at_feet = tk.BooleanVar(value=True)  # Show circles at feet
        
        # Player visualization style (needed in create_ui)
        self.player_viz_style = tk.StringVar(value="box")  # "box" or "circle"
        self.viz_color_mode = tk.StringVar(value="team")  # "team", "track", "custom"
        self.player_graphics_style = tk.StringVar(value="standard")  # "minimal", "standard", "broadcast"
        
        # Enhanced feet marker visualization (needed in create_ui)
        self.feet_marker_style = tk.StringVar(value="circle")  # "circle", "diamond", "star", "hexagon", "ring", "glow", "pulse"
        self.feet_marker_opacity = tk.IntVar(value=255)
        self.feet_marker_enable_glow = tk.BooleanVar(value=False)
        self.feet_marker_glow_intensity = tk.IntVar(value=70)
        self.feet_marker_enable_shadow = tk.BooleanVar(value=False)
        self.feet_marker_shadow_offset = tk.IntVar(value=3)
        self.feet_marker_shadow_opacity = tk.IntVar(value=128)
        self.feet_marker_enable_gradient = tk.BooleanVar(value=False)
        self.feet_marker_enable_pulse = tk.BooleanVar(value=False)
        self.feet_marker_pulse_speed = tk.DoubleVar(value=2.0)
        self.feet_marker_enable_particles = tk.BooleanVar(value=False)
        self.feet_marker_particle_count = tk.IntVar(value=5)
        self.feet_marker_vertical_offset = tk.IntVar(value=50)
        self.show_direction_arrow = tk.BooleanVar(value=False)
        
        # Ellipse visualization (for foot-based tracking)
        self.ellipse_width = tk.IntVar(value=20)
        self.ellipse_height = tk.IntVar(value=12)
        self.ellipse_outline_thickness = tk.IntVar(value=0)
        
        # Box appearance customization (needed in create_ui)
        self.box_shrink_factor = tk.DoubleVar(value=0.10)
        self.box_thickness = tk.IntVar(value=2)
        self.use_custom_box_color = tk.BooleanVar(value=False)
        self.box_color_rgb = tk.StringVar(value="0,255,0")
        self.box_color_r = tk.IntVar(value=0)
        self.box_color_g = tk.IntVar(value=255)
        self.box_color_b = tk.IntVar(value=0)
        self.player_viz_alpha = tk.IntVar(value=255)
        
        # Label customization (needed in create_ui)
        self.use_custom_label_color = tk.BooleanVar(value=False)
        self.label_color_rgb = tk.StringVar(value="255,255,255")
        self.label_color_r = tk.IntVar(value=255)
        self.label_color_g = tk.IntVar(value=255)
        self.label_color_b = tk.IntVar(value=255)
        self.label_font_scale = tk.DoubleVar(value=0.7)
        self.label_type = tk.StringVar(value="full_name")  # "full_name", "last_name", "jersey", "team", "custom"
        self.label_custom_text = tk.StringVar(value="Player")
        self.label_font_face = tk.StringVar(value="FONT_HERSHEY_SIMPLEX")
        
        # Prediction/decay visualization colors
        self.prediction_color_r = tk.IntVar(value=255)
        self.prediction_color_g = tk.IntVar(value=255)
        self.prediction_color_b = tk.IntVar(value=0)
        self.prediction_color_alpha = tk.IntVar(value=255)
        
        # Now call super (which will call create_ui)
        super().__init__(parent_frame, viewer, video_manager, detection_manager,
                        reid_manager, gallery_manager, csv_manager, anchor_manager)
        
        # Load analytics preferences after UI is created
        self.analytics_preferences = self.load_analytics_preferences()
        # Update show_analytics based on loaded preferences
        has_selections = len([k for k, v in self.analytics_preferences.items() if v]) > 0
        self.show_analytics.set(has_selections)
        
        # Load team colors after UI is created
        self.load_team_colors()
        
        # Initialize event marker system (now that video_manager is available)
        if EVENT_MARKER_AVAILABLE and hasattr(self.video_manager, 'video_path') and self.video_manager.video_path:
            try:
                self.event_marker_system = EventMarkerSystem(video_path=self.video_manager.video_path)
            except Exception as e:
                print(f"Warning: Could not initialize EventMarkerSystem: {e}")
                self.event_marker_system = None
        
        # Overlay metadata
        self.overlay_metadata = None
        self.overlay_renderer = None
        
        # Zoom/Pan
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        
        # Comparison mode
        self.comparison_mode = False
        self.frame1 = None
        self.frame2 = None
        self.id1 = None
        self.id2 = None
        self.canvas1 = None
        self.canvas2 = None
        self.comparison_window = None
        self.zoom_level1 = 1.0
        self.zoom_level2 = 1.0
        self.pan_x1 = 0
        self.pan_y1 = 0
        self.pan_x2 = 0
        self.pan_y2 = 0
        self.pan_start_x1 = 0
        self.pan_start_y1 = 0
        self.pan_start_x2 = 0
        self.pan_start_y2 = 0
        self.frame1_label = None
        self.frame2_label = None
        self.zoom_label1 = None
        self.zoom_label2 = None
        
        # Event timeline viewer
        self.event_timeline_viewer = None
        self.event_tracker = None
    
    def create_ui(self):
        """Create playback mode UI with tabbed interface"""
        # Main layout: video on left, controls on right
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top: File selection and window controls
        file_frame = ttk.LabelFrame(main_frame, text="File & Window Controls", padding="5")
        file_frame.pack(fill=tk.X, pady=5)
        
        # File operations
        file_buttons_frame = ttk.Frame(file_frame)
        file_buttons_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(file_buttons_frame, text="Load Video", command=self.load_video, width=18).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_buttons_frame, text="Load CSV", command=self.load_csv, width=18).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_buttons_frame, text="Load Metadata", command=self.load_metadata_manual, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_buttons_frame, text="Reload CSV", command=self.reload_csv, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_buttons_frame, text="Export Video", command=self.export_video, width=12).pack(side=tk.LEFT, padx=2)
        
        # Auto-reload checkbox
        ttk.Checkbutton(file_buttons_frame, text="Auto-reload CSV", variable=self.watch_csv_enabled).pack(side=tk.LEFT, padx=5)
        
        # Window controls
        window_controls_frame = ttk.Frame(file_frame)
        window_controls_frame.pack(side=tk.RIGHT, padx=5)
        
        ttk.Checkbutton(window_controls_frame, text="Always on Top", variable=self.always_on_top,
                       command=self.toggle_always_on_top).pack(side=tk.LEFT, padx=2)
        ttk.Button(window_controls_frame, text="Maximize", command=self.maximize_window, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(window_controls_frame, text="Minimize", command=self.minimize_window, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(window_controls_frame, text="Full Screen", command=self.toggle_fullscreen, width=10).pack(side=tk.LEFT, padx=2)
        
        # Playback controls bar (horizontal, above video display)
        playback_controls_bar = ttk.Frame(main_frame, padding="5")
        playback_controls_bar.pack(fill=tk.X, pady=(5, 0))
        
        # Play/Pause button
        if self.play_button is None:
            self.play_button = ttk.Button(playback_controls_bar, text="▶ Play", command=self.toggle_play, width=10)
            self.play_button.pack(side=tk.LEFT, padx=2)
        else:
            self.play_button.pack(side=tk.LEFT, padx=2)
        
        # First/Last frame buttons
        ttk.Button(playback_controls_bar, text="⏮ First", command=self.first_frame, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_controls_bar, text="⏭ Last", command=self.last_frame, width=12).pack(side=tk.LEFT, padx=2)
        
        # Previous/Next frame buttons
        ttk.Button(playback_controls_bar, text="◀◀", command=self.prev_frame, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_controls_bar, text="▶▶", command=self.next_frame, width=8).pack(side=tk.LEFT, padx=2)
        
        # Frame slider
        ttk.Label(playback_controls_bar, text="Frame:").pack(side=tk.LEFT, padx=(10, 2))
        if self.frame_var is None:
            self.frame_var = tk.IntVar()
        self.frame_slider = ttk.Scale(playback_controls_bar, from_=0, to=100, 
                                     orient=tk.HORIZONTAL, variable=self.frame_var,
                                     command=self.on_slider_change, length=200)
        self.frame_slider.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.frame_label = ttk.Label(playback_controls_bar, text="Frame: 0 / 0", width=15)
        self.frame_label.pack(side=tk.LEFT, padx=2)
        
        # Goto frame entry
        ttk.Label(playback_controls_bar, text="Goto:").pack(side=tk.LEFT, padx=(10, 2))
        if self.goto_frame_var is None:
            self.goto_frame_var = tk.StringVar()
        self.goto_frame_entry = ttk.Entry(playback_controls_bar, textvariable=self.goto_frame_var, width=8)
        self.goto_frame_entry.pack(side=tk.LEFT, padx=2)
        self.goto_frame_entry.bind("<Return>", lambda e: self.goto_frame())
        ttk.Button(playback_controls_bar, text="Go", command=self.goto_frame, width=4).pack(side=tk.LEFT, padx=2)
        
        # Speed control
        ttk.Label(playback_controls_bar, text="Speed:").pack(side=tk.LEFT, padx=(10, 2))
        if self.speed_var is None:
            self.speed_var = tk.DoubleVar(value=1.0)
        speed_spin = ttk.Spinbox(playback_controls_bar, from_=0.25, to=4.0, increment=0.25,
                                 textvariable=self.speed_var, width=8)
        speed_spin.pack(side=tk.LEFT, padx=2)
        self.speed_var.trace_add('write', lambda *args: self.update_speed())
        speed_spin.bind("<KeyRelease>", lambda e: self.update_speed())
        
        # Buffer status display
        ttk.Label(playback_controls_bar, text="Buffer:").pack(side=tk.LEFT, padx=(10, 2))
        self.buffer_status_label = ttk.Label(playback_controls_bar, text="0/0 frames", width=15, foreground="gray")
        self.buffer_status_label.pack(side=tk.LEFT, padx=2)
        
        # Middle: Video display and controls
        display_frame = ttk.Frame(main_frame)
        display_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Video canvas
        video_frame = ttk.Frame(display_frame)
        video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        if self.canvas is None:
            self.canvas = tk.Canvas(video_frame, bg='black')
            self.canvas.pack(fill=tk.BOTH, expand=True)
        else:
            self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_canvas_release)
        self.canvas.bind('<MouseWheel>', self.on_canvas_wheel)
        
        # Controls panel with tabs
        controls_panel_bg = tk.Frame(display_frame, width=400, bg="lightgray", relief=tk.RAISED, borderwidth=2)
        controls_panel_bg.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        controls_panel_bg.pack_propagate(False)
        
        # Create notebook for tabs
        self.controls_notebook = ttk.Notebook(controls_panel_bg)
        self.controls_notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Tab 1: Playback & Overlays
        playback_tab = ttk.Frame(self.controls_notebook, padding="5")
        self.controls_notebook.add(playback_tab, text="Playback & Overlays")
        
        # Tab 2: Visualization
        visualization_tab = ttk.Frame(self.controls_notebook, padding="5")
        self.controls_notebook.add(visualization_tab, text="Visualization")
        
        # Tab 3: Analytics
        analytics_tab = ttk.Frame(self.controls_notebook, padding="5")
        self.controls_notebook.add(analytics_tab, text="Analytics")
        
        # Create scrollable frames for tabs
        self._create_playback_tab(playback_tab)
        self._create_visualization_tab(visualization_tab)
        self._create_analytics_tab(analytics_tab)
        
        # Status label
        if self.status_label is None:
            self.status_label = ttk.Label(main_frame, text="Ready")
            self.status_label.pack(fill=tk.X, pady=5)
        else:
            self.status_label.pack(fill=tk.X, pady=5)
    
    def _create_playback_tab(self, parent):
        """Create Playback & Overlays tab content"""
        # Overlay toggles
        overlay_frame = ttk.LabelFrame(parent, text="Overlays", padding=5)
        overlay_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(overlay_frame, text="Show Players", 
                       variable=self.show_players_var,
                       command=self.update_display).pack(anchor=tk.W)
        
        ttk.Checkbutton(overlay_frame, text="Show Ball", 
                       variable=self.show_ball_var,
                       command=self.update_display).pack(anchor=tk.W)
        
        ttk.Checkbutton(overlay_frame, text="Show Ball Trail", 
                       variable=self.show_ball_trail,
                       command=self.update_display).pack(anchor=tk.W)
        
        ttk.Checkbutton(overlay_frame, text="Show Labels", 
                       variable=self.show_labels_var,
                       command=self.update_display).pack(anchor=tk.W)
        
        ttk.Checkbutton(overlay_frame, text="Show Trajectories", 
                       variable=self.show_trajectories_var,
                       command=self.update_display).pack(anchor=tk.W)
        
        ttk.Checkbutton(overlay_frame, text="Show Field Zones", 
                       variable=self.show_field_zones,
                       command=self.update_display).pack(anchor=tk.W)
        
        # Player trails
        trail_frame = ttk.LabelFrame(parent, text="Player Trails", padding=5)
        trail_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(trail_frame, text="Show Player Trails", 
                       variable=self.show_player_trail,
                       command=self.update_display).pack(anchor=tk.W)
        
        trail_settings_frame = ttk.Frame(trail_frame)
        trail_settings_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(trail_settings_frame, text="Length:").pack(side=tk.LEFT, padx=2)
        trail_length_spin = ttk.Spinbox(trail_settings_frame, from_=5, to=100, increment=5,
                                       textvariable=self.player_trail_length, width=8,
                                       command=self.update_display)
        trail_length_spin.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(trail_settings_frame, text="Size:").pack(side=tk.LEFT, padx=2)
        trail_size_spin = ttk.Spinbox(trail_settings_frame, from_=2, to=10, increment=1,
                                     textvariable=self.player_trail_size, width=8,
                                     command=self.update_display)
        trail_size_spin.pack(side=tk.LEFT, padx=2)
        
        ttk.Checkbutton(trail_frame, text="Fade older positions", 
                       variable=self.player_trail_fade,
                       command=self.update_display).pack(anchor=tk.W, pady=2)
        
        # Lost track predictions
        predicted_frame = ttk.LabelFrame(parent, text="Lost Track Predictions", padding=5)
        predicted_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(predicted_frame, text="Show Lost Track Predictions", 
                       variable=self.show_predicted_boxes,
                       command=self.update_display).pack(anchor=tk.W)
        
        pred_settings_frame = ttk.Frame(predicted_frame)
        pred_settings_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(pred_settings_frame, text="Duration (s):").pack(side=tk.LEFT, padx=2)
        pred_duration_spin = ttk.Spinbox(pred_settings_frame, from_=0.5, to=5.0, increment=0.1,
                                        textvariable=self.prediction_duration, width=8, format="%.1f",
                                        command=self.update_display)
        pred_duration_spin.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(pred_settings_frame, text="Style:").pack(side=tk.LEFT, padx=2)
        pred_style_combo = ttk.Combobox(pred_settings_frame, textvariable=self.prediction_style,
                                       values=["dot", "box", "cross", "x", "arrow", "diamond"],
                                       state="readonly", width=12)
        pred_style_combo.pack(side=tk.LEFT, padx=2)
        pred_style_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        ttk.Label(pred_settings_frame, text="Size:").pack(side=tk.LEFT, padx=2)
        pred_size_spin = ttk.Spinbox(pred_settings_frame, from_=3, to=20, increment=1,
                                    textvariable=self.prediction_size, width=8,
                                    command=self.update_display)
        pred_size_spin.pack(side=tk.LEFT, padx=2)
    
    def _create_visualization_tab(self, parent):
        """Create Visualization tab content"""
        # Zoom/Pan controls
        zoom_frame = ttk.LabelFrame(parent, text="Zoom & Pan", padding=5)
        zoom_frame.pack(fill=tk.X, pady=5)
        
        zoom_buttons = ttk.Frame(zoom_frame)
        zoom_buttons.pack(fill=tk.X, pady=2)
        ttk.Button(zoom_buttons, text="Zoom In (+)", command=lambda: self.zoom_single(1.2)).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_buttons, text="Zoom Out (-)", command=lambda: self.zoom_single(0.8)).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_buttons, text="Reset", command=self.reset_zoom_single).pack(side=tk.LEFT, padx=2)
        
        self.zoom_label = ttk.Label(zoom_frame, text="1.0x")
        self.zoom_label.pack(pady=2)
        
        ttk.Label(zoom_frame, text="Right-click and drag to pan", 
                 font=("Arial", 8), foreground="gray").pack(pady=2)
        
        # Event markers (if available)
        if EVENT_MARKER_AVAILABLE and self.event_marker_system:
            marker_frame = ttk.LabelFrame(parent, text="Event Markers", padding=5)
            marker_frame.pack(fill=tk.X, pady=5)
            
            ttk.Checkbutton(marker_frame, text="Show Markers", 
                           variable=self.event_marker_visible,
                           command=self.update_display).pack(anchor=tk.W)
            
            ttk.Label(marker_frame, text="Event Type:").pack(anchor=tk.W, pady=(5, 0))
            event_combo = ttk.Combobox(marker_frame, textvariable=self.current_event_type,
                                      values=["pass", "shot", "goal", "tackle", "save", "corner"],
                                      state='readonly', width=20)
            event_combo.pack(fill=tk.X, pady=2)
    
    def _create_analytics_tab(self, parent):
        """Create Analytics tab content"""
        # Analytics controls
        analytics_frame = ttk.LabelFrame(parent, text="Analytics Display", padding=5)
        analytics_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(analytics_frame, text="Show Analytics", 
                       variable=self.show_analytics,
                       command=self.update_display).pack(anchor=tk.W)
        
        ttk.Label(analytics_frame, text="Position:").pack(anchor=tk.W, pady=(5, 0))
        analytics_pos_combo = ttk.Combobox(analytics_frame, textvariable=self.analytics_position,
                                          values=["with_player", "top_left", "top_right", "bottom_left", 
                                                 "bottom_right", "top_banner", "bottom_banner", 
                                                 "left_bar", "right_bar"],
                                          state='readonly', width=20)
        analytics_pos_combo.pack(fill=tk.X, pady=2)
        analytics_pos_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        ttk.Button(analytics_frame, text="Select Analytics...", 
                  command=self.open_analytics_selection).pack(fill=tk.X, pady=2)
        
        # Analytics font settings
        font_frame = ttk.LabelFrame(parent, text="Font Settings", padding=5)
        font_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(font_frame, text="Font Scale:").pack(anchor=tk.W)
        font_scale_spin = ttk.Spinbox(font_frame, from_=0.5, to=3.0, increment=0.1,
                                     textvariable=self.analytics_font_scale, width=10,
                                     command=self.update_display)
        font_scale_spin.pack(fill=tk.X, pady=2)
        
        ttk.Label(font_frame, text="Font Thickness:").pack(anchor=tk.W)
        font_thickness_spin = ttk.Spinbox(font_frame, from_=1, to=5, increment=1,
                                         textvariable=self.analytics_font_thickness, width=10,
                                         command=self.update_display)
        font_thickness_spin.pack(fill=tk.X, pady=2)
        
        # Analytics panel sizes
        size_frame = ttk.LabelFrame(parent, text="Panel Sizes", padding=5)
        size_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(size_frame, text="Banner Height:").pack(anchor=tk.W)
        banner_height_spin = ttk.Spinbox(size_frame, from_=50, to=500, increment=10,
                                        textvariable=self.analytics_banner_height, width=10,
                                        command=self.update_display)
        banner_height_spin.pack(fill=tk.X, pady=2)
        
        ttk.Label(size_frame, text="Bar Width:").pack(anchor=tk.W)
        bar_width_spin = ttk.Spinbox(size_frame, from_=100, to=500, increment=10,
                                     textvariable=self.analytics_bar_width, width=10,
                                     command=self.update_display)
        bar_width_spin.pack(fill=tk.X, pady=2)
        
        # Heatmaps
        heatmap_frame = ttk.LabelFrame(parent, text="Heatmaps", padding=5)
        heatmap_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(heatmap_frame, text="Show Heatmap", 
                       variable=self.show_heatmap,
                       command=self.update_display).pack(anchor=tk.W)
        
        ttk.Label(heatmap_frame, text="Type:").pack(anchor=tk.W, pady=(5, 0))
        heatmap_type_combo = ttk.Combobox(heatmap_frame, textvariable=self.heatmap_type,
                                         values=["position", "speed", "acceleration", "possession"],
                                         state='readonly', width=20)
        heatmap_type_combo.pack(fill=tk.X, pady=2)
        heatmap_type_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        ttk.Label(heatmap_frame, text="Player:").pack(anchor=tk.W, pady=(5, 0))
        self.heatmap_player_combo = ttk.Combobox(heatmap_frame, textvariable=self.heatmap_player_id,
                                                 values=["all"], state='readonly', width=20)
        self.heatmap_player_combo.pack(fill=tk.X, pady=2)
        self.heatmap_player_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        ttk.Label(heatmap_frame, text="Opacity:").pack(anchor=tk.W, pady=(5, 0))
        heatmap_opacity_spin = ttk.Spinbox(heatmap_frame, from_=0.1, to=1.0, increment=0.1,
                                          textvariable=self.heatmap_opacity, width=10, format="%.1f",
                                          command=self.update_display)
        heatmap_opacity_spin.pack(fill=tk.X, pady=2)
        
        ttk.Label(heatmap_frame, text="Radius:").pack(anchor=tk.W, pady=(5, 0))
        heatmap_radius_spin = ttk.Spinbox(heatmap_frame, from_=10, to=100, increment=5,
                                         textvariable=self.heatmap_radius, width=10,
                                         command=self.update_display)
        heatmap_radius_spin.pack(fill=tk.X, pady=2)
        
        ttk.Label(heatmap_frame, text="Time Range (frames):").pack(anchor=tk.W, pady=(5, 0))
        heatmap_range_spin = ttk.Spinbox(heatmap_frame, from_=30, to=1000, increment=30,
                                         textvariable=self.heatmap_time_range, width=10,
                                         command=self.update_display)
        heatmap_range_spin.pack(fill=tk.X, pady=2)
        
        # Event Timeline Viewer
        event_timeline_frame = ttk.LabelFrame(parent, text="Event Timeline", padding=5)
        event_timeline_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(event_timeline_frame, text="📊 Open Event Timeline", 
                  command=self.open_event_timeline).pack(fill=tk.X, pady=2)
        
        # Comparison Mode
        comparison_frame = ttk.LabelFrame(parent, text="Comparison Mode", padding=5)
        comparison_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(comparison_frame, text="🔍 Open Comparison Mode", 
                  command=self.open_comparison_dialog).pack(fill=tk.X, pady=2)
        
        ttk.Label(comparison_frame, 
                 text="Compare two frames side-by-side with independent zoom/pan",
                 font=("Arial", 8), foreground="gray", wraplength=300).pack(pady=2)
    
    def display_frame(self, frame: np.ndarray, frame_num: int):
        """Display a frame with overlays and analytics"""
        if frame is None:
            return
        
        display_frame = frame.copy()
        
        # Apply zoom/pan if needed
        if self.zoom_level != 1.0 or self.pan_x != 0 or self.pan_y != 0:
            display_frame = self.apply_zoom_pan_single(display_frame)
        
        # Draw CSV overlays if available
        if self.csv_manager.is_loaded():
            # Draw player trails first (behind players)
            if self.show_player_trail.get():
                display_frame = self.draw_player_trails(display_frame, frame_num)
            
            # Draw ball trail
            if self.show_ball_trail.get():
                display_frame = self.draw_ball_trail(display_frame, frame_num)
            
            # Draw players with full visualization options
            if self.show_players_var.get():
                display_frame = self.draw_players_with_visualization(display_frame, frame_num)
            
            # Draw ball
            if self.show_ball_var.get():
                ball_data = self.csv_manager.get_ball_data(frame_num)
                if ball_data:
                    ball_x, ball_y, normalized = ball_data
                    if normalized:
                        ball_x = int(ball_x * self.video_manager.width)
                        ball_y = int(ball_y * self.video_manager.height)
                    cv2.circle(display_frame, (int(ball_x), int(ball_y)), 8, (0, 0, 255), -1)
            
            # Draw trajectories
            if self.show_trajectories_var.get():
                display_frame = self.draw_trajectories(display_frame, frame_num)
            
            # Draw field zones (placeholder - would need field calibration data)
            if self.show_field_zones.get():
                # Field zones drawing would go here
                pass
            
            # Draw heatmap
            if self.show_heatmap.get():
                display_frame = self.draw_heatmap(display_frame, frame_num)
        
        # Render analytics
        if self.show_analytics.get() and self.analytics_data:
            display_frame = self.render_analytics(display_frame, frame_num)
        
        # Draw event markers
        if self.event_marker_system and self.event_marker_visible.get():
            display_frame = self.draw_event_markers(display_frame, frame_num)
        
        # Display
        self._display_image(display_frame)
    
    def apply_zoom_pan_single(self, frame):
        """Apply zoom and pan to frame"""
        if self.zoom_level == 1.0 and self.pan_x == 0 and self.pan_y == 0:
            return frame
        
        h, w = frame.shape[:2]
        new_w = int(w * self.zoom_level)
        new_h = int(h * self.zoom_level)
        
        zoomed = cv2.resize(frame, (new_w, new_h))
        
        crop_x = int((new_w - w) / 2 - self.pan_x)
        crop_y = int((new_h - h) / 2 - self.pan_y)
        
        crop_x = max(0, min(crop_x, new_w - w))
        crop_y = max(0, min(crop_y, new_h - h))
        
        if crop_x + w <= new_w and crop_y + h <= new_h:
            cropped = zoomed[crop_y:crop_y+h, crop_x:crop_x+w]
        else:
            cropped = frame
        
        return cropped
    
    def render_analytics(self, display_frame: np.ndarray, frame_num: int) -> np.ndarray:
        """Render analytics overlay"""
        if not self.show_analytics.get() or not self.analytics_data:
            return display_frame
        
        # Find nearest frame with analytics
        if frame_num not in self.analytics_data:
            nearest_frame = None
            min_distance = float('inf')
            for existing_frame in self.analytics_data.keys():
                distance = abs(existing_frame - frame_num)
                if distance < min_distance and distance <= 5:
                    min_distance = distance
                    nearest_frame = existing_frame
            if nearest_frame is not None:
                frame_num = nearest_frame
            else:
                return display_frame
        
        if not self.analytics_data[frame_num]:
            return display_frame
        
        position = self.analytics_position.get()
        
        if position == "with_player":
            # Render with each player
            player_data = self.csv_manager.get_player_data(frame_num)
            for player_id, (x, y, team, name, bbox) in player_data.items():
                player_id_int = int(player_id)
                if player_id_int in self.analytics_data[frame_num]:
                    # Convert coordinates
                    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                        x = int(x * self.video_manager.width)
                        y = int(y * self.video_manager.height)
                    
                    # Get analytics text
                    use_imperial = 'player_speed_mph' in self.csv_manager.df.columns if self.csv_manager.df is not None else False
                    analytics_lines = self.get_analytics_text(player_id_int, frame_num, use_imperial)
                    
                    if analytics_lines:
                        # Draw background
                        font_scale = self.analytics_font_scale.get() * 0.7
                        thickness = self.analytics_font_thickness.get()
                        font_face_str = self.analytics_font_face.get()
                        font_face = getattr(cv2, font_face_str, cv2.FONT_HERSHEY_SIMPLEX)
                        
                        (text_width, text_height), _ = cv2.getTextSize(analytics_lines[0], font_face, font_scale, thickness)
                        max_line_width = 0
                        for line in analytics_lines:
                            (w, h), _ = cv2.getTextSize(line, font_face, font_scale, thickness)
                            max_line_width = max(max_line_width, w)
                        
                        rect_x1 = int(x) + 40
                        rect_y1 = int(y) + 20
                        rect_x2 = rect_x1 + max_line_width + 8
                        rect_y2 = rect_y1 + len(analytics_lines) * (text_height + 5) + 2
                        
                        h, w = display_frame.shape[:2]
                        rect_x1 = max(0, min(rect_x1, w - 1))
                        rect_y1 = max(0, min(rect_y1, h - 1))
                        rect_x2 = max(rect_x1 + 1, min(rect_x2, w))
                        rect_y2 = max(rect_y1 + 1, min(rect_y2, h))
                        
                        if rect_x2 > rect_x1 and rect_y2 > rect_y1:
                            overlay = display_frame.copy()
                            cv2.rectangle(overlay, (rect_x1, rect_y1), (rect_x2, rect_y2), (0, 0, 0), -1)
                            cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
                        
                        # Draw text
                        analytics_color = self._get_analytics_color_bgr()
                        for i, line in enumerate(analytics_lines[:5]):
                            text_y = int(y) + 20 + i * (text_height + 5)
                            cv2.putText(display_frame, line, (int(x) + 44, text_y),
                                       font_face, font_scale, analytics_color, thickness)
                            # Draw outline for contrast
                            cv2.putText(display_frame, line, (int(x) + 44, text_y),
                                       font_face, font_scale, (0, 0, 0), thickness + 1)
        else:
            # Render in panel/banner/bar
            display_frame = self._render_analytics_panel(display_frame, frame_num, position)
        
        return display_frame
    
    def _render_analytics_panel(self, display_frame: np.ndarray, frame_num: int, position: str) -> np.ndarray:
        """Render analytics in a panel/banner/bar"""
        if not self.show_analytics.get() or frame_num not in self.analytics_data:
            return display_frame
        
        h, w = display_frame.shape[:2]
        use_imperial = 'player_speed_mph' in self.csv_manager.df.columns if self.csv_manager.df is not None else False
        
        # Collect analytics for all players
        all_analytics = []
        for player_id, analytics_dict in self.analytics_data[frame_num].items():
            player_id_int = int(player_id)
            
            # Get player name
            player_name = f"Player #{player_id_int}"
            player_data = self.csv_manager.get_player_data(frame_num)
            if player_id_int in player_data:
                player_info = player_data[player_id_int]
                if len(player_info) >= 4:
                    player_name = player_info[3]
            
            # Get player team and color
            player_team = None
            if player_id_int in player_data and len(player_data[player_id_int]) >= 3:
                player_team = player_data[player_id_int][2]
            
            player_color = self.get_player_color(player_id_int, player_team, player_name)
            
            # Get analytics text
            analytics_lines = self.get_analytics_text(player_id_int, frame_num, use_imperial)
            if analytics_lines:
                all_analytics.append((player_name, analytics_lines, player_color, player_id_int))
        
        if not all_analytics:
            return display_frame
        
        # Sort by player ID for consistent ordering
        all_analytics.sort(key=lambda x: x[3])
        
        # Calculate position and size
        position = position.lower()
        banner_height = min(self.analytics_banner_height.get(), h - 20)
        bar_width = min(self.analytics_bar_width.get(), w - 20)
        panel_width = min(self.analytics_panel_width.get(), w - 20)
        panel_height = min(self.analytics_panel_height.get(), h - 20)
        
        if position == "top_banner":
            pos = (0, 0)
            panel_size = (w, banner_height)
        elif position == "bottom_banner":
            pos = (0, h - banner_height)
            panel_size = (w, banner_height)
        elif position == "left_bar":
            pos = (0, 0)
            panel_size = (bar_width, h)
        elif position == "right_bar":
            pos = (w - bar_width, 0)
            panel_size = (bar_width, h)
        elif position == "top_left":
            pos = (10, 10)
            panel_size = (panel_width, panel_height)
        elif position == "top_right":
            pos = (w - panel_width - 10, 10)
            panel_size = (panel_width, panel_height)
        elif position == "bottom_left":
            pos = (10, h - panel_height - 10)
            panel_size = (panel_width, panel_height)
        else:  # bottom_right
            pos = (w - panel_width - 10, h - panel_height - 10)
            panel_size = (panel_width, panel_height)
        
        # Draw background
        overlay = display_frame.copy()
        cv2.rectangle(overlay, pos, (pos[0] + panel_size[0], pos[1] + panel_size[1]), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
        
        # Draw analytics
        font_scale = self.analytics_font_scale.get()
        thickness = self.analytics_font_thickness.get()
        font_face_str = self.analytics_font_face.get()
        font_face = getattr(cv2, font_face_str, cv2.FONT_HERSHEY_SIMPLEX)
        
        (text_width, text_height), _ = cv2.getTextSize("Test", font_face, font_scale, thickness)
        line_height = text_height + 10
        
        analytics_color = self._get_analytics_color_bgr()
        text_x = pos[0] + 10
        text_y = pos[1] + 25
        
        # Draw title for panels
        if position not in ["top_banner", "bottom_banner"]:
            title = "Player Analytics"
            cv2.putText(display_frame, title, (text_x, text_y), font_face, font_scale * 1.2, 
                       (255, 255, 0), thickness + 1)
            text_y += 25
        
        # Draw analytics for each player
        max_players = 8 if position in ["top_banner", "bottom_banner"] else 10
        players_to_draw = all_analytics[:max_players]
        
        if position == "bottom_banner":
            # Horizontal layout for bottom banner
            num_players = len(players_to_draw)
            if num_players > 0:
                column_width = panel_size[0] // num_players
                for i, (player_name, analytics_lines, player_color, player_id) in enumerate(players_to_draw):
                    column_x = pos[0] + i * column_width + 10
                    column_y = pos[1] + 10
                    
                    # Draw player name with color
                    name_text = f"{player_name}:"
                    cv2.putText(display_frame, name_text, (column_x, column_y), font_face, font_scale,
                               player_color, thickness)
                    
                    # Draw analytics lines
                    for j, line in enumerate(analytics_lines[:3]):  # Limit to 3 lines per player
                        line_y = column_y + (j + 1) * line_height
                        if line_y > pos[1] + panel_size[1] - 10:
                            break
                        cv2.putText(display_frame, line, (column_x, line_y), font_face, font_scale * 0.9,
                                   analytics_color, thickness)
        
        elif position == "top_banner":
            # Horizontal layout for top banner (same as bottom banner)
            num_players = len(players_to_draw)
            if num_players > 0:
                column_width = panel_size[0] // num_players
                for i, (player_name, analytics_lines, player_color, player_id) in enumerate(players_to_draw):
                    column_x = pos[0] + i * column_width + 10
                    column_y = pos[1] + 10
                    
                    # Draw player name with color
                    name_text = f"{player_name}:"
                    cv2.putText(display_frame, name_text, (column_x, column_y), font_face, font_scale,
                               player_color, thickness)
                    
                    # Draw analytics lines
                    for j, line in enumerate(analytics_lines[:3]):  # Limit to 3 lines per player
                        line_y = column_y + (j + 1) * line_height
                        if line_y > pos[1] + panel_size[1] - 10:
                            break
                        cv2.putText(display_frame, line, (column_x, line_y), font_face, font_scale * 0.9,
                                   analytics_color, thickness)
        
        else:
            # Vertical layout for panels/bars (left_bar, right_bar, corner panels)
            for i, (player_name, analytics_lines, player_color, player_id) in enumerate(players_to_draw):
                # Calculate spacing - ensure enough room for analytics to not overlap
                lines_per_player = min(len(analytics_lines), 3)
                player_height = (lines_per_player + 1) * line_height + 20  # Name + lines + spacing
                
                # Check if we have room
                if text_y + player_height > pos[1] + panel_size[1] - 10:
                    break
                
                # Draw player name with color
                name_text = f"{player_name}:"
                cv2.putText(display_frame, name_text, (text_x, text_y), font_face, font_scale,
                           player_color, thickness)
                
                # Draw analytics lines
                for j, line in enumerate(analytics_lines[:3]):  # Limit to 3 lines per player
                    line_y = text_y + (j + 1) * line_height
                    if line_y > pos[1] + panel_size[1] - 10:
                        break
                    cv2.putText(display_frame, line, (text_x + 10, line_y), font_face, font_scale * 0.9,
                               analytics_color, thickness)
                
                # Move to next player with proper spacing
                text_y += player_height
        
        return display_frame
    
    def get_analytics_text(self, player_id: int, frame_num: int, use_imperial: bool = False) -> list:
        """Get formatted analytics text for a player"""
        if frame_num not in self.analytics_data or player_id not in self.analytics_data[frame_num]:
            return []
        
        analytics = self.analytics_data[frame_num][player_id]
        lines = []
        
        # Preference to column mapping
        preference_to_column = {
            'current_speed': ['player_speed_mph', 'player_speed_mps'] if use_imperial else ['player_speed_mps', 'player_speed_mph'],
            'average_speed': ['avg_speed_mph', 'avg_speed_mps'] if use_imperial else ['avg_speed_mps', 'avg_speed_mph'],
            'max_speed': ['max_speed_mph', 'max_speed_mps'] if use_imperial else ['max_speed_mps', 'max_speed_mph'],
            'acceleration': ['player_acceleration_fts2', 'player_acceleration_mps2'] if use_imperial else ['player_acceleration_mps2', 'player_acceleration_fts2'],
            'distance_to_ball': ['distance_to_ball_px'],
            'distance_traveled': ['distance_traveled_ft', 'distance_traveled_m'] if use_imperial else ['distance_traveled_m', 'distance_traveled_ft'],
            'field_zone': ['field_zone'],
            'possession_time': ['possession_time_s'],
        }
        
        display_labels = {
            'current_speed': 'Speed',
            'average_speed': 'Avg Speed',
            'max_speed': 'Max Speed',
            'acceleration': 'Accel',
            'distance_to_ball': 'Dist to Ball',
            'distance_traveled': 'Distance',
            'field_zone': 'Zone',
            'possession_time': 'Possession',
        }
        
        for pref_key, enabled in self.analytics_preferences.items():
            if not enabled:
                continue
            
            value = None
            for col in preference_to_column.get(pref_key, []):
                if col in analytics:
                    value = analytics[col]
                    break
            
            if value is not None:
                # Skip zero values for speed/acceleration
                if pref_key in ['current_speed', 'average_speed', 'max_speed', 'acceleration']:
                    if isinstance(value, (int, float)) and abs(value) < 0.01:
                        continue
                
                formatted = self.format_analytics_value(pref_key, value, use_imperial)
                if formatted:
                    label = display_labels.get(pref_key, pref_key)
                    lines.append(f"{label}: {formatted}")
        
        return lines
    
    def format_analytics_value(self, pref_key: str, value, use_imperial: bool) -> str:
        """Format analytics value for display"""
        if value is None:
            return ""
        
        if pref_key in ['current_speed', 'average_speed', 'max_speed']:
            if use_imperial:
                return f"{value:.1f} mph"
            else:
                return f"{value:.2f} m/s"
        elif pref_key == 'acceleration':
            if use_imperial:
                return f"{value:.1f} ft/s²"
            else:
                return f"{value:.2f} m/s²"
        elif pref_key == 'distance_to_ball':
            return f"{value:.0f} px"
        elif pref_key == 'distance_traveled':
            if use_imperial:
                return f"{value:.1f} ft"
            else:
                return f"{value:.2f} m"
        elif pref_key == 'possession_time':
            return f"{value:.1f} s"
        else:
            return str(value)
    
    def draw_trajectories(self, display_frame: np.ndarray, frame_num: int) -> np.ndarray:
        """Draw player trajectories"""
        if not self.csv_manager.is_loaded():
            return display_frame
        
        # Draw trajectory for last 30 frames
        trajectory_length = 30
        start_frame = max(0, frame_num - trajectory_length)
        
        for player_id in self.csv_manager.player_data.get(frame_num, {}).keys():
            trajectory_points = []
            for f in range(start_frame, frame_num + 1):
                player_data = self.csv_manager.get_player_data(f)
                if player_id in player_data:
                    x, y, team, name, bbox = player_data[player_id]
                    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                        x = int(x * self.video_manager.width)
                        y = int(y * self.video_manager.height)
                    trajectory_points.append((int(x), int(y)))
            
            if len(trajectory_points) > 1:
                # Draw trajectory line
                color = self.get_player_color(int(player_id), team, name)
                for i in range(len(trajectory_points) - 1):
                    alpha = i / len(trajectory_points)  # Fade effect
                    thickness = max(1, int(3 * alpha))
                    cv2.line(display_frame, trajectory_points[i], trajectory_points[i + 1], 
                            color, thickness)
        
        return display_frame
    
    def draw_event_markers(self, display_frame: np.ndarray, frame_num: int) -> np.ndarray:
        """Draw event markers on frame"""
        if not self.event_marker_system:
            return display_frame
        
        # Get events for this frame (within ±2 frames tolerance)
        tolerance = 2
        events = self.event_marker_system.get_markers_in_range(
            max(0, frame_num - tolerance), 
            frame_num + tolerance
        )
        
        h, w = display_frame.shape[:2]
        
        for marker in events:
            # Get position from marker (if available)
            if marker.position:
                # Position is in normalized coordinates (0-1)
                x = int(marker.position[0] * w)
                y = int(marker.position[1] * h)
            else:
                # Default to center if no position
                x, y = w // 2, h // 2
            
            # Draw marker circle
            color = (0, 255, 255)  # Cyan
            cv2.circle(display_frame, (x, y), 15, color, 3)
            
            # Draw event type text
            event_type_str = marker.event_type.value.upper() if hasattr(marker.event_type, 'value') else str(marker.event_type).upper()
            cv2.putText(display_frame, event_type_str, (x + 20, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return display_frame
    
    def get_player_color(self, player_id: int, team: str, name: str) -> tuple:
        """Get color for a player based on viz_color_mode setting"""
        color_mode = self.viz_color_mode.get()
        
        # Track mode: Use track ID based colors
        if color_mode == "track":
            colors = [
                (0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0),
                (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 165, 0),
                (255, 192, 203), (0, 255, 127), (255, 140, 0), (138, 43, 226),
                (255, 20, 147), (0, 191, 255), (255, 215, 0), (50, 205, 50)
            ]
            return colors[player_id % len(colors)]
        
        # Custom mode: Use custom box color if enabled, otherwise default
        if color_mode == "custom":
            if self.use_custom_box_color.get():
                return (self.box_color_b.get(), self.box_color_g.get(), self.box_color_r.get())
            # Fall through to default colors
        
        # Team mode (default): Use team colors if available
        if self.team_colors:
            team_name_lower = (team or "").lower()
            for team_key in ["team1", "team2"]:
                team_data = self.team_colors.get('team_colors', {}).get(team_key, {})
                if team_data.get('name', '').lower() == team_name_lower:
                    tracker_color = team_data.get('tracker_color_bgr')
                    if tracker_color:
                        return tuple(tracker_color[:3])
        
        # Default colors (fallback)
        colors = [
            (0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0),
            (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 165, 0)
        ]
        return colors[player_id % len(colors)]
    
    def _get_analytics_color_bgr(self) -> tuple:
        """Get analytics color in BGR format"""
        if self.use_custom_analytics_color.get():
            return (self.analytics_color_b.get(), self.analytics_color_g.get(), self.analytics_color_r.get())
        return (255, 255, 255)  # White default
    
    def load_analytics_preferences(self) -> dict:
        """Load analytics preferences from file"""
        prefs_file = "analytics_preferences.json"
        if os.path.exists(prefs_file):
            try:
                with open(prefs_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Default preferences
        return {
            'current_speed': True,
            'average_speed': False,
            'max_speed': False,
            'acceleration': False,
            'distance_to_ball': True,
            'distance_traveled': False,
            'field_zone': True,
            'possession_time': False,
        }
    
    def load_team_colors(self):
        """Load team colors"""
        team_colors_file = "team_color_config.json"
        if os.path.exists(team_colors_file):
            try:
                with open(team_colors_file, 'r') as f:
                    self.team_colors = json.load(f)
            except:
                self.team_colors = None
    
    def open_analytics_selection(self):
        """Open analytics selection window"""
        try:
            from analytics_selection_gui import AnalyticsSelectionGUI
            
            def apply_callback(preferences):
                self.analytics_preferences = preferences
                has_selections = len([k for k, v in preferences.items() if v]) > 0
                self.show_analytics.set(has_selections)
                self.update_display()
            
            analytics_window = AnalyticsSelectionGUI(self.viewer.root, apply_callback=apply_callback)
        except ImportError:
            messagebox.showwarning("Warning", "Analytics selection GUI not available")
    
    def _display_image(self, frame: np.ndarray):
        """Display image on canvas"""
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            self.canvas.update_idletasks()
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return
        
        scale = min(canvas_width / frame.shape[1], canvas_height / frame.shape[0])
        new_width = int(frame.shape[1] * scale)
        new_height = int(frame.shape[0] * scale)
        
        resized = cv2.resize(frame, (new_width, new_height))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        photo = ImageTk.PhotoImage(image=img)
        
        self.canvas.delete("all")
        self.canvas.create_image(canvas_width // 2, canvas_height // 2, 
                                image=photo, anchor=tk.CENTER)
        self.canvas.image = photo
    
    def toggle_play(self):
        """Toggle playback"""
        if not self.video_manager.cap:
            return
        
        self.is_playing = not self.is_playing
        
        if self.is_playing:
            self.play_button.config(text="⏸ Pause")
            # Ensure buffer thread is running
            if not self.buffer_thread_running:
                self.start_buffer_thread()
            self.play()
        else:
            self.play_button.config(text="▶ Play")
            if self.play_after_id:
                self.viewer.root.after_cancel(self.play_after_id)
                self.play_after_id = None
            # Don't stop buffer thread when paused - keep it running for smooth navigation
            # Buffer thread will continue buffering nearby frames even when paused
    
    def play(self):
        """Play video"""
        if not self.is_playing:
            return
        
        if self.viewer.current_frame_num >= self.video_manager.total_frames - 1:
            self.is_playing = False
            self.play_button.config(text="▶ Play")
            return
        
        self.next_frame()
        
        # Schedule next frame
        delay = int(1000 / (self.video_manager.fps * self.playback_speed))
        self.play_after_id = self.viewer.root.after(delay, self.play)
    
    def start_buffer_thread(self):
        """Start frame buffering thread"""
        if self.buffer_thread_running:
            return
        
        self.buffer_thread_running = True
        self.buffer_thread = threading.Thread(target=self._buffer_worker, daemon=True)
        self.buffer_thread.start()
    
    def stop_buffer_thread(self):
        """Stop frame buffering thread"""
        self.buffer_thread_running = False
        if self.buffer_thread:
            self.buffer_thread.join(timeout=2.0)  # Increased timeout for cleanup
        # Clear buffer after thread stops
        with self.buffer_lock:
            self.frame_buffer.clear()
    
    def _buffer_worker(self):
        """Background frame buffering"""
        # Use a separate VideoCapture instance for this thread to avoid conflicts
        buffer_cap = None
        try:
            if not self.video_manager.video_path:
                return
            
            buffer_cap = cv2.VideoCapture(self.video_manager.video_path)
            if not buffer_cap.isOpened():
                return
            
            while self.buffer_thread_running and self.video_manager.cap:
                try:
                    current_frame = self.viewer.current_frame_num
                    
                    # Buffer multiple frames ahead for smooth playback
                    frames_to_buffer = []
                    if self.is_playing:
                        # When playing, buffer ahead more aggressively
                        for offset in range(1, self.buffer_read_ahead + 1):
                            target_frame = current_frame + offset
                            if target_frame < self.video_manager.total_frames:
                                frames_to_buffer.append(target_frame)
                    else:
                        # When paused, buffer nearby frames for smooth navigation
                        # Buffer more frames when paused to ensure smooth navigation
                        buffer_range = min(self.buffer_read_ahead, 50)  # Buffer up to 50 frames when paused
                        for offset in range(1, buffer_range + 1):
                            target_frame = current_frame + offset
                            if target_frame < self.video_manager.total_frames:
                                frames_to_buffer.append(target_frame)
                    
                    # Also buffer frames behind for rewind (more when paused)
                    rewind_range = 50 if not self.is_playing else 30  # Buffer more frames behind when paused
                    for offset in range(1, min(rewind_range, current_frame) + 1):
                        target_frame = current_frame - offset
                        if target_frame >= 0:
                            frames_to_buffer.append(target_frame)
                    
                    # Buffer frames
                    for target_frame in frames_to_buffer:
                        with self.buffer_lock:
                            buffer_size = len(self.frame_buffer)
                            if target_frame in self.frame_buffer or buffer_size >= self.buffer_max_size:
                                continue
                        
                        # Use separate VideoCapture for buffering
                        buffer_cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                        ret, frame = buffer_cap.read()
                        if ret and frame is not None:
                            with self.buffer_lock:
                                self.frame_buffer[target_frame] = frame
                                while len(self.frame_buffer) > self.buffer_max_size:
                                    self.frame_buffer.popitem(last=False)
                    
                    # Sleep slightly longer when paused, but still keep buffering active
                    sleep_time = 0.01 if self.is_playing else 0.02  # Reduced from 0.05 to keep buffer more active
                    time.sleep(sleep_time)
                    
                    # Update buffer status label periodically (every 10 buffer cycles)
                    if hasattr(self, '_buffer_update_counter'):
                        self._buffer_update_counter += 1
                    else:
                        self._buffer_update_counter = 0
                    
                    if self._buffer_update_counter >= 10:
                        self._buffer_update_counter = 0
                        # Schedule UI update on main thread
                        if hasattr(self, 'viewer') and self.viewer.root:
                            try:
                                self.viewer.root.after(0, self._update_buffer_status_label)
                            except:
                                pass
                except Exception as e:
                    # Log error but continue
                    time.sleep(0.1)
        finally:
            # Always release the buffer VideoCapture
            if buffer_cap is not None:
                try:
                    buffer_cap.release()
                except:
                    pass
    
    def update_display(self):
        """Update display with current frame"""
        # Check buffer first for smooth playback
        frame_num = self.viewer.current_frame_num
        frame = None
        
        # Try to get from PlaybackMode buffer first
        with self.buffer_lock:
            if frame_num in self.frame_buffer:
                frame = self.frame_buffer[frame_num].copy()
                # Move to end (most recently used)
                self.frame_buffer.move_to_end(frame_num)
        
        # Fallback to video_manager
        if frame is None:
            frame = self.video_manager.get_frame(frame_num)
        
        if frame is not None:
            self.display_frame(frame, frame_num)
    
    def first_frame(self):
        self.goto_frame(0)
    
    def prev_frame(self):
        self.goto_frame(max(0, self.viewer.current_frame_num - 1))
    
    def next_frame(self):
        self.goto_frame(min(self.video_manager.total_frames - 1, 
                          self.viewer.current_frame_num + 1))
    
    def last_frame(self):
        self.goto_frame(self.video_manager.total_frames - 1)
    
    def goto_frame(self, frame_num=None):
        if frame_num is None:
            if self.frame_var is not None:
                frame_num = self.frame_var.get()
            elif self.goto_frame_var is not None:
                try:
                    frame_num = int(self.goto_frame_var.get())
                except (ValueError, TypeError):
                    return
            else:
                return
        
        frame_num = max(0, min(frame_num, self.video_manager.total_frames - 1))
        if self.frame_var is not None:
            self.frame_var.set(frame_num)
        
        # Update frame label
        if self.frame_label is not None:
            self.frame_label.config(text=f"Frame: {frame_num} / {self.video_manager.total_frames - 1}")
        
        # Use buffered frame loading for smooth playback
        self.viewer.current_frame_num = frame_num
        self.update_display()
    
    def on_video_loaded(self):
        if self.video_manager.total_frames > 0:
            if self.frame_var is not None:
                self.frame_var.set(0)
            # Update frame slider range
            if self.frame_slider is not None:
                self.frame_slider.config(to=max(100, self.video_manager.total_frames - 1))
            if self.frame_label is not None:
                self.frame_label.config(text=f"Frame: 0 / {self.video_manager.total_frames - 1}")
            self.goto_frame(0)
            if self.status_label is not None:
                self.status_label.config(text=f"Video loaded: {self.video_manager.total_frames} frames")
            
            # Pre-buffer frames for smooth playback (even when not playing)
            if not self.buffer_thread_running:
                self.start_buffer_thread()
            
            # Update buffer status
            if hasattr(self, '_update_buffer_status_label'):
                self._update_buffer_status_label()
    
    def on_csv_loaded(self):
        """Called when CSV is loaded - extract analytics data"""
        if self.csv_manager.is_loaded() and hasattr(self.csv_manager, 'df') and self.csv_manager.df is not None:
            # Extract analytics data from CSV
            self.analytics_data = {}
            
            analytics_columns = [
                'player_speed_mps', 'player_speed_mph', 'avg_speed_mps', 'avg_speed_mph',
                'max_speed_mps', 'max_speed_mph', 'player_acceleration_mps2', 
                'player_acceleration_fts2', 'distance_to_ball_px', 'distance_traveled_m',
                'distance_traveled_ft', 'field_zone', 'possession_time_s'
            ]
            
            for _, row in self.csv_manager.df.iterrows():
                if pd.isna(row.get('frame')):
                    continue
                
                try:
                    frame_num = int(row['frame'])
                except (ValueError, TypeError):
                    continue
                
                if pd.notna(row.get('player_id')):
                    player_id = int(row['player_id'])
                    
                    if frame_num not in self.analytics_data:
                        self.analytics_data[frame_num] = {}
                    
                    analytics = {}
                    for col in analytics_columns:
                        if col in self.csv_manager.df.columns and pd.notna(row.get(col)):
                            analytics[col] = row[col]
                    
                    if analytics:
                        self.analytics_data[frame_num][player_id] = analytics
            
            # Update heatmap player dropdown
            self.update_heatmap_player_dropdown()
        
        self.update_display()
        if self.status_label is not None:
            self.status_label.config(text="CSV loaded - Analytics available")
    
    def update_heatmap_player_dropdown(self):
        """Update heatmap player dropdown with available players"""
        if self.heatmap_player_combo is None:
            return
        
        if not self.csv_manager.is_loaded():
            self.heatmap_player_combo['values'] = ["all"]
            return
        
        # Get unique player IDs from CSV
        player_ids = set()
        if hasattr(self.csv_manager, 'df') and self.csv_manager.df is not None:
            if 'player_id' in self.csv_manager.df.columns:
                player_ids = sorted([int(pid) for pid in self.csv_manager.df['player_id'].dropna().unique()])
        
        # Create dropdown values
        values = ["all"] + [str(pid) for pid in player_ids]
        self.heatmap_player_combo['values'] = values
    
    # ==================== FILE OPERATIONS ====================
    
    def load_video(self):
        """Load video file"""
        filename = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if filename:
            self.video_manager.load_video(filename)
            self.on_video_loaded()
    
    def load_csv(self, csv_path=None):
        """Load CSV tracking data"""
        if csv_path is None:
            csv_path = filedialog.askopenfilename(
                title="Select CSV Tracking File",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
        if csv_path:
            self.csv_manager.load_csv(csv_path)
            self.on_csv_loaded()
            # Start file watching if enabled
            if self.watch_csv_enabled.get():
                self.start_file_watching()
    
    def load_metadata_manual(self):
        """Manually load overlay metadata file"""
        if not self.video_manager.video_path:
            messagebox.showwarning("No Video", "Please load a video file first")
            return
        
        filename = filedialog.askopenfilename(
            title="Select Overlay Metadata File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                # Try to import overlay metadata modules
                try:
                    from overlay_metadata import OverlayMetadata
                    from overlay_renderer import OverlayRenderer
                except ImportError:
                    messagebox.showerror("Error", "Overlay metadata modules not available")
                    return
                
                self.overlay_metadata = OverlayMetadata.load(filename)
                self.overlay_renderer = OverlayRenderer(self.overlay_metadata, use_hd=False, quality="sd")
                self.use_overlay_metadata.set(True)
                messagebox.showinfo("Metadata Loaded", f"Loaded {len(self.overlay_metadata.overlays)} frames")
                self.update_display()
            except Exception as e:
                messagebox.showerror("Error", f"Could not load metadata: {e}")
    
    def reload_csv(self):
        """Reload CSV file"""
        if not self.csv_manager.csv_path:
            messagebox.showwarning("No CSV", "No CSV file loaded")
            return
        try:
            self.load_csv(self.csv_manager.csv_path)
            messagebox.showinfo("Reloaded", "CSV file reloaded successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Could not reload CSV: {e}")
    
    def export_video(self):
        """Export video with overlays"""
        if not self.video_manager.video_path:
            messagebox.showerror("Error", "Please load a video file first")
            return
        
        output_path = filedialog.asksaveasfilename(
            title="Save Video With Overlays",
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        if not output_path:
            return
        
        result = messagebox.askyesno(
            "Export Video",
            f"Export video with current overlay settings?\n\n"
            f"Frames: {self.video_manager.total_frames}\n\n"
            f"This may take a while. Continue?"
        )
        if not result:
            return
        
        # Create progress window
        progress_window = tk.Toplevel(self.viewer.root)
        progress_window.title("Exporting Video")
        progress_window.geometry("400x150")
        progress_window.transient(self.viewer.root)
        progress_window.grab_set()
        
        progress_label = ttk.Label(progress_window, text="Preparing export...")
        progress_label.pack(pady=10)
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100, length=350)
        progress_bar.pack(pady=10)
        
        status_label = ttk.Label(progress_window, text="")
        status_label.pack(pady=5)
        
        # Export in background thread
        def export_thread():
            try:
                cap = cv2.VideoCapture(self.video_manager.video_path)
                if not cap.isOpened():
                    raise Exception("Could not open video")
                
                fps = self.video_manager.fps
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                
                if not out.isOpened():
                    raise Exception("Could not create output video")
                
                frame_num = 0
                start_time = time.time()
                
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    # Render overlays
                    display_frame = self.display_frame(frame.copy(), frame_num)
                    
                    # Write frame
                    out.write(display_frame)
                    
                    frame_num += 1
                    progress = (frame_num / total_frames) * 100
                    progress_var.set(progress)
                    
                    elapsed = time.time() - start_time
                    fps_current = frame_num / elapsed if elapsed > 0 else 0
                    eta = (total_frames - frame_num) / fps_current if fps_current > 0 else 0
                    
                    status_text = f"Frame {frame_num}/{total_frames} ({progress:.1f}%) | ETA: {eta:.0f}s"
                    status_label.config(text=status_text)
                    progress_window.update()
                
                cap.release()
                out.release()
                
                progress_window.after(0, progress_window.destroy)
                self.viewer.root.after(0, lambda: messagebox.showinfo(
                    "Export Complete",
                    f"Video exported successfully!\n\nOutput: {output_path}"
                ))
            except Exception as e:
                progress_window.after(0, progress_window.destroy)
                self.viewer.root.after(0, lambda: messagebox.showerror("Export Error", str(e)))
        
        thread = threading.Thread(target=export_thread, daemon=True)
        thread.start()
    
    # ==================== WINDOW CONTROLS ====================
    
    def toggle_always_on_top(self):
        """Toggle always on top"""
        self.viewer.root.attributes('-topmost', self.always_on_top.get())
    
    def maximize_window(self):
        """Maximize window"""
        self.viewer.root.state('zoomed')
        self.is_maximized = True
    
    def minimize_window(self):
        """Minimize window"""
        self.viewer.root.iconify()
    
    def toggle_fullscreen(self):
        """Toggle fullscreen"""
        self.is_fullscreen = not self.is_fullscreen
        self.viewer.root.attributes('-fullscreen', self.is_fullscreen)
    
    # ==================== PLAYBACK CONTROLS ====================
    
    def on_slider_change(self, value):
        """Handle frame slider change"""
        try:
            frame_num = int(float(value))
            self.frame_var.set(frame_num)
            self.frame_label.config(text=f"Frame: {frame_num} / {self.video_manager.total_frames - 1}")
        except:
            pass
    
    def update_speed(self):
        """Update playback speed"""
        try:
            self.playback_speed = self.speed_var.get()
        except:
            pass
    
    
    # ==================== CANVAS INTERACTIONS ====================
    
    def on_canvas_click(self, event):
        """Handle canvas click"""
        if event.num == 3:  # Right-click - start panning
            self.is_panning = True
            self.pan_start_x = event.x
            self.pan_start_y = event.y
    
    def on_canvas_drag(self, event):
        """Handle canvas drag"""
        if self.is_panning:
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.pan_x += dx
            self.pan_y += dy
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.update_display()
    
    def on_canvas_release(self, event):
        """Handle canvas release"""
        self.is_panning = False
    
    def on_canvas_wheel(self, event):
        """Handle mouse wheel for zoom"""
        if event.delta > 0:
            self.zoom_single(1.1)
        else:
            self.zoom_single(0.9)
    
    # ==================== ZOOM/PAN ====================
    
    def zoom_single(self, zoom_factor):
        """Zoom in/out"""
        self.zoom_level = max(0.5, min(5.0, self.zoom_level * zoom_factor))
        if hasattr(self, 'zoom_label'):
            self.zoom_label.config(text=f"{self.zoom_level:.1f}x")
        if self.zoom_level == 1.0:
            self.pan_x = 0
            self.pan_y = 0
        self.update_display()
    
    def reset_zoom_single(self):
        """Reset zoom and pan"""
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        if hasattr(self, 'zoom_label'):
            self.zoom_label.config(text="1.0x")
        self.update_display()
    
    # ==================== FILE WATCHING ====================
    
    def start_file_watching(self):
        """Start watching CSV file for changes"""
        if self.watch_running:
            return
        
        if not self.csv_manager.csv_path or not os.path.exists(self.csv_manager.csv_path):
            return
        
        self.csv_last_modified = os.path.getmtime(self.csv_manager.csv_path)
        self.watch_running = True
        self.watch_thread = threading.Thread(target=self._watch_csv_file, daemon=True)
        self.watch_thread.start()
    
    def stop_file_watching(self):
        """Stop file watching"""
        self.watch_running = False
        if self.watch_thread:
            self.watch_thread.join(timeout=1.0)
    
    def _watch_csv_file(self):
        """Watch CSV file for changes"""
        while self.watch_running:
            try:
                if self.watch_csv_enabled.get() and self.csv_manager.csv_path and os.path.exists(self.csv_manager.csv_path):
                    current_mtime = os.path.getmtime(self.csv_manager.csv_path)
                    if self.csv_last_modified is not None and current_mtime > self.csv_last_modified:
                        self.csv_last_modified = current_mtime
                        self.viewer.root.after(0, self._auto_reload_csv)
                time.sleep(1.0)
            except:
                time.sleep(1.0)
    
    def _auto_reload_csv(self):
        """Auto-reload CSV when file changes"""
        if self.csv_manager.csv_path and os.path.exists(self.csv_manager.csv_path):
            try:
                self.load_csv(self.csv_manager.csv_path)
                self.status_label.config(text=f"CSV auto-reloaded at {time.strftime('%H:%M:%S')}")
            except:
                pass
    
    def _update_buffer_status_label(self):
        """Update buffer status label"""
        try:
            if not hasattr(self, 'buffer_status_label') or not self.buffer_status_label.winfo_exists():
                return
            
            buffer_size = len(self.frame_buffer)
            buffer_max = self.buffer_max_size
            
            fill_pct = int((buffer_size / buffer_max) * 100) if buffer_max > 0 else 0
            
            if fill_pct < 30:
                color = "red"
            elif fill_pct < 60:
                color = "orange"
            else:
                color = "green"
            
            status_text = f"{buffer_size}/{buffer_max} ({fill_pct}%)"
            self.buffer_status_label.config(text=status_text, foreground=color)
        except (tk.TclError, AttributeError):
            pass
    
    def _sync_box_color(self):
        """Sync box_color_rgb string with individual R, G, B components"""
        r = self.box_color_r.get()
        g = self.box_color_g.get()
        b = self.box_color_b.get()
        self.box_color_rgb.set(f"{r},{g},{b}")
        self.update_display()
    
    def _sync_label_color(self):
        """Sync label_color_rgb string with individual R, G, B components"""
        r = self.label_color_r.get()
        g = self.label_color_g.get()
        b = self.label_color_b.get()
        self.label_color_rgb.set(f"{r},{g},{b}")
        self.update_display()
    
    # ==================== ENHANCED DISPLAY ====================
    
    def draw_player_trails(self, display_frame: np.ndarray, frame_num: int) -> np.ndarray:
        """Draw player movement trails"""
        if not self.show_player_trail.get() or not self.csv_manager.is_loaded():
            return display_frame
        
        from collections import deque
        
        # Initialize trails if needed
        if not hasattr(self, 'player_trails'):
            self.player_trails = {}
        
        # Update trails for each player
        player_data = self.csv_manager.get_player_data(frame_num)
        for player_id, (x, y, team, name, bbox) in player_data.items():
            player_id_int = int(player_id)
            
            # Convert coordinates
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                x = int(x * self.video_manager.width)
                y = int(y * self.video_manager.height)
            
            # Initialize trail if needed
            if player_id_int not in self.player_trails:
                self.player_trails[player_id_int] = deque(maxlen=self.player_trail_length.get())
            
            # Add current position
            self.player_trails[player_id_int].append((frame_num, int(x), int(y)))
            
            # Draw trail
            trail_points = list(self.player_trails[player_id_int])
            if len(trail_points) > 1:
                color = self.get_player_color(player_id_int, team, name)
                for i in range(len(trail_points) - 1):
                    alpha = i / len(trail_points) if self.player_trail_fade.get() else 1.0
                    size = self.player_trail_size.get()
                    pt1 = (trail_points[i][1], trail_points[i][2])
                    pt2 = (trail_points[i+1][1], trail_points[i+1][2])
                    thickness = max(1, int(size * alpha))
                    cv2.circle(display_frame, pt1, thickness, color, -1)
                    if i < len(trail_points) - 1:
                        cv2.line(display_frame, pt1, pt2, color, thickness)
        
        return display_frame
    
    def draw_ball_trail(self, display_frame: np.ndarray, frame_num: int) -> np.ndarray:
        """Draw ball trail"""
        if not self.show_ball_trail.get() or not self.csv_manager.is_loaded():
            return display_frame
        
        # Update ball trail
        ball_data = self.csv_manager.get_ball_data(frame_num)
        if ball_data:
            ball_x, ball_y, normalized = ball_data
            if normalized:
                ball_x = int(ball_x * self.video_manager.width)
                ball_y = int(ball_y * self.video_manager.height)
            
            self.ball_trail.append((frame_num, int(ball_x), int(ball_y)))
            if len(self.ball_trail) > 30:  # Keep last 30 positions
                self.ball_trail.pop(0)
        
        # Draw trail
        if len(self.ball_trail) > 1:
            for i in range(len(self.ball_trail) - 1):
                pt1 = (self.ball_trail[i][1], self.ball_trail[i][2])
                pt2 = (self.ball_trail[i+1][1], self.ball_trail[i+1][2])
                alpha = i / len(self.ball_trail)
                color = (0, int(255 * alpha), 255)
                cv2.line(display_frame, pt1, pt2, color, 2)
        
        return display_frame
    
    # ==================== HEATMAPS ====================
    
    def draw_heatmap(self, display_frame: np.ndarray, frame_num: int) -> np.ndarray:
        """Draw player heatmap overlay"""
        if not self.csv_manager.is_loaded():
            return display_frame
        
        heatmap_type = self.heatmap_type.get()
        opacity = self.heatmap_opacity.get()
        radius = self.heatmap_radius.get()
        time_range = self.heatmap_time_range.get()
        player_filter = self.heatmap_player_id.get()
        
        # Collect data points for heatmap
        start_frame = max(0, frame_num - time_range)
        end_frame = min(self.video_manager.total_frames, frame_num + 1)
        
        points = []
        weights = []
        
        for f in range(start_frame, end_frame):
            player_data = self.csv_manager.get_player_data(f)
            for player_id, (x, y, team, name, bbox) in player_data.items():
                player_id_int = int(player_id)
                
                # Filter by player if specified
                if player_filter != "all":
                    try:
                        if int(player_filter) != player_id_int:
                            continue
                    except:
                        pass
                
                # Convert coordinates
                if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                    x = int(x * self.video_manager.width)
                    y = int(y * self.video_manager.height)
                
                points.append((int(x), int(y)))
                
                # Calculate weight based on heatmap type
                weight = 1.0
                if heatmap_type == "speed" and self.analytics_data:
                    # Use speed as weight
                    if f in self.analytics_data and player_id_int in self.analytics_data[f]:
                        speed = self.analytics_data[f][player_id_int].get('player_speed_mps', 0)
                        weight = max(0.1, min(2.0, speed / 5.0))  # Normalize to 0.1-2.0
                elif heatmap_type == "acceleration" and self.analytics_data:
                    # Use acceleration as weight
                    if f in self.analytics_data and player_id_int in self.analytics_data[f]:
                        accel = abs(self.analytics_data[f][player_id_int].get('player_acceleration_mps2', 0))
                        weight = max(0.1, min(2.0, accel / 3.0))  # Normalize to 0.1-2.0
                elif heatmap_type == "possession":
                    # Weight by time spent (more recent = higher weight)
                    frame_age = frame_num - f
                    weight = max(0.1, 1.0 - (frame_age / time_range))
                
                weights.append(weight)
        
        if not points:
            return display_frame
        
        # Create heatmap using Gaussian blur
        h, w = display_frame.shape[:2]
        heatmap = np.zeros((h, w), dtype=np.float32)
        
        for (px, py), weight in zip(points, weights):
            # Create Gaussian kernel for this point
            y_coords, x_coords = np.ogrid[:h, :w]
            dist_sq = (x_coords - px)**2 + (y_coords - py)**2
            gaussian = np.exp(-dist_sq / (2 * (radius ** 2))) * weight
            heatmap += gaussian
        
        # Normalize heatmap
        if heatmap.max() > 0:
            heatmap = heatmap / heatmap.max()
        
        # Apply colormap (hot colormap: black -> red -> yellow -> white)
        heatmap_colored = cv2.applyColorMap((heatmap * 255).astype(np.uint8), cv2.COLORMAP_HOT)
        
        # Blend with original frame
        overlay = display_frame.copy()
        mask = (heatmap > 0.1).astype(np.uint8)  # Only show areas with significant activity
        overlay[mask > 0] = heatmap_colored[mask > 0]
        
        result = cv2.addWeighted(display_frame, 1.0 - opacity, overlay, opacity, 0)
        
        return result
    
    # ==================== EVENT TIMELINE VIEWER ====================
    
    def open_event_timeline(self):
        """Open event timeline viewer window"""
        try:
            # Try to import EventTimelineViewer
            try:
                from event_timeline_viewer import EventTimelineViewer
            except ImportError:
                # Try alternative path
                current_file = __file__
                parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(current_file)))))
                timeline_path = os.path.join(parent_dir, 'event_timeline_viewer.py')
                if os.path.exists(timeline_path):
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("event_timeline_viewer", timeline_path)
                    timeline_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(timeline_module)
                    EventTimelineViewer = timeline_module.EventTimelineViewer
                else:
                    messagebox.showwarning("Not Available", "Event Timeline Viewer module not found")
                    return
            
            # Check if already open
            if self.event_timeline_viewer and hasattr(self.event_timeline_viewer, 'window'):
                try:
                    if self.event_timeline_viewer.window.winfo_exists():
                        self.event_timeline_viewer.window.focus()
                        return
                except:
                    pass
            
            # Initialize event tracker if needed
            if not self.event_tracker:
                try:
                    from event_tracker import EventTracker
                    self.event_tracker = EventTracker(
                        video_path=self.video_manager.video_path,
                        fps=self.video_manager.fps
                    )
                    # Load events from CSV if available
                    if self.csv_manager.is_loaded() and hasattr(self.csv_manager, 'df'):
                        self.event_tracker.load_from_csv(self.csv_manager.df)
                except ImportError:
                    messagebox.showwarning("Event Tracker", "Event Tracker module not available")
                    return
            
            # Create timeline viewer
            def jump_to_frame(frame_num):
                """Callback to jump to frame in main viewer"""
                self.goto_frame(frame_num)
                self.viewer.root.focus()
            
            self.event_timeline_viewer = EventTimelineViewer(
                parent=self.viewer.root,
                event_tracker=self.event_tracker,
                video_path=self.video_manager.video_path,
                total_frames=self.video_manager.total_frames,
                fps=self.video_manager.fps,
                jump_callback=jump_to_frame,
                gallery_manager=self.gallery_manager,
                overlay_renderer=self.hd_renderer
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not open event timeline viewer: {e}")
            import traceback
            traceback.print_exc()
    
    # ==================== COMPARISON MODE ====================
    
    def toggle_comparison_mode(self):
        """Toggle comparison mode on/off"""
        # This will be called from the checkbox
        # We'll implement a dialog to set frames
        self.open_comparison_dialog()
    
    def open_comparison_dialog(self):
        """Open dialog to configure comparison mode"""
        dialog = tk.Toplevel(self.viewer.root)
        dialog.title("Comparison Mode Setup")
        dialog.geometry("400x200")
        dialog.transient(self.viewer.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Compare Two Frames", font=("Arial", 12, "bold")).pack(pady=10)
        
        frame1_frame = ttk.Frame(dialog)
        frame1_frame.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(frame1_frame, text="Frame 1:").pack(side=tk.LEFT, padx=5)
        frame1_var = tk.StringVar(value=str(self.viewer.current_frame_num))
        frame1_entry = ttk.Entry(frame1_frame, textvariable=frame1_var, width=10)
        frame1_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(frame1_frame, text="Current", command=lambda: frame1_var.set(str(self.viewer.current_frame_num))).pack(side=tk.LEFT, padx=2)
        
        frame2_frame = ttk.Frame(dialog)
        frame2_frame.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(frame2_frame, text="Frame 2:").pack(side=tk.LEFT, padx=5)
        frame2_var = tk.StringVar(value=str(min(self.viewer.current_frame_num + 30, self.video_manager.total_frames - 1)))
        frame2_entry = ttk.Entry(frame2_frame, textvariable=frame2_var, width=10)
        frame2_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(frame2_frame, text="Current", command=lambda: frame2_var.set(str(self.viewer.current_frame_num))).pack(side=tk.LEFT, padx=2)
        
        id1_frame = ttk.Frame(dialog)
        id1_frame.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(id1_frame, text="Player ID 1 (optional):").pack(side=tk.LEFT, padx=5)
        id1_var = tk.StringVar()
        id1_entry = ttk.Entry(id1_frame, textvariable=id1_var, width=10)
        id1_entry.pack(side=tk.LEFT, padx=5)
        
        id2_frame = ttk.Frame(dialog)
        id2_frame.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(id2_frame, text="Player ID 2 (optional):").pack(side=tk.LEFT, padx=5)
        id2_var = tk.StringVar()
        id2_entry = ttk.Entry(id2_frame, textvariable=id2_var, width=10)
        id2_entry.pack(side=tk.LEFT, padx=5)
        
        def start_comparison():
            try:
                frame1 = int(frame1_var.get())
                frame2 = int(frame2_var.get())
                id1 = int(id1_var.get()) if id1_var.get().strip() else None
                id2 = int(id2_var.get()) if id2_var.get().strip() else None
                
                if frame1 < 0 or frame1 >= self.video_manager.total_frames:
                    messagebox.showerror("Error", f"Frame 1 out of range (0-{self.video_manager.total_frames - 1})")
                    return
                if frame2 < 0 or frame2 >= self.video_manager.total_frames:
                    messagebox.showerror("Error", f"Frame 2 out of range (0-{self.video_manager.total_frames - 1})")
                    return
                
                self.start_comparison_mode(frame1, frame2, id1, id2)
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Please enter valid frame numbers")
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Start Comparison", command=start_comparison).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def start_comparison(self):
        """Start comparison from UI controls"""
        try:
            frame1 = int(self.comparison_frame1_var.get())
            frame2 = int(self.comparison_frame2_var.get())
            self.start_comparison_mode(frame1, frame2, None, None)
        except ValueError:
            messagebox.showerror("Error", "Please enter valid frame numbers")
    
    def start_comparison_mode(self, frame1: int, frame2: int, id1: int = None, id2: int = None):
        """Start comparison mode with two frames"""
        self.comparison_mode = True
        self.frame1 = frame1
        self.frame2 = frame2
        self.id1 = id1
        self.id2 = id2
        
        # Create comparison window
        self.create_comparison_window()
        
        # Render both frames
        self.render_comparison()
    
    def create_comparison_window(self):
        """Create comparison mode window with two canvases"""
        if hasattr(self, 'comparison_window') and self.comparison_window:
            try:
                if self.comparison_window.winfo_exists():
                    self.comparison_window.focus()
                    return
            except:
                pass
        
        self.comparison_window = tk.Toplevel(self.viewer.root)
        self.comparison_window.title("Frame Comparison")
        self.comparison_window.geometry("1600x900")
        
        # Main container
        main_frame = ttk.Frame(self.comparison_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Top controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(controls_frame, text=f"Frame {self.frame1}", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        ttk.Label(controls_frame, text="vs", font=("Arial", 10)).pack(side=tk.LEFT, padx=10)
        ttk.Label(controls_frame, text=f"Frame {self.frame2}", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(controls_frame, text="Close Comparison", command=self.close_comparison_mode).pack(side=tk.RIGHT, padx=5)
        
        # Two canvas side-by-side
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas 1
        canvas1_frame = ttk.Frame(canvas_frame)
        canvas1_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.frame1_label = ttk.Label(canvas1_frame, text=f"Frame {self.frame1}", font=("Arial", 9))
        self.frame1_label.pack(pady=2)
        
        self.canvas1 = tk.Canvas(canvas1_frame, bg='black')
        self.canvas1.pack(fill=tk.BOTH, expand=True)
        self.canvas1.bind('<MouseWheel>', lambda e: self.zoom_canvas(1, 1.1 if e.delta > 0 else 0.9))
        self.canvas1.bind('<Button-3>', lambda e: self.start_pan(1, e))
        self.canvas1.bind('<B3-Motion>', lambda e: self.pan_canvas(1, e))
        self.canvas1.bind('<ButtonRelease-3>', lambda e: self.stop_pan(1))
        
        # Canvas 2
        canvas2_frame = ttk.Frame(canvas_frame)
        canvas2_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.frame2_label = ttk.Label(canvas2_frame, text=f"Frame {self.frame2}", font=("Arial", 9))
        self.frame2_label.pack(pady=2)
        
        self.canvas2 = tk.Canvas(canvas2_frame, bg='black')
        self.canvas2.pack(fill=tk.BOTH, expand=True)
        self.canvas2.bind('<MouseWheel>', lambda e: self.zoom_canvas(2, 1.1 if e.delta > 0 else 0.9))
        self.canvas2.bind('<Button-3>', lambda e: self.start_pan(2, e))
        self.canvas2.bind('<B3-Motion>', lambda e: self.pan_canvas(2, e))
        self.canvas2.bind('<ButtonRelease-3>', lambda e: self.stop_pan(2))
        
        # Zoom labels
        zoom_frame = ttk.Frame(main_frame)
        zoom_frame.pack(fill=tk.X, pady=5)
        
        self.zoom_label1 = ttk.Label(zoom_frame, text="1.0x")
        self.zoom_label1.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(zoom_frame, text="Mouse wheel to zoom, Right-click drag to pan", 
                 font=("Arial", 8), foreground="gray").pack(side=tk.LEFT, padx=20)
        
        self.zoom_label2 = ttk.Label(zoom_frame, text="1.0x")
        self.zoom_label2.pack(side=tk.RIGHT, padx=20)
    
    def render_comparison(self):
        """Render both frames in comparison mode"""
        if not self.comparison_mode or not hasattr(self, 'canvas1') or not hasattr(self, 'canvas2'):
            return
        
        # Load and render frame 1
        frame1 = self.video_manager.get_frame(self.frame1)
        if frame1 is not None:
            display_frame1 = self.prepare_frame_for_display(frame1, self.frame1)
            display_frame1 = self.apply_zoom_pan_canvas(display_frame1, 1)
            self._display_image_on_canvas(display_frame1, self.canvas1)
        
        # Load and render frame 2
        frame2 = self.video_manager.get_frame(self.frame2)
        if frame2 is not None:
            display_frame2 = self.prepare_frame_for_display(frame2, self.frame2)
            display_frame2 = self.apply_zoom_pan_canvas(display_frame2, 2)
            self._display_image_on_canvas(display_frame2, self.canvas2)
    
    def prepare_frame_for_display(self, frame: np.ndarray, frame_num: int) -> np.ndarray:
        """Prepare frame with all overlays"""
        display_frame = frame.copy()
        
        # Draw CSV overlays
        if self.csv_manager.is_loaded():
            if self.show_players_var.get():
                player_data = self.csv_manager.get_player_data(frame_num)
                for player_id, (x, y, team, name, bbox) in player_data.items():
                    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                        x = int(x * self.video_manager.width)
                        y = int(y * self.video_manager.height)
                    
                    color = self.get_player_color(int(player_id), team, name)
                    cv2.circle(display_frame, (int(x), int(y)), 10, color, 2)
                    
                    if self.show_labels_var.get() and name:
                        cv2.putText(display_frame, name, (int(x) + 15, int(y)),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            if self.show_ball_var.get():
                ball_data = self.csv_manager.get_ball_data(frame_num)
                if ball_data:
                    ball_x, ball_y, normalized = ball_data
                    if normalized:
                        ball_x = int(ball_x * self.video_manager.width)
                        ball_y = int(ball_y * self.video_manager.height)
                    cv2.circle(display_frame, (int(ball_x), int(ball_y)), 8, (0, 0, 255), -1)
        
        return display_frame
    
    def apply_zoom_pan_canvas(self, frame: np.ndarray, canvas_num: int) -> np.ndarray:
        """Apply zoom and pan for comparison canvas"""
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
        new_w = int(w * zoom)
        new_h = int(h * zoom)
        
        zoomed = cv2.resize(frame, (new_w, new_h))
        
        crop_x = int((new_w - w) / 2 - pan_x)
        crop_y = int((new_h - h) / 2 - pan_y)
        
        crop_x = max(0, min(crop_x, new_w - w))
        crop_y = max(0, min(crop_y, new_h - h))
        
        if crop_x + w <= new_w and crop_y + h <= new_h:
            cropped = zoomed[crop_y:crop_y+h, crop_x:crop_x+w]
        else:
            cropped = frame
        
        return cropped
    
    def _display_image_on_canvas(self, frame: np.ndarray, canvas: tk.Canvas):
        """Display image on a specific canvas"""
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            canvas.update_idletasks()
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return
        
        scale = min(canvas_width / frame.shape[1], canvas_height / frame.shape[0])
        new_width = int(frame.shape[1] * scale)
        new_height = int(frame.shape[0] * scale)
        
        resized = cv2.resize(frame, (new_width, new_height))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        photo = ImageTk.PhotoImage(image=img)
        
        canvas.delete("all")
        canvas.create_image(canvas_width // 2, canvas_height // 2, 
                          image=photo, anchor=tk.CENTER)
        canvas.image = photo
    
    def zoom_canvas(self, canvas_num: int, zoom_factor: float):
        """Zoom canvas in comparison mode"""
        if canvas_num == 1:
            self.zoom_level1 = max(0.5, min(5.0, self.zoom_level1 * zoom_factor))
            if hasattr(self, 'zoom_label1'):
                self.zoom_label1.config(text=f"{self.zoom_level1:.1f}x")
        else:
            self.zoom_level2 = max(0.5, min(5.0, self.zoom_level2 * zoom_factor))
            if hasattr(self, 'zoom_label2'):
                self.zoom_label2.config(text=f"{self.zoom_level2:.1f}x")
        
        self.render_comparison()
    
    def start_pan(self, canvas_num: int, event):
        """Start panning on canvas"""
        if canvas_num == 1:
            self.pan_start_x1 = event.x
            self.pan_start_y1 = event.y
        else:
            self.pan_start_x2 = event.x
            self.pan_start_y2 = event.y
    
    def pan_canvas(self, canvas_num: int, event):
        """Pan canvas"""
        if canvas_num == 1:
            dx = event.x - self.pan_start_x1
            dy = event.y - self.pan_start_y1
            self.pan_x1 += dx
            self.pan_y1 += dy
            self.pan_start_x1 = event.x
            self.pan_start_y1 = event.y
        else:
            dx = event.x - self.pan_start_x2
            dy = event.y - self.pan_start_y2
            self.pan_x2 += dx
            self.pan_y2 += dy
            self.pan_start_x2 = event.x
            self.pan_start_y2 = event.y
        
        self.render_comparison()
    
    def stop_pan(self, canvas_num: int):
        """Stop panning"""
        pass
    
    # ==================== VISUALIZATION DRAWING FUNCTIONS ====================
    
    def draw_players_with_visualization(self, display_frame: np.ndarray, frame_num: int) -> np.ndarray:
        """Draw players with all visualization options"""
        if not self.csv_manager.is_loaded():
            return display_frame
        
        player_data = self.csv_manager.get_player_data(frame_num)
        h, w = display_frame.shape[:2]
        
        for player_id, (x, y, team, name, bbox) in player_data.items():
            # Convert coordinates if normalized
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                x = int(x * w)
                y = int(y * h)
            else:
                x = int(x)
                y = int(y)
            
            # Get player color
            color = self.get_player_color(int(player_id), team, name)
            
            # Draw based on visualization style
            viz_style = self.player_viz_style.get()
            
            if viz_style == "box" and bbox:
                # Draw box with shrink factor
                display_frame = self.draw_player_box(display_frame, bbox, color, int(player_id), team, name)
            elif viz_style == "circle":
                # Draw circle at player position
                display_frame = self.draw_player_circle(display_frame, (x, y), color, int(player_id), team, name)
            
            # Draw ellipse if enabled
            if self.ellipse_width.get() > 0 and self.ellipse_height.get() > 0:
                display_frame = self.draw_player_ellipse(display_frame, (x, y), color)
            
            # Draw feet marker with all effects
            feet_y = y + self.feet_marker_vertical_offset.get()
            display_frame = self.draw_feet_marker(display_frame, (x, feet_y), color, frame_num)
            
            # Draw direction arrow if enabled
            if self.show_direction_arrow.get():
                display_frame = self.draw_direction_arrow(display_frame, (x, y), frame_num, int(player_id))
            
            # Draw label with customization
            if self.show_labels_var.get() and name:
                display_frame = self.draw_player_label(display_frame, (x, y), int(player_id), team, name, color)
        
        return display_frame
    
    def draw_player_box(self, display_frame: np.ndarray, bbox: tuple, color: tuple, player_id: int, team: str, name: str) -> np.ndarray:
        """Draw player bounding box with shrink factor, custom colors, and opacity"""
        x1, y1, x2, y2 = bbox
        
        # Apply shrink factor
        shrink = self.box_shrink_factor.get()
        if shrink > 0:
            width = x2 - x1
            height = y2 - y1
            shrink_x = int(width * shrink)
            shrink_y = int(height * shrink)
            x1 += shrink_x
            y1 += shrink_y
            x2 -= shrink_x
            y2 -= shrink_y
        
        # Get box color based on color mode and custom color settings
        color_mode = self.viz_color_mode.get()
        if color_mode == "custom" and self.use_custom_box_color.get():
            box_color = (self.box_color_b.get(), self.box_color_g.get(), self.box_color_r.get())
        elif color_mode == "team" and self.use_custom_box_color.get():
            # In team mode, custom box color overrides team color
            box_color = (self.box_color_b.get(), self.box_color_g.get(), self.box_color_r.get())
        else:
            box_color = color
        
        # Get thickness
        thickness = self.box_thickness.get()
        
        # Apply opacity if not fully opaque
        alpha = self.player_viz_alpha.get() / 255.0
        if alpha < 1.0:
            # Draw on overlay and blend
            overlay = display_frame.copy()
            cv2.rectangle(overlay, (int(x1), int(y1)), (int(x2), int(y2)), box_color, thickness)
            cv2.addWeighted(overlay, alpha, display_frame, 1 - alpha, 0, display_frame)
        else:
            # Draw directly
            cv2.rectangle(display_frame, (int(x1), int(y1)), (int(x2), int(y2)), box_color, thickness)
        
        return display_frame
    
    def draw_player_circle(self, display_frame: np.ndarray, center: tuple, color: tuple, player_id: int, team: str, name: str) -> np.ndarray:
        """Draw player circle with opacity support"""
        x, y = center
        radius = 10
        
        # Circles use color from get_player_color (respects viz_color_mode)
        # Apply opacity if not fully opaque
        alpha = self.player_viz_alpha.get() / 255.0
        if alpha < 1.0:
            overlay = display_frame.copy()
            cv2.circle(overlay, (int(x), int(y)), radius, color, 2)
            cv2.addWeighted(overlay, alpha, display_frame, 1 - alpha, 0, display_frame)
        else:
            cv2.circle(display_frame, (int(x), int(y)), radius, color, 2)
        
        return display_frame
    
    def draw_player_ellipse(self, display_frame: np.ndarray, center: tuple, color: tuple) -> np.ndarray:
        """Draw ellipse at player feet with opacity support"""
        x, y = center
        axes_w = self.ellipse_width.get()
        axes_h = self.ellipse_height.get()
        outline_thickness = self.ellipse_outline_thickness.get()
        
        # Apply opacity if not fully opaque
        alpha = self.player_viz_alpha.get() / 255.0
        if alpha < 1.0:
            overlay = display_frame.copy()
            cv2.ellipse(overlay, (int(x), int(y)), (axes_w, axes_h), 0, 0, 360, color, outline_thickness)
            cv2.addWeighted(overlay, alpha, display_frame, 1 - alpha, 0, display_frame)
        else:
            cv2.ellipse(display_frame, (int(x), int(y)), (axes_w, axes_h), 0, 0, 360, color, outline_thickness)
        
        return display_frame
    
    def draw_feet_marker(self, display_frame: np.ndarray, center: tuple, color: tuple, frame_num: int) -> np.ndarray:
        """Draw enhanced feet marker with all effects"""
        import math
        x, y = center
        style = self.feet_marker_style.get()
        opacity = self.feet_marker_opacity.get()
        
        # Base size
        base_radius = 8
        
        # Apply pulse effect if enabled
        if self.feet_marker_enable_pulse.get():
            pulse_phase = (frame_num * self.feet_marker_pulse_speed.get() / 60.0) % (2 * math.pi)
            pulse_scale = 1.0 + 0.2 * math.sin(pulse_phase)
            base_radius = int(base_radius * pulse_scale)
        
        # Draw shadow if enabled
        if self.feet_marker_enable_shadow.get():
            shadow_offset = self.feet_marker_shadow_offset.get()
            shadow_opacity = self.feet_marker_shadow_opacity.get()
            shadow_color = (0, 0, 0)
            shadow_x = x + shadow_offset
            shadow_y = y + shadow_offset
            
            overlay = display_frame.copy()
            cv2.circle(overlay, (shadow_x, shadow_y), base_radius, shadow_color, -1)
            cv2.addWeighted(overlay, shadow_opacity / 255.0, display_frame, 
                           1 - (shadow_opacity / 255.0), 0, display_frame)
        
        # Draw glow if enabled
        if self.feet_marker_enable_glow.get():
            glow_intensity = self.feet_marker_glow_intensity.get()
            glow_size = int(glow_intensity / 10)
            for i in range(glow_size, 0, -1):
                glow_alpha = (glow_intensity / 100.0) * (1.0 - i / max(1, glow_size))
                glow_color = tuple(int(c * (1.0 + glow_alpha)) for c in color)
                cv2.circle(display_frame, (int(x), int(y)), base_radius + i, glow_color, 2)
        
        # Draw main marker based on style
        if style == "circle":
            if opacity < 255:
                overlay = display_frame.copy()
                cv2.circle(overlay, (int(x), int(y)), base_radius, color, -1)
                cv2.addWeighted(overlay, opacity / 255.0, display_frame, 1 - (opacity / 255.0), 0, display_frame)
            else:
                cv2.circle(display_frame, (int(x), int(y)), base_radius, color, -1)
        elif style == "diamond":
            points = np.array([
                [x, y - base_radius],
                [x + base_radius, y],
                [x, y + base_radius],
                [x - base_radius, y]
            ], np.int32)
            if opacity < 255:
                overlay = display_frame.copy()
                cv2.fillPoly(overlay, [points], color)
                cv2.addWeighted(overlay, opacity / 255.0, display_frame, 1 - (opacity / 255.0), 0, display_frame)
            else:
                cv2.fillPoly(display_frame, [points], color)
        elif style == "star":
            import math
            outer_radius = base_radius
            inner_radius = base_radius // 2
            points = []
            for i in range(10):
                angle = i * math.pi / 5
                r = outer_radius if i % 2 == 0 else inner_radius
                px = int(x + r * math.cos(angle))
                py = int(y + r * math.sin(angle))
                points.append([px, py])
            if opacity < 255:
                overlay = display_frame.copy()
                cv2.fillPoly(overlay, [np.array(points, np.int32)], color)
                cv2.addWeighted(overlay, opacity / 255.0, display_frame, 1 - (opacity / 255.0), 0, display_frame)
            else:
                cv2.fillPoly(display_frame, [np.array(points, np.int32)], color)
        elif style == "hexagon":
            import math
            hex_radius = base_radius
            points = []
            for i in range(6):
                angle = i * math.pi / 3
                px = int(x + hex_radius * math.cos(angle))
                py = int(y + hex_radius * math.sin(angle))
                points.append([px, py])
            if opacity < 255:
                overlay = display_frame.copy()
                cv2.fillPoly(overlay, [np.array(points, np.int32)], color)
                cv2.addWeighted(overlay, opacity / 255.0, display_frame, 1 - (opacity / 255.0), 0, display_frame)
            else:
                cv2.fillPoly(display_frame, [np.array(points, np.int32)], color)
        
        # Draw particles if enabled
        if self.feet_marker_enable_particles.get():
            particle_count = self.feet_marker_particle_count.get()
            import random
            random.seed(frame_num)  # Consistent particles per frame
            for _ in range(particle_count):
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(base_radius, base_radius * 2)
                px = int(x + dist * math.cos(angle))
                py = int(y + dist * math.sin(angle))
                cv2.circle(display_frame, (px, py), 2, color, -1)
        
        return display_frame
    
    def draw_direction_arrow(self, display_frame: np.ndarray, center: tuple, frame_num: int, player_id: int) -> np.ndarray:
        """Draw direction arrow based on player movement"""
        import math
        x, y = center
        
        # Get previous position to determine direction
        if frame_num > 0 and self.csv_manager.is_loaded():
            prev_data = self.csv_manager.get_player_data(frame_num - 1)
            if player_id in prev_data:
                prev_x, prev_y, _, _, _ = prev_data[player_id]
                
                # Convert if normalized
                h, w = display_frame.shape[:2]
                if 0.0 <= prev_x <= 1.0:
                    prev_x = prev_x * w
                    prev_y = prev_y * h
                
                # Calculate direction
                dx = x - prev_x
                dy = y - prev_y
                angle = math.atan2(dy, dx)
                
                # Draw arrow
                arrow_length = 20
                arrow_tip_x = int(x + arrow_length * math.cos(angle))
                arrow_tip_y = int(y + arrow_length * math.sin(angle))
                
                cv2.arrowedLine(display_frame, (int(x), int(y)), (arrow_tip_x, arrow_tip_y), (255, 255, 255), 2)
        
        return display_frame
    
    def draw_player_label(self, display_frame: np.ndarray, center: tuple, player_id: int, team: str, name: str, color: tuple) -> np.ndarray:
        """Draw player label with customization"""
        x, y = center
        
        # Get label text based on label type
        label_type = self.label_type.get()
        if label_type == "full_name":
            label_text = name
        elif label_type == "last_name":
            label_text = name.split()[-1] if " " in name else name
        elif label_type == "jersey":
            # Try to extract jersey number from name or use player_id
            label_text = f"#{player_id}"
        elif label_type == "team":
            label_text = team or f"#{player_id}"
        elif label_type == "custom":
            label_text = self.label_custom_text.get()
        else:
            label_text = name
        
        # Get label color
        if self.use_custom_label_color.get():
            label_color = (self.label_color_b.get(), self.label_color_g.get(), self.label_color_r.get())
        else:
            label_color = (255, 255, 255)  # White default
        
        # Get font settings
        font_scale = self.label_font_scale.get()
        font_thickness = 2
        
        # Get font face
        font_face_str = self.label_font_face.get()
        if font_face_str == "FONT_HERSHEY_SIMPLEX":
            font_face = cv2.FONT_HERSHEY_SIMPLEX
        elif font_face_str == "FONT_HERSHEY_PLAIN":
            font_face = cv2.FONT_HERSHEY_PLAIN
        else:
            font_face = cv2.FONT_HERSHEY_SIMPLEX
        
        # Draw label
        label_x = int(x + 15)
        label_y = int(y)
        cv2.putText(display_frame, label_text, (label_x, label_y), font_face, font_scale, label_color, font_thickness)
        
        return display_frame
    
    def close_comparison_mode(self):
        """Close comparison mode"""
        self.comparison_mode = False
        if hasattr(self, 'comparison_window') and self.comparison_window:
            try:
                self.comparison_window.destroy()
            except:
                pass
            self.comparison_window = None
        self.update_display()
    
    def cleanup(self):
        """Cleanup resources before mode switch or window close"""
        # Stop playback first
        if self.play_after_id:
            try:
                self.viewer.root.after_cancel(self.play_after_id)
            except:
                pass
            self.play_after_id = None
        
        self.is_playing = False
        
        # Stop buffer thread and wait for it to finish
        self.stop_buffer_thread()
        
        # Stop file watching
        self.stop_file_watching()
        
        # Clear frame buffer
        with self.buffer_lock:
            self.frame_buffer.clear()
        
        # Close comparison window if open
        if hasattr(self, 'comparison_window') and self.comparison_window:
            try:
                self.comparison_window.destroy()
            except:
                pass
        
        # Close event timeline viewer if open
        if self.event_timeline_viewer and hasattr(self.event_timeline_viewer, 'window'):
            try:
                if self.event_timeline_viewer.window.winfo_exists():
                    self.event_timeline_viewer.window.destroy()
            except:
                pass
