from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

"""
class IsTalep(db.Model):
    __tablename__ = 'is_talepleri'

    id = db.Column(db.Integer, primary_key=True)
    is_adi = db.Column(db.String(200), nullable=False)
    talep_eden = db.Column(db.String(100), nullable=False)
    departman = db.Column(db.String(100), nullable=False)
    oncelik = db.Column(db.String(20), nullable=False, default='Normal')
    aciklama = db.Column(db.Text, nullable=True)
    durum = db.Column(db.String(20), nullable=False, default='Beklemede')
    tarih = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'is_adi': self.is_adi,
            'talep_eden': self.talep_eden,
            'departman': self.departman,
            'oncelik': self.oncelik,
            'aciklama': self.aciklama,
            'durum': self.durum,
            'tarih': self.tarih.strftime('%d.%m.%Y %H:%M')
        }
"""