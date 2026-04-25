import urllib.request
import re
from bs4 import BeautifulSoup

url = 'https://www.cbsl.gov.lk/en/press/press-releases/government-securities'
html = urllib.request.urlopen(url).read().decode('utf-8')
soup = BeautifulSoup(html, 'html.parser')

links = []
for a in soup.find_all('a', href=True):
    if 'Treasury Bill' in a.text:
        links.append({'text': a.text.strip(), 'href': a['href']})

import json
print(json.dumps(links[:10], indent=2))
