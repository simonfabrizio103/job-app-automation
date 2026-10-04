"""Scraper posts LinkedIn con emails -> empresas.csv
Uso:
  python scrap_linkedin_posts.py --login            # 1ra vez: abre Chrome, logueas manual, Enter para guardar sesion
  python scrap_linkedin_posts.py --max-posts 25     # corridas diarias headless
Requiere: pip install playwright ; python -m playwright install chromium
"""
import argparse, csv, re, time
from pathlib import Path

BASE = Path(__file__).parent
SESS = BASE / "linkedin_session"
OUT_CSV = BASE / "empresas.csv"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BAD = ("noreply", "no-reply", "linkedin.com", "example.com", ".png", ".jpg")
KEYWORDS = ["enviar cv Mendoza", "interesados enviar cv Mendoza", "contratando email Mendoza",
            "buscamos email Mendoza", "empleo enviar curriculum Mendoza", "vacante enviar cv Argentina"]

def clean(s): return re.sub(r"\s+", " ", s or "").strip()

def emails_en(texto):
    out = []
    for e in set(EMAIL_RE.findall(texto or "")):
        el = e.lower()
        if any(b in el for b in BAD) or len(e) > 60:
            continue
        out.append(e)
    return out

def guess_empresa_puesto(texto):
    t = clean(texto)[:300]
    m = re.search(r"(buscamos|contratamos|incorporamos|vacante de|puesto de)\s+([A-ZÁÉÍÓÚa-z ñÑ/.-]{3,60})", t, re.I)
    puesto = m.group(2).strip() if m else t[:60]
    m2 = re.search(r"(empresa|en)\s+([A-Z][A-Za-z& .-]{2,50})", t)
    empresa = m2.group(2).strip() if m2 else "Vía LinkedIn"
    return empresa[:80], puesto[:80]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--max-posts", type=int, default=25)
    ap.add_argument("--keywords", default=",".join(KEYWORDS))
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright
    kws = [k.strip() for k in a.keywords.split(",") if k.strip()]
    SESS.mkdir(exist_ok=True)
    rows, seen = [], set()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)  # visible para login y anti-deteccion
        ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                  viewport={"width": 1280, "height": 900})
        # cargar cookies previas
        ck = SESS / "cookies.json"
        if ck.exists():
            import json
            try: ctx.add_cookies(json.load(open(ck, encoding="utf-8")))
            except Exception as e: print(f"cookies: {e}")
        page = ctx.new_page()

        if a.login:
            page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            print("LOGUEATE manual en la ventana Chrome y pulsa Enter aquí...")
            input()
            import json
            json.dump(ctx.cookies(), open(ck, "w", encoding="utf-8"), indent=1)
            print(f"Sesión guardada en {ck}")
            browser.close(); return

        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        print(f"URL actual: {page.url}")
        if "login" in page.url or "authwall" in page.url:
            print("Sesión expirada: corré primero --login"); browser.close(); return

        for kw in kws:
            from urllib.parse import quote_plus
            # 1) intento: búsqueda contenido 2) fallback: hashtag
            urls = [
                f"https://www.linkedin.com/search/results/content/?keywords={quote_plus(kw)}&sortBy=%22date_posted%22",
                f"https://www.linkedin.com/feed/hashtag/{quote_plus(kw.split()[0].lower())}/",
            ]
            posts = []
            for url in urls:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(4)
                for _ in range(5):
                    page.mouse.wheel(0, 2500); time.sleep(2)
                for btn in page.query_selector_all("button"):
                    try:
                        t = (btn.inner_text() or "").lower()
                        if "ver más" in t or "see more" in t:
                            btn.click(); time.sleep(0.5)
                    except Exception: pass
                posts = page.query_selector_all("article, div.feed-shared-update-v2, div.search-result__wrapper, div.entity-result, div.feed-shared-update-v2__description-wrapper, li.search-result, div.entity-result__content, main li")
                print(f"{kw} [{url.split('/')[3]}]: {len(posts)} posts (url={page.url[:80]})")
                if posts: break
            # Fallback: extraer emails de todo el texto visible aunque no matcheen posts
            try:
                full = page.inner_text("main") or page.inner_text("body")
            except Exception:
                full = ""
            if not posts and full:
                print(f"  fallback texto: {len(full)} chars")
                for em in emails_en(full):
                    key = em.lower()
                    if key in seen: continue
                    seen.add(key)
                    emp, pue = guess_empresa_puesto(full)
                    rows.append({"empresa": emp, "email": em, "puesto": f"{kw} | {pue}", "mensaje_extra": "Fuente: LinkedIn search"})
                if rows and len(rows) >= a.max_posts: break
                continue
            if not posts:
                page.screenshot(path=str(BASE / "debug_linkedin.png"))
                print("  -> sin posts, captura en debug_linkedin.png")
            for p in posts:
                if len(rows) >= a.max_posts: break
                try: txt = p.inner_text() or ""
                except Exception: continue
                try: link = p.query_selector("a[href*='/posts/'], a[href*='/activity/']")
                except Exception: link = None
                urlp = ""
                try: urlp = link.get_attribute("href") if link else ""
                except Exception: pass
                # Si no hay email en el resumen, visitar el aviso (máx 10 por corrida)
                visited = getattr(main, "_visited", 0)
                if not emails_en(txt) and urlp and visited < 10:
                    try:
                        d = page.context.new_page()
                        d.goto(urlp if urlp.startswith("http") else "https://www.linkedin.com" + urlp,
                               wait_until="domcontentloaded", timeout=25000)
                        time.sleep(3)
                        for b in d.query_selector_all("button"):
                            try:
                                if "ver más" in (b.inner_text() or "").lower() or "see more" in (b.inner_text() or "").lower():
                                    b.click(); time.sleep(0.5)
                            except Exception: pass
                        try: txt = d.inner_text("main") or txt
                        except Exception: pass
                        d.close(); main._visited = visited + 1
                        time.sleep(2)
                    except Exception: pass
                for em in emails_en(txt):
                    key = em.lower()
                    if key in seen: continue
                    seen.add(key)
                    emp, pue = guess_empresa_puesto(txt)
                    rows.append({"empresa": emp, "email": em, "puesto": pue, "mensaje_extra": f"Fuente: LinkedIn post | {urlp}"[:200]})
            if len(rows) >= a.max_posts: break
            time.sleep(2)
        browser.close()

    if not rows:
        print("0 emails nuevos. Probá otras keywords o --login de nuevo."); return
    # deduplicar contra CSV existente
    existing = set()
    if OUT_CSV.exists():
        import csv as _csv
        for r in _csv.DictReader(open(OUT_CSV, encoding="utf-8")):
            existing.add(r["email"].strip().lower())
    nuevos = [r for r in rows if r["email"].lower() not in existing]
    hdr = not OUT_CSV.exists()
    with open(OUT_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["empresa", "email", "puesto", "mensaje_extra"])
        if hdr: w.writeheader()
        w.writerows(nuevos)
    print(f"Nuevos: {len(nuevos)} -> {OUT_CSV}")

if __name__ == "__main__":
    main()
