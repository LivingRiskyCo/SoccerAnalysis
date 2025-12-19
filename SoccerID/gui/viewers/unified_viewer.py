"""
Unified Player Viewer
Combines Setup Wizard, Playback Viewer, and Gallery Seeder into a single unified interface
with mode switching for seamless workflow
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
import sys
from pathlib import Path
from typing import Optional, Dict

# Add parent directories to path
current_file = Path(__file__).resolve()
soccerid_dir = current_file.parent.parent.parent
parent_dir = soccerid_dir.parent

if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(soccerid_dir) not in sys.path:
    sys.path.insert(0, str(soccerid_dir))

# Import core managers
from .core import (
    VideoManager, DetectionManager, ReIDManager, 
    GalleryManager, CSVManager, AnchorFrameManager
)

# Import modes - defer until after BaseMode is defined
# We'll import them in switch_mode to avoid circular dependency
SetupMode = None
PlaybackMode = None
GalleryMode = None


class UnifiedViewer:
    """
    Unified viewer that combines:
    - Setup Wizard (tagging mode)
    - Playback Viewer (playback mode)  
    - Gallery Seeder (gallery mode)
    """
    
    MODES = {
        'setup': 'Setup Wizard - Tag players for initial analysis',
        'playback': 'Playback Viewer - Review and visualize tracking data',
        'gallery': 'Gallery Seeder - Build cross-video player database'
    }
    
    def __init__(self, root, mode='setup', video_path=None, csv_path=None):
        self.root = root
        self.mode = mode
        self.root.title(f"Unified Player Viewer - {self.MODES.get(mode, mode)}")
        
        # Window setup
        self.root.geometry("1920x1200")
        self.root.minsize(1600, 1000)
        self.root.resizable(True, True)
        
        # Initialize core managers
        self.video_manager = VideoManager(video_path)
        self.detection_manager = DetectionManager()
        self.reid_manager = ReIDManager()
        self.gallery_manager = GalleryManager()
        self.csv_manager = CSVManager(csv_path)
        self.anchor_manager = AnchorFrameManager()
        
        # Initialize gallery and Re-ID
        self.gallery_manager.initialize()
        self.reid_manager.initialize()
        
        # Current mode instance
        self.current_mode_instance = None
        
        # Shared state
        self.approved_mappings = {}  # track_id -> (player_name, team, jersey_number)
        self.current_frame_num = 0
        
        # Create UI
        self.create_ui()
        
        # Configure initial mode
        self.switch_mode(mode)
        
        # Auto-load video and CSV if provided
        if video_path and self.video_manager.load_video(video_path):
            self.current_frame_num = 0
            self.load_frame(0)
        
        if csv_path:
            self.csv_manager.load_csv(csv_path)
            # Extract player assignments from CSV
            csv_assignments = self.csv_manager.extract_player_assignments()
            for pid_str, (player_name, team, jersey_number) in csv_assignments.items():
                if pid_str not in self.approved_mappings:
                    self.approved_mappings[pid_str] = (player_name, team, jersey_number)
    
    def create_ui(self):
        """Create unified UI with mode selector"""
        # Top toolbar with mode selector
        toolbar = ttk.Frame(self.root, padding="5")
        toolbar.pack(fill=tk.X)
        
        # Mode selector
        ttk.Label(toolbar, text="Mode:").pack(side=tk.LEFT, padx=5)
        self.mode_var = tk.StringVar(value=self.mode)
        mode_combo = ttk.Combobox(toolbar, textvariable=self.mode_var, 
                                  values=list(self.MODES.keys()), 
                                  state='readonly', width=20)
        mode_combo.pack(side=tk.LEFT, padx=5)
        mode_combo.bind('<<ComboboxSelected>>', self.on_mode_changed)
        
        # File loading buttons
        ttk.Button(toolbar, text="Load Video", command=self.load_video).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Load CSV", command=self.load_csv).pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_label = ttk.Label(toolbar, text="Ready")
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # Main content area (will be populated by mode)
        self.content_frame = ttk.Frame(self.root)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def switch_mode(self, mode: str):
        """Switch between modes"""
        if mode not in self.MODES:
            print(f"Error: Unknown mode: {mode}")
            return
        
        # Clean up current mode
        if self.current_mode_instance:
            self.current_mode_instance.cleanup()
        
        # Clear content frame
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        self.mode = mode
        self.root.title(f"Unified Player Viewer - {self.MODES[mode]}")
        self.mode_var.set(mode)
        
        # Try to import modes if not already imported
        global SetupMode, PlaybackMode, GalleryMode
        if SetupMode is None or PlaybackMode is None or GalleryMode is None:
            try:
                from .modes.setup_mode import SetupMode
                from .modes.playback_mode import PlaybackMode
                from .modes.gallery_mode import GalleryMode
            except ImportError as e:
                import traceback
                error_msg = f"Could not import viewer modes: {e}\n\n{traceback.format_exc()}"
                print(f"Error: {error_msg}")
                ttk.Label(self.content_frame, 
                         text=f"Error loading {mode} mode:\n\n{str(e)}\n\nPlease check console for details.",
                         font=('Arial', 12), foreground='red', justify=tk.LEFT).pack(expand=True, padx=20, pady=20)
                self.current_mode_instance = None
                return
        
        # Initialize new mode
        try:
            if mode == 'setup':
                self.current_mode_instance = SetupMode(
                    self.content_frame, 
                    self,
                    self.video_manager,
                    self.detection_manager,
                    self.reid_manager,
                    self.gallery_manager,
                    self.csv_manager,
                    self.anchor_manager
                )
            elif mode == 'playback':
                self.current_mode_instance = PlaybackMode(
                    self.content_frame,
                    self,
                    self.video_manager,
                    self.detection_manager,
                    self.reid_manager,
                    self.gallery_manager,
                    self.csv_manager,
                    self.anchor_manager
                )
            elif mode == 'gallery':
                self.current_mode_instance = GalleryMode(
                    self.content_frame,
                    self,
                    self.video_manager,
                    self.detection_manager,
                    self.reid_manager,
                    self.gallery_manager,
                    self.csv_manager,
                    self.anchor_manager
                )
        except Exception as e:
            import traceback
            error_msg = f"Error initializing {mode} mode: {e}\n\n{traceback.format_exc()}"
            print(f"Error: {error_msg}")
            ttk.Label(self.content_frame, 
                     text=f"Error initializing {mode} mode:\n\n{str(e)}\n\nPlease check console for details.",
                     font=('Arial', 12), foreground='red', justify=tk.LEFT).pack(expand=True, padx=20, pady=20)
            self.current_mode_instance = None
    
    def on_mode_changed(self, event=None):
        """Handle mode change from UI"""
        new_mode = self.mode_var.get()
        if new_mode != self.mode:
            self.switch_mode(new_mode)
    
    def load_video(self):
        """Load video file"""
        filename = filedialog.askopenfilename(
            title="Load Video",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if filename:
            if self.video_manager.load_video(filename):
                self.current_frame_num = 0
                self.load_frame(0)
                if self.current_mode_instance:
                    self.current_mode_instance.on_video_loaded()
    
    def load_csv(self):
        """Load CSV file"""
        filename = filedialog.askopenfilename(
            title="Load CSV Tracking Data",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            if self.csv_manager.load_csv(filename):
                # Extract player assignments
                csv_assignments = self.csv_manager.extract_player_assignments()
                for pid_str, (player_name, team, jersey_number) in csv_assignments.items():
                    if pid_str not in self.approved_mappings:
                        self.approved_mappings[pid_str] = (player_name, team, jersey_number)
                
                if self.current_mode_instance:
                    self.current_mode_instance.on_csv_loaded()
    
    def load_frame(self, frame_num: int):
        """Load and display a frame"""
        if not self.video_manager.cap:
            return
        
        self.current_frame_num = frame_num
        frame = self.video_manager.get_frame(frame_num)
        
        if frame is not None and self.current_mode_instance:
            self.current_mode_instance.display_frame(frame, frame_num)
    
    def get_approved_mappings(self) -> Dict[str, tuple]:
        """Get approved player mappings"""
        # Combine anchor frames and CSV assignments
        mappings = self.approved_mappings.copy()
        
        # Add anchor frame mappings
        anchor_mappings = self.anchor_manager.get_approved_mappings()
        for tid_str, mapping in anchor_mappings.items():
            if tid_str not in mappings:  # Don't overwrite existing
                mappings[tid_str] = mapping
        
        return mappings
    
    def cleanup(self):
        """Clean up resources"""
        if self.current_mode_instance:
            self.current_mode_instance.cleanup()
        self.video_manager.release()
        self.detection_manager.clear_history()
        self.reid_manager.clear_features()


# Base class for mode implementations
class BaseMode:
    """Base class for viewer modes"""
    
    def __init__(self, parent_frame, viewer, video_manager, detection_manager, 
                 reid_manager, gallery_manager, csv_manager, anchor_manager):
        self.parent_frame = parent_frame
        self.viewer = viewer
        self.video_manager = video_manager
        self.detection_manager = detection_manager
        self.reid_manager = reid_manager
        self.gallery_manager = gallery_manager
        self.csv_manager = csv_manager
        self.anchor_manager = anchor_manager
        
        self.create_ui()
    
    def create_ui(self):
        """Create mode-specific UI - override in subclasses"""
        pass
    
    def display_frame(self, frame: np.ndarray, frame_num: int):
        """Display a frame - override in subclasses"""
        pass
    
    def on_video_loaded(self):
        """Called when video is loaded - override in subclasses"""
        pass
    
    def on_csv_loaded(self):
        """Called when CSV is loaded - override in subclasses"""
        pass
    
    def cleanup(self):
        """Clean up mode-specific resources - override in subclasses"""
        pass

