import requests
from bs4 import BeautifulSoup
import pdfplumber
import io
import re
import pandas as pd

class CBSLSecondaryScraper:
    """
    Parses CBSL's legacy Secondary Market Trade Summary reports (PDF).
    Extracts ISIN, Tenure, and WAY (Weighted Average Yield).
    """
    LISTING_URL = "https://www.cbsl.gov.lk/en/press/secondary-market-trade-summary"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.session.verify = False 
        
    def get_latest_summary_url(self):
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = self.session.get(self.LISTING_URL)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            text = a.text.strip().lower()
            if 'secondary' in text and 'trade' in text:
                url = a['href']
                if not url.startswith('http'):
                    url = "https://www.cbsl.gov.lk" + url
                return {
                    'title': a.text.strip(),
                    'url': url
                }
        return None
        
    def fetch_and_parse(self, url: str) -> pd.DataFrame:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        resp = self.session.get(url)
        resp.raise_for_status()
        
        pdf_file = io.BytesIO(resp.content)
        records = []
        
        with pdfplumber.open(pdf_file) as pdf:
            text = ""
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
                
            # Lines look like:
            # 3LKB00428B156 2.21 TBond 9.15 9.15 9.15 9.15 9.15 7 50 5
            # Or sometimes:
            # 1 LKA36426A300 0.16 Tbill 7.75 7.75 7.75 7.75 7.75 4 70 1
            for line in text.split('\n'):
                line = line.strip()
                # Find ISIN match: LKA or LKB followed by 9 chars
                isin_match = re.search(r'(LK[AB]\w{9})', line)
                if isin_match:
                    isin = isin_match.group(1)
                    # Extract floats
                    nums = re.findall(r'\b\d+\.\d{2}\b', line)
                    if len(nums) >= 6:
                        # Usually format: Tenure, Open, Close, High, Low, WAY
                        tenor_val = float(nums[0])
                        way_val = float(nums[5])
                        
                        if 0 < tenor_val < 40 and 0 < way_val < 35:
                            records.append({
                                'isin': isin,
                                'tenor_years': tenor_val,
                                'ytm': way_val / 100.0,
                                'source': 'CBSL_Secondary_PDF'
                            })
                            
        return pd.DataFrame(records)
