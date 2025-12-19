"""
Anchor Frame Viewer
Simple tool to view and review anchor frames from PlayerTagsSeed JSON files.
"""

import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
from pathlib import Path
from collections import defaultdict


class AnchorFrameViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Anchor Frame Viewer")
        self.root.geometry("1400x900")
        
        self.anchor_file = None
        self.video_path = None
        self.cap = None
        self.anchor_frames = {}
        self.current_frame_num = 0
        self.total_frames = 0
        self.fps = 30.0
        
        # Group anchors by player for easier navigation
        self.player_anchors = defaultdict(list)  # player_name -> [(frame_num, anchor_data), ...]
        
        self.create_widgets()
    
    def create_widgets(self):
        # Top frame for file selection
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Button(top_frame, text="Load Anchor File", command=self.load_anchor_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Load Video", command=self.load_video).pack(side=tk.LEFT, padx=5)
        
        self.status_label = ttk.Label(top_frame, text="No anchor file loaded")
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # Main content area
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel: Player list and frame navigation
        left_panel = ttk.Frame(main_frame, width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # Player list
        ttk.Label(left_panel, text="Players with Anchors:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        player_frame = ttk.Frame(left_panel)
        player_frame.pack(fill=tk.BOTH, expand=True)
        
        player_scrollbar = ttk.Scrollbar(player_frame)
        player_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.player_listbox = tk.Listbox(player_frame, yscrollcommand=player_scrollbar.set, height=15)
        self.player_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        player_scrollbar.config(command=self.player_listbox.yview)
        self.player_listbox.bind('<<ListboxSelect>>', self.on_player_select)
        
        # Frame navigation
        nav_frame = ttk.LabelFrame(left_panel, text="Frame Navigation", padding="10")
        nav_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(nav_frame, text="◀◀ First", command=self.go_first).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="◀ Prev", command=self.go_prev).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="Next ▶", command=self.go_next).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="Last ▶▶", command=self.go_last).pack(side=tk.LEFT, padx=2)
        
        self.frame_label = ttk.Label(nav_frame, text="Frame: 0")
        self.frame_label.pack(pady=5)
        
        # Anchor info
        info_frame = ttk.LabelFrame(left_panel, text="Anchor Info", padding="10")
        info_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.info_text = tk.Text(info_frame, height=8, wrap=tk.WORD, font=("Courier", 9))
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        # Right panel: Video display
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(right_panel, text="Video Frame with Anchor Overlays:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        self.canvas = tk.Canvas(right_panel, bg="black", width=800, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Statistics
        stats_frame = ttk.LabelFrame(right_panel, text="Statistics", padding="10")
        stats_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.stats_label = ttk.Label(stats_frame, text="No data loaded", font=("Arial", 9))
        self.stats_label.pack(anchor=tk.W)
    
    def load_anchor_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Anchor Frame File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                if isinstance(data, dict) and 'anchor_frames' in data:
                    self.anchor_frames = data['anchor_frames']
                elif isinstance(data, dict):
                    self.anchor_frames = data
                else:
                    messagebox.showerror("Error", "Invalid anchor frame file format")
                    return
                
                self.anchor_file = file_path
                self.process_anchors()
                self.status_label.config(text=f"Loaded: {Path(file_path).name} ({len(self.anchor_frames)} frames)")
                self.update_statistics()
                
            except Exception as e:
                messagebox.showerror("Error", f"Could not load anchor file:\n{e}")
    
    def load_video(self):
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if file_path:
            self.video_path = file_path
            self.cap = cv2.VideoCapture(file_path)
            if self.cap.isOpened():
                self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                self.status_label.config(text=f"{self.status_label.cget('text')} | Video: {Path(file_path).name}")
                self.display_frame()
            else:
                messagebox.showerror("Error", "Could not open video file")
    
    def process_anchors(self):
        """Group anchors by player and sort frames"""
        self.player_anchors.clear()
        
        for frame_str, anchors in self.anchor_frames.items():
            try:
                frame_num = int(frame_str)
            except:
                continue
            
            for anchor in anchors:
                player_name = anchor.get('player_name', 'Unknown')
                self.player_anchors[player_name].append((frame_num, anchor))
        
        # Sort frames for each player
        for player_name in self.player_anchors:
            self.player_anchors[player_name].sort(key=lambda x: x[0])
        
        # Update player listbox
        self.player_listbox.delete(0, tk.END)
        for player_name in sorted(self.player_anchors.keys()):
            count = len(self.player_anchors[player_name])
            self.player_listbox.insert(tk.END, f"{player_name} ({count} anchors)")
    
    def on_player_select(self, event):
        selection = self.player_listbox.curselection()
        if selection:
            player_name = self.player_listbox.get(selection[0]).split(' (')[0]
            if player_name in self.player_anchors and self.player_anchors[player_name]:
                # Go to first anchor frame for this player
                first_frame, _ = self.player_anchors[player_name][0]
                self.current_frame_num = first_frame
                self.display_frame()
    
    def go_first(self):
        if self.anchor_frames:
            frames = sorted([int(f) for f in self.anchor_frames.keys() if f.isdigit()])
            if frames:
                self.current_frame_num = frames[0]
                self.display_frame()
    
    def go_prev(self):
        if self.anchor_frames:
            frames = sorted([int(f) for f in self.anchor_frames.keys() if f.isdigit()])
            current_idx = frames.index(self.current_frame_num) if self.current_frame_num in frames else -1
            if current_idx > 0:
                self.current_frame_num = frames[current_idx - 1]
                self.display_frame()
    
    def go_next(self):
        if self.anchor_frames:
            frames = sorted([int(f) for f in self.anchor_frames.keys() if f.isdigit()])
            current_idx = frames.index(self.current_frame_num) if self.current_frame_num in frames else -1
            if current_idx < len(frames) - 1:
                self.current_frame_num = frames[current_idx + 1]
                self.display_frame()
    
    def go_last(self):
        if self.anchor_frames:
            frames = sorted([int(f) for f in self.anchor_frames.keys() if f.isdigit()])
            if frames:
                self.current_frame_num = frames[-1]
                self.display_frame()
    
    def display_frame(self):
        if not self.cap or not self.cap.isOpened():
            return
        
        # Seek to frame
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_num)
        ret, frame = self.cap.read()
        if not ret:
            return
        
        # Draw anchor overlays
        frame_str = str(self.current_frame_num)
        if frame_str in self.anchor_frames:
            anchors = self.anchor_frames[frame_str]
            for anchor in anchors:
                bbox = anchor.get('bbox')
                player_name = anchor.get('player_name', 'Unknown')
                team = anchor.get('team', '')
                confidence = anchor.get('confidence', 1.0)
                
                if bbox and len(bbox) >= 4:
                    x1, y1, x2, y2 = [int(b) for b in bbox[:4]]
                    
                    # Draw bounding box
                    color = (0, 255, 0) if confidence >= 1.0 else (0, 255, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    
                    # Draw label
                    label = f"{player_name}"
                    if team:
                        label += f" ({team})"
                    if confidence < 1.0:
                        label += f" [{confidence:.2f}]"
                    
                    (text_width, text_height), baseline = cv2.getTextSize(
                        label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
                    )
                    cv2.rectangle(frame, (x1, y1 - text_height - 10), 
                                (x1 + text_width + 4, y1), color, -1)
                    cv2.putText(frame, label, (x1 + 2, y1 - 5),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        # Convert to RGB for display
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Resize to fit canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width > 1 and canvas_height > 1:
            h, w = frame_rgb.shape[:2]
            scale = min(canvas_width / w, canvas_height / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            frame_rgb = cv2.resize(frame_rgb, (new_w, new_h))
        
        # Display
        img = Image.fromarray(frame_rgb)
        photo = ImageTk.PhotoImage(image=img)
        self.canvas.delete("all")
        self.canvas.create_image(canvas_width // 2, canvas_height // 2, anchor=tk.CENTER, image=photo)
        self.canvas.image_ref = photo
        
        # Update frame label
        self.frame_label.config(text=f"Frame: {self.current_frame_num}")
        
        # Update info text
        self.update_info()
    
    def update_info(self):
        frame_str = str(self.current_frame_num)
        self.info_text.delete(1.0, tk.END)
        
        if frame_str in self.anchor_frames:
            anchors = self.anchor_frames[frame_str]
            self.info_text.insert(tk.END, f"Frame {self.current_frame_num}:\n")
            self.info_text.insert(tk.END, f"{len(anchors)} anchor(s)\n\n")
            
            for i, anchor in enumerate(anchors, 1):
                self.info_text.insert(tk.END, f"Anchor {i}:\n")
                self.info_text.insert(tk.END, f"  Player: {anchor.get('player_name', 'Unknown')}\n")
                self.info_text.insert(tk.END, f"  Team: {anchor.get('team', 'N/A')}\n")
                self.info_text.insert(tk.END, f"  Confidence: {anchor.get('confidence', 1.0):.2f}\n")
                bbox = anchor.get('bbox', [])
                if bbox:
                    self.info_text.insert(tk.END, f"  BBox: [{bbox[0]:.0f}, {bbox[1]:.0f}, {bbox[2]:.0f}, {bbox[3]:.0f}]\n")
                self.info_text.insert(tk.END, "\n")
        else:
            self.info_text.insert(tk.END, f"Frame {self.current_frame_num}:\n")
            self.info_text.insert(tk.END, "No anchors in this frame")
    
    def update_statistics(self):
        total_anchors = sum(len(anchors) for anchors in self.anchor_frames.values())
        total_players = len(self.player_anchors)
        total_frames = len(self.anchor_frames)
        
        stats = f"Total Frames: {total_frames} | Total Anchors: {total_anchors} | Players: {total_players}"
        self.stats_label.config(text=stats)


if __name__ == "__main__":
    root = tk.Tk()
    app = AnchorFrameViewer(root)
    root.mainloop()

