#!/usr/bin/env python3
"""Genera el reporte mensual de finanzas personales en PDF y lo envia por correo (Resend).

Solo usa la libreria estandar. Necesita Chrome o Edge para convertir el HTML a PDF.
No imprime montos en la consola: el repositorio es publico y sus registros de ejecucion tambien.
"""
import argparse
import base64
import calendar
import csv
import datetime as dt
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
UA = "mis-finanzas-reporte/1.0"
LIMA = dt.timezone(dt.timedelta(hours=-5))


def money(v, sign=False):
    s = "S/ {:,.2f}".format(abs(v))
    if v < 0:
        return "-" + s
    return ("+" + s) if sign and v > 0 else s


def esc(t):
    return html.escape(str(t))


# ----------------------------------------------------------------- datos
def filas_desde_csv(path):
    out = []
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            out.append({"date": r["date"], "type": r["type"], "name": r["name"], "pen": float(r["amountPEN"] or 0),
                        "category": r["category"], "method": r["paymentMethod"], "entity": r["financialEntity"]})
    return out


def filas_desde_supabase(url, key):
    out, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"select": "date,type,name,amount_pen,category,payment_method,financial_entity",
                                    "order": "date.asc", "limit": 1000, "offset": offset})
        req = urllib.request.Request("%s/rest/v1/movements?%s" % (url.rstrip("/"), q),
                                     headers={"apikey": key, "Authorization": "Bearer " + key, "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            page = json.load(resp)
        for r in page:
            out.append({"date": r["date"], "type": r["type"], "name": r["name"], "pen": float(r["amount_pen"] or 0),
                        "category": r["category"], "method": r["payment_method"], "entity": r["financial_entity"]})
        if len(page) < 1000:
            return out
        offset += 1000


# ----------------------------------------------------------------- calculo
def calcular(rows, year, month, meta_pct):
    for r in rows:
        y, m, d = (int(x) for x in r["date"].split("-"))
        r["y"], r["m"], r["d"] = y, m, d

    def of(y, m):
        return [r for r in rows if r["y"] == y and r["m"] == m]

    def totals(sel):
        ing = sum(r["pen"] for r in sel if r["type"] == "Ingreso")
        gas = sum(r["pen"] for r in sel if r["type"] == "Gasto")
        return ing, gas, ing - gas, ((ing - gas) / ing * 100 if ing > 0 else None)

    cur = of(year, month)
    py, pm = (year, month - 1) if month > 1 else (year - 1, 12)
    prev = of(py, pm)
    c = {"year": year, "month": month, "pm": pm, "meta": meta_pct, "n": len(cur)}
    c["ing"], c["gas"], c["ah"], c["pct"] = totals(cur)
    c["p_ing"], c["p_gas"], c["p_ah"], c["p_pct"] = totals(prev)
    exp = [r for r in cur if r["type"] == "Gasto"]
    cat = defaultdict(float)
    meth = defaultdict(float)
    days = defaultdict(float)
    for r in exp:
        cat[r["category"]] += r["pen"]
        meth[r["method"] or "Sin método"] += r["pen"]
        days[r["d"]] += r["pen"]
    c["cat"], c["meth"], c["days"] = cat, meth, days
    c["prev_cat"] = defaultdict(float)
    for r in prev:
        if r["type"] == "Gasto":
            c["prev_cat"][r["category"]] += r["pen"]
    c["top5"] = sorted(exp, key=lambda r: -r["pen"])[:5]
    c["ndays"] = calendar.monthrange(year, month)[1]
    c["credit"] = sum(r["pen"] for r in exp if (r["method"] or "").startswith("Crédito"))
    serie = []
    for m in range(1, 13):
        sel = of(year, m)
        i_, g_, a_, p_ = totals(sel)
        serie.append({"m": m, "ing": i_, "gas": g_, "ah": a_, "pct": p_, "has": bool(sel)})
    c["serie"] = serie
    con = [s for s in serie if s["has"] and s["m"] <= month]
    c["con"] = con
    c["ytd_ing"] = sum(s["ing"] for s in con)
    c["ytd_gas"] = sum(s["gas"] for s in con)
    c["ytd_ah"] = c["ytd_ing"] - c["ytd_gas"]
    c["ytd_pct"] = c["ytd_ah"] / c["ytd_ing"] * 100 if c["ytd_ing"] else None
    c["meses_ok"] = sum(1 for s in con if s["pct"] is not None and s["pct"] >= meta_pct)
    return c


# ----------------------------------------------------------------- HTML
CSS = """
@page{size:A4;margin:0}
:root{--navy:#0a1330;--navy2:#1e3a8a;--blue:#2563eb;--sky:#93c5fd;--ink:#0e1a33;--mut:#5a6885;--line:#d9e2f1;--tint:#eef3fc;--ok:#0f7b4f;--bad:#b42318}
*{box-sizing:border-box}
html,body{margin:0;background:#fff;color:var(--ink);font:10.5pt/1.45 "IBM Plex Sans","Segoe UI",Arial,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{width:210mm;height:297mm;padding:0 0 12mm;position:relative;break-after:page;overflow:hidden}
.page:last-child{break-after:auto}
.band{background:linear-gradient(120deg,#0a1330 0%,#12234f 55%,#1e3a8a 100%);color:#fff;padding:13mm 14mm 9mm}
.band .eb{font-size:8pt;letter-spacing:.14em;text-transform:uppercase;color:#b9c9ee;font-weight:600}
.band h1{margin:3px 0 0;font-size:23pt;line-height:1.1;font-weight:700}
.band .sub{margin-top:6px;color:#cbd8f5;font-size:10.5pt}
.wrap{padding:0 14mm}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:-6mm}
.kpi{background:#fff;border:1px solid var(--line);border-top:4px solid var(--blue);border-radius:8px;padding:9px 10px;box-shadow:0 2px 6px rgba(10,19,48,.08)}
.kpi .l{font-size:7.5pt;letter-spacing:.09em;text-transform:uppercase;color:var(--mut);font-weight:600}
.kpi .v{font-size:15pt;font-weight:700;margin-top:3px;color:var(--navy2);font-variant-numeric:tabular-nums}
.kpi.k2{border-top-color:#1d4ed8}.kpi.k3{border-top-color:var(--navy2)}.kpi.k4{border-top-color:var(--navy)}
.kpi .v.neg{color:var(--bad)}
.dl{font-size:7.5pt;color:var(--mut)}.dl.ok{color:var(--ok)}.dl.bad{color:var(--bad)}
h2{font-size:11.5pt;margin:15px 0 7px;color:var(--navy2);font-weight:700}
.cols{display:grid;grid-template-columns:1.25fr 1fr;gap:16px}
.card{border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.brow{display:grid;grid-template-columns:34% 1fr 28%;gap:6px;align-items:center;margin:4px 0;font-size:8.6pt}
.bname{line-height:1.15}
.btrack{height:9px;background:var(--tint);border-radius:5px;overflow:hidden}
.bfill{height:100%;border-radius:5px}
.bval{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.bval i{color:var(--mut);font-style:normal;font-size:7.5pt}
table{width:100%;border-collapse:collapse;font-size:8.8pt}
th{font-size:7.3pt;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);text-align:left;padding:4px 6px;border-bottom:1px solid var(--line)}
td{padding:5px 6px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
td.r,th.r{text-align:right}
.tm{font-size:8.2pt}.tm td,.tm th{white-space:nowrap;padding:5px 4px}
.daily{display:flex;align-items:flex-end;gap:2px;height:62px;padding-top:4px}
.daily div{flex:1;background:var(--sky);border-radius:2px 2px 0 0;min-height:1px}
.daily div.mx{background:var(--navy2)}
.dnum{display:flex;gap:2px;margin-top:3px}
.dnum span{flex:1;text-align:center;font-size:6.2pt;color:var(--mut);font-variant-numeric:tabular-nums}
.dnum span.mx{color:var(--navy2);font-weight:700}
.foot{position:absolute;left:14mm;right:14mm;bottom:8mm;border-top:1px solid var(--line);padding-top:6px;display:flex;justify-content:space-between;font-size:8pt;color:var(--mut)}
.foot b{color:var(--navy2)}
.year{display:flex;align-items:flex-end;gap:7px;height:120px;padding:6px 4px 0;border-bottom:1px solid var(--line)}
.ycol{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%}
.ybar{width:100%;border-radius:3px 3px 0 0;background:var(--navy2)}
.ybar.neg{background:var(--bad)}
.yv{font-size:6.6pt;color:var(--mut);margin-bottom:2px;white-space:nowrap}
.ylab{display:flex;gap:7px;padding:3px 4px 0;font-size:7.4pt;color:var(--mut)}
.ylab div{flex:1;text-align:center}
.goal{height:12px;background:var(--tint);border-radius:6px;position:relative;overflow:hidden;margin-top:6px}
.goal .a{position:absolute;left:0;top:0;bottom:0;background:var(--navy2)}
ul.obs{margin:0;padding-left:16px;display:grid;gap:5px;font-size:9.4pt}
.note{font-size:7.8pt;color:var(--mut);margin-top:8px}
"""


def bars(items, total, color):
    mx = max((v for _, v in items), default=1) or 1
    out = []
    for name, v in items:
        out.append('<div class="brow"><div class="bname">%s</div><div class="btrack"><div class="bfill" style="width:%.1f%%;background:%s"></div></div><div class="bval">%s <i>%.0f%%</i></div></div>'
                   % (esc(name), v / mx * 100, color, money(v), v / total * 100 if total else 0))
    return "".join(out) or '<div class="dl">Sin gastos en este periodo</div>'


def delta(cur_v, prev_v, good_up, prev_label):
    if not prev_v:
        return '<span class="dl">sin dato previo</span>'
    d = (cur_v - prev_v) / abs(prev_v) * 100
    up = d >= 0
    return '<span class="dl %s">%s %.0f %% vs %s</span>' % ("ok" if up == good_up else "bad", "▲" if up else "▼", abs(d), prev_label)


def construir_html(c, link):
    year, month, pm, meta = c["year"], c["month"], c["pm"], c["meta"]
    mes, mes_l = MESES[month - 1], MESES[month - 1].lower()
    prev_m = MESES[pm - 1]
    ing, gas, ah, pct = c["ing"], c["gas"], c["ah"], c["pct"]
    cumple = pct is not None and pct >= meta
    neg = "neg" if ah < 0 else ""

    cats = sorted(c["cat"].items(), key=lambda x: -x[1])
    top, rest = cats[:6], cats[6:]
    if rest:
        top.append(("Otras categorías", sum(v for _, v in rest)))
    meths = sorted(c["meth"].items(), key=lambda x: -x[1])

    days, nd = c["days"], c["ndays"]
    daily = [days.get(d, 0.0) for d in range(1, nd + 1)]
    mxv = max(daily) or 1
    maxday = max(range(1, nd + 1), key=lambda d: days.get(d, 0.0)) if gas > 0 else 0
    daily_html = "".join('<div class="%s" style="height:%.1f%%"></div>' % ("mx" if i + 1 == maxday else "", v / mxv * 100) for i, v in enumerate(daily))
    dnum_html = "".join('<span class="%s">%d</span>' % ("mx" if d == maxday else "", d) for d in range(1, nd + 1))

    top5_html = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td class='r'>%s</td></tr>" % (
        r["date"][8:] + "/" + r["date"][5:7], esc(r["name"]), esc(r["category"]), money(r["pen"])) for r in c["top5"])

    names = sorted(set(c["cat"]) | set(c["prev_cat"]), key=lambda n: -max(c["cat"].get(n, 0), c["prev_cat"].get(n, 0)))[:5]

    def vcell(cu, pr):
        d = cu - pr
        return "<td class='r dl %s' style='font-size:8.8pt'>%s</td>" % (("bad" if d > 0 else "ok") if d else "", money(d, True) if d else "—")
    cmp_html = "".join("<tr><td>%s</td><td class='r'>%s</td><td class='r'>%s</td>%s</tr>" % (
        esc(n), money(c["prev_cat"].get(n, 0)), money(c["cat"].get(n, 0)), vcell(c["cat"].get(n, 0), c["prev_cat"].get(n, 0))) for n in names)

    obs = []
    if cats:
        obs.append("<b>%s</b> fue tu mayor gasto: %s (%.0f %% de lo gastado)." % (esc(cats[0][0]), money(cats[0][1]), cats[0][1] / gas * 100))
    if c["p_gas"] > 0:
        var = (gas - c["p_gas"]) / c["p_gas"] * 100
        obs.append("Gastaste <b>%.0f %% %s</b> que en %s (%s frente a %s)." % (abs(var), "más" if var > 0 else "menos", prev_m.lower(), money(gas), money(c["p_gas"])))
    if gas > 0:
        obs.append("Tu día de mayor gasto fue el <b>%d de %s</b>: %s." % (maxday, mes_l, money(days.get(maxday, 0))))
        obs.append("<b>%.0f %%</b> de tus gastos se pagó con tarjeta de crédito: cuida las fechas de cierre." % (c["credit"] / gas * 100))
        obs.append("Gasto promedio diario: <b>%s</b>." % money(gas / nd))
    if not obs:
        obs.append("No hay movimientos registrados en este periodo.")

    if cumple:
        goal_txt = "Meta cumplida: ahorraste <b>%.1f %%</b> de tus ingresos (la meta es %.0f %%)." % (pct, meta)
    elif pct is None:
        goal_txt = "No hubo ingresos este mes, por eso no se calcula el porcentaje de ahorro."
    else:
        goal_txt = "Ahorraste <b>%.1f %%</b> y la meta es %.0f %%: faltaron <b>%s</b> para alcanzarla." % (pct, meta, money(ing * meta / 100 - ah))
    avance = max(0.0, min(100.0, (pct or 0) / meta * 100))

    amax = max([abs(s["ah"]) for s in c["con"]] + [1])
    ycols, ylabs = [], []
    for s in c["serie"]:
        shown = s["has"] and s["m"] <= month
        h = abs(s["ah"]) / amax * 100 if shown else 0
        val = money(s["ah"]).replace("S/ ", "") if shown else ""
        ycols.append('<div class="ycol"><div class="yv">%s</div><div class="ybar %s" style="height:%.1f%%"></div></div>' % (val, "neg" if shown and s["ah"] < 0 else "", max(h, 0.6) if shown else 0))
        ylabs.append("<div>%s</div>" % MESES[s["m"] - 1][:3])

    fila_meses = "".join(
        "<tr><td>%s</td><td class='r'>%s</td><td class='r'>%s</td><td class='r'><b>%s</b></td><td class='r'>%s</td><td class='r dl %s' style='font-size:8.8pt'>%s</td></tr>" % (
            MESES[s["m"] - 1], money(s["ing"]), money(s["gas"]), money(s["ah"]),
            ("%.1f %%" % s["pct"]) if s["pct"] is not None else "—",
            "ok" if (s["pct"] or 0) >= meta else "bad", "Sí" if (s["pct"] or 0) >= meta else "No") for s in c["con"])

    ytd_pct = c["ytd_pct"]
    ytd_cumple = ytd_pct is not None and ytd_pct >= meta
    pct_s = ("%.1f %%" % pct) if pct is not None else "—"
    ytd_pct_s = ("%.1f %%" % ytd_pct) if ytd_pct is not None else "—"
    prom = c["ytd_ah"] / len(c["con"]) if c["con"] else 0
    prom_g = c["ytd_gas"] / len(c["con"]) if c["con"] else 0
    headline = ("Ahorraste <b>%s</b>" % money(ah) + (" (%.1f %% de tus ingresos)" % pct if pct is not None else "")) if ah >= 0 else ("Cerraste con un déficit de <b>%s</b>" % money(abs(ah)))

    return """<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Finanzas personales %(mes)s %(y)d</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>%(css)s</style></head><body>
<section class="page">
  <div class="band"><div class="eb">Mis Finanzas · Reporte mensual</div><h1>%(mes)s %(y)d</h1><div class="sub">%(headline)s</div></div>
  <div class="wrap">
    <div class="kpis">
      <div class="kpi"><div class="l">Ingresos</div><div class="v">%(ing)s</div>%(d_ing)s</div>
      <div class="kpi k2"><div class="l">Gastos</div><div class="v">%(gas)s</div>%(d_gas)s</div>
      <div class="kpi k3"><div class="l">Ahorros</div><div class="v %(neg)s">%(ah)s</div>%(d_ah)s</div>
      <div class="kpi k4"><div class="l">%% de ahorro</div><div class="v %(neg)s">%(pct)s</div><span class="dl %(cls_meta)s">meta %(meta)d %%: %(txt_meta)s</span></div>
    </div>
    <div class="cols">
      <div><h2>Gastos por categoría</h2><div class="card">%(cats)s</div></div>
      <div><h2>Cómo pagaste</h2><div class="card">%(meths)s</div></div>
    </div>
    <h2>Gasto día a día</h2>
    <div class="card"><div class="daily">%(daily)s</div><div class="dnum">%(dnum)s</div></div>
    <h2>Los 5 gastos más altos</h2>
    <div class="card" style="padding:4px 10px"><table><tr><th>Fecha</th><th>Detalle</th><th>Categoría</th><th class="r">Monto</th></tr>%(top5)s</table></div>
    <h2>Categorías frente a %(prev_l)s</h2>
    <div class="card" style="padding:4px 10px"><table><tr><th>Categoría</th><th class="r">%(prev_m)s</th><th class="r">%(mes)s</th><th class="r">Cambio</th></tr>%(cmp)s</table></div>
  </div>
  <div class="foot"><span>Mis Finanzas · %(mes)s %(y)d</span><span>Página 1 de 2</span></div>
</section>
<section class="page">
  <div class="band"><div class="eb">Mis Finanzas · Cómo vamos en el año</div><h1>Resumen %(y)d</h1><div class="sub">Acumulado a %(mes_l)s: ahorro de <b>%(ytd_ah)s</b> sobre ingresos de %(ytd_ing)s</div></div>
  <div class="wrap">
    <div class="kpis">
      <div class="kpi"><div class="l">Ingresos del año</div><div class="v">%(ytd_ing)s</div><span class="dl">%(nm)d meses con datos</span></div>
      <div class="kpi k2"><div class="l">Gastos del año</div><div class="v">%(ytd_gas)s</div><span class="dl">%(prom_g)s por mes</span></div>
      <div class="kpi k3"><div class="l">Ahorro acumulado</div><div class="v">%(ytd_ah)s</div><span class="dl">%(prom)s por mes</span></div>
      <div class="kpi k4"><div class="l">%% de ahorro del año</div><div class="v">%(ytd_pct_s)s</div><span class="dl %(cls_ytd)s">meta %(meta)d %%: %(txt_ytd)s</span></div>
    </div>
    <h2>Ahorro mes a mes</h2>
    <div class="card"><div class="year">%(ycols)s</div><div class="ylab">%(ylabs)s</div></div>
    <div class="cols" style="margin-top:2px;grid-template-columns:1.6fr 1fr">
      <div><h2>Detalle por mes</h2><div class="card" style="padding:4px 8px"><table class="tm"><tr><th>Mes</th><th class="r">Ingresos</th><th class="r">Gastos</th><th class="r">Ahorro</th><th class="r">%%</th><th class="r">Meta %(meta)d %%</th></tr>%(meses)s</table></div></div>
      <div><h2>Meta mensual de ahorro</h2><div class="card">
        <div style="font-size:9pt;display:flex;justify-content:space-between"><span>%(mes)s</span><b>%(pct_s)s de %(meta)d %%</b></div>
        <div class="goal"><div class="a" style="width:%(avance).1f%%"></div></div>
        <div style="font-size:8.4pt;margin-top:6px">%(goal_txt)s</div>
        <div style="font-size:8.4pt;margin-top:5px">Meses con meta cumplida: <b>%(meses_ok)d de %(nm)d</b></div></div></div>
    </div>
    <h2>Lo que destaca de %(mes_l)s</h2>
    <div class="card"><ul class="obs">%(obs)s</ul></div>
    <div class="note">Ahorros = ingresos − gastos. Cifras en soles (S/); los movimientos en dólares no se incluyen en este reporte.</div>
  </div>
  <div class="foot"><span>Ver el detalle completo e iniciar sesión: <b>%(link)s</b></span><span>Página 2 de 2</span></div>
</section></body></html>""" % dict(
        css=CSS, mes=mes, mes_l=mes_l, y=year, headline=headline, ing=money(ing), gas=money(gas), ah=money(ah), pct=pct_s, neg=neg,
        d_ing=delta(ing, c["p_ing"], True, prev_m[:3].lower()), d_gas=delta(gas, c["p_gas"], False, prev_m[:3].lower()), d_ah=delta(ah, c["p_ah"], True, prev_m[:3].lower()),
        cls_meta="ok" if cumple else "bad", meta=int(meta), txt_meta="cumplida" if cumple else ("sin ingresos" if pct is None else "faltaron %.1f pts" % (meta - pct)),
        cats=bars(top, gas, "var(--blue)"), meths=bars(meths, gas, "var(--navy2)"), daily=daily_html, dnum=dnum_html, top5=top5_html,
        prev_l=prev_m.lower(), prev_m=prev_m, cmp=cmp_html,
        ytd_ing=money(c["ytd_ing"]), ytd_gas=money(c["ytd_gas"]), ytd_ah=money(c["ytd_ah"]), nm=len(c["con"]), prom=money(prom), prom_g=money(prom_g),
        ytd_pct_s=ytd_pct_s, cls_ytd="ok" if ytd_cumple else "bad", txt_ytd="cumplida" if ytd_cumple else ("sin ingresos" if ytd_pct is None else "faltan %.1f pts" % (meta - ytd_pct)),
        ycols="".join(ycols), ylabs="".join(ylabs), meses=fila_meses, pct_s=pct_s, avance=avance, goal_txt=goal_txt, meses_ok=c["meses_ok"],
        obs="".join("<li>%s</li>" % o for o in obs), link=link)


