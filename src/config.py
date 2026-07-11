import os

# Project Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_DIR = os.path.join(BASE_DIR, "models")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# Sliding Window and Model Configurations
FPS = 30 # Target FPS for uniform sequences
WINDOW_SIZE = 30 # Number of frames in a sequence (1 second of context)

# MediaPipe extracts 33 landmarks. 
# We'll use (x, y, z) for position, (vx, vy, vz) for velocity, and (ax, ay, az) for acceleration.
# So 33 * 3 * 3 = 297 dimensions.
FEATURE_DIM = 297 

# Model hyperparameters
HIDDEN_DIM = 64
NUM_CLASSES = 3 # 0: Normal, 1: Collapse, 2: Altercation
NUM_LAYERS = 2
BATCH_SIZE = 32
LEARNING_RATE = 0.001
NUM_EPOCHS = 50

# Actions/Labels
ACTIONS = ["Normal", "Collapse", "Altercation"]
