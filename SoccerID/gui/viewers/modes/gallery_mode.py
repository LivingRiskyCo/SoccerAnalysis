"""
Gallery Mode - Cross-video player gallery building
Migrated from PlayerGallerySeeder
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
from ..unified_viewer import BaseMode


class GalleryMode(BaseMode):
    """Gallery seeder mode - for building cross-video player database"""
    
    def create_ui(self):
        """Create gallery mode UI"""
        # Main layout: video on left, gallery controls on right
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Video canvas
        video_frame = ttk.Frame(main_frame)
        video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.canvas = tk.Canvas(video_frame, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Gallery panel
        gallery_frame = ttk.Frame(main_frame, width=400)
        gallery_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        gallery_frame.pack_propagate(False)
        
        # Gallery list
        list_frame = ttk.LabelFrame(gallery_frame, text="Player Gallery", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.gallery_listbox = tk.Listbox(list_frame, height=15)
        self.gallery_listbox.pack(fill=tk.BOTH, expand=True)
        self.gallery_listbox.bind('<<ListboxSelect>>', self.on_player_select)
        
        # Add player controls
        add_frame = ttk.LabelFrame(gallery_frame, text="Add Player", padding=5)
        add_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(add_frame, text="Player Name:").pack(anchor=tk.W)
        self.player_name_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.player_name_var, width=20).pack(fill=tk.X, pady=2)
        
        ttk.Button(add_frame, text="Add to Gallery", command=self.add_player).pack(fill=tk.X, pady=2)
        
        # Navigation
        nav_frame = ttk.LabelFrame(gallery_frame, text="Navigation", padding=5)
        nav_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(nav_frame, text="◄◄ First", command=self.first_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="◄ Prev", command=self.prev_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="Next ►", command=self.next_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="Last ►►", command=self.last_frame).pack(side=tk.LEFT, padx=2)
        
        # Status
        self.status_label = ttk.Label(gallery_frame, text="Ready")
        self.status_label.pack(fill=tk.X, pady=5)
        
        # Update gallery list
        self.update_gallery_list()
    
    def display_frame(self, frame: np.ndarray, frame_num: int):
        """Display a frame"""
        if frame is None:
            return
        
        # Get detections
        detections = self.detection_manager.get_detections(frame_num)
        
        display_frame = frame.copy()
        
        if detections is not None and len(detections) > 0:
            # Draw detections
            for i, (xyxy, track_id, conf) in enumerate(zip(
                detections.xyxy,
                detections.tracker_id,
                detections.confidence
            )):
                if track_id is None:
                    continue
                
                x1, y1, x2, y2 = map(int, xyxy)
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # Try to match with gallery
                if self.reid_manager.is_initialized():
                    features = self.reid_manager.get_features(frame_num, track_id)
                    if features is not None and self.gallery_manager.is_initialized():
                        match = self.gallery_manager.match_player(features)
                        if match:
                            player_name, confidence, _ = match
                            if confidence > 0.6:
                                cv2.putText(display_frame, f"{player_name} ({confidence:.2f})", 
                                          (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        self._display_image(display_frame)
    
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
    
    def update_gallery_list(self):
        """Update gallery listbox"""
        self.gallery_listbox.delete(0, tk.END)
        
        if self.gallery_manager.is_initialized():
            player_names = self.gallery_manager.get_player_names()
            for name in sorted(player_names):
                self.gallery_listbox.insert(tk.END, name)
    
    def on_player_select(self, event):
        """Handle player selection"""
        pass
    
    def add_player(self):
        """Add current selection to gallery"""
        player_name = self.player_name_var.get().strip()
        if not player_name:
            messagebox.showwarning("Warning", "Please enter a player name")
            return
        
        # TODO: Extract features from current selection and add to gallery
        self.status_label.config(text=f"Added {player_name} to gallery")
        self.update_gallery_list()
    
    def first_frame(self):
        self.goto_frame(0)
    
    def prev_frame(self):
        self.goto_frame(max(0, self.viewer.current_frame_num - 1))
    
    def next_frame(self):
        self.goto_frame(min(self.video_manager.total_frames - 1, 
                          self.viewer.current_frame_num + 1))
    
    def last_frame(self):
        self.goto_frame(self.video_manager.total_frames - 1)
    
    def goto_frame(self, frame_num: int):
        self.viewer.load_frame(frame_num)
    
    def on_video_loaded(self):
        if self.video_manager.total_frames > 0:
            self.goto_frame(0)
    
    def on_csv_loaded(self):
        pass
    
    def cleanup(self):
        # Save gallery
        if self.gallery_manager.is_initialized():
            self.gallery_manager.save_gallery()

