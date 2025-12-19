<!-- a9315ea8-d461-4d8a-a285-e2126620dcaf 1c07e2b9-ef0c-4747-99ca-48e27992b6f9 -->
# Filter Gallery Matching to Exclude Anchor Players

## Problem

Currently, the system filters gallery matching to ONLY include players in anchor frames. However, the user wants:

- **Anchor-protected players**: Skip Re-ID matching entirely (already identified with 1.00 confidence)
- **Non-anchor players**: Match against ALL players in gallery EXCEPT anchor players
- This allows identification of untagged players while preventing conflicts with anchor-assigned players

## Solution

Modify the filtering logic to:

1. Create a set of anchor player names (players with anchor frames)
2. For detections that are NOT anchor-protected: Match against all gallery players EXCEPT anchor players
3. For detections that ARE anchor-protected: Skip gallery matching entirely (already identified)
4. Honor all anchor protection rules (1.00 confidence, protection windows, etc.)

## Implementation

### 1. Update `load_anchor_frames` to return anchor player names set

**File**: `combined_analysis_optimized.py` (lines ~4350-4847)

- Already returns `players_in_anchor_frames_set` - this is correct
- This set contains names of players with anchor frames

### 2. Modify gallery matching filter logic

**File**: `player_gallery.py` (lines ~2635-2642)

**Current logic**:

```python
if filter_players is not None and profile.name not in filter_players:
    # Skip players not in anchor frames
    continue
```

**New logic**:

```python
# FILTER: Exclude anchor players from matching
# If filter_players is provided, it contains anchor player names
# We want to EXCLUDE these players (they're already identified)
if filter_players is not None and profile.name in filter_players:
    # Player is anchor-protected - skip this match
    # Anchor players are already identified and shouldn't be matched via Re-ID
    all_similarities.append((player_id, profile.name, 0.0))
    continue
```

**Change**: Invert the filter - exclude anchor players instead of including only anchor players.

### 3. Update `match_against_gallery` parameter name/documentation

**File**: `reid_tracker.py` (lines ~1464-1560)

- Update parameter name from `filter_players` to `exclude_players` for clarity
- Update documentation to reflect exclusion behavior
- Pass through to `match_player` with same name

### 4. Ensure anchor-protected tracks skip gallery matching

**File**: `combined_analysis_optimized.py` (lines ~11258-11284, ~11509-11520)

**Current logic**: Already checks for anchor protection before gallery matching

- Verify that tracks with confidence >= 1.00 skip gallery matching entirely
- This is already implemented - just verify it's working correctly

### 5. Update all call sites

**File**: `combined_analysis_optimized.py`

**Location 1**: Main gallery matching (line ~10285)

```python
gallery_matches = reid_tracker.match_against_gallery(
    ...
    exclude_players=players_in_anchor_frames_set  # EXCLUDE anchor players from matching
)
```

**Location 2**: Alternative matching path 1 (line ~10461)

```python
all_candidate_matches = player_gallery.match_player(
    ...
    exclude_players=players_in_anchor_frames_set  # EXCLUDE anchor players
)
```

**Location 3**: Alternative matching path 2 (line ~10479)

```python
all_candidate_matches = player_gallery.match_player(
    ...
    exclude_players=players_in_anchor_frames_set  # EXCLUDE anchor players
)
```

### 6. Update function signatures and documentation

**Files**:

- `player_gallery.py`: Update `match_player` parameter from `filter_players` to `exclude_players`
- `reid_tracker.py`: Update `match_against_gallery` parameter from `filter_players` to `exclude_players`
- Update docstrings to clarify exclusion behavior

## Expected Behavior

**Before**:

- Gallery matching only considered players in anchor frames
- Untagged players couldn't be identified via Re-ID

**After**:

- Anchor-protected players: Skip Re-ID matching (already identified)
- Non-anchor players: Match against all gallery players EXCEPT anchor players
- Untagged players can be identified via Re-ID
- No conflicts with anchor-assigned players
- **Anchor frames update gallery**: When anchor frames are applied, extract Re-ID features and update player gallery (high-quality data points for cross-video recognition)

## Additional Requirement: Anchor Frame Gallery Updates

**File**: `combined_analysis_optimized.py` (lines ~9742-9783)

**Current behavior**: Anchor frames already update the gallery with body and jersey features

**Enhancement needed**: Add foot feature extraction for anchor frames

1. **High priority**: Anchor frames are ground truth (1.00 confidence, 1.00 similarity) - already implemented
2. **Comprehensive**: Extract body, jersey, AND foot features from anchor frames - **foot_features missing**
3. **Automatic**: Update gallery whenever anchor frame is applied - already implemented
4. **Quality tracking**: Mark anchor frame features as high-quality reference frames - already implemented

**Change needed**: Add foot feature extraction in anchor frame gallery update (line ~9761)

```python
# Extract foot features (foot/shoe region)
foot_features_for_gallery = None
try:
    if hasattr(reid_tracker, 'extract_foot_features'):
        foot_feat = reid_tracker.extract_foot_features(frame_for_reid, single_detection)
        if foot_feat is not None and len(foot_feat) > 0:
            foot_features_for_gallery = foot_feat[0]
except Exception as e:
    if current_frame_num % 100 == 0:
        print(f"  ⚠ Could not extract foot features: {e}")
```

Then pass `foot_features=foot_features_for_gallery` to `player_gallery.update_player()` call (line ~9768)

**Why this matters**: Anchor frames are high-quality data points for cross-video recognition. Including foot features improves identification when jersey is occluded or players change uniforms.

## Testing

1. Run analysis with anchor frames for Rocco, Cameron, Ellie, James
2. Verify anchor-protected tracks skip gallery matching
3. Verify untagged detections match against non-anchor players (e.g., Kevin Hill, Guest Player)
4. Verify no matches to anchor players (Rocco, Cameron, Ellie, James) for untagged detections