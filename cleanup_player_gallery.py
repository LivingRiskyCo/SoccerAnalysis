"""
Utility script to clean up the player gallery:
- Remove players with no reference frames
- Merge duplicate players
- Fix naming issues
"""

import sys
from player_gallery import PlayerGallery

def main():
    print("=" * 60)
    print("Player Gallery Cleanup Utility")
    print("=" * 60)
    
    # Load gallery
    gallery = PlayerGallery()
    print(f"\n✓ Loaded {len(gallery.players)} players from gallery")
    
    # Show current players
    print("\n📋 Current Players:")
    for player_id, profile in gallery.players.items():
        ref_count = len(profile.reference_frames) if profile.reference_frames else 0
        if profile.uniform_variants:
            for variant_refs in profile.uniform_variants.values():
                if variant_refs:
                    ref_count += len(variant_refs)
        if profile.foot_reference_frames:
            ref_count += len(profile.foot_reference_frames)
        print(f"   • {profile.name} (ID: {player_id}): {ref_count} reference frame(s)")
    
    # Step 1: Remove players with no reference frames
    print("\n" + "=" * 60)
    print("Step 1: Removing players with no reference frames...")
    print("=" * 60)
    removed_count, removed_names = gallery.remove_players_without_reference_frames(min_references=1)
    
    if removed_count > 0:
        print(f"\n✓ Removed {removed_count} player(s): {', '.join(removed_names)}")
    else:
        print("\n✓ No players removed - all players have reference frames")
    
    # Step 2: Find and merge duplicates
    print("\n" + "=" * 60)
    print("Step 2: Finding duplicate players...")
    print("=" * 60)
    
    # Group players by name (case-insensitive)
    name_groups = {}
    for player_id, profile in gallery.players.items():
        name_lower = profile.name.lower()
        if name_lower not in name_groups:
            name_groups[name_lower] = []
        name_groups[name_lower].append((player_id, profile))
    
    duplicates_found = []
    for name_lower, players in name_groups.items():
        if len(players) > 1:
            duplicates_found.append((name_lower, players))
            print(f"\n⚠ Found {len(players)} entries for '{players[0][1].name}':")
            for player_id, profile in players:
                ref_count = len(profile.reference_frames) if profile.reference_frames else 0
                if profile.uniform_variants:
                    for variant_refs in profile.uniform_variants.values():
                        if variant_refs:
                            ref_count += len(variant_refs)
                if profile.foot_reference_frames:
                    ref_count += len(profile.foot_reference_frames)
                print(f"   • ID: {player_id}, {ref_count} reference frame(s)")
    
    if duplicates_found:
        print(f"\n🔄 Merging {len(duplicates_found)} duplicate group(s)...")
        for name_lower, players in duplicates_found:
            # Sort by reference frame count (keep the one with most references)
            players_sorted = sorted(players, key=lambda x: (
                len(x[1].reference_frames) if x[1].reference_frames else 0,
                len(x[1].uniform_variants) if x[1].uniform_variants else 0
            ), reverse=True)
            
            # Keep the first one (most references), merge others into it
            target_id, target_profile = players_sorted[0]
            for source_id, source_profile in players_sorted[1:]:
                print(f"\n   Merging '{source_profile.name}' (ID: {source_id}) into '{target_profile.name}' (ID: {target_id})...")
                success = gallery.merge_duplicate_players(source_id, target_id)
                if success:
                    print(f"   ✓ Successfully merged")
                else:
                    print(f"   ✗ Merge failed")
    else:
        print("\n✓ No duplicate players found")
    
    # Final summary
    print("\n" + "=" * 60)
    print("Final Summary")
    print("=" * 60)
    print(f"✓ Gallery now contains {len(gallery.players)} player(s)")
    
    if len(gallery.players) > 0:
        print("\n📋 Remaining Players:")
        for player_id, profile in gallery.players.items():
            ref_count = len(profile.reference_frames) if profile.reference_frames else 0
            if profile.uniform_variants:
                for variant_refs in profile.uniform_variants.values():
                    if variant_refs:
                        ref_count += len(variant_refs)
            if profile.foot_reference_frames:
                ref_count += len(profile.foot_reference_frames)
            print(f"   • {profile.name} (ID: {player_id}): {ref_count} reference frame(s)")
    
    print("\n✓ Cleanup complete! Gallery saved to player_gallery.json")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Cleanup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

