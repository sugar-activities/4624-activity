#!/usr/bin/lua

local socket = require("socket")

--local host, port = "192.168.10.1", 2009
local host, port = "localhost", 2009

local client = assert(socket.connect(host, port))
client:settimeout(nil) --blocking

local function send(s)
--	print("sending", s)
	client:send(s.."\n")
	local ret = client:receive()
--	print("ret:", ret)
	return ret
end

raw_val = send("LIST")
_, pos = string.find(raw_val, "led:")

if pos ~= nil then
    port = string.sub(raw_val,pos+1,pos+1)  -- get port number
    while true do
	    print (send("CALL led:"..port.." turnOn"))
	    socket.sleep(0.5)
	    print (send("CALL led:"..port.." turnOff"))
	    socket.sleep(0.5)
    end
else
     print("err::No led connected.")
end
