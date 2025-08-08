import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Google Cloud
    google_cloud_project: str = Field(..., env="GOOGLE_CLOUD_PROJECT")
    google_application_credentials: Optional[str] = Field(None, env="GOOGLE_APPLICATION_CREDENTIALS")
    vertex_ai_location: str = Field("us-central1", env="VERTEX_AI_LOCATION")
    gemini_model: str = Field("gemini-2.5-flash", env="GEMINI_MODEL")
    
    # ChromaDB
    chroma_db_path: str = Field("./data/chroma_db", env="CHROMA_DB_PATH")
    chroma_collection_name: str = Field("presentation_transcriptions", env="CHROMA_COLLECTION_NAME")
    anonymized_telemetry: bool = Field(False, env="ANONYMIZED_TELEMETRY")
    
    # API
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8001, env="API_PORT")  # Porta diferente do audio service
    api_reload: bool = Field(True, env="API_RELOAD")
    api_workers: int = Field(4, env="API_WORKERS")  # Número de workers para produção
    api_timeout_keep_alive: int = Field(60, env="API_TIMEOUT_KEEP_ALIVE")
    api_max_requests: int = Field(1000, env="API_MAX_REQUESTS")  # Requests por worker antes de reiniciar
    
    # Google Cloud Firestore
    # Usa as mesmas credenciais do GCP
    
    # Dify.ai
    dify_api_url: str = Field("https://api.dify.ai/v1", env="DIFY_API_URL")
    dify_api_key: str = Field(..., env="DIFY_API_KEY")
    dify_dataset_id: str = Field(..., env="DIFY_DATASET_ID")
    dify_workflow_api_key: str = Field(..., env="DIFY_WORKFLOW_API_KEY")
    
    # Security
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(1440, env="JWT_EXPIRE_MINUTES")
    
    # Upload - Suporte para PPT e PDF
    max_file_size_mb: int = Field(100, env="MAX_FILE_SIZE_MB")  # PPT/PDF são menores
    allowed_presentation_formats: str = Field("pptx,ppt,pdf", env="ALLOWED_PRESENTATION_FORMATS")
    upload_directory: str = Field("./data/uploads", env="UPLOAD_DIRECTORY")
    temp_extraction_directory: str = Field("./data/temp_extraction", env="TEMP_EXTRACTION_DIRECTORY")
    
    # Processing
    slides_per_chunk: int = Field(5, env="SLIDES_PER_CHUNK")  # Slides por chunk de processamento
    overlap_slides: int = Field(1, env="OVERLAP_SLIDES")
    min_confidence_threshold: float = Field(0.8, env="MIN_CONFIDENCE_THRESHOLD")
    
    # Gemini Vision
    max_image_size_mb: int = Field(20, env="MAX_IMAGE_SIZE_MB")
    image_quality: str = Field("high", env="IMAGE_QUALITY")  # high, medium, low
    
    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str = Field("./logs/app.log", env="LOG_FILE")
    
    @property
    def allowed_formats_list(self) -> list[str]:
        return [fmt.strip() for fmt in self.allowed_presentation_formats.split(",")]
    
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024
    
    @property
    def max_image_size_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Instância global das configurações
settings = Settings()
