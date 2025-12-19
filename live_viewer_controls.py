"""
Live Viewer Control Window
GUI for controlling pause/resume, dynamic settings, and presets during watch-only mode
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
from collections import deque
from datetime import datetime


class LiveViewerControls:
    def __init__(self, parent, dynamic_settings, on_settings_update=None):
        """
        Initialize live viewer control window
        
        Args:
            parent: Parent window (can be None for standalone)
            dynamic_settings: DynamicSettings object from analysis (shared state)
            on_settings_update: Callback function when settings are updated
        """
        self.dynamic_settings = dynamic_settings
        self.on_settings_update = on_settings_update
        self.settings_history = deque(maxlen=20)  # Undo/redo history
        self.current_history_index = -1
        
        # Error tracking
        self.error_log = []  # List of error dicts: {frame, type, message, fixable, fixed}
        self.max_error_log = 100  # Keep last 100 errors
        
        # Player correction tracking
        self.player_corrections = {}  # {track_id: {'correct_player': name, 'frame': frame_num, 'applied': bool}}
        self.current_track_assignments = {}  # {track_id: player_name} - current assignments
        
        # Gallery seeder window reference
        self._gallery_seeder_window = None
        self._gallery_seeder_app = None
        
        # Create window
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("Live Viewer Controls")
        self.window.geometry("600x800")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Playback Controls
        playback_frame = ttk.Frame(notebook, padding="10")
        notebook.add(playback_frame, text="Playback")
        self.create_playback_tab(playback_frame)
        
        # Tab 2: Ball Tracking
        ball_frame = ttk.Frame(notebook, padding="10")
        notebook.add(ball_frame, text="Ball Tracking")
        self.create_ball_tracking_tab(ball_frame)
        
        # Tab 3: Visualization
        viz_frame = ttk.Frame(notebook, padding="10")
        notebook.add(viz_frame, text="Visualization")
        self.create_visualization_tab(viz_frame)
        
        # Tab 4: Presets
        preset_frame = ttk.Frame(notebook, padding="10")
        notebook.add(preset_frame, text="Presets")
        self.create_presets_tab(preset_frame)
        
        # Tab 5: Player Corrections
        correction_frame = ttk.Frame(notebook, padding="10")
        notebook.add(correction_frame, text="👤 Player Corrections")
        self.create_player_correction_tab(correction_frame)
        
        # Tab 6: Error Handling & Corrections
        error_frame = ttk.Frame(notebook, padding="10")
        notebook.add(error_frame, text="⚠ Errors & Fixes")
        self.create_error_tab(error_frame)
        
        # Status bar
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN)
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Update status periodically
        self.update_status()
    
    def create_playback_tab(self, parent):
        """Create playback control tab"""
        # Show message if analysis not running
        if self.dynamic_settings is None or not hasattr(self.dynamic_settings, 'paused'):
            info_label = ttk.Label(parent, text="⚠ Analysis not running - Playback controls require active analysis", 
                                  foreground="orange", font=("Arial", 9))
            info_label.pack(pady=10)
            return
        
        # Pause/Resume buttons
        control_frame = ttk.LabelFrame(parent, text="Playback Controls", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X)
        
        self.pause_button = ttk.Button(button_frame, text="⏸ Pause", command=self.toggle_pause)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        self.resume_button = ttk.Button(button_frame, text="▶ Resume", command=self.resume)
        self.resume_button.pack(side=tk.LEFT, padx=5)
        
        self.resume_button.config(state=tk.DISABLED)
        
        # Frame stepping (when paused)
        step_frame = ttk.LabelFrame(parent, text="Frame Stepping (when paused)", padding="10")
        step_frame.pack(fill=tk.X, pady=5)
        
        step_button_frame = ttk.Frame(step_frame)
        step_button_frame.pack(fill=tk.X)
        
        ttk.Button(step_button_frame, text="⏮ Previous Frame", command=self.step_backward).pack(side=tk.LEFT, padx=5)
        ttk.Button(step_button_frame, text="⏭ Next Frame", command=self.step_forward).pack(side=tk.LEFT, padx=5)
        
        # Screenshot
        screenshot_frame = ttk.LabelFrame(parent, text="Screenshot", padding="10")
        screenshot_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(screenshot_frame, text="📷 Capture Screenshot", command=self.capture_screenshot).pack(pady=5)
        
        # Settings History
        history_frame = ttk.LabelFrame(parent, text="Settings History", padding="10")
        history_frame.pack(fill=tk.X, pady=5)
        
        history_button_frame = ttk.Frame(history_frame)
        history_button_frame.pack(fill=tk.X)
        
        self.undo_button = ttk.Button(history_button_frame, text="↶ Undo", command=self.undo_settings)
        self.undo_button.pack(side=tk.LEFT, padx=5)
        
        self.redo_button = ttk.Button(history_button_frame, text="↷ Redo", command=self.redo_settings)
        self.redo_button.pack(side=tk.LEFT, padx=5)
        
        self.undo_button.config(state=tk.DISABLED)
        self.redo_button.config(state=tk.DISABLED)
    
    def create_ball_tracking_tab(self, parent):
        """Create ball tracking settings tab"""
        # Show message if analysis not running
        if self.dynamic_settings is None or not hasattr(self.dynamic_settings, 'track_ball_flag'):
            info_label = ttk.Label(parent, text="⚠ Analysis not running - Ball tracking controls require active analysis", 
                                  foreground="orange", font=("Arial", 9))
            info_label.pack(pady=10)
            return
        
        # Ball tracking toggle
        toggle_frame = ttk.LabelFrame(parent, text="Ball Tracking", padding="10")
        toggle_frame.pack(fill=tk.X, pady=5)
        
        self.ball_tracking_var = tk.BooleanVar(value=self.dynamic_settings.track_ball_flag)
        ttk.Checkbutton(toggle_frame, text="Enable Ball Tracking", 
                       variable=self.ball_tracking_var,
                       command=lambda: self.update_setting('track_ball_flag', self.ball_tracking_var.get())).pack(anchor=tk.W)
        
        # Ball trail
        trail_frame = ttk.LabelFrame(parent, text="Ball Trail", padding="10")
        trail_frame.pack(fill=tk.X, pady=5)
        
        self.show_trail_var = tk.BooleanVar(value=self.dynamic_settings.show_ball_trail)
        ttk.Checkbutton(trail_frame, text="Show Ball Trail", 
                       variable=self.show_trail_var,
                       command=lambda: self.update_setting('show_ball_trail', self.show_trail_var.get())).pack(anchor=tk.W)
        
        # Trail length
        ttk.Label(trail_frame, text="Trail Length:").pack(anchor=tk.W, pady=2)
        self.trail_length_var = tk.IntVar(value=self.dynamic_settings.trail_length)
        trail_length_scale = ttk.Scale(trail_frame, from_=5, to=100, 
                                      variable=self.trail_length_var,
                                      orient=tk.HORIZONTAL,
                                      command=lambda v: self.update_setting('trail_length', int(float(v))))
        trail_length_scale.pack(fill=tk.X, pady=2)
        self.trail_length_label = ttk.Label(trail_frame, text=f"Value: {self.trail_length_var.get()}")
        self.trail_length_label.pack(anchor=tk.W)
        trail_length_scale.configure(command=lambda v: self.update_trail_length_label(int(float(v))))
        
        # Ball size detection
        size_frame = ttk.LabelFrame(parent, text="Ball Size Detection", padding="10")
        size_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(size_frame, text="Min Radius:").pack(anchor=tk.W, pady=2)
        self.ball_min_var = tk.IntVar(value=self.dynamic_settings.ball_min_radius)
        ball_min_scale = ttk.Scale(size_frame, from_=3, to=20, 
                                  variable=self.ball_min_var,
                                  orient=tk.HORIZONTAL,
                                  command=lambda v: self.update_setting('ball_min_radius', int(float(v))))
        ball_min_scale.pack(fill=tk.X, pady=2)
        
        ttk.Label(size_frame, text="Max Radius:").pack(anchor=tk.W, pady=2)
        self.ball_max_var = tk.IntVar(value=self.dynamic_settings.ball_max_radius)
        ball_max_scale = ttk.Scale(size_frame, from_=20, to=100, 
                                  variable=self.ball_max_var,
                                  orient=tk.HORIZONTAL,
                                  command=lambda v: self.update_setting('ball_max_radius', int(float(v))))
        ball_max_scale.pack(fill=tk.X, pady=2)
    
    def create_visualization_tab(self, parent):
        """Create visualization settings tab"""
        # Show message if analysis not running
        if self.dynamic_settings is None or not hasattr(self.dynamic_settings, 'viz_style'):
            info_label = ttk.Label(parent, text="⚠ Analysis not running - Visualization controls require active analysis", 
                                  foreground="orange", font=("Arial", 9))
            info_label.pack(pady=10)
            return
        
        # Visualization style
        style_frame = ttk.LabelFrame(parent, text="Visualization Style", padding="10")
        style_frame.pack(fill=tk.X, pady=5)
        
        self.viz_style_var = tk.StringVar(value=self.dynamic_settings.viz_style)
        ttk.Radiobutton(style_frame, text="Boxes", variable=self.viz_style_var, 
                       value="box", command=lambda: self.update_setting('viz_style', 'box')).pack(anchor=tk.W)
        ttk.Radiobutton(style_frame, text="Circles", variable=self.viz_style_var, 
                       value="circle", command=lambda: self.update_setting('viz_style', 'circle')).pack(anchor=tk.W)
        ttk.Radiobutton(style_frame, text="Both", variable=self.viz_style_var, 
                       value="both", command=lambda: self.update_setting('viz_style', 'both')).pack(anchor=tk.W)
        
        # Color mode
        color_frame = ttk.LabelFrame(parent, text="Color Mode", padding="10")
        color_frame.pack(fill=tk.X, pady=5)
        
        self.viz_color_var = tk.StringVar(value=self.dynamic_settings.viz_color_mode)
        ttk.Radiobutton(color_frame, text="Team Colors", variable=self.viz_color_var, 
                       value="team", command=lambda: self.update_setting('viz_color_mode', 'team')).pack(anchor=tk.W)
        ttk.Radiobutton(color_frame, text="Track ID", variable=self.viz_color_var, 
                       value="track_id", command=lambda: self.update_setting('viz_color_mode', 'track_id')).pack(anchor=tk.W)
        ttk.Radiobutton(color_frame, text="Gradient", variable=self.viz_color_var, 
                       value="gradient", command=lambda: self.update_setting('viz_color_mode', 'gradient')).pack(anchor=tk.W)
        
        # Box settings
        box_frame = ttk.LabelFrame(parent, text="Box Settings", padding="10")
        box_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(box_frame, text="Box Thickness:").pack(anchor=tk.W, pady=2)
        self.box_thickness_var = tk.IntVar(value=self.dynamic_settings.box_thickness)
        box_thickness_scale = ttk.Scale(box_frame, from_=1, to=10, 
                                       variable=self.box_thickness_var,
                                       orient=tk.HORIZONTAL,
                                       command=lambda v: self.update_setting('box_thickness', int(float(v))))
        box_thickness_scale.pack(fill=tk.X, pady=2)
        
        # Ellipse settings
        ellipse_frame = ttk.LabelFrame(parent, text="Ellipse Settings", padding="10")
        ellipse_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(ellipse_frame, text="Ellipse Width:").pack(anchor=tk.W, pady=2)
        self.ellipse_width_var = tk.IntVar(value=self.dynamic_settings.ellipse_width)
        ellipse_width_scale = ttk.Scale(ellipse_frame, from_=10, to=50, 
                                       variable=self.ellipse_width_var,
                                       orient=tk.HORIZONTAL,
                                       command=lambda v: self.update_setting('ellipse_width', int(float(v))))
        ellipse_width_scale.pack(fill=tk.X, pady=2)
        
        ttk.Label(ellipse_frame, text="Ellipse Height:").pack(anchor=tk.W, pady=2)
        self.ellipse_height_var = tk.IntVar(value=self.dynamic_settings.ellipse_height)
        ellipse_height_scale = ttk.Scale(ellipse_frame, from_=5, to=30, 
                                        variable=self.ellipse_height_var,
                                        orient=tk.HORIZONTAL,
                                        command=lambda v: self.update_setting('ellipse_height', int(float(v))))
        ellipse_height_scale.pack(fill=tk.X, pady=2)
        
        # Label settings
        label_frame = ttk.LabelFrame(parent, text="Label Settings", padding="10")
        label_frame.pack(fill=tk.X, pady=5)
        
        self.show_labels_var = tk.BooleanVar(value=self.dynamic_settings.show_player_labels)
        ttk.Checkbutton(label_frame, text="Show Player Labels", 
                       variable=self.show_labels_var,
                       command=lambda: self.update_setting('show_player_labels', self.show_labels_var.get())).pack(anchor=tk.W)
        
        ttk.Label(label_frame, text="Label Font Scale:").pack(anchor=tk.W, pady=2)
        self.label_font_var = tk.DoubleVar(value=self.dynamic_settings.label_font_scale)
        label_font_scale = ttk.Scale(label_frame, from_=0.3, to=2.0, 
                                    variable=self.label_font_var,
                                    orient=tk.HORIZONTAL,
                                    command=lambda v: self.update_setting('label_font_scale', float(v)))
        label_font_scale.pack(fill=tk.X, pady=2)
    
    def create_presets_tab(self, parent):
        """Create presets management tab"""
        # Save preset
        save_frame = ttk.LabelFrame(parent, text="Save Preset", padding="10")
        save_frame.pack(fill=tk.X, pady=5)
        
        preset_name_frame = ttk.Frame(save_frame)
        preset_name_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(preset_name_frame, text="Preset Name:").pack(side=tk.LEFT, padx=5)
        self.preset_name_entry = ttk.Entry(preset_name_frame, width=30)
        self.preset_name_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(save_frame, text="💾 Save Preset", command=self.save_preset).pack(pady=5)
        
        # Load preset
        load_frame = ttk.LabelFrame(parent, text="Load Preset", padding="10")
        load_frame.pack(fill=tk.X, pady=5)
        
        # Preset list
        list_frame = ttk.Frame(load_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.preset_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.preset_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.preset_listbox.yview)
        
        ttk.Button(load_frame, text="📂 Load Selected Preset", command=self.load_preset).pack(pady=5)
        ttk.Button(load_frame, text="🗑 Delete Selected Preset", command=self.delete_preset).pack(pady=5)
        
        # Refresh preset list
        self.refresh_preset_list()
    
    def update_trail_length_label(self, value):
        """Update trail length label"""
        self.trail_length_label.config(text=f"Value: {value}")
    
    def toggle_pause(self):
        """Toggle pause/resume"""
        if self.dynamic_settings:
            self.dynamic_settings.paused = not self.dynamic_settings.paused
            if self.dynamic_settings.paused:
                self.pause_button.config(state=tk.DISABLED)
                self.resume_button.config(state=tk.NORMAL)
                self.status_label.config(text="⏸ PAUSED - Adjust settings, then resume")
            else:
                self.pause_button.config(state=tk.NORMAL)
                self.resume_button.config(state=tk.DISABLED)
                self.status_label.config(text="▶ Playing")
    
    def resume(self):
        """Resume playback"""
        if self.dynamic_settings:
            self.dynamic_settings.paused = False
            self.pause_button.config(state=tk.NORMAL)
            self.resume_button.config(state=tk.DISABLED)
            self.status_label.config(text="▶ Playing")
    
    def step_forward(self):
        """Step forward one frame (when paused)"""
        if self.dynamic_settings and self.dynamic_settings.paused:
            # This would need to be implemented in the analysis loop
            self.status_label.config(text="⏭ Stepped forward (requires frame stepping support)")
    
    def step_backward(self):
        """Step backward one frame (when paused)"""
        if self.dynamic_settings and self.dynamic_settings.paused:
            # This would need to be implemented in the analysis loop
            self.status_label.config(text="⏮ Stepped backward (requires frame stepping support)")
    
    def capture_screenshot(self):
        """Capture current frame as screenshot"""
        # This would need access to the current frame from the analysis
        screenshot_dir = "screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        # Placeholder - would need frame access
        self.status_label.config(text="📷 Screenshot captured (requires frame access)")
    
    def update_setting(self, setting_name, value):
        """Update a setting and save to history"""
        if not self.dynamic_settings:
            return
        
        # Save current state to history
        current_state = self.dynamic_settings.get_current_settings()
        self.settings_history.append(current_state.copy())
        self.current_history_index = len(self.settings_history) - 1
        
        # Update setting
        self.dynamic_settings.update_settings(**{setting_name: value})
        
        # Update undo/redo buttons
        self.update_history_buttons()
        
        # Call callback if provided
        if self.on_settings_update:
            self.on_settings_update(setting_name, value)
        
        self.status_label.config(text=f"✓ Updated {setting_name}")
    
    def undo_settings(self):
        """Undo last setting change"""
        if self.current_history_index > 0:
            self.current_history_index -= 1
            previous_state = self.settings_history[self.current_history_index]
            self.dynamic_settings.update_settings(**previous_state)
            self.update_history_buttons()
            self.status_label.config(text="↶ Undone")
    
    def redo_settings(self):
        """Redo setting change"""
        if self.current_history_index < len(self.settings_history) - 1:
            self.current_history_index += 1
            next_state = self.settings_history[self.current_history_index]
            self.dynamic_settings.update_settings(**next_state)
            self.update_history_buttons()
            self.status_label.config(text="↷ Redone")
    
    def update_history_buttons(self):
        """Update undo/redo button states"""
        self.undo_button.config(state=tk.NORMAL if self.current_history_index > 0 else tk.DISABLED)
        self.redo_button.config(state=tk.NORMAL if self.current_history_index < len(self.settings_history) - 1 else tk.DISABLED)
    
    def save_preset(self):
        """Save current settings as a preset"""
        preset_name = self.preset_name_entry.get().strip()
        if not preset_name:
            messagebox.showwarning("No Name", "Please enter a preset name")
            return
        
        preset_dir = "presets"
        os.makedirs(preset_dir, exist_ok=True)
        
        preset_file = os.path.join(preset_dir, f"{preset_name}.json")
        
        # Get current settings
        settings = self.dynamic_settings.get_current_settings()
        settings['preset_name'] = preset_name
        
        try:
            with open(preset_file, 'w') as f:
                json.dump(settings, f, indent=2)
            self.status_label.config(text=f"💾 Preset '{preset_name}' saved")
            self.refresh_preset_list()
            self.preset_name_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save preset: {e}")
    
    def load_preset(self):
        """Load a preset"""
        selection = self.preset_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a preset to load")
            return
        
        preset_name = self.preset_listbox.get(selection[0])
        preset_file = os.path.join("presets", f"{preset_name}.json")
        
        try:
            with open(preset_file, 'r') as f:
                settings = json.load(f)
            
            # Remove preset_name from settings
            settings.pop('preset_name', None)
            
            # Update all settings
            self.dynamic_settings.update_settings(**settings)
            
            # Update UI to reflect loaded settings
            self.refresh_ui_from_settings()
            
            self.status_label.config(text=f"📂 Preset '{preset_name}' loaded")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preset: {e}")
    
    def delete_preset(self):
        """Delete a preset"""
        selection = self.preset_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a preset to delete")
            return
        
        preset_name = self.preset_listbox.get(selection[0])
        preset_file = os.path.join("presets", f"{preset_name}.json")
        
        if messagebox.askyesno("Confirm Delete", f"Delete preset '{preset_name}'?"):
            try:
                os.remove(preset_file)
                self.status_label.config(text=f"🗑 Preset '{preset_name}' deleted")
                self.refresh_preset_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete preset: {e}")
    
    def refresh_preset_list(self):
        """Refresh the preset list"""
        self.preset_listbox.delete(0, tk.END)
        preset_dir = "presets"
        if os.path.exists(preset_dir):
            for filename in os.listdir(preset_dir):
                if filename.endswith('.json'):
                    preset_name = filename[:-5]  # Remove .json
                    self.preset_listbox.insert(tk.END, preset_name)
    
    def refresh_ui_from_settings(self):
        """Refresh UI elements to match current settings"""
        if not self.dynamic_settings:
            return
        
        # Update all UI variables to match current settings
        self.ball_tracking_var.set(self.dynamic_settings.track_ball_flag)
        self.show_trail_var.set(self.dynamic_settings.show_ball_trail)
        self.trail_length_var.set(self.dynamic_settings.trail_length)
        self.ball_min_var.set(self.dynamic_settings.ball_min_radius)
        self.ball_max_var.set(self.dynamic_settings.ball_max_radius)
        self.viz_style_var.set(self.dynamic_settings.viz_style)
        self.viz_color_var.set(self.dynamic_settings.viz_color_mode)
        self.box_thickness_var.set(self.dynamic_settings.box_thickness)
        self.ellipse_width_var.set(self.dynamic_settings.ellipse_width)
        self.ellipse_height_var.set(self.dynamic_settings.ellipse_height)
        self.show_labels_var.set(self.dynamic_settings.show_player_labels)
        self.label_font_var.set(self.dynamic_settings.label_font_scale)
    
    def update_status(self):
        """Update status bar periodically"""
        if self.dynamic_settings and hasattr(self.dynamic_settings, 'paused'):
            if hasattr(self, 'pause_button') and hasattr(self, 'resume_button'):
                if self.dynamic_settings.paused:
                    if self.pause_button['state'] != tk.DISABLED:
                        self.pause_button.config(state=tk.DISABLED)
                        self.resume_button.config(state=tk.NORMAL)
                else:
                    if self.pause_button['state'] != tk.NORMAL:
                        self.pause_button.config(state=tk.NORMAL)
                        self.resume_button.config(state=tk.DISABLED)
        
        # Schedule next update
        self.window.after(500, self.update_status)
    
    def create_player_correction_tab(self, parent):
        """Create player correction tab for fixing Re-ID assignments"""
        # Player Conflicts section (NEW)
        conflicts_frame = ttk.LabelFrame(parent, text="⚠ Player Conflicts (Choose Correct Track)", padding="10")
        conflicts_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Conflict statistics label
        self.conflict_stats_label = ttk.Label(conflicts_frame, text="No conflicts detected", 
                                             foreground="green", font=("Arial", 9, "bold"))
        self.conflict_stats_label.pack(pady=2)
        
        # Conflicts list
        conflicts_scrollbar = ttk.Scrollbar(conflicts_frame)
        conflicts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.conflicts_listbox = tk.Listbox(conflicts_frame, height=6, yscrollcommand=conflicts_scrollbar.set)
        self.conflicts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        conflicts_scrollbar.config(command=self.conflicts_listbox.yview)
        
        # Bind double-click to jump to track
        self.conflicts_listbox.bind('<Double-Button-1>', self.on_conflict_double_click)
        
        # Add tooltip/info label
        info_label = ttk.Label(conflicts_frame, 
                              text="💡 Double-click a track to jump to it | Select conflict and click 'Choose Selected Track' to resolve",
                              foreground="dark gray", font=("Arial", 8))
        info_label.pack(pady=2)
        
        # Conflict resolution buttons
        conflict_button_frame = ttk.Frame(conflicts_frame)
        conflict_button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(conflict_button_frame, text="✅ Choose Selected Track", command=self.resolve_selected_conflict).pack(side=tk.LEFT, padx=5)
        ttk.Button(conflict_button_frame, text="🔄 Refresh Conflicts", command=self.refresh_conflicts).pack(side=tk.LEFT, padx=5)
        ttk.Button(conflict_button_frame, text="📊 Show Statistics", command=self.show_conflict_statistics).pack(side=tk.LEFT, padx=5)
        
        # Current assignments display
        assignments_frame = ttk.LabelFrame(parent, text="Current Player Assignments", padding="10")
        assignments_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollable listbox for track assignments
        scrollbar1 = ttk.Scrollbar(assignments_frame)
        scrollbar1.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.assignments_listbox = tk.Listbox(assignments_frame, height=10, yscrollcommand=scrollbar1.set)
        self.assignments_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar1.config(command=self.assignments_listbox.yview)
        
        # Correction frame
        correction_frame = ttk.LabelFrame(parent, text="Correct Player Assignment", padding="10")
        correction_frame.pack(fill=tk.X, pady=5)
        
        # Track ID input
        ttk.Label(correction_frame, text="Track ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.track_id_var = tk.StringVar()
        track_id_entry = ttk.Entry(correction_frame, textvariable=self.track_id_var, width=10)
        track_id_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # Player selection
        ttk.Label(correction_frame, text="Correct Player:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.correct_player_var = tk.StringVar()
        player_combo = ttk.Combobox(correction_frame, textvariable=self.correct_player_var, width=20)
        player_combo.grid(row=1, column=1, padx=5, pady=5)
        
        # Load player names from gallery
        self.load_player_names(player_combo)
        
        # Buttons
        button_frame = ttk.Frame(correction_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="✅ Apply Correction", command=self.apply_player_correction).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🔄 Refresh Assignments", command=self.refresh_assignments).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🗑 Clear Correction", command=self.clear_correction).pack(side=tk.LEFT, padx=5)
        
        # Add keyboard shortcuts: Enter key to apply correction
        track_id_entry.bind('<Return>', lambda e: player_combo.focus_set())
        player_combo.bind('<Return>', lambda e: self.apply_player_correction())
        self.window.bind('<Control-Return>', lambda e: self.apply_player_correction())
        
        # Frame input for opening gallery seeder
        frame_input_frame = ttk.Frame(correction_frame)
        frame_input_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Label(frame_input_frame, text="Open Gallery Seeder at Frame:").pack(side=tk.LEFT, padx=5)
        self.gallery_seeder_frame_var = tk.StringVar()
        frame_entry = ttk.Entry(frame_input_frame, textvariable=self.gallery_seeder_frame_var, width=10)
        frame_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_input_frame, text="📸 Open Gallery Seeder", command=self.open_gallery_seeder_at_frame).pack(side=tk.LEFT, padx=5)
        
        # Corrections history
        history_frame = ttk.LabelFrame(parent, text="Applied Corrections", padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar2 = ttk.Scrollbar(history_frame)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.corrections_listbox = tk.Listbox(history_frame, height=8, yscrollcommand=scrollbar2.set)
        self.corrections_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar2.config(command=self.corrections_listbox.yview)
        
        # Auto-refresh assignments and conflicts
        self.refresh_assignments()
        self.refresh_conflicts()
        self.window.after(2000, self.auto_refresh_assignments)
        self.window.after(2000, self.auto_refresh_conflicts)
    
    def load_player_names(self, combo):
        """Load player names from gallery"""
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            gallery.load_gallery()
            player_names = [profile.name for profile in gallery.players.values()]
            combo['values'] = sorted(player_names) if player_names else ["Guest Player"]
        except Exception as e:
            print(f"Could not load player names: {e}")
            combo['values'] = ["Guest Player"]
    
    def refresh_assignments(self):
        """Refresh the current track assignments display"""
        self.assignments_listbox.delete(0, tk.END)
        
        try:
            # Try to get assignments from shared_state first (most up-to-date)
            import shared_state
            assignments = shared_state.get_current_track_assignments()
            if assignments:
                self.current_track_assignments = assignments
        except ImportError:
            # shared_state not available - analysis may not be running
            pass
        except Exception as e:
            # Log other errors but continue with cached data
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"⚠ Error loading assignments: {e}")
        
        if not self.current_track_assignments:
            self.assignments_listbox.insert(tk.END, "No active tracks")
            self.assignments_listbox.insert(tk.END, "(Analysis may not be running)")
            return
        
        # Sort tracks by ID (handle both numeric and string IDs)
        def sort_key(x):
            try:
                return int(x[0])
            except (ValueError, TypeError):
                return 0
        
        for track_id, player_name in sorted(self.current_track_assignments.items(), key=sort_key):
            correction = self.player_corrections.get(track_id, {})
            pending = False
            try:
                import shared_state
                pending_corrections = shared_state.get_pending_corrections()
                if track_id in pending_corrections:
                    pending = True
            except Exception as e:
                # Log error but continue
                if hasattr(self, 'status_label'):
                    self.status_label.config(text=f"⚠ Error checking corrections: {e}")
            
            if correction.get('applied', False):
                status = "✅ CORRECTED"
            elif pending:
                status = "⏳ PENDING"
            else:
                status = ""
            self.assignments_listbox.insert(tk.END, f"Track #{track_id}: {player_name} {status}")
    
    def update_track_assignment(self, track_id, player_name):
        """Update track assignment (called from analysis)"""
        try:
            self.current_track_assignments[track_id] = player_name
            # Auto-refresh if window is open (use after_idle to avoid threading issues)
            if hasattr(self, 'assignments_listbox'):
                # Use after_idle to ensure thread-safe GUI updates
                self.window.after_idle(self.refresh_assignments)
        except Exception as e:
            # Silently handle any errors (GUI might be closed)
            pass
    
    def apply_player_correction(self):
        """Apply a player correction"""
        track_id_str = self.track_id_var.get().strip()
        correct_player = self.correct_player_var.get().strip()
        
        if not track_id_str:
            messagebox.showwarning("Missing Track ID", "Please enter a Track ID")
            return
        
        if not correct_player:
            messagebox.showwarning("Missing Player", "Please select a player name")
            return
        
        try:
            track_id = int(track_id_str)
        except ValueError:
            messagebox.showerror("Invalid Track ID", f"Track ID must be a number, got: {track_id_str}")
            return
        
        # Check if this track is already assigned to this player
        try:
            import shared_state
            current_assignments = shared_state.get_current_track_assignments()
            if track_id in current_assignments and current_assignments[track_id] == correct_player:
                messagebox.showinfo("Already Correct", 
                                  f"Track #{track_id} is already assigned to {correct_player}")
                return
        except:
            pass
        
        # Store correction
        self.player_corrections[track_id] = {
            'correct_player': correct_player,
            'frame': getattr(self, 'current_frame', 0),
            'applied': False
        }
        
        # Try to apply immediately via shared state
        if self.apply_correction_to_analysis(track_id, correct_player):
            self.player_corrections[track_id]['applied'] = True
            self.current_track_assignments[track_id] = correct_player
            self.status_label.config(text=f"✅ Corrected Track #{track_id} → {correct_player}")
            
            # Create anchor frame for this correction
            try:
                self.create_anchor_frame_from_correction(track_id, correct_player)
            except Exception as e:
                # Don't fail if anchor frame creation fails - correction is still applied
                print(f"⚠ Could not create anchor frame: {e}")
            
            self.refresh_assignments()
            self.refresh_conflicts()  # Refresh conflicts in case this resolves one
            self.refresh_corrections_history()
            
            # Clear input fields after successful correction
            self.track_id_var.set("")
            self.correct_player_var.set("")
        else:
            messagebox.showwarning("Correction Queued", 
                                 f"Correction queued for Track #{track_id} → {correct_player}\n"
                                 "Will be applied on next frame")
    
    def apply_correction_to_analysis(self, track_id, correct_player):
        """Apply correction to the running analysis"""
        try:
            # Store in shared_state for analysis to pick up
            import shared_state
            shared_state.apply_player_correction(track_id, correct_player)
            return True
        except Exception as e:
            print(f"Error applying correction: {e}")
            return False
    
    def clear_correction(self):
        """Clear a correction"""
        track_id_str = self.track_id_var.get().strip()
        if not track_id_str:
            return
        
        try:
            track_id = int(track_id_str)
            if track_id in self.player_corrections:
                del self.player_corrections[track_id]
                self.status_label.config(text=f"🗑 Cleared correction for Track #{track_id}")
                self.refresh_assignments()
                self.refresh_corrections_history()
        except ValueError:
            pass
    
    def open_gallery_seeder_at_frame(self):
        """Open Player Gallery Seeder at a specific frame for tagging anchor frames"""
        try:
            # Get frame number from input
            frame_str = self.gallery_seeder_frame_var.get().strip()
            if not frame_str:
                messagebox.showwarning("Missing Frame", "Please enter a frame number")
                return
            
            try:
                frame_num = int(frame_str)
            except ValueError:
                messagebox.showerror("Invalid Frame", f"Frame number must be an integer, got: {frame_str}")
                return
            
            # Try to get video path from shared_state or dynamic_settings
            video_path = None
            try:
                import shared_state
                # Check if we can get video path from shared state
                if hasattr(shared_state, 'get_video_path'):
                    video_path = shared_state.get_video_path()
            except:
                pass
            
            # If no video path from shared state, try to get from dynamic_settings
            if not video_path and self.dynamic_settings:
                try:
                    if hasattr(self.dynamic_settings, 'input_path'):
                        video_path = self.dynamic_settings.input_path
                except:
                    pass
            
            # If still no video path, ask user
            if not video_path:
                video_path = filedialog.askopenfilename(
                    title="Select Video File",
                    filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
                )
                if not video_path:
                    return
            
            # Import and open gallery seeder
            from player_gallery_seeder import PlayerGallerySeeder
            
            # Check if window already exists
            if not hasattr(self, '_gallery_seeder_window') or not self._gallery_seeder_window or not self._gallery_seeder_window.winfo_exists():
                self._gallery_seeder_window = tk.Toplevel(self.window)
                self._gallery_seeder_window.transient(self.window)
                self._gallery_seeder_app = PlayerGallerySeeder(self._gallery_seeder_window)
            else:
                self._gallery_seeder_window.lift()
                self._gallery_seeder_window.focus_force()
            
            # Jump to the specified frame
            if hasattr(self, '_gallery_seeder_app'):
                success = self._gallery_seeder_app.jump_to_frame(frame_num, video_path)
                if success:
                    self.status_label.config(text=f"✓ Opened Gallery Seeder at frame {frame_num}")
                else:
                    messagebox.showerror("Error", f"Could not jump to frame {frame_num}")
            else:
                # Window was just created, get the app instance
                # The app is stored in the window's children - we need to access it differently
                # For now, just open the window and let user navigate manually
                self.status_label.config(text=f"✓ Opened Gallery Seeder - navigate to frame {frame_num}")
                messagebox.showinfo("Gallery Seeder Opened", 
                                  f"Gallery Seeder opened.\n\n"
                                  f"Please navigate to frame {frame_num} manually.\n\n"
                                  f"Video: {os.path.basename(video_path)}")
        
        except ImportError as e:
            messagebox.showerror("Error", 
                               f"Could not import player_gallery_seeder.py: {str(e)}\n\n"
                               "Make sure player_gallery_seeder.py is in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Gallery Seeder: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def refresh_corrections_history(self):
        """Refresh corrections history display"""
        self.corrections_listbox.delete(0, tk.END)
        
        for track_id, correction in sorted(self.player_corrections.items(), 
                                           key=lambda x: x[1].get('frame', 0), reverse=True):
            status = "✅ Applied" if correction.get('applied', False) else "⏳ Pending"
            frame = correction.get('frame', '?')
            player = correction.get('correct_player', '?')
            self.corrections_listbox.insert(tk.END, f"Track #{track_id} → {player} (Frame {frame}) {status}")
    
    def auto_refresh_assignments(self):
        """Auto-refresh assignments periodically"""
        self.refresh_assignments()
        self.window.after(3000, self.auto_refresh_assignments)  # Refresh every 3 seconds
    
    def refresh_conflicts(self):
        """Refresh the player conflicts display"""
        try:
            import shared_state
            conflicts = shared_state.get_player_conflicts()
            
            self.conflicts_listbox.delete(0, tk.END)
            
            if not conflicts:
                self.conflicts_listbox.insert(tk.END, "No player conflicts detected")
                self.conflicts_listbox.insert(tk.END, "(All tracks have unique player assignments)")
                if hasattr(self, 'conflict_stats_label'):
                    self.conflict_stats_label.config(text="✓ No conflicts detected", foreground="green")
                return
            
            # Count unresolved conflicts
            unresolved_count = sum(1 for c in conflicts.values() if not c.get('resolved', False))
            total_tracks_in_conflicts = sum(len(c.get('tracks', [])) for c in conflicts.values() if not c.get('resolved', False))
            
            # Update statistics label
            if hasattr(self, 'conflict_stats_label'):
                if unresolved_count > 0:
                    self.conflict_stats_label.config(
                        text=f"⚠ {unresolved_count} unresolved conflict(s) affecting {total_tracks_in_conflicts} track(s)", 
                        foreground="red"
                    )
                else:
                    self.conflict_stats_label.config(text="✓ All conflicts resolved", foreground="green")
            
            for player_name, conflict_data in sorted(conflicts.items()):
                tracks = conflict_data.get('tracks', [])
                frame = conflict_data.get('frame', '?')
                resolved = conflict_data.get('resolved', False)
                
                if resolved:
                    continue  # Skip resolved conflicts
                
                if len(tracks) > 1:
                    # Show conflict summary
                    tracks_str = ", ".join([f"#{t}" for t in tracks])
                    self.conflicts_listbox.insert(tk.END, f"⚠ {player_name} on tracks: {tracks_str} (Frame {frame})")
                    idx = self.conflicts_listbox.size() - 1
                    self.conflicts_listbox.itemconfig(idx, {'bg': '#FFEBEE'})  # Light red background
                    
                    # Make each track clickable
                    for track_id in tracks:
                        self.conflicts_listbox.insert(tk.END, f"  → Track #{track_id}: {player_name}")
                        idx = self.conflicts_listbox.size() - 1
                        self.conflicts_listbox.itemconfig(idx, {'bg': '#E3F2FD'})  # Light blue for clickable
        except ImportError:
            self.conflicts_listbox.delete(0, tk.END)
            self.conflicts_listbox.insert(tk.END, "⚠ shared_state module not available")
            self.conflicts_listbox.insert(tk.END, "(Analysis may not be running)")
            if hasattr(self, 'conflict_stats_label'):
                self.conflict_stats_label.config(text="⚠ Analysis not running", foreground="orange")
        except Exception as e:
            self.conflicts_listbox.delete(0, tk.END)
            self.conflicts_listbox.insert(tk.END, f"Error loading conflicts: {e}")
            if hasattr(self, 'conflict_stats_label'):
                self.conflict_stats_label.config(text=f"⚠ Error: {str(e)[:50]}", foreground="red")
    
    def on_conflict_double_click(self, event):
        """Handle double-click on conflict to jump to track"""
        selection = self.conflicts_listbox.curselection()
        if not selection:
            return
        
        conflict_text = self.conflicts_listbox.get(selection[0])
        
        # Parse conflict text: "🔍 Track #69: Rocco Piazza (Frame 3200)"
        try:
            import shared_state
            import re
            
            # Extract track ID and frame from text
            match = re.search(r'Track #(\d+):\s*([^(]+)\s*\(Frame\s*(\d+)\)', conflict_text)
            if match:
                track_id = int(match.group(1))
                player_name = match.group(2).strip()
                frame_num = int(match.group(3))
                
                # Request jump to this track
                if shared_state.request_track_jump(track_id, frame_num, player_name):
                    self.status_label.config(text=f"🔍 Jumping to Track #{track_id} (Frame {frame_num}) - {player_name}")
                    
                    # Show confirmation dialog
                    confirm_window = tk.Toplevel(self.window)
                    confirm_window.title(f"Confirm Track #{track_id}")
                    confirm_window.geometry("400x200")
                    confirm_window.transient(self.window)
                    
                    ttk.Label(confirm_window, 
                             text=f"Jumping to Track #{track_id} at Frame {frame_num}\n\n"
                                  f"Player: {player_name}\n\n"
                                  f"Confirm this is the correct track for {player_name}?",
                             font=("Arial", 10), justify=tk.LEFT).pack(pady=20, padx=20)
                    
                    def confirm_track():
                        if shared_state.confirm_track_jump(track_id, player_name):
                            messagebox.showinfo("Track Confirmed", 
                                               f"Track #{track_id} confirmed for {player_name}.\n\n"
                                               f"Breadcrumb set - future matches will prefer this track.")
                            confirm_window.destroy()
                            self.refresh_conflicts()
                            self.refresh_assignments()
                        else:
                            messagebox.showerror("Error", "Failed to confirm track")
                    
                    def reject_track():
                        # User says this is NOT the correct track
                        # They can manually correct it using the correction tab
                        confirm_window.destroy()
                        messagebox.showinfo("Track Not Confirmed", 
                                          f"Track #{track_id} not confirmed.\n\n"
                                          f"Use the 'Correct Player Assignment' section to fix this track.")
                    
                    button_frame = ttk.Frame(confirm_window)
                    button_frame.pack(pady=10)
                    ttk.Button(button_frame, text="✅ Confirm Track", command=confirm_track).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="❌ Not This Track", command=reject_track).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="Cancel", command=confirm_window.destroy).pack(side=tk.LEFT, padx=5)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to jump to track: {e}")
    
    def auto_refresh_conflicts(self):
        """Auto-refresh conflicts periodically"""
        self.refresh_conflicts()
        self.window.after(2000, self.auto_refresh_conflicts)
    
    def resolve_selected_conflict(self):
        """Resolve a player conflict by choosing the correct track"""
        selection = self.conflicts_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a conflict to resolve")
            return
        
        conflict_text = self.conflicts_listbox.get(selection[0])
        
        # Parse conflict text: "Rocco Piazza on tracks: #193, #248 (Frame 3200)"
        try:
            import shared_state
            conflicts = shared_state.get_player_conflicts()
            
            # Extract player name from conflict text
            if " on tracks:" in conflict_text:
                player_name = conflict_text.split(" on tracks:")[0].strip()
                
                if player_name in conflicts:
                    tracks = conflicts[player_name].get('tracks', [])
                    
                    if len(tracks) < 2:
                        messagebox.showwarning("Invalid Conflict", "This conflict has less than 2 tracks")
                        return
                    
                    # Create a dialog to choose the correct track
                    track_choice_window = tk.Toplevel(self.window)
                    track_choice_window.title(f"Resolve Conflict: {player_name}")
                    track_choice_window.geometry("400x200")
                    track_choice_window.transient(self.window)
                    
                    ttk.Label(track_choice_window, text=f"{player_name} is assigned to multiple tracks:", 
                             font=("Arial", 10, "bold")).pack(pady=10)
                    
                    # Radio buttons for each track
                    selected_track = tk.IntVar(value=tracks[0])
                    for i, track_id in enumerate(tracks):
                        ttk.Radiobutton(track_choice_window, text=f"Track #{track_id}", 
                                       variable=selected_track, value=track_id).pack(anchor=tk.W, padx=20, pady=5)
                    
                    def confirm_resolution():
                        correct_track = selected_track.get()
                        if shared_state.resolve_player_conflict(player_name, correct_track):
                            # Create anchor frame for this resolution
                            try:
                                self.create_anchor_frame_from_correction(correct_track, player_name)
                            except Exception as e:
                                # Don't fail if anchor frame creation fails - resolution is still applied
                                print(f"⚠ Could not create anchor frame: {e}")
                            
                            messagebox.showinfo("Conflict Resolved", 
                                               f"Resolved conflict: {player_name} will be assigned to Track #{correct_track}.\n\n"
                                               f"Other tracks will be cleared.\n\n"
                                               f"✓ Anchor frame created for this correction")
                            track_choice_window.destroy()
                            self.refresh_conflicts()
                            self.refresh_assignments()
                        else:
                            messagebox.showerror("Error", "Failed to resolve conflict")
                    
                    button_frame = ttk.Frame(track_choice_window)
                    button_frame.pack(pady=10)
                    ttk.Button(button_frame, text="✅ Resolve", command=confirm_resolution).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="Cancel", command=track_choice_window.destroy).pack(side=tk.LEFT, padx=5)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to resolve conflict: {e}")
    
    def create_anchor_frame_from_correction(self, track_id, player_name):
        """Create an anchor frame from a conflict resolution correction"""
        try:
            import shared_state
            import json
            import os
            
            # Get frame and bbox info for this track
            track_info = shared_state.get_track_frame_info(track_id)
            if not track_info:
                # Try to get from conflict data
                conflicts = shared_state.get_player_conflicts()
                frame_num = None
                for conflict_player, conflict_data in conflicts.items():
                    if conflict_player == player_name:
                        frame_num = conflict_data.get('frame')
                        break
                
                if not frame_num:
                    print(f"⚠ No frame info available for Track #{track_id} - cannot create anchor frame")
                    return False
            else:
                frame_num = track_info.get('frame')
                bbox = track_info.get('bbox')
                team = track_info.get('team')
                jersey = track_info.get('jersey')
            
            # Get video path from dynamic_settings
            video_path = None
            if self.dynamic_settings and hasattr(self.dynamic_settings, 'input_path'):
                video_path = self.dynamic_settings.input_path
            
            if not video_path:
                # Try to get from shared_state
                try:
                    if hasattr(shared_state, 'get_video_path'):
                        video_path = shared_state.get_video_path()
                except:
                    pass
            
            if not video_path:
                print(f"⚠ No video path available - cannot create anchor frame")
                return False
            
            # Find PlayerTagsSeed file
            video_dir = os.path.dirname(os.path.abspath(video_path))
            video_basename = os.path.splitext(os.path.basename(video_path))[0]
            seed_file = os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json")
            
            # Load existing seed file or create new one
            seed_data = {}
            if os.path.exists(seed_file):
                try:
                    with open(seed_file, 'r') as f:
                        seed_data = json.load(f)
                except Exception as e:
                    print(f"⚠ Could not load existing seed file: {e}")
                    seed_data = {}
            
            # Initialize anchor_frames if not present
            if 'anchor_frames' not in seed_data:
                seed_data['anchor_frames'] = {}
            
            # Initialize frame entry if not present
            frame_str = str(frame_num)
            if frame_str not in seed_data['anchor_frames']:
                seed_data['anchor_frames'][frame_str] = []
            
            # Check if anchor already exists for this track at this frame
            existing_anchor = None
            for anchor in seed_data['anchor_frames'][frame_str]:
                if anchor.get('track_id') == track_id:
                    existing_anchor = anchor
                    break
            
            # Get player info from gallery if available
            if not team or not jersey:
                try:
                    from player_gallery import PlayerGallery
                    gallery = PlayerGallery()
                    gallery.load_gallery()
                    for profile in gallery.players.values():
                        if profile.name == player_name:
                            if not team:
                                team = profile.team
                            if not jersey:
                                jersey = profile.jersey_number
                            break
                except:
                    pass
            
            # Create anchor frame entry
            anchor_entry = {
                'player_name': player_name,
                'track_id': track_id,
                'bbox': bbox if track_info and track_info.get('bbox') else None,
                'team': team or '',
                'jersey_number': jersey,
                'confidence': 1.0,  # High confidence for user corrections
                'source': 'conflict_resolution'  # Mark as from conflict resolution
            }
            
            if existing_anchor:
                # Update existing anchor
                existing_anchor.update(anchor_entry)
                print(f"✓ Updated anchor frame: Track #{track_id} → {player_name} (Frame {frame_num})")
            else:
                # Add new anchor
                seed_data['anchor_frames'][frame_str].append(anchor_entry)
                print(f"✓ Created anchor frame: Track #{track_id} → {player_name} (Frame {frame_num})")
            
            # Ensure video_path is set
            if 'video_path' not in seed_data:
                seed_data['video_path'] = video_path
            
            # Save updated seed file
            with open(seed_file, 'w') as f:
                json.dump(seed_data, f, indent=2)
            
            print(f"✓ Saved anchor frame to: {os.path.basename(seed_file)}")
            return True
            
        except Exception as e:
            print(f"⚠ Error creating anchor frame: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def show_conflict_statistics(self):
        """Show detailed conflict statistics"""
        try:
            import shared_state
            conflicts = shared_state.get_player_conflicts()
            assignments = shared_state.get_current_track_assignments()
            pending_corrections = shared_state.get_pending_corrections()
            
            # Count statistics
            total_conflicts = len(conflicts)
            unresolved_conflicts = sum(1 for c in conflicts.values() if not c.get('resolved', False))
            resolved_conflicts = total_conflicts - unresolved_conflicts
            total_tracks = len(assignments)
            tracks_in_conflicts = sum(len(c.get('tracks', [])) for c in conflicts.values() if not c.get('resolved', False))
            pending_corrections_count = len([c for c in pending_corrections.values() if c is not None])
            
            # Create statistics window
            stats_window = tk.Toplevel(self.window)
            stats_window.title("Conflict Resolution Statistics")
            stats_window.geometry("500x400")
            stats_window.transient(self.window)
            
            # Create scrollable text widget
            text_frame = ttk.Frame(stats_window, padding="10")
            text_frame.pack(fill=tk.BOTH, expand=True)
            
            scrollbar = ttk.Scrollbar(text_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            stats_text = tk.Text(text_frame, yscrollcommand=scrollbar.set, wrap=tk.WORD, font=("Courier", 10))
            stats_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=stats_text.yview)
            
            # Build statistics report
            report = f"""
