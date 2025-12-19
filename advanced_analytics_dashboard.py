"""
Advanced Analytics Dashboard

Provides comprehensive analytics visualization with:
- Interactive charts and graphs
- Heat maps for player positions
- Play pattern analysis
- Custom report generation
- Real-time statistics
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import csv
try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("⚠ Pandas not available - some features will be disabled")

# Try to import matplotlib for charts
try:
    import matplotlib
    matplotlib.use('TkAgg')  # Use TkAgg backend for tkinter integration
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠ Matplotlib not available - charts will be disabled")

# Import logger
try:
    from logger_config import get_logger
    logger = get_logger("analytics")
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class AdvancedAnalyticsDashboard:
    """Advanced analytics dashboard with interactive visualizations"""
    
    def __init__(self, parent, csv_path: Optional[str] = None):
        self.parent = parent
        self.csv_path = csv_path
        if PANDAS_AVAILABLE:
            self.data: Optional[pd.DataFrame] = None
        else:
            self.data = None
        self.player_stats: Dict[str, Dict] = {}
        
        # Create window
        self.window = tk.Toplevel(parent)
        self.window.title("Advanced Analytics Dashboard")
        self.window.geometry("1200x800")
        self.window.transient(parent)
        
        # Load data if CSV path provided
        if csv_path and os.path.exists(csv_path):
            self.load_csv_data(csv_path)
        
        self.create_widgets()
    
    def load_csv_data(self, csv_path: str):
        """Load tracking data from CSV"""
        try:
            self.data = pd.read_csv(csv_path, low_memory=False)
            logger.info(f"Loaded {len(self.data)} rows from {csv_path}")
            self._calculate_player_stats()
        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            messagebox.showerror("Error", f"Could not load CSV file:\n{e}")
    
    def _calculate_player_stats(self):
        """Calculate statistics for each player"""
        if self.data is None:
            return
        
        self.player_stats = {}
        
        # Group by player
        if 'player_name' in self.data.columns:
            for player_name, group in self.data.groupby('player_name'):
                if pd.isna(player_name) or player_name == '':
                    continue
                
                stats = {
                    'total_frames': len(group),
                    'avg_speed': group['speed'].mean() if 'speed' in group.columns else 0,
                    'max_speed': group['speed'].max() if 'speed' in group.columns else 0,
                    'total_distance': group['distance'].sum() if 'distance' in group.columns else 0,
                    'avg_x': group['x'].mean() if 'x' in group.columns else 0,
                    'avg_y': group['y'].mean() if 'y' in group.columns else 0,
                    'field_time': len(group) / 30.0 if len(group) > 0 else 0,  # Assuming 30fps
                }
                
                self.player_stats[str(player_name)] = stats
    
    def create_widgets(self):
        """Create dashboard widgets"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 1: Overview
        overview_tab = ttk.Frame(notebook)
        notebook.add(overview_tab, text="📊 Overview")
        self._create_overview_tab(overview_tab)
        
        # Tab 2: Player Statistics
        players_tab = ttk.Frame(notebook)
        notebook.add(players_tab, text="👤 Players")
        self._create_players_tab(players_tab)
        
        # Tab 3: Heat Maps
        heatmap_tab = ttk.Frame(notebook)
        notebook.add(heatmap_tab, text="🔥 Heat Maps")
        self._create_heatmap_tab(heatmap_tab)
        
        # Tab 4: Charts
        if MATPLOTLIB_AVAILABLE:
            charts_tab = ttk.Frame(notebook)
            notebook.add(charts_tab, text="📈 Charts")
            self._create_charts_tab(charts_tab)
        
        # Tab 5: Reports
        reports_tab = ttk.Frame(notebook)
        notebook.add(reports_tab, text="📄 Reports")
        self._create_reports_tab(reports_tab)
    
    def _create_overview_tab(self, parent):
        """Create overview tab"""
        # Summary statistics frame
        summary_frame = ttk.LabelFrame(parent, text="Summary Statistics", padding=10)
        summary_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create scrollable text area
        text_widget = scrolledtext.ScrolledText(summary_frame, wrap=tk.WORD, height=20)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Generate summary
        summary = self._generate_summary()
        text_widget.insert('1.0', summary)
        text_widget.config(state=tk.DISABLED)
    
    def _create_players_tab(self, parent):
        """Create players statistics tab"""
        # Player list frame
        list_frame = ttk.Frame(parent)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(list_frame, text="Players", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        # Player listbox
        player_listbox = tk.Listbox(list_frame, height=15)
        player_listbox.pack(fill=tk.BOTH, expand=True)
        
        # Populate list
        for player_name in sorted(self.player_stats.keys()):
            player_listbox.insert(tk.END, player_name)
        
        # Details frame
        details_frame = ttk.LabelFrame(parent, text="Player Details", padding=10)
        details_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.player_details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, height=20)
        self.player_details_text.pack(fill=tk.BOTH, expand=True)
        
        # Bind selection
        def on_player_select(event):
            selection = player_listbox.curselection()
            if selection:
                player_name = player_listbox.get(selection[0])
                self._show_player_details(player_name)
        
        player_listbox.bind('<<ListboxSelect>>', on_player_select)
    
    def _create_heatmap_tab(self, parent):
        """Create heat map tab"""
        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(parent, text="Matplotlib not available - heat maps disabled").pack(pady=20)
            return
        
        # Control frame
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(control_frame, text="Player:").pack(side=tk.LEFT, padx=5)
        player_combo = ttk.Combobox(control_frame, values=list(self.player_stats.keys()), state="readonly")
        player_combo.pack(side=tk.LEFT, padx=5)
        player_combo.set(list(self.player_stats.keys())[0] if self.player_stats else "")
        
        ttk.Button(control_frame, text="Generate Heat Map", 
                  command=lambda: self._generate_heatmap(parent, player_combo.get())).pack(side=tk.LEFT, padx=5)
        
        # Canvas for heat map
        self.heatmap_canvas_frame = ttk.Frame(parent)
        self.heatmap_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def _create_charts_tab(self, parent):
        """Create charts tab"""
        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(parent, text="Matplotlib not available - charts disabled").pack(pady=20)
            return
        
        # Control frame
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        chart_type = tk.StringVar(value="speed")
        ttk.Radiobutton(control_frame, text="Speed Over Time", variable=chart_type, 
                       value="speed").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(control_frame, text="Distance Covered", variable=chart_type, 
                       value="distance").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(control_frame, text="Position Distribution", variable=chart_type, 
                       value="position").pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Generate Chart", 
                  command=lambda: self._generate_chart(parent, chart_type.get())).pack(side=tk.LEFT, padx=5)
        
        # Canvas for chart
        self.chart_canvas_frame = ttk.Frame(parent)
        self.chart_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def _create_reports_tab(self, parent):
        """Create reports tab"""
        # Report options
        options_frame = ttk.LabelFrame(parent, text="Report Options", padding=10)
        options_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.include_charts = tk.BooleanVar(value=True)
        self.include_heatmaps = tk.BooleanVar(value=True)
        self.include_statistics = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(options_frame, text="Include Charts", 
                       variable=self.include_charts).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Include Heat Maps", 
                       variable=self.include_heatmaps).pack(anchor=tk.W)
        ttk.Checkbutton(options_frame, text="Include Statistics", 
                       variable=self.include_statistics).pack(anchor=tk.W)
        
        # Generate button
        ttk.Button(options_frame, text="Generate Report", 
                  command=self._generate_report).pack(pady=10)
    
    def _generate_summary(self) -> str:
        """Generate summary statistics"""
        if self.data is None:
            return "No data loaded. Please load a CSV file."
        
        summary = "=" * 60 + "\n"
        summary += "ANALYTICS SUMMARY\n"
        summary += "=" * 60 + "\n\n"
        
        summary += f"Total Frames: {len(self.data)}\n"
        summary += f"Unique Players: {len(self.player_stats)}\n"
        summary += f"Data Source: {os.path.basename(self.csv_path) if self.csv_path else 'Unknown'}\n\n"
        
        if self.player_stats:
            summary += "Top Players by Field Time:\n"
            sorted_players = sorted(self.player_stats.items(), 
                                  key=lambda x: x[1]['field_time'], reverse=True)
            for i, (name, stats) in enumerate(sorted_players[:5], 1):
                summary += f"  {i}. {name}: {stats['field_time']:.1f}s\n"
        
        return summary
    
    def _show_player_details(self, player_name: str):
        """Show details for a player"""
        if player_name not in self.player_stats:
            return
        
        stats = self.player_stats[player_name]
        self.player_details_text.config(state=tk.NORMAL)
        self.player_details_text.delete('1.0', tk.END)
        
        details = f"Player: {player_name}\n"
        details += "=" * 40 + "\n\n"
        details += f"Total Frames: {stats['total_frames']}\n"
        details += f"Field Time: {stats['field_time']:.1f} seconds\n"
        details += f"Average Speed: {stats['avg_speed']:.2f} units/frame\n"
        details += f"Max Speed: {stats['max_speed']:.2f} units/frame\n"
        details += f"Total Distance: {stats['total_distance']:.2f} units\n"
        details += f"Average Position: ({stats['avg_x']:.1f}, {stats['avg_y']:.1f})\n"
        
        self.player_details_text.insert('1.0', details)
        self.player_details_text.config(state=tk.DISABLED)
    
    def _generate_heatmap(self, parent, player_name: str):
        """Generate heat map for a player"""
        if not MATPLOTLIB_AVAILABLE or self.data is None:
            return
        
        if player_name not in self.player_stats:
            messagebox.showwarning("Warning", f"No data for player: {player_name}")
            return
        
        # Clear previous heat map
        for widget in self.heatmap_canvas_frame.winfo_children():
            widget.destroy()
        
        # Filter data for player
        player_data = self.data[self.data['player_name'] == player_name]
        
        if len(player_data) == 0:
            messagebox.showwarning("Warning", f"No position data for {player_name}")
            return
        
        # Create figure
        fig = Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)
        
        # Create heat map
        if 'x' in player_data.columns and 'y' in player_data.columns:
            x = player_data['x'].values
            y = player_data['y'].values
            
            # Create 2D histogram
            heatmap, xedges, yedges = np.histogram2d(x, y, bins=50)
            extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
            
            ax.imshow(heatmap.T, extent=extent, origin='lower', cmap='hot', aspect='auto')
            ax.set_xlabel('X Position')
            ax.set_ylabel('Y Position')
            ax.set_title(f'Position Heat Map: {player_name}')
        
        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, self.heatmap_canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Add toolbar
        toolbar = NavigationToolbar2Tk(canvas, self.heatmap_canvas_frame)
        toolbar.update()
    
    def _generate_chart(self, parent, chart_type: str):
        """Generate chart"""
        if not MATPLOTLIB_AVAILABLE or not PANDAS_AVAILABLE or self.data is None:
            return
        
        # Clear previous chart
        for widget in self.chart_canvas_frame.winfo_children():
            widget.destroy()
        
        # Create figure
        fig = Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)
        
        if chart_type == "speed" and 'speed' in self.data.columns:
            ax.plot(self.data['frame_num'] if 'frame_num' in self.data.columns else range(len(self.data)), 
                   self.data['speed'])
            ax.set_xlabel('Frame')
            ax.set_ylabel('Speed')
            ax.set_title('Speed Over Time')
        elif chart_type == "distance" and 'distance' in self.data.columns:
            ax.plot(self.data['frame_num'] if 'frame_num' in self.data.columns else range(len(self.data)), 
                   self.data['distance'].cumsum())
            ax.set_xlabel('Frame')
            ax.set_ylabel('Cumulative Distance')
            ax.set_title('Distance Covered Over Time')
        elif chart_type == "position":
            if 'x' in self.data.columns and 'y' in self.data.columns:
                ax.scatter(self.data['x'], self.data['y'], alpha=0.5, s=1)
                ax.set_xlabel('X Position')
                ax.set_ylabel('Y Position')
                ax.set_title('Position Distribution')
        
        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, self.chart_canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Add toolbar
        toolbar = NavigationToolbar2Tk(canvas, self.chart_canvas_frame)
        toolbar.update()
    
    def _generate_report(self):
        """Generate comprehensive report"""
        output_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        
        if not output_path:
            return
        
        try:
            # Generate HTML report
            html = self._generate_html_report()
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            
            messagebox.showinfo("Success", f"Report generated:\n{output_path}")
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            messagebox.showerror("Error", f"Could not generate report:\n{e}")
    
    def _generate_html_report(self) -> str:
        """Generate HTML report"""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>Analytics Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>Analytics Report</h1>
    <p>Generated: {}</p>
    <h2>Summary</h2>
    <p>{}</p>
    <h2>Player Statistics</h2>
    <table>
        <tr>
            <th>Player</th>
            <th>Field Time (s)</th>
            <th>Avg Speed</th>
            <th>Max Speed</th>
            <th>Total Distance</th>
        </tr>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
           self._generate_summary().replace('\n', '<br>'))
        
        for player_name, stats in sorted(self.player_stats.items()):
            html += f"""
        <tr>
            <td>{player_name}</td>
            <td>{stats['field_time']:.1f}</td>
            <td>{stats['avg_speed']:.2f}</td>
            <td>{stats['max_speed']:.2f}</td>
            <td>{stats['total_distance']:.2f}</td>
        </tr>
"""
        
        html += """
    </table>
</body>
</html>
"""
        return html


def open_analytics_dashboard(parent, csv_path: Optional[str] = None):
    """Open analytics dashboard window"""
    try:
        dashboard = AdvancedAnalyticsDashboard(parent, csv_path)
        return dashboard
    except Exception as e:
        logger.error(f"Error opening analytics dashboard: {e}")
        messagebox.showerror("Error", f"Could not open analytics dashboard:\n{e}")
        return None

