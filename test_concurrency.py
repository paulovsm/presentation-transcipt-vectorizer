#!/usr/bin/env python3
"""
Teste de concorrência para verificar se o problema de bloqueio foi resolvido
"""

import asyncio
import aiohttp
import time
import json
import random
import string
from concurrent.futures import ThreadPoolExecutor


class ConcurrencyTester:
    """
    Testa concorrência do serviço de transcrições
    """
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_health_endpoint(self) -> dict:
        """Testa endpoint de health"""
        try:
            start_time = time.time()
            async with self.session.get(f"{self.base_url}/health") as response:
                duration = time.time() - start_time
                result = await response.json()
                return {
                    "endpoint": "/health",
                    "status_code": response.status,
                    "duration": duration,
                    "success": response.status == 200,
                    "response": result
                }
        except Exception as e:
            return {
                "endpoint": "/health",
                "status_code": None,
                "duration": None,
                "success": False,
                "error": str(e)
            }
    
    async def test_list_transcriptions(self) -> dict:
        """Testa endpoint de listagem de transcrições"""
        try:
            start_time = time.time()
            async with self.session.get(f"{self.base_url}/transcriptions?limit=5") as response:
                duration = time.time() - start_time
                result = await response.json()
                return {
                    "endpoint": "/transcriptions",
                    "status_code": response.status,
                    "duration": duration,
                    "success": response.status == 200,
                    "response_size": len(json.dumps(result))
                }
        except Exception as e:
            return {
                "endpoint": "/transcriptions",
                "status_code": None,
                "duration": None,
                "success": False,
                "error": str(e)
            }
    
    async def test_stats_endpoint(self) -> dict:
        """Testa endpoint de estatísticas"""
        try:
            start_time = time.time()
            async with self.session.get(f"{self.base_url}/stats") as response:
                duration = time.time() - start_time
                result = await response.json()
                return {
                    "endpoint": "/stats",
                    "status_code": response.status,
                    "duration": duration,
                    "success": response.status == 200,
                    "response": result
                }
        except Exception as e:
            return {
                "endpoint": "/stats",
                "status_code": None,
                "duration": None,
                "success": False,
                "error": str(e)
            }
    
    async def test_invalid_transcription_id(self) -> dict:
        """Testa busca por ID inexistente"""
        try:
            fake_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            start_time = time.time()
            async with self.session.get(f"{self.base_url}/transcriptions/{fake_id}") as response:
                duration = time.time() - start_time
                return {
                    "endpoint": f"/transcriptions/{fake_id}",
                    "status_code": response.status,
                    "duration": duration,
                    "success": response.status == 404,  # Esperamos 404
                    "expected_404": True
                }
        except Exception as e:
            return {
                "endpoint": "/transcriptions/fake_id",
                "status_code": None,
                "duration": None,
                "success": False,
                "error": str(e)
            }
    
    async def run_concurrent_tests(self, num_concurrent: int = 10) -> dict:
        """
        Executa múltiplos testes concorrentes
        """
        print(f"🚀 Executando {num_concurrent} requisições concorrentes...")
        
        # Cria lista de tasks para executar concorrentemente
        tasks = []
        
        # Mistura diferentes endpoints
        for i in range(num_concurrent):
            if i % 4 == 0:
                tasks.append(self.test_health_endpoint())
            elif i % 4 == 1:
                tasks.append(self.test_list_transcriptions())
            elif i % 4 == 2:
                tasks.append(self.test_stats_endpoint())
            else:
                tasks.append(self.test_invalid_transcription_id())
        
        # Executa todos concorrentemente
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - start_time
        
        # Analisa resultados
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success", False))
        failed = len(results) - successful
        
        avg_duration = sum(
            r.get("duration", 0) for r in results 
            if isinstance(r, dict) and r.get("duration") is not None
        ) / len(results)
        
        return {
            "total_requests": num_concurrent,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / num_concurrent * 100,
            "total_duration": total_duration,
            "average_request_duration": avg_duration,
            "requests_per_second": num_concurrent / total_duration,
            "results": results
        }


