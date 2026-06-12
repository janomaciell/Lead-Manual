---
titulo: Pipeline de Leads Fríos — Clyra
cuando_usar: Cada vez que tengo CSVs de Thunderbit + Google Maps y quiero mandar outreach
scripts: procesar_leads.py, hacer_boards.py
---

# Pipeline de Leads Fríos · Clyra

Convierte CSVs crudos de Google Maps en **dos tableros de un click** para mandar
emails (Gmail) y WhatsApp. Yo solo reviso y aprieto enviar.

## Qué hace

1. Limpia la lista (saca basura, "Patrocinado", repetidos).
2. Clasifica cada lead: `WEB_PROPIA` / `SOLO_REDES` / `SIN_WEB`.
3. Entra a la web de los `WEB_PROPIA` y busca un email.
4. Arma el mensaje de cada lead y genera:
   - `emails.html` → botón **Abrir en Gmail** (correo ya escrito).
   - `whatsapp.html` → botón **WhatsApp** (mensaje ya escrito).

> Los que no tienen email caen solos al tablero de WhatsApp. No se pierde ningún lead.

## Setup (una sola vez)

1. Poné `procesar_leads.py` y `hacer_boards.py` en la carpeta con los CSVs.
2. Instalá dependencias:
   ```
   pip install pandas requests beautifulsoup4
   ```
3. Editá **arriba de `hacer_boards.py`** (es lo que firma los mensajes finales):
   ```python
   NOMBRE = "Jano Maciel"          # solo el nombre, SIN "Clyra Studio"
   EMAIL_REMITENTE = "janomaciel1@gmail.com"
   ```

## Uso — los 50 CSVs de una

Parado en la carpeta:

```
python procesar_leads.py *.csv -o leads_todos.csv
python hacer_boards.py leads_todos.csv
```

- El `*.csv` junta los 50 y **deduplica entre ciudades** (saca repetidos solos).
- Abrís `emails.html`, revisás y mandás. Después `whatsapp.html`.
- Botón **"Hecho"** en cada tarjeta para ir tachando.

### Si los prefiero separados por ciudad
```
python procesar_leads.py cosquin.csv -o cosquin.csv
python hacer_boards.py cosquin.csv
```
(repetir por archivo)

## Comandos útiles

| Quiero... | Comando |
|---|---|
| Procesar todo | `python procesar_leads.py *.csv -o leads_todos.csv` |
| Saltar la búsqueda de email (más rápido) | agregar `--sin-email` |
| Regenerar solo los tableros (sin re-scrapear) | `python hacer_boards.py leads_todos.csv` |

## Ojo con esto

- **Email solo aparece en ~30-50% de los WEB_PROPIA.** El resto va por WhatsApp/teléfono. Es normal.
- **Los links de WhatsApp son best-effort** (los teléfonos AR son un quilombo con el "15"). El botón *abre* el chat sin enviar, así que lo veo antes de mandar.
- **Revisar antes de enviar**, sobre todo los primeros de cada tanda.
- **No mandar 200 de golpe.** Tandas chicas para no quemar el mail ni que WhatsApp me marque spam.
- `procesar_leads.py` entra a muchos sitios → con 50 CSVs tarda un rato. Es normal, dejalo correr.

## Flujo mental (resumen)

```
Thunderbit (nicho/ciudad)  ->  CSV crudo
        |
        v
procesar_leads.py  ->  leads.csv  (limpio + emails + mensajes)
        |
        v
hacer_boards.py    ->  emails.html + whatsapp.html
        |
        v
Reviso y mando con un click. Marco "Hecho".
```
