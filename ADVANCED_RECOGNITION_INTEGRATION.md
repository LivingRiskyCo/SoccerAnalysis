# Advanced Player Recognition Integration Guide

This document describes the integration of four new advanced recognition modules:

1. **Jersey Number OCR** - Automatic jersey number detection
2. **Gait Analysis** - Movement signature analysis
3. **Hard Negative Mining** - Improved discrimination learning
4. **Graph-Based Tracking** - Hierarchical graph structures for long-term consistency

## Module Files Created

- `jersey_number_ocr.py` - OCR-based jersey number detection
- `gait_analyzer.py` - Gait pattern analysis from pose keypoints
- `hard_negative_mining.py` - Hard negative example mining
- `graph_tracker.py` - Graph-based hierarchical tracking

## Integration Steps

### 1. Import Modules in `combined_analysis_optimized.py`

Add these imports near the top (around line 36):

```python
try:
    from jersey_number_ocr import JerseyNumberOCR
    JERSEY_OCR_AVAILABLE = True
except ImportError:
    JERSEY_OCR_AVAILABLE = False
    print("⚠ Jersey Number OCR not available")

try:
    from gait_analyzer import GaitAnalyzer
    GAIT_ANALYZER_AVAILABLE = True
except ImportError:
    GAIT_ANALYZER_AVAILABLE = False
    print("⚠ Gait Analyzer not available")

try:
    from hard_negative_mining import HardNegativeMiner
    HARD_NEGATIVE_AVAILABLE = True
except ImportError:
    HARD_NEGATIVE_AVAILABLE = False
    print("⚠ Hard Negative Mining not available")

try:
    from graph_tracker import GraphTracker
    GRAPH_TRACKER_AVAILABLE = True
except ImportError:
    GRAPH_TRACKER_AVAILABLE = False
    print("⚠ Graph Tracker not available")
```

### 2. Initialize Modules (after Re-ID tracker initialization, ~line 5001)

```python
# Initialize advanced recognition modules
jersey_ocr = None
if JERSEY_OCR_AVAILABLE and use_reid:
    try:
        jersey_ocr = JerseyNumberOCR(ocr_backend="auto", confidence_threshold=0.5)
        print("✓ Jersey Number OCR initialized")
    except Exception as e:
        print(f"⚠ Could not initialize Jersey OCR: {e}")
        jersey_ocr = None

gait_analyzer = None
if GAIT_ANALYZER_AVAILABLE and use_reid and foot_based_tracking:
    try:
        gait_analyzer = GaitAnalyzer(history_length=30, min_samples_for_gait=10)
        print("✓ Gait Analyzer initialized")
    except Exception as e:
        print(f"⚠ Could not initialize Gait Analyzer: {e}")
        gait_analyzer = None

hard_negative_miner = None
if HARD_NEGATIVE_AVAILABLE and use_reid and player_gallery is not None:
    try:
        hard_negative_miner = HardNegativeMiner(
            max_hard_negatives=50,
            similarity_threshold=0.4,
            max_similarity=0.7
        )
        print("✓ Hard Negative Miner initialized")
    except Exception as e:
        print(f"⚠ Could not initialize Hard Negative Miner: {e}")
        hard_negative_miner = None

graph_tracker = None
if GRAPH_TRACKER_AVAILABLE and use_reid:
    try:
        graph_tracker = GraphTracker(
            position_grid_size=(10, 10),
            max_nodes_per_type=1000,
            edge_decay_rate=0.95
        )
        print("✓ Graph Tracker initialized")
    except Exception as e:
        print(f"⚠ Could not initialize Graph Tracker: {e}")
        graph_tracker = None
```

### 3. Jersey Number Detection (in frame processing loop)

Add jersey number detection when processing detections:

