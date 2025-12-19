"""
Event Timeline Viewer
Visual timeline of game events with ability to jump to events
"""

import tkinter as tk
from tkinter import ttk, messagebox
from event_tracker import EventTracker
from typing import Optional
import os

class EventTimelineViewer:
    def __init__(self, parent, event_tracker: EventTracker, video_path: Optional[str] = None, fps: float = 30.0):
        self.parent = parent
        self.event_tracker = event_tracker
        self.video_path = video_path
        self.fps = fps
        self.jump_callback = None  # Callback function to jump to frame
        
        self.window = tk.Toplevel(parent)
        self.window.title("Event Timeline")
        self.window.geometry("1000x600")
        self.window.transient(parent)
        
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(title_frame, text="Event Timeline", font=("Arial", 14, "bold")).pack(side=tk.LEFT)
        ttk.Label(title_frame, text=f"  {len(event_tracker.events)} events", 
                 font=("Arial", 10), foreground="gray").pack(side=tk.LEFT, padx=10)
        
        # Timeline canvas
        timeline_frame = ttk.LabelFrame(main_frame, text="Timeline", padding="10")
        timeline_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.timeline_canvas = tk.Canvas(timeline_frame, bg="white", height=150)
        self.timeline_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Event list
        list_frame = ttk.LabelFrame(main_frame, text="Events", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 10))
        
        # Scrollable listbox
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.event_listbox = tk.Listbox(list_container, yscrollcommand=scrollbar.set,
                                        font=("Courier New", 10))
        self.event_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.event_listbox.yview)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, side=tk.RIGHT, padx=(10, 0))
        
        ttk.Button(button_frame, text="Jump to Event", 
                  command=self._jump_to_event, width=20).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Export Events", 
                  command=self._export_events, width=20).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Delete Event", 
                  command=self._delete_event, width=20).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Refresh", 
                  command=self._refresh, width=20).pack(fill=tk.X, pady=2)
        
        # Bind double-click to jump
        self.event_listbox.bind('<Double-Button-1>', lambda e: self._jump_to_event())
        
        self._draw_timeline()
        self._populate_list()
    
    def set_jump_callback(self, callback):
        """Set callback function to jump to a frame"""
        self.jump_callback = callback
    
    def _draw_timeline(self):
        """Draw timeline visualization"""
        self.timeline_canvas.delete("all")
        
        if not self.event_tracker.events:
            self.timeline_canvas.create_text(500, 75, text="No events recorded", 
                                            font=("Arial", 12), fill="gray")
            return
        
        # Get frame range
        frames = [e.frame_num for e in self.event_tracker.events]
        min_frame = min(frames)
        max_frame = max(frames)
        frame_range = max_frame - min_frame if max_frame > min_frame else 1
        
        canvas_width = self.timeline_canvas.winfo_width()
        canvas_height = self.timeline_canvas.winfo_height()
        
        if canvas_width < 10:  # Not yet rendered
            self.timeline_canvas.update_idletasks()
            canvas_width = self.timeline_canvas.winfo_width()
            canvas_height = self.timeline_canvas.winfo_height()
        
        # Draw timeline line
        margin = 50
        timeline_y = canvas_height // 2
        timeline_start = margin
        timeline_end = canvas_width - margin
        
        self.timeline_canvas.create_line(timeline_start, timeline_y, 
                                        timeline_end, timeline_y, 
                                        fill="black", width=2)
        
        # Event type colors
        event_colors = {
            "goal": "green",
            "shot": "red",
            "pass": "blue",
            "foul": "orange",
            "save": "cyan",
            "tackle": "purple",
            "corner": "yellow",
            "free_kick": "magenta",
            "substitution": "gray",
            "custom": "brown"
        }
        
        # Draw events
        for i, event in enumerate(self.event_tracker.events):
            # Calculate position on timeline
            x_pos = timeline_start + ((event.frame_num - min_frame) / frame_range) * (timeline_end - timeline_start)
            
            # Get color for event type
            color = event_colors.get(event.event_type, "black")
            
            # Draw event marker
            self.timeline_canvas.create_oval(x_pos - 5, timeline_y - 5,
                                            x_pos + 5, timeline_y + 5,
                                            fill=color, outline="black", width=1)
            
            # Draw label (every 5th event or important events)
            if i % 5 == 0 or event.event_type in ["goal", "shot", "save"]:
                label_y = timeline_y - 20 if i % 2 == 0 else timeline_y + 20
                self.timeline_canvas.create_text(x_pos, label_y, 
                                                text=event.event_type.upper()[:3],
                                                font=("Arial", 7), fill=color)
        
        # Draw frame markers
        for frame_marker in range(int(min_frame), int(max_frame) + 1, max(1, int(frame_range / 10))):
            x_pos = timeline_start + ((frame_marker - min_frame) / frame_range) * (timeline_end - timeline_start)
            self.timeline_canvas.create_line(x_pos, timeline_y - 5,
                                            x_pos, timeline_y + 5,
                                            fill="gray", width=1)
            # Frame number label
            if frame_range > 100:  # Only show labels if range is large enough
                self.timeline_canvas.create_text(x_pos, canvas_height - 15,
                                                text=str(frame_marker),
                                                font=("Arial", 7), fill="gray")
    
    def _populate_list(self):
        """Populate event list"""
        self.event_listbox.delete(0, tk.END)
        
        if not self.event_tracker.events:
            self.event_listbox.insert(tk.END, "(No events recorded)")
            return
        
        # Header
        self.event_listbox.insert(tk.END, "Type      Time      Frame    Player")
        self.event_listbox.insert(tk.END, "-" * 60)
        
        # Sort events by frame number
        sorted_events = sorted(self.event_tracker.events, key=lambda e: e.frame_num)
        
        for event in sorted_events:
            time_str = f"{event.timestamp:6.1f}s"
            frame_str = f"{event.frame_num:6d}"
            player_str = event.player_name or (f"ID:{event.player_id}" if event.player_id else "N/A")
            
            text = f"{event.event_type:8s} {time_str} {frame_str} {player_str:20s}"
            if event.description:
                text += f" - {event.description[:30]}"
            
            self.event_listbox.insert(tk.END, text)
    
    def _jump_to_event(self):
        """Jump to selected event"""
        selection = self.event_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event to jump to")
            return
        
        # Skip header rows
        index = selection[0]
        if index < 2:  # Header rows
            return
        
        # Get event (accounting for header rows)
        event_index = index - 2
        sorted_events = sorted(self.event_tracker.events, key=lambda e: e.frame_num)
        
        if 0 <= event_index < len(sorted_events):
            event = sorted_events[event_index]
            if self.jump_callback:
                self.jump_callback(event.frame_num)
            else:
                messagebox.showinfo("Event", 
                                  f"Event: {event.event_type}\n"
                                  f"Frame: {event.frame_num}\n"
                                  f"Time: {event.timestamp:.2f}s")
    
    def _export_events(self):
        """Export events to file"""
        if not self.event_tracker.events:
            messagebox.showwarning("No Events", "No events to export")
            return
        
        output_dir = os.path.dirname(self.video_path) if self.video_path else "."
        json_path, csv_path = self.event_tracker.save_events(output_dir)
        
        messagebox.showinfo("Export Complete", 
                          f"Events exported to:\n{os.path.basename(json_path)}\n{os.path.basename(csv_path)}")
    
    def _delete_event(self):
        """Delete selected event"""
        selection = self.event_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event to delete")
            return
        
        index = selection[0]
        if index < 2:  # Header rows
            return
        
        # Get event index
        event_index = index - 2
        sorted_events = sorted(self.event_tracker.events, key=lambda e: e.frame_num)
        
        if 0 <= event_index < len(sorted_events):
            event = sorted_events[event_index]
            if messagebox.askyesno("Delete Event", 
                                  f"Delete event: {event.event_type} at frame {event.frame_num}?"):
                # Find and delete from original list
                for i, e in enumerate(self.event_tracker.events):
                    if e.frame_num == event.frame_num and e.event_type == event.event_type:
                        self.event_tracker.delete_event(i)
                        break
                self._refresh()
    
    def _refresh(self):
        """Refresh timeline and list"""
        self._draw_timeline()
        self._populate_list()

