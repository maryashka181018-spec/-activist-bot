import os
import json
import csv
import io
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "8373024398:AAG9rKnyhgPYfsccuqu_K9oHXHa7iqki1Ow")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "8229166828").split(",")))
DATA_FILE = "data.json"

# ── Состояния диалога ─────────────────────────────────────────────────────────
(
    WAIT_EVENT_TITLE,
    WAIT_EVENT_DATE,
    WAIT_EVENT_LOCATION,
    WAIT_ROLES,
    WAIT_FIO,
    WAIT_GROUP,
    CHOOSE_EVENT,
    CHOOSE_ROLE,
) = range(8)


# ── Работа с данными ──────────────────────────────────────────────────────────
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"events": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def next_event_id(data):
    ids = [e["id"] for e in data["events"]]
    return max(ids) + 1 if ids else 1


# ── Проверка прав ─────────────────────────────────────────────────────────────
def is_admin(user_id):
    return user_id in ADMIN_IDS


# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        kb = [
            [InlineKeyboardButton("➕ Добавить мероприятие", callback_data="admin_add")],
            [InlineKeyboardButton("📋 Список мероприятий", callback_data="admin_list")],
            [InlineKeyboardButton("📥 Выгрузить CSV", callback_data="admin_export")],
        ]
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}! Вы в режиме организатора.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    else:
        kb = [[InlineKeyboardButton("📅 Записаться на мероприятие", callback_data="signup_start")]]
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\nЗдесь можно записаться на мероприятие медиацентра.",
            reply_markup=InlineKeyboardMarkup(kb)
        )


# ── ОРГАНИЗАТОР: добавить мероприятие ─────────────────────────────────────────
async def admin_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data.clear()
    await query.message.reply_text(
        "📝 Введите название мероприятия:\n_(например: Съёмка в Ростелекоме)_",
        parse_mode="Markdown"
    )
    return WAIT_EVENT_TITLE

async def got_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["title"] = update.message.text.strip()
    await update.message.reply_text("📅 Введите дату и время:\n_(например: 25 апреля, 14:00)_", parse_mode="Markdown")
    return WAIT_EVENT_DATE

async def got_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["date"] = update.message.text.strip()
    await update.message.reply_text("📍 Введите место:\n_(например: Ростелеком, ул. Пушкина 10)_", parse_mode="Markdown")
    return WAIT_EVENT_LOCATION

async def got_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["location"] = update.message.text.strip()
    ctx.user_data["roles"] = []
    await update.message.reply_text(
        "👥 Добавьте роли в формате:\n`Фотограф: 1`\n`Видеограф: 2`\n`Корреспондент: 1`\n\n"
        "Каждую роль — с новой строки. Затем нажмите /done",
        parse_mode="Markdown"
    )
    return WAIT_ROLES

async def got_roles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    roles = []
    errors = []
    for line in text.splitlines():
        if ":" in line:
            parts = line.split(":", 1)
            name = parts[0].strip()
            try:
                count = int(parts[1].strip())
                roles.append({"name": name, "total": count, "signups": []})
            except ValueError:
                errors.append(line)
        else:
            errors.append(line)

    if errors:
        await update.message.reply_text(
            f"⚠️ Не удалось распознать строки:\n" + "\n".join(errors) +
            "\n\nПопробуйте ещё раз или нажмите /done чтобы сохранить без них."
        )
        ctx.user_data.setdefault("roles", []).extend(roles)
        return WAIT_ROLES

    ctx.user_data.setdefault("roles", []).extend(roles)
    return await save_event(update, ctx)

async def done_roles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await save_event(update, ctx)

