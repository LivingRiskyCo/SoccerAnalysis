"""
Cloud Integration Module
Upload videos, process in cloud, share projects, collaborative tagging
"""

from .cloud_storage import CloudStorage
from .cloud_processor import CloudProcessor
from .project_sharing import ProjectSharing
from .collaborative_tagging import CollaborativeTagging

__all__ = ['CloudStorage', 'CloudProcessor', 'ProjectSharing', 'CollaborativeTagging']

