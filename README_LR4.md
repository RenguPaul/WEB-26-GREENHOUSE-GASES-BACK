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
- атомарные операции создания, чтения и удаления сессий через Lua-скрипт `scripts/session.lua`, загружаемый при старте приложения;
- роли `user` и `moderator`;
- получение текущего пользователя по сессии вместо фиксированного `CURRENT_USER_ID = 1`;
- автоматическое назначение создателя заявки по текущей сессии;
- ограниченный модераторский API `GET /api/users/moderators/users`;
- HTML-страницы регистрации и входа;
- Swagger UI `/docs` и OpenAPI JSON `/openapi.json` с описаниями методов, параметров и основных ошибок;
- публичные GET-методы списка и ленты: чтение опубликованных записей доступно без cookie;
- защищённые методы создания черновика, получения собственного черновика, публикации и лайка;
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
При успешном входе сервер устанавливает cookie `greenhouse_session`. Swagger UI в том же браузере отправляет её автоматически для запросов к тому же приложению. Для Insomnia/Postman cookie можно скопировать из браузера в заголовок `Cookie: greenhouse_session=<значение>`.

### Матрица доступа
| Метод | Гость | Пользователь с действующей сессией |
|---|---|---|
| `GET /api/greenhouse-gases` | `200 OK`, список опубликованных записей | `200 OK`, список; `is_creator` отражает владельца |
| `GET /api/greenhouse-gases/published-gases` | `200 OK`, лента; `is_liked=0` | `200 OK`, лента с персональным `is_liked` |
| `GET /api/greenhouse-gases/my-gas` | `401 Unauthorized` | `200 OK` или `404`, если черновика нет |
| `POST /api/greenhouse-gases` | `401 Unauthorized` | `201 Created`; создатель определяется из сессии |
| `PUT /api/greenhouse-gases/{id}/publish` | `401 Unauthorized` | `200 OK` для собственного черновика; `404` для чужого/несуществующего |
| `POST /api/greenhouse-gases/{id}/like` | `401 Unauthorized` | `200 OK` |

Публичные GET-методы не требуют cookie. Если cookie отсутствует, истекла или недействительна, пользователь всё равно может читать опубликованные записи; персональные поля для гостя имеют значения `is_creator=0` и `is_liked=0`.

### Проверка Redis-сессии
В командной строке выполните:
```powershell
docker exec -it greenhouse_redis redis-cli
```
Затем в `redis-cli`:
```text
KEYS session:*
GET session:<токен_из_cookie>
TTL session:<токен_из_cookie>
```
Значение должно содержать JSON вида `{"user_id": 1}`, а TTL — положительное число. Не публикуйте реальный токен сессии на скриншотах; при необходимости замаскируйте его.

### Сценарий демонстрации в Swagger
1. Откройте `/docs` в обычном окне браузера и выполните `POST /api/users/register` с новым `username` и `password`.
2. Выполните `POST /api/users/auth` с теми же данными. Ответ устанавливает `greenhouse_session` cookie.
3. В том же браузере проверьте `GET /api/users/me`, затем `GET /api/greenhouse-gases` и `GET /api/greenhouse-gases/published-gases`.
4. Откройте `/docs` в режиме инкогнито (без входа) и проверьте, что оба GET-метода чтения возвращают `200 OK`, а `PUT /api/greenhouse-gases/{id}/publish` возвращает `401 Unauthorized`.
5. Вернитесь в авторизованный браузер. Создайте черновик через `POST /api/greenhouse-gases` с `multipart/form-data`, полем `name` и файлами `image`, `video`; затем проверьте `GET /api/greenhouse-gases/my-gas` и опубликуйте полученный `id` через `PUT /api/greenhouse-gases/{id}/publish`.
6. Покажите ключ сессии и TTL в Redis CLI. Для Insomnia/Postman скопируйте cookie из DevTools → Application → Cookies и передайте её в заголовке `Cookie`.

Важно: Swagger сохраняет cookie только в контексте того же браузера/домена. Токен не нужно вставлять в JSON тела запроса.

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

## Расчёт изменения температуры

Для оценки изменения температуры используется сохранённая в проекте упрощённая зависимость:

`ΔT = S × log₂(C / C₀)`, где `S = 3.0 °C`, `C₀ = 280 ppm`, `C` — введённая концентрация CO₂ в ppm.

В коде расчёт выполняется как `round(3.0 * math.log2(concentration_ppm / 280.0), 1)`. Если концентрация не задана, результат остаётся `NULL`; для неположительной концентрации функция HTML-обработчика возвращает `0.0`, чтобы не вычислять логарифм неположительного числа. Результат округляется до одного знака после запятой и сохраняется в `temperature_change_c`. Это упрощённая модель для учебного проекта, а не полноценная климатическая модель.

## Lua и Redis

Файл `scripts/session.lua` реализует три операции: `SET` (запись JSON-сессии с TTL), `GET` (чтение сессии) и `DEL` (удаление сессии). При запуске FastAPI скрипт регистрируется в Redis через `register_script`; обработчики авторизации и зависимости используют общий вызов `core/redis_sessions.py`. Redis хранит только идентификатор пользователя в JSON-полезной нагрузке, а срок действия ключа ограничивается TTL.

Если база уже содержит старые ссылки на SVG, выполните один раз в PostgreSQL:
```sql
UPDATE greenhouse_gases
SET image_url = '/static/media/default-greenhouse.jpg'
WHERE image_url = '/static/media/default-greenhouse.svg';
```

## Диаграмма последовательности
Файл `diagrams/lr4_sequence.drawio` описывает бизнес-процесс без таблиц базы данных и без lifeline нативного приложения: регистрация/вход, публичное чтение с фильтром, создание черновика с изображением и видео, получение полей черновика, публикация, чтение ленты, запрос следующей записи через `next=true` и лайк. Сообщения содержат HTTP-метод, путь и ключевые аргументы.

Требование StarUML о повторном использовании свойства `signature` относится к редактированию UML-модели в StarUML. Файл draw.io является диаграммой для просмотра/редактирования в diagrams.net и сам по себе не доказывает повторное использование свойства `signature` в StarUML; это действие следует выполнить в исходной модели StarUML.

## Важное замечание о старых пользователях
Если в базе остались учётные записи с открытым паролем от предыдущей лабораторной, при первом успешном входе пароль автоматически преобразуется в scrypt-хеш. Новые пароли сразу хешируются при регистрации.


## UML-диаграмма классов и ER-модель

- `diagrams/lr4_class.drawio` — UML-диаграмма классов `User`, `GreenhouseGas`, `Like`, обработчика авторизации и репозитория.
- `greenhouse_gases.xml` — ER-модель с полным набором колонок трёх таблиц. Пометка `NULL` присутствует только у nullable-полей; обязательные поля отмечены `NOT NULL`. В `likes` составной первичный ключ образован `user_id` и `greenhouse_gas_id`.

Обе диаграммы рассчитаны на лист A4 в книжной ориентации. Их можно открыть и при необходимости подвинуть элементы в diagrams.net (draw.io).
