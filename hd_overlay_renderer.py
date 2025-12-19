"""
HD Overlay Renderer
High-definition rendering functions for crisp, professional overlays
Video game quality graphics with anti-aliasing, advanced blending, and effects
"""

import cv2
import numpy as np
from typing import Tuple, List, Optional, Dict
import math
from enum import Enum

# Try to import scipy for advanced spline interpolation (optional)
try:
    from scipy.interpolate import interp1d
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class BlendingMode(Enum):
    """Blending modes for video game quality graphics."""
    NORMAL = "normal"  # Standard alpha blending
    ADDITIVE = "additive"  # Additive blending (glow effects)
    SCREEN = "screen"  # Screen blending (bright overlays)
    MULTIPLY = "multiply"  # Multiply blending (shadows)
    OVERLAY = "overlay"  # Overlay blending (enhanced contrast)
    SOFT_LIGHT = "soft_light"  # Soft light blending
    HARD_LIGHT = "hard_light"  # Hard light blending (stronger than overlay)
    COLOR_DODGE = "color_dodge"  # Color dodge (brightening effect)
    COLOR_BURN = "color_burn"  # Color burn (darkening effect)
    LINEAR_DODGE = "linear_dodge"  # Linear dodge (additive with clamping)
    LINEAR_BURN = "linear_burn"  # Linear burn (subtractive with clamping)
    VIVID_LIGHT = "vivid_light"  # Vivid light (intense contrast)
    PIN_LIGHT = "pin_light"  # Pin light (sharp transitions)
    DIFFERENCE = "difference"  # Difference blending (inversion effect)
    EXCLUSION = "exclusion"  # Exclusion blending (softer difference)


