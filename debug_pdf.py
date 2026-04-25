from lankarfr.ingest.cbsl_tbill_auction import CBSLTBillScraper
scraper = CBSLTBillScraper()
latest = scraper.get_latest_auction_pdf_url()
text = scraper.read_pdf_url(latest['url'])
print(text)
