"""
Clear Anchor Frames Utility

This script helps you remove anchor frames to start fresh with analysis.
It can:
1. Delete PlayerTagsSeed JSON files
2. Clear anchor frames from seed_config.json
3. Backup files before deletion (optional)
"""

import os
import json
import shutil
from pathlib import Path
import sys


def find_anchor_frame_files(directory):
    """Find all PlayerTagsSeed JSON files in directory and subdirectories"""
    anchor_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.startswith("PlayerTagsSeed-") and file.endswith(".json"):
                anchor_files.append(os.path.join(root, file))
    return anchor_files


def clear_seed_config_anchor_frames(seed_config_path):
    """Clear anchor_frames from seed_config.json but keep other data"""
    try:
        if not os.path.exists(seed_config_path):
            return False
        
        with open(seed_config_path, 'r') as f:
            data = json.load(f)
        
        if 'anchor_frames' in data:
            # Backup original
            backup_path = seed_config_path + ".backup"
            shutil.copy2(seed_config_path, backup_path)
            print(f"  ✓ Backed up to: {backup_path}")
            
            # Clear anchor frames
            data['anchor_frames'] = {}
            
            # Save
            with open(seed_config_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        return False
    except Exception as e:
        print(f"  ⚠ Error clearing seed_config.json: {e}")
        return False


def clear_anchor_frames(video_directory=None, backup=True):
    """
    Clear all anchor frames from the specified directory.
    
    Args:
        video_directory: Directory to search for anchor frame files (default: current directory)
        backup: Whether to create backups before deletion
    """
    if video_directory is None:
        video_directory = os.getcwd()
    
    print(f"🗑️  Clearing anchor frames from: {video_directory}")
    print()
    
    # Find all PlayerTagsSeed files
    anchor_files = find_anchor_frame_files(video_directory)
    
    if not anchor_files:
        print("✓ No anchor frame files found")
        return
    
    print(f"Found {len(anchor_files)} anchor frame file(s):")
    for f in anchor_files:
        file_size = os.path.getsize(f) / (1024 * 1024)  # Size in MB
        print(f"  • {os.path.basename(f)} ({file_size:.2f} MB)")
    print()
    
    # Ask for confirmation
    if backup:
        print("⚠ This will DELETE all anchor frame files!")
        print("  (Backups will be created if backup=True)")
    else:
        print("⚠ This will PERMANENTLY DELETE all anchor frame files!")
        print("  (No backups will be created)")
    
    response = input("\nContinue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Cancelled.")
        return
    
    # Process files
    deleted_count = 0
    backed_up_count = 0
    
    for anchor_file in anchor_files:
        try:
            if backup:
                # Create backup
                backup_file = anchor_file + ".backup"
                shutil.copy2(anchor_file, backup_file)
                backed_up_count += 1
                print(f"  ✓ Backed up: {os.path.basename(anchor_file)}")
            
            # Delete file
            os.remove(anchor_file)
            deleted_count += 1
            print(f"  ✓ Deleted: {os.path.basename(anchor_file)}")
        except Exception as e:
            print(f"  ⚠ Error processing {os.path.basename(anchor_file)}: {e}")
    
    # Also check for seed_config.json
    seed_config_path = os.path.join(video_directory, "seed_config.json")
    if os.path.exists(seed_config_path):
        print(f"\n📄 Found seed_config.json, clearing anchor_frames from it...")
        if clear_seed_config_anchor_frames(seed_config_path):
            print(f"  ✓ Cleared anchor_frames from seed_config.json")
    
    print(f"\n✅ Done!")
    print(f"   Deleted: {deleted_count} file(s)")
    if backup:
        print(f"   Backed up: {backed_up_count} file(s)")
    print(f"\n💡 Next steps:")
    print(f"   1. Run analysis WITHOUT anchor frames (faster!)")
    print(f"   2. After analysis completes, use 'Track Review & Assign' tool")
    print(f"   3. Assign player names to tracks")
    print(f"   4. Save as anchor frames (creates new, optimized anchor frames)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clear anchor frames to start fresh")
    parser.add_argument("--directory", "-d", help="Directory to search for anchor frames", default=None)
    parser.add_argument("--no-backup", action="store_true", help="Don't create backups (dangerous!)")
    args = parser.parse_args()
    
    clear_anchor_frames(
        video_directory=args.directory,
        backup=not args.no_backup
    )

