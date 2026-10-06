import os
import sys
import cv2
import numpy as np
import torch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import WINDOW_SIZE, FEATURE_DIM, HIDDEN_DIM, NUM_LAYERS, NUM_CLASSES, ACTIONS, MODEL_DIR
from src.pose_extraction import PoseExtractor
from src.kinematics import calculate_kinematics
from src.model import BiLSTMActionRecognizer

class RealTimeInference:
    def __init__(self, model_path=None):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load model
        self.model = BiLSTMActionRecognizer(
            input_dim=FEATURE_DIM,
            hidden_dim=HIDDEN_DIM,
            num_layers=NUM_LAYERS,
            num_classes=NUM_CLASSES
        ).to(self.device)
        
        if model_path is None:
            model_path = os.path.join(MODEL_DIR, "best_model.pth")
            
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))
            self.model.eval()
            print(f"Loaded model from {model_path}")
        else:
            print(f"Warning: Model weights not found at {model_path}. Using random weights.")
            
        self.pose_extractor = PoseExtractor()
        
        # Sliding window buffer
        self.pose_sequence_buffer = []
        
    def process_frame(self, frame):
        """
        Process a single frame. Returns annotated frame, detected action (or None), and telemetry dict.
        """
        landmarks, annotated_frame = self.pose_extractor.extract_pose(frame)
        
        if landmarks is None:
            # If no person detected, optionally clear buffer or ignore
            # We'll just ignore for now to maintain continuous sequence if possible,
            # or we can clear if too long. For now, clear to be safe.
            self.pose_sequence_buffer.clear()
            return annotated_frame, "No Person", {"skeletons": 0, "velocity": "0.00m/s", "accel": "0.00g", "confidence": "0.0%"}
            
        self.pose_sequence_buffer.append(landmarks)
        
        if len(self.pose_sequence_buffer) > WINDOW_SIZE:
            self.pose_sequence_buffer.pop(0)
            
        if len(self.pose_sequence_buffer) == WINDOW_SIZE:
            # We have a full window
            sequence = np.array(self.pose_sequence_buffer) # Shape (WINDOW_SIZE, 33, 3)
            enhanced_features = calculate_kinematics(sequence) # Shape (WINDOW_SIZE, FEATURE_DIM)
            
            features_tensor = torch.tensor(enhanced_features, dtype=torch.float32).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(features_tensor)
                probs = torch.softmax(outputs, dim=1)
                conf, predicted = torch.max(probs.data, 1)
                action_idx = predicted.item()
                action_name = ACTIONS[action_idx]
                
                # Calculate real telemetry
                last_frame = enhanced_features[-1].reshape(33, 9)
                mean_vel = np.mean(np.linalg.norm(last_frame[:, 3:6], axis=1))
                mean_acc = np.mean(np.linalg.norm(last_frame[:, 6:9], axis=1))
                
                telemetry = {
                    "skeletons": 1,
                    "velocity": f"{mean_vel:.2f}m/s",
                    "accel": f"{mean_acc:.2f}g",
                    "confidence": f"{conf.item()*100:.1f}%"
                }
                
                return annotated_frame, action_name, telemetry
                
        return annotated_frame, "Buffering...", {"skeletons": 1, "velocity": "0.00m/s", "accel": "0.00g", "confidence": "0.0%"}
