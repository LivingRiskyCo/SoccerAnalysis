# Re-ID (Re-identification) Installation Guide

## What is Re-ID?

Re-ID (Re-identification) uses deep learning to create feature embeddings from player bounding boxes. These features help match players even after occlusions or temporary detection loss, significantly improving ID persistence.

## Benefits

- **Better ID Persistence**: Players maintain their IDs even during occlusions
- **Reduced ID Switching**: Fewer false ID changes when players cross paths
- **Recovery After Loss**: Can recover player IDs after temporary detection loss
- **Works with ByteTrack**: Complements ByteTrack's position-based tracking with feature-based matching

## Installation

### Option 1: Full Re-ID (Recommended - Best Performance)

Install torchreid for the best Re-ID model (OSNet):

```bash
pip install torchreid
```

This will automatically install PyTorch if not already installed.

### Option 2: Simple Re-ID (Fallback - Works Without torchreid)

If torchreid is not available, the system will automatically use a simple CNN feature extractor. You still need PyTorch:

```bash
pip install torch
```

## Usage

Re-ID is **enabled by default** in the GUI. You can:

1. **Enable/Disable**: Check/uncheck "Re-ID (Re-identification)" in the tracking settings
2. **Adjust Threshold**: Set "Re-ID Similarity Threshold" (0.3-0.9, default: 0.5)
   - Higher = stricter matching (fewer false matches, but may miss some correct matches)
   - Lower = more lenient matching (more matches, but may have some false positives)

## How It Works

1. **Feature Extraction**: For each player detection, extract a 128-dimensional feature vector
2. **Feature Storage**: Store features for each track ID (up to 50 recent features per track)
3. **Matching**: When a detection loses its ID, match it to existing tracks using cosine similarity
4. **ID Recovery**: Reassign the matched track ID to the detection

## Performance Impact

- **With torchreid**: ~5-10% slower, but best accuracy
- **With simple CNN**: ~2-5% slower, good accuracy
- **Memory**: ~100-200MB additional RAM for feature storage

## Troubleshooting

### "Re-ID tracker not available"

**Solution**: Install PyTorch:
```bash
pip install torch
```

### "Could not load torchreid model"

**Solution**: This is OK - the system will use the simple CNN fallback. For better performance, install torchreid:
```bash
pip install torchreid
```

### Re-ID not helping with ID persistence

**Try**:
1. Lower the similarity threshold (e.g., 0.4 instead of 0.5)
2. Ensure you have enough frames processed (Re-ID needs history to work)
3. Check that detections are consistent (low confidence detections may not match well)

## Technical Details

- **Feature Dimension**: 128 (configurable)
- **Max Features per Track**: 50 (configurable)
- **Similarity Metric**: Cosine similarity
- **Matching Algorithm**: Greedy matching (fast, works well for most cases)

## Future Improvements

- Hungarian algorithm for optimal matching (more accurate but slower)
- Adaptive similarity threshold based on detection confidence
- Integration with team color features for better matching

