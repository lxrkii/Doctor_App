import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, Form, Depends, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from tortoise.contrib.fastapi import register_tortoise
from backend.models.user import User
from backend.models.wear_session import WearSession
from backend.models.admin import Admin
from backend.config import DB_URL
import hashlib

app = FastAPI(title="ЭлайнерКонтроль — Админка")

static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

register_tortoise(
    app,
    db_url=DB_URL,
    modules={"models": ["backend.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

@app.get("/")
def root():
    return RedirectResponse("/login")

@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    # Хешируем введенный пароль
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    print(f"Попытка входа: username={username}, password_hash={password_hash}")
    
    # Ищем администратора в базе данных
    admin = await Admin.filter(username=username, password_hash=password_hash).first()
    
    # Проверяем всех администраторов для отладки
    all_admins = await Admin.all()
    print(f"Всего администраторов в БД: {len(all_admins)}")
    for a in all_admins:
        print(f"Admin: {a.username}, hash: {a.password_hash}")
    
    if admin:
        print("Аутентификация успешна!")
        # Успешная аутентификация
        response = RedirectResponse("/patients", status_code=status.HTTP_302_FOUND)
        # TODO: Добавить сессии/куки для авторизации
        return response
    else:
        print("Аутентификация неудачна!")
        # Неудачная аутентификация
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Неверный логин или пароль"
        })

@app.get("/patients")
async def patients(request: Request):
    users = await User.all()
    return templates.TemplateResponse("patients.html", {"request": request, "users": users})

@app.get("/patient/{user_id}")
async def patient_detail(request: Request, user_id: int):
    user = await User.get_or_none(id=user_id)
    sessions = await WearSession.filter(user=user).order_by("-date").limit(30)
    return templates.TemplateResponse("patient_detail.html", {"request": request, "user": user, "sessions": sessions})

@app.post("/patient/{user_id}/edit")
async def edit_patient(request: Request, user_id: int,
                      name: str = Form(...),
                      daily_goal_hours: float = Form(...),
                      aligner_change_interval_days: int = Form(...),
                      name_locked: bool = Form(False)):
    user = await User.get_or_none(id=user_id)
    if user:
        user.name = name
        user.name_locked = name_locked
        user.daily_goal_hours = daily_goal_hours
        user.aligner_change_interval_days = aligner_change_interval_days
        await user.save()
    return RedirectResponse(f"/patient/{user_id}", status_code=302)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 