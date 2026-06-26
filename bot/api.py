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
    # We will handle notification logic here or in a separate task
    # For now, just save to DB
    last_check = get_last_check(result.service_id)
    add_service_check(result.service_id, result.status)

    # Return if state changed to trigger notifications in the bot part
    return {"status": "ok", "changed": (last_check.status != result.status) if last_check else True}

# Bot instance will be shared or we will use a global event bus/queue if needed.
# Since they are in the same process (likely), we can just import the bot.
