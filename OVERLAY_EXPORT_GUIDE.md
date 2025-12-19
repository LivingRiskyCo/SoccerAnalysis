# Overlay System Export Guide

## What Gets Exported

When you run an analysis with the overlay system enabled, here's what gets created:

### 1. **Original Video** (Input)
- **File**: Your original video file (e.g., `video.mp4`)
- **Content**: Clean video, no overlays
- **Status**: ✅ **This is already your base video!**
- **Note**: This is the file you started with - it's already clean and ready to use

### 2. **Base Video** (Optional - Usually Not Needed)
- **File**: `*_base.mp4` (e.g., `video_analyzed_base.mp4`)
- **Content**: Clean video copy without overlays
- **When to Use**: 
  - ✅ Original video was modified (dewarping, cropping, resolution changes)
  - ✅ You want a guaranteed clean copy in the output directory
  - ✅ Original file is in a different location
- **When NOT Needed**:
  - ❌ Original video is already clean (most common case)
  - ❌ You already have the original file
  - ❌ No modifications were applied to the original

**Recommendation**: Leave "Save Base Video" **unchecked** unless you specifically need a modified clean copy.

### 3. **Overlay Metadata** (Recommended)
- **File**: `*_overlay_metadata.json` (e.g., `video_analyzed_overlay_metadata.json`)
- **Content**: All visualization data (player positions, colors, trajectories, analytics)
- **Size**: Small (few MB)
- **Use**: Load in playback viewer for flexible overlay rendering
- **Status**: ✅ **Highly recommended** - enables all overlay features

### 4. **Analyzed Video** (Optional)
- **File**: `*_analyzed.mp4` (e.g., `video_analyzed.mp4`)
- **Content**: Video with overlays burned in
- **When to Use**:
  - ✅ You want a pre-rendered video with overlays
  - ✅ Sharing with others who don't have the playback viewer
  - ✅ Quick preview without loading metadata
- **When NOT Needed**:
  - ❌ You prefer flexible overlay rendering (use metadata instead)
  - ❌ Faster analysis (skip video encoding)
  - ❌ Smaller file sizes (metadata is much smaller)

**Recommendation**: Disable "Enable Video Encoding" if you only need tracking data and overlay metadata.

### 5. **Tracking Data CSV** (Recommended)
- **File**: `*_tracking_data.csv` (e.g., `video_analyzed_tracking_data.csv`)
- **Content**: All tracking data (positions, speeds, analytics)
- **Use**: Data analysis, statistics, import into other tools
- **Status**: ✅ **Highly recommended**

## Recommended Export Settings

### For Maximum Flexibility (Recommended)
```
✅ Export Overlay Metadata
✅ Export CSV
❌ Save Base Video (you already have the original)
❌ Enable Video Encoding (use metadata for rendering instead)
```
**Result**: Small files, fast analysis, maximum flexibility

### For Quick Preview
```
✅ Export Overlay Metadata
✅ Export CSV
✅ Enable Video Encoding
❌ Save Base Video
```
**Result**: Pre-rendered video + metadata for later flexibility

### For Sharing/Archiving
```
✅ Export Overlay Metadata
✅ Export CSV
✅ Enable Video Encoding
✅ Save Base Video (if original was modified)
```
**Result**: Complete package with all files

## File Size Comparison

- **Original Video**: ~100-500 MB (depends on length/resolution)
- **Base Video**: ~100-500 MB (duplicate of original if no modifications)
- **Overlay Metadata**: ~1-10 MB (very small!)
- **Analyzed Video**: ~100-500 MB (same size as original)
- **CSV**: ~1-50 MB (depends on tracking data)

**Total with metadata only**: ~102-510 MB (original + metadata + CSV)
**Total with all exports**: ~300-1500 MB (original + base + analyzed + metadata + CSV)

## Workflow Recommendations

1. **First Analysis**: Export metadata + CSV, skip video encoding for speed
2. **Review in Playback Viewer**: Load CSV + metadata, toggle overlays as needed
3. **Export Specific Videos**: Use overlay renderer to create videos with custom overlays
4. **Share Results**: Export final video with desired overlays

## Summary

- **Original Video** = Your base video (already clean)
- **Base Video Export** = Usually redundant (only needed if original was modified)
- **Overlay Metadata** = Small, flexible, recommended
- **Analyzed Video** = Optional pre-rendered version
- **CSV** = Essential for data analysis

**Best Practice**: Export metadata + CSV, skip base video (you already have it), and optionally skip analyzed video (render on-demand from metadata).

