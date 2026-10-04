"""Lee avisos pegados del canal de WhatsApp, extrae emails, compara con tu CV
y crea borradores en tu Outlook abierto.

1. En WhatsApp (el canal no deja exportar): abrí cada aviso → clic en el texto
   → Copiar (o Leer más → seleccionar → Ctrl+C) → pegalo en bolsa_mendoza.txt
   (uno debajo del otro, separá avisos con una línea en blanco).
2. Corré:
  python whatsapp_postula.py --dry-run --limit 20    # vista previa con puntaje
  python whatsapp_postula.py --limit 20              # crea borradores
  python whatsapp_postula.py --send --limit 20       # envía directo
"""
import argparse, csv, re
from pathlib import Path

BASE = Path(__file__).parent
CHAT = BASE / "bolsa_mendoza.txt"
CV = BASE / "CV_Fabrizio_Simon.pdf"
LOG = BASE / "envios_log.csv"

LINE_RE = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}).*?-\s*(.*?):\s?(.*)$")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BAD = ("noreply", "no-reply", "example.com", ".png", ".jpg", "whatsapp")

POS = {"atencion": 3, "cliente": 3, "caja": 4, "cajero": 4, "stock": 4, "deposito": 3,
       "repositor": 4, "administrativo": 3, "vendedor": 2, "ventas": 2, "mostrador": 3,
       "auditor": 2, "part time": 4, "medio tiempo": 4, "part-time": 4, "mendoza": 2,
       "turno": 1, "mañana": 1, "tarde": 1, "excel": 1}
NEG = {"senior": -8, "jefe": -6, "gerente": -8, "manager": -8, "5 años": -6,
       "ingles avanzado": -4, "developer": -5, "programador": -4, "moto": -5,
       "auto propio": -4, "disponibilidad full": -3, "recursos humanos": -6, "rrhh": -5}
UMBRAL = 4

BODY = """Buenas tardes:

Soy Fabrizio Simón, estudiante de la Tecnicatura en Programación (UTN), con experiencia en comercio, auditoría, stock y atención al público.

Me postulo al aviso publicado en el canal de empleos ({fecha}). Soy preciso con números y sistemas, ordenado para tareas administrativas y con buen trato con clientes.

Adjunto mi CV en PDF. Quedo a disposición para una entrevista.

Saludos,
Fabrizio Simón – 261 690-5971 – Simonfabrizio103@gmail.com – Mendoza
GitHub: https://github.com/simonfabrizio103
"""

def parse_chat(text):
    msgs, cur = [], None
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if m:
            cur = {"fecha": m.group(1), "autor": m.group(3).strip(), "texto": m.group(4)}
            msgs.append(cur)
        elif cur:
            cur["texto"] += "\n" + line
    if not msgs:
        # Texto pegado del canal (sin formato exportado): partir por líneas en blanco
        bloques = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
        msgs = [{"fecha": "canal", "autor": "canal", "texto": b} for b in bloques if EMAIL_RE.search(b)]
    return msgs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--umbral", type=int, default=UMBRAL)
    a = ap.parse_args()

    if not CHAT.exists():
        print("Falta bolsa_mendoza.txt. Crealo pegando avisos del canal (ver instrucciones arriba)."); return
    msgs = parse_chat(CHAT.read_text(encoding="utf-8", errors="replace"))
    print(f"Avisos: {len(msgs)}")
    cands = []
    for m in msgs:
        t = m["texto"]
        for em in set(EMAIL_RE.findall(t)):
            if any(b in em.lower() for b in BAD) or len(em) > 60: continue
            tl = t.lower()
            s = sum(p for k, p in POS.items() if k in tl) + sum(p for k, p in NEG.items() if k in tl)
            cands.append({"email": em, "score": s, "fecha": m["fecha"], "texto": t[:300]})
    print(f"Emails: {len(cands)} | matches (score>={a.umbral}): {sum(1 for c in cands if c['score'] >= a.umbral)}")
    best = {}
    for c in sorted(cands, key=lambda x: -x["score"]):
        if c["email"].lower() not in best: best[c["email"].lower()] = c
    matches = [c for c in best.values() if c["score"] >= a.umbral][:a.limit]
    if a.dry_run:
        for c in matches:
            print(f"[DRY {c['score']}] {c['email']} ({c['fecha']}) – {c['texto'][:80].replace(chr(10), ' ')}")
        print("Dry-run: nada creado."); return
    import win32com.client
    ol = win32com.client.Dispatch("Outlook.Application")
    rows = []
    for c in matches:
        mail = ol.CreateItem(0)
        mail.To = c["email"]
        mail.Subject = "Postulación – Fabrizio Simón – Atención / Caja / Stock / Administración"
        mail.Body = BODY.format(fecha=c["fecha"])
        mail.Attachments.Add(str(CV))
        if a.send: mail.Send()
        else: mail.Save()
        rows.append({"empresa": "WhatsApp bolsa Mendoza", "email": c["email"],
                      "puesto": c["texto"][:80].replace("\n", " "), "estado": "outlook enviado" if a.send else "outlook borrador"})
        print(f"{'ENVIADO' if a.send else 'Borrador'} [{c['score']}] {c['email']}")
    if rows:
        hdr = not LOG.exists()
        with open(LOG, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["empresa", "email", "puesto", "estado"])
            if hdr: w.writeheader()
            w.writerows(rows)
    print(f"Listo: {len(rows)}.")

if __name__ == "__main__":
    main()
