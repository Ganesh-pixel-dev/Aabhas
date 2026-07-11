import os
import sys
import argparse
import cv2
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import DATA_DIR, ACTIONS, WINDOW_SIZE
from src.pose_extraction import PoseExtractor

def process_videos(input_dir, action_name, overlap=0.5):
    """
    Process all videos in input_dir and extract skeletal sequences.
    
    Args:
        input_dir (str): Directory containing .mp4 or .avi files.
        action_name (str): Label for these videos (e.g., 'Collapse', 'Normal').
        overlap (float): Fraction of WINDOW_SIZE to overlap between extracted sequences (0 to 1).
    """
    if action_name not in ACTIONS:
        print(f"Error: {action_name} not in {ACTIONS}")
        return
        
    if not os.path.isdir(input_dir):
        print(f"Error: Directory {input_dir} not found.")
        return
        
    action_dir = os.path.join(DATA_DIR, action_name)
    os.makedirs(action_dir, exist_ok=True)
    
    existing_samples = [f for f in os.listdir(action_dir) if f.endswith('.npy')]
    sample_idx = len(existing_samples)
    
    pose_extractor = PoseExtractor()
    step_size = max(1, int(WINDOW_SIZE * (1.0 - overlap)))
    
    video_files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
    
    print(f"Found {len(video_files)} videos in {input_dir}.")
    print(f"Saving extracted sequences to {action_dir}...")
    
    for video_file in video_files:
        video_path = os.path.join(input_dir, video_file)
        print(f"Processing {video_file}...")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Failed to open {video_file}")
            continue
            
        sequence_buffer = []
        frames_processed = 0
        sequences_extracted = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            landmarks, _ = pose_extractor.extract_pose(frame)
            frames_processed += 1
            
            if landmarks is not None:
                sequence_buffer.append(landmarks)
            else:
                # If no person is found, clear buffer to ensure contiguous tracking
                sequence_buffer.clear()
                
            if len(sequence_buffer) == WINDOW_SIZE:
                # We have a full sequence, save it
                file_path = os.path.join(action_dir, f"sample_{sample_idx:04d}.npy")
                np.save(file_path, np.array(sequence_buffer))
                sample_idx += 1
                sequences_extracted += 1
                
                # Shift buffer by step_size to create overlapping sequences
                sequence_buffer = sequence_buffer[step_size:]
                
        cap.release()
        print(f"Finished {video_file}. Extracted {sequences_extracted} sequences.")
        
    print(f"Total samples now available for {action_name}: {sample_idx}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract training sequences from a directory of videos.")
    parser.add_argument("input_dir", type=str, help="Directory containing raw video files.")
    parser.add_argument("action", type=str, choices=ACTIONS, help="The target action class for these videos.")
    parser.add_argument("--overlap", type=float, default=0.5, help="Overlap ratio between sequences (0.0 to 0.99).")
    
    args = parser.parse_args()
    process_videos(args.input_dir, args.action, args.overlap)
