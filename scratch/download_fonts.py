import urllib.request
import urllib.parse
import os
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Ensure fonts directory exists
os.makedirs("fonts", exist_ok=True)

def download_file(url, dest):
    # Encode spaces and special chars in the path of the URL
    parsed = urllib.parse.urlparse(url)
    encoded_path = urllib.parse.quote(parsed.path)
    encoded_url = urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        encoded_path,
        parsed.params,
        parsed.query,
        parsed.fragment
    ))
    
    print(f"Downloading {encoded_url} to {dest}...")
    try:
        req = urllib.request.Request(
            encoded_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, context=ctx) as response:
            with open(dest, 'wb') as f:
                f.write(response.read())
        print(f"Successfully downloaded {dest}!")
        return True
    except Exception as e:
        print(f"Failed to download {encoded_url}: {e}")
        return False

fonts_to_download = [
    # 1. Proxima Nova Bold
    ("https://raw.githubusercontent.com/matthewelsom/font-ProximaNova/master/TTF/Mark Simonson - Proxima Nova Bold.ttf", "fonts/ProximaNova-Bold.ttf"),
    # Proxima Nova Black
    ("https://raw.githubusercontent.com/hotsen/proximanova/master/Proxima Nova Black.otf", "fonts/ProximaNova-Black.otf"),
    
    # 2. Helvetica Neue Bold
    ("https://raw.githubusercontent.com/EverGoebbels/HelveticaNeue/main/HelveticaNeue-Bold.otf", "fonts/HelveticaNeue-Bold.otf"),
    # Helvetica Neue Condensed Bold
    ("https://raw.githubusercontent.com/EverGoebbels/HelveticaNeue/main/HelveticaNeue-CondensedBold.ttf", "fonts/HelveticaNeue-CondensedBold.ttf"),
    
    # 3. Gotham Bold
    ("https://raw.githubusercontent.com/NicoAcosta/gotham-fonts/main/ttf/GothamBold.ttf", "fonts/Gotham-Bold.ttf"),
    # Gotham Ultra
    ("https://raw.githubusercontent.com/NicoAcosta/gotham-fonts/main/ttf/GothamUltra.ttf", "fonts/Gotham-Ultra.ttf"),
    
    # 4. Futura Bold
    ("https://raw.githubusercontent.com/Kyles-World/Futura-Font/main/Futura (Original Version)/Futura-Bold.ttf", "fonts/Futura-Bold.ttf"),
    # Futura Extra Bold
    ("https://raw.githubusercontent.com/Kyles-World/Futura-Font/main/Futura (Original Version)/Futura-ExtraBold.ttf", "fonts/Futura-ExtraBold.ttf")
]

for url, dest in fonts_to_download:
    download_file(url, dest)
