import os
import json
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.request import Request as URLRequest, urlopen

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

# --- Настройка БД и параметров ---
DATABASE_URL = "sqlite:////app/tracker.db"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Модели БД ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    telegram_id = Column(String, unique=True, nullable=True)
    habits = relationship("Habit", back_populates="owner", cascade="all, delete-orphan")

class Habit(Base):
    __tablename__ = "habits"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    week_number = Column(Integer, nullable=False)  # ISO week
    year = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="habits")
    logs = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan")

class HabitLog(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    habit_id = Column(Integer, ForeignKey("habits.id"))
    date = Column(String, nullable=False)
    completed = Column(Boolean, default=True)
    habit = relationship("Habit", back_populates="logs")

Base.metadata.create_all(bind=engine)

# --- Инициализация FastAPI ---
app = FastAPI(title="Подготовка к Чемпионату (Модули 1-3)")
templates = Jinja2Templates(directory="templates")

# --- План подготовки инфраструктуры (Модули 1-3, Недели 1–14) ---
DEFAULT_PLAN = [
    # Неделя 1 (38 неделя / 15 — 21 сентября)
    {"year": 2026, "week": 38, "title": "[М1] Сборка и проверка топологии (ISP, HQ-RTR, BR-RTR, HQ-SRV, BR-SRV, HQ-CLI)"},
    {"year": 2026, "week": 38, "title": "[М1] Базовая IP-адресация, VLAN, статическая маршрутизация"},
    {"year": 2026, "week": 38, "title": "[М1] Проверка связи между всеми узлами (ping)"},

    # Неделя 2 (39 неделя / 22 — 28 сентября)
    {"year": 2026, "week": 39, "title": "[М1] Настройка DNS (зона au-team.irpo, A-записи)"},
    {"year": 2026, "week": 39, "title": "[М1] Настройка DHCP для HQ-CLI"},
    {"year": 2026, "week": 39, "title": "[М1] Проверка разрешения имен с клиентов и серверов"},

    # Неделя 3 (40 неделя / 29 сентября — 5 октября)
    {"year": 2026, "week": 40, "title": "[М2] Установка Ansible на BR-SRV, проверка ansible all -m ping"},
    {"year": 2026, "week": 40, "title": "[М2] Развертывание Apache + MariaDB на HQ-SRV, импорт dump.sql в webdb"},
    {"year": 2026, "week": 40, "title": "[М2] Установка Яндекс Браузера на HQ-CLI"},

    # Неделя 4 (41 неделя / 6 — 12 октября)
    {"year": 2026, "week": 41, "title": "[М2] Docker & Docker Compose на BR-SRV (стек testapp + db на 8080)"},
    {"year": 2026, "week": 41, "title": "[М2] Nginx Reverse Proxy на ISP (web.au-team.irpo и docker.au-team.irpo)"},
    {"year": 2026, "week": 41, "title": "[М2] HTTP Basic Auth (htpasswd WEBC) для web.au-team.irpo"},

    # Неделя 5 (42 неделя / 13 — 19 октября)
    {"year": 2026, "week": 42, "title": "[М2] Настройка nftables DNAT на HQ-RTR и BR-RTR"},
    {"year": 2026, "week": 42, "title": "[М2] Проброс портов: 8080->8080 (BR-SRV), 8000->80 (HQ-SRV), 2026->22 (SSH)"},

    # Неделя 6 (43 неделя / 20 — 26 октября)
    {"year": 2026, "week": 43, "title": "[М3] Libreswan на HQ-RTR и BR-RTR, защищенный IPsec-туннель"},
    {"year": 2026, "week": 43, "title": "[М3] Динамическая маршрутизация поверх IPsec-туннеля"},

    # Неделя 7 (44 неделя / 27 октября — 2 ноября)
    {"year": 2026, "week": 44, "title": "[М3] nftables (inet filter input со стороны ISP: HTTP, HTTPS, DNS, NTP, ICMP, GRE)"},
    {"year": 2026, "week": 44, "title": "[М3] CUPS на HQ-SRV, виртуальный PDF-принтер по умолчанию на HQ-CLI"},

    # Неделя 8 (45 неделя / 3 — 9 ноября)
    {"year": 2026, "week": 45, "title": "[М3] rsyslog на HQ-SRV (сбор логов с HQ-RTR, BR-RTR, BR-SRV в /opt + ротация)"},
    {"year": 2026, "week": 45, "title": "[М3] Prometheus на HQ-SRV (ЦП, ОЗУ, диски HQ-SRV и BR-SRV -> mon.au-team.irpo)"},

    # Неделя 9 (46 неделя / 10 — 16 ноября)
    {"year": 2026, "week": 46, "title": "[М3] Ansible-плейбук инвентаризации на BR-SRV (/etc/ansible/PC-INFO)"},
    {"year": 2026, "week": 46, "title": "[М3] Fail2ban на HQ-SRV (jail.local, бан 1 мин после 3 фейлов SSH)"},

    # Неделя 10 (47 неделя / 17 — 23 ноября)
    {"year": 2026, "week": 47, "title": "[М3] Кибер Бэкап на HQ-SRV, хранилище HQ-CLI (/backup)"},
    {"year": 2026, "week": 47, "title": "[М3] Настройка планов бэкапа: /etc и webdb"},

    # Неделя 11 (48 неделя / 24 — 30 ноября)
    {"year": 2026, "week": 48, "title": "[ФИНАЛ] Сквозной сбор Модуля 1 + Модуля 2 на время"},

    # Неделя 12 (49 неделя / 1 — 7 декабря)
    {"year": 2026, "week": 49, "title": "[ФИНАЛ] Сквозной сбор Модуля 3 (IPsec, Firewall, CUPS, Mon, Backup)"},

    # Неделя 13 (50 неделя / 8 — 14 декабря)
    {"year": 2026, "week": 50, "title": "[ФИНАЛ] Финальный прогон (Модули 1-3) в рамки лимита + отчеты"},

    # Неделя 14 (51 неделя / 15 — 21 декабря)
    {"year": 2026, "week": 51, "title": "[ПОЛИРОВКА] Шпаргалки: nftables, jail.local, docker-compose, rsyslog"},

    # Финиш (52 неделя / 22 — 24 декабря)
    {"year": 2026, "week": 52, "title": "🎉 Отдых и финальная проверка готовности!"}
]

def seed_user_plan(db: Session, user_id: int):
    for item in DEFAULT_PLAN:
        habit = Habit(
            title=item["title"],
            week_number=item["week"],
            year=item["year"],
            user_id=user_id
        )
        db.add(habit)
    db.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def send_telegram_message(chat_id: str, text: str):
    if not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode('utf-8')
    req = URLRequest(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=5):
            pass
    except Exception as e:
        print(f"Ошибка отправки Telegram: {e}")

def get_current_week_info(target_week: Optional[int] = None, target_year: Optional[int] = None):
    now = datetime.now()
    year, week, _ = now.isocalendar()
    
    if target_week:
        week = target_week
    if target_year:
        year = target_year
        
    first_day = datetime.strptime(f"{year}-W{week:02d}-1", "%G-W%V-%u").date()
    week_days = [(first_day + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    return year, week, week_days

# --- Маршруты ---

@app.get("/", response_class=HTMLResponse)
def index(request: Request, user_id: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    current_user = None
    if user_id:
        current_user = db.query(User).filter(User.id == int(user_id)).first()
        
    users = db.query(User).all()
    year, current_week, _ = get_current_week_info()
    
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"users": users, "current_user": current_user, "week": current_week, "year": year}
    )

@app.get("/users/add", response_class=HTMLResponse)
def get_add_user_page(request: Request):
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/users/add")
@app.post("/auth/login")
def login_or_add_user(username: str = Form(...), telegram_id: Optional[str] = Form(None), db: Session = Depends(get_db)):
    username = username.strip()
    if not username:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username, telegram_id=telegram_id.strip() if telegram_id else None)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        seed_user_plan(db, user.id)
        
        if user.telegram_id:
            send_telegram_message(user.telegram_id, f"🚀 Привет, <b>{user.username}</b>! Твой план подготовки по Модулям 1-3 успешно загружен!")
    
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="user_id", value=str(user.id))
    return response

