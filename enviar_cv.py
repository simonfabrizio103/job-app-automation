"""Envío semi-automático de CV por Gmail + log anti-duplicados.
Uso:
  set GMAIL_USER=tu@gmail.com
  set GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx  (App Password, NO tu clave normal)
  python enviar_cv.py --dry-run        (vista previa, no envía)
  python enviar_cv.py --limit 20       (envía hasta 20 no enviados)
"""
import argparse, csv, os, ssl, sys
from datetime import datetime
from email.message import EmailMessage
import smtplib

BASE = os.path.dirname(os.path.abspath(__file__))
CV = os.path.join(BASE, "CV_Fabrizio_Simon.pdf")
CSV_IN = os.path.join(BASE, "empresas.csv")
LOG = os.path.join(BASE, "envios_log.csv")

SUBJECT = "Postulación – Fabrizio Simón – {puesto}"
BODY = """Buenas tardes:

Soy Fabrizio Simón, estudiante de la Tecnicatura en Programación (UTN), con experiencia en comercio, auditoría, stock y atención al público.

Me postulo al puesto de {puesto} en {empresa}. Soy preciso con números y sistemas, ordenado para tareas administrativas y con buen trato con clientes. {extra}

Adjunto mi CV en PDF. Quedo a disposición para una entrevista.

Saludos,
Fabrizio Simón – 261 690-5971 – Simonfabrizio103@gmail.com – Mendoza
GitHub: https://github.com/simonfabrizio103
"""

def load_sent():
    sent = set()
    if os.path.exists(LOG):
        with open(LOG, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sent.add((row.get("email","").strip().lower(), row.get("puesto","").strip().lower()))
    return sent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()

    if not os.path.exists(CV):
        print(f"Falta {CV}"); sys.exit(1)
    with open(CSV_IN, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    sent = load_sent()
    pendientes = [r for r in rows if (r["email"].strip().lower(), r["puesto"].strip().lower()) not in sent][:a.limit]
    print(f"Pendientes: {len(pendientes)} (límite {a.limit})")

    user = os.environ.get("GMAIL_USER"); pwd = os.environ.get("GMAIL_APP_PASSWORD")
    if not a.dry_run and (not user or not pwd):
        print("Definí GMAIL_USER y GMAIL_APP_PASSWORD antes de enviar. Ver instrucciones en el chat."); sys.exit(1)

    with open(CV, "rb") as f: pdf = f.read()
    ok = 0
    log_new = not os.path.exists(LOG)
    lf = open(LOG, "a", newline="", encoding="utf-8")
    lw = csv.DictWriter(lf, fieldnames=["fecha","empresa","email","puesto","estado"])
    if log_new: lw.writeheader()

    for r in pendientes:
        emp, mail, pue = r["empresa"].strip(), r["email"].strip(), r["puesto"].strip()
        extra = r.get("mensaje_extra","").strip()
        msg = EmailMessage()
        msg["From"] = user if user else "tu@gmail.com"
        msg["To"] = mail
        msg["Subject"] = SUBJECT.format(puesto=pue)
        msg.set_content(BODY.format(puesto=pue, empresa=emp, extra=extra))
        msg.add_attachment(pdf, maintype="application", subtype="pdf", filename="CV_Fabrizio_Simon.pdf")
        if a.dry_run:
            print(f"[DRY] {emp} <{mail}> – {pue}")
            continue
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
                s.login(user, pwd); s.send_message(msg)
            lw.writerow({"fecha": datetime.now().isoformat(timespec="seconds"), "empresa": emp, "email": mail, "puesto": pue, "estado": "enviado"})
            print(f"OK {emp}"); ok += 1
        except Exception as e:
            lw.writerow({"fecha": datetime.now().isoformat(timespec="seconds"), "empresa": emp, "email": mail, "puesto": pue, "estado": f"error: {e}"})
            print(f"ERROR {emp}: {e}")
    lf.close()
    print(f"Listo. Enviados: {ok} (dry-run={a.dry_run}). Log: {LOG}")

if __name__ == "__main__":
    main()
