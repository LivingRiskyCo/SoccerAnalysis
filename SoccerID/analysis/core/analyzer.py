"""
Main Analysis Orchestrator
Coordinates all analysis modules
"""

import os
import sys
from typing import Optional, Dict, Any

# Try new structure imports first, fallback to legacy
try:
    from ...utils.logger_config import get_logger
    from ..reid.reid_manager import ReIDManager
    from ..postprocessing.smoothing import SmoothingProcessor
    from ..postprocessing.drift_control import DriftController
    from ..postprocessing.validation import PostAnalysisValidator
    from ..output.csv_exporter import CSVExporter
    from ..output.metadata_exporter import MetadataExporter
except ImportError:
    try:
        from SoccerID.utils.logger_config import get_logger
        from SoccerID.analysis.reid.reid_manager import ReIDManager
        from SoccerID.analysis.postprocessing.smoothing import SmoothingProcessor
        from SoccerID.analysis.postprocessing.drift_control import DriftController
        from SoccerID.analysis.output.csv_exporter import CSVExporter
        from SoccerID.analysis.output.metadata_exporter import MetadataExporter
    except ImportError:
        # Legacy fallback - import from legacy file
        import sys
        parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        from legacy.combined_analysis_optimized import combined_analysis_optimized as _legacy_combined_analysis
        logger = None
        ReIDManager = None
        SmoothingProcessor = None
        DriftController = None
        CSVExporter = None
        MetadataExporter = None

if logger is None:
    try:
        from logger_config import get_logger
        logger = get_logger("analyzer")
    except ImportError:
        import logging
        logger = logging.getLogger("analyzer")


