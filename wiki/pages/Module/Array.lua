-- from https://runescape.wiki/w/Module:Array
--[[
====================================
RSWiki Array Module
====================================

A comprehensive library for array operations in MediaWiki Lua modules.
This module provides immutable array operations with performance optimizations for various
array types including standard Lua arrays, proxy tables, and sparse arrays.

Features:
- Immutable array operations with copy-on-write semantics
- Smart optimization for different array types (standard vs proxy)
- Comprehensive functional programming utilities (map, filter, reduce, etc.)
- Performance-optimized iteration patterns
- Type-safe operations with comprehensive error checking
- Integration with MediaWiki's proxy table system

--]]

local libraryUtil = require('libraryUtil')
local checkType = libraryUtil.checkType
local checkTypeMulti = libraryUtil.checkTypeMulti

---@class Array<T>: { [integer]: T }
---@operator call(any[]): Array
---@operator concat(any[]): Array
---@operator concat(number|string|function): string
---@operator unm: Array
---@operator add(number|number[]|Array): Array
---@operator sub(number|number[]|Array): Array
---@operator mul(number|number[]|Array): Array
---@operator div(number|number[]|Array): Array
---@operator pow(number|number[]|Array): Array

local Array = {
    pop = table.remove
}
Array.__index = Array

setmetatable(Array, {
    __index = table,
    __call = function(_, arr)
        return Array.new(arr)
    end
})

---Calculates the length of arrays including proxy arrays
---
---This function provides optimized length calculation for different array types:
---- Standard arrays: Uses native # operator (O(1))
---- Proxy arrays: Uses exponential search followed by binary search (O(log n))
---- Empty arrays: Quick detection and return (O(1))
---
---@example <caption> Length calculation examples </caption>
---local std_array = {1, 2, 3}  -- Standard array
---local proxy_array = setmetatable({[1] = 'a', [2] = 'b'}, proxy_mt)
---print(len(std_array))    -- 3 (O(1) operation)
---print(len(proxy_array))  -- 2 (O(log n) operation)
---print(len({}))           -- 0 (O(1) early detection)
---@param arr Array<any> # Array to measure (can be standard array or proxy table)
---@return integer length The number of elements in the arrayfin
function Array.len(arr)
    local l = #arr
    if l == 0 then
        if arr[1] ~= nil then
            -- Exponential search to find length of proxy table
            local low = 1
            local high = 1
            local ceil = math.ceil
            while arr[high] ~= nil do
                high = high * 2
            end
            while low ~= high do
                local m = ceil((low + high) / 2)
                if arr[m] == nil then
                    high = m - 1
                else
                    low = m
                end
            end
            return low
        else
            return 0
        end
    else
        return l
    end
end

local len = Array.len

---Transform array elements using a mapping function
---
---Creates a new array by applying the transformation function to every element of the input array. This operation is immutable - the original array is not modified. Supports filtering during mapping by returning nil for unwanted elements.
---
---## Performance
---- Time complexity: O(n) where n is the array length
---- Space complexity: O(m) where m is the number of non-nil results
---- Uses cached array length and optimized result building
---- Automatically filters out nil results for sparse result arrays
---
---@example <caption> Basic transformation </caption>
---local numbers = {1, 2, 3, 4, 5}
---local doubled = Array.map(numbers, function(x)
---    return x * 2
---end)  -- {2, 4, 6, 8, 10}
---
---local words = {"hello", "world", "test"}
---local lengths = Array.map(words, function(word)
---    return #word
---end)  -- {5, 5, 4}
---
---@example <caption> Map with filtering (nil values are excluded) </caption>
---local mixed = {1, 2, 3, 4, 5}
---local evenDoubled = Array.map(mixed, function(x)
---    if x % 2 == 0 then
---        return x * 2
---    else
---        return nil  -- This will be filtered out
---    end
---end)  -- {4, 8}
---
---@example <caption> Using index parameter </caption>
---local indexed = Array.map(numbers, function(value, index)
---    return string.format('%d: %s', index, value)
---end)  -- {"1: 1", "2: 2", "3: 3", "4: 4", "5: 5"}
---@generic T, U
---@param arr Array<`T`> # Array to transform
---@param fn fun(elem: T, i?: integer): `U` # Transformation function
---@return Array<U> # New array containing transformed elements
function Array.map(arr, fn)
    checkType('Module:Array.map', 1, arr, 'table')
    checkType('Module:Array.map', 2, fn, 'function')

    local l = 0
    local r = {}
    local array_len = len(arr)
    for i = 1, array_len do
        local tmp = fn(arr[i], i)
        if tmp ~= nil then
            l = l + 1
            r[l] = tmp
        end
    end
    return setmetatable(r, getmetatable(arr))
end

return Array