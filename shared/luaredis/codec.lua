local tostring = tostring
local tonumber = tonumber
local byte = string.byte
local find = string.find
local sub = string.sub
local concat = table.concat

local function encode(list)
	local length = #list
	local parts = {"*" .. length .. "\r\n"}

	for i = 1, length do
		local str = tostring(list[i])
		parts[i + 1] = "$" .. #str .. "\r\n" .. str .. "\r\n"
	end

	return concat(parts, "", 1, length)
end

local decode
function decode(chunk, index)
	-- return nil: do nothing
	-- return item, offset
	local start = find(chunk, "\r\n", index, true)
	if not start then return end

	local first = byte(chunk, index)

	if first == 43 then -- "+" Simple string
		return sub(chunk, index + 1, start - 1), start + 2

	elseif first == 45 then -- "-" Error
		return {
			error = sub(chunk, index + 1, start - 1)
		}, start + 2

	elseif first == 58 then -- ":" Integer
		return tonumber(sub(chunk, index + 1, start - 1)), start + 2

	elseif first == 36 then -- "$" Bulk string
		local length = tonumber(sub(chunk, index + 1, start - 1))
		if length == -1 then
			return nil, start + 2
		end

		if #chunk < start + 3 + length then
			-- Not enough data to read yet
			return
		end

		return sub(chunk, start + 2, start + 1 + length), start + 4 + length

	elseif first == 42 then -- "*" Array
		local length = tonumber(sub(chunk, index + 1, start - 1))
		if length == -1 then
			return nil, start + 2
		end

		local array = {}
		local value
		index = start + 2
		for i = 1, length do
			value, index = decode(chunk, index)
			if not index then return end

			array[i] = value
		end

		return array, index
	end
end

return {
	encode = encode,
	decode = decode,
}