@app.get("/auth/logout")
def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("user_id")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request, 
    week: Optional[int] = None, 
    user_id: Optional[str] = Cookie(None), 
    db: Session = Depends(get_db)
):
    if not user_id:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return RedirectResponse(url="/auth/logout", status_code=status.HTTP_303_SEE_OTHER)

    year, active_week, week_days = get_current_week_info(target_week=week)
    
    habits = db.query(Habit).filter(Habit.user_id == user.id, Habit.week_number == active_week, Habit.year == year).all()
    logs_map = {h.id: {log.date: log.completed for log in h.logs} for h in habits}

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "week": active_week,
            "year": year,
            "week_days": week_days,
            "habits": habits,
            "logs_map": logs_map
        }
    )

@app.post("/habits/add")
def add_habit(title: str = Form(...), week: int = Form(...), user_id: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if user_id and title.strip():
        year, _, _ = get_current_week_info()
        habit = Habit(title=title.strip(), user_id=int(user_id), week_number=week, year=year)
        db.add(habit)
        db.commit()
    return RedirectResponse(url=f"/dashboard?week={week}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/habits/toggle")
def toggle_habit(habit_id: int = Form(...), date_str: str = Form(...), week: int = Form(...), user_id: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if not user_id:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    log = db.query(HabitLog).filter(HabitLog.habit_id == habit_id, HabitLog.date == date_str).first()
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if log:
        db.delete(log)
    else:
        new_log = HabitLog(habit_id=habit_id, date=date_str, completed=True)
        db.add(new_log)
        
        if user and user.telegram_id:
            habit = db.query(Habit).filter(Habit.id == habit_id).first()
            send_telegram_message(user.telegram_id, f"✅ Выполнено: <b>{habit.title}</b> ({date_str})!")

    db.commit()
    return RedirectResponse(url=f"/dashboard?week={week}", status_code=status.HTTP_303_SEE_OTHER)
