"""
Convert existing player tags (player_mappings) to anchor frames at strategic intervals.
This preserves all existing tags while creating minimal anchor frames for protection.

Usage:
    python convert_existing_tags_to_anchors.py PlayerTagsSeed-video.json [--interval 150] [--max-per-track 10]
"""

import json
import os
import sys
import argparse
from collections import defaultdict


def convert_tags_to_anchors(input_file, output_file=None, frame_interval=150, max_anchors_per_track=10):
    """
    Convert existing player_mappings to anchor frames at strategic intervals.
    
    Args:
        input_file: Path to PlayerTagsSeed JSON file
        output_file: Output file path (default: overwrites input)
        frame_interval: Create anchor frame every N frames (default: 150, matches protection window)
        max_anchors_per_track: Maximum anchor frames per track (default: 10)
    
    Returns:
        Path to output file
    """
    if not os.path.exists(input_file):
        print(f"❌ Error: File not found: {input_file}")
        return None
    
    # Load existing file
    print(f"📖 Loading: {os.path.basename(input_file)}")
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Get player mappings
    player_mappings = data.get("player_mappings", {})
    if not player_mappings:
        print("⚠ No player_mappings found in file. Nothing to convert.")
        return None
    
    print(f"✓ Found {len(player_mappings)} player tag(s)")
    
    # Get existing anchor frames (we'll merge with new ones)
    existing_anchors = data.get("anchor_frames", {})
    if existing_anchors is None:
        existing_anchors = {}
    if not isinstance(existing_anchors, dict):
        existing_anchors = {}
    existing_anchor_count = sum(len(anchors) for anchors in existing_anchors.values() if anchors is not None and isinstance(anchors, list))
    
    if existing_anchor_count > 0:
        print(f"ℹ Found {existing_anchor_count} existing anchor frame(s) - will merge with new ones")
    
    # Load player_roster to check active status
    player_roster = data.get("player_roster", {})
    if player_roster:
        active_count = sum(1 for p in player_roster.values() if isinstance(p, dict) and p.get('active', True))
        inactive_count = len(player_roster) - active_count
        if inactive_count > 0:
            print(f"ℹ Found {inactive_count} inactive player(s) in roster - will skip them")
    
    # We need to know which frames each track appears in
    # Since we don't have CSV data, we'll create anchors at strategic intervals
    # based on the protection window (frame_interval)
    
    # Group tracks by player name (one player may have multiple track IDs due to ID switches)
    # This way we create anchors per PLAYER, not per track, which is much more efficient
    players_to_tracks = {}  # player_name -> list of (track_id, team, jersey)
    
    for track_id_str, mapping in player_mappings.items():
        try:
            track_id = int(track_id_str)
        except (ValueError, TypeError):
            continue
        
        # Extract player info from mapping
        if isinstance(mapping, list) and len(mapping) >= 1:
            player_name = mapping[0]
            team = mapping[1] if len(mapping) > 1 else ""
            jersey = mapping[2] if len(mapping) > 2 else None
        elif isinstance(mapping, tuple):
            player_name = mapping[0] if len(mapping) > 0 else ""
            team = mapping[1] if len(mapping) > 1 else ""
            jersey = mapping[2] if len(mapping) > 2 else None
        else:
            player_name = str(mapping)
            team = ""
            jersey = None
        
        if not player_name or not player_name.strip():
            continue
        
        # CRITICAL: Skip inactive players from roster
        if player_roster and player_name in player_roster:
            player_data = player_roster[player_name]
            if isinstance(player_data, dict):
                if not player_data.get('active', True):
                    # Skip inactive players - don't create anchor frames for them
                    continue
        
        # Group by player name
        if player_name not in players_to_tracks:
            players_to_tracks[player_name] = []
        players_to_tracks[player_name].append((track_id, team, jersey))
    
    # For each PLAYER (not each track), create anchor frames at strategic intervals
    # This prevents creating hundreds of anchors when a player has many track IDs
    new_anchors = {}
    players_processed = 0
    
    for player_name, track_list in players_to_tracks.items():
        # Use the first track ID as the primary one (or we could use the most common)
        primary_track_id, team, jersey = track_list[0]
        
        # Create anchor frames at strategic intervals for this PLAYER
        # We'll create them at frame_interval spacing, starting from frame 0
        anchors_created = 0
        frame_num = 0
        
        while anchors_created < max_anchors_per_track:
            frame_str = str(frame_num)
            
            # Create anchor entry (use primary track ID, but protection will work for all tracks of this player)
            anchor_entry = {
                "track_id": primary_track_id,
                "player_name": player_name,
                "team": team,
                "jersey_number": jersey,
                "bbox": None,  # Will be filled during analysis if available
                "confidence": 1.00
            }
            
            # Add to anchor frames
            if frame_str not in new_anchors:
                new_anchors[frame_str] = []
            
            # Check if already exists (from existing anchors or previous iteration)
            exists = False
            for existing in new_anchors[frame_str]:
                if existing.get("player_name") == player_name:
                    exists = True
                    break
            
            if not exists:
                new_anchors[frame_str].append(anchor_entry)
                anchors_created += 1
            
            frame_num += frame_interval
        
        players_processed += 1
        num_tracks = len(track_list)
        track_info = f"Track #{primary_track_id}" if num_tracks == 1 else f"{num_tracks} tracks (primary: #{primary_track_id})"
        print(f"  ✓ {player_name} ({track_info}): Created {anchors_created} anchor frame(s)")
    
    # Merge with existing anchors
    for frame_str, anchors in existing_anchors.items():
        if frame_str not in new_anchors:
            new_anchors[frame_str] = []
        
        # Add existing anchors (avoid duplicates)
        for existing_anchor in anchors:
            track_id = existing_anchor.get("track_id")
            if track_id is not None:
                # Check if we already have an anchor for this track at this frame
                exists = False
                for new_anchor in new_anchors[frame_str]:
                    if new_anchor.get("track_id") == track_id:
                        exists = True
                        break
                
                if not exists:
                    new_anchors[frame_str].append(existing_anchor)
    
    # Update data
    data["anchor_frames"] = new_anchors
    
    # Count total anchors
    total_anchors = sum(len(anchors) for anchors in new_anchors.values())
    total_frames = len(new_anchors)
    
    # Save to output file
    if output_file is None:
        output_file = input_file  # Overwrite input
    
    print(f"\n💾 Saving to: {os.path.basename(output_file)}")
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=4)
    
    print(f"✅ Success!")
    print(f"   • Processed {players_processed} player(s)")
    print(f"   • Created {total_anchors} total anchor frame(s) in {total_frames} frames")
    print(f"   • Frame interval: {frame_interval} (anchor spacing)")
    print(f"   • Max per track: {max_anchors_per_track}")
    print(f"\n🛡️ Protection: Each anchor protects ±150 frames during analysis")
    print(f"   (Frame interval {frame_interval} is the spacing between anchors, not the protection window)")
    print(f"   This should provide coverage throughout the video!")
    
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Convert existing player tags to anchor frames at strategic intervals"
    )
    parser.add_argument("input_file", help="Path to PlayerTagsSeed JSON file")
    parser.add_argument("-o", "--output", help="Output file path (default: overwrites input)")
    parser.add_argument("-i", "--interval", type=int, default=150,
                       help="Frame interval for anchor frames (default: 150, matches protection window)")
    parser.add_argument("-m", "--max-per-track", type=int, default=10,
                       help="Maximum anchor frames per track (default: 10)")
    
    args = parser.parse_args()
    
    convert_tags_to_anchors(
        args.input_file,
        args.output,
        args.interval,
        args.max_per_track
    )


if __name__ == "__main__":
    main()

