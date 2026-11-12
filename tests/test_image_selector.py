"""Testes unitários para seleção da arte correspondente a cada dia da semana."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.image_selector import (
    get_image_filename_for_weekday,
    select_daily_image,
)


class TestImageSelector(unittest.TestCase):
    def test_selecao_da_imagem_correspondente_aos_sete_dias(self) -> None:
        expected = [
            (0, "segunda.jpg"),
            (1, "terca.jpg"),
            (2, "quarta.jpg"),
            (3, "quinta.jpg"),
            (4, "sexta.jpg"),
            (5, "sabado.jpg"),
            (6, "domingo.jpg"),
        ]
        for weekday_idx, expected_filename in expected:
            with self.subTest(weekday_idx=weekday_idx):
                self.assertEqual(
                    get_image_filename_for_weekday(weekday_idx), expected_filename
                )

    def test_selecao_dia_invalido_levanta_erro(self) -> None:
        with self.assertRaisesRegex(ValueError, "Dia da semana inválido"):
            get_image_filename_for_weekday(7)

    def test_select_daily_image_monta_caminho_e_url_publica(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            ref_utc = datetime(2026, 11, 6, 11, 0, 0, tzinfo=timezone.utc)
            ctx, selected = select_daily_image(
                assets_dir=tmp_path,
                image_base_url="https://exemplo.github.io/point-perucaba-stories/assets/stories/",
                timezone_name="America/Sao_Paulo",
                reference_dt=ref_utc,
            )

            self.assertEqual(ctx.weekday_name, "Sexta-feira")
            self.assertEqual(selected.filename, "sexta.jpg")
            self.assertEqual(selected.local_path, tmp_path / "sexta.jpg")
            self.assertEqual(
                selected.public_url,
                "https://exemplo.github.io/point-perucaba-stories/assets/stories/sexta.jpg?v=20261106",
            )


if __name__ == "__main__":
    unittest.main()
