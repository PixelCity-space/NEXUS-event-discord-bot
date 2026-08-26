import math
import traceback
import discord
from discord import ui
from utils import emojis
from utils.i18n import t
from utils.logger import log
from utils.emoji_utils import make_button

class ReliabilityAuditView(ui.LayoutView):
    """View displaying paginated attendance reliability leaderboard and no-show audits."""
    
    def __init__(self, bot, guild: discord.Guild, stats: list, title: str = "Reliability Audit"):
        super().__init__(timeout=600)
        self.bot = bot
        self.guild = guild
        self.stats = stats
        self.audit_title = title
        self.page = 0
        self.per_page = 10 

    async def build(self):
        self.clear_items()
        
        start = self.page * self.per_page
        end = start + self.per_page
        page_stats = self.stats[start:end]
        total_pages = math.ceil(len(self.stats) / self.per_page) if self.stats else 1
        
        container_items = [
            ui.TextDisplay(self.audit_title),
            ui.TextDisplay(f"-# {t('LBL_AUDIT_ENTRIES', guild_id=self.guild.id).replace('{count}', str(len(self.stats)))} • {t('LBL_PAGE', guild_id=self.guild.id)} {self.page + 1}/{total_pages}"),
            ui.Separator()
        ]
        
        for i, s in enumerate(page_stats):
            idx = (self.page * self.per_page) + i + 1
            uid = s["user_id"]
            ns = int(s["noshow_count"] or 0)
            tot = int(s["total_past_rsvps"] or 0)
            ratio = ns / tot if tot > 0 else 0
            
            member = self.guild.get_member(int(uid))
            if not member and self.guild:
                try:
                    member = await self.guild.fetch_member(int(uid))
                except Exception:
                    pass
                
            name = member.display_name if member else t("LBL_USER_DEFAULT", guild_id=self.guild.id).replace("{uid}", str(uid))
            status_label = f"{ns}/{tot} ({ratio*100:.1f}%)"
            container_items.append(ui.TextDisplay(f"**{idx}. {name}** - {status_label}"))

        if total_pages > 1:
            container_items.append(ui.Separator())
            prev_btn = make_button(label=emojis.BACK, style=discord.ButtonStyle.gray, disabled=(self.page == 0))
            next_btn = make_button(label=emojis.FORWARD, style=discord.ButtonStyle.gray, disabled=(self.page >= total_pages - 1))
            
            async def prev_cb(it: discord.Interaction):
                try:
                    await it.response.defer()
                except Exception:
                    pass
                self.page -= 1
                await self.refresh(it)
                
            async def next_cb(it: discord.Interaction):
                try:
                    await it.response.defer()
                except Exception:
                    pass
                self.page += 1
                await self.refresh(it)
                
            prev_btn.callback = prev_cb
            next_btn.callback = next_cb
            container_items.append(ui.ActionRow(prev_btn, next_btn))

        main_container = ui.Container(*container_items, accent_color=0x40C4FF)
        self.add_item(main_container)

    async def refresh(self, interaction: discord.Interaction):
        await self.build()
        log.info(f"[Audit] Refresh page: {self.page}")
        await interaction.edit_original_response(view=self)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item):
        log.error(f"[Audit View] Error: {error}\n{traceback.format_exc()}")
        try: 
            msg = t('ERR_WIZARD_GENERAL', guild_id=self.guild.id).replace('{e}', str(error))
            await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            pass
