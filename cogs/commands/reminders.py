import asyncio
import logging
import re
from datetime import datetime, timedelta

import dateparser
from discord.ext import commands
from discord.ext.commands import Bot, Context, clean_content
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy_utils import ScalarListException

from config import CONFIG
from models import Reminder, User, db_session
from utils import get_name_string
from utils.utils import user_is_irc_bot

LONG_HELP_TEXT = """
Add reminders for yourself or remove the last one you added.
"""
SHORT_HELP_TEXT = """Add or remove reminders."""


def parse_time(time):
    # dateparser.parse returns None if it cannot parse
    parsed_time = dateparser.parse(time)

    now = datetime.now()

    try:
        parsed_time = datetime.strptime(time, "%Y-%m-%d %H:%M")
    except ValueError:
        pass

    if not parsed_time:
        try:
            parsed_time = datetime.strptime(time, "%m-%d %H:%M")
            parsed_time = parsed_time.replace(year=now.year)
            if parsed_time < now:
                parsed_time = parsed_time.replace(year=now.year + 1)
        except ValueError:
            pass

    if not parsed_time:
        try:
            parsed_time = datetime.strptime(time, "%H:%M:%S")
            parsed_time = parsed_time.replace(
                year=now.year, month=now.month, day=now.day
            )
            if parsed_time < now:
                parsed_time = parsed_time + timedelta(days=1)

        except ValueError:
            pass

    if not parsed_time:
        try:
            parsed_time = datetime.strptime(time, "%H:%M")
            parsed_time = parsed_time.replace(
                year=now.year, month=now.month, day=now.day
            )
            if parsed_time < now:
                parsed_time = parsed_time + timedelta(days=1)
        except ValueError:
            pass

    if not parsed_time:
        result = re.match(r"(\d+d)?\s*(\d+h)?\s*(\d+m)?\s*(\d+s)?(?!^)$", time)
        if result:
            parsed_time = now
            if result.group(1):
                parsed_time = parsed_time + timedelta(days=int(result.group(1)[:-1]))
            if result.group(2):
                parsed_time = parsed_time + timedelta(hours=int(result.group(2)[:-1]))
            if result.group(3):
                parsed_time = parsed_time + timedelta(minutes=int(result.group(3)[:-1]))
            if result.group(4):
                parsed_time = parsed_time + timedelta(seconds=int(result.group(4)[:-1]))

    return parsed_time


async def reminder_check(bot):
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now()
        # I have this useless variable because its not pep8 if you compare directly to False lol
        not_triggered = False
        reminders = (
            db_session.query(Reminder)
            .filter(Reminder.trigger_at <= now, Reminder.triggered == not_triggered)
            .all()
        )
        for r in reminders:
            if r.irc_name:
                display_name = r.irc_name
            else:
                author_uid = (
                    db_session.query(User).filter(User.id == r.user_id).first().user_uid
                )
                display_name = f"<@{author_uid}>"
            channel = bot.get_channel(r.playback_channel_id)
            message = f"Reminding {display_name}: " + r.reminder_content
            await channel.send(message)
            r.triggered = True
            db_session.commit()

        await asyncio.sleep(CONFIG.REMINDER_SEARCH_INTERVAL)


class Reminders(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.bot.loop.create_task(reminder_check(self.bot))

    @commands.group(help=LONG_HELP_TEXT, brief=SHORT_HELP_TEXT)
    async def reminder(self, ctx: Context):
        if not ctx.invoked_subcommand:
            await ctx.send("Subcommand not found.")

    @reminder.command(
        help='Add a reminder, format "yyyy-mm-dd hh:mm" or "mm-dd hh:mm" or hh:mm:ss or hh:mm or xdxhxmxs or any ordered combination of the last format, then finally your reminder (rest of discord message).'
    )
    async def add(self, ctx: Context, *args: clean_content):
        if not args:
            await ctx.send("You're missing a time and a message!")
        else:
            trigger_time = parse_time(args[0])
            now = datetime.now()
            if not trigger_time:
                await ctx.send("Incorrect time format, please see help text.")
            elif trigger_time < now:
                await ctx.send("That time is in the past.")
            else:
                # HURRAY the time is valid and not in the past, add the reminder
                display_name = get_name_string(ctx.message)

                # set the id to a random value if the author was the bridge bot, since we wont be using it anyways
                # if ctx.message.clean_content.startswith("**<"): <---- FOR TESTING
                if user_is_irc_bot(ctx):
                    author_id = 1
                    irc_n = display_name
                else:
                    author_id = (
                        db_session.query(User)
                        .filter(User.user_uid == ctx.author.id)
                        .first()
                        .id
                    )
                    irc_n = None

                if len(args) > 1:
                    rem_content = " ".join(args[1:])
                    trig_at = trigger_time
                    trig = False
                    playback_ch_id = ctx.message.channel.id
                    new_reminder = Reminder(
                        user_id=author_id,
                        reminder_content=rem_content,
                        trigger_at=trig_at,
                        triggered=trig,
                        playback_channel_id=playback_ch_id,
                        irc_name=irc_n,
                    )
                    db_session.add(new_reminder)
                    try:
                        db_session.commit()
                        await ctx.send(
                            f"Thanks {display_name}, I have saved your reminder (but please note that my granularity is set at {CONFIG.REMINDER_SEARCH_INTERVAL} seconds)."
                        )
                    except (ScalarListException, SQLAlchemyError) as e:
                        db_session.rollback()
                        logging.error(e)
                        await ctx.send(f"Something went wrong")
                else:
                    await ctx.send("Please include some reminder text!")


def setup(bot: Bot):
    bot.add_cog(Reminders(bot))