# ----------------------------------------------------------------- PDF y correo
def buscar_navegador():
    cand = [os.environ.get("CHROME_BIN", ""), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
    for c in cand:
        if c and (shutil.which(c) or os.path.exists(c)):
            return shutil.which(c) or c
    sys.exit("No se encontró Chrome o Edge para generar el PDF.")


def html_a_pdf(html_path, pdf_path):
    exe = buscar_navegador()
    url = "file:///" + os.path.abspath(html_path).replace("\\", "/").lstrip("/")
    args = [exe, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer", "--virtual-time-budget=10000",
            "--print-to-pdf=" + os.path.abspath(pdf_path), url]
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) < 5000:
        sys.exit("No se pudo generar el PDF.")


def enviar_correo(pdf_path, nombre_pdf, c, destino, api_key, remitente, link, usuario):
    mes, y = MESES[c["month"] - 1], c["year"]
    asunto = "Envío de finanzas personales – %s %d" % (mes, y)
    usuario_txt = " con el usuario %s" % usuario if usuario else " con tu usuario"
    resumen = "Ingresos %s · Gastos %s · Ahorros %s%s" % (money(c["ing"]), money(c["gas"]), money(c["ah"]), (" (%.1f %%)" % c["pct"]) if c["pct"] is not None else "")
    texto = ("Hola,\n\nSe adjunta tu documento de finanzas personales de %s %d, con el análisis del mes y cómo vamos en el año.\n\n%s\n\n"
             "Para ver más detalle, ingresa a %s%s.\n\nMis Finanzas") % (mes, y, resumen, link, usuario_txt)
    cuerpo = ("<div style='font-family:Segoe UI,Arial,sans-serif;font-size:15px;color:#0e1a33;line-height:1.55'>"
              "<p>Hola,</p><p>Se adjunta tu documento de finanzas personales de <b>%s %d</b>, con el análisis del mes y cómo vamos en el año.</p>"
              "<p style='background:#eef3fc;border-radius:8px;padding:10px 14px'>%s</p>"
              "<p>Para ver más detalle, ingresa a <a href='%s'>%s</a>%s.</p><p style='color:#5a6885'>Mis Finanzas</p></div>") % (
        mes, y, esc(resumen), esc(link), esc(link), esc(usuario_txt))
    with open(pdf_path, "rb") as f:
        adj = base64.b64encode(f.read()).decode()
    payload = {"from": remitente, "to": [destino], "subject": asunto, "html": cuerpo, "text": texto,
               "attachments": [{"filename": nombre_pdf, "content": adj}]}
    req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            print("Correo enviado (HTTP %d)." % resp.status)
    except urllib.error.HTTPError as e:
        print("Resend respondió HTTP %d: %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", type=int)
    ap.add_argument("--mes", type=int)
    ap.add_argument("--csv", help="Usar un CSV exportado en lugar de Supabase (pruebas locales).")
    ap.add_argument("--salida", default=tempfile.gettempdir())
    ap.add_argument("--enviar", action="store_true")
    a = ap.parse_args()

    anio = a.anio or (int(os.environ["ANIO"]) if os.environ.get("ANIO", "").strip() else 0)
    mes = a.mes or (int(os.environ["MES"]) if os.environ.get("MES", "").strip() else 0)
    if not anio or not mes:
        hoy = dt.datetime.now(LIMA).date()
        prev = hoy.replace(day=1) - dt.timedelta(days=1)
        anio, mes = prev.year, prev.month
    if not 1 <= mes <= 12:
        sys.exit("Mes inválido.")

    meta = float(os.environ.get("META_AHORRO_PCT", "30"))
    link = os.environ.get("APP_URL", "https://geremic47.github.io/MisfinanzasPC/")
    if a.csv:
        rows = filas_desde_csv(a.csv)
    else:
        rows = filas_desde_supabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    c = calcular(rows, anio, mes, meta)
    print("Reporte %04d-%02d: %d movimientos del mes, %d en total." % (anio, mes, c["n"], len(rows)))

    os.makedirs(a.salida, exist_ok=True)
    nombre = "Finanzas_Personales_%04d-%02d.pdf" % (anio, mes)
    html_path, pdf_path = os.path.join(a.salida, "reporte.html"), os.path.join(a.salida, nombre)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(construir_html(c, link))
    html_a_pdf(html_path, pdf_path)
    print("PDF generado (%d KB)." % (os.path.getsize(pdf_path) // 1024))

    if a.enviar:
        enviar_correo(pdf_path, nombre, c, os.environ["REPORT_TO_EMAIL"], os.environ["RESEND_API_KEY"],
                      os.environ.get("REPORT_FROM", "Mis Finanzas <onboarding@resend.dev>"), link, os.environ.get("APP_USER_EMAIL", ""))


if __name__ == "__main__":
    main()
