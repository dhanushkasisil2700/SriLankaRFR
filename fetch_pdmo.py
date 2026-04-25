import requests
from bs4 import BeautifulSoup
import json

URL = "https://www.treasury.gov.lk/web/report-daily-report"
print(f"Fetching {URL}...")
try:
    resp = requests.get(URL, verify=False) # Disable verify for local testing if CBSL has strange certs
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    links = []
    for a in soup.find_all('a', href=True):
        if 'api/file/' in a['href'] or 'report' in a.text.lower() or '.pdf' in a['href'].lower():
            links.append({'text': a.text.strip(), 'href': a['href']})
            
    print(json.dumps(links[:15], indent=2))
except Exception as e:
    print("Error:", e)
