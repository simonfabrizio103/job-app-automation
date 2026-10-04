# job-app-automation

Suite de automatización de postulaciones laborales escrita en **Python** y **Playwright**. Automatiza el ciclo completo de búsqueda de empleo: **scrapear avisos → puntuarlos contra el CV → extraer emails de contacto → enviar el CV → registrar el resultado**, con control de duplicados en cada paso.

Desarrollada como proyecto personal para agilizar la búsqueda de trabajo en Mendoza, Argentina.

> ⚠️ Usá esta suite sobre los sitios públicos de bolsas de empleo respetando sus términos de uso. Los envíos tienen límite autoimpuesto configurable (10–15 postulaciones/día por defecto) para no spamear a las empresas.

## Requisitos

- Python 3.10+
- `pip install -r requirements.txt`
- `playwright install chromium`

## Scripts

| Script | Función |
|---|---|
| `scrap_jobs.py` | Scrapea Bumeran, ZonaJobs y Computrabajo con Playwright: extrae empresa, puesto y email del aviso (regex + filtro de emails genéricos tipo `noreply@`), con keywords y ubicación configurables. |
| `scrap_linkedin_posts.py` | Scrapea posts de LinkedIn con sesión persistente: login una sola vez (`--login`), corridas posteriores headless, deduplicación por set. |
| `auto_apply_compu.py` | Autopostulación en Computrabajo: login persistido, scoring de avisos por keywords (positivas/negativas con umbral), mapeo de 16 campos del formulario, respuestas guardadas en JSON, preguntas desconocidas encoladas (no se inventan respuestas) y log CSV anti-duplicados. |
| `auto_postula.py` | Pipeline end-to-end: scrapea → scorea contra el CV → si hay match y email, envía el CV por Gmail (SMTP) y registra en `envios_log.csv`. |
| `enviar_cv.py` | Envío semi-automático de CV por Gmail con log CSV anti-duplicados (clave `email + puesto`). |
| `enviar_outlook.py` | Crea borradores (o envía) en Outlook ya abierto, vía COM (`win32com`), **sin credenciales**. |
| `extraer_y_enviar.py` | Para cada link de `postular_manual.csv`: entra al aviso, extrae el email y arma el borrador en Outlook. |
| `whatsapp_postula.py` | Parsea la exportación de un chat de WhatsApp de bolsas de empleo (regex), extrae emails, scorea y crea borradores en Outlook. |

Todos los scripts usan `argparse` con flags `--dry-run` (simular sin enviar) y `--limit` (acotar volumen).

## Seguridad

- Las credenciales **nunca están en el código**: se leen de variables de entorno.
  ```bat
  set GMAIL_USER=tu@gmail.com
  set GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   (App Password, NO tu clave normal)
  ```
- Las sesiones de Playwright (`compu_session.json`, `linkedin_session/`) y los logs son archivos **locales y privados**: este repo los ignora por defecto.

## Estructura

```
├── scrap_jobs.py             # scraping de bolsas (Bumeran/ZonaJobs/Computrabajo)
├── scrap_linkedin_posts.py   # scraping de LinkedIn
├── auto_apply_compu.py       # autopostulación Computrabajo (el más completo)
├── auto_postula.py           # pipeline end-to-end con envío por Gmail
├── enviar_cv.py              # envío Gmail con anti-duplicados
├── enviar_outlook.py         # borradores Outlook vía COM
├── extraer_y_enviar.py       # extrae emails de links y arma borradores
└── whatsapp_postula.py       # parser de avisos de WhatsApp
```

## Licencia

Proyecto personal. Usá bajo tu propio criterio y responsabilidad.
