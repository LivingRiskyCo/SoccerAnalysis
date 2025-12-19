"""
Clear all seed configuration files
This script clears:
- seed_config.json (main seed config)
- All PlayerTagsSeed*.json files in video directories
- Optionally clears backup files in setup_wizard_backups/
"""

import os
import json
import glob
from pathlib import Path

def clear_seed_configs(clear_backups=False):
    """Clear all seed configuration files"""
    
    cleared_files = []
    
    # 1. Clear main seed_config.json
    seed_config_path = "seed_config.json"
    if os.path.exists(seed_config_path):
        try:
            # Create empty seed config
            empty_config = {
                "player_mappings": {},
                "rejected_ids": [],
                "merged_ids": {},
                "ball_positions": []
            }
            with open(seed_config_path, 'w') as f:
                json.dump(empty_config, f, indent=4)
            cleared_files.append(seed_config_path)
            print(f"✓ Cleared: {seed_config_path}")
        except Exception as e:
            print(f"✗ Error clearing {seed_config_path}: {e}")
    else:
        print(f"ℹ Not found: {seed_config_path}")
    
    # 2. Find and clear all PlayerTagsSeed*.json files
    # Search in current directory and common video directories
    search_paths = [
        ".",  # Current directory
        "../Videos",  # Parent Videos directory
        "Videos",  # Videos in current directory
    ]
    
    # Also search in subdirectories
    for search_path in search_paths:
        if os.path.exists(search_path):
            # Find all PlayerTagsSeed*.json files
            pattern = os.path.join(search_path, "**", "PlayerTagsSeed*.json")
            seed_files = glob.glob(pattern, recursive=True)
            
            for seed_file in seed_files:
                try:
                    # Create empty seed file
                    empty_seed = {
                        "player_tags": {},
                        "ball_positions": []
                    }
                    with open(seed_file, 'w') as f:
                        json.dump(empty_seed, f, indent=4)
                    cleared_files.append(seed_file)
                    print(f"✓ Cleared: {seed_file}")
                except Exception as e:
                    print(f"✗ Error clearing {seed_file}: {e}")
    
    # 3. Optionally clear backup files
    if clear_backups:
        backup_dir = "setup_wizard_backups"
        if os.path.exists(backup_dir):
            backup_files = glob.glob(os.path.join(backup_dir, "seed_config_backup_*.json"))
            for backup_file in backup_files:
                try:
                    os.remove(backup_file)
                    cleared_files.append(backup_file)
                    print(f"✓ Deleted backup: {backup_file}")
                except Exception as e:
                    print(f"✗ Error deleting {backup_file}: {e}")
        else:
            print(f"ℹ Backup directory not found: {backup_dir}")
    
    return cleared_files

if __name__ == "__main__":
    print("=" * 60)
    print("Clear All Seed Configurations")
    print("=" * 60)
    print()
    
    # Ask about backups
    clear_backups = input("Also delete backup files in setup_wizard_backups/? (y/n): ").lower().strip() == 'y'
    
    print()
    print("Clearing seed configs...")
    print()
    
    cleared = clear_seed_configs(clear_backups=clear_backups)
    
    print()
    print("=" * 60)
    print(f"✓ Cleared {len(cleared)} seed configuration file(s)")
    print("=" * 60)
    print()
    print("All seed configs have been cleared:")
    print("  - seed_config.json → Empty config")
    print("  - PlayerTagsSeed*.json files → Empty seed files")
    if clear_backups:
        print("  - Backup files → Deleted")
    print()
    print("You can now start fresh with new seed configurations.")

