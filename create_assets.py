"""
Generate application icon and splash screen for Soccer Analysis Tool
"""

from PIL import Image, ImageDraw, ImageFont
import os
import math

def create_icon():
    """Create ICO file with multiple sizes for Windows taskbar"""
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    
    for size in sizes:
        # Create a new image with transparency
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw soccer ball (simplified pentagon pattern)
        center = size // 2
        radius = int(size * 0.4)
        
        # Background circle (green field)
        draw.ellipse(
            [center - radius, center - radius, center + radius, center + radius],
            fill=(34, 139, 34, 255),  # Forest green
            outline=(0, 0, 0, 255),
            width=max(1, size // 32)
        )
        
        # Soccer ball (white with black pentagons)
        ball_radius = int(radius * 0.6)
        draw.ellipse(
            [center - ball_radius, center - ball_radius, center + ball_radius, center + ball_radius],
            fill=(255, 255, 255, 255),
            outline=(0, 0, 0, 255),
            width=max(1, size // 32)
        )
        
        # Draw pentagon pattern on ball (simplified)
        if size >= 32:
            # Center pentagon
            pentagon_size = int(ball_radius * 0.3)
            points = []
            for i in range(5):
                angle = (i * 2 * 3.14159 / 5) - (3.14159 / 2)  # Start at top
                x = center + int(pentagon_size * 0.5 * 0.8 * (1 if i % 2 == 0 else 0.6))
                y = center + int(pentagon_size * 0.5 * 0.8 * (1 if i % 2 == 0 else 0.6))
                points.append((x, y))
            
            # Draw simplified pattern - just a few black shapes
            if size >= 48:
                # Draw a few black shapes to represent pentagons
                for i in range(3):
                    offset_x = int(ball_radius * 0.3 * (i - 1))
                    offset_y = int(ball_radius * 0.2 * (i % 2))
                    small_radius = max(2, size // 16)
                    draw.ellipse(
                        [center + offset_x - small_radius, center + offset_y - small_radius,
                         center + offset_x + small_radius, center + offset_y + small_radius],
                        fill=(0, 0, 0, 255)
                    )
        
        images.append(img)
    
    # Save as ICO file
    ico_path = 'soccer_analysis_icon.ico'
    images[0].save(ico_path, format='ICO', sizes=[(s, s) for s in sizes])
    print(f"Created icon: {ico_path}")
    return ico_path


def create_splash_screen():
    """Create splash screen image"""
    width, height = 800, 500
    
    # Create image with gradient background
    img = Image.new('RGB', (width, height), (20, 50, 20))
    draw = ImageDraw.Draw(img)
    
    # Draw gradient background (green field)
    for y in range(height):
        # Gradient from dark green to lighter green
        r = int(20 + (y / height) * 30)
        g = int(50 + (y / height) * 50)
        b = int(20 + (y / height) * 30)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Draw field lines (white)
    line_width = 3
    # Center line
    draw.line([(width // 2, 0), (width // 2, height)], fill=(255, 255, 255, 200), width=line_width)
    # Center circle
    center_radius = 80
    draw.ellipse(
        [(width // 2 - center_radius, height // 2 - center_radius),
         (width // 2 + center_radius, height // 2 + center_radius)],
        outline=(255, 255, 255, 200),
        width=line_width
    )
    
    # Draw soccer ball in center with proper pentagon/hexagon pattern
    ball_center = (width // 2, height // 2 - 50)
    ball_radius = 40
    
    # Draw white ball base
    draw.ellipse(
        [(ball_center[0] - ball_radius, ball_center[1] - ball_radius),
         (ball_center[0] + ball_radius, ball_center[1] + ball_radius)],
        fill=(255, 255, 255),
        outline=(0, 0, 0),
        width=2
    )
    
    # Draw soccer ball pattern (pentagons and hexagons)
    # Classic soccer ball has 12 pentagons (black) and 20 hexagons (white)
    # For simplicity, we'll draw a recognizable pattern with visible pentagons
    
    import math
    
    # Center pentagon (black)
    pentagon_size = ball_radius * 0.25
    center_pentagon_points = []
    for i in range(5):
        angle = (i * 2 * math.pi / 5) - (math.pi / 2)  # Start at top
        x = ball_center[0] + int(pentagon_size * math.cos(angle))
        y = ball_center[1] + int(pentagon_size * math.sin(angle))
        center_pentagon_points.append((x, y))
    draw.polygon(center_pentagon_points, fill=(0, 0, 0), outline=(0, 0, 0))
    
    # Draw surrounding pentagons (simplified pattern)
    # Top pentagon
    top_pentagon_size = ball_radius * 0.2
    top_center = (ball_center[0], ball_center[1] - int(ball_radius * 0.6))
    top_pentagon_points = []
    for i in range(5):
        angle = (i * 2 * math.pi / 5) - (math.pi / 2)
        x = top_center[0] + int(top_pentagon_size * math.cos(angle))
        y = top_center[1] + int(top_pentagon_size * math.sin(angle))
        top_pentagon_points.append((x, y))
    draw.polygon(top_pentagon_points, fill=(0, 0, 0), outline=(0, 0, 0))
    
    # Bottom-left pentagon
    bl_angle = math.pi * 0.4
    bl_center = (
        ball_center[0] + int(ball_radius * 0.5 * math.cos(bl_angle)),
        ball_center[1] + int(ball_radius * 0.5 * math.sin(bl_angle))
    )
    bl_pentagon_points = []
    for i in range(5):
        angle = (i * 2 * math.pi / 5) - (math.pi / 2) + bl_angle
        x = bl_center[0] + int(top_pentagon_size * math.cos(angle))
        y = bl_center[1] + int(top_pentagon_size * math.sin(angle))
        bl_pentagon_points.append((x, y))
    draw.polygon(bl_pentagon_points, fill=(0, 0, 0), outline=(0, 0, 0))
    
    # Bottom-right pentagon
    br_angle = -math.pi * 0.4
    br_center = (
        ball_center[0] + int(ball_radius * 0.5 * math.cos(br_angle)),
        ball_center[1] + int(ball_radius * 0.5 * math.sin(br_angle))
    )
    br_pentagon_points = []
    for i in range(5):
        angle = (i * 2 * math.pi / 5) - (math.pi / 2) + br_angle
        x = br_center[0] + int(top_pentagon_size * math.cos(angle))
        y = br_center[1] + int(top_pentagon_size * math.sin(angle))
        br_pentagon_points.append((x, y))
    draw.polygon(br_pentagon_points, fill=(0, 0, 0), outline=(0, 0, 0))
    
    # Add some connecting lines to show hexagon pattern
    line_color = (200, 200, 200)  # Light gray for hexagon outlines
    line_width = 1
    # Connect pentagons with lines to suggest hexagons
    draw.line([top_center, ball_center], fill=line_color, width=line_width)
    draw.line([bl_center, ball_center], fill=line_color, width=line_width)
    draw.line([br_center, ball_center], fill=line_color, width=line_width)
    
    # Title text
    try:
        # Try to use a nice font
        font_large = ImageFont.truetype("arial.ttf", 48)
        font_medium = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 16)
    except:
        # Fallback to default font
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Main title
    title = "Soccer Video Analysis Tool"
    title_bbox = draw.textbbox((0, 0), title, font=font_large)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    title_y = height // 2 + 80
    
    # Draw text with shadow
    shadow_offset = 2
    draw.text((title_x + shadow_offset, title_y + shadow_offset), title, 
              fill=(0, 0, 0, 180), font=font_large)
    draw.text((title_x, title_y), title, fill=(255, 255, 255), font=font_large)
    
    # Subtitle
    subtitle = "Professional Player Tracking & Analytics"
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=font_medium)
    subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
    subtitle_x = (width - subtitle_width) // 2
    subtitle_y = title_y + 60
    
    draw.text((subtitle_x + shadow_offset, subtitle_y + shadow_offset), subtitle,
              fill=(0, 0, 0, 180), font=font_medium)
    draw.text((subtitle_x, subtitle_y), subtitle, fill=(200, 200, 200), font=font_medium)
    
    # Version
    version = "Version 2.0"
    version_bbox = draw.textbbox((0, 0), version, font=font_small)
    version_width = version_bbox[2] - version_bbox[0]
    version_x = (width - version_width) // 2
    version_y = height - 40
    
    draw.text((version_x + shadow_offset, version_y + shadow_offset), version,
              fill=(0, 0, 0, 180), font=font_small)
    draw.text((version_x, version_y), version, fill=(150, 150, 150), font=font_small)
    
    # Loading text
    loading = "Loading..."
    loading_bbox = draw.textbbox((0, 0), loading, font=font_small)
    loading_width = loading_bbox[2] - loading_bbox[0]
    loading_x = (width - loading_width) // 2
    loading_y = height - 20
    
    draw.text((loading_x + shadow_offset, loading_y + shadow_offset), loading,
              fill=(0, 0, 0, 180), font=font_small)
    draw.text((loading_x, loading_y), loading, fill=(150, 150, 150), font=font_small)
    
    # Save splash screen
    splash_path = 'splash_screen.png'
    img.save(splash_path, 'PNG')
    print(f"Created splash screen: {splash_path}")
    return splash_path


if __name__ == "__main__":
    print("Creating application assets...")
    print("=" * 50)
    
    try:
        icon_path = create_icon()
        splash_path = create_splash_screen()
        
        print("=" * 50)
        print("Assets created successfully!")
        print(f"  - Icon: {icon_path}")
        print(f"  - Splash: {splash_path}")
        print("\nNext steps:")
        print("  1. Assets will be integrated into the application")
        print("  2. Icon will appear in taskbar and window title bar")
        print("  3. Splash screen will show on startup")
    except Exception as e:
        print(f"Error creating assets: {e}")
        import traceback
        traceback.print_exc()

