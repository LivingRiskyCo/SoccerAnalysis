"""
Player Profile Export
Create shareable player profiles with stats and highlights
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from player_gallery import PlayerGallery
from enhanced_stats_dashboard import EnhancedStatsDashboard
from event_tracker import EventTracker

class PlayerProfileExporter:
    def __init__(self, gallery: PlayerGallery, stats_dashboard: Optional[EnhancedStatsDashboard] = None, 
                 event_tracker: Optional[EventTracker] = None):
        self.gallery = gallery
        self.stats_dashboard = stats_dashboard
        self.event_tracker = event_tracker
    
    def export_player_profile(self, player_name: str, output_dir: str) -> tuple:
        """Export comprehensive player profile
        Returns: (json_path, html_path)
        """
        # Find player by name
        players = self.gallery.list_players()
        player_id = None
        for pid, pname in players:
            if pname == player_name:
                player_id = pid
                break
        
        if player_id:
            player = self.gallery.get_player(player_id)
        else:
            player = None
        
        # Get stats
        player_stats = self._get_player_stats(player_name, player_id if 'player_id' in locals() else None)
        
        # Get highlights
        highlights = self._get_highlights(player_name)
        
        # Get events
        events = self._get_player_events(player_name)
        
        profile = {
            "player_name": player_name,
            "jersey_number": player.jersey_number if player else None,
            "team": player.team if player else None,
            "export_date": datetime.now().isoformat(),
            "statistics": player_stats,
            "highlights": highlights,
            "events": events,
            "reference_images": self._export_reference_images(player, output_dir) if player else []
        }
        
        # Save profile JSON
        profile_path = os.path.join(output_dir, f"{player_name.replace(' ', '_')}_profile.json")
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        
        # Generate HTML report
        html_path = self._generate_html_report(profile, output_dir, player_name)
        
        return profile_path, html_path
    
    def _get_player_stats(self, player_name: str, player_id: Optional[int] = None) -> Dict:
        """Get player statistics"""
        stats = {}
        
        if self.stats_dashboard and player_id is not None:
            if player_id in self.stats_dashboard.stats:
                stats = self.stats_dashboard.stats[player_id].copy()
        
        return stats
    
    def _get_highlights(self, player_name: str) -> List[Dict]:
        """Get video highlights for player"""
        highlights = []
        
        if self.event_tracker:
            player_events = [e for e in self.event_tracker.events 
                           if e.player_name == player_name]
            
            for event in player_events:
                if event.event_type in ['goal', 'shot', 'save', 'tackle', 'pass']:
                    highlights.append({
                        "type": event.event_type,
                        "frame": event.frame_num,
                        "timestamp": event.timestamp,
                        "video": os.path.basename(event.video_path) if event.video_path else None,
                        "description": event.description
                    })
        
        return highlights
    
    def _get_player_events(self, player_name: str) -> List[Dict]:
        """Get all events for player"""
        if not self.event_tracker:
            return []
        
        events = []
        for event in self.event_tracker.get_events_for_player(player_name):
            events.append({
                "type": event.event_type,
                "frame": event.frame_num,
                "timestamp": event.timestamp,
                "team": event.team,
                "description": event.description
            })
        
        return events
    
    def _export_reference_images(self, player, output_dir: str) -> List[Dict]:
        """Export reference images for player"""
        images = []
        
        if player and player.reference_frames:
            images_dir = os.path.join(output_dir, f"{player.name.replace(' ', '_')}_images")
            os.makedirs(images_dir, exist_ok=True)
            
            for i, ref_frame in enumerate(player.reference_frames[:10]):  # Limit to 10 images
                # Store metadata about reference frames
                images.append({
                    "index": i,
                    "video": os.path.basename(ref_frame.get('video_path', '')),
                    "frame_num": ref_frame.get('frame_num'),
                    "bbox": ref_frame.get('bbox')
                })
        
        return images
    
    def _generate_html_report(self, profile: Dict, output_dir: str, player_name: str) -> str:
        """Generate HTML report for player profile"""
        html_path = os.path.join(output_dir, f"{player_name.replace(' ', '_')}_profile.html")
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Player Profile: {player_name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .section {{
            background-color: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 10px;
        }}
        .stat-item {{
            background-color: #ecf0f1;
            padding: 10px;
            border-radius: 3px;
        }}
        .stat-label {{
            font-weight: bold;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .stat-value {{
            font-size: 1.5em;
            color: #2c3e50;
            margin-top: 5px;
        }}
        .highlight {{
            background-color: #e8f5e9;
            padding: 10px;
            margin: 5px 0;
            border-left: 4px solid #4caf50;
            border-radius: 3px;
        }}
        .event {{
            background-color: #fff3e0;
            padding: 10px;
            margin: 5px 0;
            border-left: 4px solid #ff9800;
            border-radius: 3px;
        }}
        h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Player Profile: {player_name}</h1>
        <p>Jersey: {profile.get('jersey_number', 'N/A')} | Team: {profile.get('team', 'N/A')}</p>
        <p>Exported: {profile.get('export_date', 'N/A')}</p>
    </div>
    
    <div class="section">
        <h2>Statistics</h2>
        <div class="stat-grid">
"""
        
        # Add statistics
        stats = profile.get('statistics', {})
        if stats:
            for key, value in stats.items():
                if isinstance(value, (int, float)):
                    html_content += f"""
            <div class="stat-item">
                <div class="stat-label">{key.replace('_', ' ').title()}</div>
                <div class="stat-value">{value:.2f if isinstance(value, float) else value}</div>
            </div>
"""
        
        html_content += """
        </div>
    </div>
    
    <div class="section">
        <h2>Highlights</h2>
"""
        
        # Add highlights
        highlights = profile.get('highlights', [])
        if highlights:
            for highlight in highlights:
                html_content += f"""
        <div class="highlight">
            <strong>{highlight['type'].upper()}</strong> - Frame {highlight['frame']} ({highlight['timestamp']:.1f}s)
            {f"<br>{highlight['description']}" if highlight.get('description') else ''}
        </div>
"""
        else:
            html_content += "<p>No highlights available</p>"
        
        html_content += """
    </div>
    
    <div class="section">
        <h2>Events</h2>
"""
        
        # Add events
        events = profile.get('events', [])
        if events:
            for event in events:
                html_content += f"""
        <div class="event">
            <strong>{event['type'].upper()}</strong> - Frame {event['frame']} ({event['timestamp']:.1f}s)
            {f"<br>Team: {event['team']}" if event.get('team') else ''}
            {f"<br>{event['description']}" if event.get('description') else ''}
        </div>
"""
        else:
            html_content += "<p>No events recorded</p>"
        
        html_content += """
    </div>
</body>
</html>
"""
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return html_path

