"""
Streamlit Video Viewer with Overlays
Displays soccer analysis videos with interactive overlays on Streamlit Cloud
Works on desktop and mobile (Android/iOS) browsers
"""

import streamlit as st
import streamlit.components.v1 as components
import json
import os
from pathlib import Path
import base64
from typing import Dict, Optional, List
import tempfile

# Page config for better mobile experience
st.set_page_config(
    page_title="Soccer Analysis Viewer",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better mobile experience
st.markdown("""
<style>
    .main > div {
        padding-top: 1rem;
    }
    .stVideo {
        width: 100%;
    }
    @media (max-width: 768px) {
        .main > div {
            padding-top: 0.5rem;
        }
    }
</style>
""", unsafe_allow_html=True)


def load_overlay_metadata(metadata_path: str) -> Optional[Dict]:
    """Load overlay metadata from JSON file."""
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading metadata: {e}")
        return None


def create_video_player_html(video_url: str, overlay_data: Dict, 
                            show_players: bool = True, show_ball: bool = True,
                            show_trajectories: bool = False, show_labels: bool = True) -> str:
    """
    Create HTML/JavaScript video player with canvas overlay rendering.
    This provides frame-accurate overlay synchronization.
    """
    
    # Convert overlay data to JSON string for JavaScript
    overlay_json = json.dumps(overlay_data)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background: #000;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }}
            .video-container {{
                position: relative;
                max-width: 100%;
                width: 100%;
            }}
            #video {{
                width: 100%;
                height: auto;
                display: block;
            }}
            #canvas {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
            }}
            .controls {{
                position: absolute;
                bottom: 10px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0,0,0,0.7);
                padding: 10px;
                border-radius: 5px;
                display: flex;
                gap: 10px;
                z-index: 10;
            }}
            button {{
                padding: 8px 16px;
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }}
            button:hover {{
                background: #45a049;
            }}
        </style>
    </head>
    <body>
        <div class="video-container">
            <video id="video" controls crossorigin="anonymous">
                <source src="{video_url}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
            <canvas id="canvas"></canvas>
            <div class="controls">
                <button onclick="togglePlayPause()">⏯️ Play/Pause</button>
                <button onclick="seekFrame(-30)">⏪ -1s</button>
                <button onclick="seekFrame(30)">⏩ +1s</button>
            </div>
        </div>
        
        <script>
            const video = document.getElementById('video');
            const canvas = document.getElementById('canvas');
            const ctx = canvas.getContext('2d');
            const overlays = {overlay_json};
            
            // Canvas setup
            function resizeCanvas() {{
                canvas.width = video.videoWidth || video.clientWidth;
                canvas.height = video.videoHeight || video.clientHeight;
            }}
            
            video.addEventListener('loadedmetadata', resizeCanvas);
            video.addEventListener('resize', resizeCanvas);
            window.addEventListener('resize', resizeCanvas);
            
            // Get current frame number
            function getCurrentFrame() {{
                if (!video.duration) return 0;
                const fps = overlays.fps || 30;
                return Math.floor(video.currentTime * fps);
            }}
            
            // Draw overlays for current frame
            function drawOverlays() {{
                if (!canvas.width || !canvas.height) return;
                
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                const frameNum = getCurrentFrame();
                const frameKey = String(frameNum);
                const frameData = overlays.overlays[frameKey];
                
                if (!frameData) return;
                
                // Scale factor for canvas vs video
                const scaleX = canvas.width / (video.videoWidth || canvas.width);
                const scaleY = canvas.height / (video.videoHeight || canvas.height);
                
                // Draw players
                if ({str(show_players).lower()} && frameData.players) {{
                    frameData.players.forEach(player => {{
                        if (!player.xyxy) return;
                        const [x1, y1, x2, y2] = player.xyxy;
                        
                        // Scale coordinates
                        const sx1 = x1 * scaleX;
                        const sy1 = y1 * scaleY;
                        const sx2 = x2 * scaleX;
                        const sy2 = y2 * scaleY;
                        
                        // Draw box
                        ctx.strokeStyle = player.color || '#00FF00';
                        ctx.lineWidth = 2;
                        ctx.strokeRect(sx1, sy1, sx2 - sx1, sy2 - sy1);
                        
                        // Draw label
                        if ({str(show_labels).lower()} && player.name) {{
                            ctx.fillStyle = player.color || '#00FF00';
                            ctx.font = '14px Arial';
                            ctx.fillText(player.name, sx1, sy1 - 5);
                        }}
                    }});
                }}
                
                // Draw ball
                if ({str(show_ball).lower()} && frameData.ball && frameData.ball.position) {{
                    const [bx, by] = frameData.ball.position;
                    const sbx = bx * scaleX;
                    const sby = by * scaleY;
                    
                    ctx.beginPath();
                    ctx.arc(sbx, sby, 8, 0, 2 * Math.PI);
                    ctx.fillStyle = frameData.ball.color || '#FF0000';
                    ctx.fill();
                    ctx.strokeStyle = '#FFFFFF';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }}
                
                // Draw trajectories
                if ({str(show_trajectories).lower()} && frameData.trajectories) {{
                    frameData.trajectories.forEach(traj => {{
                        if (!traj.points || traj.points.length < 2) return;
                        
                        ctx.strokeStyle = traj.color || '#FFFF00';
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        
                        traj.points.forEach((point, idx) => {{
                            const [px, py] = point;
                            const spx = px * scaleX;
                            const spy = py * scaleY;
                            
                            if (idx === 0) {{
                                ctx.moveTo(spx, spy);
                            }} else {{
                                ctx.lineTo(spx, spy);
                            }}
                        }});
                        
                        ctx.stroke();
                    }});
                }}
            }}
            
            // Update overlays on timeupdate
            video.addEventListener('timeupdate', drawOverlays);
            video.addEventListener('seeked', drawOverlays);
            
            // Control functions
            function togglePlayPause() {{
                if (video.paused) {{
                    video.play();
                }} else {{
                    video.pause();
                }}
            }}
            
            function seekFrame(frames) {{
                const fps = overlays.fps || 30;
                video.currentTime += frames / fps;
            }}
            
            // Initial draw
            video.addEventListener('loadeddata', () => {{
                resizeCanvas();
                drawOverlays();
            }});
        </script>
    </body>
    </html>
    """
    return html


def main():
    st.title("⚽ Soccer Analysis Video Viewer")
    st.markdown("Upload your video and overlay metadata to view analysis results")
    
    # Sidebar for file uploads
    with st.sidebar:
        st.header("📁 Video Source")
        video_source = st.radio("Choose video source:", ["Upload File", "Video URL"])
        
        if video_source == "Upload File":
            video_file = st.file_uploader("Upload Video (MP4)", type=['mp4'])
            video_url = None
        else:
            video_url = st.text_input("Video URL (MP4)", 
                                     placeholder="https://example.com/video.mp4")
            video_file = None
        
        st.header("📄 Metadata")
        metadata_file = st.file_uploader("Upload Overlay Metadata (JSON)", type=['json'])
        
        st.header("🎛️ Display Options")
        show_players = st.checkbox("Show Players", value=True)
        show_ball = st.checkbox("Show Ball", value=True)
        show_trajectories = st.checkbox("Show Trajectories", value=False)
        show_labels = st.checkbox("Show Labels", value=True)
        show_yolo_boxes = st.checkbox("Show YOLO Boxes (Raw)", value=False)
    
    # Main content area
    has_video = (video_file is not None) or (video_url is not None)
    
    if has_video and metadata_file:
        # Handle video source
        if video_file:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_video:
                tmp_video.write(video_file.getbuffer())
                video_path = tmp_video.name
            video_url_for_player = None
        else:
            video_path = None
            video_url_for_player = video_url
        
        # Save metadata file temporarily
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as tmp_metadata:
            json.dump(json.loads(metadata_file.read().decode('utf-8')), tmp_metadata, indent=2)
            metadata_path = tmp_metadata.name
        
        # Load metadata
        overlay_data = load_overlay_metadata(metadata_path)
        
        if overlay_data:
            st.success(f"✅ Loaded metadata: {overlay_data.get('total_frames', 0)} frames")
            
            # Display video info
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("FPS", f"{overlay_data.get('fps', 30):.1f}")
            with col2:
                st.metric("Total Frames", overlay_data.get('total_frames', 0))
            with col3:
                frames_with_overlays = len(overlay_data.get('overlays', {}))
                st.metric("Frames with Overlays", frames_with_overlays)
            
            # Create video player with overlays using custom HTML component
            st.subheader("Video Player with Overlays")
            
            # Prepare video URL for player
            if video_file:
                # For uploaded files, convert to base64 (only for small files)
                file_size_mb = video_file.size / (1024 * 1024)
                if file_size_mb < 50:  # Only embed if < 50MB
                    with open(video_path, "rb") as f:
                        video_bytes = f.read()
                        video_b64 = base64.b64encode(video_bytes).decode()
                        video_url_for_player = f"data:video/mp4;base64,{video_b64}"
                else:
                    st.warning(f"⚠️ Video file is large ({file_size_mb:.1f}MB). For better performance, use a video URL instead.")
                    st.info("💡 Tip: Upload your video to Google Drive, Dropbox, or similar, and use the shareable link.")
                    # Fallback: try to use st.video for large files
                    with open(video_path, "rb") as f:
                        st.video(f.read())
                    video_url_for_player = None
            
            if video_url_for_player:
                # Create custom HTML video player with canvas overlays
                player_html = create_video_player_html(
                    video_url_for_player, 
                    overlay_data,
                    show_players=show_players,
                    show_ball=show_ball,
                    show_trajectories=show_trajectories,
                    show_labels=show_labels
                )
                
                # Display custom video player
                components.html(player_html, height=600, scrolling=False)
            
            # Display overlay info for current frame (if user provides frame number)
            st.subheader("Frame Information")
            frame_num = st.number_input("Frame Number", min_value=0, 
                                       max_value=overlay_data.get('total_frames', 0) - 1, 
                                       value=0, step=1)
            
            frame_key = str(frame_num)
            if frame_key in overlay_data.get('overlays', {}):
                frame_data = overlay_data['overlays'][frame_key]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Players in Frame:**")
                    if frame_data.get('players'):
                        for player in frame_data['players']:
                            st.write(f"- {player.get('name', 'Unknown')} (Track {player.get('track_id', 'N/A')})")
                    else:
                        st.write("No players detected")
                
                with col2:
                    st.write("**Ball:**")
                    if frame_data.get('ball'):
                        ball = frame_data['ball']
                        if ball.get('position'):
                            st.write(f"Position: ({ball['position'][0]:.1f}, {ball['position'][1]:.1f})")
                        if ball.get('confidence'):
                            st.write(f"Confidence: {ball['confidence']:.2f}")
                    else:
                        st.write("Ball not detected")
            
            # Note about advanced overlay rendering
            st.info("""
            **Note:** For frame-accurate overlay rendering synchronized with video playback, 
            you'll need to use a custom Streamlit component or host the video player separately.
            The current implementation shows basic video playback with frame-by-frame overlay information.
            
            For full overlay rendering, consider:
            1. Using `streamlit.components.v1.html()` with custom HTML/JavaScript
            2. Hosting a separate video player page that loads your metadata
            3. Using a video hosting service that supports custom overlays
            """)
            
            # Cleanup
            try:
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)
                if metadata_path and os.path.exists(metadata_path):
                    os.remove(metadata_path)
            except:
                pass
    
    elif has_video:
        st.warning("⚠️ Please upload metadata file")
        if video_file:
            st.video(video_file)
    
    elif metadata_file:
        st.warning("⚠️ Please provide a video source (upload or URL)")
    
    else:
        st.info("👆 Upload a video file and its corresponding overlay metadata JSON file to get started")
        
        # Show example metadata structure
        with st.expander("📋 Example Metadata Structure"):
            example_metadata = {
                "video_path": "video.mp4",
                "fps": 30.0,
                "total_frames": 1000,
                "overlays": {
                    "0": {
                        "players": [
                            {
                                "name": "Player 1",
                                "track_id": 1,
                                "xyxy": [100, 200, 150, 300],
                                "color": "#00FF00"
                            }
                        ],
                        "ball": {
                            "position": [500, 300],
                            "confidence": 0.95,
                            "color": "#FF0000"
                        }
                    }
                }
            }
            st.json(example_metadata)


if __name__ == "__main__":
    main()

