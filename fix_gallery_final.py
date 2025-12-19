import json

# Read the file
with open('player_gallery.json', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where "wesley_beckett" starts (the corrupted player)
wesley_start = content.find('"wesley_beckett":')
if wesley_start == -1:
    print("Could not find wesley_beckett - file structure may be different")
    exit(1)

# Get everything before wesley_beckett
before_wesley = content[:wesley_start].rstrip()

# Remove trailing comma if present
if before_wesley.endswith(','):
    before_wesley = before_wesley[:-1]

# Close the JSON object
fixed = before_wesley + '\n}'

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
    print(f"\nNote: 'Wesley Beckett' entry was incomplete and has been removed.")
    print(f"You can re-add this player using the player_gallery_seeder.py tool.")
    
except json.JSONDecodeError as e:
    print(f"JSON error: {e}")
    print(f"Position: {e.pos}")

