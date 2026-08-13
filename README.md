# python-package-maker

A small standalone script (`build.py`) that packages Python projects into portable Windows `.zip` releases using the official Python Embedded distribution.

## Why?

| Feature | PyInstaller / Nuitka | This Embedded Template |
| --- | --- | --- |
| **Antivirus Detection** | High risk of false positives | Zero (Uses official python.exe) |
| **Startup Speed** | Slow (unpacks temp files) | Instant (Runs directly) |
| **Debugging / Modifying** | Hard (compiled binary) | Easy (Source code remains readable) |
| **Build Dependencies** | Requires PyInstaller/C-compilers | Pure Python (Stdlib only) |
| **CI Overhead** | Heavy build step | Lightweight & Fast |

## How to use

1. Place source code in `src/` (entry point: `src/main.py`).
2. Configure project metadata, dependencies, and launcher options (e.g., `python.exe` vs `pythonw.exe`) in `pyproject.toml`.
3. Run:
   ```cmd
   python build.py
   ```

The packaged archive will be saved in `dist/`.
