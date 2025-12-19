"""
Merge audio from original video into analyzed video
"""

import os
import subprocess
import sys

def merge_audio(original_video, analyzed_video, output_video=None):
    """
    Merge audio from original video into analyzed video using FFmpeg
    
    Args:
        original_video: Path to original video (with audio)
        analyzed_video: Path to analyzed video (without audio)
        output_video: Path to output video (if None, replaces analyzed_video)
    """
    if not os.path.exists(original_video):
        print(f"Error: Original video not found: {original_video}")
        return False
    
    if not os.path.exists(analyzed_video):
        print(f"Error: Analyzed video not found: {analyzed_video}")
        return False
    
    if output_video is None:
        # Replace the analyzed video
        output_video = analyzed_video.replace('.mp4', '_with_audio.mp4')
        # If that exists, use a temp file first
        if os.path.exists(output_video):
            temp_output = analyzed_video.replace('.mp4', '_with_audio_temp.mp4')
            output_video = temp_output
    
    print(f"Merging audio from: {os.path.basename(original_video)}")
    print(f"Into video: {os.path.basename(analyzed_video)}")
    print(f"Output: {os.path.basename(output_video)}")
    print()
    
    # FFmpeg command to merge audio
    # -i analyzed_video: video input (no audio)
    # -i original_video: audio input
    # -c:v copy: copy video codec (no re-encoding)
    # -c:a copy: copy audio codec (no re-encoding)
    # -map 0:v:0: use video from first input (analyzed video)
    # -map 1:a:0: use audio from second input (original video)
    # -shortest: finish when shortest stream ends (in case durations differ)
    cmd = [
        'ffmpeg',
        '-i', analyzed_video,
        '-i', original_video,
        '-c:v', 'copy',  # Copy video (no re-encoding)
        '-c:a', 'copy',  # Copy audio (no re-encoding)
        '-map', '0:v:0',  # Use video from first input
        '-map', '1:a:0',  # Use audio from second input
        '-shortest',  # Finish when shortest stream ends
        '-y',  # Overwrite output file if exists
        output_video
    ]
    
    try:
        print("Running FFmpeg...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("SUCCESS: Audio merged successfully!")
        print(f"Output: {output_video}")
        
        # If we used a temp file, replace the original
        if '_temp' in output_video:
            final_output = output_video.replace('_temp', '')
            if os.path.exists(final_output):
                os.remove(final_output)
            os.rename(output_video, final_output)
            print(f"Renamed to: {os.path.basename(final_output)}")
            output_video = final_output
        
        # Optionally replace the original analyzed video
        print()
        print(f"Original analyzed video: {os.path.basename(analyzed_video)}")
        print(f"New video with audio: {os.path.basename(output_video)}")
        print()
        
        # Auto-replace if running non-interactively, or ask if interactive
        try:
            response = input("Replace original analyzed video with audio version? (y/n, default=y): ").strip().lower()
            if response == '' or response == 'y':
                replace = True
            else:
                replace = False
        except (EOFError, KeyboardInterrupt):
            # Non-interactive mode - auto-replace
            replace = True
            print("Non-interactive mode: Auto-replacing original video...")
        
        if replace:
            backup = analyzed_video.replace('.mp4', '_no_audio_backup.mp4')
            if os.path.exists(analyzed_video):
                os.rename(analyzed_video, backup)
            os.rename(output_video, analyzed_video)
            print(f"SUCCESS: Replaced! Original saved as: {os.path.basename(backup)}")
            print(f"Final video: {os.path.basename(analyzed_video)}")
        else:
            print(f"SUCCESS: Kept both files")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error: FFmpeg failed")
        print(f"Command: {' '.join(cmd)}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python merge_audio.py <original_video> <analyzed_video> [output_video]")
        print()
        print("Example:")
        print("  python merge_audio.py original.mp4 analyzed.mp4")
        print("  python merge_audio.py original.mp4 analyzed.mp4 output_with_audio.mp4")
        sys.exit(1)
    
    original = sys.argv[1]
    analyzed = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) > 3 else None
    
    success = merge_audio(original, analyzed, output)
    sys.exit(0 if success else 1)

