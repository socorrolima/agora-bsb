"""
Ágora BsB — Coletor Transparência GDF v2

Melhorias sobre a v1:
- Valores monetários convertidos para numeric (permite somar/agregar no painel)
- Chave única das emendas usa hash da descrição (não texto longo)
- Retry automático e log de coleta
- AVISO HONESTO: os endpoints do portal de transparência do DF não são
  documentados. Este coletor tem estrutura defensiva e entra em modo
  diagnóstico se a estrutura mudar. Validar no primeiro run real.
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(__file__))
from comum import (
    agora_utc, criar_sessao, registrar_coleta,
    setup_logging, parse_valor_br, hash_texto,
)

from bs4 import BeautifulSoup
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
setup_logging()
log = logging.getLogger("agora.transparencia")

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()

BASE = "https://www.transparencia.df.gov.br"
ANO = datetime.now().year

SECRETARIAS = ["SES", "SEEDF"]
TEMAS_EMENDA = ["saúde", "educação", "ses", "seedf", "escola", "hospital", "ubs", "creche"]


def coletar_orcamento_html(sessao, sigla: str) -> list[dict]:
    """Scraping da página de despesas com parsing numérico."""
    url = f"{BASE}/despesas"
    try:
        resp = sessao.get(url, params={"ano": ANO, "orgao": sigla}, timeout=45)
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Falha ao acessar despesas de {sigla}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    rows = soup.select("table tbody tr")

    if not rows:
        log.warning(
            f"DIAGNÓSTICO — nenhuma linha de tabela encontrada para {sigla}. "
            f"Título da página: '{soup.title.get_text(strip=True) if soup.title else '?'}'. "
            "A estrutura HTML pode ter mudado — inspecionar manualmente."
        )
        return []

    registros = []
    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cols) < 5:
            continue
        registros.append({
            "secretaria": sigla,
            "acao": cols[0][:300],
            "acao_hash": hash_texto(cols[0]),
            "dotacao": parse_valor_br(cols[1]),
            "empenhado": parse_valor_br(cols[2]),
            "liquidado": parse_valor_br(cols[3]),
            "pago": parse_valor_br(cols[4]),
            "ano": ANO,
            "coletado_em": agora_utc(),
        })

    log.info(f"{sigla}: {len(registros)} linhas de orçamento")
    return registros


def coletar_emendas_html(sessao) -> list[dict]:
    url = f"{BASE}/emendas"
    try:
        resp = sessao.get(url, params={"ano": ANO}, timeout=45)
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Falha ao acessar emendas: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    rows = soup.select("table tbody tr")

    if not rows:
        log.warning("DIAGNÓSTICO — página de emendas sem tabela. Estrutura mudou?")
        return []

    emendas = []
    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cols) < 6:
            continue

        descricao = cols[2]
        if not any(t in descricao.lower() for t in TEMAS_EMENDA):
            continue

        emendas.append({
            "parlamentar": cols[0][:150],
            "partido": cols[1][:40],
            "descricao": descricao[:500],
            "descricao_hash": hash_texto(descricao),
            "valor": parse_valor_br(cols[3]),
            "secretaria_destino": cols[4][:200],
            "status": cols[5][:100],
            "ano": ANO,
            "coletado_em": agora_utc(),
        })

    log.info(f"Emendas relevantes: {len(emendas)}")
    return emendas


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    sessao = criar_sessao()
    sessao.headers["Accept"] = "text/html,application/json"

    total = 0
    erros = []

    try:
        for sigla in SECRETARIAS:
            registros = coletar_orcamento_html(sessao, sigla)
            if registros:
                try:
                    supabase.table("orcamento_execucao").upsert(
                        registros, on_conflict="secretaria,acao_hash,ano"
                    ).execute()
                    total += len(registros)
                except Exception as e:
                    erros.append(f"orcamento/{sigla}: {e}")

        emendas = coletar_emendas_html(sessao)
        if emendas:
            try:
                supabase.table("emendas_parlamentares").upsert(
                    emendas, on_conflict="parlamentar,descricao_hash,ano"
                ).execute()
                total += len(emendas)
            except Exception as e:
                erros.append(f"emendas: {e}")

        if erros:
            registrar_coleta(supabase, "TRANSPARENCIA", "erro", total, "; ".join(erros))
        else:
            registrar_coleta(supabase, "TRANSPARENCIA", "ok" if total else "vazio", total)

        log.info(f"Coleta Transparência finalizada: {total} registros")

    except Exception as e:
        registrar_coleta(supabase, "TRANSPARENCIA", "erro", total, str(e))
        raise


if __name__ == "__main__":
    main()
