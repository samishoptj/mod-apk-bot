import asyncio
import logging
import os
from aiogram.enums import ChatAction
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from PIL import Image
import database 
from keep_alive import keep_alive
CHANNEL_ID = -1003836347870
from firebase_admin import credentials, firestore

# Firebase ulash
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

# TEST: databasega yozish
db.collection("users").add({
    "name": "Samir",
    "status": "bot ishladi"
})

print("Firebase ulandi!")
def save_user(user_id):
    db.collection("users").document(str(user_id)).set({
        "user_id": user_id
    })
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

bot = Bot(token=TOKEN)
dp = Dispatcher()

CACHE = {}

async def fast_search(query):
    query_lower = query.lower().strip()
    if query_lower in CACHE:
        return CACHE[query_lower]
    results = await database.search_app(query)
    CACHE[query_lower] = results
    return results

class BotStates(StatesGroup):
    choosing_language = State()
    main_menu = State()
    waiting_for_apk = State()
    waiting_for_apk_name = State()
    waiting_for_delete_name = State()

MESSAGES = {
    'uz': {
        'welcome': "Salom! Men aqlli APK botman. 🤖\n\nMenga quyidagicha murojaat qilishingiz mumkin:\n1️⃣ O'yin nomini yozing (masalan: Minecraft)\n2️⃣ O'yinni tasvirlang (masalan: 'poyga o'yini')\n3️⃣ Skrinshot yuboring!",
        'not_found': f"Afsuski, bu ilova hozircha bazada yo'q. Men adminga xabar berdim, tez orada qo'shiladi! \n\nXavotir olmang, admin juda tez vaqt ichida bu ilovani qo'shadi. Yoki agar xohlasangiz, o'zingiz to'g'ridan-to'g'ri admin bilan bog'lanishingiz mumkin 👉 <a href='tg://user?id={ADMIN_ID}'>Admin Profiliga O'tish</a>",
        'searching': "🔍 Qidiryapman...",
        'lang_name': 'Uzbek'
    },
    'ru': {
        'welcome': "Привет! Я умный APK бот. 🤖\n\nВы можете искать так:\n1️⃣ Напишите название\n2️⃣ Опишите игру\n3️⃣ Пришлите скриншот!",
        'not_found': f"Этого приложения пока нет в базе. Я сообщил админу, скоро добавим! Вы также можете написать админу напрямую 👉 <a href='tg://user?id={ADMIN_ID}'>Связаться с Админом</a>",
        'searching': "🔍 Ищу...",
        'lang_name': 'Russian'
    },
    'tj': {
        'welcome': "Салом! Ман боти интеллектуалии APK ҳастам. 🤖",
        'not_found': f"Мутаассифона, ин барнома дар база нест. Шумо метавонед ба админ нависед 👉 <a href='tg://user?id={ADMIN_ID}'>Админ</a>",
        'searching': "🔍 Ҷустуҷӯ дорам...",
        'lang_name': 'Tajik'
    },
    'en': {
        'welcome': "Hello! I am a smart APK bot. 🤖",
        'not_found': f"Unfortunately, this app is not in the database yet. Contact admin 👉 <a href='tg://user?id={ADMIN_ID}'>Admin</a>",
        'searching': "🔍 Searching...",
        'lang_name': 'English'
    }
}

# --- YORDAMCHI FUNKSIYA (Adminga xabar va mijoz manzili) ---
async def send_admin_alert(bot: Bot, user: types.User, error_type: str, query: str):
    try:
        user_link = f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"
        if user.username:
            user_link += f" (@{user.username})"
            
        msg = f"🚨 <b>DIQQAT: {error_type}</b>\n\n"
        msg += f"👤 <b>Foydalanuvchi:</b> {user_link}\n"
        msg += f"💬 <b>So'rov/Matn:</b> {query}"
        
        await bot.send_message(ADMIN_ID, msg, parse_mode="HTML")
    except Exception as e:
        print(f"Adminga xabar yuborishda xatolik: {e}")

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    # Foydalanuvchini bazaga yozamiz
    await database.add_or_update_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")
    )
    builder.row(
        types.InlineKeyboardButton(text="🇹🇯 Тоҷикӣ", callback_data="lang_tj"),
        types.InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
    )
    await message.answer("Выберите язык / Tilni tanlang / забонро интихоб кунед:", reply_markup=builder.as_markup())
    await state.set_state(BotStates.choosing_language)

