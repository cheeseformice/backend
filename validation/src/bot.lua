local json = require("json")
local RedisClient = require("./shared/luaredis/client")
local atelier = require("fromage")()
local setTimeout = require("timer").setTimeout

local reboot = tonumber(os.getenv("FORUM_REBOOT")) or 30 -- minutes


local user = os.getenv("FORUM_USER")
local pass = os.getenv("FORUM_PASS")
assert(user and pass, "need to set FORUM_USER and FORUM_PASS env variables")

local redis = RedisClient(
	os.getenv("INFRA_ADDR") or "redis:6379",
	tonumber(os.getenv("INFRA_RECONNECT")) or 10
)


redis:on("connect", function()
	print("Connected to redis.")
	redis:subscribe("bots:validation")
end)


redis:on("error", function(err)
	print("Redis socket error: " .. err)
end)


redis:on("disconnect", function()
	print("Disconnected from redis. Trying to reconnect in " .. redis.reconnectDelay .. " seconds")
end)


local nextConnectionCheck = 0
local connectionCheckDelay = 60


redis:on("channelMessage", function(channel, msg)
	if channel ~= "bots:validation" then return end

	msg = json.decode(msg)

	if os.time() >= nextConnectionCheck then
		if not atelier.isConnectionAlive() then
			atelier.connect(user, pass)
			assert(atelier.isConnected(), "invalid forum credentials")
		end
		nextConnectionCheck = os.time() + connectionCheckDelay
	end

	atelier.createPrivateMessage(
		msg.target,
		string.format("[CFM] %s", msg.title),
		msg.content
	)
end)


coroutine.wrap(function()
	atelier.connect(user, pass)
	assert(atelier.isConnected(), "invalid forum credentials")
	nextConnectionCheck = os.time() + connectionCheckDelay

	redis:connect()
	setTimeout(
		reboot * 60 * 1000,
		function()
			print("rebooting")
			os.exit()
		end
	)
end)()
