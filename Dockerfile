FROM python:3.12-slim

# Evita arquivos .pyc e garante logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências do sistema e fuso horário
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Configura o fuso horário para horário de Brasília
ENV TZ=America/Sao_Paulo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Instala dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia os arquivos do projeto
COPY . .

# Expõe a porta da aplicação
EXPOSE 5000

# Executa com Gunicorn para produção
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "run:app"]
