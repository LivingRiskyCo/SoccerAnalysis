# GSI Smoothing (Gaussian Smoothed Interpolation) - Explanation

## What is GSI Smoothing?

**GSI (Gaussian Smoothed Interpolation)** is an advanced smoothing technique that uses **Gaussian Process Regression** to create smoother, more stable player tracks. It's based on research from BoxMOT and is particularly effective for sports tracking.

## How It Works

### 1. **Gaussian Process Regression (GPR)**
- Uses machine learning (scikit-learn) to learn the pattern of player movement
- Creates a smooth curve that fits through the player's position history
- Predicts the most likely position based on past movement patterns

### 2. **Two-Stage Process**

#### Stage 1: Linear Interpolation
- **Fills gaps** in tracking (when player is temporarily lost)
- If a player disappears for up to `gsi_interval` frames (default: 20), GSI interpolates their position
- Example: Player at frame 100, disappears, reappears at frame 115 → GSI fills frames 101-114

#### Stage 2: Gaussian Smoothing
- **Smooths jittery positions** using a Gaussian kernel
- Reduces small position jumps and noise
- Creates a more natural, fluid movement path

### 3. **Real-Time Application**
- GSI runs **during analysis** (not just post-processing)
- Uses the last 30 frames of position history
- Smooths both X and Y coordinates independently
- Updates player positions in real-time

## Parameters

### **GSI Interval** (default: 20 frames)
- **Maximum gap** to interpolate
- If a player disappears for ≤20 frames, GSI fills the gap
- If gap > 20 frames, interpolation is skipped (player likely left field)
- **Recommendation**: 20-30 frames for soccer (about 0.3-0.5 seconds at 60fps)

### **GSI Tau** (default: 10.0)
- **Smoothing strength** (time constant)
- **Lower values (5-8)**: Less smoothing, more responsive to actual movement
- **Higher values (12-20)**: More smoothing, smoother tracks but may lag behind fast movements
- **Recommendation**: 
  - **10.0**: Balanced (default)
  - **8.0**: For fast-paced action (less lag)
  - **15.0**: For very jittery cameras (more smoothing)

## When to Use GSI

### ✅ **Use GSI When:**
- Camera has **jitter or shake**
- Tracking is **jumpy or noisy**
- Players are **temporarily lost** (occlusion, camera pan)
- You want **smoother analytics** (speed, acceleration calculations)
- **Post-processing** for broadcast-quality smoothness

### ❌ **Don't Use GSI When:**
- Camera is **very stable** (may over-smooth)
- You need **exact pixel positions** (GSI slightly modifies positions)
- **Real-time accuracy** is critical (GSI adds small delay)
- Processing speed is a concern (adds ~5-10% overhead)

## Performance Impact

- **CPU Overhead**: ~5-10% (requires scikit-learn)
- **Memory**: Minimal (stores last 30 frames per track)
- **Accuracy**: Slightly modifies positions (typically <5px difference)

## Comparison to Other Smoothing

| Method | Smoothing | Gap Filling | Speed | Use Case |
|--------|-----------|-------------|-------|----------|
| **GSI** | High | Yes | Medium | Best overall smoothing |
| **Temporal Smoothing** | Medium | No | Fast | Simple position averaging |
| **EMA Smoothing** | Medium | No | Fast | Exponential moving average |
| **Kalman Filter** | High | Yes | Medium | Motion prediction + smoothing |

## Example

**Without GSI:**
```
Frame 100: (500, 300)
Frame 101: (502, 298)  ← jump
Frame 102: (501, 301)  ← jump
Frame 103: (503, 299)  ← jump
```

**With GSI (tau=10.0):**
```
Frame 100: (500, 300)
Frame 101: (501, 299.5)  ← smoothed
Frame 102: (501.5, 300)  ← smoothed
Frame 103: (502, 300.5)  ← smoothed
```

## Installation

GSI requires scikit-learn:
```bash
pip install scikit-learn
```

If not installed, GSI will be automatically disabled and you'll see:
```
⚠ GSI smoothing not available. Install sklearn: pip install scikit-learn
```

## GUI Controls

**Location**: Advanced Tab → Tracking Parameters

- **Enable GSI Smoothing**: Checkbox to enable/disable
- **GSI Interval**: Spinbox (5-50 frames, default: 20)
- **GSI Tau**: Spinbox (5.0-20.0, default: 10.0)

## Technical Details

GSI uses:
- **RBF (Radial Basis Function) kernel** for Gaussian Process Regression
- **Adaptive length scale** based on track history length
- **Real-time prediction** using last 30 frames
- **Independent smoothing** for X and Y coordinates

The algorithm:
1. Collects position history (last 30 frames)
2. Fits a Gaussian Process model to the history
3. Predicts smoothed position for current frame
4. Updates player position with smoothed value

## Tips

1. **Start with defaults** (interval=20, tau=10.0)
2. **Increase tau** if tracks are still jittery
3. **Decrease tau** if tracks lag behind fast movements
4. **Increase interval** if players are frequently lost (occlusion)
5. **Use with foot-based tracking** for best results (more stable anchor point)

