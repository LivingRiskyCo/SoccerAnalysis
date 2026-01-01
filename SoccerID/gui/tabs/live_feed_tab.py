"""
Live Feed Tab - Real-Time Multi-Camera Analysis
Displays live camera feeds with real-time analysis
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import threading
import time
from PIL import Image, ImageTk
import numpy as np
import os
import sys
import json

# Suppress OpenCV/FFMPEG warnings globally
try:
    cv2.setLogLevel(cv2.LOG_LEVEL_SILENT)
except (AttributeError, cv2.error):
    # Older OpenCV versions don't have setLogLevel
    pass

# Suppress FFMPEG warnings by redirecting stderr for OpenCV operations
_original_stderr = sys.stderr
def suppress_opencv_warnings():
    """Context manager to suppress OpenCV/FFMPEG warnings"""
    class WarningSuppressor:
        def __enter__(self):
            self.devnull = open(os.devnull, 'w')
            sys.stderr = self.devnull
            return self
        def __exit__(self, *args):
            sys.stderr = _original_stderr
            self.devnull.close()
    return WarningSuppressor()


class LiveFeedTab:
    """Live Feed Tab for real-time multi-camera analysis"""
    
    def __init__(self, parent_gui, parent_frame):
        self.parent_gui = parent_gui
        self.parent_frame = parent_frame
        
        # Camera management
        self.cameras = {}  # {camera_id: {'name': str, 'source': any, 'enabled': bool}}
        self.camera_captures = {}  # {camera_id: cv2.VideoCapture}
        self.camera_threads = {}  # {camera_id: threading.Thread}
        self.camera_frames = {}  # {camera_id: np.ndarray}
        self.is_running = False
        
        # Layout options
        self.layout_mode = "grid"  # "grid", "pip", "split"
        self.selected_camera = None
        
        # Processing
        self.enable_tracking = True
        self.enable_reid = False
        
        # Streaming
        self.streaming_server = None
        self.streaming_enabled = False
        self.streaming_port = 8081
        self.latest_combined_frame = None  # Store latest combined frame for streaming
        
        # Recent camera IPs (last 4)
        self.recent_camera_ips = []
        self._load_recent_ips()
        
        self.create_tab()
    
    def create_tab(self):
        """Create the live feed tab UI"""
        # Main container
        main_container = ttk.Frame(self.parent_frame, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_container, text="📺 Live Feed - Multi-Camera Analysis", 
                               font=("Segoe UI", 18, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Control panel
        control_frame = ttk.LabelFrame(main_container, text="Camera Controls", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Camera selection
        camera_select_frame = ttk.Frame(control_frame)
        camera_select_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(camera_select_frame, text="Camera Source:").pack(side=tk.LEFT, padx=(0, 10))
        self.camera_source_var = tk.StringVar(value="")
        # Use Combobox to allow selecting from recent IPs
        self.camera_source_combobox = ttk.Combobox(camera_select_frame, textvariable=self.camera_source_var, 
                                                    width=30, values=self.recent_camera_ips)
        self.camera_source_combobox.pack(side=tk.LEFT, padx=(0, 10))
        # Allow typing new values
        self.camera_source_combobox['state'] = 'normal'
        help_label = ttk.Label(camera_select_frame, 
                               text="(USB: 0,1,2... | HTTP: http://ip:8080/video | RTSP: rtsp://ip:8080/stream)",
                               font=("Arial", 8), foreground="gray")
        help_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Scan for cameras button
        ttk.Button(camera_select_frame, text="🔍 Scan Network", 
                  command=self.scan_for_cameras).pack(side=tk.LEFT, padx=(0, 5))
        
        # Add camera button
        ttk.Button(camera_select_frame, text="➕ Add Camera", 
                  command=self.add_camera).pack(side=tk.LEFT, padx=(5, 0))
        
        # Layout selection
        layout_frame = ttk.Frame(control_frame)
        layout_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(layout_frame, text="Layout:").pack(side=tk.LEFT, padx=(0, 10))
        self.layout_var = tk.StringVar(value="grid")
        layout_options = [("Grid", "grid"), ("Picture-in-Picture", "pip"), ("Split Screen", "split")]
        for text, value in layout_options:
            ttk.Radiobutton(layout_frame, text=text, variable=self.layout_var, 
                           value=value, command=self.change_layout).pack(side=tk.LEFT, padx=(0, 10))
        
        # Control buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X)
        
        self.start_button = ttk.Button(button_frame, text="▶️ Start Live Feed", 
                                       command=self.start_feed)
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="⏹️ Stop", 
                                      command=self.stop_feed, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Streaming toggle
        self.streaming_var = tk.BooleanVar(value=True)  # Enable streaming by default
        streaming_check = ttk.Checkbutton(button_frame, text="🌐 Stream to Web", 
                                          variable=self.streaming_var)
        streaming_check.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="⚙️ Settings", 
                  command=self.open_settings).pack(side=tk.LEFT)
        
        # Camera list
        list_frame = ttk.LabelFrame(main_container, text="Active Cameras", padding="10")
        list_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Listbox with scrollbar
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.camera_listbox = tk.Listbox(list_container, height=4, yscrollcommand=scrollbar.set)
        self.camera_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.camera_listbox.yview)
        
        self.camera_listbox.bind('<<ListboxSelect>>', self.on_camera_select)
        
        # Remove camera button
        ttk.Button(list_frame, text="➖ Remove Selected Camera", 
                  command=self.remove_camera).pack(pady=(5, 0))
        
        # Video display area
        display_frame = ttk.LabelFrame(main_container, text="Live Feed", padding="10")
        display_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas for video display
        self.video_canvas = tk.Canvas(display_frame, bg='black', width=1280, height=720)
        self.video_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_label = ttk.Label(main_container, text="Ready - No cameras active", 
                                     relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X, pady=(10, 0))
    
    def _open_http_stream_like_realtime(self, url):
        """Open HTTP stream using the same method as RealTimeProcessor"""
        # Normalize URL - ensure it has a path
        if url.endswith(':8080') or url.endswith(':8080/'):
            # Try common IP Webcam endpoints
            base_url = url.rstrip('/')
            urls_to_try = [
                f"{base_url}/video",           # Standard MJPEG endpoint
                f"{base_url}/mjpegfeed",       # Alternative MJPEG endpoint
                f"{base_url}/shot.jpg",        # Single frame endpoint (fallback)
                url                            # Original URL
            ]
        elif '/video' not in url and '/mjpegfeed' not in url and '/shot.jpg' not in url:
            # URL doesn't have an endpoint, try adding common ones
            base_url = url.rstrip('/')
            urls_to_try = [
                f"{base_url}/video",
                f"{base_url}/mjpegfeed",
                url
            ]
        else:
            urls_to_try = [url]
        
        # Try FFmpeg backend first (more reliable for HTTP streams)
        for test_url in urls_to_try:
            try:
                cap = cv2.VideoCapture(test_url, cv2.CAP_FFMPEG)
                
                # Set timeout and buffer properties before checking if opened
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                if cap.isOpened():
                    # Try to read a frame to verify it works
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        return cap
                    else:
                        cap.release()
            except Exception as e:
                if 'cap' in locals() and cap:
                    cap.release()
                continue
        
        # If FFmpeg failed, try default backend
        for test_url in urls_to_try:
            try:
                cap = cv2.VideoCapture(test_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        return cap
                    else:
                        cap.release()
            except Exception as e:
                if 'cap' in locals() and cap:
                    cap.release()
                continue
        
        return None
    
    def scan_for_cameras(self):
        """Scan network for IP webcam cameras"""
        try:
            from SoccerID.utils.phone_camera_helper import PhoneCameraHelper
            helper = PhoneCameraHelper()
            
            self.update_status("Scanning network for cameras...")
            self.parent_frame.update()
            
            detected = helper.scan_local_network(timeout=0.5)
            
            if not detected:
                messagebox.showinfo("No Cameras Found", 
                                  "No IP webcam cameras found on the network.\n\n"
                                  "Make sure:\n"
                                  "• IP Webcam app is running on phones\n"
                                  "• Phones are on the same WiFi network\n"
                                  "• Firewall allows connections")
                self.update_status("Scan complete - no cameras found")
                return
            
            # Show selection dialog
            scan_window = tk.Toplevel(self.parent_frame)
            scan_window.title("Detected Cameras")
            scan_window.geometry("500x400")
            scan_window.transient(self.parent_frame)
            
            ttk.Label(scan_window, text="Select cameras to add:", 
                     font=("Arial", 10, "bold")).pack(pady=10)
            
            # Listbox for detected cameras
            list_frame = ttk.Frame(scan_window)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            camera_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, selectmode=tk.EXTENDED)
            camera_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=camera_listbox.yview)
            
            for cam in detected:
                url = cam.get('url', cam.get('http_url', ''))
                name = cam.get('name', url)
                camera_listbox.insert(tk.END, f"{name} - {url}")
            
            def add_selected():
                selected = camera_listbox.curselection()
                if not selected:
                    messagebox.showwarning("No Selection", "Please select at least one camera")
                    return
                
                added_count = 0
                for idx in selected:
                    cam = detected[idx]
                    url = cam.get('url', cam.get('http_url', ''))
                    if url:
                        self.camera_source_var.set(url)
                        self.add_camera_silent(url)
                        added_count += 1
                
                scan_window.destroy()
                self.update_status(f"Added {added_count} camera(s)")
                messagebox.showinfo("Success", f"Added {added_count} camera(s) to the feed")
            
            button_frame = ttk.Frame(scan_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)
            
            ttk.Button(button_frame, text="Add Selected", command=add_selected).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=scan_window.destroy).pack(side=tk.LEFT, padx=5)
            
        except ImportError:
            messagebox.showerror("Error", "Camera scanning not available. Please enter camera URLs manually.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan for cameras: {e}")
            self.update_status("Scan failed")
    
    def add_camera_silent(self, source_str):
        """Add camera without showing dialogs (used by scan)"""
        # Parse source (int for USB, str for URL)
        try:
            if source_str.isdigit():
                source = int(source_str)
                camera_name = f"USB Camera {source}"
            else:
                source = source_str
                # Extract IP from URL for cleaner name
                if '://' in source_str:
                    parts = source_str.split('://')
                    if len(parts) > 1:
                        ip_part = parts[1].split('/')[0].split(':')[0]
                        camera_name = f"IP Camera {ip_part}"
                    else:
                        camera_name = f"Stream {source_str[:30]}"
                else:
                    camera_name = f"Stream {source_str[:30]}"
        except ValueError:
            return
        
        # Check if camera already exists
        camera_id = f"camera_{len(self.cameras)}"
        if any(cam['source'] == source for cam in self.cameras.values()):
            return
        
        # Add camera
        self.cameras[camera_id] = {
            'name': camera_name,
            'source': source,
            'enabled': True
        }
        
        # Update listbox
        self.camera_listbox.insert(tk.END, f"{camera_name} ({camera_id})")
    
    def add_camera(self):
        """Add a camera to the feed"""
        source_str = self.camera_source_var.get().strip()
        if not source_str:
            messagebox.showwarning("No Source", "Please enter a camera source or use 'Scan Network' to find cameras")
            return
        
        # Validate and fix URL if needed
        if not source_str.isdigit():
            try:
                from SoccerID.utils.phone_camera_helper import validate_and_fix_url
                fixed_url, was_fixed, error_msg = validate_and_fix_url(source_str)
                if was_fixed:
                    source_str = fixed_url
                    if error_msg:
                        messagebox.showinfo("URL Fixed", f"Fixed URL format:\n{error_msg}\n\nUsing: {fixed_url}")
            except ImportError:
                pass  # Helper not available, continue with original
        
        # If just an IP address, try to construct URL
        if not source_str.isdigit() and '://' not in source_str:
            # Looks like just an IP, try common formats
            if ':' in source_str:
                # Has port: ip:port
                ip, port = source_str.rsplit(':', 1)
                source_str = f"http://{ip}:{port}/video"
                messagebox.showinfo("URL Constructed", f"Constructed URL: {source_str}")
            else:
                # Just IP, use default port
                source_str = f"http://{source_str}:8080/video"
                messagebox.showinfo("URL Constructed", f"Constructed URL: {source_str}\n(Using default port 8080)")
        
        # Parse source (int for USB, str for URL)
        try:
            if source_str.isdigit():
                source = int(source_str)
                camera_name = f"USB Camera {source}"
            else:
                source = source_str
                # Extract IP from URL for cleaner name
                if '://' in source_str:
                    parts = source_str.split('://')
                    if len(parts) > 1:
                        ip_part = parts[1].split('/')[0].split(':')[0]
                        camera_name = f"IP Camera {ip_part}"
                    else:
                        camera_name = f"Stream {source_str[:30]}"
                else:
                    camera_name = f"Stream {source_str[:30]}"
        except ValueError:
            messagebox.showerror("Invalid Source", "Camera source must be a number (USB) or URL (RTSP/HTTP)")
            return
        
        # Check if camera already exists
        camera_id = f"camera_{len(self.cameras)}"
        if any(cam['source'] == source for cam in self.cameras.values()):
            messagebox.showwarning("Duplicate", "This camera is already added")
            return
        
        # Test camera connection (suppress FFMPEG warnings)
        try:
            import os
            import sys
            old_stderr = sys.stderr
            
            # Suppress FFMPEG warnings during test
            try:
                devnull = open(os.devnull, 'w')
                sys.stderr = devnull
                
                # Try to open camera with appropriate backend
                if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
                    # HTTP stream - try FFMPEG backend first
                    test_cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                    test_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                elif isinstance(source, str) and source.startswith('rtsp://'):
                    # RTSP stream
                    test_cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                    test_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                else:
                    # USB camera
                    test_cap = cv2.VideoCapture(source)
                
                # Give it a moment to initialize
                import time
                time.sleep(0.2)
                
                opened = test_cap.isOpened()
                
                # Try to read a frame (but don't require it to succeed)
                frame_read = False
                if opened:
                    try:
                        ret, _ = test_cap.read()
                        frame_read = ret
                    except:
                        pass
                
                test_cap.release()
                
            finally:
                sys.stderr = old_stderr
                if 'devnull' in locals():
                    devnull.close()
            
            # If camera didn't open, ask user
            if not opened:
                result = messagebox.askyesno("Camera Not Accessible", 
                                           f"Could not open camera: {source}\n\n"
                                           "This might be normal if:\n"
                                           "• Camera is not currently streaming\n"
                                           "• IP address is incorrect\n"
                                           "• Camera is on a different network\n\n"
                                           "Add it anyway? (You can test it when starting the feed)")
                if not result:
                    return
            elif not frame_read:
                # Camera opened but couldn't read frame - still allow it
                pass  # Continue to add camera
            
        except Exception as e:
            # On any error, still allow adding (user can test when starting)
            result = messagebox.askyesno("Camera Test Error", 
                                       f"Error testing camera: {e}\n\n"
                                       "This is often normal for IP cameras.\n"
                                       "Add it anyway? (You can test it when starting the feed)")
            if not result:
                return
        
        # Add camera
        self.cameras[camera_id] = {
            'name': camera_name,
            'source': source,
            'enabled': True
        }
        
        # Update listbox
        self.camera_listbox.insert(tk.END, f"{camera_name} ({camera_id})")
        
        # Extract and save IP address to recent list
        self._add_to_recent_ips(source_str)
        
        # Clear input field
        self.camera_source_var.set("")
        
        self.update_status(f"Added {camera_name}")
    
    def remove_camera(self):
        """Remove selected camera"""
        selection = self.camera_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a camera to remove")
            return
        
        index = selection[0]
        camera_text = self.camera_listbox.get(index)
        
        # Extract camera_id from text
        camera_id = None
        for cid, cam in self.cameras.items():
            if f"{cam['name']} ({cid})" == camera_text:
                camera_id = cid
                break
        
        if camera_id:
            # Stop camera if running
            if camera_id in self.camera_captures:
                self.camera_captures[camera_id].release()
                del self.camera_captures[camera_id]
            
            if camera_id in self.camera_threads:
                # Thread will stop when capture is released
                del self.camera_threads[camera_id]
            
            # Remove from cameras
            del self.cameras[camera_id]
            if camera_id in self.camera_frames:
                del self.camera_frames[camera_id]
            
            # Update listbox
            self.camera_listbox.delete(index)
            self.update_status(f"Removed camera {camera_id}")
    
    def start_feed(self):
        """Start live feed from all cameras"""
        if not self.cameras:
            messagebox.showwarning("No Cameras", "Please add at least one camera")
            return
        
        if self.is_running:
            messagebox.showinfo("Already Running", "Live feed is already running")
            return
        
        # Suppress FFMPEG warnings globally
        import os
        import sys
        old_stderr = sys.stderr
        try:
            devnull = open(os.devnull, 'w')
            sys.stderr = devnull
            
            # Initialize all cameras
            failed_cameras = []
            for camera_id, camera_info in self.cameras.items():
                if not camera_info['enabled']:
                    continue
                
                try:
                    source = camera_info['source']
                    
                    # Handle HTTP streams with proper backend and URL fixing
                    if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
                        # Try to fix URL if needed
                        try:
                            from SoccerID.utils.phone_camera_helper import validate_and_fix_url
                            fixed_url, was_fixed, _ = validate_and_fix_url(source)
                            if was_fixed:
                                source = fixed_url
                                camera_info['source'] = fixed_url  # Update stored source
                        except:
                            pass
                        
                        # Use the same HTTP stream opening method as RealTimeProcessor
                        cap = self._open_http_stream_like_realtime(source)
                        if cap is None:
                            print(f"⚠ Camera {camera_id} failed to open HTTP stream: {source}")
                            failed_cameras.append(f"{camera_info['name']} (HTTP connection failed)")
                            continue
                            
                    elif isinstance(source, str) and source.startswith('rtsp://'):
                        # Use FFMPEG backend for RTSP streams
                        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    else:
                        # USB camera or other source
                        cap = cv2.VideoCapture(source)
                    
                    # Give it a moment to initialize (longer for HTTP streams)
                    if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
                        time.sleep(0.8)  # More time for HTTP streams to initialize
                    else:
                        time.sleep(0.2)
                    
                    if not cap.isOpened():
                        print(f"⚠ Camera {camera_id} ({camera_info['name']}) failed to open")
                        failed_cameras.append(camera_info['name'])
                        continue
                    
                    # Try to read a test frame to verify connection
                    # For HTTP streams, read multiple frames to "warm up" and clear buffer
                    test_frames_read = 0
                    test_ret = False
                    test_frame = None
                    
                    if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
                        # For HTTP streams, read several frames to clear buffer and warm up
                        # HTTP streams often have stale frames in buffer that need to be cleared
                        for i in range(8):
                            test_ret, test_frame = cap.read()
                            if test_ret and test_frame is not None:
                                test_frames_read += 1
                                if test_frames_read >= 3:  # Need at least 3 successful reads
                                    break
                            time.sleep(0.15)  # Small delay between reads
                    else:
                        # For USB/RTSP, single read is usually enough
                        test_ret, test_frame = cap.read()
                    
                    if not test_ret or test_frame is None:
                        print(f"⚠ Camera {camera_id} opened but cannot read frames (will retry in loop)")
                    else:
                        print(f"✓ Camera {camera_id} test frame successful: {test_frame.shape} (warmed up with {test_frames_read} frames)")
                    
                    self.camera_captures[camera_id] = cap
                    
                    # Initialize frame storage for this camera
                    self.camera_frames[camera_id] = None
                    
                    print(f"✓ Started camera: {camera_info['name']} ({camera_id})")
                    self.update_status(f"Starting {camera_info['name']}...")
                    
                except Exception as e:
                    failed_cameras.append(f"{camera_info['name']}: {str(e)}")
        finally:
            sys.stderr = old_stderr
            if 'devnull' in locals():
                devnull.close()
        
        if self.camera_captures:
            # Set is_running BEFORE starting threads to avoid race condition
            self.is_running = True
            
            # Now start all capture threads
            for camera_id, camera_info in self.cameras.items():
                if camera_id in self.camera_captures and camera_info.get('enabled', True):
                    thread = threading.Thread(target=self._camera_loop, 
                                            args=(camera_id,), daemon=True)
                    thread.start()
                    self.camera_threads[camera_id] = thread
                    print(f"🔵 Started capture thread for {camera_id}")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            
            # Start streaming server if enabled
            if self.streaming_var.get():
                self._start_streaming_server()
            
            # Start display update loop
            self._update_display()
            
            status_msg = f"Live feed started - {len(self.camera_captures)} camera(s) active"
            if self.streaming_enabled:
                status_msg += f" | Streaming to http://localhost:{self.streaming_port}/"
            if failed_cameras:
                status_msg += f" ({len(failed_cameras)} failed)"
            self.update_status(status_msg)
            
            if failed_cameras:
                messagebox.showwarning("Some Cameras Failed", 
                                     f"Failed to start:\n" + "\n".join(failed_cameras) + 
                                     "\n\nOther cameras are running.")
        else:
            error_msg = "Failed to start any cameras"
            if failed_cameras:
                error_msg += ":\n" + "\n".join(failed_cameras)
            messagebox.showerror("Error", error_msg)
    
    def stop_feed(self):
        """Stop live feed"""
        self.is_running = False
        
        # Stop streaming server
        if self.streaming_server:
            self.streaming_server.stop()
            self.streaming_server = None
            self.streaming_enabled = False
        
        # Release all captures
        for camera_id, cap in self.camera_captures.items():
            cap.release()
        
        self.camera_captures.clear()
        self.camera_threads.clear()
        self.camera_frames.clear()
        self.latest_combined_frame = None
        
        # Clear canvas
        self.video_canvas.delete("all")
        
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.update_status("Live feed stopped")
    
    def _camera_loop(self, camera_id):
        """Camera capture loop for a single camera"""
        print(f"🔵 Camera loop thread started for {camera_id}")
        try:
            cap = self.camera_captures[camera_id]
        except KeyError:
            print(f"⚠ Camera {camera_id} not found in captures")
            return
        
        consecutive_failures = 0
        max_failures = 30  # Allow some failures before giving up
        
        # Initialize frame lock if not exists
        if not hasattr(self, '_frame_lock'):
            import threading
            self._frame_lock = threading.Lock()
        
        # Small delay to let capture object stabilize after test frames
        time.sleep(0.3)
        
        # Suppress FFMPEG warnings in capture loop (but allow errors through)
        import os
        import sys
        
        # Debug: Check initial state
        if camera_id in self.camera_captures:
            cap = self.camera_captures[camera_id]
            print(f"🔍 Camera {camera_id} loop starting - cap.isOpened(): {cap.isOpened()}")
            try:
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                fps = cap.get(cv2.CAP_PROP_FPS)
                print(f"🔍 Camera {camera_id} properties: {width}x{height} @ {fps}fps")
            except Exception as e:
                print(f"⚠ Camera {camera_id} error getting properties: {e}")
        
        # Small delay to let capture stabilize (especially for HTTP streams after test frames)
        time.sleep(0.2)
        
        # For HTTP streams, read a few frames to clear any stale buffer after test frames
        if camera_id in self.camera_captures:
            cap = self.camera_captures[camera_id]
            source = self.cameras.get(camera_id, {}).get('source', '')
            if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
                # Clear buffer by reading a few frames
                print(f"🔍 Camera {camera_id} clearing buffer (HTTP stream)...")
                buffer_cleared = False
                for i in range(3):
                    try:
                        ret, _ = cap.read()
                        if ret:
                            buffer_cleared = True
                            print(f"🔍 Camera {camera_id} buffer cleared after {i+1} reads")
                            break
                        time.sleep(0.05)
                    except Exception as e:
                        print(f"⚠ Camera {camera_id} buffer clear error: {e}")
                        break
                if not buffer_cleared:
                    print(f"⚠ Camera {camera_id} buffer clear failed - continuing anyway")
        
        print(f"🔍 Camera {camera_id} entering main loop...")
        try:
            # Debug: Check conditions before entering loop
            is_running_check = self.is_running
            in_captures_check = camera_id in self.camera_captures
            print(f"🔍 Camera {camera_id} pre-loop check: is_running={is_running_check}, in_captures={in_captures_check}")
            
            if not is_running_check:
                print(f"⚠ Camera {camera_id} loop exiting: is_running is False")
                return
            if not in_captures_check:
                print(f"⚠ Camera {camera_id} loop exiting: not in camera_captures")
                return
            
            loop_iteration = 0
            consecutive_failures = 0
            last_reconnect_attempt = 0
            reconnect_backoff = 1.0  # Start with 1 second backoff
            
            print(f"🔍 Camera {camera_id} about to enter while loop...")
            while self.is_running and camera_id in self.camera_captures:
                loop_iteration += 1
                if loop_iteration == 1:
                    print(f"🔍 Camera {camera_id} first loop iteration")
                elif loop_iteration == 2:
                    print(f"🔍 Camera {camera_id} second loop iteration - about to read frame")
                
                # Check if camera is enabled
                if camera_id not in self.cameras or not self.cameras[camera_id].get('enabled', True):
                    print(f"⏸ Camera {camera_id} is disabled, pausing loop")
                    time.sleep(1.0)
                    continue
                
                # Get fresh reference to capture (in case it was recreated)
                if camera_id in self.camera_captures:
                    cap = self.camera_captures[camera_id]
                else:
                    print(f"⚠ Camera {camera_id} removed from captures, exiting loop")
                    break  # Camera was removed
                
                # Check if capture is still valid
                if not cap.isOpened():
                    if loop_iteration == 1:
                        print(f"⚠ Camera {camera_id} capture not opened on first iteration")
                    
                    # Implement exponential backoff for reconnection attempts
                    current_time = time.time()
                    if current_time - last_reconnect_attempt < reconnect_backoff:
                        time.sleep(0.5)
                        continue
                    
                    last_reconnect_attempt = current_time
                    print(f"⚠ Camera {camera_id} capture closed, attempting to reopen (backoff: {reconnect_backoff:.1f}s)...")
                    try:
                        source = self.cameras[camera_id]['source']
                        if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
                            try:
                                cap.release()
                            except:
                                pass
                            cap = self._open_http_stream_like_realtime(source)
                            if cap and cap.isOpened():
                                self.camera_captures[camera_id] = cap
                                consecutive_failures = 0
                                reconnect_backoff = 1.0  # Reset backoff on success
                                print(f"✓ Camera {camera_id} reconnected successfully")
                                time.sleep(0.5)
                            else:
                                consecutive_failures += 1
                                reconnect_backoff = min(reconnect_backoff * 2, 10.0)  # Max 10 seconds
                                print(f"⚠ Camera {camera_id} reconnection failed (attempt {consecutive_failures}, next retry in {reconnect_backoff:.1f}s)")
                                time.sleep(reconnect_backoff)
                                continue
                        elif isinstance(source, str) and source.startswith('rtsp://'):
                            try:
                                cap.release()
                            except:
                                pass
                            cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                            if cap.isOpened():
                                self.camera_captures[camera_id] = cap
                                consecutive_failures = 0
                                reconnect_backoff = 1.0
                                time.sleep(0.5)
                            else:
                                consecutive_failures += 1
                                reconnect_backoff = min(reconnect_backoff * 2, 10.0)
                                time.sleep(reconnect_backoff)
                                continue
                        else:
                            try:
                                cap.release()
                            except:
                                pass
                            cap = cv2.VideoCapture(source)
                            if cap.isOpened():
                                self.camera_captures[camera_id] = cap
                                consecutive_failures = 0
                                reconnect_backoff = 1.0
                                time.sleep(0.5)
                            else:
                                consecutive_failures += 1
                                reconnect_backoff = min(reconnect_backoff * 2, 10.0)
                                time.sleep(reconnect_backoff)
                                continue
                    except Exception as e:
                        print(f"⚠ Failed to reopen camera {camera_id}: {e}")
                        consecutive_failures += 1
                        reconnect_backoff = min(reconnect_backoff * 2, 10.0)
                        time.sleep(reconnect_backoff)
                        continue
                
                # For HTTP streams, use timeout mechanism to prevent blocking
                source = self.cameras.get(camera_id, {}).get('source', '')
                is_http_stream = isinstance(source, str) and (source.startswith('http://') or source.startswith('https://'))
                
                if loop_iteration == 1:
                    print(f"🔍 Camera {camera_id} about to read frame (is_http_stream={is_http_stream})")
                
                try:
                    if is_http_stream:
                        # Use threading with timeout for HTTP streams to prevent blocking
                        import threading
                        read_result = [None, None]  # [ret, frame]
                        read_exception = [None]
                        read_started = [False]
                        
                        if loop_iteration == 1:
                            print(f"🔍 Camera {camera_id} starting threaded read with timeout...")
                        
                        def read_frame():
                            try:
                                read_started[0] = True
                                if loop_iteration == 1:
                                    print(f"🔍 Camera {camera_id} thread: calling cap.read()...")
                                read_result[0], read_result[1] = cap.read()
                                if loop_iteration == 1:
                                    print(f"🔍 Camera {camera_id} thread: cap.read() returned")
                            except Exception as e:
                                read_exception[0] = e
                                if loop_iteration == 1:
                                    print(f"🔍 Camera {camera_id} thread: exception in read: {e}")
                        
                        read_thread = threading.Thread(target=read_frame, daemon=True)
                        read_thread.start()
                        
                        # Wait a moment to see if thread starts
                        time.sleep(0.1)
                        if loop_iteration == 1:
                            print(f"🔍 Camera {camera_id} thread started: alive={read_thread.is_alive()}, started={read_started[0]}")
                        
                        read_thread.join(timeout=2.0)  # 2 second timeout
                        
                        if read_thread.is_alive():
                            # Read timed out - this is a problem
                            print(f"⚠ Camera {camera_id} read timed out after 2 seconds (thread still alive)")
                            consecutive_failures += 1
                            # Try to release and recreate the capture, but with backoff
                            if consecutive_failures < 3:  # Only try to recreate first few times
                                try:
                                    cap.release()
                                    time.sleep(0.2)
                                    cap = self._open_http_stream_like_realtime(source)
                                    if cap and cap.isOpened():
                                        self.camera_captures[camera_id] = cap
                                        consecutive_failures = 0
                                        time.sleep(0.5)
                                    else:
                                        time.sleep(min(consecutive_failures * 1.0, 5.0))
                                except Exception as e:
                                    print(f"⚠ Camera {camera_id} error recreating capture: {e}")
                            else:
                                # After 3 failures, wait longer before retrying
                                wait_time = min(consecutive_failures * 2.0, 10.0)
                                print(f"⚠ Camera {camera_id} multiple timeouts, waiting {wait_time:.1f}s before retry")
                                time.sleep(wait_time)
                            continue
                        
                        if read_exception[0]:
                            print(f"⚠ Camera {camera_id} read exception: {read_exception[0]}")
                            raise read_exception[0]
                        
                        ret, frame = read_result[0], read_result[1]
                        if loop_iteration == 1:
                            print(f"🔍 Camera {camera_id} threaded read completed: ret={ret}, frame={'None' if frame is None else f'valid {frame.shape}'}")
                    else:
                        # For USB/RTSP, use normal blocking read
                        if loop_iteration == 1:
                            print(f"🔍 Camera {camera_id} starting blocking read...")
                        ret, frame = cap.read()
                        if loop_iteration == 1:
                            print(f"🔍 Camera {camera_id} blocking read completed: ret={ret}, frame={'None' if frame is None else f'valid {frame.shape}'}")
                    
                    # Debug first few reads - always log first read attempt
                    if not hasattr(self, f'_first_read_{camera_id}'):
                        setattr(self, f'_first_read_{camera_id}', True)
                        print(f"🔍 Camera {camera_id} first loop read: ret={ret}, frame={'None' if frame is None else (frame.shape if frame is not None else 'None')}")
                    # Also log if we're getting repeated failures
                    if not ret or frame is None:
                        if consecutive_failures == 0:
                            print(f"⚠ Camera {camera_id} first read failed: ret={ret}, frame is None={frame is None}")
                except Exception as e:
                    print(f"⚠ Camera {camera_id} read exception: {e}")
                    import traceback
                    traceback.print_exc()
                    consecutive_failures += 1
                    time.sleep(0.1)
                    continue
                
                if not ret or frame is None:
                    consecutive_failures += 1
                    # Debug: log failures with more detail
                    if consecutive_failures == 1:
                        print(f"⚠ Camera {camera_id} first read failure:")
                        print(f"   cap.isOpened(): {cap.isOpened()}")
                        print(f"   ret: {ret}, frame is None: {frame is None}")
                        # Try to get more info about the capture
                        try:
                            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                            fps = cap.get(cv2.CAP_PROP_FPS)
                            print(f"   Capture properties: {width}x{height} @ {fps}fps")
                        except:
                            pass
                    elif consecutive_failures == 10:
                        print(f"⚠ Camera {camera_id} still failing after 10 attempts - trying to refresh connection...")
                        # Force a refresh of the capture
                        try:
                            source = self.cameras[camera_id]['source']
                            if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
                                cap.release()
                                cap = self._open_http_stream_like_realtime(source)
                                if cap:
                                    self.camera_captures[camera_id] = cap
                                    time.sleep(0.5)
                                    # Read a few frames to warm up
                                    for _ in range(3):
                                        warm_ret, _ = cap.read()
                                        if warm_ret:
                                            break
                                        time.sleep(0.1)
                                else:
                                    time.sleep(1.0)
                                    continue
                        except Exception as refresh_err:
                            print(f"⚠ Failed to refresh camera {camera_id}: {refresh_err}")
                    elif consecutive_failures % 60 == 0:  # Every 60 failures (~2 seconds at 30fps)
                        print(f"⚠ Camera {camera_id} read failures: {consecutive_failures} (cap.isOpened: {cap.isOpened()})")
                    if consecutive_failures > max_failures:
                        # Try to reopen the camera
                        try:
                            source = self.cameras[camera_id]['source']
                            if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
                                cap.release()
                                cap = self._open_http_stream_like_realtime(source)
                                if cap:
                                    self.camera_captures[camera_id] = cap
                                    consecutive_failures = 0
                                    time.sleep(0.5)  # Give it time to reconnect
                                else:
                                    time.sleep(1.0)
                                    continue
                            elif isinstance(source, str) and source.startswith('rtsp://'):
                                cap.release()
                                cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                                self.camera_captures[camera_id] = cap
                                consecutive_failures = 0
                                time.sleep(0.5)
                        except Exception:
                            pass  # If reconnection fails, continue trying
                    
                    time.sleep(0.1)
                    continue
                
                # Successfully read frame
                consecutive_failures = 0
                
                # Update cap reference in case it was recreated
                if camera_id in self.camera_captures:
                    cap = self.camera_captures[camera_id]
                
                # Validate frame before storing
                if frame is not None and frame.size > 0:
                    # Store frame (use a lock to prevent race conditions)
                    with self._frame_lock:
                        self.camera_frames[camera_id] = frame.copy()
                    
                    # Debug: log first successful frame
                    if not hasattr(self, '_first_frame_logged'):
                        self._first_frame_logged = set()
                    if camera_id not in self._first_frame_logged:
                        print(f"✓ Camera {camera_id} received first frame: {frame.shape}")
                        self._first_frame_logged.add(camera_id)
                    
                    # Track frame count for periodic updates
                    if not hasattr(self, '_frame_count'):
                        self._frame_count = {}
                    self._frame_count[camera_id] = self._frame_count.get(camera_id, 0) + 1
                    if self._frame_count[camera_id] % 300 == 0:  # Every 10 seconds at 30fps
                        print(f"📹 Camera {camera_id}: {self._frame_count[camera_id]} frames captured")
                else:
                    # Invalid frame, skip
                    if not hasattr(self, '_invalid_frame_count'):
                        self._invalid_frame_count = {}
                    self._invalid_frame_count[camera_id] = self._invalid_frame_count.get(camera_id, 0) + 1
                    if self._invalid_frame_count[camera_id] == 1:
                        print(f"⚠ Camera {camera_id} returned invalid frame (size: {frame.size if frame is not None else 'None'})")
                    continue
                    
                # Adjust sleep time based on source type
                source = self.cameras[camera_id]['source']
                if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
                    time.sleep(1.0 / 25.0)  # Slightly slower for HTTP (25 FPS)
                else:
                    time.sleep(1.0 / 30.0)  # 30 FPS for USB/RTSP
        except Exception as e:
            print(f"❌ Camera loop {camera_id} crashed: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_display(self):
        """Update video display"""
        if not self.is_running:
            return
        
        # Ensure canvas is configured
        try:
            self.video_canvas.update_idletasks()
        except:
            pass
        
        # Collect frames from all cameras (thread-safe)
        frames = {}
        with self._frame_lock:
            for camera_id in self.cameras.keys():
                if camera_id in self.camera_frames:
                    frame = self.camera_frames[camera_id]
                    if frame is not None and frame.size > 0:
                        frames[camera_id] = frame
        
        # Debug: log frame status periodically
        if not hasattr(self, '_last_debug_log') or time.time() - self._last_debug_log > 5.0:
            print(f"📊 Display update: {len(frames)}/{len(self.cameras)} cameras have frames")
            print(f"   Active cameras: {list(self.cameras.keys())}")
            print(f"   Frames available: {list(frames.keys())}")
            # Show which cameras are missing frames
            missing = [cid for cid in self.cameras.keys() if cid not in frames]
            if missing:
                print(f"   Missing frames from: {missing}")
            self._last_debug_log = time.time()
        
        if frames:
            # Combine frames based on layout
            combined_frame = self._combine_frames(frames)
            
            if combined_frame is not None and combined_frame.size > 0:
                # Store latest combined frame for streaming (always update, even if only 1 camera)
                with self._frame_lock:
                    self.latest_combined_frame = combined_frame.copy()
                
                # Convert to PhotoImage and display
                display_frame = cv2.cvtColor(combined_frame, cv2.COLOR_BGR2RGB)
                
                # Get canvas dimensions (with fallback)
                try:
                    self.video_canvas.update_idletasks()
                    canvas_width = max(self.video_canvas.winfo_width(), 1280)
                    canvas_height = max(self.video_canvas.winfo_height(), 720)
                except:
                    canvas_width = 1280
                    canvas_height = 720
                
                # Maintain aspect ratio when resizing
                h, w = display_frame.shape[:2]
                scale = min(canvas_width / w, canvas_height / h, 1.0)
                new_w, new_h = int(w * scale), int(h * scale)
                display_frame = cv2.resize(display_frame, (new_w, new_h))
                
                img = Image.fromarray(display_frame)
                photo = ImageTk.PhotoImage(image=img)
                
                self.video_canvas.delete("all")
                # Center the image
                x = (canvas_width - new_w) // 2
                y = (canvas_height - new_h) // 2
                self.video_canvas.create_image(x, y, anchor=tk.NW, image=photo)
                self.video_canvas.image = photo  # Keep a reference
                
                # Debug: log first successful display
                if not hasattr(self, '_first_display_logged'):
                    print(f"✓ First frame displayed: {combined_frame.shape} -> canvas ({canvas_width}x{canvas_height})")
                    self._first_display_logged = True
        else:
            # No frames yet - show waiting message
            canvas_width = self.video_canvas.winfo_width() or 1280
            canvas_height = self.video_canvas.winfo_height() or 720
            self.video_canvas.delete("all")
            
            # Show which cameras are active but not receiving frames
            active_cameras = [cam['name'] for cam in self.cameras.values() if cam['enabled']]
            waiting_text = f"Waiting for frames...\n\n{len(self.camera_captures)} camera(s) active"
            if active_cameras:
                waiting_text += f"\n\nCameras:\n" + "\n".join([f"• {name}" for name in active_cameras[:3]])
                if len(active_cameras) > 3:
                    waiting_text += f"\n... and {len(active_cameras) - 3} more"
            
            self.video_canvas.create_text(
                canvas_width // 2,
                canvas_height // 2,
                text=waiting_text,
                fill="white",
                font=("Arial", 14),
                justify=tk.CENTER
            )
        
        # Schedule next update
        if self.is_running:
            self.parent_frame.after(33, self._update_display)  # ~30 FPS
    
    def _combine_frames(self, frames):
        """Combine multiple frames based on layout mode"""
        if not frames:
            return None
        
        layout = self.layout_var.get()
        num_cameras = len(frames)
        
        if num_cameras == 1:
            return next(iter(frames.values()))
        
        # Resize all frames
        target_size = (640, 360)
        resized_frames = []
        for frame in frames.values():
            resized = cv2.resize(frame, target_size)
            resized_frames.append(resized)
        
        if layout == "grid":
            # 2x2 grid for 4 cameras
            if num_cameras >= 4:
                top = np.hstack(resized_frames[:2])
                bottom = np.hstack(resized_frames[2:4])
                return np.vstack([top, bottom])
            elif num_cameras == 3:
                top = np.hstack(resized_frames[:2])
                bottom = cv2.resize(resized_frames[2], (target_size[0] * 2, target_size[1]))
                return np.vstack([top, bottom])
            else:  # 2 cameras - side by side
                # Ensure both frames are the same height for proper stacking
                h = min(f.shape[0] for f in resized_frames)
                aligned_frames = []
                for f in resized_frames:
                    if f.shape[0] != h:
                        w = int(f.shape[1] * h / f.shape[0])
                        f = cv2.resize(f, (w, h))
                    aligned_frames.append(f)
                return np.hstack(aligned_frames)
        
        elif layout == "pip":
            # Picture-in-picture: main camera full, others small in corner
            main_frame = resized_frames[0]
            main_frame = cv2.resize(main_frame, (1280, 720))
            
            if num_cameras > 1:
                pip_size = (320, 180)
                pip_frame = cv2.resize(resized_frames[1], pip_size)
                # Place in top-right corner
                main_frame[0:pip_size[1], -pip_size[0]:] = pip_frame
            
            return main_frame
        
        elif layout == "split":
            # Split screen: side by side
            return np.hstack(resized_frames[:2] if num_cameras >= 2 else resized_frames)
        
        return resized_frames[0]
    
    def change_layout(self):
        """Change display layout"""
        # Layout will be applied on next display update
        pass
    
    def on_camera_select(self, event):
        """Handle camera selection"""
        selection = self.camera_listbox.curselection()
        if selection:
            # Could highlight selected camera in display
            pass
    
    def open_settings(self):
        """Open settings dialog"""
        settings_window = tk.Toplevel(self.parent_frame)
        settings_window.title("Live Feed Settings")
        settings_window.geometry("400x300")
        
        # Settings options
        ttk.Label(settings_window, text="Processing Settings", 
                 font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        self.tracking_var = tk.BooleanVar(value=self.enable_tracking)
        ttk.Checkbutton(settings_window, text="Enable Player Tracking", 
                       variable=self.tracking_var).pack(anchor=tk.W, padx=20, pady=5)
        
        self.reid_var = tk.BooleanVar(value=self.enable_reid)
        ttk.Checkbutton(settings_window, text="Enable Re-ID (slower)", 
                       variable=self.reid_var).pack(anchor=tk.W, padx=20, pady=5)
        
        ttk.Button(settings_window, text="Save", 
                  command=lambda: self.save_settings(settings_window)).pack(pady=20)
    
    def save_settings(self, window):
        """Save settings"""
        self.enable_tracking = self.tracking_var.get()
        self.enable_reid = self.reid_var.get()
        window.destroy()
        messagebox.showinfo("Settings Saved", "Settings have been saved")
    
    def _start_streaming_server(self):
        """Start streaming server for web dashboard"""
        # Check if server is already running (avoid port conflicts)
        if self.streaming_server is not None:
            try:
                # Check if it's still running
                if hasattr(self.streaming_server, 'is_running') and self.streaming_server.is_running:
                    print("ℹ️ Streaming server already running, reusing existing instance")
                    return
            except:
                pass
        
        try:
            from SoccerID.utils.streaming_server import StreamingServer
            import socket
            
            # Check if port is already in use
            def is_port_in_use(port):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    try:
                        s.bind(('localhost', port))
                        return False
                    except OSError:
                        return True
            
            # Try to find an available port if default is in use
            port = self.streaming_port
            if is_port_in_use(port):
                print(f"⚠ Port {port} is already in use, trying alternative port...")
                # Try ports 8082-8090
                for alt_port in range(8082, 8091):
                    if not is_port_in_use(alt_port):
                        port = alt_port
                        print(f"✓ Using alternative port {port}")
                        break
                else:
                    print("⚠ Could not find available port for streaming")
                    return
            
            def get_latest_frame():
                """Get latest combined frame for streaming"""
                # Always try to get fresh frames from camera_frames dict
                # This ensures we get the latest frames even if latest_combined_frame is stale
                frames = {}
                with self._frame_lock:
                    for camera_id in self.cameras.keys():
                        if camera_id in self.camera_frames:
                            frame = self.camera_frames[camera_id]
                            if frame is not None and frame.size > 0:
                                frames[camera_id] = frame
                
                # Debug: Log frame availability occasionally
                if not hasattr(self, '_last_frame_check_log') or time.time() - self._last_frame_check_log > 5.0:
                    available_cameras = list(frames.keys())
                    total_cameras = len(self.cameras)
                    print(f"🔍 Streaming frame check: {len(frames)}/{total_cameras} cameras have frames: {available_cameras}")
                    self._last_frame_check_log = time.time()
                
                if frames:
                    # Combine frames based on current layout
                    # Even if only one camera has frames, still return it
                    try:
                        combined = self._combine_frames(frames)
                        if combined is not None and combined.size > 0:
                            # Cache it for next time and update latest_combined_frame
                            with self._frame_lock:
                                self.latest_combined_frame = combined.copy()
                            return combined.copy()
                        else:
                            if not hasattr(self, '_last_combine_fail_log') or time.time() - self._last_combine_fail_log > 5.0:
                                print(f"⚠ Streaming: _combine_frames returned None or empty (input: {len(frames)} frames)")
                                self._last_combine_fail_log = time.time()
                    except Exception as e:
                        if not hasattr(self, '_last_combine_error_log') or time.time() - self._last_combine_error_log > 5.0:
                            print(f"⚠ Streaming: Error combining frames: {e}")
                            import traceback
                            traceback.print_exc()
                            self._last_combine_error_log = time.time()
                
                # Fallback to cached combined frame if available
                with self._frame_lock:
                    if self.latest_combined_frame is not None:
                        return self.latest_combined_frame.copy()
                
                # No frames available - log this occasionally for debugging
                if not hasattr(self, '_last_stream_none_log') or time.time() - self._last_stream_none_log > 5.0:
                    print(f"⚠ Streaming server: No frames available from {len(self.camera_frames)} camera(s), total cameras: {len(self.cameras)}")
                    print(f"   Camera frames dict keys: {list(self.camera_frames.keys())}")
                    print(f"   Cameras dict keys: {list(self.cameras.keys())}")
                    self._last_stream_none_log = time.time()
                
                return None
            
            def get_stats():
                """Get stats for streaming"""
                frames_available = len([c for c in self.camera_frames.keys() if self.camera_frames.get(c) is not None])
                return {
                    'fps': 30.0,
                    'cameras': len(self.camera_captures),
                    'active_cameras': len([c for c in self.cameras.values() if c['enabled']]),
                    'frames_available': frames_available,
                    'camera_names': [cam['name'] for cam in self.cameras.values() if cam['enabled']],
                    'is_running': self.is_running,
                    'has_combined_frame': self.latest_combined_frame is not None
                }
            
            def get_events():
                """Get events (empty for now, can be extended)"""
                return []
            
            def get_tracks():
                """Get tracks (empty for now, can be extended)"""
                return {}
            
            def get_tactical():
                """Get tactical data (empty for now, can be extended)"""
                return {}
            
            def get_video_paths():
                """Get video paths (empty for now)"""
                return []
            
            self.streaming_server = StreamingServer(
                port=port,
                frame_provider=get_latest_frame,
                stats_provider=get_stats,
                events_provider=get_events,
                tracks_provider=get_tracks,
                tactical_provider=get_tactical,
                video_paths_provider=get_video_paths
            )
            
            if self.streaming_server.start():
                self.streaming_enabled = True
                self.streaming_port = port  # Update to actual port used
                print(f"🌐 Live Feed streaming server started on port {port}")
                print(f"   Web Dashboard: http://localhost:{port}/")
                print(f"   MJPEG Stream: http://localhost:{port}/video")
                print(f"   Access via web: http://localhost:5173/ (proxied to port {port})")
            else:
                print("⚠ Could not start streaming server")
                self.streaming_server = None
        except ImportError as e:
            print(f"⚠ Streaming server not available: {e}")
            print("   Install dependencies: pip install flask flask-cors")
            self.streaming_server = None
        except Exception as e:
            print(f"⚠ Error starting streaming server: {e}")
            import traceback
            traceback.print_exc()
            self.streaming_server = None
    
    def _extract_ip_from_source(self, source_str):
        """Extract IP address from camera source string"""
        if not source_str:
            return None
        
        # If it's just a number (USB camera), return None
        if source_str.isdigit():
            return None
        
        # Extract IP from URL
        if '://' in source_str:
            # http://192.168.1.65:8080/video
            parts = source_str.split('://')
            if len(parts) > 1:
                ip_part = parts[1].split('/')[0].split(':')[0]
                return ip_part
        elif ':' in source_str and not source_str.startswith('rtsp'):
            # 192.168.1.65:8080
            return source_str.split(':')[0]
        elif '.' in source_str:
            # Just IP address: 192.168.1.65
            parts = source_str.split('.')
            if len(parts) == 4 and all(p.isdigit() for p in parts):
                return source_str
        
        return None
    
    def _add_to_recent_ips(self, source_str):
        """Add IP address to recent list (max 4)"""
        ip = self._extract_ip_from_source(source_str)
        if not ip:
            return
        
        # Remove if already exists
        if ip in self.recent_camera_ips:
            self.recent_camera_ips.remove(ip)
        
        # Add to front
        self.recent_camera_ips.insert(0, ip)
        
        # Keep only last 4
        if len(self.recent_camera_ips) > 4:
            self.recent_camera_ips = self.recent_camera_ips[:4]
        
        # Update combobox values
        self._update_combobox_values()
        
        # Save to file
        self._save_recent_ips()
    
    def _update_combobox_values(self):
        """Update the combobox dropdown values"""
        if hasattr(self, 'camera_source_combobox'):
            self.camera_source_combobox['values'] = self.recent_camera_ips
    
    def _load_recent_ips(self):
        """Load recent IPs from config file"""
        try:
            config_dir = os.path.join(os.path.expanduser("~"), ".soccer_analysis")
            os.makedirs(config_dir, exist_ok=True)
            config_file = os.path.join(config_dir, "recent_camera_ips.json")
            
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    self.recent_camera_ips = data.get('recent_ips', [])[:4]  # Max 4
        except Exception as e:
            # If loading fails, just use empty list
            self.recent_camera_ips = []
    
    def _save_recent_ips(self):
        """Save recent IPs to config file"""
        try:
            config_dir = os.path.join(os.path.expanduser("~"), ".soccer_analysis")
            os.makedirs(config_dir, exist_ok=True)
            config_file = os.path.join(config_dir, "recent_camera_ips.json")
            
            with open(config_file, 'w') as f:
                json.dump({'recent_ips': self.recent_camera_ips}, f, indent=2)
        except Exception as e:
            # If saving fails, just continue
            pass
    
    def update_status(self, message):
        """Update status bar"""
        self.status_label.config(text=message)

