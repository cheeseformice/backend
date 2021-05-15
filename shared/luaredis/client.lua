local codec = require("./codec")
local connect = require("./connection")
local Emitter = require("core").Emitter
local setTimeout = require("timer").setTimeout


local Client
do
	local sub = string.sub
	local wrap = coroutine.wrap

	local function coroutine_factory(f)
		return function(...)
			return wrap(f)(...)
		end
	end

	Client = {}
	Client.__index = Client

	function Client.new(address, reconnectDelay)
		local event = Emitter:new()
		event:on("message", function(msg)
			if msg[1] == "message" then
				event:emit("channelMessage", msg[2], msg[3])
			end
		end)

		return setmetatable({
			address = address,
			reconnectDelay = reconnectDelay,

			event = event,

			isOpen = false,
			msgQueue = {}
		}, Client)
	end

	function Client:connect()
		self.socket = connect(self.address, function()
			self.isOpen = true

			for i = 1, #self.msgQueue do
				self:send(msg)
			end
			self.msgQueue = nil

			self.event:emit("connect")
		end)

		local buffer, index
		self.socket:on("data", function(chunk)
			if buffer then
				if index > 1 then
					buffer = sub(buffer, index)
					index = 1
				end

				buffer = buffer .. chunk

			else
				buffer = chunk
				index = 1
			end

			if buffer == "" then buffer = nil end
			if not buffer then return end

			while buffer do
				local msg, newIndex = codec.decode(buffer, index)

				if msg or newIndex then
					if newIndex then
						-- there was leftover data
						index = newIndex
					else
						-- no leftover data
						buffer = nil
					end

					self.event:emit("message", msg)
				else
					break
				end
			end
		end)

		self.socket:once("close", function()
			self.isOpen = false

			self.msgQueue = {}
			self.event:emit("disconnect")

			if self.reconnectDelay then
				setTimeout(self.reconnectDelay * 1000, self.connect, self)
			end
		end)

		self.socket:once("error", function(err)
			self.event:emit("error", err)
		end)
	end

	function Client:on(evt, callback)
		return self.event:on(evt, coroutine_factory(callback))
	end

	function Client:once(evt, callback)
		return self.event:once(evt, coroutine_factory(callback))
	end

	function Client:send(msg)
		if not msg then return end
		if not self.isOpen then
			self.msgQueue[#self.msgQueue + 1] = msg
			return
		end

		self.socket:write(codec.encode(msg))
	end

	function Client:subscribe(channel)
		return self:send({"subscribe", channel})
	end

	function Client:publish(channel, msg)
		return self:send({"publish", channel, msg})
	end
end


return function(...)
	return Client.new(...)
end
