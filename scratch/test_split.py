"""Test split_grid layout reframe directly using the existing uploaded R2 URL."""
import requests

MODAL_ENDPOINT = "https://ms8460149--makemyclip-ai-rendering-aireframe-reframe.modal.run"
public_url = "https://pub-dab84dec13074258806f788a00943c46.r2.dev/vault/yt_interview_5s.mp4"

payload = {
    "video_url": public_url,
    "start_time": 0.0,
    "end_time": 5.0,
    "fps": 25,
    "styling": None,
    "transcript": None,
    "show_watermark": False,
    "crop_mode": "split_grid",
}

print(f"Sending reframe request to {MODAL_ENDPOINT} with crop_mode='split_grid'...")
print(f"Video URL: {public_url}")

response = requests.post(MODAL_ENDPOINT, json=payload, timeout=600)
if response.status_code != 200:
    print(f"Error! Status: {response.status_code}")
    print(response.text)
    exit(1)

result = response.json()
print(f"\nModal Response:")
for k, v in result.items():
    print(f"  {k}: {v}")

if result.get("success"):
    reframed_url = result.get("original_video_url")
    output_path = "/home/manoj/Developer/makemyclip-remotion/downloads/yt_interview_split_grid_output.mp4"
    print(f"\nDownloading result to {output_path}...")
    try:
        r = requests.get(reframed_url, stream=True, timeout=60)
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"✅ Done! crop_mode: {result.get('crop_mode')}")
        print(f"   Saved to: {output_path}")
    except Exception as e:
        print(f"Download failed: {e}")
