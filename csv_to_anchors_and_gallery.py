"""
Enhanced script to convert CSV tracking data to anchor frames AND update player gallery with Re-ID features.

This script:
1. Reads a CSV file with player names (manually edited)
2. Creates anchor frames with 1.00 confidence
3. Extracts Re-ID features (body, jersey, foot) from the video
4. Updates the player gallery with all features

Usage:
    python csv_to_anchors_and_gallery.py <csv_file> <video_path> [--interval N] [--update-gallery]

Example:
    python csv_to_anchors_and_gallery.py "20251001_184229_analyzed_tracking_data.csv" "C:/Users/nerdw/Videos/20251001_184229.mp4" --update-gallery
"""

import csv
import json
import os
import sys
import cv2
import numpy as np
from collections import defaultdict
from pathlib import Path

# Import Re-ID and gallery modules
try:
    from reid_tracker import ReIDTracker
    from player_gallery import PlayerGallery
    try:
        import supervision as sv
        SUPERVISION_AVAILABLE = True
    except ImportError:
        SUPERVISION_AVAILABLE = False
        print("⚠ Supervision not available - Re-ID feature extraction will be limited")
except ImportError as e:
    print(f"⚠ Warning: Could not import Re-ID modules: {e}")
    ReIDTracker = None
    PlayerGallery = None
    SUPERVISION_AVAILABLE = False


def extract_reid_features_from_video(video_path, frame_num, bbox, reid_tracker):
    """
    Extract Re-ID features from a specific frame and bbox in the video.
    
    Args:
        video_path: Path to video file
        frame_num: Frame number to extract
        bbox: Bounding box [x1, y1, x2, y2]
        reid_tracker: ReIDTracker instance
    
    Returns:
        Tuple of (body_features, jersey_features, foot_features) or (None, None, None) if failed
    """
    if reid_tracker is None or not SUPERVISION_AVAILABLE:
        return None, None, None
    
    try:
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"  ⚠ Could not open video: {video_path}")
            return None, None, None
        
        # Seek to frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            print(f"  ⚠ Could not read frame {frame_num} from video")
            return None, None, None
        
        # Clamp bbox to frame bounds
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(int(x1), w - 1))
        y1 = max(0, min(int(y1), h - 1))
        x2 = max(x1 + 1, min(int(x2), w))
        y2 = max(y1 + 1, min(int(y2), h))
        
        if x2 <= x1 or y2 <= y1:
            print(f"  ⚠ Invalid bbox for frame {frame_num}: {bbox}")
            return None, None, None
        
        # Create detections object
        detections = sv.Detections(
            xyxy=np.array([[x1, y1, x2, y2]], dtype=np.float32),
            confidence=np.array([1.0]),
            class_id=np.array([0])
        )
        
        # Extract features
        body_features = None
        jersey_features = None
        foot_features = None
        
        # Extract body features (general Re-ID)
        try:
            body_feat = reid_tracker.extract_features(frame, detections)
            if body_feat is not None and len(body_feat) > 0:
                body_features = body_feat[0]
        except Exception as e:
            print(f"  ⚠ Body feature extraction failed for frame {frame_num}: {e}")
        
        # Extract jersey features
        try:
            if hasattr(reid_tracker, 'extract_jersey_features'):
                jersey_feat = reid_tracker.extract_jersey_features(frame, detections)
                if jersey_feat is not None and len(jersey_feat) > 0:
                    jersey_features = jersey_feat[0]
        except Exception as e:
            print(f"  ⚠ Jersey feature extraction failed for frame {frame_num}: {e}")
        
        # Extract foot features
        try:
            if hasattr(reid_tracker, 'extract_foot_features'):
                foot_feat = reid_tracker.extract_foot_features(frame, detections)
                if foot_feat is not None and len(foot_feat) > 0:
                    foot_features = foot_feat[0]
        except Exception as e:
            print(f"  ⚠ Foot feature extraction failed for frame {frame_num}: {e}")
        
        return body_features, jersey_features, foot_features
        
    except Exception as e:
        print(f"  ⚠ Error extracting features from frame {frame_num}: {e}")
        return None, None, None


