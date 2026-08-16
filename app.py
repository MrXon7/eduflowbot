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
INVITE_LIMIT = 10
MINI_APP_URL = os.environ.get('MINI_APP_URL', 'https://your-app.web.app')

# ============ LOGGING ============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    if not inviter:
        await update.message.reply_text("❌ Taklif qilgan foydalanuvchi topilmadi!")
        return

    user = get_user(user_id)
    if user is None:
        # Yangi foydalanuvchini ro'yxatdan o'tkazish
        update_user(user_id, {
            "invite_count": 0,
            "can_access": False,
            "username": username,
            "invited_by": inviter_id,
            "created_at": datetime.utcnow().isoformat()
        })
        logger.info(f"🆕 Yangi foydalanuvchi: @{username} ({user_id}) taklif orqali qo'shildi")

        # Inviterning hisobini oshirish
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
        
        await update.message.reply_text(
            f"✅ Siz muvaffaqiyatli ro'yxatdan o'tdingiz!\n"
            f"👤 Taklif qilgan: @{inviter.get('username', 'Noma\'lum')}\n\n"
            f"🔗 /invite - O'z taklif linkingizni olish\n"
            f"📊 /status - Holatingizni ko'rish"
        )
    else:
        # Foydalanuvchi allaqachon ro'yxatdan o'tgan
        if user.get("can_access", False):
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
        update_user(user_id, {
            "invite_count": 0,
            "can_access": False,
            "username": username,
            "created_at": datetime.utcnow().isoformat()
        })
        logger.info(f"🆕 Yangi foydalanuvchi: @{username} ({user_id})")
        user = get_user(user_id)
    
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
    
    if user.get("can_access", False):
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
    
    if user.get("can_access", False):
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
    username = user.get('username', 'Noma\'lum')
    
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
    
    logger.info("🚀 Bot ishga tushdi!")
    application.run_polling()

if __name__ == "__main__":
    main()
