import time
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf
import os
from dotenv import load_dotenv

# Import the new method from vnstock.api.quote
from vnstock.api.quote import Quote

# Define all directory paths at the top level
PRICES_DIR = Path("F:/huyle_data_projects/stock_price_prediction/data/for_pretrained_models/prices")
MACRO_DIR = Path("F:/huyle_data_projects/stock_price_prediction/data/for_pretrained_models/macro")

load_dotenv() 

try:
    # Optional: FRED API client for Fed funds rate
    from fredapi import Fred                   
    # Mark as available so we attempt FRED fetch later
    FRED_AVAILABLE = True                      
except ImportError:
    # fredapi not installed, skip FRED fetch silently
    FRED_AVAILABLE = False                     

# 6 VN30 tickers to fetch
SYMBOLS = ["VNM", "FPT", "MSN", "VCB", "VIC", "HPG"]  

# Mapping of human-readable name to Yahoo Finance ticker
MACRO_TICKERS = {          
    "gold":  "GC=F",       # Gold futures
    "oil":   "CL=F",       # WTI crude oil futures
    "sp500": "^GSPC",      # S&P 500 index
    "dxy":   "DX-Y.NYB",   # US dollar index
}

FRED_SERIES = {
    # Effective federal funds rate series on FRED
    "fed_rate": "FEDFUNDS",  
}

FRED_API_KEY = os.getenv("FRED_API_KEY") 

# Pull ~10 years of historical data (API usually expects YYYY-MM-DD format for requesting)
START_DATE = "2010-01-01"                         

# Fix timezone issue: Always get current date in ICT/UTC+7 to prevent missing the current day
END_DATE = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d")  

# Seconds to sleep between requests to avoid rate limiting
DELAY = 1.0  

logging.basicConfig(
    # Show INFO and above, suppress DEBUG
    level=logging.INFO,                                  
    # Format log output
    format="%(asctime)s  %(levelname)-8s  %(message)s",  
    # Show only HH:MM:SS, not full date
    datefmt="%H:%M:%S",                                  
)
# Create logger for this module
log = logging.getLogger(__name__)  


# Fetch historical data for a single symbol
def fetch_one_symbol(symbol: str) -> pd.DataFrame | None:
    sources = [("VCI", "vci"), ("DNSE", "dnse")]  

    # Iterate through available sources one by one
    for source_name, source_key in sources:      
        try:
            log.info(f"  {symbol} <- {source_name}")

            # Initialize Quote object using new Vnstock structure
            q = Quote(symbol=symbol, source=source_key)
            df = q.history(start=START_DATE, end=END_DATE, interval="1D")
            
            # Standardize date column name
            if 'time' in df.columns:
                df = df.rename(columns={"time": "date"})

            # Skip this source if response has no rows
            if df.empty:                             
                log.warning(f"  {symbol} ({source_name}): empty response")
                continue
            
            # Add ticker column identifying the stock
            df["ticker"] = symbol

            # Sort ascending by date first to maintain chronological order
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)               

            # Format date to dd-mm-yy (e.g., 07-05-26)
            df["date"] = df["date"].dt.strftime("%d-%m-%y")  
            
            # Titlecase all column names for consistency (e.g., 'Date', 'Close', 'Ticker')
            df.columns = [c.title() for c in df.columns]                     

            log.info(f"  + {symbol}: {len(df)} rows  [{df['Date'].iloc[0]} -> {df['Date'].iloc[-1]}]")
            
            # Success: return the raw DataFrame
            return df  

        except Exception as e:
            # Log error but keep trying other sources
            log.warning(f"  x {symbol} ({source_name}): {e}")  
            time.sleep(DELAY)

    log.error(f"  xx {symbol}: all sources failed")
    # Return None so the caller knows this ticker failed
    return None  


# Fetch data for all defined VN stocks
def fetch_all_symbols() -> None:
    # Create directory recursively, no error if exists
    PRICES_DIR.mkdir(parents=True, exist_ok=True)  

    # Collect failed tickers to report at the end
    failed = []  

    log.info(f"Fetching VN stocks ({START_DATE} -> {END_DATE})")

    for symbol in SYMBOLS:
        # Fetch one ticker
        df = fetch_one_symbol(symbol)  

        if df is not None:
            path = PRICES_DIR / f"{symbol}.csv"  
            # Save to CSV without writing the row index
            df.to_csv(path, index=False)          
            log.info(f"  -> saved: {path}")
        else:
            # Mark as failed
            failed.append(symbol)  

        # Wait before fetching next ticker
        time.sleep(DELAY)  

    if failed:
        log.error(f"Failed tickers: {failed}")
    else:
        log.info("All VN stocks fetched successfully")


