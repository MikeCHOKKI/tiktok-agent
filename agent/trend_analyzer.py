"""Analyse multi-sources des tendances pour le tiktok-agent.

Scrape Google Trends RSS, YouTube Trends (si API key configurée),
et produit des suggestions de sujets exploitables avec scores de pertinence.
"""

import datetime
import time
from typing import Any, Dict, List, Optional

import feedparser
import requests

from utils.logger import logger

CACHE_TTL_SECONDS = 1800  # 30 minutes
SOURCE_TIMEOUT = 15  # secondes par source
MIN_RATE_INTERVAL = 1800  # 1 appel toutes les 30 minutes max

NICHE_FALLBACK_TOPICS: Dict[str, List[str]] = {
    "Tech & IA": [
        "3 outils IA gratuits que vous utilisez tous les jours",
        "ChatGPT vs DeepSeek : lequel choisir en 2026",
        "Python en 60 secondes : une fonction qui change tout",
        "L'IA qui remplace Photoshop (et c'est gratuit)",
        "5 extensions VS Code pour coder 2x plus vite",
    ],
    "Cuisine": [
        "La recette en 30 secondes chrono",
        "L'astuce de chef que personne ne connaît",
        "3 ingrédients, 10 minutes, un plat de restaurant",
    ],
    "Sport": [
        "L'exercice qui brûle le plus de calories",
        "La routine 5 minutes pour se remettre en forme",
    ],
    "Motivation": [
        "Pourquoi vous procrastinez (et comment arrêter)",
        "La règle des 5 secondes qui change tout",
    ],
}

GENERIC_FALLBACK = [
    "3 astuces que personne ne vous a jamais montrées",
    "Le secret que les pros ne veulent pas que vous sachiez",
    "J'ai testé pendant 30 jours et voici ce qui s'est passé",
    "Pourquoi tout le monde se trompe sur ce sujet",
    "La méthode qui a changé ma vie en une semaine",
]


