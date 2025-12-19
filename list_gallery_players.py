"""List players in the gallery"""
import json
import os

gallery_path = "player_gallery.json"
if os.path.exists(gallery_path):
    with open(gallery_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Gallery has {len(data)} players:")
    for player_id, profile in sorted(data.items()):
        name = profile.get('name', 'Unknown')
        jersey = profile.get('jersey_number', '?')
        team = profile.get('team', '?')
        ref_frames = len(profile.get('reference_frames', []))
        print(f"  - {name} (Jersey: {jersey}, Team: {team}, {ref_frames} ref frames)")
else:
    print(f"Gallery file not found: {gallery_path}")



