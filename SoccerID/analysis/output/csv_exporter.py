"""
CSV Export Module
Handles CSV export of tracking data with comprehensive field support
"""

import csv
import os
import shutil
from typing import Dict, List, Any, Optional, TextIO

# Try new structure imports first, fallback to legacy
try:
    from ...utils.logger_config import get_logger
    from ...analysis.core.utils import meters_to_feet, mps_to_mph, mps2_to_fts2
except ImportError:
    try:
        from SoccerID.utils.logger_config import get_logger
        from SoccerID.analysis.core.utils import meters_to_feet, mps_to_mph, mps2_to_fts2
    except ImportError:
        # Legacy fallback
        try:
            from logger_config import get_logger
            from combined_analysis_optimized import meters_to_feet, mps_to_mph, mps2_to_fts2
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)
            # Fallback unit conversions
            def meters_to_feet(m): return m * 3.28084 if m is not None else None
            def mps_to_mph(mps): return mps * 2.23694 if mps is not None else None
            def mps2_to_fts2(mps2): return mps2 * 3.28084 if mps2 is not None else None

logger = get_logger("csv_export")


class CSVExporter:
    """Handles CSV export of tracking data"""
    
    # Standard CSV column headers (matches legacy format)
    CSV_HEADERS = [
        'frame_num', 'timestamp',
        'ball_x', 'ball_y', 'ball_detected',
        'ball_x_m', 'ball_y_m', 'trajectory_angle', 'ball_speed_mps',
        'track_id', 'player_name', 'player_x', 'player_y',
        'player_x_m', 'player_y_m', 'player_speed_mps', 'player_acceleration_mps2',
        'player_movement_angle', 'distance_to_ball',
        'distance_traveled_m', 'max_speed_mps', 'sprint_count', 'possession_time_s',
        'distance_from_center_m', 'distance_from_goal_m', 'field_zone',
        'field_position_x_pct', 'field_position_y_pct', 'direction_changes',
        'avg_speed_mps', 'distance_walking_m', 'distance_jogging_m',
        'distance_running_m', 'distance_sprinting_m', 'time_stationary_s',
        'acceleration_events', 'nearest_teammate_dist_m', 'nearest_opponent_dist_m',
        'confidence', 'possession_player_id', 'team', 'is_anchor',
        'bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2'
    ]
    
    def __init__(self, buffer_size: int = 1000):
        """
        Initialize CSV exporter
        
        Args:
            buffer_size: Number of rows to buffer before writing (default 1000)
        """
        self.csv_file: Optional[TextIO] = None
        self.csv_writer: Optional[csv.writer] = None
        self.csv_filename: Optional[str] = None
        self.buffer_size = buffer_size
        self.write_buffer: List[List[Any]] = []
        self.export_stats = {
            'total_player_rows': 0,
            'frames_with_players': 0,
            'frames_with_empty_centers': 0
        }
    
    def initialize_csv(self, output_path: str) -> bool:
        """
        Initialize CSV file and writer
        
        Args:
            output_path: Output CSV file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.csv_filename = output_path
            self.csv_file = open(output_path, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            
            # Write header
            self.csv_writer.writerow(self.CSV_HEADERS)
            
            logger.info(f"Initialized CSV export: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing CSV: {e}", exc_info=True)
            return False
    
    def _flush_buffer(self):
        """Flush buffered rows to CSV file"""
        if self.write_buffer and self.csv_writer:
            self.csv_writer.writerows(self.write_buffer)
            self.write_buffer.clear()
            if self.csv_file:
                self.csv_file.flush()  # Ensure data is written
    
    def write_frame_data(self, frame_data: Dict[str, Any],
                        player_centers: Dict[int, tuple],
                        player_names: Dict[str, str],
                        player_analytics: Dict[str, Dict[str, Any]],
                        ball_data: Dict[str, Any],
                        use_imperial_units: bool = False,
                        **kwargs) -> bool:
        """
        Write frame data to CSV (buffered for performance)
        
        Args:
            frame_data: Frame metadata (frame_num, timestamp, ball_center, ball_detected)
            player_centers: Dict of {player_id: (x, y)} pixel positions
            player_names: Dict of {player_id_str: player_name}
            player_analytics: Dict of {player_name: analytics_dict}
            ball_data: Ball tracking data (x_m, y_m, speed_mps, trajectory_angle)
            use_imperial_units: Convert to feet/mph if True
            **kwargs: Additional data (detections, anchor_frames, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.csv_writer or not self.csv_file:
            return False
        
        try:
            frame_num = frame_data.get('frame_num', 0)
            timestamp = frame_data.get('timestamp', 0.0)
            ball_center = frame_data.get('ball_center')
            ball_detected = frame_data.get('ball_detected', False)
            
            # Extract ball data
            ball_x_m = ball_data.get('x_m')
            ball_y_m = ball_data.get('y_m')
            ball_speed_mps = ball_data.get('speed_mps')
            trajectory_angle = ball_data.get('trajectory_angle')
            
            # Get detections for bbox extraction
            detections = kwargs.get('detections')
            track_to_team_global = kwargs.get('track_to_team_global', {})
            anchor_frames = kwargs.get('anchor_frames')
            possession_player_id = kwargs.get('possession_player_id')
            width = kwargs.get('width', 1920)
            height = kwargs.get('height', 1080)
            
            # Apply unit conversions for ball
            if use_imperial_units:
                ball_x_m = meters_to_feet(ball_x_m) if ball_x_m is not None else None
                ball_y_m = meters_to_feet(ball_y_m) if ball_y_m is not None else None
                ball_speed_mps = mps_to_mph(ball_speed_mps) if ball_speed_mps is not None else None
            
            if player_centers:
                self.export_stats['frames_with_players'] += 1
                
                for player_id, (px, py) in player_centers.items():
                    self.export_stats['total_player_rows'] += 1
                    
                    # Get player name
                    player_id_str = str(player_id)
                    player_name = player_names.get(player_id_str, '')
                    
                    # Get team
                    player_team = track_to_team_global.get(player_id, '')
                    
                    # Get bbox from detections
                    bbox_x1, bbox_y1, bbox_x2, bbox_y2 = '', '', '', ''
                    bbox_valid = False
                    if detections is not None and hasattr(detections, 'tracker_id') and detections.tracker_id is not None:
                        for det_idx, tid in enumerate(detections.tracker_id):
                            if tid == player_id and det_idx < len(detections.xyxy):
                                bbox = detections.xyxy[det_idx]
                                bbox_x1, bbox_y1, bbox_x2, bbox_y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                                
                                # Filter off-frame detections
                                frame_margin = 50
                                if (bbox_x1 < -frame_margin or bbox_x2 > width + frame_margin or
                                    bbox_y1 < -frame_margin or bbox_y2 > height + frame_margin):
                                    continue
                                
                                bbox_valid = True
                                break
                    
                    if not bbox_valid:
                        continue
                    
                    # Flush buffer if it's getting large
                    if len(self.write_buffer) >= self.buffer_size:
                        self._flush_buffer()
                    
                    # Check if anchor frame
                    is_anchor = False
                    if anchor_frames and frame_num in anchor_frames:
                        for anchor in anchor_frames[frame_num]:
                            anchor_track_id = anchor.get('track_id')
                            anchor_player_name = anchor.get('player_name', '')
                            if (anchor_track_id is not None and anchor_track_id == player_id) or \
                               (anchor_player_name and anchor_player_name == player_name):
                                is_anchor = True
                                break
                    
                    # Get analytics
                    analytics = player_analytics.get(player_name, {})
                    
                    # Extract analytics values
                    player_x_m = analytics.get('x_m')
                    player_y_m = analytics.get('y_m')
                    player_speed_mps = analytics.get('speed_mps')
                    player_acceleration_mps2 = analytics.get('acceleration_mps2')
                    player_movement_angle = analytics.get('movement_angle')
                    player_distance_to_ball = analytics.get('distance_to_ball')
                    distance_traveled_m = analytics.get('distance_traveled_m', 0.0)
                    max_speed_mps = analytics.get('max_speed_mps', 0.0)
                    sprint_count = analytics.get('sprint_count', 0)
                    possession_time_s = analytics.get('possession_time_s', 0.0)
                    distance_from_center_m = analytics.get('distance_from_center_m')
                    distance_from_goal_m = analytics.get('distance_from_goal_m')
                    field_zone = analytics.get('field_zone', '')
                    field_position_x_pct = analytics.get('field_position_x_pct')
                    field_position_y_pct = analytics.get('field_position_y_pct')
                    direction_changes = analytics.get('direction_changes', 0)
                    avg_speed_mps = analytics.get('avg_speed_mps')
                    distance_walking_m = analytics.get('distance_walking_m', 0.0)
                    distance_jogging_m = analytics.get('distance_jogging_m', 0.0)
                    distance_running_m = analytics.get('distance_running_m', 0.0)
                    distance_sprinting_m = analytics.get('distance_sprinting_m', 0.0)
                    time_stationary_s = analytics.get('time_stationary_s', 0.0)
                    acceleration_events = analytics.get('acceleration_events', 0)
                    nearest_teammate_dist_m = analytics.get('nearest_teammate_dist_m')
                    nearest_opponent_dist_m = analytics.get('nearest_opponent_dist_m')
                    
                    # Apply unit conversions
                    if use_imperial_units:
                        player_x_m = meters_to_feet(player_x_m) if player_x_m is not None else None
                        player_y_m = meters_to_feet(player_y_m) if player_y_m is not None else None
                        player_speed_mps = mps_to_mph(player_speed_mps) if player_speed_mps is not None else None
                        player_acceleration_mps2 = mps2_to_fts2(player_acceleration_mps2) if player_acceleration_mps2 is not None else None
                        distance_traveled_m = meters_to_feet(distance_traveled_m)
                        max_speed_mps = mps_to_mph(max_speed_mps)
                        distance_from_center_m = meters_to_feet(distance_from_center_m) if distance_from_center_m is not None else None
                        distance_from_goal_m = meters_to_feet(distance_from_goal_m) if distance_from_goal_m is not None else None
                        avg_speed_mps = mps_to_mph(avg_speed_mps) if avg_speed_mps is not None else None
                        distance_walking_m = meters_to_feet(distance_walking_m)
                        distance_jogging_m = meters_to_feet(distance_jogging_m)
                        distance_running_m = meters_to_feet(distance_running_m)
                        distance_sprinting_m = meters_to_feet(distance_sprinting_m)
                        nearest_teammate_dist_m = meters_to_feet(nearest_teammate_dist_m) if nearest_teammate_dist_m is not None else None
                        nearest_opponent_dist_m = meters_to_feet(nearest_opponent_dist_m) if nearest_opponent_dist_m is not None else None
                    
                    # Write row
                    try:
                        # Add to buffer instead of writing immediately
                        self.write_buffer.append([
                            frame_num, timestamp,
                            ball_center[0] if ball_center else '',
                            ball_center[1] if ball_center else '',
                            ball_detected,
                            ball_x_m if ball_x_m is not None else '',
                            ball_y_m if ball_y_m is not None else '',
                            trajectory_angle if trajectory_angle is not None else '',
                            ball_speed_mps if ball_speed_mps is not None else '',
                            player_id, player_name, px, py,
                            player_x_m if player_x_m is not None else '',
                            player_y_m if player_y_m is not None else '',
                            player_speed_mps if player_speed_mps is not None else '',
                            player_acceleration_mps2 if player_acceleration_mps2 is not None else '',
                            player_movement_angle if player_movement_angle is not None else '',
                            player_distance_to_ball if player_distance_to_ball is not None else '',
                            distance_traveled_m, max_speed_mps, sprint_count, possession_time_s,
                            distance_from_center_m if distance_from_center_m is not None else '',
                            distance_from_goal_m if distance_from_goal_m is not None else '',
                            field_zone,
                            field_position_x_pct if field_position_x_pct is not None else '',
                            field_position_y_pct if field_position_y_pct is not None else '',
                            direction_changes,
                            avg_speed_mps if avg_speed_mps is not None else '',
                            distance_walking_m, distance_jogging_m,
                            distance_running_m, distance_sprinting_m,
                            time_stationary_s, acceleration_events,
                            nearest_teammate_dist_m if nearest_teammate_dist_m is not None else '',
                            nearest_opponent_dist_m if nearest_opponent_dist_m is not None else '',
                            0.0,  # confidence
                            possession_player_id if possession_player_id == player_id else '',
                            player_team,
                            1 if is_anchor else 0,
                            bbox_x1 if bbox_x1 != '' else '',
                            bbox_y1 if bbox_y1 != '' else '',
                            bbox_x2 if bbox_x2 != '' else '',
                            bbox_y2 if bbox_y2 != '' else ''
                        ])
                        
                        # Flush buffer periodically (every 100 frames or when buffer is full)
                        if len(self.write_buffer) >= self.buffer_size or frame_num % 100 == 0:
                            self._flush_buffer()
                            
                    except OSError as e:
                        if e.errno == 28:  # No space left on device
                            self._handle_disk_space_error(frame_num)
                            raise
                        else:
                            raise
            else:
                self.export_stats['frames_with_empty_centers'] += 1
                # Write empty row for frames with no players
                try:
                    # Add to buffer instead of writing immediately
                    self.write_buffer.append([
                        frame_num, timestamp,
                        ball_center[0] if ball_center else '',
                        ball_center[1] if ball_center else '',
                        ball_detected,
                        ball_x_m if ball_x_m is not None else '',
                        ball_y_m if ball_y_m is not None else '',
                        trajectory_angle if trajectory_angle is not None else '',
                        ball_speed_mps if ball_speed_mps is not None else '',
                        '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''
                    ])
                    
                    # Flush buffer periodically
                    if len(self.write_buffer) >= self.buffer_size or frame_num % 100 == 0:
                        self._flush_buffer()
                        
                except OSError as e:
                    if e.errno == 28:
                        self._handle_disk_space_error(frame_num)
                        raise
                    else:
                        raise
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing frame data: {e}", exc_info=True)
            return False
    
    def _handle_disk_space_error(self, frame_num: int):
        """Handle disk space errors with helpful messages"""
        try:
            csv_drive = os.path.splitdrive(self.csv_filename)[0] + '\\' if self.csv_filename else 'C:\\'
            disk_usage = shutil.disk_usage(csv_drive)
            free_gb = disk_usage.free / (1024**3)
            total_gb = disk_usage.total / (1024**3)
            used_gb = disk_usage.used / (1024**3)
            
            logger.error(f"\n❌ DISK SPACE ERROR at frame {frame_num}")
            logger.error(f"   Drive: {csv_drive}")
            logger.error(f"   Free space: {free_gb:.2f}GB / {total_gb:.2f}GB total ({used_gb:.2f}GB used)")
            logger.error(f"   CSV file location: {self.csv_filename}")
            logger.error(f"\n   Solutions:")
            logger.error(f"   1. Free up space on {csv_drive} (need at least 1-2GB)")
            logger.error(f"   2. Change output location to a drive with more space")
            logger.error(f"   3. Clean Windows temp files: %TEMP% and %TMP%")
            logger.error(f"   4. Disable CSV export if not needed")
        except Exception:
            pass
    
    def close(self):
        """Close CSV file (flushes any remaining buffer)"""
        # Flush any remaining buffered rows
        if self.write_buffer:
            self._flush_buffer()
        
        if self.csv_file:
            try:
                self.csv_file.close()
                logger.info(f"CSV export closed: {self.csv_filename}")
                logger.info(f"   → {self.export_stats['total_player_rows']} player rows from {self.export_stats['frames_with_players']} frames")
            except Exception as e:
                logger.error(f"Error closing CSV: {e}")
            finally:
                self.csv_file = None
                self.csv_writer = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get export statistics"""
        return self.export_stats.copy()

