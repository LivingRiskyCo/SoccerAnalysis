"""
Adaptive Tracking
Improves tracking over time by adapting thresholds and weights based on performance
"""

import numpy as np
from typing import Dict, List, Any, Optional
from collections import deque
from datetime import datetime

# Try to import logger
try:
    from ...utils.logger_config import get_logger
except ImportError:
    try:
        from soccer_analysis.utils.logger_config import get_logger
    except ImportError:
        try:
            from utils.logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("adaptive_tracker")


class AdaptiveTracker:
    """
    Adapts tracking parameters over time based on performance metrics
    """
    
    def __init__(self,
                 initial_similarity_threshold: float = 0.6,
                 initial_reid_threshold: float = 0.55,
                 adaptation_rate: float = 0.1):
        """
        Initialize adaptive tracker
        
        Args:
            initial_similarity_threshold: Initial similarity threshold
            initial_reid_threshold: Initial Re-ID threshold
            adaptation_rate: Rate at which parameters adapt (0-1)
        """
        self.similarity_threshold = initial_similarity_threshold
        self.reid_threshold = initial_reid_threshold
        self.adaptation_rate = adaptation_rate
        
        # Performance history
        self.performance_history = deque(maxlen=100)  # Last 100 frames
        self.track_quality_history = deque(maxlen=100)
        
        # Adaptive weights for feature combination
        self.feature_weights = {
            'body': 0.35,
            'jersey': 0.30,
            'foot': 0.30,
            'general': 0.05
        }
    
    def record_performance(self,
                          frame_num: int,
                          track_quality: float,
                          match_accuracy: float,
                          false_positives: int = 0,
                          false_negatives: int = 0):
        """
        Record performance metrics for a frame
        
        Args:
            frame_num: Frame number
            track_quality: Overall track quality (0-1)
            match_accuracy: Matching accuracy (0-1)
            false_positives: Number of false positive matches
            false_negatives: Number of false negative matches
        """
        performance = {
            'frame_num': frame_num,
            'track_quality': track_quality,
            'match_accuracy': match_accuracy,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'timestamp': datetime.now().isoformat()
        }
        
        self.performance_history.append(performance)
        self.track_quality_history.append(track_quality)
        
        # Adapt thresholds based on performance
        self._adapt_thresholds()
    
    def _adapt_thresholds(self):
        """Adapt thresholds based on recent performance"""
        if len(self.performance_history) < 10:
            return  # Need more data
        
        # Calculate recent performance metrics
        recent_performance = list(self.performance_history)[-20:]  # Last 20 frames
        
        avg_accuracy = np.mean([p['match_accuracy'] for p in recent_performance])
        avg_fp = np.mean([p['false_positives'] for p in recent_performance])
        avg_fn = np.mean([p['false_negatives'] for p in recent_performance])
        
        # Adjust similarity threshold
        if avg_fp > avg_fn:
            # Too many false positives - increase threshold (be more strict)
            adjustment = self.adaptation_rate * 0.05
            self.similarity_threshold = min(0.9, self.similarity_threshold + adjustment)
            logger.debug(f"Adapted similarity threshold: {self.similarity_threshold:.3f} (reduced false positives)")
        elif avg_fn > avg_fp:
            # Too many false negatives - decrease threshold (be more lenient)
            adjustment = self.adaptation_rate * 0.05
            self.similarity_threshold = max(0.3, self.similarity_threshold - adjustment)
            logger.debug(f"Adapted similarity threshold: {self.similarity_threshold:.3f} (reduced false negatives)")
        
        # Adjust Re-ID threshold similarly
        if avg_accuracy < 0.7:
            # Low accuracy - adjust Re-ID threshold
            if avg_fp > avg_fn:
                self.reid_threshold = min(0.8, self.reid_threshold + self.adaptation_rate * 0.03)
            else:
                self.reid_threshold = max(0.4, self.reid_threshold - self.adaptation_rate * 0.03)
    
    def adapt_feature_weights(self, feature_performance: Dict[str, float]):
        """
        Adapt feature weights based on performance
        
        Args:
            feature_performance: Dict mapping feature names to performance scores (0-1)
        """
        total_performance = sum(feature_performance.values())
        if total_performance == 0:
            return
        
        # Normalize performance scores
        normalized = {k: v / total_performance for k, v in feature_performance.items()}
        
        # Adapt weights (weighted average of current and performance-based)
        for feature, perf in normalized.items():
            if feature in self.feature_weights:
                current_weight = self.feature_weights[feature]
                target_weight = perf
                # Smooth adaptation
                new_weight = (1 - self.adaptation_rate) * current_weight + self.adaptation_rate * target_weight
                self.feature_weights[feature] = new_weight
        
        # Renormalize to ensure weights sum to 1.0
        total_weight = sum(self.feature_weights.values())
        if total_weight > 0:
            self.feature_weights = {k: v / total_weight for k, v in self.feature_weights.items()}
        
        logger.debug(f"Adapted feature weights: {self.feature_weights}")
    
    def get_current_thresholds(self) -> Dict[str, float]:
        """Get current adaptive thresholds"""
        return {
            'similarity_threshold': self.similarity_threshold,
            'reid_threshold': self.reid_threshold,
            'feature_weights': self.feature_weights.copy()
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if len(self.performance_history) == 0:
            return {}
        
        recent = list(self.performance_history)[-20:]
        return {
            'avg_track_quality': float(np.mean([p['track_quality'] for p in recent])),
            'avg_match_accuracy': float(np.mean([p['match_accuracy'] for p in recent])),
            'avg_false_positives': float(np.mean([p['false_positives'] for p in recent])),
            'avg_false_negatives': float(np.mean([p['false_negatives'] for p in recent])),
            'current_thresholds': self.get_current_thresholds()
        }

