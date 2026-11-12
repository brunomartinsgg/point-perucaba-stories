"""Validação física (local) e remota (HTTP) das imagens para Instagram Stories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests
from PIL import Image, UnidentifiedImageError

# Limite oficial da Meta Content Publishing API para imagens JPEG: 8 MB
MAX_IMAGE_SIZE_BYTES = 8 * 1024 * 1024
ALLOWED_PIL_FORMATS = {"JPEG", "MPO"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg"}


class ImageValidationError(Exception):
    """Exceção lançada quando a imagem local ou sua URL pública não atende aos requisitos da Meta."""


@dataclass(frozen=True)
class ImageMetadata:
    """Metadados extraídos após validação da imagem."""

    path: Path
    size_bytes: int
    width: int
    height: int
    format_name: str


def validate_local_image(
    image_path: Path, max_size_bytes: int = MAX_IMAGE_SIZE_BYTES
) -> ImageMetadata:
    """
    Valida se o arquivo local existe, não está vazio, respeita o limite de 8 MB
    e é efetivamente um arquivo JPEG válido (verificando assinatura binária via Pillow).
    """
    if not image_path.exists():
        found_files: list[str] = []
        search_root = (
            image_path.parent.parent
            if image_path.parent.name.lower() == "stories" and image_path.parent.parent.exists()
            else image_path.parent
        )
        if search_root.exists():
            try:
                found_files = [
                    str(p.relative_to(search_root))
                    for p in sorted(search_root.rglob("*"))
                    if p.is_file() and p.name != ".gitkeep"
                ]
            except OSError:
                pass
        extra_info = (
            f" (Arquivos encontrados em '{search_root}': {found_files})"
            if found_files
            else f" (Nenhum arquivo encontrado dentro de '{search_root}')"
        )
        raise ImageValidationError(
            f"Arquivo de imagem não encontrado: {image_path}{extra_info}"
        )

    if not image_path.is_file():
        raise ImageValidationError(f"O caminho especificado não é um arquivo: {image_path}")

    size_bytes = image_path.stat().st_size
    if size_bytes <= 0:
        raise ImageValidationError(f"O arquivo de imagem está vazio (0 bytes): {image_path}")

    if size_bytes > max_size_bytes:
        raise ImageValidationError(
            f"O arquivo excede o tamanho máximo permitido pela Meta ({max_size_bytes} bytes): "
            f"{size_bytes} bytes em {image_path.name}"
        )

    try:
        with Image.open(image_path) as img:
            img.verify()
        with Image.open(image_path) as img:
            fmt = (img.format or "").upper()
            width, height = img.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageValidationError(
            f"Arquivo de imagem corrompido ou formato inválido ({image_path.name}): {exc}"
        ) from exc

    if fmt not in ALLOWED_PIL_FORMATS:
        raise ImageValidationError(
            f"Formato de imagem não suportado pela Meta Graph API: '{fmt}'. "
            "A API de publicação de Stories aceita exclusivamente imagens JPEG (.jpg)."
        )

    if width <= 0 or height <= 0:
        raise ImageValidationError(
            f"Dimensões de imagem inválidas: {width}x{height} em {image_path.name}"
        )

    return ImageMetadata(
        path=image_path,
        size_bytes=size_bytes,
        width=width,
        height=height,
        format_name="JPEG",
    )


def validate_all_weekly_images(
    assets_dir: Path,
    filenames: list[str] | None = None,
    max_size_bytes: int = MAX_IMAGE_SIZE_BYTES,
) -> list[ImageMetadata]:
    """Valida todas as 7 imagens semanais do diretório `assets/stories/`."""
    from src.image_selector import WEEKDAY_IMAGE_MAP

    expected_files = filenames or list(WEEKDAY_IMAGE_MAP.values())
    results: list[ImageMetadata] = []
    for name in expected_files:
        results.append(
            validate_local_image(assets_dir / name, max_size_bytes=max_size_bytes)
        )
    return results


def validate_remote_image_url(
    public_url: str,
    timeout_seconds: int = 15,
    max_size_bytes: int = MAX_IMAGE_SIZE_BYTES,
    session: requests.Session | None = None,
) -> None:
    """
    Realiza verificação HTTP na URL pública da imagem para garantir que os servidores
    da Meta conseguirão baixá-la com sucesso.
    """
    if not public_url or not public_url.startswith("https://"):
        raise ImageValidationError(
            f"A URL pública da imagem deve ser HTTPS válida. Recebido: '{public_url}'"
        )

    http = session or requests
    try:
        response = http.get(public_url, stream=True, timeout=timeout_seconds)
    except requests.RequestException as exc:
        raise ImageValidationError(
            f"Falha de conexão ao validar a URL pública da imagem ({public_url}): {exc}"
        ) from exc

    try:
        if response.status_code != 200:
            raise ImageValidationError(
                f"A URL pública da imagem retornou HTTP {response.status_code} "
                f"(esperado 200 OK): {public_url}"
            )

        content_type_header = response.headers.get("Content-Type", "")
        mime_type = content_type_header.split(";")[0].strip().lower()
        if mime_type not in ALLOWED_CONTENT_TYPES:
            raise ImageValidationError(
                f"Content-Type incompatível na URL pública: '{content_type_header}'. "
                "Esperado 'image/jpeg'."
            )

        content_length_header = response.headers.get("Content-Length")
        if content_length_header and content_length_header.isdigit():
            remote_size = int(content_length_header)
            if remote_size <= 0:
                raise ImageValidationError(
                    f"A URL pública indicou Content-Length vazio (0 bytes): {public_url}"
                )
            if remote_size > max_size_bytes:
                raise ImageValidationError(
                    f"A imagem remota excede o limite de {max_size_bytes} bytes: {remote_size} bytes."
                )

        # Lê o primeiro bloco para confirmar que o corpo não está vazio e possui magic bytes JPEG (FF D8 FF)
        first_chunk = next(response.iter_content(chunk_size=1024), b"")
        if not first_chunk:
            raise ImageValidationError(
                f"O corpo da resposta HTTP da imagem está vazio: {public_url}"
            )
        if not first_chunk.startswith(b"\xff\xd8\xff"):
            raise ImageValidationError(
                f"O conteúdo retornado pela URL pública não possui cabeçalho binário JPEG válido: {public_url}"
            )
    finally:
        response.close()

