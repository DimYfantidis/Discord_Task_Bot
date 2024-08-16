# This example requires the 'message_content' intent.
import os
import sys
import discord
import dotenv
import pickle
import emoji
import asyncio
import getpass

from discord.message import Message
from discord.ext.commands import Bot
from discord.ext.commands.context import Context
from typing import Literal
from typing import Any
from hashlib import sha256


# Obscures confidential data by hashing them.
# Useful for protecting guild IDs and user IDs.
def obscure(obj: Any) -> str:
    return sha256(str(obj).encode("utf-8")).hexdigest()


dotenv.load_dotenv("variables.env")
MAX_NUMBER_OF_TASKS = int(os.getenv("MAX_NUMBER_OF_TASKS"))

intents = discord.Intents.default()
intents.message_content = True

bot = Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    await bot.tree.sync()
    print(f'We have been synchronised with Discord')


# Task status codes, based on the /task command
CANCELLED, ADDED, FINISHED = -1, 0, 1


# Used for retrieving user data from the simple database by performing a
# lookup operation on the given guild's address and the user's address.
# An "address" in the aforementioned context is derived from hashing the
# guild ID or the user ID using SHA-256. This way, the IDs cannot be
# determined by looking at the database, protecting the user's identity.
def get_path_variables(ctx: Context) -> tuple[str, str, str]:
    guild_dir = f"./guilds/{obscure(ctx.guild.id)}"
    filename = f"{obscure(ctx.message.author.id)}.tasks"
    filepath = f"{guild_dir}/{filename}"
    return guild_dir, filename, filepath


@bot.hybrid_command()
async def task(ctx: Context, action: Literal["add", "finished", "cancel"], description: str):
    guild_dir, filename, filepath = get_path_variables(ctx)
    if not os.path.exists(guild_dir):
        os.mkdir(guild_dir)
    if not os.path.exists(filepath):
        with open(filepath, "wb") as fp:
            pickle.dump([], fp)

    # Handles the entry of a new task
    if action == "add":
        with open(filepath, "rb") as fp:
            user_tasks: list[list[int | str]] = pickle.load(fp)
        if len(user_tasks) >= MAX_NUMBER_OF_TASKS:
            await ctx.send(
                f"Hey {ctx.message.author.mention}, how about you get your ass \
                to complete some of your previous tasks before registering new ones?\n\
                To see your current tasks type `/tasks` in the chat."
            )
        user_tasks.append([ADDED, description])
        with open(filepath, "wb") as fp:
            pickle.dump(user_tasks, fp)
        await ctx.send(
            f"Successfully added new task for **{ctx.message.author.name}** {emoji.emojize('💪')}\n"
            f"> **#{len(user_tasks)}:** {description}"
        )
    # Handles the completion or cancellation of a task
    elif action == "finished" or action == "cancel":
        if action[0] == 'f':
            # Case 1: Task Completion
            action_code = FINISHED
            action_message = f"Successfully finished task {emoji.emojize('💪')}"
        else:
            # Case 2: Task Cancellation
            action_code = CANCELLED
            action_message = f"Task {description} has been cancelled {emoji.emojize('😴💤')}"

        with open(filepath, "rb") as fp:
            # Loads the user's task history
            user_tasks: list[list[int | str]] = pickle.load(fp)

        try:
            # Converts ace-based indexing to zero-based
            index = int(description) - 1
        except ValueError as e:
            print(e)
            # Prompts user for correct command usage in case of error
            await ctx.send(
                f"When marking a task as finished or cancelled, give me its index in the `description` field"
            )
            return
        # Change task status field
        user_tasks[index][0] = action_code
        with open(filepath, "wb") as fp:
            # Save the new to-do list
            pickle.dump(user_tasks, fp)
        await ctx.send(action_message)
    else:
        await ctx.send(f"Invalid use of `/task` command. Try again {emoji.emojize('☕')}")


STATUS_EMOJIS = {
    CANCELLED: emoji.emojize("⛔ "),
    ADDED: emoji.emojize("🎯 "),
    FINISHED: emoji.emojize("✅ ")
}


@bot.hybrid_command()
async def view(ctx: Context):
    guild_dir, filename, filepath = get_path_variables(ctx)
    if not os.path.exists(guild_dir):
        await ctx.send(f"There are no registered tasks for {ctx.message.author.mention}")
        return
    if not os.path.exists(filepath):
        await ctx.send(f"There are no registered tasks for {ctx.message.author.mention}")
        return

    with open(filepath, "rb") as fp:
        user_tasks: list[list[bool | str]] = pickle.load(fp)
    message = ""
    for i, t in enumerate(user_tasks):
        message += str(i + 1) + ". "
        message += STATUS_EMOJIS[t[0]]
        message += t[1]
        message += "\n"
    await ctx.send(message)


@bot.hybrid_command()
async def clear(ctx: Context, which: Literal["finished", "cancelled", "all"]):
    guild_dir, filename, filepath = get_path_variables(ctx)
    if not os.path.exists(guild_dir):
        await ctx.send(f"There are no registered tasks for {ctx.message.author.mention}")
        return
    if not os.path.exists(filepath):
        await ctx.send(f"There are no registered tasks for {ctx.message.author.mention}")
        return

    if which == "all":
        await ctx.send("Are you sure you want to delete all of your tasks? (Y/n)")

        def check(m: Message):  # checking if it's the same user and channel
            return m.author == ctx.author and m.channel == ctx.channel

        try:  # waiting for message
            response = await bot.wait_for('message', check=check, timeout=30.0)  # timeout in seconds
        except asyncio.TimeoutError:  # returning after timeout
            return

        if response.content == "Y":
            os.remove(filepath)
            await ctx.send(f"Cleared all of {ctx.message.author.mention}'s tasks {emoji.emojize('🧹')}")
        else:
            await ctx.send(
                f"**{ctx.message.author.name}**'s tasks have not been removed: Action aborted {emoji.emojize('🚬')}"
            )
        return

    with open(filepath, "rb") as fp:
        user_tasks: list[list[bool | str]] = pickle.load(fp)
    which = CANCELLED if which == "cancelled" else which
    which = FINISHED if which == "finished" else which

    updated_user_tasks = [t for t in user_tasks if t[0] != which]
    if len(updated_user_tasks) == 0:
        os.remove(filepath)
    else:
        with open(filepath, "wb") as fp:
            pickle.dump(updated_user_tasks, fp)
    await ctx.send(f"Cleared selected {ctx.message.author.mention}'s tasks {emoji.emojize('🧹')}")


@bot.command
async def ping(ctx: Context):
    await ctx.send(f"pong {round(bot.latency * 1000)}ms\n")


if __name__ == '__main__':
    if "DEBUG_MODE" in sys.argv:
        print(
            "If you are running this application from a CLI environment (bash, cmd, powershell etc.), "
            "consider executing again with DEBUG_MODE disabled for safety reasons.", file=sys.stderr, flush=True
        )
        # Wait for STDERR's file descriptor to be completely drained to avoid ugly non-deterministic output
        os.fsync(sys.stderr.fileno())
        dbg_tok = input("TYPE \"TaskManager\"'s AUTHENTICATION TOKEN:\n>>> ")
        bot.run(dbg_tok)
    else:
        bot.run(
            token=getpass.getpass("TYPE \"TaskManager\"'s AUTHENTICATION TOKEN:\n>>> ")
        )
