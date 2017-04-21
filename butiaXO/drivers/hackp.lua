local device = _G
local string_byte=string.byte
local RD_VERSION = string.char(0x00)
local WRITE_PORT = 0x06
local PORT_IN = 0x07
local PORT_OUT = 0x08
local READ = 0x03
local LOW = 0x04
local HIGH = 0x05
local IN = 0x01
local OUT = 0x02

api={}
api.getVersion = {}
api.getVersion.parameters = {} -- no input parameters
api.getVersion.returns = {[1]={rname="version", rtype="int"}}
api.getVersion.call = function ()
	device:send(RD_VERSION) -- operation code 0 = get version
    local version_response = device:read(3) -- 3 bytes to read (opcode, data)
    if not version_response or #version_response~=3 then return -1 end
    local raw_val = (string.byte(version_response,2) or 0) + (string.byte(version_response,3) or 0)* 256
    return raw_val
end

api.read = {}
api.read.parameters = {[1]={rname="pin", rtype="int"}} 
api.read.returns = {[1]={rname="dato", rtype="int"}} -- value of pin if no error ocurred, -1 instead
api.read.call = function (pin)
    if (pin == nil) then return -1 end
    pin = tonumber(pin)
    if (pin < 0) or (pin > 7) then return -1 end
    local msg
    msg = string.char(READ,pin)
    device:send(msg)
    local ret = device:read(2)
    if ret == nil or #ret~=2 then return -3 end
    return string.byte(ret,2) or 0
end

api.write = {}
api.write.parameters = {[1]={rname="pin", rtype="int"},[2]={rname="value", rtype="int"}} 
api.write.returns = {[1]={rname="dato", rtype="int"}} -- 1 if no error ocurred, -1 instead
api.write.call = function (pin,value)
    if (value == nil) or (pin == nil) then return -1 end
    pin, value = tonumber(pin), tonumber(value)
    if ((value ~= 0) and (value ~= 1)) or (pin < 0) or (pin > 7) then return -1 end
    local msg
    if (value == 0) then
        msg = string.char(LOW,pin)
    else 
        msg = string.char(HIGH,pin)
    end
    device:send(msg)
    local ret = device:read(1)
    return 1
end

api.setMode = {}
api.setMode.parameters = {[1]={rname="pin", rtype="int"},[2]={rname="mode", rtype="int"}} 
api.setMode.returns = {[1]={rname="dato", rtype="int"}} -- 1 if no error ocurred, -1 instead
api.setMode.call = function (pin,mode)
    if (mode == nil) or (pin == nil) then return -1 end
    pin, mode = tonumber(pin), tonumber(mode)
    if ((mode ~= 0) and (mode ~= 1)) or (pin < 0) or (pin > 7) then return -1 end
    local msg
    if (mode == 0) then 
        msg = string.char(OUT,pin)
    else 
        msg = string.char(IN,pin)
    end
    device:send(msg)
    local ret = device:read(1)
    return 1
end

api.changePortDir = {}
api.changePortDir.parameters = {[1]={rname="mode", rtype="int"}} 
api.changePortDir.returns = {[1]={rname="dato", rtype="int"}} -- 1 if no error ocurred, -1 instead
api.changePortDir.call = function (mode)
    if (mode == nil) then return -1 end
    mode = tonumber(mode)
    if (mode ~= 0) and (mode ~= 1) then return -1 end
    local msg
    if (mode == 0) then 
        msg = string.char(PORT_IN,mode)
    else 
        msg = string.char(PORT_OUT,mode)
    end
    device:send(msg)
    local ret = device:read(1)
    return 1
end

api.writePort = {}
api.writePort.parameters = {[1]={rname="value", rtype="int"}} 
api.writePort.returns = {[1]={rname="dato", rtype="int"}} -- 1 if no error ocurred, -1 instead
api.writePort.call = function (value)
    if (value == nil) then return -1 end
    value = tonumber(value)
    if (value < 0) or (value > 255) then return -1 end --FIXME control the value
    local msg
    msg = string.char(WRITE_PORT,value)
    device:send(msg)
    local ret = device:read(1)
    return 1
end
