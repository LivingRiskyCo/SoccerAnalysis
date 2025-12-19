"""
Post-Analysis Validation
Runs quality checks, track validation, and anomaly detection after analysis
"""

import os
from typing import Dict, Any, Optional, List
from pathlib import Path

# Try to import validation modules
try:
    from ...validation.quality_reporter import QualityReporter
    from ...validation.track_validator import TrackValidator
    from ...validation.anomaly_detector import AnomalyDetector
    VALIDATION_AVAILABLE = True
except ImportError:
    try:
        from SoccerID.validation.quality_reporter import QualityReporter
        from SoccerID.validation.track_validator import TrackValidator
        from SoccerID.validation.anomaly_detector import AnomalyDetector
        VALIDATION_AVAILABLE = True
    except ImportError:
        try:
            from validation.quality_reporter import QualityReporter
            from validation.track_validator import TrackValidator
            from validation.anomaly_detector import AnomalyDetector
            VALIDATION_AVAILABLE = True
        except ImportError:
            VALIDATION_AVAILABLE = False
            QualityReporter = None
            TrackValidator = None
            AnomalyDetector = None

# Try to import logger
try:
    from ...utils.logger_config import get_logger
except ImportError:
    try:
        from SoccerID.utils.logger_config import get_logger
    except ImportError:
        try:
            from utils.logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("validation")


class PostAnalysisValidator:
    """
    Runs validation checks after analysis completes
    """
    
    def __init__(self):
        """Initialize post-analysis validator"""
        self.quality_reporter = None
        self.track_validator = None
        self.anomaly_detector = None
        
        if VALIDATION_AVAILABLE:
            try:
                self.quality_reporter = QualityReporter()
                self.track_validator = TrackValidator()
                self.anomaly_detector = AnomalyDetector()
                logger.info("Post-analysis validation initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize validation modules: {e}")
    
    def validate_analysis(self, csv_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Run all validation checks on analysis results
        
        Args:
            csv_path: Path to tracking CSV file
            output_dir: Optional directory to save validation reports
            
        Returns:
            Dictionary with all validation results
        """
        if not VALIDATION_AVAILABLE:
            return {'error': 'Validation modules not available'}
        
        results = {
            'quality_report': None,
            'track_validation': None,
            'anomalies': None,
            'summary': {}
        }
        
        # Generate quality report
        if self.quality_reporter:
            try:
                quality_report_path = None
                if output_dir:
                    quality_report_path = os.path.join(output_dir, "quality_report.json")
                
                results['quality_report'] = self.quality_reporter.generate_report(
                    csv_path, quality_report_path
                )
                logger.info(f"Quality report generated: Score = {results['quality_report'].get('metrics', {}).get('quality_score', 'N/A')}")
            except Exception as e:
                logger.error(f"Quality report generation failed: {e}")
                results['quality_report'] = {'error': str(e)}
        
        # Validate tracks
        if self.track_validator:
            try:
                results['track_validation'] = self.track_validator.validate_tracks(csv_path)
                logger.info(f"Track validation: {results['track_validation'].get('valid_tracks', 0)}/{results['track_validation'].get('total_tracks', 0)} valid")
            except Exception as e:
                logger.error(f"Track validation failed: {e}")
                results['track_validation'] = {'error': str(e)}
        
        # Detect anomalies
        if self.anomaly_detector:
            try:
                results['anomalies'] = self.anomaly_detector.detect_anomalies(csv_path)
                summary = results['anomalies'].get('summary', {})
                total_anomalies = sum([
                    summary.get('total_impossible_movements', 0),
                    summary.get('total_unrealistic_speeds', 0),
                    summary.get('total_unrealistic_accelerations', 0),
                    summary.get('total_position_jumps', 0)
                ])
                logger.info(f"Anomaly detection: {total_anomalies} anomalies found")
            except Exception as e:
                logger.error(f"Anomaly detection failed: {e}")
                results['anomalies'] = {'error': str(e)}
        
        # Create summary
        results['summary'] = {
            'quality_score': results['quality_report'].get('metrics', {}).get('quality_score', 0) if results['quality_report'] else 0,
            'valid_tracks': results['track_validation'].get('valid_tracks', 0) if results['track_validation'] else 0,
            'total_tracks': results['track_validation'].get('total_tracks', 0) if results['track_validation'] else 0,
            'total_anomalies': sum([
                results['anomalies'].get('summary', {}).get('total_impossible_movements', 0),
                results['anomalies'].get('summary', {}).get('total_unrealistic_speeds', 0),
                results['anomalies'].get('summary', {}).get('total_unrealistic_accelerations', 0),
                results['anomalies'].get('summary', {}).get('total_position_jumps', 0)
            ]) if results['anomalies'] else 0
        }
        
        return results

