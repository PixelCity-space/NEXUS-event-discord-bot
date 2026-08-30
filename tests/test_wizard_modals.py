import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from cogs.event_wizard.modals import (
    SingleEventModal,
    Step1Modal,
    SingleEventSupplementaryModal,
    Step2Modal,
    Step3Modal,
    AdvancedSettingsModal,
    RoleLimitsModal,
    RsvpRolesModal,
    NotificationSettingsModal,
    ReminderMessagesModal,
    ReminderOffsetModal,
    CreatorModal,
    ColorModal,
)

@pytest.fixture
def mock_view():
    view = MagicMock()
    view.guild_id = 12345
    view.wizard_type = "single"
    view.data = {
        "start_str": "2026-12-01 20:00",
        "reminder_offsets": ["1h", "30m"],
    }
    view.steps_completed = {}
    view.save_to_draft = AsyncMock()
    view.refresh_message = AsyncMock()
    return view

@pytest.fixture
def mock_interaction():
    inter = MagicMock(spec=discord.Interaction)
    inter.guild_id = 12345
    inter.response = MagicMock()
    inter.response.defer = AsyncMock()
    inter.response.send_message = AsyncMock()
    return inter

@pytest.mark.asyncio
async def test_single_event_modal(mock_view, mock_interaction):
    modal = SingleEventModal(mock_view)
    modal.title_input._value = "Epic Raid"
    modal.desc_input._value = "Raid description"
    modal.start_input._value = "2026-11-20 20:00"
    modal.end_input._value = "2026-11-20 23:00"
    modal.images_input._value = "https://example.com/raid.png"

    await modal.on_submit(mock_interaction)
    assert mock_view.data["title"] == "Epic Raid"
    assert mock_view.data["start_str"] == "2026-11-20 20:00"
    mock_view.save_to_draft.assert_called_once()
    mock_view.refresh_message.assert_called_once()

@pytest.mark.asyncio
async def test_single_event_modal_lobby(mock_view, mock_interaction):
    mock_view.wizard_type = "lobby"
    modal = SingleEventModal(mock_view)
    modal.title_input._value = "Fast Match"
    modal.max_acc_input._value = "5"

    await modal.on_submit(mock_interaction)
    assert mock_view.data["title"] == "Fast Match"
    assert mock_view.data["max_accepted"] == 5

@pytest.mark.asyncio
async def test_step1_modal_series(mock_view, mock_interaction):
    mock_view.wizard_type = "series"
    modal = Step1Modal(mock_view)
    modal.title_input._value = "Weekly Dungeon Series"
    modal.desc_input._value = "Series desc"
    modal.start_input._value = "2026-11-20 20:00"

    await modal.on_submit(mock_interaction)
    assert mock_view.data["title"] == "Weekly Dungeon Series"

@pytest.mark.asyncio
async def test_timing_and_step_modals(mock_view, mock_interaction):
    # 1. SingleEventSupplementaryModal
    supp = SingleEventSupplementaryModal(mock_view)
    supp.max_acc_input._value = "10"
    supp.timezone_input._value = "UTC"
    supp.ping_input._value = "<@&33333>"
    await supp.on_submit(mock_interaction)
    assert mock_view.data["max_accepted"] == 10
    assert mock_view.data["timezone"] == "UTC"

    # 2. Step2Modal (recurrence)
    s2 = Step2Modal(mock_view)
    s2.limit_input._value = "5"
    await s2.on_submit(mock_interaction)
    assert mock_view.data["recurrence_limit"] == 5

    # 3. Step3Modal
    s3 = Step3Modal(mock_view)
    s3.max_acc_input._value = "8"
    s3.ping_input._value = "<@&44444>"
    await s3.on_submit(mock_interaction)
    assert mock_view.data["max_accepted"] == 8

@pytest.mark.asyncio
async def test_settings_modals(mock_view, mock_interaction):
    # 1. AdvancedSettingsModal
    asm = AdvancedSettingsModal(mock_view)
    asm.wait_limit_input._value = "15"
    await asm.on_submit(mock_interaction)
    assert '"waiting_list_limit": 15' in mock_view.data["extra_data"]

    # 2. RoleLimitsModal
    active_set = {
        "options": [{"id": "tank", "label": "Tank"}, {"id": "healer", "label": "Healer"}]
    }
    rlm = RoleLimitsModal(mock_view, active_set)
    rlm.limits_input._value = "tank: 2\nhealer: 3"
    await rlm.on_submit(mock_interaction)
    assert '"role_limits": {"tank": 2, "healer": 3}' in mock_view.data["extra_data"]

    # 3. RsvpRolesModal
    rrm = RsvpRolesModal(mock_view)
    rrm.roles_input._value = "11111, 22222"
    await rrm.on_submit(mock_interaction)
    assert "11111,22222" in mock_view.data["rsvp_allowed_role_ids"]

@pytest.mark.asyncio
async def test_notification_and_quick_modals(mock_view, mock_interaction):
    # 1. NotificationSettingsModal
    nsm = NotificationSettingsModal(mock_view)
    nsm.promo_input._value = "Promo msg"
    await nsm.on_submit(mock_interaction)
    assert "Promo msg" in str(mock_view.data.get("extra_data"))

    # 2. ReminderMessagesModal
    rmm = ReminderMessagesModal(mock_view)
    for inp in rmm.inputs:
        inp._value = "Reminder text"
    await rmm.on_submit(mock_interaction)
    assert len(mock_view.data["reminder_messages"]) == 2

    # 3. ReminderOffsetModal
    rom = ReminderOffsetModal(mock_view)
    rom.inp._value = "1h, ping, coming\n30m, dm, coming"
    await rom.on_submit(mock_interaction)
    assert len(mock_view.data["reminder_offsets"]) == 2

    # 4. CreatorModal
    cm = CreatorModal(mock_view)
    cm.inp._value = "123456"
    await cm.on_submit(mock_interaction)
    assert mock_view.data["creator_id"] == "123456"

    # 5. ColorModal
    clm = ColorModal(mock_view, current_color="0x40C4FF")
    clm.inp._value = "0xE03B42"
    await clm.on_submit(mock_interaction)
    assert mock_view.data["color"] == "0xE03B42"
