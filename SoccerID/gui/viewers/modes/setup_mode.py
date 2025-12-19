"""
Setup Mode - Interactive player tagging for initial analysis
Migrated from SetupWizard
"""

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
from ..unified_viewer import BaseMode


class SetupMode(BaseMode):
    """Setup Wizard mode - for tagging players before analysis"""
    
    def create_ui(self):
        """Create setup mode UI"""
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
        
        # Navigation controls
        nav_frame = ttk.LabelFrame(controls_frame, text="Navigation", padding=5)
        nav_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(nav_frame, text="◄◄ First", command=self.first_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="◄ Prev", command=self.prev_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="Next ►", command=self.next_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="Last ►►", command=self.last_frame).pack(side=tk.LEFT, padx=2)
        
        # Frame number
        frame_frame = ttk.Frame(nav_frame)
        frame_frame.pack(fill=tk.X, pady=5)
        ttk.Label(frame_frame, text="Frame:").pack(side=tk.LEFT)
        self.frame_var = tk.IntVar(value=0)
        frame_spin = ttk.Spinbox(frame_frame, from_=0, to=999999, textvariable=self.frame_var, width=10)
        frame_spin.pack(side=tk.LEFT, padx=5)
        frame_spin.bind('<Return>', lambda e: self.goto_frame())
        
        # Detection controls
        detect_frame = ttk.LabelFrame(controls_frame, text="Detection", padding=5)
        detect_frame.pack(fill=tk.X, pady=5)
        
        self.init_button = ttk.Button(detect_frame, text="Initialize Detection", 
                                      command=self.initialize_detection)
        self.init_button.pack(fill=tk.X, pady=2)
        
        # Tagging controls
        tag_frame = ttk.LabelFrame(controls_frame, text="Tagging", padding=5)
        tag_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(tag_frame, text="Player Name:").pack(anchor=tk.W)
        self.player_name_var = tk.StringVar()
        player_combo = ttk.Combobox(tag_frame, textvariable=self.player_name_var, width=20)
        player_combo.pack(fill=tk.X, pady=2)
        
        # Load player names
        if self.gallery_manager.is_initialized():
            player_names = self.gallery_manager.get_player_names()
            player_combo['values'] = player_names
        
        ttk.Button(tag_frame, text="Tag Selected", command=self.tag_player).pack(fill=tk.X, pady=2)
        
        # Detections list
        detections_frame = ttk.LabelFrame(controls_frame, text="Detections", padding=5)
        detections_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.detections_listbox = tk.Listbox(detections_frame, height=10)
        self.detections_listbox.pack(fill=tk.BOTH, expand=True)
        self.detections_listbox.bind('<<ListboxSelect>>', self.on_detection_select)
        
        # Status
        self.status_label = ttk.Label(controls_frame, text="Ready")
        self.status_label.pack(fill=tk.X, pady=5)
    
    def display_frame(self, frame: np.ndarray, frame_num: int):
        """Display a frame with detections"""
        if frame is None:
            return
        
        # Get detections for this frame
        detections = self.detection_manager.get_detections(frame_num)
        
        # Draw frame
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
                
                # Add label if mapped
                tid_str = str(int(track_id))
                mappings = self.viewer.get_approved_mappings()
                if tid_str in mappings:
                    player_name = mappings[tid_str][0]
                    cv2.putText(display_frame, player_name, (x1, y1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Convert to PhotoImage and display
        self._display_image(display_frame)
        
        # Update detections list
        self.update_detections_list(detections)
    
    def _display_image(self, frame: np.ndarray):
        """Display image on canvas"""
        # Resize to fit canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            self.canvas.update_idletasks()
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return
        
        # Calculate scale
        scale = min(canvas_width / frame.shape[1], canvas_height / frame.shape[0])
        new_width = int(frame.shape[1] * scale)
        new_height = int(frame.shape[0] * scale)
        
        # Resize
        resized = cv2.resize(frame, (new_width, new_height))
        
        # Convert to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Convert to PhotoImage
        img = Image.fromarray(rgb)
        photo = ImageTk.PhotoImage(image=img)
        
        # Display
        self.canvas.delete("all")
        self.canvas.create_image(canvas_width // 2, canvas_height // 2, 
                                image=photo, anchor=tk.CENTER)
        self.canvas.image = photo  # Keep reference
    
    def initialize_detection(self):
        """Initialize YOLO detection"""
        if not self.video_manager.cap:
            messagebox.showerror("Error", "Please load a video first")
            return
        
        self.status_label.config(text="Initializing detection...")
        self.init_button.config(state=tk.DISABLED)
        
        if self.detection_manager.initialize():
            # Process first few frames
            for i in range(min(30, self.video_manager.total_frames)):
                frame = self.video_manager.get_frame(i)
                if frame is not None:
                    self.detection_manager.detect_frame(frame, i)
            
            self.status_label.config(text="Detection initialized")
            self.load_frame(0)
        else:
            messagebox.showerror("Error", "Failed to initialize detection")
            self.status_label.config(text="Error initializing detection")
        
        self.init_button.config(state=tk.NORMAL)
    
    def tag_player(self):
        """Tag selected detection with player name"""
        selection = self.detections_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a detection")
            return
        
        player_name = self.player_name_var.get().strip()
        if not player_name:
            messagebox.showwarning("Warning", "Please enter a player name")
            return
        
        # Get selected detection
        # TODO: Implement tagging logic
        self.status_label.config(text=f"Tagged as {player_name}")
    
    def update_detections_list(self, detections):
        """Update detections listbox"""
        self.detections_listbox.delete(0, tk.END)
        
        if detections is None or len(detections) == 0:
            return
        
        mappings = self.viewer.get_approved_mappings()
        
        for i, (xyxy, track_id, conf) in enumerate(zip(
            detections.xyxy,
            detections.tracker_id,
            detections.confidence
        )):
            if track_id is None:
                continue
            
            tid_str = str(int(track_id))
            if tid_str in mappings:
                player_name = mappings[tid_str][0]
                label = f"Track #{track_id}: {player_name}"
            else:
                label = f"Track #{track_id}: Untagged"
            
            self.detections_listbox.insert(tk.END, label)
    
    def on_detection_select(self, event):
        """Handle detection selection"""
        pass
    
    def first_frame(self):
        """Go to first frame"""
        self.goto_frame(0)
    
    def prev_frame(self):
        """Go to previous frame"""
        self.goto_frame(max(0, self.viewer.current_frame_num - 1))
    
    def next_frame(self):
        """Go to next frame"""
        self.goto_frame(min(self.video_manager.total_frames - 1, 
                          self.viewer.current_frame_num + 1))
    
    def last_frame(self):
        """Go to last frame"""
        self.goto_frame(self.video_manager.total_frames - 1)
    
    def goto_frame(self, frame_num=None):
        """Go to specific frame"""
        if frame_num is None:
            frame_num = self.frame_var.get()
        
        frame_num = max(0, min(frame_num, self.video_manager.total_frames - 1))
        self.frame_var.set(frame_num)
        self.viewer.load_frame(frame_num)
    
    def load_frame(self, frame_num: int):
        """Load and display a frame"""
        self.viewer.load_frame(frame_num)
    
    def on_video_loaded(self):
        """Called when video is loaded"""
        if self.video_manager.total_frames > 0:
            self.frame_var.config(to=self.video_manager.total_frames - 1)
            self.load_frame(0)
    
    def on_csv_loaded(self):
        """Called when CSV is loaded"""
        # Refresh display
        self.load_frame(self.viewer.current_frame_num)
    
    def cleanup(self):
        """Clean up resources"""
        pass

