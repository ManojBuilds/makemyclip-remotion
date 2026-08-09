import json
import os
import subprocess

vault_json_path = "/home/manoj/Developer/makemyclip-remotion/video_vault.json"
output_dir = "/home/manoj/Developer/makemyclip-remotion/vault"

os.makedirs(output_dir, exist_ok=True)

with open(vault_json_path, "r") as f:
    vault = json.load(f)


def probe_duration(path):
    """Return actual duration (seconds) of a downloaded file via ffprobe, or None on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


for category, data in vault.items():
    url = data["url"]
    seg = data["segment"]
    start = seg["start_seconds"]
    end = seg["end_seconds"]
    expected_duration = end - start
    out_file = os.path.join(output_dir, f"{category}.mp4")

    print(f"\nDownloading section for {category} ({start}s to {end}s, "
          f"expected {expected_duration}s) from {url}...")

    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--download-sections", f"*{start}-{end}",
        "--force-keyframes-at-cuts",
        "-o", out_file,
        url,
    ]

    success = False
    try:
        subprocess.run(cmd, check=True)
        success = True
    except subprocess.CalledProcessError as e:
        print(f"Error downloading {category}: {e}")
        print("Retrying with default format selection...")
        fallback_cmd = [
            "yt-dlp",
            "--download-sections", f"*{start}-{end}",
            "--force-keyframes-at-cuts",
            "-o", out_file,
            url,
        ]
        try:
            subprocess.run(fallback_cmd, check=True)
            success = True
        except Exception as ex:
            print(f"Failed fallback download for {category}: {ex}")

    if success:
        if os.path.exists(out_file):
            actual_duration = probe_duration(out_file)
            if actual_duration is None:
                print(f"WARNING: downloaded {out_file} but could not probe its duration "
                      f"(file may be corrupt).")
            else:
                drift = abs(actual_duration - expected_duration)
                status = "OK" if drift <= 2.0 else "MISMATCH"
                print(f"[{status}] Saved to {out_file} "
                      f"(expected {expected_duration}s, got {actual_duration:.1f}s)")
                if status == "MISMATCH":
                    print(f"  -> Check {category} manually before using it in the eval harness.")
        else:
            print(f"WARNING: yt-dlp reported success but {out_file} does not exist.")

print("\nAll downloads finished!")