FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv pip install --system -r <(uv pip compile pyproject.toml -o -)

COPY src/ ./src/
COPY .env .

RUN mkdir -p /app/data/chroma

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
