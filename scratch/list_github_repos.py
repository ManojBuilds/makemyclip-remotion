import urllib.request
import json
import ssl
import sys

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
    repos = [
        ("matthewelsom", "font-ProximaNova", "TTF"),
        ("NicoAcosta", "gotham-fonts", ""),
        ("Catarina9548", "futura-fonts", ""),
        ("ifvictr", "helvetica-neue", ""),
        ("Kyles-World", "Futura-Font", ""),
        ("Kyles-World", "Helvetica-Font", ""),
        ("EverGoebbels", "HelveticaNeue", "")
    ]
    
    for owner, repo, path in repos:
        print(f"\n--- {owner}/{repo}/{path} ---")
        contents = list_repo_contents(owner, repo, path)
        if contents:
            if isinstance(contents, list):
                for item in contents[:25]: # limit to 25 items
                    print(f"  {item['type']}: {item['name']} -> {item['download_url']}")
            else:
                print(f"  Single item or object: {contents.get('name')}")
        else:
            # Try without path
            if path:
                print(f"Retrying root path for {owner}/{repo}...")
                contents = list_repo_contents(owner, repo, "")
                if contents and isinstance(contents, list):
                    for item in contents[:25]:
                        print(f"  {item['type']}: {item['name']} -> {item['download_url']}")
