#!/usr/bin/env python3
import asyncio, json, re, random, datetime, argparse
from typing import List, Dict, Any, Optional, Iterable, Set
import httpx
import pandas as pd
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm as tqdm_async

BASE = "https://www.codecademy.com"
CATALOG = f"{BASE}/catalog/all"
SEARCH  = f"{BASE}/search"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/119.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9"
}

# include stand-alone courses + paths for more coverage
URL_PATTERNS = ("/learn/", "/courses/", "/learn/paths/", "/learn/career-paths/")

# ----------------- small utils -----------------
def clean(s: Optional[str]) -> str:
    if not s: return ""
    return re.sub(r"\s+", " ", s).strip()

def join_list(xs: Iterable[str]) -> str:
    return " | ".join([clean(x) for x in xs if x])

def normalize_url(href: Optional[str]) -> Optional[str]:
    if not href: return None
    href = href.split("?")[0].rstrip("/")
    if href.startswith("/"): href = BASE + href
    return href if any(seg in href for seg in URL_PATTERNS) else None

def iso8601_to_readable(iso: str) -> str:
    if not iso or not iso.startswith("P"): return iso or ""
    months = re.search(r"(\d+)M(?!T)", iso)
    weeks  = re.search(r"(\d+)W", iso)
    days   = re.search(r"(\d+)D", iso)
    hours  = re.search(r"T(\d+)H", iso)
    parts = []
    if months: parts.append(f"{months.group(1)} month(s)")
    if weeks:  parts.append(f"{weeks.group(1)} week(s)")
    if days:   parts.append(f"{days.group(1)} day(s)")
    if hours:  parts.append(f"{hours.group(1)} hour(s)")
    return ", ".join(parts) if parts else iso

def extract_skills_from_text(txt: str) -> List[str]:
    buckets = {
        "Python": r"\bpython\b", "Java": r"\bjava\b(?!script)", "JavaScript": r"\bjavascript\b|\bjs\b",
        "TypeScript": r"\btypescript\b", "C": r"\bc( language| programming)\b", "C++": r"\bc\+\+\b",
        "C#": r"\bc#\b", "Go": r"\bgo(lang)?\b", "Rust": r"\brust\b", "SQL": r"\bsql\b",
        "HTML/CSS": r"\bhtml\b|\bcss\b", "React": r"\breact\b", "Node.js": r"\bnode(\.js)?\b",
        "Django": r"\bdjango\b", "Flask": r"\bflask\b", "Kubernetes": r"\bkubernetes\b|\bk8s\b",
        "Docker": r"\bdocker\b", "AWS": r"\baws\b|amazon web services", "Azure": r"\bazure\b", "GCP": r"\bgcp\b|\bgoogle cloud\b",
        "Data Engineering": r"\bdata engineering\b", "Data Science": r"\bdata science\b",
        "Machine Learning": r"\bmachine learning\b|\bml\b", "Deep Learning": r"\bdeep learning\b|\bdl\b",
        "NLP": r"\bnatural language processing\b|\bnlp\b", "Computer Vision": r"\bcomputer vision\b",
        "Backend": r"\bback[- ]?end\b", "Frontend": r"\bfront[- ]?end\b", "Full-Stack": r"\bfull[- ]?stack\b",
        "DevOps": r"\bdevops\b", "Cybersecurity": r"\bcyber ?security\b|\bsecurity\b",
        "Testing": r"\btesting\b|\bunit tests?\b|\btdd\b", "Algorithms & DS": r"\balgorithm(s)?\b|\bdata structure(s)?\b",
        "System Design": r"\bsystem design\b",
    }
    lower = txt.lower()
    return [k for k, pat in buckets.items() if re.search(pat, lower)]

