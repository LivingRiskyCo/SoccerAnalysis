# Dewarping / Fisheye Correction Note

## Important: Modern Phones Auto-Correct Fisheye

### S24 Ultra and Similar Phones
- **Ultra-wide cameras automatically correct fisheye distortion** in software
- The recorded video is already corrected
- **Applying dewarping will OVER-correct** and create distortion

### Recommendation
- **Keep dewarping DISABLED** for videos from modern phones
- Only use dewarping if:
  - You have RAW/uncorrected video
  - You're using a camera that doesn't auto-correct
  - You intentionally want to adjust the field of view

### How to Fix Already Processed Video
1. Use your **original video file** (not the processed one)
2. Re-run analysis with **dewarping disabled** (unchecked)
3. The output will be correct

### GUI Default
- Dewarping is now **disabled by default** in the GUI
- You can enable it if needed, but leave it off for phone videos

---

**TL;DR**: Modern phones fix fisheye automatically. Don't dewarp phone videos. Use original video, re-process with dewarping OFF.

