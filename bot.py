import os
import json
import random
import time
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ==============================
# CONFIG
# ==============================

TOKEN = os.getenv("DISCORD_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
GUILD_ID = os.getenv("GUILD_ID", "").strip()

CURRENCY_NAME = os.getenv("CURRENCY_NAME", "Gems")
CURRENCY_EMOJI = os.getenv("CURRENCY_EMOJI", "💎")

INVITE_REWARD = int(os.getenv("INVITE_REWARD", "125"))
DAILY_REWARD = int(os.getenv("DAILY_REWARD", "250"))

WORK_MIN = int(os.getenv("WORK_MIN", "50"))
WORK_MAX = int(os.getenv("WORK_MAX", "150"))

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID", "").strip()

if not TOKEN or not CLIENT_ID:
    raise RuntimeError(
        "DISCORD_TOKEN and CLIENT_ID are required in Environment Variables."
    )

# ==============================
# DATABASE
# ==============================

DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "database.json"

DATA_DIR.mkdir(exist_ok=True)

DEFAULT_DB = {
    "guilds": {}
}


def load_db():
    if not DATA_FILE.exists():
        DATA_FILE.write_text(
            json.dumps(DEFAULT_DB, indent=2),
            encoding="utf-8"
        )

    try:
        return json.loads(
            DATA_FILE.read_text(encoding="utf-8")
        )
    except Exception:
        return {"guilds": {}}


db = load_db()


def save_db():
    tmp = DATA_FILE.with_suffix(".tmp")

    tmp.write_text(
        json.dumps(db, indent=2),
        encoding="utf-8"
    )

    tmp.replace(DATA_FILE)


def guild_data(guild_id: int):
    gid = str(guild_id)

    if gid not in db["guilds"]:
        db["guilds"][gid] = {
            "users": {},
            "shop": {},
            "rewarded_members": [],
            "invite_uses": {}
        }

        save_db()

    return db["guilds"][gid]


def user_data(guild_id: int, user_id: int):
    guild = guild_data(guild_id)
    uid = str(user_id)

    if uid not in guild["users"]:
        guild["users"][uid] = {
            "balance": 0,
            "invites": 0,
            "daily": 0
        }

        save_db()

    return guild["users"][uid]


def balance(guild_id, user_id):
    return user_data(guild_id, user_id)["balance"]


def add_money(guild_id, user_id, amount):
    user = user_data(guild_id, user_id)

    user["balance"] = max(
        0,
        user["balance"] + amount
    )

    save_db()

    return user["balance"]


def money(amount):
    return (
        f"{CURRENCY_EMOJI} "
        f"**{amount:,}** "
        f"{CURRENCY_NAME}"
    )


# ==============================
# INVITE SYSTEM
# ==============================

invite_cache = {}


async def cache_guild_invites(guild: discord.Guild):
    try:
        invites = await guild.invites()

        uses = {
            invite.code: (invite.uses or 0)
            for invite in invites
        }

        invite_cache[guild.id] = uses

        guild_data(guild.id)["invite_uses"] = uses

        save_db()

    except discord.Forbidden:
        print(
            f"[WARN] No permission to view invites in {guild.name}"
        )

    except Exception as error:
        print(
            f"[WARN] Invite cache failed: {error}"
        )


async def identify_invite(guild: discord.Guild):
    try:
        invites = await guild.invites()

        old = invite_cache.get(
            guild.id,
            guild_data(guild.id).get(
                "invite_uses",
                {}
            )
        )

        used = None

        for invite in invites:
            before = old.get(
                invite.code,
                0
            )

            after = invite.uses or 0

            if after > before:
                used = invite
                break

        new_uses = {
            invite.code: (invite.uses or 0)
            for invite in invites
        }

        invite_cache[guild.id] = new_uses

        guild_data(guild.id)["invite_uses"] = new_uses

        save_db()

        return used

    except Exception as error:
        print(
            f"[WARN] Could not identify invite: {error}"
        )

        return None


# ==============================
# BOT
# ==============================

class EconomyBot(commands.Bot):

    def __init__(self):

        intents = discord.Intents.default()

        # Required for invite/member tracking
        intents.members = True

        # REQUIRED FOR ! PREFIX COMMANDS
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):

        if GUILD_ID:

            guild = discord.Object(
                id=int(GUILD_ID)
            )

            self.tree.copy_global_to(
                guild=guild
            )

            await self.tree.sync(
                guild=guild
            )

            print(
                "Slash commands synced to GUILD_ID."
            )

        else:

            await self.tree.sync()

            print(
                "Global slash commands synced."
            )


