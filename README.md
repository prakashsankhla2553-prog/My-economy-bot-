# 💎 Invite Economy Bot — Python

Complete Discord economy bot using `discord.py`.

## Features

- 📨 +125 💎 for a valid first-time invite by default
- 💰 Balance
- 🎁 Daily reward
- 💼 Work reward
- 💸 Give money
- 🏆 Economy leaderboard
- 📨 Invite leaderboard
- 🛒 Role shop
- 🛍️ Buy roles with economy money
- 🛠️ Manager add/remove/set money
- 💾 JSON database
- 🚫 Prevents rewarding the same member repeatedly

## Setup

1. Install Python 3.10+.
2. Rename `.env.example` to `.env`.
3. Fill in `DISCORD_TOKEN`, `CLIENT_ID`, and optionally `GUILD_ID`.
4. Install packages:

```bash
pip install -r requirements.txt
```

5. Start:

```bash
python bot.py
```

## Environment variables

```env
DISCORD_TOKEN=your_bot_token
CLIENT_ID=your_application_id
GUILD_ID=your_server_id

CURRENCY_NAME=Gems
CURRENCY_EMOJI=💎
INVITE_REWARD=125
DAILY_REWARD=250
WORK_MIN=50
WORK_MAX=150
LOG_CHANNEL_ID=
```

You can use a custom Discord emoji as the currency:

```env
CURRENCY_EMOJI=<:gem:123456789012345678>
```

## Discord Developer Portal

Enable:
- Server Members Intent

Bot permissions:
- Manage Server
- Manage Roles
- View Channels
- Send Messages
- Embed Links

Put the bot's highest role above every role sold in the shop.

## Commands

Members:
- `/balance`
- `/daily`
- `/work`
- `/give`
- `/leaderboard`
- `/invites`
- `/invite-leaderboard`
- `/shop`
- `/buy`

Managers:
- `/shop-add`
- `/shop-remove`
- `/addmoney`
- `/removemoney`
- `/setmoney`

Example:

```text
/shop-add role:@VIP price:2500
```

Then:

```text
/shop
/buy role:@VIP
```

## Invite tracking

The bot compares Discord invite use counts when a member joins. It rewards the inviter with 125 currency by default.

A member is recorded after receiving the first tracked invite reward, preventing repeated farming from leaving/rejoining.

Some joins, such as vanity URL joins or cases where Discord does not expose the inviter, cannot be credited.

## Hosting note

The JSON database is suitable for testing/small servers. On hosting providers with ephemeral storage, use a persistent disk/database for permanent economy data.

Never upload `.env` or your bot token to GitHub.
