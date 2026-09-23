-- Station screens drawn with the pack's own GUI textures (cut out by tools/images.py into
-- /assets/gui/). Every slot sits where the game draws it: coordinates are in texture pixels
-- (the top-left of the 16x16 item, as { arg, x, y }), and the screen is shown at 2x, like
-- minecraft.wiki's 32px icons.
-- Slots come from Module:Inventory slot, so aliases, animation and tooltips work as usual.
--
-- Used by Template:Crafting, Template:Cooking, Template:Smithing and Template:Stonecutter.

local slot = require( [[Module:Inventory slot]] ).slot

local p = {}

local FURNACE_SLOTS = { { 'Input', 56, 17 }, { 'Output', 116, 35 } }

local STATIONS = {
	crafting = {
		slots = {
			{ 'A1', 30, 17 }, { 'B1', 48, 17 }, { 'C1', 66, 17 },
			{ 'A2', 30, 35 }, { 'B2', 48, 35 }, { 'C2', 66, 35 },
			{ 'A3', 30, 53 }, { 'B3', 48, 53 }, { 'C3', 66, 53 },
			{ 'Output', 124, 35 },
		},
	},
	-- the pack renames the furnace and smoker; the screens show those names as their titles
	oven = { title = 'Oven', slots = FURNACE_SLOTS, burns = true },
	kiln = { title = 'Mud Kiln', slots = FURNACE_SLOTS, burns = true },
	blast = { title = 'Blast Furnace', slots = FURNACE_SLOTS, burns = true },
	-- a campfire has no screen: the item rests on the fire (see tools/images.py)
	kindling = { title = 'Kindling', slots = FURNACE_SLOTS, fire = true, arrow = 'oven' },
	smithing = {
		slots = { { 'Template', 8, 48 }, { 'Base', 26, 48 }, { 'Addition', 44, 48 }, { 'Output', 98, 48 } },
	},
	stonecutter = { title = 'Stonecutter', slots = { { 'Input', 20, 33 }, { 'Output', 143, 33 } } },
}

-- station names as the pack calls them (and as the generator passes them) -> screen
local ALIASES = {
	['crafting table'] = 'crafting', crafting = 'crafting',
	oven = 'oven', furnace = 'oven',
	['mud kiln'] = 'kiln', kiln = 'kiln', smoker = 'kiln',
	['blast furnace'] = 'blast', blast = 'blast', blasting = 'blast',
	kindling = 'kindling', campfire = 'kindling', ['soul kindling'] = 'kindling',
	['smithing table'] = 'smithing', smithing = 'smithing',
	stonecutter = 'stonecutter',
}

local function px( n )
	return ( n * 2 ) .. 'px'
end

local function place( node, x, y )
	return node:css{ left = px( x ), top = px( y ) }
end

local function getArgs( f )
	local args = {}
	if f == mw.getCurrentFrame() then
		for k, v in pairs( f:getParent().args ) do args[k] = v end
		for k, v in pairs( f.args ) do args[k] = v end
	else
		args = f
	end
	return args
end

-- Seconds of the progress animation: the recipe's real cooking time, within reason
local function progressTime( seconds )
	local s = tonumber( seconds )
	if not s or s <= 0 then
		return nil
	end
	return math.min( math.max( s, 1 ), 20 )
end

function p.screen( f )
	local args = getArgs( f )
	local key = ALIASES[mw.ustring.lower( mw.text.trim( args.station or args[1] or '' ) )]
	local st = STATIONS[key]
	if not st then
		return '<strong class="error">Module:Station: unknown station "' .. ( args.station or args[1] or '' ) .. '"</strong>'
	end

	local body = mw.html.create( 'div' )
		:addClass( 'mfui mfui-' .. key )
		:attr( 'role', 'figure' )

	local titleText = args.title or st.title
	if titleText and titleText ~= '' then
		local link = args.titlelink or titleText
		local title = place( body:tag( 'span' ):addClass( 'mfui-title' ), 8, 6 )
		if link == mw.title.getCurrentTitle().text then
			title:wikitext( titleText )
		else
			title:wikitext( '[[' .. link .. '|' .. titleText .. ']]' )
		end
	end

	local lit = st.burns or st.fire
	if st.burns then
		place( body:tag( 'span' ):addClass( 'mfui-lit' ), 56, 36 )
	end
	if st.fire then
		local soul = ( args.soul or '' ) ~= ''
		place( body:tag( 'span' ):addClass( 'mfui-campfire' ), 56, 37 )
			:attr( 'title', soul and 'Soul Kindling' or 'Kindling' )
			:addClass( soul and 'mfui-campfire-soul' or nil )
	end
	if lit then
		local progress = place( body:tag( 'span' ):addClass( 'mfui-progress mfui-progress-' .. ( st.arrow or key ) ), 79, 34 )
		-- the cooking time: time=, or the seconds a hand-written note starts with ("5 s, 0.35 XP")
		local t = progressTime( ( args.time or '' ) ~= '' and args.time or ( args.note or '' ):match( '^%s*([%d%.]+)%s*s' ) )
		if t then
			progress:css( 'animation-duration', t .. 's' )
		end
	end

	if key == 'crafting' and ( args.shapeless or '' ) ~= '' then
		place( body:tag( 'span' ):addClass( 'mfui-shapeless' ), 156, 5 )
			:attr( 'title', 'Shapeless: the ingredients can go anywhere in the grid.' )
	end
	if key == 'stonecutter' and ( args.Output or '' ) ~= '' then
		-- the result, selected in the stonecutter's list of recipes
		place( body:tag( 'span' ):addClass( 'mfui-stonecutter-selected' ), 52, 14 )
		place( body:tag( 'span' ):addClass( 'mfui-stonecutter-scroller' ), 119, 15 )
	end

	for _, pos in ipairs( st.slots ) do
		local name = pos[1]
		local item = mw.text.trim( args[name] or '' )
		if item ~= '' then
			local cell = place( body:tag( 'span' ):addClass( 'mfui-slot' ), pos[2], pos[3] )
			if name == 'Output' then
				cell:addClass( 'mfui-output' )
			end
			cell:wikitext( slot{ item, link = args[name .. 'link'], title = args[name .. 'title'] } )
		end
	end
	if key == 'stonecutter' and ( args.Output or '' ) ~= '' then
		local icon = mw.text.trim( args.Output ):gsub( ',%d+$', '' )
		place( body:tag( 'span' ):addClass( 'mfui-slot mfui-slot-plain' ), 52, 15 )
			:wikitext( slot{ icon, link = 'none' } )
	end

	return tostring( body )
end

-- A villager's offer as the trading screen lists it: what the villager wants (one or two stacks),
-- the arrow, and what it gives, on the pack's button. {{Trade|wants|wants 2|gives}}
local OFFER_SLOTS = { { 1, 5, 1 }, { 2, 35, 1 }, { 3, 68, 1 } }

function p.trade( f )
	local args = getArgs( f )
	local body = mw.html.create( 'span' ):addClass( 'mfui-trade' )
	for _, pos in ipairs( OFFER_SLOTS ) do
		local item = mw.text.trim( args[pos[1]] or '' )
		if item ~= '' then
			place( body:tag( 'span' ):addClass( 'mfui-slot' ), pos[2], pos[3] )
				:wikitext( slot{ item } )
		end
	end
	place( body:tag( 'span' ):addClass( 'mfui-trade-arrow' ), 55, 4 )
	return tostring( body )
end

return p
