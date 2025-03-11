#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Pagamentos via Mercado Pago para Telegram
================================================

Este bot implementa um sistema de pagamento via PIX utilizando a API do Mercado Pago,
permitindo que usuários comprem "packs" (por exemplo, Pack Básico e Pack Premium) via
Telegram. O bot gerencia o fluxo de criação de pagamento, verificação de status e
exibição dos packs ativos através de um banco de dados SQLite.

Autor: [Seu Nome]
Data: [Data de Publicação]
Licença: [Tipo de Licença]

Requisitos:
- Python 3.9+
- mercadopago
- pyTelegramBotAPI
- python-dotenv
"""

import os
import sys
import dotenv
import datetime
import sqlite3
import mercadopago
import telebot
from telebot import types
import logging
import threading

# Configuração para evitar problemas de codificação no Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Configuração do logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_payments.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('MercadoPagoBot')

# Carrega variáveis de ambiente a partir do arquivo .env
dotenv.load_dotenv()
MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_IDS = set(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else set()


# =============================================================================
# Classe DatabaseManager
# =============================================================================
class DatabaseManager:
    """
    Gerencia o acesso ao banco de dados SQLite para armazenar informações de pagamentos.
    Utiliza um lock para acesso concorrente e configura o modo WAL.
    """

    def __init__(self, db_file='payments.db'):
        self.db_file = db_file
        self.lock = threading.Lock()
        self.init_db()

    def init_db(self):
        """Cria a tabela de pagamentos (caso não exista) e configura o modo WAL para maior concorrência."""
        with self.lock, sqlite3.connect(self.db_file, check_same_thread=False) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS payments (
                            payment_id INTEGER PRIMARY KEY,
                            user_id INTEGER,
                            username TEXT,
                            chat_id INTEGER,
                            pack_type TEXT,
                            status TEXT,
                            pix_code TEXT,
                            created_at TEXT,
                            approved_at TEXT,
                            expires_at TEXT
                         )''')
            conn.commit()
        logger.info("Banco de dados SQLite inicializado com modo WAL")

    def get_user_active_packs(self, user_id):
        """
        Retorna os packs ativos do usuário.
        
        :param user_id: ID do usuário
        :return: Lista de tuplas (pack_type, expires_at)
        """
        now_iso = datetime.datetime.now().isoformat()
        with self.lock, sqlite3.connect(self.db_file, check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute('''SELECT pack_type, expires_at 
                         FROM payments 
                         WHERE user_id = ? AND status = 'approved' AND expires_at > ?''', 
                      (user_id, now_iso))
            result = c.fetchall()
        logger.debug(f"Packs ativos do usuário {user_id}: {result}")
        return result

    def save_payment(self, payment_id, user_id, username, chat_id, pack_type, pix_code, status='pending'):
        """
        Salva ou atualiza os dados do pagamento no banco.
        
        :param payment_id: ID do pagamento
        :param user_id: ID do usuário
        :param username: Nome do usuário
        :param chat_id: ID do chat
        :param pack_type: Tipo de pack (básico, premium, etc.)
        :param pix_code: Código PIX para pagamento
        :param status: Status do pagamento (default: pending)
        """
        created_at = datetime.datetime.now().isoformat()
        with self.lock, sqlite3.connect(self.db_file, check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO payments 
                         (payment_id, user_id, username, chat_id, pack_type, status, pix_code, created_at, approved_at, expires_at) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (payment_id, user_id, username, chat_id, pack_type, status, pix_code, created_at, None, None))
            conn.commit()
        logger.debug(f"Pagamento {payment_id} salvo no banco: {pack_type}, status={status}")

    def update_payment_status(self, payment_id, status):
        """
        Atualiza o status do pagamento no banco. Se aprovado, define datas de aprovação e expiração.
        
        :param payment_id: ID do pagamento
        :param status: Novo status do pagamento
        """
        with self.lock, sqlite3.connect(self.db_file, check_same_thread=False) as conn:
            c = conn.cursor()
            if status == 'approved':
                approved_at = datetime.datetime.now()
                expires_at = approved_at + datetime.timedelta(days=30)
                c.execute('''UPDATE payments 
                             SET status = ?, approved_at = ?, expires_at = ? 
                             WHERE payment_id = ?''',
                          (status, approved_at.isoformat(), expires_at.isoformat(), payment_id))
                logger.info(f"Pagamento {payment_id} atualizado para 'approved' com expires_at={expires_at.isoformat()}")
            else:
                c.execute('''UPDATE payments 
                             SET status = ? 
                             WHERE payment_id = ?''',
                          (status, payment_id))
                logger.info(f"Pagamento {payment_id} atualizado para {status}")
            conn.commit()


# =============================================================================
# Classe PaymentManager
# =============================================================================
class PaymentManager:
    """
    Gerencia a comunicação com a API do Mercado Pago para criação e verificação de pagamentos.
    """

    def __init__(self, sdk):
        """
        :param sdk: Instância do SDK do Mercado Pago.
        """
        self.sdk = sdk

    def create_payment(self, value, user_id):
        """
        Cria um pagamento via Mercado Pago com base no valor informado.
        
        :param value: Valor do pagamento (float)
        :param user_id: ID do usuário para tracking
        :return: Resposta da API do Mercado Pago (dicionário) ou None em caso de erro.
        """
        logger.info(f"Criando pagamento de R${value} para o usuário {user_id}")
        expire = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.000-03:00")
        logger.debug(f"Data de expiração definida para: {expire}")
        payment_data = {
            "transaction_amount": float(value),
            "payment_method_id": 'pix',
            "installments": 1,
            "description": 'Descrição do pagamento',
            "date_of_expiration": expire,
            "payer": {
                "email": 'seu.email@dominio.com'  # Substitua por um e-mail válido
            }
        }
        try:
            logger.debug(f"Enviando requisição de pagamento: {payment_data}")
            result = self.sdk.payment().create(payment_data)
            payment_id = result.get('response', {}).get('id', 'N/A')
            logger.info(f"Pagamento criado com sucesso. ID: {payment_id}")
            return result
        except Exception as e:
            logger.exception("Erro ao criar pagamento:")
            return None

    def check_payment_status(self, payment_id):
        """
        Verifica o status do pagamento via API.
        
        :param payment_id: ID do pagamento
        :return: Status do pagamento (string) ou None
        """
        logger.info(f"Verificando status do pagamento {payment_id}")
        try:
            result = self.sdk.payment().get(payment_id)
            status = result.get('response', {}).get('status')
            if status:
                logger.info(f"Status do pagamento {payment_id}: {status}")
                return status
            logger.warning(f"Resposta incompleta ao verificar pagamento {payment_id}")
            return None
        except Exception as e:
            logger.exception(f"Erro ao verificar pagamento {payment_id}:")
            return None


# =============================================================================
# Classe TelegramBotHandler
# =============================================================================
class TelegramBotHandler:
    """
    Gerencia os handlers e a lógica do bot do Telegram.
    Responsável por comandos, callbacks e integração com os gerenciadores de pagamento e banco.
    """

    def __init__(self, bot, payment_manager, db_manager):
        """
        :param bot: Instância do bot do Telegram.
        :param payment_manager: Instância de PaymentManager.
        :param db_manager: Instância de DatabaseManager.
        """
        self.bot = bot
        self.payment_manager = payment_manager
        self.db_manager = db_manager
        self.register_handlers()

    def register_handlers(self):
        """Registra os handlers de comandos, callbacks e middleware do bot."""
        self.bot.message_handler(commands=['start'])(self.cmd_start)
        self.bot.message_handler(commands=['status'])(self.cmd_status)
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback)
        self.bot.middleware_handler(update_types=['message', 'callback_query'])(self.log_errors)

    def cmd_start(self, message):
        """Handler para o comando /start."""
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        chat_id = message.chat.id
        logger.info(f"Comando /start recebido do usuário {username} (ID: {user_id}) em chat {chat_id}")

        active_packs = self.db_manager.get_user_active_packs(user_id)
        welcome_msg = f"🌟 Olá, {message.from_user.first_name.replace('!', '\\!')}\\! Bem\\-vindo ao mundo exclusivo da Melzinha\\! 🌟\n\n"
        if active_packs:
            welcome_msg += "🎁 *Seus Packs Ativos:*\n"
            for pack_type, expires_at in active_packs:
                expires_str = datetime.datetime.fromisoformat(expires_at).strftime("%d/%m/%Y")
                welcome_msg += f"\\- 🎉 *{pack_type.title()}* \\(ativo até {expires_str}\\)\n"
        else:
            welcome_msg += "🎁 *Seus Packs Ativos:*\n\\- Você ainda não possui packs ativos\\. Que tal adquirir um agora\\? 😊\n"
        welcome_msg += "\n🚀 *Novas Oportunidades:*\nNão perca a chance de adquirir mais packs e aproveitar benefícios incríveis\\! Selecione:"
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Pack Básico - R$1,90", callback_data="pack_basico"))
        keyboard.add(types.InlineKeyboardButton("Pack Premium - R$2,19", callback_data="pack_premium"))
        try:
            self.bot.send_message(chat_id, text=welcome_msg, reply_markup=keyboard, parse_mode="MarkdownV2")
            logger.info(f"Mensagem de boas-vindas enviada para o usuário {user_id}")
        except Exception as e:
            logger.exception(f"Erro ao enviar mensagem de boas-vindas para o usuário {user_id}")

    def cmd_status(self, message):
        """Handler para o comando /status (apenas para administradores)."""
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not ADMIN_IDS or user_id not in ADMIN_IDS:
            logger.warning(f"Usuário {user_id} tentou acessar /status sem permissão")
            self.bot.send_message(chat_id, "Erro: você não tem permissão para usar este comando.")
            return

        logger.info(f"Comando /status recebido do administrador {user_id} em chat {chat_id}")
        try:
            with self.db_manager.lock, sqlite3.connect(self.db_manager.db_file, check_same_thread=False) as conn:
                c = conn.cursor()
                c.execute("SELECT payment_id, user_id, username, pack_type, created_at FROM payments WHERE status = 'pending'")
                pending_payments = c.fetchall()
                c.execute('''SELECT payment_id, user_id, username, pack_type, approved_at, expires_at 
                             FROM payments 
                             WHERE status = 'approved' AND expires_at > ?''', 
                          (datetime.datetime.now().isoformat(),))
                active_payments = c.fetchall()
        except Exception as e:
            logger.exception("Erro ao acessar o banco de dados para o comando /status")
            self.bot.send_message(chat_id, "Erro ao acessar o banco de dados.")
            return

        response = "🌟 *Status dos Pagamentos* 🌟\n\n"
        response += "📋 *Pagamentos Pendentes*\n"
        if not pending_payments:
            response += "Nenhum pagamento pendente no momento\\.\n"
        else:
            response += "\\| ID            \\| Usuário         \\| Pack       \\| Criado em       \\|\n"
            separator_line = "\\|" + "\\-"*14 + "\\|" + "\\-"*16 + "\\|" + "\\-"*11 + "\\|" + "\\-"*16 + "\\|\n"
            response += separator_line
            for payment in pending_payments:
                payment_id, u_id, username, pack_type, created_at = payment
                created_str = datetime.datetime.fromisoformat(created_at).strftime("%d/%m/%Y %H:%M")
                username_safe = username.replace("|", "\\|").replace("`", "\\`").replace("-", "\\-")
                pack_type_safe = pack_type.title().replace("|", "\\|").replace("`", "\\`").replace("-", "\\-")
                response += f"\\| {payment_id:<13} \\| {username_safe:<15} \\| {pack_type_safe:<10} \\| {created_str:<15} \\|\n"

        response += "\n✅ *Pagamentos Ativos*\n"
        if not active_payments:
            response += "Nenhum pagamento ativo no momento\\.\n"
        else:
            response += "\\| ID            \\| Usuário         \\| Pack       \\| Aprovado em     \\| Expira em       \\|\n"
            separator_line = "\\|" + "\\-"*14 + "\\|" + "\\-"*16 + "\\|" + "\\-"*11 + "\\|" + "\\-"*16 + "\\|" + "\\-"*16 + "\\|\n"
            response += separator_line
            for payment in active_payments:
                payment_id, u_id, username, pack_type, approved_at, expires_at = payment
                approved_str = datetime.datetime.fromisoformat(approved_at).strftime("%d/%m/%Y %H:%M")
                expires_str = datetime.datetime.fromisoformat(expires_at).strftime("%d/%m/%Y %H:%M")
                username_safe = username.replace("|", "\\|").replace("`", "\\`").replace("-", "\\-")
                pack_type_safe = pack_type.title().replace("|", "\\|").replace("`", "\\`").replace("-", "\\-")
                response += f"\\| {payment_id:<13} \\| {username_safe:<15} \\| {pack_type_safe:<10} \\| {approved_str:<15} \\| {expires_str:<15} \\|\n"

        try:
            self.bot.send_message(chat_id, response, parse_mode="MarkdownV2")
            logger.info(f"Lista de pagamentos enviada para o administrador {user_id}")
        except Exception as e:
            logger.exception(f"Erro ao enviar lista de pagamentos para o administrador {user_id}")
            self.bot.send_message(chat_id, "⚠️ Erro ao gerar a lista de pagamentos.")

    def handle_callback(self, call):
        """Handler geral para callbacks dos botões."""
        user_id = call.from_user.id
        username = call.from_user.username or call.from_user.first_name
        chat_id = call.message.chat.id
        callback_data = call.data

        logger.info(f"Callback recebido: {callback_data} do usuário {username} (ID: {user_id}) em chat {chat_id}")
        try:
            self.bot.answer_callback_query(call.id)
        except Exception as e:
            logger.exception(f"Erro ao responder callback {call.id}")

        if callback_data == "pack_basico":
            self.handle_pack_selection(call, value=1.90, pack_type='Básico')
        elif callback_data == "pack_premium":
            self.handle_pack_selection(call, value=2.19, pack_type='Premium')
        elif callback_data.startswith("verify_"):
            payment_id_str = callback_data.split("verify_")[1]
            try:
                payment_id = int(payment_id_str)
            except ValueError:
                logger.error(f"ID de pagamento inválido: {payment_id_str}")
                self.bot.send_message(chat_id, "⚠️ Erro: ID de pagamento inválido.")
                return
            self.handle_payment_verification(call, payment_id)

    def handle_pack_selection(self, call, value, pack_type):
        """Trata a seleção de um pack (Básico ou Premium) pelo usuário."""
        user_id = call.from_user.id
        username = call.from_user.username or call.from_user.first_name
        chat_id = call.message.chat.id
        logger.info(f"Usuário {user_id} selecionou o Pack {pack_type}")
        payment = self.payment_manager.create_payment(value, user_id)
        if payment and payment.get('response') and payment['response'].get('point_of_interaction'):
            pix_data = payment['response']['point_of_interaction'].get('transaction_data', {})
            pix_code = pix_data.get('qr_code')
            payment_id = payment['response'].get('id')
            if pix_code and payment_id:
                logger.info(f"Pagamento criado para Pack {pack_type}. ID: {payment_id}")
                self.db_manager.save_payment(payment_id, user_id, username, chat_id, pack_type.lower(), pix_code)
                try:
                    self.bot.send_message(chat_id, f"🎉 Parabéns pela escolha do Pack {pack_type}! 🎉\n\nPara finalizar sua compra, copie o código PIX abaixo e realize o pagamento:\n\n💡 *Dica:* Pressione e segure o código para copiá-lo facilmente.", parse_mode='HTML')
                    self.bot.send_message(chat_id, f"<code>{pix_code}</code>\n\n", parse_mode='HTML')
                    keyboard = types.InlineKeyboardMarkup()
                    keyboard.add(types.InlineKeyboardButton("Verificar Pagamento", callback_data=f"verify_{payment_id}"))
                    self.bot.send_message(chat_id, "Após o pagamento, clique no botão abaixo para verificar.", reply_markup=keyboard)
                    logger.debug(f"Mensagens de pagamento enviadas para o usuário {user_id}")
                except Exception as e:
                    logger.exception(f"Erro ao enviar informações de pagamento para o usuário {user_id}")
                    self.bot.send_message(chat_id, "⚠️ Erro ao enviar o código PIX. Tente novamente.")
            else:
                logger.error(f"Dados de pagamento incompletos para o Pack {pack_type}")
                self.bot.send_message(chat_id, f"⚠️ Erro ao criar pagamento para o Pack {pack_type}.")
        else:
            logger.error(f"Falha ao criar pagamento para o Pack {pack_type} para o usuário {user_id}")
            self.bot.send_message(chat_id, f"⚠️ Erro ao criar pagamento para o Pack {pack_type}.")

    def handle_payment_verification(self, call, payment_id):
        """Verifica o status do pagamento e atualiza a mensagem do usuário."""
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        logger.info(f"Verificação de pagamento solicitada para ID: {payment_id} pelo usuário {user_id}")

        with self.db_manager.lock, sqlite3.connect(self.db_manager.db_file, check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute("SELECT chat_id, pack_type, status, user_id FROM payments WHERE payment_id = ?", (payment_id,))
            payment_data = c.fetchone()

        if not payment_data:
            logger.warning(f"Nenhum dado encontrado para payment_id {payment_id}")
            self.bot.send_message(chat_id, "⚠️ Erro: dados do pagamento não encontrados. Tente iniciar um novo pedido.")
            return

        stored_chat_id, pack_type, current_status, stored_user_id = payment_data
        if stored_chat_id != chat_id or stored_user_id != user_id:
            logger.warning(f"Acesso negado: stored_chat_id={stored_chat_id}, chat_id={chat_id}, stored_user_id={stored_user_id}, user_id={user_id}")
            self.bot.send_message(chat_id, "⚠️ Erro: você não tem permissão para verificar este pagamento.")
            return

        status = self.payment_manager.check_payment_status(payment_id)
        if status and status != current_status:
            self.db_manager.update_payment_status(payment_id, status)

        if status == "approved":
            logger.info(f"Pagamento {payment_id} APROVADO para o usuário {user_id}")
            # Constrói a mensagem de aprovação escapando os caracteres reservados
            approved_msg = (
                "🎉 *Pagamento Aprovado\\!* 🎉\n"
                "Seu Pack " + pack_type.title() + " já está disponível\\! "
                "Aproveite os próximos 30 dias com benefícios exclusivos\\.\n"
                "Obrigado por confiar na Melzinha\\! 😊"
            )
            self.bot.send_message(chat_id, approved_msg, parse_mode="MarkdownV2")
        elif status == "pending":
            logger.info(f"Pagamento {payment_id} PENDENTE para o usuário {user_id}")
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("Verificar Novamente", callback_data=f"verify_{payment_id}"))
            pending_msg = ("⏳ *Aguardando Confirmação\\." "\\." "\\.*\n"
                           "Seu pagamento via PIX está sendo processado\\.\n"
                           "Assim que for confirmado, seu pack será liberado automaticamente\\!")
            self.bot.send_message(chat_id, pending_msg, reply_markup=keyboard, parse_mode="MarkdownV2")
        elif status == "rejected":
            logger.warning(f"Pagamento {payment_id} REJEITADO para o usuário {user_id}")
            self.bot.send_message(chat_id, "❌ *Pagamento Não Aprovado*\nInfelizmente, seu pagamento foi rejeitado. Tente novamente ou escolha outro método de pagamento.", parse_mode="MarkdownV2")
        elif status == "cancelled":
            logger.warning(f"Pagamento {payment_id} CANCELADO para o usuário {user_id}")
            self.bot.send_message(chat_id, "❌ *Pagamento Cancelado*\nSeu pagamento foi cancelado. Inicie um novo pedido com /start e garanta seu pack!", parse_mode="MarkdownV2")
        else:
            logger.warning(f"Status desconhecido ({status}) para pagamento {payment_id}")
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("Verificar Novamente", callback_data=f"verify_{payment_id}"))
            self.bot.send_message(chat_id, f"ℹ️ *Status Desconhecido*\nO status do pagamento é: {status or 'Desconhecido'}. Tente verificar novamente mais tarde.", reply_markup=keyboard, parse_mode="MarkdownV2")

    def log_errors(self, bot_instance, update):
        """Middleware para logar mensagens e callbacks recebidos."""
        try:
            if hasattr(update, 'message') and update.message:
                user_id = update.message.from_user.id
                chat_id = update.message.chat.id
                text = update.message.text
                logger.debug(f"Mensagem recebida: '{text}' do usuário {user_id} no chat {chat_id}")
            elif hasattr(update, 'callback_query') and update.callback_query:
                user_id = update.callback_query.from_user.id
                chat_id = update.callback_query.message.chat.id
                data = update.callback_query.data
                logger.debug(f"Callback recebido: '{data}' do usuário {user_id} no chat {chat_id}")
        except Exception as e:
            logger.exception("Erro ao processar middleware")

# =============================================================================
# Inicialização dos componentes e início do bot
# =============================================================================
if __name__ == "__main__":
    try:
        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
        logger.info("SDK do Mercado Pago inicializado com sucesso")
    except Exception as e:
        logger.exception("Erro ao inicializar SDK do Mercado Pago:")
        sys.exit(1)

    try:
        telebot.apihelper.ENABLE_MIDDLEWARE = True
        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        logger.info("Bot do Telegram inicializado com sucesso")
    except Exception as e:
        logger.exception("Erro ao inicializar bot do Telegram:")
        sys.exit(1)

    # Instanciar os gerenciadores
    db_manager = DatabaseManager()
    payment_manager = PaymentManager(sdk)
    telegram_handler = TelegramBotHandler(bot, payment_manager, db_manager)

    logger.info("Iniciando bot em modo polling")
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.critical(f"Erro fatal ao executar o bot: {e}")
