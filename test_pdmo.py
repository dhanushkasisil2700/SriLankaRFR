import pandas as pd
from lankarfr.ingest.pdmo_daily_summary import PDMOSummaryScraper
import io, requests, urllib3
urllib3.disable_warnings()

scraper = PDMOSummaryScraper()
latest = scraper.get_latest_daily_summary_url()
url = latest['url']
resp = requests.get(url, verify=False)
try:
    xls = pd.ExcelFile(io.BytesIO(resp.content), engine='xlrd')
except:
    xls = pd.ExcelFile(io.BytesIO(resp.content), engine='openpyxl')

df = pd.read_excel(xls, sheet_name='QuotesTBond').fillna('')
for i, row in df.iterrows():
    s = [str(x).strip() for x in row if str(x).strip() != '']
    if s: print(i, s)
