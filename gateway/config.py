from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Intelligent API Gateway"
    API_V1_STR: str = "/api/v1"
    
    # Environment configs
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Redis configurations
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0

    # Downstream simulator (overridden in Docker via environment variable)
    SIMULATOR_URL: str = "http://localhost:8001"
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
