"""
Shared state module for communication between analysis thread and GUI
"""

# Global shared state for dynamic settings
_current_dynamic_settings = None

# Live viewer controls window reference
_live_viewer_controls = None

# Player corrections: {track_id: correct_player_name}
pending_corrections = {}

# Player conflicts: {player_name: [list of track_ids that claim this player]}
player_conflicts = {}  # {player_name: {'tracks': [track_id1, track_id2, ...], 'frame': frame_num, 'resolved': bool}}

# Breadcrumbs: Track preferences learned from user corrections
# {player_name: preferred_track_id} - stores which track a player prefers to be on
player_track_breadcrumbs = {}  # {player_name: {'preferred_track': track_id, 'confidence': float, 'frames_seen': int}}

# Track jump requests: {track_id: {'frame': frame_num, 'player': player_name, 'confirmed': bool}}
# Used to jump to a specific track during analysis for user confirmation
track_jump_requests = {}  # {track_id: {'frame': int, 'player': str, 'confirmed': bool, 'timestamp': float}}

# Locked routes: Early-frame track assignments that are "locked" as the correct path
# {player_name: {'track_id': int, 'frame': int, 'confidence': 1.0}} - locked routes from early frames
locked_routes = {}  # {player_name: {'track_id': int, 'frame': int, 'confidence': 1.0, 'locked': True}}

# Analysis stop flag: Set to True to request graceful termination of analysis
_analysis_stop_requested = False

# Current track assignments: {track_id: player_name} - updated by analysis
current_track_assignments = {}  # {track_id: player_name}

# Track frame and bbox information: {track_id: {'frame': frame_num, 'bbox': [x1, y1, x2, y2], 'team': team, 'jersey': jersey}}
# Used for creating anchor frames during conflict resolution
track_frame_info = {}  # {track_id: {'frame': int, 'bbox': list, 'team': str, 'jersey': str}}

# Team switch detections: Detected team switches awaiting confirmation
# [{player_name, from_team, to_team, frame, confidence, jersey_number, requires_confirmation}]
pending_team_switches = []

# Confirmed team switches: Team switches confirmed by user or auto-approved
# [{player_name, from_team, to_team, frame, jersey_number, timestamp}]
confirmed_team_switches = []

# Game mode validation errors: Validation errors detected in game mode
# [{player_name, error, frame, jersey_number, team, timestamp}]
validation_errors = []

# Game mode validation warnings: Non-critical warnings in game mode
# [{player_name, warning, frame, jersey_number, team, timestamp}]
validation_warnings = []

# Locked jersey+team combinations for game mode
# {player_name: {'jersey_number': str, 'team': str, 'locked_at_frame': int}}
locked_player_uniforms = {}

# Progress tracking for analysis
# Updated by analysis thread, read by GUI
_analysis_progress = {
    'current': 0,
    'total': 0,
    'status': '',
    'details': '',
    'phase': '',
    'is_running': False
}

def set_dynamic_settings(settings):
    """Set the current dynamic settings object"""
    global _current_dynamic_settings
    _current_dynamic_settings = settings

def get_dynamic_settings():
    """Get the current dynamic settings object"""
    global _current_dynamic_settings
    return _current_dynamic_settings

def clear_dynamic_settings():
    """Clear the dynamic settings"""
    global _current_dynamic_settings
    _current_dynamic_settings = None

def get_pending_corrections():
    """Get pending player corrections"""
    global pending_corrections
    return pending_corrections.copy()

def clear_pending_corrections():
    """Clear pending corrections"""
    global pending_corrections
    pending_corrections = {}

def apply_player_correction(track_id, correct_player):
    """Apply a player correction (called from GUI)"""
    global pending_corrections
    pending_corrections[track_id] = correct_player
    return True

def set_live_viewer_controls(controls):
    """Set the live viewer controls window reference"""
    global _live_viewer_controls
    _live_viewer_controls = controls

def get_live_viewer_controls():
    """Get the live viewer controls window reference"""
    global _live_viewer_controls
    return _live_viewer_controls

