local uv = require("uv")
local net = require("net")
local timer = require("timer")
local utils = require("utils")
local Duplex = require("stream").Duplex
local Emitter = require("core").Emitter

local assert = assert
local sub = string.sub
local find = string.find

local UnixSocket = Duplex:extend()
function UnixSocket:initialize(options)
	Duplex.initialize(self)
	if type(options) == "number" then
		options = { fd = options }
	elseif options == nil then
		options = {}
	end

	if options.handle then
		self._handle = options.handle
	elseif options.fd then
		local typ = uv.guess_handle(options.fd)
		if typ == "TCP" then
			self._handle = uv.new_tcp()
		elseif typ == "PIPE" then
			self._handle = uv.new_pipe()
		end
	end

	self._connecting = false
	self._reading = false
	self._destroyed = false

	self:on("finish", utils.bind(self._onSocketFinish, self))
	self:on("_socketEnd", utils.bind(self._onSocketEnd, self))
end

function UnixSocket:_onSocketFinish()
	if self._connecting then
		return self:once("connect", utils.bind(self._onSocketFinish, self))
	end
	if not self.readable then
		return self:destroy()
	end
end

function UnixSocket:_onSocketEnd()
	self:once("end", function()
		self:destroy()
	end)
end

function UnixSocket:bind(path)
	uv.pipe_bind(self._handle, path)
end

function UnixSocket:address()
	return uv.pipe_getpeername(self._handle)
end

function UnixSocket:_write(data, callback)
	if not self._handle then return end
	uv.write(self._handle, data, function(err)
		if err then
			self:destroy(err)
			return callback(err)
		end
		callback()
	end)
end

function UnixSocket:_read(n)
	local onRead

	function onRead(err, data)
		if err then
			return self:destroy(err)
		elseif data then
			self:push(data)
		else
			self:push(nil)
			self:emit("_socketEnd")
		end
	end

	if self._connecting then
		self:once("connect", utils.bind(self._read, self, n))
	elseif not self._reading then
		self._reading = true
		uv.read_start(self._handle, onRead)
	end
end

function UnixSocket:shutdown(callback)
	if self.destroyed == true and callback then
		return callback()
	end

	if uv.is_closing(self._handle) and callback then
		return callback()
	end

	uv.shutdown(self._handle, callback)
end

function UnixSocket:getSendBufferSize()
	return uv.send_buffer_size(self._handle)
end

function UnixSocket:getRecvBufferSize()
	return uv.recv_buffer_size(self._handle)
end

function UnixSocket:setSendBufferSize(size)
	assert(type(size) == "number" and size > 0, "Size must be a number greater than 0")
	return uv.send_buffer_size(self._handle, size)
end

function UnixSocket:setRecvBufferSize(size)
	assert(type(size) == "number" and size > 0, "Size must be a number greater than 0")
	return uv.recv_buffer_size(self._handle, size)
end

function UnixSocket:pause()
	Duplex.pause(self)
	if not self._handle then return end
	self._reading = false
	uv.read_stop(self._handle)
end

function UnixSocket:resume()
	Duplex.resume(self)
	self:_read(0)
end

function UnixSocket:connect(path, callback)
	assert(path, "missing socket path")
	callback = callback or function() end

	self._connecting = true

	if not self._handle then
		self._handle = uv.new_pipe()
	end

	local _, terr = uv.pipe_connect(self._handle, path, function(err)
		if err then
			return self:destroy(err)
		end
		self._connecting = false
		self:emit("connect")
		if callback then callback() end
	end)

	if terr then
		self:destroy(terr)
	end

	return self
end

function UnixSocket:destroy(exception, callback)
	callback = callback or function() end
	if self.destroyed == true or self._handle == nil then
		return callback()
	end

	self.destroyed = true
	self.readable = false
	self.writable = false

	if uv.is_closing(self._handle) then
		timer.setImmediate(callback)
	else
		uv.close(self._handle, function()
			self:emit("close")
			callback()
		end)
	end

	if exception then
		process.nextTick(function()
			self:emit("error", exception)
		end)
	end
end

function UnixSocket:getsockname()
	return uv.pipe_getsockname(self._handle)
end

local function connect(address, callback)
	local colon = find(address, ":", 1, true)

	if colon then -- host:port
		local host = sub(address, 1, colon - 1)
		local port = tonumber(sub(address, colon + 1))
		-- create a new tcp connection
		return net.createConnection(port, host, callback)
	end

	-- assume it is a unix domain socket
	local sock = UnixSocket:new()
	sock:connect(address, callback)
	return sock
end

return connect