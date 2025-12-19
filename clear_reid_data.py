"""
Clear all re-identification data from player gallery
This removes ALL learned features, reference frames, and behavioral data
to allow the system to start learning from scratch.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

def clear_all_reid_data(gallery_path="player_gallery.json"):
    """
    Clear ALL re-ID data from the player gallery
    This will keep player names/jersey numbers/teams but remove all learned data
    """
    
    print("=" * 70)
    print("CLEARING ALL RE-ID DATA FROM PLAYER GALLERY")
    print("=" * 70)
    print()
    
    if not Path(gallery_path).exists():
        print(f"! Gallery file not found: {gallery_path}")
        print("  Nothing to clear. Starting fresh!")
        # Create empty gallery
        with open(gallery_path, 'w') as f:
            json.dump({}, f, indent=2)
        return True
    
    # Load current gallery
    try:
        with open(gallery_path, 'r') as f:
            gallery_data = json.load(f)
    except Exception as e:
        print(f"! Error loading gallery: {e}")
        return False
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{gallery_path}.backup_{timestamp}"
    try:
        shutil.copy2(gallery_path, backup_path)
        print(f"[OK] Backup created: {backup_path}")
    except Exception as e:
        print(f"! Could not create backup: {e}")
        response = input("Continue without backup? (y/n): ")
        if response.lower() != 'y':
            return False
    
    print()
    print("Clearing re-ID data for each player...")
    print()
    
    # Clear all re-ID related data from each player
    total_features_cleared = 0
    total_refs_cleared = 0
    
    for player_id, player_data in gallery_data.items():
        player_name = player_data.get('name', player_id)
        
        # Count what's being cleared
        features_count = 1 if player_data.get('features') else 0
        refs_count = len(player_data.get('reference_frames') or [])
        uniform_variants = player_data.get('uniform_variants') or {}
        variants_count = sum(len(frames) for frames in uniform_variants.values())
        
        # Clear feature embeddings
        if 'features' in player_data:
            player_data['features'] = None
        
        # Clear reference frames
        if 'reference_frames' in player_data:
            player_data['reference_frames'] = []
        
        # Clear uniform variants
        if 'uniform_variants' in player_data:
            player_data['uniform_variants'] = {}
        
        # Clear learned characteristics
        player_data['avg_height'] = None
        player_data['avg_width'] = None
        player_data['height_width_ratio'] = None
        player_data['shape_samples'] = 0
        
        player_data['avg_speed'] = None
        player_data['max_speed'] = None
        player_data['avg_acceleration'] = None
        player_data['movement_samples'] = 0
        player_data['velocity_history'] = None
        
        player_data['position_heatmap'] = None
        player_data['preferred_x'] = None
        player_data['preferred_y'] = None
        player_data['position_samples'] = 0
        
        player_data['movement_style'] = None
        player_data['ball_interaction_rate'] = None
        player_data['ball_interaction_samples'] = 0
        
        player_data['track_history'] = None
        player_data['dominant_color'] = None
        
        # Update timestamp
        player_data['updated_at'] = datetime.now().isoformat()
        
        total_features_cleared += features_count
        total_refs_cleared += refs_count + variants_count
        
        if features_count > 0 or refs_count > 0 or variants_count > 0:
            print(f"  • {player_name}:")
            if features_count > 0:
                print(f"    - Cleared feature embeddings")
            if refs_count > 0:
                print(f"    - Cleared {refs_count} reference frame(s)")
            if variants_count > 0:
                print(f"    - Cleared {variants_count} uniform variant frame(s)")
    
    # Save updated gallery
    try:
        with open(gallery_path, 'w') as f:
            json.dump(gallery_data, f, indent=2)
        
        print()
        print("=" * 70)
        print(f"[OK] Cleared {total_features_cleared} feature embedding(s)")
        print(f"[OK] Cleared {total_refs_cleared} reference frame(s)")
        print(f"[OK] Cleared all learned behavioral data")
        print(f"[OK] Gallery saved: {gallery_path}")
        print("=" * 70)
        print()
        print("NEXT STEPS:")
        print("  1. Player names and teams are preserved")
        print("  2. Start a new analysis - the system will learn fresh features")
        print("  3. Use anchor frames carefully to guide initial learning")
        print("  4. The system will build new, accurate re-ID data from scratch")
        print()
        print(f"To restore previous data: copy {backup_path} to {gallery_path}")
        print()
        
        return True
    except Exception as e:
        print(f"! Error saving gallery: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    # Check for confirmation flag
    if len(sys.argv) > 1 and sys.argv[1] == "--yes":
        confirmed = True
    else:
        print()
        print("=" * 70)
        print("WARNING: This will clear ALL re-identification data!")
        print("=" * 70)
        print()
        print("This will remove:")
        print("  - All learned feature embeddings")
        print("  - All reference frames")
        print("  - All uniform variants")
        print("  - All behavioral patterns (speed, position, movement)")
        print("  - All learned characteristics")
        print()
        print("This will keep:")
        print("  - Player names")
        print("  - Jersey numbers")
        print("  - Team assignments")
        print()
        
        response = input("Are you sure you want to clear all re-ID data? (yes/no): ")
        confirmed = response.lower() in ['yes', 'y']
    
    if confirmed:
        success = clear_all_reid_data()
        if success:
            print("[OK] Done! Re-ID data cleared. Ready to learn from scratch.")
        else:
            print("[ERROR] Failed to clear re-ID data. Check errors above.")
            sys.exit(1)
    else:
        print("Cancelled. No changes made.")
        sys.exit(0)

