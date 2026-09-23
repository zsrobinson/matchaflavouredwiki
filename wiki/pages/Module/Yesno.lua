-- Used to evaluate args to booleans where applicable
--
-- Based on <https://runescape.wiki/w/Module:Yesno>
-- see page history there for contributors
--

return function( arg, default )
	if arg == nil then
		return default
	end

	arg = type( arg ) == 'string' and arg:lower() or arg

	if
		arg == true or
		arg == 'yes' or
		arg == 'y' or
		arg == 'true' or
		tonumber( arg ) == 1
	then
		return true
	end

	if
		arg == false or
		arg == 'no' or
		arg == 'n' or
		arg == 'false' or
		tonumber( arg ) == 0
	then
		return false
	end

	return default
end