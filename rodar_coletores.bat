@echo off
cd /d C:\Users\User\OneDrive\Documentos\agora-bsb
echo Rodando CLDF...
python scrapers\coletor_cldf_v2.py >> coleta.log 2>&1
echo Rodando DODF...
python dodf\coletar_dodf_local.py >> coleta.log 2>&1
echo Concluido.