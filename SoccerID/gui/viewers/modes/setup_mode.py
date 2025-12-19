"""
Setup Mode - Interactive player tagging for initial analysis
Migrated from SetupWizard with full features
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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
        # Initialize attributes BEFORE calling super (which calls create_ui)
        # State
        self.selected_detection = None
        self.current_frame = None
        self.player_name_list = []
        self.team_colors = None
        self.jersey_ocr = None
        
        # Player tag protection
        self.player_tag_protection = {}  # player_name -> (frame_num, track_id)
        self.tag_protection_frames = 2
        
        # Ball verification
        self.ball_positions = []  # List of (frame_num, x, y) tuples
        self.ball_click_mode = False
        
        # Manual detection drawing
        self.drawing_box = False
        self.box_start = None
        self.box_end = None
        self.manual_detections = []  # List of manually drawn boxes
        
        # Player roster
        self.player_roster = {}  # player_name -> {active: bool, team: str, ...}
        self.roster_manager = None
        
        # Undo/Redo system
        self.undo_stack = []  # List of (action_type, action_data) tuples
        self.redo_stack = []
        self.max_undo_history = 50
        
        # Detection history for navigation
        self.detections_history = {}  # frame_num -> detections
        
        # Now call super (which will call create_ui)
        super().__init__(parent_frame, viewer, video_manager, detection_manager,
                        reid_manager, gallery_manager, csv_manager, anchor_manager)
        
        # Load player names and team colors (after UI is created)
        self.load_player_name_list()
        self.load_team_colors()
        
        # Update quick tag dropdown with loaded player names
        if hasattr(self, 'quick_tag_player_combo'):
            self.update_quick_tag_dropdown()
        
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
        self.canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_canvas_release)
        self.canvas.bind('<Motion>', self.on_canvas_motion)
        self.canvas.bind('<Button-3>', self.on_canvas_right_click)  # Right-click for ball marking
        
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
        
        # Quick Tag section
        quick_tag_frame = ttk.LabelFrame(controls_frame, text="Quick Tag", padding=5)
        quick_tag_frame.pack(fill=tk.X, pady=5)
        
        quick_tag_inner = ttk.Frame(quick_tag_frame)
        quick_tag_inner.pack(fill=tk.X)
        
        ttk.Label(quick_tag_inner, text="Player:").pack(side=tk.LEFT, padx=2)
        self.quick_tag_player_var = tk.StringVar()
        # player_name_list might not be loaded yet, use empty list as default
        active_players = [name for name in (self.player_name_list if hasattr(self, 'player_name_list') and self.player_name_list else []) 
                         if hasattr(self, 'is_player_active') and self.is_player_active(name)]
        self.quick_tag_player_combo = ttk.Combobox(quick_tag_inner, textvariable=self.quick_tag_player_var,
                                                  width=18, values=active_players, state="readonly")
        self.quick_tag_player_combo.pack(side=tk.LEFT, padx=2)
        self.quick_tag_player_combo.bind("<<ComboboxSelected>>", self.on_quick_tag_player_select)
        
        ttk.Label(quick_tag_inner, text="Team:").pack(side=tk.LEFT, padx=2)
        self.quick_tag_team_var = tk.StringVar()
        team_names = self.get_team_names()
        team_names_with_blank = [""] + team_names
        self.quick_tag_team_combo = ttk.Combobox(quick_tag_inner, textvariable=self.quick_tag_team_var,
                                                width=12, values=team_names_with_blank)
        self.quick_tag_team_combo.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(quick_tag_frame, text="Apply Quick Tag", command=self.apply_quick_tag).pack(fill=tk.X, pady=2)
        
        # Detection controls
        detect_frame = ttk.LabelFrame(controls_frame, text="Detection", padding=5)
        detect_frame.pack(fill=tk.X, pady=5)
        
        self.init_button = ttk.Button(detect_frame, text="Initialize Detection", 
                                      command=self.initialize_detection)
        self.init_button.pack(fill=tk.X, pady=2)
        
        ttk.Button(detect_frame, text="Draw Manual Box", command=self.enable_manual_drawing).pack(fill=tk.X, pady=2)
        
        # Ball verification controls
        ball_frame = ttk.LabelFrame(controls_frame, text="Ball Verification", padding=5)
        ball_frame.pack(fill=tk.X, pady=5)
        
        self.ball_click_button = ttk.Button(ball_frame, text="⚽ Mark Ball (B key)", 
                                           command=self.enable_ball_click)
        self.ball_click_button.pack(fill=tk.X, pady=2)
        
        ttk.Button(ball_frame, text="Remove Ball from Frame", 
                  command=self.remove_ball_from_frame).pack(fill=tk.X, pady=2)
        ttk.Button(ball_frame, text="Manage Ball Positions", 
                  command=self.manage_ball_positions).pack(fill=tk.X, pady=2)
        
        self.ball_count_label = ttk.Label(ball_frame, text="Ball positions: 0", foreground="gray")
        self.ball_count_label.pack(fill=tk.X, pady=2)
        
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
        
        tag_buttons = ttk.Frame(tag_frame)
        tag_buttons.pack(fill=tk.X, pady=5)
        ttk.Button(tag_buttons, text="Tag Player", command=self.tag_player).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(tag_buttons, text="Tag All Instances", command=self.tag_all_instances).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        ttk.Button(tag_frame, text="Tag All Players (All Frames)", command=self.tag_all_instances_all_players).pack(fill=tk.X, pady=2)
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
        
        # Summary and Progress
        summary_frame = ttk.LabelFrame(controls_frame, text="Summary & Progress", padding=5)
        summary_frame.pack(fill=tk.X, pady=5)
        
        self.summary_label = ttk.Label(summary_frame, text="No tags yet", wraplength=400)
        self.summary_label.pack(fill=tk.X)
        
        # Progress indicator
        progress_frame = ttk.Frame(summary_frame)
        progress_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.progress_label = ttk.Label(progress_frame, text="Progress: 0%", foreground="blue")
        self.progress_label.pack(side=tk.LEFT)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=200)
        self.progress_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Status
        self.status_label = ttk.Label(controls_frame, text="Ready - Load video and initialize detection")
        self.status_label.pack(fill=tk.X, pady=5)
        
        # Navigation shortcuts
        nav_shortcuts_frame = ttk.LabelFrame(controls_frame, text="Navigation Shortcuts", padding=5)
        nav_shortcuts_frame.pack(fill=tk.X, pady=5)
        
        nav_shortcuts_inner = ttk.Frame(nav_shortcuts_frame)
        nav_shortcuts_inner.pack(fill=tk.X)
        
        ttk.Button(nav_shortcuts_inner, text="Next Untagged (N)", command=self.jump_to_next_untagged).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(nav_shortcuts_inner, text="Prev Untagged (P)", command=self.jump_to_prev_untagged).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Goto Track ID
        goto_frame = ttk.Frame(nav_shortcuts_frame)
        goto_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(goto_frame, text="Goto Track ID:").pack(side=tk.LEFT, padx=2)
        self.goto_track_var = tk.StringVar()
        goto_entry = ttk.Entry(goto_frame, textvariable=self.goto_track_var, width=10)
        goto_entry.pack(side=tk.LEFT, padx=2)
        goto_entry.bind('<Return>', lambda e: self.goto_track_id())
        ttk.Button(goto_frame, text="Go", command=self.goto_track_id).pack(side=tk.LEFT, padx=2)
        
        # Undo/Redo
        undo_frame = ttk.Frame(controls_frame)
        undo_frame.pack(fill=tk.X, pady=5)
        ttk.Button(undo_frame, text="↶ Undo (U)", command=self.undo_action).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(undo_frame, text="↷ Redo (R)", command=self.redo_action).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Save/Load buttons
        save_frame = ttk.Frame(controls_frame)
        save_frame.pack(fill=tk.X, pady=5)
        ttk.Button(save_frame, text="Save Tags", command=self.save_tags).pack(fill=tk.X, pady=2)
        ttk.Button(save_frame, text="Import Seed Config", command=self.import_seed_config).pack(fill=tk.X, pady=2)
        
        # Bind keyboard shortcuts (bind to root for global access)
        self.viewer.root.bind('<KeyPress-b>', lambda e: self._handle_keyboard_shortcut('b', e))
        self.viewer.root.bind('<KeyPress-B>', lambda e: self._handle_keyboard_shortcut('b', e))
        self.viewer.root.bind('<KeyPress-t>', lambda e: self._handle_keyboard_shortcut('t', e))
        self.viewer.root.bind('<KeyPress-T>', lambda e: self._handle_keyboard_shortcut('t', e))
        self.viewer.root.bind('<KeyPress-n>', lambda e: self._handle_keyboard_shortcut('n', e))
        self.viewer.root.bind('<KeyPress-N>', lambda e: self._handle_keyboard_shortcut('n', e))
        self.viewer.root.bind('<KeyPress-p>', lambda e: self._handle_keyboard_shortcut('p', e))
        self.viewer.root.bind('<KeyPress-P>', lambda e: self._handle_keyboard_shortcut('p', e))
        self.viewer.root.bind('<KeyPress-u>', lambda e: self._handle_keyboard_shortcut('u', e))
        self.viewer.root.bind('<KeyPress-U>', lambda e: self._handle_keyboard_shortcut('u', e))
        self.viewer.root.bind('<KeyPress-r>', lambda e: self._handle_keyboard_shortcut('r', e))
        self.viewer.root.bind('<KeyPress-R>', lambda e: self._handle_keyboard_shortcut('r', e))
        self.viewer.root.bind('<KeyPress-a>', lambda e: self._handle_keyboard_shortcut('a', e))
        self.viewer.root.bind('<KeyPress-A>', lambda e: self._handle_keyboard_shortcut('a', e))
        self.viewer.root.bind('<KeyPress-g>', lambda e: self._handle_keyboard_shortcut('g', e))
        self.viewer.root.bind('<KeyPress-G>', lambda e: self._handle_keyboard_shortcut('g', e))
        
        # Update quick tag dropdown
        self.update_quick_tag_dropdown()
    
    # ==================== DISPLAY METHODS ====================
    
    def display_frame(self, frame: np.ndarray, frame_num: int):
        """Display a frame with detections, ball positions, and manual boxes"""
        if frame is None:
            return
        
        self.current_frame = frame.copy()
        display_frame = frame.copy()
        
        # Draw ball positions for this frame
        for ball_frame, ball_x, ball_y in self.ball_positions:
            if ball_frame == frame_num:
                cv2.circle(display_frame, (int(ball_x), int(ball_y)), 10, (0, 0, 255), 3)
                cv2.circle(display_frame, (int(ball_x), int(ball_y)), 12, (255, 255, 255), 1)
        
        # Draw manual detection boxes
        for manual_box in self.manual_detections:
            if manual_box.get('frame') == frame_num:
                x1, y1, x2, y2 = manual_box['bbox']
                cv2.rectangle(display_frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 255), 2)
        
        # Get detections for this frame
        detections = self.detection_manager.get_detections(frame_num)
        
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
        
        # Draw box being drawn
        if self.drawing_box and self.box_start and self.box_end:
            x1, y1 = map(int, self.box_start)
            x2, y2 = map(int, self.box_end)
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
        
        # Convert to PhotoImage and display
        self._display_image(display_frame)
        
        # Update detections list
        self.update_detections_list(detections)
        self.update_summary()
        self.update_ball_count()
    
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
    
    # ==================== CANVAS EVENT HANDLERS ====================
    
    def on_canvas_click(self, event):
        """Handle canvas click - ball marking or detection selection"""
        if self.ball_click_mode:
            # Ball marking mode
            canvas_x = event.x
            canvas_y = event.y
            
            # Convert to frame coordinates
            frame_x = (canvas_x - self.display_offset_x) / self.display_scale
            frame_y = (canvas_y - self.display_offset_y) / self.display_scale
            
            # Clamp to frame bounds
            if self.current_frame is not None:
                frame_x = max(0, min(frame_x, self.current_frame.shape[1]))
                frame_y = max(0, min(frame_y, self.current_frame.shape[0]))
                
                # Remove existing ball for this frame
                self.ball_positions = [(f, x, y) for f, x, y in self.ball_positions 
                                      if f != self.viewer.current_frame_num]
                
                # Add new ball position
                self.ball_positions.append((self.viewer.current_frame_num, frame_x, frame_y))
                self.update_ball_count()
                self.update_display()
                self.ball_click_mode = False
                self.ball_click_button.config(text="⚽ Mark Ball (B key)", state=tk.NORMAL)
                self.canvas.config(cursor='crosshair')
                self.status_label.config(text=f"✓ Ball marked at ({frame_x:.0f}, {frame_y:.0f})")
            return
        
        # Normal click - select detection or start drawing box
        if self.drawing_box:
            self.box_start = (event.x, event.y)
            return
        
        # Select detection
        if self.current_frame is not None:
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
    
    def on_canvas_drag(self, event):
        """Handle canvas drag - update box being drawn"""
        if self.drawing_box and self.box_start:
            self.box_end = (event.x, event.y)
            self.update_display()
    
    def on_canvas_release(self, event):
        """Handle canvas release - finish box"""
        if self.drawing_box and self.box_start and self.box_end:
            # Convert canvas coordinates to frame coordinates
            x1 = min(self.box_start[0], self.box_end[0])
            y1 = min(self.box_start[1], self.box_end[1])
            x2 = max(self.box_start[0], self.box_end[0])
            y2 = max(self.box_start[1], self.box_end[1])
            
            # Convert to frame coordinates
            frame_x1 = (x1 - self.display_offset_x) / self.display_scale
            frame_y1 = (y1 - self.display_offset_y) / self.display_scale
            frame_x2 = (x2 - self.display_offset_x) / self.display_scale
            frame_y2 = (y2 - self.display_offset_y) / self.display_scale
            
            # Clamp to frame bounds
            if self.current_frame is not None:
                frame_x1 = max(0, min(frame_x1, self.current_frame.shape[1]))
                frame_y1 = max(0, min(frame_y1, self.current_frame.shape[0]))
                frame_x2 = max(0, min(frame_x2, self.current_frame.shape[1]))
                frame_y2 = max(0, min(frame_y2, self.current_frame.shape[0]))
                
                if (frame_x2 - frame_x1) > 20 and (frame_y2 - frame_y1) > 20:
                    # Add manual detection
                    self.manual_detections.append({
                        'frame': self.viewer.current_frame_num,
                        'bbox': (frame_x1, frame_y1, frame_x2, frame_y2)
                    })
                    self.status_label.config(text=f"✓ Manual box added: {int(frame_x2-frame_x1)}x{int(frame_y2-frame_y1)}")
            
            self.drawing_box = False
            self.box_start = None
            self.box_end = None
            self.update_display()
    
    def on_canvas_motion(self, event):
        """Handle canvas mouse motion"""
        pass
    
    def on_canvas_right_click(self, event):
        """Handle right-click - enable ball marking"""
        self.enable_ball_click()
    
    # ==================== BALL VERIFICATION ====================
    
    def enable_ball_click(self):
        """Enable ball marking mode"""
        self.ball_click_mode = True
        self.ball_click_button.config(text="⚽ Click Canvas to Mark", state=tk.DISABLED)
        self.canvas.config(cursor="plus")
        self.status_label.config(text="← Click on the ball in the video frame", 
                                foreground="orange")
    
    def remove_ball_from_frame(self):
        """Remove ball position from current frame"""
        initial_count = len(self.ball_positions)
        self.ball_positions = [(f, x, y) for f, x, y in self.ball_positions 
                              if f != self.viewer.current_frame_num]
        removed = initial_count - len(self.ball_positions)
        
        if removed > 0:
            self.update_display()
            self.update_summary()
            self.update_ball_count()
            messagebox.showinfo("Removed", f"Removed {removed} ball position(s) from frame {self.viewer.current_frame_num + 1}")
        else:
            messagebox.showinfo("Info", "No ball position found in current frame")
    
    def update_ball_count(self):
        """Update the ball count label for current frame"""
        if not hasattr(self, 'ball_count_label'):
            return
        ball_count = sum(1 for f, x, y in self.ball_positions if f == self.viewer.current_frame_num)
        total_count = len(self.ball_positions)
        if ball_count > 0:
            self.ball_count_label.config(text=f"Ball positions: {ball_count} (this frame) | {total_count} total", 
                                       foreground="green")
        else:
            self.ball_count_label.config(text=f"Ball positions: {total_count} total (none in this frame)", 
                                       foreground="gray")
    
    def manage_ball_positions(self):
        """Open dialog to manage all ball positions (view, edit, delete)"""
        dialog = tk.Toplevel(self.viewer.root)
        dialog.title("Manage Ball Positions")
        dialog.geometry("800x700")
        dialog.transient(self.viewer.root)
        
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
            
            ttk.Label(edit_dialog, text=f"Editing ball position at Frame {frame_num + 1}", 
                     font=("Arial", 10, "bold")).pack(pady=10)
            
            # Frame number
            frame_frame = ttk.Frame(edit_dialog)
            frame_frame.pack(fill=tk.X, padx=20, pady=5)
            ttk.Label(frame_frame, text="Frame Number:").pack(side=tk.LEFT)
            frame_var = tk.IntVar(value=frame_num)
            frame_spin = ttk.Spinbox(frame_frame, from_=0, to=max(0, self.video_manager.total_frames - 1), 
                                    textvariable=frame_var, width=10)
            frame_spin.pack(side=tk.LEFT, padx=5)
            ttk.Button(frame_frame, text="Go to Frame", 
                      command=lambda: self.jump_to_frame_and_close(frame_var.get(), edit_dialog)).pack(side=tk.LEFT, padx=5)
            
            # X position
            x_frame = ttk.Frame(edit_dialog)
            x_frame.pack(fill=tk.X, padx=20, pady=5)
            ttk.Label(x_frame, text="X Position:").pack(side=tk.LEFT)
            x_var = tk.DoubleVar(value=self.ball_positions[ball_idx][1])
            x_spin = ttk.Spinbox(x_frame, from_=0, to=self.video_manager.width if hasattr(self.video_manager, 'width') else 1920, 
                                textvariable=x_var, width=15, format="%.1f")
            x_spin.pack(side=tk.LEFT, padx=5)
            
            # Y position
            y_frame = ttk.Frame(edit_dialog)
            y_frame.pack(fill=tk.X, padx=20, pady=5)
            ttk.Label(y_frame, text="Y Position:").pack(side=tk.LEFT)
            y_var = tk.DoubleVar(value=self.ball_positions[ball_idx][2])
            y_spin = ttk.Spinbox(y_frame, from_=0, to=self.video_manager.height if hasattr(self.video_manager, 'height') else 1080, 
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
        
        tree.bind("<Double-1>", lambda e: edit_selected())
        
        ttk.Button(button_frame, text="Edit Selected", command=edit_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Selected", command=delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Jump to Frame", command=jump_to_frame).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def jump_to_frame_and_close(self, frame_num, dialog):
        """Jump to a specific frame and close dialog"""
        if 0 <= frame_num < self.video_manager.total_frames:
            self.goto_frame(frame_num)
            dialog.destroy()
        else:
            messagebox.showerror("Invalid Frame", f"Frame {frame_num + 1} is out of range")
    
    # ==================== QUICK TAG ====================
    
    def update_quick_tag_dropdown(self):
        """Update the quick tag player dropdown to show only active players"""
        if not hasattr(self, 'quick_tag_player_combo') or not self.quick_tag_player_combo:
            return
        
        try:
            current_selection = self.quick_tag_player_var.get()
            active_player_list = [name for name in self.player_name_list if self.is_player_active(name)]
            self.quick_tag_player_combo['values'] = active_player_list
            
            if current_selection in active_player_list:
                self.quick_tag_player_var.set(current_selection)
            else:
                self.quick_tag_player_var.set("")
        except Exception as e:
            print(f"⚠ Error updating quick tag dropdown: {e}")
    
    def is_player_active(self, player_name):
        """Check if a player is active in the roster"""
        if hasattr(self, 'player_roster') and self.player_roster:
            if player_name in self.player_roster:
                player_data = self.player_roster[player_name]
                if isinstance(player_data, dict):
                    return player_data.get('active', True)
                return True
        
        # Fallback to global roster manager
        if not hasattr(self, 'roster_manager') or self.roster_manager is None:
            try:
                current_file = Path(__file__).resolve()
                parent_dir = current_file.parent.parent.parent.parent
                roster_path = os.path.join(parent_dir, 'team_roster_manager.py')
                if os.path.exists(roster_path):
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("team_roster_manager", roster_path)
                    roster_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(roster_module)
                    TeamRosterManager = roster_module.TeamRosterManager
                    self.roster_manager = TeamRosterManager()
                else:
                    from team_roster_manager import TeamRosterManager
                    self.roster_manager = TeamRosterManager()
            except:
                return True  # Default to active if roster unavailable
        
        if not self.roster_manager:
            return True
        
        roster = self.roster_manager.roster if hasattr(self.roster_manager, 'roster') else {}
        if player_name in roster:
            return roster[player_name].get('active', True)
        return True  # Default to active if player not in roster
    
    def on_quick_tag_player_select(self, event):
        """Handle quick tag player selection - auto-fill team"""
        player_name = self.quick_tag_player_var.get()
        if not player_name:
            return
        
        # Try to get team from roster
        if player_name in self.player_roster:
            roster_entry = self.player_roster[player_name]
            if roster_entry.get("team") and hasattr(self, 'quick_tag_team_combo'):
                self.quick_tag_team_var.set(roster_entry["team"])
            return
        
        # Fall back to approved_mappings
        mappings = self.viewer.get_approved_mappings()
        for pid_str, mapping in mappings.items():
            if isinstance(mapping, tuple) and len(mapping) >= 2:
                if mapping[0] == player_name and mapping[1]:
                    if hasattr(self, 'quick_tag_team_combo'):
                        self.quick_tag_team_var.set(mapping[1])
                    return
    
    def apply_quick_tag(self):
        """Apply quick tag from quick tag section to selected detection"""
        if self.selected_detection is None:
            messagebox.showwarning("Warning", "Please select a detection first")
            return
        
        player_name = self.quick_tag_player_var.get().strip()
        if not player_name:
            messagebox.showwarning("Warning", "Please select a player name")
            return
        
        # Set the player name and team in the tag player section
        self.player_name_var.set(player_name)
        team = self.quick_tag_team_var.get().strip()
        self.team_var.set(team)
        
        # Tag the player
        self.tag_player()
        
        # Clear quick tag fields
        self.quick_tag_player_var.set("")
        self.quick_tag_team_var.set("")
    
    # ==================== MANUAL DETECTION DRAWING ====================
    
    def enable_manual_drawing(self):
        """Enable manual box drawing mode"""
        self.drawing_box = True
        self.canvas.config(cursor="crosshair")
        self.status_label.config(text="← Click and drag to draw a box around a player")
    
    # ==================== DETECTION AND MATCHING ====================
    
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
                    # Store in history
                    detections = self.detection_manager.get_detections(i)
                    if detections is not None:
                        self.detections_history[i] = detections
                    if i % 5 == 0:
                        self.status_label.config(text=f"Processing frame {i}/{frames_to_process}...")
                        self.viewer.root.update()
            
            self.status_label.config(text="Detection initialized - Ready for tagging")
            self.load_frame(0)
            self.update_progress()
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
                jersey_number=detected_jersey
            )
            
            if match_result:
                player_name, confidence, _ = match_result
                if confidence >= 0.6:  # Suggestion threshold
                    self.gallery_suggestions[track_id] = (player_name, confidence)
    
    # ==================== TAGGING ====================
    
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
            self.update_quick_tag_dropdown()
        
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
        
        # Validate tag
        validation_warnings = self.validate_tag(player_name, team, jersey_number)
        if validation_warnings:
            warning_msg = "Validation warnings:\n\n" + "\n".join(validation_warnings)
            response = messagebox.askyesno("Validation Warnings", warning_msg + "\n\nContinue anyway?")
            if not response:
                return
        
        # Save state for undo
        old_mapping = self.viewer.approved_mappings.get(pid_str)
        self._save_undo_state("tag_player", {
            'track_id': int(track_id),
            'old_mapping': old_mapping,
            'new_mapping': (player_name, team, jersey_number)
        })
        
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
        
        # Save state for undo
        old_mapping = self.viewer.approved_mappings.get(pid_str)
        self._save_undo_state("clear_tag", {
            'track_id': int(track_id),
            'old_mapping': old_mapping
        })
        
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
        """Update summary label and progress"""
        mappings = self.viewer.get_approved_mappings()
        anchor_count = self.anchor_manager.count_anchors()
        ball_count = len(self.ball_positions)
        
        summary = f"Tagged: {len(mappings)} players, {anchor_count} anchor frames, {ball_count} ball positions"
        self.summary_label.config(text=summary)
        
        # Update progress
        self.update_progress()
    
    # ==================== SEED CONFIG LOAD/SAVE ====================
    
    def auto_load_seed_data(self):
        """Auto-load ball positions and player mappings from seed config files"""
        if not self.video_manager.video_path:
            return
        
        # First, try to load from PlayerTagsSeed-{video_name}.json in video directory
        video_dir = os.path.dirname(os.path.abspath(self.video_manager.video_path))
        video_basename = os.path.splitext(os.path.basename(self.video_manager.video_path))[0]
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
        
        # Try to load from seed_config.json if video-specific file not found
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
            if os.path.normpath(config_video) == os.path.normpath(self.video_manager.video_path):
                # Load ball positions
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
                    print(f"✓ Auto-loaded {loaded_balls} ball position(s)")
                    self.update_ball_count()
                    loaded_any = True
                
                # Load player roster
                player_roster = config.get("player_roster", {})
                if player_roster:
                    self.player_roster = player_roster
                    print(f"✓ Auto-loaded player roster with {len(self.player_roster)} players")
                    loaded_any = True
                    self.update_quick_tag_dropdown()
                
                # Load player mappings
                player_mappings = config.get("player_mappings", {})
                if player_mappings:
                    loaded_mappings = 0
                    for k, v in player_mappings.items():
                        try:
                            if isinstance(v, (list, tuple)) and len(v) >= 2:
                                value = (str(v[0]) if v[0] is not None else "", 
                                        str(v[1]) if v[1] is not None else "",
                                        str(v[2]) if len(v) >= 3 and v[2] is not None else "")
                            elif isinstance(v, (list, tuple)) and len(v) == 1:
                                value = (str(v[0]) if v[0] is not None else "", "", "")
                            elif isinstance(v, (str, int, float)):
                                value = (str(v), "", "")
                            else:
                                continue
                            self.viewer.approved_mappings[str(k)] = value
                            loaded_mappings += 1
                        except:
                            pass
                    
                    if loaded_mappings > 0:
                        print(f"✓ Auto-loaded {loaded_mappings} track ID mapping(s)")
                        self.save_player_name_list()
                        loaded_any = True
                
                # Load anchor frames via anchor_manager
                anchor_frames = config.get("anchor_frames", {})
                if anchor_frames:
                    for frame_num_str, anchors in anchor_frames.items():
                        try:
                            frame_num = int(frame_num_str)
                            for anchor in anchors:
                                self.anchor_manager.add_anchor(
                                    frame_num,
                                    anchor.get('track_id', 0),
                                    anchor.get('player_name', ''),
                                    anchor.get('bbox', []),
                                    anchor.get('team', ''),
                                    anchor.get('jersey_number', '')
                                )
                        except:
                            pass
                    print(f"✓ Auto-loaded anchor frames")
                    loaded_any = True
        
        return loaded_any
    
    def import_seed_config(self):
        """Import seed config from file dialog"""
        file_path = filedialog.askopenfilename(
            title="Import Seed Config",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)
            
            if self._load_seed_config_data(config, file_path):
                messagebox.showinfo("Success", f"Imported seed config from:\n{os.path.basename(file_path)}")
                self.update_display()
                self.update_summary()
            else:
                messagebox.showwarning("Warning", "Seed config loaded but no matching data found for this video")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import seed config:\n{e}")
    
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
                "current_frame": self.viewer.current_frame_num,
                "ball_positions": [[f, x, y] for f, x, y in self.ball_positions],
                "player_roster": self.player_roster
            }
            
            if self.anchor_manager.save_to_seed_config(seed_file, additional_data):
                messagebox.showinfo("Success", f"Tags saved to:\n{os.path.basename(seed_file)}")
                self.status_label.config(text=f"✓ Tags saved to {os.path.basename(seed_file)}")
            else:
                messagebox.showerror("Error", "Failed to save tags")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save tags: {e}")
    
    # ==================== CSV PRE-POPULATION ====================
    
    def pre_populate_from_csv(self):
        """Pre-populate player tags from CSV data"""
        if not self.csv_manager.is_loaded():
            return
        
        # Get player assignments from CSV for current frame
        frame_num = self.viewer.current_frame_num
        player_data = self.csv_manager.get_player_data(frame_num)
        
        if not player_data:
            return
        
        # Update mappings from CSV
        for player_id, (x, y, team, name, bbox) in player_data.items():
            if name and name.strip():
                pid_str = str(int(player_id))
                # Only update if not already tagged (CSV is fallback)
                if pid_str not in self.viewer.approved_mappings:
                    self.viewer.approved_mappings[pid_str] = (name, team or "", "")
        
        self.update_display()
        self.update_detections_list(self.detection_manager.get_detections(frame_num))
        self.update_summary()
    
    # ==================== UTILITY METHODS ====================
    
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
            if 'team_colors' in self.team_colors:
                team_colors = self.team_colors['team_colors']
                if 'team1' in team_colors:
                    teams.append(team_colors['team1'].get('name', 'Team 1'))
                if 'team2' in team_colors:
                    teams.append(team_colors['team2'].get('name', 'Team 2'))
            return teams
        return []
    
    # ==================== NAVIGATION ====================
    
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
            for widget in self.parent_frame.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Spinbox):
                        child.config(to=self.video_manager.total_frames - 1)
            self.load_frame(0)
            self.status_label.config(text=f"Video loaded: {self.video_manager.total_frames} frames")
            
            # Auto-load seed data
            self.auto_load_seed_data()
            
            # Pre-populate from CSV if available
            if self.csv_manager.is_loaded():
                self.pre_populate_from_csv()
    
    def on_csv_loaded(self):
        # Pre-populate tags from CSV
        self.pre_populate_from_csv()
        self.status_label.config(text="CSV loaded - Player assignments applied")
    
    # ==================== ENHANCEMENTS ====================
    
    def _handle_keyboard_shortcut(self, key, event):
        """Handle keyboard shortcuts, ignoring if user is typing"""
        # Check if focus is on an entry widget
        try:
            widget = self.viewer.root.focus_get()
            if isinstance(widget, (tk.Entry, ttk.Combobox, tk.Text)):
                return  # User is typing, ignore shortcut
        except:
            pass
        
        # Execute shortcut
        key_lower = key.lower()
        if key_lower == 'b':
            self.enable_ball_click()
        elif key_lower == 't' and self.selected_detection is not None:
            self.tag_player()
        elif key_lower == 'n':
            self.jump_to_next_untagged()
        elif key_lower == 'p':
            self.jump_to_prev_untagged()
        elif key_lower == 'u':
            self.undo_action()
        elif key_lower == 'r':
            self.redo_action()
        elif key_lower == 'a' and self.selected_detection is not None:
            self.tag_all_instances()
        elif key_lower == 'g':
            self.goto_track_id()
    
    def jump_to_next_untagged(self):
        """Jump to next frame with untagged players"""
        if not self.detections_history:
            # Try to build detections history from detection_manager
            self._build_detections_history()
        
        if not self.detections_history:
            messagebox.showinfo("No Detections", "Please initialize detection first")
            return
        
        # First, check if current frame has all players tagged
        # If so, auto-tag all instances of all tagged players, then move to next
        detections = self.detection_manager.get_detections(self.viewer.current_frame_num)
        if detections is not None and len(detections) > 0:
            all_tagged = True
            for track_id in detections.tracker_id:
                if track_id is None:
                    continue
                pid_str = str(int(track_id))
                if pid_str not in self.viewer.approved_mappings:
                    all_tagged = False
                    break
            
            # If all players in current frame are tagged, tag all instances of all of them
            if all_tagged:
                self.tag_all_instances_all_players(silent=True)
        
        start_frame = self.viewer.current_frame_num + 1
        for frame_num in range(start_frame, self.video_manager.total_frames):
            detections = self.detection_manager.get_detections(frame_num)
            if detections is not None and len(detections) > 0:
                # Check if any detection is untagged
                for track_id in detections.tracker_id:
                    if track_id is None:
                        continue
                    pid_str = str(int(track_id))
                    if pid_str not in self.viewer.approved_mappings:
                        # Found untagged frame
                        self.goto_frame(frame_num)
                        return
        
        # If no untagged frames found, show message
        messagebox.showinfo("No Untagged Frames", "All frames have been tagged!")
    
    def jump_to_prev_untagged(self):
        """Jump to previous frame with untagged players"""
        if not self.detections_history:
            self._build_detections_history()
        
        if not self.detections_history:
            messagebox.showinfo("No Detections", "Please initialize detection first")
            return
        
        start_frame = self.viewer.current_frame_num - 1
        for frame_num in range(start_frame, -1, -1):
            detections = self.detection_manager.get_detections(frame_num)
            if detections is not None and len(detections) > 0:
                # Check if any detection is untagged
                for track_id in detections.tracker_id:
                    if track_id is None:
                        continue
                    pid_str = str(int(track_id))
                    if pid_str not in self.viewer.approved_mappings:
                        # Found untagged frame
                        self.goto_frame(frame_num)
                        return
        
        # If no untagged frames found, show message
        messagebox.showinfo("No Untagged Frames", "All frames before this have been tagged!")
    
    def _build_detections_history(self):
        """Build detections history from detection_manager"""
        self.detections_history = {}
        # Scan through frames to build history
        for frame_num in range(min(100, self.video_manager.total_frames)):  # Limit to first 100 for performance
            detections = self.detection_manager.get_detections(frame_num)
            if detections is not None and len(detections) > 0:
                self.detections_history[frame_num] = detections
    
    def goto_track_id(self):
        """Go to frame containing specified track ID"""
        try:
            track_id_str = self.goto_track_var.get().strip()
            if not track_id_str:
                messagebox.showwarning("No Track ID", "Please enter a track ID to search for")
                return
            
            try:
                target_track_id = int(track_id_str)
            except ValueError:
                messagebox.showerror("Invalid Input", f"'{track_id_str}' is not a valid track ID number")
                return
            
            # Search from current frame forward, then wrap around
            search_order = list(range(self.viewer.current_frame_num + 1, self.video_manager.total_frames)) + \
                          list(range(0, self.viewer.current_frame_num + 1))
            
            found_frame = None
            for frame_num in search_order:
                detections = self.detection_manager.get_detections(frame_num)
                if detections is not None:
                    for track_id in detections.tracker_id:
                        if track_id is not None and int(track_id) == target_track_id:
                            found_frame = frame_num
                            break
                    if found_frame is not None:
                        break
            
            if found_frame is not None:
                self.goto_frame(found_frame)
                messagebox.showinfo("Found", f"Track ID #{target_track_id} found at frame {found_frame + 1}")
            else:
                messagebox.showinfo("Not Found", f"Track ID #{target_track_id} not found in video")
        except Exception as e:
            messagebox.showerror("Error", f"Could not search for track ID: {e}")
    
    def tag_all_instances(self):
        """Tag all instances of the selected track ID across all frames"""
        if self.selected_detection is None:
            messagebox.showwarning("Warning", "Please select a detection first")
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
        
        # Get current name, team, and jersey number
        player_name = self.player_name_var.get().strip()
        if not player_name:
            messagebox.showwarning("Warning", "Please select or enter a player name first")
            return
        
        team = self.team_var.get().strip()
        jersey_number = self.jersey_number_var.get().strip()
        
        # Validate team (except for coaches, referees, etc.)
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
        
        # Count how many frames this ID appears in
        count = 0
        for frame_num in range(self.video_manager.total_frames):
            frame_detections = self.detection_manager.get_detections(frame_num)
            if frame_detections is not None:
                for tid in frame_detections.tracker_id:
                    if tid is not None and int(tid) == int(track_id):
                        count += 1
                        break
        
        response = messagebox.askyesno(
            "Tag All Instances?",
            f"Tag all instances of ID #{track_id} as '{player_name}'?\n\n"
            f"This will tag {count} frames.\n"
            f"Continue?"
        )
        
        if response:
            # Save state for undo
            self._save_undo_state("tag_all_instances", {
                'track_id': int(track_id),
                'player_name': player_name,
                'team': team,
                'jersey_number': jersey_number
            })
            
            # Tag all instances
            instances_tagged = 0
            for frame_num in range(self.video_manager.total_frames):
                frame_detections = self.detection_manager.get_detections(frame_num)
                if frame_detections is not None:
                    for i, tid in enumerate(frame_detections.tracker_id):
                        if tid is not None and int(tid) == int(track_id):
                            # Tag this instance
                            self.viewer.approved_mappings[pid_str] = (player_name, team, jersey_number)
                            
                            # Create anchor frame
                            if i < len(frame_detections.xyxy):
                                bbox = frame_detections.xyxy[i].tolist()
                                self.anchor_manager.add_anchor(
                                    frame_num,
                                    int(track_id),
                                    player_name,
                                    bbox,
                                    team,
                                    jersey_number
                                )
                            
                            instances_tagged += 1
                            break
            
            self.update_display()
            self.update_detections_list(detections)
            self.update_summary()
            messagebox.showinfo("Tagged", 
                              f"Tagged all instances of ID #{track_id} as '{player_name}'\n\n"
                              f"Tagged {instances_tagged} frame(s)")
    
    def tag_all_instances_all_players(self, silent=False):
        """Tag all instances of all track IDs that are currently tagged in this frame"""
        detections = self.detection_manager.get_detections(self.viewer.current_frame_num)
        if detections is None or len(detections) == 0:
            if not silent:
                messagebox.showwarning("Warning", "No detections in current frame")
            return
        
        # Collect all tagged players in current frame
        tagged_players = {}  # {track_id: (player_name, team, jersey_number)}
        untagged_count = 0
        
        for i, track_id in enumerate(detections.tracker_id):
            if track_id is None:
                continue
            
            pid_str = str(int(track_id))
            
            if pid_str in self.viewer.approved_mappings:
                mapping = self.viewer.approved_mappings[pid_str]
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
                messagebox.showwarning("Warning", "No tagged players in current frame")
            return
        
        if not silent:
            response = messagebox.askyesno(
                "Tag All Instances?",
                f"Tag all instances of {len(tagged_players)} player(s) across all frames?\n\n"
                f"This will tag all frames where these players appear.\n"
                f"Continue?"
            )
            if not response:
                return
        
        # Save state for undo
        self._save_undo_state("tag_all_instances_all_players", {
            'tagged_players': dict(tagged_players)
        })
        
        # Tag all instances of each player
        total_instances = 0
        for track_id, (player_name, team, jersey_number) in tagged_players.items():
            pid_str = str(int(track_id))
            instances = 0
            
            for frame_num in range(self.video_manager.total_frames):
                frame_detections = self.detection_manager.get_detections(frame_num)
                if frame_detections is not None:
                    for i, tid in enumerate(frame_detections.tracker_id):
                        if tid is not None and int(tid) == int(track_id):
                            # Tag this instance
                            self.viewer.approved_mappings[pid_str] = (player_name, team, jersey_number)
                            
                            # Create anchor frame (only every 150 frames to avoid thousands)
                            if frame_num % 150 == 0 and i < len(frame_detections.xyxy):
                                bbox = frame_detections.xyxy[i].tolist()
                                self.anchor_manager.add_anchor(
                                    frame_num,
                                    int(track_id),
                                    player_name,
                                    bbox,
                                    team,
                                    jersey_number
                                )
                            
                            instances += 1
                            total_instances += 1
                            break
        
        if not silent:
            self.update_display()
            self.update_detections_list(detections)
            self.update_summary()
            messagebox.showinfo("Tagged", 
                              f"Tagged all instances of {len(tagged_players)} player(s)\n\n"
                              f"Total: {total_instances} frame(s) tagged")
        else:
            self.update_summary()
    
    def update_progress(self):
        """Update tagging progress indicator"""
        if not hasattr(self, 'progress_label') or not hasattr(self, 'progress_bar'):
            return
        
        # Count total unique track IDs
        total_tracks = set()
        for frame_num in range(min(100, self.video_manager.total_frames)):  # Sample first 100 frames
            detections = self.detection_manager.get_detections(frame_num)
            if detections is not None:
                for track_id in detections.tracker_id:
                    if track_id is not None:
                        total_tracks.add(int(track_id))
        
        if len(total_tracks) == 0:
            self.progress_label.config(text="Progress: N/A")
            self.progress_bar['value'] = 0
            return
        
        # Count tagged tracks
        tagged_tracks = set()
        mappings = self.viewer.get_approved_mappings()
        for pid_str in mappings.keys():
            try:
                tagged_tracks.add(int(pid_str))
            except:
                pass
        
        # Calculate percentage
        if len(total_tracks) > 0:
            percentage = (len(tagged_tracks) / len(total_tracks)) * 100
            self.progress_label.config(text=f"Progress: {len(tagged_tracks)}/{len(total_tracks)} ({percentage:.0f}%)")
            self.progress_bar['value'] = percentage
        else:
            self.progress_label.config(text="Progress: 0%")
            self.progress_bar['value'] = 0
    
    def _save_undo_state(self, action_type, action_data):
        """Save state for undo"""
        self.undo_stack.append({
            'type': action_type,
            'data': action_data,
            'mappings': dict(self.viewer.approved_mappings),
            'frame': self.viewer.current_frame_num
        })
        
        # Limit undo history
        if len(self.undo_stack) > self.max_undo_history:
            self.undo_stack.pop(0)
        
        # Clear redo stack when new action is performed
        self.redo_stack = []
    
    def undo_action(self):
        """Undo last tagging action"""
        if not self.undo_stack:
            messagebox.showinfo("Nothing to Undo", "No actions to undo")
            return
        
        # Get last action
        last_action = self.undo_stack.pop()
        
        # Save current state to redo stack
        self.redo_stack.append({
            'type': 'undo',
            'mappings': dict(self.viewer.approved_mappings),
            'frame': self.viewer.current_frame_num
        })
        
        # Restore previous state
        self.viewer.approved_mappings = last_action['mappings']
        
        # Restore frame if needed
        if last_action.get('frame') != self.viewer.current_frame_num:
            self.goto_frame(last_action['frame'])
        
        self.update_display()
        self.update_detections_list(self.detection_manager.get_detections(self.viewer.current_frame_num))
        self.update_summary()
        self.status_label.config(text=f"✓ Undid: {last_action.get('type', 'action')}")
    
    def redo_action(self):
        """Redo last undone action"""
        if not self.redo_stack:
            messagebox.showinfo("Nothing to Redo", "No actions to redo")
            return
        
        # Get last redo action
        last_redo = self.redo_stack.pop()
        
        # Save current state to undo stack
        self.undo_stack.append({
            'type': 'redo',
            'mappings': dict(self.viewer.approved_mappings),
            'frame': self.viewer.current_frame_num
        })
        
        # Restore state
        self.viewer.approved_mappings = last_redo['mappings']
        
        if last_redo.get('frame') != self.viewer.current_frame_num:
            self.goto_frame(last_redo['frame'])
        
        self.update_display()
        self.update_detections_list(self.detection_manager.get_detections(self.viewer.current_frame_num))
        self.update_summary()
        self.status_label.config(text="✓ Redid action")
    
    def validate_tag(self, player_name, team, jersey_number):
        """Validate tag before applying"""
        warnings = []
        
        # Check for duplicate player names with different track IDs
        mappings = self.viewer.get_approved_mappings()
        for pid_str, (existing_name, existing_team, existing_jersey) in mappings.items():
            if existing_name == player_name and existing_name:  # Same name
                # Check if it's a different track (potential duplicate)
                if pid_str != str(self.selected_detection) if self.selected_detection is not None else True:
                    # Check if team matches (might be same player on same team)
                    if existing_team != team:
                        warnings.append(f"Player '{player_name}' already tagged with different team ({existing_team} vs {team})")
        
        # Check for missing team (unless exempt)
        coach_names = {"Kevin Hill", "Coach", "coach"}
        is_coach = any(coach.lower() in player_name.lower() for coach in coach_names)
        is_referee = "referee" in player_name.lower() or "ref" in player_name.lower()
        is_other = player_name.lower() in ["other", "guest player", "guest", "unknown"]
        
        if not team and not (is_coach or is_referee or is_other):
            warnings.append(f"Team not specified for '{player_name}'")
        
        # Check jersey number format
        if jersey_number and not jersey_number.isdigit():
            warnings.append(f"Jersey number '{jersey_number}' is not a valid number")
        
        return warnings
    
    def cleanup(self):
        # Save gallery
        if self.gallery_manager.is_initialized():
            self.gallery_manager.save_gallery()
        # Save player names
        self.save_player_name_list()
