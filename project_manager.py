"""
Project Manager
Save and load all project configurations (analysis settings, team colors, ball colors, 
field calibration, setup wizard data, etc.)
"""

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
from datetime import datetime


def convert_to_python_types(obj):
    """Recursively convert NumPy types to Python types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_to_python_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_python_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_python_types(item) for item in obj)
    elif isinstance(obj, set):
        return list(convert_to_python_types(item) for item in obj)
    return obj


def save_project(project_name, project_path=None, gui_instance=None):
    """
    Save all project configurations to a single project file
    
    Args:
        project_name: Name of the project
        project_path: Full path to save project file (if None, prompts for save location)
        gui_instance: SoccerAnalysisGUI instance to get current settings
    
    Returns:
        Path to saved project file, or None if cancelled
    """
    if project_path is None:
        project_path = filedialog.asksaveasfilename(
            title="Save Project",
            defaultextension=".json",
            filetypes=[("Project files", "*.json"), ("All files", "*.*")],
            initialfile=f"{project_name}.json"
        )
    
    if not project_path:
        return None
    
    try:
        project_data = {
            "project_name": project_name,
            "version": "1.0",
            
            # Analysis settings (from main GUI)
            "analysis_settings": {},
            
            # Setup wizard data
            "setup_wizard": {},
            
            # Team colors
            "team_colors": {},
            
            # Ball colors
            "ball_colors": {},
            
            # Field calibration
            "field_calibration": {},
            
            # Player names
            "player_names": {},
            "player_name_list": [],
            
            # Team switching events (for practice mode)
            "team_switch_events": []  # [{frame, player_name, from_team, to_team, jersey_number}]
        }
        
        # 1. Save ALL analysis settings from GUI
        if gui_instance:
            # Helper function to safely get GUI variable values
            def get_var(var_name, default_value):
                if hasattr(gui_instance, var_name):
                    var = getattr(gui_instance, var_name)
                    if hasattr(var, 'get'):
                        return var.get()
                return default_value
            
            project_data["analysis_settings"] = {
                # Basic file settings
                "input_file": get_var('input_file', ""),
                "output_file": get_var('output_file', ""),
                "video_type": get_var('video_type', "practice"),  # "practice" or "game"
                "dewarp_enabled": get_var('dewarp_enabled', False),
                "remove_net_enabled": get_var('remove_net_enabled', False),
                "ball_tracking_enabled": get_var('ball_tracking_enabled', True),
                "player_tracking_enabled": get_var('player_tracking_enabled', True),
                "csv_export_enabled": get_var('csv_export_enabled', True),
                "use_imperial_units": get_var('use_imperial_units', False),
                
                # Watch-only & Learning
                "watch_only": get_var('watch_only', False),
                "show_live_viewer": get_var('show_live_viewer', False),
                "focus_players_enabled": get_var('focus_players_enabled', False),
                "focused_players": getattr(gui_instance, 'focused_players', []) if hasattr(gui_instance, 'focused_players') else [],
                
                # Processing settings
                "buffer_size": get_var('buffer_size', 64),
                "batch_size": get_var('batch_size', 8),
                "use_yolo_streaming": get_var('use_yolo_streaming', False),
                
                # Ball tracking settings
                "show_ball_trail": get_var('show_ball_trail', True),
                "ball_min_radius": get_var('ball_min_radius', 5),
                "ball_max_radius": get_var('ball_max_radius', 50),
                "ball_min_size": get_var('ball_min_size', 3),
                "ball_max_size": get_var('ball_max_size', 20),
                "ball_trail_length": get_var('ball_trail_length', 20),
                "trail_length": get_var('trail_length', 20),
                "trail_buffer": get_var('trail_buffer', 20),
                
                # YOLO settings
                "yolo_confidence": get_var('yolo_confidence', 0.25),
                "yolo_iou_threshold": get_var('yolo_iou_threshold', 0.45),
                
                # Basic tracking settings
                "track_thresh": get_var('track_thresh', 0.25),
                "match_thresh": get_var('match_thresh', 0.6),
                "track_buffer": get_var('track_buffer', 50),
                "track_buffer_seconds": get_var('track_buffer_seconds', 5.0),
                "min_track_length": get_var('min_track_length', 5),
                "tracker_type": get_var('tracker_type', "deepocsort"),
                
                # Minimum detection size
                "min_bbox_area": get_var('min_bbox_area', 200),
                "min_bbox_width": get_var('min_bbox_width', 10),
                "min_bbox_height": get_var('min_bbox_height', 15),
                
                # FPS settings
                "video_fps": get_var('video_fps', 0.0),
                "output_fps": get_var('output_fps', 0.0),
                
                # Advanced tracking settings
                "temporal_smoothing": get_var('temporal_smoothing', True),
                "process_every_nth": get_var('process_every_nth', 1),
                "yolo_resolution": get_var('yolo_resolution', "full"),
                "foot_based_tracking": get_var('foot_based_tracking', True),
                "use_reid": get_var('use_reid', True),
                "reid_similarity_threshold": get_var('reid_similarity_threshold', 0.55),
                "gallery_similarity_threshold": get_var('gallery_similarity_threshold', 0.40),
                "osnet_variant": get_var('osnet_variant', "osnet_x1_0"),
                
                # Occlusion recovery
                "occlusion_recovery_seconds": get_var('occlusion_recovery_seconds', 3.0),
                "occlusion_recovery_distance": get_var('occlusion_recovery_distance', 250),
                "reid_check_interval": get_var('reid_check_interval', 30),
                "reid_confidence_threshold": get_var('reid_confidence_threshold', 0.75),
                
                # BoxMOT and GSI
                "use_boxmot_backend": get_var('use_boxmot_backend', True),
                "use_gsi": get_var('use_gsi', False),
                "gsi_interval": get_var('gsi_interval', 20),
                "gsi_tau": get_var('gsi_tau', 10.0),
                
                # Advanced tracking features (academic research)
                "use_harmonic_mean": get_var('use_harmonic_mean', True),
                "use_expansion_iou": get_var('use_expansion_iou', True),
                "enable_soccer_reid_training": get_var('enable_soccer_reid_training', False),
                "use_enhanced_kalman": get_var('use_enhanced_kalman', True),
                "use_ema_smoothing": get_var('use_ema_smoothing', True),
                "confidence_filtering": get_var('confidence_filtering', True),
                "adaptive_confidence": get_var('adaptive_confidence', True),
                "use_optical_flow": get_var('use_optical_flow', False),
                "enable_velocity_constraints": get_var('enable_velocity_constraints', True),
                "preview_max_frames": get_var('preview_max_frames', 360),
                
                # Advanced tracking options
                "track_referees": get_var('track_referees', False),
                "max_players": get_var('max_players', 12),
                "enable_substitutions": get_var('enable_substitutions', True),
                
                # Visualization - Basic
                "viz_style": get_var('viz_style', "box"),
                "viz_color_mode": get_var('viz_color_mode', "team"),
                "viz_team_colors": get_var('viz_team_colors', True),
                "show_bounding_boxes": get_var('show_bounding_boxes', True),
                "show_circles_at_feet": get_var('show_circles_at_feet', True),
                
                # Visualization - Ellipse
                "ellipse_width": get_var('ellipse_width', 20),
                "ellipse_height": get_var('ellipse_height', 12),
                "ellipse_outline_thickness": get_var('ellipse_outline_thickness', 3),
                "show_ball_possession": get_var('show_ball_possession', True),
                
                # Visualization - Feet Markers
                "feet_marker_style": get_var('feet_marker_style', "circle"),
                "feet_marker_opacity": get_var('feet_marker_opacity', 255),
                "feet_marker_enable_glow": get_var('feet_marker_enable_glow', False),
                "feet_marker_glow_intensity": get_var('feet_marker_glow_intensity', 70),
                "feet_marker_enable_shadow": get_var('feet_marker_enable_shadow', False),
                "feet_marker_shadow_offset": get_var('feet_marker_shadow_offset', 3),
                "feet_marker_shadow_opacity": get_var('feet_marker_shadow_opacity', 128),
                "feet_marker_enable_gradient": get_var('feet_marker_enable_gradient', False),
                "feet_marker_enable_pulse": get_var('feet_marker_enable_pulse', False),
                "feet_marker_pulse_speed": get_var('feet_marker_pulse_speed', 2.0),
                "feet_marker_enable_particles": get_var('feet_marker_enable_particles', False),
                "feet_marker_particle_count": get_var('feet_marker_particle_count', 5),
                "feet_marker_vertical_offset": get_var('feet_marker_vertical_offset', 50),
                "show_direction_arrow": get_var('show_direction_arrow', False),
                "show_player_trail": get_var('show_player_trail', False),
                
                # Visualization - Box
                "box_shrink_factor": get_var('box_shrink_factor', 0.10),
                "box_thickness": get_var('box_thickness', 2),
                "use_custom_box_color": get_var('use_custom_box_color', False),
                "box_color_rgb": get_var('box_color_rgb', "0,255,0"),
                "player_viz_alpha": get_var('player_viz_alpha', 255),
                
                # Visualization - Labels
                "show_player_labels": get_var('show_player_labels', True),
                "label_font_scale": get_var('label_font_scale', 0.7),
                "label_type": get_var('label_type', "full_name"),
                "label_custom_text": get_var('label_custom_text', "Player"),
                "label_font_face": get_var('label_font_face', "FONT_HERSHEY_SIMPLEX"),
                "use_custom_label_color": get_var('use_custom_label_color', False),
                "label_color_rgb": get_var('label_color_rgb', "255,255,255"),
                
                # Visualization - Predictions
                "show_predicted_boxes": get_var('show_predicted_boxes', False),
                "prediction_duration": get_var('prediction_duration', 1.5),
                "prediction_size": get_var('prediction_size', 5),
                "prediction_color_r": get_var('prediction_color_r', 255),
                "prediction_color_g": get_var('prediction_color_g', 255),
                "prediction_color_b": get_var('prediction_color_b', 0),
                "prediction_color_alpha": get_var('prediction_color_alpha', 255),
                "prediction_style": get_var('prediction_style', "dot"),
                "show_yolo_boxes": get_var('show_yolo_boxes', False),
                
                # Broadcast-level graphics
                "trajectory_smoothness": get_var('trajectory_smoothness', "bezier"),
                "player_graphics_style": get_var('player_graphics_style', "standard"),
                "use_rounded_corners": get_var('use_rounded_corners', True),
                "use_gradient_fill": get_var('use_gradient_fill', False),
                "corner_radius": get_var('corner_radius', 5),
                "show_jersey_badge": get_var('show_jersey_badge', False),
                "ball_graphics_style": get_var('ball_graphics_style', "standard"),
                
                # Statistics overlay
                "show_statistics": get_var('show_statistics', False),
                "statistics_position": get_var('statistics_position', "top_left"),
                "statistics_panel_width": get_var('statistics_panel_width', 250),
                "statistics_panel_height": get_var('statistics_panel_height', 150),
                "statistics_bg_alpha": get_var('statistics_bg_alpha', 0.75),
                "statistics_bg_color_rgb": get_var('statistics_bg_color_rgb', "0,0,0"),
                "statistics_text_color_rgb": get_var('statistics_text_color_rgb', "255,255,255"),
                "statistics_title_color_rgb": get_var('statistics_title_color_rgb', "255,255,0"),
                
                # Analytics
                "analytics_position": get_var('analytics_position', "with_player"),
                "analytics_font_scale": get_var('analytics_font_scale', 1.0),
                "analytics_font_thickness": get_var('analytics_font_thickness', 2),
                "analytics_font_face": get_var('analytics_font_face', "FONT_HERSHEY_SIMPLEX"),
                "use_custom_analytics_color": get_var('use_custom_analytics_color', True),
                "analytics_color_rgb": get_var('analytics_color_rgb', "255,255,255"),
                "analytics_title_color_rgb": get_var('analytics_title_color_rgb', "255,255,0"),
                "analytics_preferences": getattr(gui_instance, 'analytics_preferences', {}) if hasattr(gui_instance, 'analytics_preferences') else {},
                
                # Heat map
                "show_heat_map": get_var('show_heat_map', False),
                "heat_map_alpha": get_var('heat_map_alpha', 0.4),
                "heat_map_color_scheme": get_var('heat_map_color_scheme', "hot"),
                
                # Export & Output settings
                "save_base_video": get_var('save_base_video', False),
                "export_overlay_metadata": get_var('export_overlay_metadata', True),
                "enable_video_encoding": get_var('enable_video_encoding', True),
                "overlay_quality": get_var('overlay_quality', "hd"),
                "overlay_quality_preset": get_var('overlay_quality_preset', "hd"),
                "render_scale": get_var('render_scale', 1.0),
                "enable_advanced_blending": get_var('enable_advanced_blending', True),
                "enable_motion_blur": get_var('enable_motion_blur', False),
                "motion_blur_amount": get_var('motion_blur_amount', 1.0),
                "use_professional_text": get_var('use_professional_text', True),
                
                # Other settings
                "preserve_audio": get_var('preserve_audio', True)
            }
        
        # 2. Save setup wizard data
        # First try seed_config.json (manual export)
        setup_wizard_loaded = False
        if os.path.exists("seed_config.json"):
            try:
                # Use safe JSON loading with corruption protection
                try:
                    from json_utils import safe_json_load
                    from pathlib import Path
                    seed_config = safe_json_load(Path("seed_config.json"), default={})
                except ImportError:
                    # Fallback to standard JSON if json_utils not available
                    with open("seed_config.json", 'r', encoding='utf-8') as f:
                        seed_config = json.load(f)
                project_data["setup_wizard"]["seed_config"] = seed_config
                setup_wizard_loaded = True
            except Exception as e:
                print(f"Warning: Could not load seed_config.json: {e}")
        
        # If seed_config.json doesn't exist, try to load from most recent backup
        if not setup_wizard_loaded:
            backup_dir = "setup_wizard_backups"
            if os.path.exists(backup_dir):
                try:
                    # Find most recent backup file
                    backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.json')]
                    if backup_files:
                        # Sort by modification time
                        backup_files.sort(key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)), reverse=True)
                        most_recent_backup = os.path.join(backup_dir, backup_files[0])
                        
                        with open(most_recent_backup, 'r') as f:
                            backup_data = json.load(f)
                            # Use backup data as seed config
                            project_data["setup_wizard"]["seed_config"] = backup_data
                            setup_wizard_loaded = True
                            print(f"Loaded setup wizard data from backup: {backup_files[0]}")
                except Exception as e:
                    print(f"Warning: Could not load setup wizard backup: {e}")
        
        # CRITICAL FIX: Skip automatically loading player names when saving project
        # User doesn't want names to be automatically loaded - they should be empty by default
        # Only save player names if they explicitly exist and user wants them saved
        # For now, always save empty player_names to prevent automatic loading
        project_data["player_names"] = {}
        
        # REMOVED: Automatic loading of player names from player_names.json
        # REMOVED: Automatic extraction of player names from seed_config
        # This prevents 202+ names from being automatically loaded when saving a new project
        
        # 3. Save team colors
        if os.path.exists("team_color_config.json"):
            try:
                with open("team_color_config.json", 'r') as f:
                    project_data["team_colors"] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load team_color_config.json: {e}")
        
        # 4. Save ball colors
        if os.path.exists("ball_color_config.json"):
            try:
                with open("ball_color_config.json", 'r') as f:
                    project_data["ball_colors"] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load ball_color_config.json: {e}")
        
        # 5. Save field calibration (from .npy files)
        field_calibration_data = {}
        if os.path.exists("calibration_metadata.npy"):
            try:
                calibration_metadata = np.load("calibration_metadata.npy", allow_pickle=True).item()
                field_calibration_data["metadata"] = convert_to_python_types(calibration_metadata)
            except Exception as e:
                print(f"Warning: Could not load calibration_metadata.npy: {e}")
        
        if os.path.exists("calibration.npy"):
            try:
                calibration_points = np.load("calibration.npy", allow_pickle=True)
                field_calibration_data["points"] = convert_to_python_types(calibration_points.tolist())
            except Exception as e:
                print(f"Warning: Could not load calibration.npy: {e}")
        
        if field_calibration_data:
            project_data["field_calibration"] = field_calibration_data
        
        # Also check for JSON version if it exists
        if os.path.exists("field_calibration.json"):
            try:
                with open("field_calibration.json", 'r') as f:
                    json_data = json.load(f)
                    # Merge with .npy data (JSON takes precedence)
                    project_data["field_calibration"].update(json_data)
            except Exception as e:
                print(f"Warning: Could not load field_calibration.json: {e}")
        
        # 6. Save player name list (CRITICAL FIX: Skip automatic loading - keep empty)
        # User doesn't want names to be automatically loaded when saving a new project
        project_data["player_name_list"] = []
        
        # REMOVED: Automatic loading of player_name_list.json
        # This prevents names from being automatically loaded when saving a new project
        
        # Convert NumPy types
        project_data = convert_to_python_types(project_data)
        
        # Save project file
        with open(project_path, 'w') as f:
            json.dump(project_data, f, indent=4)
        
        # Save last project path for auto-load
        save_last_project_path(project_path)
        
        # Return project path and summary of what was saved
        saved_items = {
            "analysis_settings": bool(project_data.get("analysis_settings")),
            "setup_wizard": setup_wizard_loaded,
            "team_colors": bool(project_data.get("team_colors")),
            "ball_colors": bool(project_data.get("ball_colors")),
            "field_calibration": bool(project_data.get("field_calibration")),
            "player_names": bool(project_data.get("player_names")),
            "player_count": len(project_data.get("player_names", {}))
        }
        
        return project_path, saved_items
        
    except Exception as e:
        messagebox.showerror("Error", f"Could not save project: {e}")
        import traceback
        traceback.print_exc()
        return None, {}


def load_project(project_path=None, gui_instance=None, restore_files=True):
    """
    Load all project configurations from a project file
    
    Supports both new format (with project_name, analysis_settings) and old format (player_names mapping)
    
    Args:
        project_path: Path to project file (if None, prompts for file)
        gui_instance: SoccerAnalysisGUI instance to restore settings to
        restore_files: If True, restore individual config files (default: True)
    
    Returns:
        Project data dictionary, or None if cancelled/error
    """
    if project_path is None:
        project_path = filedialog.askopenfilename(
            title="Load Project",
            filetypes=[("Project files", "*.json"), ("All files", "*.*")]
        )
    
    if not project_path or not os.path.exists(project_path):
        return None
    
    try:
        with open(project_path, 'r') as f:
            project_data = json.load(f)
        
        # Check if this is an old format project file (just player_names mapping)
        is_old_format = False
        if isinstance(project_data, dict):
            # Old format: all keys are numeric strings (track IDs) mapping to player names
            # AND doesn't have new format keys
            has_new_format = 'project_name' in project_data or 'analysis_settings' in project_data
            if not has_new_format and len(project_data) > 0:
                # Check if all keys are numeric (track IDs)
                all_numeric = all(str(k).isdigit() for k in project_data.keys() if k)
                # Check if values are strings (player names)
                all_strings = all(isinstance(v, str) for v in project_data.values() if v)
                if all_numeric and all_strings:
                    is_old_format = True
        
        # Convert old format to new format
        if is_old_format:
            # This is an old player_names.json file - convert to new format
            project_dir = os.path.dirname(project_path)
            project_basename = os.path.splitext(os.path.basename(project_path))[0]
            
            # Store old player names before conversion
            old_player_names = project_data.copy()
            
            # Try to find associated video file
            input_file = None
            output_file = None
            
            # Look for video files with similar name in the same directory
            if os.path.exists(project_dir):
                video_files = []
                analyzed_files = []
                csv_files = []
                
                for filename in os.listdir(project_dir):
                    # Match files that contain the project basename (e.g., "184113")
                    # This handles cases like "20251001_184113.mp4" where basename is "184113"
                    if project_basename in filename:
                        filepath = os.path.join(project_dir, filename)
                        # Check if it's a video file
                        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.m4v', '.flv', '.wmv']
                        if any(filename.lower().endswith(ext) for ext in video_extensions):
                            # Check for analyzed output (has _analyzed in name)
                            if '_analyzed' in filename.lower():
                                analyzed_files.append(filepath)
                            else:
                                # Regular video file
                                video_files.append(filepath)
                        # Also check for CSV tracking data
                        elif filename.lower().endswith('_tracking_data.csv'):
                            csv_files.append(filepath)
                
                # Use first video file as input (prefer non-analyzed)
                if video_files:
                    input_file = video_files[0]
                elif analyzed_files:
                    # If only analyzed files, use first one as input
                    input_file = analyzed_files[0]
                
                # Use analyzed video or CSV as output
                if analyzed_files:
                    # Prefer the most recent analyzed file
                    analyzed_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
                    output_file = analyzed_files[0]
                elif csv_files:
                    # Use CSV file path as output reference
                    csv_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
                    # For CSV, create a corresponding output video path
                    csv_file = csv_files[0]
                    # Try to find corresponding video file
                    csv_basename = os.path.splitext(os.path.basename(csv_file))[0]
                    csv_basename = csv_basename.replace('_tracking_data', '')
                    # Look for video with similar name
                    for vf in video_files + analyzed_files:
                        if csv_basename in os.path.basename(vf):
                            output_file = vf
                            break
                    if not output_file:
                        output_file = csv_file  # Fallback to CSV path
            
            # Convert to new format
            project_data = {
                "project_name": project_basename,
                "version": "1.0",
                "analysis_settings": {
                    "input_file": input_file or "",
                    "output_file": output_file or "",
                },
                "player_names": old_player_names,  # Old format is just player names
                "setup_wizard": {},
                "team_colors": {},
                "ball_colors": {},
                "field_calibration": {},
                "_is_old_format": True  # Flag to indicate this was converted
            }
            
            print(f"Detected old format project file - converted to new format")
            print(f"  Project name: {project_basename}")
            print(f"  Player names: {len(old_player_names)}")
            if input_file:
                print(f"  Input file: {input_file}")
            if output_file:
                print(f"  Output file: {output_file}")
        
        # Save last project path for auto-load
        save_last_project_path(project_path)
        
        # 1. Restore ALL analysis settings to GUI
        if gui_instance and "analysis_settings" in project_data:
            settings = project_data["analysis_settings"]
            
            # Helper function to safely set GUI variable values
            def set_var(var_name, value):
                if hasattr(gui_instance, var_name):
                    var = getattr(gui_instance, var_name)
                    if hasattr(var, 'set'):
                        # Set the value directly
                        var.set(value)
            
            # Basic file settings - get values from settings and set them
            input_file_value = settings.get('input_file', "")
            output_file_value = settings.get('output_file', "")
            
            # CRITICAL: Ensure values are strings (not None)
            if input_file_value is None:
                input_file_value = ""
            if output_file_value is None:
                output_file_value = ""
            
            # Set the variables
            set_var('input_file', input_file_value)
            set_var('output_file', output_file_value)
            
            # Also verify they were set correctly (double-check)
            if hasattr(gui_instance, 'input_file') and input_file_value:
                actual_input = gui_instance.input_file.get() if hasattr(gui_instance.input_file, 'get') else ""
                if actual_input != input_file_value:
                    # Force set if not correct
                    gui_instance.input_file.set(input_file_value)
            
            if hasattr(gui_instance, 'output_file') and output_file_value:
                actual_output = gui_instance.output_file.get() if hasattr(gui_instance.output_file, 'get') else ""
                if actual_output != output_file_value:
                    # Force set if not correct
                    gui_instance.output_file.set(output_file_value)
            video_type_value = settings.get('video_type', "practice")
            set_var('video_type', video_type_value)
            set_var('dewarp_enabled', settings.get('dewarp_enabled', False))
            set_var('remove_net_enabled', settings.get('remove_net_enabled', False))
            set_var('ball_tracking_enabled', settings.get('ball_tracking_enabled', True))
            set_var('player_tracking_enabled', settings.get('player_tracking_enabled', True))
            set_var('csv_export_enabled', settings.get('csv_export_enabled', True))
            set_var('use_imperial_units', settings.get('use_imperial_units', False))
            
            # Watch-only & Learning
            set_var('watch_only', settings.get('watch_only', False))
            set_var('show_live_viewer', settings.get('show_live_viewer', False))
            set_var('focus_players_enabled', settings.get('focus_players_enabled', False))
            if hasattr(gui_instance, 'focused_players'):
                gui_instance.focused_players = settings.get("focused_players", [])
            
            # Processing settings
            set_var('buffer_size', settings.get('buffer_size', 64))
            set_var('batch_size', settings.get('batch_size', 8))
            set_var('use_yolo_streaming', settings.get('use_yolo_streaming', False))
            
            # Ball tracking settings
            set_var('show_ball_trail', settings.get('show_ball_trail', True))
            set_var('ball_min_radius', settings.get('ball_min_radius', 5))
            set_var('ball_max_radius', settings.get('ball_max_radius', 50))
            set_var('ball_min_size', settings.get('ball_min_size', 3))
            set_var('ball_max_size', settings.get('ball_max_size', 20))
            set_var('ball_trail_length', settings.get('ball_trail_length', 20))
            set_var('trail_length', settings.get('trail_length', 20))
            set_var('trail_buffer', settings.get('trail_buffer', 20))
            
            # YOLO settings
            set_var('yolo_confidence', settings.get('yolo_confidence', 0.25))
            set_var('yolo_iou_threshold', settings.get('yolo_iou_threshold', 0.45))
            
            # Basic tracking settings
            set_var('track_thresh', settings.get('track_thresh', 0.25))
            set_var('match_thresh', settings.get('match_thresh', 0.6))
            set_var('track_buffer', settings.get('track_buffer', 50))
            set_var('track_buffer_seconds', settings.get('track_buffer_seconds', 5.0))
            set_var('min_track_length', settings.get('min_track_length', 5))
            set_var('tracker_type', settings.get('tracker_type', "deepocsort"))
            
            # Minimum detection size
            set_var('min_bbox_area', settings.get('min_bbox_area', 200))
            set_var('min_bbox_width', settings.get('min_bbox_width', 10))
            set_var('min_bbox_height', settings.get('min_bbox_height', 15))
            
            # FPS settings
            set_var('video_fps', settings.get('video_fps', 0.0))
            set_var('output_fps', settings.get('output_fps', 0.0))
            
            # Advanced tracking settings
            set_var('temporal_smoothing', settings.get('temporal_smoothing', True))
            set_var('process_every_nth', settings.get('process_every_nth', 1))
            set_var('yolo_resolution', settings.get('yolo_resolution', "full"))
            set_var('foot_based_tracking', settings.get('foot_based_tracking', True))
            set_var('use_reid', settings.get('use_reid', True))
            set_var('reid_similarity_threshold', settings.get('reid_similarity_threshold', 0.55))
            set_var('gallery_similarity_threshold', settings.get('gallery_similarity_threshold', 0.40))
            set_var('osnet_variant', settings.get('osnet_variant', "osnet_x1_0"))
            
            # Occlusion recovery
            set_var('occlusion_recovery_seconds', settings.get('occlusion_recovery_seconds', 3.0))
            set_var('occlusion_recovery_distance', settings.get('occlusion_recovery_distance', 250))
            set_var('reid_check_interval', settings.get('reid_check_interval', 30))
            set_var('reid_confidence_threshold', settings.get('reid_confidence_threshold', 0.75))
            
            # BoxMOT and GSI
            set_var('use_boxmot_backend', settings.get('use_boxmot_backend', True))
            set_var('use_gsi', settings.get('use_gsi', False))
            set_var('gsi_interval', settings.get('gsi_interval', 20))
            set_var('gsi_tau', settings.get('gsi_tau', 10.0))
            
            # Advanced tracking features (academic research)
            set_var('use_harmonic_mean', settings.get('use_harmonic_mean', True))
            set_var('use_expansion_iou', settings.get('use_expansion_iou', True))
            set_var('enable_soccer_reid_training', settings.get('enable_soccer_reid_training', False))
            set_var('use_enhanced_kalman', settings.get('use_enhanced_kalman', True))
            set_var('use_ema_smoothing', settings.get('use_ema_smoothing', True))
            set_var('confidence_filtering', settings.get('confidence_filtering', True))
            set_var('adaptive_confidence', settings.get('adaptive_confidence', True))
            set_var('use_optical_flow', settings.get('use_optical_flow', False))
            set_var('enable_velocity_constraints', settings.get('enable_velocity_constraints', True))
            set_var('preview_max_frames', settings.get('preview_max_frames', 360))
            
            # Advanced tracking options
            set_var('track_referees', settings.get('track_referees', False))
            set_var('max_players', settings.get('max_players', 12))
            set_var('enable_substitutions', settings.get('enable_substitutions', True))
            
            # Visualization - Basic
            set_var('viz_style', settings.get('viz_style', "box"))
            set_var('viz_color_mode', settings.get('viz_color_mode', "team"))
            set_var('viz_team_colors', settings.get('viz_team_colors', True))
            set_var('show_bounding_boxes', settings.get('show_bounding_boxes', True))
            set_var('show_circles_at_feet', settings.get('show_circles_at_feet', True))
            
            # Visualization - Ellipse
            set_var('ellipse_width', settings.get('ellipse_width', 20))
            set_var('ellipse_height', settings.get('ellipse_height', 12))
            set_var('ellipse_outline_thickness', settings.get('ellipse_outline_thickness', 3))
            set_var('show_ball_possession', settings.get('show_ball_possession', True))
            
            # Visualization - Feet Markers
            set_var('feet_marker_style', settings.get('feet_marker_style', "circle"))
            set_var('feet_marker_opacity', settings.get('feet_marker_opacity', 255))
            set_var('feet_marker_enable_glow', settings.get('feet_marker_enable_glow', False))
            set_var('feet_marker_glow_intensity', settings.get('feet_marker_glow_intensity', 70))
            set_var('feet_marker_enable_shadow', settings.get('feet_marker_enable_shadow', False))
            set_var('feet_marker_shadow_offset', settings.get('feet_marker_shadow_offset', 3))
            set_var('feet_marker_shadow_opacity', settings.get('feet_marker_shadow_opacity', 128))
            set_var('feet_marker_enable_gradient', settings.get('feet_marker_enable_gradient', False))
            set_var('feet_marker_enable_pulse', settings.get('feet_marker_enable_pulse', False))
            set_var('feet_marker_pulse_speed', settings.get('feet_marker_pulse_speed', 2.0))
            set_var('feet_marker_enable_particles', settings.get('feet_marker_enable_particles', False))
            set_var('feet_marker_particle_count', settings.get('feet_marker_particle_count', 5))
            set_var('feet_marker_vertical_offset', settings.get('feet_marker_vertical_offset', 50))
            set_var('show_direction_arrow', settings.get('show_direction_arrow', False))
            set_var('show_player_trail', settings.get('show_player_trail', False))
            
            # Visualization - Box
            set_var('box_shrink_factor', settings.get('box_shrink_factor', 0.10))
            set_var('box_thickness', settings.get('box_thickness', 2))
            set_var('use_custom_box_color', settings.get('use_custom_box_color', False))
            # Support both old format (separate R,G,B) and new format (RGB string)
            if 'box_color_rgb' in settings:
                set_var('box_color_rgb', settings.get('box_color_rgb', "0,255,0"))
            else:
                # Legacy format: convert separate R,G,B to string
                r = settings.get('box_color_r', 0)
                g = settings.get('box_color_g', 255)
                b = settings.get('box_color_b', 0)
                set_var('box_color_rgb', f"{r},{g},{b}")
            set_var('player_viz_alpha', settings.get('player_viz_alpha', 255))
            
            # Visualization - Labels
            set_var('show_player_labels', settings.get('show_player_labels', True))
            set_var('label_font_scale', settings.get('label_font_scale', 0.7))
            set_var('label_type', settings.get('label_type', "full_name"))
            set_var('label_custom_text', settings.get('label_custom_text', "Player"))
            set_var('label_font_face', settings.get('label_font_face', "FONT_HERSHEY_SIMPLEX"))
            set_var('use_custom_label_color', settings.get('use_custom_label_color', False))
            # Support both old format (separate R,G,B) and new format (RGB string)
            if 'label_color_rgb' in settings:
                set_var('label_color_rgb', settings.get('label_color_rgb', "255,255,255"))
            else:
                # Legacy format: convert separate R,G,B to string
                r = settings.get('label_color_r', 255)
                g = settings.get('label_color_g', 255)
                b = settings.get('label_color_b', 255)
                set_var('label_color_rgb', f"{r},{g},{b}")
            
            # Visualization - Predictions
            set_var('show_predicted_boxes', settings.get('show_predicted_boxes', False))
            set_var('prediction_duration', settings.get('prediction_duration', 1.5))
            set_var('prediction_size', settings.get('prediction_size', 5))
            set_var('prediction_color_r', settings.get('prediction_color_r', 255))
            set_var('prediction_color_g', settings.get('prediction_color_g', 255))
            set_var('prediction_color_b', settings.get('prediction_color_b', 0))
            set_var('prediction_color_alpha', settings.get('prediction_color_alpha', 255))
            set_var('prediction_style', settings.get('prediction_style', "dot"))
            set_var('show_yolo_boxes', settings.get('show_yolo_boxes', False))
            
            # Broadcast-level graphics
            set_var('trajectory_smoothness', settings.get('trajectory_smoothness', "bezier"))
            set_var('player_graphics_style', settings.get('player_graphics_style', "standard"))
            set_var('use_rounded_corners', settings.get('use_rounded_corners', True))
            set_var('use_gradient_fill', settings.get('use_gradient_fill', False))
            set_var('corner_radius', settings.get('corner_radius', 5))
            set_var('show_jersey_badge', settings.get('show_jersey_badge', False))
            set_var('ball_graphics_style', settings.get('ball_graphics_style', "standard"))
            
            # Statistics overlay
            set_var('show_statistics', settings.get('show_statistics', False))
            set_var('statistics_position', settings.get('statistics_position', "top_left"))
            set_var('statistics_panel_width', settings.get('statistics_panel_width', 250))
            set_var('statistics_panel_height', settings.get('statistics_panel_height', 150))
            set_var('statistics_bg_alpha', settings.get('statistics_bg_alpha', 0.75))
            # Support both old format (separate R,G,B) and new format (RGB string)
            if 'statistics_bg_color_rgb' in settings:
                set_var('statistics_bg_color_rgb', settings.get('statistics_bg_color_rgb', "0,0,0"))
            else:
                r = settings.get('statistics_bg_color_r', 0)
                g = settings.get('statistics_bg_color_g', 0)
                b = settings.get('statistics_bg_color_b', 0)
                set_var('statistics_bg_color_rgb', f"{r},{g},{b}")
            
            if 'statistics_text_color_rgb' in settings:
                set_var('statistics_text_color_rgb', settings.get('statistics_text_color_rgb', "255,255,255"))
            else:
                r = settings.get('statistics_text_color_r', 255)
                g = settings.get('statistics_text_color_g', 255)
                b = settings.get('statistics_text_color_b', 255)
                set_var('statistics_text_color_rgb', f"{r},{g},{b}")
            
            if 'statistics_title_color_rgb' in settings:
                set_var('statistics_title_color_rgb', settings.get('statistics_title_color_rgb', "255,255,0"))
            else:
                r = settings.get('statistics_title_color_r', 255)
                g = settings.get('statistics_title_color_g', 255)
                b = settings.get('statistics_title_color_b', 0)
                set_var('statistics_title_color_rgb', f"{r},{g},{b}")
            
            # Analytics
            set_var('analytics_position', settings.get('analytics_position', "with_player"))
            set_var('analytics_font_scale', settings.get('analytics_font_scale', 1.0))
            set_var('analytics_font_thickness', settings.get('analytics_font_thickness', 2))
            set_var('analytics_font_face', settings.get('analytics_font_face', "FONT_HERSHEY_SIMPLEX"))
            set_var('use_custom_analytics_color', settings.get('use_custom_analytics_color', True))
            # Support both old format (separate R,G,B) and new format (RGB string)
            if 'analytics_color_rgb' in settings:
                set_var('analytics_color_rgb', settings.get('analytics_color_rgb', "255,255,255"))
            else:
                r = settings.get('analytics_color_r', 255)
                g = settings.get('analytics_color_g', 255)
                b = settings.get('analytics_color_b', 255)
                set_var('analytics_color_rgb', f"{r},{g},{b}")
            
            if 'analytics_title_color_rgb' in settings:
                set_var('analytics_title_color_rgb', settings.get('analytics_title_color_rgb', "255,255,0"))
            else:
                r = settings.get('analytics_title_color_r', 255)
                g = settings.get('analytics_title_color_g', 255)
                b = settings.get('analytics_title_color_b', 0)
                set_var('analytics_title_color_rgb', f"{r},{g},{b}")
            
            # Analytics preferences
            if "analytics_preferences" in settings and hasattr(gui_instance, 'analytics_preferences'):
                gui_instance.analytics_preferences = settings.get("analytics_preferences", {})
                # Also save to file for compatibility
                try:
                    import json as json_module
                    with open("analytics_preferences.json", 'w') as f:
                        json_module.dump(settings.get("analytics_preferences", {}), f, indent=4)
                except Exception as e:
                    print(f"Warning: Could not save analytics preferences: {e}")
            
            # Heat map
            set_var('show_heat_map', settings.get('show_heat_map', False))
            set_var('heat_map_alpha', settings.get('heat_map_alpha', 0.4))
            set_var('heat_map_color_scheme', settings.get('heat_map_color_scheme', "hot"))
            
            # Export & Output settings
            set_var('save_base_video', settings.get('save_base_video', False))
            set_var('export_overlay_metadata', settings.get('export_overlay_metadata', True))
            set_var('enable_video_encoding', settings.get('enable_video_encoding', True))
            set_var('overlay_quality', settings.get('overlay_quality', "hd"))
            set_var('overlay_quality_preset', settings.get('overlay_quality_preset', "hd"))
            set_var('render_scale', settings.get('render_scale', 1.0))
            set_var('enable_advanced_blending', settings.get('enable_advanced_blending', True))
            set_var('enable_motion_blur', settings.get('enable_motion_blur', False))
            set_var('motion_blur_amount', settings.get('motion_blur_amount', 1.0))
            set_var('use_professional_text', settings.get('use_professional_text', True))
            
            # Other settings
            set_var('preserve_audio', settings.get('preserve_audio', True))
        
        # 2. Restore individual config files if requested
        if restore_files:
            # Restore setup wizard data with JSON protection
            if "setup_wizard" in project_data and "seed_config" in project_data["setup_wizard"]:
                try:
                    from json_utils import safe_json_save
                    from pathlib import Path
                    safe_json_save(Path("seed_config.json"), project_data["setup_wizard"]["seed_config"], 
                                 create_backup=True, validate=True)
                except ImportError:
                    # Fallback to standard JSON if json_utils not available
                    with open("seed_config.json", 'w', encoding='utf-8') as f:
                        json.dump(project_data["setup_wizard"]["seed_config"], f, indent=4, ensure_ascii=False)
            
            # Restore player names
            # For old format projects, player names are the main data, so always restore them
            # For new format projects, restore if present
            if "player_names" in project_data and project_data["player_names"]:
                # Only restore if there are actually names (not empty dict)
                if len(project_data["player_names"]) > 0:
                    # Always restore player names (for both old and new format)
                    # Old format projects are just player names, so they must be restored
                    # New format projects may have player names that should be restored
                    with open("player_names.json", 'w') as f:
                        json.dump(project_data["player_names"], f, indent=4)
                    print(f"Restored {len(project_data['player_names'])} player names from project")
            
            # Restore team colors
            if "team_colors" in project_data and project_data["team_colors"]:
                with open("team_color_config.json", 'w') as f:
                    json.dump(project_data["team_colors"], f, indent=4)
            
            # Restore ball colors
            if "ball_colors" in project_data and project_data["ball_colors"]:
                with open("ball_color_config.json", 'w') as f:
                    json.dump(project_data["ball_colors"], f, indent=4)
            
            # Restore field calibration (save to both .npy and .json for compatibility)
            if "field_calibration" in project_data and project_data["field_calibration"]:
                calib_data = project_data["field_calibration"]
                
                # Save as JSON
                with open("field_calibration.json", 'w') as f:
                    json.dump(calib_data, f, indent=4)
                
                # Save as .npy files if metadata/points exist
                if "metadata" in calib_data:
                    np.save("calibration_metadata.npy", calib_data["metadata"])
                if "points" in calib_data:
                    np.save("calibration.npy", np.array(calib_data["points"]))
            
            # CRITICAL FIX: Skip automatic restoration of player name list
            # User doesn't want names to be automatically loaded when loading a project
            # Only restore if there are actually names (not empty list) AND user explicitly wants them
            if "player_name_list" in project_data and project_data["player_name_list"]:
                # Only restore if there are actually names (not empty list)
                if len(project_data["player_name_list"]) > 0:
                    # Skip automatic restoration - user wants to start fresh
                    # Uncomment the following lines if you want to restore names:
                    # with open("player_name_list.json", 'w') as f:
                    #     json.dump(project_data["player_name_list"], f, indent=4)
                    pass
        
        return project_data
        
    except Exception as e:
        messagebox.showerror("Error", f"Could not load project: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_last_project_path(project_path):
    """Save the last loaded/saved project path for auto-load on startup"""
    config_file = "last_project.json"
    try:
        config = {
            "last_project_path": project_path,
            "last_accessed": datetime.now().isoformat()
        }
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save last project path: {e}")


def get_last_project_path():
    """Get the path of the last loaded/saved project"""
    config_file = "last_project.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                project_path = config.get("last_project_path")
                if project_path and os.path.exists(project_path):
                    return project_path
        except Exception as e:
            print(f"Warning: Could not load last project path: {e}")
    return None


def get_project_summary(project_path):
    """Get a summary of what's in a project file without loading it"""
    try:
        with open(project_path, 'r') as f:
            project_data = json.load(f)
        
        # Check player names in project file
        project_player_names = project_data.get("player_names", {})
        has_project_player_names = bool(project_player_names)
        project_player_count = len(project_player_names)
        
        # Also check player gallery (where player names are actually stored)
        gallery_player_count = 0
        try:
            from player_gallery import PlayerGallery
            gallery = PlayerGallery()
            gallery_players = gallery.list_players()
            gallery_player_count = len(gallery_players)
        except:
            # Gallery might not be available or might not exist yet
            pass
        
        # Use gallery count if available, otherwise use project count
        total_player_count = gallery_player_count if gallery_player_count > 0 else project_player_count
        has_player_names = has_project_player_names or (gallery_player_count > 0)
        
        summary = {
            "project_name": project_data.get("project_name", "Unknown"),
            "has_analysis_settings": bool(project_data.get("analysis_settings")),
            "has_setup_wizard": bool(project_data.get("setup_wizard", {}).get("seed_config")),
            "has_team_colors": bool(project_data.get("team_colors")),
            "has_ball_colors": bool(project_data.get("ball_colors")),
            "has_field_calibration": bool(project_data.get("field_calibration")),
            "has_player_names": has_player_names,
            "player_count": total_player_count
        }
        
        return summary
    except:
        return None

