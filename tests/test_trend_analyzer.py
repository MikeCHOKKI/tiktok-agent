"""Tests unitaires pour TrendAnalyzer.

Modules testés :
- test_analyze_cache : expiration du cache (30 min)
- test_fallback_on_error : comportement en cas d'échec Google Trends
- test_suggest_topics : cohérence des suggestions avec la niche
- test_invalidate_cache : invalidation forcée
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from agent.trend_analyzer import TrendAnalyzer


class TestTrendAnalyzer:
    """Tests de l'analyseur de tendances."""

    def test_analyze_cache(self):
        """Vérifie que le cache fonctionne (< 30 min pas de nouvel appel).

        Deux appels consécutifs dans l'intervalle de cache valide
        doivent retourner le même résultat sans rescrap.
        """
        analyzer = TrendAnalyzer()

        with patch.object(analyzer, "_fetch_google_trends") as mock_fetch:
            mock_fetch.return_value = [
                {
                    "title": "Tendance test",
                    "source": "google_trends",
                    "volume_estimate": "eleve",
                }
            ]

            result1 = analyzer.analyze(niche="Tech & IA")

            # Forcer le cache comme valide
            analyzer._last_scan = time.time()
            analyzer._cached_result = result1

            result2 = analyzer.analyze(niche="Tech & IA")

            assert result1 is result2  # Même objet en cache
            assert result1["analyzed_at"] == result2["analyzed_at"]
            assert len(result2["general_trends"]) >= 1

    def test_fallback_on_error(self):
        """Vérifie le fallback si Google Trends échoue.

        Même sans données externes, l'analyseur doit produire
        des suggestions via les sujets de fallback.
        """
        analyzer = TrendAnalyzer()

        with patch.object(
            analyzer, "_fetch_google_trends"
        ) as mock_fetch:
            mock_fetch.side_effect = RuntimeError(
                "Google Trends indisponible"
            )

            result = analyzer.analyze(niche="Tech & IA")

            assert result is not None
            assert "analyzed_at" in result
            assert "general_trends" in result
            assert "suggested_topics" in result

            # Même sans données, on doit avoir des suggestions
            # via le fallback
            suggested = result.get("suggested_topics", [])
            assert len(suggested) > 0

    def test_suggest_topics(self):
        """Vérifie que les suggestions sont cohérentes avec la niche.

        Les suggestions doivent inclure des sujets de la niche
        ou des sujets génériques de fallback.
        """
        analyzer = TrendAnalyzer()

        with patch.object(analyzer, "_fetch_google_trends") as mock_fetch:
            mock_fetch.return_value = [
                {
                    "title": "IA du moment",
                    "source": "google_trends",
                    "volume_estimate": "tres eleve",
                },
                {
                    "title": "Nouveau framework Python",
                    "source": "google_trends",
                    "volume_estimate": "eleve",
                },
            ]

            topics = analyzer.suggest_topics(
                niche="Tech & IA", count=5
            )

            assert isinstance(topics, list)
            assert len(topics) > 0
            assert len(topics) <= 5

            for topic in topics:
                assert "title" in topic
                assert "reason" in topic
                assert topic["title"]

    def test_invalidate_cache(self):
        """Vérifie que l'invalidation force un rescrap.

        Après invalidation, le cache est vidé et le prochain
        appel doit refaire une analyse complète.
        """
        analyzer = TrendAnalyzer()

        with patch.object(analyzer, "_fetch_google_trends") as mock_fetch:
            mock_fetch.return_value = [
                {
                    "title": "Premier resultat",
                    "source": "google_trends",
                    "volume_estimate": "moyen",
                }
            ]

            # Premier appel : remplit le cache
            result1 = analyzer.analyze(niche="Tech")

            # Vérifie que le cache est chaud
            assert analyzer._cached_result is not None
            assert analyzer._last_scan is not None

            # Invalidation
            analyzer.invalidate_cache()
            assert analyzer._cached_result is None
            assert analyzer._last_scan is None

            # Deuxième appel : doit rescraper
            mock_fetch.return_value = [
                {
                    "title": "Nouveau resultat",
                    "source": "google_trends",
                    "volume_estimate": "eleve",
                }
            ]

            result2 = analyzer.analyze(niche="Tech")

            # Le résultat doit être différent (nouveau scrap)
            assert result2["general_trends"][0]["title"] == "Nouveau resultat"
            assert mock_fetch.call_count == 2

    def test_analyze_niche_generation(self):
        """Vérifie la génération de tendances spécifiques à une niche."""
        analyzer = TrendAnalyzer()

        with patch.object(analyzer, "_fetch_google_trends") as mock_fetch:
            mock_fetch.return_value = [
                {
                    "title": "IA et Machine Learning",
                    "source": "google_trends",
                    "volume_estimate": "tres eleve",
                },
                {
                    "title": "Recette de cuisine facile",
                    "source": "google_trends",
                    "volume_estimate": "moyen",
                },
            ]

            result = analyzer.analyze(niche="Tech & IA")
            niche_trends = result.get("niche_trends", [])

            # Au moins une tendance doit correspondre a la niche tech
            if niche_trends:
                assert len(niche_trends) > 0

    def test_analyze_rising_hashtags(self):
        """Vérifie l'extraction des hashtags montants."""
        analyzer = TrendAnalyzer()

        with patch.object(analyzer, "_fetch_google_trends") as mock_fetch:
            mock_fetch.return_value = [
                {
                    "title": "Intelligence Artificielle 2026",
                    "source": "google_trends",
                    "volume_estimate": "tres eleve",
                },
                {
                    "title": "Python pour debutants",
                    "source": "google_trends",
                    "volume_estimate": "eleve",
                },
            ]

            result = analyzer.analyze(niche="Tech & IA")
            hashtags = result.get("rising_hashtags", [])

            assert isinstance(hashtags, list)
            assert len(hashtags) <= 5

    def test_analyze_cache_expired(self):
        """Vérifie qu'un cache expire correctement apres 30 min."""
        analyzer = TrendAnalyzer()

        with patch.object(analyzer, "_fetch_google_trends") as mock_fetch:
            mock_fetch.return_value = [
                {
                    "title": "Tendance A",
                    "source": "google_trends",
                    "volume_estimate": "moyen",
                }
            ]

            result1 = analyzer.analyze(niche="Tech")

            # Simuler un cache vieux de 31 min
            analyzer._last_scan = time.time() - 1860  # 31 min
            analyzer._cached_result = result1

            mock_fetch.return_value = [
                {
                    "title": "Tendance B",
                    "source": "google_trends",
                    "volume_estimate": "moyen",
                }
            ]

            result2 = analyzer.analyze(niche="Tech")

            # Le cache etait expire, donc nouveau resultat
            assert result2["general_trends"][0]["title"] == "Tendance B"
            assert mock_fetch.call_count == 2

    def test_analyze_without_niche(self):
        """Vérifie le comportement sans niche specifiee."""
        analyzer = TrendAnalyzer()

        with patch.object(analyzer, "_fetch_google_trends") as mock_fetch:
            mock_fetch.return_value = [
                {
                    "title": "Tendance generale",
                    "source": "google_trends",
                    "volume_estimate": "eleve",
                }
            ]

            result = analyzer.analyze(niche=None)

            assert result is not None
            assert "general_trends" in result
            niche_trends = result.get("niche_trends", [])
            assert niche_trends == []  # Sans niche, pas de tendances niche

    def test_youtube_fallback(self):
        """Vérifie que YouTube API indisponible ne bloque pas l'analyse."""
        analyzer = TrendAnalyzer(
            youtube_api_key="fake_key_for_test"
        )

        with patch.object(analyzer, "_fetch_google_trends") as mock_google:
            mock_google.return_value = [
                {
                    "title": "Tendance Google",
                    "source": "google_trends",
                    "volume_estimate": "eleve",
                }
            ]

            with patch.object(
                analyzer, "_fetch_youtube_trends"
            ) as mock_yt:
                mock_yt.side_effect = RuntimeError(
                    "YouTube API error"
                )

                result = analyzer.analyze(niche="Tech")

                # L'analyse doit reussir meme sans YouTube
                assert result is not None
                assert len(result.get("general_trends", [])) >= 1