@dp.callback_query(F.data.startswith("lang_"))
async def language_selected(callback: types.CallbackQuery, state: FSMContext):
    # Har safar tugma bosganda ham vaqtini yangilaymiz
    await database.add_or_update_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
    lang = callback.data.split("_")[1]
    await state.update_data(locale=lang) 
    await callback.message.edit_text(MESSAGES[lang]['welcome'])
    await state.set_state(BotStates.main_menu)
    await callback.answer()

# ================= 👑 ADMIN PANEL =================
@dp.message(Command("admin"), F.from_user.id == int(ADMIN_ID) if ADMIN_ID else False)
async def admin_panel_start(message: types.Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="➕ O'yin qo'shish", callback_data="admin_add"))
    builder.row(types.InlineKeyboardButton(text="🗑 O'yinni o'chirish", callback_data="admin_delete"))
    builder.row(types.InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"))
    
    await message.answer("👑 Boshqaruv Paneliga xush kelibsiz, Admin!\nQuyidagilardan birini tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    
    if action == "add":
        await callback.message.answer("➕ Iltimos, bazaga qo'shmoqchi bo'lgan APK faylni yuboring.")
        await state.set_state(BotStates.waiting_for_apk)
        
    elif action == "delete":
        await callback.message.answer("🗑 O'chirmoqchi bo'lgan o'yinning ANIQLIK BILAN to'liq nomini yozing:")
        await state.set_state(BotStates.waiting_for_delete_name)
        
    elif action == "stats":
        try:
            total_games = await database.count_apps()
            total_users = await database.count_users()
            active_users = await database.count_active_users()
            
            stats_msg = f"📊 <b>Bot Statistikasi:</b>\n\n"
            stats_msg += f"👥 Jami foydalanuvchilar: <b>{total_users} ta</b>\n"
            stats_msg += f"🟢 Hozirgi faol foydalanuvchilar (15 daqiqa): <b>{active_users} ta</b>\n"
            stats_msg += f"📦 Bazadagi jami o'yinlar: <b>{total_games} ta</b>"
            
            await callback.message.answer(stats_msg, parse_mode="HTML")
        except Exception as e:
            await callback.message.answer("⚠️ Statistika olishda xato. database.py ga funksiyalar qo'shilganiga ishonch hosil qiling.")
            
    await callback.answer()

# --- QO'SHISH JARAYONI ---
@dp.message(BotStates.waiting_for_apk, F.document)
async def admin_receive_apk(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    await state.update_data(new_apk_id=file_id)
    await message.answer("✅ Fayl qabul qilindi. Endi to'liq nomini yozing:")
    await state.set_state(BotStates.waiting_for_apk_name)

@dp.message(BotStates.waiting_for_apk_name, F.text)
async def admin_save_apk(message: types.Message, state: FSMContext):
    game_name = message.text
    data = await state.get_data()
    file_id = data.get('new_apk_id')
    
    await database.add_app(game_name, file_id, game_name)
    CACHE.clear() 
    
    await message.answer(f"🎉 Muvaffaqiyatli saqlandi!\nNomi: {game_name}")
    await state.set_state(BotStates.main_menu)

# --- O'CHIRISH JARAYONI ---
@dp.message(BotStates.waiting_for_delete_name, F.text)
async def admin_delete_process(message: types.Message, state: FSMContext):
    game_to_delete = message.text.strip()
    
    results = await fast_search(game_to_delete)
    if results:
        try:
            await database.delete_app(game_to_delete)
            CACHE.clear() 
            await message.answer(f"✅ <b>{game_to_delete}</b> bot bazasidan muvaffaqiyatli o'chirildi!", parse_mode="HTML")
        except Exception as e:
            await message.answer("⚠️ Xatolik! database.py fayliga delete_app funksiyasini qo'shganingizga ishonch hosil qiling.")
    else:
        await message.answer(f"⚠️ <b>{game_to_delete}</b> bazadan topilmadi. Nomini xatosiz, to'g'ri yozganingizga ishonch hosil qiling.", parse_mode="HTML")
    
    await state.set_state(BotStates.main_menu)

# ================= KANALDAN AVTOMAT SAQLASH =================
@dp.channel_post(F.document)
async def auto_save_from_channel(message: types.Message):
    if message.chat.id == CHANNEL_ID:
        file_id = message.document.file_id
        game_name = message.caption if message.caption else message.document.file_name
        
        await database.add_app(game_name, file_id, game_name)
        CACHE.clear() 
        
        print(f"✅ BAZAGA QO'SHILDI: {game_name}")
        try:
            await bot.send_message(ADMIN_ID, f"📥 Kanaldan avtomat saqlandi:\n{game_name}")
        except Exception as e: pass

# ================= RASM ORQALI =================
@dp.message(BotStates.main_menu, F.photo)
async def handle_photo_ai(message: types.Message, state: FSMContext):
    # Foydalanuvchini yangilash
    await database.add_or_update_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    data = await state.get_data()
    lang = data.get('locale', 'ru')
    msg = await message.answer(MESSAGES[lang]['searching'])
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    
    photo_file = await bot.get_file(message.photo[-1].file_id)
    photo_bytes = await bot.download_file(photo_file.file_path)
    img = Image.open(photo_bytes)
    
    try:
        response = model.generate_content(["Напиши ТОЛЬКО название игры на картинке. Никаких других слов.", img])
        game_name = response.text.strip()
    except Exception as e:
        await msg.edit_text("Tizimda hozircha yuklama yuqori, iltimos 1 daqiqadan so'ng qayta urinib ko'ring! 🔄")
        # Xatoni adminga yuboramiz
        await send_admin_alert(bot, message.from_user, "AI Tizim Xatosi (Yuklama ko'p)", "Rasm tahlil qilishda")
        return
    
    results = await fast_search(game_name) 
    if results:
        await msg.delete()
        f_id, f_name, cap = results[-1]
        await bot.send_document(message.chat.id, f_id, caption=f"✅ <b>{f_name}</b>", parse_mode="HTML")
    else:
        await msg.edit_text(f"🤖 AI aniqladi: {game_name}\n\n{MESSAGES[lang]['not_found']}", parse_mode="HTML")
        # Rasm topilmasa adminga aniq xabar
        await send_admin_alert(bot, message.from_user, "Bazada yo'q (Rasm orqali)", f"AI tushundi: {game_name}")

# ================= UNIVERSAL MATN QIDIRUVI (ROUTER) =================
@dp.message(BotStates.main_menu, F.text)
async def handle_text_ai(message: types.Message, state: FSMContext):
    # Foydalanuvchini yangilash
    await database.add_or_update_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    data = await state.get_data()
    lang_code = data.get('locale', 'ru')
    ai_lang_name = MESSAGES[lang_code]['lang_name']
    query = message.text

    results = await fast_search(query)
    if results:
        f_id, f_name, cap = results[-1] 
        await bot.send_document(message.chat.id, f_id, caption=f"✅ <b>{f_name}</b>", parse_mode="HTML")
        return 

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    
    prompt = f"""
    Sen Telegram botning o'ta aqlli Sun'iy Intellekti (AI) yordamchisisan.
    Foydalanuvchi tili: {ai_lang_name}. Foydalanuvchi yozdi: '{query}'

    VAZIFANG quyidagi 3 ta holatdan eng mosini tanlab, STROGIY FORMATDA javob berish:

    1-HOLAT: Agar foydalanuvchi ilova/o'yin nomini yozgan bo'lsa (hatto gap ichida bo'lsa ham: "salom menga GTA kerak").
    Format:
    NOM: [Faqat o'yin nomi] | JAVOB: [Suhbatdosh sifatida qisqa, do'stona javob]

    2-HOLAT: Agar foydalanuvchi nomini bilmasdan o'yinni ta'riflasa yoki maslahat so'rasa.
    Format:
    TA'RIF: 
    [Do'stona qisqa gap]
    1. <b>[Nomi 1]</b> — [Qisqa ta'rif]
    2. <b>[Nomi 2]</b> — [Qisqa ta'rif]
    3. <b>[Nomi 3]</b> — [Qisqa ta'rif]
    [Shulardan qaysi biri kerak deb so'ra]

    3-HOLAT: Agar u shunchaki "salom", "qandaysan" desa yoki oldingi o'yinlarni "yo'q bular emas" deb rad etsa.
    Format:
    SUHBAT: [Suhbatga mos do'stona javob. Agar rad etsa: "Tushunarli, adminga xabar berdim" mazmunida yoz].
    """
    
    try:
        ai_res = model.generate_content(prompt)
        ai_answer = ai_res.text.strip()
    except Exception as e:
        print(f"❌ HAQIQIY XATO: {e}") 
        await message.answer("Tizimda hozircha yuklama yuqori, iltimos 1 daqiqadan so'ng qayta urinib ko'ring! 🔄")
        # Xatoni adminga yuboramiz
        await send_admin_alert(bot, message.from_user, "AI Tizim Xatosi (Yuklama ko'p)", query)
        return
    
    if "NOM:" in ai_answer and "|" in ai_answer:
        parts = ai_answer.split("|")
        corrected_name = parts[0].replace("NOM:", "").strip()
        chat_response = parts[1].replace("JAVOB:", "").strip()
        
        second_results = await fast_search(corrected_name) 
        if second_results:
            f_id, f_name, cap = second_results[-1]
            if chat_response: await message.answer(chat_response)
            await bot.send_document(message.chat.id, f_id, caption=f"✅ <b>{f_name}</b> (Siz qidirgan ilova)", parse_mode="HTML") 
        else:
            await message.answer(f"{chat_response}\n\n{MESSAGES[lang_code]['not_found']}", parse_mode="HTML")
            # O'yin topilmasa adminga aniq xabar
            await send_admin_alert(bot, message.from_user, "Bazada yo'q", f"Asl matn: {query}\n🤖 AI qidirdi: {corrected_name}")

    elif ai_answer.startswith("TA'RIF:"):
        desc_text = ai_answer.replace("TA'RIF:", "").strip()
        await message.answer(desc_text, parse_mode="HTML")
        
    elif ai_answer.startswith("SUHBAT:"):
        chat_text = ai_answer.replace("SUHBAT:", "").strip()
        if "admin" in chat_text.lower() or "xabar" in chat_text.lower() or "сообщил" in chat_text.lower():
            final_text = f"{chat_text}\n\n👉 <a href='tg://user?id={ADMIN_ID}'>Admin bilan bog'lanish</a>"
            # Mijoz rad etsa yoki chat qilsa adminga xabar
            await send_admin_alert(bot, message.from_user, "Foydalanuvchi Adminga Murojaat qildi/Rad etdi", query)
        else:
            final_text = chat_text
        await message.answer(final_text, parse_mode="HTML")
        
    else:
        await message.answer(ai_answer, parse_mode="HTML")

async def main():
    await database.setup_db() 
    print("Bot ishga tushdi...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
keep_alive()
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
