import cv2
import mediapipe as mp
import numpy as np

class PoseExtractor:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils

    def extract_pose(self, frame):
        """
        Extracts 3D pose landmarks from an image frame.
        Returns:
            landmarks (np.ndarray): Shape (33, 3) representing x, y, z for each joint.
                                    Returns None if no pose is detected.
            annotated_frame (np.ndarray): Frame with drawn landmarks.
        """
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(image_rgb)
        
        landmarks = None
        if results.pose_world_landmarks:
            landmarks = np.zeros((33, 3))
            for i, lm in enumerate(results.pose_world_landmarks.landmark):
                landmarks[i] = [lm.x, lm.y, lm.z]
                
        annotated_frame = frame.copy()
        if results.pose_landmarks:
            self.mp_drawing.draw_landmarks(
                annotated_frame, 
                results.pose_landmarks, 
                self.mp_pose.POSE_CONNECTIONS
            )
            
        return landmarks, annotated_frame
