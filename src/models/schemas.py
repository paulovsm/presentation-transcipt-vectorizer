from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class TranscriptionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING_SLIDES = "extracting_slides"
    PROCESSING_SLIDES = "processing_slides"
    GENERATING_SUMMARY = "generating_summary"
    COMPLETED = "completed"
    FAILED = "failed"


class PresentationFormat(str, Enum):
    PPTX = "pptx"
    PPT = "ppt"
    PDF = "pdf"


class SlideElement(BaseModel):
    """Representa um elemento individual de um slide"""
    element_id: str
    element_type: str  # diagram, chart, text_block, image, etc.
    raw_content: Optional[str] = None  # Texto extraído ou caminho para imagem
    semantic_analysis: Dict[str, Any]
    relationships_to_other_elements: Optional[List[Dict[str, Any]]] = None


class SlideData(BaseModel):
    """Dados completos de um slide"""
    slide_number: int
    slide_title: Optional[str] = None
    slide_summary: str
    elements: List[SlideElement]
    # Campos layout_type, inter_slide_relationship e image_path removidos para simplificação


class PresentationMetadata(BaseModel):
    """Metadados da apresentação"""
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[datetime] = None
    source_filename: str
    total_slides: int
    presentation_type: Optional[str] = None  # business, academic, marketing, etc.
    language: str = "pt-BR"


class PresentationTranscription(BaseModel):
    """Estrutura principal de transcrição de apresentação"""
    presentation_metadata: PresentationMetadata
    overall_summary: str
    key_concepts: List[str]
    narrative_flow_analysis: str
    slides: List[SlideData]


class TranscriptionRequest(BaseModel):
    file_name: str
    presentation_title: Optional[str] = None
    presentation_date: Optional[datetime] = None
    author: Optional[str] = None
    presentation_type: Optional[str] = None
    language_code: str = "pt-BR"
    detailed_analysis: bool = True  # Se deve fazer análise detalhada de elementos
    # Novos campos
    workstream: Optional[str] = None
    bpml_l1: Optional[str] = None
    bpml_l2: Optional[str] = None


class TranscriptionResponse(BaseModel):
    id: str
    status: TranscriptionStatus
    file_name: str
    slides_count: Optional[int] = None
    transcription: Optional[PresentationTranscription] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    processing_time_seconds: Optional[float] = None


class ProcessedPresentation(BaseModel):
    transcription_id: str
    metadata: PresentationMetadata
    summary: str
    embedding_ids: List[str]
    processing_status: ProcessingStatus
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class UploadResponse(BaseModel):
    file_id: str
    file_name: str
    file_size: int
    upload_status: str
    message: str
    presentation_format: PresentationFormat


class SearchQuery(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=100)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = None
    include_metadata: bool = True
    search_in_slides: bool = True  # Se deve buscar em slides individuais
    search_in_elements: bool = False  # Se deve buscar em elementos de slides


class SearchResult(BaseModel):
    id: str
    text: str
    score: float
    metadata: Dict[str, Any]
    transcription_id: str
    slide_number: Optional[int] = None
    element_id: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total_found: int
    query: str
    execution_time_ms: float


class DifyIntegrationRequest(BaseModel):
    transcription_id: str
    document_name: str
    content: str
    metadata: Dict[str, Any]
    dataset_id: Optional[str] = None
    dataset_name: Optional[str] = None


class DifyIntegrationResponse(BaseModel):
    success: bool
    document_id: Optional[str] = None
    dataset_id: Optional[str] = None
    message: str
    error: Optional[str] = None


class DifyDatasetRequest(BaseModel):
    name: str
    description: Optional[str] = None
    permission: str = "only_me"


class DifyDatasetResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    permission: str
    document_count: int = 0
    word_count: int = 0
    created_at: Optional[datetime] = None


class DifySearchRequest(BaseModel):
    query: str
    dataset_id: Optional[str] = None
    limit: int = 10
    similarity_threshold: float = 0.7


class PresentationAnalysisRequest(BaseModel):
    transcription_id: str
    analysis_type: str  # "business_analysis", "content_summary", "key_insights", etc.
    custom_prompt: Optional[str] = None


class PresentationAnalysisResponse(BaseModel):
    success: bool
    analysis: Optional[str] = None
    analysis_type: str
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None
    message: str
    error: Optional[str] = None
