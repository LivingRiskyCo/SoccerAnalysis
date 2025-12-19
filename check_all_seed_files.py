#!/usr/bin/env python3
"""Check all PlayerTagsSeed files for correct players"""

import json
import os
from pathlib import Path

downloads = Path.home() / "Downloads"
seed_files = list(downloads.glob("PlayerTagsSeed*.json"))

print("=" * 80)
print("CHECKING ALL PLAYERTAGSSEED FILES")
print("=" * 80)

for seed_file in seed_files:
    print(f"\nFile: {seed_file.name}")
    print(f"Modified: {os.path.getmtime(seed_file)}")
    
    try:
        with open(seed_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        anchors = data.get('anchor_frames', {})
        video_path = data.get('video_path', 'Unknown')
        
        # Get all players
        all_players = set()
        for frame_anchors in anchors.values():
            for anchor in frame_anchors:
                player_name = anchor.get('player_name', '')
                if player_name:
                    all_players.add(player_name)
        
        print(f"Video: {os.path.basename(video_path)}")
        print(f"Anchor frames: {len(anchors)}")
        print(f"Players found: {sorted(all_players)}")
        
        # Check for target players
        target_players = ['Rocco', 'Ellie', 'James', 'Cameron']
        found_targets = []
        for target in target_players:
            found = [p for p in all_players if target.lower() in p.lower()]
            if found:
                found_targets.extend(found)
        
        if found_targets:
            print(f"✓ Contains target players: {found_targets}")
        else:
            print("✗ Does NOT contain Rocco, Ellie, or James")
            
    except Exception as e:
        print(f"Error reading file: {e}")

