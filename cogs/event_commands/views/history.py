import discord
from discord import ui
from utils import emojis
from utils.i18n import t
from utils.emoji_utils import make_button

class EventHistoryView(ui.LayoutView):
    """View displaying paginated list of user's past event participation and attendance records."""
    
    def __init__(self, bot, guild_id: int, user_id: int, events: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.events = events
        self.page = 0
        self.per_page = 3

    async def build(self):
        self.clear_items()
        
        start = self.page * self.per_page
        end = start + self.per_page
        event_slice = self.events[start:end]
        
        container_items = []
        
        container_items.append(ui.TextDisplay(f"### {t('LBL_HISTORY_TITLE', guild_id=self.guild_id)}"))
        container_items.append(ui.Separator())

        for i, ev in enumerate(event_slice):
            title = ev["title"] or t("LBL_UNNAMED_EVENT", guild_id=self.guild_id)
            st = ev["start_time"]
            eid = ev["event_id"]
            cid = ev["channel_id"]
            mid = ev["message_id"]
            creator_id = ev["creator_id"]
            status_raw = ev["user_status"]
            attendance = ev["attendance"]
            
            is_creator = int(creator_id) == self.user_id
            
            time_str = f"<t:{int(st)}:d> (<t:{int(st)}:R>)" if st else t("LBL_PAST_EVENT", guild_id=self.guild_id)
            title_prefix = emojis.CROWN if is_creator else emojis.CALENDAR
            
            if is_creator:
                res_text = f"{emojis.CROWN} {t('LBL_ORGANIZER', guild_id=self.guild_id)}"
            else:
                if attendance == "present":
                    res_text = f"{emojis.SUCCESS} {t('LBL_PRESENT', guild_id=self.guild_id)}"
                elif attendance == "no_show":
                    res_text = f"{emojis.ERROR} {t('LBL_NOSHOW', guild_id=self.guild_id)}"
                else:
                    res_text = f"{emojis.SPARKLES} {str(status_raw).capitalize()}"
                
            res_lbl = t("LBL_RESULT", guild_id=self.guild_id) or "Result"
            container_items.append(ui.TextDisplay(
                f"{title_prefix} **{title}**\n{time_str}\n**{res_lbl}:** {res_text}"
            ))
            
            link = f"https://discord.com/channels/{self.guild_id}/{cid}/{mid}"
            container_items.append(ui.ActionRow(make_button(
                label=t("BTN_GO_TO_EVENT", guild_id=self.guild_id) or "View",
                url=link,
                style=discord.ButtonStyle.link
            )))
            
            if i < len(event_slice) - 1:
                container_items.append(ui.Separator())

        # Pagination controls
        if len(self.events) > self.per_page:
            container_items.append(ui.Separator())
            prev_btn = make_button(label=emojis.BACK, style=discord.ButtonStyle.secondary, disabled=(self.page == 0))
            async def prev_cb(it: discord.Interaction):
                self.page -= 1
                await self.build()
                await it.response.edit_message(view=self)
            prev_btn.callback = prev_cb
            
            next_btn = make_button(label=emojis.FORWARD, style=discord.ButtonStyle.secondary, disabled=(end >= len(self.events)))
            async def next_cb(it: discord.Interaction):
                self.page += 1
                await self.build()
                await it.response.edit_message(view=self)
            next_btn.callback = next_cb
            
            container_items.append(ui.ActionRow(prev_btn, next_btn))

        self.add_item(ui.Container(*container_items, accent_color=0x40C4FF))
