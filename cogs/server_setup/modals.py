import re
from typing import Union, Optional
import discord
from discord import ui
import database
from utils.i18n import t, load_guild_translations
from utils.logger import log
from .config_schema import SettingDefinition, ServerSettings

class ValidatedConfigModal(ui.Modal):
    """Schema-driven configuration modal with input validation and automatic cache invalidation."""
    
    def __init__(
        self,
        guild_id: int,
        setting: Union[SettingDefinition, str],
        label_text: str,
        placeholder: str = "",
        is_long: bool = False,
        default_val: str = "",
        parent_view: Optional[ui.View] = None
    ):
        super().__init__(title=t("MODAL_CONFIG_VALUE", guild_id=guild_id))
        self.guild_id = guild_id
        
        if isinstance(setting, SettingDefinition):
            self.setting = setting
            self.key = setting.key
        else:
            self.key = str(setting)
            self.setting = ServerSettings.get_by_key(self.key)
            
        self.parent_view = parent_view
        
        style = discord.TextStyle.paragraph if is_long else discord.TextStyle.short
        self.input_field = ui.TextInput(
            label=label_text[:45],
            placeholder=placeholder[:45],
            style=style,
            default=str(default_val) if default_val is not None else "",
            required=True
        )
        self.add_item(self.input_field)

    async def on_submit(self, interaction: discord.Interaction):
        val = str(self.input_field.value).strip()
        log.info(f"MODAL: Submitting key {self.key} with value '{val}' for Guild ID {self.guild_id}")
        
        try:
            # 1. Run validator if defined for this setting
            if self.setting and self.setting.validator:
                is_valid, err_msg = self.setting.validator(val)
                if not is_valid:
                    return await interaction.response.send_message(f"❌ {err_msg}", ephemeral=True)

            # 2. Persist to database
            await database.save_guild_setting(self.guild_id, self.key, val)
            
            # 3. Reload cache if key affects translations or admin authorization
            requires_reload = (self.setting.requires_reload if self.setting else False) or (self.key in ["language", "admin_role_ids", "admin_channel_ids"])
            if requires_reload:
                await load_guild_translations(self.guild_id)

            # 4. Refresh parent view if present
            if self.parent_view and hasattr(self.parent_view, "refresh_message"):
                await self.parent_view.refresh_message(interaction)
                await interaction.followup.send(
                    t("MSG_SETTING_SAVED", guild_id=self.guild_id, key=self.key, val=val[:100]), 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    t("MSG_SETTING_SAVED", guild_id=self.guild_id, key=self.key, val=val[:100]), 
                    ephemeral=True
                )
        except Exception as e:
            log.error(f"Error in modal submit for {self.key}: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    t('ERR_SETTING_SAVE_FAILED', guild_id=self.guild_id, e=str(e)),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    t('ERR_SETTING_SAVE_FAILED', guild_id=self.guild_id, e=str(e)),
                    ephemeral=True,
                )

class MultiReminderOffsetModal(ui.Modal):
    """Specialized modal for multi-line reminder offset configuration."""
    
    def __init__(self, guild_id: int, current_val: str, parent_view: Optional[ui.View] = None):
        super().__init__(title=t("MODAL_REMINDER_OFFSETS", guild_id=guild_id))
        self.guild_id = guild_id
        self.parent_view = parent_view
        self.inp = ui.TextInput(
            label=t("LBL_REMINDER_OFFSETS_PARAGRAPH", guild_id=guild_id)[:45],
            default=current_val or "15m",
            style=discord.TextStyle.paragraph,
            max_length=400,
            required=False,
        )
        self.add_item(self.inp)

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = str(self.inp.value).strip()
        if not raw_val:
            await database.save_guild_setting(self.guild_id, "default_reminder_offset", "")
            if self.parent_view and hasattr(self.parent_view, "refresh_message"):
                return await self.parent_view.refresh_message(interaction)
            return await interaction.response.send_message(
                t("MSG_SETTING_SAVED", guild_id=self.guild_id, key="default_reminder_offset", val=""),
                ephemeral=True
            )

        lines = [x.strip() for x in raw_val.splitlines() if x.strip()]
        
        # Regex validation for offset line formats (e.g. 15m, 1h, 1d)
        valid_pattern = re.compile(r"^(\d+)([mhd])(?:,([^,]*))?(?:,(.*))?$", re.IGNORECASE)
        for line in lines:
            if not valid_pattern.match(line):
                return await interaction.response.send_message(
                    t("ERR_INVALID_OFFSET_FORMAT", guild_id=self.guild_id),
                    ephemeral=True
                )
        
        # Save up to 5 lines as newline-separated string
        final_val = "\n".join(lines[:5])
        await database.save_guild_setting(self.guild_id, "default_reminder_offset", final_val)
        
        if self.parent_view and hasattr(self.parent_view, "refresh_message"):
            await self.parent_view.refresh_message(interaction)
            await interaction.followup.send(
                t("MSG_SETTING_SAVED", guild_id=self.guild_id, key="default_reminder_offset", val=final_val),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                t("MSG_SETTING_SAVED", guild_id=self.guild_id, key="default_reminder_offset", val=final_val),
                ephemeral=True
            )

# Backward compatibility alias
SimpleConfigModal = ValidatedConfigModal
