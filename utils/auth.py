from typing import Union
import discord
from discord.ext import commands
import database
from utils.logger import log
from utils.config import config

async def is_admin(ctx_or_int: Union[discord.Interaction, commands.Context]) -> bool:
    """
    Centralized check to see if a user has administrative powers.
    Supports both discord.Interaction and commands.Context.
    Enforces channel restrictions strictly if set.
    """
    # Normalize user, guild, and channel access
    if isinstance(ctx_or_int, discord.Interaction):
        user = ctx_or_int.user
        guild_id = ctx_or_int.guild_id
        channel_id = ctx_or_int.channel_id
        bot = ctx_or_int.client
    elif isinstance(ctx_or_int, commands.Context):
        user = ctx_or_int.author
        guild_id = ctx_or_int.guild.id if ctx_or_int.guild else None
        channel_id = ctx_or_int.channel.id
        bot = ctx_or_int.bot
    else:
        try:
            user = getattr(ctx_or_int, "author", None) or getattr(ctx_or_int, "user", None)
            guild = getattr(ctx_or_int, "guild", None)
            guild_id = guild.id if guild else getattr(ctx_or_int, "guild_id", None)
            channel = getattr(ctx_or_int, "channel", None)
            channel_id = channel.id if channel else getattr(ctx_or_int, "channel_id", None)
            bot = getattr(ctx_or_int, "bot", None) or getattr(ctx_or_int, "client", None)
        except Exception as e:
            log.debug("is_admin fallback context: %s", e)
            return False

    if not user or not bot:
        return False

    # 0. Bot Owner always has access and bypasses all restrictions
    if await bot.is_owner(user):
        return True

    if not guild_id:
        return False

    # Fetch guild settings for auth
    settings = await database.get_all_guild_settings(guild_id)
    
    admin_roles_str = settings.get("admin_role_ids", "")
    admin_channels_str = settings.get("admin_channel_ids", "")

    # 1. STRICT CHANNEL CHECK
    if admin_channels_str:
        allowed_channels = [c.strip() for c in admin_channels_str.split(",") if c.strip().isdigit()]
        if str(channel_id) not in allowed_channels:
            return False

    # 2. Server-wide Administrator has access (if channel check passed)
    if hasattr(user, "guild_permissions") and user.guild_permissions.administrator:
        return True

    # 3. Check Explicit Roles
    if admin_roles_str and hasattr(user, "roles"):
        allowed_roles = [r.strip() for r in admin_roles_str.split(",") if r.strip().isdigit()]
        user_role_ids = [str(r.id) for r in user.roles]
        if any(role_id in allowed_roles for role_id in user_role_ids):
            return True

    # 4. Fallback to config.json for initial setup (if no roles/channels configured in DB)
    if not admin_roles_str and hasattr(user, "roles"):
        try:
            config_role = str(config.get("admin_role_id", ""))
            if config_role and any(str(r.id) == config_role for r in user.roles):
                return True
        except Exception as e:
            log.debug("is_admin config fallback: %s", e)

    return False

async def is_master(ctx_or_int: Union[discord.Interaction, commands.Context]) -> bool:
    """
    Strictest check: Only allows access if the guild is in config.master_guild_ids
    OR if the user is the Bot Owner.
    """
    if isinstance(ctx_or_int, discord.Interaction):
        user = ctx_or_int.user
        guild_id = ctx_or_int.guild_id
        bot = ctx_or_int.client
    elif isinstance(ctx_or_int, commands.Context):
        user = ctx_or_int.author
        guild_id = ctx_or_int.guild.id if ctx_or_int.guild else None
        bot = ctx_or_int.bot
    else:
        return False

    # 0. Bot Owner always has access
    if await bot.is_owner(user):
        return True

    if not guild_id:
        return False

    # 1. Check if guild is a designated Master Hub
    master_ids = config.master_guild_ids
    if master_ids and int(guild_id) in master_ids:
        return await is_admin(ctx_or_int)

    return False


async def is_owner(ctx_or_int: Union[discord.Interaction, commands.Context]) -> bool:
    """
    Absolute highest authority check: Returns True ONLY if the invoking user is the Bot Owner.
    Required for dangerous global operations like global command tree clearing and global sync.
    """
    if isinstance(ctx_or_int, discord.Interaction):
        user = ctx_or_int.user
        bot = ctx_or_int.client
    elif isinstance(ctx_or_int, commands.Context):
        user = ctx_or_int.author
        bot = ctx_or_int.bot
    else:
        try:
            user = getattr(ctx_or_int, "author", None) or getattr(ctx_or_int, "user", None)
            bot = getattr(ctx_or_int, "bot", None) or getattr(ctx_or_int, "client", None)
        except Exception:
            return False

    if not user or not bot:
        return False

    return bool(await bot.is_owner(user))

