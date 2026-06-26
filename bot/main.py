import asyncio
import uvicorn
from .bot_logic import dp, bot
from .api import app
from .models import create_db_and_tables
from .config_loader import config
from .db_utils import get_last_check, get_consecutive_failures, Session, engine, Service, TelegramGroup
from .models import create_db_and_tables, ServiceCheck
from sqlmodel import select

async def run_bot():
    await dp.start_polling(bot)

async def run_api():
    config_api = uvicorn.Config(app, host=config['api']['host'], port=config['api']['port'], log_level="info")
    server = uvicorn.Server(config_api)
    await server.serve()

async def notification_loop():
    """Цикл проверки изменений состояния и отправки уведомлений."""
    # Храним время последней уведомленной проверки для каждого сервиса, чтобы избежать дублей
    last_notified_check_time = {}

    while True:
        with Session(engine) as session:
            # Проверяем все сервисы на наличие новых результатов проверок
            services = session.exec(select(Service)).all()
            for s in services:
                last_check = get_last_check(s.id)
                if not last_check:
                    continue

                # Если мы уже уведомляли об этой конкретной проверке, пропускаем
                if last_notified_check_time.get(s.id) == last_check.timestamp:
                    continue

                # Логика при падении
                if not last_check.status:
                    fail_count = get_consecutive_failures(s.id)
                    if fail_count <= s.notification_limit:
                        # Отправляем уведомление в привязанную группу
                        group = session.get(TelegramGroup, s.group_id)
                        if group:
                            try:
                                await bot.send_message(group.tg_id, f"⚠️ **Внимание!**\nСервис: {s.name} ({s.address})\nСтатус: НЕДОСТУПЕН ❌\nПопытка: {fail_count}/{s.notification_limit}", parse_mode="Markdown")
                            except Exception as e:
                                print(f"Ошибка отправки сообщения: {e}")

                # Логика при восстановлении
                else:
                    # Проверяем, была ли предыдущая проверка неудачной
                    statement = select(ServiceCheck).where(ServiceCheck.service_id == s.id).order_by(ServiceCheck.timestamp.desc()).offset(1)
                    prev_check = session.exec(statement).first()
                    if prev_check and not prev_check.status:
                        group = session.get(TelegramGroup, s.group_id)
                        if group:
                            try:
                                await bot.send_message(group.tg_id, f"✅ **Восстановление!**\nСервис: {s.name} ({s.address})\nСтатус: ДОСТУПЕН 👍", parse_mode="Markdown")
                            except Exception as e:
                                print(f"Ошибка отправки сообщения: {e}")

                last_notified_check_time[s.id] = last_check.timestamp

        await asyncio.sleep(5)

async def main():
    create_db_and_tables()
    await asyncio.gather(
        run_bot(),
        run_api(),
        notification_loop()
    )

if __name__ == "__main__":
    asyncio.run(main())
