"""
Migrate Player Gallery Data from Legacy to Refactored Version
This script imports player gallery data from the previous version to the new refactored version.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime


def find_legacy_gallery_files():
    """Find all player_gallery.json files in the project"""
    gallery_files = []
    
    # Check root directory
    root_gallery = Path("player_gallery.json")
    if root_gallery.exists():
        gallery_files.append(("root", str(root_gallery.absolute())))
    
    # Check soccer_analysis directory
    sa_gallery = Path("soccer_analysis/player_gallery.json")
    if sa_gallery.exists():
        gallery_files.append(("soccer_analysis", str(sa_gallery.absolute())))
    
    # Check for backup files
    for backup_file in Path(".").glob("player_gallery*.json*"):
        if backup_file.name != "player_gallery.json":
            gallery_files.append((f"backup_{backup_file.name}", str(backup_file.absolute())))
    
    return gallery_files


def load_gallery_file(file_path):
    """Load a player gallery JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # The new version expects a flat dict {player_id: player_data}
        # The old version might have {"players": {player_id: player_data}}
        # Normalize to the new format
        if isinstance(data, dict):
            if "players" in data:
                # Old format with nested "players" key
                normalized = {}
                for player_id, player_data in data["players"].items():
                    normalized[player_id] = player_data
                return normalized
            else:
                # Already in new format (flat dict)
                return data
        
        return data
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return None


def merge_galleries(legacy_data, new_data):
    """Merge two gallery datasets, preferring newer data"""
    # Both should be flat dicts {player_id: player_data} after normalization
    if not legacy_data or not isinstance(legacy_data, dict):
        return new_data if new_data else {}
    if not new_data or not isinstance(new_data, dict):
        return legacy_data
    
    # Start with legacy players (flat dict format)
    legacy_players = legacy_data
    new_players = new_data
    
    merged = {}
    
    # Add all legacy players
    for player_id, player_data in legacy_players.items():
        if isinstance(player_data, dict):
            merged[player_id] = player_data.copy()
    
    # Merge with new players (new data takes precedence for conflicts)
    for player_id, player_data in new_players.items():
        if not isinstance(player_data, dict):
            continue
            
        if player_id in merged:
            # Merge: combine reference frames, keep newer updated_at
            legacy_player = merged[player_id]
            new_player = player_data
            
            # Merge reference frames (avoid duplicates)
            legacy_refs = legacy_player.get("reference_frames", [])
            new_refs = new_player.get("reference_frames", [])
            
            # Create a set of unique reference frames based on video_path and frame_num
            ref_set = {}
            for ref in legacy_refs:
                key = (ref.get("video_path"), ref.get("frame_num"))
                ref_set[key] = ref
            for ref in new_refs:
                key = (ref.get("video_path"), ref.get("frame_num"))
                ref_set[key] = ref  # New refs overwrite old ones
            
            merged[player_id]["reference_frames"] = list(ref_set.values())
            
            # Merge uniform variants
            if "uniform_variants" in new_player:
                if "uniform_variants" not in merged[player_id]:
                    merged[player_id]["uniform_variants"] = {}
                if isinstance(new_player["uniform_variants"], dict):
                    merged[player_id]["uniform_variants"].update(new_player["uniform_variants"])
            
            # Use newer updated_at
            if "updated_at" in new_player:
                merged[player_id]["updated_at"] = new_player["updated_at"]
            
            # Merge other fields (new takes precedence)
            for key in ["features", "foot_features", "jersey_number", "team", "dominant_color"]:
                if key in new_player and new_player[key] is not None:
                    merged[player_id][key] = new_player[key]
        else:
            # New player, add it
            merged[player_id] = player_data.copy()
    
    return merged


