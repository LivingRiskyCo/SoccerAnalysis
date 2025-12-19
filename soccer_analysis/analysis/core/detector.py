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
        from soccer_analysis.utils.logger_config import get_logger
        from soccer_analysis.utils.performance import PerformanceOptimizer
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
    
    def detect_players(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect players in frame
        
        Args:
            frame: Input frame
            
        Returns:
            List of detection dictionaries with keys: bbox, confidence, class_id
        """
        if not YOLO_AVAILABLE or self.model is None:
            return []
        
        try:
            # Run YOLO detection
            results = self.model(frame, conf=self.confidence_threshold, iou=self.iou_threshold, verbose=False)
            
            detections = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Filter for person class (class 0 in COCO)
                    if int(box.cls) == 0:
                        xyxy = box.xyxy[0].cpu().numpy()
                        confidence = float(box.conf[0].cpu().numpy())
                        
                        detections.append({
                            'bbox': xyxy.tolist(),
                            'confidence': confidence,
                            'class_id': 0
                        })
            
            return detections
            
        except Exception as e:
            logger.error(f"Error detecting players: {e}", exc_info=True)
            return []
    
    def detect_players_batch(self, frames: List[np.ndarray]) -> List[List[Dict[str, Any]]]:
        """
        Detect players in multiple frames using batch processing
        
        Args:
            frames: List of input frames
            
        Returns:
            List of detection lists (one per frame)
        """
        if not YOLO_AVAILABLE or self.model is None or not frames:
            return [[] for _ in frames]
        
        try:
            # Process in batches
            all_detections = []
            for i in range(0, len(frames), self.batch_size):
                batch_frames = frames[i:i+self.batch_size]
                
                # Run YOLO detection on batch
                # Note: YOLO's predict can handle batches, but we need to format correctly
                results = self.model(batch_frames, conf=self.confidence_threshold, 
                                   iou=self.iou_threshold, verbose=False)
                
                # Process results
                for result in results:
                    detections = []
                    if hasattr(result, 'boxes') and result.boxes is not None:
                        boxes = result.boxes
                        for box in boxes:
                            # Filter for person class (class 0 in COCO)
                            if int(box.cls) == 0:
                                xyxy = box.xyxy[0].cpu().numpy()
                                confidence = float(box.conf[0].cpu().numpy())
                                
                                detections.append({
                                    'bbox': xyxy.tolist(),
                                    'confidence': confidence,
                                    'class_id': 0
                                })
                    all_detections.append(detections)
            
            # Ensure we return one list per input frame
            while len(all_detections) < len(frames):
                all_detections.append([])
            
            return all_detections[:len(frames)]
            
        except Exception as e:
            logger.error(f"Error in batch detection: {e}", exc_info=True)
            # Fallback to individual detection
            return [self.detect_players(frame) for frame in frames]
    
    def detect_ball(self, frame: np.ndarray, 
                   min_radius: int = 5, 
                   max_radius: int = 50,
                   hsv_ranges: Optional[Dict[str, Tuple]] = None,
                   **kwargs) -> Optional[Dict[str, Any]]:
        """
        Detect ball in frame using HSV color detection.
        
        Note: Full implementation is in legacy/combined_analysis_optimized.py
        This method provides a fallback to the legacy implementation.
        
        Args:
            frame: Input frame
            min_radius: Minimum ball radius in pixels
            max_radius: Maximum ball radius in pixels
            hsv_ranges: HSV color ranges for ball detection
            **kwargs: Additional arguments for ball detection (fps, field_calibration, etc.)
            
        Returns:
            Ball detection dictionary with keys: center, radius, confidence or None
        """
        # Try to import and use legacy ball detection function
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
            result_frame, center, ball_detected, velocity = track_ball_in_frame(
                frame.copy(), pts, buffer, min_radius, max_radius, edge_margin,
                show_trail, ball_velocity, fps, field_calibration, frame_num,
                seed_ball_positions, ball_history, ball_last_seen_frame,
                homography_matrix, homography_inv, trail_length
            )
            
            if ball_detected and center:
                return {
                    'center': center,
                    'radius': min_radius + (max_radius - min_radius) // 2,  # Estimate
                    'confidence': 1.0 if ball_detected else 0.0,
                    'velocity': velocity
                }
            return None
            
        except ImportError:
            logger.warning("Legacy ball detection not available - ball detection disabled")
            return None
        except Exception as e:
            logger.error(f"Error in ball detection: {e}", exc_info=True)
            return None

