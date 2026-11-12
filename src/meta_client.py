"""Cliente oficial para integração com a Meta Instagram Graph API (Content Publishing)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from src.config import mask_secret

logger = logging.getLogger(__name__)

GRAPH_API_BASE_URL = "https://graph.facebook.com"


class MetaAPIError(Exception):
    """Erro base de comunicação ou resposta da Meta Graph API."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: int | None = None,
        error_subcode: int | None = None,
        fbtrace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fbtrace_id = fbtrace_id


class MetaAuthenticationError(MetaAPIError):
    """Erro específico de autenticação (token expirado, inválido ou sem permissão)."""


@dataclass(frozen=True)
class MetaPublishResult:
    """Resultado retornado após criação de container e publicação do Story."""

    container_id: str
    media_id: str


class MetaGraphClient:
    """Cliente HTTP para publicação de Stories via Instagram Graph API."""

    def __init__(
        self,
        access_token: str,
        ig_user_id: str,
        api_version: str = "v22.0",
        timeout_seconds: int = 30,
        session: requests.Session | None = None,
    ) -> None:
        if not access_token or not access_token.strip():
            raise ValueError("META_ACCESS_TOKEN não pode ser vazio.")
        if not ig_user_id or not ig_user_id.strip():
            raise ValueError("META_IG_USER_ID não pode ser vazio.")

        self._access_token = access_token.strip()
        self._ig_user_id = ig_user_id.strip()
        self._api_version = api_version.strip().lstrip("/")
        self._timeout = timeout_seconds
        self._session = session or requests.Session()

    @property
    def base_url(self) -> str:
        # Tokens gerados via 'Instagram Login' começam com 'IG' e usam graph.instagram.com;
        # Tokens gerados via 'Facebook Login' começam com 'EAA' e usam graph.facebook.com.
        host = (
            "https://graph.instagram.com"
            if self._access_token.startswith("IG")
            else GRAPH_API_BASE_URL
        )
        return f"{host}/{self._api_version}"

    def _sanitize_text(self, text: str) -> str:
        """Garante que o token de acesso nunca apareça em mensagens de erro."""
        if self._access_token and self._access_token in text:
            return text.replace(self._access_token, mask_secret(self._access_token))
        return text

    def _handle_response(self, response: requests.Response, context_action: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            safe_body = self._sanitize_text(response.text[:300])
            raise MetaAPIError(
                f"Resposta não-JSON da Meta durante '{context_action}' "
                f"(HTTP {response.status_code}): {safe_body}",
                status_code=response.status_code,
            ) from exc

        if response.status_code >= 400 or "error" in payload:
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            message = self._sanitize_text(str(err.get("message", "Erro desconhecido da Meta API")))
            code = err.get("code")
            subcode = err.get("error_subcode")
            fbtrace = err.get("fbtrace_id")

            # Código 190 = OAuthException (token expirado/inválido); 10 ou 200 = permissão insuficiente
            if code in {190, 10, 200, 102} or response.status_code in {401, 403}:
                hint = (
                    "Verifique se o META_ACCESS_TOKEN está válido/não expirou e se possui as permissões "
                    "'instagram_basic' e 'instagram_content_publish'."
                )
                raise MetaAuthenticationError(
                    f"Falha de autenticação/permissão na Meta durante '{context_action}': "
                    f"{message} (code={code}, subcode={subcode}). {hint}",
                    status_code=response.status_code,
                    error_code=code,
                    error_subcode=subcode,
                    fbtrace_id=fbtrace,
                )

            raise MetaAPIError(
                f"Erro da Meta Graph API durante '{context_action}': "
                f"{message} (HTTP={response.status_code}, code={code}, subcode={subcode})",
                status_code=response.status_code,
                error_code=code,
                error_subcode=subcode,
                fbtrace_id=fbtrace,
            )

        if not isinstance(payload, dict):
            raise MetaAPIError(
                f"Formato de resposta inesperado da Meta durante '{context_action}'.",
                status_code=response.status_code,
            )

        return payload

    def verify_account_access(self) -> dict[str, Any]:
        """
        Valida se o token e o IG_USER_ID são válidos consultando os dados básicos da conta.
        Não realiza nenhuma publicação.
        """
        url = f"{self.base_url}/{self._ig_user_id}"
        params = {
            "fields": "id,username",
            "access_token": self._access_token,
        }
        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
        except requests.RequestException as exc:
            raise MetaAPIError(
                f"Erro de conexão ao validar credenciais na Meta: {self._sanitize_text(str(exc))}"
            ) from exc

        return self._handle_response(response, context_action="verificação de conta/autenticação")

    def create_story_container(self, image_url: str) -> str:
        """
        Etapa 1 da publicação: Cria o container de mídia para Story (`media_type=STORIES`).
        Endpoint: POST /{ig-user-id}/media
        """
        url = f"{self.base_url}/{self._ig_user_id}/media"
        data = {
            "image_url": image_url,
            "media_type": "STORIES",
            "access_token": self._access_token,
        }
        try:
            response = self._session.post(url, data=data, timeout=self._timeout)
        except requests.RequestException as exc:
            raise MetaAPIError(
                f"Erro de rede ao criar container de Story na Meta: {self._sanitize_text(str(exc))}"
            ) from exc

        payload = self._handle_response(response, context_action="criação de container (media_type=STORIES)")
        container_id = payload.get("id")
        if not container_id:
            raise MetaAPIError(
                "A Meta Graph API respondeu sem um ID de container ('id' ausente).",
                status_code=response.status_code,
            )
        return str(container_id)

    def wait_for_container_ready(
        self,
        container_id: str,
        max_attempts: int = 5,
        poll_interval_seconds: float = 2.0,
    ) -> str:
        """
        Consulta o status do container (`GET /{container-id}?fields=status_code`)
        até que esteja `FINISHED` (ou caso a API não retorne status_code para imagens simples).
        """
        url = f"{self.base_url}/{container_id}"
        params = {
            "fields": "status_code,status",
            "access_token": self._access_token,
        }

        for attempt in range(1, max_attempts + 1):
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
            except requests.RequestException as exc:
                raise MetaAPIError(
                    f"Erro de rede ao consultar status do container {container_id}: "
                    f"{self._sanitize_text(str(exc))}"
                ) from exc

            payload = self._handle_response(response, context_action="consulta de status do container")
            status_code = str(payload.get("status_code", "FINISHED")).upper()

            if status_code in {"FINISHED", "PUBLISHED"}:
                return status_code

            if status_code in {"ERROR", "EXPIRED"}:
                status_detail = payload.get("status", "Sem detalhes adicionais")
                raise MetaAPIError(
                    f"O processamento do container {container_id} falhou na Meta: "
                    f"status_code={status_code} ({status_detail})"
                )

            logger.info(
                "Container %s ainda em processamento (status_code=%s, tentativa %d/%d). Aguardando...",
                container_id,
                status_code,
                attempt,
                max_attempts,
            )
            if attempt < max_attempts and poll_interval_seconds > 0:
                time.sleep(poll_interval_seconds)

        raise MetaAPIError(
            f"Tempo limite excedido aguardando o container {container_id} ficar pronto para publicação."
        )

    def publish_container(self, container_id: str) -> str:
        """
        Etapa 2 da publicação: Publica efetivamente o container criado.
        Endpoint: POST /{ig-user-id}/media_publish
        """
        url = f"{self.base_url}/{self._ig_user_id}/media_publish"
        data = {
            "creation_id": container_id,
            "access_token": self._access_token,
        }
        try:
            response = self._session.post(url, data=data, timeout=self._timeout)
        except requests.RequestException as exc:
            raise MetaAPIError(
                f"Erro de rede ao publicar container {container_id} na Meta: "
                f"{self._sanitize_text(str(exc))}"
            ) from exc

        payload = self._handle_response(response, context_action="publicação do Story (media_publish)")
        media_id = payload.get("id")
        if not media_id:
            raise MetaAPIError(
                "A Meta Graph API respondeu ao media_publish sem um 'id' de mídia publicada.",
                status_code=response.status_code,
            )
        return str(media_id)

    def publish_story_image(
        self,
        image_url: str,
        poll_interval_seconds: float = 2.0,
    ) -> MetaPublishResult:
        """Executa o fluxo completo oficial de publicação de Story (Container -> Status -> Publish)."""
        logger.info("Etapa Meta 1/3: Criando container de mídia (media_type=STORIES)...")
        container_id = self.create_story_container(image_url=image_url)
        logger.info("Container criado com sucesso: container_id=%s", container_id)

        logger.info("Etapa Meta 2/3: Verificando disponibilidade do container...")
        self.wait_for_container_ready(
            container_id=container_id,
            poll_interval_seconds=poll_interval_seconds,
        )

        logger.info("Etapa Meta 3/3: Publicando container no Instagram Stories (media_publish)...")
        media_id = self.publish_container(container_id=container_id)
        logger.info("Story publicado com sucesso! media_id=%s", media_id)

        return MetaPublishResult(container_id=container_id, media_id=media_id)

