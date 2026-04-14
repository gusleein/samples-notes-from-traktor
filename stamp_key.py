#!/usr/bin/env python3
"""
stamp_key.py — добавляет тональность (и опционально BPM) из Traktor в имя файла.

Usage:
    python stamp_key.py /path/to/samples
    python stamp_key.py /path/to/samples --bpm
    python stamp_key.py /path/to/samples --bpm --dry-run
    python stamp_key.py /path/to/samples --collection ~/my/collection.nml
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

AUDIO_EXTENSIONS = {'.wav', '.aiff', '.aif'}

# Traktor MUSICAL_KEY: 0–11 major, 12–23 minor, порядок — круг квинт
_MAJOR_ROOTS = ['C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#', 'F']
_MINOR_ROOTS = ['A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#', 'F',  'C',  'G',  'D']


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


def find_audio_files(directory: str):
    for path in Path(directory).rglob('*'):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
            yield path


def already_tagged(stem: str) -> bool:
    """Файл уже содержит _A, _F#, _C#_138bpm и т.п."""
    return bool(re.search(r'_[A-G]#?(_\d+bpm)?$', stem))


def build_suffix(info: dict, include_bpm: bool) -> str:
    parts = [info['key']]
    if include_bpm and 'bpm' in info:
        parts.append(f"{info['bpm']:.0f}bpm")
    return '_'.join(parts)


def run(directory: str, collection_data: dict, include_bpm: bool, dry_run: bool):
    files = list(find_audio_files(directory))
    if not files:
        print("WAV/AIFF файлы не найдены.")
        return

    tagged = skipped_no_key = skipped_already = errors = 0

    for path in files:
        info = collection_data.get(str(path.resolve()))
        if not info or 'key' not in info:
            skipped_no_key += 1
            continue
        if already_tagged(path.stem):
            skipped_already += 1
            continue

        suffix = build_suffix(info, include_bpm)
        new_name = f"{path.stem}_{suffix}{path.suffix}"
        new_path = path.parent / new_name

        print(f"{'[DRY-RUN] ' if dry_run else ''}{path.name}  →  {new_name}")

        if not dry_run:
            try:
                path.rename(new_path)
                tagged += 1
            except Exception as e:
                print(f"  ERROR: {e}", file=sys.stderr)
                errors += 1
        else:
            tagged += 1

    print(f"\nПереименовано: {tagged} | Нет в Traktor: {skipped_no_key} | Уже тегированы: {skipped_already} | Ошибки: {errors}")


def main():
    default_collection = os.path.expanduser(
        '~/Documents/Native Instruments/Traktor/collection.nml'
    )
    parser = argparse.ArgumentParser(
        description='Добавляет тональность из Traktor в имя файла.'
    )
    parser.add_argument('directory', help='Директория для обработки (рекурсивно)')
    parser.add_argument('--bpm', action='store_true', help='Добавить BPM из Traktor grid')
    parser.add_argument('--collection', default=default_collection,
                        metavar='PATH', help='Путь к collection.nml')
    parser.add_argument('--dry-run', action='store_true',
                        help='Показать изменения без переименования')
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        sys.exit(f"ERROR: директория не найдена: {args.directory}")
    if not os.path.exists(args.collection):
        sys.exit(
            f"ERROR: collection.nml не найден: {args.collection}\n"
            f"Укажи путь через --collection"
        )

    print(f"Коллекция: {args.collection}")
    data = load_collection(args.collection)
    print(f"Треков в коллекции: {len(data)}\n")

    run(args.directory, data, args.bpm, args.dry_run)


if __name__ == '__main__':
    main()
