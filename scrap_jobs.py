"""Scraper Bumeran / ZonaJobs / Computrabajo → empresas.csv con emails.
Uso:
  python scrap_jobs.py --keywords "atencion cliente,caja,stock,administrativo,part time" --location "Mendoza" --max-pages 3
"""
import argparse, csv, re, sys, time
from pathlib import Path
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
OUT_CSV = BASE / "empresas.csv"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

KEYWORDS_DEFAULT = ["atencion cliente", "caja", "stock", "administrativo", "part time", "repositor", "deposito", "cajero"]
LOCATION_DEFAULT = "Mendoza"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def clean(s): return re.sub(r"\s+", " ", s or "").strip()

def extract_emails(text):
    found = set(EMAIL_RE.findall(text))
    # filtrar emails genéricos/no útiles
    bad = {"noreply", "no-reply", "info@", "contacto@", "rrhh@", "jobs@", "empleos@", "postulaciones@", "cv@", "talento@"}
    return [e for e in found if not any(b in e.lower() for b in bad)]

def scrape_bumeran(page, kw, loc, max_pages):
    results = []
    for p in range(1, max_pages+1):
        url = f"https://www.bumeran.com.ar/empleos-{quote_plus(loc)}-{quote_plus(kw)}-pagina-{p}.html"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("article, .sc-", timeout=15000)
        except Exception:
            break
        cards = page.query_selector_all("article, .sc-iHhHRJ, .sc-gKsewC, [data-qa='job-card']")
        if not cards: break
        for c in cards:
            try:
                title_el = c.query_selector("h2, h3, .sc-bczRLJ, [data-qa='job-title']")
                comp_el = c.query_selector(".sc-dXgVZQ, .sc-fqKVqY, [data-qa='company-name']")
                loc_el = c.query_selector(".sc-bZkfAO, [data-qa='job-location']")
                link_el = c.query_selector("a[href*='/empleo/'], a[href*='/job/']")
                title = clean(title_el.inner_text() if title_el else "")
                company = clean(comp_el.inner_text() if comp_el else "")
                location = clean(loc_el.inner_text() if loc_el else loc)
                url_job = link_el.get_attribute("href") if link_el else ""
                if url_job and not url_job.startswith("http"): url_job = "https://www.bumeran.com.ar" + url_job
                # entrar a detalle para buscar email
                emails = []
                if url_job:
                    try:
                        page2 = page.context.new_page()
                        page2.goto(url_job, wait_until="domcontentloaded", timeout=25000)
                        page2.wait_for_selector("body", timeout=10000)
                        body = page2.inner_text("body")
                        emails = extract_emails(body)
                        page2.close()
                    except Exception:
                        pass
                if title and (emails or company):
                    results.append({"empresa": company or "Sin empresa", "email": emails[0] if emails else "", "puesto": title, "mensaje_extra": f"Fuente: Bumeran | {url_job}"})
            except Exception:
                continue
        time.sleep(1.5)
    return results

def scrape_zonajobs(page, kw, loc, max_pages):
    results = []
    for p in range(1, max_pages+1):
        url = f"https://www.zonajobs.com.ar/empleos-{quote_plus(kw)}-en-{quote_plus(loc)}-pagina-{p}.html"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".job-card, .sc-", timeout=15000)
        except Exception:
            break
        cards = page.query_selector_all(".job-card, .sc-iHhHRJ, [data-qa='job-card']")
        if not cards: break
        for c in cards:
            try:
                title_el = c.query_selector("h2, h3, .sc-bczRLJ, [data-qa='job-title']")
                comp_el = c.query_selector(".sc-dXgVZQ, [data-qa='company-name']")
                link_el = c.query_selector("a[href*='/empleo/'], a[href*='/job/']")
                title = clean(title_el.inner_text() if title_el else "")
                company = clean(comp_el.inner_text() if comp_el else "")
                url_job = link_el.get_attribute("href") if link_el else ""
                if url_job and not url_job.startswith("http"): url_job = "https://www.zonajobs.com.ar" + url_job
                emails = []
                if url_job:
                    try:
                        page2 = page.context.new_page()
                        page2.goto(url_job, wait_until="domcontentloaded", timeout=25000)
                        page2.wait_for_selector("body", timeout=10000)
                        body = page2.inner_text("body")
                        emails = extract_emails(body)
                        page2.close()
                    except Exception:
                        pass
                if title and (emails or company):
                    results.append({"empresa": company or "Sin empresa", "email": emails[0] if emails else "", "puesto": title, "mensaje_extra": f"Fuente: ZonaJobs | {url_job}"})
            except Exception:
                continue
        time.sleep(1.5)
    return results

