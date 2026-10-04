"""Autopostulación Computrabajo: login manual 1 vez → recorre avisos → filtra por CV →
rellena preguntas con respuestas.json → postula. Preguntas desconocidas se guardan, no se inventan.

Uso:
  python auto_apply_compu.py --login                       # 1ra vez: logueate manual, Enter
  python auto_apply_compu.py --dry-run --max 50            # analiza 50, muestra qué haría
  python auto_apply_compu.py --max 15                      # postula hasta 15 matches
Límites: 10-15/día con pausas para no quemar la cuenta.
"""
import argparse, csv, json, re, time
from pathlib import Path

BASE = Path(__file__).parent
SESS = BASE / "compu_session.json"
RESP = BASE / "respuestas.json"
LOG = BASE / "postulaciones_log.csv"
PEND = BASE / "preguntas_pendientes.txt"
CV = BASE / "CV_Fabrizio_Simon.pdf"

POS = {"atencion": 3, "cliente": 3, "caja": 4, "cajero": 4, "stock": 4, "deposito": 3,
       "repositor": 4, "administrativo": 3, "vendedor": 2, "ventas": 2, "mostrador": 3,
       "auditor": 2, "part time": 6, "medio tiempo": 6, "part-time": 6, "media jornada": 6,
       "jornada parcial": 5, "por hora": 4, "horario flexible": 3, "eventual": 3,
       "mendoza": 2, "turno": 1}
NEG = {"senior": -8, "ssr": -6, "gerente": -8, "jefe": -6, "manager": -8, "5 años": -6,
       "ingles avanzado": -4, "ingles excluyente": -8, "developer": -5, "desarrollador": -5,
       "programador": -4,        "ingeniero": -4, "abogado": -10, "farmaceutic": -10, "chofer": -8,
       "licencia": -6, "carnet": -5, "moto": -5, "auto propio": -4, "movilidad propia": -4,
       "solo mujeres": -10, "2 años": -4, "experiencia comprobable": -3, "analista": -5,
       "produccion": -3, "lider": -5, "retail": -3}
UMBRAL = 4
# Exclusión dura: aunque sumen puntos, tu CV no los defiende
EXCLUIR = ("farmaceutic", "abogado", "chofer", "carnet", "licencia de conducir",
           "ingles excluyente", "solo mujeres", "solo hombres", "moto", "auto propio",
           "movilidad propia", "gerente", "senior", "cocinero", "enfermer", "docente",
           "contador", "arquitecto", "farmacia")
PT_KEYS = ("part time", "medio tiempo", "part-time", "media jornada", "jornada parcial", "por hora")

# label del campo -> clave de respuestas.json
CAMPOS = {
    "nombre": ["nombre", "name"], "apellido": ["apellido", "surname"],
    "email": ["email", "correo", "e-mail"], "telefono": ["tel", "phone", "celular"],
    "dni": ["dni", "documento"], "fecha_nacimiento": ["nacimiento", "birth"],
    "edad": ["edad", "age"], "localidad": ["localidad", "ciudad", "zona", "residencia", "domicilio", "city"],
    "direccion": ["direcci", "address"], "disponibilidad": ["disponibilidad", "availability", "horario"],
    "pretension_salarial": ["pretensi", "salario", "salary", "remuneraci"],
    "estudios": ["estudio", "educaci", "formation"], "experiencia_anos": ["experiencia", "experience"],
    "movilidad_propia": ["movilidad", "mobility"], "ingles": ["ingl", "english"],
    "linkedin": ["linkedin"], "presentacion": ["presentaci", "cover", "carta", "contanos", "sobre vos", "about"],
}

def score(texto):
    t = (texto or "").lower()
    if any(e in t for e in EXCLUIR):
        return -999
    return sum(p for k, p in POS.items() if k in t) + sum(p for k, p in NEG.items() if k in t)

def es_pt(t):
    return any(k in (t or "").lower() for k in PT_KEYS)

def _log(url, score, estado):
    hdr = not LOG.exists()
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["url", "score", "estado"])
        if hdr: w.writeheader()
        w.writerow({"url": url, "score": score, "estado": estado})

def _norm(t):
    import re as _re
    return _re.sub(r"\s+", " ", (t or "").lower())

