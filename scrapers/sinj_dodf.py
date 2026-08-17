"""
Agora BsB - Coletor DODF v5
Usa a API interna do portal dodf.df.gov.br descoberta via DevTools.

Endpoint: POST https://www.dodf.df.gov.br/dodf/jornal/diario
Sem autenticacao, sem x-client-id.

IDs de demandante confirmados em 17/08/2026:
  Saude:    782 + filhos (789,792,802,804,829,834,835,837,1171,1193,
                          1379,2212,4248,5142,5162,5447,5528,5585,5676)
  Educacao: 697 + filhos (701,716,722,1134,1189)

Roda via GitHub Actions diariamente.
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from comum import agora_utc, criar_sessao, registrar_coleta, setup_logging, hash_texto

from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
setup_logging()
log = logging.getLogger("agora.dodf")

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()

DODF_API = "https://www.dodf.df.gov.br/dodf/jornal/diario"

# IDs confirmados via DevTools em 17/08/2026
IDS_SAUDE = [
    782, 789, 792, 802, 804, 829, 834, 835, 837,
    1171, 1193, 1379, 2212, 4248, 5142, 5162,
    5447, 5528, 5585, 5676
]
IDS_EDUCACAO = [697, 701, 716, 722, 1134, 1189]

PAUSA = 1.5


def timestamp_hoje() -> int:
    """Retorna o timestamp Unix do inicio do dia atual em Brasilia."""
    agora = datetime.now(timezone.utc)
    # Ajusta para meia-noite no horario de Brasilia (UTC-3)
    from datetime import timedelta
    brasilia = agora - timedelta(hours=3)
    meia_noite = brasilia.replace(hour=0, minute=0, second=0, microsecond=0)
    return int((meia_noite + timedelta(hours=3)).timestamp())


def buscar_pagina(sessao, timestamp: int, ids: list[int], pagina: int = 1) -> dict:
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


def coletar_tema(sessao, timestamp: int, ids: list[int], tema: str) -> list[dict]:
    """Coleta todas as paginas de um tema."""
    materias = []
    pagina = 1

    while True:
        dados = buscar_pagina(sessao, timestamp, ids, pagina)
        if not dados or dados.get("type") != "success":
            log.warning(f"Resposta invalida tema={tema} pagina={pagina}: {str(dados)[:200]}")
            break

        lst = dados.get("lstMaterias", [])
        total_pags = dados.get("totalPaginas", 1)
        total_mat = dados.get("totalMaterias", 0)

        log.info(f"Tema={tema} pagina={pagina}/{total_pags} materias={len(lst)} total={total_mat}")

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
                "data_publicacao": datetime.now().strftime("%Y-%m-%d"),
                "link": (
                    f"https://www.dodf.df.gov.br/dodf/materia/visualizar"
                    f"?co_data={cod}&p={m.get('slug','')}"
                ),
                "temas": [tema],
                "fonte": "DODF",
                "coletado_em": agora_utc(),
            })

        if pagina >= total_pags:
            break
        pagina += 1
        time.sleep(PAUSA)

    return materias


def deduplicar(todas: list[dict]) -> list[dict]:
    """Mescla temas de materias com mesmo numero."""
    por_id: dict[str, dict] = {}
    for m in todas:
        k = m["numero"]
        if k in por_id:
            for t in m["temas"]:
                if t not in por_id[k]["temas"]:
                    por_id[k]["temas"].append(t)
        else:
            por_id[k] = m
    return list(por_id.values())


def salvar(supabase, publicacoes: list[dict]) -> int:
    if not publicacoes:
        return 0
    salvos = 0
    for i in range(0, len(publicacoes), 50):
        bloco = publicacoes[i:i + 50]
        try:
            supabase.table("publicacoes_dodf").upsert(
                bloco, on_conflict="numero,fonte"
            ).execute()
            salvos += len(bloco)
        except Exception as e:
            log.error(f"Erro ao salvar lote {i//50+1}: {e}")
    return salvos


def main():
    # Nao roda em fins de semana — DODF nao publica
    hoje = datetime.now()
    if hoje.weekday() >= 5:
        log.info(f"Fim de semana ({hoje.strftime('%A')}) — DODF nao publica.")
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    sessao = criar_sessao(total_retries=3, backoff=2.0)
    sessao.headers.update({
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.dodf.df.gov.br/",
        "Origin": "https://www.dodf.df.gov.br",
    })

    ts = timestamp_hoje()
    log.info(f"Coletando DODF — {hoje.strftime('%d/%m/%Y')} (timestamp={ts})")

    # Coleta saude e educacao
    saude = coletar_tema(sessao, ts, IDS_SAUDE, "saude")
    log.info(f"Saude: {len(saude)} materias")
    time.sleep(2)

    educacao = coletar_tema(sessao, ts, IDS_EDUCACAO, "educacao")
    log.info(f"Educacao: {len(educacao)} materias")

    todas = deduplicar(saude + educacao)
    log.info(f"Total unico: {len(todas)}")

    salvos = salvar(supabase, todas)
    status = "ok" if salvos > 0 else "vazio"
    registrar_coleta(supabase, "DODF", status, salvos)
    log.info(f"Coleta DODF finalizada: {salvos} registros salvos")


if __name__ == "__main__":
    main()
