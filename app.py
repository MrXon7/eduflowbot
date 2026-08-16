import json
import os
import logging
from datetime import datetime
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from keep_alive import keep_alive

# ============ KONFIGURATSIYA ============
BOT_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID', '5865675953')
INVITE_LIMIT = 1
MINI_APP_URL = os.environ.get('MINI_APP_URL', 'https://your-app.web.app')

# ============ LOGGING ============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ ADMIN TEKSHIRISH ============
def is_admin(user_id):
    """Foydalanuvchi admin ekanligini tekshirish"""
    return str(user_id) == str(ADMIN_ID)

# ============ FLASK APP (Render uchun) ============
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return jsonify({
        "status": "ok",
        "message": "Telegram bot is running"
    })

@flask_app.route('/health')
def health():
    return jsonify({"status": "healthy"})

# ============ MA'LUMOTLAR BAZASI (JSON) ============
def load_users():
    """Foydalanuvchi ma'lumotlarini JSON fayldan o'qish"""
    try:
        os.makedirs('data', exist_ok=True)
        if not os.path.exists('data/users.json'):
            return {"users": {}}
        with open('data/users.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"users": {}}

def save_users(users):
    """Foydalanuvchi ma'lumotlarini JSON faylga yozish"""
    os.makedirs('data', exist_ok=True)
    with open('data/users.json', 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def get_user(user_id):
    """Foydalanuvchini olish"""
    users = load_users()
    return users["users"].get(str(user_id))

def update_user(user_id, data):
    """Foydalanuvchini yangilash"""
    users = load_users()
    str_id = str(user_id)
    if str_id not in users["users"]:
        users["users"][str_id] = {}
    users["users"][str_id].update(data)
    save_users(users)
    return users["users"][str_id]

# ============ BOT KOMANDALARI ============

async def handle_invite_payload(update: Update, context: ContextTypes.DEFAULT_TYPE, inviter_id: str):
    """ Invite link orqali kelgan foydalanuvchini qayta ishlash """
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name or "NoUsername"
    
    # O'zini taklif qila olmaydi
    if inviter_id == user_id:
        await update.message.reply_text("❌ O'zingizni taklif qila olmaysiz!")
        return

    inviter = get_user(inviter_id)
    if not inviter and not is_admin(inviter_id):
        await update.message.reply_text("❌ Taklif qilgan foydalanuvchi topilmadi!")
        return

    user = get_user(user_id)
    if user is None:
        # Yangi foydalanuvchini ro'yxatdan o'tkazish
        is_user_admin = is_admin(user_id)
        update_user(user_id, {
            "invite_count": 0,
            "can_access": True if is_user_admin else False,
            "username": username,
            "invited_by": inviter_id,
            "created_at": datetime.utcnow().isoformat()
        })
        logger.info(f"🆕 Yangi foydalanuvchi: @{username} ({user_id}) taklif orqali qo'shildi")

        # Inviterning hisobini oshirish (agar inviter bazada bo'lsa)
        if inviter:
            new_count = inviter.get("invite_count", 0) + 1
            update_user(inviter_id, {"invite_count": new_count})
            
            # 10 ta bo'lsa, can_access = true
            if new_count >= INVITE_LIMIT:
                update_user(inviter_id, {"can_access": True})
                logger.info(f"🎉 {inviter_id} {INVITE_LIMIT} ta taklif qildi! Kirish huquqi ochildi.")
                
                # Inviterga xabar yuborish
                try:
                    await context.bot.send_message(
                        chat_id=int(inviter_id),
                        text=(
                            f"🎉 Tabriklaymiz! Siz {INVITE_LIMIT} ta odam taklif qildingiz!\n"
                            f"✅ Dasturga kirish huquqi ochildi!\n\n"
                            f"🔗 /login - Dasturni ochish"
                        )
                    )
                except Exception as e:
                    logger.error(f"Xabar yuborishda xatolik: {e}")
        
        inviter_username = inviter.get("username", "Admin" if is_admin(inviter_id) else "Noma lum") if inviter else "Admin"
        await update.message.reply_text(
            f"✅ Siz muvaffaqiyatli ro'yxatdan o'tdingiz!\n"
            f"👤 Taklif qilgan: @{inviter_username}\n\n"
            f"🔗 /invite - O'z taklif linkingizni olish\n"
            f"📊 /status - Holatingizni ko'rish"
        )
    else:
        # Foydalanuvchi allaqachon ro'yxatdan o'tgan
        if is_admin(user_id) or user.get("can_access", False):
            await update.message.reply_text(
                f"👋 Qayta xush kelibsiz, @{username}!\n"
                f"✅ Sizda dasturga kirish huquqi bor!\n\n"
                f"🔗 /login - Dasturni ochish\n"
                f"📊 /status - Holatingizni ko'rish"
            )
        else:
            remaining = INVITE_LIMIT - user.get("invite_count", 0)
            await update.message.reply_text(
                f"👋 Qayta xush kelibsiz, @{username}!\n"
                f"ℹ️ Siz allaqachon ro'yxatdan o'tgansiz.\n"
                f"📊 Takliflaringiz: {user.get('invite_count', 0)} ta. Yana {remaining} ta kerak.\n\n"
                f"🔗 /invite - Taklif linki olish\n"
                f"📊 /status - Holatingizni ko'rish"
            )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /start - Botni ishga tushirish yoki taklif havolasini qabul qilish """
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name or "NoUsername"
    
    # Deep linking argumenti tekshiruvi (masalan, /start invite_123456)
    if context.args and len(context.args) > 0 and context.args[0].startswith("invite_"):
        inviter_id = context.args[0].replace("invite_", "")
        await handle_invite_payload(update, context, inviter_id)
        return

    user = get_user(user_id)
    
    if user is None:
        # Yangi foydalanuvchi
        is_user_admin = is_admin(user_id)
        update_user(user_id, {
            "invite_count": 0,
            "can_access": True if is_user_admin else False,
            "username": username,
            "created_at": datetime.utcnow().isoformat()
        })
        logger.info(f"🆕 Yangi foydalanuvchi: @{username} ({user_id})")
        user = get_user(user_id)
    
    # Admin bo'lsa maxsus start paneli
    if is_admin(user_id):
        mini_app_link = f"{MINI_APP_URL}?userId={user_id}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Dasturni ochish (Admin)", url=mini_app_link)]
        ])
        await update.message.reply_text(
            f"👑 Xush kelibsiz, Admin @{username}!\n\n"
            f"Sizda dasturga to'liq va cheksiz kirish huquqi mavjud.\n\n"
            f"🛠 Maxsus Admin komandalari:\n"
            f"👥 /users - Barcha foydalanuvchilar ro'yxati\n"
            f"📊 /stats - Bot umumiy statistikasi\n\n"
            f"📌 Umumiy komandalar:\n"
            f"🔗 /login - Dasturni ochish\n"
            f"📨 /invite - Taklif linki olish\n"
            f"📈 /status - Holatingizni ko'rish",
            reply_markup=keyboard
        )
        return

    if user.get("can_access", False):
        await update.message.reply_text(
            f"✅ Sizda dasturga kirish huquqi bor!\n"
            f"📊 Siz {user.get('invite_count', 0)} ta odam taklif qilgansiz.\n\n"
            f"🔗 /login - Dasturni ochish\n"
            f"📊 /status - Holatingizni ko'rish"
        )
    else:
        remaining = INVITE_LIMIT - user.get("invite_count", 0)
        await update.message.reply_text(
            f"👋 Xush kelibsiz, @{username}!\n\n"
            f"❌ Sizda hali dasturga kirish huquqi yo'q.\n"
            f"📊 Siz {user.get('invite_count', 0)} ta odam taklif qilgansiz.\n"
            f"🎯 Yana {remaining} ta odam taklif qiling!\n\n"
            f"🔗 /invite - Taklif linki olish\n"
            f"📊 /status - Holatingizni ko'rish"
        )

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /invite - Taklif linki yaratish """
    user_id = str(update.effective_user.id)
    user = get_user(user_id)
    
    if user is None:
        await update.message.reply_text("❌ Iltimos, avval /start bosing!")
        return
    
    bot_obj = await context.bot.get_me()
    bot_username = bot_obj.username
    invite_link = f"https://t.me/{bot_username}?start=invite_{user_id}"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Ulashish", url=f"https://t.me/share/url?url={invite_link}&text=Dasturga%20qo%27shiling!")]
    ])
    
    if is_admin(user_id) or user.get("can_access", False):
        await update.message.reply_text(
            f"✅ Siz allaqachon dasturga kira olasiz!\n"
            f"📊 Siz {user.get('invite_count', 0)} ta odam taklif qilgansiz.\n\n"
            f"📨 Taklif linkingiz:\n{invite_link}",
            reply_markup=keyboard
        )
        return
    
    remaining = INVITE_LIMIT - user.get("invite_count", 0)
    await update.message.reply_text(
        f"📨 Taklif linkingiz:\n{invite_link}\n\n"
        f"📊 Siz {user.get('invite_count', 0)} ta odam taklif qilgansiz.\n"
        f"🎯 Yana {remaining} ta kerak.\n\n"
        f"💡 Linkni do'stlaringizga yuboring!",
        reply_markup=keyboard
    )

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /login - Mini App linkini jo'natish """
    user_id = str(update.effective_user.id)
    user = get_user(user_id)
    
    if user is None:
        await update.message.reply_text("❌ Iltimos, avval /start bosing!")
        return
    
    if is_admin(user_id) or user.get("can_access", False):
        mini_app_link = f"{MINI_APP_URL}?userId={user_id}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Dasturni ochish", url=mini_app_link)]
        ])
        
        await update.message.reply_text(
            f"✅ Dasturga kirish huquqingiz bor!\n\n"
            f"📱 Dasturni ochish uchun quyidagi tugmani bosing:",
            reply_markup=keyboard
        )
    else:
        remaining = INVITE_LIMIT - user.get("invite_count", 0)
        await update.message.reply_text(
            f"❌ Sizda hali dasturga kirish huquqi yo'q.\n"
            f"📊 Siz {user.get('invite_count', 0)} ta odam taklif qilgansiz.\n"
            f"🎯 Yana {remaining} ta odam taklif qiling!\n\n"
            f"🔗 /invite - Taklif linki olish"
        )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /status - Foydalanuvchi holatini ko'rsatish """
    user_id = str(update.effective_user.id)
    user = get_user(user_id)
    
    if user is None:
        await update.message.reply_text("❌ Iltimos, avval /start bosing!")
        return
    
    remaining = max(0, INVITE_LIMIT - user.get("invite_count", 0))
    username = user.get('username', 'Noma lum')
    
    if is_admin(user_id):
        status_text = (
            f"👑 ADMIN HOLATI\n"
            f"{'='*30}\n\n"
            f"👤 Admin: @{username}\n"
            f"🆔 ID: {user_id}\n"
            f"✅ Kirish huquqi: CHEKSIZ (ADMIN)\n"
            f"📊 Takliflaringiz: {user.get('invite_count', 0)} ta\n\n"
            f"🛠 Admin komandalari:\n"
            f"👥 /users - Barcha foydalanuvchilar\n"
            f"📊 /stats - Bot statistikasi\n"
            f"🔗 /login - Dasturni ochish"
        )
        await update.message.reply_text(status_text)
        return

    status_text = (
        f"📊 SIZNING HOLATINGIZ\n"
        f"{'='*30}\n\n"
        f"👤 Foydalanuvchi: @{username}\n"
        f"📊 Taklif qilganlar: {user.get('invite_count', 0)}\n"
        f"🎯 Kerak: {INVITE_LIMIT}\n"
        f"📉 Qolgan: {remaining}\n\n"
    )
    
    if user.get("can_access", False):
        status_text += "✅ Dasturga kirish huquqi: BOR\n🔗 /login - Dasturni ochish"
    else:
        status_text += "❌ Dasturga kirish huquqi: YO'Q\n🔗 /invite - Taklif linki olish"
    
    await update.message.reply_text(status_text)

