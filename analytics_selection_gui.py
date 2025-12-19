"""
Analytics Selection GUI
Allows users to select which analytics to display during video playback
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os


class AnalyticsSelectionGUI:
    def __init__(self, parent=None, apply_callback=None, save_to_project_callback=None):
        self.parent = parent
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("Analytics Selection")
        self.window.geometry("600x750")
        self.window.minsize(500, 600)  # Ensure minimum size so buttons are visible
        
        # Callbacks for applying and saving to project
        self.apply_callback = apply_callback
        self.save_to_project_callback = save_to_project_callback
        
        # Analytics preferences
        self.preferences = self.load_preferences()
        
        # Create main frame with scrollbar
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Select Analytics to Display", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Description
        desc_label = ttk.Label(main_frame, 
                              text="Choose which analytics to show during video playback.\n"
                                   "Selected metrics will appear as overlays on the video.",
                              font=("Arial", 9))
        desc_label.pack(pady=(0, 15))
        
        # Create scrollable frame for checkboxes
        canvas = tk.Canvas(main_frame, height=450)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Analytics categories
        self.analytics_vars = {}
        
        # Speed Metrics
        speed_frame = ttk.LabelFrame(scrollable_frame, text="Speed Metrics", padding="10")
        speed_frame.pack(fill=tk.X, pady=5)
        
        self.analytics_vars['current_speed'] = tk.BooleanVar(value=self.preferences.get('current_speed', False))
        self.analytics_vars['average_speed'] = tk.BooleanVar(value=self.preferences.get('average_speed', False))
        self.analytics_vars['max_speed'] = tk.BooleanVar(value=self.preferences.get('max_speed', False))
        self.analytics_vars['acceleration'] = tk.BooleanVar(value=self.preferences.get('acceleration', False))
        
        ttk.Checkbutton(speed_frame, text="Current Speed", variable=self.analytics_vars['current_speed']).pack(anchor=tk.W)
        ttk.Checkbutton(speed_frame, text="Average Speed", variable=self.analytics_vars['average_speed']).pack(anchor=tk.W)
        ttk.Checkbutton(speed_frame, text="Max Speed", variable=self.analytics_vars['max_speed']).pack(anchor=tk.W)
        ttk.Checkbutton(speed_frame, text="Acceleration", variable=self.analytics_vars['acceleration']).pack(anchor=tk.W)
        
        # Distance Metrics
        distance_frame = ttk.LabelFrame(scrollable_frame, text="Distance Metrics", padding="10")
        distance_frame.pack(fill=tk.X, pady=5)
        
        self.analytics_vars['distance_traveled'] = tk.BooleanVar(value=self.preferences.get('distance_traveled', False))
        self.analytics_vars['distance_to_ball'] = tk.BooleanVar(value=self.preferences.get('distance_to_ball', True))
        self.analytics_vars['distance_from_center'] = tk.BooleanVar(value=self.preferences.get('distance_from_center', False))
        self.analytics_vars['distance_from_goal'] = tk.BooleanVar(value=self.preferences.get('distance_from_goal', False))
        self.analytics_vars['nearest_teammate'] = tk.BooleanVar(value=self.preferences.get('nearest_teammate', False))
        self.analytics_vars['nearest_opponent'] = tk.BooleanVar(value=self.preferences.get('nearest_opponent', False))
        
        ttk.Checkbutton(distance_frame, text="Distance Traveled", variable=self.analytics_vars['distance_traveled']).pack(anchor=tk.W)
        ttk.Checkbutton(distance_frame, text="Distance to Ball", variable=self.analytics_vars['distance_to_ball']).pack(anchor=tk.W)
        ttk.Checkbutton(distance_frame, text="Distance from Center", variable=self.analytics_vars['distance_from_center']).pack(anchor=tk.W)
        ttk.Checkbutton(distance_frame, text="Distance from Goal", variable=self.analytics_vars['distance_from_goal']).pack(anchor=tk.W)
        ttk.Checkbutton(distance_frame, text="Nearest Teammate Distance", variable=self.analytics_vars['nearest_teammate']).pack(anchor=tk.W)
        ttk.Checkbutton(distance_frame, text="Nearest Opponent Distance", variable=self.analytics_vars['nearest_opponent']).pack(anchor=tk.W)
        
        # Position Metrics
        position_frame = ttk.LabelFrame(scrollable_frame, text="Position Metrics", padding="10")
        position_frame.pack(fill=tk.X, pady=5)
        
        self.analytics_vars['field_zone'] = tk.BooleanVar(value=self.preferences.get('field_zone', False))
        self.analytics_vars['field_position'] = tk.BooleanVar(value=self.preferences.get('field_position', False))
        self.analytics_vars['movement_angle'] = tk.BooleanVar(value=self.preferences.get('movement_angle', False))
        
        ttk.Checkbutton(position_frame, text="Field Zone (Defensive/Midfield/Attacking)", 
                       variable=self.analytics_vars['field_zone']).pack(anchor=tk.W)
        ttk.Checkbutton(position_frame, text="Field Position (X/Y %)", 
                       variable=self.analytics_vars['field_position']).pack(anchor=tk.W)
        ttk.Checkbutton(position_frame, text="Movement Angle", 
                       variable=self.analytics_vars['movement_angle']).pack(anchor=tk.W)
        
        # Activity Metrics
        activity_frame = ttk.LabelFrame(scrollable_frame, text="Activity Metrics", padding="10")
        activity_frame.pack(fill=tk.X, pady=5)
        
        self.analytics_vars['possession_time'] = tk.BooleanVar(value=self.preferences.get('possession_time', False))
        self.analytics_vars['time_stationary'] = tk.BooleanVar(value=self.preferences.get('time_stationary', False))
        self.analytics_vars['sprint_count'] = tk.BooleanVar(value=self.preferences.get('sprint_count', False))
        self.analytics_vars['direction_changes'] = tk.BooleanVar(value=self.preferences.get('direction_changes', False))
        self.analytics_vars['acceleration_events'] = tk.BooleanVar(value=self.preferences.get('acceleration_events', False))
        
        ttk.Checkbutton(activity_frame, text="Possession Time", variable=self.analytics_vars['possession_time']).pack(anchor=tk.W)
        ttk.Checkbutton(activity_frame, text="Time Stationary", variable=self.analytics_vars['time_stationary']).pack(anchor=tk.W)
        ttk.Checkbutton(activity_frame, text="Sprint Count", variable=self.analytics_vars['sprint_count']).pack(anchor=tk.W)
        ttk.Checkbutton(activity_frame, text="Direction Changes", variable=self.analytics_vars['direction_changes']).pack(anchor=tk.W)
        ttk.Checkbutton(activity_frame, text="Acceleration Events", variable=self.analytics_vars['acceleration_events']).pack(anchor=tk.W)
        
        # Speed Zone Metrics
        zone_frame = ttk.LabelFrame(scrollable_frame, text="Speed Zone Distances", padding="10")
        zone_frame.pack(fill=tk.X, pady=5)
        
        self.analytics_vars['distance_walking'] = tk.BooleanVar(value=self.preferences.get('distance_walking', False))
        self.analytics_vars['distance_jogging'] = tk.BooleanVar(value=self.preferences.get('distance_jogging', False))
        self.analytics_vars['distance_running'] = tk.BooleanVar(value=self.preferences.get('distance_running', False))
        self.analytics_vars['distance_sprinting'] = tk.BooleanVar(value=self.preferences.get('distance_sprinting', False))
        
        ttk.Checkbutton(zone_frame, text="Distance Walking", variable=self.analytics_vars['distance_walking']).pack(anchor=tk.W)
        ttk.Checkbutton(zone_frame, text="Distance Jogging", variable=self.analytics_vars['distance_jogging']).pack(anchor=tk.W)
        ttk.Checkbutton(zone_frame, text="Distance Running", variable=self.analytics_vars['distance_running']).pack(anchor=tk.W)
        ttk.Checkbutton(zone_frame, text="Distance Sprinting", variable=self.analytics_vars['distance_sprinting']).pack(anchor=tk.W)
        
        # Event Counts (from detected events)
        event_frame = ttk.LabelFrame(scrollable_frame, text="Event Counts", padding="10")
        event_frame.pack(fill=tk.X, pady=5)
        
        self.analytics_vars['pass_count'] = tk.BooleanVar(value=self.preferences.get('pass_count', False))
        self.analytics_vars['shot_count'] = tk.BooleanVar(value=self.preferences.get('shot_count', False))
        self.analytics_vars['tackle_count'] = tk.BooleanVar(value=self.preferences.get('tackle_count', False))
        self.analytics_vars['goal_count'] = tk.BooleanVar(value=self.preferences.get('goal_count', False))
        self.analytics_vars['total_events'] = tk.BooleanVar(value=self.preferences.get('total_events', False))
        
        ttk.Checkbutton(event_frame, text="Pass Count", variable=self.analytics_vars['pass_count']).pack(anchor=tk.W)
        ttk.Checkbutton(event_frame, text="Shot Count", variable=self.analytics_vars['shot_count']).pack(anchor=tk.W)
        ttk.Checkbutton(event_frame, text="Tackle Count", variable=self.analytics_vars['tackle_count']).pack(anchor=tk.W)
        ttk.Checkbutton(event_frame, text="Goal Count", variable=self.analytics_vars['goal_count']).pack(anchor=tk.W)
        ttk.Checkbutton(event_frame, text="Total Events", variable=self.analytics_vars['total_events']).pack(anchor=tk.W)
        
        ttk.Label(event_frame, text="(Requires detected events CSV from Event Detection)", 
                 font=("Arial", 8), foreground="gray").pack(anchor=tk.W, padx=(20, 0))
        
        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Separator before buttons
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 5))
        
        # Buttons frame (all buttons in vertical stack)
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        # All buttons stacked vertically
        ttk.Button(buttons_frame, text="Select All", command=self.select_all, width=20).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(buttons_frame, text="Deselect All", command=self.deselect_all, width=20).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(buttons_frame, text="Recommended", command=self.select_recommended, width=20).pack(fill=tk.X, padx=5, pady=2)
        
        # Separator between quick select and action buttons
        ttk.Separator(buttons_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        ttk.Button(buttons_frame, text="Apply", command=self.apply_preferences, width=20).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(buttons_frame, text="Save & Close", command=self.save_and_close, width=20).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(buttons_frame, text="Cancel", command=self.cancel, width=20).pack(fill=tk.X, padx=5, pady=2)
        
    def select_all(self):
        """Select all analytics"""
        for var in self.analytics_vars.values():
            var.set(True)
    
    def deselect_all(self):
        """Deselect all analytics"""
        for var in self.analytics_vars.values():
            var.set(False)
    
    def select_recommended(self):
        """Select recommended analytics (most useful for real-time viewing)"""
        self.deselect_all()
        # Recommended: key metrics that are useful during playback
        recommended = [
            'current_speed', 'distance_to_ball', 'distance_traveled',
            'sprint_count', 'possession_time', 'pass_count', 'shot_count'
        ]
        for key in recommended:
            if key in self.analytics_vars:
                self.analytics_vars[key].set(True)
    
    def apply_preferences(self):
        """Apply preferences immediately without closing window"""
        # Get current selections
        preferences = {}
        for key, var in self.analytics_vars.items():
            preferences[key] = var.get()
        
        # Save to file (for backward compatibility)
        self.save_preferences(preferences)
        
        # Call apply callback if provided (for immediate display update)
        if self.apply_callback:
            try:
                self.apply_callback(preferences)
            except Exception as e:
                print(f"Warning: Apply callback failed: {e}")
        
        # Notify parent if it has a method to update (fallback)
        elif self.parent and hasattr(self.parent, 'update_analytics_preferences'):
            self.parent.update_analytics_preferences(preferences)
    
    def save_and_close(self):
        """Save preferences to project file and close window"""
        # Get current selections
        preferences = {}
        for key, var in self.analytics_vars.items():
            preferences[key] = var.get()
        
        # Save to file (for backward compatibility)
        self.save_preferences(preferences)
        
        # Save to project file if callback provided
        if self.save_to_project_callback:
            try:
                self.save_to_project_callback(preferences)
            except Exception as e:
                print(f"Warning: Save to project callback failed: {e}")
                # Still close even if project save fails
        else:
            # Fallback: apply preferences if no project save callback
            self.apply_preferences()
        
        # Then close
        self.window.destroy()
    
    def cancel(self):
        """Close without saving"""
        self.window.destroy()
    
    def get_selected_analytics(self):
        """Get list of selected analytics keys"""
        selected = []
        for key, var in self.analytics_vars.items():
            if var.get():
                selected.append(key)
        return selected
    
    def load_preferences(self):
        """Load analytics preferences from file"""
        prefs_file = "analytics_preferences.json"
        if os.path.exists(prefs_file):
            try:
                with open(prefs_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load analytics preferences: {e}")
        return {}
    
    def save_preferences(self, preferences):
        """Save analytics preferences to file"""
        prefs_file = "analytics_preferences.json"
        try:
            with open(prefs_file, 'w') as f:
                json.dump(preferences, f, indent=4)
            print(f"✓ Analytics preferences saved to {prefs_file}")
        except Exception as e:
            print(f"Warning: Could not save analytics preferences: {e}")


if __name__ == "__main__":
    # Test the GUI
    root = tk.Tk()
    root.withdraw()  # Hide main window
    app = AnalyticsSelectionGUI(root)
    root.mainloop()

