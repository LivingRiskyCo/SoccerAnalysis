"""
Detection Module
Handles YOLO detection and ball detection with GPU acceleration and batching
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import os

# Try new structure imports first, fallback to legacy
try:
    from ...utils.logger_config import get_logger
    from ...utils.performance import PerformanceOptimizer
except ImportError:
    try:
        from SoccerID.utils.logger_config import get_logger
        from SoccerID.utils.performance import PerformanceOptimizer
    except ImportError:
        # Legacy fallback
        try:
            from logger_config import get_logger
            PerformanceOptimizer = None
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)
            PerformanceOptimizer = None

logger = get_logger("detector")

# Conditional imports
try:
    from ultralytics import YOLO
    import supervision as sv
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("YOLO dependencies not available")

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class Detector:
    """Handles object detection using YOLO with GPU acceleration and batching"""
    
    def __init__(self, model_path: str = "yolo11n.pt", 
                 confidence_threshold: float = 0.25,
                 iou_threshold: float = 0.45,
                 use_gpu: bool = True,
                 batch_size: int = 8,
                 device: Optional[str] = None):
        """
        Initialize detector
        
        Args:
            model_path: Path to YOLO model file
            confidence_threshold: Detection confidence threshold
            iou_threshold: IOU threshold for NMS
            use_gpu: Whether to use GPU if available
            batch_size: Batch size for batch processing
            device: Device to use ('cuda', 'cpu', or None for auto)
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.model = None
        self.batch_size = batch_size
        self.use_gpu = use_gpu
        
        # Auto-detect device if not specified
        if device is None:
            if use_gpu and TORCH_AVAILABLE and torch.cuda.is_available():
                self.device = 'cuda'
            else:
                self.device = 'cpu'
        else:
            self.device = device
        
        # Get optimal settings if available
        if PerformanceOptimizer:
            hardware_info = PerformanceOptimizer.detect_hardware()
            optimal = PerformanceOptimizer.get_optimal_settings(hardware_info)
            if self.batch_size == 8:  # Only override if using default
                self.batch_size = optimal.get('batch_size', 8)
        
        if YOLO_AVAILABLE:
            self._load_model()
        else:
            logger.warning("YOLO not available - detection will be disabled")
    
    def _load_model(self):
        """Load YOLO model with GPU support"""
        try:
            if os.path.exists(self.model_path):
                self.model = YOLO(self.model_path)
                # Move model to device if GPU available
                if self.device == 'cuda' and TORCH_AVAILABLE:
                    try:
                        # YOLO models automatically use GPU if available
                        # But we can verify
                        if torch.cuda.is_available():
                            logger.info(f"YOLO model will use GPU: {torch.cuda.get_device_name(0)}")
                        else:
                            logger.info("YOLO model will use CPU")
                    except:
                        pass
                logger.info(f"Loaded YOLO model: {self.model_path} (device: {self.device})")
            else:
                logger.warning(f"YOLO model not found: {self.model_path}")
        except Exception as e:
            logger.error(f"Error loading YOLO model: {e}", exc_info=True)
            self.model = None
    
    def detect_players(self, frame: np.ndarray, 
                      min_player_height: int = 30,
                      max_player_height: int = 200,
                      field_mask: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
        """
        Detect players in frame with soccer-specific filtering for improved accuracy
        
        Args:
            frame: Input frame
            min_player_height: Minimum player height in pixels (default 30)
            max_player_height: Maximum player height in pixels (default 200)
            field_mask: Optional field mask to filter detections (1 = on field, 0 = off field)
            
        Returns:
            List of detection dictionaries with keys: bbox, confidence, class_id, height, width
        """
        if not YOLO_AVAILABLE or self.model is None:
            return []
        
        try:
            # Run YOLO detection with slightly lower threshold for better recall
            # We'll filter more strictly after detection
            detection_conf = max(0.2, self.confidence_threshold - 0.05)
            results = self.model(frame, conf=detection_conf, iou=self.iou_threshold, verbose=False)
            
            detections = []
            _, frame_width = frame.shape[:2]
            
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Filter for person class (class 0 in COCO)
                    if int(box.cls) == 0:
                        xyxy = box.xyxy[0].cpu().numpy()
                        confidence = float(box.conf[0].cpu().numpy())
                        
                        # Calculate bbox dimensions
                        x1, y1, x2, y2 = xyxy
                        width = x2 - x1
                        height = y2 - y1
                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        
                        # Filter 1: Size filtering (soccer players are typically 30-200px tall)
                        if height < min_player_height or height > max_player_height:
                            continue
                        
                        # Filter 2: Aspect ratio (players are taller than wide)
                        aspect_ratio = height / width if width > 0 else 0
                        if aspect_ratio < 1.2:  # Too wide, probably not a player
                            continue
                        
                        # Filter 3: Position filtering (if field mask available)
                        if field_mask is not None:
                            try:
                                mask_y = int(np.clip(center_y, 0, field_mask.shape[0] - 1))
                                mask_x = int(np.clip(center_x, 0, field_mask.shape[1] - 1))
                                if not field_mask[mask_y, mask_x]:
                                    continue  # Outside field
                            except (IndexError, ValueError):
                                pass  # Skip mask check if coordinates invalid
                        
                        # Filter 4: Confidence adjustment based on size and position
                        # Larger detections in center are more likely players
                        size_score = min(height / 100.0, 1.0)  # Normalize to 0-1
                        center_score = 1.0 - abs(center_x - frame_width/2) / (frame_width/2) if frame_width > 0 else 1.0
                        center_score = max(0.5, center_score)  # Don't penalize too much
                        adjusted_confidence = confidence * (0.7 + 0.3 * size_score * center_score)
                        
                        # Final threshold check
                        if adjusted_confidence >= self.confidence_threshold:
                            detections.append({
                                'bbox': xyxy.tolist(),
                                'confidence': adjusted_confidence,
                                'class_id': 0,
                                'height': height,
                                'width': width,
                                'center': (center_x, center_y)
                            })
            
            return detections
            
        except Exception as e:
            logger.error(f"Error detecting players: {e}", exc_info=True)
            return []
    
    def detect_players_batch(self, frames: List[np.ndarray], 
                            min_player_height: int = 30,
                            max_player_height: int = 200,
                            field_mask: Optional[np.ndarray] = None) -> List[List[Dict[str, Any]]]:
        """
        Detect players in multiple frames using optimized batch processing
        
        Args:
            frames: List of input frames
            min_player_height: Minimum player height in pixels
            max_player_height: Maximum player height in pixels
            field_mask: Optional field mask to filter detections
            
        Returns:
            List of detection lists (one per frame)
        """
        if not YOLO_AVAILABLE or self.model is None or not frames:
            return [[] for _ in frames]
        
        try:
            # Use slightly lower threshold for batch processing (we'll filter after)
            detection_conf = max(0.2, self.confidence_threshold - 0.05)
            
            # Process in batches
            all_detections = []
            for i in range(0, len(frames), self.batch_size):
                batch_frames = frames[i:i+self.batch_size]
                
                # Run YOLO detection on batch (YOLO handles batches efficiently)
                results = self.model(batch_frames, conf=detection_conf, 
                                   iou=self.iou_threshold, verbose=False)
                
                # Process results with filtering
                for frame_idx, result in enumerate(results):
                    frame = batch_frames[frame_idx]
                    frame_height, frame_width = frame.shape[:2]
                    detections = []
                    
                    if hasattr(result, 'boxes') and result.boxes is not None:
                        boxes = result.boxes
                        for box in boxes:
                            # Filter for person class (class 0 in COCO)
                            if int(box.cls) == 0:
                                xyxy = box.xyxy[0].cpu().numpy()
                                confidence = float(box.conf[0].cpu().numpy())
                                
                                # Calculate bbox dimensions
                                x1, y1, x2, y2 = xyxy
                                width = x2 - x1
                                height = y2 - y1
                                center_x = (x1 + x2) / 2
                                center_y = (y1 + y2) / 2
                                
                                # Apply filters (same as detect_players)
                                if height < min_player_height or height > max_player_height:
                                    continue
                                
                                aspect_ratio = height / width if width > 0 else 0
                                if aspect_ratio < 1.2:
                                    continue
                                
                                if field_mask is not None:
                                    try:
                                        mask_y = int(np.clip(center_y, 0, field_mask.shape[0] - 1))
                                        mask_x = int(np.clip(center_x, 0, field_mask.shape[1] - 1))
                                        if not field_mask[mask_y, mask_x]:
                                            continue
                                    except (IndexError, ValueError):
                                        pass
                                
                                # Confidence adjustment
                                size_score = min(height / 100.0, 1.0)
                                center_score = 1.0 - abs(center_x - frame_width/2) / (frame_width/2) if frame_width > 0 else 1.0
                                center_score = max(0.5, center_score)
                                adjusted_confidence = confidence * (0.7 + 0.3 * size_score * center_score)
                                
                                if adjusted_confidence >= self.confidence_threshold:
                                    detections.append({
                                        'bbox': xyxy.tolist(),
                                        'confidence': adjusted_confidence,
                                        'class_id': 0,
                                        'height': height,
                                        'width': width,
                                        'center': (center_x, center_y)
                                    })
                    all_detections.append(detections)
            
            # Ensure we return one list per input frame
            while len(all_detections) < len(frames):
                all_detections.append([])
            
            return all_detections[:len(frames)]
            
        except Exception as e:
            logger.error(f"Error in batch detection: {e}", exc_info=True)
            # Fallback to individual detection
            return [self.detect_players(frame, min_player_height, max_player_height, field_mask) for frame in frames]
    
    def detect_ball(self, frame: np.ndarray, 
                   min_radius: int = 5, 
                   max_radius: int = 50,
                   hsv_ranges: Optional[Dict[str, Tuple]] = None,
                   use_yolo: bool = True,
                   yolo_confidence: float = 0.3,
                   **kwargs) -> Optional[Dict[str, Any]]:
        """
        Detect ball in frame using YOLO first (class 32 = sports ball), then HSV fallback.
        
        Args:
            frame: Input frame
            min_radius: Minimum ball radius in pixels
            max_radius: Maximum ball radius in pixels
            hsv_ranges: HSV color ranges for ball detection
            use_yolo: Whether to use YOLO ball detection first (default True)
            yolo_confidence: YOLO confidence threshold for ball detection (default 0.3)
            **kwargs: Additional arguments for ball detection (fps, field_calibration, etc.)
            
        Returns:
            Ball detection dictionary with keys: center, radius, confidence, method or None
        """
        # Try YOLO ball detection first (class 32 = sports ball)
        if use_yolo and YOLO_AVAILABLE and self.model is not None:
            try:
                results = self.model(frame, conf=yolo_confidence, verbose=False)
                
                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        if int(box.cls) == 32:  # Sports ball class
                            xyxy = box.xyxy[0].cpu().numpy()
                            confidence = float(box.conf[0].cpu().numpy())
                            
                            # Calculate center and size
                            x1, y1, x2, y2 = xyxy
                            center = ((x1 + x2) / 2, (y1 + y2) / 2)
                            width = x2 - x1
                            height = y2 - y1
                            radius = min(width, height) / 2
                            
                            # Size check (ball should be 5-50px radius)
                            if min_radius <= radius <= max_radius:
                                logger.debug(f"Ball detected via YOLO at {center} with confidence {confidence:.2f}")
                                return {
                                    'center': center,
                                    'radius': radius,
                                    'confidence': confidence,
                                    'method': 'yolo'
                                }
            except Exception as e:
                logger.debug(f"YOLO ball detection failed: {e}, falling back to HSV")
        
        # Fallback to HSV detection
        try:
            # Import from legacy during migration
            import sys
            import os
            legacy_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'legacy')
            if legacy_path not in sys.path:
                sys.path.insert(0, legacy_path)
            
            from combined_analysis_optimized import track_ball_in_frame
            
            # Prepare arguments for track_ball_in_frame
            from collections import deque
            pts = kwargs.get('pts', deque())
            buffer = kwargs.get('buffer', 64)
            edge_margin = kwargs.get('edge_margin', 50)
            show_trail = kwargs.get('show_trail', False)
            ball_velocity = kwargs.get('ball_velocity', None)
            fps = kwargs.get('fps', 60)
            field_calibration = kwargs.get('field_calibration', None)
            frame_num = kwargs.get('frame_num', 0)
            seed_ball_positions = kwargs.get('seed_ball_positions', None)
            ball_history = kwargs.get('ball_history', None)
            ball_last_seen_frame = kwargs.get('ball_last_seen_frame', -1)
            homography_matrix = kwargs.get('homography_matrix', None)
            homography_inv = kwargs.get('homography_inv', None)
            trail_length = kwargs.get('trail_length', 20)
            
            # Call legacy function
            _, center, ball_detected, velocity = track_ball_in_frame(
                frame.copy(), pts, buffer, min_radius, max_radius, edge_margin,
                show_trail, ball_velocity, fps, field_calibration, frame_num,
                seed_ball_positions, ball_history, ball_last_seen_frame,
                homography_matrix, homography_inv, trail_length
            )
            
            if ball_detected and center:
                return {
                    'center': center,
                    'radius': min_radius + (max_radius - min_radius) // 2,  # Estimate
                    'confidence': 0.8 if ball_detected else 0.0,  # Lower confidence for HSV
                    'velocity': velocity,
                    'method': 'hsv'
                }
            return None
            
        except ImportError:
            logger.warning("Legacy ball detection not available - ball detection disabled")
            return None
        except Exception as e:
            logger.error(f"Error in ball detection: {e}", exc_info=True)
            return None

