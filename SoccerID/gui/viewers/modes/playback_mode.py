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
        super().__init__(parent_frame, viewer, video_manager, detection_manager,
                        reid_manager, gallery_manager, csv_manager, anchor_manager)
        
        # Analytics data
        self.analytics_data = {}  # frame_num -> {player_id: {analytics_dict}}
        self.analytics_preferences = self.load_analytics_preferences()
        self.show_analytics = tk.BooleanVar(value=len([k for k, v in self.analytics_preferences.items() if v]) > 0)
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
        
        # Event marker system
        if EVENT_MARKER_AVAILABLE:
            self.event_marker_system = EventMarkerSystem(video_path=self.video_manager.video_path)
            self.event_marker_visible = tk.BooleanVar(value=True)
            self.current_event_type = tk.StringVar(value="pass")
        else:
            self.event_marker_system = None
        
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
        self.load_team_colors()
        
        # Player column mapping for consistent banner layout
        self._player_column_map = {}
        self._column_player_map = {}
    
    def create_ui(self):
        """Create playback mode UI"""
        # Main layout: video on left, controls on right
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Video canvas
        video_frame = ttk.Frame(main_frame)
        video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.canvas = tk.Canvas(video_frame, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Controls panel
        controls_frame = ttk.Frame(main_frame, width=450)
        controls_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        controls_frame.pack_propagate(False)
        
        # Playback controls
        playback_frame = ttk.LabelFrame(controls_frame, text="Playback", padding=5)
        playback_frame.pack(fill=tk.X, pady=5)
        
        self.play_button = ttk.Button(playback_frame, text="▶ Play", command=self.toggle_play)
        self.play_button.pack(fill=tk.X, pady=2)
        
        nav_buttons = ttk.Frame(playback_frame)
        nav_buttons.pack(fill=tk.X, pady=2)
        ttk.Button(nav_buttons, text="◄◄ First", command=self.first_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_buttons, text="◄ Prev", command=self.prev_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_buttons, text="Next ►", command=self.next_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_buttons, text="Last ►►", command=self.last_frame).pack(side=tk.LEFT, padx=2)
        
        # Frame slider
        frame_frame = ttk.Frame(playback_frame)
        frame_frame.pack(fill=tk.X, pady=5)
        ttk.Label(frame_frame, text="Frame:").pack(side=tk.LEFT)
        self.frame_var = tk.IntVar(value=0)
        frame_scale = ttk.Scale(frame_frame, from_=0, to=999999, 
                               variable=self.frame_var, orient=tk.HORIZONTAL)
        frame_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        frame_scale.bind('<ButtonRelease-1>', lambda e: self.goto_frame())
        
        # Overlay controls
        overlay_frame = ttk.LabelFrame(controls_frame, text="Overlays", padding=5)
        overlay_frame.pack(fill=tk.X, pady=5)
        
        self.show_players_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(overlay_frame, text="Show Players", 
                       variable=self.show_players_var,
                       command=self.update_display).pack(anchor=tk.W)
        
        self.show_ball_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(overlay_frame, text="Show Ball", 
                       variable=self.show_ball_var,
                       command=self.update_display).pack(anchor=tk.W)
        
        self.show_labels_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(overlay_frame, text="Show Labels", 
                       variable=self.show_labels_var,
                       command=self.update_display).pack(anchor=tk.W)
        
        self.show_trajectories_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(overlay_frame, text="Show Trajectories", 
                       variable=self.show_trajectories_var,
                       command=self.update_display).pack(anchor=tk.W)
        
        # Analytics controls
        analytics_frame = ttk.LabelFrame(controls_frame, text="Analytics", padding=5)
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
        
        # Event markers (if available)
        if EVENT_MARKER_AVAILABLE and self.event_marker_system:
            marker_frame = ttk.LabelFrame(controls_frame, text="Event Markers", padding=5)
            marker_frame.pack(fill=tk.X, pady=5)
            
            ttk.Checkbutton(marker_frame, text="Show Markers", 
                           variable=self.event_marker_visible,
                           command=self.update_display).pack(anchor=tk.W)
            
            ttk.Label(marker_frame, text="Event Type:").pack(anchor=tk.W, pady=(5, 0))
            event_combo = ttk.Combobox(marker_frame, textvariable=self.current_event_type,
                                      values=["pass", "shot", "goal", "tackle", "save", "corner"],
                                      state='readonly', width=20)
            event_combo.pack(fill=tk.X, pady=2)
        
        # Status
        self.status_label = ttk.Label(controls_frame, text="Ready")
        self.status_label.pack(fill=tk.X, pady=5)
    
    def display_frame(self, frame: np.ndarray, frame_num: int):
        """Display a frame with overlays and analytics"""
        if frame is None:
            return
        
        display_frame = frame.copy()
        
        # Draw CSV overlays if available
        if self.csv_manager.is_loaded():
            # Draw players
            if self.show_players_var.get():
                player_data = self.csv_manager.get_player_data(frame_num)
                for player_id, (x, y, team, name, bbox) in player_data.items():
                    # Convert coordinates if normalized
                    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                        x = int(x * self.video_manager.width)
                        y = int(y * self.video_manager.height)
                    
                    # Draw circle at player position
                    color = self.get_player_color(int(player_id), team, name)
                    cv2.circle(display_frame, (int(x), int(y)), 10, color, 2)
                    
                    # Draw label
                    if self.show_labels_var.get() and name:
                        cv2.putText(display_frame, name, (int(x) + 15, int(y)),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
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
        
        # Render analytics
        if self.show_analytics.get() and self.analytics_data:
            display_frame = self.render_analytics(display_frame, frame_num)
        
        # Draw event markers
        if self.event_marker_system and self.event_marker_visible.get():
            display_frame = self.draw_event_markers(display_frame, frame_num)
        
        # Display
        self._display_image(display_frame)
    
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
        for i, (player_name, analytics_lines, player_color, player_id) in enumerate(all_analytics[:max_players]):
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
            
            text_y += len(analytics_lines[:3]) * line_height + 15
            if text_y > pos[1] + panel_size[1] - 10:
                break
        
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
        
        # Get events for this frame (within ±2 frames)
        events = self.event_marker_system.get_events_near_frame(frame_num, tolerance=2)
        
        for event in events:
            # Draw marker at event position (if available)
            if hasattr(event, 'x') and hasattr(event, 'y'):
                x, y = int(event.x), int(event.y)
                cv2.circle(display_frame, (x, y), 15, (0, 255, 255), 3)
                cv2.putText(display_frame, event.event_type.upper(), (x + 20, y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        return display_frame
    
    def get_player_color(self, player_id: int, team: str, name: str) -> tuple:
        """Get color for a player"""
        if self.team_colors:
            # Try to get team color
            team_name_lower = (team or "").lower()
            for team_key in ["team1", "team2"]:
                team_data = self.team_colors.get('team_colors', {}).get(team_key, {})
                if team_data.get('name', '').lower() == team_name_lower:
                    tracker_color = team_data.get('tracker_color_bgr')
                    if tracker_color:
                        return tuple(tracker_color[:3])
        
        # Default colors
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
            self.start_buffer_thread()
            self.play()
        else:
            self.play_button.config(text="▶ Play")
            if self.play_after_id:
                self.viewer.root.after_cancel(self.play_after_id)
                self.play_after_id = None
            self.stop_buffer_thread()
    
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
            self.buffer_thread.join(timeout=1.0)
    
    def _buffer_worker(self):
        """Background frame buffering"""
        while self.buffer_thread_running and self.video_manager.cap:
            try:
                if not self.is_playing:
                    time.sleep(0.1)
                    continue
                
                current_frame = self.viewer.current_frame_num
                target_frame = current_frame + self.buffer_read_ahead
                
                with self.buffer_lock:
                    buffer_size = len(self.frame_buffer)
                    if target_frame in self.frame_buffer or buffer_size >= self.buffer_max_size:
                        time.sleep(0.05)
                        continue
                
                if target_frame < self.video_manager.total_frames:
                    frame = self.video_manager.get_frame(target_frame)
                    if frame is not None:
                        with self.buffer_lock:
                            self.frame_buffer[target_frame] = frame
                            while len(self.frame_buffer) > self.buffer_max_size:
                                self.frame_buffer.popitem(last=False)
                
                time.sleep(0.01)
            except:
                time.sleep(0.1)
    
    def update_display(self):
        """Update display with current frame"""
        self.viewer.load_frame(self.viewer.current_frame_num)
    
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
            frame_num = self.frame_var.get()
        
        frame_num = max(0, min(frame_num, self.video_manager.total_frames - 1))
        self.frame_var.set(frame_num)
        self.viewer.load_frame(frame_num)
    
    def on_video_loaded(self):
        if self.video_manager.total_frames > 0:
            self.frame_var.set(0)
            # Update scale range
            for widget in self.parent_frame.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Scale):
                        child.config(to=self.video_manager.total_frames - 1)
            self.goto_frame(0)
            self.status_label.config(text=f"Video loaded: {self.video_manager.total_frames} frames")
    
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
        
        self.update_display()
        self.status_label.config(text="CSV loaded - Analytics available")
    
    def cleanup(self):
        if self.play_after_id:
            self.viewer.root.after_cancel(self.play_after_id)
        self.is_playing = False
        self.stop_buffer_thread()
