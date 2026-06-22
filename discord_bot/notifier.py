"""Envoi de notifications et messages dans Discord.

Contient les fonctions d'envoi asynchrones pour les differents
types de messages (validation, tendances, rapports, rappels).
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import discord
from discord.ext import commands

from discord_bot.channels import get_channel_by_name
from utils.logger import logger

# Mapping niche -> couleur d'embed
NICHE_COLORS: Dict[str, discord.Color] = {
    "tech": discord.Color.blue(),
    "motivation": discord.Color.orange(),
    "sante": discord.Color.green(),
    "mode": discord.Color.purple(),
    "nature": discord.Color.from_rgb(6, 78, 59),
    "cuisine": discord.Color.red(),
    "sport": discord.Color.from_rgb(233, 69, 96),
}

SEASON_COLORS: Dict[str, discord.Color] = {
    "printemps": discord.Color.from_rgb(144, 238, 144),
    "ete": discord.Color.from_rgb(255, 200, 87),
    "automne": discord.Color.from_rgb(210, 105, 30),
    "hiver": discord.Color.from_rgb(176, 224, 230),
}


def _get_niche_color(niche: str) -> discord.Color:
    """Retourne la couleur d'embed associee a une niche.

    Args:
        niche: Nom de la niche.

    Returns:
        Couleur Discord pour l'embed.
    """
    normalized = niche.lower().strip()
    for key, color in NICHE_COLORS.items():
        if key in normalized or normalized in key:
            return color
    return discord.Color.blue()


def _get_season_color() -> discord.Color:
    """Retourne une couleur selon la saison courante.

    Returns:
        Couleur Discord saisonniere.
    """
    month = datetime.now().month
    if 3 <= month <= 5:
        return SEASON_COLORS["printemps"]
    elif 6 <= month <= 8:
        return SEASON_COLORS["ete"]
    elif 9 <= month <= 11:
        return SEASON_COLORS["automne"]
    else:
        return SEASON_COLORS["hiver"]


def _get_report_color(approval_rate: float) -> discord.Color:
    """Retourne une couleur selon le taux d'approbation.

    Args:
        approval_rate: Taux d'approbation (0.0 a 1.0).

    Returns:
        Vert si > 70%, orange si > 50%, rouge sinon.
    """
    if approval_rate >= 0.7:
        return discord.Color.green()
    elif approval_rate >= 0.5:
        return discord.Color.orange()
    return discord.Color.red()


def _format_model_info(task: Dict[str, Any]) -> str:
    """Retourne une chaine avec les infos du modele utilise.

    Args:
        task: Donnees de la tache.

    Returns:
        Texte descriptif du modele/image.
    """
    visual_type = task.get("visual_type", "text_visual")
    model_map = {
        "thumbnail": "SDXL Turbo (1 step)",
        "background": "Stable Diffusion 2.1",
        "text_visual": "Pillow (100% CPU)",
        "illustration": "Kandinsky 2.2",
    }
    return model_map.get(visual_type, "Pillow (100% CPU)")


async def _send_to_channel(
    bot: commands.Bot,
    channel_name: str,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
) -> bool:
    """Envoie un message dans un channel par son nom symbolique.

    Args:
        bot: Instance du bot Discord.
        channel_name: Nom symbolique du channel.
        content: Texte optionnel.
        embed: Embed optionnel.

    Returns:
        True si l'envoi a reussi.
    """
    channel = await get_channel_by_name(bot, channel_name)
    if not channel:
        logger.error("Channel %s introuvable", channel_name)
        return False

    try:
        kwargs = {}
        if content:
            kwargs["content"] = content
        if embed:
            kwargs["embed"] = embed
        await channel.send(**kwargs)
        return True
    except discord.HTTPException as exc:
        logger.error("Erreur envoi channel %s: %s", channel_name, exc)
        return False


async def send_validation(
    bot: commands.Bot,
    task: Dict[str, Any],
    script_data: Dict[str, Any],
    image_path: Optional[str] = None,
) -> bool:
    """Envoie une tache en validation dans le channel dedie.

    Cree un embed riche avec le script, l'image jointe, les hashtags,
    les metadonnees (modele, temps, type de visuel).

    Args:
        bot: Instance du bot Discord.
        task: Donnees de la tache.
        script_data: Donnees du script genere.
        image_path: Chemin vers l'image generee (optionnel).

    Returns:
        True si l'envoi a reussi.
    """
    channel = await get_channel_by_name(bot, "validation")
    if not channel:
        logger.error("Channel validation introuvable")
        return False

    script_title = task.get("subject", "Script TikTok")
    niche = task.get("niche", "Tech & IA")
    style = task.get("style", "educatif")

    hook = script_data.get("hook", "Accroche...")
    description = script_data.get("description", "")
    hashtags_raw = script_data.get("hashtags", [])
    hashtags_str = " ".join(hashtags_raw) if hashtags_raw else ""

    body_points = script_data.get("body_points", [])
    body_text = "\n".join(
        f"{i+1}. {point}" for i, point in enumerate(body_points[:5])
    )

    embed = discord.Embed(
        title=f"🎬 {script_title}",
        description=f"*{hook}*",
        color=_get_niche_color(niche),
    )

    embed.add_field(
        name="📋 Script",
        value=body_text or "Contenu non disponible",
        inline=False,
    )
    embed.add_field(name="🏷️ Niche", value=niche, inline=True)
    embed.add_field(name="🎨 Style", value=style, inline=True)

    model_info = _format_model_info(task)
    embed.add_field(name="🖼️ Type visuel", value=model_info, inline=True)

    embed.add_field(
        name="🎵 Musique suggeree",
        value=script_data.get("music_suggestion", "Non specifiee"),
        inline=False,
    )
    embed.add_field(
        name="👁️ Notes visuelles",
        value=script_data.get("visual_notes", "Non specifiees"),
        inline=False,
    )
    embed.add_field(
        name="📝 Description",
        value=description or "Non disponible",
        inline=False,
    )

    if hashtags_str:
        embed.add_field(name="🏷️ Hashtags", value=hashtags_str, inline=False)

    cta = script_data.get("cta", "")
    if cta:
        embed.add_field(name="🎯 CTA", value=cta, inline=False)

    script_json = json.dumps(script_data, ensure_ascii=False, indent=2)
    if len(script_json) > 1000:
        script_json = script_json[:1000] + "\n... (tronque)"
    embed.add_field(
        name="📄 Script JSON",
        value=f"```json\n{script_json}\n```",
        inline=False,
    )

    embed.set_footer(
        text=(
            f"Tache: {task.get('task_id', '?')} | "
            f"{task.get('created_at', '?')} | "
            f"Modele: {model_info}"
        )
    )

    try:
        if image_path and os.path.exists(image_path):
            filename = os.path.basename(image_path)
            file = discord.File(image_path, filename=filename)
            file_url = f"attachment://{filename}"
            embed.set_image(url=file_url)
            message = await channel.send(embed=embed, file=file)
            logger.info(
                "Validation envoyee avec image pour tache %s (message %d)",
                task.get("task_id"),
                message.id,
            )
        else:
            message = await channel.send(embed=embed)
            logger.info(
                "Validation envoyee (sans image) pour tache %s (message %d)",
                task.get("task_id"),
                message.id,
            )
        return True

    except discord.Forbidden:
        logger.error("Permission refusee pour le channel validation")
        return False
    except discord.HTTPException as exc:
        logger.error("Erreur HTTP Discord: %s", exc)
        return False


async def send_trends(
    bot: commands.Bot,
    trends_data: Dict[str, Any],
) -> bool:
    """Envoie une analyse des tendances dans le channel dedie.

    Embed structure :
    - Top 5 tendances generales
    - Top 3 tendances niche (avec scores)
    - 2 suggestions exploitables
    - Hashtags en hausse
    - Couleur saisonniere

    Args:
        bot: Instance du bot Discord.
        trends_data: Dict du TrendAnalyzer.analyze().

    Returns:
        True si l'envoi a reussi.
    """
    channel = await get_channel_by_name(bot, "tendances")
    if not channel:
        logger.error("Channel tendances introuvable")
        return False

    now = datetime.now()
    date_str = now.strftime("%d/%m/%Y")

    embed = discord.Embed(
        title=f"📊 Tendances du {date_str}",
        description="Analyse multi-sources des tendances actuelles",
        color=_get_season_color(),
    )

    # Top 5 tendances générales
    general = trends_data.get("general_trends", [])
    if general:
        top5 = general[:5]
        lines = []
        for i, t in enumerate(top5, 1):
            volume = t.get("volume_estimate", "?")
            source = t.get("source", "?")
            lines.append(
                f"{i}. **{t['title']}**\n"
                f"   📈 {volume} · {source}"
            )
        embed.add_field(
            name="🔥 Top 5 Tendances générales",
            value="\n".join(lines),
            inline=False,
        )

    # Top 3 tendances niche
    niche_trends = trends_data.get("niche_trends", [])
    if niche_trends:
        top3 = niche_trends[:3]
        lines = []
        for t in top3:
            score = t.get("relevance_score", "?")
            niche = t.get("niche", "?")
            lines.append(
                f"• **{t['title']}**\n"
                f"  Niche: {niche} · Score: {score}/10"
            )
        embed.add_field(
            name="🎯 Top 3 Tendances par niche",
            value="\n".join(lines),
            inline=False,
        )

    # Suggestions exploitables
    suggested = trends_data.get("suggested_topics", [])
    if suggested:
        top2 = suggested[:2]
        lines = []
        for s in top2:
            reason = s.get("reason", "")
            lines.append(f"• **{s['title']}**\n  💡 {reason}")
        embed.add_field(
            name="🚀 Suggestions exploitables",
            value="\n".join(lines),
            inline=False,
        )

    # Hashtags en hausse
    hashtags = trends_data.get("rising_hashtags", [])
    if hashtags:
        embed.add_field(
            name="🏷️ Hashtags en hausse",
            value=" ".join(hashtags[:5]),
            inline=False,
        )

    total_trends = len(general) + len(niche_trends)
    embed.set_footer(text=f"{total_trends} sources analysees | {date_str}")

    try:
        await channel.send(embed=embed)
        logger.info("Tendances envoyees (%d items)", total_trends)
        return True
    except discord.HTTPException as exc:
        logger.error("Erreur envoi tendances: %s", exc)
        return False


async def send_report(
    bot: commands.Bot,
    report_data: Dict[str, Any],
) -> bool:
    """Envoie un rapport hebdomadaire structure dans #rapports.

    Embed long avec 4 sections :
    1. Resume production
    2. Analyse niches
    3. Planning semaine suivante
    4. Metriques systeme
    Couleur selon le taux d'approbation.

    Args:
        bot: Instance du bot Discord.
        report_data: Dict du ReportBuilder.build_weekly_report().

    Returns:
        True si l'envoi a reussi.
    """
    channel = await get_channel_by_name(bot, "rapports")
    if not channel:
        logger.error("Channel rapports introuvable")
        return False

    prod = report_data.get("production", {})
    approval_rate = prod.get("approval_rate", 0.0)
    week = report_data.get("week", "?")

    embed = discord.Embed(
        title=f"📊 Rapport hebdomadaire — Semaine {week}",
        color=_get_report_color(approval_rate),
    )

    # Section 1 : Production
    total = prod.get("total_generated", 0)
    approved = prod.get("approved", 0)
    rejected = prod.get("rejected", 0)
    pending = prod.get("pending", 0)
    avg_time = prod.get("avg_generation_time_s", 0)

    embed.add_field(
        name="📦 Section 1 : Résumé de production",
        value=(
            f"**Total généré :** {total}\n"
            f"✅ **Approuvés :** {approved}\n"
            f"❌ **Rejetés :** {rejected}\n"
            f"⏳ **En attente :** {pending}\n"
            f"📈 **Taux d'approbation :** {approval_rate:.1%}\n"
            f"⚡ **Temps moyen :** {avg_time}s"
        ),
        inline=False,
    )

    # Section 2 : Analyse niches
    niche = report_data.get("niche_analysis", {})
    primary = niche.get("primary_niche", "N/A")
    top_subjects = niche.get("top_subjects", [])
    suggested_topics = niche.get("suggested_topics_next_week", [])

    niche_lines = [f"**Niche principale :** {primary}"]
    if top_subjects:
        niche_lines.append("\n**Top sujets traités :**")
        for s in top_subjects[:3]:
            niche_lines.append(f"• {s}")
    embed.add_field(
        name="🎯 Section 2 : Analyse des niches",
        value="\n".join(niche_lines),
        inline=False,
    )

    # Section 3 : Planning
    planning = report_data.get("planning", {})
    pre_gen = planning.get("pre_generated_topics", [])
    anticipated = planning.get("anticipated_trends", "Non disponible")

    planning_lines = []
    if pre_gen:
        planning_lines.append("**Sujets pré-générés :**")
        for topic in pre_gen[:5]:
            planning_lines.append(f"• {topic}")
    if anticipated:
        planning_lines.append(f"\n**Tendances anticipées :**\n{anticipated[:200]}")

    config = planning.get("recommended_config", {})
    if config:
        planning_lines.append(
            f"\n**Configuration recommandée :**\n"
            f"Style: {config.get('style', 'N/A')} · "
            f"Fréquence: {config.get('frequency', 'N/A')}"
        )

    embed.add_field(
        name="📅 Section 3 : Planning semaine suivante",
        value="\n".join(planning_lines) or "Non disponible",
        inline=False,
    )

    # Section 4 : Système
    system = report_data.get("system", {})
    quality = report_data.get("quality", {})
    rejection_reasons = quality.get("rejection_reasons", {})
    suggestions = quality.get("improvement_suggestions", "")

    sys_lines = [
        f"**Uptime :** {system.get('uptime_hours', 0)}h",
        f"**Erreurs :** {system.get('error_count', 0)}",
        f"**Appels API estimés :** {system.get('estimated_api_calls', 0)}",
    ]

    if rejection_reasons:
        sys_lines.append("\n**Raisons de rejet :**")
        for reason, count in rejection_reasons.items():
            sys_lines.append(f"• {reason}: {count}x")

    if suggestions:
        sys_lines.append(f"\n**Suggestions d'amélioration :**\n{suggestions[:300]}")

    embed.add_field(
        name="⚙️ Section 4 : Métriques système & Qualité",
        value="\n".join(sys_lines),
        inline=False,
    )

    embed.set_footer(text=f"Rapport semaine {week} | tiktok-agent")

    try:
        await channel.send(embed=embed)
        logger.info("Rapport hebdo envoyé: semaine %s", week)
        return True
    except discord.HTTPException as exc:
        logger.error("Erreur envoi rapport: %s", exc)
        return False


async def send_simple_message(
    bot: commands.Bot,
    channel_id: int,
    content: str,
) -> bool:
    """Envoie un message simple dans un channel.

    Args:
        bot: Instance du bot Discord.
        channel_id: ID du channel de destination.
        content: Contenu du message.

    Returns:
        True si l'envoi a reussi.
    """
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.warning("Channel introuvable: %d", channel_id)
        return False

    try:
        await channel.send(content)
        return True
    except discord.HTTPException as exc:
        logger.error("Erreur envoi message simple: %s", exc)
        return False
