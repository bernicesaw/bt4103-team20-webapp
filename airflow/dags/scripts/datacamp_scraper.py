#!/usr/bin/env python3
import argparse, re, time, random
from typing import List, Dict, Optional, Set
import pandas as pd
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
DURATION_RE = re.compile(r"(?:Over\s+)?\d+(?:\s*(?:–|-|to)\s*\d+)?\s*(?:hr|hrs|hour|hours)\b", re.I)

def jitter(a=0.25, b=0.6): time.sleep(random.uniform(a, b))

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

def wait_for_grid(driver, timeout=45):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/learn/courses/']"))
    )

def expand_all_courses(driver):
    """Scroll + click until all courses are visible"""
    last, stable = -1, 0
    while True:
        driver.execute_script("window.scrollBy(0,1200);")
        jitter(0.2, 0.4)
        curr = len(driver.find_elements(By.CSS_SELECTOR, "a[href^='/learn/courses/']"))
        if curr > last:
            last, stable = curr, 0
        else:
            stable += 1
        if stable >= 3: break
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
    title = soup.select_one("h1")
    title = title.get_text(" ", strip=True) if title else None
    header = title and soup.find("h1").find_parent() or soup

    # level
    level = None
    m = LEVEL_RE.search(header.get_text(" ", strip=True)) if header else None
    if m: level = m.group(1).title()

    # duration
    duration = None
    m2 = DURATION_RE.search(header.get_text(" ", strip=True)) if header else None
    if m2: duration = m2.group(0)

    # description
    desc = None
    desc_hdr = soup.find(["h2","h3"], string=lambda t: t and t.strip().lower()=="description")
    if desc_hdr:
        parts, sib, hops = [], desc_hdr.find_next_sibling(), 0
        while sib and hops < 12:
            if sib.name in ("h2","h3"): break
            if sib.name in ("p","div","section","article"):
                txt = " ".join(sib.stripped_strings)
                if txt: parts.append(txt)
            sib = sib.find_next_sibling(); hops+=1
        if parts: desc = " ".join(parts).strip()
    if not desc:
        jd = soup.find("script", {"type":"application/ld+json"})
        if jd: import json; parsed = json.loads(jd.string or "{}"); desc = parsed.get("description")

    return {"title": title, "level": level, "duration": duration, "description_full": desc}

def run(out_csv: str):
    driver = make_driver()
    results = []
    try:
        driver.get(APP_URL)
        wait_for_grid(driver)
        expand_all_courses(driver)
        urls = extract_urls(driver.page_source)
        print(f"[discover] total {len(urls)} URLs")

        for i,u in enumerate(urls,1):
            try:
                driver.get(u)
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR,"h1")))
                time.sleep(0.6)
                details = extract_course_details(driver.page_source)
                details["url"]=u
                results.append(details)
                if i%20==0: print(f"[{i}/{len(urls)}] {details['title']}")
            except TimeoutException:
                results.append({"title":None,"level":None,"duration":None,"description_full":None,"url":u})
    finally:
        driver.quit()

    df = pd.DataFrame(results, columns=["title","level","duration","description_full","url"])
    df.to_csv(out_csv,index=False)
    print(f"Saved {len(df)} rows → {out_csv}")

if __name__=="__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-o","--output",default="datacamp_courses_full.csv",help="Output CSV file")
    args = ap.parse_args()
    run(args.output)