async def main():
    """
    Função principal de teste
    """
    print("🧪 Teste de Concorrência - Sistema de Transcrições PPT")
    print("=" * 60)
    
    async with ConcurrencyTester() as tester:
        # Teste 1: Verificação básica de conectividade
        print("\n📡 Teste 1: Verificação de conectividade...")
        health_result = await tester.test_health_endpoint()
        print(f"Health check: {'✅ OK' if health_result['success'] else '❌ FALHOU'}")
        print(f"Tempo de resposta: {health_result.get('duration', 0):.3f}s")
        
        # Teste 2: Concorrência baixa (5 requisições)
        print("\n🔄 Teste 2: Concorrência baixa (5 requisições)...")
        result_low = await tester.run_concurrent_tests(5)
        print(f"Sucessos: {result_low['successful']}/{result_low['total_requests']}")
        print(f"Taxa de sucesso: {result_low['success_rate']:.1f}%")
        print(f"Tempo total: {result_low['total_duration']:.3f}s")
        print(f"Req/s: {result_low['requests_per_second']:.2f}")
        
        # Teste 3: Concorrência média (15 requisições)
        print("\n⚡ Teste 3: Concorrência média (15 requisições)...")
        result_med = await tester.run_concurrent_tests(15)
        print(f"Sucessos: {result_med['successful']}/{result_med['total_requests']}")
        print(f"Taxa de sucesso: {result_med['success_rate']:.1f}%")
        print(f"Tempo total: {result_med['total_duration']:.3f}s")
        print(f"Req/s: {result_med['requests_per_second']:.2f}")
        
        # Teste 4: Concorrência alta (30 requisições)
        print("\n🚀 Teste 4: Concorrência alta (30 requisições)...")
        result_high = await tester.run_concurrent_tests(30)
        print(f"Sucessos: {result_high['successful']}/{result_high['total_requests']}")
        print(f"Taxa de sucesso: {result_high['success_rate']:.1f}%")
        print(f"Tempo total: {result_high['total_duration']:.3f}s")
        print(f"Req/s: {result_high['requests_per_second']:.2f}")
        
        # Análise dos resultados
        print("\n📊 Resumo dos Testes:")
        print("=" * 60)
        print(f"{'Teste':<20} {'Requisições':<12} {'Sucesso':<8} {'Req/s':<8} {'Duração':<8}")
        print("-" * 60)
        print(f"{'Baixa (5)':<20} {5:<12} {result_low['success_rate']:.1f}%{'':<5} {result_low['requests_per_second']:.2f}{'':<4} {result_low['total_duration']:.2f}s")
        print(f"{'Média (15)':<20} {15:<12} {result_med['success_rate']:.1f}%{'':<5} {result_med['requests_per_second']:.2f}{'':<4} {result_med['total_duration']:.2f}s")
        print(f"{'Alta (30)':<20} {30:<12} {result_high['success_rate']:.1f}%{'':<5} {result_high['requests_per_second']:.2f}{'':<4} {result_high['total_duration']:.2f}s")
        
        # Verifica se há problemas de concorrência
        if all(r['success_rate'] > 90 for r in [result_low, result_med, result_high]):
            print("\n✅ TESTE PASSOU: Sistema respondendo bem a requisições concorrentes!")
        elif any(r['success_rate'] < 50 for r in [result_low, result_med, result_high]):
            print("\n❌ TESTE FALHOU: Sistema com problemas sérios de concorrência!")
        else:
            print("\n⚠️  TESTE PARCIAL: Sistema funcionando mas pode precisar de ajustes.")
        
        # Detalhes de erros (se houver)
        all_results = result_low['results'] + result_med['results'] + result_high['results']
        errors = [r for r in all_results if isinstance(r, dict) and not r.get('success', False)]
        
        if errors:
            print(f"\n🔍 Detalhes dos erros ({len(errors)} total):")
            for error in errors[:5]:  # Mostra apenas os primeiros 5
                print(f"  - {error.get('endpoint', 'unknown')}: {error.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
