import discord
from discord.ext import commands
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import io
import hashlib
import os

# تحديد مسار Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# إعدادات البوت
TOKEN = "MTMwNTk5MDc1ODIwNTIzMTE2NQ.GeCWnO.CcjdxJhiZAhf-k4_di1nGVeU_U4FVUU_cbamog"
GUILD_ID = 1287855233162154004
VERIFIED_ROLE_ID = 1289567685255889000  # الرول الذي سيتم إضافته
OLD_ROLE_ID = 1336108203926360105  # الرول الذي سيتم إزالته إذا كان موجودًا
VERIFY_CHANNEL_ID = 1336106441366306866  # قناة التفعيل
LOG_CHANNEL_ID = 1336097528382488658  # قناة اللوجات
FORM_CHANNEL_ID = 1336106742756544523  # قناة الفورم

# ملف لتخزين الأشخاص الذين تم التحقق منهم
verified_users_file = "verified_users.txt"
verified_images_file = "verified_images.txt"
if not os.path.exists(verified_users_file):
    with open(verified_users_file, "w") as f:
        f.write("")
if not os.path.exists(verified_images_file):
    with open(verified_images_file, "w") as f:
        f.write("")

# تحميل البيانات المخزنة
def load_verified_data():
    with open(verified_users_file, "r") as f:
        verified_users = f.read().splitlines()
    with open(verified_images_file, "r") as f:
        verified_images = f.read().splitlines()
    return verified_users, verified_images

# تخزين البيانات
def save_verified_data(verified_users, verified_images):
    with open(verified_users_file, "w") as f:
        f.write("\n".join(verified_users))
    with open(verified_images_file, "w") as f:
        f.write("\n".join(verified_images))

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot = discord.Client(intents=intents)

from discord import ui

class VerificationForm(ui.Modal, title="Apply for Verification"):
    name = ui.TextInput(label="Your name in game", placeholder="Enter your game name")
    user_id = ui.TextInput(label="Your ID in game", placeholder="Enter your ID")

    async def on_submit(self, interaction: discord.Interaction):
        new_nickname = f"{self.name.value} [ID:{self.user_id.value}]"
        try:
            await interaction.user.edit(nick=new_nickname)
            await interaction.response.send_message(f"✅ Name updated to `{new_nickname}`", ephemeral=True)

            # ID الرولات المطلوبة
            OLD_ROLE_ID = 1289567685255889000  # الرول التي سيتم إزالتها
            NEW_ROLE_ID = 1305603263936331787  # الرول الجديدة التي سيتم إضافتها

            member = interaction.guild.get_member(interaction.user.id)
            if member:
                old_role = interaction.guild.get_role(OLD_ROLE_ID)
                new_role = interaction.guild.get_role(NEW_ROLE_ID)

                if old_role in member.roles:
                    await member.remove_roles(old_role)
                    print(f"Removed old role from {interaction.user.mention}")

                if new_role:
                    await member.add_roles(new_role)
                    print(f"Added new role to {interaction.user.mention}")

        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to change your nickname!", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot is ready! Logged in as {bot.user}")
    
    form_channel = bot.get_channel(FORM_CHANNEL_ID)
    if form_channel:
        embed = discord.Embed(title="Type Your Name And Id In Game", description="Click the button below to change your nickname and id in discord.\n note : if your Name or Id wrong the role will be romoved and you may get banned")
        view = discord.ui.View()
        button = discord.ui.Button(label="Change", style=discord.ButtonStyle.primary, custom_id="apply_button")
        view.add_item(button)
        await form_channel.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.response.is_done():
        try:
            await interaction.response.send_modal(VerificationForm())
        except discord.NotFound:
            print("❌ Interaction not found (error 10062), ignoring.")


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    if message.channel.id != VERIFY_CHANNEL_ID:
        return

    verified_users, verified_images = load_verified_data()

    if message.attachments:
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg']):
                image_bytes = await attachment.read()
                image = Image.open(io.BytesIO(image_bytes))
                image = image.convert('L')
                image = ImageOps.invert(image)
                image = image.point(lambda p: p > 180 and 255)
                image = image.filter(ImageFilter.SHARPEN)
                extracted_text = pytesseract.image_to_string(image, config="--psm 6")
                print("Extracted Text from Image:")
                print(extracted_text)

                has_server_500 = "#500" in extracted_text
                has_alliance_hd = "[-HD-]" in extracted_text

                if has_server_500 and has_alliance_hd:
                    if str(message.author.id) in verified_users:
                        await message.channel.send(f"❌ You have already been verified, {message.author.mention}.")
                        return

                    image_hash = hashlib.md5(image_bytes).hexdigest()
                    if image_hash in verified_images:
                        await message.channel.send(f"❌ This image has already been verified.")
                        return

                    member = message.guild.get_member(message.author.id)
                    role = message.guild.get_role(VERIFIED_ROLE_ID)
                    if role and member:
                        old_role = message.guild.get_role(OLD_ROLE_ID)
                        if old_role in member.roles:
                            await member.remove_roles(old_role)
                            print(f"Removed old role from {message.author.mention}")

                        await member.add_roles(role)
                        print(f"Added verified role to {message.author.mention}")

                        verified_users.append(str(message.author.id))
                        verified_images.append(image_hash)
                        save_verified_data(verified_users, verified_images)

                        log_channel = bot.get_channel(LOG_CHANNEL_ID)
                        if log_channel:
                            embed = discord.Embed(
                                title="✅ User Verified",
                                description=f"**{message.author.mention}** has been verified successfully!\n"
                                            f"Discord ID: `{message.author.id}`"
                            )
                            embed.set_image(url=attachment.url)
                            await log_channel.send(embed=embed)

                        await message.delete()
                        await message.channel.send(f"✅ You have been verified successfully!")
                    else:
                        await message.channel.send("❌ Error")
                elif not has_server_500:
                    await message.channel.send("❌ You are not a member of the Kingdom. {message.author.mention}َ!")
                elif has_server_500 and not has_alliance_hd:
                    await message.channel.send("❌ You are not a member of the Alliance. {message.author.mention}")

bot.run(TOKEN)
