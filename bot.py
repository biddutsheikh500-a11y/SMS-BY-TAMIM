# ==============================================================================
# 🤖 TeleHost - Real-Time Telegram Auto Hosting & Direct Download Link Bot
# Language: Python 3.10+
# Libraries: python-telegram-bot (v20+), aiohttp, aiofiles
# ==============================================================================
# 📌 FEATURES:
# 1. 🖼️ Direct Download Link Creator: Send any picture/file -> get https://tamim.com/d/pic1
# 2. 🌐 Webpage Auto-Hosting: Send .html -> get live webpage at https://tamim.com/h/portfolio
# 3. ✏️ Custom URL Slug: Customize any link with an inline button or /seturl command
# 4. 🔘 100% Keyboard Buttons: Persistent Reply Keyboard + Rich Inline Keyboards
# ==============================================================================

import os
import re
import sys
import uuid
import json
import logging
import asyncio
from typing import Dict, Any
from aiohttp import web
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("TeleHostBot")

# --- Environment Configuration ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "9030460416:AAGByGtk9chMPcpOVgRs6WGsUA5YOamxiWg")
BASE_URL = os.getenv("BASE_URL", "https://tamim.com").rstrip("/")
PORT = int(os.getenv("PORT", 8080))
STORAGE_DIR = os.getenv("STORAGE_DIR", "hosted_files")
DATA_FILE = os.path.join(STORAGE_DIR, "metadata.json")

os.makedirs(STORAGE_DIR, exist_ok=True)
hosted_sites: Dict[str, Dict[str, Any]] = {}

def load_data():
    global hosted_sites
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                hosted_sites = json.load(f)
        except Exception as e:
            logger.error(f"Error loading database: {e}")

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(hosted_sites, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving database: {e}")

# --- Persistent Reply Keyboard (Mobile bottom buttons) ---
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [
            KeyboardButton("🖼️ Create Download Link (ছবি/ফাইল লিংক)"),
            KeyboardButton("🌐 Auto Host Webpage (ওয়েবসাইট হোস্ট)")
        ],
        [
            KeyboardButton("✏️ Customize Slug (কাস্টম লিংক)"),
            KeyboardButton("📂 My Hosted Links (আমার লিংকসমূহ)")
        ],
        [
            KeyboardButton("📊 Server Stats (পরিসংখ্যান)"),
            KeyboardButton("⚙️ Settings (সেটিংস)")
        ]
    ],
    resize_keyboard=True
)

def build_file_inline_keyboard(slug: str, is_webpage: bool) -> InlineKeyboardMarkup:
    prefix = "h" if is_webpage else "d"
    site_url = f"{BASE_URL}/{prefix}/{slug}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌐 ওপেন লিংক (Open)", url=site_url),
            InlineKeyboardButton("📥 ডাউনলোড (Download)", url=f"{site_url}?dl=1")
        ],
        [
            InlineKeyboardButton("✏️ Customize Slug (লিংক পরিবর্তন)", callback_data=f"slug_{slug}"),
            InlineKeyboardButton("📊 স্ট্যাটস", callback_data=f"stat_{slug}")
        ],
        [
            InlineKeyboardButton("📋 লিংক কপি ফরম্যাট", callback_data=f"copy_{slug}"),
            InlineKeyboardButton("🗑️ ফাইল ডিলিট", callback_data=f"del_{slug}")
        ]
    ])

