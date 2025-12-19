import cv2
from ultralytics import YOLO
import supervision as sv
import numpy as np
import argparse
import matplotlib.pyplot as plt

def track_players(input_path, output_path):
    """
    Detect and track players using YOLOv8, generate heatmap.
    
    Args:
        input_path: Path to input video file
        output_path: Path to output tracked video file
    """
    # Load YOLOv8 model (will download automatically on first run)
    print("Loading YOLOv8 model...")
    model = YOLO('yolov8n.pt')  # Nano model for speed; use 'yolov8s.pt' or 'yolov8m.pt' for better accuracy
    
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file {input_path}")
        return
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # Initialize tracker
    byte_tracker = sv.ByteTrack()
    
    # Annotators
    box_annotator = sv.BoxAnnotator()
    label_annotator = sv.LabelAnnotator()
    
    # Store positions for heatmap
    heatmap_data = []
    
    frame_count = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"Processing {total_frames} frames...")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Run YOLO detection (class 0 = person)
        results = model(frame, classes=[0], verbose=False)
        detections = sv.Detections.from_ultralytics(results[0])
        
        # Update tracker
        detections = byte_tracker.update_with_detections(detections)
        
        # Create labels with track ID and confidence
        labels = []
        for track_id, conf in zip(detections.tracker_id, detections.confidence):
            if track_id is not None:
                labels.append(f"#{track_id} {conf:.2f}")
            else:
                labels.append(f"{conf:.2f}")
        
        # Annotate frame
        frame = box_annotator.annotate(scene=frame, detections=detections)
        frame = label_annotator.annotate(scene=frame, detections=detections, labels=labels)
        
        # Collect positions for heatmap (center of bounding boxes)
        if len(detections.xyxy) > 0:
            centers = (detections.xyxy[:, :2] + detections.xyxy[:, 2:]) / 2
            heatmap_data.extend(centers.tolist())
        
        out.write(frame)
        
        frame_count += 1
        if frame_count % 100 == 0:
            progress = (frame_count / total_frames) * 100
            print(f"Progress: {progress:.1f}% ({frame_count}/{total_frames} frames)")
    
    cap.release()
    out.release()
    
    # Generate heatmap
    if heatmap_data:
        print("Generating heatmap...")
        heatmap_data = np.array(heatmap_data)
        plt.figure(figsize=(width/100, height/100), dpi=100)
        plt.hist2d(heatmap_data[:, 0], heatmap_data[:, 1], bins=50, cmap='hot')
        plt.colorbar(label='Player Density')
        plt.xlabel('X Position (pixels)')
        plt.ylabel('Y Position (pixels)')
        plt.title('Player Position Heatmap')
        plt.savefig('player_heatmap.png', dpi=100, bbox_inches='tight')
        plt.close()
        print("Heatmap saved: player_heatmap.png")
    
    print(f"Player-tracked video saved: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect and track players using YOLOv8, generate heatmap")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output tracked video path")
    args = parser.parse_args()
    track_players(args.input, args.output)