def report_player_conflict(player_name, assigned_track, conflicting_track, frame_num):
    """Report a player conflict (same player on multiple tracks)"""
    global player_conflicts
    if player_name not in player_conflicts:
        player_conflicts[player_name] = {
            'tracks': [],
            'frame': frame_num,
            'resolved': False
        }
    # Add tracks if not already present
    if assigned_track not in player_conflicts[player_name]['tracks']:
        player_conflicts[player_name]['tracks'].append(assigned_track)
    if conflicting_track not in player_conflicts[player_name]['tracks']:
        player_conflicts[player_name]['tracks'].append(conflicting_track)
    # Update frame to most recent
    player_conflicts[player_name]['frame'] = max(player_conflicts[player_name]['frame'], frame_num)

def get_player_conflicts():
    """Get unresolved player conflicts"""
    global player_conflicts
    unresolved = {k: v for k, v in player_conflicts.items() if not v.get('resolved', False)}
    return unresolved.copy()

def resolve_player_conflict(player_name, correct_track_id):
    """Resolve a player conflict by choosing the correct track"""
    global player_conflicts, pending_corrections
    if player_name in player_conflicts:
        # Mark conflict as resolved
        player_conflicts[player_name]['resolved'] = True
        # For all other tracks claiming this player, clear their assignment
        for track_id in player_conflicts[player_name]['tracks']:
            if track_id != correct_track_id:
                # Set correction to clear/remove this player from other tracks
                pending_corrections[track_id] = None  # None means "unassign this player"
        # Ensure correct track has the player assigned (if not already set)
        if correct_track_id not in pending_corrections or pending_corrections[correct_track_id] != player_name:
            pending_corrections[correct_track_id] = player_name
        
        # BREADCRUMB: Store this as a track preference for future guidance
        set_player_track_breadcrumb(player_name, correct_track_id, confidence=1.0)
        
        return True
    return False

def clear_live_viewer_controls():
    """Clear the live viewer controls reference"""
    global _live_viewer_controls
    _live_viewer_controls = None

def set_player_track_breadcrumb(player_name, preferred_track_id, confidence=1.0):
    """Set a breadcrumb (track preference) for a player"""
    global player_track_breadcrumbs
    if player_name not in player_track_breadcrumbs:
        player_track_breadcrumbs[player_name] = {
            'preferred_track': preferred_track_id,
            'confidence': confidence,
            'frames_seen': 1
        }
    else:
        # Update existing breadcrumb (increase confidence if same track, reset if different)
        existing = player_track_breadcrumbs[player_name]
        if existing['preferred_track'] == preferred_track_id:
            # Same track - increase confidence and frame count
            existing['confidence'] = min(1.0, existing['confidence'] + 0.1)
            existing['frames_seen'] += 1
        else:
            # Different track - user changed their mind, update it
            existing['preferred_track'] = preferred_track_id
            existing['confidence'] = confidence
            existing['frames_seen'] = 1

def get_player_track_breadcrumb(player_name):
    """Get the preferred track for a player (breadcrumb)"""
    global player_track_breadcrumbs
    if player_name in player_track_breadcrumbs:
        return player_track_breadcrumbs[player_name]
    return None

def get_track_breadcrumb_boost(player_name, track_id):
    """Get similarity boost if this track matches the player's breadcrumb"""
    breadcrumb = get_player_track_breadcrumb(player_name)
    if breadcrumb and breadcrumb['preferred_track'] == track_id:
        # Boost based on confidence (0.05 to 0.15 boost)
        return 0.05 + (breadcrumb['confidence'] * 0.10)
    return 0.0

def request_track_jump(track_id, frame_num, player_name=None):
    """Request to jump to a specific track during analysis"""
    global track_jump_requests
    import time
    track_jump_requests[track_id] = {
        'frame': frame_num,
        'player': player_name,
        'confirmed': False,
        'timestamp': time.time()
    }
    return True

def get_track_jump_requests():
    """Get pending track jump requests"""
    global track_jump_requests
    # Remove old requests (older than 60 seconds)
    import time
    current_time = time.time()
    track_jump_requests = {k: v for k, v in track_jump_requests.items() 
                          if current_time - v['timestamp'] < 60}
    return track_jump_requests.copy()

def confirm_track_jump(track_id, player_name):
    """Confirm a track jump and set breadcrumb"""
    global track_jump_requests
    if track_id in track_jump_requests:
        track_jump_requests[track_id]['confirmed'] = True
        if player_name:
            # Set breadcrumb for this player on this track
            set_player_track_breadcrumb(player_name, track_id, confidence=1.0)
        # Remove after confirmation
        del track_jump_requests[track_id]
        return True
    return False

