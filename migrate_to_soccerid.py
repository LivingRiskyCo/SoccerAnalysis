"""
Migration script to move soccer_analysis/soccer_analysis/ to SoccerID/
This prepares the codebase for multi-sport architecture (SoccerID, BasketballID, HockeyID, etc.)
"""

import os
import shutil
import re
from pathlib import Path
import sys

# Configure output encoding for Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

def find_python_files(directory):
    """Find all Python files in directory"""
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files

def update_imports_in_file(file_path, old_package, new_package):
    """Update imports in a Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Update various import patterns
        # Pattern 1: from soccer_analysis.module import ...
        content = re.sub(
            rf'from {re.escape(old_package)}\.([a-zA-Z_][a-zA-Z0-9_.]*) import',
            rf'from {new_package}.\1 import',
            content
        )
        
        # Pattern 2: import soccer_analysis.module
        content = re.sub(
            rf'import {re.escape(old_package)}\.([a-zA-Z_][a-zA-Z0-9_.]*)',
            rf'import {new_package}.\1',
            content
        )
        
        # Pattern 3: from soccer_analysis import ...
        content = re.sub(
            rf'from {re.escape(old_package)} import',
            rf'from {new_package} import',
            content
        )
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False

def create_soccerid_init():
    """Create __init__.py for SoccerID package"""
    init_content = '''"""
SoccerID - Professional Soccer Video Analysis Tool
Part of the SportID family (SoccerID, BasketballID, HockeyID, etc.)
"""

__version__ = "2.0.0"
__sport__ = "soccer"

# Import main entry points
try:
    from .main import main
    from .gui.main_window import SoccerAnalysisGUI
    
    __all__ = ['main', 'SoccerAnalysisGUI']
except ImportError:
    # During migration, some imports may fail
    __all__ = []
'''
    return init_content

def main():
    """Main migration function"""
    print("=" * 60)
    print("Migrating to SoccerID structure")
    print("=" * 60)
    
    root_dir = Path(__file__).parent.resolve()
    
    # Try to find the source directory
    possible_sources = [
        root_dir / 'soccer_analysis' / 'soccer_analysis',  # Nested structure
        root_dir / 'soccer_analysis',  # Direct structure (if already flattened)
    ]
    
    source_dir = None
    for possible in possible_sources:
        if possible.exists() and (possible / 'main.py').exists():
            source_dir = possible
            break
    
    if source_dir is None:
        print(f"ERROR: Could not find source directory with main.py")
        print(f"Tried:")
        for possible in possible_sources:
            print(f"  - {possible} (exists: {possible.exists()})")
        return False
    
    target_dir = root_dir / 'SoccerID'
    
    print(f"Root directory: {root_dir}")
    print(f"Source directory: {source_dir}")
    print(f"Target directory: {target_dir}")
    
    # Check if source exists
    if not source_dir.exists():
        print(f"ERROR: Source directory not found: {source_dir}")
        return False
    
    # Check if target already exists
    if target_dir.exists():
        response = input(f"WARNING: {target_dir} already exists. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Migration cancelled.")
            return False
        print(f"Removing existing {target_dir}...")
        shutil.rmtree(target_dir)
    
    print(f"\n1. Copying files from {source_dir} to {target_dir}...")
    try:
        shutil.copytree(source_dir, target_dir)
        print(f"   ✓ Copied {len(list(target_dir.rglob('*.py')))} Python files")
    except Exception as e:
        print(f"   ✗ Error copying files: {e}")
        return False
    
    print(f"\n2. Creating SoccerID/__init__.py...")
    init_file = target_dir / '__init__.py'
    try:
        with open(init_file, 'w', encoding='utf-8') as f:
            f.write(create_soccerid_init())
        print(f"   ✓ Created {init_file}")
    except Exception as e:
        print(f"   ✗ Error creating __init__.py: {e}")
        return False
    
    print(f"\n3. Updating imports from 'soccer_analysis' to 'soccerid'...")
    python_files = find_python_files(target_dir)
    updated_count = 0
    
    for file_path in python_files:
        if update_imports_in_file(file_path, 'soccer_analysis', 'soccerid'):
            updated_count += 1
            print(f"   ✓ Updated {os.path.relpath(file_path, target_dir)}")
    
    print(f"   ✓ Updated {updated_count} files")
    
    print(f"\n4. Updating main.py path references...")
    main_file = target_dir / 'main.py'
    try:
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update the import fallbacks
        content = content.replace(
            'from soccer_analysis.utils.splash_screen import show_splash_screen',
            'from soccerid.utils.splash_screen import show_splash_screen'
        )
        content = content.replace(
            'from soccer_analysis.gui.main_window import SoccerAnalysisGUI',
            'from soccerid.gui.main_window import SoccerAnalysisGUI'
        )
        
        with open(main_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   ✓ Updated {main_file}")
    except Exception as e:
        print(f"   ✗ Error updating main.py: {e}")
    
    print(f"\n5. Creating entry point script...")
    entry_script = root_dir / 'run_soccerid.py'
    entry_content = '''"""
Entry point for SoccerID
Run this script to launch the Soccer Analysis Tool
"""

import sys
from pathlib import Path

# Add SoccerID to path
root_dir = Path(__file__).parent
soccerid_dir = root_dir / 'SoccerID'
if str(soccerid_dir) not in sys.path:
    sys.path.insert(0, str(soccerid_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Import and run
from soccerid.main import main

if __name__ == "__main__":
    main()
'''
    try:
        with open(entry_script, 'w', encoding='utf-8') as f:
            f.write(entry_content)
        print(f"   ✓ Created {entry_script}")
    except Exception as e:
        print(f"   ✗ Error creating entry script: {e}")
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print(f"\nNext steps:")
    print(f"1. Test the migration: python run_soccerid.py")
    print(f"2. Update any root-level scripts that reference the old location")
    print(f"3. Consider updating documentation")
    print(f"\nThe old structure is still at: {source_dir}")
    print(f"The new structure is at: {target_dir}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

