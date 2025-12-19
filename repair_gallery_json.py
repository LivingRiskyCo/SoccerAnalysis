"""
Repair corrupted player_gallery.json file

This script attempts to fix JSON syntax errors in the gallery file
by reading it line by line and fixing common issues.
"""

import json
import os
import shutil
from typing import Dict, Any

def repair_json_file(input_path: str, output_path: str) -> bool:
    """
    Attempt to repair a corrupted JSON file
    
    Args:
        input_path: Path to corrupted JSON file
        output_path: Path to save repaired JSON file
    
    Returns:
        True if repair was successful, False otherwise
    """
    print(f"Attempting to repair: {input_path}")
    
    # Read the file as text first
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"ERROR: Could not read file: {e}")
        return False
    
    # Strategy 1: Try to parse and fix common issues
    print("   -> Strategy 1: Attempting to fix common JSON issues...")
    
    # Fix common issues:
    # 1. Trailing commas before closing brackets/braces
    # 2. Missing quotes around keys
    # 3. Unescaped newlines in strings
    
    # Remove trailing commas before } or ]
    import re
    # This regex matches a comma followed by whitespace and then } or ]
    content = re.sub(r',(\s*[}\]])', r'\1', content)
    
    # Try to parse
    try:
        data = json.loads(content)
        print(f"   OK Successfully parsed JSON after basic fixes!")
        # Save repaired version
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"   OK Saved repaired JSON to: {output_path}")
        return True
    except json.JSONDecodeError as e:
        print(f"   WARNING: Basic fixes didn't work. Error at line {e.lineno}, column {e.colno}: {e.msg}")
    
    # Strategy 2: Try to load valid players up to the error point
    print("   -> Strategy 2: Attempting to salvage valid players before corruption...")
    
    try:
        # Read the file and try to extract valid JSON objects
        # Look for complete player entries by finding matching braces
        valid_players = {}
        
        # Try to find and extract each player entry individually
        # Pattern: "player_id": { ... complete JSON object ... }
        player_pattern = r'"([a-zA-Z0-9_]+)":\s*\{'
        
        # Find all player entry starts
        matches = list(re.finditer(player_pattern, content))
        print(f"   -> Found {len(matches)} potential player entries")
        
        for match_idx, match in enumerate(matches):
            player_id = match.group(1)
            start_pos = match.start()
            
            # Find the matching closing brace for this player
            brace_count = 0
            in_string = False
            escape_next = False
            end_pos = start_pos
            
            for i, char in enumerate(content[start_pos:], start_pos):
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_pos = i + 1
                            break
            
            # Try to parse this player entry
            if end_pos > start_pos:
                try:
                    # Extract the player JSON (include the key)
                    player_json = content[start_pos:end_pos]
                    # Wrap in braces to make it valid JSON
                    wrapped_json = '{' + player_json + '}'
                    player_data = json.loads(wrapped_json)
                    valid_players[player_id] = player_data[player_id]
                except:
                    pass  # Skip this player if it can't be parsed
        
        # If we found any valid players, save them
        if valid_players:
            print(f"   OK Found {len(valid_players)} valid players before corruption")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(valid_players, f, indent=2, ensure_ascii=False)
            print(f"   OK Saved {len(valid_players)} valid players to: {output_path}")
            return True
        else:
            print(f"   WARNING: Could not salvage any valid players")
    
    except Exception as e:
        print(f"   WARNING: Salvage attempt failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Strategy 3: Manual fix guidance
    print("   -> Strategy 3: Manual fix required")
    print(f"   -> The file has a syntax error that couldn't be automatically fixed")
    print(f"   -> You can:")
    print(f"      1. Open the file in a text editor")
    print(f"      2. Go to the line mentioned in the error")
    print(f"      3. Fix the syntax issue (missing comma, quote, bracket, etc.)")
    print(f"      4. Or use player_gallery_seeder.py to rebuild the gallery")
    
    return False

def main():
    """Main repair function"""
    import sys
    # Fix Windows console encoding for emoji
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    gallery_path = "player_gallery.json"
    backup_path = "player_gallery.json.corrupted_backup"
    repaired_path = "player_gallery.json.repaired"
    
    # Check for various backup file names
    backup_candidates = [
        "player_gallery.json.backup",
        "player_gallery.json.corrupted_backup",
        gallery_path
    ]
    
    # Find the first existing backup file
    found_backup = None
    for candidate in backup_candidates:
        if os.path.exists(candidate):
            found_backup = candidate
            break
    
    if found_backup:
        backup_path = found_backup
        print(f"Found backup file: {backup_path}")
    else:
        print(f"ERROR: No backup file found")
        print(f"   -> Looked for: {', '.join(backup_candidates)}")
        return
    
    print(f"Found backup file: {backup_path}")
    print(f"   -> File size: {os.path.getsize(backup_path) / 1024 / 1024:.2f} MB")
    
    # Try to repair
    if repair_json_file(backup_path, repaired_path):
        print(f"\nSUCCESS: Repair successful!")
        print(f"   -> Repaired file saved to: {repaired_path}")
        
        # Ask if user wants to replace original
        try:
            response = input(f"\n   Replace original gallery file? (y/n): ").strip().lower()
            if response == 'y':
                # Backup original if it exists
                if os.path.exists(gallery_path):
                    shutil.copy2(gallery_path, gallery_path + ".old_backup")
                    print(f"   -> Backed up original to: {gallery_path}.old_backup")
                
                # Replace with repaired version
                shutil.copy2(repaired_path, gallery_path)
                print(f"   OK Replaced {gallery_path} with repaired version")
                print(f"   -> You can now run analysis again")
            else:
                print(f"   -> Repaired file saved as: {repaired_path}")
                print(f"   -> You can manually copy it to {gallery_path} if desired")
        except (EOFError, KeyboardInterrupt):
            print(f"\n   -> Repaired file saved as: {repaired_path}")
            print(f"   -> You can manually copy it to {gallery_path} if desired")
    else:
        print(f"\nERROR: Automatic repair failed")
        print(f"   -> The file may need manual editing")
        print(f"   -> Or use player_gallery_seeder.py to rebuild the gallery")

if __name__ == "__main__":
    main()

