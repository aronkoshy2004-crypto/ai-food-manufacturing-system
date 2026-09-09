import httpx
import re
import urllib.parse

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

# Try Yahoo
url = f"https://search.yahoo.com/search?p={urllib.parse.quote('\"POSHACO\" \"Logistics Management Dashboard\"')}"
try:
    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=10.0)
    print("Yahoo status:", r.status_code)
    # find compText or snippets
    snippets = re.findall(r'<div class="compText[^"]*"[^>]*>(.*?)</div>', r.text)
    for s in snippets[:6]:
        clean = re.sub(r'<[^>]+>', '', s).strip()
        print("Snippet:", clean)
        print("-" * 50)
except Exception as e:
    print("Yahoo error:", e)
