-- from https://minecraft.wiki/w/Module:Inventory_slot

local p = {}

-- Internationalization data
local i18n = {
	-- Name formats for pages and files
	filename = '$1',
	
	-- Dependencies
	moduleAliases = [[Module:Inventory slot/Aliases]],
	
	-- List of special prefixes which should be handled by
	-- other modules (such as being moved outside links)
	-- When localizing, you might want to use a separate list of patterns
	-- matching the prefixes’ grammatical forms depending on the language
	prefixes = {
		any = 'Any',
		matching = 'Matching',
		damaged = 'Damaged',
		unwaxed = 'Unwaxed',
	},
	
	-- List of suffixes that are usually stripped from links and tooltips
	suffixes = {
		rev = 'Revision %d+',
		-- berev = 'BE%d+',
		-- jerev= 'JE%d+',
		be = 'BE',
		lce = 'LCE',
		sm = 'SM',
		damage = '%d+'
	},
}
p.i18n = i18n

-- Global dependencies and constants
local aliases = mw.loadData( i18n.moduleAliases )
local pageName = mw.title.getCurrentTitle().text
local vanilla = { v = 1, vanilla = 1, mc = 1, minecraft = 1 }

-- Auxilliary functions --

-- Performs a simple recursive clone of a table’s values.
-- Probably exists due to mw.clone() being unusable on tables from mw.loadData()
-- at the time (see the link to help.fandom.com above)
local function cloneTable( origTable )
	local newTable = {}
	for k, v in pairs( origTable ) do
		if type( v ) == 'table' then
			v = cloneTable( v )
		end
		newTable[k] = v
	end
	return newTable
end

-- Merges a list, or inserts a string or table into a table,
-- depending on what the second argument happens to be
local function mergeList( parentTable, content )
	local i = #parentTable + 1
	if content[1] then
		-- Merge list into table
		for _, v in ipairs( content ) do
			parentTable[i] = v
			i = i + 1
		end
	else
		-- Add strings or tables to table
		parentTable[i] = content
	end
end

-- Creates the HTML node for a given item.
-- The actual icon file is found and added here
local function makeItem( frame, args )
	local item = ( mw.html.create('span')
		:addClass('invslot-item')
		:addClass(args.imgclass)
		:cssText(args.imgstyle)
	)
	
	if (frame.name or '') == '' then
		-- Empty frame, no icon to add
		return item
	end
	
	-- Frame parameters
	local title = frame.title or mw.text.trim( args.title or '' )
	local name = frame.name
	local num = frame.num
	local description = frame.text
	
	-- Split the extension out of the frame’s name
	local extension
	if name:match('%.gif') or name:match('%.png') then
		extension = name:sub(-4)
		name = name:sub(0, -5)
	elseif name:match('%.webp') then
		extension = '.webp'
		name = name:sub(0, -6)
	else
		extension = '.png'
	end
	
	-- Determine the file name
	local img
	img = i18n.filename:gsub( '%$1', name) .. extension

	-- Strip suffixes out
	for _, suffix in pairs( i18n.suffixes ) do
		name = name:gsub( ' ' .. suffix .. '$', '' )
	end
	
	-- Determine the link’s target
	local link = args.link or ''
	if link == '' then
		link = name:gsub( '^' .. i18n.prefixes.damaged .. ' ', '' )
	elseif link:lower() == 'none' then
		-- Disable the link
		link = nil
	end
	if link and link:gsub('^%l', string.upper) == pageName then
		link = nil
	end
	
	-- Tooltip titles. If JavaScript is not enabled, the slot will gracefully
	-- degrade to a simplified title without minetip formatting
	local formattedTitle
	local plainTitle
	if title == '' then
		-- If the title is not set, default to the slot’s name
		plainTitle = name
	elseif title:lower() ~= 'none' then
		-- Special character escapes
		plainTitle = title:gsub( '\\\\', '&#92;' ):gsub( '\\&', '&#38;' )
		
		-- The default title will have special formatting code stripped out
		local formatPatterns = {'&[0-9a-jl-qs-vyzr]', '&#%x%x%x%x%x%x', '&$%x%x%x'}
		for _, formatPattern in ipairs( formatPatterns ) do
			if plainTitle:match( formatPattern ) then
				formattedTitle = title
				plainTitle = plainTitle:gsub( formatPattern, '' )
			end
		end
		
		if plainTitle == '' then
			-- If the title field only has formatting code, the frame’s name
			-- is automatically used. For minetips it’s done by JavaScript
			-- by appending the plain title.
			plainTitle = name
		else
			-- Re-encode the 
			plainTitle = plainTitle:gsub( '&#92;', '\\' ):gsub( '&#38;', '&' )
		end
	elseif link then
		-- Disable the tooltip that will otherwise appear with a link
		formattedTitle = ''
	end
	
	-- Minetips are controlled by custom HTML attributes.
	-- See [[MediaWiki:Common.js]] for implementation in JavaScript
	item:attr{
		['data-minetip-title'] = formattedTitle,
		['data-minetip-text'] = description
	}
	
	-- & is re-escaped because mw.html treats attributes as plain text,
	-- but MediaWiki doesn’t.
	local escapedTitle = ( plainTitle or '' ):gsub( '&', '&#38;' )
	
	-- Alt text
	local altText = img .. ': Inventory sprite for ' .. name .. ' in Minecraft as shown in-game'
	if link then
		altText = altText .. ' linking to ' .. link
	end
	if formattedTitle or plainTitle or link then
		altText = altText .. ' with description: ' .. ( formattedTitle or plainTitle or link )
		if description then
			altText = altText .. ' ' .. description:gsub( '/', ' ' )
		end
		altText = altText:gsub( '&[0-9a-jl-qs-wr]', '' )
	end
	
	-- Add the image
	item:addClass( 'invslot-item-image' )
		:wikitext( '[[File:', img, '|32x32px|link=', link or '', '|alt=', altText, '|', escapedTitle, ']]' )
	
	-- Add the stack number, if present and in 2-999 range
	if num and num > 1 and num < 1000 then
		if link then
			item:wikitext( '[[', link, '|' )
		end
		local number = item
			:tag( 'span' )
				:addClass( 'invslot-stacksize' )
				:attr{ title = plainTitle }
				:wikitext( num )
		if args.numstyle then
			number:cssText( args.numstyle )
		end
		if link then
			item:wikitext( ']]' )
		end
	end
	
	-- The HTML node is now ready
	return item
