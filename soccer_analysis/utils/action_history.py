"""
Undo/Redo System with Action History
Tracks all user actions for full undo/redo capability
"""

from typing import Any, Optional, Callable, Dict, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ActionType(Enum):
    """Types of actions that can be undone"""
    SET_PLAYER_NAME = "set_player_name"
    SET_TEAM_COLOR = "set_team_color"
    SET_BALL_COLOR = "set_ball_color"
    CALIBRATE_FIELD = "calibrate_field"
    TAG_PLAYER = "tag_player"
    REMOVE_TAG = "remove_tag"
    MERGE_TRACKS = "merge_tracks"
    SPLIT_TRACK = "split_track"
    CHANGE_SETTING = "change_setting"
    DELETE_PLAYER = "delete_player"
    ADD_PLAYER = "add_player"
    MODIFY_GALLERY = "modify_gallery"
    CUSTOM = "custom"


@dataclass
class Action:
    """Represents a single undoable action"""
    action_type: ActionType
    timestamp: datetime
    description: str
    undo_func: Callable[[], None]
    redo_func: Callable[[], None]
    data: Dict[str, Any] = field(default_factory=dict)
    
    def execute_undo(self):
        """Execute undo for this action"""
        try:
            self.undo_func()
        except Exception as e:
            print(f"Error undoing action {self.description}: {e}")
    
    def execute_redo(self):
        """Execute redo for this action"""
        try:
            self.redo_func()
        except Exception as e:
            print(f"Error redoing action {self.description}: {e}")


class ActionHistory:
    """
    Manages undo/redo history for user actions
    
    Features:
    - Unlimited undo/redo (within memory limits)
    - Action grouping
    - History navigation
    - Action descriptions
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize action history
        
        Args:
            max_history: Maximum number of actions to keep (0 = unlimited)
        """
        self.max_history = max_history
        self.history: List[Action] = []
        self.current_index = -1  # -1 means at end of history
        self.grouping = False
        self.current_group: List[Action] = []
    
    def add_action(self, action_type: ActionType, description: str,
                   undo_func: Callable[[], None], redo_func: Callable[[], None],
                   data: Optional[Dict[str, Any]] = None):
        """
        Add an action to history
        
        Args:
            action_type: Type of action
            description: Human-readable description
            undo_func: Function to call to undo this action
            redo_func: Function to call to redo this action
            data: Optional data associated with action
        """
        action = Action(
            action_type=action_type,
            timestamp=datetime.now(),
            description=description,
            undo_func=undo_func,
            redo_func=redo_func,
            data=data or {}
        )
        
        if self.grouping:
            self.current_group.append(action)
        else:
            # Remove any actions after current index (if we're not at the end)
            if self.current_index < len(self.history) - 1:
                self.history = self.history[:self.current_index + 1]
            
            self.history.append(action)
            self.current_index = len(self.history) - 1
            
            # Limit history size
            if self.max_history > 0 and len(self.history) > self.max_history:
                self.history.pop(0)
                self.current_index -= 1
    
    def start_group(self):
        """Start grouping actions together"""
        self.grouping = True
        self.current_group = []
    
    def end_group(self, description: str = "Grouped actions"):
        """End grouping and add as single action"""
        if not self.grouping or not self.current_group:
            self.grouping = False
            return
        
        if len(self.current_group) == 1:
            # Single action, add normally
            action = self.current_group[0]
            self.add_action(
                action.action_type,
                action.description,
                action.undo_func,
                action.redo_func,
                action.data
            )
        else:
            # Multiple actions, create grouped undo/redo
            group_actions = self.current_group.copy()
            
            def group_undo():
                # Undo in reverse order
                for action in reversed(group_actions):
                    action.execute_undo()
            
            def group_redo():
                # Redo in forward order
                for action in group_actions:
                    action.execute_redo()
            
            self.add_action(
                ActionType.CUSTOM,
                description,
                group_undo,
                group_redo
            )
        
        self.grouping = False
        self.current_group = []
    
    def can_undo(self) -> bool:
        """Check if undo is possible"""
        return self.current_index >= 0
    
    def can_redo(self) -> bool:
        """Check if redo is possible"""
        return self.current_index < len(self.history) - 1
    
    def undo(self) -> Optional[str]:
        """
        Undo the last action
        
        Returns:
            Description of undone action, or None if nothing to undo
        """
        if not self.can_undo():
            return None
        
        action = self.history[self.current_index]
        action.execute_undo()
        self.current_index -= 1
        
        return action.description
    
    def redo(self) -> Optional[str]:
        """
        Redo the next action
        
        Returns:
            Description of redone action, or None if nothing to redo
        """
        if not self.can_redo():
            return None
        
        self.current_index += 1
        action = self.history[self.current_index]
        action.execute_redo()
        
        return action.description
    
    def get_undo_description(self) -> Optional[str]:
        """Get description of action that would be undone"""
        if not self.can_undo():
            return None
        return self.history[self.current_index].description
    
    def get_redo_description(self) -> Optional[str]:
        """Get description of action that would be redone"""
        if not self.can_redo():
            return None
        return self.history[self.current_index + 1].description
    
    def clear(self):
        """Clear all history"""
        self.history.clear()
        self.current_index = -1
    
    def get_history_summary(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get summary of recent history
        
        Args:
            limit: Maximum number of items to return
        
        Returns:
            List of action summaries
        """
        start = max(0, len(self.history) - limit)
        summary = []
        
        for i, action in enumerate(self.history[start:], start):
            summary.append({
                "index": i,
                "type": action.action_type.value,
                "description": action.description,
                "timestamp": action.timestamp.isoformat(),
                "is_current": i == self.current_index
            })
        
        return summary

