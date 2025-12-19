"""
Analyze anchor frame coverage for a video.

Usage:
    python analyze_anchor_coverage.py <anchor_file_path> [--video-frames N] [--protection-window N]
"""

import json
import sys
from collections import defaultdict

def analyze_coverage(anchor_file_path, video_frames=474, protection_window=150):
    """
    Analyze anchor frame coverage.
    
    Args:
        anchor_file_path: Path to PlayerTagsSeed JSON file
        video_frames: Total number of frames in video
        protection_window: Protection window in frames (default: 150, meaning ±150 frames)
    """
    try:
        with open(anchor_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading anchor file: {e}")
        return
    
    frames = data.get('anchor_frames', {})
    
    # Collect all anchor frames
    anchor_frames_list = []
    for frame_num_str, frame_entries in frames.items():
        if isinstance(frame_entries, list):
            for entry in frame_entries:
                if isinstance(entry, dict):
                    player_name = entry.get('player_name', '')
                    try:
                        frame_num = int(frame_num_str)
                        anchor_frames_list.append((frame_num, player_name))
                    except ValueError:
                        continue
    
    anchor_frames_list.sort()
    
    print(f"📊 Anchor Frame Coverage Analysis")
    print("=" * 60)
    print(f"Video: {video_frames} frames total")
    print(f"Anchor protection window: ±{protection_window} frames (each anchor protects {protection_window * 2 + 1} frames)")
    print(f"Total anchor frames: {len(anchor_frames_list)}")
    print()
    
    # Group by player
    players_anchors = defaultdict(list)
    for frame, player in anchor_frames_list:
        players_anchors[player].append(frame)
    
    print("📋 Anchor frames by player:")
    for player, frames_list in sorted(players_anchors.items()):
        print(f"  {player}: {len(frames_list)} anchor(s) at frames {frames_list}")
    print()
    
    # Calculate coverage
    protected = set()
    for frame, _ in anchor_frames_list:
        # Each anchor protects frames from (frame - protection_window) to (frame + protection_window)
        start_frame = max(0, frame - protection_window)
        end_frame = min(video_frames, frame + protection_window + 1)
        protected.update(range(start_frame, end_frame))
    
    uncovered = set(range(video_frames)) - protected
    
    print("📈 Coverage Analysis:")
    print(f"  Protected frames: {len(protected)} out of {video_frames} ({len(protected)/video_frames*100:.1f}%)")
    print(f"  Uncovered frames: {len(uncovered)} ({len(uncovered)/video_frames*100:.1f}%)")
    
    if uncovered:
        uncovered_list = sorted(list(uncovered))
        print(f"\n⚠ Uncovered frame ranges:")
        # Group consecutive frames
        ranges = []
        start = uncovered_list[0]
        end = uncovered_list[0]
        for frame in uncovered_list[1:]:
            if frame == end + 1:
                end = frame
            else:
                if start == end:
                    ranges.append(f"{start}")
                else:
                    ranges.append(f"{start}-{end}")
                start = frame
                end = frame
        if start == end:
            ranges.append(f"{start}")
        else:
            ranges.append(f"{start}-{end}")
        
        if len(ranges) <= 20:
            for r in ranges:
                print(f"    Frames {r}")
        else:
            for r in ranges[:20]:
                print(f"    Frames {r}")
            print(f"    ... and {len(ranges) - 20} more ranges")
        
        # Calculate largest gap
        gaps = []
        for i in range(len(uncovered_list) - 1):
            gap = uncovered_list[i+1] - uncovered_list[i]
            if gap > 1:
                gaps.append((uncovered_list[i], uncovered_list[i+1], gap - 1))
        
        if gaps:
            largest_gap = max(gaps, key=lambda x: x[2])
            print(f"\n  Largest gap: {largest_gap[2]} frames between frame {largest_gap[0]} and {largest_gap[1]}")
    else:
        print("\n✅ Perfect coverage! All frames are protected.")
    
    # Per-player coverage
    print(f"\n📊 Per-Player Coverage:")
    for player, frames_list in sorted(players_anchors.items()):
        player_protected = set()
        for frame in frames_list:
            start_frame = max(0, frame - protection_window)
            end_frame = min(video_frames, frame + protection_window + 1)
            player_protected.update(range(start_frame, end_frame))
        
        coverage_pct = len(player_protected) / video_frames * 100
        print(f"  {player}: {len(player_protected)}/{video_frames} frames ({coverage_pct:.1f}%)")
    
    print()
    print("💡 Recommendation:")
    if len(uncovered) / video_frames > 0.1:  # More than 10% uncovered
        print(f"  ⚠ Consider adding more anchor frames to cover {len(uncovered)} uncovered frames")
        print(f"     Target: Add anchors every ~{video_frames // (video_frames // (protection_window * 2))} frames for full coverage")
    else:
        print(f"  ✓ Coverage looks good! {len(protected)}/{video_frames} frames protected ({len(protected)/video_frames*100:.1f}%)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_anchor_coverage.py <anchor_file_path> [--video-frames N] [--protection-window N]")
        sys.exit(1)
    
    anchor_file = sys.argv[1]
    video_frames = 474
    protection_window = 150
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--video-frames' and i + 1 < len(sys.argv):
            video_frames = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--protection-window' and i + 1 < len(sys.argv):
            protection_window = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1
    
    analyze_coverage(anchor_file, video_frames, protection_window)
