"""Testes unitários para prevenção de duplicidade, modo simulação e integração Meta (com mocks)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from src.config import Settings, mask_secret
from src.meta_client import (
    MetaAPIError,
    MetaAuthenticationError,
    MetaGraphClient,
    MetaPublishResult,
)
from src.publication_log import PublicationLogStore
from src.publisher import StoryPublisher


def _populate_seven_images(assets_dir: Path) -> None:
    assets_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "segunda.jpg",
        "terca.jpg",
        "quarta.jpg",
        "quinta.jpg",
        "sexta.jpg",
        "sabado.jpg",
        "domingo.jpg",
    ]:
        img = Image.new("RGB", (540, 960), color=(30, 60, 90))
        img.save(assets_dir / name, format="JPEG")


class TestPublisher(unittest.TestCase):
    def test_modo_simulacao_nao_cria_container_nem_publica_na_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assets_dir = tmp_path / "assets"
            _populate_seven_images(assets_dir)
            history_file = tmp_path / "data" / "publication_history.json"

            settings = Settings(
                meta_access_token="TOKEN_SECRETO_TESTE_123456",
                meta_ig_user_id="17841400001",
                image_base_url="https://exemplo.github.io/repo/assets/stories",
                dry_run=True,
                assets_dir=assets_dir,
                history_file=history_file,
            )
            mock_meta = MagicMock(spec=MetaGraphClient)
            publisher = StoryPublisher(settings=settings, meta_client=mock_meta)

            ref_dt = datetime(2026, 11, 2, 11, 0, 0, tzinfo=timezone.utc)
            outcome = publisher.run(reference_dt=ref_dt, skip_remote_url_check=True)

            self.assertEqual(outcome.status, "DRY_RUN")
            self.assertEqual(outcome.selected_image.filename, "segunda.jpg")
            mock_meta.verify_account_access.assert_not_called()
            mock_meta.publish_story_image.assert_not_called()
            self.assertFalse(publisher.log_store.has_published_on_date("2026-11-02"))

    def test_publicacao_real_e_prevencao_de_duplicidade_na_mesma_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assets_dir = tmp_path / "assets"
            _populate_seven_images(assets_dir)
            history_file = tmp_path / "data" / "publication_history.json"

            settings = Settings(
                meta_access_token="TOKEN_SECRETO_TESTE_123456",
                meta_ig_user_id="17841400001",
                image_base_url="https://exemplo.github.io/repo/assets/stories",
                dry_run=False,
                assets_dir=assets_dir,
                history_file=history_file,
            )

            mock_meta = MagicMock(spec=MetaGraphClient)
            mock_meta.verify_account_access.return_value = {
                "id": "17841400001",
                "username": "pointperucaba",
            }
            mock_meta.publish_story_image.return_value = MetaPublishResult(
                container_id="CONT_999",
                media_id="MEDIA_888",
            )

            publisher = StoryPublisher(settings=settings, meta_client=mock_meta)
            ref_dt = datetime(2026, 11, 4, 11, 0, 0, tzinfo=timezone.utc)

            with patch("src.publisher.validate_remote_image_url") as mock_url_check:
                first_outcome = publisher.run(reference_dt=ref_dt)
                self.assertEqual(first_outcome.status, "SUCCESS")
                self.assertEqual(first_outcome.container_id, "CONT_999")
                self.assertEqual(first_outcome.media_id, "MEDIA_888")
                self.assertEqual(mock_meta.publish_story_image.call_count, 1)
                mock_url_check.assert_called_once()

                second_outcome = publisher.run(reference_dt=ref_dt)
                self.assertEqual(second_outcome.status, "SKIPPED_DUPLICATE")
                self.assertEqual(second_outcome.media_id, "MEDIA_888")
                self.assertEqual(mock_meta.publish_story_image.call_count, 1)

    def test_tratamento_de_erro_autenticacao_token_expirado_sem_vazar_token(self) -> None:
        secret_token = "EAABZ_SUPER_SECRET_TOKEN_987654321"
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {
                "message": f"Error validating access token: {secret_token} has expired.",
                "type": "OAuthException",
                "code": 190,
                "error_subcode": 463,
                "fbtrace_id": "AbCdEf123",
            }
        }
        mock_session.get.return_value = mock_response

        client = MetaGraphClient(
            access_token=secret_token,
            ig_user_id="17841400001",
            session=mock_session,
        )

        with self.assertRaises(MetaAuthenticationError) as ctx:
            client.verify_account_access()

        err_msg = str(ctx.exception)
        self.assertNotIn(secret_token, err_msg)
        self.assertIn(mask_secret(secret_token), err_msg)
        self.assertEqual(ctx.exception.error_code, 190)
        self.assertEqual(ctx.exception.error_subcode, 463)

    def test_fluxo_completo_cliente_meta_container_e_publish(self) -> None:
        mock_session = MagicMock()

        resp_create = MagicMock()
        resp_create.status_code = 200
        resp_create.json.return_value = {"id": "178900001"}

        resp_status = MagicMock()
        resp_status.status_code = 200
        resp_status.json.return_value = {"status_code": "FINISHED"}

        resp_publish = MagicMock()
        resp_publish.status_code = 200
        resp_publish.json.return_value = {"id": "179900002"}

        mock_session.post.side_effect = [resp_create, resp_publish]
        mock_session.get.return_value = resp_status

        client = MetaGraphClient(
            access_token="TOKEN_VALIDO_123456789",
            ig_user_id="17841400001",
            api_version="v22.0",
            session=mock_session,
        )

        result = client.publish_story_image(
            image_url="https://exemplo.github.io/stories/segunda.jpg",
            poll_interval_seconds=0,
        )

        self.assertEqual(result.container_id, "178900001")
        self.assertEqual(result.media_id, "179900002")

        first_post_call = mock_session.post.call_args_list[0]
        self.assertEqual(first_post_call.kwargs["data"]["media_type"], "STORIES")
        self.assertEqual(
            first_post_call.kwargs["data"]["image_url"],
            "https://exemplo.github.io/stories/segunda.jpg",
        )

    def test_falha_na_api_registra_status_failed_mas_permite_nova_tentativa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assets_dir = tmp_path / "assets"
            _populate_seven_images(assets_dir)
            history_file = tmp_path / "data" / "publication_history.json"

            settings = Settings(
                meta_access_token="TOKEN_TESTE_123456789",
                meta_ig_user_id="17841400001",
                image_base_url="https://exemplo.github.io/repo/assets/stories",
                dry_run=False,
                assets_dir=assets_dir,
                history_file=history_file,
            )
            mock_meta = MagicMock(spec=MetaGraphClient)
            mock_meta.verify_account_access.return_value = {"id": "17841400001"}
            mock_meta.publish_story_image.side_effect = MetaAPIError(
                "Serviço temporariamente indisponível", status_code=503
            )

            store = PublicationLogStore(history_file)
            publisher = StoryPublisher(
                settings=settings, log_store=store, meta_client=mock_meta
            )
            ref_dt = datetime(2026, 11, 5, 11, 0, 0, tzinfo=timezone.utc)

            with patch("src.publisher.validate_remote_image_url"):
                with self.assertRaisesRegex(MetaAPIError, "temporariamente indisponível"):
                    publisher.run(reference_dt=ref_dt)

            self.assertFalse(store.has_published_on_date("2026-11-05"))


if __name__ == "__main__":
    unittest.main()
