"""
Agora BsB - Coletor Transparencia GDF
Pausado - portal bloqueia IPs externos.
Usar coletar_emendas_local.py na maquina local.
"""
import os, sys, logging
sys.path.insert(0, os.path.dirname(__file__))
from comum import registrar_coleta, setup_logging
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()
setup_logging()
log = logging.getLogger("agora.transparencia")
SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()
def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    log.info("Coletor Transparencia pausado — usar coletar_emendas_local.py na maquina local")
    registrar_coleta(supabase, "TRANSPARENCIA", "vazio", 0, "pausado")
if __name__ == "__main__":
    main()
