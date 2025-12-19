#!/usr/bin/env python3
"""
Clear all player name/roster data files to start fresh.
This will backup existing files and create empty versions.
"""

import os
import json
import shutil
from datetime import datetime

def clear_player_data():
    """Clear all player data files and create backups"""
    
    # Files to clear
    files_to_clear = [
        "player_names.json",
        "player_roster.json",
        "player_teams.json",
        "player_name_list.json"
    ]
    
    # Create backup directory
    backup_dir = "player_data_backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("=" * 60)
    print("CLEARING PLAYER DATA FILES")
    print("=" * 60)
    print()
    
    cleared_count = 0
    for filename in files_to_clear:
        if os.path.exists(filename):
            # Create backup
            backup_filename = f"{timestamp}_{filename}"
            backup_path = os.path.join(backup_dir, backup_filename)
            shutil.copy2(filename, backup_path)
            print(f"[OK] Backed up: {filename} -> {backup_path}")
            
            # Clear the file (create empty JSON object)
            with open(filename, 'w') as f:
                json.dump({}, f, indent=2)
            print(f"[OK] Cleared: {filename}")
            cleared_count += 1
        else:
            print(f"[SKIP] Not found: {filename} (skipping)")
    
    print()
    print("=" * 60)
    print(f"COMPLETE: Cleared {cleared_count} file(s)")
    print(f"Backups saved to: {backup_dir}/")
    print("=" * 60)
    print()
    print("NOTE: PlayerTagsSeed files in video directories are NOT cleared.")
    print("      They will be loaded at startup but won't overwrite analysis-assigned names.")
    print()

if __name__ == "__main__":
    try:
        clear_player_data()
        input("Press Enter to exit...")
    except Exception as e:
        print(f"ERROR: {e}")
        input("Press Enter to exit...")

