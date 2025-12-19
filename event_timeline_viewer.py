"""
Event Timeline Viewer
Visual timeline of game events with ability to jump to events, create clips, and tag to players
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from event_tracker import EventTracker
from typing import Optional, Callable
import os
import sys
import threading

# Try to import clip manager
try:
    current_file = __file__
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(current_file)))
    clip_manager_path = os.path.join(parent_dir, 'SoccerID', 'utils', 'clip_manager.py')
    if os.path.exists(clip_manager_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("clip_manager", clip_manager_path)
        clip_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(clip_module)
        ClipManager = clip_module.ClipManager
        CLIP_MANAGER_AVAILABLE = True
    else:
        from SoccerID.utils.clip_manager import ClipManager
        CLIP_MANAGER_AVAILABLE = True
except ImportError:
    try:
        from clip_manager import ClipManager
        CLIP_MANAGER_AVAILABLE = True
    except ImportError:
        CLIP_MANAGER_AVAILABLE = False
        ClipManager = None

# Try to import player gallery
try:
    current_file = __file__
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(current_file)))
    gallery_path = os.path.join(parent_dir, 'SoccerID', 'models', 'player_gallery.py')
    if os.path.exists(gallery_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("player_gallery", gallery_path)
        gallery_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gallery_module)
        PlayerGallery = gallery_module.PlayerGallery
        PLAYER_GALLERY_AVAILABLE = True
    else:
        from SoccerID.models.player_gallery import PlayerGallery
        PLAYER_GALLERY_AVAILABLE = True
except ImportError:
    try:
        from player_gallery import PlayerGallery
        PLAYER_GALLERY_AVAILABLE = True
    except ImportError:
        PLAYER_GALLERY_AVAILABLE = False
        PlayerGallery = None

class EventTimelineViewer:
    def __init__(self, parent, event_tracker: EventTracker, video_path: Optional[str] = None, 
                 fps: float = 30.0, total_frames: int = 0, jump_callback: Optional[Callable] = None,
                 gallery_manager=None, overlay_renderer=None):
        self.parent = parent
        self.event_tracker = event_tracker
        self.video_path = video_path
        self.fps = fps
        self.total_frames = total_frames
        self.jump_callback = jump_callback
        self.gallery_manager = gallery_manager
        self.overlay_renderer = overlay_renderer
        
        # Initialize clip manager
        if CLIP_MANAGER_AVAILABLE:
            self.clip_manager = ClipManager()
        else:
            self.clip_manager = None
        
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
        
        # Clip creation buttons
        if self.clip_manager and self.video_path:
            ttk.Separator(button_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
            ttk.Label(button_frame, text="Clip Actions", font=("Arial", 9, "bold")).pack(pady=2)
            
            ttk.Button(button_frame, text="🎬 Create Clip", 
                      command=self._create_clip, width=20).pack(fill=tk.X, pady=2)
            ttk.Button(button_frame, text="🎬 Create & Tag to Player", 
                      command=self._create_clip_and_tag, width=20).pack(fill=tk.X, pady=2)
            ttk.Button(button_frame, text="📋 View Player Clips", 
                      command=self._view_player_clips, width=20).pack(fill=tk.X, pady=2)
        
        ttk.Separator(button_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
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
    
    # ==================== CLIP CREATION ====================
    
    def _create_clip(self):
        """Create a video clip from selected event"""
        if not self.clip_manager or not self.video_path:
            messagebox.showwarning("Not Available", "Clip creation requires video file")
            return
        
        selection = self.event_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event to create a clip from")
            return
        
        index = selection[0]
        if index < 2:  # Header rows
            return
        
        event_index = index - 2
        sorted_events = sorted(self.event_tracker.events, key=lambda e: e.frame_num)
        
        if 0 <= event_index < len(sorted_events):
            event = sorted_events[event_index]
            self._create_clip_from_event(event)
    
    def _create_clip_from_event(self, event, tag_to_player: bool = False):
        """Create clip from event with dialog"""
        # Dialog for clip settings
        dialog = tk.Toplevel(self.window)
        dialog.title("Create Video Clip")
        dialog.geometry("400x250")
        dialog.transient(self.window)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Create clip from: {event.event_type.upper()}", 
                 font=("Arial", 11, "bold")).pack(pady=10)
        
        # Clip duration settings
        duration_frame = ttk.LabelFrame(dialog, text="Clip Duration", padding=10)
        duration_frame.pack(fill=tk.X, padx=20, pady=5)
        
        ttk.Label(duration_frame, text="Before event (seconds):").pack(anchor=tk.W)
        before_var = tk.DoubleVar(value=2.0)
        before_spin = ttk.Spinbox(duration_frame, from_=0.0, to=10.0, increment=0.5,
                                 textvariable=before_var, width=10, format="%.1f")
        before_spin.pack(fill=tk.X, pady=2)
        
        ttk.Label(duration_frame, text="After event (seconds):").pack(anchor=tk.W, pady=(5, 0))
        after_var = tk.DoubleVar(value=3.0)
        after_spin = ttk.Spinbox(duration_frame, from_=0.0, to=10.0, increment=0.5,
                                textvariable=after_var, width=10, format="%.1f")
        after_spin.pack(fill=tk.X, pady=2)
        
        # Include overlays
        include_overlays_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(duration_frame, text="Include overlays (players, ball, labels)", 
                       variable=include_overlays_var).pack(anchor=tk.W, pady=5)
        
        # Player selection (if tagging)
        player_var = tk.StringVar()
        if tag_to_player and PLAYER_GALLERY_AVAILABLE and self.gallery_manager:
            player_frame = ttk.LabelFrame(dialog, text="Tag to Player", padding=10)
            player_frame.pack(fill=tk.X, padx=20, pady=5)
            
            # Get player names from gallery
            player_names = []
            if hasattr(self.gallery_manager, 'get_player_names'):
                player_names = self.gallery_manager.get_player_names()
            elif hasattr(self.gallery_manager, 'gallery') and self.gallery_manager.gallery:
                player_names = list(self.gallery_manager.gallery.keys())
            
            if player_names:
                ttk.Label(player_frame, text="Player:").pack(anchor=tk.W)
                player_combo = ttk.Combobox(player_frame, textvariable=player_var,
                                           values=player_names, state='readonly', width=25)
                player_combo.pack(fill=tk.X, pady=2)
                
                # Pre-select if event has player name
                if event.player_name and event.player_name in player_names:
                    player_var.set(event.player_name)
            else:
                ttk.Label(player_frame, text="No players in gallery", 
                         foreground="gray").pack()
        
        def create_clip():
            try:
                before = before_var.get()
                after = after_var.get()
                include_overlays = include_overlays_var.get()
                player_name = player_var.get() if tag_to_player else None
                
                if tag_to_player and not player_name:
                    messagebox.showwarning("Player Required", "Please select a player to tag")
                    return
                
                dialog.destroy()
                
                # Create progress window
                progress_window = tk.Toplevel(self.window)
                progress_window.title("Creating Clip")
                progress_window.geometry("400x120")
                progress_window.transient(self.window)
                progress_window.grab_set()
                
                progress_label = ttk.Label(progress_window, text="Creating clip...")
                progress_label.pack(pady=10)
                
                progress_var = tk.DoubleVar()
                progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100, length=350)
                progress_bar.pack(pady=5)
                
                status_label = ttk.Label(progress_window, text="")
                status_label.pack(pady=5)
                
                def progress_callback(progress):
                    progress_var.set(progress)
                    status_label.config(text=f"{progress:.0f}%")
                    progress_window.update()
                
                def create_in_thread():
                    try:
                        clip = self.clip_manager.create_clip_from_event(
                            video_path=self.video_path,
                            event=event,
                            fps=self.fps,
                            clip_duration_before=before,
                            clip_duration_after=after,
                            include_overlays=include_overlays,
                            overlay_renderer=self.overlay_renderer,
                            progress_callback=progress_callback
                        )
                        
                        if clip:
                            # Tag to player if requested
                            if tag_to_player and player_name and PLAYER_GALLERY_AVAILABLE and self.gallery_manager:
                                self._tag_clip_to_player(clip, player_name)
                            
                            progress_window.after(0, progress_window.destroy)
                            self.window.after(0, lambda: messagebox.showinfo(
                                "Clip Created",
                                f"Clip created successfully!\n\n"
                                f"Event: {event.event_type}\n"
                                f"Duration: {clip.duration:.1f}s\n"
                                f"File: {os.path.basename(clip.clip_path)}"
                            ))
                        else:
                            progress_window.after(0, progress_window.destroy)
                            self.window.after(0, lambda: messagebox.showerror(
                                "Error",
                                "Failed to create clip. Check video file and permissions."
                            ))
                    except Exception as e:
                        progress_window.after(0, progress_window.destroy)
                        self.window.after(0, lambda: messagebox.showerror("Error", f"Could not create clip: {e}"))
                
                thread = threading.Thread(target=create_in_thread, daemon=True)
                thread.start()
                
            except Exception as e:
                messagebox.showerror("Error", f"Could not create clip: {e}")
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Create Clip", command=create_clip).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def _create_clip_and_tag(self):
        """Create clip and tag to player"""
        if not self.clip_manager or not self.video_path:
            messagebox.showwarning("Not Available", "Clip creation requires video file")
            return
        
        if not PLAYER_GALLERY_AVAILABLE or not self.gallery_manager:
            messagebox.showwarning("Not Available", "Player gallery not available for tagging")
            return
        
        selection = self.event_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event to create a clip from")
            return
        
        index = selection[0]
        if index < 2:
            return
        
        event_index = index - 2
        sorted_events = sorted(self.event_tracker.events, key=lambda e: e.frame_num)
        
        if 0 <= event_index < len(sorted_events):
            event = sorted_events[event_index]
            self._create_clip_from_event(event, tag_to_player=True)
    
    def _tag_clip_to_player(self, clip, player_name: str):
        """Tag clip to player in gallery"""
        if not PLAYER_GALLERY_AVAILABLE or not self.gallery_manager:
            return
        
        try:
            # Get or create player profile
            if hasattr(self.gallery_manager, 'get_player'):
                player = self.gallery_manager.get_player(player_name)
            else:
                player = None
            
            if not player:
                # Player doesn't exist, create basic entry
                if hasattr(self.gallery_manager, 'add_player'):
                    self.gallery_manager.add_player(player_name)
                    player = self.gallery_manager.get_player(player_name)
            
            if player:
                # Add clip to player's highlight clips
                if not hasattr(player, 'highlight_clips'):
                    player.highlight_clips = []
                
                if player.highlight_clips is None:
                    player.highlight_clips = []
                
                # Add clip reference
                clip_ref = {
                    "clip_id": clip.clip_id,
                    "event_type": clip.event_type,
                    "frame_start": clip.frame_start,
                    "frame_end": clip.frame_end,
                    "video_path": clip.video_path,
                    "clip_path": clip.clip_path,
                    "thumbnail_path": clip.thumbnail_path,
                    "duration": clip.duration,
                    "created_at": clip.created_at,
                    "description": clip.description
                }
                
                player.highlight_clips.append(clip_ref)
                
                # Save gallery
                if hasattr(self.gallery_manager, 'save_gallery'):
                    self.gallery_manager.save_gallery()
        except Exception as e:
            print(f"Warning: Could not tag clip to player: {e}")
    
    def _view_player_clips(self):
        """Open player clips viewer"""
        if not PLAYER_GALLERY_AVAILABLE or not self.gallery_manager:
            messagebox.showwarning("Not Available", "Player gallery not available")
            return
        
        if not self.clip_manager:
            messagebox.showwarning("Not Available", "Clip manager not available")
            return
        
        # Get player names
        player_names = []
        if hasattr(self.gallery_manager, 'get_player_names'):
            player_names = self.gallery_manager.get_player_names()
        elif hasattr(self.gallery_manager, 'gallery') and self.gallery_manager.gallery:
            player_names = list(self.gallery_manager.gallery.keys())
        
        if not player_names:
            messagebox.showinfo("No Players", "No players in gallery")
            return
        
        # Try to import PlayerClipsViewer
        try:
            current_file = __file__
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(current_file)))
            clips_viewer_path = os.path.join(parent_dir, 'SoccerID', 'gui', 'viewers', 'player_clips_viewer.py')
            if os.path.exists(clips_viewer_path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("player_clips_viewer", clips_viewer_path)
                clips_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(clips_module)
                PlayerClipsViewer = clips_module.PlayerClipsViewer
            else:
                from SoccerID.gui.viewers.player_clips_viewer import PlayerClipsViewer
        except ImportError:
            try:
                from player_clips_viewer import PlayerClipsViewer
            except ImportError:
                messagebox.showerror("Error", "Player Clips Viewer module not found")
                return
        
        # Open player clips viewer
        clips_viewer = PlayerClipsViewer(self.window, self.gallery_manager, self.clip_manager)

