#!/usr/bin/env python3

"""
Sistema de Transcrição de Apresentações PowerPoint/PDF
Baseado na arquitetura do audio-transcript-vectorizer
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.api.main import app
from src.config.settings import settings
import uvicorn


def main():
    """Função principal"""
    # Suprimir logs do watchfiles em modo de desenvolvimento
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
    
    print("📊  Sistema de Transcrição de Apresentações PowerPoint/PDF")
    print("=======================================================")
    print(f"Iniciando servidor na porta {settings.api_port}")
    print(f"Projeto GCP: {settings.google_cloud_project}")
    print(f"Modelo Gemini: {settings.gemini_model}")
    print(f"Base vectorizada: {settings.chroma_collection_name}")
    print("=======================================================")
    
    # Configuração otimizada para concorrência
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
        workers=1 if settings.api_reload else settings.api_workers,  # Múltiplos workers em produção
        loop="asyncio",  # Event loop otimizado
        http="httptools",  # Parser HTTP mais rápido
        access_log=False,  # Reduz overhead de logging
        use_colors=True,
        timeout_keep_alive=settings.api_timeout_keep_alive
    )


if __name__ == "__main__":
    main()
