"""
Player Speed Tracking & Field Coverage Analysis
Tracks player speeds (km/h) and generates top-down field coverage heatmaps
Requires calibration.npy from calibrate_field.py
"""

import cv2
import numpy as np
import argparse
import os
import time
import csv
import json
from collections import defaultdict


def load_player_names():
    """Load player name mappings from file"""
    if os.path.exists("player_names.json"):
        try:
            with open("player_names.json", 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Error: ultralytics not installed. Install with: pip install ultralytics")

try:
    import supervision as sv
    SUPERVISION_AVAILABLE = True
except ImportError:
    SUPERVISION_AVAILABLE = False
    print("Error: supervision not installed. Install with: pip install supervision")

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Heatmap will not be generated.")

try:
    from scipy.spatial.distance import cdist
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available. Some features may be limited.")


def load_calibration():
    """Load field calibration data (supports both 4-point and 8-point modes)"""
    if not os.path.exists("calibration.npy"):
        print("Error: calibration.npy not found!")
        print("Run calibrate_field.py first to calibrate the field.")
        return None, None
    
    if not os.path.exists("field_dimensions.npy"):
        print("Warning: field_dimensions.npy not found. Using defaults (40m x 20m)")
        field_length = 40.0
        field_width = 20.0
        calibration_mode = "4-point"
    else:
        field_dims = np.load("field_dimensions.npy", allow_pickle=True).item()
        field_length = field_dims.get('length', 40.0)
        field_width = field_dims.get('width', 20.0)
        calibration_mode = field_dims.get('mode', '4-point')
    
    # Load calibration points (source points in video frame)
    src_points = np.load("calibration.npy")
    
    # Check if we have metadata for mode
    num_points = len(src_points)
    if os.path.exists("calibration_metadata.npy"):
        metadata = np.load("calibration_metadata.npy", allow_pickle=True).item()
        calibration_mode = metadata.get('mode', '4-point')
        num_points = metadata.get('num_points', len(src_points))
    
    # Define destination points (real-world coordinates in meters)
    if num_points == 4 or calibration_mode == "4-point":
        # Standard 4-point rectangle
        dst_points = np.array([
            [0, 0],                    # Top-Left
            [field_length, 0],         # Top-Right
            [field_length, field_width], # Bottom-Right
            [0, field_width]           # Bottom-Left
        ], dtype=np.float32)
        
        # Calculate homography matrix (4-point)
        H = cv2.getPerspectiveTransform(src_points, dst_points)
    else:
        # 8-point trapezoidal - use findHomography for better accuracy
        # Calculate actual dimensions based on perspective
        # Top width may be narrower in perspective view
        top_width = field_width * 0.9  # Adjust based on perspective
        bottom_width = field_width
        
        dst_points = np.array([
            [0, 0],                          # Top-Left
            [field_length, 0],               # Top-Right
            [field_length, bottom_width],    # Bottom-Right
            [0, bottom_width],               # Bottom-Left
            [field_length/2, 0],            # Top-Mid
            [field_length, field_width/2],  # Right-Mid
            [field_length/2, bottom_width], # Bottom-Mid
            [0, field_width/2]              # Left-Mid
        ], dtype=np.float32)
        
        # Use RANSAC for robust homography estimation (better for 8 points)
        H, _ = cv2.findHomography(src_points, dst_points, cv2.RANSAC, 5.0)
    
    print(f"Calibration loaded:")
    print(f"  Mode: {calibration_mode}")
    print(f"  Points: {num_points}")
    print(f"  Field size: {field_length}m x {field_width}m")
    print(f"  Homography matrix calculated")
    
    return H, (field_length, field_width)


def transform_point_to_field(point_px, H):
    """Transform pixel coordinates to real-world field coordinates (meters)"""
    point_3d = np.array([[[point_px[0], point_px[1]]]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(point_3d, H)[0][0]
    return transformed


def calculate_speed(p1_m, p2_m, time_seconds, use_mph=False):
    """Calculate speed in km/h or mph from two points and time"""
    if time_seconds <= 0:
        return 0.0, 0.0
    
    distance_m = np.linalg.norm(p2_m - p1_m)
    speed_ms = distance_m / time_seconds
    speed_kmh = speed_ms * 3.6  # Convert m/s to km/h
    speed_mph = speed_ms * 2.237  # Convert m/s to mph
    
    if use_mph:
        return speed_mph, distance_m
    return speed_kmh, distance_m


def load_team_color_config():
    """Load team color configuration from file if available"""
    config_file = "team_color_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load team color config: {e}")
    return None


def classify_player_team(frame, bbox, team_colors):
    """Classify player team based on jersey color"""
    if not team_colors:
        return None
    
    x1, y1, x2, y2 = bbox
    # Sample from upper torso area (where jersey is most visible)
    roi_y1 = int(y1 + (y2 - y1) * 0.1)  # Top 10% of bbox
    roi_y2 = int(y1 + (y2 - y1) * 0.5)   # Top 50% of bbox
    roi_x1 = int(x1)
    roi_x2 = int(x2)
    
    roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
    if roi.size == 0:
        return None
    
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    # Count pixels matching each team color
    team_scores = {}
    for team_key, team_data in team_colors.items():
        if not team_data.get("hsv_ranges"):
            continue
        
        r = team_data["hsv_ranges"]
        if "lower" in r:
            lower = np.array(r["lower"])
            upper = np.array(r["upper"])
            mask = cv2.inRange(hsv_roi, lower, upper)
        else:  # Two ranges for red
            lower1 = np.array(r["lower1"])
            upper1 = np.array(r["upper1"])
            lower2 = np.array(r["lower2"])
            upper2 = np.array(r["upper2"])
            mask1 = cv2.inRange(hsv_roi, lower1, upper1)
            mask2 = cv2.inRange(hsv_roi, lower2, upper2)
            mask = cv2.bitwise_or(mask1, mask2)
        
        team_scores[team_key] = np.sum(mask > 0)
    
    # Return team with highest score
    if team_scores:
        return max(team_scores, key=team_scores.get)
    return None


def track_speed_coverage(input_path, output_path, calibration_file=None, use_mph=True, sprint_threshold_mph=15.0):
    """
    Track player speeds and generate field coverage analysis
    
    Args:
        input_path: Input video path
        output_path: Output video path with speed labels
        calibration_file: Optional path to calibration file (default: calibration.npy)
    """
    if not YOLO_AVAILABLE or not SUPERVISION_AVAILABLE:
        print("Error: Required packages not installed")
        return
    
    # Load calibration
    H, field_dims = load_calibration()
    if H is None:
        return
    
    field_length, field_width = field_dims
    
    # Initialize YOLO model (try YOLOv11 first, fallback to YOLOv8)
    try:
        print("Loading YOLOv11 model...")
        model = YOLO('yolo11n.pt')
        print("✓ YOLOv11 loaded successfully!")
    except Exception as e:
        print(f"YOLOv11 not available ({e}), using YOLOv8...")
        model = YOLO('yolov8n.pt')
        print("✓ YOLOv8 loaded successfully!")
    
    # Initialize tracker
    tracker = sv.ByteTrack()
    box_annotator = sv.BoxAnnotator()
    label_annotator = sv.LabelAnnotator()
    
    # Open video
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"Error: Could not open video: {input_path}")
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_time = 1.0 / fps if fps > 0 else 0.033  # Default 30fps
    
    print(f"\nVideo: {width}x{height} @ {fps:.1f}fps")
    print(f"Total frames: {total_frames}")
    print(f"Frame time: {frame_time:.3f}s")
    
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # Load team colors if available
    team_config = load_team_color_config()
    team_colors = None
    team1_name = "Team 1"
    team2_name = "Team 2"
    if team_config:
        team_colors = team_config.get("team_colors", {})
        team1_name = team_config.get("team1_name", "Team 1")
        team2_name = team_config.get("team2_name", "Team 2")
        print(f"Team colors loaded: {team1_name} vs {team2_name}")
    
    # Tracking data
    prev_centers_m = {}  # track_id: (x_m, y_m) in previous frame
    speeds_all = []  # All speed measurements
    speeds_by_player = defaultdict(list)  # Speeds per player
    distances_by_player = defaultdict(float)  # Total distance covered per player (meters)
    paths = defaultdict(list)  # Player paths in meters
    sprint_zones = defaultdict(list)  # Sprint zones per player: [(x, y, speed), ...]
    player_teams = {}  # track_id: team (team1 or team2)
    frame_count = 0
    start_time = time.time()
    
    # CSV export
    csv_filename = output_path.replace('.mp4', '_speed_data.csv')
    csv_file = open(csv_filename, 'w', newline='')
    csv_writer = csv.writer(csv_file)
    if use_mph:
        csv_writer.writerow(['frame', 'timestamp', 'player_id', 'team', 'x_px', 'y_px', 
                            'x_m', 'y_m', 'speed_mph', 'distance_miles'])
    else:
        csv_writer.writerow(['frame', 'timestamp', 'player_id', 'team', 'x_px', 'y_px', 
                            'x_m', 'y_m', 'speed_kmh', 'distance_km'])
    
    print(f"\nProcessing {total_frames} frames...")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        timestamp = frame_count / fps if fps > 0 else 0
        
        # Detect players
        results = model(frame, classes=[0], verbose=False)  # Class 0 = person
        detections = sv.Detections.from_ultralytics(results[0])
        detections = tracker.update_with_detections(detections)
        
        current_centers_m = {}
        labels = []
        
        for i, (xyxy, track_id, conf) in enumerate(zip(detections.xyxy, 
                                                      detections.tracker_id, 
                                                      detections.confidence)):
            if track_id is None:
                continue
            
            x1, y1, x2, y2 = xyxy
            # Use foot position (bottom center) for more accurate tracking
            cx_px = (x1 + x2) / 2
            cy_px = y2  # Bottom of bounding box (feet)
            
            # Transform to field coordinates (meters)
            point_m = transform_point_to_field((cx_px, cy_px), H)
            current_centers_m[track_id] = point_m
            
            # Classify team
            team = None
            if team_colors:
                team = classify_player_team(frame, xyxy, team_colors)
                if team:
                    player_teams[track_id] = team
            
            # Get team name for display
            team_name = ""
            if track_id in player_teams:
                team = player_teams[track_id]
                team_name = team1_name if team == "team1" else team2_name
            
            # Load player names for display
            player_names = load_player_names()
            pid_str = str(int(track_id))
            display_name = player_names.get(pid_str, f"#{track_id}")
            
            # Calculate speed and distance
            speed = 0.0
            distance_frame = 0.0
            if track_id in prev_centers_m:
                speed, distance_frame = calculate_speed(prev_centers_m[track_id], point_m, frame_time, use_mph)
                speeds_all.append(speed)
                speeds_by_player[track_id].append(speed)
                distances_by_player[track_id] += distance_frame  # Accumulate distance
                
                # Check for sprint zone (speed > threshold)
                if speed > sprint_threshold_mph if use_mph else (speed > sprint_threshold_mph * 1.60934):
                    sprint_zones[track_id].append((point_m[0], point_m[1], speed))
            
            # Store path
            paths[track_id].append(point_m)
            
            # Create label with speed and team (use player name if available)
            speed_unit = "mph" if use_mph else "km/h"
            team_label = f" [{team_name}]" if team_name else ""
            
            if display_name.startswith("#"):
                # Use ID format
                if speed > 0:
                    label = f"{display_name}{team_label} | {speed:.1f} {speed_unit}"
                else:
                    label = f"{display_name}{team_label}"
            else:
                # Use player name
                if speed > 0:
                    label = f"{display_name} ({track_id}){team_label} | {speed:.1f} {speed_unit}"
                else:
                    label = f"{display_name} ({track_id}){team_label}"
            labels.append(label)
            
            # Export to CSV
            distance_total = distances_by_player[track_id]
            distance_display = distance_total * 0.000621371 if use_mph else distance_total / 1000.0  # Convert to miles or km
            distance_unit = "miles" if use_mph else "km"
            
            csv_writer.writerow([frame_count, timestamp, track_id, team_name,
                               int(cx_px), int(cy_px), 
                               float(point_m[0]), float(point_m[1]), 
                               float(speed), float(distance_display)])
        
        # Annotate frame
        frame = box_annotator.annotate(scene=frame, detections=detections)
        frame = label_annotator.annotate(scene=frame, detections=detections, labels=labels)
        
        # Write frame
        out.write(frame)
        
        prev_centers_m = current_centers_m
        frame_count += 1
        
        # Progress update
        if frame_count % 100 == 0:
            progress = (frame_count / total_frames) * 100
            elapsed = time.time() - start_time
            if elapsed > 0:
                rate = frame_count / elapsed
                eta = (total_frames - frame_count) / rate if rate > 0 else 0
                print(f"Progress: {progress:.1f}% ({frame_count}/{total_frames} frames) | "
                      f"Rate: {rate:.1f} fps | ETA: {eta/60:.1f} min")
    
    cap.release()
    out.release()
    csv_file.close()
    
    print(f"\n✓ Video saved: {output_path}")
    print(f"✓ Speed data exported: {csv_filename}")
    
    # Calculate statistics
    speed_unit = "mph" if use_mph else "km/h"
    distance_unit = "miles" if use_mph else "km"
    
    if speeds_all:
        avg_speed = np.mean(speeds_all)
        max_speed = np.max(speeds_all)
        median_speed = np.median(speeds_all)
        
        print(f"\n" + "="*60)
        print("Speed Statistics:")
        print("="*60)
        print(f"Average speed: {avg_speed:.1f} {speed_unit}")
        print(f"Median speed: {median_speed:.1f} {speed_unit}")
        print(f"Maximum speed: {max_speed:.1f} {speed_unit}")
        print(f"Total measurements: {len(speeds_all)}")
        
        # Distance covered statistics
        if distances_by_player:
            print(f"\n" + "="*60)
            print("Distance Covered:")
            print("="*60)
            total_distance_all = sum(distances_by_player.values())
            total_distance_display = total_distance_all * 0.000621371 if use_mph else total_distance_all / 1000.0
            print(f"Total distance (all players): {total_distance_display:.2f} {distance_unit}")
            
            # Per-player distance
            player_distances = [(tid, dist * 0.000621371 if use_mph else dist / 1000.0) 
                               for tid, dist in distances_by_player.items()]
            player_distances.sort(key=lambda x: x[1], reverse=True)
            
            print(f"\nTop 5 Distance Covered:")
            for i, (tid, dist) in enumerate(player_distances[:5], 1):
                team_info = f" [{player_teams.get(tid, 'Unknown')}]" if tid in player_teams else ""
                print(f"  {i}. Player ID {tid}{team_info}: {dist:.2f} {distance_unit}")
        
        # Per-player stats
        if speeds_by_player:
            print(f"\n" + "="*60)
            print("Top 5 Fastest Players (by max speed):")
            print("="*60)
            player_max_speeds = [(tid, max(speeds)) for tid, speeds in speeds_by_player.items()]
            player_max_speeds.sort(key=lambda x: x[1], reverse=True)
            for i, (tid, max_speed) in enumerate(player_max_speeds[:5], 1):
                avg = np.mean(speeds_by_player[tid])
                team_info = f" [{player_teams.get(tid, 'Unknown')}]" if tid in player_teams else ""
                print(f"  {i}. Player ID {tid}{team_info}: Max {max_speed:.1f} {speed_unit}, Avg {avg:.1f} {speed_unit}")
        
        # Sprint zone statistics
        if sprint_zones:
            print(f"\n" + "="*60)
            print(f"Sprint Zone Analysis (>{sprint_threshold_mph} {speed_unit}):")
            print("="*60)
            sprint_counts = {tid: len(zones) for tid, zones in sprint_zones.items()}
            sprint_counts_sorted = sorted(sprint_counts.items(), key=lambda x: x[1], reverse=True)
            print(f"Total sprint events: {sum(sprint_counts.values())}")
            print(f"\nTop 5 Sprinters (by number of sprint events):")
            for i, (tid, count) in enumerate(sprint_counts_sorted[:5], 1):
                team_info = f" [{player_teams.get(tid, 'Unknown')}]" if tid in player_teams else ""
                print(f"  {i}. Player ID {tid}{team_info}: {count} sprint events")
    
    # Generate field coverage visualization
    if MATPLOTLIB_AVAILABLE and paths:
        print(f"\nGenerating field coverage heatmap...")
        generate_field_coverage(paths, field_length, field_width, output_path, 
                               sprint_zones, player_teams, team1_name, team2_name, use_mph)
    
    total_time = time.time() - start_time
    print(f"\n✓ Analysis complete!")
    print(f"Total processing time: {total_time/60:.1f} minutes")
    print(f"Average rate: {total_frames/total_time:.1f} fps")


def generate_field_coverage(paths, field_length, field_width, output_path, 
                           sprint_zones=None, player_teams=None, team1_name="Team 1", 
                           team2_name="Team 2", use_mph=True):
    """Generate top-down field coverage heatmap with player paths and sprint zones"""
    if not MATPLOTLIB_AVAILABLE:
        return
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # === Left plot: Field coverage with paths ===
    ax1.set_xlim(0, field_length)
    ax1.set_ylim(0, field_width)
    ax1.set_aspect('equal')
    ax1.set_facecolor('#2d5016')  # Dark green field
    
    # Draw field lines
    ax1.add_patch(plt.Rectangle((0, 0), field_length, field_width, 
                               fill=False, edgecolor='white', linewidth=2))
    ax1.plot([field_length/2, field_length/2], [0, field_width], 
            'white', linewidth=1, linestyle='--', alpha=0.5)
    center_circle = plt.Circle((field_length/2, field_width/2), 
                              min(field_length, field_width) * 0.1,
                              fill=False, edgecolor='white', linewidth=1, linestyle='--', alpha=0.5)
    ax1.add_patch(center_circle)
    
    # Collect all points for heatmap
    all_points = []
    for path in paths.values():
        if len(path) > 0:
            all_points.extend(path)
    
    if all_points:
        all_points = np.array(all_points)
        # Generate heatmap
        ax1.hist2d(all_points[:, 0], all_points[:, 1], 
                  bins=30, cmap='hot', alpha=0.7, zorder=1)
        
        # Draw player paths (color by team if available)
        for tid, path in paths.items():
            if len(path) > 1:
                path_array = np.array(path)
                # Color by team
                if player_teams and tid in player_teams:
                    if player_teams[tid] == "team1":
                        color = 'blue'
                        alpha = 0.5
                    else:
                        color = 'red'
                        alpha = 0.5
                else:
                    color = 'yellow'
                    alpha = 0.4
                
                ax1.plot(path_array[:, 0], path_array[:, 1], 
                        alpha=alpha, linewidth=1.5, color=color, zorder=2)
    
    ax1.set_xlabel('Field Length (meters)', fontsize=12)
    ax1.set_ylabel('Field Width (meters)', fontsize=12)
    ax1.set_title('Player Field Coverage & Paths', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, color='white')
    
    # === Right plot: Sprint zones ===
    if sprint_zones:
        ax2.set_xlim(0, field_length)
        ax2.set_ylim(0, field_width)
        ax2.set_aspect('equal')
        ax2.set_facecolor('#2d5016')
        
        # Draw field lines
        ax2.add_patch(plt.Rectangle((0, 0), field_length, field_width, 
                                   fill=False, edgecolor='white', linewidth=2))
        ax2.plot([field_length/2, field_length/2], [0, field_width], 
                'white', linewidth=1, linestyle='--', alpha=0.5)
        center_circle2 = plt.Circle((field_length/2, field_width/2), 
                                    min(field_length, field_width) * 0.1,
                                    fill=False, edgecolor='white', linewidth=1, linestyle='--', alpha=0.5)
        ax2.add_patch(center_circle2)
        
        # Plot sprint zones
        for tid, zones in sprint_zones.items():
            if zones:
                zones_array = np.array(zones)
                speeds = zones_array[:, 2]
                
                # Color by team
                if player_teams and tid in player_teams:
                    if player_teams[tid] == "team1":
                        color = 'cyan'
                    else:
                        color = 'orange'
                else:
                    color = 'yellow'
                
                scatter = ax2.scatter(zones_array[:, 0], zones_array[:, 1], 
                                    c=speeds, cmap='hot', s=50, alpha=0.7, 
                                    edgecolors=color, linewidths=1, zorder=3)
        
        ax2.set_xlabel('Field Length (meters)', fontsize=12)
        ax2.set_ylabel('Field Width (meters)', fontsize=12)
        speed_unit = "mph" if use_mph else "km/h"
        ax2.set_title(f'Sprint Zones (>{15 if use_mph else 24.1} {speed_unit})', 
                     fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3, color='white')
        
        # Add colorbar for sprint speeds
        if sprint_zones:
            cbar = plt.colorbar(scatter, ax=ax2)
            cbar.set_label(f'Speed ({speed_unit})', fontsize=10)
    else:
        ax2.text(0.5, 0.5, 'No sprint zones detected', 
                ha='center', va='center', transform=ax2.transAxes, fontsize=14)
        ax2.set_title('Sprint Zones', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    # Save figure
    heatmap_filename = output_path.replace('.mp4', '_field_coverage.png')
    plt.savefig(heatmap_filename, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"✓ Field coverage heatmap saved: {heatmap_filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Track player speeds and generate field coverage analysis"
    )
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--mph", action="store_true", default=True, help="Use mph instead of km/h (default: True)")
    parser.add_argument("--kmh", action="store_true", help="Use km/h instead of mph")
    parser.add_argument("--sprint-threshold", type=float, default=15.0, 
                       help="Sprint threshold in mph (default: 15.0 mph = 24.1 km/h)")
    args = parser.parse_args()
    
    use_mph = not args.kmh if args.kmh else args.mph
    
    track_speed_coverage(args.input, args.output, use_mph=use_mph, 
                        sprint_threshold_mph=args.sprint_threshold)

