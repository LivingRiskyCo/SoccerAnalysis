"""
Smoothing Module
GSI, Kalman, EMA smoothing
"""

from typing import List, Dict, Any, Optional
import numpy as np

# Try new structure imports first, fallback to legacy
try:
    from ...utils.logger_config import get_logger
except ImportError:
    try:
        from soccer_analysis.utils.logger_config import get_logger
    except ImportError:
        # Legacy fallback
        try:
            from logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("smoothing")

# GSI smoothing import
try:
    from gsi_smoothing import apply_gsi_realtime, SKLEARN_AVAILABLE as GSI_AVAILABLE
except ImportError:
    GSI_AVAILABLE = False
    logger.warning("GSI smoothing not available. Install sklearn: pip install scikit-learn")


class SmoothingProcessor:
    """Handles track smoothing using various algorithms"""
    
    def __init__(self, use_gsi: bool = False, use_kalman: bool = False, 
                 use_ema: bool = False, gsi_interval: int = 20, gsi_tau: float = 10.0,
                 ema_alpha: float = 0.3):
        """
        Initialize smoothing processor
        
        Args:
            use_gsi: Enable GSI smoothing
            use_kalman: Enable Kalman filtering
            use_ema: Enable EMA smoothing
            gsi_interval: GSI interval parameter
            gsi_tau: GSI tau parameter
            ema_alpha: EMA smoothing factor (0-1, higher = more responsive)
        """
        self.use_gsi = use_gsi and GSI_AVAILABLE
        self.use_kalman = use_kalman
        self.use_ema = use_ema
        self.gsi_interval = gsi_interval
        self.gsi_tau = gsi_tau
        self.ema_alpha = ema_alpha
        
        if self.use_gsi and not GSI_AVAILABLE:
            logger.warning("GSI requested but not available")
            self.use_gsi = False
    
    def smooth_tracks(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply smoothing to tracks
        
        Args:
            tracks: List of track dictionaries
            
        Returns:
            Smoothed tracks
        """
        if not tracks:
            return tracks
        
        # Apply GSI if enabled
        if self.use_gsi:
            try:
                tracks = self._apply_gsi(tracks)
            except Exception as e:
                logger.warning(f"GSI smoothing failed: {e}")
        
        # Apply Kalman if enabled
        if self.use_kalman:
            try:
                tracks = self._apply_kalman(tracks)
            except Exception as e:
                logger.warning(f"Kalman filtering failed: {e}")
        
        # Apply EMA if enabled
        if self.use_ema:
            try:
                tracks = self._apply_ema(tracks, self.ema_alpha)
            except Exception as e:
                logger.warning(f"EMA smoothing failed: {e}")
        
        return tracks
    
    def _apply_gsi(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply GSI smoothing"""
        if not GSI_AVAILABLE:
            return tracks
        
        try:
            # GSI smoothing requires position data in a specific format
            # Extract positions from tracks
            positions = []
            for track in tracks:
                if 'bbox' in track:
                    bbox = track['bbox']
                    center_x = (bbox[0] + bbox[2]) / 2
                    center_y = (bbox[1] + bbox[3]) / 2
                    positions.append([center_x, center_y])
                elif 'center' in track:
                    positions.append(list(track['center']))
                else:
                    positions.append([0, 0])
            
            if len(positions) < 2:
                return tracks
            
            # Apply GSI smoothing
            positions_array = np.array(positions)
            smoothed_positions = apply_gsi_realtime(
                positions_array,
                interval=self.gsi_interval,
                tau=self.gsi_tau
            )
            
            # Update tracks with smoothed positions
            for i, track in enumerate(tracks):
                if i < len(smoothed_positions):
                    smoothed_pos = smoothed_positions[i]
                    if 'bbox' in track:
                        # Update bbox center
                        bbox = track['bbox']
                        center_x = (bbox[0] + bbox[2]) / 2
                        center_y = (bbox[1] + bbox[3]) / 2
                        dx = smoothed_pos[0] - center_x
                        dy = smoothed_pos[1] - center_y
                        track['bbox'] = [
                            bbox[0] + dx, bbox[1] + dy,
                            bbox[2] + dx, bbox[3] + dy
                        ]
                    elif 'center' in track:
                        track['center'] = tuple(smoothed_pos)
            
            return tracks
            
        except Exception as e:
            logger.warning(f"GSI smoothing failed: {e}")
            return tracks
    
    def _apply_kalman(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply Kalman filtering"""
        try:
            # Try to import enhanced tracking Kalman filter
            try:
                from enhanced_tracking import EnhancedKalmanFilter
                ENHANCED_KALMAN_AVAILABLE = True
            except ImportError:
                ENHANCED_KALMAN_AVAILABLE = False
            
            if not ENHANCED_KALMAN_AVAILABLE:
                # Basic Kalman implementation
                return self._apply_basic_kalman(tracks)
            
            # Use enhanced Kalman filter
            # Initialize filters for each track
            if not hasattr(self, '_kalman_filters'):
                self._kalman_filters = {}
            
            for track in tracks:
                track_id = track.get('track_id')
                if track_id is None:
                    continue
                
                if track_id not in self._kalman_filters:
                    self._kalman_filters[track_id] = EnhancedKalmanFilter()
                
                # Get position
                if 'bbox' in track:
                    bbox = track['bbox']
                    center_x = (bbox[0] + bbox[2]) / 2
                    center_y = (bbox[1] + bbox[3]) / 2
                elif 'center' in track:
                    center_x, center_y = track['center']
                else:
                    continue
                
                # Update and get filtered position
                filtered_pos = self._kalman_filters[track_id].update([center_x, center_y])
                
                # Update track
                if 'bbox' in track:
                    dx = filtered_pos[0] - center_x
                    dy = filtered_pos[1] - center_y
                    track['bbox'] = [
                        bbox[0] + dx, bbox[1] + dy,
                        bbox[2] + dx, bbox[3] + dy
                    ]
                elif 'center' in track:
                    track['center'] = tuple(filtered_pos)
            
            return tracks
            
        except Exception as e:
            logger.warning(f"Kalman filtering failed: {e}")
            return tracks
    
    def _apply_basic_kalman(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Basic Kalman filter implementation"""
        # Simple moving average as fallback
        if not hasattr(self, '_position_history'):
            self._position_history = {}
        
        for track in tracks:
            track_id = track.get('track_id')
            if track_id is None:
                continue
            
            # Get position
            if 'bbox' in track:
                bbox = track['bbox']
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
            elif 'center' in track:
                center_x, center_y = track['center']
            else:
                continue
            
            # Update history
            if track_id not in self._position_history:
                self._position_history[track_id] = []
            
            self._position_history[track_id].append([center_x, center_y])
            
            # Keep only last 5 positions
            if len(self._position_history[track_id]) > 5:
                self._position_history[track_id].pop(0)
            
            # Simple moving average
            history = np.array(self._position_history[track_id])
            smoothed_pos = np.mean(history, axis=0)
            
            # Update track
            if 'bbox' in track:
                dx = smoothed_pos[0] - center_x
                dy = smoothed_pos[1] - center_y
                track['bbox'] = [
                    bbox[0] + dx, bbox[1] + dy,
                    bbox[2] + dx, bbox[3] + dy
                ]
            elif 'center' in track:
                track['center'] = tuple(smoothed_pos)
        
        return tracks
    
    def _apply_ema(self, tracks: List[Dict[str, Any]], alpha: float = 0.3) -> List[Dict[str, Any]]:
        """Apply EMA (Exponential Moving Average) smoothing"""
        try:
            # Try to import EMA smoother
            try:
                from enhanced_tracking import EMASmoother
                EMA_AVAILABLE = True
            except ImportError:
                EMA_AVAILABLE = False
            
            if not EMA_AVAILABLE:
                # Basic EMA implementation
                return self._apply_basic_ema(tracks, alpha)
            
            # Use enhanced EMA smoother
            if not hasattr(self, '_ema_smoothers'):
                self._ema_smoothers = {}
            
            for track in tracks:
                track_id = track.get('track_id')
                if track_id is None:
                    continue
                
                if track_id not in self._ema_smoothers:
                    self._ema_smoothers[track_id] = EMASmoother(alpha=alpha)
                
                # Get position
                if 'bbox' in track:
                    bbox = track['bbox']
                    center_x = (bbox[0] + bbox[2]) / 2
                    center_y = (bbox[1] + bbox[3]) / 2
                elif 'center' in track:
                    center_x, center_y = track['center']
                else:
                    continue
                
                # Update and get smoothed position
                smoothed_pos = self._ema_smoothers[track_id].update([center_x, center_y])
                
                # Update track
                if 'bbox' in track:
                    dx = smoothed_pos[0] - center_x
                    dy = smoothed_pos[1] - center_y
                    track['bbox'] = [
                        bbox[0] + dx, bbox[1] + dy,
                        bbox[2] + dx, bbox[3] + dy
                    ]
                elif 'center' in track:
                    track['center'] = tuple(smoothed_pos)
            
            return tracks
            
        except Exception as e:
            logger.warning(f"EMA smoothing failed: {e}")
            return tracks
    
    def _apply_basic_ema(self, tracks: List[Dict[str, Any]], alpha: float = 0.3) -> List[Dict[str, Any]]:
        """Basic EMA implementation"""
        if not hasattr(self, '_ema_history'):
            self._ema_history = {}
        
        for track in tracks:
            track_id = track.get('track_id')
            if track_id is None:
                continue
            
            # Get position
            if 'bbox' in track:
                bbox = track['bbox']
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
            elif 'center' in track:
                center_x, center_y = track['center']
            else:
                continue
            
            # Update EMA
            if track_id not in self._ema_history:
                self._ema_history[track_id] = [center_x, center_y]
            
            prev_pos = self._ema_history[track_id]
            smoothed_x = alpha * center_x + (1 - alpha) * prev_pos[0]
            smoothed_y = alpha * center_y + (1 - alpha) * prev_pos[1]
            self._ema_history[track_id] = [smoothed_x, smoothed_y]
            
            # Update track
            if 'bbox' in track:
                dx = smoothed_x - center_x
                dy = smoothed_y - center_y
                track['bbox'] = [
                    bbox[0] + dx, bbox[1] + dy,
                    bbox[2] + dx, bbox[3] + dy
                ]
            elif 'center' in track:
                track['center'] = (smoothed_x, smoothed_y)
        
        return tracks

