"""
Setup Checklist for Soccer Analysis

A comprehensive checklist to ensure all necessary steps are completed
for proper video analysis setup.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
from pathlib import Path


class SetupChecklist:
    """Interactive checklist for soccer analysis setup."""
    
    def __init__(self, root=None):
        """Initialize the checklist window."""
        if root is None:
            self.root = tk.Tk()
            self.root.title("Soccer Analysis Setup Checklist")
        else:
            self.root = tk.Toplevel(root)
            self.root.title("Soccer Analysis Setup Checklist")
        
        self.root.geometry("700x800")
        self.root.resizable(True, True)
        
        # Checklist items with their status
        self.checklist_items = {
            "1. Video Setup": {
                "items": [
                    ("Load video file", False, "Load your video file in the main GUI"),
                    ("Verify video plays correctly", False, "Check that video loads and plays"),
                    ("Check video resolution and FPS", False, "Verify resolution and frame rate are correct"),
                ],
                "completed": False
            },
            "2. Field Calibration": {
                "items": [
                    ("Calibrate field boundaries", False, "Use Setup Wizard → Field Calibration to mark field corners"),
                    ("Verify field dimensions", False, "Check that field size matches your actual field"),
                    ("Test field calibration", False, "Verify players are detected within field bounds"),
                ],
                "completed": False
            },
            "3. Team Colors": {
                "items": [
                    ("Detect team colors", False, "Use Setup Wizard → Team Colors to detect team jersey colors"),
                    ("Verify team color accuracy", False, "Check that teams are correctly identified"),
                    ("Adjust HSV ranges if needed", False, "Fine-tune color detection if teams are misidentified"),
                ],
                "completed": False
            },
            "4. Ball Colors": {
                "items": [
                    ("Detect ball colors", False, "Use Setup Wizard → Ball Colors to detect ball color"),
                    ("Verify ball detection", False, "Check that ball is detected in video"),
                    ("Adjust ball color if needed", False, "Fine-tune if ball is not detected consistently"),
                ],
                "completed": False
            },
            "5. Player Identification": {
                "items": [
                    ("Tag players in Setup Wizard", False, "Use Setup Wizard → Tag Players to identify players"),
                    ("Assign jersey numbers", False, "Enter jersey numbers for each player"),
                    ("Assign teams to players", False, "Ensure each player has correct team assignment"),
                    ("Tag multiple instances", False, "Use 'Tag All Instances' for better tracking"),
                ],
                "completed": False
            },
            "6. Anchor Frames": {
                "items": [
                    ("Create anchor frames", False, "Anchor frames help with player identification"),
                    ("Tag key frames", False, "Tag players in multiple frames for better accuracy"),
                    ("Verify anchor frame quality", False, "Check that anchor frames are accurate"),
                ],
                "completed": False
            },
            "7. Analysis Settings": {
                "items": [
                    ("Configure tracking settings", False, "Set tracker type, buffer, etc. in main GUI"),
                    ("Enable/disable Re-ID", False, "Enable Re-ID for cross-video player identification"),
                    ("Set video type (Practice/Game)", False, "Select appropriate video type"),
                    ("Configure output settings", False, "Set output video format, CSV export, etc."),
                ],
                "completed": False
            },
            "8. Analytics Configuration": {
                "items": [
                    ("Select analytics to display", False, "Use Analytics Selection button to choose metrics"),
                    ("Set unit preferences", False, "Choose metric or imperial units"),
                    ("Configure analytics display", False, "Set which analytics show in video"),
                ],
                "completed": False
            },
            "9. Project Saving": {
                "items": [
                    ("Save project configuration", False, "Save all settings to project file"),
                    ("Verify project file created", False, "Check that project.json file exists"),
                    ("Test project loading", False, "Load project to verify all settings saved correctly"),
                ],
                "completed": False
            },
            "10. Testing & Validation": {
                "items": [
                    ("Run preview analysis", False, "Run a short preview to test settings"),
                    ("Verify player tracking", False, "Check that players are tracked correctly"),
                    ("Verify team classification", False, "Check that teams are correctly identified"),
                    ("Check ball tracking", False, "Verify ball is tracked throughout video"),
                    ("Review analytics output", False, "Check that analytics are calculated correctly"),
                ],
                "completed": False
            }
        }
        
        # Load saved progress if available
        self.load_progress()
        
        self.create_ui()
        
    def create_ui(self):
        """Create the checklist UI."""
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        title_label = ttk.Label(header_frame, text="Soccer Analysis Setup Checklist", 
                               font=("Arial", 16, "bold"))
        title_label.pack()
        
        subtitle_label = ttk.Label(header_frame, 
                                  text="Complete all items to ensure proper analysis setup",
                                  font=("Arial", 10))
        subtitle_label.pack(pady=5)
        
        # Progress bar
        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(progress_frame, text="Overall Progress:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                           maximum=100, length=400)
        self.progress_bar.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        self.progress_label = ttk.Label(progress_frame, text="0%", font=("Arial", 10))
        self.progress_label.pack(side=tk.LEFT, padx=5)
        
        # Scrollable checklist
        canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create checklist items
        self.checkboxes = {}
        row = 0
        
        for section_name, section_data in self.checklist_items.items():
            # Section header
            section_frame = ttk.LabelFrame(scrollable_frame, text=section_name, padding=10)
            section_frame.grid(row=row, column=0, sticky="ew", padx=10, pady=5)
            row += 1
            
            # Section items
            for i, (item_text, checked, tooltip) in enumerate(section_data["items"]):
                item_frame = ttk.Frame(section_frame)
                item_frame.pack(fill=tk.X, pady=2)
                
                var = tk.BooleanVar(value=checked)
                checkbox = ttk.Checkbutton(item_frame, text=item_text, variable=var,
                                          command=lambda v=var, s=section_name, idx=i: 
                                          self.on_checkbox_change(v, s, idx))
                checkbox.pack(side=tk.LEFT)
                
                # Tooltip label
                if tooltip:
                    tooltip_label = ttk.Label(item_frame, text=f"  ({tooltip})", 
                                            font=("Arial", 8), foreground="gray")
                    tooltip_label.pack(side=tk.LEFT)
                
                self.checkboxes[(section_name, i)] = var
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        # Buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save Progress", command=self.save_progress).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset All", command=self.reset_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Checklist", command=self.export_checklist).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.root.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Update progress
        self.update_progress()
    
    def on_checkbox_change(self, var, section_name, item_idx):
        """Handle checkbox state change."""
        self.checklist_items[section_name]["items"][item_idx] = (
            self.checklist_items[section_name]["items"][item_idx][0],
            var.get(),
            self.checklist_items[section_name]["items"][item_idx][2]
        )
        self.update_progress()
        self.save_progress()
    
    def update_progress(self):
        """Update progress bar and label."""
        total_items = 0
        completed_items = 0
        
        for section_data in self.checklist_items.values():
            for item_text, checked, tooltip in section_data["items"]:
                total_items += 1
                if checked:
                    completed_items += 1
        
        if total_items > 0:
            progress = (completed_items / total_items) * 100
            self.progress_var.set(progress)
            self.progress_label.config(text=f"{completed_items}/{total_items} ({progress:.1f}%)")
            
            # Update section completion status
            for section_name, section_data in self.checklist_items.items():
                section_items = section_data["items"]
                section_completed = all(checked for _, checked, _ in section_items)
                section_data["completed"] = section_completed
    
    def save_progress(self):
        """Save checklist progress to file."""
        try:
            progress_file = "setup_checklist_progress.json"
            progress_data = {}
            
            for section_name, section_data in self.checklist_items.items():
                progress_data[section_name] = [
                    {"text": text, "checked": checked, "tooltip": tooltip}
                    for text, checked, tooltip in section_data["items"]
                ]
            
            with open(progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
            
            # Show brief confirmation
            self.root.after(100, lambda: None)  # Non-blocking
        except Exception as e:
            print(f"Error saving progress: {e}")
    
    def load_progress(self):
        """Load checklist progress from file."""
        try:
            progress_file = "setup_checklist_progress.json"
            if os.path.exists(progress_file):
                with open(progress_file, 'r') as f:
                    progress_data = json.load(f)
                
                for section_name, items_data in progress_data.items():
                    if section_name in self.checklist_items:
                        for i, item_data in enumerate(items_data):
                            if i < len(self.checklist_items[section_name]["items"]):
                                text, _, tooltip = self.checklist_items[section_name]["items"][i]
                                checked = item_data.get("checked", False)
                                self.checklist_items[section_name]["items"][i] = (text, checked, tooltip)
        except Exception as e:
            print(f"Error loading progress: {e}")
    
    def reset_all(self):
        """Reset all checkboxes."""
        response = messagebox.askyesno("Reset All", 
                                       "Are you sure you want to reset all checklist items?")
        if response:
            for section_data in self.checklist_items.values():
                for i in range(len(section_data["items"])):
                    text, _, tooltip = section_data["items"][i]
                    section_data["items"][i] = (text, False, tooltip)
            
            # Reset checkboxes
            for (section_name, item_idx), var in self.checkboxes.items():
                var.set(False)
            
            self.update_progress()
            self.save_progress()
    
    def export_checklist(self):
        """Export checklist to text file."""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                title="Export Checklist",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            
            if filename:
                with open(filename, 'w') as f:
                    f.write("Soccer Analysis Setup Checklist\n")
                    f.write("=" * 50 + "\n\n")
                    
                    total_items = 0
                    completed_items = 0
                    
                    for section_name, section_data in self.checklist_items.items():
                        f.write(f"{section_name}\n")
                        f.write("-" * len(section_name) + "\n")
                        
                        for item_text, checked, tooltip in section_data["items"]:
                            total_items += 1
                            status = "[✓]" if checked else "[ ]"
                            f.write(f"  {status} {item_text}\n")
                            if tooltip:
                                f.write(f"      → {tooltip}\n")
                            if checked:
                                completed_items += 1
                        
                        f.write("\n")
                    
                    f.write("\n" + "=" * 50 + "\n")
                    f.write(f"Progress: {completed_items}/{total_items} items completed ")
                    f.write(f"({(completed_items/total_items*100):.1f}%)\n")
                
                messagebox.showinfo("Export Complete", 
                                  f"Checklist exported to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting checklist:\n{str(e)}")


def open_setup_checklist(parent=None):
    """Open the setup checklist window."""
    checklist = SetupChecklist(parent)
    if parent is None:
        checklist.root.mainloop()
    return checklist


if __name__ == "__main__":
    checklist = SetupChecklist()
    checklist.root.mainloop()

