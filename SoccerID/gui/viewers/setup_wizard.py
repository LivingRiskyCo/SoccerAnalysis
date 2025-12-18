"""
Interactive Setup Wizard
Frame-by-frame player tagging and ball verification to seed tracking
"""

import cv2
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import json
import os
from collections import defaultdict

# Try new structure imports first, fallback to legacy
try:
    from ...events.marker_system import EventMarkerSystem, EventMarker, EventType
    EVENT_MARKER_AVAILABLE = True
except ImportError:
    try:
        from SoccerID.events.marker_system import EventMarkerSystem, EventMarker, EventType
        EVENT_MARKER_AVAILABLE = True
    except ImportError:
        # Legacy fallback
        try:
            from event_marker_system import EventMarkerSystem, EventMarker, EventType
            EVENT_MARKER_AVAILABLE = True
        except ImportError:
            EVENT_MARKER_AVAILABLE = False
            print("Warning: Event marker system not available")

try:
    from ultralytics import YOLO
    import supervision as sv
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: YOLO not available. Setup wizard requires YOLO.")

# OC-SORT tracker import (better occlusion handling)
try:
    from ocsort_tracker import OCSortTracker
    OCSORT_AVAILABLE = True
except ImportError:
    OCSORT_AVAILABLE = False
    print("Warning: OC-SORT tracker not available. Will use ByteTrack as fallback.")


