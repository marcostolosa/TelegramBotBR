# test_payments.py
import pytest
from unittest.mock import MagicMock
from payment_manager import PaymentManager


class MockMercadoPagoSDK:
    def payment(self):
        return self

    def create(self, payment_data):
        return {'response': {'id': 123456}}

    def get(self, payment_id):
        return {'response': {'status': 'approved'}}


@pytest.fixture
def payment_manager():
    sdk_mock = MockMercadoPagoSDK()
    return PaymentManager(sdk=sdk_mock)


def test_create_payment(payment_manager):
    response = payment_manager.create_payment(1.90, 123)
    assert response['response']['id'] == 123456


def test_check_payment_status(payment_manager):
    status = payment_manager.check_payment_status(123456)
    assert status == 'approved'
