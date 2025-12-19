"""
Playback Mode - Video playback with CSV overlays
Migrated from PlaybackViewer
"""

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
from ..unified_viewer import BaseMode


class PlaybackMode(BaseMode):
    """Playback viewer mode - for reviewing tracking data"""
    
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
        controls_frame = ttk.Frame(main_frame, width=400)
        controls_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        controls_frame.pack_propagate(False)
        
        # Playback controls
        playback_frame = ttk.LabelFrame(controls_frame, text="Playback", padding=5)
        playback_frame.pack(fill=tk.X, pady=5)
        
        self.play_button = ttk.Button(playback_frame, text="▶ Play", command=self.toggle_play)
        self.play_button.pack(fill=tk.X, pady=2)
        
        ttk.Button(playback_frame, text="◄◄ First", command=self.first_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_frame, text="◄ Prev", command=self.prev_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_frame, text="Next ►", command=self.next_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_frame, text="Last ►►", command=self.last_frame).pack(side=tk.LEFT, padx=2)
        
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
        
        # Status
        self.status_label = ttk.Label(controls_frame, text="Ready")
        self.status_label.pack(fill=tk.X, pady=5)
        
        self.is_playing = False
        self.play_after_id = None
    
    def display_frame(self, frame: np.ndarray, frame_num: int):
        """Display a frame with overlays"""
        if frame is None:
            return
        
        display_frame = frame.copy()
        
        # Draw CSV overlays if available
        if self.csv_manager.is_loaded():
            # Draw players
            if self.show_players_var.get():
                player_data = self.csv_manager.get_player_data(frame_num)
                for player_id, (x, y, team, name, bbox) in player_data.items():
                    # Draw circle at player position
                    cv2.circle(display_frame, (int(x), int(y)), 10, (0, 255, 0), 2)
                    
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
                        # Convert normalized to pixels
                        ball_x = int(ball_x * self.video_manager.width)
                        ball_y = int(ball_y * self.video_manager.height)
                    cv2.circle(display_frame, (int(ball_x), int(ball_y)), 8, (0, 0, 255), -1)
        
        # Display
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
    
    def toggle_play(self):
        """Toggle playback"""
        if not self.video_manager.cap:
            return
        
        self.is_playing = not self.is_playing
        
        if self.is_playing:
            self.play_button.config(text="⏸ Pause")
            self.play()
        else:
            self.play_button.config(text="▶ Play")
            if self.play_after_id:
                self.viewer.root.after_cancel(self.play_after_id)
                self.play_after_id = None
    
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
        delay = int(1000 / self.video_manager.fps)
        self.play_after_id = self.viewer.root.after(delay, self.play)
    
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
            self.frame_var.config(to=self.video_manager.total_frames - 1)
            self.goto_frame(0)
    
    def on_csv_loaded(self):
        self.update_display()
    
    def cleanup(self):
        if self.play_after_id:
            self.viewer.root.after_cancel(self.play_after_id)
        self.is_playing = False

