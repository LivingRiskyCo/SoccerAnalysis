"""
Gallery Manager - Handles player gallery operations
Shared across all viewer modes
"""

from typing import Optional, Dict, List
import sys
import os
from pathlib import Path

# Try to import PlayerGallery
GALLERY_AVAILABLE = False
try:
    current_file = Path(__file__).resolve()
    parent_dir = current_file.parent.parent.parent.parent  # SoccerID -> soccer_analysis
    gallery_path = os.path.join(parent_dir, 'SoccerID', 'models', 'player_gallery.py')
    if os.path.exists(gallery_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("player_gallery", gallery_path)
        gallery_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gallery_module)
        PlayerGallery = gallery_module.PlayerGallery
        GALLERY_AVAILABLE = True
    else:
        # Try legacy path
        legacy_path = os.path.join(parent_dir, 'player_gallery.py')
        if os.path.exists(legacy_path):
            import importlib.util
            spec = importlib.util.spec_from_file_location("player_gallery", legacy_path)
            gallery_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(gallery_module)
            PlayerGallery = gallery_module.PlayerGallery
            GALLERY_AVAILABLE = True
        else:
            from player_gallery import PlayerGallery
            GALLERY_AVAILABLE = True
except ImportError:
    pass


class GalleryManager:
    """Manages player gallery operations"""
    
    def __init__(self):
        self.gallery = None
        self.initialized = False
        
    def initialize(self):
        """Initialize player gallery"""
        if not GALLERY_AVAILABLE:
            print("Warning: Player gallery not available")
            return False
        
        try:
            self.gallery = PlayerGallery()
            self.gallery.load_gallery()
            self.initialized = True
            print(f"✓ Loaded player gallery with {len(self.gallery.players)} players")
            return True
        except Exception as e:
            print(f"Warning: Could not load player gallery: {e}")
            return False
    
    def match_player(self, features, foot_features=None, detected_jersey=None, 
                    dominant_color=None, detection_team=None, filter_module=None) -> Optional[tuple]:
        """Match features to a player in the gallery"""
        if not self.initialized or self.gallery is None:
            return None
        
        try:
            result = self.gallery.match_player(
                features=features,
                foot_features=foot_features,
                detected_jersey=detected_jersey,
                dominant_color=dominant_color,
                detection_team=detection_team,
                filter_module=filter_module
            )
            return result  # (player_name, confidence, details)
        except Exception as e:
            print(f"Error matching player: {e}")
            return None
    
    def get_player_names(self) -> List[str]:
        """Get list of all player names in gallery"""
        if not self.initialized or self.gallery is None:
            return []
        return list(self.gallery.players.keys())
    
    def get_player(self, player_name: str):
        """Get player profile by name"""
        if not self.initialized or self.gallery is None:
            return None
        return self.gallery.players.get(player_name)
    
    def add_player(self, player_name: str, features=None, foot_features=None, 
                   team=None, jersey_number=None):
        """Add or update a player in the gallery"""
        if not self.initialized or self.gallery is None:
            return False
        
        try:
            if player_name not in self.gallery.players:
                # Create new player
                from player_gallery import PlayerProfile
                profile = PlayerProfile(
                    name=player_name,
                    team=team,
                    jersey_number=jersey_number
                )
                self.gallery.players[player_name] = profile
            
            # Update features
            if features is not None:
                self.gallery.players[player_name].add_features(features)
            if foot_features is not None:
                self.gallery.players[player_name].add_foot_features(foot_features)
            
            return True
        except Exception as e:
            print(f"Error adding player: {e}")
            return False
    
    def save_gallery(self):
        """Save gallery to disk"""
        if not self.initialized or self.gallery is None:
            return False
        
        try:
            self.gallery.save_gallery()
            return True
        except Exception as e:
            print(f"Error saving gallery: {e}")
            return False
    
    def is_initialized(self) -> bool:
        """Check if gallery is initialized"""
        return self.initialized

