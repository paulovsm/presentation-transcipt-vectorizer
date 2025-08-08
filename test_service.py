#!/usr/bin/env python3

"""
Script de exemplo para testar o PPT Transcript Service
"""

import asyncio
import httpx
import json
from pathlib import Path
import time

# Configuração do serviço
BASE_URL = "http://localhost:8001"
TIMEOUT = 300.0

async def test_health():
    """Testa se o serviço está funcionando"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                print("✅ Serviço está funcionando")
                return True
            else:
                print(f"❌ Serviço retornou status {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erro ao conectar com o serviço: {e}")
            return False

async def upload_presentation(file_path: str):
    """Faz upload de uma apresentação"""
    if not Path(file_path).exists():
        print(f"❌ Arquivo não encontrado: {file_path}")
        return None
    
    print(f"📤 Fazendo upload de: {file_path}")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            with open(file_path, 'rb') as f:
                files = {"file": (Path(file_path).name, f, "application/octet-stream")}
                data = {
                    "presentation_title": "Apresentação de Teste",
                    "author": "Sistema de Teste",
                    "presentation_type": "test",
                    "language_code": "pt-BR",
                    "detailed_analysis": True
                }
                
                response = await client.post(
                    f"{BASE_URL}/upload",
                    files=files,
                    data=data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print("✅ Upload realizado com sucesso")
                    print(f"   📄 Arquivo: {result['file_name']}")
                    print(f"   📦 Tamanho: {result['file_size']} bytes")
                    print(f"   🆔 ID: {result['file_id']}")
                    return result
                else:
                    print(f"❌ Erro no upload: {response.status_code}")
                    print(f"   Resposta: {response.text}")
                    return None
                    
        except Exception as e:
            print(f"❌ Erro durante upload: {e}")
            return None

async def wait_for_processing(transcription_id: str, max_wait: int = 300):
    """Aguarda o processamento ser concluído"""
    print(f"⏳ Aguardando processamento de {transcription_id}...")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = await client.get(f"{BASE_URL}/transcriptions/{transcription_id}")
                
                if response.status_code == 200:
                    result = response.json()
                    status = result.get("status")
                    
                    if status == "completed":
                        print("✅ Processamento concluído!")
                        return result
                    elif status == "failed":
                        print("❌ Processamento falhou")
                        print(f"   Erro: {result.get('error_message', 'Erro desconhecido')}")
                        return None
                    else:
                        print(f"   Status: {status}")
                        await asyncio.sleep(10)
                else:
                    print(f"❌ Erro ao verificar status: {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"❌ Erro ao verificar processamento: {e}")
                await asyncio.sleep(10)
        
        print("⏰ Timeout atingido")
        return None

async def search_presentations(query: str):
    """Testa busca semântica"""
    print(f"🔍 Buscando por: '{query}'")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            search_data = {
                "query": query,
                "limit": 5,
                "similarity_threshold": 0.5,
                "search_in_slides": True
            }
            
            response = await client.post(
                f"{BASE_URL}/search",
                json=search_data
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Encontrados {result['total_found']} resultados")
                
                for i, res in enumerate(result['results'][:3]):
                    print(f"   {i+1}. Score: {res['score']:.3f}")
                    print(f"      Texto: {res['text'][:100]}...")
                    if res.get('slide_number'):
                        print(f"      Slide: {res['slide_number']}")
                    print()
                
                return result
            else:
                print(f"❌ Erro na busca: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Erro durante busca: {e}")
            return None

async def get_statistics():
    """Obtém estatísticas do sistema"""
    print("📊 Obtendo estatísticas...")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(f"{BASE_URL}/stats")
            
            if response.status_code == 200:
                stats = response.json()
                print("✅ Estatísticas do sistema:")
                print(f"   📈 Total de apresentações: {stats.get('total_presentations', 0)}")
                print(f"   ⏱️  Tempo médio de processamento: {stats.get('average_processing_time_seconds', 0):.2f}s")
                print(f"   📅 Processadas nos últimos 30 dias: {stats.get('recent_30_days', 0)}")
                return stats
            else:
                print(f"❌ Erro ao obter estatísticas: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Erro ao obter estatísticas: {e}")
            return None

async def test_analysis(transcription_id: str):
    """Testa análise customizada"""
    print(f"🧠 Testando análise customizada para {transcription_id}")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            analysis_data = {
                "analysis_type": "business_analysis",
                "custom_prompt": "Identifique os principais riscos e oportunidades apresentados."
            }
            
            response = await client.post(
                f"{BASE_URL}/transcriptions/{transcription_id}/analyze",
                json=analysis_data
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print("✅ Análise gerada com sucesso")
                    print(f"   📝 Análise: {result['analysis'][:200]}...")
                    return result
                else:
                    print(f"❌ Erro na análise: {result.get('error', 'Erro desconhecido')}")
                    return None
            else:
                print(f"❌ Erro na requisição de análise: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Erro durante análise: {e}")
            return None

async def main():
    """Função principal do teste"""
    print("🧪 Iniciando testes do PPT Transcript Service")
    print("=" * 50)
    
    # 1. Testa conectividade
    if not await test_health():
        print("❌ Serviço não está disponível. Certifique-se de que está rodando.")
        return
    
    print()
    
    # 2. Obtém estatísticas iniciais
    await get_statistics()
    print()
    
    # 3. Exemplo de upload (ajuste o caminho do arquivo)
    # Descomente e ajuste para testar upload:
    
    upload_result = await upload_presentation("/teamspace/studios/this_studio/sample_presentations/TheBridge_Precision_Play_Backlog Governance.pptx")
    if upload_result:
        transcription_id = upload_result.get("file_id")
        
        # 4. Aguarda processamento
        transcription_result = await wait_for_processing(transcription_id)
        if transcription_result:
            print(f"✅ Processamento concluído em {transcription_result.get('processing_time_seconds', 0):.2f}s")
            print(f"   📄 Slides processados: {transcription_result.get('slides_count', 0)}")
            
            # 5. Testa análise customizada
            await test_analysis(transcription_id)
            print()
    
    
    # 6. Testa busca (funciona mesmo sem uploads se houver dados existentes)
    await search_presentations("gestão de projetos")
    print()
    
    # 7. Obtém estatísticas finais
    await get_statistics()
    
    print("=" * 50)
    print("🎉 Testes concluídos!")

if __name__ == "__main__":
    print("Para usar este script:")
    print("1. Certifique-se de que o serviço está rodando (python main.py)")
    print("2. Descomente e ajuste o teste de upload se desejar")
    print("3. Execute: python test_service.py")
    print()
    
    # Executa os testes
    asyncio.run(main())
