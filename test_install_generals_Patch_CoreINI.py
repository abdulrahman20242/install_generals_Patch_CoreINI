import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

import install_generals_mod as mod


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
        archive.write(text_file, "GeneralsOnlineGameData/hello.txt")

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

        extracted = tmp_path / "GeneralsOnlineGameData" / "hello.txt"
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


class _FakeWinreg:
    HKEY_CURRENT_USER = 0

    @staticmethod
    def OpenKey(_key, _subkey, **_kwargs):
        raise NotImplementedError("OpenKey is called via the real winreg path")


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


class TestConfirmOverwrite:
    def test_returns_true_for_yes(self):
        with patch("builtins.input", return_value="y"):
            assert mod.confirm_overwrite(Path("test")) is True

    def test_returns_true_for_yes_uppercase(self):
        with patch("builtins.input", return_value="YES"):
            assert mod.confirm_overwrite(Path("test")) is True

    def test_returns_false_for_no(self):
        with patch("builtins.input", return_value="n"):
            assert mod.confirm_overwrite(Path("test")) is False


class TestMoveFolder:
    def test_moves_folder_to_parent(self, tmp_path):
        source = tmp_path / "src" / "GeneralsOnlineGameData"
        source.mkdir(parents=True)
        (source / "file.txt").write_text("data")
        destination_parent = tmp_path / "dest"
        destination_parent.mkdir()

        result = mod.move_folder(source, destination_parent)

        assert result == destination_parent / "GeneralsOnlineGameData"
        assert (result / "file.txt").read_text() == "data"
        assert not source.exists()

    def test_removes_existing_destination_on_confirm(self, tmp_path):
        source = tmp_path / "src" / "GeneralsOnlineGameData"
        source.mkdir(parents=True)
        (source / "new.txt").write_text("new data")

        destination_parent = tmp_path / "dest"
        destination_parent.mkdir()
        existing = destination_parent / "GeneralsOnlineGameData"
        existing.mkdir()
        (existing / "old.txt").write_text("old data")

        with patch.object(mod, "confirm_overwrite", return_value=True):
            result = mod.move_folder(source, destination_parent)

        assert (result / "new.txt").read_text() == "new data"
        assert not (result / "old.txt").exists()

    def test_aborts_when_user_declines_overwrite(self, tmp_path):
        source = tmp_path / "src" / "GeneralsOnlineGameData"
        source.mkdir(parents=True)

        destination_parent = tmp_path / "dest"
        destination_parent.mkdir()
        (destination_parent / "GeneralsOnlineGameData").mkdir()

        with patch.object(mod, "confirm_overwrite", return_value=False):
            with pytest.raises(SystemExit, match="0"):
                mod.move_folder(source, destination_parent)


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
