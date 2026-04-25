import io
import re
import requests
import pdfplumber
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class CBSLTBillScraper:
    LISTING_URL = "https://www.cbsl.gov.lk/en/press/press-releases/government-securities"
    BASE_URL = "https://www.cbsl.gov.lk"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
    def get_latest_auction_pdf_url(self):
        """
        Scrapes the CBSL press releases page to find the latest Treasury Bill auction result PDF.
        """
        response = self.session.get(self.LISTING_URL)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for a in soup.find_all('a', href=True):
            text = a.text.strip()
            # We want Treasury bill auction results, ignoring bond announcements if they appear
            if 'Treasury Bill' in text and 'Auction' in text:
                # Some links are in a "View" or "Download" button inside the block
                href = a['href']
                full_url = urljoin(self.BASE_URL, href)
                return {
                    'title': text,
                    'url': full_url
                }
        return None

    def read_pdf_url(self, pdf_url: str):
        """Fetches the PDF and returns its text content"""
        response = self.session.get(pdf_url)
        response.raise_for_status()
        
        pdf_file = io.BytesIO(response.content)
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        return text

    def parse_auction_text(self, text: str):
        """
        Parses text extracted from a CBSL T-Bill PDF to find the auction date and yields.
        """
        results = {
            'auction_date': None,
            '91_day_yield': None,
            '182_day_yield': None,
            '364_day_yield': None
        }
        
        # 1. Parse Date - Usually looks like "Auction Date: 20 March 2024" or "held on 20 March 2024"
        date_match = re.search(r"(?:Auction Date|held on)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if date_match:
            results['auction_date'] = date_match.group(1).strip()
            
        # 2. Add fallback for date at the top of the press release if "Auction Date" block differs
        if not results['auction_date']:
            # Sometimes CBSL PDFs just start with "Date: DD.MM.YYYY"
            date_match = re.search(r"Date\s*[:\-]\s*(\d{1,2}[\./\-]\d{1,2}[\./\-]\d{4})", text, re.IGNORECASE)
            if date_match:
                results['auction_date'] = date_match.group(1).strip()

        # 3. Parse Yields
        # Table lines usually contain things like: "91 Days \n 10,000 25,000 8.50"
        lines = text.split('\n')
        current_tenor = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Detect Tenor string
            if "91" in line and (line == "91" or "Day" in line):
                current_tenor = 91
            elif "182" in line and (line == "182" or "Day" in line):
                current_tenor = 182
            elif "364" in line and (line == "364" or "Day" in line):
                current_tenor = 364
                
            # If we know the tenor, look for floats
            if current_tenor is not None:
                # Find yields roughly in the typical 5% to 30% range
                nums = re.findall(r'\b\d+\.\d{2}\b', line)
                if nums:
                    # Current WAYR is typically the second to last if there are two (Current vs Last), 
                    # or just the last if there's only one.
                    # Amounts are usually without decimals or have commas.
                    yields = [float(n) for n in nums if 2.0 <= float(n) <= 50.0]
                    if yields:
                        # usually `Current WAYR` is yields[0] if there's multiple (Current, Previous) or yields[-1] if there's (Amount, amount, yield)
                        # We will take yields[0] which corresponds to "Current Auction" WAYR
                        val = yields[0]
                        if current_tenor == 91:
                            results['91_day_yield'] = val
                        elif current_tenor == 182:
                            results['182_day_yield'] = val
                        elif current_tenor == 364:
                            results['364_day_yield'] = val
                        # Reset tenor search
                        current_tenor = None
                        
        return results

    def run(self):
        """Standard pipeline: fetch latest PDF link, download, and parse."""
        latest = self.get_latest_auction_pdf_url()
        if not latest:
            raise ValueError("Could not find a Treasury Bill auction link.")
            
        text = self.read_pdf_url(latest['url'])
        parsed = self.parse_auction_text(text)
        
        return {
            'title': latest['title'],
            'url': latest['url'],
            'results': parsed,
            'raw_text_snippet': text[:500] # Return a snippet for debugging
        }
