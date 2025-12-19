# Soccer Analysis - Best Practices Guide

## 🎯 Overview

This guide will help you get the best results from the soccer analysis system. Follow these practices to improve player tracking accuracy and reduce manual corrections.

---

## 📹 Video Preparation

### ✅ DO:
1. **Use stable footage**
   - Tripod-mounted cameras work best
   - Avoid excessive camera shake
   - If handheld, use stabilization software

2. **Good lighting**
   - Well-lit fields improve detection
   - Avoid extreme shadows or overexposure
   - Consistent lighting throughout video

3. **Appropriate resolution**
   - 1080p (1920x1080) is ideal
   - Higher resolution = better detection but slower processing
   - Lower resolution = faster but less accurate

4. **Frame rate**
   - 24-30fps is sufficient for most analysis
   - Higher FPS (60-120) helps with fast movements but increases processing time
   - Match your tracker settings to your FPS

5. **Camera angle**
   - Elevated view (press box, stands) is best
   - Side view works well
   - Avoid extreme angles (too low or too high)

### ❌ DON'T:
- Don't use heavily compressed videos (low bitrate)
- Don't use videos with lots of motion blur
- Don't use videos with frequent cuts/edits mid-game
- Don't use videos with watermarks overlaying players

---

## 🎬 Video Editing Tips

### Before Analysis:

1. **Trim to relevant sections**
   - Remove pre-game, halftime, post-game footage
   - Focus on active play periods
   - Shorter videos = faster analysis

2. **Stabilize if needed**
   - Use video editing software to stabilize shaky footage
   - Crop to remove black borders after stabilization

3. **Normalize frame rate**
   - Convert to consistent FPS (24, 30, or 60)
   - Avoid variable frame rate videos

4. **Check video codec**
   - H.264 or H.265 work well
   - Avoid unusual codecs that might cause issues

### What NOT to Edit:
- ❌ Don't add overlays, graphics, or text on top of players
- ❌ Don't apply heavy color grading that changes jersey colors
- ❌ Don't crop out important parts of the field
- ❌ Don't speed up/slow down the video (keep original speed)

---

## 🚀 Recommended Workflow

### Step 1: Initial Setup (First Time)

1. **Run Setup Wizard**
   - Load your video
   - Navigate to frame 0 (beginning)
   - Tag 5-10 key players (goalkeepers, star players)
   - Tag players from BOTH teams
   - This creates anchor frames automatically

2. **Tag at multiple frames**
   - Frame 0 (beginning)
   - Middle of video (~50% through)
   - End of video
   - Tag the SAME players at each frame

3. **Save and run first analysis**
   - Let the system learn from your anchor frames
   - Review the results

### Step 2: Build Player Gallery

1. **Use "Tag Players (Gallery)" tool**
   - Load the same video (or different videos)
   - Navigate to clear frames where players are visible
   - Tag players with their names
   - Add 3-5 reference frames per player
   - Focus on different angles, poses, and situations

2. **Best frames to tag:**
   - Players facing camera (front view)
   - Players in profile (side view)
   - Players running (action poses)
   - Different lighting conditions
   - Different parts of the field

3. **Tag multiple uniforms**
   - If players change jerseys, tag each variant
   - System supports multiple uniform variants per player

### Step 3: Run Analysis with Gallery

1. **Enable player tracking**
   - Check "Track Players" checkbox
   - Set appropriate tracking parameters:
     - Track Buffer Time: 8.0 seconds (default)
     - Min Track Length: 3 frames (default)
     - Re-ID Similarity: 0.5 (default)

2. **Enable Re-ID**
   - Check "Re-ID (Re-identification)"
   - This uses your player gallery for matching

3. **Run analysis**
   - System will use anchor frames + gallery for tracking
   - Monitor progress in console

### Step 4: Review and Correct

1. **Use Conflict Resolution**
   - Open "Conflict Resolution" from Tools menu
   - Review any ID switching or conflicts
   - Correct player assignments

2. **Add more anchor frames**
   - If you see tracking errors, jump to that frame
   - Use "Open Gallery Seeder at Frame" feature
   - Tag the correct player at that frame
   - Re-run analysis

3. **Iterate**
   - More anchor frames = better tracking
   - More gallery entries = better Re-ID
   - Repeat until satisfied

---

## 🎯 Anchor Frame Strategy

### When to Create Anchor Frames:

1. **Setup Wizard (Initial)**
   - Tag 5-10 players at beginning, middle, end
   - Creates ground truth for tracking

2. **During Analysis (Corrections)**
   - When you see ID switching
   - When tracking gets confused
   - At key game moments (scrum, substitution, etc.)

3. **Best Practices:**
   - ✅ Tag same players across multiple frames
   - ✅ Tag at clear, visible frames
   - ✅ Tag players from both teams
   - ✅ Tag at different game situations
   - ❌ Don't tag blurry/occluded players
   - ❌ Don't tag only at the beginning

### How Many Anchor Frames?

- **Minimum**: 3-5 per key player
- **Recommended**: 10-20 total across all players
- **Optimal**: 20-50 total (diminishing returns after ~50)

---

## 👥 Player Gallery Strategy

### Building a Good Gallery:

1. **Start with key players**
   - Goalkeepers (always visible)
   - Star players (most important)
   - Players you track frequently

