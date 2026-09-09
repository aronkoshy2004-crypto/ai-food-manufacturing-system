import httpx
import re
import urllib.parse

q = 'POSHACO Logistics Management Dashboard for Steel Manufacturing'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9'
}

# Try Bing
bing_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(q)}"
try:
    r = httpx.get(bing_url, headers=headers, follow_redirects=True, timeout=10.0)
    print("Bing Status:", r.status_code)
    m = re.findall(r'murl&quot;:&quot;(https://[^&]+)&quot;', r.text)
    print("Bing murls:", len(m))
    for u in m[:5]:
        print("Image URL:", u)
    
    # Extract titles and snippets
    t = re.findall(r't1&quot;:&quot;([^&]+)&quot;', r.text)
    print("Bing titles:", t[:5])
except Exception as e:
    print("Bing error:", e)
