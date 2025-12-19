"""
Quick script to check GPU usage and device selection
"""
import torch
import sys

print("=" * 60)
print("GPU Detection & Usage Check")
print("=" * 60)

# Check CUDA availability
print(f"\n[OK] CUDA Available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"[OK] CUDA Device Count: {torch.cuda.device_count()}")
    
    for i in range(torch.cuda.device_count()):
        gpu_name = torch.cuda.get_device_name(i)
        props = torch.cuda.get_device_properties(i)
        memory_gb = props.total_memory / 1024**3
        
        print(f"\n  GPU {i}: {gpu_name}")
        print(f"    Memory: {memory_gb:.1f} GB")
        print(f"    Compute Capability: {props.major}.{props.minor}")
        
        # Check if it's NVIDIA
        is_nvidia = any(x in gpu_name.lower() for x in ['nvidia', 'geforce', 'rtx', 'gtx'])
        print(f"    Is NVIDIA: {is_nvidia}")
        
        # Try to get current memory usage
        try:
            torch.cuda.set_device(i)
            allocated = torch.cuda.memory_allocated(i) / 1024**3
            reserved = torch.cuda.memory_reserved(i) / 1024**3
            print(f"    Memory Allocated: {allocated:.2f} GB")
            print(f"    Memory Reserved: {reserved:.2f} GB")
        except Exception as e:
            print(f"    Could not check memory: {e}")
    
    # Check which device PyTorch would use by default
    print(f"\n[OK] Default CUDA Device: {torch.cuda.current_device()}")
    print(f"[OK] Default Device Name: {torch.cuda.get_device_name(torch.cuda.current_device())}")
    
    # Test tensor creation on GPU
    try:
        print("\n🧪 Testing GPU tensor creation...")
        test_tensor = torch.randn(1000, 1000).cuda()
        print(f"   [OK] Created tensor on GPU: {test_tensor.device}")
        print(f"   [OK] Tensor shape: {test_tensor.shape}")
        del test_tensor
        torch.cuda.empty_cache()
        print("   [OK] GPU test successful")
    except Exception as e:
        print(f"   [FAIL] GPU test failed: {e}")
else:
    print("\n⚠ No CUDA devices available - will use CPU (very slow)")

print("\n" + "=" * 60)
print("Recommendations:")
print("=" * 60)
if torch.cuda.is_available():
    nvidia_gpus = [i for i in range(torch.cuda.device_count()) 
                   if any(x in torch.cuda.get_device_name(i).lower() 
                         for x in ['nvidia', 'geforce', 'rtx', 'gtx'])]
    if nvidia_gpus:
        print(f"[OK] Found {len(nvidia_gpus)} NVIDIA GPU(s): {nvidia_gpus}")
        print("  -> Analysis should use GPU", nvidia_gpus[0])
    else:
        print("[WARN] No NVIDIA GPUs found - may be using Intel integrated GPU")
        print("  -> This will be much slower")
else:
    print("[WARN] CUDA not available - check PyTorch installation with CUDA support")

