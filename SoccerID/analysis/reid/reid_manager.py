"""
Re-ID Manager Module
Manages Re-ID tracker and gallery matching
"""

from typing import Optional, Dict, Any, List

# Try new structure imports first, fallback to legacy
try:
    from ...utils.logger_config import get_logger
    from ...models.player_gallery import PlayerGallery
except ImportError:
    try:
        from SoccerID.utils.logger_config import get_logger
        from SoccerID.models.player_gallery import PlayerGallery
    except ImportError:
        # Legacy fallback
        try:
            from logger_config import get_logger
            from player_gallery import PlayerGallery
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)
            PlayerGallery = None

logger = get_logger("reid")

# Re-ID tracker import
try:
    from reid_tracker import ReIDTracker
    REID_AVAILABLE = True
except ImportError as e:
    REID_AVAILABLE = False
    logger.warning("⚠ Re-ID tracker not available")

# Jersey OCR import
try:
    from ...recognition.jersey_ocr import MultiFrameJerseyOCR
    OCR_AVAILABLE = True
except ImportError:
    try:
        from SoccerID.recognition.jersey_ocr import MultiFrameJerseyOCR
        OCR_AVAILABLE = True
    except ImportError:
        try:
            from recognition.jersey_ocr import MultiFrameJerseyOCR
            OCR_AVAILABLE = True
        except ImportError:
            OCR_AVAILABLE = False
            MultiFrameJerseyOCR = None

# Face Recognition import
try:
    from ...recognition.face_recognition import MultiFrameFaceRecognizer
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    try:
        from SoccerID.recognition.face_recognition import MultiFrameFaceRecognizer
        FACE_RECOGNITION_AVAILABLE = True
    except ImportError:
        try:
            from recognition.face_recognition import MultiFrameFaceRecognizer
            FACE_RECOGNITION_AVAILABLE = True
        except ImportError:
            FACE_RECOGNITION_AVAILABLE = False
            MultiFrameFaceRecognizer = None

# ML Enhancements import
try:
    from ...ml.feedback_learner import FeedbackLearner
    from ...ml.adaptive_tracker import AdaptiveTracker
    ML_AVAILABLE = True
except ImportError:
    try:
        from SoccerID.ml.feedback_learner import FeedbackLearner
        from SoccerID.ml.adaptive_tracker import AdaptiveTracker
        ML_AVAILABLE = True
    except ImportError:
        try:
            from ml.feedback_learner import FeedbackLearner
            from ml.adaptive_tracker import AdaptiveTracker
            ML_AVAILABLE = True
        except ImportError:
            ML_AVAILABLE = False
            FeedbackLearner = None
            AdaptiveTracker = None


