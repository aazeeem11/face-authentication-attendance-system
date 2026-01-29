"""
face_utils.py - Face Recognition & Registration Module

This module handles:
1. Face detection using dlib/face_recognition
2. Face embedding generation (128-D vectors)
3. Face registration and storage
4. Face identification/matching

Key Concepts:
- Face embeddings: 128-dimensional vectors that represent unique facial features
- Tolerance/Distance: Measures similarity between two faces (lower = more similar)
- Encoding: Process of converting a face image to an embedding

Interview Talking Points:
- Why embeddings? They're robust to lighting, angles, and expressions
- Why 128-D? It's proven to capture sufficient variation for face identification
- Distance metric: Euclidean distance is used to compare embeddings
"""

import os
import pickle
import numpy as np
import face_recognition
import cv2
import streamlit as st


class FaceRecognitionEngine:
    """
    Manages face registration, encoding, and recognition.
    
    Attributes:
        encodings_path (str): Path to stored face encodings pickle file
        tolerance (float): Maximum distance for face match (lower = stricter)
    """
    
    def __init__(self, encodings_path="data/encodings.pkl", tolerance=0.6):
        """
        Initialize the face recognition engine.
        
        Args:
            encodings_path (str): Path to save/load face encodings
            tolerance (float): Distance threshold for matching (0.6 is standard)
        """
        self.encodings_path = encodings_path
        self.tolerance = tolerance
        self.known_faces = {}
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(encodings_path), exist_ok=True)
        
        # Load existing encodings if available
        self.load_encodings()
    
    def load_encodings(self):
        """
        Load previously saved face encodings from pickle file.
        
        The pickle file stores a dictionary:
        - keys: user names
        - values: list of 128-D numpy arrays (encodings)
        """
        try:
            if os.path.exists(self.encodings_path):
                with open(self.encodings_path, 'rb') as f:
                    self.known_faces = pickle.load(f)
        except Exception as e:
            st.warning(f"⚠️ Could not load encodings: {str(e)}")
            self.known_faces = {}
    
    def save_encodings(self):
        """
        Save current face encodings to pickle file.
        
        This persists registered faces so they can be recognized later.
        """
        try:
            os.makedirs(os.path.dirname(self.encodings_path), exist_ok=True)
            with open(self.encodings_path, 'wb') as f:
                pickle.dump(self.known_faces, f)
        except Exception as e:
            st.error(f"❌ Error saving encodings: {str(e)}")
    
    def detect_faces(self, image_rgb):
        """
        Detect faces in an image using dlib's HOG face detector.
        
        Args:
            image_rgb (np.ndarray): Image in RGB format
            
        Returns:
            list: Face locations as [(top, right, bottom, left), ...]
        """
        try:
            # Use dlib's CNN or HOG detector
            # HOG is faster, CNN is more accurate
            face_locations = face_recognition.face_locations(
                image_rgb, 
                model='hog'  # Use 'cnn' for higher accuracy but slower
            )
            return face_locations
        except Exception as e:
            st.error(f"❌ Error detecting faces: {str(e)}")
            return []
    
    def generate_encoding(self, image_rgb, face_location):
        """
        Generate a 128-D face embedding for a detected face.
        
        Args:
            image_rgb (np.ndarray): Image in RGB format
            face_location (tuple): Face location (top, right, bottom, left)
            
        Returns:
            np.ndarray: 128-D face encoding or None if error
        """
        try:
            encodings = face_recognition.face_encodings(
                image_rgb,
                [face_location],
                num_jitters=1  # Number of times to resample (1=fast, 10=accurate)
            )
            
            if len(encodings) > 0:
                return encodings[0]
            return None
        except Exception as e:
            st.error(f"❌ Error generating encoding: {str(e)}")
            return None
    
    def register_face(self, image_rgb, user_name):
        """
        Register a new user's face or add a new encoding to an existing user.
        
        Steps:
        1. Detect face in image
        2. Validate exactly one face is present
        3. Generate face encoding
        4. Store encoding with user name
        
        Args:
            image_rgb (np.ndarray): Image in RGB format
            user_name (str): Name of the user being registered
            
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'encoding': np.ndarray or None
            }
        """
        # Detect faces
        face_locations = self.detect_faces(image_rgb)
        
        # Validation: Exactly one face must be present
        if len(face_locations) == 0:
            return {
                'success': False,
                'message': '❌ No face detected. Please position your face clearly.',
                'encoding': None
            }
        
        if len(face_locations) > 1:
            return {
                'success': False,
                'message': f'❌ Multiple faces detected ({len(face_locations)}). Register one face at a time.',
                'encoding': None
            }
        
        # Generate encoding for the detected face
        face_location = face_locations[0]
        encoding = self.generate_encoding(image_rgb, face_location)
        
        if encoding is None:
            return {
                'success': False,
                'message': '❌ Could not generate face encoding. Try again.',
                'encoding': None
            }
        
        # If user already exists, append the new encoding. Otherwise, create a new entry.
        if user_name in self.known_faces:
            self.known_faces[user_name].append(encoding)
            message = f'✅ Added new face scan for "{user_name}"!'
        else:
            self.known_faces[user_name] = [encoding]
            message = f'✅ Face registered successfully for "{user_name}"!'
            
        # Persist to disk
        self.save_encodings()
        
        return {
            'success': True,
            'message': message,
            'encoding': encoding
        }
    
    def recognize_face(self, image_rgb):
        """
        Identify a face in the image by comparing with known encodings.
        
        Algorithm:
        1. Detect face in image
        2. Generate encoding for detected face
        3. Compare with all known encodings for all users
        4. If the best match distance < tolerance, return the user's name
        
        Args:
            image_rgb (np.ndarray): Image in RGB format
            
        Returns:
            dict: {
                'success': bool,
                'name': str or None,
                'confidence': float (0-1),
                'message': str,
                'distances': [float, ...] (for debugging)
            }
        """
        # Detect faces
        face_locations = self.detect_faces(image_rgb)
        
        if len(face_locations) == 0:
            return {
                'success': False,
                'name': None,
                'confidence': 0.0,
                'message': '❌ No face detected.',
                'distances': []
            }
        
        if len(face_locations) > 1:
            return {
                'success': False,
                'name': None,
                'confidence': 0.0,
                'message': f'❌ Multiple faces detected. Please show one face at a time.',
                'distances': []
            }
        
        # If no registered users
        if not self.known_faces:
            return {
                'success': False,
                'name': None,
                'confidence': 0.0,
                'message': '❌ No registered users. Please register faces first.',
                'distances': []
            }
        
        # Generate encoding for the detected face
        face_location = face_locations[0]
        unknown_encoding = self.generate_encoding(image_rgb, face_location)
        
        if unknown_encoding is None:
            return {
                'success': False,
                'name': None,
                'confidence': 0.0,
                'message': '❌ Could not generate face encoding.',
                'distances': []
            }
        
        # Prepare a flat list of all known encodings and their corresponding names
        all_known_encodings = []
        all_known_names = []
        for name, encodings in self.known_faces.items():
            for encoding in encodings:
                all_known_encodings.append(encoding)
                all_known_names.append(name)

        # Compare with all known encodings
        distances = face_recognition.face_distance(
            all_known_encodings,
            unknown_encoding
        )
        
        # Find the closest match
        if len(distances) == 0:
            return {
                'success': False,
                'name': None,
                'confidence': 0.0,
                'message': '❌ No known faces to compare against.',
                'distances': []
            }

        best_match_idx = np.argmin(distances)
        best_distance = distances[best_match_idx]
        
        # Check if best match is within tolerance
        if best_distance < self.tolerance:
            matched_name = all_known_names[best_match_idx]
            # Convert distance to confidence (inverse relationship)
            confidence = 1 - (best_distance / self.tolerance)
            
            return {
                'success': True,
                'name': matched_name,
                'confidence': confidence,
                'message': f'✅ Recognized as "{matched_name}"!',
                'distances': distances.tolist()
            }
        else:
            return {
                'success': False,
                'name': None,
                'confidence': 0.0,
                'message': f'❌ Face not recognized (distance: {best_distance:.3f})',
                'distances': distances.tolist()
            }
    
    def get_registered_users(self):
        """
        Get list of all registered users.
        
        Returns:
            list: List of unique user names
        """
        return list(self.known_faces.keys())
    
    def get_user_count(self):
        """
        Get total number of registered users.
        
        Returns:
            int: Number of unique registered users
        """
        return len(self.known_faces)
    
    def get_user_encoding_count(self, user_name):
        """
        Get the number of encodings for a specific user.
        
        Returns:
            int: Number of encodings for the user
        """
        if user_name in self.known_faces:
            return len(self.known_faces[user_name])
        return 0

    def delete_user(self, user_name):
        """
        Delete a registered user.
        
        Args:
            user_name (str): Name of the user to delete
            
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        if user_name in self.known_faces:
            del self.known_faces[user_name]
            self.save_encodings()
            return {
                'success': True,
                'message': f'✅ User "{user_name}" deleted successfully.'
            }
        else:
            return {
                'success': False,
                'message': f'❌ User "{user_name}" not found.'
            }


def get_recognition_engine():
    """
    Get or create face recognition engine (Streamlit session state).
    
    This ensures a single engine instance across the entire Streamlit app.
    
    Returns:
        FaceRecognitionEngine: Initialized engine
    """
    if 'recognition_engine' not in st.session_state:
        st.session_state.recognition_engine = FaceRecognitionEngine()
    
    return st.session_state.recognition_engine
