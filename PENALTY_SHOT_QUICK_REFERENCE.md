# Penalty Shot Analysis - Quick Reference

## Current Status ✅
- ✅ All 4 players found in gallery
- ✅ Rocco Piazza: 389 reference frames (excellent!)
- ✅ Cameron Hill: 3 reference frames (add more for better recognition)
- ✅ Ellie Hill: 4 reference frames (add more, missing anchor frames)
- ✅ James Carlson: 85 reference frames (good)

## Quick Settings for Penalty Shot Video

### In Soccer Analysis GUI → Tracking Tab:

**Detection:**
- Confidence Threshold: **0.25-0.30** (lower to catch brief appearances)
- IOU Threshold: **0.45-0.50**

**Tracking:**
- Track Threshold: **0.30-0.35**
- Match Threshold: **0.55-0.60**
- Track Buffer: **6.0-8.0 seconds** (longer for brief appearances)
- Minimum Track Length: **3-5 frames** (shorter to catch brief appearances)

**Re-ID:**
- Re-ID Similarity Threshold: **0.50-0.55**
- Re-ID Check Interval: **20-25 frames**
- Re-ID Confidence Threshold: **0.70-0.75**

**Gallery Matching:**
- Gallery Similarity Threshold: **0.35-0.40**

### In Analysis Tab:
- ✅ Enable "Learn Player Features"
- ✅ Enable "Track Players"
- ✅ Enable "Export CSV"

## Quick Actions

### 1. Add More Reference Frames (Recommended)
```bash
python player_gallery_seeder.py
```
- Add 2-3 more frames for **Cameron Hill** (goalkeeper position)
- Add 2-3 more frames for **Ellie Hill** (different angles/poses)

### 2. Run Analysis
- Load video in GUI
- Apply settings above
- Click "Start Analysis"

### 3. Fix Missed Players
```bash
# From GUI: Click "🎓 Interactive Player Learning"
# Or run:
python interactive_player_learning.py
```

### 4. Create Anchor Frames for Ellie Hill
After analysis, use Track Review Assigner:
```bash
python track_review_assigner.py
```
- Assign Ellie Hill to her tracks
- Export as anchor frames

## Special Note: James Carlson (Brief Appearance)

Since James appears only briefly:
- **Lower detection threshold to 0.25** (critical!)
- **Increase track buffer to 8-10 seconds**
- **Set minimum track length to 3 frames**
- May need manual frame-by-frame tagging if auto-detection misses him

## Verification

After analysis, check:
- [ ] Rocco detected during penalty shot
- [ ] Cameron Hill identified as goalkeeper
- [ ] Ellie Hill recognized when visible
- [ ] James Carlson detected during brief appearance
- [ ] Player names appear correctly in output video

