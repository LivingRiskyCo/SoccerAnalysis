"""
Player Stats & Management GUI
View player statistics, edit player names, and analyze performance
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import json
import os
from collections import defaultdict
from datetime import datetime

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageTk
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: cv2/PIL not available. Player preview will be disabled.")

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Install with: pip install matplotlib")

try:
    import seaborn as sns
    SEABORN_AVAILABLE = True
except ImportError:
    SEABORN_AVAILABLE = False


class PlayerStatsGUI:
    def __init__(self, root):
        print("DEBUG PlayerStatsGUI: Initializing...")
        self.root = root
        # Only set title and geometry if root is a Toplevel window (not a Frame)
        if isinstance(root, tk.Toplevel):
            self.root.title("Player Stats & Management")
            self.root.geometry("1200x800")
            self.root.resizable(True, True)
        
        # Prevent window from closing on errors (only for Toplevel windows)
        if isinstance(root, tk.Toplevel):
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        print("DEBUG PlayerStatsGUI: Window configured")
        
        self.csv_file = None
        self.df = None
        self.player_names = {}  # track_id: name
        self.player_roster = {}  # track_id: {name, team, jersey_number, active, etc.}
        self.video_file = None  # Path to video file
        
        print("DEBUG PlayerStatsGUI: Loading player names...")
        self.load_player_names()
        print("DEBUG PlayerStatsGUI: Player names loaded")
        
        # Create widgets with error handling
        print("DEBUG PlayerStatsGUI: Creating widgets...")
        try:
            self.create_widgets()
            print("DEBUG PlayerStatsGUI: Widgets created successfully")
        except Exception as e:
            import traceback
            error_msg = f"Error creating widgets: {e}\n{traceback.format_exc()}"
            print(f"ERROR PlayerStatsGUI: {error_msg}")
            from tkinter import messagebox
            messagebox.showerror("Error", error_msg)
            # Keep window open but don't start mainloop (it's already running from parent)
            # Just show the error and keep the window visible
            pass
        
        # Ensure window stays visible after widgets are created (only for Toplevel windows)
        if isinstance(root, tk.Toplevel):
            print("DEBUG PlayerStatsGUI: Setting window focus...")
            try:
                # Force window to be visible and on top
                self.root.update_idletasks()  # Update to get accurate dimensions
                self.root.lift()
                self.root.focus_force()
                self.root.attributes('-topmost', True)
                self.root.update()  # Force immediate update
                
                # Remove topmost after a brief moment (but keep window visible)
                self.root.after(300, lambda: self.root.attributes('-topmost', False))
                
                print("DEBUG PlayerStatsGUI: Window focus set")
            except Exception as e:
                print(f"DEBUG PlayerStatsGUI: Error setting focus: {e}")
            
            # Force multiple updates to ensure window is visible
            self.root.update()
            self.root.update_idletasks()
        else:
            # For Frame widgets, just update idletasks
            self.root.update_idletasks()
        print("DEBUG PlayerStatsGUI: Initialization complete")
    
    def on_closing(self):
        """Handle window closing"""
        self.root.destroy()
    
    def load_player_names(self):
        """Load player name mappings from file"""
        if os.path.exists("player_names.json"):
            try:
                with open("player_names.json", 'r') as f:
                    self.player_names = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load player names: {e}")
        
        # Also load roster data (team, jersey number, etc.) from setup wizard
        self.load_player_roster()
        
        # Update name combo values if widget exists
        if hasattr(self, 'name_combo'):
            self.update_name_combo_values()
    
    def load_player_roster(self):
        """Load player roster data (team, jersey number, etc.) from setup wizard"""
        # Try to load from dedicated roster file first
        if os.path.exists("player_roster.json"):
            try:
                with open("player_roster.json", 'r') as f:
                    self.player_roster = json.load(f)
                
                # CRITICAL FIX: Count unique player names, not track IDs
                # The roster may be keyed by track_id (one entry per video), so we need to count unique names
                unique_names = set()
                for entry in self.player_roster.values():
                    if isinstance(entry, dict) and "name" in entry:
                        unique_names.add(entry["name"])
                    elif isinstance(entry, str):
                        # Legacy format - entry is just the name
                        unique_names.add(entry)
                
                # If roster is name-based (keys are names), count keys
                if unique_names:
                    print(f"✓ Loaded roster data for {len(unique_names)} unique players ({len(self.player_roster)} total entries)")
                else:
                    # Fallback: if no names found, roster might be name-keyed
                    print(f"✓ Loaded roster data for {len(self.player_roster)} players")
            except Exception as e:
                print(f"Warning: Could not load player roster: {e}")
                self.player_roster = {}
        
        # Also try to load from seed_config.json (backup)
        if not self.player_roster and os.path.exists("seed_config.json"):
            try:
                with open("seed_config.json", 'r') as f:
                    seed_config = json.load(f)
                    roster_data = seed_config.get("player_roster", {})
                    if roster_data:
                        # Convert from name-based to track_id-based
                        # We need to map names to track IDs
                        player_mappings = seed_config.get("player_mappings", {})
                        name_to_ids = {}
                        for pid, mapping in player_mappings.items():
                            if isinstance(mapping, tuple):
                                name = mapping[0]
                            else:
                                name = mapping
                            if name:
                                if name not in name_to_ids:
                                    name_to_ids[name] = []
                                name_to_ids[name].append(pid)
                        
                        # Build roster dict
                        for player_name, roster_info in roster_data.items():
                            track_ids = name_to_ids.get(player_name, [])
                            for pid in track_ids:
                                self.player_roster[pid] = {
                                    "name": player_name,
                                    "team": roster_info.get("team", "Unknown"),
                                    "jersey_number": roster_info.get("jersey_number", ""),
                                    "active": roster_info.get("active", True),
                                    "first_seen_frame": roster_info.get("first_seen_frame"),
                                    "last_seen_frame": roster_info.get("last_seen_frame")
                                }
                        # Count unique player names (not track IDs)
                        unique_names = set()
                        for entry in self.player_roster.values():
                            if isinstance(entry, dict) and "name" in entry:
                                unique_names.add(entry["name"])
                        print(f"✓ Loaded roster data from seed_config.json for {len(unique_names)} unique players ({len(self.player_roster)} total track entries)")
            except Exception as e:
                print(f"Warning: Could not load roster from seed_config: {e}")
        
        # Also try to load from player_teams.json (legacy format)
        if os.path.exists("player_teams.json"):
            try:
                with open("player_teams.json", 'r') as f:
                    player_teams = json.load(f)
                    # Merge team info into roster
                    for pid, team in player_teams.items():
                        if pid not in self.player_roster:
                            self.player_roster[pid] = {
                                "name": self.player_names.get(pid, f"Player {pid}"),
                                "team": team,
                                "jersey_number": "",
                                "active": True
                            }
                        else:
                            self.player_roster[pid]["team"] = team
            except Exception as e:
                print(f"Warning: Could not load player teams: {e}")
    
    def save_player_names(self):
        """Save player name mappings to file"""
        try:
            with open("player_names.json", 'w') as f:
                json.dump(self.player_names, f, indent=4)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Could not save player names: {e}")
            return False
    
    def create_widgets(self):
        # Main notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 1: Load Data & Player Management
        self.tab1 = ttk.Frame(notebook)
        notebook.add(self.tab1, text="Player Management")
        self.create_management_tab()
        
        # Tab 2: Statistics
        self.tab2 = ttk.Frame(notebook)
        notebook.add(self.tab2, text="Statistics")
        self.create_stats_tab()
        
        # Tab 3: Visualizations
        self.tab3 = ttk.Frame(notebook)
        notebook.add(self.tab3, text="Charts")
        self.create_charts_tab()
        
        # Tab 4: Events
        self.tab4 = ttk.Frame(notebook)
        notebook.add(self.tab4, text="📊 Events")
        self.create_events_tab()
    
    def create_management_tab(self):
        """Create player management tab"""
        main_frame = ttk.Frame(self.tab1, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="Load Tracking Data", padding="10")
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file_frame, text="CSV File:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.csv_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.csv_path_var, width=60).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_csv).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(file_frame, text="Load", command=self.load_csv).grid(row=0, column=3, padx=5, pady=5)
        
        # Filter controls
        filter_frame = ttk.LabelFrame(main_frame, text="Filter Options", padding="10")
        filter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(filter_frame, text="Minimum Frames:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.min_frames_var = tk.IntVar(value=10)
        min_frames_spin = ttk.Spinbox(filter_frame, from_=0, to=1000, textvariable=self.min_frames_var, width=10)
        min_frames_spin.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(filter_frame, text="Sort by:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.sort_by_var = tk.StringVar(value="Frames")
        sort_combo = ttk.Combobox(filter_frame, textvariable=self.sort_by_var, 
                                 values=["Frames", "ID", "Name"], width=15, state="readonly")
        sort_combo.grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Button(filter_frame, text="Apply Filter", command=self.refresh_player_list).grid(row=0, column=4, padx=5, pady=5)
        
        # Statistics label
        self.stats_label = ttk.Label(filter_frame, text="Total Players: 0 | Significant: 0", 
                                    font=("Arial", 9))
        self.stats_label.grid(row=0, column=5, padx=10, pady=5)
        
        # Player list with names
        list_frame = ttk.LabelFrame(main_frame, text="Players", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Treeview for player list
        columns = ("ID", "Name", "Team", "Jersey", "Frames", "Avg Speed", "Max Speed", "Distance")
        self.player_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        
        for col in columns:
            self.player_tree.heading(col, text=col)
            if col == "Name":
                self.player_tree.column(col, width=200)
            elif col == "Jersey":
                self.player_tree.column(col, width=60)
            else:
                self.player_tree.column(col, width=100)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.player_tree.yview)
        self.player_tree.configure(yscrollcommand=scrollbar.set)
        
        self.player_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Edit player name
        edit_frame = ttk.LabelFrame(main_frame, text="Edit Player Name", padding="10")
        edit_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(edit_frame, text="Player ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.edit_id_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.edit_id_var, width=10, state="readonly").grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(edit_frame, text="Name:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.edit_name_var = tk.StringVar()
        self.name_combo = ttk.Combobox(edit_frame, textvariable=self.edit_name_var, width=30, 
                                       state="normal")  # Allow typing custom names
        self.name_combo.grid(row=0, column=3, padx=5, pady=5)
        self.update_name_combo_values()  # Load player names dynamically
        
        ttk.Label(edit_frame, text="Team:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        self.edit_team_var = tk.StringVar()
        self.team_combo = ttk.Combobox(edit_frame, textvariable=self.edit_team_var, width=15, 
                                       state="normal")  # Allow typing custom team names
        self.team_combo.grid(row=0, column=5, padx=5, pady=5)
        self.update_team_combo_values()  # Load team names dynamically
        
        ttk.Label(edit_frame, text="Jersey #:").grid(row=0, column=6, sticky=tk.W, padx=5, pady=5)
        self.edit_jersey_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.edit_jersey_var, width=10).grid(row=0, column=7, padx=5, pady=5)
        
        ttk.Button(edit_frame, text="Save", command=self.save_player_edit).grid(row=0, column=8, padx=5, pady=5)
        ttk.Button(edit_frame, text="Clear", command=self.clear_player_edit).grid(row=0, column=9, padx=5, pady=5)
        ttk.Button(edit_frame, text="Delete Player", command=self.delete_player, 
                  style="Danger.TButton").grid(row=0, column=10, padx=5, pady=5)
        
        # Configure danger button style
        style = ttk.Style()
        style.configure("Danger.TButton", foreground="red")
        
        # Preview button
        preview_frame = ttk.Frame(main_frame)
        preview_frame.pack(fill=tk.X, pady=5)
        ttk.Button(preview_frame, text="Preview Selected Player", 
                   command=self.preview_player, width=25).pack(side=tk.LEFT, padx=5)
        ttk.Label(preview_frame, text="(Shows player in video with ID highlighted)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=5)
        
        # Bind selection
        self.player_tree.bind("<<TreeviewSelect>>", self.on_player_select)
    
    def create_stats_tab(self):
        """Create statistics tab"""
        main_frame = ttk.Frame(self.tab2, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Stats display
        self.stats_text = tk.Text(main_frame, wrap=tk.WORD, font=("Courier", 10))
        stats_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.stats_text.yview)
        self.stats_text.configure(yscrollcommand=stats_scrollbar.set)
        
        self.stats_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        stats_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        ttk.Button(button_frame, text="Calculate Stats", command=self.calculate_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Stats", command=self.export_stats).pack(side=tk.LEFT, padx=5)
    
    def create_charts_tab(self):
        """Create charts/visualizations tab"""
        main_frame = ttk.Frame(self.tab3, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Chart type selection
        chart_frame = ttk.LabelFrame(main_frame, text="Chart Options", padding="10")
        chart_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(chart_frame, text="Chart Type:").pack(side=tk.LEFT, padx=5)
        self.chart_type_var = tk.StringVar(value="Distance")
        chart_combo = ttk.Combobox(chart_frame, textvariable=self.chart_type_var, 
                                   values=["Distance", "Speed", "Possession", "Heatmap"],
                                   state="readonly", width=20)
        chart_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(chart_frame, text="Generate Chart", command=self.generate_chart).pack(side=tk.LEFT, padx=5)
        
        # Chart canvas frame
        self.chart_frame = ttk.Frame(main_frame)
        self.chart_frame.pack(fill=tk.BOTH, expand=True)
    
    def create_events_tab(self):
        """Create events tab for viewing and managing player events"""
        main_frame = ttk.Frame(self.tab4, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Load events from gallery
        load_frame = ttk.LabelFrame(main_frame, text="Load Events", padding="10")
        load_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(load_frame, text="Detected Events CSV:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.events_csv_var = tk.StringVar()
        ttk.Entry(load_frame, textvariable=self.events_csv_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(load_frame, text="Browse", command=self.browse_events_csv).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(load_frame, text="Import to Gallery", command=self.import_events_to_gallery).grid(row=0, column=3, padx=5, pady=5)
        
        # Player selection
        player_frame = ttk.LabelFrame(main_frame, text="Select Player", padding="10")
        player_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(player_frame, text="Player:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.events_player_var = tk.StringVar()
        self.events_player_combo = ttk.Combobox(player_frame, textvariable=self.events_player_var, 
                                                width=30, state="readonly")
        self.events_player_combo.grid(row=0, column=1, padx=5, pady=5)
        self.events_player_combo.bind('<<ComboboxSelected>>', lambda e: self.load_player_events())
        ttk.Button(player_frame, text="Refresh Players", command=self.refresh_events_players).grid(row=0, column=2, padx=5, pady=5)
        
        # Event counts summary
        summary_frame = ttk.LabelFrame(main_frame, text="Event Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=5)
        
        self.events_summary_text = tk.Text(summary_frame, height=4, width=80, font=("Courier", 9))
        self.events_summary_text.pack(fill=tk.X, padx=5, pady=5)
        
        # Events list
        list_frame = ttk.LabelFrame(main_frame, text="Event History", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Treeview for events
        event_columns = ("Frame", "Time", "Type", "Confidence", "Verified", "Details")
        self.events_tree = ttk.Treeview(list_frame, columns=event_columns, show="headings", height=15)
        
        for col in event_columns:
            self.events_tree.heading(col, text=col)
            if col == "Details":
                self.events_tree.column(col, width=300)
            elif col == "Type":
                self.events_tree.column(col, width=100)
            else:
                self.events_tree.column(col, width=100)
        
        # Scrollbar
        events_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=events_scrollbar.set)
        
        self.events_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        events_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Event actions
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(action_frame, text="Verify Selected", command=self.verify_selected_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Mark False Positive", command=self.mark_false_positive).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Delete Event", command=self.delete_selected_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Export Events", command=self.export_player_events).pack(side=tk.LEFT, padx=5)
        
        # Initialize
        self.refresh_events_players()
    
    def browse_events_csv(self):
        """Browse for detected events CSV file"""
        filename = filedialog.askopenfilename(
            title="Select Detected Events CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.events_csv_var.set(filename)
    
    def import_events_to_gallery(self):
        """Import events from CSV into player gallery"""
        csv_path = self.events_csv_var.get()
        if not csv_path or not os.path.exists(csv_path):
            messagebox.showerror("Error", "Please select a valid events CSV file")
            return
        
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            events_added = gallery.import_events_from_csv(csv_path)
            gallery.save_gallery()
            
            if events_added:
                total = sum(events_added.values())
                messagebox.showinfo("Success", 
                                  f"Imported {total} events for {len(events_added)} players.\n\n"
                                  f"Events have been saved to player gallery.")
                self.refresh_events_players()
                self.load_player_events()
            else:
                messagebox.showwarning("Warning", "No events were imported. Check that player names match.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not import events: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_events_players(self):
        """Refresh player list for events tab"""
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            players = gallery.list_players()
            
            player_names = [name for pid, name in players]
            self.events_player_combo['values'] = sorted(set(player_names))
            
            if player_names and not self.events_player_var.get():
                self.events_player_var.set(player_names[0])
                self.load_player_events()
        except Exception as e:
            print(f"Warning: Could not refresh events players: {e}")
    
    def load_player_events(self):
        """Load events for selected player"""
        player_name = self.events_player_var.get()
        if not player_name:
            return
        
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            
            # Get events
            events = gallery.get_player_events(player_name)
            event_counts = gallery.get_player_event_counts(player_name)
            
            # Update summary
            self.events_summary_text.delete(1.0, tk.END)
            if event_counts:
                summary_lines = [f"Event Counts for {player_name}:\n"]
                for event_type, count in sorted(event_counts.items()):
                    summary_lines.append(f"  {event_type}: {count}")
                self.events_summary_text.insert(1.0, "\n".join(summary_lines))
            else:
                self.events_summary_text.insert(1.0, f"No events found for {player_name}")
            
            # Update events tree
            self.events_tree.delete(*self.events_tree.get_children())
            for event in sorted(events, key=lambda x: x.get('frame_num', 0)):
                frame_num = event.get('frame_num', 0)
                timestamp = event.get('timestamp', 0.0)
                event_type = event.get('event_type', 'unknown')
                confidence = event.get('confidence', 0.0)
                verified = "✅" if event.get('verified', False) else "⚠️"
                
                # Format details
                metadata = event.get('metadata', {})
                details_parts = []
                if 'receiver_name' in metadata:
                    details_parts.append(f"To: {metadata['receiver_name']}")
                if 'pass_distance_m' in metadata:
                    details_parts.append(f"Dist: {metadata['pass_distance_m']:.1f}m")
                if 'ball_speed_mps' in metadata:
                    details_parts.append(f"Speed: {metadata['ball_speed_mps']:.1f} m/s")
                details = " | ".join(details_parts) if details_parts else "-"
                
                self.events_tree.insert("", tk.END, values=(
                    frame_num,
                    f"{timestamp:.1f}s",
                    event_type,
                    f"{confidence:.2f}",
                    verified,
                    details
                ), tags=(event_type,))
            
            # Color code by event type
            self.events_tree.tag_configure("pass", foreground="blue")
            self.events_tree.tag_configure("shot", foreground="red")
            self.events_tree.tag_configure("tackle", foreground="orange")
            self.events_tree.tag_configure("goal", foreground="green")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load player events: {e}")
            import traceback
            traceback.print_exc()
    
    def verify_selected_event(self):
        """Mark selected event as verified"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event to verify")
            return
        
        # Get event details from selection
        item = self.events_tree.item(selection[0])
        values = item['values']
        frame_num = int(values[0])
        event_type = values[2]
        
        player_name = self.events_player_var.get()
        if not player_name:
            return
        
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            events = gallery.get_player_events(player_name)
            
            # Find and update event
            for event in events:
                if event.get('frame_num') == frame_num and event.get('event_type') == event_type:
                    event['verified'] = True
                    # Update player profile
                    player = gallery.get_player(player_name)
                    if player:
                        player.updated_at = datetime.now().isoformat()
                        gallery.save_gallery()
                        messagebox.showinfo("Success", "Event marked as verified")
                        self.load_player_events()
                        return
            
            messagebox.showwarning("Warning", "Event not found")
        except Exception as e:
            messagebox.showerror("Error", f"Could not verify event: {e}")
    
    def mark_false_positive(self):
        """Mark selected event as false positive"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event to mark")
            return
        
        # Get event details
        item = self.events_tree.item(selection[0])
        values = item['values']
        frame_num = int(values[0])
        event_type = values[2]
        
        player_name = self.events_player_var.get()
        if not player_name:
            return
        
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            player = gallery.get_player(player_name)
            
            if player and player.events:
                # Remove event
                player.events = [e for e in player.events 
                               if not (e.get('frame_num') == frame_num and e.get('event_type') == event_type)]
                
                # Update counts
                if player.event_counts and event_type in player.event_counts:
                    player.event_counts[event_type] = max(0, player.event_counts[event_type] - 1)
                
                player.updated_at = datetime.now().isoformat()
                gallery.save_gallery()
                messagebox.showinfo("Success", "Event marked as false positive and removed")
                self.load_player_events()
        except Exception as e:
            messagebox.showerror("Error", f"Could not mark event: {e}")
    
    def delete_selected_event(self):
        """Delete selected event"""
        if messagebox.askyesno("Confirm", "Delete this event?"):
            self.mark_false_positive()  # Same functionality
    
    def export_player_events(self):
        """Export player events to CSV"""
        player_name = self.events_player_var.get()
        if not player_name:
            messagebox.showwarning("Warning", "Please select a player")
            return
        
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            events = gallery.get_player_events(player_name)
            
            if not events:
                messagebox.showwarning("Warning", "No events to export")
                return
            
            filename = filedialog.asksaveasfilename(
                title="Export Events",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if filename:
                import pandas as pd
                df = pd.DataFrame(events)
                df.to_csv(filename, index=False)
                messagebox.showinfo("Success", f"Exported {len(events)} events to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export events: {e}")
    
    def browse_csv(self):
        """Browse for CSV file"""
        filename = filedialog.askopenfilename(
            title="Select Tracking Data CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.csv_path_var.set(filename)
    
    def load_csv(self):
        """Load CSV tracking data"""
        csv_file = self.csv_path_var.get()
        if not csv_file or not os.path.exists(csv_file):
            messagebox.showerror("Error", "Please select a valid CSV file")
            return
        
        try:
            self.csv_file = csv_file
            self.df = pd.read_csv(csv_file)
            
            # Reload player names (in case they were updated by consolidation or setup wizard)
            self.load_player_names()
            
            # Also check for consolidated CSV and reload names if found
            if "consolidated" in csv_file.lower() or "conolidated" in csv_file.lower():
                # Force reload of player names after consolidation
                self.load_player_names()
                print(f"Reloaded player names for consolidated CSV. Found {len(self.player_names)} names.")
            
            # Check if it's a tracking data CSV or speed data CSV
            if 'speed_mph' in self.df.columns or 'speed_kmh' in self.df.columns:
                self.load_speed_data()
            else:
                self.load_tracking_data()
            
            messagebox.showinfo("Success", f"Loaded {len(self.df)} rows of tracking data")
            # Update combo values with data from CSV
            self.update_name_combo_values()
            self.update_team_combo_values()
            self.refresh_player_list()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load CSV: {e}")
    
    def load_tracking_data(self):
        """Load standard tracking data CSV"""
        # Get unique players
        if 'player_id' in self.df.columns:
            player_ids = self.df['player_id'].dropna().unique()
            
            # Initialize player names if not set
            for pid in player_ids:
                if str(int(pid)) not in self.player_names:
                    self.player_names[str(int(pid))] = f"Player {int(pid)}"
    
    def load_speed_data(self):
        """Load speed tracking data CSV"""
        # Get unique players
        if 'player_id' in self.df.columns:
            player_ids = self.df['player_id'].dropna().unique()
            
            # Initialize player names if not set
            for pid in player_ids:
                if str(int(pid)) not in self.player_names:
                    self.player_names[str(int(pid))] = f"Player {int(pid)}"
    
    def refresh_player_list(self):
        """Refresh player list display"""
        if self.df is None:
            return
        
        # CRITICAL FIX: Check if widget still exists before accessing it
        # This prevents errors if the window/widget was destroyed
        try:
            # Check if widget exists by trying to access its winfo
            if not hasattr(self, 'player_tree') or not self.player_tree.winfo_exists():
                return
        except (tk.TclError, AttributeError):
            # Widget has been destroyed, can't refresh
            return
        
        # Clear existing items
        try:
            for item in self.player_tree.get_children():
                self.player_tree.delete(item)
        except (tk.TclError, AttributeError):
            # Widget was destroyed during operation, exit gracefully
            return
        
        # Check which type of data we have
        if 'speed_mph' in self.df.columns or 'speed_kmh' in self.df.columns:
            self.refresh_speed_player_list()
        else:
            self.refresh_tracking_player_list()
    
    def refresh_tracking_player_list(self):
        """Refresh list for standard tracking data"""
        if 'player_id' not in self.df.columns:
            return
        
        # CRITICAL FIX: Check if widget still exists before accessing it
        try:
            if not hasattr(self, 'player_tree') or not self.player_tree.winfo_exists():
                return
        except (tk.TclError, AttributeError):
            return
        
        player_stats = defaultdict(lambda: {'frames': 0, 'possession_frames': 0, 'distance': 0.0})
        
        # Calculate per-player stats
        for _, row in self.df.iterrows():
            if pd.notna(row.get('player_id')):
                pid = str(int(row['player_id']))
                player_stats[pid]['frames'] += 1
                
                if pd.notna(row.get('possession_player_id')) and str(int(row['possession_player_id'])) == pid:
                    player_stats[pid]['possession_frames'] += 1
                
                # Calculate distance (if we have previous position)
                if 'player_x' in row and 'player_y' in row:
                    if pd.notna(row['player_x']) and pd.notna(row['player_y']):
                        # Distance calculated frame-by-frame
                        pass
        
        # Filter by minimum frames
        min_frames = self.min_frames_var.get() if hasattr(self, 'min_frames_var') else 0
        filtered_stats = {pid: stats for pid, stats in player_stats.items() if stats['frames'] >= min_frames}
        
        # Update statistics label
        total_players = len(player_stats)
        significant_players = len(filtered_stats)
        if hasattr(self, 'stats_label'):
            self.stats_label.config(text=f"Total IDs: {total_players} | Significant (≥{min_frames} frames): {significant_players}")
        
        # Sort players
        sort_by = self.sort_by_var.get() if hasattr(self, 'sort_by_var') else "Frames"
        if sort_by == "Frames":
            sorted_pids = sorted(filtered_stats.keys(), key=lambda x: player_stats[x]['frames'], reverse=True)
        elif sort_by == "ID":
            sorted_pids = sorted(filtered_stats.keys(), key=lambda x: int(x))
        else:  # Name
            sorted_pids = sorted(filtered_stats.keys(), 
                               key=lambda x: self.player_names.get(x, f"Player {x}"))
        
        # Add players to tree
        for pid in sorted_pids:
            name = self.player_names.get(pid, f"Player {pid}")
            stats = filtered_stats[pid]
            
            # Get team and jersey from roster if available
            team = ""
            jersey = ""
            if pid in self.player_roster:
                roster_info = self.player_roster[pid]
                team = roster_info.get("team", "")
                jersey = roster_info.get("jersey_number", "")
                # Update name from roster if available
                if roster_info.get("name"):
                    name = roster_info["name"]
            
            # Display name with jersey if available
            display_name = name
            if jersey:
                display_name = f"{name} (#{jersey})"
            
            try:
                self.player_tree.insert("", tk.END, values=(
                    pid, display_name, team, jersey, stats['frames'], "", "", ""
                ))
            except (tk.TclError, AttributeError):
                # Widget was destroyed during operation, exit gracefully
                return
    
    def refresh_speed_player_list(self):
        """Refresh list for speed tracking data"""
        if 'player_id' not in self.df.columns:
            return
        
        # CRITICAL FIX: Check if widget still exists before accessing it
        try:
            if not hasattr(self, 'player_tree') or not self.player_tree.winfo_exists():
                return
        except (tk.TclError, AttributeError):
            return
        
        speed_col = 'speed_mph' if 'speed_mph' in self.df.columns else 'speed_kmh'
        distance_col = 'distance_miles' if 'distance_miles' in self.df.columns else 'distance_km'
        
        player_stats = {}
        
        for pid in self.df['player_id'].dropna().unique():
            pid_str = str(int(pid))
            player_data = self.df[self.df['player_id'] == pid]
            
            avg_speed = player_data[speed_col].mean() if speed_col in player_data.columns else 0
            max_speed = player_data[speed_col].max() if speed_col in player_data.columns else 0
            total_distance = player_data[distance_col].iloc[-1] if len(player_data) > 0 and distance_col in player_data.columns else 0
            
            # Get team
            team = ""
            if 'team' in player_data.columns:
                team_values = player_data['team'].dropna().unique()
                if len(team_values) > 0:
                    team = str(team_values[0])
            
            player_stats[pid_str] = {
                'frames': len(player_data),
                'avg_speed': avg_speed,
                'max_speed': max_speed,
                'distance': total_distance,
                'team': team
            }
        
        # Filter by minimum frames
        min_frames = self.min_frames_var.get() if hasattr(self, 'min_frames_var') else 0
        filtered_stats = {pid: stats for pid, stats in player_stats.items() if stats['frames'] >= min_frames}
        
        # Update statistics label
        total_players = len(player_stats)
        significant_players = len(filtered_stats)
        if hasattr(self, 'stats_label'):
            self.stats_label.config(text=f"Total IDs: {total_players} | Significant (≥{min_frames} frames): {significant_players}")
        
        # Sort players
        sort_by = self.sort_by_var.get() if hasattr(self, 'sort_by_var') else "Frames"
        if sort_by == "Frames":
            sorted_pids = sorted(filtered_stats.keys(), key=lambda x: player_stats[x]['frames'], reverse=True)
        elif sort_by == "ID":
            sorted_pids = sorted(filtered_stats.keys(), key=lambda x: int(x))
        else:  # Name
            sorted_pids = sorted(filtered_stats.keys(), 
                               key=lambda x: self.player_names.get(x, f"Player {x}"))
        
        speed_unit = "mph" if 'speed_mph' in self.df.columns else "km/h"
        dist_unit = "mi" if 'distance_miles' in self.df.columns else "km"
        
        # Add players to tree
        for pid in sorted_pids:
            name = self.player_names.get(pid, f"Player {pid}")
            stats = filtered_stats[pid]
            
            # Get team and jersey from roster if available (override CSV team if roster has it)
            team = stats.get('team', '')
            jersey = ""
            if pid in self.player_roster:
                roster_info = self.player_roster[pid]
                if roster_info.get("team"):
                    team = roster_info["team"]
                jersey = roster_info.get("jersey_number", "")
                # Update name from roster if available
                if roster_info.get("name"):
                    name = roster_info["name"]
            
            # Display name with jersey if available
            display_name = name
            if jersey:
                display_name = f"{name} (#{jersey})"
            
            try:
                self.player_tree.insert("", tk.END, values=(
                pid, display_name, team, jersey,
                stats['frames'], 
                f"{stats['avg_speed']:.1f} {speed_unit}" if stats['avg_speed'] > 0 else "",
                f"{stats['max_speed']:.1f} {speed_unit}" if stats['max_speed'] > 0 else "",
                f"{stats['distance']:.2f} {dist_unit}" if stats['distance'] > 0 else ""
            ))
            except (tk.TclError, AttributeError):
                # Widget was destroyed during operation, exit gracefully
                return
    
    def on_player_select(self, event):
        """Handle player selection"""
        # CRITICAL FIX: Check if widget still exists before accessing it
        try:
            if not hasattr(self, 'player_tree') or not self.player_tree.winfo_exists():
                return
        except (tk.TclError, AttributeError):
            return
        
        try:
            selection = self.player_tree.selection()
            if not selection:
                return
            
            item = self.player_tree.item(selection[0])
            values = item['values']
        except (tk.TclError, AttributeError):
            # Widget was destroyed during operation, exit gracefully
            return
        
        if len(values) >= 2:
            pid = str(int(values[0]))
            name_with_jersey = values[1] if len(values) > 1 else ""
            # Extract name (remove jersey number if present)
            name = name_with_jersey.split(" (#")[0] if " (#" in name_with_jersey else name_with_jersey
            team = values[2] if len(values) > 2 and values[2] else ""
            jersey = values[3] if len(values) > 3 and values[3] else ""
            
            # If no jersey in values, check roster
            if not jersey and pid in self.player_roster:
                jersey = self.player_roster[pid].get("jersey_number", "")
            
            self.edit_id_var.set(pid)
            self.edit_name_var.set(name)
            self.edit_team_var.set(team)
            self.edit_jersey_var.set(jersey)
    
    def save_player_edit(self):
        """Save edited player name, team, and jersey"""
        pid = self.edit_id_var.get()
        name = self.edit_name_var.get().strip()
        team = self.edit_team_var.get()
        jersey = self.edit_jersey_var.get().strip()
        
        if not pid:
            messagebox.showwarning("Warning", "Please select a player first")
            return
        
        if not name:
            messagebox.showwarning("Warning", "Please enter a player name")
            return
        
        # Save name
        self.player_names[pid] = name
        
        # Update roster data
        if pid not in self.player_roster:
            self.player_roster[pid] = {
                "name": name,
                "team": team,
                "jersey_number": jersey,
                "active": True
            }
        else:
            self.player_roster[pid]["name"] = name
            self.player_roster[pid]["team"] = team
            self.player_roster[pid]["jersey_number"] = jersey
        
        # Save roster to file
        try:
            with open("player_roster.json", 'w') as f:
                json.dump(self.player_roster, f, indent=4)
        except Exception as e:
            print(f"Warning: Could not save roster: {e}")
        
        # Also save to player_teams.json for backward compatibility
        if not os.path.exists("player_teams.json"):
            player_teams = {}
        else:
            try:
                with open("player_teams.json", 'r') as f:
                    player_teams = json.load(f)
            except:
                player_teams = {}
        
        player_teams[pid] = team
        try:
            with open("player_teams.json", 'w') as f:
                json.dump(player_teams, f, indent=4)
        except:
            pass
        
        if self.save_player_names():
            # Update combo values in case new names/teams were added
            self.update_name_combo_values()
            self.update_team_combo_values()
            messagebox.showinfo("Success", f"Player {pid} saved:\nName: {name}\nTeam: {team}\nJersey: {jersey}")
            self.refresh_player_list()
    
    def clear_player_edit(self):
        """Clear player edit fields"""
        self.edit_id_var.set("")
        self.edit_name_var.set("")
        self.edit_team_var.set("")
        self.edit_jersey_var.set("")
    
    def update_name_combo_values(self):
        """Update player name combobox with available player names"""
        names = set()
        
        # Add names from player_names.json
        for pid, name in self.player_names.items():
            if name and name.strip():
                names.add(name.strip())
        
        # Add names from roster
        for pid, roster_info in self.player_roster.items():
            if roster_info.get("name") and roster_info["name"].strip():
                names.add(roster_info["name"].strip())
        
        # Add names from player_name_list.json (if exists - from setup wizard)
        if os.path.exists("player_name_list.json"):
            try:
                with open("player_name_list.json", 'r') as f:
                    name_list = json.load(f)
                    if isinstance(name_list, list):
                        for name in name_list:
                            if name and name.strip():
                                names.add(name.strip())
            except:
                pass
        
        # Add names from CSV if loaded (from player_id column)
        if self.df is not None and 'player_id' in self.df.columns:
            # Get names that might be in the CSV (if there's a name column)
            if 'player_name' in self.df.columns:
                name_values = self.df['player_name'].dropna().unique()
                for name in name_values:
                    if name and str(name).strip():
                        names.add(str(name).strip())
        
        # Sort names alphabetically
        sorted_names = sorted(names, key=lambda x: x.lower())
        
        if hasattr(self, 'name_combo'):
            self.name_combo['values'] = sorted_names
    
    def update_team_combo_values(self):
        """Update team combobox with available team names from roster and data"""
        teams = set()
        
        # Add default teams
        teams.update(["Team 1", "Team 2", "Coach", "Referee", "Unknown"])
        
        # Add teams from team color config
        if os.path.exists("team_color_config.json"):
            try:
                with open("team_color_config.json", 'r') as f:
                    team_config = json.load(f)
                    if "team_colors" in team_config:
                        for team_key, team_data in team_config["team_colors"].items():
                            if isinstance(team_data, dict) and "name" in team_data:
                                teams.add(team_data["name"])
                            elif isinstance(team_data, str):
                                teams.add(team_data)
            except:
                pass
        
        # Add teams from roster
        for pid, roster_info in self.player_roster.items():
            if roster_info.get("team"):
                teams.add(roster_info["team"])
        
        # Add teams from CSV if loaded
        if self.df is not None and 'team' in self.df.columns:
            team_values = self.df['team'].dropna().unique()
            for team in team_values:
                if team:
                    teams.add(str(team))
        
        # Sort teams (put common ones first)
        sorted_teams = sorted(teams, key=lambda x: (
            0 if x in ["Team 1", "Team 2", "Coach", "Referee", "Unknown"] else 1,
            x.lower()
        ))
        
        if hasattr(self, 'team_combo'):
            self.team_combo['values'] = sorted_teams
    
    def delete_player(self):
        """Delete a player from the roster"""
        pid = self.edit_id_var.get()
        if not pid:
            messagebox.showwarning("Warning", "Please select a player first")
            return
        
        # Get player name for confirmation
        name = self.edit_name_var.get() or self.player_names.get(pid, f"Player {pid}")
        
        # Confirm deletion
        response = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete player:\n\n"
            f"ID: {pid}\n"
            f"Name: {name}\n\n"
            f"This will remove the player from the roster and player names.\n"
            f"The tracking data in the CSV will remain unchanged."
        )
        
        if not response:
            return
        
        # Remove from player_names
        if pid in self.player_names:
            del self.player_names[pid]
        
        # Remove from roster
        if pid in self.player_roster:
            del self.player_roster[pid]
        
        # Save changes
        try:
            # Save player names
            with open("player_names.json", 'w') as f:
                json.dump(self.player_names, f, indent=4)
            
            # Save roster
            with open("player_roster.json", 'w') as f:
                json.dump(self.player_roster, f, indent=4)
            
            # Update player_teams.json
            if os.path.exists("player_teams.json"):
                try:
                    with open("player_teams.json", 'r') as f:
                        player_teams = json.load(f)
                    if pid in player_teams:
                        del player_teams[pid]
                    with open("player_teams.json", 'w') as f:
                        json.dump(player_teams, f, indent=4)
                except:
                    pass
            
            messagebox.showinfo("Success", f"Player {pid} ({name}) deleted successfully")
            
            # Update combo values
            self.update_name_combo_values()
            self.update_team_combo_values()
            
            # Clear edit fields
            self.clear_player_edit()
            
            # Refresh player list
            self.refresh_player_list()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete player: {e}")
    
    def preview_player(self):
        """Preview selected player in video"""
        if not CV2_AVAILABLE:
            messagebox.showerror("Error", "OpenCV and PIL are required for player preview.\nInstall with: pip install opencv-python pillow")
            return
        
        # CRITICAL FIX: Check if widget still exists before accessing it
        try:
            if not hasattr(self, 'player_tree') or not self.player_tree.winfo_exists():
                messagebox.showwarning("Warning", "Player list widget is not available")
                return
        except (tk.TclError, AttributeError):
            messagebox.showwarning("Warning", "Player list widget is not available")
            return
        
        # Get selected player
        try:
            selection = self.player_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a player first")
                return
            
            item = self.player_tree.item(selection[0])
            values = item['values']
        except (tk.TclError, AttributeError):
            # Widget was destroyed during operation, exit gracefully
            return
        if len(values) < 1:
            return
        
        player_id = int(values[0])
        
        # Find video file
        if self.csv_file:
            # Try to find the analyzed video file
            csv_dir = os.path.dirname(self.csv_file)
            csv_basename = os.path.basename(self.csv_file)
            
            # Remove common suffixes
            base_name = csv_basename.replace('_tracking_data.csv', '').replace('_speed_data.csv', '').replace('_speed_tracked_speed_data.csv', '').replace('conolidated', '').replace('consolidated', '')
            
            # Look for analyzed video
            video_file = None
            for ext in ['.mp4', '.avi', '.mov']:
                test_path = os.path.join(csv_dir, f"{base_name}_analyzed{ext}")
                if os.path.exists(test_path):
                    video_file = test_path
                    break
            
            # If not found, try original video
            if not video_file:
                for ext in ['.mp4', '.avi', '.mov', '.mkv', '.m4v']:
                    test_path = os.path.join(csv_dir, f"{base_name}{ext}")
                    if os.path.exists(test_path):
                        video_file = test_path
                        break
            
            if not video_file:
                # Ask user to select video file
                video_file = filedialog.askopenfilename(
                    title="Select Video File",
                    initialdir=csv_dir,
                    filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v"), ("All files", "*.*")]
                )
            
            if not video_file or not os.path.exists(video_file):
                messagebox.showerror("Error", "Could not find video file. Please select it manually.")
                return
        else:
            # Ask user to select video file
            video_file = filedialog.askopenfilename(
                title="Select Video File",
                filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v"), ("All files", "*.*")]
            )
            if not video_file:
                return
        
        # Open player preview window
        self.open_player_preview(player_id, video_file)
    
    def open_player_preview(self, player_id, video_file):
        """Open player preview window"""
        try:
            # Create preview window
            preview_window = tk.Toplevel(self.root)
            preview_window.title(f"Player Preview - ID: {player_id}")
            preview_window.geometry("1200x900")  # Larger to accommodate zoom controls and thumbnails
            preview_window.transient(self.root)
            
            # Ensure window opens on top
            preview_window.lift()
            preview_window.attributes('-topmost', True)
            preview_window.focus_force()
            preview_window.after(200, lambda: preview_window.attributes('-topmost', False))
            
            # Create preview widget
            preview_widget = PlayerPreviewWidget(preview_window, player_id, video_file, self.df, self.player_names)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not open player preview: {e}")
            import traceback
            traceback.print_exc()

    def calculate_stats(self):
        """Calculate and display player statistics"""
        if self.df is None:
            messagebox.showwarning("Warning", "Please load a CSV file first")
            return
        
        self.stats_text.delete(1.0, tk.END)
        
        stats_text = "="*80 + "\n"
        stats_text += "PLAYER STATISTICS\n"
        stats_text += "="*80 + "\n\n"
        
        # Check data type
        if 'speed_mph' in self.df.columns or 'speed_kmh' in self.df.columns:
            stats_text += self.calculate_speed_stats()
        else:
            stats_text += self.calculate_tracking_stats()
        
        self.stats_text.insert(1.0, stats_text)
    
    def calculate_tracking_stats(self):
        """Calculate stats from tracking data"""
        stats_text = ""
        
        if 'player_id' not in self.df.columns:
            return "No player data found in CSV.\n"
        
        # Per-player stats
        player_stats = defaultdict(lambda: {
            'frames': 0, 'possession_frames': 0, 'distance': 0.0,
            'positions': [], 'ball_distances': []
        })
        
        prev_positions = {}
        
        for _, row in self.df.iterrows():
            if pd.notna(row.get('player_id')):
                pid = str(int(row['player_id']))
                player_stats[pid]['frames'] += 1
                
                if 'player_x' in row and 'player_y' in row:
                    if pd.notna(row['player_x']) and pd.notna(row['player_y']):
                        pos = (row['player_x'], row['player_y'])
                        player_stats[pid]['positions'].append(pos)
                        
                        # Calculate distance
                        if pid in prev_positions:
                            prev_pos = prev_positions[pid]
                            dist = ((pos[0] - prev_pos[0])**2 + (pos[1] - prev_pos[1])**2)**0.5
                            player_stats[pid]['distance'] += dist
                        prev_positions[pid] = pos
                
                if pd.notna(row.get('possession_player_id')):
                    if str(int(row['possession_player_id'])) == pid:
                        player_stats[pid]['possession_frames'] += 1
                        if 'distance_to_ball' in row and pd.notna(row['distance_to_ball']):
                            player_stats[pid]['ball_distances'].append(row['distance_to_ball'])
        
        # Display stats
        stats_text += f"Total Players: {len(player_stats)}\n"
        stats_text += f"Total Frames: {len(self.df)}\n\n"
        
        stats_text += "-"*80 + "\n"
        stats_text += "PER-PLAYER STATISTICS\n"
        stats_text += "-"*80 + "\n\n"
        
        for pid in sorted(player_stats.keys(), key=lambda x: int(x)):
            name = self.player_names.get(pid, f"Player {pid}")
            stats = player_stats[pid]
            
            stats_text += f"\n{name} (ID: {pid})\n"
            stats_text += f"  Frames Detected: {stats['frames']}\n"
            stats_text += f"  Possession Frames: {stats['possession_frames']}\n"
            if stats['frames'] > 0:
                possession_pct = (stats['possession_frames'] / stats['frames']) * 100
                stats_text += f"  Possession %: {possession_pct:.1f}%\n"
            stats_text += f"  Distance Traveled: {stats['distance']:.2f} pixels\n"
            if stats['ball_distances']:
                avg_dist = sum(stats['ball_distances']) / len(stats['ball_distances'])
                stats_text += f"  Avg Distance to Ball: {avg_dist:.2f}\n"
        
        return stats_text
    
    def calculate_speed_stats(self):
        """Calculate stats from speed tracking data"""
        stats_text = ""
        
        speed_col = 'speed_mph' if 'speed_mph' in self.df.columns else 'speed_kmh'
        distance_col = 'distance_miles' if 'distance_miles' in self.df.columns else 'distance_km'
        speed_unit = "mph" if 'speed_mph' in self.df.columns else "km/h"
        dist_unit = "miles" if 'distance_miles' in self.df.columns else "km"
        
        stats_text += f"Speed Unit: {speed_unit}\n"
        stats_text += f"Distance Unit: {dist_unit}\n"
        stats_text += f"Total Frames: {len(self.df)}\n\n"
        
        # Overall stats
        if speed_col in self.df.columns:
            stats_text += f"Overall Average Speed: {self.df[speed_col].mean():.2f} {speed_unit}\n"
            stats_text += f"Overall Max Speed: {self.df[speed_col].max():.2f} {speed_unit}\n"
        
        # Per-player stats
        if 'player_id' in self.df.columns:
            player_ids = self.df['player_id'].dropna().unique()
            
            stats_text += "-"*80 + "\n"
            stats_text += "PER-PLAYER STATISTICS\n"
            stats_text += "-"*80 + "\n\n"
            
            for pid in sorted(player_ids, key=lambda x: int(x)):
                pid_str = str(int(pid))
                name = self.player_names.get(pid_str, f"Player {pid_str}")
                player_data = self.df[self.df['player_id'] == pid]
                
                stats_text += f"\n{name} (ID: {pid_str})\n"
                stats_text += f"  Frames: {len(player_data)}\n"
                
                if speed_col in player_data.columns:
                    stats_text += f"  Average Speed: {player_data[speed_col].mean():.2f} {speed_unit}\n"
                    stats_text += f"  Max Speed: {player_data[speed_col].max():.2f} {speed_unit}\n"
                    stats_text += f"  Median Speed: {player_data[speed_col].median():.2f} {speed_unit}\n"
                
                if distance_col in player_data.columns and len(player_data) > 0:
                    final_distance = player_data[distance_col].iloc[-1]
                    stats_text += f"  Total Distance: {final_distance:.2f} {dist_unit}\n"
                
                # Team
                if 'team' in player_data.columns:
                    team_values = player_data['team'].dropna().unique()
                    if len(team_values) > 0:
                        stats_text += f"  Team: {team_values[0]}\n"
        
        return stats_text
    
    def export_stats(self):
        """Export statistics to file"""
        if self.df is None:
            messagebox.showwarning("Warning", "Please load a CSV file first")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Save Statistics",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                content = self.stats_text.get(1.0, tk.END)
                with open(filename, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Statistics exported to: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not export: {e}")
    
    def generate_chart(self):
        """Generate chart based on selected type"""
        if self.df is None:
            messagebox.showwarning("Warning", "Please load a CSV file first")
            return
        
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showerror("Error", "matplotlib not available. Install with: pip install matplotlib")
            return
        
        # Clear existing chart
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        
        chart_type = self.chart_type_var.get()
        
        if chart_type == "Distance":
            self.chart_distance()
        elif chart_type == "Speed":
            self.chart_speed()
        elif chart_type == "Possession":
            self.chart_possession()
        elif chart_type == "Heatmap":
            self.chart_heatmap()
    
    def chart_distance(self):
        """Chart distance traveled per player"""
        if 'player_id' not in self.df.columns:
            return
        
        distance_col = 'distance_miles' if 'distance_miles' in self.df.columns else 'distance_km'
        if distance_col not in self.df.columns:
            messagebox.showwarning("Warning", "No distance data in CSV")
            return
        
        player_distances = {}
        for pid in self.df['player_id'].dropna().unique():
            pid_str = str(int(pid))
            player_data = self.df[self.df['player_id'] == pid]
            if len(player_data) > 0:
                name = self.player_names.get(pid_str, f"Player {pid_str}")
                final_dist = player_data[distance_col].iloc[-1]
                player_distances[name] = final_dist
        
        if not player_distances:
            return
        
        fig, ax = plt.subplots(figsize=(10, 6))
        names = list(player_distances.keys())
        distances = list(player_distances.values())
        
        bars = ax.barh(names, distances)
        ax.set_xlabel('Distance' + (' (miles)' if 'distance_miles' in self.df.columns else ' (km)'))
        ax.set_title('Distance Traveled by Player')
        ax.grid(axis='x', alpha=0.3)
        
        # Add value labels
        for i, (name, dist) in enumerate(zip(names, distances)):
            ax.text(dist, i, f' {dist:.2f}', va='center')
        
        plt.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, self.chart_frame)
        canvas.draw()
        canvas.get_widget().pack(fill=tk.BOTH, expand=True)
    
    def chart_speed(self):
        """Chart speed statistics"""
        speed_col = 'speed_mph' if 'speed_mph' in self.df.columns else 'speed_kmh'
        if speed_col not in self.df.columns:
            messagebox.showwarning("Warning", "No speed data in CSV")
            return
        
        player_stats = {}
        for pid in self.df['player_id'].dropna().unique():
            pid_str = str(int(pid))
            player_data = self.df[self.df['player_id'] == pid]
            if len(player_data) > 0:
                name = self.player_names.get(pid_str, f"Player {pid_str}")
                player_stats[name] = {
                    'avg': player_data[speed_col].mean(),
                    'max': player_data[speed_col].max()
                }
        
        if not player_stats:
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        names = list(player_stats.keys())
        avg_speeds = [player_stats[n]['avg'] for n in names]
        max_speeds = [player_stats[n]['max'] for n in names]
        
        ax1.barh(names, avg_speeds)
        ax1.set_xlabel('Average Speed' + (' (mph)' if 'speed_mph' in self.df.columns else ' (km/h)'))
        ax1.set_title('Average Speed by Player')
        ax1.grid(axis='x', alpha=0.3)
        
        ax2.barh(names, max_speeds)
        ax2.set_xlabel('Max Speed' + (' (mph)' if 'speed_mph' in self.df.columns else ' (km/h)'))
        ax2.set_title('Max Speed by Player')
        ax2.grid(axis='x', alpha=0.3)
        
        plt.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, self.chart_frame)
        canvas.draw()
        canvas.get_widget().pack(fill=tk.BOTH, expand=True)
    
    def chart_possession(self):
        """Chart possession statistics"""
        if 'possession_player_id' not in self.df.columns:
            messagebox.showwarning("Warning", "No possession data in CSV")
            return
        
        player_possession = defaultdict(int)
        total_frames = len(self.df)
        
        for _, row in self.df.iterrows():
            if pd.notna(row.get('possession_player_id')):
                pid = str(int(row['possession_player_id']))
                player_possession[pid] += 1
        
        if not player_possession:
            return
        
        player_names_list = []
        possession_counts = []
        for pid in sorted(player_possession.keys(), key=lambda x: int(x)):
            name = self.player_names.get(pid, f"Player {pid}")
            player_names_list.append(name)
            pct = (player_possession[pid] / total_frames) * 100 if total_frames > 0 else 0
            possession_counts.append(pct)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.barh(player_names_list, possession_counts)
        ax.set_xlabel('Possession %')
        ax.set_title('Ball Possession by Player')
        ax.grid(axis='x', alpha=0.3)
        
        # Add value labels
        for i, (name, pct) in enumerate(zip(player_names_list, possession_counts)):
            ax.text(pct, i, f' {pct:.1f}%', va='center')
        
        plt.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, self.chart_frame)
        canvas.draw()
        canvas.get_widget().pack(fill=tk.BOTH, expand=True)
    
    def chart_heatmap(self):
        """Generate player position heatmap"""
        if 'player_x' not in self.df.columns or 'player_y' not in self.df.columns:
            messagebox.showwarning("Warning", "No position data in CSV")
            return
        
        # Collect all positions
        positions = []
        for _, row in self.df.iterrows():
            if pd.notna(row.get('player_x')) and pd.notna(row.get('player_y')):
                positions.append([row['player_x'], row['player_y']])
        
        if not positions:
            return
        
        positions = np.array(positions)
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Create heatmap
        h = ax.hist2d(positions[:, 0], positions[:, 1], bins=50, cmap='hot')
        plt.colorbar(h[3], ax=ax, label='Frequency')
        ax.set_xlabel('X Position (pixels)')
        ax.set_ylabel('Y Position (pixels)')
        ax.set_title('Player Position Heatmap')
        ax.set_aspect('equal')
        
        plt.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, self.chart_frame)
        canvas.draw()
        canvas.get_widget().pack(fill=tk.BOTH, expand=True)


class PlayerPreviewWidget:
    """Widget for previewing a player in video frames"""
    
    def __init__(self, root, player_id, video_file, df, player_names):
        self.root = root
        self.player_id = player_id
        self.video_file = video_file
        self.df = df
        self.player_names = player_names
        
        # Get player name
        player_name = player_names.get(str(player_id), f"Player {player_id}")
        
        # Get frames where this player appears
        # Try 'frame' column first, then use index as frame number
        if df is not None and 'player_id' in df.columns:
            player_data = df[df['player_id'] == player_id]
            if 'frame' in df.columns:
                player_frames = player_data['frame'].dropna().unique()
                player_frames = sorted(player_frames.astype(int))
            else:
                # Use index as frame number
                player_frames = sorted(player_data.index.astype(int).tolist())
        else:
            player_frames = []
        
        # Open video
        self.cap = cv2.VideoCapture(video_file)
        if not self.cap.isOpened():
            messagebox.showerror("Error", f"Could not open video file: {video_file}")
            root.destroy()
            return
        
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Current frame index in player_frames list
        self.current_frame_idx = 0
        self.player_frames = player_frames
        
        # Zoom state
        self.zoom_level = 1.0  # 1.0 = no zoom, 2.0 = 2x zoom, etc.
        self.zoom_enabled = False
        self.zoom_center = None  # Center point for zoom (player position)
        
        # Create UI
        self.create_widgets(player_name)
        
        # Load first frame
        if player_frames:
            self.load_frame(player_frames[0])
        else:
            # No frames found, show first frame of video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if ret:
                self.display_frame(frame, None)
    
    def create_widgets(self, player_name):
        """Create preview widgets"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(header_frame, text=f"Player: {player_name} (ID: {self.player_id})", 
                 font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
        
        if self.player_frames:
            ttk.Label(header_frame, text=f"Frames: {len(self.player_frames)}", 
                     font=("Arial", 10)).pack(side=tk.LEFT, padx=10)
        
        # Image display with zoom controls
        image_frame = ttk.Frame(main_frame)
        image_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Zoom controls
        zoom_frame = ttk.Frame(image_frame)
        zoom_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(zoom_frame, text="Zoom:").pack(side=tk.LEFT, padx=5)
        ttk.Button(zoom_frame, text="Zoom In (2x)", command=self.zoom_in, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Zoom Out", command=self.zoom_out, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_frame, text="Reset Zoom", command=self.reset_zoom, width=12).pack(side=tk.LEFT, padx=2)
        self.zoom_label = ttk.Label(zoom_frame, text="1.0x")
        self.zoom_label.pack(side=tk.LEFT, padx=10)
        
        self.canvas = tk.Canvas(image_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Frame selection panel (collapsible)
        self.frame_selection_frame = ttk.LabelFrame(main_frame, text="Frame Selection (Click thumbnail to jump)", padding="5")
        self.frame_selection_frame.pack(fill=tk.BOTH, expand=False, pady=5)
        
        # Toggle button for frame selection
        toggle_frame = ttk.Frame(self.frame_selection_frame)
        toggle_frame.pack(fill=tk.X, pady=2)
        self.show_frames_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toggle_frame, text="Show Frame Thumbnails", 
                       variable=self.show_frames_var, 
                       command=self.toggle_frame_selection).pack(side=tk.LEFT, padx=5)
        
        # Frame thumbnails container (initially hidden)
        self.thumbnails_frame = ttk.Frame(self.frame_selection_frame)
        self.thumbnails_canvas = tk.Canvas(self.thumbnails_frame, height=0)  # Start hidden
        thumbnails_scrollbar = ttk.Scrollbar(self.frame_selection_frame, orient=tk.HORIZONTAL, 
                                            command=self.thumbnails_canvas.xview)
        self.thumbnails_canvas.configure(xscrollcommand=thumbnails_scrollbar.set)
        
        self.thumbnails_container = ttk.Frame(self.thumbnails_canvas)
        self.thumbnails_canvas_window = self.thumbnails_canvas.create_window((0, 0), window=self.thumbnails_container, anchor=tk.NW)
        
        # Store scrollbar reference
        self.thumbnails_scrollbar = thumbnails_scrollbar
        
        # Controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(controls_frame, text="◄◄ Previous", 
                   command=self.prev_frame, width=15).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(controls_frame, text="►► Next", 
                   command=self.next_frame, width=15).pack(side=tk.LEFT, padx=5)
        
        # Frame jump
        ttk.Label(controls_frame, text="Jump to Frame:").pack(side=tk.LEFT, padx=5)
        self.frame_var = tk.StringVar()
        frame_entry = ttk.Entry(controls_frame, textvariable=self.frame_var, width=10)
        frame_entry.pack(side=tk.LEFT, padx=5)
        frame_entry.bind("<Return>", self.jump_to_frame)
        
        ttk.Button(controls_frame, text="Jump", 
                   command=self.jump_to_frame, width=10).pack(side=tk.LEFT, padx=5)
        
        # Frame info
        self.frame_info_label = ttk.Label(controls_frame, text="Frame: 0 / 0")
        self.frame_info_label.pack(side=tk.LEFT, padx=10)
        
        # Navigation
        if self.player_frames:
            ttk.Label(controls_frame, text=f"Player appears in {len(self.player_frames)} frames").pack(side=tk.LEFT, padx=10)
    
    def load_frame(self, frame_num):
        """Load a specific frame from video"""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_num))
        ret, frame = self.cap.read()
        
        if not ret:
            return
        
        # Get player position from CSV if available
        player_pos = None
        if self.df is not None and 'player_id' in self.df.columns:
            if 'frame' in self.df.columns:
                frame_data = self.df[(self.df['frame'] == frame_num) & (self.df['player_id'] == self.player_id)]
            else:
                # Use index as frame number
                frame_data = self.df[(self.df.index == frame_num) & (self.df['player_id'] == self.player_id)]
            
            if len(frame_data) > 0:
                row = frame_data.iloc[0]
                if 'player_x' in row and 'player_y' in row:
                    if pd.notna(row['player_x']) and pd.notna(row['player_y']):
                        player_pos = (int(row['player_x']), int(row['player_y']))
        
        self.display_frame(frame, player_pos)
        
        # Update frame info
        if self.player_frames:
            try:
                self.current_frame_idx = self.player_frames.index(int(frame_num))
            except ValueError:
                # Frame not in player_frames, find closest
                if len(self.player_frames) > 0:
                    closest_idx = min(range(len(self.player_frames)), 
                                     key=lambda i: abs(self.player_frames[i] - frame_num))
                    self.current_frame_idx = closest_idx
                else:
                    self.current_frame_idx = 0
            
            self.frame_info_label.config(text=f"Frame: {int(frame_num)} ({self.current_frame_idx + 1}/{len(self.player_frames)})")
            self.frame_var.set(str(int(frame_num)))
        else:
            self.frame_info_label.config(text=f"Frame: {int(frame_num)}")
            self.frame_var.set(str(int(frame_num)))
    
    def display_frame(self, frame, player_pos):
        """Display frame with player highlighted"""
        # Store original frame and player position for zoom
        self.current_frame = frame.copy()
        self.current_player_pos = player_pos
        
        # Draw circle/highlight around player if position is known
        display_frame = frame.copy()
        
        if player_pos:
            x, y = player_pos
            # Draw large circle around player
            cv2.circle(display_frame, (x, y), 50, (0, 255, 0), 3)  # Green circle
            cv2.circle(display_frame, (x, y), 5, (0, 255, 0), -1)  # Green center dot
            
            # Draw label with player ID and name
            label = f"ID: {self.player_id}"
            player_name = self.player_names.get(str(self.player_id), f"Player {self.player_id}")
            if player_name != f"Player {self.player_id}":
                label = f"{player_name} (ID: {self.player_id})"
            
            # Background for text
            (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            cv2.rectangle(display_frame, 
                         (x - text_width // 2 - 5, y - 60),
                         (x + text_width // 2 + 5, y - 40),
                         (0, 0, 0), -1)
            
            # Text
            cv2.putText(display_frame, label, 
                       (x - text_width // 2, y - 45),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Apply zoom if enabled
        if self.zoom_enabled and player_pos:
            display_frame = self.apply_zoom(display_frame, player_pos)
        
        # Resize for display
        display_height = 600
        aspect_ratio = self.width / self.height
        display_width = int(display_height * aspect_ratio)
        
        if display_width > 900:
            display_width = 900
            display_height = int(display_width / aspect_ratio)
        
        display_frame = cv2.resize(display_frame, (display_width, display_height))
        
        # Convert to RGB for tkinter
        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        
        # Convert to PhotoImage
        image = Image.fromarray(display_frame)
        photo = ImageTk.PhotoImage(image=image)
        
        # Update canvas
        self.canvas.delete("all")
        self.canvas.config(width=display_width, height=display_height)
        self.canvas.create_image(display_width // 2, display_height // 2, image=photo, anchor=tk.CENTER)
        self.canvas.image = photo  # Keep a reference
    
    def apply_zoom(self, frame, center_pos):
        """Apply zoom to frame centered on player position"""
        if not center_pos or self.zoom_level <= 1.0:
            return frame
        
        h, w = frame.shape[:2]
        cx, cy = center_pos
        
        # Calculate crop region (centered on player)
        crop_size_w = int(w / self.zoom_level)
        crop_size_h = int(h / self.zoom_level)
        
        # Calculate crop bounds
        x1 = max(0, cx - crop_size_w // 2)
        y1 = max(0, cy - crop_size_h // 2)
        x2 = min(w, cx + crop_size_w // 2)
        y2 = min(h, cy + crop_size_h // 2)
        
        # Adjust if near edges
        if x2 - x1 < crop_size_w:
            if x1 == 0:
                x2 = crop_size_w
            else:
                x1 = w - crop_size_w
        if y2 - y1 < crop_size_h:
            if y1 == 0:
                y2 = crop_size_h
            else:
                y1 = h - crop_size_h
        
        # Crop and resize
        cropped = frame[y1:y2, x1:x2]
        zoomed = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
        
        return zoomed
    
    def zoom_in(self):
        """Zoom in on player"""
        if self.current_player_pos:
            self.zoom_level = min(4.0, self.zoom_level * 2.0)
            self.zoom_enabled = True
            self.zoom_center = self.current_player_pos
            self.update_zoom_display()
            # Redisplay current frame with zoom
            if hasattr(self, 'current_frame'):
                self.display_frame(self.current_frame, self.current_player_pos)
    
    def zoom_out(self):
        """Zoom out"""
        if self.zoom_level > 1.0:
            self.zoom_level = max(1.0, self.zoom_level / 2.0)
            if self.zoom_level <= 1.0:
                self.zoom_enabled = False
            self.update_zoom_display()
            # Redisplay current frame
            if hasattr(self, 'current_frame'):
                self.display_frame(self.current_frame, self.current_player_pos)
    
    def reset_zoom(self):
        """Reset zoom to 1.0"""
        self.zoom_level = 1.0
        self.zoom_enabled = False
        self.update_zoom_display()
        # Redisplay current frame
        if hasattr(self, 'current_frame'):
            self.display_frame(self.current_frame, self.current_player_pos)
    
    def update_zoom_display(self):
        """Update zoom label"""
        self.zoom_label.config(text=f"{self.zoom_level:.1f}x")
    
    def toggle_frame_selection(self):
        """Toggle frame selection thumbnails"""
        if self.show_frames_var.get():
            self.thumbnails_canvas.config(height=150)
            self.thumbnails_frame.pack(fill=tk.BOTH, expand=True, pady=5)
            self.thumbnails_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.thumbnails_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            self.load_frame_thumbnails()
        else:
            self.thumbnails_canvas.config(height=0)
            self.thumbnails_frame.pack_forget()
            self.thumbnails_canvas.pack_forget()
            self.thumbnails_scrollbar.pack_forget()
    
    def load_frame_thumbnails(self):
        """Load thumbnails for frames where player appears"""
        # Clear existing thumbnails
        for widget in self.thumbnails_container.winfo_children():
            widget.destroy()
        
        if not self.player_frames:
            ttk.Label(self.thumbnails_container, text="No frames found for this player").pack()
            return
        
        # Sample frames (show max 50 thumbnails to avoid performance issues)
        max_thumbnails = 50
        if len(self.player_frames) > max_thumbnails:
            # Sample evenly across all frames
            step = len(self.player_frames) // max_thumbnails
            sample_frames = [self.player_frames[i] for i in range(0, len(self.player_frames), step)][:max_thumbnails]
        else:
            sample_frames = self.player_frames
        
        # Create thumbnails
        thumbnail_size = 120
        for frame_num in sample_frames:
            # Create thumbnail frame
            thumb_frame = ttk.Frame(self.thumbnails_container)
            thumb_frame.pack(side=tk.LEFT, padx=2, pady=2)
            
            # Load frame
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_num))
            ret, frame = self.cap.read()
            
            if ret:
                # Get player position
                player_pos = None
                if self.df is not None and 'player_id' in self.df.columns:
                    if 'frame' in self.df.columns:
                        frame_data = self.df[(self.df['frame'] == frame_num) & (self.df['player_id'] == self.player_id)]
                    else:
                        frame_data = self.df[(self.df.index == frame_num) & (self.df['player_id'] == self.player_id)]
                    
                    if len(frame_data) > 0:
                        row = frame_data.iloc[0]
                        if 'player_x' in row and 'player_y' in row:
                            if pd.notna(row['player_x']) and pd.notna(row['player_y']):
                                player_pos = (int(row['player_x']), int(row['player_y']))
                
                # Draw highlight on thumbnail
                if player_pos:
                    x, y = player_pos
                    cv2.circle(frame, (x, y), 20, (0, 255, 0), 2)
                
                # Resize to thumbnail
                h, w = frame.shape[:2]
                aspect = w / h
                if aspect > 1:
                    thumb_w = thumbnail_size
                    thumb_h = int(thumbnail_size / aspect)
                else:
                    thumb_h = thumbnail_size
                    thumb_w = int(thumbnail_size * aspect)
                
                thumb = cv2.resize(frame, (thumb_w, thumb_h))
                thumb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
                
                # Convert to PhotoImage
                thumb_image = Image.fromarray(thumb)
                thumb_photo = ImageTk.PhotoImage(image=thumb_image)
                
                # Create button with thumbnail
                thumb_btn = tk.Button(thumb_frame, image=thumb_photo, 
                                    command=lambda fn=frame_num: self.jump_to_frame_number(fn),
                                    cursor="hand2", relief=tk.RAISED, bd=2)
                thumb_btn.image = thumb_photo  # Keep reference
                thumb_btn.pack()
                
                # Frame number label
                ttk.Label(thumb_frame, text=f"Frame {frame_num}", font=("Arial", 7)).pack()
        
        # Update scroll region
        self.thumbnails_container.update_idletasks()
        self.thumbnails_canvas.config(scrollregion=self.thumbnails_canvas.bbox("all"))
        
        # Bind canvas resize to update scroll region
        def on_canvas_configure(event):
            self.thumbnails_canvas.config(scrollregion=self.thumbnails_canvas.bbox("all"))
        
        self.thumbnails_canvas.bind('<Configure>', on_canvas_configure)
    
    def jump_to_frame_number(self, frame_num):
        """Jump to a specific frame number (from thumbnail click)"""
        if self.player_frames:
            # Find closest frame in player_frames
            closest_idx = min(range(len(self.player_frames)), 
                             key=lambda i: abs(self.player_frames[i] - frame_num))
            self.current_frame_idx = closest_idx
            self.load_frame(self.player_frames[closest_idx])
        else:
            self.load_frame(frame_num)
    
    def prev_frame(self):
        """Go to previous frame"""
        if not self.player_frames:
            return
        
        self.current_frame_idx = max(0, self.current_frame_idx - 1)
        self.load_frame(self.player_frames[self.current_frame_idx])
    
    def next_frame(self):
        """Go to next frame"""
        if not self.player_frames:
            return
        
        self.current_frame_idx = min(len(self.player_frames) - 1, self.current_frame_idx + 1)
        self.load_frame(self.player_frames[self.current_frame_idx])
    
    def jump_to_frame(self, event=None):
        """Jump to specific frame"""
        try:
            frame_num = int(self.frame_var.get())
            if self.player_frames:
                # Find closest frame in player_frames
                closest_idx = min(range(len(self.player_frames)), 
                                 key=lambda i: abs(self.player_frames[i] - frame_num))
                self.current_frame_idx = closest_idx
                self.load_frame(self.player_frames[closest_idx])
            else:
                self.load_frame(frame_num)
        except ValueError:
            messagebox.showwarning("Warning", "Please enter a valid frame number")


def main():
    root = tk.Tk()
    app = PlayerStatsGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

