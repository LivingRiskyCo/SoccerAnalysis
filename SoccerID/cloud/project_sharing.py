"""
Project Sharing Module
Share projects with team members
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

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

logger = get_logger("project_sharing")


class SharePermission(Enum):
    """Share permission levels"""
    VIEW = "view"  # Can view only
    COMMENT = "comment"  # Can view and comment
    EDIT = "edit"  # Can view, comment, and edit
    ADMIN = "admin"  # Full access


class ProjectSharing:
    """
    Manage project sharing with team members
    """
    
    def __init__(self, sharing_file: str = "project_sharing.json"):
        """
        Initialize project sharing
        
        Args:
            sharing_file: Path to sharing configuration file
        """
        self.sharing_file = sharing_file
        self.shared_projects = {}  # project_id -> sharing info
        self.load_sharing()
    
    def share_project(self,
                     project_id: str,
                     project_name: str,
                     user_email: str,
                     permission: SharePermission = SharePermission.VIEW,
                     message: Optional[str] = None) -> bool:
        """
        Share a project with a user
        
        Args:
            project_id: Project identifier
            project_name: Project name
            user_email: Email of user to share with
            permission: Permission level
            message: Optional message
            
        Returns:
            True if successful
        """
        if project_id not in self.shared_projects:
            self.shared_projects[project_id] = {
                'project_name': project_name,
                'shared_with': [],
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
        
        # Check if already shared
        for share in self.shared_projects[project_id]['shared_with']:
            if share['email'] == user_email:
                # Update permission
                share['permission'] = permission.value
                share['updated_at'] = datetime.now().isoformat()
                self.save_sharing()
                logger.info(f"Updated sharing for {user_email} on project {project_name}")
                return True
        
        # Add new share
        self.shared_projects[project_id]['shared_with'].append({
            'email': user_email,
            'permission': permission.value,
            'message': message,
            'shared_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })
        
        self.shared_projects[project_id]['updated_at'] = datetime.now().isoformat()
        self.save_sharing()
        
        logger.info(f"Shared project {project_name} with {user_email} ({permission.value})")
        return True
    
    def unshare_project(self, project_id: str, user_email: str) -> bool:
        """Remove sharing for a user"""
        if project_id not in self.shared_projects:
            return False
        
        shared_with = self.shared_projects[project_id]['shared_with']
        original_count = len(shared_with)
        self.shared_projects[project_id]['shared_with'] = [
            s for s in shared_with if s['email'] != user_email
        ]
        
        if len(self.shared_projects[project_id]['shared_with']) < original_count:
            self.save_sharing()
            logger.info(f"Unshared project {project_id} from {user_email}")
            return True
        
        return False
    
    def get_shared_projects(self, user_email: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of shared projects
        
        Args:
            user_email: Optional filter by user email
            
        Returns:
            List of shared project information
        """
        if user_email:
            # Filter projects shared with this user
            result = []
            for project_id, project_info in self.shared_projects.items():
                for share in project_info['shared_with']:
                    if share['email'] == user_email:
                        result.append({
                            'project_id': project_id,
                            'project_name': project_info['project_name'],
                            'permission': share['permission'],
                            'shared_at': share['shared_at']
                        })
            return result
        else:
            # Return all shared projects
            return [
                {
                    'project_id': project_id,
                    'project_name': info['project_name'],
                    'shared_with_count': len(info['shared_with']),
                    'created_at': info['created_at']
                }
                for project_id, info in self.shared_projects.items()
            ]
    
    def get_project_shares(self, project_id: str) -> List[Dict[str, Any]]:
        """Get list of users a project is shared with"""
        if project_id not in self.shared_projects:
            return []
        
        return self.shared_projects[project_id]['shared_with'].copy()
    
    def save_sharing(self):
        """Save sharing configuration"""
        try:
            with open(self.sharing_file, 'w') as f:
                json.dump(self.shared_projects, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sharing: {e}")
    
    def load_sharing(self):
        """Load sharing configuration"""
        if not os.path.exists(self.sharing_file):
            return
        
        try:
            with open(self.sharing_file, 'r') as f:
                self.shared_projects = json.load(f)
            logger.info(f"Loaded sharing for {len(self.shared_projects)} projects")
        except Exception as e:
            logger.error(f"Failed to load sharing: {e}")

