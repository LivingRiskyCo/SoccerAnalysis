"""
Convert CSV tracking data to anchor frames for gallery seeding.
Uses a CSV file with correct player identifications to create anchor frames
that will bootstrap Re-ID for a new video.
"""

import pandas as pd
import json
import os
import cv2
from collections import defaultdict

def csv_to_anchor_frames(csv_path, video_path, output_path=None, frames_per_player=5):
    """
    Convert CSV tracking data to anchor frames.
    
    Args:
        csv_path: Path to CSV file with correct player identifications
        video_path: Path to corresponding video file (for bbox extraction)
        output_path: Output path for PlayerTagsSeed JSON (default: same dir as video)
        frames_per_player: Number of anchor frames to create per player
    """
    print(f"📊 Loading CSV: {csv_path}")
    
    if not os.path.exists(csv_path):
        print(f"✗ CSV file not found: {csv_path}")
        return None
    
    try:
        df = pd.read_csv(csv_path, comment='#')
    except Exception as e:
        print(f"✗ Error reading CSV: {e}")
        return None
    
    if df.empty:
        print("✗ CSV file is empty")
        return None
    
    # Extract video resolution from CSV comments
    frame_width = None
    frame_height = None
    fps = 30.0
    
    try:
        with open(csv_path, 'r') as f:
            for line in f:
                if line.startswith('# Video Resolution:'):
                    res_str = line.split(':')[1].strip()
                    if 'x' in res_str:
                        w, h = res_str.split('x')
                        frame_width = int(w.strip())
                        frame_height = int(h.strip())
                elif line.startswith('# Video FPS:'):
                    fps_str = line.split(':')[1].strip()
                    fps = float(fps_str)
    except:
        pass
    
    # Check required columns
    required_cols = ['frame', 'player_id']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"✗ Missing required columns: {missing_cols}")
        print(f"  Available columns: {', '.join(df.columns)}")
        return None
    
    # Group by player and collect frames
    player_frames = defaultdict(list)
    
    for idx, row in df.iterrows():
        # Get frame number
        if pd.isna(row.get('frame')):
            continue
        try:
            frame_num = int(row['frame'])
        except (ValueError, TypeError):
            continue
        
        # Get player ID
        if pd.isna(row.get('player_id')):
            continue
        try:
            player_id = int(row['player_id'])
        except (ValueError, TypeError):
            continue
        
        # Get player name
        player_name = None
        for name_col in ['player_name', 'name', 'player']:
            if name_col in df.columns and pd.notna(row.get(name_col)):
                name_value = row[name_col]
                if isinstance(name_value, str):
                    player_name = name_value.strip()
                elif isinstance(name_value, (list, tuple)) and len(name_value) > 0:
                    player_name = str(name_value[0]).strip()
                else:
                    player_name = str(name_value).strip()
                break
        
        if not player_name:
            continue
        
        # Get team
        team = None
        if 'team' in df.columns and pd.notna(row.get('team')):
            team = str(row['team']).strip()
        
        # Get bbox if available
        bbox = None
        if all(col in df.columns for col in ['x1', 'y1', 'x2', 'y2']):
            if all(pd.notna(row.get(col)) for col in ['x1', 'y1', 'x2', 'y2']):
                try:
                    bbox = [
                        float(row['x1']),
                        float(row['y1']),
                        float(row['x2']),
                        float(row['y2'])
                    ]
                except (ValueError, TypeError):
                    pass
        
        player_frames[player_name].append({
            'frame': frame_num,
            'track_id': player_id,
            'team': team,
            'bbox': bbox
        })
    
    if len(player_frames) == 0:
        print("✗ No valid player data found in CSV")
        return None
    
    print(f"✓ Found {len(player_frames)} unique players in CSV")
    
    # Select best frames for each player (spread across video)
    anchor_frames = {}
    
    for player_name, frames in player_frames.items():
        # Sort by frame number
        frames.sort(key=lambda x: x['frame'])
        
        # Select evenly spaced frames
        total_frames = len(frames)
        if total_frames == 0:
            continue
        
        # Select frames_per_player frames, evenly distributed
        selected_indices = []
        if total_frames <= frames_per_player:
            selected_indices = list(range(total_frames))
        else:
            step = total_frames / frames_per_player
            selected_indices = [int(i * step) for i in range(frames_per_player)]
        
        for idx in selected_indices:
            if idx >= len(frames):
                continue
                
            frame_data = frames[idx]
            frame_num = frame_data['frame']
            
            if frame_num not in anchor_frames:
                anchor_frames[frame_num] = []
            
            anchor_entry = {
                'track_id': frame_data['track_id'],
                'player_name': player_name,
                'confidence': 1.00
            }
            
            if frame_data.get('team'):
                anchor_entry['team'] = frame_data['team']
            
            if frame_data.get('bbox'):
                anchor_entry['bbox'] = frame_data['bbox']
            
            # Avoid duplicates
            is_duplicate = False
            for existing in anchor_frames[frame_num]:
                if (existing.get('track_id') == anchor_entry['track_id'] and 
                    existing.get('player_name') == player_name):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                anchor_frames[frame_num].append(anchor_entry)
    
    # Determine output path
    if output_path is None:
        video_dir = os.path.dirname(os.path.abspath(video_path))
        video_basename = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(video_dir, f"PlayerTagsSeed_{video_basename}.json")
    
    # Get video resolution if not in CSV
    if frame_width is None or frame_height is None:
        try:
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if fps == 30.0:
                    fps = cap.get(cv2.CAP_PROP_FPS)
                cap.release()
                print(f"✓ Video resolution: {frame_width}x{frame_height} @ {fps:.2f} fps")
        except Exception as e:
            print(f"⚠ Could not read video resolution: {e}")
            frame_width = 1920
            frame_height = 1080
    
    # Create seed config structure
    seed_config = {
        'video_path': video_path,
        'video_resolution': {
            'width': frame_width,
            'height': frame_height
        },
        'video_fps': fps,
        'anchor_frames': {str(k): v for k, v in anchor_frames.items()},
        'source_csv': csv_path,
        'created_from': 'csv_to_anchor_frames'
    }
    
    # Save to JSON
    try:
        with open(output_path, 'w') as f:
            json.dump(seed_config, f, indent=2)
    except Exception as e:
        print(f"✗ Error saving anchor frames: {e}")
        return None
    
    total_anchors = sum(len(anchors) for anchors in anchor_frames.values())
    print(f"✓ Created {total_anchors} anchor frames across {len(anchor_frames)} frames")
    print(f"✓ Saved to: {output_path}")
    print(f"\n📋 Players with anchor frames:")
    for player_name in sorted(player_frames.keys()):
        count = sum(1 for anchors in anchor_frames.values() 
                   for a in anchors if a.get('player_name') == player_name)
        print(f"   → {player_name}: {count} anchor frame(s)")
    
    return output_path

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Convert CSV tracking data to anchor frames for Re-ID seeding',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage - creates PlayerTagsSeed_{video_name}.json in video directory
  python csv_to_anchor_frames.py tracking_data.csv video.mp4
  
  # Specify output path
  python csv_to_anchor_frames.py tracking_data.csv video.mp4 --output seed.json
  
  # Use more frames per player for better seeding
  python csv_to_anchor_frames.py tracking_data.csv video.mp4 --frames-per-player 10
        """
    )
    parser.add_argument('csv', help='Path to CSV file with correct player identifications')
    parser.add_argument('video', help='Path to corresponding video file')
    parser.add_argument('--output', help='Output path for PlayerTagsSeed JSON (default: same dir as video)')
    parser.add_argument('--frames-per-player', type=int, default=5, 
                       help='Number of anchor frames per player (default: 5)')
    
    args = parser.parse_args()
    
    result = csv_to_anchor_frames(
        args.csv,
        args.video,
        args.output,
        args.frames_per_player
    )
    
    if result:
        print(f"\n✅ Success! Anchor frames created at: {result}")
        print(f"\nNext steps:")
        print(f"1. Place this file in the same directory as your new video")
        print(f"2. Run analysis on the new video - it will automatically load these anchor frames")
        print(f"3. The anchor frames will seed the Re-ID system with correct player identifications")
    else:
        print(f"\n❌ Failed to create anchor frames. Check errors above.")

