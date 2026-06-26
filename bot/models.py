import os
from typing import List, Optional
from datetime import datetime, timezone
from sqlmodel import Field, Relationship, SQLModel, create_engine, Session, select

class Admin(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tg_id: int = Field(unique=True)
    username: Optional[str] = None

class TelegramGroup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tg_id: int = Field(unique=True)
    title: str

    services: List["Service"] = Relationship(back_populates="group")

class Service(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    type: str  # "url" or "ip"
    address: str
    group_id: int = Field(foreign_key="telegramgroup.id")
    notification_limit: int = Field(default=3)

    group: TelegramGroup = Relationship(back_populates="services")
    checks: List["ServiceCheck"] = Relationship(back_populates="service")

class ServiceCheck(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    service_id: int = Field(foreign_key="service.id")
    status: bool  # True if Up, False if Down
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    service: Service = Relationship(back_populates="checks")

sqlite_file_name = "data/database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url)

def create_db_and_tables():
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    SQLModel.metadata.create_all(engine)

if __name__ == "__main__":
    create_db_and_tables()
