"""
Utilitários para geração de IDs personalizados para transcrições
"""
from datetime import datetime
from typing import Optional
import re
import unicodedata


def _clean_string(text: str) -> str:
    """
    Remove acentos e caracteres especiais de uma string, mantendo apenas alfanuméricos, underscore e hífen
    """
    if not text:
        return ""
    
    # Remove acentos
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    
    # Remove caracteres especiais, mantém apenas alfanuméricos, underscore e hífen
    text = re.sub(r'[^a-zA-Z0-9_-]', '_', text)
    
    # Remove underscores múltiplos consecutivos
    text = re.sub(r'_+', '_', text)
    
    # Remove underscores no início e fim
    text = text.strip('_')
    
    return text.upper()


def generate_transcription_id(
    workstream: Optional[str],
    meeting_date: Optional[datetime],
    meeting_id: Optional[str]
) -> str:
    """
    Gera um ID de transcrição no formato: [workstream]_[YYYYMMDD]_[meeting_id]
    
    Args:
        workstream: Nome do workstream
        meeting_date: Data da reunião/apresentação
        meeting_id: ID da reunião/apresentação
    
    Returns:
        String no formato solicitado, com fallbacks quando campos não estão disponíveis
    """
    # Fallback para workstream
    workstream_part = _clean_string(workstream) if workstream else "DEFAULT"
    
    # Fallback para data
    if meeting_date:
        date_part = meeting_date.strftime("%Y%m%d")
    else:
        date_part = datetime.utcnow().strftime("%Y%m%d")
    
    # Fallback para meeting_id
    if meeting_id:
        meeting_id_part = _clean_string(meeting_id)
    else:
        meeting_id_part = f"MEETING_{datetime.utcnow().strftime('%H%M%S')}"
    
    # Monta o ID final
    transcription_id = f"{workstream_part}_{date_part}_{meeting_id_part}"
    
    return transcription_id


def validate_transcription_id(transcription_id: str) -> bool:
    """
    Valida se o ID de transcrição está no formato correto
    
    Args:
        transcription_id: ID para validar
    
    Returns:
        True se válido, False caso contrário
    """
    # Padrão: [workstream]_[YYYYMMDD]_[meeting_id]
    pattern = r'^[A-Z0-9_-]+_\d{8}_[A-Z0-9_-]+$'
    return bool(re.match(pattern, transcription_id))
