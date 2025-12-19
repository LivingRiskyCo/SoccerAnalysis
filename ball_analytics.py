"""
ball_analytics.py - Kinovea-style ball tracking and analytics

Features:
- Real-time trajectory visualization
- Speed/acceleration graphs
- Distance measurements
- Trajectory smoothing
- Statistical analysis
- Export capabilities
"""

import csv
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from scipy import signal
import os

@dataclass
class BallTrajectory:
    """Complete ball trajectory with analytics"""
    frames: List[int]
    positions: List[Tuple[float, float]]  # (x, y) in pixels
    positions_m: List[Tuple[float, float]]  # (x, y) in meters
    speeds: List[float]  # m/s
    accelerations: List[float]  # m/s²
    distances: List[float]  # cumulative distance in meters
    angles: List[float]  # trajectory angle in degrees
    timestamps: List[float]  # seconds

class BallAnalytics:
    """Kinovea-style ball analytics engine"""
    
    def __init__(self, csv_path: str, fps: float = 30.0, 
                 field_calibration=None):
        """
        Initialize ball analytics from CSV tracking data.
        
        Args:
            csv_path: Path to tracking CSV
            fps: Video frame rate
            field_calibration: Field calibration data for real-world coordinates
        """
        self.csv_path = csv_path
        self.fps = fps
        self.field_calibration = field_calibration
        self.df = None
        self.trajectories: List[BallTrajectory] = []
        
    def load_ball_data(self):
        """Load ball tracking data from CSV"""
        try:
            self.df = pd.read_csv(self.csv_path, comment='#')
        except Exception as e:
            print(f"Error loading CSV: {e}")
            return []
        
        # Extract ball positions
        ball_data = []
        for idx, row in self.df.iterrows():
            if pd.notna(row.get('ball_x')) and pd.notna(row.get('ball_y')):
                ball_data.append({
                    'frame': int(row['frame']),
                    'timestamp': row.get('timestamp', idx / self.fps) if pd.notna(row.get('timestamp')) else idx / self.fps,
                    'x': float(row['ball_x']),
                    'y': float(row['ball_y']),
                    'x_m': row.get('ball_x_m', None) if 'ball_x_m' in row else None,
                    'y_m': row.get('ball_y_m', None) if 'ball_y_m' in row else None,
                    'speed_mps': row.get('ball_speed_mps', None) if 'ball_speed_mps' in row else None,
                    'angle': row.get('ball_trajectory_angle', None) if 'ball_trajectory_angle' in row else None
                })
        
        return ball_data
    
    def calculate_trajectory_analytics(self, ball_data: List[Dict]) -> Optional[BallTrajectory]:
        """
        Calculate comprehensive trajectory analytics (Kinovea-style).
        
        Features:
        - Smoothed trajectory (reduces noise)
        - Speed profile
        - Acceleration profile
        - Cumulative distance
        - Trajectory angles
        """
        if len(ball_data) < 2:
            return None
        
        # Extract data
        frames = [d['frame'] for d in ball_data]
        timestamps = [d['timestamp'] for d in ball_data]
        positions = [(d['x'], d['y']) for d in ball_data]
        
        # Convert to real-world coordinates if available
        positions_m = []
        if ball_data[0].get('x_m') is not None and ball_data[0].get('x_m') != '':
            positions_m = [(float(d['x_m']) if d['x_m'] is not None and d['x_m'] != '' else 0,
                           float(d['y_m']) if d['y_m'] is not None and d['y_m'] != '' else 0) 
                          for d in ball_data]
        else:
            # Estimate from pixel coordinates (rough conversion)
            positions_m = self._pixels_to_meters(positions)
        
        # Calculate speeds
        speeds = self._calculate_speeds(positions_m, timestamps)
        
        # Calculate accelerations
        accelerations = self._calculate_accelerations(speeds, timestamps)
        
        # Calculate cumulative distance
        distances = self._calculate_cumulative_distance(positions_m)
        
        # Calculate trajectory angles
        angles = self._calculate_angles(positions_m)
        
        # Smooth trajectory (reduce noise)
        smoothed_positions_m = self._smooth_trajectory(positions_m)
        
        return BallTrajectory(
            frames=frames,
            positions=positions,
            positions_m=smoothed_positions_m,
            speeds=speeds,
            accelerations=accelerations,
            distances=distances,
            angles=angles,
            timestamps=timestamps
        )
    
    def _calculate_speeds(self, positions_m: List[Tuple[float, float]], 
                         timestamps: List[float]) -> List[float]:
        """Calculate speed at each point (m/s)"""
        speeds = [0.0]  # First point has no speed
        
        for i in range(1, len(positions_m)):
            dx = positions_m[i][0] - positions_m[i-1][0]
            dy = positions_m[i][1] - positions_m[i-1][1]
            dt = timestamps[i] - timestamps[i-1]
            
            if dt > 0:
                distance = np.sqrt(dx**2 + dy**2)
                speed = distance / dt
            else:
                speed = 0.0
            
            speeds.append(speed)
        
        return speeds
    
    def _calculate_accelerations(self, speeds: List[float], 
                                timestamps: List[float]) -> List[float]:
        """Calculate acceleration at each point (m/s²)"""
        accelerations = [0.0]  # First point has no acceleration
        
        for i in range(1, len(speeds)):
            dv = speeds[i] - speeds[i-1]
            dt = timestamps[i] - timestamps[i-1]
            
            if dt > 0:
                acceleration = dv / dt
            else:
                acceleration = 0.0
            
            accelerations.append(acceleration)
        
        return accelerations
    
    def _calculate_cumulative_distance(self, positions_m: List[Tuple[float, float]]) -> List[float]:
        """Calculate cumulative distance traveled"""
        distances = [0.0]
        total = 0.0
        
        for i in range(1, len(positions_m)):
            dx = positions_m[i][0] - positions_m[i-1][0]
            dy = positions_m[i][1] - positions_m[i-1][1]
            segment_distance = np.sqrt(dx**2 + dy**2)
            total += segment_distance
            distances.append(total)
        
        return distances
    
    def _calculate_angles(self, positions_m: List[Tuple[float, float]]) -> List[float]:
        """Calculate trajectory angle at each point (degrees)"""
        angles = [0.0]  # First point has no angle
        
        for i in range(1, len(positions_m)):
            dx = positions_m[i][0] - positions_m[i-1][0]
            dy = positions_m[i][1] - positions_m[i-1][1]
            
            if dx == 0 and dy == 0:
                angles.append(angles[-1] if angles else 0.0)
            else:
                angle_rad = np.arctan2(dy, dx)
                angle_deg = np.degrees(angle_rad)
                angles.append(angle_deg)
        
        return angles
    
    def _smooth_trajectory(self, positions_m: List[Tuple[float, float]], 
                          window_size: int = 5) -> List[Tuple[float, float]]:
        """Smooth trajectory using Savitzky-Golay filter (reduces noise)"""
        if len(positions_m) < window_size:
            return positions_m
        
        try:
            x_coords = [p[0] for p in positions_m]
            y_coords = [p[1] for p in positions_m]
            
            # Apply Savitzky-Golay filter (polynomial smoothing)
            # window_size must be odd and less than len(data)
            if window_size % 2 == 0:
                window_size += 1
            if window_size > len(x_coords):
                window_size = len(x_coords) if len(x_coords) % 2 == 1 else len(x_coords) - 1
            
            if window_size < 3:
                return positions_m
            
            x_smooth = signal.savgol_filter(x_coords, window_size, 2)
            y_smooth = signal.savgol_filter(y_coords, window_size, 2)
            
            return list(zip(x_smooth, y_smooth))
        except Exception as e:
            # If smoothing fails, return original
            print(f"Warning: Trajectory smoothing failed: {e}")
            return positions_m
    
    def _pixels_to_meters(self, positions: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Convert pixel coordinates to meters (rough estimate)"""
        # This should use field calibration if available
        # For now, use rough estimate: ~38 pixels per meter for 4K video
        # Try to detect from CSV metadata
        pixels_per_meter = 38.0
        
        # Try to read from CSV comments
        if self.csv_path and os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, 'r') as f:
                    for line in f:
                        if line.startswith('# Video Resolution:'):
                            res_str = line.split(':')[1].strip()
                            if 'x' in res_str:
                                w = int(res_str.split('x')[0].strip())
                                # Rough estimate: field is ~100m wide
                                pixels_per_meter = w / 100.0
                                break
            except:
                pass
        
        return [(x / pixels_per_meter, y / pixels_per_meter) 
                for x, y in positions]
    
    def get_statistics(self, trajectory: BallTrajectory) -> Dict:
        """Get statistical summary (Kinovea-style)"""
        if not trajectory or len(trajectory.speeds) == 0:
            return {}
        
        speeds_array = np.array(trajectory.speeds)
        accelerations_array = np.array(trajectory.accelerations) if trajectory.accelerations else np.array([0])
        
        return {
            'max_speed': float(np.max(speeds_array)),
            'avg_speed': float(np.mean(speeds_array)),
            'min_speed': float(np.min(speeds_array)),
            'total_distance': float(trajectory.distances[-1]) if trajectory.distances and len(trajectory.distances) > 0 else 0.0,
            'max_acceleration': float(np.max(accelerations_array)),
            'min_acceleration': float(np.min(accelerations_array)),
            'avg_acceleration': float(np.mean(accelerations_array)),
            'duration': float(trajectory.timestamps[-1] - trajectory.timestamps[0]) if trajectory.timestamps and len(trajectory.timestamps) > 1 else 0.0,
            'num_points': len(trajectory.frames),
            'max_height': float(max([p[1] for p in trajectory.positions_m])) if trajectory.positions_m else 0.0,
            'min_height': float(min([p[1] for p in trajectory.positions_m])) if trajectory.positions_m else 0.0
        }
    
    def export_kinovea_format(self, trajectory: BallTrajectory, output_path: str):
        """Export trajectory in Kinovea-compatible CSV format"""
        try:
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Time', 'X', 'Y', 'Distance', 'Speed', 'Acceleration', 'Angle'])
                
                for i in range(len(trajectory.frames)):
                    writer.writerow([
                        trajectory.timestamps[i],
                        trajectory.positions_m[i][0],
                        trajectory.positions_m[i][1],
                        trajectory.distances[i],
                        trajectory.speeds[i],
                        trajectory.accelerations[i],
                        trajectory.angles[i]
                    ])
            return True
        except Exception as e:
            print(f"Error exporting trajectory: {e}")
            return False

