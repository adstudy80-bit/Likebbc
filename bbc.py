import json
import os
import requests
import signal
import sys
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === CONFIG ===
BOT_TOKEN = '8461908870:AAG0KNjEfMB6iQTY-CdbDF-LZLXTnI4mDjI'
API_KEY = '629916b52780282b40084b9cd6e75415fbf4ad26'
BASE_URL = 'https://t.me/bigbulllikesbot?start=verified_'
GROUP_CHAT_ID = -1002891470815  # Your group chat ID
LIKE_API_URL = 'http://127.0.0.1:5000/like?uid={}&server_name=IND&key=Raihan'
VERIFIED_FILE = 'verified_users.json'
SHORT_LINK_FILE = 'verified_links.json'
USAGE_FILE = 'daily_usage.json'
VIP_FILE = 'vip_users.json'
OWNER_ID = 6364877645201
MAX_LIKES = 99999

# Valid regions
VALID_REGIONS = ['ind', 'bd', 'sg', 'id', 'me', 'br', 'vn', 'eu', 'th', 'na', 'us', 'uk']

# Updated links
JOIN_CHANNEL_LINK = "https://t.me/+bUldVt3yKEM2Yjhl"
HOW_TO_VERIFY_LINK = "https://t.me/freelike99/2.com"
BUY_VIP_LINK = "https://t.me/bigbullabhi880"

# === File Helpers ===
def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f)

# === Verified User Logic ===
def load_verified_users():
    return load_json(VERIFIED_FILE)

def save_verified_user(user_id, uid=None, region=None):
    users = load_verified_users()
    now = datetime.now().isoformat()
    for u in users:
        if u["id"] == user_id:
            u["timestamp"] = now
            if uid: u["uid"] = uid
            if region: u["region"] = region
            break
    else:
        users.append({
            "id": user_id, 
            "timestamp": now,
            "uid": uid,
            "region": region
        })
    save_json(VERIFIED_FILE, users)

def is_user_verified_recently(user_id):
    users = load_verified_users()
    for u in users:
        if u["id"] == user_id:
            ts = datetime.fromisoformat(u["timestamp"])
            return datetime.now() - ts < timedelta(hours=12)
    return False

def get_user_like_request(user_id):
    users = load_verified_users()
    for u in users:
        if u["id"] == user_id:
            return u.get("uid"), u.get("region")
    return None, None

# === Short Link Logic ===
def load_short_links():
    return load_json(SHORT_LINK_FILE)

def save_short_link(user_id, uid, region):
    data = load_short_links()
    now = datetime.now().isoformat()
    for entry in data:
        if entry["id"] == user_id:
            entry["timestamp"] = now
            entry["uid"] = uid
            entry["region"] = region
            break
    else:
        data.append({
            "id": user_id, 
            "timestamp": now,
            "uid": uid,
            "region": region
        })
    save_json(SHORT_LINK_FILE, data)

def is_short_link_expired(user_id):
    data = load_short_links()
    for entry in data:
        if entry["id"] == user_id:
            ts = datetime.fromisoformat(entry["timestamp"])
            return datetime.now() - ts > timedelta(minutes=10)
    return True

# === Daily Usage ===
def load_daily_usage():
    return load_json(USAGE_FILE)

def save_daily_usage(user_id):
    usage = load_daily_usage()
    today = datetime.now().strftime("%Y-%m-%d")
    for u in usage:
        if u["id"] == user_id:
            u["date"] = today
            break
    else:
        usage.append({"id": user_id, "date": today})
    save_json(USAGE_FILE, usage)

def has_used_today(user_id):
    usage = load_daily_usage()
    today = datetime.now().strftime("%Y-%m-%d")
    for u in usage:
        if u["id"] == user_id and u["date"] == today:
            return True
    return False

# === VIP Logic ===
def load_vip_users():
    return load_json(VIP_FILE)

def save_vip_user(user_id, days, like_limit):
    vip_users = load_vip_users()
    expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    for user in vip_users:
        if user["id"] == user_id:
            user["expiry"] = expiry_date
            user["like_limit"] = like_limit
            break
    else:
        vip_users.append({
            "id": user_id, 
            "expiry": expiry_date, 
            "like_limit": like_limit
        })
    save_json(VIP_FILE, vip_users)

