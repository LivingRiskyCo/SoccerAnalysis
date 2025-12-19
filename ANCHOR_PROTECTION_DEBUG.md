# Anchor Protection Debugging Guide

## Issue: Cameron Melnik took over Anay Rao despite Anay having anchor frames

### Possible Causes:

1. **Anchor Frame Matching Failed**
   - Anchor frames must match tracks via:
     - Track ID match (if anchor has `track_id`)
     - IoU matching (threshold: 0.7 if track_id present, 0.3 if None)
     - Distance fallback (max 500px)
   - If all matching methods fail, anchor protection is NOT applied
   - **Check logs for**: `⚠ ANCHOR MATCH FAILED` or `⚠ DEBUG: Anchor 'Anay Rao' failed to match`

2. **Track Merging Override**
   - Track merging can transfer identity between tracks
   - If Anay's track was merged into Cameron's track, identity could be lost
   - **Check logs for**: `🔀 Track merge: Merged Track #X into Track #Y`

3. **Re-ID Override Before Anchor Applied**
   - Re-ID matching happens AFTER anchor frames are applied
   - But if anchor matching fails, Re-ID can assign a name
   - **Check logs for**: Gallery match messages before anchor application

4. **Coordinate Mismatch**
   - If anchor frame bboxes are in wrong coordinate system, matching fails
   - **Check logs for**: `⚠ ANCHOR MATCH FAILED` with bbox coordinates

5. **Track ID Changed**
   - If Anay's track_id changed between anchor frame and current frame, matching fails
   - **Check logs for**: Track ID changes in diagnostic messages

### Diagnostic Steps for New Analysis:

1. **Check Anchor Frame Loading**
   - Look for: `🎯 ANCHOR FRAMES LOADED: X frame(s) with Y tag(s)`
   - Verify Anay Rao is in the list

2. **Check Anchor Matching**
   - Look for: `✅ ANCHOR APPLIED: Frame X, Track #Y = 'Anay Rao'`
   - If missing, look for: `⚠ ANCHOR MATCH FAILED` or `⚠ DEBUG: Anchor 'Anay Rao' failed to match`

3. **Check Anchor Protection**
   - Look for: `🛡️ GALLERY BLOCKED: Track #X is anchor-protected for 'Anay Rao'`
   - If missing, anchor protection wasn't applied

4. **Check Track Merging**
   - Look for: `🔀 Track merge: Merged Track #X into Track #Y`
   - Check if Anay's track was merged

5. **Check Re-ID Override**
   - Look for: `✓ DIAGNOSTIC: match_player - Cameron Melnik: final_similarity=X`
   - Check if Cameron was matched to Anay's track

### Prevention Measures:

1. **Ensure Anchor Frames Have Correct Track IDs**
   - When tagging in Setup Wizard or Gallery Seeder, verify track IDs match
   - If track_id is None, ensure bbox coordinates are accurate

2. **Use Multiple Anchor Frames**
   - Tag the same player in multiple frames throughout the video
   - This provides redundancy if one frame fails to match

3. **Check Coordinate System**
   - Ensure anchor frame bboxes are in the same coordinate system as detections
   - Check video resolution matches between anchor frames and analysis

4. **Monitor Diagnostic Messages**
   - Watch for anchor match failures during analysis
   - Check if protection is being applied correctly

### Clean Gallery Strategy:

1. **Remove Corrupted Frames** (already done for Anay Rao)
   ```bash
   python cleanup_gallery.py --video "20251001_183951" --players "Anay Rao"
   ```

2. **Create Fresh Anchor Frames**
   - Use Setup Wizard or Gallery Seeder
   - Tag Anay Rao in multiple frames (at least 3-5 frames)
   - Verify track IDs are correct
   - Ensure bbox coordinates are accurate

3. **Run Analysis with Enhanced Diagnostics**
   - The system will now log:
     - Anchor frame loading
     - Anchor matching attempts
     - Anchor protection application
     - Gallery blocking for protected tracks

4. **Monitor Output**
   - Watch for anchor match failures
   - Verify protection is applied
   - Check if Re-ID tries to override (should be blocked)

