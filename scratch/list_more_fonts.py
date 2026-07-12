import urllib.request
import urllib.parse
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def list_repo_contents(owner, repo, path=""):
    # URL encode each segment of the path
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
    # 1. List Proxima Nova all items
    print("--- Proxima Nova all items ---")
    contents = list_repo_contents("matthewelsom", "font-ProximaNova", "TTF")
    if contents:
        for item in contents:
            if "black" in item['name'].lower() or "bold" in item['name'].lower():
                print(f"  {item['name']} -> {item['download_url']}")
                
    # 2. List Futura (Original Version)
    print("\n--- Futura (Original Version) ---")
    contents = list_repo_contents("Kyles-World", "Futura-Font", "Futura (Original Version)")
    if contents:
        for item in contents:
            print(f"  {item['name']} -> {item['download_url']}")
            
    # 3. List Futura PT (ParaType)
    print("\n--- Futura PT (ParaType) ---")
    contents = list_repo_contents("Kyles-World", "Futura-Font", "Futura PT (ParaType)")
    if contents:
        for item in contents:
            print(f"  {item['name']} -> {item['download_url']}")
