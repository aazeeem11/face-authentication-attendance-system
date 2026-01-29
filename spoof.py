"""
spoof.py - Liveness Detection & Spoof Prevention Module

This module implements basic liveness detection to prevent spoofing attacks
(presenting photos/videos of legitimate users to bypass face recognition).

Spoof Prevention Strategies Implemented:
1. Blink Detection (EAR - Eye Aspect Ratio)
   - Real faces blink; photos do not
   - We detect natural eye closure patterns

2. Frame Variation Analysis
   - Real faces have temporal variations (movement, lighting changes)
   - Static images show minimal variation across frames

Limitations & Interview Discussion Points:
- ⚠️ These are basic heuristic-based approaches
- ⚠️ Cannot detect advanced spoofs (deep fakes, high-quality masks)
- ⚠️ Production systems use CNN/RNN-based liveness detection
- 💡 Future: Use pre-trained liveness detection models (e.g., MobileNet-based)

References:
- EAR (Eye Aspect Ratio): Tereza Soukupová, Jan Terzopoulus - "Real-Time Eye Blink Detection"
"""

import numpy as np
import cv2
import face_recognition
import streamlit as st


class LivenessDetector:
    """
    Detects if a face is real (live) or a spoof (photo/video).
    
    Uses multiple heuristics for basic liveness detection.
    """
    
    def __init__(self, blink_threshold=0.25, frame_variation_threshold=500, ear_history_len=10):
        """
        Initialize liveness detector.
        
        Args:
            blink_threshold (float): EAR threshold for blink detection (default: 0.25)
            frame_variation_threshold (int): Min pixel variation for liveness (default: 500)
            ear_history_len (int): Number of frames to store for EAR history
        """
        self.blink_threshold = blink_threshold
        self.frame_variation_threshold = frame_variation_threshold
        self.frame_history = []
        self.max_history = 5
        self.ear_history = []
        self.ear_history_len = ear_history_len
        self.blink_detected = False
    
    def compute_eye_aspect_ratio(self, eye):
        """
        Compute Eye Aspect Ratio (EAR) for blink detection.
        
        Formula:
        EAR = ||p2 - p6|| + ||p3 - p5|| / (2 * ||p1 - p4||)
        
        Where p1-p6 are eye landmark points from dlib.
        
        High EAR = Eye open
        Low EAR = Eye closed (blink)
        
        Args:
            eye (np.ndarray): 6 points representing eye landmarks
            
        Returns:
            float: Eye Aspect Ratio value
        """
        # Compute distances between eye landmarks
        A = np.linalg.norm(eye[1] - eye[5])
        B = np.linalg.norm(eye[2] - eye[4])
        C = np.linalg.norm(eye[0] - eye[3])
        
        # Compute EAR
        ear = (A + B) / (2.0 * C)
        return ear
    
    def detect_blink_presence(self, frame_rgb):
        """
        Check if face in frame shows blink patterns (indicates liveness).
        
        Strategy:
        - Extract face landmarks
        - Compute EAR for both eyes
        - If EAR drops below a threshold and then recovers, a blink is detected
        
        Args:
            frame_rgb (np.ndarray): Frame in RGB format
            
        Returns:
            dict: {
                'has_blink': bool,
                'avg_ear': float,
                'message': str
            }
        """
        try:
            # Ensure frame is uint8, as face_recognition expects it
            if frame_rgb.dtype != np.uint8:
                frame_rgb = (frame_rgb * 255).astype(np.uint8)

            # Detect face landmarks
            face_landmarks_list = face_recognition.face_landmarks(frame_rgb)
            
            if not face_landmarks_list:
                return {
                    'has_blink': False,
                    'avg_ear': 0.0,
                    'message': 'No face landmarks detected for blink analysis'
                }
            
            # For simplicity, analyze first face
            face_landmarks = face_landmarks_list[0]
            
            # Extract eye landmarks
            left_eye = np.array(face_landmarks['left_eye'])
            right_eye = np.array(face_landmarks['right_eye'])
            
            # Compute EAR for both eyes
            left_ear = self.compute_eye_aspect_ratio(left_eye)
            right_ear = self.compute_eye_aspect_ratio(right_eye)
            
            # Average the EAR
            avg_ear = (left_ear + right_ear) / 2.0
            
            # Add to EAR history
            self.ear_history.append(avg_ear)
            if len(self.ear_history) > self.ear_history_len:
                self.ear_history.pop(0)

            # Check for blink
            if len(self.ear_history) == self.ear_history_len:
                # Check if EAR dropped below threshold and then recovered
                if any(ear < self.blink_threshold for ear in self.ear_history) and self.ear_history[-1] > self.blink_threshold:
                    self.blink_detected = True

            message = "Blink detected" if self.blink_detected else "No blink detected"
            
            return {
                'has_blink': self.blink_detected,
                'avg_ear': avg_ear,
                'message': message
            }
        
        except Exception as e:
            return {
                'has_blink': False,
                'avg_ear': 0.0,
                'message': f'Error in blink detection: {str(e)}'
            }
    
    def detect_frame_variation(self, frame_rgb):
        """
        Check if frames show variation (indicates real face, not static photo).
        
        Strategy:
        - Compare current frame with recent frames
        - Calculate pixel-level differences
        - If variation > threshold, likely a real face
        - Static photos show minimal variation
        
        Args:
            frame_rgb (np.ndarray): Frame in RGB format
            
        Returns:
            dict: {
                'is_live': bool,
                'variation_score': float,
                'message': str
            }
        """
        try:
            # Convert to grayscale for comparison
            gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
            
            # Add to history
            self.frame_history.append(gray)
            
            # Keep only recent frames
            if len(self.frame_history) > self.max_history:
                self.frame_history.pop(0)
            
            # Need at least 2 frames to compare
            if len(self.frame_history) < 2:
                return {
                    'is_live': True,  # Uncertain, assume live
                    'variation_score': 0,
                    'message': 'Acquiring baseline frames...'
                }
            
            # Calculate variation between frames
            frame1 = self.frame_history[-2]
            frame2 = self.frame_history[-1]
            
            # Compute absolute difference
            diff = cv2.absdiff(frame1, frame2)
            variation_score = np.sum(diff)
            
            # Check if variation exceeds threshold
            is_live = variation_score > self.frame_variation_threshold
            
            status = "✅ Live face detected" if is_live else "⚠️ Possible spoof (static image)"
            
            return {
                'is_live': is_live,
                'variation_score': variation_score,
                'message': status
            }
        
        except Exception as e:
            return {
                'is_live': False,
                'variation_score': 0,
                'message': f'Error in variation detection: {str(e)}'
            }
    
    def check_liveness(self, frame_rgb):
        """
        Perform comprehensive liveness check.
        
        Combines multiple heuristics:
        1. Frame variation analysis
        2. Blink detection
        
        Args:
            frame_rgb (np.ndarray): Frame in RGB format
            
        Returns:
            dict: {
                'is_live': bool,
                'confidence': float (0-1),
                'details': dict,
                'message': str
            }
        """
        variation_result = self.detect_frame_variation(frame_rgb)
        blink_result = self.detect_blink_presence(frame_rgb)
        
        # A face is considered live if there is frame variation AND a blink is detected
        is_live = variation_result['is_live'] and blink_result['has_blink']
        
        # Confidence can be a combination of both scores
        variation_confidence = min(1.0, variation_result['variation_score'] / 5000)
        blink_confidence = 1.0 if blink_result['has_blink'] else 0.0
        confidence = (variation_confidence + blink_confidence) / 2.0
        
        message = f"{variation_result['message']} and {blink_result['message']}"
        
        return {
            'is_live': is_live,
            'confidence': confidence,
            'details': {
                'variation_score': variation_result['variation_score'],
                'variation_threshold': self.frame_variation_threshold,
                'avg_ear': blink_result['avg_ear'],
                'blink_threshold': self.blink_threshold
            },
            'message': message
        }
    
    def reset(self):
        """Reset history for new liveness check session."""
        self.frame_history = []
        self.ear_history = []
        self.blink_detected = False


