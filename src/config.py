from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Manages all application settings. It automatically reads from
    environment variables or a .env file.
    """
    # Tell pydantic to load variables from a .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    OPENAI_API_KEY: str

    # Define your settings here
    FITBIT_CLIENT_ID: str
    FITBIT_CLIENT_SECRET: str
    APP_SECRET_KEY: str
    REDIRECT_URL: str 

# Create a single, reusable instance of the settings
settings = Settings()