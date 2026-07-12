import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def list_repo_contents(owner, repo, path=""):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
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
    # 1. Inspect NicoAcosta/gotham-fonts/ttf
    print("\n--- NicoAcosta/gotham-fonts/ttf ---")
    contents = list_repo_contents("NicoAcosta", "gotham-fonts", "ttf")
    if contents:
        for item in contents:
            print(f"  {item['name']} -> {item['download_url']}")
            
    # 2. Inspect Kyles-World/Futura-Font
    print("\n--- Kyles-World/Futura-Font ---")
    contents = list_repo_contents("Kyles-World", "Futura-Font")
    if contents:
        for item in contents:
            print(f"  {item['name']} -> {item['download_url']}")
            if item['type'] == 'dir':
                subcontents = list_repo_contents("Kyles-World", "Futura-Font", item['name'])
                if subcontents:
                    for sub in subcontents:
                        print(f"    {sub['name']} -> {sub['download_url']}")

    # 3. Inspect EverGoebbels/HelveticaNeue (specifically looking for Bold/Condensed)
    print("\n--- EverGoebbels/HelveticaNeue ---")
    contents = list_repo_contents("EverGoebbels", "HelveticaNeue")
    if contents:
        for item in contents:
            if "bold" in item['name'].lower() or "cond" in item['name'].lower():
                print(f"  {item['name']} -> {item['download_url']}")
