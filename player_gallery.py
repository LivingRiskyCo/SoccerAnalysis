"""
Player Gallery System
Maintains a persistent database of player profiles for cross-video identification.

This system allows you to:
1. Tag a player once with their name and reference frames
2. Automatically recognize them in all future videos
3. Maintain consistent player IDs across different game recordings

Reference Frame Limits:
- Maximum reference frames per uniform variant: 1000 (allows players with multiple uniforms to have more data)
- Total frames per player can exceed 1000 if player has multiple uniform variants (e.g., gray jersey, orange jersey, blue practice penny)
- Frames are automatically pruned by quality (similarity > confidence > recency)
- More frames help with: different angles, lighting, poses, and game situations
"""

import json
import os
import numpy as np
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
# cv2 import removed - not used in this file

# Import filter module for feature quality checks
try:
    from reid_filter_module import ReIDFilterModule
    FILTER_MODULE_AVAILABLE = True
except ImportError:
    FILTER_MODULE_AVAILABLE = False

# Import logging and JSON utilities
try:
    from logger_config import get_logger
    logger = get_logger("gallery")
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from json_utils import safe_json_load, safe_json_save, JSONCorruptionError
    JSON_UTILS_AVAILABLE = True
except ImportError:
    JSON_UTILS_AVAILABLE = False
    logger.warning("JSON utilities not available - using standard JSON operations")


