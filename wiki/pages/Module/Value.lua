-- One of an item's numbers in running text, so prose follows the pack like the infobox does:
-- {{Value|Canned Golden Apples|heals}} → {{Hp|8}}. The values are generated from the pack's item
-- components and recipes into Module:Data/Values by tools/generate.py, already formatted once per
-- format; this module only picks the string (and expands {{Hp}} in it).
--
-- {{Value|<item>|<field>|effect=<Effect>|station=<Station>|format=<format>}}
--   heals          {{Hp|8}}          format=raw "8", hearts "4 hearts"
--   damage         {{Hp|6.5}}        format=raw "6.5"
--   attackspeed, miningspeed, durability, armor, toughness   the number
--   eat_time       "1.6 seconds"     format=raw "1.6"
--   level          effect=Absorption: "II"   format=raw "2", roman (past X too: "XXX")
--   duration       effect=Absorption: "2 minutes" (whole minutes) or "20 seconds"
--   cook_time      "15 seconds"; station=Oven when the stations differ
--   durations take format=clock "2:00", seconds "120 seconds", minutes "2 minutes",
--                  long "2 minutes 30 seconds", secs "120", ticks "2400"
--
-- An unknown item, field, effect, station or format is an error and puts the page in
-- [[Category:Pages with unknown values]]; tools/check_site.py and tools/lint_pages.py fail on it.

local p = {}

local function fail( msg )
	return '<strong class="error">Value: ' .. msg .. '</strong>[[Category:Pages with unknown values]]'
end

local function keys( t )
	local out = {}
	for k in pairs( t ) do
		if k ~= 1 then
			out[#out + 1] = k
		end
	end
	table.sort( out )
	return table.concat( out, ', ' )
end

function p.main( frame )
	local args = frame:getParent().args
	local item = mw.text.trim( args[1] or '' )
	local field = mw.text.trim( args[2] or '' )
	local effect = mw.text.trim( args.effect or '' )
	local station = mw.text.trim( args.station or '' )
	local format = mw.text.trim( args.format or '' )
	local values = mw.loadData( 'Module:Data/Values' )[item]
	if not values then
		return fail( 'no values for the item "' .. item .. '"' )
	end
	local key = field
	if effect ~= '' then
		key = field .. ':' .. effect
	elseif station ~= '' then
		key = field .. ':' .. station
	end
	local formats = values[key]
	if not formats then
		local have = {}
		for k in pairs( values ) do
			have[#have + 1] = k
		end
		table.sort( have )
		return fail( item .. ' has no "' .. key .. '" (it has: ' .. table.concat( have, ', ' ) .. ')' )
	end
	if formats.error then
		return fail( formats.error )
	end
	local text = formats[format == '' and 1 or format]
	if not text then
		return fail( 'no format "' .. format .. '" for ' .. key .. ' (formats: ' .. keys( formats ) .. ')' )
	end
	if text:find( '{{', 1, true ) then
		return frame:preprocess( text )
	end
	return text
end

return p