class TrendAnalyzer:
    """Analyseur multi-sources des tendances.

    Agrège Google Trends RSS, YouTube API (optionnel), et produit
    un rapport structuré avec suggestions de sujets exploitables.

    Attributes:
        google_trends_url: URL du flux RSS Google Trends.
        youtube_api_key: Clé API YouTube (optionnelle).
        niche_urls: Flux RSS additionnels par niche.
        _last_scan: Timestamp du dernier scan effectué.
        _cached_result: Résultat mis en cache du dernier scan.
    """

    def __init__(
        self,
        google_trends_url: str = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=FR",
        youtube_api_key: str = "",
        niche_urls: Optional[List[str]] = None,
    ) -> None:
        """Initialise l'analyseur de tendances.

        Args:
            google_trends_url: URL du flux RSS Google Trends.
            youtube_api_key: Clé API YouTube (optionnelle).
            niche_urls: Flux RSS additionnels par niche.
        """
        self.google_trends_url = google_trends_url
        self.youtube_api_key = youtube_api_key
        self.niche_urls = niche_urls or []
        self._last_scan: Optional[float] = None
        self._cached_result: Optional[Dict[str, Any]] = None

    def analyze(self, niche: Optional[str] = None) -> Dict[str, Any]:
        """Analyse les tendances multi-sources.

        Respecte le cache (30 min) et le rate limiting (1 appel / 30 min).

        Args:
            niche: Niche de contenu pour les suggestions spécialisées.

        Returns:
            Dict structuré avec general_trends, niche_trends,
            suggested_topics, rising_hashtags, vitality_scores.
        """
        # Cache check
        if self._is_cache_valid():
            logger.info("Analyse tendances : utilisation du cache")
            return self._cached_result  # type: ignore

        now = datetime.datetime.now()
        analyzed_at = now.isoformat()

        general_trends: List[Dict[str, Any]] = []
        niche_trends: List[Dict[str, Any]] = []
        all_hashtags: List[str] = []

        # Source 1 : Google Trends RSS
        try:
            google_trends = self._fetch_google_trends()
            general_trends.extend(google_trends)
            logger.info("Google Trends : %d tendances récupérées", len(google_trends))
        except (RuntimeError, OSError) as exc:
            logger.warning("Google Trends RSS indisponible : %s", exc)

        # Source 2 : YouTube Trends (optionnel)
        if self.youtube_api_key:
            try:
                youtube_trends = self._fetch_youtube_trends()
                general_trends.extend(youtube_trends)
                logger.info("YouTube Trends : %d vidéos récupérées", len(youtube_trends))
            except (RuntimeError, OSError) as exc:
                logger.warning("YouTube API indisponible : %s", exc)

        # Extraire les hashtags des tendances générales
        all_hashtags = self._extract_hashtags(general_trends)

        # Générer les tendances de niche
        niche_trends = self._generate_niche_trends(general_trends, niche)

        # Générer les sujets suggérés
        suggested_topics = self._suggest_topics(
            general_trends, niche_trends, niche
        )

        # Scores de viralité
        vitality_scores = self._compute_vitality_scores(general_trends)

        # Hashtags montants
        rising_hashtags = self._extract_rising_hashtags(
            general_trends, niche_trends
        )

        result: Dict[str, Any] = {
            "analyzed_at": analyzed_at,
            "general_trends": general_trends,
            "niche_trends": niche_trends,
            "suggested_topics": suggested_topics,
            "rising_hashtags": rising_hashtags,
            "vitality_scores": vitality_scores,
        }

        # Mise en cache
        self._last_scan = time.time()
        self._cached_result = result

        logger.info(
            "Analyse tendances terminée : %d générales, %d niche, %d sujets suggérés",
            len(general_trends),
            len(niche_trends),
            len(suggested_topics),
        )
        return result

    def suggest_topics(self, niche: Optional[str] = None, count: int = 5) -> List[Dict[str, Any]]:
        """Retourne des suggestions de sujets pour la niche.

        Utilise le cache si disponible, sinon déclenche une analyse.

        Args:
            niche: Niche de contenu.
            count: Nombre de sujets souhaités.

        Returns:
            Liste de dicts {title, reason}.
        """
        if self._is_cache_valid() and self._cached_result:
            topics = self._cached_result.get("suggested_topics", [])
        else:
            result = self.analyze(niche=niche)
            topics = result.get("suggested_topics", [])
        return topics[:count]

    def _fetch_google_trends(self) -> List[Dict[str, Any]]:
        """Récupère les tendances depuis Google Trends RSS.

        Returns:
            Liste de tendances avec titre, source, volume estimé.

        Raises:
            RuntimeError: Si le flux est inaccessible ou vide.
        """
        try:
            feed = feedparser.parse(self.google_trends_url)
        except Exception as exc:
            raise RuntimeError(
                f"Erreur chargement flux Google Trends : {exc}"
            ) from exc

        if not feed.entries:
            raise RuntimeError("Flux Google Trends vide ou inaccessible")

        trends = []
        volume_map = {
            "1": "très élevé",
            "2": "élevé",
            "3": "moyen",
            "4": "modéré",
            "5": "faible",
        }

        for entry in feed.entries[:20]:
            title = entry.get("title", "").strip()
            if not title:
                continue

            # Estimation du volume via l'ordre dans le flux
            approx_volume = "élevé"
            ht_news = entry.get("ht_news_item", {})
            if isinstance(ht_news, list) and ht_news:
                approx_volume = volume_map.get(
                    str(len(ht_news)), "moyen"
                )

            trends.append({
                "title": title,
                "source": "google_trends",
                "volume_estimate": approx_volume,
            })

        return trends

    def _fetch_youtube_trends(self) -> List[Dict[str, Any]]:
        """Récupère les tendances depuis l'API YouTube.

        Returns:
            Liste de vidéos tendances avec titre, source, volume.

        Raises:
            RuntimeError: Si l'appel API échoue.
        """
        url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet&chart=mostPopular&regionCode=FR"
            f"&maxResults=10&key={self.youtube_api_key}"
        )

        try:
            response = requests.get(url, timeout=SOURCE_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Erreur API YouTube : {exc}"
            ) from exc

        items = data.get("items", [])
        trends = []
        for item in items:
            snippet = item.get("snippet", {})
            title = snippet.get("title", "").strip()
            if not title:
                continue
            channel = snippet.get("channelTitle", "Inconnu")
            trends.append({
                "title": title,
                "source": "youtube_trends",
                "volume_estimate": "élevé",
                "channel": channel,
                "category": snippet.get("categoryId", ""),
            })

        return trends

    def _generate_niche_trends(
        self,
        general_trends: List[Dict[str, Any]],
        niche: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Génère des tendances spécifiques à une niche.

        Filtre les tendances générales par pertinence supposée
        avec la niche donnée.

        Args:
            general_trends: Liste des tendances générales.
            niche: Niche de contenu.

        Returns:
            Liste de tendances de niche avec score de pertinence.
        """
        if not niche:
            return []

        niche_lower = niche.lower()
        keywords = niche_lower.replace("&", "").split()

        niche_trends = []
        for trend in general_trends:
            title = trend.get("title", "").lower()
            score = sum(1 for kw in keywords if kw in title)
            if score > 0:
                niche_trends.append({
                    "title": trend["title"],
                    "niche": niche,
                    "relevance_score": min(score * 3 + 5, 10),
                })

        # Si pas assez de résultats, ajouter des sujets génériques
        if len(niche_trends) < 3:
            fallback = NICHE_FALLBACK_TOPICS.get(niche, GENERIC_FALLBACK)
            for fb in fallback[:5]:
                already = any(
                    t["title"] == fb for t in niche_trends
                )
                if not already:
                    niche_trends.append({
                        "title": fb,
                        "niche": niche,
                        "relevance_score": 6,
                    })

        return niche_trends[:5]

    def _suggest_topics(
        self,
        general_trends: List[Dict[str, Any]],
        niche_trends: List[Dict[str, Any]],
        niche: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Génère des suggestions de sujets exploitables.

        Combine tendances générales et niche pour produire
        des idées de contenu actionnables.

        Args:
            general_trends: Tendances générales.
            niche_trends: Tendances de niche.
            niche: Niche de contenu.

        Returns:
            Liste de suggestions {title, reason}.
        """
        suggested: List[Dict[str, Any]] = []
        used_titles: set = set()

        # Suggestions depuis les tendances de niche
        for nt in niche_trends:
            title = nt.get("title", "")
            if title not in used_titles and len(suggested) < 5:
                suggested.append({
                    "title": title,
                    "reason": f"En lien avec la niche {nt.get('niche', niche or 'générale')}",
                })
                used_titles.add(title)

        # Compléter avec les tendances générales
        for gt in general_trends:
            title = gt.get("title", "")
            if title not in used_titles and len(suggested) < 5:
                source = gt.get("source", "tendances")
                suggested.append({
                    "title": title,
                    "reason": f"Tendance {source} — volume {gt.get('volume_estimate', 'moyen')}",
                })
                used_titles.add(title)

        # Fallback si aucune suggestion
        if not suggested:
            fallback = NICHE_FALLBACK_TOPICS.get(
                niche or "", GENERIC_FALLBACK
            )
            for fb in fallback[:5]:
                suggested.append({
                    "title": fb,
                    "reason": "Sujet générique pour la niche",
                })

        return suggested

    def _extract_hashtags(
        self,
        trends: List[Dict[str, Any]],
    ) -> List[str]:
        """Extrait des hashtags depuis les titres de tendances.

        Args:
            trends: Liste de tendances.

        Returns:
            Liste de hashtags.
        """
        hashtags = []
        stop_words = {"les", "des", "pour", "dans", "avec", "une", "son", "ses"}

        for trend in trends:
            title = trend.get("title", "")
            words = title.lower().split()[:3]
            for word in words:
                clean = word.strip("'\".,!?;:")
                if (
                    len(clean) > 3
                    and clean not in stop_words
                    and not clean.isdigit()
                ):
                    hashtag = f"#{clean.replace(' ', '')}"
                    if hashtag not in hashtags:
                        hashtags.append(hashtag)

        return hashtags[:10]

    def _extract_rising_hashtags(
        self,
        general_trends: List[Dict[str, Any]],
        niche_trends: List[Dict[str, Any]],
    ) -> List[str]:
        """Extrait les hashtags montants depuis toutes les sources.

        Args:
            general_trends: Tendances générales.
            niche_trends: Tendances de niche.

        Returns:
            Liste des hashtags montants (top 5).
        """
        combined = general_trends + niche_trends
        all_tags = self._extract_hashtags(combined)
        return all_tags[:5]

    def _compute_vitality_scores(
        self,
        trends: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Calcule un score de viralité pour chaque tendance.

        Args:
            trends: Liste de tendances.

        Returns:
            Dict {titre_tendance: score_vitalité}.
        """
        scores: Dict[str, str] = {}
        for trend in trends[:10]:
            title = trend.get("title", "")
            volume = trend.get("volume_estimate", "moyen")
            # Mapping volume -> score de viralité
            score_map = {
                "très élevé": "très haut",
                "élevé": "haut",
                "moyen": "moyen",
                "modéré": "modéré",
                "faible": "faible",
            }
            scores[title] = score_map.get(volume, "moyen")
        return scores

    def _is_cache_valid(self) -> bool:
        """Vérifie si le cache est encore valide.

        Returns:
            True si le cache est récent (< 30 min).
        """
        if not self._last_scan or not self._cached_result:
            return False
        elapsed = time.time() - self._last_scan
        return elapsed < CACHE_TTL_SECONDS

    def invalidate_cache(self) -> None:
        """Invalide le cache pour forcer un rescrap au prochain appel."""
        self._last_scan = None
        self._cached_result = None
        logger.info("Cache tendances invalidé")
