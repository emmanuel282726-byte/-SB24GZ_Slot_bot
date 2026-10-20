import os
import io
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import qrcode
from pyzbar.pyzbar import decode
from PIL import Image

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")

def make_qr(data: str) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    buf.name = "qr.png"
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

def make_wifi_qr(ssid: str, password: str, security: str = "WPA") -> io.BytesIO:
    return make_qr(f"WIFI:T:{security};S:{ssid};P:{password};;")

def make_vcard_qr(name: str, phone: str, email: str = "") -> io.BytesIO:
    vcard = (
        "BEGIN:VCARD\nVERSION:3.0\n"
        f"FN:{name}\nTEL:{phone}\nEMAIL:{email}\n"
        "END:VCARD"
    )
    return make_qr(vcard)

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔳 Generate QR", callback_data="qr")],
        [InlineKeyboardButton("📷 Decode QR (send image)", callback_data="decode_info")],
        [InlineKeyboardButton("📶 WiFi QR", callback_data="wifi")],
        [InlineKeyboardButton("👤 vCard QR", callback_data="vcard")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")],
    ])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *SB24GZ Slot QR Bot*!\n\n"
        "Send me any text or URL and I'll return a QR code.\n"
        "Or use the menu below 👇",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Commands:*\n"
        "• Send text → QR code\n"
        "• /wifi SSID | PASSWORD\n"
        "• /vcard Name | Phone | Email\n"
        "• Send QR image → decode\n"
        "• /menu",
        parse_mode="Markdown",
    )

async def menu_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Main menu:", reply_markup=main_menu())

async def about(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🤖 *SB24GZ Slot Bot*\nFree QR generator.\nDeployed on Railway 🚂",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "about":
        return await about(update, ctx)
    texts = {
        "qr": "🔳 Send any *text or URL*.",
        "wifi": "📶 `/wifi MyWiFi | mypassword`",
        "vcard": "👤 `/vcard John Doe | +123 | john@mail.com`",
        "decode_info": "📷 Send a photo of a QR code.",
    }
    await q.edit_message_text(texts.get(q.data, "OK"), parse_mode="Markdown")

async def text_to_qr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return
    try:
        buf = make_qr(text)
        await update.message.reply_photo(
            photo=buf,
            caption=f"✅ QR for: `{text[:80]}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.exception("QR failed")
        await update.message.reply_text(f"⚠️ {e}")

async def wifi_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = " ".join(ctx.args)
    if "|" not in args:
        return await update.message.reply_text("Usage: `/wifi SSID | PASSWORD`", parse_mode="Markdown")
    ssid, pwd = [x.strip() for x in args.split("|", 1)]
    await update.message.reply_photo(photo=make_wifi_qr(ssid, pwd), caption=f"📶 WiFi *{ssid}*", parse_mode="Markdown")

async def vcard_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    parts = [x.strip() for x in " ".join(ctx.args).split("|")]
    if len(parts) < 2:
        return await update.message.reply_text("Usage: `/vcard Name | Phone | Email`", parse_mode="Markdown")
    email = parts[2] if len(parts) > 2 else ""
    await update.message.reply_photo(photo=make_vcard_qr(parts[0], parts[1], email),
                                     caption=f"👤 vCard *{parts[0]}*", parse_mode="Markdown")

async def decode_qr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    data = await file.download_as_bytearray()
    img = Image.open(io.BytesIO(data))
    results = decode(img)
    if not results:
        return await update.message.reply_text("❌ No QR found.")
    texts = "\n".join(f"`{r.data.decode('utf-8', errors='replace')}`" for r in results)
    await update.message.reply_text(f"✅ Decoded:\n{texts}", parse_mode="Markdown")

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN env var missing!")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("wifi", wifi_cmd))
    app.add_handler(CommandHandler("vcard", vcard_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, decode_qr))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_to_qr))
    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
