import os
import sys
import numpy as np
import torch
from torch.utils.data import Dataset

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import DATA_DIR, ACTIONS
from src.kinematics import calculate_kinematics

class PoseSequenceDataset(Dataset):
    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        self.samples = []
        self.labels = []
        
        # Load all file paths and labels
        for label_idx, action in enumerate(ACTIONS):
            action_dir = os.path.join(data_dir, action)
            if not os.path.exists(action_dir):
                continue
            for file_name in os.listdir(action_dir):
                if file_name.endswith('.npy'):
                    self.samples.append(os.path.join(action_dir, file_name))
                    self.labels.append(label_idx)
                    
    def __len__(self):
        return len(self.samples)
        
    def __getitem__(self, idx):
        file_path = self.samples[idx]
        label = self.labels[idx]
        
        # Load raw sequence of shape (WINDOW_SIZE, 33, 3)
        raw_sequence = np.load(file_path)
        
        # Calculate kinematics to get shape (WINDOW_SIZE, FEATURE_DIM)
        enhanced_sequence = calculate_kinematics(raw_sequence)
        
        # Convert to tensor
        features_tensor = torch.tensor(enhanced_sequence, dtype=torch.float32)
        label_tensor = torch.tensor(label, dtype=torch.long)
        
        return features_tensor, label_tensor