def combined_analysis_optimized(input_path: str, output_path: str, **kwargs):
    """
    Main analysis function - orchestrates all modules
    
    This function coordinates all analysis modules:
    - VideoProcessor: Video I/O
    - Detector: Player and ball detection
    - Tracker: Multi-object tracking
    - ReIDManager: Re-identification and gallery matching
    - SmoothingProcessor: Track smoothing
    - CSVExporter: CSV export
    - MetadataExporter: Overlay metadata export
    
    Args:
        input_path: Input video path
        output_path: Output video path
        **kwargs: Additional analysis parameters:
            - use_reid: Enable Re-ID (default: True)
            - use_gsi: Enable GSI smoothing (default: False)
            - use_kalman: Enable Kalman filtering (default: False)
            - use_ema: Enable EMA smoothing (default: False)
            - export_csv: Export CSV (default: True)
            - use_imperial_units: Use imperial units (default: False)
            - model_path: YOLO model path (default: "yolo11n.pt")
            - tracker_type: Tracker type (default: "deepocsort")
            - And many more...
    
    Returns:
        Analysis results dictionary
    """
    # Check if we should use new modular implementation or legacy
    use_new_implementation = kwargs.get('use_new_implementation', False)
    
    if not use_new_implementation:
        # For now, delegate to legacy implementation for compatibility
        # TODO: Replace with new modular implementation as modules are completed
        try:
            # Try to use legacy implementation
            import sys
            parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            
            from legacy.combined_analysis_optimized import combined_analysis_optimized as legacy_func
            return legacy_func(input_path, output_path, **kwargs)
        except ImportError:
            # Fallback: try importing from root
            try:
                from combined_analysis_optimized import combined_analysis_optimized as legacy_func
                return legacy_func(input_path, output_path, **kwargs)
            except ImportError:
                logger.error("Could not import legacy combined_analysis_optimized")
                raise
    
    # New modular implementation (work in progress)
    # This shows how modules would be coordinated
    try:
        from .video_processor import VideoProcessor
        from .detector import Detector
        from .tracker import Tracker
        from ..reid.reid_manager import ReIDManager
        from ..postprocessing.smoothing import SmoothingProcessor
        from ..output.csv_exporter import CSVExporter
        from ..output.metadata_exporter import MetadataExporter
        
        # Initialize modules
        video_processor = VideoProcessor(input_path)
        detector = Detector(
            model_path=kwargs.get('model_path', 'yolo11n.pt'),
            confidence_threshold=kwargs.get('confidence_threshold', 0.25),
            iou_threshold=kwargs.get('iou_threshold', 0.45)
        )
        tracker = Tracker(
            tracker_type=kwargs.get('tracker_type', 'deepocsort'),
            track_thresh=kwargs.get('track_thresh', 0.25),
            match_thresh=kwargs.get('match_thresh', 0.6),
            track_buffer_seconds=kwargs.get('track_buffer_seconds', 5.0),
            fps=video_processor.fps
        )
        
        # Initialize optional modules
        reid_manager = None
        if kwargs.get('use_reid', True) and ReIDManager:
            reid_manager = ReIDManager(
                use_reid=kwargs.get('use_reid', True),
                reid_similarity_threshold=kwargs.get('reid_similarity_threshold', 0.55),
                gallery_similarity_threshold=kwargs.get('gallery_similarity_threshold', 0.40),
                player_gallery=kwargs.get('player_gallery'),
                use_jersey_ocr=kwargs.get('use_jersey_ocr', True),
                ocr_consensus_frames=kwargs.get('ocr_consensus_frames', 5),
                use_face_recognition=kwargs.get('use_face_recognition', True),
                face_consensus_frames=kwargs.get('face_consensus_frames', 5),
                use_feedback_learning=kwargs.get('use_feedback_learning', True),
                use_adaptive_tracking=kwargs.get('use_adaptive_tracking', True)
            )
        
        # Initialize post-analysis validator
        validator = None
        if kwargs.get('run_validation', True) and PostAnalysisValidator:
            try:
                validator = PostAnalysisValidator()
            except Exception as e:
                logger.warning(f"Failed to initialize validator: {e}")
        
        smoothing_processor = None
        if kwargs.get('use_gsi', False) or kwargs.get('use_kalman', False) or kwargs.get('use_ema', False):
            smoothing_processor = SmoothingProcessor(
                use_gsi=kwargs.get('use_gsi', False),
                use_kalman=kwargs.get('use_kalman', False),
                use_ema=kwargs.get('use_ema', False),
                gsi_interval=kwargs.get('gsi_interval', 20),
                gsi_tau=kwargs.get('gsi_tau', 10.0),
                ema_alpha=kwargs.get('ema_alpha', 0.3)
            )
        
        csv_exporter = None
        if kwargs.get('export_csv', True):
            csv_exporter = CSVExporter()
            csv_path = output_path.replace('.mp4', '_tracking_data.csv')
            csv_exporter.initialize_csv(csv_path)
        
        metadata_exporter = None
        if kwargs.get('export_metadata', True):
            metadata_exporter = MetadataExporter()
        
        # Process video frames
        frame_num = 0
        results = {
            'total_frames': video_processor.total_frames,
            'frames_processed': 0,
            'players_detected': 0,
            'tracks_created': 0
        }
        
        logger.info(f"Starting analysis of {input_path}")
        logger.info(f"Video: {video_processor.width}x{video_processor.height} @ {video_processor.fps:.2f} fps")
        
        # Performance optimization: batch processing
        batch_size = kwargs.get('detection_batch_size', 8)
        process_every_nth = kwargs.get('process_every_nth', 1)
        
        # Main processing loop (optimized with batch processing)
        frame_buffer = []
        frame_num = 0
        
        while True:
            frame_result = video_processor.read_frame()
            if frame_result is None:
                # Process remaining frames in buffer
                if frame_buffer:
                    _process_batch(frame_buffer, detector, tracker, reid_manager, 
                                 smoothing_processor, csv_exporter, video_processor, 
                                 results, kwargs)
                break
            
            frame, current_frame = frame_result
            frame_num = current_frame
            
            # Skip frames if process_every_nth > 1 (for speed optimization)
            if frame_num % process_every_nth != 0:
                # Still need to track/interpolate skipped frames
                continue
            
            frame_buffer.append((frame, current_frame))
            
            # Process batch when buffer is full
            if len(frame_buffer) >= batch_size:
                _process_batch(frame_buffer, detector, tracker, reid_manager,
                             smoothing_processor, csv_exporter, video_processor,
                             results, kwargs)
                frame_buffer = []
        
        # Progress logging
        if frame_num % 100 == 0:
            progress = (frame_num / video_processor.total_frames * 100) if video_processor.total_frames > 0 else 0
            logger.info(f"Progress: {frame_num}/{video_processor.total_frames} frames ({progress:.1f}%)")