def remove_vip_user(user_id):
    vip_users = load_vip_users()
    vip_users = [u for u in vip_users if u["id"] != user_id]
    save_json(VIP_FILE, vip_users)

def is_vip_user(user_id):
    vip_users = load_vip_users()
    for user in vip_users:
        if user["id"] == user_id:
            expiry_date = datetime.strptime(user["expiry"], "%Y-%m-%d")
            return datetime.now() < expiry_date
    return False

def get_vip_like_limit(user_id):
    vip_users = load_vip_users()
    for user in vip_users:
        if user["id"] == user_id:
            return user.get("like_limit", 1)  # Default to 1 if not specified
    return 1

# === API CALL ===
async def call_like_api(region, uid):
    try:
        url = LIKE_API_URL.format(region=region, uid=uid)
        response = requests.get(url)
        data = response.json()
        
        if data.get("LikesafterCommand", 0) >= MAX_LIKES:
            return {
                "status": 2,
                "message": "Player already has maximum likes",
                "LikesafterCommand": data.get("LikesafterCommand", 0),
                "LikesbeforeCommand": data.get("LikesbeforeCommand", 0),
                "PlayerNickname": data.get("PlayerNickname", "N/A"),
                "UID": uid,
                "LikesGivenByAPI": data.get("LikesGivenByAPI", 0)
            }
            
        return data
    except Exception as e:
        return {"error": str(e)}

# === Helper Functions ===
def reset_daily_data():
    for file in [VERIFIED_FILE, SHORT_LINK_FILE, USAGE_FILE]:
        if os.path.exists(file):
            with open(file, 'w') as f:
                json.dump([], f)

def format_next_available_time():
    now = datetime.now()
    next_time = now + timedelta(hours=24)
    return next_time.strftime("%Y-%m-%d %H:%M:%S")