╔══════════════════════════════════════════════════════════╗
║         CONFLICT RESOLUTION STATISTICS                   ║
╚══════════════════════════════════════════════════════════╝

📊 OVERVIEW:
   • Total Conflicts: {total_conflicts}
   • Unresolved: {unresolved_conflicts} ⚠
   • Resolved: {resolved_conflicts} ✓
   • Total Active Tracks: {total_tracks}
   • Tracks in Conflicts: {tracks_in_conflicts}
   • Pending Corrections: {pending_corrections_count}

📋 CONFLICT DETAILS:
"""
            if conflicts:
                for player_name, conflict_data in sorted(conflicts.items()):
                    tracks = conflict_data.get('tracks', [])
                    frame = conflict_data.get('frame', '?')
                    resolved = conflict_data.get('resolved', False)
                    status = "✓ RESOLVED" if resolved else "⚠ UNRESOLVED"
                    
                    report += f"\n   {status}: {player_name}\n"
                    report += f"      Tracks: {', '.join([f'#{t}' for t in tracks])}\n"
                    report += f"      Frame: {frame}\n"
            else:
                report += "\n   No conflicts detected\n"
            
            report += f"\n✅ PENDING CORRECTIONS:\n"
            if pending_corrections:
                for track_id, player in sorted(pending_corrections.items()):
                    if player is None:
                        report += f"   Track #{track_id}: UNASSIGN\n"
                    else:
                        report += f"   Track #{track_id}: {player}\n"
            else:
                report += "   No pending corrections\n"
            
            stats_text.insert(tk.END, report)
            stats_text.config(state=tk.DISABLED)  # Make read-only
            
            # Close button
            button_frame = ttk.Frame(stats_window)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Close", command=stats_window.destroy).pack()
            
        except ImportError:
            messagebox.showerror("Error", "shared_state module not available.\n\nAnalysis may not be running.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load statistics:\n{e}")
    
    def create_error_tab(self, parent):
        """Create error handling and corrections tab"""
        # Error log display
        error_log_frame = ttk.LabelFrame(parent, text="Error Log", padding="10")
        error_log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollable listbox for errors
        error_scrollbar = ttk.Scrollbar(error_log_frame)
        error_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.error_listbox = tk.Listbox(error_log_frame, height=15, yscrollcommand=error_scrollbar.set)
        self.error_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        error_scrollbar.config(command=self.error_listbox.yview)
        
        # Error actions
        error_actions_frame = ttk.LabelFrame(parent, text="Error Actions", padding="10")
        error_actions_frame.pack(fill=tk.X, pady=5)
        
        button_frame = ttk.Frame(error_actions_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="🔄 Refresh Errors", command=self.refresh_errors).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🗑 Clear Error Log", command=self.clear_error_log).pack(side=tk.LEFT, padx=5)
        
        # Info label
        info_label = ttk.Label(parent, 
                               text="Errors detected during analysis will appear here.\n"
                                    "You can fix Re-ID errors by using the Player Corrections tab.",
                               foreground="dark gray", font=("Arial", 9), justify=tk.LEFT)
        info_label.pack(pady=10)
        
        # Initial refresh
        self.refresh_errors()
    
    def refresh_errors(self):
        """Refresh the error log display"""
        self.error_listbox.delete(0, tk.END)
        
        if not self.error_log:
            self.error_listbox.insert(tk.END, "No errors detected")
            return
        
        for error in self.error_log[-50:]:  # Show last 50 errors
            frame = error.get('frame', '?')
            error_type = error.get('type', 'Unknown')
            message = error.get('message', 'No message')
            fixed = error.get('fixed', False)
            status = "✅ FIXED" if fixed else "⚠ PENDING"
            self.error_listbox.insert(tk.END, f"Frame {frame}: [{error_type}] {message} {status}")
    
    def clear_error_log(self):
        """Clear the error log"""
        self.error_log.clear()
        self.refresh_errors()
    
    def on_close(self):
        """Handle window close"""
        self.window.destroy()


if __name__ == "__main__":
    # Test window (requires dynamic_settings object)
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    # Create a placeholder dynamic_settings for testing/standalone mode
    class PlaceholderDynamicSettings:
        def __init__(self):
            self.paused = False
            self.track_ball_flag = True
            self.show_ball_trail = True
            self.trail_length = 20
            self.ball_min_radius = 5
            self.ball_max_radius = 50
            self.viz_style = "box"
            self.viz_color_mode = "team"
            self.box_thickness = 2
            self.ellipse_width = 20
            self.ellipse_height = 12
            self.show_player_labels = True
            self.label_font_scale = 0.7
        
        def update_settings(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        
        def get_current_settings(self):
            return {
                'track_ball_flag': self.track_ball_flag,
                'show_ball_trail': self.show_ball_trail,
                'trail_length': self.trail_length,
                'ball_min_radius': self.ball_min_radius,
                'ball_max_radius': self.ball_max_radius,
                'viz_style': self.viz_style,
                'viz_color_mode': self.viz_color_mode,
                'box_thickness': self.box_thickness,
                'ellipse_width': self.ellipse_width,
                'ellipse_height': self.ellipse_height,
                'show_player_labels': self.show_player_labels,
                'label_font_scale': self.label_font_scale,
            }
    
    placeholder_settings = PlaceholderDynamicSettings()
    app = LiveViewerControls(None, placeholder_settings)
    app.window.mainloop()

