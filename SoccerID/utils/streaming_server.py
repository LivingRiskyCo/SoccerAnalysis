"""
HTTP Streaming Server for Real-Time Processed Video Feed
Serves processed frames with overlays as MJPEG stream
Enhanced with API endpoints and web dashboard
"""

import threading
import time
import cv2
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import io
import json
import os
import glob
from typing import Optional, Dict, List, Callable
from pathlib import Path


class StreamingHandler(BaseHTTPRequestHandler):
    """Enhanced HTTP request handler with API endpoints"""
    
    def __init__(self, frame_provider, stats_provider=None, events_provider=None, 
                 tracks_provider=None, tactical_provider=None, video_paths_provider=None, *args, **kwargs):
        self.frame_provider = frame_provider
        self.stats_provider = stats_provider or (lambda: {})
        self.events_provider = events_provider or (lambda: [])
        self.tracks_provider = tracks_provider or (lambda: {})
        self.tactical_provider = tactical_provider or (lambda: {})
        self.video_paths_provider = video_paths_provider or (lambda: [])
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        # Parse path without query string for routing
        path_without_query = self.path.split('?')[0]
        
        # Debug logging for route matching (only for /video routes)
        if self.path.startswith('/video'):
            print(f"🔍 Route check: path='{self.path}', path_without_query='{path_without_query}'")
        
        if path_without_query == '/' or path_without_query == '/index.html':
            self._serve_dashboard()
        elif path_without_query == '/video' or path_without_query == '/mjpegfeed':
            self._serve_mjpeg_stream()
        elif path_without_query == '/video/frame':
            # Single frame endpoint for browsers that don't support MJPEG streams
            print(f"✓ Routing to _serve_single_frame()")
            self._serve_single_frame()
        elif path_without_query.startswith('/video/'):
            # Video file streaming: /video/filename.mp4
            filename = path_without_query[7:]  # Remove '/video/'
            print(f"✓ Routing to _serve_video_file('{filename}')")
            self._serve_video_file(filename)
        elif self.path == '/api/stats':
            self._serve_json(self.stats_provider())
        elif self.path == '/api/events':
            self._serve_json(self.events_provider())
        elif self.path == '/api/tracks':
            self._serve_json(self.tracks_provider())
        elif self.path == '/api/tactical':
            self._serve_json(self.tactical_provider())
        elif self.path == '/api/videos':
            self._serve_json(self.video_paths_provider())
        elif self.path.startswith('/api/browse'):
            self._serve_browse()
        elif self.path == '/api/export_stats':
            self._handle_export_stats()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/api/overlay_config':
            self._handle_overlay_config()
        elif self.path == '/api/tag_player':
            self._handle_tag_player()
        elif self.path == '/api/remove_tag':
            self._handle_remove_tag()
        elif self.path == '/api/toggle_heatmap':
            self._handle_toggle_heatmap()
        elif self.path == '/api/toggle_possession':
            self._handle_toggle_possession()
        else:
            self.send_response(404)
            self.end_headers()
    
    def _serve_dashboard(self):
        """Serve the enhanced web dashboard HTML"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        # Add cache-busting headers to ensure fresh content
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        html_content = self._get_dashboard_html()
        self.wfile.write(html_content.encode('utf-8'))
    
    def _serve_json(self, data):
        """Serve JSON data with CORS headers"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def _serve_mjpeg_stream(self):
        """Serve MJPEG video stream"""
        print(f"📡 MJPEG stream request received from {self.client_address}")
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
        except Exception as e:
            print(f"⚠ Error sending headers: {e}")
            return
        
        try:
            consecutive_none_frames = 0
            frames_sent = 0
            consecutive_errors = 0
            while True:
                try:
                    frame = self.frame_provider()
                    if frame is None:
                        consecutive_none_frames += 1
                        consecutive_errors = 0  # Reset error count on None frames
                        # Log if we're waiting for frames (but not spam)
                        if consecutive_none_frames == 1:
                            print("⚠ Streaming server waiting for frames...")
                        elif consecutive_none_frames % 100 == 0:  # Every ~3 seconds
                            print(f"⚠ Streaming server still waiting for frames ({consecutive_none_frames} attempts, {frames_sent} frames sent so far)")
                        time.sleep(0.033)  # ~30 FPS
                        continue
                    
                    # Reset counter when we get a frame
                    if consecutive_none_frames > 0:
                        print(f"✓ Streaming server received frame: {frame.shape} (after {consecutive_none_frames} None frames)")
                        consecutive_none_frames = 0
                        consecutive_errors = 0
                
                    # Encode frame as JPEG
                    ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if not ret:
                        consecutive_errors += 1
                        if consecutive_errors < 5:
                            print(f"⚠ Failed to encode frame as JPEG")
                        continue
                    
                    # Send frame
                    try:
                        self.wfile.write(b'--jpgboundary\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', str(len(jpeg)))
                        self.end_headers()
                        self.wfile.write(jpeg.tobytes())
                        self.wfile.write(b'\r\n')
                        self.wfile.flush()  # Ensure data is sent immediately
                        
                        frames_sent += 1
                        consecutive_errors = 0
                        if frames_sent == 1:
                            print(f"✓ Streaming server sent first frame: {frame.shape}")
                        elif frames_sent % 300 == 0:  # Every 10 seconds at 30fps
                            print(f"📡 Streaming server: {frames_sent} frames sent")
                    except (ConnectionResetError, BrokenPipeError, OSError) as send_err:
                        # Client disconnected or connection error
                        print(f"📡 Client disconnected: {send_err}")
                        break
                    except Exception as send_err:
                        consecutive_errors += 1
                        if consecutive_errors < 5:
                            print(f"⚠ Error sending frame: {send_err}")
                        if consecutive_errors > 10:
                            print(f"⚠ Too many send errors, closing connection")
                            break
                        time.sleep(0.1)  # Brief pause on error
                        continue
                    
                    time.sleep(0.033)  # ~30 FPS
                except Exception as frame_err:
                    consecutive_errors += 1
                    if consecutive_errors < 5:
                        print(f"⚠ Error getting frame: {frame_err}")
                        import traceback
                        traceback.print_exc()
                    if consecutive_errors > 10:
                        print(f"⚠ Too many frame errors, closing connection")
                        break
                    time.sleep(0.1)  # Brief pause on error
                    continue
        except (ConnectionResetError, BrokenPipeError, OSError) as conn_err:
            # Client disconnected
            print(f"📡 Connection closed: {conn_err}")
        except Exception as e:
            print(f"❌ Streaming server error: {e}")
            import traceback
            traceback.print_exc()
    
    def _serve_single_frame(self):
        """Serve a single JPEG frame (for browsers that don't support MJPEG streams)"""
        print(f"📸 Single frame request received from {self.client_address}")
        try:
            frame = self.frame_provider()
            if frame is None:
                print("⚠ Single frame request: No frame available")
                self.send_response(204)  # No Content
                self.end_headers()
                return
            
            # Encode frame as JPEG
            ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                self.send_response(500)
                self.end_headers()
                return
            
            # Send single frame
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(jpeg)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(jpeg.tobytes())
            print(f"✓ Single frame sent: {frame.shape} ({len(jpeg)} bytes)")
        except Exception as e:
            print(f"⚠ Error serving single frame: {e}")
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()
    
    def _serve_video_file(self, filename):
        """Serve video file as MJPEG stream"""
        import urllib.parse
        # Decode URL-encoded filename
        filename = urllib.parse.unquote(filename)
        
        # Get video paths from provider
        video_paths = self.video_paths_provider()
        
        # Find the video file
        video_path = None
        print(f"🔍 Looking for video: {filename}")
        print(f"   Searching in {len(video_paths)} video entries")
        
        for path_info in video_paths:
            path_filename = path_info.get('filename', '')
            path_full = path_info.get('path', '')
            
            # Match by filename or full path (handle both forward and backslashes)
            normalized_filename = filename.replace('\\', '/')
            normalized_path = path_full.replace('\\', '/')
            
            # Try multiple matching strategies
            matches = (
                path_filename == filename or 
                path_filename == normalized_filename or
                normalized_path.endswith('/' + normalized_filename) or
                normalized_path.endswith('\\' + normalized_filename) or
                normalized_path.endswith('/' + filename) or
                normalized_path.endswith('\\' + filename) or
                os.path.basename(path_full) == filename or
                os.path.basename(path_full) == normalized_filename or
                os.path.basename(path_full).lower() == filename.lower() or
                path_filename.lower() == filename.lower()
            )
            
            if matches:
                video_path = path_full
                print(f"✓ Found video: {video_path}")
                break
        
        if not video_path:
            print(f"⚠ Video not found. Available filenames:")
            for i, v in enumerate(video_paths[:10]):
                print(f"   {i+1}. {v.get('filename', 'N/A')} -> {v.get('path', 'N/A')}")
        
        if not video_path or not os.path.exists(video_path):
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            error_msg = f'Video file not found: {filename}\n\n'
            error_msg += f'Searched in {len(video_paths)} video entries.\n'
            if video_paths:
                error_msg += f'Available filenames (first 5): {[v.get("filename", "N/A") for v in video_paths[:5]]}'
            self.wfile.write(error_msg.encode())
            print(f"⚠ Video not found: {filename}")
            if video_paths:
                print(f"   Available videos: {[v.get('filename', v.get('path', 'N/A')) for v in video_paths[:10]]}")
            return
        
        # Open video file
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'Could not open video file')
            return
        
        # Send MJPEG stream headers
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_time = 1.0 / fps
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    # Loop video
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                # Encode frame as JPEG
                ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ret:
                    continue
                
                # Send frame
                self.wfile.write(b'--jpgboundary\r\n')
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(jpeg)))
                self.end_headers()
                self.wfile.write(jpeg.tobytes())
                self.wfile.write(b'\r\n')
                
                time.sleep(frame_time)
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            cap.release()
    
    def _serve_browse(self):
        """Serve directory browsing API"""
        import urllib.parse
        from urllib.parse import urlparse, parse_qs
        
        try:
            # Parse query parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            path = query_params.get('path', [''])[0]
            
            if not path:
                # Return root directories
                import platform
                roots = []
                if platform.system() == 'Windows':
                    try:
                        import win32api
                        drives = win32api.GetLogicalDriveStrings()
                        drives = drives.split('\000')[:-1]
                        roots = [{'name': d, 'path': d, 'type': 'drive'} for d in drives if d]
                    except:
                        # Fallback
                        roots = [{'name': 'C:\\', 'path': 'C:\\', 'type': 'drive'}]
                        if os.path.exists('D:\\'):
                            roots.append({'name': 'D:\\', 'path': 'D:\\', 'type': 'drive'})
                else:
                    roots = [{'name': '/', 'path': '/', 'type': 'directory'}]
                
                # Add common video directories
                common_dirs = [
                    os.path.expanduser("~/Videos"),
                    os.path.expanduser("~/Documents/Videos"),
                    os.getcwd(),
                ]
                for common_dir in common_dirs:
                    if os.path.exists(common_dir):
                        roots.append({
                            'name': os.path.basename(common_dir) or common_dir,
                            'path': common_dir,
                            'type': 'directory'
                        })
                
                self._serve_json({'items': roots, 'path': '', 'parent': None})
                return
            
            # Normalize path
            if not os.path.exists(path):
                self.send_response(404)
                self._serve_json({'error': 'Path not found'})
                return
            
            if not os.path.isdir(path):
                self.send_response(400)
                self._serve_json({'error': 'Not a directory'})
                return
            
            items = []
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v']
            
            try:
                for item in sorted(os.listdir(path)):
                    item_path = os.path.join(path, item)
                    try:
                        if os.path.isdir(item_path):
                            items.append({
                                'name': item,
                                'path': item_path,
                                'type': 'directory'
                            })
                        elif os.path.isfile(item_path):
                            ext = os.path.splitext(item)[1].lower()
                            if ext in video_extensions:
                                file_size = os.path.getsize(item_path)
                                file_mtime = os.path.getmtime(item_path)
                                items.append({
                                    'name': item,
                                    'path': item_path,
                                    'type': 'file',
                                    'size': file_size,
                                    'size_mb': round(file_size / (1024 * 1024), 2),
                                    'modified': file_mtime
                                })
                    except (PermissionError, OSError):
                        continue
            except PermissionError:
                self.send_response(403)
                self._serve_json({'error': 'Permission denied'})
                return
            
            # Get parent directory
            parent = os.path.dirname(path) if path != os.path.dirname(path) else None
            
            self._serve_json({
                'items': items,
                'path': path,
                'parent': parent
            })
        except Exception as e:
            self.send_response(500)
            self._serve_json({'error': str(e)})
    
    def _handle_overlay_config(self):
        """Handle overlay config update"""
        if self.command != 'POST':
            self.send_response(405)
            self.end_headers()
            return
        
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            config = json.loads(post_data.decode('utf-8'))
            self._serve_json({'status': 'success', 'config': config})
        except Exception as e:
            self.send_response(500)
            self._serve_json({'error': str(e)})
    
    def _handle_tag_player(self):
        """Handle player tagging"""
        if self.command != 'POST':
            self.send_response(405)
            self.end_headers()
            return
        
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            self._serve_json({'status': 'success', 'tag': data})
        except Exception as e:
            self.send_response(500)
            self._serve_json({'error': str(e)})
    
    def _handle_remove_tag(self):
        """Handle tag removal"""
        if self.command != 'POST':
            self.send_response(405)
            self.end_headers()
            return
        
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            track_id = data.get('track_id')
            self._serve_json({'status': 'success', 'removed': track_id})
        except Exception as e:
            self.send_response(500)
            self._serve_json({'error': str(e)})
    
    def _handle_toggle_heatmap(self):
        """Handle heatmap toggle"""
        if self.command != 'POST':
            self.send_response(405)
            self.end_headers()
            return
        
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            enabled = data.get('enabled', False)
            self._serve_json({'status': 'success', 'enabled': enabled})
        except Exception as e:
            self.send_response(500)
            self._serve_json({'error': str(e)})
    
    def _handle_toggle_possession(self):
        """Handle possession view toggle"""
        if self.command != 'POST':
            self.send_response(405)
            self.end_headers()
            return
        
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            enabled = data.get('enabled', False)
            self._serve_json({'status': 'success', 'enabled': enabled})
        except Exception as e:
            self.send_response(500)
            self._serve_json({'error': str(e)})
    
    def _handle_export_stats(self):
        """Handle stats export"""
        try:
            stats = self.stats_provider()
            tracks = self.tracks_provider()
            events = self.events_provider()
            
            # Create CSV content
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Player', 'Track ID', 'Distance (px)', 'Speed (px/s)', 'Time (s)'])
            
            # Write player data
            for track_id, data in tracks.items():
                writer.writerow([
                    data.get('name', 'Unknown'),
                    track_id,
                    data.get('distance', 0),
                    data.get('speed', 0),
                    data.get('time', 0)
                ])
            
            csv_content = output.getvalue()
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv')
            self.send_header('Content-Disposition', 'attachment; filename=stats.csv')
            self.end_headers()
            self.wfile.write(csv_content.encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self._serve_json({'error': str(e)})
    
    def _get_dashboard_html(self):
        """Generate enhanced dashboard HTML with embedded CSS/JS"""
        return DASHBOARD_HTML
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Threading HTTP server"""
    daemon_threads = True


# Dashboard HTML template
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DSX Real-Time Soccer Analysis</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #fff;
            overflow-x: hidden;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header {
            text-align: center;
            padding: 20px 0;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            margin-bottom: 20px;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3); }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #4CAF50;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .main-content {
            display: grid;
            grid-template-columns: 1fr 350px;
            gap: 20px;
            margin-bottom: 20px;
            align-items: start;
        }
        @media (max-width: 768px) { .main-content { grid-template-columns: 1fr; } }
        .video-container {
            background: #000;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            position: relative;
            max-height: 70vh;
            min-height: 400px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .video-container img { 
            width: 100%; 
            height: auto; 
            display: block;
            max-height: 70vh;
            object-fit: contain;
        }
        .video-overlay {
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0, 0, 0, 0.7);
            padding: 10px;
            border-radius: 5px;
            font-size: 0.9em;
        }
        .video-controls {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(to top, rgba(0, 0, 0, 0.9), rgba(0, 0, 0, 0.7), transparent);
            padding: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            opacity: 0;
            transition: opacity 0.3s;
        }
        .video-container:hover .video-controls {
            opacity: 1;
        }
        .video-controls button {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            padding: 8px 12px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            transition: background 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .video-controls button:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        .video-controls button:active {
            background: rgba(255, 255, 255, 0.4);
        }
        .video-controls .play-pause-btn {
            width: 40px;
            height: 40px;
            font-size: 18px;
        }
        .video-controls .volume-control {
            display: flex;
            align-items: center;
            gap: 5px;
            flex: 0 0 auto;
        }
        .video-controls .volume-slider {
            width: 80px;
            height: 4px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 2px;
            outline: none;
            -webkit-appearance: none;
        }
        .video-controls .volume-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 12px;
            height: 12px;
            background: white;
            border-radius: 50%;
            cursor: pointer;
        }
        .video-controls .volume-slider::-moz-range-thumb {
            width: 12px;
            height: 12px;
            background: white;
            border-radius: 50%;
            cursor: pointer;
            border: none;
        }
        .video-controls .time-display {
            color: white;
            font-size: 14px;
            font-family: monospace;
            margin: 0 10px;
            min-width: 100px;
        }
        .video-controls .spacer {
            flex: 1;
        }
        .video-controls .fullscreen-btn {
            width: 40px;
            height: 40px;
        }
        .sidebar { display: flex; flex-direction: column; gap: 20px; }
        .card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        .card h2 {
            font-size: 1.3em;
            margin-bottom: 15px;
            border-bottom: 2px solid rgba(255, 255, 255, 0.3);
            padding-bottom: 10px;
        }
        .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }
        .stat-item { text-align: center; }
        .stat-value { font-size: 2em; font-weight: bold; color: #4CAF50; }
        .stat-label { font-size: 0.9em; opacity: 0.8; margin-top: 5px; }
        .player-list { max-height: 400px; overflow-y: auto; }
        .player-item {
            background: rgba(255, 255, 255, 0.05);
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }
        .player-name { font-weight: bold; margin-bottom: 5px; }
        .player-stats {
            font-size: 0.85em;
            opacity: 0.9;
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 5px;
        }
        .video-list-item {
            background: rgba(255, 255, 255, 0.08);
            padding: 12px;
            margin: 5px;
            border-radius: 5px;
            border-left: 4px solid #2196F3;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .video-list-item:hover {
            background: rgba(255, 255, 255, 0.15);
            border-left-color: #4CAF50;
            transform: translateX(3px);
        }
        .video-list-item.selected {
            background: rgba(33, 150, 243, 0.3);
            border-left-color: #4CAF50;
        }
        .video-item-name {
            font-weight: 500;
            font-size: 0.95em;
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .video-item-info {
            font-size: 0.8em;
            opacity: 0.7;
            margin-left: 10px;
            white-space: nowrap;
        }
        .video-item-play {
            margin-left: 10px;
            opacity: 0.6;
            font-size: 1.2em;
        }
        .video-list-item:hover .video-item-play {
            opacity: 1;
        }
        .event-item {
            background: rgba(255, 255, 255, 0.05);
            padding: 10px;
            margin-bottom: 8px;
            border-radius: 5px;
            border-left: 4px solid #FF9800;
            font-size: 0.9em;
        }
        .event-time { opacity: 0.7; font-size: 0.85em; }
        .tactical-view {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 5px;
            padding: 15px;
            margin-top: 10px;
        }
        .formation-display {
            font-size: 1.2em;
            text-align: center;
            padding: 10px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 5px;
        }
        .zone-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 10px;
        }
        .zone-item {
            text-align: center;
            padding: 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
        }
        .zone-label { font-size: 0.85em; opacity: 0.8; margin-bottom: 5px; }
        .zone-value { font-size: 1.5em; font-weight: bold; }
        .controls { display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }
        .btn {
            padding: 10px 20px;
            background: #4CAF50;
            border: none;
            border-radius: 5px;
            color: white;
            cursor: pointer;
            font-size: 1em;
            transition: background 0.3s;
        }
        .btn:hover { background: #45a049; }
        .btn-secondary { background: #2196F3; }
        .btn-secondary:hover { background: #0b7dda; }
        .loading { text-align: center; padding: 20px; opacity: 0.7; }
        label { cursor: pointer; user-select: none; }
        input[type="checkbox"] { margin-right: 5px; cursor: pointer; }
        input[type="range"] { cursor: pointer; }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: rgba(255, 255, 255, 0.1); border-radius: 10px; }
        ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.3); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.5); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚽ DSX Real-Time Soccer Analysis</h1>
            <p><span class="status-indicator"></span>Live Analysis Active</p>
        </div>
        <div class="main-content">
            <div class="video-container" id="videoContainer">
                <img id="videoStream" src="/video" alt="Live Video Feed" style="cursor: crosshair;" onclick="handleVideoClick(event)">
                <div class="video-overlay">
                    <div>FPS: <span id="liveFPS">0</span></div>
                    <div>Tracks: <span id="liveTracks">0</span></div>
                    <div id="taggingModeIndicator" style="display: none; background: rgba(255,165,0,0.8); padding: 5px; border-radius: 3px; margin-top: 5px;">
                        🏷️ Tagging Mode: Click a player to tag
                    </div>
                </div>
                <div class="video-controls">
                    <button class="play-pause-btn" id="playPauseBtn" onclick="togglePlayPause()" title="Play/Pause">⏸️</button>
                    <div class="volume-control">
                        <button id="muteBtn" onclick="toggleMute()" title="Mute/Unmute">🔊</button>
                        <input type="range" class="volume-slider" id="volumeSlider" min="0" max="100" value="100" oninput="setVolume(this.value)" title="Volume">
                    </div>
                    <div class="time-display" id="timeDisplay">--:-- / --:--</div>
                    <div class="spacer"></div>
                    <button onclick="toggleFullscreen()" class="fullscreen-btn" title="Fullscreen">⛶</button>
                </div>
            </div>
            <div class="sidebar">
                <div class="card">
                    <h2>📊 System Stats</h2>
                    <div class="stats-grid">
                        <div class="stat-item">
                            <div class="stat-value" id="fps">0</div>
                            <div class="stat-label">FPS</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="processingFPS">0</div>
                            <div class="stat-label">Processing</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="latency">0</div>
                            <div class="stat-label">Latency (ms)</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="detections">0</div>
                            <div class="stat-label">Detections</div>
                        </div>
                    </div>
                </div>
                <div class="card">
                    <h2>👥 Top Players</h2>
                    <div class="player-list" id="playerList">
                        <div class="loading">Loading players...</div>
                    </div>
                </div>
                <div class="card">
                    <h2>🎯 Recent Events</h2>
                    <div class="player-list" id="eventsList">
                        <div class="loading">Loading events...</div>
                    </div>
                </div>
                <div class="card">
                    <h2>📐 Tactical View</h2>
                    <div class="tactical-view">
                        <div class="formation-display" id="formation">Detecting...</div>
                        <div class="zone-stats">
                            <div class="zone-item">
                                <div class="zone-label">Defensive</div>
                                <div class="zone-value" id="defensiveZone">0%</div>
                            </div>
                            <div class="zone-item">
                                <div class="zone-label">Midfield</div>
                                <div class="zone-value" id="midfieldZone">0%</div>
                            </div>
                            <div class="zone-item">
                                <div class="zone-label">Attacking</div>
                                <div class="zone-value" id="attackingZone">0%</div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="card">
                    <h2>🎮 Overlay Controls</h2>
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="overlaySystemStats" checked onchange="updateOverlayConfig()">
                            <span>System Stats</span>
                        </label>
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="overlayTeamStats" checked onchange="updateOverlayConfig()">
                            <span>Team Stats</span>
                        </label>
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="overlayEvents" checked onchange="updateOverlayConfig()">
                            <span>Event Counts</span>
                        </label>
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="overlayPlayerStats" checked onchange="updateOverlayConfig()">
                            <span>Player Stats</span>
                        </label>
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="overlayFieldZones" onchange="updateOverlayConfig()">
                            <span>Field Zones</span>
                        </label>
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="overlayFormation" checked onchange="updateOverlayConfig()">
                            <span>Formation</span>
                        </label>
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="overlayTrails" checked onchange="updateOverlayConfig()">
                            <span>Player Trails</span>
                        </label>
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="overlayArrows" checked onchange="updateOverlayConfig()">
                            <span>Direction Arrows</span>
                        </label>
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="overlayBallTrail" checked onchange="updateOverlayConfig()">
                            <span>Ball Trail</span>
                        </label>
                    </div>
                </div>
                <div class="card">
                    <h2>👤 Player Tagging</h2>
                    <div id="taggingInfo" style="font-size: 0.85em; color: #999; margin-bottom: 10px;">
                        Click video to enable tagging, then click players
                    </div>
                    <div style="display: flex; gap: 5px; margin-bottom: 10px;">
                        <button class="btn btn-secondary" onclick="enableTagging()" style="flex: 1; font-size: 0.9em;">🏷️ Enable</button>
                        <button class="btn btn-secondary" onclick="disableTagging()" style="flex: 1; font-size: 0.9em;">✕ Disable</button>
                    </div>
                    <div id="taggedPlayers" style="max-height: 200px; overflow-y: auto; margin-bottom: 10px;">
                        <div style="padding: 10px; text-align: center; color: #999; font-size: 0.85em;">No players tagged yet</div>
                    </div>
                    <button class="btn btn-secondary" onclick="clearTags()" style="width: 100%;">Clear Tags</button>
                </div>
                <div class="card">
                    <h2>📊 Analytics</h2>
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        <button class="btn btn-secondary" onclick="exportStats()">📥 Export Stats</button>
                        <button class="btn btn-secondary" onclick="toggleHeatmap()">🔥 Toggle Heatmap</button>
                        <button class="btn btn-secondary" onclick="togglePossession()">⚽ Possession View</button>
                        <div style="margin-top: 10px;">
                            <label style="font-size: 0.85em; display: block; margin-bottom: 5px;">Overlay Opacity:</label>
                            <input type="range" id="overlayOpacity" min="0" max="100" value="80" oninput="updateOpacity(this.value)" style="width: 100%;">
                            <div style="text-align: center; font-size: 0.8em; color: #999;" id="opacityValue">80%</div>
                        </div>
                    </div>
                </div>
                <div class="card">
                    <h2>📹 Video Library</h2>
                    <div style="margin-bottom: 10px;">
                        <div id="videoBreadcrumb" style="font-size: 0.85em; color: #999; margin-bottom: 10px; display: flex; align-items: center; gap: 5px; flex-wrap: wrap;">
                            <span onclick="browsePath('')" style="cursor: pointer; color: #4CAF50;">🏠 Home</span>
                        </div>
                        <div id="videoStatus" style="font-size: 0.85em; color: #999; margin-bottom: 10px; min-height: 15px;"></div>
                        <div id="videoList" style="max-height: 300px; overflow-y: auto; border: 1px solid rgba(255,255,255,0.2); border-radius: 5px; background: rgba(0,0,0,0.2);">
                            <div style="padding: 20px; text-align: center; color: #999;">Click "Browse" to explore files</div>
                        </div>
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button class="btn btn-secondary" onclick="switchToLive()" style="flex: 1;">🔴 Live</button>
                        <button class="btn btn-secondary" onclick="browsePath('')" style="flex: 1;">📁 Browse</button>
                    </div>
                </div>
            </div>
        </div>
        <div class="controls">
            <button class="btn" onclick="refreshData()">🔄 Refresh</button>
            <button class="btn btn-secondary" id="autoRefreshBtn" onclick="toggleAutoRefresh()">⏸️ Auto-Refresh</button>
        </div>
    </div>
    <script>
        let currentMode = 'live'; // 'live' or 'video'
        let allVideos = []; // Store all videos for filtering
        let currentPath = ''; // Current directory path
        
        // Define functions on window immediately so they're available for onclick handlers
        window.browsePath = async function browsePath(path) {
            try {
                const videoList = document.getElementById('videoList');
                const statusDiv = document.getElementById('videoStatus');
                const breadcrumb = document.getElementById('videoBreadcrumb');
                
                if (!videoList) {
                    console.error('Video list element not found');
                    return;
                }
                
                // Show loading state
                videoList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">Loading...</div>';
                if (statusDiv) statusDiv.textContent = 'Browsing...';
                
                const url = path ? `/api/browse?path=${encodeURIComponent(path)}` : '/api/browse';
                const res = await fetch(url);
                if (!res.ok) {
                    throw new Error(`HTTP error! status: ${res.status}`);
                }
                
                const data = await res.json();
                if (data.error) {
                    throw new Error(data.error);
                }
                
                currentPath = data.path || '';
                
                // Update breadcrumb
                if (breadcrumb) {
                    const parts = [];
                    if (data.path) {
                        const pathParts = data.path.split(/[/\\]/).filter(p => p);
                        parts.push('<span onclick="browsePath(\'\')" style="cursor: pointer; color: #4CAF50;">🏠 Home</span>');
                        let current = '';
                        for (let i = 0; i < pathParts.length; i++) {
                            current = current ? current + (data.path.includes('\\') ? '\\' : '/') + pathParts[i] : pathParts[i];
                            if (data.path.includes('\\')) {
                                // Windows path
                                if (i === 0) {
                                    current = pathParts[i] + '\\';
                                } else {
                                    current = current;
                                }
                            }
                            const displayName = pathParts[i];
                            parts.push('<span style="color: #999;">/</span>');
                            parts.push(`<span onclick="browsePath('${current.replace(/'/g, "\\'")}')" style="cursor: pointer; color: #4CAF50;">${displayName}</span>`);
                        }
                    } else {
                        parts.push('<span style="color: #4CAF50;">🏠 Home</span>');
                    }
                    breadcrumb.innerHTML = parts.join(' ');
                }
                
                // Render items
                renderFileBrowser(data.items, data.parent);
                
                if (statusDiv) {
                    const fileCount = data.items.filter(i => i.type === 'file').length;
                    const dirCount = data.items.filter(i => i.type === 'directory' || i.type === 'drive').length;
                    statusDiv.textContent = `${fileCount} video(s), ${dirCount} folder(s)`;
                }
            } catch (error) {
                console.error('Error browsing:', error);
                const videoList = document.getElementById('videoList');
                const statusDiv = document.getElementById('videoStatus');
                if (videoList) {
                    videoList.innerHTML = '<div style="padding: 20px; text-align: center; color: #ff6b6b;">Error: ' + error.message + '</div>';
                }
                if (statusDiv) statusDiv.textContent = 'Error: ' + error.message;
            }
        }
        
        function renderFileBrowser(items, parent) {
            const videoList = document.getElementById('videoList');
            if (!videoList) return;
            
            if (!items || items.length === 0) {
                videoList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">Empty directory</div>';
                return;
            }
            
            // Separate directories and files
            const directories = items.filter(item => item.type === 'directory' || item.type === 'drive');
            const files = items.filter(item => item.type === 'file');
            
            let html = '';
            
            // Show parent directory link if available
            if (parent) {
                html += `
                    <div class="video-list-item" onclick="browsePath('${parent.replace(/'/g, "\\'")}')" style="border-left-color: #FF9800;">
                        <div class="video-item-name">📁 .. (Parent)</div>
                        <div class="video-item-info">Go up</div>
                        <div class="video-item-play">📂</div>
                    </div>
                `;
            }
            
            // Render directories first
            directories.forEach(item => {
                const safePath = item.path.replace(/'/g, "&#39;").replace(/"/g, "&quot;");
                html += `
                    <div class="video-list-item" onclick="browsePath('${safePath}')" style="border-left-color: #2196F3;">
                        <div class="video-item-name" title="${safePath}">📁 ${item.name}</div>
                        <div class="video-item-info">Folder</div>
                        <div class="video-item-play">📂</div>
                    </div>
                `;
            });
            
            // Render video files
            files.forEach(item => {
                const filename = item.name;
                const safePath = item.path.replace(/'/g, "&#39;").replace(/"/g, "&quot;");
                const safeName = filename.replace(/'/g, "&#39;").replace(/"/g, "&quot;");
                const sizeText = item.size_mb ? `${item.size_mb} MB` : '';
                
                html += `
                    <div class="video-list-item" onclick="playVideoFromPath('${safePath}', '${safeName}')" 
                         data-path="${safePath}" data-name="${safeName}">
                        <div class="video-item-name" title="${safePath}">🎬 ${filename}</div>
                        <div class="video-item-info">${sizeText}</div>
                        <div class="video-item-play">▶️</div>
                    </div>
                `;
            });
            
            videoList.innerHTML = html;
        }
        
        window.playVideoFromPath = function playVideoFromPath(fullPath, displayName) {
            if (!fullPath) {
                alert('Please select a video');
                return;
            }
            
            // Extract filename from path
            const filename = fullPath.split(/[/\\]/).pop();
            
            console.log('Loading video:', fullPath, 'filename:', filename);
            currentMode = 'video';
            streamStartTime = Date.now();
            
            const videoStream = document.getElementById('videoStream');
            if (!videoStream) {
                alert('Video stream element not found');
                return;
            }
            
            // Build video URL using full path
            const videoUrl = '/video/' + encodeURIComponent(fullPath);
            console.log('Video URL:', videoUrl);
            
            videoStream.src = videoUrl;
            isPaused = false;
            
            // Update play/pause button
            const playPauseBtn = document.getElementById('playPauseBtn');
            if (playPauseBtn) {
                playPauseBtn.textContent = '⏸️';
                playPauseBtn.title = 'Pause';
            }
            
            // Update header
            const headerText = document.querySelector('.header p');
            if (headerText) {
                headerText.innerHTML = '<span class="status-indicator"></span>Playing: ' + displayName;
            }
            
            // Highlight selected video
            document.querySelectorAll('.video-list-item').forEach(item => {
                item.classList.remove('selected');
                if (item.dataset.path === fullPath) {
                    item.classList.add('selected');
                }
            });
            
            // Handle video load errors
            videoStream.onerror = function() {
                console.error('Error loading video:', videoUrl);
                alert('Error loading video. The server may need the full path. Check console for details.');
            };
        }
        
        async function loadVideoList() {
            try {
                const videoList = document.getElementById('videoList');
                const statusDiv = document.getElementById('videoStatus');
                
                if (!videoList) {
                    console.error('Video list element not found');
                    return;
                }
                
                // Show loading state
                videoList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">Loading videos...</div>';
                if (statusDiv) statusDiv.textContent = 'Loading videos...';
                
                const res = await fetch('/api/videos');
                if (!res.ok) {
                    throw new Error(`HTTP error! status: ${res.status}`);
                }
                
                const videos = await res.json();
                console.log('Loaded videos:', videos.length);
                
                allVideos = videos; // Store for filtering
                
                if (!videos || videos.length === 0) {
                    videoList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">No videos found. Add video directories in the web server settings.</div>';
                    if (statusDiv) statusDiv.textContent = 'No videos found';
                    return;
                }
                
                // Populate list
                renderVideoList(videos);
                
                if (statusDiv) statusDiv.textContent = `${videos.length} video(s) available - Click to play`;
                console.log('Video list populated:', videos.length, 'videos');
            } catch (error) {
                console.error('Error loading videos:', error);
                const videoList = document.getElementById('videoList');
                const statusDiv = document.getElementById('videoStatus');
                if (videoList) {
                    videoList.innerHTML = '<div style="padding: 20px; text-align: center; color: #ff6b6b;">Error loading videos: ' + error.message + '</div>';
                }
                if (statusDiv) statusDiv.textContent = 'Error: ' + error.message;
            }
        }
        
        function renderVideoList(videos) {
            const videoList = document.getElementById('videoList');
            if (!videoList) return;
            
            if (videos.length === 0) {
                videoList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">No videos match your search</div>';
                return;
            }
            
            videoList.innerHTML = videos.map((video, index) => {
                const filename = video.filename || (video.path ? video.path.split(/[/\\\\]/).pop() : 'unknown');
                const displayName = video.name || filename;
                const sizeText = video.size_mb ? `${video.size_mb} MB` : '';
                const typeText = video.type ? `[${video.type}]` : '';
                
                // Escape for HTML attributes
                const safeFilename = filename.replace(/'/g, "&#39;").replace(/"/g, "&quot;");
                const safeDisplayName = displayName.replace(/'/g, "&#39;").replace(/"/g, "&quot;");
                
                return `
                    <div class="video-list-item" onclick="playVideo('${safeFilename}', '${safeDisplayName}')" 
                         data-filename="${safeFilename}" data-name="${safeDisplayName}">
                        <div class="video-item-name" title="${safeDisplayName}">${displayName}</div>
                        <div class="video-item-info">${sizeText} ${typeText}</div>
                        <div class="video-item-play">▶️</div>
                    </div>
                `;
            }).join('');
        }
        
        function filterVideoList() {
            const searchInput = document.getElementById('videoSearch');
            if (!searchInput || !allVideos) return;
            
            const searchTerm = searchInput.value.toLowerCase().trim();
            
            if (searchTerm === '') {
                renderVideoList(allVideos);
                return;
            }
            
            const filtered = allVideos.filter(video => {
                const filename = (video.filename || (video.path ? video.path.split(/[/\\\\]/).pop() : '')).toLowerCase();
                const name = (video.name || filename).toLowerCase();
                const path = (video.path || '').toLowerCase();
                return filename.includes(searchTerm) || name.includes(searchTerm) || path.includes(searchTerm);
            });
            
            renderVideoList(filtered);
        }
        
        function playVideo(filename, displayName) {
            if (!filename) {
                alert('Please select a video');
                return;
            }
            
            console.log('Loading video:', filename);
            currentMode = 'video';
            streamStartTime = Date.now(); // Reset timer for video playback
            
            const videoStream = document.getElementById('videoStream');
            if (!videoStream) {
                alert('Video stream element not found');
                return;
            }
            
            // Build video URL
            const videoUrl = '/video/' + encodeURIComponent(filename);
            console.log('Video URL:', videoUrl);
            
            videoStream.src = videoUrl;
            isPaused = false; // Ensure playing state
            
            // Update play/pause button
            const playPauseBtn = document.getElementById('playPauseBtn');
            if (playPauseBtn) {
                playPauseBtn.textContent = '⏸️';
                playPauseBtn.title = 'Pause';
            }
            
            // Update header
            const headerText = document.querySelector('.header p');
            if (headerText) {
                headerText.innerHTML = '<span class="status-indicator"></span>Playing: ' + displayName;
            }
            
            // Highlight selected video
            document.querySelectorAll('.video-list-item').forEach(item => {
                item.classList.remove('selected');
                if (item.dataset.filename === filename) {
                    item.classList.add('selected');
                }
            });
            
            // Handle video load errors
            videoStream.onerror = function() {
                console.error('Error loading video:', videoUrl);
                alert('Error loading video. Please check the console for details.');
            };
        }
        
        window.switchToLive = function switchToLive() {
            currentMode = 'live';
            document.getElementById('videoStream').src = '/video?' + new Date().getTime();
            const headerText = document.querySelector('.header p');
            if (headerText) {
                headerText.innerHTML = '<span class="status-indicator"></span>Live Analysis Active';
            }
            // Reset play/pause button
            const playPauseBtn = document.getElementById('playPauseBtn');
            if (playPauseBtn) {
                playPauseBtn.textContent = '⏸️';
                playPauseBtn.title = 'Pause';
            }
            isPaused = false;
        }
        
        // Video control variables
        let isPaused = false;
        let isMuted = false;
        let volume = 100;
        let streamStartTime = Date.now();
        
        function togglePlayPause() {
            const videoStream = document.getElementById('videoStream');
            const playPauseBtn = document.getElementById('playPauseBtn');
            
            if (!videoStream || !playPauseBtn) {
                console.error('Video stream or play/pause button not found');
                return;
            }
            
            try {
                isPaused = !isPaused;
                
                if (isPaused) {
                    // Pause: hide the image and stop loading by replacing with data URI
                    videoStream.dataset.pausedSrc = videoStream.src;
                    // Use a 1x1 transparent pixel to effectively stop the stream
                    videoStream.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                    videoStream.style.opacity = '0.5';
                    playPauseBtn.textContent = '▶️';
                    playPauseBtn.title = 'Play';
                } else {
                    // Play: restore the stream
                    videoStream.style.opacity = '1';
                    
                    // Restore from paused state or set new source
                    if (videoStream.dataset.pausedSrc && videoStream.dataset.pausedSrc !== videoStream.src) {
                        videoStream.src = videoStream.dataset.pausedSrc;
                        delete videoStream.dataset.pausedSrc;
                    } else if (currentMode === 'live') {
                        videoStream.src = '/video?' + new Date().getTime();
                    } else {
                        // For video files, get the current filename from selected item
                        const selectedItem = document.querySelector('.video-list-item.selected');
                        if (selectedItem) {
                            const filename = selectedItem.dataset.filename;
                            if (filename) {
                                videoStream.src = '/video/' + encodeURIComponent(filename);
                            }
                        } else {
                            videoStream.src = '/video?' + new Date().getTime();
                        }
                    }
                    playPauseBtn.textContent = '⏸️';
                    playPauseBtn.title = 'Pause';
                }
            } catch (error) {
                console.error('Error toggling play/pause:', error);
                // Reset state on error
                isPaused = false;
                playPauseBtn.textContent = '⏸️';
                playPauseBtn.title = 'Pause';
                if (videoStream) {
                    videoStream.style.opacity = '1';
                }
            }
        }
        
        function toggleMute() {
            const muteBtn = document.getElementById('muteBtn');
            const volumeSlider = document.getElementById('volumeSlider');
            
            if (!muteBtn || !volumeSlider) return;
            
            isMuted = !isMuted;
            
            if (isMuted) {
                muteBtn.textContent = '🔇';
                muteBtn.title = 'Unmute';
                volumeSlider.value = 0;
            } else {
                muteBtn.textContent = '🔊';
                muteBtn.title = 'Mute';
                volumeSlider.value = volume;
            }
        }
        
        function setVolume(value) {
            volume = parseInt(value);
            const muteBtn = document.getElementById('muteBtn');
            
            if (volume === 0) {
                isMuted = true;
                if (muteBtn) {
                    muteBtn.textContent = '🔇';
                    muteBtn.title = 'Unmute';
                }
            } else {
                isMuted = false;
                if (muteBtn) {
                    muteBtn.textContent = '🔊';
                    muteBtn.title = 'Mute';
                }
            }
        }
        
        function toggleFullscreen() {
            const videoContainer = document.getElementById('videoContainer');
            if (!videoContainer) return;
            
            if (!document.fullscreenElement && !document.webkitFullscreenElement && 
                !document.mozFullScreenElement && !document.msFullscreenElement) {
                // Enter fullscreen
                if (videoContainer.requestFullscreen) {
                    videoContainer.requestFullscreen();
                } else if (videoContainer.webkitRequestFullscreen) {
                    videoContainer.webkitRequestFullscreen();
                } else if (videoContainer.mozRequestFullScreen) {
                    videoContainer.mozRequestFullScreen();
                } else if (videoContainer.msRequestFullscreen) {
                    videoContainer.msRequestFullscreen();
                }
            } else {
                // Exit fullscreen
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                } else if (document.mozCancelFullScreen) {
                    document.mozCancelFullScreen();
                } else if (document.msExitFullscreen) {
                    document.msExitFullscreen();
                }
            }
        }
        
        function updateTimeDisplay() {
            const timeDisplay = document.getElementById('timeDisplay');
            if (!timeDisplay) return;
            
            if (currentMode === 'live') {
                const elapsed = Math.floor((Date.now() - streamStartTime) / 1000);
                const minutes = Math.floor(elapsed / 60);
                const seconds = elapsed % 60;
                timeDisplay.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')} / LIVE`;
            } else {
                // For video files, we can't get duration from MJPEG, so show elapsed time
                timeDisplay.textContent = '--:-- / --:--';
            }
        }
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Space bar: play/pause
            if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                e.preventDefault();
                togglePlayPause();
            }
            // F key: fullscreen
            if (e.code === 'KeyF' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                e.preventDefault();
                toggleFullscreen();
            }
            // M key: mute
            if (e.code === 'KeyM' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                e.preventDefault();
                toggleMute();
            }
        });
        
        let autoRefresh = true;
        let refreshInterval;
        function updateStats(data) {
            document.getElementById('fps').textContent = (data.fps || 0).toFixed(1);
            document.getElementById('processingFPS').textContent = (data.processing_fps || 0).toFixed(1);
            document.getElementById('latency').textContent = (data.latency_ms || 0).toFixed(1);
            document.getElementById('detections').textContent = data.detections_per_frame || 0;
            document.getElementById('liveFPS').textContent = (data.fps || 0).toFixed(1);
            document.getElementById('liveTracks').textContent = data.tracks || 0;
        }
        function updatePlayers(tracks) {
            const playerList = document.getElementById('playerList');
            if (!tracks || Object.keys(tracks).length === 0) {
                playerList.innerHTML = '<div class="loading">No players tracked</div>';
                return;
            }
            const players = Object.entries(tracks)
                .map(([id, data]) => ({
                    id, name: data.name || `Track ${id}`,
                    distance: data.distance || 0,
                    speed: data.speed || 0,
                    time: data.time || 0
                }))
                .sort((a, b) => b.distance - a.distance)
                .slice(0, 10);
            playerList.innerHTML = players.map(p => `
                <div class="player-item">
                    <div class="player-name">${p.name}</div>
                    <div class="player-stats">
                        <div>Distance: ${p.distance.toFixed(0)}px</div>
                        <div>Speed: ${p.speed.toFixed(1)} px/s</div>
                        <div>Time: ${p.time.toFixed(1)}s</div>
                    </div>
                </div>
            `).join('');
        }
        function updateEvents(events) {
            const eventsList = document.getElementById('eventsList');
            if (!events || events.length === 0) {
                eventsList.innerHTML = '<div class="loading">No recent events</div>';
                return;
            }
            eventsList.innerHTML = events.slice(0, 10).map(e => `
                <div class="event-item">
                    <div><strong>${e.type || 'Event'}</strong></div>
                    <div class="event-time">${e.player_name || 'Unknown'} - Frame ${e.frame || 0}</div>
                </div>
            `).join('');
        }
        function updateTactical(tactical) {
            if (!tactical) return;
            if (tactical.formation) {
                document.getElementById('formation').textContent = tactical.formation;
            }
            if (tactical.zones) {
                document.getElementById('defensiveZone').textContent = (tactical.zones.defensive || 0).toFixed(0) + '%';
                document.getElementById('midfieldZone').textContent = (tactical.zones.midfield || 0).toFixed(0) + '%';
                document.getElementById('attackingZone').textContent = (tactical.zones.attacking || 0).toFixed(0) + '%';
            }
        }
        async function refreshData() {
            try {
                const [statsRes, tracksRes, eventsRes, tacticalRes] = await Promise.all([
                    fetch('/api/stats'),
                    fetch('/api/tracks'),
                    fetch('/api/events'),
                    fetch('/api/tactical')
                ]);
                updateStats(await statsRes.json());
                updatePlayers(await tracksRes.json());
                updateEvents(await eventsRes.json());
                updateTactical(await tacticalRes.json());
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }
        function toggleAutoRefresh() {
            autoRefresh = !autoRefresh;
            const btn = document.getElementById('autoRefreshBtn');
            if (autoRefresh) {
                btn.textContent = '⏸️ Auto-Refresh';
                refreshInterval = setInterval(refreshData, 1000);
            } else {
                btn.textContent = '▶️ Auto-Refresh';
                clearInterval(refreshInterval);
            }
        }
        
        // Overlay configuration
        let overlayConfig = {
            show_system_stats: true,
            show_team_stats: true,
            show_event_counts: true,
            show_player_stats: true,
            show_field_zones: false,
            show_formation: true,
            show_trails: true,
            show_arrows: true,
            show_ball_trail: true,
            overlay_opacity: 0.8
        };
        
        // Player tagging
        let taggedPlayers = {};
        let taggingMode = false;
        
        // Analytics
        let heatmapEnabled = false;
        let possessionViewEnabled = false;
        
        window.updateOverlayConfig = function updateOverlayConfig() {
            overlayConfig.show_system_stats = document.getElementById('overlaySystemStats')?.checked ?? true;
            overlayConfig.show_team_stats = document.getElementById('overlayTeamStats')?.checked ?? true;
            overlayConfig.show_event_counts = document.getElementById('overlayEvents')?.checked ?? true;
            overlayConfig.show_player_stats = document.getElementById('overlayPlayerStats')?.checked ?? true;
            overlayConfig.show_field_zones = document.getElementById('overlayFieldZones')?.checked ?? false;
            overlayConfig.show_formation = document.getElementById('overlayFormation')?.checked ?? true;
            overlayConfig.show_trails = document.getElementById('overlayTrails')?.checked ?? true;
            overlayConfig.show_arrows = document.getElementById('overlayArrows')?.checked ?? true;
            overlayConfig.show_ball_trail = document.getElementById('overlayBallTrail')?.checked ?? true;
            
            // Send to server
            fetch('/api/overlay_config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(overlayConfig)
            }).catch(err => console.error('Error updating overlay config:', err));
        }
        
        window.updateOpacity = function updateOpacity(value) {
            overlayConfig.overlay_opacity = value / 100;
            const opacityValue = document.getElementById('opacityValue');
            if (opacityValue) opacityValue.textContent = value + '%';
            updateOverlayConfig();
        }
        
        window.clearTags = function clearTags() {
            taggedPlayers = {};
            updateTaggedPlayersDisplay();
        }
        
        function updateTaggedPlayersDisplay() {
            const container = document.getElementById('taggedPlayers');
            if (!container) return;
            
            const entries = Object.entries(taggedPlayers);
            if (entries.length === 0) {
                container.innerHTML = '<div style="padding: 10px; text-align: center; color: #999; font-size: 0.85em;">No players tagged yet</div>';
                return;
            }
            
            container.innerHTML = entries.map(([trackId, data]) => `
                <div style="background: rgba(255,255,255,0.05); padding: 8px; margin-bottom: 5px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>Track ${trackId}</strong>
                        <div style="font-size: 0.8em; color: #999;">${data.playerName || 'Untagged'}</div>
                    </div>
                    <button onclick="removeTag('${trackId}')" style="background: rgba(255,0,0,0.3); border: none; color: white; padding: 4px 8px; border-radius: 3px; cursor: pointer;">✕</button>
                </div>
            `).join('');
        }
        
        window.removeTag = function removeTag(trackId) {
            delete taggedPlayers[trackId];
            updateTaggedPlayersDisplay();
            // Send removal to server
            fetch('/api/remove_tag', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({track_id: trackId})
            }).catch(err => console.error('Error removing tag:', err));
        }
        
        window.exportStats = function exportStats() {
            fetch('/api/export_stats')
                .then(res => res.blob())
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'stats_' + new Date().toISOString().split('T')[0] + '.csv';
                    a.click();
                })
                .catch(err => {
                    console.error('Error exporting stats:', err);
                    alert('Error exporting stats. Check console for details.');
                });
        }
        
        window.toggleHeatmap = function toggleHeatmap() {
            heatmapEnabled = !heatmapEnabled;
            fetch('/api/toggle_heatmap', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({enabled: heatmapEnabled})
            }).catch(err => console.error('Error toggling heatmap:', err));
        }
        
        window.togglePossession = function togglePossession() {
            possessionViewEnabled = !possessionViewEnabled;
            fetch('/api/toggle_possession', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({enabled: possessionViewEnabled})
            }).catch(err => console.error('Error toggling possession view:', err));
        }
        
        window.enableTagging = function enableTagging() {
            taggingMode = true;
            const indicator = document.getElementById('taggingModeIndicator');
            if (indicator) indicator.style.display = 'block';
            const videoStream = document.getElementById('videoStream');
            if (videoStream) videoStream.style.cursor = 'crosshair';
        }
        
        window.disableTagging = function disableTagging() {
            taggingMode = false;
            const indicator = document.getElementById('taggingModeIndicator');
            if (indicator) indicator.style.display = 'none';
            const videoStream = document.getElementById('videoStream');
            if (videoStream) videoStream.style.cursor = 'default';
        }
        
        window.handleVideoClick = async function handleVideoClick(event) {
            if (!taggingMode) {
                // Enable tagging mode on first click
                enableTagging();
                return;
            }
            
            // Get click coordinates relative to video
            const videoStream = document.getElementById('videoStream');
            if (!videoStream) return;
            
            const rect = videoStream.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;
            
            // Get current tracks to find closest player
            try {
                const tracksRes = await fetch('/api/tracks');
                const tracks = await tracksRes.json();
                
                // Find closest track to click position
                let closestTrack = null;
                let minDistance = Infinity;
                
                // We'd need track positions from the API - for now, prompt for track ID
                const trackId = prompt('Enter Track ID to tag (or cancel to disable tagging):');
                if (trackId === null) {
                    disableTagging();
                    return;
                }
                
                if (trackId && trackId.trim()) {
                    const playerName = prompt('Enter player name for Track ' + trackId + ':');
                    if (playerName) {
                        taggedPlayers[trackId] = {
                            trackId: trackId,
                            playerName: playerName,
                            x: x,
                            y: y,
                            timestamp: Date.now()
                        };
                        
                        updateTaggedPlayersDisplay();
                        
                        // Send tag to server
                        fetch('/api/tag_player', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                track_id: trackId,
                                player_name: playerName,
                                x: x,
                                y: y
                            })
                        }).catch(err => console.error('Error tagging player:', err));
                    }
                }
            } catch (error) {
                console.error('Error handling video click:', error);
            }
        }
        
        // Functions are already assigned to window above when defined
        
        // Initialize on page load
        refreshData();
        browsePath(''); // Load file browser immediately
        if (autoRefresh) refreshInterval = setInterval(refreshData, 1000);
        
        // Update time display every second
        setInterval(updateTimeDisplay, 1000);
        streamStartTime = Date.now();
        
        // Handle video stream errors
        const videoStream = document.getElementById('videoStream');
        if (videoStream) {
            videoStream.onerror = function(e) {
                // Ignore errors for the transparent pixel (pause state)
                if (this.src && this.src.includes('data:image/gif')) {
                    return;
                }
                
                // Only handle errors when not paused
                if (!isPaused && this.src) {
                    console.error('Video stream error:', e);
                    if (currentMode === 'live') {
                        setTimeout(() => {
                            if (!isPaused && this.src) {
                                this.src = '/video?' + new Date().getTime();
                            }
                        }, 1000);
                    } else {
                        console.warn('Error loading video. Try selecting another video or switch to live feed.');
                    }
                }
            };
            
            // Handle video load success
            videoStream.onload = function() {
                if (!isPaused && !this.src.includes('data:image/gif')) {
                    console.log('Video stream loaded successfully');
                }
            };
        }
    </script>
</body>
</html>"""


class StreamingServer:
    """Enhanced HTTP server for streaming processed video feed with API endpoints"""
    
    def __init__(self, port=8081, frame_provider=None, stats_provider=None,
                 events_provider=None, tracks_provider=None, tactical_provider=None,
                 video_paths_provider=None):
        """
        Initialize enhanced streaming server
        
        Args:
            port: Port to serve on (default 8081)
            frame_provider: Callable that returns latest frame (numpy array)
            stats_provider: Callable that returns stats dict
            events_provider: Callable that returns events list
            tracks_provider: Callable that returns tracks dict
            tactical_provider: Callable that returns tactical data dict
            video_paths_provider: Callable that returns list of video file paths
        """
        self.port = port
        self.frame_provider = frame_provider or (lambda: None)
        self.stats_provider = stats_provider or (lambda: {})
        self.events_provider = events_provider or (lambda: [])
        self.tracks_provider = tracks_provider or (lambda: {})
        self.tactical_provider = tactical_provider or (lambda: {})
        self.video_paths_provider = video_paths_provider or (lambda: [])
        self.server = None
        self.server_thread = None
        self.is_running = False
    
    def start(self):
        """Start the enhanced streaming server"""
        if self.is_running:
            return
        
        try:
            # Create handler factory that passes all providers
            def handler_factory(*args, **kwargs):
                return StreamingHandler(
                    self.frame_provider,
                    self.stats_provider,
                    self.events_provider,
                    self.tracks_provider,
                    self.tactical_provider,
                    self.video_paths_provider,
                    *args, **kwargs
                )
            
            self.server = ThreadingHTTPServer(('0.0.0.0', self.port), handler_factory)
            self.is_running = True
            
            # Start server in separate thread
            def run_server():
                try:
                    self.server.serve_forever()
                except Exception as e:
                    print(f"⚠ Streaming server error: {e}")
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
            url = self.get_url()
            print(f"🌐 Enhanced streaming server started on port {self.port}")
            print(f"   Web Dashboard: {url}/")
            print(f"   MJPEG stream: {url}/video")
            print(f"   API endpoints: {url}/api/stats, /api/events, /api/tracks, /api/tactical")
            return True
        except Exception as e:
            print(f"⚠ Could not start streaming server: {e}")
            self.is_running = False
            return False
    
    def stop(self):
        """Stop the streaming server"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            print("⏹️  Streaming server stopped")
    
    def get_url(self):
        """Get the base URL for the server"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
            except Exception:
                local_ip = "localhost"
        return f"http://{local_ip}:{self.port}"
    
    def get_network_info(self):
        """Get network information including local and public IP addresses"""
        import socket
        info = {
            'local_ip': None,
            'public_ip': None,
            'is_private': False,
            'access_type': 'local_only'
        }
        
        # Get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            info['local_ip'] = local_ip
            
            # Check if it's a private IP
            parts = local_ip.split('.')
            if len(parts) == 4:
                first_octet = int(parts[0])
                second_octet = int(parts[1])
                
                # Check private IP ranges
                if (first_octet == 10) or \
                   (first_octet == 172 and 16 <= second_octet <= 31) or \
                   (first_octet == 192 and second_octet == 168):
                    info['is_private'] = True
                    info['access_type'] = 'local_only'
        except Exception:
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                info['local_ip'] = local_ip
            except Exception:
                info['local_ip'] = "localhost"
        
        # Try to get public IP (optional, may fail)
        try:
            import urllib.request
            import json
            # Use a free service to get public IP
            with urllib.request.urlopen('https://api.ipify.org?format=json', timeout=3) as response:
                data = json.loads(response.read().decode())
                info['public_ip'] = data.get('ip')
                if info['public_ip']:
                    info['access_type'] = 'external_possible'
        except Exception:
            # Public IP detection failed - that's okay
            pass
        
        return info

