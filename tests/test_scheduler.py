"""Testes unitários para agendamento e conversão de fuso horário (America/Sao_Paulo)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.scheduler import get_current_schedule_context


class TestScheduler(unittest.TestCase):
    def test_identificacao_correta_dos_sete_dias_da_semana(self) -> None:
        """Valida a identificação dos 7 dias da semana (2 a 8 de novembro de 2026)."""
        expected_days = [
            (2, 0, "Segunda-feira"),
            (3, 1, "Terça-feira"),
            (4, 2, "Quarta-feira"),
            (5, 3, "Quinta-feira"),
            (6, 4, "Sexta-feira"),
            (7, 5, "Sábado"),
            (8, 6, "Domingo"),
        ]
        for day_of_month, expected_idx, expected_name in expected_days:
            with self.subTest(day=expected_name):
                ref = datetime(2026, 11, day_of_month, 8, 0, 0)
                ctx = get_current_schedule_context("America/Sao_Paulo", reference_dt=ref)
                self.assertEqual(ctx.weekday_index, expected_idx)
                self.assertEqual(ctx.weekday_name, expected_name)
                self.assertEqual(ctx.date_iso, f"2026-11-0{day_of_month}")

    def test_conversao_correta_fuso_utc_para_sao_paulo_mesmo_dia(self) -> None:
        """11:00 UTC deve converter para 08:00 America/Sao_Paulo (UTC-3) na mesma data."""
        utc_dt = datetime(2026, 11, 11, 11, 0, 0, tzinfo=timezone.utc)
        ctx = get_current_schedule_context("America/Sao_Paulo", reference_dt=utc_dt)

        self.assertEqual(ctx.date_iso, "2026-11-11")
        self.assertEqual(ctx.now.hour, 8)
        self.assertEqual(ctx.weekday_index, 2)
        self.assertEqual(ctx.weekday_name, "Quarta-feira")

    def test_conversao_fuso_virada_de_dia_nao_usa_utc(self) -> None:
        """
        01:30 UTC de terça-feira (2026-11-03) ainda é 22:30 de segunda-feira (2026-11-02)
        em America/Sao_Paulo. Garante que o sistema nunca usa UTC para decidir o dia.
        """
        utc_dt = datetime(2026, 11, 3, 1, 30, 0, tzinfo=timezone.utc)
        ctx = get_current_schedule_context("America/Sao_Paulo", reference_dt=utc_dt)

        self.assertEqual(ctx.date_iso, "2026-11-02")
        self.assertEqual(ctx.weekday_index, 0)
        self.assertEqual(ctx.weekday_name, "Segunda-feira")


if __name__ == "__main__":
    unittest.main()
