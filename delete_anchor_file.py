"""
Quick script to delete an incorrect anchor file.

Usage:
    python delete_anchor_file.py <anchor_file_path>
"""

import sys
import os

if len(sys.argv) < 2:
    print("Usage: python delete_anchor_file.py <anchor_file_path>")
    sys.exit(1)

anchor_file = sys.argv[1]

if not os.path.exists(anchor_file):
    print(f"❌ File not found: {anchor_file}")
    sys.exit(1)

print(f"🗑️  Deleting anchor file: {anchor_file}")
try:
    os.remove(anchor_file)
    print(f"✅ Successfully deleted: {anchor_file}")
    print(f"\n💡 Next steps:")
    print(f"   1. Use Player Gallery Seeder to tag the correct players (Rocco, Cameron, Ellie, James)")
    print(f"   2. Or use Track Review & Player Assignment to assign correct names from CSV")
    print(f"   3. Then convert tracks to anchor frames with correct player names")
except Exception as e:
    print(f"❌ Error deleting file: {e}")
    sys.exit(1)

