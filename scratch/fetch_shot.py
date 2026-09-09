import httpx
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

url = 'https://dribbble.com/shots/25706847-POSHACO-Logistics-Management-Dashboard-for-Steel-Manufacturing'
try:
    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=15.0)
    print('Status:', r.status_code)
    og_img = re.findall(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', r.text)
    print('og:image:', og_img)
    twitter_img = re.findall(r'name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']', r.text)
    print('twitter:image:', twitter_img)
    desc = re.findall(r'name=["\']description["\']\s+content=["\']([^"\']+)["\']', r.text)
    print('description:', desc)
    title = re.findall(r'<title>(.*?)</title>', r.text)
    print('title:', title)
    
    # Also find any media / shot attachment images
    imgs = re.findall(r'https://cdn\.dribbble\.com/userupload/[^"\'\s<>]+', r.text)
    print('Userupload images:', list(dict.fromkeys(imgs))[:5])
    
    if not og_img and not imgs:
        print('Sample of text:', r.text[:1000])
except Exception as e:
    print('Error:', e)
