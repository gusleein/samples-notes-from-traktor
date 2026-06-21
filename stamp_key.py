#!/usr/bin/env python3
"""
stamp_key.py — добавляет тональность (и опционально BPM) из Traktor в имя файла.

Usage:
    python stamp_key.py /path/to/samples
    python stamp_key.py /path/to/samples --bpm
    python stamp_key.py /path/to/samples --bpm --dry-run
    python stamp_key.py /path/to/samples --collection ~/my/collection.nml

    # паттерн в начале имени:
    python stamp_key.py /path/to/samples --pattern "(key @key | bpm @bpm)"
    python stamp_key.py /path/to/samples --pattern "@key @bpm -"
    python stamp_key.py /path/to/samples --pattern "(key @key)"

    # сохранить исходный порядок файлов через порядковый номер:
    python stamp_key.py /path/to/samples --number --prepend
    # → 0001 (key F#) sample_name.wav

    # игнорировать backup/ папки явно (включено по умолчанию, флаг отключает):
    python stamp_key.py /path/to/samples --no-skip-backup

    # выполнить без создания backup/ — переименование без копии оригинала:
    python stamp_key.py /path/to/samples --no-backup

Плейсхолдеры в --pattern:
    @key   — тональность (напр. F#)
    @bpm   — BPM округлённый до целого (напр. 138)
    @name  — оригинальное имя файла без расширения
    @num   — порядковый номер (требует --number), ширина задаётся --num-width

Позиция тега задаётся через --prepend (в начало) или --append (в конец, по умолчанию).
Разделитель между тегом и именем — --sep (по умолчанию "_").
"""

import argparse
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

AUDIO_EXTENSIONS = {'.wav', '.aiff', '.aif', '.flac', '.mp3'}

# Traktor MUSICAL_KEY: 0–11 major, 12–23 minor, порядок — круг квинт
_MAJOR_ROOTS = ['C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#', 'F']
_MINOR_ROOTS = ['A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#', 'F',  'C',  'G',  'D']

# дефолтный паттерн (старое поведение — суффикс _Key_BPMbpm)
DEFAULT_PATTERN_APPEND  = '@key'
DEFAULT_PATTERN_PREPEND = '(@key)'


def traktor_key_to_note(value: int) -> Optional[str]:
    if 0 <= value <= 11:
        return _MAJOR_ROOTS[value]
    if 12 <= value <= 23:
        return _MINOR_ROOTS[value - 12]
    return None


def traktor_dir_to_path(dir_attr: str, file_attr: str) -> str:
    """'/:Users/:name/:Music/:' + 'file.wav' → '/Users/name/Music/file.wav'"""
    parts = [p for p in dir_attr.split('/:') if p]
    return '/' + '/'.join(parts) + '/' + file_attr


def load_collection(collection_path: str) -> dict:
    """Возвращает { '/abs/path/file.wav': {'key': 'A', 'bpm': 138.0} }"""
    data = {}
    try:
        tree = ET.parse(collection_path)
    except Exception as e:
        print(f"ERROR: не удалось прочитать collection: {e}", file=sys.stderr)
        return data

    for entry in tree.findall('.//ENTRY'):
        location = entry.find('LOCATION')
        if location is None:
            continue
        dir_attr = location.get('DIR', '')
        file_attr = location.get('FILE', '')
        if not file_attr:
            continue
        try:
            full_path = traktor_dir_to_path(dir_attr, file_attr)
        except Exception:
            continue

        info = {}

        mk = entry.find('MUSICAL_KEY')
        if mk is not None and mk.get('VALUE') is not None:
            note = traktor_key_to_note(int(mk.get('VALUE')))
            if note:
                info['key'] = note

        tempo = entry.find('TEMPO')
        if tempo is not None and tempo.get('BPM'):
            try:
                info['bpm'] = float(tempo.get('BPM'))
            except ValueError:
                pass

        if info:
            data[full_path] = info

    return data


def find_audio_files(directory: str, skip_backup: bool):
    for path in Path(directory).rglob('*'):
        if skip_backup and 'backup' in path.parts:
            continue
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
            yield path


