import argparse
from pathlib import Path

CATEGORIES = {
    ".pdf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".txt": "Documents",
    ".xls": "Documents",
    ".xlsx": "Documents",
    ".ppt": "Documents",
    ".pptx": "Documents",
    ".jpg": "Images",
    ".jpeg": "Images",
    ".png": "Images",
    ".gif": "Images",
    ".webp": "Images",
    ".svg": "Images",
    ".mp4": "Videos",
    ".mov": "Videos",
    ".avi": "Videos",
    ".mkv": "Videos",
    ".webm": "Videos",
    ".zip": "Archives",
    ".rar": "Archives",
    ".7z": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
}


def category_for(filename):
    return CATEGORIES.get(Path(filename).suffix.lower(), "Other")


def list_files(source):
    for path in sorted(source.iterdir()):
        if path.is_file():
            print(f"{path.name} -> {category_for(path.name)}")


def organize(source, dry_run=False):
    processed = 0

    for path in sorted(source.iterdir()):
        if not path.is_file():
            continue

        category = category_for(path.name)
        destination_dir = source / category
        destination = destination_dir / path.name

        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Файл уже існує: {destination}")

        if dry_run:
            print(f"[DRY-RUN] {path.name} -> {category}")
        else:
            destination_dir.mkdir(parents=True, exist_ok=True)
            path.rename(destination)
            print(f"[OK] {path.name} -> {category}")

        processed += 1

    print(f"Оброблено файлів: {processed}")


def main():
    parser = argparse.ArgumentParser(description="Організатор файлів")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--source", default=".")

    organize_parser = subparsers.add_parser("organize")
    organize_parser.add_argument("--source", default=".")
    organize_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    source = Path(args.source)

    if not source.is_dir():
        parser.error("source повинен бути папкою")

    try:
        if args.command == "list":
            list_files(source)
        else:
            organize(source, args.dry_run)
    except OSError as error:
        parser.exit(1, f"Помилка: {error}\n")


if __name__ == "__main__":
    main()
