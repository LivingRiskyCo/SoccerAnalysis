"""
Script to clean the player gallery by removing players with no reference frames.

This is useful when players have been added to the gallery but never actually
appeared in any video, causing false matches during Re-ID.

Usage:
    python clean_player_gallery.py [--min-ref-frames N] [--dry-run]
    
Options:
    --min-ref-frames N   Minimum number of reference frames required (default: 1)
    --dry-run            Show what would be removed without actually removing
"""

import json
import sys
import os
from pathlib import Path


def clean_player_gallery(gallery_path="player_gallery.json", min_ref_frames=1, dry_run=False):
    """
    Remove players from gallery that have fewer than min_ref_frames reference frames.
    
    Args:
        gallery_path: Path to player gallery JSON file
        min_ref_frames: Minimum number of reference frames required (default: 1)
        dry_run: If True, only show what would be removed without actually removing
    
    Returns:
        Tuple of (players_removed, players_kept)
    """
    if not os.path.exists(gallery_path):
        print(f"❌ Gallery file not found: {gallery_path}")
        return None, None
    
    print(f"📖 Loading gallery: {gallery_path}")
    
    try:
        with open(gallery_path, 'r', encoding='utf-8') as f:
            gallery_data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading gallery: {e}")
        return None, None
    
    # Gallery structure: {player_id: {player_data}}
    # player_id is like 'anay_rao', 'gunnar_nesbitt', etc.
    players = gallery_data
    print(f"✓ Loaded {len(players)} players from gallery")
    
    players_to_remove = []
    players_to_keep = []
    
    for player_id, player_data in players.items():
        player_name = player_data.get('name', 'Unknown')
        ref_frames = player_data.get('reference_frames', [])
        num_ref_frames = len(ref_frames) if isinstance(ref_frames, list) else 0
        
        if num_ref_frames < min_ref_frames:
            players_to_remove.append((player_id, player_name, num_ref_frames))
        else:
            players_to_keep.append((player_id, player_name, num_ref_frames))
    
    print(f"\n📊 Gallery Analysis:")
    print(f"  Total players: {len(players)}")
    print(f"  Players with ≥{min_ref_frames} ref frames: {len(players_to_keep)}")
    print(f"  Players with <{min_ref_frames} ref frames: {len(players_to_remove)}")
    
    if players_to_remove:
        print(f"\n🗑️  Players to be removed (no reference frames):")
        for player_id, player_name, num_ref in players_to_remove:
            player_data = players[player_id]
            jersey = player_data.get('jersey_number', 'N/A')
            team = player_data.get('team', 'N/A')
            print(f"  - {player_name} (ID: {player_id}, Jersey: {jersey}, Team: {team}, Ref frames: {num_ref})")
    
    if players_to_keep:
        print(f"\n✓ Players to keep (have reference frames):")
        for player_id, player_name, num_ref in players_to_keep:
            jersey = players[player_id].get('jersey_number', 'N/A')
            team = players[player_id].get('team', 'N/A')
            print(f"  - {player_name} (ID: {player_id}, Jersey: {jersey}, Team: {team}, Ref frames: {num_ref})")
    
    if dry_run:
        print(f"\n🔍 DRY RUN: No changes made. Use without --dry-run to actually remove players.")
        return players_to_remove, players_to_keep
    
    if not players_to_remove:
        print(f"\n✓ No players to remove - gallery is clean!")
        return [], players_to_keep
    
    # Remove players
    print(f"\n🗑️  Removing {len(players_to_remove)} players from gallery...")
    for player_id, player_name, _ in players_to_remove:
        del players[player_id]
        print(f"  ✓ Removed: {player_name}")
    
    # Save cleaned gallery
    try:
        # Create backup
        backup_path = gallery_path + ".backup"
        if os.path.exists(gallery_path):
            import shutil
            shutil.copy2(gallery_path, backup_path)
            print(f"  💾 Created backup: {backup_path}")
        
        with open(gallery_path, 'w', encoding='utf-8') as f:
            json.dump(gallery_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Gallery cleaned successfully!")
        print(f"  - Removed: {len(players_to_remove)} players")
        print(f"  - Kept: {len(players_to_keep)} players")
        print(f"  - Backup saved to: {backup_path}")
        
        return players_to_remove, players_to_keep
        
    except Exception as e:
        print(f"❌ Error saving cleaned gallery: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def main():
    """Main entry point."""
    gallery_path = "player_gallery.json"
    min_ref_frames = 1
    dry_run = False
    
    # Parse arguments
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--min-ref-frames' and i + 1 < len(sys.argv):
            min_ref_frames = int(sys.argv[i + 1])
            i += 2
        elif arg == '--dry-run':
            dry_run = True
            i += 1
        elif arg == '--gallery' and i + 1 < len(sys.argv):
            gallery_path = sys.argv[i + 1]
            i += 2
        elif arg.startswith('--'):
            print(f"⚠ Unknown option: {arg}")
            i += 1
        else:
            gallery_path = arg
            i += 1
    
    print("🧹 Player Gallery Cleaner")
    print("=" * 50)
    
    removed, kept = clean_player_gallery(gallery_path, min_ref_frames, dry_run)
    
    if removed is None:
        sys.exit(1)
    
    if not dry_run and removed:
        print(f"\n✅ Success! Gallery has been cleaned.")
        print(f"   Next time you run analysis, only players with reference frames will be used for matching.")
    elif not removed:
        print(f"\n✓ Gallery is already clean - no players to remove.")


if __name__ == "__main__":
    main()

