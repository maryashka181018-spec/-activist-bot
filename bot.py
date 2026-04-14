import os, json, csv, io, asyncio
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

BOT_TOKEN  = os.getenv("BOT_TOKEN", "")
ADMIN_IDS  = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
GROUP_NAME = os.getenv("GROUP_NAME", "ТК МЕДИА/ПРОФЕССИОНАЛИТЕТ")
DATA_FILE  = "data.json"

(
    WAIT_EVENT_TITLE, WAIT_EVENT_DATE, WAIT_EVENT_LOCATION, WAIT_ROLES,
    WAIT_REG_FIO, WAIT_MEMBER_NAME, WAIT_MEMBER_GROUP,
    WAIT_CERT_LINK, WAIT_GROUP_LINK,
    CHOOSE_EVENT, CHOOSE_ROLE,
    WAIT_REMOVE_COMMENT,
) = range(12)

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
        "• видеографы снимали, не упускали ключевые кадры, не отвлекались\n"
        "• в конце определяешь кто монтирует материал и отправляешь короткий текст о мероприятии\n\n"
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
    "Для начала нужно пройти быструю регистрацию. Введите ваше ФИО:"
)

# ── Данные ────────────────────────────────────────────────────────────────────
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"events": [], "members": [], "cert_link": "", "group_name": GROUP_NAME, "known_users": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        d = json.load(f)
    for k, default in [("members",[]),("cert_link",""),("group_name",GROUP_NAME),("known_users",{})]:
        if k not in d:
            d[k] = default
    return d

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def next_id(data):
    ids = [e["id"] for e in data["events"]]
    return max(ids) + 1 if ids else 1

def is_admin(uid): return uid in ADMIN_IDS

def fio_match(a, b):
    a_parts = a.strip().lower().split()
    b_parts = b.strip().lower().split()
    if len(a_parts) >= 2 and len(b_parts) >= 2:
        return a_parts[0] == b_parts[0] and a_parts[1] == b_parts[1]
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio() > 0.82

def find_member(data, fio):
    for m in data["members"]:
        if fio_match(m["name"], fio):
            return m
    return None

def get_user_reg(data, uid):
    return data["known_users"].get(str(uid))

def is_already_signed_to_event(ev, telegram_id):
    """Проверяет записан ли человек уже на любую роль этого мероприятия."""
    for r in ev["roles"]:
        if any(s["telegram_id"] == telegram_id for s in r["signups"]):
            return True
    return False

def parse_event_datetime(date_str):
    months = {"января":1,"февраля":2,"марта":3,"апреля":4,"мая":5,"июня":6,
              "июля":7,"августа":8,"сентября":9,"октября":10,"ноября":11,"декабря":12}
    try:
        parts = date_str.replace(",", "").split()
        day = int(parts[0])
        month = months.get(parts[1].lower(), 0)
        time_parts = parts[2].split(":") if len(parts) > 2 else ["12","00"]
        hour, minute = int(time_parts[0]), int(time_parts[1])
        year = datetime.now().year
        dt = datetime(year, month, day, hour, minute)
        if dt < datetime.now():
            dt = dt.replace(year=year+1)
        return dt
    except Exception:
        return None

# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        data = load_data()
        cert = data.get("cert_link") or "не указана"
        kb = [
            [InlineKeyboardButton("➕ Добавить мероприятие",   callback_data="admin_add")],
            [InlineKeyboardButton("📋 Список мероприятий",      callback_data="admin_list")],
            [InlineKeyboardButton("👥 Список активистов",       callback_data="admin_members")],
            [InlineKeyboardButton("➕ Добавить активиста",      callback_data="admin_add_member")],
            [InlineKeyboardButton("🔗 Ссылка на справку",       callback_data="admin_cert_link")],
            [InlineKeyboardButton("📥 Выгрузить CSV",           callback_data="admin_export")],
        ]
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}! Режим организатора.\n🔗 Справка: {cert}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return ConversationHandler.END

    data = load_data()
    # Каждый /start — удаляем из known_users, чтобы пройти регистрацию заново
    # Это нужно если активист очистил чат или был удалён из базы
    if str(user.id) in data["known_users"]:
        del data["known_users"][str(user.id)]
        save_data(data)
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown")
    return WAIT_REG_FIO

