import urllib.request
import urllib.parse
import json
import ssl
import sys

# Create context to ignore SSL certificate validation if needed
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def search_github(filename):
    query = f"filename:{filename}"
    url = f"https://api.github.com/search/code?q={urllib.parse.quote(query)}"
    
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/vnd.github.v3+json'
        }
    )
    
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            data = json.loads(response.read().decode())
            if 'items' in data and len(data['items']) > 0:
                item = data['items'][0]
                # Convert html_url to raw_url
                # Example: https://github.com/user/repo/blob/branch/path/to/file
                # Raw: https://raw.githubusercontent.com/user/repo/branch/path/to/file
                html_url = item['html_url']
                raw_url = html_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                return raw_url
    except Exception as e:
        print(f"Error searching for {filename}: {e}", file=sys.stderr)
    return None

if __name__ == "__main__":
    fonts = [
        "ProximaNova-Bold.ttf",
        "HelveticaNeue-Bold.ttf",
        "Gotham-Bold.ttf",
        "Futura-Bold.ttf"
    ]
    for font in fonts:
        print(f"Searching for {font}...")
        url = search_github(font)
        print(f"Result: {url}")
