"""
Quick Wins Module for Soccer Analysis GUI

Provides enhanced user experience features:
- Progress tracking with percentages
- Undo functionality
- Keyboard shortcuts
- Recent projects management
- Auto-save
- Tooltips
- Drag-and-drop support
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Callable
from datetime import datetime
import threading
import time

# Import logger
try:
    from logger_config import get_logger
    logger = get_logger("gui")
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class ProgressTracker:
    """Track progress with percentage for long-running operations"""
    
    def __init__(self, total: int = 100, label: Optional[ttk.Label] = None, 
                 progress_bar: Optional[ttk.Progressbar] = None):
        self.total = total
        self.current = 0
        self.label = label
        self.progress_bar = progress_bar
        self.start_time = time.time()
        self.last_update_time = time.time()
    
    def update(self, current: int, message: str = ""):
        """Update progress"""
        self.current = current
        percentage = (current / self.total * 100) if self.total > 0 else 0
        
        # Update label if provided
        if self.label:
            if message:
                self.label.config(text=f"{message} ({percentage:.1f}%)")
            else:
                self.label.config(text=f"Progress: {percentage:.1f}%")
        
        # Update progress bar if provided
        if self.progress_bar:
            self.progress_bar['value'] = percentage
        
        # Calculate ETA
        elapsed = time.time() - self.start_time
        if current > 0 and elapsed > 0:
            rate = current / elapsed
            remaining = (self.total - current) / rate if rate > 0 else 0
            eta_str = f"ETA: {int(remaining // 60)}m {int(remaining % 60)}s"
            if self.label and message:
                self.label.config(text=f"{message} ({percentage:.1f}%) - {eta_str}")
    
    def increment(self, amount: int = 1, message: str = ""):
        """Increment progress"""
        self.update(self.current + amount, message)
    
    def finish(self, message: str = "Complete"):
        """Mark progress as complete"""
        self.update(self.total, message)


class UndoManager:
    """Manage undo/redo functionality"""
    
    def __init__(self, max_history: int = 50):
        self.undo_stack: List[Dict] = []
        self.redo_stack: List[Dict] = []
        self.max_history = max_history
        self.enabled = True
    
    def push_action(self, action_type: str, data: Dict, undo_func: Callable, redo_func: Callable):
        """Push an action onto the undo stack"""
        if not self.enabled:
            return
        
        action = {
            'type': action_type,
            'data': data,
            'undo': undo_func,
            'redo': redo_func,
            'timestamp': datetime.now().isoformat()
        }
        
        self.undo_stack.append(action)
        self.redo_stack.clear()  # Clear redo stack when new action is performed
        
        # Limit stack size
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
    
    def undo(self) -> bool:
        """Undo last action"""
        if not self.undo_stack:
            return False
        
        action = self.undo_stack.pop()
        try:
            action['undo'](action['data'])
            self.redo_stack.append(action)
            logger.debug(f"Undid action: {action['type']}")
            return True
        except Exception as e:
            logger.error(f"Error undoing action: {e}")
            return False
    
    def redo(self) -> bool:
        """Redo last undone action"""
        if not self.redo_stack:
            return False
        
        action = self.redo_stack.pop()
        try:
            action['redo'](action['data'])
            self.undo_stack.append(action)
            logger.debug(f"Redid action: {action['type']}")
            return True
        except Exception as e:
            logger.error(f"Error redoing action: {e}")
            return False
    
    def can_undo(self) -> bool:
        """Check if undo is possible"""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is possible"""
        return len(self.redo_stack) > 0
    
    def clear(self):
        """Clear undo/redo history"""
        self.undo_stack.clear()
        self.redo_stack.clear()


