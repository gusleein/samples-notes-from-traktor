# traktor/stamp_key.py

Переименовывает WAV и AIFF файлы, добавляя тональность (и опционально BPM) из Traktor библиотеки в имя файла.

Никаких pip-зависимостей — только стандартная библиотека Python 3.9+.

---

## Что делает

1. Читает `collection.nml` из Traktor — данные анализа треков (тональность, BPM grid)
2. Рекурсивно обходит указанную директорию, ищет `.wav`, `.aiff`, `.aif`
3. Для каждого файла ищет совпадение по абсолютному пути в коллекции
4. Если тональность найдена — переименовывает файл, добавляя суффикс
5. Если тональность не найдена — файл пропускается без изменений

---

## Формат имён

```
kick_hard_01.wav          →  kick_hard_01_A.wav
bass_loop_dark.wav        →  bass_loop_dark_F#.wav
synth_pad_rise.aiff       →  synth_pad_rise_C#.aiff

# с флагом --bpm:
bass_loop_dark.wav        →  bass_loop_dark_F#_138bpm.wav
```

Нотация — только диезы: `C`, `C#`, `D`, `D#`, `E`, `F`, `F#`, `G`, `G#`, `A`, `A#`, `B`.

---

## Использование

```bash
# Показать что изменится — без переименования
python stamp_key.py /path/to/samples --dry-run

# Переименовать: добавить только тональность
python stamp_key.py /path/to/samples

# Добавить тональность + BPM из Traktor grid
python stamp_key.py /path/to/samples --bpm

# Указать нестандартный путь к collection.nml
python stamp_key.py /path/to/samples --collection ~/Desktop/collection.nml

# Комбинация
python stamp_key.py /path/to/samples --bpm --dry-run --collection ~/my/collection.nml
```

---

## Флаги

| Флаг | По умолчанию | Описание |
|---|---|---|
| `directory` | — | Директория для обработки (рекурсивно) |
| `--bpm` | выкл | Добавить BPM из Traktor beat grid |
| `--collection PATH` | `~/Documents/Native Instruments/Traktor/collection.nml` | Путь к файлу коллекции |
| `--dry-run` | выкл | Показать изменения без переименования файлов |

---

## Источник данных

Скрипт читает только `collection.nml` — XML-файл Traktor с результатами анализа. Никакого аудиоанализа самим скриптом не происходит.

**Тональность** берётся из поля `MUSICAL_KEY` — результат key detection Traktor'а. Traktor анализирует тональность значительно точнее любого open-source аудиоанализа, особенно для сложного материала (psytrance, dark forest).

**BPM** берётся из поля `TEMPO` — значение beat grid, выставленного вручную или автоопределённого Traktor'ом.

Файлы, которых нет в коллекции Traktor, пропускаются.

---

## Защита от двойного тегирования

Файлы, у которых уже есть суффикс тональности (`_A`, `_F#`, `_C#_138bpm` и т.п.), пропускаются автоматически.

---

## Первый запуск — чеклист

1. Убедись, что Traktor проанализировал нужные файлы (иконка тональности в браузере)
2. Прогони с `--dry-run`, сверь несколько треков с известными ключами
3. Если тональности сдвинуты (например, показывает G вместо A) — сообщи, маппинг правится в одну строку в скрипте
4. Если всё ок — запускай без `--dry-run`

---

## Вывод скрипта

```
Коллекция: /Users/user/Documents/Native Instruments/Traktor/collection.nml
Треков в коллекции: 4821

bass_rolling_dark_01.wav  →  bass_rolling_dark_01_F#.wav
kick_hard_psytek_02.wav   →  kick_hard_psytek_02_A.wav
synth_pad_mystik.aiff     →  synth_pad_mystik_C#.aiff

Переименовано: 3 | Нет в Traktor: 12 | Уже тегированы: 0 | Ошибки: 0
```

---

## Структура проекта

```
live-tools-lab/traktor/
├── stamp_key.py   ← скрипт
└── README.md      ← этот файл
```
