import hashlib
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: install-novnc.py VERSION SHA256 TARGET")

    version, expected_sha256, target_value = sys.argv[1:]
    archive_url = f"https://github.com/novnc/noVNC/archive/refs/tags/v{version}.tar.gz"

    with urllib.request.urlopen(archive_url, timeout=60) as response:
        archive_data = response.read()

    actual_sha256 = hashlib.sha256(archive_data).hexdigest()
    if actual_sha256 != expected_sha256.lower():
        raise RuntimeError(f"noVNC archive checksum mismatch: expected {expected_sha256}, got {actual_sha256}")

    target = Path(target_value)
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        archive_path = temporary_path / "novnc.tar.gz"
        archive_path.write_bytes(archive_data)

        with tarfile.open(archive_path, mode="r:gz") as archive:
            archive.extractall(temporary_path, filter="data")

        source = temporary_path / f"noVNC-{version}"
        if not (source / "vnc.html").is_file():
            raise RuntimeError("downloaded noVNC archive does not contain vnc.html")

        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(source, target)


if __name__ == "__main__":
    main()
