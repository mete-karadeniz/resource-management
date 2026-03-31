import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from database import db
from models import Workspace, AppSettings, MonthlyCapacity, User, Unit, Title, Person, PersonDepartment, Engagement, Booking
from datetime import datetime, timedelta, date
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///resource_planner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Lütfen giriş yapın.'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def ws_id():
    return current_user.workspace_id


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Giriş yapın'}), 401
        if not current_user.is_admin():
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Admin yetkisi gerekli'}), 403
            flash('Admin yetkisi gerekli.', 'error')
            return redirect(url_for('merge'))
        return f(*args, **kwargs)
    return decorated


def get_ws_weeks():
    wid = ws_id()
    start_str = AppSettings.get(wid, 'week_start', '')
    end_str = AppSettings.get(wid, 'week_end', '')
    start_date = None
    end_date = None
    if start_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if end_str:
        try:
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if not start_date:
        today = date.today()
        start_date = today - timedelta(days=today.weekday())
    if not end_date:
        end_date = start_date + timedelta(weeks=52)
    start_date = start_date - timedelta(days=start_date.weekday())
    end_date = end_date - timedelta(days=end_date.weekday())
    weeks = []
    current = start_date
    while current <= end_date:
        weeks.append(current)
        current += timedelta(weeks=1)
    return weeks


def get_weeks_static(start_date=None, num_weeks=52):
    if start_date is None:
        today = date.today()
        start_date = today - timedelta(days=today.weekday())
    return [start_date + timedelta(weeks=i) for i in range(num_weeks)]


def get_week_label(d):
    return f"{d.strftime('%d %b')} - {(d + timedelta(days=4)).strftime('%d %b')}"


