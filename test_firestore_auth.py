#!/usr/bin/env python3
"""
Script para testar autenticação e conectividade com Firestore
"""

import os
import sys
import json
from google.cloud import firestore
from google.oauth2 import service_account

# Configurar variáveis de ambiente
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/teamspace/studios/this_studio/transcription-service-key.json'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'sap-accelerate'

def test_firestore_connection():
    """Testa conectividade com Firestore"""
    print("🔍 Testando conectividade com Firestore...")
    
    try:
        # Método 1: Usando credenciais padrão
        print("\n1️⃣ Testando com credenciais padrão...")
        client = firestore.Client(project='sap-accelerate')
        
        # Tenta fazer uma operação simples
        collection_ref = client.collection('test_connection')
        
        # Escreve documento de teste
        doc_ref = collection_ref.document('test_doc')
        doc_ref.set({
            'test': True,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        print("✅ Escrita bem-sucedida")
        
        # Lê documento de teste
        doc = doc_ref.get()
        if doc.exists:
            print("✅ Leitura bem-sucedida:", doc.to_dict())
        
        # Remove documento de teste
        doc_ref.delete()
        print("✅ Remoção bem-sucedida")
        
        print("✅ Conexão com Firestore está funcionando!")
        return True
        
    except Exception as e:
        print(f"❌ Erro com credenciais padrão: {e}")
        
        # Método 2: Usando service account explícito
        try:
            print("\n2️⃣ Testando com service account explícito...")
            
            # Carrega credenciais do arquivo JSON
            credentials = service_account.Credentials.from_service_account_file(
                '/teamspace/studios/this_studio/transcription-service-key.json',
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            client = firestore.Client(project='sap-accelerate', credentials=credentials)
            
            # Testa operação
            collection_ref = client.collection('test_connection')
            doc_ref = collection_ref.document('test_doc')
            doc_ref.set({
                'test': True,
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            print("✅ Escrita bem-sucedida com service account")
            
            # Lê e remove
            doc = doc_ref.get()
            if doc.exists:
                print("✅ Leitura bem-sucedida:", doc.to_dict())
            doc_ref.delete()
            print("✅ Remoção bem-sucedida")
            
            print("✅ Conexão com service account está funcionando!")
            return True
            
        except Exception as e2:
            print(f"❌ Erro com service account explícito: {e2}")
            return False

def check_service_account_info():
    """Verifica informações da conta de serviço"""
    print("\n🔑 Verificando informações da conta de serviço...")
    
    try:
        with open('/teamspace/studios/this_studio/transcription-service-key.json', 'r') as f:
            key_data = json.load(f)
            
        print(f"📧 Client Email: {key_data.get('client_email')}")
        print(f"🆔 Project ID: {key_data.get('project_id')}")
        print(f"🔐 Private Key ID: {key_data.get('private_key_id')}")
        print(f"🔑 Type: {key_data.get('type')}")
        
        # Verifica se tem todas as chaves necessárias
        required_keys = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email', 'client_id', 'auth_uri', 'token_uri']
        missing_keys = [key for key in required_keys if key not in key_data]
        
        if missing_keys:
            print(f"❌ Chaves ausentes: {missing_keys}")
        else:
            print("✅ Todas as chaves necessárias estão presentes")
            
    except Exception as e:
        print(f"❌ Erro ao verificar credenciais: {e}")

def test_environment_variables():
    """Testa variáveis de ambiente"""
    print("\n🌍 Verificando variáveis de ambiente...")
    
    google_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    google_project = os.getenv('GOOGLE_CLOUD_PROJECT')
    
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {google_creds}")
    print(f"GOOGLE_CLOUD_PROJECT: {google_project}")
    
    if google_creds and os.path.exists(google_creds):
        print("✅ Arquivo de credenciais existe")
    else:
        print("❌ Arquivo de credenciais não encontrado")
        
    if google_project:
        print("✅ Projeto configurado")
    else:
        print("❌ Projeto não configurado")

if __name__ == "__main__":
    print("🧪 Testando Autenticação Google Cloud Firestore")
    print("=" * 50)
    
    test_environment_variables()
    check_service_account_info()
    
    if test_firestore_connection():
        print("\n🎉 Teste de conectividade bem-sucedido!")
        sys.exit(0)
    else:
        print("\n💥 Teste de conectividade falhou!")
        sys.exit(1)
