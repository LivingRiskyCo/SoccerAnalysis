"""
Utility script to convert tracking CSV data to anchor frames.

This script reads a tracking CSV file and converts all tracked players
into anchor frames with 1.00 confidence. This is useful when you want
to use existing tracking data as ground truth for future analysis.

Usage:
    python convert_tracks_to_anchor_frames.py <csv_file> <video_path> [output_json]

Example:
    python convert_tracks_to_anchor_frames.py part001_analyzed_tracking_data.csv "C:/Users/nerdw/Videos/Practice 11-11/11-11/part001.mp4"
"""

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

def load_player_gallery(gallery_path="player_gallery.json"):
    """Load player gallery to get player names and teams."""
    if not os.path.exists(gallery_path):
        print(f"⚠ Player gallery not found: {gallery_path}")
        return {}
    
    try:
        with open(gallery_path, 'r') as f:
            gallery_data = json.load(f)
        
        # Build mapping: track_id (as string) -> (player_name, team)
        player_map = {}
        
        # Handle both old format (dict with 'players' key) and new format (direct dict of players)
        players_dict = gallery_data.get('players', gallery_data) if isinstance(gallery_data, dict) else {}
        
        if isinstance(players_dict, dict):
            for player_id, profile in players_dict.items():
                if not isinstance(profile, dict):
                    continue
                    
                player_name = profile.get('name', '')
                team = profile.get('team', '')
                
                # Method 1: Check track_history to see which track_ids this player has been assigned to
                if 'track_history' in profile and profile['track_history']:
                    for track_id_str, count in profile['track_history'].items():
                        player_map[track_id_str] = (player_name, team)
                
                # Method 2: Also check approved_mappings if available (from seed files)
                # This helps when track_history isn't populated yet
                if 'approved_mappings' in gallery_data:
                    for track_id_str, mapping in gallery_data['approved_mappings'].items():
                        if isinstance(mapping, (list, tuple)) and len(mapping) >= 1:
                            if mapping[0] == player_name:
                                player_map[track_id_str] = (player_name, team)
                        elif isinstance(mapping, str) and mapping == player_name:
                            player_map[track_id_str] = (player_name, team)
        
        print(f"✓ Loaded {len(player_map)} track-to-player mappings from gallery")
        return player_map
    except Exception as e:
        print(f"⚠ Error loading player gallery: {e}")
        import traceback
        traceback.print_exc()
        return {}

