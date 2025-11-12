#!/usr/bin/env python3
import argparse
import asyncio
import json
import math
import random
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm as tqdm_async

SEARCH_URL = "https://www.coursera.org/search"
RESULT_PATTERNS = ("/learn/", "/specializations/", "/professional-certificates/")

HEADERS = {
    # Desktop Chrome UA to reduce bot friction
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/119.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

def iso8601_to_readable(iso: str) -> str:
    if not iso or not iso.startswith("P"):
        return iso or ""
    months = re.search(r"(\d+)M(?!T)", iso)
    weeks = re.search(r"(\d+)W", iso)
    days = re.search(r"(\d+)D", iso)
    hours = re.search(r"T(\d+)H", iso)
    parts = []
    if months: parts.append(f"{months.group(1)} month(s)")
    if weeks: parts.append(f"{weeks.group(1)} week(s)")
    if days: parts.append(f"{days.group(1)} day(s)")
    if hours: parts.append(f"{hours.group(1)} hour(s)")
    return ", ".join(parts) if parts else iso

def clean(s: Optional[str]) -> str:
    if not s: return ""
    return re.sub(r"\s+", " ", s).strip()

def join_list(xs: Iterable[str]) -> str:
    return " | ".join([clean(x) for x in xs if x])

def normalize_url(href: str) -> Optional[str]:
    if not href: return None
    href = href.split("?")[0].rstrip("/")
    if href.startswith("/"):
        href = "https://www.coursera.org" + href
    if any(seg in href for seg in RESULT_PATTERNS):
        return href
    return None

def extract_jsonld(soup: BeautifulSoup) -> Dict[str, Any]:
    best = {}
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.text)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict):
                t = it.get("@type", "")
                types = ([x.lower() for x in t] if isinstance(t, list) else [str(t).lower()])
                if any(tp in ("course", "product") for tp in types):
                    best = it
    return best

def extract_what_you_will_learn(soup: BeautifulSoup) -> List[str]:
    heads = soup.find_all(['h2','h3'], string=lambda t: t and "what you will learn" in t.lower())
    bullets = []
    for h in heads:
        # try the next ul/section
        for sib in h.find_all_next():
            if sib.name in ("ul","ol"):
                for li in sib.find_all("li"):
                    bullets.append(clean(li.get_text(" ")))
                if bullets:
                    return bullets
            # bail out if we drift too far down the tree
            if sib.name in ("h2","h3") and sib is not h:
                break
    return bullets

def extract_skills_from_jsonld(j: Dict[str, Any]) -> List[str]:
    skills = []
    jl = j.get("skills")
    if isinstance(jl, list):
        skills = [str(s) for s in jl]
    elif isinstance(jl, str):
        skills = [jl]
    return skills

def guess_level(text: str) -> str:
    m = re.search(r"\b(Beginner|Intermediate|Advanced|Mixed|All Levels)\b", text, flags=re.I)
    return m.group(1).title() if m else ""

def guess_duration(text: str) -> str:
    m = re.search(r"(\d+)\s*(week|weeks|month|months|hour|hours)", text, flags=re.I)
    return f"{m.group(1)} {m.group(2)}" if m else ""

