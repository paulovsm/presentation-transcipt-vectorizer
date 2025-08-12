import os
import tempfile
import aiofiles
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from typing import Optional, List
import logging
import asyncio

from ..config.settings import settings
from ..models.schemas import (
    TranscriptionRequest, TranscriptionResponse, SearchQuery, SearchResponse,
    UploadResponse, ProcessedPresentation, DifySearchRequest, PresentationFormat,
    PresentationAnalysisRequest, PresentationAnalysisResponse
)
from ..services.orchestrator import PresentationOrchestrator
from ..services.background_processor import background_processor

# Configuração de logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Inicialização da aplicação
app = FastAPI(
    title="Sistema de Transcrição de Apresentações PowerPoint/PDF",
    description="API para transcrição automatizada de apresentações com IA Gemini",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure adequadamente para produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependências
async def get_orchestrator() -> PresentationOrchestrator:
    return PresentationOrchestrator()


@app.on_event("startup")
async def startup_event():
    """Inicialização da aplicação"""
    logger.info("Iniciando aplicação de transcrição de apresentações...")
    
    # Cria diretórios necessários
    os.makedirs(settings.upload_directory, exist_ok=True)
    os.makedirs(settings.temp_extraction_directory, exist_ok=True)
    os.makedirs(os.path.dirname(settings.log_file), exist_ok=True)
    os.makedirs(settings.chroma_db_path, exist_ok=True)
    
    # Inicializa processador em background
    await background_processor.initialize()
    
    # Inicia worker em background
    asyncio.create_task(background_processor.start_worker())
    
    logger.info("Aplicação iniciada com sucesso - usando Cloud Firestore")


@app.on_event("shutdown")
async def shutdown_event():
    """Finalização da aplicação"""
    logger.info("Finalizando aplicação...")
    await background_processor.shutdown()
    logger.info("Aplicação finalizada")


@app.post("/upload", response_model=UploadResponse)
async def upload_presentation_file(
    file: UploadFile = File(...),
    presentation_title: Optional[str] = None,
    presentation_type: Optional[str] = None,
    author: Optional[str] = None,
    language_code: str = "pt-BR",
    detailed_analysis: bool = True,
    dataset_name: Optional[str] = None,
    # Novos parâmetros
    workstream: Optional[str] = None,
    bpml_l1: Optional[str] = None,
    bpml_l2: Optional[str] = None,
    orchestrator: PresentationOrchestrator = Depends(get_orchestrator)
):
    """
    Faz upload de arquivo de apresentação (PPT/PDF) e inicia processamento em background
    """
    try:
        # Validações
        if not file.filename:
            raise HTTPException(status_code=400, detail="Nome do arquivo é obrigatório")
        
        # Verifica formato do arquivo
        file_extension = Path(file.filename).suffix.lower().lstrip('.')
        if file_extension not in settings.allowed_formats_list:
            raise HTTPException(
                status_code=400,
                detail=f"Formato não suportado. Formatos aceitos: {settings.allowed_presentation_formats}"
            )
        
        # Determina o formato da apresentação
        presentation_format = PresentationFormat(file_extension)
        
        # Verifica tamanho do arquivo
        content = await file.read()
        file_size = len(content)
        
        if file_size > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Arquivo muito grande. Tamanho máximo: {settings.max_file_size_mb}MB"
            )
        
        # Salva arquivo temporariamente
        temp_file_path = os.path.join(
            settings.upload_directory,
            f"{uuid.uuid4()}_{file.filename}"
        )
        
        async with aiofiles.open(temp_file_path, 'wb') as temp_file:
            await temp_file.write(content)
        
        # Prepara request de transcrição
        transcription_request = TranscriptionRequest(
            file_name=file.filename,
            presentation_title=presentation_title,
            presentation_date=datetime.utcnow(),
            author=author,
            presentation_type=presentation_type,
            language_code=language_code,
            detailed_analysis=detailed_analysis,
            # Novos campos
            workstream=workstream,
            bpml_l1=bpml_l1,
            bpml_l2=bpml_l2
        )
        
        # Gera ID da transcrição que será criada
        transcription_id = str(uuid.uuid4())
        
        # Fallback: se dataset_name não informado, usar dataset padrão das settings (se definido)
        if not dataset_name:
            if getattr(settings, "dify_dataset_id", None):
                dataset_name = settings.dify_dataset_id
                logger.info(
                    "dataset_name não fornecido no upload. Usando dataset padrão configurado: %s",
                    dataset_name
                )
            else:
                logger.info(
                    "dataset_name não fornecido e nenhum dataset padrão configurado. Integração usará default interno."
                )

        # Envia para processamento em background (não bloqueia)
        task_id = await background_processor.enqueue_presentation_processing(
            temp_file_path,
            transcription_request,
            dataset_name,
            transcription_id
        )
        
        logger.info(f"Upload concluído e task {task_id} enviada para processamento em background")
        
        return UploadResponse(
            file_id=task_id,
            file_name=file.filename,
            file_size=file_size,
            upload_status="uploaded",
            message="Arquivo carregado com sucesso. Processamento iniciado em background.",
            presentation_format=presentation_format
        )
        
    except Exception as e:
        logger.error(f"Erro no upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@app.get("/transcriptions/{transcription_id}", response_model=TranscriptionResponse)
async def get_transcription(
    transcription_id: str,
    orchestrator: PresentationOrchestrator = Depends(get_orchestrator)
):
    """
    Recupera transcrição por ID
    """
    result = await orchestrator.get_transcription_by_id(transcription_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transcrição não encontrada")
    
    return result


@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """
    Recupera status de processamento de uma task
    """
    status = await background_processor.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task não encontrada")
    
    return {
        "task_id": task_id,
        "status": status.get("status", "unknown"),
        "created_at": status.get("created_at"),
        "started_at": status.get("started_at"),
        "completed_at": status.get("completed_at"),
        "failed_at": status.get("failed_at"),
        "error": status.get("error"),
        "file_name": status.get("file_name")
    }


@app.post("/search", response_model=SearchResponse)
async def search_transcriptions(
    query: SearchQuery,
    orchestrator: PresentationOrchestrator = Depends(get_orchestrator)
):
    """
    Busca semântica nas transcrições
    """
    return await orchestrator.search_transcriptions(query)


@app.delete("/transcriptions/{transcription_id}")
async def delete_transcription(
    transcription_id: str,
    orchestrator: PresentationOrchestrator = Depends(get_orchestrator)
):
    """
    Remove transcrição e todos os dados associados
    """
    success = await orchestrator.delete_transcription(transcription_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transcrição não encontrada")
    
    return {"message": "Transcrição removida com sucesso"}


@app.post("/transcriptions/{transcription_id}/analyze", response_model=PresentationAnalysisResponse)
async def generate_presentation_analysis(
    transcription_id: str,
    request: PresentationAnalysisRequest,
    orchestrator: PresentationOrchestrator = Depends(get_orchestrator)
):
    """
    Gera análise customizada de uma apresentação
    """
    try:
        analysis = await orchestrator.generate_presentation_analysis(
            transcription_id,
            request.analysis_type,
            request.custom_prompt
        )
        
        return analysis
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erro na análise: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """
    Health check da aplicação
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "service": "presentation-transcription"
    }


@app.get("/stats")
async def get_statistics(
    orchestrator: PresentationOrchestrator = Depends(get_orchestrator)
):
    """
    Estatísticas da aplicação
    """
    try:
        stats = await orchestrator.get_system_statistics()
        return stats
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transcriptions")
async def list_transcriptions(
    limit: int = 10,
    status: Optional[str] = None,
    orchestrator: PresentationOrchestrator = Depends(get_orchestrator)
):
    """
    Lista transcrições com filtros opcionais
    """
    try:
        from ..models.schemas import TranscriptionStatus
        
        status_filter = None
        if status:
            try:
                status_filter = TranscriptionStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Status inválido: {status}")
        
        transcriptions = await orchestrator.list_transcriptions(
            limit=limit,
            status_filter=status_filter
        )
        
        return {
            "transcriptions": transcriptions,
            "total": len(transcriptions),
            "limit": limit,
            "status_filter": status
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar transcrições: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/datasets")
async def create_dataset(
    name: str,
    description: Optional[str] = None,
    orchestrator: PresentationOrchestrator = Depends(get_orchestrator)
):
    """
    Cria um novo dataset no Dify.ai
    """
    try:
        result = await orchestrator.create_dataset(name, description)
        return result
    except Exception as e:
        logger.error(f"Erro ao criar dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/datasets")
async def list_datasets(
    page: int = 1,
    limit: int = 20,
    orchestrator: PresentationOrchestrator = Depends(get_orchestrator)
):
    """
    Lista todos os datasets disponíveis
    """
    try:
        result = await orchestrator.list_datasets()
        return result
    except Exception as e:
        logger.error(f"Erro ao listar datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/dify")
async def search_in_dify(
    request: DifySearchRequest,
    orchestrator: PresentationOrchestrator = Depends(get_orchestrator)
):
    """
    Busca diretamente no Dify.ai
    """
    try:
        result = await orchestrator.search_in_dify(request)
        return result
    except Exception as e:
        logger.error(f"Erro na busca Dify: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/slides/{transcription_id}/{slide_number}")
async def get_slide_details(
    transcription_id: str,
    slide_number: int,
    orchestrator: PresentationOrchestrator = Depends(get_orchestrator)
):
    """
    Recupera detalhes específicos de um slide
    """
    try:
        slide_data = await orchestrator.get_slide_details(transcription_id, slide_number)
        if not slide_data:
            raise HTTPException(status_code=404, detail="Slide não encontrado")
        
        return slide_data
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao recuperar slide: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )
