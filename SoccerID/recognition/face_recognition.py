"""
Face Recognition Module
Detects and recognizes player faces for improved identification
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
from collections import defaultdict
import os
import sys

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Try to import face recognition libraries
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

try:
    import dlib
    DLIB_AVAILABLE = True
except ImportError:
    DLIB_AVAILABLE = False

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

logger = get_logger("face_recognition")


class FaceRecognizer:
    """
    Face Recognition System for Player Identification
    Detects faces in player bounding boxes and matches them to known players
    """
    
    def __init__(self, 
                 backend: str = "auto",
                 model_name: str = "VGG-Face",
                 confidence_threshold: float = 0.6,
                 use_gpu: bool = True):
        """
        Initialize Face Recognizer
        
        Args:
            backend: Recognition backend ("face_recognition", "deepface", "dlib", or "auto")
            model_name: Model name for DeepFace (VGG-Face, Facenet, OpenFace, etc.)
            confidence_threshold: Minimum confidence for accepting recognition
            use_gpu: Whether to use GPU if available
        """
        self.confidence_threshold = confidence_threshold
        self.backend = backend
        self.model_name = model_name
        self.backend_name = None
        self.recognizer = None
        
        # Face encodings database: player_id -> [encodings]
        self.face_database: Dict[str, List[np.ndarray]] = defaultdict(list)
        
        # Initialize backend
        if backend == "auto":
            if FACE_RECOGNITION_AVAILABLE:
                self.backend_name = "face_recognition"
            elif DEEPFACE_AVAILABLE:
                self.backend_name = "deepface"
            elif DLIB_AVAILABLE:
                self.backend_name = "dlib"
            else:
                logger.warning("No face recognition backend available")
                self.backend_name = None
        elif backend == "face_recognition" and FACE_RECOGNITION_AVAILABLE:
            self.backend_name = "face_recognition"
        elif backend == "deepface" and DEEPFACE_AVAILABLE:
            self.backend_name = "deepface"
        elif backend == "dlib" and DLIB_AVAILABLE:
            self.backend_name = "dlib"
        else:
            logger.warning(f"Face recognition backend '{backend}' not available")
            self.backend_name = None
        
        if self.backend_name:
            logger.info(f"Face recognition initialized with {self.backend_name}")
    
    def extract_face_region(self, frame: np.ndarray, bbox: List[float]) -> Optional[np.ndarray]:
        """
        Extract face region from player bounding box
        
        Args:
            frame: Input frame
            bbox: Player bounding box [x1, y1, x2, y2]
            
        Returns:
            Face region image or None
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
            
            # Face region: upper 10-40% of bbox (head area)
            face_top = int(bbox_height * 0.10)
            face_bottom = int(bbox_height * 0.40)
            
            if face_bottom <= face_top:
                return None
            
            face_region = full_bbox[face_top:face_bottom, :]
            
            # Resize if too small (minimum 64x64 for face recognition)
            if face_region.shape[0] < 64 or face_region.shape[1] < 64:
                scale = max(64 / face_region.shape[0], 64 / face_region.shape[1])
                new_h, new_w = int(face_region.shape[0] * scale), int(face_region.shape[1] * scale)
                face_region = cv2.resize(face_region, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            
            return face_region
            
        except Exception as e:
            logger.warning(f"Error extracting face region: {e}")
            return None
    
    def detect_face(self, frame: np.ndarray, bbox: List[float]) -> Optional[Dict[str, Any]]:
        """
        Detect face in player bounding box
        
        Args:
            frame: Input frame
            bbox: Player bounding box
            
        Returns:
            Dict with 'encoding', 'confidence', 'bbox', or None
        """
        if self.backend_name is None:
            return None
        
        # Extract face region
        face_region = self.extract_face_region(frame, bbox)
        if face_region is None or face_region.size == 0:
            return None
        
        # Convert BGR to RGB if needed
        if len(face_region.shape) == 3 and face_region.shape[2] == 3:
            face_rgb = cv2.cvtColor(face_region, cv2.COLOR_BGR2RGB)
        else:
            face_rgb = face_region
        
        # Detect using selected backend
        result = None
        if self.backend_name == "face_recognition":
            result = self._detect_face_recognition(face_rgb)
        elif self.backend_name == "deepface":
            result = self._detect_deepface(face_rgb)
        elif self.backend_name == "dlib":
            result = self._detect_dlib(face_rgb)
        
        if result:
            return {
                'encoding': result['encoding'],
                'confidence': result.get('confidence', 1.0),
                'bbox': result.get('bbox', None),
                'backend': self.backend_name
            }
        
        return None
    
    def _detect_face_recognition(self, face_image: np.ndarray) -> Optional[Dict[str, Any]]:
        """Detect using face_recognition library"""
        try:
            # Detect face locations
            face_locations = face_recognition.face_locations(face_image, model='hog')
            
            if len(face_locations) == 0:
                return None
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(face_image, face_locations)
            
            if len(face_encodings) == 0:
                return None
            
            # Return first face (most prominent)
            return {
                'encoding': face_encodings[0],
                'confidence': 1.0,  # face_recognition doesn't provide confidence
                'bbox': face_locations[0]  # (top, right, bottom, left)
            }
        except Exception as e:
            logger.warning(f"face_recognition error: {e}")
            return None
    
    def _detect_deepface(self, face_image: np.ndarray) -> Optional[Dict[str, Any]]:
        """Detect using DeepFace library"""
        try:
            # DeepFace expects file path or numpy array
            result = DeepFace.represent(
                face_image,
                model_name=self.model_name,
                enforce_detection=False
            )
            
            if result and len(result) > 0:
                # Get embedding
                embedding = result[0].get('embedding', None)
                if embedding is not None:
                    return {
                        'encoding': np.array(embedding),
                        'confidence': result[0].get('confidence', 0.8),
                        'bbox': result[0].get('facial_area', None)
                    }
            return None
        except Exception as e:
            logger.warning(f"DeepFace error: {e}")
            return None
    
    def _detect_dlib(self, face_image: np.ndarray) -> Optional[Dict[str, Any]]:
        """Detect using dlib library"""
        try:
            # This is a basic implementation - would need face detector and encoder
            # For now, return None (requires more setup)
            logger.warning("dlib face recognition not fully implemented")
            return None
        except Exception as e:
            logger.warning(f"dlib error: {e}")
            return None
    
    def add_face_to_database(self, player_id: str, encoding: np.ndarray):
        """
        Add face encoding to database for a player
        
        Args:
            player_id: Player identifier
            encoding: Face encoding vector
        """
        if encoding is not None:
            self.face_database[player_id].append(encoding)
            logger.debug(f"Added face encoding for player {player_id} (total: {len(self.face_database[player_id])})")
    
    def match_face(self, encoding: np.ndarray, threshold: Optional[float] = None) -> Optional[Tuple[str, float]]:
        """
        Match face encoding against database
        
        Args:
            encoding: Face encoding to match
            threshold: Similarity threshold (uses default if None)
            
        Returns:
            Tuple of (player_id, similarity) or None
        """
        if threshold is None:
            threshold = self.confidence_threshold
        
        if len(self.face_database) == 0:
            return None
        
        best_match = None
        best_similarity = 0.0
        
        for player_id, encodings in self.face_database.items():
            for stored_encoding in encodings:
                # Calculate cosine similarity
                similarity = self._cosine_similarity(encoding, stored_encoding)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = player_id
        
        if best_match and best_similarity >= threshold:
            return (best_match, best_similarity)
        
        return None
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
            vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-8)
            return float(np.dot(vec1_norm, vec2_norm))
        except Exception:
            return 0.0
    
    def clear_database(self, player_id: Optional[str] = None):
        """Clear face database for a player or all players"""
        if player_id is not None:
            self.face_database.pop(player_id, None)
        else:
            self.face_database.clear()
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get statistics about face database"""
        total_faces = sum(len(encodings) for encodings in self.face_database.values())
        return {
            'num_players': len(self.face_database),
            'total_faces': total_faces,
            'avg_faces_per_player': total_faces / len(self.face_database) if len(self.face_database) > 0 else 0
        }


class MultiFrameFaceRecognizer:
    """
    Multi-frame consensus face recognition - matches faces across multiple frames
    for higher accuracy and confidence
    """
    
    def __init__(self,
                 face_recognizer: FaceRecognizer,
                 consensus_frames: int = 5,
                 consensus_threshold: float = 0.6):
        """
        Initialize multi-frame face recognizer
        
        Args:
            face_recognizer: FaceRecognizer instance
            consensus_frames: Number of frames to consider for consensus
            consensus_threshold: Minimum fraction of frames that must agree
        """
        self.face_recognizer = face_recognizer
        self.consensus_frames = consensus_frames
        self.consensus_threshold = consensus_threshold
        self.frame_history = defaultdict(list)  # track_id -> [(frame_num, player_id, similarity), ...]
    
    def recognize_with_consensus(self,
                                frame: np.ndarray,
                                detections: List[Dict[str, Any]],
                                frame_num: int) -> List[Dict[str, Any]]:
        """
        Recognize faces with multi-frame consensus
        
        Args:
            frame: Current frame
            detections: List of detections with bbox and track_id
            frame_num: Current frame number
            
        Returns:
            Detections with face_match added
        """
        results = []
        
        for det in detections:
            track_id = det.get('track_id')
            bbox = det.get('bbox')
            
            if not bbox or track_id is None:
                results.append(det)
                continue
            
            # Detect face in current frame
            face_result = self.face_recognizer.detect_face(frame, bbox)
            
            # Match if face detected
            if face_result:
                encoding = face_result['encoding']
                match = self.face_recognizer.match_face(encoding)
                
                if match:
                    player_id, similarity = match
                    self.frame_history[track_id].append((
                        frame_num,
                        player_id,
                        similarity
                    ))
            
            # Keep only recent frames
            self.frame_history[track_id] = [
                (f, p, s) for f, p, s in self.frame_history[track_id]
                if frame_num - f < self.consensus_frames
            ]
            
            # Get consensus
            consensus = self._get_consensus(track_id)
            
            if consensus:
                det['face_match'] = consensus['player_id']
                det['face_confidence'] = consensus['confidence']
                det['face_detection_frames'] = consensus['frame_count']
            
            results.append(det)
        
        return results
    
    def _get_consensus(self, track_id: int) -> Optional[Dict[str, Any]]:
        """Get consensus player match from frame history"""
        history = self.frame_history.get(track_id, [])
        if len(history) < 2:
            return None
        
        # Count occurrences of each player
        from collections import Counter
        player_counts = Counter()
        player_similarities = defaultdict(list)
        
        for frame_num, player_id, similarity in history:
            player_counts[player_id] += 1
            player_similarities[player_id].append(similarity)
        
        # Find most common player
        if not player_counts:
            return None
        
        most_common = player_counts.most_common(1)[0]
        player_id, count = most_common
        
        # Check if meets consensus threshold
        required_count = max(2, int(len(history) * self.consensus_threshold))
        if count < required_count:
            return None
        
        # Calculate average confidence
        avg_confidence = np.mean(player_similarities[player_id])
        
        return {
            'player_id': player_id,
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

