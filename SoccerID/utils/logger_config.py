"""
Centralized Logging System for Soccer Analysis Tool

Provides a unified logging interface with:
- Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- File rotation and log file management
- GUI log viewer integration
- Performance logging
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

class SoccerAnalysisLogger:
    """Centralized logger for the soccer analysis application"""
    
    _instance: Optional['SoccerAnalysisLogger'] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Create loggers for different components
        self.main_logger = self._create_logger("main", "soccer_analysis.log")
        self.tracking_logger = self._create_logger("tracking", "tracking.log")
        self.reid_logger = self._create_logger("reid", "reid.log")
        self.gallery_logger = self._create_logger("gallery", "gallery.log")
        self.gui_logger = self._create_logger("gui", "gui.log")
        self.performance_logger = self._create_logger("performance", "performance.log", level=logging.DEBUG)
        
        # Default logger (for backward compatibility)
        self.logger = self.main_logger
        
        # Log viewer callbacks (for GUI integration)
        self.log_viewer_callbacks = []
        
        self._initialized = True
    
    def _create_logger(self, name: str, filename: str, level: int = logging.INFO) -> logging.Logger:
        """Create a logger with file and console handlers"""
        logger = logging.getLogger(f"soccer_analysis.{name}")
        logger.setLevel(level)
        
        # Avoid duplicate handlers
        if logger.handlers:
            return logger
        
        # File handler with rotation (10MB max, keep 5 backups)
        log_file = self.log_dir / filename
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console handler (only INFO and above)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # Custom handler for GUI log viewer
        gui_handler = GUILogHandler(self)
        gui_handler.setLevel(logging.DEBUG)
        gui_handler.setFormatter(file_formatter)
        logger.addHandler(gui_handler)
        
        return logger
    
    def set_level(self, level: int):
        """Set log level for all loggers"""
        for logger in [self.main_logger, self.tracking_logger, self.reid_logger, 
                       self.gallery_logger, self.gui_logger, self.performance_logger]:
            logger.setLevel(level)
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                    handler.setLevel(level)
    
    def register_log_viewer(self, callback):
        """Register a callback for GUI log viewer"""
        self.log_viewer_callbacks.append(callback)
    
    def unregister_log_viewer(self, callback):
        """Unregister a log viewer callback"""
        if callback in self.log_viewer_callbacks:
            self.log_viewer_callbacks.remove(callback)
    
    def _notify_log_viewers(self, record: logging.LogRecord):
        """Notify all registered log viewers"""
        for callback in self.log_viewer_callbacks:
            try:
                callback(record)
            except Exception:
                pass  # Don't fail if viewer callback fails


class GUILogHandler(logging.Handler):
    """Custom handler that forwards logs to GUI log viewer"""
    
    def __init__(self, logger_instance: SoccerAnalysisLogger):
        super().__init__()
        self.logger_instance = logger_instance
    
    def emit(self, record: logging.LogRecord):
        """Emit a log record to GUI viewers"""
        self.logger_instance._notify_log_viewers(record)


# Global logger instance
_logger_instance: Optional[SoccerAnalysisLogger] = None

def get_logger(name: str = "main") -> logging.Logger:
    """Get a logger instance"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SoccerAnalysisLogger()
    
    logger_map = {
        "main": _logger_instance.main_logger,
        "tracking": _logger_instance.tracking_logger,
        "reid": _logger_instance.reid_logger,
        "gallery": _logger_instance.gallery_logger,
        "gui": _logger_instance.gui_logger,
        "performance": _logger_instance.performance_logger,
    }
    
    return logger_map.get(name, _logger_instance.main_logger)


def set_log_level(level: str):
    """Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"""
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    if _logger_instance:
        _logger_instance.set_level(level_map.get(level.upper(), logging.INFO))


# Convenience functions for backward compatibility
def debug(msg: str, *args, **kwargs):
    """Log debug message"""
    get_logger("main").debug(msg, *args, **kwargs)

def info(msg: str, *args, **kwargs):
    """Log info message"""
    get_logger("main").info(msg, *args, **kwargs)

def warning(msg: str, *args, **kwargs):
    """Log warning message"""
    get_logger("main").warning(msg, *args, **kwargs)

def error(msg: str, *args, **kwargs):
    """Log error message"""
    get_logger("main").error(msg, *args, **kwargs)

def critical(msg: str, *args, **kwargs):
    """Log critical message"""
    get_logger("main").critical(msg, *args, **kwargs)

def exception(msg: str, *args, exc_info=True, **kwargs):
    """Log exception with traceback"""
    get_logger("main").error(msg, *args, exc_info=exc_info, **kwargs)

