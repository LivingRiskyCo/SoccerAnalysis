"""
Player Recognition Module
AI-powered player recognition using jersey numbers, faces, and other features
"""

from .jersey_ocr import EnhancedJerseyOCR, MultiFrameJerseyOCR
from .face_recognition import FaceRecognizer, MultiFrameFaceRecognizer

__all__ = ['EnhancedJerseyOCR', 'MultiFrameJerseyOCR', 'FaceRecognizer', 'MultiFrameFaceRecognizer']

