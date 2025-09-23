import streamlit as st
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
import warnings
from datetime import datetime

warnings.filterwarnings("ignore", category=FutureWarning)

URL = "https://companiesmarketcap.com/usa/largest-companies-in-the-usa-by-market-cap/"

# ---- Scraping ----
def scrape_symbols():
    """Scrape top 100 US companies with ticker and name (no price)."""
    r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")

    symbols, names = [], []
    rows = soup.select("table tbody tr")

    for row in rows:
        name_tag = row.select_one("div.company-name")
        symbol_tag = row.select_one("div.company-code")

        if not name_tag or not symbol_tag:
            continue

        name = name_tag.get_text(strip=True)
        symbol = symbol_tag.get_text(strip=True)

        names.append(name)
        symbols.append(symbol)

        if len(names) == 100:  # only top 100
            break

    return symbols, names


# ---- YFinance Analysis ----
def analyze(symbols, names):
    """Run 20-day OHLC analysis using yfinance."""
    results = []
    latest_date = None
    for idx, ticker in enumerate(symbols):
        try:
            yf_symbol = ticker.replace(".", "-")
            data = yf.download(yf_symbol, period="20d", interval="1d",
                               progress=False, auto_adjust=False)
            if data.empty:
                continue

            data = data.round(2)
            last_date = data.index[-1].date()
            today = datetime.now().date()
            # print(last_date, today)

            if last_date == today:
                data = data.iloc[:-1]

            high_20 = float(data["High"].max())
            low_20 = float(data["Low"].min())
            current_price = float(data["Close"].iloc[-1])   # last close only for bootstrap

            results.append([ticker, names[idx], current_price, high_20, low_20])
            if latest_date is None or data.index[-1] > latest_date:
                latest_date = data.index[-1]

        except Exception as e:
            st.warning(f"⚠️ Skipping {ticker}: {e}")

    df = pd.DataFrame(results, columns=["Ticker", "Name", "Current Price", "20D High", "20D Low"])
    return df, latest_date


# ---- STREAMLIT APP ----
st.title("📊 US Top 100 Stocks – 20D High/Low Scanner")

# Keep data across reruns
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "symbols" not in st.session_state:
    st.session_state.symbols, st.session_state.names = [], []
if "last_full_refresh" not in st.session_state:
    st.session_state.last_full_refresh = "Never"
if "last_quick_refresh" not in st.session_state:
    st.session_state.last_quick_refresh = "Never"

# ---- Full Refresh ----
if st.button("🔄 Full Refresh (update 20D High/Low + Prices)"):
    st.session_state.symbols, st.session_state.names = scrape_symbols()
    st.session_state.df, latest_date = analyze(st.session_state.symbols, st.session_state.names)
    st.session_state.last_full_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.latest_data_date = latest_date.strftime("%Y-%m-%d") if latest_date else "N/A"

# ---- Quick Refresh ----
if st.button("⚡ Quick Refresh (update only Current Prices)"):
    if st.session_state.symbols:
        # scrape fresh prices from CompaniesMarketCap
        r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table tbody tr")
        price_map = {}
        for row in rows:
            sym_tag = row.select_one("div.company-code")
            cols = row.find_all("td")
            if not sym_tag or len(cols) < 5:
                continue
            sym = sym_tag.get_text(strip=True)
            price_str = cols[4].get_text(strip=True).replace("$", "").replace(",", "")
            try:
                price_map[sym] = float(price_str)
            except:
                price_map[sym] = None

        # update by ticker key
        st.session_state.df["Current Price"] = st.session_state.df["Ticker"].map(price_map)
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

# ---- Check New High/Low ----
if st.button("🆕 Check New 20D High/Low (today vs stored)"):
    if st.session_state.symbols:
        new_high_rows, new_low_rows = [], []

        for idx, ticker in enumerate(st.session_state.symbols):
            try:
                yf_symbol = ticker.replace(".", "-")
                data = yf.download(yf_symbol, period="2d", interval="1d",
                                   progress=False, auto_adjust=False)
                if data.empty or len(data) < 1:
                    continue

                last_row = data.iloc[-1]  # latest entry
                today_high = float(last_row["High"])
                today_low = float(last_row["Low"])

                prev_high = st.session_state.df.loc[
                    st.session_state.df["Ticker"] == ticker, "20D High"
                ].values[0]
                prev_low = st.session_state.df.loc[
                    st.session_state.df["Ticker"] == ticker, "20D Low"
                ].values[0]

                if today_high > prev_high:
                    new_high_rows.append([
                        ticker, st.session_state.names[idx],
                        today_high, prev_high
                    ])
                if today_low < prev_low:
                    new_low_rows.append([
                        ticker, st.session_state.names[idx],
                        today_low, prev_low
                    ])
            except Exception as e:
                st.warning(f"⚠️ Skipping {ticker}: {e}")

        if new_high_rows:
            st.subheader(f"🚀 New 20D Highs Today ({len(new_high_rows)})")
            st.dataframe(pd.DataFrame(new_high_rows,
                                      columns=["Ticker", "Name", "Today's High", "Previous 20D High"]))
        else:
            st.write("No new highs today.")

        if new_low_rows:
            st.subheader(f"📉 New 20D Lows Today ({len(new_low_rows)})")
            st.dataframe(pd.DataFrame(new_low_rows,
                                      columns=["Ticker", "Name", "Today's Low", "Previous 20D Low"]))
        else:
            st.write("No new lows today.")
    else:
        st.warning("Please run a Full Refresh first!")


# ---- Status ----
st.markdown(f"**Last Full Refresh:** {st.session_state.last_full_refresh}")
st.markdown(f"**Last Quick Refresh:** {st.session_state.last_quick_refresh}")
if "latest_data_date" in st.session_state:
    st.markdown(f"**Latest Market Data Date:** {st.session_state.latest_data_date}")

# ---- Source Link ----
st.markdown("---")
st.markdown(f"[🔗 Source: CompaniesMarketCap.com]({URL})")
