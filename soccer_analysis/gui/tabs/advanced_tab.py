"""
Advanced Tab Component
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


class AdvancedTab:
    """Advanced Settings Tab Component"""
    
    def __init__(self, parent_gui, parent_frame):
        """
        Initialize advanced tab
        
        Args:
            parent_gui: Reference to main GUI instance (for callbacks and variables)
            parent_frame: Parent frame to create tab in (should be scrollable canvas frame)
        """
        self.parent_gui = parent_gui
        self.parent_frame = parent_frame
        self.create_tab()
    
    def create_tab(self):
        """Create the Advanced tab content"""
        # Ensure parent_frame has column configuration
        self.parent_frame.columnconfigure(1, weight=1)
        
        advanced_row = 0
        
        # Watch-Only Mode
        watch_frame = ttk.LabelFrame(self.parent_frame, text="Watch-Only Mode", padding="10")
        watch_frame.grid(row=advanced_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        advanced_row += 1
        
        if hasattr(self.parent_gui, 'watch_only'):
            ttk.Checkbutton(watch_frame, text="Watch-Only Mode (learn from video, no output saved)",
                           variable=self.parent_gui.watch_only,
                           command=lambda: self._call_parent_method('_update_focus_players_ui')).grid(row=0, column=0, sticky=tk.W, pady=5)
            watch_help_label = ttk.Label(watch_frame, 
                                         text="Faster processing - learns player features & team colors, saves to player_gallery.json & team_color_config.json",
                                         foreground="dark gray", font=("Arial", 8), wraplength=500)
            watch_help_label.grid(row=1, column=0, sticky=tk.W, padx=(20, 0), pady=(0, 5))
            
            if hasattr(self.parent_gui, 'show_live_viewer'):
                ttk.Checkbutton(watch_frame, text="Show Live Viewer (watch learning in real-time)",
                               variable=self.parent_gui.show_live_viewer).grid(row=2, column=0, sticky=tk.W, padx=(20, 0), pady=5)
        
        # Focus Players (only shown if watch-only is enabled)
        if hasattr(self.parent_gui, 'focus_players_frame'):
            # This will be shown/hidden based on watch_only state
            pass
        
        # Overlay System
        overlay_frame = ttk.LabelFrame(self.parent_frame, text="Overlay System (Base Video + Overlays)", padding="10")
        overlay_frame.grid(row=advanced_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        advanced_row += 1
        
        # Base video option
        if hasattr(self.parent_gui, 'save_base_video'):
            base_video_frame = ttk.Frame(overlay_frame)
            base_video_frame.grid(row=0, column=0, sticky=tk.W, pady=5)
            ttk.Checkbutton(base_video_frame, text="Save Base Video (clean video without overlays)",
                           variable=self.parent_gui.save_base_video).pack(side=tk.LEFT)
            base_video_help = ttk.Label(base_video_frame, 
                                        text="(Usually not needed - you already have the original video)",
                                        font=("Arial", 8), foreground="gray")
            base_video_help.pack(side=tk.LEFT, padx=(10, 0))
        
        if hasattr(self.parent_gui, 'export_overlay_metadata'):
            ttk.Checkbutton(overlay_frame, text="Export Overlay Metadata (for separate rendering)",
                           variable=self.parent_gui.export_overlay_metadata).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        if hasattr(self.parent_gui, 'enable_video_encoding'):
            ttk.Checkbutton(overlay_frame, text="Enable Video Encoding (save analyzed video with overlays)",
                           variable=self.parent_gui.enable_video_encoding).grid(row=2, column=0, sticky=tk.W, pady=5)
        
        # Overlay quality and render scale
        if hasattr(self.parent_gui, 'overlay_quality'):
            overlay_quality_label = ttk.Label(overlay_frame, text="Overlay Quality & Render Settings:",
                                             font=("Arial", 9, "bold"))
            overlay_quality_label.grid(row=3, column=0, sticky=tk.W, pady=(10, 5))
            
            # Quality setting
            quality_frame = ttk.Frame(overlay_frame)
            quality_frame.grid(row=4, column=0, sticky=tk.W, pady=5, padx=(20, 0))
            ttk.Label(quality_frame, text="Quality:", width=12, anchor=tk.W).pack(side=tk.LEFT)
            quality_combo = ttk.Combobox(quality_frame, textvariable=self.parent_gui.overlay_quality,
                                        values=["sd", "hd", "4k"], width=8, state="readonly")
            quality_combo.pack(side=tk.LEFT, padx=(0, 15))
            
            # Render scale setting
            if hasattr(self.parent_gui, 'render_scale'):
                scale_frame = ttk.Frame(overlay_frame)
                scale_frame.grid(row=5, column=0, sticky=tk.W, pady=5, padx=(20, 0))
                ttk.Label(scale_frame, text="Render Scale:", width=12, anchor=tk.W).pack(side=tk.LEFT)
                render_scale_spin = ttk.Spinbox(scale_frame, from_=0.5, to=4.0, increment=0.1,
                                               textvariable=self.parent_gui.render_scale, width=8)
                render_scale_spin.pack(side=tk.LEFT, padx=(0, 8))
                scale_help = ttk.Label(scale_frame, 
                                      text="(1.0 = original, 2.0 = 2x resolution for HD)",
                                      font=("Arial", 8), foreground="gray")
                scale_help.pack(side=tk.LEFT)
        
        # Video Game Quality Graphics Settings
        if hasattr(self.parent_gui, 'enable_advanced_blending'):
            quality_graphics_label = ttk.Label(overlay_frame, text="Video Game Quality Graphics:",
                                              font=("Arial", 9, "bold"))
            quality_graphics_label.grid(row=6, column=0, sticky=tk.W, pady=(15, 5))
            
            # Advanced blending modes
            ttk.Checkbutton(overlay_frame, text="Enable Advanced Blending Modes (glow, screen, additive effects)",
                           variable=self.parent_gui.enable_advanced_blending, command=lambda: self._call_parent_method('update_preview')).grid(row=7, column=0, sticky=tk.W, pady=5, padx=(20, 0))
            blending_help = ttk.Label(overlay_frame,
                                     text="(additive glow, screen blending, overlay modes for professional effects)",
                                     font=("Arial", 8), foreground="gray")
            blending_help.grid(row=8, column=0, sticky=tk.W, padx=(40, 0), pady=(0, 5))
            
            # Professional text rendering
            if hasattr(self.parent_gui, 'use_professional_text'):
                ttk.Checkbutton(overlay_frame, text="Use Professional Text Rendering (PIL-based with outlines & shadows)",
                               variable=self.parent_gui.use_professional_text, command=lambda: self._call_parent_method('update_preview')).grid(row=9, column=0, sticky=tk.W, pady=5, padx=(20, 0))
                text_help = ttk.Label(overlay_frame,
                                     text="(high-quality fonts, smooth edges, drop shadows - requires Pillow)",
                                     font=("Arial", 8), foreground="gray")
                text_help.grid(row=10, column=0, sticky=tk.W, padx=(40, 0), pady=(0, 5))
            
            # Motion blur settings
            if hasattr(self.parent_gui, 'enable_motion_blur'):
                motion_blur_frame = ttk.Frame(overlay_frame)
                motion_blur_frame.grid(row=11, column=0, sticky=tk.W, pady=5, padx=(20, 0))
                ttk.Checkbutton(motion_blur_frame, text="Enable Motion Blur",
                               variable=self.parent_gui.enable_motion_blur, command=lambda: self._call_parent_method('update_preview')).pack(side=tk.LEFT)
                if hasattr(self.parent_gui, 'motion_blur_amount'):
                    ttk.Label(motion_blur_frame, text="Intensity:").pack(side=tk.LEFT, padx=(15, 5))
                    motion_blur_spin = ttk.Spinbox(motion_blur_frame, from_=0.0, to=2.0, increment=0.1,
                                                  textvariable=self.parent_gui.motion_blur_amount, width=6, format="%.1f", command=lambda: self._call_parent_method('update_preview'))
                    motion_blur_spin.pack(side=tk.LEFT)
                    motion_blur_spin.bind('<KeyRelease>', lambda e: self._call_parent_method('update_preview'))
                motion_blur_help = ttk.Label(overlay_frame,
                                            text="(blur trails for fast-moving objects based on velocity - adds ~10-20% overhead)",
                                            font=("Arial", 8), foreground="gray")
                motion_blur_help.grid(row=12, column=0, sticky=tk.W, padx=(40, 0), pady=(0, 5))
            
            # Enhanced graphics features
            if hasattr(self.parent_gui, 'graphics_quality_preset'):
                enhanced_label = ttk.Label(overlay_frame, text="Enhanced Graphics Features:",
                                         font=("Arial", 9, "bold"))
                enhanced_label.grid(row=13, column=0, sticky=tk.W, pady=(15, 5))
                
                # Quality preset
                quality_frame = ttk.Frame(overlay_frame)
                quality_frame.grid(row=14, column=0, sticky=tk.W, pady=5, padx=(20, 0))
                ttk.Label(quality_frame, text="Quality Preset:").pack(side=tk.LEFT, padx=(0, 5))
                quality_combo = ttk.Combobox(quality_frame, textvariable=self.parent_gui.graphics_quality_preset,
                                            values=("sd", "hd", "4k"), width=8, state="readonly")
                quality_combo.pack(side=tk.LEFT)
                quality_combo.bind('<<ComboboxSelected>>', lambda e: self._call_parent_method('update_preview'))
                
                # Text enhancements
                if hasattr(self.parent_gui, 'enable_text_gradient'):
                    ttk.Checkbutton(overlay_frame, text="Enable Text Gradient (color gradient in text)",
                                   variable=self.parent_gui.enable_text_gradient, command=lambda: self._call_parent_method('update_preview')).grid(row=15, column=0, sticky=tk.W, pady=5, padx=(20, 0))
                
                if hasattr(self.parent_gui, 'enable_text_glow'):
                    ttk.Checkbutton(overlay_frame, text="Enable Text Glow (glowing text effect)",
                                   variable=self.parent_gui.enable_text_glow, command=lambda: self._call_parent_method('update_preview')).grid(row=16, column=0, sticky=tk.W, pady=5, padx=(20, 0))
                
                if hasattr(self.parent_gui, 'enable_text_pulse'):
                    ttk.Checkbutton(overlay_frame, text="Enable Text Pulse (pulsing text animation)",
                                   variable=self.parent_gui.enable_text_pulse, command=lambda: self._call_parent_method('update_preview')).grid(row=17, column=0, sticky=tk.W, pady=5, padx=(20, 0))
                
                # Glow enhancements
                if hasattr(self.parent_gui, 'enable_glow_pulse'):
                    ttk.Checkbutton(overlay_frame, text="Enable Pulsing Glow (animated glow effects)",
                                   variable=self.parent_gui.enable_glow_pulse, command=lambda: self._call_parent_method('update_preview')).grid(row=18, column=0, sticky=tk.W, pady=5, padx=(20, 0))
                
                if hasattr(self.parent_gui, 'enable_color_shift'):
                    ttk.Checkbutton(overlay_frame, text="Enable Color-Shifting Glow (rainbow glow effects)",
                                   variable=self.parent_gui.enable_color_shift, command=lambda: self._call_parent_method('update_preview')).grid(row=19, column=0, sticky=tk.W, pady=5, padx=(20, 0))
                
                # Box/ellipse enhancements
                if hasattr(self.parent_gui, 'enable_gradient_boxes'):
                    ttk.Checkbutton(overlay_frame, text="Enable Gradient Boxes (gradient-filled bounding boxes)",
                                   variable=self.parent_gui.enable_gradient_boxes, command=lambda: self._call_parent_method('update_preview')).grid(row=20, column=0, sticky=tk.W, pady=5, padx=(20, 0))
                
                if hasattr(self.parent_gui, 'enable_particle_trails'):
                    ttk.Checkbutton(overlay_frame, text="Enable Particle Trails (motion trail particles)",
                                   variable=self.parent_gui.enable_particle_trails, command=lambda: self._call_parent_method('update_preview')).grid(row=21, column=0, sticky=tk.W, pady=5, padx=(20, 0))
                
                enhanced_help = ttk.Label(overlay_frame,
                                         text="(Advanced visual effects for professional broadcast-quality graphics)",
                                         font=("Arial", 8), foreground="gray")
                enhanced_help.grid(row=22, column=0, sticky=tk.W, padx=(40, 0), pady=(0, 5))
    
    def _call_parent_method(self, method_name, *args, **kwargs):
        """Call a method on the parent GUI instance"""
        if hasattr(self.parent_gui, method_name):
            method = getattr(self.parent_gui, method_name)
            return method(*args, **kwargs)
        else:
            # Silently fail for optional methods
            pass

