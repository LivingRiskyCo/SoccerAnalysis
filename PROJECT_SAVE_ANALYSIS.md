# Project Save Analysis: What GUI Settings Are Saved?

## Current Status: **NO - Only a small subset of GUI settings are saved**

## What IS Currently Saved (Lines 84-101 in project_manager.py):

### Basic Settings:
- ✅ `input_file` - Input video path
- ✅ `output_file` - Output video path
- ✅ `dewarp_enabled` - Dewarp toggle
- ✅ `remove_net_enabled` - Remove net toggle
- ✅ `ball_tracking_enabled` - Ball tracking toggle
- ✅ `player_tracking_enabled` - Player tracking toggle
- ✅ `csv_export_enabled` - CSV export toggle
- ✅ `buffer_size` - Buffer size
- ✅ `batch_size` - Batch size
- ✅ `show_ball_trail` - Show ball trail toggle

### Tracking Settings:
- ✅ `track_thresh` - YOLO detection threshold
- ✅ `match_thresh` - Matching threshold
- ✅ `track_buffer` - ByteTrack buffer frames (legacy)
- ✅ `tracker_type` - Tracker type ("bytetrack" or "ocsort")

### Visualization Settings:
- ✅ `viz_style` - Visualization style ("box", "circle", etc.)
- ✅ `viz_color_mode` - Color mode ("team", "single", "gradient")

## What is NOT Saved (Missing from project save):

### Watch-Only & Learning:
- ❌ `watch_only` - Watch-only mode
- ❌ `show_live_viewer` - Show live viewer
- ❌ `focus_players_enabled` - Focus players mode
- ❌ `focused_players` - List of focused players

### Ball Tracking:
- ❌ `ball_min_radius` - Minimum ball radius
- ❌ `ball_max_radius` - Maximum ball radius
- ❌ `trail_length` - Trail length
- ❌ `trail_buffer` - Trail buffer size

### Advanced Tracking:
- ❌ `track_buffer_seconds` - Buffer time in seconds (NEW, better than track_buffer)
- ❌ `min_track_length` - Minimum track length
- ❌ `video_fps` - Video FPS override
- ❌ `output_fps` - Output FPS override
- ❌ `temporal_smoothing` - Temporal smoothing
- ❌ `process_every_nth` - Process every Nth frame
- ❌ `yolo_resolution` - YOLO processing resolution
- ❌ `foot_based_tracking` - Foot-based tracking
- ❌ `use_reid` - Re-ID enabled
- ❌ `reid_similarity_threshold` - Re-ID similarity threshold

### Advanced Tracking Features (Academic Research):
- ❌ `use_harmonic_mean` - Harmonic Mean association
- ❌ `use_expansion_iou` - Expansion IOU
- ❌ `enable_soccer_reid_training` - Soccer-specific Re-ID training
- ❌ `use_enhanced_kalman` - Enhanced Kalman filtering
- ❌ `use_ema_smoothing` - EMA smoothing
- ❌ `confidence_filtering` - Confidence-based filtering
- ❌ `adaptive_confidence` - Adaptive confidence threshold

### Advanced Tracking Options:
- ❌ `track_referees` - Track referees
- ❌ `max_players` - Maximum field players
- ❌ `enable_substitutions` - Substitution handling

### Visualization Settings (Most Missing):
- ❌ `viz_team_colors` - Use team colors
- ❌ `ellipse_width` - Ellipse width
- ❌ `ellipse_height` - Ellipse height
- ❌ `ellipse_outline_thickness` - Ellipse border thickness
- ❌ `show_ball_possession` - Show ball possession triangle
- ❌ `box_shrink_factor` - Box shrink factor
- ❌ `box_thickness` - Box border thickness
- ❌ `use_custom_box_color` - Use custom box color
- ❌ `box_color_r`, `box_color_g`, `box_color_b` - Custom box color RGB
- ❌ `player_viz_alpha` - Player visualization opacity

### Label Settings:
- ❌ `show_player_labels` - Show player labels
- ❌ `label_font_scale` - Label font size
- ❌ `label_type` - Label type ("full_name", "last_name", "jersey", "team", "custom")
- ❌ `label_custom_text` - Custom label text
- ❌ `label_font_face` - Label font face

### Prediction Settings:
- ❌ `show_predicted_boxes` - Show predicted boxes
- ❌ `prediction_duration` - Prediction duration
- ❌ `prediction_size` - Prediction size
- ❌ `prediction_color_r`, `prediction_color_g`, `prediction_color_b` - Prediction color RGB
- ❌ `prediction_color_alpha` - Prediction color opacity
- ❌ `prediction_style` - Prediction style ("dot", "box", "cross", etc.)

### Other:
- ❌ `preserve_audio` - Preserve audio from original video

## Summary

**Currently saved: 16 settings**  
**Missing: ~50+ settings**

This means when you load a project, most of your GUI settings are NOT restored - only the basic analysis settings are restored.

## Recommendation

The project save/load should be expanded to save ALL GUI settings so that projects are truly portable and restore your complete configuration.

