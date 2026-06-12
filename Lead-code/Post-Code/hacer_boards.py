#!/usr/bin/env python3
"""
hacer_boards.py — Clyra Studio
Toma el CSV YA PROCESADO (el que te dejó procesar_leads.py, con la columna 'email')
y genera dos tableros de un click, SIN volver a scrapear:

  · emails.html    -> los que tienen email. Botón "Abrir en Gmail" = correo ya escrito.
  · whatsapp.html  -> el resto (con teléfono). Botón verde = WhatsApp ya escrito.

Uso:
    python hacer_boards.py leads_cosquin.csv

Editá NOMBRE / EMAIL abajo con tus datos.
"""

import html
import json
import os
import re
import sys
from urllib.parse import quote

import pandas as pd

# --------------------------------------------------------------------------- #
# CONFIG  — SOLO tu nombre, sin "Clyra Studio" (eso se agrega solo)
# --------------------------------------------------------------------------- #
NOMBRE = "Jano Maciel"
STUDIO = "Clyra Studio"
EMAIL_REMITENTE = "janomaciel1@gmail.com"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def nombre_marca(t):
    return str(t).split("|")[0].split("-")[0].strip()


def ciudad_de(addr):
    partes = [p.strip() for p in str(addr).split(",") if p.strip()]
    if not partes:
        return "tu zona"
    for p in partes:
        m = re.search(r"\b[A-Z]?\d{4}[A-Z]{0,3}\b\s+(.+)", p)
        if m:
            return m.group(1).strip()
    if len(partes) >= 2 and partes[-1].lower() in ("córdoba", "cordoba"):
        return partes[-2]
    return partes[-1]


def tel_a_wa(phone):
    d = re.sub(r"\D", "", str(phone or "")).lstrip("0")
    if not d or d.startswith(("800", "810", "600")):
        return ""
    if len(d) > 10 and "15" in d:
        for m in re.finditer("15", d):
            c = d[: m.start()] + d[m.end():]
            if len(c) == 10:
                d = c
                break
    if len(d) == 10:
        return "549" + d
    if len(d) == 11 and d.startswith("9"):
        return "54" + d
    return "54" + d if len(d) >= 10 else ""


def rubro(title):
    """Detecta el rubro del lead desde el nombre para personalizar el mensaje."""
    t = str(title).lower()
    if any(k in t for k in ("inmobiliaria", "propiedades", "emprendimiento", "desarrollos", "desarrollista")):
        return ("desarrollos inmobiliarios", "tus unidades y emprendimientos")
    if any(k in t for k in ("arquitectura", "estudio", " arq", "mmo", "maestros mayores")):
        return ("estudio de arquitectura", "tus proyectos")
    if "piscina" in t:
        return ("piscinas", "tus piscinas con fotos que vendan")
    if any(k in t for k in ("herrer", "estructuras", "steel", "metal")):
        return ("herrería y estructuras", "tus trabajos terminados")
    if any(k in t for k in ("pavimento", "hormig", "arido", "árido", "revestimiento")):
        return ("obra civil", "tus obras y servicios")
    if "vivienda" in t:
        return ("viviendas", "tus modelos de vivienda")
    return ("constructora", "tus obras terminadas")


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


def email_asunto_cuerpo(nombre):
    desc, cosa = rubro(nombre)
    asunto = f"Una idea para la web de {nombre}"
    cuerpo = (
        f"Hola, ¿cómo estás? Soy {NOMBRE}, de {STUDIO}.\n\n"
        f"Estuve mirando la web de {nombre} y me gustó mucho su trabajo como {desc}.\n\n"
        f"Te escribo porque se me ocurrieron un par de ideas concretas para que {cosa} "
        f"generen más consultas directas (mejorando la velocidad, la claridad de la propuesta y la captación de contactos).\n\n"
        f"¿Te interesaría que te las comparta en un mensaje cortito y sin compromiso?\n\n"
        f"Un saludo,\n\n"
        f"{NOMBRE}\n"
        f"{STUDIO} — Diseño & Desarrollo Web\n"
        f"{EMAIL_REMITENTE}"
    )
    return asunto, cuerpo


