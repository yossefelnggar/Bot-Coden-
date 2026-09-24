import os
import json
import asyncio
from threading import Thread

from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from supabase import create_client
from openai import OpenAI


# =========================================================
# 1. ENVIRONMENT VARIABLES
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
ZAI_API_KEY = os.getenv("ZAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if not SUPABASE_SECRET_KEY:
    raise RuntimeError("SUPABASE_SECRET_KEY is missing")

if not ZAI_API_KEY:
    raise RuntimeError("ZAI_API_KEY is missing")

if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is missing")


# =========================================================
# 2. CONNECTIONS
# =========================================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)

zai = OpenAI(
    api_key=ZAI_API_KEY,
    base_url="https://api.z.ai/api/paas/v4/"
)


# =========================================================
# 3. FLASK SERVER
# =========================================================

flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "CODEN Bot is running 🚀"


@flask_app.route("/health")
def health():
    return {
        "status": "ok",
        "service": "CODEN Telegram Bot"
    }


# =========================================================
# 4. QUESTIONS
# =========================================================

QUESTIONS = [
    ("full_name", "👤 اسمك بالكامل؟"),
    ("role", "💼 إيه دورك الأساسي؟\nمثال: Founder / Developer / Designer / Marketer"),
    ("experience_level", "📈 مستوى خبرتك؟\nمثال: Beginner / Intermediate / Advanced"),
    ("skills", "🧠 إيه أهم المهارات اللي عندك؟"),
    ("assets", "🎁 إيه الحاجات اللي تقدر تقدمها لفريق أو Startup؟\nمثال: برمجة، تصميم، علاقات، رأس مال، خبرة..."),
    ("needs", "🔎 إيه اللي بتدور عليه؟\nمثال: Co-founder، Developer، Designer، Investor..."),
    ("industry", "🏢 مهتم بأي مجال؟"),
    ("project_stage", "🚀 لو عندك مشروع، وصل لفين؟\nIdea / MVP / Early Stage / Growing / No Project"),
    ("project_description", "💡 احكيلي عن مشروعك أو فكرتك في كام سطر."),
    ("hours_per_week", "⏰ تقدر تشتغل كام ساعة في الأسبوع؟"),
    ("work_mode", "🌍 تفضل العمل إزاي؟\nRemote / Hybrid / On-site"),
    ("commitment_type", "🤝 نوع الالتزام؟\nPart-time / Full-time / Flexible"),
    ("goal", "🎯 إيه هدفك من CODEN؟"),
    ("vision", "🌎 لو عندك Startup، إيه الرؤية اللي نفسك تحققها؟"),
    ("email", "📧 إيميلك؟"),
    ("phone", "📱 رقم WhatsApp؟"),
    ("linkedin_url", "💼 رابط LinkedIn بتاعك؟\nلو مش عندك اكتب: لا يوجد"),
    ("github_url", "💻 رابط GitHub بتاعك؟\nلو مش عندك اكتب: لا يوجد"),
    ("portfolio_url", "🌐 رابط Portfolio أو موقعك؟\nلو مش عندك اكتب: لا يوجد"),
]


# =========================================================
# 5. START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    context.user_data["step"] = 0
    context.user_data["answers"] = {}

    await update.message.reply_text(
        "🚀 أهلاً بيك في CODEN\n\n"
        "CODEN بتساعدك تلاقي الأشخاص المناسبين لبناء مشروعك:\n"
        "Co-founders • Developers • Designers • Marketers • Investors\n\n"
        "هسألك شوية أسئلة بسيطة، وبعدها AI هيحلل بروفايلك ويجهزه لنظام المطابقة.\n\n"
        "جاهز؟ نبدأ 👇"
    )

    await update.message.reply_text(
        QUESTIONS[0][1]
    )


# =========================================================
# 6. RECEIVE ANSWERS
# =========================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if "step" not in context.user_data:
        await update.message.reply_text(
            "اكتب /start عشان نبدأ تسجيل بروفايلك في CODEN 🚀"
        )
        return

    step = context.user_data["step"]
    answers = context.user_data["answers"]

    key, question = QUESTIONS[step]

    answer = update.message.text.strip()

    answers[key] = answer

    step += 1
    context.user_data["step"] = step

    # Still questions remaining
    if step < len(QUESTIONS):

        next_key, next_question = QUESTIONS[step]

        await update.message.reply_text(
            next_question
        )

        return

    # Finished
    await update.message.reply_text(
        "✅ خلصنا البيانات!\n\n"
        "🤖 دلوقتي Z.ai بيحلل بروفايلك..."
    )

    try:

        profile = await analyze_with_zai(answers)

        await save_profile(
            update.effective_user.id,
            answers,
            profile
        )

        await update.message.reply_text(
            "🎉 تم تسجيل بروفايلك بنجاح!\n\n"
            "CODEN جهز بياناتك للمطابقة مع الأشخاص والمشاريع المناسبة.\n\n"
            "🚀 لما نظام الـMatching يكون جاهز، هنقدر نبدأ نوصلك بالناس المناسبة."
        )

    except Exception as e:

        print("ERROR:", e)

        await update.message.reply_text(
            "❌ حصل خطأ أثناء حفظ البيانات.\n"
            "جرب /start مرة تانية."
        )


# =========================================================
# 7. Z.AI ANALYSIS
# =========================================================

async def analyze_with_zai(answers):

    prompt = f"""
You are the AI profile normalization engine for CODEN.

CODEN is a platform that helps founders, developers,
designers, marketers and other startup people find
co-founders and teammates.

Analyze this user profile:

{json.dumps(answers, ensure_ascii=False, indent=2)}

Return ONLY valid JSON.

Required structure:

{{
  "role": "",
  "skills": [],
  "assets": [],
  "needs": [],
  "industry": [],
  "project_stage": "",
  "goal": "",
  "work_style": [],
  "summary": ""
}}

Rules:

- Normalize skills.
- Extract useful assets.
- Extract what the person needs.
- Identify industries.
- Keep information factual.
- Do not invent information.
- Make the summary concise.
"""

    response = await asyncio.to_thread(
        zai.chat.completions.create,
        model="glm-5",
        messages=[
            {
                "role": "system",
                "content": "You are a structured data extraction engine."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content.strip()

    # Remove markdown JSON fences if Z.ai returns them
    if content.startswith("```"):
        content = content.replace("```json", "")
        content = content.replace("```", "")
        content = content.strip()

    return json.loads(content)


# =========================================================
# 8. SAVE TO SUPABASE
# =========================================================

async def save_profile(telegram_id, answers, ai_profile):

    profile_data = {
        "telegram_id": telegram_id,
        "full_name": answers.get("full_name"),
        "role": ai_profile.get("role") or answers.get("role"),
        "experience_level": answers.get("experience_level"),
        "skills": ai_profile.get("skills", []),
        "assets": ai_profile.get("assets", []),
        "needs": ai_profile.get("needs", []),
        "industry": ai_profile.get("industry", []),
        "project_stage": ai_profile.get("project_stage")
        or answers.get("project_stage"),
        "project_description": answers.get("project_description"),
        "hours_per_week": answers.get("hours_per_week"),
        "work_mode": answers.get("work_mode"),
        "commitment_type": answers.get("commitment_type"),
        "goal": ai_profile.get("goal") or answers.get("goal"),
        "vision": answers.get("vision"),
        "summary": ai_profile.get("summary"),
    }

    result = supabase.table("profiles").upsert(
        profile_data,
        on_conflict="telegram_id"
    ).execute()

    print("PROFILE SAVED:", result.data)

    # Contact information
    contact_data = {
        "telegram_id": telegram_id,
        "email": answers.get("email"),
        "phone": answers.get("phone"),
        "linkedin_url": answers.get("linkedin_url"),
        "github_url": answers.get("github_url"),
        "portfolio_url": answers.get("portfolio_url"),
    }

    contact_result = supabase.table(
        "profile_contacts"
    ).upsert(
        contact_data,
        on_conflict="telegram_id"
    ).execute()

    print("CONTACT SAVED:", contact_result.data)


# =========================================================
# 9. TELEGRAM APPLICATION
# =========================================================

telegram_app = (
    Application.builder()
    .token(BOT_TOKEN)
    .build()
)

telegram_app.add_handler(
    CommandHandler("start", start)
)

telegram_app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    )
)


# =========================================================
# 10. TELEGRAM WEBHOOK
# =========================================================

async def setup_bot():

    await telegram_app.initialize()

    await telegram_app.bot.set_webhook(
        url=f"{WEBHOOK_URL}/telegram"
    )

    await telegram_app.start()

    print("===================================")
    print("🚀 CODEN BOT STARTED")
    print("Webhook:", f"{WEBHOOK_URL}/telegram")
    print("===================================")


# =========================================================
# 11. TELEGRAM WEBHOOK ENDPOINT
# =========================================================

@flask_app.route("/telegram", methods=["POST"])
def telegram_webhook():

    try:

        data = request.get_json(force=True)

        update = Update.de_json(
            data,
            telegram_app.bot
        )

        asyncio.run(
            telegram_app.process_update(update)
        )

        return "OK", 200

    except Exception as e:

        print("WEBHOOK ERROR:", e)

        return "ERROR", 500


# =========================================================
# 12. START EVERYTHING
# =========================================================

def start_background():

    asyncio.run(setup_bot())


if __name__ == "__main__":

    Thread(
        target=start_background,
        daemon=True
    ).start()

    flask_app.run(
        host="0.0.0.0",
        port=PORT
  )
