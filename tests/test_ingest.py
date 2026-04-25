import pytest
from lankarfr.ingest.cbsl_tbill_auction import CBSLTBillScraper

def test_parse_auction_text():
    # Simulate text extracted from a CBSL PDF
    sample_text = """
    CENTRAL BANK OF SRI LANKA
    Communications Department
    20 March 2024
    
    Treasury Bill Auction held on 20 March 2024
    
    Amount Offered Amount Accepted Weighted Average Yield %
    91 Days 10,000 25,000 9.85
    182 Days 5,000 5,000 10.05
    364 Days 15,000 10,000 10.25
    """
    
    scraper = CBSLTBillScraper()
    results = scraper.parse_auction_text(sample_text)
    
    assert results['auction_date'] == "20 March 2024"
    assert results['91_day_yield'] == 9.85
    assert results['182_day_yield'] == 10.05
    assert results['364_day_yield'] == 10.25
    
def test_parse_alternate_date_format():
    sample_text = """
    Date: 15.02.2024
    
    Treasury Bill Auction Results
    91 Days 8.50
    """
    scraper = CBSLTBillScraper()
    results = scraper.parse_auction_text(sample_text)
    
    # We should catch the 'Date: DD.MM.YYYY' format
    assert results['auction_date'] == "15.02.2024"
    assert results['91_day_yield'] == 8.50
    assert results['182_day_yield'] is None
