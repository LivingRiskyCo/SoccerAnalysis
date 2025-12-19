"""
Analysis Integration Helper
Integrates new modules (face recognition, ML, validation) into analysis pipeline
"""

import os
import sys
from typing import Dict, Any, Optional, List

# Try to import new modules
try:
    from ..recognition.face_recognition import FaceRecognizer, MultiFrameFaceRecognizer
    from ..ml.feedback_learner import FeedbackLearner
    from ..ml.adaptive_tracker import AdaptiveTracker
    from ..ml.predictive_analytics import PredictiveAnalytics
    from ..validation.quality_reporter import QualityReporter
    from ..validation.track_validator import TrackValidator
    from ..validation.anomaly_detector import AnomalyDetector
    from ..postprocessing.validation import PostAnalysisValidator
    INTEGRATION_AVAILABLE = True
except ImportError:
    try:
        from soccer_analysis.recognition.face_recognition import FaceRecognizer, MultiFrameFaceRecognizer
        from soccer_analysis.ml.feedback_learner import FeedbackLearner
        from soccer_analysis.ml.adaptive_tracker import AdaptiveTracker
        from soccer_analysis.ml.predictive_analytics import PredictiveAnalytics
        from soccer_analysis.validation.quality_reporter import QualityReporter
        from soccer_analysis.validation.track_validator import TrackValidator
        from soccer_analysis.validation.anomaly_detector import AnomalyDetector
        from soccer_analysis.analysis.postprocessing.validation import PostAnalysisValidator
        INTEGRATION_AVAILABLE = True
    except ImportError:
        INTEGRATION_AVAILABLE = False
        FaceRecognizer = None
        MultiFrameFaceRecognizer = None
        FeedbackLearner = None
        AdaptiveTracker = None
        PredictiveAnalytics = None
        QualityReporter = None
        TrackValidator = None
        AnomalyDetector = None
        PostAnalysisValidator = None

# Try to import logger
try:
    from ..utils.logger_config import get_logger
except ImportError:
    try:
        from soccer_analysis.utils.logger_config import get_logger
    except ImportError:
        try:
            from utils.logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("integration")


