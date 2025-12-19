"""
Penalty Shot Player Tuning Helper
Quick script to check and optimize settings for Rocco, Cameron Hill, Ellie Hill, and James Carlson
"""

import json
import os
from pathlib import Path

# Target players
TARGET_PLAYERS = {
    "Rocco Piazza": "rocco_piazza",
    "Cameron Hill": "cameron_hill", 
    "Ellie Hill": "ellie_hill",
    "James Carlson": "james_carlson"
}

def check_player_gallery():
    """Check if players exist in gallery and show their status"""
    gallery_path = Path("player_gallery.json")
    
    if not gallery_path.exists():
        print("❌ player_gallery.json not found!")
        return False
    
    print("\n📋 Checking Player Gallery...")
    print("=" * 60)
    
    with open(gallery_path, 'r', encoding='utf-8') as f:
        gallery = json.load(f)
    
    all_found = True
    for display_name, player_id in TARGET_PLAYERS.items():
        if player_id in gallery:
            profile = gallery[player_id]
            name = profile.get('name', 'Unknown')
            ref_frames = profile.get('reference_frames', [])
            uniform_variants = profile.get('uniform_variants', {})
            
            # Count total reference frames across all variants
            total_refs = len(ref_frames)
            if uniform_variants:
                for variant, frames in uniform_variants.items():
                    total_refs += len(frames) if isinstance(frames, list) else 0
            
            print(f"\n✓ {display_name} ({player_id})")
            print(f"  Name: {name}")
            print(f"  Reference Frames: {total_refs}")
            
            if total_refs < 3:
                print(f"  ⚠️  WARNING: Only {total_refs} reference frame(s). Recommend 3-5+ for better recognition.")
            elif total_refs >= 5:
                print(f"  ✅ Good: {total_refs} reference frames (recommended: 3-5+)")
            
            # Check for features
            has_features = bool(profile.get('features') or profile.get('body_features'))
            if has_features:
                print(f"  ✅ Has Re-ID features")
            else:
                print(f"  ⚠️  No Re-ID features (will be extracted during analysis)")
        else:
            print(f"\n❌ {display_name} ({player_id}) NOT FOUND in gallery")
            print(f"   → Run player_gallery_seeder.py to add this player")
            all_found = False
    
    print("\n" + "=" * 60)
    return all_found

def generate_optimal_settings():
    """Generate recommended settings for penalty shot analysis"""
    print("\n⚙️  Recommended Settings for Penalty Shot Analysis")
    print("=" * 60)
    
    settings = {
        "Detection": {
            "Confidence Threshold": "0.25-0.30",
            "IOU Threshold": "0.45-0.50",
            "Note": "Lower confidence to catch brief appearances (James Carlson)"
        },
        "Tracking": {
            "Track Threshold": "0.30-0.35",
            "Match Threshold": "0.55-0.60",
            "Track Buffer": "6.0-8.0 seconds",
            "Minimum Track Length": "3-5 frames",
            "Note": "Longer buffer for brief appearances, shorter min length"
        },
        "Re-ID": {
            "Re-ID Similarity Threshold": "0.50-0.55",
            "Re-ID Check Interval": "20-25 frames",
            "Re-ID Confidence Threshold": "0.70-0.75",
            "Note": "More frequent checks for better reconnection"
        },
        "Gallery Matching": {
            "Gallery Similarity Threshold": "0.35-0.40",
            "Note": "Slightly lower for better matching"
        }
    }
    
    for category, params in settings.items():
        print(f"\n{category}:")
        for key, value in params.items():
            if key != "Note":
                print(f"  • {key}: {value}")
        if "Note" in params:
            print(f"  → {params['Note']}")
    
    print("\n" + "=" * 60)

