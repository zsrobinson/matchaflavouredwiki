-- from https://runescape.wiki/w/Module:Mw.html%20extension
local p = {}
local checkType = require( 'libraryUtil' ).checkType
local mwHtml = getmetatable( mw.html.create() ).__index  -- Trick to get acces to the mw.html class
local stack = {}  -- Used to keep track of nested IF-END tags
local noOp = {}  -- This object is returned by IF(false) tag

function mwHtml:addClassIf( cond, ... )
    if cond then
        return self:addClass( ... )
    else
        return self
    end
end

function mwHtml:tagIf( cond, ... )
    if cond then
        return self:tag( ... )
    else
        return self
    end
end

function mwHtml:wikitextIf( cond, ... )
    if cond then
        return self:wikitext( ... )
    else
        return self
    end
end

function mwHtml:doneIf( cond )
    if cond then
        return self:done()
    else
        return self
    end
end

function mwHtml:attrIf( cond, ... )
    if cond then
        return self:attr( ... )
    else
        return self
    end
end

function mwHtml:cssIf( cond, ... )
    if cond then
        return self:css( ... )
    else
        return self
    end
end

function mwHtml:na()
    return self:td()
            :attr( 'data-sort-value', 0 )
            :attr( 'class', 'table-na' )
            :wikitext( '<small>N/A</small>' )
        :done()
end

function mwHtml:naIf( cond )
    if cond then
        return self:na()
    else
        return self
    end
end

local function addValues( self, settings )
    -- wikitext and addClass are no-ops when their argument is nil
    self:wikitext( settings[1] or settings.wikitext )
    self:addClass( settings.class or settings.addClass )

    if settings.attr then
        if settings.attr[1] and settings.attr[2] then
            self:attr( settings.attr[1], settings.attr[2] )
        else
            self:attr( settings.attr )
        end
    end

    if settings.css then
        if settings.css[1] and settings.css[2] then
            self:css( settings.css[1], settings.css[2] )
        else
            self:css( settings.css )
        end
    end

    if settings.cssText then
        self:cssText( settings.cssText )
    end
end

function mwHtml:tr( settings )
    if self.tagName == 'tr' then
        self = self:done():tag( 'tr' )
    elseif self.tagName == 'th' or self.tagName == 'td' then
        self = self:done():done():tag( 'tr' )
    else
        self = self:tag( 'tr' )
    end

    if type( settings ) == 'table' then
        addValues( self, settings )
    end

    return self
end

function mwHtml:th( settings )
    if self.tagName == 'th' or self.tagName == 'td' then
        self = self:done():tag( 'th' )
    else
        self = self:tag( 'th' )
    end

    if type( settings ) == 'table' then
        addValues( self, settings )
    else
        self = self:wikitext( settings )
    end

    return self
end

function mwHtml:td( settings )
    if self.tagName == 'th' or self.tagName == 'td' then
        self = self:done():tag( 'td' )
    else
        self = self:tag( 'td' )
    end

    if type( settings ) == 'table' then
        addValues( self, settings )
    else
        self = self:wikitext( settings )
    end

    return self
end

-- nicely formatted lists
function mwHtml:tdl( settings )
    if self.tagName == 'th' or self.tagName == 'td' then
        self = self:done():tag( 'td' )
    else
        self = self:tag( 'td' )
    end

    if type( settings ) == 'table' then
        addValues( self, settings )
    else
        self = self:wikitext( "\n"..settings )
    end

    return self
end

function mwHtml:IF( cond )
    if cond then
        table.insert( stack, { obj=noOp, trueCaseCompleted=true } )
        return self
    else
        table.insert( stack, { obj=self, trueCaseCompleted=false } )
        return noOp
    end
end

function mwHtml:ELSEIF( cond )
    if #stack == 0 then error( 'Missing IF tag', 2 ) end
    local last = stack[#stack]

    if cond and not last.trueCaseCompleted then
        last.trueCaseCompleted = true
        local res = last.obj
        last.obj = noOp
        return res
    else
        if self ~= noOp then
            last.obj = self
        end
        return noOp
    end
end

function mwHtml:ELSE()
    return self:ELSEIF( true )
end

function mwHtml:END()
    if #stack == 0 then error( 'Missing IF tag', 2 ) end

    local res = table.remove( stack )  -- Pop element from the end
    if res.obj == noOp then
        return self
    else
        return res.obj
    end
end

---Adds a table cell with content if it exists and does not match none_values, or an N/A cell otherwise
---@param content any The content to check and potentially add
---@param none_values? table Optional table of values to treat as none/empty
---@return self
function mwHtml:addOrNa(content, none_values)
    none_values = none_values or {"None"}

    -- Check if content is nil or matches none values
    local is_empty = content == nil
    if not is_empty and type(none_values) == "table" then
        for _, none_value in ipairs(none_values) do
            if content == none_value then
                is_empty = true
                break
            end
        end
    end

    if is_empty then
        return self:na()
    else
        return self:td(content)
    end
end

function mwHtml:exec( func, ... )
    checkType( 'exec', 1, func, 'function' )
    return func( self, ... )
end

function p.addFunction( func, name )
    checkType( 'addFunction', 1, func, 'function' )
    checkType( 'addFunction', 2, name, 'string' )
    mwHtml[name] = func
end

mwHtml.If = mwHtml.IF
mwHtml.Elseif = mwHtml.ELSEIF
mwHtml.Else = mwHtml.ELSE
mwHtml.End = mwHtml.END

noOp.IF = mwHtml.IF
noOp.If = mwHtml.IF
noOp.ELSEIF = mwHtml.ELSEIF
noOp.Elseif = mwHtml.ELSEIF
noOp.ELSE = mwHtml.ELSE
noOp.Else = mwHtml.ELSE
noOp.END = mwHtml.END
noOp.End = mwHtml.END
setmetatable( noOp, {
    __index = function( self )
        return self
    end,
    __call = function( self )
        return self
    end,
    __tostring = function()
        error( 'Attempting to convert no-op object into a string. Check for unbalanced IF-END tags', 2 )
    end,
    __concat = function()
        error( 'Attempting to concatenate a no-op object. Check for unbalanced IF-END tags', 2 )
    end
} )

return p