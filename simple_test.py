#!/usr/bin/env python3
"""
Teste simples de upload para debug
"""

import requests
import time

def test_upload():
    # URL do serviço
    base_url = "http://localhost:8001"
    
    # Arquivo de teste
    file_path = "/teamspace/studios/this_studio/sample_presentations/TheBridge_Precision_Play_Backlog Governance.pptx"
    
    print("🧪 Teste simples de upload")
    print("=" * 40)
    
    try:
        # Verifica se serviço está rodando
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Serviço está funcionando")
        else:
            print("❌ Serviço não está respondendo")
            return
        
        # Faz upload
        print("📤 Fazendo upload...")
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{base_url}/upload", files=files, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Upload bem-sucedido: {result['file_id']}")
            
            # Aguarda processamento
            transcription_id = result['file_id']
            print(f"⏳ Aguardando processamento de {transcription_id}...")
            
            for i in range(10):  # Aguarda até 50 segundos
                time.sleep(5)
                try:
                    status_response = requests.get(f"{base_url}/transcriptions/{transcription_id}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        print(f"📊 Status: {status_data.get('status', 'unknown')}")
                        
                        if status_data.get('status') in ['completed', 'failed']:
                            break
                    else:
                        print(f"⚠️  Status code: {status_response.status_code}")
                except Exception as e:
                    print(f"⚠️  Erro ao verificar status: {e}")
        else:
            print(f"❌ Erro no upload: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    test_upload()
