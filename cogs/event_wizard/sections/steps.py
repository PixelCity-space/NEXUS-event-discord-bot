import discord
from discord import ui
from utils.emojis import ERROR
from utils.i18n import t
from utils.logger import log
from utils.emoji_utils import split_emoji, make_button
from ..modals import (
    SingleEventModal,
    Step1Modal,
    SingleEventSupplementaryModal,
    Step2Modal,
    Step3Modal,
)

def create_step2_button(view) -> ui.Button:
    """Creates the Step 2 button (used in navigation or recurrence section)."""
    async def s2_cb(it: discord.Interaction):
        if view.wizard_type in ("single", "lobby"):
            await it.response.send_modal(SingleEventSupplementaryModal(view))
        else:
            await it.response.send_modal(Step2Modal(view))

    if view.wizard_type == "lobby":
        s2_label = t("BTN_STEP_2_LOBBY", guild_id=view.guild_id)
    elif view.wizard_type == "single":
        s2_label = t("BTN_STEP_2_SINGLE", guild_id=view.guild_id)
    else:
        s2_label = t("BTN_STEP_2_SERIES", guild_id=view.guild_id)

    step2 = make_button(label=s2_label, style=discord.ButtonStyle.gray)
    step2.callback = s2_cb
    return step2

def build_steps_row(view) -> ui.ActionRow:
    """Builds the main navigation row with steps and category toggle buttons."""
    # Step 1 Button
    async def s1_cb(it: discord.Interaction):
        try:
            log.info(f"[Wizard] s1_cb called. wizard_type={view.wizard_type}, guild_id={view.guild_id}")
            if view.wizard_type == "series":
                modal = Step1Modal(view)
            else:
                modal = SingleEventModal(view)
            await it.response.send_modal(modal)
        except Exception as e:
            log.error(f"[Wizard] s1_cb error: {e}", exc_info=True)
            if not it.response.is_done():
                await it.response.send_message(f"{ERROR} {e}", ephemeral=True)

    step1 = make_button(label=t("BTN_STEP_1", guild_id=view.guild_id), style=discord.ButtonStyle.gray)
    step1.callback = s1_cb

    # Step 2 Button
    step2 = create_step2_button(view)

    # Step 3 Button (Series only)
    step3 = None
    if view.wizard_type == "series":
        async def s3_cb(it: discord.Interaction):
            await it.response.send_modal(Step3Modal(view))
        step3 = make_button(label=t("BTN_STEP_3_SERIES", guild_id=view.guild_id), style=discord.ButtonStyle.gray)
        step3.callback = s3_cb

    # Advanced Category Toggle
    arrow_adv = " \u25BC" if view.show_advanced else " \u25C0"
    adv_btn = make_button(
        label=f"{t('BTN_ADVANCED', guild_id=view.guild_id)}{arrow_adv}",
        style=discord.ButtonStyle.secondary
    )
    async def adv_cb(it: discord.Interaction):
        await it.response.defer()
        view.show_advanced = not view.show_advanced
        if view.show_advanced:
            view.show_reminder = False
            view.show_recurrence = False
        await view.refresh_message(it)
    adv_btn.callback = adv_cb

    # Reminder Category Toggle
    rem_em, rem_lb = split_emoji(t("BTN_REMINDER_TOGGLE", guild_id=view.guild_id))
    arrow_rem = " \u25BC" if view.show_reminder else " \u25C0"
    rem_toggle_btn = make_button(
        label=f"{rem_lb}{arrow_rem}",
        emoji=rem_em,
        style=discord.ButtonStyle.secondary
    )
    async def rem_toggle_cb(it: discord.Interaction):
        await it.response.defer()
        view.show_reminder = not view.show_reminder
        if view.show_reminder:
            view.show_advanced = False
            view.show_recurrence = False
        await view.refresh_message(it)
    rem_toggle_btn.callback = rem_toggle_cb

    # Recurrence Category Toggle (Series only)
    rec_toggle_btn = None
    if view.wizard_type == "series":
        arrow_rec = " \u25BC" if view.show_recurrence else " \u25C0"
        rec_toggle_btn = make_button(
            label=f"{t('BTN_RECURRENCE_TOGGLE', guild_id=view.guild_id)}{arrow_rec}",
            style=discord.ButtonStyle.secondary
        )
        async def rec_toggle_cb(it: discord.Interaction):
            await it.response.defer()
            view.show_recurrence = not view.show_recurrence
            if view.show_recurrence:
                view.show_advanced = False
                view.show_reminder = False
            await view.refresh_message(it)
        rec_toggle_btn.callback = rec_toggle_cb

    if view.wizard_type in ("single", "lobby"):
        return ui.ActionRow(step1, step2, adv_btn, rem_toggle_btn)
    else:
        return ui.ActionRow(step1, rec_toggle_btn, step3, adv_btn, rem_toggle_btn)
