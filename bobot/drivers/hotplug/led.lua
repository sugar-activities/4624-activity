local device = _G

local RD_VERSION=string.char(0x00)
local TURN_ON=string.char(0x01)
local TURN_OFF=string.char(0x02)
local string_byte=string.byte

-- description: lets us know grey module's version
api={}
api.getVersion = {}
api.getVersion.parameters = {} -- no input parameters
api.getVersion.returns = {[1]={rname="version", rtype="int"}}
api.getVersion.call = function ()
	device:send(RD_VERSION) -- operation code 0 = get version
    local version_response = device:read(3) -- 3 bytes to read (opcode, data)
    if not version_response or #version_response~=3 then return -1 end
    local raw_val = (string_byte(version_response,2) or 0) + (string_byte(version_response,3) or 0)* 256
    return raw_val
end

-- description: turn led on or off
-- input: 0 or 1
-- output: if sucess 1
api.turn = {}
api.turn.parameters = {[1]={rname="par1", rtype="int"}} -- no input parameters
api.turn.returns = {[1]={rname="ret1", rtype="int"}} 
api.turn.call = function (value)
    value = tonumber(value)
    if value == nil or value ~= 0 and value ~= 1 then return -1 end
    if value == 0 then
        device:send(TURN_OFF)
    else
        device:send(TURN_ON)
    end
	return 1
end
