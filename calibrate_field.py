"""
Field Calibration Tool (Enhanced)
Calibrate the field for top-down perspective mapping using homography.
Supports both rectangular and trapezoidal/perspective field views.
"""

import cv2
import numpy as np
import argparse
import os

# Click points storage
click_points = []
calibration_mode = "4-point"  # "4-point" or "8-point"
img = None
img_original = None
scale = 1.0

def click_event(event, x, y, flags, param):
    """Handle mouse clicks to mark field points"""
    global img, click_points, calibration_mode
    
    if event == cv2.EVENT_LBUTTONDOWN:
        max_points = 4 if calibration_mode == "4-point" else 8
        
        if len(click_points) < max_points:
            click_points.append([x, y])
            
            # Redraw image
            img = img_original.copy()
            
            # Draw all points and labels
            for i, pt in enumerate(click_points):
                cv2.circle(img, tuple(pt), 10, (0, 255, 0), -1)
                cv2.circle(img, tuple(pt), 15, (0, 255, 0), 2)
                
                # Draw point label
                label = get_point_label(i, calibration_mode)
                cv2.putText(img, label, (pt[0] + 15, pt[1] - 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Draw connecting lines
            if calibration_mode == "4-point":
                if len(click_points) >= 2:
                    for i in range(len(click_points) - 1):
                        cv2.line(img, tuple(click_points[i]), tuple(click_points[i+1]), 
                                (0, 255, 0), 2)
                if len(click_points) == 4:
                    # Close the rectangle
                    cv2.line(img, tuple(click_points[3]), tuple(click_points[0]), 
                            (0, 255, 0), 2)
            else:  # 8-point mode
                if len(click_points) >= 2:
                    # Draw field outline
                    if len(click_points) >= 4:
                        # Draw outer rectangle
                        cv2.line(img, tuple(click_points[0]), tuple(click_points[1]), 
                                (0, 255, 0), 2)
                        cv2.line(img, tuple(click_points[1]), tuple(click_points[2]), 
                                (0, 255, 0), 2)
                        cv2.line(img, tuple(click_points[2]), tuple(click_points[3]), 
                                (0, 255, 0), 2)
                        cv2.line(img, tuple(click_points[3]), tuple(click_points[0]), 
                                (0, 255, 0), 2)
                    if len(click_points) >= 5:
                        # Draw mid-point connections to adjacent corners (for perspective stretching)
                        # TM (4) connects to TL (0) and TR (1) - top edge
                        if len(click_points) > 4:
                            cv2.line(img, tuple(click_points[0]), tuple(click_points[4]), 
                                    (255, 255, 0), 1)  # TL to TM
                            cv2.line(img, tuple(click_points[1]), tuple(click_points[4]), 
                                    (255, 255, 0), 1)  # TR to TM
                        # RM (5) connects to TR (1) and BR (2) - right edge
                        if len(click_points) > 5:
                            cv2.line(img, tuple(click_points[1]), tuple(click_points[5]), 
                                    (255, 255, 0), 1)  # TR to RM
                            cv2.line(img, tuple(click_points[2]), tuple(click_points[5]), 
                                    (255, 255, 0), 1)  # BR to RM
                        # BM (6) connects to BR (2) and BL (3) - bottom edge
                        if len(click_points) > 6:
                            cv2.line(img, tuple(click_points[2]), tuple(click_points[6]), 
                                    (255, 255, 0), 1)  # BR to BM
                            cv2.line(img, tuple(click_points[3]), tuple(click_points[6]), 
                                    (255, 255, 0), 1)  # BL to BM
                        # LM (7) connects to BL (3) and TL (0) - left edge (KEY CONNECTION)
                        if len(click_points) > 7:
                            cv2.line(img, tuple(click_points[3]), tuple(click_points[7]), 
                                    (255, 255, 0), 1)  # BL to LM
                            cv2.line(img, tuple(click_points[0]), tuple(click_points[7]), 
                                    (255, 255, 0), 1)  # TL to LM - THIS STRETCHES THE PERSPECTIVE
            
            cv2.imshow("Field Calibration", img)
            print(f"Point {len(click_points)} ({get_point_label(len(click_points)-1, calibration_mode)}): ({x}, {y})")
            
            # Save when all points are marked
            if len(click_points) == max_points:
                save_calibration()
    
    elif event == cv2.EVENT_RBUTTONDOWN:
        # Right-click to undo last point
        if click_points:
            click_points.pop()
            img = img_original.copy()
            
            # Redraw remaining points
            for i, pt in enumerate(click_points):
                cv2.circle(img, tuple(pt), 10, (0, 255, 0), -1)
                cv2.circle(img, tuple(pt), 15, (0, 255, 0), 2)
                label = get_point_label(i, calibration_mode)
                cv2.putText(img, label, (pt[0] + 15, pt[1] - 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            cv2.imshow("Field Calibration", img)
            print("Last point removed")


def get_point_label(index, mode):
    """Get label for point based on calibration mode"""
    if mode == "4-point":
        labels = ["TL", "TR", "BR", "BL"]  # Top-Left, Top-Right, Bottom-Right, Bottom-Left
        return labels[index] if index < 4 else str(index+1)
    else:  # 8-point
        labels = ["TL", "TR", "BR", "BL",  # Corners
                  "TM", "RM", "BM", "LM"]  # Mid-points (Top, Right, Bottom, Left)
        return labels[index] if index < 8 else str(index+1)


def preview_transformation(img_path, src_points, field_length, field_width):
    """Preview the perspective transformation"""
    global scale
    
    # Load original image
    img_orig = cv2.imread(img_path)
    if img_orig is None:
        return
    
    # Convert display coordinates back to original coordinates
    src_points_orig = (np.array(src_points) / scale).astype(np.float32)
    
    # Define destination points (real-world coordinates in meters)
    if len(src_points) == 4:
        # Standard 4-point rectangle
        dst_points = np.array([
            [0, 0],                    # Top-Left
            [field_length, 0],         # Top-Right
            [field_length, field_width], # Bottom-Right
            [0, field_width]           # Bottom-Left
        ], dtype=np.float32)
    else:
        # 8-point trapezoidal - adjust for perspective
        # Calculate actual dimensions based on perspective
        # Top width (may be narrower in perspective)
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
    
    # Calculate homography matrix
    if len(src_points) == 4:
        H = cv2.getPerspectiveTransform(src_points_orig, dst_points[:4])
    else:
        # Use 8 points for more accurate transformation
        H, _ = cv2.findHomography(src_points_orig, dst_points, cv2.RANSAC, 5.0)
    
    # Get output size
    h, w = img_orig.shape[:2]
    output_size = (int(field_length * 20), int(field_width * 20))  # Scale for display (20 pixels per meter)
    
    # Warp image
    warped = cv2.warpPerspective(img_orig, H, output_size)
    
    # Show preview
    cv2.imshow("Transformation Preview", warped)
    print("\nPreview window opened. Close it to continue...")
    cv2.waitKey(0)
    cv2.destroyWindow("Transformation Preview")


def save_calibration():
    """Save calibration data"""
    global click_points, scale, img_original
    
    # Convert to original image coordinates
    src_points_orig = (np.array(click_points) / scale).astype(np.float32)
    
    # Save calibration points
    np.save("calibration.npy", src_points_orig)
    
    # Save marked image
    cv2.imwrite("calibrated_corners.jpg", img)
    
    # Save calibration metadata
    calibration_data = {
        'mode': calibration_mode,
        'num_points': len(click_points),
        'points': src_points_orig.tolist(),
        'scale': scale
    }
    np.save("calibration_metadata.npy", calibration_data)
    
    print("\n" + "="*60)
    print("Calibration Complete!")
    print("="*60)
    print(f"Mode: {calibration_mode}")
    print(f"Points clicked: {len(click_points)}")
    print(f"Saved calibration points to: calibration.npy")
    print(f"Saved marked image to: calibrated_corners.jpg")
    print(f"Saved metadata to: calibration_metadata.npy")
    print("\nPoints clicked (in order):")
    for i, pt in enumerate(click_points):
        print(f"  {i+1}. {get_point_label(i, calibration_mode)}: ({int(pt[0])}, {int(pt[1])})")
    print("\nNext: Run your analysis with field calibration enabled!")
    print("="*60)


def calibrate_field(image_path, field_length=40.0, field_width=20.0, mode="auto"):
    """
    Calibrate field for perspective transformation
    
    Args:
        image_path: Path to reference image with full field visible
        field_length: Real-world field length in meters (default: 40m for indoor)
        field_width: Real-world field width in meters (default: 20m for indoor)
        mode: Calibration mode - "4-point" (rectangular), "8-point" (trapezoidal), or "auto"
    """
    global img, img_original, click_points, calibration_mode, scale
    
    # Determine mode
    if mode == "auto":
        # Ask user which mode
        print("\nSelect calibration mode:")
        print("  1. 4-point (Rectangular field - faster, simpler)")
        print("  2. 8-point (Trapezoidal/Perspective - more accurate for angled views)")
        choice = input("Enter choice (1 or 2): ").strip()
        calibration_mode = "8-point" if choice == "2" else "4-point"
    else:
        calibration_mode = mode
    
    # Load image
    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}")
        return
    
    img_orig = cv2.imread(image_path)
    if img_orig is None:
        print(f"Error: Could not load image: {image_path}")
        return
    
    # Resize for display (keep aspect ratio)
    display_width = 1280
    scale = display_width / img_orig.shape[1]
    display_height = int(img_orig.shape[0] * scale)
    img_display = cv2.resize(img_orig, (display_width, display_height))
    
    # Work with display size for clicks
    img_original = img_display.copy()
    img = img_original.copy()
    click_points = []
    
    print("="*60)
    print("Field Calibration Tool (Enhanced)")
    print("="*60)
    print(f"\nMode: {calibration_mode}")
    
    if calibration_mode == "4-point":
        print("\nInstructions (4-Point Mode):")
        print("1. Click 4 corners of the field in this order:")
        print("   - Top-Left corner (TL)")
        print("   - Top-Right corner (TR)")
        print("   - Bottom-Right corner (BR)")
        print("   - Bottom-Left corner (BL)")
        print("\n2. Right-click to undo last point")
        print("3. Calibration will be saved automatically when all 4 points are clicked")
    else:
        print("\nInstructions (8-Point Mode - Better for Trapezoidal/Perspective):")
        print("1. Click 4 corners first:")
        print("   - Top-Left corner (TL)")
        print("   - Top-Right corner (TR)")
        print("   - Bottom-Right corner (BR)")
        print("   - Bottom-Left corner (BL)")
        print("\n2. Then click 4 mid-points:")
        print("   - Top-Mid (TM) - middle of top edge")
        print("   - Right-Mid (RM) - middle of right edge")
        print("   - Bottom-Mid (BM) - middle of bottom edge")
        print("   - Left-Mid (LM) - middle of left edge")
        print("\n3. Right-click to undo last point")
        print("4. Calibration will be saved automatically when all 8 points are clicked")
    
    print("\nField dimensions (real-world):")
    print(f"   Length: {field_length}m")
    print(f"   Width: {field_width}m")
    print("\n(You can adjust these in the script if needed)")
    print("="*60)
    print("\nClick on the image window to mark points...")
    
    cv2.imshow("Field Calibration", img)
    cv2.setMouseCallback("Field Calibration", click_event)
    
    # Wait for user to click all points
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    # Ask if user wants to preview transformation
    if len(click_points) >= 4:
        preview = input("\nPreview transformation? (y/n): ").strip().lower()
        if preview == 'y':
            preview_transformation(image_path, click_points, field_length, field_width)
    
    # Save field dimensions
    field_dims = {
        'length': field_length,
        'width': field_width,
        'scale': scale,
        'mode': calibration_mode
    }
    np.save("field_dimensions.npy", field_dims)
    print(f"\nField dimensions saved to: field_dimensions.npy")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calibrate field for top-down mapping (Enhanced)")
    parser.add_argument("--image", required=True, help="Path to reference image with full field visible")
    parser.add_argument("--length", type=float, default=40.0, 
                       help="Real-world field length in meters (default: 40m for indoor)")
    parser.add_argument("--width", type=float, default=20.0,
                       help="Real-world field width in meters (default: 20m for indoor)")
    parser.add_argument("--mode", type=str, default="auto", choices=["4-point", "8-point", "auto"],
                       help="Calibration mode: 4-point (rectangular), 8-point (trapezoidal), or auto (ask user)")
    args = parser.parse_args()
    
    calibrate_field(args.image, args.length, args.width, args.mode)