bot = EconomyBot()


# ==============================
# EVENTS
# ==============================

@bot.event
async def on_ready():

    print(
        f"Logged in as {bot.user} "
        f"(ID: {bot.user.id})"
    )

    for guild in bot.guilds:
        await cache_guild_invites(guild)


@bot.event
async def on_guild_join(guild):

    await cache_guild_invites(guild)


@bot.event
async def on_member_join(member: discord.Member):

    if member.bot:
        return

    guild = guild_data(
        member.guild.id
    )

    # Don't reward the same member twice
    if str(member.id) in guild["rewarded_members"]:
        return

    invite = await identify_invite(
        member.guild
    )

    if not invite or not invite.inviter:
        return

    inviter = invite.inviter

    if inviter.id == member.id:
        return

    add_money(
        member.guild.id,
        inviter.id,
        INVITE_REWARD
    )

    user = user_data(
        member.guild.id,
        inviter.id
    )

    user["invites"] += 1

    guild["rewarded_members"].append(
        str(member.id)
    )

    save_db()

    message = (
        f"🎉 {member.mention} joined using "
        f"an invite from {inviter.mention}!\n"
        f"💎 {inviter.mention} earned "
        f"**+{INVITE_REWARD} "
        f"{CURRENCY_EMOJI}**.\n"
        f"📨 Total rewarded invites: "
        f"**{user['invites']}**"
    )

    if LOG_CHANNEL_ID:

        channel = member.guild.get_channel(
            int(LOG_CHANNEL_ID)
        )

        if channel and channel.is_text_based():

            await channel.send(message)

            return

    if (
        member.guild.system_channel
        and member.guild.system_channel.is_text_based()
    ):

        await member.guild.system_channel.send(
            message
        )


# ============================================================
# SLASH COMMANDS
# ============================================================

@bot.tree.command(
    name="balance",
    description="Check an economy balance."
)
@app_commands.describe(
    user="Member to check"
)
async def balance_cmd(
    interaction: discord.Interaction,
    user: discord.Member | None = None
):

    target = user or interaction.user

    await interaction.response.send_message(
        f"💰 {target.mention} has "
        f"{money(balance(interaction.guild_id, target.id))}."
    )


@bot.tree.command(
    name="daily",
    description="Claim your daily reward."
)
async def daily_cmd(
    interaction: discord.Interaction
):

    user = user_data(
        interaction.guild_id,
        interaction.user.id
    )

    now = int(time.time())

    remaining = (
        86400 -
        (now - user["daily"])
    )

    if remaining > 0:

        hours = max(
            1,
            (remaining + 3599) // 3600
        )

        await interaction.response.send_message(
            f"⏳ Your daily reward is ready "
            f"in about **{hours}h**.",
            ephemeral=True
        )

        return

    user["daily"] = now

    add_money(
        interaction.guild_id,
        interaction.user.id,
        DAILY_REWARD
    )

    await interaction.response.send_message(
        f"🎁 Daily reward: "
        f"+{money(DAILY_REWARD)}!"
    )


@bot.tree.command(
    name="work",
    description="Work for random economy money."
)
async def work_cmd(
    interaction: discord.Interaction
):

    amount = random.randint(
        WORK_MIN,
        WORK_MAX
    )

    add_money(
        interaction.guild_id,
        interaction.user.id,
        amount
    )

    await interaction.response.send_message(
        f"💼 You worked and earned "
        f"{money(amount)}!"
    )


