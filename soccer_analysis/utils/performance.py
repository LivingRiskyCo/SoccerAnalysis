"""
Performance Optimization Utilities
Hardware detection, optimal settings, and performance profiling
"""

import os
import sys
from typing import Dict, Any, Optional

# Try to import required libraries
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Try to import logger
try:
    from .logger_config import get_logger
except ImportError:
    try:
        from soccer_analysis.utils.logger_config import get_logger
    except ImportError:
        import logging
        get_logger = lambda name: logging.getLogger(name)

logger = get_logger("performance")


class PerformanceOptimizer:
    """Performance optimization utilities"""
    
    @staticmethod
    def detect_hardware() -> Dict[str, Any]:
        """
        Detect available hardware capabilities
        
        Returns:
            Dict with hardware information
        """
        hardware_info = {
            'gpu_available': False,
            'gpu_name': None,
            'gpu_memory_gb': 0.0,
            'cpu_count': 1,
            'ram_gb': 0.0,
            'platform': sys.platform
        }
        
        # GPU detection
        if TORCH_AVAILABLE:
            try:
                hardware_info['gpu_available'] = torch.cuda.is_available()
                if hardware_info['gpu_available']:
                    hardware_info['gpu_name'] = torch.cuda.get_device_name(0)
                    hardware_info['gpu_memory_gb'] = (
                        torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    )
                    hardware_info['gpu_count'] = torch.cuda.device_count()
            except Exception as e:
                logger.warning(f"GPU detection error: {e}")
        
        # CPU and RAM detection
        if PSUTIL_AVAILABLE:
            try:
                hardware_info['cpu_count'] = psutil.cpu_count(logical=True)
                hardware_info['cpu_physical'] = psutil.cpu_count(logical=False)
                hardware_info['ram_gb'] = psutil.virtual_memory().total / (1024**3)
                hardware_info['ram_available_gb'] = psutil.virtual_memory().available / (1024**3)
            except Exception as e:
                logger.warning(f"CPU/RAM detection error: {e}")
        else:
            # Fallback
            hardware_info['cpu_count'] = os.cpu_count() or 1
        
        return hardware_info
    
    @staticmethod
    def get_optimal_settings(hardware_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get optimal settings based on hardware
        
        Args:
            hardware_info: Hardware info dict (will detect if None)
            
        Returns:
            Dict with optimal settings
        """
        if hardware_info is None:
            hardware_info = PerformanceOptimizer.detect_hardware()
        
        settings = {
            'batch_size': 8,
            'yolo_resolution': 'full',
            'use_gpu': hardware_info.get('gpu_available', False),
            'num_threads': min(hardware_info.get('cpu_count', 4), 8),
            'cache_size_mb': 512,
            'process_every_nth': 1,
            'enable_batching': True
        }
        
        # Adjust based on GPU memory
        gpu_memory = hardware_info.get('gpu_memory_gb', 0)
        if gpu_memory > 0:
            if gpu_memory < 4:
                settings['batch_size'] = 4
                settings['yolo_resolution'] = '720p'
                settings['cache_size_mb'] = 256
            elif gpu_memory < 8:
                settings['batch_size'] = 8
                settings['yolo_resolution'] = '1080p'
                settings['cache_size_mb'] = 512
            else:
                settings['batch_size'] = 16
                settings['yolo_resolution'] = 'full'
                settings['cache_size_mb'] = 1024
        
        # Adjust based on RAM
        ram_gb = hardware_info.get('ram_gb', 0)
        if ram_gb > 0:
            # Use 10% of RAM for caching, but cap at 2GB
            cache_mb = min(int(ram_gb * 0.1 * 1024), 2048)
            settings['cache_size_mb'] = max(cache_mb, settings['cache_size_mb'])
        
        # Adjust threads based on CPU
        cpu_count = hardware_info.get('cpu_count', 4)
        if cpu_count >= 8:
            settings['num_threads'] = 8
        elif cpu_count >= 4:
            settings['num_threads'] = 4
        else:
            settings['num_threads'] = 2
        
        logger.info(f"Optimal settings: {settings}")
        return settings
    
    @staticmethod
    def apply_performance_mode(hardware_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Apply performance mode settings (optimized for speed)
        
        Returns:
            Settings dict optimized for speed
        """
        if hardware_info is None:
            hardware_info = PerformanceOptimizer.detect_hardware()
        
        settings = PerformanceOptimizer.get_optimal_settings(hardware_info)
        
        # Performance mode adjustments
        settings['process_every_nth'] = 2  # Process every 2nd frame
        settings['yolo_resolution'] = '720p'  # Lower resolution
        settings['batch_size'] = min(settings['batch_size'] * 2, 20)  # Larger batches
        
        return settings
    
    @staticmethod
    def apply_quality_mode(hardware_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Apply quality mode settings (optimized for accuracy)
        
        Returns:
            Settings dict optimized for quality
        """
        if hardware_info is None:
            hardware_info = PerformanceOptimizer.detect_hardware()
        
        settings = PerformanceOptimizer.get_optimal_settings(hardware_info)
        
        # Quality mode adjustments
        settings['process_every_nth'] = 1  # Process all frames
        settings['yolo_resolution'] = 'full'  # Full resolution
        settings['batch_size'] = max(settings['batch_size'] // 2, 4)  # Smaller batches for accuracy
        
        return settings


class FrameCache:
    """
    LRU cache for processed frames and detections
    """
    
    def __init__(self, max_size_mb: int = 512):
        """
        Initialize frame cache
        
        Args:
            max_size_mb: Maximum cache size in MB
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache = {}
        self.access_order = []
        self.current_size = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        if key in self.cache:
            # Update access order
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        return None
    
    def put(self, key: str, value: Any, size_bytes: int):
        """Put item in cache"""
        # Remove old items if needed
        while self.current_size + size_bytes > self.max_size_bytes and self.cache:
            if not self.access_order:
                break
            oldest_key = self.access_order.pop(0)
            if oldest_key in self.cache:
                old_size = self._estimate_size(self.cache[oldest_key])
                del self.cache[oldest_key]
                self.current_size -= old_size
        
        # Add new item
        self.cache[key] = value
        self.current_size += size_bytes
        self.access_order.append(key)
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate size of cached value in bytes"""
        try:
            import numpy as np
            if isinstance(value, np.ndarray):
                return value.nbytes
            elif isinstance(value, dict):
                total = 0
                for v in value.values():
                    total += self._estimate_size(v)
                return total
            elif isinstance(value, list):
                return sum(self._estimate_size(v) for v in value)
            else:
                return sys.getsizeof(value)
        except:
            return sys.getsizeof(value)
    
    def clear(self):
        """Clear cache"""
        self.cache.clear()
        self.access_order.clear()
        self.current_size = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'size_mb': self.current_size / (1024 * 1024),
            'max_size_mb': self.max_size_bytes / (1024 * 1024),
            'items': len(self.cache),
            'usage_percent': (self.current_size / self.max_size_bytes * 100) if self.max_size_bytes > 0 else 0
        }

