import urllib.request
import urllib.parse
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def list_repo_contents(owner, repo, path=""):
    encoded_path = "/".join(urllib.parse.quote(p) for p in path.split("/"))
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}"
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/vnd.github.v3+json'
        }
    )
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Error listing {owner}/{repo}/{path}: {e}")
        return None

if __name__ == "__main__":
    print("--- Proxima Nova OTF folder ---")
    contents = list_repo_contents("matthewelsom", "font-ProximaNova", "OTF")
    if contents:
        for item in contents:
            if "black" in item['name'].lower() or "extrabold" in item['name'].lower() or "bold" in item['name'].lower():
                print(f"  {item['name']} -> {item['download_url']}")
