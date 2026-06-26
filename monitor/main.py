import asyncio
import httpx
import logging
import yaml
import os
from icmplib import async_ping

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="logs/monitor.log"
)

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

config = load_config()
API_URL = f"http://{config['api']['host']}:{config['api']['port']}"
API_TOKEN = config['api']['token']
INTERVAL = config['monitoring'].get('interval', 30)

async def check_url(address: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(address)
            return response.status_code == 200
    except Exception as e:
        logging.error(f"Error checking URL {address}: {e}")
        return False

async def check_ip(address: str) -> bool:
    try:
        host = await async_ping(address, count=2, interval=0.2, timeout=2)
        return host.is_alive
    except Exception as e:
        logging.error(f"Error pinging IP {address}: {e}")
        return False

async def main():
    # Создаем директорию для логов, если её нет
    os.makedirs("logs", exist_ok=True)

    headers = {"X-Token": API_TOKEN}
    logging.info("Монитор запущен")

    while True:
        try:
            async with httpx.AsyncClient() as client:
                # Получаем список задач (сервисов для проверки)
                response = await client.get(f"{API_URL}/tasks", headers=headers)
                if response.status_code != 200:
                    logging.error(f"Не удалось получить задачи: {response.status_code}")
                    await asyncio.sleep(INTERVAL)
                    continue

                tasks = response.json()

                for task in tasks:
                    service_id = task['id']
                    service_type = task['type']
                    address = task['address']

                    status = False
                    if service_type == 'url':
                        status = await check_url(address)
                    elif service_type == 'ip':
                        status = await check_ip(address)

                    # Отправляем результат проверки в API
                    report = {"service_id": service_id, "status": status}
                    await client.post(f"{API_URL}/report", json=report, headers=headers)
                    logging.info(f"Отчет по {address}, статус: {status}")

        except Exception as e:
            logging.error(f"Error in monitor loop: {e}")

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
