#!/usr/bin/env python3
import cv2

video_path = "downloads/result_panel_letterbox.mp4"
output_path = "scratch/panel_raw_frame.jpg"

cap = cv2.VideoCapture(video_path)
ret, frame = cap.read()
if ret:
    cv2.imwrite(output_path, frame)
    print(f"✅ Extracted frame to {output_path}")
else:
    print("❌ Failed to extract frame")
cap.release()
