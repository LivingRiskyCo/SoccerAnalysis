import React from 'react'
import VideoPlayer from './VideoPlayer'
import './MultiCameraViewer.css'

const MultiCameraViewer = () => {
  return (
    <div className="multi-camera-viewer">
      <div className="viewer-header">
        <h2>📺 Live Feed</h2>
      </div>

      <div className="live-feed-info" style={{ 
        padding: '10px', 
        backgroundColor: '#1a1a1a', 
        borderRadius: '4px',
        marginBottom: '10px'
      }}>
        <p style={{ margin: 0, color: '#aaa' }}>
          This shows the live feed from the desktop application's Live Feed tab.
          Make sure the Live Feed is running in the desktop GUI.
        </p>
      </div>

      {/* Video display area */}
      <div className="video-display" style={{ 
        width: '100%', 
        height: 'calc(100vh - 200px)',
        minHeight: '500px'
      }}>
        <VideoPlayer
          videoPath={null}
          overlayData={null}
          currentFrame={0}
          onFrameChange={() => {}}
          onTrackClick={() => {}}
          showOverlays={false}
        />
      </div>
    </div>
  )
}

export default MultiCameraViewer

