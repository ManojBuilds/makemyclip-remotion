#!/usr/bin/env python3
import cv2

video_path = "downloads/result_course_presentation_captioned.mp4"
output_path = "scratch/course_caption_check.jpg"

cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
# Extract frame at 5.5 seconds
frame_no = int(5.5 * fps)
cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)

ret, frame = cap.read()
if ret:
    cv2.imwrite(output_path, frame)
    print(f"✅ Extracted frame at 5.5s to {output_path}")
else:
    print("❌ Failed to extract frame")
cap.release()
