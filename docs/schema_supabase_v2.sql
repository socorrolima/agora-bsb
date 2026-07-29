-- =====================================================
-- Ágora BsB — Schema v2 (Supabase)
-- Mudanças da v1:
--   • valores monetários em numeric (agregáveis)
--   • chaves únicas com hash (não texto longo)
--   • tabela coleta_log para monitoramento
--   • campos ple_id, tema_oficial (API oficial da CLDF)
-- Se já rodou o schema v1: rode a MIGRAÇÃO no final.
-- =====================================================

create table if not exists proposicoes (
  id            bigserial primary key,
  numero        text not null,               -- "PL 123/2026"
  ple_id        bigint,                      -- id na API do PLE
  tipo          text,
  ementa        text,
  autor         text,
  temas         text[] default '{}',
  tema_oficial  text,                        -- nome do tema na CLDF
  status        text,
  ano           int,
  link          text,
  fonte         text not null default 'CLDF',
  coletado_em   timestamptz default now(),
  unique (numero, fonte)
);

create table if not exists publicacoes_dodf (
  id              bigserial primary key,
  numero          text not null,
  tipo            text,
  descricao       text,
  secretaria      text,
  data_publicacao date,
  link            text,
  temas           text[] default '{}',
  fonte           text not null default 'DODF',
  coletado_em     timestamptz default now(),
  unique (numero, fonte)
);

create table if not exists orcamento_execucao (
  id            bigserial primary key,
  secretaria    text not null,
  acao          text,
  acao_hash     text not null,               -- hash md5 da ação
  dotacao       numeric(16,2),
  empenhado     numeric(16,2),
  liquidado     numeric(16,2),
  pago          numeric(16,2),
  ano           int not null,
  coletado_em   timestamptz default now(),
  unique (secretaria, acao_hash, ano)
);

create table if not exists emendas_parlamentares (
  id                 bigserial primary key,
  parlamentar        text not null,
  partido            text,
  descricao          text,
  descricao_hash     text not null,
  valor              numeric(16,2),
  secretaria_destino text,
  status             text,
  ano                int not null,
  coletado_em        timestamptz default now(),
  unique (parlamentar, descricao_hash, ano)
);

-- Monitoramento das coletas: cada run grava uma linha.
-- O painel pode alertar se a última coleta 'ok' for antiga.
create table if not exists coleta_log (
  id           bigserial primary key,
  fonte        text not null,     -- CLDF | DODF | TRANSPARENCIA
  status       text not null,     -- ok | erro | vazio
  registros    int default 0,
  detalhe      text,
  executado_em timestamptz default now()
);

-- Índices
create index if not exists idx_prop_temas   on proposicoes using gin (temas);
create index if not exists idx_prop_autor   on proposicoes (autor);
create index if not exists idx_prop_ano     on proposicoes (ano desc);
create index if not exists idx_dodf_temas   on publicacoes_dodf using gin (temas);
create index if not exists idx_dodf_data    on publicacoes_dodf (data_publicacao desc);
create index if not exists idx_emendas_parl on emendas_parlamentares (parlamentar);
create index if not exists idx_log_fonte    on coleta_log (fonte, executado_em desc);

-- RLS: leitura pública, escrita só pela service key
alter table proposicoes           enable row level security;
alter table publicacoes_dodf      enable row level security;
alter table orcamento_execucao    enable row level security;
alter table emendas_parlamentares enable row level security;
alter table coleta_log            enable row level security;

create policy "pub_proposicoes" on proposicoes           for select using (true);
create policy "pub_dodf"        on publicacoes_dodf      for select using (true);
create policy "pub_orcamento"   on orcamento_execucao    for select using (true);
create policy "pub_emendas"     on emendas_parlamentares for select using (true);
create policy "pub_log"         on coleta_log            for select using (true);

-- =====================================================
-- MIGRAÇÃO v1 → v2 (rode SÓ se já criou as tabelas v1)
-- =====================================================
-- alter table proposicoes add column if not exists ple_id bigint;
-- alter table proposicoes add column if not exists tema_oficial text;
-- alter table proposicoes add column if not exists ano int;
-- alter table orcamento_execucao add column if not exists acao_hash text;
-- alter table emendas_parlamentares add column if not exists descricao_hash text;
-- (converter colunas text de valores para numeric exige recriar a tabela
--  se já houver dados — no MVP sem dados, mais simples dropar e recriar:)
-- drop table orcamento_execucao; drop table emendas_parlamentares;
-- (e rodar este arquivo novamente)
