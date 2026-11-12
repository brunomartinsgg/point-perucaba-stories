"""Testes unitários para validação local e remota de imagens."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from src.image_validator import (
    ImageValidationError,
    validate_local_image,
    validate_remote_image_url,
)


def _create_jpeg(path: Path, width: int = 1080, height: int = 1920) -> Path:
    img = Image.new("RGB", (width, height), color=(20, 40, 80))
    img.save(path, format="JPEG", quality=85)
    return path


class TestImageValidator(unittest.TestCase):
    def test_comportamento_diante_de_imagem_inexistente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / "segunda.jpg"
            with self.assertRaisesRegex(
                ImageValidationError, "Arquivo de imagem não encontrado"
            ):
                validate_local_image(missing)

    def test_rejeita_arquivo_vazio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            empty_file = Path(tmp_dir) / "vazio.jpg"
            empty_file.write_bytes(b"")
            with self.assertRaisesRegex(ImageValidationError, "está vazio"):
                validate_local_image(empty_file)

    def test_rejeita_formato_png_renomeado_para_jpg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_jpg = Path(tmp_dir) / "falso.jpg"
            img = Image.new("RGB", (200, 200), color=(255, 0, 0))
            img.save(fake_jpg, format="PNG")

            with self.assertRaisesRegex(
                ImageValidationError, "Formato de imagem não suportado"
            ):
                validate_local_image(fake_jpg)

    def test_rejeita_arquivo_acima_do_tamanho_maximo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            valid_jpg = _create_jpeg(Path(tmp_dir) / "grande.jpg", width=400, height=400)
            with self.assertRaisesRegex(
                ImageValidationError, "excede o tamanho máximo"
            ):
                validate_local_image(valid_jpg, max_size_bytes=100)

    def test_aceita_imagem_jpeg_valida(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            valid_jpg = _create_jpeg(
                Path(tmp_dir) / "segunda.jpg", width=1080, height=1920
            )
            meta = validate_local_image(valid_jpg)

            self.assertEqual(meta.format_name, "JPEG")
            self.assertEqual(meta.width, 1080)
            self.assertEqual(meta.height, 1920)
            self.assertGreater(meta.size_bytes, 0)

    def test_validacao_url_remota_sucesso(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Content-Type": "image/jpeg",
            "Content-Length": "4096",
        }
        mock_response.iter_content.return_value = iter([b"\xff\xd8\xff\xe0\x00\x10JFIF"])
        mock_session.get.return_value = mock_response

        validate_remote_image_url(
            "https://exemplo.github.io/stories/segunda.jpg",
            session=mock_session,
        )
        mock_response.close.assert_called_once()

    def test_validacao_url_remota_rejeita_404_ou_content_type_invalido(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response

        with self.assertRaisesRegex(ImageValidationError, "HTTP 404"):
            validate_remote_image_url(
                "https://exemplo.github.io/stories/segunda.jpg",
                session=mock_session,
            )

        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        with self.assertRaisesRegex(ImageValidationError, "Content-Type incompatível"):
            validate_remote_image_url(
                "https://exemplo.github.io/stories/segunda.jpg",
                session=mock_session,
            )


if __name__ == "__main__":
    unittest.main()
