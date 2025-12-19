"""
Machine Learning & Validation Tab Component
Settings for ML enhancements and validation
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


class MLTab:
    """Machine Learning & Validation Tab Component"""
    
    def __init__(self, parent_gui, parent_frame):
        """
        Initialize ML tab
        
        Args:
            parent_gui: Reference to main GUI instance
            parent_frame: Parent frame to create tab in
        """
        self.parent_gui = parent_gui
        self.parent_frame = parent_frame
        
        # Initialize ML variables
        if not hasattr(parent_gui, 'use_face_recognition'):
            parent_gui.use_face_recognition = tk.BooleanVar(value=True)
            parent_gui.use_feedback_learning = tk.BooleanVar(value=True)
            parent_gui.use_adaptive_tracking = tk.BooleanVar(value=True)
            parent_gui.use_predictive_analytics = tk.BooleanVar(value=True)
            parent_gui.run_validation = tk.BooleanVar(value=True)
            parent_gui.face_backend = tk.StringVar(value="auto")
            parent_gui.face_consensus_frames = tk.IntVar(value=5)
        
        self.create_tab()
    
    def create_tab(self):
        """Create the ML tab content"""
        row = 0
        
        # Title
        title_label = ttk.Label(self.parent_frame, text="Machine Learning & Validation", 
                               font=("Arial", 14, "bold"))
        title_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        row += 1
        
        desc_label = ttk.Label(self.parent_frame, 
                               text="Enable ML enhancements and automatic validation to improve tracking accuracy over time.",
                               font=("Arial", 9), foreground="gray", justify=tk.LEFT)
        desc_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 15))
        row += 1
        
        # Face Recognition Section
        face_frame = ttk.LabelFrame(self.parent_frame, text="Face Recognition", padding="10")
        face_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        face_frame.columnconfigure(1, weight=1)
        row += 1
        
        ttk.Checkbutton(face_frame, text="Enable Face Recognition", 
                       variable=self.parent_gui.use_face_recognition).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Label(face_frame, text="Backend:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        backend_combo = ttk.Combobox(face_frame, textvariable=self.parent_gui.face_backend,
                                     values=["auto", "face_recognition", "deepface", "dlib"],
                                     state="readonly", width=15)
        backend_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(face_frame, text="Consensus Frames:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        consensus_spinbox = ttk.Spinbox(face_frame, from_=1, to=20, increment=1,
                                        textvariable=self.parent_gui.face_consensus_frames, width=10)
        consensus_spinbox.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # ML Enhancements Section
        ml_frame = ttk.LabelFrame(self.parent_frame, text="Machine Learning Enhancements", padding="10")
        ml_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        ml_frame.columnconfigure(1, weight=1)
        row += 1
        
        ttk.Checkbutton(ml_frame, text="Learn from User Corrections", 
                       variable=self.parent_gui.use_feedback_learning).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Label(ml_frame, text="(Improves matching based on your corrections)", 
                 font=("Arial", 8), foreground="gray").grid(row=0, column=2, sticky=tk.W, padx=5)
        
        ttk.Checkbutton(ml_frame, text="Adaptive Tracking", 
                       variable=self.parent_gui.use_adaptive_tracking).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Label(ml_frame, text="(Automatically adjusts thresholds based on performance)", 
                 font=("Arial", 8), foreground="gray").grid(row=1, column=2, sticky=tk.W, padx=5)
        
        ttk.Checkbutton(ml_frame, text="Predictive Analytics", 
                       variable=self.parent_gui.use_predictive_analytics).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Label(ml_frame, text="(Predicts positions, movements, and events)", 
                 font=("Arial", 8), foreground="gray").grid(row=2, column=2, sticky=tk.W, padx=5)
        
        # Validation Section
        validation_frame = ttk.LabelFrame(self.parent_frame, text="Data Validation", padding="10")
        validation_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        validation_frame.columnconfigure(1, weight=1)
        row += 1
        
        ttk.Checkbutton(validation_frame, text="Run Validation After Analysis", 
                       variable=self.parent_gui.run_validation).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Label(validation_frame, text="(Generates quality reports and detects anomalies)", 
                 font=("Arial", 8), foreground="gray").grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Validation Actions
        action_frame = ttk.Frame(validation_frame)
        action_frame.grid(row=1, column=0, columnspan=3, pady=10)
        
        ttk.Button(action_frame, text="Generate Quality Report", 
                  command=self._generate_quality_report, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Validate Tracks", 
                  command=self._validate_tracks, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Detect Anomalies", 
                  command=self._detect_anomalies, width=20).pack(side=tk.LEFT, padx=5)
        
        # Feedback Learning Section
        feedback_frame = ttk.LabelFrame(self.parent_frame, text="Feedback Learning", padding="10")
        feedback_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        row += 1
        
        ttk.Button(feedback_frame, text="View Feedback Statistics", 
                  command=self._view_feedback_stats, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(feedback_frame, text="Clear Feedback Data", 
                  command=self._clear_feedback, width=20).pack(side=tk.LEFT, padx=5)
        
        # Adaptive Tracking Section
        adaptive_frame = ttk.LabelFrame(self.parent_frame, text="Adaptive Tracking", padding="10")
        adaptive_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        row += 1
        
        ttk.Button(adaptive_frame, text="View Current Thresholds", 
                  command=self._view_thresholds, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(adaptive_frame, text="View Performance Stats", 
                  command=self._view_performance_stats, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(adaptive_frame, text="Reset to Defaults", 
                  command=self._reset_adaptive, width=20).pack(side=tk.LEFT, padx=5)
    
    def _generate_quality_report(self):
        """Generate quality report for selected CSV"""
        csv_path = filedialog.askopenfilename(
            title="Select Tracking CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not csv_path:
            return
        
        try:
            from soccer_analysis.validation.quality_reporter import QualityReporter
            reporter = QualityReporter()
            
            output_path = csv_path.replace('.csv', '_quality_report.json')
            report = reporter.generate_report(csv_path, output_path)
            
            quality_score = report.get('metrics', {}).get('quality_score', 0)
            messagebox.showinfo("Quality Report Generated", 
                              f"Quality Report saved to:\n{output_path}\n\n"
                              f"Quality Score: {quality_score:.1f}/100\n"
                              f"Issues: {len(report.get('issues', []))}\n"
                              f"Warnings: {len(report.get('warnings', []))}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate quality report: {e}")
    
    def _validate_tracks(self):
        """Validate tracks in selected CSV"""
        csv_path = filedialog.askopenfilename(
            title="Select Tracking CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not csv_path:
            return
        
        try:
            from soccer_analysis.validation.track_validator import TrackValidator
            validator = TrackValidator()
            results = validator.validate_tracks(csv_path)
            
            messagebox.showinfo("Track Validation", 
                              f"Validation Results:\n\n"
                              f"Total Tracks: {results.get('total_tracks', 0)}\n"
                              f"Valid Tracks: {results.get('valid_tracks', 0)}\n"
                              f"Broken Tracks: {results.get('broken_tracks', 0)}\n"
                              f"Short Tracks: {results.get('short_tracks', 0)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to validate tracks: {e}")
    
    def _detect_anomalies(self):
        """Detect anomalies in selected CSV"""
        csv_path = filedialog.askopenfilename(
            title="Select Tracking CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not csv_path:
            return
        
        try:
            from soccer_analysis.validation.anomaly_detector import AnomalyDetector
            detector = AnomalyDetector()
            anomalies = detector.detect_anomalies(csv_path)
            
            summary = anomalies.get('summary', {})
            messagebox.showinfo("Anomaly Detection", 
                              f"Anomaly Detection Results:\n\n"
                              f"Impossible Movements: {summary.get('total_impossible_movements', 0)}\n"
                              f"Unrealistic Speeds: {summary.get('total_unrealistic_speeds', 0)}\n"
                              f"Unrealistic Accelerations: {summary.get('total_unrealistic_accelerations', 0)}\n"
                              f"Position Jumps: {summary.get('total_position_jumps', 0)}\n"
                              f"Statistical Anomalies: {summary.get('total_statistical_anomalies', 0)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to detect anomalies: {e}")
    
    def _view_feedback_stats(self):
        """View feedback learning statistics"""
        try:
            from soccer_analysis.ml.feedback_learner import FeedbackLearner
            learner = FeedbackLearner()
            stats = learner.get_statistics()
            
            messagebox.showinfo("Feedback Learning Statistics", 
                              f"Total Corrections: {stats.get('total_corrections', 0)}\n"
                              f"Players with Corrections: {stats.get('players_with_corrections', 0)}\n"
                              f"Learned Patterns: {stats.get('learned_patterns', 0)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get feedback stats: {e}")
    
    def _clear_feedback(self):
        """Clear feedback learning data"""
        if messagebox.askyesno("Confirm", "Clear all feedback learning data?"):
            try:
                from soccer_analysis.ml.feedback_learner import FeedbackLearner
                learner = FeedbackLearner()
                learner.clear_database()
                learner.save_feedback()
                messagebox.showinfo("Success", "Feedback data cleared")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear feedback: {e}")
    
    def _view_thresholds(self):
        """View current adaptive thresholds"""
        try:
            from soccer_analysis.ml.adaptive_tracker import AdaptiveTracker
            tracker = AdaptiveTracker()
            thresholds = tracker.get_current_thresholds()
            
            messagebox.showinfo("Current Thresholds", 
                              f"Similarity Threshold: {thresholds.get('similarity_threshold', 0):.3f}\n"
                              f"Re-ID Threshold: {thresholds.get('reid_threshold', 0):.3f}\n"
                              f"Feature Weights:\n"
                              f"  Body: {thresholds.get('feature_weights', {}).get('body', 0):.1%}\n"
                              f"  Jersey: {thresholds.get('feature_weights', {}).get('jersey', 0):.1%}\n"
                              f"  Foot: {thresholds.get('feature_weights', {}).get('foot', 0):.1%}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get thresholds: {e}")
    
    def _view_performance_stats(self):
        """View performance statistics"""
        try:
            from soccer_analysis.ml.adaptive_tracker import AdaptiveTracker
            tracker = AdaptiveTracker()
            stats = tracker.get_performance_stats()
            
            if stats:
                messagebox.showinfo("Performance Statistics", 
                                  f"Avg Track Quality: {stats.get('avg_track_quality', 0):.3f}\n"
                                  f"Avg Match Accuracy: {stats.get('avg_match_accuracy', 0):.3f}\n"
                                  f"Avg False Positives: {stats.get('avg_false_positives', 0):.2f}\n"
                                  f"Avg False Negatives: {stats.get('avg_false_negatives', 0):.2f}")
            else:
                messagebox.showinfo("Performance Statistics", "No performance data available yet")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get performance stats: {e}")
    
    def _reset_adaptive(self):
        """Reset adaptive tracking to defaults"""
        if messagebox.askyesno("Confirm", "Reset adaptive tracking to default thresholds?"):
            try:
                from soccer_analysis.ml.adaptive_tracker import AdaptiveTracker
                # Reinitialize with defaults
                tracker = AdaptiveTracker()
                messagebox.showinfo("Success", "Adaptive tracking reset to defaults")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reset: {e}")

