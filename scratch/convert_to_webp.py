import os
import subprocess

def convert_all():
    input_dir = "test_outputs"
    output_dir = "public/previews"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all .mp4 files that match black_template_*.mp4
    files = [f for f in os.listdir(input_dir) if f.startswith("black_template_") and f.endswith(".mp4")]
    
    for f in files:
        input_path = os.path.join(input_dir, f)
        # Change extension to .webp
        name_without_ext = os.path.splitext(f)[0]
        output_path = os.path.join(output_dir, f"{name_without_ext}.webp")
        
        print(f"🎬 Converting {input_path} to {output_path}...")
        
        # ffmpeg command to convert to animated webp.
        # We scale the vertical video down to width 360 (retaining aspect ratio 360x640)
        # Using -loop 0 for infinite loop.
        # qscale 80 for high quality WebP.
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vcodec", "libwebp",
            "-filter_complex", "[0:v] fps=15,scale=360:-1:flags=lanczos[v]",
            "-map", "[v]",
            "-loop", "0",
            "-qscale", "75",
            "-preset", "default",
            "-an",
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"✅ Successfully converted to {output_path} (Size: {os.path.getsize(output_path) / 1024:.1f} KB)")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to convert {f}: {e.stderr}")

if __name__ == "__main__":
    convert_all()
