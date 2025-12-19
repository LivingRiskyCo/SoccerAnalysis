"""
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

# Import and run - use SoccerID to match folder name
from SoccerID.main import main

if __name__ == "__main__":
    main()
