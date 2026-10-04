"""Pipeline automático: busca avisos → compara con tu CV → si matchea Y hay email, envía.
La clave de Gmail queda SOLO en tu PC (variables de entorno). Nunca la pegues en un chat.

Uso:
  set GMAIL_USER=Simonfabrizio103@gmail.com
  set GMAIL_APP_PASSWORD=xxxx (16 letras, una sola vez)
  python auto_postula.py --dry-run --max-pages 1     # vista previa, no envía
  python auto_postula.py --limit 15                  # envía hasta 15 matches con email
"""
import argparse, csv, os, re, ssl, sys, time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
import smtplib

BASE = Path(__file__).parent
CV = BASE / "CV_Fabrizio_Simon.pdf"
LOG = BASE / "envios_log.csv"
MANUAL = BASE / "postular_manual.csv"

# --- Perfil CV (para scoring) ---
POS = {"atencion": 3, "cliente": 3, "caja": 4, "cajero": 4, "stock": 4, "deposito": 3,
       "repositor": 4, "administrativo": 3, "administracion": 3, "auditor": 2, "arqueo": 3,
       "ventas": 2, "mostrador": 3, "part time": 4, "medio tiempo": 4, "part-time": 4,
       "mendoza": 2, "remoto": 2, "presencial": 1, "turno": 1, "excel": 1, "sheets": 1}
NEG = {"senior": -8, "sr ": -8, "semi senior": -8, "ssr": -6, "lead": -8, "gerente": -8,
       "jefe": -6, "manager": -8, "5 años": -6, "ingles avanzado": -4, "full stack": -6,
       "developer": -5, "desarrollador": -5, "programador": -4, "ingeniero": -4}
UMBRAL = 4
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BAD_MAIL = ("noreply", "no-reply", "linkedin.com", "example.com", ".png", ".jpg")

SUBJECT = "Postulación – Fabrizio Simón – {puesto}"
BODY = """Buenas tardes:

Soy Fabrizio Simón, estudiante de la Tecnicatura en Programación (UTN), con experiencia en comercio, auditoría, stock y atención al público.

Me postulo al puesto de {puesto} en {empresa}. Soy preciso con números y sistemas, ordenado para tareas administrativas y con buen trato con clientes.

Adjunto mi CV en PDF. Quedo a disposición para una entrevista.

Saludos,
Fabrizio Simón – 261 690-5971 – Simonfabrizio103@gmail.com – Mendoza
GitHub: https://github.com/simonfabrizio103
"""

def score(texto):
    t = (texto or "").lower()
    s = sum(p for k, p in POS.items() if k in t) + sum(p for k, p in NEG.items() if k in t)
    return s

def emails_en(texto):
    return [e for e in set(EMAIL_RE.findall(texto or ""))
            if not any(b in e.lower() for b in BAD_MAIL) and len(e) < 60]

