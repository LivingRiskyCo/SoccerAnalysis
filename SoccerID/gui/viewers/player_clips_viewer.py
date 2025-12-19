"""
Player Clips Viewer
View and manage highlight clips for players
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import cv2
from PIL import Image, ImageTk
from typing import Optional, List
import json


class PlayerClipsViewer:
    """Viewer for player highlight clips"""
    
    def __init__(self, parent, gallery_manager, clip_manager):
        self.parent = parent
        self.gallery_manager = gallery_manager
        self.clip_manager = clip_manager
        
        self.window = tk.Toplevel(parent)
        self.window.title("Player Highlight Clips")
        self.window.geometry("1200x700")
        self.window.transient(parent)
        
        # Get player names
        self.player_names = []
        if hasattr(self.gallery_manager, 'get_player_names'):
            self.player_names = self.gallery_manager.get_player_names()
        elif hasattr(self.gallery_manager, 'gallery') and self.gallery_manager.gallery:
            self.player_names = list(self.gallery_manager.gallery.keys())
        
        self.current_player = None
        self.current_clips = []
        
        self.create_ui()
        self.update_player_list()
    
    def create_ui(self):
        """Create UI"""
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left: Player list
        left_frame = ttk.LabelFrame(main_frame, text="Players", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)
        left_frame.config(width=200)
        
        # Player listbox
        list_container = ttk.Frame(left_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.player_listbox = tk.Listbox(list_container, yscrollcommand=scrollbar.set,
                                        font=("Arial", 11))
        self.player_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.player_listbox.yview)
        self.player_listbox.bind('<<ListboxSelect>>', self.on_player_select)
        
        # Right: Clips grid
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Player info
        info_frame = ttk.Frame(right_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.player_info_label = ttk.Label(info_frame, text="Select a player to view clips", 
                                          font=("Arial", 12, "bold"))
        self.player_info_label.pack(side=tk.LEFT)
        
        # Clips container with scroll
        clips_container = ttk.Frame(right_frame)
        clips_container.pack(fill=tk.BOTH, expand=True)
        
        # Canvas for scrolling
        self.clips_canvas = tk.Canvas(clips_container, bg="white")
        clips_scrollbar = ttk.Scrollbar(clips_container, orient=tk.VERTICAL, 
                                       command=self.clips_canvas.yview)
        self.clips_scrollable = ttk.Frame(self.clips_canvas)
        
        self.clips_canvas.create_window((0, 0), window=self.clips_scrollable, anchor="nw")
        self.clips_canvas.configure(yscrollcommand=clips_scrollbar.set)
        
        self.clips_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        clips_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.clips_scrollable.bind("<Configure>", 
                                  lambda e: self.clips_canvas.configure(scrollregion=self.clips_canvas.bbox("all")))
        
        # Bind mousewheel
        def on_mousewheel(event):
            self.clips_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.clips_canvas.bind_all("<MouseWheel>", on_mousewheel)
    
    def update_player_list(self):
        """Update player list"""
        self.player_listbox.delete(0, tk.END)
        for player_name in sorted(self.player_names):
            self.player_listbox.insert(tk.END, player_name)
    
    def on_player_select(self, event):
        """Handle player selection"""
        selection = self.player_listbox.curselection()
        if not selection:
            return
        
        player_name = self.player_listbox.get(selection[0])
        self.current_player = player_name
        self.load_player_clips(player_name)
    
    def load_player_clips(self, player_name: str):
        """Load clips for a player"""
        self.current_clips = []
        
        # Get player from gallery
        if hasattr(self.gallery_manager, 'get_player'):
            player = self.gallery_manager.get_player(player_name)
        else:
            player = None
        
        if player and hasattr(player, 'highlight_clips') and player.highlight_clips:
            self.current_clips = player.highlight_clips
        
        # Also get clips from clip manager
        if self.clip_manager:
            manager_clips = self.clip_manager.get_clips_for_player(player_name)
            for clip in manager_clips:
                # Check if already in list
                if not any(c.get('clip_id') == clip.clip_id for c in self.current_clips):
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
                    self.current_clips.append(clip_ref)
        
        self.display_clips()
    
    def display_clips(self):
        """Display clips in grid"""
        # Clear existing clips
        for widget in self.clips_scrollable.winfo_children():
            widget.destroy()
        
        if not self.current_player:
            self.player_info_label.config(text="Select a player to view clips")
            return
        
        self.player_info_label.config(
            text=f"{self.current_player} - {len(self.current_clips)} highlight clip(s)"
        )
        
        if not self.current_clips:
            no_clips_label = ttk.Label(self.clips_scrollable, 
                                      text="No highlight clips for this player",
                                      font=("Arial", 12), foreground="gray")
            no_clips_label.pack(pady=50)
            return
        
        # Create grid of clips (3 columns)
        row = 0
        col = 0
        max_cols = 3
        
        for clip_ref in self.current_clips:
            clip_frame = self.create_clip_card(clip_ref)
            clip_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # Configure grid weights
        for i in range(max_cols):
            self.clips_scrollable.columnconfigure(i, weight=1)
    
    def create_clip_card(self, clip_ref: dict) -> ttk.Frame:
        """Create a clip card widget"""
        card = ttk.LabelFrame(self.clips_scrollable, padding="10")
        card.config(width=300, height=350)
        card.pack_propagate(False)
        
        # Thumbnail
        thumbnail_frame = ttk.Frame(card)
        thumbnail_frame.pack(fill=tk.X, pady=(0, 5))
        
        thumbnail_label = ttk.Label(thumbnail_frame, text="No thumbnail")
        thumbnail_label.pack()
        
        # Load thumbnail if available
        if clip_ref.get('thumbnail_path') and os.path.exists(clip_ref['thumbnail_path']):
            try:
                img = cv2.imread(clip_ref['thumbnail_path'])
                if img is not None:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    img = cv2.resize(img, (280, 157))  # 16:9 aspect ratio
                    photo = ImageTk.PhotoImage(image=Image.fromarray(img))
                    thumbnail_label.config(image=photo, text="")
                    thumbnail_label.image = photo
            except:
                pass
        
        # Clip info
        info_frame = ttk.Frame(card)
        info_frame.pack(fill=tk.X, pady=5)
        
        event_type = clip_ref.get('event_type', 'unknown').upper()
        ttk.Label(info_frame, text=event_type, font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        duration = clip_ref.get('duration', 0)
        if duration:
            ttk.Label(info_frame, text=f"Duration: {duration:.1f}s", 
                     font=("Arial", 9), foreground="gray").pack(anchor=tk.W)
        
        if clip_ref.get('description'):
            desc_text = clip_ref['description'][:50]
            if len(clip_ref['description']) > 50:
                desc_text += "..."
            ttk.Label(info_frame, text=desc_text, 
                     font=("Arial", 8), foreground="gray", wraplength=280).pack(anchor=tk.W, pady=2)
        
        # Buttons
        button_frame = ttk.Frame(card)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="▶ Play", 
                  command=lambda: self.play_clip(clip_ref)).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(button_frame, text="📤 Export", 
                  command=lambda: self.export_clip(clip_ref)).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(button_frame, text="🗑️ Delete", 
                  command=lambda: self.delete_clip(clip_ref)).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        return card
    
    def play_clip(self, clip_ref: dict):
        """Play clip in external player"""
        clip_path = clip_ref.get('clip_path')
        if not clip_path or not os.path.exists(clip_path):
            messagebox.showerror("Error", "Clip file not found")
            return
        
        try:
            # Try to open with default video player
            import subprocess
            import platform
            
            if platform.system() == 'Windows':
                os.startfile(clip_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', clip_path])
            else:  # Linux
                subprocess.run(['xdg-open', clip_path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not play clip: {e}")
    
    def export_clip(self, clip_ref: dict):
        """Export clip to a different location"""
        clip_path = clip_ref.get('clip_path')
        if not clip_path or not os.path.exists(clip_path):
            messagebox.showerror("Error", "Clip file not found")
            return
        
        output_path = filedialog.asksaveasfilename(
            title="Export Clip",
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        
        if output_path:
            try:
                import shutil
                shutil.copy2(clip_path, output_path)
                messagebox.showinfo("Success", f"Clip exported to:\n{output_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not export clip: {e}")
    
    def delete_clip(self, clip_ref: dict):
        """Delete clip"""
        if not messagebox.askyesno("Delete Clip", "Delete this highlight clip?"):
            return
        
        clip_id = clip_ref.get('clip_id')
        
        # Remove from player gallery
        if self.current_player and hasattr(self.gallery_manager, 'get_player'):
            player = self.gallery_manager.get_player(self.current_player)
            if player and hasattr(player, 'highlight_clips') and player.highlight_clips:
                player.highlight_clips = [c for c in player.highlight_clips 
                                         if c.get('clip_id') != clip_id]
                if hasattr(self.gallery_manager, 'save_gallery'):
                    self.gallery_manager.save_gallery()
        
        # Delete from clip manager
        if self.clip_manager and clip_id:
            self.clip_manager.delete_clip(clip_id)
        
        # Reload clips
        self.load_player_clips(self.current_player)

