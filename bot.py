
import json
import pandas as pd
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
from apscheduler.schedulers.background import BackgroundScheduler

CHOOSING_TASK, TYPING_COUNT, CONFIRM_NEXT = range(3)
ADMIN_ID = 6321900094  # Замените на ваш Telegram ID
BOT_TOKEN = "8033295385:AAE4XlejUznJ-4Ue4iyhheNfDfrNXABCYNA"  # Замените на токен от @BotFather

EXCEL_FILE = "daily_report.xlsx"
USER_FILE = "users.json"
TASKS = [
    "Написание претензий",
    "Написание иска",
    "Посещение судебного заседания",
    "Ознакомление с судебной экспертизой"
]

def init_excel():
    try:
        pd.read_excel(EXCEL_FILE)
    except FileNotFoundError:
        df = pd.DataFrame(columns=["Дата", "Юрист", "ID", "Задача", "Количество"])
        df.to_excel(EXCEL_FILE, index=False)

def load_users():
    try:
        with open(USER_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user(user_id, full_name):
    users = load_users()
    users[str(user_id)] = full_name
    with open(USER_FILE, "w") as f:
        json.dump(users, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.full_name)

    keyboard = [[KeyboardButton(task)] for task in TASKS]
    await update.message.reply_text(
        "Выберите задачу:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CHOOSING_TASK

async def choose_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["task"] = update.message.text
    await update.message.reply_text(f"Сколько задач '{update.message.text}' вы выполнили?")
    return TYPING_COUNT

async def type_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите положительное число.")
        return TYPING_COUNT

    user = update.effective_user
    username = user.full_name
    user_id = user.id
    task = context.user_data["task"]
    today = datetime.now().date()

    df = pd.read_excel(EXCEL_FILE)
    new_row = {
        "Дата": today,
        "Юрист": username,
        "ID": user_id,
        "Задача": task,
        "Количество": count
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

    keyboard = [[KeyboardButton("✅ Да"), KeyboardButton("❌ Нет")]]
    await update.message.reply_text("Результативность записана. Добавить ещё задачу?",
                                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CONFIRM_NEXT

async def confirm_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "да" in text:
        keyboard = [[KeyboardButton(task)] for task in TASKS]
        await update.message.reply_text("Выберите задачу:",
                                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return CHOOSING_TASK
    else:
        await update.message.reply_text("Спасибо! До завтра.")
        return ConversationHandler.END

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text="⏰ Напоминание: не забудьте заполнить результативность за сегодня!"
            )
        except Exception as e:
            print(f"Ошибка отправки напоминания {user_id}: {e}")

async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    df = pd.read_excel(EXCEL_FILE)
    now = datetime.now()
    current_month = now.month

    if user.id == ADMIN_ID:
        if context.args:
            name_filter = " ".join(context.args)
            df = df[df['Юрист'].str.contains(name_filter, case=False, na=False)]
        df = df[pd.to_datetime(df['Дата']).dt.month == current_month]
    else:
        df = df[(df['ID'] == user.id) & (pd.to_datetime(df['Дата']).dt.month == current_month)]

    if df.empty:
        await update.message.reply_text("Нет данных для отображения.")
    else:
        file_path = f"stat_{user.id}.xlsx"
        df.to_excel(file_path, index=False)
        await update.message.reply_document(open(file_path, "rb"), filename="stats.xlsx")

def main():
    init_excel()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_task)],
            TYPING_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, type_count)],
            CONFIRM_NEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_next)]
        },
        fallbacks=[]
    )
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("stats", statistics))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminder, "cron", hour=17, minute=0, args=[application.bot])
    scheduler.start()

    application.run_polling()

if __name__ == "__main__":
    main()
