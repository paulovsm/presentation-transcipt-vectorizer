import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from google.oauth2 import service_account

from ..config.settings import settings
from ..models.schemas import (
    TranscriptionStatus, ProcessingStatus, PresentationTranscription,
    TranscriptionResponse
)

logger = logging.getLogger(__name__)


class FirestoreService:
    """
    Serviço para gerenciar dados de apresentações no Cloud Firestore
    """
    
    def __init__(self):
        # Configurar autenticação explicitamente
        if settings.google_application_credentials and os.path.exists(settings.google_application_credentials):
            # Usar service account com escopo específico
            credentials = service_account.Credentials.from_service_account_file(
                settings.google_application_credentials,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            self.db = firestore.Client(project=settings.google_cloud_project, credentials=credentials)
            logger.info(f"Firestore inicializado com service account: {settings.google_application_credentials}")
        else:
            # Fallback para credenciais padrão
            self.db = firestore.Client(project=settings.google_cloud_project)
            logger.info("Firestore inicializado com credenciais padrão")
            
        self.collection_name = "presentation_transcriptions"
    
    async def create_presentation_record(
        self,
        transcription_id: str,
        file_name: str,
        presentation_title: Optional[str] = None,
        presentation_date: Optional[datetime] = None,
        author: Optional[str] = None,
        presentation_type: Optional[str] = None,
        language_code: str = "pt-BR",
        status: TranscriptionStatus = TranscriptionStatus.PENDING,
        # Novos campos
        workstream: Optional[str] = None,
        bpml_l1: Optional[str] = None,
        bpml_l2: Optional[str] = None
    ) -> None:
        """
        Cria registro inicial da apresentação no Firestore
        """
        try:
            doc_data = {
                "transcription_id": transcription_id,
                "file_name": file_name,
                "presentation_title": presentation_title,
                "presentation_date": presentation_date or datetime.utcnow(),
                "author": author,
                "presentation_type": presentation_type,
                "language_code": language_code,
                "status": status.value,
                "processing_status": ProcessingStatus.PENDING.value,
                # Novos campos
                "workstream": workstream,
                "bpml_l1": bpml_l1,
                "bpml_l2": bpml_l2,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "slides_count": None,
                "processing_time_seconds": None,
                "error_message": None
            }
            
            doc_ref = self.db.collection(self.collection_name).document(transcription_id)
            doc_ref.set(doc_data)
            
            logger.info(f"Registro de apresentação criado: {transcription_id}")
            
        except Exception as e:
            logger.error(f"Erro ao criar registro no Firestore: {e}")
            raise
    
    async def update_transcription_status(
        self,
        transcription_id: str,
        status: TranscriptionStatus,
        error_message: Optional[str] = None
    ) -> None:
        """
        Atualiza status da transcrição
        """
        try:
            doc_ref = self.db.collection(self.collection_name).document(transcription_id)
            
            update_data = {
                "status": status.value,
                "updated_at": datetime.utcnow()
            }
            
            if error_message:
                update_data["error_message"] = error_message
            
            doc_ref.update(update_data)
            
            logger.info(f"Status atualizado para {status.value}: {transcription_id}")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar status: {e}")
            raise
    
    async def update_processing_status(
        self,
        transcription_id: str,
        processing_status: ProcessingStatus
    ) -> None:
        """
        Atualiza status de processamento
        """
        try:
            doc_ref = self.db.collection(self.collection_name).document(transcription_id)
            
            doc_ref.update({
                "processing_status": processing_status.value,
                "updated_at": datetime.utcnow()
            })
            
            logger.info(f"Status de processamento atualizado para {processing_status.value}: {transcription_id}")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar status de processamento: {e}")
            raise
    
    async def update_transcription_completion(
        self,
        transcription_id: str,
        transcription: PresentationTranscription,
        processing_time: float,
        status: TranscriptionStatus = TranscriptionStatus.COMPLETED
    ) -> None:
        """
        Atualiza transcrição com dados completos
        """
        try:
            doc_ref = self.db.collection(self.collection_name).document(transcription_id)
            
            # Converte para dict serializable
            transcription_dict = self._serialize_transcription(transcription)
            
            update_data = {
                "status": status.value,
                "processing_status": ProcessingStatus.COMPLETED.value,
                "slides_count": len(transcription.slides),
                "processing_time_seconds": processing_time,
                "transcription": transcription_dict,
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            doc_ref.update(update_data)
            
            logger.info(f"Transcrição completa salva: {transcription_id}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar transcrição completa: {e}")
            raise
    
    async def get_transcription(self, transcription_id: str) -> Optional[TranscriptionResponse]:
        """
        Recupera transcrição por ID
        """
        try:
            doc_ref = self.db.collection(self.collection_name).document(transcription_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            
            # Converte para objeto de resposta
            return self._dict_to_transcription_response(data)
            
        except Exception as e:
            logger.error(f"Erro ao recuperar transcrição: {e}")
            raise
    
    async def list_transcriptions(
        self,
        limit: int = 10,
        status_filter: Optional[TranscriptionStatus] = None
    ) -> List[Dict[str, Any]]:
        """
        Lista transcrições com filtros
        """
        try:
            query = self.db.collection(self.collection_name)
            
            if status_filter:
                query = query.where(
                    filter=FieldFilter("status", "==", status_filter.value)
                )
            
            query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
            query = query.limit(limit)
            
            docs = query.stream()
            
            transcriptions = []
            for doc in docs:
                data = doc.to_dict()
                # Remove dados pesados para listagem
                if "transcription" in data:
                    del data["transcription"]
                transcriptions.append(data)
            
            return transcriptions
            
        except Exception as e:
            logger.error(f"Erro ao listar transcrições: {e}")
            raise
    
    async def delete_transcription(self, transcription_id: str) -> bool:
        """
        Remove transcrição do Firestore
        """
        try:
            doc_ref = self.db.collection(self.collection_name).document(transcription_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return False
            
            doc_ref.delete()
            logger.info(f"Transcrição deletada: {transcription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao deletar transcrição: {e}")
            return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do sistema
        """
        try:
            collection_ref = self.db.collection(self.collection_name)
            
            # Conta total de documentos
            docs = collection_ref.stream()
            total_count = sum(1 for _ in docs)
            
            # Conta por status
            status_counts = {}
            for status in TranscriptionStatus:
                query = collection_ref.where(
                    filter=FieldFilter("status", "==", status.value)
                )
                count = sum(1 for _ in query.stream())
                status_counts[status.value] = count
            
            # Estatísticas de processamento (últimos 30 dias)
            from datetime import timedelta
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            recent_query = collection_ref.where(
                filter=FieldFilter("created_at", ">=", thirty_days_ago)
            )
            recent_docs = list(recent_query.stream())
            
            total_processing_time = 0
            processed_count = 0
            
            for doc in recent_docs:
                data = doc.to_dict()
                if data.get("processing_time_seconds"):
                    total_processing_time += data["processing_time_seconds"]
                    processed_count += 1
            
            avg_processing_time = (
                total_processing_time / processed_count 
                if processed_count > 0 else 0
            )
            
            return {
                "total_presentations": total_count,
                "status_breakdown": status_counts,
                "recent_30_days": len(recent_docs),
                "average_processing_time_seconds": avg_processing_time,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {"error": str(e)}
    
    def _serialize_transcription(self, transcription: PresentationTranscription) -> Dict[str, Any]:
        """
        Serializa transcrição para armazenamento no Firestore
        """
        return {
            "presentation_metadata": {
                "title": transcription.presentation_metadata.title,
                "author": transcription.presentation_metadata.author,
                "date": transcription.presentation_metadata.date,
                "source_filename": transcription.presentation_metadata.source_filename,
                "total_slides": transcription.presentation_metadata.total_slides,
                "presentation_type": transcription.presentation_metadata.presentation_type,
                "language": transcription.presentation_metadata.language
            },
            "overall_summary": transcription.overall_summary,
            "key_concepts": transcription.key_concepts,
            "narrative_flow_analysis": transcription.narrative_flow_analysis,
            "slides": [
                {
                    "slide_number": slide.slide_number,
                    "slide_title": slide.slide_title,
                    "slide_summary": slide.slide_summary,
                    "elements": [
                        {
                            "element_id": elem.element_id,
                            "element_type": elem.element_type,
                            "raw_content": elem.raw_content,
                            "semantic_analysis": elem.semantic_analysis,
                            "relationships_to_other_elements": elem.relationships_to_other_elements
                        } for elem in slide.elements
                    ]
                } for slide in transcription.slides
            ]
        }
    
    def _dict_to_transcription_response(self, data: Dict[str, Any]) -> TranscriptionResponse:
        """
        Converte dict do Firestore para TranscriptionResponse
        """
        transcription = None
        if data.get("transcription"):
            transcription_data = data["transcription"]
            
            # Reconstrói objeto de transcrição (simplificado)
            transcription = transcription_data  # Por enquanto retorna dict
        
        return TranscriptionResponse(
            id=data["transcription_id"],
            status=TranscriptionStatus(data["status"]),
            file_name=data["file_name"],
            slides_count=data.get("slides_count"),
            transcription=transcription,  # Será dict por enquanto
            created_at=data["created_at"],
            completed_at=data.get("completed_at"),
            error_message=data.get("error_message"),
            processing_time_seconds=data.get("processing_time_seconds")
        )
