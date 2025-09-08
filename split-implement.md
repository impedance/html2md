
# `restore_numbers.lua` — Pandoc Lua-фильтр

**Назначение:** поднимает номера из оглавления (ссылки вида `#h...`) и вшивает их в текст заголовков. Опционально удаляет сам блок оглавления. Есть фолбэк-автонумерация, если для заголовка нет записи в ToC.

```lua
-- restore_numbers.lua
-- Восстанавливает нумерацию заголовков из ToC Google Docs (#h-anchors)
-- и добавляет префикс "<номер> " в текст заголовков. Опционально удаляет ToC.

local REMOVE_TOC = true           -- true: убрать блок оглавления из начала документа
local ENABLE_FALLBACK_COUNTERS = true  -- true: автонумерация, если нет записи в ToC

-- Хранилище: anchor_id ("h.*") => "N[.N]* Title"
local TOC = {}
local seen_first_header = false

-- Счетчики для фолбэк-автонумерации
local counters = {}

local function reset_lower(level)
  for i = level + 1, #counters do
    counters[i] = nil
  end
end

local function next_number(level)
  counters[level] = (counters[level] or 0) + 1
  reset_lower(level)
  -- собрать строку "1.2.3"
  local parts = {}
  for i = 1, level do
    table.insert(parts, tostring(counters[i] or 0))
  end
  return table.concat(parts, ".")
end

-- Утилиты
local stringify = (require 'pandoc.utils').stringify

local function get_anchor_id(target)
  -- ожидаем target вроде "#h1234..." -> вернуть "h1234..."
  if not target then return nil end
  local id = target:match("^#(h[%w%-%._]+)")
  return id
end

local function trim(s)
  return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function looks_like_toc_number_title(s)
  -- "8.3 Встроенный Ansible" -> ("8.3","Встроенный Ansible")
  local num, rest = s:match("^%s*(%d[%d%.]*)%s+(.+)$")
  if num and rest then
    -- защита от "1)" / "1—" и т.п. — оставим только классический формат
    return num, trim(rest)
  end
  return nil, nil
end

-- 1) Сбор карты ToC по ссылкам
function Link(el)
  local id = get_anchor_id(el.target)
  if id then
    local label = stringify(el.content)
    local num, title = looks_like_toc_number_title(label)
    if num and title then
      TOC[id] = num .. " " .. title
    end
  end
  return nil
end

-- 2) Удаление ToC в начале документа (по желанию)
--     Любой блок до первого Header, который содержит хотя бы одну ссылку на "#h..."
local function block_contains_h_anchor(b)
  -- проверяем инлайны
  local function has_h_anchor_inlines(inlines)
    if not inlines then return false end
    for _, inl in ipairs(inlines) do
      if inl.t == "Link" and get_anchor_id(inl.target) then
        return true
      end
      -- заглянем внутрь Span/Emph/Strong и т.п.
      if inl.content and type(inl.content) == "table" and has_h_anchor_inlines(inl.content) then
        return true
      end
    end
    return false
  end

  if b.t == "Para" or b.t == "Plain" then
    return has_h_anchor_inlines(b.content)
  elseif b.t == "BulletList" or b.t == "OrderedList" then
    for _, items in ipairs(b.content) do
      for _, sub in ipairs(items) do
        if block_contains_h_anchor(sub) then return true end
      end
    end
  elseif b.t == "Div" then
    for _, sub in ipairs(b.content) do
      if block_contains_h_anchor(sub) then return true end
    end
  end
  return false
end

function Blocks(blocks)
  if not REMOVE_TOC or seen_first_header then
    return nil
  end

  local out = {}
  for _, b in ipairs(blocks) do
    if b.t == "Header" then
      seen_first_header = true
      table.insert(out, b)
    else
      if block_contains_h_anchor(b) then
        -- пропускаем этот блок как часть ToC
      else
        table.insert(out, b)
      end
    end
  end
  return out
end

-- 3) Обновление заголовков: префикс из TOC[id] или фолбэк-номер
function Header(h)
  -- помечаем, что «после ToC»
  seen_first_header = true

  local id = h.identifier or (h.attr and h.attr.identifier)
  local prefix = nil

  if id and TOC[id] then
    prefix = TOC[id]
  elseif ENABLE_FALLBACK_COUNTERS then
    prefix = next_number(h.level)
  end

  if prefix then
    -- не дублировать, если уже начинается с того же номера
    local current = trim(stringify(h.content))
    local num_in_h = current:match("^%d[%d%.]*")
    if not num_in_h or not current:find("^" .. prefix:gsub("(%p)","%%%1")) then
      -- Вставить "<prefix> " в начало
      local new_inlines = { pandoc.Str(prefix), pandoc.Space() }
      for i = 1, #h.content do
        table.insert(new_inlines, h.content[i])
      end
      h.content = new_inlines
    end
  end

  return h
end
```