async def show_main_menu(message, fio):
    kb = [
        [InlineKeyboardButton("📅 Мероприятия",      callback_data="signup_start")],
        [InlineKeyboardButton("📄 Получить справку", callback_data="get_cert")],
    ]
    await message.reply_text(
        f"👋 С возвращением, *{fio}*!\n\nЧто хочешь сделать?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ── Регистрация ───────────────────────────────────────────────────────────────
async def got_reg_fio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    fio = update.message.text.strip()
    user = update.effective_user
    data = load_data()
    member = find_member(data, fio)
    if not member:
        await update.message.reply_text(
            "❌ Вас нет в списке активистов медиацентра.\n\n"
            "Если считаете это ошибкой — обратитесь к руководителю медиацентра."
        )
        return WAIT_REG_FIO
    data["known_users"][str(user.id)] = {
        "fio": member["name"],
        "group": member["group"],
        "telegram_id": user.id,
        "username": f"@{user.username}" if user.username else "—"
    }
    save_data(data)
    await update.message.reply_text(f"✅ Добро пожаловать, *{member['name']}*!", parse_mode="Markdown")
    await show_main_menu(update.message, member["name"])
    return ConversationHandler.END

# ── Справка ───────────────────────────────────────────────────────────────────
async def get_cert(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    cert = data.get("cert_link", "")
    if cert:
        await query.message.reply_text(f"📄 *Справка-подтверждение:*\n{cert}", parse_mode="Markdown")
    else:
        await query.message.reply_text("📄 Ссылка пока не добавлена. Обратитесь к руководителю.")

# ── Ссылка на справку ─────────────────────────────────────────────────────────
async def admin_cert_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    await query.message.reply_text(
        f"Текущая ссылка: {data.get('cert_link') or 'не указана'}\n\nВведите новую:"
    )
    return WAIT_CERT_LINK

async def got_cert_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    data["cert_link"] = update.message.text.strip()
    save_data(data)
    await update.message.reply_text("✅ Ссылка обновлена!")
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
        "👥 Добавьте роли:\n`Фотограф: 1`\n`Видеограф: 2`\n`Корреспондент: 1`\n`Ответственный: 1`\n\nКаждую с новой строки. Затем /done",
        parse_mode="Markdown"
    )
    return WAIT_ROLES

async def got_roles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    for line in update.message.text.strip().splitlines():
        if ":" in line:
            parts = line.split(":", 1)
            try:
                ctx.user_data.setdefault("roles", []).append({
                    "name": parts[0].strip(), "total": int(parts[1].strip()), "signups": []
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
        "id": next_id(data),
        "title": ctx.user_data["title"],
        "date": ctx.user_data["date"],
        "location": ctx.user_data["location"],
        "roles": roles,
        "created_at": datetime.now().isoformat(),
        "active": True,
        "reminders_sent": []
    }
    data["events"].append(event)
    save_data(data)
    roles_text = "\n".join(f"  • {r['name']}: {r['total']} чел." for r in roles)
    await update.message.reply_text(
        f"✅ Мероприятие добавлено!\n\n*{event['title']}*\n📅 {event['date']}\n📍 {event['location']}\n{roles_text}",
        parse_mode="Markdown"
    )
    for uid_str in data.get("known_users", {}):
        try:
            await update.get_bot().send_message(
                chat_id=int(uid_str),
                text=f"🆕 Новое мероприятие!\n\n*{event['title']}*\n📅 {event['date']}\n📍 {event['location']}\n\nЗапишись через /start",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    ctx.user_data.clear()
    return ConversationHandler.END

# ── Список мероприятий (орг) ──────────────────────────────────────────────────
async def admin_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    events = [e for e in data["events"] if e.get("active")]
    if not events:
        await query.message.reply_text("Нет активных мероприятий.")
        return
    for ev in events:
        total = sum(r["total"] for r in ev["roles"])
        signed = sum(len(r["signups"]) for r in ev["roles"])
        await query.message.reply_text(
            f"📌 *{ev['title']}*\n📅 {ev['date']}\n📍 {ev['location']}\n👥 {signed}/{total}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🗑 Закрыть мероприятие", callback_data=f"admin_close_{ev['id']}")
            ]])
        )
        for r in ev["roles"]:
            if not r["signups"]:
                await query.message.reply_text(f"🎭 *{r['name']}* — никто не записался", parse_mode="Markdown")
                continue
            for s in r["signups"]:
                status = "✅" if s.get("approved") else "⏳"
                kb = [[InlineKeyboardButton("❌ Удалить", callback_data=f"remove_{ev['id']}_{r['name']}_{s['telegram_id']}")]]
                if not s.get("approved"):
                    kb[0].insert(0, InlineKeyboardButton("✅ Принять", callback_data=f"approve_{ev['id']}_{r['name']}_{s['telegram_id']}"))
                await query.message.reply_text(
                    f"{status} *{r['name']}*: {s['fio']} — {s['group']}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(kb)
                )

