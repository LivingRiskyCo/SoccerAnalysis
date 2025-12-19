"""
Combined Color Detection Helper
Combines ball and team color detection in one window with video playback
"""

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import json
import os
import copy
import threading
import time

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL/Pillow not available. Install with: pip install pillow")


class CombinedColorHelper:
    def __init__(self, root, callback=None):
        self.root = root
        self.root.title("Color Detection Helper (Ball & Team)")
        self.root.geometry("1200x900")
        self.root.resizable(True, True)
        
        self.callback = callback
        self.video_path = None
        self.cap = None
        self.current_frame = None
        self.hsv_frame = None
        self.current_frame_num = 0
        self.total_frames = 0
        self.fps = 30.0
        
        # Playback state
        self.is_playing = False
        self.play_thread = None
        self.play_speed = 1.0  # Playback speed multiplier
        
        # Ball colors
        self.ball_hsv_ranges = {"color1": None, "color2": None}
        self.ball_color_names = {"color1": "Color 1", "color2": "Color 2"}
        self.ball_history = {"color1": [], "color2": []}
        self.ball_original_sampled = {"color1": None, "color2": None}
        
        # Team colors
        self.team_colors = {
            "team1": {"name": "Team 1", "hsv_ranges": None},
            "team2": {"name": "Team 2", "hsv_ranges": None}
        }
        self.current_team = "team1"
        self.team_history = {"team1": [], "team2": []}
        self.team_original_sampled = {"team1": None, "team2": None}
        
        # History limit for undo
        self.max_history = 10
        
        # Fine-tuning state
        self.zoom_region = None  # HSV region around click point
        self.zoom_region_original = None  # BGR region for display
        self.selector_pos = None  # Position of selector in zoom area (x, y)
        self.original_click_pos = None  # Original click position in main image
        self.fine_tuning_mode = False  # Whether we're in fine-tuning mode
        self.current_mode = "ball"  # "ball" or "team"
        self.zoom_scale_factor = 1.0  # Scale factor for coordinate conversion
        self.zoom_region_size = 100  # Size of zoom region (pixels in original image)
        
        # Ensure window stays on top
        try:
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.focus_force()
            self.root.after(200, lambda: self.root.attributes('-topmost', False))
        except:
            pass
        
        self.create_widgets()
        self.load_presets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Tab notebook for Ball/Team
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Ball color tab
        ball_tab = ttk.Frame(notebook, padding="10")
        notebook.add(ball_tab, text="⚽ Ball Colors")
        
        # Team color tab
        team_tab = ttk.Frame(notebook, padding="10")
        notebook.add(team_tab, text="👕 Team Colors")
        
        # Bind tab change
        notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)
        
        # Video controls (shared)
        video_frame = ttk.LabelFrame(main_frame, text="Video Controls", padding="10")
        video_frame.pack(fill=tk.X, pady=5)
        
        # File selection
        file_frame = ttk.Frame(video_frame)
        file_frame.pack(fill=tk.X, pady=5)
        ttk.Label(file_frame, text="Video File:").pack(side=tk.LEFT, padx=5)
        self.video_path_entry = ttk.Entry(file_frame, width=50)
        self.video_path_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="Browse", command=self.browse_video).pack(side=tk.LEFT, padx=5)
        
        # Playback controls
        playback_frame = ttk.Frame(video_frame)
        playback_frame.pack(fill=tk.X, pady=5)
        
        self.play_button = ttk.Button(playback_frame, text="▶ Play", command=self.toggle_playback)
        self.play_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(playback_frame, text="⏮ First", command=self.first_frame).pack(side=tk.LEFT, padx=5)
        ttk.Button(playback_frame, text="⏪ Prev", command=self.prev_frame).pack(side=tk.LEFT, padx=5)
        ttk.Button(playback_frame, text="⏩ Next", command=self.next_frame).pack(side=tk.LEFT, padx=5)
        ttk.Button(playback_frame, text="⏭ Last", command=self.last_frame).pack(side=tk.LEFT, padx=5)
        
        # Frame jump
        jump_frame = ttk.Frame(playback_frame)
        jump_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(jump_frame, text="Jump to:").pack(side=tk.LEFT, padx=2)
        self.frame_jump_entry = ttk.Entry(jump_frame, width=10)
        self.frame_jump_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(jump_frame, text="Go", command=self.jump_to_frame).pack(side=tk.LEFT, padx=2)
        
        # Frame info
        self.frame_label = ttk.Label(playback_frame, text="Frame: 0/0 (0:00)")
        self.frame_label.pack(side=tk.LEFT, padx=10)
        
        # Speed control
        speed_frame = ttk.Frame(playback_frame)
        speed_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(speed_frame, text="Speed:").pack(side=tk.LEFT, padx=2)
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_scale = ttk.Scale(speed_frame, from_=0.25, to=2.0, variable=self.speed_var, 
                               orient=tk.HORIZONTAL, length=100, command=self.on_speed_change)
        speed_scale.pack(side=tk.LEFT, padx=2)
        self.speed_label = ttk.Label(speed_frame, text="1.0x")
        self.speed_label.pack(side=tk.LEFT, padx=2)
        
        # Canvas frame (shared)
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Main canvas
        self.canvas = tk.Canvas(canvas_frame, bg="black", width=800, height=500)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        
        # Preview panel (right side)
        preview_frame = ttk.LabelFrame(canvas_frame, text="Color Preview", padding="5")
        preview_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        
        # Zoomed area (larger for better color selection)
        zoom_label_frame = ttk.Frame(preview_frame)
        zoom_label_frame.pack(pady=5)
        ttk.Label(zoom_label_frame, text="Zoomed Area:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        ttk.Label(zoom_label_frame, text="(Click main video, then use arrow keys)", font=("Arial", 7), foreground="gray").pack(side=tk.LEFT, padx=5)
        self.zoom_canvas = tk.Canvas(preview_frame, bg="black", width=300, height=300, 
                                     highlightthickness=2, highlightbackground="yellow")
        self.zoom_canvas.pack(pady=5)
        # Bind click to both sample color and focus
        def on_zoom_click(event):
            self.zoom_canvas.focus_set()
            self.on_zoom_canvas_click(event)
        self.zoom_canvas.bind("<Button-1>", on_zoom_click)
        self.zoom_canvas.focus_set()  # Allow keyboard focus
        # Bind arrow keys to zoom canvas specifically
        self.zoom_canvas.bind("<Up>", self.on_zoom_key)
        self.zoom_canvas.bind("<Down>", self.on_zoom_key)
        self.zoom_canvas.bind("<Left>", self.on_zoom_key)
        self.zoom_canvas.bind("<Right>", self.on_zoom_key)
        self.zoom_canvas.bind("<Return>", self.on_zoom_key)
        
        # Color swatches (will be updated based on tab)
        self.swatch_frame = ttk.Frame(preview_frame)
        self.swatch_frame.pack(pady=5)
        
        # HSV display (current cursor position)
        self.hsv_display_label = ttk.Label(preview_frame, text="HSV: Not sampled", 
                                          font=("Arial", 8), wraplength=150)
        self.hsv_display_label.pack(pady=5)
        
        # Selected color range display (will be updated based on tab)
        self.range_display_frame = ttk.LabelFrame(preview_frame, text="Selected Color Range", padding="5")
        self.range_display_frame.pack(pady=5, fill=tk.X)
        
        # Ball color tab content
        self.setup_ball_tab(ball_tab)
        
        # Team color tab content
        self.setup_team_tab(team_tab)
        
        # Status bar
        self.status_label = ttk.Label(main_frame, text="Load a video to start", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X, pady=5)
    
    def setup_ball_tab(self, tab):
        """Setup ball color tab"""
        # Instructions
        instructions = ttk.Label(
            tab,
            text="1. Load video and navigate to a frame with the ball visible\n"
                 "2. Click on the ball in the main video to zoom in\n"
                 "3. Use arrow keys in zoomed area to fine-tune selection\n"
                 "4. Click in zoomed area or press Enter to confirm\n"
                 "5. Adjust HSV ranges if needed",
            justify=tk.LEFT
        )
        instructions.pack(pady=5)
        
        # Color selection
        color_frame = ttk.LabelFrame(tab, text="Ball Color Selection", padding="10")
        color_frame.pack(fill=tk.X, pady=5)
        
        # Color 1
        color1_frame = ttk.Frame(color_frame)
        color1_frame.pack(fill=tk.X, pady=5)
        ttk.Label(color1_frame, text="Color 1 (Primary):", width=15).pack(side=tk.LEFT)
        self.ball_color1_entry = ttk.Entry(color1_frame, width=30)
        self.ball_color1_entry.pack(side=tk.LEFT, padx=5)
        self.ball_color1_entry.insert(0, "White")
        ttk.Button(color1_frame, text="Sample", command=lambda: self.set_ball_color_mode("color1")).pack(side=tk.LEFT, padx=5)
        
        # Color 2
        color2_frame = ttk.Frame(color_frame)
        color2_frame.pack(fill=tk.X, pady=5)
        ttk.Label(color2_frame, text="Color 2 (Secondary):", width=15).pack(side=tk.LEFT)
        self.ball_color2_entry = ttk.Entry(color2_frame, width=30)
        self.ball_color2_entry.pack(side=tk.LEFT, padx=5)
        self.ball_color2_entry.insert(0, "Red")
        ttk.Button(color2_frame, text="Sample", command=lambda: self.set_ball_color_mode("color2")).pack(side=tk.LEFT, padx=5)
        
        # HSV display
        hsv_frame = ttk.LabelFrame(tab, text="HSV Ranges", padding="10")
        hsv_frame.pack(fill=tk.X, pady=5)
        
        color1_display_frame = ttk.Frame(hsv_frame)
        color1_display_frame.pack(fill=tk.X, pady=5)
        self.ball_color1_hsv_label = ttk.Label(color1_display_frame, text="Color 1 HSV: Not set")
        self.ball_color1_hsv_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(color1_display_frame, text="Fine-tune", command=lambda: self.open_finetune_window("ball", "color1")).pack(side=tk.LEFT, padx=5)
        ttk.Button(color1_display_frame, text="Clear", command=lambda: self.clear_color("ball", "color1")).pack(side=tk.LEFT, padx=2)
        self.ball_undo1_button = ttk.Button(color1_display_frame, text="Undo", command=lambda: self.undo_color("ball", "color1"), state=tk.DISABLED)
        self.ball_undo1_button.pack(side=tk.LEFT, padx=2)
        
        color2_display_frame = ttk.Frame(hsv_frame)
        color2_display_frame.pack(fill=tk.X, pady=5)
        self.ball_color2_hsv_label = ttk.Label(color2_display_frame, text="Color 2 HSV: Not set")
        self.ball_color2_hsv_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(color2_display_frame, text="Fine-tune", command=lambda: self.open_finetune_window("ball", "color2")).pack(side=tk.LEFT, padx=5)
        ttk.Button(color2_display_frame, text="Clear", command=lambda: self.clear_color("ball", "color2")).pack(side=tk.LEFT, padx=2)
        self.ball_undo2_button = ttk.Button(color2_display_frame, text="Undo", command=lambda: self.undo_color("ball", "color2"), state=tk.DISABLED)
        self.ball_undo2_button.pack(side=tk.LEFT, padx=2)
        
        # Presets
        preset_frame = ttk.Frame(tab)
        preset_frame.pack(fill=tk.X, pady=5)
        ttk.Label(preset_frame, text="Preset:").pack(side=tk.LEFT, padx=5)
        self.ball_preset_var = tk.StringVar()
        self.ball_preset_combo = ttk.Combobox(preset_frame, textvariable=self.ball_preset_var, width=20)
        self.ball_preset_combo.pack(side=tk.LEFT, padx=5)
        self.ball_preset_combo.bind("<<ComboboxSelected>>", lambda e: self.load_preset("ball"))
        ttk.Button(preset_frame, text="Save Preset", command=lambda: self.save_preset("ball")).pack(side=tk.LEFT, padx=5)
        ttk.Button(preset_frame, text="Delete Preset", command=lambda: self.delete_preset("ball")).pack(side=tk.LEFT, padx=5)
        
        # Apply button
        ttk.Button(tab, text="Apply Ball Colors to Analysis", command=self.apply_ball_colors).pack(pady=10)
    
    def setup_team_tab(self, tab):
        """Setup team color tab"""
        # Instructions
        instructions = ttk.Label(
            tab,
            text="1. Load video and navigate to a frame with players visible\n"
                 "2. Click on team jerseys in the main video to zoom in\n"
                 "3. Use arrow keys in zoomed area to fine-tune selection\n"
                 "4. Click in zoomed area or press Enter to confirm\n"
                 "5. Adjust HSV ranges if needed",
            justify=tk.LEFT
        )
        instructions.pack(pady=5)
        
        # Team selection
        team_frame = ttk.LabelFrame(tab, text="Team Color Sampling", padding="10")
        team_frame.pack(fill=tk.X, pady=5)
        
        # Team 1
        team1_frame = ttk.Frame(team_frame)
        team1_frame.pack(fill=tk.X, pady=5)
        ttk.Label(team1_frame, text="Team 1 Name:").pack(side=tk.LEFT, padx=5)
        self.team1_entry = ttk.Entry(team1_frame, width=20)
        self.team1_entry.insert(0, "Team 1")
        self.team1_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(team1_frame, text="Sample Team 1", command=lambda: self.set_team_mode("team1")).pack(side=tk.LEFT, padx=5)
        ttk.Button(team1_frame, text="Fine-tune", command=lambda: self.open_finetune_window("team", "team1")).pack(side=tk.LEFT, padx=2)
        ttk.Button(team1_frame, text="Clear", command=lambda: self.clear_color("team", "team1")).pack(side=tk.LEFT, padx=2)
        self.team_undo1_button = ttk.Button(team1_frame, text="Undo", command=lambda: self.undo_color("team", "team1"), state=tk.DISABLED)
        self.team_undo1_button.pack(side=tk.LEFT, padx=2)
        self.team1_hsv_label = ttk.Label(team_frame, text="Team 1 HSV: Not sampled")
        self.team1_hsv_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # Team 2
        team2_frame = ttk.Frame(team_frame)
        team2_frame.pack(fill=tk.X, pady=5)
        ttk.Label(team2_frame, text="Team 2 Name:").pack(side=tk.LEFT, padx=5)
        self.team2_entry = ttk.Entry(team2_frame, width=20)
        self.team2_entry.insert(0, "Team 2")
        self.team2_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(team2_frame, text="Sample Team 2", command=lambda: self.set_team_mode("team2")).pack(side=tk.LEFT, padx=5)
        ttk.Button(team2_frame, text="Fine-tune", command=lambda: self.open_finetune_window("team", "team2")).pack(side=tk.LEFT, padx=2)
        ttk.Button(team2_frame, text="Clear", command=lambda: self.clear_color("team", "team2")).pack(side=tk.LEFT, padx=2)
        self.team_undo2_button = ttk.Button(team2_frame, text="Undo", command=lambda: self.undo_color("team", "team2"), state=tk.DISABLED)
        self.team_undo2_button.pack(side=tk.LEFT, padx=2)
        self.team2_hsv_label = ttk.Label(team_frame, text="Team 2 HSV: Not sampled")
        self.team2_hsv_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # Presets
        preset_frame = ttk.LabelFrame(tab, text="Presets", padding="10")
        preset_frame.pack(fill=tk.X, pady=5)
        ttk.Button(preset_frame, text="Save Current as Preset", command=lambda: self.save_preset("team")).grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(preset_frame, text="Load Preset:").grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.team_preset_combobox = ttk.Combobox(preset_frame, state="readonly")
        self.team_preset_combobox.grid(row=0, column=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.team_preset_combobox.bind("<<ComboboxSelected>>", lambda e: self.load_preset("team"))
        
        # Apply button
        ttk.Button(tab, text="Apply Team Colors to Analysis", command=self.apply_team_colors).pack(pady=10)
    
    def on_tab_change(self, event):
        """Handle tab change"""
        notebook = event.widget
        selected = notebook.index(notebook.select())
        if selected == 0:
            self.current_mode = "ball"
        else:
            self.current_mode = "team"
        self.update_swatches()
        self.update_display()
    
    def update_swatches(self):
        """Update color swatches based on current mode"""
        # Clear existing swatches
        for widget in self.swatch_frame.winfo_children():
            widget.destroy()
        
        # Clear range display
        for widget in self.range_display_frame.winfo_children():
            widget.destroy()
        
        if self.current_mode == "ball":
            # Color 1 swatch
            color1_label = ttk.Label(self.swatch_frame, text="Color 1:", font=("Arial", 9, "bold"))
            color1_label.grid(row=0, column=0, pady=5, padx=5, sticky=tk.W)
            self.ball_color1_swatch = tk.Canvas(self.swatch_frame, bg="gray", width=120, height=50, 
                                               highlightthickness=2, highlightbackground="black")
            self.ball_color1_swatch.grid(row=0, column=1, pady=5, padx=5)
            
            # Color 2 swatch
            color2_label = ttk.Label(self.swatch_frame, text="Color 2:", font=("Arial", 9, "bold"))
            color2_label.grid(row=1, column=0, pady=5, padx=5, sticky=tk.W)
            self.ball_color2_swatch = tk.Canvas(self.swatch_frame, bg="gray", width=120, height=50,
                                               highlightthickness=2, highlightbackground="black")
            self.ball_color2_swatch.grid(row=1, column=1, pady=5, padx=5)
            
            self.update_ball_swatches()
        else:
            # Team 1 swatch
            team1_label = ttk.Label(self.swatch_frame, text="Team 1:", font=("Arial", 9, "bold"))
            team1_label.grid(row=0, column=0, pady=5, padx=5, sticky=tk.W)
            self.team1_swatch = tk.Canvas(self.swatch_frame, bg="gray", width=120, height=50,
                                         highlightthickness=2, highlightbackground="black")
            self.team1_swatch.grid(row=0, column=1, pady=5, padx=5)
            
            # Team 2 swatch
            team2_label = ttk.Label(self.swatch_frame, text="Team 2:", font=("Arial", 9, "bold"))
            team2_label.grid(row=1, column=0, pady=5, padx=5, sticky=tk.W)
            self.team2_swatch = tk.Canvas(self.swatch_frame, bg="gray", width=120, height=50,
                                         highlightthickness=2, highlightbackground="black")
            self.team2_swatch.grid(row=1, column=1, pady=5, padx=5)
            
            self.update_team_swatches()
    
    def browse_video(self):
        """Browse for video file"""
        filename = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v *.mpg *.mpeg"), ("All files", "*.*")]
        )
        if filename:
            self.video_path = filename
            self.video_path_entry.delete(0, tk.END)
            self.video_path_entry.insert(0, filename)
            self.load_video()
    
    def load_video(self):
        """Load video file"""
        if self.cap:
            self.cap.release()
        
        if not self.video_path or not os.path.exists(self.video_path):
            messagebox.showerror("Error", "Please select a valid video file")
            return
        
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            messagebox.showerror("Error", f"Could not open video file: {self.video_path}")
            return
        
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.current_frame_num = 0
        self.display_frame()
        self.status_label.config(text=f"Video loaded: {os.path.basename(self.video_path)} ({self.total_frames} frames @ {self.fps:.1f}fps)")
    
    def toggle_playback(self):
        """Toggle video playback"""
        if not self.cap or not self.cap.isOpened():
            messagebox.showwarning("Warning", "Please load a video first")
            return
        
        if self.is_playing:
            self.is_playing = False
            self.play_button.config(text="▶ Play")
        else:
            self.is_playing = True
            self.play_button.config(text="⏸ Pause")
            self.start_playback()
    
    def start_playback(self):
        """Start playback thread"""
        if self.play_thread and self.play_thread.is_alive():
            return
        
        def play_loop():
            while self.is_playing and self.cap and self.cap.isOpened():
                if self.current_frame_num >= self.total_frames - 1:
                    self.is_playing = False
                    self.root.after(0, lambda: self.play_button.config(text="▶ Play"))
                    break
                
                self.current_frame_num += 1
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_num)
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame.copy()
                    self.hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    self.root.after(0, self.update_display)
                
                # Control playback speed
                delay = (1.0 / self.fps) / self.play_speed
                time.sleep(delay)
        
        self.play_thread = threading.Thread(target=play_loop, daemon=True)
        self.play_thread.start()
    
    def on_speed_change(self, value):
        """Handle speed slider change"""
        self.play_speed = float(value)
        self.speed_label.config(text=f"{self.play_speed:.2f}x")
    
    def first_frame(self):
        """Jump to first frame"""
        self.is_playing = False
        self.play_button.config(text="▶ Play")
        self.current_frame_num = 0
        self.display_frame()
    
    def last_frame(self):
        """Jump to last frame"""
        self.is_playing = False
        self.play_button.config(text="▶ Play")
        self.current_frame_num = max(0, self.total_frames - 1)
        self.display_frame()
    
    def prev_frame(self):
        """Go to previous frame"""
        self.is_playing = False
        self.play_button.config(text="▶ Play")
        if self.current_frame_num > 0:
            self.current_frame_num -= 1
            self.display_frame()
    
    def next_frame(self):
        """Go to next frame"""
        self.is_playing = False
        self.play_button.config(text="▶ Play")
        if self.current_frame_num < self.total_frames - 1:
            self.current_frame_num += 1
            self.display_frame()
    
    def jump_to_frame(self):
        """Jump to specific frame number"""
        try:
            frame_num = int(self.frame_jump_entry.get())
            if 0 <= frame_num < self.total_frames:
                self.is_playing = False
                self.play_button.config(text="▶ Play")
                self.current_frame_num = frame_num
                self.display_frame()
            else:
                messagebox.showwarning("Warning", f"Frame number must be between 0 and {self.total_frames - 1}")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid frame number")
    
    def display_frame(self):
        """Display current frame"""
        if not self.cap or not self.cap.isOpened():
            return
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_num)
        ret, frame = self.cap.read()
        if not ret:
            return
        
        self.current_frame = frame.copy()
        self.hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        self.update_display()
    
    def update_display(self):
        """Update canvas display"""
        if self.current_frame is None:
            return
        
        display_frame = self.current_frame.copy()
        
        # Draw HSV masks for visualization
        if self.current_mode == "ball":
            # Draw ball color masks
            for color_key in ["color1", "color2"]:
                if self.ball_hsv_ranges[color_key]:
                    mask = self.create_mask(self.hsv_frame, self.ball_hsv_ranges[color_key])
                    if mask is not None and mask.size > 0:
                        color = (0, 255, 0) if color_key == "color1" else (255, 0, 0)
                        # Create overlay properly
                        overlay = display_frame.copy()
                        overlay[mask > 0] = color
                        display_frame = cv2.addWeighted(display_frame, 0.7, overlay, 0.3, 0)
        else:
            # Draw team color masks
            for team_key in ["team1", "team2"]:
                if self.team_colors[team_key]["hsv_ranges"]:
                    mask = self.create_mask(self.hsv_frame, self.team_colors[team_key]["hsv_ranges"])
                    if mask is not None and mask.size > 0:
                        color = (0, 0, 255) if team_key == "team1" else (255, 0, 0)
                        # Create overlay properly
                        overlay = display_frame.copy()
                        overlay[mask > 0] = color
                        display_frame = cv2.addWeighted(display_frame, 0.7, overlay, 0.3, 0)
        
        # Resize for display
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width > 1 and canvas_height > 1:
            h, w = display_frame.shape[:2]
            scale = min(canvas_width / w, canvas_height / h)
            new_w, new_h = int(w * scale), int(h * scale)
            display_frame = cv2.resize(display_frame, (new_w, new_h))
        
        # Convert to PhotoImage and display
        if PIL_AVAILABLE:
            display_frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(display_frame_rgb)
            self.photo = ImageTk.PhotoImage(image=img)
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.photo, anchor=tk.CENTER)
        else:
            # Fallback without PIL
            self.canvas.delete("all")
            # Would need to use cv2.imencode or similar
        
        # Update frame label
        time_seconds = self.current_frame_num / self.fps if self.fps > 0 else 0
        minutes = int(time_seconds // 60)
        seconds = int(time_seconds % 60)
        self.frame_label.config(text=f"Frame: {self.current_frame_num}/{self.total_frames - 1} ({minutes}:{seconds:02d})")
        
        # Update zoom preview if in fine-tuning mode
        if self.fine_tuning_mode and self.zoom_region_original is not None:
            self.show_zoom_preview()
    
    def create_mask(self, hsv_frame, hsv_ranges):
        """Create mask from HSV ranges"""
        if hsv_ranges is None:
            return None
        
        if isinstance(hsv_ranges, dict):
            if "lower" in hsv_ranges and "upper" in hsv_ranges:
                # Ensure proper numpy array with correct dtype
                lower = np.array(hsv_ranges["lower"], dtype=np.uint8)
                upper = np.array(hsv_ranges["upper"], dtype=np.uint8)
                return cv2.inRange(hsv_frame, lower, upper)
            elif "lower1" in hsv_ranges:  # Red color (two ranges)
                lower1 = np.array(hsv_ranges["lower1"], dtype=np.uint8)
                upper1 = np.array(hsv_ranges["upper1"], dtype=np.uint8)
                lower2 = np.array(hsv_ranges["lower2"], dtype=np.uint8)
                upper2 = np.array(hsv_ranges["upper2"], dtype=np.uint8)
                mask1 = cv2.inRange(hsv_frame, lower1, upper1)
                mask2 = cv2.inRange(hsv_frame, lower2, upper2)
                return cv2.bitwise_or(mask1, mask2)
        return None
    
    # Placeholder methods - these would need full implementation from original files
    def set_ball_color_mode(self, color_key):
        """Set ball color sampling mode"""
        self.current_mode = "ball"
        self.status_label.config(text=f"Click on {self.ball_color_names[color_key]} part of the ball")
        # Store which color we're sampling
        self.sampling_color = ("ball", color_key)
    
    def set_team_mode(self, team_key):
        """Set team color sampling mode"""
        self.current_mode = "team"
        self.current_team = team_key
        self.status_label.config(text=f"Click on {self.team_colors[team_key]['name']} jersey")
        self.sampling_color = ("team", team_key)
    
    def on_canvas_click(self, event):
        """Handle canvas click for color sampling and zoom"""
        if self.current_frame is None or self.hsv_frame is None:
            return
        
        # Get click position
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # Convert to frame coordinates
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            return
        
        h, w = self.current_frame.shape[:2]
        scale = min(canvas_width / w, canvas_height / h)
        display_w, display_h = int(w * scale), int(h * scale)
        offset_x = (canvas_width - display_w) // 2
        offset_y = (canvas_height - display_h) // 2
        
        frame_x = int((canvas_x - offset_x) / scale)
        frame_y = int((canvas_y - offset_y) / scale)
        
        if 0 <= frame_x < w and 0 <= frame_y < h:
            # Extract zoom region around click point
            region_size = self.zoom_region_size
            x1 = max(0, frame_x - region_size // 2)
            y1 = max(0, frame_y - region_size // 2)
            x2 = min(w, frame_x + region_size // 2)
            y2 = min(h, frame_y + region_size // 2)
            
            # Extract regions
            self.zoom_region = self.hsv_frame[y1:y2, x1:x2].copy()
            self.zoom_region_original = self.current_frame[y1:y2, x1:x2].copy()
            self.original_click_pos = (frame_x, frame_y)
            
            # Initialize selector at center of zoom region (relative to region)
            zoom_h, zoom_w = self.zoom_region.shape[:2]
            self.selector_pos = (zoom_w // 2, zoom_h // 2)
            self.fine_tuning_mode = True
            
            # Show zoom preview
            self.show_zoom_preview()
            
            # Focus zoom canvas for keyboard input
            self.zoom_canvas.focus_set()
            self.zoom_canvas.configure(highlightbackground="yellow", highlightthickness=2)
            
            # Sample color from center of zoom region
            center_x = frame_x
            center_y = frame_y
            hsv_value = self.hsv_frame[center_y, center_x]
            self.sample_color(hsv_value, center_x, center_y)
            
            # Draw marker on main canvas
            display_x = int((frame_x * scale) + offset_x)
            display_y = int((frame_y * scale) + offset_y)
            self.canvas.create_oval(display_x - 5, display_y - 5, display_x + 5, display_y + 5,
                                  outline="yellow", width=2, tags="marker")
    
    def sample_color(self, hsv_value, x, y):
        """Sample color at position"""
        if not hasattr(self, 'sampling_color'):
            return
        
        mode, color_key = self.sampling_color
        
        if mode == "ball":
            # Sample ball color
            hsv_ranges = self.calculate_hsv_ranges(hsv_value)
            self.ball_hsv_ranges[color_key] = hsv_ranges
            self.ball_history[color_key].append(copy.deepcopy(hsv_ranges))
            if len(self.ball_history[color_key]) > self.max_history:
                self.ball_history[color_key].pop(0)
            if self.ball_original_sampled[color_key] is None:
                self.ball_original_sampled[color_key] = copy.deepcopy(hsv_ranges)
            
            # Update display
            self.update_ball_hsv_label(color_key)
            self.update_ball_swatches()
            self.status_label.config(text=f"Sampled {self.ball_color_names[color_key]} at ({x}, {y})")
        else:
            # Sample team color
            hsv_ranges = self.calculate_hsv_ranges(hsv_value)
            self.team_colors[color_key]["hsv_ranges"] = hsv_ranges
            self.team_history[color_key].append(copy.deepcopy(hsv_ranges))
            if len(self.team_history[color_key]) > self.max_history:
                self.team_history[color_key].pop(0)
            if self.team_original_sampled[color_key] is None:
                self.team_original_sampled[color_key] = copy.deepcopy(hsv_ranges)
            
            # Update display
            self.update_team_hsv_label(color_key)
            self.update_team_swatches()
            self.status_label.config(text=f"Sampled {self.team_colors[color_key]['name']} at ({x}, {y})")
        
        self.update_display()
    
    def calculate_hsv_ranges(self, hsv_value):
        """Calculate HSV ranges from sampled value"""
        # Convert to Python int to avoid overflow warnings
        h = int(hsv_value[0])
        s = int(hsv_value[1])
        v = int(hsv_value[2])
        
        # Clamp values to valid HSV ranges
        h = max(0, min(180, h))
        s = max(0, min(255, s))
        v = max(0, min(255, v))
        
        # Handle red (wraps around 0/180)
        if h < 10 or h > 170:
            return {
                "lower1": [0, max(0, s - 30), max(0, v - 30)],
                "upper1": [10, 255, 255],
                "lower2": [170, max(0, s - 30), max(0, v - 30)],
                "upper2": [180, 255, 255]
            }
        else:
            return {
                "lower": [max(0, h - 10), max(0, s - 30), max(0, v - 30)],
                "upper": [min(180, h + 10), 255, 255]
            }
    
    def update_ball_hsv_label(self, color_key):
        """Update ball HSV label"""
        ranges = self.ball_hsv_ranges[color_key]
        if ranges:
            if "lower" in ranges:
                label_text = f"Color {color_key[-1]} HSV: Lower={ranges['lower']}, Upper={ranges['upper']}"
            else:
                label_text = f"Color {color_key[-1]} HSV: Red (two ranges)"
            
            if color_key == "color1":
                self.ball_color1_hsv_label.config(text=label_text)
            else:
                self.ball_color2_hsv_label.config(text=label_text)
        
        # Also update range display
        self.update_ball_range_display()
    
    def update_team_hsv_label(self, team_key):
        """Update team HSV label"""
        ranges = self.team_colors[team_key]["hsv_ranges"]
        if ranges:
            if "lower" in ranges:
                label_text = f"{self.team_colors[team_key]['name']} HSV: Lower={ranges['lower']}, Upper={ranges['upper']}"
            else:
                label_text = f"{self.team_colors[team_key]['name']} HSV: Red (two ranges)"
            
            if team_key == "team1":
                self.team1_hsv_label.config(text=label_text)
            else:
                self.team2_hsv_label.config(text=label_text)
        
        # Also update range display
        self.update_team_range_display()
    
    def update_ball_swatches(self):
        """Update ball color swatches and range display"""
        # Update Color 1
        if hasattr(self, 'ball_color1_swatch'):
            if self.ball_hsv_ranges["color1"]:
                # Get average color from range
                color = self.get_average_color_from_range(self.ball_hsv_ranges["color1"])
                color_hex = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                self.ball_color1_swatch.config(bg=color_hex)
                self.ball_color1_swatch.delete("all")
                # Draw color name on swatch
                self.ball_color1_swatch.create_text(60, 25, text=self.ball_color1_entry.get()[:10], 
                                                    fill="white" if sum(color) < 400 else "black",
                                                    font=("Arial", 8, "bold"))
            else:
                self.ball_color1_swatch.config(bg="gray")
                self.ball_color1_swatch.delete("all")
        
        # Update Color 2
        if hasattr(self, 'ball_color2_swatch'):
            if self.ball_hsv_ranges["color2"]:
                color = self.get_average_color_from_range(self.ball_hsv_ranges["color2"])
                color_hex = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                self.ball_color2_swatch.config(bg=color_hex)
                self.ball_color2_swatch.delete("all")
                # Draw color name on swatch
                self.ball_color2_swatch.create_text(60, 25, text=self.ball_color2_entry.get()[:10],
                                                    fill="white" if sum(color) < 400 else "black",
                                                    font=("Arial", 8, "bold"))
            else:
                self.ball_color2_swatch.config(bg="gray")
                self.ball_color2_swatch.delete("all")
        
        # Update range display
        self.update_ball_range_display()
    
    def update_team_swatches(self):
        """Update team color swatches and range display"""
        # Update Team 1
        if hasattr(self, 'team1_swatch'):
            if self.team_colors["team1"]["hsv_ranges"]:
                color = self.get_average_color_from_range(self.team_colors["team1"]["hsv_ranges"])
                color_hex = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                self.team1_swatch.config(bg=color_hex)
                self.team1_swatch.delete("all")
                # Draw team name on swatch
                team1_name = self.team1_entry.get()[:10]
                self.team1_swatch.create_text(60, 25, text=team1_name,
                                             fill="white" if sum(color) < 400 else "black",
                                             font=("Arial", 8, "bold"))
            else:
                self.team1_swatch.config(bg="gray")
                self.team1_swatch.delete("all")
        
        # Update Team 2
        if hasattr(self, 'team2_swatch'):
            if self.team_colors["team2"]["hsv_ranges"]:
                color = self.get_average_color_from_range(self.team_colors["team2"]["hsv_ranges"])
                color_hex = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                self.team2_swatch.config(bg=color_hex)
                self.team2_swatch.delete("all")
                # Draw team name on swatch
                team2_name = self.team2_entry.get()[:10]
                self.team2_swatch.create_text(60, 25, text=team2_name,
                                             fill="white" if sum(color) < 400 else "black",
                                             font=("Arial", 8, "bold"))
            else:
                self.team2_swatch.config(bg="gray")
                self.team2_swatch.delete("all")
        
        # Update range display
        self.update_team_range_display()
    
    def get_average_color_from_range(self, hsv_ranges):
        """Get average RGB color from HSV range"""
        if "lower" in hsv_ranges:
            h = int((hsv_ranges["lower"][0] + hsv_ranges["upper"][0]) / 2)
            s = int((hsv_ranges["lower"][1] + hsv_ranges["upper"][1]) / 2)
            v = int((hsv_ranges["lower"][2] + hsv_ranges["upper"][2]) / 2)
        else:
            h = int((hsv_ranges["lower1"][0] + hsv_ranges["upper1"][0]) / 2)
            s = int((hsv_ranges["lower1"][1] + hsv_ranges["upper1"][1]) / 2)
            v = int((hsv_ranges["lower1"][2] + hsv_ranges["upper1"][2]) / 2)
        
        # Clamp to valid ranges
        h = max(0, min(180, h))
        s = max(0, min(255, s))
        v = max(0, min(255, v))
        
        hsv = np.uint8([[[h, s, v]]])
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        return tuple(map(int, bgr[0][0]))
    
    def update_ball_range_display(self):
        """Update the HSV range display for ball colors"""
        # Clear existing widgets
        for widget in self.range_display_frame.winfo_children():
            widget.destroy()
        
        if self.current_mode != "ball":
            return
        
        # Show Color 1 range
        if self.ball_hsv_ranges["color1"]:
            color1_name = self.ball_color1_entry.get()
            ranges = self.ball_hsv_ranges["color1"]
            self.create_range_display(self.range_display_frame, f"Color 1 ({color1_name})", ranges, 0)
        
        # Show Color 2 range
        if self.ball_hsv_ranges["color2"]:
            color2_name = self.ball_color2_entry.get()
            ranges = self.ball_hsv_ranges["color2"]
            row = 1 if self.ball_hsv_ranges["color1"] else 0
            self.create_range_display(self.range_display_frame, f"Color 2 ({color2_name})", ranges, row)
        
        if not self.ball_hsv_ranges["color1"] and not self.ball_hsv_ranges["color2"]:
            ttk.Label(self.range_display_frame, text="No colors sampled yet", 
                     font=("Arial", 8), foreground="gray").pack(pady=5)
    
    def update_team_range_display(self):
        """Update the HSV range display for team colors"""
        # Clear existing widgets
        for widget in self.range_display_frame.winfo_children():
            widget.destroy()
        
        if self.current_mode != "team":
            return
        
        # Show Team 1 range
        if self.team_colors["team1"]["hsv_ranges"]:
            team1_name = self.team1_entry.get()
            ranges = self.team_colors["team1"]["hsv_ranges"]
            self.create_range_display(self.range_display_frame, f"Team 1 ({team1_name})", ranges, 0)
        
        # Show Team 2 range
        if self.team_colors["team2"]["hsv_ranges"]:
            team2_name = self.team2_entry.get()
            ranges = self.team_colors["team2"]["hsv_ranges"]
            row = 1 if self.team_colors["team1"]["hsv_ranges"] else 0
            self.create_range_display(self.range_display_frame, f"Team 2 ({team2_name})", ranges, row)
        
        if not self.team_colors["team1"]["hsv_ranges"] and not self.team_colors["team2"]["hsv_ranges"]:
            ttk.Label(self.range_display_frame, text="No team colors sampled yet", 
                     font=("Arial", 8), foreground="gray").pack(pady=5)
    
    def create_range_display(self, parent, title, ranges, row):
        """Create a formatted display of HSV ranges"""
        if not ranges:
            return
        
        # Title
        title_label = ttk.Label(parent, text=title, font=("Arial", 9, "bold"))
        title_label.grid(row=row*3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        
        if "lower2" in ranges:
            # Two-range color (red)
            range1_text = f"Range 1: H[{ranges['lower1'][0]}-{ranges['upper1'][0]}], " \
                         f"S[{ranges['lower1'][1]}-{ranges['upper1'][1]}], " \
                         f"V[{ranges['lower1'][2]}-{ranges['upper1'][2]}]"
            range2_text = f"Range 2: H[{ranges['lower2'][0]}-{ranges['upper2'][0]}], " \
                         f"S[{ranges['lower2'][1]}-{ranges['upper2'][1]}], " \
                         f"V[{ranges['lower2'][2]}-{ranges['upper2'][2]}]"
            
            ttk.Label(parent, text=range1_text, font=("Arial", 8)).grid(row=row*3+1, column=0, columnspan=2, 
                                                                       sticky=tk.W, padx=15, pady=1)
            ttk.Label(parent, text=range2_text, font=("Arial", 8)).grid(row=row*3+2, column=0, columnspan=2, 
                                                                       sticky=tk.W, padx=15, pady=1)
        else:
            # Single range
            range_text = f"H[{ranges['lower'][0]}-{ranges['upper'][0]}], " \
                        f"S[{ranges['lower'][1]}-{ranges['upper'][1]}], " \
                        f"V[{ranges['lower'][2]}-{ranges['upper'][2]}]"
            ttk.Label(parent, text=range_text, font=("Arial", 8)).grid(row=row*3+1, column=0, columnspan=2, 
                                                                      sticky=tk.W, padx=15, pady=2)
    
    def show_zoom_preview(self):
        """Display zoomed region with selector"""
        if self.zoom_region_original is None or self.selector_pos is None:
            return
        
        # Create display version of zoom region
        zoom_display = self.zoom_region_original.copy()
        
        # Draw selector crosshair
        sel_x, sel_y = self.selector_pos
        cv2.line(zoom_display, (sel_x - 10, sel_y), (sel_x + 10, sel_y), (0, 255, 255), 2)
        cv2.line(zoom_display, (sel_x, sel_y - 10), (sel_x, sel_y + 10), (0, 255, 255), 2)
        cv2.circle(zoom_display, (sel_x, sel_y), 5, (0, 255, 255), 2)
        
        # Resize to fit zoom canvas (300x300)
        zoom_h, zoom_w = zoom_display.shape[:2]
        zoom_scale = min(300 / zoom_w, 300 / zoom_h)
        new_zoom_w = int(zoom_w * zoom_scale)
        new_zoom_h = int(zoom_h * zoom_scale)
        zoom_display = cv2.resize(zoom_display, (new_zoom_w, new_zoom_h))
        
        # Convert to RGB and display
        if PIL_AVAILABLE:
            zoom_display_rgb = cv2.cvtColor(zoom_display, cv2.COLOR_BGR2RGB)
            zoom_img = Image.fromarray(zoom_display_rgb)
            self.zoom_photo = ImageTk.PhotoImage(image=zoom_img)
            self.zoom_canvas.delete("all")
            # Center the image
            canvas_w = self.zoom_canvas.winfo_width()
            canvas_h = self.zoom_canvas.winfo_height()
            if canvas_w > 1 and canvas_h > 1:
                x_pos = (canvas_w - new_zoom_w) // 2
                y_pos = (canvas_h - new_zoom_h) // 2
                self.zoom_canvas.create_image(x_pos, y_pos, anchor=tk.NW, image=self.zoom_photo)
        
        # Update HSV display
        if self.zoom_region is not None and 0 <= sel_y < self.zoom_region.shape[0] and 0 <= sel_x < self.zoom_region.shape[1]:
            hsv_value = self.zoom_region[sel_y, sel_x]
            h, s, v = int(hsv_value[0]), int(hsv_value[1]), int(hsv_value[2])
            self.hsv_display_label.config(text=f"HSV: H={h}, S={s}, V={v}")
    
    def on_zoom_canvas_click(self, event):
        """Handle click on zoom canvas to sample color"""
        if self.zoom_region is None or self.original_click_pos is None:
            return
        
        # Convert canvas click to zoom region coordinates
        canvas_w = self.zoom_canvas.winfo_width()
        canvas_h = self.zoom_canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            return
        
        zoom_h, zoom_w = self.zoom_region.shape[:2]
        zoom_scale = min(300 / zoom_w, 300 / zoom_h)
        new_zoom_w = int(zoom_w * zoom_scale)
        new_zoom_h = int(zoom_h * zoom_scale)
        
        # Calculate position in zoom canvas
        x_pos = (canvas_w - new_zoom_w) // 2
        y_pos = (canvas_h - new_zoom_h) // 2
        
        # Convert to zoom region coordinates
        zoom_x = int((event.x - x_pos) / zoom_scale)
        zoom_y = int((event.y - y_pos) / zoom_scale)
        
        if 0 <= zoom_x < zoom_w and 0 <= zoom_y < zoom_h:
            self.selector_pos = (zoom_x, zoom_y)
            hsv_value = self.zoom_region[zoom_y, zoom_x]
            
            # Convert back to original frame coordinates
            orig_x = self.original_click_pos[0] - (self.zoom_region_size // 2) + zoom_x
            orig_y = self.original_click_pos[1] - (self.zoom_region_size // 2) + zoom_y
            
            # Clamp to frame bounds
            h, w = self.hsv_frame.shape[:2]
            orig_x = max(0, min(w - 1, orig_x))
            orig_y = max(0, min(h - 1, orig_y))
            
            # Sample color
            self.sample_color(hsv_value, orig_x, orig_y)
            self.show_zoom_preview()
    
    def on_zoom_key(self, event):
        """Handle arrow key navigation in zoom area"""
        if self.zoom_region is None or self.selector_pos is None:
            return
        
        zoom_h, zoom_w = self.zoom_region.shape[:2]
        sel_x, sel_y = self.selector_pos
        step = 2  # Move 2 pixels at a time for fine control
        
        # Handle key presses
        if event.keysym == "Up":
            sel_y = max(0, sel_y - step)
        elif event.keysym == "Down":
            sel_y = min(zoom_h - 1, sel_y + step)
        elif event.keysym == "Left":
            sel_x = max(0, sel_x - step)
        elif event.keysym == "Right":
            sel_x = min(zoom_w - 1, sel_x + step)
        elif event.keysym == "Return":
            # Confirm selection
            if 0 <= sel_y < zoom_h and 0 <= sel_x < zoom_w:
                hsv_value = self.zoom_region[sel_y, sel_x]
                # Convert back to original frame coordinates
                orig_x = self.original_click_pos[0] - (self.zoom_region_size // 2) + sel_x
                orig_y = self.original_click_pos[1] - (self.zoom_region_size // 2) + sel_y
                # Clamp to frame bounds
                h, w = self.hsv_frame.shape[:2]
                orig_x = max(0, min(w - 1, orig_x))
                orig_y = max(0, min(h - 1, orig_y))
                # Sample color
                self.sample_color(hsv_value, orig_x, orig_y)
            return
        
        # Update selector position
        self.selector_pos = (sel_x, sel_y)
        
        # Sample color at new position
        if 0 <= sel_y < zoom_h and 0 <= sel_x < zoom_w:
            hsv_value = self.zoom_region[sel_y, sel_x]
            # Convert back to original frame coordinates
            orig_x = self.original_click_pos[0] - (self.zoom_region_size // 2) + sel_x
            orig_y = self.original_click_pos[1] - (self.zoom_region_size // 2) + sel_y
            # Clamp to frame bounds
            h, w = self.hsv_frame.shape[:2]
            orig_x = max(0, min(w - 1, orig_x))
            orig_y = max(0, min(h - 1, orig_y))
            # Sample color
            self.sample_color(hsv_value, orig_x, orig_y)
            self.show_zoom_preview()
    
    def open_finetune_window(self, mode, color_key):
        """Open fine-tuning window for HSV ranges"""
        if mode == "ball":
            if color_key not in self.ball_hsv_ranges or not self.ball_hsv_ranges[color_key]:
                messagebox.showwarning("Warning", f"Please sample {color_key} first")
                return
            
            hsv_ranges = self.ball_hsv_ranges[color_key]
            color_name = self.ball_color1_entry.get() if color_key == "color1" else self.ball_color2_entry.get()
        else:  # team
            if color_key not in self.team_colors or not self.team_colors[color_key]["hsv_ranges"]:
                messagebox.showwarning("Warning", f"Please sample {color_key} first")
                return
            
            hsv_ranges = self.team_colors[color_key]["hsv_ranges"]
            color_name = self.team_colors[color_key]["name"]
        
        finetune_window = tk.Toplevel(self.root)
        finetune_window.title(f"Fine-tune {color_name} HSV Ranges")
        finetune_window.geometry("600x500")
        finetune_window.transient(self.root)
        finetune_window.lift()
        
        main_frame = ttk.Frame(finetune_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=f"Adjust HSV ranges for {color_name}", 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        # Check if it's a two-range (red) or single range
        finetune_vars = {}
        if "lower2" in hsv_ranges:
            # Two-range color (red)
            self.create_finetune_controls(main_frame, finetune_vars, hsv_ranges, 
                                        "Range 1 (Lower Hue)", "lower1", "upper1")
            self.create_finetune_controls(main_frame, finetune_vars, hsv_ranges,
                                        "Range 2 (Upper Hue)", "lower2", "upper2")
        else:
            # Single range
            self.create_finetune_controls(main_frame, finetune_vars, hsv_ranges,
                                        "HSV Range", "lower", "upper")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        def apply_finetune():
            # Update ranges
            if "lower2" in hsv_ranges:
                # Two-range color
                hsv_ranges["lower1"] = [
                    finetune_vars["lower1"][0].get(),
                    finetune_vars["lower1"][1].get(),
                    finetune_vars["lower1"][2].get()
                ]
                hsv_ranges["upper1"] = [
                    finetune_vars["upper1"][0].get(),
                    finetune_vars["upper1"][1].get(),
                    finetune_vars["upper1"][2].get()
                ]
                hsv_ranges["lower2"] = [
                    finetune_vars["lower2"][0].get(),
                    finetune_vars["lower2"][1].get(),
                    finetune_vars["lower2"][2].get()
                ]
                hsv_ranges["upper2"] = [
                    finetune_vars["upper2"][0].get(),
                    finetune_vars["upper2"][1].get(),
                    finetune_vars["upper2"][2].get()
                ]
            else:
                # Single range
                hsv_ranges["lower"] = [
                    finetune_vars["lower"][0].get(),
                    finetune_vars["lower"][1].get(),
                    finetune_vars["lower"][2].get()
                ]
                hsv_ranges["upper"] = [
                    finetune_vars["upper"][0].get(),
                    finetune_vars["upper"][1].get(),
                    finetune_vars["upper"][2].get()
                ]
            
            # Update display
            if mode == "ball":
                self.update_ball_hsv_label(color_key)
                self.update_ball_swatches()
            else:
                self.update_team_hsv_label(color_key)
                self.update_team_swatches()
            
            self.update_display()
            messagebox.showinfo("Applied", f"{color_name} HSV ranges updated!")
            finetune_window.destroy()
        
        ttk.Button(button_frame, text="Apply", command=apply_finetune).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=finetune_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def create_finetune_controls(self, parent, finetune_vars, current_range, title, lower_key, upper_key):
        """Create HSV adjustment controls for a range"""
        range_frame = ttk.LabelFrame(parent, text=title, padding="10")
        range_frame.pack(fill=tk.X, pady=5)
        
        lower = current_range[lower_key]
        upper = current_range[upper_key]
        
        # HSV Lower controls
        ttk.Label(range_frame, text="Lower:", font=("Arial", 9, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        
        finetune_vars[lower_key] = {}
        for i, (label, idx) in enumerate([("H:", 0), ("S:", 1), ("V:", 2)]):
            ttk.Label(range_frame, text=label).grid(row=1, column=i*2, padx=5, pady=2)
            var = tk.IntVar(value=int(lower[idx]))
            spinbox = ttk.Spinbox(range_frame, from_=0, to=255, textvariable=var, width=8)
            spinbox.grid(row=1, column=i*2+1, padx=5, pady=2)
            finetune_vars[lower_key][idx] = var
        
        # HSV Upper controls
        ttk.Label(range_frame, text="Upper:", font=("Arial", 9, "bold")).grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        
        finetune_vars[upper_key] = {}
        for i, (label, idx) in enumerate([("H:", 0), ("S:", 1), ("V:", 2)]):
            ttk.Label(range_frame, text=label).grid(row=3, column=i*2, padx=5, pady=2)
            var = tk.IntVar(value=int(upper[idx]))
            spinbox = ttk.Spinbox(range_frame, from_=0, to=255, textvariable=var, width=8)
            spinbox.grid(row=3, column=i*2+1, padx=5, pady=2)
            finetune_vars[upper_key][idx] = var
    
    def clear_color(self, mode, color_key):
        if mode == "ball":
            self.ball_hsv_ranges[color_key] = None
            self.update_ball_hsv_label(color_key)
            self.update_ball_swatches()
        else:
            self.team_colors[color_key]["hsv_ranges"] = None
            self.update_team_hsv_label(color_key)
            self.update_team_swatches()
        self.update_display()
    
    def undo_color(self, mode, color_key):
        if mode == "ball":
            if self.ball_history[color_key]:
                self.ball_hsv_ranges[color_key] = self.ball_history[color_key].pop()
                self.update_ball_hsv_label(color_key)
                self.update_ball_swatches()
        else:
            if self.team_history[color_key]:
                self.team_colors[color_key]["hsv_ranges"] = self.team_history[color_key].pop()
                self.update_team_hsv_label(color_key)
                self.update_team_swatches()
        self.update_display()
    
    def _get_default_tracker_color(self, team_name):
        """
        Generate default tracker color (BGR) based on team name.
        Returns a list [B, G, R] for OpenCV BGR format.
        """
        if not team_name:
            return [128, 128, 128]  # Default gray
        
        team_name_lower = team_name.lower()
        
        # Map team names to distinct, visible tracker colors (BGR format)
        if 'gray' in team_name_lower or 'grey' in team_name_lower:
            return [180, 180, 180]  # Light gray - more visible than medium gray
        elif 'blue' in team_name_lower:
            return [255, 100, 0]  # Cyan-blue - bright and distinct
        elif 'red' in team_name_lower:
            return [0, 0, 255]  # Red
        elif 'green' in team_name_lower:
            return [0, 255, 0]  # Green
        elif 'yellow' in team_name_lower or 'gold' in team_name_lower:
            return [0, 255, 255]  # Yellow
        elif 'orange' in team_name_lower:
            return [0, 165, 255]  # Orange
        elif 'purple' in team_name_lower or 'violet' in team_name_lower:
            return [255, 0, 128]  # Purple
        elif 'white' in team_name_lower:
            return [255, 255, 255]  # White
        elif 'black' in team_name_lower:
            return [0, 0, 0]  # Black
        else:
            # Unknown team name - use medium gray as safe default
            return [128, 128, 128]
    
    def convert_to_python_types(self, obj):
        """Convert numpy types to Python native types for JSON serialization"""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: self.convert_to_python_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_to_python_types(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self.convert_to_python_types(item) for item in obj)
        return obj
    
    def load_presets(self):
        """Load preset lists for both ball and team"""
        # Load ball presets
        ball_presets_file = "ball_color_presets.json"
        ball_presets_list = []
        if os.path.exists(ball_presets_file):
            try:
                with open(ball_presets_file, 'r') as f:
                    ball_presets = json.load(f)
                    ball_presets_list = list(ball_presets.keys())
            except:
                pass
        self.ball_preset_combo['values'] = ball_presets_list
        
        # Load team presets
        team_presets_file = "team_color_presets.json"
        team_presets_list = []
        if os.path.exists(team_presets_file):
            try:
                with open(team_presets_file, 'r') as f:
                    team_presets = json.load(f)
                    team_presets_list = list(team_presets.keys())
            except:
                pass
        self.team_preset_combobox['values'] = team_presets_list
    
    def save_preset(self, mode):
        """Save current color configuration as a preset"""
        if mode == "ball":
            if not self.ball_hsv_ranges["color1"]:
                messagebox.showwarning("Warning", "Please sample at least Color 1")
                return
            
            preset_name = simpledialog.askstring("Save Ball Preset", "Enter preset name:")
            if preset_name:
                preset = {
                    "color1_name": self.ball_color1_entry.get(),
                    "color2_name": self.ball_color2_entry.get(),
                    "hsv_ranges": self.convert_to_python_types(self.ball_hsv_ranges)
                }
                
                presets_file = "ball_color_presets.json"
                presets = {}
                if os.path.exists(presets_file):
                    with open(presets_file, 'r') as f:
                        presets = json.load(f)
                        
                presets[preset_name] = preset
                with open(presets_file, 'w') as f:
                    json.dump(presets, f, indent=2)
                    
                self.load_presets()
                self.ball_preset_var.set(preset_name)
                messagebox.showinfo("Success", f"Ball preset '{preset_name}' saved!")
        else:  # team
            if not self.team_colors["team1"]["hsv_ranges"] and not self.team_colors["team2"]["hsv_ranges"]:
                messagebox.showwarning("Warning", "Please sample at least one team color")
                return
            
            preset_name = simpledialog.askstring("Save Team Preset", "Enter preset name:")
            if preset_name:
                preset = {
                    "team1_name": self.team1_entry.get(),
                    "team2_name": self.team2_entry.get(),
                    "team_colors": {
                        "team1": {
                            "name": self.team1_entry.get(),
                            "hsv_ranges": self.convert_to_python_types(self.team_colors["team1"]["hsv_ranges"])
                        },
                        "team2": {
                            "name": self.team2_entry.get(),
                            "hsv_ranges": self.convert_to_python_types(self.team_colors["team2"]["hsv_ranges"])
                        }
                    }
                }
                
                presets_file = "team_color_presets.json"
                presets = {}
                if os.path.exists(presets_file):
                    with open(presets_file, 'r') as f:
                        presets = json.load(f)
                        
                presets[preset_name] = preset
                with open(presets_file, 'w') as f:
                    json.dump(presets, f, indent=2)
                    
                self.load_presets()
                messagebox.showinfo("Success", f"Team preset '{preset_name}' saved!")
    
    def load_preset(self, mode):
        """Load a preset"""
        if mode == "ball":
            preset_name = self.ball_preset_var.get()
            if not preset_name:
                return
                
            presets_file = "ball_color_presets.json"
            if os.path.exists(presets_file):
                with open(presets_file, 'r') as f:
                    presets = json.load(f)
                    
                if preset_name in presets:
                    preset = presets[preset_name]
                    self.ball_color1_entry.delete(0, tk.END)
                    self.ball_color1_entry.insert(0, preset.get("color1_name", "White"))
                    self.ball_color2_entry.delete(0, tk.END)
                    self.ball_color2_entry.insert(0, preset.get("color2_name", "Red"))
                    self.ball_hsv_ranges = preset["hsv_ranges"]
                    self.update_ball_hsv_label("color1")
                    self.update_ball_hsv_label("color2")
                    self.update_ball_swatches()
                    messagebox.showinfo("Success", f"Ball preset '{preset_name}' loaded!")
        else:  # team
            preset_name = self.team_preset_combobox.get()
            if not preset_name:
                return
                
            presets_file = "team_color_presets.json"
            if os.path.exists(presets_file):
                with open(presets_file, 'r') as f:
                    presets = json.load(f)
                    
                if preset_name in presets:
                    preset = presets[preset_name]
                    self.team1_entry.delete(0, tk.END)
                    self.team1_entry.insert(0, preset.get("team1_name", "Team 1"))
                    self.team2_entry.delete(0, tk.END)
                    self.team2_entry.insert(0, preset.get("team2_name", "Team 2"))
                    
                    team_colors_data = preset.get("team_colors", {})
                    if "team1" in team_colors_data:
                        self.team_colors["team1"]["hsv_ranges"] = team_colors_data["team1"].get("hsv_ranges")
                        self.team_colors["team1"]["name"] = team_colors_data["team1"].get("name", "Team 1")
                    if "team2" in team_colors_data:
                        self.team_colors["team2"]["hsv_ranges"] = team_colors_data["team2"].get("hsv_ranges")
                        self.team_colors["team2"]["name"] = team_colors_data["team2"].get("name", "Team 2")
                    
                    # Update display after loading preset
                    self.update_team_hsv_label("team1")
                    self.update_team_hsv_label("team2")
                    self.update_team_swatches()
                    self.update_display()
                    messagebox.showinfo("Success", f"Team preset '{preset_name}' loaded!")
    
    def delete_preset(self, mode):
        """Delete a preset"""
        if mode == "ball":
            preset_name = self.ball_preset_var.get()
            if not preset_name:
                return
                
            if messagebox.askyesno("Confirm", f"Delete ball preset '{preset_name}'?"):
                presets_file = "ball_color_presets.json"
                if os.path.exists(presets_file):
                    with open(presets_file, 'r') as f:
                        presets = json.load(f)
                        
                    if preset_name in presets:
                        del presets[preset_name]
                        with open(presets_file, 'w') as f:
                            json.dump(presets, f, indent=2)
                        self.load_presets()
                        self.ball_preset_var.set("")
                        messagebox.showinfo("Success", f"Ball preset '{preset_name}' deleted")
        else:  # team
            preset_name = self.team_preset_combobox.get()
            if not preset_name:
                return
                
            if messagebox.askyesno("Confirm", f"Delete team preset '{preset_name}'?"):
                presets_file = "team_color_presets.json"
                if os.path.exists(presets_file):
                    with open(presets_file, 'r') as f:
                        presets = json.load(f)
                        
                    if preset_name in presets:
                        del presets[preset_name]
                        with open(presets_file, 'w') as f:
                            json.dump(presets, f, indent=2)
                        self.load_presets()
                        self.team_preset_combobox.set("")
                        messagebox.showinfo("Success", f"Team preset '{preset_name}' deleted")
    
    def apply_ball_colors(self):
        """Apply ball colors to analysis"""
        config = {
            "color1": {
                "name": self.ball_color1_entry.get(),
                "hsv_ranges": self.convert_to_python_types(self.ball_hsv_ranges["color1"])
            },
            "color2": {
                "name": self.ball_color2_entry.get(),
                "hsv_ranges": self.convert_to_python_types(self.ball_hsv_ranges["color2"])
            }
        }
        
        with open("ball_color_config.json", 'w') as f:
            json.dump(config, f, indent=2)
        
        messagebox.showinfo("Success", "Ball colors saved to ball_color_config.json")
        if self.callback:
            self.callback(config)
    
    def apply_team_colors(self):
        """Apply team colors to analysis"""
        team1_name = self.team1_entry.get()
        team2_name = self.team2_entry.get()
        
        # Validate that at least one team has HSV ranges
        team1_has_ranges = self.team_colors["team1"]["hsv_ranges"] is not None and len(self.team_colors["team1"]["hsv_ranges"]) > 0
        team2_has_ranges = self.team_colors["team2"]["hsv_ranges"] is not None and len(self.team_colors["team2"]["hsv_ranges"]) > 0
        
        if not team1_has_ranges and not team2_has_ranges:
            messagebox.showwarning("Warning", 
                                 "Please sample at least one team color before applying.\n\n"
                                 "Click on a player's jersey in the video to sample the color.")
            return
        
        # Build config with only teams that have HSV ranges
        team_colors_config = {}
        if team1_has_ranges:
            # Auto-generate tracker color based on team name if not explicitly set
            tracker_color1 = self._get_default_tracker_color(team1_name)
            team_colors_config["team1"] = {
                "name": team1_name,
                "hsv_ranges": self.convert_to_python_types(self.team_colors["team1"]["hsv_ranges"]),
                "tracker_color_bgr": tracker_color1
            }
        if team2_has_ranges:
            # Auto-generate tracker color based on team name if not explicitly set
            tracker_color2 = self._get_default_tracker_color(team2_name)
            team_colors_config["team2"] = {
                "name": team2_name,
                "hsv_ranges": self.convert_to_python_types(self.team_colors["team2"]["hsv_ranges"]),
                "tracker_color_bgr": tracker_color2
            }
        
        config = {
            "team_colors": team_colors_config
        }
        
        try:
            with open("team_color_config.json", 'w') as f:
                json.dump(config, f, indent=2)
            
            teams_applied = []
            if team1_has_ranges:
                teams_applied.append(team1_name)
            if team2_has_ranges:
                teams_applied.append(team2_name)
            
            messagebox.showinfo("Success", 
                              f"Team colors saved to team_color_config.json\n\n"
                              f"Applied: {', '.join(teams_applied)}")
            
            if self.callback:
                self.callback(config, team1_name, team2_name)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save team colors: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    root = tk.Tk()
    app = CombinedColorHelper(root)
    root.mainloop()

