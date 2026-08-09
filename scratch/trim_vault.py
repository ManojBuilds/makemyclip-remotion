import os
import subprocess
import glob

vault_dir = "/home/manoj/Developer/makemyclip-remotion/vault"
mp4_files = sorted(glob.glob(os.path.join(vault_dir, "*.mp4")))

print(f"Found {len(mp4_files)} mp4 files in {vault_dir}:")

for filepath in mp4_files:
    filename = os.path.basename(filepath)
    temp_path = filepath + ".tmp.mp4"
    
    cmd = [
        "ffmpeg", "-y",
        "-ss", "0",
        "-i", filepath,
        "-t", "5",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        temp_path
    ]
    
    print(f"Trimming {filename} to 5s...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        os.replace(temp_path, filepath)
        # Probe new duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filepath
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True)
        dur = probe_res.stdout.strip()
        print(f"Successfully trimmed {filename} -> new duration: {dur}s")
    else:
        print(f"Error trimming {filename}: {res.stderr}")
        if os.path.exists(temp_path):
            os.remove(temp_path)

print("Done!")
