"""
Setup Mode - Interactive player tagging for initial analysis
Migrated from SetupWizard with full features
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
import json
import sys
from pathlib import Path
from ..unified_viewer import BaseMode

# Try to import jersey OCR
try:
    current_file = Path(__file__).resolve()
    parent_dir = current_file.parent.parent.parent.parent
    jersey_path = os.path.join(parent_dir, 'jersey_number_ocr.py')
    if os.path.exists(jersey_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("jersey_number_ocr", jersey_path)
        jersey_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(jersey_module)
        JerseyNumberOCR = jersey_module.JerseyNumberOCR
        JERSEY_OCR_AVAILABLE = True
    else:
        from jersey_number_ocr import JerseyNumberOCR
        JERSEY_OCR_AVAILABLE = True
except ImportError:
    JERSEY_OCR_AVAILABLE = False
    JerseyNumberOCR = None


class SetupMode(BaseMode):
    """Setup Wizard mode - for tagging players before analysis"""
    
    def __init__(self, parent_frame, viewer, video_manager, detection_manager, 
                 reid_manager, gallery_manager, csv_manager, anchor_manager):
        # Initialize base
        super().__init__(parent_frame, viewer, video_manager, detection_manager,
                        reid_manager, gallery_manager, csv_manager, anchor_manager)
        
        # State
        self.selected_detection = None
        self.current_frame = None
        self.player_name_list = []
        self.team_colors = None
        self.jersey_ocr = None
        
        # Player tag protection
        self.player_tag_protection = {}  # player_name -> (frame_num, track_id)
        self.tag_protection_frames = 2
        
        # Load player names and team colors
        self.load_player_name_list()
        self.load_team_colors()
        
        # Initialize jersey OCR
        if JERSEY_OCR_AVAILABLE:
            try:
                self.jersey_ocr = JerseyNumberOCR(ocr_backend="auto", confidence_threshold=0.5, preprocess=True)
            except:
                pass
    
    def create_ui(self):
        """Create setup mode UI"""
        # Main layout: video on left, controls on right
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Video canvas with scrollbars
        video_container = ttk.Frame(main_frame)
        video_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.canvas = tk.Canvas(video_container, bg='black', cursor='crosshair')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<Motion>', self.on_canvas_motion)
        
        # Controls panel
        controls_frame = ttk.Frame(main_frame, width=450)
        controls_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        controls_frame.pack_propagate(False)
        
        # Navigation controls
        nav_frame = ttk.LabelFrame(controls_frame, text="Navigation", padding=5)
        nav_frame.pack(fill=tk.X, pady=5)
        
        nav_buttons = ttk.Frame(nav_frame)
        nav_buttons.pack(fill=tk.X)
        ttk.Button(nav_buttons, text="◄◄ First", command=self.first_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_buttons, text="◄ Prev", command=self.prev_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_buttons, text="Next ►", command=self.next_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_buttons, text="Last ►►", command=self.last_frame).pack(side=tk.LEFT, padx=2)
        
        # Frame number
        frame_frame = ttk.Frame(nav_frame)
        frame_frame.pack(fill=tk.X, pady=5)
        ttk.Label(frame_frame, text="Frame:").pack(side=tk.LEFT)
        self.frame_var = tk.IntVar(value=0)
        frame_spin = ttk.Spinbox(frame_frame, from_=0, to=999999, textvariable=self.frame_var, width=10)
        frame_spin.pack(side=tk.LEFT, padx=5)
        frame_spin.bind('<Return>', lambda e: self.goto_frame())
        frame_spin.bind('<FocusOut>', lambda e: self.goto_frame())
        
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
        self.player_name_combo = ttk.Combobox(tag_frame, textvariable=self.player_name_var, width=25)
        self.player_name_combo.pack(fill=tk.X, pady=2)
        self.player_name_combo['values'] = self.player_name_list
        self.player_name_combo.bind('<Return>', lambda e: self.tag_player())
        
        ttk.Label(tag_frame, text="Team:").pack(anchor=tk.W, pady=(5, 0))
        self.team_var = tk.StringVar()
        team_names = self.get_team_names()
        self.team_combo = ttk.Combobox(tag_frame, textvariable=self.team_var, width=25, values=team_names)
        self.team_combo.pack(fill=tk.X, pady=2)
        
        ttk.Label(tag_frame, text="Jersey Number:").pack(anchor=tk.W, pady=(5, 0))
        self.jersey_number_var = tk.StringVar()
        jersey_entry = ttk.Entry(tag_frame, textvariable=self.jersey_number_var, width=25)
        jersey_entry.pack(fill=tk.X, pady=2)
        jersey_entry.bind('<Return>', lambda e: self.tag_player())
        
        ttk.Button(tag_frame, text="Tag Selected Player", command=self.tag_player).pack(fill=tk.X, pady=5)
        ttk.Button(tag_frame, text="Clear Tag", command=self.clear_tag).pack(fill=tk.X, pady=2)
        
        # Detections list
        detections_frame = ttk.LabelFrame(controls_frame, text="Detections", padding=5)
        detections_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollbar for listbox
        listbox_frame = ttk.Frame(detections_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.detections_listbox = tk.Listbox(listbox_frame, height=12, yscrollcommand=scrollbar.set)
        self.detections_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.detections_listbox.yview)
        self.detections_listbox.bind('<<ListboxSelect>>', self.on_detection_select)
        self.detections_listbox.bind('<Double-Button-1>', lambda e: self.tag_player())
        
        # Summary
        summary_frame = ttk.LabelFrame(controls_frame, text="Summary", padding=5)
        summary_frame.pack(fill=tk.X, pady=5)
        
        self.summary_label = ttk.Label(summary_frame, text="No tags yet", wraplength=400)
        self.summary_label.pack(fill=tk.X)
        
        # Status
        self.status_label = ttk.Label(controls_frame, text="Ready - Load video and initialize detection")
        self.status_label.pack(fill=tk.X, pady=5)
        
        # Save button
        save_frame = ttk.Frame(controls_frame)
        save_frame.pack(fill=tk.X, pady=5)
        ttk.Button(save_frame, text="Save Tags", command=self.save_tags).pack(fill=tk.X, pady=2)
    
    def display_frame(self, frame: np.ndarray, frame_num: int):
        """Display a frame with detections"""
        if frame is None:
            return
        
        self.current_frame = frame.copy()
        
        # Get detections for this frame
        detections = self.detection_manager.get_detections(frame_num)
        
        # Draw frame
        display_frame = frame.copy()
        
        if detections is not None and len(detections) > 0:
            # Extract Re-ID features if available
            if self.reid_manager.is_initialized():
                self.reid_manager.extract_features(display_frame, detections, frame_num)
            
            # Match to gallery
            if self.gallery_manager.is_initialized():
                self.match_detections_to_gallery(display_frame, detections, frame_num)
            
            # Draw detections
            for i, (xyxy, track_id, conf) in enumerate(zip(
                detections.xyxy,
                detections.tracker_id,
                detections.confidence
            )):
                if track_id is None:
                    continue
                
                x1, y1, x2, y2 = map(int, xyxy)
                
                # Get color
                color = self.get_detection_color(track_id)
                
                # Highlight selected
                if self.selected_detection == i:
                    cv2.rectangle(display_frame, (x1-3, y1-3), (x2+3, y2+3), (0, 255, 255), 3)
                
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                
                # Add label if mapped
                tid_str = str(int(track_id))
                mappings = self.viewer.get_approved_mappings()
                if tid_str in mappings:
                    player_name, team, jersey = mappings[tid_str]
                    label = f"{player_name}"
                    if jersey:
                        label += f" #{jersey}"
                    cv2.putText(display_frame, label, (x1, y1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                else:
                    # Show gallery suggestion if available
                    if hasattr(self, 'gallery_suggestions') and track_id in self.gallery_suggestions:
                        suggested_name, confidence = self.gallery_suggestions[track_id]
                        if confidence >= 0.6:
                            label = f"#{track_id} → {suggested_name}?"
                            cv2.putText(display_frame, label, (x1, y1 - 10),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
                    else:
                        cv2.putText(display_frame, f"#{track_id}", (x1, y1 - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        # Convert to PhotoImage and display
        self._display_image(display_frame)
        
        # Update detections list
        self.update_detections_list(detections)
        self.update_summary()
    
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
        
        # Store scale for click detection
        self.display_scale = scale
        self.display_offset_x = (canvas_width - new_width) // 2
        self.display_offset_y = (canvas_height - new_height) // 2
    
    def on_canvas_click(self, event):
        """Handle canvas click to select detection"""
        if not self.current_frame is None:
            # Convert canvas coordinates to frame coordinates
            canvas_x = event.x
            canvas_y = event.y
            
            # Adjust for display offset
            frame_x = (canvas_x - self.display_offset_x) / self.display_scale
            frame_y = (canvas_y - self.display_offset_y) / self.display_scale
            
            # Find detection at this position
            detections = self.detection_manager.get_detections(self.viewer.current_frame_num)
            if detections is not None and len(detections) > 0:
                best_match = None
                best_distance = float('inf')
                
                for i, (xyxy, track_id, conf) in enumerate(zip(
                    detections.xyxy,
                    detections.tracker_id,
                    detections.confidence
                )):
                    if track_id is None:
                        continue
                    
                    x1, y1, x2, y2 = map(float, xyxy)
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    
                    # Check if click is inside bbox
                    if x1 <= frame_x <= x2 and y1 <= frame_y <= y2:
                        distance = ((frame_x - center_x)**2 + (frame_y - center_y)**2)**0.5
                        if distance < best_distance:
                            best_distance = distance
                            best_match = i
                
                if best_match is not None:
                    self.selected_detection = best_match
                    self.on_detection_select(None)
                    self.update_display()
    
    def on_canvas_motion(self, event):
        """Handle canvas mouse motion"""
        pass
    
    def initialize_detection(self):
        """Initialize YOLO detection"""
        if not self.video_manager.cap:
            messagebox.showerror("Error", "Please load a video first")
            return
        
        self.status_label.config(text="Initializing detection...")
        self.init_button.config(state=tk.DISABLED)
        self.viewer.root.update()
        
        if self.detection_manager.initialize():
            # Process first few frames
            frames_to_process = min(30, self.video_manager.total_frames)
            for i in range(frames_to_process):
                frame = self.video_manager.get_frame(i)
                if frame is not None:
                    self.detection_manager.detect_frame(frame, i)
                    if i % 5 == 0:
                        self.status_label.config(text=f"Processing frame {i}/{frames_to_process}...")
                        self.viewer.root.update()
            
            self.status_label.config(text="Detection initialized - Ready for tagging")
            self.load_frame(0)
        else:
            messagebox.showerror("Error", "Failed to initialize detection")
            self.status_label.config(text="Error initializing detection")
        
        self.init_button.config(state=tk.NORMAL)
    
    def match_detections_to_gallery(self, frame, detections, frame_num):
        """Match detections to gallery players"""
        if not self.gallery_manager.is_initialized() or not self.reid_manager.is_initialized():
            return
        
        if not hasattr(self, 'gallery_suggestions'):
            self.gallery_suggestions = {}
        
        # Get Re-ID features for this frame
        frame_features = self.reid_manager.frame_reid_features.get(frame_num, {})
        if not frame_features:
            return
        
        # Match each untagged detection
        for i, track_id in enumerate(detections.tracker_id):
            if track_id is None:
                continue
            
            tid_str = str(int(track_id))
            mappings = self.viewer.get_approved_mappings()
            
            # Skip if already tagged
            if tid_str in mappings:
                continue
            
            # Get features
            if track_id not in frame_features:
                continue
            
            features = frame_features[track_id]
            if features is None:
                continue
            
            # Get foot features if available
            foot_features = None
            frame_foot_features = self.reid_manager.frame_foot_features.get(frame_num, {})
            if track_id in frame_foot_features:
                foot_features = frame_foot_features[track_id]
            
            # Try jersey OCR
            detected_jersey = None
            if self.jersey_ocr is not None and i < len(detections.xyxy):
                try:
                    bbox = detections.xyxy[i]
                    x1, y1, x2, y2 = map(int, bbox)
                    jersey_y1 = int(y1)
                    jersey_y2 = int(y1 + (y2 - y1) * 0.40)
                    jersey_bbox = [x1, jersey_y1, x2, jersey_y2]
                    ocr_result = self.jersey_ocr.detect_jersey_number(frame, jersey_bbox)
                    if ocr_result and ocr_result.get('jersey_number'):
                        detected_jersey = str(ocr_result['jersey_number'])
                except:
                    pass
            
            # Match to gallery
            match_result = self.gallery_manager.match_player(
                features=features,
                foot_features=foot_features,
                detected_jersey=detected_jersey
            )
            
            if match_result:
                player_name, confidence, _ = match_result
                if confidence >= 0.6:  # Suggestion threshold
                    self.gallery_suggestions[track_id] = (player_name, confidence)
    
    def tag_player(self):
        """Tag selected detection with player name"""
        if self.selected_detection is None:
            messagebox.showwarning("Warning", "Please select a detection first (click on a player)")
            return
        
        detections = self.detection_manager.get_detections(self.viewer.current_frame_num)
        if detections is None or self.selected_detection >= len(detections.tracker_id):
            messagebox.showwarning("Warning", "Selected detection is no longer valid")
            self.selected_detection = None
            return
        
        track_id = detections.tracker_id[self.selected_detection]
        if track_id is None:
            return
        
        pid_str = str(int(track_id))
        
        player_name = self.player_name_var.get().strip()
        if not player_name:
            messagebox.showwarning("Warning", "Please enter a player name")
            return
        
        # Add to player name list if new
        if player_name not in self.player_name_list:
            self.player_name_list.append(player_name)
            self.player_name_list.sort()
            self.player_name_combo['values'] = self.player_name_list
            self.save_player_name_list()
        
        team = self.team_var.get().strip()
        jersey_number = self.jersey_number_var.get().strip()
        
        # Auto-detect jersey number if not provided
        if not jersey_number and self.jersey_ocr is not None and self.current_frame is not None:
            try:
                bbox = detections.xyxy[self.selected_detection]
                x1, y1, x2, y2 = map(int, bbox)
                jersey_y1 = int(y1)
                jersey_y2 = int(y1 + (y2 - y1) * 0.40)
                jersey_bbox = [x1, jersey_y1, x2, jersey_y2]
                ocr_result = self.jersey_ocr.detect_jersey_number(self.current_frame, jersey_bbox)
                if ocr_result and ocr_result.get('jersey_number'):
                    detected_jersey = str(ocr_result['jersey_number'])
                    confidence = ocr_result.get('confidence', 0.0)
                    if confidence >= 0.5:
                        jersey_number = detected_jersey
                        self.jersey_number_var.set(jersey_number)
            except:
                pass
        
        # Validate jersey number
        if jersey_number and not jersey_number.isdigit():
            messagebox.showwarning("Warning", "Jersey number must be a number or left blank")
            return
        
        # Store mapping
        self.viewer.approved_mappings[pid_str] = (player_name, team, jersey_number)
        
        # Create anchor frame
        bbox = detections.xyxy[self.selected_detection].tolist()
        self.anchor_manager.add_anchor(
            self.viewer.current_frame_num,
            int(track_id),
            player_name,
            bbox,
            team,
            jersey_number
        )
        
        # Extract and save Re-ID features to gallery
        if self.reid_manager.is_initialized() and self.current_frame is not None:
            try:
                features = self.reid_manager.get_features(self.viewer.current_frame_num, track_id)
                foot_features = self.reid_manager.get_foot_features(self.viewer.current_frame_num, track_id)
                
                if features is not None:
                    self.gallery_manager.add_player(
                        player_name,
                        features=features,
                        foot_features=foot_features,
                        team=team if team else None,
                        jersey_number=jersey_number if jersey_number else None
                    )
            except Exception as e:
                print(f"Warning: Could not save to gallery: {e}")
        
        self.status_label.config(text=f"✓ Tagged Track #{track_id} as {player_name}")
        self.update_display()
        self.update_detections_list(detections)
        self.update_summary()
    
    def clear_tag(self):
        """Clear tag for selected detection"""
        if self.selected_detection is None:
            return
        
        detections = self.detection_manager.get_detections(self.viewer.current_frame_num)
        if detections is None or self.selected_detection >= len(detections.tracker_id):
            return
        
        track_id = detections.tracker_id[self.selected_detection]
        if track_id is None:
            return
        
        pid_str = str(int(track_id))
        
        # Remove from mappings
        if pid_str in self.viewer.approved_mappings:
            del self.viewer.approved_mappings[pid_str]
        
        # Remove anchor frame
        self.anchor_manager.remove_anchor(self.viewer.current_frame_num, int(track_id))
        
        self.update_display()
        self.update_detections_list(detections)
        self.update_summary()
    
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
                player_name, team, jersey = mappings[tid_str]
                label = f"Track #{track_id}: {player_name}"
                if jersey:
                    label += f" #{jersey}"
            else:
                label = f"Track #{track_id}: Untagged"
                # Add gallery suggestion
                if hasattr(self, 'gallery_suggestions') and track_id in self.gallery_suggestions:
                    suggested_name, confidence = self.gallery_suggestions[track_id]
                    label += f" → {suggested_name}? ({confidence:.0%})"
            
            self.detections_listbox.insert(tk.END, label)
            
            # Highlight selected
            if self.selected_detection == i:
                self.detections_listbox.selection_set(i)
                self.detections_listbox.see(i)
    
    def on_detection_select(self, event):
        """Handle detection selection from listbox"""
        selection = self.detections_listbox.curselection()
        if selection:
            self.selected_detection = selection[0]
            
            # Update tagging fields
            detections = self.detection_manager.get_detections(self.viewer.current_frame_num)
            if detections is not None and self.selected_detection < len(detections.tracker_id):
                track_id = detections.tracker_id[self.selected_detection]
                if track_id is not None:
                    tid_str = str(int(track_id))
                    mappings = self.viewer.get_approved_mappings()
                    
                    if tid_str in mappings:
                        player_name, team, jersey = mappings[tid_str]
                        self.player_name_var.set(player_name)
                        self.team_var.set(team)
                        self.jersey_number_var.set(jersey)
                    else:
                        # Clear fields
                        self.player_name_var.set("")
                        self.team_var.set("")
                        self.jersey_number_var.set("")
                        
                        # Show gallery suggestion
                        if hasattr(self, 'gallery_suggestions') and track_id in self.gallery_suggestions:
                            suggested_name, confidence = self.gallery_suggestions[track_id]
                            if confidence >= 0.8:  # Auto-fill if high confidence
                                self.player_name_var.set(suggested_name)
                            else:
                                self.status_label.config(text=f"💡 Gallery suggests: {suggested_name} ({confidence:.0%})")
            
            self.update_display()
    
    def update_summary(self):
        """Update summary label"""
        mappings = self.viewer.get_approved_mappings()
        anchor_count = self.anchor_manager.count_anchors()
        
        summary = f"Tagged: {len(mappings)} players, {anchor_count} anchor frames"
        self.summary_label.config(text=summary)
    
    def save_tags(self):
        """Save tags to seed config file"""
        if not self.video_manager.video_path:
            messagebox.showwarning("Warning", "No video loaded - cannot save tags")
            return
        
        try:
            video_dir = os.path.dirname(os.path.abspath(self.video_manager.video_path))
            video_basename = os.path.splitext(os.path.basename(self.video_manager.video_path))[0]
            seed_file = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
            
            # Prepare additional data
            additional_data = {
                "player_mappings": {k: list(v) for k, v in self.viewer.approved_mappings.items()},
                "video_path": self.video_manager.video_path,
                "current_frame": self.viewer.current_frame_num
            }
            
            if self.anchor_manager.save_to_seed_config(seed_file, additional_data):
                messagebox.showinfo("Success", f"Tags saved to:\n{os.path.basename(seed_file)}")
                self.status_label.config(text=f"✓ Tags saved to {os.path.basename(seed_file)}")
            else:
                messagebox.showerror("Error", "Failed to save tags")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save tags: {e}")
    
    def get_detection_color(self, track_id):
        """Get color for a detection based on track ID"""
        colors = [
            (0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0),
            (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 165, 0)
        ]
        return colors[int(track_id) % len(colors)]
    
    def load_player_name_list(self):
        """Load player names from file"""
        player_names_file = "player_names.json"
        if os.path.exists(player_names_file):
            try:
                with open(player_names_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.player_name_list = list(set(data.values()))
                    elif isinstance(data, list):
                        self.player_name_list = data
                    else:
                        self.player_name_list = []
            except:
                self.player_name_list = []
        else:
            # Try to get from gallery
            if self.gallery_manager.is_initialized():
                self.player_name_list = self.gallery_manager.get_player_names()
            else:
                self.player_name_list = []
    
    def save_player_name_list(self):
        """Save player names to file"""
        try:
            player_names_file = "player_names.json"
            with open(player_names_file, 'w') as f:
                json.dump(self.player_name_list, f, indent=2)
        except:
            pass
    
    def load_team_colors(self):
        """Load team colors"""
        team_colors_file = "team_color_config.json"
        if os.path.exists(team_colors_file):
            try:
                with open(team_colors_file, 'r') as f:
                    self.team_colors = json.load(f)
            except:
                self.team_colors = None
    
    def get_team_names(self):
        """Get team names from team colors config"""
        if self.team_colors:
            teams = []
            if 'team1' in self.team_colors:
                teams.append(self.team_colors['team1'].get('name', 'Team 1'))
            if 'team2' in self.team_colors:
                teams.append(self.team_colors['team2'].get('name', 'Team 2'))
            return teams
        return []
    
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
    
    def load_frame(self, frame_num: int):
        self.viewer.load_frame(frame_num)
    
    def update_display(self):
        """Update display with current frame"""
        frame = self.video_manager.get_frame(self.viewer.current_frame_num)
        if frame is not None:
            self.display_frame(frame, self.viewer.current_frame_num)
    
    def on_video_loaded(self):
        if self.video_manager.total_frames > 0:
            self.frame_var.set(0)
            # Update spinbox range
            spinbox = None
            for widget in self.parent_frame.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Spinbox):
                        child.config(to=self.video_manager.total_frames - 1)
            self.load_frame(0)
            self.status_label.config(text=f"Video loaded: {self.video_manager.total_frames} frames")
    
    def on_csv_loaded(self):
        # Refresh display
        self.load_frame(self.viewer.current_frame_num)
        self.status_label.config(text="CSV loaded - Player assignments applied")
    
    def cleanup(self):
        # Save gallery
        if self.gallery_manager.is_initialized():
            self.gallery_manager.save_gallery()
        # Save player names
        self.save_player_name_list()
