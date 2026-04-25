import io
import re
import requests
import pdfplumber
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime

class CBSLTBondScraper:
    LISTING_URL = "https://www.cbsl.gov.lk/en/press/press-releases/government-securities"
    BASE_URL = "https://www.cbsl.gov.lk"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
    def get_latest_auction_pdf_url(self):
        response = self.session.get(self.LISTING_URL)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for a in soup.find_all('a', href=True):
            text = a.text.strip()
            if 'Treasury Bond' in text and 'Auction' in text:
                href = a['href']
                full_url = urljoin(self.BASE_URL, href)
                return {
                    'title': text,
                    'url': full_url
                }
        return None

    def parse_auction_text(self, text: str):
        """
        Extracts multiple bond auction results from a single PDF.
        Bonds usually have a Maturity Date/Year, Coupon, and WAY (Weighted Average Yield).
        """
        results = {
            'auction_date': None,
            'bonds': []
        }
        
        # 1. Parse Date - Usually "Auction Date: 20 March 2024" or "Date: DD.MM.YYYY"
        date_match = re.search(r"(?:Auction Date|held on)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if date_match:
            results['auction_date'] = date_match.group(1).strip()
        else:
            date_match = re.search(r"Date\s*[:\-]\s*(\d{1,2}[\./\-]\d{1,2}[\./\-]\d{4})", text, re.IGNORECASE)
            if date_match:
                results['auction_date'] = date_match.group(1).strip()
                
        # 2. Extract bond details. CBSL Bond tables often have rows with Series, Coupon, WAY
        # This is a bit heuristical because formats change.
        # Example line: "LKB00326H194 09.00% 2026 11.25%"
        # Let's search for lines containing percentage signs and potential series/years.
        lines = text.split("\n")
        
        for line in lines:
            line = line.strip()
            # If line has two percentage signs (Coupon and WAY) or percentage and ISIN
            if "%" in line:
                # find floating numbers
                nums = re.findall(r'\b\d+\.\d{2}\b', line)
                if len(nums) >= 2:
                    # we might have (Coupon, WAY)
                    # Let's look for a maturity date or year
                    # Year like 2026, 2030
                    year_match = re.search(r'\b(20\d{2})\b', line)
                    if year_match and len(nums) >= 2:
                        year = int(year_match.group(1))
                        # As an approximation, usually coupon is the first float % and WAY is the last float
                        coupon = float(nums[0])
                        way = float(nums[-1])
                        
                        # Only add if it looks sane
                        if 0 < coupon < 30 and 0 < way < 30:
                            results['bonds'].append({
                                'maturity_year': year,
                                'coupon_rate': coupon / 100.0,
                                'yield_to_maturity': way / 100.0,
                                'raw_line': line
                            })
                            
        return results