# ----------------- HTTP helpers -----------------
async def fetch_html(client: httpx.AsyncClient, url: str, params: dict = None, retries: int = 3) -> Optional[str]:
    backoff = 0.6
    for _ in range(retries):
        try:
            r = await client.get(url, params=params, headers=HEADERS, timeout=30, follow_redirects=True)
            if r.status_code == 200: return r.text
            if r.status_code in (429,500,502,503,504):
                await asyncio.sleep(backoff + random.uniform(0,0.4)); backoff *= 1.7; continue
            return None
        except Exception:
            await asyncio.sleep(backoff + random.uniform(0,0.4)); backoff *= 1.7
    return None

# ----------------- discovery -----------------
def extract_links_from_html(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.select('a[href]'):
        u = normalize_url(a.get("href"))
        if u: links.add(u)
    # also try __NEXT_DATA__ for any embedded links
    nd = soup.find("script", id="__NEXT_DATA__")
    if nd and nd.text:
        try:
            data = json.loads(nd.text)
            def walk(x):
                if isinstance(x, dict):
                    for v in x.values(): yield from walk(v)
                elif isinstance(x, list):
                    for v in x: yield from walk(v)
                elif isinstance(x, str):
                    uu = normalize_url(x)
                    if uu: yield uu
            for u in walk(data): links.add(u)
        except Exception:
            pass
    return sorted(links)

async def discover_catalog(client: httpx.AsyncClient, *, max_pages: Optional[int], patience: int = 2) -> List[str]:
    urls, seen, page, empty = [], set(), 1, 0
    print("[catalog] auto-discover starting…")
    while True:
        if max_pages and page > max_pages:
            print(f"[catalog] reached max_pages={max_pages}"); break
        html = await fetch_html(client, CATALOG, params={"page": page})
        if not html:
            empty += 1
            if empty >= patience: break
        else:
            found = extract_links_from_html(html)
            gained = 0
            for u in found:
                if u not in seen: seen.add(u); urls.append(u); gained += 1
            print(f"[catalog] page {page}: +{gained} (total {len(urls)})")
            empty = 0 if gained > 0 else empty + 1
            if empty >= patience:
                print(f"[catalog] no growth for {patience} page(s) → stopping"); break
        page += 1
        await asyncio.sleep(random.uniform(0.15,0.35))
    return urls

async def discover_by_keyword(client: httpx.AsyncClient, keyword: str, *, max_pages: Optional[int], patience: int = 2) -> List[str]:
    urls, seen, page, empty = [], set(), 1, 0
    print(f"[search:{keyword}] auto-discover starting…")
    while True:
        if max_pages and page > max_pages:
            print(f"[search:{keyword}] reached max_pages={max_pages}"); break
        params = {"query": keyword, "page": page}
        html = await fetch_html(client, SEARCH, params=params)
        if not html:
            empty += 1
            if empty >= patience: break
        else:
            found = extract_links_from_html(html)
            gained = 0
            for u in found:
                if u not in seen: seen.add(u); urls.append(u); gained += 1
            print(f"[search:{keyword}] page {page}: +{gained} (total {len(urls)})")
            empty = 0 if gained > 0 else empty + 1
            if empty >= patience:
                print(f"[search:{keyword}] no growth for {patience} page(s) → stopping"); break
        page += 1
        await asyncio.sleep(random.uniform(0.15,0.35))
    return urls

# ----------------- details parsing -----------------
def extract_jsonld(soup: BeautifulSoup) -> Dict[str, Any]:
    best = {}
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try: data = json.loads(tag.text)
        except Exception: continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict) and str(it.get("@type","")).lower() in {"course","creativework"}:
                best = it
    return best

