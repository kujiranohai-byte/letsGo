import discord
from discord.ext import commands, tasks
import aiosqlite
from datetime import datetime, timedelta
import os

TOKEN = os.getenv("DISCORD_TOKEN")

# ===== ログ管理サーバー設定 =====
LOG_GUILD_ID = 1500396286271295578
LOG_CATEGORY_ID = 1500396365199446086

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

announce_config = {}
scheduled = []

# =======================
# DB
# =======================
async def init_db():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            guild_id TEXT,
            title TEXT,
            detail TEXT,
            created_at TEXT
        )
        """)
        await db.commit()

# =======================
# ログチャンネル取得
# =======================
async def get_log_channel(guild_id):
    log_guild = bot.get_guild(LOG_GUILD_ID)
    if not log_guild:
        return None

    category = log_guild.get_channel(LOG_CATEGORY_ID)
    if not category:
        return None

    name = str(guild_id)

    for ch in category.text_channels:
        if ch.name == name:
            return ch

    return await log_guild.create_text_channel(name=name, category=category)

# =======================
# 通報
# =======================
@bot.tree.command(name="report", description="匿名通報")
async def report(interaction: discord.Interaction, title: str, detail: str):

    await interaction.response.defer(ephemeral=True)

    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("""
        INSERT INTO reports (user_id, guild_id, title, detail, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (
            str(interaction.user.id),
            str(interaction.guild.id),
            title,
            detail,
            str(datetime.now())
        ))
        await db.commit()
        report_id = cur.lastrowid

    log_ch = await get_log_channel(interaction.guild.id)

    if log_ch:
        embed = discord.Embed(title="📨 匿名通報", color=0xff5555)
        embed.add_field(name="整理番号", value=report_id)
        embed.add_field(name="送信者ID", value=interaction.user.id)
        embed.add_field(name="内容", value=f"{title}\n{detail}")
        embed.add_field(name="日時", value=str(datetime.now()))
        await log_ch.send(embed=embed)

    await interaction.followup.send(f"通報完了（ID:{report_id}）", ephemeral=True)

# =======================
# 返信
# =======================
@bot.tree.command(name="response", description="通報返信")
async def response(interaction: discord.Interaction, report_id: int, title: str, detail: str):

    await interaction.response.defer(ephemeral=True)

    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT user_id FROM reports WHERE id=?", (report_id,))
        row = await cur.fetchone()

    if not row:
        return await interaction.followup.send("IDが存在しない", ephemeral=True)

    try:
        user = await bot.fetch_user(int(row[0]))

        embed = discord.Embed(title="📩 運営からの返信", color=0x00ffcc)
        embed.add_field(name="件名", value=title)
        embed.add_field(name="内容", value=detail)

        await user.send(embed=embed)
        await interaction.followup.send("送信完了", ephemeral=True)

    except:
        await interaction.followup.send("エラーが発生（DM送信不可）", ephemeral=True)

# =======================
# アナウンス設定
# =======================
@bot.tree.command(name="announce_setup")
async def announce_setup(interaction: discord.Interaction,
                         source: discord.TextChannel,
                         target: discord.TextChannel):

    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("管理者のみ", ephemeral=True)

    announce_config[interaction.guild.id] = {
        "source": source.id,
        "target": target.id
    }

    await interaction.response.send_message("設定完了", ephemeral=True)

# =======================
# アナウンスUI
# =======================
class AnnounceView(discord.ui.View):
    def __init__(self, content, guild_id):
        super().__init__(timeout=60)
        self.content = content
        self.guild_id = guild_id

    def get_target(self, guild):
        conf = announce_config.get(self.guild_id)
        if not conf:
            return None
        return guild.get_channel(conf["target"])

    @discord.ui.button(label="通常送信", style=discord.ButtonStyle.primary)
    async def normal(self, interaction, button):
        ch = self.get_target(interaction.guild)
        if not ch:
            return await interaction.response.send_message("送信先なし", ephemeral=True)

        await ch.send(self.content)
        await interaction.response.send_message("送信完了", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Embed送信", style=discord.ButtonStyle.success)
    async def embed(self, interaction, button):
        ch = self.get_target(interaction.guild)
        if not ch:
            return await interaction.response.send_message("送信先なし", ephemeral=True)

        await ch.send(embed=discord.Embed(description=self.content))
        await interaction.response.send_message("送信完了", ephemeral=True)
        self.stop()

# =======================
# スケジューラー
# =======================
@tasks.loop(seconds=5)
async def scheduler():
    now = datetime.utcnow()

    for item in scheduled[:]:
        if now >= item["run_at"]:
            guild = bot.get_guild(item["guild_id"])
            conf = announce_config.get(item["guild_id"])

            if guild and conf:
                ch = guild.get_channel(conf["target"])
                if ch:
                    await ch.send(item["content"])

            scheduled.remove(item)

# =======================
# メッセージ監視
# =======================
@bot.event
async def on_message(message):

    if message.author.bot or not message.guild:
        return

    conf = announce_config.get(message.guild.id)

    if conf and message.channel.id == conf["source"]:
        view = AnnounceView(message.content, message.guild.id)
        await message.reply("送信方法を選択", view=view)

    await bot.process_commands(message)

# =======================
# 起動
# =======================
@bot.event
async def on_ready():
    await init_db()
    await bot.tree.sync()
    scheduler.start()

    print("READY OK:", bot.user)

import os
TOKEN = os.getenv("DISCORD_TOKEN")

print("TOKEN:", TOKEN)

bot.run(TOKEN)