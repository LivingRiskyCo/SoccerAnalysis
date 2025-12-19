import cv2
import numpy as np
import argparse
from collections import deque
import imutils

def track_ball(input_path, output_path, buffer=64):
    """
    Track soccer ball and overlay path trail on video.
    
    Args:
        input_path: Path to input video file
        output_path: Path to output tracked video file
        buffer: Length of ball trail (default: 64)
    """
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
    
    # Ball trail points
    pts = deque(maxlen=buffer)
    
    frame_count = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"Processing {total_frames} frames...")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # HSV range for white ball (tune for your lighting conditions)
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])
        
        mask = cv2.inRange(hsv, lower_white, upper_white)
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)
        
        # Find contours
        cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        center = None
        
        if len(cnts) > 0:
            # Find the largest contour
            c = max(cnts, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            
            # Only proceed if the ball meets minimum size criteria
            if radius > 10:  # Minimum ball size (tune based on your video)
                # Draw circle around ball
                cv2.circle(frame, (int(x), int(y)), int(radius), (0, 255, 0), 2)
                center = (int(x), int(y))
                pts.appendleft(center)
        
        # Draw trail
        for i in range(1, len(pts)):
            # Thickness decreases as trail gets older
            thickness = int(np.sqrt(buffer / float(i + 1)) * 2)
            cv2.line(frame, pts[i - 1], pts[i], (0, 0, 255), thickness)
        
        out.write(frame)
        
        frame_count += 1
        if frame_count % 100 == 0:
            progress = (frame_count / total_frames) * 100
            print(f"Progress: {progress:.1f}% ({frame_count}/{total_frames} frames)")
    
    cap.release()
    out.release()
    print(f"Ball-tracked video saved: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Track soccer ball and overlay path trail")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output tracked video path")
    parser.add_argument("--buffer", type=int, default=64, help="Trail length (default: 64)")
    args = parser.parse_args()
    track_ball(args.input, args.output, args.buffer)


