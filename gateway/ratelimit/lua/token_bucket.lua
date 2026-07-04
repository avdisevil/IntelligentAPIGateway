-- Redis Lua script for Token Bucket Rate Limiting
-- KEYS[1] : The key for the token bucket (HASH)
-- ARGV[1] : Current timestamp in milliseconds
-- ARGV[2] : Consume amount (tokens needed)
-- ARGV[3] : Bucket capacity
-- ARGV[4] : Token refill rate (tokens per millisecond)

local key = KEYS[1]
local now = tonumber(ARGV[1])
local needed = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])
local rate = tonumber(ARGV[4])

-- Get current state
local bucket = redis.call("HMGET", key, "tokens", "last_ts")
local tokens = tonumber(bucket[1])
local last_ts = tonumber(bucket[2])

-- Initialize if missing
if not tokens or not last_ts then
    tokens = capacity
    last_ts = now
else
    -- Refill tokens based on elapsed time
    local elapsed = now - last_ts
    if elapsed > 0 then
        local refill = elapsed * rate
        tokens = math.min(capacity, tokens + refill)
        last_ts = now
    end
end

-- Check if enough tokens
local allowed = 0
if tokens >= needed then
    tokens = tokens - needed
    allowed = 1
end

-- Save state
redis.call("HMSET", key, "tokens", tokens, "last_ts", last_ts, "cap", capacity, "rate", rate)
-- Set TTL to prevent leakage (e.g., 1 day)
redis.call("EXPIRE", key, 86400)

return allowed
