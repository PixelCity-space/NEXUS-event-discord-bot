import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from cogs.server_setup.config_schema import (
    validate_positive_int,
    validate_hex_color,
    validate_offset_list,
    validate_non_empty,
    ServerSettings,
)
from cogs.server_setup.modals import ValidatedConfigModal
from cogs.server_setup.views.main_menu import ServerSetupView
from cogs.server_setup.views.general import GeneralSetupView
from cogs.server_setup.views.reminders import ReminderSetupView
from cogs.server_setup.views.event_defaults import EventDefaultsView
from cogs.server_setup.ui_builder import (
    create_setting_modal_button,
    create_setting_toggle_button,
    create_color_dropdown,
    create_setting_select,
)

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    return bot

@pytest.fixture
def mock_interaction(mock_bot):
    inter = MagicMock(spec=discord.Interaction)
    inter.client = mock_bot
    inter.guild_id = 12345
    inter.response = MagicMock()
    inter.response.defer = AsyncMock()
    inter.response.send_modal = AsyncMock()
    inter.response.send_message = AsyncMock()
    inter.response.edit_message = AsyncMock()
    inter.followup = MagicMock()
    inter.followup.send = AsyncMock()
    return inter

def test_config_schema_validators():
    # 1. validate_positive_int
    assert validate_positive_int("10")[0] is True
    assert validate_positive_int("0")[0] is True
    assert validate_positive_int("-5")[0] is False
    assert validate_positive_int("abc")[0] is False

    # 2. validate_hex_color
    assert validate_hex_color("0x40C4FF")[0] is True
    assert validate_hex_color("#1FAD5E")[0] is True
    assert validate_hex_color("invalid")[0] is False

    # 3. validate_offset_list
    assert validate_offset_list("15m\n1h, ping, coming")[0] is True
    assert validate_offset_list("")[0] is True
    assert validate_offset_list("invalid_offset")[0] is False

    # 4. validate_non_empty
    assert validate_non_empty("UTC")[0] is True
    assert validate_non_empty("   ")[0] is False

    # 5. ServerSettings.get_by_key
    assert ServerSettings.get_by_key("timezone") == ServerSettings.TIMEZONE
    assert ServerSettings.get_by_key("nonexistent") is None

@pytest.mark.asyncio
async def test_validated_config_modal(mock_interaction):
    modal = ValidatedConfigModal(
        guild_id=12345,
        setting=ServerSettings.TIMEZONE,
        label_text="Timezone",
        default_val="UTC"
    )
    modal.input_field._value = "Europe/Budapest"

    with patch("database.save_guild_setting", new_callable=AsyncMock) as mock_save:
        await modal.on_submit(mock_interaction)
        mock_save.assert_called_once_with(12345, "timezone", "Europe/Budapest")

@pytest.mark.asyncio
async def test_server_setup_views(mock_bot, mock_interaction):
    with patch("database.get_all_guild_settings", new_callable=AsyncMock) as mock_settings, \
         patch("database.get_guild_setting", new_callable=AsyncMock) as mock_setting, \
         patch("database.get_guild_translations", new_callable=AsyncMock) as mock_trans:

        mock_settings.return_value = {"timezone": "UTC", "language": "hu", "default_color": "0x40C4FF"}
        mock_setting.return_value = "UTC"
        mock_trans.return_value = {}

        # 1. ServerSetupView
        main_view = ServerSetupView(mock_bot, guild_id=12345)
        await main_view.prepare(mock_interaction)
        assert len(main_view.children) > 0

        # 2. GeneralSetupView
        gen_view = GeneralSetupView(mock_bot, guild_id=12345)
        await gen_view.prepare(mock_interaction)
        assert len(gen_view.children) > 0

        # 3. ReminderSetupView
        rem_view = ReminderSetupView(mock_bot, guild_id=12345)
        await rem_view.prepare(mock_interaction)
        assert len(rem_view.children) > 0

        # 4. EventDefaultsView
        def_view = EventDefaultsView(mock_bot, guild_id=12345)
        await def_view.prepare(mock_interaction)
        assert len(def_view.children) > 0

@pytest.mark.asyncio
async def test_ui_builders():
    mock_parent = MagicMock()
    mock_parent.guild_id = 12345
    mock_parent.refresh_message = AsyncMock()

    # 1. create_setting_modal_button
    btn = create_setting_modal_button(
        parent_view=mock_parent,
        setting=ServerSettings.TIMEZONE,
        label="Set Timezone",
        modal_label="Timezone"
    )
    assert btn is not None

    # 2. create_setting_toggle_button
    toggle = create_setting_toggle_button(
        parent_view=mock_parent,
        setting=ServerSettings.DEFAULT_USE_WAITING_LIST,
        current_value="true",
        label_format="Waiting list: {state}",
        on_text="ON",
        off_text="OFF"
    )
    assert toggle is not None

    # 3. create_color_dropdown
    color_sel = create_color_dropdown(parent_view=mock_parent, current_color_raw="0x40C4FF")
    assert color_sel is not None

    # 4. create_setting_select
    sel = create_setting_select(
        parent_view=mock_parent,
        setting=ServerSettings.LANGUAGE,
        options=[discord.SelectOption(label="English", value="en")],
        placeholder="Select Language"
    )
    assert sel is not None
