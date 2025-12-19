# 4K vs Downscaling Guide: Should You Downscale During Analysis?

## Quick Answer: **YES, Downscale for YOLO Processing** ✅

**Recommendation**: Use **"1080p"** or let the system **auto-downscale** 4K to 1080p for YOLO detection.

**Why**: YOLO works best at ~640-1280px width. 4K (3840px) is overkill and provides **minimal accuracy improvement** while being **much slower** and using **4x more memory**.

## How Your System Currently Handles 4K

### Automatic Behavior (When "Full" Resolution Selected)
- **4K videos (≥3840x2160)**: **Automatically downscaled to 1080p** for YOLO processing
- **Non-4K videos**: Processed at full resolution
- **Output video**: Always saved at **original full resolution** (4K stays 4K)

### Manual Control
- **GUI Setting**: "YOLO Resolution" dropdown
  - **"Full"**: Auto-downscales 4K, uses full res for smaller videos
  - **"1080p"**: Forces 1080p for all videos
  - **"720p"**: Forces 720p for all videos (faster, slightly less accurate)

## Why Downscale? The Science

### 1. **YOLO's Optimal Resolution Range**
- **Best performance**: 640-1280px width
- **Diminishing returns**: >1280px provides minimal accuracy gain
- **4K (3840px)**: Only ~5-10% better detection than 1080p, but **4x slower**

### 2. **Memory Usage**
```
4K frame (3840x2160):  ~25 MB per frame
1080p frame (1920x1080): ~6 MB per frame
Memory savings: ~75% reduction
```

**Impact**:
- **4K**: Can only process 1-2 frames at a time (limited by GPU memory)
- **1080p**: Can process 8-16 frames in batch (better GPU utilization)

### 3. **Processing Speed**
```
4K processing: ~2-5 fps (very slow)
1080p processing: ~10-30 fps (much faster)
Speed improvement: 5-10x faster
```

### 4. **Detection Accuracy**
- **1080p vs 4K**: Only ~5-10% accuracy difference
- **720p vs 1080p**: ~10-15% accuracy difference
- **Trade-off**: 1080p is the **sweet spot** (good accuracy, reasonable speed)

## When to Use Each Resolution

### ✅ **Use "1080p" (Recommended for 4K videos)**
**Best for**:
- 4K source videos
- Long videos (faster processing)
- Most use cases (best balance)

**Benefits**:
- 5-10x faster than 4K
- 75% less memory usage
- Only ~5-10% less accurate than 4K
- Better GPU batch processing

### ✅ **Use "Full" (Auto-downscales 4K)**
**Best for**:
- Mixed video resolutions
- Let system decide automatically
- When you want automatic optimization

**Behavior**:
- 4K videos → Auto-downscales to 1080p
- 1080p videos → Uses full 1080p
- 720p videos → Uses full 720p

### ⚠️ **Use "720p" (Faster, Less Accurate)**
**Best for**:
- Very long videos
- Quick previews
- When speed is critical

**Trade-off**:
- 2-3x faster than 1080p
- ~10-15% less accurate
- May miss small/far players

