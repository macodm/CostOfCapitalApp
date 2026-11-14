"""Live public-source adapters with clearly labelled, dated offline recovery values."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
import unicodedata

from bs4 import BeautifulSoup
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
SNAPSHOT = json.loads((ROOT / "data" / "reference_snapshot.json").read_text(encoding="utf-8"))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EducationalCostOfCapitalApp/1.0; +https://streamlit.io)",
    "Accept-Language": "en-US,en;q=0.9",
}
BETA_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
BETA_HTML_URL = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html"
RATING_URL = "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html"
OECD_URL = "https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html"
OECD_API_URL = "https://sdmx.oecd.org/public/rest/v1/data/OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,2.0/.A..ST..S13...?startPeriod=2025&dimension_at_observation=AllDimensions"
TE_URL = "https://tradingeconomics.com/bonds"

# Quote availability is not guaranteed for every country. The manual yield and
# tax switches deliberately allow any country (including custom entries).
CURRENCIES = {
    "Argentina": "ARS", "Australia": "AUD", "Austria": "EUR", "Belgium": "EUR",
    "Brazil": "BRL", "Bulgaria": "EUR", "Canada": "CAD", "Chile": "CLP",
    "China": "CNY", "Colombia": "COP", "Costa Rica": "CRC", "Croatia": "EUR",
    "Czechia": "CZK", "Denmark": "DKK", "Egypt": "EGP", "Estonia": "EUR",
    "Finland": "EUR", "France": "EUR", "Germany": "EUR", "Greece": "EUR",
    "Hong Kong": "HKD", "Hungary": "HUF", "Iceland": "ISK", "India": "INR",
    "Indonesia": "IDR", "Ireland": "EUR", "Israel": "ILS", "Italy": "EUR",
    "Japan": "JPY", "Latvia": "EUR", "Lithuania": "EUR", "Luxembourg": "EUR",
    "Malaysia": "MYR", "Mexico": "MXN", "Netherlands": "EUR",
    "New Zealand": "NZD", "Norway": "NOK", "Peru": "PEN", "Philippines": "PHP",
    "Poland": "PLN", "Portugal": "EUR", "Romania": "RON", "Russia": "RUB",
    "Saudi Arabia": "SAR", "Singapore": "SGD", "Slovakia": "EUR",
    "Slovenia": "EUR", "South Africa": "ZAR", "South Korea": "KRW",
    "Spain": "EUR", "Sweden": "SEK", "Switzerland": "CHF", "Thailand": "THB",
    "Turkey": "TRY", "United Arab Emirates": "AED", "United Kingdom": "GBP",
    "United States": "USD", "Vietnam": "VND",
}
COUNTRY_TO_ISO3 = {
    "Argentina":"ARG","Australia":"AUS","Austria":"AUT","Belgium":"BEL",
    "Brazil":"BRA","Bulgaria":"BGR","Canada":"CAN","Chile":"CHL",
    "China":"CHN","Colombia":"COL","Costa Rica":"CRI","Croatia":"HRV",
    "Czechia":"CZE","Denmark":"DNK","Egypt":"EGY","Estonia":"EST",
    "Finland":"FIN","France":"FRA","Germany":"DEU","Greece":"GRC",
    "Hong Kong":"HKG","Hungary":"HUN","Iceland":"ISL","India":"IND",
    "Indonesia":"IDN","Ireland":"IRL","Israel":"ISR","Italy":"ITA",
    "Japan":"JPN","Latvia":"LVA","Lithuania":"LTU","Luxembourg":"LUX",
    "Malaysia":"MYS","Mexico":"MEX","Netherlands":"NLD","New Zealand":"NZL",
    "Norway":"NOR","Peru":"PER","Philippines":"PHL","Poland":"POL",
    "Portugal":"PRT","Romania":"ROU","Russia":"RUS","Saudi Arabia":"SAU",
    "Singapore":"SGP","Slovakia":"SVK","Slovenia":"SVN","South Africa":"ZAF",
    "South Korea":"KOR","Spain":"ESP","Sweden":"SWE","Switzerland":"CHE",
    "Thailand":"THA","Turkey":"TUR","United Arab Emirates":"ARE",
    "United Kingdom":"GBR","United States":"USA","Vietnam":"VNM",
}
SLUGS = {"Czechia": "czech-republic", "South Korea": "south-korea", "Turkey": "turkey"}


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def package(data, source, period, url, status="Live", error=""):
    return {"data": data, "status": status, "period": period, "url": url,
            "fetched_at": utc_now() if status == "Live" else "Not fetched (bundled snapshot)",
            "error": str(error)[:240]}


def request(url, headers=None):
    r = requests.get(url, timeout=14, headers={**HEADERS, **(headers or {})})
    r.raise_for_status()
    return r


def _parse_betas_table(df):
    df = df.copy()
    df.columns = [str(v).replace("\xa0", " ").strip().lower() for v in df.columns]
    industry_col = next((c for c in df if c == "industry name"), None)
    beta_col = next((c for c in df if c == "unlevered beta"), None)
    if not industry_col or not beta_col:
        raise ValueError("Damodaran industry or exact unlevered-beta column was not found")
    rows = {}
    for _, row in df.iterrows():
        name = str(row[industry_col]).strip()
        value = pd.to_numeric(row[beta_col], errors="coerce")
        if (name and name.lower() != "nan" and not name.lower().startswith("total market")
                and pd.notna(value) and 0 <= float(value) < 10):
            rows[name] = float(value)
    if len(rows) < 30 or "Software (System & Application)" not in rows:
        raise ValueError("Damodaran beta table looks incomplete")
    return dict(sorted(rows.items()))


def fetch_betas():
    errors = []
    try:
        r = request(BETA_URL)
        raw = pd.read_excel(BytesIO(r.content), header=None, engine="xlrd")
        headers = [str(x).strip().lower() for x in raw.iloc[:, 0].tolist()]
        ix = next(i for i, x in enumerate(headers) if x == "industry name")
        raw.columns = raw.iloc[ix].tolist()
        data = _parse_betas_table(raw.iloc[ix + 1:])
        return package(data, "Damodaran, U.S. industry betas", "Dataset: January 2026 (check source page for updates)", BETA_URL)
    except Exception as ex:
        errors.append("XLS: " + str(ex))
    try:
        tables = pd.read_html(StringIO(request(BETA_HTML_URL).text))
        for table in tables:
            try:
                data = _parse_betas_table(table)
                return package(data, "Damodaran, U.S. industry betas", "Source page: January 2026 (check for later updates)", BETA_HTML_URL)
            except ValueError:
                continue
        raise ValueError("No valid beta table")
    except Exception as ex:
        errors.append("HTML: " + str(ex))
    return package(SNAPSHOT["us_industry_unlevered_betas"], "Damodaran beta reference",
                   "January 2026 — full 94-sector dated reference", BETA_HTML_URL,
                   "Dated snapshot", "; ".join(errors))


def fetch_bbb_spread():
    try:
        soup = BeautifulSoup(request(RATING_URL).text, "html.parser")
        for row in soup.find_all("tr"):
            pieces = [el.get_text(" ", strip=True) for el in row.find_all(["td", "th"], recursive=False)]
            for i, item in enumerate(pieces):
                if re.search(r"Baa2\s*/\s*BBB\b", item, flags=re.I):
                    # The FIRST BBB is the large non-financial column (not financial firms).
                    if i + 1 < len(pieces):
                        v = re.search(r"(\d+(?:\.\d+)?)\s*%", pieces[i+1])
                        if v:
                            return package(float(v.group(1)), "Damodaran, large non-financial Baa2/BBB",
                                           "Source page: January 2026 (check for later updates)", RATING_URL)
        raise ValueError("Large nonfinancial Baa2/BBB row not found")
    except Exception as ex:
        return package(SNAPSHOT["usd_bbb_spread_pct"], "Damodaran BBB reference", "January 2026",
                       RATING_URL, "Dated snapshot", ex)


def _parse_oecd_csv(text):
    df = pd.read_csv(StringIO(text), low_memory=False)
    df.columns = [str(c).upper().strip() for c in df.columns]
    if not {"REF_AREA", "TIME_PERIOD", "OBS_VALUE"}.issubset(df.columns):
        raise ValueError(f"Unexpected OECD columns: {list(df.columns)[:10]}")
    # The source query requests S13 (combined general-government) + ST rates.
    # Enforce dimensions if the server returns a broader dataset.
    for col in df.columns:
        if col in ("GOV_LEVEL", "GOVERNMENT", "SECTOR", "GOV", "INSTITUTIONAL_SECTOR"):
            if "S13" in set(df[col].dropna().astype(str)):
                df = df[df[col].astype(str) == "S13"]
    for col in ("TAX_RATE", "TAX_TYPE", "TAX", "MEASURE", "RATE_TYPE"):
        if col in df.columns and "ST" in set(df[col].dropna().astype(str)):
            df = df[df[col].astype(str) == "ST"]
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df["TIME_PERIOD"] = pd.to_numeric(df["TIME_PERIOD"], errors="coerce")
    df = df.dropna(subset=["OBS_VALUE", "TIME_PERIOD"])
    df = df.sort_values("TIME_PERIOD").drop_duplicates("REF_AREA", keep="last")
    iso_values = dict(zip(df["REF_AREA"].astype(str), df["OBS_VALUE"].astype(float)))
    result = {name: iso_values[code] for name, code in COUNTRY_TO_ISO3.items()
              if code in iso_values and 0 <= iso_values[code] <= 100}
    if not {"United States", "Mexico"}.issubset(result):
        raise ValueError("US and Mexico were missing from OECD combined statutory rates")
    period = str(int(df["TIME_PERIOD"].max()))
    return result, period


def fetch_tax_rates():
    errors = []
    urls = [OECD_API_URL,
            OECD_API_URL.replace("/rest/v1/data/", "/rest/data/")]
    for url in urls:
        try:
            r = request(url, headers={"Accept": "csvfile"})
            result, period = _parse_oecd_csv(r.text)
            return package(result, "OECD combined statutory tax rates (S13)",
                           f"Latest annual data through {period} (per-country periods may differ)", url)
        except Exception as ex:
            errors.append(str(ex))
    return package(SNAPSHOT["combined_statutory_tax_rates_pct"],
                   "OECD 2026 rates (bundled dated reference)", "2026 — bundled, not a live OECD fetch",
                   OECD_URL, "Dated snapshot", "; ".join(errors))


def slug(country):
    if country in SLUGS:
        return SLUGS[country]
    clean = unicodedata.normalize("NFKD", country).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", clean.lower()).strip("-")


def fetch_bond_yield(country):
    # Country detail pages expose 'Actual 5.1450' in server-rendered HTML;
    # the main /bonds table is sometimes client-rendered and cannot be scraped.
    if country == "Other (manual / custom)":
        raise ValueError("Custom country has no automatic Trading Economics URL")
    url = f"https://tradingeconomics.com/{slug(country)}/government-bond-yield"
    try:
        soup = BeautifulSoup(request(url).text, "html.parser")
        title = soup.find("h1")
        heading = title.get_text(" ", strip=True) if title else ""
        if not any(word in heading.lower() for word in ("bond", "treasury", "government")) or ("10" not in heading):
            raise ValueError(f"Unexpected Trading Economics quote page: {heading[:90]}")
        text = soup.get_text(" ", strip=True)
        match = re.search(r"\bActual\s+(-?\d{1,3}(?:\.\d{1,5})?)\b", text)
        if not match:
            raise ValueError("Actual 10Y government yield not found (page structure may have changed)")
        value = float(match.group(1))
        if not -20 < value < 150:
            raise ValueError("Government yield outside expected range")
        # TE quote date and retrieval time are different things.
        match_date = re.search(r"\bon\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2}", text)
        period = "Quote: " + match_date.group(0)[3:] if match_date else "Quote date not published in machine-readable HTML"
        return package(value, f"Trading Economics 10Y — {country}", period, url)
    except Exception as ex:
        if country in SNAPSHOT["ten_year_bond_yields_pct"]:
            return package(SNAPSHOT["ten_year_bond_yields_pct"][country],
                           f"Trading Economics 10Y — {country} (bundled quote)",
                           f"Quote: {SNAPSHOT['bond_quote_date']} — not live", url,
                           "Dated snapshot", ex)
        return package(None, f"Trading Economics 10Y — {country}", "Not available",
                       url, "Unavailable — manual entry required", ex)
