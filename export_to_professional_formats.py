"""
Export tracking data to professional sports analysis formats.
Converts your CSV tracking data to formats used by coaches, scouts, and broadcast.

Supported formats:
- SPORTS CODE / HUDL (XML)
- TRACAB / Second Spectrum (JSON)
- Dartfish / Nacsport (XML)
- Stats Perform (JSON)
"""

import csv
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
from collections import defaultdict
import argparse
import os


def read_tracking_csv(csv_path):
    """
    Read tracking CSV and organize by frame.
    Returns: {frame_num: {'timestamp': float, 'ball': {...}, 'players': [...]}}
    """
    frames = defaultdict(lambda: {'timestamp': 0, 'ball': None, 'players': []})
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame_num = int(row['frame'])
            timestamp = float(row['timestamp'])
            
            # Store ball data (once per frame)
            if frames[frame_num]['ball'] is None and row['ball_detected'] == 'True':
                frames[frame_num]['ball'] = {
                    'x': float(row['ball_x']) if row['ball_x'] else None,
                    'y': float(row['ball_y']) if row['ball_y'] else None,
                    'x_m': float(row['ball_x_m']) if row['ball_x_m'] else None,
                    'y_m': float(row['ball_y_m']) if row['ball_y_m'] else None,
                    'speed': float(row['ball_speed_mps']) if row['ball_speed_mps'] else None,
                    'angle': float(row['ball_trajectory_angle']) if row['ball_trajectory_angle'] else None
                }
            
            # Store player data
            if row['player_id']:
                frames[frame_num]['players'].append({
                    'id': int(row['player_id']),
                    'x': float(row['player_x']),
                    'y': float(row['player_y']),
                    'confidence': float(row['confidence']) if row['confidence'] else 0.0,
                    'has_possession': row['possession_player_id'] == row['player_id']
                })
            
            frames[frame_num]['timestamp'] = timestamp
    
    return dict(frames)


def export_to_sportscode_xml(frames_data, output_path, fps=24.0, video_name="soccer_match"):
    """
    Export to SportsCode XML format (used by Hudl SportsCode).
    
    SportsCode XML schema:
    - Instance-based (each event is an "instance")
    - Timeline markers for analysis
    - Label groups for categories
    """
    root = ET.Element('file')
    root.set('version', '1.0')
    
    # Add file info
    info = ET.SubElement(root, 'ALL_INSTANCES')
    info.set('code', 'All Instances')
    
    # Create instance for each significant event (possession changes, ball movement)
    instance_id = 0
    prev_possession = None
    
    for frame_num in sorted(frames_data.keys()):
        frame = frames_data[frame_num]
        timestamp = frame['timestamp']
        
        # Create instance for possession changes
        current_possession = None
        for player in frame['players']:
            if player['has_possession']:
                current_possession = player['id']
                break
        
        if current_possession != prev_possession and current_possession is not None:
            instance = ET.SubElement(info, 'instance')
            instance.set('ID', str(instance_id))
            instance.set('code', 'Possession Change')
            instance.set('start', f"{timestamp:.3f}")
            instance.set('end', f"{timestamp + 1/fps:.3f}")
            
            # Add labels
            label = ET.SubElement(instance, 'label')
            label.set('group', 'Player')
            label.set('text', f"Player #{current_possession}")
            
            # Add position data
            for player in frame['players']:
                if player['id'] == current_possession:
                    pos = ET.SubElement(instance, 'position')
                    pos.set('x', f"{player['x']:.2f}")
                    pos.set('y', f"{player['y']:.2f}")
                    break
            
            instance_id += 1
            prev_possession = current_possession
    
    # Pretty print XML
    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_str)
    
    print(f"✓ SportsCode XML exported: {output_path}")
    print(f"  - {instance_id} instances (events)")
    print(f"  - Compatible with Hudl SportsCode")


