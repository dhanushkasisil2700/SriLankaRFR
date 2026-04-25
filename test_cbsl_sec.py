import requests
from bs4 import BeautifulSoup
import pdfplumber
import io

import urllib3
urllib3.disable_warnings()

URL = "https://www.cbsl.gov.lk/en/press/secondary-market-trade-summary"
resp = requests.get(URL, verify=False)
soup = BeautifulSoup(resp.text, 'html.parser')
latest_url = None
for a in soup.find_all('a', href=True):
    if 'secondary' in a.text.lower() and 'trade' in a.text.lower():
        latest_url = a['href']
        break
        
print("Fetching:", latest_url)
resp = requests.get(latest_url, verify=False)
pdf_file = io.BytesIO(resp.content)
text = ""
with pdfplumber.open(pdf_file) as pdf:
    for page in pdf.pages:
        text += (page.extract_text() or "") + "\n"
        
print(text[:2000])
