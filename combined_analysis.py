"""
Combined Soccer Analysis Script
Combines dewarping, ball tracking, and player tracking into one pipeline.
Exports tracking data to CSV for further analysis.
"""

import cv2
import numpy as np
import argparse
from collections import deque
import csv
from datetime import datetime
import os

# Dewarping uses OpenCV (no external dependency needed)
DEFISHEYE_AVAILABLE = True

try:
    from ultralytics import YOLO
    import supervision as sv
    import imutils
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: YOLO dependencies not available. Player tracking will be skipped.")

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Heatmap generation will be skipped.")


def track_ball_in_frame(frame, pts, buffer=64, min_radius=5, max_radius=50):
    """
    Track ball in a single frame using improved color-based detection.
    Supports pink and white balls. Filters out false positives by checking size, shape, and circularity.
    """
    # Convert to HSV for better color detection
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # HSV range for white parts of ball
    lower_white = np.array([0, 0, 200])
    upper_white = np.array([180, 30, 255])
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    
    # HSV range for pink parts of ball
    # Pink in HSV: H=150-170 (magenta/pink), S=50-255, V=50-255
    lower_pink = np.array([150, 50, 50])
    upper_pink = np.array([170, 255, 255])
    mask_pink = cv2.inRange(hsv, lower_pink, upper_pink)
    
    # Combine white and pink masks
    mask = cv2.bitwise_or(mask_white, mask_pink)
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)
    
    # Find contours
    cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if YOLO_AVAILABLE:
        cnts = imutils.grab_contours(cnts)
    else:
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]
    
    center = None
    ball_detected = False
    
    # Filter contours by size, shape, and circularity
    ball_candidates = []
    for c in cnts:
        area = cv2.contourArea(c)
        if area < 20:  # Too small
            continue
            
        ((x, y), radius) = cv2.minEnclosingCircle(c)
        
        # Filter by size (ball should be small relative to field)
        if radius < min_radius or radius > max_radius:
            continue
        
        # Check circularity (ball should be roughly circular)
        perimeter = cv2.arcLength(c, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        
        # Ball should be fairly circular (circularity > 0.6)
        if circularity < 0.6:
            continue
        
        # Check aspect ratio (ball should be roughly circular, not elongated)
        (x_rect, y_rect, w_rect, h_rect) = cv2.boundingRect(c)
        aspect_ratio = float(w_rect) / h_rect if h_rect > 0 else 0
        
        # Ball should be roughly square/circular (aspect ratio between 0.6 and 1.6)
        if aspect_ratio < 0.6 or aspect_ratio > 1.6:
            continue
        
        # Score candidate: prefer circular, medium-sized objects
        score = circularity * (1.0 - abs(1.0 - aspect_ratio))
        ball_candidates.append((score, (x, y), radius, c))
    
    # Select best candidate (most circular, medium-sized)
    if len(ball_candidates) > 0:
        # Sort by score (higher is better)
        ball_candidates.sort(key=lambda x: x[0], reverse=True)
        score, (x, y), radius, c = ball_candidates[0]
        
        # Double-check size is reasonable
        if min_radius <= radius <= max_radius:
            cv2.circle(frame, (int(x), int(y)), int(radius), (0, 255, 0), 2)
            cv2.circle(frame, (int(x), int(y)), 5, (0, 255, 0), -1)
            center = (int(x), int(y))
            pts.appendleft(center)
            ball_detected = True
    
    # Draw trail
    for i in range(1, len(pts)):
        # Thickness decreases as trail gets older
        thickness = int(np.sqrt(buffer / float(i + 1)) * 2)
        cv2.line(frame, pts[i - 1], pts[i], (0, 0, 255), thickness)
    
    return frame, center, ball_detected


def calculate_possession(ball_center, player_centers, frame_width, frame_height):
    """
    Calculate which player is closest to the ball (possession indicator).
    Returns player ID and distance to ball.
    """
    if ball_center is None or len(player_centers) == 0:
        return None, None
    
    min_distance = float('inf')
    closest_player_id = None
    
    for player_id, player_center in player_centers.items():
        if player_center is not None:
            distance = np.sqrt(
                (ball_center[0] - player_center[0]) ** 2 +
                (ball_center[1] - player_center[1]) ** 2
            )
            if distance < min_distance:
                min_distance = distance
                closest_player_id = player_id
    
    # Normalize distance by frame diagonal
    frame_diagonal = np.sqrt(frame_width ** 2 + frame_height ** 2)
    normalized_distance = min_distance / frame_diagonal if frame_diagonal > 0 else 0
    
    return closest_player_id, normalized_distance


def combined_analysis(input_path, output_path, 
                     dewarp=False, track_ball_flag=True, track_players_flag=True,
                     export_csv=True, buffer=64):
    """
    Combined analysis pipeline: dewarp, track ball, track players.
    
    Args:
        input_path: Path to input video
        output_path: Path to output video
        dewarp: Whether to apply dewarping
        track_ball_flag: Whether to track ball
        track_players_flag: Whether to track players
        export_csv: Whether to export tracking data to CSV
        buffer: Ball trail buffer length
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file {input_path}")
        return
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Initialize dewarping if requested (using OpenCV)
    dewarp_maps = None
    if dewarp and DEFISHEYE_AVAILABLE:
        # Simplified fisheye undistortion
        center_x, center_y = width / 2, height / 2
        ifov_rad = np.radians(120)
        ofov_rad = np.radians(90)
        focal_length = width / (2 * np.tan(ifov_rad / 2))
        
        K = np.array([[focal_length, 0, center_x],
                      [0, focal_length, center_y],
                      [0, 0, 1]], dtype=np.float32)
        
        D = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        
        new_focal = width / (2 * np.tan(ofov_rad / 2))
        new_K, roi = cv2.getOptimalNewCameraMatrix(K, D, (width, height), 1, (width, height))
        
        # Precompute undistortion maps
        dewarp_maps = cv2.fisheye.initUndistortRectifyMap(K, D, np.eye(3), new_K, (width, height), cv2.CV_16SC2)
    
    # Initialize YOLO model if player tracking is enabled
    model = None
    byte_tracker = None
    box_annotator = None
    label_annotator = None
    if track_players_flag and YOLO_AVAILABLE:
        # Try YOLOv11 first (faster and more efficient), fallback to YOLOv8
        try:
            print("Loading YOLOv11 model (faster, more efficient)...")
            model = YOLO('yolo11n.pt')
            print("✓ YOLOv11 loaded successfully!")
        except Exception as e:
            print(f"YOLOv11 not available ({e}), using YOLOv8...")
            model = YOLO('yolov8n.pt')
            print("✓ YOLOv8 loaded successfully!")
        byte_tracker = sv.ByteTrack()
        box_annotator = sv.BoxAnnotator()
        label_annotator = sv.LabelAnnotator()
    
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # Tracking data storage
    ball_pts = deque(maxlen=buffer) if track_ball_flag else None
    tracking_data = []
    heatmap_data = []
    
    # CSV file setup
    csv_file = None
    csv_writer = None
    if export_csv:
        csv_filename = output_path.replace('.mp4', '_tracking_data.csv')
        csv_file = open(csv_filename, 'w', newline='')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['frame', 'timestamp', 'ball_x', 'ball_y', 'ball_detected',
                            'player_id', 'player_x', 'player_y', 'confidence',
                            'possession_player_id', 'distance_to_ball'])
    
    print(f"Processing {total_frames} frames...")
    frame_count = 0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        timestamp = frame_count / fps if fps > 0 else 0
        
        # Apply dewarping if requested
        if dewarp and dewarp_maps is not None:
            map1, map2 = dewarp_maps
            frame = cv2.remap(frame, map1, map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        
        ball_center = None
        ball_detected = False
        player_centers = {}
        
        # Track ball
        if track_ball_flag and ball_pts is not None:
            frame, ball_center, ball_detected = track_ball_in_frame(frame, ball_pts, buffer, min_radius=5, max_radius=50)
        
        # Track players
        if track_players_flag and model is not None:
            results = model(frame, classes=[0], verbose=False)
            detections = sv.Detections.from_ultralytics(results[0])
            detections = byte_tracker.update_with_detections(detections)
            
            # Create labels
            labels = []
            for track_id, conf in zip(detections.tracker_id, detections.confidence):
                if track_id is not None:
                    labels.append(f"#{track_id} {conf:.2f}")
                else:
                    labels.append(f"{conf:.2f}")
            
            # Annotate frame
            frame = box_annotator.annotate(scene=frame, detections=detections)
            frame = label_annotator.annotate(scene=frame, detections=detections, labels=labels)
            
            # Extract player centers
            if len(detections.xyxy) > 0:
                centers = (detections.xyxy[:, :2] + detections.xyxy[:, 2:]) / 2
                for i, (track_id, center) in enumerate(zip(detections.tracker_id, centers)):
                    if track_id is not None:
                        player_centers[track_id] = (int(center[0]), int(center[1]))
                        heatmap_data.append(center.tolist())
        
        # Calculate possession (distance to ball)
        possession_player_id = None
        distance_to_ball = None
        if ball_center is not None and player_centers:
            possession_player_id, distance_to_ball = calculate_possession(
                ball_center, player_centers, width, height
            )
        
        # Export to CSV
        if export_csv and csv_writer is not None:
            if player_centers:
                for player_id, (px, py) in player_centers.items():
                    conf = 0.0  # Confidence not directly available from tracker
                    csv_writer.writerow([
                        frame_count, timestamp,
                        ball_center[0] if ball_center else '', ball_center[1] if ball_center else '', ball_detected,
                        player_id, px, py, conf,
                        possession_player_id if possession_player_id == player_id else '',
                        distance_to_ball if possession_player_id == player_id else ''
                    ])
            else:
                # Write ball data even if no players detected
                csv_writer.writerow([
                    frame_count, timestamp,
                    ball_center[0] if ball_center else '', ball_center[1] if ball_center else '', ball_detected,
                    '', '', '', '', '', ''
                ])
        
        out.write(frame)
        
        frame_count += 1
        if frame_count % 100 == 0:
            progress = (frame_count / total_frames) * 100
            print(f"Progress: {progress:.1f}% ({frame_count}/{total_frames} frames)")
    
    cap.release()
    out.release()
    
    if csv_file:
        csv_file.close()
        print(f"Tracking data exported to: {csv_file.name}")
    
    # Generate heatmap
    if heatmap_data and MATPLOTLIB_AVAILABLE:
        print("Generating heatmap...")
        heatmap_data = np.array(heatmap_data)
        plt.figure(figsize=(width/100, height/100), dpi=100)
        plt.hist2d(heatmap_data[:, 0], heatmap_data[:, 1], bins=50, cmap='hot')
        plt.colorbar(label='Player Density')
        plt.xlabel('X Position (pixels)')
        plt.ylabel('Y Position (pixels)')
        plt.title('Player Position Heatmap')
        heatmap_filename = output_path.replace('.mp4', '_heatmap.png')
        plt.savefig(heatmap_filename, dpi=100, bbox_inches='tight')
        plt.close()
        print(f"Heatmap saved: {heatmap_filename}")
    
    print(f"Analysis complete! Output saved: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Combined soccer analysis: dewarp, track ball, track players"
    )
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--dewarp", action="store_true", help="Apply dewarping correction")
    parser.add_argument("--no-ball", action="store_true", help="Skip ball tracking")
    parser.add_argument("--no-players", action="store_true", help="Skip player tracking")
    parser.add_argument("--no-csv", action="store_true", help="Skip CSV export")
    parser.add_argument("--buffer", type=int, default=64, help="Ball trail length (default: 64)")
    args = parser.parse_args()
    
    combined_analysis(
        args.input, args.output,
        dewarp=args.dewarp,
        track_ball_flag=not args.no_ball,
        track_players_flag=not args.no_players,
        export_csv=not args.no_csv,
        buffer=args.buffer
    )


