local checkType, checkTypeForNamedArg
do
	local _libraryUtil = require("libraryUtil");
	checkType = _libraryUtil.checkType;
	checkTypeForNamedArg = _libraryUtil.checkTypeForNamedArg;
end

local p = {}

function p.is_empty(arg)
	return not string.find(arg or '', '%S')
end

function p.default_to(arg, default)
	if string.find(arg or '', '%S') then
		return arg
	else
		return default
	end
end

function p.defaults(args)
	checkType("defaults", 1, args, "table");
	local ret = {}
	for i, v in ipairs(args) do
		checkTypeForNamedArg("defaults", i, v, "table");
		ret[i] = p.default_to(v[1], v[2]);
	end
	return unpack(ret, 1, #args);
end

function p.has_content(arg)
	return string.find(arg or '', '%S')
end

function p.ucflc(arg)
	if not arg or arg:len() == 0 then
		return nil
	elseif arg:len() == 1 then
		return arg:upper()
	else
		return arg:sub(1,1):upper() .. arg:sub(2):lower()
	end
end

return p