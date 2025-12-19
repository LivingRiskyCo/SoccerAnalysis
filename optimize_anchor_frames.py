"""
Optimize Anchor Frames: Find and store strategic anchor points at occlusion points.

This script analyzes anchor frames to identify:
1. Anchor frames at occlusion points (where tracking is most likely to fail)
2. Key anchor frames per player (first appearance, high confidence, etc.)
3. Reduces anchor frame count while maintaining tracking quality
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np


def load_anchor_frames(anchor_file_path):
    """Load anchor frames from JSON file."""
    try:
        with open(anchor_file_path, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'anchor_frames' in data:
                return data['anchor_frames']
            elif isinstance(data, dict):
                # Direct frame mapping
                return data
            else:
                print(f"⚠ Unexpected anchor frame format in {anchor_file_path}")
                return {}
    except Exception as e:
        print(f"⚠ Error loading anchor frames: {e}")
        return {}


def detect_occlusion_points(anchor_frames, player_anchor_history):
    """
    Detect occlusion points by analyzing player movement patterns.
    
    Occlusion indicators:
    1. Player disappears and reappears (gap in anchor frames)
    2. Multiple players in same area (spatial clustering)
    3. Rapid position changes (velocity spikes)
    """
    occlusion_frames = set()
    player_positions = defaultdict(list)  # player_name -> [(frame, x, y), ...]
    
    # Collect player positions from anchor frames
    for frame_num_str, anchors in anchor_frames.items():
        try:
            frame_num = int(frame_num_str)
        except:
            continue
            
        for anchor in anchors:
            player_name = anchor.get('player_name')
            bbox = anchor.get('bbox')
            
            if player_name and bbox and len(bbox) >= 4:
                x1, y1, x2, y2 = bbox[:4]
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                player_positions[player_name].append((frame_num, center_x, center_y))
    
    # Sort positions by frame for each player
    for player_name in player_positions:
        player_positions[player_name].sort(key=lambda x: x[0])
    
    # Detect gaps (occlusions) - player disappears for multiple frames
    for player_name, positions in player_positions.items():
        if len(positions) < 2:
            continue
            
        for i in range(len(positions) - 1):
            frame1, x1, y1 = positions[i]
            frame2, x2, y2 = positions[i + 1]
            
            frame_gap = frame2 - frame1
            
            # Large gap indicates occlusion
            if frame_gap > 30:  # More than 1 second at 30fps
                # Mark frames around the gap as occlusion points
                occlusion_frames.add(frame1)  # Last frame before occlusion
                occlusion_frames.add(frame2)  # First frame after occlusion
                
                # Also mark frames in between if they exist
                for f in range(frame1 + 1, min(frame2, frame1 + 60)):
                    if str(f) in anchor_frames:
                        occlusion_frames.add(f)
    
    # Detect spatial clustering (multiple players close together)
    frame_player_positions = defaultdict(list)  # frame -> [(player, x, y), ...]
    
    for frame_num_str, anchors in anchor_frames.items():
        try:
            frame_num = int(frame_num_str)
        except:
            continue
            
        for anchor in anchors:
            player_name = anchor.get('player_name')
            bbox = anchor.get('bbox')
            
            if player_name and bbox and len(bbox) >= 4:
                x1, y1, x2, y2 = bbox[:4]
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                frame_player_positions[frame_num].append((player_name, center_x, center_y))
    
    # Find frames with multiple players in close proximity (potential occlusions)
    for frame_num, positions in frame_player_positions.items():
        if len(positions) < 2:
            continue
            
        # Check if any two players are very close (< 100 pixels)
        for i, (player1, x1, y1) in enumerate(positions):
            for j, (player2, x2, y2) in enumerate(positions[i+1:], i+1):
                distance = np.sqrt((x1 - x2)**2 + (y1 - y2)**2)
                if distance < 100:  # Very close - likely occlusion
                    occlusion_frames.add(frame_num)
                    break
    
    return occlusion_frames


def find_strategic_anchor_frames(anchor_frames, occlusion_frames):
    """
    Find strategic anchor frames to keep:
    1. Anchor frames at occlusion points
    2. First appearance of each player
    3. High-confidence anchor frames (confidence = 1.00)
    4. Anchor frames spaced every N frames (for coverage)
    """
    strategic_frames = set()
    player_first_appearance = {}  # player_name -> first_frame
    player_anchor_count = defaultdict(int)
    
    # Find first appearance and count anchors per player
    for frame_num_str in sorted(anchor_frames.keys(), key=int):
        frame_num = int(frame_num_str)
        anchors = anchor_frames[frame_num_str]
        
        for anchor in anchors:
            player_name = anchor.get('player_name')
            if player_name:
                if player_name not in player_first_appearance:
                    player_first_appearance[player_name] = frame_num
                player_anchor_count[player_name] += 1
    
    # Keep occlusion points
    strategic_frames.update(occlusion_frames)
    
    # Keep first appearance of each player
    for player_name, first_frame in player_first_appearance.items():
        strategic_frames.add(first_frame)
    
    # Keep high-confidence anchor frames (confidence = 1.00)
    for frame_num_str, anchors in anchor_frames.items():
        frame_num = int(frame_num_str)
        for anchor in anchors:
            confidence = anchor.get('confidence', 0.0)
            if confidence >= 1.0:
                strategic_frames.add(frame_num)
    
    # Keep anchor frames spaced every 60 frames (~2 seconds at 30fps) for coverage
    all_frames = sorted([int(f) for f in anchor_frames.keys()])
    if all_frames:
        last_kept = all_frames[0]
        strategic_frames.add(last_kept)
        
        for frame_num in all_frames[1:]:
            if frame_num - last_kept >= 60:  # At least 2 seconds apart
                strategic_frames.add(frame_num)
                last_kept = frame_num
    
    return strategic_frames


def optimize_anchor_frames(input_file, output_file=None, keep_all_occlusions=True):
    """
    Optimize anchor frames by keeping only strategic ones.
    
    Args:
        input_file: Path to input anchor frames JSON file
        output_file: Path to output optimized anchor frames (default: adds '_optimized' suffix)
        keep_all_occlusions: If True, keep all frames at occlusion points
    """
    print(f"📊 Optimizing anchor frames: {input_file}")
    
    # Load anchor frames
    anchor_frames = load_anchor_frames(input_file)
    if not anchor_frames:
        print(f"⚠ No anchor frames found in {input_file}")
        return None
    
    total_frames = len(anchor_frames)
    total_anchors = sum(len(anchors) for anchors in anchor_frames.values())
    print(f"   Original: {total_anchors} anchor tags across {total_frames} frames")
    
    # Detect occlusion points
    print(f"   Detecting occlusion points...")
    player_anchor_history = defaultdict(list)
    occlusion_frames = detect_occlusion_points(anchor_frames, player_anchor_history)
    print(f"   Found {len(occlusion_frames)} frames with occlusion indicators")
    
    # Find strategic anchor frames
    strategic_frames = find_strategic_anchor_frames(anchor_frames, occlusion_frames)
    print(f"   Identified {len(strategic_frames)} strategic frames to keep")
    
    # Build optimized anchor frames
    optimized_anchor_frames = {}
    optimized_count = 0
    
    for frame_num_str in strategic_frames:
        frame_num_str = str(frame_num_str)
        if frame_num_str in anchor_frames:
            optimized_anchor_frames[frame_num_str] = anchor_frames[frame_num_str]
            optimized_count += len(anchor_frames[frame_num_str])
    
    # Calculate reduction
    reduction = ((total_anchors - optimized_count) / total_anchors * 100) if total_anchors > 0 else 0
    print(f"   Optimized: {optimized_count} anchor tags across {len(optimized_anchor_frames)} frames")
    print(f"   Reduction: {reduction:.1f}% ({total_anchors - optimized_count} tags removed)")
    
    # Determine output file
    if output_file is None:
        input_path = Path(input_file)
        output_file = input_path.parent / f"{input_path.stem}_optimized{input_path.suffix}"
    
    # Load original file structure to preserve metadata
    try:
        with open(input_file, 'r') as f:
            original_data = json.load(f)
        
        # Preserve structure
        if isinstance(original_data, dict) and 'anchor_frames' in original_data:
            output_data = original_data.copy()
            output_data['anchor_frames'] = optimized_anchor_frames
            if 'video_path' in original_data:
                output_data['video_path'] = original_data['video_path']
        else:
            output_data = optimized_anchor_frames
    except:
        output_data = optimized_anchor_frames
    
    # Save optimized anchor frames
    try:
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"✅ Saved optimized anchor frames to: {output_file}")
        return str(output_file)
    except Exception as e:
        print(f"⚠ Error saving optimized anchor frames: {e}")
        return None


def store_occlusion_anchors_per_player(anchor_frames, occlusion_frames, output_file):
    """
    Store occlusion anchor points per player for efficient lookup.
    
    Structure:
    {
        "player_name": {
            "occlusion_frames": [frame1, frame2, ...],
            "anchors": {
                "frame1": [anchor_data, ...],
                "frame2": [anchor_data, ...]
            }
        }
    }
    """
    player_occlusion_data = defaultdict(lambda: {
        'occlusion_frames': [],
        'anchors': {}
    })
    
    for frame_num_str, anchors in anchor_frames.items():
        try:
            frame_num = int(frame_num_str)
        except:
            continue
            
        if frame_num not in occlusion_frames:
            continue
        
        for anchor in anchors:
            player_name = anchor.get('player_name')
            if player_name:
                if frame_num not in player_occlusion_data[player_name]['occlusion_frames']:
                    player_occlusion_data[player_name]['occlusion_frames'].append(frame_num)
                    player_occlusion_data[player_name]['anchors'][frame_num_str] = []
                
                player_occlusion_data[player_name]['anchors'][frame_num_str].append(anchor)
    
    # Sort occlusion frames for each player
    for player_name in player_occlusion_data:
        player_occlusion_data[player_name]['occlusion_frames'].sort()
    
    # Save to file
    output_data = {
        'occlusion_anchors_per_player': dict(player_occlusion_data),
        'total_players': len(player_occlusion_data),
        'total_occlusion_frames': len(occlusion_frames)
    }
    
    try:
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"✅ Saved occlusion anchors per player to: {output_file}")
        return output_file
    except Exception as e:
        print(f"⚠ Error saving occlusion anchors: {e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python optimize_anchor_frames.py <anchor_frames.json> [output_file]")
        print("\nThis script optimizes anchor frames by:")
        print("  1. Finding anchor frames at occlusion points")
        print("  2. Keeping strategic anchor frames (first appearance, high confidence)")
        print("  3. Reducing total anchor frame count while maintaining quality")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(input_file):
        print(f"⚠ Error: File not found: {input_file}")
        sys.exit(1)
    
    # Optimize anchor frames
    optimized_file = optimize_anchor_frames(input_file, output_file)
    
    if optimized_file:
        # Also create occlusion anchors per player file
        anchor_frames = load_anchor_frames(input_file)
        occlusion_frames = detect_occlusion_points(anchor_frames, {})
        
        occlusion_file = Path(optimized_file).parent / f"{Path(optimized_file).stem}_occlusion_per_player.json"
        store_occlusion_anchors_per_player(anchor_frames, occlusion_frames, str(occlusion_file))
        
        print(f"\n💡 Next steps:")
        print(f"   1. Review the optimized anchor frames:")
        print(f"      → Use 'View Anchor Frames' tool in GUI, or")
        print(f"      → Run: python view_anchor_frames.py")
        print(f"      → Load: {optimized_file}")
        print(f"   2. Test with the optimized file to ensure tracking quality")
        print(f"   3. If satisfied, replace the original file with the optimized version")
        print(f"   4. Occlusion anchors per player saved to: {occlusion_file}")

