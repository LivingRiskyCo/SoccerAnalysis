"""
Event Detection Tab Component
Extracted from soccer_analysis_gui.py for better organization
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


class EventDetectionTab:
    """Event Detection Tab Component"""
    
    def __init__(self, parent_gui, parent_frame):
        """
        Initialize event detection tab
        
        Args:
            parent_gui: Reference to main GUI instance (for callbacks)
            parent_frame: Parent frame to create tab in
        """
        self.parent_gui = parent_gui
        self.parent_frame = parent_frame
        
        # Initialize event detection variables (will be set on parent_gui)
        if not hasattr(parent_gui, 'event_csv_file'):
            parent_gui.event_csv_file = tk.StringVar()
            parent_gui.event_min_confidence = tk.DoubleVar(value=0.5)
            parent_gui.event_min_ball_speed = tk.DoubleVar(value=3.0)
            parent_gui.event_min_pass_distance = tk.DoubleVar(value=5.0)
            parent_gui.event_possession_threshold = tk.DoubleVar(value=1.5)
            parent_gui.event_detect_passes = tk.BooleanVar(value=True)
            parent_gui.event_detect_shots = tk.BooleanVar(value=True)
            parent_gui.event_detect_goals = tk.BooleanVar(value=False)
            parent_gui.event_detect_zones = tk.BooleanVar(value=True)
            parent_gui.event_export_csv = tk.BooleanVar(value=True)
            parent_gui.event_goal_areas_file = tk.StringVar()
            parent_gui.event_use_manual_markers = tk.BooleanVar(value=True)
            parent_gui.event_manual_markers_file = tk.StringVar()
        
        self.create_tab()
    
    def create_tab(self):
        """Create the Event Detection tab UI"""
        row = 0
        
        # Title
        title_label = ttk.Label(self.parent_frame, text="Automated Event Detection", 
                               font=("Arial", 14, "bold"))
        title_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        row += 1
        
        desc_label = ttk.Label(self.parent_frame, 
                               text="Detect passes, shots, and analyze zone occupancy from existing CSV tracking data.\n"
                                    "No need to re-process videos - works with your existing analysis results.",
                               font=("Arial", 9), foreground="gray", justify=tk.LEFT)
        desc_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 15))
        row += 1
        
        # CSV File Selection
        csv_frame = ttk.LabelFrame(self.parent_frame, text="CSV Tracking Data", padding="10")
        csv_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        csv_frame.columnconfigure(1, weight=1)
        row += 1
        
        ttk.Label(csv_frame, text="Tracking CSV File:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(csv_frame, textvariable=self.parent_gui.event_csv_file, width=50).grid(
            row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(csv_frame, text="Browse", 
                  command=lambda: self._call_parent_method('_browse_event_csv_file')).grid(row=0, column=2, padx=5, pady=5)
        
        # Auto-detect CSV from output file
        ttk.Button(csv_frame, text="Auto-detect from Output", 
                  command=lambda: self._call_parent_method('_auto_detect_event_csv')).grid(row=1, column=0, columnspan=3, pady=5)
        
        # Detection Parameters
        params_frame = ttk.LabelFrame(self.parent_frame, text="Detection Parameters", padding="10")
        params_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        params_frame.columnconfigure(1, weight=1)
        row += 1
        
        # Confidence threshold
        ttk.Label(params_frame, text="Min Confidence:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        conf_spinbox = ttk.Spinbox(params_frame, from_=0.1, to=1.0, increment=0.05,
                                  textvariable=self.parent_gui.event_min_confidence, width=10, format="%.2f")
        conf_spinbox.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(params_frame, text="(0.1 = more detections, 1.0 = only very confident)", 
                 font=("Arial", 8), foreground="gray").grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Min ball speed
        ttk.Label(params_frame, text="Min Ball Speed (m/s):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        speed_spinbox = ttk.Spinbox(params_frame, from_=1.0, to=15.0, increment=0.5,
                                    textvariable=self.parent_gui.event_min_ball_speed, width=10, format="%.1f")
        speed_spinbox.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(params_frame, text="(Minimum ball speed during pass)", 
                 font=("Arial", 8), foreground="gray").grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # Min pass distance
        ttk.Label(params_frame, text="Min Pass Distance (m):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        dist_spinbox = ttk.Spinbox(params_frame, from_=2.0, to=30.0, increment=1.0,
                                   textvariable=self.parent_gui.event_min_pass_distance, width=10, format="%.1f")
        dist_spinbox.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(params_frame, text="(Minimum pass length in meters)", 
                 font=("Arial", 8), foreground="gray").grid(row=2, column=2, sticky=tk.W, padx=5)
        
        # Possession threshold
        ttk.Label(params_frame, text="Possession Threshold (m):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        poss_spinbox = ttk.Spinbox(params_frame, from_=0.5, to=5.0, increment=0.5,
                                   textvariable=self.parent_gui.event_possession_threshold, width=10, format="%.1f")
        poss_spinbox.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(params_frame, text="(Ball within this distance = possession)", 
                 font=("Arial", 8), foreground="gray").grid(row=3, column=2, sticky=tk.W, padx=5)
        
        # Event Types
        types_frame = ttk.LabelFrame(self.parent_frame, text="Event Types", padding="10")
        types_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        row += 1
        
        ttk.Checkbutton(types_frame, text="Detect Passes", 
                       variable=self.parent_gui.event_detect_passes).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(types_frame, text="Detect Shots", 
                       variable=self.parent_gui.event_detect_shots).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(types_frame, text="Detect Goals", 
                       variable=self.parent_gui.event_detect_goals).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(types_frame, text="Analyze Zone Occupancy", 
                       variable=self.parent_gui.event_detect_zones).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Goal Area Designation
        goal_area_frame = ttk.LabelFrame(self.parent_frame, text="Goal Area Designation", padding="10")
        goal_area_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        goal_area_frame.columnconfigure(1, weight=1)
        row += 1
        
        ttk.Label(goal_area_frame, text="Goal Areas JSON:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(goal_area_frame, textvariable=self.parent_gui.event_goal_areas_file, width=50).grid(
            row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(goal_area_frame, text="Browse", 
                  command=lambda: self._call_parent_method('_browse_goal_areas_file')).grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Button(goal_area_frame, text="🎯 Designate Goal Areas", 
                  command=lambda: self._call_parent_method('_designate_goal_areas'), width=25).grid(row=1, column=0, columnspan=3, pady=5)
        
        ttk.Button(goal_area_frame, text="Auto-detect from Video", 
                  command=lambda: self._call_parent_method('_auto_detect_goal_areas'), width=25).grid(row=2, column=0, columnspan=3, pady=5)
        
        ttk.Label(goal_area_frame, 
                 text="Designate goal areas on the field to enable accurate shot and goal detection.\n"
                      "Click 'Designate Goal Areas' to mark goal boundaries on a video frame.\n"
                      "Or use 'Auto-detect' to find existing goal area files.",
                 font=("Arial", 8), foreground="gray", justify=tk.LEFT).grid(row=3, column=0, columnspan=3, pady=5)
        
        # Manual Event Markers
        markers_frame = ttk.LabelFrame(self.parent_frame, text="Manual Event Markers", padding="10")
        markers_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        markers_frame.columnconfigure(1, weight=1)
        row += 1
        
        ttk.Checkbutton(markers_frame, text="Use Manual Event Markers", 
                       variable=self.parent_gui.event_use_manual_markers).grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(markers_frame, text="Markers JSON:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(markers_frame, textvariable=self.parent_gui.event_manual_markers_file, width=50).grid(
            row=1, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(markers_frame, text="Browse", 
                  command=lambda: self._browse_manual_markers_file()).grid(row=1, column=2, padx=5, pady=5)
        
        ttk.Label(markers_frame, 
                 text="Load manual event markers created in playback viewer or setup wizard.\n"
                      "Manual markers take priority over auto-detected events.",
                 font=("Arial", 8), foreground="gray", justify=tk.LEFT).grid(row=2, column=0, columnspan=3, pady=5)
        
        # Export Options
        export_frame = ttk.LabelFrame(self.parent_frame, text="Export Options", padding="10")
        export_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        row += 1
        
        ttk.Checkbutton(export_frame, text="Export Events to CSV", 
                       variable=self.parent_gui.event_export_csv).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Run Detection Button
        action_frame = ttk.Frame(self.parent_frame)
        action_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=20)
        row += 1
        
        run_button = ttk.Button(action_frame, text="🚀 Run Event Detection", 
                               command=lambda: self._call_parent_method('_run_event_detection'),
                               width=30)
        run_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(action_frame, 
                 text="This will analyze the CSV file and detect events based on the parameters above.",
                 font=("Arial", 9), foreground="gray").pack(side=tk.LEFT, padx=10)
    
    def _browse_manual_markers_file(self):
        """Browse for manual event markers JSON file"""
        from tkinter import filedialog
        filename = filedialog.askopenfilename(
            title="Select Manual Event Markers JSON File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.parent_gui.event_manual_markers_file.set(filename)
    
    def _call_parent_method(self, method_name, *args, **kwargs):
        """Call a method on the parent GUI instance"""
        if hasattr(self.parent_gui, method_name):
            method = getattr(self.parent_gui, method_name)
            return method(*args, **kwargs)
        else:
            messagebox.showwarning("Method Not Found", 
                                 f"Method '{method_name}' not found in parent GUI.\n"
                                 "This is a migration issue - please report it.")

