# ReID Model Export Guide

## 📦 Where Are Exported Models Saved?

When you export a ReID model using the "Export ReID Model" button:

1. **Default Location**: Same directory as the original `.pt` file
   - Example: If you export `osnet_x1_0_msmt17.pt`, the ONNX version will be saved as `osnet_x1_0_msmt17.onnx` in the same folder

2. **Export Formats**:
   - **ONNX**: `model_name.onnx` (recommended, works on CPU and GPU)
   - **TensorRT**: `model_name.engine` (GPU only, fastest)
   - **OpenVINO**: `model_name_openvino_model/` (Intel hardware)
   - **TorchScript**: `model_name.torchscript.pt` (PyTorch optimized)

## 🔄 Automatic Detection & Usage

**No manual import needed!** The system automatically detects and uses exported models:

1. **Priority Order** (fastest first):
   - ONNX (`.onnx`)
   - TensorRT (`.engine`)
   - OpenVINO (`.xml` in `_openvino_model` folder)
   - TorchScript (`.torchscript.pt`)
   - PyTorch (`.pt`) - fallback

2. **Search Locations**:
   - Same directory as the original `.pt` file
   - Current working directory
   - `exported_models/` folder (if it exists)

3. **How It Works**:
   - When ReIDTracker initializes, it checks for exported models
   - If found, it automatically uses the optimized format
   - You'll see a message: `→ Found exported ONNX model: osnet_x1_0_msmt17.onnx`

## 📍 Finding Your Exported Models

### BoxMOT Default Location
BoxMOT typically saves models in:
```
~/.cache/torch/checkpoints/  (Linux/Mac)
C:\Users\<username>\.cache\torch\checkpoints\  (Windows)
```

### Custom Export Location
If you specify a custom output directory, models are saved there.

## 🚀 Performance Benefits

- **ONNX**: 2-3x faster than PyTorch on CPU
- **TensorRT**: 3-5x faster than PyTorch on GPU
- **OpenVINO**: Optimized for Intel CPUs/GPUs
- **TorchScript**: Slight improvement over PyTorch

## ✅ Verification

After exporting, you'll see:
```
✓ Model exported successfully!

📦 Export Location:
   C:\Users\...\osnet_x1_0_msmt17.onnx

💡 Automatic Usage:
   The exported ONNX model will be automatically
   detected and used by ReIDTracker when you run analysis.
   No manual import needed - BoxMOT auto-detects optimized formats!
```

When you run analysis, you'll see:
```
→ Found exported ONNX model: osnet_x1_0_msmt17.onnx
   Using optimized format for faster inference
```

## 🔧 Manual Override

If you want to use a specific exported model, you can:
1. Place it in the same directory as the original `.pt` file
2. Name it: `{original_name}.{extension}` (e.g., `osnet_x1_0_msmt17.onnx`)
3. The system will automatically detect and use it

## 📝 Notes

- Exported models are **read-only** - they're optimized for inference only
- You can delete the original `.pt` file after exporting (but keep it for re-exporting if needed)
- Different formats work on different hardware:
  - **ONNX**: Universal (CPU/GPU)
  - **TensorRT**: NVIDIA GPU only
  - **OpenVINO**: Intel hardware
  - **TorchScript**: Any PyTorch-compatible device


