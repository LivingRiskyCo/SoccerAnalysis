"""
Quick test script to verify BoxMOT is available for the GUI
Run this before starting the GUI to check if BoxMOT will be detected
"""

import sys
import os

print("=" * 60)
print("BoxMOT Detection Test for GUI")
print("=" * 60)

# Test 1: Check if boxmot can be imported
print("\n1. Testing direct boxmot import...")
try:
    from boxmot import DeepOcSort, StrongSort, BotSort
    print("   [OK] boxmot imported successfully!")
    print("   [OK] Available trackers: DeepOcSort, StrongSort, BotSort")
except ImportError as e:
    print(f"   [FAIL] boxmot import failed: {e}")
    print("   → Install with: pip install boxmot")
    sys.exit(1)
except Exception as e:
    print(f"   ✗ Unexpected error: {e}")
    sys.exit(1)

# Test 2: Check wrapper import
print("\n2. Testing boxmot_tracker_wrapper import...")
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    from boxmot_tracker_wrapper import BOXMOT_AVAILABLE
    print(f"   [OK] Wrapper imported successfully!")
    print(f"   [OK] BOXMOT_AVAILABLE = {BOXMOT_AVAILABLE}")
    
    if not BOXMOT_AVAILABLE:
        print("   [WARN] Wrapper reports BoxMOT as unavailable")
        sys.exit(1)
except ImportError as e:
    print(f"   [FAIL] Wrapper import failed: {e}")
    print("   → Make sure boxmot_tracker_wrapper.py is in the same directory")
    sys.exit(1)
except Exception as e:
    print(f"   ✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Simulate GUI detection
print("\n3. Simulating GUI detection logic...")
try:
    from boxmot import DeepOcSort
    boxmot_available = True
    print("   [OK] Direct import works (GUI will detect this)")
    
    from boxmot_tracker_wrapper import BOXMOT_AVAILABLE
    if BOXMOT_AVAILABLE:
        print("   [OK] Wrapper confirms availability")
        tracker_options = ["bytetrack", "ocsort", "deepocsort", "strongsort", "botsort"]
        print(f"   [OK] GUI should show {len(tracker_options)} tracker options:")
        for opt in tracker_options:
            print(f"      - {opt}")
    else:
        print("   [WARN] Wrapper says unavailable (but direct import works)")
        boxmot_available = False
except Exception as e:
    print(f"   [FAIL] Detection failed: {e}")
    import traceback
    traceback.print_exc()
    boxmot_available = False

print("\n" + "=" * 60)
if boxmot_available:
    print("[SUCCESS] BoxMOT should be detected in GUI")
    print("  -> Restart the GUI to see the new tracker options")
else:
    print("[FAILED] BoxMOT will not be detected in GUI")
    print("  -> Check the errors above and fix them")
print("=" * 60)