**Использование:**

```bash
pandoc input.html \
  --from=html --to=html \
  --standalone \
  --lua-filter=restore_numbers.lua \
  -o _numbered.html
```

Опции вверху файла:

* `REMOVE_TOC = true` — удалить блок оглавления из начала.
* `ENABLE_FALLBACK_COUNTERS = true` — автонумерация там, где ToC не помог.

---

# `splitter_html.py` — резка HTML на главы

**Назначение:** режет `_numbered.html` на части по `h{level}` (по умолчанию `h1`) и сохраняет валидные HTML-фрагменты `NN.<slug>.html`.

```python
# splitter_html.py
# Разрезает HTML по заголовкам h{level} на отдельные файлы-главы.
# Пример:
#   python splitter_html.py --input _numbered.html --out _chapters --level 1

import argparse
import os
import re
from pathlib import Path
from bs4 import BeautifulSoup

def slugify(text: str, maxlen: int = 80) -> str:
    text = text.lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9\-\._]+", "", text)
    text = re.sub(r"-{2,}", "-", text).strip("-._")
    return text[:maxlen] or "chapter"

def extract_title(nodes):
    for n in nodes:
        if getattr(n, "name", None) and n.name.lower().startswith("h"):
            return n.get_text(strip=True)
    # fallback: первый непустой текст
    for n in nodes:
        t = (n.get_text(strip=True) if getattr(n, "get_text", None) else "").strip()
        if t:
            return t[:60]
    return "chapter"

def wrap_minimal_html(inner_html: str, meta_charset="utf-8") -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="{meta_charset}"></head>
<body>
{inner_html}
</body>
</html>
"""

def split_html_by_hlevel(html_text: str, level: int = 1, include_prelude=False):
    soup = BeautifulSoup(html_text, "lxml")
    body = soup.body or soup

    chapters = []
    current = []
    started = False

    for node in list(body.children):
        name = getattr(node, "name", None)
        if name and name.lower() == f"h{level}":
            if started and current:
                chapters.append(current)
                current = []
            started = True

        if not started and not include_prelude:
            # пропускаем прелюдию до первого h{level}
            continue

        # сохраняем узел в текущую главу
        if getattr(node, "name", None) or str(node).strip():
            current.append(node)

    if current:
        chapters.append(current)

    return chapters

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Путь к входному HTML (_numbered.html)")
    ap.add_argument("--out", required=True, help="Папка для глав (HTML)")
    ap.add_argument("--level", type=int, default=1, help="Уровень заголовка для разрезания (h1=1, h2=2, ...)")
    ap.add_argument("--include-prelude", action="store_true", help="Сохранять прелюдию как 00.prelude.html")
    args = ap.parse_args()

    html = Path(args.input).read_text(encoding="utf-8")
    chapters = split_html_by_hlevel(html, level=args.level, include_prelude=args.include_predule if hasattr(args,'include_predule') else args.include_prelude)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.include_prelude:
        # Если прелюдия включена, и первая "глава" не начинается с h{level},
        # она попадёт сюда как 00.prelude.html.
        pass

    for i, nodes in enumerate(chapters, start=1 if not args.include_prelude else 0):
        # Собираем HTML главы
        inner = "".join(str(n) for n in nodes)
        title = extract_title(nodes)
        stem = f"{i:02d}.{slugify(title)}" if i > 0 else f"00.{slugify(title)}"
        out_html = wrap_minimal_html(inner)
        (out_dir / f"{stem}.html").write_text(out_html, encoding="utf-8")

    print(f"✅ Сохранено глав: {len(chapters)} → {args.out}")

if __name__ == "__main__":
    main()
```

**Использование:**

```bash
python splitter_html.py \
  --input _numbered.html \
  --out _chapters \
  --level 1
```

---

## Дальше (напоминание шагов Pandoc → MD с медиа)

```bash
mkdir -p out

for f in _chapters/*.html; do
  bn=$(basename "$f" .html)      # NN.slug
  ch=${bn%%.*}                    # NN
  mkdir -p "out/media/ch${ch}"
  pandoc "$f" \
    --from=html --to=gfm \
    --extract-media="out/media/ch${ch}" \
    --wrap=none \
    -o "out/${bn}.md"
done
```

