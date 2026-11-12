"""Seleção da imagem correspondente ao dia da semana."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from src.scheduler import ScheduleContext, get_current_schedule_context

# Nomes canônicos (ASCII, minúsculos) definidos na especificação do projeto.
# O mesmo nome é usado no repositório, no GitHub Pages e na URL enviada à Meta,
# garantindo que o caminho local e o caminho público sejam sempre idênticos.
WEEKDAY_IMAGE_MAP: dict[int, str] = {
    0: "segunda.jpg",
    1: "terca.jpg",
    2: "quarta.jpg",
    3: "quinta.jpg",
    4: "sexta.jpg",
    5: "sabado.jpg",
    6: "domingo.jpg",
}


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


def build_public_url(image_base_url: str, filename: str, version_tag: str | None = None) -> str:
    """Monta a URL pública da imagem a partir da URL base do GitHub Pages."""
    clean_base = image_base_url.strip().rstrip("/")
    if not clean_base:
        return ""
    url = f"{clean_base}/{quote(filename)}"
    if version_tag:
        url = f"{url}?v={version_tag}"
    return url


def select_image_for_context(
    context: ScheduleContext,
    assets_dir: Path,
    image_base_url: str = "",
) -> SelectedImage:
    """Seleciona a imagem com base no contexto de horário já resolvido (função pura, sem efeitos colaterais)."""
    filename = get_image_filename_for_weekday(context.weekday_index)
    # Cache-busting por data: força a Meta a baixar a versão atual caso a arte seja substituída
    version_tag = context.date_iso.replace("-", "")

    return SelectedImage(
        weekday_index=context.weekday_index,
        weekday_name=context.weekday_name,
        filename=filename,
        local_path=assets_dir / filename,
        public_url=build_public_url(image_base_url, filename, version_tag),
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
