import logging
import json
import asyncio
import schedule
import time
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
USER_DATA_FILE = 'yyyyyyyyyyyyyyyy'
ASSETS_FILE = 'azkar.json'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(data):
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """القائمة الرئيسية للبوت"""
    keyboard = [
        [InlineKeyboardButton("🔔 إعدادات الاشتراك", callback_data='settings_menu')],
        [InlineKeyboardButton("🌟 إختيار شكل الاذكار", callback_data='choose_design')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        " مرحبااً بك في بوت منبه الاذكار اليومي \n\n"
        "يمكنك تفعيل الاشتراك واختيار التصميم الذي يناسبك من القائمة :",
        reply_markup=reply_markup
    )

async def handle_interactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة جميع ضغطات الأزرار"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data

    users = load_json(USER_DATA_FILE)
    assets = load_json(ASSETS_FILE)

    if data == 'settings_menu':
        status = "متصل ✅" if user_id in users else "غير مشترك ❌"
        keyboard = [
            [InlineKeyboardButton("✅ تفعيل الاشتراك", callback_data='sub_on')],
            [InlineKeyboardButton("❌ إلغاء الاشتراك", callback_data='sub_off')],
            [InlineKeyboardButton("🔙 العودة", callback_data='back_to_main')]
        ]
        await query.edit_message_text(f"حالة اشتراكك: {status}\n\nاستخدم الأزرار للتحكم في استقبال الأذكار:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'choose_design':
        preview_id = assets.get("preview_image")
        if not preview_id or len(preview_id) < 10:
            await query.edit_message_text("⚠️ حدث خطأ في قاعدة البيانات.")
            return

        keyboard = [
            [InlineKeyboardButton("نمط 1🤎", callback_data='design_1'), InlineKeyboardButton("نمط 2🤍", callback_data='design_2')],
            [InlineKeyboardButton("نمط 3💙", callback_data='design_3'), InlineKeyboardButton("نمط 4🩷", callback_data='design_4')],
            [InlineKeyboardButton("🔙 العودة", callback_data='back_to_main')]
        ]
        await query.message.delete()
        await context.bot.send_photo(
            chat_id=user_id,
            photo=preview_id,
            caption=" الأنماط المتاحة، اختر النمط الذي تفضله:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == 'sub_on':
        if user_id not in users:
            users[user_id] = "1"
            save_users(users)
            await query.edit_message_text("✅ تم تفعيل الإشتراك بنجاح ، ستصلك الأذكار بشكل يومي.")
        else:
            await query.edit_message_text("أنت مشترك بالفعل ✅")

    elif data == 'sub_off':
        if user_id in users:
            del users[user_id]
            save_users(users)
            await query.edit_message_text("❌ تم إلغاء الإشتراك بنجاح.")
        else:
            await query.edit_message_text("أنت غير مشترك .")

    elif data.startswith('design_'):
        design_num = data.split('_')[1]
        if user_id in users:
            users[user_id] = design_num
            save_users(users)
            await query.message.reply_text(f"✅ تم تغيير شكل الأذكار إلى النمط  ({design_num}).")
        else:
            await query.message.reply_text("⚠️ يرجى تفعيل الاشتراك أولاً من 'إعدادات الاشتراك'.")

    elif data == 'back_to_main':
        keyboard = [[InlineKeyboardButton("🔔 إعدادات الاشتراك", callback_data='settings_menu')],
                    [InlineKeyboardButton("🌟 اختيار شكل الأذكار", callback_data='choose_design')]]
        try:
            await query.edit_message_text("منبه الأذكار ، القائمة الرئيسية:", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await query.message.delete()
            await context.bot.send_message(chat_id=user_id, text="القائمة الرئيسية:", reply_markup=InlineKeyboardMarkup(keyboard))

async def get_photo_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وظيفة للمطور لاستخراج ID الصور"""
    file_id = update.message.photo[-1].file_id
    await update.message.reply_text(f"كود الصورة المستخرج:\n`{file_id}`", parse_mode='MarkdownV2')


async def broadcast_job(type_of_azkar):
    """إرسال الأذكار لجميع المشتركين بناءً على اختيارهم"""
    users = load_json(USER_DATA_FILE)
    assets = load_json(ASSETS_FILE)

    temp_app = Application.builder().token(TOKEN).build()

    for user_id, design_id in users.items():
        try:
            photo_id = assets.get(type_of_azkar, {}).get(design_id)
            if photo_id:
                await temp_app.bot.send_photo(chat_id=user_id, photo=photo_id)
        except Exception as e:
            logging.error(f"فشل الإرسال لـ {user_id}: {e}")

def start_scheduler():
    """تشغيل المنبه في خيط منفصل لضمان عدم توقف البوت"""
    scheduler_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(scheduler_loop)

    schedule.every().day.at("08:04").do(lambda: scheduler_loop.run_until_complete(broadcast_job("morning")))
    schedule.every().day.at("17:26").do(lambda: scheduler_loop.run_until_complete(broadcast_job("evening")))

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == '__main__':
    threading.Thread(target=start_scheduler, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_interactions))
    app.add_handler(MessageHandler(filters.PHOTO, get_photo_id))

    print("🚀 البوت يعمل الآن...")
    app.run_polling()
