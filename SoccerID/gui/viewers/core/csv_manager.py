"""
CSV Manager - Handles CSV tracking data loading and access
Shared across all viewer modes
"""

import pandas as pd
import os
from typing import Optional, Dict, Tuple
import numpy as np


class CSVManager:
    """Manages CSV tracking data"""
    
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = csv_path
        self.df: Optional[pd.DataFrame] = None
        self.player_data = {}  # frame_num -> {player_id: (x, y, team, name, bbox)}
        self.ball_data = {}  # frame_num -> (x, y)
        self.loaded = False
        
        if csv_path:
            self.load_csv(csv_path)
    
    def load_csv(self, csv_path: str) -> bool:
        """Load CSV tracking data"""
        if not os.path.exists(csv_path):
            print(f"Error: CSV file not found: {csv_path}")
            return False
        
        try:
            # Skip comment lines
            self.df = pd.read_csv(csv_path, comment='#')
            
            if self.df.empty:
                print(f"Error: CSV file is empty: {csv_path}")
                return False
            
            # Check if it has frame column
            if 'frame' not in self.df.columns:
                self.df['frame'] = self.df.index
            
            # Process player data
            self._process_player_data()
            
            # Process ball data
            self._process_ball_data()
            
            self.csv_path = csv_path
            self.loaded = True
            print(f"✓ Loaded CSV data: {len(self.df)} rows from {os.path.basename(csv_path)}")
            return True
        except Exception as e:
            print(f"Error loading CSV: {e}")
            return False
    
    def _process_player_data(self):
        """Process player data from CSV"""
        self.player_data = {}
        
        if 'player_id' not in self.df.columns:
            return
        
        # Filter valid rows
        valid_mask = (
            self.df['frame'].notna() & 
            self.df['player_id'].notna() &
            self.df['player_x'].notna() &
            self.df['player_y'].notna()
        )
        valid_df = self.df[valid_mask].copy()
        
        if len(valid_df) == 0:
            return
        
        # Convert to int
        valid_df['frame'] = valid_df['frame'].astype(int)
        valid_df['player_id'] = valid_df['player_id'].astype(int)
        
        # Check if CSV has bbox columns
        has_bbox = all(col in valid_df.columns for col in ['x1', 'y1', 'x2', 'y2'])
        
        # Group by frame
        for frame_num, frame_group in valid_df.groupby('frame'):
            frame_num_int = int(frame_num)
            if frame_num_int not in self.player_data:
                self.player_data[frame_num_int] = {}
            
            for _, row in frame_group.iterrows():
                player_id = int(row['player_id'])
                x = float(row['player_x'])
                y = float(row['player_y'])
                
                # Get bbox if available
                bbox = None
                if has_bbox:
                    x1 = row.get('x1')
                    y1 = row.get('y1')
                    x2 = row.get('x2')
                    y2 = row.get('y2')
                    if pd.notna(x1) and pd.notna(y1) and pd.notna(x2) and pd.notna(y2):
                        bbox = (float(x1), float(y1), float(x2), float(y2))
                
                # Get team
                team = None
                if 'team' in row and pd.notna(row['team']):
                    team = row['team']
                
                # Get player name
                name = f"#{player_id}"
                if 'player_name' in row and pd.notna(row['player_name']):
                    csv_name = str(row['player_name']).strip()
                    if csv_name and csv_name != 'nan' and csv_name.lower() != 'none':
                        name = csv_name
                
                self.player_data[frame_num_int][player_id] = (x, y, team, name, bbox)
    
    def _process_ball_data(self):
        """Process ball data from CSV"""
        self.ball_data = {}
        
        if 'ball_x' not in self.df.columns or 'ball_y' not in self.df.columns:
            return
        
        # Filter valid rows
        valid_mask = (
            self.df['frame'].notna() & 
            self.df['ball_x'].notna() &
            self.df['ball_y'].notna()
        )
        valid_df = self.df[valid_mask].copy()
        
        if len(valid_df) == 0:
            return
        
        valid_df['frame'] = valid_df['frame'].astype(int)
        
        # Group by frame
        for frame_num, frame_group in valid_df.groupby('frame'):
            frame_num_int = int(frame_num)
            row = frame_group.iloc[0]
            ball_x = float(row['ball_x'])
            ball_y = float(row['ball_y'])
            
            # Check if coordinates are normalized (0-1)
            if 0.0 <= ball_x <= 1.0 and 0.0 <= ball_y <= 1.0:
                # Will need video dimensions to convert - store as normalized for now
                self.ball_data[frame_num_int] = (ball_x, ball_y, True)  # (x, y, normalized)
            else:
                self.ball_data[frame_num_int] = (ball_x, ball_y, False)  # (x, y, normalized)
    
    def get_player_data(self, frame_num: int) -> Dict:
        """Get player data for a frame"""
        return self.player_data.get(frame_num, {})
    
    def get_ball_data(self, frame_num: int) -> Optional[Tuple[float, float, bool]]:
        """Get ball data for a frame"""
        return self.ball_data.get(frame_num)
    
    def extract_player_assignments(self) -> Dict[str, tuple]:
        """Extract player_id -> (player_name, team, jersey_number) mappings from CSV"""
        assignments = {}
        
        if self.df is None or self.df.empty:
            return assignments
        
        if 'player_id' not in self.df.columns:
            return assignments
        
        # Filter valid rows
        valid_mask = (
            self.df['player_id'].notna() &
            ('player_name' in self.df.columns) &
            (self.df['player_name'].notna())
        )
        valid_df = self.df[valid_mask].copy()
        
        if len(valid_df) == 0:
            return assignments
        
        # Group by player_id and get most common values
        for player_id, group in valid_df.groupby('player_id'):
            # Get most common player_name
            player_names = group['player_name'].astype(str).str.strip()
            player_names = player_names[player_names != 'nan']
            player_names = player_names[player_names.str.lower() != 'none']
            
            if len(player_names) > 0:
                most_common_name = player_names.mode()
                if len(most_common_name) > 0:
                    player_name = most_common_name.iloc[0]
                    
                    # Get team
                    team = ""
                    if 'team' in group.columns:
                        teams = group['team'].astype(str).str.strip()
                        teams = teams[teams != 'nan']
                        if len(teams) > 0:
                            most_common_team = teams.mode()
                            if len(most_common_team) > 0:
                                team = most_common_team.iloc[0]
                    
                    # Get jersey_number
                    jersey_number = ""
                    if 'jersey_number' in group.columns:
                        jerseys = group['jersey_number'].astype(str).str.strip()
                        jerseys = jerseys[jerseys != 'nan']
                        if len(jerseys) > 0:
                            most_common_jersey = jerseys.mode()
                            if len(most_common_jersey) > 0:
                                jersey_number = most_common_jersey.iloc[0]
                    
                    player_id_str = str(int(player_id))
                    assignments[player_id_str] = (player_name, team, jersey_number)
        
        return assignments
    
    def is_loaded(self) -> bool:
        """Check if CSV is loaded"""
        return self.loaded

