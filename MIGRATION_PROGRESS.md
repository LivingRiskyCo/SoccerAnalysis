# Refactoring Migration Progress

## Phase 1: Setup ✅ COMPLETE

- Created new directory structure:
  - `soccer_analysis/` - New refactored codebase
  - `legacy/` - Original large files preserved
  - `config/` - Configuration files
  - `tests/` - Unit tests directory

- Files moved to legacy:
  - `soccer_analysis_gui.py` (11,800+ lines)
  - `combined_analysis_optimized.py` (large)
  - `playback_viewer.py` (9,135+ lines)
  - `setup_wizard.py` (large)

## Phase 2: Extract Utilities & Models ✅ COMPLETE

### Utilities (`soccer_analysis/utils/`)
- ✅ `logger_config.py` - Centralized logging system
- ✅ `json_utils.py` - Safe JSON operations with corruption protection
- ✅ `__init__.py` - Module exports

### Models (`soccer_analysis/models/`)
- ✅ `player_gallery.py` - Player profile management
- ✅ `__init__.py` - Module exports

### Events (`soccer_analysis/events/`)
- ✅ `detector.py` - Event detection from CSV
- ✅ `marker_system.py` - Manual event marking
- ✅ `__init__.py` - Module exports

**Note:** Files are in `soccer_analysis/soccer_analysis/` structure. This will be flattened later.

## Phase 3: Extract GUI Components 🔄 IN PROGRESS

### Completed:
- ✅ `gui/tabs/gallery_tab.py` - Player gallery tab component
  - Extracted from `legacy/soccer_analysis_gui.py` (lines 5751-5945)
  - Uses delegation pattern to call parent GUI methods
  - Handles player list display, statistics, and actions

- ✅ `gui/tabs/roster_tab.py` - Team roster management tab
  - Extracted from `legacy/soccer_analysis_gui.py` (lines 5947-6444)
  - Manages team roster, player import/export, video linking
  - Includes player add/edit/delete functionality

- ✅ `gui/tabs/event_detection_tab.py` - Event detection tab
  - Extracted from `legacy/soccer_analysis_gui.py` (lines 11096-11409)
  - Handles automated event detection (passes, shots, goals)
  - Includes goal area designation and manual marker integration

- ✅ `gui/tabs/analysis_tab.py` - Analysis configuration tab
  - Extracted from `legacy/soccer_analysis_gui.py` (lines 450-564)
  - Ball tracking settings, YOLO detection, gallery matching, processing options
  - Uses delegation pattern for parent GUI methods

- ✅ `gui/tabs/visualization_tab.py` - Visualization settings tab
  - Extracted from `legacy/soccer_analysis_gui.py` (lines 1200-1857)
  - Visualization style, colors, labels, motion visualization, track ID decay
  - Uses delegation pattern for parent GUI methods

- ✅ `gui/tabs/tracking_tab.py` - Tracking stability settings tab
  - Extracted from `legacy/soccer_analysis_gui.py` (lines 1857-2242)
  - Tracking thresholds, Re-ID settings, advanced features, occlusion handling
  - Uses delegation pattern for parent GUI methods

- ✅ `gui/tabs/advanced_tab.py` - Advanced settings tab
  - Extracted from `legacy/soccer_analysis_gui.py` (lines 727-868)
  - Watch-only mode, overlay system, video game quality graphics
  - Uses delegation pattern for parent GUI methods

- ✅ `gui/viewers/playback_viewer.py` - Video playback viewer
  - Moved from root directory
  - Updated imports to use new structure (events.marker_system)
  - Handles video playback with toggleable overlays

- ✅ `gui/viewers/setup_wizard.py` - Interactive setup wizard
  - Moved from root directory
  - Updated imports to use new structure (events.marker_system, models.player_gallery)
  - Frame-by-frame player tagging and ball verification

- ✅ `gui/viewers/__init__.py` - Viewer module exports

- ✅ `gui/dialogs/__init__.py` - Dialog module documentation
  - Documents standalone dialog files (analytics_selection_gui, setup_checklist, etc.)
  - These remain as standalone files for now

- ✅ `gui/main_window.py` - Main GUI orchestrator
  - Integrates all extracted tab components
  - Creates scrollable tab frames
  - Right panel with action buttons
  - Progress bar, status label, log output
  - Updated to use new viewer imports

## Phase 4: Extract Analysis Engine 🔄 IN PROGRESS

