#!/usr/bin/env python3
import cv2

video_path = "downloads/result_course_presentation.mp4"
output_path = "/home/manoj-kumar/.gemini/antigravity/brain/65904057-9888-4b0d-89d3-5761a6d07c1e/course_vertical_frame.png"

cap = cv2.VideoCapture(video_path)
cap.set(cv2.CAP_PROP_POS_FRAMES, 100)
ret, frame = cap.read()
if ret:
    cv2.imwrite(output_path, frame)
    print(f"Saved vertical frame to {output_path}")
else:
    print("Failed to read frame")
cap.release()
