import os
import uuid
import aiofiles
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
import json

from ..config.settings import settings
from ..models.schemas import (
    TranscriptionRequest, TranscriptionResponse, TranscriptionStatus,
    ProcessedPresentation, ProcessingStatus, SearchQuery, SearchResponse,
    PresentationTranscription, PresentationMetadata, SlideData,
    DifySearchRequest, PresentationAnalysisRequest, PresentationAnalysisResponse
)
from ..processing.slide_extraction import SlideExtractionService
from ..processing.gemini_service import GeminiPresentationService
from ..storage.vector_service import VectorStorageService
from ..storage.firestore_service import FirestoreService
from ..integrations.dify_service import DifyIntegrationService

logger = logging.getLogger(__name__)


class PresentationOrchestrator:
    """
    Orquestrador principal para processamento de apresentações
    """
    
    def __init__(self):
        self.slide_extractor = SlideExtractionService()
        self.gemini_service = GeminiPresentationService()
        self.vector_service = VectorStorageService()
        self.firestore_service = FirestoreService()
        self.dify_service = DifyIntegrationService()
    
    async def process_presentation_file(
        self,
        file_path: str,
        request: TranscriptionRequest,
        dataset_name: Optional[str] = None,
        transcription_id: Optional[str] = None
    ) -> TranscriptionResponse:
        """
        Processa um arquivo de apresentação através de todo o pipeline
        """
        if transcription_id is None:
            transcription_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Iniciando processamento da apresentação: {request.file_name}")
            
            # 1. Cria registro inicial no Firestore
            await self.firestore_service.create_presentation_record(
                transcription_id=transcription_id,
                file_name=request.file_name,
                presentation_title=request.file_name,  # Usa file_name como título
                presentation_date=request.presentation_date or datetime.utcnow(),
                author=request.author,
                presentation_type=request.presentation_type,
                language_code=request.language_code,
                status=TranscriptionStatus.PROCESSING,
                # Novos campos
                workstream=request.workstream,
                bpml_l1=request.bpml_l1,
                bpml_l2=request.bpml_l2
            )
            
            # 2. Extração de slides
            logger.info("Extraindo slides da apresentação...")
            await self.firestore_service.update_processing_status(
                transcription_id, ProcessingStatus.EXTRACTING_SLIDES
            )
            
            extraction_result = await self.slide_extractor.extract_slides_from_file(file_path)
            slides_data = extraction_result["slides_data"]
            presentation_metadata = extraction_result["metadata"]
            
            logger.info(f"Extraídos {len(slides_data)} slides")
            
            # 3. Análise global com Gemini
            logger.info("Executando análise global com Gemini...")
            global_analysis = await self.gemini_service.process_presentation_global(
                slides_data, presentation_metadata
            )
            
            # 4. Processamento detalhado de slides
            logger.info("Processando slides individualmente...")
            await self.firestore_service.update_processing_status(
                transcription_id, ProcessingStatus.PROCESSING_SLIDES
            )
            
            processed_slides = []
            
            # Processa slides em lotes para otimizar
            batch_size = settings.slides_per_chunk
            for i in range(0, len(slides_data), batch_size):
                batch = slides_data[i:i + batch_size]
                
                # Processa lote de slides
                batch_results = await self._process_slides_batch(
                    batch, global_analysis, request.detailed_analysis
                )
                processed_slides.extend(batch_results)
                
                logger.info(f"Processados {len(processed_slides)}/{len(slides_data)} slides")
            
            # 5. Gera resumo executivo
            logger.info("Gerando resumo executivo...")
            await self.firestore_service.update_processing_status(
                transcription_id, ProcessingStatus.GENERATING_SUMMARY
            )
            
            executive_summary = await self.gemini_service.generate_presentation_summary(
                processed_slides, global_analysis
            )
            
            # 6. Constrói objeto de transcrição final
            presentation_transcription = PresentationTranscription(
                presentation_metadata=PresentationMetadata(
                    title=request.file_name,  # Usa o nome do arquivo como título
                    author=presentation_metadata.get("author", request.author),
                    date=request.presentation_date or datetime.utcnow(),
                    source_filename=request.file_name,
                    total_slides=len(processed_slides),
                    presentation_type=global_analysis.get("presentation_type", request.presentation_type),
                    language=request.language_code
                ),
                overall_summary=global_analysis.get("overall_summary", ""),
                key_concepts=global_analysis.get("key_concepts", []),
                narrative_flow_analysis=global_analysis.get("narrative_flow_analysis", ""),
                slides=processed_slides
            )
            
            # 7. Armazenamento vectorizado
            # logger.info("Armazenando em base vectorizada...")
            # await self._store_in_vector_database(transcription_id, presentation_transcription)
            
            # 8. Integração com Dify (usa dataset_name se fornecido; caso contrário usa dataset padrão)
            try:
                if settings.dify_api_key and settings.dify_dataset_id:
                    logger.info(
                        "Integrando com Dify.ai... (dataset=%s)",
                        dataset_name or settings.dify_dataset_id
                    )
                    await self._integrate_with_dify(
                        transcription_id,
                        presentation_transcription,
                        dataset_name  # None => serviço usará default_dataset_id
                    )
                else:
                    logger.debug(
                        "Integração Dify não configurada (faltando API key ou dataset id). Pulando esta etapa."
                    )
            except Exception as e:
                # Não interrompe processamento principal
                logger.error(f"Falha na integração com Dify: {e}")
            
            # 9. Atualiza status final
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            await self.firestore_service.update_transcription_completion(
                transcription_id=transcription_id,
                transcription=presentation_transcription,
                processing_time=processing_time,
                status=TranscriptionStatus.COMPLETED
            )
            
            # 10. Limpeza de arquivos temporários
            await self._cleanup_temp_files(slides_data)
            
            logger.info(f"Processamento concluído em {processing_time:.2f} segundos")
            
            return TranscriptionResponse(
                id=transcription_id,
                status=TranscriptionStatus.COMPLETED,
                file_name=request.file_name,
                slides_count=len(processed_slides),
                transcription=presentation_transcription,
                created_at=start_time,
                completed_at=datetime.utcnow(),
                processing_time_seconds=processing_time
            )
            
        except Exception as e:
            logger.error(f"Erro no processamento da apresentação: {e}")
            
            # Atualiza status de erro
            await self.firestore_service.update_transcription_status(
                transcription_id,
                TranscriptionStatus.FAILED,
                error_message=str(e)
            )
            
            # Limpeza em caso de erro
            try:
                await self._cleanup_temp_files(slides_data if 'slides_data' in locals() else [])
            except:
                pass
            
            return TranscriptionResponse(
                id=transcription_id,
                status=TranscriptionStatus.FAILED,
                file_name=request.file_name,
                created_at=start_time,
                error_message=str(e)
            )
    
    async def _process_slides_batch(
        self, 
        slides_batch: List[Dict], 
        global_context: Dict, 
        detailed_analysis: bool
    ) -> List[SlideData]:
        """
        Processa um lote de slides em paralelo usando análise visual
        """
        import asyncio
        
        tasks = []
        for slide_data in slides_batch:
            # Usa a imagem base64 já preparada
            image_base64 = slide_data.get("image_base64")
            
            if not image_base64 and slide_data.get("image_path"):
                # Fallback: converte se necessário
                image_base64 = await self.slide_extractor.convert_image_to_base64(
                    slide_data["image_path"]
                )
            
            # Cria task para processamento com foco na análise visual
            task = self.gemini_service.process_slide_detailed(
                slide_data, image_base64, global_context
            )
            tasks.append(task)
        
        # Executa em paralelo (limitado para não sobrecarregar API)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filtra resultados válidos
        processed_slides = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Erro ao processar slide {slides_batch[i]['slide_number']}: {result}")
                # Cria slide básico em caso de erro
                processed_slides.append(self._create_fallback_slide(slides_batch[i]))
            else:
                processed_slides.append(result)
        
        return processed_slides
    
    def _create_fallback_slide(self, slide_data: Dict) -> SlideData:
        """
        Cria slide básico em caso de erro no processamento
        """
        return SlideData(
            slide_number=slide_data["slide_number"],
            slide_title=slide_data.get("slide_title") or f"Slide {slide_data['slide_number']}",
            slide_summary=slide_data.get("extracted_text") or "Conteúdo não disponível para análise",
            elements=[]
        )
    
    async def _store_in_vector_database(
        self, 
        transcription_id: str, 
        transcription: PresentationTranscription
    ):
        """
        Armazena dados na base vectorizada
        """
        try:
            # Armazena resumo geral
            metadata_dict = {
                "transcription_id": transcription_id,
                "content_type": "presentation_summary",
                "title": transcription.presentation_metadata.title or "",
                "author": transcription.presentation_metadata.author or "",
                "presentation_type": transcription.presentation_metadata.presentation_type or "",
                "total_slides": transcription.presentation_metadata.total_slides,
                "key_concepts": json.dumps(transcription.key_concepts),
                "language": transcription.presentation_metadata.language,
                # Novos campos
                "workstream": request.workstream,
                "bpml_l1": request.bpml_l1,
                "bpml_l2": request.bpml_l2
            }
            
            await self.vector_service.add_document(
                text=transcription.overall_summary,
                metadata=metadata_dict,
                document_id=f"{transcription_id}_summary"
            )
            
            # Armazena slides individuais
            for slide in transcription.slides:
                slide_metadata = {
                    "transcription_id": transcription_id,
                    "content_type": "slide",
                    "slide_number": slide.slide_number,
                    "slide_title": slide.slide_title or "",
                    "presentation_title": transcription.presentation_metadata.title or "",
                    # Novos campos
                    "workstream": request.workstream,
                    "bpml_l1": request.bpml_l1,
                    "bpml_l2": request.bpml_l2
                }
                
                slide_text = f"{slide.slide_title}\n\n{slide.slide_summary}"
                
                await self.vector_service.add_document(
                    text=slide_text,
                    metadata=slide_metadata,
                    document_id=f"{transcription_id}_slide_{slide.slide_number}"
                )
            
        except Exception as e:
            logger.error(f"Erro ao armazenar na base vectorizada: {e}")
            raise
    
    async def _integrate_with_dify(
        self, 
        transcription_id: str, 
        transcription: PresentationTranscription, 
        dataset_name: Optional[str] = None
    ):
        """
        Integra com Dify.ai enviando cada slide como documento individual
        """
        try:
            # Prepara informações comuns da apresentação
            presentation_info = f"""APRESENTAÇÃO: {transcription.presentation_metadata.title}
AUTOR: {transcription.presentation_metadata.author}
TOTAL DE SLIDES: {transcription.presentation_metadata.total_slides}

RESUMO EXECUTIVO:
{transcription.overall_summary}

CONCEITOS CHAVE:
{', '.join(transcription.key_concepts)}

ANÁLISE DO FLUXO NARRATIVO:
{transcription.narrative_flow_analysis}

"""
            
            # Envia cada slide como documento separado
            for slide in transcription.slides:
                # Constrói conteúdo do slide individual
                slide_content = presentation_info + f"""
--- SLIDE {slide.slide_number} ---
Título: {slide.slide_title}
Resumo: {slide.slide_summary}
"""
                
                # Adiciona detalhes dos elementos do slide
                if slide.elements:
                    slide_content += "\nElementos:\n"
                    for element in slide.elements:
                        try:
                            semantic_json = json.dumps(element.semantic_analysis, ensure_ascii=False)
                        except Exception:
                            semantic_json = str(element.semantic_analysis)
                        
                        slide_content += (
                            f"  - ID: {element.element_id}\n"
                            f"    Tipo: {element.element_type}\n"
                            f"    Conteúdo bruto: {(element.raw_content[:500] + '...') if (element.raw_content and len(element.raw_content) > 500) else (element.raw_content or 'N/A')}\n"
                            f"    Análise semântica: {semantic_json}\n"
                        )
                        
                        if element.relationships_to_other_elements:
                            try:
                                rel_json = json.dumps(element.relationships_to_other_elements, ensure_ascii=False)
                            except Exception:
                                rel_json = str(element.relationships_to_other_elements)
                            slide_content += f"    Relações: {rel_json}\n"
                
                # Nome do documento do slide (sem sufixo desnecessário)
                slide_document_name = f"{transcription.presentation_metadata.title}_Slide_{slide.slide_number:02d}"
                
                # Metadados específicos do slide
                slide_metadata = {
                    "transcription_id": transcription_id,
                    "presentation_title": transcription.presentation_metadata.title,
                    "author": transcription.presentation_metadata.author,
                    "slide_number": slide.slide_number,
                    "slide_title": slide.slide_title or f"Slide {slide.slide_number}",
                    "total_slides": transcription.presentation_metadata.total_slides,
                    "presentation_type": transcription.presentation_metadata.presentation_type or "",
                    "processing_date": datetime.utcnow().isoformat(),
                    "content_type": "slide",
                    "language": transcription.presentation_metadata.language,
                    # Novos campos
                    "workstream": request.workstream,
                    "bpml_l1": request.bpml_l1,
                    "bpml_l2": request.bpml_l2
                }
                
                logger.info(f"Preparando envio do slide {slide.slide_number} com metadados: {json.dumps(slide_metadata, indent=2, ensure_ascii=False)}")
                
                # Envia slide para Dify
                result = await self.dify_service.upload_document(
                    content=slide_content,
                    document_name=slide_document_name,
                    metadata=slide_metadata,
                    dataset_name=dataset_name
                )
                
                if result.success:
                    logger.info(f"Slide {slide.slide_number} enviado para Dify com sucesso")
                else:
                    logger.warning(f"Falha ao enviar slide {slide.slide_number} para Dify: {result.message}")
            
            # Também envia um documento com o resumo executivo completo
            summary_content = presentation_info + f"""
DOCUMENTO DE RESUMO EXECUTIVO COMPLETO

Este documento contém o resumo executivo completo da apresentação com {transcription.presentation_metadata.total_slides} slides.

DETALHAMENTO ADICIONAL:
- Data de processamento: {datetime.utcnow().isoformat()}
- Tipo de apresentação: {transcription.presentation_metadata.presentation_type or 'Não especificado'}
- Idioma: {transcription.presentation_metadata.language}
"""
            
            summary_metadata = {
                "transcription_id": transcription_id,
                "presentation_title": transcription.presentation_metadata.title,
                "author": transcription.presentation_metadata.author,
                "total_slides": transcription.presentation_metadata.total_slides,
                "presentation_type": transcription.presentation_metadata.presentation_type or "",
                "processing_date": datetime.utcnow().isoformat(),
                "content_type": "summary",
                "language": transcription.presentation_metadata.language,
                # Novos campos
                "workstream": request.workstream,
                "bpml_l1": request.bpml_l1,
                "bpml_l2": request.bpml_l2
            }
            
            logger.info(f"Preparando envio do resumo executivo com metadados: {json.dumps(summary_metadata, indent=2, ensure_ascii=False)}")
            
            summary_result = await self.dify_service.upload_document(
                content=summary_content,
                document_name=f"{transcription.presentation_metadata.title}_Resumo_Executivo",
                metadata=summary_metadata,
                dataset_name=dataset_name
            )
            
            if summary_result.success:
                logger.info("Resumo executivo enviado para Dify com sucesso")
            else:
                logger.warning(f"Falha ao enviar resumo executivo para Dify: {summary_result.message}")
            
            logger.info(f"Integração com Dify concluída: {len(transcription.slides)} slides + 1 resumo enviados")
            
        except Exception as e:
            logger.error(f"Erro na integração com Dify: {e}")
            # Não falha o processamento se Dify falhar
    
    async def _cleanup_temp_files(self, slides_data: List[Dict]):
        """
        Remove arquivos temporários usando a nova estrutura simplificada
        """
        image_paths = self.slide_extractor.get_slide_image_paths(slides_data)
        self.slide_extractor.cleanup_temp_files(image_paths)
    
    async def get_transcription_by_id(self, transcription_id: str) -> Optional[TranscriptionResponse]:
        """
        Recupera transcrição por ID
        """
        return await self.firestore_service.get_transcription(transcription_id)
    
    async def search_transcriptions(self, query: SearchQuery) -> SearchResponse:
        """
        Busca semântica nas transcrições
        """
        return await self.vector_service.search(query)
    
    async def delete_transcription(self, transcription_id: str) -> bool:
        """
        Remove transcrição e dados associados
        """
        try:
            # Remove do Firestore
            await self.firestore_service.delete_transcription(transcription_id)
            
            # Remove da base vectorizada
            await self.vector_service.delete_documents_by_transcription_id(transcription_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao deletar transcrição: {e}")
            return False
    
    async def generate_presentation_analysis(
        self,
        transcription_id: str,
        analysis_type: str,
        custom_prompt: Optional[str] = None
    ) -> PresentationAnalysisResponse:
        """
        Gera análise customizada de uma apresentação
        """
        try:
            # Recupera transcrição
            transcription_data = await self.firestore_service.get_transcription(transcription_id)
            if not transcription_data:
                raise ValueError("Transcrição não encontrada")
            
            # Prepara contexto para análise
            analysis_context = self._prepare_analysis_context(transcription_data, analysis_type)
            
            # Gera análise com Gemini
            if custom_prompt:
                full_prompt = f"{custom_prompt}\n\nCONTEXTO DA APRESENTAÇÃO:\n{analysis_context}"
            else:
                full_prompt = self._get_analysis_prompt(analysis_type, analysis_context)
            
            analysis_result = await self.gemini_service.model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 1024,  # Reduzido para evitar MAX_TOKENS
                }
            )
            
            return PresentationAnalysisResponse(
                success=True,
                analysis=analysis_result.text,
                analysis_type=analysis_type,
                message="Análise gerada com sucesso"
            )
            
        except Exception as e:
            logger.error(f"Erro ao gerar análise: {e}")
            return PresentationAnalysisResponse(
                success=False,
                analysis_type=analysis_type,
                message="Erro ao gerar análise",
                error=str(e)
            )
    
    def _prepare_analysis_context(self, transcription_data: Dict, analysis_type: str) -> str:
        """
        Prepara contexto para análise customizada
        """
        # Implementação básica - pode ser expandida
        return json.dumps(transcription_data, indent=2, ensure_ascii=False, default=str)
    
    def _get_analysis_prompt(self, analysis_type: str, context: str) -> str:
        """
        Retorna prompt específico para tipo de análise
        """
        prompts = {
            "business_analysis": f"""
            Analise esta apresentação do ponto de vista de negócios. Foque em:
            1. Oportunidades identificadas
            2. Riscos e desafios
            3. Recomendações estratégicas
            4. Viabilidade das propostas
            
            CONTEXTO: {context}
            """,
            "content_summary": f"""
            Crie um resumo executivo detalhado desta apresentação incluindo:
            1. Principais pontos abordados
            2. Conclusões e recomendações
            3. Próximos passos sugeridos
            
            CONTEXTO: {context}
            """,
            "key_insights": f"""
            Extraia os principais insights desta apresentação:
            1. Descobertas mais relevantes
            2. Padrões identificados
            3. Implicações práticas
            
            CONTEXTO: {context}
            """
        }
        
        return prompts.get(analysis_type, f"Analise esta apresentação: {context}")
    
    async def get_slide_details(self, transcription_id: str, slide_number: int) -> Optional[Dict]:
        """
        Recupera detalhes específicos de um slide
        """
        transcription_obj = await self.firestore_service.get_transcription(transcription_id)
        if not transcription_obj:
            return None

        # Extração segura do conteúdo de transcrição
        slides: List[Any] = []
        transcription_content = None

        try:
            # Caso seja um modelo TranscriptionResponse (pydantic)
            from ..models.schemas import TranscriptionResponse, PresentationTranscription, SlideData  # import local p/ evitar ciclos
            if isinstance(transcription_obj, TranscriptionResponse):
                transcription_content = transcription_obj.transcription
                if transcription_content:
                    if isinstance(transcription_content, dict):
                        slides = transcription_content.get("slides", [])
                    elif isinstance(transcription_content, PresentationTranscription):
                        # Converter para dict para resposta consistente
                        slides = [s.dict() if isinstance(s, SlideData) else s for s in transcription_content.slides]
            else:
                # Caso (improvável aqui) seja um dict já
                transcription_content = transcription_obj.get("transcription") if isinstance(transcription_obj, dict) else None
                if isinstance(transcription_content, dict):
                    slides = transcription_content.get("slides", [])
        except Exception as e:
            logger.error(f"Erro ao interpretar transcrição para recuperar slide: {e}")
            return None

        if not slides:
            return None

        for slide in slides:
            # slide pode ser dict ou SlideData convertido
            number = None
            if isinstance(slide, dict):
                number = slide.get("slide_number")
            else:
                number = getattr(slide, "slide_number", None)
            if number == slide_number:
                # Garante retorno em dict
                if not isinstance(slide, dict):
                    try:
                        slide = slide.dict()
                    except Exception:
                        slide = {"slide_number": number}
                return slide

        return None
    
    # Métodos delegados para outros serviços
    async def create_dataset(self, name: str, description: Optional[str] = None):
        return await self.dify_service.create_dataset(name, description)
    
    async def list_datasets(self):
        return await self.dify_service.list_datasets()
    
    async def search_in_dify(self, request: DifySearchRequest):
        return await self.dify_service.search_documents(request)
    
    async def list_transcriptions(
        self, 
        limit: int = 10, 
        status_filter: Optional[TranscriptionStatus] = None
    ):
        return await self.firestore_service.list_transcriptions(limit, status_filter)
    
    async def get_system_statistics(self):
        return await self.firestore_service.get_statistics()