# --- Telegram Bot Command Handlers ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "বন্ধু"
    context.user_data["mode"] = None

    welcome_text = (
        f"👋 হ্যালো <b>{user_name}</b>!\n"
        f"স্বাগতম <b>TeleHost Auto Bot</b>-এ! 🚀\n\n"
        f"🌐 <b>আপনার শর্ট কাস্টম ডোমেইন:</b> <code>{BASE_URL}</code>\n\n"
        f"🔘 <b>নিচের কিবোর্ড বাটনগুলো দিয়ে সহজেই কাজ করুন:</b>\n\n"
        f"1️⃣ <b>[ 🖼️ Create Download Link ]</b>: যেকোনো ছবি বা ফাইলের ছোট ডাইরেক্ট ডাউনলোড লিংক তৈরি করুন।\n"
        f"2️⃣ <b>[ 🌐 Auto Host Webpage ]</b>: HTML ফাইল পাঠিয়ে সরাসরি লাইভ ওয়েবসাইট তৈরি করুন।\n"
        f"3️⃣ <b>[ ✏️ Customize Slug ]</b>: আপনার লিংককে যেমন খুশি নাম দিন (যেমন: <code>{BASE_URL}/d/myphoto</code>)।\n\n"
        f"আপনার পছন্দের অপশনে চাপ দিন 👇"
    )

    await update.message.reply_html(welcome_text, reply_markup=MAIN_KEYBOARD)

