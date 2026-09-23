-- In-game item tooltips: the name in its colour (explicit, or the rarity's) and the pack's lore
-- lines with their colours and custom-font glyphs, as the game draws them. The data is generated
-- from the pack's item components into Module:Tooltip/Data by tools/generate.py.
--
-- p.slotTip(name)  hidden tooltip content for an inventory slot (Module:Inventory slot); the
--                  hover tooltip itself is drawn by MediaWiki:Gadget-mfwTooltip.js
-- {{Tooltip|name}} a static tooltip box (item infoboxes)
--
-- Glyphs are white bitmaps that take their text's colour in game; here they are masks over the
-- glyph sheet (/assets/gui/glyphs.png, 16 glyphs of 8px per row, shown at 2x) filled with the
-- text colour, one font pixel wider than the glyph as the game spaces them.

local p = {}

local data
local function getData()
	data = data or mw.loadData( 'Module:Tooltip/Data' )
	return data
end

local function glyph( cp )
	local width = getData().glyphs[cp]
	if not width then
		return ''
	end
	local i = cp - 0xE000
	local pos = ( -( i % 16 ) * 16 ) .. 'px ' .. ( -math.floor( i / 16 ) * 16 ) .. 'px'
	return '<span class="mf-g"><span style="width:' .. ( width * 2 ) .. 'px;-webkit-mask-position:' ..
		pos .. ';mask-position:' .. pos .. '"></span></span>'
end

-- text with its glyphs, escaped for wikitext
local function renderText( text )
	local out, plain = {}, {}
	local function flush()
		if #plain > 0 then
			out[#out + 1] = mw.text.nowiki( mw.ustring.char( unpack( plain ) ) )
			plain = {}
		end
	end
	for cp in mw.ustring.gcodepoint( text ) do
		if cp >= 0xE000 and cp <= 0xE0FF then
			flush()
			out[#out + 1] = glyph( cp )
		else
			plain[#plain + 1] = cp
			if #plain >= 200 then
				flush()
			end
		end
	end
	flush()
	return table.concat( out )
end

local function run( r )
	local style = {}
	if r[2] ~= '' then
		style[#style + 1] = 'color:#' .. r[2]
	end
	if r[3]:find( 'i' ) then
		style[#style + 1] = 'font-style:italic'
	end
	if r[3]:find( 'b' ) then
		style[#style + 1] = 'font-weight:bold'
	end
	local text = renderText( r[1] )
	if #style == 0 then
		return text
	end
	return '<span class="format-custom" style="' .. table.concat( style, ';' ) .. '">' .. text .. '</span>'
end

-- The tooltip's lines as HTML (the name first), or nil when the item has nothing but a plain name.
function p.content( name, withPlainName )
	local entry = getData().items[name]
	if not entry and not withPlainName then
		return nil
	end
	entry = entry or {}
	local title = entry.t or name
	local titleStyle = entry.c and ( ' style="color:#' .. entry.c .. '"' ) or ''
	local out = { '<span class="minetip-title format-custom"' .. titleStyle .. '>' .. renderText( title ) .. '</span>' }
	for _, line in ipairs( entry.l or {} ) do
		local runs = {}
		for _, r in ipairs( line ) do
			runs[#runs + 1] = run( r )
		end
		out[#out + 1] = '<span class="minetip-line">' .. ( #runs > 0 and table.concat( runs ) or '&nbsp;' ) .. '</span>'
	end
	return table.concat( out )
end

function p.slotTip( name )
	local content = p.content( name )
	if not content then
		return nil
	end
	return '<span class="mf-tip" data-pagefind-ignore="all">' .. content .. '</span>'
end

function p.box( f )
	local args = f.args or f
	local name = mw.text.trim( args[1] or '' )
	local content = p.content( name, true )
	return '<div class="mf-tooltip" data-pagefind-ignore="all">' .. content .. '</div>'
end

return p
