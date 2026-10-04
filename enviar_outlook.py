"""Crea borradores en tu Outlook ya abierto (sin claves) con el CV adjunto.
Lee empresas.csv (tiene email) y los deja en Borradores para que revises y des Enviar.
Los de postular_manual.csv NO tienen email (son links de plataforma): usá --open-links para abrirlos.

Uso:
  python enviar_outlook.py --dry-run                  # vista previa
  python enviar_outlook.py --limit 10                 # crea 10 borradores
  python enviar_outlook.py --send --limit 10          # envía directo (solo si confías)
  python enviar_outlook.py --open-links --limit 10    # abre avisos plataforma en tu navegador
"""
import argparse, csv, os, sys, webbrowser
from pathlib import Path

BASE = Path(__file__).parent
CV = BASE / "CV_Fabrizio_Simon.pdf"
CSV_MAIL = BASE / "empresas.csv"
CSV_MANUAL = BASE / "postular_manual.csv"
LOG = BASE / "envios_log.csv"

BODY = """Buenas tardes:

Soy Fabrizio Simón, estudiante de la Tecnicatura en Programación (UTN), con experiencia en comercio, auditoría, stock y atención al público.

Me postulo al puesto de {puesto} en {empresa}. Soy preciso con números y sistemas, ordenado para tareas administrativas y con buen trato con clientes. {extra}

Adjunto mi CV en PDF. Quedo a disposición para una entrevista.

Saludos,
Fabrizio Simón – 261 690-5971 – Simonfabrizio103@gmail.com – Mendoza
GitHub: https://github.com/simonfabrizio103
"""

def outlook():
    import win32com.client
    return win32com.client.Dispatch("Outlook.Application")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--open-links", action="store_true")
    a = ap.parse_args()

    if a.open_links:
        if not CSV_MANUAL.exists():
            print("Sin postular_manual.csv"); return
        rows = list(csv.DictReader(open(CSV_MANUAL, encoding="utf-8")))[:a.limit]
        for r in rows:
            print(f"Abriendo: {r['puesto'][:60]}")
            if not a.dry_run:
                webbrowser.open(r["url"])
        print(f"{len(rows)} links."); return

    if not CSV_MAIL.exists():
        print("Sin empresas.csv"); sys.exit(1)
    rows = [r for r in csv.DictReader(open(CSV_MAIL, encoding="utf-8")) if (r.get("email") or "").strip()][:a.limit]
    # filtrar ejemplos de prueba
    rows = [r for r in rows if "ejemplo.com" not in r["email"]]
    print(f"Borradores a crear: {len(rows)}")
    if a.dry_run:
        for r in rows:
            print(f"[DRY] {r['empresa']} <{r['email']}> – {r['puesto']}")
        return

    ol = outlook()
    n = 0
    for r in rows:
        mail = ol.CreateItem(0)
        mail.To = r["email"].strip()
        mail.Subject = f"Postulación – Fabrizio Simón – {r['puesto'].strip()[:80]}"
        mail.Body = BODY.format(puesto=r["puesto"].strip(), empresa=r["empresa"].strip(), extra=r.get("mensaje_extra", "").strip())
        mail.Attachments.Add(str(CV))
        if a.send:
            mail.Send(); print(f"ENVIADO {r['empresa']}")
        else:
            mail.Save(); print(f"Borrador {r['empresa']}")
        n += 1
    print(f"Listo: {n} {'enviados' if a.send else 'borradores en tu Outlook'} con CV adjunto.")

if __name__ == "__main__":
    main()
