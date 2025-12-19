"""
Re-ID Filter Module
Pre-filters low-quality detections before Re-ID processing to improve accuracy.

Based on: "Approaches to Improve the Quality of Person Re-Identification for Practical Use"
Mamedov et al., Sensors 2023
"""

import cv2
import numpy as np
from typing import Tuple, Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class ReIDFilterModule:
    """
    Filter module for pre-filtering low-quality detections before Re-ID processing.
    
    Filters out:
    - Blurry images (Laplacian variance)
    - Too small bounding boxes
    - Low confidence detections
    - Heavily occluded detections
    - Poor lighting/contrast
    """
    
    def __init__(self,
                 min_bbox_area: int = 200,
                 min_bbox_width: int = 10,
                 min_bbox_height: int = 15,
                 min_confidence: float = 0.25,
                 max_blur_threshold: float = 30.0,  # More lenient default (was 100.0, too strict for soccer videos)
                 min_contrast_threshold: float = 20.0,
                 enable_blur_check: bool = True,
                 enable_contrast_check: bool = True,
                 enable_occlusion_check: bool = True):
        """
        Initialize Re-ID Filter Module
        
        Args:
            min_bbox_area: Minimum bounding box area in pixels (default: 200)
            min_bbox_width: Minimum bounding box width in pixels (default: 10)
            min_bbox_height: Minimum bounding box height in pixels (default: 15)
            min_confidence: Minimum detection confidence (default: 0.25)
            max_blur_threshold: Maximum blur score (Laplacian variance) - lower = more blurry (default: 100.0)
            min_contrast_threshold: Minimum contrast (std dev of pixel values) (default: 20.0)
            enable_blur_check: Enable blur detection (default: True)
            enable_contrast_check: Enable contrast check (default: True)
            enable_occlusion_check: Enable occlusion estimation (default: True)
        """
        self.min_bbox_area = min_bbox_area
        self.min_bbox_width = min_bbox_width
        self.min_bbox_height = min_bbox_height
        self.min_confidence = min_confidence
        self.max_blur_threshold = max_blur_threshold
        self.min_contrast_threshold = min_contrast_threshold
        self.enable_blur_check = enable_blur_check
        self.enable_contrast_check = enable_contrast_check
        self.enable_occlusion_check = enable_occlusion_check
        
        # Statistics
        self.stats = {
            'total_checked': 0,
            'passed': 0,
            'filtered_bbox_too_small': 0,
            'filtered_bbox_too_short': 0,
            'filtered_low_confidence': 0,
            'filtered_too_blurry': 0,
            'filtered_low_contrast': 0,
            'filtered_heavily_occluded': 0,
            'filtered_invalid_crop': 0
        }
    
    def filter_detection(self, 
                        frame: np.ndarray,
                        bbox: Tuple[float, float, float, float],
                        confidence: float,
                        occlusion_ratio: Optional[float] = None) -> Tuple[bool, str]:
        """
        Filter a single detection
        
        Args:
            frame: Full frame image (BGR)
            bbox: Bounding box (x1, y1, x2, y2)
            confidence: Detection confidence score
            occlusion_ratio: Optional occlusion ratio (0.0 = no occlusion, 1.0 = fully occluded)
        
        Returns:
            (passed: bool, reason: str)
        """
        self.stats['total_checked'] += 1
        
        x1, y1, x2, y2 = bbox
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        
        # Check bbox size
        width = x2 - x1
        height = y2 - y1
        area = width * height
        
        if area < self.min_bbox_area:
            self.stats['filtered_bbox_too_small'] += 1
            return False, "bbox_too_small"
        
        if width < self.min_bbox_width:
            self.stats['filtered_bbox_too_small'] += 1
            return False, "bbox_too_narrow"
        
        if height < self.min_bbox_height:
            self.stats['filtered_bbox_too_short'] += 1
            return False, "bbox_too_short"
        
        # Check confidence
        if confidence < self.min_confidence:
            self.stats['filtered_low_confidence'] += 1
            return False, "low_confidence"
        
        # Check if bbox is within frame bounds
        frame_h, frame_w = frame.shape[:2]
        if x1 < 0 or y1 < 0 or x2 > frame_w or y2 > frame_h:
            # Clamp bbox to frame bounds
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(frame_w, x2)
            y2 = min(frame_h, y2)
        
        # Extract crop for quality checks
        crop = frame[y1:y2, x1:x2]
        
        if crop.size == 0 or crop.shape[0] < 5 or crop.shape[1] < 5:
            self.stats['filtered_invalid_crop'] += 1
            return False, "invalid_crop"
        
        # Check blur (Laplacian variance)
        if self.enable_blur_check:
            try:
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
                
                if blur_score < self.max_blur_threshold:
                    self.stats['filtered_too_blurry'] += 1
                    return False, "too_blurry"
            except Exception as e:
                logger.warning(f"Blur check failed: {e}")
        
        # Check contrast (standard deviation of pixel values)
        if self.enable_contrast_check:
            try:
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                contrast_score = np.std(gray)
                
                if contrast_score < self.min_contrast_threshold:
                    self.stats['filtered_low_contrast'] += 1
                    return False, "low_contrast"
            except Exception as e:
                logger.warning(f"Contrast check failed: {e}")
        
        # Check occlusion (if provided)
        if self.enable_occlusion_check and occlusion_ratio is not None:
            if occlusion_ratio > 0.5:  # More than 50% occluded
                self.stats['filtered_heavily_occluded'] += 1
                return False, "heavily_occluded"
        
        # All checks passed
        self.stats['passed'] += 1
        return True, "passed"
    
    def filter_detections_batch(self,
                                frame: np.ndarray,
                                detections,
                                confidences: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Filter a batch of detections
        
        Args:
            frame: Full frame image (BGR)
            detections: Array of bounding boxes (N x 4) or supervision Detections object
            confidences: Optional array of confidence scores (N,)
        
        Returns:
            (filtered_detections, quality_mask)
            quality_mask: Boolean array indicating which detections passed
        """
        # Handle supervision Detections object
        if hasattr(detections, 'xyxy'):
            bboxes = detections.xyxy
            if confidences is None:
                confidences = detections.confidence if hasattr(detections, 'confidence') else np.ones(len(bboxes))
        else:
            bboxes = np.array(detections)
            if confidences is None:
                confidences = np.ones(len(bboxes))
        
        quality_mask = np.zeros(len(bboxes), dtype=bool)
        
        for i, bbox in enumerate(bboxes):
            confidence = float(confidences[i]) if i < len(confidences) else 1.0
            passed, reason = self.filter_detection(frame, bbox, confidence)
            quality_mask[i] = passed
        
        filtered_detections = bboxes[quality_mask]
        
        return filtered_detections, quality_mask
    
    def is_feature_quality_sufficient(self, features: np.ndarray) -> bool:
        """
        Check if extracted features are of sufficient quality
        
        Args:
            features: Feature vector (1D array)
        
        Returns:
            True if features are valid, False otherwise
        """
        if features is None or len(features) == 0:
            return False
        
        # Check for NaN or Inf values
        if np.any(np.isnan(features)) or np.any(np.isinf(features)):
            return False
        
        # Check feature magnitude (should be normalized, but check for extreme values)
        feature_norm = np.linalg.norm(features)
        if feature_norm < 1e-6 or feature_norm > 1e6:
            return False
        
        return True
    
    def get_statistics(self) -> Dict[str, int]:
        """Get filter statistics"""
        return self.stats.copy()
    
    def reset_statistics(self):
        """Reset filter statistics"""
        self.stats = {
            'total_checked': 0,
            'passed': 0,
            'filtered_bbox_too_small': 0,
            'filtered_bbox_too_short': 0,
            'filtered_low_confidence': 0,
            'filtered_too_blurry': 0,
            'filtered_low_contrast': 0,
            'filtered_heavily_occluded': 0,
            'filtered_invalid_crop': 0
        }
    
    def print_statistics(self):
        """Print filter statistics"""
        total = self.stats['total_checked']
        if total == 0:
            print("No detections checked yet")
            return
        
        passed = self.stats['passed']
        pass_rate = 100.0 * passed / total if total > 0 else 0.0
        
        print(f"\n📊 Re-ID Filter Module Statistics:")
        print(f"   Total checked: {total}")
        print(f"   Passed: {passed} ({pass_rate:.1f}%)")
        print(f"   Filtered: {total - passed} ({100.0 - pass_rate:.1f}%)")
        print(f"\n   Filter reasons:")
        print(f"   - Bbox too small: {self.stats['filtered_bbox_too_small']}")
        print(f"   - Bbox too short: {self.stats['filtered_bbox_too_short']}")
        print(f"   - Low confidence: {self.stats['filtered_low_confidence']}")
        print(f"   - Too blurry: {self.stats['filtered_too_blurry']}")
        print(f"   - Low contrast: {self.stats['filtered_low_contrast']}")
        print(f"   - Heavily occluded: {self.stats['filtered_heavily_occluded']}")
        print(f"   - Invalid crop: {self.stats['filtered_invalid_crop']}")

