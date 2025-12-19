"""
Automatic Data Quality Reports
Analyzes tracking data quality and generates comprehensive reports
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
import os

# Try to import logger
try:
    from ...utils.logger_config import get_logger
except ImportError:
    try:
        from soccer_analysis.utils.logger_config import get_logger
    except ImportError:
        try:
            from utils.logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("quality_reporter")


class QualityReporter:
    """
    Generates automatic data quality reports for tracking data
    """
    
    def __init__(self):
        """Initialize quality reporter"""
        pass
    
    def generate_report(self, csv_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate comprehensive quality report from CSV tracking data
        
        Args:
            csv_path: Path to tracking CSV file
            output_path: Optional path to save report (JSON format)
            
        Returns:
            Dictionary with quality metrics and issues
        """
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return {'error': str(e)}
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'csv_path': csv_path,
            'total_frames': len(df),
            'metrics': {},
            'issues': [],
            'warnings': [],
            'recommendations': []
        }
        
        # Basic statistics
        if 'frame_num' in df.columns:
            report['metrics']['frame_range'] = {
                'min': int(df['frame_num'].min()),
                'max': int(df['frame_num'].max()),
                'total': int(df['frame_num'].max() - df['frame_num'].min() + 1)
            }
        
        # Player statistics
        if 'player_name' in df.columns:
            unique_players = df['player_name'].dropna().unique()
            report['metrics']['num_players'] = len(unique_players)
            report['metrics']['players'] = unique_players.tolist()
        
        # Track ID statistics
        if 'track_id' in df.columns:
            unique_tracks = df['track_id'].dropna().unique()
            report['metrics']['num_tracks'] = len(unique_tracks)
            
            # Track continuity
            track_continuity = self._check_track_continuity(df)
            report['metrics']['track_continuity'] = track_continuity
        
        # Missing data detection
        missing_data = self._detect_missing_data(df)
        report['issues'].extend(missing_data)
        
        # Data completeness
        completeness = self._calculate_completeness(df)
        report['metrics']['completeness'] = completeness
        
        # Position validation
        position_issues = self._validate_positions(df)
        report['issues'].extend(position_issues)
        
        # Speed validation
        speed_issues = self._validate_speeds(df)
        report['warnings'].extend(speed_issues)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(report)
        report['recommendations'] = recommendations
        
        # Calculate overall quality score
        report['metrics']['quality_score'] = self._calculate_quality_score(report)
        
        # Save report if output path provided
        if output_path:
            import json
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Quality report saved to {output_path}")
        
        return report
    
    def _check_track_continuity(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Check track continuity"""
        if 'track_id' not in df.columns or 'frame_num' not in df.columns:
            return {}
        
        continuity_issues = []
        for track_id in df['track_id'].dropna().unique():
            track_df = df[df['track_id'] == track_id].sort_values('frame_num')
            frames = track_df['frame_num'].values
            
            # Check for gaps
            gaps = []
            for i in range(len(frames) - 1):
                gap = frames[i + 1] - frames[i]
                if gap > 1:
                    gaps.append({
                        'track_id': int(track_id),
                        'gap_start': int(frames[i]),
                        'gap_end': int(frames[i + 1]),
                        'gap_size': int(gap - 1)
                    })
            
            if gaps:
                continuity_issues.append({
                    'track_id': int(track_id),
                    'gaps': gaps,
                    'total_gaps': len(gaps)
                })
        
        return {
            'total_tracks': len(df['track_id'].dropna().unique()),
            'tracks_with_gaps': len(continuity_issues),
            'gaps': continuity_issues
        }
    
    def _detect_missing_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect missing data in tracking"""
        issues = []
        
        # Check for missing required columns
        required_columns = ['frame_num', 'track_id']
        for col in required_columns:
            if col not in df.columns:
                issues.append({
                    'type': 'missing_column',
                    'column': col,
                    'severity': 'critical'
                })
        
        # Check for missing values in key columns
        key_columns = ['x', 'y', 'player_name']
        for col in key_columns:
            if col in df.columns:
                missing_count = df[col].isna().sum()
                missing_pct = (missing_count / len(df)) * 100
                if missing_pct > 5:  # More than 5% missing
                    issues.append({
                        'type': 'missing_values',
                        'column': col,
                        'missing_count': int(missing_count),
                        'missing_percentage': float(missing_pct),
                        'severity': 'high' if missing_pct > 20 else 'medium'
                    })
        
        return issues
    
    def _calculate_completeness(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate data completeness metrics"""
        completeness = {}
        
        key_columns = ['x', 'y', 'player_name', 'track_id', 'confidence']
        for col in key_columns:
            if col in df.columns:
                non_null = df[col].notna().sum()
                completeness[col] = float((non_null / len(df)) * 100)
        
        return completeness
    
    def _validate_positions(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Validate position data"""
        issues = []
        
        if 'x' in df.columns and 'y' in df.columns:
            # Check for out-of-bounds positions (assuming reasonable field size)
            # These thresholds should be configurable
            max_x = df['x'].max()
            max_y = df['y'].max()
            
            if max_x > 10000 or max_y > 10000:
                issues.append({
                    'type': 'out_of_bounds',
                    'message': f'Positions exceed reasonable bounds (max_x={max_x:.1f}, max_y={max_y:.1f})',
                    'severity': 'medium'
                })
            
            # Check for negative positions
            negative_x = (df['x'] < 0).sum()
            negative_y = (df['y'] < 0).sum()
            if negative_x > 0 or negative_y > 0:
                issues.append({
                    'type': 'negative_positions',
                    'negative_x_count': int(negative_x),
                    'negative_y_count': int(negative_y),
                    'severity': 'low'
                })
        
        return issues
    
    def _validate_speeds(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Validate speed data"""
        warnings = []
        
        if 'speed' in df.columns:
            max_speed = df['speed'].max()
            # Soccer players typically don't exceed 35 km/h (9.7 m/s)
            if max_speed > 15:  # m/s
                warnings.append({
                    'type': 'unrealistic_speed',
                    'max_speed': float(max_speed),
                    'message': f'Maximum speed ({max_speed:.1f} m/s) seems unrealistic',
                    'severity': 'medium'
                })
        
        return warnings
    
    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on quality issues"""
        recommendations = []
        
        # Check for missing data
        missing_issues = [i for i in report['issues'] if i.get('type') == 'missing_values']
        if missing_issues:
            recommendations.append("Consider re-running analysis to fill missing data gaps")
        
        # Check for track continuity
        if 'track_continuity' in report['metrics']:
            continuity = report['metrics']['track_continuity']
            if continuity.get('tracks_with_gaps', 0) > 0:
                recommendations.append("Some tracks have gaps - consider adjusting tracking parameters")
        
        # Check quality score
        quality_score = report['metrics'].get('quality_score', 100)
        if quality_score < 70:
            recommendations.append("Overall quality score is low - review tracking settings and re-analyze")
        
        return recommendations
    
    def _calculate_quality_score(self, report: Dict[str, Any]) -> float:
        """Calculate overall quality score (0-100)"""
        score = 100.0
        
        # Deduct for issues
        for issue in report['issues']:
            severity = issue.get('severity', 'low')
            if severity == 'critical':
                score -= 20
            elif severity == 'high':
                score -= 10
            elif severity == 'medium':
                score -= 5
            else:
                score -= 2
        
        # Deduct for warnings
        for warning in report['warnings']:
            severity = warning.get('severity', 'low')
            if severity == 'high':
                score -= 5
            elif severity == 'medium':
                score -= 2
        
        # Deduct for missing data
        if 'completeness' in report['metrics']:
            completeness = report['metrics']['completeness']
            for col, pct in completeness.items():
                if pct < 90:
                    score -= (100 - pct) * 0.1
        
        return max(0.0, min(100.0, score))

