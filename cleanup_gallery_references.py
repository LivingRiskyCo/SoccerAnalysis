"""
Cleanup script for player gallery reference frames
Removes excessive reference frames to reduce gallery file size
Works directly with JSON to avoid import dependencies
"""

import os
import json
import shutil
from datetime import datetime

def cleanup_gallery(max_frames_per_player=120, auto_confirm=False, quality_based=True):
    """
    Clean up reference frames in the player gallery
    
    Args:
        max_frames_per_player: Maximum reference frames to keep per player (default: 120)
        auto_confirm: If True, skip confirmation prompt
        quality_based: If True, keep highest quality frames. If False, keep most recent.
    """
    gallery_path = "player_gallery.json"
    
    if not os.path.exists(gallery_path):
        print(f"ERROR: Gallery file not found: {gallery_path}")
        return False
    
    print("=" * 60)
    print("CLEANING UP PLAYER GALLERY REFERENCE FRAMES")
    print("=" * 60)
    print(f"   -> Maximum reference frames per player: {max_frames_per_player}")
    print(f"   -> Quality-based filtering: {'Yes (keeps highest quality)' if quality_based else 'No (keeps most recent)'}")
    print(f"   -> Gallery file: {gallery_path}")
    print()
    
    # Load gallery
    try:
        with open(gallery_path, 'r', encoding='utf-8') as f:
            gallery_data = json.load(f)
        print(f"OK Loaded gallery with {len(gallery_data)} players")
    except Exception as e:
        print(f"ERROR: Error loading gallery: {e}")
        return False
    
    # Count current reference frames
    total_refs = 0
    players_with_refs = {}
    for player_id, profile in gallery_data.items():
        if 'reference_frames' in profile and profile['reference_frames']:
            count = len(profile['reference_frames'])
            total_refs += count
            players_with_refs[player_id] = {
                'name': profile.get('name', 'Unknown'),
                'count': count
            }
    
    print(f"\nCurrent Status:")
    print(f"   -> Total reference frames: {total_refs}")
    print(f"   -> Players with reference frames: {len(players_with_refs)}")
    print(f"\n   Reference frame counts per player:")
    for player_id, info in sorted(players_with_refs.items(), key=lambda x: x[1]['count'], reverse=True):
        print(f"      - {info['name']}: {info['count']} frames")
    
    # Calculate how many will be removed
    total_to_remove = 0
    for player_id, info in players_with_refs.items():
        if info['count'] > max_frames_per_player:
            total_to_remove += info['count'] - max_frames_per_player
    
    if total_to_remove == 0:
        print(f"\nOK No cleanup needed - all players have <= {max_frames_per_player} reference frames")
        return True
    
    print(f"\nCleanup Plan:")
    print(f"   -> Will remove: {total_to_remove} reference frames")
    print(f"   -> Will keep: {total_refs - total_to_remove} reference frames")
    print(f"   -> Reduction: {total_to_remove / total_refs * 100:.1f}%")
    
    # Ask for confirmation (unless auto_confirm is True)
    if not auto_confirm:
        try:
            response = input(f"\nProceed with cleanup? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("Cleanup cancelled")
                return False
        except (EOFError, KeyboardInterrupt):
            print("\nCleanup cancelled (no input available)")
            return False
    else:
        print(f"\nAuto-confirming cleanup...")
    
    # Create backup
    backup_path = gallery_path + f".backup_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        shutil.copy2(gallery_path, backup_path)
        print(f"OK Created backup: {backup_path}")
    except Exception as e:
        print(f"WARNING: Could not create backup: {e}")
        response = input("Continue without backup? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Cleanup cancelled")
            return False
    
    # Perform cleanup
    print(f"\nCleaning up reference frames...")
    total_removed = 0
    
    if quality_based:
        # Quality-based cleanup: score frames and keep highest quality
        for player_id, profile in gallery_data.items():
            if 'reference_frames' in profile and profile['reference_frames']:
                ref_frames = profile['reference_frames']
                if len(ref_frames) > max_frames_per_player:
                    # Score each frame by quality
                    scored_frames = []
                    for ref_frame in ref_frames:
                        score = 0.0
                        # Priority 1: Similarity score (if available)
                        if 'similarity' in ref_frame:
                            score += ref_frame['similarity'] * 100.0
                        # Priority 2: Confidence score (if available)
                        if 'confidence' in ref_frame:
                            score += ref_frame['confidence'] * 50.0
                        # Priority 3: Has bbox (complete reference frame)
                        if 'bbox' in ref_frame and ref_frame['bbox']:
                            score += 5.0
                        # Priority 4: Recency (small boost)
                        if 'frame_num' in ref_frame:
                            score += 1.0
                        scored_frames.append((score, ref_frame))
                    
                    # Sort by score and keep top max_frames_per_player
                    scored_frames.sort(key=lambda x: x[0], reverse=True)
                    profile['reference_frames'] = [frame for _, frame in scored_frames[:max_frames_per_player]]
                    
                    removed = len(ref_frames) - max_frames_per_player
                    total_removed += removed
                    player_name = profile.get('name', 'Unknown')
                    print(f"   - {player_name}: Removed {removed} lower-quality frames (kept {max_frames_per_player} highest quality)")
    else:
        # Recency-based cleanup: keep most recent
        for player_id, profile in gallery_data.items():
            if 'reference_frames' in profile and profile['reference_frames']:
                ref_frames = profile['reference_frames']
                if len(ref_frames) > max_frames_per_player:
                    removed = len(ref_frames) - max_frames_per_player
                    # Keep the most recent frames (last max_frames_per_player)
                    profile['reference_frames'] = ref_frames[-max_frames_per_player:]
                    total_removed += removed
                    player_name = profile.get('name', 'Unknown')
                    print(f"   - {player_name}: Removed {removed} old reference frames (kept {max_frames_per_player} most recent)")
    
    if total_removed > 0:
        print(f"OK Cleaned up {total_removed} reference frames total")
        
        # Save cleaned gallery
        try:
            with open(gallery_path, 'w', encoding='utf-8') as f:
                json.dump(gallery_data, f, indent=2)
            print(f"OK Saved cleaned gallery to: {gallery_path}")
        except Exception as e:
            print(f"ERROR: Could not save cleaned gallery: {e}")
            return False
    else:
        print("OK No cleanup needed")
    
    # Show results
    print(f"\nAfter Cleanup:")
    total_refs_after = 0
    for player_id, profile in gallery_data.items():
        if 'reference_frames' in profile and profile['reference_frames']:
            total_refs_after += len(profile['reference_frames'])
    
    print(f"   -> Total reference frames: {total_refs_after} (was {total_refs})")
    print(f"   -> Removed: {total_refs - total_refs_after} frames")
    print(f"   -> File size reduction: ~{((total_refs - total_refs_after) * 200 / 1024):.1f} KB estimated")
    
    print(f"\nOK Cleanup complete!")
    print(f"   -> Backup saved to: {backup_path}")
    print(f"   -> Gallery saved to: {gallery_path}")
    
    return True


if __name__ == "__main__":
    import sys
    
    # Allow custom max frames via command line
    max_frames = 120
    auto_confirm = False
    quality_based = True
    
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg == '--yes' or arg == '-y':
                auto_confirm = True
            elif arg == '--recent' or arg == '-r':
                quality_based = False  # Use recency instead of quality
            else:
                try:
                    max_frames = int(arg)
                except ValueError:
                    print(f"WARNING: Invalid argument: {arg}. Using default max_frames: 120")
    
    cleanup_gallery(max_frames_per_player=max_frames, auto_confirm=auto_confirm, quality_based=quality_based)
