import subprocess
import json

categories = {
    "1. Solo talking head": {
        "url": "https://www.youtube.com/watch?v=a7BSGdyjAL4",
        "notes": "Steven Bartlett - sweats the small stuff. Monologue style."
    },
    "2. Two-person side-by-side podcast": {
        "playlist": "https://www.youtube.com/playlist?list=PL22egh3ok4cNqo10K5wOZOCdPflfWMyF1",
        "notes": "Diary of a CEO playlist - guest interviews."
    },
    "3. Corner-mounted webcam over slides": {
        "search": "NetworkChuck coding tutorial",
        "notes": "Webcam overlay over code/slides layout."
    },
    "4. Fast cross-talk/interruptions": {
        "search": "Kill Tony full episode",
        "notes": "Panel/debate with fast cross-talk."
    },
    "5. Occluded/profile face": {
        "search": "Binging with Babish recipe",
        "notes": "Host looks down at food (occlusion/profile)."
    },
    "6. Background poster/photo": {
        "search": "Ludwig just chatting VOD",
        "notes": "Streamer background with monitors/posters."
    }
}

def run_ytdlp(args):
    cmd = ["yt-dlp", "--dump-json"] + args
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return [json.loads(line) for line in res.stdout.strip().split("\n") if line.strip()]
    except Exception as e:
        print(f"Error running yt-dlp with args {args}: {e}")
        return []

vault = {}

# 1. Solo talking head
print("Processing Category 1...")
info_list = run_ytdlp(["--playlist-items", "1", categories["1. Solo talking head"]["url"]])
if info_list:
    vault["solo_talking_head"] = {
        "title": info_list[0].get("title"),
        "url": categories["1. Solo talking head"]["url"],
        "duration": info_list[0].get("duration"),
        "notes": categories["1. Solo talking head"]["notes"]
    }

# 2. Two-person side-by-side podcast
print("Processing Category 2...")
info_list = run_ytdlp(["--playlist-items", "1-3", categories["2. Two-person side-by-side podcast"]["playlist"]])
vault["two_person_podcast"] = []
for info in info_list:
    vault["two_person_podcast"].append({
        "title": info.get("title"),
        "url": f"https://www.youtube.com/watch?v={info.get('id')}",
        "duration": info.get("duration"),
        "notes": categories["2. Two-person side-by-side podcast"]["notes"]
    })

# 3. Corner-mounted webcam over slides
print("Processing Category 3...")
info_list = run_ytdlp(["ytsearch3:NetworkChuck coding tutorial"])
vault["webcam_course_layout"] = []
for info in info_list:
    vault["webcam_course_layout"].append({
        "title": info.get("title"),
        "url": f"https://www.youtube.com/watch?v={info.get('id')}",
        "duration": info.get("duration"),
        "notes": categories["3. Corner-mounted webcam over slides"]["notes"]
    })

# 4. Fast cross-talk/interruptions
print("Processing Category 4...")
info_list = run_ytdlp(["ytsearch3:Kill Tony full episode"])
vault["fast_crosstalk"] = []
for info in info_list:
    vault["fast_crosstalk"].append({
        "title": info.get("title"),
        "url": f"https://www.youtube.com/watch?v={info.get('id')}",
        "duration": info.get("duration"),
        "notes": categories["4. Fast cross-talk/interruptions"]["notes"]
    })

# 5. Occluded/profile face
print("Processing Category 5...")
info_list = run_ytdlp(["ytsearch3:Binging with Babish recipe"])
vault["occluded_profile_face"] = []
for info in info_list:
    vault["occluded_profile_face"].append({
        "title": info.get("title"),
        "url": f"https://www.youtube.com/watch?v={info.get('id')}",
        "duration": info.get("duration"),
        "notes": categories["5. Occluded/profile face"]["notes"]
    })

# 6. Background poster/photo
print("Processing Category 6...")
info_list = run_ytdlp(["ytsearch3:Ludwig just chatting VOD"])
vault["background_poster"] = []
for info in info_list:
    vault["background_poster"].append({
        "title": info.get("title"),
        "url": f"https://www.youtube.com/watch?v={info.get('id')}",
        "duration": info.get("duration"),
        "notes": categories["6. Background poster/photo"]["notes"]
    })

# Save to file
vault_path = "/home/manoj/Developer/makemyclip-remotion/video_vault.json"
with open(vault_path, "w") as f:
    json.dump(vault, f, indent=2)

print(f"\nSaved video vault to {vault_path}!")