# Fetch macro data using yfinance
def fetch_macro_yfinance() -> None:
    # Create directory if not exists
    MACRO_DIR.mkdir(parents=True, exist_ok=True)  

    log.info("Fetching macro data via yfinance")

    for name, ticker in MACRO_TICKERS.items():  
        try:
            log.info(f"  {name} ({ticker})")

            df = yf.download(
                ticker,
                start=START_DATE,
                end=END_DATE,
                # Suppress yfinance progress bar
                progress=False,    
                # Adjust prices for splits and dividends automatically
                auto_adjust=True, # return adjusted close price
            )

            if df.empty:
                log.warning(f"  {name}: empty response")
                continue

            # Keep only the Close column since this is only extraneous variable
            out = df[["Close"]].copy()                                
            # Rename to "value" for consistency across all macro files
            out.columns = ["value"]                                   
            out.index.name = "date"
            
            # Add ticker column
            out["ticker"] = ticker
            
            # Sort chronologically, reset index to make date a column
            out = out.sort_index().reset_index()
            
            # Format date to dd-mm-yy
            out["date"] = pd.to_datetime(out["date"]).dt.strftime("%d-%m-%y")  
            
            # Titlecase all columns
            out.columns = [c.title() for c in out.columns]                                      

            path = MACRO_DIR / f"{name}.csv"
            # index=False since date is now a regular column
            out.to_csv(path, index=False)  
            
            log.info(f"  + {name}: {len(out)} rows  [{out['Date'].iloc[0]} -> {out['Date'].iloc[-1]}]")
            log.info(f"  -> saved: {path}")

            time.sleep(DELAY)

        except Exception as e:
            # Log error and continue to next ticker
            log.error(f"  x {name}: {e}")  


# Fetch macro data using FRED API
def fetch_macro_fred() -> None:
    # fredapi not installed, skip entirely
    if not FRED_AVAILABLE:                    
        log.warning("fredapi not installed, skipping FRED (pip install fredapi)")
        return

    # Placeholder not replaced, skip silently
    if FRED_API_KEY == "YOUR_FRED_API_KEY" or not FRED_API_KEY:  
        log.warning("FRED_API_KEY not set, skipping FRED fetch")
        log.warning("Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        return

    log.info("Fetching macro data via FRED")

    # Init FRED client with API key
    fred = Fred(api_key=FRED_API_KEY)  

    for name, series_id in FRED_SERIES.items():  
        try:
            log.info(f"  {name} ({series_id})")

            # Returns pandas Series indexed by date
            series = fred.get_series(series_id, observation_start=START_DATE)  

            # Convert Series to DataFrame with column "value"
            out = series.to_frame(name="value")                                
            out.index.name = "date"
            
            # Add ticker column
            out["ticker"] = series_id
            
            # Sort chronologically, reset index
            out = out.sort_index().reset_index()
            
            # Format date to dd-mm-yy
            out["date"] = pd.to_datetime(out["date"]).dt.strftime("%d-%m-%y")
            
            # Titlecase all columns
            out.columns = [c.title() for c in out.columns]

            path = MACRO_DIR / f"{name}.csv"
            out.to_csv(path, index=False)
            
            log.info(f"  + {name}: {len(out)} rows  [{out['Date'].iloc[0]} -> {out['Date'].iloc[-1]}]")
            log.info(f"  -> saved: {path}")

            time.sleep(DELAY)

        except Exception as e:
            log.error(f"  x {name}: {e}")


# Print summary of fetched data files
def print_summary() -> None:
    log.info("Summary")

    log.info("VN Stocks:")
    for symbol in SYMBOLS:
        path = PRICES_DIR / f"{symbol}.csv"
        if path.exists():
            df = pd.read_csv(path)
            log.info(f"  {symbol:5}: {len(df):>5} rows  [{df['Date'].iloc[0]} -> {df['Date'].iloc[-1]}]")
        else:
            # Fetch failed for this ticker
            log.warning(f"  {symbol:5}: FILE NOT FOUND")  

    log.info("Macro:")
    # Combine yfinance and FRED names into one list
    for name in list(MACRO_TICKERS.keys()) + list(FRED_SERIES.keys()):  
        path = MACRO_DIR / f"{name}.csv"
        if path.exists():
            df = pd.read_csv(path)
            log.info(f"  {name:12}: {len(df):>5} rows  [{df['Date'].iloc[0]} -> {df['Date'].iloc[-1]}]")
        else:
            log.warning(f"  {name:12}: FILE NOT FOUND")


# Only execute when run directly, not when imported by another module
if __name__ == "__main__":  
    log.info(f"Historical data pull: {START_DATE} -> {END_DATE}")

    # Step 1: fetch 6 VN tickers
    fetch_all_symbols()     
    # Step 2: fetch international macro
    fetch_macro_yfinance()  
    # Step 3: fetch fed rate from FRED (skipped if no API key)
    fetch_macro_fred()      
    # Step 4: print row counts and date ranges for all output files
    print_summary()         

    # Corrected final log message to match predefined directories
    parent_dir = PRICES_DIR.parent
    log.info(f"Done. Data saved to {parent_dir}")