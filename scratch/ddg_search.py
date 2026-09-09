import httpx
import re
import urllib.parse

q = 'POSHACO Logistics Management Dashboard for Steel Manufacturing'
url = 'https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(q)
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
r = httpx.get(url, headers=headers, follow_redirects=True)

titles = re.findall(r'<a class="result__url"[^>]*href="([^"]+)"', r.text)
snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', r.text, re.DOTALL)

for u, s in zip(titles[:5], snippets[:5]):
    clean_s = re.sub(r'<[^>]+>', '', s).strip()
    print('URL:', u)
    print('Snippet:', clean_s)
    print('='*60)