2. **Add variety**
   - Different angles (front, side, back)
   - Different poses (running, standing, jumping)
   - Different lighting (sunny, cloudy, shadows)
   - Different field positions

3. **Multiple reference frames**
   - System now supports up to 1000 frames per player
   - Aim for 10-20 high-quality frames per player
   - More frames = better recognition

4. **Quality over quantity**
   - Clear, visible players
   - Good lighting
   - Full body visible (not cropped)
   - Distinctive features visible

### Gallery Maintenance:

1. **Regular updates**
   - Add new frames from new videos
   - Update when players change uniforms
   - Remove low-quality frames

2. **Use cleanup tool**
   - Run `cleanup_gallery_references.py` periodically
   - Removes excessive frames
   - Keeps highest quality frames

---

## ⚙️ Tracking Parameters Guide

### Track Buffer Time (8.0s default)
- **What it does**: How long to keep lost tracks alive
- **Higher** (10-12s): Less blinking, better ID persistence, but may keep wrong IDs longer
- **Lower** (4-6s): More responsive, but more ID switching
- **Best for**: Most videos work well with 8.0s

### Min Track Length (3 frames default)
- **What it does**: Frames before track activates
- **Higher** (5-10): More stable, prevents early ID switching
- **Lower** (1-2): Faster activation, but more false positives
- **Best for**: 3 frames is good for most cases

### Re-ID Similarity Threshold (0.5 default)
- **What it does**: How similar a detection must be to match gallery
- **Higher** (0.6-0.7): Stricter matching, fewer false matches
- **Lower** (0.3-0.4): More lenient, more matches but more errors
- **Best for**: 0.5 is balanced

### Match Threshold (0.8 default)
- **What it does**: Detection confidence threshold
- **Higher** (0.9): Only high-confidence detections
- **Lower** (0.6-0.7): More detections, including lower confidence
- **Best for**: 0.8 works well for most videos

---

## 🔧 Common Issues & Solutions

### Issue: Players losing IDs frequently
**Solutions:**
- Add more anchor frames at problem areas
- Increase Track Buffer Time to 10-12s
- Increase Min Track Length to 5
- Add more reference frames to gallery

### Issue: Wrong players being matched
**Solutions:**
- Increase Re-ID Similarity Threshold to 0.6-0.7
- Add more distinctive reference frames to gallery
- Use anchor frames to lock correct IDs
- Check that gallery has correct players

### Issue: Players not being detected
**Solutions:**
- Lower Match Threshold to 0.6-0.7
- Check video quality (resolution, lighting)
- Ensure players are fully visible (not cropped)
- Try different YOLO resolution settings

### Issue: Slow processing
**Solutions:**
- Lower YOLO resolution (640 instead of 1280)
- Process every Nth frame (2 or 3)
- Use preview mode for testing
- Reduce video length (trim to relevant sections)

### Issue: ID switching during scrums
**Solutions:**
- Use OC-SORT tracker (better for bunched players)
- Add anchor frames before/after scrums
- Increase Track Buffer Time
- Tag players in gallery with scrum-specific poses

---

## 📊 Quality Checklist

Before running analysis, check:

- [ ] Video is stable (not shaky)
- [ ] Good lighting throughout
- [ ] Players are clearly visible
- [ ] At least 5-10 anchor frames created
- [ ] Player gallery has key players
- [ ] Tracking parameters set appropriately
- [ ] Re-ID enabled if using gallery

After analysis, check:

- [ ] Review conflict resolution
- [ ] Check for ID switching
- [ ] Verify player names are correct
- [ ] Add more anchor frames if needed
- [ ] Update gallery with new reference frames

---

## 💡 Pro Tips

1. **Start small, scale up**
   - Test with short clips first (30-60 seconds)
   - Verify settings work well
   - Then process full videos

2. **Use preview mode**
   - Test settings quickly
   - See results before full analysis
   - Adjust parameters as needed

3. **Build gallery over time**
   - Don't try to tag everything at once
   - Add players as you need them
   - Quality matters more than quantity

4. **Document your workflow**
   - Note which settings work best for your videos
   - Keep track of successful configurations
   - Share learnings with your team

5. **Iterate and improve**
   - First analysis won't be perfect
   - Add anchor frames where needed
   - Re-run analysis after corrections
   - Each iteration should get better

---

## 🎓 Learning Resources

- **Anchor Frames Guide**: See `ANCHOR_FRAMES_GUIDE.md`
- **Batch Workflow**: Use `batch_anchor_frame_workflow.py` for planning
- **Helper Scripts**: Use `anchor_frame_helper.py` for analysis

---

## ❓ Still Having Issues?

1. **Check console output**
   - Look for error messages
   - Check frame counts
   - Verify video loaded correctly

2. **Review tracking parameters**
   - Try different settings
   - Use defaults as starting point
   - Adjust based on your video

3. **Add more anchor frames**
   - More ground truth = better tracking
   - Tag at problem areas
   - Re-run analysis

4. **Improve gallery**
   - Add more reference frames
   - Use high-quality frames
   - Tag different angles/poses

---

**Remember**: The system learns and improves with more data. Start with good anchor frames, build a solid gallery, and iterate based on results. Each video you process makes the system better! 🚀

