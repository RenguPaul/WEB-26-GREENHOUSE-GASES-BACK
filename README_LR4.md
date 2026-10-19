# Лабораторная работа № 4 — Greenhouse Gases

## Тема проекта
**Прогноз температуры на Земле в зависимости от содержания парниковых газов в атмосфере.**

ЛР4 продолжает проект на FastAPI, PostgreSQL, SQLAlchemy, Alembic, MinIO и Jinja2. Существующая предметная область и расчёт температуры сохранены.

## Реализовано
- регистрация пользователя и проверка уникальности имени;
- хранение пароля в виде scrypt-хеша с индивидуальной солью;
- вход и выход через cookie `greenhouse_session`;
- HttpOnly cookie с `SameSite=Lax` и временем жизни, задаваемым настройкой;
- серверные сессии в Redis с TTL;
- роли `user` и `moderator`;
- получение текущего пользователя по сессии вместо фиксированного `CURRENT_USER_ID = 1`;
- автоматическое назначение создателя заявки по текущей сессии;
- ограниченный модераторский API `GET /api/users/moderators/users`;
- HTML-страницы регистрации и входа;
- Swagger UI `/docs` и OpenAPI JSON `/openapi.json`;
- миграция роли в таблице `users`;
- сохранение существующей формулы `ΔT = S × log₂(C / C₀)`, где `S = 3.0 °C`, `C₀ = 280 ppm`.

## Запуск
1. Создать локальный `.env` на основе `.env.example`. Не коммитить `.env`.
2. Установить зависимости: `pip install -r requirements.txt`.
3. Запустить инфраструктуру: `docker compose up -d`.
4. Применить миграции: `alembic upgrade head`.
5. Запустить приложение: `uvicorn main:app --reload`.
6. Открыть `http://127.0.0.1:8000/auth/register`, создать аккаунт, затем войти через `/auth/login`.
7. Открыть Swagger: `http://127.0.0.1:8000/docs`.

## Настройки
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` — PostgreSQL.
- `REDIS_URL` — адрес Redis, по умолчанию `redis://localhost:6379/0`.
- `SESSION_TTL_SECONDS` — срок жизни сессии, по умолчанию 86400 секунд.
- `SESSION_COOKIE_SECURE` — включить `true` при HTTPS.
- `MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_BUCKET`, `MINIO_SECURE` — MinIO.

## Роли
Новые пользователи получают роль `user`. Для назначения роли модератора администратор БД должен выполнить:
```sql
UPDATE users SET role = 'moderator' WHERE username = 'имя_пользователя';
```
Проверить роль можно запросом:
```sql
SELECT id, username, role FROM users;
```
Пользователь с ролью `user` при вызове `GET /api/users/moderators/users` получает `403 Forbidden`. Не назначайте роль модератора через публичную форму регистрации.

## Аутентификация API
### Регистрация
`POST /api/users/register`
```json
{"username": "student01", "password": "long-password-123"}
```

### Вход
`POST /api/users/auth`
```json
{"username": "student01", "password": "long-password-123"}
```
При успешном входе сервер устанавливает cookie. Swagger и браузер отправляют её автоматически для запросов к тому же приложению.

### Текущий пользователь
`GET /api/users/me` — возвращает `id`, `username`, `role`.

### Выход
`POST /api/users/deauth` — удаляет серверную сессию в Redis и очищает cookie.

### Модератор
`GET /api/users/moderators/users` — список пользователей; доступен только роли `moderator`.

## Структура новых файлов
- `core/security.py` — хеширование и проверка паролей.
- `api/auth_handlers.py` — API и HTML-обработчики регистрации/входа/выхода.
- `api/dependencies.py` — получение текущего пользователя и проверка роли.
- `templates/auth_register.html`, `templates/auth_login.html` — HTML-страницы.
- `alembic/versions/6c2f8a91b4de_add_user_roles.py` — миграция роли.

## Диаграмма последовательности
Файл `diagrams/lr4_sequence.drawio` содержит сценарии регистрации, входа с сохранением сессии в Redis, доступа к защищённому ресурсу и выхода.

## Важное замечание о старых пользователях
Если в базе остались учётные записи с открытым паролем от предыдущей лабораторной, при первом успешном входе пароль автоматически преобразуется в scrypt-хеш. Новые пароли сразу хешируются при регистрации.
