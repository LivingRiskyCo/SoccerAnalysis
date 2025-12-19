"""
Overlay Renderer
Renders overlays from metadata onto video frames
"""

import cv2
import numpy as np
import time
import math
from typing import Dict, List, Tuple, Optional
from overlay_metadata import OverlayMetadata
from hd_overlay_renderer import HDOverlayRenderer


class OverlayRenderer:
    """Renders overlays from metadata onto video frames."""
    
    def __init__(self, metadata: OverlayMetadata, use_hd: bool = True,
                 render_scale: float = 1.0, quality: str = "hd",
                 enable_advanced_blending: bool = True,
                 enable_motion_blur: bool = False,
                 motion_blur_amount: float = 1.0,
                 use_professional_text: bool = True,
                 enable_profiling: bool = False,
                 trajectory_smoothness: str = "bezier",
                 player_graphics_style: str = "standard",
                 use_rounded_corners: bool = True,
                 use_gradient_fill: bool = False,
                 corner_radius: int = 5,
                 show_jersey_badge: bool = False,
                 ball_graphics_style: str = "standard",
                 show_statistics: bool = False,
                 statistics_position: str = "top_left",
                 show_heat_map: bool = False,
                 heat_map_alpha: float = 0.4,
                 heat_map_color_scheme: str = "hot",
                 overlay_quality_preset: str = "hd"):
        """
        Initialize overlay renderer.
        
        Args:
            metadata: OverlayMetadata instance
            use_hd: Use HD rendering
            render_scale: Render scale multiplier
            quality: Quality preset ("sd", "hd", "4k")
            enable_advanced_blending: Enable advanced blending modes
            enable_motion_blur: Enable motion blur for fast objects
            motion_blur_amount: Motion blur intensity
            use_professional_text: Use PIL-based text rendering
            trajectory_smoothness: Trajectory smoothing method ("linear", "bezier", "spline")
        """
        self.metadata = metadata
        self.use_hd = use_hd
        self.enable_motion_blur = enable_motion_blur
        self.motion_blur_amount = motion_blur_amount
        self.use_professional_text = use_professional_text
        # Store broadcast-level graphics settings
        self.trajectory_smoothness = trajectory_smoothness
        self.player_graphics_style = player_graphics_style
        self.use_rounded_corners = use_rounded_corners
        self.use_gradient_fill = use_gradient_fill
        self.corner_radius = corner_radius
        self.show_jersey_badge = show_jersey_badge
        self.ball_graphics_style = ball_graphics_style
        self.show_statistics = show_statistics
        self.statistics_position = statistics_position
        self.show_heat_map = show_heat_map
        self.heat_map_alpha = heat_map_alpha
        self.heat_map_color_scheme = heat_map_color_scheme
        self.overlay_quality_preset = overlay_quality_preset
        # Initialize HD renderer with trajectory smoothness
        self.hd_renderer = HDOverlayRenderer(render_scale, quality, enable_advanced_blending, trajectory_smoothness) if use_hd else None
        
        # Get visualization settings from metadata
        self.settings = metadata.visualization_settings
        self.viz_style = self.settings.get("viz_style", "box")
        self.show_labels = self.settings.get("show_player_labels", True)
        self.box_thickness = self.settings.get("box_thickness", 2)
        # SEPARATE CONTROLS: Bounding boxes vs Circles at feet (user requested)
        self.show_bounding_boxes = self.settings.get("show_bounding_boxes", True)
        self.show_circles_at_feet = self.settings.get("show_circles_at_feet", True)
        # Ball possession and predicted boxes (can be overridden by render_frame parameters)
        self.show_ball_possession = self.settings.get("show_ball_possession", True)
        self.show_predicted_boxes = self.settings.get("show_predicted_boxes", False)
        self.prediction_style = self.settings.get("prediction_style", "dot")
        self.prediction_size = self.settings.get("prediction_size", 5)
        self.advanced_viz_style = self.settings.get("advanced_viz_style", "none")
        self.profiling_enabled = enable_profiling
        self._reset_profile()

    def _reset_profile(self):
        if not self.profiling_enabled:
            self.last_profile = {}
            return
        self.last_profile = {
            "hd_prepare_time": 0.0,
            "field_zones_time": 0.0,
            "trajectories_time": 0.0,
            "players_time": 0.0,
            "ball_time": 0.0,
            "downscale_time": 0.0,
        }

    def _profile_step(self, key: str, duration: float):
        if not self.profiling_enabled:
            return
        if key not in self.last_profile:
            self.last_profile[key] = 0.0
        self.last_profile[key] += duration
    
    def render_frame(self, frame: np.ndarray, frame_num: int,
                    show_players: bool = True, show_ball: bool = True,
                    show_trajectories: bool = False, show_field_zones: bool = False,
                    show_analytics: bool = False, show_ball_possession: bool = True,
                    show_predicted_boxes: bool = False, show_yolo_boxes: bool = False,
                    show_statistics: bool = False, show_heat_map: bool = False,
                    # Visualization settings override (for user customization)
                    viz_settings_override: Optional[Dict] = None) -> np.ndarray:
        """
        Render overlays onto a frame.
        
        Args:
            frame: Base video frame
            frame_num: Frame number
            show_players: Show player overlays
            show_ball: Show ball overlay
            show_trajectories: Show player trajectories
            show_field_zones: Show field zones
            show_analytics: Show analytics text
            show_ball_possession: Show ball possession indicator (triangle)
            show_predicted_boxes: Show predicted boxes for lost tracks (not yet implemented)
            show_statistics: Show broadcast-style statistics overlays
            show_heat_map: Show player position heat map
            viz_settings_override: Optional dict of visualization settings to override metadata settings
                                  Allows users to customize overlays on clean video with metadata
        
        Returns:
            Frame with overlays rendered
        """
        # Store override settings temporarily for this render
        original_settings = self.settings.copy() if viz_settings_override else None
        if viz_settings_override:
            # Merge override settings with existing settings (override takes precedence)
            self.settings = {**self.settings, **viz_settings_override}
            # Update instance variables that depend on settings
            self.viz_style = self.settings.get("viz_style", self.viz_style)
            self.show_bounding_boxes = self.settings.get("show_bounding_boxes", self.show_bounding_boxes)
            self.show_circles_at_feet = self.settings.get("show_circles_at_feet", self.show_circles_at_feet)
            self.advanced_viz_style = self.settings.get("advanced_viz_style", self.advanced_viz_style)
            self.box_thickness = self.settings.get("box_thickness", self.box_thickness)
        
        # Override settings with parameters if provided
        if show_ball_possession is not None:
            self.show_ball_possession = show_ball_possession
        if show_predicted_boxes is not None:
            self.show_predicted_boxes = show_predicted_boxes
        
        if frame_num not in self.metadata.overlays:
            return frame
        
        overlay_data = self.metadata.overlays[frame_num]
        
        # Create working copy
        if self.use_hd and self.hd_renderer:
            start = time.perf_counter()
            h, w = frame.shape[:2]
            hd_frame = self.hd_renderer.create_hd_canvas(w, h)
            hd_frame[:] = cv2.resize(frame, (hd_frame.shape[1], hd_frame.shape[0]),
                                    interpolation=cv2.INTER_LANCZOS4)
            working_frame = hd_frame
            self._profile_step("hd_prepare_time", time.perf_counter() - start)
        else:
            working_frame = frame.copy()
        
        # Render field zones first (background)
        if show_field_zones and "field_zones" in overlay_data:
            start = time.perf_counter()
            for zone in overlay_data["field_zones"]:
                bounds = [(int(p[0]), int(p[1])) for p in zone["bounds"]]
                color = tuple(zone["color"]) if zone["color"] else (0, 255, 0)
                if self.use_hd and self.hd_renderer:
                    self.hd_renderer.draw_field_zone(working_frame, bounds, color, alpha=0.2)
                else:
                    self._draw_field_zone_sd(working_frame, bounds, color, alpha=0.2)
            self._profile_step("field_zones_time", time.perf_counter() - start)
        
        # Render trajectories
        if show_trajectories and "trajectories" in overlay_data:
            start = time.perf_counter()
            for traj in overlay_data["trajectories"]:
                points = [(int(p[0]), int(p[1])) for p in traj["points"]]
                color = tuple(traj["color"]) if traj["color"] else (255, 255, 0)
                velocities = traj.get("velocities")  # Optional velocity data for thickness scaling
                if self.use_hd and self.hd_renderer:
                    # Use smooth trajectory for broadcast quality
                    self.hd_renderer.draw_smooth_trajectory(
                        working_frame, points, color, thickness=2, fade=True,
                        velocities=velocities, smoothness="bezier"
                    )
                else:
                    self._draw_trajectory_sd(working_frame, points, color, thickness=2)
            self._profile_step("trajectories_time", time.perf_counter() - start)
        
        # Render players
        if show_players and "players" in overlay_data:
            start = time.perf_counter()
            for player in overlay_data["players"]:
                self._render_player(working_frame, player, frame_num, show_analytics)
                
                # Apply motion blur if enabled and velocity data available
                if self.enable_motion_blur and self.use_hd and self.hd_renderer:
                    velocity = player.get("velocity", (0, 0))  # (vx, vy) in pixels per frame
                    if velocity and (velocity[0] != 0 or velocity[1] != 0):
                        # Create a mask for just this player's region
                        bbox = player.get("bbox", [0, 0, 0, 0])
                        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                        # Extract player region
                        player_region = working_frame[y1:y2, x1:x2].copy()
                        if player_region.size > 0:
                            # Apply motion blur to player region
                            blurred_region = self.hd_renderer.apply_motion_blur(
                                player_region, velocity, self.motion_blur_amount
                            )
                            # Put blurred region back
                            working_frame[y1:y2, x1:x2] = blurred_region
            self._profile_step("players_time", time.perf_counter() - start)
        
        # Render predicted boxes for lost tracks (if enabled and available)
        if show_predicted_boxes and "predicted_boxes" in overlay_data:
            for pred_box in overlay_data["predicted_boxes"]:
                self._render_predicted_box(working_frame, pred_box)
        
        # Render ball
        if show_ball and "ball" in overlay_data and overlay_data["ball"]:
            start = time.perf_counter()
            self._render_ball(working_frame, overlay_data["ball"])
            
            # Apply motion blur to ball if enabled and velocity data available
            if self.enable_motion_blur and self.use_hd and self.hd_renderer:
                ball = overlay_data["ball"]
                ball_velocity = ball.get("velocity", (0, 0))
                if ball_velocity and (ball_velocity[0] != 0 or ball_velocity[1] != 0):
                    # Apply motion blur to ball region
                    ball_pos = ball.get("position", [0, 0])
                    ball_radius = ball.get("radius", 10)
                    x, y = int(ball_pos[0]), int(ball_pos[1])
                    # Extract ball region
                    region_size = ball_radius * 4
                    x1 = max(0, x - region_size)
                    y1 = max(0, y - region_size)
                    x2 = min(working_frame.shape[1], x + region_size)
                    y2 = min(working_frame.shape[0], y + region_size)
                    if x2 > x1 and y2 > y1:
                        ball_region = working_frame[y1:y2, x1:x2].copy()
                        if ball_region.size > 0:
                            blurred_region = self.hd_renderer.apply_motion_blur(
                                ball_region, ball_velocity, self.motion_blur_amount
                            )
                            working_frame[y1:y2, x1:x2] = blurred_region
            self._profile_step("ball_time", time.perf_counter() - start)
        
        # Render raw YOLO detection boxes (before tracking) if enabled
        if show_yolo_boxes and "raw_yolo_detections" in overlay_data:
            self._render_yolo_boxes(working_frame, overlay_data["raw_yolo_detections"])
        
        # Render statistics overlays (broadcast-style)
        if show_statistics and self.use_hd and self.hd_renderer:
            start = time.perf_counter()
            self._render_statistics_overlay(working_frame, frame_num, overlay_data)
            self._profile_step("statistics_time", time.perf_counter() - start)
        
        # Render heat map
        if show_heat_map and self.use_hd and self.hd_renderer:
            start = time.perf_counter()
            self._render_heat_map(working_frame, frame_num, overlay_data)
            self._profile_step("heatmap_time", time.perf_counter() - start)
        
        # Downscale if HD
        if self.use_hd and self.hd_renderer:
            start = time.perf_counter()
            h, w = frame.shape[:2]
            working_frame = self.hd_renderer.downscale_to_original(working_frame, w, h)
            self._profile_step("downscale_time", time.perf_counter() - start)
        
        # Restore original settings if override was used
        if original_settings is not None:
            self.settings = original_settings
        
        return working_frame
    
    def _render_player(self, frame: np.ndarray, player: Dict, frame_num: int, show_analytics: bool = False):
        """Render a single player overlay."""
        bbox = player["bbox"]
        center = player["center"]
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        
        # CRITICAL FIX: Clamp bbox coordinates to frame bounds to prevent boxes from being drawn outside frame
        # This fixes issues where coordinates might be in wrong coordinate system or incorrectly scaled
        frame_h, frame_w = frame.shape[:2]
        x1 = max(0, min(x1, frame_w - 1))
        y1 = max(0, min(y1, frame_h - 1))
        x2 = max(x1 + 1, min(x2, frame_w))  # Ensure width > 0
        y2 = max(y1 + 1, min(y2, frame_h))  # Ensure height > 0
        
        # Skip invalid boxes (too small or completely outside frame)
        if x2 <= x1 or y2 <= y1 or (x2 - x1) < 5 or (y2 - y1) < 5:
            return  # Skip rendering this player
        
        cx, cy = int(center[0]), int(center[1])
        # Also clamp center to frame bounds
        cx = max(0, min(cx, frame_w - 1))
        cy = max(0, min(cy, frame_h - 1))
        
        color = tuple(player["color"]) if player["color"] else (128, 128, 128)
        
        # SEPARATE CONTROLS: Draw bounding boxes and circles independently (user requested)
        # Get broadcast-quality graphics settings
        use_rounded_corners = self.settings.get("use_rounded_corners", True)
        use_gradient_fill = self.settings.get("use_gradient_fill", False)
        player_graphics_style = self.settings.get("player_graphics_style", "standard")  # "minimal", "standard", "broadcast"
        corner_radius = self.settings.get("corner_radius", 5)
        
        # Draw bounding box if enabled
        if self.show_bounding_boxes:
            if self.use_hd and self.hd_renderer:
                # Broadcast-quality: rounded corners and gradients
                if player_graphics_style == "broadcast" and use_rounded_corners:
                    # Draw rounded rectangle with optional gradient
                    if use_gradient_fill:
                        # Create darker version for gradient end
                        darker_color = tuple(max(0, int(c * 0.6)) for c in color)
                        self.hd_renderer.draw_gradient_rectangle(
                            frame, (x1, y1), (x2, y2),
                            color, darker_color, direction="vertical",
                            alpha=0.3, rounded=True, corner_radius=corner_radius
                        )
                    # Draw rounded outline
                    self.hd_renderer.draw_crisp_rectangle(
                        frame, (x1, y1), (x2, y2), color, self.box_thickness,
                        rounded=True, corner_radius=corner_radius
                    )
                else:
                    # Standard rectangle
                    self.hd_renderer.draw_crisp_rectangle(frame, (x1, y1), (x2, y2), 
                                                          color, self.box_thickness)
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, self.box_thickness)
        # Legacy support: use viz_style if new settings not available
        elif self.viz_style in ["box", "both"]:
            if self.use_hd and self.hd_renderer:
                if player_graphics_style == "broadcast" and use_rounded_corners:
                    self.hd_renderer.draw_crisp_rectangle(
                        frame, (x1, y1), (x2, y2), color, self.box_thickness,
                        rounded=True, corner_radius=corner_radius
                    )
                else:
                    self.hd_renderer.draw_crisp_rectangle(frame, (x1, y1), (x2, y2), 
                                                          color, self.box_thickness)
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, self.box_thickness)
        
        # Draw circle at feet if enabled (always uses team colors from player data)
        if self.show_circles_at_feet:
            # Draw ellipse at feet position (bottom of bbox)
            foot_y = y2
            ellipse_width = self.settings.get("ellipse_width", 20)
            ellipse_height = self.settings.get("ellipse_height", 12)
            ellipse_outline_thickness = self.settings.get("ellipse_outline_thickness", 3)
            # Scale ellipse size
            scale_factor = max(1.0, frame.shape[1] / 1920.0)
            scaled_width = int(ellipse_width * scale_factor)
            scaled_height = int(ellipse_height * scale_factor)
            axes = (int(scaled_width / 2), int(scaled_height / 2))
            # Always use team color for circles (ignore box_color setting)
            ellipse_color = color
            
            # Get enhanced feet marker settings
            feet_marker_style = self.settings.get("feet_marker_style", "circle")
            feet_marker_opacity = self.settings.get("feet_marker_opacity", 255)
            feet_marker_enable_glow = self.settings.get("feet_marker_enable_glow", False)
            feet_marker_glow_intensity = self.settings.get("feet_marker_glow_intensity", 50)
            feet_marker_enable_shadow = self.settings.get("feet_marker_enable_shadow", False)
            feet_marker_shadow_offset = self.settings.get("feet_marker_shadow_offset", 3)
            feet_marker_shadow_opacity = self.settings.get("feet_marker_shadow_opacity", 128)
            feet_marker_enable_gradient = self.settings.get("feet_marker_enable_gradient", False)
            feet_marker_enable_pulse = self.settings.get("feet_marker_enable_pulse", False)
            feet_marker_pulse_speed = self.settings.get("feet_marker_pulse_speed", 2.0)
            feet_marker_enable_particles = self.settings.get("feet_marker_enable_particles", False)
            feet_marker_particle_count = self.settings.get("feet_marker_particle_count", 5)
            
            # Use enhanced rendering if any advanced features are enabled
            if (feet_marker_style != "circle" and feet_marker_style != "ellipse") or \
               feet_marker_enable_glow or feet_marker_enable_shadow or \
               feet_marker_enable_gradient or feet_marker_enable_pulse or \
               feet_marker_enable_particles or feet_marker_opacity < 255:
                # Use enhanced rendering function
                self._draw_enhanced_feet_marker(
                    frame, (cx, foot_y), axes,
                    feet_marker_style, ellipse_color, feet_marker_opacity,
                    feet_marker_enable_glow, feet_marker_glow_intensity,
                    feet_marker_enable_shadow, feet_marker_shadow_offset, feet_marker_shadow_opacity,
                    feet_marker_enable_gradient, feet_marker_enable_pulse, feet_marker_pulse_speed, frame_num,
                    feet_marker_enable_particles, feet_marker_particle_count,
                    ellipse_outline_thickness
                )
            else:
                # Draw standard ellipse (legacy mode for performance)
                if self.use_hd and self.hd_renderer:
                    # Draw filled ellipse
                    self.hd_renderer.draw_crisp_ellipse(frame, (cx, foot_y), axes, 0, ellipse_color, thickness=-1, filled=True)
                    # Draw white outline (only if thickness > 0)
                    if ellipse_outline_thickness > 0:
                        self.hd_renderer.draw_crisp_ellipse(frame, (cx, foot_y), axes, 0, (255, 255, 255), thickness=ellipse_outline_thickness, filled=False)
                else:
                    # Draw filled ellipse
                    cv2.ellipse(frame, (cx, foot_y), axes, 0, 0, 360, ellipse_color, -1)
                    # Draw white outline (only if thickness > 0)
                    if ellipse_outline_thickness > 0:
                        cv2.ellipse(frame, (cx, foot_y), axes, 0, 0, 360, (255, 255, 255), ellipse_outline_thickness)
        
        # ENHANCEMENT: Draw direction arrow if enabled and data available
        show_direction_arrow = self.settings.get("show_direction_arrow", False)
        if show_direction_arrow:
            direction_angle = player.get("direction_angle")
            if direction_angle is not None:
                # Import draw_direction_arrow from combined_analysis_optimized
                try:
                    from combined_analysis_optimized import draw_direction_arrow
                    arrow_color_setting = self.settings.get("direction_arrow_color", None)
                    arrow_color = None
                    if arrow_color_setting:
                        arrow_color = tuple(int(c) for c in arrow_color_setting) if isinstance(arrow_color_setting, (list, tuple)) else (255, 255, 255)
                    else:
                        arrow_color = (255, 255, 255)  # Default white
                    arrow_center = (cx, foot_y + axes[1] + 5)  # 5 pixels below marker
                    draw_direction_arrow(frame, arrow_center, direction_angle,
                                       arrow_length=20, arrow_color=arrow_color,
                                       arrow_thickness=2, arrow_head_size=8)
                except ImportError:
                    pass  # Silently fail if function not available
        
        # ENHANCEMENT: Draw player trail if enabled and data available
        show_player_trail = self.settings.get("show_player_trail", False)
        trail_length = self.settings.get("trail_length", 20)
        if show_player_trail:
            position_history = player.get("position_history")
            if position_history and len(position_history) > 1:
                # Draw trail with fading opacity
                trail_points = position_history[-min(trail_length, len(position_history)):]
                for j, (trail_x, trail_y) in enumerate(trail_points):
                    if j < len(trail_points) - 1:  # Don't draw line from last point
                        next_x, next_y = trail_points[j + 1]
                        # Fade opacity based on age (older = more transparent)
                        trail_alpha = int(255 * (1.0 - j / len(trail_points)) * 0.6)
                        trail_color = tuple(int(c * trail_alpha / 255.0) for c in color)
                        cv2.line(frame, (int(trail_x), int(trail_y)),
                                (int(next_x), int(next_y)), trail_color, 2, cv2.LINE_AA)
        
        # Legacy support: use viz_style if new settings not available
        elif self.viz_style in ["circle", "both"]:
            radius = min((x2 - x1) // 2, (y2 - y1) // 2)
            if self.use_hd and self.hd_renderer:
                self.hd_renderer.draw_crisp_circle(frame, (cx, y2), radius, color, 2)
            else:
                cv2.circle(frame, (cx, y2), radius, color, 2)
        
        # Draw label with broadcast-quality typography
        if self.show_labels:
            player_name = player.get("player_name") or f"#{player['track_id']}"
            jersey_number = player.get("jersey_number")
            player_graphics_style = self.settings.get("player_graphics_style", "standard")
            show_jersey_badge = self.settings.get("show_jersey_badge", False)
            
            # Broadcast style: draw jersey badge separately
            if player_graphics_style == "broadcast" and jersey_number and show_jersey_badge and self.use_hd and self.hd_renderer:
                # Draw circular badge at top-left of box
                badge_radius = max(12, min((x2 - x1) // 8, (y2 - y1) // 8))
                badge_center = (x1 + badge_radius + 2, y1 + badge_radius + 2)
                self.hd_renderer.draw_player_badge(
                    frame, badge_center, badge_radius,
                    str(jersey_number), text_color=(255, 255, 255),
                    bg_color=color, outline_color=(255, 255, 255), outline_thickness=1
                )
                # Draw name above box
                label_y = y1 - 8 if y1 > 25 else y2 + 25
                label = player_name  # Just name, number is in badge
            else:
                # Standard style: combined label
                label = player_name
                if jersey_number:
                    label = f"{label} ({jersey_number})"
                label_y = y1 - 5 if y1 > 20 else y2 + 20
            
            # Use professional text rendering if enabled
            if self.use_professional_text and self.use_hd and self.hd_renderer:
                font_size = int(self.settings.get("label_font_scale", 0.7) * 24)  # Scale to pixel size
                # Broadcast style: better positioning and background
                if player_graphics_style == "broadcast":
                    # Draw semi-transparent background for text
                    text_bg_padding = 4
                    (text_width, text_height), baseline = cv2.getTextSize(
                        label, cv2.FONT_HERSHEY_BOLD, font_size / 24.0, 2
                    )
                    bg_x1 = max(0, x1 - text_bg_padding)
                    bg_y1 = max(0, label_y - text_height - text_bg_padding)
                    bg_x2 = min(frame_w, x1 + text_width + text_bg_padding)
                    bg_y2 = min(frame_h, label_y + baseline + text_bg_padding)
                    
                    # Draw rounded background
                    if bg_x2 > bg_x1 and bg_y2 > bg_y1:
                        overlay = frame.copy()
                        self.hd_renderer.draw_crisp_rectangle(
                            overlay, (bg_x1, bg_y1), (bg_x2, bg_y2),
                            (0, 0, 0), thickness=-1, filled=True, rounded=True, corner_radius=3
                        )
                        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
                
                self.hd_renderer.draw_professional_text(frame, label, (x1, label_y),
                                                        font_size=font_size,
                                                        color=color,
                                                        outline_color=(0, 0, 0),
                                                        outline_width=2,
                                                        shadow=True)
            elif self.use_hd and self.hd_renderer:
                self.hd_renderer.draw_crisp_text(frame, label, (x1, label_y),
                                                color=color, outline_color=(0, 0, 0),
                                                outline_thickness=3)
            else:
                # Draw outline
                cv2.putText(frame, label, (x1, label_y), cv2.FONT_HERSHEY_SIMPLEX,
                           0.6, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(frame, label, (x1, label_y), cv2.FONT_HERSHEY_SIMPLEX,
                           0.6, color, 2, cv2.LINE_AA)
        
        # Draw ball possession indicator (enhanced for broadcast quality)
        if self.show_ball_possession and player.get("has_ball", False):
            foot_y = y2
            ellipse_height = self.settings.get("ellipse_height", 12)
            player_graphics_style = self.settings.get("player_graphics_style", "standard")
            
            if player_graphics_style == "broadcast" and self.use_hd and self.hd_renderer:
                # Enhanced broadcast-style indicator: larger, with glow
                triangle_size = max(12, int(ellipse_height * 1.2))
                triangle_top = (cx, int(foot_y) - int(ellipse_height / 2) - triangle_size)
                triangle_left = (cx - triangle_size, int(foot_y) - int(ellipse_height / 2))
                triangle_right = (cx + triangle_size, int(foot_y) - int(ellipse_height / 2))
                triangle_points = np.array([triangle_top, triangle_left, triangle_right], np.int32)
                
                # Draw with glow effect
                def draw_triangle(img, pts, col):
                    cv2.fillPoly(img, [pts], col)
                    cv2.polylines(img, [pts], isClosed=True, color=(255, 255, 255), thickness=2, lineType=cv2.LINE_AA)
                
                # Apply glow
                self.hd_renderer.draw_glow_effect(
                    frame, draw_triangle, {"pts": triangle_points, "col": (255, 0, 0)},
                    glow_color=(255, 100, 100), glow_intensity=40, glow_layers=3
                )
                # Draw main triangle
                draw_triangle(frame, triangle_points, (255, 0, 0))  # Blue in BGR
            else:
                # Standard indicator
                triangle_size = max(8, int(ellipse_height * 0.8))
                triangle_top = (cx, int(foot_y) - int(ellipse_height / 2) - triangle_size)
                triangle_left = (cx - triangle_size, int(foot_y) - int(ellipse_height / 2))
                triangle_right = (cx + triangle_size, int(foot_y) - int(ellipse_height / 2))
                triangle_points = np.array([triangle_top, triangle_left, triangle_right], np.int32)
                # Draw filled triangle (blue for ball possession)
                cv2.fillPoly(frame, [triangle_points], (255, 0, 0))  # Blue in BGR
                # Draw outline
                cv2.polylines(frame, [triangle_points], isClosed=True, color=(255, 255, 255), thickness=1)
        
        # Draw analytics
        if show_analytics and frame_num in self.metadata.analytics_data:
            analytics = self.metadata.analytics_data[frame_num].get(player["track_id"])
            if analytics:
                self._render_analytics(frame, (x1, y2 + 5), analytics)
    
    def _draw_advanced_shape(self, frame: np.ndarray, center: Tuple[int, int], axes: Tuple[int, int],
                             style: str, color: Tuple[int, int, int], outline_thickness: int):
        """Draw advanced visualization shapes (star, diamond, hexagon, arrow)."""
        cx, cy = center
        width, height = axes[0] * 2, axes[1] * 2
        
        if style == "star":
            # Draw 5-pointed star
            import math
            points = []
            outer_radius = max(width, height) // 2
            inner_radius = outer_radius // 2
            for i in range(10):
                angle = i * math.pi / 5
                radius = outer_radius if i % 2 == 0 else inner_radius
                x = int(cx + radius * math.cos(angle - math.pi / 2))
                y = int(cy + radius * math.sin(angle - math.pi / 2))
                points.append([x, y])
            points = np.array(points, np.int32)
            cv2.fillPoly(frame, [points], color)
            if outline_thickness > 0:
                cv2.polylines(frame, [points], True, (255, 255, 255), outline_thickness)
        elif style == "diamond":
            # Draw diamond
            half_w, half_h = width // 2, height // 2
            points = np.array([
                [cx, cy - half_h],  # Top
                [cx + half_w, cy],  # Right
                [cx, cy + half_h],  # Bottom
                [cx - half_w, cy]   # Left
            ], np.int32)
            cv2.fillPoly(frame, [points], color)
            cv2.polylines(frame, [points], True, (255, 255, 255), outline_thickness)
        elif style == "hexagon":
            # Draw hexagon
            import math
            radius = max(width, height) // 2
            points = []
            for i in range(6):
                angle = i * math.pi / 3
                x = int(cx + radius * math.cos(angle))
                y = int(cy + radius * math.sin(angle))
                points.append([x, y])
            points = np.array(points, np.int32)
            cv2.fillPoly(frame, [points], color)
            if outline_thickness > 0:
                cv2.polylines(frame, [points], True, (255, 255, 255), outline_thickness)
    
    def _draw_enhanced_feet_marker(self, frame: np.ndarray, center: Tuple[int, int], axes: Tuple[int, int],
                                   style: str, color: Tuple[int, int, int], opacity: int,
                                   enable_glow: bool, glow_intensity: int,
                                   enable_shadow: bool, shadow_offset: int, shadow_opacity: int,
                                   enable_gradient: bool, enable_pulse: bool, pulse_speed: float, frame_num: int,
                                   enable_particles: bool, particle_count: int,
                                   outline_thickness: int = 3):
        """
        Draw enhanced feet marker with high-quality graphics effects.
        
        Args:
            frame: Frame to draw on
            center: (x, y) center position
            axes: (width/2, height/2) for ellipse
            style: "circle", "ellipse", "diamond", "star", "hexagon", "ring", "glow", "pulse"
            color: Base color (B, G, R)
            opacity: Opacity (0-255)
            enable_glow: Enable glow effect
            glow_intensity: Glow intensity (0-100)
            enable_shadow: Enable shadow effect
            shadow_offset: Shadow offset in pixels
            shadow_opacity: Shadow opacity (0-255)
            enable_gradient: Enable gradient fill
            enable_pulse: Enable pulse animation
            pulse_speed: Pulse speed (cycles per second)
            frame_num: Current frame number (for animation)
            enable_particles: Enable particle effects
            particle_count: Number of particles
            outline_thickness: Outline thickness
        """
        import math
        import cv2
        
        cx, cy = center
        width, height = axes[0] * 2, axes[1] * 2
        
        # Apply opacity to color
        base_color = tuple(int(c * opacity / 255.0) for c in color)
        
        # Calculate pulse scale if enabled
        pulse_scale = 1.0
        if enable_pulse:
            # Pulse animation: scale from 0.8 to 1.2
            pulse_phase = (frame_num * pulse_speed / 30.0) % (2 * math.pi)  # Assuming 30 FPS
            pulse_scale = 0.8 + 0.4 * (1.0 + math.sin(pulse_phase)) / 2.0
            width = int(width * pulse_scale)
            height = int(height * pulse_scale)
            axes = (width // 2, height // 2)
        
        # Create a temporary layer for effects
        effect_layer = None
        if enable_glow or enable_shadow:
            # Create larger canvas for effects
            effect_size = max(width, height) + (glow_intensity * 2 if enable_glow else shadow_offset * 2)
            effect_layer = np.zeros((effect_size * 2, effect_size * 2, 3), dtype=np.uint8)
            effect_center = (effect_size, effect_size)
            effect_axes = (axes[0], axes[1])
        else:
            effect_center = center
            effect_axes = axes
        
        # Draw shadow first (if enabled)
        if enable_shadow:
            shadow_color = (0, 0, 0)  # Black shadow
            shadow_alpha = shadow_opacity / 255.0
            shadow_center = (cx + shadow_offset, cy + shadow_offset)
            
            # Draw shadow shape
            if style in ["circle", "ellipse"]:
                shadow_layer = np.zeros_like(frame)
                cv2.ellipse(shadow_layer, shadow_center, axes, 0, 0, 360, shadow_color, -1)
                frame[:, :] = cv2.addWeighted(frame, 1.0, shadow_layer, shadow_alpha, 0)
            elif style == "diamond":
                half_w, half_h = axes[0], axes[1]
                shadow_points = np.array([
                    [shadow_center[0], shadow_center[1] - half_h],
                    [shadow_center[0] + half_w, shadow_center[1]],
                    [shadow_center[0], shadow_center[1] + half_h],
                    [shadow_center[0] - half_w, shadow_center[1]]
                ], np.int32)
                shadow_layer = np.zeros_like(frame)
                cv2.fillPoly(shadow_layer, [shadow_points], shadow_color)
                frame[:, :] = cv2.addWeighted(frame, 1.0, shadow_layer, shadow_alpha, 0)
            elif style == "star":
                outer_radius = max(axes[0], axes[1])
                inner_radius = outer_radius // 2
                shadow_points = []
                for i in range(10):
                    angle = i * math.pi / 5
                    radius = outer_radius if i % 2 == 0 else inner_radius
                    x = int(shadow_center[0] + radius * math.cos(angle - math.pi / 2))
                    y = int(shadow_center[1] + radius * math.sin(angle - math.pi / 2))
                    shadow_points.append([x, y])
                shadow_points = np.array(shadow_points, np.int32)
                shadow_layer = np.zeros_like(frame)
                cv2.fillPoly(shadow_layer, [shadow_points], shadow_color)
                frame[:, :] = cv2.addWeighted(frame, 1.0, shadow_layer, shadow_alpha, 0)
            elif style == "hexagon":
                radius = max(axes[0], axes[1])
                shadow_points = []
                for i in range(6):
                    angle = i * math.pi / 3
                    x = int(shadow_center[0] + radius * math.cos(angle))
                    y = int(shadow_center[1] + radius * math.sin(angle))
                    shadow_points.append([x, y])
                shadow_points = np.array(shadow_points, np.int32)
                shadow_layer = np.zeros_like(frame)
                cv2.fillPoly(shadow_layer, [shadow_points], shadow_color)
                frame[:, :] = cv2.addWeighted(frame, 1.0, shadow_layer, shadow_alpha, 0)
        
        # Draw main shape
        if style in ["circle", "ellipse"]:
            if enable_gradient:
                # Draw gradient fill (radial gradient)
                for r in range(max(axes[0], axes[1]), 0, -2):
                    gradient_alpha = int(opacity * (r / max(axes[0], axes[1])))
                    gradient_color = tuple(int(c * gradient_alpha / 255.0) for c in color)
                    cv2.ellipse(frame, center, (r, r), 0, 0, 360, gradient_color, -1)
            else:
                cv2.ellipse(frame, center, axes, 0, 0, 360, base_color, -1)
            # Draw outline (only if thickness > 0)
            if outline_thickness > 0:
                cv2.ellipse(frame, center, axes, 0, 0, 360, (255, 255, 255), outline_thickness)
            
        elif style == "diamond":
            half_w, half_h = axes[0], axes[1]
            points = np.array([
                [cx, cy - half_h],
                [cx + half_w, cy],
                [cx, cy + half_h],
                [cx - half_w, cy]
            ], np.int32)
            if enable_gradient:
                # Draw gradient diamond (simplified - draw multiple layers)
                for scale in [1.0, 0.8, 0.6, 0.4, 0.2]:
                    scaled_points = np.array([
                        [cx, int(cy - half_h * scale)],
                        [int(cx + half_w * scale), cy],
                        [cx, int(cy + half_h * scale)],
                        [int(cx - half_w * scale), cy]
                    ], np.int32)
                    gradient_alpha = int(opacity * scale)
                    gradient_color = tuple(int(c * gradient_alpha / 255.0) for c in color)
                    cv2.fillPoly(frame, [scaled_points], gradient_color)
            else:
                cv2.fillPoly(frame, [points], base_color)
            if outline_thickness > 0:
                cv2.polylines(frame, [points], True, (255, 255, 255), outline_thickness)
            
        elif style == "star":
            outer_radius = max(axes[0], axes[1])
            inner_radius = outer_radius // 2
            points = []
            for i in range(10):
                angle = i * math.pi / 5
                radius = outer_radius if i % 2 == 0 else inner_radius
                x = int(cx + radius * math.cos(angle - math.pi / 2))
                y = int(cy + radius * math.sin(angle - math.pi / 2))
                points.append([x, y])
            points = np.array(points, np.int32)
            if enable_gradient:
                # Draw gradient star (simplified)
                for scale in [1.0, 0.7, 0.4]:
                    scaled_points = []
                    for i in range(10):
                        angle = i * math.pi / 5
                        radius = (outer_radius if i % 2 == 0 else inner_radius) * scale
                        x = int(cx + radius * math.cos(angle - math.pi / 2))
                        y = int(cy + radius * math.sin(angle - math.pi / 2))
                        scaled_points.append([x, y])
                    scaled_points = np.array(scaled_points, np.int32)
                    gradient_alpha = int(opacity * scale)
                    gradient_color = tuple(int(c * gradient_alpha / 255.0) for c in color)
                    cv2.fillPoly(frame, [scaled_points], gradient_color)
            else:
                cv2.fillPoly(frame, [points], base_color)
            if outline_thickness > 0:
                cv2.polylines(frame, [points], True, (255, 255, 255), outline_thickness)
            
        elif style == "hexagon":
            radius = max(axes[0], axes[1])
            points = []
            for i in range(6):
                angle = i * math.pi / 3
                x = int(cx + radius * math.cos(angle))
                y = int(cy + radius * math.sin(angle))
                points.append([x, y])
            points = np.array(points, np.int32)
            if enable_gradient:
                # Draw gradient hexagon
                for scale in [1.0, 0.8, 0.6, 0.4, 0.2]:
                    scaled_points = []
                    for i in range(6):
                        angle = i * math.pi / 3
                        x = int(cx + radius * scale * math.cos(angle))
                        y = int(cy + radius * scale * math.sin(angle))
                        scaled_points.append([x, y])
                    scaled_points = np.array(scaled_points, np.int32)
                    gradient_alpha = int(opacity * scale)
                    gradient_color = tuple(int(c * gradient_alpha / 255.0) for c in color)
                    cv2.fillPoly(frame, [scaled_points], gradient_color)
            else:
                cv2.fillPoly(frame, [points], base_color)
            if outline_thickness > 0:
                cv2.polylines(frame, [points], True, (255, 255, 255), outline_thickness)
            
        elif style == "ring":
            # Hollow circle/ellipse (ring)
            outer_axes = axes
            inner_axes = (int(axes[0] * 0.6), int(axes[1] * 0.6))
            if outline_thickness > 0:
                cv2.ellipse(frame, center, outer_axes, 0, 0, 360, base_color, outline_thickness * 2)
                # Draw inner circle to create ring effect
                cv2.ellipse(frame, center, inner_axes, 0, 0, 360, (0, 0, 0), -1)  # Black fill to create ring
                cv2.ellipse(frame, center, outer_axes, 0, 0, 360, (255, 255, 255), outline_thickness)
            else:
                # If no outline, just draw filled ellipse
                cv2.ellipse(frame, center, axes, 0, 0, 360, base_color, -1)
            
        elif style == "glow":
            # Glow effect: draw multiple layers with decreasing opacity
            glow_layers = glow_intensity // 10
            for i in range(glow_layers, 0, -1):
                glow_alpha = int(opacity * (i / glow_layers) * 0.3)
                glow_color = tuple(int(c * glow_alpha / 255.0) for c in color)
                glow_axes = (axes[0] + i * 2, axes[1] + i * 2)
                cv2.ellipse(frame, center, glow_axes, 0, 0, 360, glow_color, -1)
            # Draw main shape on top
            cv2.ellipse(frame, center, axes, 0, 0, 360, base_color, -1)
            if outline_thickness > 0:
                cv2.ellipse(frame, center, axes, 0, 0, 360, (255, 255, 255), outline_thickness)
            
        elif style == "pulse":
            # Pulse is handled by scale adjustment above, just draw the shape
            cv2.ellipse(frame, center, axes, 0, 0, 360, base_color, -1)
            if outline_thickness > 0:
                cv2.ellipse(frame, center, axes, 0, 0, 360, (255, 255, 255), outline_thickness)
        
        # Apply glow effect (post-processing)
        if enable_glow and style != "glow":
            # Create glow using Gaussian blur
            glow_radius = glow_intensity // 5
            if glow_radius > 0:
                # Create a mask for the shape
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                if style in ["circle", "ellipse"]:
                    cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
                elif style == "diamond":
                    half_w, half_h = axes[0], axes[1]
                    points = np.array([
                        [cx, cy - half_h],
                        [cx + half_w, cy],
                        [cx, cy + half_h],
                        [cx - half_w, cy]
                    ], np.int32)
                    cv2.fillPoly(mask, [points], 255)
                elif style == "star":
                    outer_radius = max(axes[0], axes[1])
                    inner_radius = outer_radius // 2
                    points = []
                    for i in range(10):
                        angle = i * math.pi / 5
                        radius = outer_radius if i % 2 == 0 else inner_radius
                        x = int(cx + radius * math.cos(angle - math.pi / 2))
                        y = int(cy + radius * math.sin(angle - math.pi / 2))
                        points.append([x, y])
                    points = np.array(points, np.int32)
                    cv2.fillPoly(mask, [points], 255)
                elif style == "hexagon":
                    radius = max(axes[0], axes[1])
                    points = []
                    for i in range(6):
                        angle = i * math.pi / 3
                        x = int(cx + radius * math.cos(angle))
                        y = int(cy + radius * math.sin(angle))
                        points.append([x, y])
                    points = np.array(points, np.int32)
                    cv2.fillPoly(mask, [points], 255)
                
                # Apply Gaussian blur to create glow
                blurred = cv2.GaussianBlur(mask, (glow_radius * 2 + 1, glow_radius * 2 + 1), 0)
                # Create glow color layer
                glow_layer = np.zeros_like(frame)
                glow_alpha = glow_intensity / 100.0
                for c in range(3):
                    glow_layer[:, :, c] = blurred * color[c] * glow_alpha
                # Blend glow with frame
                frame[:, :] = cv2.addWeighted(frame, 1.0, glow_layer, 0.5, 0)
        
        # Draw particle effects
        if enable_particles:
            import random
            particle_radius = max(2, min(axes[0], axes[1]) // 4)
            for _ in range(particle_count):
                # Random position around the marker
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(max(axes[0], axes[1]) * 1.2, max(axes[0], axes[1]) * 2.0)
                px = int(cx + distance * math.cos(angle))
                py = int(cy + distance * math.sin(angle))
                # Random color variation
                particle_color = tuple(min(255, int(c * random.uniform(0.7, 1.3))) for c in base_color)
                cv2.circle(frame, (px, py), particle_radius, particle_color, -1)
                cv2.circle(frame, (px, py), particle_radius, (255, 255, 255), 1)
        elif style == "arrow":
            # Draw upward arrow
            arrow_size = max(width, height) // 2
            points = np.array([
                [cx, cy - arrow_size],  # Top point
                [cx - arrow_size // 2, cy],  # Left
                [cx + arrow_size // 2, cy]   # Right
            ], np.int32)
            cv2.fillPoly(frame, [points], color)
            cv2.polylines(frame, [points], True, (255, 255, 255), outline_thickness)
    
    def _render_predicted_box(self, frame: np.ndarray, pred_box: Dict):
        """Render a predicted box for a lost track."""
        center = pred_box.get("center")
        if not center:
            return
        
        cx, cy = int(center[0]), int(center[1])
        color = tuple(pred_box.get("color", (0, 255, 255)))  # Default yellow
        style = pred_box.get("style", "dot")
        size = pred_box.get("size", 5)
        
        # Draw based on style (same logic as in combined_analysis_optimized.py)
        if style == "dot":
            cv2.circle(frame, (cx, cy), size, color, -1)
            cv2.circle(frame, (cx, cy), size, (255, 255, 255), 1)
        elif style == "box":
            half_size = size
            cv2.rectangle(frame, (cx - half_size, cy - half_size),
                         (cx + half_size, cy + half_size), color, 2)
        elif style == "cross":
            half_size = size
            cv2.line(frame, (cx - half_size, cy), (cx + half_size, cy), color, 2)
            cv2.line(frame, (cx, cy - half_size), (cx, cy + half_size), color, 2)
        elif style == "x":
            half_size = int(size * 0.7)
            cv2.line(frame, (cx - half_size, cy - half_size),
                    (cx + half_size, cy + half_size), color, 2)
            cv2.line(frame, (cx - half_size, cy + half_size),
                    (cx + half_size, cy - half_size), color, 2)
        elif style == "arrow":
            arrow_size = size
            points = np.array([
                [cx, cy - arrow_size],  # Top point
                [cx - arrow_size // 2, cy],  # Left
                [cx + arrow_size // 2, cy]   # Right
            ], np.int32)
            cv2.fillPoly(frame, [points], color)
        elif style == "diamond":
            half_size = size
            points = np.array([
                [cx, cy - half_size],  # Top
                [cx + half_size, cy],   # Right
                [cx, cy + half_size],   # Bottom
                [cx - half_size, cy]    # Left
            ], np.int32)
            cv2.fillPoly(frame, [points], color)
            cv2.polylines(frame, [points], True, (255, 255, 255), 1)
    
    def _render_ball(self, frame: np.ndarray, ball: Dict):
        """Render ball overlay."""
        if not ball.get("detected") or not ball.get("center"):
            return
        
        center = ball["center"]
        cx, cy = int(center[0]), int(center[1])
        radius = 8
        
        # Draw ball
        if self.use_hd and self.hd_renderer:
            self.hd_renderer.draw_crisp_circle(frame, (cx, cy), radius, (0, 0, 255), 2)
            self.hd_renderer.draw_crisp_circle(frame, (cx, cy), radius - 2, (0, 255, 0), -1)
        else:
            cv2.circle(frame, (cx, cy), radius, (0, 0, 255), 2)
            cv2.circle(frame, (cx, cy), radius - 2, (0, 255, 0), -1)
        
        # Draw trail with enhanced broadcast graphics
        if ball.get("trail") and len(ball["trail"]) > 1:
            trail_points = [(int(p[0]), int(p[1])) for p in ball["trail"]]
            ball_graphics_style = self.settings.get("ball_graphics_style", "standard")
            
            if self.use_hd and self.hd_renderer:
                ball_velocity = ball.get("velocity", (0, 0))
                velocities = None
                if ball_velocity and len(trail_points) > 1:
                    velocities = [ball_velocity] * len(trail_points)
                
                if ball_graphics_style == "broadcast":
                    # Enhanced trail: velocity-based color coding
                    speed = math.sqrt(ball_velocity[0]**2 + ball_velocity[1]**2) if ball_velocity else 0
                    # Color code: red = fast, blue = slow
                    if speed > 30:
                        trail_color = (0, 0, 255)  # Red (fast)
                    elif speed > 15:
                        trail_color = (0, 128, 255)  # Orange
                    else:
                        trail_color = (255, 128, 0)  # Blue (slow)
                    
                    # Use smooth trajectory with velocity-based thickness
                    self.hd_renderer.draw_smooth_trajectory(
                        frame, trail_points, trail_color, 
                        thickness=3, fade=True, velocities=velocities, smoothness="bezier"
                    )
                else:
                    # Standard smooth trajectory
                    self.hd_renderer.draw_smooth_trajectory(
                        frame, trail_points, (0, 0, 255), 
                        thickness=2, fade=True, velocities=velocities, smoothness="bezier"
                    )
            else:
                self._draw_trajectory_sd(frame, trail_points, (0, 0, 255), thickness=2)
    
    def _render_analytics(self, frame: np.ndarray, position: Tuple[int, int], analytics: Dict):
        """Render analytics text from metadata."""
        lines = []
        
        # Priority order for analytics display (most important first)
        # Check for speed (prefer m/s, fallback to mph)
        speed_value = None
        speed_unit = "m/s"
        if "speed_mps" in analytics or "player_speed_mps" in analytics:
            speed_value = analytics.get("speed_mps") or analytics.get("player_speed_mps")
            speed_unit = "m/s"
        elif "speed_mph" in analytics or "player_speed_mph" in analytics:
            speed_value = analytics.get("speed_mph") or analytics.get("player_speed_mph")
            speed_unit = "mph"
        
        if speed_value is not None and isinstance(speed_value, (int, float)) and abs(speed_value) > 0.01:
            try:
                lines.append(f"Speed: {speed_value:.1f} {speed_unit}")
            except (ValueError, TypeError):
                lines.append(f"Speed: {speed_value} {speed_unit}")
        
        # Distance to ball
        dist_to_ball = None
        if "distance_to_ball" in analytics:
            dist_to_ball = analytics["distance_to_ball"]
        elif "distance_to_ball_px" in analytics:
            # Convert pixels to meters (rough approximation: 1px ≈ 0.05m)
            try:
                dist_to_ball = analytics["distance_to_ball_px"] * 0.05
            except (TypeError, ValueError):
                pass
        
        if dist_to_ball is not None and isinstance(dist_to_ball, (int, float)):
            try:
                if dist_to_ball < 1000:  # Show in meters if reasonable
                    lines.append(f"Ball: {dist_to_ball:.1f}m")
                else:  # Show in km if very large
                    lines.append(f"Ball: {dist_to_ball/1000:.2f}km")
            except (ValueError, TypeError):
                lines.append(f"Ball: {dist_to_ball}m")
        
        # Acceleration
        if "acceleration_mps2" in analytics or "player_acceleration_mps2" in analytics:
            accel = analytics.get("acceleration_mps2") or analytics.get("player_acceleration_mps2")
            if accel is not None and isinstance(accel, (int, float)) and abs(accel) > 0.01:
                try:
                    lines.append(f"Accel: {accel:.1f} m/s²")
                except (ValueError, TypeError):
                    lines.append(f"Accel: {accel} m/s²")
        
        # Distance traveled
        if "distance_traveled_m" in analytics or "distance_traveled" in analytics:
            dist = analytics.get("distance_traveled_m") or analytics.get("distance_traveled")
            if dist is not None and isinstance(dist, (int, float)) and dist > 0:
                try:
                    if dist < 1000:
                        lines.append(f"Dist: {dist:.1f}m")
                    else:
                        lines.append(f"Dist: {dist/1000:.2f}km")
                except (ValueError, TypeError):
                    lines.append(f"Dist: {dist}m")
        
        # Max speed
        if "max_speed_mps" in analytics or "max_speed" in analytics:
            max_speed = analytics.get("max_speed_mps") or analytics.get("max_speed")
            if max_speed is not None and isinstance(max_speed, (int, float)) and max_speed > 0:
                # Only show if we don't already have current speed
                if not lines or not any("Speed:" in str(l) for l in lines):
                    try:
                        lines.append(f"Max: {max_speed:.1f} m/s")
                    except (ValueError, TypeError):
                        lines.append(f"Max: {max_speed} m/s")
        
        # Field zone
        if "field_zone" in analytics and analytics["field_zone"]:
            zone = analytics["field_zone"]
            if isinstance(zone, str) and zone.strip():
                lines.append(f"Zone: {zone}")
            elif zone is not None:
                # Handle non-string zone values
                try:
                    lines.append(f"Zone: {str(zone)}")
                except:
                    pass
        
        # Limit to 4 lines to avoid clutter
        lines = lines[:4]
        
        # Get analytics font scale from settings (default: 0.5)
        analytics_font_scale = self.settings.get("analytics_font_scale", 0.5)
        line_height = int(15 * analytics_font_scale / 0.5)  # Scale line height with font
        
        y_offset = 0
        for line in lines:
            # Ensure line is a string (handle None, numbers, etc.)
            if line is None:
                continue
            line_str = str(line).strip()
            if not line_str:  # Skip empty strings
                continue
            
            if self.use_hd and self.hd_renderer:
                self.hd_renderer.draw_crisp_text(frame, line_str, 
                                               (position[0], position[1] + y_offset),
                                               font_scale=analytics_font_scale, color=(255, 255, 255),
                                               outline_color=(0, 0, 0))
            else:
                cv2.putText(frame, line_str, (position[0], position[1] + y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, analytics_font_scale * 0.8, (0, 0, 0), 2, cv2.LINE_AA)
                cv2.putText(frame, line_str, (position[0], position[1] + y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, analytics_font_scale * 0.8, (255, 255, 255), 1, cv2.LINE_AA)
            y_offset += line_height
    
    def _draw_trajectory_sd(self, frame: np.ndarray, points: List[Tuple[int, int]],
                           color: Tuple[int, int, int], thickness: int = 2):
        """Draw trajectory in standard definition."""
        if len(points) < 2:
            return
        
        for i in range(len(points) - 1):
            cv2.line(frame, points[i], points[i + 1], color, thickness, cv2.LINE_AA)
    
    def _draw_field_zone_sd(self, frame: np.ndarray, bounds: List[Tuple[int, int]],
                           color: Tuple[int, int, int], alpha: float = 0.3):
        """Draw field zone in standard definition."""
        if len(bounds) < 3:
            return
        
        overlay = frame.copy()
        cv2.fillPoly(overlay, [np.array(bounds, np.int32)], color)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        cv2.polylines(frame, [np.array(bounds, np.int32)], True, color, 2, cv2.LINE_AA)
    
    def _render_statistics_overlay(self, frame: np.ndarray, frame_num: int, overlay_data: Dict):
        """Render broadcast-style statistics overlays."""
        if not self.use_hd or not self.hd_renderer:
            return
        
        # Get statistics panel settings
        stats_position = self.settings.get("statistics_position", "top_left")
        default_panel_size = self.settings.get("statistics_panel_size", (250, 150))
        
        h, w = frame.shape[:2]
        
        # Calculate position and size based on setting
        # Banner positions: full width, fixed height
        # Bar positions: full height, fixed width
        # Corner positions: fixed size panel
        
        if stats_position == "top_banner":
            # Full-width banner at top
            banner_height = 120  # Fixed height for banner
            pos = (0, 0)
            panel_size = (w, banner_height)
        elif stats_position == "bottom_banner":
            # Full-width banner at bottom
            banner_height = 120  # Fixed height for banner
            pos = (0, h - banner_height)
            panel_size = (w, banner_height)
        elif stats_position == "left_bar":
            # Full-height bar on left
            bar_width = 200  # Fixed width for bar
            pos = (0, 0)
            panel_size = (bar_width, h)
        elif stats_position == "right_bar":
            # Full-height bar on right
            bar_width = 200  # Fixed width for bar
            pos = (w - bar_width, 0)
            panel_size = (bar_width, h)
        elif stats_position == "top_left":
            pos = (10, 10)
            panel_size = default_panel_size
        elif stats_position == "top_right":
            pos = (w - default_panel_size[0] - 10, 10)
            panel_size = default_panel_size
        elif stats_position == "bottom_left":
            pos = (10, h - default_panel_size[1] - 10)
            panel_size = default_panel_size
        else:  # bottom_right
            pos = (w - default_panel_size[0] - 10, h - default_panel_size[1] - 10)
            panel_size = default_panel_size
        
        # Collect statistics from overlay data
        stats = {}
        
        # Player count
        if "players" in overlay_data:
            stats["Players"] = str(len(overlay_data["players"]))
        
        # Ball position/status
        if "ball" in overlay_data and overlay_data["ball"]:
            ball = overlay_data["ball"]
            if ball.get("position"):
                stats["Ball"] = "On Field"
            else:
                stats["Ball"] = "Not Detected"
        
        # Frame/time info
        if hasattr(self.metadata, 'fps') and self.metadata.fps > 0:
            time_seconds = frame_num / self.metadata.fps
            minutes = int(time_seconds // 60)
            seconds = int(time_seconds % 60)
            stats["Time"] = f"{minutes:02d}:{seconds:02d}"
        
        # Draw panel if we have statistics
        if stats:
            # Get customizable colors and opacity from settings
            bg_color = self.settings.get("statistics_bg_color", (0, 0, 0))
            bg_alpha = self.settings.get("statistics_bg_alpha", 0.75)
            text_color = self.settings.get("statistics_text_color", (255, 255, 255))
            title_color = self.settings.get("statistics_title_color", (255, 255, 0))
            
            self.hd_renderer.draw_statistics_panel(
                frame, pos, panel_size,
                title="Match Stats", stats=stats,
                bg_color=bg_color, bg_alpha=bg_alpha,
                text_color=text_color, title_color=title_color
            )
    
    def _render_heat_map(self, frame: np.ndarray, frame_num: int, overlay_data: Dict):
        """Render player position heat map."""
        if not self.use_hd or not self.hd_renderer:
            return
        
        # Collect player positions from recent frames (last 300 frames = ~10 seconds at 30fps)
        positions = []
        lookback_frames = min(300, frame_num)
        
        for i in range(max(0, frame_num - lookback_frames), frame_num + 1):
            frame_data = self.metadata.get_frame_data(i)
            if frame_data and "players" in frame_data:
                for player in frame_data["players"]:
                    center = player.get("center")
                    if center:
                        positions.append((int(center[0]), int(center[1])))
        
        if len(positions) > 0:
            heat_map_alpha = self.settings.get("heat_map_alpha", 0.4)
            heat_map_color_scheme = self.settings.get("heat_map_color_scheme", "hot")
            self.hd_renderer.draw_heat_map(
                frame, positions, color_scheme=heat_map_color_scheme,
                alpha=heat_map_alpha, blur_radius=30
            )
    
    def _render_yolo_boxes(self, frame: np.ndarray, raw_yolo_detections: Dict):
        """Render raw YOLO detection boxes (before tracking)."""
        if raw_yolo_detections is None or not isinstance(raw_yolo_detections, dict):
            return
        
        xyxy_list = raw_yolo_detections.get('xyxy')
        if xyxy_list is None or not isinstance(xyxy_list, list) or len(xyxy_list) == 0:
            return
        
        yolo_box_color = (0, 165, 255)  # Orange in BGR
        yolo_box_thickness = 1  # Thinner than tracked boxes
        
        for xyxy in xyxy_list:
            if not isinstance(xyxy, list) or len(xyxy) != 4:
                continue
            
            try:
                x1, y1, x2, y2 = map(int, xyxy)
                # Validate coordinates
                if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0:
                    if self.use_hd and self.hd_renderer:
                        self.hd_renderer.draw_crisp_rectangle(frame, (x1, y1), (x2, y2), 
                                                             yolo_box_color, yolo_box_thickness)
                    else:
                        cv2.rectangle(frame, (x1, y1), (x2, y2), yolo_box_color, yolo_box_thickness)
            except (ValueError, TypeError) as e:
                # Skip invalid coordinates
                continue

