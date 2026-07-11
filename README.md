# Project Aabhas: Predictive Emergency Intent System

Project Aabhas is an AI-powered security and monitoring web application designed to analyze live video feeds in real time. Rather than just recording video like a standard security camera, it actively "watches" the footage to understand human behavior and predict potential emergencies or specific intents.

## Key Features

- **Live Video Monitoring:** The dashboard provides a continuous live stream (CAM 1).
- **Real-Time Action Analysis:** The AI categorizes the current activity and displays the status with a confidence score.
- **Live Telemetry & Tracking:** Tracks the number of targets (people/skeletons) in the frame and calculates physical metrics like velocity and acceleration.
- **Event Logging:** A real-time event log keeps a historical timeline of system statuses and detected events.

## How to Run

1. Clone the repository.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python app.py
   ```
4. Open your web browser and navigate to `http://localhost:5000`.

*Note: Ensure your webcam is available and not in use by another application.*
