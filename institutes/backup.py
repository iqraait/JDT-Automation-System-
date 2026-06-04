import os
import zipfile
from django.conf import settings

def generate_zip_backup(buffer):
    """
    Writes a compressed ZIP backup of the project codebase, database,
    and media uploads directly to the provided buffer.
    Excludes large/temporary/virtualenv files to keep backup size small.
    """
    exclude_items = {'.git', 'venv', 'staticfiles', '__pycache__', 'backups', 'scratch'}
    base_dir = str(settings.BASE_DIR)
    
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(base_dir):
            # Prune excluded directories in-place so os.walk doesn't descend into them
            dirs[:] = [d for d in dirs if d not in exclude_items]
            
            for file in files:
                # Exclude temporary sqlite files and python cache files
                if file.endswith('.pyc') or file.endswith('.pyo') or file == 'db.sqlite3-journal':
                    continue
                
                file_path = os.path.join(root, file)
                # Ensure the file is not a symlink to prevent infinite loops
                if not os.path.islink(file_path):
                    rel_path = os.path.relpath(file_path, base_dir)
                    zip_file.write(file_path, rel_path)
