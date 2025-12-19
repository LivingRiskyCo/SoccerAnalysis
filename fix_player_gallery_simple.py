"""
Simple script to fix corrupted player_gallery.json
Removes the incomplete last entry and saves a valid JSON file
"""
import json
import os
import re

def fix_player_gallery():
    gallery_path = "player_gallery.json"
    backup_path = gallery_path + ".backup"
    
    if not os.path.exists(gallery_path):
        print(f"File not found: {gallery_path}")
        return
    
    print(f"Reading {gallery_path}...")
    
    # Read the file
    with open(gallery_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"   File size: {len(content)} characters")
    
    # Find where the corruption starts (incomplete "preferred_x")
    corruption_start = content.find('"preferred_x":')
    
    if corruption_start == -1:
        print("File appears to be complete!")
        return
    
    print(f"   Found corruption at position {corruption_start}")
    
    # Find the start of the corrupted player entry
    # Look backwards for the last complete player entry
    before_corruption = content[:corruption_start]
    
    # Find the last complete player entry (ends with },)
    # We need to find the last }, that's followed by whitespace and then a quote (start of next player)
    # Or the last }, before the corruption
    
    # Find all player entry endings: }, followed by newline and quote
    # Pattern: }, \n    "player_id":
    pattern = r'},\s*\n\s*"[^"]+":\s*{'
    matches = list(re.finditer(pattern, before_corruption))
    
    if matches:
        # Get the position after the last complete player entry
        last_match = matches[-1]
        # Find the closing brace of that entry
        cut_position = last_match.end() - 1  # Before the opening { of corrupted entry
        # Actually, we want to keep up to the }, of the last complete entry
        cut_position = before_corruption.rfind('},', 0, corruption_start)
        if cut_position != -1:
            cut_position += 2  # Include the },
    else:
        # Fallback: find the last }, before corruption
        cut_position = before_corruption.rfind('},')
        if cut_position != -1:
            cut_position += 2
    
    if cut_position == -1 or cut_position == 1:
        print("Could not find a safe cut position")
        return
    
    # Extract the good part
    good_content = content[:cut_position].rstrip()
    
    # Remove any trailing comma
    if good_content.endswith(','):
        good_content = good_content[:-1]
    
    # Close the JSON object
    if not good_content.endswith('}'):
        good_content += '\n}'
    
    # Try to parse it
    try:
        data = json.loads(good_content)
        print(f"Successfully parsed {len(data)} complete players!")
        
        # Create backup
        if not os.path.exists(backup_path):
            import shutil
            shutil.copy2(gallery_path, backup_path)
            print(f"Created backup: {backup_path}")
        else:
            print(f"Backup already exists: {backup_path}")
        
        # Save fixed version
        with open(gallery_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"Fixed and saved {len(data)} players to {gallery_path}")
        print(f"\nPlayers recovered:")
        for player_id, player_data in data.items():
            name = player_data.get('name', 'Unknown')
            jersey = player_data.get('jersey_number', '?')
            print(f"   • {name} (#{jersey})")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"Still has JSON error: {e}")
        print(f"   Error at position: {e.pos}")
        return False

if __name__ == "__main__":
    fix_player_gallery()

