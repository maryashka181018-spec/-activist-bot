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

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
DATA_FILE = "data.json"

(
    WAIT_EVENT_TITLE, WAIT_EVENT_DATE, WAIT_EVENT_LOCATION, WAIT_ROLES,
    WAIT_FIO, WAIT_GROUP, CHOOSE_EVENT, CHOOSE_ROLE,
    WAIT_MEMBER_NAME, WAIT_MEMBER_GROUP, WAIT_CERT_LINK,
) = range(11)

ROLE_DESCRIPTIONS = {
    "Фотограф": (
        "📷 *Фотограф*\n\n"
        "Ты — глаза команды. Твоя задача — поймать живые, красивые моменты мероприятия. "
        "Снимай людей, эмоции, детали. Фото должны рассказывать историю даже без слов."
    ),
    "Видеограф": (
        "🎥 *Видеограф*\n\n"
        "Вы работаете в паре с другим видеографом. Вместе снимаете интересные кадры: "
        "общие планы, крупные планы, динамику события. Думайте как режиссёры — каждый кадр должен цеплять."
    ),
    "Корреспондент": (
        "🎤 *Корреспондент*\n\n"
        "Твоя роль — голос команды. До начала съёмки выйди на камеру и расскажи: "
        "где вы находитесь, что за мероприятие, с кем работаете, какая школа или организация. "
        "Также берёшь интервью у участников и гостей."
    ),
    "Ответственный": (
        "📋 *Ответственный (сценарист)*\n\n"
        "Ты — мозг команды на мероприятии. Следишь за тем, чтобы:\n"
        "• фотограф снимал нужные моменты\n"
        "• корреспондент взял нужные интервью и рассказал на камеру о сегодняшнем дне\n"
        "• видеографы, чтоб снимали, не упустили ключевые кадры, не отвлекались\n"
        "• в конце определяешь кто монтирует материал и отправляешь короткий текст о сегодняшнем мероприятии\n\n"
        "Без тебя команда — без руля."
    ),
}

WELCOME_TEXT = (
    "👋 Привет! Это бот медиацентра\n"
    "*Технического колледжа им. Р.Н. Ашуралиева*\n\n"
    "Мы — команда, которая снимает, пишет и создаёт контент о жизни колледжа. "
    "Каждый участник важен и у каждого своя роль:\n\n"
    "📷 *Фотограф* — ловит красивые живые моменты\n"
    "🎥 *Видеограф* — снимает интересные кадры в паре\n"
    "🎤 *Корреспондент* — рассказывает на камеру о мероприятии и берёт интервью\n"
    "📋 *Ответственный* — контролирует всю команду на месте. Он отвечает за это мероприятие\n\n"
    "Здесь ты можешь записаться на мероприятие и выбрать свою роль. Вперёд! 🚀"
)


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"events": [], "members": [], "cert_link": ""}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "members" not in data:
        data["members"] = []
    if "cert_link" not in data:
        data["cert_link"] = ""
    return data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def next_event_id(data):
    ids = [e["id"] for e in data["events"]]
    return max(ids) + 1 if ids else 1

def is_admin(user_id):
    return user_id in ADMIN_IDS

