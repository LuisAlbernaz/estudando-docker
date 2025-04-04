FROM python:3.9

WORKDIR /app

# Instalar as dependências do backend
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copiar o código do backend
COPY . .

# Rodar a aplicação
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]