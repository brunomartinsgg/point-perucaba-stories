"""Controle persistente de duplicidade e histórico de publicações."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PublicationRecord:
    """Registro de uma execução de publicação de Story."""

    date: str
    weekday: str
    image_name: str
    container_id: str | None
    media_id: str | None
    executed_at: str
    status: str  # "SUCCESS", "DRY_RUN", "FAILED"
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PublicationRecord:
        return cls(
            date=str(data["date"]),
            weekday=str(data["weekday"]),
            image_name=str(data["image_name"]),
            container_id=data.get("container_id"),
            media_id=data.get("media_id"),
            executed_at=str(data["executed_at"]),
            status=str(data["status"]),
            error_message=data.get("error_message"),
        )


class PublicationLogStore:
    """Gerencia a persistência em JSON das publicações realizadas por data."""

    def __init__(self, history_file: Path) -> None:
        self.history_file = history_file

    def _load_raw(self) -> dict[str, Any]:
        if not self.history_file.exists():
            return {"publications": {}}
        try:
            content = self.history_file.read_text(encoding="utf-8").strip()
            if not content:
                return {"publications": {}}
            data = json.loads(content)
            if not isinstance(data, dict) or "publications" not in data:
                return {"publications": {}}
            return data
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(
                f"Erro ao ler arquivo de histórico de publicações ({self.history_file}): {exc}"
            ) from exc

    def _save_atomic(self, data: dict[str, Any]) -> None:
        """Salva o arquivo JSON de forma atômica para evitar corrupção em caso de falha."""
        if not self.history_file.parent.is_dir():
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.history_file.parent),
            prefix=".pub_history_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(data, tmp_file, ensure_ascii=False, indent=2, sort_keys=True)
                tmp_file.write("\n")
            os.replace(tmp_path, self.history_file)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def get_successful_publication(self, date_iso: str) -> PublicationRecord | None:
        """Retorna o registro caso já exista uma publicação real bem-sucedida (`SUCCESS`) na data."""
        data = self._load_raw()
        entry = data.get("publications", {}).get(date_iso)
        if not entry:
            return None
        record = PublicationRecord.from_dict(entry)
        if record.status == "SUCCESS":
            return record
        return None

    def has_published_on_date(self, date_iso: str) -> bool:
        """Verifica se já houve publicação concluída com sucesso na data informada."""
        return self.get_successful_publication(date_iso) is not None

    def record_publication(self, record: PublicationRecord) -> None:
        """
        Registra o resultado de uma execução.
        Se já houver um registro `SUCCESS` para a mesma data, ele nunca é sobrescrito
        por uma falha ou simulação posterior.
        """
        data = self._load_raw()
        publications = data.setdefault("publications", {})
        existing_raw = publications.get(record.date)
        if existing_raw:
            existing = PublicationRecord.from_dict(existing_raw)
            if existing.status == "SUCCESS" and record.status != "SUCCESS":
                return

        publications[record.date] = record.to_dict()
        self._save_atomic(data)

