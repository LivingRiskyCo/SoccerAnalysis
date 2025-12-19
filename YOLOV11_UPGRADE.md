# YOLOv11 Upgrade Guide

## ✅ YOLOv11 is Now Available!

Your scripts have been updated to automatically use **YOLOv11** when available, with automatic fallback to YOLOv8.

## Benefits of YOLOv11

### Performance Improvements:
- **22% fewer parameters** than YOLOv8 (more efficient)
- **Higher accuracy** (better mAP)
- **Faster processing** (better GPU utilization)
- **New architecture modules**:
  - `C3k2` - Enhanced feature extraction
  - `C2PSA` - Better attention to critical regions

### Expected Impact:
- **Processing speed**: 10-20% faster
- **GPU efficiency**: Better utilization
- **Accuracy**: Slightly better player detection

## How It Works

The scripts automatically:
1. Try to load YOLOv11 first (`yolo11n.pt`)
2. If not available, fallback to YOLOv8 (`yolov8n.pt`)
3. No manual configuration needed!

## Current Status

✅ **YOLOv11 is available** in ultralytics 8.3.225  
✅ **Scripts updated** to use YOLOv11 automatically  
✅ **Automatic fallback** to YOLOv8 if needed

## Next Run

When you start your next analysis:
- Script will automatically download `yolo11n.pt` (if not already downloaded)
- You'll see: "Loading YOLOv11 model (faster, more efficient)..."
- Processing should be faster than before!

## Model Sizes

YOLOv11 models available:
- `yolo11n.pt` - Nano (smallest, fastest) ← **Currently using**
- `yolo11s.pt` - Small (more accurate)
- `yolo11m.pt` - Medium
- `yolo11l.pt` - Large
- `yolo11x.pt` - Extra Large (most accurate, slowest)

For your 4K video processing, `yolo11n.pt` is recommended for speed.

## To Use a Different Model

If you want to use a different YOLOv11 model (e.g., `yolo11s.pt` for better accuracy):

Edit `combined_analysis_optimized.py` and `combined_analysis.py`:
```python
model = YOLO('yolo11s.pt')  # Change from yolo11n.pt to yolo11s.pt
```

## Summary

✅ **Upgraded**: Scripts now use YOLOv11 automatically  
✅ **No action needed**: Works out of the box  
✅ **Better performance**: Faster processing with same accuracy  
✅ **Backward compatible**: Falls back to YOLOv8 if needed

Enjoy faster processing! 🚀

