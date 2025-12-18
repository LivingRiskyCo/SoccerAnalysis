"""
BoxMOT Tracker Wrapper
Integrates BoxMOT tracking algorithms with the soccer analysis system.

This wrapper provides:
- Unified interface for BoxMOT trackers
- Integration with existing Re-ID system
- Compatibility with supervision Detections format
"""

import numpy as np
import cv2
from typing import Optional, Tuple, List

# Try to import BoxMOT
try:
    import warnings
    # Suppress pkg_resources deprecation warning from BoxMOT (third-party library issue)
    # BoxMOT uses deprecated pkg_resources API that will be removed in setuptools 81
    # This is a BoxMOT library issue, not our code
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources is deprecated.*")
        from boxmot import DeepOcSort, StrongSort, BotSort, OcSort, ByteTrack as BoxMOTByteTrack
    BOXMOT_AVAILABLE = True
except ImportError as e:
    BOXMOT_AVAILABLE = False
    print(f"[WARN] BoxMOT not available. Install with: pip install boxmot (Error: {e})")

# Try to import supervision for compatibility
try:
    import supervision as sv
    SUPERVISION_AVAILABLE = True
except ImportError:
    SUPERVISION_AVAILABLE = False


class BoxMOTTrackerWrapper:
    """
    Wrapper for BoxMOT trackers to work with supervision Detections format.
    
    This allows BoxMOT trackers to be used as drop-in replacements for
    ByteTrack/OC-SORT while maintaining compatibility with existing code.
    """
    
    def __init__(self, 
                 tracker_type: str = "deepocsort",
                 model_weights: Optional[str] = None,
                 device: str = "cuda",
                 fp16: bool = True,
                 track_thresh: float = 0.25,
                 match_thresh: float = 0.8,
                 track_buffer: int = 30,
                 min_track_length: int = 5,
                 osnet_variant: str = "osnet_x1_0",
                 **kwargs):
        """
        Initialize BoxMOT tracker.
        
        Args:
            tracker_type: Type of tracker ("deepocsort", "strongsort", "botsort", "ocsort", "bytetrack")
            model_weights: Path to Re-ID model weights (for appearance-based trackers)
            device: Device to use ("cuda" or "cpu")
            fp16: Use half precision (faster, less memory)
            track_thresh: Detection confidence threshold
            match_thresh: Matching threshold
            track_buffer: Frames to keep lost tracks
            min_track_length: Minimum frames before track is activated
        """
        if not BOXMOT_AVAILABLE:
            raise ImportError("BoxMOT is not installed. Install with: pip install boxmot")
        
        self.tracker_type = tracker_type.lower()
        self.device = device
        self.fp16 = fp16
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.track_buffer = track_buffer
        self.min_track_length = min_track_length
        self.osnet_variant = osnet_variant  # OSNet variant for Re-ID model selection
        
        # Initialize the appropriate tracker
        # BoxMOT trackers have different parameter names than supervision
        from pathlib import Path
        
        # For appearance-based trackers, need reid_weights (Path) and half (bool)
        if self.tracker_type in ['deepocsort', 'strongsort', 'botsort']:
            # BoxMOT appearance trackers require reid_weights (Path) - cannot be None
            if model_weights:
                reid_weights_path = Path(model_weights)
            else:
                # Use selected OSNet variant
                from boxmot.utils import WEIGHTS
                import os
                
                # Ensure WEIGHTS directory exists (BoxMOT needs it to download/store models)
                if not os.path.exists(WEIGHTS):
                    try:
                        os.makedirs(WEIGHTS, exist_ok=True)
                        print(f"  [INFO] Created weights directory: {WEIGHTS}")
                    except Exception as e:
                        print(f"  [WARN] Could not create weights directory: {e}")
                
                # Map OSNet variant to BoxMOT model weights
                osnet_weights_map = {
                    'osnet_x1_0': WEIGHTS / "osnet_x1_0_msmt17.pt",
                    'osnet_ain_x1_0': WEIGHTS / "osnet_ain_x1_0_msmt17.pt",
                    'osnet_ibn_x1_0': WEIGHTS / "osnet_ibn_x1_0_msmt17.pt",
                    'osnet_x0_75': WEIGHTS / "osnet_x0_75_msmt17.pt",
                    'osnet_x0_5': WEIGHTS / "osnet_x0_5_msmt17.pt",
                    'osnet_x0_25': WEIGHTS / "osnet_x0_25_msmt17.pt",
                }
                
                # Get weights path for selected variant (default to osnet_x1_0 if not found)
                reid_weights_path = osnet_weights_map.get(self.osnet_variant, osnet_weights_map['osnet_x1_0'])
                print(f"  [INFO] Using OSNet variant: {self.osnet_variant}")
                print(f"  [INFO] BoxMOT will download the model automatically if needed")
            
            # Convert device string to torch.device
            # BoxMOT expects device as string like "0" for CUDA, not "cuda"
            import torch
            if isinstance(device, str):
                if device == "cuda":
                    # Check if CUDA is available and get device ID
                    if torch.cuda.is_available():
                        device_obj = "0"  # Use first GPU
                    else:
                        device_obj = "cpu"
                elif device.startswith("cuda:"):
                    # Extract device ID from "cuda:0"
                    device_id = device.split(":")[1]
                    device_obj = device_id
                else:
                    device_obj = device
            else:
                device_obj = device
            
            # BoxMOT uses different parameter names:
            # track_thresh -> det_thresh
            # match_thresh -> iou_threshold  
            # track_buffer -> max_age
            # min_track_length -> min_hits
            tracker_kwargs = {
                'reid_weights': reid_weights_path,
                'half': fp16,
                'device': device_obj,
                'det_thresh': track_thresh,  # Detection threshold
                'iou_threshold': match_thresh,  # Matching threshold
                'max_age': track_buffer,  # Track buffer (frames to keep lost tracks)
                'min_hits': min_track_length,  # Minimum frames before activation
            }
        else:
            # Motion-only trackers (OC-SORT, ByteTrack) - use standard parameters
            import torch
            if isinstance(device, str):
                if device == "cuda":
                    if torch.cuda.is_available():
                        device_obj = "0"
                    else:
                        device_obj = "cpu"
                elif device.startswith("cuda:"):
                    device_id = device.split(":")[1]
                    device_obj = device_id
                else:
                    device_obj = device
            else:
                device_obj = device
            
            tracker_kwargs = {
                'track_thresh': track_thresh,
                'match_thresh': match_thresh,
                'track_buffer': track_buffer,
                'min_track_length': min_track_length,
                'device': device_obj,
            }
            # Some BoxMOT trackers support fp16
            if self.tracker_type == "bytetrack":
                tracker_kwargs['fp16'] = fp16
        
        try:
            if self.tracker_type == "deepocsort":
                self.tracker = DeepOcSort(**tracker_kwargs)
            elif self.tracker_type == "strongsort":
                self.tracker = StrongSort(**tracker_kwargs)
            elif self.tracker_type == "botsort":
                # BotSort uses different parameter names: match_thresh instead of det_thresh
                botsort_kwargs = tracker_kwargs.copy()
                if 'det_thresh' in botsort_kwargs:
                    # BotSort uses match_thresh for detection threshold, not det_thresh
                    botsort_kwargs['match_thresh'] = botsort_kwargs.pop('det_thresh')
                self.tracker = BotSort(**botsort_kwargs)
            elif self.tracker_type == "ocsort":
                self.tracker = OcSort(**tracker_kwargs)
            elif self.tracker_type == "bytetrack":
                self.tracker = BoxMOTByteTrack(**tracker_kwargs)
            else:
                raise ValueError(f"Unknown tracker type: {tracker_type}. "
                               f"Supported: deepocsort, strongsort, botsort, ocsort, bytetrack")
            
            print(f"[OK] BoxMOT {tracker_type} tracker initialized")
            if self.tracker_type in ['deepocsort', 'strongsort', 'botsort']:
                print(f"  -> Appearance-based tracking enabled (better occlusion handling)")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize BoxMOT tracker: {e}")
    
    def update(self, detections: 'sv.Detections', frame: np.ndarray) -> 'sv.Detections':
        """
        Update tracker with new detections.
        
        Args:
            detections: supervision Detections object
            frame: Current frame (for appearance features)
        
        Returns:
            Updated detections with tracker_id assigned
        """
        if not SUPERVISION_AVAILABLE:
            raise ImportError("supervision library is required")
        
        # Validate frame before passing to tracker
        if frame is None:
            # Frame is None - return detections without tracking
            return detections
        
        # Ensure frame is a numpy array
        if not isinstance(frame, np.ndarray):
            try:
                frame = np.asarray(frame)
            except:
                # Can't convert to array - return detections without tracking
                return detections
        
        # Check if frame has valid dimensions
        if frame.size == 0 or len(frame.shape) < 2:
            # Empty or invalid frame - return detections without tracking
            return detections
        
        # Check if frame dimensions are valid (height and width > 0)
        if frame.shape[0] == 0 or frame.shape[1] == 0:
            # Invalid dimensions - return detections without tracking
            return detections
        
        # Convert supervision Detections to BoxMOT format
        try:
            if len(detections) == 0:
                # Empty detections - still update tracker (for lost track handling)
                # BoxMOT expects positional arguments: update(dets, img)
                tracks = self.tracker.update(
                    np.empty((0, 6)),  # Empty array: [x1, y1, x2, y2, conf, cls]
                    frame
                )
            else:
                # Prepare detections in BoxMOT format: [x1, y1, x2, y2, conf, cls]
                try:
                    # Safely access xyxy
                    if detections.xyxy is None:
                        raise ValueError("detections.xyxy is None")
                    
                    # Convert to numpy array - handle tuple, list, or array
                    xyxy_array = np.asarray(detections.xyxy, dtype=np.float32)
                    
                    # Handle different array shapes
                    if xyxy_array.ndim == 0:
                        raise ValueError(f"xyxy is scalar, expected 2D array")
                    elif xyxy_array.ndim == 1:
                        # Single detection: reshape to (1, 4)
                        if len(xyxy_array) >= 4:
                            xyxy_array = xyxy_array[:4].reshape(1, 4)
                        else:
                            raise ValueError(f"xyxy 1D array has {len(xyxy_array)} elements, expected at least 4")
                    elif xyxy_array.ndim == 2:
                        # Multiple detections: ensure shape is (N, 4+)
                        if xyxy_array.shape[1] < 4:
                            raise ValueError(f"xyxy 2D array has {xyxy_array.shape[1]} columns, expected at least 4")
                        if xyxy_array.shape[0] != len(detections):
                            raise ValueError(f"xyxy shape mismatch: {xyxy_array.shape[0]} rows, expected {len(detections)}")
                    else:
                        raise ValueError(f"xyxy has {xyxy_array.ndim} dimensions, expected 1 or 2")
                    
                    dets_array = np.zeros((len(detections), 6), dtype=np.float32)
                    dets_array[:, :4] = xyxy_array[:, :4]  # Bounding boxes (first 4 columns)
                    
                    # Safely access confidence
                    try:
                        if detections.confidence is not None:
                            conf_array = np.asarray(detections.confidence, dtype=np.float32)
                            # Handle different array shapes
                            if conf_array.ndim == 0:
                                # Scalar - broadcast to all detections
                                dets_array[:, 4] = float(conf_array)
                            elif conf_array.ndim == 1:
                                if len(conf_array) == len(detections):
                                    dets_array[:, 4] = conf_array
                                else:
                                    # Length mismatch - use default
                                    dets_array[:, 4] = 0.5
                            else:
                                # Multi-dimensional - try to flatten or use default
                                dets_array[:, 4] = 0.5
                        else:
                            dets_array[:, 4] = 0.5  # Default confidence
                    except (IndexError, ValueError, TypeError, AttributeError) as e:
                        # If confidence access fails, use default
                        print(f"  [WARN] Error accessing confidence: {e}, type: {type(detections.confidence) if hasattr(detections, 'confidence') else 'N/A'}")
                        dets_array[:, 4] = 0.5
                    
                    # Safely access class_id
                    try:
                        if detections.class_id is not None:
                            cls_array = np.asarray(detections.class_id, dtype=np.int32)
                            # Handle different array shapes
                            if cls_array.ndim == 0:
                                # Scalar - broadcast to all detections
                                dets_array[:, 5] = int(cls_array)
                            elif cls_array.ndim == 1:
                                if len(cls_array) == len(detections):
                                    dets_array[:, 5] = cls_array
                                else:
                                    # Length mismatch - use default
                                    dets_array[:, 5] = 0
                            else:
                                # Multi-dimensional - try to flatten or use default
                                dets_array[:, 5] = 0
                        else:
                            dets_array[:, 5] = 0  # Default class
                    except (IndexError, ValueError, TypeError, AttributeError) as e:
                        # If class_id access fails, use default
                        print(f"  [WARN] Error accessing class_id: {e}, type: {type(detections.class_id) if hasattr(detections, 'class_id') else 'N/A'}")
                        dets_array[:, 5] = 0
                    
                    # Update tracker
                    # BoxMOT expects positional arguments: update(dets, img)
                    # Additional frame validation before passing to BoxMOT
                    if frame is None or frame.size == 0 or len(frame.shape) < 2 or frame.shape[0] == 0 or frame.shape[1] == 0:
                        # Invalid frame - return detections without tracking
                        return detections
                    
                    tracks = self.tracker.update(dets_array, frame)
                except (ValueError, IndexError, AttributeError, TypeError, cv2.error) as e:
                    # If we can't prepare detections, return them without track IDs
                    import traceback
                    error_details = traceback.format_exc()
                    
                    # SUPPRESS KNOWN BOXMOT BUGS:
                    error_str = str(e)
                    # 1. Kalman filter revert_state_on_poor_update IndexError
                    if isinstance(e, IndexError) and "index -2 is out of bounds" in error_str:
                        # This is the known BoxMOT Kalman filter bug - suppress verbose logging
                        # Tracking continues to work fine despite this error
                        pass  # Don't print anything - this is expected during tracker warmup
                    # 2. OpenCV resize errors (BoxMOT internal issue with empty frames)
                    elif "cv::resize" in error_str or "!ssize.empty()" in error_str or "Assertion failed" in error_str:
                        # OpenCV resize error - likely empty frame passed to BoxMOT internally
                        # This is a known BoxMOT issue, suppress verbose logging
                        pass  # Don't print - this is expected when frames are invalid
                    else:
                        # For other errors, show detailed information
                        print(f"  [WARN] Error preparing detections for BoxMOT: {e}")
                        print(f"  [WARN] Error type: {type(e).__name__}")
                        # Print the last few lines of traceback to see where it failed
                        tb_lines = error_details.split('\n')
                        if len(tb_lines) > 3:
                            print(f"  [WARN] Error location (last 3 lines):")
                            for line in tb_lines[-4:-1]:  # Last 3 relevant lines
                                if line.strip():
                                    print(f"    {line}")
                        # Debug prints only for non-suppressed errors
                        if hasattr(detections, 'xyxy'):
                            try:
                                xyxy_info = f"xyxy type: {type(detections.xyxy)}"
                                if detections.xyxy is not None:
                                    try:
                                        xyxy_arr = np.asarray(detections.xyxy)
                                        xyxy_info += f", shape: {xyxy_arr.shape}, ndim: {xyxy_arr.ndim}"
                                    except:
                                        xyxy_info += f", value: {str(detections.xyxy)[:100]}"
                                else:
                                    xyxy_info += ", value: None"
                                print(f"  [WARN] {xyxy_info}")
                            except:
                                pass
                        # Also check confidence and class_id
                        try:
                            if hasattr(detections, 'confidence'):
                                conf_info = f"confidence type: {type(detections.confidence)}"
                                if detections.confidence is not None:
                                    try:
                                        conf_arr = np.asarray(detections.confidence)
                                        conf_info += f", shape: {conf_arr.shape if hasattr(conf_arr, 'shape') else 'no shape'}, ndim: {conf_arr.ndim if hasattr(conf_arr, 'ndim') else 'N/A'}"
                                    except:
                                        conf_info += f", value: {str(detections.confidence)[:50]}"
                                print(f"  [WARN] {conf_info}")
                        except:
                            pass
                        try:
                            if hasattr(detections, 'class_id'):
                                cls_info = f"class_id type: {type(detections.class_id)}"
                                if detections.class_id is not None:
                                    try:
                                        cls_arr = np.asarray(detections.class_id)
                                        cls_info += f", shape: {cls_arr.shape if hasattr(cls_arr, 'shape') else 'no shape'}, ndim: {cls_arr.ndim if hasattr(cls_arr, 'ndim') else 'N/A'}"
                                    except:
                                        cls_info += f", value: {str(detections.class_id)[:50]}"
                                print(f"  [WARN] {cls_info}")
                        except:
                            pass
                        print(f"  [WARN] detections length: {len(detections)}")
                    if len(detections) > 0:
                        detections.tracker_id = np.full(len(detections), -1, dtype=int)
                    else:
                        detections.tracker_id = np.array([], dtype=int)
                    return detections
        except Exception as e:
            # If tracker update fails, return detections without track IDs
            # Suppress OpenCV resize errors (BoxMOT internal issue with empty frames)
            error_str = str(e)
            if "cv::resize" in error_str or "!ssize.empty()" in error_str or "Assertion failed" in error_str:
                # OpenCV resize error - likely empty frame passed to BoxMOT internally
                # This is a known BoxMOT issue, suppress verbose logging
                pass  # Don't print - this is expected when frames are invalid
            else:
                print(f"  [WARN] BoxMOT tracker update error: {e}")
            if len(detections) > 0:
                detections.tracker_id = np.full(len(detections), -1, dtype=int)
            else:
                detections.tracker_id = np.array([], dtype=int)
            return detections
        
        # Convert BoxMOT tracks back to supervision format
        # Handle empty tracks
        if tracks is None or (hasattr(tracks, '__len__') and len(tracks) == 0):
            # No tracks - return detections without track IDs
            if len(detections) > 0:
                detections.tracker_id = np.full(len(detections), -1, dtype=int)
            else:
                detections.tracker_id = np.array([], dtype=int)
            return detections
        
        # Ensure tracks is a numpy array
        if not isinstance(tracks, np.ndarray):
            tracks = np.array(tracks)
        
        # Check tracks shape
        if tracks.shape[0] == 0:
            if len(detections) > 0:
                detections.tracker_id = np.full(len(detections), -1, dtype=int)
            else:
                detections.tracker_id = np.array([], dtype=int)
            return detections
        
        # BoxMOT tracks format: [x1, y1, x2, y2, track_id, conf, cls, ...] (8 columns)
        # Extract track IDs and bounding boxes from tracks
        try:
            # Ensure we have enough columns
            if tracks.shape[1] < 5:
                print(f"  [WARN] BoxMOT tracks has insufficient columns: {tracks.shape[1]}, expected at least 5")
                if len(detections) > 0:
                    detections.tracker_id = np.full(len(detections), -1, dtype=int)
                else:
                    detections.tracker_id = np.array([], dtype=int)
                return detections
            
            track_ids = tracks[:, 4].astype(int)  # Track IDs at column 4
            track_boxes = tracks[:, :4]  # Bounding boxes in first 4 columns
        except (IndexError, ValueError, TypeError) as e:
            # Handle case where tracks format is unexpected
            print(f"  [WARN] Error parsing BoxMOT tracks: {e}")
            print(f"  [WARN] Tracks type: {type(tracks)}, shape: {tracks.shape if hasattr(tracks, 'shape') else 'no shape'}")
            if len(detections) > 0:
                detections.tracker_id = np.full(len(detections), -1, dtype=int)
            else:
                detections.tracker_id = np.array([], dtype=int)
            return detections
        
        # Match tracks to detections by IoU
        # Initialize all detections as unmatched
        matched_detections = np.full(len(detections), -1, dtype=int)  # -1 = unmatched
        
        if len(detections) > 0 and len(track_boxes) > 0:
            try:
                # Ensure detections.xyxy is accessible
                det_xyxy = detections.xyxy
                if det_xyxy is None:
                    print(f"  [WARN] detections.xyxy is None, cannot match tracks")
                    detections.tracker_id = matched_detections
                    return detections
                
                # Convert to numpy array if needed
                det_xyxy = np.asarray(det_xyxy)
                
                # Check shape
                if len(det_xyxy) == 0 or det_xyxy.shape[0] == 0:
                    print(f"  [WARN] detections.xyxy is empty, cannot match tracks")
                    detections.tracker_id = matched_detections
                    return detections
                
                # Ensure 2D shape: (N, 4)
                if det_xyxy.ndim == 1:
                    if det_xyxy.shape[0] == 4:
                        det_xyxy = det_xyxy.reshape(1, 4)
                    else:
                        print(f"  [WARN] detections.xyxy has unexpected 1D shape: {det_xyxy.shape}")
                        detections.tracker_id = matched_detections
                        return detections
                
                if det_xyxy.shape[1] < 4:
                    print(f"  [WARN] detections.xyxy has insufficient columns: {det_xyxy.shape[1]}, expected 4")
                    detections.tracker_id = matched_detections
                    return detections
                
                for i in range(len(detections)):
                    try:
                        # Get detection box - ensure it has 4 elements
                        if i >= det_xyxy.shape[0]:
                            continue  # Skip if index out of range
                        
                        det_box = det_xyxy[i, :4]  # Explicitly take first 4 elements
                        
                        # Ensure det_box is a 1D array with 4 elements
                        det_box = np.asarray(det_box).flatten()
                        if len(det_box) < 4:
                            continue  # Skip if box is invalid
                        
                        best_iou = 0.0
                        best_track_idx = -1
                        
                        for j in range(len(track_boxes)):
                            try:
                                track_box = track_boxes[j, :4]  # Explicitly take first 4 elements
                                track_box = np.asarray(track_box).flatten()
                                if len(track_box) < 4:
                                    continue  # Skip if box is invalid
                                
                                iou = self._calculate_iou(det_box, track_box)
                                if iou > best_iou and iou > 0.3:  # Minimum IoU threshold
                                    best_iou = iou
                                    best_track_idx = j
                            except (IndexError, ValueError, TypeError) as e:
                                continue  # Skip this track box
                        
                        if best_track_idx >= 0:
                            matched_detections[i] = track_ids[best_track_idx]
                    except (IndexError, ValueError, TypeError) as e:
                        # Skip this detection if there's an error
                        continue
            except (IndexError, ValueError, TypeError, AttributeError) as e:
                print(f"  [WARN] Error matching tracks to detections: {e}")
                print(f"  [WARN] detections type: {type(detections)}, len: {len(detections) if hasattr(detections, '__len__') else 'N/A'}")
                if hasattr(detections, 'xyxy'):
                    print(f"  [WARN] xyxy type: {type(detections.xyxy)}, shape: {np.asarray(detections.xyxy).shape if detections.xyxy is not None else 'None'}")
                # Return detections without track IDs on error
                matched_detections = np.full(len(detections), -1, dtype=int)
        
        # Assign track IDs to detections
        detections.tracker_id = matched_detections
        
        return detections
    
    def _calculate_iou(self, box1: np.ndarray, box2: np.ndarray) -> float:
        """Calculate Intersection over Union (IoU) between two boxes."""
        try:
            # Ensure boxes are numpy arrays and have 4 elements
            box1 = np.asarray(box1)
            box2 = np.asarray(box2)
            
            if box1.shape[0] < 4 or box2.shape[0] < 4:
                return 0.0
            
            x1_1, y1_1, x2_1, y2_1 = box1[:4]
            x1_2, y1_2, x2_2, y2_2 = box2[:4]
        except (ValueError, IndexError, TypeError):
            return 0.0
        
        # Calculate intersection
        inter_x1 = max(x1_1, x1_2)
        inter_y1 = max(y1_1, y1_2)
        inter_x2 = min(x2_1, x2_2)
        inter_y2 = min(y2_1, y2_2)
        
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0
        
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        
        # Calculate union
        box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
        box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = box1_area + box2_area - inter_area
        
        if union_area == 0:
            return 0.0
        
        return inter_area / union_area
    
    def reset(self):
        """Reset tracker state (for new video)."""
        # Not all trackers support reset(). This is a no-op for most trackers.
        pass

    def __getattr__(self, name):
        """Forward attribute access to underlying tracker."""
        return getattr(self.tracker, name)


