"""
Player Gallery Tab Component
Extracted from soccer_analysis_gui.py for better organization
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

# Try new structure imports first, fallback to legacy
try:
    from soccer_analysis.models.player_gallery import PlayerGallery
except ImportError:
    try:
        from models.player_gallery import PlayerGallery
    except ImportError:
        from player_gallery import PlayerGallery


class GalleryTab:
    """Player Gallery Tab Component"""
    
    def __init__(self, parent_gui, parent_frame):
        """
        Initialize gallery tab
        
        Args:
            parent_gui: Reference to main GUI instance (for callbacks)
            parent_frame: Parent frame to create tab in
        """
        self.parent_gui = parent_gui
        self.parent_frame = parent_frame
        self.create_tab()
    
    def create_tab(self):
        """Create the player gallery tab content"""
        try:
            gallery = PlayerGallery()
            stats = gallery.get_stats()
            players = gallery.list_players()
            
            # Main container with scrollbar
            main_container = ttk.Frame(self.parent_frame)
            main_container.pack(fill=tk.BOTH, expand=True)
            
            # Top info section
            info_frame = ttk.Frame(main_container)
            info_frame.pack(fill=tk.X, pady=(0, 15))
            
            # Title and description
            title_frame = ttk.Frame(info_frame)
            title_frame.pack(fill=tk.X)
            
            ttk.Label(title_frame, text="Player Gallery", font=("Arial", 16, "bold")).pack(side=tk.LEFT)
            ttk.Label(title_frame, text="  Cross-Video Player Recognition", 
                     font=("Arial", 10), foreground="gray").pack(side=tk.LEFT, padx=10)
            
            # Statistics box
            stats_frame = ttk.LabelFrame(info_frame, text="Gallery Statistics", padding="10")
            stats_frame.pack(fill=tk.X, pady=(10, 0))
            
            stats_grid = ttk.Frame(stats_frame)
            stats_grid.pack(fill=tk.X)
            
            ttk.Label(stats_grid, text="Total Players:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=5)
            ttk.Label(stats_grid, text=str(stats['total_players']), font=("Arial", 9)).grid(row=0, column=1, sticky=tk.W)
            
            ttk.Label(stats_grid, text="With Re-ID Features:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky=tk.W, padx=5)
            ttk.Label(stats_grid, text=str(stats['players_with_features']), font=("Arial", 9), 
                     foreground="green" if stats['players_with_features'] > 0 else "red").grid(row=1, column=1, sticky=tk.W)
            
            ttk.Label(stats_grid, text="With Reference Frames:", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky=tk.W, padx=5)
            ttk.Label(stats_grid, text=str(stats['players_with_reference_frames']), font=("Arial", 9)).grid(row=2, column=1, sticky=tk.W)
            
            ttk.Label(stats_grid, text="Gallery File:", font=("Arial", 9, "bold")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=(5, 0))
            ttk.Label(stats_grid, text=stats['gallery_path'], font=("Arial", 8), 
                     foreground="blue").grid(row=3, column=1, sticky=tk.W, columnspan=2, pady=(5, 0))
            
            # Action buttons - delegate to parent_gui methods
            button_frame = ttk.Frame(info_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            ttk.Button(button_frame, text="➕ Add New Player", 
                      command=lambda: self._call_parent_method('_add_new_player_to_gallery', self.parent_frame), width=18).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="📸 Tag New Players", 
                      command=lambda: self._call_parent_method('open_player_gallery_seeder'), width=18).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🔧 Backfill Features", 
                      command=lambda: self._call_parent_method('backfill_gallery_features'), width=18).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🔍 Match Unnamed Anchors", 
                      command=lambda: self._call_parent_method('match_unnamed_anchor_frames'), width=28).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🧹 Remove False Matches", 
                      command=lambda: self._call_parent_method('remove_false_matches_from_gallery', self.parent_frame), width=28).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🗑️ Remove Missing Frames", 
                      command=lambda: self._call_parent_method('remove_missing_reference_frames', self.parent_frame), width=28).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🗑️ Delete Selected", 
                      command=lambda: self._call_parent_method('_delete_selected_player_from_gallery', self.parent_frame, listbox, player_list_data), width=18).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🔄 Refresh", 
                      command=lambda: self._call_parent_method('_refresh_gallery_tab', self.parent_frame), width=12).pack(side=tk.LEFT, padx=5)
            
            # Player list
            list_frame = ttk.LabelFrame(main_container, text="Players in Gallery", padding="10")
            list_frame.pack(fill=tk.BOTH, expand=True)
            
            # Create scrollable listbox
            list_container = ttk.Frame(list_frame)
            list_container.pack(fill=tk.BOTH, expand=True)
            
            scrollbar = ttk.Scrollbar(list_container)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            listbox = tk.Listbox(list_container, yscrollcommand=scrollbar.set, 
                                font=("Courier New", 10), height=20)
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            
            # Store player list for selection handling
            player_list_data = []
            
            # Populate list
            if players:
                listbox.insert(tk.END, "✓/✗  Player Name                Jersey  Team      Ref Frames  Confidence")
                listbox.insert(tk.END, "─" * 95)
                
                for player_id, player_name in players:
                    profile = gallery.get_player(player_id)
                    jersey = f"#{profile.jersey_number:>3}" if profile.jersey_number else "    "
                    team = f"{profile.team[:10]:10}" if profile.team else " " * 10
                    has_features = "✓" if profile.features is not None else "✗"
                    
                    # Get reference frame count
                    ref_frames_count = len(profile.reference_frames) if profile.reference_frames else 0
                    ref_frames_display = f"{ref_frames_count:>4}"
                    
                    # Get confidence metrics
                    confidence_metrics = gallery.get_player_confidence_metrics(player_id)
                    overall_conf = confidence_metrics['overall_confidence']
                    
                    # Color-code confidence (high=green, medium=yellow, low=red)
                    if overall_conf >= 0.7:
                        conf_display = f"High ({overall_conf:.2f})"
                        conf_color = "green"
                    elif overall_conf >= 0.4:
                        conf_display = f"Med ({overall_conf:.2f})"
                        conf_color = "orange"
                    else:
                        conf_display = f"Low ({overall_conf:.2f})"
                        conf_color = "red"
                    
                    line = f" {has_features}  {player_name:30} {jersey}  {team}  {ref_frames_display:>11}  {conf_display:15}"
                    listbox.insert(tk.END, line)
                    # Tag with color for confidence
                    if overall_conf >= 0.7:
                        listbox.itemconfig(listbox.size() - 1, {'fg': 'green'})
                    elif overall_conf >= 0.4:
                        listbox.itemconfig(listbox.size() - 1, {'fg': 'orange'})
                    else:
                        listbox.itemconfig(listbox.size() - 1, {'fg': 'red'})
                    
                    player_list_data.append((player_id, player_name))
                
                # Add double-click handler to view player details
                def on_player_select(event):
                    selection = listbox.curselection()
                    if selection and len(selection) > 0:
                        index = selection[0]
                        # Skip header rows (0 and 1)
                        if index > 1 and (index - 2) < len(player_list_data):
                            player_id, player_name = player_list_data[index - 2]
                            self._call_parent_method('_show_player_details', gallery, player_id, self.parent_frame)
                
                listbox.bind('<Double-Button-1>', on_player_select)
                
                # Right-click context menu for delete
                context_menu = tk.Menu(listbox, tearoff=0)
                
                def show_context_menu(event):
                    selection = listbox.curselection()
                    if selection and len(selection) > 0:
                        index = selection[0]
                        if index > 1 and (index - 2) < len(player_list_data):
                            # Clear existing menu items
                            context_menu.delete(0, tk.END)
                            
                            # Store index in closure
                            selected_index = index
                            
                            # Add menu items with proper closures
                            context_menu.add_command(label="View/Edit Details", 
                                                   command=lambda: self._call_parent_method('_show_player_details_from_list', listbox, player_list_data, gallery, self.parent_frame, selected_index))
                            context_menu.add_separator()
                            context_menu.add_command(label="🗑️ Delete Player", 
                                                   command=lambda: self._call_parent_method('_delete_selected_player_from_gallery', self.parent_frame, listbox, player_list_data, selected_index))
                            
                            try:
                                context_menu.tk_popup(event.x_root, event.y_root)
                            finally:
                                context_menu.grab_release()
                
                listbox.bind('<Button-3>', show_context_menu)  # Right-click
            else:
                listbox.insert(tk.END, "")
                listbox.insert(tk.END, "  No players in gallery yet!")
                listbox.insert(tk.END, "")
                listbox.insert(tk.END, "  Click 'Tag New Players' to add players for")
                listbox.insert(tk.END, "  cross-video recognition.")
            
            # Legend
            legend_text = """