def wa_texto(seg, nombre, ciudad, url=""):
    u = str(url).lower()
    desc, cosa = rubro(nombre)
    if seg == "WEB_PROPIA":
        return (
            f"Hola! ¿Cómo estás? Soy {NOMBRE} de {STUDIO}. Estuve viendo la web de {nombre} "
            f"y me pareció excelente su trabajo como {desc}. Tengo un par de ideas simples "
            f"para que {cosa} consigan más clientes. ¿Te las puedo compartir por acá, sin compromiso?"
        )
    if seg == "SOLO_REDES":
        red = "tu Instagram" if "instagram" in u else "tu Facebook" if "facebook" in u else "tus redes"
        return (
            f"Hola! ¿Cómo va? Soy {NOMBRE} de {STUDIO}. Vi {red} de {nombre} y se ve muy bueno el laburo. "
            f"Como {desc} en {ciudad}, hoy depender solo de redes limita a los clientes que buscan directo en Google. "
            f"¿Te gustaría ver una propuesta rápida de cómo quedaría una web propia mostrando {cosa}? Sin compromiso."
        )
    return (
        f"Hola, ¿cómo estás? Soy {NOMBRE} de {STUDIO}. Busqué a {nombre} en Google pero no "
        f"encontré su web propia. Para {desc} en {ciudad}, tener un sitio es clave para convertir las búsquedas en clientes. "
        f"Te puedo armar en unos minutos una idea/diseño rápido de cómo quedaría mostrando {cosa}, sin compromiso. ¿Te interesaría verlo?"
    )


CSS = """
  :root{--bg:#0a0a0a;--card:#141414;--line:#262626;--txt:#ededed;--mut:#8a8a8a;--cyan:#00F5D4;--wa:#25D366;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.5 system-ui,Segoe UI,sans-serif;padding:24px}
  header{max-width:1100px;margin:0 auto 16px}
  h1{margin:0 0 4px;font-size:22px}h1 span{color:var(--cyan)}
  .sub{color:var(--mut);font-size:14px}
  .nav{max-width:1100px;margin:0 auto 14px;display:flex;gap:8px}
  .nav a{color:var(--mut);text-decoration:none;border:1px solid var(--line);padding:6px 12px;border-radius:8px;font-size:13px}
  .nav a.on{color:var(--cyan);border-color:var(--cyan)}
  .bar{max-width:1100px;margin:0 auto 18px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
  input{flex:1;min-width:200px;background:var(--card);border:1px solid var(--line);color:var(--txt);padding:9px 12px;border-radius:8px}
  .count{color:var(--mut);font-size:13px;margin-left:auto}.count b{color:var(--cyan)}
  .grid{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;display:flex;flex-direction:column;gap:10px}
  .card.is-done{opacity:.4}
  .head{display:flex;justify-content:space-between;align-items:center}
  .badge{font-size:11px;padding:3px 9px;border-radius:99px;font-weight:600}
  .badge.mail{background:#1d2e3a;color:#9bd2ff}.badge.wa{background:#16301f;color:#9be6b4}
  .done{background:none;border:1px solid var(--line);color:var(--mut);font-size:12px;padding:3px 10px;border-radius:7px;cursor:pointer}
  .dl{background:var(--card);border:1px solid var(--cyan);color:var(--cyan);padding:9px 14px;border-radius:8px;font-size:13px;cursor:pointer;font-weight:600}
  .dl:hover{background:var(--cyan);color:#04211e}
  h2{margin:0;font-size:17px}.meta{margin:0;color:var(--mut);font-size:13px;word-break:break-all}
  input.su{width:100%;background:#0e0e0e;border:1px solid var(--line);color:var(--txt);border-radius:8px;padding:8px;font-size:13px}
  textarea{width:100%;min-height:120px;background:#0e0e0e;border:1px solid var(--line);color:var(--txt);border-radius:8px;padding:10px;font:13px/1.5 inherit;resize:vertical}
  .actions{display:flex;gap:8px;width:100%;align-items:center}
  .actions .send{flex:1;margin:0}
  .send{display:block;text-align:center;font-weight:700;text-decoration:none;padding:11px;border-radius:9px}
  .send.mail{background:var(--cyan);color:#04211e}.send.wa{background:var(--wa);color:#04210f}
  .send:hover{filter:brightness(1.08)}
  .link-btn{display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:11px 16px;border-radius:9px;font-weight:600;background:var(--line);color:var(--txt);border:1px solid var(--line);font-size:13px;transition:background 0.2s,border-color 0.2s;white-space:nowrap}
  .link-btn:hover{background:#3a3a3a;border-color:var(--mut)}
"""

