import requests

SUPABASE_URL = "https://vlvoyxgwcxmenbsqhsdf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZsdm95eGd3Y3htZW5ic3Foc2RmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTMzMDA1MiwiZXhwIjoyMTAwOTA2MDUyfQ.itiZX_pRMakM0_NzNgR72GqrMmlAYUuw2bILg4G_9pA"

r = requests.post(
    f"{SUPABASE_URL}/rest/v1/publicacoes_dodf?on_conflict=numero,fonte",
    json=[{
        "numero": "teste123",
        "tipo": "Teste",
        "descricao": "teste de conexao",
        "secretaria": "",
        "data_publicacao": "2026-08-17",
        "link": "",
        "temas": ["saude"],
        "fonte": "DODF",
        "coletado_em": "2026-08-17T00:00:00"
    }],
    headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    },
    timeout=30
)
print(f"Status: {r.status_code}")
print(f"Resposta: {r.text[:300]}")