def _process_batch(frame_buffer, detector, tracker, reid_manager, 
                  smoothing_processor, csv_exporter, video_processor, 
                  results, kwargs):
    """Helper function to process a batch of frames"""
    frames = [f[0] for f in frame_buffer]
    frame_nums = [f[1] for f in frame_buffer]
    
    # Batch detection (much faster than individual)
    all_detections = detector.detect_players_batch(frames)
    
    # Process each frame's detections
    for i, (frame, frame_num, detections) in enumerate(zip(frames, frame_nums, all_detections)):
        # Track objects
        tracks = tracker.update(detections, frame)
        
        # Apply Re-ID if enabled
        if reid_manager:
            tracks = reid_manager.match_with_gallery(tracks, frame_num, frame)
        
        # Apply smoothing if enabled
        if smoothing_processor:
            tracks = smoothing_processor.smooth_tracks(tracks)
        
        # Export to CSV if enabled
        if csv_exporter:
            # Prepare frame data
            frame_data = {
                'frame_num': frame_num,
                'timestamp': frame_num / video_processor.fps,
                'ball_center': None,  # Would come from ball detection
                'ball_detected': False
            }
            player_centers = {track['track_id']: (
                (track['bbox'][0] + track['bbox'][2]) / 2,
                (track['bbox'][1] + track['bbox'][3]) / 2
            ) for track in tracks}
            
            csv_exporter.write_frame_data(
                frame_data,
                player_centers,
                {},  # player_names
                {},  # player_analytics
                {},  # ball_data
                use_imperial_units=kwargs.get('use_imperial_units', False)
            )
        
        results['frames_processed'] += 1
        results['players_detected'] += len(detections)
        results['tracks_created'] += len(tracks)
        
        # Cleanup
        video_processor.close()
        csv_path = None
        if csv_exporter:
            csv_exporter.close()
            results['csv_stats'] = csv_exporter.get_stats()
            csv_path = output_path.replace('.mp4', '_tracking_data.csv')
        
        # Run validation if enabled
        if validator and csv_path and os.path.exists(csv_path):
            try:
                output_dir = os.path.dirname(output_path)
                validation_results = validator.validate_analysis(csv_path, output_dir)
                results['validation'] = validation_results
                
                # Log validation summary
                summary = validation_results.get('summary', {})
                logger.info(f"Validation complete: Quality Score = {summary.get('quality_score', 'N/A')}, "
                          f"Valid Tracks = {summary.get('valid_tracks', 0)}/{summary.get('total_tracks', 0)}, "
                          f"Anomalies = {summary.get('total_anomalies', 0)}")
            except Exception as e:
                logger.warning(f"Validation failed: {e}")
        
        logger.info("Analysis complete")
        return results
        
    except Exception as e:
        logger.error(f"Error in new modular implementation: {e}", exc_info=True)
        # Fallback to legacy
        logger.warning("Falling back to legacy implementation")
        try:
            import sys
            parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            from legacy.combined_analysis_optimized import combined_analysis_optimized as legacy_func
            return legacy_func(input_path, output_path, **kwargs)
        except ImportError:
            raise

