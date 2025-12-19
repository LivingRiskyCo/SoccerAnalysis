"""
Update all imports from 'soccerid' to 'SoccerID' to match the folder name
"""

import os
import re
from pathlib import Path

def update_file(file_path):
    """Update imports in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # Replace soccerid with SoccerID (case-sensitive)
        content = re.sub(r'\bsoccerid\b', 'SoccerID', content)
        
        if content != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False

def main():
    """Update all Python files"""
    soccerid_dir = Path('SoccerID')
    if not soccerid_dir.exists():
        print("SoccerID directory not found!")
        return
    
    python_files = list(soccerid_dir.rglob('*.py'))
    updated = 0
    
    for file_path in python_files:
        if update_file(file_path):
            updated += 1
            print(f"Updated: {file_path.relative_to(soccerid_dir)}")
    
    print(f"\nUpdated {updated} files")

if __name__ == "__main__":
    main()

