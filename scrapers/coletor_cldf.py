import os
import sys
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

def main():
    log.info("VERSAO NOVA FUNCIONANDO")
    resp = requests.get(
        "https://ple.cl.df.gov.br/pleservico/api/public/tema",
        timeout=30
    )
    dados = resp.json()
    for t in dados:
        log.info(f"value={t.get('value')} label={t.get('label')}")

if __name__ == "__main__":
    main()
