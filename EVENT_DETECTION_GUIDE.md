# Event Detection Guide

Automated event detection system that works with your existing CSV tracking data. No need to re-process videos - just run analysis on your tracking CSV files!

## Features

- **Pass Detection**: Automatically detects passes between players using ball movement and player proximity
- **Shot Detection**: Identifies shots by analyzing ball trajectory toward goal
- **Zone Occupancy**: Calculates time spent in each field zone per player
- **Confidence Scores**: Every detection includes a confidence score (0.0-1.0) so you know when to trust it
- **Works with Imperfect Video**: Designed to be tolerant of tracking gaps and imperfect data

## Quick Start

### Basic Usage

```bash
# Test on your existing CSV file
python test_event_detection.py your_video_analyzed_tracking_data.csv
```

This will:
- Detect passes
- Detect shots
- Analyze zone occupancy
- Show top detections with confidence scores

### Adjusting Sensitivity

If you're not getting enough detections (or getting too many false positives):

```bash
# Lower confidence threshold for more detections
python test_event_detection.py your_video.csv --min-confidence 0.3

# Adjust pass detection parameters
python test_event_detection.py your_video.csv --min-ball-speed 2.0 --min-pass-distance 3.0

# Export results to CSV
python test_event_detection.py your_video.csv --export
```

## Understanding Confidence Scores

Every detected event has a confidence score from 0.0 to 1.0:

- **0.9-1.0**: Very reliable - high-quality detection
- **0.7-0.9**: Reliable - good detection
- **0.5-0.7**: Moderate - may need review
- **0.3-0.5**: Low - likely false positive or poor tracking
- **<0.3**: Very low - probably noise

**Tip**: Start with `--min-confidence 0.5` and adjust based on results.

## Parameters

### Pass Detection

- `--min-ball-speed`: Minimum ball speed during pass (m/s, default: 3.0)
  - Lower = more detections (but more false positives)
  - Higher = fewer detections (but more reliable)
  
- `--min-pass-distance`: Minimum pass length (meters, default: 5.0)
  - Lower = includes shorter passes
  - Higher = only long passes

- `--possession-threshold`: Ball possession distance (meters, default: 1.5)
  - How close ball must be to player to count as possession
  - Lower = stricter possession requirement

### Shot Detection

- Automatically detects shots when ball moves fast toward goal area
- Uses goal area: X=(0.4-0.6), Y=(0.0-0.1) normalized coordinates
- Adjustable via code if needed

### Zone Occupancy

- Divides field into three zones:
  - Defensive third: Y=(0.0-0.33)
  - Midfield: Y=(0.33-0.67)
  - Attacking third: Y=(0.67-1.0)
- Shows time spent in each zone per player

## Output

### Console Output

Shows:
- Number of events detected
- Top events by confidence
- Zone occupancy statistics
- Summary statistics

### CSV Export

Use `--export` to save events to CSV:

```bash
python test_event_detection.py your_video.csv --export
```

Creates: `your_video_detected_events.csv`

Columns:
- `event_type`: "pass", "shot", etc.
- `frame_num`: Frame number
- `timestamp`: Time in seconds
- `confidence`: Confidence score
- `player_id`, `player_name`, `team`: Player info
- `start_x`, `start_y`, `end_x`, `end_y`: Event positions
- `metadata`: Additional data (JSON string)

## Testing Strategy

### 1. Test on Current Video

Even if video quality isn't perfect, you can still test:

```bash
python test_event_detection.py your_current_video.csv --min-confidence 0.3
```

This will show you:
- What the system can detect with current tracking quality
- Which events have high confidence (reliable)
- Which events have low confidence (may be false positives)

### 2. Review Results

- **High confidence events (0.7+)**: Likely real events - review to confirm
- **Medium confidence (0.5-0.7)**: May be real - check manually
- **Low confidence (<0.5)**: Probably false positives or poor tracking

### 3. Adjust Parameters

Based on results:
- Too many false positives? → Increase `--min-confidence`
- Missing real events? → Decrease `--min-confidence` or adjust speed/distance thresholds
- Passes too short? → Increase `--min-pass-distance`

### 4. Refine with Better Video

As you get better video:
- System will detect more events
- Confidence scores will be higher
- Fewer false positives

## Integration with Playback Viewer

You can manually review detected events in the playback viewer:

1. Run event detection: `python test_event_detection.py video.csv --export`
2. Open playback viewer: `python playback_viewer.py`
3. Load video and CSV
4. Jump to event frames using frame numbers from detected events CSV

## Troubleshooting

### "No events detected"

Possible causes:
1. **Tracking data insufficient**: Check that CSV has ball_x, ball_y, player_x, player_y columns
2. **Thresholds too strict**: Try `--min-confidence 0.3`
3. **No actual events**: Video may not contain passes/shots
4. **Ball tracking gaps**: Large gaps in ball tracking will miss events

**Solution**: Lower thresholds and check CSV data quality

### "Too many false positives"

Possible causes:
1. **Tracking noise**: Imperfect tracking creates false events
2. **Thresholds too low**: Confidence threshold too permissive

**Solution**: Increase `--min-confidence` to 0.6-0.7

### "Missing real events"

Possible causes:
1. **Ball speed too low**: Ball not moving fast enough
2. **Pass distance too high**: Short passes filtered out
3. **Possession threshold too strict**: Ball not close enough to players

**Solution**: Lower `--min-ball-speed` and `--min-pass-distance`

## Advanced Usage

### Custom Zone Definitions

Edit `test_event_detection.py` to define custom zones:

```python
zones = {
    'defensive_box': (0.0, 0.0, 1.0, 0.2),
    'midfield': (0.0, 0.2, 1.0, 0.8),
    'attacking_box': (0.0, 0.8, 1.0, 1.0)
}
```

### Programmatic Usage

```python
from event_detector import EventDetector

detector = EventDetector('your_video.csv', fps=30.0)
detector.load_tracking_data()

# Detect passes
passes = detector.detect_passes(
    min_ball_speed=3.0,
    min_pass_distance=5.0,
    confidence_threshold=0.5
)

# Detect shots
shots = detector.detect_shots(confidence_threshold=0.5)

# Zone analysis
zones = {
    'defensive_third': (0.0, 0.0, 1.0, 0.33),
    'midfield': (0.0, 0.33, 1.0, 0.67),
    'attacking_third': (0.0, 0.67, 1.0, 1.0)
}
zone_stats = detector.detect_zone_occupancy(zones)

# Export
detector.events = passes + shots
detector.export_events('events.csv')
```

## Future Enhancements

Planned features:
- Formation detection
- Tackle detection
- Foul detection
- Corner kick detection
- Free kick detection
- Integration with playback viewer (auto-jump to events)
- Event timeline visualization

## Notes

- **Works with existing CSV**: No need to re-process videos
- **Post-processing**: Analyzes tracking data after analysis is complete
- **Confidence-based**: Every detection has a reliability score
- **Tolerant**: Designed to work with imperfect tracking data
- **Adjustable**: All thresholds can be tuned for your video quality

## Support

If you encounter issues:
1. Check that CSV file has required columns (frame, ball_x, ball_y, player_id, player_x, player_y)
2. Verify tracking data quality (are players/ball being tracked?)
3. Try adjusting confidence thresholds
4. Review console output for warnings/errors

