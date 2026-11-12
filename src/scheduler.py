"""Gerenciamento de data, hora e fuso horário (America/Sao_Paulo)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

WEEKDAY_NAMES_PT: dict[int, str] = {
    0: "Segunda-feira",
    1: "Terça-feira",
    2: "Quarta-feira",
    3: "Quinta-feira",
    4: "Sexta-feira",
    5: "Sábado",
    6: "Domingo",
}


@dataclass(frozen=True)
class ScheduleContext:
    """Informações temporais resolvidas no fuso horário alvo."""

    now: datetime
    date_iso: str
    timestamp_iso: str
    weekday_index: int
    weekday_name: str
    timezone_name: str


def get_current_schedule_context(
    timezone_name: str = "America/Sao_Paulo",
    reference_dt: datetime | None = None,
) -> ScheduleContext:
    """
    Obtém a data/hora atual ou converte um datetime de referência para o fuso informado.

    Nunca utiliza UTC puro para decidir o dia da semana: se `reference_dt` possuir
    fuso horário (ex.: UTC), é convertido para `timezone_name`. Se for ingênuo (naive),
    assume-se que já está no fuso `timezone_name`.
    """
    tz = ZoneInfo(timezone_name)
    if reference_dt is None:
        localized = datetime.now(tz)
    elif reference_dt.tzinfo is None:
        localized = reference_dt.replace(tzinfo=tz)
    else:
        localized = reference_dt.astimezone(tz)

    weekday_idx = localized.weekday()
    if weekday_idx not in WEEKDAY_NAMES_PT:
        raise ValueError(f"Índice de dia da semana inválido: {weekday_idx}")

    return ScheduleContext(
        now=localized,
        date_iso=localized.strftime("%Y-%m-%d"),
        timestamp_iso=localized.isoformat(timespec="seconds"),
        weekday_index=weekday_idx,
        weekday_name=WEEKDAY_NAMES_PT[weekday_idx],
        timezone_name=timezone_name,
    )