APLICADO_RE = r"(ya te postulaste|ya aplicaste|postulaci.n enviada|candidatura enviada|tu postulaci.n|seguir el proceso en mis postulaciones|postulaci.n exitosa|postulaci.n registrada|gracias por postular|hemos recibido tu)"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max", type=int, default=50)
    ap.add_argument("--keywords", default="caja,atencion cliente,stock,administrativo,repositor,mostrador,deposito,auxiliar,cajero,atencion al publico")
    ap.add_argument("--location", default="Mendoza")
    ap.add_argument("--pages", type=int, default=5)
    ap.add_argument("--candidatos", type=int, default=15)
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()
    resp = json.loads(RESP.read_text(encoding="utf-8"))
    # URLs ya resueltas en corridas anteriores: no reprocesar
    hechos = set()
    if LOG.exists():
        for r in csv.DictReader(open(LOG, encoding="utf-8")):
            if r.get("estado") in ("postulado", "ya postulado"):
                hechos.add(r.get("url", "").split("#")[0])
    # Lista negra manual: un fragmento de URL por línea, # comentarios
    negras = set()
    _nb = BASE / "descartados.txt"
    if _nb.exists():
        for line in _nb.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                negras.add(line)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=a.headless)
        ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        if SESS.exists():
            try: ctx.add_cookies(json.loads(SESS.read_text(encoding="utf-8")))
            except Exception as e: print(f"cookies: {e}")
        pg = ctx.new_page()

        if a.login:
            pg.goto("https://ar.computrabajo.com/", wait_until="domcontentloaded")
            print("LOGUEATE manual y pulsa Enter...")
            input()
            SESS.write_text(json.dumps(ctx.cookies(), indent=1), encoding="utf-8")
            print(f"Sesión en {SESS}"); b.close(); return

        from urllib.parse import quote_plus
        links = []
        for kw in [k.strip() for k in a.keywords.split(",") if k.strip()]:
            for p in range(1, a.pages + 1):
                if len(links) >= a.max: break
                try:
                    pg.goto(f"https://ar.computrabajo.com/trabajo-de-{quote_plus(kw)}-en-{quote_plus(a.location)}?p={p}",
                            wait_until="domcontentloaded", timeout=30000)
                    pg.wait_for_selector(".box_offer, article", timeout=12000)
                except Exception: break
                for c in pg.query_selector_all(".box_offer, article"):
                    try:
                        t = c.query_selector("h2 a, a.js-o-link")
                        href = t.get_attribute("href") if t else ""
                        if href:
                            if not href.startswith("http"): href = "https://ar.computrabajo.com" + href
                            if href not in links: links.append(href)
                    except Exception: pass
                time.sleep(1)
        links = links[:a.max]
        print(f"Avisos: {len(links)}")

        post = []
        for url in links:
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=25000); time.sleep(2)
                txt = pg.inner_text("body")
            except Exception: continue
            s = score(txt)
            btn = None
            for b_ in pg.query_selector_all("button, a"):
                try:
                    if re.search(r"postular", (b_.inner_text() or ""), re.I):
                        btn = b_; break
                except Exception: pass
            post.append({"url": url, "score": s, "match": s >= UMBRAL, "btn": btn is not None, "txt": txt[:2000]})
        # fix simple
        post = [{"url": x["url"], "score": x["score"], "match": x["score"] >= UMBRAL, "btn": x["btn"], "txt": x["txt"]} for x in post]
        print(f"Matches: {sum(1 for x in post if x['match'])} | con botón postular: {sum(1 for x in post if x['match'] and x['btn'])}")
        if a.dry_run:
            for x in post:
                if x["match"]:
                    pt = "PT" if es_pt(x["txt"]) else "  "
                    print(f"[DRY {x['score']}{pt}] btn={x['btn']} {x['url'][:90]}")
            b.close(); return

        SKIP = ("search", "alert", "pwd", "password", "gdpr", "reasons", "comment",
                "report", "captcha", "alertlogged", "createalert", "legalnotice", "follow",
                "cv", "curriculum", "adjunt", "attach")
        CHECK_TERMS = ("termino", "condicion", "acepto", "privacidad", "veracidad", "terms", "policy")
        n = 0
        # part-time primero, luego por puntaje
        candidatos = sorted([x for x in post if x["match"] and x["btn"]],
                            key=lambda x: (es_pt(x["txt"]), x["score"]), reverse=True)[:a.candidatos]
        print(f"Orden: {sum(1 for x in candidatos if es_pt(x['txt']))} PT primero")
        for x in candidatos:
            if x["url"].split("#")[0] in hechos:
                print(f"HECHO (ya resuelto antes): {x['url'][:80]}"); continue
            if any(n in x["url"] for n in negras):
                print(f"NEGRO (descartado manual): {x['url'][:80]}"); continue
            pg.goto(x["url"], wait_until="domcontentloaded", timeout=25000); time.sleep(4)
            try: body0 = _norm(pg.inner_text("body"))
            except Exception: body0 = ""
            if re.search(APLICADO_RE, body0):
                print(f"YA POSTULADO: {x['url'][:80]}")
                _log(x["url"], x["score"], "ya postulado"); hechos.add(x["url"].split("#")[0]); continue
            # 1) clic en Postularme y esperar el formulario real (modal)
            try:
                clicked = False
                for b_ in pg.query_selector_all("button, a"):
                    try:
                        if re.search(r"postular", (b_.inner_text() or ""), re.I):
                            b_.click(); clicked = True; break
                    except Exception: pass
                if not clicked:
                    print(f"SKIP (sin botón postular visible): {x['url'][:80]}"); continue
                time.sleep(3)
            except Exception as e:
                print(f"X clic postular: {e}"); continue
            # 2) ámbito = diálogo/modal si existe, si no toda la página
            scope = None
            for sel in ["[role=dialog]", ".modal", ".ReactModal", ".apply-form", "form"]:
                try:
                    scope = pg.query_selector(sel)
                    if scope: break
                except Exception: pass
            if scope is None:
                scope = pg
            unknowns = []
            try:
                # esperar que carguen las killer questions (AJAX): hasta que el nº de campos se estabilice
                try:
                    prev = -1
                    for _w in range(5):
                        time.sleep(2)
                        cur = len(scope.query_selector_all("input, textarea, select"))
                        if cur == prev: break
                        prev = cur
                except Exception: pass
                radios = {}  # name -> lista de inputs radio
                for inp in scope.query_selector_all("input:not([type=hidden]):not([type=submit]):not([type=button]), textarea, select"):
                    try:
                        typ = (inp.get_attribute("type") or "").lower()
                        label = (inp.get_attribute("placeholder") or "") + " " + (inp.get_attribute("name") or "") + " " + (inp.get_attribute("id") or "")
                    except Exception:
                        typ, label = "", ""
                    if any(s in label.lower() for s in SKIP):
                        continue  # buscador, alertas, legales: no son preguntas
                    if typ == "radio":
                        try: nm = inp.get_attribute("name") or label
                        except Exception: nm = label
                        radios.setdefault(nm, []).append(inp)
                        continue
                    if typ == "checkbox":
                        # solo términos/condiciones; resto (newsletters) se deja sin tocar
                        try: cb_lab = (inp.evaluate("e=>e.parentElement.innerText") or "")[:150]
                        except Exception: cb_lab = label
                        if any(t in cb_lab.lower() for t in CHECK_TERMS):
                            try:
                                if not inp.is_checked(): inp.check()
                            except Exception: pass
                        elif "news" in cb_lab.lower() or "boletin" in cb_lab.lower() or "ofertas" in cb_lab.lower():
                            pass
                        else:
                            unknowns.append("CHECKBOX: " + cb_lab.strip()[:150].replace("\n", " "))
                        continue
                    # texto visible de la pregunta: label asociado, aria-label o padre cercano
                    qtext = ""
                    try:
                        qtext = inp.evaluate("""e=>{
                          let t='';
                          const id=e.id;
                          if(id){const l=document.querySelector(`label[for="${id}"]`); if(l) t+=l.innerText+' ';}
                          let p=e.parentElement, n=0;
                          while(p && n<3){t+=p.innerText.slice(0,200)+' '; p=p.parentElement; n++;}
                          return t.trim().slice(0,250);
                        }""") or ""
                    except Exception: pass
                    key = next((k for k, pats in CAMPOS.items() if any(p in (label + " " + qtext).lower() for p in pats)), None)
                    if key and resp.get(key):
                        try:
                            tag = inp.evaluate("e=>e.tagName")
                            if tag == "SELECT":
                                # elegir opción que contenga la respuesta; si no, 2da (1ra suele ser placeholder)
                                try:
                                    opts = inp.query_selector_all("option")
                                    picked = False
                                    for i, o in enumerate(opts):
                                        try: ot = (o.inner_text() or "")
                                        except Exception: ot = ""
                                        if ot and any(w in ot.lower() for w in str(resp[key]).lower().split()[:3]):
                                            inp.select_option(index=i); picked = True; break
                                    if not picked and len(opts) > 1:
                                        inp.select_option(index=1)
                                except Exception:
                                    inp.select_option(index=0)
                            else:
                                inp.fill(str(resp[key])[:500])
                        except Exception: pass
                    else:
                        unknowns.append((qtext.strip()[:200] + " || " + label.strip()[:80]) if qtext else (label.strip()[:80] or "(campo sin etiqueta)"))
                # Sí/No y opción múltiple según respuestas.json -> cerradas (clic en LABEL, no en input)
                for nm, opts in radios.items():
                    try:
                        grp_txt = opts[0].evaluate("""e=>{let p=e.parentElement,n=0,t='';while(p&&n<4){t+=p.innerText.slice(0,300)+' ';p=p.parentElement;n++;}return t;}""") or ""
                    except Exception: grp_txt = ""
                    ans = None
                    for pat, val in (resp.get("cerradas") or {}).items():
                        if pat.lower() in grp_txt.lower():
                            ans = val; break
                    if ans is None:
                        unknowns.append("RADIO: " + grp_txt.strip()[:200].replace("\n", " "))
                        continue
                    for o in opts:
                        try:
                            info = o.evaluate("""e=>{const id=e.id;let t='';const l=id?document.querySelector(`label[for="${id}"]`):null;if(l)t+=l.innerText+' ';let s=e.nextElementSibling;if(s)t+=s.innerText+' ';return {t:(t+' '+e.value).trim(),for:id||''};}""") or {}
                            lab = info.get("t", "") if isinstance(info, dict) else str(info)
                        except Exception: lab = ""
                        if ans.lower() in lab.lower():
                            try:
                                o.evaluate("""e=>{const id=e.id;const l=id?document.querySelector(`label[for="${id}"]`):null;if(l){l.click();}else{e.click();}}""")
                                time.sleep(0.5); break
                            except Exception: pass
                for f in scope.query_selector_all("input[type=file]"):
                    try: f.set_input_files(str(CV)); break
                    except Exception: pass
            except Exception as e:
                print(f"X form: {e}"); continue
            if unknowns:
                with open(PEND, "a", encoding="utf-8") as f:
                    f.write(f"\n{x['url']}\n" + "\n".join(f" - {u}" for u in unknowns) + "\n")
                print(f"SKIP (preguntas nuevas -> {PEND}): {x['url'][:80]}"); continue
            # enviar (botón dentro del formulario, fallback a página)
            try:
                sent = False
                cands = list(scope.query_selector_all("button")) + list(pg.query_selector_all("[role=dialog] button, .modal button"))
                seen_txt = set()
                for b_ in cands:
                    try:
                        tx = (b_.inner_text() or "").strip()
                    except Exception: continue
                    if not tx or tx in seen_txt: continue
                    seen_txt.add(tx)
                    if re.search(r"(enviar|confirmar|postularme|finalizar|postular)", tx, re.I):
                        try:
                            try: b_.scroll_into_view_if_needed(timeout=5000)
                            except Exception: pass
                            try:
                                b_.click(timeout=5000); time.sleep(4); sent = True; break
                            except Exception:
                                b_.evaluate("e=>e.click()"); time.sleep(4); sent = True; break
                        except Exception: pass
                estado = "sin confirmar"
                if sent:
                    try: body1 = _norm(pg.inner_text("body"))
                    except Exception: body1 = ""
                    if re.search(APLICADO_RE, body1):
                        estado = "postulado"
                    else:
                        estado = "revisar manual"
                        try: pg.screenshot(path=str(BASE / "debug_apply.png"))
                        except Exception: pass
                _log(x["url"], x["score"], estado)
                if estado == "postulado":
                    hechos.add(x["url"].split("#")[0])
                if not sent:
                    # diagnóstico: qué botones hay en el modal
                    try:
                        btns = []
                        for b_ in scope.query_selector_all("button, input[type=submit]"):
                            try: btns.append((b_.inner_text() or b_.get_attribute("value") or "?")[:40])
                            except Exception: pass
                        pg.screenshot(path=str(BASE / "debug_apply.png"))
                        with open(BASE / "debug_botones.txt", "a", encoding="utf-8") as f:
                            f.write(f"\n{x['url']}\nBOTONES: {btns}\n")
                    except Exception: pass
                print(f"{'OK' if estado == 'postulado' else '?'} [{x['score']}] {x['url'][:80]} ({estado})"); n += 1
            except Exception as e:
                print(f"ERROR envío: {e}")
            time.sleep(4)
        b.close()
        print(f"Postulados: {n}. Pendientes en {PEND} si hubo.")

if __name__ == "__main__":
    main()