# ============ ADMIN KOMANDALARI ============

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /users - Barcha foydalanuvchilar ro'yxatini ko'rsatish (Admin) """
    user_id = str(update.effective_user.id)
    if not is_admin(user_id):
        await update.message.reply_text("❌ Bu komanda faqat admin uchun!")
        return

    data = load_users()
    users = data.get("users", {})

    if not users:
        await update.message.reply_text("ℹ️ Hozircha hech qanday foydalanuvchi ro'yxatdan o'tmagan.")
        return

    lines = [f"👥 BARCHA FOYDALANUVCHILAR ({len(users)} ta):\n{'='*30}\n"]
    for uid, udata in users.items():
        uname = udata.get("username", "Noma lum")
        inv_cnt = udata.get("invite_count", 0)
        has_access = "✅ Ha" if (udata.get("can_access", False) or is_admin(uid)) else "❌ Yo'q"
        invited_by = udata.get("invited_by", "To'g'ridan-to'g'ri")
        admin_mark = " [👑 ADMIN]" if is_admin(uid) else ""

        line = (
            f"👤 @{uname}{admin_mark}\n"
            f"   🆔 ID: <code>{uid}</code>\n"
            f"   📊 Takliflar: {inv_cnt}\n"
            f"   🔑 Ruxsat: {has_access}\n"
            f"   🔗 Taklif qilgan: {invited_by}\n"
        )
        lines.append(line)

    full_text = ""
    for item in lines:
        if len(full_text) + len(item) > 3800:
            await update.message.reply_text(full_text, parse_mode="HTML")
            full_text = ""
        full_text += item + "\n"

    if full_text:
        await update.message.reply_text(full_text, parse_mode="HTML")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /stats - Bot umumiy statistikasini ko'rsatish (Admin) """
    user_id = str(update.effective_user.id)
    if not is_admin(user_id):
        await update.message.reply_text("❌ Bu komanda faqat admin uchun!")
        return

    data = load_users()
    users = data.get("users", {})

    total_users = len(users)
    access_granted_users = sum(1 for uid, u in users.items() if u.get("can_access", False) or is_admin(uid))
    completed_10_invites = sum(1 for u in users.values() if u.get("invite_count", 0) >= INVITE_LIMIT)
    total_invites = sum(u.get("invite_count", 0) for u in users.values())

    stats_text = (
        f"📊 BOT STATISTIKASI\n"
        f"{'='*30}\n\n"
        f"👥 Jami foydalanuvchilar: {total_users} ta\n"
        f"🔑 Kirish huquqi borlar: {access_granted_users} ta\n"
        f"🎯 10+ ta taklif qilganlar: {completed_10_invites} ta\n"
        f"📨 Jami berilgan takliflar: {total_invites} ta\n"
    )

    await update.message.reply_text(stats_text)

# ============ MAIN ============

def main():
    import threading
    
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN environment variable is not set!")
        print("Xatolik: TELEGRAM_TOKEN environment variable o'rnatilmagan.")
        return
    
    # Flask serverni ishga tushirish (Render uchun port tinglash)
    def run_flask():
        port = int(os.environ.get('PORT', 10000))
        flask_app.run(host='0.0.0.0', port=port, debug=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Keep-alive (uxlab qolmasligi uchun)
    keep_alive()
    
    # Bot application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Komandalarni qo'shish
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("invite", invite))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    logger.info(f"🚀 Bot ishga tushdi! (Admin ID: {ADMIN_ID})")
    application.run_polling()

if __name__ == "__main__":
    main()
