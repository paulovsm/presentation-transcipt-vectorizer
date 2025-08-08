#!/usr/bin/env python3

"""
Script de teste específico para a nova funcionalidade de extração de slides
com foco na análise visual usando imagens
"""

import asyncio
import os
import sys
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.processing.slide_extraction import SlideExtractionService
from src.config.settings import settings
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_slide_extraction_service():
    """
    Testa o serviço de extração de slides com a nova abordagem visual
    """
    print("🧪 Testando SlideExtractionService com análise visual")
    print("=" * 60)
    
    # Inicializa o serviço
    extractor = SlideExtractionService()
    
    print(f"📁 Diretório temporário: {extractor.temp_dir}")
    print(f"🖼️  Qualidade de imagem: {settings.image_quality}")
    print(f"📐 DPI configurado: {extractor.image_dpi}")
    print(f"📏 Dimensão máxima: {extractor.max_image_dimension}px")
    print()
    
    # Lista arquivos de teste disponíveis
    test_files = []
    
    # Verifica apresentação de exemplo
    sample_ppt = "/teamspace/studios/this_studio/sample_presentations/TheBridge_Precision_Play_Backlog Governance.pptx"
    if os.path.exists(sample_ppt):
        test_files.append(sample_ppt)
    
    # Procura outros arquivos de teste
    for ext in ['.pptx', '.ppt', '.pdf']:
        for file_path in Path("/teamspace/studios/this_studio").rglob(f"*{ext}"):
            if file_path.is_file() and str(file_path) not in test_files:
                test_files.append(str(file_path))
                if len(test_files) >= 3:  # Limita a 3 arquivos para teste
                    break
    
    if not test_files:
        print("❌ Nenhum arquivo de teste encontrado (.pptx, .ppt, .pdf)")
        print("   Coloque arquivos de teste no diretório do projeto para testar")
        return
    
    print(f"📄 Arquivos encontrados para teste: {len(test_files)}")
    for i, file_path in enumerate(test_files):
        print(f"   {i+1}. {Path(file_path).name}")
    print()
    
    # Testa cada arquivo
    for file_path in test_files:
        await test_single_file(extractor, file_path)
        print("-" * 40)
    
    print("🎉 Testes de extração concluídos!")

async def test_single_file(extractor: SlideExtractionService, file_path: str):
    """
    Testa extração de um arquivo específico
    """
    file_name = Path(file_path).name
    file_ext = Path(file_path).suffix.lower()
    
    print(f"📄 Testando: {file_name}")
    print(f"   Formato: {file_ext}")
    print(f"   Tamanho: {os.path.getsize(file_path) / 1024 / 1024:.2f} MB")
    
    try:
        # Executa extração
        start_time = asyncio.get_event_loop().time()
        result = await extractor.extract_slides_from_file(file_path)
        end_time = asyncio.get_event_loop().time()
        
        slides_data = result["slides_data"]
        metadata = result["metadata"]
        
        print(f"✅ Extração concluída em {end_time - start_time:.2f}s")
        print(f"   📊 Total de slides: {len(slides_data)}")
        print(f"   📋 Título: {metadata.get('title', 'N/A')}")
        print(f"   👤 Autor: {metadata.get('author', 'N/A')}")
        print()
        
        # Testa alguns slides específicos
        for i, slide in enumerate(slides_data[:3]):  # Primeiros 3 slides
            slide_num = slide["slide_number"]
            image_path = slide.get("image_path")
            image_base64 = slide.get("image_base64")
            
            print(f"   📄 Slide {slide_num}:")
            
            if image_path:
                if os.path.exists(image_path):
                    # Valida qualidade da imagem
                    quality_info = await extractor.validate_image_quality(image_path)
                    if quality_info.get("is_valid"):
                        print(f"      🖼️  Imagem: {quality_info['width']}x{quality_info['height']} ({quality_info['size_bytes']} bytes)")
                        print(f"      📐 Aspect ratio: {quality_info['aspect_ratio']:.2f}")
                    else:
                        print(f"      ❌ Imagem inválida: {quality_info.get('error', 'Erro desconhecido')}")
                else:
                    print(f"      ❌ Arquivo de imagem não encontrado: {image_path}")
            else:
                print(f"      ⚠️  Imagem não gerada")
            
            if image_base64:
                print(f"      📦 Base64: {len(image_base64)} caracteres")
            else:
                print(f"      ⚠️  Base64 não disponível")
            
            print()
        
        # Testa limpeza de arquivos temporários
        print("🧹 Testando limpeza de arquivos temporários...")
        image_paths = extractor.get_slide_image_paths(slides_data)
        
        if image_paths:
            print(f"   📁 {len(image_paths)} arquivos temporários criados")
            extractor.cleanup_temp_files(image_paths)
            
            # Verifica se foram removidos
            remaining = [path for path in image_paths if os.path.exists(path)]
            if remaining:
                print(f"   ⚠️  {len(remaining)} arquivos não foram removidos")
            else:
                print(f"   ✅ Todos os arquivos temporários foram removidos")
        else:
            print(f"   ℹ️  Nenhum arquivo temporário para limpar")
        
    except Exception as e:
        print(f"❌ Erro durante extração: {e}")
        logger.exception("Detalhes do erro:")

