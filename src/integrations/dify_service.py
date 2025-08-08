import logging
import httpx
from typing import Dict, Any, Optional, List
import json
from datetime import datetime

from ..config.settings import settings
from ..models.schemas import (
    DifyIntegrationRequest, DifyIntegrationResponse,
    DifyDatasetRequest, DifyDatasetResponse,
    DifySearchRequest
)

logger = logging.getLogger(__name__)


class DifyIntegrationService:
    """
    Serviço para integração com Dify.ai
    """
    
    def __init__(self):
        self.base_url = settings.dify_api_url
        self.api_key = settings.dify_api_key
        self.default_dataset_id = settings.dify_dataset_id
        self.workflow_api_key = settings.dify_workflow_api_key
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def upload_document(
        self,
        content: str,
        document_name: str,
        metadata: Dict[str, Any],
        dataset_name: Optional[str] = None,
        dataset_id: Optional[str] = None
    ) -> DifyIntegrationResponse:
        """
        Faz upload de documento para o Dify.ai e atribui metadados
        """
        try:
            target_dataset_id = dataset_id or self.default_dataset_id
            
            # Se foi especificado um nome de dataset, tenta encontrar ou criar
            if dataset_name:
                target_dataset_id = await self._get_or_create_dataset_by_name(dataset_name)
            
            # Primeiro, cria o documento sem metadados
            document_data = {
                "name": document_name,
                "text": content,
                "indexing_technique": "high_quality",
                "process_rule": {
                    "mode": "automatic",
                    "rules": {
                        "pre_processing_rules": [
                            {"id": "remove_extra_spaces", "enabled": True},
                            {"id": "remove_urls_emails", "enabled": False}
                        ],
                        "segmentation": {
                            "separator": "\\n\\n",
                            "max_tokens": 1000
                        }
                    }
                }
            }
            
            logger.info(f"Enviando documento para Dify: {document_name} (dataset: {target_dataset_id})")
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Cria o documento
                response = await client.post(
                    f"{self.base_url}/datasets/{target_dataset_id}/document/create_by_text",
                    headers=self.headers,
                    json=document_data
                )
                
                if response.status_code != 200:
                    logger.error(f"Erro ao enviar documento para Dify: {response.status_code} - {response.text}")
                    return DifyIntegrationResponse(
                        success=False,
                        message=f"Erro ao enviar documento: {response.status_code}",
                        error=response.text
                    )
                
                result = response.json()
                document_id = result.get("document", {}).get("id")
                
                if not document_id:
                    logger.error("Document ID não retornado na resposta do Dify")
                    return DifyIntegrationResponse(
                        success=False,
                        message="Document ID não encontrado na resposta",
                        error="Resposta inválida da API"
                    )
                
                # Se há metadados, primeiro garante que os campos existem no dataset
                if metadata:
                    await self._ensure_metadata_fields_exist(target_dataset_id, metadata)
                    
                    # Depois atribui os metadados ao documento
                    metadata_success = await self._assign_metadata_to_document(
                        target_dataset_id, document_id, metadata
                    )
                    
                    if metadata_success:
                        logger.info(f"Metadados atribuídos com sucesso ao documento {document_id}")
                    else:
                        logger.warning(f"Falha ao atribuir metadados ao documento {document_id}")
                
                return DifyIntegrationResponse(
                    success=True,
                    document_id=document_id,
                    dataset_id=target_dataset_id,
                    message="Documento enviado com sucesso para Dify.ai"
                )
                    
        except Exception as e:
            logger.error(f"Erro na integração com Dify: {e}")
            return DifyIntegrationResponse(
                success=False,
                message="Erro na integração com Dify.ai",
                error=str(e)
            )
    
    async def create_dataset(
        self,
        name: str,
        description: Optional[str] = None
    ) -> DifyDatasetResponse:
        """
        Cria novo dataset no Dify.ai
        """
        try:
            dataset_data = {
                "name": name,
                "description": description or f"Dataset criado em {datetime.utcnow().isoformat()}",
                "permission": "only_me",
                "provider": "vendor",
                "indexing_technique": "high_quality"
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/datasets",
                    headers=self.headers,
                    json=dataset_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    return DifyDatasetResponse(
                        id=result["id"],
                        name=result["name"],
                        description=result.get("description"),
                        permission=result.get("permission", "only_me"),
                        document_count=result.get("document_count", 0),
                        word_count=result.get("word_count", 0),
                        created_at=datetime.utcnow()
                    )
                else:
                    logger.error(f"Erro ao criar dataset no Dify: {response.status_code} - {response.text}")
                    raise Exception(f"Erro ao criar dataset: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Erro ao criar dataset: {e}")
            raise
    
    async def list_datasets(self) -> Dict[str, Any]:
        """
        Lista todos os datasets disponíveis
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.base_url}/datasets",
                    headers=self.headers,
                    params={"page": 1, "limit": 100}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Erro ao listar datasets: {response.status_code} - {response.text}")
                    return {"data": [], "total": 0}
                    
        except Exception as e:
            logger.error(f"Erro ao listar datasets: {e}")
            return {"data": [], "total": 0, "error": str(e)}
    
    async def search_documents(
        self,
        request: DifySearchRequest
    ) -> Dict[str, Any]:
        """
        Busca documentos no Dify.ai
        """
        try:
            search_data = {
                "query": request.query,
                "retrieval_model": {
                    "search_method": "semantic_search",
                    "reranking_enable": True,
                    "reranking_model": {
                        "reranking_provider_name": "jina",
                        "reranking_model_name": "jina-reranker-v1-base-en"
                    },
                    "top_k": request.limit,
                    "score_threshold_enabled": True,
                    "score_threshold": request.similarity_threshold
                }
            }
            
            dataset_id = request.dataset_id or self.default_dataset_id
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/datasets/{dataset_id}/retrieve",
                    headers=self.headers,
                    json=search_data
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Erro na busca Dify: {response.status_code} - {response.text}")
                    return {"query": request.query, "retrieval_docs": []}
                    
        except Exception as e:
            logger.error(f"Erro na busca Dify: {e}")
            return {"query": request.query, "retrieval_docs": [], "error": str(e)}
    
    async def generate_presentation_analysis(
        self,
        presentation_content: str,
        analysis_type: str,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gera análise de apresentação usando workflow do Dify
        """
        try:
            # Prepara dados para o workflow
            workflow_data = {
                "inputs": {
                    "presentation_content": presentation_content,
                    "analysis_type": analysis_type,
                    "custom_prompt": custom_prompt or ""
                },
                "response_mode": "blocking",
                "user": "presentation-service"
            }
            
            # Headers específicos para workflow
            workflow_headers = {
                "Authorization": f"Bearer {self.workflow_api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/workflows/run",
                    headers=workflow_headers,
                    json=workflow_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    return {
                        "success": True,
                        "analysis": result.get("data", {}).get("outputs", {}).get("analysis", ""),
                        "workflow_id": result.get("workflow_id"),
                        "task_id": result.get("task_id"),
                        "message": "Análise gerada com sucesso"
                    }
                else:
                    logger.error(f"Erro no workflow Dify: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "message": f"Erro no workflow: {response.status_code}",
                        "error": response.text
                    }
                    
        except Exception as e:
            logger.error(f"Erro no workflow de análise: {e}")
            return {
                "success": False,
                "message": "Erro no workflow de análise",
                "error": str(e)
            }
    
    async def _get_or_create_dataset_by_name(self, dataset_name: str) -> str:
        """
        Busca dataset por nome ou cria se não existir
        """
        try:
            # Lista datasets existentes
            datasets_response = await self.list_datasets()
            
            # Procura por dataset com o nome especificado
            for dataset in datasets_response.get("data", []):
                if dataset.get("name") == dataset_name:
                    return dataset["id"]
            
            # Se não encontrar, cria novo dataset
            logger.info(f"Dataset '{dataset_name}' não encontrado, criando novo...")
            new_dataset = await self.create_dataset(
                name=dataset_name,
                description=f"Dataset auto-criado para apresentações - {dataset_name}"
            )
            
            return new_dataset.id
            
        except Exception as e:
            logger.error(f"Erro ao buscar/criar dataset: {e}")
            # Retorna dataset padrão em caso de erro
            return self.default_dataset_id
    
    async def get_dataset_info(self, dataset_id: str) -> Dict[str, Any]:
        """
        Obtém informações detalhadas de um dataset
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.base_url}/datasets/{dataset_id}",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Erro ao obter info do dataset: {response.status_code}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Erro ao obter info do dataset: {e}")
            return {}
    
    async def delete_document(self, dataset_id: str, document_id: str) -> bool:
        """
        Remove documento do Dify.ai
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.delete(
                    f"{self.base_url}/datasets/{dataset_id}/documents/{document_id}",
                    headers=self.headers
                )
                
                return response.status_code == 204
                
        except Exception as e:
            logger.error(f"Erro ao deletar documento do Dify: {e}")
            return False
    
    async def update_document(
        self,
        dataset_id: str,
        document_id: str,
        content: str,
        document_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Atualiza documento no Dify.ai
        """
        try:
            update_data = {
                "name": document_name,
                "text": content,
                "process_rule": {
                    "mode": "automatic",
                    "rules": {
                        "pre_processing_rules": [
                            {"id": "remove_extra_spaces", "enabled": True},
                            {"id": "remove_urls_emails", "enabled": False}
                        ],
                        "segmentation": {
                            "separator": "\\n\\n",
                            "max_tokens": 1000
                        }
                    }
                }
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/datasets/{dataset_id}/documents/{document_id}/update_by_text",
                    headers=self.headers,
                    json=update_data
                )
                
                success = response.status_code == 200
                
                # Se houve sucesso na atualização e há metadados, atribui eles
                if success and metadata:
                    await self._ensure_metadata_fields_exist(dataset_id, metadata)
                    await self._assign_metadata_to_document(dataset_id, document_id, metadata)
                
                return success
                
        except Exception as e:
            logger.error(f"Erro ao atualizar documento no Dify: {e}")
            return False

    async def _ensure_metadata_fields_exist(self, dataset_id: str, metadata: Dict[str, Any]):
        """
        Garante que todos os campos de metadados existem no dataset
        """
        try:
            # Primeiro, obtém os campos existentes
            existing_fields = await self._get_existing_metadata_fields(dataset_id)
            existing_field_names = {field.get("name") for field in existing_fields}
            
            # Cria campos que não existem
            async with httpx.AsyncClient(timeout=60.0) as client:
                for field_name, field_value in metadata.items():
                    if field_name not in existing_field_names:
                        # Determina o tipo do campo baseado no valor
                        field_type = self._determine_field_type(field_value)
                        
                        field_data = {
                            "type": field_type,
                            "name": field_name
                        }
                        
                        response = await client.post(
                            f"{self.base_url}/datasets/{dataset_id}/metadata",
                            headers=self.headers,
                            json=field_data
                        )
                        
                        if response.status_code in [200, 201]:  # 200 OK ou 201 CREATED
                            logger.info(f"Campo de metadado criado com sucesso: {field_name} ({field_type})")
                        else:
                            logger.warning(f"Falha ao criar campo {field_name}: {response.status_code} - {response.text}")
                            
        except Exception as e:
            logger.error(f"Erro ao garantir campos de metadados: {e}")

    async def _get_existing_metadata_fields(self, dataset_id: str) -> List[Dict]:
        """
        Obtém a lista de campos de metadados existentes no dataset
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.base_url}/datasets/{dataset_id}/metadata",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("doc_metadata", [])
                else:
                    logger.warning(f"Falha ao obter campos de metadados: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Erro ao obter campos de metadados: {e}")
            return []

    def _determine_field_type(self, value: Any) -> str:
        """
        Determina o tipo do campo de metadado baseado no valor
        """
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "number"
        elif isinstance(value, float):
            return "number"
        else:
            return "string"

    async def _assign_metadata_to_document(self, dataset_id: str, document_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Atribui metadados a um documento específico
        """
        try:
            # Primeiro, obtém os campos de metadados para pegar os IDs
            existing_fields = await self._get_existing_metadata_fields(dataset_id)
            field_map = {field.get("name"): field.get("id") for field in existing_fields}
            
            # Prepara lista de metadados com IDs
            metadata_list = []
            for field_name, field_value in metadata.items():
                field_id = field_map.get(field_name)
                if field_id:
                    metadata_list.append({
                        "id": field_id,
                        "name": field_name,
                        "value": str(field_value)  # Converte para string conforme esperado pela API
                    })
                else:
                    logger.warning(f"Campo de metadado não encontrado: {field_name}")
            
            if not metadata_list:
                logger.warning("Nenhum metadado válido para atribuir")
                return False
            
            operation_data = {
                "operation_data": [
                    {
                        "document_id": document_id,
                        "metadata_list": metadata_list
                    }
                ]
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/datasets/{dataset_id}/documents/metadata",
                    headers=self.headers,
                    json=operation_data
                )
                
                if response.status_code == 200:
                    logger.info(f"Metadados atribuídos com sucesso ao documento {document_id}")
                    return True
                else:
                    logger.error(f"Falha ao atribuir metadados: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Erro ao atribuir metadados ao documento: {e}")
            return False