end

-- Publicly available functions --

-- Main entry point: Creates the whole slot
function p.slot( f )
	-- Incoming arguments
	local args = f.args or f
	if f == mw.getCurrentFrame() and args[1] == nil then
		args = f:getParent().args
	end
	
	-- TODO: Add support for unexpanded frame sequences in table format
	if not args.parsed then
		-- Assumed to be a string, trim it
		args[1] = mw.text.trim( args[1] or '' )
	end

	-- Get the frame sequence in table format
	local frames
	if args.parsed then
		-- Already parsed in some other module, such as Recipe table
		frames = args[1]
	elseif args[1] ~= '' then
		frames = p.parseFrameText( args[1], false )
	end
	
	-- Create the slot node and add applicable styles
	local body = mw.html.create( 'span' ):addClass( 'invslot' ):css{ ['vertical-align'] = args.align }
	
	-- Default background
	if ( args.default or '' ) ~= '' then -- default background
		body:addClass( 'invslot-default-' .. string.lower( args.default ):gsub( ' ', '-' ) )
	end
	
	-- Custom styles
	body:addClass( args.class )
	body:cssText( args.style )
	
	--mw.logObject( frames )
	if not frames or #frames == 0 then
		-- Empty slot
		return tostring( body )
	end
	
	-- If we have multiple frames, set up the animation and select the active
	-- frame
	local activeFrame = 0
	if #frames > 1 then
		body:addClass( 'animated' )
		activeFrame = 1
	end
	
	-- Add the frames
	for i, frame in ipairs( frames ) do
		local item
		if frame[1] then
			-- This is a subframe container. Each animation cycle of the slot
			-- will show a subframe, one at a time.
			
			-- Create a container node for subframes
			item = body:tag( 'span' ):addClass( 'animated-subframe' )
			
			-- Subframe containers have at least two subframes by definition
			local subActiveFrame = 1
			
			-- Add subframes to the note
			for sI, sFrame in ipairs( frame ) do
				local sItem = makeItem( sFrame, args )
				item:node( sItem )
				
				-- Set this subframe as active
				if sI == subActiveFrame then
					sItem:addClass( 'animated-active' )
				end
			end
		else
			-- A simple frame
			item = makeItem( frame, args )
			body:node( item )
		end
		
		if i == activeFrame then
			-- Set this frame as active, if we have multiple of them. Otherwise,
			-- the active frame id is zero, before Lua’s starting index of one,
			-- and this CSS class is never added.
			item:addClass( 'animated-active' )
		end
	end
	
	-- The slot is ready
	return tostring( body )