async def save_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    roles = ctx.user_data.get("roles", [])
    if not roles:
        await update.message.reply_text("❌ Нужна хотя бы одна роль. Добавьте роли:")
        return WAIT_ROLES

    data = load_data()
    event = {
        "id": next_event_id(data),
        "title": ctx.user_data["title"],
        "date": ctx.user_data["date"],
        "location": ctx.user_data["location"],
        "roles": roles,
        "created_at": datetime.now().isoformat(),
        "active": True
    }
    data["events"].append(event)
    save_data(data)

    roles_text = "\n".join(f"  • {r['name']}: {r['total']} чел." for r in roles)
    await update.message.reply_text(
        f"✅ Мероприятие добавлено!\n\n"
        f"*{event['title']}*\n"
        f"📅 {event['date']}\n"
        f"📍 {event['location']}\n"
        f"👥 Роли:\n{roles_text}",
        parse_mode="Markdown"
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ── ОРГАНИЗАТОР: список мероприятий ──────────────────────────────────────────
async def admin_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    events = [e for e in data["events"] if e.get("active")]

    if not events:
        await query.message.reply_text("Нет активных мероприятий.")
        return

    for ev in events:
        total_spots = sum(r["total"] for r in ev["roles"])
        total_signed = sum(len(r["signups"]) for r in ev["roles"])
        roles_text = ""
        for r in ev["roles"]:
            signed_names = ", ".join(s["fio"] for s in r["signups"]) or "—"
            roles_text += f"\n  *{r['name']}* ({len(r['signups'])}/{r['total']}): {signed_names}"

        kb = [[InlineKeyboardButton("🗑 Закрыть мероприятие", callback_data=f"admin_close_{ev['id']}")]]
        await query.message.reply_text(
            f"📌 *{ev['title']}*\n"
            f"📅 {ev['date']}\n"
            f"📍 {ev['location']}\n"
            f"👥 Записалось: {total_signed}/{total_spots}{roles_text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )

async def admin_close_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.split("_")[-1])
    data = load_data()
    for ev in data["events"]:
        if ev["id"] == event_id:
            ev["active"] = False
            break
    save_data(data)
    await query.message.reply_text("✅ Мероприятие закрыто.")


# ── ОРГАНИЗАТОР: выгрузка CSV ─────────────────────────────────────────────────
async def admin_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Мероприятие", "Дата", "Место", "Роль", "Мест всего", "ФИО", "Группа", "Telegram", "Время записи"])

    for ev in data["events"]:
        for role in ev["roles"]:
            for s in role["signups"]:
                writer.writerow([
                    ev["title"], ev["date"], ev["location"],
                    role["name"], role["total"],
                    s["fio"], s["group"], s.get("username", "—"), s["signed_at"]
                ])
            if not role["signups"]:
                writer.writerow([ev["title"], ev["date"], ev["location"], role["name"], role["total"], "", "", "", ""])

    output.seek(0)
    bio = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    bio.name = "activists.csv"
    await query.message.reply_document(document=bio, filename="activists.csv", caption="📥 Выгрузка записей")


# ── АКТИВИСТ: запись ──────────────────────────────────────────────────────────
async def signup_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    events = [e for e in data["events"] if e.get("active")]

    if not events:
        await query.message.reply_text("😔 Сейчас нет открытых мероприятий. Загляните позже!")
        return ConversationHandler.END

    kb = [[InlineKeyboardButton(f"📌 {ev['title']} — {ev['date']}", callback_data=f"ev_{ev['id']}")] for ev in events]
    await query.message.reply_text("Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(kb))
    return CHOOSE_EVENT

async def choose_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.split("_")[1])
    data = load_data()
    ev = next((e for e in data["events"] if e["id"] == event_id), None)
    if not ev:
        await query.message.reply_text("Мероприятие не найдено.")
        return ConversationHandler.END

    ctx.user_data["event_id"] = event_id
    available = [r for r in ev["roles"] if len(r["signups"]) < r["total"]]

    if not available:
        await query.message.reply_text("😔 К сожалению, все места заняты!")
        return ConversationHandler.END

    kb = [[InlineKeyboardButton(
        f"{r['name']} ({len(r['signups'])}/{r['total']})",
        callback_data=f"role_{r['name']}"
    )] for r in available]

    await query.message.reply_text(
        f"*{ev['title']}*\n📅 {ev['date']}\n📍 {ev['location']}\n\nВыберите роль:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return CHOOSE_ROLE

async def choose_role(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    role_name = query.data[len("role_"):]
    ctx.user_data["role"] = role_name
    await query.message.reply_text("✏️ Введите ваше ФИО (Фамилия Имя Отчество):")
    return WAIT_FIO

async def got_fio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["fio"] = update.message.text.strip()
    await update.message.reply_text("🎓 Введите вашу группу:")
    return WAIT_GROUP

async def got_group(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    group = update.message.text.strip()
    user = update.effective_user
    data = load_data()

    event_id = ctx.user_data["event_id"]
    role_name = ctx.user_data["role"]
    fio = ctx.user_data["fio"]

    ev = next((e for e in data["events"] if e["id"] == event_id), None)
    if not ev:
        await update.message.reply_text("❌ Ошибка: мероприятие не найдено.")
        return ConversationHandler.END

    role = next((r for r in ev["roles"] if r["name"] == role_name), None)
    if not role:
        await update.message.reply_text("❌ Ошибка: роль не найдена.")
        return ConversationHandler.END

    if len(role["signups"]) >= role["total"]:
        await update.message.reply_text("😔 К сожалению, место уже занято. Попробуйте выбрать другую роль — /start")
        return ConversationHandler.END

    # Проверка — не записан ли уже
    already = any(s.get("telegram_id") == user.id for s in role["signups"])
    if already:
        await update.message.reply_text("Вы уже записаны на эту роль!")
        return ConversationHandler.END

    role["signups"].append({
        "telegram_id": user.id,
        "username": f"@{user.username}" if user.username else "—",
        "fio": fio,
        "group": group,
        "signed_at": datetime.now().strftime("%d.%m.%Y %H:%M")
    })
    save_data(data)

    await update.message.reply_text(
        f"✅ *Вы записаны!*\n\n"
        f"📌 {ev['title']}\n"
        f"📅 {ev['date']}\n"
        f"📍 {ev['location']}\n"
        f"🎭 Роль: *{role_name}*\n"
        f"👤 {fio}, {group}\n\n"
        f"Если что-то изменится — напишите организатору.",
        parse_mode="Markdown"
    )
    ctx.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Нажмите /start чтобы начать заново.")
    ctx.user_data.clear()
    return ConversationHandler.END


# ── Запуск ────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Диалог добавления мероприятия (для организатора)
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add, pattern="^admin_add$")],
        states={
            WAIT_EVENT_TITLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_title)],
            WAIT_EVENT_DATE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, got_date)],
            WAIT_EVENT_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_location)],
            WAIT_ROLES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_roles),
                CommandHandler("done", done_roles),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Диалог записи (для активиста)
    signup_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(signup_start, pattern="^signup_start$")],
        states={
            CHOOSE_EVENT: [CallbackQueryHandler(choose_event, pattern="^ev_")],
            CHOOSE_ROLE:  [CallbackQueryHandler(choose_role, pattern="^role_")],
            WAIT_FIO:     [MessageHandler(filters.TEXT & ~filters.COMMAND, got_fio)],
            WAIT_GROUP:   [MessageHandler(filters.TEXT & ~filters.COMMAND, got_group)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_conv)
    app.add_handler(signup_conv)
    app.add_handler(CallbackQueryHandler(admin_list, pattern="^admin_list$"))
    app.add_handler(CallbackQueryHandler(admin_export, pattern="^admin_export$"))
    app.add_handler(CallbackQueryHandler(admin_close_event, pattern="^admin_close_"))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
