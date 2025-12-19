"""
Pass Statistics Viewer GUI
Displays pass accuracy, player-to-player statistics, and pass matrices
"""

import tkinter as tk
from tkinter import ttk
import pandas as pd
from typing import Dict, List, Optional
from event_detector import DetectedEvent

class PassStatisticsViewer:
    def __init__(self, parent, pass_data: Dict, use_imperial: bool = False):
        """
        Initialize pass statistics viewer.
        
        Args:
            parent: Parent window
            pass_data: Dictionary with keys:
                - 'successful_passes': List[DetectedEvent]
                - 'incomplete_passes': List[DetectedEvent]
                - 'player_statistics': Dict
                - 'accuracy_metrics': Dict
            use_imperial: If True, display distances in feet and speeds in mph
        """
        self.parent = parent
        self.pass_data = pass_data
        self.use_imperial = use_imperial
        
        # Unit conversion factors
        self.dist_unit = "ft" if use_imperial else "m"
        self.speed_unit = "mph" if use_imperial else "m/s"
        self.meters_to_feet = 3.281
        self.mps_to_mph = 2.237
        
        # Create window
        self.window = tk.Toplevel(parent)
        title = "Pass Statistics & Accuracy"
        if use_imperial:
            title += " (Imperial Units)"
        self.window.title(title)
        self.window.geometry("1200x800")
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 1: Overview
        self.create_overview_tab()
        
        # Tab 2: Player Statistics
        self.create_player_stats_tab()
        
        # Tab 3: Pass Matrix
        self.create_pass_matrix_tab()
        
        # Tab 4: Accuracy by Distance
        self.create_accuracy_tab()
        
        # Tab 5: Pass Events List
        self.create_events_list_tab()
    
    def create_overview_tab(self):
        """Create overview tab with summary statistics"""
        overview_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(overview_frame, text="Overview")
        
        # Scrollable frame
        canvas = tk.Canvas(overview_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(overview_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Overall Statistics
        stats_frame = ttk.LabelFrame(scrollable_frame, text="Overall Pass Statistics", padding="10")
        stats_frame.pack(fill=tk.X, pady=5)
        
        accuracy_metrics = self.pass_data.get('accuracy_metrics', {})
        
        # Convert distances if using imperial
        avg_successful_dist = accuracy_metrics.get('average_pass_distance_successful', 0.0)
        avg_incomplete_dist = accuracy_metrics.get('average_pass_distance_incomplete', 0.0)
        
        if self.use_imperial:
            avg_successful_dist = avg_successful_dist * self.meters_to_feet
            avg_incomplete_dist = avg_incomplete_dist * self.meters_to_feet
        
        stats_text = f"""
Total Passes: {accuracy_metrics.get('total_passes', 0)}
Successful Passes: {accuracy_metrics.get('successful_passes', 0)}
Incomplete Passes: {accuracy_metrics.get('incomplete_passes', 0)}
Overall Completion Rate: {accuracy_metrics.get('overall_completion_rate', 0.0)*100:.1f}%

Average Pass Distance (Successful): {avg_successful_dist:.2f} {self.dist_unit}
Average Pass Distance (Incomplete): {avg_incomplete_dist:.2f} {self.dist_unit}
"""
        
        ttk.Label(stats_frame, text=stats_text, font=("Courier", 10), justify=tk.LEFT).pack(anchor=tk.W)
        
        # Team Statistics
        team_frame = ttk.LabelFrame(scrollable_frame, text="Team Statistics", padding="10")
        team_frame.pack(fill=tk.X, pady=5)
        
        team_stats = self.pass_data.get('player_statistics', {}).get('team_stats', {})
        if team_stats:
            team_text = ""
            for team_name, stats in sorted(team_stats.items(), key=lambda x: x[1]['total_passes'], reverse=True):
                completion = stats.get('completion_rate', 0.0) * 100
                team_text += f"{team_name}:\n"
                team_text += f"  Total: {stats['total_passes']}, Successful: {stats['successful_passes']}, "
                team_text += f"Incomplete: {stats['incomplete_passes']}\n"
                team_text += f"  Completion Rate: {completion:.1f}%\n\n"
            ttk.Label(team_frame, text=team_text, font=("Courier", 9), justify=tk.LEFT).pack(anchor=tk.W)
        else:
            ttk.Label(team_frame, text="No team statistics available", font=("Arial", 9)).pack(anchor=tk.W)
        
        # Top Passers
        top_passers_frame = ttk.LabelFrame(scrollable_frame, text="Top Passers", padding="10")
        top_passers_frame.pack(fill=tk.X, pady=5)
        
        player_stats = self.pass_data.get('player_statistics', {}).get('player_stats', {})
        if player_stats:
            sorted_players = sorted(
                player_stats.items(),
                key=lambda x: x[1]['total_passes'],
                reverse=True
            )[:10]
            
            passers_text = f"{'Player':<25} {'Total':<8} {'Successful':<12} {'Incomplete':<12} {'Rate':<8}\n"
            passers_text += "-" * 70 + "\n"
            for player_name, stats in sorted_players:
                completion = stats.get('completion_rate', 0.0) * 100
                passers_text += f"{player_name[:24]:<25} {stats['total_passes']:<8} "
                passers_text += f"{stats['successful_passes']:<12} {stats['incomplete_passes']:<12} "
                passers_text += f"{completion:.1f}%\n"
            
            ttk.Label(top_passers_frame, text=passers_text, font=("Courier", 9), justify=tk.LEFT).pack(anchor=tk.W)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_player_stats_tab(self):
        """Create player statistics tab"""
        player_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(player_frame, text="Player Statistics")
        
        # Filter frame
        filter_frame = ttk.Frame(player_frame)
        filter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(filter_frame, text="Filter by Team:").pack(side=tk.LEFT, padx=5)
        self.team_filter_var = tk.StringVar(value="All")
        team_combo = ttk.Combobox(filter_frame, textvariable=self.team_filter_var, state="readonly", width=20)
        
        # Get unique teams
        player_stats = self.pass_data.get('player_statistics', {}).get('player_stats', {})
        teams = set()
        for stats in player_stats.values():
            if stats.get('team'):
                teams.add(stats['team'])
        team_combo['values'] = ["All"] + sorted(teams)
        team_combo.pack(side=tk.LEFT, padx=5)
        team_combo.bind("<<ComboboxSelected>>", lambda e: self.update_player_stats_display())
        
        # Treeview for player stats
        columns = ('Player', 'Team', 'Total Passes', 'Successful', 'Incomplete', 'Completion Rate', 'Received')
        tree = ttk.Treeview(player_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)
        
        tree.column('Player', width=200)
        tree.column('Completion Rate', width=130)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(player_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.player_tree = tree
        self.update_player_stats_display()
    
    def update_player_stats_display(self):
        """Update player statistics display"""
        # Clear existing items
        for item in self.player_tree.get_children():
            self.player_tree.delete(item)
        
        player_stats = self.pass_data.get('player_statistics', {}).get('player_stats', {})
        team_filter = self.team_filter_var.get()
        
        # Sort by total passes
        sorted_players = sorted(
            player_stats.items(),
            key=lambda x: x[1]['total_passes'],
            reverse=True
        )
        
        for player_name, stats in sorted_players:
            # Apply team filter
            if team_filter != "All" and stats.get('team') != team_filter:
                continue
            
            completion = stats.get('completion_rate', 0.0) * 100
            self.player_tree.insert('', 'end', values=(
                player_name,
                stats.get('team', 'Unknown'),
                stats['total_passes'],
                stats['successful_passes'],
                stats['incomplete_passes'],
                f"{completion:.1f}%",
                stats.get('total_received', 0)
            ))
    
    def create_pass_matrix_tab(self):
        """Create pass matrix tab showing player-to-player passes"""
        matrix_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(matrix_frame, text="Pass Matrix")
        
        # Instructions
        info_label = ttk.Label(matrix_frame, 
                              text="Shows number of passes between players (Sender → Receiver)",
                              font=("Arial", 9), foreground="gray")
        info_label.pack(pady=5)
        
        # Treeview for pass matrix
        columns = ('Sender', 'Receiver', 'Count', 'Team')
        tree = ttk.Treeview(matrix_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=200)
        
        tree.column('Count', width=80)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(matrix_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate matrix
        pass_matrix = self.pass_data.get('player_statistics', {}).get('pass_matrix', {})
        player_stats = self.pass_data.get('player_statistics', {}).get('player_stats', {})
        
        # Sort by count
        sorted_matrix = sorted(pass_matrix.items(), key=lambda x: x[1], reverse=True)
        
        for (sender, receiver), count in sorted_matrix:
            sender_team = player_stats.get(sender, {}).get('team', 'Unknown')
            tree.insert('', 'end', values=(sender, receiver, count, sender_team))
    
    def create_accuracy_tab(self):
        """Create accuracy by distance tab"""
        accuracy_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(accuracy_frame, text="Accuracy by Distance")
        
        accuracy_metrics = self.pass_data.get('accuracy_metrics', {})
        distance_ranges = accuracy_metrics.get('distance_ranges', {})
        
        # Create frame for each range
        for range_name in ['short', 'medium', 'long']:
            range_data = distance_ranges.get(range_name, {})
            range_frame = ttk.LabelFrame(accuracy_frame, text=f"{range_name.capitalize()} Passes ({self._get_range_label(range_name)})", padding="10")
            range_frame.pack(fill=tk.X, pady=5)
            
            total = range_data.get('total', 0)
            successful = range_data.get('successful', 0)
            incomplete = range_data.get('incomplete', 0)
            completion = range_data.get('completion_rate', 0.0) * 100
            
            stats_text = f"""
Total: {total}
Successful: {successful}
Incomplete: {incomplete}
Completion Rate: {completion:.1f}%
"""
            ttk.Label(range_frame, text=stats_text, font=("Courier", 10), justify=tk.LEFT).pack(anchor=tk.W)
    
    def _get_range_label(self, range_name: str) -> str:
        """Get label for distance range"""
        if self.use_imperial:
            # Convert meters to feet: 10m = 32.8ft, 20m = 65.6ft
            labels = {
                'short': '0-33ft',
                'medium': '33-66ft',
                'long': '66ft+'
            }
        else:
            labels = {
                'short': '0-10m',
                'medium': '10-20m',
                'long': '20m+'
            }
        return labels.get(range_name, range_name)
    
    def create_events_list_tab(self):
        """Create tab showing all pass events"""
        events_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(events_frame, text="All Pass Events")
        
        # Filter frame
        filter_frame = ttk.Frame(events_frame)
        filter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=5)
        self.event_filter_var = tk.StringVar(value="All")
        event_combo = ttk.Combobox(filter_frame, textvariable=self.event_filter_var, 
                                  values=["All", "Successful", "Incomplete", "Interceptions"],
                                  state="readonly", width=15)
        event_combo.pack(side=tk.LEFT, padx=5)
        event_combo.bind("<<ComboboxSelected>>", lambda e: self.update_events_display())
        
        # Treeview for events
        distance_col_name = f'Distance ({self.dist_unit})'
        columns = ('Frame', 'Time', 'Type', 'Sender', 'Receiver', distance_col_name, 'Confidence')
        tree = ttk.Treeview(events_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            tree.heading(col, text=col)
            if col == 'Sender' or col == 'Receiver':
                tree.column(col, width=150)
            elif col == distance_col_name:
                tree.column(col, width=120)  # Wider for unit label
            else:
                tree.column(col, width=100)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(events_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.events_tree = tree
        self.distance_col_name = distance_col_name  # Store for use in update_events_display
        self.update_events_display()
    
    def update_events_display(self):
        """Update events list display"""
        # Clear existing items
        for item in self.events_tree.get_children():
            self.events_tree.delete(item)
        
        filter_type = self.event_filter_var.get()
        
        # Add successful passes
        if filter_type in ["All", "Successful"]:
            for pass_event in self.pass_data.get('successful_passes', []):
                receiver = pass_event.metadata.get('receiver_name') if pass_event.metadata else "Unknown"
                distance = pass_event.metadata.get('pass_distance_m', 0) if pass_event.metadata else 0
                
                # Convert to imperial if needed
                if self.use_imperial:
                    distance = distance * self.meters_to_feet
                    distance_str = f"{distance:.1f} {self.dist_unit}"
                else:
                    distance_str = f"{distance:.1f} {self.dist_unit}"
                
                self.events_tree.insert('', 'end', values=(
                    pass_event.frame_num,
                    f"{pass_event.timestamp:.2f}s",
                    "Successful",
                    pass_event.player_name or f"Player {pass_event.player_id}",
                    receiver,
                    distance_str,
                    f"{pass_event.confidence:.2f}"
                ))
        
        # Add incomplete passes
        if filter_type in ["All", "Incomplete"]:
            for pass_event in self.pass_data.get('incomplete_passes', []):
                if pass_event.event_type == "incomplete_pass":
                    self.events_tree.insert('', 'end', values=(
                        pass_event.frame_num,
                        f"{pass_event.timestamp:.2f}s",
                        "Incomplete",
                        pass_event.player_name or f"Player {pass_event.player_id}",
                        "Unknown",
                        "-",
                        f"{pass_event.confidence:.2f}"
                    ))
        
        # Add interceptions
        if filter_type in ["All", "Interceptions"]:
            for pass_event in self.pass_data.get('incomplete_passes', []):
                if pass_event.event_type == "interception":
                    intercepted_by = pass_event.metadata.get('intercepted_by_name') if pass_event.metadata else "Unknown"
                    self.events_tree.insert('', 'end', values=(
                        pass_event.frame_num,
                        f"{pass_event.timestamp:.2f}s",
                        "Interception",
                        pass_event.player_name or f"Player {pass_event.player_id}",
                        intercepted_by,
                        "-",
                        f"{pass_event.confidence:.2f}"
                    ))

