import numpy as np

def calculate_kinematics(pose_sequence, fps=30):
    """
    Calculates velocity and acceleration for a sequence of poses.
    
    Args:
        pose_sequence (np.ndarray): Shape (T, 33, 3), where T is sequence length.
        fps (int): Frames per second to calculate real time derivatives.
        
    Returns:
        np.ndarray: Enhanced feature sequence of shape (T, 297)
                    containing [x, y, z, vx, vy, vz, ax, ay, az] flattened for each joint.
    """
    T, num_joints, dims = pose_sequence.shape
    dt = 1.0 / fps
    
    # Calculate velocity: dx/dt
    velocity = np.zeros_like(pose_sequence)
    if T > 1:
        velocity[1:] = (pose_sequence[1:] - pose_sequence[:-1]) / dt
    
    # Calculate acceleration: dv/dt
    acceleration = np.zeros_like(pose_sequence)
    if T > 2:
        acceleration[2:] = (velocity[2:] - velocity[1:-1]) / dt
    
    # Concatenate features
    # Shape: (T, 33, 9) -> flatten to (T, 297)
    enhanced_features = np.concatenate([pose_sequence, velocity, acceleration], axis=2)
    return enhanced_features.reshape(T, -1)
