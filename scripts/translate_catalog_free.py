import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'catalog/en/bulk'
OUT.mkdir(parents=True, exist_ok=True)
CACHE = OUT / 'translations.json'
cache = json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {}
HAN = re.compile(r'[\u3400-\u9fff]')
MANUAL = {'人工智能': '../artificial-intelligence.md', '天文': '../astronomy.md', '生物': '../biology.md'}
errors = []
categories = []
needed = set()

def cells(line):
    return [x.strip() for x in re.split(r'(?<!\\)\|', line.strip().strip('|'))]

def needs(text):
    return bool(HAN.search(text)) and not re.search(r'https?://', text)

def esc(text):
    return text.replace('|', '&#124;').replace('\n', '<br>')

def add(text):
    if needs(text) and text not in cache:
        needed.add(text)

for source in sorted((ROOT / 'md').glob('*.md')):
    name = source.stem
    lines = source.read_text(encoding='utf-8').splitlines()
    headers, rows, prose = [], [], []
    active = False
    bad = False
    for line in lines:
        if line.lstrip().startswith('|'):
            values = cells(line)
            if not headers:
                headers = values
                active = True
            elif all(re.fullmatch(r':?-+:?', x.replace(' ', '')) for x in values):
                continue
            elif len(values) == len(headers):
                rows.append(values)
            else:
                errors.append({'source': source.name, 'error': 'Unequal table column counts', 'line': line})
                bad = True
        elif line.strip() and not line.startswith('#'):
            prose.append(line.strip())
    if not active or not rows:
        errors.append({'source': source.name, 'error': 'No supported book table'})
        bad = True
    item = {'name': name, 'source': source.name, 'headers': headers, 'rows': rows, 'prose': prose, 'bad': bad}
    categories.append(item)
    add(name)
    if name not in MANUAL:
        for text in headers + prose + [v for row in rows for v in row]:
            add(text)

if needed:
    import torch
    from transformers import MarianMTModel, MarianTokenizer
    torch.set_num_threads(2)
    model_id = 'Helsinki-NLP/opus-mt-zh-en'
    tokenizer = MarianTokenizer.from_pretrained(model_id)
    model = MarianMTModel.from_pretrained(model_id).eval()
    deadline = time.monotonic() + 3600
    ordered = sorted(needed, key=lambda x: (x not in {c['name'] for c in categories}, len(x), x))
    for text in ordered:
        if time.monotonic() >= deadline:
            break
        try:
            chunks = []
            current = ''
            for part in re.split(r'(?<=[。！？；.!?;])', text):
                trial = current + part
                if len(tokenizer.encode(trial)) > 400:
                    if current:
                        chunks.append(current)
                    current = part
                else:
                    current = trial
            if current:
                chunks.append(current)
            translated = []
            for chunk in chunks:
                inputs = tokenizer(chunk, return_tensors='pt', truncation=False)
                if inputs['input_ids'].shape[1] > 400:
                    raise ValueError('Text exceeds safe input length; requires review')
                with torch.inference_mode():
                    result = model.generate(**inputs, max_new_tokens=512, num_beams=2)
                if result.shape[1] >= 512:
                    raise ValueError('Potentially truncated translation; requires review')
                translated.append(tokenizer.decode(result[0], skip_special_tokens=True).strip())
            english = ' '.join(translated)
            if not english or HAN.search(english):
                raise ValueError('Empty output or remaining Chinese text')
            cache[text] = english
            temporary = CACHE.with_suffix('.tmp')
            temporary.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(CACHE)
        except Exception as exc:
            errors.append({'text': text, 'error': str(exc)})

def english(text):
    return cache.get(text, text).replace('[下载]', '[Download]')

def bilingual(text):
    translated = english(text)
    return esc(translated) + ('<br>' + esc(text) if needs(text) and translated != text else '')

index = []
complete = 0
entries = 0
for item in categories:
    name = item['name']
    label = english(name)
    if name in MANUAL:
        index.append((label, MANUAL[name], len(item['rows']), 'Previously translated'))
        complete += 1
        entries += len(item['rows'])
        continue
    texts = [name] + item['headers'] + item['prose'] + [v for row in item['rows'] for v in row]
    pending = [x for x in texts if needs(x) and x not in cache]
    unsafe = [x for x in texts if HAN.search(x) and re.search(r'https?://', x) and not re.fullmatch(r'\[下载\]\(https?://[^\s]+\)', x)]
    filename = hashlib.sha256(name.encode()).hexdigest()[:16] + '.md'
    if item['bad'] or pending or unsafe:
        index.append((label, '', len(item['rows']), 'Pending translation or review'))
        for text in unsafe:
            errors.append({'source': item['source'], 'error': 'Mixed Chinese and URL requires review', 'text': text})
        continue
    content = ['# ' + label, '', 'Original category: ' + name, '', '[English index](README.md) | [Original category](../../../md/' + quote(item['source']) + ')', '', 'Machine-translated catalog metadata, not verified official English-edition titles. Original author names and titles are retained. Ebook contents are not translated. Source categories are preserved, not independently reclassified. The source copyright notice below is translated as a statement by the source, not verification of download permission.', '']
    for text in item['prose']:
        content.extend([bilingual(text), ''])
    content += ['| ' + ' | '.join(esc(english(x)) for x in item['headers']) + ' |', '| ' + ' | '.join('---' for _ in item['headers']) + ' |']
    for row in sorted(item['rows'], key=lambda r: english(r[0]).casefold()):
        content.append('| ' + ' | '.join(bilingual(x) for x in row) + ' |')
    (OUT / filename).write_text('\n'.join(content) + '\n', encoding='utf-8')
    index.append((label, filename, len(item['rows']), 'Machine translated; not human reviewed'))
    complete += 1
    entries += len(item['rows'])

report = {'source_categories': len(categories), 'translated_categories': complete, 'translated_category_entries': entries, 'remaining_unique_texts': sum(x not in cache for x in needed), 'issues': errors}
(OUT / 'status.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
lines = ['# English Catalog — All Categories A–Z', '', f'Translated categories: {complete}/{len(categories)}. Category entries in translated pages: {entries}. Entries may repeat across categories.', '', 'Pending categories are not marked complete. English labels are machine translations unless previously translated. Sorting includes initial articles. See [status report](status.json) for parsing and translation issues. Rerun the workflow to resume. This index does not change the original website.', '', 'Translation model: [Helsinki-NLP/opus-mt-zh-en](https://huggingface.co/Helsinki-NLP/opus-mt-zh-en), Helsinki-NLP / OPUS-MT, CC-BY-4.0. Output is an unverified machine translation of the original catalog.', '', '| Category | Source category | Entries | Status |', '| --- | --- | --- | --- |']
for label, link, count, state in sorted(index, key=lambda x: x[0].casefold()):
    display = '[' + esc(label) + '](' + link + ')' if link else esc(label)
    source_name = next(c['name'] for c in categories if english(c['name']) == label) if False else ''
    lines.append('| ' + display + ' | ' + str(count) + ' entries | ' + str(count) + ' | ' + state + ' |')
(OUT / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'issues'}, ensure_ascii=False))
