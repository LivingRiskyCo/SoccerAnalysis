"""
Utility script to fix anchor frames that failed to match during analysis.

This script:
1. Reads the analysis log to find failed anchor frames
2. Or reads the anchor frames JSON directly
3. Improves matching by adjusting bbox sizes or removing problematic frames
4. Re-saves the anchor frames file

Usage:
    python fix_failed_anchor_frames.py <anchor_frames_json> [video_path]

Example:
    python fix_failed_anchor_frames.py PlayerTagsSeed-part001.json "C:/Users/nerdw/Videos/Practice 11-11/11-11/part001.mp4"
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict

def analyze_anchor_frame_issues(anchor_frames_path):
    """Analyze anchor frames to find potential issues"""
    if not os.path.exists(anchor_frames_path):
        print(f"❌ Anchor frames file not found: {anchor_frames_path}")
        return None
    
    try:
        with open(anchor_frames_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        anchor_frames = data.get('anchor_frames', {})
        
        if not anchor_frames:
            print("⚠ No anchor frames found in file")
            return None
        
        # Analyze issues
        issues = {
            'total_frames': len(anchor_frames),
            'frames_with_unknown': 0,
            'frames_with_many_anchors': 0,
            'bbox_size_issues': [],
            'missing_bbox': 0,
            'missing_track_id': 0
        }
        
        for frame_num_str, anchors in anchor_frames.items():
            frame_num = int(frame_num_str)
            
            # Count "Unknown Player" entries
            unknown_count = sum(1 for a in anchors if a.get('player_name', '').startswith('Unknown'))
            if unknown_count > 0:
                issues['frames_with_unknown'] += 1
            
            # Count frames with many anchors (might be too crowded)
            if len(anchors) > 15:
                issues['frames_with_many_anchors'] += 1
            
            for anchor in anchors:
                bbox = anchor.get('bbox')
                track_id = anchor.get('track_id')
                player_name = anchor.get('player_name', 'Unknown Player')
                
                if bbox is None or len(bbox) < 4:
                    issues['missing_bbox'] += 1
                    continue
                
                if track_id is None:
                    issues['missing_track_id'] += 1
                
                # Check bbox size (might be too small or too large)
                x1, y1, x2, y2 = bbox[:4]
                width = x2 - x1
                height = y2 - y1
                area = width * height
                
                # Typical player bbox: 50-100px wide, 100-200px tall
                if width < 30 or width > 200 or height < 50 or height > 300:
                    issues['bbox_size_issues'].append({
                        'frame': frame_num,
                        'player': player_name,
                        'bbox': bbox,
                        'width': width,
                        'height': height,
                        'area': area
                    })
        
        return issues
        
    except Exception as e:
        print(f"❌ Error analyzing anchor frames: {e}")
        import traceback
        traceback.print_exc()
        return None

def fix_anchor_frames(anchor_frames_path, output_path=None, fix_unknown=True, fix_bbox_sizes=True):
    """
    Fix common issues in anchor frames:
    1. Remove "Unknown Player" entries
    2. Fix bbox sizes that are too small/large
    3. Remove frames with too many anchors
    """
    if not os.path.exists(anchor_frames_path):
        print(f"❌ Anchor frames file not found: {anchor_frames_path}")
        return False
    
    try:
        with open(anchor_frames_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        anchor_frames = data.get('anchor_frames', {})
        original_count = sum(len(anchors) for anchors in anchor_frames.values())
        
        fixed_frames = {}
        removed_count = 0
        fixed_count = 0
        
        for frame_num_str, anchors in anchor_frames.items():
            frame_num = int(frame_num_str)
            fixed_anchors = []
            
            for anchor in anchors:
                player_name = anchor.get('player_name', '')
                bbox = anchor.get('bbox')
                track_id = anchor.get('track_id')
                
                # Fix 1: Remove "Unknown Player" entries
                if fix_unknown and (player_name.startswith('Unknown') or not player_name or player_name == 'Unknown Player'):
                    removed_count += 1
                    continue
                
                # Fix 2: Fix bbox sizes
                if fix_bbox_sizes and bbox and len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox[:4]
                    width = x2 - x1
                    height = y2 - y1
                    
                    # If bbox is too small or too large, adjust to reasonable size
                    # Use center point and default size
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    
                    if width < 30 or width > 200 or height < 50 or height > 300:
                        # Use default player size (80x160) centered on original center
                        new_width = 80
                        new_height = 160
                        x1 = center_x - new_width / 2
                        y1 = center_y - new_height / 2
                        x2 = center_x + new_width / 2
                        y2 = center_y + new_height / 2
                        anchor['bbox'] = [x1, y1, x2, y2]
                        fixed_count += 1
                
                fixed_anchors.append(anchor)
            
            # Only keep frames that have at least one valid anchor
            if fixed_anchors:
                fixed_frames[frame_num_str] = fixed_anchors
        
        # Update data
        data['anchor_frames'] = fixed_frames
        
        # Determine output path
        if output_path is None:
            # Create backup and overwrite original
            backup_path = anchor_frames_path.replace('.json', '_backup.json')
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.rename(anchor_frames_path, backup_path)
            output_path = anchor_frames_path
            print(f"📦 Created backup: {backup_path}")
        
        # Save fixed file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        new_count = sum(len(anchors) for anchors in fixed_frames.values())
        
        print(f"✅ Fixed anchor frames:")
        print(f"   - Original: {original_count} anchor entries in {len(anchor_frames)} frames")
        print(f"   - Fixed: {new_count} anchor entries in {len(fixed_frames)} frames")
        print(f"   - Removed: {removed_count} 'Unknown Player' entries")
        print(f"   - Fixed bbox sizes: {fixed_count} entries")
        print(f"   - Saved to: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing anchor frames: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage:")
        print("  python fix_failed_anchor_frames.py <anchor_frames_json> [output_json]")
        print("\nOptions:")
        print("  --analyze-only    : Only analyze issues, don't fix")
        print("  --no-fix-unknown  : Don't remove Unknown Player entries")
        print("  --no-fix-bbox     : Don't fix bbox sizes")
        print("\nExample:")
        print('  python fix_failed_anchor_frames.py "PlayerTagsSeed-part001.json"')
        sys.exit(1)
    
    anchor_frames_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Parse flags
    analyze_only = '--analyze-only' in sys.argv
    fix_unknown = '--no-fix-unknown' not in sys.argv
    fix_bbox = '--no-fix-bbox' not in sys.argv
    
    # Analyze first
    print("📊 Analyzing anchor frames...")
    issues = analyze_anchor_frame_issues(anchor_frames_path)
    
    if issues:
        print(f"\n📈 Analysis Results:")
        print(f"   - Total frames: {issues['total_frames']}")
        print(f"   - Frames with 'Unknown Player': {issues['frames_with_unknown']}")
        print(f"   - Frames with >15 anchors: {issues['frames_with_many_anchors']}")
        print(f"   - Missing bbox: {issues['missing_bbox']}")
        print(f"   - Missing track_id: {issues['missing_track_id']}")
        print(f"   - Bbox size issues: {len(issues['bbox_size_issues'])}")
        
        if issues['bbox_size_issues']:
            print(f"\n⚠ Bbox size issues (first 10):")
            for issue in issues['bbox_size_issues'][:10]:
                print(f"   Frame {issue['frame']}: {issue['player']} - "
                      f"bbox={issue['bbox']}, size={issue['width']:.0f}x{issue['height']:.0f}")
    
    if not analyze_only:
        print(f"\n🔧 Fixing anchor frames...")
        success = fix_anchor_frames(anchor_frames_path, output_path, fix_unknown, fix_bbox)
        
        if success:
            print(f"\n✅ Done! Re-run analysis to see improved matching.")
        else:
            print(f"\n❌ Failed to fix anchor frames")
            sys.exit(1)
    else:
        print(f"\nℹ Analysis only - no fixes applied")

if __name__ == "__main__":
    main()

