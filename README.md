# Serviço de Transcrição de Apresentações PowerPoint/PDF

Sistema baseado no audio-transcript-vectorizer para processar apresentações PowerPoint e PDF usando Google Gemini Vision AI com **análise visual avançada**.

## 🆕 **Nova Versão - Análise Visual**

Esta versão foi completamente refatorada para usar **análise visual de slides** ao invés de extração de elementos estruturais, proporcionando:

- **🎯 Maior Precisão**: Análise contextual de layouts e designs
- **🖼️ Compatibilidade Total**: Funciona com qualquer tipo de slide ou formato
- **🧠 IA Avançada**: Aproveitamento total das capacidades do Gemini Vision
- **⚡ Performance Otimizada**: Processamento paralelo e conversão inteligente

## Características

- **Extração Visual**: Converte slides em imagens para análise com Gemini Vision
- **Múltiplos Formatos**: Suporte para PPTX, PPT e PDF
- **Análise Inteligente**: Identificação automática de layouts, texto e elementos visuais
- **Qualidade Configurável**: 3 níveis de qualidade de imagem (high/medium/low)
- **Busca Semântica**: Base vectorizada com ChromaDB
- **Integração Dify**: Upload automático para plataforma Dify.ai
- **Storage Cloud**: Firestore para persistência
- **Limpeza Automática**: Gestão inteligente de arquivos temporários

## Arquitetura

```
ppt-transcript-service/
├── src/
│   ├── api/              # Endpoints FastAPI
│   ├── config/           # Configurações
│   ├── models/           # Schemas Pydantic
│   ├── processing/       # Extração e processamento
│   ├── services/         # Orquestração
│   ├── storage/          # Firestore e ChromaDB
│   └── integrations/     # Dify.ai
├── main.py              # Ponto de entrada
├── requirements.txt     # Dependências
└── README.md           # Este arquivo
```

## Instalação

```bash
# Clone e instale dependências
pip install -r requirements.txt

# Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais
```

## Configuração

### Variáveis de Ambiente

```env
# Google Cloud
GOOGLE_CLOUD_PROJECT=seu-projeto-gcp
GOOGLE_APPLICATION_CREDENTIALS=caminho/para/credentials.json
VERTEX_AI_LOCATION=us-central1
GEMINI_MODEL=gemini-2.5-flash

# ChromaDB
CHROMA_DB_PATH=./data/chroma_db
CHROMA_COLLECTION_NAME=presentation_transcriptions

# API
API_HOST=0.0.0.0
API_PORT=8001
API_RELOAD=true

# Dify.ai
DIFY_API_URL=https://api.dify.ai/v1
DIFY_API_KEY=sua-chave-dify
DIFY_DATASET_ID=seu-dataset-id
DIFY_WORKFLOW_API_KEY=sua-chave-workflow

# Upload e Processamento
MAX_FILE_SIZE_MB=100
ALLOWED_PRESENTATION_FORMATS=pptx,ppt,pdf
SLIDES_PER_CHUNK=3
TEMP_EXTRACTION_DIRECTORY=./data/temp_extraction

# 🆕 Configurações de Análise Visual
IMAGE_QUALITY=high              # high, medium, low
MAX_IMAGE_SIZE_MB=20           # Limite para análise
```

### Configurações de Qualidade

| Configuração | DPI | Qualidade JPEG | Uso Recomendado |
|-------------|-----|----------------|-----------------|
| `high` | 300 | 95% | Produção, análise detalhada |
| `medium` | 200 | 85% | Desenvolvimento, testes |
| `low` | 150 | 75% | Prototipagem, recursos limitados |

## 🔧 Dependências do Sistema

### LibreOffice (Recomendado)
Para conversão de PowerPoint com máxima qualidade:

```bash
# Ubuntu/Debian
sudo apt-get install libreoffice

# CentOS/RHEL
sudo yum install libreoffice

# Alpine (Docker)
apk add libreoffice
```

**⚠️ Sem LibreOffice**: O sistema usará método de fallback limitado
- ✅ Funciona para slides com imagens existentes
- ❌ Não renderiza texto, gráficos ou layouts
- 📖 Veja `LIBREOFFICE_SETUP.md` para instruções detalhadas

### Fontes Adicionais (Opcional)
```bash
# Para melhor compatibilidade
sudo apt-get install fonts-liberation fonts-dejavu
```
ALLOWED_PRESENTATION_FORMATS=pptx,ppt,pdf
UPLOAD_DIRECTORY=./data/uploads
TEMP_EXTRACTION_DIRECTORY=./data/temp_extraction

# Processing
SLIDES_PER_CHUNK=5
OVERLAP_SLIDES=1
MAX_IMAGE_SIZE_MB=20
IMAGE_QUALITY=high

# Security
JWT_SECRET_KEY=sua-chave-secreta
```

## Uso

### Iniciar Servidor

```bash
python main.py
```

### API Endpoints

#### Upload de Apresentação
```http
POST /upload
Content-Type: multipart/form-data

{
  "file": arquivo.pptx,
  "presentation_title": "Título da Apresentação",
  "author": "Nome do Autor",
  "presentation_type": "business",
  "language_code": "pt-BR",
  "detailed_analysis": true,
  "dataset_name": "meu-dataset"
}
```

#### Buscar Transcrições
```http
POST /search
Content-Type: application/json

