"""Entra a cada link de postular_manual.csv, copia el email si hay, y lo manda por tu Outlook abierto.
Sin claves: usa tu Outlook ya iniciado. Sin email en el aviso: lo salta (esos van por plataforma).

Uso:
  python extraer_y_enviar.py --dry-run --limit 5    # prueba: muestra qué emails encuentra, no manda
  python extraer_y_enviar.py --limit 10             # crea borradores en Outlook
  python extraer_y_enviar.py --send --limit 10      # envía directo
"""
import argparse, csv, re, time
from pathlib import Path

BASE = Path(__file__).parent
CV = BASE / "CV_Fabrizio_Simon.pdf"
MANUAL = BASE / "postular_manual.csv"
LOG = BASE / "envios_log.csv"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BAD = ("noreply", "no-reply", "linkedin.com", "example.com", ".png", ".jpg", "computrabajo.com", "bumeran.com", "zonajobs.com")

BODY = """Buenas tardes:

Soy Fabrizio Simón, estudiante de la Tecnicatura en Programación (UTN), con experiencia en comercio, auditoría, stock y atención al público.

Me postulo al puesto de {puesto} en {empresa}. Soy preciso con números y sistemas, ordenado para tareas administrativas y con buen trato con clientes.

Vi su aviso en {url} y adjunto mi CV en PDF. Quedo a disposición para una entrevista.

Saludos,
Fabrizio Simón – 261 690-5971 – Simonfabrizio103@gmail.com – Mendoza
GitHub: https://github.com/simonfabrizio103
"""

def emails_en(t):
    return [e for e in set(EMAIL_RE.findall(t or ""))
            if not any(b in e.lower() for b in BAD) and len(e) < 60]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args()

    rows = list(csv.DictReader(open(MANUAL, encoding="utf-8")))[:a.limit]
    print(f"Avisos a revisar: {len(rows)}")
    from playwright.sync_api import sync_playwright
    hallados, creados = 0, 0
    log_rows = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        pg = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)").new_page()
        for r in rows:
            url, emp, pue = r.get("url", ""), r.get("empresa", "s/d"), r.get("puesto", "")
            if not url: continue
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=25000)
                time.sleep(2)
                txt = pg.inner_text("body")
            except Exception as e:
                print(f"X {pue[:50]} (no abre: {type(e).__name__})"); continue
            ems = emails_en(txt)
            if not ems:
                print(f"- {pue[:50]}: sin email (va por plataforma)"); continue
            hallados += 1
            print(f"+ {pue[:50]}: {ems[0]}")
            if a.dry_run: continue
            import win32com.client
            mail = win32com.client.Dispatch("Outlook.Application").CreateItem(0)
            mail.To = ems[0]
            mail.Subject = f"Postulación – Fabrizio Simón – {pue[:80]}"
            mail.Body = BODY.format(puesto=pue, empresa=emp, url=url)
            mail.Attachments.Add(str(CV))
            if a.send: mail.Send()
            else: mail.Save()
            creados += 1
            log_rows.append({"empresa": emp, "email": ems[0], "puesto": pue[:80],
                             "estado": "outlook enviado" if a.send else "outlook borrador"})
            time.sleep(1)
        b.close()
    if log_rows and not a.dry_run:
        import csv as _c
        hdr = not LOG.exists()
        with open(LOG, "a", newline="", encoding="utf-8") as f:
            w = _c.DictWriter(f, fieldnames=["empresa", "email", "puesto", "estado"])
            if hdr: w.writeheader()
            w.writerows(log_rows)
    print(f"Emails hallados: {hallados} | {'enviados' if a.send else 'borradores'}: {creados} (dry={a.dry_run})")

if __name__ == "__main__":
    main()
