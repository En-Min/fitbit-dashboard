import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./fitbit_data.db")
    FITBIT_CLIENT_ID: str = os.getenv("FITBIT_CLIENT_ID", "")
    FITBIT_CLIENT_SECRET: str = os.getenv("FITBIT_CLIENT_SECRET", "")
    FITBIT_REDIRECT_URI: str = os.getenv(
        "FITBIT_REDIRECT_URI", "http://localhost:8000/api/auth/callback"
    )
    FITBIT_AUTH_URL: str = "https://www.fitbit.com/oauth2/authorize"
    FITBIT_TOKEN_URL: str = "https://api.fitbit.com/oauth2/token"
    FITBIT_API_BASE: str = "https://api.fitbit.com"
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")


settings = Settings()
