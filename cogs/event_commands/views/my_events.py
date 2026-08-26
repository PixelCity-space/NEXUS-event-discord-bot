import discord
from discord import ui
from utils import emojis
from utils.i18n import t
from utils.emoji_utils import make_button

class MyEventsView(ui.LayoutView):
    """View displaying paginated list of user's active/organized events."""
    
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
        
        # Header
        container_items.append(ui.TextDisplay(f"### {t('LBL_MY_EVENTS_TITLE', guild_id=self.guild_id)}"))
        container_items.append(ui.Separator())

        for i, ev in enumerate(event_slice):
            title = ev["title"] or t("LBL_UNNAMED_EVENT", guild_id=self.guild_id)
            st = ev["start_time"]
            eid = ev["event_id"]
            cid = ev["channel_id"]
            mid = ev["message_id"]
            creator_id = ev["creator_id"]
            status_raw = ev["user_status"]
            
            # Formatted timing and organizer indicator
            time_rel = f"<t:{int(st)}:R>" if st else t("LBL_LOBBY_LIST_NO_START", guild_id=self.guild_id)
            lbl_id = t("LBL_ID", guild_id=self.guild_id)
            
            if int(creator_id) == self.user_id:
                state_text = f"{emojis.CROWN} **{t('LBL_ORGANIZER', guild_id=self.guild_id)}**"
            else:
                state_text = f"{emojis.SPARKLES} {str(status_raw).capitalize()}"
                
            status_lbl = t("LBL_STATUS", guild_id=self.guild_id) or "Status"
            container_items.append(ui.TextDisplay(
                f"{emojis.CALENDAR} **{title}**\n{lbl_id}: `{eid}` | {time_rel}\n**{status_lbl}:** {state_text}"
            ))
            
            # Jump link button
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
