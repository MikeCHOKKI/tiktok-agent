"""Tests unitaires pour ScriptGenerator.

Modules testés :
- test_generate_script_structure : intégrité du JSON retourné
- test_generate_script_retry_on_failure : mécanisme de retry
- test_generate_script_empty_subject : gestion sujet vide
- test_prompt_format : formatage du prompt système
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from huggingface_hub.utils import HfHubHTTPError

from agent.script_generator import ScriptGenerator, SYSTEM_PROMPT


# Mock reponse HTTP pour HfHubHTTPError
class _MockResponse:
    def __init__(self, status_code=500):
        self.status_code = status_code
        self.headers = {"x-request-id": "test-request-001"}
        self.request = MagicMock()


class TestScriptGenerator:
    """Tests du générateur de scripts TikTok."""

    def test_generate_script_structure(
        self, mock_hf_client, sample_script_data
    ):
        """Vérifie que le JSON retourné contient tous les champs attendus.

        Validation des clés obligatoires : hook, transition, body_points,
        cta, hashtags, description, music_suggestion, visual_notes.
        """
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            sample_script_data
        )
        mock_hf_client.chat.completions.create.return_value = mock_response

        generator = ScriptGenerator(hf_token="fake_token")
        result = generator.generate_script(
            subject="Test IA",
            niche="Tech & IA",
            style="liste_educative",
        )

        expected_keys = [
            "hook",
            "transition",
            "body_points",
            "cta",
            "hashtags",
            "description",
            "music_suggestion",
            "visual_notes",
            "subject",
            "niche",
            "style",
        ]
        for key in expected_keys:
            assert key in result, f"Clé manquante dans le résultat : {key}"

        assert result["subject"] == "Test IA"
        assert result["niche"] == "Tech & IA"
        assert result["style"] == "liste_educative"
        assert isinstance(result["body_points"], list)
        assert len(result["body_points"]) > 0
        assert isinstance(result["hashtags"], list)
        assert len(result["hashtags"]) > 0

        mock_hf_client.chat.completions.create.assert_called_once()

    def test_generate_script_retry_on_failure(
        self, mock_hf_client, sample_script_data
    ):
        """Vérifie le retry en cas d'échec API.

        Simule 2 échecs (HfHubHTTPError) puis une réussite.
        Le générateur doit réessayer 3 fois puis retourner le résultat.
        """
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            sample_script_data
        )

        mock_hf_client.chat.completions.create.side_effect = [
            HfHubHTTPError("Erreur API 1", response=_MockResponse()),
            HfHubHTTPError("Erreur API 2", response=_MockResponse()),
            mock_response,
        ]

        generator = ScriptGenerator(hf_token="fake_token")
        result = generator.generate_script(
            subject="Test retry",
            niche="Tech",
            style="liste_educative",
        )

        assert result is not None
        assert result["subject"] == "Test retry"
        assert mock_hf_client.chat.completions.create.call_count == 3

    def test_generate_script_empty_subject(
        self, mock_hf_client, sample_script_data
    ):
        """Vérifie la gestion d'un sujet vide.

        Un sujet vide ne doit pas bloquer la génération.
        Le LLM reçoit une chaîne vide et doit produire un résultat valide.
        """
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            sample_script_data
        )
        mock_hf_client.chat.completions.create.return_value = mock_response

        generator = ScriptGenerator(hf_token="fake_token")
        result = generator.generate_script(
            subject="",
            niche="Tech",
            style="liste_educative",
        )

        assert result is not None
        assert result["subject"] == ""
        assert "hook" in result
        mock_hf_client.chat.completions.create.assert_called_once()

    def test_prompt_format(self):
        """Vérifie que le prompt système est correctement formaté.

        Validation :
        - Contient les mots-clés attendus (viral, TikTok, JSON)
        - Les styles disponibles sont définis
        - Le format JSON attendu est documenté
        """
        from agent.script_generator import STYLES_AVAILABLE

        assert "TikTok" in SYSTEM_PROMPT
        assert "JSON" in SYSTEM_PROMPT
        assert "viral" in SYSTEM_PROMPT or "Viral" in SYSTEM_PROMPT
        assert isinstance(STYLES_AVAILABLE, list)
        assert len(STYLES_AVAILABLE) > 0
        assert "storytelling" in STYLES_AVAILABLE
        assert "tutoriel" in STYLES_AVAILABLE

    def test_generate_script_prompt_construction(self, mock_hf_client):
        """Vérifie que le prompt utilisateur est construit correctement.

        Le prompt doit contenir le sujet, la niche, le style
        et le format JSON attendu.
        """
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "hook": "Test",
            "transition": "Test",
            "body_points": ["Point"],
            "cta": "Test",
            "hashtags": ["#test"],
            "description": "Test",
            "music_suggestion": "Test",
            "visual_notes": "Test",
        })
        mock_hf_client.chat.completions.create.return_value = mock_response

        generator = ScriptGenerator(hf_token="fake_token")
        generator.generate_script(
            subject="Python pour debutants",
            niche="Tech & IA",
            style="tutoriel",
        )

        call_args = mock_hf_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Python pour debutants" in messages[1]["content"]
        assert "Tech & IA" in messages[1]["content"]
        assert "tutoriel" in messages[1]["content"]

    def test_generate_script_invalid_style(self):
        """Vérifie qu'un style invalide lève une erreur."""
        generator = ScriptGenerator(hf_token="fake_token")

        with pytest.raises(ValueError, match="style.*invalide"):
            generator.generate_script(
                subject="Test",
                niche="Tech",
                style="style_inexistant",
            )

    def test_generate_script_final_failure(self, mock_hf_client):
        """Vérifie qu'après 3 échecs, une RuntimeError est levée."""
        mock_hf_client.chat.completions.create.side_effect = (
            HfHubHTTPError(
                "Erreur persistante", response=_MockResponse()
            )
        )

        generator = ScriptGenerator(hf_token="fake_token")

        with pytest.raises(RuntimeError, match="Echec.*3 tentatives"):
            generator.generate_script(
                subject="Test",
                niche="Tech",
                style="liste_educative",
            )

        assert mock_hf_client.chat.completions.create.call_count == 3

    def test_generate_script_parse_json_block(self, mock_hf_client):
        """Vérifie le parsing du JSON dans un bloc ```json ```."""
        mock_response = MagicMock()
        raw_content = (
            "Voici le script genere :\n"
            "```json\n"
            '{"hook": "Accroche", "transition": "Transition", '
            '"body_points": ["P1"], "cta": "CTA", '
            '"hashtags": ["#t"], "description": "Desc", '
            '"music_suggestion": "Musique", "visual_notes": "Notes"}\n'
            "```\n"
            "Fin du script."
        )
        mock_response.choices[0].message.content = raw_content
        mock_hf_client.chat.completions.create.return_value = mock_response

        generator = ScriptGenerator(hf_token="fake_token")
        result = generator.generate_script(
            subject="Test",
            niche="Tech",
            style="liste_educative",
        )

        assert result["hook"] == "Accroche"
        assert result["transition"] == "Transition"
        assert result["body_points"] == ["P1"]


@pytest.mark.asyncio
async def test_chat_response_format():
    """Vérifie que chat_response() retourne un texte français, max 3 paragraphes."""
    from agent.script_generator import ScriptGenerator

    gen = ScriptGenerator.__new__(ScriptGenerator)
    gen.client = AsyncMock()
    gen.client.chat.completions.create = AsyncMock()

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=(
                    "Premier paragraphe.\n\n"
                    "Deuxième paragraphe.\n\n"
                    "Troisième paragraphe."
                )
            )
        )
    ]
    gen.client.chat.completions.create.return_value = mock_response

    result = await gen.chat_response(
        "Que devrais-je poster cette semaine ?",
        {
            "niche": "Tech & IA",
            "recent_tasks": [],
            "current_trends": "IA générative",
        },
    )

    assert isinstance(result, str)
    assert len(result) > 0
    paragraphs = result.split("\n\n")
    assert len(paragraphs) <= 3, "Max 3 paragraphes"
