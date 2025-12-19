"""
Hard Negative Mining Module
Actively samples difficult negative examples during matching to improve discrimination.

Hard negatives are examples that are similar to the positive but are actually different players.
Mining these helps the model learn better boundaries between players.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from collections import deque
import random


class HardNegativeMiner:
    """
    Mines hard negative examples during player matching.
    
    Hard negatives are:
    - Similar appearance but different players
    - Same team but different jersey numbers
    - Similar position but different identity
    """
    
    def __init__(self,
                 max_hard_negatives: int = 50,  # Maximum hard negatives to store per player
                 similarity_threshold: float = 0.4,  # Minimum similarity to be considered "hard"
                 max_similarity: float = 0.7,  # Maximum similarity (too similar = might be same player)
                 min_confidence: float = 0.3):  # Minimum confidence for negative examples
        """
        Initialize Hard Negative Miner
        
        Args:
            max_hard_negatives: Maximum hard negatives to store per player
            similarity_threshold: Minimum similarity to be considered "hard" (similar but wrong)
            max_similarity: Maximum similarity (above this might be same player, not negative)
            min_confidence: Minimum confidence for negative examples
        """
        self.max_hard_negatives = max_hard_negatives
        self.similarity_threshold = similarity_threshold
        self.max_similarity = max_similarity
        self.min_confidence = min_confidence
        
        # Store hard negatives per player
        # Format: player_id -> deque of (feature_vector, track_id, similarity, frame_num)
        self.hard_negatives: Dict[str, deque] = {}
        
        # Track negative mining statistics
        self.mining_stats = {
            'total_mined': 0,
            'total_used': 0,
            'improvements': 0  # Times hard negatives improved discrimination
        }
    
    def mine_negative(self,
                     player_id: str,
                     player_feature: np.ndarray,
                     candidate_feature: np.ndarray,
                     candidate_track_id: int,
                     similarity: float,
                     confidence: float = 0.5,
                     frame_num: int = 0,
                     jersey_number_match: bool = False,
                     team_match: bool = False) -> bool:
        """
        Mine a hard negative example
        
        Args:
            player_id: Player identifier (positive example)
            player_feature: Feature vector of the player
            candidate_feature: Feature vector of candidate (potential negative)
            candidate_track_id: Track ID of candidate
            similarity: Similarity score between player and candidate
            confidence: Detection confidence
            frame_num: Current frame number
            jersey_number_match: Whether jersey numbers match (if True, less likely to be negative)
            team_match: Whether teams match (if True, more likely to be hard negative)
            
        Returns:
            True if negative was mined and stored, False otherwise
        """
        # Check if this is a valid hard negative
        if similarity < self.similarity_threshold:
            # Too dissimilar - not a hard negative
            return False
        
        if similarity > self.max_similarity:
            # Too similar - might be same player, not a negative
            return False
        
        if confidence < self.min_confidence:
            # Low confidence - unreliable negative
            return False
        
        # If jersey numbers match, be more conservative (might be same player)
        if jersey_number_match and similarity > 0.6:
            return False
        
        # Initialize deque for this player if needed
        if player_id not in self.hard_negatives:
            self.hard_negatives[player_id] = deque(maxlen=self.max_hard_negatives)
        
        # Create negative example
        negative_example = {
            'feature': candidate_feature.copy(),
            'track_id': candidate_track_id,
            'similarity': similarity,
            'confidence': confidence,
            'frame_num': frame_num,
            'team_match': team_match,
            'jersey_match': jersey_number_match
        }
        
        # Add to hard negatives (deque automatically limits size)
        self.hard_negatives[player_id].append(negative_example)
        self.mining_stats['total_mined'] += 1
        
        return True
    
    def get_hard_negatives(self, 
                          player_id: str, 
                          count: int = 10,
                          min_similarity: Optional[float] = None) -> List[Dict]:
        """
        Get hard negative examples for a player
        
        Args:
            player_id: Player identifier
            count: Number of negatives to return
            min_similarity: Optional minimum similarity filter
            
        Returns:
            List of hard negative examples
        """
        if player_id not in self.hard_negatives:
            return []
        
        negatives = list(self.hard_negatives[player_id])
        
        # Filter by minimum similarity if specified
        if min_similarity is not None:
            negatives = [n for n in negatives if n['similarity'] >= min_similarity]
        
        # Sort by similarity (descending) - hardest negatives first
        negatives.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Return top N
        return negatives[:count]
    
    def compute_negative_distance(self,
                                 player_feature: np.ndarray,
                                 player_id: str) -> float:
        """
        Compute distance to nearest hard negative
        
        This helps measure how well the model discriminates this player from similar others.
        
        Args:
            player_feature: Current player feature vector
            player_id: Player identifier
            
        Returns:
            Distance to nearest hard negative (higher = better discrimination)
        """
        negatives = self.get_hard_negatives(player_id, count=5)
        
        if not negatives:
            return 1.0  # No negatives = perfect discrimination (default)
        
        # Compute cosine similarity to each negative
        similarities = []
        for neg in negatives:
            neg_feature = neg['feature']
            
            # Normalize
            player_norm = player_feature / (np.linalg.norm(player_feature) + 1e-8)
            neg_norm = neg_feature / (np.linalg.norm(neg_feature) + 1e-8)
            
            # Cosine similarity
            sim = np.dot(player_norm, neg_norm)
            similarities.append(sim)
        
        # Distance = 1 - max similarity (higher = better)
        max_sim = max(similarities) if similarities else 0.0
        distance = 1.0 - max_sim
        
        return distance
    
    def adjust_similarity_with_negatives(self,
                                         player_feature: np.ndarray,
                                         candidate_feature: np.ndarray,
                                         player_id: str,
                                         base_similarity: float) -> float:
        """
        Adjust similarity score using hard negatives
        
        If candidate is similar to known hard negatives, reduce similarity score.
        
        Args:
            player_feature: Player feature vector
            candidate_feature: Candidate feature vector
            player_id: Player identifier
            base_similarity: Base similarity score
            
        Returns:
            Adjusted similarity score
        """
        negatives = self.get_hard_negatives(player_id, count=5, min_similarity=0.3)
        
        if not negatives:
            return base_similarity
        
        # Check if candidate is similar to any hard negative
        candidate_norm = candidate_feature / (np.linalg.norm(candidate_feature) + 1e-8)
        
        max_negative_similarity = 0.0
        for neg in negatives:
            neg_feature = neg['feature']
            neg_norm = neg_feature / (np.linalg.norm(neg_feature) + 1e-8)
            
            # Cosine similarity to negative
            neg_sim = np.dot(candidate_norm, neg_norm)
            max_negative_similarity = max(max_negative_similarity, neg_sim)
        
        # If candidate is very similar to a hard negative, reduce similarity
        # This helps avoid false matches
        if max_negative_similarity > 0.6:
            # Candidate looks like a known negative - reduce confidence
            penalty = (max_negative_similarity - 0.6) * 0.5  # Penalty up to 0.2
            adjusted_similarity = base_similarity - penalty
            return max(0.0, adjusted_similarity)
        
        return base_similarity
    
    def batch_mine_negatives(self,
                            player_id: str,
                            player_feature: np.ndarray,
                            candidates: List[Tuple[np.ndarray, int, float, float]],  # (feature, track_id, similarity, confidence)
                            frame_num: int = 0,
                            jersey_numbers: Optional[Dict[int, str]] = None,
                            teams: Optional[Dict[int, str]] = None) -> int:
        """
        Mine hard negatives from a batch of candidates
        
        Args:
            player_id: Player identifier
            player_feature: Player feature vector
            candidates: List of (feature, track_id, similarity, confidence) tuples
            frame_num: Current frame number
            jersey_numbers: Optional dict mapping track_id -> jersey_number
            teams: Optional dict mapping track_id -> team
            
        Returns:
            Number of negatives mined
        """
        mined_count = 0
        
        for candidate_feature, track_id, similarity, confidence in candidates:
            # Check jersey number match
            jersey_match = False
            if jersey_numbers:
                player_jersey = None  # Would need player's jersey number
                candidate_jersey = jersey_numbers.get(track_id)
                if player_jersey and candidate_jersey and player_jersey == candidate_jersey:
                    jersey_match = True
            
            # Check team match
            team_match = False
            if teams:
                player_team = None  # Would need player's team
                candidate_team = teams.get(track_id)
                if player_team and candidate_team and player_team == candidate_team:
                    team_match = True
            
            if self.mine_negative(
                player_id, player_feature, candidate_feature, track_id,
                similarity, confidence, frame_num, jersey_match, team_match
            ):
                mined_count += 1
        
        return mined_count
    
    def clear_player_negatives(self, player_id: str):
        """Clear hard negatives for a specific player"""
        if player_id in self.hard_negatives:
            del self.hard_negatives[player_id]
    
    def clear_all(self):
        """Clear all hard negatives"""
        self.hard_negatives.clear()
        self.mining_stats = {
            'total_mined': 0,
            'total_used': 0,
            'improvements': 0
        }
    
    def get_stats(self) -> Dict:
        """Get mining statistics"""
        total_stored = sum(len(negatives) for negatives in self.hard_negatives.values())
        return {
            **self.mining_stats,
            'total_stored': total_stored,
            'players_with_negatives': len(self.hard_negatives)
        }

