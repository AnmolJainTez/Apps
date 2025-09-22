import streamlit as st
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
import warnings
from datetime import datetime

warnings.filterwarnings("ignore", category=FutureWarning)

# ---- CONFIG ----
BASE_URL = "https://companiesmarketcap.com/usa/largest-companies-in-the-usa-by-market-cap/"
NUM_PAGES = 2   # Change to 3, 4... if more pages exist


# ---- Scraping ----
def scrape_symbols():
    """Scrape top US companies across multiple pages with ticker, name, and price."""
    symbols, names, prices = [], [], []

    for page in range(1, NUM_PAGES + 1):
        url = BASE_URL if page == 1 else f"{BASE_URL}?page={page}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")

        rows = soup.select("table tbody tr")
        for row in rows:
            name_tag = row.select_one("div.company-name")
            symbol_tag = row.select_one("div.company-code")
            cols = row.find_all("td")

            if not name_tag or not symbol_tag or len(cols) < 5:
                continue

            name = name_tag.get_text(strip=True)
            symbol = symbol_tag.get_text(strip=True)
            price_str = cols[4].get_text(strip=True).replace("$", "").replace(",", "")

            try:
                price = float(price_str)
            except:
                price = None

            names.append(name)
            symbols.append(symbol)
            prices.append(price)

    return symbols, names, prices


# ---- YFinance Analysis ----
def analyze(symbols, prices):
    """Run 20-day OHLC analysis using yfinance (slow)."""
    results = []
    latest_date = None
    for idx, ticker in enumerate(symbols):
        try:
            data = yf.download(ticker, period="20d", interval="1d", progress=False, auto_adjust=False)
            if data.empty:
                continue

            data = data.round(2)

            high_20 = float(data["High"].max())
            low_20 = float(data["Low"].min())
            current_price = prices[idx]

            results.append([ticker, st.session_state.names[idx], current_price, high_20, low_20])

            if latest_date is None or data.index[-1] > latest_date:
                latest_date = data.index[-1]

        except Exception as e:
            st.warning(f"⚠️ Skipping {ticker}: {e}")

    df = pd.DataFrame(results, columns=["Ticker", "Name", "Current Price", "20D High", "20D Low"])
    return df, latest_date


# ---- STREAMLIT APP ----
st.title("📊 US Top 200 Stocks – 20D High/Low Scanner")

# Keep data across reruns
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "symbols" not in st.session_state:
    st.session_state.symbols, st.session_state.names, st.session_state.prices = [], [], []
if "last_full_refresh" not in st.session_state:
    st.session_state.last_full_refresh = "Never"
if "last_quick_refresh" not in st.session_state:
    st.session_state.last_quick_refresh = "Never"

# ---- Full Refresh ----
if st.button("🔄 Full Refresh (update 20D High/Low + Prices)"):
    st.session_state.symbols, st.session_state.names, st.session_state.prices = scrape_symbols()
    st.session_state.df, latest_date = analyze(st.session_state.symbols, st.session_state.prices)
    st.session_state.last_full_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.latest_data_date = latest_date.strftime("%Y-%m-%d") if latest_date else "N/A"

# ---- Quick Refresh ----
if st.button("⚡ Quick Refresh (update only Current Prices)"):
    if st.session_state.symbols:
        _, _, new_prices = scrape_symbols()
        st.session_state.df["Current Price"] = new_prices
        st.session_state.last_quick_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        st.warning("Please run a Full Refresh first!")

# ---- Show Filtered Data ----
if not st.session_state.df.empty:
    above_high_df = st.session_state.df[
        st.session_state.df["Current Price"] > st.session_state.df["20D High"]
    ]
    below_low_df = st.session_state.df[
        st.session_state.df["Current Price"] < st.session_state.df["20D Low"]
    ]

    st.subheader("📈 Above 20D High")
    if not above_high_df.empty:
        st.dataframe(above_high_df)
    else:
        st.write("None")

    st.subheader("📉 Below 20D Low")
    if not below_low_df.empty:
        st.dataframe(below_low_df)
    else:
        st.write("None")

# ---- Status ----
st.markdown(f"**Last Full Refresh:** {st.session_state.last_full_refresh}")
st.markdown(f"**Last Quick Refresh:** {st.session_state.last_quick_refresh}")
if "latest_data_date" in st.session_state:
    st.markdown(f"**Latest Market Data Date:** {st.session_state.latest_data_date}")

# ---- Source Link ----
st.markdown("---")
st.markdown(f"[🔗 Source: CompaniesMarketCap.com]({BASE_URL}) (Pages 1–{NUM_PAGES})")
