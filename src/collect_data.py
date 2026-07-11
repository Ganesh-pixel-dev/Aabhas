import os
import sys
import cv2
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import DATA_DIR, ACTIONS, WINDOW_SIZE
from src.pose_extraction import PoseExtractor

def collect_data(action_name, num_samples=50):
    if action_name not in ACTIONS:
        print(f"Error: {action_name} not in {ACTIONS}")
        return
        
    action_dir = os.path.join(DATA_DIR, action_name)
    os.makedirs(action_dir, exist_ok=True)
    
    # Start sample counter
    existing_samples = [f for f in os.listdir(action_dir) if f.endswith('.npy')]
    start_idx = len(existing_samples)
    
    pose_extractor = PoseExtractor()
    cap = cv2.VideoCapture(0)
    
    print(f"Collecting data for {action_name}")
    print("Press 's' to start recording a sequence, 'q' to quit.")
    
    collected = 0
    while collected < num_samples:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Preview mode
        _, annotated_frame = pose_extractor.extract_pose(frame)
        cv2.putText(annotated_frame, f"Ready to collect {action_name}. Collected: {collected}/{num_samples}", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        cv2.putText(annotated_frame, "Press 's' to record 1 sec sequence", 
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                    
        cv2.imshow("Data Collection", annotated_frame)
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord('s'):
            # Record sequence
            print("Recording sequence...")
            sequence = []
            frames_recorded = 0
            
            while frames_recorded < WINDOW_SIZE:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                landmarks, ann_frame = pose_extractor.extract_pose(frame)
                
                cv2.putText(ann_frame, f"Recording: {frames_recorded}/{WINDOW_SIZE}", 
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.imshow("Data Collection", ann_frame)
                cv2.waitKey(1)
                
                if landmarks is not None:
                    sequence.append(landmarks)
                    frames_recorded += 1
                else:
                    print("Lost person during recording! Restarting sequence...")
                    sequence = []
                    frames_recorded = 0
                    
            if len(sequence) == WINDOW_SIZE:
                file_path = os.path.join(action_dir, f"sample_{start_idx + collected:04d}.npy")
                np.save(file_path, np.array(sequence))
                print(f"Saved {file_path}")
                collected += 1
                
    cap.release()
    cv2.destroyAllWindows()
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python collect_data.py [ActionName]")
        print(f"Available actions: {ACTIONS}")
    else:
        collect_data(sys.argv[1])
