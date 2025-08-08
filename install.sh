#!/bin/bash

# Script de instalação do PPT Transcript Service
# Baseado no audio-transcript-vectorizer

set -e

echo "🔧 Instalando PPT Transcript Service..."

# Cria diretórios necessários
echo "📁 Criando diretórios..."
mkdir -p data/uploads
mkdir -p data/temp_extraction
mkdir -p data/chroma_db
mkdir -p logs

# Instala dependências Python
echo "📦 Instalando dependências Python..."
pip install -r requirements.txt

# Copia arquivo de configuração se não existir
if [ ! -f .env ]; then
    echo "⚙️  Criando arquivo de configuração..."
    cp .env.example .env
    echo "✅ Arquivo .env criado. Configure suas credenciais antes de executar."
else
    echo "⚠️  Arquivo .env já existe. Verifique se está atualizado."
fi

# Verifica dependências do sistema
echo "🔍 Verificando dependências do sistema..."

# Verifica se o LibreOffice está instalado (opcional para PPT)
if command -v libreoffice &> /dev/null; then
    echo "✅ LibreOffice encontrado (para conversão PPT avançada)"
else
    echo "⚠️  LibreOffice não encontrado. Instale para melhor suporte PPT:"
    echo "   Ubuntu/Debian: sudo apt-get install libreoffice"
    echo "   macOS: brew install --cask libreoffice"
    echo "   Windows: Baixe de https://www.libreoffice.org/"
fi

# Verifica credenciais do Google Cloud
if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ] && [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "⚠️  Credenciais do Google Cloud não configuradas."
    echo "   1. Crie um service account no Google Cloud Console"
    echo "   2. Baixe o arquivo JSON das credenciais"
    echo "   3. Configure GOOGLE_APPLICATION_CREDENTIALS no .env"
fi

echo ""
echo "🎉 Instalação concluída!"
echo ""
echo "📋 Próximos passos:"
echo "1. Configure suas credenciais no arquivo .env"
echo "2. Execute: python main.py"
echo "3. Acesse http://localhost:8001/docs para a documentação da API"
echo ""
echo "📚 Documentação: README.md"
echo "🐛 Logs: logs/app.log"
echo ""