def clear_track_jump_requests():
    """Clear all track jump requests"""
    global track_jump_requests
    track_jump_requests = {}

def lock_early_route(player_name, track_id, frame_num, early_frame_threshold=1000, force_lock=False):
    """
    Lock a route when a player is tagged in early frames or from anchor frames.
    Early tags (first 1000 frames) or anchor frames (any frame) are considered the "correct" path with confidence 1.0.
    
    Args:
        player_name: Player name
        track_id: Track ID this player is assigned to
        frame_num: Frame number where assignment occurred
        early_frame_threshold: Frame threshold for "early" frames (default: 1000)
        force_lock: If True, lock route regardless of frame number (for anchor frames)
    
    Returns:
        True if route was newly locked, False if already locked or frame is too late
    """
    global locked_routes
    if force_lock or frame_num <= early_frame_threshold:
        # Check if this route is already locked (same player and track)
        if player_name in locked_routes:
            existing = locked_routes[player_name]
            if existing['track_id'] == track_id and existing.get('locked', False):
                # Already locked to this track - don't spam
                return False
        
        # This is a NEW assignment - lock it as the correct route
        locked_routes[player_name] = {
            'track_id': track_id,
            'frame': frame_num,
            'confidence': 1.0,
            'locked': True
        }
        # Also set as breadcrumb with maximum confidence
        set_player_track_breadcrumb(player_name, track_id, confidence=1.0)
        return True
    return False

def get_locked_route(player_name):
    """Get the locked route for a player (if exists)"""
    global locked_routes
    if player_name in locked_routes:
        return locked_routes[player_name]
    return None

def get_locked_route_boost(player_name, track_id):
    """
    Get similarity boost if this track matches the player's locked route.
    Locked routes have maximum confidence (1.0) and provide strong guidance.
    
    Returns:
        Boost value (0.15 to 0.25) if track matches locked route, 0.0 otherwise
    """
    locked_route = get_locked_route(player_name)
    if locked_route and locked_route['track_id'] == track_id and locked_route.get('locked', False):
        # Locked route match - provide strong boost (0.20 to 0.25)
        # This ensures locked routes are strongly preferred
        return 0.20 + (locked_route['confidence'] * 0.05)  # 0.20 to 0.25 boost
    return 0.0

def is_route_locked(player_name, track_id):
    """Check if a specific player-track combination is locked"""
    locked_route = get_locked_route(player_name)
    if locked_route and locked_route['track_id'] == track_id:
        return locked_route.get('locked', False)
    return False

def request_analysis_stop():
    """Request that the analysis stop gracefully"""
    global _analysis_stop_requested
    _analysis_stop_requested = True

def clear_analysis_stop():
    """Clear the stop request flag"""
    global _analysis_stop_requested
    _analysis_stop_requested = False

def is_analysis_stop_requested():
    """Check if analysis stop has been requested"""
    global _analysis_stop_requested
    return _analysis_stop_requested

def update_track_assignment(track_id, player_name, frame_num=None, bbox=None, team=None, jersey=None):
    """Update current track assignment (called from analysis)
    
    Args:
        track_id: Track ID
        player_name: Player name assigned to track
        frame_num: Current frame number (optional, for anchor frame creation)
        bbox: Bounding box [x1, y1, x2, y2] (optional, for anchor frame creation)
        team: Team name (optional, for anchor frame creation)
        jersey: Jersey number (optional, for anchor frame creation)
    """
    global current_track_assignments, track_frame_info
    current_track_assignments[track_id] = player_name
    
    # Store frame and bbox info for anchor frame creation
    if frame_num is not None:
        track_frame_info[track_id] = {
            'frame': frame_num,
            'bbox': bbox,
            'team': team,
            'jersey': jersey,
            'player_name': player_name
        }
    
    # Notify live viewer controls if available
    controls = get_live_viewer_controls()
    if controls and hasattr(controls, 'update_track_assignment'):
        try:
            controls.update_track_assignment(track_id, player_name)
        except:
            pass  # Silently handle errors (GUI might be closed)

def get_current_track_assignments():
    """Get current track assignments"""
    global current_track_assignments
    return current_track_assignments.copy()

def clear_track_assignments():
    """Clear all track assignments"""
    global current_track_assignments, track_frame_info
    current_track_assignments = {}
    track_frame_info = {}