class RecentProjectsManager:
    """Manage recent projects list"""
    
    def __init__(self, max_projects: int = 10, config_file: str = "recent_projects.json"):
        self.max_projects = max_projects
        self.config_file = Path(config_file)
        self.projects: List[Dict] = []
        self.load()
    
    def load(self):
        """Load recent projects from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.projects = data.get('projects', [])
                    # Validate that files still exist
                    self.projects = [p for p in self.projects if os.path.exists(p.get('path', ''))]
        except Exception as e:
            logger.warning(f"Could not load recent projects: {e}")
            self.projects = []
    
    def save(self):
        """Save recent projects to file"""
        try:
            data = {'projects': self.projects[:self.max_projects]}
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save recent projects: {e}")
    
    def add_project(self, path: str, name: str = None):
        """Add a project to recent list"""
        if not path or not os.path.exists(path):
            return
        
        # Remove if already exists
        self.projects = [p for p in self.projects if p.get('path') != path]
        
        # Add to front
        project = {
            'path': path,
            'name': name or os.path.basename(path),
            'timestamp': datetime.now().isoformat()
        }
        self.projects.insert(0, project)
        
        # Limit size
        if len(self.projects) > self.max_projects:
            self.projects = self.projects[:self.max_projects]
        
        self.save()
    
    def get_projects(self) -> List[Dict]:
        """Get list of recent projects"""
        return self.projects.copy()
    
    def clear(self):
        """Clear recent projects"""
        self.projects = []
        self.save()


class AutoSaveManager:
    """Manage auto-save functionality"""
    
    def __init__(self, save_func: Callable, interval_seconds: int = 300):
        self.save_func = save_func
        self.interval_seconds = interval_seconds
        self.enabled = True
        self.last_save_time = time.time()
        self.auto_save_thread: Optional[threading.Thread] = None
        self.running = False
    
    def start(self):
        """Start auto-save thread"""
        if self.running:
            return
        
        self.running = True
        self.auto_save_thread = threading.Thread(target=self._auto_save_loop, daemon=True)
        self.auto_save_thread.start()
        logger.info("Auto-save started")
    
    def stop(self):
        """Stop auto-save thread"""
        self.running = False
        if self.auto_save_thread:
            self.auto_save_thread.join(timeout=1.0)
        logger.info("Auto-save stopped")
    
    def _auto_save_loop(self):
        """Auto-save loop"""
        while self.running:
            time.sleep(self.interval_seconds)
            if self.enabled and self.running:
                try:
                    elapsed = time.time() - self.last_save_time
                    if elapsed >= self.interval_seconds:
                        logger.debug("Auto-saving...")
                        self.save_func()
                        self.last_save_time = time.time()
                except Exception as e:
                    logger.error(f"Auto-save error: {e}")
    
    def force_save(self):
        """Force immediate save"""
        try:
            self.save_func()
            self.last_save_time = time.time()
            logger.debug("Forced save completed")
        except Exception as e:
            logger.error(f"Force save error: {e}")
    
    def set_enabled(self, enabled: bool):
        """Enable or disable auto-save"""
        self.enabled = enabled
        if enabled:
            logger.info("Auto-save enabled")
        else:
            logger.info("Auto-save disabled")
    
    def is_enabled(self) -> bool:
        """Check if auto-save is enabled"""
        return self.enabled


class KeyboardShortcuts:
    """Manage keyboard shortcuts"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.shortcuts: Dict[str, Callable] = {}
        self._setup_default_shortcuts()
    
    def _setup_default_shortcuts(self):
        """Setup default keyboard shortcuts"""
        # File operations
        self.register('Ctrl+o', lambda: None, "Open Project")
        self.register('Ctrl+s', lambda: None, "Save Project")
        self.register('Ctrl+Shift+s', lambda: None, "Save Project As")
        self.register('Ctrl+n', lambda: None, "New Project")
        
        # Edit operations
        self.register('Ctrl+z', lambda: None, "Undo")
        self.register('Ctrl+y', lambda: None, "Redo")
        
        # Analysis operations
        self.register('F5', lambda: None, "Start Analysis")
        self.register('F6', lambda: None, "Stop Analysis")
        self.register('F7', lambda: None, "Preview")
        
        # View operations
        self.register('F11', lambda: None, "Toggle Fullscreen")
        self.register('Escape', lambda: None, "Close Dialog")
    
    def register(self, key: str, callback: Callable, description: str = ""):
        """Register a keyboard shortcut"""
        self.shortcuts[key] = {
            'callback': callback,
            'description': description
        }
        
        # Convert key string to tkinter event format
        # Examples: "Ctrl+o" -> "<Control-o>", "F5" -> "<F5>", "Ctrl+Shift+s" -> "<Control-Shift-s>"
        tkinter_key = self._convert_to_tkinter_format(key)
        
        # Bind to root
        self.root.bind(tkinter_key, lambda e: callback())
    
    def _convert_to_tkinter_format(self, key: str) -> str:
        """Convert key string to tkinter event format"""
        # Handle function keys
        if key.startswith('F') and key[1:].isdigit():
            return f'<{key}>'
        
        # Handle Escape
        if key.lower() == 'escape':
            return '<Escape>'
        
        # Parse key combination
        modifiers = []
        key_char = key
        
        if '+' in key:
            parts = key.split('+')
            key_char = parts[-1].lower()
            modifiers = [m.lower() for m in parts[:-1]]
        else:
            key_char = key.lower()
        
        # Build tkinter format
        mod_parts = []
        if 'ctrl' in modifiers:
            mod_parts.append('Control')
        if 'shift' in modifiers:
            mod_parts.append('Shift')
        if 'alt' in modifiers:
            mod_parts.append('Alt')
        
        # Combine modifiers and key
        if mod_parts:
            mod_str = '-'.join(mod_parts)
            return f'<{mod_str}-{key_char}>'
        else:
            return f'<{key_char}>'
    
    def get_shortcuts_list(self) -> List[Dict]:
        """Get list of all shortcuts"""
        return [
            {'key': k, 'description': v['description']}
            for k, v in self.shortcuts.items()
        ]


def create_tooltip(widget, text: str):
    """Create a tooltip for a widget"""
    def on_enter(event):
        tooltip = tk.Toplevel()
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        label = tk.Label(tooltip, text=text, background="#ffffe0", 
                        relief=tk.SOLID, borderwidth=1, font=("TkDefaultFont", 9))
        label.pack()
        widget.tooltip = tooltip
    
    def on_leave(event):
        if hasattr(widget, 'tooltip'):
            widget.tooltip.destroy()
            del widget.tooltip
    
    widget.bind('<Enter>', on_enter)
    widget.bind('<Leave>', on_leave)


def generate_video_thumbnail(video_path: str, output_path: str = None, 
                            frame_number: int = 0) -> Optional[str]:
    """Generate thumbnail for a video file"""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        
        # Seek to frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return None
        
        # Generate output path
        if output_path is None:
            video_path_obj = Path(video_path)
            output_path = str(video_path_obj.parent / f"{video_path_obj.stem}_thumb.jpg")
        
        # Save thumbnail
        cv2.imwrite(output_path, frame)
        return output_path
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        return None


def setup_drag_and_drop(widget, callback: Callable):
    """Setup drag-and-drop for file loading"""
    def on_drop(event):
        files = widget.tk.splitlist(event.data)
        if files:
            callback(files[0])  # Use first file
    
    widget.drop_target_register('DND_Files')
    widget.dnd_bind('<<Drop>>', on_drop)

