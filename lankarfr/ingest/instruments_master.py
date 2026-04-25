import requests
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO
from datetime import datetime

class PDMOMasterScraper:
    """
    Pulls outstanding Government Securities from the PDMO website.
    URL: https://www.treasury.gov.lk/web/government-securities/section/GOSL%20Outstanding%20Debt%20Securities
    """
    URL = "https://www.treasury.gov.lk/web/government-securities/section/GOSL%20Outstanding%20Debt%20Securities"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
    def fetch_outstanding_bonds(self) -> pd.DataFrame:
        """
        Attempts to scrape the HTML tables from the PDMO outstanding debt page.
        Returns a DataFrame of active instruments.
        """
        response = self.session.get(self.URL)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Typically the outstanding bonds are in an HTML table.
        # We can use pandas read_html to extract all tables.
        try:
            # StringIO wrap needed for modern pandas read_html
            tables = pd.read_html(StringIO(str(soup)))
        except ValueError:
             # No tables found
             return pd.DataFrame()
             
        # Find the table that looks like a bond list (has ISIN, Maturity, Coupon, etc.)
        bonds_df = None
        for df in tables:
            # Flatten columns if multi-index
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = ['_'.join(map(str, col)).strip() for col in df.columns.values]
                
            cols_lower = [str(c).lower() for c in df.columns]
            
            # Look for typical keywords
            if any('isin' in c for c in cols_lower) and any('maturity' in c for c in cols_lower):
                bonds_df = df
                break
                
        if bonds_df is not None:
            return self._clean_bond_dataframe(bonds_df)
            
        return pd.DataFrame()
        
    def _clean_bond_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize column names and types.
        """
        # Map to standard names
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        col_mapping = {}
        for c in df.columns:
            if 'isin' in c:
                col_mapping[c] = 'isin'
            elif 'maturity' in c:
                col_mapping[c] = 'maturity_date'
            elif 'coupon' in c or 'rate' in c: # Often "Coupon Rate (%)"
                col_mapping[c] = 'coupon_rate'
                
        df = df.rename(columns=col_mapping)
        
        if 'maturity_date' in df.columns:
            # Attempt to parse dates
            df['maturity_date'] = pd.to_datetime(df['maturity_date'], errors='coerce')
            
        if 'coupon_rate' in df.columns:
            # Clean % signs and convert to float
            df['coupon_rate'] = df['coupon_rate'].astype(str).str.replace('%', '').str.strip()
            df['coupon_rate'] = pd.to_numeric(df['coupon_rate'], errors='coerce') / 100.0
            
        return df
