"""
Interactive Player Learning System

After analysis, this system identifies unknown/unassigned players and asks the user
to identify them. Once identified, it automatically propagates the assignment across
all frames where that player appears.

This is much faster than manually tagging many frames!
"""

import csv
import json
import os
import cv2
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import numpy as np


class InteractivePlayerLearner:
    """Interactive system for learning player identities from user input."""
    
    def __init__(self, csv_path: str, video_path: str, player_gallery_path: str = "player_gallery.json"):
        """
        Initialize the interactive learner.
        
        Args:
            csv_path: Path to tracking CSV file
            video_path: Path to video file (for showing frames)
            player_gallery_path: Path to player gallery JSON
        """
        self.csv_path = csv_path
        self.video_path = video_path
        self.player_gallery_path = player_gallery_path
        self.video_cap = None
        self.track_data = defaultdict(list)  # {track_id: [(frame, x, y, bbox), ...]}
        self.track_frames = {}  # {track_id: [frame_nums]}
        self.player_names = {}  # {track_id: player_name}
        self.player_teams = {}  # {track_id: team}
        self.known_players = set()  # Set of known player names
        self.unknown_tracks = []  # List of track_ids that need identification
        
    def load_tracking_data(self):
        """Load tracking data from CSV and identify unknown tracks."""
        print(f"📖 Loading tracking data from: {self.csv_path}")
        
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
        
        # Load existing player names from gallery
        self._load_known_players()
        
        # Load tracking data
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    frame_num = int(float(row.get('frame', 0)))
                    player_id = row.get('player_id', '').strip()
                    
                    if not player_id:
                        continue
                    
                    track_id = int(float(player_id))
                    player_x = float(row.get('player_x', 0))
                    player_y = float(row.get('player_y', 0))
                    
                    # Get bbox if available, otherwise estimate
                    bbox = None
                    if 'player_x' in row and 'player_y' in row:
                        # Estimate bbox size (default player size)
                        w, h = 80, 160
                        bbox = [player_x - w/2, player_y - h/2, player_x + w/2, player_y + h/2]
                    
                    self.track_data[track_id].append((frame_num, player_x, player_y, bbox))
                    
                    if track_id not in self.track_frames:
                        self.track_frames[track_id] = []
                    self.track_frames[track_id].append(frame_num)
                    
                except (ValueError, KeyError) as e:
                    continue
        
        # Identify unknown tracks (tracks without player names)
        for track_id in self.track_data.keys():
            if track_id not in self.player_names:
                # Check if this track appears in enough frames to be worth identifying
                if len(self.track_frames[track_id]) >= 30:  # At least 1 second at 30fps
                    self.unknown_tracks.append(track_id)
        
        # Sort by number of appearances (most frequent first)
        self.unknown_tracks.sort(key=lambda tid: len(self.track_frames[tid]), reverse=True)
        
        print(f"✓ Loaded {len(self.track_data)} tracks")
        print(f"✓ Found {len(self.unknown_tracks)} unknown tracks needing identification")
        print(f"✓ {len(self.known_players)} known players in gallery")
        
        return len(self.unknown_tracks)
    
    def _load_known_players(self):
        """Load known player names from player gallery."""
        # Try to load from player_gallery module first (if available)
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery(self.player_gallery_path)
            # gallery.load_gallery() is called in __init__, so players should already be loaded
            if gallery.players:
                for player_id, profile in gallery.players.items():
                    # profile is a PlayerProfile object, not a dict
                    name = getattr(profile, 'name', '') or ''
                    if isinstance(name, str):
                        name = name.strip()
                    else:
                        name = str(name).strip() if name else ''
                    
                    if name and name not in ['Unknown', 'Guest Player', '']:
                        self.known_players.add(name)
                        print(f"  ✓ Loaded player from gallery: {name}")
                        
                        # Check track_history for track-to-player mappings
                        track_history = getattr(profile, 'track_history', None)
                        if track_history:
                            if isinstance(track_history, dict):
                                for track_id_str, count in track_history.items():
                                    try:
                                        track_id = int(track_id_str)
                                        self.player_names[track_id] = name
                                        self.player_teams[track_id] = getattr(profile, 'team', '') or ''
                                    except (ValueError, TypeError):
                                        pass
                print(f"✓ Loaded {len(self.known_players)} players from PlayerGallery module")
                return
        except ImportError:
            print("⚠ PlayerGallery module not available, using JSON fallback")
        except Exception as e:
            print(f"⚠ Error loading from PlayerGallery module: {e}")
            import traceback
            traceback.print_exc()
        
        # Fallback: Load directly from JSON file
        if not os.path.exists(self.player_gallery_path):
            print(f"⚠ Player gallery file not found: {self.player_gallery_path}")
            print(f"  Looking for players in: {os.path.abspath(self.player_gallery_path)}")
            return
        
        try:
            with open(self.player_gallery_path, 'r', encoding='utf-8') as f:
                gallery_data = json.load(f)
            
            # JSON structure: flat dict {player_id: player_data} or nested {players: {player_id: player_data}}
            players_dict = gallery_data.get('players', gallery_data) if isinstance(gallery_data, dict) else {}
            
            if not players_dict:
                # If it's a flat dict, use it directly
                if isinstance(gallery_data, dict) and gallery_data:
                    players_dict = gallery_data
            
            for player_id, profile in players_dict.items():
                # Handle both dict and PlayerProfile-like objects
                if isinstance(profile, dict):
                    name = profile.get('name', '') or ''
                else:
                    name = getattr(profile, 'name', '') or ''
                
                if isinstance(name, str):
                    name = name.strip()
                else:
                    name = str(name).strip() if name else ''
                
                # Include all named players (not just non-Unknown)
                if name and name not in ['Unknown', 'Guest Player', '']:
                    self.known_players.add(name)
                    print(f"  ✓ Loaded player from JSON: {name}")
                    
                    # Check track_history for track-to-player mappings
                    track_history = profile.get('track_history', {}) if isinstance(profile, dict) else getattr(profile, 'track_history', {})
                    if track_history and isinstance(track_history, dict):
                        for track_id_str, count in track_history.items():
                            try:
                                track_id = int(track_id_str)
                                self.player_names[track_id] = name
                                team = profile.get('team', '') if isinstance(profile, dict) else getattr(profile, 'team', '')
                                self.player_teams[track_id] = team or ''
                            except (ValueError, TypeError):
                                pass
            print(f"✓ Loaded {len(self.known_players)} players from JSON gallery")
        except Exception as e:
            print(f"⚠ Error loading player gallery: {e}")
            import traceback
            traceback.print_exc()
    
    def get_representative_frame(self, track_id: int) -> Optional[Tuple[int, np.ndarray]]:
        """
        Get a representative frame showing this track.
        
        Returns:
            (frame_num, frame_image) or None if video can't be opened
        """
        if not self.video_cap:
            self.video_cap = cv2.VideoCapture(self.video_path)
            if not self.video_cap.isOpened():
                return None
        
        # Get middle frame of track (usually best visibility)
        frames = self.track_frames[track_id]
        if not frames:
            return None
        
        # Use middle frame or frame with most detections
        mid_frame = frames[len(frames) // 2]
        
        self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = self.video_cap.read()
        
        if ret:
            return (mid_frame, frame)
        return None
    
    def show_player_identification_dialog(self, track_id: int, frame_image: np.ndarray, frame_num: int) -> Optional[Tuple[str, str]]:
        """
        Show dialog asking user to identify a player.
        
        Returns:
            (player_name, team) or None if cancelled
        """
        dialog = tk.Toplevel()
        dialog.title(f"Identify Player - Track #{track_id}")
        dialog.geometry("1000x750")
        dialog.transient()
        dialog.grab_set()
        
        result = {'player_name': None, 'team': None, 'cancelled': False, 'stop_learning': False}
        
        # Store original frame for zoom/pan
        original_frame_rgb = cv2.cvtColor(frame_image, cv2.COLOR_BGR2RGB)
        
        # Find player position and bbox in this frame
        player_pos = None
        player_bbox = None
        for fnum, x, y, bbox in self.track_data[track_id]:
            if fnum == frame_num:
                player_pos = (int(x), int(y))
                if bbox:
                    player_bbox = [int(b) for b in bbox]
                break
        
        # Create enhanced highlight frame with focus effect
        def create_highlighted_frame(zoom_level=1.0, pan_x=0, pan_y=0):
            """Create frame with enhanced highlighting and zoom/pan"""
            # Start with original frame
            frame_rgb = original_frame_rgb.copy()
            frame_h, frame_w = frame_rgb.shape[:2]
            
            # Draw enhanced highlight on player
            if player_bbox:
                x1, y1, x2, y2 = player_bbox
                # Draw glowing highlight box (multiple layers for glow effect)
                for thickness in [8, 6, 4, 2]:
                    alpha = 0.3 / (thickness // 2)
                    overlay = frame_rgb.copy()
                    cv2.rectangle(overlay, (x1-thickness, y1-thickness), (x2+thickness, y2+thickness), 
                                (0, 255, 255), thickness)  # Cyan glow
                    frame_rgb = cv2.addWeighted(frame_rgb, 1-alpha, overlay, alpha, 0)
                
                # Draw main highlight box
                cv2.rectangle(frame_rgb, (x1, y1), (x2, y2), (0, 255, 255), 4)  # Bright cyan
                
                # Draw center point
                center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
                cv2.circle(frame_rgb, (center_x, center_y), 8, (0, 255, 255), -1)
                cv2.circle(frame_rgb, (center_x, center_y), 12, (255, 255, 0), 2)  # Yellow outer ring
                
                # Add focus effect: darken everything except player region
                mask = np.zeros((frame_h, frame_w), dtype=np.uint8)
                cv2.rectangle(mask, (max(0, x1-20), max(0, y1-20)), 
                            (min(frame_w, x2+20), min(frame_h, y2+20)), 255, -1)
                mask = cv2.GaussianBlur(mask, (101, 101), 0)  # Soft edge
                mask = mask.astype(np.float32) / 255.0
                mask = np.stack([mask, mask, mask], axis=2)
                
                # Darken non-focus areas
                darkened = (frame_rgb * 0.3).astype(np.uint8)
                frame_rgb = (frame_rgb * mask + darkened * (1 - mask)).astype(np.uint8)
            
            elif player_pos:
                # Fallback: use circle if no bbox
                cv2.circle(frame_rgb, player_pos, 60, (0, 255, 255), 6)  # Outer glow
                cv2.circle(frame_rgb, player_pos, 50, (255, 255, 0), 4)  # Inner highlight
                cv2.circle(frame_rgb, player_pos, 8, (0, 255, 255), -1)  # Center point
            
            # Apply zoom with better interpolation
            if zoom_level != 1.0:
                new_w = int(frame_w * zoom_level)
                new_h = int(frame_h * zoom_level)
                if new_w > 0 and new_h > 0:
                    # Use better interpolation for higher zoom levels
                    if zoom_level > 3.0:
                        interpolation = cv2.INTER_CUBIC
                    elif zoom_level > 1.5:
                        interpolation = cv2.INTER_LINEAR
                    else:
                        interpolation = cv2.INTER_LINEAR
                    frame_rgb = cv2.resize(frame_rgb, (new_w, new_h), interpolation=interpolation)
                    frame_h, frame_w = frame_rgb.shape[:2]
                    
                    # Apply pan offset (crop from zoomed frame)
                    if pan_x != 0 or pan_y != 0:
                        # Calculate visible region (centered on pan point)
                        center_x = frame_w // 2
                        center_y = frame_h // 2
                        crop_w = int(frame_w / zoom_level)
                        crop_h = int(frame_h / zoom_level)
                        
                        crop_x1 = max(0, center_x - crop_w // 2 + int(pan_x))
                        crop_y1 = max(0, center_y - crop_h // 2 + int(pan_y))
                        crop_x2 = min(frame_w, crop_x1 + crop_w)
                        crop_y2 = min(frame_h, crop_y1 + crop_h)
                        
                        if crop_x2 > crop_x1 and crop_y2 > crop_y1:
                            frame_rgb = frame_rgb[crop_y1:crop_y2, crop_x1:crop_x2]
                            # Resize back to maintain aspect ratio
                            if frame_rgb.shape[0] > 0 and frame_rgb.shape[1] > 0:
                                frame_rgb = cv2.resize(frame_rgb, (crop_w, crop_h), interpolation=cv2.INTER_LINEAR)
            
            return frame_rgb
        
        # Initial frame
        display_frame = create_highlighted_frame()
        display_frame = cv2.resize(display_frame, (800, 450))  # Initial display size
        
        # Convert to PhotoImage
        try:
            from PIL import Image, ImageTk
            img = Image.fromarray(display_frame)
            photo = ImageTk.PhotoImage(image=img)
        except ImportError:
            # Fallback: use tkinter's PhotoImage (limited to GIF/PPM)
            import io
            import base64
            # Convert to PPM format
            _, buffer = cv2.imencode('.ppm', display_frame)
            photo = tk.PhotoImage(data=buffer.tobytes())
        
        # Zoom and pan state
        zoom_level = 1.0
        pan_x = 0
        pan_y = 0
        is_panning = False
        pan_start_x = 0
        pan_start_y = 0
        
        # Video canvas with zoom/pan support
        video_frame = ttk.Frame(dialog)
        video_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(video_frame, bg="black", width=800, height=450)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        canvas_image_id = canvas.create_image(400, 225, anchor=tk.CENTER, image=photo)
        canvas.image_ref = photo  # Keep reference
        
        def update_canvas():
            """Update canvas with current zoom/pan"""
            nonlocal photo
            frame_rgb = create_highlighted_frame(zoom_level, pan_x, pan_y)
            
            # Resize to fit canvas
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            if canvas_width > 1 and canvas_height > 1:
                frame_h, frame_w = frame_rgb.shape[:2]
                scale_w = canvas_width / frame_w
                scale_h = canvas_height / frame_h
                scale = min(scale_w, scale_h)
                new_w = int(frame_w * scale)
                new_h = int(frame_h * scale)
                if new_w > 0 and new_h > 0:
                    frame_rgb = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            try:
                from PIL import Image, ImageTk
                img = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(image=img)
            except ImportError:
                _, buffer = cv2.imencode('.ppm', frame_rgb)
                photo = tk.PhotoImage(data=buffer.tobytes())
            
            canvas.itemconfig(canvas_image_id, image=photo)
            canvas.image_ref = photo
        
        # Zoom and pan event handlers
        def on_canvas_wheel(event):
            nonlocal zoom_level, pan_x, pan_y
            if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
                zoom_factor = 1.3  # Increased from 1.15 for more aggressive zoom
            elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
                zoom_factor = 0.77  # Increased from 0.87 (1/1.3) for matching zoom out
            else:
                return
            
            old_zoom = zoom_level
            zoom_level *= zoom_factor
            zoom_level = max(0.5, min(10.0, zoom_level))  # Increased max from 4.0 to 10.0
            
            # Adjust pan to zoom towards mouse
            canvas_x = event.x
            canvas_y = event.y
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            offset_x = canvas_x - canvas_width // 2
            offset_y = canvas_y - canvas_height // 2
            
            if old_zoom != zoom_level:
                zoom_ratio = zoom_level / old_zoom
                pan_x = (pan_x - offset_x) * zoom_ratio + offset_x
                pan_y = (pan_y - offset_y) * zoom_ratio + offset_y
                update_canvas()
        
        def on_canvas_click(event):
            nonlocal is_panning, pan_start_x, pan_start_y
            if zoom_level > 1.0:
                is_panning = True
                pan_start_x = event.x
                pan_start_y = event.y
        
        def on_canvas_drag(event):
            nonlocal pan_x, pan_y, pan_start_x, pan_start_y
            if is_panning and zoom_level > 1.0:
                delta_x = event.x - pan_start_x
                delta_y = event.y - pan_start_y
                pan_x += delta_x
                pan_y += delta_y
                pan_start_x = event.x
                pan_start_y = event.y
                update_canvas()
        
        def on_canvas_release(event):
            nonlocal is_panning
            is_panning = False
        
        def on_canvas_right_click(event):
            nonlocal zoom_level, pan_x, pan_y
            zoom_level = 1.0
            pan_x = 0
            pan_y = 0
            update_canvas()
        
        # Bind events
        canvas.bind("<MouseWheel>", on_canvas_wheel)
        canvas.bind("<Button-4>", on_canvas_wheel)
        canvas.bind("<Button-5>", on_canvas_wheel)
        canvas.bind("<Button-1>", on_canvas_click)
        canvas.bind("<B1-Motion>", on_canvas_drag)
        canvas.bind("<ButtonRelease-1>", on_canvas_release)
        canvas.bind("<Button-3>", on_canvas_right_click)
        
        # Zoom/Pan instructions
        zoom_label = tk.Label(dialog, text="🔍 Zoom: Mouse wheel | Pan: Click & drag | Reset: Right-click", 
                             font=("Arial", 8), fg="gray")
        zoom_label.pack(pady=(0, 5))
        
        # Info label with focus indicator
        info_frame = ttk.Frame(dialog)
        info_frame.pack(pady=5, padx=10, fill=tk.X)
        info_label = tk.Label(info_frame, 
                             text=f"🎯 FOCUS: Track #{track_id} | {len(self.track_frames[track_id])} frames | Frame {frame_num}", 
                             font=("Arial", 11, "bold"), fg="darkblue", bg="lightyellow")
        info_label.pack(fill=tk.X, pady=2)
        
        # Main content area: Player list on left, input on right
        main_content = ttk.Frame(dialog)
        main_content.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        # Left side: Large player listbox for quick selection
        left_panel = ttk.LabelFrame(main_content, text="🎯 Select Player (Double-click to assign)", padding="10")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Large scrollable listbox for player selection
        listbox_frame = ttk.Frame(left_panel)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        player_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, height=18, width=35, 
                                   exportselection=False, font=("Arial", 11), selectmode=tk.SINGLE)
        player_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=player_listbox.yview)
        
        # Populate with known players
        known_players_sorted = sorted(self.known_players) if self.known_players else []
        if known_players_sorted:
            for player in known_players_sorted:
                player_listbox.insert(tk.END, player)
            print(f"✓ Populated player listbox with {len(known_players_sorted)} players")
        else:
            # Show helpful message if no players loaded
            player_listbox.insert(tk.END, "⚠ No players found in gallery")
            player_listbox.insert(tk.END, "")
            player_listbox.insert(tk.END, "Please add players to the Player")
            player_listbox.insert(tk.END, "Gallery first, or enter manually.")
            player_listbox.insert(tk.END, "")
            player_listbox.insert(tk.END, f"Gallery path: {self.player_gallery_path}")
            player_listbox.config(state=tk.DISABLED)  # Disable selection if empty
            print(f"⚠ No players loaded! Gallery path: {os.path.abspath(self.player_gallery_path)}")
        
        # Right side: Manual input and team selection
        right_panel = ttk.LabelFrame(main_content, text="Or Enter Manually", padding="10")
        right_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 0))
        right_panel.config(width=300)
        
        # Player name input
        name_frame = ttk.Frame(right_panel)
        name_frame.pack(pady=10, padx=5, fill=tk.X)
        ttk.Label(name_frame, text="Player Name:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        name_var = tk.StringVar()
        name_entry = ttk.Entry(name_frame, textvariable=name_var, width=30, font=("Arial", 11))
        name_entry.pack(fill=tk.X)
        name_entry.focus()
        
        # Team selection
        team_frame = ttk.Frame(right_panel)
        team_frame.pack(pady=10, padx=5, fill=tk.X)
        ttk.Label(team_frame, text="Team:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        team_var = tk.StringVar()
        team_combo = ttk.Combobox(team_frame, textvariable=team_var, width=28, 
                                  values=["Gray", "Blue", "Red", "White", "Other"], font=("Arial", 10))
        team_combo.pack(fill=tk.X)
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        def on_assign():
            name = name_var.get().strip()
            team = team_var.get().strip()
            if name:
                result['player_name'] = name
                result['team'] = team if team else ""
                dialog.destroy()
            else:
                messagebox.showwarning("Missing Name", "Please enter a player name.")
        
        def on_skip():
            result['cancelled'] = True
            dialog.destroy()
        
        # Bind player listbox handlers (after on_assign is defined)
        def on_player_listbox_select(event=None):
            selection = player_listbox.curselection()
            if selection:
                selected = player_listbox.get(selection[0])
                name_var.set(selected)
                name_entry.delete(0, tk.END)
                name_entry.insert(0, selected)
        
        def on_player_listbox_double_click(event=None):
            on_player_listbox_select()
            on_assign()  # Auto-assign on double-click
        
        player_listbox.bind('<<ListboxSelect>>', on_player_listbox_select)
        player_listbox.bind('<Double-Button-1>', on_player_listbox_double_click)
        
        # Also allow typing to search/filter in listbox
        def on_name_entry_change(*args):
            """When user types, try to find matching player in listbox"""
            typed = name_var.get().lower()
            if typed and known_players_sorted:
                # Find first match
                for i, player in enumerate(known_players_sorted):
                    if player.lower().startswith(typed):
                        player_listbox.selection_clear(0, tk.END)
                        player_listbox.selection_set(i)
                        player_listbox.see(i)
                        break
        
        name_var.trace('w', on_name_entry_change)
        
        def on_stop_learning():
            """Stop the entire learning process"""
            result['stop_learning'] = True
            result['cancelled'] = True
            dialog.destroy()
        
        ttk.Button(button_frame, text="Assign", command=on_assign).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Skip", command=on_skip).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Stop Learning", command=on_stop_learning).pack(side=tk.LEFT, padx=5)
        
        # Wait for user response
        dialog.wait_window()
        
        # Check if user wants to stop entire process
        if result.get('stop_learning', False):
            return 'STOP_LEARNING'  # Special return value to signal stop
        
        if result['cancelled']:
            return None
        return (result['player_name'], result['team']) if result['player_name'] else None
    
    def propagate_assignment(self, track_id: int, player_name: str, team: str):
        """
        Propagate player assignment to all frames where this track appears.
        Updates player_names and player_teams dictionaries.
        """
        self.player_names[track_id] = player_name
        self.player_teams[track_id] = team
        self.known_players.add(player_name)
        
        print(f"  ✓ Assigned '{player_name}' to Track #{track_id} ({len(self.track_frames[track_id])} frames)")
    
    def save_assignments(self, output_csv: Optional[str] = None):
        """
        Save player assignments back to CSV (creates new CSV with player names).
        
        Args:
            output_csv: Output CSV path (default: adds '_with_names' suffix)
        """
        if output_csv is None:
            base = Path(self.csv_path).stem
            output_csv = str(Path(self.csv_path).parent / f"{base}_with_names.csv")
        
        print(f"💾 Saving assignments to: {output_csv}")
        
        # Read original CSV and add player names
        rows = []
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                
                if not fieldnames:
                    print(f"⚠ Error: CSV file has no column headers: {self.csv_path}")
                    return None
                
                print(f"📊 CSV has {len(fieldnames)} columns: {', '.join(fieldnames[:10])}{'...' if len(fieldnames) > 10 else ''}")
                
                row_count = 0
                for row in reader:
                    row_count += 1
                    try:
                        player_id = row.get('player_id', row.get('track_id', ''))
                        if player_id:
                            # Handle both string and numeric player_id
                            player_id_str = str(player_id).strip()
                            if player_id_str:
                                track_id = int(float(player_id_str))
                                if track_id in self.player_names:
                                    # Add player_name and team columns if they don't exist
                                    row['player_name'] = self.player_names[track_id]
                                    row['team'] = self.player_teams.get(track_id, '')
                    except (ValueError, KeyError, TypeError) as e:
                        # Keep the row even if we can't process it (preserve all data)
                        pass
                    
                    rows.append(row)
                
                print(f"📊 Read {row_count} rows from CSV")
        except Exception as e:
            print(f"❌ Error reading CSV: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        # Write updated CSV
        if not rows:
            print(f"⚠ Warning: No rows to save! CSV might be empty.")
            return None
        
        try:
            with open(output_csv, 'w', encoding='utf-8', newline='') as f:
                if fieldnames:
                    # Add player_name and team to fieldnames if not present
                    fieldnames_list = list(fieldnames) if fieldnames else []
                    if 'player_name' not in fieldnames_list:
                        fieldnames_list.append('player_name')
                    if 'team' not in fieldnames_list:
                        fieldnames_list.append('team')
                    
                    writer = csv.DictWriter(f, fieldnames=fieldnames_list, extrasaction='ignore')
                    writer.writeheader()
                    writer.writerows(rows)
                    
                    print(f"✓ Saved {len(rows)} rows with player assignments")
                    print(f"✓ Output file: {output_csv}")
                    print(f"✓ File size: {os.path.getsize(output_csv):,} bytes")
                    return output_csv
                else:
                    print(f"❌ Error: No fieldnames available to write CSV")
                    return None
        except Exception as e:
            print(f"❌ Error writing CSV: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def run_interactive_learning(self, max_players: int = 20):
        """
        Run the interactive learning process.
        
        Args:
            max_players: Maximum number of players to ask about (default: 20)
        """
        root = tk.Tk()
        root.withdraw()  # Hide main window
        
        assigned_count = 0
        skipped_count = 0
        
        print(f"\n🎓 Starting Interactive Player Learning")
        print(f"   Will ask about up to {min(max_players, len(self.unknown_tracks))} unknown players")
        print(f"   (Press 'Skip' to skip a player, 'Stop Learning' to finish early)\n")
        
        for i, track_id in enumerate(self.unknown_tracks[:max_players]):
            print(f"\n[{i+1}/{min(max_players, len(self.unknown_tracks))}] Identifying Track #{track_id}...")
            
            # Get representative frame
            frame_data = self.get_representative_frame(track_id)
            if not frame_data:
                print(f"  ⚠ Could not load frame for Track #{track_id}, skipping...")
                skipped_count += 1
                continue
            
            frame_num, frame_image = frame_data
            
            # Show identification dialog
            assignment = self.show_player_identification_dialog(track_id, frame_image, frame_num)
            
            # Check if user wants to stop entire learning process
            if assignment == 'STOP_LEARNING':
                print(f"\n⏹ User stopped learning process")
                break
            
            if assignment is None:
                print(f"  ⏭ Skipped Track #{track_id}")
                skipped_count += 1
                continue
            
            player_name, team = assignment
            
            # Propagate assignment
            self.propagate_assignment(track_id, player_name, team)
            assigned_count += 1
        
        # Cleanup
        if self.video_cap:
            self.video_cap.release()
        
        print(f"\n✅ Interactive Learning Complete!")
        print(f"   Assigned: {assigned_count} players")
        print(f"   Skipped: {skipped_count} players")
        
        return assigned_count, skipped_count


def run_interactive_learning_gui(csv_path: str, video_path: str, player_gallery_path: str = "player_gallery.json"):
    """
    Run interactive learning via GUI.
    
    Args:
        csv_path: Path to tracking CSV
        video_path: Path to video file
        player_gallery_path: Path to player gallery JSON
    """
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    try:
        learner = InteractivePlayerLearner(csv_path, video_path, player_gallery_path)
        unknown_count = learner.load_tracking_data()
        
        if unknown_count == 0:
            messagebox.showinfo("No Unknown Players", 
                              "All tracks already have player names assigned!\n\n"
                              "No learning needed.")
            return
        
        # Ask user how many players to identify
        max_players = tk.simpledialog.askinteger(
            "Interactive Learning",
            f"Found {unknown_count} unknown tracks.\n\n"
            f"How many players would you like to identify?\n"
            f"(Recommended: 10-20 for best results)",
            minvalue=1,
            maxvalue=unknown_count,
            initialvalue=min(20, unknown_count)
        )
        
        if max_players is None:
            return
        
        # Run learning
        assigned, skipped = learner.run_interactive_learning(max_players=max_players)
        
        if assigned > 0:
            # Ask to save
            save = messagebox.askyesno(
                "Save Assignments",
                f"Successfully assigned {assigned} players!\n\n"
                f"Would you like to save the assignments to a new CSV file?"
            )
            
            if save:
                output_file = filedialog.asksaveasfilename(
                    title="Save CSV with Player Names",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )
                
                if output_file:
                    learner.save_assignments(output_file)
                    messagebox.showinfo("Success", 
                                      f"Assignments saved to:\n{output_file}\n\n"
                                      f"You can now use this CSV for future analysis.")
        else:
            messagebox.showinfo("No Assignments", 
                              "No players were assigned.\n\n"
                              "You can run this again later.")
    
    except Exception as e:
        messagebox.showerror("Error", f"Error during interactive learning:\n{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python interactive_player_learning.py <csv_file> <video_file> [player_gallery.json]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    video_path = sys.argv[2]
    gallery_path = sys.argv[3] if len(sys.argv) > 3 else "player_gallery.json"
    
    run_interactive_learning_gui(csv_path, video_path, gallery_path)