@dataclass
class PlayerProfile:
    """Profile for a single player in the gallery"""
    name: str
    jersey_number: Optional[str] = None
    team: Optional[str] = None
    features: Optional[List[float]] = None  # Re-ID embedding vector
    reference_frames: Optional[List[Dict]] = None  # List of {video_path, frame_num, bbox, uniform_info}
    dominant_color: Optional[List[int]] = None  # HSV color [H, S, V]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    # UNIFORM VARIANTS: Store reference frames organized by uniform combinations
    # This allows matching players across different uniform colors (gray, orange, blue practice penny, etc.)
    uniform_variants: Optional[Dict[str, List[Dict]]] = None  # {uniform_key: [reference_frames]}
    # uniform_key format: "jersey_color-shorts_color-socks_color" (e.g., "gray-black-white")
    
    # SHAPE FEATURES: Learned from detections
    avg_height: Optional[float] = None  # Average bounding box height (pixels)
    avg_width: Optional[float] = None  # Average bounding box width (pixels)
    height_width_ratio: Optional[float] = None  # Average height/width ratio
    shape_samples: int = 0  # Number of shape samples collected
    
    # MOVEMENT FEATURES: Learned from tracking
    avg_speed: Optional[float] = None  # Average movement speed (pixels/frame)
    max_speed: Optional[float] = None  # Maximum observed speed
    avg_acceleration: Optional[float] = None  # Average acceleration (pixels/frame²)
    movement_samples: int = 0  # Number of movement samples collected
    velocity_history: Optional[List[float]] = None  # Recent velocity samples (for pattern learning)
    
    # POSITION PREFERENCES: Field position patterns
    position_heatmap: Optional[List[List[float]]] = None  # 2D grid of position frequencies
    preferred_x: Optional[float] = None  # Average X position on field (normalized 0-1)
    preferred_y: Optional[float] = None  # Average Y position on field (normalized 0-1)
    position_samples: int = 0  # Number of position samples collected
    
    # BEHAVIORAL PATTERNS
    movement_style: Optional[str] = None  # "stationary", "moderate", "active", "very_active"
    ball_interaction_rate: Optional[float] = None  # Frequency of being near ball (0-1)
    ball_interaction_samples: int = 0
    
    # FOOT/SHOE FEATURES: For player identification by shoes
    foot_features: Optional[List[float]] = None  # Re-ID embedding vector from foot/shoe region
    foot_reference_frames: Optional[List[Dict]] = None  # List of foot region reference frames
    shoe_color: Optional[List[int]] = None  # Dominant shoe color in HSV [H, S, V]
    
    # HIGHEST QUALITY IMAGES: Best images for each body part (stored as base64 or file paths)
    # These are used for Re-ID features and verification
    best_body_image: Optional[Dict] = None  # {image_data: base64 or path, frame_num: int, bbox: list, quality: float, confidence: float, video_path: str}
    best_jersey_image: Optional[Dict] = None  # {image_data: base64 or path, frame_num: int, bbox: list, quality: float, confidence: float, video_path: str}
    best_foot_image: Optional[Dict] = None  # {image_data: base64 or path, frame_num: int, bbox: list, quality: float, confidence: float, video_path: str}
    
    # SEPARATE RE-ID FEATURES: Features extracted from specific body regions
    body_features: Optional[List[float]] = None  # Re-ID features from full body image
    jersey_features: Optional[List[float]] = None  # Re-ID features from jersey region only
    # foot_features already exists above
    
    # QUALITY METRICS: For tracking image quality
    body_image_quality_history: Optional[List[Dict]] = None  # [{quality, confidence, frame_num, timestamp}]
    jersey_image_quality_history: Optional[List[Dict]] = None  # [{quality, confidence, frame_num, timestamp}]
    
    # PER-PLAYER VISUALIZATION SETTINGS
    visualization_settings: Optional[Dict[str, Any]] = None
    # Structure:
    # {
    #     "use_custom_color": bool,  # Use custom color instead of team color
    #     "custom_color_rgb": [int, int, int],  # RGB values 0-255, e.g., [255, 0, 0] for red
    #     "box_color": [int, int, int] or None,  # Override box color (RGB)
    #     "label_color": [int, int, int] or None,  # Override label color (RGB)
    #     "feet_marker_color": [int, int, int] or None,  # Override feet marker color (RGB)
    #     "box_thickness": int or None,  # Override box thickness (1-10)
    #     "show_glow": bool or None,  # Override glow effect
    #     "glow_color": [int, int, int] or None,  # Glow color (RGB)
    #     "glow_intensity": int or None,  # Glow intensity (0-100)
    #     "show_trail": bool or None,  # Override trail visibility
    #     "trail_color": [int, int, int] or None,  # Trail color (RGB)
    #     "trail_length": int or None,  # Trail length (frames)
    #     "label_style": str or None,  # "full_name", "jersey", "initials", "number"
    #     "highlight": bool or None,  # Special highlight mode
    #     "highlight_color": [int, int, int] or None  # Highlight color (RGB)
    # }
    foot_image_quality_history: Optional[List[Dict]] = None  # [{quality, confidence, frame_num, timestamp}]
    
    # TRACK HISTORY: Breadcrumbs from gallery data
    # {track_id: count} - tracks this player has been assigned to and how many times
    track_history: Optional[Dict[int, int]] = None  # {track_id: occurrence_count}
    
    # TEAM SWITCH HISTORY: Track team changes (especially for practice mode)
    # [{frame, video, from_team, to_team}]
    team_switches: Optional[List[Dict]] = None  # List of team switch events
    
    # EVENT HISTORY: Track game events (passes, shots, tackles, goals, etc.)
    # Format: [{event_type, frame_num, timestamp, video_path, confidence, metadata, verified}]
    events: Optional[List[Dict]] = None  # List of events for this player
    event_counts: Optional[Dict[str, int]] = None  # {event_type: count} - summary counts
    # Event types: "pass", "shot", "tackle", "goal", "foul", "corner", "free_kick", "save", "substitution"
    
    # ENHANCED: Multiple gallery entries per player for better matching
    alternative_features: Optional[List[Dict]] = None  # List of alternative feature sets: [{'features': ..., 'quality': ..., 'frame': ...}, ...]
    max_alternative_entries: int = 5  # Maximum number of alternative entries to store
    
    # ENHANCED: Feature diversity tracking
    feature_diversity_score: Optional[float] = None  # Diversity score (0-1, higher = more diverse features)
    feature_clusters: Optional[List[int]] = None  # Cluster assignments for reference frames (for diversity analysis)
    diversity_samples: int = 0  # Number of diversity samples collected
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        
        # Recursively convert numpy types to native Python types
        def convert_numpy_types(obj):
            """Recursively convert numpy types to native Python types"""
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, (np.integer, np.floating, np.bool_)):
                return obj.item()  # Convert numpy scalar to Python native type
            elif hasattr(obj, 'item') and type(obj).__module__ == 'numpy':
                # Catch-all for any numpy scalar types (float32, float64, int32, etc.)
                return obj.item()
            elif isinstance(obj, dict):
                return {key: convert_numpy_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            elif isinstance(obj, tuple):
                return tuple(convert_numpy_types(item) for item in obj)
            else:
                return obj
        
        # Convert numpy arrays to lists if present
        if self.features is not None and isinstance(self.features, np.ndarray):
            data['features'] = self.features.tolist()
        if self.dominant_color is not None and isinstance(self.dominant_color, np.ndarray):
            data['dominant_color'] = self.dominant_color.tolist()
        
        # Convert all numpy types in the data dictionary
        data = convert_numpy_types(data)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Create PlayerProfile from dictionary"""
        # Convert lists back to numpy arrays if needed
        if 'features' in data and data['features'] is not None:
            data['features'] = np.array(data['features'])
        if 'dominant_color' in data and data['dominant_color'] is not None:
            data['dominant_color'] = np.array(data['dominant_color'])
        
        # ENHANCED: Ensure backward compatibility - initialize alternative_features if missing
        if 'alternative_features' not in data:
            data['alternative_features'] = None
        if 'max_alternative_entries' not in data:
            data['max_alternative_entries'] = 5
        
        # ENHANCED: Initialize feature diversity fields if missing
        if 'feature_diversity_score' not in data:
            data['feature_diversity_score'] = None
        if 'feature_clusters' not in data:
            data['feature_clusters'] = None
        if 'diversity_samples' not in data:
            data['diversity_samples'] = 0
        
        return cls(**data)


class PlayerGallery:
    """
    Manages a persistent gallery of known players.
    
    The gallery stores player profiles with their visual features,
    allowing for cross-video identification and consistent naming.
    """
    
    def __init__(self, gallery_path: str = "player_gallery.json"):
        """
        Initialize Player Gallery
        
        Args:
            gallery_path: Path to the gallery JSON file
        """
        self.gallery_path = gallery_path
        self.players: Dict[str, PlayerProfile] = {}
        self._update_count: Dict[str, int] = {}  # Track update counts per player
        
        # ENHANCED: Gallery statistics for adaptive thresholds
        self._gallery_stats_cache: Optional[Dict] = None
        self._gallery_stats_cache_frame: int = 0
        self._gallery_stats_update_interval: int = 1000  # Update stats every 1000 frames
        
        self.load_gallery()
    
    def load_gallery(self):
        """Load player gallery from disk with corruption protection"""
        gallery_path = Path(self.gallery_path)
        
        if JSON_UTILS_AVAILABLE:
            try:
                # Use safe JSON loading with automatic recovery
                data = safe_json_load(gallery_path, default={}, create_if_missing=True)
                
                # Convert dict entries to PlayerProfile objects
                for player_id, player_data in data.items():
                    try:
                        profile = PlayerProfile.from_dict(player_data)
                        # ENHANCED: Ensure backward compatibility - initialize missing attributes
                        if not hasattr(profile, 'alternative_features'):
                            profile.alternative_features = None
                        if not hasattr(profile, 'max_alternative_entries'):
                            profile.max_alternative_entries = 5
                        self.players[player_id] = profile
                    except Exception as e:
                        logger.warning(f"Could not load player {player_id}: {e}")
                        continue
                
                logger.info(f"Loaded {len(self.players)} players from gallery: {self.gallery_path}")
            except JSONCorruptionError as e:
                logger.error(f"Gallery file corrupted and cannot be recovered: {e}")
                logger.info("Starting with empty gallery. You can use player_gallery_seeder.py to re-add players.")
                self.players = {}
            except Exception as e:
                logger.error(f"Could not load player gallery: {e}", exc_info=True)
                logger.info("Starting with empty gallery. You can use player_gallery_seeder.py to re-add players.")
                self.players = {}
        else:
            # Fallback to original method if JSON utils not available
            if os.path.exists(self.gallery_path):
                try:
                    with open(self.gallery_path, 'r') as f:
                        data = json.load(f)
                    
                    # Convert dict entries to PlayerProfile objects
                    for player_id, player_data in data.items():
                        profile = PlayerProfile.from_dict(player_data)
                        if not hasattr(profile, 'alternative_features'):
                            profile.alternative_features = None
                        if not hasattr(profile, 'max_alternative_entries'):
                            profile.max_alternative_entries = 5
                        self.players[player_id] = profile
                    
                    logger.info(f"Loaded {len(self.players)} players from gallery: {self.gallery_path}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {e}")
                    logger.info("Attempting automatic repair...")
                    repair_successful = self._attempt_repair()
                    if repair_successful:
                        try:
                            with open(self.gallery_path, 'r') as f:
                                data = json.load(f)
                            for player_id, player_data in data.items():
                                profile = PlayerProfile.from_dict(player_data)
                                if not hasattr(profile, 'alternative_features'):
                                    profile.alternative_features = None
                                if not hasattr(profile, 'max_alternative_entries'):
                                    profile.max_alternative_entries = 5
                                self.players[player_id] = profile
                            logger.info(f"Successfully loaded {len(self.players)} players after repair!")
                            return
                        except Exception as reload_error:
                            logger.error(f"Repair succeeded but reload failed: {reload_error}")
                    logger.info("Starting with empty gallery.")
                    self.players = {}
                except Exception as e:
                    logger.error(f"Could not load player gallery: {e}", exc_info=True)
                    self.players = {}
            else:
                logger.info("No existing player gallery found. Creating new gallery.")
                self.players = {}
    
    def _attempt_repair(self) -> bool:
        """
        Attempt to automatically repair corrupted JSON file.
        
        Returns:
            True if repair was successful, False otherwise
        """
        import re
        import shutil
        
        try:
            # Read the file as text
            with open(self.gallery_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Strategy 1: Fix common JSON issues (trailing commas, etc.)
            # Remove trailing commas before } or ]
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            
            # Try to parse after basic fixes
            try:
                data = json.loads(content)
                # Save repaired version
                with open(self.gallery_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"   ✓ Successfully repaired JSON using basic fixes!")
                return True
            except json.JSONDecodeError:
                pass  # Try next strategy
            
            # Strategy 2: Try to salvage valid players before corruption point
            # Find the error line and try to load everything before it
            try:
                # Try to find where corruption starts by attempting partial loads
                lines = content.split('\n')
                valid_players = {}
                
                # Try loading progressively smaller portions
                for end_line in range(len(lines), 0, -1):
                    try:
                        partial_content = '\n'.join(lines[:end_line])
                        # Try to make it valid JSON by closing any open structures
                        # Count open braces
                        open_braces = partial_content.count('{') - partial_content.count('}')
                        if open_braces > 0:
                            # Close remaining braces
                            partial_content += '\n' + '}' * open_braces
                        elif open_braces < 0:
                            # Too many closing braces, remove excess
                            excess = -open_braces
                            partial_content = partial_content.rsplit('}', excess)[0]
                            partial_content += '}'
                        
                        data = json.loads(partial_content)
                        # If we got here, we have valid data
                        valid_players = data
                        print(f"   ✓ Successfully salvaged {len(valid_players)} players before corruption point!")
                        # Save salvaged version
                        with open(self.gallery_path, 'w', encoding='utf-8') as f:
                            json.dump(valid_players, f, indent=2, ensure_ascii=False)
                        return True
                    except (json.JSONDecodeError, ValueError):
                        continue
            except Exception:
                pass
            
            return False
        except Exception as e:
            print(f"   ⚠ Repair attempt failed: {e}")
            return False
    
    def get_total_reference_frames(self, player_id: str) -> int:
        """
        Get total reference frame count for a player, including uniform variants.
        
        Args:
            player_id: Player ID to count reference frames for
            
        Returns:
            Total number of reference frames (main list + all uniform variants)
        """
        if player_id not in self.players:
            return 0
        
        profile = self.players[player_id]
        total = 0
        
        # Count main reference_frames list
        if profile.reference_frames:
            total += len(profile.reference_frames)
        
        # Count reference frames in uniform variants
        if profile.uniform_variants:
            for variant_refs in profile.uniform_variants.values():
                if variant_refs:
                    total += len(variant_refs)
        
        return total
    
    def save_gallery(self):
        """Save player gallery to disk with corruption protection"""
        try:
            # Convert PlayerProfile objects to dictionaries
            data = {player_id: profile.to_dict() 
                   for player_id, profile in self.players.items()}
            
            gallery_path = Path(self.gallery_path)
            
            if JSON_UTILS_AVAILABLE:
                # Use safe JSON saving with atomic writes and backups
                success = safe_json_save(gallery_path, data, create_backup=True, validate=True)
                if success:
                    logger.info(f"Saved {len(self.players)} players to gallery: {self.gallery_path}")
                else:
                    logger.error(f"Failed to save gallery: {self.gallery_path}")
                    raise Exception("Failed to save gallery")
            else:
                # Fallback to original method
                with open(self.gallery_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved {len(self.players)} players to gallery: {self.gallery_path}")
        except Exception as e:
            logger.error(f"Could not save player gallery: {e}", exc_info=True)
            raise  # Re-raise to allow caller to handle
    
    def add_player(self, 
                   name: str, 
                   features: np.ndarray,
                   jersey_number: Optional[str] = None,
                   team: Optional[str] = None,
                   reference_frame: Optional[Dict] = None,
                   dominant_color: Optional[np.ndarray] = None,
                   visualization_settings: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a new player to the gallery
        
        Args:
            name: Player's name
            features: Re-ID feature embedding (numpy array)
            jersey_number: Jersey number (optional)
            team: Team name (optional)
            reference_frame: Dict with {video_path, frame_num, bbox} (optional)
            dominant_color: Dominant jersey color in HSV (optional)
            visualization_settings: Per-player visualization settings (optional)
        
        Returns:
            player_id: Unique identifier for the player
        """
        # Generate unique player ID from name
        player_id = name.lower().replace(" ", "_")
        
        # Check if player already exists
        if player_id in self.players:
            print(f"⚠ Player '{name}' already exists. Use update_player() to modify.")
            return player_id
        
        # Create new profile
        profile = PlayerProfile(
            name=name,
            jersey_number=jersey_number,
            team=team,
            features=features.tolist() if isinstance(features, np.ndarray) else features,
            reference_frames=[reference_frame] if reference_frame else [],
            dominant_color=dominant_color.tolist() if isinstance(dominant_color, np.ndarray) else dominant_color,
            visualization_settings=visualization_settings,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        self.players[player_id] = profile
        self.save_gallery()
        
        print(f"✓ Added player '{name}' to gallery (ID: {player_id})")
        return player_id
    
    def update_player(self,
                     player_id: str,
                     name: Optional[str] = None,
                     features: Optional[np.ndarray] = None,
                     reference_frame: Optional[Dict] = None,
                     jersey_number: Optional[str] = None,
                     team: Optional[str] = None,
                     dominant_color: Optional[np.ndarray] = None,
                     uniform_info: Optional[Dict] = None,
                     foot_features: Optional[np.ndarray] = None,
                     foot_reference_frame: Optional[Dict] = None,
                     shoe_color: Optional[np.ndarray] = None,
                     body_features: Optional[np.ndarray] = None,
                     jersey_features: Optional[np.ndarray] = None,
                     visualization_settings: Optional[Dict[str, Any]] = None):
        """
        Update an existing player's profile
        
        Args:
            player_id: Player identifier
            name: Update player name
            features: New Re-ID features to add/average with existing
            reference_frame: Additional reference frame to add
            jersey_number: Update jersey number
            team: Update team
            dominant_color: Update dominant color
            uniform_info: Dict with uniform details {'jersey_color': 'gray', 'shorts_color': 'black', 'socks_color': 'white'}
                          Used to organize reference frames by uniform variant for better cross-uniform matching
            visualization_settings: Per-player visualization settings (optional)
        """
        if player_id not in self.players:
            print(f"⚠ Player ID '{player_id}' not found in gallery.")
            return
        
        profile = self.players[player_id]
        
        # ENHANCED: Quality-weighted feature aggregation (instead of simple average)
        # This prevents high-quality features from being diluted by low-quality ones
        if features is not None:
            if isinstance(features, np.ndarray):  # type: ignore[reportUnnecessaryIsInstance]
                features = features.tolist()
            
            # Calculate quality score for new features
            # 🎓 ANCHOR FRAMES: Anchor frames (confidence 1.00, similarity 1.00) are ABSOLUTE TRUTH
            # They should be given maximum weight for learning
            new_quality = self._calculate_feature_quality_score(reference_frame)
            
            # CRITICAL: If this is an anchor frame (confidence 1.00, similarity 1.00), give it maximum quality
            is_anchor_frame = False
            if reference_frame is not None:
                ref_confidence = reference_frame.get('confidence', 0.0)
                ref_similarity = reference_frame.get('similarity', 0.0)
                is_anchor = reference_frame.get('is_anchor', False)
                # Anchor frames are ground truth - they should have maximum quality for learning
                if (ref_confidence >= 1.00 and ref_similarity >= 1.00) or is_anchor:
                    new_quality = 1.0  # Maximum quality for anchor frames
                    is_anchor_frame = True
            
            if profile.features is not None:
                # Quality-weighted average instead of simple average
                existing = np.array(profile.features)
                new_features = np.array(features)
                
                # Get existing feature quality (default to 0.5, or use quality from last reference frame)
                # For anchor frames, we want to give them maximum weight
                existing_quality = 0.5  # Default quality
                if profile.reference_frames and len(profile.reference_frames) > 0:
                    # Use quality from most recent reference frame as existing quality estimate
                    last_ref = profile.reference_frames[-1]
                    existing_quality = self._calculate_feature_quality_score(last_ref)
                
                # 🎓 ANCHOR FRAMES: Anchor frames (confidence 1.00) should dominate the feature average
                # If new features are from an anchor frame, give them much higher weight
                # Anchor frames are ABSOLUTE TRUTH - they should dominate the player's profile
                if is_anchor_frame:
                    # Anchor frames get 10x weight - they are ground truth and should dominate learning
                    # This ensures anchor frame features are the primary source for player identification
                    anchor_weight = 10.0
                    existing_quality_weighted = existing_quality / anchor_weight  # Reduce existing weight
                    new_quality_weighted = new_quality * anchor_weight  # Boost anchor weight
                    total_quality = existing_quality_weighted + new_quality_weighted
                    if total_quality > 0:
                        weighted_averaged = (existing_quality_weighted * existing + new_quality_weighted * new_features) / total_quality
                    else:
                        weighted_averaged = new_features  # If total is 0, use anchor features directly
                else:
                    # Normal quality-weighted average for non-anchor frames
                    total_quality = existing_quality + new_quality
                    if total_quality > 0:
                        weighted_averaged = (existing_quality * existing + new_quality * new_features) / total_quality
                    else:
                        # Fallback to simple average if no quality info
                        weighted_averaged = (existing + new_features) / 2
                if total_quality > 0:
                    weighted_averaged = (existing_quality * existing + new_quality * new_features) / total_quality
                else:
                    # Fallback to simple average if no quality info
                    weighted_averaged = (existing + new_features) / 2
                
                # Normalize
                weighted_averaged = weighted_averaged / (np.linalg.norm(weighted_averaged) + 1e-8)
                profile.features = weighted_averaged.tolist()
                
                # Quality is calculated on-the-fly from reference frames, no need to store separately
                # Anchor frames will naturally have higher quality scores in future calculations
            else:
                # First feature - store directly
                if isinstance(features, np.ndarray):
                    profile.features = features.tolist()
                else:
                    profile.features = features
                # Quality is calculated on-the-fly from reference frames, no need to store separately
        
        # ENHANCED: False match detection - check if similarity is too low
        # If similarity is very low (< 0.3), this might be a false match
        # Don't add reference frames with clearly wrong matches
        if reference_frame is not None:
            ref_similarity = reference_frame.get('similarity', 0.5)
            ref_confidence = reference_frame.get('confidence', 0.5)
            
            # CRITICAL: Reject low-confidence matches to prevent gallery pollution
            # EXCEPTION: Anchor frames (ground truth) always get added regardless of similarity threshold
            # Anchor frames are ABSOLUTE TRUTH - they should always be learned from
            is_anchor = reference_frame.get('is_anchor', False)
            ref_confidence = reference_frame.get('confidence', 0.0)
            is_anchor_frame = is_anchor or (ref_confidence >= 1.00 and ref_similarity >= 1.00)
            
            if not is_anchor_frame:
                # Require minimum similarity of 0.75 for non-anchor gallery updates (was 0.3, too permissive)
                if ref_similarity < 0.75:
                    # Don't add this reference frame - similarity too low (likely false match)
                    if ref_similarity >= 0.6:  # Only log if it was close (avoid spam)
                        print(f"   ⚠ REJECTED: Low similarity match for '{profile.name}' (similarity: {ref_similarity:.2f} < 0.75 threshold)")
                    return  # Early return to skip the update
            
            # Also require minimum detection confidence (unless it's an anchor frame)
            if not is_anchor_frame and ref_confidence < 0.4:
                # Don't add this reference frame - detection confidence too low
                return  # Early return to skip the update
        
        # Add reference frame with automatic cleanup to prevent excessive storage
        if reference_frame is not None:
            # Add uniform info to reference frame if provided
            if uniform_info is not None:
                reference_frame['uniform_info'] = uniform_info
            
            # CRITICAL FIX: Check for duplicate reference frames (same video_path and frame_num)
            # Only keep one reference per frame to avoid redundant storage
            ref_video_path = reference_frame.get('video_path')
            ref_frame_num = reference_frame.get('frame_num')
            
            # Store in main reference_frames list (backward compatibility)
            if profile.reference_frames is None:
                profile.reference_frames = []
            
            # Check if this frame already exists
            frame_exists = False
            if ref_video_path is not None and ref_frame_num is not None:
                for existing_ref in profile.reference_frames:
                    existing_video = existing_ref.get('video_path')
                    existing_frame = existing_ref.get('frame_num')
                    if existing_video == ref_video_path and existing_frame == ref_frame_num:
                        frame_exists = True
                        # Replace with new reference if it has higher quality/confidence
                        new_quality = reference_frame.get('quality', 0.0)
                        new_confidence = reference_frame.get('confidence', 0.0)
                        existing_quality = existing_ref.get('quality', 0.0)
                        existing_confidence = existing_ref.get('confidence', 0.0)
                        
                        # Replace if new reference is better (higher quality or confidence)
                        if new_quality > existing_quality or (new_quality == existing_quality and new_confidence > existing_confidence):
                            profile.reference_frames.remove(existing_ref)
                            frame_exists = False  # Allow adding the better one
                        break
            
            # Only add if frame doesn't exist (or we removed the old one)
            if not frame_exists:
                profile.reference_frames.append(reference_frame)
            
            # UNIFORM VARIANTS: Also organize by uniform type for better matching
            if uniform_info is not None:
                if profile.uniform_variants is None:
                    profile.uniform_variants = {}
                
                # Create uniform key: "jersey_color-shorts_color-socks_color"
                jersey = uniform_info.get('jersey_color', 'unknown').lower()
                shorts = uniform_info.get('shorts_color', 'unknown').lower()
                socks = uniform_info.get('socks_color', 'unknown').lower()
                uniform_key = f"{jersey}-{shorts}-{socks}"
                
                # Add to uniform-specific list
                if uniform_key not in profile.uniform_variants:
                    profile.uniform_variants[uniform_key] = []
                
                # Check for duplicates in uniform_variants too
                frame_exists_in_variant = False
                if ref_video_path is not None and ref_frame_num is not None:
                    for existing_ref in profile.uniform_variants[uniform_key]:
                        existing_video = existing_ref.get('video_path')
                        existing_frame = existing_ref.get('frame_num')
                        if existing_video == ref_video_path and existing_frame == ref_frame_num:
                            frame_exists_in_variant = True
                            # Replace with new reference if it has higher quality/confidence
                            new_quality = reference_frame.get('quality', 0.0)
                            new_confidence = reference_frame.get('confidence', 0.0)
                            existing_quality = existing_ref.get('quality', 0.0)
                            existing_confidence = existing_ref.get('confidence', 0.0)
                            
                            if new_quality > existing_quality or (new_quality == existing_quality and new_confidence > existing_confidence):
                                profile.uniform_variants[uniform_key].remove(existing_ref)
                                frame_exists_in_variant = False
                            break
                
                # Only add if frame doesn't exist in this variant (or we removed the old one)
                if not frame_exists_in_variant:
                    profile.uniform_variants[uniform_key].append(reference_frame)
                
                # ENHANCED: Limit reference frames per uniform variant (1000 per variant for better recognition)
                # This allows players with multiple uniforms to have more reference frames
                MAX_FRAMES_PER_UNIFORM = 1000
                if len(profile.uniform_variants[uniform_key]) > MAX_FRAMES_PER_UNIFORM:
                    # Create temporary profile object for pruning
                    class TempProfile:
                        def __init__(self, ref_frames):
                            self.reference_frames = ref_frames
                            self.uniform_variants = None
                    temp_profile = TempProfile(profile.uniform_variants[uniform_key])
                    # Use quality and diversity-based pruning
                    self._prune_reference_frames_by_quality_and_diversity(temp_profile, MAX_FRAMES_PER_UNIFORM)
                    profile.uniform_variants[uniform_key] = temp_profile.reference_frames[:MAX_FRAMES_PER_UNIFORM]
            
            # ENHANCED: Update feature diversity score after adding reference frame
            # This helps track how diverse the player's reference frames are
            profile.feature_diversity_score = self._calculate_feature_diversity(profile)
            profile.diversity_samples += 1
            
            # ENHANCED: Limit reference frames per player (keep highest quality AND diverse)
            # NOTE: With uniform variants, total frames can exceed this (1000 per variant)
            # This limit applies to the main reference_frames list (backward compatibility)
            # Uniform variants can have up to 1000 frames each, so total can be much higher
            MAX_REFERENCE_FRAMES = 1000
            if len(profile.reference_frames) > MAX_REFERENCE_FRAMES:
                # Keep the highest quality AND most diverse frames
                # This ensures good coverage of different conditions (angles, lighting, uniforms)
                self._prune_reference_frames_by_quality_and_diversity(profile, MAX_REFERENCE_FRAMES)
                # Update diversity score after pruning
                profile.feature_diversity_score = self._calculate_feature_diversity(profile)
            
            # AUTOMATIC HIGHEST QUALITY IMAGE TRACKING
            # Extract and store best quality images for body, jersey, and feet
            try:
                video_path = reference_frame.get('video_path')
                frame_num = reference_frame.get('frame_num')
                bbox = reference_frame.get('bbox')
                similarity = reference_frame.get('similarity', 0.0)
                confidence = reference_frame.get('confidence', 0.0)
                
                if video_path and frame_num is not None and bbox:
                    # Extract images from video
                    body_image, jersey_image, foot_image = self._extract_images_from_reference(
                        video_path, frame_num, bbox
                    )
                    
                    # Calculate quality scores
                    if body_image is not None:
                        quality = self.calculate_image_quality_score(body_image, bbox, similarity, confidence)
                        reference_frame['quality'] = quality  # Store in reference frame too
                        
                        # Check if this is better than current best body image
                        if profile.best_body_image is None or quality > profile.best_body_image.get('quality', 0.0):
                            # Encode image as base64 for storage
                            import base64
                            import cv2
                            _, buffer = cv2.imencode('.jpg', body_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
                            image_base64 = base64.b64encode(buffer).decode('utf-8')
                            
                            profile.best_body_image = {
                                'image_data': image_base64,
                                'frame_num': frame_num,
                                'bbox': bbox,
                                'quality': quality,
                                'confidence': confidence,
                                'video_path': video_path,
                                'updated_at': datetime.now().isoformat()
                            }
                            
                            # Update quality history
                            if profile.body_image_quality_history is None:
                                profile.body_image_quality_history = []
                            profile.body_image_quality_history.append({
                                'quality': quality,
                                'confidence': confidence,
                                'frame_num': frame_num,
                                'timestamp': datetime.now().isoformat()
                            })
                            if len(profile.body_image_quality_history) > 50:
                                profile.body_image_quality_history = profile.body_image_quality_history[-50:]
                    
                    if jersey_image is not None:
                        jersey_quality = self.calculate_image_quality_score(jersey_image, bbox, similarity, confidence)
                        if profile.best_jersey_image is None or jersey_quality > profile.best_jersey_image.get('quality', 0.0):
                            import base64
                            import cv2
                            _, buffer = cv2.imencode('.jpg', jersey_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
                            image_base64 = base64.b64encode(buffer).decode('utf-8')
                            
                            profile.best_jersey_image = {
                                'image_data': image_base64,
                                'frame_num': frame_num,
                                'bbox': bbox,
                                'quality': jersey_quality,
                                'confidence': confidence,
                                'video_path': video_path,
                                'updated_at': datetime.now().isoformat()
                            }
                            
                            if profile.jersey_image_quality_history is None:
                                profile.jersey_image_quality_history = []
                            profile.jersey_image_quality_history.append({
                                'quality': jersey_quality,
                                'confidence': confidence,
                                'frame_num': frame_num,
                                'timestamp': datetime.now().isoformat()
                            })
                            if len(profile.jersey_image_quality_history) > 50:
                                profile.jersey_image_quality_history = profile.jersey_image_quality_history[-50:]
                    
                    if foot_image is not None:
                        foot_quality = self.calculate_image_quality_score(foot_image, bbox, similarity, confidence)
                        if profile.best_foot_image is None or foot_quality > profile.best_foot_image.get('quality', 0.0):
                            import base64
                            import cv2
                            _, buffer = cv2.imencode('.jpg', foot_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
                            image_base64 = base64.b64encode(buffer).decode('utf-8')
                            
                            profile.best_foot_image = {
                                'image_data': image_base64,
                                'frame_num': frame_num,
                                'bbox': bbox,
                                'quality': foot_quality,
                                'confidence': confidence,
                                'video_path': video_path,
                                'updated_at': datetime.now().isoformat()
                            }
                            
                            if profile.foot_image_quality_history is None:
                                profile.foot_image_quality_history = []
                            profile.foot_image_quality_history.append({
                                'quality': foot_quality,
                                'confidence': confidence,
                                'frame_num': frame_num,
                                'timestamp': datetime.now().isoformat()
                            })
                            if len(profile.foot_image_quality_history) > 50:
                                profile.foot_image_quality_history = profile.foot_image_quality_history[-50:]
            except Exception as e:
                # Don't fail if image extraction fails - just log and continue
                print(f"⚠ Could not extract/update quality images: {e}")
        
        # Update body features (separate from general features)
        if body_features is not None:
            if isinstance(body_features, np.ndarray):
                # Store directly (don't average - these are from highest quality images)
                profile.body_features = body_features.tolist()
            else:
                profile.body_features = body_features
        
        # Update jersey features (separate from general features)
        if jersey_features is not None:
            if isinstance(jersey_features, np.ndarray):
                # Store directly (don't average - these are from highest quality images)
                profile.jersey_features = jersey_features.tolist()
            else:
                profile.jersey_features = jersey_features
        
        # Update foot features (average with existing if both present)
        if foot_features is not None:
            if isinstance(foot_features, np.ndarray):  # type: ignore[reportUnnecessaryIsInstance]
                foot_features = foot_features.tolist()
            
            if profile.foot_features is not None:
                # Average with existing foot features
                existing = np.array(profile.foot_features)
                new_foot_features = np.array(foot_features)
                averaged = (existing + new_foot_features) / 2
                # Normalize
                averaged = averaged / (np.linalg.norm(averaged) + 1e-8)
                profile.foot_features = averaged.tolist()
            else:
                if isinstance(foot_features, np.ndarray):
                    profile.foot_features = foot_features.tolist()
                else:
                    profile.foot_features = foot_features
        
        # Add foot reference frame
        if foot_reference_frame is not None:
            if profile.foot_reference_frames is None:
                profile.foot_reference_frames = []
            
            # CRITICAL FIX: Check for duplicate foot reference frames (same video_path and frame_num)
            ref_video_path = foot_reference_frame.get('video_path')
            ref_frame_num = foot_reference_frame.get('frame_num')
            
            frame_exists = False
            if ref_video_path is not None and ref_frame_num is not None:
                for existing_ref in profile.foot_reference_frames:
                    existing_video = existing_ref.get('video_path')
                    existing_frame = existing_ref.get('frame_num')
                    if existing_video == ref_video_path and existing_frame == ref_frame_num:
                        frame_exists = True
                        # Replace with new reference if it has higher quality/confidence
                        new_quality = foot_reference_frame.get('quality', 0.0)
                        new_confidence = foot_reference_frame.get('confidence', 0.0)
                        existing_quality = existing_ref.get('quality', 0.0)
                        existing_confidence = existing_ref.get('confidence', 0.0)
                        
                        if new_quality > existing_quality or (new_quality == existing_quality and new_confidence > existing_confidence):
                            profile.foot_reference_frames.remove(existing_ref)
                            frame_exists = False
                        break
            
            # Only add if frame doesn't exist (or we removed the old one)
            if not frame_exists:
                profile.foot_reference_frames.append(foot_reference_frame)
            
            # Limit foot reference frames (keep most recent 100)
            MAX_FOOT_FRAMES = 100
            if len(profile.foot_reference_frames) > MAX_FOOT_FRAMES:
                profile.foot_reference_frames = profile.foot_reference_frames[-MAX_FOOT_FRAMES:]
        
        # Update shoe color
        if shoe_color is not None:
            if isinstance(shoe_color, np.ndarray):  # type: ignore[reportUnnecessaryIsInstance]
                profile.shoe_color = shoe_color.tolist()
            elif isinstance(shoe_color, list):  # type: ignore[reportUnnecessaryIsInstance]
                profile.shoe_color = shoe_color
            else:
                profile.shoe_color = list(shoe_color) if hasattr(shoe_color, '__iter__') else [shoe_color]
        
        # Update other fields
        # CRITICAL: Handle name changes properly - if name changes, player_id must change too
        old_name = profile.name
        new_player_id = None
        
        if name is not None and name != old_name:
            # Name is changing - need to update player_id
            new_player_id = name.lower().replace(" ", "_")
            
            # Check if new player_id already exists (would create duplicate)
            if new_player_id in self.players and new_player_id != player_id:
                # New name would create a duplicate - don't allow rename
                raise ValueError(f"Cannot rename '{old_name}' to '{name}': Player '{name}' already exists in gallery!")
            
            # Update the name
            profile.name = name
            
            # If player_id changed, move the player to new key in dictionary
            if new_player_id != player_id:
                # Move player to new key
                self.players[new_player_id] = self.players.pop(player_id)
                # Update player_id reference for caller
                player_id = new_player_id
                print(f"✓ Renamed player: '{old_name}' (ID: {player_id}) → '{name}' (ID: {new_player_id})")
        elif name is not None:
            # Name is same, just update it
            profile.name = name
        
        if jersey_number is not None:
            profile.jersey_number = jersey_number
        if team is not None:
            profile.team = team
        if visualization_settings is not None:
            profile.visualization_settings = visualization_settings
        if dominant_color is not None:
            # Convert numpy array to list if needed
            if isinstance(dominant_color, np.ndarray):  # type: ignore[reportUnnecessaryIsInstance]
                profile.dominant_color = dominant_color.tolist()
            elif isinstance(dominant_color, list):  # type: ignore[reportUnnecessaryIsInstance]
                profile.dominant_color = dominant_color
            else:
                # Convert other types to list
                profile.dominant_color = list(dominant_color) if hasattr(dominant_color, '__iter__') else [dominant_color]
        
        profile.updated_at = datetime.now().isoformat()
        # CRITICAL: Save immediately when called from GUI/user actions
        # For batch updates during analysis, the caller should save periodically
        # But for manual edits (name changes, etc.), we must save immediately
        # Check if this is a manual edit by checking if name/jersey/team changed
        is_manual_edit = (name is not None or jersey_number is not None or team is not None)
        if is_manual_edit:
            self.save_gallery()  # Save immediately for manual edits
        # For feature/reference_frame updates during analysis, caller handles saving
        
        # OPTIMIZATION: Only print update message periodically to reduce console spam
        # Print every 100th update or if this is a new player
        # Use the final player_id (may have changed if name was updated)
        final_player_id = new_player_id if new_player_id else player_id
        if not hasattr(self, '_update_count'):
            self._update_count = {}
        if final_player_id not in self._update_count:
            self._update_count[final_player_id] = 0
        self._update_count[final_player_id] += 1
        
        # Only log every 100 updates per player, or on first update
        if self._update_count[final_player_id] == 1 or self._update_count[final_player_id] % 100 == 0:
            print(f"✓ Updated player '{profile.name}' (ID: {final_player_id})" + (f" ({self._update_count[final_player_id]} updates)" if self._update_count[final_player_id] > 1 else ""))
    
    def update_highest_quality_images(self,
                                    player_id: str,
                                    body_image_data: Optional[Dict] = None,
                                    jersey_image_data: Optional[Dict] = None,
                                    foot_image_data: Optional[Dict] = None,
                                    body_features: Optional[np.ndarray] = None,
                                    jersey_features: Optional[np.ndarray] = None):
        """
        Update highest quality images for a player (body, jersey, feet)
        
        Args:
            player_id: Player identifier
            body_image_data: Dict with {image_data: base64/path, frame_num: int, bbox: list, quality: float, confidence: float, video_path: str}
            jersey_image_data: Dict with {image_data: base64/path, frame_num: int, bbox: list, quality: float, confidence: float, video_path: str}
            foot_image_data: Dict with {image_data: base64/path, frame_num: int, bbox: list, quality: float, confidence: float, video_path: str}
            body_features: Re-ID features extracted from body image
            jersey_features: Re-ID features extracted from jersey image
        """
        if player_id not in self.players:
            return
        
        profile = self.players[player_id]
        
        # Update body image if provided and better quality
        if body_image_data is not None:
            quality = body_image_data.get('quality', 0.0)
            confidence = body_image_data.get('confidence', 0.0)
            current_quality = profile.best_body_image.get('quality', 0.0) if profile.best_body_image else 0.0
            current_confidence = profile.best_body_image.get('confidence', 0.0) if profile.best_body_image else 0.0
            
            # Update if quality is better, or if quality is same but confidence is better
            if quality > current_quality or (quality == current_quality and confidence > current_confidence):
                profile.best_body_image = body_image_data.copy()
                # Add timestamp
                profile.best_body_image['updated_at'] = datetime.now().isoformat()
                
                # Update quality history
                if profile.body_image_quality_history is None:
                    profile.body_image_quality_history = []
                profile.body_image_quality_history.append({
                    'quality': quality,
                    'confidence': confidence,
                    'frame_num': body_image_data.get('frame_num'),
                    'timestamp': datetime.now().isoformat()
                })
                # Keep only last 50 entries
                if len(profile.body_image_quality_history) > 50:
                    profile.body_image_quality_history = profile.body_image_quality_history[-50:]
        
        # Update jersey image if provided and better quality
        if jersey_image_data is not None:
            quality = jersey_image_data.get('quality', 0.0)
            confidence = jersey_image_data.get('confidence', 0.0)
            current_quality = profile.best_jersey_image.get('quality', 0.0) if profile.best_jersey_image else 0.0
            current_confidence = profile.best_jersey_image.get('confidence', 0.0) if profile.best_jersey_image else 0.0
            
            if quality > current_quality or (quality == current_quality and confidence > current_confidence):
                profile.best_jersey_image = jersey_image_data.copy()
                profile.best_jersey_image['updated_at'] = datetime.now().isoformat()
                
                # Update quality history
                if profile.jersey_image_quality_history is None:
                    profile.jersey_image_quality_history = []
                profile.jersey_image_quality_history.append({
                    'quality': quality,
                    'confidence': confidence,
                    'frame_num': jersey_image_data.get('frame_num'),
                    'timestamp': datetime.now().isoformat()
                })
                if len(profile.jersey_image_quality_history) > 50:
                    profile.jersey_image_quality_history = profile.jersey_image_quality_history[-50:]
        
        # Update foot image if provided and better quality
        if foot_image_data is not None:
            quality = foot_image_data.get('quality', 0.0)
            confidence = foot_image_data.get('confidence', 0.0)
            current_quality = profile.best_foot_image.get('quality', 0.0) if profile.best_foot_image else 0.0
            current_confidence = profile.best_foot_image.get('confidence', 0.0) if profile.best_foot_image else 0.0
            
            if quality > current_quality or (quality == current_quality and confidence > current_confidence):
                profile.best_foot_image = foot_image_data.copy()
                profile.best_foot_image['updated_at'] = datetime.now().isoformat()
                
                # Update quality history
                if profile.foot_image_quality_history is None:
                    profile.foot_image_quality_history = []
                profile.foot_image_quality_history.append({
                    'quality': quality,
                    'confidence': confidence,
                    'frame_num': foot_image_data.get('frame_num'),
                    'timestamp': datetime.now().isoformat()
                })
                if len(profile.foot_image_quality_history) > 50:
                    profile.foot_image_quality_history = profile.foot_image_quality_history[-50:]
        
        # Update separate features
        if body_features is not None:
            if isinstance(body_features, np.ndarray):
                profile.body_features = body_features.tolist()
            else:
                profile.body_features = body_features
        
        if jersey_features is not None:
            if isinstance(jersey_features, np.ndarray):
                profile.jersey_features = jersey_features.tolist()
            else:
                profile.jersey_features = jersey_features
        
        profile.updated_at = datetime.now().isoformat()
    
    def _calculate_feature_quality_score(self, reference_frame: Optional[Dict] = None) -> float:
        """
        Calculate quality score for a feature based on reference frame metadata.
        Used for quality-weighted feature aggregation.
        
        🎓 ANCHOR FRAMES: Anchor frames (confidence 1.00, similarity 1.00) are ABSOLUTE TRUTH
        They are manually tagged, so we KNOW WHO THE PLAYER IS with absolute certainty.
        These should receive maximum quality score (1.0) for learning.
        
        Args:
            reference_frame: Reference frame dict with similarity, confidence, quality, etc.
        
        Returns:
            Quality score (0.0-1.0, higher is better)
        """
        if reference_frame is None:
            return 0.5  # Default quality if no reference frame
        
        # 🎓 ANCHOR FRAMES: Check if this is an anchor frame (ABSOLUTE TRUTH)
        ref_confidence = reference_frame.get('confidence', 0.0)
        ref_similarity = reference_frame.get('similarity', 0.0)
        is_anchor = reference_frame.get('is_anchor', False)
        
        # Anchor frames are ground truth - they should have maximum quality
        if (ref_confidence >= 1.00 and ref_similarity >= 1.00) or is_anchor:
            return 1.0  # Maximum quality for anchor frames (ABSOLUTE TRUTH)
        
        # Normal quality calculation for non-anchor frames
        score = 0.0
        weights = {
            'similarity': 0.4,  # 40% weight on Re-ID similarity
            'confidence': 0.3,   # 30% weight on detection confidence
            'quality': 0.2,      # 20% weight on image quality (if available)
            'recency': 0.1       # 10% weight on recency (newer = slightly better)
        }
        
        # Similarity score (0-1)
        similarity = reference_frame.get('similarity', 0.5)
        score += similarity * weights['similarity']
        
        # Confidence score (0-1)
        confidence = reference_frame.get('confidence', 0.5)
        score += confidence * weights['confidence']
        
        # Image quality (if available)
        quality = reference_frame.get('quality', 0.5)
        score += quality * weights['quality']
        
        # Recency boost (small boost for newer frames)
        # Assume frames are added in order, so newer frames get small boost
        score += 0.5 * weights['recency']  # Default recency score
        
        return min(1.0, max(0.0, score))  # Clamp to 0-1
    
    def calculate_image_quality_score(self, image: np.ndarray, bbox: List[float], 
                                     similarity: float = 0.0, confidence: float = 0.0) -> float:
        """
        Calculate quality score for an image based on multiple factors
        
        Args:
            image: Image array (numpy array)
            bbox: Bounding box [x1, y1, x2, y2]
            similarity: Re-ID similarity score (0-1)
            confidence: Detection confidence (0-1)
        
        Returns:
            Quality score (0-1, higher is better)
        """
        if image is None or len(image.shape) < 2:
            return 0.0
        
        score = 0.0
        weights = {
            'similarity': 0.4,  # 40% weight on Re-ID similarity
            'confidence': 0.3,   # 30% weight on detection confidence
            'size': 0.15,        # 15% weight on image size
            'sharpness': 0.1,    # 10% weight on image sharpness
            'aspect_ratio': 0.05 # 5% weight on aspect ratio
        }
        
        # Similarity score (0-1)
        score += similarity * weights['similarity']
        
        # Confidence score (0-1)
        score += confidence * weights['confidence']
        
        # Size score: larger images are better (normalized to 0-1)
        h, w = image.shape[:2]
        size_score = min(1.0, (h * w) / (300 * 200))  # Normalize to 300x200 as "good" size
        score += size_score * weights['size']
        
        # Sharpness score: calculate using Laplacian variance
        try:
            import cv2
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(1.0, laplacian_var / 500.0)  # Normalize to 500 as "good" sharpness
            score += sharpness_score * weights['sharpness']
        except:
            # If sharpness calculation fails, use default
            score += 0.5 * weights['sharpness']
        
        # Aspect ratio score: prefer taller images (players are taller than wide)
        if w > 0:
            aspect_ratio = h / w
            # Ideal aspect ratio is around 2.0-3.0 for standing players
            if 1.5 <= aspect_ratio <= 3.5:
                aspect_score = 1.0
            elif aspect_ratio < 1.5:
                aspect_score = aspect_ratio / 1.5  # Penalize wider images
            else:
                aspect_score = max(0.0, 1.0 - (aspect_ratio - 3.5) / 2.0)  # Penalize very tall images
            score += aspect_score * weights['aspect_ratio']
        else:
            score += 0.5 * weights['aspect_ratio']
        
        return min(1.0, max(0.0, score))  # Clamp to 0-1
    
    def extract_jersey_region(self, frame: np.ndarray, bbox: List[float]) -> Optional[np.ndarray]:
        """
        Extract jersey region from a player bounding box
        Jersey region is typically the upper 30-60% of the bounding box (torso area)
        
        Args:
            frame: Full frame image
            bbox: Bounding box [x1, y1, x2, y2]
        
        Returns:
            Cropped jersey region image or None
        """
        try:
            import cv2
            
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            h, w = frame.shape[:2]
            
            # Ensure coordinates are within frame bounds
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            
            if x2 <= x1 or y2 <= y1:
                return None
            
            # Extract full bbox
            full_bbox = frame[y1:y2, x1:x2]
            bbox_height = y2 - y1
            
            # Jersey region: upper 30-60% of bbox (torso area)
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
    
    def _extract_images_from_reference(self, video_path: str, frame_num: int, bbox: List[float]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Extract body, jersey, and foot images from a video reference frame
        
        Args:
            video_path: Path to video file
            frame_num: Frame number
            bbox: Bounding box [x1, y1, x2, y2]
        
        Returns:
            Tuple of (body_image, jersey_image, foot_image) or (None, None, None) if extraction fails
        """
        try:
            import cv2
            
            if not os.path.exists(video_path):
                return None, None, None
            
            # Open video and seek to frame
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None, None, None
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_num))
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                return None, None, None
            
            # Extract body image (full bbox)
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            h, w = frame.shape[:2]
            
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            
            if x2 <= x1 or y2 <= y1:
                return None, None, None
            
            body_image = frame[y1:y2, x1:x2].copy()
            
            # Extract jersey region (upper 30-60% of bbox)
            bbox_height = y2 - y1
            jersey_top = int(bbox_height * 0.30)
            jersey_bottom = int(bbox_height * 0.60)
            if jersey_bottom > jersey_top:
                jersey_image = body_image[jersey_top:jersey_bottom, :].copy()
            else:
                jersey_image = None
            
            # Extract foot region (bottom 10-30% of bbox, i.e., 70-90% from top)
            # This captures the feet/shoes area, not shorts (which are at 60-80%)
            foot_top = int(bbox_height * 0.70)
            foot_bottom = int(bbox_height * 0.90)
            if foot_bottom > foot_top:
                foot_image = body_image[foot_top:foot_bottom, :].copy()
            else:
                foot_image = None
            
            return body_image, jersey_image, foot_image
            
        except Exception as e:
            print(f"⚠ Error extracting images from reference: {e}")
            return None, None, None
    
    def learn_shape_features(self, player_id: str, bbox: List[float]):
        """
        Learn shape features from bounding box
        
        Args:
            player_id: Player identifier
            bbox: Bounding box [x1, y1, x2, y2]
        """
        if player_id not in self.players:
            return
        
        profile = self.players[player_id]
        x1, y1, x2, y2 = bbox
        height = y2 - y1
        width = x2 - x1
        ratio = height / (width + 1e-8)  # Avoid division by zero
        
        # Update running averages
        if profile.shape_samples == 0:
            profile.avg_height = height
            profile.avg_width = width
            profile.height_width_ratio = ratio
        else:
            # Exponential moving average (more weight to recent samples)
            alpha = 0.1  # Learning rate
            if profile.avg_height is not None:
                profile.avg_height = (1 - alpha) * profile.avg_height + alpha * height
            if profile.avg_width is not None:
                profile.avg_width = (1 - alpha) * profile.avg_width + alpha * width
            if profile.height_width_ratio is not None:
                profile.height_width_ratio = (1 - alpha) * profile.height_width_ratio + alpha * ratio
        
        profile.shape_samples += 1
    
    def learn_movement_features(self, player_id: str, velocity: float, acceleration: Optional[float] = None):
        """
        Learn movement features from velocity and acceleration
        
        Args:
            player_id: Player identifier
            velocity: Current velocity (pixels/frame)
            acceleration: Current acceleration (pixels/frame²), optional
        """
        if player_id not in self.players:
            return
        
        profile = self.players[player_id]
        
        # Initialize velocity history if needed
        if profile.velocity_history is None:
            profile.velocity_history = []
        
        # Update running averages
        if profile.movement_samples == 0:
            profile.avg_speed = abs(velocity)
            profile.max_speed = abs(velocity)
            if acceleration is not None:
                profile.avg_acceleration = abs(acceleration)
        else:
            # Exponential moving average
            alpha = 0.1
            if profile.avg_speed is not None:
                profile.avg_speed = (1 - alpha) * profile.avg_speed + alpha * abs(velocity)
            if profile.max_speed is not None:
                profile.max_speed = max(profile.max_speed, abs(velocity))
            else:
                profile.max_speed = abs(velocity)
            if acceleration is not None and profile.avg_acceleration is not None:
                profile.avg_acceleration = (1 - alpha) * profile.avg_acceleration + alpha * abs(acceleration)
        
        # Store recent velocity samples (keep last 30)
        profile.velocity_history.append(velocity)
        if len(profile.velocity_history) > 30:
            _ = profile.velocity_history.pop(0)  # Remove oldest, discard value
        
        profile.movement_samples += 1
        
        # Update movement style based on average speed
        if profile.avg_speed is not None:
            if profile.avg_speed < 2.0:
                profile.movement_style = "stationary"
            elif profile.avg_speed < 5.0:
                profile.movement_style = "moderate"
            elif profile.avg_speed < 10.0:
                profile.movement_style = "active"
            else:
                profile.movement_style = "very_active"
    
    def learn_position_preferences(self, player_id: str, x: float, y: float, field_width: float, field_height: float):
        """
        Learn position preferences on the field
        
        Args:
            player_id: Player identifier
            x: X position in pixels
            y: Y position in pixels
            field_width: Field width in pixels
            field_height: Field height in pixels
        """
        if player_id not in self.players:
            return
        
        profile = self.players[player_id]
        
        # Normalize position to 0-1 range
        norm_x = x / (field_width + 1e-8)
        norm_y = y / (field_height + 1e-8)
        
        # Clamp to [0, 1]
        norm_x = max(0.0, min(1.0, norm_x))
        norm_y = max(0.0, min(1.0, norm_y))
        
        # Update running averages
        if profile.position_samples == 0:
            profile.preferred_x = norm_x
            profile.preferred_y = norm_y
            # Initialize position heatmap (10x10 grid)
            profile.position_heatmap = [[0.0] * 10 for _ in range(10)]
        else:
            # Exponential moving average
            alpha = 0.05  # Slower learning for position (more stable)
            if profile.preferred_x is not None:
                profile.preferred_x = (1 - alpha) * profile.preferred_x + alpha * norm_x
            if profile.preferred_y is not None:
                profile.preferred_y = (1 - alpha) * profile.preferred_y + alpha * norm_y
        
        # Update position heatmap
        grid_x = int(norm_x * 9)  # 0-9
        grid_y = int(norm_y * 9)  # 0-9
        grid_x = max(0, min(9, grid_x))
        grid_y = max(0, min(9, grid_y))
        
        # Increment heatmap cell (with decay to prevent overflow)
        if profile.position_heatmap is not None:
            profile.position_heatmap[grid_y][grid_x] += 1.0
            # Normalize heatmap periodically (every 100 samples)
            if profile.position_samples % 100 == 0 and profile.position_samples > 0:
                max_val = max(max(row) for row in profile.position_heatmap)
                if max_val > 0:
                    profile.position_heatmap = [[val / max_val for val in row] for row in profile.position_heatmap]
        
        profile.position_samples += 1
    
    def learn_ball_interaction(self, player_id: str, distance_to_ball: float, interaction_threshold: float = 50.0):
        """
        Learn ball interaction patterns
        
        Args:
            player_id: Player identifier
            distance_to_ball: Distance to ball in pixels
            interaction_threshold: Distance considered as "interaction" (pixels)
        """
        if player_id not in self.players:
            return
        
        profile = self.players[player_id]
        
        # Check if player is interacting with ball
        is_interacting = distance_to_ball <= interaction_threshold
        
        # Update interaction rate
        if profile.ball_interaction_samples == 0:
            profile.ball_interaction_rate = 1.0 if is_interacting else 0.0
        else:
            # Exponential moving average
            alpha = 0.05
            current_rate = 1.0 if is_interacting else 0.0
            if profile.ball_interaction_rate is not None:
                profile.ball_interaction_rate = (1 - alpha) * profile.ball_interaction_rate + alpha * current_rate
        
        profile.ball_interaction_samples += 1
    
    def update_track_history(self, player_id: str, track_id: int):
        """
        Update track history for a player (gallery-based breadcrumb)
        
        Args:
            player_id: Player identifier
            track_id: Track ID this player was assigned to
        """
        if player_id not in self.players:
            return
        
        profile = self.players[player_id]
        if profile.track_history is None:
            profile.track_history = {}
        
        # CRITICAL: Handle legacy format where track_history might contain lists instead of counts
        # Convert any list values to counts (length of list)
        for tid, value in list(profile.track_history.items()):
            if isinstance(value, list):
                # Legacy format: convert list to count
                profile.track_history[tid] = len(value)
            elif not isinstance(value, (int, float)):
                # Invalid format: reset to 0
                profile.track_history[tid] = 0
        
        # Increment count for this track
        current_count = profile.track_history.get(track_id, 0)
        # Ensure current_count is an integer
        if not isinstance(current_count, (int, float)):
            current_count = 0
        profile.track_history[track_id] = int(current_count) + 1
        
        # Limit history size (keep top 10 most frequent tracks)
        if len(profile.track_history) > 10:
            # Keep only the most frequently seen tracks
            # CRITICAL: Ensure all values are integers before sorting
            cleaned_history = {tid: int(count) if isinstance(count, (int, float)) else 0 
                             for tid, count in profile.track_history.items()}
            sorted_tracks = sorted(cleaned_history.items(), key=lambda x: x[1], reverse=True)
            profile.track_history = dict(sorted_tracks[:10])
    
    def get_track_history_boost(self, player_id: str, track_id: int) -> float:
        """
        Get similarity boost if this player has been on this track before (gallery breadcrumb)
        
        Args:
            player_id: Player identifier
            track_id: Track ID to check
        
        Returns:
            Boost value (0.0 to 0.15) based on how often this player was on this track
        """
        if player_id not in self.players:
            return 0.0
        
        profile = self.players[player_id]
        if profile.track_history is None or track_id not in profile.track_history:
            return 0.0
        
        # Get occurrence count for this track
        # CRITICAL: Handle legacy format where track_history might contain lists
        count_value = profile.track_history[track_id]
        if isinstance(count_value, list):
            # Legacy format: use list length as count
            count = len(count_value)
        elif isinstance(count_value, (int, float)):
            count = int(count_value)
        else:
            # Invalid format: return 0 boost
            return 0.0
        
        # Calculate boost based on frequency
        # 1-2 occurrences: 0.05 boost
        # 3-5 occurrences: 0.10 boost
        # 6+ occurrences: 0.15 boost
        if count >= 6:
            return 0.15
        elif count >= 3:
            return 0.10
        elif count >= 1:
            return 0.05
        else:
            return 0.0
    
    def _calculate_feature_diversity(self, profile: PlayerProfile) -> float:
        """
        Calculate feature diversity score for a player.
        Higher diversity = features cover different angles, poses, lighting conditions.
        
        Args:
            profile: PlayerProfile to analyze
        
        Returns:
            Diversity score (0.0-1.0, higher = more diverse)
        """
        if not profile.reference_frames or len(profile.reference_frames) < 2:
            return 0.5  # Default diversity for single or no frames
        
        # Extract features from reference frames (if available)
        # For now, use a simplified diversity metric based on reference frame characteristics
        # In a full implementation, we'd cluster actual feature vectors
        
        # Diversity factors:
        # 1. Number of different videos (more videos = more diverse)
        # 2. Frame number spread (wider spread = more diverse)
        # 3. Uniform variants (different uniforms = more diverse)
        # 4. Quality variance (varying quality = more diverse conditions)
        
        unique_videos = set()
        frame_numbers = []
        quality_scores = []
        
        for ref_frame in profile.reference_frames:
            video_path = ref_frame.get('video_path')
            if video_path:
                unique_videos.add(video_path)
            
            frame_num = ref_frame.get('frame_num')
            if frame_num is not None:
                frame_numbers.append(frame_num)
            
            quality = ref_frame.get('quality', ref_frame.get('similarity', 0.5))
            quality_scores.append(quality)
        
        # Calculate diversity components
        video_diversity = min(1.0, len(unique_videos) / 5.0)  # Normalize to 5 videos = max
        
        if len(frame_numbers) > 1:
            frame_spread = (max(frame_numbers) - min(frame_numbers)) / max(frame_numbers, 1)
            frame_spread = min(1.0, frame_spread)  # Normalize
        else:
            frame_spread = 0.0
        
        uniform_diversity = 0.0
        if profile.uniform_variants:
            uniform_diversity = min(1.0, len(profile.uniform_variants) / 3.0)  # Normalize to 3 variants = max
        
        quality_variance = 0.0
        if len(quality_scores) > 1:
            quality_variance = np.std(quality_scores) if quality_scores else 0.0
            quality_variance = min(1.0, quality_variance * 2.0)  # Normalize
        
        # Weighted combination
        diversity = (
            0.3 * video_diversity +
            0.2 * frame_spread +
            0.3 * uniform_diversity +
            0.2 * quality_variance
        )
        
        return min(1.0, max(0.0, diversity))
    
    def _prune_reference_frames_by_quality_and_diversity(self, profile: PlayerProfile, max_frames: int):
        """
        ENHANCED: Prune reference frames to keep highest quality AND most diverse ones.
        This ensures the gallery has good coverage of different conditions.
        
        CRITICAL: Anchor frames (is_anchor=True) are NEVER pruned - they are ground truth.
        
        Args:
            profile: PlayerProfile to prune
            max_frames: Maximum number of frames to keep (excluding anchor frames)
        """
        if not profile.reference_frames or len(profile.reference_frames) <= max_frames:
            return
        
        # CRITICAL: Separate anchor frames from regular frames
        # Anchor frames are ground truth and must NEVER be pruned
        anchor_frames = []
        regular_frames = []
        for ref_frame in profile.reference_frames:
            is_anchor = ref_frame.get('is_anchor', False) or (ref_frame.get('confidence', 0.0) >= 1.00 and ref_frame.get('similarity', 0.0) >= 1.00)
            if is_anchor:
                anchor_frames.append(ref_frame)
            else:
                regular_frames.append(ref_frame)
        
        # If we only have anchor frames or regular frames are within limit, no pruning needed
        if len(regular_frames) <= max_frames:
            # Keep all anchor frames + all regular frames
            profile.reference_frames = anchor_frames + regular_frames
            return
        
        # Calculate feature diversity for this player
        diversity_score = self._calculate_feature_diversity(profile)
        profile.feature_diversity_score = diversity_score
        
        # Score each REGULAR reference frame by quality AND diversity contribution
        # (Anchor frames are already protected and will be kept)
        scored_frames = []
        for i, ref_frame in enumerate(regular_frames):
            score = 0.0
            
            # Quality factors (70% weight)
            if 'similarity' in ref_frame:
                score += ref_frame['similarity'] * 70.0  # Weight: 70x
            
            if 'confidence' in ref_frame:
                score += ref_frame['confidence'] * 35.0  # Weight: 35x
            
            if 'quality' in ref_frame:
                score += ref_frame['quality'] * 20.0  # Weight: 20x
            
            # Diversity factors (30% weight)
            # Prefer frames from different videos
            video_path = ref_frame.get('video_path')
            if video_path:
                # Check how many other REGULAR frames are from same video (exclude anchor frames from count)
                same_video_count = sum(1 for rf in regular_frames 
                                     if rf.get('video_path') == video_path)
                if same_video_count > 1:
                    # Penalize if many frames from same video (redundant)
                    score -= (same_video_count - 1) * 2.0
                else:
                    # Bonus for unique video
                    score += 10.0
            
            # Prefer frames with different uniform variants
            uniform_info = ref_frame.get('uniform_info')
            if uniform_info and profile.uniform_variants:
                jersey = uniform_info.get('jersey_color', 'unknown').lower()
                shorts = uniform_info.get('shorts_color', 'unknown').lower()
                socks = uniform_info.get('socks_color', 'unknown').lower()
                uniform_key = f"{jersey}-{shorts}-{socks}"
                
                # Count how many REGULAR frames have this uniform (exclude anchor frames from count)
                same_uniform_count = sum(1 for rf in regular_frames
                                       if rf.get('uniform_info', {}).get('jersey_color', '').lower() == jersey)
                if same_uniform_count > 3:
                    # Penalize if too many frames with same uniform
                    score -= (same_uniform_count - 3) * 1.0
                else:
                    # Bonus for diverse uniforms
                    score += 5.0
            
            # Frame number spread (prefer frames spread across video)
            frame_num = ref_frame.get('frame_num')
            if frame_num is not None and len(regular_frames) > 1:
                other_frames = [rf.get('frame_num') for rf in regular_frames 
                              if rf.get('frame_num') is not None and rf != ref_frame]
                if other_frames:
                    avg_distance = np.mean([abs(frame_num - of) for of in other_frames])
                    # Bonus for frames that are far from others (more diverse)
                    score += min(5.0, avg_distance / 1000.0)  # Normalize
            
            # Has bbox (complete reference frame)
            if 'bbox' in ref_frame and ref_frame['bbox']:
                score += 5.0
            
            scored_frames.append((score, ref_frame, i))
        
        # Sort by score (highest first)
        scored_frames.sort(key=lambda x: x[0], reverse=True)
        
        # Keep top max_frames REGULAR frames, but ensure diversity:
        # - Keep at least one frame per uniform variant (if possible)
        # - Keep at least one frame per video (if possible)
        kept_frames = []
        kept_uniforms = set()
        kept_videos = set()
        
        # First pass: Keep highest quality REGULAR frames
        for score, ref_frame, idx in scored_frames[:max_frames]:
            kept_frames.append(ref_frame)
            # Track what we've kept
            video_path = ref_frame.get('video_path')
            if video_path:
                kept_videos.add(video_path)
            
            uniform_info = ref_frame.get('uniform_info')
            if uniform_info:
                jersey = uniform_info.get('jersey_color', 'unknown').lower()
                kept_uniforms.add(jersey)
        
        # Second pass: If we have room, add diverse REGULAR frames we missed
        if len(kept_frames) < max_frames:
            for score, ref_frame, idx in scored_frames[max_frames:]:
                if len(kept_frames) >= max_frames:
                    break
                
                # Check if this frame adds diversity
                adds_diversity = False
                video_path = ref_frame.get('video_path')
                if video_path and video_path not in kept_videos:
                    adds_diversity = True
                
                uniform_info = ref_frame.get('uniform_info')
                if uniform_info:
                    jersey = uniform_info.get('jersey_color', 'unknown').lower()
                    if jersey not in kept_uniforms:
                        adds_diversity = True
                
                if adds_diversity:
                    kept_frames.append(ref_frame)
                    if video_path:
                        kept_videos.add(video_path)
                    if uniform_info:
                        jersey = uniform_info.get('jersey_color', 'unknown').lower()
                        kept_uniforms.add(jersey)
        
        # CRITICAL: Always keep ALL anchor frames + pruned regular frames
        # Anchor frames are ground truth and must never be removed
        profile.reference_frames = anchor_frames + kept_frames[:max_frames]
        
        # Log if we're keeping anchor frames
        if anchor_frames and len(anchor_frames) > 0:
            if len(profile.reference_frames) > max_frames:
                print(f"   ℹ Kept {len(anchor_frames)} anchor frame(s) (ground truth) + {len(kept_frames[:max_frames])} regular frame(s) = {len(profile.reference_frames)} total")
    
    def _prune_reference_frames_by_quality(self, profile, max_frames: int):
        """
        Prune reference frames to keep only the highest quality ones.
        Quality is determined by: similarity score > confidence > recency
        
        Args:
            profile: PlayerProfile to prune
            max_frames: Maximum number of frames to keep
        """
        # Use enhanced pruning that considers diversity
        self._prune_reference_frames_by_quality_and_diversity(profile, max_frames)
    
    def cleanup_reference_frames(self, max_frames_per_player: int = 1000, quality_based: bool = True):
        """
        Clean up excessive reference frames for all players.
        Keeps the highest quality reference frames (or most recent if quality_based=False).
        
        Args:
            max_frames_per_player: Maximum reference frames to keep per player
            quality_based: If True, keep highest quality frames. If False, keep most recent.
        """
        total_removed = 0
        for _player_id, profile in self.players.items():
            if profile.reference_frames and len(profile.reference_frames) > max_frames_per_player:
                removed = len(profile.reference_frames) - max_frames_per_player
                if quality_based:
                    # Keep highest quality frames
                    self._prune_reference_frames_by_quality(profile, max_frames_per_player)
                else:
                    # Keep most recent frames
                    profile.reference_frames = profile.reference_frames[-max_frames_per_player:]
                total_removed += removed
                print(f"   • {profile.name}: Removed {removed} reference frames (kept {max_frames_per_player} {'highest quality' if quality_based else 'most recent'})")
        
        if total_removed > 0:
            print(f"✓ Cleaned up {total_removed} reference frames total")
            self.save_gallery()
        else:
            print(f"✓ No cleanup needed - all players have ≤{max_frames_per_player} reference frames")
    
    def remove_false_matches(self, min_similarity_threshold: float = 0.3, min_confidence_threshold: float = 0.4):
        """
        ENHANCED: Remove false matched images and reference frames based on low similarity/confidence.
        
        This method identifies and removes reference frames that are likely false matches:
        - Low similarity scores (< min_similarity_threshold)
        - Low confidence scores (< min_confidence_threshold)
        - Poor quality images
        
        Args:
            min_similarity_threshold: Minimum similarity score to keep (default: 0.3)
            min_confidence_threshold: Minimum confidence score to keep (default: 0.4)
        """
        total_removed = 0
        players_cleaned = 0
        
        for player_id, profile in self.players.items():
            removed_count = 0
            
            # Remove low-quality reference frames
            if profile.reference_frames:
                original_count = len(profile.reference_frames)
                profile.reference_frames = [
                    ref for ref in profile.reference_frames
                    if ref.get('similarity', 0.5) >= min_similarity_threshold
                    and ref.get('confidence', 0.5) >= min_confidence_threshold
                ]
                removed_count += original_count - len(profile.reference_frames)
            
            # Remove low-quality best images
            if profile.best_body_image and profile.best_body_image.get('quality', 1.0) < 0.3:
                if profile.best_body_image.get('similarity', 0.5) < min_similarity_threshold:
                    profile.best_body_image = None
                    removed_count += 1
            
            if profile.best_jersey_image and profile.best_jersey_image.get('quality', 1.0) < 0.3:
                if profile.best_jersey_image.get('similarity', 0.5) < min_similarity_threshold:
                    profile.best_jersey_image = None
                    removed_count += 1
            
            if profile.best_foot_image and profile.best_foot_image.get('quality', 1.0) < 0.3:
                if profile.best_foot_image.get('similarity', 0.5) < min_similarity_threshold:
                    profile.best_foot_image = None
                    removed_count += 1
            
            # Remove low-quality alternative features (if attribute exists)
            if hasattr(profile, 'alternative_features') and profile.alternative_features:
                original_count = len(profile.alternative_features)
                profile.alternative_features = [
                    alt for alt in profile.alternative_features
                    if alt.get('quality', 0.5) >= 0.3
                    and alt.get('confidence', 0.5) >= min_confidence_threshold
                ]
                removed_count += original_count - len(profile.alternative_features)
            
            if removed_count > 0:
                players_cleaned += 1
                total_removed += removed_count
                print(f"   • {profile.name}: Removed {removed_count} false/low-quality matches")
        
        if total_removed > 0:
            print(f"✓ Removed {total_removed} false matches from {players_cleaned} players")
            self.save_gallery()
        else:
            print(f"✓ No false matches found - all reference frames meet quality thresholds")
    
    def remove_missing_reference_frames(self, verify_video_files: bool = True):
        """
        Remove reference frames that point to missing video files or invalid frames.
        
        This is important for data integrity - if a video file has been deleted or moved,
        the reference frames pointing to it are invalid and should be removed.
        
        Args:
            verify_video_files: If True, check if video files actually exist on disk
        """
        total_removed = 0
        players_cleaned = 0
        
        for player_id, profile in self.players.items():
            removed_count = 0
            
            # Check main reference_frames
            if profile.reference_frames:
                original_count = len(profile.reference_frames)
                valid_frames = []
                
                for ref_frame in profile.reference_frames:
                    video_path = ref_frame.get('video_path')
                    frame_num = ref_frame.get('frame_num')
                    
                    # Check if reference frame is valid
                    is_valid = True
                    
                    # Check if video_path is missing or invalid
                    if not video_path or not isinstance(video_path, str):
                        is_valid = False
                    elif verify_video_files and not os.path.exists(video_path):
                        is_valid = False
                    
                    # Check if frame_num is valid
                    if frame_num is None or not isinstance(frame_num, (int, float)):
                        is_valid = False
                    
                    # If valid, keep it; otherwise remove it
                    if is_valid:
                        valid_frames.append(ref_frame)
                    else:
                        removed_count += 1
                        if video_path:
                            print(f"   • {profile.name}: Removing reference frame (missing video: {os.path.basename(video_path)})")
                        else:
                            print(f"   • {profile.name}: Removing reference frame (invalid video_path)")
                
                profile.reference_frames = valid_frames
                if removed_count > 0:
                    print(f"   → {profile.name}: Removed {removed_count} missing reference frames (kept {len(valid_frames)})")
            
            # Check uniform_variants reference frames
            if profile.uniform_variants:
                for uniform_key, variant_frames in profile.uniform_variants.items():
                    if variant_frames:
                        original_count = len(variant_frames)
                        valid_frames = []
                        
                        for ref_frame in variant_frames:
                            video_path = ref_frame.get('video_path')
                            frame_num = ref_frame.get('frame_num')
                            
                            is_valid = True
                            if not video_path or not isinstance(video_path, str):
                                is_valid = False
                            elif verify_video_files and not os.path.exists(video_path):
                                is_valid = False
                            if frame_num is None or not isinstance(frame_num, (int, float)):
                                is_valid = False
                            
                            if is_valid:
                                valid_frames.append(ref_frame)
                            else:
                                removed_count += 1
                        
                        profile.uniform_variants[uniform_key] = valid_frames
                        if len(valid_frames) < original_count:
                            print(f"   → {profile.name} ({uniform_key}): Removed {original_count - len(valid_frames)} missing frames")
            
            # Check foot_reference_frames
            if profile.foot_reference_frames:
                original_count = len(profile.foot_reference_frames)
                valid_frames = []
                
                for ref_frame in profile.foot_reference_frames:
                    video_path = ref_frame.get('video_path')
                    frame_num = ref_frame.get('frame_num')
                    
                    is_valid = True
                    if not video_path or not isinstance(video_path, str):
                        is_valid = False
                    elif verify_video_files and not os.path.exists(video_path):
                        is_valid = False
                    if frame_num is None or not isinstance(frame_num, (int, float)):
                        is_valid = False
                    
                    if is_valid:
                        valid_frames.append(ref_frame)
                    else:
                        removed_count += 1
                
                profile.foot_reference_frames = valid_frames
                if len(valid_frames) < original_count:
                    print(f"   → {profile.name}: Removed {original_count - len(valid_frames)} missing foot reference frames")
            
            # Check best images (body, jersey, foot)
            for image_type in ['best_body_image', 'best_jersey_image', 'best_foot_image']:
                best_image = getattr(profile, image_type, None)
                if best_image and isinstance(best_image, dict):
                    video_path = best_image.get('video_path')
                    if video_path:
                        if not isinstance(video_path, str) or (verify_video_files and not os.path.exists(video_path)):
                            # Clear the best image if video is missing
                            setattr(profile, image_type, None)
                            removed_count += 1
                            print(f"   → {profile.name}: Removed missing {image_type} (video: {os.path.basename(video_path) if video_path else 'invalid'})")
            
            if removed_count > 0:
                players_cleaned += 1
                total_removed += removed_count
        
        if total_removed > 0:
            print(f"✓ Removed {total_removed} missing reference frames from {players_cleaned} players")
            self.save_gallery()
            return total_removed, players_cleaned
        else:
            print(f"✓ No missing reference frames found - all reference frames are valid")
            return 0, 0
    
    def remove_reference_frames_for_players_from_video(self, video_path: str, player_names: list[str]) -> tuple[int, int]:
        """
        Remove reference frames for specific players from a specific video.
        
        This is useful when you know certain players were incorrectly matched in a video
        and you want to remove their gallery references from that video.
        
        Args:
            video_path: Path to the video file (will be normalized for comparison)
            player_names: List of player names to remove references for
        
        Returns:
            Tuple of (total_frames_removed, players_cleaned)
        """
        import os
        total_removed = 0
        players_cleaned = 0
        
        # Normalize video path for comparison
        video_path_normalized = os.path.normpath(os.path.abspath(video_path)) if video_path else None
        
        if not video_path_normalized:
            print("⚠ Cannot remove reference frames: video_path is empty")
            return 0, 0
        
        # Normalize player names (handle list format)
        player_names_clean = []
        for name in player_names:
            if isinstance(name, list) and len(name) > 0:
                player_names_clean.append(str(name[0]).strip())
            else:
                player_names_clean.append(str(name).strip())
        
        print(f"🧹 Removing reference frames for {len(player_names_clean)} player(s) from video: {os.path.basename(video_path)}")
        print(f"   Players: {', '.join(player_names_clean)}")
        
        for player_id, profile in self.players.items():
            # Check if this player should have references removed
            profile_name_clean = str(profile.name).strip()
            if profile_name_clean not in player_names_clean:
                continue
            
            removed_count = 0
            
            # Remove from main reference_frames
            if profile.reference_frames:
                original_count = len(profile.reference_frames)
                valid_frames = []
                
                for ref_frame in profile.reference_frames:
                    ref_video_path = ref_frame.get('video_path')
                    if ref_video_path:
                        ref_video_normalized = os.path.normpath(os.path.abspath(ref_video_path))
                        # Remove if video path matches
                        if ref_video_normalized == video_path_normalized:
                            removed_count += 1
                            continue  # Skip this frame
                    
                    valid_frames.append(ref_frame)
                
                profile.reference_frames = valid_frames
                if removed_count > 0:
                    print(f"   • {profile.name}: Removed {removed_count} reference frames from main frames")
            
            # Remove from uniform_variants
            if profile.uniform_variants:
                for uniform_key, variant_frames in profile.uniform_variants.items():
                    if variant_frames:
                        original_count = len(variant_frames)
                        valid_frames = []
                        
                        for ref_frame in variant_frames:
                            ref_video_path = ref_frame.get('video_path')
                            if ref_video_path:
                                ref_video_normalized = os.path.normpath(os.path.abspath(ref_video_path))
                                if ref_video_normalized == video_path_normalized:
                                    removed_count += 1
                                    continue
                            
                            valid_frames.append(ref_frame)
                        
                        profile.uniform_variants[uniform_key] = valid_frames
                        if len(valid_frames) < original_count:
                            removed_count += (original_count - len(valid_frames))
            
            # Remove from foot_reference_frames
            if profile.foot_reference_frames:
                original_count = len(profile.foot_reference_frames)
                valid_frames = []
                
                for ref_frame in profile.foot_reference_frames:
                    ref_video_path = ref_frame.get('video_path')
                    if ref_video_path:
                        ref_video_normalized = os.path.normpath(os.path.abspath(ref_video_path))
                        if ref_video_normalized == video_path_normalized:
                            removed_count += 1
                            continue
                    
                    valid_frames.append(ref_frame)
                
                profile.foot_reference_frames = valid_frames
                if len(valid_frames) < original_count:
                    removed_count += (original_count - len(valid_frames))
            
            # Check best images (body, jersey, foot) - clear if from this video
            for image_type in ['best_body_image', 'best_jersey_image', 'best_foot_image']:
                best_image = getattr(profile, image_type, None)
                if best_image and isinstance(best_image, dict):
                    ref_video_path = best_image.get('video_path')
                    if ref_video_path:
                        ref_video_normalized = os.path.normpath(os.path.abspath(ref_video_path))
                        if ref_video_normalized == video_path_normalized:
                            setattr(profile, image_type, None)
                            removed_count += 1
                            print(f"   • {profile.name}: Removed {image_type} from this video")
            
            if removed_count > 0:
                players_cleaned += 1
                total_removed += removed_count
                print(f"   ✓ {profile.name}: Removed {removed_count} total reference frames/images")
        
        if total_removed > 0:
            print(f"✓ Removed {total_removed} reference frames/images from {players_cleaned} player(s)")
            self.save_gallery()
            return total_removed, players_cleaned
        else:
            print(f"✓ No reference frames found for specified players in this video")
            return 0, 0
    
    def remove_players_without_reference_frames(self, min_references: int = 1) -> tuple[int, list[str]]:
        """
        Remove players who have no reference frames (or fewer than min_references).
        Useful for cleaning up players who weren't actually on the field.
        
        Args:
            min_references: Minimum number of reference frames required (default: 1)
        
        Returns:
            Tuple of (removed_count, removed_player_names)
        """
        removed_count = 0
        removed_names = []
        players_to_remove = []
        
        for player_id, profile in list(self.players.items()):
            # Count total reference frames (including uniform variants)
            total_refs = 0
            if profile.reference_frames:
                total_refs += len(profile.reference_frames)
            if profile.uniform_variants:
                for variant_refs in profile.uniform_variants.values():
                    if variant_refs:
                        total_refs += len(variant_refs)
            
            # Also check foot reference frames
            if profile.foot_reference_frames:
                total_refs += len(profile.foot_reference_frames)
            
            # Check if player has fewer than minimum references
            if total_refs < min_references:
                players_to_remove.append((player_id, profile.name, total_refs))
        
        # Remove players (after iteration to avoid modifying dict during iteration)
        for player_id, name, ref_count in players_to_remove:
            del self.players[player_id]
            removed_count += 1
            removed_names.append(name)
            print(f"   • Removed '{name}' (ID: {player_id}) - {ref_count} reference frame(s)")
        
        if removed_count > 0:
            print(f"✓ Removed {removed_count} player(s) with fewer than {min_references} reference frame(s)")
            self.save_gallery()
        else:
            print(f"✓ All players have at least {min_references} reference frame(s)")
        
        return removed_count, removed_names
    
    def merge_duplicate_players(self, source_player_id: str, target_player_id: str) -> bool:
        """
        Merge two players, consolidating all data from source into target.
        Useful for fixing duplicate entries (e.g., "Cameron Melnick" and "Cameron Melnik").
        
        Args:
            source_player_id: Player ID to merge FROM (will be deleted)
            target_player_id: Player ID to merge INTO (will be kept)
        
        Returns:
            True if merge was successful, False otherwise
        """
        if source_player_id not in self.players:
            print(f"⚠ Source player ID '{source_player_id}' not found")
            return False
        
        if target_player_id not in self.players:
            print(f"⚠ Target player ID '{target_player_id}' not found")
            return False
        
        if source_player_id == target_player_id:
            print(f"⚠ Cannot merge player with itself")
            return False
        
        source_profile = self.players[source_player_id]
        target_profile = self.players[target_player_id]
        
        print(f"🔄 Merging '{source_profile.name}' (ID: {source_player_id}) into '{target_profile.name}' (ID: {target_player_id})")
        
        # Merge reference frames
        if source_profile.reference_frames:
            if target_profile.reference_frames is None:
                target_profile.reference_frames = []
            # Add source reference frames (deduplication will happen automatically on next update)
            target_profile.reference_frames.extend(source_profile.reference_frames)
            print(f"   → Merged {len(source_profile.reference_frames)} reference frame(s)")
        
        # Merge uniform variants
        if source_profile.uniform_variants:
            if target_profile.uniform_variants is None:
                target_profile.uniform_variants = {}
            for uniform_key, variant_refs in source_profile.uniform_variants.items():
                if uniform_key not in target_profile.uniform_variants:
                    target_profile.uniform_variants[uniform_key] = []
                target_profile.uniform_variants[uniform_key].extend(variant_refs)
            print(f"   → Merged {len(source_profile.uniform_variants)} uniform variant(s)")
        
        # Merge foot reference frames
        if source_profile.foot_reference_frames:
            if target_profile.foot_reference_frames is None:
                target_profile.foot_reference_frames = []
            target_profile.foot_reference_frames.extend(source_profile.foot_reference_frames)
            print(f"   → Merged {len(source_profile.foot_reference_frames)} foot reference frame(s)")
        
        # Merge features (quality-weighted average)
        if source_profile.features and target_profile.features:
            source_features = np.array(source_profile.features)
            target_features = np.array(target_profile.features)
            # Weighted average (equal weight for now)
            merged_features = (source_features + target_features) / 2.0
            merged_features = merged_features / (np.linalg.norm(merged_features) + 1e-8)
            target_profile.features = merged_features.tolist()
            print(f"   → Merged Re-ID features")
        elif source_profile.features and not target_profile.features:
            target_profile.features = source_profile.features
            print(f"   → Copied Re-ID features")
        
        # Merge other features (body, jersey, foot)
        if source_profile.body_features and not target_profile.body_features:
            target_profile.body_features = source_profile.body_features
        if source_profile.jersey_features and not target_profile.jersey_features:
            target_profile.jersey_features = source_profile.jersey_features
        if source_profile.foot_features and not target_profile.foot_features:
            target_profile.foot_features = source_profile.foot_features
        
        # Merge best images (keep highest quality)
        for image_type in ['best_body_image', 'best_jersey_image', 'best_foot_image']:
            source_image = getattr(source_profile, image_type, None)
            target_image = getattr(target_profile, image_type, None)
            if source_image and not target_image:
                setattr(target_profile, image_type, source_image)
            elif source_image and target_image:
                # Keep the one with higher quality (if quality info available)
                source_quality = source_image.get('quality', 0.0) if isinstance(source_image, dict) else 0.0
                target_quality = target_image.get('quality', 0.0) if isinstance(target_image, dict) else 0.0
                if source_quality > target_quality:
                    setattr(target_profile, image_type, source_image)
        
        # Merge track history
        if source_profile.track_history:
            if target_profile.track_history is None:
                target_profile.track_history = {}
            for track_id, count in source_profile.track_history.items():
                if isinstance(count, list):
                    count = len(count)  # Handle legacy format
                current_count = target_profile.track_history.get(track_id, 0)
                if isinstance(current_count, list):
                    current_count = len(current_count)  # Handle legacy format
                target_profile.track_history[track_id] = int(current_count) + int(count)
        
        # Remove source player
        del self.players[source_player_id]
        print(f"✓ Successfully merged '{source_profile.name}' into '{target_profile.name}'")
        
        # Save gallery
        self.save_gallery()
        return True
    
    def get_best_profile_frame(self, player_id: str) -> Optional[Dict]:
        """
        Find the highest quality reference frame for a player to use as profile image.
        
        Quality is determined by:
        1. Bounding box size (larger = closer/clearer view)
        2. Aspect ratio (players are taller than wide)
        3. Similarity score (if available)
        4. Confidence score (if available)
        5. Has complete bbox data
        6. Validates bbox is reasonable (not too small, not field-only)
        
        Args:
            player_id: Player identifier
            
        Returns:
            Best reference frame dict, or None if no frames available
        """
        if player_id not in self.players:
            return None
        
        profile = self.players[player_id]
        if not profile.reference_frames or len(profile.reference_frames) == 0:
            return None
        
        # Score each reference frame by quality
        scored_frames = []
        for ref_frame in profile.reference_frames:
            score = 0.0
            has_valid_bbox = False
            
            # Priority 1: Bounding box validation and size
            if 'bbox' in ref_frame and ref_frame['bbox']:
                bbox = ref_frame['bbox']
                if len(bbox) >= 4:
                    width = abs(bbox[2] - bbox[0]) if len(bbox) > 2 else 0
                    height = abs(bbox[3] - bbox[1]) if len(bbox) > 3 else 0
                    
                    # Validation: Minimum size requirements (too small = not a good view)
                    min_size = 50  # Minimum 50x50 pixels
                    if width < min_size or height < min_size:
                        continue  # Skip frames that are too small
                    
                    # Validation: Aspect ratio (players are taller than wide, not square/wide)
                    # Typical player bbox: height/width ratio is 1.5-3.0
                    if width > 0:
                        aspect_ratio = height / width
                        if aspect_ratio < 1.0:  # Wider than tall - probably not a player
                            score -= 50.0  # Heavy penalty
                        elif aspect_ratio < 1.2:  # Too square - less likely to be a good player view
                            score -= 20.0  # Penalty
                        elif aspect_ratio > 1.2 and aspect_ratio < 3.5:  # Good player aspect ratio
                            score += 20.0  # Bonus for good aspect ratio
                    
                    area = width * height
                    # Normalize area score (assume max reasonable bbox is 500x500 = 250000)
                    # Larger bboxes get higher scores, but cap at reasonable size
                    area_score = min(area / 250000.0, 1.0) * 100.0
                    score += area_score
                    has_valid_bbox = True
            
            # Skip frames without valid bbox
            if not has_valid_bbox:
                continue
            
            # Priority 2: Similarity score (if available) - high weight
            if 'similarity' in ref_frame:
                similarity = ref_frame['similarity']
                # Only use similarity if it's reasonable (not 0 or negative)
                if similarity > 0.3:  # Minimum threshold for similarity
                    score += similarity * 50.0  # Weight: 50x
                else:
                    score -= 10.0  # Penalty for low similarity
            
            # Priority 3: Confidence score (if available)
            if 'confidence' in ref_frame:
                confidence = ref_frame['confidence']
                if confidence > 0.5:  # Only reward high confidence
                    score += confidence * 30.0  # Weight: 30x
                elif confidence < 0.3:  # Penalize very low confidence
                    score -= 15.0
            
            # Priority 4: Has video_path and frame_num (complete reference)
            if 'video_path' in ref_frame and 'frame_num' in ref_frame:
                score += 10.0
            else:
                continue  # Skip incomplete references
            
            # Priority 5: Prefer frames with uniform_info (more complete data)
            if 'uniform_info' in ref_frame:
                score += 5.0
            
            # Priority 6: Prefer frames with player_name match (ensures it's the right player)
            # This helps avoid cross-player contamination
            if 'player_name' in ref_frame and ref_frame.get('player_name') == profile.name:
                score += 15.0  # Bonus for explicit player name match
            
            scored_frames.append((score, ref_frame))
        
        # Sort by score (highest first) and return best frame
        if not scored_frames:
            return None
        
        scored_frames.sort(key=lambda x: x[0], reverse=True)
        
        # Return the best frame, but validate it's not obviously wrong
        # (score should be positive and reasonable)
        best_score, best_frame = scored_frames[0]
        if best_score < 0:
            # All frames had negative scores - try to find the least bad one
            # or return None if all are terrible
            if len(scored_frames) > 1:
                # Try second best
                return scored_frames[1][1] if scored_frames[1][0] > best_score else None
            return None
        
        return best_frame
    
    def get_player_confidence_metrics(self, player_id: str) -> Dict:
        """
        Calculate confidence metrics for a player based on their reference frames.
        
        Returns:
            Dict with:
            - avg_similarity: Average similarity score from all reference frames
            - ref_frame_count: Number of reference frames
            - avg_detection_confidence: Average detection confidence from reference frames
            - overall_confidence: Weighted overall confidence score (0-1)
        """
        if player_id not in self.players:
            return {
                'avg_similarity': 0.0,
                'ref_frame_count': 0,
                'avg_detection_confidence': 0.0,
                'overall_confidence': 0.0
            }
        
        profile = self.players[player_id]
        
        if not profile.reference_frames or len(profile.reference_frames) == 0:
            return {
                'avg_similarity': 0.0,
                'ref_frame_count': 0,
                'avg_detection_confidence': 0.0,
                'overall_confidence': 0.0
            }
        
        # Extract similarity scores
        similarities = []
        confidences = []
        
        for ref_frame in profile.reference_frames:
            if 'similarity' in ref_frame and ref_frame['similarity'] is not None:
                similarities.append(float(ref_frame['similarity']))
            if 'confidence' in ref_frame and ref_frame['confidence'] is not None:
                confidences.append(float(ref_frame['confidence']))
        
        # Calculate averages
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
        avg_detection_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        ref_frame_count = len(profile.reference_frames)
        
        # Normalize ref frame count (0-1 scale, max at 1000 frames = 1.0)
        normalized_ref_count = min(ref_frame_count / 1000.0, 1.0)
        
        # Calculate overall confidence (weighted combination)
        # Similarity: 50%, Ref count: 20%, Detection confidence: 30%
        overall_confidence = (
            avg_similarity * 0.5 +
            normalized_ref_count * 0.2 +
            avg_detection_confidence * 0.3
        )
        
        return {
            'avg_similarity': round(avg_similarity, 3),
            'ref_frame_count': ref_frame_count,
            'avg_detection_confidence': round(avg_detection_confidence, 3),
            'overall_confidence': round(overall_confidence, 3)
        }
    
    def remove_player(self, player_id: str):
        """Remove a player from the gallery"""
        if player_id in self.players:
            name = self.players[player_id].name
            del self.players[player_id]
            self.save_gallery()
            print(f"✓ Removed player '{name}' from gallery")
        else:
            print(f"⚠ Player ID '{player_id}' not found in gallery.")
    
    def record_team_switch(self, player_id: str, from_team: str, to_team: str, frame_num: int, video_path: Optional[str] = None):
        """
        Record a team switch event for a player
        
        Args:
            player_id: Player identifier
            from_team: Previous team
            to_team: New team
            frame_num: Frame number when switch occurred
            video_path: Optional video path
        """
        if player_id not in self.players:
            print(f"⚠ Player ID '{player_id}' not found in gallery.")
            return False
        
        profile = self.players[player_id]
        
        # Initialize team_switches if needed
        if profile.team_switches is None:
            profile.team_switches = []
        
        # Create team switch entry
        switch_entry = {
            "frame": frame_num,
            "video": os.path.basename(video_path) if video_path else "unknown",
            "from_team": from_team,
            "to_team": to_team,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to team switch history
        profile.team_switches.append(switch_entry)
        
        # Update player's current team
        profile.team = to_team
        profile.updated_at = datetime.now().isoformat()
        
        print(f"✓ Recorded team switch for '{profile.name}': {from_team} → {to_team} (frame {frame_num})")
        return True
    
    def remove_reference_frame(self, player_id: str, frame_index: int):
        """
        Remove a specific reference frame from a player's profile
        
        Args:
            player_id: Player identifier
            frame_index: Index of the reference frame to remove (0-based)
        
        Returns:
            True if frame was removed, False otherwise
        """
        if player_id not in self.players:
            print(f"⚠ Player ID '{player_id}' not found in gallery.")
            return False
        
        profile = self.players[player_id]
        
        if not profile.reference_frames or frame_index < 0 or frame_index >= len(profile.reference_frames):
            print(f"⚠ Invalid frame index {frame_index} for player '{profile.name}'")
            return False
        
        # Get the frame to remove for logging
        removed_frame = profile.reference_frames[frame_index]
        video_name = os.path.basename(removed_frame.get('video_path', 'unknown')) if removed_frame.get('video_path') else 'unknown'
        frame_num = removed_frame.get('frame_num', '?')
        
        # Remove from main reference_frames list
        _ = profile.reference_frames.pop(frame_index)  # Discard removed frame
        
        # Also remove from uniform_variants if present
        if profile.uniform_variants:
            uniform_info = removed_frame.get('uniform_info')
            if uniform_info:
                jersey = uniform_info.get('jersey_color', 'unknown').lower()
                shorts = uniform_info.get('shorts_color', 'unknown').lower()
                socks = uniform_info.get('socks_color', 'unknown').lower()
                uniform_key = f"{jersey}-{shorts}-{socks}"
                
                if uniform_key in profile.uniform_variants:
                    # Find and remove matching frame from uniform variant
                    for i, variant_frame in enumerate(profile.uniform_variants[uniform_key]):
                        if (variant_frame.get('video_path') == removed_frame.get('video_path') and
                            variant_frame.get('frame_num') == removed_frame.get('frame_num')):
                            _ = profile.uniform_variants[uniform_key].pop(i)  # Discard removed frame
                            break
                    
                    # Clean up empty uniform keys
                    if not profile.uniform_variants[uniform_key]:
                        del profile.uniform_variants[uniform_key]
        
        profile.updated_at = datetime.now().isoformat()
        self.save_gallery()
        
        print(f"✓ Removed reference frame {frame_num} from {video_name} for player '{profile.name}'")
        return True
    
    def merge_player(self, anonymous_player_id: str, target_player_id: str):
        """
        Merge an anonymous player into a named player.
        Combines features, learned data, and reference frames.
        
        Args:
            anonymous_player_id: ID of the anonymous player to merge (will be deleted)
            target_player_id: ID of the target named player (will receive merged data)
        
        Returns:
            True if merge was successful, False otherwise
        """
        if anonymous_player_id not in self.players:
            print(f"⚠ Anonymous player '{anonymous_player_id}' not found in gallery.")
            return False
        
        if target_player_id not in self.players:
            print(f"⚠ Target player '{target_player_id}' not found in gallery.")
            return False
        
        anonymous_profile = self.players[anonymous_player_id]
        target_profile = self.players[target_player_id]
        
        # Merge features (average them)
        if anonymous_profile.features is not None and target_profile.features is not None:
            # Combine features by averaging
            anon_features = np.array(anonymous_profile.features)
            target_features = np.array(target_profile.features)
            
            # If shapes match, average them
            if anon_features.shape == target_features.shape:
                merged_features = (anon_features + target_features) / 2.0
                target_profile.features = merged_features.tolist()
            else:
                # If shapes don't match, use the one with more samples or better quality
                # For now, prefer target (named player) features, but add anonymous as reference
                if anonymous_profile.reference_frames and target_profile.reference_frames is not None:
                    target_profile.reference_frames.extend(anonymous_profile.reference_frames)
                elif anonymous_profile.reference_frames:
                    target_profile.reference_frames = list(anonymous_profile.reference_frames)
        
        # Merge learned features (combine samples)
        if anonymous_profile.shape_samples > 0:
            # Average shape features
            if target_profile.shape_samples == 0:
                target_profile.avg_height = anonymous_profile.avg_height
                target_profile.avg_width = anonymous_profile.avg_width
                target_profile.height_width_ratio = anonymous_profile.height_width_ratio
            else:
                # Weighted average based on sample counts
                total_samples = target_profile.shape_samples + anonymous_profile.shape_samples
                if target_profile.avg_height is not None and anonymous_profile.avg_height is not None:
                    target_profile.avg_height = (target_profile.avg_height * target_profile.shape_samples + 
                                                 anonymous_profile.avg_height * anonymous_profile.shape_samples) / total_samples
                if target_profile.avg_width is not None and anonymous_profile.avg_width is not None:
                    target_profile.avg_width = (target_profile.avg_width * target_profile.shape_samples + 
                                               anonymous_profile.avg_width * anonymous_profile.shape_samples) / total_samples
                if target_profile.height_width_ratio is not None and anonymous_profile.height_width_ratio is not None:
                    target_profile.height_width_ratio = (target_profile.height_width_ratio * target_profile.shape_samples + 
                                                        anonymous_profile.height_width_ratio * anonymous_profile.shape_samples) / total_samples
            target_profile.shape_samples += anonymous_profile.shape_samples
        
        # Merge movement features
        if anonymous_profile.movement_samples > 0:
            if target_profile.movement_samples == 0:
                target_profile.avg_speed = anonymous_profile.avg_speed
                target_profile.max_speed = anonymous_profile.max_speed
                target_profile.avg_acceleration = anonymous_profile.avg_acceleration
            else:
                total_samples = target_profile.movement_samples + anonymous_profile.movement_samples
                if target_profile.avg_speed is not None and anonymous_profile.avg_speed is not None:
                    target_profile.avg_speed = (target_profile.avg_speed * target_profile.movement_samples + 
                                              anonymous_profile.avg_speed * anonymous_profile.movement_samples) / total_samples
                if target_profile.max_speed is not None and anonymous_profile.max_speed is not None:
                    target_profile.max_speed = max(target_profile.max_speed, anonymous_profile.max_speed)
                elif anonymous_profile.max_speed is not None:
                    target_profile.max_speed = anonymous_profile.max_speed
                if target_profile.avg_acceleration is not None and anonymous_profile.avg_acceleration is not None:
                    target_profile.avg_acceleration = (target_profile.avg_acceleration * target_profile.movement_samples + 
                                                     anonymous_profile.avg_acceleration * anonymous_profile.movement_samples) / total_samples
            target_profile.movement_samples += anonymous_profile.movement_samples
        
        # Merge position preferences
        if anonymous_profile.position_samples > 0:
            if target_profile.position_samples == 0:
                target_profile.preferred_x = anonymous_profile.preferred_x
                target_profile.preferred_y = anonymous_profile.preferred_y
                target_profile.position_heatmap = anonymous_profile.position_heatmap
            else:
                total_samples = target_profile.position_samples + anonymous_profile.position_samples
                if target_profile.preferred_x is not None and anonymous_profile.preferred_x is not None:
                    target_profile.preferred_x = (target_profile.preferred_x * target_profile.position_samples + 
                                                 anonymous_profile.preferred_x * anonymous_profile.position_samples) / total_samples
                if target_profile.preferred_y is not None and anonymous_profile.preferred_y is not None:
                    target_profile.preferred_y = (target_profile.preferred_y * target_profile.position_samples + 
                                                 anonymous_profile.preferred_y * anonymous_profile.position_samples) / total_samples
                # Merge heatmaps (average)
                if target_profile.position_heatmap and anonymous_profile.position_heatmap:
                    # Simple merge: combine heatmaps (would need more sophisticated merging for production)
                    pass
            target_profile.position_samples += anonymous_profile.position_samples
        
        # Merge ball interaction
        if anonymous_profile.ball_interaction_samples > 0:
            if target_profile.ball_interaction_samples == 0:
                target_profile.ball_interaction_rate = anonymous_profile.ball_interaction_rate
            else:
                total_samples = target_profile.ball_interaction_samples + anonymous_profile.ball_interaction_samples
                if target_profile.ball_interaction_rate is not None and anonymous_profile.ball_interaction_rate is not None:
                    target_profile.ball_interaction_rate = (target_profile.ball_interaction_rate * target_profile.ball_interaction_samples + 
                                                           anonymous_profile.ball_interaction_rate * anonymous_profile.ball_interaction_samples) / total_samples
            target_profile.ball_interaction_samples += anonymous_profile.ball_interaction_samples
        
        # Merge reference frames
        if anonymous_profile.reference_frames:
            if not target_profile.reference_frames:
                target_profile.reference_frames = []
            target_profile.reference_frames.extend(anonymous_profile.reference_frames)
        
        # Merge dominant color (prefer target, but update if anonymous has better data)
        if anonymous_profile.dominant_color is not None and target_profile.dominant_color is None:
            target_profile.dominant_color = anonymous_profile.dominant_color
        
        # Merge team (prefer target, but update if anonymous has team and target doesn't)
        if anonymous_profile.team is not None and target_profile.team is None:
            target_profile.team = anonymous_profile.team
        
        # Remove anonymous player
        del self.players[anonymous_player_id]
        
        # Save gallery
        self.save_gallery()
        
        print(f"✓ Merged '{anonymous_profile.name}' into '{target_profile.name}'")
        return True
    
    def match_player(self, 
                     features: np.ndarray,
                     similarity_threshold: float = 0.6,
                     dominant_color: Optional[np.ndarray] = None,
                     team: Optional[str] = None,
                     jersey_number: Optional[str] = None,
                     return_all: bool = False,
                     early_frame_range: tuple = (0, 1000),
                     early_frame_boost: float = 0.10,
                     current_frame_num: Optional[int] = None,
                     uniform_info: Optional[Dict] = None,
                     detection_confidence: Optional[float] = None,
                     detection_quality: Optional[float] = None,
                     detection_size: Optional[Tuple[float, float]] = None,
                     detection_position: Optional[Tuple[float, float]] = None,
                     enable_adaptive_threshold: bool = True,
                     strict_team_filtering: bool = False,
                     hard_negative_miner: Optional[Any] = None,
                     track_id: Optional[int] = None,
                     filter_module: Optional[Any] = None,
                     suppress_diagnostics: bool = False,
                     exclude_players: Optional[set] = None,
                     include_only_players: Optional[set] = None,
                     body_features: Optional[np.ndarray] = None,
                     jersey_features: Optional[np.ndarray] = None,
                     foot_features: Optional[np.ndarray] = None,
                     enable_foot_matching: bool = True,
                     log_matching_details: bool = False) -> Union[Tuple[Optional[str], Optional[str], float], List[Tuple[str, str, float]]]:
        """
        Match a detected player against the gallery
        
        Args:
            features: Re-ID feature embedding to match
            similarity_threshold: Minimum cosine similarity for a match
            dominant_color: Dominant color in HSV (optional, for additional filtering)
            team: Team name (optional, for additional filtering)
            jersey_number: Jersey number (optional, for filtering and boosting matches)
            return_all: If True, return all similarities for diagnostics
            early_frame_range: Tuple (min, max) frame numbers for early-frame priority boost (default: (0, 1000))
            early_frame_boost: Proportional boost factor for early-frame tagged players (default: 0.10 = 10% boost, only if similarity >= 0.5)
            filter_module: Optional ReIDFilterModule instance for feature quality checks
            current_frame_num: Optional current frame number - boost only applies if detection is also from early frames (0-1000)
            uniform_info: Dict with uniform details {'jersey_color': 'gray', 'shorts_color': 'black', 'socks_color': 'white'}
                          Matches with same uniform get a boost (0.05-0.10 similarity boost)
            detection_confidence: Optional detection confidence (0-1) for adaptive thresholding
            detection_quality: Optional image quality score (0-1) for adaptive thresholding
            detection_size: Optional detection size (width, height) for negative filtering
            detection_position: Optional detection position (x, y) for position verification
            enable_adaptive_threshold: If True, adjust threshold based on detection quality/confidence
            strict_team_filtering: If True, hard-filter players from different teams (skip entirely).
                                  If False (default), apply soft penalty (8%) but allow cross-team fallback.
                                  Team filtering enforces roster constraints (one player = one team) and
                                  helps reduce wrong identifications by limiting search space. Same-team
                                  matches are strongly preferred, with cross-team fallback for difficult cases.
            exclude_players: Optional set of player names to exclude from gallery matching.
                            If provided, players in this set will be skipped during matching.
                            This is used to exclude anchor-protected players (they're already identified).
            body_features: Optional body features extracted from detection (for better matching)
            jersey_features: Optional jersey features extracted from detection (for better matching)
            foot_features: Optional foot features extracted from detection (for better matching)
            enable_foot_matching: If True, use foot features in matching (default: True)
            log_matching_details: If True, log detailed matching information including foot feature contributions (default: False)
        
        Returns:
            If return_all=False (default):
                (player_id, player_name, similarity_score) or (None, None, 0.0) if no match
            If return_all=True:
                List of (player_id, player_name, similarity_score) for ALL gallery players
        """
        if len(self.players) == 0:
            if return_all:
                return []
            return (None, None, 0.0)
        
        # NEW: Check feature quality using filter module if available
        if filter_module is not None and FILTER_MODULE_AVAILABLE:
            if not filter_module.is_feature_quality_sufficient(features):
                # Low-quality features - skip matching
                return (None, None, 0.0) if not return_all else []
        
        # Normalize features
        if features is None or len(features) == 0:
            return (None, None, 0.0) if not return_all else []
        
        features = np.array(features).flatten()
        feature_norm = np.linalg.norm(features)
        if feature_norm < 1e-8:
            return (None, None, 0.0) if not return_all else []
        
        features = features / feature_norm
        
        best_match_id = None
        best_match_name = None
        best_similarity = 0.0
        best_confidence = 0.0  # ENHANCED: Track confidence score
        
        all_similarities = []  # Store all for diagnostics
        
        # ENHANCED: Adaptive threshold calculation with gallery statistics
        # CRITICAL: Always respect the GUI threshold - never lower it below the user's setting
        effective_threshold = similarity_threshold
        
        # Get gallery statistics for adaptive thresholding
        gallery_stats = self._get_gallery_statistics()
        
        if enable_adaptive_threshold:
            # Adjust based on detection quality
            if detection_confidence is not None and detection_quality is not None:
                if detection_confidence > 0.7 and detection_quality > 0.6:
                    effective_threshold += 0.05  # Slightly stricter for high-quality detections
                elif detection_confidence < 0.4 or detection_quality < 0.4:
                    # More lenient for low-quality detections, but NEVER below GUI threshold
                    effective_threshold = max(similarity_threshold, effective_threshold - 0.20)
                effective_threshold = max(similarity_threshold, min(0.85, effective_threshold))  # Never below GUI threshold
            
            # Adjust based on gallery diversity
            if gallery_stats and gallery_stats.get('diversity_ratio') is not None:
                diversity_ratio = gallery_stats['diversity_ratio']
                # If gallery is diverse (low inter-player similarity): lower threshold
                # If gallery is similar (high inter-player similarity): raise threshold
                if diversity_ratio > 0.3:  # Diverse gallery (players look different)
                    # Can be more lenient, but NEVER below GUI threshold
                    effective_threshold = max(similarity_threshold, effective_threshold - 0.05)
                elif diversity_ratio < 0.15:  # Similar gallery (players look similar)
                    effective_threshold += 0.05  # Need to be stricter
                effective_threshold = max(similarity_threshold, min(0.85, effective_threshold))  # Never below GUI threshold
            
            # Adjust based on gallery size
            if gallery_stats and gallery_stats.get('gallery_size') is not None:
                gallery_size = gallery_stats['gallery_size']
                # Larger galleries may need slightly higher thresholds (more players to distinguish)
                if gallery_size > 20:
                    effective_threshold += 0.02  # Slightly stricter for large galleries
                elif gallery_size < 5:
                    # More lenient for small galleries, but NEVER below GUI threshold
                    effective_threshold = max(similarity_threshold, effective_threshold - 0.03)
                effective_threshold = max(similarity_threshold, min(0.85, effective_threshold))  # Never below GUI threshold
        
        # REMOVED: Auto-lowering threshold optimization - this was overriding GUI settings
        # The GUI threshold should always be respected - users set it for a reason
        # If threshold is too high, users should adjust it in the GUI, not have it auto-lowered
        
        # Normalize input features and ensure 1D shape
        try:
            if isinstance(features, np.ndarray):  # type: ignore[reportUnnecessaryIsInstance]
                features = np.array(features).flatten()  # Ensure 1D
                if len(features) == 0 or np.isnan(features).any():
                    # Invalid features - return empty list if return_all, otherwise no match
                    if return_all:
                        return []
                    return (None, None, 0.0)
                # Normalize features
                norm = np.linalg.norm(features)
                if norm < 1e-8:  # Features are all zeros or too small
                    # Invalid features (all zeros) - return empty list if return_all, otherwise no match
                    if return_all:
                        return []
                    return (None, None, 0.0)
                features = features / norm
            else:
                # Invalid input - return empty list if return_all, otherwise no match
                if return_all:
                    return []
                return (None, None, 0.0)
        except Exception as e:
            # Error normalizing features - return empty list if return_all, otherwise no match
            # DIAGNOSTIC: Log the error for debugging
            import sys
            if hasattr(sys, '_getframe'):
                frame_num = sys._getframe(1).f_locals.get('current_frame_num', 'unknown')
                if frame_num and frame_num % 500 == 0:  # Only log occasionally
                    print(f"   ⚠ DIAGNOSTIC: Error normalizing features in match_player: {e}")
            if return_all:
                return []
            return (None, None, 0.0)
        
        # DIAGNOSTIC: Log matching attempt (occasionally)
        # Note: current_frame_num is not passed to match_player, so we can't use it here
        # We'll rely on the caller to pass it if needed, or log based on other criteria
        
        # DIAGNOSTIC: Check input features before matching (for debugging)
        if isinstance(features, np.ndarray) and features.size > 0:
            input_norm = np.linalg.norm(features)
            if input_norm < 1e-8:
                # Features are all zeros - this is a problem
                if return_all:
                    return []
                return (None, None, 0.0)
        
        # DIAGNOSTIC: Track which players have features (for debugging why only some players match)
        players_with_features = []
        players_without_features = []
        
        for player_id, profile in self.players.items():
            try:
                # FILTER: Include only players in current video (if specified)
                # If include_only_players is provided, ONLY match against these players
                # This prevents matching to players like Jax Derryberry who aren't in the video
                if include_only_players is not None and len(include_only_players) > 0:
                    if profile.name not in include_only_players:
                        # Player is not in current video - skip this match
                        all_similarities.append((player_id, profile.name, 0.0))
                        continue
                
                # FILTER: Exclude anchor players from matching
                # If exclude_players is provided, it contains anchor player names
                # We want to EXCLUDE these players (they're already identified)
                if exclude_players is not None and profile.name in exclude_players:
                    # Player is anchor-protected - skip this match
                    # Anchor players are already identified and shouldn't be matched via Re-ID
                    all_similarities.append((player_id, profile.name, 0.0))
                    continue
                
                if profile.features is None:
                    # Check if player has body_features or jersey_features as fallback
                    has_any_features = (profile.body_features is not None or 
                                       profile.jersey_features is not None)
                    if not has_any_features:
                        players_without_features.append(profile.name)
                        all_similarities.append((player_id, profile.name, 0.0))
                        continue
                    else:
                        players_with_features.append(profile.name)
                else:
                    players_with_features.append(profile.name)
                
                # ENHANCED: Team-based roster constraint filtering
                # Team filtering serves multiple purposes:
                # 1. Enforce roster constraints (player can only be on one team at a time)
                # 2. Reduce wrong identifications by limiting search space
                # 3. Force matches by defaulting to players on the correct team when similarities are low
                # 
                # Strategy: Prioritize same-team matches, but allow cross-team fallback if no good match found
                # This balances roster enforcement with player identification accuracy
                team_penalty = 0.0
                is_team_match = True
                if team is not None and profile.team is not None:
                    if profile.team != team:
                        is_team_match = False
                        if strict_team_filtering:
                            # STRICT MODE: Hard filter - skip players from different teams entirely
                            # Use this when team assignments are very reliable (e.g., games with distinct uniforms)
                            all_similarities.append((player_id, profile.name, 0.0))
                            continue  # Skip this player completely
                        else:
                            # LENIENT MODE: Apply penalty but still allow cross-team matching
                            # This helps enforce roster constraints while allowing fallback for difficult cases
                            # Penalty of 0.08 (8%) strongly prefers same-team but doesn't block strong visual matches
                            team_penalty = 0.08
                    else:
                        # Same team - no penalty, and can apply a small boost for roster consistency
                        # Small boost (0.02 = 2%) to prefer same-team matches when similarities are close
                        # This helps force matches to correct team when similarities are borderline
                        pass  # Will apply boost later if similarity is close to threshold
                
                # ENHANCED: Additional negative filters could go here
                # (size mismatch, impossible position jumps, etc.)
                # These would require additional parameters (detection size, position, etc.)
                
                # JERSEY NUMBER FILTERING/BOOSTING: Use jersey number as search criterion
                jersey_boost = 0.0
                if jersey_number is not None:
                    if profile.jersey_number is not None:
                        # Convert both to strings for comparison (handle int/str mismatch)
                        profile_jersey = str(profile.jersey_number).strip()
                        search_jersey = str(jersey_number).strip()
                        
                        if profile_jersey == search_jersey:
                            # Exact match: Boost similarity significantly (15% boost)
                            jersey_boost = 0.15
                        elif profile_jersey and search_jersey:
                            # Partial match (e.g., "6" vs "06"): Small boost (5% boost)
                            if profile_jersey.replace("0", "") == search_jersey.replace("0", ""):
                                jersey_boost = 0.05
                    # If jersey_number provided but doesn't match, don't filter out (just no boost)
                    # This allows Re-ID features to still match even if jersey number is wrong
                
                # ENHANCED: Multi-feature ensemble matching with foot features
                # Match against multiple features (body, jersey, foot, general) and combine results
                # This provides more robust matching than single-feature matching
                ensemble_similarities = []
                ensemble_weights = []
                feature_contributions = {}  # Track which features contributed for logging
                
                # Determine which input features to use (prefer specific, fallback to general)
                input_body_features = body_features if body_features is not None else features
                input_jersey_features = jersey_features if jersey_features is not None else features
                input_foot_features = foot_features if foot_features is not None else None
                
                # 1. Body features (highest weight - most reliable)
                if profile.body_features is not None:
                    try:
                        profile_body = np.array(profile.body_features).flatten()
                        body_norm = np.linalg.norm(profile_body)
                        if body_norm > 1e-8:
                            profile_body = profile_body / body_norm
                            input_body = np.array(input_body_features).flatten()
                            input_body_norm = np.linalg.norm(input_body)
                            if input_body_norm > 1e-8:
                                input_body = input_body / input_body_norm
                                body_sim = np.dot(input_body, profile_body)
                                if np.isfinite(body_sim):
                                    ensemble_similarities.append(body_sim)
                                    ensemble_weights.append(0.35)  # 35% weight for body
                                    feature_contributions['body'] = body_sim
                    except Exception as e:
                        if log_matching_details:
                            logger.debug(f"Body feature matching error for {profile.name}: {e}")
                
                # 2. Jersey features (medium weight)
                if profile.jersey_features is not None:
                    try:
                        profile_jersey = np.array(profile.jersey_features).flatten()
                        jersey_norm = np.linalg.norm(profile_jersey)
                        if jersey_norm > 1e-8:
                            profile_jersey = profile_jersey / jersey_norm
                            input_jersey = np.array(input_jersey_features).flatten()
                            input_jersey_norm = np.linalg.norm(input_jersey)
                            if input_jersey_norm > 1e-8:
                                input_jersey = input_jersey / input_jersey_norm
                                jersey_sim = np.dot(input_jersey, profile_jersey)
                                if np.isfinite(jersey_sim):
                                    ensemble_similarities.append(jersey_sim)
                                    ensemble_weights.append(0.30)  # 30% weight for jersey
                                    feature_contributions['jersey'] = jersey_sim
                    except Exception as e:
                        if log_matching_details:
                            logger.debug(f"Jersey feature matching error for {profile.name}: {e}")
                
                # 3. Foot features (ENHANCED: Now properly weighted and used)
                # Foot features are especially useful when:
                # - Jerseys are similar (same team)
                # - Players are facing away
                # - Bottom portion is more visible than top
                foot_sim = None
                if enable_foot_matching and profile.foot_features is not None:
                    if input_foot_features is not None:
                        # Use provided foot features (extracted from detection)
                        try:
                            profile_foot = np.array(profile.foot_features).flatten()
                            foot_norm = np.linalg.norm(profile_foot)
                            if foot_norm > 1e-8:
                                profile_foot = profile_foot / foot_norm
                                input_foot = np.array(input_foot_features).flatten()
                                input_foot_norm = np.linalg.norm(input_foot)
                                if input_foot_norm > 1e-8:
                                    input_foot = input_foot / input_foot_norm
                                    foot_sim = np.dot(input_foot, profile_foot)
                                    if np.isfinite(foot_sim):
                                        ensemble_similarities.append(foot_sim)
                                        ensemble_weights.append(0.30)  # 30% weight for foot (increased from 15%)
                                        feature_contributions['foot'] = foot_sim
                                        if log_matching_details:
                                            logger.info(f"  👟 Foot features matched for {profile.name}: similarity={foot_sim:.3f}")
                        except Exception as e:
                            if log_matching_details:
                                logger.debug(f"Foot feature matching error for {profile.name}: {e}")
                    else:
                        # Fallback: Use general features for foot matching (less accurate)
                        try:
                            profile_foot = np.array(profile.foot_features).flatten()
                            foot_norm = np.linalg.norm(profile_foot)
                            if foot_norm > 1e-8:
                                profile_foot = profile_foot / foot_norm
                                input_foot = np.array(features).flatten()
                                input_foot_norm = np.linalg.norm(input_foot)
                                if input_foot_norm > 1e-8:
                                    input_foot = input_foot / input_foot_norm
                                    foot_sim = np.dot(input_foot, profile_foot)
                                    if np.isfinite(foot_sim):
                                        ensemble_similarities.append(foot_sim)
                                        ensemble_weights.append(0.20)  # 20% weight (lower since using general features)
                                        feature_contributions['foot'] = foot_sim
                                        if log_matching_details:
                                            logger.info(f"  👟 Foot features matched (using general features) for {profile.name}: similarity={foot_sim:.3f}")
                        except Exception:
                            pass
                
                # 4. General features (fallback, lower weight)
                if profile.features is not None:
                    try:
                        general_features = np.array(profile.features).flatten()
                        general_norm = np.linalg.norm(general_features)
                        if general_norm > 1e-8:
                            general_features = general_features / general_norm
                            input_general = np.array(features).flatten()
                            input_general_norm = np.linalg.norm(input_general)
                            if input_general_norm > 1e-8:
                                input_general = input_general / input_general_norm
                                general_sim = np.dot(input_general, general_features)
                                if np.isfinite(general_sim):
                                    # Only use general features if we don't have enough specific features
                                    if len(ensemble_similarities) < 2:
                                        ensemble_similarities.append(general_sim)
                                        ensemble_weights.append(0.15)  # 15% weight for general (fallback)
                                        feature_contributions['general'] = general_sim
                    except Exception:
                        pass
                
                # Combine ensemble similarities
                if len(ensemble_similarities) > 0:
                    # Normalize weights to sum to 1.0
                    total_weight = sum(ensemble_weights)
                    if total_weight > 0:
                        # Weighted average of similarities
                        weighted_sim = sum(sim * weight for sim, weight in zip(ensemble_similarities, ensemble_weights)) / total_weight
                        
                        # Log foot feature contribution if it was significant
                        if log_matching_details and 'foot' in feature_contributions:
                            foot_contrib = feature_contributions['foot']
                            foot_idx = ensemble_similarities.index(foot_contrib) if foot_contrib in ensemble_similarities else -1
                            foot_weight = ensemble_weights[foot_idx] / total_weight if foot_idx >= 0 else 0.0
                            if foot_weight > 0.15:  # Only log if foot features have significant weight
                                logger.info(f"  👟 Foot features contributed {foot_weight*100:.1f}% to match with {profile.name} (foot_sim={foot_contrib:.3f}, final_sim={weighted_sim:.3f})")
                        
                        # Log all feature contributions if enabled
                        if log_matching_details and feature_contributions:
                            contrib_str = ", ".join([f"{k}={v:.3f}" for k, v in feature_contributions.items()])
                            logger.debug(f"  Feature contributions for {profile.name}: {contrib_str}")
                        
                        normalized_weights = [w / total_weight for w in ensemble_weights]
                        # Weighted average of similarities
                        weighted_avg = sum(sim * weight for sim, weight in zip(ensemble_similarities, normalized_weights))
                        # Also use max pooling for conservative matching (take the best match)
                        max_similarity = max(ensemble_similarities)
                        # Combine: 70% weighted average, 30% max (conservative)
                        similarity = 0.7 * weighted_avg + 0.3 * max_similarity
                    else:
                        similarity = max(ensemble_similarities) if ensemble_similarities else 0.0
                else:
                    # No features available
                    all_similarities.append((player_id, profile.name, 0.0))
                    continue
                
                # ENHANCED: Hard negative mining integration
                # Adjust similarity if this detection is similar to known hard negatives for this player
                if hard_negative_miner is not None:
                    try:
                        # Get player feature for hard negative comparison
                        player_feature_for_hn = None
                        if profile.body_features is not None:
                            player_feature_for_hn = np.array(profile.body_features).flatten()
                        elif profile.features is not None:
                            player_feature_for_hn = np.array(profile.features).flatten()
                        
                        if player_feature_for_hn is not None:
                            # Check if hard negative miner has method to adjust similarity
                            if hasattr(hard_negative_miner, 'adjust_similarity_with_negatives'):
                                original_similarity = similarity
                                # Normalize features for comparison
                                player_feature_norm = player_feature_for_hn / (np.linalg.norm(player_feature_for_hn) + 1e-8)
                                detection_feature_norm = features / (np.linalg.norm(features) + 1e-8)
                                
                                similarity = hard_negative_miner.adjust_similarity_with_negatives(
                                    player_feature=player_feature_norm,
                                    candidate_feature=detection_feature_norm,
                                    player_id=player_id,
                                    base_similarity=similarity
                                )
                                # Log if adjustment was significant
                                if abs(original_similarity - similarity) > 0.05:
                                    if len(all_similarities) < 3:
                                        print(f"   ⚠ Hard negative adjustment for {profile.name}: {original_similarity:.3f} → {similarity:.3f}")
                    except Exception as e:
                        # If hard negative mining fails, continue with original similarity
                        if len(all_similarities) < 3:
                            print(f"   ⚠ Hard negative mining error: {e}")
                        pass
                
                # Apply team mismatch penalty (soft filter for roster enforcement)
                if team_penalty > 0:
                    similarity = max(0.0, similarity - team_penalty)
                    # DIAGNOSTIC: Log team penalty application
                    if len(all_similarities) < 3:
                        print(f"   ⚠ DIAGNOSTIC: match_player - {profile.name}: Applied team penalty (-{team_penalty:.2f}), similarity: {similarity:.4f}")
                
                # Apply same-team boost for roster consistency (helps force matches when similarities are borderline)
                if is_team_match and team is not None:
                    # Small boost (0.02 = 2%) to prefer same-team matches when similarity is close to threshold
                    # This helps enforce roster constraints by pushing borderline matches over the threshold
                    if similarity >= (effective_threshold - 0.05) and similarity < effective_threshold:
                        similarity = min(1.0, similarity + 0.02)
                        if len(all_similarities) < 3:
                            print(f"   ✓ DIAGNOSTIC: match_player - {profile.name}: Applied same-team boost (+0.02), similarity: {similarity:.4f}")
                
                # DIAGNOSTIC: Log similarity computation for debugging (occasionally)
                # Only log for first few players to avoid spam
                if len(all_similarities) < 3:
                    # Check if similarity is actually being computed
                    if np.isnan(similarity) or not np.isfinite(similarity):
                        print(f"   ⚠ DIAGNOSTIC: match_player - {profile.name}: similarity is NaN or Inf (features norm: {np.linalg.norm(features):.4f}, gallery norm: {np.linalg.norm(gallery_features):.4f})")
                    elif abs(similarity) < 1e-6:
                        print(f"   ⚠ DIAGNOSTIC: match_player - {profile.name}: similarity is near-zero ({similarity:.6f}) - features may be orthogonal or incorrectly normalized")
                    else:
                        # Log successful similarity computation (before boosts)
                        # Note: Final similarity after boosts will be logged separately if it exceeds threshold
                        pass  # Reduced verbosity - only log if needed for debugging
                
                # Note: Multi-feature ensemble matching is now done above (replaces old multi-region fusion)
                # The similarity computed above already combines body, jersey, foot, and general features
                # using weighted ensemble with max pooling for conservative matching
                
                # DIAGNOSTIC: Log first few similarity computations (only for debugging, disabled by default)
                # Uncomment the line below to enable detailed similarity logging
                # if len(all_similarities) < 3:
                #     print(f"   🔍 DIAGNOSTIC: match_player - {profile.name}: similarity={similarity:.4f}")
                
                # Check for NaN or invalid similarity
                if np.isnan(similarity) or not np.isfinite(similarity):
                    similarity = 0.0
                
                # Color similarity boost (optional)
                # IMPROVED: Better color matching with weighted HSV components
                if dominant_color is not None and profile.dominant_color is not None:
                    try:
                        profile_color = np.array(profile.dominant_color)
                        detection_color = np.array(dominant_color)
                        
                        # Compute color distance in HSV space with proper weighting
                        # Hue is most important (0-180), Saturation and Value are 0-255
                        hue_diff = abs(detection_color[0] - profile_color[0])
                        hue_diff = min(hue_diff, 180 - hue_diff)  # Handle wraparound
                        sat_diff = abs(detection_color[1] - profile_color[1])
                        val_diff = abs(detection_color[2] - profile_color[2])
                        
                        # Normalize differences: hue (0-90), sat/val (0-255)
                        hue_sim = 1.0 - (hue_diff / 90.0)  # Hue difference normalized to 0-1
                        sat_sim = 1.0 - (sat_diff / 255.0)  # Saturation similarity
                        val_sim = 1.0 - (val_diff / 255.0)  # Value similarity
                        
                        # Weighted combination: hue (50%), saturation (30%), value (20%)
                        color_similarity = 0.5 * hue_sim + 0.3 * sat_sim + 0.2 * val_sim
                        color_similarity = max(0.0, min(1.0, color_similarity))  # Clamp to [0, 1]
                        
                        # IMPROVED: Only boost if color similarity is good (>= 0.6) to avoid false matches
                        # Use 15% weight instead of 10% for better color-based matching
                        if color_similarity >= 0.6:
                            similarity = 0.85 * similarity + 0.15 * color_similarity
                    except Exception:
                        # If color matching fails, continue without color boost
                        pass
                
                # Apply jersey number boost (proportional, like early-frame boost)
                # IMPROVED: Lower threshold to 0.25 to help borderline matches
                if jersey_boost > 0 and similarity >= 0.25:  # Boost if similarity is reasonable
                    similarity = min(1.0, similarity * (1.0 + jersey_boost))
                
                # UNIFORM MATCHING BOOST: Boost matches with same uniform variant
                uniform_boost = 0.0
                if uniform_info is not None and profile.uniform_variants is not None:
                    # Create uniform key for detection
                    det_jersey = uniform_info.get('jersey_color', 'unknown').lower()
                    det_shorts = uniform_info.get('shorts_color', 'unknown').lower()
                    det_socks = uniform_info.get('socks_color', 'unknown').lower()
                    det_uniform_key = f"{det_jersey}-{det_shorts}-{det_socks}"
                    
                    # Check if player has this uniform variant
                    if det_uniform_key in profile.uniform_variants:
                        # Exact uniform match: Strong boost (10% boost)
                        uniform_boost = 0.10
                    else:
                        # Partial match: Check for jersey color match only (5% boost)
                        for variant_key in profile.uniform_variants.keys():
                            variant_jersey = variant_key.split('-')[0] if '-' in variant_key else variant_key
                            if variant_jersey == det_jersey and det_jersey != 'unknown':
                                uniform_boost = 0.05
                                break
                
                # Apply uniform boost
                # IMPROVED: Lower threshold to 0.25 to help borderline matches
                if uniform_boost > 0 and similarity >= 0.25:  # Boost if similarity is reasonable
                    similarity = min(1.0, similarity * (1.0 + uniform_boost))
                
                # Early-frame priority boost: Boost players tagged in early frames (20-120)
                # BUT: Only boost if the CURRENT detection is also from an early frame
                # This prevents early-frame tagged players from dominating later detections
                if profile.reference_frames and len(profile.reference_frames) > 0:
                    early_frame_min, early_frame_max = early_frame_range
                    has_early_frame_tag = False
                    for ref_frame in profile.reference_frames:
                        frame_num = ref_frame.get('frame_num', None)
                        if frame_num is not None and early_frame_min <= frame_num <= early_frame_max:
                            has_early_frame_tag = True
                            break
                    
                    # Only boost if BOTH conditions are met:
                    # 1. Player was tagged in early frames (20-120)
                    # 2. Current detection is also from early frames (if frame number is provided)
                    should_boost = has_early_frame_tag
                    if current_frame_num is not None:
                        # Only boost if current detection is also from early frames
                        should_boost = should_boost and (early_frame_min <= current_frame_num <= early_frame_max)
                    
                    if should_boost:
                        # Boost similarity for early-frame tagged players matching early-frame detections
                        # Use PROPORTIONAL boost (10% increase) instead of flat boost
                        # This prevents early-frame players from dominating when they shouldn't
                        # IMPROVED: Lower threshold to 0.35 to help more borderline matches
                        if similarity >= 0.35:
                            # Proportional boost: multiply by (1 + boost_factor)
                            # e.g., 0.10 boost = 10% increase: 0.45 * 1.10 = 0.495, still below 0.60
                            # But if we have jersey boost too: 0.45 * 1.10 * 1.15 = 0.57, closer to threshold
                            similarity = min(1.0, similarity * (1.0 + early_frame_boost))
                
                # Store final similarity (after all boosts)
                all_similarities.append((player_id, profile.name, similarity))
                
                # DIAGNOSTIC: Log final similarity for ALL players (not just first 3)
                # Log if similarity is above a minimum threshold to reduce spam
                # Show top matches and any that are close to threshold
                # Skip diagnostics if suppress_diagnostics is True (for alternative matching)
                if not suppress_diagnostics:
                    min_log_threshold = max(0.25, effective_threshold - 0.20)  # Log if within 0.20 of threshold or above 0.25
                    if similarity >= min_log_threshold:
                        print(f"   ✓ DIAGNOSTIC: match_player - {profile.name}: final_similarity={similarity:.4f} (threshold: {effective_threshold:.2f})")
                
                # ENHANCED: Use confidence score for best match selection
                match_confidence = confidence_score if 'confidence_score' in locals() else similarity
                
                if similarity > best_similarity and similarity >= effective_threshold:
                    best_similarity = similarity
                    best_confidence = match_confidence
                    best_match_id = player_id
                    best_match_name = profile.name
            except Exception:
                # If there's an error processing this player, skip it
                # Don't append anything invalid to all_similarities
                continue
        
        # Return all similarities if requested (for diagnostics)
        if return_all:
            return sorted(all_similarities, key=lambda x: x[2], reverse=True)
        
        # ENHANCED: Two-pass matching for roster enforcement
        # Pass 1: Prefer same-team matches (roster constraint enforcement)
        # Pass 2: Fallback to cross-team if no good same-team match found
        
        # DIAGNOSTIC: Log matching results with more detail
        # Skip diagnostics if suppress_diagnostics is True (for alternative matching)
        # Only log when there's a meaningful match (similarity > 0) to avoid spam
        if not suppress_diagnostics and len(all_similarities) > 0:
            # Sort by similarity for better diagnostics
            sorted_similarities = sorted(all_similarities, key=lambda x: x[2], reverse=True)
            max_sim = sorted_similarities[0][2] if sorted_similarities else 0
            
            # Only print diagnostic if there's a meaningful match (similarity > 0)
            # If all similarities are 0.000, that's expected (no gallery data) and doesn't need logging
            if max_sim > 0:
                # Log top 5 matches for better visibility
                top_matches = sorted_similarities[:5]
                if len(top_matches) > 0:
                    match_list = ", ".join([f"{name}={sim:.3f}" for _, name, sim in top_matches])
                    same_team_count = sum(1 for pid, _, sim in all_similarities 
                                        if sim > 0 and self.players.get(pid) and 
                                        team is not None and self.players[pid].team == team)
                    total_checked = len([s for s in all_similarities if s[2] > 0])
                    print(f"   🔍 DIAGNOSTIC: match_player - Top matches: {match_list} | "
                          f"Max: {max_sim:.4f} (threshold: {effective_threshold:.2f}), "
                          f"same-team: {same_team_count}/{total_checked}, total checked: {len(all_similarities)}")
        
        # Separate same-team and cross-team matches
        same_team_matches = []
        cross_team_matches = []
        
        for player_id, player_name, similarity in all_similarities:
            if similarity <= 0.0:
                continue  # Skip invalid matches
            
            # Check if this is a same-team match
            profile = self.players.get(player_id)
            if profile and team is not None and profile.team is not None:
                if profile.team == team:
                    same_team_matches.append((player_id, player_name, similarity))
                else:
                    cross_team_matches.append((player_id, player_name, similarity))
            else:
                # No team info - treat as potential match (neutral)
                same_team_matches.append((player_id, player_name, similarity))
        
        # Sort by similarity (highest first)
        same_team_matches.sort(key=lambda x: x[2], reverse=True)
        cross_team_matches.sort(key=lambda x: x[2], reverse=True)
        
        # Pass 1: Check for same-team matches that meet threshold
        if same_team_matches and same_team_matches[0][2] >= effective_threshold:
            best_match_id, best_match_name, best_similarity = same_team_matches[0]
            similarity_float = float(best_similarity) if isinstance(best_similarity, (np.floating, np.ndarray)) else best_similarity
            return (best_match_id, best_match_name, similarity_float)
        
        # Pass 2: Fallback to cross-team matches if no good same-team match
        # This allows player identification when team assignment is uncertain
        # but still enforces roster constraints when team info is reliable
        if cross_team_matches and cross_team_matches[0][2] >= effective_threshold:
            best_match_id, best_match_name, best_similarity = cross_team_matches[0]
            similarity_float = float(best_similarity) if isinstance(best_similarity, (np.floating, np.ndarray)) else best_similarity
            return (best_match_id, best_match_name, similarity_float)
        
        # Pass 3: If no match meets threshold, return best available (for forced matching)
        # This helps keep players tagged to tracks even when similarities are low
        # Prefer same-team matches even if below threshold (roster enforcement)
        if same_team_matches:
            best_match_id, best_match_name, best_similarity = same_team_matches[0]
            # Only return if similarity is reasonable (>= 0.3) to avoid very wrong matches
            if best_similarity >= 0.3:
                similarity_float = float(best_similarity) if isinstance(best_similarity, (np.floating, np.ndarray)) else best_similarity
                return (best_match_id, best_match_name, similarity_float)
        
        # Final fallback: cross-team match if reasonable
        if cross_team_matches and cross_team_matches[0][2] >= 0.3:
            best_match_id, best_match_name, best_similarity = cross_team_matches[0]
            similarity_float = float(best_similarity) if isinstance(best_similarity, (np.floating, np.ndarray)) else best_similarity
            return (best_match_id, best_match_name, similarity_float)
        
        # No reasonable match found
        return (None, None, 0.0)
    
    def get_player(self, player_id: str) -> Optional[PlayerProfile]:
        """Get a player profile by ID"""
        return self.players.get(player_id)
    
    def list_players(self) -> List[Tuple[str, str]]:
        """Get list of all players as (player_id, player_name) tuples"""
        return [(pid, profile.name) for pid, profile in self.players.items()]
    
    def _get_gallery_statistics(self, force_update: bool = False) -> Optional[Dict]:
        """
        Calculate gallery statistics for adaptive thresholding.
        Caches results to avoid expensive recomputation.
        
        Returns:
            Dict with:
            - gallery_size: Number of players
            - diversity_ratio: Inter-player vs intra-player similarity ratio
            - avg_inter_player_sim: Average similarity between different players
            - avg_intra_player_sim: Average similarity within same player
        """
        # Check cache
        if not force_update and self._gallery_stats_cache is not None:
            return self._gallery_stats_cache
        
        if len(self.players) < 2:
            # Need at least 2 players for diversity calculation
            return {
                'gallery_size': len(self.players),
                'diversity_ratio': 0.5,  # Default neutral ratio
                'avg_inter_player_sim': 0.3,
                'avg_intra_player_sim': 0.6
            }
        
        # Calculate inter-player similarities (how similar are different players?)
        inter_player_similarities = []
        intra_player_similarities = []
        
        player_ids = list(self.players.keys())
        player_features = {}
        
        # Extract features for all players
        for player_id in player_ids:
            profile = self.players[player_id]
            # Use best available feature
            if profile.body_features is not None:
                features = np.array(profile.body_features).flatten()
            elif profile.jersey_features is not None:
                features = np.array(profile.jersey_features).flatten()
            elif profile.features is not None:
                features = np.array(profile.features).flatten()
            else:
                continue
            
            # Normalize
            norm = np.linalg.norm(features)
            if norm > 1e-8:
                player_features[player_id] = features / norm
        
        # Calculate inter-player similarities (between different players)
        player_id_list = list(player_features.keys())
        for i in range(len(player_id_list)):
            for j in range(i + 1, len(player_id_list)):
                feat1 = player_features[player_id_list[i]]
                feat2 = player_features[player_id_list[j]]
                sim = np.dot(feat1, feat2)
                if np.isfinite(sim):
                    inter_player_similarities.append(float(sim))
        
        # Calculate intra-player similarities (within same player, using reference frames)
        # This is approximated by checking feature consistency
        # For now, use a default value based on typical Re-ID performance
        # (In practice, intra-player similarity should be higher than inter-player)
        avg_inter_player_sim = np.mean(inter_player_similarities) if inter_player_similarities else 0.3
        avg_intra_player_sim = 0.6  # Typical value for good Re-ID models
        
        # Diversity ratio: lower = more diverse (players look different)
        # Higher = less diverse (players look similar)
        if avg_inter_player_sim > 0:
            diversity_ratio = avg_inter_player_sim / (avg_intra_player_sim + 1e-8)
        else:
            diversity_ratio = 0.2  # Default: diverse gallery
        
        stats = {
            'gallery_size': len(self.players),
            'diversity_ratio': float(diversity_ratio),
            'avg_inter_player_sim': float(avg_inter_player_sim),
            'avg_intra_player_sim': float(avg_intra_player_sim)
        }
        
        # Cache results
        self._gallery_stats_cache = stats
        return stats
    
    def add_event_to_player(self, player_name: str, event_data: Dict) -> bool:
        """
        Add an event to a player's event history.
        
        Args:
            player_name: Name of the player
            event_data: Event dictionary with keys: event_type, frame_num, timestamp, 
                       video_path, confidence, metadata, verified (optional)
        
        Returns:
            True if event was added, False if player not found
        """
        # Find player by name
        player = None
        for pid, profile in self.players.items():
            if profile.name == player_name:
                player = profile
                break
        
        if not player:
            return False
        
        # Initialize events list if needed
        if player.events is None:
            player.events = []
        
        # Add event
        player.events.append(event_data)
        
        # Update event counts
        if player.event_counts is None:
            player.event_counts = {}
        
        event_type = event_data.get('event_type', 'unknown')
        player.event_counts[event_type] = player.event_counts.get(event_type, 0) + 1
        
        # Update timestamp
        player.updated_at = datetime.now().isoformat()
        
        return True
    
    def get_player_events(self, player_name: str, event_type: Optional[str] = None) -> List[Dict]:
        """
        Get events for a specific player.
        
        Args:
            player_name: Name of the player
            event_type: Optional filter by event type (e.g., "pass", "shot")
        
        Returns:
            List of event dictionaries
        """
        # Find player by name
        player = None
        for pid, profile in self.players.items():
            if profile.name == player_name:
                player = profile
                break
        
        if not player or player.events is None:
            return []
        
        if event_type:
            return [e for e in player.events if e.get('event_type') == event_type]
        else:
            return player.events.copy()
    
    def get_player_event_counts(self, player_name: str) -> Dict[str, int]:
        """
        Get event counts for a specific player.
        
        Args:
            player_name: Name of the player
        
        Returns:
            Dictionary of {event_type: count}
        """
        # Find player by name
        player = None
        for pid, profile in self.players.items():
            if profile.name == player_name:
                player = profile
                break
        
        if not player or player.event_counts is None:
            return {}
        
        return player.event_counts.copy()
    
    def import_events_from_csv(self, csv_path: str) -> Dict[str, int]:
        """
        Import detected events from CSV and assign to players in gallery.
        
        Args:
            csv_path: Path to detected events CSV file
        
        Returns:
            Dictionary of {player_name: events_added_count}
        """
        import pandas as pd
        
        if not os.path.exists(csv_path):
            logger.warning(f"Events CSV not found: {csv_path}")
            return {}
        
        try:
            df = pd.read_csv(csv_path)
            events_added = {}
            
            for idx, row in df.iterrows():
                player_name = row.get('player_name')
                if pd.isna(player_name) or not player_name:
                    continue
                
                event_data = {
                    'event_type': row.get('event_type', 'unknown'),
                    'frame_num': int(row.get('frame_num', 0)),
                    'timestamp': float(row.get('timestamp', 0.0)),
                    'video_path': None,  # Will be set from CSV path
                    'confidence': float(row.get('confidence', 0.0)),
                    'metadata': eval(row.get('metadata', '{}')) if pd.notna(row.get('metadata')) else {},
                    'verified': False  # Not verified by default
                }
                
                # Try to infer video path from CSV path
                csv_dir = os.path.dirname(csv_path)
                csv_basename = os.path.splitext(os.path.basename(csv_path))[0]
                # Remove _detected_events suffix if present
                if csv_basename.endswith('_detected_events'):
                    video_basename = csv_basename.replace('_detected_events', '')
                else:
                    video_basename = csv_basename
                
                # Look for video file in same directory
                video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.m4v']
                for ext in video_extensions:
                    video_path = os.path.join(csv_dir, f"{video_basename}{ext}")
                    if os.path.exists(video_path):
                        event_data['video_path'] = video_path
                        break
                
                if self.add_event_to_player(player_name, event_data):
                    events_added[player_name] = events_added.get(player_name, 0) + 1
            
            logger.info(f"Imported {sum(events_added.values())} events for {len(events_added)} players")
            return events_added
            
        except Exception as e:
            logger.error(f"Error importing events from CSV: {e}", exc_info=True)
            return {}
    
    def get_stats(self) -> Dict:
        """Get gallery statistics"""
        total_players = len(self.players)
        players_with_features = sum(1 for p in self.players.values() if p.features is not None)
        players_with_refs = sum(1 for p in self.players.values() 
                               if p.reference_frames and len(p.reference_frames) > 0)
        players_with_events = sum(1 for p in self.players.values() 
                                 if p.events and len(p.events) > 0)
        total_events = sum(len(p.events) if p.events else 0 for p in self.players.values())
        
        # Get enhanced statistics
        enhanced_stats = self._get_gallery_statistics()
        
        stats = {
            "total_players": total_players,
            "players_with_features": players_with_features,
            "players_with_reference_frames": players_with_refs,
            "players_with_events": players_with_events,
            "total_events": total_events,
            "gallery_path": self.gallery_path
        }
        
        # Add enhanced statistics if available
        if enhanced_stats:
            stats.update({
                "diversity_ratio": enhanced_stats.get('diversity_ratio', 0.5),
                "avg_inter_player_sim": enhanced_stats.get('avg_inter_player_sim', 0.3),
                "avg_intra_player_sim": enhanced_stats.get('avg_intra_player_sim', 0.6)
            })
        
        return stats


if __name__ == "__main__":
    # Test the gallery system
    gallery = PlayerGallery()
    stats = gallery.get_stats()
    print("\n=== Player Gallery Stats ===")
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print("\n=== Current Players ===")
    players = gallery.list_players()
    if players:
        for pid, name in players:
            print(f"  {pid}: {name}")
    else:
        print("  No players in gallery yet.")

