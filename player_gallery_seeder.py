"""
Player Gallery Seeder GUI
Interactive tool for tagging players and adding them to the player gallery.

This tool allows you to:
1. Load a video and navigate to specific frames
2. Click on a player to select them
3. Assign a name and add them to the gallery
4. Build a persistent player database for cross-video recognition
"""

import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np
from typing import Optional, List, Tuple, Dict
import os
import traceback

# Import player gallery and reid tracker
from player_gallery import PlayerGallery, PlayerProfile

# Try to import supervision
try:
    import supervision as sv
    SUPERVISION_AVAILABLE = True
except ImportError:
    SUPERVISION_AVAILABLE = False
    print("⚠ Supervision library not available. Install with: pip install supervision")

try:
    from reid_tracker import ReIDTracker, TORCHREID_AVAILABLE
    REID_AVAILABLE = True
except:
    REID_AVAILABLE = False
    print("⚠ Re-ID tracker not available. Feature extraction will be limited.")

try:
    from event_marker_system import EventMarkerSystem, EventMarker, EventType
    EVENT_MARKER_AVAILABLE = True
except ImportError:
    EVENT_MARKER_AVAILABLE = False
    print("Warning: Event marker system not available")


class PlayerGallerySeeder:
    """GUI application for seeding players into the gallery"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Player Gallery Seeder")
        self.root.geometry("1400x900")
        
        # Video state
        self.video_path: Optional[str] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.current_frame_num: int = 0
        self.total_frames: int = 0
        self.current_frame: Optional[np.ndarray] = None
        self.display_frame: Optional[np.ndarray] = None
        self.fps: float = 30.0
        
        # CSV tracking data state
        self.csv_path: Optional[str] = None
        self.csv_data: Optional[Dict] = None  # {frame_num: {track_id: {player_name, bbox, team, jersey_number}}}
        
        # Player selection state
        self.selected_bbox: Optional[Tuple[int, int, int, int]] = None  # (x1, y1, x2, y2)
        self.click_start: Optional[Tuple[int, int]] = None
        
        # Gallery and Re-ID
        self.gallery = PlayerGallery()
        self.reid_tracker = None
        if REID_AVAILABLE:
            try:
                self.reid_tracker = ReIDTracker(feature_dim=128, similarity_threshold=0.6, use_torchreid=True)
                print("✓ Re-ID tracker initialized for feature extraction")
            except Exception as e:
                print(f"⚠ Could not initialize Re-ID: {e}")
        
        # ANCHOR FRAMES: Store frame-specific player tags with 1.00 confidence
        # Format: {frame_num: [{track_id (or None), player_name, bbox: [x1, y1, x2, y2], confidence: 1.00, team}]}
        self.anchor_frames = {}  # frame_num -> list of anchor player tags
        
        # Player identity protection: track when players were last manually tagged
        # Format: {player_name: (last_tagged_frame, bbox)}
        # This prevents overwriting recently tagged players for at least 2 frames
        self.player_tag_protection = {}  # player_name -> (frame_num, bbox)
        self.tag_protection_frames = 2  # Protect player identity for N frames after manual tagging
        
        # YOLO model for player detection (lazy loaded)
        self.yolo_model = None
        self.detected_players = []  # List of detected player bboxes for current frame
        self.detected_player_matches = {}  # Map bbox to (player_id, player_name, similarity) if matched
        self.detected_boxes_display_coords = {}  # Map bbox to (sx1, sy1, sx2, sy2) display coordinates for click detection
        
        # Scale factor for display
        self.scale_factor = 1.0
        
        # Zoom and pan state
        self.zoom_level = 1.0  # 1.0 = fit to window, >1.0 = zoomed in
        self.pan_x = 0  # Pan offset in pixels
        self.pan_y = 0
        self.pan_start = None  # For pan dragging
        self.pan_mode = False  # True when right-click dragging for pan
        
        # Event marker system
        if EVENT_MARKER_AVAILABLE:
            self.event_marker_system = EventMarkerSystem(video_path=self.video_path)
            self.event_marker_visible = tk.BooleanVar(value=True)
            self.current_event_type = tk.StringVar(value="pass")
        else:
            self.event_marker_system = None
        
        self.create_widgets()
        self.update_gallery_list()
        self.update_player_dropdown()
    
    def create_widgets(self):
        """Create GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Top controls
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(control_frame, text="Load Video", command=self.load_video).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Load CSV", command=self.load_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="View Gallery", command=self.show_gallery_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Help", command=self.show_help).pack(side=tk.LEFT, padx=5)
        
        self.video_label = ttk.Label(control_frame, text="No video loaded")
        self.video_label.pack(side=tk.LEFT, padx=20)
        
        self.csv_label = ttk.Label(control_frame, text="No CSV loaded", foreground="gray")
        self.csv_label.pack(side=tk.LEFT, padx=20)
        
        # Content area (side by side)
        content_frame = ttk.Frame(main_frame)
        content_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=3)  # Video gets more space
        content_frame.columnconfigure(1, weight=1)  # Sidebar
        content_frame.rowconfigure(0, weight=1)
        
        # Left: Video display
        video_frame = ttk.LabelFrame(content_frame, text="Video Frame", padding="10")
        video_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        video_frame.columnconfigure(0, weight=1)
        video_frame.rowconfigure(0, weight=1)
        
        # Canvas for video display
        self.canvas = tk.Canvas(video_frame, bg='black', cursor="crosshair")
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_click_start)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_click_end)
        # Pan support (right-click or middle-click)
        self.canvas.bind("<ButtonPress-3>", self.on_pan_start)
        self.canvas.bind("<B3-Motion>", self.on_pan_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_pan_end)
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_pan_end)
        # Mouse wheel zoom
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)  # Linux
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)  # Linux
        
        # Video controls
        video_controls = ttk.Frame(video_frame)
        video_controls.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        video_controls.columnconfigure(2, weight=1)
        
        ttk.Button(video_controls, text="◀◀", command=lambda: self.skip_frames(-30), width=5).grid(row=0, column=0)
        ttk.Button(video_controls, text="◀", command=lambda: self.skip_frames(-1), width=5).grid(row=0, column=1)
        
        self.frame_slider = ttk.Scale(video_controls, from_=0, to=100, orient=tk.HORIZONTAL, command=self.on_slider_change)
        self.frame_slider.grid(row=0, column=2, sticky=(tk.W, tk.E), padx=10)
        
        ttk.Button(video_controls, text="▶", command=lambda: self.skip_frames(1), width=5).grid(row=0, column=3)
        ttk.Button(video_controls, text="▶▶", command=lambda: self.skip_frames(30), width=5).grid(row=0, column=4)
        
        self.frame_label = ttk.Label(video_controls, text="Frame: 0 / 0")
        self.frame_label.grid(row=1, column=0, columnspan=5, pady=(5, 0))
        
        # Zoom controls (row 2)
        zoom_frame = ttk.Frame(video_controls)
        zoom_frame.grid(row=2, column=0, columnspan=5, pady=(10, 0))
        
        ttk.Label(zoom_frame, text="Zoom:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(zoom_frame, text="🔍−", command=self.zoom_out, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="🔍+", command=self.zoom_in, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Fit", command=self.zoom_fit, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="1:1", command=self.zoom_actual, width=6).pack(side=tk.LEFT, padx=2)
        
        self.zoom_label = ttk.Label(zoom_frame, text="100%", foreground="blue")
        self.zoom_label.pack(side=tk.LEFT, padx=(10, 0))
        
        ttk.Label(zoom_frame, text="|", foreground="gray").pack(side=tk.LEFT, padx=(20, 5))
        
        # YOLO detection button
        ttk.Button(zoom_frame, text="🔍 YOLO Detect", command=self.on_yolo_detect, width=12).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(zoom_frame, text="| Pan: Right-click & drag", foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=(5, 0))
        
        # Right: Player tagging sidebar
        sidebar_frame = ttk.LabelFrame(content_frame, text="Tag Player", padding="10")
        sidebar_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Instructions
        instructions = """1. Draw a box around a player
2. Select from dropdown OR type new name
3. Click "Add to Gallery"

The player will be recognized
in all future videos!"""
        ttk.Label(sidebar_frame, text=instructions, justify=tk.LEFT, wraplength=200, foreground="blue", font=("Arial", 9)).pack(pady=(0, 15))
        
        # Player selection dropdown
        ttk.Label(sidebar_frame, text="Select Existing Player:").pack(anchor=tk.W)
        self.player_dropdown = ttk.Combobox(sidebar_frame, width=23, state="readonly")
        self.player_dropdown.pack(fill=tk.X, pady=(5, 5))
        self.player_dropdown.bind("<<ComboboxSelected>>", self.on_player_selected)
        
        ttk.Label(sidebar_frame, text="OR type new name:", font=("Arial", 8, "italic"), foreground="gray").pack(anchor=tk.W, pady=(5, 0))
        
        # Player name input
        ttk.Label(sidebar_frame, text="Player Name:").pack(anchor=tk.W, pady=(5, 0))
        self.name_entry = ttk.Entry(sidebar_frame, width=25)
        self.name_entry.pack(fill=tk.X, pady=(5, 10))
        self.name_entry.bind('<KeyRelease>', lambda e: (self.update_add_button_state(), self.update_name_button_state()))
        
        ttk.Label(sidebar_frame, text="Jersey Number (optional):").pack(anchor=tk.W)
        self.jersey_entry = ttk.Entry(sidebar_frame, width=25)
        self.jersey_entry.pack(fill=tk.X, pady=(5, 10))
        
        ttk.Label(sidebar_frame, text="Team (optional):").pack(anchor=tk.W)
        self.team_entry = ttk.Entry(sidebar_frame, width=25)
        self.team_entry.pack(fill=tk.X, pady=(5, 10))
        
        # Visualization settings (collapsible section)
        viz_separator = ttk.Separator(sidebar_frame, orient=tk.HORIZONTAL)
        viz_separator.pack(fill=tk.X, pady=(5, 5))
        
        viz_label = ttk.Label(sidebar_frame, text="Visualization Settings (Optional)", font=("Arial", 9, "bold"))
        viz_label.pack(anchor=tk.W, pady=(5, 5))
        
        # Custom color - Color Picker
        from color_picker_utils import create_color_picker_widget
        self.viz_color_var = tk.StringVar()
        color_picker_frame, _ = create_color_picker_widget(
            sidebar_frame,
            self.viz_color_var,
            label_text="Custom Color:",
            initial_color=None,
            on_change_callback=None
        )
        color_picker_frame.pack(fill=tk.X, pady=(2, 5))
        
        # Box thickness
        thickness_frame = ttk.Frame(sidebar_frame)
        thickness_frame.pack(fill=tk.X, pady=(2, 5))
        ttk.Label(thickness_frame, text="Box Thickness:", font=("Arial", 8)).pack(side=tk.LEFT)
        self.viz_box_thickness = tk.IntVar(value=2)
        ttk.Spinbox(thickness_frame, from_=1, to=10, textvariable=self.viz_box_thickness, width=8).pack(side=tk.LEFT, padx=(5, 0))
        
        # Show glow
        self.viz_show_glow = tk.BooleanVar(value=False)
        ttk.Checkbutton(sidebar_frame, text="Show Glow Effect", variable=self.viz_show_glow, font=("Arial", 8)).pack(anchor=tk.W, pady=(2, 2))
        
        # Glow intensity
        glow_frame = ttk.Frame(sidebar_frame)
        glow_frame.pack(fill=tk.X, pady=(2, 5))
        ttk.Label(glow_frame, text="Glow Intensity:", font=("Arial", 8)).pack(side=tk.LEFT)
        self.viz_glow_intensity = tk.IntVar(value=50)
        ttk.Spinbox(glow_frame, from_=0, to=100, textvariable=self.viz_glow_intensity, width=8).pack(side=tk.LEFT, padx=(5, 0))
        
        # Show trail
        self.viz_show_trail = tk.BooleanVar(value=False)
        ttk.Checkbutton(sidebar_frame, text="Show Movement Trail", variable=self.viz_show_trail, font=("Arial", 8)).pack(anchor=tk.W, pady=(2, 2))
        
        # Label style
        label_style_frame = ttk.Frame(sidebar_frame)
        label_style_frame.pack(fill=tk.X, pady=(2, 10))
        ttk.Label(label_style_frame, text="Label Style:", font=("Arial", 8)).pack(side=tk.LEFT)
        self.viz_label_style = tk.StringVar(value="full_name")
        ttk.Combobox(label_style_frame, textvariable=self.viz_label_style, 
                    values=["full_name", "jersey", "initials", "number"], 
                    width=12, state="readonly").pack(side=tk.LEFT, padx=(5, 0))
        
        # Add button
        self.add_button = ttk.Button(sidebar_frame, text="Add to Gallery", command=self.add_player_to_gallery, state=tk.DISABLED)
        self.add_button.pack(fill=tk.X, pady=(0, 5))
        
        # Update/Correct Name button (for detected players with wrong names)
        self.update_name_button = ttk.Button(sidebar_frame, text="Update Name", command=self.update_detected_player_name, state=tk.DISABLED)
        self.update_name_button.pack(fill=tk.X, pady=(0, 5))
        
        # Clear match button (for correcting incorrect YOLO matches)
        self.clear_match_button = ttk.Button(sidebar_frame, text="Clear Match", command=self.clear_selected_match, state=tk.DISABLED)
        self.clear_match_button.pack(fill=tk.X)
        
        # Selection info
        self.selection_label = ttk.Label(sidebar_frame, text="No player selected", foreground="gray")
        self.selection_label.pack(pady=(10, 0))
        
        # Event Marker System controls (if available)
        if EVENT_MARKER_AVAILABLE and self.event_marker_system:
            marker_separator = ttk.Separator(sidebar_frame, orient=tk.HORIZONTAL)
            marker_separator.pack(fill=tk.X, pady=(10, 5))
            
            marker_label = ttk.Label(sidebar_frame, text="Event Markers", font=("Arial", 9, "bold"))
            marker_label.pack(anchor=tk.W, pady=(5, 5))
            
            # Event type selector
            ttk.Label(sidebar_frame, text="Event Type:", font=("Arial", 8)).pack(anchor=tk.W, pady=2)
            event_type_combo = ttk.Combobox(sidebar_frame, textvariable=self.current_event_type,
                                           values=["pass", "shot", "goal", "tackle", "save", "corner", 
                                                  "free_kick", "penalty", "offside", "custom"],
                                           state="readonly", width=22)
            event_type_combo.pack(fill=tk.X, pady=2)
            
            # Marker buttons
            marker_buttons_frame = ttk.Frame(sidebar_frame)
            marker_buttons_frame.pack(fill=tk.X, pady=5)
            
            ttk.Button(marker_buttons_frame, text="➕ Mark", 
                      command=self.mark_event_at_current_frame).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            ttk.Button(marker_buttons_frame, text="➖ Remove", 
                      command=self.remove_event_at_current_frame).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            
            # Marker management buttons
            marker_mgmt_frame = ttk.Frame(sidebar_frame)
            marker_mgmt_frame.pack(fill=tk.X, pady=5)
            
            ttk.Button(marker_mgmt_frame, text="💾 Save", 
                      command=self.save_event_markers).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            ttk.Button(marker_mgmt_frame, text="📂 Load", 
                      command=self.load_event_markers).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            
            # Marker statistics
            self.marker_stats_label = ttk.Label(sidebar_frame, text="Markers: 0", 
                                               font=("Arial", 8), foreground="gray")
            self.marker_stats_label.pack(anchor=tk.W, pady=2)
        
        # Gallery stats
        ttk.Separator(sidebar_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)
        
        self.gallery_stats_frame = ttk.Frame(sidebar_frame)
        self.gallery_stats_frame.pack(fill=tk.X)
        
        ttk.Label(self.gallery_stats_frame, text="Gallery:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.gallery_stats_label = ttk.Label(self.gallery_stats_frame, text="0 players", foreground="blue")
        self.gallery_stats_label.pack(anchor=tk.W, pady=(5, 10))
        
        # Recent additions list
        ttk.Label(self.gallery_stats_frame, text="Recent Additions:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 5))
        self.recent_listbox = tk.Listbox(self.gallery_stats_frame, height=8, font=("Arial", 9))
        self.recent_listbox.pack(fill=tk.BOTH, expand=True)
        self.recent_listbox.bind('<Double-Button-1>', self.on_player_double_click)
        
        ttk.Label(self.gallery_stats_frame, text="(Double-click to view/edit)", font=("Arial", 7, "italic"), foreground="gray").pack(anchor=tk.W, pady=(2, 0))
    
    def update_player_dropdown(self):
        """Update the player dropdown with all gallery players"""
        try:
            # Check if widget still exists (window might be closed)
            if not hasattr(self, 'player_dropdown') or not self.player_dropdown.winfo_exists():
                return
            
            # Get all players sorted alphabetically
            all_players = self.gallery.list_players()
            if all_players:
                # Extract names from tuples (player_id, player_name)
                player_names = sorted([p[1] for p in all_players])
                self.player_dropdown['values'] = ["-- New Player --"] + player_names
            else:
                self.player_dropdown['values'] = ["-- New Player --"]
            
            # Set default selection
            self.player_dropdown.current(0)
        except tk.TclError as e:
            # Widget was destroyed - this is expected if window is closed
            if "invalid command name" not in str(e):
                print(f"⚠ Could not update player dropdown: {e}")
        except Exception as e:
            print(f"⚠ Could not update player dropdown: {e}")
    
    def on_player_selected(self, event):
        """Handle player selection from dropdown"""
        selected = self.player_dropdown.get()
        
        if selected == "-- New Player --":
            # Clear all fields
            self.name_entry.delete(0, tk.END)
            self.jersey_entry.delete(0, tk.END)
            self.team_entry.delete(0, tk.END)
        else:
            # Find player in gallery and populate fields
            try:
                all_players = self.gallery.list_players()
                for player_id, player_name in all_players:
                    if player_name == selected:
                        profile = self.gallery.get_player(player_id)
                        if profile:
                            self.name_entry.delete(0, tk.END)
                            self.name_entry.insert(0, profile.name)
                            
                            self.jersey_entry.delete(0, tk.END)
                            if profile.jersey_number:
                                self.jersey_entry.insert(0, profile.jersey_number)
                            
                            self.team_entry.delete(0, tk.END)
                            if profile.team:
                                self.team_entry.insert(0, profile.team)
                            
                            # Load visualization settings
                            if profile.visualization_settings:
                                viz = profile.visualization_settings
                                if viz.get("custom_color_rgb"):
                                    rgb = viz["custom_color_rgb"]
                                    if isinstance(rgb, list) and len(rgb) == 3:
                                        self.viz_color_var.set(f"{rgb[0]},{rgb[1]},{rgb[2]}")
                                    else:
                                        self.viz_color_var.set("")
                                else:
                                    self.viz_color_var.set("")
                                
                                self.viz_box_thickness.set(viz.get("box_thickness", 2))
                                self.viz_show_glow.set(viz.get("show_glow", False))
                                self.viz_glow_intensity.set(viz.get("glow_intensity", 50))
                                self.viz_show_trail.set(viz.get("show_trail", False))
                                self.viz_label_style.set(viz.get("label_style", "full_name"))
                            else:
                                # Reset to defaults
                                self.viz_color_var.set("")
                                self.viz_box_thickness.set(2)
                                self.viz_show_glow.set(False)
                                self.viz_glow_intensity.set(50)
                                self.viz_show_trail.set(False)
                                self.viz_label_style.set("full_name")
                            break
            except Exception as e:
                print(f"⚠ Could not load player data: {e}")
        
        self.update_add_button_state()
    
    def load_video(self):
        """Load a video file"""
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        # Load existing anchor frames for this video
        self.load_existing_anchor_frames(file_path)
        
        try:
            # Close previous video if exists
            if self.cap:
                self.cap.release()
            
            # Open new video
            self.cap = cv2.VideoCapture(file_path)
            self.video_path = file_path
            
            # Update event marker system video path
            if EVENT_MARKER_AVAILABLE and self.event_marker_system:
                self.event_marker_system.video_path = self.video_path
                # Try to auto-load markers
                video_dir = os.path.dirname(os.path.abspath(self.video_path))
                video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
                marker_path = os.path.join(video_dir, f"{video_basename}_event_markers.json")
                if os.path.exists(marker_path):
                    self.event_marker_system.load_from_file(marker_path)
                    if hasattr(self, 'marker_stats_label'):
                        self.update_marker_statistics()
            
            # Get video properties
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # Update UI
            video_name = os.path.basename(file_path)
            self.video_label.config(text=f"✓ Loaded: {video_name} ({self.total_frames} frames @ {self.fps:.1f} fps)")
            
            # Configure slider
            self.frame_slider.config(to=self.total_frames - 1)
            
            # Load first frame
            self.load_frame(0)
            
            print(f"✓ Loaded video: {video_name} ({self.total_frames} frames @ {self.fps:.1f} fps)")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load video:\n\n{str(e)}")
            print(f"⚠ Error loading video: {e}")
            traceback.print_exc()
    
    def load_frame(self, frame_num: int):
        """Load and display a specific frame"""
        if not self.cap:
            return
        
        # Clamp frame number
        frame_num = max(0, min(frame_num, self.total_frames - 1))
        
        # Clear previous detections if frame changed
        if frame_num != self.current_frame_num:
            self.detected_players = []
            self.detected_player_matches = {}
            self.detected_boxes_display_coords = {}
            
            # CRITICAL: Check for protected players in anchor frames for this frame
            # If a player was tagged in this frame or nearby frames, restore their identity
            if frame_num in self.anchor_frames:
                for anchor in self.anchor_frames[frame_num]:
                    player_name = anchor.get('player_name')
                    anchor_bbox = anchor.get('bbox')
                    if player_name and anchor_bbox:
                        # Restore protection for this player at this frame
                        self.player_tag_protection[player_name] = (frame_num, tuple(anchor_bbox))
                        print(f"✓ Restored protected player '{player_name}' from anchor frame {frame_num}")
        
        # Seek to frame
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.cap.read()
        
        if not ret:
            print(f"⚠ Could not read frame {frame_num}")
            return
        
        # Store frame
        self.current_frame_num = frame_num
        self.current_frame = frame
        
        # Update slider if it exists
        try:
            if hasattr(self, 'frame_slider') and self.frame_slider.winfo_exists():
                self.frame_slider.set(frame_num)
        except tk.TclError:
            pass
        
        # Update frame label if it exists
        try:
            if hasattr(self, 'frame_label') and self.frame_label.winfo_exists():
                self.frame_label.config(text=f"Frame: {frame_num} / {self.total_frames - 1}")
        except tk.TclError:
            pass
        
        # Display the frame on canvas
        self.display_frame_on_canvas()
    
    def jump_to_frame(self, frame_num: int, video_path: Optional[str] = None, 
                     highlight_bbox: Optional[Tuple[int, int, int, int]] = None,
                     detect_all_players: bool = False):
        """
        Jump to a specific frame number, optionally loading video if not loaded
        
        Args:
            frame_num: Frame number to jump to
            video_path: Optional video path (loads if different from current)
            highlight_bbox: Optional bbox (x1, y1, x2, y2) to highlight the player
            detect_all_players: If True, run YOLO detection to show all players in frame
        """
        # If video path provided and different from current, load it
        if video_path and video_path != self.video_path:
            try:
                # Close previous video if exists
                if self.cap:
                    self.cap.release()
                
                # Open new video
                self.cap = cv2.VideoCapture(video_path)
                self.video_path = video_path
                
                # Get video properties
                self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                
                # Update UI
                video_name = os.path.basename(video_path)
                if hasattr(self, 'video_label') and self.video_label.winfo_exists():
                    self.video_label.config(text=f"✓ Loaded: {video_name} ({self.total_frames} frames @ {self.fps:.1f} fps)")
                
                # Configure slider
                if hasattr(self, 'frame_slider') and self.frame_slider.winfo_exists():
                    self.frame_slider.config(to=self.total_frames - 1)
                
                # Load existing anchor frames
                self.load_existing_anchor_frames(video_path)
            except Exception as e:
                print(f"⚠ Could not load video: {e}")
                return False
        
        # Jump to frame
        if self.cap:
            self.load_frame(frame_num)
            
            # Set highlighted bbox if provided
            if highlight_bbox:
                self.selected_bbox = highlight_bbox
                # Auto-pan to center the highlighted player
                x1, y1, x2, y2 = highlight_bbox
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                # Center the view on this player
                frame_width = self.current_frame.shape[1]
                frame_height = self.current_frame.shape[0]
                self.pan_x = (frame_width / 2 - center_x) * self.scale_factor
                self.pan_y = (frame_height / 2 - center_y) * self.scale_factor
            
            # Detect all players if requested
            if detect_all_players:
                self.detect_players_in_frame()
            
            self.display_frame_on_canvas()
            
            # Update frame label if it exists
            try:
                if hasattr(self, 'frame_label') and self.frame_label.winfo_exists():
                    self.frame_label.config(text=f"Frame: {frame_num} / {self.total_frames - 1}")
            except tk.TclError:
                pass
            
            return True
        
        return False
    
    def detect_players_in_frame(self):
        """Detect all players in the current frame using YOLO with anchor frame protection"""
        if self.current_frame is None:
            return
        
        # YOLO detection confidence threshold (lowered for better detection)
        detection_confidence = 0.15  # Lowered from 0.25 to detect players that are far away or partially occluded
        
        try:
            # Lazy load YOLO model
            if self.yolo_model is None:
                try:
                    from ultralytics import YOLO
                    # Try to load YOLO model (use yolo11n.pt or yolo11s.pt if available)
                    model_paths = ['yolo11n.pt', 'yolo11s.pt', 'yolov8n.pt', 'yolov8s.pt']
                    self.yolo_model = None
                    for model_path in model_paths:
                        try:
                            self.yolo_model = YOLO(model_path)
                            print(f"✓ Loaded YOLO model: {model_path}")
                            break
                        except:
                            continue
                    
                    if self.yolo_model is None:
                        print("⚠ Could not load YOLO model - player detection disabled")
                        self.detected_players = []
                        return
                except ImportError:
                    print("⚠ YOLO not available - install with: pip install ultralytics")
                    self.detected_players = []
                    return
            
            # 🛡️ CRITICAL: Build anchor protection map for current frame
            # Check ALL anchor frames and find which players are protected at this frame
            # Protection window: anchor frame ± 150 frames (same as main analysis)
            ANCHOR_PROTECTION_WINDOW = 150
            protected_players_by_position = {}  # (x1, y1, x2, y2) -> (player_name, anchor_frame, confidence: 1.00)
            player_anchor_protection = {}  # player_name -> list of (start_frame, end_frame, bbox)
            
            for anchor_frame_num, anchors in self.anchor_frames.items():
                # Convert frame number to int (JSON keys are strings)
                try:
                    anchor_frame_num = int(anchor_frame_num)
                except (ValueError, TypeError):
                    continue  # Skip invalid frame numbers
                
                for anchor in anchors:
                    player_name = anchor.get('player_name')
                    anchor_bbox = anchor.get('bbox')
                    if player_name and anchor_bbox:
                        # Calculate protection window
                        protection_start = max(0, anchor_frame_num - ANCHOR_PROTECTION_WINDOW)
                        protection_end = anchor_frame_num + ANCHOR_PROTECTION_WINDOW
                        
                        # If current frame is within protection window, this player is protected
                        if protection_start <= self.current_frame_num <= protection_end:
                            # Store protection info
                            if player_name not in player_anchor_protection:
                                player_anchor_protection[player_name] = []
                            player_anchor_protection[player_name].append((protection_start, protection_end, tuple(anchor_bbox)))
                            
                            # Also store by position for quick lookup
                            bbox_key = tuple(anchor_bbox)
                            if bbox_key not in protected_players_by_position:
                                protected_players_by_position[bbox_key] = []
                            protected_players_by_position[bbox_key].append((player_name, anchor_frame_num, 1.00))
            
            # Run detection with lower confidence threshold for better detection
            results = self.yolo_model(self.current_frame, conf=detection_confidence, classes=[0])  # class 0 = person
            
            # Log detection attempt
            if self.current_frame_num % 50 == 0 or self.current_frame_num == 409:
                print(f"🔍 YOLO Detection (Frame {self.current_frame_num}): confidence={detection_confidence}, frame_size={self.current_frame.shape}")
            
            # Extract player bounding boxes and match with gallery
            raw_detections = []
            detection_features = {}  # bbox -> feature_vector
            self.detected_player_matches = {}
            self.detected_boxes_display_coords = {}
            
            # Track which players have already been assigned (prevent duplicates)
            assigned_players = set()  # player_name -> True if already assigned to a detection
            
            frame_height, frame_width = self.current_frame.shape[:2]
            
            if results and len(results) > 0:
                boxes = results[0].boxes
                if boxes is not None and len(boxes) > 0:
                    for box in boxes:
                        # Get bbox coordinates (xyxy format)
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        
                        # CRITICAL FIX: Filter out balls and small objects
                        # Balls are typically much smaller than players
                        bbox_width = x2 - x1
                        bbox_height = y2 - y1
                        bbox_area = bbox_width * bbox_height
                        aspect_ratio = bbox_height / bbox_width if bbox_width > 0 else 0
                        
                        # 🚫 AGGRESSIVE BALL FILTERING: Filter out balls and small objects
                        # Balls are being detected as players even when out of bounds
                        # Filter criteria (more aggressive to prevent ball detection):
                        # 1. Minimum area: 3000 pixels (balls are usually < 2000 pixels, increased from 2000)
                        # 2. Minimum height: 80 pixels (players are taller, increased from 60)
                        # 3. Aspect ratio: Players are typically taller than wide (ratio > 1.3)
                        #    Balls are roughly circular (ratio ~ 0.8-1.2)
                        min_area = 3000  # pixels (increased from 2000 to be more aggressive)
                        min_height = 80  # pixels (increased from 60 to be more aggressive)
                        min_aspect_ratio = 1.3  # Players are taller than wide (increased from 1.1)
                        
                        # Additional check: If it's small AND circular, definitely a ball
                        max_aspect_ratio_for_ball = 1.2  # Balls are roughly circular
                        if bbox_area < 2000 and 0.8 <= aspect_ratio <= max_aspect_ratio_for_ball:
                            # Small and circular = definitely a ball
                            continue
                        
                        if bbox_area < min_area or bbox_height < min_height or aspect_ratio < min_aspect_ratio:
                            # Likely a ball or small object - skip it
                            continue
                        
                        # CRITICAL FIX: Expand bbox slightly to better fit players and make them easier to click
                        # YOLO boxes can be tight, so expand by 5% on each side for better visibility
                        expand_x = bbox_width * 0.05  # 5% expansion horizontally
                        expand_y = bbox_height * 0.05  # 5% expansion vertically
                        
                        # Expand bbox (clamp to frame bounds)
                        x1_expanded = max(0, int(x1 - expand_x))
                        y1_expanded = max(0, int(y1 - expand_y))
                        x2_expanded = min(frame_width, int(x2 + expand_x))
                        y2_expanded = min(frame_height, int(y2 + expand_y))
                        
                        bbox = (x1_expanded, y1_expanded, x2_expanded, y2_expanded)
                        raw_detections.append(bbox)
                        
                        # Extract Re-ID features for all detections (needed for duplicate detection)
                        # CRITICAL: Use original (non-expanded) bbox for Re-ID feature extraction (more accurate)
                        if self.reid_tracker is not None and SUPERVISION_AVAILABLE:
                            try:
                                # Use original YOLO bbox for feature extraction (not expanded)
                                x1_int, y1_int, x2_int, y2_int = int(x1), int(y1), int(x2), int(y2)
                                # Clamp to frame bounds
                                x1_int = max(0, min(x1_int, self.current_frame.shape[1]))
                                y1_int = max(0, min(y1_int, self.current_frame.shape[0]))
                                x2_int = max(0, min(x2_int, self.current_frame.shape[1]))
                                y2_int = max(0, min(y2_int, self.current_frame.shape[0]))
                                
                                if x2_int > x1_int and y2_int > y1_int:
                                    # Create a supervision Detections object for this single detection
                                    xyxy = np.array([[x1_int, y1_int, x2_int, y2_int]], dtype=np.float32)
                                    detections = sv.Detections(xyxy=xyxy)
                                    
                                    # Extract features using the Re-ID tracker
                                    features = self.reid_tracker.extract_features(self.current_frame, detections)
                                    
                                    if features is not None and len(features) > 0 and features.shape[0] > 0:
                                        # Store feature vector for this detection
                                        feature_vector = features[0]
                                        detection_features[bbox] = feature_vector
                                        
                                        # 🛡️ CRITICAL: Check anchor frame protection FIRST (before gallery matching)
                                        # If this detection matches an anchor-protected player, use that with 1.00 confidence
                                        anchor_match = None
                                        anchor_player_name = None
                                        anchor_confidence = 0.0
                                        
                                        # Check if this bbox position matches any anchor-protected player
                                        x1_curr, y1_curr, x2_curr, y2_curr = bbox
                                        for protected_name, protection_list in player_anchor_protection.items():
                                            # Skip if this player is already assigned to another detection
                                            if protected_name in assigned_players:
                                                continue
                                            
                                            for prot_start, prot_end, prot_bbox in protection_list:
                                                # Check if current frame is within protection window
                                                if prot_start <= self.current_frame_num <= prot_end:
                                                    # Calculate IoU between current bbox and protected bbox
                                                    x1_prot, y1_prot, x2_prot, y2_prot = prot_bbox
                                                    
                                                    # Calculate center of both bboxes
                                                    center_x_curr = (x1_curr + x2_curr) / 2
                                                    center_y_curr = (y1_curr + y2_curr) / 2
                                                    center_x_prot = (x1_prot + x2_prot) / 2
                                                    center_y_prot = (y1_prot + y2_prot) / 2
                                                    
                                                    # Calculate center distance (players can move between frames)
                                                    center_distance = ((center_x_curr - center_x_prot) ** 2 + (center_y_curr - center_y_prot) ** 2) ** 0.5
                                                    
                                                    # Calculate IoU between current bbox and protected bbox
                                                    x1_i = max(x1_curr, x1_prot)
                                                    y1_i = max(y1_curr, y1_prot)
                                                    x2_i = min(x2_curr, x2_prot)
                                                    y2_i = min(y2_curr, y2_prot)
                                                    
                                                    iou = 0.0
                                                    if x2_i > x1_i and y2_i > y1_i:
                                                        intersection = (x2_i - x1_i) * (y2_i - y1_i)
                                                        area_curr = (x2_curr - x1_curr) * (y2_curr - y1_curr)
                                                        area_prot = (x2_prot - x1_prot) * (y2_prot - y1_prot)
                                                        union = area_curr + area_prot - intersection
                                                        iou = intersection / union if union > 0 else 0.0
                                                    
                                                    # LENIENT MATCHING: Accept if IoU > 0.05 OR center distance < 200px
                                                    # This handles cases where players move between frames
                                                    # Players tagged in frame 0 should be protected for the entire video
                                                    if iou > 0.05 or center_distance < 200:
                                                        anchor_match = True
                                                        anchor_player_name = protected_name
                                                        anchor_confidence = 1.00  # Anchor frames are ground truth
                                                        if self.current_frame_num % 10 == 0:  # Log every 10 frames to avoid spam
                                                            print(f"🛡️ ANCHOR MATCH: Frame {self.current_frame_num}, '{protected_name}' (IoU: {iou:.2f}, distance: {center_distance:.1f}px)")
                                                        break
                                            
                                            if anchor_match:
                                                break
                                        
                                        # If anchor match found, use it with 1.00 confidence
                                        if anchor_match and anchor_player_name:
                                            # Find player ID
                                            anchor_player_id = None
                                            for pid, pname in self.gallery.list_players():
                                                if pname.lower() == anchor_player_name.lower():
                                                    anchor_player_id = pid
                                                    break
                                            
                                            if anchor_player_id:
                                                self.detected_player_matches[bbox] = (anchor_player_id, anchor_player_name, anchor_confidence)
                                                assigned_players.add(anchor_player_name)  # Mark as assigned
                                                if self.current_frame_num % 10 == 0:  # Log every 10 frames to avoid spam
                                                    print(f"🛡️ ANCHOR PROTECTION: Frame {self.current_frame_num}, '{anchor_player_name}' forced with 1.00 confidence (IoU match)")
                                            else:
                                                # Player not in gallery yet - still mark as protected
                                                self.detected_player_matches[bbox] = (None, anchor_player_name, anchor_confidence)
                                                assigned_players.add(anchor_player_name)
                                                if self.current_frame_num % 10 == 0:
                                                    print(f"🛡️ ANCHOR PROTECTION: Frame {self.current_frame_num}, '{anchor_player_name}' forced with 1.00 confidence (not in gallery yet)")
                                        else:
                                            # No anchor match - try gallery matching
                                            if self.gallery is not None:
                                                match_result = self.gallery.match_player(
                                                    feature_vector,
                                                    similarity_threshold=0.5  # Lower threshold for display
                                                )
                                                
                                                if match_result[0] is not None:  # Found a match
                                                    player_id, player_name, similarity = match_result
                                                    
                                                    # Check if this player is already assigned (prevent duplicates)
                                                    if player_name in assigned_players:
                                                        # Skip - this player is already assigned to another detection
                                                        if self.current_frame_num % 10 == 0:
                                                            print(f"⚠ Skipping duplicate assignment: '{player_name}' already assigned to another detection")
                                                        continue
                                                    
                                                    # Check if matched player conflicts with anchor protection
                                                    is_blocked = False
                                                    if player_name in player_anchor_protection:
                                                        # This player has anchor protection - check if we should block gallery match
                                                        for prot_start, prot_end, prot_bbox in player_anchor_protection[player_name]:
                                                            if prot_start <= self.current_frame_num <= prot_end:
                                                                # Player is protected - check if bbox matches
                                                                x1_prot, y1_prot, x2_prot, y2_prot = prot_bbox
                                                                x1_i = max(x1_curr, x1_prot)
                                                                y1_i = max(y1_curr, y1_prot)
                                                                x2_i = min(x2_curr, x2_prot)
                                                                y2_i = min(y2_curr, y2_prot)
                                                                
                                                                if x2_i > x1_i and y2_i > y1_i:
                                                                    intersection = (x2_i - x1_i) * (y2_i - y1_i)
                                                                    area_curr = (x2_curr - x1_curr) * (y2_curr - y1_curr)
                                                                    area_prot = (x2_prot - x1_prot) * (y2_prot - y1_prot)
                                                                    union = area_curr + area_prot - intersection
                                                                    iou = intersection / union if union > 0 else 0.0
                                                                    
                                                                    # If bbox doesn't match protected position, this might be wrong
                                                                    if iou < 0.1:
                                                                        # Bbox doesn't match - might be a different player
                                                                        # But if player is already assigned, block this
                                                                        if player_name in assigned_players:
                                                                            is_blocked = True
                                                                            break
                                                    
                                                    if not is_blocked:
                                                        self.detected_player_matches[bbox] = (player_id, player_name, similarity)
                                                        assigned_players.add(player_name)  # Mark as assigned
                                                    
                                                    # Also check temporary protection (recently tagged players)
                                                    for protected_name, (protected_frame, protected_bbox) in self.player_tag_protection.items():
                                                        frames_since_tag = self.current_frame_num - protected_frame
                                                        
                                                        # If tagged recently (within protection window), check position overlap
                                                        if frames_since_tag <= self.tag_protection_frames:
                                                            # Calculate IoU between current bbox and protected bbox
                                                            x1_prot, y1_prot, x2_prot, y2_prot = protected_bbox
                                                            
                                                            # Calculate intersection
                                                            x1_i = max(x1_curr, x1_prot)
                                                            y1_i = max(y1_curr, y1_prot)
                                                            x2_i = min(x2_curr, x2_prot)
                                                            y2_i = min(y2_curr, y2_prot)
                                                            
                                                            if x2_i > x1_i and y2_i > y1_i:
                                                                intersection = (x2_i - x1_i) * (y2_i - y1_i)
                                                                area_curr = (x2_curr - x1_curr) * (y2_curr - y1_curr)
                                                                area_prot = (x2_prot - x1_prot) * (y2_prot - y1_prot)
                                                                union = area_curr + area_prot - intersection
                                                                iou = intersection / union if union > 0 else 0.0
                                                                
                                                                # If significant overlap (IoU > 0.3), this might be the protected player
                                                                if iou > 0.3:
                                                                    # Check if matched player is different from protected player
                                                                    if player_name.lower() != protected_name.lower():
                                                                        # Gallery matched different player - block it if protected player is more recent
                                                                        if protected_name not in assigned_players:
                                                                            # Use protected player instead
                                                                            protected_player_id = None
                                                                            for pid, pname in self.gallery.list_players():
                                                                                if pname.lower() == protected_name.lower():
                                                                                    protected_player_id = pid
                                                                                    break
                                                                            if protected_player_id:
                                                                                # Remove gallery match and use protected player
                                                                                if bbox in self.detected_player_matches:
                                                                                    del self.detected_player_matches[bbox]
                                                                                if player_name in assigned_players:
                                                                                    assigned_players.remove(player_name)
                                                                                self.detected_player_matches[bbox] = (protected_player_id, protected_name, 1.0)  # High confidence for protected
                                                                                assigned_players.add(protected_name)
                                                                                if self.current_frame_num % 10 == 0:
                                                                                    print(f"⚠ Protected player '{protected_name}' at bbox {protected_bbox} - blocking gallery match '{player_name}' (IoU: {iou:.2f}, similarity: {similarity:.2f})")
                                                                                break
                                            
                                            # CSV DATA: If no match found and CSV is loaded, try to match by position/bbox
                                            if bbox not in self.detected_player_matches and self.csv_data is not None:
                                                csv_match = self.match_detection_to_csv(bbox, self.current_frame_num)
                                                if csv_match:
                                                    csv_player_name, csv_team, csv_jersey = csv_match
                                                    # Check if player is already assigned
                                                    if csv_player_name not in assigned_players:
                                                        # Find player ID in gallery
                                                        csv_player_id = None
                                                        for pid, pname in self.gallery.list_players():
                                                            if pname.lower() == csv_player_name.lower():
                                                                csv_player_id = pid
                                                                break
                                                        self.detected_player_matches[bbox] = (csv_player_id, csv_player_name, 0.9)  # High confidence from CSV
                                                        assigned_players.add(csv_player_name)
                                                        if self.current_frame_num % 10 == 0:
                                                            print(f"📋 CSV MATCH: Frame {self.current_frame_num}, '{csv_player_name}' from CSV data")
                                            
                            except Exception as e:
                                # Print error for debugging
                                print(f"  ⚠ Error extracting/matching features: {e}")
            
            # MERGE DUPLICATE DETECTIONS: Group detections of the same player
            # Use both IoU overlap and Re-ID similarity to identify duplicates
            self.detected_players = self._merge_duplicate_detections(raw_detections, detection_features)
            
            matched_count = len(self.detected_player_matches)
            print(f"✓ Detected {len(raw_detections)} raw detections, merged to {len(self.detected_players)} unique players ({matched_count} matched with gallery)")
            
            # Log if no players detected
            if len(self.detected_players) == 0:
                print(f"⚠ No players detected in frame {self.current_frame_num}")
                print(f"   → Frame size: {self.current_frame.shape}")
                print(f"   → YOLO confidence threshold: 0.15 (lowered for better detection)")
                if results and len(results) > 0:
                    boxes = results[0].boxes
                    if boxes is not None:
                        print(f"   → Raw YOLO boxes: {len(boxes)} (may have been filtered)")
                    else:
                        print(f"   → No boxes in YOLO results")
                else:
                    print(f"   → No YOLO results returned")
            
        except Exception as e:
            print(f"⚠ Error detecting players: {e}")
            import traceback
            traceback.print_exc()
            self.detected_players = []
    
    def _merge_duplicate_detections(self, detections: List[Tuple], features: Dict) -> List[Tuple]:
        """
        Merge duplicate detections of the same player using IoU overlap and Re-ID similarity.
        
        Args:
            detections: List of bounding boxes [(x1, y1, x2, y2), ...]
            features: Dict mapping bbox -> feature_vector
        
        Returns:
            List of merged/unique bounding boxes
        """
        if len(detections) <= 1:
            return detections
        
        # Calculate IoU between all pairs
        def calculate_iou(bbox1, bbox2):
            """Calculate Intersection over Union (IoU) between two bounding boxes"""
            x1_1, y1_1, x2_1, y2_1 = bbox1
            x1_2, y1_2, x2_2, y2_2 = bbox2
            
            # Calculate intersection
            x1_i = max(x1_1, x1_2)
            y1_i = max(y1_1, y1_2)
            x2_i = min(x2_1, x2_2)
            y2_i = min(y2_1, y2_2)
            
            if x2_i <= x1_i or y2_i <= y1_i:
                return 0.0
            
            intersection = (x2_i - x1_i) * (y2_i - y1_i)
            area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
            area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
            union = area1 + area2 - intersection
            
            return intersection / union if union > 0 else 0.0
        
        # Calculate Re-ID similarity between feature vectors
        def calculate_similarity(feat1, feat2):
            """Calculate cosine similarity between two feature vectors"""
            if feat1 is None or feat2 is None:
                return 0.0
            try:
                feat1_norm = feat1 / (np.linalg.norm(feat1) + 1e-8)
                feat2_norm = feat2 / (np.linalg.norm(feat2) + 1e-8)
                similarity = np.dot(feat1_norm, feat2_norm)
                return float(similarity)
            except:
                return 0.0
        
        # Group detections that are likely the same player
        merged = []
        used = set()
        
        for i, bbox1 in enumerate(detections):
            if i in used:
                continue
            
            # Find all detections that overlap significantly with this one
            group = [i]
            group_bboxes = [bbox1]
            
            for j, bbox2 in enumerate(detections[i+1:], start=i+1):
                if j in used:
                    continue
                
                # Check IoU overlap
                iou = calculate_iou(bbox1, bbox2)
                
                # Check Re-ID similarity if features available
                similarity = 0.0
                if bbox1 in features and bbox2 in features:
                    similarity = calculate_similarity(features[bbox1], features[bbox2])
                
                # Merge if high IoU (>0.5) OR high Re-ID similarity (>0.85)
                # This catches both overlapping boxes and non-overlapping detections of the same player
                if iou > 0.5 or similarity > 0.85:
                    group.append(j)
                    group_bboxes.append(bbox2)
                    used.add(j)
            
            # Merge the group: use the largest bbox (most complete view)
            if len(group) > 1:
                # Find largest bbox by area
                largest_idx = 0
                largest_area = 0
                for idx, bbox in enumerate(group_bboxes):
                    x1, y1, x2, y2 = bbox
                    area = (x2 - x1) * (y2 - y1)
                    if area > largest_area:
                        largest_area = area
                        largest_idx = idx
                
                merged_bbox = group_bboxes[largest_idx]
                merged.append(merged_bbox)
                
                # Update matches to use merged bbox
                if len(group) > 1:
                    # Transfer matches from merged detections to the merged bbox
                    for idx in group:
                        orig_bbox = detections[idx]
                        if orig_bbox in self.detected_player_matches:
                            # Use the match from the highest confidence detection
                            if merged_bbox not in self.detected_player_matches:
                                self.detected_player_matches[merged_bbox] = self.detected_player_matches[orig_bbox]
                            elif orig_bbox in self.detected_player_matches:
                                # Keep the match with higher similarity
                                existing_sim = self.detected_player_matches[merged_bbox][2] if len(self.detected_player_matches[merged_bbox]) > 2 else 0.0
                                new_sim = self.detected_player_matches[orig_bbox][2] if len(self.detected_player_matches[orig_bbox]) > 2 else 0.0
                                if new_sim > existing_sim:
                                    self.detected_player_matches[merged_bbox] = self.detected_player_matches[orig_bbox]
                
                print(f"  → Merged {len(group)} duplicate detections into one (IoU or similarity match)")
            else:
                merged.append(bbox1)
            
            used.add(i)
        
        return merged
    
    def on_yolo_detect(self):
        """Handle YOLO detection button click"""
        if self.current_frame is None:
            messagebox.showwarning("No Video", "Please load a video first.")
            return
        
        # Run detection
        self.detect_players_in_frame()
        
        # Refresh display to show detected players
        self.display_frame_on_canvas()
        
        # Show message
        if len(self.detected_players) > 0:
            messagebox.showinfo("Detection Complete", 
                              f"Detected {len(self.detected_players)} player(s) in this frame.\n"
                              "They are shown with orange/blue boxes.\n"
                              "Draw a box around a player to tag them.")
        else:
            messagebox.showinfo("Detection Complete", 
                              "No players detected in this frame.\n"
                              "Try adjusting the frame or zoom level.")
    
    def display_frame_on_canvas(self):
        """Display current frame on canvas with zoom and pan support"""
        if self.current_frame is None:
            return
        
        # Get canvas size
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            # Canvas not yet rendered, try again later
            self.root.after(100, self.display_frame_on_canvas)
            return
        
        # Calculate base scale factor to fit frame in canvas
        frame_height, frame_width = self.current_frame.shape[:2]
        scale_w = canvas_width / frame_width
        scale_h = canvas_height / frame_height
        base_scale = min(scale_w, scale_h, 1.0)  # Don't upscale beyond 1:1
        
        # Apply zoom level
        self.scale_factor = base_scale * self.zoom_level
        
        # Calculate display size with zoom
        display_width = int(frame_width * self.scale_factor)
        display_height = int(frame_height * self.scale_factor)
        
        # If zoomed in beyond canvas, crop to visible region with pan offset
        if display_width > canvas_width or display_height > canvas_height:
            # Calculate crop region in original frame coordinates
            visible_width = int(canvas_width / self.scale_factor)
            visible_height = int(canvas_height / self.scale_factor)
            
            # Center of view with pan offset
            center_x = frame_width / 2 - (self.pan_x / self.scale_factor)
            center_y = frame_height / 2 - (self.pan_y / self.scale_factor)
            
            # Calculate crop bounds
            x1 = int(max(0, center_x - visible_width / 2))
            y1 = int(max(0, center_y - visible_height / 2))
            x2 = int(min(frame_width, x1 + visible_width))
            y2 = int(min(frame_height, y1 + visible_height))
            
            # Adjust if we hit boundaries
            if x2 - x1 < visible_width:
                x1 = max(0, x2 - visible_width)
            if y2 - y1 < visible_height:
                y1 = max(0, y2 - visible_height)
            
            # Crop and resize
            cropped = self.current_frame[y1:y2, x1:x2]
            self.display_frame = cv2.resize(cropped, (canvas_width, canvas_height))
            
            # Adjust selection bbox for cropped view
            display_offset_x = x1
            display_offset_y = y1
        else:
            # Normal resize (zoomed out or fit)
            self.display_frame = cv2.resize(self.current_frame, (display_width, display_height))
            display_offset_x = 0
            display_offset_y = 0
        
        # Draw all detected players (if any)
        if self.detected_players:
            for player_bbox in self.detected_players:
                px1, py1, px2, py2 = player_bbox
                # Check if this is the highlighted player
                is_highlighted = (self.selected_bbox and 
                                abs(px1 - self.selected_bbox[0]) < 5 and 
                                abs(py1 - self.selected_bbox[1]) < 5 and
                                abs(px2 - self.selected_bbox[2]) < 5 and 
                                abs(py2 - self.selected_bbox[3]) < 5)
                
                # Check if this player is matched with gallery
                matched_info = self.detected_player_matches.get(player_bbox)
                player_name = None
                similarity = None
                if matched_info:
                    _, player_name, similarity = matched_info
                
                if is_highlighted:
                    # Highlighted player - draw with bright green, thicker line
                    color = (0, 255, 0)
                    thickness = 3
                elif matched_info:
                    # Matched player - draw with cyan, medium thickness
                    color = (255, 255, 0)  # Cyan for matched players
                    thickness = 2
                else:
                    # Other players - draw with orange, thinner line
                    color = (255, 200, 0)  # Orange for unmatched
                    thickness = 1
                
                # Draw bbox (adjusted for zoom/pan)
                if display_width > canvas_width or display_height > canvas_height:
                    # Zoomed in - cropped region is resized to canvas size
                    # Calculate actual crop dimensions
                    crop_width = x2 - x1 if display_width > canvas_width else frame_width
                    crop_height = y2 - y1 if display_height > canvas_height else frame_height
                    
                    # CRITICAL FIX: Check if player bbox OVERLAPS with cropped region (not just contained)
                    # A bbox is visible if it overlaps the crop region at all
                    bbox_overlaps = not (px2 < display_offset_x or px1 > display_offset_x + crop_width or
                                        py2 < display_offset_y or py1 > display_offset_y + crop_height)
                    
                    if bbox_overlaps:
                        # Convert frame coordinates to display coordinates
                        # The cropped region [x1:x2, y1:y2] is resized to [canvas_width, canvas_height]
                        # Clamp bbox to crop region bounds for proper scaling
                        clamped_px1 = max(px1, display_offset_x)
                        clamped_py1 = max(py1, display_offset_y)
                        clamped_px2 = min(px2, display_offset_x + crop_width)
                        clamped_py2 = min(py2, display_offset_y + crop_height)
                        
                        # Convert to display coordinates
                        spx1 = int((clamped_px1 - display_offset_x) * canvas_width / crop_width)
                        spy1 = int((clamped_py1 - display_offset_y) * canvas_height / crop_height)
                        spx2 = int((clamped_px2 - display_offset_x) * canvas_width / crop_width)
                        spy2 = int((clamped_py2 - display_offset_y) * canvas_height / crop_height)
                        
                        # Clamp to canvas bounds to prevent drawing off-screen
                        spx1 = max(0, min(spx1, canvas_width - 1))
                        spy1 = max(0, min(spy1, canvas_height - 1))
                        spx2 = max(spx1 + 1, min(spx2, canvas_width))
                        spy2 = max(spy1 + 1, min(spy2, canvas_height))
                        
                        cv2.rectangle(self.display_frame, (spx1, spy1), (spx2, spy2), color, thickness)
                        
                        # Store display coordinates for click detection (use full bbox for click detection)
                        # Calculate full bbox in display coords for click detection
                        full_spx1 = int((px1 - display_offset_x) * canvas_width / crop_width)
                        full_spy1 = int((py1 - display_offset_y) * canvas_height / crop_height)
                        full_spx2 = int((px2 - display_offset_x) * canvas_width / crop_width)
                        full_spy2 = int((py2 - display_offset_y) * canvas_height / crop_height)
                        self.detected_boxes_display_coords[player_bbox] = (full_spx1, full_spy1, full_spx2, full_spy2)
                        
                        # Draw player name if matched
                        if player_name and spy1 > 20:
                            label = f"{player_name}"
                            if similarity is not None:
                                label += f" ({similarity:.2f})"
                            # Get text size for background
                            (text_width, text_height), baseline = cv2.getTextSize(
                                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                            )
                            # Draw background rectangle
                            cv2.rectangle(self.display_frame,
                                        (spx1, spy1 - text_height - 5),
                                        (spx1 + text_width + 4, spy1),
                                        color, -1)
                            # Draw text
                            cv2.putText(self.display_frame, label,
                                      (spx1 + 2, spy1 - 3),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                else:
                    # Normal view - scale coordinates
                    # CRITICAL FIX: display_frame is display_width x display_height (resized from original frame)
                    # Drawing coordinates must be relative to display_frame (0,0 to display_width, display_height)
                    # Scale bbox coordinates using the same scale factor used for frame resize
                    spx1 = int(px1 * self.scale_factor)
                    spy1 = int(py1 * self.scale_factor)
                    spx2 = int(px2 * self.scale_factor)
                    spy2 = int(py2 * self.scale_factor)
                    
                    # Clamp to display_frame bounds (display_frame is display_width x display_height)
                    spx1 = max(0, min(spx1, display_width - 1))
                    spy1 = max(0, min(spy1, display_height - 1))
                    spx2 = max(spx1 + 1, min(spx2, display_width))
                    spy2 = max(spy1 + 1, min(spy2, display_height))
                    
                    # Draw on display_frame (coordinates are relative to display_frame, not canvas)
                    cv2.rectangle(self.display_frame, (spx1, spy1), (spx2, spy2), color, thickness)
                    
                    # Store display coordinates for click detection (in canvas coordinates, accounting for centering offset)
                    # display_frame is centered in canvas, so add offset for click detection
                    offset_x = (canvas_width - display_width) // 2
                    offset_y = (canvas_height - display_height) // 2
                    canvas_spx1 = spx1 + offset_x
                    canvas_spy1 = spy1 + offset_y
                    canvas_spx2 = spx2 + offset_x
                    canvas_spy2 = spy2 + offset_y
                    self.detected_boxes_display_coords[player_bbox] = (canvas_spx1, canvas_spy1, canvas_spx2, canvas_spy2)
                    
                    # Draw player name if matched
                    if player_name and spy1 > 20:
                        label = f"{player_name}"
                        if similarity is not None:
                            label += f" ({similarity:.2f})"
                        # Get text size for background
                        (text_width, text_height), baseline = cv2.getTextSize(
                            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                        )
                        # Draw background rectangle
                        cv2.rectangle(self.display_frame,
                                    (spx1, spy1 - text_height - 5),
                                    (spx1 + text_width + 4, spy1),
                                    color, -1)
                        # Draw text
                        cv2.putText(self.display_frame, label,
                                  (spx1 + 2, spy1 - 3),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        # Draw selection box if exists (adjusted for zoom/pan) - draw on top of detected players
        if self.selected_bbox:
            sel_x1, sel_y1, sel_x2, sel_y2 = self.selected_bbox
            
            # Check if selection is visible in current view
            if display_width > canvas_width or display_height > canvas_height:
                # Zoomed in - cropped region is resized to canvas size
                # Calculate actual crop dimensions (x1, y1, x2, y2 are from crop calculation above)
                crop_width = x2 - x1 if display_width > canvas_width else frame_width
                crop_height = y2 - y1 if display_height > canvas_height else frame_height
                
                # Check if selection is visible in the cropped region
                if (sel_x1 >= display_offset_x and sel_x2 <= display_offset_x + crop_width and
                    sel_y1 >= display_offset_y and sel_y2 <= display_offset_y + crop_height):
                    # Selection is visible - draw it
                    # Convert frame coordinates to display coordinates
                    sx1 = int((sel_x1 - display_offset_x) * canvas_width / crop_width)
                    sy1 = int((sel_y1 - display_offset_y) * canvas_height / crop_height)
                    sx2 = int((sel_x2 - display_offset_x) * canvas_width / crop_width)
                    sy2 = int((sel_y2 - display_offset_y) * canvas_height / crop_height)
                    cv2.rectangle(self.display_frame, (sx1, sy1), (sx2, sy2), (0, 255, 0), 3)
                    if sy1 > 15:
                        cv2.putText(self.display_frame, "Selected Player", (sx1, sy1 - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                # Normal view - scale coordinates relative to display size
                # CRITICAL FIX: display_frame is already resized, so coordinates should be relative to display_frame (0,0)
                # Do NOT add canvas offset - that's only for canvas click detection, not for drawing on display_frame
                sx1 = int(sel_x1 * self.scale_factor)
                sy1 = int(sel_y1 * self.scale_factor)
                sx2 = int(sel_x2 * self.scale_factor)
                sy2 = int(sel_y2 * self.scale_factor)
                
                # Clamp to display_frame bounds
                sx1 = max(0, min(sx1, display_width - 1))
                sy1 = max(0, min(sy1, display_height - 1))
                sx2 = max(sx1 + 1, min(sx2, display_width))
                sy2 = max(sy1 + 1, min(sy2, display_height))
                
                cv2.rectangle(self.display_frame, (sx1, sy1), (sx2, sy2), (0, 255, 0), 3)
                if sy1 > 15:
                    cv2.putText(self.display_frame, "Selected Player", (sx1, sy1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Convert to PhotoImage
        frame_rgb = cv2.cvtColor(self.display_frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb)
        photo = ImageTk.PhotoImage(image=image)
        
        # Update canvas (center the image)
        self.canvas.delete("all")
        if display_width > canvas_width or display_height > canvas_height:
            # Zoomed in - fill canvas
            self.canvas.create_image(0, 0, image=photo, anchor=tk.NW)
        else:
            # Normal - center image
            self.canvas.create_image(canvas_width // 2, canvas_height // 2, image=photo, anchor=tk.CENTER)
        self.canvas.image = photo  # Keep reference
    
    def on_canvas_click_start(self, event):
        """Handle mouse press on canvas"""
        if not self.pan_mode:
            # First check if clicking on a detection box
            click_x, click_y = event.x, event.y
            
            # Check if click is within any detection box
            clicked_bbox = None
            for bbox, (sx1, sy1, sx2, sy2) in self.detected_boxes_display_coords.items():
                if sx1 <= click_x <= sx2 and sy1 <= click_y <= sy2:
                    clicked_bbox = bbox
                    break
            
            if clicked_bbox:
                # Clicked on a detection box - select it
                self.selected_bbox = clicked_bbox
                
                # Populate name field with matched player name (if any)
                matched_info = self.detected_player_matches.get(clicked_bbox)
                if matched_info:
                    _, player_name, similarity = matched_info
                    # Set the name in the entry field
                    if hasattr(self, 'name_entry') and self.name_entry.winfo_exists():
                        self.name_entry.delete(0, tk.END)
                        self.name_entry.insert(0, player_name)
                    
                    # Also select from dropdown if available
                    if hasattr(self, 'player_dropdown') and self.player_dropdown.winfo_exists():
                        try:
                            all_players = self.gallery.list_players()
                            player_names = [p[1] for p in all_players]
                            if player_name in player_names:
                                self.player_dropdown.set(player_name)
                            else:
                                self.player_dropdown.set("-- New Player --")
                        except:
                            pass
                else:
                    # No match - clear fields
                    if hasattr(self, 'name_entry') and self.name_entry.winfo_exists():
                        self.name_entry.delete(0, tk.END)
                    if hasattr(self, 'player_dropdown') and self.player_dropdown.winfo_exists():
                        self.player_dropdown.set("-- New Player --")
                
                # Update display
                self.display_frame_on_canvas()
                self.update_add_button_state()
                self.update_name_button_state()
                
                # Enable/disable clear match button
                if hasattr(self, 'clear_match_button') and self.clear_match_button.winfo_exists():
                    if matched_info:
                        self.clear_match_button.config(state=tk.NORMAL)
                    else:
                        self.clear_match_button.config(state=tk.DISABLED)
                
                # Update selection label
                if hasattr(self, 'selection_label') and self.selection_label.winfo_exists():
                    x1, y1, x2, y2 = clicked_bbox
                    w, h = x2 - x1, y2 - y1
                    match_text = f" (matched: {matched_info[1]})" if matched_info else ""
                    self.selection_label.config(text=f"Selected: {w}x{h} px{match_text}", foreground="green")
            else:
                # Normal click - start drawing selection
                self.click_start = (event.x, event.y)
    
    def on_canvas_drag(self, event):
        """Handle mouse drag on canvas"""
        if self.click_start and self.current_frame is not None and not self.pan_mode:
            # Get canvas and frame dimensions
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            frame_height, frame_width = self.current_frame.shape[:2]
            
            # Use the same scale factor that was calculated in display_frame_on_canvas
            # Recalculate to ensure it's current (in case zoom changed)
            scale_w = canvas_width / frame_width
            scale_h = canvas_height / frame_height
            base_scale = min(scale_w, scale_h, 1.0)  # Don't upscale beyond 1:1
            # Update self.scale_factor to match what display_frame_on_canvas uses
            self.scale_factor = base_scale * self.zoom_level
            
            # Calculate display size with current scale
            display_width = int(frame_width * self.scale_factor)
            display_height = int(frame_height * self.scale_factor)
            
            # Get canvas click coordinates
            x1, y1 = self.click_start
            x2, y2 = event.x, event.y
            
            # Convert canvas coordinates to frame coordinates
            # This is the inverse of the display logic in display_frame_on_canvas
            if display_width > canvas_width or display_height > canvas_height:
                # Zoomed in - image is cropped and resized to fill canvas
                # Image is at (0, 0) with anchor=tk.NW
                # Calculate crop region exactly as display_frame_on_canvas does
                visible_width = int(canvas_width / self.scale_factor)
                visible_height = int(canvas_height / self.scale_factor)
                
                # Center of view with pan offset (same calculation as display_frame_on_canvas)
                center_x = frame_width / 2 - (self.pan_x / self.scale_factor)
                center_y = frame_height / 2 - (self.pan_y / self.scale_factor)
                
                # Calculate crop bounds (same as display_frame_on_canvas)
                crop_x1 = int(max(0, center_x - visible_width / 2))
                crop_y1 = int(max(0, center_y - visible_height / 2))
                crop_x2 = int(min(frame_width, crop_x1 + visible_width))
                crop_y2 = int(min(frame_height, crop_y1 + visible_height))
                
                # Adjust if we hit boundaries (same as display_frame_on_canvas)
                if crop_x2 - crop_x1 < visible_width:
                    crop_x1 = max(0, crop_x2 - visible_width)
                if crop_y2 - crop_y1 < visible_height:
                    crop_y1 = max(0, crop_y2 - visible_height)
                
                # The cropped region [crop_x1:crop_x2, crop_y1:crop_y2] is resized to canvas size
                # Display logic: spx1 = (px1 - crop_x1) * self.scale_factor
                # Reverse: px1 = crop_x1 + (spx1 / self.scale_factor)
                # But since the crop is resized to canvas, we need to account for the actual crop size
                crop_width = crop_x2 - crop_x1
                crop_height = crop_y2 - crop_y1
                fx1 = crop_x1 + (min(x1, x2) * crop_width / canvas_width)
                fy1 = crop_y1 + (min(y1, y2) * crop_height / canvas_height)
                fx2 = crop_x1 + (max(x1, x2) * crop_width / canvas_width)
                fy2 = crop_y1 + (max(y1, y2) * crop_height / canvas_height)
            else:
                # Normal view - image is centered
                offset_x = (canvas_width - display_width) // 2
                offset_y = (canvas_height - display_height) // 2
                
                # Display logic: spx1 = px1 * self.scale_factor + offset_x
                # Reverse: px1 = (spx1 - offset_x) / self.scale_factor
                fx1 = (min(x1, x2) - offset_x) / self.scale_factor
                fy1 = (min(y1, y2) - offset_y) / self.scale_factor
                fx2 = (max(x1, x2) - offset_x) / self.scale_factor
                fy2 = (max(y1, y2) - offset_y) / self.scale_factor
            
            # Convert to integers and clamp to frame bounds
            fx1 = max(0, min(int(fx1), frame_width))
            fy1 = max(0, min(int(fy1), frame_height))
            fx2 = max(0, min(int(fx2), frame_width))
            fy2 = max(0, min(int(fy2), frame_height))
            
            # Update selection
            if fx2 > fx1 and fy2 > fy1:
                self.selected_bbox = (fx1, fy1, fx2, fy2)
                self.display_frame_on_canvas()
    
    def on_canvas_click_end(self, event):
        """Handle mouse release on canvas"""
        if not self.pan_mode:
            self.on_canvas_drag(event)  # Final update
            self.click_start = None
            
            if self.selected_bbox:
                x1, y1, x2, y2 = self.selected_bbox
                w, h = x2 - x1, y2 - y1
                self.selection_label.config(text=f"Selected: {w}x{h} px", foreground="green")
                self.update_add_button_state()
            else:
                self.selection_label.config(text="Selection too small", foreground="orange")
    
    def on_pan_start(self, event):
        """Start panning (right-click or middle-click)"""
        self.pan_start = (event.x, event.y)
        self.pan_mode = True
        self.canvas.config(cursor="fleur")  # Move cursor
    
    def on_pan_drag(self, event):
        """Pan the view"""
        if self.pan_start and self.pan_mode:
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]
            self.pan_x += dx
            self.pan_y += dy
            self.pan_start = (event.x, event.y)
            self.display_frame_on_canvas()
    
    def on_pan_end(self, event):
        """End panning"""
        self.pan_start = None
        self.pan_mode = False
        self.canvas.config(cursor="crosshair")
    
    def on_mouse_wheel(self, event):
        """Handle mouse wheel zoom"""
        if self.current_frame is None or (isinstance(self.current_frame, np.ndarray) and self.current_frame.size == 0):
            return
        
        # Determine zoom direction
        if event.num == 4 or event.delta > 0:  # Scroll up / zoom in
            self.zoom_in()
        elif event.num == 5 or event.delta < 0:  # Scroll down / zoom out
            self.zoom_out()
    
    def zoom_in(self):
        """Zoom in by 25%"""
        self.zoom_level = min(self.zoom_level * 1.25, 8.0)  # Max 8x zoom
        self.update_zoom_label()
        self.display_frame_on_canvas()
    
    def zoom_out(self):
        """Zoom out by 25%"""
        self.zoom_level = max(self.zoom_level / 1.25, 0.1)  # Min 0.1x zoom
        self.update_zoom_label()
        self.display_frame_on_canvas()
    
    def zoom_fit(self):
        """Reset zoom to fit window"""
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.update_zoom_label()
        self.display_frame_on_canvas()
    
    def zoom_actual(self):
        """Zoom to actual size (1:1 pixels)"""
        if self.current_frame is None or (isinstance(self.current_frame, np.ndarray) and self.current_frame.size == 0):
            return
        
        # Calculate what zoom level gives 1:1
        frame_height, frame_width = self.current_frame.shape[:2]
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        scale_w = canvas_width / frame_width
        scale_h = canvas_height / frame_height
        fit_scale = min(scale_w, scale_h, 1.0)
        
        # Set zoom to achieve 1:1 (actual pixels)
        self.zoom_level = 1.0 / fit_scale if fit_scale > 0 else 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.update_zoom_label()
        self.display_frame_on_canvas()
    
    def update_zoom_label(self):
        """Update the zoom percentage label"""
        zoom_pct = int(self.zoom_level * 100)
        self.zoom_label.config(text=f"{zoom_pct}%")
    
    def skip_frames(self, delta: int):
        """Skip forward/backward by delta frames"""
        if self.cap:
            new_frame = self.current_frame_num + delta
            self.load_frame(new_frame)
    
    def on_slider_change(self, value):
        """Handle slider movement"""
        if self.cap:
            frame_num = int(float(value))
            if frame_num != self.current_frame_num:
                self.load_frame(frame_num)
    
    # Event Marker Methods
    def mark_event_at_current_frame(self):
        """Mark an event at the current frame using the event marker system"""
        if not EVENT_MARKER_AVAILABLE or not self.event_marker_system:
            messagebox.showwarning("Not Available", "Event marker system is not available")
            return
        
        if not self.video_path or self.current_frame_num < 0:
            return
        
        event_type_str = self.current_event_type.get()
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            messagebox.showerror("Invalid Event Type", f"Unknown event type: {event_type_str}")
            return
        
        # Get player info from selected bbox
        player_name = None
        position = None
        
        if self.selected_bbox:
            x1, y1, x2, y2 = self.selected_bbox
            x_center = (x1 + x2) / 2
            y_center = (y1 + y2) / 2
            
            # Get player name from entry or dropdown
            if self.name_entry.get().strip():
                player_name = self.name_entry.get().strip()
            elif self.player_dropdown.get() and self.player_dropdown.get() != "-- New Player --":
                player_name = self.player_dropdown.get()
            
            # Normalize position
            if self.current_frame is not None:
                h, w = self.current_frame.shape[:2]
                if w > 0 and h > 0:
                    # Account for zoom and pan
                    display_w = self.canvas.winfo_width()
                    display_h = self.canvas.winfo_height()
                    if display_w > 0 and display_h > 0:
                        # Convert canvas coordinates to original frame coordinates
                        scale_x = w / display_w if display_w > 0 else 1.0
                        scale_y = h / display_h if display_h > 0 else 1.0
                        orig_x = (x_center - self.pan_x) / self.zoom_level * scale_x
                        orig_y = (y_center - self.pan_y) / self.zoom_level * scale_y
                        position = (orig_x / w, orig_y / h)
        
        # Create marker
        timestamp = self.current_frame_num / self.fps if self.fps > 0 else self.current_frame_num / 30.0
        marker = EventMarker(
            frame_num=self.current_frame_num,
            event_type=event_type,
            timestamp=timestamp,
            player_name=player_name,
            position=position,
            confidence=1.0
        )
        
        self.event_marker_system.add_marker(marker)
        self.update_marker_statistics()
        
        messagebox.showinfo("Event Marked", 
                          f"Marked {event_type_str} at frame {self.current_frame_num}\n"
                          f"Player: {player_name or 'Unknown'}")
    
    def remove_event_at_current_frame(self):
        """Remove event marker(s) at the current frame"""
        if not EVENT_MARKER_AVAILABLE or not self.event_marker_system:
            return
        
        markers = self.event_marker_system.get_markers_at_frame(self.current_frame_num)
        if not markers:
            messagebox.showinfo("No Markers", f"No event markers at frame {self.current_frame_num}")
            return
        
        if len(markers) == 1:
            event_type = markers[0].event_type
            self.event_marker_system.remove_marker(self.current_frame_num, event_type)
            messagebox.showinfo("Marker Removed", f"Removed {event_type.value} marker")
        else:
            marker_types = [m.event_type.value for m in markers]
            choice = simpledialog.askstring(
                "Remove Marker",
                f"Multiple markers at frame {self.current_frame_num}:\n" +
                "\n".join(f"{i+1}. {t}" for i, t in enumerate(marker_types)) +
                "\n\nEnter number to remove (or 'all' for all):"
            )
            if choice:
                if choice.lower() == 'all':
                    self.event_marker_system.remove_marker(self.current_frame_num)
                    messagebox.showinfo("Markers Removed", f"Removed all markers")
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
    
    def save_event_markers(self):
        """Save event markers to file"""
        if not EVENT_MARKER_AVAILABLE or not self.event_marker_system:
            return
        
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
        if not EVENT_MARKER_AVAILABLE or not self.event_marker_system:
            return
        
        if self.video_path:
            video_dir = os.path.dirname(os.path.abspath(self.video_path))
            video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
            default_path = os.path.join(video_dir, f"{video_basename}_event_markers.json")
            
            if os.path.exists(default_path):
                if self.event_marker_system.load_from_file(default_path):
                    messagebox.showinfo("Markers Loaded", 
                                      f"Loaded {len(self.event_marker_system.markers)} markers from:\n{default_path}")
                    self.update_marker_statistics()
                    return
        
        filename = filedialog.askopenfilename(
            title="Load Event Markers",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            if self.event_marker_system.load_from_file(filename):
                messagebox.showinfo("Markers Loaded", f"Loaded {len(self.event_marker_system.markers)} markers")
                self.update_marker_statistics()
            else:
                messagebox.showerror("Load Failed", "Could not load event markers from file")
    
    def update_marker_statistics(self):
        """Update the marker statistics display"""
        if not EVENT_MARKER_AVAILABLE or not self.event_marker_system or not hasattr(self, 'marker_stats_label'):
            return
        
        stats = self.event_marker_system.get_statistics()
        total = stats['total_markers']
        by_type = stats.get('by_type', {})
        
        if total == 0:
            self.marker_stats_label.config(text="Markers: 0")
        else:
            type_str = ", ".join([f"{k}: {v}" for k, v in by_type.items()])
            self.marker_stats_label.config(text=f"Markers: {total} ({type_str})")
    
    def update_add_button_state(self):
        """Enable/disable Add button based on current state"""
        try:
            # Check if widgets still exist (window might be closed)
            if not hasattr(self, 'add_button') or not self.add_button.winfo_exists():
                return
            if not hasattr(self, 'name_entry') or not self.name_entry.winfo_exists():
                return
            
            if self.selected_bbox and self.name_entry.get().strip():
                self.add_button.config(state=tk.NORMAL)
            else:
                self.add_button.config(state=tk.DISABLED)
        except tk.TclError:
            # Widget was destroyed - this is expected if window is closed
            pass
    
    def update_name_button_state(self):
        """Enable/disable Update Name button based on current state"""
        try:
            # Check if widgets still exist (window might be closed)
            if not hasattr(self, 'update_name_button') or not self.update_name_button.winfo_exists():
                return
            if not hasattr(self, 'name_entry') or not self.name_entry.winfo_exists():
                return
            if not self.selected_bbox:
                self.update_name_button.config(state=tk.DISABLED)
                return
            
            # Enable if: selected bbox is a detected player (has match) AND name field has text
            is_detected_player = self.selected_bbox in self.detected_player_matches
            has_name = bool(self.name_entry.get().strip())
            
            if is_detected_player and has_name:
                self.update_name_button.config(state=tk.NORMAL)
            else:
                self.update_name_button.config(state=tk.DISABLED)
        except tk.TclError:
            # Widget was destroyed - this is expected if window is closed
            pass
    
    def clear_selected_match(self):
        """Clear the match for the currently selected detection box"""
        if not self.selected_bbox:
            return
        
        # Remove from matches dictionary
        if self.selected_bbox in self.detected_player_matches:
            del self.detected_player_matches[self.selected_bbox]
            print(f"✓ Cleared match for selected player")
        
        # Clear name field
        if hasattr(self, 'name_entry') and self.name_entry.winfo_exists():
            self.name_entry.delete(0, tk.END)
        if hasattr(self, 'player_dropdown') and self.player_dropdown.winfo_exists():
            self.player_dropdown.set("-- New Player --")
        
        # Disable clear match button
        if hasattr(self, 'clear_match_button') and self.clear_match_button.winfo_exists():
            self.clear_match_button.config(state=tk.DISABLED)
        
        # Update display to remove the name label
        self.display_frame_on_canvas()
        
        # Update selection label
        if hasattr(self, 'selection_label') and self.selection_label.winfo_exists():
            x1, y1, x2, y2 = self.selected_bbox
            w, h = x2 - x1, y2 - y1
            self.selection_label.config(text=f"Selected: {w}x{h} px", foreground="green")
    
    def update_detected_player_name(self):
        """Update the name for a detected player (correct wrong matches)"""
        if not self.selected_bbox:
            messagebox.showwarning("No Selection", "Please click on a detected player box first")
            return
        
        # Check if this is a detected player (has a match)
        if self.selected_bbox not in self.detected_player_matches:
            messagebox.showwarning("Not a Detected Player", "This player is not from YOLO detection. Use 'Add to Gallery' instead.")
            return
        
        # Get new name from input field
        new_name = self.name_entry.get().strip()
        if not new_name:
            messagebox.showerror("Error", "Please enter a player name")
            return
        
        # Get current match info
        old_match_info = self.detected_player_matches[self.selected_bbox]
        old_player_id, old_name, old_similarity = old_match_info
        
        # Update the match with new name
        # Try to find player in gallery by name
        new_player_id = None
        try:
            all_players = self.gallery.list_players()
            for pid, name in all_players:
                if name == new_name:
                    new_player_id = pid
                    break
        except:
            pass
        
        # If player not in gallery, create new player ID
        if new_player_id is None:
            new_player_id = new_name.lower().replace(" ", "_")
        
        # Update match dictionary
        # Keep the same similarity score (it's based on visual match, not name)
        self.detected_player_matches[self.selected_bbox] = (new_player_id, new_name, old_similarity)
        
        # Update/create anchor frame with corrected name
        x1, y1, x2, y2 = self.selected_bbox
        bbox = [float(x1), float(y1), float(x2), float(y2)]
        frame_str = str(self.current_frame_num)
        
        if frame_str not in self.anchor_frames:
            self.anchor_frames[frame_str] = []
        
        # Remove old anchor frame entry for this bbox (if exists)
        self.anchor_frames[frame_str] = [
            anchor for anchor in self.anchor_frames[frame_str]
            if not (abs(anchor.get('bbox', [0])[0] - x1) < 5 and 
                   abs(anchor.get('bbox', [0])[1] - y1) < 5)
        ]
        
        # Add new anchor frame with corrected name
        anchor = {
            'player_name': new_name,
            'track_id': None,  # No track ID yet (from YOLO detection)
            'confidence': 1.00,  # Manual correction = ground truth
            'bbox': bbox,
            'team': self.team_entry.get().strip() or None
        }
        
        # Add jersey number if available
        jersey = self.jersey_entry.get().strip()
        if jersey:
            try:
                anchor['jersey_number'] = int(jersey)
            except:
                pass
        
        self.anchor_frames[frame_str].append(anchor)
        
        # Update player tag protection
        self.player_tag_protection[new_name] = (self.current_frame_num, tuple(bbox))
        
        print(f"✓ Updated player name: '{old_name}' → '{new_name}' (Frame {self.current_frame_num})")
        
        # Update display to show new name
        self.display_frame_on_canvas()
        
        # Update selection label
        if hasattr(self, 'selection_label') and self.selection_label.winfo_exists():
            self.selection_label.config(text=f"Updated: {new_name}", foreground="green")
        
        # Show confirmation
        messagebox.showinfo("Name Updated", f"Player name updated to: {new_name}\n\nThis will be saved when you save anchor frames.")
    
    def add_player_to_gallery(self):
        """Add tagged player to gallery with Re-ID features"""
        if not self.selected_bbox or not self.current_frame is not None:
            messagebox.showerror("Error", "Please select a player first")
            return
        
        player_name = self.name_entry.get().strip()
        if not player_name:
            messagebox.showerror("Error", "Please enter a player name")
            return
        
        jersey = self.jersey_entry.get().strip() or None
        team = self.team_entry.get().strip() or None
        
        # Parse visualization settings
        viz_settings = None
        custom_color_str = self.viz_color_var.get().strip()
        if custom_color_str or self.viz_box_thickness.get() != 2 or self.viz_show_glow.get() or self.viz_show_trail.get() or self.viz_label_style.get() != "full_name":
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
            
            if self.viz_box_thickness.get() != 2:
                viz_settings["box_thickness"] = self.viz_box_thickness.get()
            
            if self.viz_show_glow.get():
                viz_settings["show_glow"] = True
                viz_settings["glow_intensity"] = self.viz_glow_intensity.get()
            
            if self.viz_show_trail.get():
                viz_settings["show_trail"] = True
            
            if self.viz_label_style.get() != "full_name":
                viz_settings["label_style"] = self.viz_label_style.get()
        
        try:
            # Extract bounding box
            x1, y1, x2, y2 = self.selected_bbox
            bbox = (x1, y1, x2, y2)
            
            print(f"\nExtracting Re-ID features for player: {player_name}")
            print(f"  BBox: {bbox}")
            
            # Extract comprehensive Re-ID features (body, jersey, foot) if available
            features = None
            body_features = None
            jersey_features = None
            foot_features = None
            
            if self.reid_tracker and SUPERVISION_AVAILABLE:
                try:
                    # Create detections object
                    detections = sv.Detections(
                        xyxy=np.array([[x1, y1, x2, y2]]),
                        confidence=np.array([1.0]),
                        class_id=np.array([0])
                    )
                    print("  Created detections object")
                    
                    # Extract full body features (general Re-ID features)
                    features = self.reid_tracker.extract_features(
                        self.current_frame,
                        detections,
                        team_colors=None,
                        ball_colors=None
                    )
                    
                    if features is not None and len(features) > 0:
                        print(f"  ✓ Body features extracted: shape={features.shape}")
                        features = features[0]  # Take first (and only) feature vector
                    else:
                        print("  ⚠ Body feature extraction returned None")
                        features = None
                    
                    # Extract jersey/torso region features
                    try:
                        jersey_feat = self.reid_tracker.extract_jersey_features(
                            self.current_frame,
                            detections
                        )
                        if jersey_feat is not None and len(jersey_feat) > 0:
                            jersey_features = jersey_feat[0]
                            print(f"  ✓ Jersey features extracted: shape={jersey_features.shape}")
                        else:
                            print("  ⚠ Jersey feature extraction returned None")
                    except Exception as e:
                        print(f"  ⚠ Jersey feature extraction failed: {e}")
                    
                    # Extract foot/shoe region features
                    try:
                        foot_feat = self.reid_tracker.extract_foot_features(
                            self.current_frame,
                            detections
                        )
                        if foot_feat is not None and len(foot_feat) > 0:
                            foot_features = foot_feat[0]
                            print(f"  ✓ Foot features extracted: shape={foot_features.shape}")
                        else:
                            print("  ⚠ Foot feature extraction returned None")
                    except Exception as e:
                        print(f"  ⚠ Foot feature extraction failed: {e}")
                    
                    if features is not None:
                        print("  ✓ Re-ID features extracted successfully")
                    else:
                        print("  ⚠ No Re-ID features extracted")
                        
                except Exception as e:
                    print(f"  ⚠ Feature extraction failed: {e}")
                    traceback.print_exc()
                    features = None
                    body_features = None
                    jersey_features = None
                    foot_features = None
            
            # Create reference frame info
            reference_frame = {
                'video_path': self.video_path,
                'frame_num': self.current_frame_num,
                'bbox': list(bbox)
            }
            
            # ANCHOR FRAME: Save this as an anchor frame with 1.00 confidence
            # Note: track_id will be None (matched by bbox position during analysis)
            anchor_entry = {
                "track_id": None,  # Will be matched by bbox position during analysis
                "player_name": player_name,
                "jersey_number": jersey,  # Include jersey number for better matching
                "team": team,
                "bbox": list(bbox),  # [x1, y1, x2, y2]
                "confidence": 1.00  # Anchor frames are ground truth
            }
            
            # Add to anchor_frames dictionary
            if self.current_frame_num not in self.anchor_frames:
                self.anchor_frames[self.current_frame_num] = []
            self.anchor_frames[self.current_frame_num].append(anchor_entry)
            
            # CRITICAL: Protect this player's identity for the next few frames
            # This prevents the system from overwriting a manually tagged player
            # when navigating between frames or when detections change
            self.player_tag_protection[player_name] = (self.current_frame_num, bbox)
            
            # Save anchor frames to seed config file
            self.save_anchor_frames()
            
            # Add to gallery
            print(f"\nAdding player to gallery:")
            print(f"  Name: {player_name}")
            print(f"  Jersey: {jersey}")
            print(f"  Team: {team}")
            print(f"  Has body features: {features is not None}")
            print(f"  Has jersey features: {jersey_features is not None}")
            print(f"  Has foot features: {foot_features is not None}")
            print(f"  Reference frame: {self.current_frame_num}")
            
            # Check if player already exists
            all_players = self.gallery.list_players()
            player_id = None
            for pid, pname in all_players:
                if pname.lower() == player_name.lower():
                    player_id = pid
                    print(f"  ℹ Player already exists - updating instead")
                    break
            
            if player_id:
                # Update existing player with all feature types
                self.gallery.update_player(
                    player_id=player_id,
                    features=features,  # General/body features
                    body_features=features,  # Explicit body features
                    jersey_features=jersey_features,
                    foot_features=foot_features,
                    reference_frame=reference_frame,
                    jersey_number=jersey,
                    team=team,
                    visualization_settings=viz_settings
                )
                feature_summary = []
                if features is not None:
                    feature_summary.append("body")
                if jersey_features is not None:
                    feature_summary.append("jersey")
                if foot_features is not None:
                    feature_summary.append("foot")
                
                feature_text = f"✓ Added new reference frame with {', '.join(feature_summary)} features!" if feature_summary else "✓ Added new reference frame!"
                
                print(f"✓ Updated player '{player_name}' (ID: {player_id})")
                messagebox.showinfo(
                    "Updated", 
                    f"✓ Updated '{player_name}' in gallery!\n\n"
                    f"{feature_text}\n\n"
                    f"Jersey: #{jersey if jersey else 'None'}"
                )
            else:
                # Add new player with all feature types
                player_id = self.gallery.add_player(
                    name=player_name,
                    jersey_number=jersey,
                    team=team,
                    features=features,  # General/body features
                    body_features=features,  # Explicit body features
                    jersey_features=jersey_features,
                    foot_features=foot_features,
                    reference_frame=reference_frame,
                    visualization_settings=viz_settings
                )
                
                feature_summary = []
                if features is not None:
                    feature_summary.append("body")
                if jersey_features is not None:
                    feature_summary.append("jersey")
                if foot_features is not None:
                    feature_summary.append("foot")
                
                feature_text = f"✓ Re-ID features extracted: {', '.join(feature_summary)}!" if feature_summary else "⚠ No Re-ID features (manual only)"
                
                print(f"✓ Added player '{player_name}' (ID: {player_id})")
                messagebox.showinfo(
                    "Added", 
                    f"✓ Added '{player_name}' to gallery!\n\n"
                    f"{feature_text}\n\n"
                    f"Jersey: #{jersey if jersey else 'None'}"
                )
            
            # Update UI (check if widgets exist first)
            try:
                self.update_gallery_list()
                self.update_player_dropdown()
                
                # Clear selection
                self.selected_bbox = None
                if hasattr(self, 'selection_label') and self.selection_label.winfo_exists():
                    self.selection_label.config(text="Player added!", foreground="green")
                if hasattr(self, 'canvas') and self.canvas.winfo_exists():
                    self.display_frame_on_canvas()
                
                # Update button state
                self.update_add_button_state()
            except tk.TclError:
                # Widgets were destroyed - window might be closed, ignore
                pass
            
            print("  ✓ Player updated (ID: {})".format(player_id))
            print("  ✓ Gallery updated\n")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not add player:\n\n{str(e)}")
            print(f"⚠ Error adding player: {e}")
            traceback.print_exc()
    
    def check_and_offer_csv_load(self, video_path):
        """Check for matching CSV files and offer to load one"""
        try:
            video_dir = os.path.dirname(os.path.abspath(video_path))
            video_basename = os.path.splitext(os.path.basename(video_path))[0]
            
            # Look for common CSV naming patterns
            csv_patterns = [
                f"{video_basename}_analyzed_tracking_data.csv",
                f"{video_basename}_tracking_data.csv",
                f"{video_basename}_analyzed.csv",
                f"{video_basename}.csv"
            ]
            
            found_csvs = []
            for pattern in csv_patterns:
                csv_path = os.path.join(video_dir, pattern)
                if os.path.exists(csv_path):
                    found_csvs.append(csv_path)
            
            if found_csvs:
                # If only one CSV found, auto-load it
                if len(found_csvs) == 1:
                    print(f"✓ Found matching CSV: {os.path.basename(found_csvs[0])}")
                    self.load_csv(found_csvs[0])
                else:
                    # Multiple CSVs found - ask user which one
                    print(f"✓ Found {len(found_csvs)} matching CSV files")
                    result = messagebox.askyesno(
                        "CSV Files Found",
                        f"Found {len(found_csvs)} CSV file(s) for this video:\n\n" +
                        "\n".join([os.path.basename(csv) for csv in found_csvs]) +
                        "\n\nWould you like to load one now?\n(You can also load manually using 'Load CSV' button)"
                    )
                    if result:
                        # Show file dialog to choose
                        csv_path = filedialog.askopenfilename(
                            title="Select CSV File to Load",
                            initialdir=video_dir,
                            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                        )
                        if csv_path:
                            self.load_csv(csv_path)
            else:
                print(f"ℹ No matching CSV files found for {video_basename}")
        except Exception as e:
            print(f"⚠ Error checking for CSV files: {e}")
    
    def load_csv(self, csv_path=None):
        """Load CSV tracking data for the current video"""
        if csv_path is None:
            # Show file dialog
            initial_dir = os.path.dirname(self.video_path) if self.video_path else None
            csv_path = filedialog.askopenfilename(
                title="Select Tracking Data CSV",
                initialdir=initial_dir,
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not csv_path:
                return
        
        if not os.path.exists(csv_path):
            messagebox.showerror("Error", f"CSV file not found: {csv_path}")
            return
        
        try:
            import pandas as pd
            
            # Load CSV
            df = pd.read_csv(csv_path)
            
            if df.empty:
                messagebox.showerror("Error", "CSV file is empty")
                return
            
            # Check required columns
            if 'frame' not in df.columns:
                messagebox.showerror("Error", "CSV file missing 'frame' column")
                return
            
            # Determine track_id column name
            track_id_col = None
            for col in ['track_id', 'player_id', 'id']:
                if col in df.columns:
                    track_id_col = col
                    break
            
            if track_id_col is None:
                messagebox.showerror("Error", "CSV file missing track_id/player_id column")
                return
            
            # Process CSV data into frame-based structure
            self.csv_data = {}
            has_bbox = all(col in df.columns for col in ['x1', 'y1', 'x2', 'y2'])
            
            for _, row in df.iterrows():
                frame_num = int(row['frame'])
                track_id = int(row[track_id_col]) if pd.notna(row[track_id_col]) else None
                
                if track_id is None:
                    continue
                
                if frame_num not in self.csv_data:
                    self.csv_data[frame_num] = {}
                
                # Get player name
                player_name = None
                if 'player_name' in row and pd.notna(row['player_name']):
                    name_str = str(row['player_name']).strip()
                    if name_str and name_str.lower() not in ['nan', 'none', '']:
                        player_name = name_str
                
                # Get bbox
                bbox = None
                if has_bbox:
                    x1 = row.get('x1') if pd.notna(row.get('x1')) else None
                    y1 = row.get('y1') if pd.notna(row.get('y1')) else None
                    x2 = row.get('x2') if pd.notna(row.get('x2')) else None
                    y2 = row.get('y2') if pd.notna(row.get('y2')) else None
                    if all(v is not None for v in [x1, y1, x2, y2]):
                        bbox = [float(x1), float(y1), float(x2), float(y2)]
                
                # Get team and jersey
                team = None
                if 'team' in row and pd.notna(row['team']):
                    team_str = str(row['team']).strip()
                    if team_str and team_str.lower() not in ['nan', 'none', '']:
                        team = team_str
                
                jersey_number = None
                if 'jersey_number' in row and pd.notna(row['jersey_number']):
                    jersey_str = str(row['jersey_number']).strip()
                    if jersey_str and jersey_str.lower() not in ['nan', 'none', '']:
                        jersey_number = jersey_str
                
                # Store CSV data
                self.csv_data[frame_num][track_id] = {
                    'player_name': player_name,
                    'bbox': bbox,
                    'team': team,
                    'jersey_number': jersey_number
                }
            
            # Update UI
            csv_name = os.path.basename(csv_path)
            frames_with_data = len(self.csv_data)
            total_tracks = sum(len(tracks) for tracks in self.csv_data.values())
            self.csv_label.config(text=f"✓ CSV: {csv_name} ({frames_with_data} frames, {total_tracks} tracks)", foreground="green")
            self.csv_path = csv_path
            
            print(f"✓ Loaded CSV: {csv_name} ({frames_with_data} frames with {total_tracks} total track entries)")
            
            # Show summary
            players_with_names = set()
            for frame_data in self.csv_data.values():
                for track_data in frame_data.values():
                    if track_data.get('player_name'):
                        players_with_names.add(track_data['player_name'])
            
            if players_with_names:
                messagebox.showinfo(
                    "CSV Loaded",
                    f"✓ Loaded CSV: {csv_name}\n\n"
                    f"• {frames_with_data} frames with tracking data\n"
                    f"• {total_tracks} total track entries\n"
                    f"• {len(players_with_names)} players with names: {', '.join(sorted(players_with_names))}\n\n"
                    f"Player names from CSV will be used when detecting players."
                )
            else:
                messagebox.showinfo(
                    "CSV Loaded",
                    f"✓ Loaded CSV: {csv_name}\n\n"
                    f"• {frames_with_data} frames with tracking data\n"
                    f"• {total_tracks} total track entries\n\n"
                    f"Note: No player names found in CSV. You can still tag players manually."
                )
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load CSV:\n\n{str(e)}")
            print(f"⚠ Error loading CSV: {e}")
            traceback.print_exc()
    
    def get_csv_data_for_frame(self, frame_num: int, track_id: Optional[int] = None) -> Optional[Dict]:
        """Get CSV data for a specific frame and optionally track_id"""
        if self.csv_data is None or frame_num not in self.csv_data:
            return None
        
        frame_data = self.csv_data[frame_num]
        
        if track_id is not None:
            return frame_data.get(track_id)
        else:
            # Return all tracks for this frame
            return frame_data
    
    def match_detection_to_csv(self, bbox: Tuple[int, int, int, int], frame_num: int) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
        """Match a detection bbox to CSV data for the current frame"""
        if self.csv_data is None or frame_num not in self.csv_data:
            return None
        
        frame_data = self.csv_data[frame_num]
        if not frame_data:
            return None
        
        x1_curr, y1_curr, x2_curr, y2_curr = bbox
        center_x_curr = (x1_curr + x2_curr) / 2
        center_y_curr = (y1_curr + y2_curr) / 2
        
        best_match = None
        best_distance = float('inf')
        best_iou = 0.0
        
        # Try to match by bbox IoU or center distance
        for track_id, track_data in frame_data.items():
            csv_bbox = track_data.get('bbox')
            csv_player_name = track_data.get('player_name')
            
            if not csv_player_name:
                continue
            
            if csv_bbox:
                # Match by bbox IoU
                x1_csv, y1_csv, x2_csv, y2_csv = csv_bbox
                x1_i = max(x1_curr, x1_csv)
                y1_i = max(y1_curr, y1_csv)
                x2_i = min(x2_curr, x2_csv)
                y2_i = min(y2_curr, y2_csv)
                
                if x2_i > x1_i and y2_i > y1_i:
                    intersection = (x2_i - x1_i) * (y2_i - y1_i)
                    area_curr = (x2_curr - x1_curr) * (y2_curr - y1_curr)
                    area_csv = (x2_csv - x1_csv) * (y2_csv - y1_csv)
                    union = area_curr + area_csv - intersection
                    iou = intersection / union if union > 0 else 0.0
                    
                    if iou > best_iou and iou > 0.3:  # Minimum IoU threshold
                        best_iou = iou
                        best_match = (
                            csv_player_name,
                            track_data.get('team'),
                            track_data.get('jersey_number')
                        )
            else:
                # Fallback: Match by center distance (if CSV has player_x/player_y, we'd need to add that)
                # For now, skip if no bbox
                pass
        
        return best_match
    
    def load_existing_anchor_frames(self, video_path):
        """Load existing anchor frames from PlayerTagsSeed file (STRICT: full path matching required)"""
        try:
            import json
            
            video_dir = os.path.dirname(os.path.abspath(video_path))
            video_basename = os.path.splitext(os.path.basename(video_path))[0]
            video_path_normalized = os.path.normpath(os.path.abspath(video_path))
            
            print(f"🔍 Loading anchor frames for video: {os.path.basename(video_path)}")
            print(f"   → Video directory: {video_dir}")
            print(f"   → Video full path: {video_path_normalized}")
            
            # CRITICAL: Find all matching PlayerTagsSeed files and validate they're for THIS video
            # This prevents loading anchor frames from videos with the same filename in different folders
            seed_patterns = [
                f"PlayerTagsSeed_{video_basename}.json",  # Underscore format (newer, often more accurate)
                f"PlayerTagsSeed-{video_basename}.json",  # Dash format (original)
                f"PlayerTagsSeed-{video_basename}-Project.json",
                f"PlayerTagsSeed-{video_basename}_optimized.json",  # Optimized version
            ]
            
            # Find all matching files and validate they're for this video
            found_files = []
            for pattern in seed_patterns:
                seed_file = os.path.join(video_dir, pattern)
                if os.path.exists(seed_file):
                    try:
                        with open(seed_file, 'r') as f:
                            seed_data = json.load(f)
                        
                        # CRITICAL: Verify this file is for the CURRENT video using FULL PATH matching
                        file_video_path = seed_data.get("video_path", "")
                        if file_video_path:
                            # Normalize both paths for comparison
                            file_video_normalized = os.path.normpath(os.path.abspath(file_video_path))
                            
                            # STRICT: Require exact path match (prevents matching videos with same name in different folders)
                            if file_video_normalized == video_path_normalized:
                                # This file is for the current video - add it
                                found_files.append((seed_file, os.path.getmtime(seed_file), seed_data))
                                print(f"  ✓ VERIFIED {os.path.basename(seed_file)}: Video path matches exactly")
                            else:
                                # Filenames might match but paths differ - this is a different video!
                                file_basename = os.path.basename(file_video_path)
                                video_basename_check = os.path.basename(video_path)
                                if file_basename == video_basename_check:
                                    print(f"  ⚠ SKIPPING {os.path.basename(seed_file)}: Same filename but different folder")
                                    print(f"     → Anchor file video: {file_video_path}")
                                    print(f"     → Current video: {video_path}")
                                    print(f"     → These are DIFFERENT videos - skipping to avoid wrong player assignments")
                                else:
                                    print(f"  ⚠ SKIPPING {os.path.basename(seed_file)}: Different video (filename mismatch)")
                        else:
                            # No video_path in anchor file - fallback to filename matching (less safe)
                            print(f"  ⚠ WARNING: {os.path.basename(seed_file)} has no 'video_path' - using filename match only")
                            print(f"     → This is less safe if you have videos with same name in different folders")
                            # Still add it but with a warning
                            found_files.append((seed_file, os.path.getmtime(seed_file), seed_data))
                    except Exception as e:
                        print(f"  ⚠ Could not read {os.path.basename(seed_file)}: {e}")
                        continue
            
            # Also check for any PlayerTagsSeed files matching the video name (with strict validation)
            if not found_files:
                try:
                    for filename in os.listdir(video_dir):
                        if filename.startswith("PlayerTagsSeed") and filename.endswith(".json"):
                            # Check if it matches this video (contains video basename)
                            if video_basename in filename:
                                seed_file = os.path.join(video_dir, filename)
                                try:
                                    with open(seed_file, 'r') as f:
                                        seed_data = json.load(f)
                                    
                                    # Validate video_path matches
                                    file_video_path = seed_data.get("video_path", "")
                                    if file_video_path:
                                        file_video_normalized = os.path.normpath(os.path.abspath(file_video_path))
                                        if file_video_normalized == video_path_normalized:
                                            found_files.append((seed_file, os.path.getmtime(seed_file), seed_data))
                                            print(f"  ✓ VERIFIED {filename}: Video path matches exactly")
                                        else:
                                            print(f"  ⚠ SKIPPING {filename}: Video path mismatch (different video)")
                                    else:
                                        # No video_path - use with caution
                                        found_files.append((seed_file, os.path.getmtime(seed_file), seed_data))
                                        print(f"  ⚠ WARNING: {filename} has no 'video_path' - using filename match only")
                                except:
                                    pass
                except:
                    pass
            
            # Sort by modification time (newest first) and load the most recent
            if found_files:
                found_files.sort(key=lambda x: x[1], reverse=True)
                seed_file, mod_time, seed_data = found_files[0]
                
                print(f"  📋 Selected {os.path.basename(seed_file)} (newest of {len(found_files)} matching files)")
                
                try:
                    if "anchor_frames" in seed_data:
                        # Convert string keys back to integers
                        for frame_str, anchors in seed_data["anchor_frames"].items():
                            frame_num = int(frame_str)
                            if frame_num not in self.anchor_frames:
                                self.anchor_frames[frame_num] = []
                            # Merge anchors (avoid duplicates)
                            for anchor in anchors:
                                if anchor not in self.anchor_frames[frame_num]:
                                    self.anchor_frames[frame_num].append(anchor)
                        
                        total_anchors = sum(len(anchors) for anchors in self.anchor_frames.values())
                        if total_anchors > 0:
                            print(f"✓ Loaded {total_anchors} existing anchor frame tag(s) from {len(self.anchor_frames)} frames: {os.path.basename(seed_file)}")
                            
                            # Show which players are in the anchor frames
                            players_in_anchors = set()
                            for frame_num, anchors in self.anchor_frames.items():
                                for anchor in anchors:
                                    player_name = anchor.get('player_name', '')
                                    if player_name:
                                        players_in_anchors.add(player_name)
                            
                            if players_in_anchors:
                                players_list = sorted(players_in_anchors)
                                print(f"  📋 Players in anchor frames: {', '.join(players_list)}")
                        else:
                            print(f"  ℹ Anchor file exists but contains no anchor frames")
                    else:
                        print(f"  ⚠ {os.path.basename(seed_file)} has no 'anchor_frames' key")
                except Exception as e:
                    print(f"⚠ Could not load anchor frames from {seed_file}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"ℹ No PlayerTagsSeed files found for video: {video_basename}")
                print(f"   → You can add players and they will be saved to a new PlayerTagsSeed file")
        except Exception as e:
            print(f"⚠ Could not load existing anchor frames: {e}")
            import traceback
            traceback.print_exc()
    
    def save_anchor_frames(self):
        """Save anchor frames to seed config file"""
        if not self.video_path or not self.anchor_frames:
            return
        
        try:
            import json
            
            # Determine seed config file path
            video_dir = os.path.dirname(os.path.abspath(self.video_path))
            video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
            seed_file = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
            
            # Also try seed_config.json as fallback
            seed_file_fallback = os.path.join(video_dir, "seed_config.json")
            
            # Try to load existing seed config
            seed_data = {}
            if os.path.exists(seed_file):
                try:
                    with open(seed_file, 'r') as f:
                        seed_data = json.load(f)
                except:
                    pass
            elif os.path.exists(seed_file_fallback):
                try:
                    with open(seed_file_fallback, 'r') as f:
                        seed_data = json.load(f)
                    seed_file = seed_file_fallback
                except:
                    pass
            
            # Merge anchor frames (new ones take precedence for same frame)
            if "anchor_frames" not in seed_data:
                seed_data["anchor_frames"] = {}
            
            # Convert frame numbers to strings for JSON
            for frame_num, anchors in self.anchor_frames.items():
                frame_str = str(frame_num)
                if frame_str not in seed_data["anchor_frames"]:
                    seed_data["anchor_frames"][frame_str] = []
                # Add new anchors (avoid duplicates)
                for anchor in anchors:
                    # Check if this anchor already exists (same player_name and similar bbox)
                    exists = False
                    for existing in seed_data["anchor_frames"][frame_str]:
                        if (existing.get("player_name") == anchor.get("player_name") and
                            existing.get("bbox") == anchor.get("bbox")):
                            exists = True
                            break
                    if not exists:
                        seed_data["anchor_frames"][frame_str].append(anchor)
            
            # Save updated seed config
            seed_data["video_path"] = self.video_path
            with open(seed_file, 'w') as f:
                json.dump(seed_data, f, indent=4)
            
            total_anchors = sum(len(anchors) for anchors in seed_data["anchor_frames"].values())
            print(f"  ✓ Saved {total_anchors} anchor frame tag(s) to {os.path.basename(seed_file)}")
            
        except Exception as e:
            print(f"  ⚠ Could not save anchor frames: {e}")
            traceback.print_exc()
    
    def update_gallery_list(self):
        """Update the gallery stats and recent additions list"""
        try:
            # Check if widgets still exist (window might be closed)
            if not hasattr(self, 'gallery_stats_label') or not self.gallery_stats_label.winfo_exists():
                return
            if not hasattr(self, 'recent_listbox') or not self.recent_listbox.winfo_exists():
                return
            
            stats = self.gallery.get_stats()
            self.gallery_stats_label.config(text=f"{stats['total_players']} players")
            
            # Update recent additions
            self.recent_listbox.delete(0, tk.END)
            all_players = self.gallery.list_players()
            
            # Show last 10 players (most recent first) with confidence
            for player_id, player_name in all_players[-10:][::-1]:
                # Get confidence metrics
                confidence_metrics = self.gallery.get_player_confidence_metrics(player_id)
                overall_conf = confidence_metrics['overall_confidence']
                
                # Format confidence display
                if overall_conf >= 0.7:
                    conf_display = f"High ({overall_conf:.2f})"
                    conf_color = "green"
                elif overall_conf >= 0.4:
                    conf_display = f"Med ({overall_conf:.2f})"
                    conf_color = "orange"
                else:
                    conf_display = f"Low ({overall_conf:.2f})"
                    conf_color = "red"
                
                display_text = f"{player_name} - {conf_display}"
                idx = self.recent_listbox.insert(tk.END, display_text)
                # Color-code by confidence
                try:
                    self.recent_listbox.itemconfig(idx, foreground=conf_color)
                except (tk.TclError, AttributeError):
                    # Fallback if itemconfig fails (some Tkinter versions)
                    pass
                
        except tk.TclError as e:
            # Widget was destroyed - this is expected if window is closed
            if "invalid command name" not in str(e):
                print(f"⚠ Could not update gallery list: {e}")
        except Exception as e:
            print(f"⚠ Could not update gallery list: {e}")
    
    def on_player_double_click(self, event):
        """Handle double-click on player in recent list"""
        selection = self.recent_listbox.curselection()
        if not selection:
            return
        
        player_name = self.recent_listbox.get(selection[0])
        
        # Find player ID
        all_players = self.gallery.list_players()
        for player_id, pname in all_players:
            if pname == player_name:
                self.show_player_details(player_id)
                break
    
    def show_player_details(self, player_id):
        """Show detailed player information with edit/delete options"""
        try:
            profile = self.gallery.get_player(player_id)
            if not profile:
                messagebox.showerror("Error", f"Player not found in gallery")
                return
            
            # Create detail window
            detail_window = tk.Toplevel(self.root)
            detail_window.title(f"Player Details - {profile.name}")
            detail_window.geometry("450x550")
            detail_window.transient(self.root)
            
            # Main frame
            main_frame = ttk.Frame(detail_window, padding="15")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            ttk.Label(main_frame, text=profile.name, font=("Arial", 14, "bold")).pack(pady=(0, 10))
            
            # Player info
            info_frame = ttk.LabelFrame(main_frame, text="Player Information", padding="10")
            info_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Editable fields
            ttk.Label(info_frame, text="Player Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            name_var = tk.StringVar(value=profile.name if profile.name else "")
            name_entry = ttk.Entry(info_frame, textvariable=name_var, width=25)
            name_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
            
            ttk.Label(info_frame, text="Jersey Number:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
            jersey_var = tk.StringVar(value=profile.jersey_number if profile.jersey_number else "")
            jersey_entry = ttk.Entry(info_frame, textvariable=jersey_var, width=10)
            jersey_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
            
            ttk.Label(info_frame, text="Team:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
            team_var = tk.StringVar(value=profile.team if profile.team else "")
            team_entry = ttk.Entry(info_frame, textvariable=team_var, width=20)
            team_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
            
            # Read-only info
            ttk.Label(info_frame, text="Has Re-ID Features:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
            has_features = "✓ Yes" if profile.features is not None else "✗ No"
            ttk.Label(info_frame, text=has_features, 
                     foreground="green" if profile.features is not None else "red").grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
            
            ttk.Label(info_frame, text="Reference Frames:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
            ref_count = len(profile.reference_frames) if profile.reference_frames else 0
            ttk.Label(info_frame, text=str(ref_count)).grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
            
            # Confidence metrics section
            confidence_metrics = self.gallery.get_player_confidence_metrics(player_id)
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
            
            # Reference frames list
            if ref_count > 0:
                ref_frame = ttk.LabelFrame(main_frame, text="Reference Frames", padding="10")
                ref_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
                
                ref_listbox = tk.Listbox(ref_frame, height=6, font=("Arial", 8))
                ref_listbox.pack(fill=tk.BOTH, expand=True)
                
                for i, ref in enumerate(profile.reference_frames):
                    video_name = os.path.basename(ref.get('video_path', 'unknown')) if ref.get('video_path') else 'unknown'
                    frame_num = ref.get('frame_num', '?')
                    ref_listbox.insert(tk.END, f"{i+1}. {video_name} - Frame {frame_num}")
            
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
                    
                    self.gallery.update_player(
                        player_id=player_id,
                        name=new_name,
                        jersey_number=new_jersey,
                        team=new_team
                    )
                    
                    messagebox.showinfo("Success", f"Updated {new_name}!")
                    detail_window.destroy()
                    self.update_gallery_list()
                    self.update_player_dropdown()
                except Exception as e:
                    messagebox.showerror("Error", f"Could not update:\n\n{str(e)}")
            
            def delete_player():
                result = messagebox.askyesno(
                    "Confirm Delete", 
                    f"Delete '{profile.name}' from gallery?\n\nThis cannot be undone!",
                    icon='warning'
                )
                
                if result:
                    try:
                        self.gallery.remove_player(player_id)
                        messagebox.showinfo("Success", f"Deleted {profile.name}")
                        detail_window.destroy()
                        self.update_gallery_list()
                        self.update_player_dropdown()
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not delete:\n\n{str(e)}")
            
            ttk.Button(button_frame, text="Save", command=save_changes, width=12).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Delete", command=delete_player, width=12).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Close", command=detail_window.destroy, width=10).pack(side=tk.RIGHT, padx=5)
            
            detail_window.lift()
            detail_window.focus_force()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not show details:\n\n{str(e)}")
    
    def show_gallery_window(self):
        """Show gallery management window"""
        gallery_window = tk.Toplevel(self.root)
        gallery_window.title("Player Gallery")
        gallery_window.geometry("600x500")
        
        # Gallery list
        frame = ttk.Frame(gallery_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Current Gallery", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        # Listbox with scrollbar
        listbox_frame = ttk.Frame(frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(listbox_frame, font=("Arial", 10), yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Populate list
        all_players = self.gallery.list_players()
        for player_id, player_name in all_players:
            profile = self.gallery.get_player(player_id)
            jersey = f" (#{profile.jersey_number})" if profile and profile.jersey_number else ""
            ref_count = len(profile.reference_frames) if profile and profile.reference_frames else 0
            listbox.insert(tk.END, f"{player_name}{jersey} - {ref_count} frames")
        
        # Stats
        stats = self.gallery.get_stats()
        stats_text = f"\nTotal Players: {stats['total_players']}\nWith Re-ID: {stats['players_with_features']}"
        ttk.Label(frame, text=stats_text, font=("Arial", 9)).pack(pady=(10, 0))
        
        # Close button
        ttk.Button(frame, text="Close", command=gallery_window.destroy).pack(pady=(10, 0))
    
    def show_help(self):
        """Show help dialog"""
        help_text = """
Player Gallery Seeder - Help

LOADING VIDEO:
1. Click "Load Video" to select a video file
2. Use ◀/▶ buttons or slider to navigate frames

TAGGING PLAYERS:
1. Draw a box around a player (left-click & drag)
2. Select existing player from dropdown OR type new name
3. Enter jersey number and team (optional)
4. Click "Add to Gallery"

ZOOM & PAN:
• Mouse wheel: Zoom in/out
• 🔍+ / 🔍− buttons: Zoom in/out
• Right-click & drag: Pan around
• "Fit" button: Reset zoom
• "1:1" button: View at actual size

MULTI-VIDEO TAGGING:
• Tag the same player in different videos
• System will update their profile automatically
• More reference frames = better recognition

TIPS:
• Tag 3-5 clear shots per player
• Use zoom to verify jersey numbers
• Tag from multiple videos for best results
• Double-click player names to edit/view details
"""
        messagebox.showinfo("Help", help_text)


def main():
    """Main entry point"""
    root = tk.Tk()
    app = PlayerGallerySeeder(root)
    root.mainloop()


if __name__ == "__main__":
    main()

