import os
import sys
import subprocess

# Add modal dir to sys.path
sys.path.insert(0, os.path.abspath("modal"))
from ass_builder import generate_ass

os.makedirs("scratch/klap_previews", exist_ok=True)

test_configs = [
    {
        "preset": "bobby",
        "words": [
            {"word": "never", "start": 0.0, "end": 0.5},
            {"word": "laughed", "start": 0.5, "end": 1.0},
            {"word": "at", "start": 1.0, "end": 1.3},
            {"word": "anybody", "start": 1.3, "end": 2.0},
        ],
        "active_time": 0.2, # "never" is active (yellow)
    },
    {
        "preset": "tom",
        "words": [
            {"word": "THE", "start": 0.0, "end": 0.4},
            {"word": "ROOM", "start": 0.4, "end": 1.0},
            {"word": "AS", "start": 1.0, "end": 1.4},
            {"word": "IF", "start": 1.4, "end": 2.0},
        ],
        "active_time": 0.6, # "ROOM" is active (red pill)
    },
    {
        "preset": "casey",
        "words": [
            {"word": "I", "start": 0.0, "end": 0.3},
            {"word": "WANTED", "start": 0.3, "end": 0.8},
            {"word": "TO", "start": 0.8, "end": 1.1},
            {"word": "EXPLAIN", "start": 1.1, "end": 1.8},
        ],
        "active_time": 0.5, # orange outline
    },
    {
        "preset": "fred",
        "words": [
            {"word": "Every", "start": 0.0, "end": 0.4},
            {"word": "time", "start": 0.4, "end": 0.9},
            {"word": "he's", "start": 0.9, "end": 1.3},
            {"word": "writing,", "start": 1.3, "end": 2.0},
        ],
        "active_time": 0.6, # "time" is active (emerald green)
    },
    {
        "preset": "sara",
        "words": [
            {"word": "Because", "start": 0.0, "end": 0.5},
            {"word": "it's", "start": 0.5, "end": 1.0},
            {"word": "really", "start": 1.0, "end": 1.5},
            {"word": "the", "start": 1.5, "end": 2.0},
        ],
        "active_time": 0.7, # "it's" is active (orange pill)
    },
    {
        "preset": "billy",
        "words": [
            {"word": "when", "start": 0.0, "end": 0.4},
            {"word": "someone", "start": 0.4, "end": 0.9},
            {"word": "doesn't", "start": 0.9, "end": 1.4},
            {"word": "want", "start": 1.4, "end": 2.0},
        ],
        "active_time": 0.6, # top purple outline
    },
    {
        "preset": "unbox",
        "words": [
            {"word": "CREATE", "start": 0.0, "end": 0.5},
            {"word": "PRESSURE", "start": 0.5, "end": 1.1},
            {"word": "THAT", "start": 1.1, "end": 1.6},
        ],
        "active_time": 0.8, # "PRESSURE" is active (magenta pill)
    },
]

fonts_dir = os.path.abspath("fonts")

for cfg in test_configs:
    preset = cfg["preset"]
    ass_path = f"scratch/klap_previews/{preset}.ass"
    out_img = f"scratch/klap_previews/{preset}_preview.jpg"
    
    # Generate ASS
    generate_ass(
        transcript=cfg["words"],
        styling={"preset": preset},
        output_path=ass_path,
        crop_mode="reframe"
    )
    print(f"Generated {ass_path}")
    
    # Render with ffmpeg on a clean dark vertical canvas (1080x1920)
    # Using fontsdir
    t = cfg["active_time"]
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=0x1E1E24:s=1080x1920:d=3.0",
        "-vf", f"ass={ass_path}:fontsdir={fonts_dir}",
        "-ss", str(t),
        "-vframes", "1",
        out_img
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"Rendered {out_img}")

print("All 7 styles generated and rendered!")
