sh

cat > /home/claude/sinj_dodf.py << 'EOF'
"""
Agora BsB - Coletor DODF v4
Usa o feed RSS publico do Jusbrasil que indexa o DODF.
URL: https://www.jusbrasil.com.br/diarios/DODF/rss

Nao requer autenticacao e nao bloqueia IPs externos.
Filtra por palavras-chave de saude e educacao no titulo/descricao.
Salva no status 'vazio' (sem erro) se nao houver publicacoes recentes.
"""

import os, sys, logging, time
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from comum import agora_utc, criar_sessao, registrar_coleta, setup_logging, hash_texto, classificar_com_exclusoes

from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
setup_logging()
log = logging.getLogger("agora.dodf")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip()

RSS_URL = "https://www.jusbrasil.com.br/diarios/DODF/rss"

TERMOS_SAUDE = ["saude", "ses-df", "hospital", "ubs", "atencao primaria", "saude mental", "medicamento", "vacina"]
TERMOS_EDUCACAO = ["educacao", "seedf", "escola", "merenda", "professor", "creche", "alfabetizacao", "ensino"]

import unicodedata
def norm(s):
    return unicodedata.normalize("NFD", str(s)).encode("ascii","ignore").decode().lower()


def classificar(titulo, descricao):
    texto = norm(titulo) + " " + norm(descricao)
    temas = []
    if any(t in texto for t in TERMOS_SAUDE):
        resultado = classificar_com_exclusoes(texto, "saude")
        if resultado:
            temas.extend(resultado)
    if any(t in texto for t in TERMOS_EDUCACAO):
        resultado = classificar_com_exclusoes(texto, "educacao")
        if resultado:
            temas.extend(resultado)
    return list(set(temas))


def coletar_rss(sessao):
    log.info(f"Buscando RSS: {RSS_URL}")
    try:
        resp = sessao.get(RSS_URL, timeout=30, verify=False)
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Erro ao buscar RSS: {e}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except Exception as e:
        log.error(f"Erro ao parsear XML: {e}")
        return []

    items = root.findall(".//item")
    log.info(f"Total de itens no RSS: {len(items)}")

    publicacoes = {}
    for item in items:
        titulo = item.findtext("title") or ""
        descricao = item.findtext("description") or ""
        link = item.findtext("link") or ""
        data = item.findtext("pubDate") or ""
        guid = item.findtext("guid") or hash_texto(titulo + link)

        temas = classificar(titulo, descricao)
        if not temas:
            continue

        pub = {
            "numero": hash_texto(guid),
            "tipo": "Publicacao DODF",
            "descricao": f"{titulo} — {descricao}"[:800],
            "secretaria": "",
            "data_publicacao": None,
            "link": link,
            "temas": temas,
            "fonte": "DODF",
            "coletado_em": agora_utc(),
        }
        publicacoes[pub["numero"]] = pub

    log.info(f"Publicacoes relevantes: {len(publicacoes)}")
    return list(publicacoes.values())


def salvar(supabase, publicacoes):
    if not publicacoes:
        return 0
    salvos = 0
    for i in range(0, len(publicacoes), 50):
        bloco = publicacoes[i:i+50]
        try:
            supabase.table("publicacoes_dodf").upsert(
                bloco, on_conflict="numero,fonte"
            ).execute()
            salvos += len(bloco)
        except Exception as e:
            log.error(f"Erro ao salvar: {e}")
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
EOF
python -m ast /home/claude/sinj_dodf.py && echo "SINTAXE OK"
Output

