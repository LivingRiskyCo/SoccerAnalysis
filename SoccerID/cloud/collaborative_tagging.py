"""
Collaborative Tagging Module
Multiple users can tag players and events collaboratively
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict

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

logger = get_logger("collaborative_tagging")


class CollaborativeTagging:
    """
    Collaborative tagging system for multiple users
    """
    
    def __init__(self, tags_file: str = "collaborative_tags.json"):
        """
        Initialize collaborative tagging
        
        Args:
            tags_file: Path to tags storage file
        """
        self.tags_file = tags_file
        self.tags = defaultdict(list)  # project_id -> [tags]
        self.load_tags()
    
    def add_tag(self,
                project_id: str,
                user_email: str,
                tag_type: str,
                frame_num: int,
                track_id: Optional[int] = None,
                player_name: Optional[str] = None,
                event_type: Optional[str] = None,
                metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a collaborative tag
        
        Args:
            project_id: Project identifier
            user_email: User who created the tag
            tag_type: Type of tag ("player", "event", "annotation")
            frame_num: Frame number
            track_id: Optional track ID
            player_name: Optional player name
            event_type: Optional event type
            metadata: Optional additional metadata
            
        Returns:
            Tag ID
        """
        import uuid
        tag_id = str(uuid.uuid4())
        
        tag = {
            'tag_id': tag_id,
            'user_email': user_email,
            'tag_type': tag_type,
            'frame_num': frame_num,
            'track_id': track_id,
            'player_name': player_name,
            'event_type': event_type,
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'votes': {},  # user_email -> vote (upvote/downvote)
            'comments': []  # List of comments
        }
        
        self.tags[project_id].append(tag)
        self.save_tags()
        
        logger.info(f"Added tag {tag_id} by {user_email} on project {project_id}")
        return tag_id
    
    def update_tag(self,
                  project_id: str,
                  tag_id: str,
                  user_email: str,
                  updates: Dict[str, Any]) -> bool:
        """
        Update an existing tag
        
        Args:
            project_id: Project identifier
            tag_id: Tag identifier
            user_email: User making the update
            updates: Dictionary of fields to update
            
        Returns:
            True if successful
        """
        for tag in self.tags[project_id]:
            if tag['tag_id'] == tag_id:
                # Check permission (simplified - would need proper permission checking)
                if tag['user_email'] == user_email or updates.get('force', False):
                    tag.update(updates)
                    tag['updated_at'] = datetime.now().isoformat()
                    tag['last_updated_by'] = user_email
                    self.save_tags()
                    logger.info(f"Updated tag {tag_id} by {user_email}")
                    return True
        
        return False
    
    def delete_tag(self, project_id: str, tag_id: str, user_email: str) -> bool:
        """Delete a tag"""
        original_count = len(self.tags[project_id])
        self.tags[project_id] = [
            tag for tag in self.tags[project_id]
            if not (tag['tag_id'] == tag_id and tag['user_email'] == user_email)
        ]
        
        if len(self.tags[project_id]) < original_count:
            self.save_tags()
            logger.info(f"Deleted tag {tag_id} by {user_email}")
            return True
        
        return False
    
    def vote_tag(self,
                project_id: str,
                tag_id: str,
                user_email: str,
                vote: str) -> bool:
        """
        Vote on a tag (upvote/downvote)
        
        Args:
            project_id: Project identifier
            tag_id: Tag identifier
            user_email: User voting
            vote: "upvote" or "downvote"
            
        Returns:
            True if successful
        """
        for tag in self.tags[project_id]:
            if tag['tag_id'] == tag_id:
                tag['votes'][user_email] = vote
                tag['updated_at'] = datetime.now().isoformat()
                self.save_tags()
                logger.info(f"Voted {vote} on tag {tag_id} by {user_email}")
                return True
        
        return False
    
    def add_comment(self,
                   project_id: str,
                   tag_id: str,
                   user_email: str,
                   comment: str) -> bool:
        """Add a comment to a tag"""
        for tag in self.tags[project_id]:
            if tag['tag_id'] == tag_id:
                tag['comments'].append({
                    'user_email': user_email,
                    'comment': comment,
                    'created_at': datetime.now().isoformat()
                })
                tag['updated_at'] = datetime.now().isoformat()
                self.save_tags()
                logger.info(f"Added comment to tag {tag_id} by {user_email}")
                return True
        
        return False
    
    def get_tags(self,
                project_id: str,
                tag_type: Optional[str] = None,
                user_email: Optional[str] = None,
                frame_range: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Get tags for a project with optional filters
        
        Args:
            project_id: Project identifier
            tag_type: Filter by tag type
            user_email: Filter by user
            frame_range: Filter by frame range (min_frame, max_frame)
            
        Returns:
            List of tags
        """
        if project_id not in self.tags:
            return []
        
        tags = self.tags[project_id]
        
        # Apply filters
        if tag_type:
            tags = [t for t in tags if t['tag_type'] == tag_type]
        
        if user_email:
            tags = [t for t in tags if t['user_email'] == user_email]
        
        if frame_range:
            min_frame, max_frame = frame_range
            tags = [t for t in tags if min_frame <= t['frame_num'] <= max_frame]
        
        return tags
    
    def get_tag_statistics(self, project_id: str) -> Dict[str, Any]:
        """Get statistics about tags for a project"""
        if project_id not in self.tags:
            return {}
        
        tags = self.tags[project_id]
        
        stats = {
            'total_tags': len(tags),
            'by_type': defaultdict(int),
            'by_user': defaultdict(int),
            'total_votes': 0,
            'total_comments': 0
        }
        
        for tag in tags:
            stats['by_type'][tag['tag_type']] += 1
            stats['by_user'][tag['user_email']] += 1
            stats['total_votes'] += len(tag['votes'])
            stats['total_comments'] += len(tag['comments'])
        
        return dict(stats)
    
    def save_tags(self):
        """Save tags to file"""
        try:
            with open(self.tags_file, 'w') as f:
                json.dump(dict(self.tags), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save tags: {e}")
    
    def load_tags(self):
        """Load tags from file"""
        if not os.path.exists(self.tags_file):
            return
        
        try:
            with open(self.tags_file, 'r') as f:
                loaded = json.load(f)
                self.tags = defaultdict(list, loaded)
            logger.info(f"Loaded tags for {len(self.tags)} projects")
        except Exception as e:
            logger.error(f"Failed to load tags: {e}")

