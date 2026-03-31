from database import db
from datetime import datetime
from flask_login import UserMixin
import secrets
import string


class Workspace(db.Model):
    __tablename__ = 'workspaces'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('User', backref='workspace', lazy=True)
    units = db.relationship('Unit', backref='workspace', lazy=True, cascade='all, delete-orphan')
    titles = db.relationship('Title', backref='workspace', lazy=True, cascade='all, delete-orphan')
    persons = db.relationship('Person', backref='workspace', lazy=True, cascade='all, delete-orphan')
    engagements = db.relationship('Engagement', backref='workspace', lazy=True, cascade='all, delete-orphan')
    settings = db.relationship('AppSettings', backref='workspace', lazy=True, cascade='all, delete-orphan')
    monthly_capacities = db.relationship('MonthlyCapacity', backref='workspace', lazy=True, cascade='all, delete-orphan')

    @staticmethod
    def generate_code():
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(8))
            if not Workspace.query.filter_by(code=code).first():
                return code


class AppSettings(db.Model):
    __tablename__ = 'app_settings'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(500), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'key', name='unique_ws_setting'),
    )

    @staticmethod
    def get(workspace_id, key, default=''):
        s = AppSettings.query.filter_by(workspace_id=workspace_id, key=key).first()
        return s.value if s else default

    @staticmethod
    def set(workspace_id, key, value):
        s = AppSettings.query.filter_by(workspace_id=workspace_id, key=key).first()
        if s:
            s.value = value
        else:
            s = AppSettings(workspace_id=workspace_id, key=key, value=value)
            db.session.add(s)
        db.session.commit()


class MonthlyCapacity(db.Model):
    __tablename__ = 'monthly_capacities'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    hours = db.Column(db.Float, nullable=False, default=160)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'year', 'month', name='unique_ws_month_cap'),
    )


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), default='user')
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_admin(self):
        return self.role == 'admin'


class Unit(db.Model):
    __tablename__ = 'units'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    short_name = db.Column(db.String(20), nullable=False)
    long_name = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(50), default='fas fa-folder')
    color = db.Column(db.String(20), default='#6366f1')
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'short_name', name='unique_ws_unit'),
    )


class Title(db.Model):
    __tablename__ = 'titles'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'name', name='unique_ws_title'),
    )


class Person(db.Model):
    __tablename__ = 'persons'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    departments = db.relationship('PersonDepartment', backref='person', lazy=True, cascade='all, delete-orphan')
    bookings = db.relationship('Booking', backref='person', lazy=True, cascade='all, delete-orphan')

    def get_departments(self):
        return [d.department for d in self.departments]


class PersonDepartment(db.Model):
    __tablename__ = 'person_department'
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('persons.id'), nullable=False)
    department = db.Column(db.String(50), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('person_id', 'department', name='unique_person_dept'),
    )


class Engagement(db.Model):
    __tablename__ = 'engagements'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    client = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(50), nullable=False, default='FS')
    status = db.Column(db.String(50), default='Active')
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship('Booking', backref='engagement', lazy=True, cascade='all, delete-orphan')


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('persons.id'), nullable=False)
    engagement_id = db.Column(db.Integer, db.ForeignKey('engagements.id'), nullable=False)
    week_start = db.Column(db.Date, nullable=False)
    hours = db.Column(db.Float, default=0)
    color = db.Column(db.String(20), default='green')
    note = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('person_id', 'engagement_id', 'week_start', name='unique_booking'),
    )