#!/usr/bin/env python3
"""
procesar_leads.py — Clyra Studio · pipeline de leads fríos
-----------------------------------------------------------
Toma uno o varios CSV de Thunderbit + Google Maps y genera DOS salidas:

  A) leads_procesados.csv  → todos los leads, segmentados.
       · WEB_PROPIA  -> busca email + deja borrador de email.
       · SIN_WEB / SOLO_REDES -> deja mensaje + link de WhatsApp.

  B) whatsapp.html  → tablero con botones. Click = abre WhatsApp con el
       mensaje ya escrito. El texto es editable antes de enviar.

Uso:
    pip install pandas requests beautifulsoup4
    python procesar_leads.py constructora-cosquin-cordoba.csv
    python procesar_leads.py *.csv -o leads_todos.csv

Corré esto en TU máquina (la búsqueda de email entra a sitios externos).
"""

import argparse
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------- #
# CONFIG  — editá esto
# --------------------------------------------------------------------------- #
REMITENTE = "Jano Maciel | Clyra Studio"                       # tu nombre para la firma
STUDIO = "Clyra Studio"
EMAIL_REMITENTE = "janomaciel1@gmail.com"  # <-- poné tu email real

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
TIMEOUT = 8
RUTAS_CONTACTO = ["", "contacto", "contact", "nosotros", "about", "empresa"]
EMAIL_BLOCKLIST = re.compile(
    r"(noreply|no-reply|sentry|wixpress|example|@2x|@3x|\.png|\.jpg|\.webp)", re.I
)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


# --------------------------------------------------------------------------- #
# Limpieza / clasificación
# --------------------------------------------------------------------------- #
def limpiar_glifos(s: str) -> str:
    # Google Maps inyecta íconos del Private Use Area (ej: \ue5d4)
    return re.sub(r"[\ue000-\uf8ff]", "", str(s or "")).strip()


def normalizar_tel(t: str) -> str:
    return re.sub(r"\D", "", str(t or ""))


def telefono_a_wa(phone: str) -> str:
    """
    Convierte un teléfono AR local a formato wa.me (best-effort).
    Objetivo: 549 + (codigo de area + numero) = 13 dígitos.
    Ej: '03541 15-68-0682' -> '5493541680682'
    """
    d = re.sub(r"\D", "", str(phone or "")).lstrip("0")
    if not d:
        return ""
    if d.startswith(("800", "810", "600")):  # números de servicio, sin WhatsApp
        return ""
    # saca el prefijo '15' (móvil local) si así llega a 10 dígitos nacionales
    if len(d) > 10 and "15" in d:
        for m in re.finditer("15", d):
            cand = d[: m.start()] + d[m.end():]
            if len(cand) == 10:
                d = cand
                break
    if len(d) == 10:
        return "549" + d
    if len(d) == 11 and d.startswith("9"):
        return "54" + d
    if len(d) >= 10:
        return "54" + d  # best-effort, revisalo antes de enviar
    return ""


def clasificar_web(url: str) -> str:
    u = (url or "").strip().lower()
    if u in ("", "nan"):
        return "SIN_WEB"
    if any(r in u for r in ("instagram.com", "facebook.com", "linktr", "wa.me", "tiktok.com")):
        return "SOLO_REDES"
    return "WEB_PROPIA"


