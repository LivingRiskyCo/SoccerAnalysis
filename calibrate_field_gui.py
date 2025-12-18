"""
Field Calibration GUI Tool
Interactive GUI for calibrating field boundaries with visual feedback and undo capability
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import cv2
import numpy as np
import os
import json

# Try to import PIL/Pillow for image display
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL/Pillow not available. Image display may be limited.")


class FieldCalibrationGUI:
    def __init__(self, parent=None, video_path=None):
        # Use parent window if provided, otherwise create new root
        if parent:
            self.root = parent
            # Update parent window properties instead of creating new one
            self.root.title("Field Calibration Tool")
            self.root.geometry("1800x1000")  # Increased size for better visibility
            self.root.resizable(True, True)
        else:
            self.root = tk.Tk()
            self.root.title("Field Calibration Tool")
            self.root.geometry("1800x1000")  # Increased size for better visibility
            self.root.resizable(True, True)
        
        # Ensure window opens on top
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(200, lambda: self.root.attributes('-topmost', False))
        
        # Variables
        self.video_path = video_path  # Video path passed from main GUI
        self.image_path = None
        self.original_image = None
        self.original_frame_bgr = None  # Store original BGR frame from video for saving/preview
        self.display_image = None
        self.click_points = []
        self.calibration_mode = "4-point"  # "4-point", "8-point", "12-point", or "16-point"
        self.field_length = 40.0
        self.field_width = 20.0
        
        # Reference measurements (for better calibration accuracy)
        self.reference_measurements = []  # List of dicts: {type, points, dimensions, label}
        self.selected_point_index = None  # For manual adjustment
        self.adjustment_mode = False
        self._adding_measurement = False  # Flag for adding reference measurements
        
        # Goal area designation
        self.goal_areas = {}  # 'goal_1', 'goal_2' -> {'points': [(x,y), ...], 'type': 'rectangle' or 'polygon'}
        self.goal_designation_mode = False  # True when in goal designation mode
        self.current_goal_name = None
        self.current_goal_points = []
        self.goal_counter = 1
        self.goal_designation_type = "rectangle"  # "rectangle" or "polygon"
        
        # Create widgets
        self.create_widgets()
        
        # Auto-load video first frame if video path provided
        if self.video_path and os.path.exists(self.video_path):
            self.load_video_first_frame(self.video_path)
        
        # Auto-load existing calibration if available (silent, no messagebox)
        self.auto_load_calibration()
    
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top section: File selection and settings
        top_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # File selection
        file_frame = ttk.Frame(top_frame)
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file_frame, text="Video/Image:").pack(side=tk.LEFT, padx=5)
        self.image_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.image_path_var, width=50, state="readonly").pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Load Video (First Frame)", command=self.browse_video).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Load Image", command=self.browse_image).pack(side=tk.LEFT, padx=5)
        
        # Field dimensions
        dims_frame = ttk.Frame(top_frame)
        dims_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(dims_frame, text="Field Length (meters):").pack(side=tk.LEFT, padx=5)
        self.length_var = tk.DoubleVar(value=40.0)
        length_spinbox = ttk.Spinbox(dims_frame, from_=10, to=200, increment=1, textvariable=self.length_var, width=10)
        length_spinbox.pack(side=tk.LEFT, padx=5)
        length_spinbox.bind('<KeyRelease>', lambda e: self.update_field_plot())
        length_spinbox.bind('<ButtonRelease>', lambda e: self.update_field_plot())
        # Also bind to variable change
        self.length_var.trace_add('write', lambda *args: self.update_field_plot())
        
        ttk.Label(dims_frame, text="Field Width (meters):").pack(side=tk.LEFT, padx=5)
        self.width_var = tk.DoubleVar(value=20.0)
        width_spinbox = ttk.Spinbox(dims_frame, from_=5, to=100, increment=1, textvariable=self.width_var, width=10)
        width_spinbox.pack(side=tk.LEFT, padx=5)
        width_spinbox.bind('<KeyRelease>', lambda e: self.update_field_plot())
        width_spinbox.bind('<ButtonRelease>', lambda e: self.update_field_plot())
        # Also bind to variable change
        self.width_var.trace_add('write', lambda *args: self.update_field_plot())
        
        # Calibration mode
        mode_frame = ttk.Frame(top_frame)
        mode_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(mode_frame, text="Calibration Mode:").pack(side=tk.LEFT, padx=5)
        self.mode_var = tk.StringVar(value="4-point")
        ttk.Radiobutton(mode_frame, text="4-Point", variable=self.mode_var, 
                       value="4-point", command=self.on_mode_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="8-Point", variable=self.mode_var, 
                       value="8-point", command=self.on_mode_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="12-Point (Better Perspective)", variable=self.mode_var, 
                       value="12-point", command=self.on_mode_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="16-Point (Best Perspective)", variable=self.mode_var, 
                       value="16-point", command=self.on_mode_change).pack(side=tk.LEFT, padx=5)
        
        # Middle section: Image display and instructions
        middle_frame = ttk.Frame(main_frame)
        middle_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Left: Instructions and controls
        left_panel = ttk.LabelFrame(middle_frame, text="Instructions", padding="10", width=380)  # Increased width for button visibility
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        self.instructions_text = tk.Text(left_panel, height=20, width=42, wrap=tk.WORD, state=tk.DISABLED)  # Increased width
        self.instructions_text.pack(fill=tk.BOTH, expand=True)
        
        # Control buttons - arranged in 2x2 grid for better visibility
        control_frame = ttk.Frame(left_panel)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        # First row of buttons
        button_row1 = ttk.Frame(control_frame)
        button_row1.pack(fill=tk.X, pady=2)
        ttk.Button(button_row1, text="Undo Last Point", command=self.undo_last_point).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(button_row1, text="Clear All", command=self.clear_all_points).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # Second row of buttons
        button_row2 = ttk.Frame(control_frame)
        button_row2.pack(fill=tk.X, pady=2)
        ttk.Button(button_row2, text="Adjust Points", command=self.toggle_adjustment_mode).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(button_row2, text="Load Calibration", command=self.load_existing_calibration).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # Reference measurements section
        ref_frame = ttk.LabelFrame(left_panel, text="Reference Measurements", padding="5")
        ref_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Add measurement buttons
        meas_buttons_frame = ttk.Frame(ref_frame)
        meas_buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(meas_buttons_frame, text="Goal Box", command=lambda: self.add_reference_measurement("goal_box")).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(meas_buttons_frame, text="Penalty Area", command=lambda: self.add_reference_measurement("penalty_area")).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        meas_buttons_frame2 = ttk.Frame(ref_frame)
        meas_buttons_frame2.pack(fill=tk.X, pady=5)
        
        ttk.Button(meas_buttons_frame2, text="Center Circle", command=lambda: self.add_reference_measurement("center_circle")).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(meas_buttons_frame2, text="Custom Distance", command=lambda: self.add_reference_measurement("custom")).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # List of measurements
        self.measurements_listbox = tk.Listbox(ref_frame, height=4)
        self.measurements_listbox.pack(fill=tk.X, pady=5)
        self.measurements_listbox.bind("<Double-Button-1>", self.edit_measurement)
        
        ttk.Button(ref_frame, text="Remove Selected", command=self.remove_measurement).pack(fill=tk.X, pady=2)
        
        # Goal Area Designation section
        goal_frame = ttk.LabelFrame(left_panel, text="Goal Area Designation", padding="5")
        goal_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Mode toggle
        mode_toggle_frame = ttk.Frame(goal_frame)
        mode_toggle_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(mode_toggle_frame, text="Mode:").pack(side=tk.LEFT, padx=2)
        self.goal_mode_var = tk.StringVar(value="calibration")
        ttk.Radiobutton(mode_toggle_frame, text="Calibration", variable=self.goal_mode_var, 
                       value="calibration", command=self.on_goal_mode_change).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(mode_toggle_frame, text="Goal Areas", variable=self.goal_mode_var, 
                       value="goals", command=self.on_goal_mode_change).pack(side=tk.LEFT, padx=2)
        
        # Goal designation type
        goal_type_frame = ttk.Frame(goal_frame)
        goal_type_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(goal_type_frame, text="Goal Type:").pack(side=tk.LEFT, padx=2)
        self.goal_type_var = tk.StringVar(value="rectangle")
        ttk.Radiobutton(goal_type_frame, text="Rectangle", variable=self.goal_type_var, 
                       value="rectangle", command=self.on_goal_type_change).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(goal_type_frame, text="Polygon", variable=self.goal_type_var, 
                       value="polygon", command=self.on_goal_type_change).pack(side=tk.LEFT, padx=2)
        
        # Goal area buttons
        goal_buttons_frame = ttk.Frame(goal_frame)
        goal_buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(goal_buttons_frame, text="Start New Goal", command=self.start_new_goal).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(goal_buttons_frame, text="Finish Goal", command=self.finish_current_goal).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        goal_buttons_frame2 = ttk.Frame(goal_frame)
        goal_buttons_frame2.pack(fill=tk.X, pady=5)
        
        ttk.Button(goal_buttons_frame2, text="Clear All Goals", command=self.clear_all_goals).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(goal_buttons_frame2, text="Remove Last Goal", command=self.remove_last_goal).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # List of goals
        self.goals_listbox = tk.Listbox(goal_frame, height=3)
        self.goals_listbox.pack(fill=tk.X, pady=5)
        self.goals_listbox.bind("<Double-Button-1>", self.edit_goal)
        
        ttk.Button(goal_frame, text="Save Goal Areas", command=self.save_goal_areas).pack(fill=tk.X, pady=2)
        ttk.Button(goal_frame, text="Load Goal Areas", command=self.load_goal_areas).pack(fill=tk.X, pady=2)
        
        # Right: Split into image canvas and field plot
        right_container = ttk.Frame(middle_frame)
        right_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Top: Image canvas
        right_panel = ttk.LabelFrame(right_container, text="Field Image", padding="10")
        right_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Canvas with scrollbars
        canvas_frame = ttk.Frame(right_panel)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg="gray", cursor="crosshair")
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)  # Right-click for undo
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)  # For manual adjustment
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        
        # Bottom: Field plot visualization
        field_plot_panel = ttk.LabelFrame(right_container, text="Current Field Plot", padding="10")
        field_plot_panel.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False, pady=(0, 0))
        field_plot_panel.config(height=250)  # Fixed height for field plot
        
        # Field plot canvas
        self.field_plot_canvas = tk.Canvas(field_plot_panel, bg="white", height=230)
        self.field_plot_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Initialize field plot
        self.update_field_plot()
        
        # Bottom section: Status and actions
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Status
        self.status_label = ttk.Label(bottom_frame, text="Ready - Load an image to begin", 
                                      font=("Arial", 10))
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Action buttons
        action_frame = ttk.Frame(bottom_frame)
        action_frame.pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(action_frame, text="Preview Transformation", command=self.preview_transformation).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Save Calibration", command=self.save_calibration).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Close", command=self.root.destroy).pack(side=tk.LEFT, padx=5)
        
        self.update_instructions()
    
    def browse_video(self):
        """Browse for video file and load first frame"""
        filename = filedialog.askopenfilename(
            title="Select Video File (First Frame Will Be Used)",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v *.mpg *.mpeg"), ("All files", "*.*")]
        )
        if filename:
            self.load_video_first_frame(filename)
    
    def load_video_first_frame(self, video_path):
        """Load first frame from video file"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                messagebox.showerror("Error", f"Could not open video file: {video_path}")
                return
            
            # Read first frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                messagebox.showerror("Error", "Could not read first frame from video")
                return
            
            # Store original BGR frame for saving/preview operations
            self.original_frame_bgr = frame.copy()
            
            # Convert BGR to RGB for display
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.original_image = frame_rgb.copy()
            
            # Store video path
            self.video_path = video_path
            self.image_path = None  # Clear image path since we're using video
            
            # Resize for display (max 1200px width)
            max_width = 1200
            height, width = frame_rgb.shape[:2]
            if width > max_width:
                scale = max_width / width
                new_width = max_width
                new_height = int(height * scale)
                frame_rgb = cv2.resize(frame_rgb, (new_width, new_height))
            
            self.display_image = frame_rgb
            self.click_points = []  # Reset points
            
            # Update UI
            self.image_path_var.set(f"Video: {os.path.basename(video_path)} (First Frame)")
            
            # Display image on canvas
            self.update_canvas()
            self.update_status(f"Loaded first frame from video: {os.path.basename(video_path)}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load video: {str(e)}")
    
    def browse_image(self):
        """Browse for reference image"""
        filename = filedialog.askopenfilename(
            title="Select Reference Image with Full Field Visible",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*")]
        )
        if filename:
            self.load_image(filename)
    
    def load_image(self, image_path):
        """Load and display image"""
        try:
            self.image_path = image_path
            self.image_path_var.set(os.path.basename(image_path))
            
            # Load image with OpenCV
            img_bgr = cv2.imread(image_path)
            if img_bgr is None:
                messagebox.showerror("Error", f"Could not load image: {image_path}")
                return
            
            # Store original BGR for saving/preview operations
            self.original_frame_bgr = img_bgr.copy()
            
            # Convert BGR to RGB for display
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            self.original_image = img_rgb.copy()
            
            # Clear video path since we're using image
            self.video_path = None
            
            # Resize for display (max 1200px width)
            max_width = 1200
            height, width = img_rgb.shape[:2]
            if width > max_width:
                scale = max_width / width
                new_width = max_width
                new_height = int(height * scale)
                img_rgb = cv2.resize(img_rgb, (new_width, new_height))
            
            self.display_image = img_rgb
            self.click_points = []  # Reset points
            
            # Display image on canvas
            self.update_canvas()
            self.update_status(f"Image loaded: {os.path.basename(image_path)}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {str(e)}")
    
    def update_canvas(self):
        """Update canvas with image and points"""
        if self.display_image is None:
            return
        
        # Create image with points drawn
        img_with_points = self.display_image.copy()
        
        # Draw points and lines
        if len(self.click_points) > 0:
            # Draw all points
            for i, (x, y) in enumerate(self.click_points):
                # Highlight selected point in adjustment mode
                if self.adjustment_mode and i == self.selected_point_index:
                    color = (0, 255, 255)  # Yellow for selected
                    cv2.circle(img_with_points, (int(x), int(y)), 15, color, -1)
                    cv2.circle(img_with_points, (int(x), int(y)), 20, color, 3)
                else:
                    color = (0, 255, 0)  # Green
                    cv2.circle(img_with_points, (int(x), int(y)), 10, color, -1)
                    cv2.circle(img_with_points, (int(x), int(y)), 15, color, 2)
                
                # Draw label
                label = self.get_point_label(i)
                cv2.putText(img_with_points, label, (int(x) + 20, int(y) - 5), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # Draw reference measurements
        for meas in self.reference_measurements:
            self.draw_measurement(img_with_points, meas)
        
        # Draw goal areas
        for goal_name, goal_data in self.goal_areas.items():
            points = goal_data['points']
            goal_type = goal_data.get('type', 'rectangle')
            
            # Convert display coordinates to image coordinates for drawing
            if len(points) >= 2:
                if goal_type == 'rectangle' and len(points) >= 2:
                    pt1 = tuple(map(int, points[0]))
                    pt2 = tuple(map(int, points[1]))
                    cv2.rectangle(img_with_points, pt1, pt2, (0, 255, 255), 2)  # Cyan for goals
                    cv2.putText(img_with_points, goal_name, (pt1[0], pt1[1] - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                elif goal_type == 'polygon' and len(points) >= 3:
                    pts = np.array(points, dtype=np.int32)
                    cv2.polylines(img_with_points, [pts], True, (0, 255, 255), 2)  # Cyan for goals
                    cv2.putText(img_with_points, goal_name, (int(points[0][0]), int(points[0][1]) - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Draw current goal being defined
        if self.current_goal_name and len(self.current_goal_points) > 0:
            if self.goal_designation_type == 'rectangle' and len(self.current_goal_points) >= 2:
                pt1 = tuple(map(int, self.current_goal_points[0]))
                pt2 = tuple(map(int, self.current_goal_points[-1]))
                cv2.rectangle(img_with_points, pt1, pt2, (255, 0, 0), 2)  # Red for current
            elif self.goal_designation_type == 'polygon' and len(self.current_goal_points) >= 2:
                pts = np.array(self.current_goal_points, dtype=np.int32)
                cv2.polylines(img_with_points, [pts], False, (255, 0, 0), 2)  # Red for current
            
            # Draw points
            for pt in self.current_goal_points:
                cv2.circle(img_with_points, tuple(map(int, pt)), 5, (255, 0, 0), -1)
            
            # Draw lines based on mode
            if self.calibration_mode == "4-point":
                if len(self.click_points) >= 2:
                    for i in range(len(self.click_points) - 1):
                        pt1 = tuple(map(int, self.click_points[i]))
                        pt2 = tuple(map(int, self.click_points[i + 1]))
                        cv2.line(img_with_points, pt1, pt2, (0, 255, 0), 2)
                if len(self.click_points) == 4:
                    # Close the rectangle
                    pt1 = tuple(map(int, self.click_points[3]))
                    pt2 = tuple(map(int, self.click_points[0]))
                    cv2.line(img_with_points, pt1, pt2, (0, 255, 0), 2)
            elif self.calibration_mode == "8-point":
                if len(self.click_points) >= 4:
                    # Draw outer rectangle
                    corners = self.click_points[:4]
                    for i in range(4):
                        pt1 = tuple(map(int, corners[i]))
                        pt2 = tuple(map(int, corners[(i + 1) % 4]))
                        cv2.line(img_with_points, pt1, pt2, (0, 255, 0), 2)
                
                # Draw mid-point connections to adjacent corners (for perspective stretching)
                if len(self.click_points) >= 5:
                    corners = self.click_points[:4]
                    mid_points = self.click_points[4:8] if len(self.click_points) >= 8 else self.click_points[4:]
                    
                    # TM (index 4) - connects to TL (0) and TR (1)
                    if len(mid_points) > 0:
                        tm = tuple(map(int, mid_points[0]))
                        tl = tuple(map(int, corners[0]))
                        tr = tuple(map(int, corners[1]))
                        cv2.line(img_with_points, tm, tl, (255, 255, 0), 1)
                        cv2.line(img_with_points, tm, tr, (255, 255, 0), 1)
                    
                    # RM (index 5) - connects to TR (1) and BR (2)
                    if len(mid_points) > 1:
                        rm = tuple(map(int, mid_points[1]))
                        tr = tuple(map(int, corners[1]))
                        br = tuple(map(int, corners[2]))
                        cv2.line(img_with_points, rm, tr, (255, 255, 0), 1)
                        cv2.line(img_with_points, rm, br, (255, 255, 0), 1)
                    
                    # BM (index 6) - connects to BR (2) and BL (3)
                    if len(mid_points) > 2:
                        bm = tuple(map(int, mid_points[2]))
                        br = tuple(map(int, corners[2]))
                        bl = tuple(map(int, corners[3]))
                        cv2.line(img_with_points, bm, br, (255, 255, 0), 1)
                        cv2.line(img_with_points, bm, bl, (255, 255, 0), 1)
                    
                    # LM (index 7) - connects to BL (3) and TL (0) - THIS IS THE KEY CONNECTION
                    if len(mid_points) > 3:
                        lm = tuple(map(int, mid_points[3]))
                        bl = tuple(map(int, corners[3]))
                        tl = tuple(map(int, corners[0]))
                        cv2.line(img_with_points, lm, bl, (255, 255, 0), 1)
                        cv2.line(img_with_points, lm, tl, (255, 255, 0), 1)  # LM to TL connection
            
            elif self.calibration_mode in ["12-point", "16-point"]:
                # For 12-point and 16-point modes, draw polygon connecting all points
                if len(self.click_points) >= 4:
                    # Draw outer rectangle from first 4 points
                    corners = self.click_points[:4]
                    for i in range(4):
                        pt1 = tuple(map(int, corners[i]))
                        pt2 = tuple(map(int, corners[(i + 1) % 4]))
                        cv2.line(img_with_points, pt1, pt2, (0, 255, 0), 2)
                    
                    # Draw connections from edge points to corners
                    if len(self.click_points) > 4:
                        edge_points = self.click_points[4:]
                        corners = self.click_points[:4]
                        
                        # Connect edge points to their adjacent corners
                        # Top edge points connect to TL and TR
                        # Right edge points connect to TR and BR
                        # Bottom edge points connect to BR and BL
                        # Left edge points connect to BL and TL
                        
                        num_per_edge = (len(self.click_points) - 4) // 4  # Points per edge
                        for i, edge_pt in enumerate(edge_points):
                            edge_idx = i // num_per_edge if num_per_edge > 0 else 0
                            edge_pt_int = tuple(map(int, edge_pt))
                            
                            # Determine which corners this edge point connects to
                            if edge_idx == 0:  # Top edge
                                tl = tuple(map(int, corners[0]))
                                tr = tuple(map(int, corners[1]))
                                cv2.line(img_with_points, edge_pt_int, tl, (255, 255, 0), 1)
                                cv2.line(img_with_points, edge_pt_int, tr, (255, 255, 0), 1)
                            elif edge_idx == 1:  # Right edge
                                tr = tuple(map(int, corners[1]))
                                br = tuple(map(int, corners[2]))
                                cv2.line(img_with_points, edge_pt_int, tr, (255, 255, 0), 1)
                                cv2.line(img_with_points, edge_pt_int, br, (255, 255, 0), 1)
                            elif edge_idx == 2:  # Bottom edge
                                br = tuple(map(int, corners[2]))
                                bl = tuple(map(int, corners[3]))
                                cv2.line(img_with_points, edge_pt_int, br, (255, 255, 0), 1)
                                cv2.line(img_with_points, edge_pt_int, bl, (255, 255, 0), 1)
                            elif edge_idx == 3:  # Left edge
                                bl = tuple(map(int, corners[3]))
                                tl = tuple(map(int, corners[0]))
                                cv2.line(img_with_points, edge_pt_int, bl, (255, 255, 0), 1)
                                cv2.line(img_with_points, edge_pt_int, tl, (255, 255, 0), 1)
                        
                        # Also draw lines connecting edge points on the same edge
                        for edge_idx in range(4):
                            start_idx = 4 + edge_idx * num_per_edge
                            end_idx = start_idx + num_per_edge
                            if end_idx <= len(self.click_points):
                                edge_pts = self.click_points[start_idx:end_idx]
                                for j in range(len(edge_pts) - 1):
                                    pt1 = tuple(map(int, edge_pts[j]))
                                    pt2 = tuple(map(int, edge_pts[j + 1]))
                                    cv2.line(img_with_points, pt1, pt2, (255, 200, 0), 1)
        
        # Convert to PhotoImage for Tkinter
        if not PIL_AVAILABLE:
            messagebox.showerror("Error", "PIL/Pillow is required for image display.\n\nPlease install: pip install Pillow")
            return
        
        img_pil = Image.fromarray(img_with_points)
        self.photo = ImageTk.PhotoImage(image=img_pil)
        
        # Update canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        
        # Update status
        if self.calibration_mode == "4-point":
            max_points = 4
        elif self.calibration_mode == "8-point":
            max_points = 8
        elif self.calibration_mode == "12-point":
            max_points = 12
        elif self.calibration_mode == "16-point":
            max_points = 16
        else:
            max_points = 4
        
        remaining = max_points - len(self.click_points)
        if remaining > 0:
            self.update_status(f"Points: {len(self.click_points)}/{max_points} - Click {remaining} more point(s)")
        else:
            self.update_status(f"All {max_points} points marked! Click 'Save Calibration' when ready.")
    
    def on_canvas_click(self, event):
        """Handle left-click on canvas"""
        if self.display_image is None:
            return
        
        # Get click position relative to canvas
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # Check if in adjustment mode
        if self.adjustment_mode:
            # Find closest point to adjust
            min_dist = float('inf')
            closest_idx = None
            for i, (px, py) in enumerate(self.click_points):
                dist = np.sqrt((x - px)**2 + (y - py)**2)
                if dist < min_dist and dist < 30:  # 30 pixel threshold
                    min_dist = dist
                    closest_idx = i
            
            if closest_idx is not None:
                self.selected_point_index = closest_idx
                self.update_canvas()
                return
        
        # Check if in goal designation mode
        if self.goal_designation_mode:
            self.handle_goal_click(x, y)
            return
        
        # Check if adding reference measurement
        if hasattr(self, '_adding_measurement') and self._adding_measurement:
            self.handle_measurement_click(x, y)
            return
        
        # Normal point clicking
        # Get max points based on mode
        if self.calibration_mode == "4-point":
            max_points = 4
        elif self.calibration_mode == "8-point":
            max_points = 8
        elif self.calibration_mode == "12-point":
            max_points = 12
        elif self.calibration_mode == "16-point":
            max_points = 16
        else:
            max_points = 4
        
        if len(self.click_points) < max_points:
            self.click_points.append([x, y])
            self.update_canvas()
            self.update_instructions()
            self.update_field_plot()  # Update field plot when points are added
        else:
            messagebox.showinfo("Info", f"All {max_points} points already marked. Use 'Undo' to remove points.")
    
    def on_canvas_drag(self, event):
        """Handle mouse drag for manual point adjustment"""
        if self.adjustment_mode and self.selected_point_index is not None:
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)
            self.click_points[self.selected_point_index] = [x, y]
            self.update_canvas()
    
    def on_canvas_release(self, event):
        """Handle mouse release"""
        if self.adjustment_mode:
            self.selected_point_index = None
            self.update_canvas()
            self.update_field_plot()  # Update field plot when points are adjusted
    
    def on_canvas_right_click(self, event):
        """Handle right-click (undo or finish goal)"""
        if self.goal_designation_mode:
            # In goal mode, right-click finishes current goal
            if self.current_goal_name:
                self.finish_current_goal()
        else:
            # In calibration mode, right-click undos last point
            self.undo_last_point()
    
    def undo_last_point(self):
        """Remove last clicked point"""
        # Check if in goal designation mode
        if self.goal_designation_mode:
            if len(self.current_goal_points) > 0:
                self.current_goal_points.pop()
                self.update_canvas()
                if self.current_goal_name:
                    self.update_status(f"Goal {self.current_goal_name}: Removed last point. {len(self.current_goal_points)} point(s) remaining.")
                else:
                    self.update_status("Last goal point removed")
            else:
                self.update_status("No goal points to undo")
        else:
            # Normal calibration mode
            if len(self.click_points) > 0:
                self.click_points.pop()
                self.update_canvas()
                self.update_instructions()
                self.update_field_plot()  # Update field plot when points are removed
                self.update_status("Last point removed")
            else:
                self.update_status("No points to undo")
    
    def clear_all_points(self):
        """Clear all points"""
        # Check if in goal designation mode
        if self.goal_designation_mode:
            if len(self.current_goal_points) > 0:
                if messagebox.askyesno("Confirm", "Clear all points for current goal?"):
                    self.current_goal_points = []
                    self.current_goal_name = None  # Reset current goal
                    self.update_canvas()
                    self.update_status("All goal points cleared")
            else:
                self.update_status("No goal points to clear")
        else:
            # Normal calibration mode
            if len(self.click_points) > 0:
                if messagebox.askyesno("Confirm", "Clear all points?"):
                    self.click_points = []
                    self.update_canvas()
                    self.update_instructions()
                    self.update_field_plot()  # Update field plot when points are cleared
                    self.update_status("All points cleared")
            else:
                self.update_status("No points to clear")
    
    def on_mode_change(self):
        """Handle calibration mode change"""
        self.calibration_mode = self.mode_var.get()
        self.click_points = []  # Reset points when mode changes
        self.update_canvas()
        self.update_instructions()
        self.update_field_plot()  # Update field plot when mode changes
    
    def get_point_label(self, index):
        """Get label for point at index"""
        if self.calibration_mode == "4-point":
            labels = ["TL", "TR", "BR", "BL"]
        elif self.calibration_mode == "8-point":
            labels = ["TL", "TR", "BR", "BL", "TM", "RM", "BM", "LM"]
        elif self.calibration_mode == "12-point":
            # 4 corners + 8 edge points (2 per edge)
            labels = ["TL", "TR", "BR", "BL",  # Corners
                     "T1", "T2",  # Top edge (2 points)
                     "R1", "R2",  # Right edge (2 points)
                     "B1", "B2",  # Bottom edge (2 points)
                     "L1", "L2"]  # Left edge (2 points)
        elif self.calibration_mode == "16-point":
            # 4 corners + 12 edge points (3 per edge)
            labels = ["TL", "TR", "BR", "BL",  # Corners
                     "T1", "T2", "T3",  # Top edge (3 points)
                     "R1", "R2", "R3",  # Right edge (3 points)
                     "B1", "B2", "B3",  # Bottom edge (3 points)
                     "L1", "L2", "L3"]  # Left edge (3 points)
        else:
            labels = ["TL", "TR", "BR", "BL"]
        
        if index < len(labels):
            return labels[index]
        return f"P{index + 1}"
    
    def update_instructions(self):
        """Update instructions text"""
        self.instructions_text.config(state=tk.NORMAL)
        self.instructions_text.delete(1.0, tk.END)
        
        max_points = 4 if self.calibration_mode == "4-point" else 8
        points_clicked = len(self.click_points)
        
        instructions = f"""Field Calibration Instructions

Mode: {self.calibration_mode.upper()}

{"=" * 30}

Current Progress:
{points_clicked}/{max_points} points marked

{"=" * 30}

Instructions:
"""
        
        if self.calibration_mode == "4-point":
            instructions += """
1. Click 4 corners in order:
   • Top-Left (TL)
   • Top-Right (TR)
   • Bottom-Right (BR)
   • Bottom-Left (BL)

2. Right-click or use "Undo" to remove last point

3. Click "Save Calibration" when done
"""
        elif self.calibration_mode == "8-point":
            instructions += """
1. Click 4 corners first:
   • Top-Left (TL)
   • Top-Right (TR)
   • Bottom-Right (BR)
   • Bottom-Left (BL)

2. Then click 4 mid-points:
   • Top-Mid (TM) - middle of top edge
   • Right-Mid (RM) - middle of right edge
   • Bottom-Mid (BM) - middle of bottom edge
   • Left-Mid (LM) - middle of left edge

3. Right-click or use "Undo" to remove last point

4. Click "Save Calibration" when done
"""
        elif self.calibration_mode == "12-point":
            instructions += """
1. Click 4 corners first:
   • Top-Left (TL)
   • Top-Right (TR)
   • Bottom-Right (BR)
   • Bottom-Left (BL)

2. Then click 2 points on each edge:
   • Top edge: T1, T2 (spread along top)
   • Right edge: R1, R2 (spread along right)
   • Bottom edge: B1, B2 (spread along bottom)
   • Left edge: L1, L2 (spread along left)

3. Right-click or use "Undo" to remove last point

4. Click "Save Calibration" when done

Tip: Spread points evenly along each edge for best perspective correction
"""
        elif self.calibration_mode == "16-point":
            instructions += """
1. Click 4 corners first:
   • Top-Left (TL)
   • Top-Right (TR)
   • Bottom-Right (BR)
   • Bottom-Left (BL)

2. Then click 3 points on each edge:
   • Top edge: T1, T2, T3 (spread evenly along top)
   • Right edge: R1, R2, R3 (spread evenly along right)
   • Bottom edge: B1, B2, B3 (spread evenly along bottom)
   • Left edge: L1, L2, L3 (spread evenly along left)

3. Right-click or use "Undo" to remove last point

4. Click "Save Calibration" when done

Tip: Spread points evenly along each edge for best perspective correction
"""
        
        instructions += f"""
{"=" * 30}

Tips:
• Click field corners, not sidelines
• Ensure all corners are visible
• Use "Clear All" to start over
• Preview transformation before saving
"""
        
        self.instructions_text.insert(1.0, instructions)
        self.instructions_text.config(state=tk.DISABLED)
    
    def update_status(self, message):
        """Update status label"""
        self.status_label.config(text=message)
    
    def preview_transformation(self):
        """Preview the transformation"""
        if len(self.click_points) < 4:
            messagebox.showwarning("Warning", "Need at least 4 points to preview transformation")
            return
        
        try:
            # Load original image/frame to get actual coordinates
            if self.original_frame_bgr is None:
                messagebox.showerror("Error", "No image or video frame loaded")
                return
            
            # Use stored original frame (from video or image)
            img_orig = self.original_frame_bgr.copy()
            
            # Calculate scale factor
            orig_height, orig_width = img_orig.shape[:2]
            display_height, display_width = self.display_image.shape[:2]
            scale_x = orig_width / display_width
            scale_y = orig_height / display_height
            
            # Convert display coordinates to original image coordinates
            original_points = []
            for x, y in self.click_points:
                orig_x = x * scale_x
                orig_y = y * scale_y
                original_points.append([orig_x, orig_y])
            
            points = np.array(original_points, dtype=np.float32)
            
            # Define destination points (real-world coordinates)
            length = self.length_var.get()
            width = self.width_var.get()
            
            # Use reference measurements if available for better calibration
            if len(self.reference_measurements) > 0:
                # Build source and destination points from reference measurements
                src_meas_points = []
                dst_meas_points = []
                
                for meas in self.reference_measurements:
                    meas_type = meas["type"]
                    meas_points = np.array(meas["points"], dtype=np.float32)
                    # Convert to original coordinates
                    meas_points_orig = []
                    for px, py in meas_points:
                        orig_x = px * scale_x
                        orig_y = py * scale_y
                        meas_points_orig.append([orig_x, orig_y])
                    meas_points_orig = np.array(meas_points_orig, dtype=np.float32)
                    
                    dims = meas["dimensions"]
                    
                    if meas_type == "goal_box" or meas_type == "penalty_area":
                        # Use corners of the box/area
                        if len(meas_points_orig) >= 4:
                            src_meas_points.extend(meas_points_orig[:4].tolist())
                            # Create destination points based on dimensions
                            meas_length = dims.get("length", 5.0)
                            meas_width = dims.get("width", 2.0)
                            # Position relative to field (assume centered or at goal line)
                            # For now, use as additional constraint points
                            dst_meas_points.extend([
                                [0, 0],
                                [meas_length, 0],
                                [meas_length, meas_width],
                                [0, meas_width]
                            ])
                    
                    elif meas_type == "center_circle":
                        # Use center and radius points
                        if len(meas_points_orig) >= 3:
                            center = meas_points_orig[0]
                            radius_point = meas_points_orig[1]
                            src_meas_points.append(center.tolist())
                            src_meas_points.append(radius_point.tolist())
                            # Destination: center at field center, radius point at known distance
                            radius_m = dims.get("radius", 9.15)
                            dst_meas_points.append([length/2, width/2])
                            dst_meas_points.append([length/2 + radius_m, width/2])
                    
                    elif meas_type == "custom":
                        # Use two points for distance measurement
                        if len(meas_points_orig) >= 2:
                            src_meas_points.extend(meas_points_orig[:2].tolist())
                            distance_m = dims.get("distance", 10.0)
                            dst_meas_points.append([0, 0])
                            dst_meas_points.append([distance_m, 0])
                
                # Combine calibration points with measurement points
                all_src_points = points.tolist() + src_meas_points
                all_dst_points = []
                
                # Destination for calibration points (corners)
                dst_corners = np.array([
                    [0, 0],
                    [length, 0],
                    [length, width],
                    [0, width]
                ], dtype=np.float32).tolist()
                all_dst_points.extend(dst_corners[:len(points)])
                all_dst_points.extend(dst_meas_points)
                
                if len(all_src_points) >= 4:
                    all_src_array = np.array(all_src_points, dtype=np.float32)
                    all_dst_array = np.array(all_dst_points, dtype=np.float32)
                    # Use findHomography with all points for better accuracy
                    H, _ = cv2.findHomography(all_src_array, all_dst_array, cv2.RANSAC, 5.0)
                else:
                    # Fallback to standard method
                    H = cv2.getPerspectiveTransform(points[:4], dst_corners[:4])
            
            # For 4-point: use simple perspective transform
            elif len(points) == 4:
                dst_points = np.array([
                    [0, 0],
                    [length, 0],
                    [length, width],
                    [0, width]
                ], dtype=np.float32)
                H = cv2.getPerspectiveTransform(points, dst_points)
            else:
                # For 8, 12, or 16-point: use findHomography with RANSAC for better accuracy
                # Create destination points for all source points
                dst_corners = np.array([
                    [0, 0],
                    [length, 0],
                    [length, width],
                    [0, width]
                ], dtype=np.float32)
                
                # For additional points, create destination points along edges
                if len(points) > 4:
                    # Build destination points array
                    dst_points = dst_corners.tolist()
                    
                    num_per_edge = (len(points) - 4) // 4  # Points per edge
                    
                    # Top edge points (between TL and TR)
                    for i in range(1, num_per_edge + 1):
                        t = i / (num_per_edge + 1)
                        dst_points.append([length * t, 0])
                    
                    # Right edge points (between TR and BR)
                    for i in range(1, num_per_edge + 1):
                        t = i / (num_per_edge + 1)
                        dst_points.append([length, width * t])
                    
                    # Bottom edge points (between BR and BL)
                    for i in range(1, num_per_edge + 1):
                        t = i / (num_per_edge + 1)
                        dst_points.append([length * (1 - t), width])
                    
                    # Left edge points (between BL and TL)
                    for i in range(1, num_per_edge + 1):
                        t = i / (num_per_edge + 1)
                        dst_points.append([0, width * (1 - t)])
                    
                    dst_points_array = np.array(dst_points, dtype=np.float32)
                    
                    # Use findHomography with RANSAC for robust estimation with all points
                    # This provides better perspective correction with more points
                    H, _ = cv2.findHomography(points, dst_points_array, cv2.RANSAC, 5.0)
                else:
                    H = cv2.getPerspectiveTransform(points, dst_corners)
            
            # Transform image
            if self.display_image is not None:
                h, w = img_orig.shape[:2]
                # Scale output to reasonable size for preview
                scale_factor = 20  # pixels per meter
                output_width = int(length * scale_factor)
                output_height = int(width * scale_factor)
                transformed = cv2.warpPerspective(img_orig, H, (output_width, output_height))
                
                # Show preview
                cv2.imshow("Transformation Preview", transformed)
                cv2.waitKey(0)
                cv2.destroyAllWindows()
                
                messagebox.showinfo("Preview", "Transformation preview shown. Close the preview window to continue.")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to preview transformation: {str(e)}")
    
    def save_calibration(self):
        """Save calibration data"""
        if self.calibration_mode == "4-point":
            max_points = 4
        elif self.calibration_mode == "8-point":
            max_points = 8
        elif self.calibration_mode == "12-point":
            max_points = 12
        elif self.calibration_mode == "16-point":
            max_points = 16
        else:
            max_points = 4
        
        if len(self.click_points) < max_points:
            messagebox.showwarning("Warning", f"Need {max_points} points to save calibration. Currently have {len(self.click_points)}.")
            return
        
        if self.original_frame_bgr is None:
            messagebox.showerror("Error", "No image or video frame loaded")
            return
        
        try:
            # Use stored original frame (from video or image)
            img_orig = self.original_frame_bgr.copy()
            
            # Calculate scale factor
            orig_height, orig_width = img_orig.shape[:2]
            display_height, display_width = self.display_image.shape[:2]
            scale_x = orig_width / display_width
            scale_y = orig_height / display_height
            
            # Convert display coordinates to original image coordinates
            original_points = []
            for x, y in self.click_points:
                orig_x = x * scale_x
                orig_y = y * scale_y
                original_points.append([orig_x, orig_y])
            
            points_array = np.array(original_points, dtype=np.float32)
            
            # Save calibration points
            np.save("calibration.npy", points_array)
            
            # Save metadata
            metadata = {
                'mode': self.calibration_mode,
                'num_points': len(original_points),
                'points': original_points,
                'scale': 1.0
            }
            np.save("calibration_metadata.npy", metadata)
            
            # Save as JSON (newer format)
            json_data = {
                "points": original_points,
                "mode": self.calibration_mode,
                "num_points": len(original_points),
                "reference_measurements": self.reference_measurements,
                "field_length": float(self.length_var.get()),  # Save field length in meters
                "field_width": float(self.width_var.get())      # Save field width in meters
            }
            with open("field_calibration.json", 'w') as f:
                json.dump(json_data, f, indent=4)
            
            # Save field dimensions
            field_dims = {
                'length': self.length_var.get(),
                'width': self.width_var.get(),
                'scale': 1.0,
                'mode': self.calibration_mode
            }
            np.save("field_dimensions.npy", field_dims)
            
            # Save marked image (use original frame)
            img_marked = self.original_frame_bgr.copy()
            for i, (x, y) in enumerate(original_points):
                cv2.circle(img_marked, (int(x), int(y)), 15, (0, 255, 0), -1)
                cv2.circle(img_marked, (int(x), int(y)), 20, (0, 255, 0), 2)
                label = self.get_point_label(i)
                cv2.putText(img_marked, label, (int(x) + 25, int(y) - 5), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.imwrite("calibrated_corners.jpg", img_marked)
            
            # Show success message
            msg = f"""Calibration saved successfully!

Mode: {self.calibration_mode}
Points: {len(original_points)}
Field size: {self.length_var.get()}m x {self.width_var.get()}m

Files saved:
• calibration.npy
• calibration_metadata.npy
• field_calibration.json
• field_dimensions.npy
• calibrated_corners.jpg

You can now run analysis with field calibration enabled!"""
            
            messagebox.showinfo("Success", msg)
            self.update_status("Calibration saved successfully!")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save calibration: {str(e)}")
    
    def toggle_adjustment_mode(self):
        """Toggle manual point adjustment mode"""
        self.adjustment_mode = not self.adjustment_mode
        if self.adjustment_mode:
            self.update_status("Adjustment mode: Click and drag points to adjust")
        else:
            self.update_status("Normal mode: Click to add points")
        self.update_canvas()
    
    def add_reference_measurement(self, meas_type):
        """Add a reference measurement (goal box, penalty area, etc.)"""
        self._adding_measurement = True
        self._current_measurement_type = meas_type
        self._current_measurement_points = []
        
        # Get required points and dimensions based on type
        if meas_type == "goal_box":
            required_points = 4
            default_dims = {"length": 5.0, "width": 2.0}  # Standard goal box: 5m x 2m
            label = "Goal Box"
        elif meas_type == "penalty_area":
            required_points = 4
            default_dims = {"length": 16.5, "width": 40.0}  # Standard penalty area
            label = "Penalty Area"
        elif meas_type == "center_circle":
            required_points = 3  # Center point + 2 points on circle
            default_dims = {"radius": 9.15}  # Standard center circle radius
            label = "Center Circle"
        else:  # custom
            required_points = 2  # Two points for distance measurement
            default_dims = {"distance": 10.0}
            label = "Custom Distance"
        
        # Ask for dimensions
        dims = {}
        if meas_type == "center_circle":
            radius = simpledialog.askfloat("Center Circle Radius", 
                                           f"Enter radius in meters (default: {default_dims['radius']}m):",
                                           initialvalue=default_dims['radius'], minvalue=1.0, maxvalue=50.0)
            if radius is None:
                self._adding_measurement = False
                return
            dims = {"radius": radius}
        elif meas_type == "custom":
            distance = simpledialog.askfloat("Distance", 
                                            f"Enter distance in meters (default: {default_dims['distance']}m):",
                                            initialvalue=default_dims['distance'], minvalue=0.1, maxvalue=200.0)
            if distance is None:
                self._adding_measurement = False
                return
            dims = {"distance": distance}
        else:
            length = simpledialog.askfloat(f"{label} Length", 
                                          f"Enter length in meters (default: {default_dims['length']}m):",
                                          initialvalue=default_dims['length'], minvalue=0.1, maxvalue=200.0)
            if length is None:
                self._adding_measurement = False
                return
            width = simpledialog.askfloat(f"{label} Width", 
                                         f"Enter width in meters (default: {default_dims['width']}m):",
                                         initialvalue=default_dims['width'], minvalue=0.1, maxvalue=200.0)
            if width is None:
                self._adding_measurement = False
                return
            dims = {"length": length, "width": width}
        
        self._current_measurement_dims = dims
        self._current_measurement_label = label
        self._current_measurement_required = required_points
        
        self.update_status(f"Click {required_points} point(s) for {label} measurement")
    
    def handle_measurement_click(self, x, y):
        """Handle clicks when adding reference measurement"""
        self._current_measurement_points.append([x, y])
        
        if len(self._current_measurement_points) >= self._current_measurement_required:
            # Measurement complete
            measurement = {
                "type": self._current_measurement_type,
                "points": self._current_measurement_points.copy(),
                "dimensions": self._current_measurement_dims.copy(),
                "label": self._current_measurement_label
            }
            self.reference_measurements.append(measurement)
            self.update_measurements_list()
            self._adding_measurement = False
            self._current_measurement_points = []
            self.update_status(f"{self._current_measurement_label} measurement added")
            self.update_canvas()
        else:
            remaining = self._current_measurement_required - len(self._current_measurement_points)
            self.update_status(f"Click {remaining} more point(s) for {self._current_measurement_label}")
    
    def draw_measurement(self, img, measurement):
        """Draw a reference measurement on the image"""
        meas_type = measurement["type"]
        points = measurement["points"]
        dims = measurement["dimensions"]
        color = (255, 165, 0)  # Orange for measurements
        
        if meas_type == "goal_box" or meas_type == "penalty_area":
            # Draw rectangle
            if len(points) >= 4:
                pts = np.array([tuple(map(int, p)) for p in points], dtype=np.int32)
                cv2.polylines(img, [pts], True, color, 2)
                # Draw label
                center_x = int(sum(p[0] for p in points) / len(points))
                center_y = int(sum(p[1] for p in points) / len(points))
                label = f"{measurement['label']}: {dims.get('length', 0):.1f}m x {dims.get('width', 0):.1f}m"
                cv2.putText(img, label, (center_x - 50, center_y), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        elif meas_type == "center_circle":
            # Draw circle
            if len(points) >= 3:
                center = tuple(map(int, points[0]))
                # Calculate radius from center to first point on circle
                radius = int(np.sqrt((points[1][0] - points[0][0])**2 + (points[1][1] - points[0][1])**2))
                cv2.circle(img, center, radius, color, 2)
                label = f"{measurement['label']}: r={dims.get('radius', 0):.1f}m"
                cv2.putText(img, label, (center[0] - 30, center[1] - radius - 10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        elif meas_type == "custom":
            # Draw line with distance label
            if len(points) >= 2:
                pt1 = tuple(map(int, points[0]))
                pt2 = tuple(map(int, points[1]))
                cv2.line(img, pt1, pt2, color, 2)
                cv2.circle(img, pt1, 5, color, -1)
                cv2.circle(img, pt2, 5, color, -1)
                mid_x = int((pt1[0] + pt2[0]) / 2)
                mid_y = int((pt1[1] + pt2[1]) / 2)
                label = f"{dims.get('distance', 0):.1f}m"
                cv2.putText(img, label, (mid_x, mid_y), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    def update_measurements_list(self):
        """Update the measurements listbox"""
        self.measurements_listbox.delete(0, tk.END)
        for meas in self.reference_measurements:
            label = f"{meas['label']}: {meas.get('dimensions', {})}"
            self.measurements_listbox.insert(tk.END, label)
    
    def edit_measurement(self, event):
        """Edit selected measurement"""
        selection = self.measurements_listbox.curselection()
        if selection:
            idx = selection[0]
            meas = self.reference_measurements[idx]
            # For now, just show info - could add edit dialog
            messagebox.showinfo("Measurement Info", 
                              f"Type: {meas['label']}\n"
                              f"Dimensions: {meas['dimensions']}\n"
                              f"Points: {len(meas['points'])}")
    
    def remove_measurement(self):
        """Remove selected measurement"""
        selection = self.measurements_listbox.curselection()
        if selection:
            idx = selection[0]
            self.reference_measurements.pop(idx)
            self.update_measurements_list()
            self.update_canvas()
    
    def auto_load_calibration(self):
        """Auto-load existing calibration silently on startup"""
        if os.path.exists("field_calibration.json"):
            try:
                with open("field_calibration.json", 'r') as f:
                    data = json.load(f)
                    if "mode" in data:
                        self.calibration_mode = data["mode"]
                        self.mode_var.set(data["mode"])
                        self.on_mode_change()
                    if "points" in data and len(data["points"]) > 0:
                        points_list = data["points"]
                        if isinstance(points_list, list) and len(points_list) > 0:
                            # Convert points to list format (not numpy arrays) for consistency
                            self.click_points = [list(p) for p in points_list]
                    if "reference_measurements" in data:
                        self.reference_measurements = data["reference_measurements"]
                        self.update_measurements_list()
                    if "field_length" in data:
                        self.length_var.set(data["field_length"])
                    if "field_width" in data:
                        self.width_var.set(data["field_width"])
                    # Update field plot after auto-loading
                    self.update_field_plot()
            except Exception as e:
                print(f"Warning: Could not auto-load calibration: {e}")
    
    def load_existing_calibration(self):
        """Load existing calibration manually (with user prompts)"""
        # Ask user if they want to load from default location or browse
        if os.path.exists("field_calibration.json"):
            response = messagebox.askyesno(
                "Load Calibration",
                f"Found calibration file: field_calibration.json\n\n"
                f"Load this calibration?\n\n"
                f"(This will replace any current points)"
            )
            if not response:
                return
        
        # Try to load from default location first
        calibration_file = "field_calibration.json"
        if not os.path.exists(calibration_file):
            # Ask user to browse for calibration file
            calibration_file = filedialog.askopenfilename(
                title="Load Field Calibration",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir=os.getcwd()
            )
            if not calibration_file:
                return
        
        if os.path.exists(calibration_file):
            try:
                with open(calibration_file, 'r') as f:
                    data = json.load(f)
                    loaded_items = []
                    
                    if "mode" in data:
                        self.calibration_mode = data["mode"]
                        self.mode_var.set(data["mode"])
                        self.on_mode_change()  # Update UI
                        loaded_items.append(f"Mode: {self.calibration_mode}")
                    
                    if "points" in data and len(data["points"]) > 0:
                        # Convert points to numpy array format
                        points_list = data["points"]
                        if isinstance(points_list, list) and len(points_list) > 0:
                            # Convert points to list format (not numpy arrays) for consistency
                            self.click_points = [list(p) for p in points_list]
                            loaded_items.append(f"{len(self.click_points)} calibration points")
                            # Update canvas if image is loaded
                            if self.display_image is not None:
                                self.update_canvas()
                            self.update_field_plot()  # Update field plot when points are loaded
                    
                    if "reference_measurements" in data:
                        self.reference_measurements = data["reference_measurements"]
                        self.update_measurements_list()
                        if self.reference_measurements:
                            loaded_items.append(f"{len(self.reference_measurements)} reference measurements")
                    
                    if "field_length" in data:
                        self.length_var.set(data["field_length"])
                        loaded_items.append(f"Field length: {data['field_length']}m")
                    
                    if "field_width" in data:
                        self.width_var.set(data["field_width"])
                        loaded_items.append(f"Field width: {data['field_width']}m")
                    
                    if loaded_items:
                        messagebox.showinfo("Calibration Loaded", 
                            f"Successfully loaded calibration:\n\n" + "\n".join(loaded_items) + 
                            f"\n\nLoad a reference image to see the points on the field.")
                        self.update_field_plot()  # Update field plot when calibration is loaded
                    else:
                        messagebox.showwarning("No Data", "Calibration file exists but contains no data.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not load calibration: {e}")
        else:
            messagebox.showwarning("Not Found", "Calibration file not found.")
    
    def update_field_plot(self):
        """Update the field plot visualization showing current calibration"""
        if not hasattr(self, 'field_plot_canvas'):
            return
        
        # Clear canvas
        self.field_plot_canvas.delete("all")
        
        # Get canvas dimensions
        canvas_width = self.field_plot_canvas.winfo_width()
        canvas_height = self.field_plot_canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            # Canvas not yet rendered, schedule update
            self.root.after(100, self.update_field_plot)
            return
        
        # Get field dimensions
        length = float(self.length_var.get())
        width = float(self.width_var.get())
        
        if length <= 0 or width <= 0:
            # Draw placeholder
            self.field_plot_canvas.create_text(canvas_width // 2, canvas_height // 2,
                                             text="Set field dimensions to see plot",
                                             fill="gray", font=("Arial", 12))
            return
        
        # Calculate scale to fit field in canvas with padding
        padding = 20
        available_width = canvas_width - 2 * padding
        available_height = canvas_height - 2 * padding
        
        # Maintain aspect ratio - CRITICAL: Use both length AND width
        field_aspect = length / width if width > 0 else 1.0
        canvas_aspect = available_width / available_height if available_height > 0 else 1.0
        
        if field_aspect > canvas_aspect:
            # Field is wider (length > width) - fit to canvas width
            plot_width = available_width
            plot_height = available_width / field_aspect  # Height determined by width and aspect ratio
        else:
            # Field is taller (width > length) or square - fit to canvas height
            plot_height = available_height
            plot_width = available_height * field_aspect  # Width determined by height and aspect ratio
        
        # Center the plot
        offset_x = (canvas_width - plot_width) / 2
        offset_y = (canvas_height - plot_height) / 2
        
        # Draw field background (green)
        self.field_plot_canvas.create_rectangle(
            offset_x, offset_y,
            offset_x + plot_width, offset_y + plot_height,
            fill="#4CAF50", outline="#2E7D32", width=2
        )
        
        # Draw center line
        center_x = offset_x + plot_width / 2
        self.field_plot_canvas.create_line(
            center_x, offset_y,
            center_x, offset_y + plot_height,
            fill="white", width=2
        )
        
        # Draw center circle
        circle_radius = min(plot_width, plot_height) * 0.15
        self.field_plot_canvas.create_oval(
            center_x - circle_radius, offset_y + plot_height / 2 - circle_radius,
            center_x + circle_radius, offset_y + plot_height / 2 + circle_radius,
            outline="white", width=2
        )
        
        # Draw penalty areas (approximate)
        penalty_area_width = plot_width * 0.15
        penalty_area_height = plot_height * 0.25
        # Left penalty area
        self.field_plot_canvas.create_rectangle(
            offset_x, offset_y + plot_height / 2 - penalty_area_height / 2,
            offset_x + penalty_area_width, offset_y + plot_height / 2 + penalty_area_height / 2,
            outline="white", width=2
        )
        # Right penalty area
        self.field_plot_canvas.create_rectangle(
            offset_x + plot_width - penalty_area_width, offset_y + plot_height / 2 - penalty_area_height / 2,
            offset_x + plot_width, offset_y + plot_height / 2 + penalty_area_height / 2,
            outline="white", width=2
        )
        
        # Draw goal boxes (approximate)
        goal_box_width = plot_width * 0.05
        goal_box_height = plot_height * 0.15
        # Left goal box
        self.field_plot_canvas.create_rectangle(
            offset_x, offset_y + plot_height / 2 - goal_box_height / 2,
            offset_x + goal_box_width, offset_y + plot_height / 2 + goal_box_height / 2,
            outline="white", width=2
        )
        # Right goal box
        self.field_plot_canvas.create_rectangle(
            offset_x + plot_width - goal_box_width, offset_y + plot_height / 2 - goal_box_height / 2,
            offset_x + plot_width, offset_y + plot_height / 2 + goal_box_height / 2,
            outline="white", width=2
        )
        
        # Draw calibration points if available
        if len(self.click_points) >= 4:
            # Calculate homography to map points to field plot
            try:
                # Get first 4 points (corners)
                src_points = np.array(self.click_points[:4], dtype=np.float32)
                
                # Destination points in field plot coordinates
                dst_points = np.array([
                    [offset_x, offset_y],  # TL
                    [offset_x + plot_width, offset_y],  # TR
                    [offset_x + plot_width, offset_y + plot_height],  # BR
                    [offset_x, offset_y + plot_height]  # BL
                ], dtype=np.float32)
                
                # Calculate transformation
                H = cv2.getPerspectiveTransform(src_points, dst_points)
                
                # Transform all points
                for i, point in enumerate(self.click_points):
                    # Convert point to list if it's a numpy array
                    if isinstance(point, np.ndarray):
                        point = point.tolist()
                    pt = np.array([[point]], dtype=np.float32)
                    transformed = cv2.perspectiveTransform(pt, H)[0][0]
                    x = float(transformed[0])
                    y = float(transformed[1])
                    
                    # Draw point
                    color = "yellow" if i < 4 else "orange"
                    self.field_plot_canvas.create_oval(
                        x - 5, y - 5, x + 5, y + 5,
                        fill=color, outline="black", width=1
                    )
                    # Draw label
                    label = self.get_point_label(i)
                    self.field_plot_canvas.create_text(
                        x + 8, y - 8, text=label,
                        fill="black", font=("Arial", 8, "bold")
                    )
            except Exception as e:
                # If transformation fails, just show dimensions
                pass
        
        # Draw dimensions text
        dim_text = f"{length:.1f}m × {width:.1f}m"
        self.field_plot_canvas.create_text(
            canvas_width // 2, canvas_height - 10,
            text=dim_text, fill="black", font=("Arial", 10, "bold")
        )
        
        # Show point count if points exist
        if len(self.click_points) > 0:
            point_text = f"{len(self.click_points)} point(s) marked"
            self.field_plot_canvas.create_text(
                canvas_width // 2, 15,
                text=point_text, fill="black", font=("Arial", 9)
            )
    
    # Goal Area Designation Methods
    def on_goal_mode_change(self):
        """Handle change between calibration and goal designation mode"""
        self.goal_designation_mode = (self.goal_mode_var.get() == "goals")
        if self.goal_designation_mode:
            self.update_status("Goal Area Mode: Click to add points to current goal. Right-click to finish goal.")
        else:
            self.update_status("Calibration Mode: Click to add calibration points.")
        self.update_canvas()
        self.update_goals_list()
    
    def on_goal_type_change(self):
        """Handle change in goal designation type (rectangle/polygon)"""
        self.goal_designation_type = self.goal_type_var.get()
        if self.current_goal_name:
            # Reset current goal if type changes
            self.current_goal_points = []
            self.current_goal_name = None
            self.update_canvas()
    
    def start_new_goal(self):
        """Start defining a new goal area"""
        if self.display_image is None:
            messagebox.showwarning("Warning", "Please load an image or video first.")
            return
        
        self.current_goal_name = f"goal_{self.goal_counter}"
        self.current_goal_points = []
        self.update_status(f"Started new goal: {self.current_goal_name}. Click to add points.")
        self.update_canvas()
    
    def finish_current_goal(self):
        """Finish the current goal being defined"""
        if not self.current_goal_name or len(self.current_goal_points) < 2:
            messagebox.showwarning("Warning", "Need at least 2 points to define a goal area.")
            return
        
        # Save current goal
        self.goal_areas[self.current_goal_name] = {
            'type': self.goal_designation_type,
            'points': self.current_goal_points.copy()
        }
        
        self.goal_counter += 1
        self.current_goal_name = None
        self.current_goal_points = []
        
        self.update_status(f"Goal saved. Total goals: {len(self.goal_areas)}")
        self.update_canvas()
        self.update_goals_list()
    
    def handle_goal_click(self, x, y):
        """Handle click in goal designation mode"""
        if not self.current_goal_name:
            # Start new goal
            self.start_new_goal()
        
        # Add point to current goal
        self.current_goal_points.append([x, y])
        
        # Auto-finish rectangle goals after 2 points
        if self.goal_designation_type == 'rectangle' and len(self.current_goal_points) >= 2:
            self.finish_current_goal()
        else:
            self.update_canvas()
            self.update_status(f"Goal {self.current_goal_name}: {len(self.current_goal_points)} point(s). Right-click to finish.")
    
    def clear_all_goals(self):
        """Clear all goal areas"""
        if self.goal_areas:
            if messagebox.askyesno("Confirm", "Clear all goal areas?"):
                self.goal_areas = {}
                self.current_goal_name = None
                self.current_goal_points = []
                self.goal_counter = 1
                self.update_canvas()
                self.update_goals_list()
                self.update_status("All goals cleared.")
        else:
            self.update_status("No goals to clear.")
    
    def remove_last_goal(self):
        """Remove the last goal area"""
        if self.goal_areas:
            # Get the last goal (highest numbered)
            goal_names = sorted(self.goal_areas.keys())
            if goal_names:
                last_goal = goal_names[-1]
                del self.goal_areas[last_goal]
                self.update_canvas()
                self.update_goals_list()
                self.update_status(f"Removed goal: {last_goal}")
        else:
            self.update_status("No goals to remove.")
    
    def edit_goal(self, event):
        """Edit a selected goal (double-click)"""
        selection = self.goals_listbox.curselection()
        if selection:
            goal_name = self.goals_listbox.get(selection[0])
            # Extract goal name from listbox text (format: "goal_1 (rectangle, 2 pts)")
            goal_name = goal_name.split(' ')[0]
            if goal_name in self.goal_areas:
                # Load goal for editing
                goal_data = self.goal_areas[goal_name]
                self.current_goal_name = goal_name
                self.current_goal_points = goal_data['points'].copy()
                self.goal_designation_type = goal_data.get('type', 'rectangle')
                self.goal_type_var.set(self.goal_designation_type)
                
                # Remove from goals list (will be re-added when finished)
                del self.goal_areas[goal_name]
                
                self.update_canvas()
                self.update_goals_list()
                self.update_status(f"Editing goal: {goal_name}. Modify points and finish to save.")
    
    def update_goals_list(self):
        """Update the goals listbox"""
        self.goals_listbox.delete(0, tk.END)
        for goal_name in sorted(self.goal_areas.keys()):
            goal_data = self.goal_areas[goal_name]
            goal_type = goal_data.get('type', 'rectangle')
            num_points = len(goal_data.get('points', []))
            self.goals_listbox.insert(tk.END, f"{goal_name} ({goal_type}, {num_points} pts)")
    
    def save_goal_areas(self):
        """Save goal areas to JSON file"""
        if not self.goal_areas:
            messagebox.showwarning("Warning", "No goal areas to save.")
            return
        
        if self.original_frame_bgr is None:
            messagebox.showerror("Error", "No image or video frame loaded")
            return
        
        try:
            # Get output path
            if self.video_path:
                video_dir = os.path.dirname(self.video_path)
                video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
                default_filename = os.path.join(video_dir, f"goal_areas_{video_basename}.json")
            elif self.image_path:
                image_dir = os.path.dirname(self.image_path)
                image_basename = os.path.splitext(os.path.basename(self.image_path))[0]
                default_filename = os.path.join(image_dir, f"goal_areas_{image_basename}.json")
            else:
                default_filename = "goal_areas.json"
            
            filename = filedialog.asksaveasfilename(
                title="Save Goal Areas",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile=os.path.basename(default_filename),
                initialdir=os.path.dirname(default_filename) if os.path.dirname(default_filename) else "."
            )
            
            if not filename:
                return
            
            # Calculate scale factor to convert display coordinates to original image coordinates
            orig_height, orig_width = self.original_frame_bgr.shape[:2]
            display_height, display_width = self.display_image.shape[:2]
            scale_x = orig_width / display_width
            scale_y = orig_height / display_height
            
            # Convert goal areas to original coordinates and normalize
            normalized_areas = {}
            for goal_name, goal_data in self.goal_areas.items():
                points = goal_data['points']
                # Convert to original image coordinates
                orig_points = []
                for x, y in points:
                    orig_x = x * scale_x
                    orig_y = y * scale_y
                    orig_points.append([orig_x, orig_y])
                
                # Normalize to 0-1 range
                norm_points = []
                for x, y in orig_points:
                    norm_x = x / orig_width
                    norm_y = y / orig_height
                    norm_points.append([norm_x, norm_y])
                
                normalized_areas[goal_name] = {
                    'type': goal_data.get('type', 'rectangle'),
                    'points': norm_points
                }
            
            # Save to JSON
            json_data = {
                'video_path': self.video_path or self.image_path,
                'frame_num': 0,
                'goal_areas': normalized_areas
            }
            
            with open(filename, 'w') as f:
                json.dump(json_data, f, indent=4)
            
            messagebox.showinfo("Success", f"Goal areas saved to:\n{filename}\n\nTotal goals: {len(self.goal_areas)}")
            self.update_status(f"Goal areas saved: {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save goal areas: {str(e)}")
    
    def load_goal_areas(self):
        """Load goal areas from JSON file"""
        filename = filedialog.askopenfilename(
            title="Load Goal Areas",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not filename or not os.path.exists(filename):
            return
        
        try:
            with open(filename, 'r') as f:
                json_data = json.load(f)
            
            goal_areas_data = json_data.get('goal_areas', {})
            
            if not goal_areas_data:
                messagebox.showwarning("Warning", "No goal areas found in file.")
                return
            
            # Convert normalized coordinates back to display coordinates
            orig_height, orig_width = self.original_frame_bgr.shape[:2]
            display_height, display_width = self.display_image.shape[:2]
            scale_x = display_width / orig_width
            scale_y = display_height / orig_height
            
            self.goal_areas = {}
            for goal_name, goal_data in goal_areas_data.items():
                norm_points = goal_data.get('points', [])
                # Convert from normalized to display coordinates
                display_points = []
                for norm_x, norm_y in norm_points:
                    orig_x = norm_x * orig_width
                    orig_y = norm_y * orig_height
                    display_x = orig_x * scale_x
                    display_y = orig_y * scale_y
                    display_points.append([display_x, display_y])
                
                self.goal_areas[goal_name] = {
                    'type': goal_data.get('type', 'rectangle'),
                    'points': display_points
                }
            
            # Update goal counter
            if self.goal_areas:
                goal_numbers = [int(name.split('_')[1]) for name in self.goal_areas.keys() if '_' in name and name.split('_')[1].isdigit()]
                if goal_numbers:
                    self.goal_counter = max(goal_numbers) + 1
                else:
                    self.goal_counter = len(self.goal_areas) + 1
            
            self.update_canvas()
            self.update_goals_list()
            self.update_status(f"Loaded {len(self.goal_areas)} goal areas from: {os.path.basename(filename)}")
            messagebox.showinfo("Success", f"Loaded {len(self.goal_areas)} goal area(s) from:\n{filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load goal areas: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = FieldCalibrationGUI(root)
    root.mainloop()