def convert_csv_to_anchor_frames(csv_path, video_path, output_json=None, player_gallery_path="player_gallery.json",
                                  max_frames=None, frame_interval=30, min_confidence=None, use_csv_names=True, 
                                  video_width=None, video_height=None):
    """
    Convert tracking CSV to anchor frames format with smart filtering.
    
    Args:
        csv_path: Path to tracking CSV file
        video_path: Path to video file (for anchor frame format)
        output_json: Optional output JSON path (default: PlayerTagsSeed-{video_name}.json)
        player_gallery_path: Path to player gallery JSON
        max_frames: Maximum number of frames to convert (None = no limit)
        frame_interval: Only convert every Nth frame (default: 30 = ~1 frame per second at 30fps)
        min_confidence: Minimum confidence threshold (if CSV has confidence column)
        video_width: Video native width in pixels (for resolution validation)
        video_height: Video native height in pixels (for resolution validation)
    
    Returns:
        Path to created JSON file
    """
    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        return None
    
    # CRITICAL: Detect video resolution from CSV metadata or video file
    # This ensures anchor frames are locked to the correct video resolution
    detected_video_width = video_width
    detected_video_height = video_height
    
    # Try to read video resolution from CSV metadata (comments at top of file)
    if not detected_video_width or not detected_video_height:
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                first_lines = [f.readline() for _ in range(10)]  # Read first 10 lines
                for line in first_lines:
                    if line.startswith('# Video Resolution:'):
                        # Parse: "# Video Resolution: 3840x2160 pixels"
                        import re
                        match = re.search(r'(\d+)x(\d+)', line)
                        if match:
                            detected_video_width = int(match.group(1))
                            detected_video_height = int(match.group(2))
                            print(f"  📐 Detected video resolution from CSV: {detected_video_width}x{detected_video_height}")
                            break
        except:
            pass
    
    # Fallback: Try to detect from video file if available
    if (not detected_video_width or not detected_video_height) and video_path and os.path.exists(video_path):
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                detected_video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                detected_video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                print(f"  📐 Detected video resolution from video file: {detected_video_width}x{detected_video_height}")
        except:
            pass
    
    # Load player gallery for name/team mapping
    player_map = load_player_gallery(player_gallery_path)
    
    # Group tracks by frame
    frames_data = defaultdict(list)  # {frame_num: [{track_id, player_name, team, bbox}]}
    
    # Default bbox size (same as metrics evaluator uses)
    default_w = 80  # pixels
    default_h = 160  # pixels
    
    print(f"📖 Reading CSV: {csv_path}")
    if detected_video_width and detected_video_height:
        print(f"  📐 Video resolution: {detected_video_width}x{detected_video_height} (locked)")
    
    # Check file exists and get size
    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        return None
    
    file_size = os.path.getsize(csv_path)
    print(f"  📊 File size: {file_size:,} bytes")
    
    if frame_interval > 1:
        print(f"  📊 Frame sampling: Every {frame_interval} frames (~{30/frame_interval:.1f} frames/sec at 30fps)")
    if max_frames is not None:
        print(f"  📊 Max frames limit: {max_frames} frames")
    if min_confidence is not None:
        print(f"  📊 Min confidence: {min_confidence}")
    total_rows = 0
    tracks_processed = 0
    skipped_no_frame = 0
    skipped_no_player_id = 0
    skipped_no_position = 0
    skipped_no_name = 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            # Skip comment lines (starting with '#') - these contain metadata
            lines = [line for line in f if not line.strip().startswith('#')]
            reader = csv.DictReader(lines)
        
        # Check if we have the expected columns
        fieldnames = reader.fieldnames
        if fieldnames:
            print(f"  📊 CSV columns: {', '.join(fieldnames[:10])}{'...' if len(fieldnames) > 10 else ''}")
            has_player_name = 'player_name' in fieldnames
            has_frame = 'frame' in fieldnames or 'frame_num' in fieldnames
            has_player_id = 'player_id' in fieldnames or 'track_id' in fieldnames
            print(f"  ✓ Has 'player_name' column: {has_player_name}")
            print(f"  ✓ Has 'frame' column: {has_frame}")
            print(f"  ✓ Has 'player_id' column: {has_player_id}")
        else:
            print(f"  ⚠ Warning: CSV has no column headers!")
        
        for row in reader:
                total_rows += 1
                
                # Get frame number
                frame_val = row.get('frame', row.get('frame_num', ''))
                if not frame_val or str(frame_val).strip() == '':
                    skipped_no_frame += 1
                    continue
                
                try:
                    frame_num = int(float(frame_val))
                except (ValueError, TypeError):
                    skipped_no_frame += 1
                    continue
                
                # Get player_id (track_id) - try multiple column names
                player_id_val = row.get('player_id', row.get('track_id', row.get('id', '')))
                if not player_id_val or str(player_id_val).strip() == '':
                    skipped_no_player_id += 1
                    continue
                
                try:
                    track_id = int(float(player_id_val))
                except (ValueError, TypeError):
                    skipped_no_player_id += 1
                    continue
                
                # CRITICAL FIX: Use actual bbox coordinates from CSV if available
                # This ensures anchor frames match the actual detection bboxes from the video
                # Try to get bbox coordinates directly from CSV (most accurate)
                bbox_x1_val = row.get('x1', row.get('bbox_x1', ''))
                bbox_y1_val = row.get('y1', row.get('bbox_y1', ''))
                bbox_x2_val = row.get('x2', row.get('bbox_x2', ''))
                bbox_y2_val = row.get('y2', row.get('bbox_y2', ''))
                
                bbox = None
                if (bbox_x1_val and bbox_y1_val and bbox_x2_val and bbox_y2_val and 
                    str(bbox_x1_val).strip() != '' and str(bbox_y1_val).strip() != '' and
                    str(bbox_x2_val).strip() != '' and str(bbox_y2_val).strip() != ''):
                    try:
                        x1 = float(bbox_x1_val)
                        y1 = float(bbox_y1_val)
                        x2 = float(bbox_x2_val)
                        y2 = float(bbox_y2_val)
                        # Validate bbox (x2 > x1, y2 > y1)
                        if x2 > x1 and y2 > y1:
                            bbox = [x1, y1, x2, y2]
                    except (ValueError, TypeError):
                        pass  # Fall back to center point method
                
                # Fallback: Use center point if bbox columns not available
                if bbox is None:
                    player_x_val = row.get('player_x', row.get('x', row.get('center_x', '')))
                    player_y_val = row.get('player_y', row.get('y', row.get('center_y', '')))
                    
                    if not player_x_val or not player_y_val or str(player_x_val).strip() == '' or str(player_y_val).strip() == '':
                        skipped_no_position += 1
                        continue
                    
                    try:
                        px = float(player_x_val)
                        py = float(player_y_val)
                    except (ValueError, TypeError):
                        skipped_no_position += 1
                        continue
                    
                    # Convert center point to bbox (fallback method)
                    x1 = px - default_w / 2
                    y1 = py - default_h / 2
                    x2 = px + default_w / 2
                    y2 = py + default_h / 2
                    bbox = [x1, y1, x2, y2]
                
                # Get player name and team - ONLY use CSV names (don't fall back to gallery)
                # CRITICAL FIX: Gallery mappings may be from previous videos, so we should ONLY use CSV names
                # This prevents importing players from other videos (e.g., Jax Derryberry, Wesley Beckett)
                track_id_str = str(track_id)
                player_name = None
                team = ""
                
                # ONLY use CSV player names - don't fall back to gallery
                # Gallery mappings are from previous videos and may not apply to this video
                csv_name = row.get('player_name', row.get('name', ''))
                if csv_name and csv_name.strip() and not csv_name.startswith('Unknown'):
                    player_name = csv_name.strip()
                    team = row.get('team', row.get('player_team', row.get('team_name', '')))
                
                # Skip entries without player names (don't create "Unknown Player" entries)
                # These won't be useful for matching anyway
                # CRITICAL: Don't fall back to gallery - only use names that are explicitly in the CSV
                if not player_name or str(player_name).startswith('Unknown') or str(player_name).strip() == '':
                    skipped_no_name += 1
                    continue
                
                # Apply frame interval filtering (only convert every Nth frame)
                if frame_interval > 1 and frame_num % frame_interval != 0:
                    continue
                
                # Check confidence threshold if provided
                if min_confidence is not None:
                    conf_val = row.get('confidence', '')
                    try:
                        conf = float(conf_val) if conf_val else 1.0
                        if conf < min_confidence:
                            continue
                    except (ValueError, TypeError):
                        pass  # Skip confidence check if not available
                
                # Create anchor frame entry
                anchor_entry = {
                    "track_id": track_id,
                    "player_name": player_name,
                    "team": team,
                    "bbox": bbox,
                    "confidence": 1.00  # All converted tracks are ground truth
                }
                
                frames_data[frame_num].append(anchor_entry)
                tracks_processed += 1
                
                if tracks_processed % 1000 == 0:
                    print(f"  Processed {tracks_processed} track entries...")
                
                # Apply max_frames limit (stop early if we've reached the limit of unique frames)
                if max_frames is not None and len(frames_data) >= max_frames:
                    print(f"  ⚠ Reached max_frames limit ({max_frames}), stopping conversion...")
                    break
        
        print(f"✓ Processed {tracks_processed} track entries from {total_rows} CSV rows")
        if skipped_no_frame > 0:
            print(f"  ⚠ Skipped {skipped_no_frame} rows: missing frame number")
        if skipped_no_player_id > 0:
            print(f"  ⚠ Skipped {skipped_no_player_id} rows: missing player_id/track_id")
        if skipped_no_position > 0:
            print(f"  ⚠ Skipped {skipped_no_position} rows: missing player_x/player_y")
        if skipped_no_name > 0:
            print(f"  ⚠ Skipped {skipped_no_name} rows: missing player_name")
        print(f"✓ Found {len(frames_data)} frames with tracked players")
        
    except Exception as e:
        error_msg = f"❌ Error reading CSV: {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return None
    
    if not frames_data:
        error_msg = "❌ Conversion failed!\n\n"
        error_msg += "Possible reasons:\n"
        if not player_map:
            error_msg += "• No player mappings found in player_gallery.json\n"
        if tracks_processed == 0:
            error_msg += f"• CSV doesn't have matching player names\n"
            error_msg += f"  → Check that CSV has 'player_name' column with player names\n"
            error_msg += f"  → Or that player_gallery.json has track_history mappings\n"
        if total_rows == 0:
            error_msg += "• CSV file is empty or couldn't be read\n"
        else:
            error_msg += f"• All tracks were filtered out by settings\n"
            error_msg += f"  → Check frame_interval, max_frames, or min_confidence settings\n"
        error_msg += "\nCheck the error messages above for details.\n\n"
        error_msg += "Tip: Make sure player_gallery.json has track_history\n"
        error_msg += "or run analysis first to populate the gallery."
        print(error_msg)
        return None
    
    # Determine output path
    if output_json is None:
        # Use same directory as CSV, with video name
        video_name = Path(video_path).stem if video_path else Path(csv_path).stem.replace('_tracking_data', '')
        output_dir = Path(csv_path).parent
        output_json = output_dir / f"PlayerTagsSeed-{video_name}.json"
    
    # Create anchor frames structure
    anchor_frames = {}
    for frame_num, entries in frames_data.items():
        anchor_frames[str(frame_num)] = entries
    
    # Create full seed config structure
    seed_config = {
        "video_path": video_path,
        "approved_mappings": {},  # Will be populated from anchor frames
        "anchor_frames": anchor_frames
    }
    
    # CRITICAL: Store video resolution in anchor frames for validation
    # This ensures we can check if anchor frames match the video being analyzed
    if detected_video_width and detected_video_height:
        seed_config["video_resolution"] = {
            "width": detected_video_width,
            "height": detected_video_height
        }
        print(f"  📐 Stored video resolution in anchor frames: {detected_video_width}x{detected_video_height}")
    
    # Populate approved_mappings from anchor frames
    for frame_num, entries in frames_data.items():
        for entry in entries:
            track_id_str = str(entry['track_id'])
            if track_id_str not in seed_config['approved_mappings']:
                seed_config['approved_mappings'][track_id_str] = (
                    entry['player_name'],
                    entry['team']
                )
    
    # Save to JSON
    try:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(seed_config, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved anchor frames to: {output_json}")
        print(f"  - {len(anchor_frames)} frames with anchor frames")
        print(f"  - {tracks_processed} total anchor frame entries")
        print(f"  - {len(seed_config['approved_mappings'])} unique track IDs")
        
        return str(output_json)
        
    except Exception as e:
        print(f"❌ Error saving JSON: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nUsage:")
        print("  python convert_tracks_to_anchor_frames.py <csv_file> <video_path> [output_json] [--interval N] [--max-frames N]")
        print("\nOptions:")
        print("  --interval N      Only convert every Nth frame (default: 30 = ~1 per second at 30fps)")
        print("  --max-frames N   Maximum number of frames to convert (default: no limit)")
        print("\nExample:")
        print('  python convert_tracks_to_anchor_frames.py "part001_analyzed_tracking_data.csv" "C:/Users/nerdw/Videos/Practice 11-11/11-11/part001.mp4"')
        print('  python convert_tracks_to_anchor_frames.py "data.csv" "video.mp4" --interval 30 --max-frames 500')
        sys.exit(1)
    
    csv_path = sys.argv[1]
    video_path = sys.argv[2]
    output_json = None
    frame_interval = 30  # Default
    max_frames = None
    
    # Parse optional arguments
    i = 3
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--interval' and i + 1 < len(sys.argv):
            frame_interval = int(sys.argv[i + 1])
            i += 2
        elif arg == '--max-frames' and i + 1 < len(sys.argv):
            max_frames = int(sys.argv[i + 1])
            i += 2
        elif not arg.startswith('--'):
            output_json = arg
            i += 1
        else:
            i += 1
    
    result = convert_csv_to_anchor_frames(csv_path, video_path, output_json, 
                                         frame_interval=frame_interval, max_frames=max_frames)
    
    if result:
        print(f"\n✅ Success! Anchor frames saved to: {result}")
        print("\nNext steps:")
        print("  1. The anchor frames will be automatically loaded during analysis")
        print("  2. They will be used as ground truth for Re-ID, metrics, and routing")
        print("  3. All tracks will have 1.00 confidence (highest priority)")
    else:
        print("\n❌ Failed to convert tracks to anchor frames")
        sys.exit(1)

if __name__ == "__main__":
    main()

