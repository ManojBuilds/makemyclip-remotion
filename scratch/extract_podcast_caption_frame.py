#!/usr/bin/env python3
import cv2

video_path = "downloads/result_podcast_reframe_captioned.mp4"
output_path = "scratch/podcast_caption_check.jpg"

cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS) or 23.976
# Extract frame at 8.4 seconds
frame_no = int(8.4 * fps)
cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)

ret, frame = cap.read()
if ret:
    cv2.imwrite(output_path, frame)
    print(f"✅ Extracted frame at 8.4s to {output_path}")
else:
    print("❌ Failed to extract frame")
cap.release()
