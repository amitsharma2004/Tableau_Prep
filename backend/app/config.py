from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./app_metadata.db"
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    encryption_key: str = ""

    join_anomaly_ratio: float = 1.5
    schema_sample_row_limit: int = 20
    hyper_output_dir: str = "./hyper_output"
    execute_chunk_size: int = 50_000


settings = Settings()