def migrate_player_gallery(merge=False, target_path=None):
    """
    Migrate player gallery data from legacy to refactored version
    
    Args:
        merge: If True, merge with existing gallery. If False, overwrite.
        target_path: Target path for gallery file (default: player_gallery.json in root)
    """
    print("=" * 60)
    print("Player Gallery Migration Tool")
    print("=" * 60)
    
    # Find all gallery files
    gallery_files = find_legacy_gallery_files()
    
    if not gallery_files:
        print("No player_gallery.json files found!")
        return False
    
    print(f"\nFound {len(gallery_files)} gallery file(s):")
    for i, (location, path) in enumerate(gallery_files, 1):
        print(f"  {i}. {location}: {path}")
    
    # Determine target path
    if target_path is None:
        target_path = "player_gallery.json"
    
    target_path = Path(target_path)
    
    # Load target gallery if it exists and merge is enabled
    target_data = None
    if target_path.exists() and merge:
        print(f"\nLoading existing gallery: {target_path}")
        target_data = load_gallery_file(str(target_path))
        if target_data:
            print(f"  Found {len(target_data.get('players', {}))} existing players")
    
    # Load the largest/most recent legacy gallery
    print("\nSelecting source gallery file...")
    best_file = None
    best_size = 0
    
    for location, path in gallery_files:
        data = load_gallery_file(path)
        if data and isinstance(data, dict):
            # Count players (flat dict format)
            player_count = len([k for k, v in data.items() if isinstance(v, dict) and ("name" in v or "features" in v)])
            if player_count > best_size:
                best_size = player_count
                best_file = (location, path, data)
    
    if not best_file:
        print("Error: Could not load any gallery files!")
        return False
    
    location, _source_path, source_data = best_file
    print(f"  Selected: {location} ({best_size} players)")
    
    # Merge or use source data
    if target_data and merge:
        print("\nMerging galleries...")
        final_data = merge_galleries(source_data, target_data)
        print(f"  Merged: {len(final_data)} total players")
    else:
        final_data = source_data
        print(f"\nUsing source gallery: {len(final_data)} players")
    
    # Create backup of target if it exists
    if target_path.exists():
        backup_path = target_path.with_suffix(f".json.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        print(f"\nCreating backup: {backup_path}")
        shutil.copy2(target_path, backup_path)
    
    # Save to target location
    print(f"\nSaving gallery to: {target_path}")
    try:
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        print(f"  ✓ Successfully saved {len(final_data)} players")
        
        # Also save to soccer_analysis directory if different
        sa_path = Path("soccer_analysis/player_gallery.json")
        if sa_path != target_path and sa_path.parent.exists():
            print(f"\nAlso saving to: {sa_path}")
            with open(sa_path, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)
            print(f"  ✓ Successfully saved to soccer_analysis directory")
        
        # Verify the file can be loaded by the new version
        print("\nVerifying migration...")
        try:
            from soccer_analysis.models.player_gallery import PlayerGallery
            test_gallery = PlayerGallery(gallery_path=str(target_path))
            print(f"  ✓ Successfully loaded {len(test_gallery.players)} players with new PlayerGallery class")
        except Exception as e:
            print(f"  ⚠ Warning: Could not verify with new PlayerGallery class: {e}")
            print("  The file was saved, but there may be compatibility issues.")
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\nError saving gallery: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    import sys
    
    merge = "--merge" in sys.argv or "-m" in sys.argv
    
    if "--help" in sys.argv or "-h" in sys.argv:
        print("""
Player Gallery Migration Tool

Usage:
    python migrate_player_gallery.py [options]

Options:
    --merge, -m    Merge with existing gallery instead of overwriting
    --help, -h     Show this help message

This tool migrates player gallery data from the legacy version to the
new refactored version. It will:
1. Find all player_gallery.json files
2. Select the one with the most players
3. Save it to the target location (player_gallery.json in root)
4. Optionally merge with existing gallery if --merge is specified
        """)
        return
    
    success = migrate_player_gallery(merge=merge)
    
    if success:
        print("\nYou can now use the refactored version with your player gallery data.")
    else:
        print("\nMigration failed. Please check the error messages above.")


if __name__ == "__main__":
    main()

