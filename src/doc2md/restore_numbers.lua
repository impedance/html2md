-- Pandoc Lua filter to restore chapter numbers from table of contents
-- This filter extracts numbering information from TOC links and applies them to headings

local toc_map = {}
local should_remove_toc = true  -- Flag to remove TOC block after processing

-- Helper function to extract number from TOC text
local function extract_number(text)
    local number = string.match(text, "^(%d+[%.%d]*)%s+")
    return number
end

-- Helper function to clean heading text (remove existing numbers if any)
local function clean_heading_text(text)
    return string.gsub(text, "^%d+[%.%d]*%s*", "")
end

-- First pass: collect TOC information
function collect_toc_info(elem)
    if elem.tag == "Link" then
        local href = elem.target
        local text_content = pandoc.utils.stringify(elem.content)
        
        -- Check if this is a TOC link (href starts with #)
        if string.match(href, "^#") then
            local anchor_id = string.gsub(href, "^#", "")
            local number = extract_number(text_content)
            
            if number then
                -- Extract the heading text without the number
                local heading_text = string.gsub(text_content, "^%d+[%.%d]*%s*", "")
                toc_map[anchor_id] = {
                    number = number,
                    text = heading_text
                }
            end
        end
    end
    
    -- Mark TOC blocks for removal (typically div with id "toc" or similar)
    if elem.tag == "Div" and elem.identifier then
        if string.match(string.lower(elem.identifier), "toc") or 
           string.match(string.lower(elem.identifier), "contents") then
            return {}  -- Remove TOC block
        end
    end
    
    return elem
end

-- Second pass: apply numbers to headings
function apply_numbers_to_headings(elem)
    if elem.tag == "Header" then
        local heading_id = elem.identifier
        local heading_text = pandoc.utils.stringify(elem.content)
        
        -- Check if we have numbering info for this heading
        if toc_map[heading_id] then
            local number = toc_map[heading_id].number
            local clean_text = clean_heading_text(heading_text)
            
            -- Create new content with number prepended
            local numbered_text = number .. " " .. clean_text
            elem.content = {pandoc.Str(numbered_text)}
            
        -- Fallback: if no TOC info found, check for existing span with id
        else
            -- Look for spans or divs within the header that might have the anchor
            local found_anchor = false
            pandoc.walk_block(elem, {
                Span = function(span)
                    if span.identifier and toc_map[span.identifier] then
                        local number = toc_map[span.identifier].number
                        local clean_text = clean_heading_text(heading_text)
                        local numbered_text = number .. " " .. clean_text
                        elem.content = {pandoc.Str(numbered_text)}
                        found_anchor = true
                    end
                    return span
                end,
                Div = function(div)
                    if div.identifier and toc_map[div.identifier] then
                        local number = toc_map[div.identifier].number
                        local clean_text = clean_heading_text(heading_text)
                        local numbered_text = number .. " " .. clean_text
                        elem.content = {pandoc.Str(numbered_text)}
                        found_anchor = true
                    end
                    return div
                end
            })
        end
    end
    
    return elem
end

-- Remove TOC sections (lists that contain mostly links starting with #)
function remove_toc_blocks(elem)
    if elem.tag == "BulletList" or elem.tag == "OrderedList" then
        local toc_link_count = 0
        local total_items = #elem.content
        
        -- Count how many items contain TOC-like links
        for _, item in ipairs(elem.content) do
            pandoc.walk_block(pandoc.Div(item), {
                Link = function(link)
                    if string.match(link.target, "^#") then
                        toc_link_count = toc_link_count + 1
                    end
                    return link
                end
            })
        end
        
        -- If more than 70% of items are TOC links, consider this a TOC block
        if total_items > 2 and (toc_link_count / total_items) > 0.7 then
            return {}  -- Remove the entire list
        end
    end
    
    -- Remove divs that look like TOC containers
    if elem.tag == "Div" then
        if elem.identifier and (
            string.match(string.lower(elem.identifier), "toc") or
            string.match(string.lower(elem.identifier), "contents") or
            string.match(string.lower(elem.identifier), "table.*contents")
        ) then
            return {}
        end
        
        -- Check if div contains mostly TOC-like content
        local link_count = 0
        local toc_link_count = 0
        
        pandoc.walk_block(elem, {
            Link = function(link)
                link_count = link_count + 1
                if string.match(link.target, "^#") then
                    toc_link_count = toc_link_count + 1
                end
                return link
            end
        })
        
        -- If this div contains mostly internal links, it's probably TOC
        if link_count > 3 and (toc_link_count / link_count) > 0.8 then
            return {}
        end
    end
    
    return elem
end

-- Main filter function that orchestrates the process
return {
    {
        -- First pass: collect TOC information
        Link = collect_toc_info,
        Div = collect_toc_info
    },
    {
        -- Second pass: apply numbers to headings and remove TOC
        Header = apply_numbers_to_headings,
        BulletList = remove_toc_blocks,
        OrderedList = remove_toc_blocks,
        Div = remove_toc_blocks
    }
}