def render_pattern(pattern: str, info: dict, stem: str, num: Optional[int] = None,
                    num_width: int = 4) -> Optional[str]:
    """
    Подставляет плейсхолдеры в паттерн.
    Возвращает None если обязательный @key отсутствует в info.
    """
    if '@key' in pattern and 'key' not in info:
        return None

    result = pattern
    result = result.replace('@key',  info.get('key', ''))
    result = result.replace('@bpm',  f"{info['bpm']:.0f}" if 'bpm' in info else '')
    result = result.replace('@name', stem)
    result = result.replace('@num',  f"{num:0{num_width}d}" if num is not None else '')

    # убираем незаполненные плейсхолдеры, которые могли остаться
    result = re.sub(r'@\w+', '', result)
    return result.strip()


def already_tagged(stem: str, pattern: str, prepend: bool) -> bool:
    """
    Эвристика: если паттерн содержит скобки — ищем их в имени.
    Иначе — старая проверка суффикса _Key.
    """
    if '(' in pattern or ')' in pattern:
        # ищем любой блок в скобках в начале или конце имени
        if prepend:
            return bool(re.match(r'^\(.*?\)', stem))
        else:
            return bool(re.search(r'\(.*?\)$', stem))
    # дефолтная проверка для старого формата суффикса
    return bool(re.search(r'_[A-G]#?(_\d+bpm)?$', stem))


def build_new_name(stem: str, ext: str, tag: str, sep: str, prepend: bool) -> str:
    if prepend:
        return f"{tag}{sep}{stem}{ext}"
    else:
        return f"{stem}{sep}{tag}{ext}"


def ensure_backup_dir(directory: Path, dry_run: bool) -> Path:
    backup_dir = directory / 'backup'
    if not dry_run:
        backup_dir.mkdir(exist_ok=True)
    return backup_dir


def backup_file(path: Path, dry_run: bool) -> Optional[Path]:
    backup_dir = ensure_backup_dir(path.parent, dry_run)
    backup_path = backup_dir / path.name
    if not dry_run and backup_path.exists():
        return backup_path
    if not dry_run:
        try:
            shutil.copy2(path, backup_path)
        except Exception as e:
            print(f"  ERROR backup: {e}", file=sys.stderr)
            return None
    return backup_path


def run(directory: str, collection_data: dict, pattern: str, sep: str,
        prepend: bool, dry_run: bool, skip_backup: bool,
        number: bool, num_width: int, no_backup: bool):

    files = sorted(find_audio_files(directory, skip_backup), key=lambda p: str(p))
    if not files:
        print("Аудио файлы не найдены.")
        return

    tagged = skipped_no_key = skipped_already = errors = 0
    counter = 1

    for path in files:
        info = collection_data.get(str(path.resolve()))
        if not info or 'key' not in info:
            skipped_no_key += 1
            continue
        if already_tagged(path.stem, pattern, prepend):
            skipped_already += 1
            continue

        num = counter if number else None
        tag = render_pattern(pattern, info, path.stem, num=num, num_width=num_width)
        if tag is None:
            skipped_no_key += 1
            continue

        new_name = build_new_name(path.stem, path.suffix, tag, sep, prepend)
        new_path  = path.parent / new_name

        prefix = '[DRY-RUN] ' if dry_run else ''
        backup_note = '' if no_backup else f"  (backup: backup/{path.name})"
        print(f"{prefix}{path.name}  →  {new_name}{backup_note}")

        if not dry_run:
            if not no_backup:
                backed_up = backup_file(path, dry_run=False)
                if backed_up is None:
                    print(f"  SKIP: не удалось создать backup для {path.name}", file=sys.stderr)
                    errors += 1
                    continue
            try:
                path.rename(new_path)
                tagged += 1
            except Exception as e:
                print(f"  ERROR rename: {e}", file=sys.stderr)
                errors += 1
        else:
            tagged += 1

        counter += 1

    print(f"\nПереименовано: {tagged} | Нет в Traktor: {skipped_no_key} | Уже тегированы: {skipped_already} | Ошибки: {errors}")


