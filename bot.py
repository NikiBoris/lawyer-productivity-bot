
import json
import pandas as pd
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
from apscheduler.schedulers.background import BackgroundScheduler

# Константы
TASK_SELECT, TASK_COUNT = range(2)
ADMIN_ID = 6321900094  # <-- ЗАМЕНИ НА СВОЙ TELEGRAM ID
BOT_TOKEN = "8033295385:AAE4XlejUznJ-4Ue4iyhheNfDfrNXABCYNA"  # <-- ЗАМЕНИ НА ТОКЕН ОТ BotFather

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
        df = pd.DataFrame(columns=["Дата", "Юрист", "Задача", "Количество"])
        df.to_excel(EXCEL_FILE, index=False)

def load_users():
    try:
        with open(USER_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        with open(USER_FILE, "w") as f:
            json.dump(users, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    keyboard = [[task] for task in TASKS]
    await update.message.reply_text(
        "Выберите задачу:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return TASK_SELECT

async def handle_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = update.message.text
    context.user_data["task"] = task
    await update.message.reply_text(f"Сколько задач '{task}' вы выполнили?")
    return TASK_COUNT

async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        if count < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите, пожалуйста, положительное число.")
        return TASK_COUNT

    username = update.effective_user.full_name
    task = context.user_data["task"]
    today = datetime.now().date()

    df = pd.read_excel(EXCEL_FILE)
    df = pd.concat([df, pd.DataFrame([{
        "Дата": today,
        "Юрист": username,
        "Задача": task,
        "Количество": count
    }])], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

    await update.message.reply_text("Результативность записана. Спасибо!")
    return ConversationHandler.END

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="⏰ Не забудьте заполнить результативность за сегодня!"
            )
        except Exception as e:
            print(f"Ошибка при отправке напоминания {user_id}: {e}")

async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    df = pd.read_excel(EXCEL_FILE)
    today = datetime.now().date()
    daily_df = df[df["Дата"] == today]

    if not daily_df.empty:
        file_path = f"report_{today}.xlsx"
        daily_df.to_excel(file_path, index=False)
        await context.bot.send_document(chat_id=ADMIN_ID, document=open(file_path, "rb"),
                                        filename=file_path, caption="Ежедневный отчёт")
    else:
        await context.bot.send_message(chat_id=ADMIN_ID, text="Нет данных за сегодня.")

async def send_monthly_report(context: ContextTypes.DEFAULT_TYPE):
    df = pd.read_excel(EXCEL_FILE)
    now = datetime.now()
    monthly_df = df[(pd.to_datetime(df["Дата"]).dt.month == now.month)]

    if not monthly_df.empty:
        file_path = f"monthly_report_{now.strftime('%Y_%m')}.xlsx"
        monthly_df.to_excel(file_path, index=False)
        await context.bot.send_document(chat_id=ADMIN_ID, document=open(file_path, "rb"),
                                        filename=file_path, caption="Ежемесячный отчёт")
    else:
        await context.bot.send_message(chat_id=ADMIN_ID, text="Нет данных за месяц.")

def main():
    init_excel()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TASK_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task)],
            TASK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity)]
        },
        fallbacks=[]
    )
    application.add_handler(conv_handler)

    scheduler = BackgroundScheduler()
    scheduler.add_job(send_reminder, "cron", hour=17, minute=45, args=[application.bot])
    scheduler.add_job(send_daily_report, "cron", hour=18, minute=0, args=[application.bot])
    scheduler.add_job(send_monthly_report, "cron", day=1, hour=9, minute=0, args=[application.bot])
    scheduler.start()

    application.run_polling()

if __name__ == "__main__":
    main()