async def approve_signup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, ev_id, role_name, tg_id = query.data.split("_", 3)
    ev_id, tg_id = int(ev_id), int(tg_id)
    data = load_data()
    for ev in data["events"]:
        if ev["id"] == ev_id:
            for r in ev["roles"]:
                if r["name"] == role_name:
                    for s in r["signups"]:
                        if s["telegram_id"] == tg_id:
                            s["approved"] = True
                            save_data(data)
                            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("❌ Удалить", callback_data=f"remove_{ev_id}_{role_name}_{tg_id}")
                            ]]))
                            await query.message.reply_text(f"✅ {s['fio']} подтверждён.")
                            try:
                                await query.get_bot().send_message(
                                    chat_id=tg_id,
                                    text=f"✅ Ваша запись на *{ev['title']}* подтверждена!\n🎭 Роль: {role_name}\n\n"
                                         f"Ожидайте. Будьте на паре — руководитель медиацентра придёт и отпросит вас с занятия.",
                                    parse_mode="Markdown"
                                )
                            except Exception:
                                pass
                            return

async def remove_signup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, ev_id, role_name, tg_id = query.data.split("_", 3)
    ev_id, tg_id = int(ev_id), int(tg_id)
    ctx.user_data["remove_ev_id"] = ev_id
    ctx.user_data["remove_role"] = role_name
    ctx.user_data["remove_tg_id"] = tg_id
    await query.message.reply_text(
        "✏️ Напишите комментарий для активиста (или напишите `-` чтобы не добавлять):"
    )
    return WAIT_REMOVE_COMMENT

