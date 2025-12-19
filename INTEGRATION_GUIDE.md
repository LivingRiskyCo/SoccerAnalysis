# Integration Guide - How to Use New Modules

## Quick Start

### 1. Enable Features in GUI

1. Open the **"🧠 ML & Validation"** tab
2. Check the features you want:
   - ✅ Enable Face Recognition
   - ✅ Learn from User Corrections
   - ✅ Adaptive Tracking
   - ✅ Predictive Analytics
   - ✅ Run Validation After Analysis

### 2. Run Analysis

The new features will automatically:
- Extract face features during analysis
- Learn from any corrections you make
- Adapt thresholds based on performance
- Generate validation reports after analysis

### 3. View Results

- **Quality Reports**: Check `*_quality_report.json` in output folder
- **Validation Results**: Shown in analysis summary
- **Feedback Stats**: Click "View Feedback Statistics" in ML tab
- **Performance Stats**: Click "View Performance Stats" in ML tab

## Programmatic Usage

### Basic Integration

```python
from soccer_analysis.integration.analysis_integration import AnalysisIntegration

# Initialize
integration = AnalysisIntegration(
    use_face_recognition=True,
    use_feedback_learning=True,
    use_adaptive_tracking=True,
    use_predictive_analytics=True,
    run_validation=True
)

# In your analysis loop
for frame_num, frame in enumerate(video):
    detections = detect_players(frame)
    tracks = track_objects(detections)
    
    # Enhance with new modules
    tracks = integration.process_frame(frame, tracks, frame_num)
    
    # Record performance (for adaptive tracking)
    integration.record_performance(
        frame_num, track_quality=0.85, match_accuracy=0.92
    )

# After analysis
validation = integration.validate_analysis(csv_path, output_dir)
print(f"Quality Score: {validation['summary']['quality_score']}")
```

### Recording Corrections

```python
# When user corrects a player assignment
integration.record_correction(
    player_id="john_doe",
    original_track_id=5,  # Wrong track
    corrected_track_id=12,  # Correct track
    frame_num=1000,
    context={
        'original_similarity': 0.45,
        'corrected_similarity': 0.78
    }
)
```

### Getting Predictions

```python
# Get predictions for a track
predictions = integration.get_predictions(track_id=1, frames_ahead=5)
if predictions:
    print(f"Predicted position: {predictions['predicted_position']}")
    print(f"Direction: {predictions['direction']}°")
    print(f"Trajectory type: {predictions['trajectory']['trajectory_type']}")
```

## Integration with Legacy Code

### Option 1: Use Integration Helper (Recommended)

```python
from soccer_analysis.integration.analysis_integration import AnalysisIntegration

# In combined_analysis_optimized.py
integration = AnalysisIntegration()

# In main loop, after tracking:
if integration.use_face_recognition:
    tracks = integration.process_frame(frame, tracks, frame_num)

# After analysis:
if integration.run_validation:
    csv_path = output_path.replace('.mp4', '_tracking_data.csv')
    validation = integration.validate_analysis(csv_path, output_dir)
```

### Option 2: Direct Module Usage

```python
from soccer_analysis.analysis.reid.reid_manager import ReIDManager

# Initialize with all features
reid_manager = ReIDManager(
    use_reid=True,
    use_jersey_ocr=True,
    use_face_recognition=True,
    use_feedback_learning=True,
    use_adaptive_tracking=True,
    player_gallery=gallery
)

# Use in matching
detections = reid_manager.match_with_gallery(detections, frame_num, frame)
```

## Validation Workflow

### Automatic Validation

Validation runs automatically after analysis if `run_validation=True`:

```python
# In analyzer.py
if validator and csv_path:
    validation_results = validator.validate_analysis(csv_path, output_dir)
    # Results include:
    # - quality_report: Quality metrics and issues
    # - track_validation: Track continuity validation
    # - anomalies: Anomaly detection results
    # - summary: Overall summary
```

### Manual Validation

```python
from soccer_analysis.validation.quality_reporter import QualityReporter
from soccer_analysis.validation.track_validator import TrackValidator
from soccer_analysis.validation.anomaly_detector import AnomalyDetector

# Generate quality report
reporter = QualityReporter()
report = reporter.generate_report("tracking.csv", "report.json")

# Validate tracks
validator = TrackValidator()
results = validator.validate_tracks("tracking.csv")

# Detect anomalies
detector = AnomalyDetector()
anomalies = detector.detect_anomalies("tracking.csv")
```

## Face Recognition Workflow

### Automatic Face Recognition

Face recognition runs automatically during analysis:

```python
# In ReIDManager.match_with_gallery()
if self.use_face_recognition and self.face_recognizer:
    detections = self.face_recognizer.recognize_with_consensus(
        frame, detections, frame_num
    )
    # detections now include 'face_match' and 'face_confidence'
```

### Manual Face Recognition

```python
from soccer_analysis.recognition.face_recognition import FaceRecognizer

recognizer = FaceRecognizer(backend="auto")
face_result = recognizer.detect_face(frame, bbox)

if face_result:
    match = recognizer.match_face(face_result['encoding'])
    if match:
        player_id, similarity = match
        print(f"Face matched to {player_id} with {similarity:.3f} confidence")
```

## Feedback Learning Workflow

### Recording Corrections

```python
from soccer_analysis.ml.feedback_learner import FeedbackLearner

learner = FeedbackLearner()

# When user corrects a player
learner.record_correction(
    player_id="john_doe",
    original_track_id=5,
    corrected_track_id=12,
    frame_num=1000,
    context={'similarity_scores': {...}}
)

# Get adjustment for future matching
adjustment = learner.get_adjustment("john_doe")
# Use adjustment to modify similarity threshold
```

### Viewing Statistics

```python
stats = learner.get_statistics()
print(f"Total corrections: {stats['total_corrections']}")
print(f"Learned patterns: {stats['learned_patterns']}")
```

## Adaptive Tracking Workflow

### Automatic Adaptation

Adaptive tracking adjusts thresholds automatically:

```python
from soccer_analysis.ml.adaptive_tracker import AdaptiveTracker

tracker = AdaptiveTracker()

# Record performance each frame
tracker.record_performance(
    frame_num=1000,
    track_quality=0.85,
    match_accuracy=0.92,
    false_positives=2,
    false_negatives=1
)

# Get current thresholds (automatically adjusted)
thresholds = tracker.get_current_thresholds()
print(f"Similarity threshold: {thresholds['similarity_threshold']}")
```

## All Modules Are Now Integrated! 🎉

The system is ready to use with all new features enabled.

