#!/usr/bin/env python3
import sys
import os
import numpy as np

# Add modal directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))

from reframer import AIReframe, slice_tracks_and_scores, annotate_transcript_layout
from ass_builder import generate_ass

def run_tests():
    print("--- Testing Scene-Level Layout Classification & Transcript Annotation ---")
    
    # 1. Test slice_tracks_and_scores
    tracks = [
        {
            "track": {
                "frame": np.array([0, 1, 2, 10, 11, 12])
            },
            "proc_track": {
                "x": np.array([100.0, 101.0, 102.0, 200.0, 201.0, 202.0]),
                "y": np.array([100.0, 101.0, 102.0, 200.0, 201.0, 202.0]),
                "s": np.array([50.0, 50.0, 50.0, 60.0, 60.0, 60.0]),
            }
        }
    ]
    scores = [np.array([0.5, 0.6, 0.5, 0.4, 0.5, 0.4])]
    
    # Slice for frame range [0, 5)
    scene_tr, scene_sc = slice_tracks_and_scores(tracks, scores, 0, 5)
    assert len(scene_tr) == 1
    assert np.array_equal(scene_tr[0]["track"]["frame"], np.array([0, 1, 2]))
    assert np.array_equal(scene_tr[0]["proc_track"]["x"], np.array([100.0, 101.0, 102.0]))
    assert np.array_equal(scene_sc[0], np.array([0.5, 0.6, 0.5]))
    print("✅ slice_tracks_and_scores works perfectly!")

    # 2. Test annotate_transcript_layout
    frame_layout = ["single"] * 10 + ["split"] * 10 + ["letterbox"] * 10
    transcript = [
        {
            "words": [
                {"word": "hello", "start": 0.1, "end": 0.3},      # frame index = 0.1 * 25 = 2 -> single/reframe
                {"word": "world", "start": 0.5, "end": 0.8},      # frame index = 0.5 * 25 = 12 -> split
                {"word": "test", "start": 0.9, "end": 1.2},       # frame index = 0.9 * 25 = 22 -> letterbox
            ]
        }
    ]
    
    annotated = annotate_transcript_layout(transcript, frame_layout, "auto", fps=25)
    words = annotated[0]["words"]
    
    assert words[0]["layout"] == "reframe"
    assert words[1]["layout"] == "split"
    assert words[2]["layout"] == "letterbox"
    print("✅ annotate_transcript_layout works perfectly!")

    # 3. Test generate_ass with dynamic positioning
    output_ass = "scratch/test_dynamic_pos.ass"
    styling = {
        "preset": "simple",
        "font_color": "#FFFFFF",
        "font_size": 24,
        "position_y": 0.8, # default bottom
    }
    
    # Generate ASS file using the annotated transcript
    # Using words_per_phrase=1 so each word is in its own event
    styling["max_words"] = 1
    generate_ass(annotated, styling, output_ass, crop_mode="auto")
    
    # Read the generated ASS file and verify the positioning tags
    with open(output_ass, "r") as f:
        ass_content = f.read()
    
    print("\nGenerated ASS events:")
    for line in ass_content.splitlines():
        if line.startswith("Dialogue:"):
            print(line)
            # Verify that \pos is injected with the correct layout-specific coordinates
            # split/course -> position_y = 0.50 -> 0.50 * 1920 = 960 -> 960 + 38/2.0 = 979
            # letterbox -> position_y = 0.66 -> 0.66 * 1920 = 1267 -> 1267 + 38/2.0 = 1286
            # reframe/default -> position_y = 0.75 -> 0.75 * 1920 = 1440 -> 1440 + 38/2.0 = 1459
            if "hello" in line.lower():
                assert "\\pos(540,1459)" in line
            elif "world" in line.lower():
                assert "\\pos(540,979)" in line
            elif "test" in line.lower():
                assert "\\pos(540,1286)" in line
                
    print("\n✅ generate_ass dynamically resolved Y-positions correctly!")

    # Clean up
    if os.path.exists(output_ass):
        os.remove(output_ass)

if __name__ == "__main__":
    run_tests()
