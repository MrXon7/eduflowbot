# EduFlow / Maktab Jadvali Telegram Bot

Render.com da bepul tier'da 24/7 ishlashga mo'ljallangan, referal (taklif) tizimiga va Admin boshqaruviga ega Telegram bot.

## 📋 Vazifasi va Imkoniyatlari
- Har bir yangi foydalanuvchiga unikal taklif havolasi (`/invite`) beriladi.
- Foydalanuvchi 10 ta do'stini taklif qilgandan so'ng dasturga kirish huquqi (`can_access = True`) ochiladi.
- Foydalanuvchi `/status` orqali qancha odam taklif qilgani va qancha qolganini kuzatishi mumkin.
- Ruxsat berilgach, `/login` orqali Mini App (Flutter web app) ga yo'naltiriladi.
- **Admin paneli**: Admin ID (`5865675953`) uchun cheksiz kirish huquqi va `/users`, `/stats` komandalari.
- Render.com uxlab qolmasligi uchun Flask veb-server va `keep_alive` fon xizmati bilan ta'minlangan.

## 📁 Loyiha Tuzilmasi

```
eduflowbot/
├── app.py                 # Asosiy Telegram bot va Flask server kodi (Admin + User)
├── keep_alive.py          # Render uxlab qolmasligi uchun ping yuboruvchi skript
├── requirements.txt       # Kerakli Python kutubxonalari
├── runtime.txt            # Render uchun Python versiyasi (3.10.14)
├── .gitignore             # Git istisno fayllari
├── data/
│   └── users.json         # Foydalanuvchilar ma'lumotlar bazasi (JSON)
└── README.md              # Qo'llanma
```

## 🤖 Bot Komandalari

### Umumiy komandalar:
- `/start` - Botni ishga tushirish (yoki referal link orqali ro'yxatdan o'tish)
- `/invite` - Shaxsiy taklif linkini olish
- `/login` - Mini App havolasini olish (ruxsat berilganlar va admin uchun)
- `/status` - Takliflar holati va ruxsatni tekshirish

### 👑 Maxsus Admin komandalari (Faqat ID: `5865675953`):
- `/users` - Barcha foydalanuvchilar ro'yxati (ID, Username, Takliflar soni, Ruxsati, Taklif qilgan odami)
- `/stats` - Bot statistikasi (Jami userlar, Ruxsati borlar, 10+ taklif qilganlar, Jami takliflar)

## 🚀 Render.com ga Joylash (Deploy)

### 1. GitHub repozitoriyaga yuklash
```bash
git init
git add .
git commit -m "Add admin functionality for user 5865675953"
git branch -M main
git remote add origin https://github.com/USERNAME/eduflowbot.git
git push -u origin main
```

### 2. Render.com da sozlash
1. [Render Dashboard](https://dashboard.render.com/) ga kiring.
2. **New +** -> **Web Service** ni tanlang.
3. GitHub repozitoriyangizni ulang.
4. Quyidagi parametrlarni belgilang:
   - **Name**: `eduflow-bot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
5. **Environment Variables** bo'limida quyidagilarni kiriting:
   - `TELEGRAM_TOKEN`: `@BotFather` dan olingan bot tokeni
   - `ADMIN_ID`: `5865675953` (ixtiyoriy, default holatda ham o'rnatilgan)
   - `MINI_APP_URL`: Flutter ilovangiz havolasi (masalan: `https://your-app.web.app`)
   - `PYTHON_VERSION`: `3.10.14`
   - `RENDER_EXTERNAL_URL`: Render servisingiz URL manzili (masalan: `https://eduflow-bot.onrender.com`)

## 💻 Mahalliy Muhitda Sinash (Local)

```bash
# Virtual muhit yaratish
python -m venv venv

# Virtual muhitni faollashtirish
# Windows (PowerShell / CMD):
venv\Scripts\activate

# Paketlarni o'rnatish
pip install -r requirements.txt

# Environment o'zgaruvchisini o'rnatish (Windows PowerShell):
$env:TELEGRAM_TOKEN="SIZNING_BOT_TOKENINGIZ"
$env:ADMIN_ID="5865675953"
$env:MINI_APP_URL="https://your-app.web.app"

# Botni ishga tushirish
python app.py
```
