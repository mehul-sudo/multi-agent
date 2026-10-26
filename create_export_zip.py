import os
import shutil
import zipfile
import time

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DOWNLOADS = os.path.dirname(SOURCE_DIR)

LOCAL_ZIP = os.path.join(SOURCE_DIR, "multi_agent_ai_assistant.zip")
TARGET_DOWNLOADS_ZIP = os.path.join(PARENT_DOWNLOADS, "multi_agent_ai_assistant.zip")

EXCLUDED_DIRS = {
    ".git", ".hg", ".svn",
    ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache",
    "venv", ".venv", "env", "ENV",
    "node_modules", ".idea", ".vscode",
}

EXCLUDED_EXTS = {
    ".pyc", ".pyo", ".pyd",
    ".zip",  # never nest archives
}

EXCLUDED_FILES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    "dev.db",
    "test.db",
    "export_temp.zip",
    "multi_agent_ai_assistant.zip",
}

def should_skip(filename: str) -> bool:
    name_lower = filename.lower()
    ext = os.path.splitext(filename)[1].lower()
    if ext in EXCLUDED_EXTS:
        return True
    if name_lower in EXCLUDED_FILES:
        return True
    if name_lower.startswith(".env") and not name_lower.endswith(".example"):
        return True
    if name_lower.endswith(".db") or name_lower.endswith(".sqlite"):
        return True
    return False

def main() -> None:
    print(f"Creating export zip from: {SOURCE_DIR}")
    start_time = time.time()

    # Clean existing temporary or old zip files if present
    temp_zip = os.path.join(SOURCE_DIR, "export_temp.zip")
    if os.path.exists(temp_zip):
        try:
            os.remove(temp_zip)
        except Exception:
            pass

    count = 0
    with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
        for root, dirs, files in os.walk(SOURCE_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for filename in files:
                if should_skip(filename):
                    continue
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, SOURCE_DIR)
                # Standard archive layout with root-relative paths
                zipf.write(full_path, arcname=rel_path)
                count += 1

    # Atomically replace LOCAL_ZIP
    if os.path.exists(LOCAL_ZIP):
        try:
            os.remove(LOCAL_ZIP)
        except Exception:
            pass
    shutil.move(temp_zip, LOCAL_ZIP)

    size_mb = round(os.path.getsize(LOCAL_ZIP) / (1024 * 1024), 2)
    elapsed = round(time.time() - start_time, 2)
    print(f"Successfully packaged {count} files in {elapsed}s:")
    print(f"  -> Local ZIP: {LOCAL_ZIP} ({size_mb} MB)")

    # Also copy to Downloads directory
    try:
        shutil.copyfile(LOCAL_ZIP, TARGET_DOWNLOADS_ZIP)
        print(f"  -> Downloads ZIP: {TARGET_DOWNLOADS_ZIP}")
    except Exception as e:
        print(f"  Warning: Could not copy to {TARGET_DOWNLOADS_ZIP}: {e}")

if __name__ == "__main__":
    main()
