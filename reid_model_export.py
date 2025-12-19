"""
ReID Model Export Utility
Exports ReID models (OSNet, etc.) to optimized formats: ONNX, TensorRT, OpenVINO, TorchScript
Based on BoxMOT's export functionality
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

try:
    from boxmot.utils import WEIGHTS
    BOXMOT_EXPORT_AVAILABLE = True
except (ImportError, AttributeError):
    BOXMOT_EXPORT_AVAILABLE = False
    WEIGHTS = None  # type: ignore
    print("⚠ BoxMOT export not available. Install with: pip install boxmot")


def export_model(weights_path: str, 
                 output_format: str = "onnx",
                 device: str = "cpu",
                 output_dir: Optional[str] = None,
                 dynamic: bool = False) -> Optional[Path]:
    """
    Export ReID model to specified format.
    
    Args:
        weights_path: Path to input model weights (.pt file)
        output_format: Export format: "onnx", "openvino", "engine" (TensorRT), "torchscript"
        device: Device to use: "cpu" or "0" (for GPU)
        output_dir: Optional output directory (default: same as input)
        dynamic: Enable dynamic input shapes (for TensorRT)
    
    Returns:
        Path to exported model or None if export failed
    """
    if not BOXMOT_EXPORT_AVAILABLE:
        print("❌ BoxMOT export functionality not available")
        print("   Install with: pip install boxmot")
        return None
    
    weights_path_obj = Path(weights_path)
    if not weights_path_obj.exists():
        print(f"❌ Model weights not found: {weights_path_obj}")
        return None
    
    # Determine output path
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = weights_path_obj.parent
    
    # Map output format to BoxMOT format
    format_map = {
        "onnx": "onnx",
        "openvino": "openvino",
        "engine": "engine",  # TensorRT
        "torchscript": "torchscript",
        "jit": "torchscript"
    }
    
    if output_format.lower() not in format_map:
        print(f"❌ Unsupported format: {output_format}")
        print(f"   Supported formats: {', '.join(format_map.keys())}")
        return None
    
    boxmot_format = format_map[output_format.lower()]
    
    try:
        print(f"🔄 Exporting {weights_path_obj.name} to {output_format.upper()}...")
        print(f"   Device: {device}")
        print(f"   Dynamic shapes: {dynamic}")
        
        # BoxMOT export function
        # Note: BoxMOT's export_reid_model may have different signature
        # We'll use the command-line interface approach
        import subprocess
        
        cmd = [
            sys.executable, "-m", "boxmot.appearance.reid_export",
            "--weights", str(weights_path_obj),
            "--include", boxmot_format,
            "--device", device
        ]
        
        if dynamic and output_format.lower() == "engine":
            cmd.append("--dynamic")
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(output_path))
        
        # BoxMOT typically saves exports in the same directory as the input file
        # Check both the output_path and the input file's directory
        search_dirs = [output_path, weights_path_obj.parent]
        
        if result.returncode == 0:
            # Find the exported file
            if output_format.lower() == "onnx":
                exported_file = output_path / weights_path_obj.stem.replace(".pt", ".onnx")
            elif output_format.lower() == "openvino":
                exported_file = output_path / weights_path_obj.stem.replace(".pt", "_openvino_model")
            elif output_format.lower() == "engine":
                exported_file = output_path / weights_path_obj.stem.replace(".pt", ".engine")
            elif output_format.lower() in ["torchscript", "jit"]:
                exported_file = output_path / weights_path_obj.stem.replace(".pt", ".torchscript.pt")
            else:
                exported_file = None
            
            # Search for exported file in multiple locations
            exported_file_found = None
            for search_dir in search_dirs:
                if output_format.lower() == "onnx":
                    check_path = search_dir / f"{weights_path_obj.stem}.onnx"
                elif output_format.lower() == "openvino":
                    # OpenVINO creates a directory
                    check_path = search_dir / f"{weights_path_obj.stem}_openvino_model"
                elif output_format.lower() == "engine":
                    check_path = search_dir / f"{weights_path_obj.stem}.engine"
                elif output_format.lower() in ["torchscript", "jit"]:
                    check_path = search_dir / f"{weights_path_obj.stem}.torchscript.pt"
                else:
                    check_path = None
                
                if check_path and check_path.exists():
                    exported_file_found = check_path
                    break
            
            if exported_file_found:
                print(f"✓ Model exported successfully!")
                print(f"\n📦 Export Location:")
                print(f"   {exported_file_found.absolute()}")
                print(f"\n💡 Automatic Usage:")
                print(f"   The exported {output_format.upper()} model will be automatically")
                print(f"   detected and used by ReIDTracker when you run analysis.")
                print(f"   No manual import needed - BoxMOT auto-detects optimized formats!")
                print(f"   Priority: {output_format.upper()} > PyTorch (.pt)")
                return exported_file_found
            else:
                # Check if export created files with different naming
                all_possible = []
                for search_dir in search_dirs:
                    if search_dir.exists():
                        all_possible.extend(list(search_dir.glob(f"*{weights_path_obj.stem}*")))
                        all_possible.extend(list(search_dir.glob(f"*.onnx")))
                        all_possible.extend(list(search_dir.glob(f"*.engine")))
                
                if all_possible:
                    print(f"⚠ Export completed but file not at expected location")
                    print(f"   Found files: {[f.name for f in all_possible[:5]]}")
                    print(f"   Check directories: {[str(d) for d in search_dirs]}")
                    return search_dirs[0] if search_dirs else output_path
                else:
                    print(f"⚠ Export completed but no files found")
                    print(f"   Check directories: {[str(d) for d in search_dirs]}")
                    print(f"   Check console output above for export details")
                    print(f"   BoxMOT may have saved to a different location")
                    return search_dirs[0] if search_dirs else output_path
        else:
            print(f"❌ Export failed:")
            print(result.stderr)
            return None
            
    except Exception as e:
        print(f"❌ Export error: {e}")
        import traceback
        traceback.print_exc()
        return None


def export_osnet_variants(output_dir: str = "exported_models", device: str = "cpu"):
    """
    Export common OSNet variants to ONNX for faster inference.
    
    Args:
        output_dir: Directory to save exported models
        device: Device to use for export
    """
    if not BOXMOT_EXPORT_AVAILABLE:
        print("❌ BoxMOT export functionality not available")
        return
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Common OSNet variants
    variants = [
        "osnet_x1_0",
        "osnet_ain_x1_0",
        "osnet_ibn_x1_0",
        "osnet_x0_75",
        "osnet_x0_5",
        "osnet_x0_25"
    ]
    
    print(f"🔄 Exporting OSNet variants to ONNX...")
    print(f"   Output directory: {output_path}")
    
    # Ensure WEIGHTS is available and is a Path
    if WEIGHTS is None:
        print("❌ BoxMOT WEIGHTS not available")
        return
    
    weights_path = Path(WEIGHTS)
    
    for variant in variants:
        # Try to find model in BoxMOT weights directory
        model_path = weights_path / f"{variant}_msmt17.pt"
        
        if not model_path.exists():
            print(f"⚠ Model not found: {model_path}")
            print(f"   BoxMOT will download it automatically on first use")
            continue
        
        print(f"\n📦 Exporting {variant}...")
        exported = export_model(
            weights_path=str(model_path),
            output_format="onnx",
            device=device,
            output_dir=str(output_path)
        )
        
        if exported:
            print(f"   ✓ {variant} exported successfully")
        else:
            print(f"   ❌ {variant} export failed")


def main():
    """Command-line interface for model export"""
    parser = argparse.ArgumentParser(description="Export ReID models to optimized formats")
    parser.add_argument("--weights", type=str, required=True, help="Path to model weights (.pt file)")
    parser.add_argument("--format", type=str, default="onnx", 
                       choices=["onnx", "openvino", "engine", "torchscript"],
                       help="Export format (default: onnx)")
    parser.add_argument("--device", type=str, default="cpu", 
                       help="Device for export: 'cpu' or '0' for GPU (default: cpu)")
    parser.add_argument("--output-dir", type=str, default=None,
                       help="Output directory (default: same as input)")
    parser.add_argument("--dynamic", action="store_true",
                       help="Enable dynamic input shapes (for TensorRT)")
    parser.add_argument("--export-all-osnet", action="store_true",
                       help="Export all OSNet variants to ONNX")
    
    args = parser.parse_args()
    
    if args.export_all_osnet:
        export_osnet_variants(output_dir=args.output_dir or "exported_models", device=args.device)
    else:
        if not args.weights:
            parser.error("--weights is required (or use --export-all-osnet)")
        
        export_model(
            weights_path=args.weights,
            output_format=args.format,
            device=args.device,
            output_dir=args.output_dir,
            dynamic=args.dynamic
        )


if __name__ == "__main__":
    main()

