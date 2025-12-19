"""
Jersey Number OCR Module
Detects and recognizes jersey numbers from player bounding boxes using OCR.

Supports multiple OCR backends:
- EasyOCR (recommended, good accuracy)
- PaddleOCR (fast, good for digits)
- Tesseract (fallback)
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict
import os

# Try to import OCR libraries
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("⚠ EasyOCR not available. Install with: pip install easyocr")

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    print("⚠ PaddleOCR not available. Install with: pip install paddlepaddle paddleocr")

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("⚠ Tesseract not available. Install with: pip install pytesseract")


class JerseyNumberOCR:
    """
    Jersey Number OCR detector for recognizing player jersey numbers.
    
    Uses multiple OCR backends with fallback support for maximum compatibility.
    """
    
    def __init__(self, 
                 ocr_backend: str = "auto",  # "easyocr", "paddleocr", "tesseract", or "auto"
                 confidence_threshold: float = 0.5,
                 preprocess: bool = True):
        """
        Initialize Jersey Number OCR
        
        Args:
            ocr_backend: OCR backend to use ("easyocr", "paddleocr", "tesseract", or "auto")
            confidence_threshold: Minimum confidence for accepting a detection
            preprocess: Whether to preprocess images before OCR
        """
        self.confidence_threshold = confidence_threshold
        self.preprocess = preprocess
        self.ocr_backend = ocr_backend
        
        # Initialize OCR reader based on backend
        self.reader = None
        self.backend_name = None
        
        # Check for GPU availability
        try:
            import torch
            use_gpu = torch.cuda.is_available()
        except ImportError:
            use_gpu = False
        
        if ocr_backend == "auto":
            # Auto-select best available backend
            if EASYOCR_AVAILABLE:
                self.backend_name = "easyocr"
                self.reader = easyocr.Reader(['en'], gpu=use_gpu)
            elif PADDLEOCR_AVAILABLE:
                self.backend_name = "paddleocr"
                self.reader = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=use_gpu)
            elif TESSERACT_AVAILABLE:
                self.backend_name = "tesseract"
                self.reader = None  # Tesseract doesn't need initialization
            else:
                print("⚠ No OCR backend available. Jersey number detection will be disabled.")
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
            print(f"⚠ OCR backend '{ocr_backend}' not available. Jersey number detection will be disabled.")
            self.backend_name = None
        
        if self.backend_name:
            print(f"✓ Jersey Number OCR initialized with {self.backend_name}")
    
    def preprocess_jersey_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess jersey region image for better OCR accuracy
        
        Args:
            image: Input jersey region image (BGR format)
            
        Returns:
            Preprocessed image (grayscale, enhanced)
        """
        if image is None or image.size == 0:
            return image
        
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Resize if too small (OCR works better on larger images)
        h, w = gray.shape
        if h < 32 or w < 32:
            scale = max(32 / h, 32 / w)
            new_h, new_w = int(h * scale), int(w * scale)
            gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        
        # Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Optional: Apply thresholding for better digit separation
        # Use adaptive threshold to handle varying lighting
        thresh = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Optional: Morphological operations to clean up
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def extract_jersey_region(self, frame: np.ndarray, bbox: List[float]) -> Optional[np.ndarray]:
        """
        Extract jersey region from player bounding box
        
        Args:
            frame: Full frame image (BGR format)
            bbox: Bounding box [x1, y1, x2, y2]
            
        Returns:
            Cropped jersey region image or None
        """
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
            
            # Jersey region: upper 30-60% of bbox (torso area where numbers are)
            jersey_top = int(bbox_height * 0.30)
            jersey_bottom = int(bbox_height * 0.60)
            
            if jersey_bottom <= jersey_top:
                return None
            
            # Extract jersey region
            jersey_region = full_bbox[jersey_top:jersey_bottom, :]
            
            return jersey_region
            
        except Exception as e:
            print(f"⚠ Error extracting jersey region: {e}")
            return None
    
    def detect_number_easyocr(self, image: np.ndarray) -> Optional[Tuple[str, float]]:
        """Detect jersey number using EasyOCR"""
        try:
            results = self.reader.readtext(image)
            
            if not results:
                return None
            
            # Filter for digit-only results and get highest confidence
            best_result = None
            best_confidence = 0.0
            
            for (bbox, text, confidence) in results:
                # Clean text: remove spaces, keep only digits and letters
                cleaned_text = ''.join(c for c in text if c.isalnum())
                
                # Prefer short numbers (1-2 digits, sometimes 3 for 100+)
                if len(cleaned_text) <= 3 and cleaned_text.isdigit():
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_result = cleaned_text
            
            if best_result and best_confidence >= self.confidence_threshold:
                return (best_result, best_confidence)
            
            return None
            
        except Exception as e:
            print(f"⚠ EasyOCR error: {e}")
            return None
    
    def detect_number_paddleocr(self, image: np.ndarray) -> Optional[Tuple[str, float]]:
        """Detect jersey number using PaddleOCR"""
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
                    else:
                        continue
                    
                    # Clean text: keep only digits
                    cleaned_text = ''.join(c for c in text if c.isdigit())
                    
                    # Prefer short numbers (1-3 digits)
                    if len(cleaned_text) <= 3 and cleaned_text:
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_result = cleaned_text
            
            if best_result and best_confidence >= self.confidence_threshold:
                return (best_result, best_confidence)
            
            return None
            
        except Exception as e:
            print(f"⚠ PaddleOCR error: {e}")
            return None
    
    def detect_number_tesseract(self, image: np.ndarray) -> Optional[Tuple[str, float]]:
        """Detect jersey number using Tesseract"""
        try:
            # Tesseract configuration for digits only
            config = '--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
            
            text = pytesseract.image_to_string(image, config=config)
            
            # Clean and extract digits
            cleaned_text = ''.join(c for c in text if c.isdigit())
            
            if len(cleaned_text) <= 3 and cleaned_text:
                # Tesseract doesn't provide confidence directly, use default
                return (cleaned_text, 0.7)  # Default confidence
            
            return None
            
        except Exception as e:
            print(f"⚠ Tesseract error: {e}")
            return None
    
    def detect_jersey_number(self, 
                            frame: np.ndarray, 
                            bbox: List[float]) -> Optional[Dict[str, any]]:
        """
        Detect jersey number from player bounding box
        
        Args:
            frame: Full frame image (BGR format)
            bbox: Bounding box [x1, y1, x2, y2]
            
        Returns:
            Dict with 'number', 'confidence', 'backend', or None if not detected
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
        
        # Detect number using selected backend
        result = None
        if self.backend_name == "easyocr":
            result = self.detect_number_easyocr(processed_image)
        elif self.backend_name == "paddleocr":
            result = self.detect_number_paddleocr(processed_image)
        elif self.backend_name == "tesseract":
            result = self.detect_number_tesseract(processed_image)
        
        if result:
            number, confidence = result
            return {
                'number': number,
                'confidence': confidence,
                'backend': self.backend_name
            }
        
        return None
    
    def batch_detect(self, 
                    frame: np.ndarray, 
                    bboxes: List[List[float]]) -> List[Optional[Dict[str, any]]]:
        """
        Detect jersey numbers for multiple players in batch
        
        Args:
            frame: Full frame image
            bboxes: List of bounding boxes [x1, y1, x2, y2]
            
        Returns:
            List of detection results (same length as bboxes)
        """
        results = []
        for bbox in bboxes:
            result = self.detect_jersey_number(frame, bbox)
            results.append(result)
        return results