def convert_csv_to_anchors_and_gallery(csv_path, video_path, output_json=None, 
                                      player_gallery_path="player_gallery.json",
                                      frame_interval=30, update_gallery=True):
    """
    Convert CSV tracking data to anchor frames and update player gallery.
    
    Args:
        csv_path: Path to tracking CSV file
        video_path: Path to video file
        output_json: Optional output JSON path
        player_gallery_path: Path to player gallery JSON
        frame_interval: Only process every Nth frame (default: 30)
        update_gallery: Whether to extract Re-ID features and update gallery
    
    Returns:
        Path to created JSON file
    """
    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        return None
    
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return None
    
    # Initialize Re-ID tracker and gallery if updating gallery
    reid_tracker = None
    player_gallery = None
    
    if update_gallery:
        print("🔧 Initializing Re-ID tracker and player gallery...")
        try:
            if ReIDTracker is not None:
                reid_tracker = ReIDTracker(feature_dim=128, similarity_threshold=0.6, use_torchreid=True)
                print("✓ Re-ID tracker initialized")
            else:
                print("⚠ Re-ID tracker not available - skipping gallery updates")
                update_gallery = False
        except Exception as e:
            print(f"⚠ Could not initialize Re-ID tracker: {e}")
            update_gallery = False
        
        try:
            if PlayerGallery is not None:
                player_gallery = PlayerGallery()
                player_gallery.load_gallery(player_gallery_path)
                print(f"✓ Loaded player gallery: {len(player_gallery.list_players())} players")
            else:
                print("⚠ Player gallery not available - skipping gallery updates")
                update_gallery = False
        except Exception as e:
            print(f"⚠ Could not load player gallery: {e}")
            update_gallery = False
    
    # Group tracks by frame and player
    frames_data = defaultdict(list)  # {frame_num: [{track_id, player_name, team, bbox, jersey_number}]}
    player_frames = defaultdict(list)  # {player_name: [(frame_num, bbox, track_id, team, jersey_number), ...]}
    
    # Track ID generation: If CSV has invalid track IDs (-1), generate unique IDs based on player_name + position
    # Format: {player_name: {position_hash: track_id}}
    player_track_id_map = {}  # {player_name: {position_key: track_id}}
    next_track_id = 1  # Start from 1 (0 is reserved, negative is invalid)
    
    # Default bbox size (if not in CSV)
    default_w = 80
    default_h = 160
    
    print(f"📖 Reading CSV: {csv_path}")
    
    total_rows = 0
    tracks_processed = 0
    skipped_no_frame = 0
    skipped_no_track_id = 0
    skipped_no_position = 0
    skipped_no_name = 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Check columns
            fieldnames = reader.fieldnames
            if fieldnames:
                print(f"  📊 CSV columns: {', '.join(fieldnames[:10])}{'...' if len(fieldnames) > 10 else ''}")
                has_player_name = 'player_name' in fieldnames
                has_frame = 'frame' in fieldnames or 'frame_num' in fieldnames
                has_track_id = 'track_id' in fieldnames or 'player_id' in fieldnames
                has_bbox = 'x1' in fieldnames and 'y1' in fieldnames and 'x2' in fieldnames and 'y2' in fieldnames
                print(f"  ✓ Has 'player_name': {has_player_name}")
                print(f"  ✓ Has 'frame': {has_frame}")
                print(f"  ✓ Has 'track_id': {has_track_id}")
                print(f"  ✓ Has bbox columns (x1/y1/x2/y2): {has_bbox}")
            
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
                
                # Apply frame interval filtering
                if frame_interval > 1 and frame_num % frame_interval != 0:
                    continue
                
                # Get player name FIRST (REQUIRED - skip if missing)
                player_name = row.get('player_name', row.get('name', '')).strip()
                if not player_name or player_name.startswith('Unknown') or player_name == '':
                    skipped_no_name += 1
                    continue
                
                # Get bbox (try multiple sources)
                bbox = None
                
                # Priority 1: Direct bbox columns
                if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                    try:
                        bbox = [float(row['x1']), float(row['y1']), float(row['x2']), float(row['y2'])]
                    except (ValueError, TypeError):
                        pass
                
                # Priority 2: Center point (convert to bbox)
                if bbox is None:
                    player_x = row.get('player_x', row.get('x', row.get('center_x', '')))
                    player_y = row.get('player_y', row.get('y', row.get('center_y', '')))
                    if player_x and player_y:
                        try:
                            px = float(player_x)
                            py = float(player_y)
                            bbox = [px - default_w/2, py - default_h/2, px + default_w/2, py + default_h/2]
                        except (ValueError, TypeError):
                            pass
                
                if bbox is None:
                    skipped_no_position += 1
                    continue
                
                # Get track_id (with fallback generation if invalid)
                track_id = None
                track_id_val = row.get('track_id', row.get('player_id', row.get('id', '')))
                
                if track_id_val and str(track_id_val).strip() != '':
                    try:
                        track_id = int(float(track_id_val))
                        # Skip invalid track IDs (-1 typically means "no track" or "unassigned")
                        if track_id < 0:
                            track_id = None  # Will generate below
                    except (ValueError, TypeError):
                        track_id = None  # Will generate below
                
                # CRITICAL FIX: If track_id is invalid or missing, generate unique ID based on player_name + position
                # This handles CSVs where all track_ids are -1 (invalid)
                if track_id is None or track_id < 0:
                    # Generate position-based key (round to nearest 50 pixels to group nearby positions)
                    center_x = (bbox[0] + bbox[2]) / 2
                    center_y = (bbox[1] + bbox[3]) / 2
                    position_key = f"{int(center_x // 50)}_{int(center_y // 50)}"
                    
                    # Check if we've seen this player at this position before
                    if player_name not in player_track_id_map:
                        player_track_id_map[player_name] = {}
                    
                    if position_key not in player_track_id_map[player_name]:
                        # New track for this player at this position
                        player_track_id_map[player_name][position_key] = next_track_id
                        track_id = next_track_id
                        next_track_id += 1
                    else:
                        # Use existing track ID for this player at this position
                        track_id = player_track_id_map[player_name][position_key]
                
                # Get team and jersey number
                team = row.get('team', row.get('player_team', row.get('team_name', ''))).strip() or None
                jersey_number = row.get('jersey_number', row.get('jersey', '')).strip() or None
                
                # Create anchor frame entry
                anchor_entry = {
                    "track_id": track_id,
                    "player_name": player_name,
                    "team": team or "",
                    "bbox": bbox,
                    "confidence": 1.00
                }
                
                if jersey_number:
                    anchor_entry["jersey_number"] = jersey_number
                
                frames_data[frame_num].append(anchor_entry)
                player_frames[player_name].append((frame_num, bbox, track_id, team, jersey_number))
                tracks_processed += 1
                
                if tracks_processed % 1000 == 0:
                    print(f"  Processed {tracks_processed} track entries...")
        
        print(f"✓ Processed {tracks_processed} track entries from {total_rows} CSV rows")
        if skipped_no_frame > 0:
            print(f"  ⚠ Skipped {skipped_no_frame} rows: missing frame number")
        if skipped_no_track_id > 0:
            print(f"  ⚠ Skipped {skipped_no_track_id} rows: missing track_id")
        if skipped_no_position > 0:
            print(f"  ⚠ Skipped {skipped_no_position} rows: missing position/bbox")
        if skipped_no_name > 0:
            print(f"  ⚠ Skipped {skipped_no_name} rows: missing player_name")
        print(f"✓ Found {len(frames_data)} frames with tracked players")
        print(f"✓ Found {len(player_frames)} unique players")
        
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    if not frames_data:
        print("❌ No anchor frames created! Check that CSV has 'player_name' column with valid names.")
        return None
    
    # Update player gallery with Re-ID features
    if update_gallery and reid_tracker and player_gallery:
        print(f"\n🎨 Extracting Re-ID features and updating player gallery...")
        print(f"  Processing {len(player_frames)} players...")
        
        players_updated = 0
        players_created = 0
        features_extracted = 0
        
        for player_name, frames_list in player_frames.items():
            print(f"\n  👤 Processing: {player_name} ({len(frames_list)} frames)")
            
            # Collect features from multiple frames (use best quality frames)
            all_body_features = []
            all_jersey_features = []
            all_foot_features = []
            best_frame = None
            best_bbox = None
            best_team = None
            best_jersey = None
            
            # Process up to 10 frames per player (to avoid too many extractions)
            frames_to_process = frames_list[:10] if len(frames_list) > 10 else frames_list
            
            for frame_num, bbox, track_id, team, jersey_number in frames_to_process:
                body_feat, jersey_feat, foot_feat = extract_reid_features_from_video(
                    video_path, frame_num, bbox, reid_tracker
                )
                
                if body_feat is not None:
                    all_body_features.append(body_feat)
                    features_extracted += 1
                    # Use first successful frame as reference
                    if best_frame is None:
                        best_frame = frame_num
                        best_bbox = bbox
                        best_team = team
                        best_jersey = jersey_number
                
                if jersey_feat is not None:
                    all_jersey_features.append(jersey_feat)
                
                if foot_feat is not None:
                    all_foot_features.append(foot_feat)
            
            if not all_body_features:
                print(f"    ⚠ No features extracted for {player_name} - skipping gallery update")
                continue
            
            # Average features (better than single frame)
            avg_body_features = np.mean(all_body_features, axis=0) if all_body_features else None
            avg_jersey_features = np.mean(all_jersey_features, axis=0) if all_jersey_features else None
            avg_foot_features = np.mean(all_foot_features, axis=0) if all_foot_features else None
            
            # Check if player exists
            player_id = None
            for pid, pname in player_gallery.list_players():
                if pname.lower() == player_name.lower():
                    player_id = pid
                    break
            
            # Create reference frame
            reference_frame = {
                'video_path': video_path,
                'frame_num': best_frame,
                'bbox': best_bbox,
                'confidence': 1.00,
                'similarity': 1.00
            }
            
            if player_id:
                # Update existing player
                player_gallery.update_player(
                    player_id=player_id,
                    features=avg_body_features,
                    body_features=avg_body_features,
                    jersey_features=avg_jersey_features,
                    foot_features=avg_foot_features,
                    reference_frame=reference_frame,
                    jersey_number=best_jersey,
                    team=best_team
                )
                players_updated += 1
                print(f"    ✓ Updated gallery for {player_name} ({len(all_body_features)} frames)")
            else:
                # Create new player
                player_id = player_gallery.add_player(
                    name=player_name,
                    features=avg_body_features,
                    body_features=avg_body_features,
                    jersey_features=avg_jersey_features,
                    foot_features=avg_foot_features,
                    reference_frame=reference_frame,
                    jersey_number=best_jersey,
                    team=best_team
                )
                players_created += 1
                print(f"    ✓ Created gallery entry for {player_name} ({len(all_body_features)} frames)")
        
        # Save gallery
        try:
            player_gallery.save_gallery()
            print(f"\n✓ Gallery updated: {players_updated} updated, {players_created} created, {features_extracted} feature extractions")
        except Exception as e:
            print(f"⚠ Could not save gallery: {e}")
    
    # Create anchor frames structure
    anchor_frames = {}
    for frame_num, entries in frames_data.items():
        anchor_frames[str(frame_num)] = entries
    
    # Determine output path
    if output_json is None:
        video_name = Path(video_path).stem
        output_dir = Path(csv_path).parent
        output_json = output_dir / f"PlayerTagsSeed-{video_name}.json"
    
    # Create full seed config structure
    seed_config = {
        "video_path": video_path,
        "approved_mappings": {},
        "anchor_frames": anchor_frames
    }
    
    # Populate approved_mappings from anchor frames
    for frame_num, entries in frames_data.items():
        for entry in entries:
            track_id_str = str(entry['track_id'])
            if track_id_str not in seed_config['approved_mappings']:
                seed_config['approved_mappings'][track_id_str] = (
                    entry['player_name'],
                    entry.get('team', '')
                )
    
    # Save to JSON
    try:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(seed_config, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Saved anchor frames to: {output_json}")
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
        print("  python csv_to_anchors_and_gallery.py <csv_file> <video_path> [output_json] [--interval N] [--update-gallery]")
        print("\nOptions:")
        print("  --interval N      Only process every Nth frame (default: 30 = ~1 per second at 30fps)")
        print("  --update-gallery  Extract Re-ID features and update player gallery (default: True)")
        print("\nExample:")
        print('  python csv_to_anchors_and_gallery.py "20251001_184229_analyzed_tracking_data.csv" "C:/Users/nerdw/Videos/20251001_184229.mp4" --update-gallery')
        sys.exit(1)
    
    csv_path = sys.argv[1]
    video_path = sys.argv[2]
    output_json = None
    frame_interval = 30
    update_gallery = True
    
    # Parse optional arguments
    i = 3
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--interval' and i + 1 < len(sys.argv):
            frame_interval = int(sys.argv[i + 1])
            i += 2
        elif arg == '--update-gallery':
            update_gallery = True
            i += 1
        elif arg == '--no-update-gallery':
            update_gallery = False
            i += 1
        elif not arg.startswith('--'):
            output_json = arg
            i += 1
        else:
            i += 1
    
    result = convert_csv_to_anchors_and_gallery(
        csv_path, video_path, output_json,
        frame_interval=frame_interval,
        update_gallery=update_gallery
    )
    
    if result:
        print(f"\n✅ Success! Anchor frames saved to: {result}")
        if update_gallery:
            print("✅ Player gallery updated with Re-ID features")
        print("\nNext steps:")
        print("  1. The anchor frames will be automatically loaded during analysis")
        print("  2. They will be used as ground truth for Re-ID, metrics, and routing")
        print("  3. All tracks will have 1.00 confidence (highest priority)")
        print("  4. Player gallery now has updated Re-ID features for better cross-video recognition")
    else:
        print("\n❌ Failed to convert CSV to anchor frames")
        sys.exit(1)


if __name__ == "__main__":
    main()

