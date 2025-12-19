# Phase 4: Extraction Plan for combined_analysis_optimized.py

## Overview
This document outlines the plan to extract functionality from `legacy/combined_analysis_optimized.py` (23,000+ lines) into modular components.

## Module Extraction Status

### ✅ Completed
1. **utils.py** - Unit conversions, field calibration, coordinate transforms, possession calculation
2. **video_processor.py** - Basic video I/O structure
3. **detector.py** - Basic YOLO detection structure
4. **tracker.py** - Basic tracking structure

### 🔄 In Progress
1. **detector.py** - Ball detection extraction (`track_ball_in_frame` function)
2. **csv_exporter.py** - CSV export logic
3. **metadata_exporter.py** - Metadata export logic

### ⏳ Pending
1. **smoothing.py** - GSI, Kalman, EMA smoothing
2. **drift_control.py** - Drift control logic
3. **reid_manager.py** - Re-ID integration
4. **analyzer.py** - Main orchestrator

## Key Functions to Extract

### From legacy/combined_analysis_optimized.py:

1. **Ball Detection** (lines ~3608-4444)
   - `track_ball_in_frame()` - Main ball tracking function
   - Uses HSV color detection, field calibration, seed positions

2. **CSV Export** (lines ~19730-20030)
   - CSV writing logic with unit conversions
   - Player analytics export
   - Ball tracking data export

3. **Metadata Export** (lines ~22618-22710)
   - Overlay metadata saving
   - Pickle/JSON serialization

4. **Smoothing Functions**
   - GSI smoothing (from `gsi_smoothing.py`)
   - Kalman filtering
   - EMA smoothing

5. **Re-ID Integration**
   - Re-ID tracker initialization
   - Gallery matching
   - Identity assignment

6. **Main Analyzer**
   - Frame processing loop
   - Module orchestration
   - Progress tracking

## Migration Strategy

1. **Incremental Extraction**: Extract functions one module at a time
2. **Legacy Fallback**: Import from legacy during transition
3. **Testing**: Verify each module works before moving to next
4. **Documentation**: Update imports and usage as modules are extracted

## Next Steps

1. Extract `track_ball_in_frame` to `detector.py`
2. Extract CSV export logic to `csv_exporter.py`
3. Extract metadata export to `metadata_exporter.py`
4. Extract smoothing functions to `smoothing.py`
5. Extract Re-ID logic to `reid_manager.py`
6. Create main `analyzer.py` orchestrator

