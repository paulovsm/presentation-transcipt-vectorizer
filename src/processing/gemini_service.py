import asyncio
import json
import logging
import os
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

import vertexai
from vertexai.generative_models import GenerativeModel, Part, Content
from google.cloud import aiplatform

from ..config.settings import settings
from ..models.schemas import (
    SlideData, SlideElement, PresentationTranscription, 
    PresentationMetadata, ProcessingStatus
)

logger = logging.getLogger(__name__)


class GeminiPresentationService:
    """
    Serviço para processar apresentações usando Gemini Vision e Text
    """
    
    def __init__(self):
        # Configuração explícita de autenticação
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
        
        # Inicializa Vertex AI com configuração específica
        try:
            vertexai.init(
                project=settings.google_cloud_project,
                location=settings.vertex_ai_location,
                credentials=None  # Usa as credenciais do ambiente
            )
            
            self.model = GenerativeModel(settings.gemini_model)
            logger.info(f"Vertex AI inicializado para projeto {settings.google_cloud_project} em {settings.vertex_ai_location}")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar Vertex AI: {e}")
            # Tenta inicialização alternativa
            try:
                import google.auth
                from google.auth import default
                
                # Obtém credenciais com escopos específicos
                credentials, project = default(
                    scopes=[
                        'https://www.googleapis.com/auth/cloud-platform',
                        'https://www.googleapis.com/auth/generative-language'
                    ]
                )
                
                vertexai.init(
                    project=settings.google_cloud_project,
                    location=settings.vertex_ai_location,
                    credentials=credentials
                )
                
                self.model = GenerativeModel(settings.gemini_model)
                logger.info("Vertex AI inicializado com credenciais específicas")
                
            except Exception as e2:
                logger.error(f"Erro na inicialização alternativa: {e2}")
                raise e2
        
        # Prompts especializados
        self.global_analysis_prompt = self._get_global_analysis_prompt()
        self.slide_analysis_prompt = self._get_slide_analysis_prompt()
        self.element_analysis_prompt = self._get_element_analysis_prompt()
    
    async def process_presentation_global(
        self, 
        slides_data: List[Dict[str, Any]], 
        presentation_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Análise global da apresentação usando Gemini
        """
        try:
            logger.info("Iniciando análise global da apresentação com Gemini")
            
            # Prepara contexto global
            global_context = self._prepare_global_context(slides_data, presentation_metadata)
            
            # Chama Gemini para análise global
            response = await self._call_gemini_for_global_analysis(global_context)
            
            return response
            
        except Exception as e:
            logger.error(f"Erro na análise global: {e}")
            raise
    
    async def process_slide_detailed(
        self, 
        slide_data: Dict[str, Any], 
        slide_image_base64: Optional[str] = None,
        presentation_context: Optional[Dict[str, Any]] = None
    ) -> SlideData:
        """
        Análise detalhada de um slide específico
        """
        try:
            logger.info(f"Processando slide {slide_data['slide_number']} com Gemini")
            
            # Prepara conteúdo para análise
            content_parts = []
            
            # Adiciona imagem se disponível
            if slide_image_base64:
                image_part = Part.from_data(
                    data=slide_image_base64,
                    mime_type="image/jpeg"
                )
                content_parts.append(image_part)
            
            # Prepara prompt específico do slide
            slide_prompt = self._prepare_slide_prompt(slide_data, presentation_context)
            content_parts.append(Part.from_text(slide_prompt))
            
            # Chama Gemini
            response = self.model.generate_content(
                Content(role="user", parts=content_parts),
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "top_k": 40,
                    #"max_output_tokens": 2048,  # Reduzido para evitar MAX_TOKENS
                }
            )
            
            # Processa resposta
            slide_analysis = self._parse_slide_analysis_response(response.text)
            
            # Constrói objeto SlideData
            processed_slide = self._build_slide_data_object(slide_data, slide_analysis)
            
            return processed_slide
            
        except Exception as e:
            logger.error(f"Erro no processamento do slide {slide_data.get('slide_number', 'unknown')}: {e}")
            # Cria fallback básico para não interromper o processamento
            return self._create_fallback_slide_data(slide_data)
    
    async def generate_presentation_summary(
        self, 
        slides: List[SlideData], 
        global_analysis: Dict[str, Any]
    ) -> str:
        """
        Gera resumo executivo da apresentação
        """
        try:
            logger.info("Gerando resumo executivo da apresentação")
            
            # Prepara contexto para resumo
            summary_context = self._prepare_summary_context(slides, global_analysis)
            
            # Prompt para resumo executivo
            summary_prompt = f"""
            Baseado na análise desta apresentação, gere um resumo executivo conciso.
            
            CONTEXTO (RESUMIDO):
            {summary_context[:2000]}  # Limita o contexto para evitar overflow
            
            GERE UM RESUMO EXECUTIVO INCLUINDO:
            1. **Objetivo**: Propósito central da apresentação
            2. **Conceitos Principais**: 3-4 conceitos mais importantes  
            3. **Conclusões**: Principais insights ou recomendações
            4. **Aplicabilidade**: Como pode ser aplicado
            
            Mantenha o resumo conciso (máximo 300 palavras).
            """
            
            response = self.model.generate_content(
                summary_prompt,
                generation_config={
                    "temperature": 0.2,
                    #"max_output_tokens": 512,  # Reduzido para evitar MAX_TOKENS
                }
            )
            
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Erro ao gerar resumo: {e}")
            # Tenta um resumo básico baseado nos dados disponíveis
            try:
                basic_summary = self._generate_basic_summary(slides, global_analysis)
                return basic_summary
            except:
                return f"Apresentação com {len(slides)} slides processados - Resumo não disponível devido a erro técnico"
    
    def _prepare_global_context(self, slides_data: List[Dict], metadata: Dict) -> str:
        """
        Prepara contexto global da apresentação
        """
        context = f"""
        METADADOS DA APRESENTAÇÃO:
        - Título: {metadata.get('title', 'Não informado')}
        - Autor: {metadata.get('author', 'Não informado')}
        - Total de slides: {metadata.get('total_slides', len(slides_data))}
        - Arquivo fonte: {metadata.get('source_filename', 'Não informado')}
        
        CONTEÚDO DOS SLIDES:
        """
        
        for slide in slides_data:
            context += f"\n--- SLIDE {slide['slide_number']} ---\n"
            context += f"Título: {slide.get('title', 'Sem título')}\n"
            context += f"Layout: {slide.get('layout_name', 'Desconhecido')}\n"
            
            if slide.get('text_content'):
                context += "Conteúdo de texto:\n"
                for text in slide['text_content']:
                    context += f"- {text}\n"
            
            context += "\n"
        
        return context
    
    def _prepare_slide_prompt(self, slide_data: Dict, context: Optional[Dict] = None) -> str:
        """
        Prepara prompt específico para análise de slide
        """
        prompt = f"""
        Você é um analista de apresentações expert. Analise este slide em detalhes e forneça uma análise estruturada em JSON.
        
        DADOS DO SLIDE:
        - Número: {slide_data['slide_number']}
        - Título: {slide_data.get('title', 'Sem título')}
        - Layout: {slide_data.get('layout_name', 'Desconhecido')}
        
        {self.slide_analysis_prompt}
        """
        
        if context:
            prompt += f"\n\nCONTEXTO DA APRESENTAÇÃO:\n{json.dumps(context, indent=2, ensure_ascii=False)}"
        
        return prompt
    
    def _prepare_summary_context(self, slides: List[SlideData], global_analysis: Dict) -> str:
        """
        Prepara contexto para geração de resumo
        """
        context = f"""
        ANÁLISE GLOBAL:
        {json.dumps(global_analysis, indent=2, ensure_ascii=False)}
        
        RESUMO DOS SLIDES:
        """
        
        for slide in slides:
            context += f"\n--- SLIDE {slide.slide_number} ---\n"
            context += f"Título: {slide.slide_title or 'Sem título'}\n"
            context += f"Resumo: {slide.slide_summary}\n"
            # Campos layout_type e inter_slide_relationship removidos
        
        return context
    
    async def _call_gemini_for_global_analysis(self, context: str) -> Dict[str, Any]:
        """
        Chama Gemini para análise global
        """
        prompt = f"""
        {self.global_analysis_prompt}
        
        APRESENTAÇÃO PARA ANÁLISE:
        {context}
        """
        
        response = self.model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
                "top_p": 0.8,
                #"max_output_tokens": 1024,  # Reduzido para evitar MAX_TOKENS
            }
        )
        
        try:
            # Extrai possível bloco JSON limpo
            json_text = self._extract_json_text(response.text)
            return json.loads(json_text)
        except json.JSONDecodeError:
            # Se não conseguir parsear, retorna estrutura básica
            logger.warning("Resposta do Gemini não é JSON válido, criando estrutura básica")
            return {
                "overall_summary": response.text,
                "key_concepts": [],
                "narrative_flow_analysis": "",
                "presentation_type": "unknown"
            }
    
    def _parse_slide_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """
        Faz parse da resposta de análise de slide
        """
        try:
            json_text = self._extract_json_text(response_text)
            return json.loads(json_text)
        except json.JSONDecodeError:
            logger.warning("Resposta do Gemini não é JSON válido para slide")
            return {
                "slide_title": "",
                "layout_type": "unknown",
                "slide_summary": response_text[:200],
                "elements": [],
                "inter_slide_relationship": {}
            }
    
    def _build_slide_data_object(self, original_data: Dict, analysis: Dict) -> SlideData:
        """
        Constrói objeto SlideData a partir dos dados originais e análise
        """
        # Processa elementos se existirem na análise
        elements = []
        for elem_data in analysis.get("elements", []):
            element = SlideElement(
                element_id=elem_data.get("element_id", f"elem_{uuid.uuid4().hex[:8]}"),
                element_type=elem_data.get("element_type", "unknown"),
                raw_content=elem_data.get("raw_content"),
                semantic_analysis=elem_data.get("semantic_analysis", {}),
                relationships_to_other_elements=elem_data.get("relationships_to_other_elements")
            )
            elements.append(element)
        
        return SlideData(
            slide_number=original_data["slide_number"],
            slide_title=analysis.get("slide_title") or original_data.get("title"),
            slide_summary=analysis.get("slide_summary", ""),
            elements=elements,
            # Campos removidos: layout_type, inter_slide_relationship, image_path
        )
    
    def _get_global_analysis_prompt(self) -> str:
        """
        Prompt para análise global da apresentação
        """
        return """
        Você é um analista de negócios sênior especializado em análise de apresentações.
        Analise esta apresentação completa e forneça uma análise estruturada.

        INSTRUÇÕES DE FORMATO (IMPORTANTE):
        1. Responda SOMENTE com JSON válido (RFC 8259).
        2. NÃO inclua explicações, markdown, comentários, texto antes ou depois.
        3. NÃO use trailing vírgulas nem comentários // ou /* */.
        4. Todas as chaves e strings DEVEM usar aspas duplas.

        Estrutura esperada:
        {
            "overall_summary": "Resumo executivo conciso da apresentação (2-3 frases)",
            "key_concepts": ["conceito1", "conceito2", "conceito3"],
            "narrative_flow_analysis": "Descrição de como as ideias fluem do início ao fim",
            "presentation_type": "business|academic|marketing|training|other",
            "target_audience": "Para quem esta apresentação foi criada",
            "main_objective": "Objetivo principal da apresentação"
        }

        Gere somente o objeto JSON.
        """
    
    def _get_slide_analysis_prompt(self) -> str:
        """
        Prompt para análise detalhada de slide
        """
        return """
        Forneça uma análise detalhada deste slide em formato JSON.

        INSTRUÇÕES DE FORMATO (IMPORTANTE):
        1. Responda SOMENTE com JSON válido (sem markdown, sem explicações, sem texto extra).
        2. Use apenas aspas duplas. Não use comentários ou vírgulas sobrando.
        3. Se algum campo não puder ser determinado, use string vazia, array vazio ou objeto vazio conforme apropriado.

        Estrutura do objeto esperado:
        {
            "slide_title": "Título identificado do slide",
            "layout_type": "Classificação do layout visual (ex: 'Título e Conteúdo', 'Comparação', 'Fluxograma', 'Gráfico')",
            "slide_summary": "Resumo do principal ponto ou mensagem deste slide (1-2 frases)",
            "elements": [
                {
                    "element_id": "ID único do elemento",
                    "element_type": "diagram|chart|text_block|image|table|flowchart",
                    "raw_content": "Conteúdo bruto extraído (texto do bloco ou descrição sucinta se imagem/diagrama)",
                    "semantic_analysis": {
                        "description": "Descrição visual do elemento",
                        "purpose_and_meaning": "Por que este elemento está aqui e que informação transmite",
                        "key_data_points": ["ponto1", "ponto2"]
                    },
                    "relationships_to_other_elements": [
                        {
                            "related_element_id": "ID do elemento relacionado",
                            "relationship_type": "describes|supports|connects_to",
                            "details": "Descrição da relação"
                        }
                    ]
                }
            ],
            "inter_slide_relationship": {
                "to_previous": "Como este slide se baseia no anterior",
                "to_next": "Como este slide prepara para o próximo"
            }
        }

        Gere somente o objeto JSON.
        """
    
    def _get_element_analysis_prompt(self) -> str:
        """
        Prompt para análise de elementos específicos
        """
        return """
        Analise este elemento específico do slide e forneça insights detalhados sobre:
        1. Tipo e propósito do elemento
        2. Informações que transmite
        3. Como se relaciona com outros elementos
        4. Importância no contexto do slide
        """
    
    def _create_fallback_slide_data(self, slide_data: Dict) -> SlideData:
        """
        Cria um SlideData básico quando o processamento com Gemini falha
        """
        return SlideData(
            slide_number=slide_data["slide_number"],
            slide_title=slide_data.get("title", f"Slide {slide_data['slide_number']}"),
            slide_summary=f"Slide {slide_data['slide_number']} - processamento básico",
            elements=[]
        )

    def _extract_json_text(self, raw_text: str) -> str:
        """Tenta isolar e limpar um bloco JSON de uma resposta possivelmente contaminada.

        Estratégia:
        1. Se já começa com `{` e termina com `}` e faz parse, retorna direto.
        2. Extrai primeiro bloco entre ```json ... ``` ou ``` ... ```.
        3. Procura primeira chave '{' e última '}' e tenta parse incremental.
        4. Remove markdown, prefixos como 'Aqui está', e trailing vírgulas comuns.
        """
        text = raw_text.strip()
        # Caso simples
        if text.startswith('{') and text.endswith('}'):
            return text

        # Bloco fenced com linguagem
        fenced = re.findall(r"```(?:json)?\n(.*?)```", text, flags=re.DOTALL|re.IGNORECASE)
        if fenced:
            candidate = fenced[0].strip()
            if candidate.startswith('{'):
                return candidate

        # Remove possíveis prefixos
        prefixes = ["Aqui está", "Segue", "JSON:", "Resultado:"]
        for p in prefixes:
            if text.lower().startswith(p.lower()):
                text = text[len(p):].strip(': \n')

        # Tenta encontrar maior substring entre chaves balanceadas
        first = text.find('{')
        last = text.rfind('}')
        if first != -1 and last != -1 and last > first:
            candidate = text[first:last+1]
            # Heurística para remover trailing vírgulas antes de '}' ou ']' que quebram JSON
            candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
            return candidate.strip()

        # Se tudo falhar retorna texto original (vai gerar fallback)
        return raw_text
    
    def _generate_basic_summary(self, slides: List[SlideData], global_analysis: Dict[str, Any]) -> str:
        """
        Gera um resumo básico sem usar Gemini quando há falha
        """
        total_slides = len(slides)
        slide_titles = [slide.slide_title for slide in slides if slide.slide_title]
        
        summary = f"Apresentação com {total_slides} slides.\n\n"
        
        if slide_titles:
            summary += "Principais tópicos abordados:\n"
            for i, title in enumerate(slide_titles[:5], 1):  # Primeiros 5 títulos
                summary += f"{i}. {title}\n"
            
            if len(slide_titles) > 5:
                summary += f"... e mais {len(slide_titles) - 5} tópicos.\n"
        
        if global_analysis.get("overall_summary"):
            summary += f"\nContexto: {global_analysis['overall_summary']}"
        
        return summary