def main():
    default_collection = os.path.expanduser(
        '~/Documents/Native Instruments/Traktor/collection.nml'
    )
    parser = argparse.ArgumentParser(
        description='Добавляет тональность из Traktor в имя файла.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Плейсхолдеры для --pattern:
  @key   тональность (напр. F#)
  @bpm   BPM целое (напр. 138)
  @name  оригинальное имя файла без расширения
  @num   порядковый номер (требует --number)

Примеры:
  --pattern "(key @key | bpm @bpm)"  --prepend
      → (key F# | bpm 138)_loop_drums.wav

  --pattern "@key @bpm"  --prepend  --sep " - "
      → F# 138 - loop_drums.wav

  --pattern "(key @key)"  --append
      → loop_drums_(key F#).wav

  --number  --prepend
      → 0001_(key F#)_loop_drums.wav

  --pattern "@num (key @key)"  --prepend  --sep " "
      → 0001 (key F#) loop_drums.wav
        """
    )
    parser.add_argument('directory',
                        help='Директория для обработки (рекурсивно)')
    parser.add_argument('--collection', default=default_collection,
                        metavar='PATH', help='Путь к collection.nml')
    parser.add_argument('--pattern', default=None,
                        metavar='PATTERN',
                        help='Шаблон тега с плейсхолдерами @key @bpm @name. '
                             'По умолчанию: "@key" (append) или "(@key)" (prepend)')
    parser.add_argument('--prepend', action='store_true',
                        help='Добавить тег В НАЧАЛО имени файла (по умолчанию — в конец)')
    parser.add_argument('--sep', default='_',
                        help='Разделитель между тегом и именем (по умолчанию "_")')
    parser.add_argument('--bpm', action='store_true',
                        help='Добавить BPM — эквивалент --pattern "@key @bpm" '
                             '(игнорируется если задан --pattern)')
    parser.add_argument('--no-skip-backup', action='store_true',
                        help='Не пропускать файлы внутри backup/ директорий при сканировании')
    parser.add_argument('--no-backup', action='store_true',
                        help='Не создавать backup/ — переименовывать файлы напрямую, без копии оригинала')
    parser.add_argument('--number', action='store_true',
                        help='Добавить порядковый номер @num в паттерн (сохраняет исходный '
                             'алфавитный порядок файлов). Если --pattern не задан явно, '
                             'используется "@num (key @key)" с --prepend.')
    parser.add_argument('--num-width', type=int, default=4, metavar='N',
                        help='Ширина порядкового номера с ведущими нулями (по умолчанию 4 → 0001)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Показать изменения без переименования')
    args = parser.parse_args()

    # определяем паттерн
    if args.pattern:
        pattern = args.pattern
    elif args.number:
        pattern = '@num (key @key)' if args.prepend else '(key @key) @num'
    elif args.bpm:
        pattern = '@key @bpm' if not args.prepend else '(@key | @bpm bpm)'
    else:
        pattern = DEFAULT_PATTERN_PREPEND if args.prepend else DEFAULT_PATTERN_APPEND

    skip_backup = not args.no_skip_backup

    if not os.path.isdir(args.directory):
        sys.exit(f"ERROR: директория не найдена: {args.directory}")
    if not os.path.exists(args.collection):
        sys.exit(
            f"ERROR: collection.nml не найден: {args.collection}\n"
            f"Укажи путь через --collection"
        )

    pos_label = 'начало' if args.prepend else 'конец'
    print(f"Коллекция : {args.collection}")
    print(f"Паттерн   : {pattern!r}  →  позиция: {pos_label}  sep: {args.sep!r}")
    data = load_collection(args.collection)
    print(f"Треков    : {len(data)}\n")

    run(args.directory, data, pattern, args.sep, args.prepend, args.dry_run,
        skip_backup, args.number, args.num_width, args.no_backup)


if __name__ == '__main__':
    main()
