"""
Ágora BsB — Coletor CLDF v2
Usa a API PÚBLICA OFICIAL do Processo Legislativo Eletrônico (PLE).

Base: https://ple.cl.df.gov.br/pleservico/api/public
Documentação: https://dados.cl.df.gov.br/sv/dataset/proposicoes

Vantagens sobre o scraping HTML da v1:
- Dados estruturados em JSON (sem parsing frágil de HTML)
- Classificação temática OFICIAL da CLDF (sem falsos positivos de keyword)
- Autoria, tramitação e situação incluídas
- Sem autenticação

A API pode evoluir sem aviso — por isso o modo diagnóstico
loga a estrutura da resposta quando algo muda.
"""

import os
import sys
import time
import logging

sys.path.insert(0, os.path.dirname(__file__))
from comum import agora_utc, criar_sessao, registrar_coleta, setup_logging

from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
setup_logging()
log = logging.getLogger("agora.cldf")

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()

API_BASE = "https://ple.cl.df.gov.br/pleservico/api/public"

# Nomes de temas oficiais da CLDF que interessam ao projeto.
# Comparação é case-insensitive por substring — cobre variações
# como "Educação", "Educação e Cultura" etc.
import unicodedata

TEMAS_ALVO = ["saude", "educacao"]


def normalizar_str(s: str) -> str:
    """Remove acentos e coloca em minúsculas para comparação robusta."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()

PAGE_SIZE = 50
MAX_PAGINAS = 200          # trava de segurança
PAUSA_ENTRE_PAGINAS = 1.5  # segundos — respeito ao servidor


def buscar_temas_oficiais(sessao) -> dict[int, str]:
    """
    GET /tema — retorna o catálogo oficial de temas da CLDF.
    Devolve {codigo: nome} apenas dos temas que interessam.
    """
    resp = sessao.get(f"{API_BASE}/tema", timeout=30)
    resp.raise_for_status()
    temas = resp.json()

    if not isinstance(temas, list):
        temas = temas.get("content", temas.get("items", []))

    alvo = {}
    for t in temas:
        # API retorna {value, label} — com fallback para {id, nome} e {codigo, descricao}
        nome = (t.get("label") or t.get("nome") or t.get("descricao") or "").strip()
        codigo = t.get("value") or t.get("id") or t.get("codigo")
        if codigo is None or not nome:
            continue
        if any(alvo_nome in normalizar_str(nome) for alvo_nome in TEMAS_ALVO):
            alvo[codigo] = nome

    log.info(f"Catálogo completo de temas: {temas}")
    log.info(f"Temas oficiais encontrados: {alvo}")
    if not alvo:
        log.warning(
            "Nenhum tema alvo encontrado no catálogo — "
            f"estrutura da resposta pode ter mudado. Amostra: {str(temas)[:400]}"
        )
    return alvo


def normalizar_tema_local(nome_tema_oficial: str) -> str:
    """Mapeia o nome oficial da CLDF para as categorias internas do painel."""
    nome = normalizar_str(nome_tema_oficial)
    if "saude" in nome:
        return "saude"
    if "educacao" in nome:
        return "educacao"
    return "outro"


def buscar_proposicoes_por_tema(sessao, codigo_tema: int, nome_tema: str, ano: int) -> list[dict]:
    """
    POST /proposicao/filter — busca paginada filtrando por tema e ano.
    """
    todas = []
    pagina = 0

    while pagina < MAX_PAGINAS:
        payload = {
            "tema": str(codigo_tema),
            "ano": str(ano),
        }
        params = {
            "page": pagina,
            "size": PAGE_SIZE,
            "sort": "dataLeitura,DESC",
        }

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
            log.error(f"Erro tema={nome_tema} ano={ano} página={pagina}: {e}")
            break

        # A API Spring costuma devolver {content: [...], last: bool}
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

    log.info(f"Tema '{nome_tema}' ano {ano}: {len(todas)} proposições")
    return todas


def normalizar_proposicao(p: dict, nome_tema: str) -> dict | None:
    """Converte o objeto da API para o schema do banco."""
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

    chave = f"{tipo} {numero}/{ano}" if numero else f"PLE-{prop_id}"

    return {
        "numero": chave.strip(),
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


def deduplicar_e_mesclar_temas(proposicoes: list[dict]) -> list[dict]:
    """
    Uma proposição pode aparecer em mais de um tema (saúde E educação).
    Mescla os temas em vez de duplicar o registro.
    """
    por_chave: dict[str, dict] = {}
    for p in proposicoes:
        chave = p["numero"]
        if chave in por_chave:
            existente = por_chave[chave]
            for t in p["temas"]:
                if t not in existente["temas"]:
                    existente["temas"].append(t)
        else:
            por_chave[chave] = p
    return list(por_chave.values())


def salvar(supabase, proposicoes: list[dict]) -> int:
    if not proposicoes:
        return 0
    salvos = 0
    lote = 50
    for i in range(0, len(proposicoes), lote):
        bloco = proposicoes[i:i + lote]
        try:
            supabase.table("proposicoes").upsert(
                bloco, on_conflict="numero,fonte"
            ).execute()
            salvos += len(bloco)
        except Exception as e:
            log.error(f"Erro no lote {i // lote + 1}: {e}")
    return salvos


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    sessao = criar_sessao()

    try:
        temas = buscar_temas_oficiais(sessao)
        if not temas:
            registrar_coleta(supabase, "CLDF", "erro", 0,
                             "Catálogo de temas vazio — verificar API")
            sys.exit(1)

        from datetime import datetime
        ano_atual = datetime.now().year
        anos = [ano_atual, ano_atual - 1]

        todas = []
        for codigo, nome in temas.items():
            for ano in anos:
                todas.extend(buscar_proposicoes_por_tema(sessao, codigo, nome, ano))

        unicas = deduplicar_e_mesclar_temas(todas)
        salvos = salvar(supabase, unicas)

        status = "ok" if salvos > 0 else "vazio"
        registrar_coleta(supabase, "CLDF", status, salvos)
        log.info(f"Coleta CLDF finalizada: {salvos} registros salvos")

    except Exception as e:
        registrar_coleta(supabase, "CLDF", "erro", 0, str(e))
        raise


if __name__ == "__main__":
    main()
