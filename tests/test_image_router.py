"""Tests unitaires pour le pipeline image (ImageRouter).

Modules testés :
- test_route_thumbnail : routage vers ThumbnailGenerator
- test_route_background : routage vers BackgroundGenerator
- test_route_text_visual : routage vers TextVisualGenerator
- test_route_unknown_type_fallback : fallback sur type inconnu
"""

from unittest.mock import MagicMock, patch

import pytest

from image.router import (
    ImageRouter,
    VISUAL_TYPE_THUMBNAIL,
    VISUAL_TYPE_BACKGROUND,
    VISUAL_TYPE_TEXT,
    VISUAL_TYPE_ILLUSTRATION,
)


class TestImageRouter:
    """Tests du routeur de pipeline image."""

    @patch("image.router.ThumbnailGenerator")
    @patch("image.router.TextVisualGenerator")
    @patch("image.router.PostProcessor")
    def test_route_thumbnail(
        self, mock_post, mock_text, mock_thumb, mock_settings
    ):
        """Vérifie le routage vers ThumbnailGenerator."""
        mock_thumb_instance = MagicMock()
        mock_thumb.return_value = mock_thumb_instance
        mock_thumb_instance.generate.return_value = (
            MagicMock(),
            1.5,
        )

        mock_post_instance = MagicMock()
        mock_post.return_value = mock_post_instance
        mock_post_instance.process.return_value = (
            "/tmp/test_thumbnail.png"
        )

        router = ImageRouter(settings=mock_settings)
        router.thumbnail = mock_thumb_instance
        router.postprocessor = mock_post_instance
        router._initialized = True

        task = {
            "task_id": "task_001",
            "niche": "cuisine",
            "visual_type": VISUAL_TYPE_THUMBNAIL,
            "prompt": "Une pizza qui fait saliver",
        }
        script_data = {
            "hook": "La meilleure pizza",
            "body_points": ["Point 1"],
            "visual_notes": "Fromage fondant",
        }

        result = router.generate_image(
            task=task, script_data=script_data
        )

        assert result == "/tmp/test_thumbnail.png"
        mock_thumb_instance.generate.assert_called_once()

    @patch("image.router.BackgroundGenerator")
    @patch("image.router.TextVisualGenerator")
    @patch("image.router.PostProcessor")
    def test_route_background(
        self, mock_post, mock_text, mock_bg, mock_settings
    ):
        """Vérifie le routage vers BackgroundGenerator."""
        mock_bg_instance = MagicMock()
        mock_bg.return_value = mock_bg_instance
        mock_bg_instance.generate.return_value = (
            MagicMock(),
            2.0,
        )

        mock_post_instance = MagicMock()
        mock_post.return_value = mock_post_instance
        mock_post_instance.process.return_value = (
            "/tmp/test_bg.png"
        )

        router = ImageRouter(settings=mock_settings)
        router.background = mock_bg_instance
        router.postprocessor = mock_post_instance
        router._initialized = True

        task = {
            "task_id": "task_002",
            "niche": "sante",
            "visual_type": VISUAL_TYPE_BACKGROUND,
        }
        script_data = {
            "hook": "Meditation guidée",
            "body_points": [],
            "visual_notes": "Fond calme nature",
        }

        result = router.generate_image(
            task=task, script_data=script_data
        )

        assert result == "/tmp/test_bg.png"
        mock_bg_instance.generate.assert_called_once()

    @patch("image.router.ThumbnailGenerator")
    @patch("image.router.TextVisualGenerator")
    @patch("image.router.PostProcessor")
    def test_route_text_visual(
        self, mock_post, mock_text, mock_thumb, mock_settings
    ):
        """Vérifie le routage vers TextVisualGenerator."""
        mock_text_instance = MagicMock()
        mock_text.return_value = mock_text_instance
        mock_text_instance.generate.return_value = MagicMock()

        mock_post_instance = MagicMock()
        mock_post.return_value = mock_post_instance
        mock_post_instance.process.return_value = (
            "/tmp/test_text.png"
        )

        router = ImageRouter(settings=mock_settings)
        router.text_visual = mock_text_instance
        router.postprocessor = mock_post_instance
        router._initialized = True

        task = {
            "task_id": "task_003",
            "niche": "tech",
            "visual_type": VISUAL_TYPE_TEXT,
        }
        script_data = {
            "hook": "3 astuces Python",
            "body_points": ["Astuce 1", "Astuce 2", "Astuce 3"],
            "visual_notes": "Code a l'ecran",
        }

        result = router.generate_image(
            task=task, script_data=script_data
        )

        assert result == "/tmp/test_text.png"
        mock_text_instance.generate.assert_called_once()

    @patch("image.router.ThumbnailGenerator")
    @patch("image.router.TextVisualGenerator")
    @patch("image.router.PostProcessor")
    def test_route_unknown_type_fallback(
        self, mock_post, mock_text, mock_thumb, mock_settings
    ):
        """Vérifie le fallback sur le type par défaut de la niche.

        Quand le type de visuel n'est pas spécifié, le routeur
        détermine automatiquement le type via DEFAULT_VISUAL_MAP.
        """
        mock_text_instance = MagicMock()
        mock_text.return_value = mock_text_instance
        mock_text_instance.generate.return_value = MagicMock()

        mock_post_instance = MagicMock()
        mock_post.return_value = mock_post_instance
        mock_post_instance.process.return_value = (
            "/tmp/test_fallback.png"
        )

        router = ImageRouter(settings=mock_settings)
        router.text_visual = mock_text_instance
        router.postprocessor = mock_post_instance
        router._initialized = True

        # Niche "motivation" -> DEFAULT_VISUAL_MAP donne VISUAL_TYPE_TEXT
        task = {
            "task_id": "task_004",
            "niche": "motivation",
            "visual_type": "",  # Non specifié
        }
        script_data = {
            "hook": "Ne jamais abandonner",
            "body_points": ["Point 1"],
            "visual_notes": "Texte inspirant",
        }

        # Niche "motivation" -> text_visual
        result = router.generate_image(
            task=task, script_data=script_data
        )

        assert result == "/tmp/test_fallback.png"
        mock_text_instance.generate.assert_called_once()

    @patch("image.router.ThumbnailGenerator")
    @patch("image.router.TextVisualGenerator")
    @patch("image.router.PostProcessor")
    def test_route_without_initialization(
        self, mock_post, mock_text, mock_thumb, mock_settings
    ):
        """Vérifie que le routeur s'initialise automatiquement."""
        mock_thumb_instance = MagicMock()
        mock_thumb.return_value = mock_thumb_instance
        mock_thumb_instance.generate.return_value = (
            MagicMock(),
            1.0,
        )

        mock_text_instance = MagicMock()
        mock_text.return_value = mock_text_instance
        mock_text_instance.generate.return_value = MagicMock()

        mock_post_instance = MagicMock()
        mock_post.return_value = mock_post_instance
        mock_post_instance.process.return_value = (
            "/tmp/test_autoinit.png"
        )

        router = ImageRouter(settings=mock_settings)

        # Ne pas initialiser manuellement
        # generate_image doit appeler initialize()

        router.thumbnail = mock_thumb_instance
        router.text_visual = mock_text_instance
        router.postprocessor = mock_post_instance

        task = {
            "task_id": "task_005",
            "niche": "tech",
            "visual_type": VISUAL_TYPE_TEXT,
        }
        script_data = {
            "hook": "Auto init test",
            "body_points": ["Point"],
            "visual_notes": "",
        }

        result = router.generate_image(
            task=task, script_data=script_data
        )

        assert result is not None

    @patch("image.router.ThumbnailGenerator")
    @patch("image.router.TextVisualGenerator")
    @patch("image.router.PostProcessor")
    def test_route_illustration(
        self, mock_post, mock_text, mock_thumb, mock_settings
    ):
        """Vérifie le routage vers IllustrationGenerator."""
        with patch("image.router.IllustrationGenerator") as mock_ill:
            mock_ill_instance = MagicMock()
            mock_ill.return_value = mock_ill_instance
            mock_ill_instance.generate.return_value = (
                MagicMock(),
                3.0,
            )

            mock_post_instance = MagicMock()
            mock_post.return_value = mock_post_instance
            mock_post_instance.process.return_value = (
                "/tmp/test_illustration.png"
            )

            router = ImageRouter(settings=mock_settings)
            router.illustration = mock_ill_instance
            router.postprocessor = mock_post_instance
            router._initialized = True

            task = {
                "task_id": "task_006",
                "niche": "mode",
                "visual_type": VISUAL_TYPE_ILLUSTRATION,
            }
            script_data = {
                "hook": "Look du jour",
                "body_points": [],
                "visual_notes": "Illustration mode",
            }

            result = router.generate_image(
                task=task, script_data=script_data
            )

            assert result == "/tmp/test_illustration.png"
            mock_ill_instance.generate.assert_called_once()

    def test_get_available_types(self, mock_settings):
        """Vérifie la liste des types disponibles."""
        router = ImageRouter(settings=mock_settings)
        types = router.get_available_types()

        assert VISUAL_TYPE_THUMBNAIL in types
        assert VISUAL_TYPE_BACKGROUND in types
        assert VISUAL_TYPE_TEXT in types
        assert VISUAL_TYPE_ILLUSTRATION in types
        assert len(types) == 4