def buscar(pw, keywords, location, max_pages):
    from playwright.sync_api import sync_playwright
    avisos = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)").new_page()
        from urllib.parse import quote_plus
        for kw in keywords:
            # Computrabajo (no requiere login para listados)
            for pag in range(1, max_pages + 1):
                url = f"https://ar.computrabajo.com/trabajo-de-{quote_plus(kw)}-en-{quote_plus(location)}?p={pag}"
                try:
                    pg.goto(url, wait_until="domcontentloaded", timeout=30000)
                    pg.wait_for_selector(".box_offer, article", timeout=12000)
                except Exception:
                    break
                for c in pg.query_selector_all(".box_offer, article"):
                    try:
                        t_el = c.query_selector("h2 a, a.js-o-link")
                        titulo = (t_el.inner_text() if t_el else "").strip()
                        href = t_el.get_attribute("href") if t_el else ""
                        if href and not href.startswith("http"): href = "https://ar.computrabajo.com" + href
                        txt = c.inner_text() or ""
                        if titulo:
                            avisos.append({"empresa": "s/d", "puesto": titulo, "texto": txt, "url": href})
                    except Exception:
                        continue
                time.sleep(1)
        # detalle: descripción + email (máx 15 por corrida para no abusar)
        for av in avisos[:15]:
            if not av["url"]: continue
            try:
                d = b.new_context(user_agent="Mozilla/5.0").new_page() if False else pg
                pg.goto(av["url"], wait_until="domcontentloaded", timeout=25000)
                time.sleep(2)
                body = pg.inner_text("body")
                av["texto"] += "\n" + body[:4000]
                em = emails_en(body)
                av["email"] = em[0] if em else ""
                m = re.search(r"(?i)(empresa|compañía)[:\s]+([A-Z][\w& .-]{2,40})", body)
                if m: av["empresa"] = m.group(2).strip()
            except Exception:
                av["email"] = ""
            time.sleep(1)
        b.close()
    return avisos

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--max-pages", type=int, default=1)
    ap.add_argument("--keywords", default="caja,atencion cliente,stock,administrativo,repositor")
    ap.add_argument("--location", default="Mendoza")
    ap.add_argument("--umbral", type=int, default=UMBRAL)
    a = ap.parse_args()

    kws = [k.strip() for k in a.keywords.split(",") if k.strip()]
    print(f"Buscando {kws} en {a.location}...")
    avisos = buscar(None, kws, a.location, a.max_pages)
    print(f"Avisos: {len(avisos)}")
    for av in avisos:
        av["score"] = score(av["puesto"] + " " + av["texto"])
    matches = [x for x in avisos if x["score"] >= a.umbral]
    print(f"Matches (score>={a.umbral}): {len(matches)}")
    con_mail = [x for x in matches if x.get("email")]
    sin_mail = [x for x in matches if not x.get("email")]
    print(f"  con email: {len(con_mail)} | para plataforma manual: {len(sin_mail)}")

    # guardar manuales
    if sin_mail:
        hdr = not MANUAL.exists()
        with open(MANUAL, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["empresa", "puesto", "score", "url"])
            if hdr: w.writeheader()
            for x in sin_mail:
                w.writerow({"empresa": x["empresa"], "puesto": x["puesto"], "score": x["score"], "url": x["url"]})
        print(f"Manuales -> {MANUAL}")

    if a.dry_run:
        for x in con_mail[:a.limit]:
            print(f"[DRY score={x['score']}] {x['empresa']} <{x['email']}> – {x['puesto'][:70]}")
        print("Dry-run: nada enviado."); return

    user, pwd = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not pwd:
        print("Definí GMAIL_USER y GMAIL_APP_PASSWORD en TU cmd. Nunca las compartas."); sys.exit(1)
    # anti-duplicados
    sent = set()
    if LOG.exists():
        for r in csv.DictReader(open(LOG, encoding="utf-8")):
            sent.add((r.get("email", "").lower(), r.get("puesto", "").lower()))
    pdf = open(CV, "rb").read()
    hdr = not LOG.exists()
    lf = open(LOG, "a", newline="", encoding="utf-8")
    lw = csv.DictWriter(lf, fieldnames=["fecha", "empresa", "email", "puesto", "estado"])
    if hdr: lw.writeheader()
    n = 0
    for x in con_mail:
        if (x["email"].lower(), x["puesto"].lower()) in sent or n >= a.limit: continue
        msg = EmailMessage()
        msg["From"] = user; msg["To"] = x["email"]
        msg["Subject"] = SUBJECT.format(puesto=x["puesto"][:80])
        msg.set_content(BODY.format(puesto=x["puesto"][:80], empresa=x["empresa"]))
        msg.add_attachment(pdf, maintype="application", subtype="pdf", filename="CV_Fabrizio_Simon.pdf")
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
                s.login(user, pwd); s.send_message(msg)
            lw.writerow({"fecha": datetime.now().isoformat(timespec="seconds"), "empresa": x["empresa"], "email": x["email"], "puesto": x["puesto"][:80], "estado": f"auto score={x['score']}"})
            print(f"OK [{x['score']}] {x['empresa']}"); n += 1
        except Exception as e:
            lw.writerow({"fecha": datetime.now().isoformat(timespec="seconds"), "empresa": x["empresa"], "email": x["email"], "puesto": x["puesto"][:80], "estado": f"error: {e}"})
            print(f"ERROR {x['empresa']}: {e}")
    lf.close()
    print(f"Enviados: {n}. Log: {LOG}")

if __name__ == "__main__":
    main()
