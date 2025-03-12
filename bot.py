# bot.py (com melhorias visuais e UX)
import os
import dotenv
import logging
import mercadopago
import telebot
from telebot import types
from database_manager import DatabaseManager
from payment_manager import PaymentManager

# Configuração inicial
dotenv.load_dotenv('.env')
MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_IDS = set(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else set()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot_payments.log", encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger('TelegramBot')

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

db_manager = DatabaseManager()
payment_manager = PaymentManager(sdk)

@bot.message_handler(commands=['start'])
def cmd_start(message):
    chat_id = message.chat.id
    first_name = message.from_user.first_name

    mensagem = (
        f"🔥 Olá, {first_name}! 🔥\n\n"
        "Aproveite a oferta exclusiva por tempo limitado! 🚀\n"
        "Escolha seu pack agora e ganhe brindes exclusivos:\n\n"
        "💎 VIP - Apenas R$2,50 (Melhor Escolha!)\n"
        "⭐ Premium - R$1,20\n"
        "⚡ Básico - R$0,50"
    )

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("💎 VIP", callback_data="pack_vip"),
        types.InlineKeyboardButton("⭐ Premium", callback_data="pack_premium"),
        types.InlineKeyboardButton("⚡ Básico", callback_data="pack_basico")
    )

    # Envio de imagem de boas-vindas
    with open('mel.jfif', 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption=mensagem, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pack_"))
def handle_pack_selection(call):
    pack_prices = {'pack_basico': 0.50, 'pack_premium': 1.20, 'pack_vip': 2.50}
    pack_type = call.data
    value = pack_prices[pack_type]
    user_id = call.from_user.id
    username = call.from_user.username

    payment = payment_manager.create_payment(value, user_id)

    if payment and payment.get('response') and payment['response'].get('point_of_interaction'):
        pix_code = payment['response']['point_of_interaction']['transaction_data']['qr_code']
        payment_id = payment['response']['id']

        db_manager.save_payment(payment_id, user_id, username, call.message.chat.id, pack_type=pack_type, pix_code=pix_code)

        mensagem_pagamento = (
            "🚀 Seu pagamento está sendo processado! 🚀\n\n"
            "✨ Quanto antes você pagar, mais rápido aproveita! ✨"
        )

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Verificar Pagamento", callback_data=f"verify_{payment_id}"))

        bot.send_message(call.message.chat.id, mensagem_pagamento)
        bot.send_message(call.message.chat.id, f"`{pix_code}`", parse_mode="Markdown")
        bot.send_message(call.message.chat.id, "👆 Copie o código PIX acima para realizar o pagamento.", reply_markup=markup)
    else:
        bot.send_message(call.message.chat.id, "⚠️ Algo deu errado, tente novamente!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_"))
def handle_payment_verification(call):
    payment_id = int(call.data.split("_")[1])
    status = payment_manager.check_payment_status(payment_id)

    if status == 'approved':
        db_manager.update_payment_status(payment_id, status)
        bot.send_message(call.message.chat.id, "🎉 Pagamento aprovado! Aproveite:")
    elif status == 'pending':
        bot.send_message(call.message.chat.id, "⏳ Ainda estamos aguardando seu pagamento, tente novamente em alguns minutos.")
    else:
        bot.send_message(call.message.chat.id, f"❌ Pagamento não aprovado. Status: {status}")

if __name__ == "__main__":
    logger.info("Iniciando bot em modo polling")
    bot.infinity_polling()