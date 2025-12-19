"""
Batch Anchor Frame Workflow
Helps you efficiently create anchor frames across multiple videos or frames
"""
import json
import os
import glob
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog
import sys

class BatchAnchorFrameWorkflow:
    """GUI workflow for batch creating anchor frames"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Batch Anchor Frame Workflow")
        self.root.geometry("800x600")
        
        self.video_path = None
        self.selected_frames = []
        self.target_players = []
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create GUI widgets"""
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = tk.Label(main_frame, text="Batch Anchor Frame Creator", 
                        font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Video selection
        video_frame = tk.LabelFrame(main_frame, text="1. Select Video", padx=10, pady=10)
        video_frame.pack(fill=tk.X, pady=5)
        
        self.video_label = tk.Label(video_frame, text="No video selected", 
                                    foreground="gray")
        self.video_label.pack(side=tk.LEFT, padx=5)
        
        tk.Button(video_frame, text="Browse...", 
                 command=self.select_video).pack(side=tk.RIGHT, padx=5)
        
        # Frame selection strategy
        strategy_frame = tk.LabelFrame(main_frame, text="2. Frame Selection Strategy", 
                                       padx=10, pady=10)
        strategy_frame.pack(fill=tk.X, pady=5)
        
        self.strategy_var = tk.StringVar(value="suggested")
        tk.Radiobutton(strategy_frame, text="Suggested frames (beginning, middle, end)", 
                      variable=self.strategy_var, value="suggested").pack(anchor=tk.W)
        tk.Radiobutton(strategy_frame, text="Custom frame numbers", 
                      variable=self.strategy_var, value="custom").pack(anchor=tk.W)
        tk.Radiobutton(strategy_frame, text="Evenly spaced frames", 
                      variable=self.strategy_var, value="spaced").pack(anchor=tk.W)
        
        # Frame count input
        input_frame = tk.Frame(strategy_frame)
        input_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(input_frame, text="Number of frames:").pack(side=tk.LEFT, padx=5)
        self.frame_count_var = tk.StringVar(value="10")
        tk.Entry(input_frame, textvariable=self.frame_count_var, width=10).pack(side=tk.LEFT, padx=5)
        
        # Custom frames input
        custom_frame = tk.Frame(strategy_frame)
        custom_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(custom_frame, text="Custom frames (comma-separated):").pack(side=tk.LEFT, padx=5)
        self.custom_frames_var = tk.StringVar(value="0, 1000, 2000, 3000, 5000")
        custom_entry = tk.Entry(custom_frame, textvariable=self.custom_frames_var, width=30)
        custom_entry.pack(side=tk.LEFT, padx=5)
        
        # Help text for custom frames
        help_label = tk.Label(strategy_frame, 
                             text="Example: 0, 1000, 2000, 3000, 5000 (works without video info)",
                             font=("Arial", 8), foreground="gray")
        help_label.pack(anchor=tk.W, padx=5)
        
        # Player list
        players_frame = tk.LabelFrame(main_frame, text="3. Target Players (Optional)", 
                                      padx=10, pady=10)
        players_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        tk.Label(players_frame, 
                text="Enter player names to focus on (one per line, or leave empty for all):",
                font=("Arial", 9)).pack(anchor=tk.W, pady=5)
        
        self.players_text = tk.Text(players_frame, height=5, width=50)
        self.players_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Actions
        action_frame = tk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(action_frame, text="📋 Generate Workflow Plan", 
                 command=self.generate_plan, bg="#4CAF50", fg="white",
                 font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        tk.Button(action_frame, text="📄 Export Plan to File", 
                 command=self.export_plan).pack(side=tk.LEFT, padx=5)
        
        tk.Button(action_frame, text="🚀 Open Setup Wizard", 
                 command=self.open_setup_wizard).pack(side=tk.LEFT, padx=5)
        
        # Results
        results_frame = tk.LabelFrame(main_frame, text="Workflow Plan", padx=10, pady=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = tk.Scrollbar(results_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.results_text = tk.Text(results_frame, height=10, yscrollcommand=scrollbar.set)
        self.results_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.results_text.yview)
    
    def select_video(self):
        """Select video file"""
        video_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if video_path:
            self.video_path = video_path
            self.video_label.config(text=os.path.basename(video_path), 
                                   foreground="black")
    
    def get_video_info(self):
        """Get video frame count and duration"""
        if not self.video_path or not os.path.exists(self.video_path):
            return None, None, None
        
        try:
            import cv2
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                print(f"[WARNING] Could not open video: {self.video_path}")
                return None, None, None
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            cap.release()
            
            # Validate results
            if total_frames <= 0:
                print(f"[WARNING] Invalid frame count: {total_frames}")
                return None, None, None
            
            return total_frames, fps, duration
        except ImportError:
            messagebox.showwarning(
                "OpenCV Not Available",
                "OpenCV is required to read video information.\n\n"
                "Install with: pip install opencv-python\n\n"
                "You can still use the workflow, but frame suggestions will be limited."
            )
            return None, None, None
        except Exception as e:
            print(f"[ERROR] Could not read video info: {e}")
            messagebox.showerror(
                "Video Read Error",
                f"Could not read video information:\n\n{str(e)}\n\n"
                "The video file may be corrupted or in an unsupported format.\n"
                "You can still proceed with manual frame numbers."
            )
            return None, None, None
    
    def calculate_frames(self):
        """Calculate which frames to tag based on strategy"""
        total_frames, fps, duration = self.get_video_info()
        
        strategy = self.strategy_var.get()
        frames = []
        
        if strategy == "suggested":
            if total_frames is None:
                messagebox.showwarning(
                    "Video Info Required",
                    "Cannot use 'Suggested frames' strategy without video information.\n\n"
                    "Please:\n"
                    "• Install OpenCV: pip install opencv-python\n"
                    "• OR use 'Custom frame numbers' strategy instead"
                )
                return []
            
            # Beginning, middle, end, plus evenly spaced
            count = int(self.frame_count_var.get() or "10")
            frames.append(0)
            frames.append(total_frames // 2)
            frames.append(total_frames - 1)
            
            # Add evenly spaced frames
            spacing = total_frames // (count - 2)
            for i in range(1, count - 2):
                frame = i * spacing
                if frame not in frames:
                    frames.append(frame)
        
        elif strategy == "custom":
            # Parse custom frame numbers
            custom_str = self.custom_frames_var.get().strip()
            if not custom_str:
                messagebox.showwarning(
                    "No Custom Frames",
                    "Please enter frame numbers (comma-separated)\n"
                    "Example: 0, 1000, 2000, 3000, 5000"
                )
                return []
            
            try:
                frames = [int(f.strip()) for f in custom_str.split(",")]
                # Only filter by total_frames if we have it
                if total_frames is not None:
                    frames = [f for f in frames if 0 <= f < total_frames]
                else:
                    # Just filter out negative frames
                    frames = [f for f in frames if f >= 0]
            except ValueError as e:
                messagebox.showerror(
                    "Invalid Frame Numbers",
                    f"Could not parse frame numbers:\n\n{str(e)}\n\n"
                    "Please enter numbers separated by commas.\n"
                    "Example: 0, 1000, 2000, 3000"
                )
                return []
        
        elif strategy == "spaced":
            if total_frames is None:
                messagebox.showwarning(
                    "Video Info Required",
                    "Cannot use 'Evenly spaced frames' strategy without video information.\n\n"
                    "Please:\n"
                    "• Install OpenCV: pip install opencv-python\n"
                    "• OR use 'Custom frame numbers' strategy instead"
                )
                return []
            
            # Evenly spaced frames
            count = int(self.frame_count_var.get() or "10")
            spacing = total_frames // (count + 1)
            for i in range(1, count + 1):
                frames.append(i * spacing)
        
        return sorted(set(frames))
    
    def generate_plan(self):
        """Generate workflow plan"""
        if not self.video_path:
            messagebox.showwarning("No Video", "Please select a video first")
            return
        
        total_frames, fps, duration = self.get_video_info()
        
        # If we can't read video info, allow manual frame entry
        if total_frames is None:
            response = messagebox.askyesno(
                "Video Info Unavailable",
                "Could not read video information automatically.\n\n"
                "Would you like to:\n"
                "• Enter frame numbers manually (Yes)\n"
                "• Try a different video (No)\n\n"
                "You can still create a workflow plan with custom frame numbers."
            )
            if not response:
                return
            
            # Use custom frames strategy
            self.strategy_var.set("custom")
            if not self.custom_frames_var.get().strip():
                # Suggest some default frames
                self.custom_frames_var.set("0, 1000, 2000, 3000, 5000")
                messagebox.showinfo(
                    "Using Custom Frames",
                    "Using default frame numbers: 0, 1000, 2000, 3000, 5000\n\n"
                    "You can edit these in the 'Custom frame numbers' field."
                )
        
        frames = self.calculate_frames()
        if not frames:
            messagebox.showwarning(
                "No Frames",
                "No valid frames selected.\n\n"
                "Please:\n"
                "• Enter custom frame numbers (comma-separated), OR\n"
                "• Select a different strategy"
            )
            return
        
        # Get target players
        players_text = self.players_text.get("1.0", tk.END).strip()
        target_players = [p.strip() for p in players_text.split("\n") if p.strip()]
        
        # Generate plan
        plan = []
        plan.append("="*70)
        plan.append("BATCH ANCHOR FRAME WORKFLOW PLAN")
        plan.append("="*70)
        plan.append(f"\nVideo: {os.path.basename(self.video_path)}")
        plan.append(f"Video path: {self.video_path}")
        
        if total_frames is not None:
            plan.append(f"Total frames: {total_frames}")
            plan.append(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
            plan.append(f"FPS: {fps:.1f}")
        else:
            plan.append("Total frames: Unknown (using custom frame numbers)")
            plan.append("Duration: Unknown")
            plan.append("FPS: Unknown")
        
        plan.append(f"\nTarget frames: {len(frames)} frames")
        if target_players:
            plan.append(f"Target players: {', '.join(target_players)}")
        else:
            plan.append("Target players: All visible players")
        
        plan.append("\n" + "-"*70)
        plan.append("STEP-BY-STEP WORKFLOW:")
        plan.append("-"*70)
        
        plan.append("\n1. Open Setup Wizard or Gallery Seeder")
        plan.append("   - Main GUI → 'Setup Wizard' (recommended)")
        plan.append("   - OR Main GUI → 'Tag Players (Gallery)'")
        
        plan.append("\n2. Load your video:")
        plan.append(f"   {self.video_path}")
        
        plan.append("\n3. Tag players at the following frames:")
        for i, frame_num in enumerate(frames, 1):
            if total_frames is not None and fps > 0:
                time_sec = frame_num / fps
                if time_sec > 60:
                    time_str = f"{int(time_sec//60)}m {int(time_sec%60)}s"
                else:
                    time_str = f"{int(time_sec)}s"
                frame_info = f"Frame #{frame_num} ({time_str})"
            else:
                frame_info = f"Frame #{frame_num}"
            
            plan.append(f"\n   Frame {i}/{len(frames)}: {frame_info}")
            plan.append(f"      - Navigate to frame {frame_num}")
            if target_players:
                plan.append(f"      - Look for: {', '.join(target_players[:3])}")
                if len(target_players) > 3:
                    plan.append(f"        (and {len(target_players)-3} more)")
            plan.append(f"      - Tag 3-5 players at this frame")
            plan.append(f"      - Each tag = 1 anchor frame")
        
        plan.append("\n" + "-"*70)
        plan.append("TIPS:")
        plan.append("-"*70)
        plan.append("• Tag the same players across multiple frames for best results")
        plan.append("• Focus on key players (goalkeepers, star players, etc.)")
        plan.append("• Tag players from both teams")
        plan.append("• Use clear frames where players are fully visible")
        plan.append("• Don't worry about tagging every single frame")
        
        plan.append("\n" + "-"*70)
        plan.append("ESTIMATED TIME:")
        plan.append("-"*70)
        time_per_frame = 30  # seconds
        total_time = len(frames) * time_per_frame
        plan.append(f"~{total_time} seconds ({total_time/60:.1f} minutes) for {len(frames)} frames")
        plan.append(f"Assuming ~{time_per_frame} seconds per frame (tagging 3-5 players)")
        
        plan.append("\n" + "="*70)
        
        # Display plan
        self.results_text.delete("1.0", tk.END)
        self.results_text.insert("1.0", "\n".join(plan))
        
        self.selected_frames = frames
        self.target_players = target_players
    
    def export_plan(self):
        """Export workflow plan to file"""
        plan_text = self.results_text.get("1.0", tk.END)
        if not plan_text.strip():
            messagebox.showwarning("No Plan", "Please generate a plan first")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Save Workflow Plan",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(plan_text)
                messagebox.showinfo("Success", f"Plan saved to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file:\n{e}")
    
    def open_setup_wizard(self):
        """Open setup wizard with video pre-loaded"""
        if not self.video_path:
            messagebox.showwarning("No Video", "Please select a video first")
            return
        
        messagebox.showinfo(
            "Open Setup Wizard",
            f"1. Click 'Setup Wizard' in the main GUI\n"
            f"2. Load video: {os.path.basename(self.video_path)}\n"
            f"3. Follow the workflow plan shown above\n\n"
            f"Video path:\n{self.video_path}"
        )
    
    def run(self):
        """Run the workflow GUI"""
        self.root.mainloop()

if __name__ == "__main__":
    app = BatchAnchorFrameWorkflow()
    app.run()

