# Generals Online — Community Patch Installer

Automated installer for the Command & Conquer Generals Zero Hour community-modified INI files. Downloads the archive from GitHub, extracts it, and installs it into the correct Documents path on Windows.

## Installation

### Option 1: Download the executable

Download `GeneralsPatchInstaller.exe` from [Releases](https://github.com/abdulrahman20242/install_generals_Patch_CoreINI/releases) and run it directly — no Python required.

### Option 2: Clone and run from source

```bash
git clone https://github.com/abdulrahman20242/install_generals_Patch_CoreINI.git
cd install_generals_Patch_CoreINI
```

Set up a virtual environment and install dependencies:

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Run the installer:

```bash
python install_generals_Patch_CoreINI.py
```

### Build with PyInstaller

To build a standalone `.exe`:

```bash
pyinstaller --onefile install_generals_Patch_CoreINI.py
```

The executable will be in `dist\install_generals_Patch_CoreINI.exe`.

## What it does

1. Downloads `GeneralsOnlineGameData.zip` from the GitHub release
2. Extracts the archive to a temporary folder
3. Detects the current user's Documents path (via Windows registry, with fallback)
4. Moves the extracted `GeneralsOnlineGameData` folder to:
   ```
   Documents\Command and Conquer Generals Zero Hour Data\GeneralsOnlineGameData
   ```
5. Verifies that `500_900_CommunityPatch_CoreINI.big` exists in the installed folder
6. Cleans up all temporary files

## Requirements

- **Python 3.10+**
- **Windows** (Documents path resolved via `winreg` with `Path.home() / "Documents"` fallback)
- **Internet connection** for the initial download

## Usage

The script prints progress for each step and prompts for confirmation when a previous installation is detected (the `500_900_CommunityPatch_CoreINI.big` verification file exists in the destination).

### Example output

```
Step 1/5: Downloading mod archive...
Downloading: 100%|████████████████| 15.2M/15.2M [00:03<00:00, 4.8MB/s]
Step 2/5: Extracting archive...
Step 3/5: Resolving destination path...
Step 4/5: Moving mod files to Documents...
Step 5/5: Verifying installation...
✅ Verified: '500_900_CommunityPatch_CoreINI.big' exists at C:\Users\<user>\Documents\Command and Conquer Generals Zero Hour Data\GeneralsOnlineGameData\500_900_CommunityPatch_CoreINI.big
Done.
```

## Error handling

| Error | Message | Cause |
|---|---|---|
| `ConnectionError` | Failed to connect. Check your internet connection and retry. | No network or DNS failure |
| `Timeout` | Download timed out. Try again later. | Server unresponsive |
| `HTTPError` | Server returned an error: `<status_code>` | Non-200 response from GitHub |
| `BadZipFile` | The downloaded file is not a valid ZIP archive. | Corrupted download |
| Unexpected structure | Extracted folder structure unexpected. | Archive contents changed upstream |
| `PermissionError` | Permission denied. Close any application using the target folder and run this script as Administrator. | Folder locked by another process |
| Missing verification file | `❌ Error: '500_900_CommunityPatch_CoreINI.big' not found` | Incomplete extraction or corrupted archive |

Temporary files are always cleaned up, even when the script exits with an error.

## Testing

```bash
pytest test_install_generals_Patch_CoreINI.py -v
```

The test suite covers all functions with 20 tests across 8 test classes:

| Class | Tests | What it covers |
|---|---|---|
| `TestDownloadFile` | 4 | Bytes written to disk; 3 network failure modes |
| `TestExtractZip` | 2 | Valid extraction; corrupt ZIP rejection |
| `TestResolveDocumentsFolder` | 2 | Registry path; fallback when winreg is absent |
| `TestConfirmFileOverwrite` | 3 | "y", "YES" → True; "n" → False |
| `TestMoveFolder` | 2 | Fresh move; overwrite replaces old |
| `TestCoreIniAlreadyInstalled` | 3 | Big file present; empty folder; folder absent |
| `TestVerifyCoreIni` | 2 | File exists → True; file missing → False |
| `TestCleanupTemporaryFiles` | 2 | Removes paths; handles already-deleted paths |

## Project structure

```
.
├── install_generals_Patch_CoreINI.py      # Main application
├── test_install_generals_Patch_CoreINI.py  # Test suite (pytest)
├── requirements.txt                        # Python dependencies
├── README.md
└── .gitignore
```

## License

This project downloads and installs community-created content for Command & Conquer Generals Zero Hour. The installer script itself is provided as-is.
