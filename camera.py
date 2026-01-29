"""
camera.py - Webcam Capture Module

This module handles real-time webcam input using OpenCV.
It provides functionality to capture frames and ensures proper 
resource management (camera release).

Key Responsibilities:
- Initialize webcam
- Capture frames reliably
- Handle camera resource cleanup
- Provide frame dimensions
"""

import cv2
import streamlit as st


class CameraHandler:
    """
    Manages webcam capture operations.
    
    This class encapsulates OpenCV webcam functionality with
    proper resource management and error handling.
    """
    
    def __init__(self, camera_index=0):
        """
        Initialize the camera handler.
        
        Args:
            camera_index (int): Index of the camera (default: 0 for primary camera)
        """
        self.camera_index = camera_index
        self.cap = None
        
    def open_camera(self):
        """
        Open and initialize the webcam.
        
        Returns:
            bool: True if camera opened successfully, False otherwise
        """
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            
            # Set camera properties for better performance
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Test if camera is working
            ret, _ = self.cap.read()
            if not ret:
                st.error("❌ Failed to access camera. Please check permissions.")
                return False
            
            return True
        except Exception as e:
            st.error(f"❌ Error opening camera: {str(e)}")
            return False
    
    def capture_frame(self):
        """
        Capture a single frame from the webcam.
        
        Returns:
            tuple: (frame_numpy_array, success_bool)
                   Returns (None, False) if capture fails
        """
        if self.cap is None:
            return None, False
        
        try:
            ret, frame = self.cap.read()
            if not ret:
                return None, False
            
            # Mirror the frame for better UX (front-facing camera)
            frame = cv2.flip(frame, 1)
            
            # Convert BGR to RGB for Streamlit display
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            return frame_rgb, True
        except Exception as e:
            st.error(f"❌ Error capturing frame: {str(e)}")
            return None, False
    
    def get_frame_dimensions(self):
        """
        Get the dimensions of captured frames.
        
        Returns:
            tuple: (width, height) or (None, None) if camera not open
        """
        if self.cap is None:
            return None, None
        
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        return width, height
    
    def release_camera(self):
        """
        Release the camera resource.
        
        This should be called when done to prevent resource leaks.
        """
        if self.cap is not None:
            self.cap.release()
            self.cap = None


def get_camera(camera_index=0):
    """
    Get or create camera handler (Streamlit session state).
    
    Args:
        camera_index (int): Index of the camera
        
    Returns:
        CameraHandler: Initialized camera handler instance
    """
    if 'camera' not in st.session_state or st.session_state.camera.camera_index != camera_index:
        st.session_state.camera = CameraHandler(camera_index)
    
    return st.session_state.camera
