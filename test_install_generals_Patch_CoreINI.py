import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

import install_generals_Patch_CoreINI as mod


def _build_fake_response(content=b"data"):
    response = requests.Response()
    response.status_code = 200
    response.headers["content-length"] = str(len(content))
    response.raw = io.BytesIO(content)
    return response


@pytest.fixture()
def fake_zip(tmp_path):
    zip_path = tmp_path / "test.zip"
    inner_dir = tmp_path / "extract"
    inner_dir.mkdir()

    text_file = inner_dir / "hello.txt"
    text_file.write_text("mod content")

    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(text_file, f"{mod.MOD_FOLDER_NAME}/hello.txt")

    return zip_path


class TestDownloadFile:
    def test_writes_bytes_to_disk(self, tmp_path):
        destination = tmp_path / "output.zip"
        content = b"fake zip bytes"

        with patch.object(
            requests, "get", return_value=_build_fake_response(content)
        ):
            mod.download_file("https://example.com/file.zip", destination)

        assert destination.read_bytes() == content

    @pytest.mark.parametrize(
        "exception",
        [
            requests.ConnectionError("no route"),
            requests.Timeout("timed out"),
            requests.HTTPError(response=requests.Response()),
        ],
        ids=["connection", "timeout", "http_error"],
    )
    def test_propagates_network_errors(self, exception):
        with patch.object(requests, "get", side_effect=exception):
            with pytest.raises(type(exception)):
                mod.download_file("https://example.com/file.zip", Path("/x"))


class TestExtractZip:
    def test_creates_inner_folder_with_files(self, tmp_path, fake_zip):
        mod.extract_zip(fake_zip, tmp_path)

        extracted = tmp_path / mod.MOD_FOLDER_NAME / "hello.txt"
        assert extracted.read_text() == "mod content"

    def test_raises_on_corrupt_zip(self, tmp_path):
        corrupt = tmp_path / "corrupt.zip"
        corrupt.write_bytes(b"not a real zip")

        with pytest.raises(zipfile.BadZipFile):
            mod.extract_zip(corrupt, tmp_path)


class _FakeRegistryKey:
    def __init__(self, path):
        self._path = path

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def QueryValueEx(self, _subkey):
        return (self._path, 0)


class TestResolveDocumentsFolder:
    @patch.dict("sys.modules", {"winreg": None})
    def test_falls_back_to_home_when_winreg_missing(self):
        result = mod.resolve_documents_folder()

        assert result == Path.home() / "Documents"

    def test_uses_winreg_personal_key(self, tmp_path):
        fake_path = str(tmp_path / "CustomDocs")

        fake_winreg = type("FakeWinreg", (), {
            "HKEY_CURRENT_USER": 0,
            "OpenKey": classmethod(
                lambda cls, *a, **kw: _FakeRegistryKey(fake_path)
            ),
            "QueryValueEx": staticmethod(
                lambda key, _subkey: (fake_path, 0)
            ),
        })()

        with patch.dict("sys.modules", {"winreg": fake_winreg}):
            result = mod.resolve_documents_folder()

        assert result == Path(fake_path)


class TestConfirmFileOverwrite:
    @pytest.mark.parametrize(
        ("user_input", "expected"),
        [
            ("y", True),
            ("YES", True),
            ("n", False),
        ],
        ids=["lowercase_yes", "uppercase_yes", "lowercase_no"],
    )
    def test_accepts_yes_rejects_no(self, user_input, expected):
        with patch("builtins.input", return_value=user_input):
            assert mod.confirm_file_overwrite() is expected


class TestMoveFolder:
    def test_moves_folder_to_parent(self, tmp_path):
        source = tmp_path / "src" / mod.MOD_FOLDER_NAME
        source.mkdir(parents=True)
        (source / "file.txt").write_text("data")
        destination_parent = tmp_path / "dest"
        destination_parent.mkdir()

        result = mod.move_folder(source, destination_parent)

        assert result == destination_parent / mod.MOD_FOLDER_NAME
        assert (result / "file.txt").read_text() == "data"
        assert not source.exists()

    def test_removes_existing_destination_before_move(self, tmp_path):
        source = tmp_path / "src" / mod.MOD_FOLDER_NAME
        source.mkdir(parents=True)
        (source / "new_file.txt").write_text("new data")

        destination_parent = tmp_path / "dest"
        destination_parent.mkdir()
        old_dest = destination_parent / mod.MOD_FOLDER_NAME
        old_dest.mkdir()
        (old_dest / "old_file.txt").write_text("old data")

        result = mod.move_folder(source, destination_parent)

        assert result == old_dest
        assert (result / "new_file.txt").read_text() == "new data"
        assert not (result / "old_file.txt").exists()


class TestCoreIniAlreadyInstalled:
    @patch.object(mod, "resolve_documents_folder")
    def test_returns_true_when_big_file_present(self, mock_resolve, tmp_path):
        big_file = (
            tmp_path / mod.DESTINATION_FOLDER
            / mod.MOD_FOLDER_NAME / mod.VERIFY_FILENAME
        )
        big_file.parent.mkdir(parents=True)
        big_file.write_text("binary")

        mock_resolve.return_value = tmp_path

        assert mod.core_ini_already_installed() is True

    @patch.object(mod, "resolve_documents_folder")
    def test_returns_false_when_folder_empty(self, mock_resolve, tmp_path):
        mod_folder = (
            tmp_path / mod.DESTINATION_FOLDER / mod.MOD_FOLDER_NAME
        )
        mod_folder.mkdir(parents=True)

        mock_resolve.return_value = tmp_path

        assert mod.core_ini_already_installed() is False

    @patch.object(mod, "resolve_documents_folder")
    def test_returns_false_when_folder_absent(self, mock_resolve, tmp_path):
        mock_resolve.return_value = tmp_path

        assert mod.core_ini_already_installed() is False


class TestVerifyCoreIni:
    def test_returns_true_when_file_exists(self, tmp_path):
        mod_folder = tmp_path / "mod"
        mod_folder.mkdir()
        (mod_folder / mod.VERIFY_FILENAME).write_text("binary")

        assert mod.verify_core_ini(mod_folder) is True

    def test_returns_false_when_file_missing(self, tmp_path):
        mod_folder = tmp_path / "mod"
        mod_folder.mkdir()

        assert mod.verify_core_ini(mod_folder) is False


class TestCleanupTemporaryFiles:
    def test_removes_zip_and_extraction_folder(self, tmp_path):
        zip_path = tmp_path / "archive.zip"
        zip_path.write_bytes(b"zip data")
        extraction = tmp_path / "extracted"
        extraction.mkdir()

        mod.cleanup_temporary_files(zip_path, extraction)

        assert not zip_path.exists()
        assert not extraction.exists()

    def test_handles_already_deleted_paths(self, tmp_path):
        zip_path = tmp_path / "nonexistent.zip"
        extraction = tmp_path / "nonexistent"

        mod.cleanup_temporary_files(zip_path, extraction)

        assert not zip_path.exists()
        assert not extraction.exists()
