# Streamlit Video Viewer Setup

## Quick Start

1. **Install Streamlit** (if not already installed):
   ```bash
   pip install streamlit
   ```

2. **Run the app locally**:
   ```bash
   streamlit run streamlit_video_viewer.py
   ```

3. **Deploy to Streamlit Cloud**:
   - Push this code to a GitHub repository
   - Go to https://share.streamlit.io
   - Connect your repository
   - Set main file to `streamlit_video_viewer.py`
   - Deploy!

## File Structure for Streamlit Cloud

```
your-repo/
├── streamlit_video_viewer.py
├── requirements_streamlit.txt
├── README_STREAMLIT.md
└── .streamlit/
    └── config.toml (optional)
```

## Important Notes

### Video File Size Limits
- Streamlit Cloud has file upload limits (~200MB)
- For larger videos, consider:
  1. **Host videos separately** (e.g., on Google Drive, Dropbox, or S3)
  2. **Use video URLs** instead of file uploads
  3. **Compress videos** before uploading

### Better Approach for Production

For production use with large videos, consider:

1. **Host videos on cloud storage** (S3, Google Cloud Storage, etc.)
2. **Modify the app** to accept video URLs instead of file uploads
3. **Use CORS-enabled storage** so the browser can load videos directly

### Mobile Optimization

The app is optimized for mobile devices:
- Responsive video player
- Touch-friendly controls
- Works on Android/iOS browsers

## Usage

1. Upload your video file (MP4)
2. Upload the corresponding overlay metadata JSON file
3. Toggle overlay options in the sidebar
4. View synchronized overlays on the video

## Troubleshooting

**Videos not loading?**
- Check file size (Streamlit Cloud limit: ~200MB)
- Try compressing the video
- Use external video hosting

**Overlays not showing?**
- Verify metadata JSON format matches expected structure
- Check browser console for JavaScript errors
- Ensure frame numbers in metadata match video frames

