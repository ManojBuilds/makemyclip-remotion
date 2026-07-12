import modal

image = modal.Image.debian_slim().pip_install("requests")
app = modal.App("test-fetch", image=image)

@app.function()
def test_fetch_metadata(url: str):
    import requests
    import re
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print("Status:", res.status_code)
        if res.status_code != 200:
            return f"Failed: status {res.status_code}"
            
        html = res.text
        length_match = re.search(r'"lengthSeconds":"(\d+)"', html)
        if length_match:
            return f"Success! Length: {length_match.group(1)}"
        else:
            # Let's save a snippet to see what's there
            print("HTML sample:", html[:500])
            return "Failed to find lengthSeconds"
    except Exception as e:
        return f"Error: {e}"

@app.local_entrypoint()
def main():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    res = test_fetch_metadata.remote(url)
    print("Result:", res)
