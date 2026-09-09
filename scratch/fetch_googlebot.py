import httpx
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
}
url = 'https://dribbble.com/shots/25706847-POSHACO-Logistics-Management-Dashboard-for-Steel-Manufacturing'
try:
    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=10.0)
    print('Googlebot Status:', r.status_code)
    if r.status_code == 200:
        print('Title:', re.findall(r'<title>(.*?)</title>', r.text))
        imgs = re.findall(r'https://cdn\.dribbble\.com/[^"\'\s<>]+', r.text)
        print('Images found:', len(imgs))
        for img in list(dict.fromkeys(imgs))[:10]:
            print('Img:', img)
        og = re.findall(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', r.text)
        print('og:image:', og)
        desc = re.findall(r'name=["\']description["\']\s+content=["\']([^"\']+)["\']', r.text)
        print('desc:', desc)
    else:
        print('Sample:', r.text[:300])
except Exception as e:
    print('Error:', e)
