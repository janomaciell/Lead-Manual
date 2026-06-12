---
titulo: Pipeline de Leads Fríos — Clyra
cuando_usar: Cada vez que tengo CSVs de Thunderbit + Google Maps y quiero mandar outreach
scripts: procesar_leads.py, hacer_boards.py
---

# Pipeline de Leads Fríos · Clyra

CSVs de Google Maps → dos tableros de un click (Email + WhatsApp). Yo solo reviso y mando.

## Setup (una vez)

1. Poné `procesar_leads.py` y `hacer_boards.py` en la carpeta con los CSVs.
2. `pip install pandas requests beautifulsoup4`
3. Editá arriba de `hacer_boards.py`:
   ```python
   NOMBRE = "Jano Maciel"          # solo el nombre, sin "Clyra Studio"
   EMAIL_REMITENTE = "janomaciel1@gmail.com"
   ```

## Uso — los 50 CSVs de una

```
python procesar_leads.py *.csv -o leads_todos.csv
python hacer_boards.py leads_todos.csv
```

- El `*.csv` junta los 50 y saca repetidos solo.
- Se generan `emails.html` y `whatsapp.html`. Abrí `emails.html` y empezá.

## Registro (para no repetir)

1. En el tablero marcá **"Enviado"** a medida que mandás.
2. Al terminar, tocá **"Descargar contactados"** → baja `contactados.csv`.
3. Dejá ese `contactados.csv` en la carpeta.
4. La próxima corrida los excluye sola. El archivo se va acumulando.

> El registro de verdad es `contactados.csv`. Descargalo al final de cada sesión.

## Ojo

- El email solo aparece en ~30-50% de los que tienen web. El resto va por WhatsApp.
- Los links de WhatsApp son best-effort: el botón abre el chat sin enviar, así lo ves antes.
- Revisá antes de mandar y no dispares 200 de golpe (para no quemar el mail/WhatsApp).
- Con 50 CSVs, `procesar_leads.py` tarda (entra a muchos sitios). Dejalo correr.

## Resumen

```
Thunderbit → CSV crudo
   -> procesar_leads.py  -> leads.csv (limpio + emails + rubro)
   -> hacer_boards.py    -> emails.html + whatsapp.html
   -> reviso, mando, marco "Enviado", descargo contactados.csv
```
