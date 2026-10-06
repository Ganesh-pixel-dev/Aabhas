import cv2
from src.inference import RealTimeInference

def main():
    print("Starting Project Aabhas (Predictive Emergency Intent)...")
    inference = RealTimeInference()
    
    cap = cv2.VideoCapture(0) # Open default webcam
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return
        
    print("Press 'q' to quit.")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        annotated_frame, action = inference.process_frame(frame)
        
        # Draw text
        color = (0, 255, 0)
        if action == "Collapse" or action == "Altercation":
            color = (0, 0, 255) # Red for emergency
            
        cv2.putText(annotated_frame, f"Status: {action}", (10, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                    
        cv2.imshow("Project Aabhas", annotated_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
