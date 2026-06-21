# traktor/stamp_key.py

Переименовывает WAV, AIFF, MP3, FLAC файлы, добавляя тональность (и опционально BPM, порядковый номер) из Traktor библиотеки в имя файла.

Никаких pip-зависимостей — только стандартная библиотека Python 3.9+.

---

## Что делает

1. Читает `collection.nml` из Traktor — данные анализа треков (тональность, BPM grid)
2. Рекурсивно обходит указанную директорию, ищет `.wav`, `.aiff`, `.aif`, `.mp3`, `.flac`
3. Для каждого файла ищет совпадение по абсолютному пути в коллекции
4. Если тональность найдена — делает бэкап оригинала в `backup/` рядом с файлом и переименовывает его, добавляя тег
5. Если тональность не найдена — файл пропускается без изменений
6. Файлы внутри `backup/` директорий пропускаются автоматически (если не указан `--no-skip-backup`)

---

## Формат имён

По умолчанию тег добавляется в конец имени (старое поведение):

```
kick_hard_01.wav          →  kick_hard_01_A.wav
bass_loop_dark.wav        →  bass_loop_dark_F#.wav
synth_pad_rise.aiff       →  synth_pad_rise_C#.aiff
```

С `--prepend` тег уходит в начало и оборачивается в скобки для читаемости:

```
bass_loop_dark.wav        →  (F#)_bass_loop_dark.wav
```

Через `--pattern` формат полностью настраиваемый (см. ниже), например:

```
bass_loop_dark.wav        →  0001 (key F#) bass_loop_dark.wav
```

Нотация тональности — только диезы: `C`, `C#`, `D`, `D#`, `E`, `F`, `F#`, `G`, `G#`, `A`, `A#`, `B`.

---

## Использование

```bash
# Показать что изменится — без переименования
python stamp_key.py /path/to/samples --dry-run

# Переименовать: добавить только тональность (тег в конце)
python stamp_key.py /path/to/samples

# Добавить тональность + BPM из Traktor grid
python stamp_key.py /path/to/samples --bpm

# Тег в начало имени: (F#)_sample.wav
python stamp_key.py /path/to/samples --prepend

# Кастомный паттерн с плейсхолдерами @key, @bpm, @name, @num
python stamp_key.py /path/to/samples --prepend --pattern "(key @key | bpm @bpm)"

# Сохранить исходный порядок файлов через порядковый номер
python stamp_key.py /path/to/samples --prepend --number --sep " "
# → 0001 (key F#) sample.wav

# Указать нестандартный путь к collection.nml
python stamp_key.py /path/to/samples --collection ~/Desktop/collection.nml

# Не пропускать файлы внутри backup/ (на случай повторной обработки)
python stamp_key.py /path/to/samples --no-skip-backup

# Комбинация
python stamp_key.py /path/to/samples --bpm --dry-run --collection ~/my/collection.nml
```


#### Пример расположения коллекции

'/Users/amadau/Documents/Native Instruments/Traktor 4.1.1/collection.nml'

---

## Флаги

| Флаг | По умолчанию | Описание |
|---|---|---|
| `directory` | — | Директория для обработки (рекурсивно) |
| `--collection PATH` | `~/Documents/Native Instruments/Traktor/collection.nml` | Путь к файлу коллекции |
| `--pattern PATTERN` | `@key` (append) / `(@key)` (prepend) | Шаблон тега с плейсхолдерами `@key`, `@bpm`, `@name`, `@num` |
| `--prepend` | выкл (тег в конец) | Добавить тег в начало имени файла |
| `--sep STR` | `_` | Разделитель между тегом и оригинальным именем |
| `--bpm` | выкл | Добавить BPM из Traktor beat grid (игнорируется, если задан `--pattern`) |
| `--number` | выкл | Добавить порядковый номер `@num` в паттерн — сохраняет исходный алфавитный порядок файлов |
| `--num-width N` | `4` | Ширина номера с ведущими нулями (`0001`) |
| `--no-skip-backup` | выкл (backup/ пропускается) | Обрабатывать файлы и внутри `backup/` директорий |
| `--dry-run` | выкл | Показать изменения без переименования файлов |

---

## Плейсхолдеры для `--pattern`

| Плейсхолдер | Значение |
|---|---|
| `@key` | Тональность (напр. `F#`) — обязательна, если используется в паттерне |
| `@bpm` | BPM, округлённый до целого (напр. `138`) |
| `@name` | Оригинальное имя файла без расширения |
| `@num` | Порядковый номер — заполняется только при `--number`, ширина задаётся `--num-width` |

### Примеры паттернов

```bash
--pattern "(key @key | bpm @bpm)"  --prepend
# → (key F# | bpm 138)_loop_drums.wav

--pattern "@key @bpm"  --prepend  --sep " - "
# → F# 138 - loop_drums.wav

--pattern "(key @key)"  --append
# → loop_drums_(key F#).wav

--number  --prepend
# → 0001_(key F#)_loop_drums.wav

--pattern "@num (key @key)"  --prepend  --sep " "  --number
# → 0001 (key F#) loop_drums.wav
```

---

## Бэкапы

Перед каждым переименованием скрипт копирует оригинальный файл в `backup/` в той же директории, где он лежит (через `shutil.copy2`, с сохранением метаданных файла). Если файл с таким именем уже есть в `backup/` — он не перезаписывается, повторный запуск скрипта безопасен.

При рекурсивном обходе каждая поддиректория получает свой собственный `backup/`, а не один общий в корне.

---

## Источник данных

Скрипт читает только `collection.nml` — XML-файл Traktor с результатами анализа. Никакого аудиоанализа самим скриптом не происходит.

**Тональность** берётся из поля `MUSICAL_KEY` — результат key detection Traktor'а. Traktor анализирует тональность значительно точнее любого open-source аудиоанализа, особенно для сложного материала (psytrance, dark forest).

**BPM** берётся из поля `TEMPO` — значение beat grid, выставленного вручную или автоопределённого Traktor'ом.

Файлы, которых нет в коллекции Traktor, пропускаются.

---

## Защита от двойного тегирования

- Для дефолтного формата (без `--pattern`) — файлы с суффиксом тональности (`_A`, `_F#`, `_C#_138bpm` и т.п.) пропускаются автоматически.
- Для паттернов со скобками — скрипт ищет блок в скобках в начале или конце имени (в зависимости от `--prepend`/`--append`) и пропускает совпадения.

---

## Первый запуск — чеклист

1. Убедись, что Traktor проанализировал нужные файлы (иконка тональности в браузере)
2. Прогони с `--dry-run`, сверь несколько треков с известными ключами
3. Если тональности сдвинуты (например, показывает G вместо A) — сообщи, маппинг правится в одну строку в скрипте
4. Если всё ок — запускай без `--dry-run`

---

## Вывод скрипта

```
Коллекция : /Users/user/Documents/Native Instruments/Traktor/collection.nml
Паттерн   : '@num (key @key)'  →  позиция: начало  sep: ' '
Треков    : 4821

0001 (key F#) bass_rolling_dark_01.wav  (backup: backup/bass_rolling_dark_01.wav)
0002 (key A) kick_hard_psytek_02.wav  (backup: backup/kick_hard_psytek_02.wav)
0003 (key C#) synth_pad_mystik.aiff  (backup: backup/synth_pad_mystik.aiff)

Переименовано: 3 | Нет в Traktor: 12 | Уже тегированы: 0 | Ошибки: 0
```

---

## Структура проекта

```
live-tools-lab/traktor/
├── stamp_key.py   ← скрипт
└── README.md      ← этот файл
```
