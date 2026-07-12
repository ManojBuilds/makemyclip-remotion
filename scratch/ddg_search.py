import urllib.request
import urllib.parse
import re
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def ddg_search(query):
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    )
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            html = response.read().decode('utf-8', errors='ignore')
            links = re.findall(r'href="([^"]*)"', html)
            cleaned = []
            for link in links:
                if 'github.com' in link:
                    if 'uddg=' in link:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                        if 'uddg' in parsed:
                            cleaned.append(parsed['uddg'][0])
                    else:
                        cleaned.append(link)
            return list(set(cleaned))
    except Exception as e:
        print(f"DDG Search Error: {e}")
    return []

if __name__ == "__main__":
    queries = [
        'proxima gotham din futura site:github.com',
        'proximanova gotham din futura site:github.com',
        'proxima gotham din futura fonts site:github.com'
    ]
    for q in queries:
        print(f"\nQuery: {q}")
        results = ddg_search(q)
        for r in results[:10]:
            print(f"  - {r}")
