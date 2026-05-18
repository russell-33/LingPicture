from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.6-flash"
    qwen_tokenizer_model: str = "Qwen/Qwen3-8B"
    qwen_tokenizer_local_only: bool = False

    # Rerank
    rerank_model: str = "qwen3-rerank"
    rerank_api_key: str = ""
    rerank_base_url: str = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"

    # Embedding
    embedding_model: str = "text-embedding-v4"
    embedding_api_key: str = ""
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # ChromaDB
    chroma_data_dir: str = "./data/chroma"

    # Java backend
    java_backend_url: str = "http://localhost:8123/api"
    ai_internal_token: str = ""

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 4

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "yp_picture"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