```python
# Detect jersey numbers for all detections
jersey_numbers = {}
if jersey_ocr is not None and len(detections) > 0:
    for i, (x1, y1, x2, y2) in enumerate(detections.xyxy):
        bbox = [float(x1), float(y1), float(x2), float(y2)]
        result = jersey_ocr.detect_jersey_number(frame, bbox)
        if result and result['confidence'] >= 0.5:
            track_id = detections.tracker_id[i] if i < len(detections.tracker_id) else None
            if track_id is not None:
                jersey_numbers[track_id] = result['number']
```

### 4. Gait Analysis (in frame processing loop)

Update gait analyzer with pose keypoints:

```python
# Update gait analyzer with pose keypoints
if gait_analyzer is not None and pose_model is not None:
    # Extract pose keypoints (if available from pose model)
    # This depends on your pose model output format
    for i, track_id in enumerate(detections.tracker_id):
        if track_id is not None:
            # Get keypoints for this detection (if available)
            # keypoints = pose_keypoints[i]  # Format: (17, 3) - (x, y, confidence)
            # position = (center_x, center_y)
            # velocity = velocity_magnitude
            
            # gait_analyzer.update_track(
            #     track_id=track_id,
            #     keypoints=keypoints,
            #     position=position,
            #     velocity=velocity,
            #     frame_num=current_frame_num
            # )
            pass
```

### 5. Hard Negative Mining (in player matching section)

Add hard negative mining when matching players:

```python
# Mine hard negatives during player matching
if hard_negative_miner is not None and player_gallery is not None:
    # When matching a player, collect candidates that are similar but wrong
    for player_id, player_profile in player_gallery.players.items():
        if player_profile.features is not None:
            # Get candidates that are similar but not the same player
            candidates = []
            for track_id, track_features in track_features_dict.items():
                similarity = cosine_similarity(player_profile.features, track_features)
                if 0.4 <= similarity <= 0.7:  # Hard negative range
                    candidates.append((track_features, track_id, similarity, 0.5))
            
            # Mine negatives
            hard_negative_miner.batch_mine_negatives(
                player_id=player_id,
                player_feature=np.array(player_profile.features),
                candidates=candidates,
                frame_num=current_frame_num,
                jersey_numbers=jersey_numbers
            )
```

### 6. Graph-Based Tracking (in frame processing loop)

Update graph tracker with player information:

```python
# Update graph tracker
if graph_tracker is not None:
    for i, track_id in enumerate(detections.tracker_id):
        if track_id is not None:
            # Get player information
            player_id = track_id_to_player_id.get(track_id)
            jersey_number = jersey_numbers.get(track_id)
            team = track_id_to_team.get(track_id)
            position = (center_x, center_y)
            features = track_features[i]
            
            # Create/update player node
            node_id = graph_tracker.create_or_update_player_node(
                track_id=track_id,
                features=features,
                player_id=player_id,
                jersey_number=jersey_number,
                team=team,
                position=position,
                field_size=(width, height),
                confidence=detections.confidence[i] if i < len(detections.confidence) else 0.5,
                frame_num=current_frame_num
            )
    
    # Use graph for matching
    if player_id is None:  # Unknown player, try to match
        matches = graph_tracker.find_matching_players(
            features=features,
            jersey_number=jersey_number,
            team=team,
            position=position,
            field_size=(width, height),
            similarity_threshold=0.5
        )
        if matches:
            best_match_node_id, similarity = matches[0]
            matched_node = graph_tracker.nodes[best_match_node_id]
            if matched_node.player_id:
                player_id = matched_node.player_id
```

### 7. Cleanup (periodic maintenance)

Add periodic cleanup:

```python
# Periodic cleanup (every 100 frames)
if current_frame_num % 100 == 0:
    # Decay graph edges
    if graph_tracker is not None:
        graph_tracker.decay_edges(current_frame_num)
        graph_tracker.clear_old_nodes(current_frame_num, max_age_frames=300)
    
    # Clear old gait history
    if gait_analyzer is not None:
        # Gait analyzer uses deque with maxlen, so automatic cleanup
        pass
    
    # Clear old hard negatives (optional)
    # if hard_negative_miner is not None:
    #     # Hard negatives are automatically limited by max_hard_negatives
    #     pass
```

