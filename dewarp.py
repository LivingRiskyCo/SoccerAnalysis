import cv2
import numpy as np
import argparse

def dewarp_video(input_path, output_path, ifov=120, ofov=90):
    """
    Dewarp video to correct fisheye distortion from ultra-wide lens.
    Uses OpenCV's fisheye undistortion (simplified approach).
    
    Args:
        input_path: Path to input video file
        output_path: Path to output dewarped video file
        ifov: Input field of view in degrees (default 120 for Samsung ultra-wide)
        ofov: Output field of view in degrees (default 90 for rectilinear)
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
    
    # Estimate camera matrix for fisheye (simplified approach)
    # For ultra-wide lens, we'll use a simple radial distortion model
    center_x, center_y = width / 2, height / 2
    focal_length = width / (2 * np.tan(np.radians(ifov / 2)))
    
    # Create camera matrix
    K = np.array([[focal_length, 0, center_x],
                  [0, focal_length, center_y],
                  [0, 0, 1]], dtype=np.float32)
    
    # Distortion coefficients (simplified - adjust if needed)
    D = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    
    # Generate new camera matrix for desired FOV
    new_focal = width / (2 * np.tan(np.radians(ofov / 2)))
    new_K, roi = cv2.getOptimalNewCameraMatrix(K, D, (width, height), 1, (width, height))
    
    # Precompute undistortion maps for efficiency
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(K, D, np.eye(3), new_K, (width, height), cv2.CV_16SC2)
    
    frame_count = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"Processing {total_frames} frames...")
    print(f"Note: This is a simplified dewarping. For best results, calibrate with checkerboard pattern.")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Dewarp frame using precomputed maps
        frame_dewarped = cv2.remap(frame, map1, map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        out.write(frame_dewarped)
        
        frame_count += 1
        if frame_count % 100 == 0:
            progress = (frame_count / total_frames) * 100
            print(f"Progress: {progress:.1f}% ({frame_count}/{total_frames} frames)")
    
    cap.release()
    out.release()
    print(f"Dewarped video saved: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dewarp fisheye distortion from ultra-wide lens video")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output dewarped video path")
    parser.add_argument("--ifov", type=int, default=120, help="Input field of view in degrees (default: 120)")
    parser.add_argument("--ofov", type=int, default=90, help="Output field of view in degrees (default: 90)")
    args = parser.parse_args()
    dewarp_video(args.input, args.output, args.ifov, args.ofov)