def check_anchor_frames():
    """Check if anchor frames exist for these players"""
    print("\n📌 Checking Anchor Frames...")
    print("=" * 60)
    
    # Check seed_config.json
    seed_config_path = Path("seed_config.json")
    if seed_config_path.exists():
        with open(seed_config_path, 'r', encoding='utf-8') as f:
            seed_config = json.load(f)
        
        anchor_frames = seed_config.get('anchor_frames', {})
        if anchor_frames:
            print(f"✓ Found anchor frames in seed_config.json")
            
            # Count anchor frames per player
            player_counts = {}
            for frame_num, anchors in anchor_frames.items():
                if isinstance(anchors, list):
                    for anchor in anchors:
                        player_name = anchor.get('player_name', '')
                        if player_name in TARGET_PLAYERS:
                            player_counts[player_name] = player_counts.get(player_name, 0) + 1
            
            if player_counts:
                print("\n  Anchor frame counts:")
                for player_name in TARGET_PLAYERS.keys():
                    count = player_counts.get(player_name, 0)
                    if count > 0:
                        print(f"    ✓ {player_name}: {count} anchor frame(s)")
                    else:
                        print(f"    ⚠️  {player_name}: No anchor frames")
            else:
                print("  ⚠️  No anchor frames found for target players")
        else:
            print("  ⚠️  No anchor frames in seed_config.json")
    else:
        print("  ⚠️  seed_config.json not found")
    
    # Check for PlayerTagsSeed JSON files
    current_dir = Path(".")
    anchor_files = list(current_dir.glob("PlayerTagsSeed*.json"))
    
    if anchor_files:
        print(f"\n✓ Found {len(anchor_files)} PlayerTagsSeed file(s):")
        for f in anchor_files:
            print(f"    • {f.name}")
    else:
        print("\n  ⚠️  No PlayerTagsSeed JSON files found")
        print("  → Use 'Convert Tracks → Anchor Frames' after analysis")
    
    print("=" * 60)

def print_workflow():
    """Print recommended workflow"""
    print("\n📝 Recommended Workflow")
    print("=" * 60)
    print("""
1. TAG PLAYERS (if not already done):
   python player_gallery_seeder.py
   - Tag Rocco during penalty setup
   - Tag Cameron Hill in goalkeeper position
   - Tag Ellie Hill when clearly visible
   - Tag James Carlson during brief appearance (may need frame-by-frame)

2. ADJUST SETTINGS in soccer_analysis_gui.py:
   - Use recommended settings from above
   - Enable "Learn Player Features"
   - Enable "Track Players"
   - Enable "Export CSV"

3. RUN ANALYSIS:
   - Load video
   - Click "Start Analysis"
   - Monitor console for gallery matches

4. REVIEW & CORRECT:
   - Use "Interactive Player Learning" to fix any missed assignments
   - Or use track_review_assigner.py for detailed review

5. EXPORT ANCHOR FRAMES:
   - Use "Convert Tracks → Anchor Frames" 
   - Or export from Track Review Assigner
   - These will auto-load in future analyses
""")
    print("=" * 60)

def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("🎯 PENALTY SHOT PLAYER TUNING HELPER")
    print("=" * 60)
    print("\nTarget Players:")
    for name in TARGET_PLAYERS.keys():
        print(f"  • {name}")
    
    # Check gallery
    gallery_ok = check_player_gallery()
    
    # Check anchor frames
    check_anchor_frames()
    
    # Generate settings
    generate_optimal_settings()
    
    # Print workflow
    print_workflow()
    
    # Summary
    print("\n📊 SUMMARY")
    print("=" * 60)
    if gallery_ok:
        print("✅ All players found in gallery")
        print("✅ Ready to run analysis with optimized settings")
    else:
        print("⚠️  Some players missing from gallery")
        print("   → Run player_gallery_seeder.py first")
    
    print("\n💡 TIP: For James Carlson's brief appearance:")
    print("   - Lower detection threshold to 0.25")
    print("   - Increase track buffer to 8-10 seconds")
    print("   - Set minimum track length to 3 frames")
    print("   - May need manual tagging in Track Review Assigner")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()