JS = """
  var LS='clyra_enviados';
  function load(){try{return JSON.parse(localStorage.getItem(LS)||'[]')}catch(e){return[]}}
  function save(a){try{localStorage.setItem(LS,JSON.stringify(a))}catch(e){}}
  function recount(){document.getElementById('done').textContent=document.querySelectorAll('.card.is-done').length;}
  function toggleDone(b){var c=b.closest('.card');c.classList.toggle('is-done');
    var on=c.classList.contains('is-done');b.textContent=on?'Deshacer':'Enviado';
    var k=c.dataset.key,a=load();var i=a.indexOf(k);
    if(on&&i<0)a.push(k);if(!on&&i>=0)a.splice(i,1);save(a);recount();}
  function filtrar(){var q=document.getElementById('q').value.toLowerCase();
    document.querySelectorAll('.card').forEach(function(c){c.style.display=c.dataset.name.includes(q)?'':'none';});}
  function descargar(){
    var prev=window.PREV||[];var s={};prev.forEach(function(k){s[k]=1});
    document.querySelectorAll('.card.is-done').forEach(function(c){s[c.dataset.key]=1});
    var csv='key\\n'+Object.keys(s).join('\\n')+'\\n';
    var b=new Blob([csv],{type:'text/csv'});var u=URL.createObjectURL(b);
    var a=document.createElement('a');a.href=u;a.download='contactados.csv';a.click();URL.revokeObjectURL(u);}
  window.addEventListener('load',function(){
    var a=load();document.querySelectorAll('.card').forEach(function(c){
      if(a.indexOf(c.dataset.key)>=0){c.classList.add('is-done');
        var b=c.querySelector('.done');if(b)b.textContent='Deshacer';}});
    recount();});
"""


