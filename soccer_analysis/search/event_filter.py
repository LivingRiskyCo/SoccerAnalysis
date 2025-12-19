"""
Advanced Event Filtering
Filter events by player, time, zone, type, and more
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Try to import logger
try:
    from ...utils.logger_config import get_logger
except ImportError:
    try:
        from soccer_analysis.utils.logger_config import get_logger
    except ImportError:
        try:
            from utils.logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("event_filter")


class EventFilter:
    """
    Advanced filtering for events
    """
    
    def __init__(self):
        """Initialize event filter"""
        pass
    
    def filter_events(self,
                     csv_path: str,
                     filters: Dict[str, Any]) -> pd.DataFrame:
        """
        Filter events from CSV based on criteria
        
        Args:
            csv_path: Path to events CSV file
            filters: Filter criteria dictionary:
                - player_name: Filter by player name(s)
                - event_type: Filter by event type(s)
                - time_range: Filter by time range (start_time, end_time)
                - frame_range: Filter by frame range (start_frame, end_frame)
                - zone: Filter by field zone
                - min_confidence: Minimum confidence threshold
                - min_speed: Minimum speed threshold
                - tags: Filter by tags
                
        Returns:
            Filtered DataFrame
        """
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return pd.DataFrame()
        
        # Apply filters
        filtered_df = df.copy()
        
        # Player filter
        if 'player_name' in filters:
            player_names = filters['player_name']
            if isinstance(player_names, str):
                player_names = [player_names]
            if 'player_name' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['player_name'].isin(player_names)]
        
        # Event type filter
        if 'event_type' in filters:
            event_types = filters['event_type']
            if isinstance(event_types, str):
                event_types = [event_types]
            if 'event_type' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['event_type'].isin(event_types)]
        
        # Time range filter
        if 'time_range' in filters:
            start_time, end_time = filters['time_range']
            if 'timestamp' in filtered_df.columns:
                filtered_df = filtered_df[
                    (filtered_df['timestamp'] >= start_time) &
                    (filtered_df['timestamp'] <= end_time)
                ]
        
        # Frame range filter
        if 'frame_range' in filters:
            start_frame, end_frame = filters['frame_range']
            if 'frame_num' in filtered_df.columns:
                filtered_df = filtered_df[
                    (filtered_df['frame_num'] >= start_frame) &
                    (filtered_df['frame_num'] <= end_frame)
                ]
        
        # Zone filter
        if 'zone' in filters:
            zone = filters['zone']
            if 'zone' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['zone'] == zone]
            elif 'x' in filtered_df.columns and 'y' in filtered_df.columns:
                # Filter by position if zone column doesn't exist
                filtered_df = self._filter_by_zone_position(filtered_df, zone)
        
        # Confidence filter
        if 'min_confidence' in filters:
            min_conf = filters['min_confidence']
            if 'confidence' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['confidence'] >= min_conf]
        
        # Speed filter
        if 'min_speed' in filters:
            min_speed = filters['min_speed']
            if 'speed' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['speed'] >= min_speed]
        
        # Tags filter
        if 'tags' in filters:
            tags = filters['tags']
            if isinstance(tags, str):
                tags = [tags]
            if 'tags' in filtered_df.columns:
                # Tags might be comma-separated string or list
                filtered_df = filtered_df[
                    filtered_df['tags'].apply(
                        lambda x: any(tag in str(x) for tag in tags) if pd.notna(x) else False
                    )
                ]
        
        logger.info(f"Filtered {len(df)} events to {len(filtered_df)} events")
        return filtered_df
    
    def _filter_by_zone_position(self, df: pd.DataFrame, zone: str) -> pd.DataFrame:
        """Filter by zone based on position"""
        # Simplified zone filtering - would need field calibration
        # Zones: "defensive_third", "middle_third", "attacking_third", "goal_area", etc.
        if 'x' not in df.columns or 'y' not in df.columns:
            return df
        
        # Assume field is normalized 0-1 or in pixels
        # This is simplified - would need actual field calibration
        if zone == "defensive_third":
            # Bottom third of field (assuming y increases downward)
            threshold = df['y'].max() * 0.67
            return df[df['y'] > threshold]
        elif zone == "middle_third":
            threshold_low = df['y'].max() * 0.33
            threshold_high = df['y'].max() * 0.67
            return df[(df['y'] >= threshold_low) & (df['y'] <= threshold_high)]
        elif zone == "attacking_third":
            threshold = df['y'].max() * 0.33
            return df[df['y'] < threshold]
        
        return df
    
    def get_filter_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get summary statistics for filtered events"""
        if len(df) == 0:
            return {}
        
        summary = {
            'total_events': len(df),
            'by_type': {},
            'by_player': {},
            'time_range': {},
            'frame_range': {}
        }
        
        # Count by type
        if 'event_type' in df.columns:
            summary['by_type'] = df['event_type'].value_counts().to_dict()
        
        # Count by player
        if 'player_name' in df.columns:
            summary['by_player'] = df['player_name'].value_counts().to_dict()
        
        # Time range
        if 'timestamp' in df.columns:
            summary['time_range'] = {
                'start': float(df['timestamp'].min()),
                'end': float(df['timestamp'].max()),
                'duration': float(df['timestamp'].max() - df['timestamp'].min())
            }
        
        # Frame range
        if 'frame_num' in df.columns:
            summary['frame_range'] = {
                'start': int(df['frame_num'].min()),
                'end': int(df['frame_num'].max()),
                'span': int(df['frame_num'].max() - df['frame_num'].min())
            }
        
        return summary

