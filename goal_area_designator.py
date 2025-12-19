"""
Goal Area Designation Tool
Allows user to designate goal areas on the field by clicking to define goal boundaries.
Saves goal area definitions for use in shot and goal detection.
"""

import cv2
import numpy as np
import json
import os
from typing import Tuple, Optional, Dict, List

class GoalAreaDesignator:
    def __init__(self, video_path: str, frame_num: int = 0):
        """
        Initialize goal area designator.
        
        Args:
            video_path: Path to video file
            frame_num: Frame number to use for designation (default: 0)
        """
        self.video_path = video_path
        self.frame_num = frame_num
        self.cap = None
        self.frame = None
        self.goal_areas = {}  # 'goal_1', 'goal_2' -> {'points': [(x,y), ...], 'type': 'rectangle' or 'polygon'}
        self.current_goal = None
        self.current_points = []
        self.designation_mode = "rectangle"  # "rectangle" or "polygon"
        
    def load_frame(self, frame_num: Optional[int] = None) -> bool:
        """Load a specific frame from video"""
        if frame_num is not None:
            self.frame_num = frame_num
        
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                return False
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.frame_num)
        ret, frame = self.cap.read()
        if ret:
            self.frame = frame.copy()
            return True
        return False
    
    def save_goal_areas(self, output_path: Optional[str] = None) -> str:
        """
        Save goal area definitions to JSON file.
        
        Args:
            output_path: Path to save JSON file (default: goal_areas_{video_name}.json)
        
        Returns:
            Path to saved file
        """
        if output_path is None:
            video_dir = os.path.dirname(os.path.abspath(self.video_path))
            video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
            output_path = os.path.join(video_dir, f"goal_areas_{video_basename}.json")
        
        # Get video properties
        if self.cap:
            frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
        else:
            frame_width = self.frame.shape[1] if self.frame is not None else 1920
            frame_height = self.frame.shape[0] if self.frame is not None else 1080
            fps = 30.0
        
        # Convert points to normalized coordinates (0-1)
        normalized_areas = {}
        for goal_name, goal_data in self.goal_areas.items():
            normalized_points = []
            for point in goal_data['points']:
                norm_x = point[0] / frame_width
                norm_y = point[1] / frame_height
                normalized_points.append([norm_x, norm_y])
            
            normalized_areas[goal_name] = {
                'type': goal_data['type'],
                'points': normalized_points,
                'frame_width': frame_width,
                'frame_height': frame_height
            }
        
        data = {
            'video_path': self.video_path,
            'video_resolution': f"{frame_width}x{frame_height}",
            'video_fps': fps,
            'designation_frame': self.frame_num,
            'goal_areas': normalized_areas
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return output_path
    
    def load_goal_areas(self, json_path: str) -> bool:
        """
        Load goal area definitions from JSON file.
        
        Args:
            json_path: Path to JSON file
        
        Returns:
            True if loaded successfully
        """
        if not os.path.exists(json_path):
            return False
        
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            frame_width = data.get('frame_width', 1920)
            frame_height = data.get('frame_height', 1080)
            
            # Convert normalized points back to pixel coordinates
            self.goal_areas = {}
            for goal_name, goal_data in data.get('goal_areas', {}).items():
                pixel_points = []
                for norm_point in goal_data.get('points', []):
                    x = int(norm_point[0] * frame_width)
                    y = int(norm_point[1] * frame_height)
                    pixel_points.append((x, y))
                
                self.goal_areas[goal_name] = {
                    'type': goal_data.get('type', 'rectangle'),
                    'points': pixel_points
                }
            
            return True
        except Exception as e:
            print(f"Error loading goal areas: {e}")
            return False
    
    def get_goal_area_bounds(self, goal_name: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Get bounding box for a goal area in normalized coordinates (0-1).
        Returns (min_x, min_y, max_x, max_y) or None if goal doesn't exist.
        """
        if goal_name not in self.goal_areas:
            return None
        
        points = self.goal_areas[goal_name]['points']
        if not points:
            return None
        
        # Get frame dimensions
        if self.cap:
            frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        elif self.frame is not None:
            frame_width = self.frame.shape[1]
            frame_height = self.frame.shape[0]
        else:
            return None
        
        # Find bounds
        min_x = min(p[0] for p in points) / frame_width
        min_y = min(p[1] for p in points) / frame_height
        max_x = max(p[0] for p in points) / frame_width
        max_y = max(p[1] for p in points) / frame_height
        
        return (min_x, min_y, max_x, max_y)
    
    def is_point_in_goal(self, x: float, y: float, goal_name: str) -> bool:
        """
        Check if a point (in pixel coordinates) is inside a goal area.
        
        Args:
            x, y: Point coordinates in pixels
            goal_name: Name of goal area to check
        
        Returns:
            True if point is inside goal area
        """
        if goal_name not in self.goal_areas:
            return False
        
        goal_data = self.goal_areas[goal_name]
        points = goal_data['points']
        
        if goal_data['type'] == 'rectangle' and len(points) >= 2:
            # Simple rectangle check
            min_x = min(p[0] for p in points)
            max_x = max(p[0] for p in points)
            min_y = min(p[1] for p in points)
            max_y = max(p[1] for p in points)
            return min_x <= x <= max_x and min_y <= y <= max_y
        elif goal_data['type'] == 'polygon' and len(points) >= 3:
            # Point-in-polygon test
            return self._point_in_polygon(x, y, points)
        
        return False
    
    def _point_in_polygon(self, x: float, y: float, polygon: List[Tuple[float, float]]) -> bool:
        """Point-in-polygon test using ray casting algorithm"""
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def cleanup(self):
        """Clean up resources"""
        if self.cap:
            self.cap.release()

def designate_goal_areas_interactive(video_path: str, frame_num: int = 0) -> Optional[GoalAreaDesignator]:
    """
    Interactive goal area designation using OpenCV window.
    User clicks to define goal areas.
    
    Args:
        video_path: Path to video file
        frame_num: Frame number to use for designation
    
    Returns:
        GoalAreaDesignator instance with designated areas, or None if cancelled
    """
    designator = GoalAreaDesignator(video_path, frame_num)
    
    if not designator.load_frame():
        print(f"Error: Could not load frame {frame_num} from {video_path}")
        return None
    
    frame = designator.frame.copy()
    display_frame = frame.copy()
    
    # Get frame dimensions for proper scaling
    frame_height, frame_width = frame.shape[:2]
    
    # Mouse callback state
    drawing = False
    current_goal_name = None
    current_points = []
    goal_counter = 1
    
    def mouse_callback(event, x, y, flags, param):
        nonlocal drawing, current_goal_name, current_points, display_frame, goal_counter
        
        # OpenCV mouse callback gives coordinates in the displayed image coordinate space
        # When window is resized, OpenCV scales the image, so we need to get the actual displayed image size
        try:
            # getWindowImageRect returns (x, y, width, height) of the displayed image
            rect = cv2.getWindowImageRect("Goal Area Designation")
            displayed_w = rect[2] if rect[2] > 0 else frame_width
            displayed_h = rect[3] if rect[3] > 0 else frame_height
        except:
            displayed_w = frame_width
            displayed_h = frame_height
        
        # Scale mouse coordinates from displayed image size to original frame size
        # This handles cases where the image is scaled to fit the window
        scale_x = frame_width / displayed_w if displayed_w > 0 else 1.0
        scale_y = frame_height / displayed_h if displayed_h > 0 else 1.0
        orig_x = int(x * scale_x)
        orig_y = int(y * scale_y)
        
        # Clamp to frame bounds
        orig_x = max(0, min(orig_x, frame_width - 1))
        orig_y = max(0, min(orig_y, frame_height - 1))
        
        if event == cv2.EVENT_LBUTTONDOWN:
            if current_goal_name is None:
                # Start new goal
                current_goal_name = f"goal_{goal_counter}"
                current_points = [(orig_x, orig_y)]
                drawing = True
            else:
                # Add point to current goal (use original frame coordinates)
                current_points.append((orig_x, orig_y))
                
                # Redraw
                display_frame = frame.copy()
                
                # Draw all existing goals
                for goal_name, goal_data in designator.goal_areas.items():
                    points = goal_data['points']
                    if goal_data['type'] == 'rectangle' and len(points) >= 2:
                        cv2.rectangle(display_frame, points[0], points[1], (0, 255, 0), 2)
                        cv2.putText(display_frame, goal_name, (points[0][0], points[0][1] - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    elif len(points) >= 3:
                        pts = np.array(points, np.int32)
                        cv2.polylines(display_frame, [pts], True, (0, 255, 0), 2)
                        cv2.putText(display_frame, goal_name, (points[0][0], points[0][1] - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Draw current goal being defined
                if len(current_points) >= 2:
                    if designator.designation_mode == 'rectangle':
                        cv2.rectangle(display_frame, current_points[0], current_points[-1], (255, 0, 0), 2)
                    else:
                        pts = np.array(current_points, np.int32)
                        cv2.polylines(display_frame, [pts], False, (255, 0, 0), 2)
                
                # Draw points
                for pt in current_points:
                    cv2.circle(display_frame, pt, 5, (255, 0, 0), -1)
        
        elif event == cv2.EVENT_RBUTTONDOWN:
            # Finish current goal
            if current_goal_name and len(current_points) >= 2:
                designator.goal_areas[current_goal_name] = {
                    'type': designator.designation_mode,
                    'points': current_points.copy()
                }
                goal_counter += 1
                current_goal_name = None
                current_points = []
                
                # Redraw
                display_frame = frame.copy()
                for goal_name, goal_data in designator.goal_areas.items():
                    points = goal_data['points']
                    if goal_data['type'] == 'rectangle' and len(points) >= 2:
                        cv2.rectangle(display_frame, points[0], points[1], (0, 255, 0), 2)
                        cv2.putText(display_frame, goal_name, (points[0][0], points[0][1] - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    elif len(points) >= 3:
                        pts = np.array(points, np.int32)
                        cv2.polylines(display_frame, [pts], True, (0, 255, 0), 2)
                        cv2.putText(display_frame, goal_name, (points[0][0], points[0][1] - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        elif event == cv2.EVENT_MOUSEMOVE and drawing:
            # Show preview
            if len(current_points) > 0:
                display_frame = frame.copy()
                
                # Draw existing goals
                for goal_name, goal_data in designator.goal_areas.items():
                    points = goal_data['points']
                    if goal_data['type'] == 'rectangle' and len(points) >= 2:
                        cv2.rectangle(display_frame, points[0], points[1], (0, 255, 0), 2)
                        cv2.putText(display_frame, goal_name, (points[0][0], points[0][1] - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    elif len(points) >= 3:
                        pts = np.array(points, np.int32)
                        cv2.polylines(display_frame, [pts], True, (0, 255, 0), 2)
                        cv2.putText(display_frame, goal_name, (points[0][0], points[0][1] - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Draw current goal preview (coordinates are already in frame space)
                if designator.designation_mode == 'rectangle':
                    cv2.rectangle(display_frame, current_points[0], (orig_x, orig_y), (255, 0, 0), 2)
                else:
                    preview_points = current_points + [(orig_x, orig_y)]
                    if len(preview_points) >= 2:
                        pts = np.array(preview_points, np.int32)
                        cv2.polylines(display_frame, [pts], False, (255, 0, 0), 2)
                
                for pt in current_points:
                    cv2.circle(display_frame, pt, 5, (255, 0, 0), -1)
                cv2.circle(display_frame, (orig_x, orig_y), 5, (255, 0, 0), -1)
        
        cv2.imshow("Goal Area Designation", display_frame)
    
    # Instructions
    print("\n=== Goal Area Designation ===")
    print("Left-click: Add point to current goal")
    print("Right-click: Finish current goal and start next")
    print("Press 'r': Switch to rectangle mode (2 points)")
    print("Press 'p': Switch to polygon mode (multiple points)")
    print("Press 'c': Clear all goals")
    print("Press 's': Save and exit")
    print("Press 'q' or ESC: Cancel and exit")
    print(f"\nDesignating goal areas on frame {frame_num}")
    print("Start by left-clicking to define goal boundaries...")
    
    # Create resizable window
    cv2.namedWindow("Goal Area Designation", cv2.WINDOW_NORMAL)
    
    # Get screen size to fit window appropriately
    try:
        import tkinter as tk
        root_temp = tk.Tk()
        screen_width = root_temp.winfo_screenwidth()
        screen_height = root_temp.winfo_screenheight()
        root_temp.destroy()
    except:
        screen_width = 1920
        screen_height = 1080
    
    # Scale to fit screen (use 85% of screen, maintain aspect ratio)
    max_display_width = int(screen_width * 0.85)
    max_display_height = int(screen_height * 0.85)
    
    # Calculate scaling to fit (scale down if needed, but show full frame)
    scale_w = max_display_width / frame_width if frame_width > max_display_width else 1.0
    scale_h = max_display_height / frame_height if frame_height > max_display_height else 1.0
    scale = min(scale_w, scale_h)  # Use smaller scale to ensure it fits
    
    # Set initial window size (show full frame, scaled to fit screen)
    display_width = int(frame_width * scale)
    display_height = int(frame_height * scale)
    cv2.resizeWindow("Goal Area Designation", display_width, display_height)
    
    # Center window on screen
    window_x = max(0, (screen_width - display_width) // 2)
    window_y = max(0, (screen_height - display_height) // 2)
    cv2.moveWindow("Goal Area Designation", window_x, window_y)
    
    # Set window property to allow resizing (already done with WINDOW_NORMAL)
    # Note: WND_PROP_ASPECT_RATIO might not be available in all OpenCV versions
    try:
        cv2.setWindowProperty("Goal Area Designation", cv2.WND_PROP_ASPECT_RATIO, cv2.WINDOW_KEEPRATIO)
    except:
        pass  # Property not available in this OpenCV version
    
    cv2.setMouseCallback("Goal Area Designation", mouse_callback)
    
    # Initial display - show full frame
    cv2.imshow("Goal Area Designation", display_frame)
    
    while True:
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q') or key == 27:  # ESC
            designator.cleanup()
            cv2.destroyAllWindows()
            return None
        
        elif key == ord('s'):
            # Save
            if designator.goal_areas:
                output_path = designator.save_goal_areas()
                print(f"\n✓ Saved {len(designator.goal_areas)} goal areas to: {output_path}")
                designator.cleanup()
                cv2.destroyAllWindows()
                return designator
            else:
                print("\n⚠ No goal areas defined. Nothing to save.")
        
        elif key == ord('r'):
            designator.designation_mode = 'rectangle'
            print("Mode: Rectangle (2 points)")
        
        elif key == ord('p'):
            designator.designation_mode = 'polygon'
            print("Mode: Polygon (multiple points)")
        
        elif key == ord('c'):
            designator.goal_areas = {}
            current_goal_name = None
            current_points = []
            goal_counter = 1
            display_frame = frame.copy()
            cv2.imshow("Goal Area Designation", display_frame)
            print("Cleared all goals")
    
    designator.cleanup()
    cv2.destroyAllWindows()
    return None

