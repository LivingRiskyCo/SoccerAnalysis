"""
Re-ID (Re-identification) Tracker Module
Provides feature-based matching for better ID persistence during occlusions

Supports soccer-specific fine-tuning for improved player Re-ID.
"""

import cv2
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import os
import json

# Logging setup
try:
    from logger_config import get_logger
    logger = get_logger("reid")
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Logger config not available - using basic logging")

# Import filter module
try:
    from reid_filter_module import ReIDFilterModule
    FILTER_MODULE_AVAILABLE = True
except ImportError as e:
    FILTER_MODULE_AVAILABLE = False
    logger.warning("⚠ Re-ID Filter Module not available (reid_filter_module.py not found or dependencies missing). "
                   "Filter module features will be disabled.")
    logger.debug(f"Re-ID Filter Module import error: {e}")

# Try to import torchreid (lightweight Re-ID library)
try:
    import torchreid
    TORCHREID_AVAILABLE = True  # type: ignore[reportConstantRedefinition]  # Set in try/except block
except ImportError as e:
    TORCHREID_AVAILABLE = False  # type: ignore[reportConstantRedefinition]  # Set in try/except block
    logger.warning("⚠ torchreid not available. Install with: pip install torchreid")
    logger.warning("  Re-ID features will use a simple CNN feature extractor instead.")
    logger.debug(f"torchreid import error: {e}")

# Try to import BoxMOT for optimized OSNet backends
try:
    import warnings
    # Suppress pkg_resources deprecation warning from BoxMOT (third-party library issue)
    # BoxMOT uses deprecated pkg_resources API that will be removed in setuptools 81
    # This is a BoxMOT library issue, not our code
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources is deprecated.*")
        from boxmot.appearance.reid_auto_backend import ReidAutoBackend
    import torch
    BOXMOT_REID_AVAILABLE = True  # type: ignore[reportConstantRedefinition]  # Set in try/except block
except ImportError as e:
    BOXMOT_REID_AVAILABLE = False  # type: ignore[reportConstantRedefinition]  # Set in try/except block
    logger.warning("⚠ BoxMOT Re-ID backends not available. Install with: pip install boxmot")
    logger.warning("  Will use torchreid (PyTorch backend) instead.")
    logger.debug(f"BoxMOT Re-ID import error: {e}")