Break down `combined_analysis_optimized.py` into:
- ✅ `analysis/core/` - Video processing, detection, tracking
  - ✅ `video_processor.py` - Video I/O and frame reading
  - ✅ `detector.py` - YOLO detection and ball detection (with legacy fallback)
  - ✅ `tracker.py` - Multi-object tracking
  - ✅ `utils.py` - **COMPLETE** - Unit conversions, field calibration, coordinate transforms, possession calculation
    - ✅ `meters_to_feet()`, `mps_to_mph()`, `mps2_to_fts2()` - Unit conversions
    - ✅ `draw_direction_arrow()` - Drawing utilities
    - ✅ `load_field_calibration()` - Load field calibration from JSON
    - ✅ `load_ball_color_config()` - Load ball color configuration
    - ✅ `is_point_in_field()` - Check if point is within field boundaries
    - ✅ `transform_point_to_field()` - Transform image to field coordinates
    - ✅ `transform_field_to_point()` - Transform field to image coordinates
    - ✅ `calculate_possession()` - Calculate ball possession
  - ✅ `detector.py` - YOLO detection and ball detection
  - ✅ `tracker.py` - Multi-object tracking
  - ✅ `utils.py` - Unit conversions and drawing functions
  - ✅ `analyzer.py` - Main orchestrator (delegates to legacy for now)
- ✅ `analysis/reid/` - Re-ID management
  - ✅ `reid_manager.py` - Re-ID tracker and gallery matching
- ✅ `analysis/postprocessing/` - Smoothing, drift control
  - ✅ `smoothing.py` - GSI, Kalman, EMA smoothing
  - ✅ `drift_control.py` - Track drift prevention
- ✅ `analysis/output/` - CSV and metadata export
  - ✅ `csv_exporter.py` - CSV export with unit conversion
  - ✅ `metadata_exporter.py` - Overlay metadata export

**Note:** Modules are created with basic structure. Full implementation will be completed incrementally.
The main analyzer currently delegates to legacy implementation for compatibility.

## Current File Structure

```
soccer_analysis/
├── __init__.py
├── main.py
├── gui/
│   ├── tabs/
│   │   ├── __init__.py
│   │   ├── gallery_tab.py ✅
│   │   ├── roster_tab.py ✅
│   │   ├── event_detection_tab.py ✅
│   │   ├── analysis_tab.py ✅
│   │   ├── visualization_tab.py ✅
│   │   ├── tracking_tab.py ✅
│   │   └── advanced_tab.py ✅
│   ├── viewers/
│   │   ├── __init__.py ✅
│   │   ├── playback_viewer.py ✅
│   │   └── setup_wizard.py ✅
│   ├── dialogs/
│   │   └── __init__.py ✅
│   └── main_window.py ✅
├── analysis/
│   ├── __init__.py ✅
│   ├── core/
│   │   ├── __init__.py ✅
│   │   ├── analyzer.py ✅
│   │   ├── video_processor.py ✅
│   │   ├── detector.py ✅
│   │   ├── tracker.py ✅
│   │   └── utils.py ✅
│   ├── reid/
│   │   ├── __init__.py ✅
│   │   └── reid_manager.py ✅
│   ├── postprocessing/
│   │   ├── __init__.py ✅
│   │   ├── smoothing.py ✅
│   │   └── drift_control.py ✅
│   └── output/
│       ├── __init__.py ✅
│       ├── csv_exporter.py ✅
│       └── metadata_exporter.py ✅
│   ├── dialogs/       (to be populated)
│   ├── widgets/       (to be populated)
│   └── viewers/       (to be populated)
├── analysis/
│   ├── core/          (to be populated)
│   ├── reid/          (to be populated)
│   ├── postprocessing/ (to be populated)
│   └── output/        (to be populated)
├── events/
│   ├── detector.py    ✅
│   ├── marker_system.py ✅
│   └── analytics/      (to be populated)
├── utils/
│   ├── logger_config.py ✅
│   └── json_utils.py   ✅
└── models/
    └── player_gallery.py ✅

legacy/
├── soccer_analysis_gui.py
├── combined_analysis_optimized.py
├── playback_viewer.py
└── setup_wizard.py
```

## Import Strategy

All new modules use relative imports with fallback to legacy imports:
```python
try:
    from ..utils.logger_config import get_logger
except ImportError:
    from logger_config import get_logger  # Fallback
```

This allows gradual migration without breaking existing code.

## Design Patterns Used

### Delegation Pattern (Gallery Tab)
The `GalleryTab` class uses delegation to call methods on the parent GUI:
```python
def _call_parent_method(self, method_name, *args, **kwargs):
    if hasattr(self.parent_gui, method_name):
        method = getattr(self.parent_gui, method_name)
        return method(*args, **kwargs)
```

This allows tabs to be extracted without immediately refactoring all dependencies.

## Next Actions

1. ✅ Extract Gallery Tab
2. ✅ Extract Roster Tab
3. ✅ Extract Event Detection Tab
4. ✅ Extract Analysis Tab
5. ✅ Extract Visualization Tab
6. ✅ Extract Tracking Tab
7. ✅ Extract Advanced Tab
6. Create main_window.py orchestrator
7. Extract viewer classes (playback_viewer, setup_wizard)
8. Flatten nested structure
9. Update entry point