def scrape_computrabajo(page, kw, loc, max_pages):
    results = []
    for p in range(1, max_pages+1):
        url = f"https://ar.computrabajo.com/trabajo-de-{quote_plus(kw)}-en-{quote_plus(loc)}?p={p}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".box_offer, .iO", timeout=15000)
        except Exception:
            break
        cards = page.query_selector_all(".box_offer, .iO, article")
        if not cards: break
        for c in cards:
            try:
                title_el = c.query_selector("h2 a, .js-o-link, a[href*='/empleo/']")
                comp_el = c.query_selector(".fc_base, .fs16, a[href*='/empresa/']")
                link_el = title_el
                title = clean(title_el.inner_text() if title_el else "")
                company = clean(comp_el.inner_text() if comp_el else "")
                url_job = title_el.get_attribute("href") if title_el else ""
                if url_job and not url_job.startswith("http"): url_job = "https://ar.computrabajo.com" + url_job
                emails = []
                if url_job:
                    try:
                        page2 = page.context.new_page()
                        page2.goto(url_job, wait_until="domcontentloaded", timeout=25000)
                        page2.wait_for_selector("body", timeout=10000)
                        body = page2.inner_text("body")
                        emails = extract_emails(body)
                        page2.close()
                    except Exception:
                        pass
                if title and (emails or company):
                    results.append({"empresa": company or "Sin empresa", "email": emails[0] if emails else "", "puesto": title, "mensaje_extra": f"Fuente: Computrabajo | {url_job}"})
            except Exception:
                continue
        time.sleep(1.5)
    return results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", default=",".join(KEYWORDS_DEFAULT))
    ap.add_argument("--location", default=LOCATION_DEFAULT)
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()

    kws = [k.strip() for k in a.keywords.split(",") if k.strip()]
    all_rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=a.headless)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        for kw in kws:
            print(f"\n=== {kw} ===")
            for fn, name in [(scrape_bumeran,"Bumeran"),(scrape_zonajobs,"ZonaJobs"),(scrape_computrabajo,"Computrabajo")]:
                print(f"  {name}...")
                rows = fn(page, kw, a.location, a.max_pages)
                print(f"    {len(rows)} ofertas")
                all_rows.extend(rows)
        browser.close()

    # deduplicar por email+puesto
    seen = set()
    uniq = []
    for r in all_rows:
        key = (r["email"].lower(), r["puesto"].lower())
        if key not in seen and r["email"]:
            seen.add(key); uniq.append(r)

    # cargar existentes para no duplicar
    existing = set()
    if OUT_CSV.exists():
        with open(OUT_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing.add((row["email"].strip().lower(), row["puesto"].strip().lower()))
    new_rows = [r for r in uniq if (r["email"].lower(), r["puesto"].lower()) not in existing]

    # append
    write_header = not OUT_CSV.exists()
    with open(OUT_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["empresa","email","puesto","mensaje_extra"])
        if write_header: w.writeheader()
        w.writerows(new_rows)

    print(f"\nTotal scrapeadas: {len(all_rows)} | Nuevas con email: {len(new_rows)} -> {OUT_CSV}")

if __name__ == "__main__":
    main()