class HDOverlayRenderer:
    """High-definition overlay renderer with anti-aliasing and crisp text."""
    
    def __init__(self, render_scale: float = 1.0, quality: str = "hd", 
                 enable_advanced_blending: bool = True,
                 trajectory_smoothness: str = "bezier"):
        """
        Initialize HD renderer with video game quality features.
        
        Args:
            render_scale: Scale multiplier for rendering (1.0 = original, 2.0 = 2x)
            quality: Quality preset ("sd", "hd", "4k")
            enable_advanced_blending: Enable advanced blending modes for glow effects
            trajectory_smoothness: Trajectory smoothing method ("linear", "bezier", "spline")
        """
        self.render_scale = render_scale
        self.quality = quality
        self.enable_advanced_blending = enable_advanced_blending
        self.trajectory_smoothness = trajectory_smoothness
        
        # Quality presets - enhanced for video game quality
        quality_settings = {
            "sd": {"scale": 1.0, "font_scale": 0.6, "thickness": 1, "aa": False, "shadow_layers": 1},
            "hd": {"scale": 2.0, "font_scale": 1.2, "thickness": 2, "aa": True, "shadow_layers": 3},
            "4k": {"scale": 4.0, "font_scale": 2.4, "thickness": 4, "aa": True, "shadow_layers": 5}
        }
        
        preset = quality_settings.get(quality, quality_settings["hd"])
        self.effective_scale = preset["scale"] * render_scale
        self.font_scale = preset["font_scale"] * render_scale
        self.base_thickness = preset["thickness"]
        self.use_anti_aliasing = preset["aa"]
        self.shadow_layers = preset["shadow_layers"]
        
        # Interpolation method for scaling (Lanczos for best quality)
        self.interpolation = cv2.INTER_LANCZOS4 if self.effective_scale > 1.0 else cv2.INTER_AREA
        
        # Trajectory curve cache for performance
        self._trajectory_cache = {}
    
    def scale_point(self, point: Tuple[float, float]) -> Tuple[int, int]:
        """Scale a point by the render scale."""
        return (int(point[0] * self.effective_scale), int(point[1] * self.effective_scale))
    
    def scale_size(self, size: float) -> int:
        """Scale a size by the render scale."""
        return int(size * self.effective_scale)
    
    def draw_crisp_text(self, img: np.ndarray, text: str, position: Tuple[int, int],
                       font_face: int = cv2.FONT_HERSHEY_SIMPLEX, 
                       font_scale: Optional[float] = None,
                       color: Tuple[int, int, int] = (255, 255, 255),
                       thickness: Optional[int] = None,
                       outline_color: Optional[Tuple[int, int, int]] = None,
                       outline_thickness: Optional[int] = None) -> np.ndarray:
        """
        Draw crisp, anti-aliased text with optional outline.
        
        Args:
            img: Image to draw on
            text: Text to draw
            position: (x, y) position
            font_face: OpenCV font face
            font_scale: Font scale (uses quality preset if None)
            color: Text color (BGR)
            thickness: Text thickness (uses quality preset if None)
            outline_color: Outline color (BGR) - if None, no outline
            outline_thickness: Outline thickness - if None, uses thickness + 2
        
        Returns:
            Image with text drawn
        """
        if font_scale is None:
            font_scale = self.font_scale
        if thickness is None:
            thickness = max(1, int(self.base_thickness * self.effective_scale))
        
        # Scale position
        pos = self.scale_point(position)
        
        # Draw outline first (if specified)
        if outline_color is not None:
            outline_thick = outline_thickness if outline_thickness is not None else thickness + 2
            cv2.putText(img, text, pos, font_face, font_scale, outline_color, 
                       outline_thick, cv2.LINE_AA if self.use_anti_aliasing else cv2.LINE_8)
        
        # Draw main text
        cv2.putText(img, text, pos, font_face, font_scale, color, 
                   thickness, cv2.LINE_AA if self.use_anti_aliasing else cv2.LINE_8)
        
        return img
    
    def draw_crisp_rectangle(self, img: np.ndarray, pt1: Tuple[int, int], pt2: Tuple[int, int],
                            color: Tuple[int, int, int], thickness: int = 2,
                            filled: bool = False, rounded: bool = False,
                            corner_radius: int = 5) -> np.ndarray:
        """
        Draw crisp rectangle with anti-aliasing and optional rounded corners.
        
        Args:
            img: Image to draw on
            pt1: Top-left corner (x, y)
            pt2: Bottom-right corner (x, y)
            color: Rectangle color (BGR)
            thickness: Line thickness
            filled: If True, fill the rectangle
            rounded: If True, draw rounded corners
            corner_radius: Radius of rounded corners (pixels)
        
        Returns:
            Image with rectangle drawn
        """
        pt1_scaled = self.scale_point(pt1)
        pt2_scaled = self.scale_point(pt2)
        thickness_scaled = self.scale_size(thickness)
        radius_scaled = self.scale_size(corner_radius)
        
        if rounded and radius_scaled > 0:
            # Draw rounded rectangle
            x1, y1 = pt1_scaled
            x2, y2 = pt2_scaled
            w = x2 - x1
            h = y2 - y1
            
            # Ensure radius doesn't exceed half width/height
            radius_scaled = min(radius_scaled, min(w, h) // 2)
            
            if filled:
                # Create mask for rounded rectangle
                mask = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
                self._draw_rounded_rect_mask(mask, pt1_scaled, pt2_scaled, radius_scaled, 255)
                img[mask > 0] = color
            else:
                # Draw rounded rectangle outline
                self._draw_rounded_rect_outline(img, pt1_scaled, pt2_scaled, radius_scaled, 
                                               color, thickness_scaled)
        else:
            # Standard rectangle
            if filled:
                cv2.rectangle(img, pt1_scaled, pt2_scaled, color, -1)
            else:
                cv2.rectangle(img, pt1_scaled, pt2_scaled, color, thickness_scaled,
                             cv2.LINE_AA if self.use_anti_aliasing else cv2.LINE_8)
        
        return img
    
    def _draw_rounded_rect_mask(self, mask: np.ndarray, pt1: Tuple[int, int], pt2: Tuple[int, int],
                               radius: int, fill_value: int):
        """Draw filled rounded rectangle on mask."""
        x1, y1 = pt1
        x2, y2 = pt2
        
        # Draw main rectangle
        cv2.rectangle(mask, (x1 + radius, y1), (x2 - radius, y2), fill_value, -1)
        cv2.rectangle(mask, (x1, y1 + radius), (x2, y2 - radius), fill_value, -1)
        
        # Draw rounded corners
        cv2.circle(mask, (x1 + radius, y1 + radius), radius, fill_value, -1)
        cv2.circle(mask, (x2 - radius, y1 + radius), radius, fill_value, -1)
        cv2.circle(mask, (x1 + radius, y2 - radius), radius, fill_value, -1)
        cv2.circle(mask, (x2 - radius, y2 - radius), radius, fill_value, -1)
    
    def _draw_rounded_rect_outline(self, img: np.ndarray, pt1: Tuple[int, int], pt2: Tuple[int, int],
                                   radius: int, color: Tuple[int, int, int], thickness: int):
        """Draw rounded rectangle outline."""
        x1, y1 = pt1
        x2, y2 = pt2
        
        # Draw straight edges
        cv2.line(img, (x1 + radius, y1), (x2 - radius, y1), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1 + radius, y2), (x2 - radius, y2), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1, y1 + radius), (x1, y2 - radius), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x2, y1 + radius), (x2, y2 - radius), color, thickness, cv2.LINE_AA)
        
        # Draw rounded corners
        cv2.ellipse(img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, 
                   color, thickness, cv2.LINE_AA)
        cv2.ellipse(img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, 
                   color, thickness, cv2.LINE_AA)
        cv2.ellipse(img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, 
                   color, thickness, cv2.LINE_AA)
        cv2.ellipse(img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, 
                   color, thickness, cv2.LINE_AA)
    
    def draw_gradient_rectangle(self, img: np.ndarray, pt1: Tuple[int, int], pt2: Tuple[int, int],
                               color1: Tuple[int, int, int], color2: Tuple[int, int, int],
                               direction: str = "vertical", alpha: float = 0.5,
                               rounded: bool = False, corner_radius: int = 5) -> np.ndarray:
        """
        Draw rectangle with gradient fill (broadcast-quality effect).
        
        Args:
            img: Image to draw on
            pt1: Top-left corner (x, y)
            pt2: Bottom-right corner (x, y)
            color1: Start color (BGR)
            color2: End color (BGR)
            direction: "vertical" (top to bottom) or "horizontal" (left to right)
            alpha: Opacity (0.0 to 1.0)
            rounded: If True, draw rounded corners
            corner_radius: Radius of rounded corners
        
        Returns:
            Image with gradient rectangle drawn
        """
        pt1_scaled = self.scale_point(pt1)
        pt2_scaled = self.scale_point(pt2)
        x1, y1 = pt1_scaled
        x2, y2 = pt2_scaled
        
        # Create gradient overlay
        overlay = img.copy()
        h, w = overlay.shape[:2]
        
        if direction == "vertical":
            # Vertical gradient (top to bottom)
            for y in range(y1, y2):
                t = (y - y1) / max(1, y2 - y1)
                color = tuple(int(c1 * (1 - t) + c2 * t) for c1, c2 in zip(color1, color2))
                cv2.line(overlay, (x1, y), (x2, y), color, 1)
        else:
            # Horizontal gradient (left to right)
            for x in range(x1, x2):
                t = (x - x1) / max(1, x2 - x1)
                color = tuple(int(c1 * (1 - t) + c2 * t) for c1, c2 in zip(color1, color2))
                cv2.line(overlay, (x, y1), (x, y2), color, 1)
        
        # Apply rounded corners if requested
        if rounded:
            mask = np.zeros((h, w), dtype=np.uint8)
            radius_scaled = self.scale_size(corner_radius)
            self._draw_rounded_rect_mask(mask, pt1_scaled, pt2_scaled, radius_scaled, 255)
            # Apply mask
            overlay = cv2.bitwise_and(overlay, overlay, mask=mask)
            img = cv2.bitwise_and(img, img, mask=255 - mask)
        
        # Blend with original
        cv2.addWeighted(overlay, alpha, img, 1.0 - alpha, 0, img)
        
        return img
    
    def draw_player_badge(self, img: np.ndarray, center: Tuple[int, int], radius: int,
                         text: str, text_color: Tuple[int, int, int] = (255, 255, 255),
                         bg_color: Tuple[int, int, int] = (0, 0, 0),
                         outline_color: Optional[Tuple[int, int, int]] = None,
                         outline_thickness: int = 2) -> np.ndarray:
        """
        Draw circular player number badge (broadcast-style).
        
        Args:
            img: Image to draw on
            center: Badge center (x, y)
            radius: Badge radius
            text: Text to display (usually player number)
            text_color: Text color (BGR)
            bg_color: Background color (BGR)
            outline_color: Outline color (BGR, optional)
            outline_thickness: Outline thickness
        
        Returns:
            Image with badge drawn
        """
        center_scaled = self.scale_point(center)
        radius_scaled = self.scale_size(radius)
        
        # Draw background circle
        cv2.circle(img, center_scaled, radius_scaled, bg_color, -1, cv2.LINE_AA)
        
        # Draw outline if specified
        if outline_color is not None:
            outline_thick = self.scale_size(outline_thickness)
            cv2.circle(img, center_scaled, radius_scaled, outline_color, outline_thick, cv2.LINE_AA)
        
        # Draw text centered
        font_scale = self.font_scale * 0.8  # Slightly smaller for badge
        thickness = max(1, int(self.base_thickness * self.effective_scale))
        (text_width, text_height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_BOLD, 
                                                             font_scale, thickness)
        text_x = center_scaled[0] - text_width // 2
        text_y = center_scaled[1] + text_height // 2
        
        # Draw text with outline for visibility
        if self.use_anti_aliasing:
            cv2.putText(img, text, (text_x, text_y), cv2.FONT_HERSHEY_BOLD, font_scale,
                       (0, 0, 0), thickness + 2, cv2.LINE_AA)  # Black outline
            cv2.putText(img, text, (text_x, text_y), cv2.FONT_HERSHEY_BOLD, font_scale,
                       text_color, thickness, cv2.LINE_AA)
        else:
            cv2.putText(img, text, (text_x, text_y), cv2.FONT_HERSHEY_BOLD, font_scale,
                       (0, 0, 0), thickness + 2, cv2.LINE_8)
            cv2.putText(img, text, (text_x, text_y), cv2.FONT_HERSHEY_BOLD, font_scale,
                       text_color, thickness, cv2.LINE_8)
        
        return img
    
    def draw_crisp_circle(self, img: np.ndarray, center: Tuple[int, int], radius: int,
                         color: Tuple[int, int, int], thickness: int = 2,
                         filled: bool = False) -> np.ndarray:
        """
        Draw crisp circle with anti-aliasing.
        
        Args:
            img: Image to draw on
            center: Circle center (x, y)
            radius: Circle radius
            color: Circle color (BGR)
            thickness: Line thickness (-1 for filled)
            filled: If True, fill the circle
        
        Returns:
            Image with circle drawn
        """
        center_scaled = self.scale_point(center)
        radius_scaled = self.scale_size(radius)
        thickness_scaled = -1 if filled else self.scale_size(thickness)
        
        cv2.circle(img, center_scaled, radius_scaled, color, thickness_scaled,
                  cv2.LINE_AA if self.use_anti_aliasing else cv2.LINE_8)
        
        return img
    
    def draw_crisp_line(self, img: np.ndarray, pt1: Tuple[int, int], pt2: Tuple[int, int],
                       color: Tuple[int, int, int], thickness: int = 2) -> np.ndarray:
        """
        Draw crisp line with anti-aliasing.
        
        Args:
            img: Image to draw on
            pt1: Start point (x, y)
            pt2: End point (x, y)
            color: Line color (BGR)
            thickness: Line thickness
        
        Returns:
            Image with line drawn
        """
        pt1_scaled = self.scale_point(pt1)
        pt2_scaled = self.scale_point(pt2)
        thickness_scaled = self.scale_size(thickness)
        
        cv2.line(img, pt1_scaled, pt2_scaled, color, thickness_scaled,
                cv2.LINE_AA if self.use_anti_aliasing else cv2.LINE_8)
        
        return img
    
    def draw_crisp_ellipse(self, img: np.ndarray, center: Tuple[int, int], axes: Tuple[int, int],
                          angle: float, color: Tuple[int, int, int], thickness: int = 2,
                          filled: bool = False) -> np.ndarray:
        """
        Draw crisp ellipse with anti-aliasing.
        
        Args:
            img: Image to draw on
            center: Ellipse center (x, y)
            axes: (width, height) axes
            angle: Rotation angle in degrees
            color: Ellipse color (BGR)
            thickness: Line thickness (-1 for filled)
            filled: If True, fill the ellipse
        
        Returns:
            Image with ellipse drawn
        """
        center_scaled = self.scale_point(center)
        axes_scaled = (self.scale_size(axes[0]), self.scale_size(axes[1]))
        thickness_scaled = -1 if filled else self.scale_size(thickness)
        
        cv2.ellipse(img, center_scaled, axes_scaled, angle, 0, 360, color, thickness_scaled,
                   cv2.LINE_AA if self.use_anti_aliasing else cv2.LINE_8)
        
        return img
    
    def draw_trajectory(self, img: np.ndarray, points: List[Tuple[int, int]],
                       color: Tuple[int, int, int], thickness: int = 2,
                       fade: bool = True, max_points: int = 50) -> np.ndarray:
        """
        Draw smooth trajectory line with optional fading.
        
        Args:
            img: Image to draw on
            points: List of (x, y) points
            color: Line color (BGR)
            thickness: Line thickness
            fade: If True, fade the line (recent points brighter)
            max_points: Maximum number of points to draw
        
        Returns:
            Image with trajectory drawn
        """
        if len(points) < 2:
            return img
        
        # Limit points
        points = points[-max_points:] if len(points) > max_points else points
        
        # Draw lines between points
        for i in range(len(points) - 1):
            pt1 = self.scale_point(points[i])
            pt2 = self.scale_point(points[i + 1])
            
            # Fade effect: more recent points are brighter
            if fade:
                alpha = (i + 1) / len(points)
                fade_color = tuple(int(c * alpha) for c in color)
            else:
                fade_color = color
            
            thickness_scaled = self.scale_size(thickness)
            cv2.line(img, pt1, pt2, fade_color, thickness_scaled,
                    cv2.LINE_AA if self.use_anti_aliasing else cv2.LINE_8)
        
        return img
    
    def _bezier_point(self, p0: Tuple[float, float], p1: Tuple[float, float], 
                      p2: Tuple[float, float], p3: Tuple[float, float], t: float) -> Tuple[float, float]:
        """
        Calculate a point on a cubic Bezier curve.
        
        Args:
            p0, p1, p2, p3: Control points (p0 and p3 are endpoints, p1 and p2 are control points)
            t: Parameter (0.0 to 1.0)
        
        Returns:
            (x, y) point on curve
        """
        u = 1.0 - t
        tt = t * t
        uu = u * u
        uuu = uu * u
        ttt = tt * t
        
        x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
        y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
        
        return (x, y)
    
    def _catmull_rom_point(self, p0: Tuple[float, float], p1: Tuple[float, float],
                           p2: Tuple[float, float], p3: Tuple[float, float], t: float) -> Tuple[float, float]:
        """
        Calculate a point on a Catmull-Rom spline.
        
        Args:
            p0, p1, p2, p3: Control points (p1 and p2 are endpoints, p0 and p3 control curvature)
            t: Parameter (0.0 to 1.0)
        
        Returns:
            (x, y) point on curve
        """
        t2 = t * t
        t3 = t2 * t
        
        # Catmull-Rom spline formula
        x = 0.5 * ((2 * p1[0]) + 
                   (-p0[0] + p2[0]) * t +
                   (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                   (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
        
        y = 0.5 * ((2 * p1[1]) + 
                   (-p0[1] + p2[1]) * t +
                   (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                   (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
        
        return (x, y)
    
    def _interpolate_bezier_segment(self, p0: Tuple[float, float], p1: Tuple[float, float],
                                    p2: Tuple[float, float], p3: Tuple[float, float],
                                    num_points: int = 10) -> List[Tuple[float, float]]:
        """
        Interpolate points along a Bezier curve segment.
        
        Args:
            p0, p1, p2, p3: Control points
            num_points: Number of points to generate
        
        Returns:
            List of (x, y) points along curve
        """
        points = []
        for i in range(num_points):
            t = i / (num_points - 1) if num_points > 1 else 0.0
            points.append(self._bezier_point(p0, p1, p2, p3, t))
        return points
    
    def _interpolate_catmull_rom(self, points: List[Tuple[float, float]], 
                                 num_points_per_segment: int = 10) -> List[Tuple[float, float]]:
        """
        Interpolate points using Catmull-Rom spline.
        
        Args:
            points: List of control points
            num_points_per_segment: Points per segment
        
        Returns:
            List of interpolated (x, y) points
        """
        if len(points) < 2:
            return points
        if len(points) == 2:
            return points
        
        interpolated = []
        
        # Add first point
        interpolated.append(points[0])
        
        # For each segment, use Catmull-Rom interpolation
        for i in range(len(points) - 1):
            # Get control points (use edge points for boundaries)
            p0 = points[max(0, i - 1)]
            p1 = points[i]
            p2 = points[i + 1]
            p3 = points[min(len(points) - 1, i + 2)]
            
            # Interpolate segment
            for j in range(1, num_points_per_segment):
                t = j / num_points_per_segment
                point = self._catmull_rom_point(p0, p1, p2, p3, t)
                interpolated.append(point)
        
        # Add last point
        interpolated.append(points[-1])
        
        return interpolated
    
    def _create_bezier_control_points(self, points: List[Tuple[float, float]]) -> List[Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float], Tuple[float, float]]]:
        """
        Create Bezier control points from a list of points.
        
        Args:
            points: List of (x, y) points
        
        Returns:
            List of (p0, p1, p2, p3) tuples for each segment
        """
        if len(points) < 2:
            return []
        
        segments = []
        
        for i in range(len(points) - 1):
            p0 = points[i]
            p3 = points[i + 1]
            
            # Calculate control points based on neighboring points
            if i == 0:
                # First segment: use next point for control
                if len(points) > 2:
                    direction = (points[2][0] - p0[0], points[2][1] - p0[1])
                    p1 = (p0[0] + direction[0] * 0.3, p0[1] + direction[1] * 0.3)
                else:
                    p1 = ((p0[0] + p3[0]) / 2, (p0[1] + p3[1]) / 2)
            else:
                # Use previous point for control
                direction = (p3[0] - points[i-1][0], p3[1] - points[i-1][1])
                p1 = (p0[0] + direction[0] * 0.3, p0[1] + direction[1] * 0.3)
            
            if i == len(points) - 2:
                # Last segment: use previous point for control
                if len(points) > 2:
                    direction = (p3[0] - points[i-1][0], p3[1] - points[i-1][1])
                    p2 = (p3[0] - direction[0] * 0.3, p3[1] - direction[1] * 0.3)
                else:
                    p2 = ((p0[0] + p3[0]) / 2, (p0[1] + p3[1]) / 2)
            else:
                # Use next point for control
                direction = (points[i+2][0] - p0[0], points[i+2][1] - p0[1])
                p2 = (p3[0] - direction[0] * 0.3, p3[1] - direction[1] * 0.3)
            
            segments.append((p0, p1, p2, p3))
        
        return segments
    
    def draw_smooth_trajectory(self, img: np.ndarray, points: List[Tuple[int, int]],
                              color: Tuple[int, int, int], thickness: int = 2,
                              fade: bool = True, max_points: int = 50,
                              velocities: Optional[List[Tuple[float, float]]] = None,
                              smoothness: Optional[str] = None) -> np.ndarray:
        """
        Draw smooth trajectory with Bezier or Catmull-Rom spline interpolation.
        Broadcast-quality smooth curves with velocity-based thickness and gradient fade.
        
        Args:
            img: Image to draw on
            points: List of (x, y) points
            color: Line color (BGR)
            thickness: Base line thickness
            fade: If True, fade the line (recent points brighter)
            max_points: Maximum number of points to draw
            velocities: Optional list of (vx, vy) velocity vectors for thickness scaling
            smoothness: Smoothing method ("linear", "bezier", "spline", or None for default)
        
        Returns:
            Image with smooth trajectory drawn
        """
        if len(points) < 2:
            return img
        
        # Use provided smoothness or default
        if smoothness is None:
            smoothness = self.trajectory_smoothness
        
        # Limit points
        points = points[-max_points:] if len(points) > max_points else points
        if velocities is not None:
            velocities = velocities[-max_points:] if len(velocities) > max_points else velocities
        
        # Convert to float for calculations
        float_points = [(float(p[0]), float(p[1])) for p in points]
        
        # Interpolate curve based on smoothness method
        if smoothness == "linear" or len(float_points) < 3:
            # Use original linear method
            return self.draw_trajectory(img, points, color, thickness, fade, max_points)
        
        elif smoothness == "spline" and len(float_points) >= 4:
            # Catmull-Rom spline (smooth through all points)
            # Adaptive density based on point spacing
            avg_spacing = 0
            for i in range(len(float_points) - 1):
                dx = float_points[i+1][0] - float_points[i][0]
                dy = float_points[i+1][1] - float_points[i][1]
                avg_spacing += math.sqrt(dx*dx + dy*dy)
            avg_spacing /= (len(float_points) - 1)
            
            # More points for larger spacing
            num_points_per_segment = max(5, min(20, int(avg_spacing / 10)))
            interpolated = self._interpolate_catmull_rom(float_points, num_points_per_segment)
        
        else:
            # Bezier curves (smooth segments)
            segments = self._create_bezier_control_points(float_points)
            interpolated = []
            
            for segment in segments:
                p0, p1, p2, p3 = segment
                # Adaptive density based on segment length
                dx = p3[0] - p0[0]
                dy = p3[1] - p0[1]
                segment_length = math.sqrt(dx*dx + dy*dy)
                num_points = max(5, min(15, int(segment_length / 5)))
                
                segment_points = self._interpolate_bezier_segment(p0, p1, p2, p3, num_points)
                interpolated.extend(segment_points[1:])  # Skip first point to avoid duplicates
        
        # Draw interpolated curve with fade and velocity-based thickness
        for i in range(len(interpolated) - 1):
            pt1 = self.scale_point(interpolated[i])
            pt2 = self.scale_point(interpolated[i + 1])
            
            # Calculate fade alpha
            if fade:
                # Exponential fade for smoother gradient
                alpha = math.pow((i + 1) / len(interpolated), 0.7)
                fade_color = tuple(int(c * alpha) for c in color)
            else:
                fade_color = color
            
            # Velocity-based thickness
            if velocities is not None and len(velocities) > 0:
                # Map interpolated point index back to original velocity
                vel_idx = min(i * len(velocities) // len(interpolated), len(velocities) - 1)
                velocity = velocities[vel_idx]
                speed = math.sqrt(velocity[0]**2 + velocity[1]**2)
                # Scale thickness: base + speed factor (max 2x)
                vel_thickness = int(thickness * (1.0 + min(speed / 50.0, 1.0)))
            else:
                vel_thickness = thickness
            
            thickness_scaled = self.scale_size(vel_thickness)
            cv2.line(img, pt1, pt2, fade_color, thickness_scaled,
                    cv2.LINE_AA if self.use_anti_aliasing else cv2.LINE_8)
        
        return img
    
    def draw_field_zone(self, img: np.ndarray, zone_bounds: List[Tuple[int, int]],
                       color: Tuple[int, int, int], alpha: float = 0.3) -> np.ndarray:
        """
        Draw semi-transparent field zone.
        
        Args:
            img: Image to draw on
            zone_bounds: List of (x, y) points defining zone polygon
            color: Zone color (BGR)
            alpha: Transparency (0.0 = transparent, 1.0 = opaque)
        
        Returns:
            Image with zone drawn
        """
        if len(zone_bounds) < 3:
            return img
        
        # Scale points
        scaled_points = np.array([self.scale_point(p) for p in zone_bounds], np.int32)
        
        # Create overlay
        overlay = img.copy()
        cv2.fillPoly(overlay, [scaled_points], color)
        cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
        
        # Draw outline
        cv2.polylines(img, [scaled_points], True, color, self.scale_size(2),
                     cv2.LINE_AA if self.use_anti_aliasing else cv2.LINE_8)
        
        return img
    
    def create_hd_canvas(self, width: int, height: int) -> np.ndarray:
        """
        Create high-resolution canvas for rendering.
        
        Args:
            width: Original width
            height: Original height
        
        Returns:
            High-resolution canvas
        """
        hd_width = int(width * self.effective_scale)
        hd_height = int(height * self.effective_scale)
        return np.zeros((hd_height, hd_width, 3), dtype=np.uint8)
    
    def downscale_to_original(self, hd_img: np.ndarray, original_width: int, 
                             original_height: int) -> np.ndarray:
        """
        Downscale HD image back to original resolution.
        
        Args:
            hd_img: High-resolution image
            original_width: Target width
            original_height: Target height
        
        Returns:
            Downscaled image
        """
        if self.effective_scale == 1.0:
            return hd_img
        
        return cv2.resize(hd_img, (original_width, original_height), 
                         interpolation=cv2.INTER_AREA)
    
    def draw_professional_text(self, img: np.ndarray, text: str, position: Tuple[int, int],
                              font_size: int = 24, color: Tuple[int, int, int] = (255, 255, 255),
                              outline_color: Tuple[int, int, int] = (0, 0, 0),
                              outline_width: int = 2, shadow: bool = True,
                              shadow_offset: Tuple[int, int] = (2, 2),
                              shadow_blur: int = 3, font_name: str = "arial.ttf",
                              gradient: bool = False, 
                              gradient_colors: Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = None,
                              glow: bool = False, glow_color: Optional[Tuple[int, int, int]] = None,
                              glow_intensity: float = 0.5, pulse: bool = False, pulse_phase: float = 0.0) -> np.ndarray:
        """
        Draw professional text with PIL for better quality (Stage 4).
        
        Args:
            img: Image to draw on (BGR format)
            text: Text to draw
            position: (x, y) position
            font_size: Font size in pixels
            color: Text color (BGR)
            outline_color: Outline color (BGR)
            outline_width: Outline width in pixels
            shadow: Enable drop shadow
            shadow_offset: Shadow offset (x, y)
            shadow_blur: Shadow blur radius
            font_name: Font file name (must be in system fonts or provide path)
        
        Returns:
            Image with text drawn
        """
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageFilter
        except ImportError:
            # Fallback to OpenCV if PIL not available
            return self.draw_crisp_text(img, text, position, color=color,
                                      outline_color=outline_color)
        
        # Convert BGR to RGB for PIL
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        draw = ImageDraw.Draw(pil_img)
        
        # Scale font size
        scaled_font_size = int(font_size * self.effective_scale)
        scaled_pos = (int(position[0] * self.effective_scale), 
                     int(position[1] * self.effective_scale))
        
        # Try to load font, fallback to default
        try:
            # Try system font first
            font = ImageFont.truetype(font_name, scaled_font_size)
        except (OSError, IOError):
            try:
                # Try common Windows font paths
                import os
                font_paths = [
                    "C:/Windows/Fonts/arial.ttf",
                    "C:/Windows/Fonts/calibri.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                ]
                font = None
                for path in font_paths:
                    if os.path.exists(path):
                        font = ImageFont.truetype(path, scaled_font_size)
                        break
                if font is None:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
        
        # Convert colors to RGB
        text_color_rgb = (color[2], color[1], color[0])  # BGR to RGB
        outline_color_rgb = (outline_color[2], outline_color[1], outline_color[0])
        
        # Draw shadow first (if enabled)
        if shadow:
            shadow_pos = (scaled_pos[0] + shadow_offset[0] * int(self.effective_scale),
                         scaled_pos[1] + shadow_offset[1] * int(self.effective_scale))
            # Create shadow layer
            shadow_img = Image.new('RGBA', pil_img.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_img)
            shadow_draw.text(shadow_pos, text, font=font, fill=(*outline_color_rgb, 200))
            # Blur shadow
            shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
            # Composite shadow
            pil_img = Image.alpha_composite(pil_img.convert('RGBA'), shadow_img).convert('RGB')
            draw = ImageDraw.Draw(pil_img)
        
        # Apply pulse effect if enabled
        if pulse:
            pulse_factor = 0.8 + 0.2 * (1.0 + math.sin(pulse_phase * 2 * math.pi)) / 2.0
            scaled_font_size = int(scaled_font_size * pulse_factor)
            try:
                font = ImageFont.truetype(font_name, scaled_font_size) if font_name != "arial.ttf" else font
            except:
                pass
        
        # Draw outline (multiple passes for thicker outline)
        if outline_width > 0:
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx*dx + dy*dy <= outline_width*outline_width:
                        draw.text((scaled_pos[0] + dx, scaled_pos[1] + dy), text, 
                                 font=font, fill=outline_color_rgb)
        
        # Draw main text with gradient or solid color
        if gradient and gradient_colors is not None:
            # Create gradient text
            from PIL import ImageFont
            # Get text bounding box
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = int(bbox[2] - bbox[0])
            text_height = int(bbox[3] - bbox[1])
            
            # Create gradient image
            grad_img = Image.new('RGB', (text_width, text_height), (0, 0, 0))
            grad_draw = ImageDraw.Draw(grad_img)
            
            # Draw gradient
            color1_rgb = (gradient_colors[0][2], gradient_colors[0][1], gradient_colors[0][0])  # BGR to RGB
            color2_rgb = (gradient_colors[1][2], gradient_colors[1][1], gradient_colors[1][0])
            
            for y in range(int(text_height)):
                ratio = float(y) / text_height if text_height > 0 else 0.0
                r = int(color1_rgb[0] * (1 - ratio) + color2_rgb[0] * ratio)
                g = int(color1_rgb[1] * (1 - ratio) + color2_rgb[1] * ratio)
                b = int(color1_rgb[2] * (1 - ratio) + color2_rgb[2] * ratio)
                grad_draw.line([(0, y), (text_width, y)], fill=(r, g, b))
            
            # Create text mask
            mask_img = Image.new('L', pil_img.size, 0)
            mask_draw = ImageDraw.Draw(mask_img)
            mask_draw.text(scaled_pos, text, font=font, fill=255)
            
            # Apply gradient to text
            try:
                # Try newer PIL API first (Pillow 10.0+)
                grad_img = grad_img.resize((text_width, text_height), Image.Resampling.LANCZOS)
            except (AttributeError, TypeError):
                # Fallback to older PIL API
                try:
                    grad_img = grad_img.resize((text_width, text_height), Image.LANCZOS)
                except AttributeError:
                    # Last resort: use ANTIALIAS
                    grad_img = grad_img.resize((text_width, text_height), Image.ANTIALIAS)
            grad_img.putalpha(mask_img.crop((scaled_pos[0], scaled_pos[1], 
                                           scaled_pos[0] + text_width, scaled_pos[1] + text_height)))
            pil_img.paste(grad_img, scaled_pos, grad_img)
            draw = ImageDraw.Draw(pil_img)
        else:
            # Draw solid color text
            draw.text(scaled_pos, text, font=font, fill=text_color_rgb)
        
        # Apply glow effect if enabled
        if glow:
            glow_color_rgb = (glow_color[2], glow_color[1], glow_color[0]) if glow_color else text_color_rgb
            # Create glow layer
            glow_img = Image.new('RGBA', pil_img.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            glow_draw.text(scaled_pos, text, font=font, fill=(*glow_color_rgb, int(255 * glow_intensity)))
            
            # Apply multiple blur passes for glow
            for blur_radius in [3, 5, 7]:
                blurred = glow_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
                pil_img = Image.alpha_composite(pil_img.convert('RGBA'), blurred).convert('RGB')
            draw = ImageDraw.Draw(pil_img)
        
        # Convert back to BGR numpy array
        if self.effective_scale > 1.0:
            # Downscale if needed
            original_size = (img.shape[1], img.shape[0])
            try:
                # Try newer PIL API first (Pillow 10.0+)
                pil_img = pil_img.resize(original_size, Image.Resampling.LANCZOS)
            except (AttributeError, TypeError):
                # Fallback to older PIL API
                try:
                    pil_img = pil_img.resize(original_size, Image.LANCZOS)
                except AttributeError:
                    # Last resort: use ANTIALIAS
                    pil_img = pil_img.resize(original_size, Image.ANTIALIAS)
        
        img_result = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return img_result
    
    def apply_blending_mode(self, base: np.ndarray, overlay: np.ndarray, 
                           mode: BlendingMode, alpha: float = 1.0) -> np.ndarray:
        """
        Apply advanced blending mode for video game quality effects.
        
        Args:
            base: Base image (BGR, uint8)
            overlay: Overlay image (BGR, uint8)
            mode: Blending mode
            alpha: Blend strength (0.0 to 1.0)
        
        Returns:
            Blended image
        """
        if not self.enable_advanced_blending or mode == BlendingMode.NORMAL:
            # Standard alpha blending
            return cv2.addWeighted(base, 1.0 - alpha, overlay, alpha, 0)
        
        # Convert to float for calculations
        base_f = base.astype(np.float32) / 255.0
        overlay_f = overlay.astype(np.float32) / 255.0
        
        if mode == BlendingMode.ADDITIVE:
            # Additive blending (great for glows)
            result = np.clip(base_f + overlay_f * alpha, 0, 1)
        elif mode == BlendingMode.SCREEN:
            # Screen blending (brightens base)
            result = 1.0 - (1.0 - base_f) * (1.0 - overlay_f * alpha)
        elif mode == BlendingMode.MULTIPLY:
            # Multiply blending (darkens base)
            result = base_f * (overlay_f * alpha + (1.0 - alpha))
        elif mode == BlendingMode.OVERLAY:
            # Overlay blending (enhances contrast)
            mask = base_f < 0.5
            result = np.where(mask, 
                            2.0 * base_f * overlay_f * alpha + base_f * (1.0 - alpha),
                            1.0 - 2.0 * (1.0 - base_f) * (1.0 - overlay_f * alpha))
        elif mode == BlendingMode.SOFT_LIGHT:
            # Soft light blending (subtle enhancement)
            mask = overlay_f < 0.5
            result = np.where(mask,
                            base_f - (1.0 - 2.0 * overlay_f * alpha) * base_f * (1.0 - base_f),
                            base_f + (2.0 * overlay_f * alpha - 1.0) * (np.sqrt(base_f) - base_f))
        elif mode == BlendingMode.HARD_LIGHT:
            # Hard light blending (stronger than overlay)
            mask = overlay_f < 0.5
            result = np.where(mask,
                            2.0 * base_f * overlay_f * alpha + base_f * (1.0 - alpha),
                            1.0 - 2.0 * (1.0 - base_f) * (1.0 - overlay_f * alpha))
        elif mode == BlendingMode.COLOR_DODGE:
            # Color dodge (brightening effect)
            result = np.clip(base_f / (1.0 - overlay_f * alpha + 1e-6), 0, 1)
        elif mode == BlendingMode.COLOR_BURN:
            # Color burn (darkening effect)
            result = np.clip(1.0 - (1.0 - base_f) / (overlay_f * alpha + 1e-6), 0, 1)
        elif mode == BlendingMode.LINEAR_DODGE:
            # Linear dodge (additive with clamping)
            result = np.clip(base_f + overlay_f * alpha, 0, 1)
        elif mode == BlendingMode.LINEAR_BURN:
            # Linear burn (subtractive with clamping)
            result = np.clip(base_f + overlay_f * alpha - 1.0, 0, 1)
        elif mode == BlendingMode.VIVID_LIGHT:
            # Vivid light (intense contrast)
            mask = overlay_f < 0.5
            result = np.where(mask,
                            np.clip(1.0 - (1.0 - base_f) / (2.0 * overlay_f * alpha + 1e-6), 0, 1),
                            np.clip(base_f / (2.0 * (1.0 - overlay_f * alpha) + 1e-6), 0, 1))
        elif mode == BlendingMode.PIN_LIGHT:
            # Pin light (sharp transitions)
            mask1 = overlay_f < 0.5
            mask2 = base_f < 2.0 * overlay_f * alpha
            mask3 = base_f > 2.0 * overlay_f * alpha - 1.0 + alpha
            result = np.where(mask1,
                            np.where(mask2, 2.0 * overlay_f * alpha, base_f),
                            np.where(mask3, 2.0 * overlay_f * alpha - 1.0 + alpha, base_f))
        elif mode == BlendingMode.DIFFERENCE:
            # Difference blending (inversion effect)
            result = np.abs(base_f - overlay_f * alpha)
        elif mode == BlendingMode.EXCLUSION:
            # Exclusion blending (softer difference)
            result = base_f + overlay_f * alpha - 2.0 * base_f * overlay_f * alpha
        else:
            result = base_f
        
        # Convert back to uint8
        return (np.clip(result, 0, 1) * 255).astype(np.uint8)
    
    def draw_soft_shadow(self, img: np.ndarray, shape_func, shape_args: Dict,
                        shadow_color: Tuple[int, int, int] = (0, 0, 0),
                        shadow_offset: Tuple[int, int] = (3, 3),
                        shadow_blur: int = 5, shadow_opacity: float = 0.5,
                        layers: Optional[int] = None) -> np.ndarray:
        """
        Draw soft, multi-layer shadow for depth effect.
        
        Args:
            img: Image to draw on
            shape_func: Function to draw shape (takes img, **kwargs)
            shape_args: Arguments for shape function
            shadow_color: Shadow color (BGR)
            shadow_offset: Shadow offset (x, y)
            shadow_blur: Blur radius
            shadow_opacity: Shadow opacity (0.0 to 1.0)
            layers: Number of shadow layers (uses quality preset if None)
        
        Returns:
            Image with shadow drawn
        """
        if layers is None:
            layers = self.shadow_layers
        
        # Create shadow layer
        shadow_img = np.zeros_like(img)
        
        # Draw shape on shadow layer
        shadow_args = shape_args.copy()
        shadow_args['color'] = shadow_color
        shadow_args['img'] = shadow_img
        shape_func(**shadow_args)
        
        # Apply multiple blur layers for soft shadow
        for i in range(layers):
            blur_size = shadow_blur + i * 2
            if blur_size > 0:
                shadow_img = cv2.GaussianBlur(shadow_img, (blur_size * 2 + 1, blur_size * 2 + 1), 0)
        
        # Offset shadow
        if shadow_offset != (0, 0):
            M = np.float32([[1, 0, shadow_offset[0]], [0, 1, shadow_offset[1]]])
            h, w = shadow_img.shape[:2]
            shadow_img = cv2.warpAffine(shadow_img, M, (w, h))
        
        # Blend shadow with base image
        return self.apply_blending_mode(img, shadow_img, BlendingMode.MULTIPLY, shadow_opacity)
    
    def apply_motion_blur(self, img: np.ndarray, velocity: Tuple[float, float],
                         blur_amount: float = 1.0) -> np.ndarray:
        """
        Apply motion blur based on velocity for fast-moving objects (Stage 5).
        
        Args:
            img: Image to blur
            velocity: Velocity vector (vx, vy) in pixels per frame
            blur_amount: Blur intensity multiplier
        
        Returns:
            Motion-blurred image
        """
        speed = math.sqrt(velocity[0]**2 + velocity[1]**2)
        if speed < 1.0:
            return img
        
        # Calculate blur kernel size based on speed
        kernel_size = int(speed * blur_amount * self.effective_scale)
        if kernel_size < 1:
            return img
        
        # Create motion blur kernel
        angle = math.degrees(math.atan2(velocity[1], velocity[0]))
        kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
        center = kernel_size // 2
        kernel[center, :] = 1.0 / kernel_size
        
        # Rotate kernel to match velocity direction
        M = cv2.getRotationMatrix2D((center, center), angle, 1.0)
        kernel = cv2.warpAffine(kernel, M, (kernel_size, kernel_size))
        
        # Normalize kernel
        kernel = kernel / np.sum(kernel)
        
        # Apply motion blur
        return cv2.filter2D(img, -1, kernel)
    
    def draw_glow_effect(self, img: np.ndarray, shape_func, shape_args: Dict,
                        glow_color: Tuple[int, int, int], glow_intensity: int = 50,
                        glow_layers: int = 5) -> np.ndarray:
        """
        Draw additive glow effect around shape.
        
        Args:
            img: Image to draw on
            shape_func: Function to draw shape (takes img, **kwargs)
            shape_args: Arguments for shape function
            glow_color: Glow color (BGR)
            glow_intensity: Glow intensity (0-100)
            glow_layers: Number of glow layers
        
        Returns:
            Image with glow drawn
        """
        if glow_intensity <= 0:
            return img
        
        # Create glow layer
        glow_img = np.zeros_like(img)
        
        # Draw shape on glow layer
        glow_args = shape_args.copy()
        glow_args['color'] = glow_color
        glow_args['img'] = glow_img
        shape_func(**glow_args)
        
        # Apply multiple blur layers for glow
        alpha = glow_intensity / 100.0
        for i in range(glow_layers):
            blur_size = (i + 1) * 3
            blurred = cv2.GaussianBlur(glow_img, (blur_size * 2 + 1, blur_size * 2 + 1), 0)
            layer_alpha = alpha * (1.0 - i / glow_layers) * 0.3
            img = self.apply_blending_mode(img, blurred, BlendingMode.ADDITIVE, layer_alpha)
        
        return img
    
    def draw_statistics_panel(self, img: np.ndarray, position: Tuple[int, int], 
                             size: Tuple[int, int], title: str = "", 
                             stats: Dict[str, str] = None, bg_color: Tuple[int, int, int] = (0, 0, 0),
                             bg_alpha: float = 0.75, text_color: Tuple[int, int, int] = (255, 255, 255),
                             title_color: Tuple[int, int, int] = (255, 255, 0)) -> np.ndarray:
        """
        Draw a statistics panel with semi-transparent background (reduces flashing).
        Supports corner panels, full-width banners, and full-height bars.
        
        Args:
            img: Image to draw on
            position: (x, y) top-left position
            size: (width, height) panel size
            title: Panel title
            stats: Dictionary of stat name -> value
            bg_color: Background color (BGR)
            bg_alpha: Background alpha (0.0 to 1.0) - lower values reduce flashing
            text_color: Text color (BGR)
            title_color: Title color (BGR)
        
        Returns:
            Image with panel drawn
        """
        if stats is None:
            stats = {}
        
        x, y = position
        w, h = size
        
        # Clamp to image bounds
        img_h, img_w = img.shape[:2]
        x = max(0, min(x, img_w - 1))
        y = max(0, min(y, img_h - 1))
        w = min(w, img_w - x)
        h = min(h, img_h - y)
        
        if w <= 0 or h <= 0:
            return img
        
        # Draw semi-transparent background (reduced alpha to minimize flashing)
        overlay = img.copy()
        cv2.rectangle(overlay, (x, y), (x + w, y + h), bg_color, -1)
        # Use lower alpha (0.5 instead of 0.75) to reduce flashing visibility
        alpha = min(0.5, bg_alpha * 0.67)  # Reduce by 33% to minimize flashing
        cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
        
        # Determine layout based on aspect ratio (banner = wide, bar = tall)
        is_banner = w > h * 2  # Much wider than tall = banner
        is_bar = h > w * 2  # Much taller than wide = bar
        
        # Draw title if provided
        title_y = y
        if title:
            font_scale = 0.5 * self.effective_scale
            thickness = max(1, int(self.base_thickness * 0.5))
            (text_w, text_h), baseline = cv2.getTextSize(
                title, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
            )
            title_y = y + text_h + 5
            if title_y < y + h:
                self.draw_crisp_text(img, title, (x + 5, title_y), 
                                    font_scale=font_scale, color=title_color,
                                    outline_color=(0, 0, 0))
                title_y += 10
        
        # Draw statistics with appropriate layout
        font_scale = 0.4 * self.effective_scale
        thickness = max(1, int(self.base_thickness * 0.4))
        line_height = int(15 * self.effective_scale)
        
        if is_banner:
            # Horizontal layout for banners (arrange stats side-by-side)
            stats_list = list(stats.items())
            if len(stats_list) > 0:
                # Calculate spacing for horizontal layout
                total_text_width = 0
                text_widths = []
                for stat_name, stat_value in stats_list:
                    line_text = f"{stat_name}: {stat_value}"
                    (text_w, text_h), _ = cv2.getTextSize(
                        line_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
                    )
                    text_widths.append(text_w)
                    total_text_width += text_w
                
                # Add spacing between items
                spacing = 30
                total_width = total_text_width + spacing * (len(stats_list) - 1)
                
                # Center horizontally if there's room
                start_x = x + 10
                if total_width < w - 20:
                    start_x = x + (w - total_width) // 2
                
                # Draw stats horizontally
                current_x = start_x
                for i, ((stat_name, stat_value), text_w) in enumerate(zip(stats_list, text_widths)):
                    line_text = f"{stat_name}: {stat_value}"
                    # Center vertically in banner
                    text_y = y + h // 2
                    if title:
                        text_y = title_y + line_height
                    
                    self.draw_crisp_text(img, line_text, (current_x, text_y),
                                       font_scale=font_scale, color=text_color,
                                       outline_color=(0, 0, 0))
                    current_x += text_w + spacing
        else:
            # Vertical layout for bars and corner panels
            for i, (stat_name, stat_value) in enumerate(stats.items()):
                line_y = title_y + (i + 1) * line_height
                if line_y >= y + h - 5:
                    break
                
                line_text = f"{stat_name}: {stat_value}"
                self.draw_crisp_text(img, line_text, (x + 5, line_y),
                                   font_scale=font_scale, color=text_color,
                                   outline_color=(0, 0, 0))
        
        return img