end

-- Splits a given text into fragments separated by semicolons that are not
-- inside square brackets. Originally written by AttemptToCallNil for the
-- Russian wiki.
-- It processes the text byte-by-byte due to being written under a much stricter
-- Lua runtime budget, with no LuaSandbox and mw.text.split being unperformant.
-- See also https://help.fandom.com/wiki/Extension:Scribunto#Known_issues_and_solutions
function p.splitOnUnenclosedSemicolons(text)
	local semicolon, lbrace, rbrace = (";[]"):byte(1, 3)
	local nesting = false
	local splitStart = 1
	local frameIndex = 1
	local frames = {}
	
	for index = 1, text:len() do
		local byte = text:byte(index)
		if byte == semicolon and not nesting then
			frames[frameIndex] = text:sub(splitStart, index - 1)
			frameIndex = frameIndex + 1
			splitStart = index + 1
		elseif byte == lbrace then
			assert(not nesting, "Excessive square brackets found")
			nesting = true
		elseif byte == rbrace then
			assert(nesting, "Unbalanced square brackets found")
			nesting = false
		end
	end
	assert(not nesting, "Unbalanced square brackets found")
	frames[frameIndex] = text:sub(splitStart, text:len())
	
	for index = 1, #frames do
		frames[index] = (frames[index]:gsub("^%s+", ""):gsub("%s+$", "")) -- faster than mw.text.trim
	end
	
	return frames
end

