import os
import zipfile
from pathlib import Path

def create_project_zip():
    base_dir = Path(__file__).resolve().parent.parent
    output_zip = base_dir.parent / "omni-flow-ai.zip"
    
    # Also save inside the project folder for convenience
    local_zip = base_dir / "omni-flow-ai.zip"
    
    exclude_dirs = {".venv", "__pycache__", ".pytest_cache", ".git"}
    exclude_extensions = {".pyc", ".pyo", ".png"}
    exclude_files = {"omniflow.db", "omni-flow-ai.zip"}

    print(f"Creating zip archive of {base_dir}...")
    
    total_files = 0
    total_bytes = 0
    
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base_dir):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for f in files:
                if f in exclude_files:
                    continue
                file_path = Path(root) / f
                if file_path.suffix.lower() in exclude_extensions:
                    continue
                
                # Relative path inside zip
                rel_path = file_path.relative_to(base_dir)
                archive_name = Path("omni-flow-ai") / rel_path
                
                zf.write(file_path, arcname=str(archive_name))
                total_files += 1
                total_bytes += file_path.stat().st_size
                
    # Copy to local_zip as well
    import shutil
    shutil.copyfile(output_zip, local_zip)
    
    zip_size_kb = output_zip.stat().st_size / 1024
    print(f"[SUCCESS] Packaged {total_files} files ({total_bytes / 1024:.1f} KB uncompressed).")
    print(f"[OUTPUT] Primary Zip Path: {output_zip} ({zip_size_kb:.1f} KB)")
    print(f"[OUTPUT] Local Copy:       {local_zip}")
    return output_zip

if __name__ == "__main__":
    create_project_zip()
