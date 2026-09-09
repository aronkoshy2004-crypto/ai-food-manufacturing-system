import httpx
import re
import urllib.parse

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

url = f"https://www.bing.com/search?q={urllib.parse.quote('site:dribbble.com/shots/25706847 OR \"POSHACO - Logistics Management Dashboard\"')}"
try:
    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=10.0)
    print("Bing Web Status:", r.status_code)
    # Extract b_caption or result snippets
    snippets = re.findall(r'<p class="b_lineclamp[^"]*"[^>]*>(.*?)</p>', r.text)
    if not snippets:
        snippets = re.findall(r'<div class="b_caption"[^>]*>(.*?)</div>', r.text, re.DOTALL)
    for s in snippets[:6]:
        print("Snippet:", re.sub(r'<[^>]+>', '', s).strip())
        print("-" * 50)
except Exception as e:
    print("Bing web error:", e)
