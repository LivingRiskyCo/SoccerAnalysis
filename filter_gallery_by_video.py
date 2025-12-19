"""
Script to filter the player gallery to only include players present in a specific video.

This is different from clean_player_gallery.py - it doesn't remove players permanently,
it just identifies which players should be excluded from matching for a specific video
based on anchor frames or CSV tracking data.

Usage:
    python filter_gallery_by_video.py <video_path> [--anchor-file path] [--csv-file path]
    
Options:
    --anchor-file path   Path to PlayerTagsSeed JSON file for the video
    --csv-file path      Path to CSV tracking data for the video
"""

import json
import sys
import os
from pathlib import Path


def get_players_in_video(video_path, anchor_file=None, csv_file=None):
    """
    Get list of players that are actually in the video.
    
    Args:
        video_path: Path to video file
        anchor_file: Optional path to PlayerTagsSeed JSON file
        csv_file: Optional path to CSV tracking data
    
    Returns:
        Set of player names found in the video
    """
    players_in_video = set()
    
    # Method 1: Check anchor frames
    if anchor_file and os.path.exists(anchor_file):
        print(f"📖 Loading anchor frames: {anchor_file}")
        try:
            with open(anchor_file, 'r', encoding='utf-8') as f:
                anchor_data = json.load(f)
            
            anchor_frames = anchor_data.get('anchor_frames', {})
            for frame_num, entries in anchor_frames.items():
                if isinstance(entries, list):
                    for entry in entries:
                        player_name = entry.get('player_name', '').strip()
                        if player_name:
                            players_in_video.add(player_name)
            
            print(f"  ✓ Found {len(players_in_video)} players in anchor frames")
        except Exception as e:
            print(f"  ⚠ Error loading anchor file: {e}")
    
    # Method 2: Check CSV file
    if csv_file and os.path.exists(csv_file):
        print(f"📖 Loading CSV: {csv_file}")
        try:
            import csv
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                csv_players = set()
                for row in reader:
                    player_name = row.get('player_name', '').strip()
                    if player_name and player_name not in ['', 'Unknown', 'None']:
                        csv_players.add(player_name)
                players_in_video.update(csv_players)
            
            print(f"  ✓ Found {len(csv_players)} unique players in CSV")
        except Exception as e:
            print(f"  ⚠ Error loading CSV: {e}")
    
    # Method 3: Auto-detect anchor file from video path
    if not players_in_video and not anchor_file:
        video_name = Path(video_path).stem
        video_dir = Path(video_path).parent
        
        # Try to find PlayerTagsSeed file
        possible_files = [
            video_dir / f"PlayerTagsSeed-{video_name}.json",
            video_dir / f"PlayerTagsSeed_{video_name}.json",
        ]
        
        for anchor_path in possible_files:
            if anchor_path.exists():
                print(f"📖 Auto-detected anchor file: {anchor_path}")
                try:
                    with open(anchor_path, 'r', encoding='utf-8') as f:
                        anchor_data = json.load(f)
                    
                    anchor_frames = anchor_data.get('anchor_frames', {})
                    for frame_num, entries in anchor_frames.items():
                        if isinstance(entries, list):
                            for entry in entries:
                                player_name = entry.get('player_name', '').strip()
                                if player_name:
                                    players_in_video.add(player_name)
                    
                    print(f"  ✓ Found {len(players_in_video)} players in anchor frames")
                    break
                except Exception as e:
                    print(f"  ⚠ Error loading anchor file: {e}")
    
    return players_in_video


def analyze_gallery_for_video(gallery_path="player_gallery.json", video_path=None, 
                              anchor_file=None, csv_file=None):
    """
    Analyze which players in the gallery are in the specified video.
    
    Returns:
        Tuple of (players_in_video, players_not_in_video, players_with_ref_frames)
    """
    if not os.path.exists(gallery_path):
        print(f"❌ Gallery file not found: {gallery_path}")
        return None, None, None
    
    print(f"📖 Loading gallery: {gallery_path}")
    try:
        with open(gallery_path, 'r', encoding='utf-8') as f:
            gallery_data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading gallery: {e}")
        return None, None, None
    
    players = gallery_data
    print(f"✓ Loaded {len(players)} players from gallery")
    
    # Get players actually in the video
    if video_path:
        players_in_video_set = get_players_in_video(video_path, anchor_file, csv_file)
    else:
        players_in_video_set = set()
    
    players_in_video = []
    players_not_in_video = []
    players_with_ref_frames = []
    
    for player_id, player_data in players.items():
        player_name = player_data.get('name', 'Unknown')
        ref_frames = player_data.get('reference_frames', [])
        num_ref_frames = len(ref_frames) if isinstance(ref_frames, list) else 0
        
        if num_ref_frames > 0:
            players_with_ref_frames.append((player_id, player_name, num_ref_frames))
        
        if players_in_video_set:
            if player_name in players_in_video_set:
                players_in_video.append((player_id, player_name, num_ref_frames))
            else:
                players_not_in_video.append((player_id, player_name, num_ref_frames))
    
    return players_in_video, players_not_in_video, players_with_ref_frames


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage:")
        print("  python filter_gallery_by_video.py <video_path> [--anchor-file path] [--csv-file path]")
        print("\nExample:")
        print('  python filter_gallery_by_video.py "C:/Users/nerdw/Videos/20251001_184229.mp4" --anchor-file "PlayerTagsSeed-20251001_184229.json"')
        sys.exit(1)
    
    video_path = sys.argv[1]
    anchor_file = None
    csv_file = None
    
    # Parse arguments
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--anchor-file' and i + 1 < len(sys.argv):
            anchor_file = sys.argv[i + 1]
            i += 2
        elif arg == '--csv-file' and i + 1 < len(sys.argv):
            csv_file = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    
    print("🔍 Player Gallery Filter by Video")
    print("=" * 50)
    
    players_in_video, players_not_in_video, players_with_ref_frames = analyze_gallery_for_video(
        video_path=video_path,
        anchor_file=anchor_file,
        csv_file=csv_file
    )
    
    if players_in_video is None:
        sys.exit(1)
    
    print(f"\n📊 Analysis Results:")
    print(f"  Total players in gallery: {len(players_in_video) + len(players_not_in_video)}")
    print(f"  Players IN this video: {len(players_in_video)}")
    print(f"  Players NOT in this video: {len(players_not_in_video)}")
    print(f"  Players with reference frames: {len(players_with_ref_frames)}")
    
    if players_in_video:
        print(f"\n✓ Players IN this video (should be used for matching):")
        for player_id, player_name, num_ref in players_in_video:
            print(f"  - {player_name} (Ref frames: {num_ref})")
    
    if players_not_in_video:
        print(f"\n⚠ Players NOT in this video (should be EXCLUDED from matching):")
        for player_id, player_name, num_ref in players_not_in_video:
            print(f"  - {player_name} (Ref frames: {num_ref})")
    
    print(f"\n💡 Recommendation:")
    print(f"  Use 'include_only_players' parameter in analysis to restrict matching")
    print(f"  to only these {len(players_in_video)} players for this video.")


if __name__ == "__main__":
    main()