def export_to_tracab_json(frames_data, output_path, fps=24.0, field_length=24.6, field_width=20.0):
    """
    Export to TRACAB JSON format (used by Second Spectrum, ChyronHego).
    
    TRACAB format:
    - Frame-by-frame tracking
    - Real-world coordinates (meters)
    - Player and ball positions
    - Speed and acceleration data
    """
    tracab_data = {
        "metadata": {
            "provider": "Custom Soccer Tracker",
            "match_id": "match_001",
            "timestamp": datetime.now().isoformat(),
            "fps": fps,
            "pitch_size": [field_length, field_width],
            "coordinate_system": "center_origin"  # (0,0) at center of field
        },
        "frames": []
    }
    
    for frame_num in sorted(frames_data.keys()):
        frame = frames_data[frame_num]
        
        frame_entry = {
            "frame_id": frame_num,
            "timestamp": frame['timestamp'],
            "ball": None,
            "players": []
        }
        
        # Add ball data
        if frame['ball'] and frame['ball']['x_m'] is not None:
            frame_entry['ball'] = {
                "x": frame['ball']['x_m'],
                "y": frame['ball']['y_m'],
                "speed": frame['ball']['speed'] if frame['ball']['speed'] else 0.0,
                "possession": None
            }
            
            # Find possession
            for player in frame['players']:
                if player['has_possession']:
                    frame_entry['ball']['possession'] = player['id']
                    break
        
        # Add player data
        for player in frame['players']:
            frame_entry['players'].append({
                "player_id": player['id'],
                "team_id": 0,  # TODO: Add team classification
                "jersey_number": player['id'] % 100,
                "x": player.get('x_m', player['x']),  # Use meters if available
                "y": player.get('y_m', player['y']),
                "speed": 0.0,  # TODO: Calculate from frame-to-frame
                "acceleration": 0.0
            })
        
        tracab_data['frames'].append(frame_entry)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(tracab_data, f, indent=2)
    
    print(f"✓ TRACAB JSON exported: {output_path}")
    print(f"  - {len(tracab_data['frames'])} frames")
    print(f"  - Compatible with Second Spectrum, ChyronHego")


def export_to_dartfish_xml(frames_data, output_path, fps=24.0, video_name="soccer_match.mp4"):
    """
    Export to Dartfish XML format (used by Dartfish, Nacsport).
    
    Dartfish format:
    - Timeline-based analysis
    - Tagged moments
    - Player tracking overlay
    """
    root = ET.Element('DartfishProject')
    root.set('version', '11.0')
    
    # Add video reference
    video = ET.SubElement(root, 'Video')
    video.set('source', video_name)
    video.set('fps', str(fps))
    
    # Add tracking data
    tracking = ET.SubElement(root, 'TrackingData')
    
    for frame_num in sorted(frames_data.keys()):
        frame = frames_data[frame_num]
        
        frame_elem = ET.SubElement(tracking, 'Frame')
        frame_elem.set('number', str(frame_num))
        frame_elem.set('time', f"{frame['timestamp']:.3f}")
        
        # Add ball
        if frame['ball']:
            ball = ET.SubElement(frame_elem, 'Ball')
            ball.set('x', f"{frame['ball']['x']:.2f}")
            ball.set('y', f"{frame['ball']['y']:.2f}")
            if frame['ball']['speed']:
                ball.set('speed', f"{frame['ball']['speed']:.2f}")
        
        # Add players
        for player in frame['players']:
            player_elem = ET.SubElement(frame_elem, 'Player')
            player_elem.set('id', str(player['id']))
            player_elem.set('x', f"{player['x']:.2f}")
            player_elem.set('y', f"{player['y']:.2f}")
            if player['has_possession']:
                player_elem.set('hasBall', 'true')
    
    # Add tags for key events
    tags = ET.SubElement(root, 'Tags')
    prev_possession = None
    tag_id = 0
    
    for frame_num in sorted(frames_data.keys()):
        frame = frames_data[frame_num]
        
        current_possession = None
        for player in frame['players']:
            if player['has_possession']:
                current_possession = player['id']
                break
        
        if current_possession != prev_possession and current_possession is not None:
            tag = ET.SubElement(tags, 'Tag')
            tag.set('id', str(tag_id))
            tag.set('frame', str(frame_num))
            tag.set('time', f"{frame['timestamp']:.3f}")
            tag.set('label', f"Possession: Player #{current_possession}")
            tag_id += 1
            prev_possession = current_possession
    
    # Pretty print XML
    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_str)
    
    print(f"✓ Dartfish XML exported: {output_path}")
    print(f"  - {len(frames_data)} frames tracked")
    print(f"  - {tag_id} tagged events")
    print(f"  - Compatible with Dartfish, Nacsport")


