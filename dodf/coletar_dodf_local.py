"""
Agora BsB - Coletor DODF Local v2
Usa a API real do portal dodf.df.gov.br descoberta via DevTools.

Endpoint: POST https://www.dodf.df.gov.br/dodf/jornal/diario
Sem autenticacao — mesma requisicao que o site faz no navegador.

IDs confirmados em 17/08/2026:
  Saude:    782 + subsecretarias
  Educacao: 697 + subsecretarias

Rodar na maquina local (Windows) em dias uteis.
Agendar via Task Scheduler: todo dia util as 8h.
"""

import os
import sys
import time
import logging
import requests
from datetime import datetime, timezone, timedelta

# ── Configuracao ──────────────────────────────────────────────
SUPABASE_URL = "https://vlvoyxgwcxmenbsqhsdf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZsdm95eGd3Y3htZW5ic3Foc2RmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTMzMDA1MiwiZXhwIjoyMTAwOTA2MDUyfQ.itiZX_pRMakM0_NzNgR72GqrMmlAYUuw2bILg4G_9pA"

DODF_API = "https://www.dodf.df.gov.br/dodf/jornal/diario"

# IDs confirmados via DevTools em 17/08/2026
IDS_SAUDE = [
    782, 789, 792, 802, 804, 829, 834, 835, 837,
    1171, 1193, 1379, 2212, 4248, 5142, 5162,
    5447, 5528, 5585, 5676
]
IDS_EDUCACAO = [697, 701, 716, 722, 1134, 1189]

PAUSA = 1.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("dodf_coleta.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("dodf")


def timestamp_hoje() -> int:
    """Timestamp Unix da meia-noite de hoje no horario de Brasilia."""
    agora = datetime.now(timezone.utc)
    brasilia = agora - timedelta(hours=3)
    meia_noite = brasilia.replace(hour=0, minute=0, second=0, microsecond=0)
    return int((meia_noite + timedelta(hours=3)).timestamp())

def criar_sessao() -> requests.Session:
    s = requests.Session()
    s.verify = False  # adicionar esta linha
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.dodf.df.gov.br/",
        "Origin": "https://www.dodf.df.gov.br",
        "Accept": "application/json, text/plain, */*",
    })
    return s


def buscar_pagina(sessao, timestamp: int, ids: list, pagina: int = 1) -> dict:
    """POST para a API do DODF com filtro de demandantes."""
    ids_str = ",".join(str(i) for i in ids)
    payload = {
        "data": str(timestamp),
        "pagina": str(pagina),
        "tpJornal": "",
        "letra": "",
        "tpDemandante": ids_str,
        "tpMateria": "",
        "tpOrdenacao": "",
        "tpSecao": "",
    }
    try:
        resp = sessao.post(DODF_API, data=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"Erro pagina {pagina}: {e}")
        return {}


def coletar_tema(sessao, timestamp: int, ids: list, tema: str) -> list:
    """Coleta todas as paginas de um tema."""
    materias = []
    pagina = 1

    while True:
        dados = buscar_pagina(sessao, timestamp, ids, pagina)
        if not dados or dados.get("type") != "success":
            log.warning(f"Resposta invalida tema={tema} pagina={pagina}")
            break

        lst = dados.get("lstMaterias", [])
        total_pags = dados.get("totalPaginas", 1)
        total_mat = dados.get("totalMaterias", 0)

        log.info(f"Tema={tema} pagina={pagina}/{total_pags} materias={len(lst)} total={total_mat}")

        hoje_str = datetime.now().strftime("%Y-%m-%d")

        for m in lst:
            cod = str(m.get("coMateria", ""))
            if not cod:
                continue

            poder = m.get("poder", [])
            orgao = " > ".join(poder) if poder else ""
            texto = m.get("texto", "")
            titulo = m.get("titulo", "")

            materias.append({
                "numero": cod,
                "tipo": m.get("tipo", "Publicacao"),
                "descricao": f"{titulo}\n{texto}"[:800],
                "secretaria": orgao[:200],
                "data_publicacao": hoje_str,
                "link": (
                    f"https://www.dodf.df.gov.br/dodf/materia/visualizar"
                    f"?co_data={cod}&p={m.get('slug','')}"
                ),
                "temas": [tema],
                "fonte": "DODF",
                "coletado_em": datetime.utcnow().isoformat(),
            })

        if pagina >= total_pags:
            break
        pagina += 1
        time.sleep(PAUSA)

    return materias


def deduplicar(todas: list) -> list:
    por_id = {}
    for m in todas:
        k = m["numero"]
        if k in por_id:
            for t in m["temas"]:
                if t not in por_id[k]["temas"]:
                    por_id[k]["temas"].append(t)
        else:
            por_id[k] = m
    return list(por_id.values())


def salvar(publicacoes: list) -> int:
    if not publicacoes:
        return 0

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    salvos = 0
    for i in range(0, len(publicacoes), 50):
        bloco = publicacoes[i:i + 50]
        try:
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/publicacoes_dodf?on_conflict=numero,fonte",
                json=bloco,
                headers=headers,
                timeout=30,
            )
            if r.status_code in (200, 201):
                salvos += len(bloco)
                log.info(f"Lote {i//50+1} salvo: {len(bloco)} registros")
            else:
                log.error(f"Erro {r.status_code}: {r.text[:200]}")
        except Exception as e:
            log.error(f"Erro ao salvar: {e}")

    return salvos


def main():
    hoje = datetime.now()

    if hoje.weekday() >= 5:
        log.info(f"Fim de semana — DODF nao publica.")
        return

    log.info(f"Iniciando coleta DODF — {hoje.strftime('%d/%m/%Y')}")

    sessao = criar_sessao()
    ts = timestamp_hoje()
    log.info(f"Timestamp: {ts}")

    saude = coletar_tema(sessao, ts, IDS_SAUDE, "saude")
    log.info(f"Saude: {len(saude)} materias")
    time.sleep(2)

    educacao = coletar_tema(sessao, ts, IDS_EDUCACAO, "educacao")
    log.info(f"Educacao: {len(educacao)} materias")

    todas = deduplicar(saude + educacao)
    log.info(f"Total unico: {len(todas)}")

    salvos = salvar(todas)
    log.info(f"Coleta finalizada: {salvos} registros salvos no Supabase")


if __name__ == "__main__":
    main()