# International Cost of Capital — Streamlit

A Streamlit app to compare a project's **cost of equity, cost of borrowing, and WACC in USD versus the currency of a selected country**. Designed for the Kellogg international finance assignment.

## Launch locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy (GitHub + Streamlit Community Cloud)

1. Create a **new GitHub repository** (e.g., `international-cost-of-capital`).
2. Upload **all files and the `data/` folder** from this project (including `app.py`, `finance.py`, `data_sources.py`, `requirements.txt`, `README.md`, `data/reference_snapshot.json`). The `tests/` folder is recommended.
3. In [Streamlit Community Cloud](https://share.streamlit.io/), choose **Create app → Deploy a public app from GitHub**.
4. Select the repository, branch `main`, and main file `app.py`; deploy. No API key is needed.
5. Open the app and click **Refresh all source data**. Check the **Data sources, observation dates and retrieval diagnostics** panel before submission.

A complete downloadable zip is provided alongside the files; extract before uploading to GitHub. Streamlit's public deployment requires access to the referenced third-party sites and may encounter temporary scraping or rate limits.

## Defaults

| Control | Default |
|---|---|
| Industry | Software (System & Application) |
| Target country | United States |
| Project tax jurisdiction | U.S. statutory rate |
| Equity risk premium | 6.5% |
| Debt / financing | 30% |
| USD BBB spread | Damodaran Baa2/BBB, large non-financial firms |
| Foreign BBB spread | Automatically calculated; can be overwritten |

Selecting the United States itself displays equal currency results by default. You can select a preloaded country or **Other (manual / custom)** to model a country not listed; manual tax/bond-yield entries are then required. Local currency units are indicated with ISO codes (EUR, MXN, etc.). A country without a 10-year quote can also be used with a manual yield override.

## Calculations — IMPORTANT: check against your class notes

**These are the implemented, provisional formulas, since the assignment does not include the actual class formulas.** All rate inputs in the UI are *percentage points* (6.5 = 6.5%); in the formulas below, rates are decimals.

- Financing ratio: `D/E = debt_share / (1 - debt_share)`.
- Relevered beta: `beta_L = beta_U × [1 + (1 - T) × D/E]`.
- USD cost of equity: `Ke_USD = U.S. 10Y yield + beta_L × ERP`.
- Local cost of equity: `Ke_local = local 10Y yield + beta_L × ERP`.
- USD cost of debt: `Kd_USD = U.S. 10Y yield + USD BBB spread`.
- Auto local BBB spread: `spread_local = spread_USD × (1 + local 10Y yield) / (1 + U.S. 10Y yield)`.
- Local cost of debt: `Kd_local = local 10Y yield + spread_local`, unless the local spread has been manually overwritten.
- WACC for each currency: `WACC = (1 - debt_share) × Ke + debt_share × Kd × (1 - T)`.

**The automatic local BBB spread is a Fisher-style scaling assumption**, not an observed BBB bond spread. Likewise, using each country's 10-year government bond yield as a risk-free yield simplifies matters: emerging market sovereign yields can contain country/default and liquidity risk, and government bond yields do not necessarily make a perfectly consistent currency-translation model. The same numeric ERP, debt share, and **one chosen project tax rate** apply to both columns, as requested. No FX spot rate or cash flows are converted.

## Sources and time stamps

| Input | Primary source / approach | Source period as checked on 14 Nov 2026 |
|---|---|---|
| U.S. unlevered industry betas | [Damodaran XLS](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls), with [HTML fallback](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html). Uses exact **Unlevered beta**, not cash-adjusted beta. | Jan 2026 |
| Baa2/BBB default spread | [Damodaran ratings](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html) — **large non-financial firms** | Jan 2026; 1.11% in dated snapshot |
| Combined statutory corporate tax rate | [OECD Corporate Income Tax Rates Database](https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html), queried via OECD SDMX API; national+subnational **S13 / ST** rates | 2026 database, updated 21 Jul 2026 |
| US and local 10Y yields | [Trading Economics](https://tradingeconomics.com/bonds), via `/<country>/government-bond-yield` public HTML (no API key) | Per-country quote date; fallback snapshot 13 Nov 2026 |

**The handout's OECD Corporate Tax Statistics 2024 page is historical.** Its successor is [Corporate Tax Statistics 2026](https://www.oecd.org/en/publications/corporate-tax-statistics-2026_73af6222-en/full-report/statutory-corporate-income-tax-rates_ce84abb9.html). The snapshot contains the 2026 combined rates visible in the OECD-backed series and should *not* be mistaken for a fresh API response.

### Refresh, fallbacks and transparent provenance

- On startup, live-fetch industry betas, the U.S. BBB spread, OECD rates and 10-year quotes. The Streamlit cache has a **1-hour TTL**.
- **Refresh all source data** clears the caches and requests the sites again; it does not simply change the on-screen timestamp.
- If a source blocks scraping or changes its HTML, the app displays **Dated snapshot** with a clearly marked **source observation date**; it does not pretend the snapshot is live. The beta backup contains **all 94 January 2026 U.S. sectors** from the source page; the all-industry comparison displays a dated-data warning until live data is retrieved.
- For countries without a source value, use the corresponding manual input; don't infer a yield or tax rate.
- The **Data sources** panel shows source links, dataset periods, fetch times (only when live), and errors. Exports include source metadata and all applied assumptions.
- Corporate statutory rates differ from effective project tax rates. The project tax selection is a modeling assumption, not tax advice.

> Scraping third-party sites is inherently fragile. No API key is used, but unauthenticated access is not guaranteed and may be limited by site rules. Avoid rapid automated refreshes.

## Verification

Run the pure-math tests (they do not require network access):

```bash
python -m unittest discover -s tests -v
```

The tests independently confirm:

1. The USD values for a hand-calculated software project, with `beta_U=1.23`, `T=25.53%`, `D/V=30%`, `ERP=6.5%`, `USD 10Y=5.145%`, `USD BBB=1.11%`.
2. Equal 10Y government yields yield equal USD and foreign equity costs, debt costs and WACC when the local BBB override is off.
3. At 0% debt, WACC equals the relevant cost of equity.
4. Overriding only the foreign BBB spread changes only the foreign borrowing cost / WACC; USD numbers remain unchanged.
5. The foreign spread default obeys its documented yield ratio.

An accompanying **Excel verification workbook** contains an independent formula-driven example for checking the same values. Keep that workbook separate from live fetching: it fixes a specific source-dated example for reproducibility.

## Files

- `app.py`: Streamlit interface, selectors, overrides, comparisons, downloads, provenance and in-app verification.
- `finance.py`: small, independently testable financial calculation functions.
- `data_sources.py`: data adapters and retrieval logic, with transparent source-dated fallbacks.
- `data/reference_snapshot.json`: explicit offline recovery inputs **not live market data**.
- `tests/test_finance.py`: calculator-style verification test suite.
- `requirements.txt`: Streamlit Cloud dependencies.
- `README.md`: this guide.
