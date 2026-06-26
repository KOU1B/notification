import logging
from fastapi import FastAPI, Depends, HTTPException, Header
from typing import List, Optional
from pydantic import BaseModel
from .db_utils import get_services, add_service_check, get_last_check
from .config_loader import config

app = FastAPI()

API_TOKEN = config['api']['token']

class CheckResult(BaseModel):
    service_id: int
    status: bool

def verify_token(x_token: str = Header(...)):
    if x_token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid API Token")

@app.get("/tasks")
async def get_tasks(token: str = Depends(verify_token)):
    services = get_services()
    return [{"id": s.id, "type": s.type, "address": s.address} for s in services]

@app.post("/report")
async def report_result(result: CheckResult, token: str = Depends(verify_token)):
    # Логика уведомлений обрабатывается в фоновом цикле bot/main.py
    # Здесь мы только сохраняем результат в БД
    last_check = get_last_check(result.service_id)
    add_service_check(result.service_id, result.status)

    # Возвращаем информацию о том, изменилось ли состояние (для логов монитора)
    return {"status": "ok", "changed": (last_check.status != result.status) if last_check else True}
