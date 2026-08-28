from discord import ui
from utils.i18n import t

def build_header_section(view) -> list[ui.Item]:
    """Builds the title, subtitles, channel warning, and steps completion status."""
    title_text = f"### {t('WIZARD_TITLE', guild_id=view.guild_id)}"
    if view.wizard_type == "lobby":
        title_text += f"\n{t('WIZARD_LOBBY_SUBTITLE', guild_id=view.guild_id)}"
    if view.bulk_ids:
        title_text += f" {t('LBL_BULK_EDIT', guild_id=view.guild_id)}"

    status_text = view.get_status_text()
    if view.chan_warning:
        desc_text = f"{view.chan_warning}\n{t('WIZARD_DESC', guild_id=view.guild_id, status=status_text)}"
    else:
        desc_text = t("WIZARD_DESC", guild_id=view.guild_id, status=status_text)

    return [
        ui.TextDisplay(title_text),
        ui.Separator(),
        ui.TextDisplay(desc_text),
        ui.Separator()
    ]
