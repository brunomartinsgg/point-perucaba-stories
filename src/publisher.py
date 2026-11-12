"""Orquestrador do fluxo de publicação diária de Instagram Stories."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from src.config import Settings
from src.image_selector import (
    SelectedImage,
    normalize_assets_directory,
    select_daily_image,
)
from src.image_validator import validate_local_image, validate_remote_image_url
from src.meta_client import MetaGraphClient
from src.publication_log import PublicationLogStore, PublicationRecord
from src.scheduler import ScheduleContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionOutcome:
    """Resultado consolidado da execução do fluxo."""

    status: str  # "SUCCESS", "SKIPPED_DUPLICATE", "DRY_RUN"
    context: ScheduleContext
    selected_image: SelectedImage
    container_id: str | None = None
    media_id: str | None = None
    message: str = ""


class StoryPublisher:
    """Orquestra a validação, prevenção de duplicidade e publicação do Story do dia."""

    def __init__(
        self,
        settings: Settings,
        log_store: PublicationLogStore | None = None,
        meta_client: MetaGraphClient | None = None,
    ) -> None:
        self.settings = settings
        self.log_store = log_store or PublicationLogStore(settings.history_file)
        self._meta_client = meta_client

    def _get_meta_client(self) -> MetaGraphClient:
        if self._meta_client is not None:
            return self._meta_client
        return MetaGraphClient(
            access_token=self.settings.meta_access_token,
            ig_user_id=self.settings.meta_ig_user_id,
            api_version=self.settings.meta_api_version,
        )

    def run(
        self,
        reference_dt: datetime | None = None,
        skip_remote_url_check: bool = False,
    ) -> ExecutionOutcome:
        """
        Executa o ciclo completo de publicação diária:
        1. Identifica data e dia da semana em `America/Sao_Paulo`.
        2. Seleciona a arte correspondente ao dia.
        3. Verifica controle de duplicidade para a data atual.
        4. Valida a imagem local (existência, tamanho, formato JPEG).
        5. Se `dry_run=True`, interrompe antes de criar container/publicar na Meta.
        6. Valida a URL pública HTTPS da imagem e publica na Meta Graph API.
        7. Registra o resultado no histórico persistente.
        """
        normalize_assets_directory(self.settings.assets_dir)

        context, selected = select_daily_image(
            assets_dir=self.settings.assets_dir,
            image_base_url=self.settings.image_base_url,
            timezone_name=self.settings.timezone_name,
            reference_dt=reference_dt,
        )

        logger.info(
            "Iniciando processamento | Data=%s (%s) | Horário=%s | Imagem=%s | Modo=%s",
            context.date_iso,
            context.weekday_name,
            context.timestamp_iso,
            selected.filename,
            "SIMULAÇÃO (DRY-RUN)" if self.settings.dry_run else "PRODUÇÃO",
        )

        # 1. Controle de duplicidade
        existing = self.log_store.get_successful_publication(context.date_iso)
        if existing is not None:
            msg = (
                f"Publicação ignorada por controle de duplicidade: já existe um Story "
                f"publicado com sucesso em {context.date_iso} "
                f"(media_id={existing.media_id}, horário={existing.executed_at})."
            )
            logger.info(msg)
            return ExecutionOutcome(
                status="SKIPPED_DUPLICATE",
                context=context,
                selected_image=selected,
                container_id=existing.container_id,
                media_id=existing.media_id,
                message=msg,
            )

        # 2. Validação do arquivo local
        logger.info("Etapa: Validando arquivo de imagem local (%s)...", selected.local_path)
        metadata = validate_local_image(selected.local_path)
        logger.info(
            "Imagem local válida: formato=%s, dimensões=%dx%d, tamanho=%d bytes.",
            metadata.format_name,
            metadata.width,
            metadata.height,
            metadata.size_bytes,
        )

        # 3. Modo Simulação (Dry-Run) — nunca cria containers nem publica na Meta
        if self.settings.dry_run:
            if selected.public_url and not skip_remote_url_check:
                logger.info(
                    "Etapa (Simulação): Validando acessibilidade HTTP da URL pública (%s)...",
                    selected.public_url,
                )
                validate_remote_image_url(selected.public_url)
                logger.info("URL pública validada com sucesso via HTTP.")
            else:
                logger.info(
                    "Etapa (Simulação): Verificação de URL remota ignorada (URL não configurada ou flag ativa)."
                )

            msg = (
                f"Simulação concluída com sucesso para {context.weekday_name} ({selected.filename}). "
                "Nenhum container ou publicação foi enviado à Meta."
            )
            logger.info(msg)
            return ExecutionOutcome(
                status="DRY_RUN",
                context=context,
                selected_image=selected,
                message=msg,
            )

        # 4. Validação de variáveis obrigatórias e URL remota para publicação real
        self.settings.validate_for_execution(require_remote=True)

        if not skip_remote_url_check:
            logger.info("Etapa: Validando acessibilidade HTTP da URL pública (%s)...", selected.public_url)
            validate_remote_image_url(selected.public_url)
            logger.info("URL pública validada com sucesso (HTTP 200, image/jpeg).")

        # 5. Autenticação e publicação na Meta Graph API
        client = self._get_meta_client()
        try:
            logger.info("Etapa: Validando autenticação com a Meta Graph API...")
            account_info = client.verify_account_access()
            logger.info(
                "Autenticação na Meta confirmada (username=%s, id=%s).",
                account_info.get("username", "N/A"),
                account_info.get("id", self.settings.meta_ig_user_id),
            )

            result = client.publish_story_image(image_url=selected.public_url)
        except Exception as exc:
            failed_record = PublicationRecord(
                date=context.date_iso,
                weekday=context.weekday_name,
                image_name=selected.filename,
                container_id=None,
                media_id=None,
                executed_at=context.timestamp_iso,
                status="FAILED",
                error_message=str(exc),
            )
            self.log_store.record_publication(failed_record)
            logger.error("Falha durante a publicação na Meta: %s", exc)
            raise

        # 6. Registro de publicação bem-sucedida
        success_record = PublicationRecord(
            date=context.date_iso,
            weekday=context.weekday_name,
            image_name=selected.filename,
            container_id=result.container_id,
            media_id=result.media_id,
            executed_at=context.timestamp_iso,
            status="SUCCESS",
        )
        self.log_store.record_publication(success_record)

        msg = (
            f"Story publicado e registrado com sucesso em {context.date_iso} "
            f"({context.weekday_name} -> {selected.filename} | media_id={result.media_id})."
        )
        logger.info(msg)
        return ExecutionOutcome(
            status="SUCCESS",
            context=context,
            selected_image=selected,
            container_id=result.container_id,
            media_id=result.media_id,
            message=msg,
        )

