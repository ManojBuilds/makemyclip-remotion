#!/usr/bin/env python3
import sys
import os
import numpy as np

# Add modal directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))

from reframer import AIReframe

class MockLogger:
    def info(self, msg, *args):
        print(f"[INFO] {msg % args}")
    def warning(self, msg, *args):
        print(f"[WARNING] {msg % args}")

# Replace the logger in reframer with our mock logger for test output readability
import reframer
reframer.logger = MockLogger()

def make_mock_track(xs, ys, ss):
    return {
        "proc_track": {
            "x": np.array(xs, dtype=float),
            "y": np.array(ys, dtype=float),
            "s": np.array(ss, dtype=float)
        }
    }

def run_tests():
    reframe_inst = AIReframe()
    width = 1280
    height = 720

    print("--- Test Case 1: No valid tracks (noise filtering check) ---")
    # Empty tracks
    tracks = []
    scores = []
    assert reframe_inst.classify_layout(tracks, scores, width, height) == "letterbox"

    # Tracks present but fail ASD score and movement thresholds
    tracks = [
        make_mock_track([100.0, 100.0, 100.1], [100.0, 100.0, 100.1], [50.0, 50.0, 50.0])
    ]
    scores = [np.array([0.02, 0.03, 0.02])] # below 0.1 score and movement standard dev sum is < 1.5
    layout = reframe_inst.classify_layout(tracks, scores, width, height)
    print(f"Result: {layout}")
    assert layout == "letterbox"

    print("\n--- Test Case 2: One valid track (reframe crop) ---")
    tracks = [
        make_mock_track([640.0, 642.0, 645.0], [360.0, 362.0, 360.0], [200.0, 201.0, 202.0]) # centered, large face
    ]
    scores = [np.array([0.4, 0.5, 0.6])] # high speaker score
    layout = reframe_inst.classify_layout(tracks, scores, width, height)
    print(f"Result: {layout}")
    assert layout == "reframe"

    print("\n--- Test Case 3: One valid track (course corner zoom layout) ---")
    # Small face in bottom-left corner
    tracks = [
        make_mock_track([120.0, 120.0, 122.0], [600.0, 600.0, 601.0], [80.0, 80.0, 80.0])
    ]
    scores = [np.array([0.3, 0.4, 0.3])]
    layout = reframe_inst.classify_layout(tracks, scores, width, height)
    print(f"Result: {layout}")
    assert layout == "course"

    print("\n--- Test Case 4: Two valid tracks (split layout horizontal separation) ---")
    # One speaker on left, one on right
    tracks = [
        make_mock_track([300.0, 301.0], [360.0, 360.0], [150.0, 150.0]),
        make_mock_track([980.0, 981.0], [360.0, 360.0], [150.0, 150.0])
    ]
    scores = [np.array([0.5, 0.5]), np.array([0.4, 0.4])]
    layout = reframe_inst.classify_layout(tracks, scores, width, height)
    print(f"Result: {layout}")
    assert layout == "split"

    print("\n--- Test Case 5: Two valid tracks close to center/overlapping (letterbox) ---")
    # Both speakers near center (no clear horizontal separation)
    tracks = [
        make_mock_track([600.0, 601.0], [360.0, 360.0], [150.0, 150.0]),
        make_mock_track([680.0, 681.0], [360.0, 360.0], [150.0, 150.0])
    ]
    scores = [np.array([0.5, 0.5]), np.array([0.4, 0.4])]
    layout = reframe_inst.classify_layout(tracks, scores, width, height)
    print(f"Result: {layout}")
    assert layout == "letterbox"

    print("\n--- Test Case 6: Three valid tracks (letterbox) ---")
    tracks = [
        make_mock_track([300.0, 301.0], [360.0, 360.0], [150.0, 150.0]),
        make_mock_track([640.0, 641.0], [360.0, 360.0], [150.0, 150.0]),
        make_mock_track([980.0, 981.0], [360.0, 360.0], [150.0, 150.0])
    ]
    scores = [np.array([0.5, 0.5]), np.array([0.4, 0.4]), np.array([0.3, 0.3])]
    layout = reframe_inst.classify_layout(tracks, scores, width, height)
    print(f"Result: {layout}")
    assert layout == "letterbox"

    print("\n🎉 All tests passed successfully!")

if __name__ == "__main__":
    run_tests()
