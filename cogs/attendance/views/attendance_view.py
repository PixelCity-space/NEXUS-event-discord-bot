from typing import Any
import math
import traceback
import discord
from discord import ui
from utils.i18n import t
from utils.logger import log
from utils import emojis
from utils.emoji_utils import make_button
from services.attendance_service import (
    calculate_attendance_stats,
    toggle_user_attendance,
    resolve_member_names_batch,
)

class AttendanceView(ui.LayoutView):
    """Interactive Discord Components V2 view for managing event attendance and no-shows."""
    
    def __init__(
        self, 
        bot: discord.Client, 
        event_id: str, 
        participants: list[dict[str, Any]], 
        guild_id: int | str, 
        title: str = "Event"
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.event_id = event_id
        self.participants = participants  # list of dicts {user_id, status, attendance}
        self.guild_id = guild_id
        self.event_title = title
        self.page: int = 0
        self.per_page: int = 5  # Section layout: 5 users fit comfortably
        self.name_cache: dict[str, str] = {}

    async def build(self) -> None:
        self.clear_items()
        
        start = self.page * self.per_page
        end = start + self.per_page
        page_users = self.participants[start:end]
        total_pages = math.ceil(len(self.participants) / self.per_page) if self.participants else 1
        
        # 1. Parallel Member Resolution via AttendanceService
        page_uids = [str(p["user_id"]) for p in page_users]
        self.name_cache = await resolve_member_names_batch(
            self.bot, self.guild_id, page_uids, self.name_cache
        )

        # 2. Prepare Container Items with AttendanceService Stats
        attended, no_shows, _ = calculate_attendance_stats(self.participants)
        
        stats_text = t("MSG_ATT_STATS", guild_id=self.guild_id)
        stats_text = stats_text.replace("{attended}", str(attended))
        stats_text = stats_text.replace("{noshows}", str(no_shows))
        
        page_label = f"{t('LBL_PAGE', guild_id=self.guild_id)} {self.page + 1}/{total_pages}"
        
        container_items = [
            ui.TextDisplay(f"### {self.event_title}"),
            ui.TextDisplay(f"-# {stats_text} • {page_label}"),
            ui.Separator()
        ]
        
        for i, p in enumerate(page_users):
            idx = (self.page * self.per_page) + i + 1
            uid = str(p["user_id"])
            att = p.get("attendance", "present")
            is_noshow = (att == "no_show")
            
            user_name = self.name_cache.get(uid, t("LBL_USER_DEFAULT", guild_id=self.guild_id).replace("{uid}", str(uid)))
            label = t("LBL_ATT_NOSHOW", guild_id=self.guild_id) if is_noshow else t("LBL_ATT_PRESENT", guild_id=self.guild_id)
            style = discord.ButtonStyle.secondary
            
            toggle_btn = make_button(
                label=label, 
                style=style, 
                custom_id=f"att_tg_{uid}_{self.page}"
            )
            
            def create_callback(u_id: str, current_att: str, current_idx: int):
                async def callback(interaction: discord.Interaction):
                    try:
                        await interaction.response.defer()
                    except Exception:
                        pass
                    
                    log.info(f"[Attendance Debug] SECTION CLICK: User #{current_idx} (UID: {u_id})")
                    try:
                        new_att = await toggle_user_attendance(self.event_id, u_id, current_att)
                        for part in self.participants:
                            if str(part["user_id"]) == str(u_id):
                                part["attendance"] = new_att
                                break
                        await self.refresh(interaction)
                    except Exception as e:
                        log.error(f"[Attendance] Section callback failure: {e}\n{traceback.format_exc()}")
                        try:
                            await interaction.followup.send(t('ERR_WIZARD_GENERAL', guild_id=self.guild_id).replace('{e}', str(e)), ephemeral=True)
                        except Exception:
                            pass
                return callback
                
            toggle_btn.callback = create_callback(uid, att, idx)
            section = ui.Section(f"**{idx}. {user_name}**", accessory=toggle_btn)
            container_items.append(section)

        # 3. Navigation Buttons
        if total_pages > 1:
            container_items.append(ui.Separator())
            prev_btn = make_button(label=emojis.BACK, style=discord.ButtonStyle.gray, disabled=(self.page == 0), custom_id=f"att_pre_{self.page}")
            next_btn = make_button(label=emojis.FORWARD, style=discord.ButtonStyle.gray, disabled=(self.page >= total_pages - 1), custom_id=f"att_nxt_{self.page}")
            
            async def prev_cb(it: discord.Interaction):
                try:
                    await it.response.defer()
                except Exception:
                    pass
                log.info("[Attendance Debug] NAV: Prev")
                self.page -= 1
                await self.refresh(it)
                
            async def next_cb(it: discord.Interaction):
                try:
                    await it.response.defer()
                except Exception:
                    pass
                log.info("[Attendance Debug] NAV: Next")
                self.page += 1
                await self.refresh(it)
                
            prev_btn.callback = prev_cb
            next_btn.callback = next_cb
            container_items.append(ui.ActionRow(prev_btn, next_btn))

        main_container = ui.Container(*container_items, accent_color=0x40C4FF)
        self.add_item(main_container)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        log.error(f"[Attendance] View Error on {item}: {error}\n{traceback.format_exc()}")
        try: 
            msg = t('ERR_WIZARD_GENERAL', guild_id=self.guild_id).replace('{e}', str(error))
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            pass

    async def refresh(self, interaction: discord.Interaction) -> None:
        new_view = AttendanceView(self.bot, self.event_id, self.participants, self.guild_id, self.event_title)
        new_view.page = self.page
        new_view.name_cache = self.name_cache
        await new_view.build()
        
        log.info("[Attendance Debug] REFRESH: Updating message with new view state")
        if interaction.response.is_done():
            await interaction.edit_original_response(content=None, embeds=[], view=new_view)
        else:
            await interaction.response.edit_message(content=None, embeds=[], view=new_view)
