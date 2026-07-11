import os
import sys
import cv2
import psutil
from flask import Flask, render_template, Response, jsonify

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.inference import RealTimeInference

app = Flask(__name__)
inference = RealTimeInference()
camera = cv2.VideoCapture(0)

# Global state to keep track of current action
current_action = "Buffering..."
current_telemetry = {"skeletons": 0, "velocity": "0.00m/s", "accel": "0.00g", "confidence": "0.0%"}

def gen_frames():
    global current_action, current_telemetry
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            annotated_frame, action, telemetry = inference.process_frame(frame)
            current_action = action
            current_telemetry = telemetry
            
            # Encode frame to JPEG
            ret, buffer = cv2.imencode('.jpg', annotated_frame)
            frame_bytes = buffer.tobytes()
            
            # Yield as multipart
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify({
        "status": current_action,
        "cpu": psutil.cpu_percent(interval=None),
        "ram": psutil.virtual_memory().percent,
        "telemetry": current_telemetry
    })

if __name__ == '__main__':
    print("Starting Project Aabhas Web Dashboard...")
    app.run(host='0.0.0.0', port=5000, debug=False)
