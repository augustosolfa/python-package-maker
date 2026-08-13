import os
import sys
import re
import shutil
import zipfile
import subprocess
import urllib.request
from pathlib import Path

import tomllib

# Define paths relative to this script
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
ASSETS_DIR = BASE_DIR / "assets"
VENV_DIR = BASE_DIR / ".venv"
PYPROJECT_PATH = BASE_DIR / "pyproject.toml"
BUILD_DIR = BASE_DIR / "build"
DIST_DIR = BASE_DIR / "dist"

def log(message: str, level: str = "INFO"):
    prefix = {
        "INFO": "[INFO]",
        "SUCCESS": "[SUCCESS]",
        "WARNING": "[WARNING]",
        "ERROR": "[ERROR]"
    }.get(level, "[INFO]")
    print(f"{prefix} {message}")

def get_project_metadata():
    if not PYPROJECT_PATH.exists():
        log(f"pyproject.toml not found at {PYPROJECT_PATH}", "ERROR")
        sys.exit(1)
    
    try:
        with open(PYPROJECT_PATH, "rb") as f:
            data = tomllib.load(f)
        project = data.get("project", {})
        name = project.get("name")
        version = project.get("version")
        if not name or not version:
            log("pyproject.toml is missing 'name' or 'version' under [project].", "ERROR")
            sys.exit(1)
        return name, version
    except Exception as e:
        log(f"Error parsing pyproject.toml: {e}", "ERROR")
        sys.exit(1)

def get_latest_3_14_version():
    url = "https://www.python.org/ftp/python/"
    log(f"Querying {url} for latest Python 3.14.x release...")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
        
        # Match pattern "3.14.x" where x is a number or tag (e.g. 3.14.7, 3.14.0a5)
        versions = re.findall(r'href=["\']?(3\.14\.\d+(?:[a-zA-Z0-9.]+)?)/?["\']?', html)
        
        # Helper to convert version string into a sortable tuple
        def version_key(v_str):
            parts = v_str.split('.')
            if len(parts) < 3:
                return (0, 0, 0)
            major, minor = int(parts[0]), int(parts[1])
            patch_part = parts[2]
            
            match = re.match(r'^(\d+)(.*)$', patch_part)
            if match:
                patch = int(match.group(1))
                suffix = match.group(2)
                suffix_val = (1, "") if not suffix else (0, suffix)
                return (major, minor, patch, suffix_val)
            return (major, minor, 0, (0, ""))
        
        valid_versions = sorted(set(versions), key=version_key)
        if valid_versions:
            latest = valid_versions[-1]
            log(f"Latest online Python 3.14.x identified as: {latest}")
            return latest
    except Exception as e:
        log(f"Failed to query python.org: {e}. Falling back to 3.14.7", "WARNING")
    
    return "3.14.7"

def resolve_version_and_zip():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Search for any local python-3.14.*-embed-amd64.zip in root or assets first
    local_zips = list(BASE_DIR.glob("python-3.14.*-embed-amd64.zip")) + list(ASSETS_DIR.glob("python-3.14.*-embed-amd64.zip"))
    if local_zips:
        source_zip = local_zips[0]
        match = re.search(r'python-(3\.14\.\d+(?:[a-zA-Z0-9.]+)?)-embed-amd64\.zip', source_zip.name)
        if match:
            version = match.group(1)
            target_zip = ASSETS_DIR / f"python-{version}-embed-amd64.zip"
            if source_zip != target_zip:
                log(f"Found local zip candidate: {source_zip}. Copying to {target_zip}...")
                shutil.copy2(source_zip, target_zip)
            return version, target_zip

    # 2. Query online for latest 3.14 version
    version = get_latest_3_14_version()
    target_zip = ASSETS_DIR / f"python-{version}-embed-amd64.zip"
    
    if target_zip.exists():
        log(f"Found cached embed zip for Python {version} at {target_zip}")
        return version, target_zip
        
    download_url = f"https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip"
    log(f"Downloading {target_zip.name} from {download_url}...")
    try:
        urllib.request.urlretrieve(download_url, target_zip)
        log("Download completed successfully.", "SUCCESS")
        return version, target_zip
    except Exception as e:
        log(f"Failed to download from {download_url}: {e}", "ERROR")
        sys.exit(1)


