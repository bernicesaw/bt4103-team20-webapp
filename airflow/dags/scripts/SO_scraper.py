
#!/usr/bin/env python3
"""
Download Stack Overflow Developer Survey (>= min_year, auto-detect newest)
→ save ONLY the public results CSV per year (flat files, no folders, no schema).

Default behavior:
  - Visit https://survey.stackoverflow.co/
  - Discover all "Download Full Data Set" links and extract the year from URL/text
  - Keep all years >= --min-year (default: 2021)
  - Download ZIPs, extract only the public-results CSV, save as:
        <out_dir>/survey_results_public_<YEAR>.csv

Examples:
  python SO_scraper_auto.py --min-year 2021 --out-dir so_survey_datasets
"""

import io
import re
import zipfile
from pathlib import Path
from urllib.parse import urljoin
import argparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://survey.stackoverflow.co/"
TIMEOUT = 30

RETRY = Retry(
    total=8, connect=3, read=3,
    backoff_factor=1.3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "HEAD"],
    raise_on_status=False,
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SO-Survey-Scraper/2.0)",
    "Referer": BASE_URL,
    "Accept": "*/*",
}

YEAR_RE = re.compile(r"\b(20\d{2})\b")

def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    adapter = HTTPAdapter(max_retries=RETRY)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

def fetch_home(session: requests.Session) -> str:
    r = session.get(BASE_URL, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text

def parse_year_links(html: str):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a"):
        text = (a.get_text(strip=True) or "").lower()
        if not text:
            continue
        # The site typically uses 'Download Full Data Set' (case may vary)
        if "download full data set" not in text:
            continue
        href = (a.get("href") or "").strip()
        # try to find year in href or nearby text
        year = None
        for src in (href, text, a.find_parent().get_text(" ", strip=True) if a.find_parent() else ""):
            if not src: 
                continue
            m = YEAR_RE.search(src)
            if m:
                year = int(m.group(1))
                break
        if not href or not year:
            continue
        abs_url = urljoin(BASE_URL, href)
        links.append((year, abs_url))
    # de-dup by year prefer last seen (site order isn't critical)
    seen = {}
    for y,u in links:
        seen[y] = u
    items = sorted(seen.items(), key=lambda x: x[0])
    return items

def download_zip_bytes(session: requests.Session, url: str) -> bytes:
    r = session.get(url, timeout=TIMEOUT, stream=True, allow_redirects=True)
    r.raise_for_status()
    chunks = []
    for chunk in r.iter_content(chunk_size=1024 * 64):
        if chunk:
            chunks.append(chunk)
    return b"".join(chunks)

def choose_public_csv_name(zipf: zipfile.ZipFile, year: int) -> str | None:
    """
    Return the member filename to extract for the 'public results' CSV.
    Heuristics across years:
      - exact 'survey_results_public.csv'
      - any file containing 'survey_results_public'
      - fallback: any CSV with 'public' in name (case-insensitive), excluding 'schema'
    """
    names = [zi.filename for zi in zipf.infolist() if zi.filename.lower().endswith(".csv")]
    lower = [n.lower() for n in names]

    # 1) exact file
    for n, ln in zip(names, lower):
        if ln.endswith("/survey_results_public.csv") or ln == "survey_results_public.csv":
            return n

    # 2) contains survey_results_public
    for n, ln in zip(names, lower):
        if "survey_results_public" in ln:
            return n

    # 3) contains 'public' (avoid schema)
    candidates = [n for n, ln in zip(names, lower) if "public" in ln and "schema" not in ln]
    if candidates:
        # if multiple, prefer shortest basename
        return sorted(candidates, key=lambda x: len(Path(x).name))[0]

    # If nothing matches, warn
    print(f"[warn] No public results CSV detected in {year} ZIP. Found CSVs: {names}")
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-year", type=int, default=2021, help="Only download years >= this (default: 2021)")
    ap.add_argument("--out-dir", type=str, default="so_survey_datasets", help="Output directory")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = make_session()
    html = fetch_home(session)
    year_links = parse_year_links(html)
    # keep only >= min-year
    year_links = [(y,u) for (y,u) in year_links if y >= args.min_year]

    if not year_links:
        raise SystemExit(f"No dataset links found for years >= {args.min_year}.")

    print(f"Found {len(year_links)} dataset links:")
    for y, u in year_links:
        print(f"  {y}: {u}")

    for year, url in year_links:
        out_path = out_dir / f"survey_results_public_{year}.csv"
        if out_path.exists() and out_path.stat().st_size > 0:
            print(f"[skip] {out_path.name} exists.")
            continue

        print(f"[downloading] {year}")
        try:
            zip_bytes = download_zip_bytes(session, url)
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                member_name = choose_public_csv_name(zf, year)
                if not member_name:
                    print(f"[error] Could not find public results CSV for {year}.")
                    continue
                with zf.open(member_name, "r") as src, open(out_path, "wb") as dst:
                    dst.write(src.read())
                print(f"[ok]   {out_path}")
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            print(f"[error] HTTP {code} for {year} at {url}")
        except zipfile.BadZipFile:
            print(f"[error] Corrupted ZIP for {year}")
        except Exception as e:
            print(f"[error] {year}: {e}")

if __name__ == "__main__":
    main()