# Fallback: Simple CNN feature extractor
class SimpleFeatureExtractor(nn.Module):
    """Simple CNN feature extractor for Re-ID (fallback if torchreid not available)"""
    def __init__(self, feature_dim=128):
        super().__init__()
        # Simple CNN architecture
        self.conv1 = nn.Conv2d(3, 32, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm2d(128)
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(128, feature_dim)
        self.relu = nn.ReLU(inplace=True)
        
    def forward(self, x):
        x = self.relu(self.bn1(self.conv1(x)))
        x = self.relu(self.bn2(self.conv2(x)))
        x = self.relu(self.bn3(self.conv3(x)))
        x = self.pool(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        # L2 normalize for cosine similarity
        x = torch.nn.functional.normalize(x, p=2, dim=1)
        return x


class ReIDTracker:
    """
    Re-ID Tracker for maintaining player identities using feature embeddings
    
    This class extracts features from player bounding boxes and matches them
    to existing tracks using cosine similarity, improving ID persistence
    during occlusions and temporary detection loss.
    """
    
    def __init__(self, 
                 feature_dim=128,
                 similarity_threshold=0.5,
                 max_features_per_track=50,
                 use_torchreid=True,
                 device=None,
                 osnet_variant='osnet_x1_0',
                 use_boxmot_backend=True,
                 enable_adaptive_thresholds=True,
                 enable_multi_frame_verification=True,
                 enable_quality_weighting=True,
                 enable_negative_filtering=True,
                 enable_position_verification=True,
                 enable_filter_module=True,
                 filter_min_bbox_area=200,
                 filter_min_bbox_width=10,
                 filter_min_bbox_height=15,
                 filter_min_confidence=0.25,
                 filter_max_blur_threshold=30.0):  # More lenient default (was 100.0, too strict for soccer videos)
        """
        Initialize Re-ID Tracker
        
        Args:
            feature_dim: Dimension of feature embeddings (default: 128)
            similarity_threshold: Minimum cosine similarity for matching (default: 0.5)
            max_features_per_track: Maximum number of features to store per track (default: 50)
            use_torchreid: Whether to use torchreid library if available (default: True)
            device: Device to run model on ('cuda' or 'cpu'). If None, auto-detects.
            osnet_variant: OSNet variant to use ('osnet_x1_0', 'osnet_ain_x1_0', 'osnet_ibn_x1_0', etc.)
            use_boxmot_backend: Whether to use BoxMOT optimized backends (ONNX/TensorRT) if available (default: True)
        """
        self.feature_dim = feature_dim
        self.similarity_threshold = similarity_threshold
        self.max_features_per_track = max_features_per_track
        
        # ENHANCED: Feature flags for new improvements
        self.enable_adaptive_thresholds = enable_adaptive_thresholds
        self.enable_multi_frame_verification = enable_multi_frame_verification
        self.enable_quality_weighting = enable_quality_weighting
        self.enable_negative_filtering = enable_negative_filtering
        self.enable_position_verification = enable_position_verification
        
        # Auto-detect device with proper CUDA checking
        if device is None:
            device = self._detect_device()
        self.device = device
        
        # Store features for each track ID
        self.track_features: Dict[int, List[np.ndarray]] = defaultdict(list)
        
        # ENHANCED: Store track history with metadata (frame_num, confidence, quality)
        self.track_history: Dict[int, List[Dict]] = defaultdict(list)  # track_id -> [{'feature': ..., 'frame': ..., 'confidence': ..., 'quality': ...}, ...]
        self.max_history_length = 10  # Keep last 10 features with metadata
        
        # ENHANCED: Multi-frame verification - track match history per track
        self.track_match_history: Dict[int, List[Tuple[str, float, int]]] = defaultdict(list)  # track_id -> [(player_id, similarity, frame_num), ...]
        self.verification_frames_required = 2  # Require 2-3 consistent matches
        
        # ENHANCED: Track positions and velocities for motion verification
        self.track_positions: Dict[int, List[Tuple[float, float, int]]] = defaultdict(list)  # track_id -> [(x, y, frame_num), ...]
        self.track_velocities: Dict[int, Tuple[float, float]] = {}  # track_id -> (vx, vy)
        
        # Store color features for each track ID (team color, ball color)
        self.track_color_features: Dict[int, Dict[str, np.ndarray]] = defaultdict(dict)
        
        # Initialize feature extractor
        self.feature_extractor = None
        self.use_torchreid = use_torchreid and TORCHREID_AVAILABLE
        
        # Soccer-specific training attributes (initialized here for type checking)
        self.soccer_training_enabled: bool = False
        self.training_data_dir: Optional[str] = None
        self.osnet_variant = osnet_variant
        self.use_boxmot_backend = use_boxmot_backend and BOXMOT_REID_AVAILABLE
        self.backend_type = None  # Will be set during initialization
        
        if self.use_torchreid:
            # Try BoxMOT optimized backend first (faster), fallback to torchreid
            if self.use_boxmot_backend:
                if self._init_boxmot_backend():
                    self.backend_type = 'boxmot'
                else:
                    self._init_torchreid()
                    self.backend_type = 'torchreid'
            else:
                self._init_torchreid()
                self.backend_type = 'torchreid'
        else:
            self._init_simple_extractor()
            self.backend_type = 'simple_cnn'
        
        # Initialize filter module
        self.filter_module = None
        if enable_filter_module and FILTER_MODULE_AVAILABLE:
            self.filter_module = ReIDFilterModule(
                min_bbox_area=filter_min_bbox_area,
                min_bbox_width=filter_min_bbox_width,
                min_bbox_height=filter_min_bbox_height,
                min_confidence=filter_min_confidence,
                max_blur_threshold=filter_max_blur_threshold,
                enable_blur_check=True,
                enable_contrast_check=True,
                enable_occlusion_check=True
            )
            print("✓ Re-ID Filter Module initialized (pre-filters low-quality detections)")
        elif enable_filter_module and not FILTER_MODULE_AVAILABLE:
            print("⚠ Re-ID Filter Module requested but not available")
        
        backend_info = f"{self.backend_type} ({self.osnet_variant})" if self.backend_type != 'simple_cnn' else 'simple CNN'
        print(f"✓ Re-ID Tracker initialized (device: {self.device}, method: {backend_info})")
    
    def _detect_device(self):
        """Detect the best available device (CUDA if available and working, else CPU)"""
        # First check if CUDA is available
        if not torch.cuda.is_available():
            return 'cpu'
        
        # Try to actually use CUDA to verify it works
        try:
            # Try a simple operation on CUDA
            test_tensor = torch.tensor([1.0]).cuda()
            _ = test_tensor * 2
            del test_tensor
            torch.cuda.empty_cache()
            return 'cuda'
        except Exception:
            # CUDA is reported as available but doesn't work (e.g., not compiled with CUDA)
            print("⚠ CUDA reported as available but not usable, falling back to CPU")
            return 'cpu'
    
    def _init_boxmot_backend(self):
        """Initialize BoxMOT optimized backend (ONNX/TensorRT/OpenVINO) for faster inference"""
        try:
            from boxmot.utils import WEIGHTS
            import os
            
            # Ensure WEIGHTS directory exists (BoxMOT needs it to download/store models)
            if not os.path.exists(WEIGHTS):
                try:
                    os.makedirs(WEIGHTS, exist_ok=True)
                    print(f"  [INFO] Created weights directory: {WEIGHTS}")
                except Exception as e:
                    print(f"  [WARN] Could not create weights directory: {e}")
            from pathlib import Path
            
            # Map OSNet variant to BoxMOT model weights
            # BoxMOT uses pre-trained weights from various datasets
            osnet_weights_map = {
                'osnet_x1_0': WEIGHTS / "osnet_x1_0_msmt17.pt",
                'osnet_ain_x1_0': WEIGHTS / "osnet_ain_x1_0_msmt17.pt",
                'osnet_ibn_x1_0': WEIGHTS / "osnet_ibn_x1_0_msmt17.pt",
                'osnet_x0_75': WEIGHTS / "osnet_x0_75_msmt17.pt",
                'osnet_x0_5': WEIGHTS / "osnet_x0_5_msmt17.pt",
                'osnet_x0_25': WEIGHTS / "osnet_x0_25_msmt17.pt",
            }
            
            # Get base weights path for selected variant
            base_weights_path = osnet_weights_map.get(self.osnet_variant, osnet_weights_map['osnet_x1_0'])
            
            # AUTO-DETECT EXPORTED MODELS: Check for optimized formats first (faster inference)
            # Priority: ONNX > TensorRT > OpenVINO > TorchScript > PyTorch
            # BoxMOT's ReidAutoBackend automatically detects format by file extension
            weights_path = None
            exported_formats = [
                (base_weights_path.parent / f"{base_weights_path.stem}.onnx", "ONNX"),
                (base_weights_path.parent / f"{base_weights_path.stem}.engine", "TensorRT"),
                (base_weights_path.parent / f"{base_weights_path.stem}_openvino_model", "OpenVINO"),
                (base_weights_path.parent / f"{base_weights_path.stem}.torchscript.pt", "TorchScript"),
            ]
            
            # Check for exported models in same directory as .pt file
            for exported_path, format_name in exported_formats:
                if exported_path.exists():
                    weights_path = exported_path
                    print(f"  → Found exported {format_name} model: {exported_path.name}")
                    print(f"     Using optimized format for faster inference")
                    break
            
            # Also check in current directory and common export locations
            if weights_path is None:
                search_dirs = [
                    Path("."),  # Current directory
                    Path("exported_models"),  # Common export directory
                    base_weights_path.parent,  # Same as .pt file
                ]
                
                for search_dir in search_dirs:
                    if search_dir.exists():
                        for exported_path, format_name in exported_formats:
                            check_path = search_dir / exported_path.name
                            if check_path.exists():
                                weights_path = check_path
                                print(f"  → Found exported {format_name} model: {check_path}")
                                print(f"     Using optimized format for faster inference")
                                break
                        if weights_path:
                            break
            
            # Fallback to original .pt file if no exported model found
            if weights_path is None:
                weights_path = base_weights_path
                print(f"  → Using PyTorch model: {base_weights_path.name}")
                print(f"     (Export to ONNX/TensorRT for faster inference)")
            
            # Convert device string to BoxMOT format
            # BoxMOT expects '0', '1', etc. for CUDA devices, or 'cpu' for CPU
            if isinstance(self.device, str):
                if self.device == 'cuda':
                    # BoxMOT expects '0' for first CUDA device, not 'cuda'
                    if torch.cuda.is_available():
                        boxmot_device = '0'  # First CUDA device
                        device_obj = torch.device('cuda:0')
                    else:
                        boxmot_device = 'cpu'
                        device_obj = torch.device('cpu')
                elif self.device.startswith('cuda:'):
                    # Extract device number from 'cuda:0', 'cuda:1', etc.
                    device_num = self.device.split(':')[1] if ':' in self.device else '0'
                    boxmot_device = device_num
                    device_obj = torch.device(self.device)
                else:
                    boxmot_device = self.device
                    device_obj = torch.device(self.device)
            else:
                # torch.device object
                device_obj = self.device
                if device_obj.type == 'cuda':
                    boxmot_device = str(device_obj.index) if device_obj.index is not None else '0'
                else:
                    boxmot_device = 'cpu'
            
            # Initialize BoxMOT backend (auto-selects best backend: ONNX > TensorRT > OpenVINO > PyTorch)
            # BoxMOT expects device as string ('0', '1', 'cpu'), not torch.device
            backend = ReidAutoBackend(
                weights=weights_path,
                device=boxmot_device,  # type: ignore[reportArgumentType]  # Use string format for BoxMOT
                half=(device_obj.type == 'cuda')  # Use FP16 on GPU for speed
            )
            
            # BoxMOT's ReidAutoBackend returns a backend object
            # The backend object should have a model attribute that is the actual model
            # For PyTorchBackend, we need to access the underlying model
            if hasattr(backend, 'model'):
                # The .model attribute is the actual PyTorch model
                self.feature_extractor = backend.model
            elif hasattr(backend, '__call__') or callable(backend):
                # Some backends are directly callable
                self.feature_extractor = backend
            else:
                # Try to find the model in the backend
                # BoxMOT backends might have different structures
                if hasattr(backend, 'net'):
                    self.feature_extractor = backend.net
                elif hasattr(backend, 'engine'):
                    self.feature_extractor = backend.engine
                else:
                    self.feature_extractor = backend
            
            # Test the backend and detect feature dimension
            test_input = torch.randn(1, 3, 64, 128)
            if device_obj.type == 'cuda':
                test_input = test_input.cuda()
            
            # Test the feature extractor
            with torch.no_grad():
                test_output = self.feature_extractor(test_input)  # type: ignore[reportCallIssue]
            
            # Detect actual feature dimension from test output
            if isinstance(test_output, torch.Tensor):
                actual_feature_dim = test_output.shape[1] if len(test_output.shape) > 1 else test_output.shape[0]
            elif isinstance(test_output, np.ndarray):
                actual_feature_dim = test_output.shape[1] if len(test_output.shape) > 1 else test_output.shape[0]
            else:
                # Try to get shape attribute
                actual_feature_dim = getattr(test_output, 'shape', [None, self.feature_dim])[1] or self.feature_dim
            
            # Clean up test tensors
            del test_input, test_output
            if device_obj.type == 'cuda':
                torch.cuda.empty_cache()
            
            if actual_feature_dim != self.feature_dim:
                print(f"  → Detected feature dimension: {actual_feature_dim} (updating from {self.feature_dim})")
                self.feature_dim = actual_feature_dim
            
            backend_name = self.feature_extractor.__class__.__name__.replace('Backend', '')
            print(f"✓ Loaded BoxMOT {self.osnet_variant} via {backend_name} backend on device {boxmot_device}")
            return True
            
        except Exception as e:
            print(f"⚠ Could not initialize BoxMOT backend: {e}")
            print("  Falling back to torchreid...")
            return False
    
    def _init_torchreid(self):
        """Initialize torchreid model (OSNet - lightweight and fast)"""
        try:
            # Use selected OSNet variant
            model_name = self.osnet_variant
            
            # Check if variant is supported by torchreid
            supported_variants = [
                'osnet_x1_0', 'osnet_x0_75', 'osnet_x0_5', 'osnet_x0_25', 
                'osnet_ibn_x1_0',
                'osnet_ain_x1_0', 'osnet_ain_x0_75', 'osnet_ain_x0_5', 'osnet_ain_x0_25'
            ]
            if model_name not in supported_variants:
                print(f"⚠ torchreid doesn't support {model_name}, falling back to osnet_x1_0")
                model_name = 'osnet_x1_0'
            
            self.feature_extractor = torchreid.models.build_model(
                name=model_name,
                num_classes=1,  # Dummy, we only need features
                loss='softmax',
                pretrained=True
            )
            self.feature_extractor.eval()
            
            # Try to move to device, fallback to CPU if CUDA fails
            try:
                self.feature_extractor.to(self.device)
                # Verify device actually works
                if self.device == 'cuda':
                    test_input = torch.randn(1, 3, 64, 128).to(self.device)
                    _ = self.feature_extractor(test_input)
                    del test_input
                    torch.cuda.empty_cache()
            except Exception as device_error:
                print(f"⚠ Could not use {self.device} device: {device_error}")
                print("  Falling back to CPU...")
                self.device = 'cpu'
                self.feature_extractor.to(self.device)
            
            print(f"✓ Loaded torchreid model: {model_name} on {self.device}")
            
            # Detect actual feature dimension from model output
            # OSNet outputs 512-dimensional features, not 128
            with torch.no_grad():
                test_input = torch.randn(1, 3, 64, 128).to(self.device)
                test_output = self.feature_extractor(test_input)
                actual_feature_dim = test_output.shape[1]  # Get feature dimension from output
                del test_input, test_output
                if self.device == 'cuda':
                    torch.cuda.empty_cache()
            
            # Update feature_dim to match model output
            if actual_feature_dim != self.feature_dim:
                print(f"  → Detected feature dimension: {actual_feature_dim} (updating from {self.feature_dim})")
                self.feature_dim = actual_feature_dim
        except Exception as e:
            print(f"⚠ Could not load torchreid model: {e}")
            print("  Falling back to simple feature extractor...")
            self.use_torchreid = False
            self._init_simple_extractor()
    
    def _init_simple_extractor(self):
        """Initialize simple CNN feature extractor (fallback)"""
        self.feature_extractor = SimpleFeatureExtractor(feature_dim=self.feature_dim)
        _ = self.feature_extractor.eval()  # Returns self, but we don't need it
        
        # Try to move to device, fallback to CPU if CUDA fails
        try:
            _ = self.feature_extractor.to(self.device)  # Returns self, but we don't need it
            # Verify device actually works
            if self.device == 'cuda':
                test_input = torch.randn(1, 3, 64, 128).to(self.device)
                _ = self.feature_extractor(test_input)
                del test_input
                torch.cuda.empty_cache()
        except Exception as device_error:
            print(f"⚠ Could not use {self.device} device: {device_error}")
            print("  Falling back to CPU...")
            self.device = 'cpu'
            _ = self.feature_extractor.to(self.device)  # Returns self, but we don't need it
        
        print(f"✓ Using simple CNN feature extractor on {self.device}")
    
    def extract_color_features(self, frame: np.ndarray, detections, team_colors=None, ball_colors=None):
        """
        Extract color features (team color and ball color) from bounding boxes
        
        Args:
            frame: Input frame (BGR format)
            detections: Supervision Detections object with bounding boxes
            team_colors: Team color configuration dict (optional, for future use)
            ball_colors: Ball color configuration dict (optional, for future use)
            
        Returns:
            color_features: Dict with 'team_color' and 'ball_color' arrays, or None
        """
        if len(detections) == 0:
            return None
        
        color_features = {
            'team_color': np.zeros((len(detections), 3), dtype=np.float32),  # BGR average
            'ball_color': np.zeros((len(detections), 3), dtype=np.float32)   # BGR average
        }
        
        for i, (x1, y1, x2, y2) in enumerate(detections.xyxy):
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            if x2 > x1 and y2 > y1 and x1 >= 0 and y1 >= 0:
                h, w = frame.shape[:2]
                
                # Sample jersey region (top 10-40% of bounding box) for team color
                sample_y1 = int(y1 + (y2 - y1) * 0.1)
                sample_y2 = int(y1 + (y2 - y1) * 0.4)
                sample_x1 = int(x1 + (x2 - x1) * 0.2)
                sample_x2 = int(x1 + (x2 - x1) * 0.8)
                
                sample_y1 = max(0, min(h, sample_y1))
                sample_y2 = max(0, min(h, sample_y2))
                sample_x1 = max(0, min(w, sample_x1))
                sample_x2 = max(0, min(w, sample_x2))
                
                if sample_y2 > sample_y1 and sample_x2 > sample_x1:
                    jersey_region = frame[sample_y1:sample_y2, sample_x1:sample_x2]
                    if jersey_region.size > 0:
                        # Average BGR color of jersey region
                        color_features['team_color'][i] = np.mean(jersey_region.reshape(-1, 3), axis=0).astype(np.float32)
                
                # Sample center region for ball color (center 20% of bounding box)
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                radius = max(5, min(15, (x2 - x1) // 4, (y2 - y1) // 4))
                
                if radius > 0:
                    ball_y1 = max(0, center_y - radius)
                    ball_y2 = min(h, center_y + radius)
                    ball_x1 = max(0, center_x - radius)
                    ball_x2 = min(w, center_x + radius)
                    
                    if ball_y2 > ball_y1 and ball_x2 > ball_x1:
                        ball_region = frame[ball_y1:ball_y2, ball_x1:ball_x2]
                        if ball_region.size > 0:
                            color_features['ball_color'][i] = np.mean(ball_region.reshape(-1, 3), axis=0).astype(np.float32)
        
        return color_features
    
    def extract_foot_features(self, frame: np.ndarray, detections) -> np.ndarray:
        """
        Extract features from foot/base region of player bounding boxes
        Foot region is typically the bottom 10-30% of the bounding box (shoes/feet area, not shorts which are at 60-80%)
        
        Args:
            frame: Input frame (BGR format)
            detections: Supervision Detections object with bounding boxes
            
        Returns:
            foot_features: Array of shape (N, feature_dim) where N is number of detections
        """
        if len(detections) == 0:
            return np.array([])
        
        # Extract foot region crops from bounding boxes
        foot_crops = []
        valid_indices = []
        
        frame_h, frame_w = frame.shape[:2]
        
        for i, (x1, y1, x2, y2) in enumerate(detections.xyxy):
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # Foot region: bottom 10-30% of bounding box (where shoes/feet are, not shorts)
            # Using 70-90% from top to capture feet/shoes area (shorts are at 60-80%)
            bbox_height = y2 - y1
            foot_y1 = int(y1 + bbox_height * 0.70)  # Start at 70% from top (bottom 30%)
            foot_y2 = int(y1 + bbox_height * 0.90)  # End at 90% from top (bottom 10%)
            
            # Clamp to frame boundaries
            x1_clamped = max(0, min(x1, frame_w - 2))
            x2_clamped = max(x1_clamped + 1, min(x2, frame_w))
            foot_y1_clamped = max(0, min(foot_y1, frame_h - 2))
            foot_y2_clamped = max(foot_y1_clamped + 1, min(foot_y2, frame_h))
            
            # Ensure valid foot region
            if x2_clamped > x1_clamped and foot_y2_clamped > foot_y1_clamped:
                foot_crop = frame[foot_y1_clamped:foot_y2_clamped, x1_clamped:x2_clamped]
                
                if foot_crop.size > 0 and foot_crop.shape[0] >= 8 and foot_crop.shape[1] >= 8:
                    try:
                        # Resize to standard size for feature extraction
                        foot_crop_resized = cv2.resize(foot_crop, (64, 32))  # Wider than tall (feet are horizontal)
                        foot_crops.append(foot_crop_resized)
                        valid_indices.append(i)
                    except Exception:
                        pass
        
        if len(foot_crops) == 0:
            return np.array([])
        
        # Convert to tensor
        foot_crops_array = np.array(foot_crops)
        foot_crops_tensor = torch.from_numpy(foot_crops_array).permute(0, 3, 1, 2).float() / 255.0
        foot_crops_tensor = foot_crops_tensor.to(self.device)
        
        # Extract features using the same feature extractor
        with torch.no_grad():
            if self.feature_extractor is None:
                raise RuntimeError("Feature extractor is None")
            
            try:
                # First try: Call backend directly
                if callable(self.feature_extractor):
                    foot_features = self.feature_extractor(foot_crops_tensor)  # type: ignore[reportCallIssue]
                else:
                    raise TypeError("Feature extractor is not callable")
            except (TypeError, AttributeError):
                # Fallback: Try accessing .model attribute
                if hasattr(self.feature_extractor, 'model') and self.feature_extractor.model is not None:
                    if callable(self.feature_extractor.model):
                        foot_features = self.feature_extractor.model(foot_crops_tensor)  # type: ignore[reportCallIssue]
                    elif hasattr(self.feature_extractor.model, 'forward'):
                        foot_features = self.feature_extractor.model.forward(foot_crops_tensor)
                    else:
                        raise RuntimeError("BoxMOT backend model is not callable")
                elif hasattr(self.feature_extractor, 'forward'):
                    foot_features = self.feature_extractor.forward(foot_crops_tensor)
                else:
                    raise RuntimeError("Could not determine how to call feature extractor")
            
            # Convert to numpy
            if isinstance(foot_features, torch.Tensor):
                foot_features = foot_features.cpu().numpy()
            elif not isinstance(foot_features, np.ndarray):
                foot_features = np.array(foot_features)
        
        # Create full feature array (with zeros for invalid detections)
        full_foot_features = np.zeros((len(detections), foot_features.shape[1] if len(foot_features) > 0 else self.feature_dim))
        for idx, valid_idx in enumerate(valid_indices):
            if idx < len(foot_features):
                full_foot_features[valid_idx] = foot_features[idx]
        
        return full_foot_features
    
    def extract_jersey_features(self, frame: np.ndarray, detections) -> np.ndarray:
        """
        Extract features from jersey/torso region of player bounding boxes
        Jersey region is typically the upper 30-60% of the bounding box (torso area)
        
        Args:
            frame: Input frame (BGR format)
            detections: Supervision Detections object with bounding boxes
            
        Returns:
            jersey_features: Array of shape (N, feature_dim) where N is number of detections
        """
        if len(detections) == 0:
            return np.array([])
        
        # Extract jersey region crops from bounding boxes
        jersey_crops = []
        valid_indices = []
        
        frame_h, frame_w = frame.shape[:2]
        
        for i, (x1, y1, x2, y2) in enumerate(detections.xyxy):
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # Jersey region: upper 30-60% of bounding box (torso area)
            bbox_height = y2 - y1
            jersey_y1 = int(y1 + bbox_height * 0.30)  # Start at 30% from top
            jersey_y2 = int(y1 + bbox_height * 0.60)  # End at 60% from top
            
            # Clamp to frame boundaries
            x1_clamped = max(0, min(x1, frame_w - 2))
            x2_clamped = max(x1_clamped + 1, min(x2, frame_w))
            jersey_y1_clamped = max(0, min(jersey_y1, frame_h - 2))
            jersey_y2_clamped = max(jersey_y1_clamped + 1, min(jersey_y2, frame_h))
            
            # Ensure valid jersey region
            if x2_clamped > x1_clamped and jersey_y2_clamped > jersey_y1_clamped:
                jersey_crop = frame[jersey_y1_clamped:jersey_y2_clamped, x1_clamped:x2_clamped]
                
                if jersey_crop.size > 0 and jersey_crop.shape[0] >= 8 and jersey_crop.shape[1] >= 8:
                    try:
                        # Resize to standard size for feature extraction
                        jersey_crop_resized = cv2.resize(jersey_crop, (128, 128))  # Square for jersey
                        jersey_crops.append(jersey_crop_resized)
                        valid_indices.append(i)
                    except Exception:
                        pass
        
        if len(jersey_crops) == 0:
            return np.array([])
        
        # Convert to tensor
        jersey_crops_array = np.array(jersey_crops)
        jersey_crops_tensor = torch.from_numpy(jersey_crops_array).permute(0, 3, 1, 2).float() / 255.0
        jersey_crops_tensor = jersey_crops_tensor.to(self.device)
        
        # Extract features using the same feature extractor
        with torch.no_grad():
            if self.feature_extractor is None:
                raise RuntimeError("Feature extractor is None")
            
            try:
                # First try: Call backend directly
                if callable(self.feature_extractor):
                    jersey_features = self.feature_extractor(jersey_crops_tensor)  # type: ignore[reportCallIssue]
                else:
                    raise TypeError("Feature extractor is not callable")
            except (TypeError, AttributeError):
                # Fallback: Try accessing .model attribute
                if hasattr(self.feature_extractor, 'model') and self.feature_extractor.model is not None:
                    if callable(self.feature_extractor.model):
                        jersey_features = self.feature_extractor.model(jersey_crops_tensor)  # type: ignore[reportCallIssue]
                    elif hasattr(self.feature_extractor.model, 'forward'):
                        jersey_features = self.feature_extractor.model.forward(jersey_crops_tensor)
                    else:
                        raise RuntimeError("BoxMOT backend model is not callable")
                elif hasattr(self.feature_extractor, 'forward'):
                    jersey_features = self.feature_extractor.forward(jersey_crops_tensor)
                else:
                    raise RuntimeError("Could not determine how to call feature extractor")
            
            # Convert to numpy
            if isinstance(jersey_features, torch.Tensor):
                jersey_features = jersey_features.cpu().numpy()
            elif not isinstance(jersey_features, np.ndarray):
                jersey_features = np.array(jersey_features)
        
        # Create full feature array (with zeros for invalid detections)
        full_jersey_features = np.zeros((len(detections), jersey_features.shape[1] if len(jersey_features) > 0 else self.feature_dim))
        for idx, valid_idx in enumerate(valid_indices):
            if idx < len(jersey_features):
                full_jersey_features[valid_idx] = jersey_features[idx]
        
        return full_jersey_features
    
    def extract_body_features(self, frame: np.ndarray, detections) -> np.ndarray:
        """
        Extract features from full body region of player bounding boxes
        This is similar to extract_features but explicitly for body region
        
        Args:
            frame: Input frame (BGR format)
            detections: Supervision Detections object with bounding boxes
            
        Returns:
            body_features: Array of shape (N, feature_dim) where N is number of detections
        """
        # Body features are the same as general features (full bbox)
        # This method exists for clarity and consistency with jersey/foot features
        return self.extract_features(frame, detections)
    
    def extract_features(self, frame: np.ndarray, detections, team_colors=None, ball_colors=None) -> np.ndarray:
        """
        Extract features from bounding boxes in the frame
        
        Args:
            frame: Input frame (BGR format)
            detections: Supervision Detections object with bounding boxes
            team_colors: Optional team color configuration for color feature extraction
            ball_colors: Optional ball color configuration for color feature extraction
            
        Returns:
            features: Array of shape (N, feature_dim) where N is number of detections
        """
        if len(detections) == 0:
            return np.array([])
        
        # NEW: Pre-filter detections using filter module
        if self.filter_module is not None:
            # Get confidences if available
            confidences = detections.confidence if hasattr(detections, 'confidence') else None
            
            # Filter detections - create quality mask
            quality_mask = np.ones(len(detections), dtype=bool)
            for i, bbox in enumerate(detections.xyxy):
                confidence = float(confidences[i]) if confidences is not None and i < len(confidences) else 1.0
                passed, reason = self.filter_module.filter_detection(frame, bbox, confidence)
                quality_mask[i] = passed
            
            # Only process filtered detections
            if not np.any(quality_mask):
                return np.array([])
            
            # Create filtered indices list
            filtered_indices = np.where(quality_mask)[0].tolist()
        else:
            filtered_indices = list(range(len(detections)))
        
        # Extract crops from bounding boxes (only for filtered detections)
        crops = []
        valid_indices = []
        rejection_reasons = []  # Track why boxes were rejected (for diagnostics)
        
        frame_h, frame_w = frame.shape[:2]
        
        for i in filtered_indices:
            x1, y1, x2, y2 = detections.xyxy[i]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # DIAGNOSTIC: Track rejection reasons
            rejection_reason = None
            
            # First check for obviously invalid boxes
            if not (x2 > x1 and y2 > y1):
                rejection_reason = f"invalid_size(w={x2-x1},h={y2-y1},orig=({x1},{y1},{x2},{y2}))"
            else:
                # Clamp coordinates to frame boundaries (handle out-of-bounds gracefully)
                # CRITICAL FIX: Ensure boxes don't collapse to 1 pixel after clamping
                # Clamp x1 and y1 to valid range
                x1_clamped = max(0, min(x1, frame_w - 2))  # Leave room for at least 2px width
                y1_clamped = max(0, min(y1, frame_h - 2))  # Leave room for at least 2px height
                # Clamp x2 and y2, but ensure they're > x1/y1
                x2_clamped = max(x1_clamped + 1, min(x2, frame_w))  # Ensure x2 > x1
                y2_clamped = max(y1_clamped + 1, min(y2, frame_h))  # Ensure y2 > y1
                
                # Final validation: ensure box is still valid after clamping
                if x2_clamped <= x1_clamped or y2_clamped <= y1_clamped:
                    rejection_reason = f"collapsed_after_clamp(x:{x1_clamped}->{x2_clamped},y:{y1_clamped}->{y2_clamped})"
                else:
                    crop = frame[y1_clamped:y2_clamped, x1_clamped:x2_clamped]
                    if crop.size == 0:
                        rejection_reason = f"empty_crop(size=0)"
                    elif crop.shape[0] < 10 or crop.shape[1] < 10:
                        rejection_reason = f"too_small(h={crop.shape[0]},w={crop.shape[1]},orig=({x1},{y1},{x2},{y2}),clamped=({x1_clamped},{y1_clamped},{x2_clamped},{y2_clamped}))"
                    else:
                        # Valid crop!
                        try:
                            crop_resized = cv2.resize(crop, (64, 128))  # Smaller for speed
                            crops.append(crop_resized)
                            valid_indices.append(i)
                        except Exception as e:
                            rejection_reason = f"resize_failed({str(e)})"
            
            if rejection_reason:
                rejection_reasons.append((i, rejection_reason))
        
        # DIAGNOSTIC: Log rejection stats on first call or when many rejected
        if len(rejection_reasons) > len(detections) * 0.5:  # > 50% rejected
            print(f"\n⚠ Re-ID Feature Extraction: {len(rejection_reasons)}/{len(detections)} detections rejected:")
            reason_counts = {}
            for _, reason in rejection_reasons:
                reason_type = reason.split('(')[0]
                reason_counts[reason_type] = reason_counts.get(reason_type, 0) + 1
            for reason_type, count in reason_counts.items():
                print(f"   • {reason_type}: {count} detections")
            # Show first few examples
            print(f"   Examples: {', '.join([f'#{i}: {r}' for i, r in rejection_reasons[:3]])}")
        
        if len(crops) == 0:
            return np.array([])
        
        # Convert to tensor
        crops_array = np.array(crops)
        crops_tensor = torch.from_numpy(crops_array).permute(0, 3, 1, 2).float() / 255.0
        crops_tensor = crops_tensor.to(self.device)
        
        # Extract features
        with torch.no_grad():
            # BoxMOT backend: Try calling directly first, then fall back to .model
            if self.feature_extractor is None:
                raise RuntimeError("Feature extractor is None")
            
            try:
                # First try: Call backend directly (ReidAutoBackend should be callable)
                if callable(self.feature_extractor):
                    features = self.feature_extractor(crops_tensor)  # type: ignore[reportCallIssue]
                else:
                    raise TypeError("Feature extractor is not callable")
            except (TypeError, AttributeError):
                # Fallback: Try accessing .model attribute
                if hasattr(self.feature_extractor, 'model') and self.feature_extractor.model is not None:
                    if callable(self.feature_extractor.model):
                        features = self.feature_extractor.model(crops_tensor)  # type: ignore[reportCallIssue]
                    elif hasattr(self.feature_extractor.model, 'forward'):
                        features = self.feature_extractor.model.forward(crops_tensor)
                    else:
                        raise RuntimeError("BoxMOT backend model is not callable")
                elif hasattr(self.feature_extractor, 'forward'):
                    features = self.feature_extractor.forward(crops_tensor)
                else:
                    raise RuntimeError("Could not determine how to call feature extractor")
            
            # Convert to numpy (handle both tensor and numpy output)
            if isinstance(features, torch.Tensor):
                features = features.cpu().numpy()
            elif not isinstance(features, np.ndarray):
                features = np.array(features)
        
        # Get actual feature dimension from extracted features
        # OSNet outputs 512-dimensional features, not 128
        if len(features) > 0:
            actual_feature_dim = features.shape[1]
            # Update self.feature_dim if it doesn't match (for torchreid models)
            if actual_feature_dim != self.feature_dim:
                self.feature_dim = actual_feature_dim
        
        # Create full feature array (with NaN for invalid detections)
        # Use detected feature dimension (now updated in self.feature_dim)
        # Map back to original detection indices (accounting for filter module)
        full_features = np.full((len(detections), self.feature_dim), np.nan, dtype=np.float32)
        for idx, valid_idx in enumerate(valid_indices):
            if idx < len(features):
                # Ensure feature dimension matches
                if features[idx].shape[0] == self.feature_dim:
                    full_features[valid_idx] = features[idx]
                else:
                    # Dimension mismatch - skip this feature
                    print(f"⚠ Feature dimension mismatch: expected {self.feature_dim}, got {features[idx].shape[0]}")
        
        return full_features
    
    def update_tracks(self, track_ids: List[Optional[int]], features: np.ndarray, 
                     color_features: Optional[Dict] = None,
                     frame_num: Optional[int] = None,
                     confidences: Optional[np.ndarray] = None,
                     positions: Optional[np.ndarray] = None,
                     quality_scores: Optional[np.ndarray] = None):
        """
        Update stored features for existing tracks
        
        Args:
            track_ids: List of track IDs (can be None for new detections)
            features: Feature array of shape (N, feature_dim)
            color_features: Optional dict with 'team_color' and 'ball_color' arrays
            frame_num: Optional current frame number for history tracking
            confidences: Optional detection confidence scores (N,)
            positions: Optional detection positions (N, 2) as (center_x, center_y)
            quality_scores: Optional image quality scores (N,)
        """
        for i, (track_id, feature) in enumerate(zip(track_ids, features)):
            if track_id is not None and not np.isnan(feature).any():
                # Add visual feature to track's history
                self.track_features[track_id].append(feature.copy())
                
                # ENHANCED: Store track history with metadata
                history_entry = {
                    'feature': feature.copy(),
                    'frame': frame_num if frame_num is not None else -1,
                    'confidence': float(confidences[i]) if confidences is not None and i < len(confidences) else 0.5,
                    'quality': float(quality_scores[i]) if quality_scores is not None and i < len(quality_scores) else 0.5
                }
                self.track_history[track_id].append(history_entry)
                
                # ENHANCED: Update track positions for motion verification
                if positions is not None and i < len(positions):
                    pos = positions[i]
                    if len(pos) >= 2:
                        self.track_positions[track_id].append((float(pos[0]), float(pos[1]), frame_num if frame_num is not None else -1))
                        # Keep last 20 positions
                        if len(self.track_positions[track_id]) > 20:
                            self.track_positions[track_id].pop(0)
                        
                        # Calculate velocity from recent positions
                        if len(self.track_positions[track_id]) >= 2:
                            recent_positions = self.track_positions[track_id][-5:]  # Last 5 positions
                            if len(recent_positions) >= 2:
                                # Calculate average velocity
                                dx = sum(recent_positions[j][0] - recent_positions[j-1][0] for j in range(1, len(recent_positions))) / (len(recent_positions) - 1)
                                dy = sum(recent_positions[j][1] - recent_positions[j-1][1] for j in range(1, len(recent_positions))) / (len(recent_positions) - 1)
                                self.track_velocities[track_id] = (dx, dy)
                
                # Limit history size
                if len(self.track_features[track_id]) > self.max_features_per_track:
                    _ = self.track_features[track_id].pop(0)  # Remove oldest, discard value
                
                # Limit history metadata size
                if len(self.track_history[track_id]) > self.max_history_length:
                    self.track_history[track_id].pop(0)
                
                # Store color features if available
                if color_features is not None:
                    if 'team_color' in color_features and i < len(color_features['team_color']):
                        # Store average team color (update with exponential moving average)
                        if 'team_color' not in self.track_color_features[track_id]:
                            self.track_color_features[track_id]['team_color'] = color_features['team_color'][i].copy()
                        else:
                            # EMA: 70% old, 30% new
                            self.track_color_features[track_id]['team_color'] = (
                                0.7 * self.track_color_features[track_id]['team_color'] + 
                                0.3 * color_features['team_color'][i]
                            )
                    
                    if 'ball_color' in color_features and i < len(color_features['ball_color']):
                        # Store average ball color (update with exponential moving average)
                        if 'ball_color' not in self.track_color_features[track_id]:
                            self.track_color_features[track_id]['ball_color'] = color_features['ball_color'][i].copy()
                        else:
                            # EMA: 70% old, 30% new
                            self.track_color_features[track_id]['ball_color'] = (
                                0.7 * self.track_color_features[track_id]['ball_color'] + 
                                0.3 * color_features['ball_color'][i]
                            )
    
    def match_detections_to_tracks(self, 
                                   new_features: np.ndarray,
                                   existing_track_ids: List[int],
                                   position_similarity: Optional[np.ndarray] = None,
                                   new_color_features: Optional[Dict] = None) -> Dict[int, int]:
        """
        Match new detections to existing tracks using feature similarity and color
        
        Args:
            new_features: Features for new detections (N, feature_dim)
            existing_track_ids: List of existing track IDs to match against
            position_similarity: Optional position-based similarity matrix (N, M)
                                to combine with feature similarity
            new_color_features: Optional dict with 'team_color' and 'ball_color' arrays for new detections
        
        Returns:
            matches: Dictionary mapping detection index to track_id
        """
        if len(new_features) == 0 or len(existing_track_ids) == 0:
            return {}
        
        matches = {}
        
        # ENHANCED: Get features using track history matching
        track_avg_features = {}
        for track_id in existing_track_ids:
            if track_id in self.track_features and len(self.track_features[track_id]) > 0:
                # Use weighted average of recent features (more weight on recent/high-quality)
                if track_id in self.track_history and len(self.track_history[track_id]) > 0:
                    # Use history-based weighted average
                    recent_entries = self.track_history[track_id][-10:]  # Last 10
                    weights = []
                    features_list = []
                    for entry in recent_entries:
                        weight = entry.get('confidence', 0.5) * entry.get('quality', 0.5)
                        weights.append(weight)
                        features_list.append(entry['feature'])
                    weights = np.array(weights)
                    if weights.sum() > 0:
                        weights = weights / weights.sum()  # Normalize
                        avg_feature = np.average(features_list, axis=0, weights=weights)
                    else:
                        # Fallback to simple average
                        avg_feature = np.mean([e['feature'] for e in recent_entries], axis=0)
                else:
                    # Fallback: Use average of recent features
                    recent_features = self.track_features[track_id][-10:]  # Last 10 features
                    avg_feature = np.mean(recent_features, axis=0)
                track_avg_features[track_id] = avg_feature
        
        if len(track_avg_features) == 0:
            return {}
        
        # Filter out NaN features
        valid_feature_indices = []
        valid_features = []
        for i, feat in enumerate(new_features):
            if not np.isnan(feat).any():
                valid_feature_indices.append(i)
                valid_features.append(feat)
        
        if len(valid_features) == 0:
            return {}
        
        valid_features = np.array(valid_features)
        
        # Compute similarity matrix (cosine similarity)
        # new_features: (N, feature_dim)
        # track_features: (M, feature_dim) where M = len(track_avg_features)
        track_ids_list = list(track_avg_features.keys())
        track_features_array = np.array([track_avg_features[tid] for tid in track_ids_list])
        
        # Normalize features (already normalized, but ensure)
        valid_features_norm = valid_features / (np.linalg.norm(valid_features, axis=1, keepdims=True) + 1e-8)
        track_features_norm = track_features_array / (np.linalg.norm(track_features_array, axis=1, keepdims=True) + 1e-8)
        
        # Cosine similarity: (N_valid, M)
        similarity_matrix = np.dot(valid_features_norm, track_features_norm.T)
        
        # Add color similarity if color features are available
        if new_color_features is not None:
            color_similarity = self._compute_color_similarity(
                new_color_features, track_ids_list, valid_feature_indices
            )
            if color_similarity is not None:
                # Combine: 50% visual features, 30% color, 20% position (if available)
                if position_similarity is not None:
                    similarity_matrix = 0.5 * similarity_matrix + 0.3 * color_similarity + 0.2 * position_similarity
                else:
                    similarity_matrix = 0.7 * similarity_matrix + 0.3 * color_similarity
        elif position_similarity is not None:
            # Weighted combination: 70% feature, 30% position
            similarity_matrix = 0.7 * similarity_matrix + 0.3 * position_similarity
        
        # Match each detection to best track (Hungarian algorithm would be better, but greedy is faster)
        used_tracks = set()
        for valid_idx, original_idx in enumerate(valid_feature_indices):
            # Find best match
            best_similarity = -1
            best_track_idx = -1
            
            for track_idx, track_id in enumerate(track_ids_list):
                if track_id in used_tracks:
                    continue
                
                similarity = similarity_matrix[valid_idx, track_idx]
                
                # ENHANCED: Use adaptive threshold
                adaptive_thresh = self.similarity_threshold
                if self.enable_adaptive_thresholds:
                    # Get detection confidence if available (would need to pass this in)
                    adaptive_thresh = self._calculate_adaptive_threshold(
                        self.similarity_threshold,
                        confidence=0.5,  # Default, would be better with actual confidence
                        quality=0.5  # Default, would be better with actual quality
                    )
                
                # ENHANCED: Match against track history for better accuracy
                if track_id in self.track_features and len(self.track_features[track_id]) > 0:
                    history_similarity = self._match_against_track_history(
                        valid_features[valid_idx], track_id, use_weighted_average=True
                    )
                    # Use the better of the two similarities
                    similarity = max(similarity, history_similarity * 0.9)  # Slight penalty for history-only match
                
                if similarity > best_similarity and similarity >= adaptive_thresh:
                    best_similarity = similarity
                    best_track_idx = track_idx
            
            if best_track_idx >= 0:
                matched_track_id = track_ids_list[best_track_idx]
                matches[original_idx] = matched_track_id
                used_tracks.add(matched_track_id)
        
        return matches
    
    def _calculate_adaptive_threshold(self, 
                                     base_threshold: float,
                                     confidence: float = 0.5,
                                     distance: Optional[float] = None,
                                     occlusion_level: float = 0.0,
                                     quality: float = 0.5) -> float:
        """
        ENHANCED: Calculate adaptive similarity threshold based on scene conditions
        
        Args:
            base_threshold: Base similarity threshold (e.g., 0.55)
            confidence: Detection confidence (0-1, higher = stricter)
            distance: Optional distance from camera (pixels, closer = stricter)
            occlusion_level: Occlusion level (0-1, higher = more lenient)
            quality: Image quality score (0-1, higher = stricter)
        
        Returns:
            Adjusted threshold
        """
        if not self.enable_adaptive_thresholds:
            return base_threshold
        
        threshold = base_threshold
        
        # High confidence + clear view: stricter threshold
        if confidence > 0.7 and quality > 0.6:
            threshold += 0.10  # Stricter
        # Low confidence or occlusion: more lenient
        elif confidence < 0.4 or occlusion_level > 0.5:
            threshold -= 0.10  # More lenient
        
        # Distance-based adjustment
        if distance is not None:
            if distance < 100:  # Close players
                threshold += 0.05  # Stricter (more detail visible)
            elif distance > 300:  # Far players
                threshold -= 0.05  # More lenient (less detail)
        
        # Clamp to reasonable range
        return max(0.30, min(0.85, threshold))
    
    def _assess_feature_quality(self, 
                                feature: np.ndarray,
                                bbox_size: Tuple[int, int],
                                confidence: float = 0.5,
                                occlusion_level: float = 0.0) -> float:
        """
        ENHANCED: Assess quality of a feature for gallery updates
        
        Args:
            feature: Feature vector
            bbox_size: (width, height) of bounding box
            confidence: Detection confidence
            occlusion_level: Occlusion level (0-1)
        
        Returns:
            Quality score (0-1, higher = better)
        """
        quality = 0.5  # Base quality
        
        # Size-based quality (larger = better)
        bbox_area = bbox_size[0] * bbox_size[1]
        if bbox_area > 5000:  # Large player
            quality += 0.2
        elif bbox_area < 1000:  # Small player
            quality -= 0.2
        
        # Confidence-based quality
        quality += (confidence - 0.5) * 0.3
        
        # Occlusion penalty
        quality -= occlusion_level * 0.3
        
        # Feature validity check
        if np.isnan(feature).any() or np.linalg.norm(feature) < 1e-8:
            quality = 0.0
        
        return max(0.0, min(1.0, quality))
    
    def _negative_filter(self,
                        candidate_player_id: str,
                        candidate_team: Optional[str],
                        detection_team: Optional[str],
                        candidate_size: Optional[Tuple[float, float]],
                        detection_size: Tuple[float, float],
                        candidate_position: Optional[Tuple[float, float]],
                        detection_position: Tuple[float, float],
                        max_position_jump: float = 200.0) -> bool:
        """
        ENHANCED: Negative filtering - exclude impossible matches
        
        Args:
            candidate_player_id: Candidate player ID
            candidate_team: Candidate's team
            detection_team: Detection's team
            candidate_size: Candidate's typical size (width, height) or None
            detection_size: Detection's size (width, height)
            candidate_position: Candidate's last known position or None
            detection_position: Detection's position (x, y)
            max_position_jump: Maximum plausible position jump in pixels
        
        Returns:
            True if match should be excluded (impossible), False if plausible
        """
        if not self.enable_negative_filtering:
            return False  # Don't exclude
        
        # Team mismatch (unless substitution handling is enabled)
        if candidate_team is not None and detection_team is not None:
            if candidate_team != detection_team:
                return True  # Exclude: different teams
        
        # Size mismatch (very different sizes are unlikely)
        if candidate_size is not None:
            size_ratio_w = detection_size[0] / candidate_size[0] if candidate_size[0] > 0 else 1.0
            size_ratio_h = detection_size[1] / candidate_size[1] if candidate_size[1] > 0 else 1.0
            # If size differs by more than 2x, likely different player
            if size_ratio_w > 2.0 or size_ratio_w < 0.5 or size_ratio_h > 2.0 or size_ratio_h < 0.5:
                return True  # Exclude: size mismatch
        
        # Position jump check (if position verification enabled)
        if self.enable_position_verification and candidate_position is not None:
            dx = detection_position[0] - candidate_position[0]
            dy = detection_position[1] - candidate_position[1]
            distance = np.sqrt(dx*dx + dy*dy)
            if distance > max_position_jump:
                return True  # Exclude: impossible position jump
        
        return False  # Don't exclude
    
    def _verify_position_velocity(self,
                                  track_id: int,
                                  detection_position: Tuple[float, float],
                                  frame_num: int,
                                  max_jump_distance: float = 200.0) -> Tuple[bool, float]:
        """
        ENHANCED: Verify match using position and velocity consistency
        
        Args:
            track_id: Track ID to verify
            detection_position: Detection position (x, y)
            frame_num: Current frame number
            max_jump_distance: Maximum plausible jump distance in pixels
        
        Returns:
            (is_valid, confidence) tuple
        """
        if not self.enable_position_verification:
            return (True, 0.5)  # No verification, neutral confidence
        
        if track_id not in self.track_positions or len(self.track_positions[track_id]) == 0:
            return (True, 0.3)  # No history, low confidence but allow
        
        # Get last known position
        last_pos = self.track_positions[track_id][-1]
        last_x, last_y, last_frame = last_pos
        
        # Calculate expected position using velocity
        frames_since_last = frame_num - last_frame
        expected_x, expected_y = last_x, last_y
        
        if track_id in self.track_velocities and frames_since_last > 0:
            vx, vy = self.track_velocities[track_id]
            expected_x += vx * frames_since_last
            expected_y += vy * frames_since_last
        
        # Calculate distance from expected position
        dx = detection_position[0] - expected_x
        dy = detection_position[1] - expected_y
        distance = np.sqrt(dx*dx + dy*dy)
        
        # Check if within plausible range
        if distance <= max_jump_distance:
            # Calculate confidence based on distance (closer = higher confidence)
            confidence = max(0.3, 1.0 - (distance / max_jump_distance))
            return (True, confidence)
        else:
            # Position jump too large
            return (False, 0.0)
    
    def _match_against_track_history(self,
                                    feature: np.ndarray,
                                    track_id: int,
                                    use_weighted_average: bool = True) -> float:
        """
        ENHANCED: Match against track's recent history instead of just average
        
        Args:
            feature: Feature vector to match
            track_id: Track ID to match against
            use_weighted_average: If True, weight recent features more
        
        Returns:
            Best similarity score from track history
        """
        if track_id not in self.track_history or len(self.track_history[track_id]) == 0:
            return 0.0
        
        # Normalize input feature
        feature_norm = feature / (np.linalg.norm(feature) + 1e-8)
        
        best_similarity = 0.0
        
        for i, history_entry in enumerate(self.track_history[track_id]):
            hist_feature = history_entry['feature']
            hist_confidence = history_entry.get('confidence', 0.5)
            hist_quality = history_entry.get('quality', 0.5)
            
            # Normalize history feature
            hist_feature_norm = hist_feature / (np.linalg.norm(hist_feature) + 1e-8)
            
            # Compute similarity
            similarity = np.dot(feature_norm, hist_feature_norm)
            
            # Weight by recency and quality if enabled
            if use_weighted_average:
                # More recent = higher weight, higher quality = higher weight
                recency_weight = (i + 1) / len(self.track_history[track_id])  # Later entries = higher
                quality_weight = hist_quality * hist_confidence
                weighted_similarity = similarity * (0.5 + 0.3 * recency_weight + 0.2 * quality_weight)
                similarity = max(similarity, weighted_similarity)
            
            best_similarity = max(best_similarity, similarity)
        
        return best_similarity
    
    def _check_multi_frame_verification(self,
                                      track_id: int,
                                      player_id: str,
                                      similarity: float,
                                      frame_num: int,
                                      min_similarity: float = 0.5) -> Tuple[bool, float]:
        """
        ENHANCED: Check if match is verified across multiple frames
        
        Args:
            track_id: Track ID
            player_id: Matched player ID
            similarity: Current similarity score
            frame_num: Current frame number
            min_similarity: Minimum similarity for verification
        
        Returns:
            (is_verified, verification_confidence) tuple
        """
        if not self.enable_multi_frame_verification:
            return (True, similarity)  # No verification required
        
        # Add current match to history
        self.track_match_history[track_id].append((player_id, similarity, frame_num))
        
        # Keep only recent history (last 10 frames)
        if len(self.track_match_history[track_id]) > 10:
            self.track_match_history[track_id].pop(0)
        
        # Check if we have enough history
        if len(self.track_match_history[track_id]) < self.verification_frames_required:
            return (False, similarity * 0.7)  # Not enough history, lower confidence
        
        # Check recent matches
        recent_matches = self.track_match_history[track_id][-self.verification_frames_required:]
        
        # Count consistent matches
        consistent_count = sum(1 for pid, sim, _ in recent_matches 
                              if pid == player_id and sim >= min_similarity)
        
        if consistent_count >= self.verification_frames_required:
            # Verified: consistent matches across frames
            avg_similarity = sum(sim for _, sim, _ in recent_matches if sim >= min_similarity) / consistent_count
            return (True, min(1.0, avg_similarity * 1.1))  # Boost confidence for verified matches
        else:
            # Not verified: inconsistent matches
            return (False, similarity * 0.6)  # Lower confidence
    
    def _compute_color_similarity(self, new_color_features: Dict, track_ids_list: List[int], valid_indices: List[int]) -> Optional[np.ndarray]:
        """
        Compute color similarity between new detections and existing tracks
        
        Args:
            new_color_features: Dict with 'team_color' and 'ball_color' arrays
            track_ids_list: List of track IDs to compare against
            valid_indices: Valid detection indices
            
        Returns:
            similarity_matrix: (N_valid, M) similarity matrix, or None if no color data
        """
        if not new_color_features or len(track_ids_list) == 0 or len(valid_indices) == 0:
            return None
        
        N_valid = len(valid_indices)
        M = len(track_ids_list)
        similarity_matrix = np.zeros((N_valid, M))
        
        for valid_idx, orig_idx in enumerate(valid_indices):
            if orig_idx >= len(new_color_features.get('team_color', [])):
                continue
            
            new_team_color = new_color_features['team_color'][orig_idx]
            new_ball_color = new_color_features['ball_color'][orig_idx]
            
            for track_idx, track_id in enumerate(track_ids_list):
                if track_id not in self.track_color_features:
                    continue
                
                track_colors = self.track_color_features[track_id]
                similarity = 0.0
                weight = 0.0
                
                # Team color similarity (if both have team colors)
                if 'team_color' in track_colors and np.any(new_team_color > 0):
                    # Cosine similarity in BGR space
                    track_team = track_colors['team_color']
                    new_team_norm = new_team_color / (np.linalg.norm(new_team_color) + 1e-8)
                    track_team_norm = track_team / (np.linalg.norm(track_team) + 1e-8)
                    team_sim = np.dot(new_team_norm, track_team_norm)
                    similarity += 0.6 * team_sim  # Team color is more important
                    weight += 0.6
                
                # Ball color similarity (if both have ball colors)
                if 'ball_color' in track_colors and np.any(new_ball_color > 0):
                    track_ball = track_colors['ball_color']
                    new_ball_norm = new_ball_color / (np.linalg.norm(new_ball_color) + 1e-8)
                    track_ball_norm = track_ball / (np.linalg.norm(track_ball) + 1e-8)
                    ball_sim = np.dot(new_ball_norm, track_ball_norm)
                    similarity += 0.4 * ball_sim  # Ball color is less important
                    weight += 0.4
                
                if weight > 0:
                    similarity_matrix[valid_idx, track_idx] = similarity / weight
                else:
                    similarity_matrix[valid_idx, track_idx] = 0.0
        
        return similarity_matrix
    
    def clear_track(self, track_id: int):
        """Clear features for a track that's been deleted"""
        if track_id in self.track_features:
            del self.track_features[track_id]
        if track_id in self.track_color_features:
            del self.track_color_features[track_id]
    
    def clear_all_tracks(self):
        """Clear all stored track features"""
        self.track_features.clear()
    
    def get_track_count(self) -> int:
        """Get number of active tracks"""
        return len(self.track_features)
    
    # ============================================================
    # PLAYER GALLERY SUPPORT (Cross-Video Identification)
    # ============================================================
    
    def match_against_gallery(self, 
                             features: np.ndarray,
                             gallery,
                             dominant_colors: Optional[np.ndarray] = None,
                             teams: Optional[List[str]] = None,
                             jersey_numbers: Optional[List[str]] = None,
                             similarity_threshold: Optional[float] = None,
                             current_frame_num: Optional[int] = None,
                             track_ids: Optional[List[Optional[int]]] = None,
                             uniform_info_list: Optional[List[Dict]] = None,
                             exclude_players: Optional[set] = None,
                             include_only_players: Optional[set] = None) -> List[Tuple[Optional[str], Optional[str], float]]:
        """
        Match detected players against the player gallery
        
        Args:
            features: Feature array of shape (N, feature_dim) for N detections
            gallery: PlayerGallery instance
            dominant_colors: Optional array of dominant colors in HSV, shape (N, 3)
            teams: Optional list of team names for each detection
            jersey_numbers: Optional list of jersey numbers for each detection (for filtering/boosting)
            similarity_threshold: Optional custom threshold (uses gallery default if None)
            current_frame_num: Optional current frame number (for early-frame boost)
            track_ids: Optional list of track IDs for breadcrumb matching
            uniform_info_list: Optional list of uniform info dicts [{'jersey_color': 'gray', 'shorts_color': 'black', 'socks_color': 'white'}, ...]
            exclude_players: Optional set of player names to exclude from matching (e.g., anchor-protected players)
        
        Returns:
            List of (player_id, player_name, similarity_score) for each detection
            Returns (None, None, 0.0) for detections without matches
        """
        if gallery is None or len(features) == 0:
            return [(None, None, 0.0) for _ in range(len(features))]
        
        # Use default threshold if not provided
        if similarity_threshold is None:
            similarity_threshold = self.similarity_threshold
        
        matches = []
        
        # DIAGNOSTIC: Check features before matching
        current_frame = current_frame_num  # Use the parameter passed in
        if current_frame is not None and current_frame % 500 == 0:
            valid_count = sum(1 for f in features if f is not None and isinstance(f, np.ndarray) and f.size > 0 and not np.isnan(f).any())
            print(f"   🔍 DIAGNOSTIC: match_against_gallery (Frame {current_frame}) - {valid_count}/{len(features)} valid features")
            if valid_count == 0 and len(features) > 0:
                # All features are invalid - show why
                for i, f in enumerate(features[:3]):
                    if f is None:
                        print(f"      → Feature #{i}: None")
                    elif not isinstance(f, np.ndarray):
                        print(f"      → Feature #{i}: Not numpy array (type: {type(f)})")
                    elif f.size == 0:
                        print(f"      → Feature #{i}: Empty array")
                    elif np.isnan(f).any():
                        print(f"      → Feature #{i}: Contains NaN")
                    else:
                        print(f"      → Feature #{i}: Valid (shape: {f.shape})")
        
        for i, feature in enumerate(features):
            # Skip invalid features
            if feature is None:
                matches.append((None, None, 0.0))
                if current_frame is not None and current_frame % 500 == 0 and i < 3:
                    print(f"      → Detection #{i}: feature is None")
                continue
            
            # Check if feature is a valid numpy array
            if not isinstance(feature, np.ndarray):
                matches.append((None, None, 0.0))
                if current_frame is not None and current_frame % 500 == 0 and i < 3:
                    print(f"      → Detection #{i}: feature is not numpy array (type: {type(feature)})")
                continue
            
            # Check for NaN or invalid values
            if np.isnan(feature).any() or feature.size == 0:
                matches.append((None, None, 0.0))
                if current_frame is not None and current_frame % 500 == 0 and i < 3:
                    print(f"      → Detection #{i}: feature has NaN or is empty (size: {feature.size}, has_nan: {np.isnan(feature).any() if feature.size > 0 else True})")
                continue
            
            # Get optional parameters for this detection
            dominant_color = dominant_colors[i] if dominant_colors is not None and i < len(dominant_colors) else None
            team = teams[i] if teams is not None and i < len(teams) else None
            jersey_number = jersey_numbers[i] if jersey_numbers is not None and i < len(jersey_numbers) else None
            track_id = track_ids[i] if track_ids is not None and i < len(track_ids) else None
            uniform_info = uniform_info_list[i] if uniform_info_list is not None and i < len(uniform_info_list) else None
            
            # Match against gallery
            player_id, player_name, similarity = gallery.match_player(
                features=feature,
                similarity_threshold=similarity_threshold,
                dominant_color=dominant_color,
                team=team,
                jersey_number=jersey_number,  # Pass jersey number for filtering/boosting
                early_frame_range=(0, 1000),  # Boost players tagged in first 1000 frames
                early_frame_boost=0.10,  # 10% proportional boost for early-frame tags (only if similarity >= 0.5)
                current_frame_num=current_frame_num,  # Only boost if detection is also from early frames
                uniform_info=uniform_info,  # Pass uniform info for uniform-based matching boost
                exclude_players=exclude_players,  # Exclude anchor-protected players from matching (if provided)
                include_only_players=include_only_players  # Restrict to players in current video (if provided)
            )
            
            # DIAGNOSTIC: Log first few matches (occasionally)
            if current_frame is not None and current_frame % 500 == 0 and i < 3:
                if player_id is None:
                    # Check if similarity is actually 0.0 or if it's below threshold
                    if similarity == 0.0:
                        # This is suspicious - check if features are valid
                        if feature is not None and isinstance(feature, np.ndarray) and feature.size > 0:
                            feat_norm = np.linalg.norm(feature)
                            print(f"      → Detection #{i}: No match (similarity: {similarity:.4f}, threshold: {similarity_threshold:.2f}, feature norm: {feat_norm:.4f})")
                            # Check if gallery has features
                            if gallery is not None and len(gallery.players) > 0:
                                first_player = list(gallery.players.values())[0]
                                if first_player.features is not None:
                                    gal_feat = np.array(first_player.features)
                                    gal_norm = np.linalg.norm(gal_feat)
                                    # Try computing similarity manually for debugging
                                    feat_normed = feature / (feat_norm + 1e-8)
                                    gal_feat_normed = gal_feat / (gal_norm + 1e-8)
                                    manual_sim = np.dot(feat_normed, gal_feat_normed)
                                    print(f"         → Manual similarity test: {manual_sim:.4f} (detection norm: {feat_norm:.4f}, gallery norm: {gal_norm:.4f})")
                        else:
                            print(f"      → Detection #{i}: No match (similarity: {similarity:.4f}, threshold: {similarity_threshold:.2f}, feature is invalid)")
                    else:
                        print(f"      → Detection #{i}: No match (similarity: {similarity:.4f}, threshold: {similarity_threshold:.2f})")
                else:
                    print(f"      → Detection #{i}: Matched to {player_name} (similarity: {similarity:.4f})")
            
            # BREADCRUMBS: Apply multiple breadcrumb boosts
            total_breadcrumb_boost = 0.0
            
            # 1. LOCKED ROUTE BOOST (highest priority - from early-frame tags)
            if player_name and track_id is not None:
                try:
                    import shared_state
                    locked_route_boost = shared_state.get_locked_route_boost(player_name, track_id)
                    if locked_route_boost > 0:
                        total_breadcrumb_boost += locked_route_boost
                except:
                    pass  # Silently fail if shared_state not available
            
            # 2. User correction breadcrumb (from shared_state)
            if player_name and track_id is not None:
                try:
                    import shared_state
                    user_breadcrumb_boost = shared_state.get_track_breadcrumb_boost(player_name, track_id)
                    if user_breadcrumb_boost > 0:
                        total_breadcrumb_boost += user_breadcrumb_boost
                except:
                    pass  # Silently fail if shared_state not available
            
            # 3. Gallery track history breadcrumb (from player gallery)
            if player_id and track_id is not None and gallery is not None:
                try:
                    gallery_breadcrumb_boost = gallery.get_track_history_boost(player_id, track_id)
                    if gallery_breadcrumb_boost > 0:
                        total_breadcrumb_boost += gallery_breadcrumb_boost
                except:
                    pass  # Silently fail if gallery method not available
            
            # Apply combined boost (cap at 0.25 total to allow locked routes to have strong influence)
            if total_breadcrumb_boost > 0 and similarity > 0:
                total_breadcrumb_boost = min(0.25, total_breadcrumb_boost)  # Cap at 25% boost (locked routes can use up to 0.25)
                similarity = min(1.0, similarity + total_breadcrumb_boost)
            
            matches.append((player_id, player_name, similarity))
        
        return matches
    
    def add_track_to_gallery(self,
                            track_id: int,
                            player_name: str,
                            gallery,
                            jersey_number: Optional[str] = None,
                            team: Optional[str] = None,
                            reference_frame_info: Optional[Dict] = None) -> Optional[str]:
        """
        Add a tracked player to the gallery
        
        Args:
            track_id: Track ID to add to gallery
            player_name: Name of the player
            gallery: PlayerGallery instance
            jersey_number: Optional jersey number
            team: Optional team name
            reference_frame_info: Optional dict with {video_path, frame_num, bbox}
        
        Returns:
            player_id in the gallery, or None if track has no features
        """
        if track_id not in self.track_features or len(self.track_features[track_id]) == 0:
            print(f"⚠ Track #{track_id} has no features to add to gallery")
            return None
        
        # Compute average features for this track
        track_features_array = np.array(self.track_features[track_id])
        avg_features = np.mean(track_features_array, axis=0)
        # Normalize
        avg_features = avg_features / (np.linalg.norm(avg_features) + 1e-8)
        
        # Get dominant color if available
        dominant_color = None
        if track_id in self.track_color_features and 'team_color' in self.track_color_features[track_id]:
            # Convert BGR to HSV
            bgr_color = self.track_color_features[track_id]['team_color']
            bgr_pixel = np.uint8([[bgr_color]])
            hsv_pixel = cv2.cvtColor(bgr_pixel, cv2.COLOR_BGR2HSV)
            dominant_color = hsv_pixel[0, 0]
        
        # Add to gallery
        player_id = gallery.add_player(
            name=player_name,
            features=avg_features,
            jersey_number=jersey_number,
            team=team,
            reference_frame=reference_frame_info,
            dominant_color=dominant_color
        )
        
        return player_id
    
    def enable_soccer_specific_training(self, training_data_dir: Optional[str] = None):
        """
        Enable soccer-specific fine-tuning infrastructure.
        
        This prepares the Re-ID model for fine-tuning on soccer player data,
        which can improve feature extraction for players.
        
        Args:
            training_data_dir: Optional directory containing soccer training data
        """
        self.soccer_training_enabled = True
        self.training_data_dir = training_data_dir
        print("✓ Soccer-specific Re-ID training infrastructure enabled")
        print("  Use 'export_training_data()' to prepare data for fine-tuning")
    
    def export_training_data(
        self,
        output_dir: str,
        min_samples_per_player: int = 10,
        format: str = 'torchreid'
    ):
        """
        Export Re-ID training data for soccer-specific fine-tuning.
        
        Uses collected track features to create training dataset.
        Based on SoccerNet Re-ID task best practices.
        
        Args:
            output_dir: Directory to save training data
            min_samples_per_player: Minimum samples per player to include
            format: Export format ('torchreid', 'soccernet', 'custom')
        """
        try:
            from advanced_tracking_utils import SoccerReIDTrainer
        except ImportError:
            print("⚠ Advanced tracking utilities not available for training data export")
            return
        
        os.makedirs(output_dir, exist_ok=True)
        
        _ = SoccerReIDTrainer()  # Placeholder for future implementation
        
        # Note: This is a placeholder - actual implementation would need
        # access to frames and player IDs from the tracking system
        print(f"✓ Training data export infrastructure ready")
        print(f"  Output directory: {output_dir}")
        print(f"  Format: {format}")
        print(f"  Minimum samples per player: {min_samples_per_player}")
        print(f"  Note: Use 'add_training_sample()' to collect data during tracking")
        
        # Save metadata
        metadata = {
            'format': format,
            'min_samples_per_player': min_samples_per_player,
            'feature_dim': self.feature_dim,
            'model_type': 'osnet_x1_0' if self.use_torchreid else 'simple_cnn'
        }
        
        with open(os.path.join(output_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def update_gallery_player(self,
                             track_id: int,
                             player_id: str,
                             gallery,
                             reference_frame_info: Optional[Dict] = None):
        """
        Update an existing gallery player with new features from a track
        
        Args:
            track_id: Track ID with new features
            player_id: Player ID in the gallery to update
            gallery: PlayerGallery instance
            reference_frame_info: Optional dict with {video_path, frame_num, bbox}
        """
        if track_id not in self.track_features or len(self.track_features[track_id]) == 0:
            print(f"⚠ Track #{track_id} has no features to update gallery")
            return
        
        # Compute average features for this track
        track_features_array = np.array(self.track_features[track_id])
        avg_features = np.mean(track_features_array, axis=0)
        # Normalize
        avg_features = avg_features / (np.linalg.norm(avg_features) + 1e-8)
        
        # Get dominant color if available
        dominant_color = None
        if track_id in self.track_color_features and 'team_color' in self.track_color_features[track_id]:
            bgr_color = self.track_color_features[track_id]['team_color']
            bgr_pixel = np.uint8([[bgr_color]])
            hsv_pixel = cv2.cvtColor(bgr_pixel, cv2.COLOR_BGR2HSV)
            dominant_color = hsv_pixel[0, 0]
        
        # Update gallery
        gallery.update_player(
            player_id=player_id,
            features=avg_features,
            reference_frame=reference_frame_info,
            dominant_color=dominant_color
        )

