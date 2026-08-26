import discord
from discord import ui
from utils.i18n import t
from utils.emoji_utils import make_select_option
from .steps import create_step2_button

def build_recurrence_section(view) -> list[ui.Item]:
    """Builds the recurrence settings accordion for recurring series."""
    if view.wizard_type != "series" or not view.show_recurrence:
        return []

    items: list[ui.Item] = [
        ui.Separator(),
        ui.TextDisplay(f"**{t('STATUS_STEP2_EMOJI', guild_id=view.guild_id)} {t('STATUS_STEP2_SERIES_LBL', guild_id=view.guild_id)}**"),
        ui.TextDisplay(t("LBL_CHOOSE_REC_TYPE", guild_id=view.guild_id)),
    ]

    # Recurrence Type Select
    sel_rec = ui.Select(placeholder=t("SEL_REC_TYPE", guild_id=view.guild_id), options=view.recurrence_options)
    async def rec_cb(it: discord.Interaction):
        view.data["recurrence_type"] = sel_rec.values[0]
        await view.save_to_draft()
        await view.refresh_message(it)
    sel_rec.callback = rec_cb
    items.append(ui.ActionRow(sel_rec))

    # Repost Trigger Select
    cur_trig = view.data.get("repost_trigger", "after_end")
    trig_opts = [
        make_select_option(label=t("SEL_TRIG_BEFORE", guild_id=view.guild_id), value="before_start", default=(cur_trig == "before_start")),
        make_select_option(label=t("SEL_TRIG_AFTER_START", guild_id=view.guild_id), value="after_start", default=(cur_trig == "after_start")),
        make_select_option(label=t("SEL_TRIG_AFTER_END", guild_id=view.guild_id), value="after_end", default=(cur_trig == "after_end")),
    ]
    sel_trig = ui.Select(placeholder=t("SEL_TRIG_TYPE", guild_id=view.guild_id), options=trig_opts)
    async def trig_cb(it: discord.Interaction):
        await it.response.defer()
        view.data["repost_trigger"] = sel_trig.values[0]
        await view.save_to_draft()
        await view.refresh_message(it)
    sel_trig.callback = trig_cb

    items.append(ui.TextDisplay(t("LBL_CHOOSE_REPOST_TIME", guild_id=view.guild_id)))
    items.append(ui.ActionRow(sel_trig))

    # Custom Days Select
    if view.data.get("recurrence_type") == "custom":
        cust_days = view.data.get("custom_days", [])
        day_opts = [
            discord.SelectOption(label=t("DAY_MON", guild_id=view.guild_id), value="monday", default=("monday" in cust_days)),
            discord.SelectOption(label=t("DAY_TUE", guild_id=view.guild_id), value="tuesday", default=("tuesday" in cust_days)),
            discord.SelectOption(label=t("DAY_WED", guild_id=view.guild_id), value="wednesday", default=("wednesday" in cust_days)),
            discord.SelectOption(label=t("DAY_THU", guild_id=view.guild_id), value="thursday", default=("thursday" in cust_days)),
            discord.SelectOption(label=t("DAY_FRI", guild_id=view.guild_id), value="friday", default=("friday" in cust_days)),
            discord.SelectOption(label=t("DAY_SAT", guild_id=view.guild_id), value="saturday", default=("saturday" in cust_days)),
            discord.SelectOption(label=t("DAY_SUN", guild_id=view.guild_id), value="sunday", default=("sunday" in cust_days))
        ]
        cust_sel = ui.Select(placeholder=t("SEL_CUSTOM_DAYS", guild_id=view.guild_id), options=day_opts, min_values=1, max_values=7)
        async def cust_cb(it: discord.Interaction):
            await it.response.defer()
            view.data["custom_days"] = cust_sel.values
            await view.save_to_draft()
            await view.refresh_message(it)
        cust_sel.callback = cust_cb
        items.append(ui.TextDisplay(t("LBL_CHOOSE_CUSTOM_DAYS", guild_id=view.guild_id)))
        items.append(ui.ActionRow(cust_sel))

    # Relative Recurrence Select
    elif view.data.get("recurrence_type") == "relative":
        rel_combo = view.data.get("relative_combo", [])
        rel_opts = [
            discord.SelectOption(label=t("REL_WEEK_1", guild_id=view.guild_id), value="wk_1", default=("wk_1" in rel_combo)),
            discord.SelectOption(label=t("REL_WEEK_2", guild_id=view.guild_id), value="wk_2", default=("wk_2" in rel_combo)),
            discord.SelectOption(label=t("REL_WEEK_3", guild_id=view.guild_id), value="wk_3", default=("wk_3" in rel_combo)),
            discord.SelectOption(label=t("REL_WEEK_4", guild_id=view.guild_id), value="wk_4", default=("wk_4" in rel_combo)),
            discord.SelectOption(label=t("REL_WEEK_LAST", guild_id=view.guild_id), value="wk_last", default=("wk_last" in rel_combo)),
            discord.SelectOption(label=t("DAY_MON", guild_id=view.guild_id), value="day_monday", default=("day_monday" in rel_combo)),
            discord.SelectOption(label=t("DAY_TUE", guild_id=view.guild_id), value="day_tuesday", default=("day_tuesday" in rel_combo)),
            discord.SelectOption(label=t("DAY_WED", guild_id=view.guild_id), value="day_wednesday", default=("day_wednesday" in rel_combo)),
            discord.SelectOption(label=t("DAY_THU", guild_id=view.guild_id), value="day_thursday", default=("day_thursday" in rel_combo)),
            discord.SelectOption(label=t("DAY_FRI", guild_id=view.guild_id), value="day_friday", default=("day_friday" in rel_combo)),
            discord.SelectOption(label=t("DAY_SAT", guild_id=view.guild_id), value="day_saturday", default=("day_saturday" in rel_combo)),
            discord.SelectOption(label=t("DAY_SUN", guild_id=view.guild_id), value="day_sunday", default=("day_sunday" in rel_combo))
        ]
        rel_sel = ui.Select(placeholder=t("SEL_REL_COMBO", guild_id=view.guild_id), options=rel_opts, min_values=1, max_values=2)
        async def rel_cb(it: discord.Interaction):
            await it.response.defer()
            view.data["relative_combo"] = rel_sel.values
            await view.save_to_draft()
            await view.refresh_message(it)
        rel_sel.callback = rel_cb
        items.append(ui.TextDisplay(t("LBL_CHOOSE_REL_COMBO", guild_id=view.guild_id)))
        items.append(ui.ActionRow(rel_sel))

    # Supplementary timing (Step 2) button
    step2 = create_step2_button(view)
    items.append(ui.ActionRow(step2))

    return items
