#!/usr/bin/env python3
"""
Analyze PlayerTagsSeed JSON file to extract player tagging information
"""

import json
from collections import defaultdict
import sys

def analyze_anchor_frames(json_path):
    """Analyze anchor frames and extract player information"""
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    anchors = data.get('anchor_frames', {})
    approved_mappings = data.get('approved_mappings', {})
    
    # Collect player statistics from anchor frames
    player_stats = defaultdict(lambda: {
        'frames': [],
        'track_ids': set(),
        'teams': set(),
        'bboxes': [],
        'count': 0
    })
    
    # Process anchor frames
    for frame_num_str, frame_anchors in anchors.items():
        frame_num = int(frame_num_str)
        for anchor in frame_anchors:
            player_name = anchor.get('player_name')
            if player_name:
                stats = player_stats[player_name]
                stats['frames'].append(frame_num)
                stats['track_ids'].add(anchor.get('track_id'))
                stats['teams'].add(anchor.get('team', 'Unknown'))
                stats['bboxes'].append(anchor.get('bbox'))
                stats['count'] += 1
    
    # Print analysis
    print("=" * 80)
    print("PLAYER ANCHOR FRAME ANALYSIS")
    print("=" * 80)
    print(f"\nTotal anchor frames: {len(anchors)}")
    print(f"Total player tags: {sum(len(frame_anchors) for frame_anchors in anchors.values())}")
    print(f"Unique players tagged: {len(player_stats)}")
    print(f"\nApproved mappings (track_id -> [player_name, team]): {len(approved_mappings)}")
    print("\n" + "=" * 80)
    print("PLAYER DETAILS:")
    print("=" * 80 + "\n")
    
    for name, stats in sorted(player_stats.items()):
        print(f"Player: {name}")
        print(f"  Total tags: {stats['count']}")
        print(f"  Frame range: {min(stats['frames'])} to {max(stats['frames'])}")
        print(f"  Track IDs assigned: {sorted(stats['track_ids'])}")
        print(f"  Teams: {sorted(stats['teams'])}")
        print(f"  Confidence: 1.00 (all anchor frames)")
        
        # Check bbox validity
        valid_bboxes = [b for b in stats['bboxes'] if b and len(b) == 4 and all(isinstance(x, (int, float)) for x in b)]
        print(f"  Valid bboxes: {len(valid_bboxes)}/{len(stats['bboxes'])}")
        
        # Check for track ID consistency
        if len(stats['track_ids']) > 1:
            print(f"  ⚠ WARNING: Player appears on multiple track IDs: {sorted(stats['track_ids'])}")
        
        print()
    
    # Print approved mappings
    print("=" * 80)
    print("APPROVED MAPPINGS (Track ID -> Player):")
    print("=" * 80 + "\n")
    for track_id, mapping in sorted(approved_mappings.items(), key=lambda x: int(x[0])):
        player_name, team = mapping
        print(f"Track {track_id}: {player_name} ({team})")
    
    # Check for conflicts
    print("\n" + "=" * 80)
    print("CONFLICT ANALYSIS:")
    print("=" * 80 + "\n")
    
    # Check if same track_id has multiple players in anchor frames
    track_to_players = defaultdict(set)
    for frame_anchors in anchors.values():
        for anchor in frame_anchors:
            track_id = anchor.get('track_id')
            player_name = anchor.get('player_name')
            if track_id is not None and player_name:
                track_to_players[track_id].add(player_name)
    
    conflicts = {tid: players for tid, players in track_to_players.items() if len(players) > 1}
    if conflicts:
        print("⚠ TRACK ID CONFLICTS (same track_id assigned to multiple players):")
        for track_id, players in sorted(conflicts.items()):
            print(f"  Track {track_id}: {sorted(players)}")
    else:
        print("✓ No track ID conflicts found")
    
    # Check if players appear on multiple track IDs
    multi_track_players = {name: stats['track_ids'] for name, stats in player_stats.items() 
                          if len(stats['track_ids']) > 1}
    if multi_track_players:
        print("\n⚠ PLAYERS ON MULTIPLE TRACK IDs:")
        for name, track_ids in sorted(multi_track_players.items()):
            print(f"  {name}: Tracks {sorted(track_ids)}")
    else:
        print("\n✓ No players appear on multiple track IDs")
    
    return player_stats, approved_mappings

if __name__ == "__main__":
    json_path = r"C:\Users\nerdw\Downloads\PlayerTagsSeed-20251001_184229.json"
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    
    try:
        analyze_anchor_frames(json_path)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

