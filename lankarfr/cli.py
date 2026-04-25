import argparse
import sys
import requests
import pandas as pd
from datetime import datetime
from pprint import pprint

from lankarfr.ingest.cbsl_tbill_auction import CBSLTBillScraper
from lankarfr.ingest.cbsl_tbond_auction import CBSLTBondScraper
from lankarfr.ingest.pdmo_daily_summary import PDMOSummaryScraper
from lankarfr.ingest.cbsl_secondary import CBSLSecondaryScraper
from lankarfr.curve.curve import build_tbill_curve, YieldCurve
from lankarfr.curve.bootstrap import bootstrap_curve, Bond
from lankarfr.curve.smooth import (
    fit_nelson_siegel, 
    fit_nelson_siegel_svensson, 
    fit_cubic_spline, 
    fit_monotone_convex, 
    fit_smith_wilson
)
from lankarfr.store.duckdb_store import CurveStore
from lankarfr.conventions.daycount import get_year_fraction

def main():
    parser = argparse.ArgumentParser(description="LankaRFR - Sri Lanka Risk Free Rate Curve Builder")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest latest T-bill auction results")
    
    # Curve command
    curve_parser = subparsers.add_parser("curve", help="Get curve for a given date")
    curve_parser.add_argument("--date", type=str, help="Date in YYYY-MM-DD format (e.g., 2024-03-20)", required=True)
    curve_parser.add_argument("--tenor", type=float, help="Optional tenor to evaluate (e.g., 5.0 for 5Y)", required=False)
    
    args = parser.parse_args()
    
    if args.command == "ingest":
        print("Fetching PDMO Daily Summary secondary trades...")
        pdmo_scraper = PDMOSummaryScraper()
        latest_pdmo = pdmo_scraper.get_latest_daily_summary_url()
        df_pdmo = None
        pdmo_date = None
        pdmo_tbills = {}
        
        if latest_pdmo:
            try:
                pdmo_date, pdmo_tbills, df_pdmo = pdmo_scraper.fetch_and_parse(latest_pdmo['url'])
                print(f"Found {len(df_pdmo)} secondary quotes from PDMO with report date: {pdmo_date}")
            except Exception as e:
                print(f"Could not parse PDMO: {e}")

        print("Scraping latest CBSL T-Bill auction results...")
        scraper = CBSLTBillScraper()
        try:
            result = scraper.run()
            print(f"Found: {result['title']}")
            
            # Use CBSL date by default
            date_str = result['results']['auction_date']
            if not date_str:
                parsed_dt = datetime.now()
            else:
                try:
                    parsed_dt = datetime.strptime(date_str, "%d %B %Y")
                except ValueError:
                    try:
                        parsed_dt = datetime.strptime(date_str, "%d.%m.%Y")
                    except ValueError:
                        parsed_dt = datetime.now()
                        
            # OVERRIDE WITH PDMO IF PDMO HAS REPORT DATE AND IS NEWER
            if pdmo_date is not None and isinstance(pdmo_date, datetime):
                # If PDMO date is more than 7 days newer than CBSL date, CBSL is stale
                if (pdmo_date - parsed_dt).days > 7:
                    print(f"CBSL missing recent data. Falling back to PDMO T-Bill quotes for {pdmo_date.date()}")
                    parsed_dt = pdmo_date
                    result['results']['91_day_yield'] = pdmo_tbills.get('91_day_yield', result['results']['91_day_yield'])
                    result['results']['182_day_yield'] = pdmo_tbills.get('182_day_yield', result['results']['182_day_yield'])
                    result['results']['364_day_yield'] = pdmo_tbills.get('364_day_yield', result['results']['364_day_yield'])
                    
            iso_date = parsed_dt.strftime("%Y-%m-%d")
            
            # Build T-Bill Curve
            tbill_curve = build_tbill_curve(result['results'])
            curve_points = tbill_curve.points
            bonds_dict = {}
            
            if df_pdmo is not None and not df_pdmo.empty:
                for _, row in df_pdmo.iterrows():
                    if pd.notna(row['maturity_date']) and pd.notna(row['ytm']):
                        tenor = get_year_fraction(parsed_dt.date(), row['maturity_date'].date(), "ACT/365")
                        if tenor > 1.0:
                            bonds_dict[tenor] = Bond(tenor, row['ytm'], row['ytm'])
                            
            # Fetch Secondary Market CBSL Legacy Quotes
            print("Fetching CBSL Legacy Secondary trades...")
            cbsl_sec_scraper = CBSLSecondaryScraper()
            latest_sec = cbsl_sec_scraper.get_latest_summary_url()
            if latest_sec:
                try:
                    df_sec = cbsl_sec_scraper.fetch_and_parse(latest_sec['url'])
                    print(f"Found {len(df_sec)} secondary quotes from CBSL.")
                    for _, row in df_sec.iterrows():
                        if pd.notna(row['tenor_years']) and pd.notna(row['ytm']):
                            tenor = row['tenor_years']
                            if tenor > 1.0:
                                bonds_dict[tenor] = Bond(tenor, row['ytm'], row['ytm'])
                except Exception as e:
                    print(f"Could not parse CBSL Secondary: {e}")

            # Try to fetch recent T-bond results to bootstrap further
            print("Fetching latest T-Bond auction results...")
            bond_scraper = CBSLTBondScraper()
            latest_bond = bond_scraper.get_latest_auction_pdf_url()
            if latest_bond:
                print(f"Found T-Bond auction: {latest_bond['title']}")
                bond_res = requests.get(latest_bond['url'])
                if bond_res.status_code == 200:
                    import io, pdfplumber
                    pdf_file = io.BytesIO(bond_res.content)
                    text = ""
                    with pdfplumber.open(pdf_file) as pdf:
                        for page in pdf.pages:
                            text += (page.extract_text() or "") + "\n"
                            
                    bond_data = bond_scraper.parse_auction_text(text)
                    if bond_data.get('bonds'):
                        print(f"Parsed {len(bond_data['bonds'])} primary bonds from auction.")
                        current_year = parsed_dt.year
                        for b in bond_data['bonds']:
                            tenor = float(b['maturity_year'] - current_year)
                            if tenor > 1.0:
                                # Primary auction points override secondary due to higher volume/firmness
                                bonds_dict[tenor] = Bond(tenor, b['coupon_rate'], b['yield_to_maturity'])
                                
            # 1. Exact-Fit Bootstrap (Linear/Root-Scalar)
            print("1. Generating Exact-Fit Linear Curve...")
            linear_points = curve_points[:]
            
            bonds_list = list(bonds_dict.values())
            raw_yield_points = linear_points[:] # For Nelson-Siegel pool
            
            if bonds_list:
                # Add T-bonds to raw yield pool
                for b in bonds_list:
                    raw_yield_points.append((b.tenor_years, b.ytm))
                    
                print(f"Bootstrapping linear curve with {len(bonds_list)} distinct Bond nodes...")
                # To avoid closely spaced tenors causing extreme zero rate spikes, filter nodes > 0.3 yrs apart
                bonds_list.sort(key=lambda x: x.tenor_years)
                filtered_bonds = []
                last_t = linear_points[-1][0]
                for b in bonds_list:
                    if b.tenor_years - last_t >= 0.2: # Minimum threshold between points
                        filtered_bonds.append(b)
                        last_t = b.tenor_years
                        
                full_curve = bootstrap_curve(linear_points, filtered_bonds)
                linear_points = full_curve.points
                
            # 2. Nelson-Siegel Smoothing
            print("2. Generating Nelson-Siegel Smoothed Curve...")
            ns_points = fit_nelson_siegel(raw_yield_points)
            
            # 3. Nelson-Siegel-Svensson
            print("3. Generating Nelson-Siegel-Svensson Curve...")
            nss_points = fit_nelson_siegel_svensson(raw_yield_points)
            
            # 4. Cubic Splines
            print("4. Generating Cubic Spline Curve...")
            cubic_points = fit_cubic_spline(raw_yield_points)
            
            # 5. Monotone Convex
            print("5. Generating Monotone Convex Curve...")
            mc_points = fit_monotone_convex(raw_yield_points)
            
            # 6. Smith-Wilson
            print("6. Generating Solvency II Smith-Wilson Extrapolated Curve...")
            sw_points = fit_smith_wilson(raw_yield_points, ufr=0.04, alpha=0.1)
                            
            # 7. Save
            print(f"Saving all curves to DuckDB for date {iso_date}...")
            store = CurveStore()
            store.save_curve(iso_date, linear_points, method='linear_exact')
            store.save_curve(iso_date, ns_points, method='nelson_siegel')
            store.save_curve(iso_date, nss_points, method='nss')
            store.save_curve(iso_date, cubic_points, method='cubic_spline')
            store.save_curve(iso_date, mc_points, method='monotone_convex')
            store.save_curve(iso_date, sw_points, method='smith_wilson')
            
            print(f"Successfully saved 6 distinct algorithmic evaluations into the database!")
                
        except Exception as e:
            print(f"Error during ingestion: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
            
    elif args.command == "curve":
        store = CurveStore()
        points = store.get_curve(args.date)
        
        if not points:
            print(f"No curve found for date {args.date}. Run 'lankarfr ingest' first.")
            sys.exit(1)
            
        curve = YieldCurve(points)
        print(f"Yield Curve for {args.date} (continuously compounded zero rates):")
        for t, z in points:
             print(f"  {t:.3f}Y Input Point: {z*100:.2f}%")
             
        if args.tenor is not None:
            z = curve.get_zero_rate(args.tenor)
            df = curve.get_discount_factor(args.tenor)
            print(f"\nEvaluation at tenor {args.tenor}Y:")
            print(f"  Zero Rate: {z*100:.4f}%")
            print(f"  Discount Factor: {df:.6f}")
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