async def send_like_success_message(update, context, api_response, region, is_vip=False):
    user = update.effective_user.first_name or "User"

    if api_response.get("status") == 2:
        text = (
            f"📌 <b>Notice</b>\n\n"
            f"Maximum likes reached for today.\n"
            f"Please try again tomorrow.\n\n"
            f"🔍 <b>Player:</b> <code>{api_response.get('PlayerNickname', 'N/A')}</code>\n"
            f"🔍 <b>UID:</b> <code>{api_response.get('UID', 'N/A')}</code>\n"
            f"🔍 <b>Current Likes:</b> <code>{api_response.get('LikesafterCommand', 0)}</code>\n\n"
            f"<b>Bot Owner:</b> @bigbullabhi880"
        )
    else:
        vip_text = f"💎 <b>VIP User:</b> {user}\n" if is_vip else f"👤 <b>User:</b> {user}\n"
        text = (
            f"<b>✅ Like Sent Successfully!</b>\n\n"
            f"{vip_text}"
            f"🔸 <b>Player:</b> <code>{api_response.get('PlayerNickname', 'N/A')}</code>\n"
            f"🔸 <b>UID:</b> <code>{api_response.get('UID', 'N/A')}</code>\n"
            f"🔸 <b>Region:</b> <code>{region.upper()}</code>\n"
            f"🔸 <b>Likes Before:</b> <code>{api_response.get('LikesbeforeCommand', 0)}</code>\n"
            f"🔸 <b>Likes After:</b> <code>{api_response.get('LikesafterCommand', 0)}</code>\n"
            f"🔸 <b>Likes Given:</b> <code>{api_response.get('LikesGivenByAPI', 0)}</code>\n\n"
            f"❗ <b>Next Likes Available:</b> {format_next_available_time()}\n\n"
            f"<b>Bot Owner:</b> @bigbullabhi880"
        )

    await update.message.reply_text(text, parse_mode="HTML")
    
    keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("🌟 JOIN CHANNEL", url="https://t.me/+bUldVt3yKEM2Yjhl")],
    [InlineKeyboardButton("💎 BUY VIP", url="https://t.me/bigbullabhi880")]
])
    
    # Reply to user's message
    await update.message.reply_text(
        text=text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    
    # Also send to group chat if not VIP
    if not is_vip:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

# === Commands ===
async def like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user.first_name or "there"
    
    # Send initial message to user
    loading_msg = await update.message.reply_text(
        text=f"*⏳ Processing your like request...*",
        parse_mode='Markdown'
    )

    if not context.args or len(context.args) < 2:
        await loading_msg.edit_text(
            "*❌ Invalid Format*\n\n"
            "*Usage:* `/like [region] [uid]`\n\n"
            "*Valid regions:* ind, bd, sg, id, me, br, vn, eu, th, na, us, uk\n\n"
            "*Example:* `/like ind 8431487083`",
            parse_mode='Markdown'
        )
        return

    region = context.args[0].lower()
    uid = context.args[1]
    
    # Validate region
    if region not in VALID_REGIONS:
        await loading_msg.edit_text(
            "*❌ Invalid Region*\n\n"
            f"*You entered:* `{region}`\n"
            "*Valid regions:* ind, bd, sg, id, me, br, vn, eu, th, na, us, uk\n\n"
            "*Example:* `/like ind 8431487083`",
            parse_mode='Markdown'
        )
        return

    # Owner bypass
    if user_id == OWNER_ID:
        api_response = await call_like_api(region, uid)
        if "error" in api_response:
            await loading_msg.edit_text(f"*⚠️ API error:*\n`{api_response['error']}`", parse_mode='Markdown')
            return
        
        await send_like_success_message(update, context, api_response, region)
        await loading_msg.delete()
        return

    # VIP bypass
    if is_vip_user(user_id):
        api_response = await call_like_api(region, uid)
        if "error" in api_response:
            await loading_msg.edit_text(f"*⚠️ API error:*\n`{api_response['error']}`", parse_mode='Markdown')
            return
        
        await send_like_success_message(update, context, api_response, region, is_vip=True)
        await loading_msg.delete()
        return

    # Normal user flow
    if not is_user_verified_recently(user_id):
        if not is_short_link_expired(user_id):
            await loading_msg.edit_text(
                "*⚠️ You must use your previous verification link. You can generate a new one after 10 minutes.*",
                parse_mode='Markdown'
            )
            return

        user_param = f"{region}_{uid}"
        destination_url = f"{BASE_URL}{user_param}"

        try:
            short_api = f"https://vplink.in/api?api={API_KEY}&url={destination_url}"
            response = requests.get(short_api).json()
            if response.get("status") != "success":
                raise Exception(response.get("message", "Unknown error"))
            short_link = response["shortenedUrl"]
            save_short_link(user_id, uid, region)
        except Exception as e:
            await loading_msg.edit_text(f"*⚠️ Link generation failed:*\n`{e}`", parse_mode='Markdown')
            return

        text = ( 

            f"*Like Request 🥶*\n\n"
            f"*👤 Name:* `{user}`\n"
            f"*🆔 UID:* `{uid}`\n"
            f"*🌍 Region:* `{region.upper()}`\n\n"
            f"*🔗 {short_link}*\n"
            f"*⚠️ Link expired in 10 minutes*"
            f"*BIG BULL CHEATS*"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Verify & Send Likes", url=short_link)],
            [InlineKeyboardButton("❓ How to Verify?", url=HOW_TO_VERIFY_LINK)]
        ])
        await loading_msg.edit_text(text, reply_markup=keyboard, parse_mode='Markdown')
        return

    if has_used_today(user_id):
        await loading_msg.edit_text("*🚫 You have already used your free Like today.*\n*Come back tomorrow after 4 AM IST.*", parse_mode='Markdown')
        return

    api_response = await call_like_api(region, uid)

    if "error" in api_response:
        await loading_msg.edit_text(f"*⚠️ API error:*\n`{api_response['error']}`", parse_mode='Markdown')
        return

    save_daily_usage(user_id)
    await send_like_success_message(update, context, api_response, region)
    await loading_msg.delete()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    name = user.first_name or "there"
    args = context.args

    if args and args[0].startswith("verified_"):
        parts = args[0].split("_")
        if len(parts) >= 3:
            region = parts[1]
            uid = parts[2]
            
            # Send verification message to user
            await update.message.reply_text(
                text=f"*✅ Verification complete for {name}!*\n\n*Processing like request...*",
                parse_mode='Markdown'
            )
            
            loading_msg = await update.message.reply_text(
                text="*⏳ Sending likes...*",
                parse_mode='Markdown'
            )
            
            # Save verification and automatically send like
            save_verified_user(user_id, uid, region)
            
            api_response = await call_like_api(region, uid)
            if "error" in api_response:
                await loading_msg.edit_text(f"*⚠️ API error:*\n`{api_response['error']}`", parse_mode='Markdown')
                return
            
            save_daily_usage(user_id)
            await send_like_success_message(update, context, api_response, region)
            await loading_msg.delete()
            
            # Also notify group
            await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"*✅ Verified & Auto-Liked:* {name} (ID: {user_id})",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("*❌ Invalid verification link format.*", parse_mode='Markdown')
    else:
        await update.message.reply_text(
            "*Welcome to Free Fire VIP Likes Bot!*\n\n"
            "To get likes, use:\n`/like [region] [uid]`\n\n"
            "*Example:* `/like ind 8431487083`\n\n"
            "*Valid regions:* ind, bd, sg, id, me, br, vn, eu, th, na, us, uk",
            parse_mode='Markdown'
        )