async def got_remove_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    comment = update.message.text.strip()
    ev_id = ctx.user_data["remove_ev_id"]
    role_name = ctx.user_data["remove_role"]
    tg_id = ctx.user_data["remove_tg_id"]
    data = load_data()
    for ev in data["events"]:
        if ev["id"] == ev_id:
            for r in ev["roles"]:
                if r["name"] == role_name:
                    removed = [s for s in r["signups"] if s["telegram_id"] == tg_id]
                    r["signups"] = [s for s in r["signups"] if s["telegram_id"] != tg_id]
                    save_data(data)
                    await update.message.reply_text("🗑 Запись удалена. Место освободилось.")
                    if removed:
                        comment_text = f"\n\n💬 Комментарий: {comment}" if comment != "-" else ""
                        try:
                            await update.get_bot().send_message(
                                chat_id=tg_id,
                                text=f"❌ Ваша запись на *{ev['title']}* (роль: {role_name}) отменена.{comment_text}",
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                    ctx.user_data.clear()
                    return ConversationHandler.END
    await update.message.reply_text("Запись не найдена.")
    return ConversationHandler.END

async def admin_close_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ev_id = int(query.data.split("_")[-1])
    data = load_data()
    for ev in data["events"]:
        if ev["id"] == ev_id:
            ev["active"] = False
    save_data(data)
    await query.message.reply_text("✅ Мероприятие закрыто.")

# ── Добавить/удалить активиста ────────────────────────────────────────────────
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

async def admin_members(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    if not data["members"]:
        await query.message.reply_text("Список пуст.")
        return
    text = "👥 *Активисты:*\n\n"
    kb = []
    for i, m in enumerate(data["members"]):
        text += f"{i+1}. {m['name']} — {m['group']}\n"
        kb.append([InlineKeyboardButton(f"❌ {m['name'].split()[0]}", callback_data=f"del_member_{i}")])
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def del_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("_")[-1])
    data = load_data()
    if 0 <= idx < len(data["members"]):
        removed = data["members"].pop(idx)
        # Удаляем из known_users — при следующем /start пройдёт регистрацию заново и получит отказ
        to_delete = [uid for uid, u in data["known_users"].items() if fio_match(u["fio"], removed["name"])]
        for uid in to_delete:
            del data["known_users"][uid]
        save_data(data)
        await query.message.reply_text(f"🗑 *{removed['name']}* удалён из базы активистов.", parse_mode="Markdown")

# ── Выгрузка CSV ──────────────────────────────────────────────────────────────
async def admin_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow([
        "Мероприятие", "Дата мероприятия", "Место",
        "Роль", "Мест всего", "Занято мест",
        "Фамилия", "Имя", "Отчество",
        "Группа", "Ник в Telegram",
        "Дата записи", "Время записи", "Статус"
    ])
    for ev in data["events"]:
        for role in ev["roles"]:
            if role["signups"]:
                for s in role["signups"]:
                    # Разбиваем ФИО на части
                    fio_parts = s["fio"].split()
                    surname   = fio_parts[0] if len(fio_parts) > 0 else ""
                    first     = fio_parts[1] if len(fio_parts) > 1 else ""
                    patronym  = fio_parts[2] if len(fio_parts) > 2 else ""
                    # Разбиваем дату/время записи
                    signed_at = s.get("signed_at", "")
                    if " " in signed_at:
                        date_part, time_part = signed_at.split(" ", 1)
                    else:
                        date_part, time_part = signed_at, ""
                    w.writerow([
                        ev["title"], ev["date"], ev["location"],
                        role["name"], role["total"], len(role["signups"]),
                        surname, first, patronym,
                        s["group"], s.get("username", "—"),
                        date_part, time_part,
                        "Подтверждён" if s.get("approved") else "Ожидает"
                    ])
            else:
                w.writerow([
                    ev["title"], ev["date"], ev["location"],
                    role["name"], role["total"], 0,
                    "", "", "", "", "", "", "", ""
                ])
    output.seek(0)
    bio = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    bio.name = "activists.csv"
    await query.message.reply_document(document=bio, filename="activists.csv", caption="📥 Выгрузка")

# ── Запись на мероприятие ─────────────────────────────────────────────────────
async def signup_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    events = [e for e in data["events"] if e.get("active")]
    if not events:
        await query.message.reply_text("😔 Сейчас нет открытых мероприятий.")
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(f"📌 {ev['title']} — {ev['date']}", callback_data=f"ev_{ev['id']}")] for ev in events]
    await query.message.reply_text("Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(kb))
    return CHOOSE_EVENT

async def choose_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ev_id = int(query.data.split("_")[1])
    user = update.effective_user
    data = load_data()
    ev = next((e for e in data["events"] if e["id"] == ev_id), None)
    if not ev:
        await query.message.reply_text("Мероприятие не найдено.")
        return ConversationHandler.END
    # Проверка: уже записан на это мероприятие?
    if is_already_signed_to_event(ev, user.id):
        await query.message.reply_text("Вы уже записаны на это мероприятие!")
        return ConversationHandler.END
    ctx.user_data["event_id"] = ev_id
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
    user = update.effective_user
    data = load_data()
    reg = get_user_reg(data, user.id)
    ev_id = ctx.user_data["event_id"]
    ev = next((e for e in data["events"] if e["id"] == ev_id), None)
    role = next((r for r in ev["roles"] if r["name"] == role_name), None)
    if len(role["signups"]) >= role["total"]:
        await query.message.reply_text("😔 Место уже занято. Выберите другую роль.")
        return CHOOSE_ROLE
    desc = ROLE_DESCRIPTIONS.get(role_name, f"🎭 *{role_name}*")
    await query.message.reply_text(desc, parse_mode="Markdown")
    role["signups"].append({
        "telegram_id": user.id,
        "username": f"@{user.username}" if user.username else "—",
        "fio": reg["fio"],
        "group": reg["group"],
        "signed_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "approved": False
    })
    save_data(data)
    # Уведомить организатора
    for admin_id in ADMIN_IDS:
        try:
            kb = [[
                InlineKeyboardButton("✅ Принять", callback_data=f"approve_{ev_id}_{role_name}_{user.id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"remove_{ev_id}_{role_name}_{user.id}"),
            ]]
            await query.get_bot().send_message(
                chat_id=admin_id,
                text=f"🔔 Новая запись!\n\n*{reg['fio']}* ({reg['group']})\n📌 {ev['title']}\n🎭 {role_name}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except Exception:
            pass
    cert = data.get("cert_link", "")
    cert_text = f"\n\n📄 Справка-подтверждение: {cert}" if cert else "\n\n📄 Справка будет доступна после мероприятия."
    await query.message.reply_text(
        f"⏳ *Заявка отправлена!*\n\n"
        f"📌 {ev['title']}\n📅 {ev['date']}\n📍 {ev['location']}\n🎭 Роль: *{role_name}*\n\n"
        f"Ожидайте подтверждения от руководителя.\n"
        f"Будьте на паре — руководитель медиацентра придёт и отпросит вас с занятия."
        f"{cert_text}",
        parse_mode="Markdown"
    )
    ctx.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. /start — начать заново.")
    ctx.user_data.clear()
    return ConversationHandler.END

# ── Напоминания ───────────────────────────────────────────────────────────────
async def send_reminders(app):
    while True:
        await asyncio.sleep(300)
        try:
            data = load_data()
            now = datetime.now()
            changed = False
            for ev in data["events"]:
                if not ev.get("active"):
                    continue
                dt = parse_event_datetime(ev["date"])
                if not dt:
                    continue
                diff = (dt - now).total_seconds() / 3600
                sent = ev.get("reminders_sent", [])
                for threshold, label in [(12, "12h"), (1, "1h")]:
                    if label not in sent and 0 < diff <= threshold + 0.08:
                        hours_text = "12 часов" if threshold == 12 else "1 час"
                        # Уведомляем только подтверждённых
                        for r in ev["roles"]:
                            for s in r["signups"]:
                                if not s.get("approved"):
                                    continue
                                try:
                                    await app.bot.send_message(
                                        chat_id=s["telegram_id"],
                                        text=f"⏰ Напоминание! До мероприятия *{ev['title']}* осталось {hours_text}.\n📅 {ev['date']}\n📍 {ev['location']}",
                                        parse_mode="Markdown"
                                    )
                                except Exception:
                                    pass
                        sent.append(label)
                        changed = True
                ev["reminders_sent"] = sent
            if changed:
                save_data(data)
        except Exception:
            pass

# ── Запуск ────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={WAIT_REG_FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_reg_fio)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
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
    remove_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(remove_signup, pattern="^remove_")],
        states={WAIT_REMOVE_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_remove_comment)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    signup_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(signup_start, pattern="^signup_start$")],
        states={
            CHOOSE_EVENT: [CallbackQueryHandler(choose_event, pattern="^ev_")],
            CHOOSE_ROLE:  [CallbackQueryHandler(choose_role, pattern="^role_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(reg_conv)
    app.add_handler(cert_conv)
    app.add_handler(add_conv)
    app.add_handler(member_conv)
    app.add_handler(remove_conv)
    app.add_handler(signup_conv)
    app.add_handler(CallbackQueryHandler(admin_list,        pattern="^admin_list$"))
    app.add_handler(CallbackQueryHandler(admin_members,     pattern="^admin_members$"))
    app.add_handler(CallbackQueryHandler(admin_export,      pattern="^admin_export$"))
    app.add_handler(CallbackQueryHandler(admin_close_event, pattern="^admin_close_"))
    app.add_handler(CallbackQueryHandler(approve_signup,    pattern="^approve_"))
    app.add_handler(CallbackQueryHandler(del_member,        pattern="^del_member_"))
    app.add_handler(CallbackQueryHandler(get_cert,          pattern="^get_cert$"))

    async def post_init(application):
        from telegram import BotCommand
        await application.bot.set_my_commands([
            BotCommand("start", "Открыть меню"),
        ])
        asyncio.create_task(send_reminders(application))

    app.post_init = post_init
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