async def handle_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "Create Download Link" in text or "ছবি/ফাইল লিংক" in text:
        context.user_data["mode"] = "download"
        await update.message.reply_html(
            "📥 <b>ডাইরেক্ট ডাউনলোড লিংক মোড সক্রিয়!</b>\n\n"
            "এখন যেকোনো <b>ছবি (Photo)</b> বা <b>ফাইল</b> এখানে পাঠান।\n"
            f"তৎক্ষণাৎ <code>{BASE_URL}/d/your-name</code> এর মতো ছোট ও পরিচ্ছন্ন লিংক পাবেন!",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if "Auto Host Webpage" in text or "ওয়েবসাইট হোস্ট" in text:
        context.user_data["mode"] = "webpage"
        await update.message.reply_html(
            "🌐 <b>ওয়েবসাইট অটো হোস্টিং মোড সক্রিয়!</b>\n\n"
            "যেকোনো <b>.html</b> বা <b>.zip</b> ফাইল এখানে পাঠান।\n"
            f"সঙ্গে সঙ্গে তা লাইভ ওয়েবসাইট হিসেবে <code>{BASE_URL}/h/your-name</code> লিংকে চলবে!",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if "Customize Slug" in text or "কাস্টম লিংক" in text:
        await update.message.reply_html(
            "✏️ <b>কাস্টম URL স্লাগ পরিবর্তন করার নিয়ম:</b>\n\n"
            "ফরম্যাট: <code>/seturl [পুরোনো_slug] [নতুন_slug]</code>\n\n"
            f"উদাহরণ: <code>/seturl pic-3k9z myphoto</code>\n"
            f"তাহলে নতুন লিংক হবে: <code>{BASE_URL}/d/myphoto</code>",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if "My Hosted Links" in text or "আমার লিংকসমূহ" in text:
        items = list(hosted_sites.values())[-6:]
        if not items:
            await update.message.reply_html("📂 কোনো ফাইল এখনো হোস্ট করা হয়নি। ছবি বা ফাইল পাঠান!", reply_markup=MAIN_KEYBOARD)
            return

        resp = f"📂 <b>হোস্টকৃত লিংকসমূহ ({len(hosted_sites)}):</b>\n\n"
        btns = []
        for it in items:
            p = "h" if it.get("is_webpage") else "d"
            u = f"{BASE_URL}/{p}/{it['slug']}"
            resp += f"• <b>{it['file_name']}</b>\n  🔗 <a href='{u}'>{u}</a>\n\n"
            btns.append([InlineKeyboardButton(f"🔗 /{p}/{it['slug']}", url=u)])

        await update.message.reply_html(resp, reply_markup=InlineKeyboardMarkup(btns))
        return

    if "Server Stats" in text or "পরিসংখ্যান" in text:
        total_views = sum(i.get("views", 0) for i in hosted_sites.values())
        await update.message.reply_html(
            f"📊 <b>সার্ভার পরিসংখ্যান:</b>\n\n"
            f"• মোট ফাইল/ছবি: <b>{len(hosted_sites)} টি</b>\n"
            f"• মোট ভিউজ/ডাউনলোড: <b>{total_views} বার</b>\n"
            f"• ডোমেইন: <code>{BASE_URL}</code>\n"
            f"• স্ট্যাটাস: <b>অনলাইন (Online 🟢)</b>",
            reply_markup=MAIN_KEYBOARD
        )
        return

    await update.message.reply_html(
        "💡 যেকোনো ছবি বা ফাইল সরাসরি সেন্ড করুন অথবা নিচের কিবোর্ড বাটনগুলো ব্যবহার করুন 👇",
        reply_markup=MAIN_KEYBOARD
    )

async def file_and_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    current_mode = context.user_data.get("mode")

    file_id = None
    file_name = "file"
    mime_type = "application/octet-stream"
    is_webpage = False

    if msg.photo:
        highest_res = msg.photo[-1]
        file_id = highest_res.file_id
        file_name = f"photo_{int(msg.date.timestamp())}.jpg"
        mime_type = "image/jpeg"
        is_webpage = False
    elif msg.document:
        doc = msg.document
        file_id = doc.file_id
        file_name = doc.file_name or "document.bin"
        mime_type = doc.mime_type or "application/octet-stream"
        if file_name.endswith((".html", ".htm")) and current_mode != "download":
            is_webpage = True

    if not file_id:
        return

    if current_mode == "webpage":
        is_webpage = True

    status_msg = await msg.reply_text("⏳ ফাইল রিসিভ ও শর্ট লিংক তৈরি হচ্ছে...")

    try:
        tg_file = await context.bot.get_file(file_id)
        clean_base = re.sub(r'[^a-zA-Z0-9_-]', '-', file_name.split('.')[0]).lower()[:15]
        slug = f"{clean_base or 'file'}-{uuid.uuid4().hex[:4]}"

        save_path = os.path.join(STORAGE_DIR, f"{slug}_{file_name}")
        await tg_file.download_to_drive(custom_path=save_path)

        file_size = os.path.getsize(save_path)
        hosted_sites[slug] = {
            "slug": slug,
            "file_name": file_name,
            "path": save_path,
            "mime_type": mime_type,
            "size": file_size,
            "is_webpage": is_webpage,
            "views": 0,
            "owner": update.effective_user.id
        }
        save_data()

        prefix = "h" if is_webpage else "d"
        short_url = f"{BASE_URL}/{prefix}/{slug}"
        inline_kb = build_file_inline_keyboard(slug, is_webpage)

        header = "🌐 <b>ওয়েবসাইট সফলভাবে হোস্ট হয়েছে!</b>" if is_webpage else "🎉 <b>ডাইরেক্ট ডাউনলোড লিংক তৈরি হয়েছে!</b>"

        caption = (
            f"{header}\n\n"
            f"📁 <b>ফাইলের নাম:</b> <code>{file_name}</code>\n"
            f"⚖️ <b>সাইজ:</b> {file_size / 1024:.1f} KB\n"
            f"🔗 <b>শর্ট কাস্টম URL:</b>\n<a href='{short_url}'>{short_url}</a>\n\n"
            f"👉 <b>লিংক নিজের পছন্দমতো পরিবর্তন করতে:</b> নিচের <b>[✏️ Customize Slug]</b> বাটনে চাপ দিন!"
        )

        await status_msg.delete()
        await msg.reply_html(caption, reply_markup=inline_kb)
        context.user_data["mode"] = None

    except Exception as err:
        logger.error(f"Upload error: {err}")
        await status_msg.edit_text(f"⚠️ ত্রুটি: {str(err)}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("slug_"):
        slug = data.replace("slug_", "")
        site = hosted_sites.get(slug)
        p = "h" if site and site.get("is_webpage") else "d"
        await query.message.reply_html(
            f"✏️ <b>কাস্টম স্লাগ সেট করুন:</b>\n\n"
            f"বর্তমান লিংক: <code>{BASE_URL}/{p}/{slug}</code>\n"
            f"নতুন নাম দিতে কমান্ড লিখুন:\n"
            f"<code>/seturl {slug} your-custom-name</code>"
        )
    elif data.startswith("stat_"):
        slug = data.replace("stat_", "")
        site = hosted_sites.get(slug)
        if site:
            await query.answer(f"📊 ভিউজ/ডাউনলোড: {site.get('views', 0)} বার | সাইজ: {site.get('size', 0)//1024} KB", show_alert=True)
    elif data.startswith("copy_"):
        slug = data.replace("copy_", "")
        site = hosted_sites.get(slug)
        p = "h" if site and site.get("is_webpage") else "d"
        await query.message.reply_html(f"📋 <b>কপি লিংক:</b>\n\n<code>{BASE_URL}/{p}/{slug}</code>")
    elif data.startswith("del_"):
        slug = data.replace("del_", "")
        if slug in hosted_sites:
            target = hosted_sites.pop(slug)
            save_data()
            if os.path.exists(target.get("path", "")):
                try: os.remove(target["path"])
                except Exception: pass
            await query.message.reply_html(f"🗑️ <code>{slug}</code> ডিলিট করা হয়েছে!")

async def seturl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_html("⚠️ ব্যবহার: <code>/seturl [পুরোনো_slug] [নতুন_slug]</code>")
        return

    old_slug = args[0].strip()
    new_slug = re.sub(r'[^a-zA-Z0-9_-]', '-', args[1].strip().lower()).strip("-")

    if new_slug in hosted_sites:
        await update.message.reply_html(f"❌ <b>'{new_slug}'</b> নামটি ইতোমধ্যে ব্যবহৃত!")
        return

    if old_slug in hosted_sites:
        item = hosted_sites.pop(old_slug)
        item["slug"] = new_slug
        hosted_sites[new_slug] = item
        save_data()

        p = "h" if item.get("is_webpage") else "d"
        new_url = f"{BASE_URL}/{p}/{new_slug}"
        await update.message.reply_html(
            f"✅ <b>URL সফলভাবে আপডেট হয়েছে!</b>\n\n🔗 <a href='{new_url}'>{new_url}</a>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 ওপেন নতুন লিংক", url=new_url)]])
        )
    else:
        await update.message.reply_html(f"⚠️ '{old_slug}' সাইট খুঁজে পাওয়া যায়নি!")

