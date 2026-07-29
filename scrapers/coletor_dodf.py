"""
Ágora BsB — Coletor DODF v2

O DODF não tem API documentada oficialmente. O site dodf.df.gov.br
usa endpoints internos JSON que o frontend de busca consome.
Este coletor:

1. Tenta o endpoint interno de busca do site (descoberto via inspeção)
2. Em caso de mudança na estrutura, entra em MODO DIAGNÓSTICO:
   loga a resposta bruta para facilitar o conserto
3. Classificação por keywords COM filtro negativo (reduz falsos positivos)

Alternativa estruturada: SINJ-DF (sinj.df.gov.br) indexa toda a
legislação publicada no DODF — considerar como fonte complementar.
"""

import os
import sys
import logging
import time

sys.path.insert(0, os.path.dirname(__file__))
from comum import (
    agora_utc, criar_sessao, registrar_coleta,
    setup_logging, hash_texto, classificar_com_exclusoes,
)

from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
setup_logging()
log = logging.getLogger("agora.dodf")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

DODF_BASE = "https://dodf.df.gov.br"
# Endpoints candidatos do buscador interno — o coletor testa em ordem.
ENDPOINTS_BUSCA = [
    f"{DODF_BASE}/dodfsearchengine/busca",
    f"{DODF_BASE}/index/pesquisar",
    f"{DODF_BASE}/pesquisar",
]

TERMOS = {
    "saude": [
        "Secretaria de Estado de Saúde",
        "atenção primária",
        "saúde mental",
        "medicamentos",
        "unidade básica de saúde",
    ],
    "educacao": [
        "Secretaria de Estado de Educação",
        "merenda escolar",
        "rede pública de ensino",
        "creche",
        "alfabetização",
    ],
}



def buscar_termo(sessao, endpoint: str, termo: str, data_ini: str, data_fim: str) -> tuple[list, bool]:
    """
    Tenta buscar um termo num endpoint.
    Retorna (resultados, endpoint_funciona).
    """
    params = {
        "q": termo,
        "texto": termo,
        "dataIni": data_ini,
        "dataFim": data_fim,
        "pagina": 1,
    }
    try:
        resp = sessao.get(endpoint, params=params, timeout=30)
        if resp.status_code != 200:
            return [], False

        ctype = resp.headers.get("content-type", "")
        if "json" not in ctype:
            return [], False

        dados = resp.json()
        for chave in ("results", "items", "content", "publicacoes", "data"):
            if isinstance(dados, dict) and chave in dados:
                return dados[chave], True
        if isinstance(dados, list):
            return dados, True

        # Estrutura desconhecida — modo diagnóstico
        log.warning(f"DIAGNÓSTICO — estrutura desconhecida em {endpoint}: {str(dados)[:400]}")
        return [], True

    except Exception as e:
        log.debug(f"Endpoint {endpoint} falhou: {e}")
        return [], False


def descobrir_endpoint(sessao) -> str | None:
    """Testa os endpoints candidatos e retorna o primeiro funcional."""
    ontem = datetime.now() - timedelta(days=1)
    hoje = datetime.now()
    for ep in ENDPOINTS_BUSCA:
        _, funciona = buscar_termo(
            sessao, ep, "saúde",
            ontem.strftime("%d/%m/%Y"),
            hoje.strftime("%d/%m/%Y"),
        )
        if funciona:
            log.info(f"Endpoint funcional: {ep}")
            return ep
    return None


def normalizar(item: dict, tema: str) -> dict | None:
    texto = str(
        item.get("texto") or item.get("descricao")
        or item.get("titulo") or item.get("ementa") or ""
    )
    if not texto:
        return None

    temas = classificar_com_exclusoes(texto, tema)
    if not temas:
        return None

    numero = str(
        item.get("numero") or item.get("id")
        or item.get("edicao") or hash_texto(texto)
    )

    return {
        "numero": numero,
        "tipo": str(item.get("tipo") or item.get("tipoMateria") or "Publicação")[:60],
        "descricao": texto[:800],
        "secretaria": str(item.get("orgao") or item.get("secretaria") or "")[:200],
        "data_publicacao": item.get("data") or item.get("dataPublicacao"),
        "link": str(item.get("urlPdf") or item.get("url") or item.get("link") or ""),
        "temas": temas,
        "fonte": "DODF",
        "coletado_em": agora_utc(),
    }


def coletar(sessao, endpoint: str, dias: int = 7) -> list[dict]:
    hoje = datetime.now()
    inicio = hoje - timedelta(days=dias)
    data_ini = inicio.strftime("%d/%m/%Y")
    data_fim = hoje.strftime("%d/%m/%Y")

    unicos: dict[str, dict] = {}

    for tema, termos in TERMOS.items():
        for termo in termos:
            items, _ = buscar_termo(sessao, endpoint, termo, data_ini, data_fim)
            log.info(f"'{termo}' → {len(items)} resultados")

            for item in items:
                pub = normalizar(item, tema)
                if not pub:
                    continue
                chave = pub["numero"]
                if chave in unicos:
                    for t in pub["temas"]:
                        if t not in unicos[chave]["temas"]:
                            unicos[chave]["temas"].append(t)
                else:
                    unicos[chave] = pub

            time.sleep(1)

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
            log.error(f"Erro ao salvar lote: {e}")
    return salvos


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    sessao = criar_sessao()

    try:
        endpoint = descobrir_endpoint(sessao)
        if not endpoint:
            msg = ("Nenhum endpoint de busca do DODF respondeu com JSON. "
                   "O site pode ter mudado — inspecionar manualmente com DevTools "
                   "(aba Network) em dodf.df.gov.br e atualizar ENDPOINTS_BUSCA.")
            log.error(msg)
            registrar_coleta(supabase, "DODF", "erro", 0, msg)
            sys.exit(1)

        publicacoes = coletar(sessao, endpoint, dias=7)
        salvos = salvar(supabase, publicacoes)

        registrar_coleta(supabase, "DODF", "ok" if salvos else "vazio", salvos)
        log.info(f"Coleta DODF finalizada: {salvos} registros")

    except SystemExit:
        raise
    except Exception as e:
        registrar_coleta(supabase, "DODF", "erro", 0, str(e))
        raise


if __name__ == "__main__":
    main()