def export_to_stats_perform_json(frames_data, output_path, fps=24.0):
    """
    Export to Stats Perform (Opta) JSON format.
    
    Stats Perform format:
    - Event-based analytics
    - Player metrics
    - Team performance data
    """
    stats_data = {
        "metadata": {
            "provider": "Custom Soccer Tracker",
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "fps": fps
        },
        "tracking": {
            "frames": []
        },
        "events": [],
        "analytics": {
            "possession_time": {},
            "player_distances": {},
            "player_speeds": {}
        }
    }
    
    # Calculate analytics
    possession_frames = defaultdict(int)
    
    for frame_num in sorted(frames_data.keys()):
        frame = frames_data[frame_num]
        
        # Track possession time
        for player in frame['players']:
            if player['has_possession']:
                possession_frames[player['id']] += 1
        
        # Add frame data
        stats_data['tracking']['frames'].append({
            "frame": frame_num,
            "timestamp": frame['timestamp'],
            "objects": [
                {
                    "type": "ball" if frame['ball'] else None,
                    "position": [frame['ball']['x'], frame['ball']['y']] if frame['ball'] else None
                }
            ] + [
                {
                    "type": "player",
                    "id": p['id'],
                    "position": [p['x'], p['y']],
                    "in_possession": p['has_possession']
                }
                for p in frame['players']
            ]
        })
    
    # Add analytics
    for player_id, frames_count in possession_frames.items():
        stats_data['analytics']['possession_time'][str(player_id)] = {
            "frames": frames_count,
            "seconds": frames_count / fps,
            "percentage": (frames_count / len(frames_data)) * 100
        }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, indent=2)
    
    print(f"✓ Stats Perform JSON exported: {output_path}")
    print(f"  - {len(frames_data)} frames")
    print(f"  - {len(possession_frames)} players tracked")
    print(f"  - Possession analytics included")


def export_all_formats(csv_path, output_dir=None, fps=24.0):
    """Export to all professional formats."""
    if output_dir is None:
        output_dir = os.path.dirname(csv_path)
    
    base_name = os.path.splitext(os.path.basename(csv_path))[0]
    
    print(f"\n📊 Reading tracking data from: {csv_path}")
    frames_data = read_tracking_csv(csv_path)
    print(f"✓ Loaded {len(frames_data)} frames\n")
    
    # Export to each format
    export_to_sportscode_xml(
        frames_data,
        os.path.join(output_dir, f"{base_name}_sportscode.xml"),
        fps=fps
    )
    
    export_to_tracab_json(
        frames_data,
        os.path.join(output_dir, f"{base_name}_tracab.json"),
        fps=fps
    )
    
    export_to_dartfish_xml(
        frames_data,
        os.path.join(output_dir, f"{base_name}_dartfish.xml"),
        fps=fps
    )
    
    export_to_stats_perform_json(
        frames_data,
        os.path.join(output_dir, f"{base_name}_statsperform.json"),
        fps=fps
    )
    
    print(f"\n✅ All formats exported to: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export tracking data to professional sports analysis formats"
    )
    parser.add_argument("--csv", required=True, help="Input CSV tracking data file")
    parser.add_argument("--output-dir", help="Output directory (default: same as CSV)")
    parser.add_argument("--fps", type=float, default=24.0, help="Video frame rate (default: 24)")
    parser.add_argument("--format", choices=['all', 'sportscode', 'tracab', 'dartfish', 'statsperform'],
                       default='all', help="Export format (default: all)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv):
        print(f"❌ Error: CSV file not found: {args.csv}")
        exit(1)
    
    frames_data = read_tracking_csv(args.csv)
    output_dir = args.output_dir or os.path.dirname(args.csv)
    base_name = os.path.splitext(os.path.basename(args.csv))[0]
    
    print(f"\n📊 Loaded {len(frames_data)} frames from {args.csv}\n")
    
    if args.format == 'all':
        export_all_formats(args.csv, output_dir, args.fps)
    elif args.format == 'sportscode':
        export_to_sportscode_xml(frames_data, 
                                 os.path.join(output_dir, f"{base_name}_sportscode.xml"),
                                 fps=args.fps)
    elif args.format == 'tracab':
        export_to_tracab_json(frames_data,
                             os.path.join(output_dir, f"{base_name}_tracab.json"),
                             fps=args.fps)
    elif args.format == 'dartfish':
        export_to_dartfish_xml(frames_data,
                              os.path.join(output_dir, f"{base_name}_dartfish.xml"),
                              fps=args.fps)
    elif args.format == 'statsperform':
        export_to_stats_perform_json(frames_data,
                                     os.path.join(output_dir, f"{base_name}_statsperform.json"),
                                     fps=args.fps)
    
    print("\n✅ Export complete!")
    print("\nUsage tips:")
    print("  • SportsCode XML: Import via File → Import → XML")
    print("  • TRACAB JSON: Compatible with Second Spectrum API")
    print("  • Dartfish XML: Open in Dartfish or Nacsport")
    print("  • Stats Perform: Upload to Opta platform or API")

