import React, { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { API_BASE } from '../utils/apiConfig'
import './VideoPlayer.css'

const VideoPlayer = ({
  videoPath,
  overlayData,
  currentFrame,
  onFrameChange,
  onTrackClick,
  taggingMode = false,
  showOverlays = true,
  overlaySettings = {},
  playbackSpeed = 1.0
}) => {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [videoMetadata, setVideoMetadata] = useState(null)
  const [currentFrameNum, setCurrentFrameNum] = useState(0)
  const [frameTime, setFrameTime] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [tracks, setTracks] = useState({})
  const [hoveredTrack, setHoveredTrack] = useState(null)
  const [streamKey, setStreamKey] = useState(0) // For live stream refresh
  const [streamError, setStreamError] = useState(false) // For live stream error state
  const animationFrameRef = useRef(null)
  const containerRef = useRef(null)
  const trackHistoryRef = useRef({}) // Store full track history: {track_id: [{frame, x, y, bbox, ...}, ...]}
  const playerGalleryCacheRef = useRef({}) // Cache player data: {player_name: {jersey_number, ...}}
  const refreshIntervalRef = useRef(null) // For live stream auto-refresh

  // Load player gallery data for jersey number lookup
  useEffect(() => {
    loadPlayerGallery()
  }, [])

  const loadPlayerGallery = async () => {
    try {
      const res = await axios.get(`${API_BASE}/players`)
      // The API returns {players: [...], count: X}
      let players = []
      if (res.data?.players && Array.isArray(res.data.players)) {
        players = res.data.players
      } else if (Array.isArray(res.data)) {
        players = res.data
      } else if (res.data && typeof res.data === 'object') {
        // Try to find an array in the object
        const arrayValue = Object.values(res.data).find(v => Array.isArray(v))
        if (arrayValue) {
          players = arrayValue
        }
      }
      
      const cache = {}
      if (Array.isArray(players)) {
        players.forEach(player => {
          if (player && player.name) {
            const nameKey = player.name.toLowerCase().trim()
            cache[nameKey] = {
              jersey_number: player.jersey_number,
              team: player.team,
              position: player.position
            }
          }
        })
      }
      playerGalleryCacheRef.current = cache
    } catch (err) {
      console.warn('Could not load player gallery for jersey numbers:', err)
    }
  }

  // Load video metadata when videoPath changes
  useEffect(() => {
    if (videoPath) {
      loadVideoMetadata()
      // Reset error state when video path changes
      setError(null)
    } else {
      // Live stream mode
      setIsPlaying(true)
    }
  }, [videoPath])

  // Update current frame when prop changes
  useEffect(() => {
    if (currentFrame !== undefined && currentFrame !== currentFrameNum) {
      setCurrentFrameNum(currentFrame)
      if (videoRef.current && videoMetadata) {
        const time = currentFrame / videoMetadata.fps
        videoRef.current.currentTime = time
      }
    }
  }, [currentFrame, videoMetadata])

  // Load video metadata
  const loadVideoMetadata = async () => {
    if (!videoPath) return

    setLoading(true)
    setError(null)
    try {
      const res = await axios.post(`${API_BASE}/videos/load`, {
        video_path: videoPath
      })
      setVideoMetadata(res.data)
      setCurrentFrameNum(0)
      
      // Verify video can be loaded by checking if video element can load it
      if (videoRef.current) {
        const video = videoRef.current
        const videoUrl = `/video/${encodeURIComponent(videoPath.replace(/\\/g, '/'))}`
        
        // Set up error handler before setting src
        const handleError = () => {
          const error = video.error
          if (error) {
            let errorMsg = 'Video playback error: '
            switch (error.code) {
              case error.MEDIA_ERR_ABORTED:
                errorMsg += 'Video loading aborted'
                break
              case error.MEDIA_ERR_NETWORK:
                errorMsg += 'Network error while loading video'
                break
              case error.MEDIA_ERR_DECODE:
                errorMsg += 'Video decoding error. The video format or codec may not be supported by your browser. Try converting to MP4 (H.264 codec).'
                break
              case error.MEDIA_ERR_SRC_NOT_SUPPORTED:
                errorMsg += 'Video format not supported. The browser cannot play this video format. Try converting to MP4 (H.264 codec).'
                break
              default:
                errorMsg += error.message || 'Unknown error'
            }
            setError(errorMsg)
            console.error('Video error details:', {
              code: error.code,
              message: error.message,
              videoUrl: videoUrl
            })
          }
        }
        
        video.addEventListener('error', handleError, { once: true })
        video.src = videoUrl
        video.load() // Force reload to trigger error if format is unsupported
      }
    } catch (err) {
      setError('Failed to load video metadata: ' + (err.response?.data?.error || err.message))
      console.error('Error loading video:', err)
    } finally {
      setLoading(false)
    }
  }

  // Load overlay data and extract tracks + build track history for trails
  useEffect(() => {
    if (overlayData) {
      const tracksMap = {}
      const trackHistory = {}
      
      // Process overlay data to build track history
      // Handle both formats: {frames: {frame: {tracks: [...]}}} and {frame: [...]} or {frame: {track_id: {...}}}
      const processFrame = (frameNum, frameData) => {
        let items = []
        
        if (Array.isArray(frameData)) {
          // Format: {frame: [...]}
          items = frameData
        } else if (frameData.tracks) {
          // Format: {frame: {tracks: [...]}}
          items = Array.isArray(frameData.tracks) ? frameData.tracks : Object.values(frameData.tracks)
        } else if (typeof frameData === 'object') {
          // Format: {frame: {track_id: {...}}} - extract values
          items = Object.values(frameData)
        } else {
          // Single item
          items = [frameData]
        }
        
        items.forEach(track => {
          if (!track || typeof track !== 'object' || !track.bbox || !Array.isArray(track.bbox) || track.bbox.length < 4) return
          
          const trackId = track.track_id || track.id || 'unknown'
          const [x1, y1, x2, y2] = track.bbox
          const centerX = (x1 + x2) / 2
          const centerY = (y1 + y2) / 2
          
          // Build track history
          if (!trackHistory[trackId]) {
            trackHistory[trackId] = []
          }
          trackHistory[trackId].push({
            frame: frameNum,
            x: centerX,
            y: centerY,
            bbox: track.bbox,
            color: track.color || '#00FF00',
            ...track
          })
          
          // Store current frame tracks (will be updated separately)
          // Don't filter here - we'll get current frame tracks from overlay data in renderOverlays
        })
      }
      
      if (overlayData.frames) {
        // Structured format: {frames: {frame: {tracks: [...]}}}
        Object.entries(overlayData.frames).forEach(([frame, frameData]) => {
          const frameNum = parseInt(frame)
          if (!isNaN(frameNum)) {
            processFrame(frameNum, frameData)
          }
        })
      } else {
        // Direct frame format: {frame: [...]}
        Object.entries(overlayData).forEach(([frame, frameData]) => {
          const frameNum = parseInt(frame)
          if (!isNaN(frameNum)) {
            processFrame(frameNum, frameData)
          }
        })
      }
      
      // Sort track history by frame
      Object.keys(trackHistory).forEach(id => {
        trackHistory[id].sort((a, b) => a.frame - b.frame)
      })
      
      trackHistoryRef.current = trackHistory
      
      // Get current frame tracks
      const currentFrameTracks = {}
      const getFrameItems = (frameData) => {
        if (Array.isArray(frameData)) {
          return frameData
        } else if (frameData.tracks) {
          return Array.isArray(frameData.tracks) ? frameData.tracks : Object.values(frameData.tracks)
        } else if (typeof frameData === 'object') {
          // Format: {track_id: {...}} - extract values
          return Object.values(frameData)
        } else {
          return [frameData]
        }
      }
      
      if (overlayData.frames) {
        // Try both string and numeric keys
        const frameKey = String(currentFrameNum)
        const frameData = overlayData.frames[frameKey] || overlayData.frames[currentFrameNum]
        if (frameData) {
          const items = getFrameItems(frameData)
          items.forEach(track => {
            if (track && track.bbox && Array.isArray(track.bbox) && track.bbox.length >= 4) {
              const trackId = String(track.track_id || track.id || 'unknown')
              currentFrameTracks[trackId] = track
            }
          })
        }
      } else {
        // Direct frame format: {frame: {...}} or {frame: {track_id: {...}}}
        const frameKey = String(currentFrameNum)
        const frameData = overlayData[frameKey] || overlayData[currentFrameNum]
        if (frameData) {
          const items = getFrameItems(frameData)
          items.forEach(track => {
            if (track && track.bbox && Array.isArray(track.bbox) && track.bbox.length >= 4) {
              const trackId = String(track.track_id || track.id || 'unknown')
              currentFrameTracks[trackId] = track
            }
          })
        }
      }
      
      console.log('Processed overlay data:', {
        totalFrames: overlayData.frames ? Object.keys(overlayData.frames).length : Object.keys(overlayData).length,
        currentFrame: currentFrameNum,
        currentFrameTracks: Object.keys(currentFrameTracks).length,
        trackHistoryCount: Object.keys(trackHistory).length
      })
      
      setTracks(currentFrameTracks)
    } else {
      setTracks({})
      trackHistoryRef.current = {}
    }
  }, [overlayData, currentFrameNum])

  // Update playback speed
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackSpeed
    }
  }, [playbackSpeed])

  // Pre-buffer video when metadata is loaded
  useEffect(() => {
    if (videoRef.current && videoMetadata && !isPlaying) {
      const video = videoRef.current
      
      // Trigger initial buffering by loading the video
      // The preload="auto" attribute should handle this, but we can help it along
      if (video.readyState < 2) {
        // Force load by seeking slightly forward then back
        const originalTime = video.currentTime || 0
        if (video.duration > 1) {
          video.currentTime = 0.1
          setTimeout(() => {
            if (video && !isPlaying) {
              video.currentTime = originalTime
            }
          }, 200)
        }
      }
    }
  }, [videoMetadata, isPlaying])

  // Handle video time update
  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current && videoMetadata) {
      const time = videoRef.current.currentTime
      const frame = Math.floor(time * videoMetadata.fps)
      setCurrentFrameNum(frame)
      setFrameTime(time)
      if (onFrameChange) {
        onFrameChange(frame)
      }
    }
  }, [videoMetadata, onFrameChange])

  // Handle video ended
  const handleVideoEnded = () => {
    setIsPlaying(false)
    setIsPaused(true)
  }

  // Toggle play/pause
  const togglePlayPause = () => {
    if (!videoRef.current) return

    if (isPaused || !isPlaying) {
      videoRef.current.play()
      setIsPlaying(true)
      setIsPaused(false)
    } else {
      videoRef.current.pause()
      setIsPaused(true)
      setIsPlaying(false)
    }
  }

  // Seek to frame
  const seekToFrame = (frame) => {
    if (!videoRef.current || !videoMetadata) return
    const time = frame / videoMetadata.fps
    videoRef.current.currentTime = time
    setCurrentFrameNum(frame)
    if (onFrameChange) {
      onFrameChange(frame)
    }
  }

  // Frame navigation
  const goToPreviousFrame = () => {
    if (currentFrameNum > 0) {
      seekToFrame(currentFrameNum - 1)
    }
  }

  const goToNextFrame = () => {
    if (videoMetadata && currentFrameNum < videoMetadata.frame_count - 1) {
      seekToFrame(currentFrameNum + 1)
    }
  }

  // Handle canvas click for track selection
  const handleCanvasClick = (e) => {
    if (!taggingMode || !canvasRef.current) return

    const rect = canvasRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    // Find clicked track
    const clickedTrack = Object.values(tracks).find(track => {
      if (!track.bbox) return false
      const [x1, y1, x2, y2] = track.bbox
      return x >= x1 && x <= x2 && y >= y1 && y <= y2
    })

    if (clickedTrack && onTrackClick) {
      // Pass both track_id and full track data
      onTrackClick(clickedTrack.track_id || clickedTrack.id, clickedTrack)
    }
  }

  // Render analytics overlays
  const renderAnalytics = useCallback((ctx, canvas, video, frameNum, frameTracks, overlaySettings) => {
    if (!overlaySettings?.showAnalytics || !overlaySettings?.analyticsPreferences) {
      return
    }

    const preferences = overlaySettings.analyticsPreferences
    const position = overlaySettings.analyticsPosition || 'with_player'
    const fontScale = (overlaySettings.analyticsFontScale || 1.5) * 1.2 // Increase default font size
    const fontThickness = overlaySettings.analyticsFontThickness || 2
    const bannerHeight = overlaySettings.bannerHeight || 150
    const barWidth = overlaySettings.barWidth || 250
    const panelWidth = overlaySettings.panelWidth || 300
    const panelHeight = overlaySettings.panelHeight || 200
    const hasAnyAnalytics = Object.values(preferences).some(v => v)
    
    if (!hasAnyAnalytics) {
      return
    }

    const canvasWidth = canvas.width
    const canvasHeight = canvas.height

    // Extract analytics data from tracks
    const playerAnalytics = []
    if (frameTracks && typeof frameTracks === 'object') {
      const tracksArray = Array.isArray(frameTracks) ? frameTracks : Object.values(frameTracks)
      
      tracksArray.forEach((track) => {
        if (!track) return
        const trackId = track.track_id || track.id || 'unknown'
        const playerName = track.player_name || `Player ${trackId}`
        const [x1, y1, x2, y2] = track.bbox || [0, 0, 0, 0]
        const centerX = (x1 + x2) / 2
        const centerY = (y1 + y2) / 2

        // Build analytics text from preferences
        const analyticsLines = []
        if (preferences.current_speed && track.speed !== undefined) {
          analyticsLines.push(`Speed: ${track.speed.toFixed(1)} m/s`)
        }
        if (preferences.average_speed && track.avg_speed !== undefined) {
          analyticsLines.push(`Avg: ${track.avg_speed.toFixed(1)} m/s`)
        }
        if (preferences.max_speed && track.max_speed !== undefined) {
          analyticsLines.push(`Max: ${track.max_speed.toFixed(1)} m/s`)
        }
        if (preferences.acceleration && track.acceleration !== undefined) {
          analyticsLines.push(`Accel: ${track.acceleration.toFixed(2)} m/s²`)
        }
        if (preferences.distance_to_ball && track.distance_to_ball !== undefined) {
          analyticsLines.push(`Ball: ${track.distance_to_ball.toFixed(0)} px`)
        }
        if (preferences.distance_traveled && track.distance_traveled !== undefined) {
          analyticsLines.push(`Dist: ${track.distance_traveled.toFixed(1)} m`)
        }
        if (preferences.field_zone && track.field_zone) {
          analyticsLines.push(`Zone: ${track.field_zone}`)
        }
        if (preferences.possession_time && track.possession_time !== undefined) {
          analyticsLines.push(`Poss: ${track.possession_time.toFixed(1)}s`)
        }

        // If no analytics data but preferences are enabled, show placeholder
        if (analyticsLines.length === 0 && Object.values(preferences).some(v => v)) {
          // Show at least track ID and position if analytics are requested but data isn't available
          analyticsLines.push(`Track: ${trackId}`)
          if (track.bbox && track.bbox.length >= 4) {
            analyticsLines.push(`Pos: (${Math.round(centerX)}, ${Math.round(centerY)})`)
          }
        }

        if (analyticsLines.length > 0) {
          playerAnalytics.push({
            trackId,
            playerName,
            centerX,
            centerY,
            lines: analyticsLines,
            color: track.color || '#00FF00'
          })
        }
      })
    }

    if (playerAnalytics.length === 0) return

    const fontSize = 14 * fontScale // Increased base font size
    const lineHeight = fontSize + 6
    ctx.font = `bold ${fontSize}px Arial`
    ctx.lineWidth = fontThickness

    if (position === 'with_player') {
      // Render next to each player
      playerAnalytics.forEach(({ centerX, centerY, lines, color }) => {
        const textX = centerX + 40
        const textY = centerY + 20
        const maxWidth = Math.max(...lines.map(l => ctx.measureText(l).width)) + 8
        const totalHeight = lines.length * lineHeight + 4

        // Draw background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
        ctx.fillRect(textX, textY - fontSize, maxWidth, totalHeight)

        // Draw text
        ctx.fillStyle = '#FFFFFF'
        lines.forEach((line, idx) => {
          ctx.fillText(line, textX + 4, textY + idx * lineHeight)
        })
      })
    } else {
      // Render in panel/banner/bar - use settings from overlaySettings
      let posX = 10, posY = 10
      let sizeX, sizeY

      if (position === 'top_banner') {
        posX = 0
        posY = 0 // Start at top
        sizeX = canvasWidth
        sizeY = bannerHeight
      } else if (position === 'bottom_banner') {
        posX = 0
        posY = canvasHeight - bannerHeight // Position from bottom
        sizeX = canvasWidth
        sizeY = bannerHeight
      } else if (position === 'left_bar') {
        posX = 0
        posY = 0
        sizeX = barWidth
        sizeY = canvasHeight
      } else if (position === 'right_bar') {
        posX = canvasWidth - barWidth
        posY = 0
        sizeX = barWidth
        sizeY = canvasHeight
      } else if (position === 'top_left') {
        posX = 10
        posY = 10
        sizeX = panelWidth
        sizeY = panelHeight
      } else if (position === 'top_right') {
        posX = canvasWidth - panelWidth - 10
        posY = 10
        sizeX = panelWidth
        sizeY = panelHeight
      } else if (position === 'bottom_left') {
        posX = 10
        posY = canvasHeight - panelHeight - 10
        sizeX = panelWidth
        sizeY = panelHeight
      } else if (position === 'bottom_right') {
        posX = canvasWidth - panelWidth - 10
        posY = canvasHeight - panelHeight - 10
        sizeX = panelWidth
        sizeY = panelHeight
      }

      // Draw background
      ctx.fillStyle = 'rgba(0, 0, 0, 0.85)' // Darker background for better visibility
      ctx.fillRect(posX, posY, sizeX, sizeY)

      // Draw border
      ctx.strokeStyle = '#FFFFFF'
      ctx.lineWidth = 2
      ctx.strokeRect(posX, posY, sizeX, sizeY)

      // Draw analytics
      ctx.fillStyle = '#FFFFFF'
      // Adjust text position to be higher in banner (not too low)
      let textY = posY + fontSize + 15 // Start text higher from top
      const maxPlayers = position.includes('banner') ? 8 : 10

      if (position.includes('banner')) {
        // Horizontal layout for banners
        const numPlayers = Math.min(playerAnalytics.length, maxPlayers)
        const columnWidth = sizeX / numPlayers
        playerAnalytics.slice(0, numPlayers).forEach((player, idx) => {
          const columnX = posX + idx * columnWidth + 10
          let columnY = posY + fontSize + 10

          // Player name
          ctx.fillStyle = player.color
          ctx.fillText(player.playerName, columnX, columnY)
          columnY += lineHeight

          // Analytics lines
          ctx.fillStyle = '#FFFFFF'
          player.lines.slice(0, 3).forEach((line, lineIdx) => {
            if (columnY + lineHeight <= posY + sizeY - 10) {
              ctx.fillText(line, columnX, columnY)
              columnY += lineHeight
            }
          })
        })
      } else {
        // Vertical layout for panels/bars
        let currentTextY = textY // Use separate variable to avoid conflicts
        playerAnalytics.slice(0, maxPlayers).forEach((player) => {
          if (currentTextY + (player.lines.length + 1) * lineHeight > posY + sizeY - 10) return

          // Player name
          ctx.fillStyle = player.color
          ctx.fillText(player.playerName + ':', posX + 10, currentTextY)
          currentTextY += lineHeight

          // Analytics lines
          ctx.fillStyle = '#FFFFFF'
          player.lines.slice(0, 3).forEach((line) => {
            if (currentTextY + lineHeight <= posY + sizeY - 10) {
              ctx.fillText(line, posX + 20, currentTextY)
              currentTextY += lineHeight
            }
          })
          currentTextY += 5 // Spacing between players
        })
      }
    }
  }, [])

  // Render heatmap
  const renderHeatmap = useCallback((ctx, canvas, frameNum, overlaySettings, frameTracks) => {
    if (!overlaySettings?.showHeatmap) return

    const heatmapType = overlaySettings.heatmapType || 'position'
    const opacity = overlaySettings.heatmapOpacity || 0.5

    // Simplified heatmap rendering - would need proper heatmap data
    if (frameTracks && typeof frameTracks === 'object') {
      const tracksArray = Array.isArray(frameTracks) ? frameTracks : Object.values(frameTracks)
      ctx.globalAlpha = opacity
      
      tracksArray.forEach(track => {
        if (!track || !track.bbox) return
        const [x1, y1, x2, y2] = track.bbox
        const centerX = (x1 + x2) / 2
        const centerY = (y1 + y2) / 2

        // Color based on heatmap type
        let color = 'rgba(255, 0, 0, 0.5)'
        if (heatmapType === 'speed' && track.speed !== undefined) {
          const intensity = Math.min(track.speed / 10, 1) // Normalize speed
          color = `rgba(255, ${255 * (1 - intensity)}, 0, ${opacity})`
        } else if (heatmapType === 'acceleration' && track.acceleration !== undefined) {
          const intensity = Math.min(Math.abs(track.acceleration) / 5, 1)
          color = `rgba(0, ${255 * intensity}, 255, ${opacity})`
        }

        ctx.fillStyle = color
        ctx.beginPath()
        ctx.arc(centerX, centerY, 20, 0, Math.PI * 2)
        ctx.fill()
      })
      
      ctx.globalAlpha = 1.0
    }
  }, [])

  // Render overlays on canvas
  const renderOverlays = useCallback(() => {
    if (!canvasRef.current || !showOverlays) {
      if (!showOverlays && currentFrameNum % 60 === 0) {
        console.log('Overlays disabled or canvas not available')
      }
      return
    }

    const canvas = canvasRef.current
    if (!canvas) return
    
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    
    const video = videoRef.current
    if (!video || !video.videoWidth || !video.videoHeight || video.videoWidth === 0 || video.videoHeight === 0) {
      if (currentFrameNum % 60 === 0) {
        console.log('Video not ready for rendering:', {
          hasVideo: !!video,
          videoWidth: video?.videoWidth,
          videoHeight: video?.videoHeight
        })
      }
      return
    }

    // Use current values from refs/state at render time
    const currentOverlayData = overlayData || null
    // Calculate current frame from video's currentTime if available, otherwise use state
    let currentFrame = currentFrameNum || 0
    if (videoMetadata && video.currentTime !== undefined && !isNaN(video.currentTime)) {
      currentFrame = Math.floor(video.currentTime * videoMetadata.fps)
    }
    const currentTracks = tracks || {}
    const currentHovered = hoveredTrack || null
    const currentSettings = overlaySettings || {}
    
    // Debug: log overlay data availability and settings
    if (currentFrame % 60 === 0) {
      console.log('Overlay rendering check:', {
        hasOverlayData: !!currentOverlayData,
        showOverlays: showOverlays,
        currentFrame: currentFrame,
        overlayDataKeys: currentOverlayData ? Object.keys(currentOverlayData).slice(0, 10) : [],
        showBoundingBoxes: currentSettings.showBoundingBoxes,
        showCirclesAtFeet: currentSettings.showCirclesAtFeet,
        showLabels: currentSettings.showLabels
      })
    }

    try {
      // Set canvas size to match video
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Draw track trails (trajectories) if enabled - draw before current frame tracks
      if (currentSettings.showTrajectories !== false && trackHistoryRef.current) {
        const trailLength = currentSettings.trailLength || 30 // frames to show in trail
        const startFrame = Math.max(0, currentFrame - trailLength)
        
        Object.entries(trackHistoryRef.current).forEach(([trackId, history]) => {
          if (!history || history.length === 0) return
          
          // Get trail points within the frame range
          const trailPoints = history.filter(p => p.frame >= startFrame && p.frame <= currentFrame)
          if (trailPoints.length < 2) return
          
          // Get track color
          const firstPoint = trailPoints[0]
          const trackColor = firstPoint.color || '#00FF00'
          
          // Draw trail as connected dots/lines
          ctx.strokeStyle = trackColor
          ctx.lineWidth = 2
          ctx.globalAlpha = 0.6
          
          // Draw trail as connected dots (like desktop version)
          // Use the stored x, y coordinates from track history
          trailPoints.forEach((point, idx) => {
            // Use stored center coordinates or calculate from bbox
            let x, y
            if (point.x !== undefined && point.y !== undefined) {
              x = point.x
              y = point.y
            } else if (point.bbox && point.bbox.length >= 4) {
              const [px1, py1, px2, py2] = point.bbox
              x = (px1 + px2) / 2
              y = (py1 + py2) / 2
            } else {
              return // Skip if no valid coordinates
            }
            
            // Scale coordinates to canvas size
            const scaleX = canvas.width / (video.videoWidth || canvas.width)
            const scaleY = canvas.height / (video.videoHeight || canvas.height)
            const scaledX = x * scaleX
            const scaledY = y * scaleY
            
            // Fade effect - older points are more transparent
            const age = idx / trailPoints.length
            const alpha = 0.3 + (1 - age) * 0.4
            ctx.globalAlpha = alpha
            
            // Draw dot with track color
            ctx.fillStyle = trackColor
            ctx.beginPath()
            ctx.arc(scaledX, scaledY, 4, 0, Math.PI * 2)
            ctx.fill()
            
            // Draw connecting line to next point
            if (idx < trailPoints.length - 1) {
              const nextPoint = trailPoints[idx + 1]
              let nextX, nextY
              if (nextPoint.x !== undefined && nextPoint.y !== undefined) {
                nextX = nextPoint.x
                nextY = nextPoint.y
              } else if (nextPoint.bbox && nextPoint.bbox.length >= 4) {
                const [nx1, ny1, nx2, ny2] = nextPoint.bbox
                nextX = (nx1 + nx2) / 2
                nextY = (ny1 + ny2) / 2
              } else {
                return
              }
              
              const scaledNextX = nextX * scaleX
              const scaledNextY = nextY * scaleY
              
              ctx.strokeStyle = trackColor
              ctx.lineWidth = 2
              ctx.beginPath()
              ctx.moveTo(scaledX, scaledY)
              ctx.lineTo(scaledNextX, scaledNextY)
              ctx.stroke()
            }
          })
          
          ctx.globalAlpha = 1.0
        })
      }

      // Get current frame tracks from overlay data
      // Handle both formats: {frames: {frame: {tracks: [...]}}} and {frame: {...}} or {frame: {track_id: {...}}}
      let frameTracks = currentTracks
      if (currentOverlayData) {
        // Try structured format first: {frames: {frame: {tracks: [...]}}}
        if (currentOverlayData.frames) {
          const frameKey = String(currentFrame)
          if (currentOverlayData.frames[frameKey]) {
            const frameData = currentOverlayData.frames[frameKey]
            frameTracks = frameData.tracks || frameData
          } else if (currentOverlayData.frames[currentFrame]) {
            // Also try numeric key
            const frameData = currentOverlayData.frames[currentFrame]
            frameTracks = frameData.tracks || frameData
          }
        } 
        // Try direct frame format: {frame: {...}} or {frame: {track_id: {...}}}
        // Frame keys might be strings or numbers
        const frameKeyStr = String(currentFrame)
        const frameKeyNum = currentFrame
        const frameData = currentOverlayData[frameKeyStr] || currentOverlayData[frameKeyNum]
        
        if (frameData) {
          // If it's an array, convert to tracks object
          if (Array.isArray(frameData)) {
            frameTracks = {}
            frameData.forEach((item, idx) => {
              if (item && typeof item === 'object' && item.bbox) {
                const trackId = String(item.track_id || item.id || `track_${idx}`)
                frameTracks[trackId] = item
              }
            })
          } 
          // If it's already an object (track_id -> item mapping), use it directly
          else if (typeof frameData === 'object') {
            frameTracks = frameData
          }
        }
        
        // Debug logging - always log when no tracks found (not just every 30 frames)
        if (Object.keys(frameTracks || {}).length === 0) {
          if (currentFrame % 10 === 0) { // Log every 10 frames to see pattern
            const sampleKeys = Object.keys(currentOverlayData).slice(0, 10).map(k => `${k} (${typeof k})`)
            const minFrame = Math.min(...Object.keys(currentOverlayData).map(k => parseInt(k) || 0))
            const maxFrame = Math.max(...Object.keys(currentOverlayData).map(k => parseInt(k) || 0))
            console.log(`Frame ${currentFrame}: No tracks found.`, {
              lookingFor: currentFrame,
              frameType: typeof currentFrame,
              overlayDataKeys: sampleKeys,
              frameRange: `${minFrame} - ${maxFrame}`,
              hasStringKey: !!currentOverlayData[String(currentFrame)],
              hasNumericKey: !!currentOverlayData[currentFrame],
              stringKeyData: currentOverlayData[String(currentFrame)],
              numericKeyData: currentOverlayData[currentFrame]
            })
          }
        } else {
          // Log when tracks ARE found
          if (currentFrame % 30 === 0) {
            console.log(`Frame ${currentFrame}: Found ${Object.keys(frameTracks).length} tracks`)
          }
        }
      }

      // Render tracks
      if (frameTracks && typeof frameTracks === 'object') {
        const tracksArray = Array.isArray(frameTracks) ? frameTracks : Object.values(frameTracks)
        
        // Debug: log track count and first track details
        if (tracksArray.length > 0 && currentFrame % 30 === 0) {
          const firstTrack = tracksArray[0]
          console.log(`Frame ${currentFrame}: Rendering ${tracksArray.length} tracks. First track:`, {
            track_id: firstTrack.track_id,
            bbox: firstTrack.bbox,
            hasBbox: !!firstTrack.bbox && Array.isArray(firstTrack.bbox) && firstTrack.bbox.length >= 4
          })
        }
        
        tracksArray.forEach(track => {
          try {
            if (!track || !track.bbox || !Array.isArray(track.bbox) || track.bbox.length < 4) {
              // Skip tracks without valid bbox
              return
            }
            
            // Validate bbox coordinates
            const [x1, y1, x2, y2] = track.bbox
            if (isNaN(x1) || isNaN(y1) || isNaN(x2) || isNaN(y2) || x1 >= x2 || y1 >= y2) {
              console.warn(`Invalid bbox for track ${track.track_id}:`, track.bbox)
              return
            }

            const trackId = track.track_id || track.id || 'unknown'
            const isHovered = currentHovered === trackId
            const isSelected = false // Could add selected state

            // Scale coordinates if needed (in case bbox is in different coordinate system)
            const scaleX = canvas.width / (video.videoWidth || canvas.width)
            const scaleY = canvas.height / (video.videoHeight || canvas.height)
            const scaledX1 = x1 * scaleX
            const scaledY1 = y1 * scaleY
            const scaledX2 = x2 * scaleX
            const scaledY2 = y2 * scaleY

            // Debug: log when trying to draw bbox (first track only, every 30 frames)
            if (tracksArray.indexOf(track) === 0 && currentFrame % 30 === 0) {
              console.log(`Drawing bbox for frame ${currentFrame}:`, {
                showBoundingBoxes: currentSettings.showBoundingBoxes,
                bbox: [x1, y1, x2, y2],
                scaled: [scaledX1, scaledY1, scaledX2, scaledY2],
                canvasSize: [canvas.width, canvas.height],
                videoSize: [video.videoWidth, video.videoHeight]
              })
            }

            // Draw bounding box (if enabled) - YOLO boxes
            if (currentSettings.showBoundingBoxes !== false) {
              const boxColor = isHovered ? '#FF6B35' : (track.color || '#00FF00')
              
              // Draw semi-transparent fill first (behind stroke)
              ctx.fillStyle = boxColor
              ctx.globalAlpha = 0.15
              ctx.fillRect(scaledX1, scaledY1, scaledX2 - scaledX1, scaledY2 - scaledY1)
              
              // Draw stroke on top
              ctx.globalAlpha = currentSettings.opacity || 0.9
              ctx.strokeStyle = boxColor
              ctx.lineWidth = isHovered ? 3 : 2
              ctx.strokeRect(scaledX1, scaledY1, scaledX2 - scaledX1, scaledY2 - scaledY1)
              
              ctx.globalAlpha = 1.0
            }

            // Draw circle at feet (foot-based tracking marker)
            if (currentSettings.showCirclesAtFeet !== false) {
              const feetY = scaledY2 // Bottom of bounding box (feet position)
              const centerX = (scaledX1 + scaledX2) / 2
              
              ctx.globalAlpha = 0.7
              ctx.fillStyle = track.color || '#00FF00'
              ctx.strokeStyle = '#FFFFFF'
              ctx.lineWidth = 2
              
              // Draw circle at feet
              ctx.beginPath()
              ctx.arc(centerX, feetY, 8, 0, Math.PI * 2)
              ctx.fill()
              ctx.stroke()
              
              ctx.globalAlpha = 1.0
            }

            // Get jersey number from track data or player gallery
            let jerseyNumber = track.jersey_number
            if (!jerseyNumber && track.player_name && playerGalleryCacheRef.current) {
              const nameKey = track.player_name.toLowerCase().trim()
              const playerData = playerGalleryCacheRef.current[nameKey]
              if (playerData && playerData.jersey_number) {
                jerseyNumber = playerData.jersey_number
              }
            }

            // Draw jersey number prominently on bounding box (top-left corner) if enabled
            if (jerseyNumber && currentSettings.showJerseyNumbers !== false) {
              const jerseyText = `#${jerseyNumber}`
              ctx.font = 'bold 16px Arial'
              const textMetrics = ctx.measureText(jerseyText)
              const textWidth = textMetrics.width
              const textHeight = 18
              const padding = 4
              
              // Draw background box
              ctx.fillStyle = 'rgba(0, 0, 0, 0.8)'
              ctx.fillRect(scaledX1, scaledY1 - textHeight - padding, textWidth + padding * 2, textHeight + padding * 2)
              
              // Draw jersey number
              ctx.fillStyle = '#FFFF00'
              ctx.font = 'bold 16px Arial'
              ctx.fillText(jerseyText, scaledX1 + padding, scaledY1 - padding)
            }

            // Draw track ID label (if enabled and jersey number not shown, or if both enabled)
            if (currentSettings.showLabels !== false) {
              const labelY = jerseyNumber && currentSettings.showJerseyNumbers !== false 
                ? scaledY1 - 40  // Move down if jersey number is shown
                : scaledY1 - 20
              
              ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
              ctx.fillRect(scaledX1, labelY - 20, 60, 20)
              ctx.fillStyle = '#FFFFFF'
              ctx.font = '12px Arial'
              ctx.fillText(`ID: ${trackId}`, scaledX1 + 5, labelY - 5)
            }

            // Draw player name if available (below bounding box)
            if (track.player_name && currentSettings.showLabels !== false) {
              const nameText = track.player_name
              ctx.font = '12px Arial'
              const nameMetrics = ctx.measureText(nameText)
              const nameWidth = nameMetrics.width
              
              ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
              ctx.fillRect(scaledX1, scaledY2, nameWidth + 10, 20)
              ctx.fillStyle = '#FFFFFF'
              ctx.font = '12px Arial'
              ctx.fillText(nameText, scaledX1 + 5, scaledY2 + 15)
              
              // Draw Re-ID match confidence if available
              if (track.gallery_match_confidence !== undefined && currentSettings.showReidConfidence !== false) {
                const confidence = track.gallery_match_confidence
                const confidenceText = `${(confidence * 100).toFixed(0)}%`
                const confWidth = ctx.measureText(confidenceText).width
                
                // Color based on confidence: green (high) -> yellow (medium) -> red (low)
                let confColor = '#00FF00' // Green for high confidence
                if (confidence < 0.7) confColor = '#FFFF00' // Yellow for medium
                if (confidence < 0.5) confColor = '#FF6B35' // Orange/red for low
                
                ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
                ctx.fillRect(scaledX1 + nameWidth + 15, scaledY2, confWidth + 10, 20)
                ctx.fillStyle = confColor
                ctx.font = '11px Arial'
                ctx.fillText(confidenceText, scaledX1 + nameWidth + 20, scaledY2 + 15)
              }
            }

            // Draw speed/analytics if available
            if (track.speed !== undefined) {
              const speedText = `${track.speed.toFixed(1)} px/s`
              ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
              ctx.fillRect(scaledX1, scaledY2 + 36, 80, 16)
              ctx.fillStyle = '#FFFF00'
              ctx.font = '11px Arial'
              ctx.fillText(speedText, scaledX1 + 5, scaledY2 + 49)
            }
          } catch (err) {
            console.error('Error rendering track:', err)
          }
        })
      }


      // Render heatmap if enabled
      if (currentSettings.showHeatmap) {
        try {
          renderHeatmap(ctx, canvas, currentFrame, currentSettings, frameTracks)
        } catch (err) {
          console.error('Error rendering heatmap:', err)
        }
      }

      // Render analytics overlays if enabled
      if (currentSettings.showAnalytics) {
        try {
          renderAnalytics(ctx, canvas, video, currentFrame, frameTracks, currentSettings)
        } catch (err) {
          console.error('Error rendering analytics:', err)
        }
      }
    } catch (err) {
      console.error('Error in renderOverlays:', err)
      // Don't throw - just log the error
    }
  }, [showOverlays, overlayData, tracks, currentFrameNum, hoveredTrack, overlaySettings, videoMetadata, renderAnalytics, renderHeatmap])

  // Update canvas on frame change and during playback
  useEffect(() => {
    if (!videoRef.current || !canvasRef.current) return

    // Cancel any existing animation
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }

    const render = () => {
      try {
        if (videoRef.current && canvasRef.current) {
          renderOverlays()
        }
      } catch (err) {
        console.error('Error in render effect:', err)
      }
    }

    if (isPlaying && !isPaused) {
      const animate = () => {
        if (videoRef.current && canvasRef.current && isPlaying && !isPaused) {
          render()
          animationFrameRef.current = requestAnimationFrame(animate)
        } else {
          animationFrameRef.current = null
        }
      }
      animationFrameRef.current = requestAnimationFrame(animate)
    } else {
      // Render once when paused
      render()
    }

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
        animationFrameRef.current = null
      }
    }
  }, [isPlaying, isPaused, currentFrameNum, showOverlays, overlayData, renderOverlays])

  // Handle mouse move for track hover
  const handleCanvasMouseMove = (e) => {
    if (!canvasRef.current || !taggingMode) {
      setHoveredTrack(null)
      return
    }

    const rect = canvasRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    const hovered = Object.values(tracks).find(track => {
      if (!track.bbox) return false
      const [x1, y1, x2, y2] = track.bbox
      return x >= x1 && x <= x2 && y >= y1 && y <= y2
    })

    setHoveredTrack(hovered?.track_id || null)
    canvasRef.current.style.cursor = hovered ? 'pointer' : 'default'
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return

      switch (e.key) {
        case ' ':
          e.preventDefault()
          togglePlayPause()
          break
        case 'ArrowLeft':
          e.preventDefault()
          goToPreviousFrame()
          break
        case 'ArrowRight':
          e.preventDefault()
          goToNextFrame()
          break
      }
    }

    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [currentFrameNum, videoMetadata])

  if (loading) {
    return (
      <div className="video-player loading">
        <div className="loading-spinner">Loading video...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="video-player error">
        <div className="error-message">
          <div style={{ marginBottom: '10px', fontWeight: 'bold', color: '#ff4444', fontSize: '1.1em' }}>⚠️ Video Playback Error</div>
          <div style={{ marginBottom: '15px', lineHeight: '1.5' }}>{error}</div>
          {(error.includes('codec') || error.includes('format') || error.includes('DEMUXER') || error.includes('no supported streams') || error.includes('H.265') || error.includes('HEVC')) && (
            <div style={{ fontSize: '0.9em', color: '#333', marginTop: '15px', padding: '15px', backgroundColor: '#fff3cd', borderRadius: '4px', border: '1px solid #ffc107' }}>
              <div style={{ fontWeight: 'bold', marginBottom: '8px', color: '#856404' }}>💡 Why this happens:</div>
              <div style={{ marginBottom: '10px', lineHeight: '1.5' }}>
                Your MP4 file plays in VLC because VLC supports many codecs (H.264, H.265/HEVC, VP9, etc.). 
                However, <strong>web browsers only support H.264 (AVC) codec</strong> in MP4 files for security and compatibility reasons.
              </div>
              <div style={{ fontWeight: 'bold', marginTop: '10px', marginBottom: '8px', color: '#856404' }}>✅ Solution:</div>
              <div style={{ lineHeight: '1.5', marginBottom: '10px' }}>
                Go to the <strong>Events tab</strong> (🎯 Events) and scroll down to find the <strong>"🎥 Video Quality Enhancement"</strong> section. 
                Use it to convert your video to MP4 format with H.264 codec, which will make it playable in all browsers.
              </div>
              <div style={{ fontSize: '0.85em', color: '#666', fontStyle: 'italic', paddingTop: '8px', borderTop: '1px solid #ddd' }}>
                Alternative: Convert manually using FFmpeg: <code style={{ backgroundColor: '#f5f5f5', padding: '2px 6px', borderRadius: '3px' }}>ffmpeg -i input.mp4 -c:v libx264 -c:a aac -movflags +faststart output.mp4</code>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // Update stream key when pause state changes for live streams
  useEffect(() => {
    if (!videoPath) {
      // Force refresh when pause state changes
      setStreamKey(prev => prev + 1)
    }
  }, [isPaused, videoPath])

  // Toggle play/pause for live stream (separate from video file toggle)
  const toggleLiveStreamPlayPause = () => {
    setIsPaused(!isPaused)
    setStreamKey(prev => prev + 1) // Force refresh
  }
  
  // Auto-refresh stream when playing (only for live streams)
  useEffect(() => {
    if (!videoPath && !isPaused && !streamError) {
      // Refresh image every 100ms for smooth playback (10 FPS)
      refreshIntervalRef.current = setInterval(() => {
        setStreamKey(prev => prev + 1)
      }, 100)
    } else {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
        refreshIntervalRef.current = null
      }
    }
    
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
      }
    }
  }, [isPaused, streamError, videoPath])

  // Live stream mode (no videoPath)
  if (!videoPath) {
    // Use MJPEG stream with proper parsing for smooth playback
    const streamUrl = '/video'
    const streamCanvasRef = useRef(null)
    const streamAbortControllerRef = useRef(null)
    
    // MJPEG stream handler using fetch and canvas
    useEffect(() => {
      if (isPaused || streamError) {
        // Stop stream when paused or on error
        if (streamAbortControllerRef.current) {
          streamAbortControllerRef.current.abort()
          streamAbortControllerRef.current = null
        }
        return
      }
      
      const canvas = streamCanvasRef.current || canvasRef.current
      if (!canvas) return
      
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      
      // Start MJPEG stream
      const abortController = new AbortController()
      streamAbortControllerRef.current = abortController
      
      const loadStream = async () => {
        try {
          const response = await fetch(streamUrl, {
            signal: abortController.signal,
            headers: {
              'Cache-Control': 'no-cache'
            }
          })
          
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`)
          }
          
          const reader = response.body.getReader()
          let buffer = new Uint8Array(0)
          let frameCount = 0
          
          setStreamError(false)
          console.log('✓ MJPEG stream connected')
          
          while (!abortController.signal.aborted && !isPaused) {
            const { done, value } = await reader.read()
            
            if (done) {
              console.log('MJPEG stream ended')
              break
            }
            
            // Append new data to buffer
            const newBuffer = new Uint8Array(buffer.length + value.length)
            newBuffer.set(buffer)
            newBuffer.set(value, buffer.length)
            buffer = newBuffer
            
            // Look for JPEG boundaries in binary data
            const boundary = new TextEncoder().encode('--jpgboundary\r\n')
            let boundaryIndex = findBytes(buffer, boundary)
            
            while (boundaryIndex !== -1) {
              // Find the next boundary
              const nextBoundary = findBytes(buffer, boundary, boundaryIndex + boundary.length)
              
              if (nextBoundary === -1) {
                // Incomplete frame, keep buffer
                break
              }
              
              // Extract frame data between boundaries
              const frameStart = boundaryIndex + boundary.length
              const frameData = buffer.slice(frameStart, nextBoundary)
              
              // Find Content-Length header (convert to string for regex)
              const frameText = new TextDecoder().decode(frameData)
              const contentLengthMatch = frameText.match(/Content-Length:\s*(\d+)/i)
              
              if (contentLengthMatch) {
                const contentLength = parseInt(contentLengthMatch[1])
                const headerEnd = frameText.indexOf('\r\n\r\n')
                
                if (headerEnd !== -1) {
                  // Extract JPEG data (after headers, in binary)
                  const jpegStart = headerEnd + 4
                  const jpegBytes = frameData.slice(jpegStart, jpegStart + contentLength)
                  
                  // Create image from JPEG data
                  const blob = new Blob([jpegBytes], { type: 'image/jpeg' })
                  const imageUrl = URL.createObjectURL(blob)
                  const img = new Image()
                  
                  img.onload = () => {
                    if (canvas && ctx && !isPaused && !abortController.signal.aborted) {
                      // Set canvas size to match image
                      canvas.width = img.width
                      canvas.height = img.height
                      ctx.drawImage(img, 0, 0)
                      frameCount++
                      
                      if (frameCount === 1) {
                        console.log(`✓ First frame received: ${img.width}x${img.height}`)
                      }
                    }
                    URL.revokeObjectURL(imageUrl)
                  }
                  
                  img.onerror = (e) => {
                    console.error('Error loading frame image:', e)
                    URL.revokeObjectURL(imageUrl)
                  }
                  
                  img.src = imageUrl
                }
              }
              
              // Remove processed data from buffer
              buffer = buffer.slice(nextBoundary)
              boundaryIndex = findBytes(buffer, boundary)
            }
          }
        } catch (err) {
          if (err.name !== 'AbortError') {
            console.error('MJPEG stream error:', err)
            setStreamError(true)
            // Retry after 2 seconds
            setTimeout(() => {
              setStreamError(false)
            }, 2000)
          }
        }
      }
      
      // Helper function to find byte pattern in Uint8Array
      const findBytes = (haystack, needle, startIndex = 0) => {
        for (let i = startIndex; i <= haystack.length - needle.length; i++) {
          let match = true
          for (let j = 0; j < needle.length; j++) {
            if (haystack[i + j] !== needle[j]) {
              match = false
              break
            }
          }
          if (match) return i
        }
        return -1
      }
      
      loadStream()
      
      return () => {
        if (abortController) {
          abortController.abort()
        }
      }
    }, [isPaused, streamError, streamUrl])
    
    return (
      <div className="video-player">
        <div className="video-container" style={{ position: 'relative', width: '100%', height: '100%' }}>
          {!isPaused ? (
            <>
              <canvas
                ref={streamCanvasRef}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain',
                  backgroundColor: '#000',
                  display: 'block'
                }}
              />
              {streamError && (
                <div style={{
                  position: 'absolute',
                  top: '50%',
                  left: '50%',
                  transform: 'translate(-50%, -50%)',
                  backgroundColor: 'rgba(0, 0, 0, 0.8)',
                  color: '#fff',
                  padding: '20px',
                  borderRadius: '4px',
                  textAlign: 'center',
                  zIndex: 10
                }}>
                  <div>⚠️ Stream Error</div>
                  <div style={{ fontSize: '14px', marginTop: '10px' }}>
                    Make sure the Live Feed is running in the desktop application
                  </div>
                  <div style={{ fontSize: '12px', marginTop: '10px', color: '#aaa' }}>
                    Stream URL: {streamUrl}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: '#000',
              color: '#fff',
              fontSize: '18px'
            }}>
              ⏸️ Paused
            </div>
          )}
          <div className="video-overlay">
            <div className="video-controls">
              <button 
                onClick={toggleLiveStreamPlayPause} 
                className="play-pause-btn"
                style={{
                  padding: '10px 20px',
                  fontSize: '18px',
                  cursor: 'pointer',
                  backgroundColor: 'rgba(0, 0, 0, 0.7)',
                  border: 'none',
                  borderRadius: '4px',
                  color: '#fff'
                }}
              >
                {isPaused ? '▶️ Play' : '⏸️ Pause'}
              </button>
              <div className="video-info">
                <span>Live Feed {isPaused ? '(Paused)' : ''}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Video file playback mode
  return (
    <div className="video-player">
      <div className="video-container" ref={containerRef}>
        <video
          ref={videoRef}
          src={`/video/${encodeURIComponent(videoPath.replace(/\\/g, '/'))}`}
          onTimeUpdate={handleTimeUpdate}
          crossOrigin="anonymous"
          preload="auto"
          onEnded={handleVideoEnded}
          onError={(e) => {
            console.error('Video error:', e)
            const video = e.target
            if (video.error) {
              console.error('Video error code:', video.error.code)
              console.error('Video error message:', video.error.message)
              
              let errorMsg = 'Video playback error: '
              switch (video.error.code) {
                case video.error.MEDIA_ERR_ABORTED:
                  errorMsg = 'Video loading was aborted'
                  break
                case video.error.MEDIA_ERR_NETWORK:
                  errorMsg = 'Network error while loading video. Please check your connection.'
                  break
                case video.error.MEDIA_ERR_DECODE:
                  errorMsg = 'Video decoding error. The video codec may not be supported by your browser. '
                  errorMsg += 'Go to the Events tab and use the "Video Quality Enhancement" feature to convert to H.264 codec.'
                  break
                case video.error.MEDIA_ERR_SRC_NOT_SUPPORTED:
                  errorMsg = 'Video format not supported. Your browser cannot play this video format. '
                  errorMsg += 'Supported formats: MP4 (H.264), WebM, OGG. '
                  errorMsg += 'Go to the Events tab and use the "Video Quality Enhancement" feature to convert to MP4 with H.264.'
                  break
                default:
                  // Check for specific error messages
                  const errorText = video.error.message || ''
                  if (errorText.includes('DEMUXER_ERROR') || errorText.includes('no supported streams')) {
                    errorMsg = 'Video codec not supported by browser. '
                    errorMsg += 'Even though your video is MP4 format, it may be using a codec (like H.265/HEVC) that browsers cannot play. '
                    errorMsg += 'Browsers only support H.264 codec in MP4 files. '
                    errorMsg += 'VLC can play many codecs, but browsers are more limited. '
                    errorMsg += 'Go to the Events tab (🎯 Events) and scroll down to the "🎥 Video Quality Enhancement" section to convert your video to H.264 codec.'
                  } else {
                    errorMsg = `Video playback error: ${errorText || 'Unknown error'}`
                  }
              }
              setError(errorMsg)
            }
          }}
          onLoadStart={() => {
            console.log('Video load started:', videoPath)
          }}
          onCanPlayThrough={() => {
            console.log('Video can play through')
          }}
          onLoadedMetadata={(e) => {
            if (videoRef.current && videoMetadata) {
              videoRef.current.currentTime = currentFrameNum / videoMetadata.fps
            }
            // Adjust container to match video's natural aspect ratio
            if (containerRef.current && e.target) {
              const video = e.target
              const videoWidth = video.videoWidth || videoMetadata?.width
              const videoHeight = video.videoHeight || videoMetadata?.height
              if (videoWidth && videoHeight) {
                const aspectRatio = videoWidth / videoHeight
                containerRef.current.style.aspectRatio = `${aspectRatio}`
              }
            }
          }}
          onWaiting={(e) => {
            // Video is buffering - pause playback until buffer is ready
            if (videoRef.current && isPlaying) {
              console.log('Video buffering, waiting for data...')
            }
          }}
          onCanPlay={(e) => {
            // Buffer is ready - resume playback if it was playing
            if (videoRef.current && isPlaying && !isPaused) {
              videoRef.current.play().catch(err => {
                console.error('Error resuming playback:', err)
              })
            }
          }}
          onProgress={(e) => {
            // Monitor buffer progress
            if (videoRef.current) {
              const video = videoRef.current
              const buffered = video.buffered
              if (buffered.length > 0) {
                const bufferedEnd = buffered.end(buffered.length - 1)
                const currentTime = video.currentTime
                const bufferAhead = bufferedEnd - currentTime
                
                // Log buffer status for debugging (only if very low)
                if (bufferAhead < 0.5 && isPlaying && !isPaused) {
                  console.log(`Very low buffer: ${bufferAhead.toFixed(2)}s ahead`)
                }
              }
            }
          }}
          className="video-element"
          controls={false}
          playsInline
          preload="auto"
          crossOrigin="anonymous"
        />
        <canvas
          ref={canvasRef}
          className="overlay-canvas"
          onClick={handleCanvasClick}
          onMouseMove={handleCanvasMouseMove}
          style={{
            cursor: taggingMode ? 'crosshair' : 'default',
            pointerEvents: taggingMode ? 'auto' : 'none'
          }}
        />
        <div className="video-overlay">
          <div className="video-controls">
            <button onClick={togglePlayPause} className="play-pause-btn">
              {isPaused ? '▶️' : '⏸️'}
            </button>
            <button onClick={goToPreviousFrame} className="frame-nav-btn" title="Previous Frame (←)">
              ⏮️
            </button>
            <button onClick={goToNextFrame} className="frame-nav-btn" title="Next Frame (→)">
              ⏭️
            </button>
            <div className="video-info">
              <span>Frame: {currentFrameNum} / {videoMetadata?.frame_count || 0}</span>
              <span>Time: {formatTime(frameTime)} / {formatTime(videoMetadata?.duration || 0)}</span>
            </div>
            {taggingMode && (
              <div className="tagging-indicator">
                🏷️ Tagging Mode - Click on tracks to tag
              </div>
            )}
          </div>
        </div>
        {videoMetadata && (
          <div className="video-progress">
            <input
              type="range"
              min="0"
              max={videoMetadata.frame_count - 1}
              value={currentFrameNum}
              onChange={(e) => {
                const frame = parseInt(e.target.value)
                seekToFrame(frame)
              }}
              onInput={(e) => {
                // Update immediately on drag for smoother scrubbing
                const frame = parseInt(e.target.value)
                if (videoRef.current && videoMetadata) {
                  const time = frame / videoMetadata.fps
                  videoRef.current.currentTime = time
                  setCurrentFrameNum(frame)
                }
              }}
              className="progress-slider"
            />
          </div>
        )}
      </div>
    </div>
  )
}

const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export default VideoPlayer
