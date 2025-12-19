"""
Video Search Module
Search across multiple videos for events, players, and patterns
"""

import os
import pandas as pd
from typing import Dict, List, Any, Optional
from pathlib import Path

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

logger = get_logger("video_search")


class VideoSearch:
    """
    Search across multiple videos
    """
    
    def __init__(self, search_index_file: Optional[str] = None):
        """
        Initialize video search
        
        Args:
            search_index_file: Path to search index file
        """
        self.search_index_file = search_index_file or "video_search_index.json"
        self.index = {}  # video_path -> metadata
        self.load_index()
    
    def index_video(self,
                   video_path: str,
                   csv_path: str,
                   metadata: Optional[Dict[str, Any]] = None):
        """
        Index a video for searching
        
        Args:
            video_path: Path to video file
            csv_path: Path to tracking CSV
            metadata: Optional metadata (date, teams, etc.)
        """
        if not os.path.exists(csv_path):
            logger.warning(f"CSV not found: {csv_path}")
            return
        
        try:
            df = pd.read_csv(csv_path)
            
            # Extract searchable information
            index_entry = {
                'video_path': video_path,
                'csv_path': csv_path,
                'metadata': metadata or {},
                'players': [],
                'events': [],
                'date': metadata.get('date') if metadata else None,
                'teams': metadata.get('teams', []) if metadata else [],
                'indexed_at': pd.Timestamp.now().isoformat()
            }
            
            # Extract unique players
            if 'player_name' in df.columns:
                index_entry['players'] = df['player_name'].dropna().unique().tolist()
            
            # Extract events (if events CSV exists)
            events_path = csv_path.replace('_tracking_data.csv', '_events.csv')
            if os.path.exists(events_path):
                try:
                    events_df = pd.read_csv(events_path)
                    if 'event_type' in events_df.columns:
                        index_entry['events'] = events_df['event_type'].unique().tolist()
                except:
                    pass
            
            self.index[video_path] = index_entry
            self.save_index()
            
            logger.info(f"Indexed video: {video_path}")
        except Exception as e:
            logger.error(f"Failed to index video: {e}")
    
    def search(self,
              query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search across indexed videos
        
        Args:
            query: Search query dictionary:
                - player_name: Search for player
                - event_type: Search for event type
                - date_range: Search by date range
                - team: Search by team
                - keywords: Text search in metadata
                
        Returns:
            List of matching videos with relevance scores
        """
        results = []
        
        for video_path, entry in self.index.items():
            score = 0.0
            matches = []
            
            # Player search
            if 'player_name' in query:
                query_player = query['player_name']
                if query_player in entry['players']:
                    score += 10.0
                    matches.append(f"Player: {query_player}")
            
            # Event search
            if 'event_type' in query:
                query_event = query['event_type']
                if query_event in entry['events']:
                    score += 8.0
                    matches.append(f"Event: {query_event}")
            
            # Date range search
            if 'date_range' in query:
                start_date, end_date = query['date_range']
                if entry['date']:
                    entry_date = pd.Timestamp(entry['date'])
                    if start_date <= entry_date <= end_date:
                        score += 5.0
                        matches.append(f"Date: {entry['date']}")
            
            # Team search
            if 'team' in query:
                query_team = query['team']
                if query_team in entry['teams']:
                    score += 7.0
                    matches.append(f"Team: {query_team}")
            
            # Keyword search
            if 'keywords' in query:
                keywords = query['keywords'].lower()
                metadata_str = str(entry['metadata']).lower()
                if keywords in metadata_str:
                    score += 3.0
                    matches.append(f"Keywords: {keywords}")
            
            if score > 0:
                results.append({
                    'video_path': video_path,
                    'csv_path': entry['csv_path'],
                    'score': score,
                    'matches': matches,
                    'metadata': entry['metadata']
                })
        
        # Sort by relevance score
        results.sort(key=lambda x: x['score'], reverse=True)
        
        logger.info(f"Search found {len(results)} matching videos")
        return results
    
    def save_index(self):
        """Save search index"""
        try:
            import json
            with open(self.search_index_file, 'w') as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
    
    def load_index(self):
        """Load search index"""
        if not os.path.exists(self.search_index_file):
            return
        
        try:
            import json
            with open(self.search_index_file, 'r') as f:
                self.index = json.load(f)
            logger.info(f"Loaded index for {len(self.index)} videos")
        except Exception as e:
            logger.error(f"Failed to load index: {e}")

