#!/usr/bin/env python3
import argparse
import re
import time
import random
from typing import List, Dict, Optional

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

APP_URL = "https://app.datacamp.com/learn/courses"
LEVEL_RE = re.compile(r"\b(Basic|Beginner|Intermediate|Advanced)\b", re.I)
DURATION_RE = re.compile(
    r"(?:Over\s+)?\d+(?:\s*(?:–|-|to)\s*\d+)?\s*(?:hr|hrs|hour|hours)\b",
    re.I,
)


def jitter(a: float = 0.25, b: float = 0.6) -> None:
    time.sleep(random.uniform(a, b))


def make_driver(attach_port: Optional[int] = None) -> webdriver.Chrome:
    opts = ChromeOptions()
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--lang=en-US")
    if attach_port:
        opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{attach_port}")
    service = ChromeService()
    drv = webdriver.Chrome(service=service, options=opts)
    drv.set_page_load_timeout(90)
    drv.implicitly_wait(2)
    return drv


def wait_for_grid(driver: webdriver.Chrome, timeout: int = 45) -> None:
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "a[href^='/learn/courses/']")
        )
    )


def expand_all_courses(driver: webdriver.Chrome) -> None:
    """
    Scroll + click until all courses are visible.
    """
    last, stable = -1, 0
    while True:
        driver.execute_script("window.scrollBy(0,1200);")
        jitter(0.2, 0.4)
        curr = len(
            driver.find_elements(By.CSS_SELECTOR, "a[href^='/learn/courses/']")
        )
        if curr > last:
            last, stable = curr, 0
        else:
            stable += 1
        if stable >= 3:
            break
    print(f"[expand] final count: {last}")


def extract_urls(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    seen, urls = set(), []
    for a in soup.select("a[href^='/learn/courses/']"):
        href = a.get("href", "")
        if href and href.startswith("/learn/courses/"):
            url = "https://app.datacamp.com" + href.split("?")[0]
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def extract_course_details(html: str) -> Dict[str, Optional[str]]:
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one("h1")
    title = title_el.get_text(" ", strip=True) if title_el else None
    header = title_el.find_parent() if title_el else soup

    # level
    level = None
    if header:
        m = LEVEL_RE.search(header.get_text(" ", strip=True))
        if m:
            level = m.group(1).title()

    # duration
    duration = None
    if header:
        m2 = DURATION_RE.search(header.get_text(" ", strip=True))
        if m2:
            duration = m2.group(0)

    # description
    desc = None
    desc_hdr = soup.find(
        ["h2", "h3"], string=lambda t: t and t.strip().lower() == "description"
    )
    if desc_hdr:
        parts, sib, hops = [], desc_hdr.find_next_sibling(), 0
        while sib and hops < 12:
            if sib.name in ("h2", "h3"):
                break
            if sib.name in ("p", "div", "section", "article"):
                txt = " ".join(sib.stripped_strings)
                if txt:
                    parts.append(txt)
            sib = sib.find_next_sibling()
            hops += 1
        if parts:
            desc = " ".join(parts).strip()
    if not desc:
        jd = soup.find("script", {"type": "application/ld+json"})
        if jd:
            import json

            parsed = json.loads(jd.string or "{}")
            desc = parsed.get("description")

    return {
        "title": title,
        "level": level,
        "duration": duration,
        "description_full": desc,
    }


# ---------------------------------------------------------------------------
# Scraping public API (for DAGs / callers)
# ---------------------------------------------------------------------------


def scrape_datacamp_courses() -> List[Dict[str, Optional[str]]]:
    """
    Scrape all DataCamp course detail pages and return a list of dict rows:
      {"title", "level", "duration", "description_full", "url"}.
    """
    driver = make_driver()
    results: List[Dict[str, Optional[str]]] = []
    try:
        driver.get(APP_URL)
        wait_for_grid(driver)
        expand_all_courses(driver)
        urls = extract_urls(driver.page_source)
        print(f"[discover] total {len(urls)} URLs")

        for i, u in enumerate(urls, 1):
            try:
                driver.get(u)
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
                )
                time.sleep(0.6)
                details = extract_course_details(driver.page_source)
                details["url"] = u
                results.append(details)
                if i % 20 == 0:
                    print(f"[{i}/{len(urls)}] {details.get('title')}")
            except TimeoutException:
                print(f"[timeout] {u}")
                results.append(
                    {
                        "title": None,
                        "level": None,
                        "duration": None,
                        "description_full": None,
                        "url": u,
                    }
                )
            except WebDriverException as e:
                print(f"[webdriver-error] {u}: {e}")
                results.append(
                    {
                        "title": None,
                        "level": None,
                        "duration": None,
                        "description_full": None,
                        "url": u,
                    }
                )
    finally:
        driver.quit()

    print(f"[done] scraped {len(results)} course rows")
    return results


def scrape_datacamp_rows_sync() -> List[Dict[str, Optional[str]]]:
    """
    Simple alias used by Airflow DAGs.
    """
    return scrape_datacamp_courses()


# ---------------------------------------------------------------------------
# Transform for Supabase demo schema
# ---------------------------------------------------------------------------


def _derive_course_id(url: Optional[str]) -> str:
    """
    Best-effort stable ID from URL path (e.g.
      'https://app.datacamp.com/learn/courses/python-introduction'
      -> 'learn/courses/python-introduction'
    """
    if not url:
        return ""
    if "app.datacamp.com" in url:
        path = url.split("app.datacamp.com", 1)[-1].strip("/")
    else:
        path = url.strip("/")
    return path or url.strip("/")


def transform_for_db(
    rows: List[Dict[str, Optional[str]]]
) -> List[Dict[str, Optional[str]]]:
    """
    Shape raw scrape output into the unified demo schema:
      course_id, title, provider, url, price, duration, level, language,
      rating, reviews_count, last_updated, keyword, description,
      what_you_will_learn, skills, recommended_experience
    """
    out: List[Dict[str, Optional[str]]] = []
    for r in rows:
        url = r.get("url") or ""
        out.append(
            {
                "course_id": _derive_course_id(url),
                "title": r.get("title") or "",
                "provider": "DataCamp",
                "url": url,
                "price": None,  # not scraped; keep as NULL
                "duration": r.get("duration") or "",
                "level": r.get("level") or "",
                "language": "English",  # DataCamp catalog default
                "rating": None,  # not scraped
                "reviews_count": None,  # not scraped
                "last_updated": None,  # not scraped
                "keyword": None,  # no keyword-based search here
                "description": r.get("description_full") or "",
                "what_you_will_learn": "",
                "skills": "",
                "recommended_experience": "",
            }
        )
    return out


# ---------------------------------------------------------------------------
# CLI entrypoint: scrape + save to Supabase
# ---------------------------------------------------------------------------


def main():
    """
    When run as a script:
      - Scrape all DataCamp courses
      - Ensure public.datacamp_demo exists
      - Upsert all rows via db_supabase_datacamp
    """
    parser = argparse.ArgumentParser(
        description="Scrape DataCamp course catalog and upsert into Supabase."
    )
    # no args needed for now, but parser kept for future extension
    _ = parser.parse_args()

    rows = scrape_datacamp_rows_sync()
    if not rows:
        print("No DataCamp rows scraped; nothing to write.")
        return

    from scripts.db_supabase_datacamp import ensure_table_exists, upsert_rows

    ensure_table_exists()
    db_rows = transform_for_db(rows)
    upsert_rows(db_rows)

    print(f"✅ Upserted {len(db_rows)} rows into public.datacamp_demo")


if __name__ == "__main__":
    main()
