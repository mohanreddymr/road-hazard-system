import cv2
import numpy as np

class MotionDetector:
    
    def __init__(self):
        # Store the previous frame for comparison
        self.prev_frame = None
        
        # Minimum area to consider as real motion
        # (filters out tiny noise/shadows)
        self.min_area = 500
        
        # Motion threshold — how different must pixels be?
        self.threshold = 25
        
        print("Motion Detector initialized.")
    
    def detect(self, frame):
        """
        Takes one frame, compares with previous frame.
        Returns: motion_score, vertical_movement, annotated_frame
        """
        
        # Convert frame to grayscale
        # (we don't need color for motion detection)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Blur slightly to reduce noise
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        # First frame — nothing to compare yet
        if self.prev_frame is None:
            self.prev_frame = gray
            return 0, 0, frame
        
        # Calculate difference between current and previous frame
        frame_diff = cv2.absdiff(self.prev_frame, gray)
        
        # Make the difference more visible
        # (pixels below threshold become 0, above become 255)
        _, thresh = cv2.threshold(
            frame_diff, self.threshold, 255, cv2.THRESH_BINARY
        )
        
        # Expand the white areas slightly
        # (connects nearby motion pixels together)
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        # Find contours (outlines of moving regions)
        contours, _ = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Variables to track motion
        motion_score = 0
        vertical_movement = 0
        annotated_frame = frame.copy()
        
        # Loop through each detected moving region
        for contour in contours:
            
            # Skip tiny regions — probably just noise
            if cv2.contourArea(contour) < self.min_area:
                continue
            
            # Get bounding box around moving region
            x, y, w, h = cv2.boundingRect(contour)
            
            # Draw green box around moving object
            cv2.rectangle(
                annotated_frame,
                (x, y),           # top-left corner
                (x+w, y+h),       # bottom-right corner
                (0, 255, 0),      # green color
                2                 # line thickness
            )
            
            # Calculate motion score (size of moving area)
            motion_score += cv2.contourArea(contour)
            
            # Calculate vertical movement
            # (center Y position of the moving object)
            center_y = y + h // 2
            vertical_movement += center_y
        
        # Update previous frame for next comparison
        self.prev_frame = gray
        
        # Normalize motion score
        motion_score = round(motion_score / 1000, 2)
        
        return motion_score, vertical_movement, annotated_frame