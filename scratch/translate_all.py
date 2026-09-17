
import sys, json, os, urllib.request, urllib.parse, re, time

CACHE_FILE = 'scratch/translation_cache.json'
cache = {}
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
    except Exception:
        cache = {}

print(f'Starting with cache of {len(cache)} entries')

def save_cache():
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def protect_placeholders(text):
    # Protect {0}, {1}, {name}, {count}, {rules}, etc.
    # Replace {xxx} with ___PH_{i}___
    placeholders = []
    def repl(m):
        idx = len(placeholders)
        placeholders.append(m.group(0))
        return f'XYZPH{idx}XYZ'
    
    protected = re.sub(r'\{[a-zA-Z0-9_]+\}', repl, text)
    return protected, placeholders

def unprotect_placeholders(text, placeholders):
    out = text
    for idx, ph in enumerate(placeholders):
        # Match variations that translator might emit (spacing around XYZPH)
        pattern = re.compile(rf'XYZ\s*PH\s*{idx}\s*XYZ', re.IGNORECASE)
        out = pattern.sub(ph, out)
    return out

def translate_phrase(text):
    if text in cache:
        return cache[text]
    
    # Check trivial / empty
    stripped = text.strip()
    if not stripped or stripped.isdigit():
        cache[text] = text
        return text
    
    protected, placeholders = protect_placeholders(text)
    
    url = 'https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=en&tl=fr&q=' + urllib.parse.quote(protected)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                res = json.loads(r.read().decode('utf-8'))
                raw_tr = res[0] if isinstance(res, list) and res else str(res)
                # Unprotect
                final_tr = unprotect_placeholders(raw_tr, placeholders)
                # Cleanup non-breaking space
                final_tr = final_tr.replace('\u00a0', ' ')
                cache[text] = final_tr
                return final_tr
        except Exception as e:
            time.sleep(1 + attempt)
            
    # Fallback to text if failed
    cache[text] = text
    return text

with open('scratch/all_distinct_en.json', 'r', encoding='utf-8') as f:
    all_items = json.load(f)

print(f'Total distinct items to translate: {len(all_items)}')
count = 0
for idx, item in enumerate(all_items):
    if item not in cache:
        translate_phrase(item)
        count += 1
        if count % 50 == 0:
            save_cache()
            print(f'Translated {count} / {len(all_items)} (Total in cache: {len(cache)})')
        time.sleep(0.05)

save_cache()
print(f'Finished translating. Cache entries: {len(cache)}')
