"""Seleção da imagem correspondente ao dia da semana."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import io
import logging
import os
from pathlib import Path
import unicodedata
from urllib.parse import quote

from PIL import Image, UnidentifiedImageError

from src.scheduler import ScheduleContext, get_current_schedule_context

logger = logging.getLogger(__name__)

WEEKDAY_IMAGE_MAP: dict[int, str] = {
    0: "segunda.jpg",
    1: "terca.jpg",
    2: "quarta.jpg",
    3: "quinta.jpg",
    4: "sexta.jpg",
    5: "sabado.jpg",
    6: "domingo.jpg",
}

WEEKDAY_ALIASES: dict[int, set[str]] = {
    0: {"segunda", "segunda-feira", "segunda_feira", "segundafeira", "arte01", "arte 01", "arte-01", "arte_01", "01", "1"},
    1: {"terca", "terca-feira", "terca_feira", "tercafeira", "arte02", "arte 02", "arte-02", "arte_02", "02", "2"},
    2: {"quarta", "quarta-feira", "quarta_feira", "quartafeira", "arte03", "arte 03", "arte-03", "arte_03", "03", "3"},
    3: {"quinta", "quinta-feira", "quinta_feira", "quintafeira", "arte04", "arte 04", "arte-04", "arte_04", "04", "4"},
    4: {"sexta", "sexta-feira", "sexta_feira", "sextafeira", "arte05", "arte 05", "arte-05", "arte_05", "05", "5"},
    5: {"sabado", "sabado-feira", "arte06", "arte 06", "arte-06", "arte_06", "06", "6"},
    6: {"domingo", "arte07", "arte 07", "arte-07", "arte_07", "07", "7"},
}

SUPPORTED_SOURCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def find_matching_source_for_weekday(assets_dir: Path, weekday_index: int) -> Path | None:
    """Localiza o arquivo de imagem correspondente ao dia da semana em `assets/stories` ou `assets/`."""
    target_filename = get_image_filename_for_weekday(weekday_index)
    canonical_path = assets_dir / target_filename
    if canonical_path.exists() and canonical_path.is_file() and canonical_path.stat().st_size > 0:
        return canonical_path

    search_root = (
        assets_dir.parent
        if assets_dir.name.lower() == "stories" and assets_dir.parent.exists()
        else assets_dir
    )
    if not search_root.exists():
        return None

    aliases = WEEKDAY_ALIASES[weekday_index]
    try:
        for candidate in sorted(search_root.rglob("*")):
            if not candidate.is_file() or candidate.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
                continue
            stem_clean = _strip_accents(candidate.stem.strip().lower())
            if stem_clean in aliases or any(
                alias in stem_clean for alias in aliases if len(alias) >= 5
            ):
                return candidate
    except OSError:
        return None

    return None


def normalize_assets_directory(assets_dir: Path) -> list[Path]:
    """
    Procura imagens em `assets/stories/` e `assets/` e tenta padronizá-las como
    `assets/stories/<dia>.jpg`. Caso o sistema de arquivos (ex.: OneDrive) impeça
    a cópia, mantém a referência para o arquivo original encontrado.
    """
    resolved_paths: list[Path] = []
    for weekday_idx, target_filename in WEEKDAY_IMAGE_MAP.items():
        target_path = assets_dir / target_filename
        if target_path.exists() and target_path.stat().st_size > 0:
            resolved_paths.append(target_path)
            continue

        matched_source = find_matching_source_for_weekday(assets_dir, weekday_idx)
        if matched_source is None:
            continue

        try:
            raw_bytes = matched_source.read_bytes()
            with Image.open(io.BytesIO(raw_bytes)) as img:
                fmt = (img.format or "").upper()
                rgb_img = img.convert("RGB") if fmt not in {"JPEG", "MPO"} else None

            if rgb_img is not None:
                out_buf = io.BytesIO()
                rgb_img.save(out_buf, format="JPEG", quality=95)
                target_path.write_bytes(out_buf.getvalue())
            else:
                target_path.write_bytes(raw_bytes)

            logger.info(
                "Arte padronizada: '%s' -> '%s'",
                matched_source.name,
                target_path.name,
            )
            resolved_paths.append(target_path)
        except (UnidentifiedImageError, OSError):
            # Se o OneDrive bloquear a criação da cópia, utiliza o arquivo original diretamente
            resolved_paths.append(matched_source)

    return resolved_paths


@dataclass(frozen=True)
class SelectedImage:
    """Representa a arte selecionada para publicação no dia."""

    weekday_index: int
    weekday_name: str
    filename: str
    local_path: Path
    public_url: str


def get_image_filename_for_weekday(weekday_index: int) -> str:
    """Retorna o nome do arquivo JPEG correspondente ao índice do dia da semana (0=Segunda .. 6=Domingo)."""
    if weekday_index not in WEEKDAY_IMAGE_MAP:
        raise ValueError(
            f"Dia da semana inválido: {weekday_index}. Esperado valor entre 0 (Segunda) e 6 (Domingo)."
        )
    return WEEKDAY_IMAGE_MAP[weekday_index]


def select_image_for_context(
    context: ScheduleContext,
    assets_dir: Path,
    image_base_url: str = "",
) -> SelectedImage:
    """Seleciona a imagem com base no contexto de horário já resolvido."""
    canonical_filename = get_image_filename_for_weekday(context.weekday_index)
    canonical_path = assets_dir / canonical_filename

    matched_path = find_matching_source_for_weekday(assets_dir, context.weekday_index)
    local_path = matched_path if matched_path is not None else canonical_path
    filename = local_path.name

    clean_base = image_base_url.strip().rstrip("/")
    if clean_base:
        # Cache-busting por data e URL-encoding seguro caso o nome tenha espaços/acentos
        version_tag = context.date_iso.replace("-", "")
        encoded_filename = quote(filename)
        public_url = f"{clean_base}/{encoded_filename}?v={version_tag}"
    else:
        public_url = ""

    return SelectedImage(
        weekday_index=context.weekday_index,
        weekday_name=context.weekday_name,
        filename=filename,
        local_path=local_path,
        public_url=public_url,
    )


def select_daily_image(
    assets_dir: Path,
    image_base_url: str = "",
    timezone_name: str = "America/Sao_Paulo",
    reference_dt: datetime | None = None,
) -> tuple[ScheduleContext, SelectedImage]:
    """Identifica o dia da semana no fuso configurado e retorna o contexto e a imagem selecionada."""
    context = get_current_schedule_context(
        timezone_name=timezone_name,
        reference_dt=reference_dt,
    )
    selected = select_image_for_context(
        context=context,
        assets_dir=assets_dir,
        image_base_url=image_base_url,
    )
    return context, selected

