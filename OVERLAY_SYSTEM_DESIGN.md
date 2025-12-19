# Overlay System Design - Separating Visualizations from Base Video

## Current Architecture (Everything Burned In)

**Current Flow:**
1. Analysis runs → Detects players/ball → Tracks → Identifies players
2. **All visualizations are drawn directly onto video frames** (boxes, labels, circles, trails, analytics)
3. Final video is saved with everything permanently embedded
4. Playback viewer loads the analyzed video (already has overlays)

**Problems:**
- ❌ Can't change visualization style without re-analyzing
- ❌ Can't toggle overlays on/off in the analyzed video
- ❌ Larger file sizes (overlays add visual data)
- ❌ Can't customize labels/colors after analysis
- ❌ Base video is lost (can't get clean video back)

## Proposed Architecture (Base Video + Overlay Metadata)

**New Flow:**
1. Analysis runs → Detects players/ball → Tracks → Identifies players
2. **Save base video** (clean, no overlays) OR skip video entirely
3. **Save overlay metadata** (JSON/CSV with all visualization data)
4. Playback viewer loads base video + overlay metadata → Renders overlays on-the-fly

**Benefits:**
- ✅ Change visualization style without re-analyzing
- ✅ Toggle overlays on/off in real-time
- ✅ Smaller file sizes (base video only, overlays are metadata)
- ✅ Customize labels/colors/styles after analysis
- ✅ Base video preserved (can export clean video)
- ✅ Multiple visualization styles from same analysis
- ✅ Faster analysis (no video encoding if overlays disabled)

## Overlay Metadata Structure

```json
{
  "video_path": "path/to/base_video.mp4",
  "fps": 30.0,
  "total_frames": 17640,
  "overlays": {
    "frame_0": {
      "players": [
        {
          "track_id": 1,
          "bbox": [x1, y1, x2, y2],
          "center": [x, y],
          "player_name": "John Smith",
          "team": "Gray",
          "jersey_number": "5",
          "confidence": 0.95,
          "color": [128, 128, 128]  // BGR
        }
      ],
      "ball": {
        "center": [x, y],
        "detected": true,
        "trail": [[x1, y1], [x2, y2], ...]  // Recent positions
      }
    }
  },
  "analytics": {
    "frame_0": {
      "player_1": {
        "speed_mps": 3.2,
        "distance_to_ball": 5.5,
        ...
      }
    }
  },
  "visualization_settings": {
    "show_boxes": true,
    "show_circles": false,
    "show_labels": true,
    "show_analytics": true,
    "label_type": "name",  // "name", "id", "jersey", "custom"
    "box_color_mode": "team",  // "team", "custom", "track"
    "custom_colors": {...}
  }
}
```

## Implementation Options

### Option A: Full Overlay System (Recommended)
- **Base Video**: Save clean video (no overlays) during analysis
- **Overlay Metadata**: Save all visualization data to JSON
- **Playback**: Render overlays on-the-fly from metadata
- **Export**: Can export video with overlays when needed

**Pros:**
- Maximum flexibility
- Smallest file sizes
- Fastest analysis (optional video encoding)

**Cons:**
- More complex implementation
- Requires overlay rendering engine

### Option B: Hybrid Approach
- **Analysis Video**: Save with overlays (current behavior)
- **Base Video**: Also save clean copy (optional)
- **Overlay Metadata**: Save visualization data
- **Playback**: Can use either analyzed video OR base + overlays

**Pros:**
- Backward compatible
- Users can choose
- Gradual migration

**Cons:**
- Larger storage (two videos)
- More disk space needed

### Option C: Metadata-Only (Lightweight)
- **No Video**: Skip video encoding entirely during analysis
- **Overlay Metadata**: Save all visualization data
- **Playback**: Always render from base video + metadata
- **Export**: Generate video with overlays on-demand

**Pros:**
- Fastest analysis
- Smallest storage
- Most flexible

**Cons:**
- No pre-rendered video
- Must render overlays for playback

## Recommended Implementation: Option A (Full Overlay System)

### Phase 1: Overlay Metadata Export
1. During analysis, collect all visualization data per frame
2. Save overlay metadata to JSON alongside CSV
3. Keep current video encoding (backward compatible)

### Phase 2: Base Video Option
1. Add checkbox: "Save base video (no overlays)"
2. If checked, save clean video + overlay metadata
3. If unchecked, save analyzed video (current behavior)

### Phase 3: Enhanced Playback Viewer
1. Load base video + overlay metadata
2. Render overlays on-the-fly with toggles
3. Support real-time style changes

### Phase 4: Video Export with Overlays
1. Add "Export Video with Overlays" button
2. Render overlays onto base video on-demand
3. Allow customization before export

## Overlay Components to Separate

1. **Player Visualizations:**
   - Bounding boxes
   - Circles/ellipses
   - Labels (name, ID, jersey number)
   - Colors (team, custom, track-based)

2. **Ball Visualizations:**
   - Ball circle
   - Ball trail
   - Ball label

3. **Analytics Overlays:**
   - Speed, distance, etc. (already in CSV)
   - Text overlays below labels

4. **Other Visualizations:**
   - Field lines (if drawn)
   - Trajectory lines
   - Heat maps

## File Structure

```
video_analysis_output/
├── base_video.mp4              # Clean video (no overlays)
├── tracking_data.csv           # Tracking data (already exists)
├── overlay_metadata.json       # All visualization data
├── analytics_data.csv          # Analytics (already exists)
└── [optional] analyzed_video.mp4  # With overlays (if user wants)
```

## User Experience

### During Analysis:
- Checkbox: "Save base video (no overlays)" → Faster, smaller
- Checkbox: "Save analyzed video (with overlays)" → Current behavior
- Both can be enabled

### During Playback:
- Load base video + overlay metadata
- Toggle overlays on/off in real-time
- Change visualization styles instantly
- Export video with custom overlays

### Benefits for Users:
- **Faster Analysis**: Skip video encoding if not needed
- **Smaller Files**: Base video is much smaller
- **Flexibility**: Change styles without re-analyzing
- **Customization**: Adjust overlays after analysis
- **Export Options**: Generate videos with different styles

## Technical Considerations

### Performance:
- Overlay rendering is fast (already done in playback viewer)
- JSON metadata is small compared to video
- Can cache rendered frames if needed

### Compatibility:
- Keep current behavior as default (backward compatible)
- Add overlay system as optional enhancement
- Gradual migration path

### Storage:
- Base video: ~same size as original
- Overlay metadata: ~few MB (JSON)
- Total: Much smaller than analyzed video

## Questions to Consider

1. **Default Behavior**: Should we default to base video + overlays, or keep current?
2. **Video Encoding**: Should we make it optional, or always save base video?
3. **Metadata Format**: JSON vs. separate CSV files for overlays?
4. **Playback Performance**: Is on-the-fly rendering fast enough?
5. **Export Options**: Should we support multiple export formats?

## Recommendation

**Start with Option B (Hybrid)** for backward compatibility, then migrate to **Option A (Full Overlay)**:
1. Add overlay metadata export (Phase 1)
2. Add base video option (Phase 2)
3. Enhance playback viewer (Phase 3)
4. Add export functionality (Phase 4)

This gives users flexibility while maintaining compatibility with existing workflows.