def parse_course_page(html: str, url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    jsonld = extract_jsonld(soup)

    title = clean(jsonld.get("name")) if jsonld else ""
    description = clean(jsonld.get("description")) if jsonld else ""

    if not title:
        h1 = soup.find("h1")
        if h1: title = clean(h1.get_text(" "))

    if not description:
        desc_node = soup.select_one('[data-testid*="description"], [data-test*="description"], section p')
        if desc_node: description = clean(desc_node.get_text(" "))

    duration = ""
    if jsonld and isinstance(jsonld.get("timeRequired"), str):
        duration = iso8601_to_readable(jsonld["timeRequired"])
    if not duration:
        duration = ""
        txt = soup.get_text(" ")
        m = re.search(r"(\d+)\s*(hour|hours|hr|hrs|week|weeks|month|months)", txt, flags=re.I)
        if m: duration = f"{m.group(1)} {m.group(2)}"

    skills = set()
    if jsonld:
        kw = jsonld.get("keywords")
        if isinstance(kw, list): skills.update(clean(x) for x in kw if clean(x))
        elif isinstance(kw, str): skills.update(clean(x) for x in kw.split(",") if clean(x))
    for tag in soup.select('a[href*="skill"], a[href*="tag"], a[href*="category"], a[href*="/catalog/"]'):
        t = clean(tag.get_text(" "))
        if t: skills.add(t)
    skills.update(extract_skills_from_text((title + " " + description + " " + soup.get_text(" "))))

    learn_items = []
    heads = soup.find_all(["h2","h3"], string=lambda t: t and ("learn" in t.lower()))
    for h in heads:
        for ul in h.find_all_next(["ul","ol"], limit=2):
            for li in ul.find_all("li"):
                txt = clean(li.get_text(" "))
                if txt and txt not in learn_items:
                    learn_items.append(txt)
        if learn_items: break

    return {
        "title": title,
        "url": url,
        "description": description,
        "duration": duration,
        "what_you_learn": join_list(learn_items),
        "skills": join_list(sorted(skills)),
    }

async def fetch_course_detail(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    html = await fetch_html(client, url)
    if not html:
        return {"title":"", "url":url, "description":"", "duration":"", "what_you_learn":"", "skills":""}
    return parse_course_page(html, url)

# ----------------- runner -----------------
async def run(keywords: List[str], include_catalog: bool, max_pages: Optional[int], concurrency: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(http2=True) as client:
        discovered: Set[str] = set()

        if include_catalog:
            cat_urls = await discover_catalog(client, max_pages=max_pages, patience=2)
            discovered.update(cat_urls)

        for kw in keywords:
            urls = await discover_by_keyword(client, kw, max_pages=max_pages, patience=2)
            discovered.update(urls)

        # fetch details concurrently
        sem = asyncio.Semaphore(concurrency)
        async def worker(u: str):
            async with sem:
                await asyncio.sleep(random.uniform(0.05,0.2))
                rows.append(await fetch_course_detail(client, u))

        tasks = [worker(u) for u in sorted(discovered)]
        for _ in await tqdm_async.gather(*tasks, total=len(tasks), desc="[courses] fetch details"):
            pass

    return rows

def save_csv(rows: List[Dict[str, Any]], out_path: str):
    df = pd.DataFrame(rows)
    cols = ["title","url","description","duration","what_you_learn","skills"]
    df = df[[c for c in cols if c in df.columns]]
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df):,} rows → {out_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Codecademy scraper (catalog + keyword search).")
    ap.add_argument("--keywords", type=str, default="", help="Comma-separated keywords, e.g. 'python, java, sql'")
    ap.add_argument("--include-catalog", action="store_true", help="Also crawl /catalog/all")
    ap.add_argument("--max-pages", type=int, default=0, help="Cap per source (0 = auto until dry)")
    ap.add_argument("--concurrency", type=int, default=32, help="Concurrent detail fetches")
    ap.add_argument("-o", "--output", type=str, default=None, help="Output CSV path")
    args = ap.parse_args()

    kw_list = [k.strip() for k in args.keywords.split(",") if k.strip()]
    rows = asyncio.run(run(kw_list, args.include_catalog, (args.max_pages or None), args.concurrency))
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.output or f"codecademy_courses_{ts}.csv"
    save_csv(rows, out)
