import json

# Read the corrupted file
with open('player_gallery.json', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where corruption starts
corruption_pos = content.find('"preferred_x":')
if corruption_pos == -1:
    print("File appears complete!")
    exit(0)

# Get content before corruption
before = content[:corruption_pos].rstrip()

# Find the last complete player entry
# We need to find where a complete player entry ends: }, followed by newline
# But we also need to make sure we're not cutting in the middle of an array

# Strategy: Find the last complete player by looking for the pattern:
#   }, \n    "player_id": {
# This indicates the end of one player and start of another

import re

# Find all player boundaries: }, followed by whitespace, then "player_id": {
pattern = r'},\s*\n\s*"[^"]+":\s*{'
matches = list(re.finditer(pattern, before))

if matches:
    # Use the last complete player boundary
    # This pattern matches: }, \n    "player_id": {
    # The match.start() is at the position of the }, 
    # We want to keep everything up to and including the }
    # But we need to remove the comma
    last_match = matches[-1]
    # Position at the } (the match starts at the }, so start+1 is the })
    # Actually, the match starts at the }, so start is at the comma position
    # We want to keep up to the } before the comma
    cut_pos = last_match.start()  # Position at the comma
    fixed_content = before[:cut_pos].rstrip()
    # Now we have content ending with }, but we need to remove the comma
    # The content should end with } (the closing brace of the last complete player)
    # Add the closing brace for the root object
    fixed = fixed_content + '\n}'
else:
    # No player boundaries found - might be only one player or different structure
    # Find the last complete reference_frames array closing: ]
    last_array_close = before.rfind(']')
    if last_array_close != -1:
        # Find the closing brace of that player entry
        after_array = before[last_array_close:]
        player_close = after_array.find('},')
        if player_close != -1:
            cut_pos = last_array_close + player_close + 2
            fixed_content = before[:cut_pos].rstrip()
            if fixed_content.endswith(','):
                fixed_content = fixed_content[:-1]
            fixed = fixed_content + '\n}'
        else:
            # Just close at the array
            fixed = before[:last_array_close+1] + '\n    },\n  }\n}'
    else:
        # Last resort: find last },
        last_complete = before.rfind('},')
        if last_complete != -1:
            fixed_content = before[:last_complete+2].rstrip()
            if fixed_content.endswith(','):
                fixed_content = fixed_content[:-1]
            fixed = fixed_content + '\n}'
        else:
            print("Could not find safe cut position")
            exit(1)

# Try to parse
try:
    data = json.loads(fixed)
    print(f"Successfully recovered {len(data)} players!")
    print("\nPlayers:")
    for player_id, player_data in data.items():
        name = player_data.get('name', 'Unknown')
        jersey = player_data.get('jersey_number', '?')
        print(f"  - {name} (#{jersey})")
    
    # Create backup
    import shutil
    shutil.copy2('player_gallery.json', 'player_gallery.json.backup')
    print(f"\nBackup created: player_gallery.json.backup")
    
    # Save fixed version
    with open('player_gallery.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"Fixed file saved: player_gallery.json")
    
except json.JSONDecodeError as e:
    print(f"JSON error: {e}")
    print(f"Position: {e.pos}")
    # Show context around error
    start = max(0, e.pos - 50)
    end = min(len(fixed), e.pos + 50)
    print(f"Context: {fixed[start:end]}")

