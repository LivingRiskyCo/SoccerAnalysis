import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useSocket } from '../contexts/SocketContext'
import HelpSystem from './HelpSystem'
import './Layout.css'

const Layout = ({ children }) => {
  const location = useLocation()
  const { connected } = useSocket()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [showHelp, setShowHelp] = useState(false)
  const [helpFeature, setHelpFeature] = useState(null)

  const navItems = [
    { path: '/', label: 'Dashboard', icon: '🏠' },
    { path: '/live-feed', label: 'Live Feed', icon: '📺' },
    { path: '/players', label: 'Players', icon: '👥' },
    { path: '/video-analysis', label: 'Video Analysis', icon: '🎬' },
    { path: '/advanced-analytics', label: 'Advanced Analytics', icon: '📊' },
    { path: '/opponent-intelligence', label: 'Opponent Intel', icon: '⚽' },
    { path: '/batch-processing', label: 'Batch Processing', icon: '⚡' },
    { path: '/statistics', label: 'Statistics', icon: '📈' },
    { path: '/team', label: 'Team', icon: '⚽' },
    { path: '/video-comparison', label: 'Multi-View', icon: '📹' }
  ]

  return (
    <div className="layout">
      <aside className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <h2>⚽ DSX Analysis</h2>
          <button 
            className="sidebar-toggle"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? '◀' : '▶'}
          </button>
        </div>
        <nav className="sidebar-nav">
          {navItems.map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              {sidebarOpen && <span className="nav-label">{item.label}</span>}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
            <span className="status-dot"></span>
            {sidebarOpen && <span>{connected ? 'Connected' : 'Disconnected'}</span>}
          </div>
        </div>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <h1>DSX Soccer Analysis</h1>
          <div className="topbar-actions">
            <button
              className="help-btn"
              onClick={() => {
                // Determine help feature based on current route
                const route = location.pathname
                let feature = 'video-analysis'
                if (route.includes('batch')) feature = 'batch-processing'
                else if (route.includes('video-analysis')) feature = 'video-analysis'
                setHelpFeature(feature)
                setShowHelp(true)
              }}
              title="Help & Documentation"
            >
              ❓ Help
            </button>
            <span className={`status-badge ${connected ? 'online' : 'offline'}`}>
              {connected ? '🟢 Live' : '🔴 Offline'}
            </span>
          </div>
        </header>
        {showHelp && (
          <HelpSystem
            feature={helpFeature}
            onClose={() => setShowHelp(false)}
          />
        )}
        <div className="content-area">
          {children}
        </div>
      </main>
    </div>
  )
}

export default Layout

