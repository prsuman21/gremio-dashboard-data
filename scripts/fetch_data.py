import json
import re
import datetime as dt
from typing import Optional, List, Dict

import requests
from bs4 import BeautifulSoup
from unidecode import unidecode

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GremioDashboardBot/1.0; +https://github.com/)",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

TEAM_TOKEN = "gremio"

SOURCES = {
    "ufmg_rebaixamento": "https://www.mat.ufmg.br/futebol/rebaixamento_seriea/",
    "ufmg_libertadores": "https://www.mat.ufmg.br/futebol/classificacao-para-libertadores_seriea/",
    "ufmg_sulamericana": "https://www.mat.ufmg.br/futebol/classificacao-para-sulamericana_seriea/",
    "ufmg_campeao": "https://www.mat.ufmg.br/futebol/campeao_seriea/",
    "ge_agenda": "https://ge.globo.com/rs/futebol/times/gremio/agenda-de-jogos-do-gremio/",
    "espn_calendario": "https://www.espn.com.br/futebol/time/calendario/_/id/6273/gremio",
    "cbf_tabela": "https://www.cbf.com.br/futebol-brasileiro/tabelas/campeonato-brasileiro/serie-a/2025?doc=Tabela+Detalhada",
    "ge_lesionados_exemplo": "https://ge.globo.com/rs/futebol/times/gremio/noticia/2025/09/30/gremio-chega-a-13-jogadores-fora-por-problemas-fisicos-meio-time-so-volta-em-2026.ghtml",
}

def fetch(url: str) -> Optional[str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None

def percent_from_row_text(text: str) -> Optional[float]:
    import re
    m = re.search(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*%", text)
    if not m:
        m2 = re.search(r"(\d{1,3}(?:[.,]\d{1,2})?)\b", text)
        if m2:
            try:
                val = float(m2.group(1).replace(",", "."))
                if val <= 1:
                    return round(val * 100, 2)
                return round(val, 2)
            except Exception:
                return None
        return None
    try:
        return round(float(m.group(1).replace(",", ".")), 2)
    except Exception:
        return None

def find_team_row(table: BeautifulSoup, team_key: str = TEAM_TOKEN) -> Optional[BeautifulSoup]:
    rows = table.find_all("tr")
    for tr in rows:
        txt = unidecode(" ".join(tr.stripped_strings)).lower()
        if "gremio" in txt:
            return tr
    return None

def parse_ufmg_single_probability(url: str) -> Optional[float]:
    html = fetch(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    for tab in tables:
        row = find_team_row(tab)
        if row:
            txt = unidecode(" ".join(row.stripped_strings)).lower()
            return percent_from_row_text(txt)
    body_txt = unidecode(" ".join(soup.stripped_strings)).lower()
    return percent_from_row_text(body_txt)

def parse_cbf_table() -> Dict:
    html = fetch(SOURCES["cbf_tabela"])
    if not html:
        return {}
    soup = BeautifulSoup(html, "lxml")
    for tab in soup.find_all("table"):
        tr = find_team_row(tab)
        if tr:
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            def to_int(s):
                try:
                    import re
                    return int(re.sub(r"[^\d]", "", s))
                except Exception:
                    return None
            nums = [to_int(x) for x in cells]
            pontos = None
            posicao = None
            cand = [n for n in nums if isinstance(n, int)]
            if cand:
                pontos = cand[-1]
            if nums and nums[0] and nums[0] <= 20:
                posicao = nums[0]
            return {
                "posicao": posicao,
                "pontos": pontos,
                "j": None, "v": None, "e": None, "d": None,
                "gp": None, "gc": None, "sg": None, "aproveitamento": None
            }
    return {}

def parse_ge_espn_games() -> (List[Dict], List[Dict]):
    proximos, ultimos = [], []
    espn_html = fetch(SOURCES["espn_calendario"])
    if espn_html:
        espn_soup = BeautifulSoup(espn_html, "lxml")
        for li in espn_soup.select("li, article, section"):
            txt = " ".join(li.stripped_strings)
            low = unidecode(txt).lower()
            if "gremio" in low:
                import re
                mdate = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", low)
                has_score = re.search(r"\b(\d+)\s*x\s*(\d+)\b", low)
                item = {
                    "data_hora": mdate.group(1) if mdate else None,
                    "adversario": None,
                    "competicao": None,
                    "mando": None,
                    "placar": None
                }
                if has_score:
                    item["placar"] = has_score.group(0)
                    ultimos.append(item)
                else:
                    proximos.append(item)
    ge_html = fetch(SOURCES["ge_agenda"])
    if ge_html:
        ge_soup = BeautifulSoup(ge_html, "lxml")
        for card in ge_soup.select("a, article, li"):
            txt = " ".join(card.stripped_strings)
            low = unidecode(txt).lower()
            if "gremio" in low:
                pass
    def clean_list(lst, is_last=False):
        clean = []
        for it in lst:
            if any(it.values()):
                clean.append(it)
        return clean[:10] if not is_last else clean[:10]
    return clean_list(proximos), clean_list(ultimos, is_last=True)

def parse_ge_lesionados() -> List[Dict]:
    html = fetch(SOURCES["ge_lesionados_exemplo"])
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    items = []
    for p in soup.find_all(["p", "li"]):
        txt = " ".join(p.stripped_strings)
        low = unidecode(txt).lower()
        if "les" in low or "desfal" in low or "retorno" in low:
            items.append({"nome": txt, "status": None, "previsao": None})
    return items[:20]

def main():
    prob = {
        "rebaixamento": parse_ufmg_single_probability(SOURCES["ufmg_rebaixamento"]),
        "libertadores": parse_ufmg_single_probability(SOURCES["ufmg_libertadores"]),
        "sulamericana": parse_ufmg_single_probability(SOURCES["ufmg_sulamericana"]),
        "campeao": parse_ufmg_single_probability(SOURCES["ufmg_campeao"]),
    }

    tabela = parse_cbf_table()
    proximos, ultimos = parse_ge_espn_games()
    lesionados = parse_ge_lesionados()
    suspensos = []

    data = {
        "proximos_jogos": proximos,
        "ultimos_jogos": ultimos,
        "tabela": {
            "posicao": tabela.get("posicao"),
            "pontos": tabela.get("pontos"),
            "j": tabela.get("j"),
            "v": tabela.get("v"),
            "e": tabela.get("e"),
            "d": tabela.get("d"),
            "gp": tabela.get("gp"),
            "gc": tabela.get("gc"),
            "sg": tabela.get("sg"),
            "aproveitamento": tabela.get("aproveitamento"),
        },
        "suspensos": suspensos,
        "lesionados": lesionados,
        "probabilidades": prob
    }

    out = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "sources": SOURCES,
        "data": data
    }

    import os
    os.makedirs("public", exist_ok=True)
    with open("public/latest.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("Gerado public/latest.json com sucesso.")

if __name__ == "__main__":
    main()
