"""
Check what's actually being learned in watch mode
Shows incremental learning vs total accumulated data
"""
import json
import os
from datetime import datetime

def check_gallery_learning():
    """Check player gallery learning status"""
    gallery_file = "player_gallery.json"
    
    if not os.path.exists(gallery_file):
        print("[ERROR] No player_gallery.json found")
        print("   -> Run watch mode to create the gallery")
        return
    
    print("=" * 70)
    print("PLAYER GALLERY LEARNING STATUS")
    print("=" * 70)
    
    try:
        with open(gallery_file, 'r') as f:
            gallery_data = json.load(f)
        
        players = gallery_data.get("players", {})
        total_players = len(players)
        
        print(f"\nTotal Players in Gallery: {total_players}")
        print(f"Gallery file: {gallery_file}")
        print(f"Last modified: {datetime.fromtimestamp(os.path.getmtime(gallery_file))}")
        
        # Calculate totals
        total_shape = 0
        total_movement = 0
        total_position = 0
        total_ball = 0
        players_with_features = 0
        players_with_data = 0
        total_ref_frames = 0
        
        print(f"\n{'Player Name':<25} {'Ref Frames':<12} {'Shape':<8} {'Position':<10} {'Ball':<8} {'Re-ID':<6}")
        print("-" * 70)
        
        for player_id, profile in sorted(players.items(), key=lambda x: x[1].get("name", "")):
            name = profile.get("name", "Unknown")
            ref_frames = len(profile.get("reference_frames", []))
            shape = profile.get("shape_samples", 0)
            movement = profile.get("movement_samples", 0)
            position = profile.get("position_samples", 0)
            ball = profile.get("ball_interaction_samples", 0)
            has_features = "Yes" if profile.get("features") else "No"
            
            total_shape += shape
            total_movement += movement
            total_position += position
            total_ball += ball
            total_ref_frames += ref_frames
            
            if profile.get("features"):
                players_with_features += 1
            if shape > 0 or movement > 0 or position > 0 or ball > 0:
                players_with_data += 1
            
            print(f"{name:<25} {ref_frames:<12} {shape:<8} {position:<10} {ball:<8} {has_features:<6}")
        
        print("-" * 70)
        print(f"{'TOTALS':<25} {total_ref_frames:<12} {total_shape:<8} {total_position:<10} {total_ball:<8}")
        
        print(f"\nSummary:")
        print(f"   - Players with learned data: {players_with_data}/{total_players}")
        print(f"   - Players with Re-ID features: {players_with_features}/{total_players}")
        print(f"   - Total reference frames: {total_ref_frames}")
        print(f"   - Total shape samples: {total_shape}")
        print(f"   - Total position samples: {total_position}")
        print(f"   - Total ball interaction samples: {total_ball}")
        
        # Check if gallery is being updated
        print(f"\nUnderstanding Watch Mode:")
        print(f"   -> Watch mode loads existing gallery at start")
        print(f"   -> Learning summary shows CUMULATIVE totals (all runs combined)")
        print(f"   -> If numbers don't change, watch mode might not be learning NEW data")
        print(f"   -> This can happen if:")
        print(f"      * Players already have enough reference frames (max 1000)")
        print(f"      * Re-ID threshold is too high (not matching new detections)")
        print(f"      * Players aren't being detected/tracked")
        
        print(f"\nTo see incremental learning:")
        print(f"   1. Note current totals above")
        print(f"   2. Run watch mode")
        print(f"   3. Check if totals increased")
        print(f"   4. If same, try:")
        print(f"      * Lower Re-ID similarity threshold (0.3-0.4)")
        print(f"      * Check that players are being detected")
        print(f"      * Verify tracking is working")
        
        print(f"\nTo start fresh (reset gallery):")
        print(f"   1. Backup current gallery: copy player_gallery.json to player_gallery_backup.json")
        print(f"   2. Delete player_gallery.json")
        print(f"   3. Run watch mode again")
        print(f"   4. Gallery will be created fresh")
        
    except Exception as e:
        print(f"[ERROR] Error reading gallery: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_gallery_learning()

