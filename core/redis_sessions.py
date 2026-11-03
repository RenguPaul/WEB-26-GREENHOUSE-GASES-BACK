from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "session.lua"


def register_session_script(redis):
    """Загружает Lua-скрипт управления сессиями в Redis."""
    return redis.register_script(_SCRIPT_PATH.read_text(encoding="utf-8"))


async def run_session_script(request, action: str, key: str, value: str | None = None, ttl: int | None = None):
    script = getattr(request.app.state, "session_script", None)
    if script is None:
        raise RuntimeError("Lua-скрипт Redis-сессий не зарегистрирован")
    args = [action, key]
    if value is not None:
        args.append(value)
    if ttl is not None:
        args.append(str(ttl))
    return await script(keys=[], args=args)
