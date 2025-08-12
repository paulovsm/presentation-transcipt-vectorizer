"""
Sistema de processamento em background usando asyncio e Redis
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import redis.asyncio as redis
import os

from ..config.settings import settings
from ..models.schemas import TranscriptionRequest
from .orchestrator import PresentationOrchestrator

logger = logging.getLogger(__name__)


def json_serial(obj):
    """JSON serializer para objetos que não são nativamente serializáveis"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


class BackgroundProcessor:
    """
    Processador de tasks em background usando Redis como queue
    """
    
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6380")
        self.redis_client: Optional[redis.Redis] = None
        self.orchestrator = PresentationOrchestrator()
        self.executor = ThreadPoolExecutor(max_workers=2)  # Pool dedicado para operações CPU-intensivas
        self.running = False
        
    async def initialize(self):
        """Inicializa conexão com Redis"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            # Testa conexão
            await self.redis_client.ping()
            logger.info("Conexão com Redis estabelecida com sucesso")
        except Exception as e:
            logger.error(f"Erro ao conectar com Redis: {e}")
            self.redis_client = None
            
    async def shutdown(self):
        """Fecha conexões e recursos"""
        self.running = False
        if self.redis_client:
            await self.redis_client.close()
        self.executor.shutdown(wait=True)
        
    async def enqueue_presentation_processing(
        self,
        file_path: str,
        request: TranscriptionRequest,
        dataset_name: Optional[str] = None,
        transcription_id: Optional[str] = None
    ) -> str:
        """
        Adiciona task de processamento na fila
        """
        if not self.redis_client:
            # Fallback: processa diretamente se Redis não estiver disponível
            logger.warning("Redis não disponível, processando diretamente")
            asyncio.create_task(
                self._process_presentation_direct(file_path, request, dataset_name, transcription_id)
            )
            return transcription_id or str(uuid.uuid4())
            
        task_id = transcription_id or str(uuid.uuid4())
        
        task_data = {
            "task_id": task_id,
            "file_path": file_path,
            "request": request.model_dump(mode='json'),  # Serialização JSON completa
            "dataset_name": dataset_name,
            "created_at": datetime.utcnow().isoformat(),
            "status": "queued"
        }
        
        try:
            # Adiciona na fila
            await self.redis_client.lpush("presentation_queue", json.dumps(task_data, default=json_serial))
            
            # Salva metadata da task
            await self.redis_client.hset(
                f"task:{task_id}",
                mapping={
                    "status": "queued",
                    "created_at": task_data["created_at"],
                    "file_name": request.file_name
                }
            )
            
            # TTL de 24 horas para limpeza automática
            await self.redis_client.expire(f"task:{task_id}", 86400)
            
            logger.info(f"Task {task_id} adicionada à fila de processamento")
            return task_id
            
        except Exception as e:
            logger.error(f"Erro ao adicionar task na fila: {e}")
            # Fallback
            asyncio.create_task(
                self._process_presentation_direct(file_path, request, dataset_name, task_id)
            )
            return task_id
    
    async def start_worker(self):
        """
        Inicia worker para processar fila
        """
        if not self.redis_client:
            logger.warning("Redis não disponível, worker não será iniciado")
            return
            
        self.running = True
        logger.info("Iniciando worker de processamento em background")
        
        while self.running:
            try:
                # Busca próxima task (bloqueia por até 5 segundos)
                result = await self.redis_client.brpop("presentation_queue", timeout=5)
                
                if result:
                    queue_name, task_data_str = result
                    task_data = json.loads(task_data_str)
                    
                    # Processa task
                    await self._process_task(task_data)
                    
                else:
                    # Timeout - continua loop
                    continue
                    
            except Exception as e:
                logger.error(f"Erro no worker de processamento: {e}")
                await asyncio.sleep(1)  # Aguarda antes de tentar novamente
                
    async def _process_task(self, task_data: Dict[str, Any]):
        """
        Processa uma task específica
        """
        task_id = task_data["task_id"]
        
        try:
            # Atualiza status
            await self.redis_client.hset(
                f"task:{task_id}",
                mapping={
                    "status": "processing",
                    "started_at": datetime.utcnow().isoformat()
                }
            )
            
            # Reconstroi objetos
            request = TranscriptionRequest(**task_data["request"])
            
            # Processa apresentação
            await self._process_presentation_with_executor(
                task_data["file_path"],
                request,
                task_data.get("dataset_name"),
                task_id
            )
            
            # Atualiza status final
            await self.redis_client.hset(
                f"task:{task_id}",
                mapping={
                    "status": "completed",
                    "completed_at": datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"Task {task_id} processada com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao processar task {task_id}: {e}")
            
            # Atualiza status de erro
            await self.redis_client.hset(
                f"task:{task_id}",
                mapping={
                    "status": "failed",
                    "failed_at": datetime.utcnow().isoformat(),
                    "error": str(e)
                }
            )
        finally:
            # Limpeza do arquivo temporário
            try:
                os.unlink(task_data["file_path"])
            except Exception:
                pass
    
    async def _process_presentation_with_executor(
        self,
        file_path: str,
        request: TranscriptionRequest,
        dataset_name: Optional[str] = None,
        transcription_id: Optional[str] = None
    ):
        """
        Executa processamento em thread separada para operações CPU-intensivas
        """
        loop = asyncio.get_event_loop()
        
        # Executa processamento pesado em thread separada
        await loop.run_in_executor(
            self.executor,
            self._run_sync_processing,
            file_path,
            request,
            dataset_name,
            transcription_id
        )
    
    def _run_sync_processing(
        self,
        file_path: str,
        request: TranscriptionRequest,
        dataset_name: Optional[str] = None,
        transcription_id: Optional[str] = None
    ):
        """
        Executa processamento síncrono em thread separada
        """
        # Cria novo event loop para a thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Executa processamento
            result = loop.run_until_complete(
                self.orchestrator.process_presentation_file(
                    file_path, request, dataset_name, transcription_id
                )
            )
            return result
        finally:
            loop.close()
    
    async def _process_presentation_direct(
        self,
        file_path: str,
        request: TranscriptionRequest,
        dataset_name: Optional[str] = None,
        transcription_id: Optional[str] = None
    ):
        """
        Processamento direto sem Redis (fallback)
        """
        try:
            await self.orchestrator.process_presentation_file(
                file_path, request, dataset_name, transcription_id
            )
        except Exception as e:
            logger.error(f"Erro no processamento direto: {e}")
        finally:
            try:
                os.unlink(file_path)
            except Exception:
                pass
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera status de uma task
        """
        if not self.redis_client:
            return None
            
        try:
            task_data = await self.redis_client.hgetall(f"task:{task_id}")
            return task_data if task_data else None
        except Exception as e:
            logger.error(f"Erro ao recuperar status da task: {e}")
            return None


# Instância global do processador
background_processor = BackgroundProcessor()
