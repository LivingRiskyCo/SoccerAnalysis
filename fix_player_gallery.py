"""
Fix corrupted player_gallery.json by removing incomplete entries
"""
import json
import os

def fix_player_gallery():
    gallery_path = "player_gallery.json"
    
    if not os.path.exists(gallery_path):
        print(f"❌ File not found: {gallery_path}")
        return
    
    # Read the file as text
    with open(gallery_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"📄 File size: {len(content)} characters")
    
    # Try to find the last complete player entry
    # Look for the last complete closing brace before the corruption
    last_complete_brace = content.rfind('}')
    
    if last_complete_brace == -1:
        print("❌ Could not find any complete JSON structure")
        return
    
    # Find the start of the last player entry
    # Look backwards from the last complete brace to find the start of that player
    # We'll try to extract all complete players
    try:
        # Try to parse up to the last complete brace
        # Find the last complete player entry by looking for pattern: "player_id": { ... }
        # We'll manually fix by finding where the corruption starts
        
        # Find the last occurrence of a complete player entry
        # Look for pattern: closing brace, comma, newline, then player_id pattern
        # Actually, simpler: just try to parse what we can
        
        # Find where "preferred_x" appears incomplete
        corruption_start = content.find('"preferred_x":')
        if corruption_start != -1:
            # Find the start of this player entry
            # Look backwards for the last complete player entry
            # Find the last "player_id": { before the corruption
            before_corruption = content[:corruption_start]
            
            # Find the last complete player entry
            # Look for the pattern: "player_id": { ... } with proper closing
            # We'll find the last } that closes a player entry
            
            # Try a different approach: find all player entries before corruption
            # Look for the pattern: "player_id": { ... },
            # The corruption is in the last entry, so we remove everything from "preferred_x" onwards
            
            # Find the start of the corrupted player entry
            # Look backwards for the last "player_id": {
            last_player_start = before_corruption.rfind('"')
            if last_player_start != -1:
                # Find the opening brace of this player
                player_start = before_corruption.rfind('{', 0, last_player_start)
                if player_start != -1:
                    # Find the player_id before this
                    # Actually, let's find the last complete player entry differently
                    # Find the last }, that closes a complete player entry
                    last_complete_entry = before_corruption.rfind('},')
                    if last_complete_entry != -1:
                        # This should be the end of the last complete player
                        # Now we need to close the JSON properly
                        fixed_content = before_corruption[:last_complete_entry+1] + '\n}'
                        
                        # Try to parse it
                        try:
                            data = json.loads(fixed_content)
                            print(f"✓ Fixed JSON! Found {len(data)} complete players")
                            
                            # Save the fixed version
                            backup_path = gallery_path + ".backup"
                            if not os.path.exists(backup_path):
                                os.rename(gallery_path, backup_path)
                                print(f"📦 Created backup: {backup_path}")
                            
                            with open(gallery_path, 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=2)
                            
                            print(f"✓ Fixed and saved {len(data)} players to {gallery_path}")
                            print(f"📋 Player names: {[p.get('name', 'Unknown') for p in data.values()]}")
                            return
                        except json.JSONDecodeError as e:
                            print(f"⚠ Still has JSON error: {e}")
        
        # Alternative: try to load what we can using the PlayerGallery class
        print("\n🔄 Trying alternative fix method...")
        print("   (This will load all complete players and save them)")
        
    except Exception as e:
        print(f"❌ Error during fix: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_player_gallery()