def copy_site_packages(dest_dir: Path):
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Path to local virtual environment site-packages
    # On Windows, it is typically .venv/Lib/site-packages
    # On Unix/macOS, it would be .venv/lib/python3.x/site-packages
    site_packages_candidates = [
        VENV_DIR / "Lib" / "site-packages",
        VENV_DIR / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
        VENV_DIR / "lib" / "site-packages"
    ]
    
    venv_site_packages = None
    for candidate in site_packages_candidates:
        if candidate.exists() and any(candidate.iterdir()):
            venv_site_packages = candidate
            break
            
    if venv_site_packages:
        log(f"Copying dependencies from virtual environment: {venv_site_packages}")
        # Recursive copy excluding __pycache__ and *.pyc
        def ignore_patterns(path, names):
            ignored = []
            for name in names:
                full_path = Path(path) / name
                if name == "__pycache__" or name.endswith(".pyc"):
                    ignored.append(name)
            return ignored
            
        for item in venv_site_packages.iterdir():
            dest_item = dest_dir / item.name
            if item.is_dir():
                if item.name != "__pycache__":
                    shutil.copytree(item, dest_item, ignore=ignore_patterns, dirs_exist_ok=True)
            else:
                if not item.name.endswith(".pyc"):
                    shutil.copy2(item, dest_item)
        log("Dependencies successfully copied from .venv.", "SUCCESS")
    else:
        log("No valid virtual environment dependencies found in .venv. Falling back to pip install...", "WARNING")
        # Fallback pip install
        try:
            cmd = [
                sys.executable, "-m", "pip", "install", ".",
                "-t", str(dest_dir),
                "--no-user"
            ]
            log(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            log("Pip install fallback succeeded.", "SUCCESS")
            # Clean up __pycache__ and .pyc files created during installation
            for pycache in dest_dir.glob("**/__pycache__"):
                shutil.rmtree(pycache, ignore_errors=True)
            for pyc in dest_dir.glob("**/*.pyc"):
                pyc.unlink(missing_ok=True)
        except subprocess.CalledProcessError as e:
            log(f"Pip install fallback failed: {e.stderr}", "ERROR")
            log("Continuing without dependencies...", "WARNING")

def configure_pth_file(python_dir: Path, version: str):
    # Find the _pth file dynamically in the extracted python directory
    pth_files = list(python_dir.glob("*._pth"))
    major_minor = "".join(version.split(".")[:2])
    if not pth_files:
        pth_file = python_dir / f"python{major_minor}._pth"
    else:
        pth_file = pth_files[0]
        
    log(f"Configuring path file: {pth_file}")
    
    # Required entries
    zip_name = f"python{major_minor}.zip"
    required_paths = [
        zip_name,
        ".",
        "./app",
        "./Lib/site-packages"
    ]

    
    lines = []
    if pth_file.exists():
        with open(pth_file, "r") as f:
            lines = [line.strip() for line in f.readlines()]
            
    # Add required paths if not present
    for path in required_paths:
        if path not in lines:
            lines.insert(0, path)
            
    # Ensure "import site" is uncommented / present at the end
    # In embed editions, "import site" is usually commented out as "#import site"
    has_import_site = False
    for idx, line in enumerate(lines):
        if line == "import site":
            has_import_site = True
            break
        elif line == "#import site":
            lines[idx] = "import site"
            has_import_site = True
            break
            
    if not has_import_site:
        lines.append("import site")
        
    # Write back the _pth file
    with open(pth_file, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    log("Successfully configured path configuration file.", "SUCCESS")

def find_and_copy_vcruntime(dest_dir: Path):
    # Look for vcruntime140.dll in current python sys.prefix, system32, or search path
    candidates = [
        Path(sys.prefix) / "vcruntime140.dll",
        Path(os.path.dirname(sys.executable)) / "vcruntime140.dll",
        Path("C:/Windows/System32/vcruntime140.dll")
    ]
    for candidate in candidates:
        if candidate.exists():
            log(f"Found vcruntime140.dll at {candidate}. Copying for portability...")
            shutil.copy2(candidate, dest_dir / "vcruntime140.dll")
            return
    log("vcruntime140.dll not found in default locations. Skipping copy...", "WARNING")

def create_launcher(build_dir: Path):
    launcher_path = build_dir / "run.bat"
    log(f"Generating launcher: {launcher_path}")
    
    bat_content = (
        "@echo off\n"
        'setlocal\n'
        'cd /d "%~dp0"\n'
        'start "" "%~dp0python\\python.exe" "%~dp0app\\main.py" %*\n'
        'endlocal\n'
    )
    # Note: Using start runs it as a background process or standard window. 
    # The requirement specifies:
    # @echo off
    # "%~dp0python\python.exe" "%~dp0app\main.py" %*
    # Let's write the exact script requested, as it runs synchronously and returns output to console.
    exact_bat_content = (
        "@echo off\n"
        '"%~dp0python\\python.exe" "%~dp0app\\main.py" %*\n'
    )
    
    with open(launcher_path, "w", newline="\r\n") as f:
        f.write(exact_bat_content)
    log("Launcher run.bat generated.", "SUCCESS")

def create_zip_archive(name: str, version: str):
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    archive_name = DIST_DIR / f"{name}-{version}.zip"
    
    log(f"Compressing build folder to archive: {archive_name}")
    
    with zipfile.ZipFile(archive_name, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in BUILD_DIR.rglob("*"):
            if file_path.is_file():
                # Store relative to build directory
                arcname = file_path.relative_to(BUILD_DIR)
                zip_file.write(file_path, arcname)
                
    log(f"Archive successfully generated at {archive_name}", "SUCCESS")

def main():
    log("Starting portable Windows packaging process...")
    
    name, version = get_project_metadata()
    log(f"Project Metadata: {name} (v{version})")
    
    # Setup directories
    if BUILD_DIR.exists():
        log(f"Cleaning previous build directory: {BUILD_DIR}")
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Resolve and extract Embed Archive
    embed_version, embed_zip = resolve_version_and_zip()
    python_dest = BUILD_DIR / "python"
    log(f"Extracting {embed_zip.name} into {python_dest}...")
    with zipfile.ZipFile(embed_zip, "r") as zip_ref:
        zip_ref.extractall(python_dest)
        
    # 2. Copy source code
    app_dest = BUILD_DIR / "app"
    log(f"Copying app source code to {app_dest}...")
    if not SRC_DIR.exists():
        log(f"Source directory {SRC_DIR} does not exist!", "ERROR")
        sys.exit(1)
    shutil.copytree(SRC_DIR, app_dest, dirs_exist_ok=True)
    
    # 3. Copy dependencies / fallback installation
    site_packages_dest = python_dest / "Lib" / "site-packages"
    copy_site_packages(site_packages_dest)
    
    # 4. Configure ._pth file
    configure_pth_file(python_dest, embed_version)
    
    # 5. Copy vcruntime140.dll if available
    find_and_copy_vcruntime(python_dest)
    
    # 6. Create Launcher
    create_launcher(BUILD_DIR)
    
    # 7. Package to Zip
    create_zip_archive(name, version)
    
    # 8. Clean up build folder
    log(f"Cleaning up temporary build folder: {BUILD_DIR}")
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    
    log("Build process completed successfully!", "SUCCESS")

if __name__ == "__main__":
    main()