def get_track_frame_info(track_id):
    """Get frame and bbox information for a track (for anchor frame creation)"""
    global track_frame_info
    return track_frame_info.get(track_id)

def report_team_switch(player_name, from_team, to_team, frame_num, jersey_number=None, confidence=0.0, requires_confirmation=True):
    """
    Report a detected team switch
    
    Args:
        player_name: Player name
        from_team: Previous team
        to_team: New team
        frame_num: Frame number where switch detected
        jersey_number: Jersey number (optional)
        confidence: Detection confidence
        requires_confirmation: Whether user confirmation is needed
    """
    global pending_team_switches
    
    # Check if this switch is already pending
    for switch in pending_team_switches:
        if (switch['player_name'] == player_name and 
            switch['from_team'] == from_team and 
            switch['to_team'] == to_team):
            # Already pending - don't add duplicate
            return False
    
    # Add to pending switches
    switch_entry = {
        'player_name': player_name,
        'from_team': from_team,
        'to_team': to_team,
        'frame': frame_num,
        'jersey_number': jersey_number,
        'confidence': confidence,
        'requires_confirmation': requires_confirmation
    }
    pending_team_switches.append(switch_entry)
    return True

def get_pending_team_switches():
    """Get pending team switches"""
    global pending_team_switches
    return pending_team_switches.copy()

def confirm_team_switch(player_name, from_team, to_team, frame_num, jersey_number=None):
    """
    Confirm a team switch (user approved or auto-approved)
    
    Args:
        player_name: Player name
        from_team: Previous team
        to_team: New team
        frame_num: Frame number
        jersey_number: Jersey number (optional)
    """
    global pending_team_switches, confirmed_team_switches
    
    # Remove from pending
    pending_team_switches = [s for s in pending_team_switches 
                            if not (s['player_name'] == player_name and 
                                   s['from_team'] == from_team and 
                                   s['to_team'] == to_team)]
    
    # Add to confirmed
    import datetime
    confirmed_entry = {
        'player_name': player_name,
        'from_team': from_team,
        'to_team': to_team,
        'frame': frame_num,
        'jersey_number': jersey_number,
        'timestamp': datetime.datetime.now().isoformat()
    }
    confirmed_team_switches.append(confirmed_entry)
    return True

def reject_team_switch(player_name, from_team, to_team):
    """
    Reject a pending team switch
    
    Args:
        player_name: Player name
        from_team: Previous team
        to_team: New team
    """
    global pending_team_switches
    
    # Remove from pending
    pending_team_switches = [s for s in pending_team_switches 
                            if not (s['player_name'] == player_name and 
                                   s['from_team'] == from_team and 
                                   s['to_team'] == to_team)]
    return True

def get_confirmed_team_switches():
    """Get confirmed team switches"""
    global confirmed_team_switches
    return confirmed_team_switches.copy()

def clear_team_switches():
    """Clear all team switch data"""
    global pending_team_switches, confirmed_team_switches
    pending_team_switches = []
    confirmed_team_switches = []

def report_validation_error(player_name, error, frame_num, jersey_number=None, team=None):
    """
    Report a game mode validation error
    
    Args:
        player_name: Player name
        error: Error message
        frame_num: Frame number where error occurred
        jersey_number: Jersey number (optional)
        team: Team (optional)
    """
    global validation_errors
    
    # Check if this error is already reported
    for err in validation_errors:
        if (err['player_name'] == player_name and 
            err['error'] == error and 
            abs(err['frame'] - frame_num) < 30):  # Within 30 frames (1 second)
            # Already reported recently - don't duplicate
            return False
    
    # Add to validation errors
    import datetime
    error_entry = {
        'player_name': player_name,
        'error': error,
        'frame': frame_num,
        'jersey_number': jersey_number,
        'team': team,
        'timestamp': datetime.datetime.now().isoformat()
    }
    validation_errors.append(error_entry)
    return True

