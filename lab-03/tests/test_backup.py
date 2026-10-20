import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

BACKUP_SCRIPT = Path(__file__).resolve().parents[1] / "backup.sh"


class TestBackupScript(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source"
        self.destination = self.root / "backups"

        self.source.mkdir()
        (self.source / "example.txt").write_text(
            "DevOps backup test", encoding="utf-8"
        )

    def run_backup(self, *extra_args):
        return subprocess.run(
            [
                "bash",
                str(BACKUP_SCRIPT),
                "--source",
                str(self.source),
                "--dest",
                str(self.destination),
                *extra_args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_creates_archive(self):
        result = self.run_backup()

        self.assertEqual(result.returncode, 0, result.stderr)

        archives = list(self.destination.glob("*.tar.gz"))
        self.assertEqual(len(archives), 1)

        with tarfile.open(archives[0], "r:gz") as archive:
            names = archive.getnames()
            self.assertTrue(
                any(name.endswith("example.txt") for name in names)
            )

    def test_dry_run_does_not_create_archive(self):
        result = self.run_backup("--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.destination.exists())

    def test_invalid_source_returns_error(self):
        self.source.rename(self.root / "renamed-source")

        result = self.run_backup()

        self.assertNotEqual(result.returncode, 0)

    def test_keep_one_archive(self):
        result = self.run_backup("--keep", "1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            len(list(self.destination.glob("*.tar.gz"))), 1
        )


if __name__ == "__main__":
    unittest.main()
