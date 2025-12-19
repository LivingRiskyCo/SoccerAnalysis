"""
Toast Notification System
Provides non-intrusive notifications for completed actions
"""

import tkinter as tk
from typing import Optional, Literal
import threading
import time


class ToastNotification:
    """
    Toast notification widget
    
    Displays temporary notifications that fade in/out
    """
    
    def __init__(self, parent, message: str, duration: int = 3000,
                 notification_type: Literal["success", "info", "warning", "error"] = "info"):
        """
        Initialize toast notification
        
        Args:
            parent: Parent widget
            message: Notification message
            duration: Display duration in milliseconds
            notification_type: Type of notification (affects color)
        """
        self.parent = parent
        self.message = message
        self.duration = duration
        self.notification_type = notification_type
        
        # Colors for different notification types
        self.colors = {
            "success": {"bg": "#4CAF50", "fg": "white", "icon": "✓"},
            "info": {"bg": "#2196F3", "fg": "white", "icon": "ℹ"},
            "warning": {"bg": "#FF9800", "fg": "white", "icon": "⚠"},
            "error": {"bg": "#F44336", "fg": "white", "icon": "✕"}
        }
        
        self.toast_window = None
        self.fade_thread = None
        self._create_toast()
    
    def _create_toast(self):
        """Create toast notification window"""
        # Create toplevel window
        self.toast_window = tk.Toplevel(self.parent)
        self.toast_window.overrideredirect(True)  # Remove window decorations
        self.toast_window.attributes('-topmost', True)
        self.toast_window.attributes('-alpha', 0.0)  # Start transparent
        
        # Get parent window position and size
        self.parent.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        # Position toast at bottom-right of parent
        toast_width = 350
        toast_height = 80
        x = parent_x + parent_width - toast_width - 20
        y = parent_y + parent_height - toast_height - 80
        
        self.toast_window.geometry(f"{toast_width}x{toast_height}+{x}+{y}")
        
        # Get colors
        colors = self.colors.get(self.notification_type, self.colors["info"])
        
        # Create frame with rounded appearance
        frame = tk.Frame(self.toast_window, bg=colors["bg"], relief=tk.FLAT, bd=0)
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Icon and message
        content_frame = tk.Frame(frame, bg=colors["bg"])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Icon
        icon_label = tk.Label(content_frame, text=colors["icon"], 
                             font=("Arial", 16, "bold"), bg=colors["bg"], fg=colors["fg"])
        icon_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Message
        message_label = tk.Label(content_frame, text=self.message, 
                                font=("Arial", 10), bg=colors["bg"], fg=colors["fg"],
                                wraplength=250, justify=tk.LEFT)
        message_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Close button
        close_btn = tk.Label(content_frame, text="×", font=("Arial", 18, "bold"),
                           bg=colors["bg"], fg=colors["fg"], cursor="hand2")
        close_btn.pack(side=tk.RIGHT, padx=(5, 0))
        close_btn.bind("<Button-1>", lambda e: self.dismiss())
        
        # Start fade-in animation
        self._fade_in()
        
        # Schedule auto-dismiss
        self.toast_window.after(self.duration, self._fade_out)
    
    def _fade_in(self):
        """Fade in animation"""
        def fade():
            for alpha in range(0, 101, 10):
                if self.toast_window and self.toast_window.winfo_exists():
                    self.toast_window.attributes('-alpha', alpha / 100.0)
                    time.sleep(0.02)
                else:
                    break
        
        self.fade_thread = threading.Thread(target=fade, daemon=True)
        self.fade_thread.start()
    
    def _fade_out(self):
        """Fade out animation"""
        def fade():
            if not self.toast_window or not self.toast_window.winfo_exists():
                return
            
            current_alpha = self.toast_window.attributes('-alpha')
            for alpha in range(int(current_alpha * 100), -1, -10):
                if self.toast_window and self.toast_window.winfo_exists():
                    self.toast_window.attributes('-alpha', alpha / 100.0)
                    time.sleep(0.02)
                else:
                    break
            
            if self.toast_window and self.toast_window.winfo_exists():
                self.toast_window.destroy()
        
        self.fade_thread = threading.Thread(target=fade, daemon=True)
        self.fade_thread.start()
    
    def dismiss(self):
        """Manually dismiss toast"""
        if self.toast_window and self.toast_window.winfo_exists():
            self._fade_out()


class ToastManager:
    """
    Manages toast notifications
    
    Prevents too many toasts from appearing at once
    """
    
    def __init__(self, parent):
        """
        Initialize toast manager
        
        Args:
            parent: Parent widget for toasts
        """
        self.parent = parent
        self.active_toasts = []
        self.max_toasts = 3
    
    def show(self, message: str, duration: int = 3000,
            notification_type: Literal["success", "info", "warning", "error"] = "info"):
        """
        Show a toast notification
        
        Args:
            message: Notification message
            duration: Display duration in milliseconds
            notification_type: Type of notification
        """
        # Remove old toasts if too many
        while len(self.active_toasts) >= self.max_toasts:
            old_toast = self.active_toasts.pop(0)
            if old_toast.toast_window and old_toast.toast_window.winfo_exists():
                old_toast.dismiss()
        
        # Create new toast
        toast = ToastNotification(self.parent, message, duration, notification_type)
        self.active_toasts.append(toast)
        
        # Remove from active list when dismissed
        def cleanup():
            if toast in self.active_toasts:
                self.active_toasts.remove(toast)
        
        toast.toast_window.after(duration + 500, cleanup)
    
    def success(self, message: str, duration: int = 3000):
        """Show success notification"""
        self.show(message, duration, "success")
    
    def info(self, message: str, duration: int = 3000):
        """Show info notification"""
        self.show(message, duration, "info")
    
    def warning(self, message: str, duration: int = 4000):
        """Show warning notification"""
        self.show(message, duration, "warning")
    
    def error(self, message: str, duration: int = 5000):
        """Show error notification"""
        self.show(message, duration, "error")


def show_toast(parent, message: str, duration: int = 3000,
              notification_type: Literal["success", "info", "warning", "error"] = "info"):
    """
    Convenience function to show a toast notification
    
    Args:
        parent: Parent widget
        message: Notification message
        duration: Display duration in milliseconds
        notification_type: Type of notification
    """
    toast = ToastNotification(parent, message, duration, notification_type)
    return toast