async def fetch_html(client: httpx.AsyncClient, url: str, params: Dict[str, Any] = None) -> Optional[str]:
    try:
        r = await client.get(url, params=params, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.text
        return None
    except Exception:
        return None

async def collect_search_urls_for_keyword(client: httpx.AsyncClient, keyword: str, pages: int) -> List[str]:
    urls = []
    seen = set()
    # iterate paginated search (?page=2 etc.)
    tasks = []
    for page in range(1, pages + 1):
        params = {"query": keyword, "page": page, "index": "prod_all_products_term_optimization"}
        tasks.append(fetch_html(client, SEARCH_URL, params=params))

    html_pages = []
    # progress for discovery
    for html in await tqdm_async.gather(*tasks, total=len(tasks), desc=f"[{keyword}] discover pages"):
        html_pages.append(html)

    for html in html_pages:
        if not html: continue
        soup = BeautifulSoup(html, "html.parser")
        # 1) Try anchors directly
        for a in soup.select('a[href*="/learn/"], a[href*="/specializations/"], a[href*="/professional-certificates/"]'):
            url = normalize_url(a.get("href"))
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        # 2) Try __NEXT_DATA__ (render payload) if present
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.text:
            try:
                data = json.loads(script.text)
            except Exception:
                data = None
            if isinstance(data, dict):
                def walker(x):
                    out = []
                    if isinstance(x, dict):
                        for v in x.values():
                            out.extend(walker(v))
                    elif isinstance(x, list):
                        for v in x:
                            out.extend(walker(v))
                    elif isinstance(x, str):
                        u = normalize_url(x)
                        if u: out.append(u)
                    return out
                for u in walker(data):
                    if u not in seen:
                        seen.add(u)
                        urls.append(u)

    return urls

async def fetch_course_detail(client: httpx.AsyncClient, url: str, keyword: str) -> Dict[str, Any]:
    html = await fetch_html(client, url)
    data = {
        "keyword": keyword, "url": url, "title": "", "description": "", "partner": "",
        "rating": "", "rating_count": "", "duration": "", "level": "",
        "what_you_will_learn": "", "skills": "", "recommended_experience": ""
    }
    if not html:
        return data

    soup = BeautifulSoup(html, "html.parser")
    j = extract_jsonld(soup)

    # JSON-LD first
    if j:
        data["title"] = clean(j.get("name")) or data["title"]
        data["description"] = clean(j.get("description")) or data["description"]
        provider = j.get("provider") or j.get("brand")
        if isinstance(provider, dict):
            data["partner"] = clean(provider.get("name")) or data["partner"]
        ar = j.get("aggregateRating") or {}
        if isinstance(ar, dict):
            if ar.get("ratingValue") is not None:
                data["rating"] = str(ar.get("ratingValue"))
            if ar.get("ratingCount") is not None:
                data["rating_count"] = str(ar.get("ratingCount"))
        dur = j.get("timeRequired") or ""
        data["duration"] = iso8601_to_readable(dur) or data["duration"]
        level = j.get("educationalLevel")
        if isinstance(level, list):
            data["level"] = join_list(level) or data["level"]
        else:
            data["level"] = clean(level) or data["level"]
        skills = extract_skills_from_jsonld(j)
        if skills:
            data["skills"] = join_list(skills)

    # Fallbacks via HTML
    if not data["title"]:
        h1 = soup.find("h1")
        if h1: data["title"] = clean(h1.get_text(" "))

    if not data["partner"]:
        # common partner locations
        cand = soup.select_one('[data-e2e="partner-name"]') or soup.select_one("a[href*='/partner/']") or soup.select_one("div.partnerBanner span")
        if cand:
            data["partner"] = clean(cand.get_text(" "))

    if not data["rating"]:
        rt = soup.select_one('[data-test="number-star-rating"], [data-e2e="star-rating"]')
        if rt:
            m = re.search(r"([0-5]\.?[0-9]?)", rt.get_text(" "))
            if m: data["rating"] = m.group(1)

    wyw = extract_what_you_will_learn(soup)
    if wyw:
        data["what_you_will_learn"] = join_list(wyw)

    # Recommended experience / prerequisites
    rec = ""
    txt = soup.get_text(" ")
    m = re.search(r"(Recommended\s+Experience|Prerequisites?|Before\s+you\s+start)\s*[:\-–]?\s*(.{10,300})", txt, flags=re.I)
    if m:
        rec = clean(m.group(2))
    data["recommended_experience"] = rec

    if not data["level"]:
        data["level"] = guess_level(txt)

    if not data["duration"]:
        data["duration"] = guess_duration(txt)

    return data

async def scrape_keywords(keywords: List[str], pages: int, concurrency: int, per_keyword_limit: Optional[int]) -> List[Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []
    limits = per_keyword_limit if per_keyword_limit and per_keyword_limit > 0 else None

    async with httpx.AsyncClient(http2=True, follow_redirects=True) as client:
        for kw in keywords:
            # 1) discover URLs
            urls = await collect_search_urls_for_keyword(client, kw, pages=pages)
            if limits:
                urls = urls[:limits]

            # 2) fetch details concurrently
            sem = asyncio.Semaphore(concurrency)
            rows: List[Dict[str, Any]] = []

            async def worker(u: str):
                async with sem:
                    # small jitter between requests
                    await asyncio.sleep(random.uniform(0.05, 0.2))
                    rows.append(await fetch_course_detail(client, u, kw))

            tasks = [worker(u) for u in urls]
            for _ in await tqdm_async.gather(*tasks, total=len(tasks), desc=f"[{kw}] fetch details"):
                pass

            all_rows.extend(rows)

    return all_rows

def cli():
    ap = argparse.ArgumentParser(description="Scrape Coursera courses by keyword(s) and export CSV (httpx + bs4).")
    ap.add_argument("--keywords", type=str, required=True, help="Comma-separated keywords, e.g. 'machine learning, data science'")
    ap.add_argument("--pages", type=int, default=5, help="How many search pages per keyword to scan (default: 5)")
    ap.add_argument("--concurrency", type=int, default=16, help="Concurrent detail fetches (default: 16)")
    ap.add_argument("--limit-per-keyword", type=int, default=0, help="Optional cap per keyword (0 = no cap)")
    ap.add_argument("-o", "--output", type=str, default=None, help="Output CSV filename")
    return ap.parse_args()

async def main():
    args = cli()
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    rows = await scrape_keywords(
        keywords=keywords,
        pages=args.pages,
        concurrency=args.concurrency,
        per_keyword_limit=args.limit_per_keyword
    )
    if not rows:
        print("No rows collected. Try increasing --pages or check connectivity.")
        return

    df = pd.DataFrame(rows)
    df = df[[
        "keyword","title","partner","level","rating","rating_count","duration",
        "what_you_will_learn","skills","recommended_experience","description","url"
    ]]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.output or f"coursera_courses_{ts}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df):,} rows to {out}")

if __name__ == "__main__":
    asyncio.run(main())