-- Parses the frame text into a table of frames and subframes
-- and expanding aliases (and optionally retaining a reference)
-- Alias references are used in [[Module:Recipe table]] to create links and
-- lists of unique items.
function p.parseFrameText( framesText, aliasReference )
	-- Frame sequences
	local frames = {}
	local subframes = {}
	
	-- Is the current frame a subframe?
	local subframe
	
	-- The list of expanded aliases, will be added to the frame sequence
	-- if aliasReference is set to true AND if there are any aliases to expand.
	local expandedAliases
	
	-- Split the frame string by semicolons (respecting square brackets)
	local splitFrames = p.splitOnUnenclosedSemicolons( framesText )
	
	-- Iterate on frame fragments
	for i, frameText in ipairs( splitFrames ) do
		-- Subframes are grouped by curly braces
		frameText = frameText:gsub( '^%s*{%s*', function()
			subframe = true
			return ''
		end )
		
		if subframe then
			-- Closing brace found
			frameText = frameText:gsub( '%s*}%s*$', function()
				subframe = 'last'
				return ''
			end )
		end
		
		-- Convert the frame text into table format
		local frame = p.makeFrame( frameText )
		
		-- Alias processing
		local newFrame = frame
		if aliases then
			local id = frame.name

			local alias = aliases and aliases[id]
			if alias then
				-- Alias found, expand it
				newFrame = p.getAlias( alias, frame )
				
				-- Save the alias references, if asked
				if aliasReference then
					-- The alias data includes the original unexpanded frame
					-- and the number of frames it has expanded to.
					-- The alias reference table is not sequential — indices for
					-- each alias data object correspond to that alias’ first
					-- (or only) expanded frame. Which is not added to the frame
					-- sequence yet
					local curFrame = #frames + 1
					local aliasData = { frame = frame, length = #newFrame }
					if subframe then
						-- Subframe containers will have their own
						-- alias reference tables
						if not subframes.aliasReference then
							subframes.aliasReference = {}
						end
						subframes.aliasReference[#subframes + 1] = aliasData
					else
						if not expandedAliases then
							expandedAliases = {}
						end
						expandedAliases[curFrame] = aliasData
					end
				end
			end
		end
		-- Alias processing ends here
		
		-- Add frames
		if subframe then
			-- Add the frame to the current subframe container
			mergeList( subframes, newFrame )

			if subframe == 'last' then
				if #subframes == 1 or #splitFrames == i and #frames == 0 then
					-- If the subframe container only has one expanded frame or
					-- is the only frame in the whole sequence, its contents are
					-- extracted into the main frame sequence
					local lastFrame = #frames
					mergeList( frames, subframes )

					-- Append alias reference data, if present
					if aliasReference and subframes.aliasReference then
						if not expandedAliases then
							expandedAliases = {}
						end
						for i, aliasRefData in pairs(subframes.aliasReference) do
							expandedAliases[lastFrame + i] = aliasRefData
						end
					end
				else
					-- Add the subframe container to the frame sequence
					table.insert( frames, subframes )
				end
				
				-- Finished processing this subframe container
				subframes = {}
				subframe = nil
			end
		else
			-- Add the expanded frame(s) to the frame sequence
			mergeList( frames, newFrame )
		end
	end
	
	-- Add the alias reference, if we’re compiling one
	frames.aliasReference = expandedAliases
	
	-- The frame sequence is ready
	return frames
end

-- Applies parameters from the parent frame (such as title or text)
-- to the alias’ expansion
function p.getAlias( aliasFrames, parentFrame )
	-- If alias is just a name, return the parent frame with the new name
	if type( aliasFrames ) == 'string' then
		local expandedFrame = mw.clone( parentFrame )
		expandedFrame.name = aliasFrames
		return { expandedFrame }
	end
	
	-- Single frame alias, put in list
	if aliasFrames.name then
		aliasFrames = { aliasFrames }
	end
	
	-- Common case: group alias
	local expandedFrames = {}
	for i, aliasFrame in ipairs( aliasFrames ) do
		local expandedFrame
		if type( aliasFrame ) == 'string' then
			-- Simple expansion frame in string format
			expandedFrame = { name = aliasFrame }
		else
			-- Expansion frame in table format
			-- As it’s loaded with mw.loadData, it must be cloned
			-- before changing
			expandedFrame = cloneTable( aliasFrame )
		end
		
		-- Apply the parent frame’s settings
		expandedFrame.title = parentFrame.title or expandedFrame.title
		expandedFrame.num = parentFrame.num or expandedFrame.num
		expandedFrame.text = parentFrame.text or expandedFrame.text

		expandedFrames[i] = expandedFrame
	end
	
	return expandedFrames
end

-- Convert the frame object back into string format
function p.stringifyFrame( frame )
	if not frame.name then
		return ''
	end
	return string.format(
		'[%s]%s:%s,%s[%s]',
		frame.title or '',
		'Minecraft',
		frame.name,
		frame.num or '',
		frame.text or ''
	)
end

-- Convert the frame sequence into string format
function p.stringifyFrames( frames )
	for i, frame in ipairs( frames ) do
		if frame[1] then
			-- Subframe container
			-- As the format and the syntax are the same, process it recursively
			frames[i] = '{' .. p.stringifyFrames( frame ) .. '}'
		else
			frames[i] = p.stringifyFrame( frame )
		end
	end
	return table.concat( frames, ';' )
end

-- Converts the frame text into a frame object
-- Full syntax: [Title]:Name,Number[Text]
function p.makeFrame( frameText )
	-- Simple frame with no parts
	if not frameText:match( '[%[:,]' ) then
		return {
			name = mw.text.trim( frameText ),
		}
	end
	
	-- Complex frame
	local frame = {}
	
	-- Title
	local title, rest = frameText:match( '^%s*%[([^%]]*)%]%s*(.*)' )
	if title then
		frame.title = title
		frameText = rest
	end
	
	-- Additional tooltip text
	local rest, text = frameText:match( '([^%]]*)%s*%[([^%]]*)%]%s*$' )
	if text then
		frame.text = text
		frameText = rest
	end

	-- Name and stack size
	-- The pattern will match the last comma, so you can use names with commas
	-- like so: “Potatiesh, Greatstaff of the Peasant,1”
	local name, num = frameText:match('(.*),%s*(%d+)')
	if num then
		-- Number is set
		frame.name = mw.text.trim(name)
		frame.num = math.floor(num)
		if frame.num < 2 then
			frame.num = nil
		end
	else
		-- No number
		frame.name = mw.text.trim(frameText)
	end
	
	-- The frame object is ready
	return frame
end

-- This line should be the last one:
return p