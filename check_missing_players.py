#!/usr/bin/env python3
"""Check for missing players in anchor frames"""

import json
import sys

json_path = r"C:\Users\nerdw\Downloads\PlayerTagsSeed-20251001_184229.json"

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

anchors = data.get('anchor_frames', {})
approved_mappings = data.get('approved_mappings', {})

# Search for players
all_players = set()
for frame_anchors in anchors.values():
    for anchor in frame_anchors:
        player_name = anchor.get('player_name', '')
        if player_name:
            all_players.add(player_name)

print("All players found in anchor frames:")
for p in sorted(all_players):
    print(f"  - {p}")

print("\nSearching for specific players:")
target_players = ['Rocco', 'Ellie', 'James', 'Cameron']
for target in target_players:
    found = [p for p in all_players if target.lower() in p.lower()]
    if found:
        print(f"  {target}: FOUND - {found}")
    else:
        print(f"  {target}: NOT FOUND")

# Check approved mappings
print("\nApproved mappings:")
for track_id, mapping in sorted(approved_mappings.items(), key=lambda x: int(x[0])):
    player_name, team = mapping
    print(f"  Track {track_id}: {player_name} ({team})")