def report_validation_warning(player_name, warning, frame_num, jersey_number=None, team=None):
    """
    Report a game mode validation warning
    
    Args:
        player_name: Player name
        warning: Warning message
        frame_num: Frame number where warning occurred
        jersey_number: Jersey number (optional)
        team: Team (optional)
    """
    global validation_warnings
    
    # Check if this warning is already reported
    for warn in validation_warnings:
        if (warn['player_name'] == player_name and 
            warn['warning'] == warning and 
            abs(warn['frame'] - frame_num) < 30):  # Within 30 frames (1 second)
            # Already reported recently - don't duplicate
            return False
    
    # Add to validation warnings
    import datetime
    warning_entry = {
        'player_name': player_name,
        'warning': warning,
        'frame': frame_num,
        'jersey_number': jersey_number,
        'team': team,
        'timestamp': datetime.datetime.now().isoformat()
    }
    validation_warnings.append(warning_entry)
    return True

def get_validation_errors():
    """Get all validation errors"""
    global validation_errors
    return validation_errors.copy()

def get_validation_warnings():
    """Get all validation warnings"""
    global validation_warnings
    return validation_warnings.copy()

def clear_validation_errors():
    """Clear all validation errors and warnings"""
    global validation_errors, validation_warnings
    validation_errors = []
    validation_warnings = []

def lock_player_uniform(player_name, jersey_number, team, frame_num):
    """
    Lock a player's jersey+team combination for game mode
    This prevents any changes during the game
    
    Args:
        player_name: Player name
        jersey_number: Jersey number
        team: Team
        frame_num: Frame number where lock occurred
    
    Returns:
        True if newly locked, False if already locked
    """
    global locked_player_uniforms
    
    if player_name in locked_player_uniforms:
        # Already locked - check if it's the same combination
        existing = locked_player_uniforms[player_name]
        if (existing['jersey_number'] == jersey_number and 
            existing['team'] == team):
            # Same combination - already locked
            return False
        else:
            # Different combination - this is an error!
            # Don't update the lock, report this elsewhere
            return False
    
    # Lock this combination
    locked_player_uniforms[player_name] = {
        'jersey_number': jersey_number,
        'team': team,
        'locked_at_frame': frame_num
    }
    return True

def get_locked_uniform(player_name):
    """
    Get the locked uniform for a player
    
    Args:
        player_name: Player name
    
    Returns:
        Dict with jersey_number, team, locked_at_frame or None if not locked
    """
    global locked_player_uniforms
    return locked_player_uniforms.get(player_name)

def is_uniform_locked(player_name):
    """Check if a player's uniform is locked"""
    global locked_player_uniforms
    return player_name in locked_player_uniforms

def validate_locked_uniform(player_name, jersey_number, team):
    """
    Validate that a player's current assignment matches their locked uniform
    
    Args:
        player_name: Player name
        jersey_number: Current jersey number
        team: Current team
    
    Returns:
        dict with:
            - valid: True/False
            - error: Error message (if mismatch)
    """
    locked = get_locked_uniform(player_name)
    if not locked:
        # Not locked - this is valid (will be locked on first detection)
        return {'valid': True}
    
    errors = []
    
    # Check jersey number
    if locked['jersey_number'] and jersey_number:
        if str(locked['jersey_number']).strip() != str(jersey_number).strip():
            errors.append(f"Jersey # mismatch: expected #{locked['jersey_number']}, got #{jersey_number}")
    
    # Check team
    if locked['team'] and team:
        if locked['team'] != team:
            errors.append(f"Team mismatch: expected {locked['team']}, got {team}")
    
    if errors:
        return {
            'valid': False,
            'error': f"{player_name}: {' | '.join(errors)}"
        }
    else:
        return {'valid': True}

def clear_locked_uniforms():
    """Clear all locked uniforms"""
    global locked_player_uniforms
    locked_player_uniforms = {}

def update_analysis_progress(current, total, status="", details="", phase=""):
    """
    Update analysis progress (called from analysis thread)
    
    Args:
        current: Current frame/item number
        total: Total frames/items
        status: Status message
        details: Detailed status
        phase: Processing phase (e.g., "Detection", "Tracking", "Export")
    """
    global _analysis_progress
    _analysis_progress = {
        'current': current,
        'total': total,
        'status': status,
        'details': details,
        'phase': phase,
        'is_running': True
    }

def get_analysis_progress():
    """Get current analysis progress (called from GUI)"""
    global _analysis_progress
    return _analysis_progress.copy()

def clear_analysis_progress():
    """Clear analysis progress"""
    global _analysis_progress
    _analysis_progress = {
        'current': 0,
        'total': 0,
        'status': '',
        'details': '',
        'phase': '',
        'is_running': False
    }