class ReIDManager:
    """Manages Re-ID tracker and gallery matching"""
    
    def __init__(self, use_reid: bool = True, 
                 reid_similarity_threshold: float = 0.55,
                 gallery_similarity_threshold: float = 0.50,  # Increased from 0.40 for better accuracy
                 player_gallery: Optional[PlayerGallery] = None,
                 use_jersey_ocr: bool = True,
                 ocr_consensus_frames: int = 5,
                 use_face_recognition: bool = True,
                 face_consensus_frames: int = 5,
                 use_feedback_learning: bool = True,
                 use_adaptive_tracking: bool = True,
                 temporal_consistency_frames: int = 30):  # New parameter for temporal consistency
        """
        Initialize Re-ID manager
        
        Args:
            use_reid: Enable Re-ID
            reid_similarity_threshold: Re-ID similarity threshold
            gallery_similarity_threshold: Gallery similarity threshold
            player_gallery: Player gallery instance
            use_jersey_ocr: Enable jersey number OCR
            ocr_consensus_frames: Number of frames for OCR consensus
            use_face_recognition: Enable face recognition
            face_consensus_frames: Number of frames for face recognition consensus
            use_feedback_learning: Enable learning from user corrections
            use_adaptive_tracking: Enable adaptive threshold adjustment
        """
        self.use_reid = use_reid and REID_AVAILABLE
        self.reid_similarity_threshold = reid_similarity_threshold
        self.gallery_similarity_threshold = gallery_similarity_threshold
        self.player_gallery = player_gallery
        self.reid_tracker = None
        self.temporal_consistency_frames = temporal_consistency_frames
        
        # Track history for temporal consistency (track_id -> list of recent matches)
        self.track_match_history: Dict[int, List[Dict[str, Any]]] = {}
        
        # Feature cache to avoid redundant extractions (track_id -> features)
        self.feature_cache: Dict[int, Any] = {}
        self.feature_cache_max_size = 100  # Cache up to 100 tracks
        
        # Initialize jersey OCR
        self.use_jersey_ocr = use_jersey_ocr and OCR_AVAILABLE
        self.jersey_ocr = None
        if self.use_jersey_ocr and MultiFrameJerseyOCR:
            try:
                self.jersey_ocr = MultiFrameJerseyOCR(
                    consensus_frames=ocr_consensus_frames
                )
                logger.info("Jersey OCR initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize jersey OCR: {e}")
                self.use_jersey_ocr = False
        
        # Initialize face recognition
        self.use_face_recognition = use_face_recognition and FACE_RECOGNITION_AVAILABLE
        self.face_recognizer = None
        if self.use_face_recognition and MultiFrameFaceRecognizer:
            try:
                from ...recognition.face_recognition import FaceRecognizer
                face_recognizer = FaceRecognizer()
                self.face_recognizer = MultiFrameFaceRecognizer(
                    face_recognizer,
                    consensus_frames=face_consensus_frames
                )
                logger.info("Face recognition initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize face recognition: {e}")
                self.use_face_recognition = False
        
        # Initialize ML enhancements
        self.use_feedback_learning = use_feedback_learning and ML_AVAILABLE
        self.feedback_learner = None
        if self.use_feedback_learning and FeedbackLearner:
            try:
                self.feedback_learner = FeedbackLearner()
                logger.info("Feedback learner initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize feedback learner: {e}")
                self.use_feedback_learning = False
        
        self.use_adaptive_tracking = use_adaptive_tracking and ML_AVAILABLE
        self.adaptive_tracker = None
        if self.use_adaptive_tracking and AdaptiveTracker:
            try:
                self.adaptive_tracker = AdaptiveTracker(
                    initial_similarity_threshold=reid_similarity_threshold,
                    initial_reid_threshold=gallery_similarity_threshold
                )
                logger.info("Adaptive tracker initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize adaptive tracker: {e}")
                self.use_adaptive_tracking = False
        
        if self.use_reid:
            try:
                # Use adaptive threshold if available
                threshold = self.adaptive_tracker.similarity_threshold if self.adaptive_tracker else reid_similarity_threshold
                self.reid_tracker = ReIDTracker(
                    similarity_threshold=threshold
                )
                logger.info("Re-ID tracker initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Re-ID tracker: {e}")
                self.use_reid = False
    
    def match_with_gallery(self, detections: List[Dict[str, Any]], 
                          frame_num: int,
                          frame: Any = None) -> List[Dict[str, Any]]:
        """
        Match detections with player gallery (with jersey OCR, face recognition, and ML enhancements)
        
        Args:
            detections: List of detection dictionaries or sv.Detections object
            frame_num: Current frame number
            frame: Current frame (for feature extraction, OCR, and face recognition)
            
        Returns:
            Detections with player names matched from gallery, jersey numbers, and face matches
        """
        # First, run jersey OCR if enabled
        if self.use_jersey_ocr and self.jersey_ocr and frame is not None:
            try:
                detections = self.jersey_ocr.detect_with_consensus(
                    frame, detections, frame_num
                )
            except Exception as e:
                logger.warning(f"Jersey OCR failed: {e}")
        
        # Run face recognition if enabled
        if self.use_face_recognition and self.face_recognizer and frame is not None:
            try:
                detections = self.face_recognizer.recognize_with_consensus(
                    frame, detections, frame_num
                )
            except Exception as e:
                logger.warning(f"Face recognition failed: {e}")
        
        # Then match with gallery using Re-ID
        if not self.player_gallery or not self.use_reid:
            return detections
        
        if not self.reid_tracker:
            return detections
        
        # Get adaptive thresholds if available
        if self.adaptive_tracker:
            thresholds = self.adaptive_tracker.get_current_thresholds()
            self.gallery_similarity_threshold = thresholds.get('similarity_threshold', self.gallery_similarity_threshold)
        
        try:
            # Convert detections to sv.Detections format if needed
            if not hasattr(detections, 'xyxy'):
                # Assume it's a list of dicts, convert to sv.Detections
                import supervision as sv
                import numpy as np
                
                boxes = []
                confidences = []
                for det in detections:
                    boxes.append(det.get('bbox', []))
                    confidences.append(det.get('confidence', 0.0))
                
                if not boxes:
                    return detections
                
                detections_sv = sv.Detections(
                    xyxy=np.array(boxes),
                    confidence=np.array(confidences)
                )
            else:
                detections_sv = detections
            
            # Extract Re-ID features if frame is provided (with caching)
            reid_features = None
            if frame is not None:
                # Check cache first for stable tracks
                cached_features = []
                uncached_indices = []
                
                for i, det in enumerate(detections):
                    track_id = det.get('track_id')
                    if track_id is not None and track_id in self.feature_cache:
                        cached_features.append((i, self.feature_cache[track_id]))
                    else:
                        uncached_indices.append(i)
                
                # Extract features only for uncached detections
                if uncached_indices:
                    uncached_detections = [detections[i] for i in uncached_indices]
                    # Convert to sv.Detections format
                    import supervision as sv
                    import numpy as np
                    boxes = [d.get('bbox', []) for d in uncached_detections]
                    confidences = [d.get('confidence', 0.0) for d in uncached_detections]
                    if boxes:
                        uncached_sv = sv.Detections(
                            xyxy=np.array(boxes),
                            confidence=np.array(confidences)
                        )
                        new_features = self.reid_tracker.extract_features(frame, uncached_sv)
                        
                        # Cache new features
                        for idx, feat in zip(uncached_indices, new_features):
                            track_id = detections[idx].get('track_id')
                            if track_id is not None:
                                # Manage cache size
                                if len(self.feature_cache) >= self.feature_cache_max_size:
                                    # Remove oldest (simple FIFO)
                                    oldest_key = next(iter(self.feature_cache))
                                    del self.feature_cache[oldest_key]
                                self.feature_cache[track_id] = feat
                                cached_features.append((idx, feat))
                    else:
                        new_features = []
                else:
                    new_features = []
                
                # Reconstruct features list in original order
                if cached_features or new_features:
                    all_features = [None] * len(detections)
                    for idx, feat in cached_features:
                        all_features[idx] = feat
                    for idx, feat in zip(uncached_indices, new_features):
                        all_features[idx] = feat
                    reid_features = [f for f in all_features if f is not None]
                else:
                    reid_features = []
            else:
                reid_features = None
            
            # Match with gallery
            if reid_features is not None and len(reid_features) > 0:
                # Convert back to list of dicts if needed
                if hasattr(detections, 'xyxy'):
                    detections_list = []
                    for i in range(len(detections)):
                        det = {
                            'bbox': detections.xyxy[i].tolist(),
                            'confidence': float(detections.confidence[i])
                        }
                        detections_list.append(det)
                    detections = detections_list
                
                for i, feature in enumerate(reid_features):
                    if i >= len(detections):
                        break
                    
                    # Extract body, jersey, and foot features if available
                    body_features = None
                    jersey_features = None
                    foot_features = None
                    
                    if self.reid_tracker and frame is not None:
                        try:
                            # Convert to sv.Detections for feature extraction
                            import supervision as sv
                            import numpy as np
                            det = detections[i]
                            bbox = det.get('bbox', [])
                            if bbox:
                                det_sv = sv.Detections(
                                    xyxy=np.array([bbox]),
                                    confidence=np.array([det.get('confidence', 0.5)])
                                )
                                body_features = self.reid_tracker.extract_body_features(frame, det_sv)
                                jersey_features = self.reid_tracker.extract_jersey_features(frame, det_sv)
                                foot_features = self.reid_tracker.extract_foot_features(frame, det_sv)
                                
                                if body_features is not None and len(body_features) > 0:
                                    body_features = body_features[0]
                                if jersey_features is not None and len(jersey_features) > 0:
                                    jersey_features = jersey_features[0]
                                if foot_features is not None and len(foot_features) > 0:
                                    foot_features = foot_features[0]
                        except Exception as e:
                            logger.debug(f"Error extracting body/jersey/foot features: {e}")
                    
                    # Get track_id for temporal consistency and feedback learning
                    track_id = detections[i].get('track_id')
                    
                    # TEMPORAL CONSISTENCY: Check recent matches for this track first
                    consistent_match = None
                    if track_id is not None and track_id in self.track_match_history:
                        recent_matches = self.track_match_history[track_id]
                        if recent_matches:
                            from collections import Counter
                            # Get most common match in recent history
                            match_counts = Counter([m.get('player_name') for m in recent_matches if m.get('player_name')])
                            if match_counts:
                                most_common_match, count = match_counts.most_common(1)[0]
                                consistency_ratio = count / len(recent_matches)
                                
                                # If track consistently matches one player (67%+ of recent frames), use that
                                if consistency_ratio >= 0.67 and count >= 20:  # At least 20 matches in history
                                    # Verify the match still makes sense with current features
                                    # Find player by name
                                    player = None
                                    player_id = None
                                    for pid, p in self.player_gallery.players.items():
                                        if p.name == most_common_match:
                                            player = p
                                            player_id = pid
                                            break
                                    if player:
                                        # Quick similarity check to verify match still makes sense
                                        if hasattr(self.player_gallery, 'match_player'):
                                            quick_match = self.player_gallery.match_player(
                                                features=feature,
                                                similarity_threshold=self.gallery_similarity_threshold * 0.8,  # Slightly lower for consistency
                                                body_features=body_features,
                                                jersey_features=jersey_features,
                                                foot_features=foot_features,
                                                enable_foot_matching=True,
                                                log_matching_details=False
                                            )
                                            if quick_match and isinstance(quick_match, tuple):
                                                _, matched_name, similarity = quick_match
                                                # Use consistent match if it matches or similarity is reasonable
                                                if matched_name == most_common_match or similarity >= self.gallery_similarity_threshold * 0.7:
                                                    consistent_match = (player_id, most_common_match, consistency_ratio)
                                                    logger.debug(f"Using temporal consistency for track {track_id}: {most_common_match} ({consistency_ratio:.1%} consistency, current similarity: {similarity:.2f})")
                                        else:
                                            # Fallback: use consistent match if we found the player
                                            consistent_match = (player_id, most_common_match, consistency_ratio)
                                            logger.debug(f"Using temporal consistency for track {track_id}: {most_common_match} ({consistency_ratio:.1%} consistency)")
                    
                    # If no consistent match, do fresh matching
                    matches = None
                    if consistent_match is None:
                        # Match with gallery (with foot features support)
                        # Try match_player first (new method with foot features), fallback to match_features
                        if hasattr(self.player_gallery, 'match_player'):
                            matches = self.player_gallery.match_player(
                                features=feature,
                                similarity_threshold=self.gallery_similarity_threshold,
                                body_features=body_features,
                                jersey_features=jersey_features,
                                foot_features=foot_features,
                                enable_foot_matching=True,
                                log_matching_details=False
                            )
                        else:
                            # Fallback to match_features
                            matches = self.player_gallery.match_features(
                                feature.reshape(1, -1),
                                threshold=self.gallery_similarity_threshold
                            )
                    else:
                        # Use consistent match
                        matches = consistent_match
                    
                    if matches:
                        if isinstance(matches, tuple) and len(matches) == 3:
                            # match_player returns (player_id, player_name, similarity)
                            player_id, player_name, similarity = matches
                        elif isinstance(matches, list) and len(matches) > 0:
                            # match_features returns list of (player_id, similarity)
                            player_id, similarity = matches[0]
                            player = self.player_gallery.get_player(player_id)
                            player_name = player.name if player else None
                        else:
                            continue
                        
                        if not player_name:
                            continue
                        player = self.player_gallery.get_player(player_id)
                        if player:
                            detections[i]['player_name'] = player_name
                            detections[i]['gallery_match_confidence'] = similarity
                            
                            # Update track match history for temporal consistency
                            if track_id is not None:
                                if track_id not in self.track_match_history:
                                    self.track_match_history[track_id] = []
                                self.track_match_history[track_id].append({
                                    'player_name': player_name,
                                    'player_id': player_id,
                                    'similarity': similarity,
                                    'frame_num': frame_num
                                })
                                # Keep only recent history (last N frames)
                                if len(self.track_match_history[track_id]) > self.temporal_consistency_frames:
                                    self.track_match_history[track_id] = self.track_match_history[track_id][-self.temporal_consistency_frames:]
                            
                            # Check if this match should be excluded based on feedback
                            if self.feedback_learner and track_id is not None:
                                try:
                                    if self.feedback_learner.should_exclude_track(str(player_id), int(track_id)):
                                        logger.debug(f"Excluding track {track_id} for {player_name} based on feedback")
                                        detections[i]['player_name'] = None
                                        detections[i]['gallery_match_confidence'] = 0.0
                                        continue
                                    
                                    # Apply feedback adjustment
                                    adjustment = self.feedback_learner.get_adjustment(str(player_id))
                                    if adjustment != 0.0:
                                        detections[i]['gallery_match_confidence'] = min(1.0, similarity + adjustment)
                                except (ValueError, TypeError) as e:
                                    logger.debug(f"Feedback learner error: {e}")
                            
                            # Also check jersey number match if available
                            if 'jersey_number' in detections[i]:
                                jersey_num = detections[i]['jersey_number']
                                if player.jersey_number and str(player.jersey_number) == str(jersey_num):
                                    detections[i]['jersey_match'] = True
                                    detections[i]['gallery_match_confidence'] = min(
                                        detections[i].get('gallery_match_confidence', similarity) + 0.1,
                                        1.0
                                    )
                            
                            # Check face match if available
                            if 'face_match' in detections[i]:
                                face_match = detections[i]['face_match']
                                if face_match == player_id:
                                    detections[i]['face_match_confirmed'] = True
                                    detections[i]['gallery_match_confidence'] = min(
                                        detections[i].get('gallery_match_confidence', similarity) + 0.15,
                                        1.0
                                    )
            
            return detections
            
        except Exception as e:
            logger.warning(f"Gallery matching failed: {e}")
            return detections
    
    def update_reid_features(self, detections: List[Dict[str, Any]], 
                            frame_num: int,
                            frame: Any = None):
        """
        Update Re-ID features for detections
        
        Args:
            detections: List of detection dictionaries or sv.Detections object
            frame_num: Current frame number
            frame: Current frame (for feature extraction)
        """
        if not self.use_reid or not self.reid_tracker:
            return
        
        try:
            # Extract features if frame is provided
            if frame is not None:
                # Convert to sv.Detections if needed
                if not hasattr(detections, 'xyxy'):
                    import supervision as sv
                    import numpy as np
                    
                    boxes = []
                    confidences = []
                    for det in detections:
                        boxes.append(det.get('bbox', []))
                        confidences.append(det.get('confidence', 0.0))
                    
                    if boxes:
                        detections = sv.Detections(
                            xyxy=np.array(boxes),
                            confidence=np.array(confidences)
                        )
                    else:
                        return
                
                # Extract features
                features = self.reid_tracker.extract_features(frame, detections)
                
                # Store features in detections or return separately
                # (Implementation depends on how detections are structured)
                return features
            
        except Exception as e:
            logger.warning(f"Re-ID feature update failed: {e}")

