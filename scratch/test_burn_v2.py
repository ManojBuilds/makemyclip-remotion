
import modal
import os

# Define the transcript from test_caption_burn.py
transcript = [
    {"word": "That's", "start": 0.005, "end": 1.045},
    {"word": "Jensen", "start": 0.39, "end": 0.79},
    {"word": "Huang.", "start": 0.79, "end": 1.43},
    {"word": "And", "start": 3.19, "end": 3.51},
    {"word": "whether", "start": 3.51, "end": 3.83},
    {"word": "you", "start": 3.83, "end": 3.99},
    {"word": "know", "start": 3.99, "end": 4.15},
    {"word": "it", "start": 4.15, "end": 4.31},
    {"word": "or", "start": 4.31, "end": 4.47},
    {"word": "not,", "start": 4.47, "end": 4.79},
    {"word": "his", "start": 4.79, "end": 4.95},
    {"word": "decisions", "start": 4.95, "end": 5.35},
    {"word": "are", "start": 5.35, "end": 5.75},
    {"word": "shaping", "start": 5.75, "end": 6.23},
    {"word": "your", "start": 6.23, "end": 6.63},
    {"word": "future.", "start": 6.63, "end": 7.11},
    {"word": "He's", "start": 7.11, "end": 7.35},
    {"word": "the", "start": 7.35, "end": 7.51},
    {"word": "CEO", "start": 7.51, "end": 7.83},
    {"word": "of", "start": 7.83, "end": 8.07},
    {"word": "NVIDIA,", "start": 8.07, "end": 8.71},
    {"word": "the", "start": 8.71, "end": 8.79},
    {"word": "company", "start": 8.79, "end": 9.03},
    {"word": "that", "start": 9.03, "end": 9.27},
    {"word": "skyrocketed", "start": 9.27, "end": 9.99},
    {"word": "over", "start": 9.99, "end": 10.23},
    {"word": "the", "start": 10.23, "end": 10.31},
    {"word": "past", "start": 10.31, "end": 10.55},
    {"word": "few", "start": 10.55, "end": 10.79},
    {"word": "years", "start": 10.79, "end": 11.03},
    {"word": "to", "start": 11.03, "end": 11.35},
    {"word": "become", "start": 11.35, "end": 11.67},
    {"word": "one", "start": 11.67, "end": 11.83},
    {"word": "of", "start": 11.83, "end": 11.91},
    {"word": "the", "start": 11.91, "end": 11.99},
    {"word": "most", "start": 11.99, "end": 12.23},
    {"word": "valuable", "start": 12.23, "end": 13.11},
    {"word": "companies", "start": 12.67, "end": 13.15},
    {"word": "in", "start": 13.15, "end": 13.31},
    {"word": "the", "start": 13.31, "end": 13.47},
    {"word": "world.", "start": 13.47, "end": 14.03},
]

# Style settings
styling = {
    "font_family": "THEBOLDFONT",
    "font_size": 28.0,
    "font_color": "#FFFFFF",
    "highlight_color": "#FFD700",
    "stroke_color": "#000000",
    "stroke_width": 2.0,
    "animation": "karaoke",  # Test the new karaoke wrapping
    "shadow": True,
    "position_y": 0.75,
    "uppercase": True
}

video_url = "https://pub-dab84dec13074258806f788a00943c46.r2.dev/reframes/orig_502ab25b-2441-4d28-8b25-a6fd6bf20a11.mp4"

# Connect to Modal and run the burner
try:
    print(f"Applying captions to {video_url}...")
    
    # We need to use the deployed app name
    f = modal.Cls.from_name("makemyclip-ai-rendering", "CaptionBurner")
    
    # Run the burn method
    # burn(self, video_url: str, transcript, styling, show_watermark: bool = False)
    result_url = f().burn.remote(video_url, transcript, styling, show_watermark=True)
    
    print(f"\nSUCCESS! Captioned video available at:\n{result_url}")
except Exception as e:
    print(f"\nFAILED: {e}")
