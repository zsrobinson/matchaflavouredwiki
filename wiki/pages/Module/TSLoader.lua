-- from https://minecraft.wiki/w/Module:TSLoader

local p = {}

function p.call( name )
	if not name then
		return nil
	end
	return mw.getCurrentFrame():extensionTag{ name = "templatestyles", args = { src = name } }
end

function p.main( f )
	local args = f
	local frame = mw.getCurrentFrame()
	if f == frame then
		args = require( 'Module:ProcessArgs' ).merge( true )
	end
	return p.call( args[ 1 ] )
end

return p