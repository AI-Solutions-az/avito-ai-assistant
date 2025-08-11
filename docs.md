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
- Очистка кэша
`redis-cli FLUSHALL`

Должно вернуть: PONG

## FastAPI
### Запуск FastAPI
--host 0.0.0.0 — доступ с других устройств <br>
--port 8000 — FastAPI работает на http://127.0.0.1:8000  <br>
 — автообновление при изменениях

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
-d '{"url": "http://45.95.235.182:8000/chat"}'`

Получение информации об объявлении <br>
`curl -X GET "https://api.avito.ru/core/v1/accounts/{user_id}/items/{item_id}/" \
 -H "Authorization: Bearer ACCESS_TOKEN" \
 -H "Content-Type: application/json"`

Удаление URL из листа вебхуков <br>
`curl -X POST "https://api.avito.ru/messenger/v1/webhook/unsubscribe" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer <TOKEN>" \
-d '{"url": "http://45.95.235.182:8000/chat"}'`



## Демон
Путь
`cd /etc/systemd/system`

Сервис - создаем через nano
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

# Использование нескольких версий python
## Настройка

```bash
# Установи зависимости
sudo apt update && sudo apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev \
libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

# Установи pyenv
curl https://pyenv.run | bash

# Добавь в .bashrc или .zshrc
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv virtualenv-init -)"
```
## Установить версию по умолчанию
```bash
pyenv global 3.12.1
```
# Фича-флаги (feature flags)
| Название флага              | Тип  | Значение по умолчанию | Описание                                                                                         | Поведение при включении                                                                                      | Поведение при отключении                                                                                      |
|-----------------------------|------|-----------------------|------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| `WORKING_TIME_LOGIC`        | bool | True                  | Управляет режимами работы ассистента и менеджера по времени суток (ночной/дневной режимы)      | В ночное время бот отвечает, в дневное — менеджер мониторит, бот пропускает сообщения                        | Бот обрабатывает все сообщения без разделения режимов                                                         |
| `VOICE_RECOGNITION_ENABLED` | bool | True                  | Управляет модулем распознавания голосовых сообщений через Whisper API                          | Голосовые сообщения распознаются в текст и обрабатываются как обычные сообщения                              | Голосовые сообщения игнорируются, клиенты не получают ответов на голосовые сообщения                         |

Находится в config.py и контролируется с помощью изменения значения переменной флага (False) - для отключения модуля, (True) - для включения.






avito-ai-demo.service
Склад https://docs.google.com/spreadsheets/d/16flBHTR0XouAsjqN6dtgh23LjlzQZMc92cIQExh-HzA/edit?gid=293278087#gid=293278087

street-store.service
Склад https://docs.google.com/spreadsheets/d/1Wd2TfQEUC2nfiLrRiBh3-6n4y1zqNB41v9R1wJ0Guf4/edit?gid=0#gid=0

Try Fashion
Склад https://docs.google.com/spreadsheets/d/1Fj3KYI5qXowmXrWsboKyEFdKx9dCh9mtmRACv9sYq7M/edit?gid=1738833130#gid=1738833130

# Тестирование API приложения
## Тестирование основной логики
```bash
pytest tests/test_chat.py
```
## Тестирование корректной работы парсинга Google таблицы
```bash
pytest tests/test_new_structure.py
```
Для подробного вывода по всем кейсам :
```bash
pytest tests/test_chat.py -v -s
```
```bash
pytest tests/test_new_structure.py -v -s
```
