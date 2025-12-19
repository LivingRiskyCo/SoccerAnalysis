"""
Enhanced Statistics Dashboard
Real-time stats overlay with more metrics
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from event_tracker import EventTracker

class EnhancedStatsDashboard:
    def __init__(self, csv_data: pd.DataFrame, event_tracker: Optional[EventTracker] = None):
        self.csv_data = csv_data
        self.event_tracker = event_tracker
        self.stats = self._calculate_stats()
    
    def _calculate_stats(self):
        """Calculate comprehensive statistics"""
        stats = {}
        
        if self.csv_data.empty or 'track_id' not in self.csv_data.columns:
            return stats
        
        # Per-player stats
        for player_id in self.csv_data['track_id'].unique():
            if pd.isna(player_id):
                continue
                
            player_data = self.csv_data[self.csv_data['track_id'] == player_id].copy()
            
            stats[int(player_id)] = {
                # Basic
                "total_frames": len(player_data),
                "time_on_field": len(player_data) / 30.0,  # Assuming 30 fps
                
                # Movement
                "total_distance": self._calculate_distance(player_data),
                "avg_speed": self._calculate_avg_speed(player_data),
                "max_speed": self._calculate_max_speed(player_data),
                "avg_acceleration": self._calculate_acceleration(player_data),
                
                # Position
                "avg_x_position": float(player_data['x'].mean()) if 'x' in player_data.columns else None,
                "avg_y_position": float(player_data['y'].mean()) if 'y' in player_data.columns else None,
                "position_variance": self._calculate_position_variance(player_data),
                
                # Events (if event tracker available)
                "goals": len(self.event_tracker.get_events_for_player(str(player_id))) if self.event_tracker else 0,
                "passes": len([e for e in (self.event_tracker.events if self.event_tracker else []) 
                             if e.event_type == 'pass' and (e.player_id == player_id or str(e.player_id) == str(player_id))]),
                "shots": len([e for e in (self.event_tracker.events if self.event_tracker else []) 
                            if e.event_type == 'shot' and (e.player_id == player_id or str(e.player_id) == str(player_id))]),
                
                # Heat map data
                "heat_map": self._generate_heat_map(player_data)
            }
        
        # Team stats
        stats['team'] = self._calculate_team_stats()
        
        return stats
    
    def _calculate_distance(self, player_data: pd.DataFrame) -> float:
        """Calculate total distance traveled"""
        if 'x' not in player_data.columns or 'y' not in player_data.columns:
            return 0.0
        
        # Sort by frame
        sorted_data = player_data.sort_values('frame_num')
        
        if len(sorted_data) < 2:
            return 0.0
        
        # Calculate distance between consecutive frames
        dx = sorted_data['x'].diff()
        dy = sorted_data['y'].diff()
        distances = np.sqrt(dx**2 + dy**2)
        
        return float(distances.sum())
    
    def _calculate_avg_speed(self, player_data: pd.DataFrame) -> float:
        """Calculate average speed (pixels per frame)"""
        if 'x' not in player_data.columns or 'y' not in player_data.columns:
            return 0.0
        
        sorted_data = player_data.sort_values('frame_num')
        
        if len(sorted_data) < 2:
            return 0.0
        
        dx = sorted_data['x'].diff()
        dy = sorted_data['y'].diff()
        speeds = np.sqrt(dx**2 + dy**2)
        
        return float(speeds.mean())
    
    def _calculate_max_speed(self, player_data: pd.DataFrame) -> float:
        """Calculate maximum speed"""
        if 'x' not in player_data.columns or 'y' not in player_data.columns:
            return 0.0
        
        sorted_data = player_data.sort_values('frame_num')
        
        if len(sorted_data) < 2:
            return 0.0
        
        dx = sorted_data['x'].diff()
        dy = sorted_data['y'].diff()
        speeds = np.sqrt(dx**2 + dy**2)
        
        return float(speeds.max())
    
    def _calculate_acceleration(self, player_data: pd.DataFrame) -> float:
        """Calculate average acceleration"""
        if 'x' not in player_data.columns or 'y' not in player_data.columns:
            return 0.0
        
        sorted_data = player_data.sort_values('frame_num')
        
        if len(sorted_data) < 3:
            return 0.0
        
        dx = sorted_data['x'].diff()
        dy = sorted_data['y'].diff()
        speeds = np.sqrt(dx**2 + dy**2)
        accelerations = speeds.diff()
        
        return float(accelerations.mean())
    
    def _calculate_position_variance(self, player_data: pd.DataFrame) -> float:
        """Calculate position variance (how much player moves around)"""
        if 'x' not in player_data.columns or 'y' not in player_data.columns:
            return 0.0
        
        x_var = float(player_data['x'].var()) if len(player_data) > 1 else 0.0
        y_var = float(player_data['y'].var()) if len(player_data) > 1 else 0.0
        
        return x_var + y_var
    
    def _generate_heat_map(self, player_data: pd.DataFrame, grid_size: int = 20) -> List[List[float]]:
        """Generate heat map data for player positions"""
        if 'x' not in player_data.columns or 'y' not in player_data.columns:
            return [[0.0] * grid_size for _ in range(grid_size)]
        
        # Normalize positions to 0-1 range
        x_min, x_max = player_data['x'].min(), player_data['x'].max()
        y_min, y_max = player_data['y'].min(), player_data['y'].max()
        
        if x_max == x_min or y_max == y_min:
            return [[0.0] * grid_size for _ in range(grid_size)]
        
        x_norm = (player_data['x'] - x_min) / (x_max - x_min)
        y_norm = (player_data['y'] - y_min) / (y_max - y_min)
        
        # Create grid
        heat_map = [[0.0] * grid_size for _ in range(grid_size)]
        
        for x, y in zip(x_norm, y_norm):
            grid_x = min(int(x * grid_size), grid_size - 1)
            grid_y = min(int(y * grid_size), grid_size - 1)
            heat_map[grid_y][grid_x] += 1.0
        
        # Normalize
        max_val = max(max(row) for row in heat_map)
        if max_val > 0:
            heat_map = [[val / max_val for val in row] for row in heat_map]
        
        return heat_map
    
    def _calculate_team_stats(self) -> Dict:
        """Calculate team-level statistics"""
        if self.event_tracker:
            return {
                "total_goals": len(self.event_tracker.get_events_by_type('goal')),
                "total_shots": len(self.event_tracker.get_events_by_type('shot')),
                "total_passes": len(self.event_tracker.get_events_by_type('pass')),
                "total_fouls": len(self.event_tracker.get_events_by_type('foul')),
                "total_saves": len(self.event_tracker.get_events_by_type('save'))
            }
        return {}
    
    def get_realtime_stats(self, frame_num: int, player_id: int) -> Dict:
        """Get real-time stats for current frame"""
        frame_data = self.csv_data[self.csv_data['frame_num'] == frame_num]
        player_frame = frame_data[frame_data['track_id'] == player_id]
        
        if player_frame.empty:
            return {}
        
        # Calculate distance traveled up to this frame
        player_data = self.csv_data[self.csv_data['track_id'] == player_id]
        player_data = player_data[player_data['frame_num'] <= frame_num]
        
        return {
            "current_speed": self._get_current_speed(player_frame),
            "distance_traveled": self._calculate_distance_to_frame(player_id, frame_num),
            "time_on_field": frame_num / 30.0,
            "current_position": (
                float(player_frame['x'].iloc[0]) if 'x' in player_frame.columns else None,
                float(player_frame['y'].iloc[0]) if 'y' in player_frame.columns else None
            ) if not player_frame.empty else None
        }
    
    def _get_current_speed(self, player_frame: pd.DataFrame) -> float:
        """Get current speed from frame data"""
        if 'speed' in player_frame.columns:
            return float(player_frame['speed'].iloc[0])
        return 0.0
    
    def _calculate_distance_to_frame(self, player_id: int, frame_num: int) -> float:
        """Calculate distance traveled up to a specific frame"""
        player_data = self.csv_data[self.csv_data['track_id'] == player_id]
        player_data = player_data[player_data['frame_num'] <= frame_num]
        return self._calculate_distance(player_data)
    
    def get_player_summary(self, player_id: int) -> Dict:
        """Get summary statistics for a player"""
        if player_id not in self.stats:
            return {}
        return self.stats[player_id]

