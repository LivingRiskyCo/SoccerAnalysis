"""
Migration script to move code to new structure
"""

import os
import shutil
from pathlib import Path

def create_new_structure():
    """Create the new directory structure"""
    base = Path("soccer_analysis")
    
    directories = [
        base / "gui" / "tabs",
        base / "gui" / "dialogs",
        base / "gui" / "widgets",
        base / "gui" / "viewers",
        base / "analysis" / "core",
        base / "analysis" / "reid",
        base / "analysis" / "postprocessing",
        base / "analysis" / "output",
        base / "events" / "analytics",
        base / "utils",
        base / "models",
        Path("legacy"),
        Path("config"),
        Path("tests"),
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        # Create __init__.py files
        init_file = directory / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Auto-generated during migration"""\n')
    
    print("[OK] Directory structure created")

def move_to_legacy():
    """Move large files to legacy directory"""
    legacy_files = [
        "soccer_analysis_gui.py",
        "combined_analysis_optimized.py",
        "playback_viewer.py",
        "setup_wizard.py",
    ]
    
    legacy_dir = Path("legacy")
    legacy_dir.mkdir(exist_ok=True)
    
    for file in legacy_files:
        file_path = Path(file)
        if file_path.exists():
            dest = legacy_dir / file
            if not dest.exists():  # Don't overwrite if already moved
                shutil.copy2(file_path, dest)
                print(f"[OK] Copied {file} to legacy/ (keeping original)")
            else:
                print(f"[SKIP] {file} already exists in legacy/, skipping")
        else:
            print(f"[SKIP] {file} not found, skipping")

if __name__ == "__main__":
    print("Creating new structure...")
    create_new_structure()
    print("\nCopying files to legacy...")
    move_to_legacy()
    print("\n[OK] Migration setup complete!")
    print("\nNext steps:")
    print("1. Start extracting code from legacy files")
    print("2. Move functionality to new modules")
    print("3. Update imports gradually")

