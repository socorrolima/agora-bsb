"""
Ágora BsB — utilitários compartilhados entre os coletores.
"""

import hashlib
import logging
import os
import re
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("agora")


def agora_utc() -> str:
    """Timestamp UTC ISO — substitui datetime.utcnow() (deprecado)."""
    return datetime.now(timezone.utc).isoformat()


def criar_sessao(total_retries: int = 4, backoff: float = 2.0) -> requests.Session:
    """
    Sessão HTTP com retry automático e backoff exponencial.
    Retenta em 429/5xx — essencial para portais governamentais instáveis.
    """
    sessao = requests.Session()
    retry = Retry(
        total=total_retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    sessao.mount("https://", adapter)
    sessao.mount("http://", adapter)
    sessao.headers.update({
        "User-Agent": "AgoraBsB/2.0 (civic-tech; monitoramento legislativo DF; contato via GitHub)",
        "Accept": "application/json",
    })
    return sessao


def parse_valor_br(texto: str) -> float | None:
    """
    Converte valores em formato brasileiro para float.
    'R$ 1.234.567,89' -> 1234567.89
    '1.234,56'        -> 1234.56
    ''                -> None
    """
    if not texto:
        return None
    limpo = re.sub(r"[^\d,.\-]", "", str(texto))
    if not limpo:
        return None
    # formato BR: ponto = milhar, vírgula = decimal
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return None


def hash_texto(texto: str) -> str:
    """Hash curto e determinístico para chaves únicas de textos longos."""
    return hashlib.md5(texto.strip().lower().encode("utf-8")).hexdigest()[:16]


def registrar_coleta(supabase, fonte: str, status: str, registros: int, detalhe: str = "") -> None:
    """
    Grava resultado da execução na tabela coleta_log.
    Permite monitorar pelo painel se algum coletor parou de funcionar.
    """
    try:
        supabase.table("coleta_log").insert({
            "fonte": fonte,
            "status": status,          # 'ok' | 'erro' | 'vazio'
            "registros": registros,
            "detalhe": detalhe[:500],
            "executado_em": agora_utc(),
        }).execute()
    except Exception as e:
        log.error(f"Falha ao registrar log de coleta: {e}")


# Filtro negativo do classificador DODF — evita falsos positivos comuns
EXCLUSOES_CLASSIFICADOR = [
    "saúde financeira",
    "saúde fiscal",
    "atestado de saúde ocupacional",
    "escola de samba",
    "escola de condutores",
    "auto escola",
    "autoescola",
]


def classificar_com_exclusoes(texto: str, tema_sugerido: str) -> list[str]:
    """
    Confirma o tema sugerido pelo termo de busca,
    aplicando o filtro negativo de exclusões.
    """
    texto_lower = texto.lower()
    if any(exc in texto_lower for exc in EXCLUSOES_CLASSIFICADOR):
        return []
    return [tema_sugerido]


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
