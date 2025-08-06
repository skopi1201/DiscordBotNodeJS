import discord
import os
import random
import json
import difflib
from discord.ext import commands
from discord import app_commands

# Load token from secrets.json

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Load tank data
with open("answers.json", "r") as f:
    answers = json.load(f)

# Track active games per channel
active_games = {}

def is_close_guess(guess, aliases, threshold=0.7):
    guess = guess.lower()
    return any(difflib.SequenceMatcher(None, guess, alias.lower()).ratio() >= threshold for alias in aliases)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

@tree.command(name="tank", description="Start a multiplayer tank trivia game")
@app_commands.describe(
    start_year="Start year of tank production (default 1900)",
    end_year="End year of tank production (default 2025)",
    rounds="Number of rounds (default 10)"
)
async def tank_slash(
    interaction: discord.Interaction,
    start_year: int = 1900,
    end_year: int = 2025,
    rounds: int = 10
):
    channel_id = interaction.channel.id

    if channel_id in active_games:
        await interaction.response.send_message("⚠️ A game is already running in this channel!", ephemeral=True)
        return

    if rounds < 1 or rounds > 50:
        await interaction.response.send_message("❌ Rounds must be between 1 and 50.", ephemeral=True)
        return

    filtered = [
        (img, data) for img, data in answers.items()
        if start_year <= data["year"] <= end_year
    ]

    if not filtered:
        await interaction.response.send_message("❌ No tanks found in that year range.", ephemeral=True)
        return

    if len(filtered) < rounds:
        await interaction.response.send_message(
            f"⚠️ Only {len(filtered)} tanks available for that year range. Game will end early if needed."
        )

    tank_pool = filtered.copy()
    random.shuffle(tank_pool)

    active_games[channel_id] = {
        "scores": {},
        "running": True
    }

    await interaction.response.send_message(
        f"🎮 **Tank Trivia started!** Up to {rounds} rounds. First correct answer gets the point!"
    )

    round_num = 0
    while round_num < rounds and tank_pool and active_games[channel_id]["running"]:
        tank_img, tank_data = tank_pool.pop()
        round_num += 1
        aliases = tank_data["aliases"]
        year = tank_data["year"]

        with open(f"tanks/{tank_img}", "rb") as img_file:
            file = discord.File(img_file)
            question_msg = await interaction.channel.send(
                f"🧠 **Round {round_num}/{rounds}**\n🔍 What tank is this? (Year: {year})",
                file=file
            )

        winner = None

        def check(m):
            return m.channel.id == channel_id

        try:
            for remaining in range(20, 0, -1):
                try:
                    msg = await bot.wait_for("message", timeout=1.0, check=check)
                    guess = msg.content.strip().lower()

                    if guess == "!stop":
                        active_games[channel_id]["running"] = False
                        await interaction.channel.send("🛑 Game cancelled.")
                        return

                    if is_close_guess(guess, aliases):
                        winner = msg.author
                        name = str(winner)
                        scores = active_games[channel_id]["scores"]
                        scores[name] = scores.get(name, 0) + 1
                        await interaction.channel.send(f"✅ {winner.mention} got it right! (+1)")
                        break
                except:
                    if remaining <= 5:
                        try:
                            await question_msg.edit(
                                content=f"🧠 **Round {round_num}/{rounds}**\n⏳ {remaining} seconds left..."
                            )
                        except:
                            pass
            if not winner:
                await interaction.channel.send(
                    f"⏰ Time's up! Correct answers were: **{', '.join(aliases)}**"
                )
        except Exception as e:
            print(f"Error: {e}")
            continue

    if not tank_pool and round_num < rounds:
        await interaction.channel.send(
            "⚠️ No more tanks available for the selected year range. Ending game early."
        )

    scores = active_games[channel_id]["scores"]
    if scores:
        leaderboard = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        msg = "**🏁 Game Over! Final Scores:**\n"
        for i, (name, score) in enumerate(leaderboard, start=1):
            msg += f"{i}. **{name}**: {score} point{'s' if score != 1 else ''}\n"
    else:
        msg = "Nobody got any points 😢"

    await interaction.channel.send(msg)
    active_games.pop(channel_id, None)

@tree.command(name="stopgame", description="Stop the current Tank Trivia game")
async def stop_slash(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    if channel_id in active_games:
        active_games[channel_id]["running"] = False
        await interaction.response.send_message("🛑 Game has been stopped.")
    else:
        await interaction.response.send_message("ℹ️ No game is currently running in this channel.")

@tree.command(name="help", description="Show help for Tank Trivia commands")
async def help_slash(interaction: discord.Interaction):
    help_text = (
        "**🧠 Tank Trivia Bot Help**\n\n"
        "🎮 `/tank start_year:YYYY end_year:YYYY rounds:X` - Start a new multiplayer trivia game.\n"
        "• Everyone in the channel can answer.\n"
        "• First correct answer per round gets 1 point.\n"
        "• Game ends early if not enough tanks are available.\n\n"
        "🛑 `/stopgame` - Cancels the current game in this channel.\n"
        "⌛ 20 second timer per round. Last 5 seconds show a countdown.\n\n"
        "📁 Images must be in the `tanks/` folder and answers in `answers.json`\n"
        "💬 Fuzzy matching is enabled — close guesses count!"
    )
    await interaction.response.send_message(help_text, ephemeral=True)

bot.run("******")
