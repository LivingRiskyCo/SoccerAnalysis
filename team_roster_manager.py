"""
Team Roster Management
Import/export rosters, link players to videos
"""

import json
import csv
import os
from typing import Dict, List, Optional

class TeamRosterManager:
    def __init__(self, roster_file: str = "team_roster.json"):
        self.roster_file = roster_file
        self.roster = self._load_roster()
    
    def _load_roster(self) -> Dict:
        """Load roster from file"""
        if os.path.exists(self.roster_file):
            try:
                with open(self.roster_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load roster: {e}")
                return {}
        return {}
    
    def save_roster(self):
        """Save roster to file"""
        try:
            with open(self.roster_file, 'w', encoding='utf-8') as f:
                json.dump(self.roster, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving roster: {e}")
            raise
    
    def _parse_color_string(self, color_str: str) -> Optional[List[int]]:
        """Parse color string from CSV (format: 'R,G,B' or '#RRGGBB' or 'rgb(R,G,B)')"""
        if not color_str or not color_str.strip():
            return None
        color_str = color_str.strip()
        
        # Try RGB format: "255,0,0" or "255, 0, 0"
        if ',' in color_str:
            try:
                parts = [int(x.strip()) for x in color_str.split(',')]
                if len(parts) == 3 and all(0 <= p <= 255 for p in parts):
                    return parts
            except ValueError:
                pass
        
        # Try hex format: "#FF0000" or "FF0000"
        if color_str.startswith('#'):
            color_str = color_str[1:]
        if len(color_str) == 6:
            try:
                r = int(color_str[0:2], 16)
                g = int(color_str[2:4], 16)
                b = int(color_str[4:6], 16)
                return [r, g, b]
            except ValueError:
                pass
        
        return None
    
    def _parse_visualization_settings(self, row: Dict) -> Dict:
        """Parse visualization settings from CSV row"""
        viz_settings = {}
        
        # Custom color
        custom_color = None
        if row.get('custom_color') or row.get('color'):
            color_str = row.get('custom_color') or row.get('color')
            custom_color = self._parse_color_string(color_str)
        
        if custom_color:
            viz_settings['use_custom_color'] = True
            viz_settings['custom_color_rgb'] = custom_color
        
        # Box color override
        if row.get('box_color'):
            box_color = self._parse_color_string(row.get('box_color'))
            if box_color:
                viz_settings['box_color'] = box_color
        
        # Label color override
        if row.get('label_color'):
            label_color = self._parse_color_string(row.get('label_color'))
            if label_color:
                viz_settings['label_color'] = label_color
        
        # Box thickness
        if row.get('box_thickness'):
            try:
                thickness = int(row.get('box_thickness'))
                if 1 <= thickness <= 10:
                    viz_settings['box_thickness'] = thickness
            except ValueError:
                pass
        
        # Show glow
        if row.get('show_glow'):
            viz_settings['show_glow'] = row.get('show_glow', '').lower() in ('true', '1', 'yes', 'y')
        
        # Glow color
        if row.get('glow_color'):
            glow_color = self._parse_color_string(row.get('glow_color'))
            if glow_color:
                viz_settings['glow_color'] = glow_color
        
        # Glow intensity
        if row.get('glow_intensity'):
            try:
                intensity = int(row.get('glow_intensity'))
                if 0 <= intensity <= 100:
                    viz_settings['glow_intensity'] = intensity
            except ValueError:
                pass
        
        # Show trail
        if row.get('show_trail'):
            viz_settings['show_trail'] = row.get('show_trail', '').lower() in ('true', '1', 'yes', 'y')
        
        # Trail color
        if row.get('trail_color'):
            trail_color = self._parse_color_string(row.get('trail_color'))
            if trail_color:
                viz_settings['trail_color'] = trail_color
        
        # Trail length
        if row.get('trail_length'):
            try:
                length = int(row.get('trail_length'))
                if 1 <= length <= 100:
                    viz_settings['trail_length'] = length
            except ValueError:
                pass
        
        # Label style
        if row.get('label_style'):
            style = row.get('label_style').strip().lower()
            if style in ('full_name', 'jersey', 'initials', 'number'):
                viz_settings['label_style'] = style
        
        return viz_settings if viz_settings else None
    
    def import_from_csv(self, csv_path: str):
        """Import roster from CSV file
        Expected CSV format: name, jersey_number, team, position, active
        Optional visualization columns: custom_color, box_color, label_color, box_thickness, 
        show_glow, glow_color, glow_intensity, show_trail, trail_color, trail_length, label_style
        Color format: 'R,G,B' (e.g., '255,0,0') or '#RRGGBB' (e.g., '#FF0000')
        """
        imported_count = 0
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                player_name = row.get('name') or row.get('player_name') or row.get('Name')
                if player_name and player_name.strip():
                    player_name = player_name.strip()
                    player_data = {
                        "jersey_number": (row.get('jersey_number') or row.get('jersey') or row.get('Jersey Number') or "").strip() or None,
                        "team": (row.get('team') or row.get('Team') or "").strip() or None,
                        "position": (row.get('position') or row.get('Position') or "").strip() or None,
                        "active": row.get('active', 'true').lower() in ('true', '1', 'yes', 'y', '')
                    }
                    
                    # Parse visualization settings
                    viz_settings = self._parse_visualization_settings(row)
                    if viz_settings:
                        player_data["visualization_settings"] = viz_settings
                    
                    self.roster[player_name] = player_data
                    imported_count += 1
        self.save_roster()
        return imported_count
    
    def _format_color_string(self, color_rgb: List[int]) -> str:
        """Format color as CSV-friendly string: 'R,G,B'"""
        if color_rgb and len(color_rgb) == 3:
            return f"{color_rgb[0]},{color_rgb[1]},{color_rgb[2]}"
        return ''
    
    def export_to_csv(self, output_path: str, include_visualization: bool = True):
        """Export roster to CSV file
        Args:
            output_path: Path to output CSV file
            include_visualization: If True, include visualization settings columns
        """
        fieldnames = ['name', 'jersey_number', 'team', 'position', 'active']
        if include_visualization:
            fieldnames.extend([
                'custom_color', 'box_color', 'label_color', 'box_thickness',
                'show_glow', 'glow_color', 'glow_intensity',
                'show_trail', 'trail_color', 'trail_length', 'label_style'
            ])
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for name, data in self.roster.items():
                if name == 'videos':  # Skip videos metadata
                    continue
                
                row = {
                    'name': name,
                    'jersey_number': data.get('jersey_number', '') or '',
                    'team': data.get('team', '') or '',
                    'position': data.get('position', '') or '',
                    'active': str(data.get('active', True))
                }
                
                if include_visualization:
                    viz = data.get('visualization_settings', {})
                    row['custom_color'] = self._format_color_string(viz.get('custom_color_rgb'))
                    row['box_color'] = self._format_color_string(viz.get('box_color'))
                    row['label_color'] = self._format_color_string(viz.get('label_color'))
                    row['box_thickness'] = str(viz.get('box_thickness', '')) if viz.get('box_thickness') else ''
                    row['show_glow'] = str(viz.get('show_glow', '')).lower() if viz.get('show_glow') is not None else ''
                    row['glow_color'] = self._format_color_string(viz.get('glow_color'))
                    row['glow_intensity'] = str(viz.get('glow_intensity', '')) if viz.get('glow_intensity') else ''
                    row['show_trail'] = str(viz.get('show_trail', '')).lower() if viz.get('show_trail') is not None else ''
                    row['trail_color'] = self._format_color_string(viz.get('trail_color'))
                    row['trail_length'] = str(viz.get('trail_length', '')) if viz.get('trail_length') else ''
                    row['label_style'] = viz.get('label_style', '') or ''
                
                writer.writerow(row)
    
    def link_video_to_roster(self, video_path: str, roster_players: List[str]):
        """Link a video to specific roster players"""
        video_name = os.path.basename(video_path)
        if 'videos' not in self.roster:
            self.roster['videos'] = {}
        self.roster['videos'][video_name] = roster_players
        self.save_roster()
    
    def get_videos_for_player(self, player_name: str) -> List[str]:
        """Get list of videos linked to a player"""
        videos = self.roster.get('videos', {})
        return [video for video, players in videos.items() if player_name in players]
    
    def get_players_for_video(self, video_path: str) -> List[str]:
        """Get list of players linked to a video"""
        video_name = os.path.basename(video_path)
        return self.roster.get('videos', {}).get(video_name, [])
    
    def add_player(self, name: str, jersey_number: Optional[str] = None, 
                   team: Optional[str] = None, position: Optional[str] = None, 
                   active: bool = True, visualization_settings: Optional[Dict] = None):
        """Add a player to the roster"""
        self.roster[name] = {
            "jersey_number": jersey_number,
            "team": team,
            "position": position,
            "active": active
        }
        if visualization_settings:
            self.roster[name]["visualization_settings"] = visualization_settings
        self.save_roster()
    
    def update_player(self, name: str, **kwargs):
        """Update player information"""
        if name in self.roster:
            self.roster[name].update(kwargs)
            self.save_roster()
    
    def delete_player(self, name: str):
        """Delete a player from the roster"""
        if name in self.roster:
            del self.roster[name]
            # Also remove from video links
            videos = self.roster.get('videos', {})
            for video_name in list(videos.keys()):
                if name in videos[video_name]:
                    videos[video_name].remove(name)
                    if not videos[video_name]:  # Remove empty video entries
                        del videos[video_name]
            self.save_roster()
            return True
        return False