@bot.tree.command(
    name="give",
    description="Give economy money to another member."
)
@app_commands.describe(
    user="Member",
    amount="Amount"
)
async def give_cmd(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int
):

    if amount < 1:

        await interaction.response.send_message(
            "❌ Amount must be at least 1.",
            ephemeral=True
        )

        return

    if (
        user.bot
        or user.id == interaction.user.id
    ):

        await interaction.response.send_message(
            "❌ Choose another real member.",
            ephemeral=True
        )

        return

    current = balance(
        interaction.guild_id,
        interaction.user.id
    )

    if current < amount:

        await interaction.response.send_message(
            f"❌ You only have "
            f"{money(current)}.",
            ephemeral=True
        )

        return

    add_money(
        interaction.guild_id,
        interaction.user.id,
        -amount
    )

    add_money(
        interaction.guild_id,
        user.id,
        amount
    )

    await interaction.response.send_message(
        f"✅ {interaction.user.mention} gave "
        f"{money(amount)} to {user.mention}."
    )


@bot.tree.command(
    name="leaderboard",
    description="Show the economy leaderboard."
)
async def leaderboard_cmd(
    interaction: discord.Interaction
):

    users = guild_data(
        interaction.guild_id
    )["users"]

    rows = sorted(
        (
            (
                uid,
                data.get("balance", 0)
            )
            for uid, data in users.items()
        ),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    if not rows:

        text = "No economy data yet."

    else:

        text = "\n".join(
            f"**{i}.** <@{uid}> — "
            f"{money(amount)}"
            for i, (uid, amount)
            in enumerate(rows, 1)
        )

    embed = discord.Embed(
        title="🏆 Economy Leaderboard",
        description=text
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="invites",
    description="Check invite count."
)
@app_commands.describe(
    user="Member to check"
)
async def invites_cmd(
    interaction: discord.Interaction,
    user: discord.Member | None = None
):

    target = user or interaction.user

    data = user_data(
        interaction.guild_id,
        target.id
    )

    await interaction.response.send_message(
        f"📨 {target.mention} has "
        f"**{data['invites']}** rewarded invites."
    )


@bot.tree.command(
    name="invite-leaderboard",
    description="Show invite leaderboard."
)
async def invite_leaderboard_cmd(
    interaction: discord.Interaction
):

    users = guild_data(
        interaction.guild_id
    )["users"]

    rows = sorted(
        (
            (
                uid,
                data.get("invites", 0)
            )
            for uid, data in users.items()
        ),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    text = "\n".join(
        f"**{i}.** <@{uid}> — "
        f"**{count}** invites"
        for i, (uid, count)
        in enumerate(rows, 1)
    ) or "No invite data yet."

    embed = discord.Embed(
        title="📨 Invite Leaderboard",
        description=text
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="shop",
    description="Show roles available in the economy shop."
)
async def shop_cmd(
    interaction: discord.Interaction
):

    shop = guild_data(
        interaction.guild_id
    )["shop"]

    lines = []

    for role_id, price in shop.items():

        role = interaction.guild.get_role(
            int(role_id)
        )

        if role:

            lines.append(
                f"{role.mention} — "
                f"{money(price)}"
            )

    if not lines:

        await interaction.response.send_message(
            "🛒 The shop is empty."
        )

        return

    embed = discord.Embed(
        title="🛒 Economy Role Shop",
        description="\n".join(lines)
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="buy",
    description="Buy a role from the economy shop."
)
@app_commands.describe(
    role="Role to buy"
)
async def buy_cmd(
    interaction: discord.Interaction,
    role: discord.Role
):

    shop = guild_data(
        interaction.guild_id
    )["shop"]

    role_id = str(role.id)

    if role_id not in shop:

        await interaction.response.send_message(
            "❌ That role is not in the shop.",
            ephemeral=True
        )

        return

    if role in interaction.user.roles:

        await interaction.response.send_message(
            "❌ You already have that role.",
            ephemeral=True
        )

        return

    if not role.is_assignable():

        await interaction.response.send_message(
            "❌ I can't give that role. "
            "Move my bot role above the shop role.",
            ephemeral=True
        )

        return

    price = int(shop[role_id])

    current = balance(
        interaction.guild_id,
        interaction.user.id
    )

    if current < price:

        await interaction.response.send_message(
            f"❌ You need "
            f"{money(price - current)} more.",
            ephemeral=True
        )

        return

    try:

        await interaction.user.add_roles(
            role,
            reason="Economy shop purchase"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I don't have permission "
            "to give that role.",
            ephemeral=True
        )

        return

    add_money(
        interaction.guild_id,
        interaction.user.id,
        -price
    )

    await interaction.response.send_message(
        f"🎉 You bought {role.mention} "
        f"for {money(price)}!"
    )


# ============================================================
# MANAGER SLASH COMMANDS
# ============================================================

def manager_only():

    return app_commands.checks.has_permissions(
        manage_guild=True
    )


@bot.tree.command(
    name="shop-add",
    description="Add/update a role in the economy shop."
)
@manager_only()
@app_commands.describe(
    role="Role",
    price="Price"
)
async def shop_add_cmd(
    interaction: discord.Interaction,
    role: discord.Role,
    price: int
):

    if price < 1:

        await interaction.response.send_message(
            "❌ Price must be at least 1.",
            ephemeral=True
        )

        return

    if not role.is_assignable():

        await interaction.response.send_message(
            "❌ My bot role must be above this role.",
            ephemeral=True
        )

        return

    guild_data(
        interaction.guild_id
    )["shop"][str(role.id)] = price

    save_db()

    await interaction.response.send_message(
        f"✅ Added {role.mention} to the shop "
        f"for {money(price)}."
    )


@bot.tree.command(
    name="shop-remove",
    description="Remove a role from the economy shop."
)
@manager_only()
@app_commands.describe(
    role="Role"
)
async def shop_remove_cmd(
    interaction: discord.Interaction,
    role: discord.Role
):

    guild_data(
        interaction.guild_id
    )["shop"].pop(
        str(role.id),
        None
    )

    save_db()

    await interaction.response.send_message(
        f"✅ Removed {role.mention} from the shop."
    )


@bot.tree.command(
    name="addmoney",
    description="Add economy money."
)
@manager_only()
@app_commands.describe(
    user="Member",
    amount="Amount"
)
async def addmoney_cmd(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int
):

    if amount < 1:

        await interaction.response.send_message(
            "❌ Amount must be at least 1.",
            ephemeral=True
        )

        return

    new_balance = add_money(
        interaction.guild_id,
        user.id,
        amount
    )

    await interaction.response.send_message(
        f"✅ Added {money(amount)} to "
        f"{user.mention}.\n"
        f"New balance: {money(new_balance)}."
    )


@bot.tree.command(
    name="removemoney",
    description="Remove economy money."
)
@manager_only()
@app_commands.describe(
    user="Member",
    amount="Amount"
)
async def removemoney_cmd(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int
):

    if amount < 1:

        await interaction.response.send_message(
            "❌ Amount must be at least 1.",
            ephemeral=True
        )

        return

    new_balance = add_money(
        interaction.guild_id,
        user.id,
        -amount
    )

    await interaction.response.send_message(
        f"✅ Removed {money(amount)} from "
        f"{user.mention}.\n"
        f"New balance: {money(new_balance)}."
    )


@bot.tree.command(
    name="setmoney",
    description="Set an economy balance."
)
@manager_only()
@app_commands.describe(
    user="Member",
    amount="Amount"
)
async def setmoney_cmd(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int
):

    if amount < 0:

        await interaction.response.send_message(
            "❌ Amount can't be negative.",
            ephemeral=True
        )

        return

    data = user_data(
        interaction.guild_id,
        user.id
    )

    data["balance"] = amount

    save_db()

    await interaction.response.send_message(
        f"✅ Set {user.mention}'s balance to "
        f"{money(amount)}."
    )


# ============================================================
# PREFIX COMMANDS
# ============================================================

@bot.command(
    name="balance",
    aliases=["bal"]
)
async def prefix_balance(
    ctx,
    member: discord.Member | None = None
):

    target = member or ctx.author

    await ctx.send(
        f"💰 {target.mention} has "
        f"{money(balance(ctx.guild.id, target.id))}."
    )


@bot.command(name="daily")
async def prefix_daily(ctx):

    user = user_data(
        ctx.guild.id,
        ctx.author.id
    )

    now = int(time.time())

    remaining = (
        86400 -
        (now - user["daily"])
    )

    if remaining > 0:

        hours = max(
            1,
            (remaining + 3599) // 3600
        )

        await ctx.send(
            f"⏳ Your daily reward is ready "
            f"in about **{hours}h**."
        )

        return

    user["daily"] = now

    add_money(
        ctx.guild.id,
        ctx.author.id,
        DAILY_REWARD
    )

    await ctx.send(
        f"🎁 Daily reward: "
        f"+{money(DAILY_REWARD)}!"
    )


@bot.command(name="work")
async def prefix_work(ctx):

    amount = random.randint(
        WORK_MIN,
        WORK_MAX
    )

    add_money(
        ctx.guild.id,
        ctx.author.id,
        amount
    )

    await ctx.send(
        f"💼 You worked and earned "
        f"{money(amount)}!"
    )

# ==============================
# PREFIX COMMANDS
# ==============================

@bot.command(name="give", aliases=["pay"])
async def prefix_give(ctx, member: discord.Member, amount: int):
    if amount < 1:
        await ctx.send("❌ Amount must be at least 1.")
        return

    if member.bot or member.id == ctx.author.id:
        await ctx.send("❌ Choose another real member.")
        return

    current = balance(ctx.guild.id, ctx.author.id)

    if current < amount:
        await ctx.send(
            f"❌ You only have {money(current)}."
        )
        return

    add_money(ctx.guild.id, ctx.author.id, -amount)
    add_money(ctx.guild.id, member.id, amount)

    await ctx.send(
        f"✅ {ctx.author.mention} gave "
        f"{money(amount)} to {member.mention}."
    )


@bot.command(name="leaderboard", aliases=["lb"])
async def prefix_leaderboard(ctx):
    users = guild_data(ctx.guild.id)["users"]

    rows = sorted(
        ((uid, d.get("balance", 0)) for uid, d in users.items()),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    if not rows:
        text = "No economy data yet."
    else:
        text = "\n".join(
            f"**{i}.** <@{uid}> — {money(amount)}"
            for i, (uid, amount) in enumerate(rows, 1)
        )

    embed = discord.Embed(
        title="🏆 Economy Leaderboard",
        description=text
    )

    await ctx.send(embed=embed)


@bot.command(name="invites")
async def prefix_invites(ctx, member: discord.Member | None = None):
    target = member or ctx.author
    u = user_data(ctx.guild.id, target.id)

    await ctx.send(
        f"📨 {target.mention} has "
        f"**{u['invites']}** rewarded invites."
    )


# ==============================
# ROB COMMAND
# ==============================

rob_cooldowns = {}


@bot.command(name="rob")
async def rob(ctx, target: discord.Member):
    if target.bot:
        await ctx.send("❌ You can't rob a bot.")
        return

    if target.id == ctx.author.id:
        await ctx.send("❌ You can't rob yourself.")
        return

    key = (ctx.guild.id, ctx.author.id)
    now = time.time()

    if key in rob_cooldowns:
        remaining = 3600 - (now - rob_cooldowns[key])

        if remaining > 0:
            minutes = max(1, int(remaining // 60))
            await ctx.send(
                f"⏳ You can rob someone again in "
                f"**{minutes} minutes**."
            )
            return

    target_balance = balance(ctx.guild.id, target.id)

    if target_balance < 100:
        await ctx.send(
            f"❌ {target.mention} doesn't have enough "
            f"{CURRENCY_NAME} to rob."
        )
        return

    rob_cooldowns[key] = now

    # 60% success chance
    if random.randint(1, 100) <= 60:

        amount = random.randint(
            max(1, target_balance // 10),
            max(1, target_balance // 4)
        )

        add_money(ctx.guild.id, target.id, -amount)
        add_money(ctx.guild.id, ctx.author.id, amount)

        await ctx.send(
            f"💰 **Rob successful!**\n"
            f"🦹 {ctx.author.mention} stole "
            f"{money(amount)} from {target.mention}!"
        )

    else:

        penalty = min(
            balance(ctx.guild.id, ctx.author.id),
            random.randint(25, 75)
        )

        if penalty > 0:
            add_money(
                ctx.guild.id,
                ctx.author.id,
                -penalty
            )

        await ctx.send(
            f"🚔 **Rob failed!**\n"
            f"{ctx.author.mention} got caught and lost "
            f"{money(penalty)}."
        )


# ==============================
# START BOT
# ==============================

bot.run(TOKEN)
