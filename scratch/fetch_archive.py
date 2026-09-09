import httpx
import re

archive_url = 'https://web.archive.org/web/20250000000000*/https://dribbble.com/shots/25706847-POSHACO-Logistics-Management-Dashboard-for-Steel-Manufacturing'
cdx_url = 'http://web.archive.org/cdx/search/cdx?url=dribbble.com/shots/25706847*&output=json'
try:
    r = httpx.get(cdx_url, timeout=10.0)
    print("Archive CDX Status:", r.status_code)
    print("Archive data:", r.text)
except Exception as e:
    print("Archive error:", e)
