"""
Agora BsB - Coletor DODF
Temporariamente desativado: portais do GDF bloqueiam IPs externos.
Registra 'vazio' sem erro para nao travar o workflow.
Proxima etapa: scraping via proxy ou coleta manual semanal.
"""
import os, sys, logging
sys.path.insert(0, os.path.dirname(__file__))
from comum import registrar_coleta, setup_logging
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
setup_logging()
log = logging.getLogger("agora.dodf")

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()

def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    log.info("Coletor DODF pausado — portais GDF bloqueiam IPs externos")
    log.info("Proxima etapa: definir fonte alternativa acessivel")
    registrar_coleta(supabase, "DODF", "vazio", 0, "pausado temporariamente")

if __name__ == "__main__":
    main()