Legend:
  ✓ = Player has Re-ID features (will be auto-recognized in videos)
  ✗ = Player without features (manual identification only)
  
Double-click a player to view/edit details
Right-click for context menu (Delete, etc.)
To add players: Click 'Tag New Players' button above
"""
            ttk.Label(list_frame, text=legend_text, justify=tk.LEFT, 
                     foreground="gray", font=("Arial", 8)).pack(pady=(10, 0))
            
        except ImportError as e:
            ttk.Label(self.parent_frame, 
                     text=f"⚠ Player Gallery not available\n\n{str(e)}\n\nMake sure player_gallery.py is in the same folder.",
                     justify=tk.CENTER, font=("Arial", 10)).pack(expand=True)
        except Exception as e:
            ttk.Label(self.parent_frame, 
                     text=f"Error loading Player Gallery:\n\n{str(e)}",
                     justify=tk.CENTER, font=("Arial", 10)).pack(expand=True)
    
    def _call_parent_method(self, method_name, *args, **kwargs):
        """Call a method on the parent GUI instance"""
        if hasattr(self.parent_gui, method_name):
            method = getattr(self.parent_gui, method_name)
            return method(*args, **kwargs)
        else:
            messagebox.showwarning("Method Not Found", 
                                 f"Method '{method_name}' not found in parent GUI.\n"
                                 "This is a migration issue - please report it.")

