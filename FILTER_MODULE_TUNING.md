# Re-ID Filter Module Tuning Guide

## Current Statistics Analysis

From your latest analysis:
- **Total checked**: 4997 detections
- **Passed**: 289 (5.8%)
- **Filtered**: 4708 (94.2%)

### Filter Breakdown:
- **Too blurry**: 4597 (92% of all detections!)
- **Low confidence**: 51
- **Low contrast**: 15
- **Invalid crop**: 45

## Issue Identified

The blur threshold is **too strict**. 92% of detections are being filtered for blur, which is likely too aggressive for soccer videos.

## Blur Threshold Explanation

**Laplacian Variance** measures image sharpness:
- **High values (200-500+)**: Very sharp, clear images
- **Medium values (50-200)**: Slightly blurry but usable
- **Low values (<50)**: Very blurry, likely unusable

**Previous default**: 100.0 (too strict - filters out usable detections)
**New default**: 50.0 (more lenient - allows slightly blurry but usable detections)

## Adjustments Made

1. **Reduced blur threshold** from 100.0 to 50.0
   - This will allow more detections to pass
   - Still filters out very blurry images (<50)
   - Better balance for soccer video analysis

## Expected Impact

With the new threshold (50.0):
- **More detections will pass** (estimated: 20-40% pass rate instead of 5.8%)
- **Better Re-ID matching** (more features to match against)
- **Improved tracking metrics** (more detections = better tracking)

## Further Tuning Options

If you want to adjust further, you can modify the blur threshold:

### Option 1: Make it configurable via GUI
Add a control in the Tracking Settings tab to adjust blur threshold.

### Option 2: Disable blur check entirely
Set `enable_blur_check=False` in ReIDTracker initialization.

### Option 3: Use adaptive threshold
Adjust blur threshold based on video quality or detection confidence.

## Recommended Settings

For soccer videos:
- **Blur threshold**: 50.0 (current new default) - good balance
- **Confidence threshold**: 0.25 (current) - reasonable
- **Contrast threshold**: 20.0 (current) - reasonable

If still too aggressive:
- Try blur threshold: 30.0 (very lenient)
- Or disable blur check: `enable_blur_check=False`

## Monitoring

After running with the new threshold, check the filter statistics:
- If pass rate is still <10%: Consider lowering blur threshold further
- If pass rate is >50%: May want to increase threshold slightly
- Target pass rate: 20-40% (filters bad detections but keeps usable ones)

