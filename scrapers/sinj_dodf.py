"""
Agora BsB - Coletor DODF v3

O portal dodf.df.gov.br bloqueia conexoes de IPs externos (GitHub Actions).
Alternativa: SINJ-DF (sinj.df.gov.br) — sistema de normas juridicas do DF
que indexa toda legislacao publicada no DODF, com API REST publica e
acessivel de qualquer IP.

API SINJ-DF:
  Base: https://sinj.df.gov.br/sinj/api
  /norma?tipo=Portaria&orgao=SES&pagina=1
  /norma?tipo=Decreto&palavraChave=educacao&pagina=1

Vantagem: dados estruturados, sem bloqueio geografico, sem autenticacao.
Limitacao: indexa normas (portarias, decretos, resolucoes) — nao atos
           administrativos menores como editais e avisos.
"""

import os
import sys
import time
import logging
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, os.path.dirname(__file__))
from comum import agora_utc, criar_sessao, registrar_coleta, setup_logging, hash_texto

from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
setup_logging()
log = logging.getLogger("agora.dodf")

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()

SINJ_BASE = "https://sinj.df.gov.br/sinj/api"

# Orgaos e palavras-chave por tema
CONSULTAS = {
    "saude": [
        {"orgao": "Secretaria de Estado de Saude do Distrito Federal"},
        {"orgao": "SES-DF"},
        {"palavraChave": "atencao primaria"},
        {"palavraChave": "saude mental"},
        {"palavraChave": "hospital"},
    ],
    "educacao": [
        {"orgao": "Secretaria de Estado de Educacao do Distrito Federal"},
        {"orgao": "SEEDF"},
        {"palavraChave": "merenda escolar"},
        {"palavraChave": "rede publica ensino"},
        {"palavraChave": "creche"},
    ],
}

TIPOS = ["Portaria", "Decreto", "Resolucao", "Instrucao Normativa"]
PAUSA = 1.0


def buscar_sinj(sessao, params: dict, pagina: int = 1) -> list[dict]:
    """Consulta a API do SINJ-DF."""
    url = f"{SINJ_BASE}/norma"
    p = {**params, "pagina": pagina, "quantidade": 20}
    try:
        resp = sessao.get(url, params=p, timeout=30, verify=False)
        if resp.status_code != 200:
            log.warning(f"SINJ status {resp.status_code} params={params}")
            return []
        dados = resp.json()
        # SINJ pode retornar lista ou {content: [...]}
        if isinstance(dados, list):
            return dados
        for chave in ("content", "items", "normas", "data", "results"):
            if chave in dados:
                return dados[chave]
        log.warning(f"DIAGNOSTICO SINJ — estrutura desconhecida: {str(dados)[:300]}")
        return []
    except Exception as e:
        log.error(f"Erro SINJ params={params}: {e}")
        return []


def normalizar(item: dict, tema: str) -> dict | None:
    """Converte resposta do SINJ para o schema do banco."""
    numero = (
        item.get("numero") or item.get("id")
        or item.get("identificacao") or ""
    )
    tipo = (
        item.get("tipo") or item.get("tipoNorma")
        or item.get("especie") or "Publicacao"
    )
    descricao = (
        item.get("ementa") or item.get("descricao")
        or item.get("texto") or item.get("titulo") or ""
    )
    orgao = (
        item.get("orgao") or item.get("orgaoEmissor")
        or item.get("secretaria") or ""
    )
    data = (
        item.get("data") or item.get("dataPublicacao")
        or item.get("dataAssinatura") or None
    )
    link = (
        item.get("link") or item.get("url")
        or item.get("urlDodf") or ""
    )

    if not descricao and not numero:
        return None

    chave = str(numero) if numero else hash_texto(str(descricao))

    return {
        "numero": chave[:100],
        "tipo": str(tipo)[:60],
        "descricao": str(descricao)[:800],
        "secretaria": str(orgao)[:200],
        "data_publicacao": data,
        "link": str(link),
        "temas": [tema],
        "fonte": "DODF",
        "coletado_em": agora_utc(),
    }


def coletar(sessao) -> list[dict]:
    """Coleta publicacoes do SINJ-DF dos ultimos 30 dias."""
    unicos: dict[str, dict] = {}

    for tema, consultas in CONSULTAS.items():
        for consulta in consultas:
            items = buscar_sinj(sessao, consulta)
            log.info(f"SINJ {consulta} ({tema}): {len(items)} resultados")

            for item in items:
                pub = normalizar(item, tema)
                if not pub:
                    continue
                chave = pub["numero"]
                if chave in unicos:
                    if tema not in unicos[chave]["temas"]:
                        unicos[chave]["temas"].append(tema)
                else:
                    unicos[chave] = pub

            time.sleep(PAUSA)

    log.info(f"Total unico DODF/SINJ: {len(unicos)}")
    return list(unicos.values())


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
            log.error(f"Erro ao salvar: {e}")
    return salvos


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    sessao = criar_sessao()
    # SINJ nao exige Accept especifico mas JSON e o padrao
    sessao.headers["Accept"] = "application/json"

    try:
        publicacoes = coletar(sessao)

        if not publicacoes:
            log.warning(
                "Nenhum resultado do SINJ-DF. "
                "Verificar se https://sinj.df.gov.br/sinj/api/norma responde. "
                "Alternativa: usar Jusbrasil RSS ou download mensal do DODF."
            )
            registrar_coleta(supabase, "DODF", "vazio", 0,
                             "SINJ sem resultados — verificar endpoint")
            return

        salvos = salvar(supabase, publicacoes)
        registrar_coleta(supabase, "DODF", "ok" if salvos else "vazio", salvos)
        log.info(f"Coleta DODF finalizada: {salvos} registros")

    except Exception as e:
        registrar_coleta(supabase, "DODF", "erro", 0, str(e))
        raise


if __name__ == "__main__":
    main()
