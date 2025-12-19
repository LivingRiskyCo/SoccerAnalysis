# Performance Optimization Guide

This module provides hardware detection, optimal settings, and performance utilities.

## Features

### Hardware Detection
- Automatic GPU detection (CUDA)
- CPU core count
- RAM detection
- GPU memory detection

### Optimal Settings
- Auto-configure settings based on hardware
- Performance mode (speed optimized)
- Quality mode (accuracy optimized)
- Balanced mode (hardware-specific)

### Frame Caching
- LRU cache for processed frames
- Configurable cache size
- Automatic cache management
- Cache statistics

## Usage

### Hardware Detection

```python
from soccer_analysis.utils.performance import PerformanceOptimizer

# Detect hardware
hardware = PerformanceOptimizer.detect_hardware()
print(f"GPU: {hardware['gpu_name']}")
print(f"GPU Memory: {hardware['gpu_memory_gb']} GB")
print(f"CPU: {hardware['cpu_count']} cores")
print(f"RAM: {hardware['ram_gb']} GB")
```

### Optimal Settings

```python
# Get optimal settings for your hardware
settings = PerformanceOptimizer.get_optimal_settings()

# Or use preset modes
perf_settings = PerformanceOptimizer.apply_performance_mode()  # Speed
quality_settings = PerformanceOptimizer.apply_quality_mode()  # Accuracy
```

### Frame Caching

```python
from soccer_analysis.utils.performance import FrameCache

# Create cache (512 MB)
cache = FrameCache(max_size_mb=512)

# Cache a frame
cache.put("frame_100", frame_array, frame_size_bytes)

# Retrieve from cache
cached_frame = cache.get("frame_100")

# Get statistics
stats = cache.get_stats()
print(f"Cache usage: {stats['usage_percent']:.1f}%")
```

## Performance Modes

### Performance Mode
- Process every 2nd frame (2x speedup)
- Lower YOLO resolution (720p)
- Larger batch sizes
- **Expected**: 2-3x faster processing

### Quality Mode
- Process all frames
- Full YOLO resolution
- Smaller batch sizes for accuracy
- **Expected**: Best quality, slower processing

### Balanced Mode
- Auto-configured based on hardware
- Optimal balance for your system
- **Expected**: Good quality with reasonable speed

## Integration

The performance optimizer is integrated into:
- **Detector**: GPU acceleration and batching
- **VideoProcessor**: Frame caching and prefetching
- **GUI**: Hardware detection and mode selection

## Requirements

Optional but recommended:
```bash
pip install psutil  # For CPU/RAM detection
# PyTorch with CUDA for GPU detection
```

