"""
Color Picker Utilities
Provides a visual color picker dialog to replace RGB spinboxes throughout the application
"""

import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Optional, Tuple, List


def pick_color(parent, initial_color: Optional[Tuple[int, int, int]] = None, title: str = "Pick a Color") -> Optional[Tuple[int, int, int]]:
    """
    Open a color picker dialog and return RGB values (0-255)
    
    Args:
        parent: Parent window for the dialog
        initial_color: Initial RGB color as (R, G, B) tuple (0-255), or None for default
        title: Dialog title
    
    Returns:
        RGB tuple (R, G, B) with values 0-255, or None if cancelled
    """
    # Convert RGB (0-255) to hex for colorchooser
    if initial_color:
        r, g, b = initial_color
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
    else:
        hex_color = None
    
    # Open color chooser dialog
    color = colorchooser.askcolor(
        color=hex_color,
        title=title
    )
    
    if color[0] is None:  # User cancelled
        return None
    
    # Convert from RGB (0-1 float) to RGB (0-255 int)
    r, g, b = color[0]
    return (int(r), int(g), int(b))


def create_color_picker_widget(parent, rgb_var: tk.StringVar, label_text: str = "Color:", 
                               initial_color: Optional[Tuple[int, int, int]] = None,
                               on_change_callback=None) -> Tuple[ttk.Frame, tk.Button]:
    """
    Create a color picker widget with a label, color preview button, and RGB display
    
    Args:
        parent: Parent widget
        rgb_var: StringVar to store RGB as "R,G,B" string
        label_text: Label text
        initial_color: Initial RGB color as (R, G, B) tuple
        on_change_callback: Optional callback function(color_rgb_tuple) called when color changes
    
    Returns:
        Tuple of (frame, color_button) for further customization
    """
    frame = ttk.Frame(parent)
    
    # Label
    if label_text:
        ttk.Label(frame, text=label_text).pack(side=tk.LEFT, padx=(0, 5))
    
    # Color preview button (shows current color)
    def update_color_button():
        """Update the color button's background to show current color"""
        try:
            color_str = rgb_var.get()
            if color_str:
                parts = color_str.split(',')
                if len(parts) == 3:
                    r, g, b = [int(x.strip()) for x in parts]
                    # Convert RGB to hex for tkinter
                    hex_color = f"#{r:02x}{g:02x}{b:02x}"
                    color_button.config(bg=hex_color)
                else:
                    color_button.config(bg="SystemButtonFace")
            else:
                color_button.config(bg="SystemButtonFace")
        except Exception:
            color_button.config(bg="SystemButtonFace")
    
    def on_color_click():
        """Handle color button click - open color picker"""
        # Get current color
        current_color = None
        try:
            color_str = rgb_var.get()
            if color_str:
                parts = color_str.split(',')
                if len(parts) == 3:
                    current_color = tuple([int(x.strip()) for x in parts])
        except Exception:
            pass
        
        # Open color picker
        new_color = pick_color(parent.winfo_toplevel(), current_color, title=f"Pick {label_text}")
        
        if new_color is not None:
            # Update the string variable
            rgb_var.set(f"{new_color[0]},{new_color[1]},{new_color[2]}")
            update_color_button()
            
            # Call callback if provided
            if on_change_callback:
                on_change_callback(new_color)
    
    color_button = tk.Button(
        frame,
        text="  Pick Color  ",
        command=on_color_click,
        width=12,
        relief=tk.RAISED,
        cursor="hand2"
    )
    color_button.pack(side=tk.LEFT, padx=(0, 5))
    
    # RGB display (read-only entry showing current RGB values)
    rgb_display = ttk.Entry(frame, width=15, state="readonly")
    rgb_display.pack(side=tk.LEFT, padx=(0, 5))
    
    def update_rgb_display(*args):
        """Update the RGB display when variable changes"""
        try:
            color_str = rgb_var.get()
            if color_str:
                rgb_display.config(state="normal")
                rgb_display.delete(0, tk.END)
                rgb_display.insert(0, color_str)
                rgb_display.config(state="readonly")
            else:
                rgb_display.config(state="normal")
                rgb_display.delete(0, tk.END)
                rgb_display.config(state="readonly")
            update_color_button()
        except Exception:
            pass
    
    # Initialize display
    if initial_color:
        rgb_var.set(f"{initial_color[0]},{initial_color[1]},{initial_color[2]}")
    
    # Watch for changes
    rgb_var.trace_add("write", update_rgb_display)
    update_rgb_display()  # Initial update
    
    return frame, color_button


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple (0-255) to hex string"""
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex string to RGB tuple (0-255)"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_string_to_tuple(rgb_str: str, default: Optional[Tuple[int, int, int]] = None) -> Optional[Tuple[int, int, int]]:
    """Parse RGB string "R,G,B" to tuple (R, G, B)"""
    try:
        if not rgb_str or not rgb_str.strip():
            return default
        parts = rgb_str.split(',')
        if len(parts) == 3:
            return tuple([int(x.strip()) for x in parts])
    except Exception:
        pass
    return default