class SetupWizard:
    def __init__(self, root, video_path=None, csv_path=None):
        self.root = root
        self.root.title("Interactive Setup Wizard - Player & Ball Calibration")
        # Larger window size for better visibility
        self.root.geometry("1920x1200")
        self.root.minsize(1600, 1000)  # Minimum size
        # Allow manual resizing and ensure minimize/maximize buttons are visible
        self.root.resizable(True, True)
        # Ensure window has standard title bar controls (minimize, maximize, close)
        # This is the default, but we make sure overrideredirect is not set
        try:
            self.root.overrideredirect(False)  # Ensure standard window controls are visible
        except:
            pass  # If already False, that's fine
        
        # Explicitly ensure window can be minimized and maximized
        # On Windows, we may need to set window attributes after the window is shown
        try:
            # Ensure the window is resizable (allows maximize)
            self.root.resizable(True, True)
            # Set window attributes to ensure standard controls are visible
            # This is especially important on Windows
            if hasattr(self.root, 'attributes'):
                # Ensure the window is not toolwindow (toolwindows don't show in taskbar)
                self.root.attributes('-toolwindow', False)
                # Ensure the window is not topmost (which can interfere with controls)
                # We'll set topmost later if needed, but not during initialization
        except:
            pass
        
        # Ensure window is visible and on top - use aggressive Windows-specific approach
        self.root.withdraw()  # Hide first to ensure clean state
        self.root.update()
        self.root.update_idletasks()
        
        # Try Windows-specific window activation (if available)
        try:
            import ctypes
            # Get window handle and force activation
            hwnd = self.root.winfo_id()
            if hwnd:
                # Force window to foreground (Windows API)
                ctypes.windll.user32.ShowWindow(hwnd, 1)  # SW_SHOWNORMAL
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                ctypes.windll.user32.BringWindowToTop(hwnd)
        except:
            pass  # Fallback to Tkinter methods
        
        self.root.deiconify()  # Show window
        self.root.state('normal')  # Ensure normal state (not minimized/maximized)
        
        # Ensure window controls are visible after showing
        try:
            # Force window to have standard controls (minimize, maximize, close)
            self.root.overrideredirect(False)
            self.root.resizable(True, True)
            # On Windows, ensure the window style includes minimize/maximize buttons
            if hasattr(self.root, 'attributes'):
                self.root.attributes('-toolwindow', False)
        except:
            pass
        
        self.root.lift()  # Bring to front
        self.root.focus_set()  # Set focus
        self.root.focus_force()  # Force focus (works on Windows)
        self.root.update()  # Update window state immediately
        self.root.update_idletasks()  # Process all pending events
        
        # Video and model
        self.video_path = video_path  # Allow video path to be passed in
        self.csv_path = csv_path  # Allow CSV path to be passed in for loading tracking data
        self.csv_data = None  # Store loaded CSV data
        self.cap = None
        self.model = None
        self.tracker = None
        self.reid_tracker = None  # Re-ID tracker for maintaining player identity
        self.jersey_ocr = None  # Jersey number OCR for automatic jersey detection
        self.hard_negative_miner = None  # Hard negative mining for better discrimination
        self.gait_analyzer = None  # Gait analyzer for movement signature matching
        
        # Video properties
        self.fps = 30.0
        self.total_frames = 0
        self.current_frame_num = 0
        self.width = 0
        self.height = 0
        
        # Detection data
        self.detections_history = {}  # frame_num -> detections
        self.approved_mappings = {}  # track_id -> (player_name, team)
        self.referee_mappings = {}  # track_id -> referee_name (separate from players)
        self.rejected_ids = set()  # IDs to ignore
        self.merged_ids = {}  # track_id -> merged_to_id
        self.ball_positions = []  # (frame_num, x, y) for ball
        
        # Player identity protection: track when players were last manually tagged
        # Format: {player_name: (last_tagged_frame, last_tagged_track_id)}
        # This prevents overwriting recently tagged players for at least 2 frames
        self.player_tag_protection = {}  # player_name -> (frame_num, track_id)
        self.tag_protection_frames = 2  # Protect player identity for N frames after manual tagging
        
        # Position-based matching for when track IDs change
        self.player_positions = {}  # player_name -> list of (frame_num, x, y, track_id) for position-based matching
        
        # Re-ID feature storage for appearance-based matching
        self.player_reid_features = {}  # player_name -> list of (frame_num, reid_features) for Re-ID matching
        self.frame_reid_features = {}  # frame_num -> {track_id: features} for per-frame Re-ID features
        self.frame_foot_features = {}  # frame_num -> {track_id: foot_features} for per-frame foot Re-ID features
        self.gallery_suggestions = {}  # track_id -> (player_name, confidence) for gallery-based suggestions
        
        # Re-ID configuration
        self.reid_auto_tag_threshold = 0.8  # Auto-tag threshold (high confidence)
        self.reid_suggestion_threshold = 0.6  # Suggestion threshold (medium confidence)
        self.reid_training_mode = False  # Training mode: learn from manual confirmations
        self.reid_training_pairs = []  # List of (frame1, track_id1, frame2, track_id2) pairs for training
        
        # Player Gallery for cross-video identification
        self.player_gallery = None
        try:
            # Try new structure imports first
            try:
                from ...models.player_gallery import PlayerGallery
            except ImportError:
                try:
                    from SoccerID.models.player_gallery import PlayerGallery
                except ImportError:
                    # Legacy fallback
                    from player_gallery import PlayerGallery
            self.player_gallery = PlayerGallery()
            self.player_gallery.load_gallery()
            print(f"✓ Loaded player gallery with {len(self.player_gallery.players)} players")
        except Exception as e:
            print(f"⚠ Could not load player gallery: {e}")
            self.player_gallery = None
        
        # ANCHOR FRAMES: Store frame-level player tags with 1.00 confidence
        # Format: {frame_num: [{track_id, player_name, bbox: [x1, y1, x2, y2], confidence: 1.00, team}]}
        self.anchor_frames = {}  # frame_num -> list of anchor player tags
        
        # Substitution tracking
        self.substitution_events = []  # List of {frame_num, player_id, action: "on"/"off", team, player_name}
        self.player_roster = {}  # player_name -> {team, jersey_number, active: bool, first_seen_frame, last_seen_frame}
        
        # Player name list
        self.player_name_list = []  # List of available player names
        self.load_player_name_list()
        
        # Current frame data
        self.current_detections = None
        self.current_frame = None
        
        # Playback state
        self.is_playing = False
        
        # Zoom and pan state
        self.zoom_factor = 1.0  # 1.0 = no zoom, >1.0 = zoomed in
        self.pan_x = 0  # Pan offset in pixels (starts at 0 for centered)
        self.pan_y = 0  # Pan offset in pixels (starts at 0 for centered)
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        # Track if this is the first display update (for initial centering)
        self._first_display = True
        
        # UI state
        self.selected_detection = None
        self.show_ball_detection = tk.BooleanVar(value=True)
        self.listbox_to_detection_map = {}  # Map listbox index to detection index
        self.name_combo_focused = False  # Track if name combobox has focus
        
        # Event marker system
        if EVENT_MARKER_AVAILABLE:
            self.event_marker_system = EventMarkerSystem(video_path=self.video_path)
            self.event_marker_visible = tk.BooleanVar(value=True)
            self.current_event_type = tk.StringVar(value="pass")
        else:
            self.event_marker_system = None
        
        # Manual detection state
        self.manual_detection_mode = False
        self.drawing_box = False
        self.box_start = None
        self.box_end = None
        self.current_box_id = None  # Canvas item ID for the box being drawn
        self.next_manual_id = 10000  # Start manual IDs from 10000 to avoid conflicts
        
        # Manual detection tracking across frames
        self.manual_detections_history = {}  # frame_num -> list of {id, xyxy, velocity}
        self.manual_detection_velocities = {}  # manual_id -> (vx, vy) for position prediction
        
        # Team colors for visualization
        self.team_colors = None
        self.load_team_colors()
        
        # Auto-save state
        self.auto_save_enabled = True
        self.auto_save_interval = 30000  # 30 seconds in milliseconds
        self.last_auto_save = 0
        self.auto_save_job = None
        self.auto_save_enabled_var = tk.BooleanVar(value=True)  # For checkbox
        
        # Load existing player names if available
        self.load_existing_player_names()
        
        self.create_widgets()
        
        # Start auto-save timer
        self.start_auto_save()
        
        # Auto-load video if path was provided (after widgets are created)
        if self.video_path and os.path.exists(self.video_path):
            self.root.after(500, self.auto_load_video)  # Delay to ensure GUI is fully ready
        
        # Auto-load CSV if path was provided
        if self.csv_path and os.path.exists(self.csv_path):
            self.root.after(700, lambda: self.load_csv_data(self.csv_path))  # Load CSV after video
    
    def _show_file_dialog(self, dialog_func, *args, **kwargs):
        """Helper function to show file dialogs above the wizard window"""
        # Temporarily remove topmost to allow file dialog to appear
        was_topmost = self.root.attributes('-topmost')
        if was_topmost:
            self.root.attributes('-topmost', False)
            self.root.update()
        
        # Ensure parent is set for the dialog
        if 'parent' not in kwargs:
            kwargs['parent'] = self.root
        
        try:
            result = dialog_func(*args, **kwargs)
        finally:
            # Restore topmost if it was set
            if was_topmost:
                self.root.attributes('-topmost', True)
                self.root.update()
        
        return result
    
    def load_csv_data(self, csv_path):
        """Load CSV tracking data if available"""
        try:
            if csv_path and os.path.exists(csv_path):
                self.csv_data = pd.read_csv(csv_path)
                self.csv_path = csv_path  # Store the path
                print(f"✓ Loaded CSV data: {len(self.csv_data)} rows from {os.path.basename(csv_path)}")
                # Update CSV file label
                if hasattr(self, 'csv_file_label'):
                    self.csv_file_label.config(text=f"CSV: {os.path.basename(csv_path)}")
        except Exception as e:
            print(f"⚠ Could not load CSV data: {e}")
            if hasattr(self, 'csv_file_label'):
                self.csv_file_label.config(text="CSV: Error loading file")
    
    def load_csv_file(self):
        """Load CSV file manually"""
        filename = self._show_file_dialog(
            filedialog.askopenfilename,
            title="Load CSV Tracking Data",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.csv_path = filename
            self.load_csv_data(filename)
    
    def auto_load_video(self):
        """Auto-load video if path was provided"""
        if self.video_path and os.path.exists(self.video_path):
            self.cap = cv2.VideoCapture(self.video_path)
            
            # Get video properties
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
            self.total_frames = int(frame_count) if frame_count and not np.isnan(frame_count) else 0
            width_val = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height_val = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            self.width = int(width_val) if width_val and not np.isnan(width_val) else 0
            self.height = int(height_val) if height_val and not np.isnan(height_val) else 0
            
            if self.total_frames > 0:
                # Frame slider was moved to nav bar, but we still need to update frame_var
                if hasattr(self, 'frame_var'):
                    self.frame_var.set(0)
                self.current_frame_num = 0
                video_name = os.path.basename(self.video_path)
                self.status_label.config(text=f"Video: {video_name} ({self.total_frames} frames)")
                # Update video file label
                if hasattr(self, 'video_file_label'):
                    self.video_file_label.config(text=f"Video: {video_name}")
                # Also update window title to show video name
                self.root.title(f"Interactive Setup Wizard - {video_name}")
                self.init_button.config(state=tk.NORMAL)
                
                # Auto-load ball positions and player mappings if they exist
                self.auto_load_seed_data()
                
                # Auto-load event markers if available
                if EVENT_MARKER_AVAILABLE and self.event_marker_system:
                    self.event_marker_system.video_path = self.video_path
                    video_dir = os.path.dirname(os.path.abspath(self.video_path))
                    video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
                    marker_path = os.path.join(video_dir, f"{video_basename}_event_markers.json")
                    if os.path.exists(marker_path):
                        self.event_marker_system.load_from_file(marker_path)
                        if hasattr(self, 'marker_stats_label'):
                            self.update_marker_statistics()
                
                # Load first frame immediately and also after a delay to ensure canvas is fully rendered
                self.root.after(100, self.load_frame)
                self.root.after(300, self.load_frame)  # Backup in case first one doesn't work
            if self.cap.isOpened():
                self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
                frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
                self.total_frames = int(frame_count) if frame_count and not np.isnan(frame_count) else 0
                width_val = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height_val = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                self.width = int(width_val) if width_val and not np.isnan(width_val) else 0
                self.height = int(height_val) if height_val and not np.isnan(height_val) else 0
                
                if self.total_frames <= 0:
                    messagebox.showerror("Error", "Could not determine video frame count. The video file may be corrupted.")
                    self.cap.release()
                    self.cap = None
                    return
                
                # Frame slider was moved to nav bar, no longer exists here
                # Just update frame_var if it exists
                if hasattr(self, 'frame_var'):
                    self.frame_var.set(0)
                video_name = os.path.basename(self.video_path)
                self.status_label.config(text=f"Video: {video_name} ({self.total_frames} frames)")
                # Update video file label
                if hasattr(self, 'video_file_label'):
                    self.video_file_label.config(text=f"Video: {video_name}")
                # Update window title to show video name
                self.root.title(f"Interactive Setup Wizard - {video_name}")
                self.init_button.config(state=tk.NORMAL)
                
                # Load first frame
                self.load_frame()
        
    def load_team_colors(self):
        """Load team colors if available"""
        if os.path.exists("team_color_config.json"):
            try:
                with open("team_color_config.json", 'r') as f:
                    self.team_colors = json.load(f)
                    print(f"✓ Loaded team colors from team_color_config.json")
            except Exception as e:
                print(f"Warning: Could not load team colors: {e}")
                self.team_colors = None
    
    def open_team_color_detector(self):
        """Open Team Color Detector Helper window"""
        try:
            from team_color_detector import TeamColorDetector
            
            # Check if window already exists
            if hasattr(self, '_team_color_window') and self._team_color_window and self._team_color_window.winfo_exists():
                self._team_color_window.lift()
                self._team_color_window.focus_force()
                return
            
            # Create new window
            team_color_window = tk.Toplevel(self.root)
            team_color_window.title("Team Color Detector - Setup Wizard")
            team_color_window.transient(self.root)
            
            # Auto-load video if available
            video_path = self.video_path if self.video_path and os.path.exists(self.video_path) else None
            
            # Callback function to reload team colors after saving
            def on_team_colors_saved(team_colors, team1_name, team2_name):
                """Callback when team colors are saved"""
                self.load_team_colors()  # Reload team colors
                # Update team dropdowns with new team names
                team_names = self.get_team_names_from_config()
                team_names_with_blank = [""] + team_names
                if hasattr(self, 'team_combo'):
                    self.team_combo['values'] = team_names_with_blank
                if hasattr(self, 'quick_tag_team_combo'):
                    self.quick_tag_team_combo['values'] = team_names_with_blank
                self.status_label.config(text=f"✓ Team colors configured: {team1_name} vs {team2_name}")
                print(f"✓ Team colors updated in setup wizard: {team1_name} vs {team2_name}")
            
            # Create TeamColorDetector instance
            detector = TeamColorDetector(team_color_window, callback=on_team_colors_saved)
            
            # Auto-load video if available
            if video_path:
                detector.video_path = video_path
                detector.video_path_entry.delete(0, tk.END)
                detector.video_path_entry.insert(0, video_path)
                # Load video in detector using its own method
                detector.load_video()
                print(f"✓ Auto-loaded video in Team Color Detector: {os.path.basename(video_path)}")
            
            # Store reference
            self._team_color_window = team_color_window
            
            # Update status
            self.status_label.config(text="Team Color Detector opened - Configure HSV ranges for team recognition")
            
        except ImportError as e:
            messagebox.showerror("Error", f"Could not import team_color_detector: {e}\n\nMake sure team_color_detector.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Team Color Detector: {e}")
            import traceback
            traceback.print_exc()
    
    def load_existing_player_names(self):
        """Load existing player names from player_names.json if available"""
        if os.path.exists("player_names.json"):
            try:
                with open("player_names.json", 'r') as f:
                    loaded_names = json.load(f)
                    # Convert to tuple format (name, team, jersey_number) if needed
                    for pid, name in loaded_names.items():
                        if pid not in self.approved_mappings:
                            # Try to preserve team info if available
                            # Store as (name, "", "") - team and jersey can be set later
                            self.approved_mappings[pid] = (name, "", "")
                    print(f"✓ Loaded {len(loaded_names)} existing player mappings")
            except Exception as e:
                print(f"Warning: Could not load existing player names: {e}")
    
    def load_players_from_gallery(self):
        """Load players from player_gallery.json using PlayerGallery class"""
        gallery_players = []
        try:
            # Try to use PlayerGallery class for proper loading
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            gallery.load_gallery()
            
            # Get all players using the proper method
            player_list = gallery.list_players()  # Returns List[Tuple[str, str]]: (player_id, player_name)
            for player_id, player_name in player_list:
                if player_name and player_name not in gallery_players:
                    gallery_players.append(player_name)
            
            print(f"✓ Loaded {len(gallery_players)} players from player_gallery.json via PlayerGallery")
        except ImportError:
            print("⚠ PlayerGallery class not available, using manual JSON parsing")
        except Exception as e:
            print(f"⚠ Error loading via PlayerGallery: {e}, trying manual parse...")
        
        # Always try manual JSON parsing as fallback or supplement
        if os.path.exists("player_gallery.json"):
            try:
                with open("player_gallery.json", 'r') as f:
                    gallery_data = json.load(f)
                    
                    # PlayerGallery format: {player_id: {name: "...", ...}}
                    if isinstance(gallery_data, dict):
                        # Check if it's the PlayerGallery format (dict of player profiles)
                        for player_id, player_data in gallery_data.items():
                            if isinstance(player_data, dict):
                                # Could be PlayerProfile dict or old format
                                if 'name' in player_data:
                                    player_name = player_data['name']
                                    if player_name and player_name not in gallery_players:
                                        gallery_players.append(player_name)
                                elif 'players' in player_data:
                                    # Nested format
                                    for player in player_data['players']:
                                        if isinstance(player, dict) and 'name' in player:
                                            player_name = player['name']
                                            if player_name and player_name not in gallery_players:
                                                gallery_players.append(player_name)
                        # Also check for 'players' key at top level
                        if 'players' in gallery_data and isinstance(gallery_data['players'], list):
                            for player in gallery_data['players']:
                                if isinstance(player, dict) and 'name' in player:
                                    player_name = player['name']
                                    if player_name and player_name not in gallery_players:
                                        gallery_players.append(player_name)
                    elif isinstance(gallery_data, list):
                        # Old format: list of players
                        for player in gallery_data:
                            if isinstance(player, dict) and 'name' in player:
                                player_name = player['name']
                                if player_name and player_name not in gallery_players:
                                    gallery_players.append(player_name)
                
                if gallery_players:
                    print(f"✓ Loaded {len(gallery_players)} players from player_gallery.json (manual parse)")
            except Exception as e:
                print(f"⚠ Warning: Could not load players from gallery (manual parse): {e}")
                import traceback
                traceback.print_exc()
        
        return gallery_players
    
    def get_team_names_from_config(self):
        """Get team names from team_color_config.json - supports custom team names like 'Blue', 'Gray', etc."""
        team_names = []
        if self.team_colors:
            # Check for team_colors structure (preferred format)
            if 'team_colors' in self.team_colors:
                team_colors_dict = self.team_colors['team_colors']
                if isinstance(team_colors_dict, dict):
                    # Check for team1 and team2 keys
                    for team_key in ['team1', 'team2']:
                        if team_key in team_colors_dict:
                            team_data = team_colors_dict[team_key]
                            if isinstance(team_data, dict):
                                # Get the 'name' field from team data (e.g., "Blue", "Gray", custom name)
                                team_name = team_data.get('name', team_key)
                                if team_name and team_name not in team_names:
                                    team_names.append(team_name)
                    # Also check for any other team keys (for future extensibility)
                    for team_key, team_data in team_colors_dict.items():
                        if team_key not in ['team1', 'team2'] and isinstance(team_data, dict):
                            team_name = team_data.get('name', team_key)
                            if team_name and team_name not in team_names:
                                team_names.append(team_name)
            
            # Fallback: Check for top-level team1_name and team2_name (legacy format)
            if not team_names:
                if 'team1_name' in self.team_colors:
                    team_names.append(self.team_colors['team1_name'])
                if 'team2_name' in self.team_colors:
                    team_names.append(self.team_colors['team2_name'])
        
        # Add default options if no teams found
        if not team_names:
            team_names = ["Team 1", "Team 2"]
        
        # Always add these options (for coaches, referees, and other non-team players)
        if "Coach" not in team_names:
            team_names.append("Coach")
        if "Unknown" not in team_names:
            team_names.append("Unknown")
        if "Other" not in team_names:
            team_names.append("Other")
        
        # Note: Empty string option is added separately in UI code to allow blank selection
        return team_names
    
    def load_player_name_list(self):
        """Load the list of available player names from all sources"""
        self.player_name_list = []
        
        # 1. Load from player_name_list.json if it exists
        player_list_file = "player_name_list.json"
        if os.path.exists(player_list_file):
            try:
                with open(player_list_file, 'r') as f:
                    loaded_data = json.load(f)
                    # Ensure it's a list, not a dict
                    if isinstance(loaded_data, list):
                        self.player_name_list = loaded_data.copy()
                    elif isinstance(loaded_data, dict):
                        # If it's a dict, extract values (player names)
                        self.player_name_list = list(set(loaded_data.values()))
                        self.player_name_list.sort()
                        # Save as list format for future
                        self.save_player_name_list()
                        print(f"⚠ Converted dict to list format - saved as list")
                    else:
                        self.player_name_list = []
                    print(f"✓ Loaded {len(self.player_name_list)} player names from list")
            except Exception as e:
                print(f"Warning: Could not load player name list: {e}")
                self.player_name_list = []
        
        # 2. Also try to extract names from existing player_names.json (fallback)
        if not self.player_name_list and os.path.exists("player_names.json"):
            try:
                with open("player_names.json", 'r') as f:
                    existing_names = json.load(f)
                    # Ensure existing_names is a dict
                    if isinstance(existing_names, dict):
                        self.player_name_list = list(set(existing_names.values()))
                    elif isinstance(existing_names, list):
                        self.player_name_list = existing_names.copy()
                    else:
                        self.player_name_list = []
                    self.player_name_list.sort()
                    if self.player_name_list:
                        self.save_player_name_list()
                    print(f"✓ Extracted {len(self.player_name_list)} names from existing mappings")
            except Exception as e:
                print(f"Warning: Could not load from player_names.json: {e}")
        
        # 3. ALWAYS load players from player_gallery.json and merge them
        gallery_players = self.load_players_from_gallery()
        gallery_added = 0
        for player_name in gallery_players:
            if player_name and player_name not in self.player_name_list:
                self.player_name_list.append(player_name)
                gallery_added += 1
        
        if gallery_added > 0:
            print(f"✓ Added {gallery_added} players from gallery (total gallery: {len(gallery_players)})")
        
        # Sort and save the combined list
        if self.player_name_list:
            self.player_name_list.sort()
            self.save_player_name_list()
            print(f"✓ Total player names available: {len(self.player_name_list)}")
    
    def refresh_player_name_list(self):
        """Refresh the player name list from all sources and update UI"""
        # Clear current list and reload from all sources
        old_count = len(self.player_name_list)
        self.player_name_list = []
        self.load_player_name_list()
        
        # Update combobox values if it exists (filter to active players only)
        if hasattr(self, 'player_name_combo') and self.player_name_combo:
            try:
                active_player_list = [name for name in self.player_name_list if self.is_player_active(name)]
                self.player_name_combo['values'] = active_player_list
                print(f"✓ Updated player name combobox with {len(active_player_list)} active players (out of {len(self.player_name_list)} total)")
            except Exception as e:
                print(f"⚠ Error updating player name combobox: {e}")
        
        # Update quick tag combobox if it exists (filter to active players only)
        if hasattr(self, 'quick_tag_player_combo') and self.quick_tag_player_combo:
            try:
                active_player_list = [name for name in self.player_name_list if self.is_player_active(name)]
                self.quick_tag_player_combo['values'] = active_player_list
                print(f"✓ Updated quick tag combobox with {len(active_player_list)} active players (out of {len(self.player_name_list)} total)")
            except Exception as e:
                print(f"⚠ Error updating quick tag combobox: {e}")
        
        # Show message to user
        new_count = len(self.player_name_list)
        gallery_count = len(self.load_players_from_gallery())  # Count gallery players
        if new_count != old_count or new_count > 0:
            messagebox.showinfo("Players Refreshed", 
                              f"Loaded {new_count} players from all sources:\n"
                              f"- Player Gallery: {gallery_count} players\n"
                              f"- Player Name List\n"
                              f"- Player Names")
        
        print(f"✓ Refreshed player name list: {new_count} players available (was {old_count})")
    
    def save_player_name_list(self):
        """Save the list of available player names"""
        try:
            with open("player_name_list.json", 'w') as f:
                json.dump(self.player_name_list, f, indent=4)
        except Exception as e:
            print(f"Warning: Could not save player name list: {e}")
    
    def on_name_combo_focus(self, event):
        """Handle focus on name combobox - disable keyboard shortcuts"""
        # Unbind shortcuts temporarily when typing in combobox
        self.name_combo_focused = True
    
    def on_name_combo_unfocus(self, event):
        """Handle focus loss on name combobox - re-enable keyboard shortcuts"""
        self.name_combo_focused = False
    
    def on_name_combo_key_release(self, event):
        """Handle key release in combobox - update autocomplete"""
        current_text = self.player_name_var.get().lower()
        if current_text:
            # Filter player names that start with current text
            matches = [name for name in self.player_name_list if name.lower().startswith(current_text)]
            if matches:
                self.player_name_combo['values'] = matches
            else:
                self.player_name_combo['values'] = self.player_name_list
        else:
            self.player_name_combo['values'] = self.player_name_list
    
    def create_roster_management(self, parent_frame):
        """Create roster management UI with active/inactive checkboxes"""
        try:
            from team_roster_manager import TeamRosterManager
            self.roster_manager = TeamRosterManager()
        except Exception as e:
            print(f"⚠ Could not load roster manager: {e}")
            ttk.Label(parent_frame, text="Roster management unavailable", 
                     foreground="gray").pack(pady=5)
            return
        
        # Load roster
        roster = self.roster_manager.roster
        
        # Create scrollable frame for roster list
        roster_list_frame = ttk.Frame(parent_frame)
        roster_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollable canvas for roster
        roster_canvas = tk.Canvas(roster_list_frame, height=200, highlightthickness=0)
        roster_scrollbar = ttk.Scrollbar(roster_list_frame, orient="vertical", command=roster_canvas.yview)
        roster_inner_frame = ttk.Frame(roster_canvas)
        
        roster_canvas.configure(yscrollcommand=roster_scrollbar.set)
        roster_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        roster_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create window in canvas
        roster_window = roster_canvas.create_window((0, 0), window=roster_inner_frame, anchor="nw")
        
        def update_roster_scroll_region(event=None):
            roster_canvas.update_idletasks()
            bbox = roster_canvas.bbox("all")
            if bbox:
                roster_canvas.configure(scrollregion=bbox)
        
        roster_inner_frame.bind("<Configure>", update_roster_scroll_region)
        
        # Store checkboxes for active status
        self.roster_active_vars = {}
        
        # Header
        header_frame = ttk.Frame(roster_inner_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(header_frame, text="Player", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text="Active", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=5)
        
        # Merge with video-specific player_roster (video settings take precedence)
        # This ensures video-specific active/inactive settings are preserved
        merged_roster = {}
        for player_name, player_data in roster.items():
            if player_name == 'videos':  # Skip videos metadata
                continue
            merged_roster[player_name] = player_data.copy()
            # Override with video-specific settings if available
            if player_name in self.player_roster:
                merged_roster[player_name]['active'] = self.player_roster[player_name].get('active', player_data.get('active', True))
        
        # Also add players from video-specific roster that might not be in global roster
        for player_name, player_data in self.player_roster.items():
            if player_name not in merged_roster:
                merged_roster[player_name] = player_data.copy()
        
        # Add players from merged roster
        if merged_roster:
            for player_name, player_data in sorted(merged_roster.items()):
                player_row = ttk.Frame(roster_inner_frame)
                player_row.pack(fill=tk.X, pady=2)
                
                # Player name
                ttk.Label(player_row, text=player_name, width=25, anchor="w").pack(side=tk.LEFT, padx=5)
                
                # Active checkbox - use video-specific active status if available
                active_status = player_data.get('active', True)
                active_var = tk.BooleanVar(value=active_status)
                self.roster_active_vars[player_name] = active_var
                active_check = ttk.Checkbutton(player_row, variable=active_var, 
                                               command=lambda name=player_name: self.update_roster_active(name))
                active_check.pack(side=tk.RIGHT, padx=5)
        else:
            ttk.Label(roster_inner_frame, text="No players in roster", 
                     foreground="gray").pack(pady=10)
        
        # Buttons
        roster_buttons_frame = ttk.Frame(parent_frame)
        roster_buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(roster_buttons_frame, text="Refresh Roster", 
                  command=lambda: self.refresh_roster_display(roster_inner_frame, roster_canvas),
                  width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(roster_buttons_frame, text="Save Changes", 
                  command=self.save_roster_changes,
                  width=15).pack(side=tk.LEFT, padx=2)
        
        # Info label
        info_label = ttk.Label(parent_frame, 
                              text="Inactive players excluded from Re-ID, gallery updates, and naming",
                              font=("Arial", 7), foreground="gray", wraplength=400)
        info_label.pack(pady=2)
        
        # Update quick tag dropdown after roster is created
        # Use after() to ensure dropdown exists (it's created later in the UI)
        self.root.after(100, self.update_quick_tag_dropdown)
    
    def update_roster_active(self, player_name):
        """Update active status for a player in roster"""
        if hasattr(self, 'roster_active_vars') and player_name in self.roster_active_vars:
            active_status = self.roster_active_vars[player_name].get()
            
            # Update global roster manager
            if hasattr(self, 'roster_manager') and self.roster_manager:
                self.roster_manager.update_player(player_name, active=active_status)
            
            # CRITICAL: Also update video-specific player_roster immediately
            if player_name not in self.player_roster:
                self.player_roster[player_name] = {
                    "team": None,
                    "jersey_number": None,
                    "active": active_status,
                    "first_seen_frame": None,
                    "last_seen_frame": None
                }
            else:
                self.player_roster[player_name]["active"] = active_status
            
            print(f"✓ Updated {player_name}: active={active_status} (video-specific roster updated)")
            
            # Update quick tag dropdown to reflect active status changes
            self.update_quick_tag_dropdown()
    
    def save_roster_changes(self):
        """Save all roster changes to both global roster and video-specific seed config"""
        if not hasattr(self, 'roster_manager') or not self.roster_manager:
            messagebox.showwarning("Warning", "Roster manager not initialized. Please refresh the roster.")
            return
        
        saved_count = 0
        if hasattr(self, 'roster_active_vars'):
            for player_name, active_var in self.roster_active_vars.items():
                active_status = active_var.get()
                # Update global roster
                self.roster_manager.update_player(player_name, active=active_status)
                
                # CRITICAL: Update video-specific player_roster in seed config
                if player_name not in self.player_roster:
                    self.player_roster[player_name] = {
                        "team": None,
                        "jersey_number": None,
                        "active": active_status,
                        "first_seen_frame": None,
                        "last_seen_frame": None
                    }
                else:
                    self.player_roster[player_name]["active"] = active_status
                
                saved_count += 1
        
        if saved_count == 0:
            messagebox.showinfo("Info", "No roster changes to save")
            return
        
        # Save global roster
        try:
            self.roster_manager.save_roster()
            print(f"✓ Saved global roster: {saved_count} players updated")
        except Exception as e:
            print(f"⚠ Could not save global roster: {e}")
            messagebox.showerror("Error", f"Could not save global roster: {e}")
            return
        
        # Auto-save seed config if video is loaded (to persist video-specific settings)
        seed_saved = False
        if self.video_path:
            try:
                self.save_tags_explicitly()
                seed_saved = True
                print(f"✓ Saved video-specific seed config: {saved_count} players updated")
            except Exception as e:
                print(f"⚠ Could not auto-save seed config: {e}")
                import traceback
                traceback.print_exc()
        
        # Show success message
        if seed_saved:
            messagebox.showinfo("Saved", 
                              f"✓ Saved active status for {saved_count} player(s)\n\n"
                              f"Saved to:\n"
                              f"• Global roster (team_roster.json)\n"
                              f"• Video seed config (PlayerTagsSeed-*.json)\n\n"
                              f"These settings will persist for this video.")
        else:
            messagebox.showinfo("Saved", 
                              f"✓ Saved active status for {saved_count} player(s) to global roster\n\n"
                              f"Note: Video seed config will be saved when you export seed config or start analysis")
        
        print(f"✓ Saved roster changes: {saved_count} players updated")
        
        # Update quick tag dropdown to reflect active status changes
        self.update_quick_tag_dropdown()
    
    def update_quick_tag_dropdown(self):
        """Update the quick tag player dropdown to show only active players"""
        if not hasattr(self, 'quick_tag_player_combo') or not self.quick_tag_player_combo:
            return
        
        try:
            # Get current selection to preserve it if possible
            current_selection = self.quick_tag_player_var.get()
            
            # Filter player list to only show active players
            active_player_list = [name for name in self.player_name_list if self.is_player_active(name)]
            
            # Update dropdown values
            self.quick_tag_player_combo['values'] = active_player_list
            
            # Restore selection if it's still in the active list
            if current_selection in active_player_list:
                self.quick_tag_player_var.set(current_selection)
            else:
                # Clear selection if current player is now inactive
                self.quick_tag_player_var.set("")
            
            print(f"✓ Updated quick tag dropdown: {len(active_player_list)} active players")
        except Exception as e:
            print(f"⚠ Error updating quick tag dropdown: {e}")
    
    def refresh_roster_display(self, roster_inner_frame, roster_canvas):
        """Refresh the roster display"""
        # Clear existing widgets
        for widget in roster_inner_frame.winfo_children():
            widget.destroy()
        
        # Reload roster
        try:
            from team_roster_manager import TeamRosterManager
            self.roster_manager = TeamRosterManager()
        except Exception as e:
            print(f"⚠ Could not reload roster manager: {e}")
            return
        
        roster = self.roster_manager.roster
        
        # Recreate display
        self.roster_active_vars = {}
        
        # Header
        header_frame = ttk.Frame(roster_inner_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(header_frame, text="Player", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text="Active", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=5)
        
        # Add players
        if roster:
            for player_name, player_data in sorted(roster.items()):
                if player_name == 'videos':
                    continue
                
                player_row = ttk.Frame(roster_inner_frame)
                player_row.pack(fill=tk.X, pady=2)
                
                ttk.Label(player_row, text=player_name, width=25, anchor="w").pack(side=tk.LEFT, padx=5)
                
                active_var = tk.BooleanVar(value=player_data.get('active', True))
                self.roster_active_vars[player_name] = active_var
                active_check = ttk.Checkbutton(player_row, variable=active_var,
                                              command=lambda name=player_name: self.update_roster_active(name))
                active_check.pack(side=tk.RIGHT, padx=5)
        else:
            ttk.Label(roster_inner_frame, text="No players in roster", 
                     foreground="gray").pack(pady=10)
        
        roster_canvas.update_idletasks()
        bbox = roster_canvas.bbox("all")
        if bbox:
            roster_canvas.configure(scrollregion=bbox)
        
        # Update quick tag dropdown after refreshing roster display
        self.update_quick_tag_dropdown()
    
    def is_player_active(self, player_name):
        """Check if a player is active in the roster (checks video-specific roster first, then global)"""
        # CRITICAL: Check video-specific roster first (from seed config)
        if hasattr(self, 'player_roster') and self.player_roster:
            if player_name in self.player_roster:
                player_data = self.player_roster[player_name]
                if isinstance(player_data, dict):
                    return player_data.get('active', True)
                # If it's not a dict, assume active
                return True
        
        # Fallback to global roster manager
        if not hasattr(self, 'roster_manager'):
            try:
                from team_roster_manager import TeamRosterManager
                self.roster_manager = TeamRosterManager()
            except Exception:
                return True  # Default to active if roster unavailable
        
        if not self.roster_manager:
            return True
        
        roster = self.roster_manager.roster
        if player_name in roster:
            return roster[player_name].get('active', True)
        return True  # Default to active if player not in roster
    
    def manage_player_names(self):
        """Open dialog to manage the list of player names"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Player Names")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.lift()
        dialog.attributes('-topmost', True)
        dialog.after(200, lambda: dialog.attributes('-topmost', False))
        
        # Instructions
        ttk.Label(dialog, text="Add or remove player names from the list:", 
                 font=("Arial", 10, "bold")).pack(pady=10)
        
        # Current list
        list_frame = ttk.LabelFrame(dialog, text="Current Player Names", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Listbox with scrollbar
        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        names_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, height=15,
                                   font=("Arial", 10))
        names_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=names_listbox.yview)
        
        # Populate listbox
        for name in sorted(self.player_name_list):
            names_listbox.insert(tk.END, name)
        
        # Add name section
        add_frame = ttk.Frame(dialog)
        add_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(add_frame, text="Add Name:").pack(side=tk.LEFT, padx=5)
        new_name_entry = ttk.Entry(add_frame, width=25)
        new_name_entry.pack(side=tk.LEFT, padx=5)
        new_name_entry.focus()
        
        def add_name():
            name = new_name_entry.get().strip()
            if not name:
                messagebox.showwarning("Warning", "Please enter a player name")
                return
            
            if name in self.player_name_list:
                messagebox.showwarning("Warning", f"Player '{name}' is already in the list")
                return
            
            # Add to player name list
            self.player_name_list.append(name)
            self.player_name_list.sort()
            names_listbox.delete(0, tk.END)
            for n in self.player_name_list:
                names_listbox.insert(tk.END, n)
            new_name_entry.delete(0, tk.END)
            self.player_name_combo['values'] = self.player_name_list
            self.save_player_name_list()
            
            # Optionally add to player gallery as well
            try:
                from player_gallery import PlayerGallery
                import numpy as np
                gallery = PlayerGallery()
                
                # Check if player already exists in gallery
                existing_players = gallery.list_players()
                player_exists = False
                for player_id, player_name in existing_players:
                    if player_name.lower() == name.lower():
                        player_exists = True
                        break
                
                if not player_exists:
                    # Ask user if they want to add to gallery
                    add_to_gallery = messagebox.askyesno(
                        "Add to Gallery?",
                        f"Would you like to add '{name}' to the Player Gallery as well?\n\n"
                        f"This allows cross-video recognition. You can add Re-ID features later."
                    )
                    
                    if add_to_gallery:
                        # Create dummy feature vector (will be updated when features are added)
                        dummy_features = np.zeros(512, dtype=np.float32)
                        gallery.add_player(
                            name=name,
                            features=dummy_features
                        )
                        messagebox.showinfo("Success", f"Added '{name}' to Player Gallery!")
            except Exception as e:
                # Don't fail if gallery add fails - just log it
                print(f"⚠ Could not add to gallery: {e}")
        
        def remove_name():
            selection = names_listbox.curselection()
            if selection:
                index = selection[0]
                name = names_listbox.get(index)
                if name in self.player_name_list:
                    self.player_name_list.remove(name)
                    names_listbox.delete(index)
                    self.player_name_combo['values'] = self.player_name_list
                    self.save_player_name_list()
        
        ttk.Button(add_frame, text="Add", command=add_name).pack(side=tk.LEFT, padx=5)
        ttk.Button(add_frame, text="Remove Selected", command=remove_name).pack(side=tk.LEFT, padx=5)
        
        new_name_entry.bind("<Return>", lambda e: add_name())
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Quick add common names button
        def quick_add_common():
            common_names = ["Wesley Beckett", "Player 1", "Player 2", "Player 3", "Player 4", 
                          "Player 5", "Player 6", "Player 7", "Player 8", "Player 9", 
                          "Player 10", "Player 11", "Coach"]
            added = 0
            for name in common_names:
                if name not in self.player_name_list:
                    self.player_name_list.append(name)
                    added += 1
            if added > 0:
                self.player_name_list.sort()
                names_listbox.delete(0, tk.END)
                for n in self.player_name_list:
                    names_listbox.insert(tk.END, n)
                self.player_name_combo['values'] = self.player_name_list
                self.save_player_name_list()
                messagebox.showinfo("Added", f"Added {added} common names to the list")
        
        ttk.Button(button_frame, text="Add Common Names", command=quick_add_common).pack(side=tk.LEFT, padx=5)
    
    def create_widgets(self):
        """Create GUI widgets"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top: File selection and setup
        file_frame = ttk.LabelFrame(main_frame, text="Setup", padding="10")
        file_frame.pack(fill=tk.X, pady=5)
        
        # File loading section
        file_loading_frame = ttk.Frame(file_frame)
        file_loading_frame.pack(fill=tk.X, pady=2)
        
        ttk.Button(file_loading_frame, text="📹 Load Video", command=self.load_video, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_loading_frame, text="📊 Load CSV", command=self.load_csv_file, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_loading_frame, text="Load Backup", command=self.load_backup, width=15).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(file_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # First row of buttons
        button_row1 = ttk.Frame(file_frame)
        button_row1.pack(fill=tk.X, pady=2)
        ttk.Button(button_row1, text="🔄 Refresh Players", command=self.refresh_player_name_list, 
                  width=18).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_row1, text="🎨 Team Colors", command=self.open_team_color_detector, 
                  width=15).pack(side=tk.LEFT, padx=5)
        # Store button reference directly instead of using winfo_children index
        self.init_button = ttk.Button(button_row1, text="Initialize Detection", command=self.initialize_detection, 
                  width=20, state=tk.DISABLED)
        self.init_button.pack(side=tk.LEFT, padx=5)
        
        # Second row of buttons
        button_row2 = ttk.Frame(file_frame)
        button_row2.pack(fill=tk.X, pady=2)
        
        # Prominent Save button
        save_button = ttk.Button(button_row2, text="💾 Save Tags", command=self.save_tags_explicitly, 
                                width=15, style="Accent.TButton")
        save_button.pack(side=tk.LEFT, padx=5)
        
        # Export button
        ttk.Button(button_row2, text="📤 Export Seed Config", command=self.export_seed_config, 
                  width=18).pack(side=tk.LEFT, padx=5)
        
        # Auto-save controls
        autosave_frame = ttk.Frame(button_row2)
        autosave_frame.pack(side=tk.LEFT, padx=10)
        self.autosave_check = ttk.Checkbutton(autosave_frame, text="Auto-save", 
                                              variable=self.auto_save_enabled_var,
                                              command=self.toggle_autosave)
        self.autosave_check.pack(side=tk.LEFT, padx=2)
        self.autosave_status_label = ttk.Label(autosave_frame, text="(Every 30s)", 
                                               font=("Arial", 7), foreground="gray")
        self.autosave_status_label.pack(side=tk.LEFT, padx=2)
        
        # Status and progress on second row
        self.status_label = ttk.Label(button_row2, text="Load a video to begin", foreground="gray")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Video file label - shows loaded video file name
        self.video_file_label = ttk.Label(button_row2, text="", foreground="blue", font=("Arial", 9))
        self.video_file_label.pack(side=tk.LEFT, padx=10)
        
        # CSV file label - shows loaded CSV file name
        self.csv_file_label = ttk.Label(button_row2, text="", foreground="green", font=("Arial", 9))
        self.csv_file_label.pack(side=tk.LEFT, padx=10)
        
        # Progress indicator
        self.progress_label = ttk.Label(button_row2, text="", foreground="blue")
        self.progress_label.pack(side=tk.LEFT, padx=10)
        
        # Navigation controls - horizontal bar above video frame
        nav_bar = ttk.Frame(main_frame, padding="5")
        nav_bar.pack(fill=tk.X, pady=5)
        
        # Play/Pause button
        self.play_button = ttk.Button(nav_bar, text="▶ Play", command=self.toggle_playback, width=12)
        self.play_button.pack(side=tk.LEFT, padx=2)
        
        # Separator
        ttk.Separator(nav_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Navigation buttons
        ttk.Button(nav_bar, text="⏮ First", command=self.go_to_first, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_bar, text="◀◀ Prev", command=self.prev_frame, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_bar, text="▶▶ Next", command=self.next_frame, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_bar, text="⏭ Last", command=self.go_to_last, width=10).pack(side=tk.LEFT, padx=2)
        
        # Separator
        ttk.Separator(nav_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Smart navigation buttons
        ttk.Button(nav_bar, text="⏭ Next Untagged", command=self.jump_to_next_untagged,
                  width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_bar, text="⏮ Prev Untagged", command=self.jump_to_prev_untagged,
                  width=15).pack(side=tk.LEFT, padx=2)
        
        # Separator
        ttk.Separator(nav_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Frame number display and goto
        frame_info_frame = ttk.Frame(nav_bar)
        frame_info_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(frame_info_frame, text="Frame:").pack(side=tk.LEFT, padx=2)
        self.frame_number_label = ttk.Label(frame_info_frame, text="0 / 0", width=12)
        self.frame_number_label.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(frame_info_frame, text="Goto:").pack(side=tk.LEFT, padx=(10, 2))
        self.goto_frame_var = tk.StringVar()
        goto_entry = ttk.Entry(frame_info_frame, textvariable=self.goto_frame_var, width=8)
        goto_entry.pack(side=tk.LEFT, padx=2)
        goto_entry.bind('<Return>', lambda e: self.goto_frame())
        ttk.Button(frame_info_frame, text="Go", command=self.goto_frame, width=5).pack(side=tk.LEFT, padx=2)
        
        # Main content area
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Left: Video display
        display_frame = ttk.LabelFrame(content_frame, text="Video Frame", padding="5")
        display_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.canvas = tk.Canvas(display_frame, bg="black", cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Force canvas to update when window is mapped (fully visible)
        def on_canvas_map(event):
            # Canvas is now visible, force a display update if video is loaded
            if hasattr(self, 'current_frame') and self.current_frame is not None:
                self.root.after(50, self.update_display)
        self.canvas.bind("<Map>", on_canvas_map)
        
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Motion>", self.on_canvas_hover)
        
        # Zoom controls - mouse wheel
        self.canvas.bind("<MouseWheel>", self.on_canvas_zoom)
        self.canvas.bind("<Button-4>", self.on_canvas_zoom)  # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_canvas_zoom)  # Linux scroll down
        
        # Pan controls - right mouse button or middle mouse button
        self.canvas.bind("<Button-2>", self.on_canvas_pan_start)  # Middle mouse button
        self.canvas.bind("<Button-3>", self.on_canvas_pan_start)  # Right mouse button
        self.canvas.bind("<B2-Motion>", self.on_canvas_pan_drag)
        self.canvas.bind("<B3-Motion>", self.on_canvas_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_canvas_pan_end)
        self.canvas.bind("<ButtonRelease-3>", self.on_canvas_pan_end)
        
        # Keyboard shortcuts for zoom
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())  # + without shift
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())
        self.root.bind("<Control-0>", lambda e: self.zoom_reset())
        self.root.bind("<Control-r>", lambda e: self.zoom_reset())  # Reset zoom
        
        # Right: Controls and tagging - Make scrollable with fixed width to prevent overflow
        controls_container = ttk.Frame(content_frame)
        controls_container.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5)
        
        # Create scrollable frame with fixed width to prevent elements from going off edge
        controls_canvas = tk.Canvas(controls_container, width=450, highlightthickness=0)
        controls_scrollbar = ttk.Scrollbar(controls_container, orient="vertical", command=controls_canvas.yview)
        controls_panel = ttk.Frame(controls_canvas, width=450)  # Set fixed width on panel
        
        # Update scroll region when panel size changes
        def update_scroll_region(event=None):
            controls_canvas.update_idletasks()
            bbox = controls_canvas.bbox("all")
            if bbox:
                controls_canvas.configure(scrollregion=bbox)
        
        controls_panel.bind("<Configure>", update_scroll_region)
        
        # Create window in canvas with fixed width
        window_id = controls_canvas.create_window((0, 0), window=controls_panel, anchor="nw", width=450)
        
        # Configure canvas to maintain fixed width for inner window
        def configure_canvas_width(event):
            canvas_width = min(event.width, 450)  # Cap at 450 to prevent overflow
            controls_canvas.itemconfig(window_id, width=canvas_width)
        
        controls_canvas.bind('<Configure>', configure_canvas_width)
        controls_canvas.configure(yscrollcommand=controls_scrollbar.set)
        
        controls_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        controls_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind mousewheel to canvas (only when hovering over controls)
        def on_mousewheel(event):
            try:
                # Check if canvas still exists and is valid
                if not hasattr(controls_canvas, 'winfo_exists'):
                    return
                try:
                    if not controls_canvas.winfo_exists():
                        return
                except (tk.TclError, AttributeError):
                    return
                
                # Only scroll if mouse is over the controls canvas
                try:
                    x, y = controls_canvas.winfo_pointerxy()
                    widget_x = controls_canvas.winfo_rootx()
                    widget_y = controls_canvas.winfo_rooty()
                    widget_width = controls_canvas.winfo_width()
                    widget_height = controls_canvas.winfo_height()
                    
                    if (widget_x <= x <= widget_x + widget_width and 
                        widget_y <= y <= widget_y + widget_height):
                        controls_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                except (tk.TclError, AttributeError):
                    # Widget was destroyed or invalid - ignore the event
                    pass
            except (tk.TclError, AttributeError):
                # Widget was destroyed or invalid - ignore the event
                pass
        
        # Bind to root window for mousewheel
        self.root.bind_all("<MouseWheel>", on_mousewheel)
        
        # Navigation controls have been moved to horizontal bar above video frame
        # Keep track ID search in controls panel for reference
        track_search_frame = ttk.LabelFrame(controls_panel, text="Track Search", padding="10")
        track_search_frame.pack(fill=tk.X, pady=5)
        
        # Go to Track ID search
        goto_track_frame = ttk.Frame(track_search_frame)
        goto_track_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(goto_track_frame, text="Go to Track ID:").pack(side=tk.LEFT, padx=5)
        self.goto_track_entry = ttk.Entry(goto_track_frame, width=10)
        self.goto_track_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(goto_track_frame, text="🔍 Find", command=self.goto_track_id, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(goto_track_frame, text="📋 List IDs", command=self.show_track_id_list, width=12).pack(side=tk.LEFT, padx=2)
        self.goto_track_entry.bind("<Return>", lambda e: self.goto_track_id())
        
        # Note: Zoom controls and frame slider have been moved to the horizontal navigation bar above the video frame
        # They are no longer in the right-side controls panel
        # Initialize frame_var if not already initialized (it's used throughout the code)
        if not hasattr(self, 'frame_var'):
            self.frame_var = tk.IntVar()
        
        # Event Marker System controls (if available)
        if EVENT_MARKER_AVAILABLE and self.event_marker_system:
            marker_frame = ttk.LabelFrame(controls_panel, text="Event Markers", padding="10")
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
            
            ttk.Button(marker_mgmt_frame, text="💾 Save", 
                      command=self.save_event_markers).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            ttk.Button(marker_mgmt_frame, text="📂 Load", 
                      command=self.load_event_markers).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            ttk.Button(marker_mgmt_frame, text="🗑️ Clear", 
                      command=self.clear_all_event_markers).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            
            # Marker statistics
            self.marker_stats_label = ttk.Label(marker_frame, text="Markers: 0", 
                                               font=("Arial", 8), foreground="gray")
            self.marker_stats_label.pack(anchor=tk.W, pady=2)
        
        # Detection list
        detections_frame = ttk.LabelFrame(controls_panel, text="Detections (Click to Select)", padding="10")
        detections_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Listbox with scrollbar
        listbox_frame = ttk.Frame(detections_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.detections_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, height=12,
                                             font=("Arial", 10), selectbackground="yellow", 
                                             selectforeground="black")
        self.detections_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.detections_listbox.bind("<<ListboxSelect>>", self.on_detection_select)
        self.detections_listbox.bind("<Double-Button-1>", self.on_listbox_double_click)  # Double-click for zoom
        scrollbar.config(command=self.detections_listbox.yview)
        
        # Quick tag dropdown in detections section
        quick_tag_frame = ttk.Frame(detections_frame)
        quick_tag_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(quick_tag_frame, text="Quick Tag:", font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.quick_tag_player_var = tk.StringVar()
        # Ensure player_name_list is fully loaded before creating quick tag combobox
        if not self.player_name_list or len(self.player_name_list) == 0:
            self.refresh_player_name_list()
        
        # Filter player list to only show active players
        active_player_list = [name for name in self.player_name_list if self.is_player_active(name)]
        self.quick_tag_player_combo = ttk.Combobox(quick_tag_frame, textvariable=self.quick_tag_player_var,
                                                   width=20, values=active_player_list, state="readonly")
        self.quick_tag_player_combo.pack(side=tk.LEFT, padx=2)
        self.quick_tag_player_combo.bind("<<ComboboxSelected>>", self.on_quick_tag_player_select)
        
        self.quick_tag_team_var = tk.StringVar()
        quick_tag_team_names = self.get_team_names_from_config()
        # Add empty option at the beginning to allow blank team selection
        quick_tag_team_names_with_blank = [""] + quick_tag_team_names
        # Allow typing custom team names (not readonly) - users can enter "Blue", "Gray", or any custom name, or leave blank
        self.quick_tag_team_combo = ttk.Combobox(quick_tag_frame, textvariable=self.quick_tag_team_var,
                                                 width=12, values=quick_tag_team_names_with_blank)
        self.quick_tag_team_combo.pack(side=tk.LEFT, padx=2)
        self.quick_tag_team_combo.bind("<<ComboboxSelected>>", self.on_quick_tag_team_select)
        
        ttk.Button(quick_tag_frame, text="Apply", command=self.apply_quick_tag, width=8).pack(side=tk.LEFT, padx=2)
        
        # Zoom button
        zoom_frame = ttk.Frame(detections_frame)
        zoom_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(zoom_frame, text="🔍 Zoom Selected Player", 
                  command=self.zoom_selected_player).pack(fill=tk.X)
        
        # Re-ID Controls
        reid_frame = ttk.LabelFrame(controls_panel, text="Re-ID Matching", padding="10")
        reid_frame.pack(fill=tk.X, pady=5)
        
        # Re-ID Threshold Controls
        threshold_frame = ttk.Frame(reid_frame)
        threshold_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(threshold_frame, text="Auto-Tag Threshold:", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        self.reid_auto_tag_var = tk.DoubleVar(value=0.8)
        self.reid_auto_tag_scale = ttk.Scale(threshold_frame, from_=0.5, to=1.0, 
                                             orient=tk.HORIZONTAL, variable=self.reid_auto_tag_var,
                                             length=150, command=self.on_reid_threshold_change)
        self.reid_auto_tag_scale.pack(side=tk.LEFT, padx=5)
        self.reid_auto_tag_label = ttk.Label(threshold_frame, text="0.80", width=5)
        self.reid_auto_tag_label.pack(side=tk.LEFT, padx=2)
        
        # Suggestion threshold
        suggestion_frame = ttk.Frame(reid_frame)
        suggestion_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(suggestion_frame, text="Suggestion Threshold:", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        self.reid_suggestion_var = tk.DoubleVar(value=0.6)
        self.reid_suggestion_scale = ttk.Scale(suggestion_frame, from_=0.3, to=0.9, 
                                              orient=tk.HORIZONTAL, variable=self.reid_suggestion_var,
                                              length=150, command=self.on_reid_threshold_change)
        self.reid_suggestion_scale.pack(side=tk.LEFT, padx=5)
        self.reid_suggestion_label = ttk.Label(suggestion_frame, text="0.60", width=5)
        self.reid_suggestion_label.pack(side=tk.LEFT, padx=2)
        
        # Re-ID Action Buttons
        reid_buttons_frame = ttk.Frame(reid_frame)
        reid_buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(reid_buttons_frame, text="🔄 Refresh Re-ID", 
                  command=self.refresh_reid_matching, width=18).pack(side=tk.LEFT, padx=2)
        self.reid_training_button = ttk.Button(reid_buttons_frame, text="🎓 Training Mode: OFF", 
                                               command=self.toggle_reid_training, width=18)
        self.reid_training_button.pack(side=tk.LEFT, padx=2)
        
        # Training instructions
        training_info = ttk.Label(reid_frame, 
                                 text="Training: Select 2 detections to teach they're the same player",
                                 font=("Arial", 8), foreground="gray", wraplength=400)
        training_info.pack(pady=2)
        
        # Roster Management
        roster_frame = ttk.LabelFrame(controls_panel, text="👥 Team Roster Management", padding="10")
        roster_frame.pack(fill=tk.X, pady=5)
        
        self.create_roster_management(roster_frame)
        
        # Player tagging
        tag_frame = ttk.LabelFrame(controls_panel, text="Tag Player", padding="10")
        tag_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(tag_frame, text="Selected ID:").pack(anchor=tk.W)
        self.selected_id_label = ttk.Label(tag_frame, text="None", foreground="blue", font=("Arial", 10, "bold"))
        self.selected_id_label.pack(anchor=tk.W, pady=2)
        
        # Player name with dropdown
        name_frame = ttk.Frame(tag_frame)
        name_frame.pack(fill=tk.X, pady=(5, 2))
        
        ttk.Label(name_frame, text="Player Name:").pack(anchor=tk.W)
        
        name_combo_frame = ttk.Frame(name_frame)
        name_combo_frame.pack(fill=tk.X, pady=2)
        
        self.player_name_var = tk.StringVar()
        # Ensure player_name_list is fully loaded before creating combobox
        # Refresh the list to make sure we have all players from gallery
        if not self.player_name_list or len(self.player_name_list) == 0:
            self.refresh_player_name_list()
        
        # Filter player list to only show active players
        active_player_list = [name for name in self.player_name_list if self.is_player_active(name)]
        self.player_name_combo = ttk.Combobox(name_combo_frame, textvariable=self.player_name_var,
                                             width=25, values=active_player_list, state="readonly")
        self.player_name_combo.pack(side=tk.LEFT, padx=2)
        self.player_name_combo.bind("<Return>", lambda e: self.tag_player())
        self.player_name_combo.bind("<<ComboboxSelected>>", self.on_player_name_select)  # Auto-populate team
        self.player_name_combo.bind("<FocusIn>", self.on_name_combo_focus)
        self.player_name_combo.bind("<FocusOut>", self.on_name_combo_unfocus)
        self.player_name_combo.bind("<KeyRelease>", self.on_name_combo_key_release)
        
        # Button to manage player names
        ttk.Button(name_combo_frame, text="Manage Names", 
                  command=self.manage_player_names, width=12).pack(side=tk.LEFT, padx=(5, 0))
        
        # Jersey Number field (NEW)
        jersey_frame = ttk.Frame(tag_frame)
        jersey_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(jersey_frame, text="Jersey #:").pack(side=tk.LEFT)
        self.jersey_number_var = tk.StringVar()
        self.jersey_number_entry = ttk.Entry(jersey_frame, textvariable=self.jersey_number_var, width=8)
        self.jersey_number_entry.pack(side=tk.LEFT, padx=5)
        self.jersey_number_entry.bind("<Return>", lambda e: self.tag_player())
        ttk.Label(jersey_frame, text="(Optional, e.g. 5, 12, 99)", foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=5)
        
        # Team assignment
        team_frame = ttk.Frame(tag_frame)
        team_frame.pack(fill=tk.X, pady=5)
        
        button_frame = ttk.Frame(tag_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="Tag Player", command=self.tag_player).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Reject", command=self.reject_detection).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Clear Tag", command=self.clear_tag).pack(side=tk.LEFT, padx=2)
        
        # Batch operations
        batch_frame = ttk.LabelFrame(controls_panel, text="Batch Operations", padding="10")
        batch_frame.pack(fill=tk.X, pady=5)
        
        smart_match_button_frame = ttk.Frame(batch_frame)
        smart_match_button_frame.pack(fill=tk.X, pady=2)
        ttk.Button(smart_match_button_frame, text="🎯 Auto-Match Roster", 
                  command=self.smart_roster_auto_match, width=18).pack(side=tk.LEFT, padx=(0,2))
        ttk.Button(smart_match_button_frame, text="📝 Review", 
                  command=self.smart_roster_match, width=6).pack(side=tk.LEFT)
        ttk.Button(batch_frame, text="Tag All Instances of ID", 
                  command=self.tag_all_instances, width=25).pack(fill=tk.X, pady=2)
        ttk.Button(batch_frame, text="Tag All Instances (All Players)", 
                  command=self.tag_all_instances_all_players, width=25).pack(fill=tk.X, pady=2)
        ttk.Button(batch_frame, text="Tag All Visible Players", 
                  command=self.tag_all_visible, width=25).pack(fill=tk.X, pady=2)
        ttk.Button(batch_frame, text="Copy Tags from Frame...", 
                  command=self.copy_tags_from_frame, width=25).pack(fill=tk.X, pady=2)
        
        ttk.Label(team_frame, text="Team:").pack(side=tk.LEFT)
        self.team_var = tk.StringVar(value="")
        # Get team names from config (supports custom names like "Blue", "Gray", etc.)
        team_names = self.get_team_names_from_config()
        # Allow typing custom team names (not readonly) - users can enter "Blue", "Gray", or any custom name
        self.team_combo = ttk.Combobox(team_frame, textvariable=self.team_var, width=15,
                                      values=team_names)
        self.team_combo.pack(side=tk.LEFT, padx=5)
        
        # Manual detection
        manual_frame = ttk.LabelFrame(controls_panel, text="Manual Detection", padding="10")
        manual_frame.pack(fill=tk.X, pady=5)
        
        self.manual_mode_button = ttk.Button(manual_frame, text="Enable Manual Detection", 
                                            command=self.toggle_manual_mode)
        self.manual_mode_button.pack(fill=tk.X, pady=5)
        ttk.Label(manual_frame, text="(Click and drag to draw bounding box)", 
                 foreground="gray", font=("Arial", 8)).pack(pady=2)
        
        # Ball detection
        ball_frame = ttk.LabelFrame(controls_panel, text="Ball Position", padding="10")
        ball_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(ball_frame, text="Show Ball Markers", 
                       variable=self.show_ball_detection,
                       command=self.update_display).pack(anchor=tk.W)
        
        # Ball position button (more prominent)
        self.ball_click_button = ttk.Button(ball_frame, text="⚽ Mark Ball Position", 
                                           command=self.enable_ball_click,
                                           width=25)
        self.ball_click_button.pack(fill=tk.X, pady=5)
        
        # Status label
        self.ball_status_label = ttk.Label(ball_frame, text="Click button, then click on canvas", 
                                           foreground="gray", font=("Arial", 8))
        self.ball_status_label.pack(pady=2)
        
        # Ball count for current frame
        self.ball_count_label = ttk.Label(ball_frame, text="Ball positions: 0", 
                                          foreground="blue", font=("Arial", 9))
        self.ball_count_label.pack(pady=2)
        
        # Remove ball button
        ttk.Button(ball_frame, text="Remove Ball from This Frame", 
                  command=self.remove_ball_from_frame, width=25).pack(fill=tk.X, pady=2)
        
        # Manage ball positions button
        ttk.Button(ball_frame, text="📋 Manage Ball Positions", 
                  command=self.manage_ball_positions, width=25).pack(fill=tk.X, pady=2)
        
        self.ball_click_mode = False
        
        # Referee tagging (separate from players)
        referee_frame = ttk.LabelFrame(controls_panel, text="Tag Referee", padding="10")
        referee_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(referee_frame, text="Referee Name:").pack(anchor=tk.W)
        self.referee_name_var = tk.StringVar()
        referee_name_combo = ttk.Combobox(referee_frame, textvariable=self.referee_name_var,
                                         width=25, values=["Referee 1", "Referee 2", "Linesman 1", "Linesman 2"])
        referee_name_combo.pack(fill=tk.X, pady=2)
        referee_name_combo.bind("<Return>", lambda e: self.tag_referee())
        
        ttk.Button(referee_frame, text="Tag as Referee", command=self.tag_referee, width=25).pack(fill=tk.X, pady=2)
        ttk.Button(referee_frame, text="Clear Referee Tag", command=self.clear_referee_tag, width=25).pack(fill=tk.X, pady=2)
        
        # Substitution events
        substitution_frame = ttk.LabelFrame(controls_panel, text="Substitution Events", padding="10")
        substitution_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(substitution_frame, text="Mark when players come on/off field", 
                 foreground="gray", font=("Arial", 8)).pack(anchor=tk.W, pady=2)
        
        sub_buttons_frame = ttk.Frame(substitution_frame)
        sub_buttons_frame.pack(fill=tk.X, pady=2)
        
        ttk.Button(sub_buttons_frame, text="Player ON", command=lambda: self.mark_substitution("on"), 
                  width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(sub_buttons_frame, text="Player OFF", command=lambda: self.mark_substitution("off"), 
                  width=12).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(substitution_frame, text="📋 View Substitutions", command=self.view_substitutions, 
                  width=25).pack(fill=tk.X, pady=2)
        
        # Roster management
        roster_frame = ttk.LabelFrame(controls_panel, text="Player Roster (7v7)", padding="10")
        roster_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(roster_frame, text="Manage team rosters and jersey numbers", 
                 foreground="gray", font=("Arial", 8)).pack(anchor=tk.W, pady=2)
        
        ttk.Button(roster_frame, text="📋 Manage Roster", command=self.manage_roster, 
                  width=25).pack(fill=tk.X, pady=2)
        
        ttk.Button(roster_frame, text="View Active Players", command=self.view_active_players, 
                  width=25).pack(fill=tk.X, pady=2)
        
        # Workflow guide
        workflow_frame = ttk.LabelFrame(controls_panel, text="Workflow Guide", padding="10")
        workflow_frame.pack(fill=tk.X, pady=5)
        
        workflow_text = """1. Tag Players: Click on players and assign names
2. Mark Ball: Click ball position in key frames
3. Export Seed: Save your initial mappings
4. Run Analysis: Start full video analysis (main GUI)
5. Consolidate IDs: After analysis, merge fragmented tracks"""
        
        workflow_label = ttk.Label(workflow_frame, text=workflow_text, 
                                   foreground="darkblue", font=("Arial", 8), justify=tk.LEFT)
        workflow_label.pack(anchor=tk.W, pady=2)
        
        # Summary and export
        summary_frame = ttk.LabelFrame(controls_panel, text="Summary & Export", padding="10")
        summary_frame.pack(fill=tk.X, pady=5)
        
        self.summary_label = ttk.Label(summary_frame, text="No mappings yet", 
                                       foreground="gray", font=("Arial", 9))
        self.summary_label.pack(anchor=tk.W)
        
        ttk.Button(summary_frame, text="Export Seed Config", 
                  command=self.export_seed_config).pack(fill=tk.X, pady=5)
        ttk.Button(summary_frame, text="Ready for Analysis", 
                  command=self.start_analysis).pack(fill=tk.X, pady=5)
        
        # Post-analysis section (for after full analysis is complete)
        post_analysis_frame = ttk.LabelFrame(controls_panel, text="After Analysis", padding="10")
        post_analysis_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(post_analysis_frame, 
                 text="Use Consolidate IDs tool after running full analysis to merge fragmented player tracks.",
                 foreground="gray", font=("Arial", 8), wraplength=380, justify=tk.LEFT).pack(anchor=tk.W, pady=2)
        
        ttk.Button(post_analysis_frame, text="Consolidate IDs (Post-Analysis)", 
                  command=self.open_consolidate_ids, width=25).pack(fill=tk.X, pady=5)
        
        # Keyboard shortcuts help
        shortcuts_frame = ttk.LabelFrame(controls_panel, text="Keyboard Shortcuts", padding="10")
        shortcuts_frame.pack(fill=tk.X, pady=5)
        
        shortcuts_text = """← → / ↑ ↓ / Space: Navigate frames
T: Tag player
R: Reject detection
C: Clear tag
N: Next untagged frame
P: Prev untagged frame
M: Toggle manual detection
B: Mark ball
Home/End: First/Last frame"""
        
        shortcuts_label = ttk.Label(shortcuts_frame, text=shortcuts_text, 
                                    foreground="gray", font=("Arial", 8), justify=tk.LEFT)
        shortcuts_label.pack(anchor=tk.W)
        
        # Bind keyboard shortcuts
        self.setup_keyboard_shortcuts()
        self.root.focus_set()
    
    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for faster workflow"""
        # Navigation - check focus before executing
        self.root.bind('<Left>', self.on_key_prev_frame)
        self.root.bind('<Right>', self.on_key_next_frame)
        self.root.bind('<Up>', self.on_key_prev_frame)
        self.root.bind('<Down>', self.on_key_next_frame)
        self.root.bind('<space>', self.on_key_next_frame)
        
        # Tagging actions (only when not typing in entry fields)
        self.root.bind('<KeyPress-t>', self.on_key_tag)
        self.root.bind('<KeyPress-T>', self.on_key_tag)
        self.root.bind('<KeyPress-r>', self.on_key_reject)
        self.root.bind('<KeyPress-R>', self.on_key_reject)
        self.root.bind('<KeyPress-n>', self.on_key_next_untagged)
        self.root.bind('<KeyPress-N>', self.on_key_next_untagged)
        self.root.bind('<KeyPress-c>', self.on_key_clear_tag)
        self.root.bind('<KeyPress-C>', self.on_key_clear_tag)
        
        # Frame jumping - check focus
        self.root.bind('<Home>', self.on_key_first_frame)
        self.root.bind('<End>', self.on_key_last_frame)
        self.root.bind('<KeyPress-f>', self.on_key_first_frame)
        self.root.bind('<KeyPress-F>', self.on_key_first_frame)
        self.root.bind('<KeyPress-l>', self.on_key_last_frame)
        self.root.bind('<KeyPress-L>', self.on_key_last_frame)
        
        # Previous untagged - check focus
        self.root.bind('<KeyPress-p>', self.on_key_prev_untagged)
        self.root.bind('<KeyPress-P>', self.on_key_prev_untagged)
        
        # Manual detection toggle - check focus
        self.root.bind('<KeyPress-m>', self.on_key_toggle_manual)
        self.root.bind('<KeyPress-M>', self.on_key_toggle_manual)
        
        # Ball marking - check focus
        self.root.bind('<KeyPress-b>', self.on_key_ball_click)
        self.root.bind('<KeyPress-B>', self.on_key_ball_click)
    
    def should_ignore_keyboard_shortcut(self, event):
        """Check if keyboard shortcut should be ignored (user is typing)"""
        # Check if focus is on an entry widget
        if isinstance(event.widget, (tk.Entry, ttk.Combobox)):
            return True
        # Check if name combobox has focus
        if hasattr(self, 'name_combo_focused') and self.name_combo_focused:
            return True
        # Check if the focused widget is a text entry
        try:
            widget = self.root.focus_get()
            if isinstance(widget, (tk.Entry, ttk.Combobox, tk.Text)):
                return True
        except:
            pass
        return False
    
    def on_key_prev_frame(self, event):
        """Handle arrow keys/space for previous frame"""
        if self.should_ignore_keyboard_shortcut(event):
            return
        self.prev_frame()
    
    def on_key_next_frame(self, event):
        """Handle arrow keys/space for next frame"""
        if self.should_ignore_keyboard_shortcut(event):
            return
        self.next_frame()
    
    def on_key_first_frame(self, event):
        """Handle Home/F key for first frame"""
        if self.should_ignore_keyboard_shortcut(event):
            return
        self.go_to_first()
    
    def on_key_last_frame(self, event):
        """Handle End/L key for last frame"""
        if self.should_ignore_keyboard_shortcut(event):
            return
        self.go_to_last()
    
    def on_key_next_untagged(self, event):
        """Handle N key for next untagged"""
        if self.should_ignore_keyboard_shortcut(event):
            return
        self.jump_to_next_untagged()
    
    def on_key_prev_untagged(self, event):
        """Handle P key for previous untagged"""
        if self.should_ignore_keyboard_shortcut(event):
            return
        self.jump_to_prev_untagged()
    
    def on_key_toggle_manual(self, event):
        """Handle M key for toggle manual mode"""
        if self.should_ignore_keyboard_shortcut(event):
            return
        self.toggle_manual_mode()
    
    def on_key_ball_click(self, event):
        """Handle B key for ball click mode"""
        if self.should_ignore_keyboard_shortcut(event):
            return
        self.enable_ball_click()
    
    def on_key_tag(self, event):
        """Handle T key for tagging"""
        # Don't trigger if typing in entry field or combobox
        if isinstance(event.widget, (tk.Entry, ttk.Combobox)):
            return
        if hasattr(self, 'name_combo_focused') and self.name_combo_focused:
            return
        self.tag_player()
    
    def on_key_reject(self, event):
        """Handle R key for rejecting"""
        if isinstance(event.widget, (tk.Entry, ttk.Combobox)):
            return
        if hasattr(self, 'name_combo_focused') and self.name_combo_focused:
            return
        self.reject_detection()
    
    def on_key_clear_tag(self, event):
        """Handle C key for clearing tag"""
        if isinstance(event.widget, (tk.Entry, ttk.Combobox)):
            return
        if hasattr(self, 'name_combo_focused') and self.name_combo_focused:
            return
        self.clear_tag()
    
    def jump_to_next_untagged(self, event=None):
        """Jump to next frame with untagged players"""
        if not self.detections_history:
            messagebox.showinfo("No Detections", "Please initialize detection first")
            return
        
        # First, check if current frame has all players tagged
        # If so, auto-tag all instances of all tagged players, then move to next
        if self.current_detections is not None and len(self.current_detections) > 0:
            all_tagged = True
            for track_id in self.current_detections.tracker_id:
                if track_id is None or track_id in self.rejected_ids:
                    continue
                track_id = self.merged_ids.get(track_id, track_id)
                pid_str = str(int(track_id))
                if pid_str not in self.approved_mappings:
                    all_tagged = False
                    break
            
            # If all players in current frame are tagged, tag all instances of all of them
            if all_tagged:
                self.tag_all_instances_all_players(silent=True)
        
        start_frame = self.current_frame_num + 1
        for frame_num in range(start_frame, self.total_frames):
            if frame_num in self.detections_history:
                detections = self.detections_history[frame_num]
                # Check if any detection is untagged
                for track_id in detections.tracker_id:
                    if track_id is None or track_id in self.rejected_ids:
                        continue
                    track_id = self.merged_ids.get(track_id, track_id)
                    pid_str = str(int(track_id))
                    if pid_str not in self.approved_mappings:
                        # Found untagged frame
                        self.current_frame_num = frame_num
                        self.load_frame()
                        return
        
        # If no untagged frames found, show message
        messagebox.showinfo("No Untagged Frames", "All frames have been tagged!")
    
    def jump_to_prev_untagged(self, event=None):
        """Jump to previous frame with untagged players"""
        if not self.detections_history:
            messagebox.showinfo("No Detections", "Please initialize detection first")
            return
        
        start_frame = self.current_frame_num - 1
        for frame_num in range(start_frame, -1, -1):
            if frame_num in self.detections_history:
                detections = self.detections_history[frame_num]
                # Check if any detection is untagged
                for track_id in detections.tracker_id:
                    if track_id is None or track_id in self.rejected_ids:
                        continue
                    track_id = self.merged_ids.get(track_id, track_id)
                    pid_str = str(int(track_id))
                    if pid_str not in self.approved_mappings:
                        # Found untagged frame
                        self.current_frame_num = frame_num
                        self.load_frame()
                        return
        
        # If no untagged frames found, show message
        messagebox.showinfo("No Untagged Frames", "All frames before this have been tagged!")
    
    def goto_track_id(self):
        """Go to frame containing specified track ID"""
        try:
            # Get track ID from entry
            track_id_str = self.goto_track_entry.get().strip()
            if not track_id_str:
                messagebox.showwarning("No Track ID", "Please enter a track ID to search for")
                return
            
            try:
                target_track_id = int(track_id_str)
            except ValueError:
                messagebox.showerror("Invalid Input", f"'{track_id_str}' is not a valid track ID number")
                return
            
            if not self.detections_history:
                messagebox.showinfo("No Detections", "Please initialize detection first")
                return
            
            # Search from current frame forward, then wrap around
            search_order = list(range(self.current_frame_num + 1, self.total_frames)) + list(range(0, self.current_frame_num + 1))
            
            found_frame = None
            for frame_num in search_order:
                if frame_num in self.detections_history:
                    detections = self.detections_history[frame_num]
                    if detections.tracker_id is not None:
                        for track_id in detections.tracker_id:
                            if track_id is not None:
                                # Check both original and merged IDs
                                actual_id = self.merged_ids.get(track_id, track_id)
                                if int(track_id) == target_track_id or int(actual_id) == target_track_id:
                                    found_frame = frame_num
                                    break
                if found_frame is not None:
                    break
            
            if found_frame is not None:
                self.current_frame_num = found_frame
                self.load_frame()
                
                # Auto-select the track in the listbox
                if self.current_detections is not None:
                    for i, track_id in enumerate(self.current_detections.tracker_id):
                        if track_id is not None:
                            actual_id = self.merged_ids.get(track_id, track_id)
                            if int(track_id) == target_track_id or int(actual_id) == target_track_id:
                                # Select in listbox
                                self.detections_listbox.selection_clear(0, tk.END)
                                if i in self.listbox_to_detection_map.values():
                                    # Find listbox index
                                    for listbox_idx, det_idx in self.listbox_to_detection_map.items():
                                        if det_idx == i:
                                            self.detections_listbox.selection_set(listbox_idx)
                                            self.detections_listbox.see(listbox_idx)
                                            # Trigger selection event
                                            self.selected_detection = i
                                            self.update_display()
                                            break
                                break
                
                self.status_label.config(text=f"✓ Found Track #{target_track_id} at frame {found_frame}")
            else:
                messagebox.showinfo("Track Not Found", 
                                  f"Track ID #{target_track_id} not found in any frame.\n"
                                  f"It may have been rejected or not exist in this video.")
                self.status_label.config(text=f"Track #{target_track_id} not found")
        
        except Exception as e:
            messagebox.showerror("Error", f"Error searching for track: {e}")
            import traceback
            traceback.print_exc()
    
    def show_track_id_list(self):
        """Show a dialog listing all track IDs with their player names"""
        if not self.detections_history:
            messagebox.showinfo("No Detections", "Please initialize detection first")
            return
        
        # Collect all unique track IDs and their player names
        track_info = {}  # track_id -> (player_name, team, first_frame, last_frame, frame_count)
        
        for frame_num, detections in self.detections_history.items():
            if detections is None or detections.tracker_id is None:
                continue
            
            for track_id in detections.tracker_id:
                if track_id is None or track_id in self.rejected_ids:
                    continue
                
                # Get merged ID
                actual_id = self.merged_ids.get(track_id, track_id)
                track_id_int = int(actual_id)
                
                # Get player name from mappings
                pid_str = str(track_id_int)
                player_name = "Untagged"
                team = ""
                if pid_str in self.approved_mappings:
                    mapping = self.approved_mappings[pid_str]
                    if isinstance(mapping, tuple):
                        player_name = mapping[0] if len(mapping) > 0 else "Untagged"
                        team = mapping[1] if len(mapping) > 1 else ""
                    else:
                        player_name = str(mapping) if mapping else "Untagged"
                
                # Update track info
                if track_id_int not in track_info:
                    track_info[track_id_int] = {
                        'player_name': player_name,
                        'team': team,
                        'first_frame': frame_num,
                        'last_frame': frame_num,
                        'frame_count': 1
                    }
                else:
                    info = track_info[track_id_int]
                    info['first_frame'] = min(info['first_frame'], frame_num)
                    info['last_frame'] = max(info['last_frame'], frame_num)
                    info['frame_count'] += 1
        
        if not track_info:
            messagebox.showinfo("No Tracks", "No track IDs found. Please initialize detection first.")
            return
        
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Track ID List")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.lift()
        dialog.attributes('-topmost', True)
        dialog.after(200, lambda: dialog.attributes('-topmost', False))
        
        # Instructions
        ttk.Label(dialog, text="Double-click a track ID to go to it", 
                 font=("Arial", 9, "bold")).pack(pady=5)
        
        # Create treeview with scrollbar
        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create treeview
        columns = ("Track ID", "Player Name", "Team", "First Frame", "Last Frame", "Frames")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", yscrollcommand=scrollbar.set, height=15)
        scrollbar.config(command=tree.yview)
        
        # Configure columns
        tree.heading("Track ID", text="Track ID")
        tree.heading("Player Name", text="Player Name")
        tree.heading("Team", text="Team")
        tree.heading("First Frame", text="First Frame")
        tree.heading("Last Frame", text="Last Frame")
        tree.heading("Frames", text="Frames")
        
        tree.column("Track ID", width=80, anchor=tk.CENTER)
        tree.column("Player Name", width=150, anchor=tk.W)
        tree.column("Team", width=80, anchor=tk.CENTER)
        tree.column("First Frame", width=90, anchor=tk.CENTER)
        tree.column("Last Frame", width=90, anchor=tk.CENTER)
        tree.column("Frames", width=80, anchor=tk.CENTER)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Populate treeview
        for track_id in sorted(track_info.keys()):
            info = track_info[track_id]
            tree.insert("", tk.END, values=(
                track_id,
                info['player_name'],
                info['team'] if info['team'] else "-",
                info['first_frame'],
                info['last_frame'],
                info['frame_count']
            ))
        
        # Double-click to go to track
        def on_double_click(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                track_id = item['values'][0]
                self.goto_track_entry.delete(0, tk.END)
                self.goto_track_entry.insert(0, str(track_id))
                self.goto_track_id()
                dialog.destroy()
        
        tree.bind("<Double-1>", on_double_click)
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=5)
        
        # Summary
        tagged_count = sum(1 for info in track_info.values() if info['player_name'] != "Untagged")
        ttk.Label(dialog, text=f"Total: {len(track_info)} tracks ({tagged_count} tagged, {len(track_info) - tagged_count} untagged)", 
                 font=("Arial", 8), foreground="gray").pack(pady=2)
    
    def goto_frame(self):
        """Go to a specific frame number"""
        try:
            if not self.video_path or self.total_frames == 0:
                messagebox.showwarning("No Video", "Please load a video first")
                return
            
            # Use goto_frame_var from navigation bar
            frame_str = self.goto_frame_var.get().strip() if hasattr(self, 'goto_frame_var') else ""
            if not frame_str:
                messagebox.showwarning("No Frame Number", "Please enter a frame number")
                return
            
            try:
                target_frame = int(frame_str)
            except ValueError:
                messagebox.showerror("Invalid Input", f"'{frame_str}' is not a valid frame number")
                return
            
            # Validate frame number
            if target_frame < 0:
                messagebox.showwarning("Invalid Frame", f"Frame number must be 0 or greater")
                return
            
            if target_frame >= self.total_frames:
                messagebox.showwarning("Invalid Frame", 
                                     f"Frame {target_frame} is out of range.\n"
                                     f"Video has {self.total_frames} frames (0-{self.total_frames - 1})")
                return
            
            # Go to frame
            self.current_frame_num = target_frame
            self.frame_var.set(target_frame)
            self.load_frame()
            self.status_label.config(text=f"✓ Jumped to frame {target_frame}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error going to frame: {e}")
            import traceback
            traceback.print_exc()
    
    def toggle_autosave(self):
        """Toggle auto-save on/off"""
        self.auto_save_enabled = self.auto_save_enabled_var.get()
        if self.auto_save_enabled:
            # Restart auto-save
            if self.auto_save_job:
                self.root.after_cancel(self.auto_save_job)
            self.start_auto_save()
            self.autosave_status_label.config(text="(Every 30s)", foreground="green")
        else:
            # Stop auto-save
            if self.auto_save_job:
                self.root.after_cancel(self.auto_save_job)
                self.auto_save_job = None
            self.autosave_status_label.config(text="(Disabled)", foreground="red")
    
    def start_auto_save(self):
        """Start auto-save timer"""
        if self.auto_save_enabled:
            self.auto_save()
            # Schedule next auto-save
            self.auto_save_job = self.root.after(self.auto_save_interval, self.start_auto_save)
    
    def auto_save(self):
        """Auto-save player names and create backup"""
        try:
            # Save player names
            self.save_player_names()
            
            # Also save seed config backup
            backup_dir = "setup_wizard_backups"
            if not os.path.exists(backup_dir):
                # Create backup directory if it doesn't exist, with error handling
                try:
                    os.makedirs(backup_dir, exist_ok=True)
                except OSError as e:
                    print(f"⚠ Could not create backup directory {backup_dir}: {e}")
                    # Fall back to current directory if backup directory creation fails
                    backup_dir = "."
            
            backup_file = os.path.join(backup_dir, f"seed_config_backup_{int(self.root.winfo_id())}.json")
            
            # Convert NumPy types to Python types for JSON serialization
            def convert_to_python_types(obj):
                """Recursively convert NumPy types to Python types"""
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {k: convert_to_python_types(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_to_python_types(item) for item in obj]
                elif isinstance(obj, tuple):
                    return tuple(convert_to_python_types(item) for item in obj)
                elif isinstance(obj, set):
                    return list(convert_to_python_types(item) for item in obj)
                return obj
            
            # Convert anchor_frames: ensure frame numbers are strings (JSON requirement)
            anchor_frames_dict = {}
            total_anchor_count = 0
            for frame_num, anchors in self.anchor_frames.items():
                frame_str = str(int(frame_num))  # Ensure string key
                anchor_frames_dict[frame_str] = convert_to_python_types(anchors)
                total_anchor_count += len(anchors)
            
            # Log anchor frame save status (only warn once, not on every auto-save)
            if total_anchor_count > 0:
                print(f"💾 Saving {total_anchor_count} anchor frame tag(s) from {len(anchor_frames_dict)} frames")
            # Don't warn if anchor frames are empty - this is normal if none have been created yet
            # Only log if we're explicitly saving and expected anchor frames but found none
            
            config = {
                    "player_mappings": convert_to_python_types(self.approved_mappings),
                    "referee_mappings": convert_to_python_types(self.referee_mappings),
                    "rejected_ids": convert_to_python_types(list(self.rejected_ids)),
                    "merged_ids": convert_to_python_types(self.merged_ids),
                    "ball_positions": convert_to_python_types(self.ball_positions),
                    "substitution_events": convert_to_python_types(self.substitution_events),
                    "player_roster": convert_to_python_types(self.player_roster),
                    "anchor_frames": anchor_frames_dict,  # Use converted dict with string keys
                    "video_path": self.video_path,
                    "current_frame": int(self.current_frame_num)
                }
            
            # Save to backup file
            with open(backup_file, 'w') as f:
                json.dump(config, f, indent=4)
            
            # ALSO save to both locations (same as start_analysis) so analyzer can find it
            if self.video_path:
                try:
                    # 1. Save to project root (for backward compatibility)
                    seed_file_root = "seed_config.json"
                    with open(seed_file_root, 'w') as f:
                        json.dump(config, f, indent=4)
                    
                    # 2. ALSO save to video directory as PlayerTagsSeed-{video_basename}.json (for analyzer)
                    video_dir = os.path.dirname(os.path.abspath(self.video_path))
                    video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
                    seed_file_video = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
                    with open(seed_file_video, 'w') as f:
                        json.dump(config, f, indent=4)
                    
                    # Log what was saved
                    if total_anchor_count > 0:
                        print(f"✓ Saved anchor frames to: {os.path.basename(seed_file_video)} ({total_anchor_count} tags in {len(anchor_frames_dict)} frames)")
                except Exception as e:
                    print(f"⚠ Auto-save: Could not save to video directory: {e}")
            
            # Update status (subtle)
            if hasattr(self, 'status_label'):
                current_text = self.status_label.cget("text")
                if "✓ Auto-saved" not in current_text:
                    self.status_label.config(text=f"{current_text} | ✓ Auto-saved")
                    # Clear after 3 seconds
                    self.root.after(3000, lambda: self.status_label.config(
                        text=current_text.replace(" | ✓ Auto-saved", "")))
            
            # Update autosave status label
            if hasattr(self, 'autosave_status_label') and self.auto_save_enabled:
                import time
                current_time = time.strftime("%H:%M:%S")
                self.autosave_status_label.config(text=f"(Saved {current_time})", foreground="green")
                # Reset to interval text after 5 seconds
                self.root.after(5000, lambda: self.autosave_status_label.config(
                    text="(Every 30s)", foreground="gray") if self.auto_save_enabled else None)
        except Exception as e:
            print(f"Auto-save warning: {e}")
    
    def load_video(self):
        """Load video file"""
        filename = self._show_file_dialog(
            filedialog.askopenfilename,
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v"), ("All files", "*.*")]
        )
        if not filename:
            return
        
        self.video_path = filename
        self.cap = cv2.VideoCapture(filename)
        
        if not self.cap.isOpened():
            messagebox.showerror("Error", f"Could not open video: {filename}")
            return
        
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.total_frames = int(frame_count) if frame_count and not np.isnan(frame_count) else 0
        width_val = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height_val = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.width = int(width_val) if width_val and not np.isnan(width_val) else 0
        self.height = int(height_val) if height_val and not np.isnan(height_val) else 0
        
        if self.total_frames <= 0:
            messagebox.showerror("Error", "Could not determine video frame count. The video file may be corrupted.")
            self.cap.release()
            self.cap = None
            return
        
        # Frame slider was moved to nav bar, but we still need to update frame_var
        if hasattr(self, 'frame_var'):
            self.frame_var.set(0)
        self.current_frame_num = 0
        
        video_name = os.path.basename(filename)
        self.status_label.config(text=f"Video: {video_name} ({self.total_frames} frames)")
        # Update video file label
        if hasattr(self, 'video_file_label'):
            self.video_file_label.config(text=f"Video: {video_name}")
        # Also update window title to show video name
        self.root.title(f"Interactive Setup Wizard - {video_name}")
        self.init_button.config(state=tk.NORMAL)
        
        # Auto-load ball positions and player mappings if they exist for this video
        self.auto_load_seed_data()
        
        # Load first frame immediately and also after a delay to ensure canvas is fully rendered
        self.root.after(100, self.load_frame)
        self.root.after(300, self.load_frame)  # Backup in case first one doesn't work
    
    def initialize_detection(self):
        """Initialize YOLO model and tracker"""
        # Check if video is loaded
        if self.cap is None or not self.cap.isOpened():
            messagebox.showerror("Error", "Please load a video first before initializing detection.")
            return
        
        if self.total_frames <= 0:
            messagebox.showerror("Error", "Video has no frames. Please load a valid video file.")
            return
        
        if not YOLO_AVAILABLE:
            messagebox.showerror("Error", "YOLO not available. Please install ultralytics.")
            return
        
        # Disable button during initialization
        self.init_button.config(state=tk.DISABLED)
        self.status_label.config(text="Loading seed data and player gallery...")
        self.root.update()
        
        try:
            # CRITICAL: Load seed data and player gallery BEFORE initializing YOLO
            # This ensures we have player mappings and Re-ID information available during initialization
            self.auto_load_seed_data()
            
            # Load anchor frames and populate approved_mappings BEFORE Re-ID matching
            if hasattr(self, 'anchor_frames') and self.anchor_frames:
                print(f"✓ Loading {len(self.anchor_frames)} anchor frames to pre-populate player mappings")
                for frame_num, anchors in self.anchor_frames.items():
                    # Handle both string and integer frame numbers
                    frame_key = frame_num if isinstance(frame_num, int) else int(frame_num)
                    for anchor in anchors:
                        track_id = anchor.get("track_id")
                        player_name = anchor.get("player_name")
                        team = anchor.get("team", "")
                        jersey_number = anchor.get("jersey_number", "")
                        
                        if track_id is not None and player_name:
                            tid_str = str(int(track_id))
                            # Pre-populate approved_mappings with anchor frame data
                            if tid_str not in self.approved_mappings:
                                self.approved_mappings[tid_str] = (player_name, team, jersey_number)
                                print(f"  → Anchor frame {frame_key}: Track #{track_id} → '{player_name}'")
            
            # Ensure player gallery is loaded
            if self.player_gallery is None:
                try:
                    from player_gallery import PlayerGallery
                    self.player_gallery = PlayerGallery()
                    self.player_gallery.load_gallery()
                    print(f"✓ Loaded player gallery with {len(self.player_gallery.players)} players")
                except Exception as e:
                    print(f"⚠ Could not load player gallery: {e}")
                    self.player_gallery = None
            
            self.status_label.config(text="Initializing YOLO model...")
            self.root.update()
            # Try YOLOv11 first, fallback to YOLOv8
            try:
                self.model = YOLO('yolo11n.pt')
                print("✓ YOLOv11 loaded")
            except:
                self.model = YOLO('yolov8n.pt')
                print("✓ YOLOv8 loaded")
            
            # Initialize tracker - prefer OC-SORT for better occlusion handling
            if OCSORT_AVAILABLE:
                # OC-SORT is better for occlusions and maintains track identity better
                self.tracker = OCSortTracker(
                    track_activation_threshold=0.20,
                    minimum_matching_threshold=0.8,
                    lost_track_buffer=50,
                    min_track_length=3,  # Minimum frames before track activates
                    max_age=150,  # Max frames to keep lost tracks
                    iou_threshold=0.8
                )
                print("✓ Using OC-SORT tracker (better occlusion handling)")
            else:
                # Fallback to ByteTrack if OC-SORT not available
                self.tracker = sv.ByteTrack(
                    track_activation_threshold=0.20,
                    minimum_matching_threshold=0.8,
                    lost_track_buffer=50
                )
                print("✓ Using ByteTrack tracker (OC-SORT not available)")
            
            # Initialize Re-ID tracker for better identity maintenance (works with OC-SORT)
            try:
                from reid_tracker import ReIDTracker
                self.reid_tracker = ReIDTracker()
                print("✓ Re-ID tracker initialized (works with OC-SORT for better identity)")
                print("  → OC-SORT handles occlusions, Re-ID maintains appearance-based identity")
                
                # If we have seed mappings, use them to initialize Re-ID with known player-track associations
                if self.approved_mappings and self.player_gallery:
                    print(f"  → Using {len(self.approved_mappings)} seed mappings to initialize Re-ID")
            except ImportError:
                print("⚠ Re-ID tracker not available - using position-based matching only")
                self.reid_tracker = None
            except Exception as e:
                print(f"⚠ Could not initialize Re-ID tracker: {e} - using position-based matching only")
                self.reid_tracker = None
            
            # Initialize Jersey Number OCR for automatic jersey detection
            try:
                from jersey_number_ocr import JerseyNumberOCR
                self.jersey_ocr = JerseyNumberOCR(ocr_backend="auto", confidence_threshold=0.5, preprocess=True)
                print("✓ Jersey Number OCR initialized - will auto-detect jersey numbers during tagging")
            except ImportError:
                print("⚠ Jersey OCR not available - install with: pip install paddlepaddle paddleocr OR pip install pytesseract")
                self.jersey_ocr = None
            except Exception as e:
                print(f"⚠ Could not initialize Jersey OCR: {e}")
                self.jersey_ocr = None
            
            # Initialize Hard Negative Miner for better discrimination
            try:
                from hard_negative_mining import HardNegativeMiner
                self.hard_negative_miner = HardNegativeMiner()
                print("✓ Hard Negative Mining initialized - improves player discrimination")
            except ImportError:
                print("⚠ Hard Negative Mining not available")
                self.hard_negative_miner = None
            except Exception as e:
                print(f"⚠ Could not initialize Hard Negative Miner: {e}")
                self.hard_negative_miner = None
            
            # Initialize Gait Analyzer for movement signature matching
            try:
                from gait_analyzer import GaitAnalyzer
                self.gait_analyzer = GaitAnalyzer(history_length=30, min_samples_for_gait=10)
                print("✓ Gait Analyzer initialized - will analyze movement patterns")
            except ImportError:
                print("⚠ Gait Analyzer not available")
                self.gait_analyzer = None
            except Exception as e:
                print(f"⚠ Could not initialize Gait Analyzer: {e}")
                self.gait_analyzer = None
            
            self.status_label.config(text="Detection initialized. Processing frames...")
            self.progress_label.config(text="Processing...")
            self.root.update()
            
            # Process first 30 frames (or first 10% of video, whichever is smaller)
            frames_to_process = min(30, max(10, int(self.total_frames * 0.1)))
            self.process_initial_frames(frames_to_process)
            
            # After processing initial frames, use Re-ID to match detections to gallery and pre-populate tags
            if self.reid_tracker and self.player_gallery and len(self.player_gallery.players) > 0:
                self.status_label.config(text="Matching detections to player gallery using Re-ID...")
                self.root.update()
                self.apply_reid_matching_to_initial_frames(frames_to_process)
            
            status_text = f"✓ Processed {int(frames_to_process)} frames. Ready for tagging."
            self.status_label.config(text=str(status_text))
            self.progress_label.config(text="")  # Empty string, not None
            self.load_frame()
            
            # Re-enable button (though it's not needed after initialization)
            self.init_button.config(state=tk.DISABLED)  # Keep disabled after successful init
            
        except Exception as e:
            error_msg = f"Failed to initialize detection: {str(e)}"
            messagebox.showerror("Error", error_msg)
            self.status_label.config(text=f"Error: {error_msg}")
            self.progress_label.config(text="")
            # Re-enable button so user can try again
            self.init_button.config(state=tk.NORMAL)
            import traceback
            traceback.print_exc()
    
    def process_initial_frames(self, num_frames):
        """Process initial frames to get detections"""
        if self.cap is None or self.model is None:
            return
        
        for i in range(min(num_frames, self.total_frames)):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = self.cap.read()
            if not ret:
                break
            
            # Run YOLO detection
            results = self.model(frame, classes=[0], verbose=False)  # Class 0 = person
            detections = sv.Detections.from_ultralytics(results[0])
            
            # Update tracker (OC-SORT uses update(), ByteTrack uses update_with_detections())
            if hasattr(self.tracker, 'update_with_detections'):
                detections = self.tracker.update_with_detections(detections)
            else:
                detections = self.tracker.update(detections)
            
            # Extract Re-ID features for this frame if Re-ID tracker is available
            if self.reid_tracker is not None and len(detections) > 0:
                self.extract_reid_features_for_frame(frame, detections, i)
            
            # Store detections
            self.detections_history[i] = detections
            
            # Update progress
            if i % 5 == 0:
                progress_text = f"Processing frame {i}/{num_frames}..."
                self.progress_label.config(text=str(progress_text))
                self.root.update()
        
        # Reset to first frame
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    def apply_reid_matching_to_initial_frames(self, num_frames):
        """Apply Re-ID matching to initial frames to pre-populate tags from seed data and gallery"""
        if self.reid_tracker is None or self.player_gallery is None:
            return
        
        matched_count = 0
        for frame_num in range(min(num_frames, self.total_frames)):
            if frame_num not in self.detections_history:
                continue
            
            detections = self.detections_history[frame_num]
            if detections is None or len(detections) == 0:
                continue
            
            # Load frame for Re-ID matching
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = self.cap.read()
            if not ret:
                continue
            
            # Temporarily set current_frame_num and current_detections for matching
            old_frame_num = self.current_frame_num
            old_detections = self.current_detections
            self.current_frame_num = frame_num
            self.current_detections = detections
            
            # First, check if this frame has anchor frames and use them
            frame_key_str = str(frame_num)
            frame_key_int = frame_num
            if frame_key_str in self.anchor_frames or frame_key_int in self.anchor_frames:
                anchors = self.anchor_frames.get(frame_key_str) or self.anchor_frames.get(frame_key_int, [])
                for anchor in anchors:
                    track_id = anchor.get("track_id")
                    player_name = anchor.get("player_name")
                    team = anchor.get("team", "")
                    jersey_number = anchor.get("jersey_number", "")
                    
                    if track_id is not None and player_name:
                        tid_str = str(int(track_id))
                        # Find the detection with this track_id
                        for i, tid in enumerate(detections.tracker_id):
                            if tid is not None and int(tid) == int(track_id):
                                # Use anchor frame data to populate mapping
                                self.approved_mappings[tid_str] = (player_name, team, jersey_number)
                                print(f"✓ Using anchor frame {frame_num}: Track #{track_id} → '{player_name}'")
                                
                                # Store position for tracking
                                if i < len(detections.xyxy):
                                    bbox = detections.xyxy[i]
                                    center_x = (bbox[0] + bbox[2]) / 2.0
                                    center_y = (bbox[1] + bbox[3]) / 2.0
                                    if player_name not in self.player_positions:
                                        self.player_positions[player_name] = []
                                    self.player_positions[player_name].append((frame_num, center_x, center_y, int(track_id)))
                                    if len(self.player_positions[player_name]) > 10:
                                        self.player_positions[player_name] = self.player_positions[player_name][-10:]
                                break
            
            # Match detections to gallery (this will auto-tag high-confidence matches)
            # Note: match_detections_to_gallery will skip already-mapped detections
            self.match_detections_to_gallery(frame)
            
            # Also use seed mappings to pre-populate tags
            for track_id in detections.tracker_id:
                if track_id is None or track_id in self.rejected_ids:
                    continue
                
                tid_str = str(int(track_id))
                # If this track ID is in seed mappings, update position tracking
                if tid_str in self.approved_mappings:
                    # Get player name from mapping
                    mapping = self.approved_mappings[tid_str]
                    if isinstance(mapping, tuple):
                        player_name = mapping[0]
                    else:
                        player_name = mapping
                    
                    if player_name:
                        # Find detection index for this track_id
                        for i, tid in enumerate(detections.tracker_id):
                            if tid is not None and int(tid) == int(track_id):
                                if i < len(detections.xyxy):
                                    bbox = detections.xyxy[i]
                                    center_x = (bbox[0] + bbox[2]) / 2.0
                                    center_y = (bbox[1] + bbox[3]) / 2.0
                                    if player_name not in self.player_positions:
                                        self.player_positions[player_name] = []
                                    self.player_positions[player_name].append((frame_num, center_x, center_y, int(track_id)))
                                    if len(self.player_positions[player_name]) > 10:
                                        self.player_positions[player_name] = self.player_positions[player_name][-10:]
                                    matched_count += 1
                                break
            
            # Restore old values
            self.current_frame_num = old_frame_num
            self.current_detections = old_detections
        
        if matched_count > 0:
            print(f"✓ Pre-populated {matched_count} tags from seed data and Re-ID matching")
        
        # Reset to first frame
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    def load_frame(self):
        """Load and display current frame"""
        if self.cap is None:
            return
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_num)
        ret, frame = self.cap.read()
        
        if not ret:
            return
        
        self.current_frame = frame.copy()
        
        # Get detections for this frame
        if self.current_frame_num in self.detections_history:
            self.current_detections = self.detections_history[self.current_frame_num]
        else:
            # Run detection on demand if not in history
            if self.model is not None:
                results = self.model(frame, classes=[0], verbose=False)
                detections = sv.Detections.from_ultralytics(results[0])
                if self.tracker:
                    # Update tracker (OC-SORT uses update(), ByteTrack uses update_with_detections())
                    if hasattr(self.tracker, 'update_with_detections'):
                        detections = self.tracker.update_with_detections(detections)
                    else:
                        detections = self.tracker.update(detections)
                self.current_detections = detections
                self.detections_history[self.current_frame_num] = detections
            else:
                self.current_detections = None
        
        # Try to match manual detections with YOLO detections in this frame
        self.match_manual_detections()
        
        # RE-ID MATCHING: Use Re-ID and player gallery to maintain player identity when track IDs change
        if self.current_detections is not None and len(self.current_detections) > 0:
            # Extract Re-ID features for all detections in this frame
            self.extract_reid_features_for_frame(frame)
            
            # Match detections to gallery players using Re-ID
            self.match_detections_to_gallery(frame)
            
            # Use Re-ID and position to maintain player identity when track IDs change
            self.match_players_with_reid(frame)
        
        # Validate selected_detection is still valid for this frame
        if self.selected_detection is not None and self.current_detections is not None:
            if len(self.current_detections.tracker_id) == 0 or self.selected_detection >= len(self.current_detections.tracker_id):
                # Invalid selection for this frame, clear it
                self.selected_detection = None
                if hasattr(self, 'player_name_var'):
                    self.player_name_var.set("")
                    if hasattr(self, 'team_var'):
                        self.team_var.set("")
        
        # Update manual detection positions based on tracking
        self.update_manual_detection_tracking()
        
        self.update_display()
        self.update_detections_list()
        self.update_summary()
    
    def update_display(self):
        """Render frame with detections"""
        if self.current_frame is None:
            return
        
        display_frame = self.current_frame.copy()
        
        # Draw detections
        if self.current_detections is not None and len(self.current_detections) > 0:
            for i, (xyxy, track_id, conf) in enumerate(zip(
                self.current_detections.xyxy,
                self.current_detections.tracker_id,
                self.current_detections.confidence
            )):
                if track_id is None or track_id in self.rejected_ids:
                    continue
                
                track_id = self.merged_ids.get(track_id, track_id)
                pid_str = str(int(track_id))
                
                x1, y1, x2, y2 = map(int, xyxy)
                
                # Check if this is a referee
                if pid_str in self.referee_mappings:
                    # Draw referee with different color (orange/red)
                    color = (0, 165, 255)  # Orange in BGR
                    label = f"Ref: {self.referee_mappings[pid_str]}"
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 3)
                    cv2.putText(display_frame, label, (x1, y1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    continue
                
                # Regular player detection
                color = self.get_detection_color(track_id)
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                
                # Add label if mapped
                if pid_str in self.approved_mappings:
                    mapping = self.approved_mappings[pid_str]
                    if isinstance(mapping, tuple):
                        player_name = mapping[0]
                        team = mapping[1] if len(mapping) > 1 else ""
                    else:
                        player_name = mapping
                        team = ""
                    
                    label = f"{player_name} ({team})" if team else player_name
                    label_x = x1
                    label_y = y1 - 10 if y1 > 20 else y1 + 20
                    cv2.putText(display_frame, label, (label_x, label_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                else:
                    # Unmapped player - show ID
                    label = f"#{track_id}"
                    label_x = x1
                    label_y = y1 - 10 if y1 > 20 else y1 + 20
                    cv2.putText(display_frame, label, (label_x, label_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                
                # Draw circle at center
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                cv2.circle(display_frame, (cx, cy), 5, color, -1)
                
                # Highlight selected detection
                if self.selected_detection is not None and self.selected_detection == i:
                    cv2.rectangle(display_frame, (x1-2, y1-2), (x2+2, y2+2), (255, 255, 0), 3)
        
        # Draw ball positions if available
        if self.show_ball_detection.get():
            for frame_num, bx, by in self.ball_positions:
                if frame_num == self.current_frame_num:
                    # Draw larger, more visible ball marker
                    cv2.circle(display_frame, (int(bx), int(by)), 20, (0, 255, 0), 4)
                    cv2.circle(display_frame, (int(bx), int(by)), 8, (0, 255, 255), -1)  # Yellow center
                    # Draw label with background
                    label = "BALL"
                    (text_width, text_height), baseline = cv2.getTextSize(
                        label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
                    label_x = int(bx) + 25
                    label_y = int(by)
                    cv2.rectangle(display_frame,
                                 (label_x - 5, label_y - text_height - 10),
                                 (label_x + text_width + 5, label_y + 5),
                                 (0, 0, 0), -1)
                    cv2.putText(display_frame, label, (label_x, label_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Resize for display (base size)
        base_display_height = 600
        aspect_ratio = self.width / self.height
        base_display_width = int(base_display_height * aspect_ratio)
        
        if base_display_width > 900:
            base_display_width = 900
            base_display_height = int(base_display_width / aspect_ratio)
        
        # Apply zoom
        display_width = int(base_display_width * self.zoom_factor)
        display_height = int(base_display_height * self.zoom_factor)
        
        # Resize frame
        display_frame = cv2.resize(display_frame, (display_width, display_height))
        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        
        # Update canvas
        image = Image.fromarray(display_frame)
        photo = ImageTk.PhotoImage(image=image)
        
        # Check if canvas still exists before trying to delete (fixes Tkinter error)
        try:
            if self.canvas.winfo_exists():
                self.canvas.delete("all")
        except tk.TclError:
            # Canvas widget was destroyed, skip update
            return
        
        # Get canvas size (avoid update_idletasks to prevent window resizing)
        try:
            # Read canvas size without forcing layout update
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
        except tk.TclError:
            # Canvas widget was destroyed, skip update
            return
        
        # If canvas hasn't been rendered yet, use parent frame size
        if canvas_width <= 1 or canvas_height <= 1:
            # Use the parent frame size if available
            parent = self.canvas.master
            if parent:
                parent.update_idletasks()
                parent_width = parent.winfo_width()
                parent_height = parent.winfo_height()
                if parent_width > 1 and parent_height > 1:
                    # Account for padding (5px on each side = 10px total)
                    canvas_width = max(parent_width - 10, base_display_width)
                    canvas_height = max(parent_height - 10, base_display_height)
                else:
                    # Use base display size as fallback
                    canvas_width = base_display_width
                    canvas_height = base_display_height
            else:
                canvas_width = base_display_width
                canvas_height = base_display_height
            
            # Re-read canvas size (don't force update_idletasks as it can cause window resizing)
            try:
                # Just read the current size without forcing layout update
                actual_width = self.canvas.winfo_width()
                actual_height = self.canvas.winfo_height()
                if actual_width > 1 and actual_height > 1:
                    canvas_width = actual_width
                    canvas_height = actual_height
                else:
                    # If still not ready, use parent size as fallback
                    parent = self.canvas.master
                    if parent:
                        parent_width = parent.winfo_width()
                        parent_height = parent.winfo_height()
                        if parent_width > 1 and parent_height > 1:
                            canvas_width = max(parent_width - 10, base_display_width)
                            canvas_height = max(parent_height - 10, base_display_height)
            except tk.TclError:
                # Canvas widget was destroyed, skip update
                return
        
        # CRITICAL FIX: Don't explicitly set canvas size - let it fill naturally
        # Setting explicit size causes window to resize on every update
        # The canvas is already configured with fill=tk.BOTH, expand=True
        
        # Calculate position with pan offset
        # Center the image in the canvas, then apply pan offset
        # On first display, ensure image is centered (reset pan if needed)
        if self._first_display:
            self.pan_x = 0
            self.pan_y = 0
            self._first_display = False
        
        img_x = canvas_width // 2 + self.pan_x
        img_y = canvas_height // 2 + self.pan_y
        
        # Clamp pan to keep image visible (but allow some flexibility)
        max_pan_x = max(0, (display_width // 2) - (canvas_width // 2))
        max_pan_y = max(0, (display_height // 2) - (canvas_height // 2))
        self.pan_x = max(-max_pan_x, min(max_pan_x, self.pan_x))
        self.pan_y = max(-max_pan_y, min(max_pan_y, self.pan_y))
        
        # Recalculate position after clamping
        img_x = canvas_width // 2 + self.pan_x
        img_y = canvas_height // 2 + self.pan_y
        
        # Check if canvas still exists before creating image
        try:
            if self.canvas.winfo_exists():
                self.canvas.create_image(img_x, img_y, image=photo, anchor=tk.CENTER)
                # CRITICAL: Keep PhotoImage reference on instance to prevent garbage collection
                if not hasattr(self, '_canvas_image_refs'):
                    self._canvas_image_refs = []
                self._canvas_image_refs.append(photo)
                # Keep only last 2 references to prevent memory buildup
                if len(self._canvas_image_refs) > 2:
                    self._canvas_image_refs.pop(0)
        except tk.TclError:
            # Canvas widget was destroyed, skip update
            return
        
        # Update zoom label
        if hasattr(self, 'zoom_label'):
            self.zoom_label.config(text=f"{int(self.zoom_factor * 100)}%")
        
        # Update frame label
        max_frame = max(0, self.total_frames - 1) if self.total_frames > 0 else 0
        # Update frame number label in navigation bar
        if hasattr(self, 'frame_number_label'):
            self.frame_number_label.config(text=f"{self.current_frame_num} / {max_frame}")
        self.frame_var.set(self.current_frame_num)
        
        # Update ball count for current frame
        if hasattr(self, 'ball_count_label'):
            self.update_ball_count()
    
    def get_detection_color(self, track_id):
        """Get color for detection based on approved mappings"""
        pid_str = str(int(track_id))
        
        # If mapped, use team color or green
        if pid_str in self.approved_mappings:
            # Try to get team color
            if self.team_colors:
                # For now, use green for approved
                return (0, 255, 0)  # Green for approved/mapped
        
        # Default colors
        hue = (int(track_id) * 137) % 180
        color_hsv = np.uint8([[[hue, 255, 255]]])
        color_bgr = cv2.cvtColor(color_hsv, cv2.COLOR_HSV2BGR)[0][0]
        return tuple(map(int, color_bgr))
    
    def update_detections_list(self):
        """Update detections listbox with improved formatting"""
        self.detections_listbox.delete(0, tk.END)
        
        if self.current_detections is None:
            return
        
        # Store mapping of listbox index to detection index
        self.listbox_to_detection_map = {}
        
        listbox_idx = 0
        for i, (xyxy, track_id, conf) in enumerate(zip(
            self.current_detections.xyxy,
            self.current_detections.tracker_id,
            self.current_detections.confidence
        )):
            if track_id is None:
                continue
            
            if track_id in self.rejected_ids:
                continue
            
            track_id = self.merged_ids.get(track_id, track_id)
            pid_str = str(int(track_id))
            
            # Check if this is an anchor frame (should show 1.00 confidence)
            is_anchor = False
            frame_key = str(self.current_frame_num)  # Anchor frames use string keys when loaded from JSON
            if frame_key in self.anchor_frames:
                for anchor in self.anchor_frames[frame_key]:
                    if anchor.get("track_id") == int(track_id):
                        is_anchor = True
                        break
            # Also check integer key (for in-memory anchor frames)
            if not is_anchor and self.current_frame_num in self.anchor_frames:
                for anchor in self.anchor_frames[self.current_frame_num]:
                    if anchor.get("track_id") == int(track_id):
                        is_anchor = True
                        break
            
            # If this is an anchor frame, use 1.00 confidence
            if is_anchor:
                conf = 1.00
            
            # Get player name (handle tuple format)
            if pid_str in self.approved_mappings:
                mapping = self.approved_mappings[pid_str]
                if isinstance(mapping, tuple):
                    player_name = mapping[0]
                    team = mapping[1] if mapping[1] else ""
                else:
                    player_name = mapping
                    team = ""
                status = "✓"
                team_display = f" ({team})" if team and team != "Unknown" else ""
            else:
                # Check for gallery suggestions
                gallery_suggestion = ""
                if hasattr(self, 'gallery_suggestions') and track_id in self.gallery_suggestions:
                    suggested_name, confidence = self.gallery_suggestions[track_id]
                    gallery_suggestion = f" [Gallery: {suggested_name} ({confidence:.0%})]"
                
                player_name = f"#{track_id}{gallery_suggestion}"
                team_display = ""
                if track_id >= 10000:
                    player_name += " (manual)"
                status = "○"
            
            # Add anchor emoji if this is an anchor frame
            anchor_indicator = " ⚓" if is_anchor else ""
            
            # Make label more readable with larger font indicators
            display_text = f"{status} {player_name}{team_display}{anchor_indicator} | Conf: {conf:.2f}"
            
            # Highlight if selected
            if self.selected_detection == i:
                display_text = f"→ {display_text}"
            
            self.detections_listbox.insert(tk.END, display_text)
            self.listbox_to_detection_map[listbox_idx] = i
            listbox_idx += 1
        
        # Highlight selected item in listbox
        if self.selected_detection is not None:
            for listbox_idx, det_idx in self.listbox_to_detection_map.items():
                if det_idx == self.selected_detection:
                    self.detections_listbox.selection_clear(0, tk.END)
                    self.detections_listbox.selection_set(listbox_idx)
                    self.detections_listbox.see(listbox_idx)
                    break
    
    def on_detection_select(self, event):
        """Handle detection selection from listbox"""
        selection = self.detections_listbox.curselection()
        if not selection:
            return
        
        # Get the index from listbox
        listbox_index = selection[0]
        
        # Find the corresponding detection index
        if self.current_detections is None:
            return
        
        # Map listbox index to detection index (need to account for rejected IDs)
        valid_indices = []
        for i, (xyxy, track_id, conf) in enumerate(zip(
            self.current_detections.xyxy,
            self.current_detections.tracker_id,
            self.current_detections.confidence
        )):
            if track_id is None or track_id in self.rejected_ids:
                continue
            valid_indices.append(i)
        
        if listbox_index < len(valid_indices):
            self.selected_detection = valid_indices[listbox_index]
            self.update_selected_info()
            self.update_display()
            # Scroll to ensure selected detection is visible on canvas
            self.scroll_to_selected_detection()
    
    def on_listbox_double_click(self, event):
        """Handle double-click on listbox item to zoom"""
        selection = self.detections_listbox.curselection()
        if selection:
            # Ensure selection is set first
            self.on_detection_select(event)
            self.zoom_selected_player()
    
    def scroll_to_selected_detection(self):
        """Scroll canvas to center on selected detection"""
        if self.selected_detection is None or self.current_detections is None:
            return
        
        if self.selected_detection >= len(self.current_detections.xyxy):
            return
        
        xyxy = self.current_detections.xyxy[self.selected_detection]
        x1, y1, x2, y2 = xyxy
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        
        # Convert to canvas coordinates
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        scale_x = canvas_width / self.width
        scale_y = canvas_height / self.height
        
        canvas_x = cx * scale_x
        canvas_y = cy * scale_y
        
        # Scroll canvas to center the detection (if using scrollable canvas)
        # For now, we'll just ensure it's visible by updating display
        self.update_display()
    
    def toggle_manual_mode(self):
        """Toggle manual detection mode"""
        self.manual_detection_mode = not self.manual_detection_mode
        if self.manual_detection_mode:
            self.manual_mode_button.config(text="Disable Manual Detection", state=tk.ACTIVE)
            self.canvas.config(cursor="crosshair")
            self.ball_click_mode = False  # Disable ball mode if active
            self.ball_click_button.config(text="Click to Mark Ball", state=tk.NORMAL)
        else:
            self.manual_mode_button.config(text="Enable Manual Detection")
            self.canvas.config(cursor="")
            # Cancel any ongoing box drawing
            if self.current_box_id:
                self.canvas.delete(self.current_box_id)
                self.current_box_id = None
            self.drawing_box = False
            self.box_start = None
            self.box_end = None
    
    def on_canvas_click(self, event):
        """Handle canvas click"""
        if self.ball_click_mode:
            # Get canvas coordinates (accounting for scrolling if any)
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            
            # Get actual canvas dimensions (must be > 1, otherwise canvas not yet rendered)
            canvas_width = max(1, self.canvas.winfo_width())
            canvas_height = max(1, self.canvas.winfo_height())
            
            # Calculate displayed image dimensions (same as in update_display)
            base_display_height = 600
            aspect_ratio = self.width / self.height if self.height > 0 else 1.0
            base_display_width = int(base_display_height * aspect_ratio)
            
            if base_display_width > 900:
                base_display_width = 900
                base_display_height = int(base_display_width / aspect_ratio) if aspect_ratio > 0 else base_display_height
            
            # Apply zoom (same as in update_display)
            display_width = int(base_display_width * self.zoom_factor)
            display_height = int(base_display_height * self.zoom_factor)
            
            # Calculate image position on canvas (same as in update_display)
            # Image is centered on canvas with pan offset
            img_x = canvas_width // 2 + self.pan_x
            img_y = canvas_height // 2 + self.pan_y
            
            # Convert canvas coordinates to image-relative coordinates
            # Account for image being centered on canvas
            image_relative_x = canvas_x - img_x + (display_width // 2)
            image_relative_y = canvas_y - img_y + (display_height // 2)
            
            # Check if click is within the displayed image bounds
            if (image_relative_x < 0 or image_relative_x > display_width or 
                image_relative_y < 0 or image_relative_y > display_height):
                messagebox.showwarning("Warning", "Click is outside the video frame. Please click on the video.")
                return
            
            # Convert display coordinates to original frame coordinates
            scale_x = self.width / display_width if display_width > 0 else 1.0
            scale_y = self.height / display_height if display_height > 0 else 1.0
            
            frame_x = image_relative_x * scale_x
            frame_y = image_relative_y * scale_y
            
            # Clamp to frame bounds
            frame_x = max(0, min(self.width - 1, frame_x))
            frame_y = max(0, min(self.height - 1, frame_y))
            
            # Debug output (can be removed later)
            print(f"Ball click: canvas=({canvas_x:.1f}, {canvas_y:.1f}), "
                  f"image_relative=({image_relative_x:.1f}, {image_relative_y:.1f}), "
                  f"display_size=({display_width}, {display_height}), "
                  f"frame=({frame_x:.1f}, {frame_y:.1f}), "
                  f"scale=({scale_x:.3f}, {scale_y:.3f}), "
                  f"zoom={self.zoom_factor:.2f}, pan=({self.pan_x}, {self.pan_y}), "
                  f"original_frame_size=({self.width}, {self.height})")
            
            # Check if ball already exists for this frame, replace if so
            existing_ball = None
            for i, (f, x, y) in enumerate(self.ball_positions):
                if f == self.current_frame_num:
                    existing_ball = i
                    break
            
            if existing_ball is not None:
                # Replace existing ball position
                self.ball_positions[existing_ball] = (self.current_frame_num, frame_x, frame_y)
                message = f"Ball position updated at frame {self.current_frame_num + 1}\n({int(frame_x)}, {int(frame_y)})"
            else:
                # Add new ball position
                self.ball_positions.append((self.current_frame_num, frame_x, frame_y))
                message = f"Ball position marked at frame {self.current_frame_num + 1}\n({int(frame_x)}, {int(frame_y)})"
            
            self.ball_click_mode = False
            self.ball_click_button.config(text="⚽ Mark Ball Position", state=tk.NORMAL)
            self.ball_status_label.config(text="Ball marked! Click button to mark again", 
                                          foreground="green", font=("Arial", 8))
            self.update_display()
            self.update_summary()
            self.update_ball_count()
            
            # Auto-save immediately when ball is marked (don't wait for timer)
            self.auto_save()
            
            messagebox.showinfo("Ball Marked", message)
            return
        
        if self.manual_detection_mode:
            # Start drawing a bounding box (use canvas coordinates for drawing)
            self.drawing_box = True
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            self.box_start = (canvas_x, canvas_y)
            self.box_end = (canvas_x, canvas_y)
            # Draw initial box
            if self.current_box_id:
                self.canvas.delete(self.current_box_id)
            self.current_box_id = self.canvas.create_rectangle(
                self.box_start[0], self.box_start[1],
                self.box_end[0], self.box_end[1],
                outline="yellow", width=2, dash=(5, 5)
            )
            return
        
        # Otherwise, try to select detection by click
        if self.current_detections is None:
            return
        
        # Get canvas coordinates (accounting for scrolling if any)
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # Get actual canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Calculate displayed image dimensions (same as in update_display)
        display_height = 600
        aspect_ratio = self.width / self.height
        display_width = int(display_height * aspect_ratio)
        
        if display_width > 900:
            display_width = 900
            display_height = int(display_width / aspect_ratio)
        
        # Image is centered on canvas, calculate offset
        offset_x = (canvas_width - display_width) / 2
        offset_y = (canvas_height - display_height) / 2
        
        # Convert canvas coordinates to display image coordinates
        display_x = canvas_x - offset_x
        display_y = canvas_y - offset_y
        
        # Check if click is within the displayed image bounds
        if display_x < 0 or display_x > display_width or display_y < 0 or display_y > display_height:
            return  # Click outside image, ignore
        
        # Convert display coordinates to original frame coordinates
        scale_x = self.width / display_width
        scale_y = self.height / display_height
        
        frame_x = display_x * scale_x
        frame_y = display_y * scale_y
        
        # Find closest detection (using frame coordinates)
        min_dist = float('inf')
        closest_idx = None
        
        for i, (xyxy, track_id, conf) in enumerate(zip(
            self.current_detections.xyxy,
            self.current_detections.tracker_id,
            self.current_detections.confidence
        )):
            if track_id is None or track_id in self.rejected_ids:
                continue
            
            x1, y1, x2, y2 = xyxy
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            
            # Calculate distance in frame coordinates (more accurate)
            dist = np.sqrt((frame_x - cx)**2 + (frame_y - cy)**2)
            # Threshold in frame coordinates (50 pixels scaled)
            threshold_frame = 50 * scale_x
            if dist < min_dist and dist < threshold_frame:
                min_dist = dist
                closest_idx = i
        
        if closest_idx is not None:
            self.selected_detection = closest_idx
            # Find corresponding listbox index
            if hasattr(self, 'listbox_to_detection_map'):
                for listbox_idx, det_idx in self.listbox_to_detection_map.items():
                    if det_idx == closest_idx:
                        self.detections_listbox.selection_clear(0, tk.END)
                        self.detections_listbox.selection_set(listbox_idx)
                        self.detections_listbox.see(listbox_idx)
                        break
            self.update_selected_info()
            self.update_display()
    
    def on_canvas_drag(self, event):
        """Handle canvas drag (while drawing box)"""
        if self.manual_detection_mode and self.drawing_box:
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            self.box_end = (canvas_x, canvas_y)
            # Update box
            if self.current_box_id:
                self.canvas.delete(self.current_box_id)
            self.current_box_id = self.canvas.create_rectangle(
                self.box_start[0], self.box_start[1],
                self.box_end[0], self.box_end[1],
                outline="yellow", width=2, dash=(5, 5)
            )
    
    def on_canvas_release(self, event):
        """Handle canvas release (finish drawing box)"""
        if self.manual_detection_mode and self.drawing_box:
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            self.box_end = (canvas_x, canvas_y)
            self.drawing_box = False
            
            # Calculate box dimensions (in canvas coordinates)
            x1, y1 = self.box_start
            x2, y2 = self.box_end
            
            # Ensure x1 < x2 and y1 < y2
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            
            # Get actual canvas dimensions (must be > 1, otherwise canvas not yet rendered)
            canvas_width = max(1, self.canvas.winfo_width())
            canvas_height = max(1, self.canvas.winfo_height())
            
            # Calculate displayed image dimensions (same as in update_display)
            display_height = 600
            aspect_ratio = self.width / self.height if self.height > 0 else 1.0
            display_width = int(display_height * aspect_ratio)
            
            if display_width > 900:
                display_width = 900
                display_height = int(display_width / aspect_ratio) if aspect_ratio > 0 else display_height
            
            # In update_display, canvas is configured to match display dimensions exactly:
            # self.canvas.config(width=display_width, height=display_height)
            # And image is placed at center with anchor=CENTER
            # So canvas coordinates ARE display coordinates (no offset needed)
            
            # Check if box is within the displayed image bounds
            if x1 < 0 or x1 > display_width or x2 < 0 or x2 > display_width or \
               y1 < 0 or y1 > display_height or y2 < 0 or y2 > display_height:
                # Box is outside image, cancel
                if self.current_box_id:
                    self.canvas.delete(self.current_box_id)
                self.current_box_id = None
                self.box_start = None
                self.box_end = None
                return
            
            # Check minimum size (at least 20x20 pixels in display space)
            if abs(x2 - x1) < 20 or abs(y2 - y1) < 20:
                # Too small, cancel
                if self.current_box_id:
                    self.canvas.delete(self.current_box_id)
                self.current_box_id = None
                self.box_start = None
                self.box_end = None
                return
            
            # Convert display coordinates to original frame coordinates
            scale_x = self.width / display_width if display_width > 0 else 1.0
            scale_y = self.height / display_height if display_height > 0 else 1.0
            
            frame_x1 = x1 * scale_x
            frame_y1 = y1 * scale_y
            frame_x2 = x2 * scale_x
            frame_y2 = y2 * scale_y
            
            # Clamp to frame bounds
            frame_x1 = max(0, min(self.width - 1, frame_x1))
            frame_y1 = max(0, min(self.height - 1, frame_y1))
            frame_x2 = max(0, min(self.width - 1, frame_x2))
            frame_y2 = max(0, min(self.height - 1, frame_y2))
            
            # Create manual detection
            self.add_manual_detection(frame_x1, frame_y1, frame_x2, frame_y2)
            
            # Clean up drawing
            if self.current_box_id:
                self.canvas.delete(self.current_box_id)
            self.current_box_id = None
            self.box_start = None
            self.box_end = None
    
    def add_manual_detection(self, x1, y1, x2, y2):
        """Add a manually drawn detection to the current frame"""
        if self.current_frame is None:
            return
        
        # Generate unique manual ID
        manual_id = self.next_manual_id
        self.next_manual_id += 1
        
        # Create detection arrays
        # We need to create a proper sv.Detections object
        xyxy = np.array([[x1, y1, x2, y2]], dtype=np.float32)
        confidence = np.array([0.95], dtype=np.float32)  # High confidence for manual
        tracker_id = np.array([manual_id], dtype=np.int32)
        
        # Create or append to current detections
        if self.current_detections is None:
            # Create new detections
            self.current_detections = sv.Detections(
                xyxy=xyxy,
                confidence=confidence,
                tracker_id=tracker_id
            )
        else:
            # Append to existing detections
            existing_xyxy = self.current_detections.xyxy
            existing_conf = self.current_detections.confidence
            existing_tracker_id = self.current_detections.tracker_id
            
            # Combine arrays
            new_xyxy = np.vstack([existing_xyxy, xyxy])
            new_conf = np.concatenate([existing_conf, confidence])
            new_tracker_id = np.concatenate([existing_tracker_id, tracker_id])
            
            # Create new detections object
            self.current_detections = sv.Detections(
                xyxy=new_xyxy,
                confidence=new_conf,
                tracker_id=new_tracker_id
            )
        
        # Update history
        self.detections_history[self.current_frame_num] = self.current_detections
        
        # Store manual detection for tracking across frames
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        if self.current_frame_num not in self.manual_detections_history:
            self.manual_detections_history[self.current_frame_num] = []
        self.manual_detections_history[self.current_frame_num].append({
            'id': manual_id,
            'xyxy': (x1, y1, x2, y2),
            'center': (center_x, center_y),
            'frame': self.current_frame_num
        })
        
        # Initialize velocity (will be updated as we track)
        self.manual_detection_velocities[manual_id] = (0.0, 0.0)
        
        # Update display
        self.update_display()
        self.update_detections_list()
        
        # Auto-select the new detection
        if len(self.current_detections) > 0:
            self.selected_detection = len(self.current_detections) - 1
            self.detections_listbox.selection_clear(0, tk.END)
            self.detections_listbox.selection_set(self.selected_detection)
            self.detections_listbox.see(self.selected_detection)
            self.update_selected_info()
        
        messagebox.showinfo("Manual Detection Added", 
                          f"Manual detection added with ID #{manual_id}\n"
                          "This detection will be tracked across frames and merged with YOLO detections when found.")
    
    def on_canvas_hover(self, event):
        """Handle canvas hover"""
        pass
    
    def update_manual_detection_tracking(self):
        """Update manual detection positions based on velocity prediction and add to current frame if not matched"""
        if not self.manual_detections_history:
            return
        
        current_frame = self.current_frame_num
        
        # Check if we have manual detections from previous frames that should appear in current frame
        # Look back up to 30 frames to find manual detections
        for lookback in range(1, min(30, current_frame + 1)):
            prev_frame = current_frame - lookback
            if prev_frame not in self.manual_detections_history:
                continue
            
            for manual_det in self.manual_detections_history[prev_frame]:
                manual_id = manual_det['id']
                
                # Skip if already merged
                if manual_id in self.merged_ids:
                    continue
                
                # Check if this manual detection already exists in current frame
                if current_frame in self.manual_detections_history:
                    if any(d['id'] == manual_id for d in self.manual_detections_history[current_frame]):
                        continue  # Already exists in current frame
                
                # Predict position based on velocity
                vx, vy = self.manual_detection_velocities.get(manual_id, (0.0, 0.0))
                prev_xyxy = manual_det['xyxy']
                prev_center = manual_det['center']
                
                # Predict new position
                predicted_center = (
                    prev_center[0] + vx * lookback,
                    prev_center[1] + vy * lookback
                )
                
                # Calculate predicted bounding box (maintain size, move center)
                box_width = prev_xyxy[2] - prev_xyxy[0]
                box_height = prev_xyxy[3] - prev_xyxy[1]
                predicted_x1 = predicted_center[0] - box_width / 2
                predicted_y1 = predicted_center[1] - box_height / 2
                predicted_x2 = predicted_center[0] + box_width / 2
                predicted_y2 = predicted_center[1] + box_height / 2
                
                # Check if predicted position is within frame bounds
                if (0 <= predicted_x1 < self.width and 0 <= predicted_x2 < self.width and
                    0 <= predicted_y1 < self.height and 0 <= predicted_y2 < self.height):
                    
                    # Add predicted manual detection to current frame detections
                    if self.current_detections is None:
                        # Create new detections
                        xyxy = np.array([[predicted_x1, predicted_y1, predicted_x2, predicted_y2]], dtype=np.float32)
                        confidence = np.array([0.90], dtype=np.float32)  # Slightly lower confidence for predicted
                        tracker_id = np.array([manual_id], dtype=np.int32)
                        self.current_detections = sv.Detections(
                            xyxy=xyxy,
                            confidence=confidence,
                            tracker_id=tracker_id
                        )
                    else:
                        # Check if manual_id already exists in current detections
                        if manual_id not in self.current_detections.tracker_id:
                            # Append to existing detections
                            xyxy = np.array([[predicted_x1, predicted_y1, predicted_x2, predicted_y2]], dtype=np.float32)
                            confidence = np.array([0.90], dtype=np.float32)
                            tracker_id = np.array([manual_id], dtype=np.int32)
                            
                            existing_xyxy = self.current_detections.xyxy
                            existing_conf = self.current_detections.confidence
                            existing_tracker_id = self.current_detections.tracker_id
                            
                            new_xyxy = np.vstack([existing_xyxy, xyxy])
                            new_conf = np.concatenate([existing_conf, confidence])
                            new_tracker_id = np.concatenate([existing_tracker_id, tracker_id])
                            
                            self.current_detections = sv.Detections(
                                xyxy=new_xyxy,
                                confidence=new_conf,
                                tracker_id=new_tracker_id
                            )
                    
                    # Store in history for current frame
                    if current_frame not in self.manual_detections_history:
                        self.manual_detections_history[current_frame] = []
                    self.manual_detections_history[current_frame].append({
                        'id': manual_id,
                        'xyxy': (predicted_x1, predicted_y1, predicted_x2, predicted_y2),
                        'center': predicted_center,
                        'frame': current_frame
                    })
                    
                    # Update detections history
                    self.detections_history[current_frame] = self.current_detections
    
    def match_manual_detections(self):
        """Match manual detections with YOLO detections in current frame"""
        if self.current_detections is None or len(self.current_detections) == 0:
            return
        
        if self.current_frame_num not in self.manual_detections_history:
            return
        
        # Get manual detections for current frame
        manual_dets = self.manual_detections_history[self.current_frame_num]
        if not manual_dets:
            return
        
        # Get YOLO detections
        yolo_xyxy = self.current_detections.xyxy
        yolo_tracker_ids = self.current_detections.tracker_id
        
        # Match each manual detection with closest YOLO detection
        for manual_det in manual_dets:
            manual_id = manual_det['id']
            
            # Skip if already merged
            if manual_id in self.merged_ids:
                continue
            
            manual_xyxy = manual_det['xyxy']
            manual_center = manual_det['center']
            
            # Find closest YOLO detection
            best_match_idx = None
            best_distance = float('inf')
            max_match_distance = 150  # Maximum distance for matching (pixels)
            
            for i, (yolo_xyxy_item, yolo_id) in enumerate(zip(yolo_xyxy, yolo_tracker_ids)):
                if yolo_id is None or yolo_id in self.rejected_ids:
                    continue
                
                # Skip if YOLO detection is already merged to a manual detection
                if yolo_id in self.merged_ids.values():
                    continue
                
                # Calculate center of YOLO detection
                yolo_x1, yolo_y1, yolo_x2, yolo_y2 = yolo_xyxy_item
                yolo_center = ((yolo_x1 + yolo_x2) / 2, (yolo_y1 + yolo_y2) / 2)
                
                # Calculate distance
                distance = np.sqrt(
                    (manual_center[0] - yolo_center[0])**2 + 
                    (manual_center[1] - yolo_center[1])**2
                )
                
                # Also check IoU (Intersection over Union) for better matching
                manual_x1, manual_y1, manual_x2, manual_y2 = manual_xyxy
                intersection_x1 = max(manual_x1, yolo_x1)
                intersection_y1 = max(manual_y1, yolo_y1)
                intersection_x2 = min(manual_x2, yolo_x2)
                intersection_y2 = min(manual_y2, yolo_y2)
                
                if intersection_x2 > intersection_x1 and intersection_y2 > intersection_y1:
                    intersection_area = (intersection_x2 - intersection_x1) * (intersection_y2 - intersection_y1)
                    manual_area = (manual_x2 - manual_x1) * (manual_y2 - manual_y1)
                    yolo_area = (yolo_x2 - yolo_x1) * (yolo_y2 - yolo_y1)
                    union_area = manual_area + yolo_area - intersection_area
                    iou = intersection_area / union_area if union_area > 0 else 0
                    
                    # Prefer IoU > 0.3 or distance < 100
                    if iou > 0.3 or distance < 100:
                        # Use combined score (lower is better)
                        combined_score = distance * (1.0 - iou * 0.5)
                        if combined_score < best_distance:
                            best_distance = combined_score
                            best_match_idx = i
            
            # If we found a good match, merge the IDs
            if best_match_idx is not None and best_distance < max_match_distance:
                yolo_id = int(yolo_tracker_ids[best_match_idx])
                
                # Merge: manual_id -> yolo_id (manual detection becomes the YOLO detection)
                self.merged_ids[manual_id] = yolo_id
                
                # Transfer any player name from manual detection to YOLO detection
                manual_id_str = str(manual_id)
                yolo_id_str = str(yolo_id)
                if manual_id_str in self.approved_mappings:
                    # Transfer mapping to YOLO ID
                    self.approved_mappings[yolo_id_str] = self.approved_mappings[manual_id_str]
                
                # Update velocity based on movement
                yolo_xyxy_item = yolo_xyxy[best_match_idx]
                yolo_center = (
                    (yolo_xyxy_item[0] + yolo_xyxy_item[2]) / 2,
                    (yolo_xyxy_item[1] + yolo_xyxy_item[3]) / 2
                )
                
                # Find previous position of this manual detection
                prev_center = manual_center
                for prev_frame in range(max(0, self.current_frame_num - 10), self.current_frame_num):
                    if prev_frame in self.manual_detections_history:
                        for prev_det in self.manual_detections_history[prev_frame]:
                            if prev_det['id'] == manual_id:
                                prev_center = prev_det['center']
                                break
                
                # Calculate velocity (pixels per frame)
                frames_diff = 1  # Assume 1 frame difference
                vx = (yolo_center[0] - prev_center[0]) / frames_diff
                vy = (yolo_center[1] - prev_center[1]) / frames_diff
                self.manual_detection_velocities[manual_id] = (vx, vy)
                
                print(f"✓ Matched manual detection #{manual_id} with YOLO detection #{yolo_id} (distance: {best_distance:.1f}px)")
                
                # Update display to show the merge
                self.update_display()
                self.update_detections_list()
    
    def zoom_selected_player(self):
        """Open a zoomed view of the selected player"""
        if self.selected_detection is None or self.current_detections is None:
            messagebox.showwarning("Warning", "Please select a player first")
            return
        
        if self.selected_detection >= len(self.current_detections.xyxy):
            return
        
        # Get detection bounding box
        xyxy = self.current_detections.xyxy[self.selected_detection]
        track_id = self.current_detections.tracker_id[self.selected_detection]
        
        if track_id is None:
            return
        
        track_id = self.merged_ids.get(track_id, track_id)
        pid_str = str(int(track_id))
        
        # Get player name
        if pid_str in self.approved_mappings:
            mapping = self.approved_mappings[pid_str]
            if isinstance(mapping, tuple):
                player_name = str(mapping[0]) if mapping[0] is not None else f"Player #{track_id}"
            else:
                player_name = str(mapping) if mapping is not None else f"Player #{track_id}"
        else:
            player_name = f"Player #{track_id}"
        
        # Ensure player_name is a string
        player_name = str(player_name) if player_name is not None else f"Player #{track_id}"
        
        # Extract player region with padding
        x1, y1, x2, y2 = map(int, xyxy)
        padding = 30  # Extra pixels around the player
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(self.width, x2 + padding)
        y2 = min(self.height, y2 + padding)
        
        # Extract region from current frame
        if self.current_frame is None:
            return
        
        player_region = self.current_frame[y1:y2, x1:x2].copy()
        
        # Create zoom window
        zoom_window = tk.Toplevel(self.root)
        zoom_window.title(f"Zoom: {player_name} (ID: #{track_id})")
        zoom_window.geometry("600x800")
        zoom_window.lift()
        zoom_window.attributes('-topmost', True)
        zoom_window.after(200, lambda: zoom_window.attributes('-topmost', False))
        
        # Calculate zoom scale (make it at least 3x larger)
        region_width = x2 - x1
        region_height = y2 - y1
        zoom_scale = max(3.0, min(600 / region_width, 700 / region_height))
        
        zoom_width = int(region_width * zoom_scale)
        zoom_height = int(region_height * zoom_scale)
        
        # Resize player region
        zoomed_region = cv2.resize(player_region, (zoom_width, zoom_height), 
                                   interpolation=cv2.INTER_CUBIC)
        
        # Draw bounding box on zoomed region (scaled)
        box_thickness = max(2, int(3 * zoom_scale))
        cv2.rectangle(zoomed_region, 
                      (padding, padding), 
                      (zoom_width - padding, zoom_height - padding),
                      (0, 255, 0), box_thickness)
        
        # Draw label (ensure all parts are strings)
        label = f"{str(player_name)} (ID: #{int(track_id)})"
        font_scale = 1.2 * zoom_scale / 3.0  # Scale font appropriately
        font_thickness = max(2, int(3 * zoom_scale / 3.0))
        (text_width, text_height), baseline = cv2.getTextSize(
            str(label), cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
        
        cv2.rectangle(zoomed_region,
                     (5, 5),
                     (text_width + 15, text_height + baseline + 15),
                     (0, 0, 0), -1)
        cv2.putText(zoomed_region, str(label), (10, text_height + 10),
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), font_thickness)
        
        # Convert to PhotoImage
        zoomed_rgb = cv2.cvtColor(zoomed_region, cv2.COLOR_BGR2RGB)
        zoomed_pil = Image.fromarray(zoomed_rgb)
        zoomed_photo = ImageTk.PhotoImage(image=zoomed_pil)
        
        # Create canvas for zoomed view
        zoom_canvas = tk.Canvas(zoom_window, width=zoom_width, height=zoom_height, bg="black")
        zoom_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        zoom_canvas.create_image(zoom_width // 2, zoom_height // 2, 
                                image=zoomed_photo, anchor=tk.CENTER)
        zoom_canvas.image = zoomed_photo  # Keep a reference
        
        # Add info label
        info_label = ttk.Label(zoom_window, 
                              text=f"Frame: {self.current_frame_num + 1} | "
                                   f"Position: ({x1}, {y1}) - ({x2}, {y2}) | "
                                   f"Size: {region_width}x{region_height}px",
                              font=("Arial", 9))
        info_label.pack(pady=5)
        
        # Close button
        ttk.Button(zoom_window, text="Close", command=zoom_window.destroy).pack(pady=5)
    
    def zoom_in(self):
        """Zoom in on the video"""
        self.zoom_factor = min(self.zoom_factor * 1.2, 5.0)  # Max 5x zoom
        self.update_display()
    
    def zoom_out(self):
        """Zoom out from the video"""
        self.zoom_factor = max(self.zoom_factor / 1.2, 0.5)  # Min 0.5x zoom
        # Reset pan if zoomed out to fit
        if self.zoom_factor <= 1.0:
            self.pan_x = 0
            self.pan_y = 0
        self.update_display()
    
    def zoom_reset(self):
        """Reset zoom and pan to default"""
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.update_display()
    
    def on_canvas_zoom(self, event):
        """Handle mouse wheel zoom"""
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            # Zoom in
            self.zoom_in()
        elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
            # Zoom out
            self.zoom_out()
    
    def on_canvas_pan_start(self, event):
        """Start panning"""
        if self.zoom_factor > 1.0:  # Only allow panning when zoomed in
            self.is_panning = True
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.canvas.config(cursor="fleur")  # Change cursor to indicate panning
    
    def on_canvas_pan_drag(self, event):
        """Handle panning drag"""
        if self.is_panning and self.zoom_factor > 1.0:
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.pan_x += dx
            self.pan_y += dy
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.update_display()
    
    def on_canvas_pan_end(self, event):
        """End panning"""
        self.is_panning = False
        self.canvas.config(cursor="crosshair")  # Restore cursor
    
    def update_selected_info(self):
        """Update info for selected detection"""
        if self.selected_detection is None or self.current_detections is None:
            self.selected_id_label.config(text="None")
            return
        
        # Validate selected_detection index
        if self.selected_detection >= len(self.current_detections.tracker_id):
            # Invalid index, clear selection
            self.selected_detection = None
            self.selected_id_label.config(text="None")
            return
        
        track_id = self.current_detections.tracker_id[self.selected_detection]
        if track_id is None:
            return
        
        track_id = self.merged_ids.get(track_id, track_id)
        pid_str = str(int(track_id))
        
        self.selected_id_label.config(text=f"ID: #{track_id}")
        
        # Load existing name if mapped
        if pid_str in self.approved_mappings:
            mapping = self.approved_mappings[pid_str]
            if isinstance(mapping, tuple):
                name = mapping[0]
                team = mapping[1] if len(mapping) > 1 else ""
                jersey_number = mapping[2] if len(mapping) > 2 else ""
            else:
                name = mapping
                team = ""
                jersey_number = ""
            self.player_name_var.set(name)
            self.team_var.set(team if team else "")
            self.jersey_number_var.set(jersey_number if jersey_number else "")
        else:
            self.player_name_var.set("")
            self.team_var.set("")
            self.jersey_number_var.set("")
            
            # AUTO-DETECT jersey number using OCR if available
            if self.jersey_ocr is not None and self.current_frame is not None:
                try:
                    bbox = self.current_detections.xyxy[self.selected_detection]
                    x1, y1, x2, y2 = map(int, bbox)
                    # Extract jersey region (upper 40% of bounding box)
                    jersey_y1 = int(y1)
                    jersey_y2 = int(y1 + (y2 - y1) * 0.40)
                    jersey_bbox = [x1, jersey_y1, x2, jersey_y2]
                    
                    # Detect jersey number
                    ocr_result = self.jersey_ocr.detect_jersey_number(self.current_frame, jersey_bbox)
                    if ocr_result and ocr_result.get('jersey_number'):
                        detected_jersey = ocr_result['jersey_number']
                        confidence = ocr_result.get('confidence', 0.0)
                        if confidence >= 0.5:  # Only use if confidence is reasonable
                            self.jersey_number_var.set(str(detected_jersey))
                            print(f"🔢 Auto-detected jersey number for Track #{track_id}: {detected_jersey} (confidence: {confidence:.2f})")
                except Exception as e:
                    print(f"⚠ Jersey OCR failed for Track #{track_id}: {e}")
            
            # Show gallery suggestion if available
            if hasattr(self, 'gallery_suggestions') and track_id in self.gallery_suggestions:
                suggested_name, confidence = self.gallery_suggestions[track_id]
                # Auto-populate name if confidence is high enough
                if confidence >= self.reid_auto_tag_threshold:
                    self.player_name_var.set(suggested_name)
                    # Try to get team from gallery
                    if self.player_gallery is not None:
                        try:
                            player_id = suggested_name.lower().replace(" ", "_")
                            if player_id in self.player_gallery.players:
                                profile = self.player_gallery.players[player_id]
                                if profile.team:
                                    self.team_var.set(profile.team)
                                if profile.jersey_number:
                                    self.jersey_number_var.set(profile.jersey_number)
                        except:
                            pass
                    print(f"💡 Auto-filled from gallery: {suggested_name} (confidence: {confidence:.2f})")
                else:
                    # Show suggestion in status
                    self.status_label.config(text=f"💡 Gallery suggests: {suggested_name} ({confidence:.0%}) - Press Enter to accept")
    
    def tag_player(self):
        """Tag selected player with name"""
        if self.selected_detection is None or self.current_detections is None:
            messagebox.showwarning("Warning", "Please select a detection first")
            return
        
        # Validate selected_detection index
        if self.selected_detection >= len(self.current_detections.tracker_id):
            messagebox.showwarning("Warning", "Selected detection is no longer valid. Please select a player again.")
            self.selected_detection = None
            return
        
        track_id = self.current_detections.tracker_id[self.selected_detection]
        if track_id is None:
            return
        
        track_id = self.merged_ids.get(track_id, track_id)
        pid_str = str(int(track_id))
        
        player_name = self.player_name_var.get().strip()
        if not player_name:
            messagebox.showwarning("Warning", "Please select or enter a player name")
            return
        
        # If name is not in list, offer to add it
        # Ensure player_name_list is a list (not a dict)
        if not isinstance(self.player_name_list, list):
            # Convert to list if it's a dict
            if isinstance(self.player_name_list, dict):
                self.player_name_list = list(set(self.player_name_list.values()))
            else:
                self.player_name_list = []
        
        if player_name not in self.player_name_list:
            response = messagebox.askyesno("New Name", 
                f"'{player_name}' is not in your player list.\n\n"
                "Would you like to add it to the list?")
            if response:
                self.player_name_list.append(player_name)
                self.player_name_list.sort()
                self.player_name_combo['values'] = self.player_name_list
                self.save_player_name_list()
        
        team = self.team_var.get().strip()
        
        # Allow blank team - user can leave it empty if desired
        # Team is optional and can be set later if needed
        
        # Get jersey number (NEW) - try OCR first if available
        jersey_number = self.jersey_number_var.get().strip()
        
        # AUTO-DETECT jersey number using OCR if available and not manually entered
        if not jersey_number and self.jersey_ocr is not None and self.current_frame is not None:
            try:
                bbox = self.current_detections.xyxy[self.selected_detection]
                x1, y1, x2, y2 = map(int, bbox)
                # Extract jersey region (upper 40% of bounding box)
                jersey_y1 = int(y1)
                jersey_y2 = int(y1 + (y2 - y1) * 0.40)
                jersey_bbox = [x1, jersey_y1, x2, jersey_y2]
                
                # Detect jersey number
                ocr_result = self.jersey_ocr.detect_jersey_number(self.current_frame, jersey_bbox)
                if ocr_result and ocr_result.get('jersey_number'):
                    detected_jersey = ocr_result['jersey_number']
                    confidence = ocr_result.get('confidence', 0.0)
                    if confidence >= 0.5:  # Only use if confidence is reasonable
                        jersey_number = str(detected_jersey)
                        self.jersey_number_var.set(jersey_number)
                        print(f"🔢 Auto-detected jersey number: {jersey_number} (confidence: {confidence:.2f})")
            except Exception as e:
                print(f"⚠ Jersey OCR failed: {e}")
        
        # Validate jersey number (optional field, but must be numeric if provided)
        if jersey_number and not jersey_number.isdigit():
            messagebox.showwarning("Warning", "Jersey number must be a number (e.g. 5, 12, 99) or left blank")
            return
        
        # Smart suggestion: check nearby frames for same ID
        nearby_suggestions = self.find_nearby_frames_with_same_id(track_id)
        
        # Store mapping (now includes jersey number)
        self.approved_mappings[pid_str] = (player_name, team, jersey_number)
        
        # CRITICAL: Protect this player's identity for the next few frames
        # This prevents the system from overwriting a manually tagged player
        # when track IDs change during occlusions
        self.player_tag_protection[player_name] = (self.current_frame_num, int(track_id))
        
        # Store position for position-based matching
        if self.current_detections is not None and self.selected_detection < len(self.current_detections.xyxy):
            bbox = self.current_detections.xyxy[self.selected_detection]
            center_x = (bbox[0] + bbox[2]) / 2.0
            center_y = (bbox[1] + bbox[3]) / 2.0
            if player_name not in self.player_positions:
                self.player_positions[player_name] = []
            self.player_positions[player_name].append((self.current_frame_num, center_x, center_y, int(track_id)))
            # Keep only last 10 positions per player
            if len(self.player_positions[player_name]) > 10:
                self.player_positions[player_name] = self.player_positions[player_name][-10:]
            
            # Store Re-ID features for appearance-based matching (works with OC-SORT)
            if self.reid_tracker is not None and self.current_frame is not None:
                try:
                    # Create a single detection for this player
                    single_detection = sv.Detections(
                        xyxy=np.array([bbox]),
                        confidence=np.array([1.0]),
                        tracker_id=np.array([track_id])
                    )
                    # Extract Re-ID features (upper body)
                    reid_features = self.reid_tracker.extract_features(
                        self.current_frame, single_detection, None, None
                    )
                    
                    # Extract foot features (lower body - shoes/feet region)
                    foot_features = None
                    try:
                        foot_features = self.reid_tracker.extract_foot_features(
                            self.current_frame, single_detection
                        )
                        if foot_features is not None and len(foot_features) > 0:
                            foot_features = foot_features[0] if hasattr(foot_features, '__getitem__') else foot_features
                    except Exception as e:
                        print(f"⚠ Could not extract foot features: {e}")
                    
                    if reid_features is not None and len(reid_features) > 0:
                        # Store in session-based features
                        if player_name not in self.player_reid_features:
                            self.player_reid_features[player_name] = []
                        # Store the feature vector (first detection's features)
                        feature_vector = reid_features[0] if hasattr(reid_features, '__getitem__') else reid_features
                        # Ensure feature vector is 1D (flatten if needed)
                        if isinstance(feature_vector, np.ndarray) and len(feature_vector.shape) > 1:
                            feature_vector = feature_vector.flatten()
                        elif not isinstance(feature_vector, np.ndarray):
                            feature_vector = np.array(feature_vector).flatten()
                        self.player_reid_features[player_name].append((self.current_frame_num, feature_vector))
                        # Keep only last 5 Re-ID features per player
                        if len(self.player_reid_features[player_name]) > 5:
                            self.player_reid_features[player_name] = self.player_reid_features[player_name][-5:]
                        
                        # CRITICAL: Also save to player gallery for cross-video identification
                        if self.player_gallery is not None:
                            try:
                                # numpy is already imported at module level
                                # Convert to numpy array if needed
                                if not isinstance(feature_vector, np.ndarray):
                                    feature_vector = np.array(feature_vector)
                                
                                # Convert foot features if available
                                foot_feature_vector = None
                                if foot_features is not None:
                                    if not isinstance(foot_features, np.ndarray):
                                        foot_features = np.array(foot_features)
                                    # Ensure foot features are 1D (flatten if needed)
                                    if len(foot_features.shape) > 1:
                                        foot_features = foot_features.flatten()
                                    foot_feature_vector = foot_features
                                
                                # Extract foot region bbox for reference frame
                                foot_bbox = None
                                if foot_feature_vector is not None:
                                    x1, y1, x2, y2 = bbox
                                    bbox_height = y2 - y1
                                    foot_y1 = int(y1 + bbox_height * 0.60)  # Bottom 40%
                                    foot_y2 = int(y1 + bbox_height * 0.80)  # Bottom 20%
                                    foot_bbox = [x1, foot_y1, x2, foot_y2]
                                
                                # Create reference frame info
                                reference_frame = {
                                    "video_path": self.video_path,
                                    "frame_num": self.current_frame_num,
                                    "bbox": bbox.tolist() if hasattr(bbox, 'tolist') else list(bbox)
                                }
                                
                                # Create foot reference frame info
                                foot_reference_frame = None
                                if foot_bbox is not None:
                                    foot_reference_frame = {
                                        "video_path": self.video_path,
                                        "frame_num": self.current_frame_num,
                                        "bbox": foot_bbox
                                    }
                                
                                # Update or add player to gallery
                                player_id = player_name.lower().replace(" ", "_")
                                if player_id in self.player_gallery.players:
                                    # Update existing player with new features (both upper and foot)
                                    self.player_gallery.update_player(
                                        player_id=player_id,
                                        features=feature_vector,
                                        reference_frame=reference_frame,
                                        jersey_number=jersey_number if jersey_number else None,
                                        team=team if team else None,
                                        foot_features=foot_feature_vector,
                                        foot_reference_frame=foot_reference_frame
                                    )
                                else:
                                    # Add new player to gallery
                                    self.player_gallery.add_player(
                                        name=player_name,
                                        features=feature_vector,
                                        reference_frame=reference_frame,
                                        jersey_number=jersey_number if jersey_number else None,
                                        team=team if team else None
                                    )
                                    # Also add foot features if available
                                    if foot_feature_vector is not None and foot_reference_frame is not None:
                                        self.player_gallery.update_player(
                                            player_id=player_id,
                                            foot_features=foot_feature_vector,
                                            foot_reference_frame=foot_reference_frame
                                        )
                                
                                if foot_feature_vector is not None:
                                    print(f"✓ Saved Re-ID features (upper + foot) for '{player_name}' to player gallery")
                                else:
                                    print(f"✓ Saved Re-ID features for '{player_name}' to player gallery")
                            except Exception as e:
                                print(f"⚠ Could not save to player gallery: {e}")
                                import traceback
                                traceback.print_exc()
                except Exception as e:
                    # Re-ID extraction failed, continue without it
                    print(f"⚠ Re-ID extraction failed: {e}")
        
        # ANCHOR FRAME: Save this as an anchor frame with 1.00 confidence
        # Get bounding box for this detection
        bbox = None
        if self.current_detections is not None and self.selected_detection is not None:
            if self.selected_detection < len(self.current_detections.xyxy):
                bbox = self.current_detections.xyxy[self.selected_detection].tolist()
        
        # Create anchor frame entry (now includes jersey number)
        anchor_entry = {
            "track_id": int(track_id),
            "player_name": player_name,
            "team": team,
            "jersey_number": jersey_number,
            "bbox": bbox,
            "confidence": 1.00
        }
        
        # Add to anchor_frames dictionary
        if self.current_frame_num not in self.anchor_frames:
            self.anchor_frames[self.current_frame_num] = []
        self.anchor_frames[self.current_frame_num].append(anchor_entry)
        
        # Log anchor frame creation
        total_anchors = sum(len(anchors) for anchors in self.anchor_frames.values())
        print(f"🎯 Created anchor frame: Frame {self.current_frame_num}, Track #{track_id} = '{player_name}' (total: {total_anchors} anchor frames)")
        
        # Update roster with player info (including jersey number)
        if player_name not in self.player_roster:
            self.player_roster[player_name] = {
                "team": team,
                "jersey_number": jersey_number,
                "active": True,
                "first_seen_frame": self.current_frame_num,
                "last_seen_frame": self.current_frame_num
            }
        else:
            # Update existing roster entry
            self.player_roster[player_name]["team"] = team
            self.player_roster[player_name]["jersey_number"] = jersey_number
            self.player_roster[player_name]["last_seen_frame"] = self.current_frame_num
            if not self.player_roster[player_name]["active"]:
                self.player_roster[player_name]["active"] = True
        
        # Also save to player_names.json and roster file
        self.save_player_names()
        
        self.update_display()
        self.update_detections_list()
        self.update_summary()
        
        # 🚀 AUTO-TAG ALL INSTANCES: Automatically tag all other appearances of this track ID
        # This saves many clicks and makes tagging much faster!
        # NOTE: This creates player_mappings (approved_mappings) for all instances, but only creates
        # anchor frames at strategic intervals to avoid creating thousands of anchor frames
        instances_tagged = self.auto_tag_all_instances_of_id(track_id, player_name, team, jersey_number, 
                                                               create_anchor_frames=False, silent=True)
        
        # Show result message
        if instances_tagged > 0:
            messagebox.showinfo(
                "Tagged", 
                f"✓ Player ID #{track_id} tagged as: {player_name}\n\n"
                f"🚀 Auto-tagged {instances_tagged} additional instance(s) across all frames!"
            )
        else:
            messagebox.showinfo("Tagged", f"✓ Player ID #{track_id} tagged as: {player_name}")
    
    def extract_reid_features_for_frame(self, frame, detections=None, frame_num=None):
        """
        Extract Re-ID features for all detections in the current frame.
        Stores features for later matching with gallery players.
        Extracts both upper body features and foot features.
        
        Args:
            frame: Video frame
            detections: Optional Detections object (if None, uses self.current_detections)
            frame_num: Optional frame number (if None, uses self.current_frame_num)
        """
        # Use provided detections or fall back to current_detections
        detections_to_use = detections if detections is not None else self.current_detections
        frame_num_to_use = frame_num if frame_num is not None else self.current_frame_num
        
        if detections_to_use is None or len(detections_to_use) == 0:
            return
        
        if self.reid_tracker is None:
            return
        
        try:
            # CRITICAL: Filter detections before Re-ID extraction (if filter module is available)
            # This ensures only high-quality detections are used for matching
            detections_to_process = detections_to_use
            if (self.reid_tracker is not None and 
                hasattr(self.reid_tracker, 'filter_module') and 
                self.reid_tracker.filter_module is not None and
                self.current_detections is not None and len(self.current_detections) > 0):
                try:
                    # Use filter_detections_batch for batch processing (handles Detections objects)
                    # Returns (filtered_bboxes, quality_mask) where quality_mask is boolean array
                    filtered_bboxes, quality_mask = self.reid_tracker.filter_module.filter_detections_batch(
                        frame, detections_to_use
                    )
                    # Apply quality mask to filter the original Detections object
                    if quality_mask is not None and len(quality_mask) > 0 and np.any(quality_mask):
                        # Use supervision's boolean indexing to filter Detections object
                        detections_to_process = detections_to_use[quality_mask]
                    elif quality_mask is not None and len(quality_mask) > 0 and not np.any(quality_mask):
                        # All detections were filtered out - create empty Detections
                        import supervision as sv
                        detections_to_process = sv.Detections.empty()
                except Exception as e:
                    # If filtering fails, use original detections
                    detections_to_process = detections_to_use
            
            # Extract Re-ID features for all detections (upper body)
            # Note: extract_features already uses filter_module internally, but we also filter here
            # to ensure consistency and avoid processing low-quality detections
            reid_features = self.reid_tracker.extract_features(
                frame, detections_to_process, None, None
            )
            
            # Extract foot features for all detections (lower body - shoes)
            # Use filtered detections for consistency
            foot_features = None
            try:
                foot_features = self.reid_tracker.extract_foot_features(
                    frame, detections_to_process
                )
            except Exception as e:
                print(f"⚠ Could not extract foot features for frame {self.current_frame_num}: {e}")
            
            # Store features indexed by track_id for quick lookup
            if frame_num_to_use not in self.frame_reid_features:
                self.frame_reid_features[frame_num_to_use] = {}
            if frame_num_to_use not in self.frame_foot_features:
                self.frame_foot_features[frame_num_to_use] = {}
            
            # Map features to track IDs
            # CRITICAL: Use detections_to_process (filtered) for mapping, not original detections
            if reid_features is not None and len(reid_features) > 0:
                # Map features to track IDs from filtered detections
                if detections_to_process.tracker_id is not None:
                    for i, track_id in enumerate(detections_to_process.tracker_id):
                        if track_id is not None and i < len(reid_features):
                            feature = reid_features[i]
                            # Ensure feature is 1D (flatten if needed)
                            if isinstance(feature, np.ndarray) and len(feature.shape) > 1:
                                feature = feature.flatten()
                            elif not isinstance(feature, np.ndarray):
                                feature = np.array(feature).flatten()
                            self.frame_reid_features[frame_num_to_use][track_id] = feature
            
            # Map foot features to track IDs
            # CRITICAL: Use detections_to_process (filtered) for mapping, not original detections
            if foot_features is not None and len(foot_features) > 0:
                # Map foot features to track IDs from filtered detections
                if detections_to_process.tracker_id is not None:
                    for i, track_id in enumerate(detections_to_process.tracker_id):
                        if track_id is not None and i < len(foot_features):
                            foot_feature = foot_features[i]
                            # Ensure foot feature is 1D (flatten if needed)
                            if isinstance(foot_feature, np.ndarray) and len(foot_feature.shape) > 1:
                                foot_feature = foot_feature.flatten()
                            elif not isinstance(foot_feature, np.ndarray):
                                foot_feature = np.array(foot_feature).flatten()
                            self.frame_foot_features[frame_num_to_use][track_id] = foot_feature
        except Exception as e:
            # Re-ID extraction failed, continue without it
            print(f"⚠ Could not extract Re-ID features for frame {frame_num_to_use}: {e}")
            import traceback
            traceback.print_exc()
    
    def match_detections_to_gallery(self, frame):
        """
        Match current frame detections to players in the gallery using Re-ID features.
        Auto-suggests player names for untagged detections based on gallery matches.
        """
        if self.current_detections is None or len(self.current_detections) == 0:
            return
        
        if self.player_gallery is None or len(self.player_gallery.players) == 0:
            return
        
        if self.reid_tracker is None:
            return
        
        # Get Re-ID features for this frame
        frame_features = self.frame_reid_features.get(self.current_frame_num, {})
        if not frame_features:
            return
        
        import numpy as np
        
        # Match each untagged detection to gallery players
        for i, track_id in enumerate(self.current_detections.tracker_id):
            if track_id is None or track_id in self.rejected_ids:
                continue
            
            # Skip if already tagged (including from anchor frames)
            tid_str = str(int(track_id))
            if tid_str in self.approved_mappings:
                # Already mapped - skip Re-ID matching to avoid overwriting anchor frame data
                continue
            
            # Get Re-ID features for this detection (upper body)
            if track_id not in frame_features:
                continue
            
            detection_features = frame_features[track_id]
            if detection_features is None:
                continue
            
            # Convert to numpy array if needed and ensure correct shape
            if not isinstance(detection_features, np.ndarray):
                detection_features = np.array(detection_features)
            
            # Ensure features are 1D (flatten if needed)
            if len(detection_features.shape) > 1:
                detection_features = detection_features.flatten()
            
            # Normalize features
            detection_features_norm = detection_features / (np.linalg.norm(detection_features) + 1e-8)
            
            # Also try to get foot features for this detection
            detection_foot_features = None
            detection_foot_features_norm = None
            if hasattr(self, 'frame_foot_features') and self.current_frame_num in self.frame_foot_features:
                if track_id in self.frame_foot_features[self.current_frame_num]:
                    detection_foot_features = self.frame_foot_features[self.current_frame_num][track_id]
                    if detection_foot_features is not None:
                        if not isinstance(detection_foot_features, np.ndarray):
                            detection_foot_features = np.array(detection_foot_features)
                        # Ensure foot features are 1D (flatten if needed)
                        if len(detection_foot_features.shape) > 1:
                            detection_foot_features = detection_foot_features.flatten()
                        detection_foot_features_norm = detection_foot_features / (np.linalg.norm(detection_foot_features) + 1e-8)
            
            # Try to detect jersey number using OCR for better matching
            detected_jersey = None
            if self.jersey_ocr is not None and i < len(self.current_detections.xyxy):
                try:
                    bbox = self.current_detections.xyxy[i]
                    x1, y1, x2, y2 = map(int, bbox)
                    # Extract jersey region (upper 40% of bounding box)
                    jersey_y1 = int(y1)
                    jersey_y2 = int(y1 + (y2 - y1) * 0.40)
                    jersey_bbox = [x1, jersey_y1, x2, jersey_y2]
                    
                    ocr_result = self.jersey_ocr.detect_jersey_number(frame, jersey_bbox)
                    if ocr_result and ocr_result.get('jersey_number'):
                        detected_jersey = str(ocr_result['jersey_number'])
                except Exception as e:
                    pass  # OCR failed, continue without jersey number
            
            # Use player_gallery.match_player() with advanced features instead of manual calculation
            # This uses multi-feature ensemble matching, hard negative mining, and adaptive thresholds
            try:
                # Get dominant color and team if available (for better matching)
                dominant_color = None
                detection_team = None
                # Try to classify team from jersey color if team colors are available
                if hasattr(self, 'team_colors') and self.team_colors and i < len(self.current_detections.xyxy):
                    try:
                        bbox = self.current_detections.xyxy[i]
                        # Simple team classification based on jersey region color
                        # (This is a simplified version - full implementation would use team_color_detector)
                        pass  # Team classification can be added later
                    except:
                        pass
                
                # Call match_player with all advanced features
                # CRITICAL: Pass filter_module from Re-ID tracker for quality validation
                filter_module = None
                if self.reid_tracker is not None and hasattr(self.reid_tracker, 'filter_module'):
                    filter_module = self.reid_tracker.filter_module
                
                all_matches = self.player_gallery.match_player(
                    features=detection_features,
                    similarity_threshold=0.0,  # Get all matches
                    dominant_color=dominant_color,
                    team=detection_team,
                    jersey_number=detected_jersey,  # Use detected jersey number for search/boost
                    return_all=True,  # Return all similarities
                    foot_features=detection_foot_features if detection_foot_features is not None else None,
                    hard_negative_miner=self.hard_negative_miner,  # Use hard negative mining
                    filter_module=filter_module,  # Pass filter module for quality checks
                    track_id=int(track_id)  # Pass track ID for hard negative mining
                )
                
                # Find best match from results (filtering out inactive players)
                if all_matches and len(all_matches) > 0:
                    # all_matches is list of (player_id, player_name, similarity) tuples
                    # Filter to only active players
                    active_matches = []
                    for match in all_matches:
                        player_id, player_name, similarity = match
                        # CRITICAL: Only consider active players from roster
                        if self.is_player_active(player_name):
                            active_matches.append(match)
                    
                    if active_matches:
                        # Sort by similarity (highest first)
                        active_matches_sorted = sorted(active_matches, key=lambda x: x[2], reverse=True)
                        best_match = active_matches_sorted[0]
                        best_match_player_id = best_match[0]
                        best_match_similarity = best_match[2]
                        best_match_score = best_match_similarity
                    else:
                        # No active players matched
                        best_match_player_id = None
                        best_match_score = 0.0
                        best_match_similarity = 0.0
                else:
                    best_match_player_id = None
                    best_match_score = 0.0
                    best_match_similarity = 0.0
            except Exception as e:
                # Fallback to manual calculation if match_player fails
                print(f"⚠ Advanced gallery matching failed, using fallback: {e}")
                best_match_player_id = None
                best_match_score = 0.0
                best_match_similarity = 0.0
                
                # Manual fallback calculation (simplified)
                for player_id, profile in self.player_gallery.players.items():
                    # CRITICAL: Skip inactive players from roster
                    if not self.is_player_active(profile.name):
                        continue
                    
                    if profile.features is None:
                        continue
                    
                    gallery_features = np.array(profile.features)
                    if len(gallery_features) == 0:
                        continue
                    
                    if len(gallery_features.shape) > 1:
                        gallery_features = gallery_features.flatten()
                    
                    gallery_features_norm = gallery_features / (np.linalg.norm(gallery_features) + 1e-8)
                    
                    if len(detection_features_norm.shape) > 1:
                        detection_features_norm = detection_features_norm.flatten()
                    if len(gallery_features_norm.shape) > 1:
                        gallery_features_norm = gallery_features_norm.flatten()
                    
                    similarity = np.dot(detection_features_norm, gallery_features_norm)
                    similarity = float(similarity)
                    
                    if similarity > best_match_similarity and similarity >= self.reid_suggestion_threshold:
                        best_match_similarity = similarity
                        best_match_score = similarity
                        best_match_player_id = player_id
            
            # If we found a good match, auto-suggest the player name
            if best_match_player_id is not None and best_match_score >= self.reid_suggestion_threshold:
                matched_profile = self.player_gallery.players[best_match_player_id]
                player_name = matched_profile.name
                
                # CRITICAL: Check if this track ID is already mapped to a protected player
                # Don't auto-tag if it would overwrite a recently manually tagged player
                can_auto_tag = True
                if tid_str in self.approved_mappings:
                    existing_mapping = self.approved_mappings[tid_str]
                    if isinstance(existing_mapping, tuple):
                        existing_player = existing_mapping[0]
                        # Check if existing player is protected
                        if existing_player in self.player_tag_protection:
                            last_tagged_frame, _ = self.player_tag_protection[existing_player]
                            frames_since_tag = self.current_frame_num - last_tagged_frame
                            if frames_since_tag <= self.tag_protection_frames:
                                # Existing player is protected - don't auto-tag over them
                                can_auto_tag = False
                                print(f"⚠ Gallery match '{player_name}' blocked - Track #{track_id} is protected for '{existing_player}' (tagged {frames_since_tag} frames ago)")
                
                # Auto-tag if confidence is above auto-tag threshold AND not blocked
                if can_auto_tag and best_match_score >= self.reid_auto_tag_threshold:
                    # High confidence match - auto-tag
                    team = matched_profile.team if matched_profile.team else ""
                    jersey_number = matched_profile.jersey_number if matched_profile.jersey_number else ""
                    self.approved_mappings[tid_str] = (player_name, team, jersey_number)
                    
                    # Store position for tracking
                    if i < len(self.current_detections.xyxy):
                        bbox = self.current_detections.xyxy[i]
                        center_x = (bbox[0] + bbox[2]) / 2.0
                        center_y = (bbox[1] + bbox[3]) / 2.0
                        if player_name not in self.player_positions:
                            self.player_positions[player_name] = []
                        self.player_positions[player_name].append((self.current_frame_num, center_x, center_y, int(track_id)))
                        if len(self.player_positions[player_name]) > 10:
                            self.player_positions[player_name] = self.player_positions[player_name][-10:]
                    
                    print(f"✓ Auto-tagged Track #{track_id} as '{player_name}' (gallery match: {best_match_score:.2f})")
                else:
                    # Medium confidence - suggest but don't auto-tag
                    # Store suggestion for UI display
                    if not hasattr(self, 'gallery_suggestions'):
                        self.gallery_suggestions = {}  # track_id -> (player_name, confidence)
                    self.gallery_suggestions[track_id] = (player_name, best_match_score)
                    print(f"💡 Gallery suggests Track #{track_id} → '{player_name}' (confidence: {best_match_score:.2f})")
    
    def match_players_with_reid(self, frame):
        """
        Use Re-ID and position-based matching to maintain player identity when track IDs change.
        This helps ensure that players tagged in previous frames are correctly identified even
        when ByteTrack reassigns track IDs.
        Enhanced to also use player gallery features for better matching.
        """
        if self.current_detections is None or len(self.current_detections) == 0:
            return
        
        import numpy as np
        
        # For each tagged player, try to find them in current frame
        for player_name, positions in self.player_positions.items():
            if not positions:
                continue
            
            # Get most recent position (within last 5 frames)
            recent_positions = [p for p in positions if abs(p[0] - self.current_frame_num) <= 5]
            if not recent_positions:
                continue
            
            # Get last known position and track ID
            last_frame, last_x, last_y, last_track_id = recent_positions[-1]
            
            # CRITICAL: Check if this player was recently manually tagged (within protection window)
            # If so, prioritize maintaining their identity even if track ID changed
            is_protected = False
            if player_name in self.player_tag_protection:
                last_tagged_frame, last_tagged_tid = self.player_tag_protection[player_name]
                frames_since_tag = self.current_frame_num - last_tagged_frame
                
                # If tagged very recently (within protection window), protect their identity
                if frames_since_tag <= self.tag_protection_frames:
                    is_protected = True
                    # Check if the last tagged track ID still exists in current frame
                    if self.current_detections.tracker_id is not None:
                        for tid in self.current_detections.tracker_id:
                            if tid is not None and int(tid) == last_tagged_tid:
                                # Same track ID still exists - keep the mapping
                                tid_str = str(int(tid))
                                if tid_str not in self.approved_mappings:
                                    # Restore the mapping if it was lost
                                    for pid, mapping in list(self.approved_mappings.items()):
                                        if isinstance(mapping, tuple) and mapping[0] == player_name:
                                            self.approved_mappings[tid_str] = mapping
                                            print(f"✓ Restored protected player '{player_name}' to Track #{last_tagged_tid} (frame {self.current_frame_num})")
                                            break
                                continue  # Skip rematching - player is protected
            
            # Check if this player is already mapped to a track ID in current frame
            already_mapped = False
            for pid_str, mapping in self.approved_mappings.items():
                if isinstance(mapping, tuple) and mapping[0] == player_name:
                    # Check if this track ID exists in current frame
                    if self.current_detections.tracker_id is not None:
                        for tid in self.current_detections.tracker_id:
                            if tid is not None and str(int(tid)) == pid_str:
                                already_mapped = True
                                break
                    if already_mapped:
                        break
            
            if already_mapped:
                continue  # Player already correctly mapped
            
            # Find best matching detection in current frame
            best_match_idx = None
            best_match_score = 0.0
            best_match_tid = None
            
            for i, (xyxy, track_id) in enumerate(zip(
                self.current_detections.xyxy,
                self.current_detections.tracker_id
            )):
                if track_id is None or track_id in self.rejected_ids:
                    continue
                
                # Skip if this track ID is already mapped to a different player
                tid_str = str(int(track_id))
                if tid_str in self.approved_mappings:
                    existing_mapping = self.approved_mappings[tid_str]
                    if isinstance(existing_mapping, tuple) and existing_mapping[0] != player_name:
                        # CRITICAL: Check if the existing player is protected (recently tagged)
                        existing_player = existing_mapping[0]
                        if existing_player in self.player_tag_protection:
                            last_tagged_frame, _ = self.player_tag_protection[existing_player]
                            frames_since_tag = self.current_frame_num - last_tagged_frame
                            # If existing player was tagged recently, don't overwrite them
                            if frames_since_tag <= self.tag_protection_frames:
                                continue  # Protected player - don't overwrite
                        # If not protected, allow overwrite but require higher confidence
                        # (fall through to matching logic, but with higher threshold)
                
                # Calculate position-based score
                center_x = (xyxy[0] + xyxy[2]) / 2.0
                center_y = (xyxy[1] + xyxy[3]) / 2.0
                
                # Distance from last known position
                distance = np.sqrt((center_x - last_x)**2 + (center_y - last_y)**2)
                
                # Position score (closer = better, max distance ~500 pixels)
                position_score = max(0.0, 1.0 - (distance / 500.0))
                
                # Re-ID score (if available) - compare with stored features AND gallery
                reid_score = 0.0
                
                # First, try to get Re-ID features from current frame (already extracted)
                current_feature = None
                if hasattr(self, 'frame_reid_features'):
                    frame_features = self.frame_reid_features.get(self.current_frame_num, {})
                    if track_id in frame_features:
                        current_feature = frame_features[track_id]
                        if not isinstance(current_feature, np.ndarray):
                            current_feature = np.array(current_feature)
                
                # If not available, extract on demand
                if current_feature is None and self.reid_tracker is not None and frame is not None:
                    try:
                        single_detection = sv.Detections(
                            xyxy=np.array([xyxy]),
                            confidence=np.array([1.0]),
                            tracker_id=np.array([track_id])
                        )
                        current_features = self.reid_tracker.extract_features(
                            frame, single_detection, None, None
                        )
                        if current_features is not None and len(current_features) > 0:
                            current_feature = current_features[0] if hasattr(current_features, '__getitem__') else current_features
                            if not isinstance(current_feature, np.ndarray):
                                current_feature = np.array(current_feature)
                            # Ensure feature is 1D (flatten if needed)
                            if len(current_feature.shape) > 1:
                                current_feature = current_feature.flatten()
                    except Exception:
                        pass
                
                # Compare with stored Re-ID features (session-based)
                if current_feature is not None and player_name in self.player_reid_features:
                    try:
                        stored_features = self.player_reid_features[player_name]
                        if stored_features:
                            _, stored_feature = stored_features[-1]
                            if not isinstance(stored_feature, np.ndarray):
                                stored_feature = np.array(stored_feature)
                            # Ensure stored feature is 1D (flatten if needed)
                            if len(stored_feature.shape) > 1:
                                stored_feature = stored_feature.flatten()
                            
                            # Normalize and calculate cosine similarity
                            stored_norm = stored_feature / (np.linalg.norm(stored_feature) + 1e-8)
                            current_norm = current_feature / (np.linalg.norm(current_feature) + 1e-8)
                            # Ensure both are 1D for dot product
                            if len(stored_norm.shape) > 1:
                                stored_norm = stored_norm.flatten()
                            if len(current_norm.shape) > 1:
                                current_norm = current_norm.flatten()
                            similarity = np.dot(stored_norm, current_norm)
                            reid_score = max(reid_score, float(similarity))
                    except Exception:
                        pass
                
                # Also compare with player gallery features (cross-video matching)
                if current_feature is not None and self.player_gallery is not None:
                    try:
                        # Find player in gallery
                        player_id = player_name.lower().replace(" ", "_")
                        if player_id in self.player_gallery.players:
                            profile = self.player_gallery.players[player_id]
                            if profile.features is not None:
                                gallery_features = np.array(profile.features)
                                if len(gallery_features) > 0:
                                    # Ensure gallery features are 1D (flatten if needed)
                                    if len(gallery_features.shape) > 1:
                                        gallery_features = gallery_features.flatten()
                                    gallery_norm = gallery_features / (np.linalg.norm(gallery_features) + 1e-8)
                                    current_norm = current_feature / (np.linalg.norm(current_feature) + 1e-8)
                                    # Ensure both are 1D for dot product
                                    if len(gallery_norm.shape) > 1:
                                        gallery_norm = gallery_norm.flatten()
                                    if len(current_norm.shape) > 1:
                                        current_norm = current_norm.flatten()
                                    similarity = np.dot(gallery_norm, current_norm)
                                    # Use gallery match if it's better
                                    reid_score = max(reid_score, float(similarity))
                    except Exception:
                        pass
                
                # Combined score (position weighted more heavily for nearby frames)
                frame_delta = abs(self.current_frame_num - last_frame)
                if frame_delta <= 2:
                    # Very recent: position is most important
                    combined_score = 0.8 * position_score + 0.2 * reid_score
                else:
                    # Further away: Re-ID becomes more important
                    combined_score = 0.5 * position_score + 0.5 * reid_score
                
                # CRITICAL: Use higher threshold if track ID is already mapped to a different player
                # This prevents overwriting existing mappings unless match is very strong
                threshold = 0.6  # Default threshold
                if tid_str in self.approved_mappings:
                    existing_mapping = self.approved_mappings[tid_str]
                    if isinstance(existing_mapping, tuple) and existing_mapping[0] != player_name:
                        # Track ID already mapped to different player - require higher confidence
                        threshold = 0.75  # Higher threshold to prevent false overwrites
                
                # CRITICAL: If player is protected (recently tagged), require even higher confidence
                if is_protected:
                    # Protected player - only match if very confident (0.85+)
                    threshold = 0.85
                
                if combined_score > best_match_score and combined_score > threshold:
                    best_match_score = combined_score
                    best_match_idx = i
                    best_match_tid = track_id
            
            # If we found a good match, assign the player to that track ID
            if best_match_idx is not None and best_match_tid is not None:
                tid_str = str(int(best_match_tid))
                
                # CRITICAL: Check if this track ID is already mapped to a different protected player
                should_assign = True
                if tid_str in self.approved_mappings:
                    existing_mapping = self.approved_mappings[tid_str]
                    if isinstance(existing_mapping, tuple) and existing_mapping[0] != player_name:
                        existing_player = existing_mapping[0]
                        # Check if existing player is protected
                        if existing_player in self.player_tag_protection:
                            last_tagged_frame, _ = self.player_tag_protection[existing_player]
                            frames_since_tag = self.current_frame_num - last_tagged_frame
                            if frames_since_tag <= self.tag_protection_frames:
                                # Existing player is protected - don't overwrite
                                should_assign = False
                                print(f"⚠ Protected player '{existing_player}' on Track #{best_match_tid} - not overwriting with '{player_name}' (match score: {best_match_score:.2f})")
                
                if should_assign:
                    # Get player info from approved_mappings (find by player_name)
                    player_info = None
                    for pid, mapping in self.approved_mappings.items():
                        if isinstance(mapping, tuple) and mapping[0] == player_name:
                            player_info = mapping
                            break
                    
                    if player_info:
                        # Update mapping to new track ID
                        self.approved_mappings[tid_str] = player_info
                        # Update position history
                        bbox = self.current_detections.xyxy[best_match_idx]
                        center_x = (bbox[0] + bbox[2]) / 2.0
                        center_y = (bbox[1] + bbox[3]) / 2.0
                        self.player_positions[player_name].append((self.current_frame_num, center_x, center_y, int(best_match_tid)))
                        # Keep only last 10 positions
                        if len(self.player_positions[player_name]) > 10:
                            self.player_positions[player_name] = self.player_positions[player_name][-10:]
                        
                        print(f"✓ Matched '{player_name}' to Track #{best_match_tid} (score: {best_match_score:.2f}, frame {self.current_frame_num})")
    
    def find_nearby_frames_with_same_id(self, track_id):
        """Find frames near current frame that contain the same track ID"""
        if not self.detections_history:
            return []
        
        nearby_frames = []
        # Check ±10 frames around current
        for offset in range(-10, 11):
            if offset == 0:
                continue
            frame_num = self.current_frame_num + offset
            if 0 <= frame_num < self.total_frames and frame_num in self.detections_history:
                detections = self.detections_history[frame_num]
                for tid in detections.tracker_id:
                    if tid is None:
                        continue
                    tid = self.merged_ids.get(tid, tid)
                    if tid == track_id:
                        # Check if untagged
                        pid_str = str(int(tid))
                        if pid_str not in self.approved_mappings:
                            nearby_frames.append(frame_num)
                        break
        
        return nearby_frames
    
    def auto_tag_all_instances_of_id(self, track_id, player_name, team, jersey_number, 
                                      create_anchor_frames=False, anchor_frame_interval=150, silent=False):
        """
        Automatically tag all instances of a track ID across all frames.
        
        Args:
            track_id: Track ID to tag
            player_name: Player name
            team: Team name
            jersey_number: Jersey number
            create_anchor_frames: If True, creates anchor frames (default: False to avoid thousands)
            anchor_frame_interval: If creating anchor frames, only create every N frames (default: 150)
            silent: If True, don't show messages
        """
        if not self.detections_history:
            return 0
        
        instances_tagged = 0
        frames_with_anchors = []
        last_anchor_frame = -anchor_frame_interval  # Track last anchor frame created
        
        # Iterate through all frames
        for frame_num, detections in self.detections_history.items():
            if frame_num == self.current_frame_num:
                continue  # Skip current frame (already tagged)
            
            # Check if this frame has the track ID
            for i, tid in enumerate(detections.tracker_id):
                if tid is None or tid in self.rejected_ids:
                    continue
                
                # Check both original and merged IDs
                actual_tid = self.merged_ids.get(tid, tid)
                if actual_tid == track_id:
                    # Tag this instance (always create player_mapping)
                    pid_str = str(int(actual_tid))
                    
                    # Only tag if not already tagged with same info
                    if pid_str not in self.approved_mappings or self.approved_mappings[pid_str] != (player_name, team, jersey_number):
                        self.approved_mappings[pid_str] = (player_name, team, jersey_number)
                        instances_tagged += 1
                        
                        # Only create anchor frames if requested AND at strategic intervals
                        # This prevents creating thousands of anchor frames while still providing protection
                        should_create_anchor = (create_anchor_frames and 
                                               (frame_num - last_anchor_frame) >= anchor_frame_interval)
                        
                        if should_create_anchor:
                            bbox = None
                            if i < len(detections.xyxy):
                                bbox = detections.xyxy[i].tolist()
                            
                            anchor_entry = {
                                "track_id": int(actual_tid),
                                "player_name": player_name,
                                "team": team,
                                "jersey_number": jersey_number,
                                "bbox": bbox,
                                "confidence": 1.00
                            }
                            
                            # Add to anchor_frames
                            if frame_num not in self.anchor_frames:
                                self.anchor_frames[frame_num] = []
                            
                            # Check if already exists
                            exists = False
                            for existing_anchor in self.anchor_frames[frame_num]:
                                if existing_anchor["track_id"] == int(actual_tid):
                                    # Update existing
                                    existing_anchor.update(anchor_entry)
                                    exists = True
                                    break
                            
                            if not exists:
                                self.anchor_frames[frame_num].append(anchor_entry)
                                last_anchor_frame = frame_num
                                frames_with_anchors.append(frame_num)
                    break  # Only one instance per frame
        
        # Save if we tagged any instances
        if instances_tagged > 0:
            self.save_player_names()
            if not silent:
                self.update_display()
                self.update_detections_list()
                self.update_summary()
        
        return instances_tagged
    
    def smart_roster_auto_match(self):
        """Intelligently auto-match and apply remaining roster players to untagged tracks"""
        if not self.detections_history:
            messagebox.showinfo("No Detections", "Please initialize detection first")
            return
        
        # Get roster players grouped by team
        roster_by_team = {}  # team -> [player_names]
        all_roster_players = []
        
        if self.player_roster:
            for player_name, player_info in self.player_roster.items():
                team = player_info.get('team', 'Unknown')
                if team not in roster_by_team:
                    roster_by_team[team] = []
                roster_by_team[team].append(player_name)
                all_roster_players.append(player_name)
        else:
            all_roster_players = self.player_name_list
        
        if not all_roster_players:
            messagebox.showinfo("No Roster", "No players in roster. Use 'Manage Names' to add players first.")
            return
        
        # Find which roster players are already assigned
        assigned_players = set()
        assigned_by_team = {}  # team -> {track_id: player_name}
        
        for pid_str, mapping in self.approved_mappings.items():
            if isinstance(mapping, tuple) and len(mapping) >= 2:
                player_name = mapping[0]
                team = mapping[1]
                assigned_players.add(player_name)
                
                if team:
                    if team not in assigned_by_team:
                        assigned_by_team[team] = {}
                    try:
                        track_id = int(pid_str)
                        assigned_by_team[team][track_id] = player_name
                    except (ValueError, TypeError):
                        pass
        
        # Find unassigned roster players by team
        unassigned_by_team = {}  # team -> [player_names]
        for team, players in roster_by_team.items():
            unassigned = [p for p in players if p not in assigned_players]
            if unassigned:
                unassigned_by_team[team] = unassigned
        
        # Also handle players not in roster (fallback)
        unassigned_players = [p for p in all_roster_players if p not in assigned_players]
        
        if not unassigned_players:
            messagebox.showinfo("All Assigned", 
                              f"✓ All {len(all_roster_players)} roster players already assigned!")
            return
        
        # Find all untagged track IDs with their spatial clustering info
        untagged_tracks = {}  # track_id -> {frames: [frame_nums], team_hint: str, avg_position: (x,y)}
        
        for frame_num, detections in self.detections_history.items():
            for idx, tid in enumerate(detections.tracker_id):
                if tid is None or tid in self.rejected_ids:
                    continue
                tid = self.merged_ids.get(tid, tid)
                pid_str = str(int(tid))
                
                if pid_str not in self.approved_mappings:
                    # Untagged track
                    if int(tid) not in untagged_tracks:
                        untagged_tracks[int(tid)] = {
                            'frames': [],
                            'positions': [],
                            'team_hint': None
                        }
                    untagged_tracks[int(tid)]['frames'].append(frame_num)
                    
                    # Store position for spatial clustering
                    try:
                        if hasattr(detections, 'xyxy') and len(detections.xyxy) > idx:
                            bbox = detections.xyxy[idx]
                            center_x = (bbox[0] + bbox[2]) / 2
                            center_y = (bbox[1] + bbox[3]) / 2
                            untagged_tracks[int(tid)]['positions'].append((center_x, center_y))
                    except:
                        pass
        
        if not untagged_tracks:
            messagebox.showinfo("All Tagged", 
                              f"All tracks are already tagged!\n\n"
                              f"Unassigned roster players ({len(unassigned_players)}):\n" +
                              "\n".join(f"• {p}" for p in unassigned_players[:5]) +
                              (f"\n... and {len(unassigned_players)-5} more" if len(unassigned_players) > 5 else ""))
            return
        
        # Calculate average position for each untagged track
        for track_id, track_info in untagged_tracks.items():
            if track_info['positions']:
                avg_x = sum(p[0] for p in track_info['positions']) / len(track_info['positions'])
                avg_y = sum(p[1] for p in track_info['positions']) / len(track_info['positions'])
                track_info['avg_position'] = (avg_x, avg_y)
            else:
                track_info['avg_position'] = None
        
        # 🧠 SMART TEAM ASSIGNMENT: Use spatial proximity to already-tagged teammates
        # For each untagged track, find the closest tagged tracks and infer team
        tagged_track_positions = {}  # track_id -> (avg_position, team, player_name)
        
        for pid_str, mapping in self.approved_mappings.items():
            if isinstance(mapping, tuple) and len(mapping) >= 2:
                team = mapping[1]
                player_name = mapping[0]
                try:
                    track_id = int(pid_str)
                    # Find this track's average position
                    track_positions = []
                    for frame_num, detections in self.detections_history.items():
                        for idx, tid in enumerate(detections.tracker_id):
                            if tid == track_id or self.merged_ids.get(tid, tid) == track_id:
                                try:
                                    if hasattr(detections, 'xyxy') and len(detections.xyxy) > idx:
                                        bbox = detections.xyxy[idx]
                                        center_x = (bbox[0] + bbox[2]) / 2
                                        center_y = (bbox[1] + bbox[3]) / 2
                                        track_positions.append((center_x, center_y))
                                except:
                                    pass
                    
                    if track_positions:
                        avg_x = sum(p[0] for p in track_positions) / len(track_positions)
                        avg_y = sum(p[1] for p in track_positions) / len(track_positions)
                        tagged_track_positions[track_id] = ((avg_x, avg_y), team, player_name)
                except (ValueError, TypeError):
                    pass
        
        # Infer team for untagged tracks based on spatial proximity
        if tagged_track_positions:
            for track_id, track_info in untagged_tracks.items():
                if track_info['avg_position'] is None:
                    continue
                
                # Find closest tagged tracks
                distances = []
                for tagged_id, (tagged_pos, team, player_name) in tagged_track_positions.items():
                    dx = track_info['avg_position'][0] - tagged_pos[0]
                    dy = track_info['avg_position'][1] - tagged_pos[1]
                    distance = (dx**2 + dy**2) ** 0.5
                    distances.append((distance, team))
                
                if distances:
                    # Take the 3 closest tagged tracks and find most common team
                    distances.sort()
                    closest_teams = [team for dist, team in distances[:3]]
                    # Most common team
                    team_counts = {}
                    for t in closest_teams:
                        team_counts[t] = team_counts.get(t, 0) + 1
                    most_common_team = max(team_counts.items(), key=lambda x: x[1])[0]
                    track_info['team_hint'] = most_common_team
        
        # Sort untagged tracks by frequency (most frames = likely more important player)
        sorted_untagged = sorted(untagged_tracks.items(), 
                                key=lambda x: len(x[1]['frames']), 
                                reverse=True)
        
        # 🎯 SMART MATCHING: Match untagged tracks to unassigned roster players
        auto_matches = []  # [(track_id, player_name, team, jersey)]
        
        # Strategy 1: Match by team hint
        for team, unassigned in unassigned_by_team.items():
            team_untagged = [(tid, info) for tid, info in sorted_untagged 
                            if info['team_hint'] == team]
            
            for i, (track_id, track_info) in enumerate(team_untagged):
                if i < len(unassigned):
                    player_name = unassigned[i]
                    jersey = ""
                    if player_name in self.player_roster:
                        jersey = self.player_roster[player_name].get('jersey_number', '')
                    
                    auto_matches.append((track_id, player_name, team, jersey))
        
        # Strategy 2: Match remaining players to remaining tracks (by frequency)
        matched_tracks = set(m[0] for m in auto_matches)
        matched_players = set(m[1] for m in auto_matches)
        
        remaining_unassigned = [p for p in unassigned_players if p not in matched_players]
        remaining_untagged = [(tid, info) for tid, info in sorted_untagged if tid not in matched_tracks]
        
        for i, (track_id, track_info) in enumerate(remaining_untagged):
            if i < len(remaining_unassigned):
                player_name = remaining_unassigned[i]
                
                # Try to get team from roster
                team = ""
                jersey = ""
                if player_name in self.player_roster:
                    team = self.player_roster[player_name].get('team', '')
                    jersey = self.player_roster[player_name].get('jersey_number', '')
                
                # If no team in roster, use team hint from spatial analysis
                if not team and track_info['team_hint']:
                    team = track_info['team_hint']
                
                auto_matches.append((track_id, player_name, team, jersey))
        
        if not auto_matches:
            messagebox.showinfo("No Matches", 
                              "Could not find suitable matches.\n\n"
                              "Try tagging a few players manually first to establish team clustering.")
            return
        
        # Confirm with user before applying
        match_summary = "\n".join([f"Track #{tid} → {name} ({team})" 
                                  for tid, name, team, jersey in auto_matches[:10]])
        if len(auto_matches) > 10:
            match_summary += f"\n... and {len(auto_matches) - 10} more"
        
        response = messagebox.askyesno(
            "🎯 Auto-Match Ready",
            f"Found {len(auto_matches)} smart matches:\n\n{match_summary}\n\n"
            f"Apply these matches automatically?",
            icon='question'
        )
        
        if not response:
            return
        
        # Apply all matches (with team validation)
        applied_count = 0
        missing_teams = []
        for track_id, player_name, team, jersey in auto_matches:
            # CRITICAL: Require team assignment (except for coaches, referees, and "other" players)
            coach_names = {"Kevin Hill", "Coach", "coach"}
            is_coach = any(coach.lower() in player_name.lower() for coach in coach_names)
            is_referee = "referee" in player_name.lower() or "ref" in player_name.lower()
            is_other = player_name.lower() in ["other", "guest player", "guest", "unknown"]
            
            if not team and not (is_coach or is_referee or is_other):
                missing_teams.append(f"{player_name} (Track #{track_id})")
                continue  # Skip matches without teams
            
            pid_str = str(track_id)
            self.approved_mappings[pid_str] = (player_name, team, jersey)
            
            # Tag all instances across all frames
            self.auto_tag_all_instances_of_id(track_id, player_name, team, jersey, silent=True)
            applied_count += 1
        
        if missing_teams:
            messagebox.showwarning("Team Required", 
                f"The following players need team assignments before auto-matching:\n\n" +
                "\n".join(f"• {p}" for p in missing_teams[:10]) +
                (f"\n... and {len(missing_teams)-10} more" if len(missing_teams) > 10 else "") +
                "\n\nPlease tag these players manually with teams first, then try auto-matching again.")
            if applied_count > 0:
                # Still save what was applied
                self.save_player_names()
                self.update_display()
                self.update_detections_list()
                self.update_summary()
                messagebox.showinfo("Partial Success", 
                    f"Applied {applied_count} matches with teams.\n"
                    f"Skipped {len(missing_teams)} matches without teams.")
            return
        
        # Save and update
        self.save_player_names()
        self.update_display()
        self.update_detections_list()
        self.update_summary()
        
        messagebox.showinfo("Success", 
                          f"✓ Auto-matched and applied {applied_count} roster assignments!\n\n"
                          f"All instances of these tracks have been tagged.\n\n"
                          f"Review in the playback viewer to verify accuracy.")
    
    def smart_roster_match(self):
        """Smart matching of roster players to untagged track IDs"""
        if not self.detections_history:
            messagebox.showinfo("No Detections", "Please initialize detection first")
            return
        
        # Get list of players from roster
        roster_players = list(self.player_roster.keys()) if self.player_roster else self.player_name_list
        if not roster_players:
            messagebox.showinfo("No Roster", "No players in roster. Use 'Manage Names' to add players first.")
            return
        
        # Find which roster players are already assigned
        assigned_players = set()
        for pid_str, mapping in self.approved_mappings.items():
            if isinstance(mapping, tuple) and len(mapping) > 0:
                assigned_players.add(mapping[0])  # Player name
        
        # Find unassigned roster players
        unassigned_players = [p for p in roster_players if p not in assigned_players]
        
        if not unassigned_players:
            messagebox.showinfo("All Assigned", 
                              f"All {len(roster_players)} roster players are already assigned to tracks!\n\n"
                              "✓ Roster complete!")
            return
        
        # Find all untagged track IDs across all frames
        untagged_tracks = {}  # track_id -> [frame_nums where it appears]
        all_tracks = set()
        
        for frame_num, detections in self.detections_history.items():
            for tid in detections.tracker_id:
                if tid is None or tid in self.rejected_ids:
                    continue
                tid = self.merged_ids.get(tid, tid)
                pid_str = str(int(tid))
                all_tracks.add(int(tid))
                
                if pid_str not in self.approved_mappings:
                    # Untagged track
                    if int(tid) not in untagged_tracks:
                        untagged_tracks[int(tid)] = []
                    untagged_tracks[int(tid)].append(frame_num)
        
        if not untagged_tracks:
            messagebox.showinfo("All Tagged", 
                              f"All detected tracks are already tagged!\n\n"
                              f"Unassigned roster players ({len(unassigned_players)}):\n" +
                              "\n".join(f"• {p}" for p in unassigned_players[:5]) +
                              (f"\n... and {len(unassigned_players)-5} more" if len(unassigned_players) > 5 else ""))
            return
        
        # Sort untagged tracks by number of appearances (most frequent first)
        sorted_untagged = sorted(untagged_tracks.items(), key=lambda x: len(x[1]), reverse=True)
        
        # Create smart matching dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("🎯 Smart Roster Match")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.lift()
        
        # Header
        header_frame = ttk.Frame(dialog)
        header_frame.pack(fill=tk.X, padx=15, pady=10)
        
        ttk.Label(header_frame, text="Smart Roster Matching", 
                 font=("Arial", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(header_frame, 
                 text=f"📋 {len(unassigned_players)} unassigned roster players  •  "
                      f"🔍 {len(untagged_tracks)} untagged tracks  •  "
                      f"✓ {len(assigned_players)} already assigned",
                 foreground="gray", font=("Arial", 9)).pack(anchor=tk.W, pady=(5,0))
        
        ttk.Separator(dialog, orient="horizontal").pack(fill=tk.X, padx=10, pady=10)
        
        # Instructions
        ttk.Label(dialog, text="Match unassigned roster players to untagged tracks:",
                 font=("Arial", 10)).pack(anchor=tk.W, padx=15, pady=(0,10))
        
        # Scrollable frame for matches
        canvas_frame = ttk.Frame(dialog)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=15)
        
        canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create match rows
        match_vars = {}  # track_id -> (player_var, team_var, jersey_var, enabled_var)
        
        for i, (track_id, frame_list) in enumerate(sorted_untagged[:len(unassigned_players)]):
            row_frame = ttk.Frame(scrollable_frame)
            row_frame.pack(fill=tk.X, pady=5, padx=5)
            
            # Checkbox to enable/disable this match
            enabled_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(row_frame, variable=enabled_var).pack(side=tk.LEFT, padx=(0,5))
            
            # Track ID info
            ttk.Label(row_frame, text=f"Track #{track_id}:", 
                     font=("Arial", 10, "bold"), width=12).pack(side=tk.LEFT)
            ttk.Label(row_frame, text=f"({len(frame_list)} frames)", 
                     foreground="gray", font=("Arial", 8), width=12).pack(side=tk.LEFT)
            ttk.Label(row_frame, text="→", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
            
            # Player name dropdown (suggest next unassigned player)
            player_var = tk.StringVar(value=unassigned_players[i] if i < len(unassigned_players) else "")
            player_combo = ttk.Combobox(row_frame, textvariable=player_var,
                                       values=unassigned_players, width=20, state="readonly")
            player_combo.pack(side=tk.LEFT, padx=5)
            
            # Auto-fill team and jersey when player selected
            def on_player_select(event, pvar=player_var, track_id=track_id):
                player_name = pvar.get()
                if player_name in self.player_roster:
                    roster_entry = self.player_roster[player_name]
                    if track_id in match_vars:
                        _, team_var, jersey_var, _ = match_vars[track_id]
                        if roster_entry.get("team"):
                            team_var.set(roster_entry["team"])
                        if roster_entry.get("jersey_number"):
                            jersey_var.set(roster_entry["jersey_number"])
            
            player_combo.bind("<<ComboboxSelected>>", on_player_select)
            
            # Team dropdown (allows custom names like "Blue", "Gray", etc.)
            team_var = tk.StringVar(value="")
            team_names = self.get_team_names_from_config()
            # Allow typing custom team names (not readonly) - users can enter "Blue", "Gray", or any custom name
            team_combo = ttk.Combobox(row_frame, textvariable=team_var,
                                     values=team_names, width=12)
            team_combo.pack(side=tk.LEFT, padx=2)
            
            # Jersey number
            jersey_var = tk.StringVar(value="")
            jersey_entry = ttk.Entry(row_frame, textvariable=jersey_var, width=5)
            jersey_entry.pack(side=tk.LEFT, padx=2)
            
            # Auto-populate from roster if available
            if i < len(unassigned_players):
                player_name = unassigned_players[i]
                if player_name in self.player_roster:
                    roster_entry = self.player_roster[player_name]
                    if roster_entry.get("team"):
                        team_var.set(roster_entry["team"])
                    if roster_entry.get("jersey_number"):
                        jersey_var.set(roster_entry["jersey_number"])
            
            match_vars[track_id] = (player_var, team_var, jersey_var, enabled_var)
        
        # Show unmatched players if any remain
        if len(unassigned_players) > len(untagged_tracks):
            remaining = len(unassigned_players) - len(untagged_tracks)
            info_frame = ttk.Frame(scrollable_frame)
            info_frame.pack(fill=tk.X, pady=10, padx=5)
            ttk.Label(info_frame, 
                     text=f"⚠ {remaining} roster player(s) have no untagged tracks to match.\n"
                          f"They may appear later in the video.",
                     foreground="orange", font=("Arial", 9)).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=15, pady=15)
        
        def apply_matches():
            applied_count = 0
            for track_id, (player_var, team_var, jersey_var, enabled_var) in match_vars.items():
                if not enabled_var.get():
                    continue  # Skip disabled matches
                
                player_name = player_var.get().strip()
                if not player_name:
                    continue
                
                team = team_var.get().strip()
                jersey = jersey_var.get().strip()
                
                # CRITICAL: Require team assignment (except for coaches, referees, and "other" players)
                coach_names = {"Kevin Hill", "Coach", "coach"}
                is_coach = any(coach.lower() in player_name.lower() for coach in coach_names)
                is_referee = "referee" in player_name.lower() or "ref" in player_name.lower()
                is_other = player_name.lower() in ["other", "guest player", "guest", "unknown"]
                
                if not team and not (is_coach or is_referee or is_other):
                    messagebox.showwarning("Team Required", 
                        f"Please select a team for '{player_name}' (Track #{track_id}).\n\n"
                        "All players must be assigned to a team (Team 1 or Team 2).\n"
                        "Coaches, referees, and 'Other' players are exempt from this requirement.")
                    return  # Stop applying matches if team is missing
                
                # Apply to all instances of this track ID
                pid_str = str(track_id)
                self.approved_mappings[pid_str] = (player_name, team, jersey)
                
                # Tag all instances across all frames
                self.auto_tag_all_instances_of_id(track_id, player_name, team, jersey, silent=True)
                applied_count += 1
            
            if applied_count > 0:
                self.save_player_names()
                self.update_display()
                self.update_detections_list()
                self.update_summary()
                messagebox.showinfo("Success", 
                                  f"✓ Applied {applied_count} roster matches!\n\n"
                                  f"All instances of these tracks have been tagged.")
            
            dialog.destroy()
        
        ttk.Button(button_frame, text="✓ Apply Matches", command=apply_matches,
                  style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Status
        status_label = ttk.Label(button_frame, 
                                text="Review and modify matches, then click Apply",
                                foreground="gray", font=("Arial", 8))
        status_label.pack(side=tk.LEFT, padx=15)
    
    def reject_detection(self):
        """Reject selected detection (mark as false positive)"""
        if self.selected_detection is None or self.current_detections is None:
            return
        
        # Validate selected_detection index
        if self.selected_detection >= len(self.current_detections.tracker_id):
            messagebox.showwarning("Warning", "Selected detection is no longer valid.")
            self.selected_detection = None
            return
        
        track_id = self.current_detections.tracker_id[self.selected_detection]
        if track_id is None:
            return
        
        self.rejected_ids.add(track_id)
        self.selected_detection = None
        self.update_display()
        self.update_detections_list()
        self.update_summary()
    
    def on_player_name_select(self, event=None):
        """Handle player name selection in Tag Player section - auto-populate team and jersey"""
        player_name = self.player_name_var.get()
        if not player_name:
            return
        
        # Check roster first (most reliable source)
        if player_name in self.player_roster:
            roster_entry = self.player_roster[player_name]
            if roster_entry.get("team"):
                self.team_var.set(roster_entry["team"])
            if roster_entry.get("jersey_number"):
                self.jersey_number_var.set(roster_entry["jersey_number"])
            return
        
        # Fall back to approved_mappings (existing tags in this session)
        for pid_str, mapping in self.approved_mappings.items():
            if isinstance(mapping, tuple) and len(mapping) >= 2:
                if mapping[0] == player_name:  # Player name matches
                    if mapping[1]:  # Team exists
                        self.team_var.set(mapping[1])
                    if len(mapping) > 2 and mapping[2]:  # Jersey number exists
                        self.jersey_number_var.set(mapping[2])
                    return
    
    def on_quick_tag_player_select(self, event=None):
        """Handle quick tag player selection - auto-populate team if available"""
        player_name = self.quick_tag_player_var.get()
        if not player_name:
            return
        
        # Check roster first (most reliable source)
        if player_name in self.player_roster:
            roster_entry = self.player_roster[player_name]
            if roster_entry.get("team") and hasattr(self, 'quick_tag_team_combo'):
                self.quick_tag_team_var.set(roster_entry["team"])
            return
        
        # Fall back to approved_mappings
        for pid_str, mapping in self.approved_mappings.items():
            if isinstance(mapping, tuple) and len(mapping) >= 2:
                if mapping[0] == player_name and mapping[1]:  # Name and team match
                    if hasattr(self, 'quick_tag_team_combo'):
                        self.quick_tag_team_var.set(mapping[1])
                    return
    
    def on_quick_tag_team_select(self, event=None):
        """Handle quick tag team selection"""
        pass
    
    def apply_quick_tag(self):
        """Apply quick tag from detections section to selected detection"""
        if self.selected_detection is None or self.current_detections is None:
            messagebox.showwarning("Warning", "Please select a detection first")
            return
        
        player_name = self.quick_tag_player_var.get().strip()
        if not player_name:
            messagebox.showwarning("Warning", "Please select a player name")
            return
        
        # Set the player name and team in the tag player section
        self.player_name_var.set(player_name)
        team = self.quick_tag_team_var.get().strip()
        
        # Allow blank team - user can leave it empty if desired
        # Set team (even if blank) to allow tag_player() to handle it
        self.team_var.set(team)
        
        # Now tag the player (tag_player will handle blank team appropriately)
        self.tag_player()
        
        # Clear quick tag fields
        self.quick_tag_player_var.set("")
        self.quick_tag_team_var.set("")
    
    def clear_tag(self):
        """Clear tag for selected detection"""
        if self.selected_detection is None or self.current_detections is None:
            return
        
        # Validate selected_detection index
        if self.selected_detection >= len(self.current_detections.tracker_id):
            messagebox.showwarning("Warning", "Selected detection is no longer valid.")
            self.selected_detection = None
            return
        
        track_id = self.current_detections.tracker_id[self.selected_detection]
        if track_id is None:
            return
        
        track_id = self.merged_ids.get(track_id, track_id)
        pid_str = str(int(track_id))
        
        if pid_str in self.approved_mappings:
            del self.approved_mappings[pid_str]
            self.save_player_names()
            self.update_display()
            self.update_detections_list()
            self.update_summary()
    
    def tag_referee(self):
        """Tag selected detection as a referee"""
        if self.selected_detection is None or self.current_detections is None:
            messagebox.showwarning("Warning", "Please select a detection first")
            return
        
        # Validate selected_detection index
        if self.selected_detection >= len(self.current_detections.tracker_id):
            messagebox.showwarning("Warning", "Selected detection is no longer valid. Please select again.")
            self.selected_detection = None
            return
        
        track_id = self.current_detections.tracker_id[self.selected_detection]
        if track_id is None:
            return
        
        track_id = self.merged_ids.get(track_id, track_id)
        pid_str = str(int(track_id))
        
        referee_name = self.referee_name_var.get().strip()
        if not referee_name:
            messagebox.showwarning("Warning", "Please enter a referee name")
            return
        
        # Tag as referee (separate from players)
        self.referee_mappings[pid_str] = referee_name
        
        # Remove from player mappings if it was there
        if pid_str in self.approved_mappings:
            del self.approved_mappings[pid_str]
        
        # Remove from rejected IDs if it was there
        if track_id in self.rejected_ids:
            self.rejected_ids.remove(track_id)
        
        self.update_display()
        self.update_detections_list()
        self.update_summary()
        messagebox.showinfo("Tagged", f"Tagged ID #{track_id} as '{referee_name}'")
    
    def clear_referee_tag(self):
        """Clear referee tag for selected detection"""
        if self.selected_detection is None or self.current_detections is None:
            messagebox.showwarning("Warning", "Please select a detection first")
            return
        
        track_id = self.current_detections.tracker_id[self.selected_detection]
        if track_id is None:
            return
        
        track_id = self.merged_ids.get(track_id, track_id)
        pid_str = str(int(track_id))
        
        if pid_str in self.referee_mappings:
            del self.referee_mappings[pid_str]
            self.update_display()
            self.update_detections_list()
            self.update_summary()
            messagebox.showinfo("Cleared", f"Removed referee tag from ID #{track_id}")
        else:
            messagebox.showinfo("Info", f"ID #{track_id} is not tagged as a referee")
    
    def mark_substitution(self, action):
        """Mark a substitution event (player coming on or off field)"""
        if self.selected_detection is None or self.current_detections is None:
            messagebox.showwarning("Warning", "Please select a player first")
            return
        
        # Validate selected_detection index
        if self.selected_detection >= len(self.current_detections.tracker_id):
            messagebox.showwarning("Warning", "Selected detection is no longer valid.")
            self.selected_detection = None
            return
        
        track_id = self.current_detections.tracker_id[self.selected_detection]
        if track_id is None:
            return
        
        track_id = self.merged_ids.get(track_id, track_id)
        pid_str = str(int(track_id))
        
        # Get player name
        player_name = "Unknown"
        team = "Unknown"
        if pid_str in self.approved_mappings:
            mapping = self.approved_mappings[pid_str]
            if isinstance(mapping, tuple):
                player_name = mapping[0]
                team = mapping[1] if len(mapping) > 1 else "Unknown"
            else:
                player_name = mapping
        
        # Create substitution event
        sub_event = {
            "frame_num": self.current_frame_num,
            "player_id": int(track_id),
            "player_name": player_name,
            "team": team,
            "action": action  # "on" or "off"
        }
        
        self.substitution_events.append(sub_event)
        
        # Update roster
        if player_name not in self.player_roster:
            self.player_roster[player_name] = {
                "team": team,
                "jersey_number": "",
                "active": action == "on",
                "first_seen_frame": self.current_frame_num if action == "on" else None,
                "last_seen_frame": self.current_frame_num
            }
        else:
            self.player_roster[player_name]["active"] = action == "on"
            if action == "on":
                if self.player_roster[player_name]["first_seen_frame"] is None:
                    self.player_roster[player_name]["first_seen_frame"] = self.current_frame_num
            self.player_roster[player_name]["last_seen_frame"] = self.current_frame_num
        
        action_text = "ON" if action == "on" else "OFF"
        messagebox.showinfo("Substitution Marked", 
                           f"Marked {player_name} ({team}) as {action_text} at frame {self.current_frame_num}")
    
    def view_substitutions(self):
        """View all substitution events"""
        if not self.substitution_events:
            messagebox.showinfo("No Substitutions", "No substitution events have been marked yet.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Substitution Events")
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.lift()
        
        # Listbox with scrollbar
        listbox_frame = ttk.Frame(dialog, padding="10")
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, font=("Courier", 9))
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Populate listbox
        for event in sorted(self.substitution_events, key=lambda x: x["frame_num"]):
            frame_num = event["frame_num"]
            player_name = event["player_name"]
            team = event["team"]
            action = event["action"].upper()
            player_id = event["player_id"]
            
            time_str = f"{frame_num / self.fps:.1f}s" if self.fps > 0 else f"Frame {frame_num}"
            listbox.insert(tk.END, f"Frame {frame_num:6d} ({time_str:>8s}) | {action:>3s} | {player_name:20s} ({team:10s}) | ID #{player_id}")
        
        # Buttons
        button_frame = ttk.Frame(dialog, padding="10")
        button_frame.pack(fill=tk.X)
        
        def delete_selected():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                del self.substitution_events[index]
                listbox.delete(index)
                messagebox.showinfo("Deleted", "Substitution event removed")
        
        ttk.Button(button_frame, text="Delete Selected", command=delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def manage_roster(self):
        """Manage player roster with teams and jersey numbers - integrated with player_gallery.json and Re-ID"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Player Roster Management (7v7)")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.lift()
        
        # Load roster data from player_gallery.json on open
        self.load_roster_from_gallery()
        
        # Also load from global roster manager to merge players
        try:
            from team_roster_manager import TeamRosterManager
            roster_manager = TeamRosterManager()
            global_roster = roster_manager.roster
            
            # Merge global roster with video-specific roster (video takes precedence for active status)
            for player_name, player_data in global_roster.items():
                if player_name == 'videos':
                    continue
                if player_name not in self.player_roster:
                    # Add player from global roster
                    self.player_roster[player_name] = {
                        "team": player_data.get("team"),
                        "jersey_number": player_data.get("jersey_number"),
                        "active": player_data.get("active", True),
                        "first_seen_frame": None,
                        "last_seen_frame": None
                    }
                else:
                    # Merge: use global roster for team/jersey if not set, but keep video-specific active status
                    if not self.player_roster[player_name].get("team"):
                        self.player_roster[player_name]["team"] = player_data.get("team")
                    if not self.player_roster[player_name].get("jersey_number"):
                        self.player_roster[player_name]["jersey_number"] = player_data.get("jersey_number")
                    # Active status stays as video-specific (already set)
        except Exception as e:
            print(f"⚠ Could not load global roster: {e}")
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        ttk.Label(main_frame, text="Manage player rosters for 7v7 game (7 players per team + coach)", 
                 font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=5)
        ttk.Label(main_frame, text="✓ Connected to player_gallery.json - Re-ID features preserved", 
                 font=("Arial", 8), foreground="green").pack(anchor=tk.W, pady=2)
        ttk.Label(main_frame, text="💡 Active/Inactive settings are saved per video in seed config", 
                 font=("Arial", 8), foreground="blue").pack(anchor=tk.W, pady=2)
        
        # Treeview for roster
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree = ttk.Treeview(tree_frame, columns=("Team", "Jersey", "Active", "First Frame", "Last Frame"), 
                           show="tree headings", yscrollcommand=scrollbar.set)
        tree.heading("#0", text="Player Name")
        tree.heading("Team", text="Team")
        tree.heading("Jersey", text="Jersey #")
        tree.heading("Active", text="Active")
        tree.heading("First Frame", text="First Seen")
        tree.heading("Last Frame", text="Last Seen")
        
        tree.column("#0", width=200)
        tree.column("Team", width=100)
        tree.column("Jersey", width=80)
        tree.column("Active", width=60)
        tree.column("First Frame", width=100)
        tree.column("Last Frame", width=100)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=tree.yview)
        
        # Populate tree
        def refresh_tree():
            tree.delete(*tree.get_children())
            for player_name, info in sorted(self.player_roster.items()):
                team = info.get("team", "Unknown") or "Unknown"
                jersey = info.get("jersey_number", "") or ""
                active = "Yes" if info.get("active", True) else "No"
                first_frame = info.get("first_seen_frame", "") or ""
                last_frame = info.get("last_seen_frame", "") or ""
                
                tree.insert("", tk.END, text=player_name, 
                          values=(team, jersey, active, first_frame, last_frame))
        
        refresh_tree()
        
        # Edit frame
        edit_frame = ttk.LabelFrame(main_frame, text="Edit Player", padding="10")
        edit_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(edit_frame, text="Player:").grid(row=0, column=0, sticky=tk.W, padx=5)
        player_var = tk.StringVar()
        player_entry = ttk.Entry(edit_frame, textvariable=player_var, width=20)
        player_entry.grid(row=0, column=1, padx=5)
        
        ttk.Label(edit_frame, text="Team:").grid(row=0, column=2, sticky=tk.W, padx=5)
        team_var = tk.StringVar()
        # Get team names from config (supports custom names like "Blue", "Gray", etc.)
        team_names = self.get_team_names_from_config()
        # Allow typing custom team names (not readonly) - users can enter "Blue", "Gray", or any custom name
        team_combo = ttk.Combobox(edit_frame, textvariable=team_var, width=15,
                                 values=team_names)
        team_combo.grid(row=0, column=3, padx=5)
        
        ttk.Label(edit_frame, text="Jersey #:").grid(row=1, column=0, sticky=tk.W, padx=5)
        jersey_var = tk.StringVar()
        jersey_entry = ttk.Entry(edit_frame, textvariable=jersey_var, width=20)
        jersey_entry.grid(row=1, column=1, padx=5)
        
        # Active checkbox
        ttk.Label(edit_frame, text="Active:").grid(row=1, column=2, sticky=tk.W, padx=5)
        active_var = tk.BooleanVar(value=True)
        active_check = ttk.Checkbutton(edit_frame, text="Yes", variable=active_var)
        active_check.grid(row=1, column=3, padx=5, sticky=tk.W)
        
        # Visualization settings section (expandable)
        viz_frame = ttk.LabelFrame(edit_frame, text="Visualization Settings (Optional)", padding="5")
        viz_frame.grid(row=2, column=0, columnspan=4, sticky=tk.EW, pady=5, padx=5)
        
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
        box_thickness_spin = ttk.Spinbox(viz_frame, from_=1, to=10, textvariable=box_thickness_var, width=10)
        box_thickness_spin.grid(row=1, column=1, padx=5, sticky=tk.W)
        
        # Show glow
        show_glow_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(viz_frame, text="Show Glow Effect", variable=show_glow_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        # Glow intensity
        ttk.Label(viz_frame, text="Glow Intensity:").grid(row=3, column=0, sticky=tk.W, padx=5)
        glow_intensity_var = tk.IntVar(value=50)
        glow_intensity_spin = ttk.Spinbox(viz_frame, from_=0, to=100, textvariable=glow_intensity_var, width=10)
        glow_intensity_spin.grid(row=3, column=1, padx=5, sticky=tk.W)
        
        # Show trail
        show_trail_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(viz_frame, text="Show Movement Trail", variable=show_trail_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        # Label style
        ttk.Label(viz_frame, text="Label Style:").grid(row=5, column=0, sticky=tk.W, padx=5)
        label_style_var = tk.StringVar(value="full_name")
        label_style_combo = ttk.Combobox(viz_frame, textvariable=label_style_var, 
                                        values=["full_name", "jersey", "initials", "number"], 
                                        width=12, state="readonly")
        label_style_combo.grid(row=5, column=1, padx=5, sticky=tk.W)
        
        def load_selected():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                player_name = item["text"]
                values = item["values"]
                
                player_var.set(player_name)
                team_var.set(values[0] if values else "Unknown")
                jersey_var.set(values[1] if values and len(values) > 1 else "")
                # Load active status
                active_status = values[2] if values and len(values) > 2 else "Yes"
                active_var.set(active_status == "Yes")
                
                # Load visualization settings
                try:
                    from team_roster_manager import TeamRosterManager
                    roster_manager = TeamRosterManager()
                    player_data = roster_manager.roster.get(player_name, {})
                    viz = player_data.get("visualization_settings", {})
                    
                    if viz.get("custom_color_rgb"):
                        rgb = viz["custom_color_rgb"]
                        custom_color_var.set(f"{rgb[0]},{rgb[1]},{rgb[2]}")
                    else:
                        custom_color_var.set("")
                    
                    box_thickness_var.set(viz.get("box_thickness", 2))
                    show_glow_var.set(viz.get("show_glow", False))
                    glow_intensity_var.set(viz.get("glow_intensity", 50))
                    show_trail_var.set(viz.get("show_trail", False))
                    label_style_var.set(viz.get("label_style", "full_name"))
                except Exception:
                    # Reset to defaults if error
                    custom_color_var.set("")
                    box_thickness_var.set(2)
                    show_glow_var.set(False)
                    glow_intensity_var.set(50)
                    show_trail_var.set(False)
                    label_style_var.set("full_name")
        
        def save_player():
            player_name = player_var.get().strip()
            if not player_name:
                messagebox.showwarning("Warning", "Please enter a player name")
                return
            
            team = team_var.get()
            jersey = jersey_var.get().strip()
            active_status = active_var.get()
            
            # Parse visualization settings
            viz_settings = {}
            custom_color_str = custom_color_var.get().strip()
            if custom_color_str:
                try:
                    from team_roster_manager import TeamRosterManager
                    roster_manager = TeamRosterManager()
                    rgb = roster_manager._parse_color_string(custom_color_str)
                    if rgb:
                        viz_settings["use_custom_color"] = True
                        viz_settings["custom_color_rgb"] = rgb
                except Exception:
                    pass  # Skip if parsing fails
            
            if box_thickness_var.get() != 2:  # Only save if different from default
                viz_settings["box_thickness"] = box_thickness_var.get()
            
            if show_glow_var.get():
                viz_settings["show_glow"] = True
                viz_settings["glow_intensity"] = glow_intensity_var.get()
            
            if show_trail_var.get():
                viz_settings["show_trail"] = True
            
            if label_style_var.get() != "full_name":  # Only save if different from default
                viz_settings["label_style"] = label_style_var.get()
            
            if player_name not in self.player_roster:
                self.player_roster[player_name] = {
                    "team": team,
                    "jersey_number": jersey,
                    "active": active_status,
                    "first_seen_frame": None,
                    "last_seen_frame": None
                }
            else:
                self.player_roster[player_name]["team"] = team
                self.player_roster[player_name]["jersey_number"] = jersey
                self.player_roster[player_name]["active"] = active_status  # Save active status
            
            # Update global roster manager with active status
            try:
                from team_roster_manager import TeamRosterManager
                roster_manager = TeamRosterManager()
                # Add player if doesn't exist, then update
                if player_name not in roster_manager.roster:
                    roster_manager.add_player(
                        name=player_name,
                        jersey_number=jersey if jersey else None,
                        team=team if team else None,
                        active=active_status
                    )
                else:
                    update_data = {
                        "active": active_status,
                        "team": team if team else None,
                        "jersey_number": jersey if jersey else None
                    }
                    if viz_settings:
                        update_data["visualization_settings"] = viz_settings
                    roster_manager.update_player(player_name, **update_data)
                roster_manager.save_roster()
            except Exception as e:
                print(f"⚠ Could not update global roster: {e}")
            
            # Update player_gallery.json with roster info (preserves Re-ID features)
            try:
                from player_gallery import PlayerGallery
                gallery = PlayerGallery()
                gallery.load_gallery()
                
                # Generate player_id from name (same format as gallery uses)
                player_id = player_name.lower().replace(" ", "_")
                
                # Update or create player in gallery
                if player_id in gallery.players:
                    # Update existing player (preserves Re-ID features and reference frames)
                    gallery.update_player(
                        player_id=player_id,
                        jersey_number=jersey if jersey else None,
                        team=team if team else None
                    )
                    print(f"✓ Updated player '{player_name}' in gallery with roster info (Re-ID features preserved)")
                else:
                    # Create new player entry (will be populated with Re-ID features during analysis)
                    gallery.add_player(
                        name=player_name,
                        jersey_number=jersey if jersey else None,
                        team=team if team else None
                    )
                    print(f"✓ Added player '{player_name}' to gallery with roster info")
                
                gallery.save_gallery()
            except Exception as e:
                print(f"⚠ Could not update player_gallery.json: {e}")
                # Continue anyway - roster will still be saved
            
            refresh_tree()
            # Save roster to file so player stats can access it
            self.save_roster_to_file()
            
            # Auto-save seed config if video is loaded (to persist video-specific settings)
            if self.video_path:
                try:
                    self.save_tags_explicitly()
                    messagebox.showinfo("Saved", f"Updated roster for {player_name}\n\n✓ Saved to:\n- Global roster\n- Video seed config\n- player_gallery.json (Re-ID features preserved)")
                except Exception as e:
                    print(f"⚠ Could not auto-save seed config: {e}")
                    messagebox.showinfo("Saved", f"Updated roster for {player_name}\n\n✓ Saved to global roster and player_gallery.json\n(Note: Video seed config will be saved when you export seed config)")
            else:
                messagebox.showinfo("Saved", f"Updated roster for {player_name}\n\n✓ Saved to global roster and player_gallery.json (Re-ID features preserved)")
        
        tree.bind("<Double-1>", lambda e: load_selected())
        
        ttk.Button(edit_frame, text="Load Selected", command=load_selected).grid(row=3, column=0, columnspan=2, pady=5)
        ttk.Button(edit_frame, text="Save", command=save_player).grid(row=3, column=2, columnspan=2, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def view_active_players(self):
        """View which players are active at the current frame"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Active Players at Frame {self.current_frame_num}")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.lift()
        
        # Get active players from current frame
        active_players = {}
        if self.current_detections is not None:
            for i, track_id in enumerate(self.current_detections.tracker_id):
                if track_id is None or track_id in self.rejected_ids:
                    continue
                
                track_id = self.merged_ids.get(track_id, track_id)
                pid_str = str(int(track_id))
                
                if pid_str in self.approved_mappings:
                    mapping = self.approved_mappings[pid_str]
                    if isinstance(mapping, tuple):
                        player_name = mapping[0]
                        team = mapping[1] if len(mapping) > 1 else "Unknown"
                    else:
                        player_name = mapping
                        team = "Unknown"
                    
                    active_players[track_id] = (player_name, team)
        
        # Display
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=f"Active Players at Frame {self.current_frame_num}", 
                 font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=5)
        
        if not active_players:
            ttk.Label(main_frame, text="No active players found in this frame", 
                     foreground="gray").pack(pady=20)
        else:
            # Group by team
            team1_players = []
            team2_players = []
            other_players = []
            
            for track_id, (name, team) in active_players.items():
                if team == "Team 1":
                    team1_players.append((track_id, name))
                elif team == "Team 2":
                    team2_players.append((track_id, name))
                else:
                    other_players.append((track_id, name))
            
            # Display teams
            if team1_players:
                ttk.Label(main_frame, text="Team 1:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 2))
                for track_id, name in sorted(team1_players):
                    ttk.Label(main_frame, text=f"  • {name} (ID #{track_id})").pack(anchor=tk.W)
            
            if team2_players:
                ttk.Label(main_frame, text="Team 2:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 2))
                for track_id, name in sorted(team2_players):
                    ttk.Label(main_frame, text=f"  • {name} (ID #{track_id})").pack(anchor=tk.W)
            
            if other_players:
                ttk.Label(main_frame, text="Other:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 2))
                for track_id, name in sorted(other_players):
                    ttk.Label(main_frame, text=f"  • {name} (ID #{track_id})").pack(anchor=tk.W)
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)
    
    def tag_all_instances(self):
        """Tag all instances of the selected track ID across all frames"""
        if self.selected_detection is None or self.current_detections is None:
            messagebox.showwarning("Warning", "Please select a detection first")
            return
        
        # Validate selected_detection index
        if self.selected_detection >= len(self.current_detections.tracker_id):
            messagebox.showwarning("Warning", "Selected detection is no longer valid. Please select a player again.")
            self.selected_detection = None
            return
        
        track_id = self.current_detections.tracker_id[self.selected_detection]
        if track_id is None:
            return
        
        track_id = self.merged_ids.get(track_id, track_id)
        
        # Get current name, team, and jersey number
        player_name = self.player_name_var.get().strip()
        if not player_name:
            messagebox.showwarning("Warning", "Please select or enter a player name first")
            return
        
        team = self.team_var.get().strip()
        
        # CRITICAL: Require team assignment (except for coaches, referees, and "other" players)
        coach_names = {"Kevin Hill", "Coach", "coach"}
        is_coach = any(coach.lower() in player_name.lower() for coach in coach_names)
        is_referee = "referee" in player_name.lower() or "ref" in player_name.lower()
        is_other = player_name.lower() in ["other", "guest player", "guest", "unknown"]
        
        if not team and not (is_coach or is_referee or is_other):
            messagebox.showwarning("Team Required", 
                f"Please select a team for '{player_name}'.\n\n"
                "All players must be assigned to a team (Team 1 or Team 2).\n"
                "Coaches, referees, and 'Other' players are exempt from this requirement.")
            return
        
        jersey_number = self.jersey_number_var.get().strip()  # Get jersey number from GUI
        pid_str = str(int(track_id))
        
        # Count how many frames this ID appears in
        count = 0
        for frame_num in self.detections_history:
            detections = self.detections_history[frame_num]
            for tid in detections.tracker_id:
                if tid is None:
                    continue
                tid = self.merged_ids.get(tid, tid)
                if tid == track_id:
                    count += 1
                    break
        
        response = messagebox.askyesno(
            "Tag All Instances?",
            f"Tag all instances of ID #{track_id} as '{player_name}'?\n\n"
            f"This will tag {count} frames.\n"
            f"Continue?"
        )
        
        if response:
            # Tag all instances and create anchor frames
            total_anchor_frames_created = 0
            
            # Create anchor frames for all instances of this track ID
            for frame_num in self.detections_history:
                detections = self.detections_history[frame_num]
                detection_idx = None
                for idx, tid in enumerate(detections.tracker_id):
                    if tid is None:
                        continue
                    tid = self.merged_ids.get(tid, tid)
                    if tid == track_id:
                        detection_idx = idx
                        break
                
                # Create anchor frame for this instance
                if detection_idx is not None and detection_idx < len(detections.xyxy):
                    bbox = detections.xyxy[detection_idx].tolist()
                    
                    anchor_entry = {
                        "track_id": int(track_id),
                        "player_name": player_name,
                        "team": team,
                        "jersey_number": jersey_number,
                        "bbox": bbox,
                        "confidence": 1.00  # Anchor frames are ground truth
                    }
                    
                    if frame_num not in self.anchor_frames:
                        self.anchor_frames[frame_num] = []
                    
                    # Check if already exists
                    existing = False
                    for existing_anchor in self.anchor_frames[frame_num]:
                        if (existing_anchor.get("track_id") == int(track_id) and 
                            existing_anchor.get("player_name") == player_name):
                            existing = True
                            break
                    
                    if not existing:
                        self.anchor_frames[frame_num].append(anchor_entry)
                        total_anchor_frames_created += 1
            
            # Tag all instances (mapping) - use jersey number if available
            jersey_number = self.jersey_number_var.get().strip() if hasattr(self, 'jersey_number_var') else ""
            self.approved_mappings[pid_str] = (player_name, team, jersey_number)
            self.save_player_names()
            self.update_display()
            self.update_detections_list()
            self.update_summary()
            messagebox.showinfo("Tagged", 
                              f"Tagged all instances of ID #{track_id} as '{player_name}'\n\n"
                              f"Created {total_anchor_frames_created} anchor frame(s) with 1.00 confidence\n"
                              f"(These will be used for Re-ID, metrics, routing, and player gallery updates)")
    
    def tag_all_instances_all_players(self, silent=False):
        """Tag all instances of all track IDs that are currently tagged in this frame"""
        if self.current_detections is None or len(self.current_detections) == 0:
            if not silent:
                messagebox.showwarning("Warning", "No detections in current frame")
            return
        
        # Collect all tagged players in current frame
        tagged_players = {}  # {track_id: (player_name, team, jersey_number)}
        untagged_count = 0
        
        for i, track_id in enumerate(self.current_detections.tracker_id):
            if track_id is None or track_id in self.rejected_ids:
                continue
            
            track_id = self.merged_ids.get(track_id, track_id)
            pid_str = str(int(track_id))
            
            if pid_str in self.approved_mappings:
                mapping = self.approved_mappings[pid_str]
                if isinstance(mapping, tuple):
                    player_name = mapping[0]
                    team = mapping[1] if len(mapping) > 1 else ""
                    jersey_number = mapping[2] if len(mapping) > 2 else ""
                else:
                    player_name = mapping
                    team = ""
                    jersey_number = ""
                tagged_players[track_id] = (player_name, team, jersey_number)
            else:
                untagged_count += 1
        
        if not tagged_players:
            if not silent:
                messagebox.showinfo("Info", "No tagged players in current frame to tag all instances of")
            return
        
        if untagged_count > 0 and not silent:
            response = messagebox.askyesno(
                "Tag All Instances?",
                f"Found {len(tagged_players)} tagged player(s) in this frame.\n\n"
                f"There are also {untagged_count} untagged player(s) in this frame.\n\n"
                f"Tag all instances of all {len(tagged_players)} tagged player(s) across the entire video?\n\n"
                f"This will tag all frames where these track IDs appear."
            )
            if not response:
                return
        elif not silent:
            response = messagebox.askyesno(
                "Tag All Instances?",
                f"All players in this frame are tagged ({len(tagged_players)} player(s)).\n\n"
                f"Tag all instances of all {len(tagged_players)} player(s) across the entire video?\n\n"
                f"This will tag all frames where these track IDs appear."
            )
            if not response:
                return
        
        # Tag all instances of each tagged player
        total_frames_tagged = 0
        total_anchor_frames_created = 0
        
        for track_id, (player_name, team, jersey_number) in tagged_players.items():
            pid_str = str(int(track_id))
            # Count frames for this ID and create anchor frames
            frame_count = 0
            for frame_num in self.detections_history:
                detections = self.detections_history[frame_num]
                detection_idx = None
                for idx, tid in enumerate(detections.tracker_id):
                    if tid is None:
                        continue
                    tid = self.merged_ids.get(tid, tid)
                    if tid == track_id:
                        detection_idx = idx
                        frame_count += 1
                        break
                
                # CRITICAL: Create anchor frame for this instance
                # This ensures all tagged instances become ground truth for Re-ID, metrics, and routing
                if detection_idx is not None and detection_idx < len(detections.xyxy):
                    bbox = detections.xyxy[detection_idx].tolist()
                    
                    # Create anchor frame entry (same format as manual tagging)
                    anchor_entry = {
                        "track_id": int(track_id),
                        "player_name": player_name,
                        "team": team,
                        "jersey_number": jersey_number,
                        "bbox": bbox,
                        "confidence": 1.00  # Anchor frames are ground truth
                    }
                    
                    # Add to anchor_frames dictionary
                    if frame_num not in self.anchor_frames:
                        self.anchor_frames[frame_num] = []
                    
                    # Check if this anchor frame already exists (avoid duplicates)
                    existing = False
                    for existing_anchor in self.anchor_frames[frame_num]:
                        if (existing_anchor.get("track_id") == int(track_id) and 
                            existing_anchor.get("player_name") == player_name):
                            existing = True
                            break
                    
                    if not existing:
                        self.anchor_frames[frame_num].append(anchor_entry)
                        total_anchor_frames_created += 1
            
            # Tag all instances (mapping)
            self.approved_mappings[pid_str] = (player_name, team, jersey_number)
            total_frames_tagged += frame_count
        
        # Save and update
        self.save_player_names()
        
        # CRITICAL: Force immediate save of anchor frames after creation
        # This ensures anchor frames are saved even if auto-save hasn't run yet
        if total_anchor_frames_created > 0:
            # Verify anchor frames are actually in self.anchor_frames
            actual_anchor_count = sum(len(anchors) for anchors in self.anchor_frames.values())
            if actual_anchor_count != total_anchor_frames_created:
                print(f"⚠ Warning: Created {total_anchor_frames_created} anchor frames but found {actual_anchor_count} in self.anchor_frames")
            else:
                print(f"✓ Verified: {actual_anchor_count} anchor frames stored in self.anchor_frames")
            # Force immediate save
            self.auto_save()
        
        self.update_display()
        self.update_detections_list()
        self.update_summary()
        
        if not silent:
            messagebox.showinfo("Tagged", 
                              f"Tagged all instances of {len(tagged_players)} player(s) across {total_frames_tagged} frame(s)\n\n"
                              f"Created {total_anchor_frames_created} anchor frame(s) with 1.00 confidence\n"
                              f"(These will be used for Re-ID, metrics, routing, and player gallery updates)")
    
    def tag_all_visible(self):
        """Quick tag all visible detections in current frame"""
        if self.current_detections is None or len(self.current_detections) == 0:
            messagebox.showwarning("Warning", "No detections in current frame")
            return
        
        # Count untagged
        untagged = []
        for track_id in self.current_detections.tracker_id:
            if track_id is None or track_id in self.rejected_ids:
                continue
            track_id = self.merged_ids.get(track_id, track_id)
            pid_str = str(int(track_id))
            if pid_str not in self.approved_mappings:
                untagged.append(track_id)
        
        if not untagged:
            messagebox.showinfo("Info", "All detections in this frame are already tagged")
            return
        
        # Open dialog for quick tagging
        dialog = tk.Toplevel(self.root)
        dialog.title("Tag All Visible Players")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        
        ttk.Label(dialog, text=f"Tag {len(untagged)} untagged players:", font=("Arial", 10, "bold")).pack(pady=10)
        
        # Create entry fields for each untagged ID
        entries = {}
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        for tid in untagged:
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=2)
            
            ttk.Label(row, text=f"ID #{tid}:", width=10).pack(side=tk.LEFT)
            entry = ttk.Entry(row, width=20)
            entry.pack(side=tk.LEFT, padx=5)
            entries[tid] = entry
            
            # Team combo (allows custom names like "Blue", "Gray", etc.)
            team_var = tk.StringVar(value="")
            # Get team names from config (supports custom names like "Blue", "Gray", etc.)
            team_names = self.get_team_names_from_config()
            # Allow typing custom team names (not readonly) - users can enter "Blue", "Gray", or any custom name
            team_combo = ttk.Combobox(row, textvariable=team_var, width=12,
                                      values=team_names)
            team_combo.pack(side=tk.LEFT, padx=2)
            entries[tid] = (entry, team_var)
        
        def apply_tags():
            tagged_count = 0
            for tid, (entry, team_var) in entries.items():
                name = entry.get().strip()
                if name:
                    pid_str = str(int(tid))
                    team = team_var.get()
                    # Use empty jersey number for bulk tagging (can be set individually later)
                    self.approved_mappings[pid_str] = (name, team, "")
                    tagged_count += 1
            
            if tagged_count > 0:
                self.save_player_names()
                self.update_display()
                self.update_detections_list()
                self.update_summary()
                messagebox.showinfo("Tagged", f"Tagged {tagged_count} players")
            
            dialog.destroy()
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(button_frame, text="Apply Tags", command=apply_tags).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def copy_tags_from_frame(self):
        """Copy all tags from another frame"""
        if not self.detections_history:
            messagebox.showwarning("Warning", "No detection history available")
            return
        
        # Ask for frame number
        frame_num_str = simpledialog.askinteger(
            "Copy Tags from Frame",
            f"Enter frame number to copy tags from (0-{self.total_frames-1}):",
            minvalue=0,
            maxvalue=self.total_frames-1,
            initialvalue=max(0, self.current_frame_num - 10)
        )
        
        if frame_num_str is None:
            return
        
        if frame_num_str not in self.detections_history:
            messagebox.showwarning("Warning", f"No detections in frame {frame_num_str}")
            return
        
        source_detections = self.detections_history[frame_num_str]
        
        # Get mappings from source frame
        source_mappings = {}
        for track_id in source_detections.tracker_id:
            if track_id is None or track_id in self.rejected_ids:
                continue
            track_id = self.merged_ids.get(track_id, track_id)
            pid_str = str(int(track_id))
            if pid_str in self.approved_mappings:
                source_mappings[track_id] = self.approved_mappings[pid_str]
        
        if not source_mappings:
            messagebox.showinfo("Info", f"No tags found in frame {frame_num_str}")
            return
        
        # Apply to current frame
        applied = 0
        if self.current_detections is not None:
            for track_id in self.current_detections.tracker_id:
                if track_id is None or track_id in self.rejected_ids:
                    continue
                track_id = self.merged_ids.get(track_id, track_id)
                if track_id in source_mappings:
                    pid_str = str(int(track_id))
                    if pid_str not in self.approved_mappings:
                        self.approved_mappings[pid_str] = source_mappings[track_id]
                        applied += 1
        
        if applied > 0:
            self.save_player_names()
            self.update_display()
            self.update_detections_list()
            self.update_summary()
            messagebox.showinfo("Copied", f"Copied {applied} tags from frame {frame_num_str}")
        else:
            messagebox.showinfo("Info", "No matching IDs to copy tags to")
    
    def enable_ball_click(self):
        """Enable ball marking mode"""
        self.ball_click_mode = True
        self.ball_click_button.config(text="⚽ Click Canvas to Mark", state=tk.DISABLED)
        self.ball_status_label.config(text="← Click on the ball in the video frame", 
                                      foreground="orange", font=("Arial", 9, "bold"))
        self.canvas.config(cursor="plus")
        
    def remove_ball_from_frame(self):
        """Remove ball position from current frame"""
        # Remove all ball positions for current frame
        initial_count = len(self.ball_positions)
        self.ball_positions = [(f, x, y) for f, x, y in self.ball_positions 
                              if f != self.current_frame_num]
        removed = initial_count - len(self.ball_positions)
        
        if removed > 0:
            self.update_display()
            self.update_summary()
            self.update_ball_count()
            messagebox.showinfo("Removed", f"Removed {removed} ball position(s) from frame {self.current_frame_num + 1}")
        else:
            messagebox.showinfo("Info", "No ball position found in current frame")
    
    def update_ball_count(self):
        """Update the ball count label for current frame"""
        if not hasattr(self, 'ball_count_label'):
            return
        ball_count = sum(1 for f, x, y in self.ball_positions if f == self.current_frame_num)
        total_count = len(self.ball_positions)
        if ball_count > 0:
            self.ball_count_label.config(text=f"Ball positions: {ball_count} (this frame) | {total_count} total", 
                                         foreground="green")
        else:
            self.ball_count_label.config(text=f"Ball positions: {total_count} total (none in this frame)", 
                                         foreground="gray")
    
    def manage_ball_positions(self):
        """Open dialog to manage all ball positions (view, edit, delete)"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Ball Positions")
        dialog.geometry("800x700")
        dialog.transient(self.root)
        dialog.lift()
        dialog.attributes('-topmost', True)
        dialog.after(200, lambda: dialog.attributes('-topmost', False))
        dialog.focus_force()
        
        # Header
        header_frame = ttk.Frame(dialog, padding="10")
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text="Ball Position Manager", 
                 font=("Arial", 12, "bold")).pack()
        ttk.Label(header_frame, text=f"Total ball positions: {len(self.ball_positions)}", 
                 font=("Arial", 9), foreground="gray").pack()
        
        # List of ball positions
        list_frame = ttk.LabelFrame(dialog, text="All Ball Positions", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Treeview for ball positions
        columns = ("Frame", "X", "Y", "Actions")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)
        tree.heading("Frame", text="Frame #")
        tree.heading("X", text="X Position")
        tree.heading("Y", text="Y Position")
        tree.heading("Actions", text="Actions")
        tree.column("Frame", width=100)
        tree.column("X", width=120)
        tree.column("Y", width=120)
        tree.column("Actions", width=200)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate tree
        def refresh_tree():
            tree.delete(*tree.get_children())
            # Sort by frame number
            sorted_balls = sorted(self.ball_positions, key=lambda b: b[0])
            for frame_num, x, y in sorted_balls:
                tree.insert("", tk.END, values=(frame_num + 1, f"{x:.1f}", f"{y:.1f}", "Edit | Delete"),
                           tags=(frame_num,))
        
        refresh_tree()
        
        # Action buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        def edit_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a ball position to edit")
                return
            
            item = tree.item(selection[0])
            frame_num = item['tags'][0]
            
            # Find the ball position
            ball_idx = None
            for i, (f, bx, by) in enumerate(self.ball_positions):
                if f == frame_num:
                    ball_idx = i
                    break
            
            if ball_idx is None:
                return
            
            # Open edit dialog
            edit_dialog = tk.Toplevel(dialog)
            edit_dialog.title("Edit Ball Position")
            edit_dialog.geometry("400x300")
            edit_dialog.transient(dialog)
            edit_dialog.lift()
            
            ttk.Label(edit_dialog, text=f"Editing ball position at Frame {frame_num + 1}", 
                     font=("Arial", 10, "bold")).pack(pady=10)
            
            # Frame number
            frame_frame = ttk.Frame(edit_dialog)
            frame_frame.pack(fill=tk.X, padx=20, pady=5)
            ttk.Label(frame_frame, text="Frame Number:").pack(side=tk.LEFT)
            frame_var = tk.IntVar(value=frame_num)
            frame_spin = ttk.Spinbox(frame_frame, from_=0, to=max(0, self.total_frames - 1), 
                                    textvariable=frame_var, width=10)
            frame_spin.pack(side=tk.LEFT, padx=5)
            ttk.Button(frame_frame, text="Go to Frame", 
                      command=lambda: self.jump_to_frame_and_close(frame_var.get(), edit_dialog)).pack(side=tk.LEFT, padx=5)
            
            # X position
            x_frame = ttk.Frame(edit_dialog)
            x_frame.pack(fill=tk.X, padx=20, pady=5)
            ttk.Label(x_frame, text="X Position:").pack(side=tk.LEFT)
            x_var = tk.DoubleVar(value=self.ball_positions[ball_idx][1])
            x_spin = ttk.Spinbox(x_frame, from_=0, to=self.width, 
                                textvariable=x_var, width=15, format="%.1f")
            x_spin.pack(side=tk.LEFT, padx=5)
            
            # Y position
            y_frame = ttk.Frame(edit_dialog)
            y_frame.pack(fill=tk.X, padx=20, pady=5)
            ttk.Label(y_frame, text="Y Position:").pack(side=tk.LEFT)
            y_var = tk.DoubleVar(value=self.ball_positions[ball_idx][2])
            y_spin = ttk.Spinbox(y_frame, from_=0, to=self.height, 
                                textvariable=y_var, width=15, format="%.1f")
            y_spin.pack(side=tk.LEFT, padx=5)
            
            def save_edit():
                new_frame = frame_var.get()
                new_x = x_var.get()
                new_y = y_var.get()
                
                # Remove old position
                self.ball_positions.pop(ball_idx)
                
                # Add new position
                self.ball_positions.append((new_frame, new_x, new_y))
                
                refresh_tree()
                self.update_display()
                self.update_summary()
                self.update_ball_count()
                edit_dialog.destroy()
                messagebox.showinfo("Updated", f"Ball position updated:\nFrame {new_frame + 1}\n({new_x:.1f}, {new_y:.1f})")
            
            ttk.Button(edit_dialog, text="Save Changes", command=save_edit).pack(pady=10)
            ttk.Button(edit_dialog, text="Cancel", command=edit_dialog.destroy).pack()
        
        def delete_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a ball position to delete")
                return
            
            item = tree.item(selection[0])
            frame_num = item['tags'][0]
            
            response = messagebox.askyesno("Confirm Delete", 
                f"Delete ball position at Frame {frame_num + 1}?")
            if response:
                # Remove from list
                self.ball_positions = [(f, x, y) for f, x, y in self.ball_positions if f != frame_num]
                refresh_tree()
                self.update_display()
                self.update_summary()
                self.update_ball_count()
                messagebox.showinfo("Deleted", f"Ball position at Frame {frame_num + 1} deleted")
        
        def jump_to_frame():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a ball position")
                return
            
            item = tree.item(selection[0])
            frame_num = item['tags'][0]
            self.jump_to_frame_and_close(frame_num, dialog)
        
        # Bind double-click to edit
        def on_double_click(event):
            edit_selected()
        
        tree.bind("<Double-1>", on_double_click)
        
        ttk.Button(button_frame, text="Edit Selected", command=edit_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Selected", command=delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Jump to Frame", command=jump_to_frame).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Info label
        info_label = ttk.Label(dialog, 
                              text="Double-click a row to edit, or use buttons below. Changes are saved automatically.",
                              font=("Arial", 8), foreground="gray")
        info_label.pack(pady=5)
    
    def jump_to_frame_and_close(self, frame_num, dialog):
        """Jump to a specific frame and close dialog"""
        if 0 <= frame_num < self.total_frames:
            self.current_frame_num = frame_num
            self.frame_var.set(frame_num)
            self.load_frame()
            dialog.destroy()
        else:
            messagebox.showerror("Invalid Frame", f"Frame {frame_num + 1} is out of range")
    
    def auto_load_seed_data(self):
        """Auto-load ball positions and player mappings from PlayerTagsSeed-{video_name}.json, seed_config.json, or backup if available"""
        if not self.video_path:
            return
        
        # First, try to load from PlayerTagsSeed-{video_name}.json in video directory (preferred)
        video_dir = os.path.dirname(os.path.abspath(self.video_path))
        video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
        seed_file_video = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
        
        seed_file_loaded = False
        if os.path.exists(seed_file_video):
            try:
                with open(seed_file_video, 'r') as f:
                    config = json.load(f)
                    seed_file_loaded = self._load_seed_config_data(config, seed_file_video)
                    if seed_file_loaded:
                        print(f"✓ Loaded seed data from PlayerTagsSeed-{video_basename}.json")
            except Exception as e:
                print(f"Warning: Could not load PlayerTagsSeed file: {e}")
        
        # Try to load from seed_config.json if video-specific file not found or didn't have data
        if not seed_file_loaded:
            seed_file = "seed_config.json"
            if os.path.exists(seed_file):
                try:
                    with open(seed_file, 'r') as f:
                        config = json.load(f)
                        if self._load_seed_config_data(config, seed_file):
                            print(f"✓ Loaded seed data from seed_config.json")
                except Exception as e:
                    print(f"Warning: Could not auto-load seed config: {e}")
        
    def _load_seed_config_data(self, config, source_file=""):
        """Helper method to load seed config data from a config dictionary"""
        loaded_any = False
        
        # Check if this seed config is for the same video
        config_video = config.get("video_path")
        if config_video and os.path.exists(config_video):
            # Check if it's the same video (by filename or path)
            if os.path.normpath(config_video) == os.path.normpath(self.video_path):
                # Load ball positions
                ball_positions_raw = config.get("ball_positions", [])
                loaded_balls = 0
                for item in ball_positions_raw:
                    if isinstance(item, (list, tuple)) and len(item) >= 3:
                        try:
                            frame_num = int(item[0])
                            x = float(item[1])
                            y = float(item[2])
                            # Check if this ball position already exists
                            if not any(f == frame_num for f, _, _ in self.ball_positions):
                                self.ball_positions.append((frame_num, x, y))
                                loaded_balls += 1
                        except (ValueError, TypeError, IndexError):
                            pass
                
                if loaded_balls > 0:
                    print(f"✓ Auto-loaded {loaded_balls} ball position(s) from {os.path.basename(source_file) if source_file else 'seed config'}")
                    self.update_ball_count()
                    loaded_any = True
                
                # Load referee mappings
                referee_mappings = config.get("referee_mappings", {})
                if referee_mappings:
                    self.referee_mappings = {str(k): str(v) for k, v in referee_mappings.items()}
                    print(f"✓ Auto-loaded {len(self.referee_mappings)} referee mapping(s)")
                    loaded_any = True
                
                # Load substitution events
                substitution_events = config.get("substitution_events", [])
                if substitution_events:
                    self.substitution_events = substitution_events
                    print(f"✓ Auto-loaded {len(self.substitution_events)} substitution event(s)")
                    loaded_any = True
                
                # Load player roster (video-specific active/inactive settings)
                player_roster = config.get("player_roster", {})
                if player_roster:
                    self.player_roster = player_roster
                    print(f"✓ Auto-loaded player roster with {len(self.player_roster)} players")
                    loaded_any = True
                    # Update quick tag dropdown to reflect loaded active status
                    self.update_quick_tag_dropdown()
                
                # Load player mappings (always load, even if some exist, to update with seed data)
                player_mappings = config.get("player_mappings", {})
                if player_mappings:
                    loaded_mappings = 0
                    unique_players = set()
                    for k, v in player_mappings.items():
                        try:
                            if isinstance(v, (list, tuple)) and len(v) >= 2:
                                value = (str(v[0]) if v[0] is not None else "", 
                                        str(v[1]) if v[1] is not None else "")
                            elif isinstance(v, (list, tuple)) and len(v) == 1:
                                value = (str(v[0]) if v[0] is not None else "", "")
                            elif isinstance(v, (str, int, float)):
                                value = (str(v), "")
                            else:
                                continue
                            # Update mapping (may overwrite existing)
                            self.approved_mappings[str(k)] = value
                            loaded_mappings += 1
                            # Track unique players (value is always a tuple: (player_name, team))
                            player_name = value[0] if value and len(value) > 0 else ""
                            if player_name and player_name.strip():
                                unique_players.add(player_name.strip())
                        except:
                            pass
                    
                    if loaded_mappings > 0:
                        if len(unique_players) > 0:
                            print(f"✓ Auto-loaded {loaded_mappings} track ID mapping(s) for {len(unique_players)} unique player(s) from {os.path.basename(source_file) if source_file else 'seed config'}")
                        else:
                            print(f"✓ Auto-loaded {loaded_mappings} track ID mapping(s) from {os.path.basename(source_file) if source_file else 'seed config'}")
                        self.save_player_names()
                        if hasattr(self, 'update_detections_list'):
                            self.update_detections_list()
                        if hasattr(self, 'update_summary'):
                            self.update_summary()
                        loaded_any = True
                
                # Load anchor frames
                anchor_frames = config.get("anchor_frames", {})
                if anchor_frames:
                    self.anchor_frames = anchor_frames
                    total_anchors = sum(len(anchors) for anchors in anchor_frames.values())
                    print(f"✓ Auto-loaded {total_anchors} anchor frame tag(s) from {len(anchor_frames)} frames")
                    loaded_any = True
        
        return loaded_any
    
    def auto_load_seed_data(self):
        """Auto-load ball positions and player mappings from PlayerTagsSeed-{video_name}.json, seed_config.json, or backup if available"""
        if not self.video_path:
            return
        
        # First, try to load from PlayerTagsSeed-{video_name}.json in video directory (preferred)
        video_dir = os.path.dirname(os.path.abspath(self.video_path))
        video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
        seed_file_video = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
        
        seed_file_loaded = False
        if os.path.exists(seed_file_video):
            try:
                with open(seed_file_video, 'r') as f:
                    config = json.load(f)
                    seed_file_loaded = self._load_seed_config_data(config, seed_file_video)
                    if seed_file_loaded:
                        print(f"✓ Loaded seed data from PlayerTagsSeed-{video_basename}.json")
            except Exception as e:
                print(f"Warning: Could not load PlayerTagsSeed file: {e}")
        
        # Try to load from seed_config.json if video-specific file not found or didn't have data
        if not seed_file_loaded:
            seed_file = "seed_config.json"
            if os.path.exists(seed_file):
                try:
                    with open(seed_file, 'r') as f:
                        config = json.load(f)
                        if self._load_seed_config_data(config, seed_file):
                            print(f"✓ Loaded seed data from seed_config.json")
                except Exception as e:
                    print(f"Warning: Could not auto-load seed config: {e}")
        
        # Also try to load from most recent backup if seed files don't have data
        if len(self.ball_positions) == 0:
            backup_dir = "setup_wizard_backups"
            if os.path.exists(backup_dir):
                try:
                    # Find most recent backup file
                    backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.json')]
                    if backup_files:
                        # Sort by modification time
                        backup_files.sort(key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)), reverse=True)
                        most_recent_backup = os.path.join(backup_dir, backup_files[0])
                        
                        with open(most_recent_backup, 'r') as f:
                            config = json.load(f)
                            
                            # Check if backup is for same video
                            backup_video = config.get("video_path")
                            if backup_video and os.path.exists(backup_video):
                                if os.path.normpath(backup_video) == os.path.normpath(self.video_path):
                                    # Load ball positions from backup
                                    ball_positions_raw = config.get("ball_positions", [])
                                    loaded_balls = 0
                                    for item in ball_positions_raw:
                                        if isinstance(item, (list, tuple)) and len(item) >= 3:
                                            try:
                                                frame_num = int(item[0])
                                                x = float(item[1])
                                                y = float(item[2])
                                                if not any(f == frame_num for f, _, _ in self.ball_positions):
                                                    self.ball_positions.append((frame_num, x, y))
                                                    loaded_balls += 1
                                            except (ValueError, TypeError, IndexError):
                                                pass
                                    
                                    if loaded_balls > 0:
                                        print(f"✓ Auto-loaded {loaded_balls} ball position(s) from backup")
                                        self.update_ball_count()
                except Exception as e:
                    print(f"Warning: Could not auto-load from backup: {e}")
    
    def save_player_names(self):
        """Save player names to file"""
        player_names_dict = {}
        for pid, mapping in self.approved_mappings.items():
            # Handle tuple (name, team, jersey_number), tuple (name, team), and string (name) formats
            if isinstance(mapping, tuple):
                if len(mapping) == 3:
                    name, team, jersey_number = mapping
                elif len(mapping) == 2:
                    name, team = mapping
                else:
                    name = mapping[0] if len(mapping) > 0 else ""
            else:
                name = mapping
            player_names_dict[pid] = name
        
        try:
            with open("player_names.json", 'w') as f:
                json.dump(player_names_dict, f, indent=4)
            
            # Also save roster data to a separate file for player stats integration
            self.save_roster_to_file()
            
            return True
        except Exception as e:
            print(f"Warning: Could not save player names: {e}")
            return False
    
    def load_roster_from_gallery(self):
        """Load roster data from player_gallery.json to sync with Re-ID database"""
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            gallery.load_gallery()
            
            # Update roster from gallery data
            for player_id, profile in gallery.players.items():
                player_name = profile.name
                
                # Initialize roster entry if needed
                if player_name not in self.player_roster:
                    self.player_roster[player_name] = {
                        "team": profile.team,
                        "jersey_number": profile.jersey_number,
                        "active": True,
                        "first_seen_frame": None,
                        "last_seen_frame": None
                    }
                else:
                    # Update roster with gallery data (but preserve frame tracking)
                    if profile.team:
                        self.player_roster[player_name]["team"] = profile.team
                    if profile.jersey_number:
                        self.player_roster[player_name]["jersey_number"] = profile.jersey_number
            
            print(f"✓ Loaded roster data from player_gallery.json ({len(gallery.players)} players)")
            # Update quick tag dropdown after loading roster from gallery
            self.update_quick_tag_dropdown()
        except Exception as e:
            print(f"⚠ Could not load roster from gallery: {e}")
    
    def save_roster_to_file(self):
        """Save roster data to a file that player stats can load"""
        try:
            # Create roster file with player_id -> roster info mapping
            roster_dict = {}
            
            # Map from player names to track IDs
            name_to_ids = {}
            for pid, mapping in self.approved_mappings.items():
                if isinstance(mapping, tuple):
                    name = mapping[0]
                else:
                    name = mapping
                if name:
                    if name not in name_to_ids:
                        name_to_ids[name] = []
                    name_to_ids[name].append(pid)
            
            # Build roster dict with track IDs
            for player_name, roster_info in self.player_roster.items():
                # Find all track IDs for this player name
                track_ids = name_to_ids.get(player_name, [])
                for pid in track_ids:
                    roster_dict[pid] = {
                        "name": player_name,
                        "team": roster_info.get("team", "Unknown"),
                        "jersey_number": roster_info.get("jersey_number", ""),
                        "active": roster_info.get("active", True),
                        "first_seen_frame": roster_info.get("first_seen_frame"),
                        "last_seen_frame": roster_info.get("last_seen_frame")
                    }
            
            # Save to file
            with open("player_roster.json", 'w') as f:
                json.dump(roster_dict, f, indent=4)
            
            return True
        except Exception as e:
            print(f"Warning: Could not save roster data: {e}")
            return False
    
    def save_tags_explicitly(self):
        """Explicitly save all tags with user feedback"""
        if not self.approved_mappings and not self.player_roster:
            messagebox.showwarning("No Tags", "No player tags or roster changes to save. Please tag some players or update roster first.")
            return
        
        # Save player names
        success = self.save_player_names()
        
        # Also save seed config if video is loaded
        seed_saved = False
        if self.video_path:
            try:
                # Convert NumPy types to Python types for JSON serialization
                def convert_to_python_types(obj):
                    """Recursively convert NumPy types to Python types"""
                    if isinstance(obj, np.integer):
                        return int(obj)
                    elif isinstance(obj, np.floating):
                        return float(obj)
                    elif isinstance(obj, np.ndarray):
                        return obj.tolist()
                    elif isinstance(obj, dict):
                        return {k: convert_to_python_types(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_to_python_types(item) for item in obj]
                    elif isinstance(obj, tuple):
                        return tuple(convert_to_python_types(item) for item in obj)
                    elif isinstance(obj, set):
                        return list(convert_to_python_types(item) for item in obj)
                    return obj
                
                config = {
                    "player_mappings": convert_to_python_types(self.approved_mappings),
                    "referee_mappings": convert_to_python_types(self.referee_mappings),
                    "rejected_ids": convert_to_python_types(list(self.rejected_ids)),
                    "merged_ids": convert_to_python_types(self.merged_ids),
                    "substitution_events": convert_to_python_types(self.substitution_events),
                    "player_roster": convert_to_python_types(self.player_roster),
                    "ball_positions": convert_to_python_types(self.ball_positions),
                    "anchor_frames": convert_to_python_types(self.anchor_frames),
                    "video_path": self.video_path,
                    "current_frame": int(self.current_frame_num)
                }
                
                # Save to video directory as PlayerTagsSeed-{video_basename}.json
                video_dir = os.path.dirname(os.path.abspath(self.video_path))
                video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
                seed_file_video = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
                with open(seed_file_video, 'w') as f:
                    json.dump(config, f, indent=4)
                print(f"✓ Saved seed config (with player_roster) to: {seed_file_video}")
                seed_saved = True
            except Exception as e:
                print(f"⚠ Could not save seed config: {e}")
        
        # Also save seed config
        try:
            # Count unique players
            unique_players = set()
            for pid, mapping in self.approved_mappings.items():
                if isinstance(mapping, tuple):
                    name = mapping[0]
                else:
                    name = mapping
                if name:
                    unique_players.add(name)
            
            if success:
                msg = f"Successfully saved {len(self.approved_mappings)} player tags!\n\n"
                msg += f"Unique players: {len(unique_players)}\n\n"
                msg += f"Saved to: player_names.json\n\n"
                if seed_saved:
                    msg += f"✓ Seed config (with player_roster) saved to video directory\n\n"
                msg += f"These names will be available in Player Stats & Management."
                messagebox.showinfo("Tags Saved", msg)
            else:
                messagebox.showerror("Error", "Failed to save player tags. Please check file permissions.")
        except Exception as e:
            messagebox.showerror("Error", f"Error saving tags: {e}")
    
    def load_backup(self):
        """Load backup configuration if available"""
        backup_dir = "setup_wizard_backups"
        if not os.path.exists(backup_dir):
            return False
        
        # Find most recent backup
        backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.json')]
        if not backup_files:
            return False
        
        backup_files.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)), reverse=True)
        most_recent = backup_files[0]
        
        response = messagebox.askyesno(
            "Load Backup?",
            f"Found backup configuration.\n\n"
            f"File: {most_recent}\n"
            f"Would you like to load it?"
        )
        
        if response:
            try:
                backup_path = os.path.join(backup_dir, most_recent)
                with open(backup_path, 'r') as f:
                    config = json.load(f)
                
                # Restore mappings - ensure keys are strings and values are tuples or strings
                player_mappings_raw = config.get("player_mappings", {})
                self.approved_mappings = {}
                
                # Handle case where player_mappings_raw might not be a dict
                if not isinstance(player_mappings_raw, dict):
                    print(f"Warning: player_mappings is not a dict, got {type(player_mappings_raw)}")
                    player_mappings_raw = {}
                
                for k, v in player_mappings_raw.items():
                    try:
                        # Ensure key is hashable (string, int, float) - skip if list or other unhashable type
                        if isinstance(k, list):
                            print(f"Warning: Skipping mapping with list key: {k}")
                            continue
                        if k is None:
                            continue
                        # Convert key to string
                        try:
                            key = str(k)
                        except (TypeError, ValueError):
                            print(f"Warning: Could not convert key to string: {k} (type: {type(k)})")
                            continue
                        
                        # Ensure value is a tuple (name, team) or string (name)
                        if isinstance(v, list):
                            # Convert list to tuple
                            if len(v) >= 2:
                                value = (str(v[0]) if v[0] is not None else "", 
                                        str(v[1]) if v[1] is not None else "")
                            elif len(v) == 1:
                                value = (str(v[0]) if v[0] is not None else "", "")
                            else:
                                value = ("", "")
                        elif isinstance(v, tuple):
                            # Ensure tuple elements are strings
                            if len(v) >= 2:
                                value = (str(v[0]) if v[0] is not None else "", 
                                        str(v[1]) if v[1] is not None else "")
                            elif len(v) == 1:
                                value = (str(v[0]) if v[0] is not None else "", "")
                            else:
                                value = ("", "")
                        elif isinstance(v, (str, int, float)):
                            # Single value - convert to tuple (name, "")
                            value = (str(v), "")
                        else:
                            # Skip invalid entries
                            continue
                        
                        self.approved_mappings[key] = value
                    except (ValueError, TypeError, AttributeError) as e:
                        # Skip invalid entries
                        print(f"Warning: Skipping invalid mapping entry: {k} -> {v} (error: {e})")
                        continue
                
                # Handle rejected_ids - ensure all are hashable (integers)
                rejected_ids_raw = config.get("rejected_ids", [])
                rejected_ids_clean = []
                for item in rejected_ids_raw:
                    if isinstance(item, (int, float)):
                        rejected_ids_clean.append(int(item))
                    elif isinstance(item, list):
                        # If nested list, extract integers
                        for subitem in item:
                            if isinstance(subitem, (int, float)):
                                rejected_ids_clean.append(int(subitem))
                    elif item is not None:
                        # Try to convert to int
                        try:
                            rejected_ids_clean.append(int(item))
                        except (ValueError, TypeError):
                            pass  # Skip invalid items
                self.rejected_ids = set(rejected_ids_clean)
                
                # Handle merged_ids - ensure keys and values are hashable
                merged_ids_raw = config.get("merged_ids", {})
                self.merged_ids = {}
                for k, v in merged_ids_raw.items():
                    try:
                        key = int(k) if isinstance(k, (int, float, str)) else k
                        val = int(v) if isinstance(v, (int, float, str)) else v
                        self.merged_ids[key] = val
                    except (ValueError, TypeError):
                        pass  # Skip invalid entries
                
                # Handle ball_positions - ensure all are tuples of (int, float, float)
                ball_positions_raw = config.get("ball_positions", [])
                self.ball_positions = []
                for item in ball_positions_raw:
                    if isinstance(item, (list, tuple)) and len(item) >= 3:
                        try:
                            frame_num = int(item[0])
                            x = float(item[1])
                            y = float(item[2])
                            self.ball_positions.append((frame_num, x, y))
                        except (ValueError, TypeError, IndexError):
                            pass  # Skip invalid entries
                
                # Load anchor frames (NEW)
                anchor_frames = config.get("anchor_frames", {})
                if anchor_frames:
                    self.anchor_frames = anchor_frames
                    total_anchors = sum(len(anchors) for anchors in anchor_frames.values())
                    print(f"✓ Loaded {total_anchors} anchor frame tag(s) from {len(anchor_frames)} frames")
                
                # Load player_roster (video-specific active/inactive settings)
                player_roster_backup = config.get("player_roster", {})
                if player_roster_backup:
                    self.player_roster = player_roster_backup.copy()
                    print(f"✓ Loaded player roster with {len(self.player_roster)} players (including active/inactive settings)")
                
                # Try to restore video if path exists
                backup_video = config.get("video_path")
                if backup_video and os.path.exists(backup_video):
                    # Load video manually (don't call load_video which shows dialog)
                    self.video_path = backup_video
                    self.cap = cv2.VideoCapture(backup_video)
                    
                    if self.cap.isOpened():
                        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
                        frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
                        self.total_frames = int(frame_count) if frame_count and not np.isnan(frame_count) else 0
                        width_val = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                        height_val = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                        self.width = int(width_val) if width_val and not np.isnan(width_val) else 0
                        self.height = int(height_val) if height_val and not np.isnan(height_val) else 0
                        
                        if self.total_frames <= 0:
                            messagebox.showerror("Error", "Could not determine video frame count from backup video.")
                            self.cap.release()
                            self.cap = None
                        else:
                            # Frame slider was moved to nav bar, no longer exists here
                            # Just update frame_var if it exists
                            if hasattr(self, 'frame_var'):
                                self.frame_var.set(0)
                            video_name = os.path.basename(backup_video)
                            status_text = f"Video: {video_name} ({self.total_frames} frames)"
                            self.status_label.config(text=str(status_text))
                            # Update window title to show video name
                            self.root.title(f"Interactive Setup Wizard - {video_name}")
                        self.init_button.config(state=tk.NORMAL)
                        
                        # Restore frame position
                        backup_frame = config.get("current_frame", 0)
                        if 0 <= backup_frame < self.total_frames:
                            self.current_frame_num = backup_frame
                        else:
                            self.current_frame_num = 0
                        
                        self.load_frame()
                
                # Save to main files
                self.save_player_names()
                
                # Update ball count display
                self.update_ball_count()
                
                self.update_display()
                self.update_detections_list()
                self.update_summary()
                
                ball_count = len(self.ball_positions)
                message = f"Loaded {len(self.approved_mappings)} player mappings"
                if ball_count > 0:
                    message += f" and {ball_count} ball position(s)"
                messagebox.showinfo("Backup Loaded", message)
                return True
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"Backup load error: {error_details}")
                messagebox.showerror("Error", 
                    f"Could not load backup: {e}\n\n"
                    f"Check console for details.\n\n"
                    f"If this persists, the backup file may be corrupted.\n"
                    f"You can try deleting the backup and starting fresh.")
                return False
        
        return False
    
    def update_summary(self):
        """Update summary label with enhanced progress info"""
        num_mapped = len(self.approved_mappings)
        num_rejected = len(self.rejected_ids)
        num_ball = len(self.ball_positions)
        
        # Count unique players tagged
        unique_players = set()
        for pid, mapping in self.approved_mappings.items():
            try:
                if isinstance(mapping, tuple):
                    name = mapping[0] if len(mapping) > 0 else ""
                elif isinstance(mapping, list):
                    # Handle list case (shouldn't happen after backup fix, but just in case)
                    name = mapping[0] if len(mapping) > 0 else ""
                else:
                    name = mapping
                
                # Ensure name is a string and not empty
                name = str(name) if name is not None else ""
                if name and name.strip():
                    unique_players.add(name)
            except (TypeError, IndexError, AttributeError) as e:
                # Skip invalid mappings
                print(f"Warning: Skipping invalid mapping in update_summary: {pid} -> {mapping} (error: {e})")
                continue
        
        # Progress indicator (initialize as empty string)
        progress = ""
        if self.detections_history and len(self.detections_history) > 0:
            # Count frames with untagged players
            untagged_frames = 0
            total_detection_frames = len(self.detections_history)
            for frame_num in self.detections_history:
                detections = self.detections_history[frame_num]
                has_untagged = False
                for track_id in detections.tracker_id:
                    try:
                        # Ensure track_id is hashable (not a list)
                        if track_id is None:
                            continue
                        if isinstance(track_id, (list, tuple, dict)):
                            # Skip unhashable types
                            continue
                        # Convert to int for set lookup
                        track_id_int = int(track_id) if not isinstance(track_id, (int, float)) else int(track_id)
                        if track_id_int in self.rejected_ids:
                            continue
                        track_id = self.merged_ids.get(track_id_int, track_id_int)
                        pid_str = str(int(track_id))
                        if pid_str not in self.approved_mappings:
                            has_untagged = True
                            break
                    except (TypeError, ValueError, AttributeError):
                        # Skip invalid track_ids
                        continue
                if has_untagged:
                    untagged_frames += 1
            
            tagged_frames = total_detection_frames - untagged_frames
            if total_detection_frames > 0:
                progress_pct = (tagged_frames / total_detection_frames) * 100
                progress = f" | Progress: {int(progress_pct)}% ({int(tagged_frames)}/{int(total_detection_frames)} frames)"
            else:
                progress = ""
        
        # Roster completion status
        roster_status = ""
        if self.player_roster:
            roster_players = list(self.player_roster.keys())
            assigned_from_roster = [p for p in unique_players if p in roster_players]
            unassigned_from_roster = [p for p in roster_players if p not in unique_players]
            
            if unassigned_from_roster:
                roster_status = f" | 📋 Roster: {len(assigned_from_roster)}/{len(roster_players)} assigned"
            else:
                roster_status = f" | ✓ Roster: {len(roster_players)}/{len(roster_players)} complete!"
        
        # Validation warnings
        warnings = []
        if len(unique_players) < 11:
            warnings.append(f"⚠ Only {len(unique_players)}/11 players tagged")
        
        summary = f"Mapped: {int(num_mapped)} IDs ({int(len(unique_players))} unique players) | Rejected: {int(num_rejected)} | Ball: {int(num_ball)} positions{str(roster_status)}{str(progress)}"
        if warnings:
            summary += f"\n{' | '.join(warnings)}"
        
        self.summary_label.config(text=str(summary))
    
    def export_seed_config(self):
        """Export seed configuration for analysis with validation"""
        # Run validation
        validation_issues = []
        
        # Count unique players
        unique_players = set()
        for pid, mapping in self.approved_mappings.items():
            if isinstance(mapping, tuple):
                name = mapping[0]
            else:
                name = mapping
            if name:
                unique_players.add(name)
        
        # For 7v7, expect 7 players per team (14 total) + coach = 15
        # But allow flexibility
        if len(unique_players) < 7:
            validation_issues.append(f"Only {len(unique_players)} unique players tagged (expected 7+ for 7v7)")
        
        if len(self.approved_mappings) == 0:
            validation_issues.append("No players have been tagged")
        
        # Show validation if issues found
        if validation_issues:
            issues_text = "\n".join(validation_issues)
            response = messagebox.askyesno(
                "Validation Warnings",
                f"The following issues were found:\n\n{issues_text}\n\n"
                "Do you want to export anyway?"
            )
            if not response:
                return
        
        # Convert NumPy types to Python types for JSON serialization
        def convert_to_python_types(obj):
            """Recursively convert NumPy types to Python types"""
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_to_python_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_python_types(item) for item in obj]
            elif isinstance(obj, tuple):
                return tuple(convert_to_python_types(item) for item in obj)
            elif isinstance(obj, set):
                return list(convert_to_python_types(item) for item in obj)
            return obj
        
        config = {
            "player_mappings": convert_to_python_types(self.approved_mappings),
            "referee_mappings": convert_to_python_types(self.referee_mappings),
            "rejected_ids": convert_to_python_types(list(self.rejected_ids)),
            "merged_ids": convert_to_python_types(self.merged_ids),
            "ball_positions": convert_to_python_types(self.ball_positions),
            "substitution_events": convert_to_python_types(self.substitution_events),
            "player_roster": convert_to_python_types(self.player_roster),
            "anchor_frames": convert_to_python_types(self.anchor_frames),  # NEW: Anchor frames with 1.00 confidence
            "video_path": self.video_path,
            "current_frame": int(self.current_frame_num)
        }
        
        filename = self._show_file_dialog(
            filedialog.asksaveasfilename,
            title="Save Seed Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(config, f, indent=4)
                
                # Show summary
                summary = (
                    f"Seed configuration exported!\n\n"
                    f"Players mapped: {len(self.approved_mappings)} IDs\n"
                    f"Unique players: {len(unique_players)}\n"
                    f"Referees: {len(self.referee_mappings)}\n"
                    f"Substitution events: {len(self.substitution_events)}\n"
                    f"Ball positions: {len(self.ball_positions)}\n"
                    f"Rejected IDs: {len(self.rejected_ids)}\n\n"
                    f"Saved to:\n{filename}"
                )
                messagebox.showinfo("Export Complete", summary)
            except Exception as e:
                messagebox.showerror("Error", f"Could not save config: {e}")
    
    def start_analysis(self):
        """Prepare for full analysis - explains next steps"""
        if not self.video_path:
            messagebox.showwarning("Warning", "Please load a video first")
            return
        
        # Save current mappings
        self.save_player_names()
        
        # Auto-export seed config if mappings exist
        # CRITICAL: Save to BOTH locations so analyzer can find it
        seed_exported = False
        seed_file = None  # Initialize seed_file variable
        if self.approved_mappings and self.video_path:
            try:
                # Convert NumPy types to Python types for JSON serialization
                def convert_to_python_types(obj):
                    """Recursively convert NumPy types to Python types"""
                    if isinstance(obj, np.integer):
                        return int(obj)
                    elif isinstance(obj, np.floating):
                        return float(obj)
                    elif isinstance(obj, np.ndarray):
                        return obj.tolist()
                    elif isinstance(obj, dict):
                        return {k: convert_to_python_types(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_to_python_types(item) for item in obj]
                    elif isinstance(obj, tuple):
                        return tuple(convert_to_python_types(item) for item in obj)
                    elif isinstance(obj, set):
                        return list(convert_to_python_types(item) for item in obj)
                    return obj
                
                config = {
                    "player_mappings": convert_to_python_types(self.approved_mappings),
                    "referee_mappings": convert_to_python_types(self.referee_mappings),
                    "rejected_ids": convert_to_python_types(list(self.rejected_ids)),
                    "merged_ids": convert_to_python_types(self.merged_ids),
                    "substitution_events": convert_to_python_types(self.substitution_events),
                    "player_roster": convert_to_python_types(self.player_roster),
                    "ball_positions": convert_to_python_types(self.ball_positions),
                    "anchor_frames": convert_to_python_types(self.anchor_frames),  # NEW: Anchor frames with 1.00 confidence
                    "video_path": self.video_path,  # CRITICAL: Include video path so analyzer can verify it matches
                    "current_frame": int(self.current_frame_num)
                }
                
                # 1. Save to project root (for backward compatibility)
                seed_file_root = "seed_config.json"
                with open(seed_file_root, 'w') as f:
                    json.dump(config, f, indent=4)
                print(f"✓ Saved seed config to: {seed_file_root}")
                
                # 2. ALSO save to video directory as PlayerTagsSeed-{video_basename}.json (for analyzer)
                video_dir = os.path.dirname(os.path.abspath(self.video_path))
                video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
                seed_file_video = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
                with open(seed_file_video, 'w') as f:
                    json.dump(config, f, indent=4)
                print(f"✓ Saved seed config to: {seed_file_video}")
                
                # Store seed_file for use in workflow message
                seed_file = seed_file_video
                seed_exported = True
            except Exception as e:
                print(f"⚠ Could not auto-save seed config: {e}")
                import traceback
                traceback.print_exc()
                seed_exported = False
        else:
            seed_exported = False
        
        # Show workflow instructions
        workflow_msg = (
            f"✓ Setup Wizard Complete!\n\n"
            f"Tagged Players: {len(self.approved_mappings)} IDs\n"
            f"Ball Positions: {len(self.ball_positions)} frames\n\n"
            f"Next Steps:\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"1. Go to Main GUI\n"
            f"   → Select your video (already selected)\n"
            f"   → Configure analysis options\n"
            f"   → Click 'Start Analysis'\n\n"
            f"2. Wait for Analysis to Complete\n"
            f"   → This creates a CSV with all tracking data\n"
            f"   → Fragmented player IDs will appear\n\n"
            f"3. Use Consolidate IDs Tool\n"
            f"   → Open from Main GUI or Setup Wizard\n"
            f"   → Load the CSV from analysis\n"
            f"   → Merge duplicate player IDs\n\n"
            f"4. Review Results\n"
            f"   → Use Playback Viewer to verify\n"
            f"   → Check Player Stats & Names\n\n"
        )
        
        if seed_exported and seed_file:
            workflow_msg += f"\n✓ Seed config saved to: {seed_file}\n"
            workflow_msg += "  (The analysis will use these mappings)"
        
        messagebox.showinfo("Ready for Analysis", workflow_msg)
    
    def open_consolidate_ids(self):
        """Open consolidate IDs tool - should be used AFTER full analysis"""
        if not self.video_path or not os.path.exists(self.video_path):
            messagebox.showwarning("Warning", "Please load a video first")
            return
        
        # Explain the workflow
        response = messagebox.askyesno(
            "Consolidate IDs - Post-Analysis Tool",
            "The Consolidate IDs tool is used AFTER running the full video analysis.\n\n"
            "Workflow:\n"
            "1. Setup Wizard: Tag players (you are here)\n"
            "2. Export Seed Config: Save your initial mappings\n"
            "3. Run Full Analysis: Process entire video (creates CSV with tracking data)\n"
            "4. Consolidate IDs: Merge fragmented player tracks from the CSV\n\n"
            "Have you already run the full analysis and have a CSV file?\n\n"
            "If yes, the tool will help you merge duplicate player IDs.\n"
            "If no, please complete the analysis first."
        )
        if not response:
            return
        
        try:
            from consolidate_player_ids import IDConsolidationGUI
            
            consolidate_window = tk.Toplevel(self.root)
            consolidate_window.title("Consolidate Player IDs")
            consolidate_window.geometry("1200x800")
            consolidate_window.transient(self.root)
            
            # Ensure window opens on top
            consolidate_window.lift()
            consolidate_window.attributes('-topmost', True)
            consolidate_window.focus_force()
            consolidate_window.after(200, lambda: consolidate_window.attributes('-topmost', False))
            
            # Create consolidation GUI
            app = IDConsolidationGUI(consolidate_window)
            
            # Pre-load video if available
            if self.video_path:
                app.video_path = self.video_path
                app.video_path_entry.delete(0, tk.END)
                app.video_path_entry.insert(0, self.video_path)
            
            # Note: The Consolidate IDs tool needs the CSV from full analysis, not just seed mappings
            # The seed mappings help, but the actual consolidation works on the full tracking CSV
            messagebox.showinfo(
                "Consolidate IDs Tool",
                "The Consolidate IDs tool will open.\n\n"
                "To use it effectively:\n"
                "1. Load the CSV file from your full video analysis\n"
                "   (e.g., '[video_name]_tracking_data.csv')\n"
                "2. The tool will analyze fragmented player tracks\n"
                "3. You can merge duplicate IDs that represent the same player\n\n"
                "Your seed mappings from the Setup Wizard help identify which\n"
                "IDs should be merged, but the consolidation works on the full CSV."
            )
            
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import consolidate_player_ids.py: {str(e)}\n\n"
                               "Make sure consolidate_player_ids.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open consolidate IDs tool: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def on_reid_threshold_change(self, value=None):
        """Update Re-ID thresholds when slider changes"""
        self.reid_auto_tag_threshold = self.reid_auto_tag_var.get()
        self.reid_suggestion_threshold = self.reid_suggestion_var.get()
        
        # Update labels
        self.reid_auto_tag_label.config(text=f"{self.reid_auto_tag_threshold:.2f}")
        self.reid_suggestion_label.config(text=f"{self.reid_suggestion_threshold:.2f}")
        
        # Auto-refresh matching if video is loaded
        if self.current_frame is not None and self.current_detections is not None:
            self.refresh_reid_matching()
    
    def refresh_reid_matching(self):
        """Refresh Re-ID matching for current frame"""
        if self.current_frame is None:
            messagebox.showinfo("No Frame", "Please load a video and navigate to a frame first.")
            return
        
        if self.reid_tracker is None:
            messagebox.showwarning("Re-ID Not Available", "Re-ID tracker is not initialized. Please initialize detection first.")
            return
        
        # Clear existing suggestions
        self.gallery_suggestions = {}
        
        # Re-extract features and re-match
        self.extract_reid_features_for_frame(self.current_frame)
        self.match_detections_to_gallery(self.current_frame)
        
        # Update display and detections list
        self.update_detections_list()
        self.update_display()
        
        # Show status
        matched_count = len([tid for tid in self.gallery_suggestions.keys()])
        auto_tagged_count = len([tid for tid, (name, conf) in self.gallery_suggestions.items() 
                                if conf >= self.reid_auto_tag_threshold])
        
        if matched_count > 0:
            self.status_label.config(
                text=f"Re-ID: {auto_tagged_count} auto-tagged, {matched_count - auto_tagged_count} suggestions",
                foreground="green"
            )
        else:
            self.status_label.config(text="Re-ID refreshed - no matches found", foreground="gray")
    
    def toggle_reid_training(self):
        """Toggle Re-ID training mode"""
        self.reid_training_mode = not self.reid_training_mode
        
        if self.reid_training_mode:
            self.reid_training_button.config(text="🎓 Training Mode: ON")
            self.status_label.config(
                text="Training Mode: Select 2 detections to teach they're the same player",
                foreground="blue"
            )
            # Store first selection
            self.reid_training_first_selection = None
        else:
            self.reid_training_button.config(text="🎓 Training Mode: OFF")
            self.status_label.config(text="Training mode disabled", foreground="gray")
            self.reid_training_first_selection = None
    
    def train_reid_with_selection(self, frame_num1, track_id1, frame_num2, track_id2):
        """Train Re-ID by confirming two detections are the same player"""
        if self.reid_tracker is None:
            return
        
        try:
            import numpy as np
            
            # Get features for both detections
            features1 = None
            features2 = None
            
            # Get features from frame_reid_features
            if frame_num1 in self.frame_reid_features and track_id1 in self.frame_reid_features[frame_num1]:
                features1 = self.frame_reid_features[frame_num1][track_id1]
            if frame_num2 in self.frame_reid_features and track_id2 in self.frame_reid_features[frame_num2]:
                features2 = self.frame_reid_features[frame_num2][track_id2]
            
            # If features not cached, extract them
            if features1 is None:
                # Need to load frame and extract
                if self.cap is not None:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num1)
                    ret, frame1 = self.cap.read()
                    if ret:
                        # Find detection in that frame
                        if frame_num1 in self.detections_history:
                            detections1 = self.detections_history[frame_num1]
                            for i, tid in enumerate(detections1.tracker_id):
                                if tid == track_id1:
                                    bbox = detections1.xyxy[i]
                                    single_det = sv.Detections(
                                        xyxy=np.array([bbox]),
                                        confidence=np.array([1.0]),
                                        tracker_id=np.array([track_id1])
                                    )
                                    feats = self.reid_tracker.extract_features(frame1, single_det, None, None)
                                    if feats is not None and len(feats) > 0:
                                        features1 = feats[0]
                                        # Cache it
                                        if frame_num1 not in self.frame_reid_features:
                                            self.frame_reid_features[frame_num1] = {}
                                        self.frame_reid_features[frame_num1][track_id1] = features1
            
            if features2 is None:
                # Need to load frame and extract
                if self.cap is not None:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num2)
                    ret, frame2 = self.cap.read()
                    if ret:
                        # Find detection in that frame
                        if frame_num2 in self.detections_history:
                            detections2 = self.detections_history[frame_num2]
                            for i, tid in enumerate(detections2.tracker_id):
                                if tid == track_id2:
                                    bbox = detections2.xyxy[i]
                                    single_det = sv.Detections(
                                        xyxy=np.array([bbox]),
                                        confidence=np.array([1.0]),
                                        tracker_id=np.array([track_id2])
                                    )
                                    feats = self.reid_tracker.extract_features(frame2, single_det, None, None)
                                    if feats is not None and len(feats) > 0:
                                        features2 = feats[0]
                                        # Cache it
                                        if frame_num2 not in self.frame_reid_features:
                                            self.frame_reid_features[frame_num2] = {}
                                        self.frame_reid_features[frame_num2][track_id2] = features2
            
            # If we have both features, update player gallery
            if features1 is not None and features2 is not None:
                # Average the features to create a better representation
                if not isinstance(features1, np.ndarray):
                    features1 = np.array(features1)
                if not isinstance(features2, np.ndarray):
                    features2 = np.array(features2)
                
                # Average and normalize
                averaged_features = (features1 + features2) / 2.0
                averaged_features = averaged_features / (np.linalg.norm(averaged_features) + 1e-8)
                
                # Check if either track is already tagged
                tid1_str = str(int(track_id1))
                tid2_str = str(int(track_id2))
                
                player_name = None
                if tid1_str in self.approved_mappings:
                    mapping = self.approved_mappings[tid1_str]
                    if isinstance(mapping, tuple):
                        player_name = mapping[0]
                elif tid2_str in self.approved_mappings:
                    mapping = self.approved_mappings[tid2_str]
                    if isinstance(mapping, tuple):
                        player_name = mapping[0]
                
                # Create foot reference frames if we have foot features
                foot_ref_frame1 = None
                foot_ref_frame2 = None
                if averaged_foot_features is not None:
                    # Get foot bboxes from the detections
                    if frame_num1 in self.detections_history:
                        detections1 = self.detections_history[frame_num1]
                        for i, tid in enumerate(detections1.tracker_id):
                            if tid == track_id1:
                                bbox = detections1.xyxy[i]
                                x1, y1, x2, y2 = bbox
                                bbox_height = y2 - y1
                                foot_y1 = int(y1 + bbox_height * 0.60)
                                foot_y2 = int(y1 + bbox_height * 0.80)
                                foot_ref_frame1 = {
                                    "video_path": self.video_path,
                                    "frame_num": frame_num1,
                                    "bbox": [x1, foot_y1, x2, foot_y2]
                                }
                                break
                    
                    if frame_num2 in self.detections_history:
                        detections2 = self.detections_history[frame_num2]
                        for i, tid in enumerate(detections2.tracker_id):
                            if tid == track_id2:
                                bbox = detections2.xyxy[i]
                                x1, y1, x2, y2 = bbox
                                bbox_height = y2 - y1
                                foot_y1 = int(y1 + bbox_height * 0.60)
                                foot_y2 = int(y1 + bbox_height * 0.80)
                                foot_ref_frame2 = {
                                    "video_path": self.video_path,
                                    "frame_num": frame_num2,
                                    "bbox": [x1, foot_y1, x2, foot_y2]
                                }
                                break
                
                # Update gallery with averaged features (both upper and foot)
                if self.player_gallery is not None:
                    if player_name:
                        # Update existing player
                        player_id = player_name.lower().replace(" ", "_")
                        if player_id in self.player_gallery.players:
                            self.player_gallery.update_player(
                                player_id=player_id,
                                features=averaged_features,
                                foot_features=averaged_foot_features,
                                foot_reference_frame=foot_ref_frame1 if foot_ref_frame1 else foot_ref_frame2
                            )
                            if averaged_foot_features is not None:
                                print(f"✓ Updated Re-ID features (upper + foot) for '{player_name}' from training pair")
                            else:
                                print(f"✓ Updated Re-ID features for '{player_name}' from training pair")
                        else:
                            # Create new player
                            self.player_gallery.add_player(
                                name=player_name,
                                features=averaged_features
                            )
                            if averaged_foot_features is not None:
                                self.player_gallery.update_player(
                                    player_id=player_id,
                                    foot_features=averaged_foot_features,
                                    foot_reference_frame=foot_ref_frame1 if foot_ref_frame1 else foot_ref_frame2
                                )
                            print(f"✓ Created Re-ID profile for '{player_name}' from training pair")
                    else:
                        # Create temporary training entry
                        training_id = f"training_{len(self.reid_training_pairs)}"
                        self.player_gallery.add_player(
                            name=f"Training Player {len(self.reid_training_pairs) + 1}",
                            features=averaged_features
                        )
                        if averaged_foot_features is not None:
                            self.player_gallery.update_player(
                                player_id=training_id,
                                foot_features=averaged_foot_features,
                                foot_reference_frame=foot_ref_frame1 if foot_ref_frame1 else foot_ref_frame2
                            )
                        print(f"✓ Created training Re-ID profile from pair (Track {track_id1} ↔ Track {track_id2})")
                
                # Store training pair
                self.reid_training_pairs.append((frame_num1, track_id1, frame_num2, track_id2))
                
                # Refresh matching
                self.refresh_reid_matching()
                
                return True
        
        except Exception as e:
            print(f"⚠ Error training Re-ID: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return False
    
    def export_mappings_to_csv_for_consolidation(self):
        """Export current player mappings to a CSV file for consolidation tool"""
        # Create a simple CSV with frame, player_id, player_name
        # This is a simplified version - the consolidation tool will need actual tracking data
        output_file = "setup_wizard_mappings.csv"
        
        rows = []
        for track_id_str, mapping in self.approved_mappings.items():
            if isinstance(mapping, tuple):
                player_name = mapping[0]
                team = mapping[1] if len(mapping) > 1 else None
            else:
                player_name = mapping
                team = None
            
            # Create a basic entry (the consolidation tool will need full tracking data)
            rows.append({
                'frame': 0,  # Placeholder
                'player_id': int(track_id_str),
                'player_name': player_name,
                'team': team if team else ''
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(output_file, index=False)
    
    def next_frame(self):
        """Go to next frame"""
        if self.current_frame_num < self.total_frames - 1:
            self.current_frame_num += 1
            self.load_frame()
    
    def prev_frame(self):
        """Go to previous frame"""
        if self.current_frame_num > 0:
            self.current_frame_num -= 1
            self.load_frame()
    
    def go_to_first(self):
        """Go to first frame"""
        self.current_frame_num = 0
        self.load_frame()
    
    def go_to_last(self):
        """Go to last frame"""
        self.current_frame_num = max(0, self.total_frames - 1)
        self.load_frame()
    
    def toggle_playback(self):
        """Toggle play/pause"""
        if self.cap is None:
            return
        
        self.is_playing = not self.is_playing
        
        if self.is_playing:
            self.play_button.config(text="⏸ Pause")
            self.play()
        else:
            self.play_button.config(text="▶ Play")
    
    def play(self):
        """Start playback - continuously advance frames"""
        if not self.is_playing or self.cap is None:
            return
        
        # Advance to next frame
        if self.current_frame_num < self.total_frames - 1:
            self.current_frame_num += 1
            self.load_frame()
            
            # Schedule next frame based on FPS
            if self.fps > 0:
                delay_ms = int(1000 / self.fps)
            else:
                delay_ms = 33  # Default to ~30fps
            
            # Continue playback
            self.root.after(delay_ms, self.play)
        else:
            # Reached end of video - stop playback
            self.is_playing = False
            self.play_button.config(text="▶ Play")
    
    def on_slider_change(self, value):
        """Handle slider change"""
        frame_num = int(float(value))
        if frame_num != self.current_frame_num:
            self.current_frame_num = frame_num
            self.load_frame()
    
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
        
        # Get player info from current detections
        player_id = None
        player_name = None
        team = None
        position = None
        
        if self.current_detections:
            # Get first detection or selected detection
            detection = self.selected_detection if self.selected_detection else (self.current_detections[0] if self.current_detections else None)
            if detection:
                track_id = detection.get('track_id')
                if track_id and track_id in self.approved_mappings:
                    mapping = self.approved_mappings[track_id]
                    if isinstance(mapping, tuple):
                        player_name = mapping[0] if len(mapping) > 0 else None
                        team = mapping[1] if len(mapping) > 1 else None
                    else:
                        player_name = mapping
                    player_id = track_id
                
                # Get position from detection bbox
                if 'xyxy' in detection:
                    xyxy = detection['xyxy']
                    if len(xyxy) >= 4:
                        x_center = (xyxy[0] + xyxy[2]) / 2
                        y_center = (xyxy[1] + xyxy[3]) / 2
                        if self.width > 0 and self.height > 0:
                            position = (x_center / self.width, y_center / self.height)
        
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
        if not EVENT_MARKER_AVAILABLE or not self.event_marker_system:
            return
        
        markers = self.event_marker_system.get_markers_at_frame(self.current_frame_num)
        if not markers:
            messagebox.showinfo("No Markers", f"No event markers at frame {self.current_frame_num}")
            return
        
        if len(markers) == 1:
            event_type = markers[0].event_type
            self.event_marker_system.remove_marker(self.current_frame_num, event_type)
            messagebox.showinfo("Marker Removed", f"Removed {event_type.value} marker at frame {self.current_frame_num}")
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
        if not EVENT_MARKER_AVAILABLE or not self.event_marker_system:
            return
        
        if not self.event_marker_system.markers:
            messagebox.showinfo("No Markers", "No event markers to save")
            return
        
        if self.video_path:
            default_path = self.event_marker_system.save_to_file()
            messagebox.showinfo("Markers Saved", f"Saved {len(self.event_marker_system.markers)} markers to:\n{default_path}")
        else:
            filename = self._show_file_dialog(
                filedialog.asksaveasfilename,
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
                    self.update_timeline_display()
                    return
        
        filename = self._show_file_dialog(
            filedialog.askopenfilename,
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
        if not EVENT_MARKER_AVAILABLE or not self.event_marker_system:
            return
        
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
    
    def update_timeline_display(self):
        """Update the timeline slider to show event markers"""
        if not EVENT_MARKER_AVAILABLE or not self.event_marker_system:
            return
        
        if not self.event_marker_visible.get():
            return
        
        # Force slider update
        if hasattr(self, 'frame_slider'):
            self.on_slider_change(self.frame_var.get())


def main():
    root = tk.Tk()
    app = SetupWizard(root)
    root.mainloop()


if __name__ == "__main__":
    main()

