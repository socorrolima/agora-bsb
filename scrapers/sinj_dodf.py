"""
Agora BsB - Coletor DODF v4
Usa o feed RSS publico do Jusbrasil que indexa o DODF.
"""

import os, sys, logging
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from comum import agora_utc, criar_sessao, registrar_coleta, setup_logging, hash_texto, classificar_com_exclusoes
from supabase import create_client
from dotenv import load_dotenv
import unicodedata, urllib3

load_dotenv()
setup_logging()
log = logging.getLogger("agora.dodf")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()
RSS_URL = "https://www.jusbrasil.com.br/diarios/DODF/rss"
TERMOS_SAUDE = ["saude", "ses-df", "hospital", "ubs", "saude mental", "medicamento", "vacina"]
TERMOS_EDUCACAO = ["educacao", "seedf", "escola", "merenda", "professor", "creche", "ensino"]

def norm(s):
    return unicodedata.normalize("NFD", str(s)).encode("ascii","ignore").decode().lower()

def classificar(titulo, descricao):
    texto = norm(titulo) + " " + norm(descricao)
    temas = []
    if any(t in texto for t in TERMOS_SAUDE):
        r = classificar_com_exclusoes(texto, "saude")
        if r: temas.extend(r)
    if any(t in texto for t in TERMOS_EDUCACAO):
        r = classificar_com_exclusoes(texto, "educacao")
        if r: temas.extend(r)
    return list(set(temas))

def coletar_rss(sessao):
    log.info(f"Buscando RSS: {RSS_URL}")
    try:
        resp = sessao.get(RSS_URL, timeout=30, verify=False)
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Erro RSS: {e}")
        return []
    try:
        root = ET.fromstring(resp.content)
    except Exception as e:
        log.error(f"Erro XML: {e}")
        return []
    items = root.findall(".//item")
    log.info(f"Itens no RSS: {len(items)}")
    publicacoes = {}
    for item in items:
        titulo = item.findtext("title") or ""
        descricao = item.findtext("description") or ""
        link = item.findtext("link") or ""
        guid = item.findtext("guid") or hash_texto(titulo + link)
        temas = classificar(titulo, descricao)
        if not temas:
            continue
        chave = hash_texto(guid)
        publicacoes[chave] = {
            "numero": chave,
            "tipo": "Publicacao DODF",
            "descricao": f"{titulo} — {descricao}"[:800],
            "secretaria": "",
            "data_publicacao": None,
            "link": link,
            "temas": temas,
            "fonte": "DODF",
            "coletado_em": agora_utc(),
        }
    log.info(f"Publicacoes relevantes: {len(publicacoes)}")
    return list(publicacoes.values())

def salvar(supabase, publicacoes):
    if not publicacoes: return 0
    salvos = 0
    for i in range(0, len(publicacoes), 50):
        bloco = publicacoes[i:i+50]
        try:
            supabase.table("publicacoes_dodf").upsert(bloco, on_conflict="numero,fonte").execute()
            salvos += len(bloco)
        except Exception as e:
            log.error(f"Erro salvar: {e}")
    return salvos

def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    sessao = criar_sessao(total_retries=2, backoff=1.0)
    try:
        publicacoes = coletar_rss(sessao)
        salvos = salvar(supabase, publicacoes)
        status = "ok" if salvos > 0 else "vazio"
        registrar_coleta(supabase, "DODF", status, salvos)
        log.info(f"Coleta DODF finalizada: {salvos} registros")
    except Exception as e:
        registrar_coleta(supabase, "DODF", "erro", 0, str(e))
        raise

if __name__ == "__main__":
    main()