class AnalysisIntegration:
    """
    Integrates new modules into the analysis pipeline
    """
    
    def __init__(self, 
                 use_face_recognition: bool = True,
                 use_feedback_learning: bool = True,
                 use_adaptive_tracking: bool = True,
                 use_predictive_analytics: bool = True,
                 run_validation: bool = True):
        """
        Initialize analysis integration
        
        Args:
            use_face_recognition: Enable face recognition
            use_feedback_learning: Enable feedback learning
            use_adaptive_tracking: Enable adaptive tracking
            use_predictive_analytics: Enable predictive analytics
            run_validation: Run validation after analysis
        """
        self.use_face_recognition = use_face_recognition and INTEGRATION_AVAILABLE
        self.use_feedback_learning = use_feedback_learning and INTEGRATION_AVAILABLE
        self.use_adaptive_tracking = use_adaptive_tracking and INTEGRATION_AVAILABLE
        self.use_predictive_analytics = use_predictive_analytics and INTEGRATION_AVAILABLE
        self.run_validation = run_validation and INTEGRATION_AVAILABLE
        
        # Initialize modules
        self.face_recognizer = None
        self.feedback_learner = None
        self.adaptive_tracker = None
        self.predictive_analytics = None
        self.validator = None
        
        if self.use_face_recognition and FaceRecognizer and MultiFrameFaceRecognizer:
            try:
                face_rec = FaceRecognizer()
                self.face_recognizer = MultiFrameFaceRecognizer(face_rec)
                logger.info("Face recognition integrated")
            except Exception as e:
                logger.warning(f"Face recognition integration failed: {e}")
                self.use_face_recognition = False
        
        if self.use_feedback_learning and FeedbackLearner:
            try:
                self.feedback_learner = FeedbackLearner()
                logger.info("Feedback learning integrated")
            except Exception as e:
                logger.warning(f"Feedback learning integration failed: {e}")
                self.use_feedback_learning = False
        
        if self.use_adaptive_tracking and AdaptiveTracker:
            try:
                self.adaptive_tracker = AdaptiveTracker()
                logger.info("Adaptive tracking integrated")
            except Exception as e:
                logger.warning(f"Adaptive tracking integration failed: {e}")
                self.use_adaptive_tracking = False
        
        if self.use_predictive_analytics and PredictiveAnalytics:
            try:
                self.predictive_analytics = PredictiveAnalytics()
                logger.info("Predictive analytics integrated")
            except Exception as e:
                logger.warning(f"Predictive analytics integration failed: {e}")
                self.use_predictive_analytics = False
        
        if self.run_validation and PostAnalysisValidator:
            try:
                self.validator = PostAnalysisValidator()
                logger.info("Validation integrated")
            except Exception as e:
                logger.warning(f"Validation integration failed: {e}")
                self.run_validation = False
    
    def process_frame(self, 
                     frame: Any,
                     detections: List[Dict[str, Any]],
                     frame_num: int,
                     track_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Process frame with integrated modules
        
        Args:
            frame: Current frame
            detections: List of detections
            frame_num: Frame number
            track_id: Optional track ID
            
        Returns:
            Enhanced detections
        """
        # Face recognition
        if self.use_face_recognition and self.face_recognizer:
            try:
                detections = self.face_recognizer.recognize_with_consensus(
                    frame, detections, frame_num
                )
            except Exception as e:
                logger.debug(f"Face recognition failed: {e}")
        
        # Predictive analytics
        if self.use_predictive_analytics and self.predictive_analytics:
            try:
                for det in detections:
                    track_id = det.get('track_id')
                    if track_id and 'x' in det and 'y' in det:
                        self.predictive_analytics.update_track(
                            track_id, det['x'], det['y'], frame_num
                        )
            except Exception as e:
                logger.debug(f"Predictive analytics failed: {e}")
        
        return detections
    
    def record_correction(self,
                         player_id: str,
                         original_track_id: int,
                         corrected_track_id: int,
                         frame_num: int,
                         context: Optional[Dict[str, Any]] = None):
        """Record a user correction for feedback learning"""
        if self.use_feedback_learning and self.feedback_learner:
            try:
                self.feedback_learner.record_correction(
                    player_id, original_track_id, corrected_track_id, frame_num, context
                )
            except Exception as e:
                logger.warning(f"Failed to record correction: {e}")
    
    def record_performance(self,
                           frame_num: int,
                           track_quality: float,
                           match_accuracy: float,
                           false_positives: int = 0,
                           false_negatives: int = 0):
        """Record performance metrics for adaptive tracking"""
        if self.use_adaptive_tracking and self.adaptive_tracker:
            try:
                self.adaptive_tracker.record_performance(
                    frame_num, track_quality, match_accuracy, false_positives, false_negatives
                )
            except Exception as e:
                logger.debug(f"Failed to record performance: {e}")
    
    def validate_analysis(self, csv_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Run validation on analysis results"""
        if self.run_validation and self.validator:
            try:
                return self.validator.validate_analysis(csv_path, output_dir)
            except Exception as e:
                logger.warning(f"Validation failed: {e}")
                return {'error': str(e)}
        return {}
    
    def get_predictions(self, track_id: int, frames_ahead: int = 5) -> Optional[Dict[str, Any]]:
        """Get predictions for a track"""
        if self.use_predictive_analytics and self.predictive_analytics:
            try:
                predicted_pos = self.predictive_analytics.predict_position(track_id, frames_ahead)
                direction = self.predictive_analytics.predict_movement_direction(track_id)
                trajectory = self.predictive_analytics.analyze_trajectory(track_id)
                
                return {
                    'predicted_position': predicted_pos,
                    'direction': direction,
                    'trajectory': trajectory
                }
            except Exception as e:
                logger.debug(f"Prediction failed: {e}")
        return None
    
    def get_adaptive_thresholds(self) -> Dict[str, Any]:
        """Get current adaptive thresholds"""
        if self.use_adaptive_tracking and self.adaptive_tracker:
            try:
                return self.adaptive_tracker.get_current_thresholds()
            except Exception as e:
                logger.debug(f"Failed to get thresholds: {e}")
        return {}

