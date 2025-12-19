"""
Team Color Detection Helper
Similar to ball color detector, but for identifying team colors (e.g., red vs blue)
"""

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import json
import os
import copy

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL/Pillow not available. Install with: pip install pillow")


class TeamColorDetector:
    def __init__(self, root, callback=None):
        self.root = root
        self.root.title("Team Color Detector Helper")
        self.root.geometry("900x750")
        self.root.resizable(True, True)
        
        # Ensure window stays on top (but allow parent to manage it)
        try:
            self.root.lift()
            self.root.focus_force()
            # Don't set topmost here - let the parent window manage it
        except:
            pass

        self.callback = callback
        self.current_frame = None
        self.hsv_frame = None
        self.video_path = None
        self.cap = None
        self.current_frame_num = 0
        self.total_frames = 0
        
        # Team colors (team1 and team2)
        self.team_colors = {
            "team1": {"name": "Team 1", "hsv_ranges": None},
            "team2": {"name": "Team 2", "hsv_ranges": None}
        }
        self.current_team = "team1"  # Default to sampling team 1
        
        # History for undo functionality
        self.history = {"team1": [], "team2": []}  # Store history of HSV ranges
        self.max_history = 10  # Maximum history entries per team
        self.original_sampled = {"team1": None, "team2": None}  # Store originally sampled values
        
        # Fine-tuning state (same as ball color detector)
        self.zoom_region = None  # Store the original region for navigation
        self.zoom_region_original = None  # Original BGR region
        self.selector_pos = None  # Position of selector in zoom area (x, y)
        self.original_click_pos = None  # Original click position in main image
        self.fine_tuning_mode = False  # Whether we're in fine-tuning mode

        self.create_widgets()
        self.load_existing_config()  # Load existing config if available
        self.load_presets()

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Video controls
        video_frame = ttk.LabelFrame(main_frame, text="Video Controls", padding="10")
        video_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(video_frame, text="Video File:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.video_path_entry = ttk.Entry(video_frame, width=50)
        self.video_path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        ttk.Button(video_frame, text="Browse", command=self.browse_video).grid(row=0, column=2, padx=5, pady=5)

        self.prev_frame_button = ttk.Button(video_frame, text="<< Prev Frame", command=self.prev_frame)
        self.prev_frame_button.grid(row=1, column=0, padx=5, pady=5)
        self.next_frame_button = ttk.Button(video_frame, text="Next Frame >>", command=self.next_frame)
        self.next_frame_button.grid(row=1, column=1, padx=5, pady=5)
        
        # Frame jump controls
        ttk.Label(video_frame, text="Jump to frame:").grid(row=2, column=0, padx=5, pady=5)
        self.frame_jump_entry = ttk.Entry(video_frame, width=10)
        self.frame_jump_entry.grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(video_frame, text="Go", command=self.jump_to_frame).grid(row=2, column=2, padx=5, pady=5)
        
        self.frame_label = ttk.Label(video_frame, text="Frame: 0/0")
        self.frame_label.grid(row=1, column=2, padx=5, pady=5)

        # Canvas for video frame
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.grid(row=1, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.canvas = tk.Canvas(canvas_frame, bg="gray", width=640, height=360)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        
        # Color preview panel (right side)
        preview_frame = ttk.LabelFrame(canvas_frame, text="Color Preview", padding="5")
        preview_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        
        # Zoomed area preview
        zoom_label_frame = ttk.Frame(preview_frame)
        zoom_label_frame.pack(pady=5)
        ttk.Label(zoom_label_frame, text="Zoomed Area:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        ttk.Label(zoom_label_frame, text="(Use Arrow Keys to move)", font=("Arial", 7), 
                 foreground="gray").pack(side=tk.LEFT, padx=5)
        self.zoom_canvas = tk.Canvas(preview_frame, bg="black", width=150, height=150, 
                                     highlightthickness=1, highlightbackground="gray")
        self.zoom_canvas.pack(pady=5)
        self.zoom_canvas.bind("<Button-1>", lambda e: self.zoom_canvas.focus_set() or self.on_zoom_canvas_click(e))
        # Bind arrow keys on root (need to bind on root for arrow keys to work)
        self.root.bind("<Up>", self.on_zoom_key)
        self.root.bind("<Down>", self.on_zoom_key)
        self.root.bind("<Left>", self.on_zoom_key)
        self.root.bind("<Right>", self.on_zoom_key)
        self.root.bind("<Return>", self.on_zoom_key)
        self.root.bind("<KP_Enter>", self.on_zoom_key)
        self.zoom_canvas.configure(highlightbackground="yellow", highlightthickness=2)  # Visual indicator when focused
        
        # Color swatches
        swatch_frame = ttk.Frame(preview_frame)
        swatch_frame.pack(pady=5)
        
        ttk.Label(swatch_frame, text="Team 1:", font=("Arial", 8)).grid(row=0, column=0, pady=2)
        self.team1_swatch = tk.Canvas(swatch_frame, bg="gray", width=100, height=30)
        self.team1_swatch.grid(row=0, column=1, pady=2, padx=5)
        
        ttk.Label(swatch_frame, text="Team 2:", font=("Arial", 8)).grid(row=1, column=0, pady=2)
        self.team2_swatch = tk.Canvas(swatch_frame, bg="gray", width=100, height=30)
        self.team2_swatch.grid(row=1, column=1, pady=2, padx=5)
        
        # HSV values display
        self.hsv_display_label = ttk.Label(preview_frame, text="HSV: Not sampled", 
                                          font=("Arial", 8), wraplength=150)
        self.hsv_display_label.pack(pady=5)

        # Team color sampling controls
        color_frame = ttk.LabelFrame(main_frame, text="Team Color Sampling", padding="10")
        color_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        # Team 1
        ttk.Label(color_frame, text="Team 1 Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.team1_entry = ttk.Entry(color_frame, width=20)
        self.team1_entry.insert(0, "Team 1")
        self.team1_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Button(color_frame, text="Sample Team 1", command=lambda: self.set_team_mode("team1")).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(color_frame, text="Fine-tune", command=lambda: self.open_finetune_window("team1")).grid(row=0, column=3, padx=2, pady=5)
        ttk.Button(color_frame, text="Clear", command=lambda: self.clear_team_color("team1")).grid(row=0, column=4, padx=2, pady=5)
        self.undo1_button = ttk.Button(color_frame, text="Undo", command=lambda: self.undo_team_color("team1"), state=tk.DISABLED)
        self.undo1_button.grid(row=0, column=5, padx=2, pady=5)
        self.team1_hsv_label = ttk.Label(color_frame, text="Team 1 HSV: Not sampled")
        self.team1_hsv_label.grid(row=1, column=0, columnspan=6, sticky=tk.W, padx=5, pady=5)

        # Team 2
        ttk.Label(color_frame, text="Team 2 Name:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.team2_entry = ttk.Entry(color_frame, width=20)
        self.team2_entry.insert(0, "Team 2")
        self.team2_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Button(color_frame, text="Sample Team 2", command=lambda: self.set_team_mode("team2")).grid(row=2, column=2, padx=5, pady=5)
        ttk.Button(color_frame, text="Fine-tune", command=lambda: self.open_finetune_window("team2")).grid(row=2, column=3, padx=2, pady=5)
        ttk.Button(color_frame, text="Clear", command=lambda: self.clear_team_color("team2")).grid(row=2, column=4, padx=2, pady=5)
        self.undo2_button = ttk.Button(color_frame, text="Undo", command=lambda: self.undo_team_color("team2"), state=tk.DISABLED)
        self.undo2_button.grid(row=2, column=5, padx=2, pady=5)
        self.team2_hsv_label = ttk.Label(color_frame, text="Team 2 HSV: Not sampled")
        self.team2_hsv_label.grid(row=3, column=0, columnspan=6, sticky=tk.W, padx=5, pady=5)

        # Presets
        preset_frame = ttk.LabelFrame(main_frame, text="Presets", padding="10")
        preset_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        ttk.Button(preset_frame, text="Save Current as Preset", command=self.save_preset).grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(preset_frame, text="Load Preset:").grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.preset_combobox = ttk.Combobox(preset_frame, state="readonly")
        self.preset_combobox.grid(row=0, column=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.preset_combobox.bind("<<ComboboxSelected>>", self.load_selected_preset)
        # Add explicit load button to allow re-selecting same preset
        ttk.Button(preset_frame, text="Load", command=self.load_current_preset).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(preset_frame, text="Apply to Analysis", command=self.apply_to_main_gui).grid(row=0, column=4, padx=5, pady=5)

        # Status bar
        self.status_label = ttk.Label(main_frame, text="Load a video and click on team jerseys to sample colors.", 
                                     relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        main_frame.rowconfigure(1, weight=1)  # Make canvas expandable
        canvas_frame.rowconfigure(0, weight=1)

    def browse_video(self):
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
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            messagebox.showerror("Error", f"Could not open video file: {self.video_path}")
            return
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.current_frame_num = 0
        self.display_frame()

    def display_frame(self):
        if not self.cap or not self.cap.isOpened():
            return

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_num)
        ret, frame = self.cap.read()
        if not ret:
            return

        self.current_frame = frame.copy()
        self.hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        display_frame = self.current_frame.copy()

        # Draw current HSV masks for visualization
        mask = None
        for team_key, team_data in self.team_colors.items():
            if team_data["hsv_ranges"]:
                r = team_data["hsv_ranges"]
                if "lower" in r:  # Single range
                    lower = np.array(r["lower"])
                    upper = np.array(r["upper"])
                    mask_team = cv2.inRange(self.hsv_frame, lower, upper)
                else:  # Two ranges for red
                    lower1 = np.array(r["lower1"])
                    upper1 = np.array(r["upper1"])
                    lower2 = np.array(r["lower2"])
                    upper2 = np.array(r["upper2"])
                    mask_team_1 = cv2.inRange(self.hsv_frame, lower1, upper1)
                    mask_team_2 = cv2.inRange(self.hsv_frame, lower2, upper2)
                    mask_team = cv2.bitwise_or(mask_team_1, mask_team_2)
                
                # Color code: team1 = blue overlay, team2 = red overlay
                if team_key == "team1":
                    overlay_color = (255, 0, 0)  # Blue in BGR
                else:
                    overlay_color = (0, 0, 255)  # Red in BGR
                
                # Create colored overlay
                overlay = display_frame.copy()
                overlay[mask_team > 0] = overlay_color
                display_frame = cv2.addWeighted(display_frame, 0.7, overlay, 0.3, 0)
        
        # Resize for display
        h, w, _ = display_frame.shape
        max_width = 800
        max_height = 450
        if w > max_width or h > max_height:
            scale = min(max_width / w, max_height / h)
            new_w, new_h = int(w * scale), int(h * scale)
            display_frame = cv2.resize(display_frame, (new_w, new_h))
            
        # Convert to RGB for tkinter
        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        
        # Display on canvas
        if PIL_AVAILABLE:
            img = Image.fromarray(display_frame)
            self.photo = ImageTk.PhotoImage(image=img)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            self.canvas.config(width=display_frame.shape[1], height=display_frame.shape[0])
        else:
            # Fallback
            _, img_data = cv2.imencode('.png', display_frame)
            import base64
            img_str = base64.b64encode(img_data).decode()
            self.photo = tk.PhotoImage(data=img_str)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            self.canvas.config(width=display_frame.shape[1], height=display_frame.shape[0])
        
        # Store scale factor for click coordinates
        self.scale_factor = w / display_frame.shape[1]
        
        self.frame_label.config(text=f"Frame: {self.current_frame_num + 1}/{self.total_frames}")

    def prev_frame(self):
        if self.current_frame_num > 0:
            self.current_frame_num -= 1
            self.display_frame()

    def next_frame(self):
        if self.current_frame_num < self.total_frames - 1:
            self.current_frame_num += 1
            self.display_frame()
    
    def jump_to_frame(self):
        """Jump to a specific frame number"""
        try:
            frame_num = int(self.frame_jump_entry.get())
            if 0 <= frame_num < self.total_frames:
                self.current_frame_num = frame_num
                self.display_frame()
            else:
                messagebox.showwarning("Invalid Frame", f"Frame number must be between 0 and {self.total_frames - 1}")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid frame number")

    def set_team_mode(self, team_key):
        self.current_team = team_key
        team_name = self.team1_entry.get() if team_key == "team1" else self.team2_entry.get()
        self.status_label.config(text=f"Click on {team_name} jersey to sample color")
        
    def on_canvas_click(self, event):
        if self.current_frame is None or self.hsv_frame is None:
            return
            
        # Convert canvas coordinates to image coordinates
        if hasattr(self, 'scale_factor'):
            x = int(event.x * self.scale_factor)
            y = int(event.y * self.scale_factor)
        else:
            x = int(event.x)
            y = int(event.y)
            
        # Sample HSV values from a small region around click point
        region_size = 15  # Larger region for jerseys
        x1 = max(0, x - region_size)
        y1 = max(0, y - region_size)
        x2 = min(self.hsv_frame.shape[1], x + region_size)
        y2 = min(self.hsv_frame.shape[0], y + region_size)
        
        region = self.hsv_frame[y1:y2, x1:x2]
        
        # Store original click position and region for fine-tuning
        self.original_click_pos = (x, y)
        self.zoom_region = region
        if self.current_frame is not None:
            self.zoom_region_original = self.current_frame[y1:y2, x1:x2]
        else:
            self.zoom_region_original = None
        
        # Initialize selector at center of zoom area
        self.selector_pos = (region.shape[1] // 2, region.shape[0] // 2) if region.size > 0 else None
        self.fine_tuning_mode = True
        
        # Show zoomed preview with selector
        self.show_zoom_preview(region, show_selector=True)
        
        # Focus zoom canvas for keyboard input
        self.zoom_canvas.focus_set()
        self.zoom_canvas.configure(highlightbackground="yellow", highlightthickness=2)  # Show focused state
        
        # Update status message
        team_name = self.team1_entry.get() if self.current_team == "team1" else self.team2_entry.get()
        self.status_label.config(text=f"{team_name} selected - Use arrow keys to fine-tune, then click/Enter to confirm")
        
        # Draw marker on canvas
        self.canvas.create_oval(event.x - 5, event.y - 5, event.x + 5, event.y + 5,
                              outline="yellow", width=2)
        
        # Note: HSV ranges will be set when confirming in fine-tuning mode via confirm_selector_color()
            
    def show_zoom_preview(self, region=None, show_selector=False):
        """Show zoomed-in preview of selected region with optional selector"""
        if region is None:
            region = self.zoom_region
        
        if region is None or region.size == 0:
            return
        
        # Convert HSV region to BGR for display
        bgr_region = cv2.cvtColor(region, cv2.COLOR_HSV2BGR)
        
        # Resize to fit zoom canvas (150x150)
        zoom_size = 150
        zoomed = cv2.resize(bgr_region, (zoom_size, zoom_size), interpolation=cv2.INTER_NEAREST)
        
        # Convert to RGB for tkinter
        zoomed_rgb = cv2.cvtColor(zoomed, cv2.COLOR_BGR2RGB)
        
        # Clear zoom canvas
        self.zoom_canvas.delete("all")
        
        # Display on zoom canvas
        if PIL_AVAILABLE:
            zoom_img = Image.fromarray(zoomed_rgb)
            zoom_photo = ImageTk.PhotoImage(image=zoom_img)
            self.zoom_canvas.create_image(0, 0, anchor=tk.NW, image=zoom_photo)
            self.zoom_canvas.zoom_photo = zoom_photo  # Keep reference
            self.zoom_canvas.config(width=zoom_size, height=zoom_size)
        else:
            # Fallback
            _, img_data = cv2.imencode('.png', zoomed_rgb)
            import base64
            img_str = base64.b64encode(img_data).decode()
            zoom_photo = tk.PhotoImage(data=img_str)
            self.zoom_canvas.create_image(0, 0, anchor=tk.NW, image=zoom_photo)
            self.zoom_canvas.zoom_photo = zoom_photo
            self.zoom_canvas.config(width=zoom_size, height=zoom_size)
        
        # Draw selector if in fine-tuning mode
        if show_selector and self.selector_pos is not None:
            # Map selector position to zoom canvas coordinates
            sel_x, sel_y = self.selector_pos
            # Scale to zoom canvas size
            zoom_x = int((sel_x / region.shape[1]) * zoom_size)
            zoom_y = int((sel_y / region.shape[0]) * zoom_size)
            
            # Draw crosshair selector
            crosshair_size = 10
            self.zoom_canvas.create_line(zoom_x - crosshair_size, zoom_y, 
                                         zoom_x + crosshair_size, zoom_y, 
                                         fill="yellow", width=2)
            self.zoom_canvas.create_line(zoom_x, zoom_y - crosshair_size, 
                                         zoom_x, zoom_y + crosshair_size, 
                                         fill="yellow", width=2)
            self.zoom_canvas.create_oval(zoom_x - 5, zoom_y - 5, zoom_x + 5, zoom_y + 5, 
                                         outline="yellow", width=2)
            
            # Update color from selector position
            self.update_color_from_selector()
    
    def on_zoom_key(self, event):
        """Handle arrow key navigation in zoom area"""
        if not self.fine_tuning_mode or self.selector_pos is None or self.zoom_region is None:
            return
        
        if self.zoom_region.size == 0:
            return
        
        sel_x, sel_y = self.selector_pos
        region_h, region_w = self.zoom_region.shape[:2]
        
        # Move selector based on arrow key
        if event.keysym == "Up":
            sel_y = max(0, sel_y - 1)
        elif event.keysym == "Down":
            sel_y = min(region_h - 1, sel_y + 1)
        elif event.keysym == "Left":
            sel_x = max(0, sel_x - 1)
        elif event.keysym == "Right":
            sel_x = min(region_w - 1, sel_x + 1)
        elif event.keysym == "Return" or event.keysym == "KP_Enter":
            # Enter key confirms selection
            self.confirm_selector_color()
            return
        else:
            return  # Ignore other keys
        
        # Update selector position
        self.selector_pos = (sel_x, sel_y)
        
        # Update zoom preview with new selector position
        self.show_zoom_preview(show_selector=True)
    
    def on_zoom_canvas_click(self, event):
        """Handle click on zoom canvas to confirm color selection"""
        if not self.fine_tuning_mode or self.zoom_region is None:
            return
        
        # Map click position to region coordinates
        zoom_size = 150
        click_x = event.x
        click_y = event.y
        
        # Convert to region coordinates
        region_w, region_h = self.zoom_region.shape[1], self.zoom_region.shape[0]
        sel_x = int((click_x / zoom_size) * region_w)
        sel_y = int((click_y / zoom_size) * region_h)
        
        # Clamp to region bounds
        sel_x = max(0, min(region_w - 1, sel_x))
        sel_y = max(0, min(region_h - 1, sel_y))
        
        self.selector_pos = (sel_x, sel_y)
        
        # Confirm selection
        self.confirm_selector_color()
    
    def update_color_from_selector(self):
        """Update color preview from current selector position"""
        if not self.fine_tuning_mode or self.selector_pos is None or self.zoom_region is None:
            return
        
        if self.zoom_region.size == 0:
            return
        
        sel_x, sel_y = self.selector_pos
        
        # Get HSV value at selector position
        if sel_y < self.zoom_region.shape[0] and sel_x < self.zoom_region.shape[1]:
            hsv_val = self.zoom_region[sel_y, sel_x]
            h, s, v = int(hsv_val[0]), int(hsv_val[1]), int(hsv_val[2])
            
            # Get BGR color for swatch
            if self.zoom_region_original is not None and sel_y < self.zoom_region_original.shape[0] and sel_x < self.zoom_region_original.shape[1]:
                bgr_color = tuple(int(c) for c in self.zoom_region_original[sel_y, sel_x])
            else:
                # Convert HSV to BGR
                bgr_pixel = cv2.cvtColor(np.array([[[h, s, v]]], dtype=np.uint8), cv2.COLOR_HSV2BGR)[0][0]
                bgr_color = tuple(int(c) for c in bgr_pixel)
            
            # Update display (but don't save HSV ranges yet - wait for confirmation)
            self.hsv_display_label.config(text=f"HSV: H={h}, S={s}, V={v}\nRGB: R={bgr_color[2]}, G={bgr_color[1]}, B={bgr_color[0]}\n(Arrow keys to adjust, Click/Enter to confirm)")
    
    def confirm_selector_color(self):
        """Confirm color selection from current selector position"""
        if not self.fine_tuning_mode or self.selector_pos is None or self.zoom_region is None:
            return
        
        if self.zoom_region.size == 0:
            return
        
        sel_x, sel_y = self.selector_pos
        
        # Get HSV value at selector position
        if sel_y >= self.zoom_region.shape[0] or sel_x >= self.zoom_region.shape[1]:
            return
        
        hsv_val = self.zoom_region[sel_y, sel_x]
        h_median = int(hsv_val[0])
        s_median = int(hsv_val[1])
        v_median = int(hsv_val[2])
        
        # Get BGR color for swatch
        if self.zoom_region_original is not None and sel_y < self.zoom_region_original.shape[0] and sel_x < self.zoom_region_original.shape[1]:
            bgr_color = tuple(int(c) for c in self.zoom_region_original[sel_y, sel_x])
        else:
            # Convert HSV to BGR
            bgr_pixel = cv2.cvtColor(np.array([[[h_median, s_median, v_median]]], dtype=np.uint8), cv2.COLOR_HSV2BGR)[0][0]
            bgr_color = tuple(int(c) for c in bgr_pixel)
        
        # Calculate HSV range based on sampled color (same logic as before, but wider for jerseys)
        if h_median < 10 or h_median > 170:  # Red (wraps around)
            lower1 = np.array([0, max(50, s_median - 40), max(50, v_median - 40)])
            upper1 = np.array([10, 255, 255])
            lower2 = np.array([170, max(50, s_median - 40), max(50, v_median - 40)])
            upper2 = np.array([180, 255, 255])
            new_range = {
                "lower1": lower1.tolist(), "upper1": upper1.tolist(),
                "lower2": lower2.tolist(), "upper2": upper2.tolist()
            }
            # Save to history and store as original if first time
            if self.team_colors[self.current_team]["hsv_ranges"] is not None:
                self.save_to_history(self.current_team)
            else:
                self.original_sampled[self.current_team] = copy.deepcopy(new_range)
            self.team_colors[self.current_team]["hsv_ranges"] = new_range
            self.update_color_swatch(self.current_team, bgr_color, h_median, s_median, v_median)
        else:
            # General color range (wider for jerseys)
            lower = np.array([max(0, h_median - 15), max(30, s_median - 40), max(30, v_median - 40)])
            upper = np.array([min(180, h_median + 15), 255, 255])
            new_range = {
                "lower": lower.tolist(), "upper": upper.tolist()
            }
            # Save to history and store as original if first time
            if self.team_colors[self.current_team]["hsv_ranges"] is not None:
                self.save_to_history(self.current_team)
            else:
                self.original_sampled[self.current_team] = copy.deepcopy(new_range)
            self.team_colors[self.current_team]["hsv_ranges"] = new_range
            self.update_color_swatch(self.current_team, bgr_color, h_median, s_median, v_median)
        
        self.update_hsv_display()
        self.update_undo_button_state()
        
        team_name = self.team1_entry.get() if self.current_team == "team1" else self.team2_entry.get()
        self.status_label.config(text=f"{team_name} sampled: HSV({h_median}, {s_median}, {v_median}) - Fine-tuned")
        
        # Exit fine-tuning mode
        self.fine_tuning_mode = False
    
    def update_color_swatch(self, team_key, bgr_color, h, s, v):
        """Update color swatch for the selected team"""
        # Convert BGR to RGB for tkinter
        rgb_color = f"#{bgr_color[2]:02x}{bgr_color[1]:02x}{bgr_color[0]:02x}"
        
        swatch = self.team1_swatch if team_key == "team1" else self.team2_swatch
        swatch.delete("all")
        swatch.create_rectangle(0, 0, 100, 30, fill=rgb_color, outline="black", width=2)
        
        # Update HSV display
        self.hsv_display_label.config(text=f"HSV: H={h}, S={s}, V={v}\nRGB: R={bgr_color[2]}, G={bgr_color[1]}, B={bgr_color[0]}")
    
    def update_hsv_display(self):
        for team_key in ["team1", "team2"]:
            team_data = self.team_colors[team_key]
            if team_data["hsv_ranges"]:
                r = team_data["hsv_ranges"]
                if "lower" in r:
                    text = f"Team {team_key[-1]} HSV: Lower={r['lower']}, Upper={r['upper']}"
                else:
                    text = f"Team {team_key[-1]} HSV: Lower1={r['lower1']}, Upper1={r['upper1']}, Lower2={r['lower2']}, Upper2={r['upper2']}"
                
                if team_key == "team1":
                    self.team1_hsv_label.config(text=f"Team 1: {text.split('Team 1: ')[-1] if 'Team 1:' in text else text}")
                else:
                    self.team2_hsv_label.config(text=f"Team 2: {text.split('Team 2: ')[-1] if 'Team 2:' in text else text}")
            else:
                if team_key == "team1":
                    self.team1_hsv_label.config(text="Team 1 HSV: Not sampled")
                else:
                    self.team2_hsv_label.config(text="Team 2 HSV: Not sampled")
        self.display_frame()  # Redraw frame with new masks
    
    def open_finetune_window(self, team_key):
        """Open fine-tuning window for HSV ranges (similar to ball_color_detector)"""
        if team_key not in self.team_colors or not self.team_colors[team_key]["hsv_ranges"]:
            messagebox.showwarning("Warning", f"Please sample {team_key} first")
            return
        
        finetune_window = tk.Toplevel(self.root)
        finetune_window.title(f"Fine-tune {team_key.upper()} HSV Ranges")
        finetune_window.geometry("600x500")
        
        team_name = self.team1_entry.get() if team_key == "team1" else self.team2_entry.get()
        
        main_frame = ttk.Frame(finetune_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=f"Adjust HSV ranges for {team_name}", 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        # Get current ranges
        current_range = self.team_colors[team_key]["hsv_ranges"]
        
        # Check if it's a two-range (red) or single range
        if "lower2" in current_range:
            # Two-range color (red)
            self.create_finetune_controls(main_frame, team_key, current_range, 
                                        "Range 1 (Lower Hue)", "lower1", "upper1")
            self.create_finetune_controls(main_frame, team_key, current_range,
                                        "Range 2 (Upper Hue)", "lower2", "upper2")
        else:
            # Single range
            self.create_finetune_controls(main_frame, team_key, current_range,
                                        "HSV Range", "lower", "upper")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Apply", command=lambda: self.apply_finetune(finetune_window, team_key)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset to Sampled", command=lambda: self.reset_to_sampled(team_key)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=finetune_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def create_finetune_controls(self, parent, team_key, current_range, title, lower_key, upper_key):
        """Create HSV adjustment controls for a range"""
        range_frame = ttk.LabelFrame(parent, text=title, padding="10")
        range_frame.pack(fill=tk.X, pady=5)
        
        lower = current_range[lower_key]
        upper = current_range[upper_key]
        
        # HSV Lower controls
        ttk.Label(range_frame, text="Lower:", font=("Arial", 9, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        
        for i, (label, idx) in enumerate([("H:", 0), ("S:", 1), ("V:", 2)]):
            ttk.Label(range_frame, text=label).grid(row=1, column=i*2, padx=5, pady=2)
            var = tk.IntVar(value=int(lower[idx]))
            spinbox = ttk.Spinbox(range_frame, from_=0, to=255, textvariable=var, width=8)
            spinbox.grid(row=1, column=i*2+1, padx=5, pady=2)
            
            # Store reference
            if not hasattr(self, 'finetune_vars'):
                self.finetune_vars = {}
            if team_key not in self.finetune_vars:
                self.finetune_vars[team_key] = {}
            if lower_key not in self.finetune_vars[team_key]:
                self.finetune_vars[team_key][lower_key] = {}
            self.finetune_vars[team_key][lower_key][idx] = var
        
        # HSV Upper controls
        ttk.Label(range_frame, text="Upper:", font=("Arial", 9, "bold")).grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        
        for i, (label, idx) in enumerate([("H:", 0), ("S:", 1), ("V:", 2)]):
            ttk.Label(range_frame, text=label).grid(row=3, column=i*2, padx=5, pady=2)
            var = tk.IntVar(value=int(upper[idx]))
            spinbox = ttk.Spinbox(range_frame, from_=0, to=255, textvariable=var, width=8)
            spinbox.grid(row=3, column=i*2+1, padx=5, pady=2)
            
            # Store reference
            if upper_key not in self.finetune_vars[team_key]:
                self.finetune_vars[team_key][upper_key] = {}
            self.finetune_vars[team_key][upper_key][idx] = var
    
    def apply_finetune(self, window, team_key):
        """Apply fine-tuned HSV ranges"""
        if not hasattr(self, 'finetune_vars') or team_key not in self.finetune_vars:
            return
        
        vars_dict = self.finetune_vars[team_key]
        current_range = copy.deepcopy(self.team_colors[team_key]["hsv_ranges"])
        
        # Update ranges
        if "lower2" in current_range:
            # Two-range color
            current_range["lower1"] = [
                vars_dict["lower1"][0].get(),
                vars_dict["lower1"][1].get(),
                vars_dict["lower1"][2].get()
            ]
            current_range["upper1"] = [
                vars_dict["upper1"][0].get(),
                vars_dict["upper1"][1].get(),
                vars_dict["upper1"][2].get()
            ]
            current_range["lower2"] = [
                vars_dict["lower2"][0].get(),
                vars_dict["lower2"][1].get(),
                vars_dict["lower2"][2].get()
            ]
            current_range["upper2"] = [
                vars_dict["upper2"][0].get(),
                vars_dict["upper2"][1].get(),
                vars_dict["upper2"][2].get()
            ]
        else:
            # Single range
            current_range["lower"] = [
                vars_dict["lower"][0].get(),
                vars_dict["lower"][1].get(),
                vars_dict["lower"][2].get()
            ]
            current_range["upper"] = [
                vars_dict["upper"][0].get(),
                vars_dict["upper"][1].get(),
                vars_dict["upper"][2].get()
            ]
        
        # Save to history before updating
        self.save_to_history(team_key)
        self.team_colors[team_key]["hsv_ranges"] = current_range
        self.update_hsv_display()
        self.update_undo_button_state()
        
        messagebox.showinfo("Applied", f"{team_key.upper()} HSV ranges updated!")
        window.destroy()
    
    def save_to_history(self, team_key):
        """Save current HSV range to history before changing"""
        if self.team_colors[team_key]["hsv_ranges"] is not None:
            # Deep copy current range
            current = copy.deepcopy(self.team_colors[team_key]["hsv_ranges"])
            self.history[team_key].append(current)
            # Limit history size
            if len(self.history[team_key]) > self.max_history:
                self.history[team_key] = self.history[team_key][-self.max_history:]
    
    def clear_team_color(self, team_key):
        """Clear the selected team's HSV ranges"""
        if self.team_colors[team_key]["hsv_ranges"] is not None:
            # Save to history before clearing
            self.save_to_history(team_key)
            self.team_colors[team_key]["hsv_ranges"] = None
            self.original_sampled[team_key] = None
            
            # Clear swatch
            swatch = self.team1_swatch if team_key == "team1" else self.team2_swatch
            swatch.delete("all")
            swatch.create_rectangle(0, 0, 100, 30, fill="gray", outline="black", width=2)
            
            # Update display
            self.update_hsv_display()
            self.update_undo_button_state()
            team_name = self.team1_entry.get() if team_key == "team1" else self.team2_entry.get()
            self.status_label.config(text=f"{team_name} cleared")
    
    def undo_team_color(self, team_key):
        """Undo the last change to a team's HSV range"""
        if len(self.history[team_key]) == 0:
            return
        
        # Restore previous value from history
        previous = self.history[team_key].pop()
        self.team_colors[team_key]["hsv_ranges"] = previous
        self.update_hsv_display()
        self.update_undo_button_state()
        
        # Update swatch if we have a range
        if previous is not None:
            # Try to extract color from range (use midpoint)
            if "lower" in previous:
                lower = np.array(previous["lower"])
                upper = np.array(previous["upper"])
                mid_hsv = (lower + upper) // 2
            else:
                lower1 = np.array(previous["lower1"])
                upper1 = np.array(previous["upper1"])
                mid_hsv = (lower1 + upper1) // 2
            
            bgr_pixel = cv2.cvtColor(np.array([[[int(mid_hsv[0]), int(mid_hsv[1]), int(mid_hsv[2])]]], dtype=np.uint8), cv2.COLOR_HSV2BGR)[0][0]
            bgr_color = tuple(int(c) for c in bgr_pixel)
            swatch = self.team1_swatch if team_key == "team1" else self.team2_swatch
            rgb_color = f"#{bgr_color[2]:02x}{bgr_color[1]:02x}{bgr_color[0]:02x}"
            swatch.delete("all")
            swatch.create_rectangle(0, 0, 100, 30, fill=rgb_color, outline="black", width=2)
        
        team_name = self.team1_entry.get() if team_key == "team1" else self.team2_entry.get()
        self.status_label.config(text=f"{team_name} undone")
    
    def update_undo_button_state(self):
        """Update the enabled/disabled state of undo buttons"""
        if hasattr(self, 'undo1_button'):
            self.undo1_button.config(state=tk.NORMAL if len(self.history["team1"]) > 0 else tk.DISABLED)
        if hasattr(self, 'undo2_button'):
            self.undo2_button.config(state=tk.NORMAL if len(self.history["team2"]) > 0 else tk.DISABLED)
    
    def reset_to_sampled(self, team_key):
        """Reset HSV ranges to originally sampled values"""
        if self.original_sampled[team_key] is not None:
            self.save_to_history(team_key)
            self.team_colors[team_key]["hsv_ranges"] = copy.deepcopy(self.original_sampled[team_key])
            self.update_hsv_display()
            self.update_undo_button_state()
            team_name = self.team1_entry.get() if team_key == "team1" else self.team2_entry.get()
            self.status_label.config(text=f"{team_name} reset to original sampled values")
        else:
            messagebox.showinfo("Info", "No original sampled values found. Please re-sample the color.")

    def save_preset(self):
        if not self.team_colors["team1"]["hsv_ranges"] and not self.team_colors["team2"]["hsv_ranges"]:
            messagebox.showwarning("Warning", "Please sample at least one team color")
            return
            
        preset_name = simpledialog.askstring("Save Preset", "Enter preset name:")
        if preset_name:
            preset = {
                "team1_name": self.team1_entry.get(),
                "team2_name": self.team2_entry.get(),
                "team_colors": self.team_colors
            }
            
            presets_file = "team_color_presets.json"
            all_presets = {}
            if os.path.exists(presets_file):
                with open(presets_file, 'r') as f:
                    all_presets = json.load(f)
            
            all_presets[preset_name] = preset
            
            with open(presets_file, 'w') as f:
                json.dump(all_presets, f, indent=4)
            
            messagebox.showinfo("Success", f"Preset '{preset_name}' saved!")
            self.load_presets()

    def load_existing_config(self):
        """Load existing team color configuration from team_color_config.json"""
        config_file = "team_color_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                # Handle both old format (with team1_name/team2_name) and new format
                if "team_colors" in config:
                    # New format: {"team_colors": {"team1": {...}, "team2": {...}}}
                    self.team_colors = config["team_colors"]
                    
                    # Update team name entry fields
                    if "team1" in self.team_colors:
                        team1_name = self.team_colors["team1"].get("name", "Team 1")
                        self.team1_entry.delete(0, tk.END)
                        self.team1_entry.insert(0, team1_name)
                    
                    if "team2" in self.team_colors:
                        team2_name = self.team_colors["team2"].get("name", "Team 2")
                        self.team2_entry.delete(0, tk.END)
                        self.team2_entry.insert(0, team2_name)
                    
                    # Update HSV display
                    self.update_hsv_display()
                elif "team1_name" in config and "team2_name" in config:
                    # Old format: {"team1_name": "...", "team2_name": "...", "team_colors": {...}}
                    # Convert to new format
                    if "team_colors" in config:
                        self.team_colors = config["team_colors"]
                        # Update names from old format
                        if "team1" in self.team_colors:
                            self.team_colors["team1"]["name"] = config.get("team1_name", "Team 1")
                        if "team2" in self.team_colors:
                            self.team_colors["team2"]["name"] = config.get("team2_name", "Team 2")
                        
                        # Update entry fields
                        self.team1_entry.delete(0, tk.END)
                        self.team1_entry.insert(0, config.get("team1_name", "Team 1"))
                        self.team2_entry.delete(0, tk.END)
                        self.team2_entry.insert(0, config.get("team2_name", "Team 2"))
                        
                        # Update HSV display
                        self.update_hsv_display()
            except Exception as e:
                print(f"Warning: Could not load existing team color config: {e}")
                # Keep default values

    def load_presets(self):
        presets_file = "team_color_presets.json"
        if os.path.exists(presets_file):
            with open(presets_file, 'r') as f:
                self.all_presets = json.load(f)
                self.preset_combobox['values'] = list(self.all_presets.keys())
        else:
            self.all_presets = {}
            self.preset_combobox['values'] = []

    def load_selected_preset(self, event=None):
        """Load the currently selected preset from the dropdown"""
        selected_preset_name = self.preset_combobox.get()
        if not selected_preset_name:
            messagebox.showwarning("Warning", "Please select a preset from the dropdown first.")
            return
        
        if selected_preset_name in self.all_presets:
            preset = self.all_presets[selected_preset_name]
            self.team1_entry.delete(0, tk.END)
            self.team1_entry.insert(0, preset.get("team1_name", "Team 1"))
            self.team2_entry.delete(0, tk.END)
            self.team2_entry.insert(0, preset.get("team2_name", "Team 2"))
            self.team_colors = preset["team_colors"]
            self.update_hsv_display()
            messagebox.showinfo("Preset Loaded", f"Preset '{selected_preset_name}' loaded.")
        else:
            messagebox.showerror("Error", f"Preset '{selected_preset_name}' not found.")
    
    def load_current_preset(self):
        """Load the currently selected preset (allows re-selecting same preset)"""
        self.load_selected_preset()

    def apply_to_main_gui(self):
        # Save team colors to config file
        config_file = "team_color_config.json"
        try:
            team1_name = self.team1_entry.get().strip()
            team2_name = self.team2_entry.get().strip()
            
            # Update team names in team_colors structure
            if "team1" in self.team_colors:
                self.team_colors["team1"]["name"] = team1_name if team1_name else "Team 1"
            if "team2" in self.team_colors:
                self.team_colors["team2"]["name"] = team2_name if team2_name else "Team 2"
            
            # Save in the format expected by the analysis: {"team_colors": {...}}
            config = {
                "team_colors": self.team_colors
            }
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)  # Use indent=2 to match analysis format
            
            messagebox.showinfo("Applied", f"Team color configuration saved to {config_file}.\n\nAnalysis will now use these team colors.")
            if self.callback:
                # Call callback with required arguments
                self.callback(self.team_colors, team1_name, team2_name)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save team color config: {e}")


def main():
    root = tk.Tk()
    app = TeamColorDetector(root)
    root.mainloop()


if __name__ == "__main__":
    main()

