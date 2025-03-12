# database_manager.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta
import threading

engine = create_engine('sqlite:///payments.db', connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Payment(Base):
    __tablename__ = 'payments'

    payment_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    chat_id = Column(Integer, nullable=False)
    pack_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default='pending')
    pix_code = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime)
    expires_at = Column(DateTime)


Base.metadata.create_all(engine)


class DatabaseManager:
    def __init__(self):
        self.lock = threading.Lock()

    def get_user_active_packs(self, user_id):
        with self.lock:
            db = SessionLocal()
            now = datetime.utcnow()
            packs = db.query(Payment).filter(
                Payment.user_id == user_id,
                Payment.status == 'approved',
                Payment.expires_at > now
            ).all()
            db.close()
            return [(pack.pack_type, pack.expires_at) for pack in packs]

    def save_payment(self, payment_id, user_id, username, chat_id, pack_type, pix_code):
        with self.lock:
            db = SessionLocal()
            payment = Payment(
                payment_id=payment_id,
                user_id=user_id,
                username=username,
                chat_id=chat_id,
                pack_type=pack_type,
                pix_code=pix_code
            )
            db.add(payment)
            db.commit()
            db.close()

    def update_payment_status(self, payment_id, status):
        with self.lock:
            db = SessionLocal()
            payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
            if payment:
                payment.status = status
                if status == 'approved':
                    payment.approved_at = datetime.utcnow()
                    payment.expires_at = datetime.utcnow() + timedelta(days=30)
                db.commit()
            db.close()

    def get_all_active_payments(self):
        with self.lock:
            db = SessionLocal()
            now = datetime.utcnow()
            active_payments = db.query(Payment).filter(
                Payment.status == 'approved',
                Payment.expires_at > now
            ).all()
            db.close()
            return [(p.payment_id, p.username, p.pack_type, p.expires_at) for p in active_payments]
