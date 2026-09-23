-- from https://minecraft.wiki/w/Module:SpriteFile

local p = {}

function p.sprite( f )
	local args = f
	if f == mw.getCurrentFrame() then
		args = require( 'Module:ProcessArgs' ).merge( true )
	else
		f = mw.getCurrentFrame()
	end
	
	-- Default settings
	local default = {
		scale = 1,
		size = 16,
		align = 'text-top'
	}
	
	local id = mw.text.trim( tostring( args[1] or '' ) )
	if not args.keepcase then
		id = mw.ustring.lower( id ):gsub( '[%s%+]', '-' )
	end
	
	local link = ( args.link or '' )
	if mw.ustring.lower( link ) == 'none' then
		link = ''
	elseif link ~= '' then
		local linkPrefix = ( not link:find( '//' ) and args.linkprefix ) or ''
		link = linkPrefix .. link
	end
	
	local scale = args.scale or default.scale
	local height = ( args.height or args.size or default.size ) * scale
	local width = ( args.width or args.size or default.size ) * scale
	local size = width .. 'x' .. height .. 'px'
	
	local styles = {}
	if height ~= default.size then
		styles[#styles + 1] = 'height:' .. height .. 'px'
	end
	if width ~= default.size then
		styles[#styles + 1] = 'width:' .. width .. 'px'
	end
	
	local name = args.name or ''
	if name == 'InvSprite' then
		name = 'Invicon'
	end
	local file = name .. ' ' .. id .. ( name == '' and '' or '.png' )
	local altText = ''
	if link == '' then
		altText = file .. ': Sprite image for ' .. id .. ' in Minecraft'
	end
	if id == '' then
		file = 'Grid Unknown.png'
		altText = 'Unknown sprite image'
	end
	local sprite = mw.html.create( 'span' ):addClass( 'sprite-file' )
	local img = '[[File:' .. file .. '|' .. size .. '|link=' .. link .. '|alt=' .. altText .. '|class=pixel-image|' .. ( args.title or '' ) .. ']]'
	sprite:node( img )
	
	local align = args.align or default.align
	if align ~= default.align then
		styles[#styles + 1] = '--vertical-align:' .. align
	end
	styles[#styles + 1] = args.css
	
	sprite:cssText( table.concat( styles, ';' ) )
	
	local root
	local spriteText
	if args.text then
		if not args['wrap'] then
			root = mw.html.create( 'span' ):addClass( 'nowrap' )
		end
		spriteText = mw.html.create( 'span' ):addClass( 'sprite-text' ):wikitext( args.text )
		if args.title then
			spriteText:attr( 'title', args.title )
		end
		if link ~= '' then
			-- External link
			if link:find( '//' ) then
				spriteText = '[' .. link .. ' ' .. tostring( spriteText ) .. ']'
			else
				spriteText = '[[' .. link .. '|' .. tostring( spriteText ) .. ']]'
			end
		end
	end
	
	if not root then
		root = mw.html.create( '' )
	end
	root:node( sprite )
	if spriteText then
		root:node( spriteText )
	end
	
	return tostring( root )
end

function p.link( f )
	local args = f
	if f == mw.getCurrentFrame() then
		args = require( 'Module:ProcessArgs' ).merge( true )
	end
	
	local link = args[1]
	if args[1] and not args.id then
		link = args[1]:match( '^(.-)%+' ) or args[1]
	end
	local text
	if not args.notext then
		text = args.text or args[2] or link
	end
	
	args[1] = args.id or args[1]
	args.link = args.link or link
	args.text = text
	
	return p.sprite( args )
end

return p