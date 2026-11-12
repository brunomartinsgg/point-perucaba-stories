"""Configurações e segurança de variáveis de ambiente do projeto."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ASSETS_DIR = BASE_DIR / "assets" / "stories"
DEFAULT_HISTORY_FILE = BASE_DIR / "data" / "publication_history.json"
DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_META_API_VERSION = "v22.0"
DEFAULT_IMAGE_BASE_URL = "https://brunomartinsgg.github.io/point-perucaba-stories/assets/stories"


def mask_secret(secret: str | None) -> str:
    """Mascaramento seguro para impedir vazamento de tokens nos logs."""
    if not secret:
        return "<vazio>"
    cleaned = secret.strip()
    if len(cleaned) <= 8:
        return "****"
    return f"{cleaned[:4]}...{cleaned[-4:]}"


class SensitiveDataFilter(logging.Filter):
    """Filtro de log que oculta automaticamente o token caso apareça em mensagens ou exceções."""

    def __init__(self, secrets: list[str | None]) -> None:
        super().__init__()
        self._secrets = [s.strip() for s in secrets if s and len(s.strip()) > 4]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for secret in self._secrets:
            if secret in msg:
                msg = msg.replace(secret, mask_secret(secret))
        record.msg = msg
        record.args = ()
        return True


@dataclass(frozen=True)
class Settings:
    """Parâmetros de configuração carregados do ambiente."""

    meta_access_token: str
    meta_ig_user_id: str
    image_base_url: str = DEFAULT_IMAGE_BASE_URL
    meta_api_version: str = DEFAULT_META_API_VERSION
    timezone_name: str = DEFAULT_TIMEZONE
    dry_run: bool = False
    assets_dir: Path = DEFAULT_ASSETS_DIR
    history_file: Path = DEFAULT_HISTORY_FILE

    @classmethod
    def from_env(cls, override_dry_run: bool | None = None) -> Settings:
        """Carrega configurações a partir de variáveis de ambiente."""
        raw_dry_run = os.getenv("DRY_RUN", "false").strip().lower()
        env_dry_run = raw_dry_run in {"1", "true", "yes", "sim", "on"}
        dry_run = override_dry_run if override_dry_run is not None else env_dry_run

        image_base_url = (
            os.getenv("IMAGE_BASE_URL", DEFAULT_IMAGE_BASE_URL).strip().rstrip("/")
            or DEFAULT_IMAGE_BASE_URL
        )
        meta_api_version = (
            os.getenv("META_API_VERSION", DEFAULT_META_API_VERSION).strip()
            or DEFAULT_META_API_VERSION
        )
        timezone_name = (
            os.getenv("TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
        )

        assets_dir_env = os.getenv("ASSETS_DIR", "").strip()
        assets_dir = Path(assets_dir_env) if assets_dir_env else DEFAULT_ASSETS_DIR

        history_file_env = os.getenv("HISTORY_FILE", "").strip()
        history_file = (
            Path(history_file_env) if history_file_env else DEFAULT_HISTORY_FILE
        )

        return cls(
            meta_access_token=os.getenv("META_ACCESS_TOKEN", "").strip(),
            meta_ig_user_id=os.getenv("META_IG_USER_ID", "").strip(),
            image_base_url=image_base_url,
            meta_api_version=meta_api_version,
            timezone_name=timezone_name,
            dry_run=dry_run,
            assets_dir=assets_dir,
            history_file=history_file,
        )

    def validate_for_execution(self, require_remote: bool = True) -> None:
        """Valida se as credenciais e URLs obrigatórias estão preenchidas."""
        if require_remote:
            missing: list[str] = []
            if not self.meta_access_token:
                missing.append("META_ACCESS_TOKEN")
            if not self.meta_ig_user_id:
                missing.append("META_IG_USER_ID")
            if not self.image_base_url:
                missing.append("IMAGE_BASE_URL")
            if missing:
                raise ValueError(
                    f"Variáveis de ambiente obrigatórias ausentes: {', '.join(missing)}"
                )
            if not self.image_base_url.startswith("https://"):
                raise ValueError(
                    "IMAGE_BASE_URL deve utilizar protocolo seguro (https://)."
                )