async def add_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("*❌ Only the owner can use this command.*", parse_mode='Markdown')
        return

    if not context.args or len(context.args) < 3:
        await update.message.reply_text("*❌ Usage:* `/add user_id days like_limit`", parse_mode='Markdown')
        return

    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
        like_limit = int(context.args[2])
        save_vip_user(user_id, days, like_limit)
        await update.message.reply_text(
            f"*✅ User {user_id} added to VIP for {days} days with {like_limit} likes per day.*", 
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("*❌ Invalid user ID, days or like limit.*", parse_mode='Markdown')

async def remove_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("*❌ Only the owner can use this command.*", parse_mode='Markdown')
        return

    if not context.args:
        await update.message.reply_text("*❌ Usage:* `/remove user_id`", parse_mode='Markdown')
        return

    try:
        user_id = int(context.args[0])
        remove_vip_user(user_id)
        await update.message.reply_text(f"*✅ User {user_id} removed from VIP.*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("*❌ Invalid user ID.*", parse_mode='Markdown')

async def vip_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vip_users = load_vip_users()
    if not vip_users:
        await update.message.reply_text("*ℹ️ No VIP users found.*", parse_mode='Markdown')
        return

    text = "*🌟 VIP Users List:*\n\n"
    for user in vip_users:
        text += f"• *ID:* `{user['id']}` - *Expiry:* `{user['expiry']}` - *Limit:* `{user.get('like_limit', 1)}` likes/day\n"

    await update.message.reply_text(text, parse_mode='Markdown')

async def reset_daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("*❌ Only the owner can use this command.*", parse_mode='Markdown')
        return

    reset_daily_data()
    await update.message.reply_text("*✅ Daily data has been reset.*", parse_mode='Markdown')

# === Shutdown Cleanup ===
def clear_verified_data():
    for file in [VERIFIED_FILE, SHORT_LINK_FILE, USAGE_FILE, VIP_FILE]:
        if os.path.exists(file):
            with open(file, 'w') as f:
                json.dump([], f)
    print("*🧹 Data cleared.*")

def handle_shutdown(signum, frame):
    print("*🚫 Bot stopping...*")
    clear_verified_data()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

# === Start Bot ===
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("like", like_command))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("add", add_vip_command))
    app.add_handler(CommandHandler("remove", remove_vip_command))
    app.add_handler(CommandHandler("viplist", vip_list_command))
    app.add_handler(CommandHandler("resetdaily", reset_daily_command))
    print("*🤖 Free Fire VIP Likes Bot is running...*")
    app.run_polling()
