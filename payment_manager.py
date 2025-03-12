# payment_manager.py
import logging
from datetime import datetime, timedelta

logger = logging.getLogger('MercadoPagoBot')


class PaymentManager:
    def __init__(self, sdk):
        self.sdk = sdk

    def create_payment(self, value, user_id):
        expire = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.000-03:00")
        payment_data = {
            "transaction_amount": float(value),
            "payment_method_id": 'pix',
            "installments": 1,
            "description": f'Pagamento do usuário {user_id}',
            "date_of_expiration": expire,
            "payer": {"email": 'email@dominio.com'}  # Sugestão futura: email dinâmico
        }
        try:
            result = self.sdk.payment().create(payment_data)
            payment_id = result.get('response', {}).get('id')
            logger.info(f"Pagamento criado com sucesso. ID: {payment_id}")
            return result
        except Exception as e:
            self.handle_exception(e, "criação de pagamento")
            return None

    def check_payment_status(self, payment_id):
        try:
            result = self.sdk.payment().get(payment_id)
            status = result.get('response', {}).get('status')
            if status:
                logger.info(f"Status do pagamento {payment_id}: {status}")
                return status
            else:
                logger.warning(f"Resposta incompleta para pagamento {payment_id}")
                return None
        except Exception as e:
            self.handle_exception(e, f"verificação do pagamento {payment_id}")
            return None

    @staticmethod
    def handle_exception(e, context=""):
        logger.exception(f"Erro em {context}: {e}")
