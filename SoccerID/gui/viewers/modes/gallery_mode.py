"""
Gallery Mode - Cross-video player gallery building
Migrated from PlayerGallerySeeder with full features
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
import sys
from pathlib import Path
from ..unified_viewer import BaseMode

# Try to import YOLO
YOLO_AVAILABLE = False
try:
    from ultralytics import YOLO
    import supervision as sv
    YOLO_AVAILABLE = True
    SUPERVISION_AVAILABLE = True
except ImportError:
    SUPERVISION_AVAILABLE = False

# Try to import color picker
try:
    current_file = Path(__file__).resolve()
    parent_dir = current_file.parent.parent.parent.parent
    color_path = os.path.join(parent_dir, 'color_picker_utils.py')
    if os.path.exists(color_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("color_picker_utils", color_path)
        color_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(color_module)
        create_color_picker_widget = color_module.create_color_picker_widget
        COLOR_PICKER_AVAILABLE = True
    else:
        from color_picker_utils import create_color_picker_widget
        COLOR_PICKER_AVAILABLE = True
except ImportError:
    COLOR_PICKER_AVAILABLE = False
    create_color_picker_widget = None


class GalleryMode(BaseMode):
    """Gallery seeder mode - for building cross-video player database"""
    
    def __init__(self, parent_frame, viewer, video_manager, detection_manager, 
                 reid_manager, gallery_manager, csv_manager, anchor_manager):
        # Initialize attributes BEFORE calling super (which calls create_ui)
        # YOLO model
        self.yolo_model = None
        
        # Detection state
        self.detected_players = []  # List of bboxes
        self.detected_player_matches = {}  # bbox -> (player_id, player_name, confidence)
        self.selected_bbox = None
        self.drawing_box = False
        self.box_start = None
        self.box_end = None
        
        # Canvas state
        self.scale_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        
        # Playback state (needed in create_ui)
        self.is_playing = False
        self.play_after_id = None
        self.playback_speed = 1.0
        self.frame_var = None
        self.frame_slider = None
        self.frame_label = None
        self.goto_frame_var = None
        self.speed_var = None
        self.play_button = None
        
        # Now call super (which will call create_ui)
        super().__init__(parent_frame, viewer, video_manager, detection_manager,
                        reid_manager, gallery_manager, csv_manager, anchor_manager)
    
    def create_ui(self):
        """Create gallery mode UI"""
        # Main layout: video on left, gallery controls on right
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Video canvas with drawing support
        video_frame = ttk.Frame(main_frame)
        video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.canvas = tk.Canvas(video_frame, bg='black', cursor='crosshair')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_canvas_release)
        self.canvas.bind('<Button-3>', self.on_canvas_right_click)
        self.canvas.bind('<B3-Motion>', self.on_canvas_pan)
        self.canvas.bind('<ButtonRelease-3>', self.on_canvas_pan_release)
        
        # Gallery panel
        gallery_frame = ttk.Frame(main_frame, width=450)
        gallery_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        gallery_frame.pack_propagate(False)
        
        # Detection controls
        detect_frame = ttk.LabelFrame(gallery_frame, text="Detection", padding=5)
        detect_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(detect_frame, text="🔍 YOLO Detect", command=self.on_yolo_detect).pack(fill=tk.X, pady=2)
        ttk.Button(detect_frame, text="Clear Detections", command=self.clear_detections).pack(fill=tk.X, pady=2)
        
        # Player selection dropdown
        player_frame = ttk.LabelFrame(gallery_frame, text="Select Player", padding=5)
        player_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(player_frame, text="Existing Player:").pack(anchor=tk.W)
        self.player_dropdown = ttk.Combobox(player_frame, width=25, state="readonly")
        self.player_dropdown.pack(fill=tk.X, pady=2)
        self.player_dropdown.bind("<<ComboboxSelected>>", self.on_player_selected)
        self.update_player_dropdown()
        
        ttk.Label(player_frame, text="OR New Player:").pack(anchor=tk.W, pady=(5, 0))
        
        # Player name input
        ttk.Label(player_frame, text="Player Name:").pack(anchor=tk.W, pady=(5, 0))
        self.name_entry = ttk.Entry(player_frame, width=25)
        self.name_entry.pack(fill=tk.X, pady=2)
        self.name_entry.bind('<KeyRelease>', self.on_name_changed)
        
        ttk.Label(player_frame, text="Jersey Number:").pack(anchor=tk.W, pady=(5, 0))
        self.jersey_entry = ttk.Entry(player_frame, width=25)
        self.jersey_entry.pack(fill=tk.X, pady=2)
        
        ttk.Label(player_frame, text="Team:").pack(anchor=tk.W, pady=(5, 0))
        self.team_entry = ttk.Entry(player_frame, width=25)
        self.team_entry.pack(fill=tk.X, pady=2)
        
        # Visualization settings
        viz_frame = ttk.LabelFrame(gallery_frame, text="Visualization", padding=5)
        viz_frame.pack(fill=tk.X, pady=5)
        
        if COLOR_PICKER_AVAILABLE:
            self.viz_color_var = tk.StringVar()
            color_picker_frame, _ = create_color_picker_widget(
                viz_frame, self.viz_color_var, label_text="Custom Color:",
                initial_color=None, on_change_callback=None
            )
            color_picker_frame.pack(fill=tk.X, pady=2)
        
        self.viz_box_thickness = tk.IntVar(value=2)
        thickness_frame = ttk.Frame(viz_frame)
        thickness_frame.pack(fill=tk.X, pady=2)
        ttk.Label(thickness_frame, text="Box Thickness:").pack(side=tk.LEFT)
        ttk.Spinbox(thickness_frame, from_=1, to=10, textvariable=self.viz_box_thickness, width=8).pack(side=tk.LEFT, padx=5)
        
        # Add/Update buttons
        button_frame = ttk.Frame(gallery_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        self.add_button = ttk.Button(button_frame, text="Add to Gallery", command=self.add_player_to_gallery, state=tk.DISABLED)
        self.add_button.pack(fill=tk.X, pady=2)
        
        self.update_button = ttk.Button(button_frame, text="Update Player", command=self.update_player_name, state=tk.DISABLED)
        self.update_button.pack(fill=tk.X, pady=2)
        
        # Gallery list
        list_frame = ttk.LabelFrame(gallery_frame, text="Player Gallery", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.gallery_listbox = tk.Listbox(list_frame, height=12)
        self.gallery_listbox.pack(fill=tk.BOTH, expand=True)
        self.gallery_listbox.bind('<<ListboxSelect>>', self.on_gallery_player_select)
        self.gallery_listbox.bind('<Double-Button-1>', self.on_gallery_player_double_click)
        
        # Navigation and Playback Controls
        nav_frame = ttk.LabelFrame(gallery_frame, text="Navigation & Playback", padding=5)
        nav_frame.pack(fill=tk.X, pady=5)
        
        # Playback controls
        playback_buttons = ttk.Frame(nav_frame)
        playback_buttons.pack(fill=tk.X, pady=2)
        
        self.play_button = ttk.Button(playback_buttons, text="▶ Play", command=self.toggle_play, width=8)
        self.play_button.pack(side=tk.LEFT, padx=2)
        self.is_playing = False
        self.play_after_id = None
        self.playback_speed = 1.0
        
        ttk.Button(playback_buttons, text="⏮ First", command=self.first_frame, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_buttons, text="◄◄", command=self.prev_frame, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_buttons, text="►►", command=self.next_frame, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_buttons, text="Last ⏭", command=self.last_frame, width=8).pack(side=tk.LEFT, padx=2)
        
        # Frame slider
        frame_slider_frame = ttk.Frame(nav_frame)
        frame_slider_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(frame_slider_frame, text="Frame:").pack(side=tk.LEFT, padx=2)
        self.frame_var = tk.IntVar(value=0)
        self.frame_slider = ttk.Scale(frame_slider_frame, from_=0, to=100, 
                                     orient=tk.HORIZONTAL, variable=self.frame_var,
                                     command=self.on_slider_change, length=200)
        self.frame_slider.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.frame_label = ttk.Label(frame_slider_frame, text="Frame: 0 / 0", width=15)
        self.frame_label.pack(side=tk.LEFT, padx=2)
        
        # Goto frame entry
        goto_frame = ttk.Frame(nav_frame)
        goto_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(goto_frame, text="Goto:").pack(side=tk.LEFT, padx=2)
        self.goto_frame_var = tk.StringVar()
        goto_entry = ttk.Entry(goto_frame, textvariable=self.goto_frame_var, width=8)
        goto_entry.pack(side=tk.LEFT, padx=2)
        goto_entry.bind("<Return>", lambda e: self.goto_frame())
        ttk.Button(goto_frame, text="Go", command=self.goto_frame, width=4).pack(side=tk.LEFT, padx=2)
        
        # Speed control
        speed_frame = ttk.Frame(nav_frame)
        speed_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(speed_frame, text="Speed:").pack(side=tk.LEFT, padx=2)
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_spin = ttk.Spinbox(speed_frame, from_=0.25, to=4.0, increment=0.25,
                                 textvariable=self.speed_var, width=8)
        speed_spin.pack(side=tk.LEFT, padx=2)
        self.speed_var.trace_add('write', lambda *args: self.update_speed())
        
        # Selection info
        self.selection_label = ttk.Label(gallery_frame, text="No player selected", foreground="gray")
        self.selection_label.pack(fill=tk.X, pady=5)
        
        # Status
        self.status_label = ttk.Label(gallery_frame, text="Ready - Draw box around player or use YOLO Detect")
        self.status_label.pack(fill=tk.X, pady=5)
        
        # Update gallery list
        self.update_gallery_list()
    
    def display_frame(self, frame: np.ndarray, frame_num: int):
        """Display a frame with detections and matches"""
        if frame is None:
            return
        
        display_frame = frame.copy()
        
        # Draw detected players
        for bbox in self.detected_players:
            x1, y1, x2, y2 = map(int, bbox)
            
            # Check if matched
            if bbox in self.detected_player_matches:
                player_id, player_name, confidence = self.detected_player_matches[bbox]
                if player_name:
                    # Draw with matched color
                    color = (0, 255, 0)  # Green for matched
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(display_frame, f"{player_name} ({confidence:.2f})", 
                              (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                else:
                    # Unmatched
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
            else:
                # No match yet
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
            
            # Highlight selected
            if self.selected_bbox == bbox:
                cv2.rectangle(display_frame, (x1-3, y1-3), (x2+3, y2+3), (0, 255, 255), 3)
        
        # Draw box being drawn
        if self.drawing_box and self.box_start and self.box_end:
            x1, y1 = map(int, self.box_start)
            x2, y2 = map(int, self.box_end)
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
        
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
        
        # Calculate scale
        scale = min(canvas_width / frame.shape[1], canvas_height / frame.shape[0])
        new_width = int(frame.shape[1] * scale)
        new_height = int(frame.shape[0] * scale)
        
        self.scale_factor = scale
        
        # Resize
        resized = cv2.resize(frame, (new_width, new_height))
        
        # Convert to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Convert to PhotoImage
        img = Image.fromarray(rgb)
        photo = ImageTk.PhotoImage(image=img)
        
        # Display with pan offset
        self.canvas.delete("all")
        img_x = canvas_width // 2 + self.pan_x
        img_y = canvas_height // 2 + self.pan_y
        self.canvas.create_image(img_x, img_y, image=photo, anchor=tk.CENTER)
        self.canvas.image = photo  # Keep reference
    
    def on_canvas_click(self, event):
        """Handle canvas click - start drawing box"""
        self.box_start = (event.x, event.y)
        self.drawing_box = True
        self.selected_bbox = None
    
    def on_canvas_drag(self, event):
        """Handle canvas drag - update box"""
        if self.drawing_box:
            self.box_end = (event.x, event.y)
            self.update_display()
    
    def on_canvas_release(self, event):
        """Handle canvas release - finish box"""
        if self.drawing_box:
            self.box_end = (event.x, event.y)
            self.drawing_box = False
            
            # Convert canvas coordinates to frame coordinates
            if self.box_start and self.box_end:
                x1 = min(self.box_start[0], self.box_end[0])
                y1 = min(self.box_start[1], self.box_end[1])
                x2 = max(self.box_start[0], self.box_end[0])
                y2 = max(self.box_start[1], self.box_end[1])
                
                # Convert to frame coordinates
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
                img_x = canvas_width // 2 + self.pan_x
                img_y = canvas_height // 2 + self.pan_y
                
                frame_x1 = (x1 - img_x + self.video_manager.width // 2) / self.scale_factor
                frame_y1 = (y1 - img_y + self.video_manager.height // 2) / self.scale_factor
                frame_x2 = (x2 - img_x + self.video_manager.width // 2) / self.scale_factor
                frame_y2 = (y2 - img_y + self.video_manager.height // 2) / self.scale_factor
                
                bbox = (int(frame_x1), int(frame_y1), int(frame_x2), int(frame_y2))
                
                # Check if clicking on existing detection
                clicked_bbox = self.find_bbox_at_position(x1, y1)
                if clicked_bbox:
                    self.selected_bbox = clicked_bbox
                    self.on_bbox_selected(clicked_bbox)
                else:
                    # New box
                    if (frame_x2 - frame_x1) > 20 and (frame_y2 - frame_y1) > 20:
                        self.detected_players.append(bbox)
                        self.selected_bbox = bbox
                        self.on_bbox_selected(bbox)
                
                self.box_start = None
                self.box_end = None
                self.update_display()
    
    def on_canvas_right_click(self, event):
        """Start panning"""
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
    
    def on_canvas_pan(self, event):
        """Pan canvas"""
        if self.is_panning:
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.pan_x += dx
            self.pan_y += dy
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.update_display()
    
    def on_canvas_pan_release(self, event):
        """Stop panning"""
        self.is_panning = False
    
    def find_bbox_at_position(self, x, y):
        """Find bbox at canvas position"""
        for bbox in self.detected_players:
            x1, y1, x2, y2 = bbox
            
            # Convert to canvas coordinates
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            img_x = canvas_width // 2 + self.pan_x
            img_y = canvas_height // 2 + self.pan_y
            
            canvas_x1 = (x1 * self.scale_factor) + img_x - (self.video_manager.width // 2) * self.scale_factor
            canvas_y1 = (y1 * self.scale_factor) + img_y - (self.video_manager.height // 2) * self.scale_factor
            canvas_x2 = (x2 * self.scale_factor) + img_x - (self.video_manager.width // 2) * self.scale_factor
            canvas_y2 = (y2 * self.scale_factor) + img_y - (self.video_manager.height // 2) * self.scale_factor
            
            if canvas_x1 <= x <= canvas_x2 and canvas_y1 <= y <= canvas_y2:
                return bbox
        return None
    
    def on_bbox_selected(self, bbox):
        """Handle bbox selection"""
        # Check if matched
        if bbox in self.detected_player_matches:
            player_id, player_name, confidence = self.detected_player_matches[bbox]
            if player_name:
                self.player_dropdown.set(player_name)
                self.name_entry.delete(0, tk.END)
                self.name_entry.insert(0, player_name)
                self.selection_label.config(text=f"Selected: {player_name} (confidence: {confidence:.2f})")
            else:
                self.selection_label.config(text="Selected: Unmatched detection")
        else:
            self.selection_label.config(text="Selected: New detection (not matched)")
        
        self.update_add_button_state()
        self.update_display()
    
    def on_yolo_detect(self):
        """Run YOLO detection on current frame"""
        if not self.video_manager.cap:
            messagebox.showwarning("Warning", "Please load a video first")
            return
        
        if not YOLO_AVAILABLE:
            messagebox.showerror("Error", "YOLO not available. Install with: pip install ultralytics")
            return
        
        # Initialize YOLO if needed
        if self.yolo_model is None:
            try:
                model_paths = ['yolo11n.pt', 'yolo11s.pt', 'yolov8n.pt', 'yolov8s.pt']
                for model_path in model_paths:
                    try:
                        self.yolo_model = YOLO(model_path)
                        print(f"✓ Loaded YOLO model: {model_path}")
                        break
                    except:
                        continue
                
                if self.yolo_model is None:
                    messagebox.showerror("Error", "Could not load YOLO model")
                    return
            except ImportError:
                messagebox.showerror("Error", "YOLO not available")
                return
        
        # Get current frame
        frame = self.video_manager.get_frame(self.viewer.current_frame_num)
        if frame is None:
            return
        
        self.status_label.config(text="Detecting players...")
        self.viewer.root.update()
        
        # Run detection
        results = self.yolo_model(frame, conf=0.25, classes=[0])  # class 0 = person
        
        # Extract detections
        self.detected_players = []
        if results and len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    bbox = (int(x1), int(y1), int(x2), int(y2))
                    
                    # Filter small detections (likely balls)
                    bbox_width = x2 - x1
                    bbox_height = y2 - y1
                    if bbox_width * bbox_height < 3000 or bbox_height < 80:
                        continue
                    
                    self.detected_players.append(bbox)
                    
                    # Try to match with gallery
                    if self.reid_manager.is_initialized() and self.gallery_manager.is_initialized():
                        # Extract features
                        try:
                            if SUPERVISION_AVAILABLE and self.reid_manager.is_initialized():
                                xyxy = np.array([[x1, y1, x2, y2]], dtype=np.float32)
                                detections = sv.Detections(xyxy=xyxy)
                                # Use reid_manager's extract_features method
                                self.reid_manager.extract_features(frame, detections, self.viewer.current_frame_num)
                                # Get features from manager (use first track_id from detections)
                                temp_track_id = detections.tracker_id[0] if len(detections.tracker_id) > 0 else 0
                                feature_vector = self.reid_manager.get_features(self.viewer.current_frame_num, temp_track_id)
                                
                                if feature_vector is not None:
                                    # Match to gallery
                                    match_result = self.gallery_manager.match_player(features=feature_vector)
                                    if match_result:
                                        player_name, confidence, _ = match_result
                                        if confidence >= 0.5:
                                            # Find player ID
                                            player_id = None
                                            player_names = self.gallery_manager.get_player_names()
                                            for name in player_names:
                                                if name.lower() == player_name.lower():
                                                    player_id = name
                                                    break
                                            
                                            self.detected_player_matches[bbox] = (player_id, player_name, confidence)
                        except Exception as e:
                            print(f"Warning: Could not match detection: {e}")
        
        self.status_label.config(text=f"Detected {len(self.detected_players)} players")
        self.update_display()
    
    def clear_detections(self):
        """Clear all detections"""
        self.detected_players = []
        self.detected_player_matches = {}
        self.selected_bbox = None
        self.update_display()
        self.selection_label.config(text="No player selected")
    
    def on_player_selected(self, event):
        """Handle player selection from dropdown"""
        selected = self.player_dropdown.get()
        if selected == "-- New Player --":
            self.name_entry.delete(0, tk.END)
            self.jersey_entry.delete(0, tk.END)
            self.team_entry.delete(0, tk.END)
        else:
            # Load player data
            player = self.gallery_manager.get_player(selected)
            if player:
                self.name_entry.delete(0, tk.END)
                self.name_entry.insert(0, player.get('name', selected))
                # Load other fields if available
                # (gallery_manager.get_player returns dict or profile object)
    
    def on_name_changed(self, event):
        """Handle name entry change"""
        self.update_add_button_state()
    
    def update_add_button_state(self):
        """Update add button state based on selection"""
        has_name = len(self.name_entry.get().strip()) > 0
        has_selection = self.selected_bbox is not None
        
        if has_name and has_selection:
            self.add_button.config(state=tk.NORMAL)
            self.update_button.config(state=tk.NORMAL)
        else:
            self.add_button.config(state=tk.DISABLED)
            self.update_button.config(state=tk.DISABLED)
    
    def add_player_to_gallery(self):
        """Add selected player to gallery"""
        if not self.selected_bbox:
            messagebox.showwarning("Warning", "Please select a detection first")
            return
        
        player_name = self.name_entry.get().strip()
        if not player_name:
            messagebox.showwarning("Warning", "Please enter a player name")
            return
        
        # Get current frame
        frame = self.video_manager.get_frame(self.viewer.current_frame_num)
        if frame is None:
            return
        
        # Extract features from selected bbox
        x1, y1, x2, y2 = self.selected_bbox
        
        try:
            if self.reid_manager.is_initialized() and SUPERVISION_AVAILABLE:
                # Extract Re-ID features
                xyxy = np.array([[x1, y1, x2, y2]], dtype=np.float32)
                detections = sv.Detections(xyxy=xyxy)
                
                # Use reid_manager's extract_features method
                self.reid_manager.extract_features(frame, detections, self.viewer.current_frame_num)
                
                # Get features from manager (use first track_id from detections)
                temp_track_id = detections.tracker_id[0] if len(detections.tracker_id) > 0 else 99999
                feature_vector = self.reid_manager.get_features(self.viewer.current_frame_num, temp_track_id)
                
                # Get foot features if available
                foot_features = None
                foot_features_result = self.reid_manager.get_foot_features(self.viewer.current_frame_num, temp_track_id)
                if foot_features_result is not None:
                    foot_features = foot_features_result
                
                if feature_vector is not None:
                    
                    # Get jersey and team
                    jersey_number = self.jersey_entry.get().strip()
                    team = self.team_entry.get().strip()
                    
                    # Add to gallery
                    self.gallery_manager.add_player(
                        player_name,
                        features=feature_vector,
                        foot_features=foot_features,
                        team=team if team else None,
                        jersey_number=jersey_number if jersey_number else None
                    )
                    
                    # Save gallery
                    self.gallery_manager.save_gallery()
                    
                    # Update UI
                    self.update_gallery_list()
                    self.update_player_dropdown()
                    self.status_label.config(text=f"✓ Added {player_name} to gallery")
                    
                    # Match this detection
                    self.detected_player_matches[self.selected_bbox] = (player_name, player_name, 1.0)
                    self.update_display()
                else:
                    messagebox.showerror("Error", "Could not extract features from selection")
            else:
                messagebox.showerror("Error", "Re-ID tracker not initialized")
        except Exception as e:
            messagebox.showerror("Error", f"Could not add player: {e}")
            import traceback
            traceback.print_exc()
    
    def update_player_name(self):
        """Update name for selected detection"""
        if not self.selected_bbox:
            return
        
        player_name = self.name_entry.get().strip()
        if not player_name:
            return
        
        # Update match
        self.detected_player_matches[self.selected_bbox] = (player_name, player_name, 1.0)
        self.update_display()
        self.status_label.config(text=f"✓ Updated to {player_name}")
    
    def update_gallery_list(self):
        """Update gallery listbox"""
        self.gallery_listbox.delete(0, tk.END)
        
        if self.gallery_manager.is_initialized():
            player_names = self.gallery_manager.get_player_names()
            for name in sorted(player_names):
                self.gallery_listbox.insert(tk.END, name)
    
    def update_player_dropdown(self):
        """Update player dropdown"""
        if not self.gallery_manager.is_initialized():
            return
        
        player_names = self.gallery_manager.get_player_names()
        self.player_dropdown['values'] = ["-- New Player --"] + sorted(player_names)
        self.player_dropdown.current(0)
    
    def on_gallery_player_select(self, event):
        """Handle gallery player selection"""
        selection = self.gallery_listbox.curselection()
        if selection:
            player_name = self.gallery_listbox.get(selection[0])
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, player_name)
    
    def on_gallery_player_double_click(self, event):
        """Handle gallery player double-click"""
        selection = self.gallery_listbox.curselection()
        if selection:
            player_name = self.gallery_listbox.get(selection[0])
            # Load player data
            player = self.gallery_manager.get_player(player_name)
            if player:
                self.name_entry.delete(0, tk.END)
                self.name_entry.insert(0, player_name)
                # Could show player details in a dialog here
    
    def update_display(self):
        """Update display with current frame"""
        frame = self.video_manager.get_frame(self.viewer.current_frame_num)
        if frame is not None:
            self.display_frame(frame, self.viewer.current_frame_num)
    
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
        """Go to a specific frame"""
        if frame_num is None:
            if self.frame_var is not None:
                try:
                    frame_num = self.frame_var.get()
                except:
                    frame_num = self.viewer.current_frame_num
            elif self.goto_frame_var is not None:
                try:
                    frame_num = int(self.goto_frame_var.get())
                except (ValueError, TypeError):
                    frame_num = self.viewer.current_frame_num
            else:
                frame_num = self.viewer.current_frame_num
        
        frame_num = max(0, min(frame_num, self.video_manager.total_frames - 1))
        if self.frame_var is not None:
            self.frame_var.set(frame_num)
        
        # Update frame label
        if self.frame_label is not None:
            total_frames = self.video_manager.total_frames - 1 if self.video_manager.total_frames > 0 else 0
            self.frame_label.config(text=f"Frame: {frame_num} / {total_frames}")
        
        self.viewer.load_frame(frame_num)
    
    def on_slider_change(self, value):
        """Handle frame slider change"""
        try:
            frame_num = int(float(value))
            total_frames = self.video_manager.total_frames - 1 if self.video_manager.total_frames > 0 else 0
            if self.frame_var.get() != frame_num:
                self.frame_var.set(frame_num)
                self.frame_label.config(text=f"Frame: {frame_num} / {total_frames}")
                self.goto_frame(frame_num)
        except Exception:
            pass
    
    def toggle_play(self):
        """Toggle play/pause"""
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
        delay = int(1000 / (self.video_manager.fps * self.playback_speed))
        self.play_after_id = self.viewer.root.after(delay, self.play)
    
    def update_speed(self):
        """Update playback speed"""
        try:
            self.playback_speed = self.speed_var.get()
        except:
            self.playback_speed = 1.0
    
    def on_video_loaded(self):
        """Called when video is loaded - preserve current frame position"""
        if self.video_manager.total_frames > 0:
            # Update frame slider range
            if self.frame_slider is not None:
                self.frame_slider.config(to=max(100, self.video_manager.total_frames - 1))
            
            # Preserve current frame position (don't reset to 0 if video was already loaded)
            current_frame = self.viewer.current_frame_num
            if current_frame >= self.video_manager.total_frames:
                current_frame = 0
            
            if self.frame_var is not None:
                self.frame_var.set(current_frame)
            
            if self.frame_label is not None:
                total_frames = self.video_manager.total_frames - 1
                self.frame_label.config(text=f"Frame: {current_frame} / {total_frames}")
            
            # Load current frame (preserves position)
            self.goto_frame(current_frame)
            self.status_label.config(text=f"Video loaded: {self.video_manager.total_frames} frames")
    
    def on_csv_loaded(self):
        pass
    
    def cleanup(self):
        # Stop playback if running
        if self.is_playing:
            self.is_playing = False
            if self.play_after_id:
                self.viewer.root.after_cancel(self.play_after_id)
                self.play_after_id = None
        
        # Save gallery
        if self.gallery_manager.is_initialized():
            self.gallery_manager.save_gallery()
