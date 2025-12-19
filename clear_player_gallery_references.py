"""
Clear all reference frames from player gallery
This removes Re-ID reference frames that may be corrupted from bad tracking.

Usage:
    python clear_player_gallery_references.py
"""

import json
import os
from pathlib import Path

def clear_reference_frames(gallery_path="player_gallery.json", backup=True):
    """
    Clear all reference frames from player gallery
    
    Args:
        gallery_path: Path to player_gallery.json
        backup: Whether to create a backup before clearing
    """
    if not os.path.exists(gallery_path):
        print(f"⚠ Gallery file not found: {gallery_path}")
        return False
    
    # Load gallery
    try:
        with open(gallery_path, 'r') as f:
            gallery_data = json.load(f)
    except Exception as e:
        print(f"⚠ Error loading gallery: {e}")
        return False
    
    # Create backup
    if backup:
        backup_path = f"{gallery_path}.backup"
        try:
            with open(backup_path, 'w') as f:
                json.dump(gallery_data, f, indent=2)
            print(f"✓ Backup created: {backup_path}")
        except Exception as e:
            print(f"⚠ Could not create backup: {e}")
            response = input("Continue without backup? (y/n): ")
            if response.lower() != 'y':
                return False
    
    # Clear reference frames and uniform variants
    total_refs = 0
    players_cleared = 0
    
    for player_id, player_data in gallery_data.items():
        ref_count = 0
        
        # Count reference frames
        if 'reference_frames' in player_data and player_data['reference_frames']:
            ref_count = len(player_data['reference_frames'])
            total_refs += ref_count
            player_data['reference_frames'] = []
        
        # Clear uniform variants (they contain reference frames)
        if 'uniform_variants' in player_data and player_data['uniform_variants']:
            variant_count = sum(len(frames) for frames in player_data['uniform_variants'].values())
            total_refs += variant_count
            player_data['uniform_variants'] = {}
        
        if ref_count > 0:
            players_cleared += 1
            player_name = player_data.get('name', player_id)
            print(f"  • {player_name}: Cleared {ref_count} reference frame(s)")
    
    # Save updated gallery
    try:
        with open(gallery_path, 'w') as f:
            json.dump(gallery_data, f, indent=2)
        
        print(f"\n✓ Cleared {total_refs} reference frame(s) from {players_cleared} player(s)")
        print(f"✓ Gallery saved: {gallery_path}")
        
        if backup:
            print(f"\n💡 To restore backup: copy {backup_path} to {gallery_path}")
        
        return True
    except Exception as e:
        print(f"⚠ Error saving gallery: {e}")
        return False


if __name__ == "__main__":
    print("🧹 Clearing Player Gallery Reference Frames")
    print("=" * 50)
    
    # Find gallery file
    gallery_path = "player_gallery.json"
    if not os.path.exists(gallery_path):
        print(f"⚠ Gallery file not found: {gallery_path}")
        print("   → Looking in current directory...")
        print(f"   → Current directory: {os.getcwd()}")
        response = input("\nEnter gallery path (or press Enter to exit): ")
        if response:
            gallery_path = response
        else:
            exit(1)
    
    print(f"\n📁 Gallery file: {gallery_path}")
    
    # Confirm
    response = input("\n⚠ This will clear ALL reference frames from ALL players.\n   Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cancelled.")
        exit(0)
    
    # Clear reference frames
    success = clear_reference_frames(gallery_path, backup=True)
    
    if success:
        print("\n✅ Done! Player gallery reference frames cleared.")
        print("\n💡 Next steps:")
        print("   1. Start fresh analysis with minimal anchor frames")
        print("   2. Let the system rebuild clean reference frames")
        print("   3. Only tag frames when you're confident about player identity")
    else:
        print("\n❌ Failed to clear reference frames. Check errors above.")

