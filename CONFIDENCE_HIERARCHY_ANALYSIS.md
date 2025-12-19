# Confidence Hierarchy and Player Assignment Flow

## Complete Hierarchy (Actual Implementation)

### 1. **Anchor Frames (1.00 confidence)** - HIGHEST PRIORITY ✅
   - **Source**: Setup Wizard manual tags (`PlayerTagsSeed-{video}.json`)
   - **Applied**: BEFORE gallery matching (line 5539)
   - **Protection**: Checked at line 6364-6373 - NEVER overridden by gallery matches
   - **Matching Strategy** (IMPROVED):
     - **Primary**: Bbox position matching (IoU > 0.2, distance < 150px) - MORE STABLE
     - **Fallback**: Track ID matching (if bbox fails)
   - **Why bbox first**: Track IDs can change between Setup Wizard and Analyzer, but bbox positions are more stable
   - **Confidence**: Always 1.00 (ground truth)

### 2. **Gallery Matches (0.48-1.00 confidence)** - SECOND PRIORITY
   - **Source**: Re-ID similarity matching against player gallery
   - **Applied**: AFTER anchor frames (line 5772)
   - **Protection**: Checks for anchor frames before applying (line 6364-6373)
   - **Threshold**: `gallery_similarity_threshold` (default: 0.48, lowered from Re-ID threshold for cross-video matching)
   - **Can be overridden by**: Only anchor frames (1.00 confidence)
   - **Update rules**:
     - High confidence (>=0.75): Requires 0.20+ improvement AND 60+ frames
     - Medium confidence (>=0.70): Requires 0.15+ improvement AND 30+ frames
     - Low confidence (<0.70): Requires 0.10+ improvement AND 15+ frames, OR 0.20+ immediate improvement

### 3. **Route Locked (Early Frame Assignments)** - THIRD PRIORITY
   - **Source**: Gallery matches in first 1000 frames
   - **Applied**: During gallery matching (line 6834-6842)
   - **Protection**: Similar to high-confidence locks
   - **Can be overridden by**: Anchor frames (1.00), or very high confidence updates

## The Problem (FIXED)

### Issue 1: Anchor Frame Matching May Fail ✅ FIXED
- **OLD**: Anchor frames tried track_id FIRST, then bbox
- **NEW**: Anchor frames try bbox FIRST (more stable), then track_id as fallback
- **IMPROVED**: More lenient bbox matching (IoU > 0.2 instead of 0.3, distance < 150px instead of 100px)

### Issue 2: Track ID Instability ✅ MITIGATED
- Track IDs can still change, but bbox matching is now primary
- Bbox positions are more stable across frames than track IDs

### Issue 3: Timing of Application ✅ ACCEPTABLE
- Anchor frames applied BEFORE tracker update (line 5539)
- Uses bbox matching primarily, which works with current frame detections
- Track ID matching is fallback only

### Issue 4: Gallery Matching Happens After Tracking ✅ PROTECTED
- Gallery matching checks for anchor frames (line 6364-6373)
- Anchor frames with 1.00 confidence are NEVER overridden

## Root Cause Analysis

The Setup Wizard tags players by the track_id that exists AT THAT MOMENT in the Setup Wizard. But when the analyzer runs:
1. Tracker may assign different IDs (tracking is non-deterministic) ✅ MITIGATED by bbox matching
2. Track IDs can fragment/merge ✅ MITIGATED by bbox matching
3. Anchor frames try to match by track_id, but that ID doesn't exist anymore ✅ FIXED - bbox matching is primary

## Solution Implemented

1. ✅ **Bbox matching is now PRIMARY** (more stable than track_id)
2. ✅ **More lenient bbox matching** (IoU > 0.2, distance < 150px)
3. ✅ **Track ID matching is fallback** (only if bbox fails)
4. ✅ **Better logging** when anchor frames fail to match

## How to Debug

When anchor frames fail to match, you'll see:
```
⚠ ANCHOR FRAME FAILED: Frame {N}, {player_name} - bbox={...}, track_id={...} - no matching detection found
⚠ WARNING: Frame {N} has {X} anchor frame(s) but NONE matched! Check bbox positions and track IDs.
```

**Common causes**:
1. Player not detected in that frame (YOLO missed them)
2. Bbox position changed significantly (player moved > 150px)
3. IoU too low (< 0.2) due to bbox size/shape changes
4. Track ID changed and bbox matching failed

**Solutions**:
1. Tag anchor frames in frames where player is clearly visible
2. Use "Tag All Instances" to create multiple anchor frames
3. Check that bbox positions in Setup Wizard match actual player positions