def head(titulo, activo, total):
    nav = (
        '<a href="emails.html" class="%s">📧 Email</a>'
        '<a href="whatsapp.html" class="%s">💬 WhatsApp</a>'
        % ("on" if activo == "mail" else "", "on" if activo == "wa" else "")
    )
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{titulo}</title>
<style>{CSS}</style></head><body>
<header><h1><span>Clyra</span> · {titulo}</h1>
<p class="sub">Marcá "Enviado" a medida que mandás. Al terminar, tocá "Descargar contactados" y dejá ese archivo en la carpeta: en la próxima corrida no vuelven a aparecer.</p></header>
<div class="nav">{nav}</div>
<div class="bar"><input id="q" placeholder="Buscar por nombre..." oninput="filtrar()">
<button class="dl" onclick="descargar()">⬇ Descargar contactados</button>
<span class="count"><b id="done">0</b> / {total} enviados</span></div>
<div class="grid">"""


def clave(email, phone):
    """Identificador estable de un lead: email, o sino el teléfono en dígitos."""
    e = str(email or "").strip().lower()
    if e and "@" in e:
        return e
    d = re.sub(r"\D", "", str(phone or ""))
    return d


def cargar_contactados(path="contactados.csv"):
    if not os.path.exists(path):
        return set()
    try:
        c = pd.read_csv(path)
        col = "key" if "key" in c.columns else c.columns[0]
        return set(str(x).strip().lower() for x in c[col].dropna())
    except Exception:
        return set()


def main(csv_path):
    df = pd.read_csv(csv_path)
    for c in ["Title", "email", "Phone number", "Website", "Address", "segmento"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str).str.strip()
        else:
            df[c] = ""

    ya = cargar_contactados()
    prev = sorted(ya)
    saltados = 0

    mail_cards, wa_cards = [], []
    for _, r in df.iterrows():
        k = clave(r["email"], r["Phone number"])
        if k and k in ya:          # ya lo contactaste en una tanda anterior
            saltados += 1
            continue
        nombre = nombre_marca(r["Title"])
        ne = html.escape(nombre)
        ciudad = ciudad_de(r["Address"])
        lbl, href = link_web_redes(r["Website"])
        link_html = f'<a class="link-btn" href="{html.escape(href)}" target="_blank">{lbl} ↗</a>' if href else ''

        if r["email"] and "@" in r["email"]:
            asunto, cuerpo = email_asunto_cuerpo(nombre)
            mail_cards.append(f"""
  <article class="card" data-name="{ne.lower()}" data-key="{html.escape(k)}">
    <div class="head"><span class="badge mail">Email</span>
      <button class="done" onclick="toggleDone(this)">Enviado</button></div>
    <h2>{ne}</h2><p class="meta">{html.escape(r['email'])}</p>
    <input class="su" value="{html.escape(asunto)}">
    <textarea>{html.escape(cuerpo)}</textarea>
    <div class="actions">
      <a class="send mail" href="mailto:{html.escape(r['email'])}"
         onclick="this.href='mailto:{html.escape(r['email'])}?subject='+encodeURIComponent(this.closest('.card').querySelector('.su').value)+'&body='+encodeURIComponent(this.closest('.card').querySelector('textarea').value)">Abrir en Email</a>
      {link_html}
    </div>
  </article>""")
        else:
            wa = tel_a_wa(r["Phone number"])
            if not wa:
                continue
            txt = wa_texto(r["segmento"], nombre, ciudad, r["Website"])
            wa_cards.append(f"""
  <article class="card" data-name="{ne.lower()}" data-key="{html.escape(k)}">
    <div class="head"><span class="badge wa">WhatsApp</span>
      <button class="done" onclick="toggleDone(this)">Enviado</button></div>
    <h2>{ne}</h2><p class="meta">{ciudad} · {html.escape(r['Phone number'] or '—')}</p>
    <textarea>{html.escape(txt)}</textarea>
    <div class="actions">
      <a class="send wa" target="_blank" href="https://wa.me/{wa}?text="
         onclick="this.href='https://wa.me/{wa}?text='+encodeURIComponent(this.closest('.card').querySelector('textarea').value)">Enviar por WhatsApp</a>
      {link_html}
    </div>
  </article>""")

    prev_js = "<script>window.PREV=" + json.dumps(prev) + ";</script>"
    tail = f"</div>{prev_js}<script>{JS}</script></body></html>"
    with open("emails.html", "w", encoding="utf-8") as f:
        f.write(head("Outreach por Email", "mail", len(mail_cards)) + "".join(mail_cards) + tail)
    with open("whatsapp.html", "w", encoding="utf-8") as f:
        f.write(head("Outreach por WhatsApp", "wa", len(wa_cards)) + "".join(wa_cards) + tail)

    if ya:
        print(f"Salteados por estar en contactados.csv: {saltados}")
    print(f"OK: emails.html   -> {len(mail_cards)} leads con boton Email")
    print(f"OK: whatsapp.html -> {len(wa_cards)} leads con boton WhatsApp")
    print("Abri emails.html en el navegador y empeza por ahi.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Uso: python hacer_boards.py leads_procesados.csv")
    main(sys.argv[1])