## Usage in Player Matching

### Enhanced Matching with All Features

```python
def enhanced_player_matching(track_features, track_id, jersey_ocr, gait_analyzer, 
                            hard_negative_miner, graph_tracker, player_gallery):
    """Enhanced player matching using all available features"""
    
    matches = []
    
    # 1. Get jersey number (if available)
    jersey_number = None
    if jersey_ocr:
        # Detect jersey number
        pass
    
    # 2. Get gait signature (if available)
    gait_signature = None
    if gait_analyzer:
        gait_signature = gait_analyzer.get_gait_signature(track_id)
    
    # 3. Match using graph tracker (if available)
    if graph_tracker:
        graph_matches = graph_tracker.find_matching_players(
            features=track_features,
            jersey_number=jersey_number,
            similarity_threshold=0.5
        )
        matches.extend(graph_matches)
    
    # 4. Match using player gallery
    if player_gallery:
        for player_id, profile in player_gallery.players.items():
            if profile.features is not None:
                # Base similarity
                similarity = cosine_similarity(track_features, profile.features)
                
                # Adjust with hard negatives
                if hard_negative_miner:
                    similarity = hard_negative_miner.adjust_similarity_with_negatives(
                        track_features, profile.features, player_id, similarity
                    )
                
                # Boost if jersey matches
                if jersey_number and profile.jersey_number == jersey_number:
                    similarity += 0.1
                
                # Boost if gait matches (if available)
                if gait_signature is not None and profile.gait_signature is not None:
                    gait_sim = cosine_similarity(gait_signature, profile.gait_signature)
                    similarity += 0.05 * gait_sim
                
                matches.append((player_id, similarity))
    
    # Sort by similarity
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches
```

## Dependencies

### Jersey Number OCR
- `easyocr` (recommended): `pip install easyocr`
- `paddleocr` (alternative): `pip install paddlepaddle paddleocr`
- `pytesseract` (fallback): `pip install pytesseract` (requires Tesseract OCR installed)

### Gait Analyzer
- Requires pose keypoints from YOLO pose model (already available)
- No additional dependencies

### Hard Negative Mining
- No additional dependencies (uses numpy)

### Graph Tracker
- No additional dependencies (uses standard library)

## Performance Considerations

1. **Jersey OCR**: Can be slow on CPU. Consider running on GPU or processing every Nth frame.
2. **Gait Analysis**: Lightweight, minimal performance impact.
3. **Hard Negative Mining**: Very lightweight, minimal impact.
4. **Graph Tracker**: Moderate overhead, but improves long-term consistency.

## Testing

Test each module individually before full integration:

```python
# Test Jersey OCR
from jersey_number_ocr import JerseyNumberOCR
ocr = JerseyNumberOCR()
result = ocr.detect_jersey_number(frame, bbox)
print(f"Detected: {result}")

# Test Gait Analyzer
from gait_analyzer import GaitAnalyzer
gait = GaitAnalyzer()
gait.update_track(track_id, keypoints, position, velocity, frame_num)
features = gait.extract_gait_features(track_id)
print(f"Gait features: {features}")

# Test Hard Negative Mining
from hard_negative_mining import HardNegativeMiner
miner = HardNegativeMiner()
miner.mine_negative(player_id, player_feat, candidate_feat, track_id, similarity)
negatives = miner.get_hard_negatives(player_id)
print(f"Hard negatives: {len(negatives)}")

# Test Graph Tracker
from graph_tracker import GraphTracker
graph = GraphTracker()
node_id = graph.create_or_update_player_node(track_id, features, jersey_number="5", team="Team1")
matches = graph.find_matching_players(features, jersey_number="5")
print(f"Graph matches: {matches}")
```

## Next Steps

1. Integrate imports and initialization
2. Add jersey number detection in frame loop
3. Add gait analysis updates
4. Add hard negative mining during matching
5. Add graph tracker updates
6. Test with sample videos
7. Tune parameters based on results