{
  "query": "governança de backlog",
  "limit": 10,
  "similarity_threshold": 0.7,
  "search_in_slides": true
}
```

#### Obter Transcrição
```http
GET /transcriptions/{transcription_id}
```

#### Análise Customizada
```http
POST /transcriptions/{transcription_id}/analyze
Content-Type: application/json

{
  "analysis_type": "business_analysis",
  "custom_prompt": "Analise os riscos desta apresentação"
}
```

## Schema de Dados

### Estrutura JSON da Transcrição

```json
{
  "presentation_metadata": {
    "title": "BACKLOG GOVERNANCE",
    "author": "ACCENTURE VENTURES",
    "date": "2024-01-01T00:00:00Z",
    "source_filename": "presentation.pptx",
    "total_slides": 10,
    "presentation_type": "business",
    "language": "pt-BR"
  },
  "overall_summary": "Resumo executivo da apresentação...",
  "key_concepts": ["Agile", "Design Thinking", "Backlog Governance"],
  "narrative_flow_analysis": "Análise do fluxo narrativo...",
  "slides": [
    {
      "slide_number": 1,
      "slide_title": "BACKLOG MANAGEMENT",
      "layout_type": "Fluxograma de Processo",
      "slide_summary": "Resumo do slide...",
      "elements": [
        {
          "element_id": "slide1_element1",
          "element_type": "diagram",
          "semantic_analysis": {
            "description": "Descrição do elemento",
            "purpose_and_meaning": "Propósito do elemento",
            "process_steps": ["passo1", "passo2"]
          },
          "position": {"x": 100, "y": 50, "width": 300, "height": 200},
          "relationships_to_other_elements": [...]
        }
      ],
      "inter_slide_relationship": {
        "to_previous": "Relação com slide anterior",
        "to_next": "Preparação para próximo slide"
      }
    }
  ]
}
```

## Processamento

### Pipeline de Processamento

1. **Upload & Validação**: Verifica formato e tamanho
2. **Extração de Slides**: 
   - PPT/PPTX: python-pptx para texto + conversão para imagens
   - PDF: PyMuPDF para texto e renderização de páginas
3. **Análise Global**: Gemini processa toda a apresentação
4. **Análise Detalhada**: Cada slide processado individualmente
5. **Geração de Resumo**: Síntese executiva com Gemini
6. **Armazenamento**: ChromaDB para busca + Firestore para persistência
7. **Integração Dify**: Upload para plataforma (opcional)

### Formatos Suportados

- **PowerPoint**: .pptx, .ppt
- **PDF**: Especialmente PDFs exportados de apresentações
- **Tamanho máximo**: 100MB (configurável)
- **Qualidade de imagem**: Ajustável (high/medium/low)

## Integração com Gemini

### Prompts Especializados

- **Análise Global**: Visão geral da apresentação completa
- **Análise de Slide**: Processamento detalhado por slide
- **Análise de Elementos**: Interpretação de diagramas, gráficos, etc.

### Configuração Multimodal

- Suporte a texto + imagem simultâneo
- Otimização de imagens para API (redimensionamento, compressão)
- Processamento em lotes para eficiência

## Monitoramento

### Métricas Disponíveis

```http
GET /stats
```

Retorna:
- Total de apresentações processadas
- Breakdown por status
- Tempo médio de processamento
- Estatísticas da base vectorizada

### Logs

- Arquivo: `./logs/app.log`
- Níveis: DEBUG, INFO, WARNING, ERROR
- Rotação automática

## 🧪 Testes

### Teste Completo do Sistema
```bash
python test_service.py
```

### 🆕 Teste da Extração Visual
```bash
python test_slide_extraction.py
```

**Funcionalidades testadas:**
- ✅ Conversão de slides para imagens
- ✅ Diferentes configurações de qualidade
- ✅ Tratamento de erros e formatos
- ✅ Limpeza de arquivos temporários
- ✅ Validação de imagens
- ✅ Métodos fallback

### Exemplo de Saída do Teste
```
🧪 Testando SlideExtractionService com análise visual
✅ Extração concluída em 4.65s
📊 Total de slides: 42
🖼️  Imagem: 3301x2474 (alta qualidade)
🧹 Todos os arquivos temporários removidos
```

## Desenvolvimento

### Estrutura de Código

- **Modular**: Cada componente em módulo separado
- **Async**: Operações assíncronas para performance
- **Typed**: Type hints completos com Pydantic
- **Tested**: Testes unitários e integração

### Extensibilidade

- Facilmente extensível para novos formatos
- Plugins para análises específicas
- Integração com outras plataformas IA

## Limitações Conhecidas

- PowerPoint: Extração de imagens limitada (requer LibreOffice para conversão completa)
- Gemini: Rate limits da API
- Tamanho: Apresentações muito grandes podem exceder limites de token

## Próximos Passos

- [ ] Melhor extração de imagens do PowerPoint
- [ ] Cache de embeddings
- [ ] API de webhooks para notificações
- [ ] Interface web para upload
- [ ] Análises pré-definidas (business, academic, etc.)
- [ ] Export para diferentes formatos (Markdown, Word, etc.)
