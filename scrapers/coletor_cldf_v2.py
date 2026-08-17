"""
Agora BsB - Coletor CLDF v2
API oficial do PLE: https://ple.cl.df.gov.br/pleservico/api/public

Temas confirmados em 29/07/2026:
  value=15 label='Educacao'
  value=24 label='Saude'
"""

import os
import sys
import time
import logging
import unicodedata

sys.path.insert(0, os.path.dirname(__file__))
from comum import agora_utc, criar_sessao, registrar_coleta, setup_logging

from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
setup_logging()
log = logging.getLogger("agora.cldf")

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()

API_BASE = "https://ple.cl.df.gov.br/pleservico/api/public"

# Codigos confirmados pela API da CLDF
TEMAS_FIXOS = {
    15: "Educacao",
    24: "Saude",
}

PAGE_SIZE = 50
MAX_PAGINAS = 200
PAUSA_ENTRE_PAGINAS = 1.5


def normalizar_str(s):
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def normalizar_tema_local(nome_tema):
    nome = normalizar_str(nome_tema)
    if "saude" in nome:
        return "saude"
    if "educac" in nome:
        return "educacao"
    return "outro"


def buscar_proposicoes_por_tema(sessao, codigo_tema, nome_tema, ano):
    todas = []
    pagina = 0

    while pagina < MAX_PAGINAS:
        payload = {"tema": str(codigo_tema), "ano": str(ano)}
        params = {"page": pagina, "size": PAGE_SIZE, "sort": "dataLeitura,DESC"}

        try:
            resp = sessao.post(
                f"{API_BASE}/proposicao/filter",
                json=payload,
                params=params,
                timeout=45,
            )
            resp.raise_for_status()
            dados = resp.json()
        except Exception as e:
            log.error(f"Erro tema={nome_tema} ano={ano} pagina={pagina}: {e}")
            break

        items = dados.get("content", dados if isinstance(dados, list) else [])
        if not items:
            break

        for p in items:
            prop = normalizar_proposicao(p, nome_tema)
            if prop:
                todas.append(prop)

        ultima = dados.get("last", len(items) < PAGE_SIZE)
        if ultima:
            break

        pagina += 1
        time.sleep(PAUSA_ENTRE_PAGINAS)

    log.info(f"Tema '{nome_tema}' ano {ano}: {len(todas)} proposicoes")
    return todas


def normalizar_proposicao(p, nome_tema):
    prop_id = p.get("id")
    numero = p.get("numero") or p.get("numeroProposicao")
    tipo = p.get("tipoProposicao") or p.get("tipo") or ""
    if isinstance(tipo, dict):
        tipo = tipo.get("nome", tipo.get("descricao", ""))
    if not (prop_id or numero):
        return None

    ementa = p.get("ementa") or p.get("texto") or ""
    ano = p.get("ano")

    autores = p.get("autores") or p.get("autoria") or []
    if isinstance(autores, list):
        nomes_autores = ", ".join(
            a.get("nome", str(a)) if isinstance(a, dict) else str(a)
            for a in autores
        )
    else:
        nomes_autores = str(autores)

    situacao = p.get("situacao") or p.get("status") or ""
    if isinstance(situacao, dict):
        situacao = situacao.get("nome", situacao.get("descricao", ""))

    chave = f"{tipo} {numero}/{ano}".strip() if numero else f"PLE-{prop_id}"

    return {
        "numero": chave,
        "ple_id": prop_id,
        "tipo": str(tipo)[:80],
        "ementa": str(ementa)[:800],
        "autor": nomes_autores[:300],
        "temas": [normalizar_tema_local(nome_tema)],
        "tema_oficial": nome_tema,
        "status": str(situacao)[:120],
        "ano": ano,
        "link": f"https://ple.cl.df.gov.br/#/publico/proposicao/{prop_id}" if prop_id else None,
        "fonte": "CLDF",
        "coletado_em": agora_utc(),
    }


def deduplicar(proposicoes):
    por_chave = {}
    for p in proposicoes:
        chave = p["numero"]
        if chave in por_chave:
            for t in p["temas"]:
                if t not in por_chave[chave]["temas"]:
                    por_chave[chave]["temas"].append(t)
        else:
            por_chave[chave] = p
    return list(por_chave.values())


def salvar(supabase, proposicoes):
    if not proposicoes:
        return 0
    salvos = 0
    for i in range(0, len(proposicoes), 50):
        bloco = proposicoes[i:i + 50]
        try:
            supabase.table("proposicoes").upsert(
                bloco, on_conflict="numero,fonte"
            ).execute()
            salvos += len(bloco)
        except Exception as e:
            log.error(f"Erro ao salvar lote: {e}")
    return salvos


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    sessao = criar_sessao()

    try:
        log.info(f"Iniciando coleta CLDF com temas: {TEMAS_FIXOS}")
        ano_atual = datetime.now().year
        anos = [ano_atual, ano_atual - 1]

        todas = []
        for codigo, nome in TEMAS_FIXOS.items():
            for ano in anos:
                todas.extend(buscar_proposicoes_por_tema(sessao, codigo, nome, ano))

        unicas = deduplicar(todas)
        salvos = salvar(supabase, unicas)

        status = "ok" if salvos > 0 else "vazio"
        registrar_coleta(supabase, "CLDF", status, salvos)
        log.info(f"Coleta CLDF finalizada: {salvos} registros salvos")

    except Exception as e:
        registrar_coleta(supabase, "CLDF", "erro", 0, str(e))
        raise


if __name__ == "__main__":
    main()
