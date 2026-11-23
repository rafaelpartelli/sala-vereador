#!/usr/bin/env python3
"""Robô da Sala do Vereador: lê a API aberta dos portais E&L (portaltp) dos municípios do ES
e grava um JSON por município em dados/mun/<ibge>.json. Só dados públicos agregados.
Sem dado inventado: recurso que não responde fica marcado como indisponível."""
import json, os, re, sys, time, unicodedata, urllib.request, urllib.parse, datetime, concurrent.futures as cf
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANO = int(os.environ.get("ANO") or datetime.date.today().year)
UA = {"User-Agent": "Mozilla/5.0 (Sala do Vereador; partelli.pro)"}

def slug(s):
    s = unicodedata.normalize("NFD", s); s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s.lower())

def get(host, metodo, **p):
    url = f"https://{host}/api/transparencia.asmx/json_{metodo}?" + urllib.parse.urlencode(p)
    for t in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                txt = r.read().decode("utf-8", "replace")
            m = re.search(r"<string[^>]*>([\s\S]*)</string>", txt)
            if not m: return None
            import html
            return json.loads(html.unescape(m.group(1)))
        except Exception as e:
            if t == 2: return None
            time.sleep(3 * (t + 1))

def num(x):
    try: return float(x or 0)
    except Exception: return 0.0

def limpo(s): return re.sub(r"\s+", " ", (s or "").strip())
def sem_codigo(s):  # "33903036000 - MATERIAL ..." -> "MATERIAL ..."
    return limpo(re.sub(r"^[\d\.]+\s*-\s*", "", s or ""))
def top(d, n=10): return sorted(d.items(), key=lambda kv: -kv[1][0] if isinstance(kv[1], list) else -kv[1])[:n]

def coletar(nome, ibge):
    host = f"{slug(nome)}-es.portaltp.com.br"
    out = {"municipio": nome, "ibge": ibge, "fonte": "Portal da Transparência (E&L), API aberta", "host": host,
           "ano": ANO, "gerado": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "disp": {}}
    # processos
    lic = get(host, "licitacoes", ano=ANO, mes=0, extra="False", situacao="")
    dis = get(host, "dispensas_inexigibilidades", ano=ANO, mes=0)
    ctr = get(host, "contratos", ano=ANO, mes="")
    ata = get(host, "atas", ano=ANO, mes="")
    out["disp"].update(lic=lic is not None, dispensas=dis is not None, contratos=ctr is not None, atas=ata is not None)
    if lic is None and ctr is None and ata is None and dis is None:
        out["disp"]["portal"] = False; return out
    out["disp"]["portal"] = True
    lic = lic or []; dis = dis or []; ctr = ctr or []; ata = ata or []
    out["T"] = {"lic": len(lic), "licVal": round(sum(num(r.get("valor_homologado")) for r in lic), 2),
                "disp": len(dis), "dispVal": round(sum(num(r.get("valor_homologado", r.get("valor"))) for r in dis), 2),
                "ctr": len(ctr), "ctrVal": round(sum(num(r.get("valor")) for r in ctr), 2),
                "atas": len(ata), "atasVal": round(sum(num(r.get("valor")) for r in ata), 2)}
    def proc(r, vkey):
        return [limpo(r.get("unidade_gestora"))[:40], limpo(r.get("modalidade")), limpo(r.get("licitacao") or r.get("dispensa") or r.get("numero")),
                limpo(r.get("objeto"))[:260], limpo(r.get("situacao")), num(r.get(vkey))]
    out["lic"] = [proc(r, "valor_homologado") for r in sorted(lic, key=lambda r: -num(r.get("valor_homologado")))]
    out["dis"] = [proc(r, "valor_homologado" if "valor_homologado" in r else "valor") for r in sorted(dis, key=lambda r: -num(r.get("valor_homologado", r.get("valor"))))]
    def cont(r): return [limpo(r.get("contrato")), (r.get("assinatura") or "")[:10], limpo(r.get("nome_favorecido"))[:70],
                         limpo(r.get("categoria")), limpo(r.get("objeto"))[:260], limpo(r.get("situacao")), num(r.get("valor"))]
    out["ctr"] = [cont(r) for r in sorted(ctr, key=lambda r: -num(r.get("valor")))]
    out["ata"] = [cont(r) for r in sorted(ata, key=lambda r: -num(r.get("valor")))]
    mod = {}
    for r in lic:
        k = limpo(r.get("modalidade")) or "Sem modalidade"; a = mod.setdefault(k, [0, 0.0]); a[0] += 1; a[1] += num(r.get("valor_homologado"))
    out["modalidade"] = [[k, v[0], round(v[1], 2)] for k, v in sorted(mod.items(), key=lambda kv: -kv[1][1])]
    # despesa liquidada mês a mês
    mes_liq, func, elem, fav, grp = {}, {}, {}, {}, {}
    ultimo = 0; pf = [0.0, 0]
    for m in range(1, 13):
        L = get(host, "liquidacoes", ano=ANO, mes=m)
        if not L: continue
        ultimo = m
        for r in L:
            v = num(r.get("valor")); mes_liq[m] = mes_liq.get(m, 0) + v
            f = sem_codigo(r.get("funcao")) or "Sem função"; func[f] = func.get(f, 0) + v
            e = sem_codigo(r.get("elemento_despesa")) or "Sem elemento"; a = elem.setdefault(e, [0.0, 0]); a[0] += v; a[1] += 1
            g = sem_codigo(r.get("grupo_despesa")) or "Sem grupo"; grp[g] = grp.get(g, 0) + v
            doc = r.get("documento_favorecido") or ""
            if "*" in doc or re.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}", doc):  # pessoa física: não identificar
                pf[0] += v; pf[1] += 1; continue
            n = limpo(r.get("nome_favorecido")) or "Sem nome"; a = fav.setdefault(n, [0.0, 0]); a[0] += v; a[1] += 1
    if ultimo:
        out["despesa"] = {"ultimoMes": ultimo, "total": round(sum(mes_liq.values()), 2),
            "mensal": [[m, round(mes_liq.get(m, 0), 2)] for m in range(1, ultimo + 1)],
            "funcao": [[k, round(v, 2)] for k, v in sorted(func.items(), key=lambda kv: -kv[1])[:10]],
            "grupo": [[k, round(v, 2)] for k, v in sorted(grp.items(), key=lambda kv: -kv[1])],
            "elemento": [[k, round(v[0], 2), v[1]] for k, v in sorted(elem.items(), key=lambda kv: -kv[1][0])[:10]],
            "favorecido": [[k, round(v[0], 2), v[1]] for k, v in sorted(fav.items(), key=lambda kv: -kv[1][0])[:10]],
            "pessoaFisica": [round(pf[0], 2), pf[1]]}
    out["disp"]["despesa"] = bool(ultimo)
    # receita realizada
    mes_rec, org = {}, {}; ur = 0
    for m in range(1, 13):
        R = get(host, "execucao_receitas", ano=ANO, mes=m)
        if not R: continue
        ur = m
        for r in R:
            v = num(r.get("valor_realizado")); mes_rec[m] = mes_rec.get(m, 0) + v
            k = limpo(r.get("conta_origem")) or "Sem origem"; org[k] = org.get(k, 0) + v
    if ur:
        out["receita"] = {"ultimoMes": ur, "total": round(sum(mes_rec.values()), 2),
            "mensal": [[m, round(mes_rec.get(m, 0), 2)] for m in range(1, ur + 1)],
            "origem": [[k, round(v, 2)] for k, v in sorted(org.items(), key=lambda kv: -kv[1])[:8]]}
    out["disp"]["receita"] = bool(ur)
    # folha (agregada, sem nomes)
    for m in range(12, 0, -1):
        S = get(host, "servidores", ano=ANO, mes=m)
        if S: break
    else:
        S = None; m = 0
    if S:
        reg, sec, car = {}, {}, {}
        tot = 0.0
        for r in S:
            b = num(r.get("valor_rem07")); tot += b
            k = limpo(r.get("regime")) or "Sem regime"; a = reg.setdefault(k, [0, 0.0]); a[0] += 1; a[1] += b
            s = sem_codigo(r.get("secretaria")) or "Sem lotação"; a = sec.setdefault(s, [0, 0.0]); a[0] += 1; a[1] += b
            c = limpo(r.get("cargo")) or "Sem cargo"; a = car.setdefault(c, [0, 0.0]); a[0] += 1; a[1] += b
        out["pessoal"] = {"mes": m, "vinculos": len(S), "folhaBruta": round(tot, 2),
            "regime": [[k, v[0], round(v[1], 2)] for k, v in sorted(reg.items(), key=lambda kv: -kv[1][1])],
            "secretaria": [[k, v[0], round(v[1], 2)] for k, v in sorted(sec.items(), key=lambda kv: -kv[1][1])[:12]],
            "cargoFolha": [[k, v[0], round(v[1], 2)] for k, v in sorted(car.items(), key=lambda kv: -kv[1][1])[:10]],
            "cargoQtd": [[k, v[0], round(v[1], 2)] for k, v in sorted(car.items(), key=lambda kv: -kv[1][0])[:10]]}
    out["disp"]["pessoal"] = bool(S)
    return out

