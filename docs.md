# Общее
Сервис предназначен для работы с LLM в качестве продавца-ассистента

# Технический детали
## Стек
- Python (см. requirements.txt)



# Шпаргалки команд
## Окружение
Активация окружения <br>
`python -m venv venv` <br>
`source venv/bin/activate  # Для macOS/Linux`

Установка зависимостей <br>
`pip install -r requirements.txt`

## Демон
### Команды
- Проверка статуса бота <br>
`systemctl status avito-ai`
- Рестарт бота <br>
`systemctl restart avito-ai`
- Остановка бота <br>
`systemctl stop avito-ai`
- Старт бота  <br>
`systemctl start avito-ai`

## Redis
- Запуск Redis <br>
`redis-server`
- Проверка работы Redis: <br>
`redis-cli ping`

Должно вернуть: PONG

## FastAPI
### Запуск FastAPI
--host 0.0.0.0 — доступ с других устройств <br>
--port 8000 — FastAPI работает на http://127.0.0.1:8000  <br>
--reload — автообновление при изменениях

`uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

### Проверка работы
Открываем браузер и заходим в Swagger UI:
http://127.0.0.1:8000/docs <br>
Там можно тестировать API-запросы прямо в интерфейсе.

## Авито API
Авторизация <br>
https://arc.net/l/quote/oxnxkssg <br>
`curl -L -X POST 'https://api.avito.ru/token/' \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode 'grant_type=client_credentials' \
    --data-urlencode 'client_id=<CLIENT_ID>' \
    --data-urlencode 'client_secret=<CLIENT_SECRET>'`

Добавление URL в лист вебхуков <br>
`curl -X POST "https://api.avito.ru/messenger/v3/webhook" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer <TOKEN>" \
-d '{"url": "http://209.38.74.186:8000/chat"}'`

Получение информации об объявлении <br>
`curl -X GET "https://api.avito.ru/core/v1/accounts/{user_id}/items/{item_id}/" \
 -H "Authorization: Bearer ACCESS_TOKEN" \
 -H "Content-Type: application/json"`

Удаление URL из листа вебхуков <br>
`curl -X POST "https://api.avito.ru/messenger/v1/webhook/unsubscribe" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer <TOKEN>" \
-d '{"url": "http://209.38.74.186:8000/chat"}'`



## Демон
Путь
`cd /etc/systemd/system`

Сервис
`avito-ai.service`

[Unit] <br>
Description=Avito AI Assistant
After=network.target

[Service] <br>
User=root <br>
WorkingDirectory=/root/avito-ai-assistant <br>
ExecStart=/root/avito-ai-assistant/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 <br>
Restart=always <br>

[Install] <br>
WantedBy=multi-user.target