def get_month_label(d):
    m = {1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
         7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'}
    return m.get(d.month, d.strftime('%B'))


def get_active_units():
    if not current_user.is_authenticated:
        return []
    return Unit.query.filter_by(workspace_id=ws_id(), is_active=True).order_by(Unit.sort_order, Unit.short_name).all()


def get_active_titles():
    if not current_user.is_authenticated:
        return []
    return Title.query.filter_by(workspace_id=ws_id(), is_active=True).order_by(Title.sort_order, Title.name).all()


def get_demand_page_name():
    if not current_user.is_authenticated:
        return 'Ana Sayfa'
    name = AppSettings.get(ws_id(), 'demand_page_name', '')
    return name if name else 'Ana Sayfa'


@app.context_processor
def utility_processor():
    try:
        units = get_active_units()
        dpn = get_demand_page_name()
        titles = get_active_titles()
        ws_code = current_user.workspace.code if current_user.is_authenticated else ''
        ws_name = current_user.workspace.name if current_user.is_authenticated else ''
    except Exception:
        units, titles = [], []
        dpn = 'Ana Sayfa'
        ws_code, ws_name = '', ''
    return {
        'get_week_label': get_week_label,
        'get_month_label': get_month_label,
        'active_units': units,
        'active_titles': titles,
        'demand_page_name': dpn,
        'ws_code': ws_code,
        'ws_name': ws_name,
    }


# ============ AUTH ============

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('merge'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Kullanıcı adı ve şifre gerekli.', 'error')
            return render_template('login.html')
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            flash('Kullanıcı adı veya şifre hatalı.', 'error')
            return render_template('login.html')
        user.last_login = datetime.utcnow()
        db.session.commit()
        login_user(user, remember=True)
        return redirect(request.args.get('next', url_for('merge')))
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('merge'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        display_name = request.form.get('display_name', '').strip()
        email = request.form.get('email', '').strip()
        action = request.form.get('action', '')
        workspace_name = request.form.get('workspace_name', '').strip()
        workspace_code = request.form.get('workspace_code', '').strip().upper()

        if not username or not password or not display_name:
            flash('Tüm alanları doldurun.', 'error')
            return render_template('register.html')
        if len(password) < 4:
            flash('Şifre en az 4 karakter olmalı.', 'error')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten alınmış.', 'error')
            return render_template('register.html')

        if action == 'create':
            if not workspace_name:
                flash('Workspace adı gerekli.', 'error')
                return render_template('register.html')
            ws = Workspace(name=workspace_name, code=Workspace.generate_code())
            db.session.add(ws)
            db.session.flush()
            user = User(username=username, password=generate_password_hash(password),
                        display_name=display_name, email=email, role='admin', workspace_id=ws.id)
            db.session.add(user)
            db.session.commit()
            flash(f'Workspace oluşturuldu! Kodunuz: {ws.code}', 'success')
            login_user(user, remember=True)
            return redirect(url_for('admin_settings'))

        elif action == 'join':
            if not workspace_code:
                flash('Workspace kodu gerekli.', 'error')
                return render_template('register.html')
            ws = Workspace.query.filter_by(code=workspace_code).first()
            if not ws:
                flash('Geçersiz workspace kodu.', 'error')
                return render_template('register.html')
            user = User(username=username, password=generate_password_hash(password),
                        display_name=display_name, email=email, role='user', workspace_id=ws.id)
            db.session.add(user)
            db.session.commit()
            flash(f'{ws.name} workspace\'ine katıldınız!', 'success')
            login_user(user, remember=True)
            return redirect(url_for('merge'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ============ PAGES ============

@app.route('/')
@login_required
def index():
    return redirect(url_for('merge'))


@app.route('/merge')
@login_required
def merge():
    weeks = get_ws_weeks()
    units = get_active_units()
    data = {}
    cat_weekly_totals = {}

    for unit in units:
        engs = Engagement.query.filter_by(workspace_id=ws_id(), category=unit.short_name).order_by(Engagement.name).all()
        cat_data = []
        for eng in engs:
            booked = db.session.query(Person).join(Booking).filter(Booking.engagement_id == eng.id).distinct().all()
            ei = {'engagement': eng, 'persons': []}
            for p in booked:
                bks = Booking.query.filter_by(person_id=p.id, engagement_id=eng.id).all()
                ei['persons'].append({'person': p, 'bookings': {b.week_start: b for b in bks}})
            cat_data.append(ei)
        data[unit.short_name] = cat_data
        cat_weekly_totals[unit.short_name] = {}
        eids = [e.id for e in engs]
        for w in weeks:
            cat_weekly_totals[unit.short_name][w] = (
                db.session.query(db.func.sum(Booking.hours)).filter(
                    Booking.week_start == w, Booking.engagement_id.in_(eids)).scalar() or 0
            ) if eids else 0

    return render_template('merge.html', weeks=weeks, data=data, units=units, cat_weekly_totals=cat_weekly_totals)


@app.route('/unit/<short_name>')
@login_required
def unit_view(short_name):
    unit = Unit.query.filter_by(workspace_id=ws_id(), short_name=short_name, is_active=True).first_or_404()
    weeks = get_ws_weeks()
    engs = Engagement.query.filter_by(workspace_id=ws_id(), category=unit.short_name).order_by(Engagement.name).all()
    data = []
    for eng in engs:
        booked = db.session.query(Person).join(Booking).filter(Booking.engagement_id == eng.id).distinct().all()
        ei = {'engagement': eng, 'persons': []}
        for p in booked:
            bks = Booking.query.filter_by(person_id=p.id, engagement_id=eng.id).all()
            ei['persons'].append({'person': p, 'bookings': {b.week_start: b for b in bks}})
        data.append(ei)
    eids = [e.id for e in engs]
    wt = {w: (db.session.query(db.func.sum(Booking.hours)).filter(
        Booking.week_start == w, Booking.engagement_id.in_(eids)).scalar() or 0) if eids else 0 for w in weeks}
    return render_template('category_view.html', weeks=weeks, data=data, unit=unit, weekly_totals=wt)


@app.route('/dashboard')
@login_required
def dashboard():
    wid = ws_id()
    tp = Person.query.filter_by(workspace_id=wid, is_active=True).count()
    te = Engagement.query.filter_by(workspace_id=wid, status='Active').count()
    today = date.today()
    cw = today - timedelta(days=today.weekday())
    cwh = db.session.query(db.func.sum(Booking.hours)).join(Engagement).filter(
        Engagement.workspace_id == wid, Booking.week_start == cw).scalar() or 0
    units = get_active_units()
    cs = {}
    for u in units:
        pc = db.session.query(Person).join(PersonDepartment).filter(
            Person.workspace_id == wid, PersonDepartment.department == u.short_name, Person.is_active == True).count()
        ec = Engagement.query.filter_by(workspace_id=wid, category=u.short_name, status='Active').count()
        eids = [e.id for e in Engagement.query.filter_by(workspace_id=wid, category=u.short_name).all()]
        h = (db.session.query(db.func.sum(Booking.hours)).filter(
            Booking.week_start == cw, Booking.engagement_id.in_(eids)).scalar() or 0) if eids else 0
        cs[u.short_name] = {'unit': u, 'people': pc, 'engagements': ec, 'current_hours': h}
    weeks = get_ws_weeks()[:12]
    td = []
    for w in weeks:
        wh = db.session.query(db.func.sum(Booking.hours)).join(Engagement).filter(
            Engagement.workspace_id == wid, Booking.week_start == w).scalar() or 0
        td.append({'week': w.strftime('%d %b'), 'hours': float(wh)})
    bp = db.session.query(Person.name, Person.title, db.func.sum(Booking.hours).label('th')
        ).join(Booking).join(Engagement).filter(Engagement.workspace_id == wid, Booking.week_start == cw
        ).group_by(Person.id).order_by(db.func.sum(Booking.hours).desc()).limit(10).all()
    return render_template('dashboard.html', total_people=tp, total_engagements=te,
                           current_week_hours=cwh, cat_stats=cs, trend_data=json.dumps(td),
                           busy_people=bp, current_week=cw)


@app.route('/utilization')
@login_required
def utilization():
    wid = ws_id()
    weeks = get_ws_weeks()

    months = []
    seen = set()
    for w in weeks:
        key = (w.year, w.month)
        if key not in seen:
            seen.add(key)
            months.append({'year': w.year, 'month': w.month})

    month_labels = {
        1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
        7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
    }

    capacities = {}
    for m in months:
        cap = MonthlyCapacity.query.filter_by(workspace_id=wid, year=m['year'], month=m['month']).first()
        capacities[(m['year'], m['month'])] = cap.hours if cap else 0

    persons = Person.query.filter_by(workspace_id=wid, is_active=True).order_by(Person.name).all()

    person_data = []
    for p in persons:
        monthly_hours = {}
        for m in months:
            key = (m['year'], m['month'])
            total = db.session.query(db.func.sum(Booking.hours)).join(Engagement).filter(
                Booking.person_id == p.id,
                Engagement.workspace_id == wid,
                db.extract('year', Booking.week_start) == m['year'],
                db.extract('month', Booking.week_start) == m['month'],
                Booking.hours > 0
            ).scalar() or 0
            cap = capacities[key]
            available = cap - total if cap > 0 else 0
            pct = (total / cap * 100) if cap > 0 else 0
            monthly_hours[key] = {
                'booked': round(total, 1),
                'capacity': cap,
                'available': round(available, 1),
                'pct': round(pct, 1)
            }
        person_data.append({'person': p, 'months': monthly_hours})

    month_info = []
    for m in months:
        key = (m['year'], m['month'])
        month_info.append({
            'year': m['year'],
            'month': m['month'],
            'label': month_labels.get(m['month'], ''),
            'short': month_labels.get(m['month'], '')[:3],
            'capacity': capacities[key]
        })

    return render_template('utilization.html', person_data=person_data,
                           month_info=month_info, capacities=capacities)


@app.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    r = {'persons': [], 'engagements': []}
    if q:
        r['persons'] = Person.query.filter(Person.workspace_id == ws_id(), db.or_(
            Person.name.ilike(f'%{q}%'), Person.title.ilike(f'%{q}%'))).all()
        r['engagements'] = Engagement.query.filter(Engagement.workspace_id == ws_id(), db.or_(
            Engagement.name.ilike(f'%{q}%'), Engagement.client.ilike(f'%{q}%'))).all()
    return render_template('search.html', query=q, results=r)


@app.route('/search/person/<int:person_id>')
@login_required
def person_detail(person_id):
    person = Person.query.filter_by(id=person_id, workspace_id=ws_id()).first_or_404()
    weeks = get_ws_weeks()
    bks = Booking.query.filter_by(person_id=person.id).all()
    eb = {}
    for b in bks:
        if b.engagement_id not in eb:
            eb[b.engagement_id] = {'engagement': db.session.get(Engagement, b.engagement_id), 'bookings': {}}
        eb[b.engagement_id]['bookings'][b.week_start] = b
    wt = {w: sum(e['bookings'][w].hours for e in eb.values() if w in e['bookings']) for w in weeks}
    return render_template('person_detail.html', person=person, weeks=weeks, eng_bookings=eb, weekly_totals=wt)


@app.route('/search/engagement/<int:engagement_id>')
@login_required
def engagement_detail(engagement_id):
    eng = Engagement.query.filter_by(id=engagement_id, workspace_id=ws_id()).first_or_404()
    weeks = get_ws_weeks()
    bks = Booking.query.filter_by(engagement_id=eng.id).all()
    pb = {}
    for b in bks:
        if b.person_id not in pb:
            pb[b.person_id] = {'person': db.session.get(Person, b.person_id), 'bookings': {}}
        pb[b.person_id]['bookings'][b.week_start] = b
    wt = {w: sum(p['bookings'][w].hours for p in pb.values() if w in p['bookings']) for w in weeks}
    return render_template('engagement_detail.html', engagement=eng, weeks=weeks, person_bookings=pb, weekly_totals=wt)


@app.route('/manage/engagements')
@login_required
def manage_engagements():
    if not current_user.is_admin():
        return redirect(url_for('merge'))
    units = get_active_units()
    ebu = {u.short_name: Engagement.query.filter_by(workspace_id=ws_id(), category=u.short_name).order_by(Engagement.name).all() for u in units}
    persons = Person.query.filter_by(workspace_id=ws_id(), is_active=True).order_by(Person.name).all()
    return render_template('manage_engagements.html', units=units, engagements_by_unit=ebu, persons=persons)


@app.route('/manage/people')
@login_required
def manage_people():
    if not current_user.is_admin():
        return redirect(url_for('merge'))
    return render_template('manage_people.html',
                           people=Person.query.filter_by(workspace_id=ws_id()).order_by(Person.name).all(),
                           units=get_active_units())


@app.route('/admin/settings')
@login_required
def admin_settings():
    if not current_user.is_admin():
        return redirect(url_for('merge'))
    wid = ws_id()
    return render_template('admin_settings.html',
                           units=Unit.query.filter_by(workspace_id=wid).order_by(Unit.sort_order).all(),
                           titles=Title.query.filter_by(workspace_id=wid).order_by(Title.sort_order).all(),
                           users=User.query.filter_by(workspace_id=wid).order_by(User.role.desc(), User.display_name).all(),
                           demand_name=get_demand_page_name(),
                           workspace=current_user.workspace,
                           week_start=AppSettings.get(wid, 'week_start', ''),
                           week_end=AppSettings.get(wid, 'week_end', ''))


# ============ API: USER ============

@app.route('/api/user/<int:uid>/role', methods=['POST'])
@admin_required
def change_user_role(uid):
    u = User.query.filter_by(id=uid, workspace_id=ws_id()).first()
    if not u:
        return jsonify({'success': False}), 404
    r = request.json.get('role', 'user')
    if r not in ('admin', 'user'):
        return jsonify({'success': False}), 400
    u.role = r
    db.session.commit()
    return jsonify({'success': True, 'role': u.role})


@app.route('/api/user/<int:uid>', methods=['DELETE'])
@admin_required
def delete_user(uid):
    u = User.query.filter_by(id=uid, workspace_id=ws_id()).first()
    if not u:
        return jsonify({'success': False}), 404
    if u.id == current_user.id:
        return jsonify({'success': False, 'error': 'Kendinizi silemezsiniz'}), 400
    db.session.delete(u)
    db.session.commit()
    return jsonify({'success': True})


# ============ API: SETTINGS ============

@app.route('/api/settings/demand-name', methods=['POST'])
@admin_required
def update_demand_name():
    AppSettings.set(ws_id(), 'demand_page_name', request.json.get('name', ''))
    return jsonify({'success': True})


@app.route('/api/settings/week-range', methods=['POST'])
@admin_required
def update_week_range():
    d = request.json
    wid = ws_id()
    start = d.get('week_start', '').strip()
    end = d.get('week_end', '').strip()
    if start:
        AppSettings.set(wid, 'week_start', start)
    if end:
        AppSettings.set(wid, 'week_end', end)
    return jsonify({'success': True})


# ============ API: UNITS ============

@app.route('/api/unit', methods=['POST'])
@admin_required
def add_unit():
    d = request.json
    s, l = d.get('short_name', '').strip(), d.get('long_name', '').strip()
    if not s or not l:
        return jsonify({'success': False, 'error': 'İsim gerekli'}), 400
    if Unit.query.filter_by(workspace_id=ws_id(), short_name=s).first():
        return jsonify({'success': False, 'error': 'Zaten var'}), 400
    db.session.add(Unit(workspace_id=ws_id(), short_name=s, long_name=l,
                        icon=d.get('icon', 'fas fa-folder'), color=d.get('color', '#6366f1'),
                        sort_order=d.get('sort_order', 0)))
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/unit/<int:uid>/toggle', methods=['POST'])
@admin_required
def toggle_unit(uid):
    u = Unit.query.filter_by(id=uid, workspace_id=ws_id()).first()
    if not u:
        return jsonify({'success': False}), 404
    u.is_active = not u.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': u.is_active})


@app.route('/api/unit/<int:uid>', methods=['DELETE'])
@admin_required
def delete_unit(uid):
    u = Unit.query.filter_by(id=uid, workspace_id=ws_id()).first()
    if not u:
        return jsonify({'success': False}), 404
    db.session.delete(u)
    db.session.commit()
    return jsonify({'success': True})


# ============ API: TITLES ============

@app.route('/api/title', methods=['POST'])
@admin_required
def add_title():
    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'İsim gerekli'}), 400
    if Title.query.filter_by(workspace_id=ws_id(), name=name).first():
        return jsonify({'success': False, 'error': 'Zaten var'}), 400
    db.session.add(Title(workspace_id=ws_id(), name=name, sort_order=request.json.get('sort_order', 0)))
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/title/<int:tid>/toggle', methods=['POST'])
@admin_required
def toggle_title(tid):
    t = Title.query.filter_by(id=tid, workspace_id=ws_id()).first()
    if not t:
        return jsonify({'success': False}), 404
    t.is_active = not t.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': t.is_active})


@app.route('/api/title/<int:tid>', methods=['DELETE'])
@admin_required
def delete_title(tid):
    t = Title.query.filter_by(id=tid, workspace_id=ws_id()).first()
    if not t:
        return jsonify({'success': False}), 404
    db.session.delete(t)
    db.session.commit()
    return jsonify({'success': True})


# ============ API: PERSON ============

@app.route('/api/person', methods=['POST'])
@admin_required
def add_person():
    d = request.json
    p = Person(workspace_id=ws_id(), name=d['name'], title=d['title'], email=d.get('email', ''), is_active=True)
    db.session.add(p)
    db.session.flush()
    for dept in d.get('departments', []):
        db.session.add(PersonDepartment(person_id=p.id, department=dept))
    db.session.commit()
    return jsonify({'success': True, 'id': p.id})


@app.route('/api/person/<int:pid>/toggle-active', methods=['POST'])
@admin_required
def toggle_person_active(pid):
    p = Person.query.filter_by(id=pid, workspace_id=ws_id()).first()
    if not p:
        return jsonify({'success': False}), 404
    p.is_active = not p.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': p.is_active, 'name': p.name})


@app.route('/api/person/<int:pid>', methods=['DELETE'])
@admin_required
def delete_person(pid):
    p = Person.query.filter_by(id=pid, workspace_id=ws_id()).first()
    if not p:
        return jsonify({'success': False}), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify({'success': True})


# ============ API: ENGAGEMENT ============

@app.route('/api/engagement', methods=['POST'])
@admin_required
def add_engagement():
    d = request.json
    e = Engagement(workspace_id=ws_id(), name=d['name'], client=d.get('client', ''), category=d['category'],
                   status=d.get('status', 'Active'),
                   start_date=datetime.strptime(d['start_date'], '%Y-%m-%d').date() if d.get('start_date') else None,
                   end_date=datetime.strptime(d['end_date'], '%Y-%m-%d').date() if d.get('end_date') else None)
    db.session.add(e)
    db.session.commit()
    return jsonify({'success': True, 'id': e.id})


@app.route('/api/engagement/<int:eid>', methods=['DELETE'])
@admin_required
def delete_engagement(eid):
    e = Engagement.query.filter_by(id=eid, workspace_id=ws_id()).first()
    if not e:
        return jsonify({'success': False}), 404
    db.session.delete(e)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/engagement/<int:eid>/add-person', methods=['POST'])
@admin_required
def add_person_to_engagement(eid):
    p = Person.query.filter_by(id=request.json['person_id'], workspace_id=ws_id()).first()
    if not p:
        return jsonify({'success': False, 'error': 'Kişi bulunamadı'}), 404
    if not p.is_active:
        return jsonify({'success': False, 'error': 'Deaktif kişi atanamaz'}), 400
    if not Booking.query.filter_by(person_id=p.id, engagement_id=eid).first():
        weeks = get_ws_weeks()
        w = weeks[0] if weeks else date.today()
        db.session.add(Booking(person_id=p.id, engagement_id=eid, week_start=w, hours=0, color='green'))
        db.session.commit()
    return jsonify({'success': True})


# ============ API: BOOKING ============

@app.route('/api/booking', methods=['POST'])
@admin_required
def save_booking():
    d = request.json
    pid, eid = int(d['person_id']), int(d['engagement_id'])
    ws_date = datetime.strptime(d['week_start'], '%Y-%m-%d').date()
    hours, color = float(d.get('hours', 0)), d.get('color', 'green')
    b = Booking.query.filter_by(person_id=pid, engagement_id=eid, week_start=ws_date).first()
    if hours == 0 and b:
        db.session.delete(b)
    elif hours > 0:
        if b:
            b.hours = hours
            b.color = color
        else:
            db.session.add(Booking(person_id=pid, engagement_id=eid, week_start=ws_date, hours=hours, color=color))
    db.session.commit()
    eng = db.session.get(Engagement, eid)
    cat, ct = '', 0
    if eng:
        cat = eng.category
        eids = [e.id for e in Engagement.query.filter_by(workspace_id=ws_id(), category=cat).all()]
        ct = db.session.query(db.func.sum(Booking.hours)).filter(
            Booking.week_start == ws_date, Booking.engagement_id.in_(eids)).scalar() or 0
    return jsonify({'success': True, 'cat_total': float(ct), 'category': cat})


@app.route('/api/booking/bulk', methods=['POST'])
@admin_required
def bulk_save_booking():
    d = request.json
    for bd in d.get('bookings', []):
        pid, eid = int(bd['person_id']), int(bd['engagement_id'])
        ws_date = datetime.strptime(bd['week_start'], '%Y-%m-%d').date()
        hours, color = float(bd.get('hours', 0)), bd.get('color', 'green')
        b = Booking.query.filter_by(person_id=pid, engagement_id=eid, week_start=ws_date).first()
        if hours == 0 and b:
            db.session.delete(b)
        elif hours > 0:
            if b:
                b.hours = hours
                b.color = color
            else:
                db.session.add(Booking(person_id=pid, engagement_id=eid, week_start=ws_date, hours=hours, color=color))
    db.session.commit()
    return jsonify({'success': True})


# ============ API: MONTHLY CAPACITY ============

@app.route('/api/capacity', methods=['POST'])
@admin_required
def save_capacity():
    d = request.json
    wid = ws_id()
    year, month, hours = int(d['year']), int(d['month']), float(d['hours'])
    cap = MonthlyCapacity.query.filter_by(workspace_id=wid, year=year, month=month).first()
    if cap:
        cap.hours = hours
    else:
        cap = MonthlyCapacity(workspace_id=wid, year=year, month=month, hours=hours)
        db.session.add(cap)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/capacity/bulk', methods=['POST'])
@admin_required
def save_capacity_bulk():
    d = request.json
    wid = ws_id()
    for item in d.get('capacities', []):
        year, month, hours = int(item['year']), int(item['month']), float(item['hours'])
        cap = MonthlyCapacity.query.filter_by(workspace_id=wid, year=year, month=month).first()
        if cap:
            cap.hours = hours
        else:
            cap = MonthlyCapacity(workspace_id=wid, year=year, month=month, hours=hours)
            db.session.add(cap)
    db.session.commit()
    return jsonify({'success': True})


# ============ SEED ============

def seed_data():
    if User.query.filter_by(username='admin').first():
        return
    ws = Workspace(name='Demo Workspace', code=Workspace.generate_code())
    db.session.add(ws)
    db.session.flush()
    admin = User(username='admin', password=generate_password_hash('admin'),
                 display_name='Admin', email='admin@demo.com', role='admin', workspace_id=ws.id)
    db.session.add(admin)
    db.session.flush()

    for s, l, i, c, o in [
        ('FS', 'Financial Services', 'fas fa-building-columns', '#6366f1', 1),
        ('TR', 'Tax & Regulatory', 'fas fa-file-invoice-dollar', '#8b5cf6', 2),
        ('EoS', 'Engineering & Other Services', 'fas fa-cogs', '#06b6d4', 3),
    ]:
        db.session.add(Unit(workspace_id=ws.id, short_name=s, long_name=l, icon=i, color=c, sort_order=o))
    for idx, name in enumerate(['Partner', 'Director', 'Senior Manager', 'Manager',
                                 'Senior Consultant', 'Consultant', 'Analyst', 'Intern']):
        db.session.add(Title(workspace_id=ws.id, name=name, sort_order=idx))
    db.session.commit()

    for name, title, depts in [
        ('Ahmet Yılmaz', 'Manager', ['FS']), ('Mehmet Kaya', 'Senior Consultant', ['FS', 'TR']),
        ('Ayşe Demir', 'Consultant', ['FS']), ('Ali Öztürk', 'Senior Manager', ['FS']),
        ('Zeynep Arslan', 'Partner', ['TR']), ('Elif Şahin', 'Senior Consultant', ['TR']),
        ('Burak Yıldız', 'Manager', ['EoS']), ('Deniz Eren', 'Senior Consultant', ['EoS', 'FS']),
    ]:
        p = Person(workspace_id=ws.id, name=name, title=title, is_active=True)
        db.session.add(p)
        db.session.flush()
        for d in depts:
            db.session.add(PersonDepartment(person_id=p.id, department=d))
    db.session.commit()

    for n, cl, cat in [('Bank ABC Audit', 'Bank ABC', 'FS'), ('Tax Review', 'MegaCorp', 'TR'),
                        ('IT Transform', 'TechCorp', 'EoS')]:
        db.session.add(Engagement(workspace_id=ws.id, name=n, client=cl, category=cat, status='Active',
                                  start_date=date.today(), end_date=date.today() + timedelta(days=180)))
    db.session.commit()

    import random
    weeks = get_weeks_static(num_weeks=12)
    for eng in Engagement.query.filter_by(workspace_id=ws.id).all():
        dp = [p for p in Person.query.filter_by(workspace_id=ws.id).all() if eng.category in p.get_departments()]
        for person in random.sample(dp, min(2, len(dp))):
            c, sw = random.choice(['green', 'yellow', 'red']), random.randint(0, 4)
            for i in range(random.randint(3, 8)):
                if sw + i < len(weeks):
                    db.session.add(Booking(person_id=person.id, engagement_id=eng.id,
                                           week_start=weeks[sw + i], hours=random.choice([8, 16, 24, 32, 40]), color=c))
    db.session.commit()
    print(f"✅ Demo: admin/admin | Kod: {ws.code}")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True, host='0.0.0.0', port=5000)