def main():
    mapa = json.load(open(os.path.join(RAIZ, "dados", "mapa.json"), encoding="utf-8"))
    alvo = [x.strip() for x in (sys.argv[1] if len(sys.argv) > 1 else "").split(",") if x.strip()]
    linhas = [(r[1], r[0]) for r in mapa["rows"] if not alvo or slug(r[1]) in alvo]
    os.makedirs(os.path.join(RAIZ, "dados", "mun"), exist_ok=True)
    indice = {}
    try: indice = json.load(open(os.path.join(RAIZ, "dados", "mun", "_indice.json"), encoding="utf-8"))
    except Exception: pass
    def uma(x):
        nome, ibge = x
        try: return nome, ibge, coletar(nome, ibge)
        except Exception as e: return nome, ibge, {"municipio": nome, "ibge": ibge, "erro": str(e)[:200], "disp": {"portal": False}}
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for nome, ibge, d in ex.map(uma, linhas):
            ok = d.get("disp", {}).get("portal")
            caminho = os.path.join(RAIZ, "dados", "mun", f"{ibge}.json")
            if ok:  # só grava se o portal respondeu; senão mantém o último arquivo bom
                json.dump(d, open(caminho, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            indice[str(ibge)] = {"nome": nome, "portal": bool(ok) or indice.get(str(ibge), {}).get("portal", False),
                "host": d.get("host"), "gerado": d["gerado"] if ok else indice.get(str(ibge), {}).get("gerado"),
                "disp": d.get("disp"), "pessoalMes": (d.get("pessoal") or {}).get("mes"), "despesaMes": (d.get("despesa") or {}).get("ultimoMes")}
            print(nome, "ok" if ok else "SEM DADOS", flush=True)
    json.dump({"atualizado": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "ano": ANO, "municipios": indice},
              open(os.path.join(RAIZ, "dados", "mun", "_indice.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

if __name__ == "__main__": main()
