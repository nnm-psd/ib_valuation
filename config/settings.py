"""
Central configuration. Keep secrets out of here -- use a .env file + python-dotenv
if you add any API keys later (e.g. a paid market data provider).
"""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DATA_CACHE_DIR = ROOT_DIR / "data" / "cache"

DB_PATH = DATA_PROCESSED_DIR / "valuation_lab.db"
DB_URL = f"sqlite:///{DB_PATH}"

# filings.xbrl.org base -- verify exact endpoints against current docs
# (https://filings.xbrl.org) before relying on this in production.
FILINGS_XBRL_ORG_BASE = "https://filings.xbrl.org"
FILINGS_XBRL_ORG_API = f"{FILINGS_XBRL_ORG_BASE}/api/filings"

# AMF ONDE portal -- fallback / cross-check for French issuers specifically
AMF_ONDE_BASE = "https://www.data.gouv.fr"  # placeholder, AMF's own portal also works

# Default valuation assumptions (overridable per model run)
DEFAULT_MARKET_RISK_PREMIUM = 0.05      # France/Eurozone equity risk premium, sanity-check against current Damodaran data
DEFAULT_TERMINAL_GROWTH_RATE = 0.02     # long-run nominal GDP-ish assumption
DEFAULT_TAX_RATE_FR = 0.25              # French corporate tax rate (IS), verify current rate