def get_liveness_detector():
    """
    Get or create liveness detector (Streamlit session state).
    
    Returns:
        LivenessDetector: Initialized detector
    """
    if 'liveness_detector' not in st.session_state:
        st.session_state.liveness_detector = LivenessDetector()
    
    return st.session_state.liveness_detector


# ============================================================================
# INTERVIEW TALKING POINTS & FUTURE IMPROVEMENTS
# ============================================================================
"""
Current Implementation Notes:
- This MVP uses basic frame variation detection
- Production systems would use:
  * Pre-trained CNN models for liveness detection
  * Temporal analysis of facial landmarks
  * Texture analysis (CNNs detect photo textures)
  * Challenge-response (ask user to blink/turn head)

Known Limitations:
1. Cannot detect sophisticated deep fakes
2. May have false positives with static backgrounds
3. Requires multiple frames (not instant)
4. Not suitable for high-security applications

Production-Grade Alternatives:
1. Face Liveness Detection (TensorFlow Lite)
   - Pre-trained model: MobileNetV2-based
   - Fast inference on mobile devices

2. Challenge-Based:
   - Ask user to perform actions (blink, turn head)
   - Verify response in real-time

3. Passive Liveness:
   - Analyze facial texture (real vs. printed)
   - Detect micro-expressions
   - Temporal consistency checks

Future Improvements:
[ ] Implement facial landmark-based blink detection
[ ] Add challenge-response (blink/turn requests)
[ ] Integrate pre-trained liveness model (TensorFlow)
[ ] Add anti-spoofing specific CNN architecture
[ ] Implement attention score (face quality metrics)
"""
