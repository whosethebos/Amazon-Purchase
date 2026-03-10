# backend/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama
    ollama_model: str = "qwen3:14b"
    ollama_base_url: str = "http://localhost:11434"

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Scraping
    amazon_batch_size: int = 5
    max_confirmation_iterations: int = 3
    max_reviews_per_product: int = 20

    # App
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
