"""
Enhanced Jersey Number OCR Module
Detects and recognizes jersey numbers with multi-frame consensus and team color context
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
from collections import defaultdict, Counter
import os
import sys

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Try to import OCR libraries
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# Try to import logger
try:
    from soccer_analysis.utils.logger_config import get_logger
except ImportError:
    try:
        from utils.logger_config import get_logger
    except ImportError:
        import logging
        get_logger = lambda name: logging.getLogger(name)

logger = get_logger("jersey_ocr")


class EnhancedJerseyOCR:
    """
    Enhanced Jersey Number OCR with improved accuracy and validation
    """
    
    def __init__(self, 
                 ocr_backend: str = "auto",
                 confidence_threshold: float = 0.5,
                 preprocess: bool = True,
                 use_gpu: bool = True):
        """
        Initialize Enhanced Jersey OCR
        
        Args:
            ocr_backend: OCR backend ("easyocr", "paddleocr", "tesseract", or "auto")
            confidence_threshold: Minimum confidence for accepting detection
            preprocess: Whether to preprocess images
            use_gpu: Whether to use GPU if available
        """
        self.confidence_threshold = confidence_threshold
        self.preprocess = preprocess
        self.ocr_backend = ocr_backend
        self.reader = None
        self.backend_name = None
        
        # Check for GPU availability
        try:
            import torch
            use_gpu = use_gpu and torch.cuda.is_available()
        except ImportError:
            use_gpu = False
        
        # Initialize OCR reader
        if ocr_backend == "auto":
            if EASYOCR_AVAILABLE:
                self.backend_name = "easyocr"
                self.reader = easyocr.Reader(['en'], gpu=use_gpu)
            elif PADDLEOCR_AVAILABLE:
                self.backend_name = "paddleocr"
                self.reader = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=use_gpu)
            elif TESSERACT_AVAILABLE:
                self.backend_name = "tesseract"
                self.reader = None
            else:
                logger.warning("No OCR backend available")
                self.backend_name = None
        elif ocr_backend == "easyocr" and EASYOCR_AVAILABLE:
            self.backend_name = "easyocr"
            self.reader = easyocr.Reader(['en'], gpu=use_gpu)
        elif ocr_backend == "paddleocr" and PADDLEOCR_AVAILABLE:
            self.backend_name = "paddleocr"
            self.reader = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=use_gpu)
        elif ocr_backend == "tesseract" and TESSERACT_AVAILABLE:
            self.backend_name = "tesseract"
            self.reader = None
        else:
            logger.warning(f"OCR backend '{ocr_backend}' not available")
            self.backend_name = None
        
        if self.backend_name:
            logger.info(f"Jersey OCR initialized with {self.backend_name}")
    
    def preprocess_jersey_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess jersey region for better OCR"""
        if image is None or image.size == 0:
            return image
        
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Resize if too small
        h, w = gray.shape
        if h < 32 or w < 32:
            scale = max(32 / h, 32 / w)
            new_h, new_w = int(h * scale), int(w * scale)
            gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        
        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Morphological cleanup
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def extract_jersey_region(self, frame: np.ndarray, bbox: List[float]) -> Optional[np.ndarray]:
        """Extract jersey region from player bounding box"""
        try:
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            h, w = frame.shape[:2]
            
            # Clamp to frame bounds
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            
            if x2 <= x1 or y2 <= y1:
                return None
            
            # Extract full bbox
            full_bbox = frame[y1:y2, x1:x2]
            bbox_height = y2 - y1
            
            # Jersey region: upper 30-60% of bbox
            jersey_top = int(bbox_height * 0.30)
            jersey_bottom = int(bbox_height * 0.60)
            
            if jersey_bottom <= jersey_top:
                return None
            
            jersey_region = full_bbox[jersey_top:jersey_bottom, :]
            return jersey_region
            
        except Exception as e:
            logger.warning(f"Error extracting jersey region: {e}")
            return None
    
    def detect_number(self, frame: np.ndarray, bbox: List[float]) -> Optional[Dict[str, Any]]:
        """
        Detect jersey number from player bounding box
        
        Returns:
            Dict with 'number', 'confidence', 'backend', or None
        """
        if self.backend_name is None:
            return None
        
        # Extract jersey region
        jersey_region = self.extract_jersey_region(frame, bbox)
        if jersey_region is None or jersey_region.size == 0:
            return None
        
        # Preprocess if enabled
        if self.preprocess:
            processed_image = self.preprocess_jersey_image(jersey_region)
        else:
            processed_image = jersey_region
        
        # Detect using selected backend
        result = None
        if self.backend_name == "easyocr":
            result = self._detect_easyocr(processed_image)
        elif self.backend_name == "paddleocr":
            result = self._detect_paddleocr(processed_image)
        elif self.backend_name == "tesseract":
            result = self._detect_tesseract(processed_image)
        
        if result:
            number, confidence = result
            return {
                'number': number,
                'confidence': confidence,
                'backend': self.backend_name
            }
        
        return None
    
    def _detect_easyocr(self, image: np.ndarray) -> Optional[Tuple[str, float]]:
        """Detect using EasyOCR"""
        try:
            results = self.reader.readtext(image)
            if not results:
                return None
            
            best_result = None
            best_confidence = 0.0
            
            for (bbox, text, confidence) in results:
                cleaned_text = ''.join(c for c in text if c.isalnum())
                if len(cleaned_text) <= 3 and cleaned_text.isdigit():
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_result = cleaned_text
            
            if best_result and best_confidence >= self.confidence_threshold:
                return (best_result, best_confidence)
            return None
        except Exception as e:
            logger.warning(f"EasyOCR error: {e}")
            return None
    
    def _detect_paddleocr(self, image: np.ndarray) -> Optional[Tuple[str, float]]:
        """Detect using PaddleOCR"""
        try:
            results = self.reader.ocr(image, cls=True)
            if not results or not results[0]:
                return None
            
            best_result = None
            best_confidence = 0.0
            
            for line in results[0]:
                if line and len(line) >= 2:
                    text_info = line[1]
                    if isinstance(text_info, tuple) and len(text_info) >= 2:
                        text, confidence = text_info[0], text_info[1]
                        cleaned_text = ''.join(c for c in text if c.isdigit())
                        if len(cleaned_text) <= 3 and cleaned_text:
                            if confidence > best_confidence:
                                best_confidence = confidence
                                best_result = cleaned_text
            
            if best_result and best_confidence >= self.confidence_threshold:
                return (best_result, best_confidence)
            return None
        except Exception as e:
            logger.warning(f"PaddleOCR error: {e}")
            return None
    
    def _detect_tesseract(self, image: np.ndarray) -> Optional[Tuple[str, float]]:
        """Detect using Tesseract"""
        try:
            config = '--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
            text = pytesseract.image_to_string(image, config=config)
            cleaned_text = ''.join(c for c in text if c.isdigit())
            if len(cleaned_text) <= 3 and cleaned_text:
                return (cleaned_text, 0.7)  # Default confidence
            return None
        except Exception as e:
            logger.warning(f"Tesseract error: {e}")
            return None