async def test_configuration():
    """
    Testa diferentes configurações
    """
    print("⚙️ Testando diferentes configurações")
    print("=" * 60)
    
    # Testa configurações de qualidade
    quality_settings = ["high", "medium", "low"]
    
    for quality in quality_settings:
        print(f"🎛️  Testando qualidade: {quality}")
        
        # Temporariamente altera configuração
        original_quality = settings.image_quality
        settings.image_quality = quality
        
        extractor = SlideExtractionService()
        expected_dpi = 300 if quality == "high" else 200 if quality == "medium" else 150
        
        print(f"   📐 DPI esperado: {expected_dpi}, obtido: {extractor.image_dpi}")
        
        if extractor.image_dpi == expected_dpi:
            print(f"   ✅ Configuração aplicada corretamente")
        else:
            print(f"   ❌ Configuração não aplicada")
        
        # Restaura configuração original
        settings.image_quality = original_quality
        print()

async def test_error_handling():
    """
    Testa tratamento de erros
    """
    print("🛡️ Testando tratamento de erros")
    print("=" * 60)
    
    extractor = SlideExtractionService()
    
    # Teste 1: Arquivo inexistente
    print("1. Arquivo inexistente:")
    try:
        await extractor.extract_slides_from_file("/path/inexistente.pptx")
        print("   ❌ Deveria ter dado erro")
    except Exception as e:
        print(f"   ✅ Erro capturado corretamente: {type(e).__name__}")
    
    # Teste 2: Formato não suportado
    print("2. Formato não suportado:")
    try:
        await extractor.extract_slides_from_file("arquivo.txt")
        print("   ❌ Deveria ter dado erro")
    except ValueError as e:
        print(f"   ✅ Erro capturado corretamente: {e}")
    except Exception as e:
        print(f"   ⚠️  Erro inesperado: {type(e).__name__}: {e}")
    
    # Teste 3: Imagem inválida
    print("3. Validação de imagem inválida:")
    invalid_path = "/path/inexistente.png"
    quality_info = await extractor.validate_image_quality(invalid_path)
    if not quality_info.get("is_valid"):
        print(f"   ✅ Imagem inválida detectada corretamente")
    else:
        print(f"   ❌ Deveria ter detectado imagem inválida")
    
    print()

async def main():
    """
    Função principal dos testes
    """
    print("🧪 Iniciando testes completos do SlideExtractionService")
    print("🎯 Foco: Nova abordagem com análise visual de imagens")
    print("=" * 60)
    
    # Verifica dependências
    try:
        from src.processing.slide_extraction import SlideExtractionService
        print("✅ Módulo de extração importado com sucesso")
    except ImportError as e:
        print(f"❌ Erro ao importar módulo: {e}")
        return
    
    # Verifica diretório temporário
    temp_dir = settings.temp_extraction_directory
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
        print(f"📁 Diretório temporário criado: {temp_dir}")
    else:
        print(f"📁 Diretório temporário encontrado: {temp_dir}")
    
    print()
    
    # Executa testes
    await test_configuration()
    await test_error_handling()
    await test_slide_extraction_service()
    
    print("=" * 60)
    print("🎉 Todos os testes concluídos!")

if __name__ == "__main__":
    print("🔧 Script de teste para SlideExtractionService")
    print("   Foco na nova abordagem de análise visual com imagens")
    print()
    
    # Executa os testes
    asyncio.run(main())