def find_member(data, fio):
    fio_clean = fio.strip().lower()
    for m in data["members"]:
        if m["name"].strip().lower() == fio_clean:
            return m
    return None


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        data = load_data()
        cert = data.get("cert_link", "") or "не указана"
        kb = [
            [InlineKeyboardButton("➕ Добавить мероприятие", callback_data="admin_add")],
            [InlineKeyboardButton("📋 Список мероприятий", callback_data="admin_list")],
            [InlineKeyboardButton("👥 Список активистов", callback_data="admin_members")],
            [InlineKeyboardButton("➕ Добавить активиста", callback_data="admin_add_member")],
            [InlineKeyboardButton("🔗 Изменить ссылку на справку", callback_data="admin_cert_link")],
            [InlineKeyboardButton("📥 Выгрузить CSV", callback_data="admin_export")],
        ]
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}! Вы в режиме организатора.\n\n"
            f"🔗 Текущая ссылка на справку: {cert}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    else:
        kb = [[InlineKeyboardButton("📅 Записаться на мероприятие", callback_data="signup_start")]]
        await update.message.reply_text(WELCOME_TEXT, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ── Ссылка на справку ────────────────────────────────────────────────────────
async def admin_cert_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    current = data.get("cert_link", "") or "не указана"
    await query.message.reply_text(
        f"🔗 Текущая ссылка: {current}\n\nВведите новую ссылку на справку:"
    )
    return WAIT_CERT_LINK

async def got_cert_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    data = load_data()
    data["cert_link"] = link
    save_data(data)
    await update.message.reply_text(f"✅ Ссылка обновлена!\n{link}")
    return ConversationHandler.END


# ── Добавить мероприятие ──────────────────────────────────────────────────────
async def admin_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data.clear()
    await query.message.reply_text("📝 Введите название мероприятия:")
    return WAIT_EVENT_TITLE

async def got_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["title"] = update.message.text.strip()
    await update.message.reply_text("📅 Введите дату и время:\n_(например: 25 апреля, 14:00)_", parse_mode="Markdown")
    return WAIT_EVENT_DATE

async def got_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["date"] = update.message.text.strip()
    await update.message.reply_text("📍 Введите место:")
    return WAIT_EVENT_LOCATION

async def got_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["location"] = update.message.text.strip()
    ctx.user_data["roles"] = []
    await update.message.reply_text(
        "👥 Добавьте роли в формате:\n`Фотограф: 1`\n`Видеограф: 2`\n`Корреспондент: 1`\n`Ответственный: 1`\n\nКаждую роль с новой строки. Затем /done",
        parse_mode="Markdown"
    )
    return WAIT_ROLES

async def got_roles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    for line in update.message.text.strip().splitlines():
        if ":" in line:
            parts = line.split(":", 1)
            try:
                ctx.user_data.setdefault("roles", []).append({
                    "name": parts[0].strip(),
                    "total": int(parts[1].strip()),
                    "signups": []
                })
            except ValueError:
                pass
    return WAIT_ROLES

async def done_roles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    roles = ctx.user_data.get("roles", [])
    if not roles:
        await update.message.reply_text("❌ Нужна хотя бы одна роль.")
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
        f"✅ Мероприятие добавлено!\n\n*{event['title']}*\n📅 {event['date']}\n📍 {event['location']}\n👥 Роли:\n{roles_text}",
        parse_mode="Markdown"
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ── Добавить активиста ────────────────────────────────────────────────────────
async def admin_add_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("👤 Введите ФИО активиста:")
    return WAIT_MEMBER_NAME

async def got_member_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["member_name"] = update.message.text.strip()
    await update.message.reply_text("🎓 Введите группу:")
    return WAIT_MEMBER_GROUP

async def got_member_group(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = ctx.user_data["member_name"]
    group = update.message.text.strip()
    data = load_data()
    if find_member(data, name):
        await update.message.reply_text(f"⚠️ *{name}* уже есть в списке.", parse_mode="Markdown")
    else:
        data["members"].append({"name": name, "group": group})
        save_data(data)
        await update.message.reply_text(f"✅ *{name}* ({group}) добавлен!", parse_mode="Markdown")
    ctx.user_data.clear()
    return ConversationHandler.END


# ── Список активистов ─────────────────────────────────────────────────────────
async def admin_members(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    if not data["members"]:
        await query.message.reply_text("Список активистов пуст.")
        return
    text = "👥 *Список активистов:*\n\n"
    for i, m in enumerate(data["members"], 1):
        text += f"{i}. {m['name']} — {m['group']}\n"
    await query.message.reply_text(text, parse_mode="Markdown")


# ── Список мероприятий ────────────────────────────────────────────────────────
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
            names = ", ".join(s["fio"] for s in r["signups"]) or "—"
            roles_text += f"\n  *{r['name']}* ({len(r['signups'])}/{r['total']}): {names}"
        kb = [[InlineKeyboardButton("🗑 Закрыть мероприятие", callback_data=f"admin_close_{ev['id']}")]]
        await query.message.reply_text(
            f"📌 *{ev['title']}*\n📅 {ev['date']}\n📍 {ev['location']}\n"
            f"👥 Записалось: {total_signed}/{total_spots}{roles_text}",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
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


# ── Выгрузка CSV ──────────────────────────────────────────────────────────────
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
                writer.writerow([ev["title"], ev["date"], ev["location"], role["name"], role["total"],
                                  s["fio"], s["group"], s.get("username", "—"), s["signed_at"]])
            if not role["signups"]:
                writer.writerow([ev["title"], ev["date"], ev["location"], role["name"], role["total"], "", "", "", ""])
    output.seek(0)
    bio = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    bio.name = "activists.csv"
    await query.message.reply_document(document=bio, filename="activists.csv", caption="📥 Выгрузка записей")


# ── Запись активиста ──────────────────────────────────────────────────────────
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
        await query.message.reply_text("😔 Все места заняты!")
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(f"{r['name']} ({len(r['signups'])}/{r['total']})", callback_data=f"role_{r['name']}")] for r in available]
    await query.message.reply_text(
        f"*{ev['title']}*\n📅 {ev['date']}\n📍 {ev['location']}\n\nВыберите роль:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
    )
    return CHOOSE_ROLE

async def choose_role(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    role_name = query.data[len("role_"):]
    ctx.user_data["role"] = role_name
    desc = ROLE_DESCRIPTIONS.get(role_name, f"🎭 *{role_name}*")
    await query.message.reply_text(desc, parse_mode="Markdown")
    await query.message.reply_text("✏️ Введите ваше ФИО (Фамилия Имя или Фамилия Имя Отчество):")
    return WAIT_FIO

async def got_fio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    fio = update.message.text.strip()
    ctx.user_data["fio"] = fio
    data = load_data()
    if not find_member(data, fio):
        for admin_id in ADMIN_IDS:
            try:
                await update.get_bot().send_message(
                    chat_id=admin_id,
                    text=f"⚠️ Активист *{fio}* не найден в списке, но пытается записаться.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
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
        await update.message.reply_text("❌ Мероприятие не найдено.")
        return ConversationHandler.END
    role = next((r for r in ev["roles"] if r["name"] == role_name), None)
    if not role:
        await update.message.reply_text("❌ Роль не найдена.")
        return ConversationHandler.END
    if len(role["signups"]) >= role["total"]:
        await update.message.reply_text("😔 Место уже занято. Попробуйте другую роль — /start")
        return ConversationHandler.END
    if any(s.get("telegram_id") == user.id for s in role["signups"]):
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

    cert_link = data.get("cert_link", "")
    cert_text = (
        f"\n\n📄 Справка-подтверждение об участии будет доступна по ссылке:\n{cert_link}"
        if cert_link else
        "\n\n📄 Справка-подтверждение будет доступна после мероприятия."
    )

    await update.message.reply_text(
        f"✅ *Вы записаны!*\n\n"
        f"📌 {ev['title']}\n"
        f"📅 {ev['date']}\n"
        f"📍 {ev['location']}\n"
        f"🎭 Роль: *{role_name}*\n"
        f"👤 {fio}, {group}\n\n"
        f"⏳ Ожидайте. Будьте на паре — руководитель медиацентра придёт и отпросит вас с занятия."
        f"{cert_text}",
        parse_mode="Markdown"
    )
    ctx.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Нажмите /start чтобы начать заново.")
    ctx.user_data.clear()
    return ConversationHandler.END


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    cert_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_cert_link, pattern="^admin_cert_link$")],
        states={WAIT_CERT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_cert_link)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
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
    member_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_member, pattern="^admin_add_member$")],
        states={
            WAIT_MEMBER_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_member_name)],
            WAIT_MEMBER_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_member_group)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
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
    app.add_handler(cert_conv)
    app.add_handler(add_conv)
    app.add_handler(member_conv)
    app.add_handler(signup_conv)
    app.add_handler(CallbackQueryHandler(admin_list, pattern="^admin_list$"))
    app.add_handler(CallbackQueryHandler(admin_members, pattern="^admin_members$"))
    app.add_handler(CallbackQueryHandler(admin_export, pattern="^admin_export$"))
    app.add_handler(CallbackQueryHandler(admin_close_event, pattern="^admin_close_"))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
