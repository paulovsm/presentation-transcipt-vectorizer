import logging
import uuid
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
import numpy as np
from sentence_transformers import SentenceTransformer

from ..config.settings import settings
from ..models.schemas import SearchQuery, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


class VectorStorageService:
    """
    Serviço para armazenamento vectorizado de apresentações usando ChromaDB
    """
    
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.chroma_db_path,
            settings=ChromaSettings(
                anonymized_telemetry=settings.anonymized_telemetry
            )
        )
        
        # Cria ou obtém coleção
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"description": "Apresentações PowerPoint/PDF processadas"}
        )
        
        # Inicializa modelo de embeddings
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        logger.info(f"VectorStorageService inicializado com coleção: {settings.chroma_collection_name}")
    
    async def add_document(
        self,
        text: str,
        metadata: Dict[str, Any],
        document_id: Optional[str] = None
    ) -> str:
        """
        Adiciona documento à base vectorizada
        """
        try:
            if not document_id:
                document_id = str(uuid.uuid4())
            
            # Garante que metadados são strings (requisito do ChromaDB)
            clean_metadata = self._clean_metadata(metadata)
            
            # Adiciona documento
            self.collection.add(
                documents=[text],
                metadatas=[clean_metadata],
                ids=[document_id]
            )
            
            logger.info(f"Documento adicionado à base vectorizada: {document_id}")
            return document_id
            
        except Exception as e:
            logger.error(f"Erro ao adicionar documento: {e}")
            raise
    
    async def add_documents_batch(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        document_ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Adiciona múltiplos documentos em lote
        """
        try:
            if not document_ids:
                document_ids = [str(uuid.uuid4()) for _ in texts]
            
            # Limpa metadados
            clean_metadatas = [self._clean_metadata(meta) for meta in metadatas]
            
            # Adiciona lote
            self.collection.add(
                documents=texts,
                metadatas=clean_metadatas,
                ids=document_ids
            )
            
            logger.info(f"Lote de {len(texts)} documentos adicionado à base vectorizada")
            return document_ids
            
        except Exception as e:
            logger.error(f"Erro ao adicionar lote de documentos: {e}")
            raise
    
    async def search(self, query: SearchQuery) -> SearchResponse:
        """
        Busca semântica na base vectorizada
        """
        try:
            start_time = self._get_current_time_ms()
            
            # Prepara filtros
            where_clause = None
            if query.filters:
                where_clause = self._build_where_clause(query.filters)
            
            # Executa busca
            results = self.collection.query(
                query_texts=[query.query],
                n_results=query.limit,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            # Processa resultados
            search_results = []
            
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 0.0
                    
                    # Converte distância para score (1 - distance para score positivo)
                    score = max(0.0, 1.0 - distance)
                    
                    # Filtra por threshold de similaridade
                    if score >= query.similarity_threshold:
                        search_result = SearchResult(
                            id=results["ids"][0][i],
                            text=doc,
                            score=score,
                            metadata=metadata if query.include_metadata else {},
                            transcription_id=metadata.get("transcription_id", ""),
                            slide_number=self._safe_int(metadata.get("slide_number")),
                            element_id=metadata.get("element_id")
                        )
                        search_results.append(search_result)
            
            end_time = self._get_current_time_ms()
            execution_time = end_time - start_time
            
            return SearchResponse(
                results=search_results,
                total_found=len(search_results),
                query=query.query,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            logger.error(f"Erro na busca vectorizada: {e}")
            raise
    
    async def delete_document(self, document_id: str) -> bool:
        """
        Remove documento específico
        """
        try:
            self.collection.delete(ids=[document_id])
            logger.info(f"Documento removido: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao remover documento: {e}")
            return False
    
    async def delete_documents_by_transcription_id(self, transcription_id: str) -> int:
        """
        Remove todos os documentos de uma transcrição
        """
        try:
            # Busca todos os documentos da transcrição
            results = self.collection.query(
                query_texts=["dummy"],  # Query fictícia
                n_results=1000,  # Limite alto para pegar todos
                where={"transcription_id": transcription_id},
                include=["metadatas"]
            )
            
            if results["ids"] and results["ids"][0]:
                ids_to_delete = results["ids"][0]
                self.collection.delete(ids=ids_to_delete)
                
                logger.info(f"Removidos {len(ids_to_delete)} documentos da transcrição {transcription_id}")
                return len(ids_to_delete)
            
            return 0
            
        except Exception as e:
            logger.error(f"Erro ao remover documentos da transcrição: {e}")
            return 0
    
    async def get_document_count(self) -> int:
        """
        Retorna número total de documentos na coleção
        """
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Erro ao contar documentos: {e}")
            return 0
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estatísticas da base vectorizada
        """
        try:
            total_docs = await self.get_document_count()
            
            # Busca estatísticas por tipo de conteúdo
            content_types = {}
            
            # Conta apresentações
            presentation_results = self.collection.query(
                query_texts=["dummy"],
                n_results=1000,
                where={"content_type": "presentation_summary"},
                include=["metadatas"]
            )
            content_types["presentations"] = len(presentation_results["ids"][0]) if presentation_results["ids"] else 0
            
            # Conta slides
            slide_results = self.collection.query(
                query_texts=["dummy"],
                n_results=1000,
                where={"content_type": "slide"},
                include=["metadatas"]
            )
            content_types["slides"] = len(slide_results["ids"][0]) if slide_results["ids"] else 0
            
            return {
                "total_documents": total_docs,
                "content_types": content_types,
                "collection_name": settings.chroma_collection_name
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {"error": str(e)}
    
    def _clean_metadata(self, metadata: Dict[str, Any]) -> Dict[str, str]:
        """
        Limpa metadados para compatibilidade com ChromaDB
        """
        clean_meta = {}
        
        for key, value in metadata.items():
            if value is not None:
                # ChromaDB aceita apenas strings, números, ou booleanos
                if isinstance(value, (str, int, float, bool)):
                    clean_meta[key] = str(value)
                elif isinstance(value, list):
                    # Converte listas para strings JSON
                    import json
                    clean_meta[key] = json.dumps(value, ensure_ascii=False)
                else:
                    clean_meta[key] = str(value)
        
        return clean_meta
    
    def _build_where_clause(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Constrói cláusula WHERE para filtros
        """
        where_clause = {}
        
        for key, value in filters.items():
            if value is not None:
                where_clause[key] = str(value)
        
        return where_clause
    
    def _safe_int(self, value: Any) -> Optional[int]:
        """
        Converte valor para int de forma segura
        """
        try:
            return int(value) if value is not None else None
        except (ValueError, TypeError):
            return None
    
    def _get_current_time_ms(self) -> float:
        """
        Retorna tempo atual em milissegundos
        """
        import time
        return time.time() * 1000
    
    async def search_similar_presentations(
        self,
        transcription_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Busca apresentações similares baseadas no conteúdo
        """
        try:
            # Primeiro, busca o resumo da apresentação atual
            current_results = self.collection.query(
                query_texts=["dummy"],
                n_results=1,
                where={
                    "transcription_id": transcription_id,
                    "content_type": "presentation_summary"
                },
                include=["documents", "metadatas"]
            )
            
            if not current_results["documents"] or not current_results["documents"][0]:
                return []
            
            current_summary = current_results["documents"][0][0]
            
            # Busca apresentações similares
            similar_results = self.collection.query(
                query_texts=[current_summary],
                n_results=limit + 1,  # +1 para excluir a própria apresentação
                where={"content_type": "presentation_summary"},
                include=["documents", "metadatas", "distances"]
            )
            
            # Filtra a apresentação atual dos resultados
            filtered_results = []
            
            if similar_results["documents"] and similar_results["documents"][0]:
                for i, doc in enumerate(similar_results["documents"][0]):
                    metadata = similar_results["metadatas"][0][i]
                    
                    # Exclui a apresentação atual
                    if metadata.get("transcription_id") != transcription_id:
                        distance = similar_results["distances"][0][i]
                        score = max(0.0, 1.0 - distance)
                        
                        filtered_results.append({
                            "transcription_id": metadata.get("transcription_id"),
                            "title": metadata.get("title", ""),
                            "author": metadata.get("author", ""),
                            "presentation_type": metadata.get("presentation_type", ""),
                            "similarity_score": score,
                            "summary_preview": doc[:200] + "..." if len(doc) > 200 else doc
                        })
            
            return filtered_results[:limit]
            
        except Exception as e:
            logger.error(f"Erro ao buscar apresentações similares: {e}")
            return []
