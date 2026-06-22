"""Tests unitaires pour les slash commands Discord.

Vérifie que les 9 commandes sont enregistrées et que
chacune appelle bien defer() pour accuser réception.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_slash_commands_registered():
    """Vérifie que les 9 commandes sont enregistrées dans le bot."""
    # On utilise un bot entièrement mocké car on ne teste que
    # le câblage des commandes via register_commands()
    bot = MagicMock()

    # Simuler tree.command pour capturer les noms enregistrés
    registered = []

    def capture_command(name=None, description=None):
        def decorator(func):
            registered.append(name)
            cmd = MagicMock()
            cmd.name = name
            cmd.callback = func
            return cmd

        return decorator

    bot.tree.command = capture_command

    from discord_bot.commands import register_commands

    await register_commands(bot)

    expected = [
        "generer",
        "tendances",
        "niche",
        "statut",
        "rapport",
        "planifier",
        "historique",
        "config",
        "aide",
    ]
    for cmd in expected:
        assert cmd in registered, f"Commande /{cmd} manquante"
    assert len(registered) == 9


async def test_generer_defer_response():
    """Vérifie que /generer appelle defer()."""
    from discord_bot.commands import generer

    ctx = AsyncMock()
    ctx.response.defer = AsyncMock()
    ctx.client = MagicMock()

    try:
        await generer(ctx, sujet="test")
    except Exception:
        pass

    ctx.response.defer.assert_awaited_once()


async def test_tendances_defer():
    """Vérifie que /tendances appelle defer()."""
    from discord_bot.commands import tendances

    ctx = AsyncMock()
    ctx.response.defer = AsyncMock()
    ctx.client = MagicMock()

    try:
        await tendances(ctx)
    except Exception:
        pass

    ctx.response.defer.assert_awaited_once()


async def test_niche_cmd_defer():
    """Vérifie que /niche appelle defer()."""
    from discord_bot.commands import niche_cmd

    ctx = AsyncMock()
    ctx.response.defer = AsyncMock()
    ctx.client = MagicMock()

    try:
        await niche_cmd(ctx, niche="Tech")
    except Exception:
        pass

    ctx.response.defer.assert_awaited_once()


async def test_statut_defer():
    """Vérifie que /statut appelle defer()."""
    from discord_bot.commands import statut

    ctx = AsyncMock()
    ctx.response.defer = AsyncMock()
    ctx.client = MagicMock()

    try:
        await statut(ctx)
    except Exception:
        pass

    ctx.response.defer.assert_awaited_once()


async def test_rapport_defer():
    """Vérifie que /rapport appelle defer()."""
    from discord_bot.commands import rapport

    ctx = AsyncMock()
    ctx.response.defer = AsyncMock()
    ctx.client = MagicMock()

    try:
        await rapport(ctx)
    except Exception:
        pass

    ctx.response.defer.assert_awaited_once()


async def test_planifier_defer():
    """Vérifie que /planifier appelle defer()."""
    from discord_bot.commands import planifier

    ctx = AsyncMock()
    ctx.response.defer = AsyncMock()
    ctx.client = MagicMock()

    try:
        await planifier(ctx, sujet="test", jour="2026-07-01", heure="14:00")
    except Exception:
        pass

    ctx.response.defer.assert_awaited_once()


async def test_historique_defer():
    """Vérifie que /historique appelle defer()."""
    from discord_bot.commands import historique

    ctx = AsyncMock()
    ctx.response.defer = AsyncMock()
    ctx.client = MagicMock()

    try:
        await historique(ctx)
    except Exception:
        pass

    ctx.response.defer.assert_awaited_once()


async def test_config_cmd_defer():
    """Vérifie que /config appelle defer()."""
    from discord_bot.commands import config_cmd

    ctx = AsyncMock()
    ctx.response.defer = AsyncMock()
    ctx.client = MagicMock()

    try:
        await config_cmd(ctx, parametre="style", valeur="tutoriel")
    except Exception:
        pass

    ctx.response.defer.assert_awaited_once()


async def test_aide_defer():
    """Vérifie que /aide appelle defer()."""
    from discord_bot.commands import aide

    ctx = AsyncMock()
    ctx.response.defer = AsyncMock()
    ctx.client = MagicMock()

    try:
        await aide(ctx)
    except Exception:
        pass

    ctx.response.defer.assert_awaited_once()
