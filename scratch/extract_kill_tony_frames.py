#!/usr/bin/env python3
import os
import cv2

video_path = "downloads/result_kill_tony_reframe.mp4"
output_dir = "scratch/kill_tony_checks"
os.makedirs(output_dir, exist_ok=True)

cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

timestamps = [2.0, 5.0, 10.0, 15.0, 18.0]

for ts in timestamps:
    frame_no = int(ts * fps)
    if frame_no < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ret, frame = cap.read()
        if ret:
            out_file = os.path.join(output_dir, f"frame_{int(ts)}s.jpg")
            cv2.imwrite(out_file, frame)
            print(f"✅ Extracted frame at {ts}s to {out_file}")
        else:
            print(f"❌ Failed to read frame at {ts}s")
    else:
        print(f"⚠️ Timestamp {ts}s exceeds total frame count")

cap.release()
