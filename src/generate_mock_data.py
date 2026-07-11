import os
import sys
import numpy as np

# Add parent directory to path so we can import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import DATA_DIR, WINDOW_SIZE, ACTIONS

def generate_synthetic_data(num_samples_per_class=100):
    """
    Generates dummy data for testing the training pipeline.
    """
    print(f"Generating synthetic data in {DATA_DIR}...")
    
    for action in ACTIONS:
        action_dir = os.path.join(DATA_DIR, action)
        os.makedirs(action_dir, exist_ok=True)
        
    for class_idx, action in enumerate(ACTIONS):
        for i in range(num_samples_per_class):
            # Generate random base pose
            base_pose = np.random.randn(33, 3)
            sequence = [base_pose]
            for frame_idx in range(WINDOW_SIZE - 1):
                # Add small noise for temporal consistency
                step = np.random.randn(33, 3) * 0.05
                
                # If collapse, add huge downward velocity in y-axis at halfway point
                if action == "Collapse" and frame_idx > WINDOW_SIZE // 2:
                    step[:, 1] += 0.5 # MediaPipe y-axis goes down
                    
                # If altercation, add rapid erratic movements
                elif action == "Altercation":
                    step *= 3.0
                    
                next_pose = sequence[-1] + step
                sequence.append(next_pose)
                
            sequence = np.array(sequence) # Shape (WINDOW_SIZE, 33, 3)
            
            # Save sequence as npy
            file_path = os.path.join(DATA_DIR, action, f"sample_{i:04d}.npy")
            np.save(file_path, sequence)
            
    print("Synthetic data generation complete!")

if __name__ == "__main__":
    generate_synthetic_data()