class MultiFrameJerseyOCR:
    """
    Multi-frame consensus OCR - reads jersey numbers across multiple frames
    for higher accuracy and confidence
    """
    
    def __init__(self, 
                 ocr_backend: str = "auto",
                 confidence_threshold: float = 0.5,
                 consensus_frames: int = 5,
                 consensus_threshold: float = 0.6):
        """
        Initialize multi-frame OCR
        
        Args:
            ocr_backend: OCR backend to use
            confidence_threshold: Minimum confidence per frame
            consensus_frames: Number of frames to consider for consensus
            consensus_threshold: Minimum fraction of frames that must agree
        """
        self.ocr = EnhancedJerseyOCR(ocr_backend, confidence_threshold)
        self.consensus_frames = consensus_frames
        self.consensus_threshold = consensus_threshold
        self.frame_history = defaultdict(list)  # track_id -> [(frame_num, number, confidence), ...]
    
    def detect_with_consensus(self, 
                             frame: np.ndarray,
                             detections: List[Dict[str, Any]],
                             frame_num: int) -> List[Dict[str, Any]]:
        """
        Detect jersey numbers with multi-frame consensus
        
        Args:
            frame: Current frame
            detections: List of detections with bbox and track_id
            frame_num: Current frame number
            
        Returns:
            Detections with jersey_number added
        """
        results = []
        
        for det in detections:
            track_id = det.get('track_id')
            bbox = det.get('bbox')
            
            if not bbox or track_id is None:
                results.append(det)
                continue
            
            # Detect number in current frame
            ocr_result = self.ocr.detect_number(frame, bbox)
            
            # Add to history
            if ocr_result:
                self.frame_history[track_id].append((
                    frame_num,
                    ocr_result['number'],
                    ocr_result['confidence']
                ))
            
            # Keep only recent frames
            self.frame_history[track_id] = [
                (f, n, c) for f, n, c in self.frame_history[track_id]
                if frame_num - f < self.consensus_frames
            ]
            
            # Get consensus
            consensus = self._get_consensus(track_id)
            
            if consensus:
                det['jersey_number'] = consensus['number']
                det['jersey_confidence'] = consensus['confidence']
                det['jersey_detection_frames'] = consensus['frame_count']
            else:
                # Still add single-frame result if available
                if ocr_result:
                    det['jersey_number'] = ocr_result['number']
                    det['jersey_confidence'] = ocr_result['confidence']
                    det['jersey_detection_frames'] = 1
            
            results.append(det)
        
        return results
    
    def _get_consensus(self, track_id: int) -> Optional[Dict[str, Any]]:
        """Get consensus jersey number from frame history"""
        history = self.frame_history.get(track_id, [])
        if len(history) < 2:
            return None
        
        # Count occurrences of each number
        number_counts = Counter()
        number_confidences = defaultdict(list)
        
        for frame_num, number, confidence in history:
            number_counts[number] += 1
            number_confidences[number].append(confidence)
        
        # Find most common number
        if not number_counts:
            return None
        
        most_common = number_counts.most_common(1)[0]
        number, count = most_common
        
        # Check if meets consensus threshold
        required_count = max(2, int(len(history) * self.consensus_threshold))
        if count < required_count:
            return None
        
        # Calculate average confidence
        avg_confidence = np.mean(number_confidences[number])
        
        return {
            'number': number,
            'confidence': float(avg_confidence),
            'frame_count': count,
            'total_frames': len(history)
        }
    
    def clear_history(self, track_id: Optional[int] = None):
        """Clear frame history for a track or all tracks"""
        if track_id is not None:
            self.frame_history.pop(track_id, None)
        else:
            self.frame_history.clear()

