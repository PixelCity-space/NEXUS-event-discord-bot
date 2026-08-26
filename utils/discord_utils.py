import re
from typing import Optional, Union
import discord
from utils.logger import log

async def resolve_channel(guild: Optional[discord.Guild], channel_query: Union[str, int, None]) -> Optional[int]:
    """
    Tries to resolve a channel by ID, mention (<#ID>), or Name.
    Returns the integer channel_id or None if not found.
    """
    if not guild or not channel_query:
        return None

    query = str(channel_query).strip()

    # Extract ID from mention (<#123456789>) or strip leading #
    mention_match = re.match(r'^<#(\d+)>$', query)
    if mention_match:
        query = mention_match.group(1)
    else:
        query = query.lstrip('#').strip()

    # Try numeric ID lookup
    if query.isdigit():
        chan = guild.get_channel(int(query))
        if chan:
            return chan.id

    # Try matching by name
    for chan in guild.channels:
        if chan.name == query:
            return chan.id

    return None

def resolve_role(guild: Optional[discord.Guild], role_query: Union[str, int, None]) -> Optional[discord.Role]:
    """
    Tries to resolve a role by ID, mention (<@&ID>), or Name.
    Returns the discord.Role object or None if not found.
    """
    if not guild or not role_query:
        return None

    query = str(role_query).strip()

    mention_match = re.match(r'^<@&(\d+)>$', query)
    if mention_match:
        query = mention_match.group(1)
    else:
        query = query.lstrip('@').strip()

    if query.isdigit():
        role = guild.get_role(int(query))
        if role:
            return role

    for role in guild.roles:
        if role.name == query:
            return role

    return None

async def resolve_user(bot: discord.Client, user_id: Union[str, int, None]) -> Optional[Union[discord.User, discord.Member]]:
    """
    Safely resolves a Discord user or member from cache or API fetch.
    Returns discord.User/Member or None.
    """
    if not user_id:
        return None

    try:
        uid = int(str(user_id).strip().strip('<@!>&'))
        user = bot.get_user(uid)
        if user:
            return user
        return await bot.fetch_user(uid)
    except Exception as e:
        log.debug(f"[DiscordUtils] Could not resolve user {user_id}: {e}")
        return None
