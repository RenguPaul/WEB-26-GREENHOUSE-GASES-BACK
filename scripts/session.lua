-- Единый Lua-скрипт операций с серверными сессиями.
-- Вызов: EVALSHA <sha> 0 <action> <key> [value] [ttl]
local action = ARGV[1]
local key = ARGV[2]
if action == 'SET' then
    local value = ARGV[3]
    local ttl = tonumber(ARGV[4])
    if not ttl or ttl <= 0 then return redis.error_reply('TTL must be positive') end
    redis.call('SET', key, value, 'EX', ttl)
    return 'OK'
elseif action == 'GET' then
    return redis.call('GET', key)
elseif action == 'DEL' then
    return redis.call('DEL', key)
end
return redis.error_reply('Unsupported session action')
