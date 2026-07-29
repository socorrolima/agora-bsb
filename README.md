# Ágora BsB v2 — Monitoramento Legislativo do DF

## O que mudou da v1 → v2

| Mudança | Motivo |
|---|---|
| CLDF via **API oficial do PLE** (JSON) | v1 raspava HTML com seletores não verificados |
| Temas **oficiais da CLDF** | v1 classificava por keyword (falsos positivos) |
| Classificador DODF com **filtro negativo** | "saúde financeira" ≠ saúde |
| Valores em `numeric` | v1 salvava "R$ 1.234,56" como texto — não somava |
| Chaves únicas com **hash MD5** | v1 usava texto longo como unique (índice ruim) |
| **Retry automático** com backoff | portais gov são instáveis |
| Tabela **coleta_log** | saber quando um coletor quebrou |
| **Issue automática** no GitHub em falha | ninguém precisa vigiar os logs |
| **15 testes** rodando antes de cada coleta | regressão detectada antes de tocar o banco |
| Modo **diagnóstico** | quando o site muda, o log mostra a estrutura nova |

## Fontes

| Fonte | Método | Confiabilidade |
|---|---|---|
| CLDF (`ple.cl.df.gov.br/pleservico/api/public`) | API oficial JSON | Alta — validar 1º run |
| DODF (`dodf.df.gov.br`) | Endpoint interno do buscador | Média — endpoint não documentado |
| Transparência GDF | Scraping HTML | Baixa — validar e ajustar seletores |

## Estrutura

```
scrapers/
  comum.py                  ← sessão HTTP, parser BR, classificador, log
  coletor_cldf.py           ← API oficial PLE
  coletor_dodf.py           ← buscador DODF + diagnóstico
  coletor_transparencia.py  ← orçamento e emendas
tests/test_coletores.py     ← 15 testes (pytest)
docs/schema_supabase_v2.sql ← schema completo + migração v1→v2
.github/workflows/          ← coleta diária + semanal + alertas
```

## Setup

Ver `docs/configuracao.md` da v1 — passos idênticos, mas use o
`schema_supabase_v2.sql`. Depois do 1º run, verifique a tabela
`coleta_log` no Supabase: status `ok` = funcionando.

## Avisos honestos

1. A API do PLE "pode evoluir sem aviso prévio" (aviso oficial da CLDF).
   O modo diagnóstico existe por isso.
2. Os coletores DODF e Transparência **precisam de validação no 1º run
   real** — os endpoints internos não são documentados. Se falharem,
   a issue automática + o log diagnóstico mostram o que ajustar.
3. Emendas parlamentares no DF têm transparência historicamente
   incompleta — pode ser necessário complementar com o SIGGO/TCDF.
