import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

DOWNLOAD_URL = (
    "https://github.com/ReizanTech/Additional-content-in-Command-Conquer-"
    "Generals-Zero-Hour/releases/download/has-modified-INI-files/"
    "GeneralsOnlineGameData.zip"
)

VERIFY_FILENAME = "500_900_CommunityPatch_CoreINI.big"
DESTINATION_FOLDER = "Command and Conquer Generals Zero Hour Data"


def download_file(url, destination_path):
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))
    chunk_size = 8192

    with open(destination_path, "wb") as file, tqdm(
        total=total_size, unit="B", unit_scale=True, desc="Downloading"
    ) as progress_bar:
        for chunk in response.iter_content(chunk_size=chunk_size):
            file.write(chunk)
            progress_bar.update(len(chunk))


def extract_zip(zip_path, extraction_folder):
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extraction_folder)


def resolve_documents_folder():
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as key:
            return Path(winreg.QueryValueEx(key, "Personal")[0])
    except (ImportError, OSError):
        return Path.home() / "Documents"


def confirm_overwrite(destination_folder):
    user_input = input(
        f"'{destination_folder.name}' already exists. "
        "Overwrite it? (y/n): "
    )
    return user_input.strip().lower() in ("y", "yes")


def move_folder(source_folder, destination_parent):
    destination_path = destination_parent / source_folder.name

    if destination_path.exists():
        if not confirm_overwrite(destination_path):
            print("Aborted by user.")
            sys.exit(0)
        shutil.rmtree(destination_path)

    shutil.move(str(source_folder), str(destination_path))
    return destination_path


def verify_core_ini(mod_folder_path):
    verification_target = mod_folder_path / VERIFY_FILENAME
    if verification_target.exists():
        print(f"✅ Verified: '{VERIFY_FILENAME}' exists at {verification_target}")
        return True

    print(f"❌ Error: '{VERIFY_FILENAME}' not found at {verification_target}")
    print(
        "The mod files may be corrupted or the archive structure has changed. "
        "Download the archive again and retry."
    )
    return False


def cleanup_temporary_files(zip_path, extraction_folder):
    if zip_path.exists():
        zip_path.unlink()
    if extraction_folder.exists():
        shutil.rmtree(extraction_folder)


def main():
    temp_folder = Path(tempfile.mkdtemp(prefix="generals_mod_"))
    zip_path = temp_folder / "GeneralsOnlineGameData.zip"

    try:
        print("Step 1/5: Downloading mod archive...")
        try:
            download_file(DOWNLOAD_URL, zip_path)
        except requests.ConnectionError:
            print(
                "Failed to connect. Check your internet connection and retry."
            )
            sys.exit(1)
        except requests.Timeout:
            print("Download timed out. Try again later.")
            sys.exit(1)
        except requests.HTTPError as exc:
            print(f"Server returned an error: {exc.response.status_code}")
            sys.exit(1)

        print("Step 2/5: Extracting archive...")
        try:
            extract_zip(zip_path, temp_folder)
        except zipfile.BadZipFile:
            print(
                "The downloaded file is not a valid ZIP archive. "
                "Redownload and retry."
            )
            sys.exit(1)

        extraction_target = temp_folder / "GeneralsOnlineGameData"
        if not extraction_target.exists():
            print(
                "Extracted folder structure unexpected. "
                "The archive may have been modified upstream."
            )
            sys.exit(1)

        print("Step 3/5: Resolving destination path...")
        documents_folder = resolve_documents_folder()
        destination_parent = documents_folder / DESTINATION_FOLDER
        destination_parent.mkdir(parents=True, exist_ok=True)

        print("Step 4/5: Moving mod files to Documents...")
        try:
            installed_path = move_folder(extraction_target, destination_parent)
        except PermissionError:
            print(
                "Permission denied. Close any application using the "
                "target folder and run this script as Administrator."
            )
            sys.exit(1)
        except shutil.Error as exc:
            print(f"Failed to move files: {exc}")
            sys.exit(1)

        print("Step 5/5: Verifying installation...")
        if not verify_core_ini(installed_path):
            sys.exit(1)

        print("Done.")
    finally:
        cleanup_temporary_files(zip_path, temp_folder)


if __name__ == "__main__":
    main()