def cargar_y_limpiar(rutas):
    frames = []
    for r in rutas:
        df = pd.read_csv(r)
        df["_origen"] = r
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    for col in ["Title", "Website", "Phone number", "Address"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).apply(limpiar_glifos)

    df = df[df["Title"].str.lower() != "patrocinado"]
    df = df[df["Title"] != ""]
    # saca títulos basura (ej: ".") — exijo al menos 2 letras
    df = df[df["Title"].str.count(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]") >= 2]

    df["_tel"] = df["Phone number"].apply(normalizar_tel)
    df["_key"] = df.apply(lambda x: x["_tel"] if x["_tel"] else x["Title"].lower(), axis=1)
    df = df.drop_duplicates(subset="_key", keep="first").reset_index(drop=True)

    df["segmento"] = df["Website"].apply(clasificar_web)
    return df


# --------------------------------------------------------------------------- #
# Email finding (solo WEB_PROPIA)
# --------------------------------------------------------------------------- #
def buscar_email(url: str) -> str:
    base = url.rstrip("/")
    if not base.startswith("http"):
        base = "https://" + base
    encontrados = []
    for ruta in RUTAS_CONTACTO:
        full = base if ruta == "" else f"{base}/{ruta}"
        try:
            resp = requests.get(full, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("a[href^=mailto]"):
                raw = a["href"].replace("mailto:", "").split("?")[0].strip()
                m = EMAIL_RE.search(raw)  # saca solo el email, descarta HTML colado
                if m and not EMAIL_BLOCKLIST.search(m.group(0)):
                    encontrados.append(m.group(0))
            for mail in EMAIL_RE.findall(resp.text):
                if not EMAIL_BLOCKLIST.search(mail):
                    encontrados.append(mail)
            if encontrados:
                break
        except requests.RequestException:
            continue
        time.sleep(0.3)
    vistos, out = set(), []
    for m in encontrados:
        m = m.lower()
        if m not in vistos:
            vistos.add(m)
            out.append(m)
    return out[0] if out else ""


# --------------------------------------------------------------------------- #
# Copy
# --------------------------------------------------------------------------- #
def nombre_marca(title: str) -> str:
    return title.split("|")[0].split("-")[0].strip()


def ciudad_de(addr: str) -> str:
    partes = [p.strip() for p in addr.split(",") if p.strip()]
    if not partes:
        return ""
    # 1) ciudad = lo que viene después del código postal (ej: "X5166 Cosquín" -> "Cosquín")
    for p in partes:
        m = re.search(r"\b[A-Z]?\d{4}[A-Z]{0,3}\b\s+(.+)", p)
        if m:
            return m.group(1).strip()
    # 2) fallback: si el último bloque es la provincia, usá el anterior
    if len(partes) >= 2 and partes[-1].lower() in ("córdoba", "cordoba"):
        return partes[-2]
    return partes[-1]


def email_draft(nombre, ciudad):
    ciudad = ciudad or "la zona"
    asunto = f"Una idea para la web de {nombre}"
    cuerpo = (
        f"Hola, ¿cómo estás? Soy {REMITENTE}, de {STUDIO}.\n\n"
        f"Estuve mirando la web de {nombre} y me gustó mucho su trabajo.\n\n"
        f"Te escribo porque se me ocurrieron un par de ideas concretas para que "
        f"generen más consultas directas (mejorando la velocidad, la claridad de la propuesta y la captación de contactos).\n\n"
        f"¿Te interesaría que te las comparta en un mensaje cortito y sin compromiso?\n\n"
        f"Un saludo,\n\n"
        f"{REMITENTE}\n"
        f"{STUDIO} — Diseño & Desarrollo Web\n"
        f"{EMAIL_REMITENTE}"
    )
    return asunto, cuerpo


def wa_mensaje(seg, nombre, ciudad, url=""):
    ciudad = ciudad or "tu zona"
    u = (url or "").lower()
    if seg == "SOLO_REDES":
        red = "tu Instagram" if "instagram" in u else "tu Facebook" if "facebook" in u else "tus redes"
        return (
            f"Hola! ¿Cómo va? Soy {REMITENTE} de {STUDIO}. Vi {red} de {nombre} y se ve muy bueno el laburo. "
            f"Como en {ciudad}, hoy depender solo de redes limita a los clientes que buscan directo en Google. "
            f"¿Te gustaría ver una propuesta rápida de cómo quedaría una web propia? Sin compromiso."
        )
    return (  # SIN_WEB
        f"Hola, ¿cómo estás? Soy {REMITENTE} de {STUDIO}. Busqué a {nombre} en Google pero no "
        f"encontré su web propia. Para {ciudad}, tener un sitio es clave para convertir las búsquedas en clientes. "
        f"Te puedo armar en unos minutos una idea/diseño rápido de cómo quedaría, sin compromiso. ¿Te interesaría verlo?"
    )


# --------------------------------------------------------------------------- #
def link_web_redes(url):
    u = str(url).strip().lower()
    if not u or u in ("nan", ""):
        return None, None
    href = url
    if not href.startswith(("http://", "https://")):
        href = "https://" + href
    if any(r in u for r in ("instagram.com", "facebook.com", "linktr", "wa.me", "tiktok.com", "twitter.com", "linkedin.com", "youtube.com")):
        return "Redes", href
    return "Web", href


def generar_html(df, salida_html):
    wa_df = df[df["segmento"].isin(["SIN_WEB", "SOLO_REDES"])].copy()
    wa_df = wa_df[wa_df["_wa"] != ""]  # solo los que tienen teléfono válido

    cards = []
    for _, r in wa_df.iterrows():
        nombre = html.escape(nombre_marca(r["Title"]))
        ciudad = html.escape(ciudad_de(r.get("Address", "")) or "—")
        tel = html.escape(r["Phone number"] or "—")
        seg = r["segmento"]
        msg = html.escape(r["_wa_msg"])
        wa = r["_wa"]
        badge = "Sin web" if seg == "SIN_WEB" else "Solo redes"

        lbl, href = link_web_redes(r.get("Website", ""))
        link_html = f'<a class="link-btn" href="{html.escape(href)}" target="_blank">{lbl} ↗</a>' if href else ''

        cards.append(f"""
      <article class="card" data-seg="{seg}" data-name="{nombre.lower()}">
        <div class="head">
          <span class="badge {seg}">{badge}</span>
          <button class="done" onclick="toggleDone(this)">Hecho</button>
        </div>
        <h2>{nombre}</h2>
        <p class="meta">{ciudad} · {tel}</p>
        <textarea>{msg}</textarea>
        <div class="actions">
          <a class="send" href="https://wa.me/{wa}?text=" target="_blank"
             onclick="this.href='https://wa.me/{wa}?text='+encodeURIComponent(this.closest('.card').querySelector('textarea').value)">
             Enviar por WhatsApp
          </a>
          {link_html}
        </div>
      </article>""")

    total = len(cards)
    doc = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clyra · Outreach WhatsApp</title>
<style>
  :root{{--bg:#0a0a0a;--card:#141414;--line:#262626;--txt:#ededed;--mut:#8a8a8a;--cyan:#00F5D4;--wa:#25D366;}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--txt);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;padding:24px}}
  header{{max-width:1100px;margin:0 auto 20px}}
  h1{{margin:0 0 4px;font-size:22px}}h1 span{{color:var(--cyan)}}
  .sub{{color:var(--mut);font-size:14px}}
  .bar{{max-width:1100px;margin:0 auto 18px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
  input,select{{background:var(--card);border:1px solid var(--line);color:var(--txt);padding:9px 12px;border-radius:8px;font-size:14px}}
  input{{flex:1;min-width:200px}}
  .count{{color:var(--mut);font-size:13px;margin-left:auto}}
  .count b{{color:var(--cyan)}}
  .grid{{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;display:flex;flex-direction:column;gap:10px}}
  .card.is-done{{opacity:.4}}
  .head{{display:flex;justify-content:space-between;align-items:center}}
  .badge{{font-size:11px;padding:3px 9px;border-radius:99px;font-weight:600;letter-spacing:.02em}}
  .badge.SIN_WEB{{background:#3a1d1d;color:#ff9b9b}}
  .badge.SOLO_REDES{{background:#1d2e3a;color:#9bd2ff}}
  .done{{background:none;border:1px solid var(--line);color:var(--mut);font-size:12px;padding:3px 10px;border-radius:7px;cursor:pointer}}
  .done:hover{{color:var(--txt);border-color:var(--mut)}}
  h2{{margin:0;font-size:17px}}
  .meta{{margin:0;color:var(--mut);font-size:13px}}
  textarea{{width:100%;min-height:120px;background:#0e0e0e;border:1px solid var(--line);color:var(--txt);border-radius:8px;padding:10px;font:13px/1.5 inherit;resize:vertical}}
  .actions{{display:flex;gap:8px;width:100%;align-items:center}}
  .actions .send{{flex:1;margin:0}}
  .send{{display:block;text-align:center;background:var(--wa);color:#04210f;font-weight:700;text-decoration:none;padding:11px;border-radius:9px;transition:.15s}}
  .send:hover{{filter:brightness(1.08)}}
  .link-btn{{display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:11px 16px;border-radius:9px;font-weight:600;background:var(--line);color:var(--txt);border:1px solid var(--line);font-size:13px;transition:background 0.2s,border-color 0.2s;white-space:nowrap}}
  .link-btn:hover{{background:#3a3a3a;border-color:var(--mut)}}
</style></head>
<body>
  <header>
    <h1><span>Clyra</span> · Outreach por WhatsApp</h1>
    <p class="sub">Click en "Enviar" abre WhatsApp con el mensaje listo. Editá el texto antes si querés.</p>
  </header>
  <div class="bar">
    <input id="q" placeholder="Buscar por nombre..." oninput="filtrar()">
    <select id="seg" onchange="filtrar()">
      <option value="">Todos los segmentos</option>
      <option value="SIN_WEB">Sin web</option>
      <option value="SOLO_REDES">Solo redes</option>
    </select>
    <span class="count"><b id="done">0</b> / {total} contactados</span>
  </div>
  <div class="grid" id="grid">{''.join(cards)}
  </div>
<script>
  function toggleDone(btn){{
    const c=btn.closest('.card'); c.classList.toggle('is-done');
    btn.textContent=c.classList.contains('is-done')?'Deshacer':'Hecho';
    document.getElementById('done').textContent=document.querySelectorAll('.card.is-done').length;
  }}
  function filtrar(){{
    const q=document.getElementById('q').value.toLowerCase();
    const s=document.getElementById('seg').value;
    document.querySelectorAll('.card').forEach(c=>{{
      const ok=c.dataset.name.includes(q) && (!s || c.dataset.seg===s);
      c.style.display=ok?'':'none';
    }});
  }}
</script>
</body></html>"""
    with open(salida_html, "w", encoding="utf-8") as f:
        f.write(doc)
    return total


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def procesar(rutas, salida, buscar_emails=True, workers=8):
    df = cargar_y_limpiar(rutas)
    print(f"Leads únicos: {len(df)}")
    print(df["segmento"].value_counts().to_string(), "\n")

    # email solo en WEB_PROPIA
    df["email"] = ""
    if buscar_emails:
        idx = df.index[df["segmento"] == "WEB_PROPIA"].tolist()
        print(f"Buscando email en {len(idx)} sitios propios...")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            fut = {ex.submit(buscar_email, df.at[i, "Website"]): i for i in idx}
            for f in as_completed(fut):
                i = fut[f]
                try:
                    df.at[i, "email"] = f.result()
                except Exception:
                    df.at[i, "email"] = ""
        print(f"Emails encontrados: {(df['email'] != '').sum()}/{len(idx)}\n")

    # copy por lead
    asunto, cuerpo, wmsg, wlink = [], [], [], []
    for _, r in df.iterrows():
        nombre = nombre_marca(r["Title"])
        ciudad = ciudad_de(r.get("Address", ""))
        if r["segmento"] == "WEB_PROPIA":
            a, c = email_draft(nombre, ciudad)
            asunto.append(a); cuerpo.append(c); wmsg.append(""); wlink.append("")
        else:
            m = wa_mensaje(r["segmento"], nombre, ciudad, r.get("Website", ""))
            wa = telefono_a_wa(r["Phone number"])
            link = f"https://wa.me/{wa}" if wa else ""
            asunto.append(""); cuerpo.append(""); wmsg.append(m); wlink.append(link)
    df["draft_asunto"] = asunto
    df["draft_email"] = cuerpo
    df["_wa_msg"] = wmsg
    df["_wa"] = df["Phone number"].apply(telefono_a_wa)
    df["wa_mensaje"] = wmsg
    df["wa_link"] = wlink
    df["estado"] = "pendiente"

    cols = ["Title", "segmento", "email", "Phone number", "Website", "Address",
            "draft_asunto", "draft_email", "wa_mensaje", "wa_link", "estado", "_origen"]
    cols = [c for c in cols if c in df.columns]
    df[cols].to_csv(salida, index=False)
    print(f"✓ CSV: {salida}")

    html_out = salida.rsplit(".", 1)[0] + "_whatsapp.html"
    n = generar_html(df, html_out)
    print(f"✓ HTML WhatsApp ({n} leads con botón): {html_out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("-o", "--out", default="leads_procesados.csv")
    ap.add_argument("--sin-email", action="store_true")
    args = ap.parse_args()
    procesar(args.csv, args.out, buscar_emails=not args.sin_email)
