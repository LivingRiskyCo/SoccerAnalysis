"""
Post-processing event detection from CSV tracking data.
Works with existing tracking data - no need for perfect video.
Detects passes, shots, and other events with confidence scores.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import deque
import os

@dataclass
class DetectedEvent:
    """Represents a detected game event"""
    event_type: str  # "pass", "shot", "tackle", etc.
    frame_num: int
    timestamp: float  # seconds from video start
    confidence: float  # 0.0 to 1.0 - how reliable is this detection
    player_id: Optional[int] = None
    player_name: Optional[str] = None
    team: Optional[str] = None
    start_pos: Optional[Tuple[float, float]] = None
    end_pos: Optional[Tuple[float, float]] = None
    metadata: Optional[Dict] = None

class EventDetector:
    def __init__(self, csv_path: str, fps: float = 30.0):
        """
        Initialize event detector from CSV tracking data.
        
        Args:
            csv_path: Path to tracking CSV file
            fps: Video frame rate (will try to detect from CSV if not provided)
        """
        self.csv_path = csv_path
        self.fps = fps
        self.df = None
        self.events: List[DetectedEvent] = []
        self.frame_width = None
        self.frame_height = None
        
    def load_tracking_data(self):
        """Load tracking data from CSV"""
        try:
            # Read CSV, skipping comment lines
            self.df = pd.read_csv(self.csv_path, comment='#')
            
            # Try to extract FPS from comment lines if available
            try:
                with open(self.csv_path, 'r') as f:
                    for line in f:
                        if line.startswith('# Video FPS:'):
                            fps_str = line.split(':')[1].strip()
                            self.fps = float(fps_str)
                            break
            except:
                pass
            
            # Try to extract resolution from comment lines
            try:
                with open(self.csv_path, 'r') as f:
                    for line in f:
                        if line.startswith('# Video Resolution:'):
                            res_str = line.split(':')[1].strip()
                            if 'x' in res_str:
                                w, h = res_str.split('x')
                                self.frame_width = int(w.strip())
                                self.frame_height = int(h.strip())
                            break
            except:
                pass
            
            print(f"✓ Loaded {len(self.df)} rows of tracking data")
            print(f"  → FPS: {self.fps:.2f}")
            if self.frame_width and self.frame_height:
                print(f"  → Resolution: {self.frame_width}x{self.frame_height}")
            
            # Check required columns
            required_cols = ['frame', 'ball_x', 'ball_y']
            missing = [col for col in required_cols if col not in self.df.columns]
            if missing:
                print(f"⚠ Missing required columns: {missing}")
                return False
            
            return True
        except Exception as e:
            print(f"✗ Error loading CSV: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_ball_positions(self) -> List[Tuple[int, float, float]]:
        """Get list of (frame, x, y) ball positions"""
        ball_positions = []
        for idx, row in self.df.iterrows():
            frame = int(row['frame'])
            ball_x = row.get('ball_x')
            ball_y = row.get('ball_y')
            
            if pd.notna(ball_x) and pd.notna(ball_y):
                ball_positions.append((frame, float(ball_x), float(ball_y)))
        
        return ball_positions
    
    def _get_player_positions_by_frame(self, frame_num: int) -> Dict[int, Dict]:
        """Get all player positions for a specific frame"""
        frame_data = self.df[self.df['frame'] == frame_num]
        players = {}
        
        for idx, row in frame_data.iterrows():
            player_id = row.get('player_id')
            if pd.isna(player_id):
                continue
            
            player_id = int(player_id)
            player_x = row.get('player_x')
            player_y = row.get('player_y')
            player_name = row.get('player_name')
            team = row.get('team')
            
            if pd.notna(player_x) and pd.notna(player_y):
                players[player_id] = {
                    'x': float(player_x),
                    'y': float(player_y),
                    'name': player_name if pd.notna(player_name) else None,
                    'team': team if pd.notna(team) else None
                }
        
        return players
    
    def _find_possession_windows(self, possession_threshold: float = 1.5) -> List[Dict]:
        """
        Find time windows where ball is in possession of a player.
        Returns list of dicts with player_id, start_frame, end_frame, positions.
        """
        windows = []
        current_window = None
        
        # Get unique frames
        unique_frames = sorted(self.df['frame'].unique())
        
        for frame_num in unique_frames:
            # Get ball position
            ball_row = self.df[self.df['frame'] == frame_num].iloc[0] if len(self.df[self.df['frame'] == frame_num]) > 0 else None
            if ball_row is None:
                if current_window:
                    windows.append(current_window)
                    current_window = None
                continue
            
            ball_x = ball_row.get('ball_x')
            ball_y = ball_row.get('ball_y')
            
            if pd.isna(ball_x) or pd.isna(ball_y):
                if current_window:
                    windows.append(current_window)
                    current_window = None
                continue
            
            # Find closest player
            players = self._get_player_positions_by_frame(frame_num)
            closest_player = None
            min_dist = float('inf')
            
            # Calculate distance in pixels (assuming coordinates are in pixels)
            # If normalized, we'd need to multiply by frame dimensions
            for player_id, player_data in players.items():
                dx = ball_x - player_data['x']
                dy = ball_y - player_data['y']
                dist = np.sqrt(dx**2 + dy**2)
                
                # Normalize distance if we have frame dimensions
                if self.frame_width and self.frame_height:
                    # Normalize to percentage of frame diagonal
                    frame_diagonal = np.sqrt(self.frame_width**2 + self.frame_height**2)
                    dist_normalized = dist / frame_diagonal
                    # Convert to approximate meters (assuming ~100m field diagonal in frame)
                    # This is approximate - would need field calibration for accuracy
                    dist_meters = dist_normalized * 100.0
                else:
                    # Fallback: assume ~100 pixels = 1 meter (rough estimate)
                    dist_meters = dist / 100.0
                
                if dist_meters < possession_threshold and dist < min_dist:
                    min_dist = dist
                    closest_player = {
                        'player_id': player_id,
                        'player_name': player_data['name'],
                        'team': player_data['team'],
                        'x': player_data['x'],
                        'y': player_data['y'],
                        'distance': dist_meters
                    }
            
            # Check if we have a possession window
            if closest_player:
                if current_window is None:
                    # Start new window
                    current_window = {
                        'player_id': closest_player['player_id'],
                        'player_name': closest_player['player_name'],
                        'team': closest_player['team'],
                        'start_frame': frame_num,
                        'start_x': closest_player['x'],
                        'start_y': closest_player['y'],
                        'end_frame': frame_num,
                        'end_x': closest_player['x'],
                        'end_y': closest_player['y'],
                        'frames': 1
                    }
                elif current_window['player_id'] == closest_player['player_id']:
                    # Extend current window
                    current_window['end_frame'] = frame_num
                    current_window['end_x'] = closest_player['x']
                    current_window['end_y'] = closest_player['y']
                    current_window['frames'] += 1
                else:
                    # Different player - close current window and start new
                    if current_window['frames'] >= 3:  # Only keep windows with at least 3 frames
                        windows.append(current_window)
                    current_window = {
                        'player_id': closest_player['player_id'],
                        'player_name': closest_player['player_name'],
                        'team': closest_player['team'],
                        'start_frame': frame_num,
                        'start_x': closest_player['x'],
                        'start_y': closest_player['y'],
                        'end_frame': frame_num,
                        'end_x': closest_player['x'],
                        'end_y': closest_player['y'],
                        'frames': 1
                    }
            else:
                # No possession - close window if open
                if current_window and current_window['frames'] >= 3:
                    windows.append(current_window)
                current_window = None
        
        if current_window and current_window['frames'] >= 3:
            windows.append(current_window)
        
        return windows
    
    def _calculate_ball_speeds(self, start_frame: int, end_frame: int) -> List[float]:
        """Calculate ball speeds for frames between start and end"""
        speeds = []
        prev_pos = None
        
        for frame in range(start_frame, end_frame + 1):
            frame_data = self.df[self.df['frame'] == frame]
            if len(frame_data) == 0:
                continue
            
            row = frame_data.iloc[0]
            ball_x = row.get('ball_x')
            ball_y = row.get('ball_y')
            
            if pd.isna(ball_x) or pd.isna(ball_y):
                continue
            
            if prev_pos:
                dx = ball_x - prev_pos[0]
                dy = ball_y - prev_pos[1]
                dt = 1.0 / self.fps if self.fps > 0 else 1.0 / 30.0
                
                # Calculate distance in pixels
                dist_pixels = np.sqrt(dx**2 + dy**2)
                
                # Convert to approximate m/s
                # Rough estimate: if frame is 3840x2160 and field is ~100m, then ~38 pixels/meter
                if self.frame_width:
                    pixels_per_meter = self.frame_width / 100.0  # Rough estimate
                else:
                    pixels_per_meter = 38.0  # Default estimate
                
                speed_mps = (dist_pixels / pixels_per_meter) / dt
                speeds.append(speed_mps)
            
            prev_pos = (ball_x, ball_y)
        
        return speeds
    
    def _calculate_pass_confidence(self, window1: Dict, window2: Dict, 
                                   ball_speeds: List[float], 
                                   pass_distance: float, 
                                   time_gap: float) -> float:
        """
        Calculate confidence score for pass detection (0.0 to 1.0).
        Higher = more reliable detection.
        """
        confidence = 0.5  # Base confidence
        
        # Factor 1: Ball speed (faster = more confident it's a pass)
        if ball_speeds:
            max_speed = max(ball_speeds)
            # Normalize: 10 m/s = high confidence
            speed_confidence = min(max_speed / 10.0, 1.0)
            confidence += speed_confidence * 0.2
        
        # Factor 2: Pass distance (longer = more confident, but not too long)
        # Ideal pass: 5-20 meters
        if pass_distance < 3.0:
            distance_confidence = pass_distance / 3.0  # Too short
        elif pass_distance > 30.0:
            distance_confidence = max(0, 1.0 - (pass_distance - 30.0) / 20.0)  # Too long
        else:
            distance_confidence = 1.0  # Good range
        
        confidence += distance_confidence * 0.15
        
        # Factor 3: Time gap (shorter = more confident)
        time_confidence = max(0, 1.0 - (time_gap / 2.0))  # Prefer < 2 seconds
        confidence += time_confidence * 0.15
        
        # Factor 4: Possession duration (longer possession = more confident)
        window1_duration = window1['frames'] / self.fps if self.fps > 0 else window1['frames'] / 30.0
        window2_duration = window2['frames'] / self.fps if self.fps > 0 else window2['frames'] / 30.0
        possession_confidence = min((window1_duration + window2_duration) / 1.0, 1.0)
        confidence += possession_confidence * 0.1
        
        return min(confidence, 1.0)
    
    def detect_passes(self, 
                     min_ball_speed: float = 3.0,  # m/s
                     max_pass_duration: float = 2.0,  # seconds
                     min_player_distance: float = 2.0,  # meters
                     possession_threshold: float = 1.5,  # meters - ball within this distance = possession
                     min_pass_distance: float = 5.0,  # meters - minimum pass length
                     confidence_threshold: float = 0.5):  # Minimum confidence to include
        """
        Detect passes by analyzing ball movement and player proximity.
        
        Tolerant of imperfect tracking:
        - Uses ball speed (works even if player tracking is spotty)
        - Uses possession windows (ball near player)
        - Filters out noise with multiple thresholds
        """
        if self.df is None:
            return []
        
        print("\n=== Detecting Passes ===")
        print(f"  Parameters:")
        print(f"    Min ball speed: {min_ball_speed} m/s")
        print(f"    Max pass duration: {max_pass_duration} s")
        print(f"    Min pass distance: {min_pass_distance} m")
        print(f"    Possession threshold: {possession_threshold} m")
        print(f"    Confidence threshold: {confidence_threshold}")
        
        passes = []
        
        # Find possession windows
        print("  Finding possession windows...")
        possession_windows = self._find_possession_windows(possession_threshold)
        print(f"    Found {len(possession_windows)} possession windows")
        
        if len(possession_windows) < 2:
            print("  ⚠ Not enough possession windows for pass detection")
            return []
        
        # Detect passes between possession windows
        print("  Analyzing pass candidates...")
        for i in range(len(possession_windows) - 1):
            window1 = possession_windows[i]
            window2 = possession_windows[i + 1]
            
            # Check if different players
            if window1['player_id'] == window2['player_id']:
                continue
            
            # Check time gap (pass duration)
            time_gap = (window2['start_frame'] - window1['end_frame']) / self.fps if self.fps > 0 else (window2['start_frame'] - window1['end_frame']) / 30.0
            if time_gap > max_pass_duration:
                continue
            
            # Check ball speed during pass
            pass_start_frame = window1['end_frame']
            pass_end_frame = window2['start_frame']
            ball_speeds = self._calculate_ball_speeds(pass_start_frame, pass_end_frame)
            
            if len(ball_speeds) == 0:
                continue
            
            max_ball_speed = max(ball_speeds)
            if max_ball_speed < min_ball_speed:
                continue
            
            # Calculate pass distance
            start_pos = (window1['end_x'], window1['end_y'])
            end_pos = (window2['start_x'], window2['start_y'])
            
            # Convert pixel distance to meters
            dx = end_pos[0] - start_pos[0]
            dy = end_pos[1] - start_pos[1]
            dist_pixels = np.sqrt(dx**2 + dy**2)
            
            if self.frame_width:
                pixels_per_meter = self.frame_width / 100.0  # Rough estimate
            else:
                pixels_per_meter = 38.0  # Default estimate
            
            pass_distance = dist_pixels / pixels_per_meter
            
            if pass_distance < min_pass_distance:
                continue
            
            # Calculate confidence
            confidence = self._calculate_pass_confidence(
                window1, window2, ball_speeds, pass_distance, time_gap
            )
            
            # Only include high-confidence passes
            if confidence >= confidence_threshold:
                pass_event = DetectedEvent(
                    event_type="pass",
                    frame_num=window1['end_frame'],
                    timestamp=window1['end_frame'] / self.fps if self.fps > 0 else window1['end_frame'] / 30.0,
                    confidence=confidence,
                    player_id=window1['player_id'],
                    player_name=window1.get('player_name'),
                    team=window1.get('team'),
                    start_pos=start_pos,
                    end_pos=end_pos,
                    metadata={
                        'receiver_id': window2['player_id'],
                        'receiver_name': window2.get('player_name'),
                        'pass_distance_m': pass_distance,
                        'pass_duration_s': time_gap,
                        'max_ball_speed_mps': max_ball_speed,
                        'avg_ball_speed_mps': np.mean(ball_speeds) if ball_speeds else 0
                    }
                )
                passes.append(pass_event)
        
        print(f"  ✓ Detected {len(passes)} passes (confidence >= {confidence_threshold})")
        return passes
    
    def detect_shots(self,
                    goal_area_x: Optional[Tuple[float, float]] = None,  # Normalized goal area (0-1)
                    goal_area_y: Optional[Tuple[float, float]] = None,
                    goal_areas_json: Optional[str] = None,  # Path to goal areas JSON file
                    min_ball_speed: float = 8.0,  # m/s - fast movement toward goal
                    min_approach_distance: float = 10.0,  # meters
                    confidence_threshold: float = 0.5):
        """
        Detect shots by analyzing ball movement toward goal area.
        Works even with imperfect tracking - uses ball trajectory.
        
        Args:
            goal_area_x: Normalized X range for goal area (default: 0.4-0.6)
            goal_area_y: Normalized Y range for goal area (default: 0.0-0.1)
            goal_areas_json: Path to goal areas JSON file (overrides goal_area_x/y if provided)
            min_ball_speed: Minimum ball speed in m/s
            min_approach_distance: Minimum approach distance in meters
            confidence_threshold: Minimum confidence to include
        """
        if self.df is None:
            return []
        
        print("\n=== Detecting Shots ===")
        
        # Load goal areas from JSON if provided
        goal_areas = []
        if goal_areas_json and os.path.exists(goal_areas_json):
            try:
                from goal_area_designator import GoalAreaDesignator
                designator = GoalAreaDesignator("")  # Dummy path, we just need the loader
                if designator.load_goal_areas(goal_areas_json):
                    for goal_name, goal_data in designator.goal_areas.items():
                        bounds = designator.get_goal_area_bounds(goal_name)
                        if bounds:
                            goal_areas.append({
                                'name': goal_name,
                                'bounds': bounds,
                                'points': goal_data['points']
                            })
                    print(f"  Loaded {len(goal_areas)} goal areas from {goal_areas_json}")
            except Exception as e:
                print(f"  ⚠ Error loading goal areas: {e}")
        
        # Use default goal area if no JSON provided
        if not goal_areas:
            if goal_area_x is None:
                goal_area_x = (0.4, 0.6)
            if goal_area_y is None:
                goal_area_y = (0.0, 0.1)
            goal_areas.append({
                'name': 'default_goal',
                'bounds': (goal_area_x[0], goal_area_y[0], goal_area_x[1], goal_area_y[1]),
                'points': None
            })
        
        print(f"  Parameters:")
        print(f"    Goal areas: {len(goal_areas)}")
        for goal in goal_areas:
            print(f"      {goal['name']}: {goal['bounds']}")
        print(f"    Min ball speed: {min_ball_speed} m/s")
        print(f"    Min approach distance: {min_approach_distance} m")
        
        shots = []
        ball_positions = self._get_ball_positions()
        
        if len(ball_positions) < 10:
            print("  ⚠ Insufficient ball tracking data for shot detection")
            return []
        
        # Convert normalized goal areas to pixel coordinates
        goal_pixel_areas = []
        for goal in goal_areas:
            bounds = goal['bounds']
            if self.frame_width and self.frame_height:
                goal_x1 = bounds[0] * self.frame_width
                goal_x2 = bounds[2] * self.frame_width
                goal_y1 = bounds[1] * self.frame_height
                goal_y2 = bounds[3] * self.frame_height
            else:
                goal_x1 = bounds[0]
                goal_x2 = bounds[2]
                goal_y1 = bounds[1]
                goal_y2 = bounds[3]
            
            goal_pixel_areas.append({
                'name': goal['name'],
                'x1': goal_x1,
                'y1': goal_y1,
                'x2': goal_x2,
                'y2': goal_y2,
                'points': goal.get('points')
            })
        
        # Look for ball moving fast toward goal
        for i in range(len(ball_positions) - 5):
            frame, ball_x, ball_y = ball_positions[i]
            
            # Check if ball is in any goal area
            ball_in_goal = False
            current_goal = None
            for goal_area in goal_pixel_areas:
                # Simple rectangle check
                if goal_area['x1'] <= ball_x <= goal_area['x2'] and goal_area['y1'] <= ball_y <= goal_area['y2']:
                    # If we have polygon points, do point-in-polygon test
                    if goal_area.get('points'):
                        from goal_area_designator import GoalAreaDesignator
                        designator = GoalAreaDesignator("")
                        designator.goal_areas[goal_area['name']] = {
                            'type': 'polygon',
                            'points': goal_area['points']
                        }
                        if designator.is_point_in_goal(ball_x, ball_y, goal_area['name']):
                            ball_in_goal = True
                            current_goal = goal_area
                            break
                    else:
                        ball_in_goal = True
                        current_goal = goal_area
                        break
            
            if ball_in_goal and current_goal:
                # Look back to find approach
                approach_start_idx = max(0, i - 30)  # Look back ~1 second
                approach_frames = ball_positions[approach_start_idx:i+1]
                
                if len(approach_frames) < 5:
                    continue
                
                # Calculate approach speed
                start_frame, start_x, start_y = approach_frames[0]
                end_frame, end_x, end_y = approach_frames[-1]
                
                dx = end_x - start_x
                dy = end_y - start_y
                dt = (end_frame - start_frame) / self.fps if self.fps > 0 else (end_frame - start_frame) / 30.0
                
                if dt <= 0:
                    continue
                
                # Convert to meters
                if self.frame_width:
                    pixels_per_meter = self.frame_width / 100.0
                else:
                    pixels_per_meter = 38.0
                
                dist_pixels = np.sqrt(dx**2 + dy**2)
                dist_meters = dist_pixels / pixels_per_meter
                speed_mps = dist_meters / dt
                
                # Check if approaching goal (moving toward goal area)
                # Simple check: ball should be moving in direction of goal
                if speed_mps >= min_ball_speed and dist_meters >= min_approach_distance:
                    # Find closest player (likely shooter)
                    players = self._get_player_positions_by_frame(frame)
                    closest_player = None
                    min_dist = float('inf')
                    
                    for player_id, player_data in players.items():
                        dx_player = ball_x - player_data['x']
                        dy_player = ball_y - player_data['y']
                        dist = np.sqrt(dx_player**2 + dy_player**2)
                        if dist < min_dist:
                            min_dist = dist
                            closest_player = {
                                'player_id': player_id,
                                'player_name': player_data['name'],
                                'team': player_data['team']
                            }
                    
                    # Calculate confidence
                    confidence = min(speed_mps / 15.0, 1.0)  # 15 m/s = high confidence
                    
                    if confidence >= confidence_threshold:
                        shot_event = DetectedEvent(
                            event_type="shot",
                            frame_num=frame,
                            timestamp=frame / self.fps if self.fps > 0 else frame / 30.0,
                            confidence=confidence,
                            player_id=closest_player['player_id'] if closest_player else None,
                            player_name=closest_player['player_name'] if closest_player else None,
                            team=closest_player['team'] if closest_player else None,
                            start_pos=(start_x, start_y),
                            end_pos=(ball_x, ball_y),
                            metadata={
                                'ball_speed_mps': speed_mps,
                                'approach_distance_m': dist_meters,
                                'goal_area': current_goal['name'],
                                'goal_bounds': (current_goal['x1'], current_goal['y1'], current_goal['x2'], current_goal['y2'])
                            }
                        )
                        shots.append(shot_event)
        
        print(f"  ✓ Detected {len(shots)} shots (confidence >= {confidence_threshold})")
        return shots
    
    def detect_goals(self,
                    goal_areas_json: Optional[str] = None,
                    min_ball_speed: float = 5.0,  # m/s - ball must be moving
                    goal_crossing_frames: int = 5,  # Frames ball must be in goal to count
                    confidence_threshold: float = 0.7):
        """
        Detect goals by tracking when ball crosses goal boundary and stays in goal area.
        
        Args:
            goal_areas_json: Path to goal areas JSON file (required)
            min_ball_speed: Minimum ball speed when entering goal (m/s)
            goal_crossing_frames: Number of consecutive frames ball must be in goal
            confidence_threshold: Minimum confidence to include
        
        Returns:
            List of DetectedEvent objects with event_type="goal"
        """
        if self.df is None:
            return []
        
        print("\n=== Detecting Goals ===")
        
        # Load goal areas
        goal_areas = []
        if goal_areas_json and os.path.exists(goal_areas_json):
            try:
                from goal_area_designator import GoalAreaDesignator
                designator = GoalAreaDesignator("")
                if designator.load_goal_areas(goal_areas_json):
                    for goal_name, goal_data in designator.goal_areas.items():
                        bounds = designator.get_goal_area_bounds(goal_name)
                        if bounds:
                            goal_areas.append({
                                'name': goal_name,
                                'bounds': bounds,
                                'points': goal_data['points'],
                                'type': goal_data.get('type', 'rectangle')
                            })
                    print(f"  Loaded {len(goal_areas)} goal areas from {goal_areas_json}")
            except Exception as e:
                print(f"  ⚠ Error loading goal areas: {e}")
        
        if not goal_areas:
            print("  ⚠ No goal areas defined. Please designate goal areas first.")
            return []
        
        print(f"  Parameters:")
        print(f"    Goal areas: {len(goal_areas)}")
        print(f"    Min ball speed: {min_ball_speed} m/s")
        print(f"    Goal crossing frames: {goal_crossing_frames}")
        
        goals = []
        ball_positions = self._get_ball_positions()
        
        if len(ball_positions) < goal_crossing_frames:
            print("  ⚠ Insufficient ball tracking data for goal detection")
            return []
        
        # Convert to pixel coordinates
        goal_pixel_areas = []
        for goal in goal_areas:
            bounds = goal['bounds']
            if self.frame_width and self.frame_height:
                goal_x1 = bounds[0] * self.frame_width
                goal_x2 = bounds[2] * self.frame_width
                goal_y1 = bounds[1] * self.frame_height
                goal_y2 = bounds[3] * self.frame_height
            else:
                goal_x1 = bounds[0]
                goal_x2 = bounds[2]
                goal_y1 = bounds[1]
                goal_y2 = bounds[3]
            
            goal_pixel_areas.append({
                'name': goal['name'],
                'x1': goal_x1,
                'y1': goal_y1,
                'x2': goal_x2,
                'y2': goal_y2,
                'points': goal.get('points'),
                'type': goal.get('type', 'rectangle')
            })
        
        # Track ball crossing goal boundaries
        prev_in_goal = {goal['name']: False for goal in goal_pixel_areas}
        goal_sequence = {goal['name']: [] for goal in goal_pixel_areas}  # Track consecutive frames in goal
        
        for i in range(len(ball_positions)):
            frame, ball_x, ball_y = ball_positions[i]
            
            # Check which goal (if any) the ball is in
            current_in_goal = {}
            for goal_area in goal_pixel_areas:
                in_goal = False
                
                # Check if point is in goal area
                if goal_area.get('points') and goal_area['type'] == 'polygon':
                    # Point-in-polygon test
                    from goal_area_designator import GoalAreaDesignator
                    designator = GoalAreaDesignator("")
                    designator.goal_areas[goal_area['name']] = {
                        'type': 'polygon',
                        'points': goal_area['points']
                    }
                    in_goal = designator.is_point_in_goal(ball_x, ball_y, goal_area['name'])
                else:
                    # Rectangle check
                    in_goal = (goal_area['x1'] <= ball_x <= goal_area['x2'] and 
                              goal_area['y1'] <= ball_y <= goal_area['y2'])
                
                current_in_goal[goal_area['name']] = in_goal
                
                # Track consecutive frames in goal
                if in_goal:
                    goal_sequence[goal_area['name']].append((frame, ball_x, ball_y))
                else:
                    # Ball left goal - check if we had enough consecutive frames
                    if len(goal_sequence[goal_area['name']]) >= goal_crossing_frames:
                        # Potential goal - check if ball was moving when it entered
                        entry_frame, entry_x, entry_y = goal_sequence[goal_area['name']][0]
                        
                        # Find previous position (before entering goal)
                        prev_pos = None
                        for j in range(i - 1, -1, -1):
                            prev_frame, prev_x, prev_y = ball_positions[j]
                            if prev_frame < entry_frame:
                                prev_pos = (prev_x, prev_y)
                                break
                        
                        if prev_pos:
                            # Calculate entry speed
                            dx = entry_x - prev_pos[0]
                            dy = entry_y - prev_pos[1]
                            dt = 1.0 / self.fps if self.fps > 0 else 1.0 / 30.0
                            
                            if self.frame_width:
                                pixels_per_meter = self.frame_width / 100.0
                            else:
                                pixels_per_meter = 38.0
                            
                            dist_pixels = np.sqrt(dx**2 + dy**2)
                            dist_meters = dist_pixels / pixels_per_meter
                            speed_mps = dist_meters / dt if dt > 0 else 0
                            
                            if speed_mps >= min_ball_speed:
                                # Find closest player (scorer)
                                players = self._get_player_positions_by_frame(entry_frame)
                                closest_player = None
                                min_dist = float('inf')
                                
                                for player_id, player_data in players.items():
                                    dx_player = entry_x - player_data['x']
                                    dy_player = entry_y - player_data['y']
                                    dist = np.sqrt(dx_player**2 + dy_player**2)
                                    if dist < min_dist:
                                        min_dist = dist
                                        closest_player = {
                                            'player_id': player_id,
                                            'player_name': player_data['name'],
                                            'team': player_data['team']
                                        }
                                
                                # Calculate confidence based on speed and time in goal
                                time_in_goal = len(goal_sequence[goal_area['name']]) / self.fps if self.fps > 0 else len(goal_sequence[goal_area['name']]) / 30.0
                                speed_confidence = min(speed_mps / 10.0, 1.0)
                                time_confidence = min(time_in_goal / 0.5, 1.0)  # 0.5s in goal = high confidence
                                confidence = (speed_confidence * 0.6 + time_confidence * 0.4)
                                
                                if confidence >= confidence_threshold:
                                    goal_event = DetectedEvent(
                                        event_type="goal",
                                        frame_num=entry_frame,
                                        timestamp=entry_frame / self.fps if self.fps > 0 else entry_frame / 30.0,
                                        confidence=confidence,
                                        player_id=closest_player['player_id'] if closest_player else None,
                                        player_name=closest_player['player_name'] if closest_player else None,
                                        team=closest_player['team'] if closest_player else None,
                                        start_pos=prev_pos,
                                        end_pos=(entry_x, entry_y),
                                        metadata={
                                            'goal_area': goal_area['name'],
                                            'ball_speed_mps': speed_mps,
                                            'time_in_goal_s': time_in_goal,
                                            'frames_in_goal': len(goal_sequence[goal_area['name']])
                                        }
                                    )
                                    goals.append(goal_event)
                    
                    # Reset sequence
                    goal_sequence[goal_area['name']] = []
            
            prev_in_goal = current_in_goal
        
        # Check for goals that are still in progress at end of video
        for goal_area in goal_pixel_areas:
            if len(goal_sequence[goal_area['name']]) >= goal_crossing_frames:
                entry_frame, entry_x, entry_y = goal_sequence[goal_area['name']][0]
                # Similar logic as above...
                # (Could add this if needed, but usually goals are detected when ball exits)
        
        print(f"  ✓ Detected {len(goals)} goals (confidence >= {confidence_threshold})")
        return goals
    
    def detect_zone_occupancy(self, 
                             zones: Dict[str, Tuple[float, float, float, float]]):
        """
        Calculate time spent in each zone per player.
        Zones are defined as (min_x, min_y, max_x, max_y) in normalized coordinates (0-1).
        
        Example zones:
        zones = {
            'defensive_third': (0.0, 0.0, 1.0, 0.33),
            'midfield': (0.0, 0.33, 1.0, 0.67),
            'attacking_third': (0.0, 0.67, 1.0, 1.0)
        }
        """
        if self.df is None:
            return {}
        
        print("\n=== Analyzing Zone Occupancy ===")
        
        # Convert normalized zones to pixel coordinates if we have frame dimensions
        pixel_zones = {}
        for zone_name, (min_x, min_y, max_x, max_y) in zones.items():
            if self.frame_width and self.frame_height:
                pixel_zones[zone_name] = (
                    min_x * self.frame_width,
                    min_y * self.frame_height,
                    max_x * self.frame_width,
                    max_y * self.frame_height
                )
            else:
                # Assume coordinates are already in pixels or normalized
                pixel_zones[zone_name] = (min_x, min_y, max_x, max_y)
        
        zone_stats = {}
        unique_frames = sorted(self.df['frame'].unique())
        
        for frame_num in unique_frames:
            timestamp = frame_num / self.fps if self.fps > 0 else frame_num / 30.0
            players = self._get_player_positions_by_frame(frame_num)
            
            for player_id, player_data in players.items():
                player_x = player_data['x']
                player_y = player_data['y']
                
                # Determine which zone player is in
                for zone_name, (min_x, min_y, max_x, max_y) in pixel_zones.items():
                    if min_x <= player_x <= max_x and min_y <= player_y <= max_y:
                        key = f"{player_id}_{zone_name}"
                        if key not in zone_stats:
                            zone_stats[key] = {
                                'player_id': player_id,
                                'player_name': player_data['name'],
                                'team': player_data['team'],
                                'zone': zone_name,
                                'time': 0.0,
                                'frames': 0
                            }
                        zone_stats[key]['time'] += 1.0 / self.fps if self.fps > 0 else 1.0 / 30.0
                        zone_stats[key]['frames'] += 1
                        break
        
        print(f"  ✓ Analyzed {len(unique_frames)} frames")
        print(f"  ✓ Found {len(zone_stats)} player-zone combinations")
        
        return zone_stats
    
    def export_events(self, output_path: str):
        """Export detected events to CSV"""
        if not self.events:
            print("No events to export")
            return
        
        events_data = []
        for event in self.events:
            events_data.append({
                'event_type': event.event_type,
                'frame_num': event.frame_num,
                'timestamp': event.timestamp,
                'confidence': event.confidence,
                'player_id': event.player_id,
                'player_name': event.player_name,
                'team': event.team,
                'start_x': event.start_pos[0] if event.start_pos else None,
                'start_y': event.start_pos[1] if event.start_pos else None,
                'end_x': event.end_pos[0] if event.end_pos else None,
                'end_y': event.end_pos[1] if event.end_pos else None,
                'metadata': str(event.metadata) if event.metadata else ''
            })
        
        df_events = pd.DataFrame(events_data)
        df_events.to_csv(output_path, index=False)
        print(f"✓ Exported {len(self.events)} events to {output_path}")
    
    def detect_passes_with_accuracy(self,
                     min_ball_speed: float = 3.0,
                     max_pass_duration: float = 2.0,
                     min_player_distance: float = 2.0,
                     possession_threshold: float = 1.5,
                     min_pass_distance: float = 5.0,
                     confidence_threshold: float = 0.5,
                     incomplete_timeout: float = 3.0):  # seconds before considering pass incomplete
        """
        Enhanced pass detection with accuracy tracking.
        Returns successful passes, incomplete passes, and statistics.
        """
        if self.df is None:
            return {
                'successful_passes': [],
                'incomplete_passes': [],
                'player_statistics': {},
                'accuracy_metrics': {}
            }
        
        print("\n=== Detecting Passes with Accuracy ===")
        
        # Get all passes (successful ones)
        successful_passes = self.detect_passes(
            min_ball_speed=min_ball_speed,
            max_pass_duration=max_pass_duration,
            min_player_distance=min_player_distance,
            possession_threshold=possession_threshold,
            min_pass_distance=min_pass_distance,
            confidence_threshold=confidence_threshold
        )
        
        # Detect incomplete passes
        incomplete_passes = self._detect_incomplete_passes(
            successful_passes,
            possession_threshold=possession_threshold,
            incomplete_timeout=incomplete_timeout,
            min_ball_speed=min_ball_speed
        )
        
        # Calculate player statistics
        player_stats = self._calculate_player_pass_stats(successful_passes, incomplete_passes)
        
        # Calculate accuracy metrics
        accuracy_metrics = self._calculate_pass_accuracy(successful_passes, incomplete_passes, player_stats)
        
        return {
            'successful_passes': successful_passes,
            'incomplete_passes': incomplete_passes,
            'player_statistics': player_stats,
            'accuracy_metrics': accuracy_metrics
        }
    
    def _detect_incomplete_passes(self, successful_passes: List[DetectedEvent],
                                  possession_threshold: float = 1.5,
                                  incomplete_timeout: float = 3.0,
                                  min_ball_speed: float = 3.0) -> List[DetectedEvent]:
        """
        Detect incomplete passes:
        - Pass attempts that don't result in successful possession transfer
        - Interceptions
        - Turnovers
        - Out of bounds
        """
        if self.df is None:
            return []
        
        print("  Detecting incomplete passes...")
        incomplete = []
        
        # Get possession windows
        possession_windows = self._find_possession_windows(possession_threshold)
        
        # Track successful pass end frames to avoid duplicates
        successful_end_frames = {p.frame_num for p in successful_passes}
        
        # Look for possession windows that end but don't lead to another possession
        for i, window in enumerate(possession_windows):
            # Skip if this window is part of a successful pass
            if window['end_frame'] in successful_end_frames:
                continue
            
            # Check if there's a gap after this window without possession
            next_window = None
            if i + 1 < len(possession_windows):
                next_window = possession_windows[i + 1]
            
            if next_window:
                time_gap = (next_window['start_frame'] - window['end_frame']) / self.fps if self.fps > 0 else (next_window['start_frame'] - window['end_frame']) / 30.0
                
                # If gap is too long, or if next possession is different team, mark as incomplete
                if time_gap > incomplete_timeout:
                    # Check ball movement during gap
                    ball_speeds = self._calculate_ball_speeds(window['end_frame'], next_window['start_frame'])
                    if ball_speeds and max(ball_speeds) >= min_ball_speed:
                        # Ball moved fast but didn't reach intended target - incomplete pass
                        incomplete.append(DetectedEvent(
                            event_type="incomplete_pass",
                            frame_num=window['end_frame'],
                            timestamp=window['end_frame'] / self.fps if self.fps > 0 else window['end_frame'] / 30.0,
                            confidence=0.6,  # Lower confidence for incomplete detection
                            player_id=window['player_id'],
                            player_name=window.get('player_name'),
                            team=window.get('team'),
                            start_pos=(window['end_x'], window['end_y']),
                            end_pos=None,  # Unknown end position
                            metadata={
                                'reason': 'timeout',
                                'timeout_duration_s': time_gap,
                                'max_ball_speed_mps': max(ball_speeds) if ball_speeds else 0
                            }
                        ))
                elif window.get('team') and next_window.get('team') and window['team'] != next_window['team']:
                    # Possession changed to different team - interception
                    incomplete.append(DetectedEvent(
                        event_type="interception",
                        frame_num=window['end_frame'],
                        timestamp=window['end_frame'] / self.fps if self.fps > 0 else window['end_frame'] / 30.0,
                        confidence=0.7,
                        player_id=window['player_id'],
                        player_name=window.get('player_name'),
                        team=window.get('team'),
                        start_pos=(window['end_x'], window['end_y']),
                        end_pos=(next_window['start_x'], next_window['start_y']),
                        metadata={
                            'reason': 'interception',
                            'intercepted_by_id': next_window['player_id'],
                            'intercepted_by_name': next_window.get('player_name'),
                            'intercepted_by_team': next_window.get('team')
                        }
                    ))
        
        print(f"    Found {len(incomplete)} incomplete passes/interceptions")
        return incomplete
    
    def _calculate_player_pass_stats(self, successful_passes: List[DetectedEvent],
                                     incomplete_passes: List[DetectedEvent]) -> Dict:
        """
        Calculate player-to-player pass statistics.
        Returns dict with player stats and pass matrix.
        """
        stats = {
            'player_stats': {},  # player_name -> {total_passes, successful, incomplete, completion_rate, etc.}
            'pass_matrix': {},   # (sender, receiver) -> count
            'team_stats': {}     # team -> {total_passes, successful, incomplete, completion_rate}
        }
        
        # Process successful passes
        for pass_event in successful_passes:
            sender = pass_event.player_name or f"Player {pass_event.player_id}"
            receiver = pass_event.metadata.get('receiver_name') if pass_event.metadata else None
            receiver = receiver or f"Player {pass_event.metadata.get('receiver_id')}" if pass_event.metadata and pass_event.metadata.get('receiver_id') else "Unknown"
            team = pass_event.team or "Unknown"
            
            # Update player stats
            if sender not in stats['player_stats']:
                stats['player_stats'][sender] = {
                    'total_passes': 0,
                    'successful_passes': 0,
                    'incomplete_passes': 0,
                    'total_received': 0,
                    'team': team
                }
            
            stats['player_stats'][sender]['total_passes'] += 1
            stats['player_stats'][sender]['successful_passes'] += 1
            
            # Update receiver stats
            if receiver not in stats['player_stats']:
                stats['player_stats'][receiver] = {
                    'total_passes': 0,
                    'successful_passes': 0,
                    'incomplete_passes': 0,
                    'total_received': 0,
                    'team': team
                }
            stats['player_stats'][receiver]['total_received'] += 1
            
            # Update pass matrix
            matrix_key = (sender, receiver)
            stats['pass_matrix'][matrix_key] = stats['pass_matrix'].get(matrix_key, 0) + 1
            
            # Update team stats
            if team not in stats['team_stats']:
                stats['team_stats'][team] = {
                    'total_passes': 0,
                    'successful_passes': 0,
                    'incomplete_passes': 0
                }
            stats['team_stats'][team]['total_passes'] += 1
            stats['team_stats'][team]['successful_passes'] += 1
        
        # Process incomplete passes
        for pass_event in incomplete_passes:
            sender = pass_event.player_name or f"Player {pass_event.player_id}"
            team = pass_event.team or "Unknown"
            
            if sender not in stats['player_stats']:
                stats['player_stats'][sender] = {
                    'total_passes': 0,
                    'successful_passes': 0,
                    'incomplete_passes': 0,
                    'total_received': 0,
                    'team': team
                }
            
            stats['player_stats'][sender]['total_passes'] += 1
            stats['player_stats'][sender]['incomplete_passes'] += 1
            
            # Update team stats
            if team not in stats['team_stats']:
                stats['team_stats'][team] = {
                    'total_passes': 0,
                    'successful_passes': 0,
                    'incomplete_passes': 0
                }
            stats['team_stats'][team]['total_passes'] += 1
            stats['team_stats'][team]['incomplete_passes'] += 1
        
        # Calculate completion rates
        for player_name, player_data in stats['player_stats'].items():
            if player_data['total_passes'] > 0:
                player_data['completion_rate'] = player_data['successful_passes'] / player_data['total_passes']
            else:
                player_data['completion_rate'] = 0.0
        
        for team_name, team_data in stats['team_stats'].items():
            if team_data['total_passes'] > 0:
                team_data['completion_rate'] = team_data['successful_passes'] / team_data['total_passes']
            else:
                team_data['completion_rate'] = 0.0
        
        return stats
    
    def _calculate_pass_accuracy(self, successful_passes: List[DetectedEvent],
                                 incomplete_passes: List[DetectedEvent],
                                 player_stats: Dict) -> Dict:
        """
        Calculate overall pass accuracy metrics.
        """
        total_passes = len(successful_passes) + len(incomplete_passes)
        successful_count = len(successful_passes)
        
        if total_passes == 0:
            return {
                'overall_completion_rate': 0.0,
                'total_passes': 0,
                'successful_passes': 0,
                'incomplete_passes': 0,
                'average_pass_distance_successful': 0.0,
                'average_pass_distance_incomplete': 0.0,
                'distance_ranges': {}
            }
        
        overall_completion_rate = successful_count / total_passes if total_passes > 0 else 0.0
        
        # Calculate average distances
        successful_distances = []
        incomplete_distances = []
        
        for pass_event in successful_passes:
            if pass_event.metadata and 'pass_distance_m' in pass_event.metadata:
                successful_distances.append(pass_event.metadata['pass_distance_m'])
        
        for pass_event in incomplete_passes:
            if pass_event.start_pos and pass_event.end_pos:
                dx = pass_event.end_pos[0] - pass_event.start_pos[0]
                dy = pass_event.end_pos[1] - pass_event.start_pos[1]
                dist_pixels = np.sqrt(dx**2 + dy**2)
                if self.frame_width:
                    pixels_per_meter = self.frame_width / 100.0
                else:
                    pixels_per_meter = 38.0
                incomplete_distances.append(dist_pixels / pixels_per_meter)
        
        avg_successful_dist = np.mean(successful_distances) if successful_distances else 0.0
        avg_incomplete_dist = np.mean(incomplete_distances) if incomplete_distances else 0.0
        
        # Calculate accuracy by distance ranges
        distance_ranges = {
            'short': {'successful': 0, 'incomplete': 0, 'total': 0},  # 0-10m
            'medium': {'successful': 0, 'incomplete': 0, 'total': 0},  # 10-20m
            'long': {'successful': 0, 'incomplete': 0, 'total': 0}    # 20m+
        }
        
        for pass_event in successful_passes:
            if pass_event.metadata and 'pass_distance_m' in pass_event.metadata:
                dist = pass_event.metadata['pass_distance_m']
                if dist < 10:
                    distance_ranges['short']['successful'] += 1
                    distance_ranges['short']['total'] += 1
                elif dist < 20:
                    distance_ranges['medium']['successful'] += 1
                    distance_ranges['medium']['total'] += 1
                else:
                    distance_ranges['long']['successful'] += 1
                    distance_ranges['long']['total'] += 1
        
        for pass_event in incomplete_passes:
            if pass_event.start_pos and pass_event.end_pos:
                dx = pass_event.end_pos[0] - pass_event.start_pos[0]
                dy = pass_event.end_pos[1] - pass_event.start_pos[1]
                dist_pixels = np.sqrt(dx**2 + dy**2)
                if self.frame_width:
                    pixels_per_meter = self.frame_width / 100.0
                else:
                    pixels_per_meter = 38.0
                dist = dist_pixels / pixels_per_meter
                
                if dist < 10:
                    distance_ranges['short']['incomplete'] += 1
                    distance_ranges['short']['total'] += 1
                elif dist < 20:
                    distance_ranges['medium']['incomplete'] += 1
                    distance_ranges['medium']['total'] += 1
                else:
                    distance_ranges['long']['incomplete'] += 1
                    distance_ranges['long']['total'] += 1
        
        # Calculate completion rates for each range
        for range_name, range_data in distance_ranges.items():
            if range_data['total'] > 0:
                range_data['completion_rate'] = range_data['successful'] / range_data['total']
            else:
                range_data['completion_rate'] = 0.0
        
        return {
            'overall_completion_rate': overall_completion_rate,
            'total_passes': total_passes,
            'successful_passes': successful_count,
            'incomplete_passes': len(incomplete_passes),
            'average_pass_distance_successful': avg_successful_dist,
            'average_pass_distance_incomplete': avg_incomplete_dist,
            'distance_ranges': distance_ranges
        }

