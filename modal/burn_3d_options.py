import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../modal")))

from ass_builder import generate_ass
from burner import burn_captions_local
from presets import PRESET_STYLES
from test_on_black import preset_to_styling, CUSTOM_TRANSCRIPT

input_video = os.path.abspath("reframed_3s.mp4")
if not os.path.exists(input_video):
    input_video = os.path.abspath("reframed_stable_zoom_fixed.mp4")
output_dir = os.path.abspath("modal/test_outputs")
os.makedirs(output_dir, exist_ok=True)

# Base styling for bobby
styling = preset_to_styling("bobby", PRESET_STYLES["bobby"])
styling["stroke_width"] = 5.0

base_ass_path = os.path.join(output_dir, "bobby_base.ass")
generate_ass(
    transcript=CUSTOM_TRANSCRIPT,
    styling=styling,
    output_path=base_ass_path,
    crop_mode="reframe"
)

with open(base_ass_path, "r", encoding="utf-8") as f:
    base_ass_content = f.read()

# -------------------------------------------------------------
# Option 1: Solid 3D Diagonal Extrusion (Sharp offset down-right)
# -------------------------------------------------------------
ass_opt1_content = re.sub(
    r"\\xshad\d+(\.\d+)?\\yshad\d+(\.\d+)?\\blur\d+(\.\d+)?",
    r"\\xshad6\\yshad6\\blur0\\4c&H000000&\\4a&H00&",
    base_ass_content
)
# Make sure BackColour in Style is opaque black
ass_opt1_content = ass_opt1_content.replace("&HFF000000", "&H00000000")
opt1_ass = os.path.join(output_dir, "bobby_opt1_diagonal.ass")
with open(opt1_ass, "w", encoding="utf-8") as f:
    f.write(ass_opt1_content)

opt1_video = os.path.join(output_dir, "bobby_opt1_diagonal.mp4")
print("🎬 Burning Option 1 (3D Diagonal Extrusion)...")
burn_captions_local(
    local_video=input_video,
    local_output=opt1_video,
    transcript=CUSTOM_TRANSCRIPT,
    styling=styling,
    show_watermark=False,
    crop_mode="reframe",
    quality="export",
    tmpdir=output_dir,
    custom_ass_path=opt1_ass
)
print(f"✅ Option 1 ready: {opt1_video}")

# -------------------------------------------------------------
# Option 2: Pure Vertical 3D Drop (Straight Down)
# -------------------------------------------------------------
ass_opt2_content = re.sub(
    r"\\xshad\d+(\.\d+)?\\yshad\d+(\.\d+)?\\blur\d+(\.\d+)?",
    r"\\xshad0\\yshad8\\blur0\\4c&H000000&\\4a&H00&",
    base_ass_content
)
ass_opt2_content = ass_opt2_content.replace("&HFF000000", "&H00000000")
opt2_ass = os.path.join(output_dir, "bobby_opt2_vertical.ass")
with open(opt2_ass, "w", encoding="utf-8") as f:
    f.write(ass_opt2_content)

opt2_video = os.path.join(output_dir, "bobby_opt2_vertical.mp4")
print("🎬 Burning Option 2 (3D Vertical Drop)...")
burn_captions_local(
    local_video=input_video,
    local_output=opt2_video,
    transcript=CUSTOM_TRANSCRIPT,
    styling=styling,
    show_watermark=False,
    crop_mode="reframe",
    quality="export",
    tmpdir=output_dir,
    custom_ass_path=opt2_ass
)
print(f"✅ Option 2 ready: {opt2_video}")

# -------------------------------------------------------------
# Option 3: Multi-Layer Stacked 3D Block (True Dense 3D Wall)
# -------------------------------------------------------------
lines = base_ass_content.splitlines()
opt3_lines = []
dialogue_pattern = re.compile(r"^Dialogue:\s*(\d+),(.*?),(.*?),(.*?),(.*?),(.*?),(.*?),(.*?),(.*?),(.*)$")

for line in lines:
    match = dialogue_pattern.match(line)
    if not match:
        opt3_lines.append(line)
        continue
    
    layer, start, end, style, name, ml, mr, mv, effect, text = match.groups()
    
    # Extract pos(x, y)
    pos_match = re.search(r"\\pos\((\d+),(\d+)\)", text)
    if pos_match:
        px, py = int(pos_match.group(1)), int(pos_match.group(2))
        
        # Strip color tags for under-layers so entire silhouette is black
        clean_text_for_depth = re.sub(r"\\c&H[0-9A-Fa-f]+&", r"\\c&H000000&", text)
        clean_text_for_depth = re.sub(r"\\xshad\d+(\.\d+)?\\yshad\d+(\.\d+)?\\blur\d+(\.\d+)?", r"\\xshad0\\yshad0\\blur0", clean_text_for_depth)
        
        # Add extrusion layers at +8, +6, +4, +2
        for offset_y in [8, 6, 4, 2]:
            layer_text = clean_text_for_depth.replace(f"\\pos({px},{py})", f"\\pos({px},{py + offset_y})")
            opt3_lines.append(f"Dialogue: 0,{start},{end},{style},{name},{ml},{mr},{mv},{effect},{layer_text}")
    
    # Top front text at Layer 1
    top_text = re.sub(r"\\xshad\d+(\.\d+)?\\yshad\d+(\.\d+)?\\blur\d+(\.\d+)?", r"\\xshad0\\yshad0\\blur0", text)
    opt3_lines.append(f"Dialogue: 1,{start},{end},{style},{name},{ml},{mr},{mv},{effect},{top_text}")

opt3_ass = os.path.join(output_dir, "bobby_opt3_multilayer.ass")
with open(opt3_ass, "w", encoding="utf-8") as f:
    f.write("\n".join(opt3_lines))

opt3_video = os.path.join(output_dir, "bobby_opt3_multilayer.mp4")
print("🎬 Burning Option 3 (Multi-Layer Stacked 3D Block)...")
burn_captions_local(
    local_video=input_video,
    local_output=opt3_video,
    transcript=CUSTOM_TRANSCRIPT,
    styling=styling,
    show_watermark=False,
    crop_mode="reframe",
    quality="export",
    tmpdir=output_dir,
    custom_ass_path=opt3_ass
)
print(f"✅ Option 3 ready: {opt3_video}")
print("\n🎉 ALL 3 3D OPTIONS GENERATED SUCCESSFULLY!")
