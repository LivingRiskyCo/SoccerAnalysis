"""
Track Continuity Validation
Validates track continuity and detects broken tracks
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Try to import logger
try:
    from ...utils.logger_config import get_logger
except ImportError:
    try:
        from SoccerID.utils.logger_config import get_logger
    except ImportError:
        try:
            from utils.logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("track_validator")


class TrackValidator:
    """
    Validates track continuity and detects issues
    """
    
    def __init__(self, max_gap_frames: int = 10, min_track_length: int = 30):
        """
        Initialize track validator
        
        Args:
            max_gap_frames: Maximum allowed gap in frames before track is considered broken
            min_track_length: Minimum track length in frames to be considered valid
        """
        self.max_gap_frames = max_gap_frames
        self.min_track_length = min_track_length
    
    def validate_tracks(self, csv_path: str) -> Dict[str, Any]:
        """
        Validate all tracks in CSV file
        
        Args:
            csv_path: Path to tracking CSV file
            
        Returns:
            Dictionary with validation results
        """
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return {'error': str(e)}
        
        if 'track_id' not in df.columns or 'frame_num' not in df.columns:
            return {'error': 'Missing required columns: track_id or frame_num'}
        
        results = {
            'total_tracks': 0,
            'valid_tracks': 0,
            'broken_tracks': 0,
            'short_tracks': 0,
            'track_details': []
        }
        
        for track_id in df['track_id'].dropna().unique():
            track_df = df[df['track_id'] == track_id].sort_values('frame_num')
            track_info = self._validate_single_track(track_id, track_df)
            results['track_details'].append(track_info)
            
            results['total_tracks'] += 1
            if track_info['is_valid']:
                results['valid_tracks'] += 1
            elif track_info['is_broken']:
                results['broken_tracks'] += 1
            elif track_info['is_short']:
                results['short_tracks'] += 1
        
        return results
    
    def _validate_single_track(self, track_id: int, track_df: pd.DataFrame) -> Dict[str, Any]:
        """Validate a single track"""
        frames = track_df['frame_num'].values
        track_length = len(frames)
        
        info = {
            'track_id': int(track_id),
            'length': track_length,
            'start_frame': int(frames[0]),
            'end_frame': int(frames[-1]),
            'is_valid': True,
            'is_broken': False,
            'is_short': False,
            'gaps': [],
            'issues': []
        }
        
        # Check for gaps
        gaps = []
        for i in range(len(frames) - 1):
            gap = frames[i + 1] - frames[i]
            if gap > 1:
                gap_size = int(gap - 1)
                gaps.append({
                    'start_frame': int(frames[i]),
                    'end_frame': int(frames[i + 1]),
                    'gap_size': gap_size
                })
                
                if gap_size > self.max_gap_frames:
                    info['is_broken'] = True
                    info['is_valid'] = False
                    info['issues'].append(f'Large gap of {gap_size} frames')
        
        info['gaps'] = gaps
        
        # Check track length
        if track_length < self.min_track_length:
            info['is_short'] = True
            info['is_valid'] = False
            info['issues'].append(f'Track too short ({track_length} frames < {self.min_track_length})')
        
        return info
    
    def detect_missing_tracks(self, csv_path: str, expected_players: List[str]) -> Dict[str, Any]:
        """
        Detect missing tracks for expected players
        
        Args:
            csv_path: Path to tracking CSV
            expected_players: List of player names that should be tracked
            
        Returns:
            Dictionary with missing track information
        """
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            return {'error': str(e)}
        
        if 'player_name' not in df.columns:
            return {'error': 'Missing player_name column'}
        
        detected_players = df['player_name'].dropna().unique().tolist()
        missing_players = [p for p in expected_players if p not in detected_players]
        
        return {
            'expected_players': expected_players,
            'detected_players': detected_players,
            'missing_players': missing_players,
            'missing_count': len(missing_players)
        }

