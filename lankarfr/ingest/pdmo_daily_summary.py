import requests
import pandas as pd
from bs4 import BeautifulSoup
import io
import re

class PDMOSummaryScraper:
    """
    Parses the PDMO Daily Summary Report (Excel).
    Finds traded yields for various tenors / bonds.
    """
    LISTING_URL = "https://www.treasury.gov.lk/web/report-daily-report"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.session.verify = False # Sometimes CBSL/PDMO certs are finicky locally
    
    def get_latest_daily_summary_url(self):
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = self.session.get(self.LISTING_URL)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for a in soup.find_all('a', href=True):
            text = a.text.strip().lower()
            if 'daily summary report' in text and 'amended' not in text:
                url = a['href']
                if url.startswith('/'):
                    url = "https://www.treasury.gov.lk" + url
                return {
                    'title': a.text.strip(),
                    'url': url
                }
        return None
        
    def fetch_and_parse(self, url: str) -> pd.DataFrame:
        """
        Downloads the excel file and extracts secondary market transactions.
        Return tuple of (report_date, tbill_dict, df_of_bonds)
        """
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        resp = self.session.get(url)
        resp.raise_for_status()
        
        excel_data = io.BytesIO(resp.content)
        
        # PDMO Daily Summary has multiple sheets. We'll look for standard Outright Transactions sheets
        try:
            xls = pd.ExcelFile(excel_data, engine='xlrd') 
        except Exception:
            xls = pd.ExcelFile(excel_data, engine='openpyxl')
            
        records = []
        tbill_yields = {}
        report_date = None
        
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name).fillna('')
            
            # Find report_date
            # As a fallback, check the whole dataframe string representation
            if report_date is None:
                text_rep = df.to_string()
                match = re.search(r'REPORTING DATE.*?(\d{4}-\d{2}-\d{2})', text_rep, re.IGNORECASE)
                if match:
                    report_date = pd.to_datetime(match.group(1), errors='coerce')
                    
            for r_idx in range(min(15, len(df))):
                row_vals = list(df.iloc[r_idx].values)
                for v in row_vals:
                    if isinstance(v, pd.Timestamp) and report_date is None:
                        report_date = v
                        break
                    elif isinstance(v, str):
                        match = re.search(r'(\d{4}-\d{2}-\d{2})', v)
                        if match and report_date is None:
                            dt = pd.to_datetime(match.group(1), errors='coerce')
                            if pd.notna(dt):
                                report_date = dt
                                break
                        
            # Parse TBills
            if 'Quotes' in sheet_name and 'TBills' in sheet_name.replace(' ', ''):
                for idx, row in df.iterrows():
                    row_str = ' '.join(str(x).lower() for x in row.values)
                    
                    if '3 month' in row_str or '6 month' in row_str or '12 month' in row_str:
                        # Extract yields
                        yields = [float(x.replace('%', '').strip()) if isinstance(x, str) else float(x) for x in row.values if (isinstance(x, (int, float)) or (isinstance(x, str) and re.match(r'^0\.\d+', x.strip()))) and float(str(x).replace('%', '').strip()) < 0.40]
                        if yields:
                            y = sum(yields) / len(yields)
                            if '3 month' in row_str:
                                tbill_yields['91_day_yield'] = y * 100.0 if y < 1.0 else y
                            elif '6 month' in row_str:
                                tbill_yields['182_day_yield'] = y * 100.0 if y < 1.0 else y
                            elif '12 month' in row_str:
                                tbill_yields['364_day_yield'] = y * 100.0 if y < 1.0 else y
            
            # Simple heuristic: Look for column containing dates and columns containing typical yields ~0.05 to 0.30
            # PDMO Two-Way Quotes sheet structure: Series, Tenor, Maturity, Days, Buying Price, Buying Yield, Selling Price, Selling Yield
            if 'QuotesTBond' in sheet_name or 'Bond' in sheet_name:
                for idx, row in df.iterrows():
                    values = [x for x in row.values if x != '']
                    if len(values) >= 5:
                        # Try to find a date
                        mat_date = None
                        for v in values:
                            if re.match(r'\d{4}-\d{2}-\d{2}', str(v).strip()[:10]):
                                mat_date = pd.to_datetime(str(v).strip()[:10], errors='coerce')
                                break
                        
                        if mat_date is not None:
                            # Try to find exactly yields (often around 0.05 to 0.25 in SL right now)
                            # Or if formatted as percentage
                            yields = []
                            for v in values:
                                try:
                                    f = float(str(v).replace('%', '').strip())
                                    if 0.03 < f < 0.35: # If between 3% and 35%, assume decimal yield
                                        yields.append(f)
                                    elif 3.0 < f < 35.0: # If percentage
                                        yields.append(f / 100.0)
                                except Exception:
                                    pass
                                    
                            if yields:
                                # We can take the average of buying and selling yields as the mid YTM
                                mid_ytm = sum(yields) / len(yields)
                                
                                records.append({
                                    'isin': str(values[0]) if isinstance(values[0], str) else None,
                                    'maturity_date': mat_date,
                                    'ytm': mid_ytm,
                                    'sheet': sheet_name
                                })
                                
        return report_date, tbill_yields, pd.DataFrame(records)