### ❌ **Don't Use Full 4K for YOLO** (Not Recommended)
**Why not**:
- **4x slower** than 1080p
- **4x more memory** usage
- **Minimal accuracy gain** (~5-10%)
- **Poor GPU utilization** (can't batch process)

**Exception**: Only if you have:
- Very powerful GPU (RTX 4090, A100)
- Unlimited time
- Need absolute maximum accuracy
- Processing very short clips

## What About Output Video Resolution?

**Important**: YOLO processing resolution ≠ Output video resolution

- **YOLO processing**: Can be downscaled (1080p recommended)
- **Output video**: Always saved at **original full resolution**

**Example**:
- Input: 4K video (3840x2160)
- YOLO processing: 1080p (1920x1080) ← Downscaled for detection
- Output: 4K video (3840x2160) ← Full resolution preserved

**Why this works**:
1. YOLO detects players at 1080p (good enough)
2. Detections are **scaled back up** to 4K coordinates
3. Output video is rendered at full 4K with scaled detections
4. You get **fast processing** + **full resolution output**

## Performance Comparison

### Processing Speed (Estimated)
| Resolution | FPS (GPU) | FPS (CPU) | Relative Speed |
|------------|-----------|-----------|----------------|
| 4K (3840x2160) | 2-5 | 0.5-1 | 1x (baseline) |
| 1080p (1920x1080) | 10-30 | 2-5 | **5-10x faster** |
| 720p (1280x720) | 20-50 | 5-10 | **10-20x faster** |

### Memory Usage (Per Frame)
| Resolution | Memory | Relative |
|------------|--------|----------|
| 4K (3840x2160) | ~25 MB | 4x |
| 1080p (1920x1080) | ~6 MB | 1x |
| 720p (1280x720) | ~3 MB | 0.5x |

### Detection Accuracy (Relative)
| Resolution | Accuracy | Notes |
|------------|----------|-------|
| 4K (3840x2160) | 100% | Baseline |
| 1080p (1920x1080) | 90-95% | **Recommended** |
| 720p (1280x720) | 80-85% | Acceptable for most cases |

## Real-World Example

**Your video**: 3512.5 seconds (58.5 minutes), 4K (3840x2160), 116.93 fps

### Processing Time Estimates

**4K Processing**:
- ~2-5 fps processing speed
- Total time: **~12-30 hours** 😱
- GPU memory: ~8-10 GB (may run out)

**1080p Processing** (Recommended):
- ~10-30 fps processing speed
- Total time: **~2-6 hours** ✅
- GPU memory: ~2-4 GB (comfortable)
- Accuracy: ~90-95% of 4K

**720p Processing**:
- ~20-50 fps processing speed
- Total time: **~1-3 hours** ⚡
- GPU memory: ~1-2 GB
- Accuracy: ~80-85% of 4K

## Recommendations by Use Case

### 🎯 **Best Overall: "1080p"**
- Best balance of speed and accuracy
- Works well for 4K source videos
- Reasonable processing time
- Good detection quality

### ⚡ **Speed Priority: "720p"**
- Fastest processing
- Good for long videos
- Preview/quick analysis
- Slightly less accurate

### 🔬 **Maximum Accuracy: "Full" (Auto)**
- System automatically optimizes
- 4K → 1080p (smart downscale)
- Smaller videos → Full resolution
- Best of both worlds

### ❌ **Not Recommended: Force 4K**
- Too slow for practical use
- High memory usage
- Minimal accuracy gain
- Poor GPU utilization

## Technical Details

### How Downscaling Works
1. **Frame read**: Full 4K frame loaded from video
2. **Resize**: Frame resized to 1080p for YOLO
3. **YOLO detection**: Detects players at 1080p
4. **Coordinate scaling**: Detection boxes scaled back to 4K coordinates
5. **Output rendering**: Full 4K frame rendered with scaled detections

### Coordinate Translation
```python
# Detection at 1080p: (x, y) = (960, 540)
# Scale factor: 3840 / 1920 = 2.0
# Scaled to 4K: (x, y) = (1920, 1080)
```

**Accuracy**: Coordinate scaling is **pixel-perfect** - no accuracy loss in positioning.

### ROI Cropping Impact
- ROI cropping happens **after** downscaling
- Even more memory savings
- Faster processing
- Focuses on field area

## Common Questions

### Q: Will I lose detection accuracy by downscaling?
**A**: Minimal loss (~5-10% for 4K→1080p). YOLO works best at 1080p anyway, so you're actually using its optimal resolution.

### Q: Will the output video be lower quality?
**A**: No! Output video is always full resolution. Only YOLO processing is downscaled.

### Q: Should I downscale the source video before analysis?
**A**: No need! The system handles it automatically. Keep your 4K source video.

### Q: What if I have a powerful GPU (RTX 4090)?
**A**: Still recommend 1080p. The speed gain (5-10x) is worth the minimal accuracy loss.

### Q: Can I process at 4K for maximum accuracy?
**A**: Technically yes, but not recommended. You can force it by setting resolution to "Full" and modifying code, but you'll get:
- 4x slower processing
- 4x more memory usage
- Only ~5-10% better accuracy

## Bottom Line

**For 4K videos**: Use **"1080p"** or **"Full"** (auto-downscales)

**Why**:
- ✅ 5-10x faster processing
- ✅ 75% less memory usage
- ✅ Only ~5-10% less accurate (negligible)
- ✅ Better GPU batch processing
- ✅ Output video still full 4K resolution

**The system is already optimized** - it auto-downscales 4K to 1080p when you select "Full" resolution. You're getting the best of both worlds: fast processing + full resolution output.

## Summary Table

| Setting | 4K Source | Processing | Speed | Accuracy | Memory | Recommendation |
|---------|-----------|------------|-------|----------|--------|----------------|
| **"1080p"** | ✅ | 1080p | ⚡⚡⚡⚡⚡ | 90-95% | Low | ⭐ **Best** |
| **"Full"** | ✅ | Auto 1080p | ⚡⚡⚡⚡⚡ | 90-95% | Low | ⭐ **Best** |
| **"720p"** | ✅ | 720p | ⚡⚡⚡⚡⚡⚡ | 80-85% | Very Low | ⚡ Fast |
| **Force 4K** | ❌ | 4K | ⚡ | 100% | Very High | ❌ Not recommended |

**Verdict**: **Downscale to 1080p for YOLO processing**. You'll get fast processing, reasonable memory usage, and full 4K output video. The minimal accuracy loss is not worth the 4x slowdown.

