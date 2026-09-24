-- Infobox for a page about a family of items (Fence Gate, Mattock, Banners), as minecraft.wiki draws one:
-- the picture cycles through the variants, and a row under it shows every variant's inventory slot.
-- {{Family infobox|Oak Fence Gate;Spruce Fence Gate;...|title=Fence Gate|type=Block|stackable=Yes (64)}}
-- Other named arguments are passed on to {{Infobox}} as rows.
local p = {}

function p.main( frame )
	local args = frame:getParent().args
	local members = {}
	for name in mw.text.gsplit( args[1] or '', '%s*;%s*' ) do
		if name ~= '' then
			members[#members + 1] = name
		end
	end
	local size = args.imagesize or '150px'
	local images, slots = {}, {}
	for i, name in ipairs( members ) do
		images[#images + 1] = string.format( '<span%s>[[File:%s.png|%s|link=|class=pixel-image]]</span>',
			i == 1 and ' class="animated-active"' or '', name, size )
		slots[#slots + 1] = frame:expandTemplate{ title = 'Slot', args = { name, link = 'none' } }
	end
	local infobox = {}
	for k, v in pairs( args ) do
		if type( k ) == 'string' and k ~= 'imagesize' then
			infobox[k] = v
		end
	end
	if #members > 0 then
		infobox.images = '<span class="animated">' .. table.concat( images ) .. '</span>'
		infobox.invslots = table.concat( slots )
	end
	return frame:expandTemplate{ title = 'Infobox', args = infobox }
end

return p
