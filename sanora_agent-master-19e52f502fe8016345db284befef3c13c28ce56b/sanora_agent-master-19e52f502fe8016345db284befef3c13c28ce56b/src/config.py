import os
import yaml
from typing import Dict, Any, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LangGraphAppConfig(BaseModel):
    name: str
    description: str
    api_key: str
    model_provider: str
    graph_type: str
    enabled: bool = True
    max_history: int = 50  # Default max history
    enable_router_output_node: bool = False


class ModelConfig(BaseModel):
    name: str
    base_url: str
    max_tokens: int
    temperature: float = 0.7
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0


class ServerConfig(BaseModel):
    default_model: str
    default_graph: str
    stream_timeout: int = 30
    max_concurrent_requests: int = 100


class APIConfig(BaseModel):
    rate_limit: int = 100
    enable_cors: bool = True
    cors_origins: list = ["*"]


class AuthConfig(BaseModel):
    require_api_key: bool = True
    default_fallback: bool = False


class PostgresConfig(BaseModel):
    enabled: bool = False
    host: str = "localhost"
    port: int = 5432
    database: str = "car_agent_db"
    username: str = "lg_user"
    password: str = "dafang_password"
    connection_string: Optional[str] = None


class DatabaseConfig(BaseModel):
    postgres: PostgresConfig = PostgresConfig()
    mouth_postgres: PostgresConfig = PostgresConfig()


class Config:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self._config_data = self._load_config()

        # Parse configurations
        self.langgraph_apps = self._parse_langgraph_apps()
        self.models = self._parse_models()
        self.server = ServerConfig(**self._config_data.get("server", {}))
        self.api = APIConfig(**self._config_data.get("api", {}))
        self.auth = AuthConfig(**self._config_data.get("auth", {}))
        self.database = DatabaseConfig(**self._config_data.get("database", {}))

        # Load API keys from environment
        self.api_keys = self._load_api_keys()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file {self.config_path} not found")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")

    def _parse_langgraph_apps(self) -> Dict[str, LangGraphAppConfig]:
        """Parse LangGraph application configurations"""
        apps = {}
        apps_config = self._config_data.get("langgraph_apps", {})

        for app_id, app_data in apps_config.items():
            apps[app_id] = LangGraphAppConfig(**app_data)

        return apps

    def _parse_models(self) -> Dict[str, ModelConfig]:
        """Parse model configurations"""
        models = {}
        models_config = self._config_data.get("models", {})

        for model_name, model_data in models_config.items():
            models[model_name] = ModelConfig(**model_data)

        return models

    def _load_api_keys(self) -> Dict[str, str]:
        """
        Load API keys from environment variables.
        The environment variable name is dynamically generated from the model key in config.yaml.
        Example: model key 'qwen3-flash' maps to environment variable 'QWEN3-FLASH_API_KEY'.

        Special case: All 'openrouter-*' models use a single 'OPENROUTER_API_KEY' environment variable.
        """
        api_keys = {}

        # Dynamically generate the key mapping from the model configurations
        key_mapping = {}
        for model_name in self.models.keys():
            # Special handling for Openrouter models - all use the same API key
            if model_name.startswith('openrouter-'):
                key_mapping[model_name] = "OPENROUTER_API_KEY"
            else:
                key_mapping[model_name] = f"{model_name.upper().replace('-', '_')}_API_KEY"

        print(f"Model to Env Var mapping: {key_mapping}")

        for model_name, env_var in key_mapping.items():
            api_key = os.getenv(env_var)
            if api_key:
                api_keys[model_name] = api_key

        return api_keys

    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """Get configuration for a specific model"""
        return self.models.get(model_name)

    def get_api_key(self, model_name: str) -> Optional[str]:
        """Get API key for a specific model"""
        return self.api_keys.get(model_name)

    def get_default_model(self) -> str:
        """Get the default model name"""
        return self.server.default_model

    def get_default_graph(self) -> str:
        """Get the default graph name"""
        return self.server.default_graph

    def list_available_models(self) -> list:
        """List all available models"""
        return list(self.models.keys())

    def is_model_available(self, model_name: str) -> bool:
        """Check if a model is available and has API key"""
        return model_name in self.models and model_name in self.api_keys

    # LangGraph App methods
    def get_langgraph_app(self, app_id: str) -> Optional[LangGraphAppConfig]:
        """Get LangGraph app configuration by ID"""
        return self.langgraph_apps.get(app_id)

    def get_langgraph_app_by_api_key(
        self, api_key: str
    ) -> Optional[tuple[str, LangGraphAppConfig]]:
        """Get LangGraph app configuration by API key"""
        for app_id, app_config in self.langgraph_apps.items():
            if app_config.api_key == api_key and app_config.enabled:
                return app_id, app_config
        return None

    def list_enabled_langgraph_apps(self) -> Dict[str, LangGraphAppConfig]:
        """List all enabled LangGraph applications"""
        return {
            app_id: app_config
            for app_id, app_config in self.langgraph_apps.items()
            if app_config.enabled
        }

    def validate_langgraph_api_key(self, api_key: str) -> bool:
        """Validate if API key belongs to an enabled LangGraph app"""
        return self.get_langgraph_app_by_api_key(api_key) is not None


# Global configuration instance
config = Config()
