"""Ponto de entrada CLI da automação Point Perucaba Stories."""

from __future__ import annotations

import argparse
import logging
import sys

from src.config import SensitiveDataFilter, Settings
from src.image_selector import WEEKDAY_IMAGE_MAP, build_public_url
from src.image_validator import (
    ImageValidationError,
    validate_all_weekly_images,
    validate_remote_image_url,
)
from src.meta_client import MetaAPIError, MetaAuthenticationError, MetaGraphClient
from src.publisher import StoryPublisher


def configure_logging(settings: Settings) -> None:
    """Configura logs estruturados com filtro de proteção contra vazamento de segredos."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter([settings.meta_access_token]))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automação diária de publicação de Instagram Stories — Point Perucaba."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa em modo de simulação sem criar container nem publicar na Meta.",
    )
    parser.add_argument(
        "--skip-remote-url-check",
        action="store_true",
        help="Ignora a validação HTTP da URL remota durante testes locais offline.",
    )
    parser.add_argument(
        "--init-placeholders",
        action="store_true",
        help="Gera as 7 imagens JPEG iniciais de teste em assets/stories/ caso ainda não existam.",
    )
    parser.add_argument(
        "--verify-setup",
        action="store_true",
        help="Valida as 7 imagens locais, as 7 URLs remotas e a autenticação na Meta sem publicar nada.",
    )
    return parser.parse_args(argv)


def run_verify_setup(
    settings: Settings,
    skip_remote_url_check: bool,
    logger: logging.Logger,
) -> int:
    """Executa diagnóstico completo de pré-produção sem criar containers nem publicar Stories."""
    logger.info("=== INICIANDO DIAGNÓSTICO DE CONFIGURAÇÃO (--verify-setup) ===")

    # 1. Valida todas as 7 imagens locais
    metas = validate_all_weekly_images(settings.assets_dir)
    for meta in metas:
        logger.info(
            "[OK] Imagem local validada: %s (%dx%d, %d bytes, %s)",
            meta.path.name,
            meta.width,
            meta.height,
            meta.size_bytes,
            meta.format_name,
        )

    # 2. Valida as 7 URLs públicas remotas (se habilitado e se IMAGE_BASE_URL estiver definida)
    if skip_remote_url_check:
        logger.info("[PULADO] Validação de URLs públicas (--skip-remote-url-check ativo).")
    elif not settings.image_base_url:
        logger.info(
            "[PENDENTE] Variável IMAGE_BASE_URL ainda não configurada para validação das URLs públicas."
        )
    else:
        for meta in metas:
            url = build_public_url(settings.image_base_url, meta.path.name)
            validate_remote_image_url(url)
            logger.info("[OK] URL pública acessível e compatível: %s", url)

    # 3. Testa autenticação na Meta Graph API (se credenciais estiverem definidas)
    if settings.meta_access_token and settings.meta_ig_user_id:
        client = MetaGraphClient(
            access_token=settings.meta_access_token,
            ig_user_id=settings.meta_ig_user_id,
            api_version=settings.meta_api_version,
        )
        account = client.verify_account_access()
        logger.info(
            "[OK] Autenticação Meta confirmada | Conta Instagram: @%s (ID: %s)",
            account.get("username", "N/A"),
            account.get("id", settings.meta_ig_user_id),
        )
    else:
        logger.info(
            "[PENDENTE] Credenciais META_ACCESS_TOKEN / META_IG_USER_ID ainda não definidas no ambiente."
        )

    logger.info("=== DIAGNÓSTICO CONCLUÍDO COM SUCESSO (Nenhuma publicação realizada) ===")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    override_dry_run = True if args.dry_run else None
    settings = Settings.from_env(override_dry_run=override_dry_run)
    configure_logging(settings)

    logger = logging.getLogger("point_perucaba.main")
    try:
        if args.init_placeholders:
            from scripts.generate_placeholder_images import generate_placeholders

            created = generate_placeholders(settings.assets_dir)
            logger.info(
                "%d imagens JPEG iniciais geradas com sucesso em %s.",
                len(created),
                settings.assets_dir,
            )

        if args.verify_setup:
            return run_verify_setup(
                settings=settings,
                skip_remote_url_check=args.skip_remote_url_check,
                logger=logger,
            )

        publisher = StoryPublisher(settings=settings)
        outcome = publisher.run(skip_remote_url_check=args.skip_remote_url_check)
        logger.info("Execução finalizada com status=%s | %s", outcome.status, outcome.message)
        return 0
    except ImageValidationError as exc:
        logger.error("ERRO DE VALIDAÇÃO DE IMAGEM: %s", exc)
        return 2
    except MetaAuthenticationError as exc:
        logger.error("ERRO DE AUTENTICAÇÃO NA META: %s", exc)
        return 3
    except MetaAPIError as exc:
        logger.error("ERRO NA API DA META: %s", exc)
        return 4
    except Exception as exc:
        logger.error("ERRO INESPERADO NA EXECUÇÃO: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

