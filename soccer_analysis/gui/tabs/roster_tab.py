"""
Team Roster Tab Component
Extracted from soccer_analysis_gui.py for better organization
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

# Try new structure imports first, fallback to legacy
try:
    from team_roster_manager import TeamRosterManager
except ImportError:
    pass  # Will handle in create_tab


class RosterTab:
    """Team Roster Management Tab Component"""
    
    def __init__(self, parent_gui, parent_frame):
        """
        Initialize roster tab
        
        Args:
            parent_gui: Reference to main GUI instance (for callbacks)
            parent_frame: Parent frame to create tab in
        """
        self.parent_gui = parent_gui
        self.parent_frame = parent_frame
        self.create_tab()
    
    def create_tab(self):
        """Create the team roster management tab"""
        try:
            from team_roster_manager import TeamRosterManager
            
            # Initialize roster manager
            roster_manager = TeamRosterManager()
            
            # Main container
            main_container = ttk.Frame(self.parent_frame)
            main_container.pack(fill=tk.BOTH, expand=True)
            
            # Top controls
            controls_frame = ttk.LabelFrame(main_container, text="Roster Management", padding="10")
            controls_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Import/Export buttons
            import_export_frame = ttk.Frame(controls_frame)
            import_export_frame.pack(fill=tk.X, pady=5)
            
            ttk.Button(import_export_frame, text="📥 Import from CSV", 
                      command=lambda: self._call_parent_method('_import_roster_csv', roster_manager, self.parent_frame)).pack(side=tk.LEFT, padx=5)
            ttk.Button(import_export_frame, text="📤 Export to CSV", 
                      command=lambda: self._call_parent_method('_export_roster_csv', roster_manager)).pack(side=tk.LEFT, padx=5)
            ttk.Button(import_export_frame, text="➕ Add Player", 
                      command=lambda: self._call_parent_method('_add_roster_player', roster_manager, self.parent_frame)).pack(side=tk.LEFT, padx=5)
            ttk.Button(import_export_frame, text="🔄 Refresh", 
                      command=lambda: self._call_parent_method('_refresh_roster_tab', self.parent_frame)).pack(side=tk.LEFT, padx=5)
            
            # Video linking
            link_frame = ttk.LabelFrame(controls_frame, text="Link Video to Roster", padding="10")
            link_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(link_frame, text="Select video and players to link:").pack(side=tk.LEFT, padx=5)
            ttk.Button(link_frame, text="🔗 Link Video", 
                      command=lambda: self._call_parent_method('_link_video_to_roster', roster_manager)).pack(side=tk.LEFT, padx=5)
            
            # Roster list
            list_frame = ttk.LabelFrame(main_container, text="Team Roster", padding="10")
            list_frame.pack(fill=tk.BOTH, expand=True)
            
            # Scrollable listbox
            list_container = ttk.Frame(list_frame)
            list_container.pack(fill=tk.BOTH, expand=True)
            
            scrollbar = ttk.Scrollbar(list_container)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            listbox = tk.Listbox(list_container, yscrollcommand=scrollbar.set,
                                font=("Courier New", 10), height=20)
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            
            # Store roster data
            roster_list_data = []
            
            # Populate roster
            self._populate_roster_list(listbox, roster_manager, roster_list_data)
            
            # Right-click context menu
            context_menu = tk.Menu(listbox, tearoff=0)
            
            def show_context_menu(event):
                selection = listbox.curselection()
                if selection and len(selection) > 0:
                    index = selection[0]
                    if index > 1 and (index - 2) < len(roster_list_data):
                        context_menu.delete(0, tk.END)
                        selected_index = index
                        player_name = roster_list_data[selected_index - 2]
                        context_menu.add_command(label="✏️ Edit Player", 
                                               command=lambda: self._call_parent_method('_edit_roster_player', roster_manager, player_name, self.parent_frame))
                        context_menu.add_separator()
                        context_menu.add_command(label="🗑️ Delete Player", 
                                               command=lambda: self._call_parent_method('_delete_roster_player', roster_manager, player_name, self.parent_frame))
                        try:
                            context_menu.tk_popup(event.x_root, event.y_root)
                        finally:
                            context_menu.grab_release()
            
            listbox.bind('<Button-3>', show_context_menu)
            
            # Store references for refresh
            self.parent_frame._roster_manager = roster_manager
            self.parent_frame._roster_listbox = listbox
            self.parent_frame._roster_list_data = roster_list_data
            
        except ImportError as e:
            ttk.Label(self.parent_frame, 
                     text=f"⚠ Team Roster Manager not available\n\n{str(e)}\n\nMake sure team_roster_manager.py is in the same folder.",
                     justify=tk.CENTER, font=("Arial", 10)).pack(expand=True)
        except Exception as e:
            ttk.Label(self.parent_frame, 
                     text=f"Error loading Team Roster:\n\n{str(e)}",
                     justify=tk.CENTER, font=("Arial", 10)).pack(expand=True)
    
    def _populate_roster_list(self, listbox, roster_manager, roster_list_data):
        """Populate the roster listbox"""
        listbox.delete(0, tk.END)
        roster_list_data.clear()
        
        roster = roster_manager.roster
        if not roster or (len(roster) == 1 and 'videos' in roster):
            listbox.insert(tk.END, "")
            listbox.insert(tk.END, "  No players in roster yet!")
            listbox.insert(tk.END, "")
            listbox.insert(tk.END, "  Click 'Add Player' or 'Import from CSV' to add players.")
            return
        
        # Header
        listbox.insert(tk.END, "Name                    Jersey    Team            Position    Active")
        listbox.insert(tk.END, "─" * 80)
        
        # Sort players by name
        players = [(name, data) for name, data in roster.items() if name != 'videos']
        players.sort(key=lambda x: x[0])
        
        for player_name, player_data in players:
            jersey = player_data.get('jersey_number', '') or ''
            team = (player_data.get('team', '') or '')[:15]
            position = (player_data.get('position', '') or '')[:10]
            active = "Yes" if player_data.get('active', True) else "No"
            
            line = f"{player_name:23} {jersey:8} {team:15} {position:10} {active:6}"
            listbox.insert(tk.END, line)
            roster_list_data.append(player_name)
    
    def _call_parent_method(self, method_name, *args, **kwargs):
        """Call a method on the parent GUI instance"""
        if hasattr(self.parent_gui, method_name):
            method = getattr(self.parent_gui, method_name)
            return method(*args, **kwargs)
        else:
            messagebox.showwarning("Method Not Found", 
                                 f"Method '{method_name}' not found in parent GUI.\n"
                                 "This is a migration issue - please report it.")

