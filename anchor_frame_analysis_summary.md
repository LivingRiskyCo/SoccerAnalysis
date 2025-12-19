# Anchor Frame Analysis Summary

## Issue #1: Wrong File Being Loaded ✅ FIXED

### Problem Found:
- **Wrong file**: `PlayerTagsSeed-20251001_184229.json` (dash, modified 11/30/2025)
  - Contains: Jax Derryberry (686 tags!), Guest Player (28 tags), Cameron Hill, Kevin Hill, Wesley Beckett
  - **Jax and Guest Player are NOT in the video** (user confirmed)
  
- **Correct file**: `PlayerTagsSeed_20251001_184229.json` (underscore, modified 12/1/2025)
  - Contains: Rocco Piazza, Ellie Hill, James Carlson, Cameron Hill
  - **These are the correct players** (user confirmed)

### Root Cause:
The code only checked for files with **dash** format (`PlayerTagsSeed-{name}.json`) and loaded the first match, which was the old/wrong file.

### Fix Applied:
1. Added underscore format to search patterns: `PlayerTagsSeed_{name}.json`
2. Changed loading logic to:
   - Find ALL matching files
   - Sort by modification time (newest first)
   - Load the most recent file
3. This ensures the system always uses the most up-to-date anchor frames

## Issue #2: Multiple Track IDs Per Player ⚠️ NEEDS FIX

### Problem Found:
Several players appear on multiple track IDs in anchor frames:
- **Cameron Hill**: Tracks 23, 26, 27
- **Guest Player**: Tracks 7, 12, 19  
- **Jax Derryberry**: Tracks 10, 11, 17, 20, 21, 22

### Why This Causes Issues:
1. When a player is tagged on multiple track IDs, anchor protection applies to each track separately
2. If tracks merge or track IDs change, the system doesn't know which is the "correct" track
3. The player-to-track mapping may point to an old/inactive track ID, blocking assignment to the new track

### Next Steps:
The code already has spatial recovery logic, but we need to ensure:
1. When a player appears on multiple tracks, the system prioritizes the most recent/active track
2. Anchor protection transfers when track IDs change
3. Player-to-track mappings are cleared when tracks become inactive (already fixed in previous update)

## Issue #3: Missing Players in Anchor Frames ✅ FIXED

### Problem:
- Rocco Piazza: NOT in old file, but IS in new file
- Ellie Hill: NOT in old file, but IS in new file  
- James Carlson: NOT in old file, but IS in new file

### Solution:
By loading the newest file (with underscore), these players will now be found.

## Verification

Run the analysis again and check:
1. Does it load `PlayerTagsSeed_20251001_184229.json` (underscore, newest)?
2. Are Rocco, Ellie, and James now being tracked?
3. Are Jax and Guest Player no longer appearing?

