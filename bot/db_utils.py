from typing import List, Optional
from datetime import datetime
from sqlmodel import Session, select, func
from .models import engine, Admin, TelegramGroup, Service, ServiceCheck

def add_admin(tg_id: int, username: Optional[str] = None):
    with Session(engine) as session:
        statement = select(Admin).where(Admin.tg_id == tg_id)
        existing = session.exec(statement).first()
        if not existing:
            admin = Admin(tg_id=tg_id, username=username)
            session.add(admin)
            session.commit()
            return True
        return False

def is_admin(tg_id: int) -> bool:
    with Session(engine) as session:
        statement = select(Admin).where(Admin.tg_id == tg_id)
        return session.exec(statement).first() is not None

def get_admins() -> List[Admin]:
    with Session(engine) as session:
        return session.exec(select(Admin)).all()

def register_group(tg_id: int, title: str):
    with Session(engine) as session:
        statement = select(TelegramGroup).where(TelegramGroup.tg_id == tg_id)
        group = session.exec(statement).first()
        if not group:
            group = TelegramGroup(tg_id=tg_id, title=title)
            session.add(group)
            session.commit()
            session.refresh(group)
            return group
        else:
            group.title = title
            session.add(group)
            session.commit()
            session.refresh(group)
            return group

def get_groups() -> List[TelegramGroup]:
    with Session(engine) as session:
        return session.exec(select(TelegramGroup)).all()

def add_service(name: str, type: str, address: str, group_id: int, notification_limit: int = 3):
    with Session(engine) as session:
        service = Service(name=name, type=type, address=address, group_id=group_id, notification_limit=notification_limit)
        session.add(service)
        session.commit()
        session.refresh(service)
        return service

def get_services() -> List[Service]:
    with Session(engine) as session:
        return session.exec(select(Service)).all()

def delete_service(service_id: int):
    with Session(engine) as session:
        service = session.get(Service, service_id)
        if service:
            session.delete(service)
            session.commit()
            return True
        return False

def add_service_check(service_id: int, status: bool):
    with Session(engine) as session:
        check = ServiceCheck(service_id=service_id, status=status)
        session.add(check)
        session.commit()
        return check

def get_last_check(service_id: int) -> Optional[ServiceCheck]:
    with Session(engine) as session:
        statement = select(ServiceCheck).where(ServiceCheck.service_id == service_id).order_by(ServiceCheck.timestamp.desc())
        return session.exec(statement).first()

def get_uptime_info(service_id: int):
    with Session(engine) as session:
        # Находим последнее падение
        statement = select(ServiceCheck).where(ServiceCheck.service_id == service_id, ServiceCheck.status == False).order_by(ServiceCheck.timestamp.desc())
        last_failure = session.exec(statement).first()

        if last_failure:
            return last_failure.timestamp
        else:
            # Если падений не было, возвращаем время самой первой проверки или None
            statement = select(ServiceCheck).where(ServiceCheck.service_id == service_id).order_by(ServiceCheck.timestamp.asc())
            first_check = session.exec(statement).first()
            return first_check.timestamp if first_check else None

def get_consecutive_failures(service_id: int) -> int:
    with Session(engine) as session:
        # Запрашиваем только последние N проверок
        # Нам нужно знать, сколько раз подряд сервис был недоступен с момента последней успешной проверки
        statement = select(ServiceCheck).where(ServiceCheck.service_id == service_id).order_by(ServiceCheck.timestamp.desc()).limit(20)
        checks = session.exec(statement).all()
        count = 0
        for check in checks:
            if not check.status:
                count += 1
            else:
                break
        return count
