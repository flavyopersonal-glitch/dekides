# 1. Usa uma imagem oficial do Python leve (slim)
FROM python:3.11-slim

# 2. Define o diretório de trabalho dentro do container do Linux
WORKDIR /app

# 3. Evita que o Python escreva arquivos .pyc no disco e força o output do log direto no terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 4. Instala dependências do sistema caso alguma biblioteca precise compilar algo (segurança)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copia apenas o arquivo de dependências primeiro (otimiza o cache do Docker)
COPY requirements.txt .

# 6. Instala as bibliotecas do Python dentro do container
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 7. Copia o restante do código do projeto para dentro do container
COPY . .

# 8. Informa a porta que o container vai expor (o Render vai ler essa porta)
EXPOSE 8000

# 9. Comando para rodar a API usando o Uvicorn (sem o --reload, pois em produção não precisa)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]