# --- Web Server Routes ---
async def serve_download(request: web.Request):
    slug = request.match_info.get("slug")
    site = hosted_sites.get(slug)
    if not site or not os.path.exists(site["path"]):
        return web.Response(text="<h1>404 - File Not Found</h1>", content_type="text/html", status=404)

    site["views"] = site.get("views", 0) + 1
    save_data()

    headers = {"Content-Type": site["mime_type"], "Access-Control-Allow-Origin": "*"}
    if request.query.get("dl") == "1" or not site["mime_type"].startswith("image/"):
        headers["Content-Disposition"] = f'attachment; filename="{site["file_name"]}"'
    else:
        headers["Content-Disposition"] = f'inline; filename="{site["file_name"]}"'

    return web.FileResponse(site["path"], headers=headers)

async def serve_webpage(request: web.Request):
    slug = request.match_info.get("slug")
    site = hosted_sites.get(slug)
    if not site or not os.path.exists(site["path"]):
        return web.Response(text="<h1>404 - Webpage Not Found</h1>", content_type="text/html", status=404)

    site["views"] = site.get("views", 0) + 1
    save_data()

    return web.FileResponse(site["path"], headers={"Content-Type": site["mime_type"] or "text/html; charset=utf-8"})

async def root_index(request: web.Request):
    return web.Response(text=f"⚡ TeleHost Server Active on {BASE_URL}", content_type="text/plain")

async def run_server():
    app = web.Application()
    app.router.add_get("/", root_index)
    app.router.add_get("/d/{slug}", serve_download)
    app.router.add_get("/h/{slug}", serve_webpage)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server active on port {PORT}")

def main():
    load_data()
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start_handler))
    tg_app.add_handler(CommandHandler("seturl", seturl_command))
    tg_app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.AUDIO, file_and_photo_handler))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_text))
    tg_app.add_handler(CallbackQueryHandler(callback_handler))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_server())

    logger.info("🤖 Starting Telegram Bot polling...")
    tg_app.run_polling()

if __name__ == "__main__":
    main()
