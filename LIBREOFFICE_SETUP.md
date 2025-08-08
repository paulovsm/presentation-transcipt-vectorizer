# Instalação do LibreOffice para Conversão de PowerPoint

## 🎯 Por que LibreOffice?

O LibreOffice é a ferramenta recomendada para conversão de arquivos PowerPoint (.pptx/.ppt) em imagens de alta qualidade. Sem ele, o sistema usa um método de fallback limitado que:

- Só funciona com slides que já contêm imagens
- Não renderiza texto, gráficos ou elementos visuais
- Pode falhar com formatos específicos (como WMF)

## 📦 Instalação

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install libreoffice
```

### CentOS/RHEL/Fedora
```bash
# CentOS/RHEL
sudo yum install libreoffice

# Fedora
sudo dnf install libreoffice
```

### Alpine Linux (Docker)
```bash
apk add --no-cache libreoffice
```

### Docker com Ubuntu Base
```dockerfile
FROM ubuntu:20.04

# Instala LibreOffice
RUN apt-get update && \
    apt-get install -y libreoffice && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Resto da configuração...
```

### macOS
```bash
# Usando Homebrew
brew install --cask libreoffice

# Ou baixar direto do site
# https://www.libreoffice.org/download/download/
```

### Windows
1. Baixar do site oficial: https://www.libreoffice.org/download/download/
2. Executar o instalador
3. Adicionar ao PATH do sistema (opcional)

## 🧪 Teste da Instalação

Após instalar, teste se está funcionando:

```bash
# Teste básico
libreoffice --version

# Teste de conversão
libreoffice --headless --convert-to png --outdir /tmp /path/to/presentation.pptx
```

## 🐳 Docker Compose Atualizado

Se estiver usando Docker, atualize o Dockerfile:

```dockerfile
FROM python:3.10-slim

# Instala dependências do sistema incluindo LibreOffice
RUN apt-get update && \
    apt-get install -y \
    libreoffice \
    fonts-liberation \
    fontconfig \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Resto da configuração...
COPY requirements.txt .
RUN pip install -r requirements.txt

# Configuração da aplicação...
```

## ⚙️ Configuração Avançada

### Fontes Adicionais (Recomendado)
```bash
# Ubuntu/Debian
sudo apt-get install fonts-liberation fonts-dejavu fonts-droid-fallback

# Para melhor compatibilidade com PowerPoint
sudo apt-get install ttf-mscorefonts-installer
```

### Variáveis de Ambiente
```bash
# Para ambientes headless
export DISPLAY=:99
export LIBGL_ALWAYS_SOFTWARE=1
```

## 🔧 Solução de Problemas

### LibreOffice não encontrado
- Verifique se está no PATH: `which libreoffice`
- No Docker, garanta que foi instalado na imagem
- Teste com caminho completo: `/usr/bin/libreoffice`

### Erro de permissões
```bash
# Crie diretório de configuração
mkdir -p ~/.config/libreoffice
chmod 755 ~/.config/libreoffice
```

### Timeout na conversão
- Aumente o timeout no código (atualmente 120s)
- Verifique se há recursos suficientes (RAM/CPU)

### Qualidade baixa das imagens
- Use DPI maior na configuração
- Verifique configuração `image_quality=high`

## 📊 Comparação: Com vs Sem LibreOffice

| Aspecto | Com LibreOffice | Sem LibreOffice (Fallback) |
|---------|----------------|----------------------------|
| **Qualidade** | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Compatibilidade** | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Renderização de Texto** | ✅ | ❌ |
| **Gráficos/Tabelas** | ✅ | ❌ |
| **Layouts Complexos** | ✅ | ❌ |
| **Velocidade** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Dependências** | LibreOffice | Nenhuma |

## 🎯 Resultado Esperado

Após a instalação, você deve ver no log:
```
INFO: Convertendo PowerPoint para imagens usando LibreOffice
✅ Extração concluída em X.Xs
📊 Total de slides: XX
```

Ao invés de:
```
WARNING: LibreOffice não encontrado, usando método alternativo
INFO: Usando método de fallback para conversão de slides
```

## 📝 Notas Importantes

1. **Ambiente de Produção**: LibreOffice é essencial para qualidade profissional
2. **Desenvolvimento Local**: Fallback pode ser suficiente para testes básicos
3. **Performance**: LibreOffice adiciona ~2-3s ao tempo total de processamento
4. **Recursos**: Requer ~200-500MB RAM adicional durante conversão

## 🔄 Próximos Passos

Após instalar o LibreOffice:
1. Execute novamente o teste: `python test_slide_extraction.py`
2. Verifique se não há mais warnings sobre LibreOffice
3. Compare a qualidade das imagens geradas
4. Teste com diferentes tipos de apresentações
