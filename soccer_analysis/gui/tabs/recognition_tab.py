"""
Player Recognition Tab Component
AI-powered player recognition settings and controls
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


class RecognitionTab:
    """Player Recognition Tab Component"""
    
    def __init__(self, parent_gui, parent_frame):
        """
        Initialize recognition tab
        
        Args:
            parent_gui: Reference to main GUI instance
            parent_frame: Parent frame to create tab in
        """
        self.parent_gui = parent_gui
        self.parent_frame = parent_frame
        
        # Initialize recognition variables
        if not hasattr(parent_gui, 'use_jersey_ocr'):
            parent_gui.use_jersey_ocr = tk.BooleanVar(value=True)
            parent_gui.ocr_backend = tk.StringVar(value="auto")
            parent_gui.ocr_confidence_threshold = tk.DoubleVar(value=0.5)
            parent_gui.ocr_consensus_frames = tk.IntVar(value=5)
            parent_gui.ocr_consensus_threshold = tk.DoubleVar(value=0.6)
            parent_gui.ocr_preprocess = tk.BooleanVar(value=True)
        
        self.create_tab()
    
    def create_tab(self):
        """Create the recognition tab content"""
        row = 0
        
        # Title
        title_label = ttk.Label(self.parent_frame, text="AI-Powered Player Recognition", 
                               font=("Arial", 14, "bold"))
        title_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        row += 1
        
        desc_label = ttk.Label(self.parent_frame, 
                               text="Automatically recognize players using jersey numbers, faces, and other features.\n"
                                    "Reduces manual tagging effort and improves cross-video player matching.",
                               font=("Arial", 9), foreground="gray", justify=tk.LEFT)
        desc_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 15))
        row += 1
        
        # Jersey Number OCR Section
        ocr_frame = ttk.LabelFrame(self.parent_frame, text="Jersey Number OCR", padding="10")
        ocr_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        ocr_frame.columnconfigure(1, weight=1)
        row += 1
        
        # Enable OCR
        ttk.Checkbutton(ocr_frame, text="Enable Jersey Number OCR", 
                       variable=self.parent_gui.use_jersey_ocr).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # OCR Backend
        ttk.Label(ocr_frame, text="OCR Backend:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        backend_combo = ttk.Combobox(ocr_frame, textvariable=self.parent_gui.ocr_backend,
                                     values=["auto", "easyocr", "paddleocr", "tesseract"],
                                     state="readonly", width=15)
        backend_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(ocr_frame, text="(auto = best available)", 
                 font=("Arial", 8), foreground="gray").grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # Confidence Threshold
        ttk.Label(ocr_frame, text="Confidence Threshold:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        conf_spinbox = ttk.Spinbox(ocr_frame, from_=0.1, to=1.0, increment=0.05,
                                  textvariable=self.parent_gui.ocr_confidence_threshold, width=10, format="%.2f")
        conf_spinbox.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(ocr_frame, text="(minimum confidence per frame)", 
                 font=("Arial", 8), foreground="gray").grid(row=2, column=2, sticky=tk.W, padx=5)
        
        # Consensus Frames
        ttk.Label(ocr_frame, text="Consensus Frames:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        consensus_spinbox = ttk.Spinbox(ocr_frame, from_=1, to=20, increment=1,
                                        textvariable=self.parent_gui.ocr_consensus_frames, width=10)
        consensus_spinbox.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(ocr_frame, text="(number of frames to consider for consensus)", 
                 font=("Arial", 8), foreground="gray").grid(row=3, column=2, sticky=tk.W, padx=5)
        
        # Consensus Threshold
        ttk.Label(ocr_frame, text="Consensus Threshold:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        consensus_thresh_spinbox = ttk.Spinbox(ocr_frame, from_=0.3, to=1.0, increment=0.05,
                                              textvariable=self.parent_gui.ocr_consensus_threshold, width=10, format="%.2f")
        consensus_thresh_spinbox.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(ocr_frame, text="(minimum fraction of frames that must agree)", 
                 font=("Arial", 8), foreground="gray").grid(row=4, column=2, sticky=tk.W, padx=5)
        
        # Preprocess
        ttk.Checkbutton(ocr_frame, text="Preprocess Images", 
                       variable=self.parent_gui.ocr_preprocess).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Label(ocr_frame, text="(enhance contrast, thresholding for better OCR)", 
                 font=("Arial", 8), foreground="gray").grid(row=5, column=2, sticky=tk.W, padx=5)
        
        # Performance Section
        perf_frame = ttk.LabelFrame(self.parent_frame, text="Performance Settings", padding="10")
        perf_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        perf_frame.columnconfigure(1, weight=1)
        row += 1
        
        # Auto-detect hardware button
        ttk.Button(perf_frame, text="Auto-Detect Hardware", 
                  command=self._detect_hardware).grid(row=0, column=0, columnspan=3, pady=5)
        
        # Hardware info display
        self.hardware_label = ttk.Label(perf_frame, text="Click 'Auto-Detect Hardware' to see system capabilities", 
                                        font=("Arial", 9), foreground="gray")
        self.hardware_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Performance mode buttons
        mode_frame = ttk.Frame(perf_frame)
        mode_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        ttk.Button(mode_frame, text="Performance Mode", 
                  command=self._apply_performance_mode, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(mode_frame, text="Quality Mode", 
                  command=self._apply_quality_mode, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(mode_frame, text="Balanced Mode", 
                  command=self._apply_balanced_mode, width=20).pack(side=tk.LEFT, padx=5)
    
    def _detect_hardware(self):
        """Detect and display hardware capabilities"""
        try:
            from soccer_analysis.utils.performance import PerformanceOptimizer
            hardware = PerformanceOptimizer.detect_hardware()
            
            info_text = f"GPU: {hardware.get('gpu_name', 'Not Available')} "
            info_text += f"({hardware.get('gpu_memory_gb', 0):.1f} GB) | "
            info_text += f"CPU: {hardware.get('cpu_count', 1)} cores | "
            info_text += f"RAM: {hardware.get('ram_gb', 0):.1f} GB"
            
            self.hardware_label.config(text=info_text, foreground="black")
            
            messagebox.showinfo("Hardware Detection", 
                              f"GPU: {hardware.get('gpu_name', 'Not Available')}\n"
                              f"GPU Memory: {hardware.get('gpu_memory_gb', 0):.1f} GB\n"
                              f"CPU Cores: {hardware.get('cpu_count', 1)}\n"
                              f"RAM: {hardware.get('ram_gb', 0):.1f} GB\n\n"
                              f"Optimal settings have been applied.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not detect hardware: {e}")
    
    def _apply_performance_mode(self):
        """Apply performance mode settings"""
        try:
            from soccer_analysis.utils.performance import PerformanceOptimizer
            settings = PerformanceOptimizer.apply_performance_mode()
            self._apply_settings(settings)
            messagebox.showinfo("Performance Mode", 
                              "Performance mode applied!\n\n"
                              "Settings optimized for speed:\n"
                              f"• Process every {settings.get('process_every_nth', 2)} frame\n"
                              f"• YOLO resolution: {settings.get('yolo_resolution', '720p')}\n"
                              f"• Batch size: {settings.get('batch_size', 8)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not apply performance mode: {e}")
    
    def _apply_quality_mode(self):
        """Apply quality mode settings"""
        try:
            from soccer_analysis.utils.performance import PerformanceOptimizer
            settings = PerformanceOptimizer.apply_quality_mode()
            self._apply_settings(settings)
            messagebox.showinfo("Quality Mode", 
                              "Quality mode applied!\n\n"
                              "Settings optimized for accuracy:\n"
                              f"• Process all frames\n"
                              f"• YOLO resolution: {settings.get('yolo_resolution', 'full')}\n"
                              f"• Batch size: {settings.get('batch_size', 4)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not apply quality mode: {e}")
    
    def _apply_balanced_mode(self):
        """Apply balanced mode settings"""
        try:
            from soccer_analysis.utils.performance import PerformanceOptimizer
            settings = PerformanceOptimizer.get_optimal_settings()
            self._apply_settings(settings)
            messagebox.showinfo("Balanced Mode", 
                              "Balanced mode applied!\n\n"
                              "Settings optimized for your hardware:\n"
                              f"• YOLO resolution: {settings.get('yolo_resolution', 'full')}\n"
                              f"• Batch size: {settings.get('batch_size', 8)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not apply balanced mode: {e}")
    
    def _apply_settings(self, settings: dict):
        """Apply settings to GUI variables"""
        if hasattr(self.parent_gui, 'process_every_nth'):
            self.parent_gui.process_every_nth.set(settings.get('process_every_nth', 1))
        if hasattr(self.parent_gui, 'yolo_resolution'):
            self.parent_gui.yolo_resolution.set(settings.get('yolo_resolution', 'full'))
        if hasattr(self.parent_gui, 'batch_size'):
            self.parent_gui.batch_size.set(settings.get('batch_size', 8))

