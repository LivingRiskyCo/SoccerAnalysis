"""
Track Review & Player Assignment Tool

This tool allows you to:
1. Review all tracks from a completed analysis (CSV file)
2. Assign player names to track IDs
3. Convert those assignments to anchor frames

This is MUCH faster than manual frame-by-frame tagging!
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pandas as pd
import json
import os
# Path and defaultdict are not used - removed to fix unused import warnings
import cv2
import numpy as np
from PIL import Image, ImageTk
import threading
from datetime import datetime

# Import Re-ID and gallery modules
try:
    from reid_tracker import ReIDTracker
    from player_gallery import PlayerGallery
    try:
        from supervision import Detections
        SUPERVISION_AVAILABLE = True  # type: ignore[reportConstantRedefinition]  # Set in try/except block
    except ImportError:
        SUPERVISION_AVAILABLE = False  # type: ignore[reportConstantRedefinition]  # Set in try/except block
        Detections = None
except ImportError as e:
    print(f"Warning: Could not import Re-ID modules: {e}")
    ReIDTracker = None
    PlayerGallery = None
    SUPERVISION_AVAILABLE = False  # type: ignore[reportConstantRedefinition]  # Set in try/except block
    Detections = None


class TrackReviewAssigner:
    def __init__(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Track Review & Player Assignment")
        self.root.geometry("1400x900")
        
        self.csv_file = None
        self.video_file = None
        self.tracks_data = None
        self.player_gallery = None
        self.track_assignments = {}  # {track_id: player_name}
        
        # Video viewer state
        self.video_cap = None
        self.current_frame_num = 0
        self.current_track_id = None
        self.current_track_index = None  # Store listbox index to preserve selection
        self.track_frame_list = []  # List of frame numbers where current track appears
        self.track_frame_index = 0  # Current index in track_frame_list
        
        # Zoom and pan state
        self.zoom_level = 1.0  # Current zoom level (1.0 = fit to canvas)
        self.pan_x = 0  # Pan offset in x direction
        self.pan_y = 0  # Pan offset in y direction
        self.is_panning = False  # Whether user is currently panning
        self.pan_start_x = 0  # Starting x position for pan
        self.pan_start_y = 0  # Starting y position for pan
        self.original_frame = None  # Store original frame before zoom/pan transformations
        
        # Post-processing state
        self.auto_corrections = {}  # {track_id: correction_dict}
        self.pending_corrections = {}  # {track_id: correction_dict}
        self.reid_tracker = None  # ReIDTracker instance for gallery matching
        self.player_gallery_obj = None  # PlayerGallery instance
        self.analysis_in_progress = False
        self.corrections_listbox_track_ids = []  # Maps listbox indices to track IDs
        self.current_selected_track_ids_for_update = []  # Store selected track IDs for update operations
        self.assigned_player_manually_edited = False  # Track if user has manually edited the combobox
        
        self.setup_ui()
        self.load_player_gallery()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Create notebook for tabs (Review and Post-Process)
        self.main_notebook = ttk.Notebook(self.root)
        self.main_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Review & Assignment (existing functionality)
        review_tab = ttk.Frame(self.main_notebook, padding="10")
        self.main_notebook.add(review_tab, text="Review & Assignment")
        
        # Top frame for file selection
        top_frame = ttk.Frame(review_tab, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="1. Load Analysis CSV:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.csv_label = ttk.Label(top_frame, text="No CSV loaded", foreground="gray")
        self.csv_label.grid(row=0, column=1, sticky=tk.W, padx=10)
        ttk.Button(top_frame, text="Browse...", command=self.load_csv).grid(row=0, column=2, padx=5)
        
        ttk.Label(top_frame, text="2. Load Video (required for viewer):", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.video_label = ttk.Label(top_frame, text="No video loaded", foreground="gray")
        self.video_label.grid(row=1, column=1, sticky=tk.W, padx=10)
        ttk.Button(top_frame, text="Browse...", command=self.load_video).grid(row=1, column=2, padx=5)
        
        # Main content area
        main_frame = ttk.Frame(review_tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel: Track list
        left_panel = ttk.LabelFrame(main_frame, text="Tracks", padding="10")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
        left_panel.config(width=300)
        
        # Track list with scrollbar
        list_frame = ttk.Frame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.track_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=20)
        self.track_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.track_listbox.bind('<<ListboxSelect>>', self.on_track_select)
        scrollbar.config(command=self.track_listbox.yview)
        
        # Track info
        info_frame = ttk.LabelFrame(left_panel, text="Track Info", padding="10")
        info_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.track_info_text = scrolledtext.ScrolledText(info_frame, height=8, wrap=tk.WORD)
        self.track_info_text.pack(fill=tk.BOTH, expand=True)
        
        # Center panel: Video viewer
        center_panel = ttk.LabelFrame(main_frame, text="Video Viewer - See Player on Track", padding="10")
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # Video canvas
        self.video_canvas = tk.Canvas(center_panel, bg="black", width=640, height=360)
        self.video_canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Bind zoom and pan events
        self.video_canvas.bind("<MouseWheel>", self.on_canvas_wheel)  # Windows/Mac
        self.video_canvas.bind("<Button-4>", self.on_canvas_wheel)  # Linux scroll up
        self.video_canvas.bind("<Button-5>", self.on_canvas_wheel)  # Linux scroll down
        self.video_canvas.bind("<Button-1>", self.on_canvas_click)  # Left click for pan
        self.video_canvas.bind("<B1-Motion>", self.on_canvas_drag)  # Drag for pan
        self.video_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)  # Release pan
        self.video_canvas.bind("<Button-3>", self.on_canvas_right_click)  # Right click to reset zoom/pan
        
        # Frame navigation controls
        nav_frame = ttk.Frame(center_panel)
        nav_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(nav_frame, text="◄◄ First", command=self.go_to_first_frame, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="◄ Prev", command=self.go_to_prev_frame, width=12).pack(side=tk.LEFT, padx=2)
        self.frame_label = ttk.Label(nav_frame, text="Frame: 0 / 0", width=20)
        self.frame_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(nav_frame, text="Next ►", command=self.go_to_next_frame, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="Last ►►", command=self.go_to_last_frame, width=12).pack(side=tk.LEFT, padx=2)
        
        # Zoom and pan controls
        zoom_frame = ttk.Frame(center_panel)
        zoom_frame.pack(fill=tk.X, pady=5)
        ttk.Label(zoom_frame, text="Zoom: Mouse wheel | Pan: Click & drag | Reset: Right-click", 
                  font=("Arial", 8), foreground="gray").pack(side=tk.LEFT, padx=5)
        ttk.Button(zoom_frame, text="Reset Zoom/Pan", command=self.reset_zoom_pan, width=15).pack(side=tk.RIGHT, padx=2)
        
        # Right panel: Player assignment
        right_panel = ttk.LabelFrame(main_frame, text="Assign Player to Track", padding="10")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        right_panel.config(width=300)
        
        ttk.Label(right_panel, text="Selected Track ID:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=5)
        self.selected_track_label = ttk.Label(right_panel, text="None", font=("Arial", 10))
        self.selected_track_label.pack(anchor=tk.W, pady=5)
        
        ttk.Label(right_panel, text="Assign Player Name:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(10, 5))
        
        # Player name listbox (more reliable than combobox for selection)
        player_list_frame = ttk.Frame(right_panel)
        player_list_frame.pack(fill=tk.BOTH, expand=False, pady=5)
        player_list_frame.config(height=250)  # Increased height for listbox to reduce scrolling
        
        # Scrollbar for player list
        player_scrollbar = ttk.Scrollbar(player_list_frame)
        player_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox for player selection - increased height to show more players
        self.player_listbox = tk.Listbox(player_list_frame, yscrollcommand=player_scrollbar.set, height=12, width=25, exportselection=False)
        self.player_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        player_scrollbar.config(command=self.player_listbox.yview)
        self.player_listbox.bind('<<ListboxSelect>>', self.on_player_listbox_select)
        self.player_listbox.bind('<Double-Button-1>', lambda e: self.assign_player())
        
        # Also keep the combobox for backward compatibility (hidden)
        self.player_var = tk.StringVar()
        self.player_combo = ttk.Combobox(right_panel, textvariable=self.player_var, width=25, state="normal")
        self.player_combo.pack_forget()  # Hide combobox, use listbox instead
        self.player_combo.bind('<<ComboboxSelected>>', self.on_player_select)
        
        # Or enter custom name
        ttk.Label(right_panel, text="Or enter custom name:", font=("Arial", 9)).pack(anchor=tk.W, pady=(10, 5))
        self.custom_player_var = tk.StringVar()
        custom_entry = ttk.Entry(right_panel, textvariable=self.custom_player_var, width=25)
        custom_entry.pack(fill=tk.X, pady=5)
        custom_entry.bind('<Return>', lambda e: self.assign_player())
        
        # Assign button
        ttk.Button(right_panel, text="Assign Player to Track", command=self.assign_player, width=25).pack(pady=10)
        
        # Clear assignment button
        ttk.Button(right_panel, text="Clear Assignment", command=self.clear_assignment, width=25).pack(pady=5)
        
        # Assignment summary
        summary_frame = ttk.LabelFrame(right_panel, text="Assignments", padding="10")
        summary_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.summary_text = scrolledtext.ScrolledText(summary_frame, height=10, wrap=tk.WORD)
        self.summary_text.pack(fill=tk.BOTH, expand=True)
        
        # Bottom buttons
        bottom_frame = ttk.Frame(review_tab, padding="10")
        bottom_frame.pack(fill=tk.X)
        
        ttk.Button(bottom_frame, text="Save to CSV", 
                   command=self.save_to_csv, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="Save Assignments as Anchor Frames", 
                   command=self.save_as_anchor_frames, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="Export Assignments (JSON)", 
                   command=self.export_assignments, width=25).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="Close", command=self.root.destroy, width=15).pack(side=tk.RIGHT, padx=5)
        
        # Tab 2: Post-Process
        postprocess_tab = ttk.Frame(self.main_notebook, padding="10")
        self.main_notebook.add(postprocess_tab, text="Post-Process")
        self.setup_postprocess_ui(postprocess_tab)
    
    def load_player_gallery(self):
        """Load player names from gallery"""
        try:
            gallery_path = "player_gallery.json"
            if os.path.exists(gallery_path):
                with open(gallery_path, 'r') as f:
                    gallery_data = json.load(f)
                    self.player_gallery = gallery_data
                    
                    # Player gallery can be a dict with 'players' key or direct dict of player_id -> profile
                    players = []
                    if isinstance(gallery_data, dict):
                        if 'players' in gallery_data:
                            # Old format: {'players': [list of players]}
                            for p in gallery_data['players']:
                                if isinstance(p, dict) and p.get('name'):
                                    players.append(p.get('name'))
                        else:
                            # New format: {player_id: {profile dict}}
                            for player_id, profile in gallery_data.items():
                                if isinstance(profile, dict) and profile.get('name'):
                                    players.append(profile.get('name'))
                    
                    player_values = sorted(set(players)) if players else []
                    
                    # Populate listbox
                    self.player_listbox.delete(0, tk.END)
                    for player in player_values:
                        self.player_listbox.insert(tk.END, player)
                    
                    # Also populate combobox for backward compatibility
                    self.player_combo['values'] = player_values
                    self.player_combo.config(state="normal")
                    
                    if len(player_values) > 0:
                        print(f"Loaded {len(player_values)} players into player list")
            else:
                self.player_listbox.delete(0, tk.END)
                self.player_combo['values'] = []
                self.player_combo.config(state="normal")
        except Exception as e:
            print(f"Error loading player gallery: {e}")
            self.player_listbox.delete(0, tk.END)
            self.player_combo['values'] = []
            self.player_combo.config(state="normal")
    
    def load_csv(self, file_path=None):
        """Load tracking CSV file"""
        if file_path is None:
            file_path = filedialog.askopenfilename(
                title="Select Tracking CSV File",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
        
        if not file_path:
            return
        
        # Check if file is JSON (anchor frames file) instead of CSV
        if file_path.lower().endswith('.json') or 'PlayerTagsSeed' in os.path.basename(file_path):
            messagebox.showerror(
                "Wrong File Type",
                f"This tool requires a CSV tracking data file, not an anchor frames JSON file.\n\n"
                f"You selected: {os.path.basename(file_path)}\n\n"
                f"Anchor frames JSON files are used during analysis, not in Track Review.\n\n"
                f"Please select a CSV file (e.g., '*_tracking_data.csv' or '*_consolidated.csv')"
            )
            return
        
        try:
            print(f"🔍 DEBUG: Loading CSV from: {file_path}")
            # Load CSV
            self.tracks_data = pd.read_csv(file_path)
            print(f"🔍 DEBUG: CSV loaded successfully. Shape: {self.tracks_data.shape}")
            print(f"🔍 DEBUG: Columns: {list(self.tracks_data.columns)}")
            self.csv_file = file_path
            self.csv_label.config(text=os.path.basename(file_path), foreground="black")
            
            # CRITICAL FIX: Convert frame columns to numeric to prevent type errors
            for col in ['frame', 'frame_num', 'frame_number']:
                if col in self.tracks_data.columns:
                    self.tracks_data[col] = pd.to_numeric(self.tracks_data[col], errors='coerce')
            
            # CRITICAL FIX: Convert track_id columns to numeric/int for consistency
            # Store original column name for reference
            self.track_id_col_original = None
            for col in ['track_id', 'player_id', 'id']:
                if col in self.tracks_data.columns:
                    self.track_id_col_original = col
                    # Try to convert to numeric, but keep original for fallback
                    try:
                        # Create a numeric version but keep original
                        numeric_col = pd.to_numeric(self.tracks_data[col], errors='coerce')
                        # Only replace if conversion was successful for most values
                        if numeric_col.notna().sum() > len(numeric_col) * 0.5:  # At least 50% converted
                            self.tracks_data[col] = numeric_col
                    except (ValueError, TypeError):
                        pass  # Keep as string if conversion fails
            
            # Get unique track IDs
            track_id_col = None
            for col in ['track_id', 'player_id', 'id']:
                if col in self.tracks_data.columns:
                    track_id_col = col
                    break
            
            if track_id_col is None:
                messagebox.showerror("Error", "CSV file must contain 'track_id', 'player_id', or 'id' column")
                return
            
            # Get unique tracks - CRITICAL FIX: Convert to numeric first, then sort
            print(f"🔍 DEBUG: Getting unique tracks from column '{track_id_col}'...")
            try:
                print(f"🔍 DEBUG:   Column dtype: {self.tracks_data[track_id_col].dtype}")
                print(f"🔍 DEBUG:   Sample values: {self.tracks_data[track_id_col].iloc[:5].tolist()}")
                track_ids_numeric = pd.to_numeric(self.tracks_data[track_id_col], errors='coerce')
                print(f"🔍 DEBUG:   After numeric conversion dtype: {track_ids_numeric.dtype}")
                print(f"🔍 DEBUG:   Sample numeric values: {track_ids_numeric.iloc[:5].tolist()}")
                unique_tracks_raw = track_ids_numeric.dropna().unique()
                print(f"🔍 DEBUG:   Unique tracks (raw): {unique_tracks_raw[:10]} (showing first 10)")
                print(f"🔍 DEBUG:   Unique tracks types: {[type(t) for t in unique_tracks_raw[:5]]}")
                unique_tracks = sorted(unique_tracks_raw)
                print(f"🔍 DEBUG:   After sorting: {unique_tracks[:10]} (showing first 10)")
                # Convert to int for consistency
                unique_tracks = [int(t) for t in unique_tracks if pd.notna(t)]
                print(f"🔍 DEBUG:   After int conversion: {unique_tracks[:10]} (showing first 10)")
            except (ValueError, TypeError) as e:
                print(f"🔍 DEBUG:   ERROR in track ID processing: {e}")
                print(f"🔍 DEBUG:   Error type: {type(e)}")
                import traceback
                print(f"🔍 DEBUG:   Traceback:\n{traceback.format_exc()}")
                # Fallback: try direct conversion
                try:
                    print(f"🔍 DEBUG:   Trying fallback conversion...")
                    unique_tracks_raw = self.tracks_data[track_id_col].dropna().unique()
                    print(f"🔍 DEBUG:   Fallback raw values: {unique_tracks_raw[:10]}")
                    unique_tracks = sorted([int(float(t)) for t in unique_tracks_raw if str(t).strip()])
                    print(f"🔍 DEBUG:   Fallback successful: {unique_tracks[:10]}")
                except (ValueError, TypeError) as e2:
                    print(f"🔍 DEBUG:   Fallback also failed: {e2}")
                    import traceback
                    print(f"🔍 DEBUG:   Fallback traceback:\n{traceback.format_exc()}")
                    messagebox.showerror("Error", f"Could not convert track IDs to numeric: {e}\n\nFallback also failed: {e2}")
                    return
            
            # Load existing player_name assignments from CSV if present
            print(f"🔍 DEBUG: Loading existing player_name assignments...")
            if 'player_name' in self.tracks_data.columns:
                # CRITICAL FIX: Use numeric version of track_id_col for comparisons
                print(f"🔍 DEBUG:   Creating numeric version of track_id_col for comparisons...")
                try:
                    track_id_col_numeric = pd.to_numeric(self.tracks_data[track_id_col], errors='coerce')
                    print(f"🔍 DEBUG:   Numeric column dtype: {track_id_col_numeric.dtype}")
                    for track_id in unique_tracks[:5]:  # Debug first 5 only
                        print(f"🔍 DEBUG:   Processing track_id: {track_id} (type={type(track_id)})")
                        track_id_int = int(track_id)  # Already int, but ensure it
                        print(f"🔍 DEBUG:     Converted to int: {track_id_int} (type={type(track_id_int)})")
                        try:
                            track_data = self.tracks_data[track_id_col_numeric == track_id_int]
                            print(f"🔍 DEBUG:     Filtered {len(track_data)} rows")
                            player_names = track_data['player_name'].dropna().unique()
                            if len(player_names) > 0:
                                player_name = str(player_names[0]).strip()
                                if player_name and player_name not in ['Guest Player', 'None', '']:
                                    self.track_assignments[track_id_int] = player_name
                                    print(f"🔍 DEBUG:     Assigned: {player_name}")
                        except Exception as e:
                            print(f"🔍 DEBUG:     ERROR filtering track_id {track_id_int}: {e}")
                            import traceback
                            print(f"🔍 DEBUG:     Traceback:\n{traceback.format_exc()}")
                    # Process remaining tracks without debug output
                    for track_id in unique_tracks[5:]:
                        track_id_int = int(track_id)
                        track_data = self.tracks_data[track_id_col_numeric == track_id_int]
                        player_names = track_data['player_name'].dropna().unique()
                        if len(player_names) > 0:
                            player_name = str(player_names[0]).strip()
                            if player_name and player_name not in ['Guest Player', 'None', '']:
                                self.track_assignments[track_id_int] = player_name
                except Exception as e:
                    print(f"🔍 DEBUG:   ERROR in player_name assignment loading: {e}")
                    import traceback
                    print(f"🔍 DEBUG:   Traceback:\n{traceback.format_exc()}")
            
            # Populate track list with visual indicators
            print(f"🔍 DEBUG: Populating track listbox...")
            self.track_listbox.delete(0, tk.END)
            
            # Configure colors for tagged/untagged tracks
            self.track_listbox.config(selectbackground='#4A90E2', selectforeground='white')
            
            print(f"🔍 DEBUG:   Processing {len(unique_tracks)} tracks for listbox...")
            for i, track_id in enumerate(unique_tracks):
                if i < 5:  # Debug first 5
                    print(f"🔍 DEBUG:     Processing track {i}: {track_id} (type={type(track_id)})")
                try:
                    track_id_int = int(track_id)  # Already int, but ensure it
                    if i < 5:
                        print(f"🔍 DEBUG:       Converted to int: {track_id_int} (type={type(track_id_int)})")
                    # Check if track is assigned
                    if track_id_int in self.track_assignments:
                        player_name = self.track_assignments[track_id_int]
                        display_text = f"Track #{track_id_int} ✓ {player_name}"
                        self.track_listbox.insert(tk.END, display_text)
                        # Tag as assigned (we'll use itemconfig for colors)
                        # CRITICAL FIX: Use size() - 1 instead of tk.END - 1 (tk.END is a string, not an int)
                        last_index = self.track_listbox.size() - 1
                        self.track_listbox.itemconfig(last_index, {'bg': '#d4edda', 'fg': '#155724'})  # Light green background
                    else:
                        display_text = f"Track #{track_id_int}"
                        self.track_listbox.insert(tk.END, display_text)
                        # Tag as unassigned
                        # CRITICAL FIX: Use size() - 1 instead of tk.END - 1 (tk.END is a string, not an int)
                        last_index = self.track_listbox.size() - 1
                        self.track_listbox.itemconfig(last_index, {'bg': 'white', 'fg': 'black'})
                except Exception as e:
                    print(f"🔍 DEBUG:       ERROR processing track {track_id}: {e}")
                    import traceback
                    print(f"🔍 DEBUG:       Traceback:\n{traceback.format_exc()}")
                    # Continue with next track
                    continue
            
            print(f"🔍 DEBUG: Counting loaded assignments...")
            try:
                loaded_count = len([t for t in unique_tracks if int(t) in self.track_assignments])
                print(f"🔍 DEBUG:   Loaded count: {loaded_count}")
            except Exception as e:
                print(f"🔍 DEBUG:   ERROR counting assignments: {e}")
                import traceback
                print(f"🔍 DEBUG:   Traceback:\n{traceback.format_exc()}")
                loaded_count = 0
            
            print(f"🔍 DEBUG: CSV loading complete!")
            messagebox.showinfo("Success", 
                f"Loaded {len(unique_tracks)} tracks from CSV\n"
                f"({loaded_count} tracks already have player assignments)")
            self.update_summary()
            
        except Exception as e:
            print(f"🔍 DEBUG: FATAL ERROR in load_csv: {e}")
            print(f"🔍 DEBUG: Error type: {type(e)}")
            import traceback
            print(f"🔍 DEBUG: Full traceback:\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"Could not load CSV: {e}\n\nCheck console for detailed debug output.")
    
    def load_video(self, file_path=None):
        """Load video file for preview"""
        if file_path is None:
            file_path = filedialog.askopenfilename(
                title="Select Video File",
                filetypes=[("Video files", "*.mp4 *.avi *.mov"), ("All files", "*.*")]
            )
        
        if file_path:
            # Close existing video if open
            if self.video_cap is not None:
                self.video_cap.release()
            
            self.video_file = file_path
            self.video_label.config(text=os.path.basename(file_path), foreground="black")
            
            # Open video
            try:
                self.video_cap = cv2.VideoCapture(file_path)
                if not self.video_cap.isOpened():
                    messagebox.showerror("Error", "Could not open video file")
                    self.video_cap = None
                else:
                    # If a track is selected, show it
                    if self.current_track_id is not None:
                        self.show_track_frame(self.current_track_id)
            except Exception as e:
                messagebox.showerror("Error", f"Could not load video: {e}")
                self.video_cap = None
    
    def on_track_select(self, event):
        """Handle track selection"""
        selection = self.track_listbox.curselection()
        if not selection:
            return
        
        track_index = selection[0]
        track_id = self.get_track_id_from_index(track_index)
        
        if track_id is None:
            return
        
        # Store both track_id and index to preserve selection
        self.current_track_id = track_id
        self.current_track_index = track_index
        self.selected_track_label.config(text=f"Track #{int(track_id)}")
        
        # Show track info
        self.show_track_info(track_id)
        
        # Show video frame with this track
        self.show_track_frame(track_id)
        
        # Show current assignment if any
        if track_id in self.track_assignments:
            assigned_player = self.track_assignments[track_id]
            self.player_var.set(assigned_player)
            self.custom_player_var.set(assigned_player)
        else:
            self.player_var.set("")
            self.custom_player_var.set("")
    
    def get_track_id_from_index(self, index):
        """Get track ID from listbox index"""
        if self.tracks_data is None:
            return None
        
        track_id_col = None
        for col in ['track_id', 'player_id', 'id']:
            if col in self.tracks_data.columns:
                track_id_col = col
                break
        
        if track_id_col is None:
            return None
        
        # CRITICAL FIX: Convert to numeric before sorting
        try:
            track_ids_numeric = pd.to_numeric(self.tracks_data[track_id_col], errors='coerce')
            unique_tracks = sorted(track_ids_numeric.dropna().unique())
            unique_tracks = [int(t) for t in unique_tracks if pd.notna(t)]
        except (ValueError, TypeError):
            # Fallback: try direct conversion
            try:
                unique_tracks_raw = self.tracks_data[track_id_col].dropna().unique()
                unique_tracks = sorted([int(float(t)) for t in unique_tracks_raw if str(t).strip()])
            except (ValueError, TypeError):
                return None
        
        if index < len(unique_tracks):
            return unique_tracks[index]
        return None
    
    def show_track_info(self, track_id):
        """Show information about the selected track"""
        if self.tracks_data is None:
            return
        
        track_id_col = None
        for col in ['track_id', 'player_id', 'id']:
            if col in self.tracks_data.columns:
                track_id_col = col
                break
        
        if track_id_col is None:
            return
        
        # Filter data for this track - CRITICAL FIX: Use numeric comparison
        try:
            track_id_col_numeric = pd.to_numeric(self.tracks_data[track_id_col], errors='coerce')
            track_data = self.tracks_data[track_id_col_numeric == int(track_id)]
        except (ValueError, TypeError):
            # Fallback: direct comparison
            track_data = self.tracks_data[self.tracks_data[track_id_col] == track_id]
        
        self.track_info_text.delete(1.0, tk.END)
        
        info = f"Track ID: {int(track_id)}\n"
        info += f"Total frames: {len(track_data)}\n"
        
        # Find frame column
        frame_col = None
        for col in ['frame', 'frame_num', 'frame_number']:
            if col in track_data.columns:
                frame_col = col
                break
        
        if frame_col:
            # CRITICAL FIX: Ensure frame numbers are numeric before operations
            try:
                frame_values = pd.to_numeric(track_data[frame_col], errors='coerce').dropna()
                if len(frame_values) > 0:
                    first_frame = int(frame_values.min())
                    last_frame = int(frame_values.max())
                    info += f"Frame range: {first_frame} - {last_frame}\n"
                    info += f"Duration: {last_frame - first_frame} frames\n"
            except (ValueError, TypeError) as e:
                # If conversion fails, skip frame info
                pass
        
        if 'player_x' in track_data.columns and 'player_y' in track_data.columns:
            avg_x = track_data['player_x'].mean()
            avg_y = track_data['player_y'].mean()
            info += f"Average position: ({avg_x:.1f}, {avg_y:.1f})\n"
        
        if 'confidence' in track_data.columns:
            avg_conf = track_data['confidence'].mean()
            info += f"Average confidence: {avg_conf:.3f}\n"
        
        if track_id in self.track_assignments:
            info += f"\n✅ Assigned to: {self.track_assignments[track_id]}\n"
        else:
            info += f"\n⚠ Not yet assigned\n"
        
        self.track_info_text.insert(1.0, info)
    
    def show_track_frame(self, track_id):
        """Show a video frame with the selected track highlighted"""
        if self.video_cap is None or self.tracks_data is None:
            return
        
        # Get track data
        track_id_col = None
        for col in ['track_id', 'player_id', 'id']:
            if col in self.tracks_data.columns:
                track_id_col = col
                break
        
        if track_id_col is None:
            return
        
        # CRITICAL FIX: Use numeric comparison to avoid type mismatches
        try:
            track_id_col_numeric = pd.to_numeric(self.tracks_data[track_id_col], errors='coerce')
            track_data = self.tracks_data[track_id_col_numeric == int(track_id)]
        except (ValueError, TypeError):
            # Fallback: direct comparison
            track_data = self.tracks_data[self.tracks_data[track_id_col] == track_id]
        
        if len(track_data) == 0:
            return
        
        # Get list of frames where this track appears
        frame_col = None
        for col in ['frame', 'frame_num', 'frame_number']:
            if col in track_data.columns:
                frame_col = col
                break
        
        if frame_col is not None:
            # Ensure we work with a pandas Series, not a numpy array
            frame_series = track_data[frame_col]
            if not isinstance(frame_series, pd.Series):
                frame_series = pd.Series(frame_series)
            # CRITICAL FIX: Convert to numeric first, then to int
            try:
                frame_series_numeric = pd.to_numeric(frame_series, errors='coerce')
                self.track_frame_list = sorted(frame_series_numeric.dropna().unique().astype(int).tolist())
            except (ValueError, TypeError) as e:
                # If conversion fails, try direct conversion
                try:
                    self.track_frame_list = sorted([int(float(x)) for x in frame_series.dropna().unique() if str(x).strip()])
                except (ValueError, TypeError):
                    self.track_frame_list = []

            if len(self.track_frame_list) == 0:
                return
        # Start at first frame
        self.track_frame_index = 0
        self.display_frame(self.track_frame_list[0], track_id)
    
    def display_frame(self, frame_num, track_id):
        """Display a specific frame with track highlighted"""
        if self.video_cap is None:
            return
        
        # Seek to frame
        self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.video_cap.read()
        
        if not ret:
            return
        
        self.current_frame_num = frame_num
        
        # Get track data for this frame
        track_id_col = None
        for col in ['track_id', 'player_id', 'id']:
            if col in self.tracks_data.columns:
                track_id_col = col
                break
        
        if track_id_col is None:
            return
        
        # Get bbox for this track at this frame
        frame_col = None
        for col in ['frame', 'frame_num', 'frame_number']:
            if col in self.tracks_data.columns:
                frame_col = col
                break
        
        if frame_col:
            # CRITICAL FIX: Ensure frame_num comparison works with mixed types
            try:
                # Convert frame_col to numeric for comparison
                frame_col_numeric = pd.to_numeric(self.tracks_data[frame_col], errors='coerce')
                track_data = self.tracks_data[
                    (self.tracks_data[track_id_col] == track_id) & 
                    (frame_col_numeric == frame_num)
                ]
            except (ValueError, TypeError):
                # Fallback: try direct comparison (may work if types match)
                try:
                    track_id_col_numeric = pd.to_numeric(self.tracks_data[track_id_col], errors='coerce')
                    track_data = self.tracks_data[
                        (track_id_col_numeric == int(track_id)) & 
                        (self.tracks_data[frame_col] == frame_num)
                    ]
                except (ValueError, TypeError):
                    track_data = self.tracks_data[
                        (self.tracks_data[track_id_col] == track_id) & 
                        (self.tracks_data[frame_col] == frame_num)
                    ]
        else:
            # No frame column - just get first row for this track - CRITICAL FIX: Use numeric comparison
            try:
                track_id_col_numeric = pd.to_numeric(self.tracks_data[track_id_col], errors='coerce')
                track_data = self.tracks_data[track_id_col_numeric == int(track_id)]
            except (ValueError, TypeError):
                track_data = self.tracks_data[self.tracks_data[track_id_col] == track_id]
        
        if len(track_data) > 0:
            row = track_data.iloc[0]
            
            # Draw bounding box
            bbox = None
            if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                x1, y1, x2, y2 = int(row['x1']), int(row['y1']), int(row['x2']), int(row['y2'])
                bbox = (x1, y1, x2, y2)
            elif 'player_x' in row and 'player_y' in row:
                # Convert center to bbox
                cx, cy = float(row['player_x']), float(row['player_y'])
                bbox = (int(cx - 40), int(cy - 60), int(cx + 40), int(cy + 60))
            
            if bbox:
                x1, y1, x2, y2 = bbox
                # Draw thick green box for selected track
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                
                # Draw foot/base region highlight (bottom 20-40% of bbox - where shoes are)
                bbox_height = y2 - y1
                foot_y1 = int(y1 + bbox_height * 0.60)  # Start at 60% from top
                foot_y2 = int(y1 + bbox_height * 0.80)  # End at 80% from top
                # Draw cyan box for foot region
                cv2.rectangle(frame, (x1, foot_y1), (x2, foot_y2), (255, 255, 0), 2)  # Cyan for foot region
                
                # Draw track ID and player name
                label = f"Track #{int(track_id)}"
                if track_id in self.track_assignments:
                    label += f" - {self.track_assignments[track_id]}"
                
                # Draw label background
                (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cv2.rectangle(frame, (x1, y1 - text_height - 10), (x1 + text_width, y1), (0, 255, 0), -1)
                cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                
                # Draw foot region label
                foot_label = "Foot/Shoe Region"
                (foot_text_width, foot_text_height), _ = cv2.getTextSize(foot_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x1, foot_y1 - foot_text_height - 5), (x1 + foot_text_width, foot_y1), (255, 255, 0), -1)
                cv2.putText(frame, foot_label, (x1, foot_y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        # Store original frame for zoom/pan
        self.original_frame = frame.copy()
        
        # Resize frame to fit canvas (base scale)
        canvas_width = self.video_canvas.winfo_width()
        canvas_height = self.video_canvas.winfo_height()
        
        if canvas_width > 1 and canvas_height > 1:
            # Calculate base scaling to fit canvas
            frame_h, frame_w = frame.shape[:2]
            scale_w = canvas_width / frame_w
            scale_h = canvas_height / frame_h
            base_scale = min(scale_w, scale_h)
            
            # Apply zoom level
            actual_scale = base_scale * self.zoom_level
            new_w = int(frame_w * actual_scale)
            new_h = int(frame_h * actual_scale)
            
            # Resize frame
            if new_w > 0 and new_h > 0:
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            else:
                return  # Invalid size
            
            # Convert BGR to RGB for tkinter
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img_tk = ImageTk.PhotoImage(image=img)
            
            # Calculate position with pan offset
            # Center the image, then apply pan offset
            img_x = canvas_width // 2 + self.pan_x
            img_y = canvas_height // 2 + self.pan_y
            
            # Update canvas
            self.video_canvas.delete("all")
            self.video_canvas.create_image(img_x, img_y, anchor=tk.CENTER, image=img_tk)
            
            # Keep a reference to prevent garbage collection
            if not hasattr(self, '_canvas_images'):
                self._canvas_images = []
            self._canvas_images.append(img_tk)  # Keep reference
            if len(self._canvas_images) > 5:  # Limit stored images
                self._canvas_images.pop(0)
        
        # Update frame label
        self.frame_label.config(text=f"Frame: {frame_num} ({self.track_frame_index + 1}/{len(self.track_frame_list)})")
    
    def on_canvas_wheel(self, event):
        """Handle mouse wheel for zoom"""
        if self.original_frame is None or self.current_track_id is None:
            return
        
        # Determine zoom direction
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            # Zoom in
            zoom_factor = 1.1
        elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
            # Zoom out
            zoom_factor = 0.9
        else:
            return
        
        # Get mouse position relative to canvas
        canvas_x = self.video_canvas.canvasx(event.x)
        canvas_y = self.video_canvas.canvasy(event.y)
        canvas_width = self.video_canvas.winfo_width()
        canvas_height = self.video_canvas.winfo_height()
        
        # Calculate zoom center relative to image center
        old_zoom = self.zoom_level
        self.zoom_level *= zoom_factor
        self.zoom_level = max(0.1, min(5.0, self.zoom_level))  # Limit zoom between 0.1x and 5x
        
        # Adjust pan to zoom towards mouse position
        if old_zoom != self.zoom_level:
            # Calculate offset from canvas center
            offset_x = canvas_x - canvas_width // 2
            offset_y = canvas_y - canvas_height // 2
            
            # Adjust pan to maintain zoom point
            zoom_ratio = self.zoom_level / old_zoom
            self.pan_x = (self.pan_x - offset_x) * zoom_ratio + offset_x
            self.pan_y = (self.pan_y - offset_y) * zoom_ratio + offset_y
            
            # Redraw frame with new zoom/pan
            self.display_frame(self.current_frame_num, self.current_track_id)
    
    def on_canvas_click(self, event):
        """Handle mouse click for pan start"""
        if self.zoom_level > 1.0:  # Only allow panning when zoomed in
            self.is_panning = True
            self.pan_start_x = event.x
            self.pan_start_y = event.y
    
    def on_canvas_drag(self, event):
        """Handle mouse drag for panning"""
        if self.is_panning and self.zoom_level > 1.0:
            # Calculate pan delta
            delta_x = event.x - self.pan_start_x
            delta_y = event.y - self.pan_start_y
            
            # Update pan offset
            self.pan_x += delta_x
            self.pan_y += delta_y
            
            # Update start position for next drag
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            
            # Redraw frame with new pan
            self.display_frame(self.current_frame_num, self.current_track_id)
    
    def on_canvas_release(self, event):
        """Handle mouse release for pan end"""
        self.is_panning = False
    
    def on_canvas_right_click(self, event):
        """Handle right click to reset zoom and pan"""
        self.reset_zoom_pan()
    
    def reset_zoom_pan(self):
        """Reset zoom and pan to default values"""
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.is_panning = False
        
        # Redraw frame
        if self.current_track_id is not None:
            self.display_frame(self.current_frame_num, self.current_track_id)
    
    def go_to_first_frame(self):
        """Go to first frame of current track"""
        if self.current_track_id is not None and len(self.track_frame_list) > 0:
            self.track_frame_index = 0
            self.display_frame(self.track_frame_list[0], self.current_track_id)
    
    def go_to_prev_frame(self):
        """Go to previous frame of current track"""
        if self.current_track_id is not None and len(self.track_frame_list) > 0:
            if self.track_frame_index > 0:
                self.track_frame_index -= 1
                self.display_frame(self.track_frame_list[self.track_frame_index], self.current_track_id)
    
    def go_to_next_frame(self):
        """Go to next frame of current track"""
        if self.current_track_id is not None and len(self.track_frame_list) > 0:
            if self.track_frame_index < len(self.track_frame_list) - 1:
                self.track_frame_index += 1
                self.display_frame(self.track_frame_list[self.track_frame_index], self.current_track_id)
    
    def go_to_last_frame(self):
        """Go to last frame of current track"""
        if self.current_track_id is not None and len(self.track_frame_list) > 0:
            self.track_frame_index = len(self.track_frame_list) - 1
            self.display_frame(self.track_frame_list[self.track_frame_index], self.current_track_id)
    
    def on_player_listbox_select(self, event):
        """Handle player selection from listbox"""
        selection = self.player_listbox.curselection()
        if selection:
            player_name = self.player_listbox.get(selection[0])
            self.player_var.set(player_name)
            self.custom_player_var.set(player_name)
            
            # Preserve track selection when player is selected
            if self.current_track_index is not None:
                self.track_listbox.selection_clear(0, tk.END)
                self.track_listbox.selection_set(self.current_track_index)
                self.track_listbox.see(self.current_track_index)
    
    def on_player_select(self, event):
        """Handle player selection from combobox (if used)"""
        player_name = self.player_var.get()
        if player_name:
            self.custom_player_var.set(player_name)
        
        # Preserve track selection when player is selected
        # Restore listbox selection if we have a stored track
        if self.current_track_index is not None:
            self.track_listbox.selection_clear(0, tk.END)
            self.track_listbox.selection_set(self.current_track_index)
            self.track_listbox.see(self.current_track_index)
    
    def assign_player(self):
        """Assign selected player to selected track"""
        # Use stored track_id if available, otherwise try to get from selection
        if self.current_track_id is not None:
            track_id = self.current_track_id
        else:
            selection = self.track_listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a track first")
                return
            track_id = self.get_track_id_from_index(selection[0])
            if track_id is None:
                return
        
        # Get player name (from dropdown or custom entry)
        player_name = self.player_var.get() or self.custom_player_var.get()
        
        if not player_name:
            messagebox.showwarning("Warning", "Please select or enter a player name")
            return
        
        # Assign
        self.track_assignments[track_id] = player_name
        messagebox.showinfo("Success", f"Assigned '{player_name}' to Track #{int(track_id)}")
        
        # Update visual indicator in listbox
        self.update_track_listbox_display()
        
        # Preserve track selection in listbox
        if self.current_track_index is not None:
            self.track_listbox.selection_clear(0, tk.END)
            self.track_listbox.selection_set(self.current_track_index)
            self.track_listbox.see(self.current_track_index)
        
        # Update UI
        self.show_track_info(track_id)
        self.update_summary()
        
        # Refresh video display to show new assignment
        if track_id == self.current_track_id:
            self.display_frame(self.current_frame_num, track_id)
    
    def clear_assignment(self):
        """Clear assignment for selected track"""
        # Use stored track_id if available
        if self.current_track_id is not None:
            track_id = self.current_track_id
        else:
            selection = self.track_listbox.curselection()
            if not selection:
                return
            track_id = self.get_track_id_from_index(selection[0])
        
        if track_id and track_id in self.track_assignments:
            del self.track_assignments[track_id]
            
            # Update visual indicator in listbox
            self.update_track_listbox_display()
            
            self.show_track_info(track_id)
            self.update_summary()
            
            # Clear player name fields
            self.player_var.set("")
            self.custom_player_var.set("")
            
            # Preserve track selection
            if self.current_track_index is not None:
                self.track_listbox.selection_clear(0, tk.END)
                self.track_listbox.selection_set(self.current_track_index)
                self.track_listbox.see(self.current_track_index)
            
            # Refresh video display
            if track_id == self.current_track_id:
                self.display_frame(self.current_frame_num, track_id)
    
    def update_summary(self):
        """Update assignment summary"""
        self.summary_text.delete(1.0, tk.END)
        
        if not self.track_assignments:
            self.summary_text.insert(1.0, "No assignments yet.\n\nSelect tracks and assign player names.")
            return
        
        summary = f"Total assignments: {len(self.track_assignments)}\n\n"
        
        for track_id, player_name in sorted(self.track_assignments.items()):
            summary += f"Track #{int(track_id)} → {player_name}\n"
        
        self.summary_text.insert(1.0, summary)
    
    def save_as_anchor_frames(self):
        """Save assignments as anchor frames JSON file"""
        if not self.track_assignments:
            messagebox.showwarning("Warning", "No assignments to save")
            return
        
        if self.tracks_data is None:
            messagebox.showerror("Error", "No CSV data loaded")
            return
        
        # Auto-generate filename based on video name if available
        default_filename = "PlayerTagsSeed_track_review.json"
        if self.video_file:
            video_basename = os.path.splitext(os.path.basename(self.video_file))[0]
            # Extract part number or use full name
            default_filename = f"PlayerTagsSeed_{video_basename}.json"
        
        # Ask for output file
        output_file = filedialog.asksaveasfilename(
            title="Save Anchor Frames As",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=default_filename,
            initialdir=os.path.dirname(self.video_file) if self.video_file else None
        )
        
        if not output_file:
            return
        
        try:
            # Build anchor frames from assignments
            anchor_frames = {}
            track_id_col = None
            for col in ['track_id', 'player_id', 'id']:
                if col in self.tracks_data.columns:
                    track_id_col = col
                    break
            
            if track_id_col is None:
                messagebox.showerror("Error", "Could not find track ID column")
                return
            
            # Group by frame and track_id
            for track_id, player_name in self.track_assignments.items():
                track_data = self.tracks_data[self.tracks_data[track_id_col] == track_id]
                
                # Get team and jersey_number from player gallery if available
                team = None
                jersey_number = None
                
                # Try PlayerGallery object first (preferred - has full profile data)
                if self.player_gallery_obj is not None:
                    try:
                        player_id = player_name.lower().replace(" ", "_")
                        if hasattr(self.player_gallery_obj, 'get_player'):
                            profile = self.player_gallery_obj.get_player(player_id)
                            if profile:
                                if hasattr(profile, 'team'):
                                    team = profile.team
                                if hasattr(profile, 'jersey_number'):
                                    jersey_number = profile.jersey_number
                    except Exception as e:
                        # Fall through to dict format
                        pass
                
                # Fallback to dict format if PlayerGallery object didn't work
                if team is None or jersey_number is None:
                    if self.player_gallery:
                        if isinstance(self.player_gallery, dict):
                            if 'players' in self.player_gallery:
                                # Old format
                                for player in self.player_gallery.get('players', []):
                                    if isinstance(player, dict) and player.get('name') == player_name:
                                        if team is None:
                                            team = player.get('team')
                                        if jersey_number is None:
                                            jersey_number = player.get('jersey_number')
                                        break
                            else:
                                # New format: {player_id: {profile}}
                                for player_id, profile in self.player_gallery.items():
                                    if isinstance(profile, dict) and profile.get('name') == player_name:
                                        if team is None:
                                            team = profile.get('team')
                                        if jersey_number is None:
                                            jersey_number = profile.get('jersey_number')
                                        break
                
                # Create anchor frame entries for each frame this track appears
                for _, row in track_data.iterrows():
                    frame_val = row.get('frame', 0)
                    frame_num = int(frame_val) if frame_val is not None and not pd.isna(frame_val) else 0
                    frame_str = str(frame_num)
                    
                    if frame_str not in anchor_frames:
                        anchor_frames[frame_str] = []
                    
                    # Build bbox from available columns (CRITICAL: bbox is essential for matching when track_id changes)
                    # Try multiple sources in priority order
                    bbox = None
                    bbox_source = None
                    
                    # Priority 1: Direct bbox columns (most accurate)
                    if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                        try:
                            bbox = [float(row['x1']), float(row['y1']), float(row['x2']), float(row['y2'])]
                            bbox_source = 'x1/y1/x2/y2'
                        except (ValueError, TypeError):
                            pass
                    
                    # Priority 2: Center point columns (fallback - convert to bbox)
                    if bbox is None and 'player_x' in row and 'player_y' in row:
                        try:
                            x = float(row['player_x'])
                            y = float(row['player_y'])
                            # Default bbox size: 80px wide, 120px tall (centered on player position)
                            bbox = [x - 40, y - 60, x + 40, y + 60]
                            bbox_source = 'player_x/player_y'
                        except (ValueError, TypeError):
                            pass
                    
                    # Build anchor frame with all available information
                    anchor = {
                        'player_name': player_name,
                        'track_id': int(track_id),
                        'confidence': 1.00,  # CRITICAL: Anchor frames must have 1.00 confidence for maximum protection
                        'team': team or ''
                    }
                    
                    # Add jersey_number if available
                    if jersey_number:
                        anchor['jersey_number'] = jersey_number
                    
                    # CRITICAL: Always include bbox if available (essential for matching when track_id changes)
                    if bbox:
                        anchor['bbox'] = bbox
                        # Store bbox source for diagnostics (optional metadata)
                        if bbox_source:
                            anchor['bbox_source'] = bbox_source
                    else:
                        # Warn if bbox cannot be determined (bbox is critical for matching)
                        print(f"  ⚠ WARNING: Frame {frame_num}, Track {track_id}, Player '{player_name}' - no bbox available (bbox is critical for matching when track_id changes)")
                    
                    anchor_frames[frame_str].append(anchor)
            
            # Save anchor frames
            video_basename = os.path.splitext(os.path.basename(self.video_file))[0]
            output_file = os.path.join(os.path.dirname(self.video_file), 
                                      f"PlayerTagsSeed-{video_basename}-PostProcessed.json")
            
            # Validation: Check anchor frames before saving
            total_frames = len(anchor_frames)
            frames_with_bbox = 0
            frames_without_bbox = 0
            frames_with_jersey = 0
            frames_with_team = 0
            confidence_issues = []
            total_anchor_entries = 0
            
            for frame_str, anchors in anchor_frames.items():
                for anchor in anchors:
                    total_anchor_entries += 1
                    # Check bbox
                    if anchor.get('bbox'):
                        frames_with_bbox += 1
                    else:
                        frames_without_bbox += 1
                    
                    # Check jersey_number
                    if anchor.get('jersey_number'):
                        frames_with_jersey += 1
                    
                    # Check team
                    if anchor.get('team'):
                        frames_with_team += 1
                    
                    # Validate confidence is 1.00
                    conf = anchor.get('confidence', 0.0)
                    if conf != 1.00:
                        confidence_issues.append(f"Frame {frame_str}, Track {anchor.get('track_id')}: confidence={conf} (expected 1.00)")
            
            # Save to file
            output_data = {
                'anchor_frames': anchor_frames,
                'video_path': self.video_file or '',
                'source': 'track_review_assigner',
                'total_assignments': len(self.track_assignments),
                'total_frames': total_frames,
                'total_anchor_entries': total_anchor_entries,
                'validation': {
                    'frames_with_bbox': frames_with_bbox,
                    'frames_without_bbox': frames_without_bbox,
                    'frames_with_jersey': frames_with_jersey,
                    'frames_with_team': frames_with_team,
                    'confidence_issues': len(confidence_issues)
                }
            }
            
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            # Build validation message
            validation_msg = f"Saved {total_frames} frames ({total_anchor_entries} anchor entries) to:\n{output_file}\n\n"
            validation_msg += f"Validation Summary:\n"
            if total_anchor_entries > 0:
                validation_msg += f"  • Frames with bbox: {frames_with_bbox} ({frames_with_bbox/total_anchor_entries*100:.1f}%)\n"
                if frames_without_bbox > 0:
                    validation_msg += f"  • Frames without bbox: {frames_without_bbox} ({frames_without_bbox/total_anchor_entries*100:.1f}%)\n"
                validation_msg += f"  • Frames with jersey: {frames_with_jersey} ({frames_with_jersey/total_anchor_entries*100:.1f}%)\n" if frames_with_jersey > 0 else ""
                validation_msg += f"  • Frames with team: {frames_with_team} ({frames_with_team/total_anchor_entries*100:.1f}%)\n" if frames_with_team > 0 else ""
            
            if frames_without_bbox > 0:
                validation_msg += f"\n⚠ WARNING: {frames_without_bbox} anchor entries are missing bbox.\n"
                validation_msg += f"Bbox is critical for matching when track_id changes between sessions.\n"
                validation_msg += f"Consider regenerating anchor frames if CSV has bbox data.\n"
            
            if confidence_issues:
                validation_msg += f"\n⚠ WARNING: {len(confidence_issues)} anchor frames have incorrect confidence:\n"
                for issue in confidence_issues[:5]:  # Show first 5
                    validation_msg += f"  • {issue}\n"
                if len(confidence_issues) > 5:
                    validation_msg += f"  ... and {len(confidence_issues) - 5} more\n"
            
            validation_msg += f"\nThis file can be used as anchor frames in future analyses."
            
            print(f"✓ Anchor Frame Export Validation:")
            print(f"  • Total frames: {total_frames}")
            print(f"  • Total anchor entries: {total_anchor_entries}")
            if total_anchor_entries > 0:
                print(f"  • Frames with bbox: {frames_with_bbox} ({frames_with_bbox/total_anchor_entries*100:.1f}%)")
                if frames_without_bbox > 0:
                    print(f"  • Frames without bbox: {frames_without_bbox} ({frames_without_bbox/total_anchor_entries*100:.1f}%)")
                print(f"  • Frames with jersey: {frames_with_jersey} ({frames_with_jersey/total_anchor_entries*100:.1f}%)" if frames_with_jersey > 0 else "")
                print(f"  • Frames with team: {frames_with_team} ({frames_with_team/total_anchor_entries*100:.1f}%)" if frames_with_team > 0 else "")
            if confidence_issues:
                print(f"  ⚠ Confidence issues: {len(confidence_issues)}")
            
            messagebox.showinfo("Success", validation_msg)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not save anchor frames: {e}")
    
    def save_to_csv(self):
        """Save player assignments directly to CSV file (updates player_name column)"""
        if self.tracks_data is None:
            messagebox.showerror("Error", "No CSV data loaded")
            return
        
        if not self.track_assignments:
            messagebox.showwarning("Warning", "No assignments to save")
            return
        
        # Ask for output file (default to same as input with _tagged suffix)
        default_name = self.csv_file.replace('.csv', '_tagged.csv') if self.csv_file else 'tracking_data_tagged.csv'
        output_file = filedialog.asksaveasfilename(
            title="Save Tagged CSV As",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=os.path.basename(default_name)
        )
        
        if not output_file:
            return
        
        try:
            # Get track ID column
            track_id_col = None
            for col in ['track_id', 'player_id', 'id']:
                if col in self.tracks_data.columns:
                    track_id_col = col
                    break
            
            if track_id_col is None:
                messagebox.showerror("Error", "Could not find track ID column in CSV")
                return
            
            # Create a copy of the dataframe
            df_output = self.tracks_data.copy()
            
            # Add or update player_name column
            if 'player_name' not in df_output.columns:
                df_output['player_name'] = None
            
            # Update player_name for all rows with assigned tracks
            updated_count = 0
            for track_id, player_name in self.track_assignments.items():
                mask = df_output[track_id_col] == track_id
                rows_updated = mask.sum()
                if rows_updated > 0:
                    df_output.loc[mask, 'player_name'] = player_name
                    updated_count += rows_updated
            
            # Save to CSV
            df_output.to_csv(output_file, index=False)
            
            messagebox.showinfo("Success", 
                f"Saved tagged CSV to:\n{output_file}\n\n"
                f"Updated {len(self.track_assignments)} tracks\n"
                f"({updated_count} total rows updated)\n\n"
                f"You can now load this CSV in Consolidate IDs to merge tracks with the same player name.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not save CSV: {e}")
            import traceback
            traceback.print_exc()
    
    def update_track_listbox_display(self):
        """Update the track listbox to show visual indicators for tagged tracks"""
        if self.tracks_data is None:
            return
        
        # Get track ID column
        track_id_col = None
        for col in ['track_id', 'player_id', 'id']:
            if col in self.tracks_data.columns:
                track_id_col = col
                break
        
        if track_id_col is None:
            return
        
        # Get unique tracks - CRITICAL FIX: Convert to numeric first
        try:
            track_ids_numeric = pd.to_numeric(self.tracks_data[track_id_col], errors='coerce')
            unique_tracks_raw = sorted(track_ids_numeric.dropna().unique())
            unique_tracks = [int(t) for t in unique_tracks_raw if pd.notna(t)]
        except (ValueError, TypeError):
            # Fallback: try direct conversion
            try:
                unique_tracks_raw = self.tracks_data[track_id_col].dropna().unique()
                unique_tracks = sorted([int(float(t)) for t in unique_tracks_raw if str(t).strip()])
            except (ValueError, TypeError):
                return  # Can't process tracks
        
        # Store current selection
        current_selection = self.track_listbox.curselection()
        current_selected_track_id = None
        if current_selection:
            selected_index = current_selection[0]
            if selected_index < len(unique_tracks):
                current_selected_track_id = unique_tracks[selected_index]
        
        # Clear and repopulate with visual indicators - SHOW ALL TRACKS (not just assigned)
        self.track_listbox.delete(0, tk.END)
        
        # CRITICAL: Ensure we show ALL tracks, not just assigned ones
        print(f"🔍 DEBUG: update_track_listbox_display - Showing {len(unique_tracks)} total tracks")
        
        for idx, track_id in enumerate(unique_tracks):
            track_id_int = int(track_id)  # Already int, but ensure it
            try:
                # Check if track is assigned
                if track_id_int in self.track_assignments:
                    player_name = self.track_assignments[track_id_int]
                    display_text = f"Track #{track_id_int} ✓ {player_name}"
                    self.track_listbox.insert(tk.END, display_text)
                    # Tag as assigned (green background) - CRITICAL FIX: Use size() - 1 instead of tk.END - 1
                    last_index = self.track_listbox.size() - 1
                    if last_index >= 0:  # Safety check
                        self.track_listbox.itemconfig(last_index, {'bg': '#d4edda', 'fg': '#155724'})
                else:
                    display_text = f"Track #{track_id_int}"
                    self.track_listbox.insert(tk.END, display_text)
                    # Tag as unassigned (white background) - CRITICAL FIX: Use size() - 1 instead of tk.END - 1
                    last_index = self.track_listbox.size() - 1
                    if last_index >= 0:  # Safety check
                        self.track_listbox.itemconfig(last_index, {'bg': 'white', 'fg': 'black'})
            except Exception as e:
                print(f"🔍 DEBUG: Error updating track {track_id_int} in listbox: {e}")
                import traceback
                print(f"🔍 DEBUG: Traceback:\n{traceback.format_exc()}")
                # Continue with next track
                continue
        
        print(f"🔍 DEBUG: update_track_listbox_display - Listbox now has {self.track_listbox.size()} items")
        
        # Restore selection if it existed
        if current_selected_track_id is not None:
            try:
                new_index = unique_tracks.index(current_selected_track_id)
                self.track_listbox.selection_set(new_index)
                self.track_listbox.see(new_index)
            except (ValueError, IndexError):
                pass
    
    def export_assignments(self):
        """Export assignments as simple JSON"""
        if not self.track_assignments:
            messagebox.showwarning("Warning", "No assignments to export")
            return
        
        output_file = filedialog.asksaveasfilename(
            title="Export Assignments As",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not output_file:
            return
        
        try:
            with open(output_file, 'w') as f:
                json.dump(self.track_assignments, f, indent=2)
            messagebox.showinfo("Success", f"Exported assignments to:\n{output_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export: {e}")

    def setup_postprocess_ui(self, parent):
        """Setup Post-Process tab UI"""
        # Top section: Analysis controls
        control_frame = ttk.LabelFrame(parent, text="Post-Processing Analysis", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        # Analysis button
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        self.analyze_button = ttk.Button(button_frame, text="Analyze CSV", 
                                         command=self.start_postprocessing_analysis, width=20)
        self.analyze_button.pack(side=tk.LEFT, padx=5)
        
        # Save/Load buttons
        ttk.Button(button_frame, text="Save Analysis", 
                  command=self.save_postprocessing_analysis, width=18).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Load Analysis", 
                  command=self.load_postprocessing_analysis, width=18).pack(side=tk.LEFT, padx=2)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(button_frame, variable=self.progress_var, 
                                           maximum=100, length=300)
        self.progress_bar.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        self.progress_label = ttk.Label(button_frame, text="Ready")
        self.progress_label.pack(side=tk.LEFT, padx=5)
        
        # Main content area: Split between corrections list and viewer
        main_content = ttk.Frame(parent)
        main_content.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Left side: Corrections list and controls
        left_panel = ttk.LabelFrame(main_content, text="Pending Corrections", padding="10")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Results summary
        summary_frame = ttk.Frame(left_panel)
        summary_frame.pack(fill=tk.X, pady=5)
        
        self.auto_applied_label = ttk.Label(summary_frame, text="Auto-applied: 0", font=("Arial", 9, "bold"))
        self.auto_applied_label.pack(side=tk.LEFT, padx=10)
        
        self.pending_label = ttk.Label(summary_frame, text="Pending review: 0", font=("Arial", 9, "bold"))
        self.pending_label.pack(side=tk.LEFT, padx=10)
        
        # Filter by player
        filter_frame = ttk.Frame(left_panel)
        filter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(filter_frame, text="Filter by player:").pack(side=tk.LEFT, padx=5)
        self.player_filter_var = tk.StringVar()
        self.player_filter_combo = ttk.Combobox(filter_frame, textvariable=self.player_filter_var, 
                                                width=20, state="readonly")
        self.player_filter_combo.pack(side=tk.LEFT, padx=5)
        self.player_filter_combo.bind('<<ComboboxSelected>>', self.filter_corrections_by_player)
        
        ttk.Button(filter_frame, text="Clear Filter", 
                  command=self.clear_player_filter, width=12).pack(side=tk.LEFT, padx=5)
        
        # Pending corrections list (scrollable, multi-select)
        list_frame = ttk.Frame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar_corrections = ttk.Scrollbar(list_frame)
        scrollbar_corrections.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.corrections_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar_corrections.set, 
                                              height=15, font=("Courier", 9), selectmode=tk.EXTENDED)
        self.corrections_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_corrections.config(command=self.corrections_listbox.yview)
        self.corrections_listbox.bind('<<ListboxSelect>>', self.on_correction_select)
        self.corrections_listbox.bind('<Double-Button-1>', lambda e: self.show_selected_tracks_in_viewer())
        self.corrections_listbox.bind('<Button-1>', self.on_listbox_click)
        self.corrections_listbox.bind('<FocusOut>', self.on_listbox_focus_out)
        
        # Correction details
        details_frame = ttk.LabelFrame(left_panel, text="Selected Correction Details", padding="10")
        details_frame.pack(fill=tk.BOTH, expand=False, pady=5)
        
        self.correction_details_text = scrolledtext.ScrolledText(details_frame, height=4, wrap=tk.WORD, 
                                                                 font=("Courier", 9))
        self.correction_details_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Player assignment editor
        assignment_frame = ttk.Frame(details_frame)
        assignment_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(assignment_frame, text="Assigned Player:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.assigned_player_var = tk.StringVar()
        self.assigned_player_combo = ttk.Combobox(assignment_frame, textvariable=self.assigned_player_var, 
                                                  width=25, state="readonly")  # CRITICAL FIX: Use "readonly" to allow dropdown selection
        self.assigned_player_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        # Track when user manually edits the combobox (for when state is changed to "normal" temporarily)
        self.assigned_player_combo.bind('<KeyRelease>', self.on_combobox_edit)
        self.assigned_player_combo.bind('<<ComboboxSelected>>', self.on_combobox_selected)
        self.assigned_player_combo.bind('<FocusIn>', self.on_combobox_focus_in)
        
        ttk.Button(assignment_frame, text="Update", 
                  command=self.update_selected_correction_assignment, width=10).pack(side=tk.LEFT, padx=5)
        
        # Action buttons for corrections
        action_frame = ttk.Frame(left_panel)
        action_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(action_frame, text="View Selected Tracks", 
                  command=self.show_selected_tracks_in_viewer, width=20).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Approve Selected", 
                  command=self.approve_selected_corrections, width=18).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Reject Selected", 
                  command=self.reject_selected_corrections, width=18).pack(side=tk.LEFT, padx=2)
        
        action_frame2 = ttk.Frame(left_panel)
        action_frame2.pack(fill=tk.X, pady=5)
        
        ttk.Button(action_frame2, text="Approve All for Player", 
                  command=self.approve_all_for_selected_player, width=22).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame2, text="Approve All High Confidence (≥0.65)", 
                  command=self.approve_all_high_confidence, width=30).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame2, text="Reject All Pending", 
                  command=self.reject_all_pending, width=20).pack(side=tk.LEFT, padx=2)
        
        # Right side: Video viewer
        right_panel = ttk.LabelFrame(main_content, text="Track Viewer - See Selected Tracks", padding="10")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        right_panel.config(width=640)
        
        # Video canvas for post-processing viewer
        self.postprocess_video_canvas = tk.Canvas(right_panel, bg="black", width=640, height=360)
        self.postprocess_video_canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Frame navigation controls for viewer
        nav_frame = ttk.Frame(right_panel)
        nav_frame.pack(fill=tk.X, pady=5)
        
        # Store button references for state management
        self.postprocess_nav_buttons = {}
        
        first_btn = ttk.Button(nav_frame, text="◄◄ First", command=self.postprocess_go_to_first_frame, width=12)
        first_btn.pack(side=tk.LEFT, padx=2)
        self.postprocess_nav_buttons['first'] = first_btn
        
        prev_btn = ttk.Button(nav_frame, text="◄ Prev", command=self.postprocess_go_to_prev_frame, width=12)
        prev_btn.pack(side=tk.LEFT, padx=2)
        self.postprocess_nav_buttons['prev'] = prev_btn
        
        self.postprocess_frame_label = ttk.Label(nav_frame, text="Frame: 0 / 0", width=20)
        self.postprocess_frame_label.pack(side=tk.LEFT, padx=10)
        
        next_btn = ttk.Button(nav_frame, text="Next ►", command=self.postprocess_go_to_next_frame, width=12)
        next_btn.pack(side=tk.LEFT, padx=2)
        self.postprocess_nav_buttons['next'] = next_btn
        
        last_btn = ttk.Button(nav_frame, text="Last ►►", command=self.postprocess_go_to_last_frame, width=12)
        last_btn.pack(side=tk.LEFT, padx=2)
        self.postprocess_nav_buttons['last'] = last_btn
        
        # Initially disable all buttons
        for btn in self.postprocess_nav_buttons.values():
            btn.config(state="disabled")
        
        # Selected tracks info
        self.postprocess_selected_tracks_label = ttk.Label(right_panel, text="No tracks selected", 
                                                           font=("Arial", 9), wraplength=600)
        self.postprocess_selected_tracks_label.pack(pady=5)
        
        # Post-processing viewer state
        self.postprocess_selected_track_ids = []  # List of track IDs to view
        self.postprocess_current_frame_index = 0
        self.postprocess_frame_list = []
        self.postprocess_video_cap = None
        self.postprocess_nav_buttons = {}  # Navigation button references
        
        # Export section
        export_frame = ttk.LabelFrame(parent, text="Export Corrected Data", padding="10")
        export_frame.pack(fill=tk.X, pady=5)
        
        options_frame = ttk.Frame(export_frame)
        options_frame.pack(fill=tk.X, pady=5)
        
        self.update_gallery_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Update Player Gallery", 
                      variable=self.update_gallery_var).pack(side=tk.LEFT, padx=10)
        
        self.generate_anchors_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Generate Anchor Frames", 
                      variable=self.generate_anchors_var).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(export_frame, text="Export Corrected CSV", 
                  command=self.export_corrected_csv, width=25).pack(pady=10)

    def save_postprocessing_analysis(self):
        """Save the current post-processing analysis state"""
        if len(self.pending_corrections) == 0 and len(self.auto_corrections) == 0:
            messagebox.showwarning("Warning", "No analysis data to save. Please run analysis first.")
            return
        
        output_file = filedialog.asksaveasfilename(
            title="Save Post-Processing Analysis",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="postprocessing_analysis.json"
        )
        
        if not output_file:
            return
        
        try:
            # Prepare data to save
            save_data = {
                'version': '1.0',
                'timestamp': datetime.now().isoformat(),
                'csv_file': self.csv_file,
                'video_file': self.video_file,
                'pending_corrections': {},
                'auto_corrections': {},
                'track_assignments': self.track_assignments.copy(),
                'corrections_listbox_track_ids': []
            }
            
            # Convert track IDs to strings for JSON serialization
            for track_id, correction in self.pending_corrections.items():
                save_data['pending_corrections'][str(track_id)] = correction
            
            for track_id, correction in self.auto_corrections.items():
                save_data['auto_corrections'][str(track_id)] = correction
            
            # Save to file
            with open(output_file, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            messagebox.showinfo("Success", 
                f"Analysis data saved to:\n{output_file}\n\n"
                f"Saved:\n"
                f"- {len(self.pending_corrections)} pending corrections\n"
                f"- {len(self.auto_corrections)} auto-applied corrections\n"
                f"- {len(self.track_assignments)} track assignments")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not save analysis data: {e}")
            import traceback
            traceback.print_exc()
    
    def load_postprocessing_analysis(self):
        """Load a previously saved post-processing analysis"""
        input_file = filedialog.askopenfilename(
            title="Load Post-Processing Analysis",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not input_file:
            return
        
        try:
            with open(input_file, 'r') as f:
                save_data = json.load(f)
            
            # Validate version
            if 'version' not in save_data:
                messagebox.showwarning("Warning", 
                    "This file appears to be from an older version. "
                    "Some data may not load correctly.")
            
            # Load corrections (convert string keys back to appropriate types)
            self.pending_corrections = {}
            for track_id_str, correction in save_data.get('pending_corrections', {}).items():
                # Try to convert to int, fallback to float if needed
                try:
                    track_id = int(track_id_str)
                except ValueError:
                    track_id = float(track_id_str)
                self.pending_corrections[track_id] = correction
            
            self.auto_corrections = {}
            for track_id_str, correction in save_data.get('auto_corrections', {}).items():
                try:
                    track_id = int(track_id_str)
                except ValueError:
                    track_id = float(track_id_str)
                self.auto_corrections[track_id] = correction
            
            # Load track assignments
            self.track_assignments = save_data.get('track_assignments', {}).copy()
            
            # Optionally load CSV and video if paths are saved and files exist
            csv_path = save_data.get('csv_file')
            video_path = save_data.get('video_file')
            
            if csv_path and os.path.exists(csv_path):
                response = messagebox.askyesno("Load Files?", 
                    f"Found saved file paths:\n"
                    f"CSV: {csv_path}\n"
                    f"Video: {video_path if video_path else 'Not specified'}\n\n"
                    f"Would you like to load these files?")
                
                if response:
                    if csv_path and os.path.exists(csv_path):
                        self.load_csv(csv_path)
                    if video_path and os.path.exists(video_path):
                        self.load_video(video_path)
            
            # Refresh display
            self.update_corrections_display()
            # Update summary if labels exist
            if hasattr(self, 'auto_applied_label') and hasattr(self, 'pending_label'):
                self.auto_applied_label.config(text=f"Auto-applied: {len(self.auto_corrections)}")
                self.pending_label.config(text=f"Pending review: {len(self.pending_corrections)}")
            
            messagebox.showinfo("Success", 
                f"Analysis data loaded from:\n{input_file}\n\n"
                f"Loaded:\n"
                f"- {len(self.pending_corrections)} pending corrections\n"
                f"- {len(self.auto_corrections)} auto-applied corrections\n"
                f"- {len(self.track_assignments)} track assignments")
            
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON file: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load analysis data: {e}")
            import traceback
            traceback.print_exc()
    
    def start_postprocessing_analysis(self):
        """Start post-processing analysis in a separate thread"""
        if self.tracks_data is None:
            messagebox.showerror("Error", "Please load a CSV file first")
            return
        
        if self.analysis_in_progress:
            messagebox.showwarning("Warning", "Analysis already in progress")
            return
        
        # Start analysis in background thread
        self.analysis_in_progress = True
        self.analyze_button.config(state="disabled")
        self.progress_var.set(0)
        self.progress_label.config(text="Starting analysis...")
        
        thread = threading.Thread(target=self._run_postprocessing_analysis, daemon=True)
        thread.start()
    
    def _run_postprocessing_analysis(self):
        """Run post-processing analysis (called from thread)"""
        try:
            # Initialize Re-ID tracker and gallery if available
            if ReIDTracker is not None and self.reid_tracker is None:
                try:
                    self.reid_tracker = ReIDTracker(device='cuda' if cv2.cuda.getCudaEnabledDeviceCount() > 0 else 'cpu')
                except Exception as e:
                    print(f"Warning: Could not initialize Re-ID tracker: {e}")
                    self.reid_tracker = None
            
            if PlayerGallery is not None and self.player_gallery_obj is None:
                try:
                    self.player_gallery_obj = PlayerGallery()
                    self.player_gallery_obj.load_gallery()
                except Exception as e:
                    print(f"Warning: Could not load player gallery: {e}")
                    self.player_gallery_obj = None
            
            # Run all three analysis methods
            self.root.after(0, lambda: self.progress_label.config(text="Gallery matching..."))
            gallery_suggestions = self.analyze_with_gallery_matching(self.tracks_data, self.video_file)
            self.root.after(0, lambda: self.progress_var.set(33))
            
            self.root.after(0, lambda: self.progress_label.config(text="Temporal analysis..."))
            temporal_suggestions = self.analyze_temporal_continuity(self.tracks_data)
            self.root.after(0, lambda: self.progress_var.set(66))
            
            self.root.after(0, lambda: self.progress_label.config(text="Frame pattern analysis..."))
            frame_suggestions = self.analyze_frame_patterns(self.tracks_data)
            self.root.after(0, lambda: self.progress_var.set(90))
            
            # Process corrections
            self.root.after(0, lambda: self.progress_label.config(text="Processing corrections..."))
            self.process_corrections(gallery_suggestions, temporal_suggestions, frame_suggestions)
            
            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self.progress_label.config(text="Analysis complete!"))
            self.root.after(0, self.update_corrections_display)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Analysis failed: {e}"))
            import traceback
            traceback.print_exc()
        finally:
            self.analysis_in_progress = False
            self.root.after(0, lambda: self.analyze_button.config(state="normal"))
    
    def analyze_with_gallery_matching(self, csv_data, video_path):
        """Analyze tracks using gallery-based Re-ID matching"""
        suggestions = {}
        
        if self.reid_tracker is None or self.player_gallery_obj is None or video_path is None:
            return suggestions
        
        if not os.path.exists(video_path):
            return suggestions
        
        try:
            # Get track ID column
            track_id_col = None
            for col in ['track_id', 'player_id', 'id']:
                if col in csv_data.columns:
                    track_id_col = col
                    break
            
            if track_id_col is None:
                return suggestions
            
            # Get frame column
            frame_col = None
            for col in ['frame', 'frame_num', 'frame_number']:
                if col in csv_data.columns:
                    frame_col = col
                    break
            
            if frame_col is None:
                return suggestions
            
            # Group by track_id
            unique_tracks = csv_data[track_id_col].dropna().unique()
            total_tracks = len(unique_tracks)
            
            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return suggestions
            
            # Process each track
            for idx, track_id in enumerate(unique_tracks):
                track_data = csv_data[csv_data[track_id_col] == track_id]
                
                # Sample frames (first, middle, last) for efficiency
                frames_to_check = []
                frame_nums = sorted(track_data[frame_col].dropna().unique().astype(int))
                if len(frame_nums) > 0:
                    frames_to_check = [
                        frame_nums[0],
                        frame_nums[len(frame_nums) // 2],
                        frame_nums[-1]
                    ]
                
                # Extract features from sampled frames
                all_features = []
                for frame_num in frames_to_check:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    
                    # Get bbox for this track at this frame
                    frame_data = track_data[track_data[frame_col] == frame_num]
                    if len(frame_data) == 0:
                        continue
                    
                    row = frame_data.iloc[0]
                    bbox = None
                    if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                        bbox = (int(row['x1']), int(row['y1']), int(row['x2']), int(row['y2']))
                    elif 'player_x' in row and 'player_y' in row:
                        cx, cy = float(row['player_x']), float(row['player_y'])
                        bbox = (int(cx - 40), int(cy - 60), int(cx + 40), int(cy + 60))
                    
                    if bbox and SUPERVISION_AVAILABLE and Detections is not None:
                        # Create dummy detections object for feature extraction
                        dummy_detections = Detections(
                            xyxy=np.array([[bbox[0], bbox[1], bbox[2], bbox[3]]]),
                            confidence=np.array([0.9])
                        )
                        
                        try:
                            features = self.reid_tracker.extract_features(frame, dummy_detections)
                            if len(features) > 0:
                                all_features.append(features[0])
                        except Exception as e:
                            print(f"Warning: Could not extract features for track {track_id} at frame {frame_num}: {e}")
                
                if len(all_features) > 0:
                    # Average features
                    avg_features = np.mean(all_features, axis=0)
                    avg_features = avg_features / (np.linalg.norm(avg_features) + 1e-8)
                    
                    # Match against gallery
                    try:
                        matches = self.reid_tracker.match_against_gallery(
                            avg_features.reshape(1, -1),
                            self.player_gallery_obj,
                            similarity_threshold=0.3
                        )
                        
                        if len(matches) > 0 and matches[0][0] is not None:
                            player_id, player_name, similarity = matches[0]
                            if similarity >= 0.3:
                                suggestions[track_id] = {
                                    'suggested_assignment': player_name,
                                    'confidence': float(similarity),
                                    'method': 'gallery',
                                    'evidence': {
                                        'gallery_similarity': float(similarity),
                                        'temporal_continuity_score': 0.0,
                                        'frame_pattern_match': 0.0,
                                        'reasoning': f'Gallery match with {similarity:.2%} similarity'
                                    },
                                    'frames_affected': frame_nums[:10]  # First 10 frames
                                }
                    except Exception as e:
                        print(f"Warning: Could not match track {track_id} against gallery: {e}")
            
            cap.release()
            
        except Exception as e:
            print(f"Error in gallery matching: {e}")
            import traceback
            traceback.print_exc()
        
        return suggestions
    
    def analyze_temporal_continuity(self, csv_data):
        """Analyze tracks for temporal continuity issues"""
        suggestions = {}
        
        try:
            # Get track ID column
            track_id_col = None
            for col in ['track_id', 'player_id', 'id']:
                if col in csv_data.columns:
                    track_id_col = col
                    break
            
            if track_id_col is None:
                return suggestions
            
            # Get frame column
            frame_col = None
            for col in ['frame', 'frame_num', 'frame_number']:
                if col in csv_data.columns:
                    frame_col = col
                    break
            
            if frame_col is None:
                return suggestions
            
            # Group by track_id
            unique_tracks = csv_data[track_id_col].dropna().unique()
            
            for track_id in unique_tracks:
                track_data = csv_data[csv_data[track_id_col] == track_id].sort_values(frame_col)
                
                if len(track_data) < 2:
                    continue
                
                # Check for position jumps
                if 'player_x' in track_data.columns and 'player_y' in track_data.columns:
                    positions = track_data[['player_x', 'player_y']].values
                    frame_nums = track_data[frame_col].values
                    
                    # Calculate distances between consecutive frames
                    distances = []
                    for i in range(1, len(positions)):
                        dist = np.linalg.norm(positions[i] - positions[i-1])
                        distances.append(dist)
                    
                    if len(distances) > 0:
                        max_jump = max(distances)
                        avg_distance = np.mean(distances)
                        
                        # If there's a sudden jump (>200px), flag for review
                        if max_jump > 200 and max_jump > avg_distance * 3:
                            # Find the frame with the jump
                            jump_idx = distances.index(max_jump) + 1
                            jump_frame = frame_nums[jump_idx]
                            
                            # Check if another track appears nearby
                            nearby_tracks = []
                            for other_track_id in unique_tracks:
                                if other_track_id == track_id:
                                    continue
                                other_data = csv_data[csv_data[track_id_col] == other_track_id]
                                other_frame_data = other_data[other_data[frame_col] == jump_frame]
                                if len(other_frame_data) > 0:
                                    other_pos = other_frame_data[['player_x', 'player_y']].iloc[0].values
                                    dist_to_other = np.linalg.norm(positions[jump_idx] - other_pos)
                                    if dist_to_other < 100:
                                        nearby_tracks.append(other_track_id)
                            
                            if nearby_tracks:
                                # Suggest potential merge
                                suggestions[track_id] = {
                                    'suggested_assignment': None,  # Needs manual review
                                    'confidence': 0.5,
                                    'method': 'temporal',
                                    'evidence': {
                                        'gallery_similarity': 0.0,
                                        'temporal_continuity_score': 0.5,
                                        'frame_pattern_match': 0.0,
                                        'reasoning': f'Position jump detected at frame {jump_frame} (jump: {max_jump:.1f}px). Possible track merge with tracks: {nearby_tracks}'
                                    },
                                    'frames_affected': [int(jump_frame)]
                                }
                
                # Check track lifespan
                frame_nums = sorted(track_data[frame_col].dropna().unique().astype(int))
                if len(frame_nums) > 0:
                    track_length = frame_nums[-1] - frame_nums[0]
                    gap_count = 0
                    for i in range(1, len(frame_nums)):
                        if frame_nums[i] - frame_nums[i-1] > 30:  # Gap > 1 second at 30fps
                            gap_count += 1
                    
                    # If track has many gaps, it might be multiple tracks merged
                    if gap_count > 3 and track_length > 1000:
                        if track_id not in suggestions:
                            suggestions[track_id] = {
                                'suggested_assignment': None,
                                'confidence': 0.4,
                                'method': 'temporal',
                                'evidence': {
                                    'gallery_similarity': 0.0,
                                    'temporal_continuity_score': 0.4,
                                    'frame_pattern_match': 0.0,
                                    'reasoning': f'Track has {gap_count} large gaps. May be multiple tracks merged.'
                                },
                                'frames_affected': frame_nums[:10]
                            }
        
        except Exception as e:
            print(f"Error in temporal analysis: {e}")
            import traceback
            traceback.print_exc()
        
        return suggestions
    
    def analyze_frame_patterns(self, csv_data):
        """Analyze tracks using frame-based patterns"""
        suggestions = {}
        
        try:
            # Get track ID column
            track_id_col = None
            for col in ['track_id', 'player_id', 'id']:
                if col in csv_data.columns:
                    track_id_col = col
                    break
            
            if track_id_col is None:
                return suggestions
            
            # Get frame column
            frame_col = None
            for col in ['frame', 'frame_num', 'frame_number']:
                if col in csv_data.columns:
                    frame_col = col
                    break
            
            if frame_col is None:
                return suggestions
            
            # Group by track_id
            unique_tracks = csv_data[track_id_col].dropna().unique()
            
            # Calculate average stats per track
            track_stats = {}
            for track_id in unique_tracks:
                track_data = csv_data[csv_data[track_id_col] == track_id]
                
                stats = {}
                if 'player_speed_mph' in track_data.columns:
                    stats['avg_speed'] = track_data['player_speed_mph'].mean()
                    stats['max_speed'] = track_data['player_speed_mph'].max()
                
                if 'player_x' in track_data.columns and 'player_y' in track_data.columns:
                    stats['avg_x'] = track_data['player_x'].mean()
                    stats['avg_y'] = track_data['player_y'].mean()
                
                if 'field_zone' in track_data.columns:
                    zones = track_data['field_zone'].dropna().value_counts()
                    stats['preferred_zone'] = zones.index[0] if len(zones) > 0 else None
                
                track_stats[track_id] = stats
            
            # Compare against player gallery patterns if available
            if self.player_gallery_obj is not None:
                for track_id, stats in track_stats.items():
                    best_match = None
                    best_score = 0.0
                    
                    for player_id, profile in self.player_gallery_obj.players.items():
                        if not isinstance(profile, dict):
                            continue
                        
                        score = 0.0
                        match_count = 0
                        
                        # Compare speed profile
                        if 'avg_speed' in stats and profile.get('avg_speed') is not None:
                            speed_diff = abs(stats['avg_speed'] - profile['avg_speed'])
                            if speed_diff < 2.0:  # Within 2 mph
                                score += 0.3
                            match_count += 1
                        
                        # Compare position preference
                        if 'preferred_zone' in stats and profile.get('preferred_x') is not None:
                            # Simple position matching (could be improved)
                            score += 0.2
                            match_count += 1
                        
                        if match_count > 0:
                            score = score / match_count
                            if score > best_score:
                                best_score = score
                                best_match = profile.get('name')
                    
                    if best_match and best_score >= 0.4:
                        frame_nums = sorted(csv_data[csv_data[track_id_col] == track_id][frame_col].dropna().unique().astype(int))
                        suggestions[track_id] = {
                            'suggested_assignment': best_match,
                            'confidence': float(best_score),
                            'method': 'frame_pattern',
                            'evidence': {
                                'gallery_similarity': 0.0,
                                'temporal_continuity_score': 0.0,
                                'frame_pattern_match': float(best_score),
                                'reasoning': f'Movement pattern matches {best_match} (score: {best_score:.2%})'
                            },
                            'frames_affected': frame_nums[:10]
                        }
        
        except Exception as e:
            print(f"Error in frame pattern analysis: {e}")
            import traceback
            traceback.print_exc()
        
        return suggestions
    
    def process_corrections(self, gallery_suggestions, temporal_suggestions, frame_suggestions, confidence_threshold=0.75):
        """Combine all suggestions and determine auto-apply vs pending review"""
        self.auto_corrections = {}
        self.pending_corrections = {}
        
        # Combine all suggestions by track_id
        all_suggestions = {}
        
        # Add gallery suggestions
        for track_id, suggestion in gallery_suggestions.items():
            if track_id not in all_suggestions:
                all_suggestions[track_id] = []
            all_suggestions[track_id].append(suggestion)
        
        # Add temporal suggestions
        for track_id, suggestion in temporal_suggestions.items():
            if track_id not in all_suggestions:
                all_suggestions[track_id] = []
            all_suggestions[track_id].append(suggestion)
        
        # Add frame pattern suggestions
        for track_id, suggestion in frame_suggestions.items():
            if track_id not in all_suggestions:
                all_suggestions[track_id] = []
            all_suggestions[track_id].append(suggestion)
        
        # Process each track
        for track_id, suggestions_list in all_suggestions.items():
            # Get current assignment if any
            current_assignment = self.track_assignments.get(track_id)
            
            # CRITICAL FIX: Skip tracks that were already manually assigned in Review & Assignment tab
            # If a track has a manual assignment, don't override it with post-processing suggestions
            if current_assignment and current_assignment not in ['Guest Player', 'None', None, '']:
                # Check if this assignment was manually made (not from auto-corrections)
                # If it's in track_assignments but not in auto_corrections, it was manually assigned
                if track_id not in self.auto_corrections:
                    # This is a manual assignment - skip post-processing suggestions for this track
                    continue
            
            # Find best suggestion (highest confidence with assignment)
            best_suggestion = None
            best_confidence = 0.0
            methods_used = []
            
            for suggestion in suggestions_list:
                if suggestion['suggested_assignment'] is not None:
                    if suggestion['confidence'] > best_confidence:
                        best_confidence = suggestion['confidence']
                        best_suggestion = suggestion
                methods_used.append(suggestion['method'])
            
            if best_suggestion is None:
                # No assignment suggestion, but might have temporal issues
                for suggestion in suggestions_list:
                    if suggestion['method'] == 'temporal':
                        self.pending_corrections[track_id] = {
                            'track_id': track_id,
                            'current_assignment': current_assignment,
                            'suggested_assignment': None,
                            'confidence': suggestion['confidence'],
                            'methods': methods_used,
                            'evidence': suggestion['evidence'],
                            'frames_affected': suggestion.get('frames_affected', [])
                        }
                continue
            
            # Check if multiple methods agree
            agreeing_methods = [s for s in suggestions_list 
                               if s['suggested_assignment'] == best_suggestion['suggested_assignment']]
            
            # Combine evidence
            combined_evidence = {
                'gallery_similarity': 0.0,
                'temporal_continuity_score': 0.0,
                'frame_pattern_match': 0.0,
                'reasoning': ''
            }
            
            for suggestion in suggestions_list:
                if 'evidence' in suggestion:
                    ev = suggestion['evidence']
                    combined_evidence['gallery_similarity'] = max(combined_evidence['gallery_similarity'], 
                                                                 ev.get('gallery_similarity', 0.0))
                    combined_evidence['temporal_continuity_score'] = max(combined_evidence['temporal_continuity_score'],
                                                                       ev.get('temporal_continuity_score', 0.0))
                    combined_evidence['frame_pattern_match'] = max(combined_evidence['frame_pattern_match'],
                                                                   ev.get('frame_pattern_match', 0.0))
            
            # Boost confidence if multiple methods agree
            if len(agreeing_methods) >= 2:
                best_confidence = min(1.0, best_confidence * 1.2)
            
            combined_evidence['reasoning'] = f"Suggested by: {', '.join(set([s['method'] for s in agreeing_methods]))}"
            
            correction = {
                'track_id': track_id,
                'current_assignment': current_assignment,
                'suggested_assignment': best_suggestion['suggested_assignment'],
                'confidence': best_confidence,
                'methods': methods_used,
                'evidence': combined_evidence,
                'frames_affected': best_suggestion.get('frames_affected', [])
            }
            
            # Auto-apply if high confidence and methods agree
            if best_confidence >= confidence_threshold and len(agreeing_methods) >= 1:
                self.auto_corrections[track_id] = correction
            else:
                self.pending_corrections[track_id] = correction
    
    def update_corrections_display(self):
        """Update the corrections listbox and summary"""
        # Update summary labels
        self.auto_applied_label.config(text=f"Auto-applied: {len(self.auto_corrections)}")
        self.pending_label.config(text=f"Pending review: {len(self.pending_corrections)}")
        
        # Update player filter dropdown
        players = set()
        for correction in self.pending_corrections.values():
            if correction['suggested_assignment']:
                players.add(correction['suggested_assignment'])
        self.player_filter_combo['values'] = sorted(players)
        
        # Update listbox
        self.corrections_listbox.delete(0, tk.END)
        
        # Store track IDs for listbox items
        self.corrections_listbox_track_ids = []
        
        filter_player = self.player_filter_var.get()
        
        for track_id, correction in sorted(self.pending_corrections.items()):
            # Apply filter if set
            if filter_player and correction['suggested_assignment'] != filter_player:
                continue
            
            current = correction['current_assignment'] or "None"
            suggested = correction['suggested_assignment'] or "Review needed"
            conf = correction['confidence']
            
            display_text = f"Track #{int(track_id)}: {current} → {suggested} (Conf: {conf:.2%})"
            self.corrections_listbox.insert(tk.END, display_text)
            self.corrections_listbox_track_ids.append(track_id)
    
    def on_listbox_click(self, event):
        """Handle listbox click - don't clear manual edits"""
        # Allow the selection to change, but don't clear manual edits immediately
        pass
    
    def on_listbox_focus_out(self, event):
        """Handle listbox focus loss"""
        # Don't clear manual edits when focus is lost
        pass
    
    def on_combobox_edit(self, event):
        """Track when user manually edits the combobox"""
        self.assigned_player_manually_edited = True
    
    def on_combobox_selected(self, event):
        """Track when user selects from dropdown"""
        self.assigned_player_manually_edited = True
    
    def on_combobox_focus_in(self, event):
        """Track when combobox gets focus"""
        # Don't reset the manual edit flag when focusing
        pass
    
    def on_correction_select(self, event):
        """Handle correction selection (single or multiple)"""
        selection = self.corrections_listbox.curselection()
        if not selection:
            self.correction_details_text.delete(1.0, tk.END)
            self.assigned_player_var.set("")
            self.assigned_player_combo['values'] = []
            self.postprocess_selected_tracks_label.config(text="No tracks selected")
            self.assigned_player_manually_edited = False
            # Clear viewer when no selection
            self.postprocess_selected_track_ids = []
            self.postprocess_frame_list = []
            self.postprocess_current_frame_index = 0
            self.update_navigation_buttons()
            self.postprocess_video_canvas.delete("all")
            self.postprocess_frame_label.config(text="Frame: 0 / 0")
            return
        
        # Get selected track IDs
        selected_track_ids = []
        for idx in selection:
            if idx < len(self.corrections_listbox_track_ids):
                selected_track_ids.append(self.corrections_listbox_track_ids[idx])
        
        if len(selected_track_ids) == 0:
            return
        
        # Load player names for combobox (always update the list)
        player_names = []
        if self.player_gallery:
            if isinstance(self.player_gallery, dict):
                if 'players' in self.player_gallery:
                    for p in self.player_gallery['players']:
                        if isinstance(p, dict) and p.get('name'):
                            player_names.append(p.get('name'))
                else:
                    for player_id, profile in self.player_gallery.items():
                        if isinstance(profile, dict) and profile.get('name'):
                            player_names.append(profile.get('name'))
        
        # CRITICAL FIX: Ensure combobox values are set and state allows selection
        sorted_player_names = sorted(set(player_names))
        self.assigned_player_combo['values'] = sorted_player_names
        # Temporarily set to normal to allow custom entry, then back to readonly for dropdown
        # Actually, let's use "normal" state but configure it properly for both dropdown and typing
        self.assigned_player_combo.config(state="normal")  # Allow both dropdown and typing
        
        # Only update combobox value if user hasn't manually edited it
        # OR if this is a different track selection
        should_update_combobox = True
        if self.assigned_player_manually_edited:
            # Check if the selected track IDs have changed
            if hasattr(self, 'current_selected_track_ids_for_update'):
                if set(selected_track_ids) == set(self.current_selected_track_ids_for_update):
                    # Same track(s) selected - preserve user's manual edit
                    should_update_combobox = False
        
        # Display details for first selected (or summary if multiple)
        if len(selected_track_ids) == 1:
            track_id = selected_track_ids[0]
            correction = self.pending_corrections.get(track_id) or self.auto_corrections.get(track_id)
            
            if correction:
                details = f"Track ID: {int(track_id)}\n"
                details += f"Current Assignment: {correction['current_assignment'] or 'None'}\n"
                details += f"Suggested Assignment: {correction['suggested_assignment'] or 'Review needed'}\n"
                details += f"Confidence: {correction['confidence']:.2%}\n"
                details += f"Methods: {', '.join(correction['methods'])}\n\n"
                details += f"Evidence:\n"
                ev = correction['evidence']
                details += f"  Gallery Similarity: {ev.get('gallery_similarity', 0.0):.2%}\n"
                details += f"  Temporal Score: {ev.get('temporal_continuity_score', 0.0):.2%}\n"
                details += f"  Pattern Match: {ev.get('frame_pattern_match', 0.0):.2%}\n"
                details += f"  Reasoning: {ev.get('reasoning', 'N/A')}\n"
                
                self.correction_details_text.delete(1.0, tk.END)
                self.correction_details_text.insert(1.0, details)
                
                # Set current assignment in combobox only if not manually edited
                if should_update_combobox:
                    current_assignment = correction.get('suggested_assignment') or correction.get('current_assignment') or ""
                    self.assigned_player_var.set(current_assignment)
                    self.assigned_player_manually_edited = False
        else:
            # Multiple selected - show summary
            details = f"Selected: {len(selected_track_ids)} tracks\n\n"
            players = {}
            for track_id in selected_track_ids:
                correction = self.pending_corrections.get(track_id) or self.auto_corrections.get(track_id)
                if correction:
                    player = correction.get('suggested_assignment') or correction.get('current_assignment') or "Unassigned"
                    if player not in players:
                        players[player] = []
                    players[player].append(int(track_id))
            
            details += "Grouped by suggested player:\n"
            for player, track_ids in sorted(players.items()):
                details += f"  {player}: {len(track_ids)} tracks (IDs: {', '.join(map(str, track_ids[:10]))}"
                if len(track_ids) > 10:
                    details += f", ...)"
                details += "\n"
            
            self.correction_details_text.delete(1.0, tk.END)
            self.correction_details_text.insert(1.0, details)
            
            # For multiple selection, show first player or empty (only if not manually edited)
            if should_update_combobox:
                if players:
                    first_player = sorted(players.keys())[0]
                    self.assigned_player_var.set(first_player)
                else:
                    self.assigned_player_var.set("")
                self.assigned_player_manually_edited = False
        
        # Update selected tracks label
        if len(selected_track_ids) == 1:
            self.postprocess_selected_tracks_label.config(text=f"Selected: Track #{selected_track_ids[0]}")
        else:
            self.postprocess_selected_tracks_label.config(text=f"Selected: {len(selected_track_ids)} tracks")
        
        # Store selected track IDs for update operations
        self.current_selected_track_ids_for_update = selected_track_ids
    
    def update_selected_correction_assignment(self):
        """Update the assigned player for selected correction(s)"""
        # Try to get selection from listbox first
        selection = self.corrections_listbox.curselection()
        selected_track_ids = []
        
        if selection:
            # Get track IDs from current selection
            for idx in selection:
                if idx < len(self.corrections_listbox_track_ids):
                    selected_track_ids.append(self.corrections_listbox_track_ids[idx])
        
        # Fallback to stored selection if listbox selection is lost
        if len(selected_track_ids) == 0 and len(self.current_selected_track_ids_for_update) > 0:
            selected_track_ids = self.current_selected_track_ids_for_update.copy()
        
        if len(selected_track_ids) == 0:
            messagebox.showwarning("Warning", "Please select one or more corrections to update")
            return
        
        new_player_name = self.assigned_player_var.get().strip()
        if not new_player_name:
            messagebox.showwarning("Warning", "Please enter a player name")
            return
        
        updated_count = 0
        tracks_updated = []
        
        for track_id in selected_track_ids:
            track_updated = False
            
            # Update in pending corrections
            if track_id in self.pending_corrections:
                old_assignment = self.pending_corrections[track_id].get('suggested_assignment', 'None')
                self.pending_corrections[track_id]['suggested_assignment'] = new_player_name
                # Update evidence reasoning to indicate manual change
                if 'evidence' not in self.pending_corrections[track_id]:
                    self.pending_corrections[track_id]['evidence'] = {}
                self.pending_corrections[track_id]['evidence']['reasoning'] = f"Manually assigned to {new_player_name} (was: {old_assignment})"
                updated_count += 1
                track_updated = True
                tracks_updated.append(int(track_id))
            
            # Also update in auto_corrections if present
            if track_id in self.auto_corrections:
                old_assignment = self.auto_corrections[track_id].get('suggested_assignment', 'None')
                self.auto_corrections[track_id]['suggested_assignment'] = new_player_name
                if 'evidence' not in self.auto_corrections[track_id]:
                    self.auto_corrections[track_id]['evidence'] = {}
                self.auto_corrections[track_id]['evidence']['reasoning'] = f"Manually assigned to {new_player_name} (was: {old_assignment})"
                if not track_updated:
                    updated_count += 1
                    tracks_updated.append(int(track_id))
            
            # If track is not in corrections yet, create a new correction entry
            if track_id not in self.pending_corrections and track_id not in self.auto_corrections:
                # Create a new correction entry for manual assignment
                self.pending_corrections[track_id] = {
                    'track_id': track_id,
                    'current_assignment': None,
                    'suggested_assignment': new_player_name,
                    'confidence': 1.0,  # Manual assignment = 100% confidence
                    'methods': ['manual'],
                    'evidence': {
                        'gallery_similarity': 0.0,
                        'temporal_continuity_score': 0.0,
                        'frame_pattern_match': 0.0,
                        'reasoning': f"Manually assigned to {new_player_name}"
                    },
                    'frames_affected': []
                }
                updated_count += 1
                tracks_updated.append(int(track_id))
        
        if updated_count == 0:
            messagebox.showwarning("Warning", "No corrections found to update")
            return
        
        # Refresh display
        self.update_corrections_display()
        
        # Re-select the same items if selection still exists
        if selection:
            for idx in selection:
                if idx < self.corrections_listbox.size():
                    self.corrections_listbox.selection_set(idx)
        
        # Reset manual edit flag after successful update
        self.assigned_player_manually_edited = False
        
        # Update details display
        if len(selected_track_ids) == 1:
            track_id = selected_track_ids[0]
            correction = self.pending_corrections.get(track_id) or self.auto_corrections.get(track_id)
            if correction:
                details = f"Track ID: {int(track_id)}\n"
                details += f"Current Assignment: {correction.get('current_assignment') or 'None'}\n"
                details += f"Suggested Assignment: {correction.get('suggested_assignment') or 'Review needed'}\n"
                details += f"Confidence: {correction.get('confidence', 0.0):.2%}\n"
                details += f"Methods: {', '.join(correction.get('methods', []))}\n\n"
                details += f"Evidence:\n"
                ev = correction.get('evidence', {})
                details += f"  Gallery Similarity: {ev.get('gallery_similarity', 0.0):.2%}\n"
                details += f"  Temporal Score: {ev.get('temporal_continuity_score', 0.0):.2%}\n"
                details += f"  Pattern Match: {ev.get('frame_pattern_match', 0.0):.2%}\n"
                details += f"  Reasoning: {ev.get('reasoning', 'N/A')}\n"
                
                self.correction_details_text.delete(1.0, tk.END)
                self.correction_details_text.insert(1.0, details)
        
        messagebox.showinfo("Success", 
            f"Updated assignment to '{new_player_name}' for {updated_count} track(s):\n" +
            f"Track IDs: {', '.join(map(str, tracks_updated[:10]))}" +
            (f" (and {len(tracks_updated) - 10} more)" if len(tracks_updated) > 10 else ""))
    
    def approve_selected_corrections(self):
        """Approve the selected correction(s) - supports multiple selection"""
        # Try to get selection from listbox first
        selection = self.corrections_listbox.curselection()
        selected_track_ids = []
        
        if selection:
            # Get track IDs from current selection
            for idx in selection:
                if idx < len(self.corrections_listbox_track_ids):
                    selected_track_ids.append(self.corrections_listbox_track_ids[idx])
        
        # Fallback to stored selection if listbox selection is lost
        if len(selected_track_ids) == 0 and len(self.current_selected_track_ids_for_update) > 0:
            selected_track_ids = self.current_selected_track_ids_for_update.copy()
        
        if len(selected_track_ids) == 0:
            messagebox.showwarning("Warning", "Please select one or more corrections to approve")
            return
        
        # Get edited player name from combobox
        edited_player = self.assigned_player_var.get().strip()
        
        approved_count = 0
        for track_id in selected_track_ids:
            # Check if there's an edited assignment in the combobox
            use_combobox_value = False
            assignment = None
            
            if track_id in self.pending_corrections:
                correction = self.pending_corrections[track_id]
                
                # Check if combobox has a different value than the correction
                if edited_player and edited_player != correction.get('suggested_assignment', ''):
                    use_combobox_value = True
                    assignment = edited_player
                else:
                    assignment = correction.get('suggested_assignment')
                
                if assignment:
                    self.track_assignments[track_id] = assignment
                    correction['suggested_assignment'] = assignment
                    if use_combobox_value:
                        if 'evidence' not in correction:
                            correction['evidence'] = {}
                        correction['evidence']['reasoning'] = f"Manually assigned to {assignment}"
                
                # Move to auto_corrections
                self.auto_corrections[track_id] = correction
                del self.pending_corrections[track_id]
                approved_count += 1
            elif track_id in self.auto_corrections:
                # Already approved, but update assignment if edited in combobox
                if edited_player and edited_player != self.auto_corrections[track_id].get('suggested_assignment', ''):
                    self.auto_corrections[track_id]['suggested_assignment'] = edited_player
                    self.track_assignments[track_id] = edited_player
                    if 'evidence' not in self.auto_corrections[track_id]:
                        self.auto_corrections[track_id]['evidence'] = {}
                    self.auto_corrections[track_id]['evidence']['reasoning'] = f"Manually assigned to {edited_player}"
                elif not edited_player:
                    # Use existing assignment
                    assignment = self.auto_corrections[track_id].get('suggested_assignment')
                    if assignment:
                        self.track_assignments[track_id] = assignment
                approved_count += 1
        
        self.update_corrections_display()
        self.correction_details_text.delete(1.0, tk.END)
        self.assigned_player_var.set("")
        self.postprocess_selected_tracks_label.config(text="No tracks selected")
        self.current_selected_track_ids_for_update = []
        messagebox.showinfo("Success", f"Approved {approved_count} correction(s)")
    
    def reject_selected_corrections(self):
        """Reject the selected correction(s) - supports multiple selection"""
        selection = self.corrections_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select one or more corrections to reject")
            return
        
        # Get all selected track IDs
        selected_track_ids = []
        for idx in selection:
            if idx < len(self.corrections_listbox_track_ids):
                selected_track_ids.append(self.corrections_listbox_track_ids[idx])
        
        if len(selected_track_ids) == 0:
            return
        
        rejected_count = 0
        for track_id in selected_track_ids:
            if track_id in self.pending_corrections:
                del self.pending_corrections[track_id]
                rejected_count += 1
        
        self.update_corrections_display()
        self.correction_details_text.delete(1.0, tk.END)
        self.postprocess_selected_tracks_label.config(text="No tracks selected")
        messagebox.showinfo("Success", f"Rejected {rejected_count} correction(s)")
    
    def approve_all_for_selected_player(self):
        """Approve all corrections for the player selected in the filter"""
        filter_player = self.player_filter_var.get()
        if not filter_player:
            messagebox.showwarning("Warning", "Please select a player from the filter dropdown first")
            return
        
        approved_count = 0
        to_approve = []
        for track_id, correction in list(self.pending_corrections.items()):
            if correction['suggested_assignment'] == filter_player:
                to_approve.append((track_id, correction))
        
        for track_id, correction in to_approve:
            if correction['suggested_assignment']:
                self.track_assignments[track_id] = correction['suggested_assignment']
            self.auto_corrections[track_id] = correction
            del self.pending_corrections[track_id]
            approved_count += 1
        
        self.update_corrections_display()
        messagebox.showinfo("Success", f"Approved {approved_count} corrections for {filter_player}")
    
    def filter_corrections_by_player(self, event=None):
        """Filter corrections list by selected player"""
        self.update_corrections_display()
    
    def clear_player_filter(self):
        """Clear the player filter"""
        self.player_filter_var.set("")
        self.update_corrections_display()
    
    def show_selected_tracks_in_viewer(self):
        """Show selected tracks in the video viewer"""
        selection = self.corrections_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select one or more tracks to view")
            return
        
        if self.video_file is None or not os.path.exists(self.video_file):
            messagebox.showwarning("Warning", "Please load the video file first (in Review & Assignment tab)")
            return
        
        if self.tracks_data is None:
            messagebox.showwarning("Warning", "No CSV data loaded")
            return
        
        # Get selected track IDs
        selected_track_ids = []
        for idx in selection:
            if idx < len(self.corrections_listbox_track_ids):
                selected_track_ids.append(self.corrections_listbox_track_ids[idx])
        
        if len(selected_track_ids) == 0:
            return
        
        self.postprocess_selected_track_ids = selected_track_ids
        
        # Open video if not already open
        if self.postprocess_video_cap is None:
            self.postprocess_video_cap = cv2.VideoCapture(self.video_file)
            if not self.postprocess_video_cap.isOpened():
                messagebox.showerror("Error", "Could not open video file")
                self.postprocess_video_cap = None
                return
        
        # Get all frames where any selected track appears
        track_id_col = None
        for col in ['track_id', 'player_id', 'id']:
            if col in self.tracks_data.columns:
                track_id_col = col
                break
        
        frame_col = None
        for col in ['frame', 'frame_num', 'frame_number']:
            if col in self.tracks_data.columns:
                frame_col = col
                break
        
        if track_id_col is None or frame_col is None:
            messagebox.showerror("Error", "Could not find track_id or frame column in CSV")
            return
        
        # Collect all frames for selected tracks
        all_frames = set()
        for track_id in selected_track_ids:
            track_data = self.tracks_data[self.tracks_data[track_id_col] == track_id]
            if len(track_data) > 0 and isinstance(track_data, pd.DataFrame):
                # Use pandas dropna for Series
                frame_series = track_data[frame_col]
                if not isinstance(frame_series, pd.Series):
                    frame_series = pd.Series(frame_series)
                frames = frame_series.dropna().unique().astype(int).tolist()
                all_frames.update(frames)
        
        self.postprocess_frame_list = sorted(all_frames)
        
        if len(self.postprocess_frame_list) > 0:
            self.postprocess_current_frame_index = 0
            self.update_navigation_buttons()
            self.postprocess_display_frame(self.postprocess_frame_list[0])
        else:
            messagebox.showwarning("Warning", "No frames found for selected tracks")
            self.postprocess_frame_list = []
            self.postprocess_current_frame_index = 0
            self.update_navigation_buttons()
            # Clear the canvas
            self.postprocess_video_canvas.delete("all")
            self.postprocess_frame_label.config(text="Frame: 0 / 0")
    
    def postprocess_display_frame(self, frame_num):
        """Display a frame with selected tracks highlighted"""
        if self.postprocess_video_cap is None:
            return
        
        if self.tracks_data is None:
            return
        
        # Seek to frame
        self.postprocess_video_cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_num))
        ret, frame = self.postprocess_video_cap.read()
        
        if not ret:
            print(f"Warning: Could not read frame {frame_num}")
            return
        
        # Get track ID and frame columns
        track_id_col = None
        for col in ['track_id', 'player_id', 'id']:
            if col in self.tracks_data.columns:
                track_id_col = col
                break
        
        frame_col = None
        for col in ['frame', 'frame_num', 'frame_number']:
            if col in self.tracks_data.columns:
                frame_col = col
                break
        
        if track_id_col is None or frame_col is None:
            return
        
        # Draw all selected tracks
        colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
        
        for idx, track_id in enumerate(self.postprocess_selected_track_ids):
            track_data = self.tracks_data[
                (self.tracks_data[track_id_col] == track_id) & 
                (self.tracks_data[frame_col] == frame_num)
            ]
            
            if len(track_data) > 0:
                row = track_data.iloc[0]
                color = colors[idx % len(colors)]
                
                # Get bbox
                bbox = None
                if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                    x1, y1, x2, y2 = int(row['x1']), int(row['y1']), int(row['x2']), int(row['y2'])
                    bbox = (x1, y1, x2, y2)
                elif 'player_x' in row and 'player_y' in row:
                    cx, cy = float(row['player_x']), float(row['player_y'])
                    bbox = (int(cx - 40), int(cy - 60), int(cx + 40), int(cy + 60))
                
                if bbox:
                    x1, y1, x2, y2 = bbox
                    # Draw bounding box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
                    
                    # Draw label
                    correction = self.pending_corrections.get(track_id) or self.auto_corrections.get(track_id)
                    if correction:
                        label = f"Track #{int(track_id)}"
                        if correction['suggested_assignment']:
                            label += f" - {correction['suggested_assignment']}"
                        label += f" ({correction['confidence']:.0%})"
                    else:
                        label = f"Track #{int(track_id)}"
                    
                    (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    cv2.rectangle(frame, (x1, y1 - text_height - 10), (x1 + text_width, y1), color, -1)
                    cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        # Resize frame to fit canvas
        canvas_width = self.postprocess_video_canvas.winfo_width()
        canvas_height = self.postprocess_video_canvas.winfo_height()
        
        if canvas_width > 1 and canvas_height > 1:
            frame_h, frame_w = frame.shape[:2]
            scale_w = canvas_width / frame_w
            scale_h = canvas_height / frame_h
            scale = min(scale_w, scale_h)
            
            new_w = int(frame_w * scale)
            new_h = int(frame_h * scale)
            frame = cv2.resize(frame, (new_w, new_h))
        
        # Convert BGR to RGB for tkinter
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        img_tk = ImageTk.PhotoImage(image=img)
        
        # Update canvas
        self.postprocess_video_canvas.delete("all")
        self.postprocess_video_canvas.create_image(canvas_width // 2, canvas_height // 2, anchor=tk.CENTER, image=img_tk)
        # Keep reference
        if not hasattr(self, '_postprocess_canvas_images'):
            self._postprocess_canvas_images = []
        self._postprocess_canvas_images.append(img_tk)
        if len(self._postprocess_canvas_images) > 5:
            self._postprocess_canvas_images.pop(0)
        
        # Update frame label
        total_frames = len(self.postprocess_frame_list)
        current_pos = self.postprocess_current_frame_index + 1
        if total_frames > 0:
            self.postprocess_frame_label.config(
                text=f"Frame: {int(frame_num)} ({current_pos}/{total_frames})"
            )
        else:
            self.postprocess_frame_label.config(text="Frame: 0 / 0")
        
        # Update navigation buttons state
        self.update_navigation_buttons()
    
    def update_navigation_buttons(self):
        """Update navigation button states based on current frame position"""
        if not hasattr(self, 'postprocess_nav_buttons') or len(self.postprocess_nav_buttons) == 0:
            return
        
        total_frames = len(self.postprocess_frame_list)
        current_idx = self.postprocess_current_frame_index
        
        if total_frames == 0:
            # Disable all buttons if no frames
            for btn in self.postprocess_nav_buttons.values():
                if btn:
                    btn.config(state="disabled")
        else:
            # Enable/disable based on position
            if 'first' in self.postprocess_nav_buttons:
                self.postprocess_nav_buttons['first'].config(state="normal" if current_idx > 0 else "disabled")
            if 'prev' in self.postprocess_nav_buttons:
                self.postprocess_nav_buttons['prev'].config(state="normal" if current_idx > 0 else "disabled")
            if 'next' in self.postprocess_nav_buttons:
                self.postprocess_nav_buttons['next'].config(state="normal" if current_idx < total_frames - 1 else "disabled")
            if 'last' in self.postprocess_nav_buttons:
                self.postprocess_nav_buttons['last'].config(state="normal" if current_idx < total_frames - 1 else "disabled")
    
    def postprocess_go_to_first_frame(self):
        """Go to first frame"""
        if len(self.postprocess_frame_list) > 0:
            self.postprocess_current_frame_index = 0
            self.postprocess_display_frame(self.postprocess_frame_list[0])
    
    def postprocess_go_to_prev_frame(self):
        """Go to previous frame"""
        if len(self.postprocess_frame_list) > 0 and self.postprocess_current_frame_index > 0:
            self.postprocess_current_frame_index -= 1
            self.postprocess_display_frame(self.postprocess_frame_list[self.postprocess_current_frame_index])
    
    def postprocess_go_to_next_frame(self):
        """Go to next frame"""
        if len(self.postprocess_frame_list) > 0 and self.postprocess_current_frame_index < len(self.postprocess_frame_list) - 1:
            self.postprocess_current_frame_index += 1
            self.postprocess_display_frame(self.postprocess_frame_list[self.postprocess_current_frame_index])
    
    def postprocess_go_to_last_frame(self):
        """Go to last frame"""
        if len(self.postprocess_frame_list) > 0:
            self.postprocess_current_frame_index = len(self.postprocess_frame_list) - 1
            self.postprocess_display_frame(self.postprocess_frame_list[self.postprocess_current_frame_index])
    
    def approve_all_high_confidence(self):
        """Approve all corrections with confidence >= 0.65"""
        approved_count = 0
        to_approve = []
        
        for track_id, correction in list(self.pending_corrections.items()):
            if correction['confidence'] >= 0.65 and correction['suggested_assignment']:
                to_approve.append((track_id, correction))
        
        for track_id, correction in to_approve:
            if correction['suggested_assignment']:
                self.track_assignments[track_id] = correction['suggested_assignment']
            self.auto_corrections[track_id] = correction
            del self.pending_corrections[track_id]
            approved_count += 1
        
        self.update_corrections_display()
        messagebox.showinfo("Success", f"Approved {approved_count} high-confidence corrections")
    
    def reject_all_pending(self):
        """Reject all pending corrections"""
        count = len(self.pending_corrections)
        self.pending_corrections.clear()
        self.update_corrections_display()
        messagebox.showinfo("Success", f"Rejected {count} pending corrections")
    
    def export_corrected_csv(self):
        """Export CSV with corrected player IDs"""
        if self.tracks_data is None:
            messagebox.showerror("Error", "No CSV data loaded")
            return
        
        # Combine auto and approved corrections (including manual ones)
        # Manual corrections are stored in pending_corrections with confidence 1.0
        all_corrections = {**self.auto_corrections}
        
        # Also include pending corrections that have been manually edited or approved
        # These are corrections that the user has reviewed and wants to apply
        for track_id, correction in self.pending_corrections.items():
            # Include if it has a suggested assignment (user has made a decision)
            if correction.get('suggested_assignment'):
                all_corrections[track_id] = correction
        
        if len(all_corrections) == 0:
            messagebox.showwarning("Warning", "No corrections to apply. Please approve or update corrections first.")
            return
        
        # Ask for output file
        output_file = filedialog.asksaveasfilename(
            title="Save Corrected CSV As",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=os.path.basename(self.csv_file).replace('.csv', '-corrected.csv') if self.csv_file else "corrected.csv"
        )
        
        if not output_file:
            return
        
        try:
            # Create copy of data
            corrected_data = self.tracks_data.copy()
            
            # Get track ID column
            track_id_col = None
            for col in ['track_id', 'player_id', 'id']:
                if col in corrected_data.columns:
                    track_id_col = col
                    break
            
            if track_id_col is None:
                messagebox.showerror("Error", "Could not find track ID column")
                return
            
            # Apply corrections
            correction_log = []
            for track_id, correction in all_corrections.items():
                if correction['suggested_assignment']:
                    # Update player_id column if it exists
                    if 'player_id' in corrected_data.columns:
                        mask = corrected_data[track_id_col] == track_id
                        corrected_data.loc[mask, 'player_id'] = correction['suggested_assignment']
                    
                    correction_log.append({
                        'track_id': int(track_id),
                        'original_assignment': correction['current_assignment'],
                        'corrected_assignment': correction['suggested_assignment'],
                        'confidence': correction['confidence'],
                        'methods': correction['methods'],
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Save corrected CSV
            corrected_data.to_csv(output_file, index=False)
            
            # Save correction log
            log_file = output_file.replace('.csv', '-corrections.json')
            with open(log_file, 'w') as f:
                json.dump(correction_log, f, indent=2)
            
            # Update gallery if requested
            if self.update_gallery_var.get():
                self.update_player_gallery_from_corrections(all_corrections)
            
            # Generate anchor frames if requested
            if self.generate_anchors_var.get():
                self.generate_anchor_frames_from_corrections(all_corrections)
            
            messagebox.showinfo("Success", 
                f"Exported corrected CSV to:\n{output_file}\n\n"
                f"Correction log saved to:\n{log_file}\n\n"
                f"Applied {len(correction_log)} corrections.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not export corrected CSV: {e}")
            import traceback
            traceback.print_exc()
    
    def update_player_gallery_from_corrections(self, corrections):
        """Update player gallery with new features from corrected tracks"""
        if self.player_gallery_obj is None or self.reid_tracker is None:
            return
        
        if self.video_file is None or not os.path.exists(self.video_file):
            return
        
        try:
            cap = cv2.VideoCapture(self.video_file)
            if not cap.isOpened():
                return
            
            # Get track ID and frame columns
            track_id_col = None
            for col in ['track_id', 'player_id', 'id']:
                if col in self.tracks_data.columns:
                    track_id_col = col
                    break
            
            frame_col = None
            for col in ['frame', 'frame_num', 'frame_number']:
                if col in self.tracks_data.columns:
                    frame_col = col
                    break
            
            if track_id_col is None or frame_col is None:
                cap.release()
                return
            
            updated_count = 0
            for track_id, correction in corrections.items():
                # Process all approved corrections (including manual ones with confidence 1.0)
                # Only skip if no suggested assignment
                if not correction.get('suggested_assignment'):
                    continue
                
                player_name = correction['suggested_assignment']
                track_data = self.tracks_data[self.tracks_data[track_id_col] == track_id]
                
                if len(track_data) == 0:
                    continue
                
                # Sample frames for feature extraction (up to 10 frames for better coverage)
                frame_series = track_data[frame_col]
                if not isinstance(frame_series, pd.Series):
                    frame_series = pd.Series(frame_series)
                frame_nums = sorted(frame_series.dropna().unique().astype(int))
                # Sample evenly across the track
                if len(frame_nums) > 10:
                    step = len(frame_nums) // 10
                    frame_nums = frame_nums[::step][:10]
                else:
                    frame_nums = frame_nums[:10]
                
                all_features = []
                all_foot_features = []
                reference_bbox = None
                reference_frame_num = None
                
                for frame_num in frame_nums:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_num))
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    
                    # Get bbox
                    frame_data = track_data[track_data[frame_col] == frame_num]
                    if len(frame_data) == 0 or not isinstance(frame_data, pd.DataFrame):
                        continue
                    
                    row = frame_data.iloc[0]
                    bbox = None
                    if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                        bbox = (int(row['x1']), int(row['y1']), int(row['x2']), int(row['y2']))
                    elif 'player_x' in row and 'player_y' in row:
                        cx, cy = float(row['player_x']), float(row['player_y'])
                        bbox = (int(cx - 40), int(cy - 60), int(cx + 40), int(cy + 60))
                    
                    if bbox and SUPERVISION_AVAILABLE and Detections is not None:
                        dummy_detections = Detections(
                            xyxy=np.array([[bbox[0], bbox[1], bbox[2], bbox[3]]]),
                            confidence=np.array([0.9])
                        )
                        
                        # Extract body Re-ID features
                        try:
                            features = self.reid_tracker.extract_features(frame, dummy_detections)
                            if len(features) > 0:
                                all_features.append(features[0])
                        except Exception:
                            pass
                        
                        # Extract foot features if available
                        try:
                            if hasattr(self.reid_tracker, 'extract_foot_features'):
                                foot_features = self.reid_tracker.extract_foot_features(frame, dummy_detections)
                                if len(foot_features) > 0 and foot_features.shape[0] > 0:
                                    all_foot_features.append(foot_features[0])
                        except Exception:
                            pass
                        
                        # Store reference bbox and frame for first valid frame
                        if reference_bbox is None:
                            reference_bbox = bbox
                            reference_frame_num = frame_num
                
                # Update gallery if we extracted any features
                if len(all_features) > 0:
                    # Average body features
                    avg_features = np.mean(all_features, axis=0)
                    avg_features = avg_features / (np.linalg.norm(avg_features) + 1e-8)
                    
                    # Average foot features if available
                    avg_foot_features = None
                    if len(all_foot_features) > 0:
                        avg_foot_features = np.mean(all_foot_features, axis=0)
                        avg_foot_features = avg_foot_features / (np.linalg.norm(avg_foot_features) + 1e-8)
                    
                    # Update gallery
                    player_id = player_name.lower().replace(" ", "_")
                    self.player_gallery_obj.update_player(
                        player_id=player_id,
                        name=player_name,
                        features=avg_features,
                        foot_features=avg_foot_features,
                        reference_frame={
                            'video_path': self.video_file,
                            'frame_num': reference_frame_num if reference_frame_num else (frame_nums[0] if frame_nums else 0),
                            'bbox': list(reference_bbox) if reference_bbox else None,
                            'source': 'post_processing',
                            'confidence': correction.get('confidence', 1.0),
                            'correction_method': ', '.join(correction.get('methods', ['manual']))
                        }
                    )
                    updated_count += 1
            
            cap.release()
            self.player_gallery_obj.save_gallery()
            print(f"✓ Updated player gallery with {updated_count} correction(s)")
            if updated_count > 0:
                gallery_file = getattr(self.player_gallery_obj, 'gallery_file', 'player_gallery.json')
                messagebox.showinfo("Gallery Updated", 
                    f"Successfully updated player gallery with Re-ID features from {updated_count} corrected track(s).\n\n"
                    f"Features extracted:\n"
                    f"- Body Re-ID features: Yes\n"
                    f"- Foot features: {'Yes' if any('foot_features' in str(c) for c in corrections.values()) else 'Attempted'}\n\n"
                    f"Gallery saved to: {gallery_file}")
            
        except Exception as e:
            print(f"Error updating player gallery: {e}")
            import traceback
            traceback.print_exc()
    
    def generate_anchor_frames_from_corrections(self, corrections):
        """Generate anchor frames from approved corrections"""
        if self.tracks_data is None:
            return
        
        if self.video_file is None:
            return
        
        try:
            # Get track ID and frame columns
            track_id_col = None
            for col in ['track_id', 'player_id', 'id']:
                if col in self.tracks_data.columns:
                    track_id_col = col
                    break
            
            frame_col = None
            for col in ['frame', 'frame_num', 'frame_number']:
                if col in self.tracks_data.columns:
                    frame_col = col
                    break
            
            if track_id_col is None or frame_col is None:
                return
            
            anchor_frames = {}
            
            for track_id, correction in corrections.items():
                if not correction['suggested_assignment']:
                    continue
                
                player_name = correction['suggested_assignment']
                track_data = self.tracks_data[self.tracks_data[track_id_col] == track_id]
                
                # Get team and jersey_number from gallery if available
                team = None
                jersey_number = None
                
                # Try PlayerGallery object first (preferred - has full profile data)
                if self.player_gallery_obj:
                    try:
                        player_id = player_name.lower().replace(" ", "_")
                        if hasattr(self.player_gallery_obj, 'get_player'):
                            profile = self.player_gallery_obj.get_player(player_id)
                            if profile:
                                if hasattr(profile, 'team'):
                                    team = profile.team
                                if hasattr(profile, 'jersey_number'):
                                    jersey_number = profile.jersey_number
                        elif player_id in self.player_gallery_obj.players:
                            # Fallback to dict access
                            profile = self.player_gallery_obj.players[player_id]
                            if isinstance(profile, dict):
                                team = profile.get('team')
                                jersey_number = profile.get('jersey_number')
                    except Exception as e:
                        # Fall through - team/jersey will remain None
                        pass
                
                # Select representative frames (first, middle, last)
                frame_series = track_data[frame_col]
                if not isinstance(frame_series, pd.Series):
                    frame_series = pd.Series(frame_series)
                frame_nums = sorted(frame_series.dropna().unique().astype(int))
                if len(frame_nums) == 0:
                    continue
                
                representative_frames = [
                    frame_nums[0],
                    frame_nums[len(frame_nums) // 2] if len(frame_nums) > 1 else frame_nums[0],
                    frame_nums[-1] if len(frame_nums) > 1 else frame_nums[0]
                ]
                
                for frame_num in representative_frames:
                    frame_str = str(frame_num)
                    if frame_str not in anchor_frames:
                        anchor_frames[frame_str] = []
                    
                    # Get bbox for this frame (CRITICAL: bbox is essential for matching when track_id changes)
                    frame_data = track_data[track_data[frame_col] == frame_num]
                    if len(frame_data) == 0 or not isinstance(frame_data, pd.DataFrame):
                        continue
                    
                    row = frame_data.iloc[0]
                    bbox = None
                    bbox_source = None
                    
                    # Priority 1: Direct bbox columns (most accurate)
                    if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                        try:
                            bbox = [float(row['x1']), float(row['y1']), float(row['x2']), float(row['y2'])]
                            bbox_source = 'x1/y1/x2/y2'
                        except (ValueError, TypeError):
                            pass
                    
                    # Priority 2: Center point columns (fallback - convert to bbox)
                    if bbox is None and 'player_x' in row and 'player_y' in row:
                        try:
                            x = float(row['player_x'])
                            y = float(row['player_y'])
                            # Default bbox size: 80px wide, 120px tall (centered on player position)
                            bbox = [x - 40, y - 60, x + 40, y + 60]
                            bbox_source = 'player_x/player_y'
                        except (ValueError, TypeError):
                            pass
                    
                    anchor = {
                        'player_name': player_name,
                        'track_id': int(track_id),
                        'confidence': 1.00,  # CRITICAL: Anchor frames must have 1.00 confidence for maximum protection
                        'team': team or '',
                        'source': 'post_processing'
                    }
                    
                    # Add jersey_number if available
                    if jersey_number:
                        anchor['jersey_number'] = jersey_number
                    
                    # CRITICAL: Always include bbox if available (essential for matching when track_id changes)
                    if bbox:
                        anchor['bbox'] = bbox
                        # Store bbox source for diagnostics (optional metadata)
                        if bbox_source:
                            anchor['bbox_source'] = bbox_source
                    else:
                        # Warn if bbox cannot be determined (bbox is critical for matching)
                        print(f"  ⚠ WARNING: Frame {frame_num}, Track {track_id}, Player '{player_name}' - no bbox available (bbox is critical for matching when track_id changes)")
                    
                    anchor_frames[frame_str].append(anchor)
            
            # Save anchor frames
            video_basename = os.path.splitext(os.path.basename(self.video_file))[0]
            output_file = os.path.join(os.path.dirname(self.video_file), 
                                      f"PlayerTagsSeed-{video_basename}-PostProcessed.json")
            
            # Validation: Check anchor frames before saving
            total_frames = len(anchor_frames)
            frames_with_bbox = 0
            frames_without_bbox = 0
            frames_with_jersey = 0
            frames_with_team = 0
            confidence_issues = []
            total_anchor_entries = 0
            
            for frame_str, anchors in anchor_frames.items():
                for anchor in anchors:
                    total_anchor_entries += 1
                    # Check bbox
                    if anchor.get('bbox'):
                        frames_with_bbox += 1
                    else:
                        frames_without_bbox += 1
                    
                    # Check jersey_number
                    if anchor.get('jersey_number'):
                        frames_with_jersey += 1
                    
                    # Check team
                    if anchor.get('team'):
                        frames_with_team += 1
                    
                    # Validate confidence is 1.00
                    conf = anchor.get('confidence', 0.0)
                    if conf != 1.00:
                        confidence_issues.append(f"Frame {frame_str}, Track {anchor.get('track_id')}: confidence={conf} (expected 1.00)")
            
            # Add validation to output data
            output_data['total_frames'] = total_frames
            output_data['total_anchor_entries'] = total_anchor_entries
            output_data['validation'] = {
                'frames_with_bbox': frames_with_bbox,
                'frames_without_bbox': frames_without_bbox,
                'frames_with_jersey': frames_with_jersey,
                'frames_with_team': frames_with_team,
                'confidence_issues': len(confidence_issues)
            }
            
            print(f"✓ Generated anchor frames: {output_file}")
            print(f"✓ Anchor Frame Export Validation:")
            print(f"  • Total frames: {total_frames}")
            print(f"  • Total anchor entries: {total_anchor_entries}")
            if total_anchor_entries > 0:
                print(f"  • Frames with bbox: {frames_with_bbox} ({frames_with_bbox/total_anchor_entries*100:.1f}%)")
                if frames_without_bbox > 0:
                    print(f"  • Frames without bbox: {frames_without_bbox} ({frames_without_bbox/total_anchor_entries*100:.1f}%)")
                print(f"  • Frames with jersey: {frames_with_jersey} ({frames_with_jersey/total_anchor_entries*100:.1f}%)" if frames_with_jersey > 0 else "")
                print(f"  • Frames with team: {frames_with_team} ({frames_with_team/total_anchor_entries*100:.1f}%)" if frames_with_team > 0 else "")
            if confidence_issues:
                print(f"  ⚠ Confidence issues: {len(confidence_issues)}")
            
            # Build validation message
            validation_msg = f"Generated anchor frames from {len(corrections)} corrections:\n{output_file}\n\n"
            validation_msg += f"Validation Summary:\n"
            validation_msg += f"  • Total frames: {total_frames}\n"
            validation_msg += f"  • Total anchor entries: {total_anchor_entries}\n"
            if total_anchor_entries > 0:
                validation_msg += f"  • Frames with bbox: {frames_with_bbox} ({frames_with_bbox/total_anchor_entries*100:.1f}%)\n"
                if frames_without_bbox > 0:
                    validation_msg += f"  • Frames without bbox: {frames_without_bbox} ({frames_without_bbox/total_anchor_entries*100:.1f}%)\n"
                validation_msg += f"  • Frames with jersey: {frames_with_jersey} ({frames_with_jersey/total_anchor_entries*100:.1f}%)\n" if frames_with_jersey > 0 else ""
                validation_msg += f"  • Frames with team: {frames_with_team} ({frames_with_team/total_anchor_entries*100:.1f}%)\n" if frames_with_team > 0 else ""
            
            if frames_without_bbox > 0:
                validation_msg += f"\n⚠ WARNING: {frames_without_bbox} anchor entries are missing bbox.\n"
                validation_msg += f"Bbox is critical for matching when track_id changes between sessions.\n"
            
            if confidence_issues:
                validation_msg += f"\n⚠ WARNING: {len(confidence_issues)} anchor frames have incorrect confidence.\n"
            
            messagebox.showinfo("Success", validation_msg)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not generate anchor frames: {e}")
            import traceback
            traceback.print_exc()
    
    def __del__(self):
        """Cleanup video capture on close"""
        if self.video_cap is not None:
            self.video_cap.release()
        if hasattr(self, 'postprocess_video_cap') and self.postprocess_video_cap is not None:
            self.postprocess_video_cap.release()


if __name__ == "__main__":
    app = TrackReviewAssigner()
    app.root.mainloop()