Module(
   body=[
      Expr(
         value=Constant(value="\nAgora BsB - Coletor DODF v4\nUsa o feed RSS publico do Jusbrasil que indexa o DODF.\nURL: https://www.jusbrasil.com.br/diarios/DODF/rss\n\nNao requer autenticacao e nao bloqueia IPs externos.\nFiltra por palavras-chave de saude e educacao no titulo/descricao.\nSalva no status 'vazio' (sem erro) se nao houver publicacoes recentes.\n")),
      Import(
         names=[
            alias(name='os'),
            alias(name='sys'),
            alias(name='logging'),
            alias(name='time')]),
      Import(
         names=[
            alias(name='xml.etree.ElementTree', asname='ET')]),
      Expr(
         value=Call(
            func=Attribute(
               value=Attribute(
                  value=Name(id='sys', ctx=Load()),
                  attr='path',
                  ctx=Load()),
               attr='insert',
               ctx=Load()),
            args=[
               Constant(value=0),
               Call(
                  func=Attribute(
                     value=Attribute(
                        value=Name(id='os', ctx=Load()),
                        attr='path',
                        ctx=Load()),
                     attr='dirname',
                     ctx=Load()),
                  args=[
                     Name(id='__file__', ctx=Load())],
                  keywords=[])],
            keywords=[])),
      ImportFrom(
         module='comum',
         names=[
            alias(name='agora_utc'),
            alias(name='criar_sessao'),
            alias(name='registrar_coleta'),
            alias(name='setup_logging'),
            alias(name='hash_texto'),
            alias(name='classificar_com_exclusoes')],
         level=0),
      ImportFrom(
         module='supabase',
         names=[
            alias(name='create_client')],
         level=0),
      ImportFrom(
         module='dotenv',
         names=[
            alias(name='load_dotenv')],
         level=0),
      Expr(
         value=Call(
            func=Name(id='load_dotenv', ctx=Load()),
            args=[],
            keywords=[])),
      Expr(
         value=Call(
            func=Name(id='setup_logging', ctx=Load()),
            args=[],
            keywords=[])),
      Assign(
         targets=[
            Name(id='log', ctx=Store())],
         value=Call(
            func=Attribute(
               value=Name(id='logging', ctx=Load()),
               attr='getLogger',
               ctx=Load()),
            args=[
               Constant(value='agora.dodf')],
            keywords=[])),
      Import(
         names=[
            alias(name='urllib3')]),
      Expr(
         value=Call(
            func=Attribute(
               value=Name(id='urllib3', ctx=Load()),
               attr='disable_warnings',
               ctx=Load()),
            args=[
               Attribute(
                  value=Attribute(
                     value=Name(id='urllib3', ctx=Load()),
                     attr='exceptions',
                     ctx=Load()),
                  attr='InsecureRequestWarning',
                  ctx=Load())],
            keywords=[])),
      Assign(
         targets=[
            Name(id='SUPABASE_URL', ctx=Store())],
         value=Call(
            func=Attribute(
               value=Subscript(
                  value=Attribute(
                     value=Name(id='os', ctx=Load()),
                     attr='environ',
                     ctx=Load()),
                  slice=Constant(value='SUPABASE_URL'),
                  ctx=Load()),
               attr='strip',
               ctx=Load()),
            args=[],
            keywords=[])),
      Assign(
         targets=[
            Name(id='SUPABASE_KEY', ctx=Store())],
         value=Call(
            func=Attribute(
               value=Subscript(
                  value=Attribute(
                     value=Name(id='os', ctx=Load()),
                     attr='environ',
                     ctx=Load()),
                  slice=Constant(value='SUPABASE_KEY'),
                  ctx=Load()),
               attr='strip',
               ctx=Load()),
            args=[],
            keywords=[])),
      Assign(
         targets=[
            Name(id='RSS_URL', ctx=Store())],
         value=Constant(value='https://www.jusbrasil.com.br/diarios/DODF/rss')),
      Assign(
         targets=[
            Name(id='TERMOS_SAUDE', ctx=Store())],
         value=List(
            elts=[
               Constant(value='saude'),
               Constant(value='ses-df'),
               Constant(value='hospital'),
               Constant(value='ubs'),
               Constant(value='atencao primaria'),
               Constant(value='saude mental'),
               Constant(value='medicamento'),
               Constant(value='vacina')],
            ctx=Load())),
      Assign(
         targets=[
            Name(id='TERMOS_EDUCACAO', ctx=Store())],
         value=List(
            elts=[
               Constant(value='educacao'),
               Constant(value='seedf'),
               Constant(value='escola'),
               Constant(value='merenda'),
               Constant(value='professor'),
               Constant(value='creche'),
               Constant(value='alfabetizacao'),
               Constant(value='ensino')],
            ctx=Load())),
      Import(
         names=[
            alias(name='unicodedata')]),
      FunctionDef(
         name='norm',
         args=arguments(
            posonlyargs=[],
            args=[
               arg(arg='s')],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[]),
         body=[
            Return(
               value=Call(
                  func=Attribute(
                     value=Call(
                        func=Attribute(
                           value=Call(
                              func=Attribute(
                                 value=Call(
                                    func=Attribute(
                                       value=Name(id='unicodedata', ctx=Load()),
                                       attr='normalize',
                                       ctx=Load()),
                                    args=[
                                       Constant(value='NFD'),
                                       Call(
                                          func=Name(id='str', ctx=Load()),
                                          args=[
                                             Name(id='s', ctx=Load())],
                                          keywords=[])],
                                    keywords=[]),
                                 attr='encode',
                                 ctx=Load()),
                              args=[
                                 Constant(value='ascii'),
                                 Constant(value='ignore')],
                              keywords=[]),
                           attr='decode',
                           ctx=Load()),
                        args=[],
                        keywords=[]),
                     attr='lower',
                     ctx=Load()),
                  args=[],
                  keywords=[]))],
         decorator_list=[],
         type_params=[]),
      FunctionDef(
         name='classificar',
         args=arguments(
            posonlyargs=[],
            args=[
               arg(arg='titulo'),
               arg(arg='descricao')],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[]),
         body=[
            Assign(
               targets=[
                  Name(id='texto', ctx=Store())],
               value=BinOp(
                  left=BinOp(
                     left=Call(
                        func=Name(id='norm', ctx=Load()),
                        args=[
                           Name(id='titulo', ctx=Load())],
                        keywords=[]),
                     op=Add(),
                     right=Constant(value=' ')),
                  op=Add(),
                  right=Call(
                     func=Name(id='norm', ctx=Load()),
                     args=[
                        Name(id='descricao', ctx=Load())],
                     keywords=[]))),
            Assign(
               targets=[
                  Name(id='temas', ctx=Store())],
               value=List(elts=[], ctx=Load())),
            If(
               test=Call(
                  func=Name(id='any', ctx=Load()),
                  args=[
                     GeneratorExp(
                        elt=Compare(
                           left=Name(id='t', ctx=Load()),
                           ops=[
                              In()],
                           comparators=[
                              Name(id='texto', ctx=Load())]),
                        generators=[
                           comprehension(
                              target=Name(id='t', ctx=Store()),
                              iter=Name(id='TERMOS_SAUDE', ctx=Load()),
                              ifs=[],
                              is_async=0)])],
                  keywords=[]),
               body=[
                  Assign(
                     targets=[
                        Name(id='resultado', ctx=Store())],
                     value=Call(
                        func=Name(id='classificar_com_exclusoes', ctx=Load()),
                        args=[
                           Name(id='texto', ctx=Load()),
                           Constant(value='saude')],
                        keywords=[])),
                  If(
                     test=Name(id='resultado', ctx=Load()),
                     body=[
                        Expr(
                           value=Call(
                              func=Attribute(
                                 value=Name(id='temas', ctx=Load()),
                                 attr='extend',
                                 ctx=Load()),
                              args=[
                                 Name(id='resultado', ctx=Load())],
                              keywords=[]))],
                     orelse=[])],
               orelse=[]),
            If(
               test=Call(
                  func=Name(id='any', ctx=Load()),
                  args=[
                     GeneratorExp(
                        elt=Compare(
                           left=Name(id='t', ctx=Load()),
                           ops=[
                              In()],
                           comparators=[
                              Name(id='texto', ctx=Load())]),
                        generators=[
                           comprehension(
                              target=Name(id='t', ctx=Store()),
                              iter=Name(id='TERMOS_EDUCACAO', ctx=Load()),
                              ifs=[],
                              is_async=0)])],
                  keywords=[]),
               body=[
                  Assign(
                     targets=[
                        Name(id='resultado', ctx=Store())],
                     value=Call(
                        func=Name(id='classificar_com_exclusoes', ctx=Load()),
                        args=[
                           Name(id='texto', ctx=Load()),
                           Constant(value='educacao')],
                        keywords=[])),
                  If(
                     test=Name(id='resultado', ctx=Load()),
                     body=[
                        Expr(
                           value=Call(
                              func=Attribute(
                                 value=Name(id='temas', ctx=Load()),
                                 attr='extend',
                                 ctx=Load()),
                              args=[
                                 Name(id='resultado', ctx=Load())],
                              keywords=[]))],
                     orelse=[])],
               orelse=[]),
            Return(
               value=Call(
                  func=Name(id='list', ctx=Load()),
                  args=[
                     Call(
                        func=Name(id='set', ctx=Load()),
                        args=[
                           Name(id='temas', ctx=Load())],
                        keywords=[])],
                  keywords=[]))],
         decorator_list=[],
         type_params=[]),
      FunctionDef(
         name='coletar_rss',
         args=arguments(
            posonlyargs=[],
            args=[
               arg(arg='sessao')],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[]),
         body=[
            Expr(
               value=Call(
                  func=Attribute(
                     value=Name(id='log', ctx=Load()),
                     attr='info',
                     ctx=Load()),
                  args=[
                     JoinedStr(
                        values=[
                           Constant(value='Buscando RSS: '),
                           FormattedValue(
                              value=Name(id='RSS_URL', ctx=Load()),
                              conversion=-1)])],
                  keywords=[])),
            Try(
               body=[
                  Assign(
                     targets=[
                        Name(id='resp', ctx=Store())],
                     value=Call(
                        func=Attribute(
                           value=Name(id='sessao', ctx=Load()),
                           attr='get',
                           ctx=Load()),
                        args=[
                           Name(id='RSS_URL', ctx=Load())],
                        keywords=[
                           keyword(
                              arg='timeout',
                              value=Constant(value=30)),
                           keyword(
                              arg='verify',
                              value=Constant(value=False))])),
                  Expr(
                     value=Call(
                        func=Attribute(
                           value=Name(id='resp', ctx=Load()),
                           attr='raise_for_status',
                           ctx=Load()),
                        args=[],
                        keywords=[]))],
               handlers=[
                  ExceptHandler(
                     type=Name(id='Exception', ctx=Load()),
                     name='e',
                     body=[
                        Expr(
                           value=Call(
                              func=Attribute(
                                 value=Name(id='log', ctx=Load()),
                                 attr='error',
                                 ctx=Load()),
                              args=[
                                 JoinedStr(
                                    values=[
                                       Constant(value='Erro ao buscar RSS: '),
                                       FormattedValue(
                                          value=Name(id='e', ctx=Load()),
                                          conversion=-1)])],
                              keywords=[])),
                        Return(
                           value=List(elts=[], ctx=Load()))])],
               orelse=[],
               finalbody=[]),
            Try(
               body=[
                  Assign(
                     targets=[
                        Name(id='root', ctx=Store())],
                     value=Call(
                        func=Attribute(
                           value=Name(id='ET', ctx=Load()),
                           attr='fromstring',
                           ctx=Load()),
                        args=[
                           Attribute(
                              value=Name(id='resp', ctx=Load()),
                              attr='content',
                              ctx=Load())],
                        keywords=[]))],
               handlers=[
                  ExceptHandler(
                     type=Name(id='Exception', ctx=Load()),
                     name='e',
                     body=[
                        Expr(
                           value=Call(
                              func=Attribute(
                                 value=Name(id='log', ctx=Load()),
                                 attr='error',
                                 ctx=Load()),
                              args=[
                                 JoinedStr(
                                    values=[
                                       Constant(value='Erro ao parsear XML: '),
                                       FormattedValue(
                                          value=Name(id='e', ctx=Load()),
                                          conversion=-1)])],
                              keywords=[])),
                        Return(
                           value=List(elts=[], ctx=Load()))])],
               orelse=[],
               finalbody=[]),
            Assign(
               targets=[
                  Name(id='items', ctx=Store())],
               value=Call(
                  func=Attribute(
                     value=Name(id='root', ctx=Load()),
                     attr='findall',
                     ctx=Load()),
                  args=[
                     Constant(value='.//item')],
                  keywords=[])),
            Expr(
               value=Call(
                  func=Attribute(
                     value=Name(id='log', ctx=Load()),
                     attr='info',
                     ctx=Load()),
                  args=[
                     JoinedStr(
                        values=[
                           Constant(value='Total de itens no RSS: '),
                           FormattedValue(
                              value=Call(
                                 func=Name(id='len', ctx=Load()),
                                 args=[
                                    Name(id='items', ctx=Load())],
                                 keywords=[]),
                              conversion=-1)])],
                  keywords=[])),
            Assign(
               targets=[
                  Name(id='publicacoes', ctx=Store())],
               value=Dict(keys=[], values=[])),
            For(
               target=Name(id='item', ctx=Store()),
               iter=Name(id='items', ctx=Load()),
               body=[
                  Assign(
                     targets=[
                        Name(id='titulo', ctx=Store())],
                     value=BoolOp(
                        op=Or(),
                        values=[
                           Call(
                              func=Attribute(
                                 value=Name(id='item', ctx=Load()),
                                 attr='findtext',
                                 ctx=Load()),
                              args=[
                                 Constant(value='title')],
                              keywords=[]),
                           Constant(value='')])),
                  Assign(
                     targets=[
                        Name(id='descricao', ctx=Store())],
                     value=BoolOp(
                        op=Or(),
                        values=[
                           Call(
                              func=Attribute(
                                 value=Name(id='item', ctx=Load()),
                                 attr='findtext',
                                 ctx=Load()),
                              args=[
                                 Constant(value='description')],
                              keywords=[]),
                           Constant(value='')])),
                  Assign(
                     targets=[
                        Name(id='link', ctx=Store())],
                     value=BoolOp(
                        op=Or(),
                        values=[
                           Call(
                              func=Attribute(
                                 value=Name(id='item', ctx=Load()),
                                 attr='findtext',
                                 ctx=Load()),
                              args=[
                                 Constant(value='link')],
                              keywords=[]),
                           Constant(value='')])),
                  Assign(
                     targets=[
                        Name(id='data', ctx=Store())],
                     value=BoolOp(
                        op=Or(),
                        values=[
                           Call(
                              func=Attribute(
                                 value=Name(id='item', ctx=Load()),
                                 attr='findtext',
                                 ctx=Load()),
                              args=[
                                 Constant(value='pubDate')],
                              keywords=[]),
                           Constant(value='')])),
                  Assign(
                     targets=[
                        Name(id='guid', ctx=Store())],
                     value=BoolOp(
                        op=Or(),
                        values=[
                           Call(
                              func=Attribute(
                                 value=Name(id='item', ctx=Load()),
                                 attr='findtext',
                                 ctx=Load()),
                              args=[
                                 Constant(value='guid')],
                              keywords=[]),
                           Call(
                              func=Name(id='hash_texto', ctx=Load()),
                              args=[
                                 BinOp(
                                    left=Name(id='titulo', ctx=Load()),
                                    op=Add(),
                                    right=Name(id='link', ctx=Load()))],
                              keywords=[])])),
                  Assign(
                     targets=[
                        Name(id='temas', ctx=Store())],
                     value=Call(
                        func=Name(id='classificar', ctx=Load()),
                        args=[
                           Name(id='titulo', ctx=Load()),
                           Name(id='descricao', ctx=Load())],
                        keywords=[])),
                  If(
                     test=UnaryOp(
                        op=Not(),
                        operand=Name(id='temas', ctx=Load())),
                     body=[
                        Continue()],
                     orelse=[]),
                  Assign(
                     targets=[
                        Name(id='pub', ctx=Store())],
                     value=Dict(
                        keys=[
                           Constant(value='numero'),
                           Constant(value='tipo'),
                           Constant(value='descricao'),
                           Constant(value='secretaria'),
                           Constant(value='data_publicacao'),
                           Constant(value='link'),
                           Constant(value='temas'),
                           Constant(value='fonte'),
                           Constant(value='coletado_em')],
                        values=[
                           Call(
                              func=Name(id='hash_texto', ctx=Load()),
                              args=[
                                 Name(id='guid', ctx=Load())],
                              keywords=[]),
                           Constant(value='Publicacao DODF'),
                           Subscript(
                              value=JoinedStr(
                                 values=[
                                    FormattedValue(
                                       value=Name(id='titulo', ctx=Load()),
                                       conversion=-1),
                                    Constant(value=' — '),
                                    FormattedValue(
                                       value=Name(id='descricao', ctx=Load()),
                                       conversion=-1)]),
                              slice=Slice(
                                 upper=Constant(value=800)),
                              ctx=Load()),
                           Constant(value=''),
                           Constant(value=None),
                           Name(id='link', ctx=Load()),
                           Name(id='temas', ctx=Load()),
                           Constant(value='DODF'),
                           Call(
                              func=Name(id='agora_utc', ctx=Load()),
                              args=[],
                              keywords=[])])),
                  Assign(
                     targets=[
                        Subscript(
                           value=Name(id='publicacoes', ctx=Load()),
                           slice=Subscript(
                              value=Name(id='pub', ctx=Load()),
                              slice=Constant(value='numero'),
                              ctx=Load()),
                           ctx=Store())],
                     value=Name(id='pub', ctx=Load()))],
               orelse=[]),
            Expr(
               value=Call(
                  func=Attribute(
                     value=Name(id='log', ctx=Load()),
                     attr='info',
                     ctx=Load()),
                  args=[
                     JoinedStr(
                        values=[
                           Constant(value='Publicacoes relevantes: '),
                           FormattedValue(
                              value=Call(
                                 func=Name(id='len', ctx=Load()),
                                 args=[
                                    Name(id='publicacoes', ctx=Load())],
                                 keywords=[]),
                              conversion=-1)])],
                  keywords=[])),
            Return(
               value=Call(
                  func=Name(id='list', ctx=Load()),
                  args=[
                     Call(
                        func=Attribute(
                           value=Name(id='publicacoes', ctx=Load()),
                           attr='values',
                           ctx=Load()),
                        args=[],
                        keywords=[])],
                  keywords=[]))],
         decorator_list=[],
         type_params=[]),
      FunctionDef(
         name='salvar',
         args=arguments(
            posonlyargs=[],
            args=[
               arg(arg='supabase'),
               arg(arg='publicacoes')],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[]),
         body=[
            If(
               test=UnaryOp(
                  op=Not(),
                  operand=Name(id='publicacoes', ctx=Load())),
               body=[
                  Return(
                     value=Constant(value=0))],
               orelse=[]),
            Assign(
               targets=[
                  Name(id='salvos', ctx=Store())],
               value=Constant(value=0)),
            For(
               target=Name(id='i', ctx=Store()),
               iter=Call(
                  func=Name(id='range', ctx=Load()),
                  args=[
                     Constant(value=0),
                     Call(
                        func=Name(id='len', ctx=Load()),
                        args=[
                           Name(id='publicacoes', ctx=Load())],
                        keywords=[]),
                     Constant(value=50)],
                  keywords=[]),
               body=[
                  Assign(
                     targets=[
                        Name(id='bloco', ctx=Store())],
                     value=Subscript(
                        value=Name(id='publicacoes', ctx=Load()),
                        slice=Slice(
                           lower=Name(id='i', ctx=Load()),
                           upper=BinOp(
                              left=Name(id='i', ctx=Load()),
                              op=Add(),
                              right=Constant(value=50))),
                        ctx=Load())),
                  Try(
                     body=[
                        Expr(
                           value=Call(
                              func=Attribute(
                                 value=Call(
                                    func=Attribute(
                                       value=Call(
                                          func=Attribute(
                                             value=Name(id='supabase', ctx=Load()),
                                             attr='table',
                                             ctx=Load()),
                                          args=[
                                             Constant(value='publicacoes_dodf')],
                                          keywords=[]),
                                       attr='upsert',
                                       ctx=Load()),
                                    args=[
                                       Name(id='bloco', ctx=Load())],
                                    keywords=[
                                       keyword(
                                          arg='on_conflict',
                                          value=Constant(value='numero,fonte'))]),
                                 attr='execute',
                                 ctx=Load()),
                              args=[],
                              keywords=[])),
                        AugAssign(
                           target=Name(id='salvos', ctx=Store()),
                           op=Add(),
                           value=Call(
                              func=Name(id='len', ctx=Load()),
                              args=[
                                 Name(id='bloco', ctx=Load())],
                              keywords=[]))],
                     handlers=[
                        ExceptHandler(
                           type=Name(id='Exception', ctx=Load()),
                           name='e',
                           body=[
                              Expr(
                                 value=Call(
                                    func=Attribute(
                                       value=Name(id='log', ctx=Load()),
                                       attr='error',
                                       ctx=Load()),
                                    args=[
                                       JoinedStr(
                                          values=[
                                             Constant(value='Erro ao salvar: '),
                                             FormattedValue(
                                                value=Name(id='e', ctx=Load()),
                                                conversion=-1)])],
                                    keywords=[]))])],
                     orelse=[],
                     finalbody=[])],
               orelse=[]),
            Return(
               value=Name(id='salvos', ctx=Load()))],
         decorator_list=[],
         type_params=[]),
      FunctionDef(
         name='main',
         args=arguments(
            posonlyargs=[],
            args=[],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[]),
         body=[
            Assign(
               targets=[
                  Name(id='supabase', ctx=Store())],
               value=Call(
                  func=Name(id='create_client', ctx=Load()),
                  args=[
                     Name(id='SUPABASE_URL', ctx=Load()),
                     Name(id='SUPABASE_KEY', ctx=Load())],
                  keywords=[])),
            Assign(
               targets=[
                  Name(id='sessao', ctx=Store())],
               value=Call(
                  func=Name(id='criar_sessao', ctx=Load()),
                  args=[],
                  keywords=[
                     keyword(
                        arg='total_retries',
                        value=Constant(value=2)),
                     keyword(
                        arg='backoff',
                        value=Constant(value=1.0))])),
            Try(
               body=[
                  Assign(
                     targets=[
                        Name(id='publicacoes', ctx=Store())],
                     value=Call(
                        func=Name(id='coletar_rss', ctx=Load()),
                        args=[
                           Name(id='sessao', ctx=Load())],
                        keywords=[])),
                  Assign(
                     targets=[
                        Name(id='salvos', ctx=Store())],
                     value=Call(
                        func=Name(id='salvar', ctx=Load()),
                        args=[
                           Name(id='supabase', ctx=Load()),
                           Name(id='publicacoes', ctx=Load())],
                        keywords=[])),
                  Assign(
                     targets=[
                        Name(id='status', ctx=Store())],
                     value=IfExp(
                        test=Compare(
                           left=Name(id='salvos', ctx=Load()),
                           ops=[
                              Gt()],
                           comparators=[
                              Constant(value=0)]),
                        body=Constant(value='ok'),
                        orelse=Constant(value='vazio'))),
                  Expr(
                     value=Call(
                        func=Name(id='registrar_coleta', ctx=Load()),
                        args=[
                           Name(id='supabase', ctx=Load()),
                           Constant(value='DODF'),
                           Name(id='status', ctx=Load()),
                           Name(id='salvos', ctx=Load())],
                        keywords=[])),
                  Expr(
                     value=Call(
                        func=Attribute(
                           value=Name(id='log', ctx=Load()),
                           attr='info',
                           ctx=Load()),
                        args=[
                           JoinedStr(
                              values=[
                                 Constant(value='Coleta DODF finalizada: '),
                                 FormattedValue(
                                    value=Name(id='salvos', ctx=Load()),
                                    conversion=-1),
                                 Constant(value=' registros')])],
                        keywords=[]))],
               handlers=[
                  ExceptHandler(
                     type=Name(id='Exception', ctx=Load()),
                     name='e',
                     body=[
                        Expr(
                           value=Call(
                              func=Name(id='registrar_coleta', ctx=Load()),
                              args=[
                                 Name(id='supabase', ctx=Load()),
                                 Constant(value='DODF'),
                                 Constant(value='erro'),
                                 Constant(value=0),
                                 Call(
                                    func=Name(id='str', ctx=Load()),
                                    args=[
                                       Name(id='e', ctx=Load())],
                                    keywords=[])],
                              keywords=[])),
                        Raise()])],
               orelse=[],
               finalbody=[])],
         decorator_list=[],
         type_params=[]),
      If(
         test=Compare(
            left=Name(id='__name__', ctx=Load()),
            ops=[
               Eq()],
            comparators=[
               Constant(value='__main__')]),
         body=[
            Expr(
               value=Call(
                  func=Name(id='main', ctx=Load()),
                  args=[],
                  keywords=[]))],
         orelse=[])],
   type_ignores=[])
SINTAXE OK