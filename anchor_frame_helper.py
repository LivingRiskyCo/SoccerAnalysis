"""
Anchor Frame Helper Script
Helps you create and manage anchor frames for your videos
"""
import json
import os
import glob
from pathlib import Path

def analyze_video_for_anchor_frames(video_path):
    """Analyze a video and suggest anchor frame strategy"""
    if not os.path.exists(video_path):
        print(f"[ERROR] Video not found: {video_path}")
        return
    
    video_dir = os.path.dirname(os.path.abspath(video_path))
    video_basename = os.path.splitext(os.path.basename(video_path))[0]
    
    # Check for existing anchor frames
    seed_files = [
        os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}-Project.json"),
        os.path.join(video_dir, f"PlayerTagsSeed-{video_basename}.json"),
        os.path.join(video_dir, "seed_config.json")
    ]
    
    existing_anchors = {}
    for seed_file in seed_files:
        if os.path.exists(seed_file):
            try:
                with open(seed_file, 'r') as f:
                    data = json.load(f)
                anchor_frames = data.get("anchor_frames", {})
                if anchor_frames:
                    existing_anchors = anchor_frames
                    print(f"[OK] Found existing anchor frames in: {os.path.basename(seed_file)}")
                    break
            except Exception as e:
                print(f"[WARNING] Could not read {seed_file}: {e}")
    
    # Count existing anchors
    total_anchors = sum(len(anchors) for anchors in existing_anchors.values())
    total_frames = len(existing_anchors)
    
    print(f"\n{'='*60}")
    print(f"ANCHOR FRAME ANALYSIS: {os.path.basename(video_path)}")
    print(f"{'='*60}")
    print(f"Current anchor frames: {total_anchors} tags in {total_frames} frames")
    
    if total_anchors == 0:
        print(f"\nRECOMMENDATIONS:")
        print(f"  1. Use Setup Wizard to tag 5-10 key players")
        print(f"  2. Tag at frames: 0, middle, and end of video")
        print(f"  3. Tag players from both teams")
        print(f"  4. Focus on most visible/important players first")
        print(f"\nQuick Start:")
        print(f"  - Open main GUI -> Click 'Setup Wizard'")
        print(f"  - Load your video: {video_path}")
        print(f"  - Navigate and tag players (each tag = 1 anchor frame)")
    else:
        print(f"\n[OK] You already have anchor frames!")
        print(f"\nDistribution:")
        frame_nums = sorted([int(f) for f in existing_anchors.keys()])
        if frame_nums:
            print(f"   First frame: {frame_nums[0]}")
            print(f"   Last frame: {frame_nums[-1]}")
            print(f"   Frames with anchors: {len(frame_nums)}")
        
        # Count unique players
        unique_players = set()
        for anchors in existing_anchors.values():
            for anchor in anchors:
                unique_players.add(anchor.get("player_name", "Unknown"))
        print(f"   Unique players tagged: {len(unique_players)}")
        
        print(f"\nTo add more anchor frames:")
        print(f"  - Use 'Tag Players (Gallery)' button")
        print(f"  - Or use Setup Wizard to tag more frames")
    
    return existing_anchors

def suggest_anchor_frame_strategy(video_path, target_frames=10):
    """Suggest which frames to tag for best anchor frame coverage"""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0
        cap.release()
        
        print(f"\n{'='*60}")
        print(f"SUGGESTED ANCHOR FRAME STRATEGY")
        print(f"{'='*60}")
        print(f"Video: {os.path.basename(video_path)}")
        print(f"Total frames: {total_frames}")
        print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        print(f"FPS: {fps:.1f}")
        
        # Suggest frames
        suggested_frames = []
        if total_frames > 0:
            # Beginning, middle, end
            suggested_frames.append(0)
            suggested_frames.append(total_frames // 2)
            suggested_frames.append(total_frames - 1)
            
            # Evenly spaced frames
            spacing = total_frames // (target_frames - 3)
            for i in range(1, target_frames - 2):
                frame = i * spacing
                if frame not in suggested_frames:
                    suggested_frames.append(frame)
        
        suggested_frames = sorted(set(suggested_frames))
        
        print(f"\nSuggested frames to tag ({len(suggested_frames)} frames):")
        for i, frame in enumerate(suggested_frames, 1):
            time_sec = frame / fps if fps > 0 else 0
            time_str = f"{int(time_sec//60)}m {int(time_sec%60)}s" if time_sec > 60 else f"{int(time_sec)}s"
            print(f"  {i:2d}. Frame {frame:6d} ({time_str})")
        
        print(f"\nWorkflow:")
        print(f"  1. Open Setup Wizard or Gallery Seeder")
        print(f"  2. Load video: {video_path}")
        print(f"  3. Navigate to each suggested frame")
        print(f"  4. Tag 3-5 key players per frame")
        print(f"  5. Save and run analysis")
        
    except ImportError:
        print("[WARNING] OpenCV not available - cannot analyze video properties")
    except Exception as e:
        print(f"[WARNING] Could not analyze video: {e}")

def main():
    """Main function"""
    print("="*60)
    print("ANCHOR FRAME HELPER")
    print("="*60)
    print("\nThis script helps you create and manage anchor frames.")
    print("\nOptions:")
    print("1. Analyze existing anchor frames")
    print("2. Get strategy suggestions for a video")
    print("3. Check all videos in a directory")
    
    # Example usage
    print("\n" + "="*60)
    print("EXAMPLE USAGE:")
    print("="*60)
    print("\n# Analyze a specific video:")
    print("python anchor_frame_helper.py --video 'path/to/video.mp4'")
    print("\n# Get strategy for a video:")
    print("python anchor_frame_helper.py --suggest 'path/to/video.mp4'")
    print("\n# Check all videos in directory:")
    print("python anchor_frame_helper.py --check-dir 'path/to/videos'")
    
    # Check for command line args
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--video" and len(sys.argv) > 2:
            analyze_video_for_anchor_frames(sys.argv[2])
        elif sys.argv[1] == "--suggest" and len(sys.argv) > 2:
            suggest_anchor_frame_strategy(sys.argv[2])
        elif sys.argv[1] == "--check-dir" and len(sys.argv) > 2:
            dir_path = sys.argv[2]
            for video_file in glob.glob(os.path.join(dir_path, "*.mp4")):
                print("\n")
                analyze_video_for_anchor_frames(video_file)
        else:
            print("\nUsage:")
            print("  python anchor_frame_helper.py --video <video_path>")
            print("  python anchor_frame_helper.py --suggest <video_path>")
            print("  python anchor_frame_helper.py --check-dir <directory>")
    else:
        print("\nRun with --video, --suggest, or --check-dir arguments")
        print("Or use the GUI tools: Setup Wizard or Tag Players (Gallery)")

if __name__ == "__main__":
    main()