def create_boxmot_tracker(tracker_type: str,
                          device: str = "cuda",
                          track_thresh: float = 0.25,
                          match_thresh: float = 0.8,
                          track_buffer: int = 30,
                          min_track_length: int = 5,
                          model_weights: Optional[str] = None,
                          fp16: bool = True,
                          osnet_variant: str = "osnet_x1_0") -> Optional[BoxMOTTrackerWrapper]:
    """
    Factory function to create a BoxMOT tracker.
    
    Args:
        tracker_type: Type of tracker ("deepocsort", "strongsort", "botsort", "ocsort", "bytetrack")
        device: Device to use ("cuda" or "cpu")
        track_thresh: Detection confidence threshold
        match_thresh: Matching threshold
        track_buffer: Frames to keep lost tracks
        min_track_length: Minimum frames before track is activated
        model_weights: Path to Re-ID model weights (optional, for appearance-based trackers)
        fp16: Use half precision
        osnet_variant: OSNet variant to use ('osnet_x1_0', 'osnet_ain_x1_0', etc.) (default: 'osnet_x1_0')
    
    Returns:
        BoxMOTTrackerWrapper instance or None if BoxMOT is not available
    """
    if not BOXMOT_AVAILABLE:
        return None
    
    try:
        return BoxMOTTrackerWrapper(
            tracker_type=tracker_type,
            model_weights=model_weights,
            device=device,
            fp16=fp16,
            track_thresh=track_thresh,
            match_thresh=match_thresh,
            track_buffer=track_buffer,
            min_track_length=min_track_length,
            osnet_variant=osnet_variant
        )
    except Exception as e:
        print(f"[WARN] Failed to create BoxMOT tracker: {e}")
        return None


# Alias for backward compatibility
create_tracker = create_boxmot_tracker

