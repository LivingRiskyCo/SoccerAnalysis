"""
Visualization Tab Component
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

# Import tooltip system
try:
    from SoccerID.utils.tooltip import create_tooltip, TOOLTIP_DATABASE
except ImportError:
    try:
        from utils.tooltip import create_tooltip, TOOLTIP_DATABASE
    except ImportError:
        # Fallback: create dummy function
        def create_tooltip(widget, text, detailed_text=None):
            pass
        TOOLTIP_DATABASE = {}


class VisualizationTab:
    """Visualization Settings Tab Component"""
    
    def __init__(self, parent_gui, parent_frame):
        """
        Initialize visualization tab
        
        Args:
            parent_gui: Reference to main GUI instance (for callbacks and variables)
            parent_frame: Parent frame to create tab in (should be scrollable canvas frame)
        """
        self.parent_gui = parent_gui
        self.parent_frame = parent_frame
        self.create_tab()
    
    def create_tab(self):
        """Create the Visualization tab content"""
        # Ensure parent_frame has column configuration
        self.parent_frame.columnconfigure(1, weight=1)
        
        viz_row = 0
        
        # Visualization Style
        style_frame = ttk.LabelFrame(self.parent_frame, text="Visualization Style", padding="10")
        style_frame.grid(row=viz_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        style_frame.columnconfigure(0, weight=0, minsize=180)
        style_frame.columnconfigure(1, weight=0, minsize=100)
        style_frame.columnconfigure(2, weight=1, minsize=300)
        viz_row += 1
        
        ttk.Label(style_frame, text="Style:", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        style_combo = ttk.Combobox(style_frame, textvariable=self.parent_gui.viz_style,
                                   values=["box", "ellipse", "circle", "minimal"], width=15, state="readonly")
        style_combo.grid(row=0, column=1, padx=5, pady=5)
        style_combo.bind('<<ComboboxSelected>>', lambda e: self._call_parent_method('update_preview'))
        ttk.Label(style_frame, text="(box: rectangles, ellipse: ovals, circle: circles, minimal: dots)", wraplength=280).grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Color Mode
        ttk.Label(style_frame, text="Color Mode:", font=("Arial", 9)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        color_mode_combo = ttk.Combobox(style_frame, textvariable=self.parent_gui.viz_color_mode,
                                       values=["team", "player", "track"], width=15, state="readonly")
        color_mode_combo.grid(row=1, column=1, padx=5, pady=5)
        color_mode_combo.bind('<<ComboboxSelected>>', lambda e: self._call_parent_method('update_preview'))
        ttk.Label(style_frame, text="(team: by team colors, player: by player, track: by track ID)", wraplength=280).grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # Ellipse/Circle Settings
        if hasattr(self.parent_gui, 'ellipse_width'):
            ellipse_frame = ttk.LabelFrame(self.parent_frame, text="Ellipse/Circle Settings", padding="10")
            ellipse_frame.grid(row=viz_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
            ellipse_frame.columnconfigure(0, weight=0, minsize=180)
            ellipse_frame.columnconfigure(1, weight=0, minsize=100)
            ellipse_frame.columnconfigure(2, weight=1, minsize=300)
            viz_row += 1
            
            ttk.Label(ellipse_frame, text="Width:", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            width_spinbox = ttk.Spinbox(ellipse_frame, from_=10, to=200, increment=5,
                                        textvariable=self.parent_gui.ellipse_width, width=8, command=lambda: self._call_parent_method('update_preview'))
            width_spinbox.grid(row=0, column=1, padx=5, pady=5)
            width_spinbox.bind('<KeyRelease>', lambda e: self._call_parent_method('update_preview'))
            ttk.Label(ellipse_frame, text="(ellipse/circle width in pixels)", wraplength=280).grid(row=0, column=2, sticky=tk.W, padx=5)
            
            ttk.Label(ellipse_frame, text="Height:", font=("Arial", 9)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
            height_spinbox = ttk.Spinbox(ellipse_frame, from_=10, to=200, increment=5,
                                         textvariable=self.parent_gui.ellipse_height, width=8, command=lambda: self._call_parent_method('update_preview'))
            height_spinbox.grid(row=1, column=1, padx=5, pady=5)
            height_spinbox.bind('<KeyRelease>', lambda e: self._call_parent_method('update_preview'))
            ttk.Label(ellipse_frame, text="(ellipse/circle height in pixels)", wraplength=280).grid(row=1, column=2, sticky=tk.W, padx=5)
            
            ttk.Label(ellipse_frame, text="Outline Thickness:", font=("Arial", 9)).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
            thickness_spinbox = ttk.Spinbox(ellipse_frame, from_=1, to=10, increment=1,
                                           textvariable=self.parent_gui.ellipse_outline_thickness, width=8, command=lambda: self._call_parent_method('update_preview'))
            thickness_spinbox.grid(row=2, column=1, padx=5, pady=5)
            thickness_spinbox.bind('<KeyRelease>', lambda e: self._call_parent_method('update_preview'))
            ttk.Label(ellipse_frame, text="(outline thickness, 1=thin, 3=normal, 5=thick)", wraplength=280).grid(row=2, column=2, sticky=tk.W, padx=5)
        
        # Box Settings
        if hasattr(self.parent_gui, 'box_thickness'):
            box_frame = ttk.LabelFrame(self.parent_frame, text="Box Settings", padding="10")
            box_frame.grid(row=viz_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
            box_frame.columnconfigure(0, weight=0, minsize=180)
            box_frame.columnconfigure(1, weight=0, minsize=100)
            box_frame.columnconfigure(2, weight=1, minsize=300)
            viz_row += 1
            
            ttk.Label(box_frame, text="Box Thickness:", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            box_thick_spinbox = ttk.Spinbox(box_frame, from_=1, to=10, increment=1,
                                           textvariable=self.parent_gui.box_thickness, width=8, command=lambda: self._call_parent_method('update_preview'))
            box_thick_spinbox.grid(row=0, column=1, padx=5, pady=5)
            box_thick_spinbox.bind('<KeyRelease>', lambda e: self._call_parent_method('update_preview'))
            ttk.Label(box_frame, text="(border thickness for boxes)", wraplength=280).grid(row=0, column=2, sticky=tk.W, padx=5)
            
            if hasattr(self.parent_gui, 'box_shrink_factor'):
                ttk.Label(box_frame, text="Shrink Factor:", font=("Arial", 9)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
                shrink_spinbox = ttk.Spinbox(box_frame, from_=0.5, to=1.0, increment=0.05,
                                            textvariable=self.parent_gui.box_shrink_factor, width=8, format="%.2f", command=lambda: self._call_parent_method('update_preview'))
                shrink_spinbox.grid(row=1, column=1, padx=5, pady=5)
                shrink_spinbox.bind('<KeyRelease>', lambda e: self._call_parent_method('update_preview'))
                ttk.Label(box_frame, text="(shrink boxes to fit better, 1.0=full size)", wraplength=280).grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # Analytics Settings
        if hasattr(self.parent_gui, 'analytics_font_scale'):
            analytics_frame = ttk.LabelFrame(self.parent_frame, text="Analytics Display Settings", padding="10")
            analytics_frame.grid(row=viz_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
            analytics_frame.columnconfigure(0, weight=0, minsize=180)
            analytics_frame.columnconfigure(1, weight=0, minsize=100)
            analytics_frame.columnconfigure(2, weight=1, minsize=300)
            viz_row += 1
            
            ttk.Label(analytics_frame, text="Font Scale:", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            font_scale_spinbox = ttk.Spinbox(analytics_frame, from_=0.3, to=2.0, increment=0.1,
                                            textvariable=self.parent_gui.analytics_font_scale, width=8, format="%.1f", command=lambda: self._call_parent_method('update_preview'))
            font_scale_spinbox.grid(row=0, column=1, padx=5, pady=5)
            font_scale_spinbox.bind('<KeyRelease>', lambda e: self._call_parent_method('update_preview'))
            ttk.Label(analytics_frame, text="(font size for analytics text)", wraplength=280).grid(row=0, column=2, sticky=tk.W, padx=5)
            
            if hasattr(self.parent_gui, 'analytics_font_thickness'):
                ttk.Label(analytics_frame, text="Font Thickness:", font=("Arial", 9)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
                thickness_spinbox = ttk.Spinbox(analytics_frame, from_=1, to=5, increment=1,
                                                textvariable=self.parent_gui.analytics_font_thickness, width=8, command=lambda: self._call_parent_method('update_preview'))
                thickness_spinbox.grid(row=1, column=1, padx=5, pady=5)
                thickness_spinbox.bind('<KeyRelease>', lambda e: self._call_parent_method('update_preview'))
                ttk.Label(analytics_frame, text="(1=thin, 3=normal, 5=very thick)", wraplength=280).grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # Custom Colors
        if hasattr(self.parent_gui, 'use_custom_box_color'):
            color_frame = ttk.LabelFrame(self.parent_frame, text="Custom Colors", padding="10")
            color_frame.grid(row=viz_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
            viz_row += 1
            
            ttk.Checkbutton(color_frame, text="Use Custom Box Color",
                           variable=self.parent_gui.use_custom_box_color, command=lambda: self._call_parent_method('update_preview')).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            
            if hasattr(self.parent_gui, 'box_color_rgb'):
                try:
                    from color_picker_utils import create_color_picker_widget
                    color_picker_frame, _ = create_color_picker_widget(
                        color_frame,
                        self.parent_gui.box_color_rgb,
                        label_text="Box Color:",
                        initial_color=(0, 255, 0),
                        on_change_callback=lambda rgb: self._call_parent_method('update_preview')
                    )
                    color_picker_frame.grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)
                except ImportError:
                    ttk.Label(color_frame, text="(Color picker not available)", foreground="gray").grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # Player Labels
        if hasattr(self.parent_gui, 'show_player_labels'):
            label_frame = ttk.LabelFrame(self.parent_frame, text="Player Labels", padding="10")
            label_frame.grid(row=viz_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
            label_frame.columnconfigure(0, weight=0, minsize=180)
            label_frame.columnconfigure(1, weight=0, minsize=100)
            label_frame.columnconfigure(2, weight=1, minsize=300)
            viz_row += 1
            
            ttk.Checkbutton(label_frame, text="Show Player Labels",
                           variable=self.parent_gui.show_player_labels, command=lambda: self._call_parent_method('update_preview')).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            ttk.Label(label_frame, text="(uncheck to hide all player name/ID labels)", wraplength=280).grid(row=0, column=2, sticky=tk.W, padx=5)
            
            if hasattr(self.parent_gui, 'label_type'):
                ttk.Label(label_frame, text="Label Type:", font=("Arial", 9)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
                label_type_frame = ttk.Frame(label_frame)
                label_type_frame.grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)
                
                ttk.Radiobutton(label_type_frame, text="Full Name", variable=self.parent_gui.label_type, value="full_name",
                               command=lambda: self._call_parent_method('update_preview')).pack(side=tk.LEFT, padx=5)
                ttk.Radiobutton(label_type_frame, text="Jersey #", variable=self.parent_gui.label_type, value="jersey",
                               command=lambda: self._call_parent_method('update_preview')).pack(side=tk.LEFT, padx=5)
                ttk.Radiobutton(label_type_frame, text="Custom", variable=self.parent_gui.label_type, value="custom",
                               command=lambda: self._call_parent_method('update_preview')).pack(side=tk.LEFT, padx=5)
        
        # Motion Visualization
        if hasattr(self.parent_gui, 'show_player_trail'):
            motion_frame = ttk.LabelFrame(self.parent_frame, text="Motion Visualization", padding="10")
            motion_frame.grid(row=viz_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
            viz_row += 1
            
            ttk.Checkbutton(motion_frame, text="Show Player Trail",
                           variable=self.parent_gui.show_player_trail, command=lambda: self._call_parent_method('update_preview')).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            ttk.Label(motion_frame, text="(trail behind player showing movement path)", wraplength=280).grid(row=0, column=2, sticky=tk.W, padx=5)
            
            if hasattr(self.parent_gui, 'show_direction_arrow'):
                ttk.Checkbutton(motion_frame, text="Show Direction Arrow",
                               variable=self.parent_gui.show_direction_arrow, command=lambda: self._call_parent_method('update_preview')).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
                ttk.Label(motion_frame, text="(arrow pointing in direction of travel)", wraplength=280).grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # Track ID Decay Visualization
        if hasattr(self.parent_gui, 'show_predicted_boxes'):
            decay_frame = ttk.LabelFrame(self.parent_frame, text="Track ID Decay Visualization", padding="10")
            decay_frame.grid(row=viz_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
            decay_frame.columnconfigure(0, weight=0, minsize=180)
            decay_frame.columnconfigure(1, weight=0, minsize=100)
            decay_frame.columnconfigure(2, weight=1, minsize=300)
            viz_row += 1
            
            ttk.Checkbutton(decay_frame, text="Show Predicted Boxes",
                           variable=self.parent_gui.show_predicted_boxes, command=lambda: self._call_parent_method('update_preview')).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            ttk.Label(decay_frame, text="(show predicted boxes when track is lost)", wraplength=280).grid(row=0, column=2, sticky=tk.W, padx=5)
            
            if hasattr(self.parent_gui, 'prediction_duration'):
                ttk.Label(decay_frame, text="Prediction Duration (s):", font=("Arial", 9)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
                pred_dur_spinbox = ttk.Spinbox(decay_frame, from_=0.0, to=2.0, increment=0.1,
                                              textvariable=self.parent_gui.prediction_duration, width=8, format="%.1f", command=lambda: self._call_parent_method('update_preview'))
                pred_dur_spinbox.grid(row=1, column=1, padx=5, pady=5)
                pred_dur_spinbox.bind('<KeyRelease>', lambda e: self._call_parent_method('update_preview'))
                ttk.Label(decay_frame, text="(how long to show predicted boxes)", wraplength=280).grid(row=1, column=2, sticky=tk.W, padx=5)
    
    def _call_parent_method(self, method_name, *args, **kwargs):
        """Call a method on the parent GUI instance"""
        if hasattr(self.parent_gui, method_name):
            method = getattr(self.parent_gui, method_name)
            return method(*args, **kwargs)
        else:
            # Silently fail for optional methods
            pass

