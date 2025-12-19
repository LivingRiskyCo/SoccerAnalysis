"""
Ball Color Detection Helper
Helps identify HSV color ranges for different colored balls.
"""

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import json
import os
import copy

# Try to import PIL for image display, fallback if not available
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL/Pillow not available. Install with: pip install pillow")


class BallColorDetector:
    def __init__(self, root, callback=None):
        self.root = root
        self.callback = callback  # Callback to return HSV ranges
        self.video_path = None
        self.cap = None
        self.current_frame = None
        self.hsv_frame = None
        self.selected_points = []
        self.hsv_ranges = {"color1": None, "color2": None}
        self.color_names = {"color1": "Color 1", "color2": "Color 2"}
        
        # History for undo functionality
        self.history = {"color1": [], "color2": []}  # Store history of HSV ranges
        self.max_history = 10  # Maximum history entries per color
        self.original_sampled = {"color1": None, "color2": None}  # Store originally sampled values
        
        # Fine-tuning state
        self.zoom_region = None  # Store the original region for navigation
        self.zoom_region_original = None  # Original BGR region
        self.selector_pos = None  # Position of selector in zoom area (x, y)
        self.original_click_pos = None  # Original click position in main image
        self.fine_tuning_mode = False  # Whether we're in fine-tuning mode
        
        # Ensure window stays on top
        try:
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.focus_force()
        except:
            pass
        
        self.setup_ui()
        
    def setup_ui(self):
        self.root.title("Ball Color Detection Helper")
        self.root.geometry("900x700")
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        instructions = ttk.Label(
            main_frame,
            text="1. Load video or select a frame\n"
                 "2. Click on the ball to sample its color\n"
                 "3. Use arrow keys in the zoomed area to fine-tune the selection\n"
                 "4. Click or press Enter in the zoomed area to confirm\n"
                 "5. Adjust HSV ranges if needed (Fine-tune button)\n"
                 "6. Save preset for future use",
            justify=tk.LEFT
        )
        instructions.pack(pady=10)
        
        # Video selection
        video_frame = ttk.Frame(main_frame)
        video_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(video_frame, text="Load Video", command=self.load_video).pack(side=tk.LEFT, padx=5)
        ttk.Button(video_frame, text="Load Image", command=self.load_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(video_frame, text="Grab Frame", command=self.grab_frame).pack(side=tk.LEFT, padx=5)
        
        # Canvas frame with preview
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        
        # Canvas for displaying image
        self.canvas = tk.Canvas(canvas_frame, width=800, height=450, bg="black")
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
        self.zoom_canvas = tk.Canvas(preview_frame, bg="black", width=150, height=150, highlightthickness=1, highlightbackground="gray")
        self.zoom_canvas.pack(pady=5)
        # Bind arrow keys on root (need to bind on root for arrow keys to work)
        self.root.bind("<Up>", self.on_zoom_key)
        self.root.bind("<Down>", self.on_zoom_key)
        self.root.bind("<Left>", self.on_zoom_key)
        self.root.bind("<Right>", self.on_zoom_key)
        self.root.bind("<Return>", self.on_zoom_key)
        self.root.bind("<KP_Enter>", self.on_zoom_key)
        # Make zoom canvas focusable and clickable
        self.zoom_canvas.bind("<Button-1>", lambda e: self.zoom_canvas.focus_set() or self.on_zoom_canvas_click(e))
        self.zoom_canvas.configure(highlightbackground="yellow", highlightthickness=2)  # Visual indicator when focused
        
        # Color swatches
        swatch_frame = ttk.Frame(preview_frame)
        swatch_frame.pack(pady=5)
        
        ttk.Label(swatch_frame, text="Color 1:", font=("Arial", 8)).grid(row=0, column=0, pady=2)
        self.color1_swatch = tk.Canvas(swatch_frame, bg="gray", width=100, height=30)
        self.color1_swatch.grid(row=0, column=1, pady=2, padx=5)
        
        ttk.Label(swatch_frame, text="Color 2:", font=("Arial", 8)).grid(row=1, column=0, pady=2)
        self.color2_swatch = tk.Canvas(swatch_frame, bg="gray", width=100, height=30)
        self.color2_swatch.grid(row=1, column=1, pady=2, padx=5)
        
        # HSV values display
        self.hsv_display_label = ttk.Label(preview_frame, text="HSV: Not sampled", 
                                          font=("Arial", 8), wraplength=150)
        self.hsv_display_label.pack(pady=5)
        
        # Status
        self.status_label = ttk.Label(main_frame, text="Load a video or image to start")
        self.status_label.pack(pady=5)
        
        # Color selection
        color_frame = ttk.LabelFrame(main_frame, text="Color Selection", padding="10")
        color_frame.pack(fill=tk.X, pady=5)
        
        # Color 1 (primary)
        color1_frame = ttk.Frame(color_frame)
        color1_frame.pack(fill=tk.X, pady=5)
        ttk.Label(color1_frame, text="Color 1 (Primary):", width=15).pack(side=tk.LEFT)
        self.color1_entry = ttk.Entry(color1_frame, width=30)
        self.color1_entry.pack(side=tk.LEFT, padx=5)
        self.color1_entry.insert(0, "White")
        self.color1_var = tk.StringVar(value="White")
        ttk.Button(color1_frame, text="Sample", command=lambda: self.set_color_mode("color1")).pack(side=tk.LEFT, padx=5)
        
        # Color 2 (secondary)
        color2_frame = ttk.Frame(color_frame)
        color2_frame.pack(fill=tk.X, pady=5)
        ttk.Label(color2_frame, text="Color 2 (Secondary):", width=15).pack(side=tk.LEFT)
        self.color2_entry = ttk.Entry(color2_frame, width=30)
        self.color2_entry.pack(side=tk.LEFT, padx=5)
        self.color2_entry.insert(0, "Red")
        self.color2_var = tk.StringVar(value="Red")
        ttk.Button(color2_frame, text="Sample", command=lambda: self.set_color_mode("color2")).pack(side=tk.LEFT, padx=5)
        
        # HSV Range display and adjustment
        hsv_frame = ttk.LabelFrame(main_frame, text="HSV Ranges", padding="10")
        hsv_frame.pack(fill=tk.X, pady=5)
        
        # Color 1 HSV display
        color1_display_frame = ttk.Frame(hsv_frame)
        color1_display_frame.pack(fill=tk.X, pady=5)
        self.color1_hsv_label = ttk.Label(color1_display_frame, text="Color 1 HSV: Not set")
        self.color1_hsv_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(color1_display_frame, text="Fine-tune", command=lambda: self.open_finetune_window("color1")).pack(side=tk.LEFT, padx=5)
        ttk.Button(color1_display_frame, text="Clear", command=lambda: self.clear_color("color1")).pack(side=tk.LEFT, padx=2)
        self.undo1_button = ttk.Button(color1_display_frame, text="Undo", command=lambda: self.undo_color("color1"), state=tk.DISABLED)
        self.undo1_button.pack(side=tk.LEFT, padx=2)
        
        # Color 2 HSV display
        color2_display_frame = ttk.Frame(hsv_frame)
        color2_display_frame.pack(fill=tk.X, pady=5)
        self.color2_hsv_label = ttk.Label(color2_display_frame, text="Color 2 HSV: Not set")
        self.color2_hsv_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(color2_display_frame, text="Fine-tune", command=lambda: self.open_finetune_window("color2")).pack(side=tk.LEFT, padx=5)
        ttk.Button(color2_display_frame, text="Clear", command=lambda: self.clear_color("color2")).pack(side=tk.LEFT, padx=2)
        self.undo2_button = ttk.Button(color2_display_frame, text="Undo", command=lambda: self.undo_color("color2"), state=tk.DISABLED)
        self.undo2_button.pack(side=tk.LEFT, padx=2)
        
        # Presets
        preset_frame = ttk.Frame(main_frame)
        preset_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(preset_frame, text="Preset:").pack(side=tk.LEFT, padx=5)
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(preset_frame, textvariable=self.preset_var, width=20)
        self.preset_combo.pack(side=tk.LEFT, padx=5)
        self.preset_combo.bind("<<ComboboxSelected>>", self.load_preset)
        
        ttk.Button(preset_frame, text="Save Preset", command=self.save_preset).pack(side=tk.LEFT, padx=5)
        ttk.Button(preset_frame, text="Delete Preset", command=self.delete_preset).pack(side=tk.LEFT, padx=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Apply to Analysis", command=self.apply_to_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Copy HSV Code", command=self.copy_hsv_code).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.root.destroy).pack(side=tk.LEFT, padx=5)
        
        # Load existing presets
        self.load_presets_list()
        
    def load_video(self):
        filename = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if filename:
            self.video_path = filename
            self.cap = cv2.VideoCapture(filename)
            if self.cap.isOpened():
                self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.current_frame_num = 0
                self.status_label.config(text=f"Video loaded: {os.path.basename(filename)}")
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame.copy()
                    self.hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    self.display_frame(frame)
            else:
                messagebox.showerror("Error", "Could not open video file")
                
    def load_image(self):
        filename = filedialog.askopenfilename(
            title="Select Image File",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if filename:
            frame = cv2.imread(filename)
            if frame is not None:
                self.display_frame(frame)
                self.status_label.config(text=f"Image loaded: {os.path.basename(filename)}")
            else:
                messagebox.showerror("Error", "Could not load image")
                
    def grab_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.display_frame(frame)
                self.status_label.config(text="Frame grabbed - Click on the ball to sample colors")
            else:
                messagebox.showwarning("Warning", "Could not read frame from video")
        else:
            messagebox.showwarning("Warning", "No video loaded. Please load a video first.")
                
    def display_frame(self, frame):
        if frame is None:
            return
        self.current_frame = frame.copy()
        self.hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Resize for display if too large
        display_frame = frame.copy()
        max_width, max_height = 800, 450
        h, w = display_frame.shape[:2]
        
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
            # Fallback: use cv2.imencode to create image data
            # Convert to format tkinter can handle
            _, img_data = cv2.imencode('.png', display_frame)
            import base64
            import io
            img_str = base64.b64encode(img_data).decode()
            self.photo = tk.PhotoImage(data=img_str)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            self.canvas.config(width=display_frame.shape[1], height=display_frame.shape[0])
        
        # Store scale factor for click coordinates
        self.scale_factor = w / display_frame.shape[1]
        
    def set_color_mode(self, color_key):
        self.current_color_mode = color_key
        self.color_names[color_key] = self.color1_entry.get() if color_key == "color1" else self.color2_entry.get()
        self.status_label.config(text=f"Click on {self.color_names[color_key]} part of the ball")
        
    def on_canvas_click(self, event):
        if self.current_frame is None or self.hsv_frame is None:
            return
            
        # Get color mode (default to color1 if not set)
        if not hasattr(self, 'current_color_mode'):
            self.current_color_mode = "color1"
            
        # Convert canvas coordinates to image coordinates
        if hasattr(self, 'scale_factor'):
            x = int(event.x * self.scale_factor)
            y = int(event.y * self.scale_factor)
        else:
            x = int(event.x)
            y = int(event.y)
            
        # Sample HSV values from a small region around click point
        region_size = 10
        x1 = max(0, x - region_size)
        y1 = max(0, y - region_size)
        x2 = min(self.hsv_frame.shape[1], x + region_size)
        y2 = min(self.hsv_frame.shape[0], y + region_size)
        
        region = self.hsv_frame[y1:y2, x1:x2]
        
        # Store original click position and region for fine-tuning
        self.original_click_pos = (x, y)
        self.zoom_region = region
        if hasattr(self, 'current_frame') and self.current_frame is not None:
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
        color_name = self.color_names[self.current_color_mode]
        self.status_label.config(text=f"{color_name} selected - Use arrow keys to fine-tune, then click/Enter to confirm")
        
        # Draw marker on canvas
        self.canvas.create_oval(event.x - 5, event.y - 5, event.x + 5, event.y + 5,
                              outline="yellow", width=2)
            
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
    
    def update_color_swatch(self, color_key, bgr_color, h, s, v):
        """Update color swatch for the selected color"""
        # Convert BGR to RGB for tkinter
        rgb_color = f"#{bgr_color[2]:02x}{bgr_color[1]:02x}{bgr_color[0]:02x}"
        
        swatch = self.color1_swatch if color_key == "color1" else self.color2_swatch
        swatch.delete("all")
        swatch.create_rectangle(0, 0, 100, 30, fill=rgb_color, outline="black", width=2)
        
        # Update HSV display
        self.hsv_display_label.config(text=f"HSV: H={h}, S={s}, V={v}\nRGB: R={bgr_color[2]}, G={bgr_color[1]}, B={bgr_color[0]}")
    
    def on_zoom_key(self, event):
        """Handle arrow key navigation in zoom area"""
        # Only handle if in fine-tuning mode and zoom canvas has focus or is visible
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
        
        # Calculate HSV range based on sampled color (same logic as before)
        if self.current_color_mode == "color1":
            # White or light colors - adjusted for indoor lighting
            if v_median > 200:  # Bright color (likely white)
                # For indoor/artificial lighting, white may appear more saturated
                # Allow higher saturation if the sampled value is high
                max_sat = max(30, min(100, s_median + 20))  # Allow up to 100 saturation if sampled is high
                lower = np.array([0, 0, max(180, v_median - 30)])
                upper = np.array([180, max_sat, 255])
            else:
                # General color range
                lower = np.array([max(0, h_median - 10), max(50, s_median - 30), max(50, v_median - 30)])
                upper = np.array([min(180, h_median + 10), 255, 255])
            
            new_range = {"lower": lower.tolist(), "upper": upper.tolist()}
            # Save to history and store as original if first time
            if self.hsv_ranges[self.current_color_mode] is not None:
                self.save_to_history(self.current_color_mode)
            else:
                # First time sampling - store as original
                self.original_sampled[self.current_color_mode] = copy.deepcopy(new_range)
            self.hsv_ranges[self.current_color_mode] = new_range
            self.update_color_swatch("color1", bgr_color, h_median, s_median, v_median)
        else:
            # Color 2 - specific color (red, pink, etc.)
            if h_median < 10 or h_median > 170:  # Red (wraps around)
                lower1 = np.array([0, max(50, s_median - 30), max(50, v_median - 30)])
                upper1 = np.array([10, 255, 255])
                lower2 = np.array([170, max(50, s_median - 30), max(50, v_median - 30)])
                upper2 = np.array([180, 255, 255])
                new_range = {"lower1": lower1.tolist(), "upper1": upper1.tolist(),
                           "lower2": lower2.tolist(), "upper2": upper2.tolist()}
                # Save to history and store as original if first time
                if self.hsv_ranges["color2"] is not None:
                    self.save_to_history("color2")
                else:
                    self.original_sampled["color2"] = copy.deepcopy(new_range)
                self.hsv_ranges["color2"] = new_range
                self.update_color_swatch("color2", bgr_color, h_median, s_median, v_median)
            else:
                lower = np.array([max(0, h_median - 10), max(50, s_median - 30), max(50, v_median - 30)])
                upper = np.array([min(180, h_median + 10), 255, 255])
                new_range = {"lower": lower.tolist(), "upper": upper.tolist()}
                # Save to history and store as original if first time
                if self.hsv_ranges[self.current_color_mode] is not None:
                    self.save_to_history(self.current_color_mode)
                else:
                    self.original_sampled[self.current_color_mode] = copy.deepcopy(new_range)
                self.hsv_ranges[self.current_color_mode] = new_range
                self.update_color_swatch("color2", bgr_color, h_median, s_median, v_median)
        
        self.update_hsv_display()
        self.update_undo_button_state()
        
        color_name = self.color_names[self.current_color_mode]
        self.status_label.config(text=f"{color_name} sampled: HSV({h_median}, {s_median}, {v_median}) - Fine-tuned")
        
        # Exit fine-tuning mode
        self.fine_tuning_mode = False
    
    def update_hsv_display(self):
        if self.hsv_ranges["color1"]:
            r1 = self.hsv_ranges["color1"]
            self.color1_hsv_label.config(
                text=f"Color 1 HSV: Lower={r1['lower']}, Upper={r1['upper']}"
            )
        if self.hsv_ranges["color2"]:
            r2 = self.hsv_ranges["color2"]
            if "lower2" in r2:
                self.color2_hsv_label.config(
                    text=f"Color 2 HSV: Lower1={r2['lower1']}, Upper1={r2['upper1']}, Lower2={r2['lower2']}, Upper2={r2['upper2']}"
                )
            else:
                self.color2_hsv_label.config(
                    text=f"Color 2 HSV: Lower={r2['lower']}, Upper={r2['upper']}"
                )
                
    def save_preset(self):
        if not self.hsv_ranges["color1"]:
            messagebox.showwarning("Warning", "Please sample at least Color 1")
            return
            
        preset_name = simpledialog.askstring("Save Preset", "Enter preset name:")
        if preset_name:
            preset = {
                "color1_name": self.color1_entry.get(),
                "color2_name": self.color2_entry.get(),
                "hsv_ranges": self.hsv_ranges
            }
            
            presets_file = "ball_color_presets.json"
            presets = {}
            if os.path.exists(presets_file):
                with open(presets_file, 'r') as f:
                    presets = json.load(f)
                    
            presets[preset_name] = preset
            with open(presets_file, 'w') as f:
                json.dump(presets, f, indent=2)
                
            self.load_presets_list()
            self.preset_var.set(preset_name)
            messagebox.showinfo("Success", f"Preset '{preset_name}' saved!")
            
    def load_preset(self, event=None):
        preset_name = self.preset_var.get()
        if not preset_name:
            return
            
        presets_file = "ball_color_presets.json"
        if os.path.exists(presets_file):
            with open(presets_file, 'r') as f:
                presets = json.load(f)
                
            if preset_name in presets:
                preset = presets[preset_name]
                self.color1_entry.delete(0, tk.END)
                self.color1_entry.insert(0, preset.get("color1_name", "White"))
                self.color2_entry.delete(0, tk.END)
                self.color2_entry.insert(0, preset.get("color2_name", "Red"))
                self.hsv_ranges = preset["hsv_ranges"]
                self.update_hsv_display()
                self.status_label.config(text=f"Preset '{preset_name}' loaded")
                
    def delete_preset(self):
        preset_name = self.preset_var.get()
        if not preset_name:
            return
            
        if messagebox.askyesno("Confirm", f"Delete preset '{preset_name}'?"):
            presets_file = "ball_color_presets.json"
            if os.path.exists(presets_file):
                with open(presets_file, 'r') as f:
                    presets = json.load(f)
                    
                if preset_name in presets:
                    del presets[preset_name]
                    with open(presets_file, 'w') as f:
                        json.dump(presets, f, indent=2)
                    self.load_presets_list()
                    self.preset_var.set("")
                    messagebox.showinfo("Success", f"Preset '{preset_name}' deleted")
                    
    def load_presets_list(self):
        presets_file = "ball_color_presets.json"
        presets_list = []
        if os.path.exists(presets_file):
            with open(presets_file, 'r') as f:
                presets = json.load(f)
                presets_list = list(presets.keys())
        self.preset_combo['values'] = presets_list
        
    def copy_hsv_code(self):
        if not self.hsv_ranges["color1"]:
            messagebox.showwarning("Warning", "Please sample at least Color 1")
            return
            
        code = self.generate_hsv_code()
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        messagebox.showinfo("Copied", "HSV code copied to clipboard!")
        
    def generate_hsv_code(self):
        code = "# HSV ranges for ball detection\n"
        if self.hsv_ranges["color1"]:
            r1 = self.hsv_ranges["color1"]
            code += f"lower_color1 = np.array({r1['lower']})\n"
            code += f"upper_color1 = np.array({r1['upper']})\n"
        if self.hsv_ranges["color2"]:
            r2 = self.hsv_ranges["color2"]
            if "lower2" in r2:
                code += f"lower_color2_1 = np.array({r2['lower1']})\n"
                code += f"upper_color2_1 = np.array({r2['upper1']})\n"
                code += f"lower_color2_2 = np.array({r2['lower2']})\n"
                code += f"upper_color2_2 = np.array({r2['upper2']})\n"
            else:
                code += f"lower_color2 = np.array({r2['lower']})\n"
                code += f"upper_color2 = np.array({r2['upper']})\n"
        return code
        
    def open_finetune_window(self, color_key):
        """Open fine-tuning window for HSV ranges"""
        if color_key not in self.hsv_ranges or not self.hsv_ranges[color_key]:
            messagebox.showwarning("Warning", f"Please sample {color_key} first")
            return
        
        finetune_window = tk.Toplevel(self.root)
        finetune_window.title(f"Fine-tune {color_key.upper()} HSV Ranges")
        finetune_window.geometry("600x500")
        
        color_name = self.color1_entry.get() if color_key == "color1" else self.color2_entry.get()
        
        main_frame = ttk.Frame(finetune_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=f"Adjust HSV ranges for {color_name}", 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        # Get current ranges
        current_range = self.hsv_ranges[color_key]
        
        # Check if it's a two-range (red) or single range
        if "lower2" in current_range:
            # Two-range color (red)
            self.create_finetune_controls(main_frame, color_key, current_range, 
                                        "Range 1 (Lower Hue)", "lower1", "upper1")
            self.create_finetune_controls(main_frame, color_key, current_range,
                                        "Range 2 (Upper Hue)", "lower2", "upper2")
        else:
            # Single range
            self.create_finetune_controls(main_frame, color_key, current_range,
                                        "HSV Range", "lower", "upper")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Apply", command=lambda: self.apply_finetune(finetune_window, color_key)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset to Sampled", command=lambda: self.reset_to_sampled(color_key)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=finetune_window.destroy).pack(side=tk.LEFT, padx=5)
        
        # Store window reference
        self.finetune_windows = getattr(self, 'finetune_windows', {})
        self.finetune_windows[color_key] = finetune_window
    
    def create_finetune_controls(self, parent, color_key, current_range, title, lower_key, upper_key):
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
            if color_key not in self.finetune_vars:
                self.finetune_vars[color_key] = {}
            if lower_key not in self.finetune_vars[color_key]:
                self.finetune_vars[color_key][lower_key] = {}
            self.finetune_vars[color_key][lower_key][idx] = var
        
        # HSV Upper controls
        ttk.Label(range_frame, text="Upper:", font=("Arial", 9, "bold")).grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        
        for i, (label, idx) in enumerate([("H:", 0), ("S:", 1), ("V:", 2)]):
            ttk.Label(range_frame, text=label).grid(row=3, column=i*2, padx=5, pady=2)
            var = tk.IntVar(value=int(upper[idx]))
            spinbox = ttk.Spinbox(range_frame, from_=0, to=255, textvariable=var, width=8)
            spinbox.grid(row=3, column=i*2+1, padx=5, pady=2)
            
            # Store reference
            if upper_key not in self.finetune_vars[color_key]:
                self.finetune_vars[color_key][upper_key] = {}
            self.finetune_vars[color_key][upper_key][idx] = var
    
    def apply_finetune(self, window, color_key):
        """Apply fine-tuned HSV ranges"""
        if not hasattr(self, 'finetune_vars') or color_key not in self.finetune_vars:
            return
        
        vars_dict = self.finetune_vars[color_key]
        current_range = self.hsv_ranges[color_key].copy()
        
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
        self.save_to_history(color_key)
        self.hsv_ranges[color_key] = current_range
        self.update_hsv_display()
        self.update_undo_button_state()
        
        messagebox.showinfo("Applied", f"{color_key.upper()} HSV ranges updated!")
        window.destroy()
    
    def save_to_history(self, color_key):
        """Save current HSV range to history before changing"""
        if self.hsv_ranges[color_key] is not None:
            # Deep copy current range
            current = copy.deepcopy(self.hsv_ranges[color_key])
            self.history[color_key].append(current)
            # Limit history size
            if len(self.history[color_key]) > self.max_history:
                self.history[color_key] = self.history[color_key][-self.max_history:]
    
    def clear_color(self, color_key):
        """Clear the selected color's HSV ranges"""
        if self.hsv_ranges[color_key] is not None:
            # Save to history before clearing
            self.save_to_history(color_key)
            self.hsv_ranges[color_key] = None
            self.original_sampled[color_key] = None
            
            # Clear swatch
            swatch = self.color1_swatch if color_key == "color1" else self.color2_swatch
            swatch.delete("all")
            swatch.create_rectangle(0, 0, 100, 30, fill="gray", outline="black", width=2)
            
            # Update display
            if color_key == "color1":
                self.color1_hsv_label.config(text="Color 1 HSV: Not set")
            else:
                self.color2_hsv_label.config(text="Color 2 HSV: Not set")
            
            self.update_hsv_display()
            self.update_undo_button_state()
            self.status_label.config(text=f"{color_key.upper()} cleared")
    
    def undo_color(self, color_key):
        """Undo the last change to a color's HSV range"""
        if len(self.history[color_key]) == 0:
            return
        
        # Restore previous value from history
        previous = self.history[color_key].pop()
        self.hsv_ranges[color_key] = previous
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
            swatch = self.color1_swatch if color_key == "color1" else self.color2_swatch
            rgb_color = f"#{bgr_color[2]:02x}{bgr_color[1]:02x}{bgr_color[0]:02x}"
            swatch.delete("all")
            swatch.create_rectangle(0, 0, 100, 30, fill=rgb_color, outline="black", width=2)
        
        self.status_label.config(text=f"{color_key.upper()} undone")
    
    def update_undo_button_state(self):
        """Update the enabled/disabled state of undo buttons"""
        if hasattr(self, 'undo1_button'):
            self.undo1_button.config(state=tk.NORMAL if len(self.history["color1"]) > 0 else tk.DISABLED)
        if hasattr(self, 'undo2_button'):
            self.undo2_button.config(state=tk.NORMAL if len(self.history["color2"]) > 0 else tk.DISABLED)
    
    def reset_to_sampled(self, color_key):
        """Reset HSV ranges to originally sampled values"""
        if self.original_sampled[color_key] is not None:
            self.save_to_history(color_key)
            self.hsv_ranges[color_key] = copy.deepcopy(self.original_sampled[color_key])
            self.update_hsv_display()
            self.update_undo_button_state()
            self.status_label.config(text=f"{color_key.upper()} reset to original sampled values")
        else:
            messagebox.showinfo("Info", "No original sampled values found. Please re-sample the color.")
    
    def apply_to_analysis(self):
        if not self.hsv_ranges["color1"]:
            messagebox.showwarning("Warning", "Please sample at least Color 1")
            return
            
        if self.callback:
            self.callback(self.hsv_ranges, self.color1_entry.get(), self.color2_entry.get())
        messagebox.showinfo("Applied", "HSV ranges applied to analysis script!")
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = BallColorDetector(root)
    root.mainloop()

