"""
Learn from User Corrections
Feedback loop system to improve tracking based on user corrections
"""

import json
import os
from typing import Dict, List, Any, Optional
from collections import defaultdict
from datetime import datetime
import numpy as np

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

logger = get_logger("feedback_learner")


class FeedbackLearner:
    """
    Learns from user corrections to improve tracking accuracy
    Stores correction patterns and applies them to future tracking
    """
    
    def __init__(self, feedback_file: Optional[str] = None):
        """
        Initialize feedback learner
        
        Args:
            feedback_file: Path to JSON file storing feedback data
        """
        self.feedback_file = feedback_file or "feedback_learning.json"
        self.corrections = defaultdict(list)  # player_id -> [corrections]
        self.patterns = {}  # Learned patterns
        self.load_feedback()
    
    def record_correction(self,
                         player_id: str,
                         original_track_id: int,
                         corrected_track_id: int,
                         frame_num: int,
                         context: Optional[Dict[str, Any]] = None):
        """
        Record a user correction
        
        Args:
            player_id: Player identifier
            original_track_id: Track ID that was incorrectly assigned
            corrected_track_id: Track ID that should have been assigned
            frame_num: Frame number where correction occurred
            context: Additional context (similarity scores, features, etc.)
        """
        correction = {
            'timestamp': datetime.now().isoformat(),
            'original_track_id': original_track_id,
            'corrected_track_id': corrected_track_id,
            'frame_num': frame_num,
            'context': context or {}
        }
        
        self.corrections[player_id].append(correction)
        logger.info(f"Recorded correction for {player_id}: track {original_track_id} -> {corrected_track_id} at frame {frame_num}")
        
        # Learn from this correction
        self._learn_from_correction(player_id, correction)
        
        # Save feedback
        self.save_feedback()
    
    def _learn_from_correction(self, player_id: str, correction: Dict[str, Any]):
        """Learn patterns from a correction"""
        context = correction.get('context', {})
        
        # Extract learning signals
        if 'similarity_scores' in context:
            # Learn that certain similarity thresholds need adjustment
            original_sim = context.get('original_similarity', 0.0)
            corrected_sim = context.get('corrected_similarity', 0.0)
            
            if player_id not in self.patterns:
                self.patterns[player_id] = {
                    'similarity_adjustments': [],
                    'common_mistakes': []
                }
            
            # Record similarity adjustment needed
            if original_sim < corrected_sim:
                adjustment = corrected_sim - original_sim
                self.patterns[player_id]['similarity_adjustments'].append(adjustment)
                logger.debug(f"Learned similarity adjustment for {player_id}: +{adjustment:.3f}")
        
        # Record common mistakes
        original_track = correction['original_track_id']
        if 'common_mistakes' in self.patterns[player_id]:
            mistakes = self.patterns[player_id]['common_mistakes']
            mistake_found = False
            for mistake in mistakes:
                if mistake['wrong_track_id'] == original_track:
                    mistake['count'] += 1
                    mistake_found = True
                    break
            
            if not mistake_found:
                mistakes.append({
                    'wrong_track_id': original_track,
                    'count': 1
                })
    
    def get_adjustment(self, player_id: str) -> float:
        """
        Get similarity adjustment for a player based on learned patterns
        
        Args:
            player_id: Player identifier
            
        Returns:
            Similarity adjustment value (positive = increase threshold, negative = decrease)
        """
        if player_id not in self.patterns:
            return 0.0
        
        adjustments = self.patterns[player_id].get('similarity_adjustments', [])
        if len(adjustments) == 0:
            return 0.0
        
        # Average adjustment
        avg_adjustment = np.mean(adjustments)
        return float(avg_adjustment)
    
    def should_exclude_track(self, player_id: str, track_id: int) -> bool:
        """
        Check if a track should be excluded based on learned patterns
        
        Args:
            player_id: Player identifier
            track_id: Track ID to check
            
        Returns:
            True if track should be excluded
        """
        if player_id not in self.patterns:
            return False
        
        mistakes = self.patterns[player_id].get('common_mistakes', [])
        for mistake in mistakes:
            if mistake['wrong_track_id'] == track_id and mistake['count'] >= 3:
                # If this track was incorrectly assigned 3+ times, exclude it
                return True
        
        return False
    
    def save_feedback(self):
        """Save feedback data to file"""
        try:
            data = {
                'corrections': dict(self.corrections),
                'patterns': self.patterns,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.feedback_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved feedback data to {self.feedback_file}")
        except Exception as e:
            logger.warning(f"Error saving feedback: {e}")
    
    def load_feedback(self):
        """Load feedback data from file"""
        if not os.path.exists(self.feedback_file):
            return
        
        try:
            with open(self.feedback_file, 'r') as f:
                data = json.load(f)
            
            self.corrections = defaultdict(list, data.get('corrections', {}))
            self.patterns = data.get('patterns', {})
            
            logger.info(f"Loaded feedback data: {len(self.corrections)} players, {len(self.patterns)} patterns")
        except Exception as e:
            logger.warning(f"Error loading feedback: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get feedback learning statistics"""
        total_corrections = sum(len(corrections) for corrections in self.corrections.values())
        return {
            'total_corrections': total_corrections,
            'players_with_corrections': len(self.corrections),
            'learned_patterns': len(self.patterns),
            'feedback_file': self.feedback_file
        }

