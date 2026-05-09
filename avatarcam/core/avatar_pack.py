from __future__ import annotations

from pathlib import Path
import json
import shutil
import zipfile

from avatarcam.core.settings import APP_DIR


AVATAR_DIR = APP_DIR / "avatars"
IMAGE_EXTS = {".png", ".gif"}
MAX_IMAGE_SIDE = 1600


def safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name.strip())
    return cleaned or "avatar"


def images_from_folder(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    return [str(path) for path in sorted(folder.iterdir()) if path.is_file() and path.suffix.lower() in IMAGE_EXTS]


def copy_optimized_image(src: Path, dest: Path) -> None:
    if src.suffix.lower() == ".gif":
        shutil.copy2(src, dest)
        return

    try:
        from PIL import Image

        with Image.open(src) as image:
            image.load()
            if max(image.size) > MAX_IMAGE_SIDE:
                image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
            image.save(dest, format="PNG", optimize=True)
    except Exception:
        shutil.copy2(src, dest)


def import_avatar_folder(source: str, name: str) -> dict:
    source_path = Path(source)
    target = AVATAR_DIR / safe_name(name)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    folders = {
        "idle": ("idle",),
        "talk": ("talk", "fala"),
        "talk_low": ("talk_low", "fala_baixa"),
        "talk_mid": ("talk_mid", "fala_media"),
        "talk_high": ("talk_high", "fala_alta"),
    }

    result = {}
    for key, candidates in folders.items():
        src_folder = next((source_path / item for item in candidates if (source_path / item).is_dir()), None)
        dst_folder = target / key
        dst_folder.mkdir(parents=True, exist_ok=True)
        if src_folder:
            for src in images_from_folder(src_folder):
                src_path = Path(src)
                destination = dst_folder / (src_path.stem + src_path.suffix.lower())
                copy_optimized_image(src_path, destination)
        result[key] = images_from_folder(dst_folder)

    manifest = {"name": name, "folders": list(folders.keys())}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


def export_avatar_pack(destination: str, name: str, image_sets: dict, settings: dict) -> None:
    dest = Path(destination)
    manifest = {
        "name": name,
        "settings": settings,
        "sets": {key: [Path(path).name for path in paths] for key, paths in image_sets.items()},
    }
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        for key, paths in image_sets.items():
            for path in paths:
                src = Path(path)
                if src.is_file():
                    archive.write(src, f"{key}/{src.name}")


def import_avatar_pack(pack_path: str) -> dict:
    pack = Path(pack_path)
    with zipfile.ZipFile(pack, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        name = safe_name(manifest.get("name", pack.stem))
        target = AVATAR_DIR / name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        for member in archive.infolist():
            destination = (target / member.filename).resolve()
            if not str(destination).startswith(str(target.resolve())):
                raise ValueError("Avatarpack contem caminho invalido")
            archive.extract(member, target)

    return {
        "name": manifest.get("name", pack.stem),
        "settings": manifest.get("settings", {}),
        "sets": {
            "idle": images_from_folder(target / "idle"),
            "talk": images_from_folder(target / "talk"),
            "talk_low": images_from_folder(target / "talk_low"),
            "talk_mid": images_from_folder(target / "talk_mid"),
            "talk_high": images_from_folder(target / "talk_high"),
        },
    }
