"""
JSON Utilities with Corruption Protection

Provides safe JSON operations with:
- Atomic writes (write to temp file, then rename)
- Automatic backups before writes
- JSON validation
- Checksum verification
- Automatic recovery from backups
"""

import json
import os
import shutil
import hashlib
import tempfile
from pathlib import Path
from typing import Any, Optional, Dict
from datetime import datetime
import logging

# Import logger
try:
    from .logger_config import get_logger
    logger = get_logger("main")
except ImportError:
    try:
        from logger_config import get_logger  # Fallback for legacy imports
        logger = get_logger("main")
    except ImportError:
        import logging
        logger = logging.getLogger(__name__)


class JSONCorruptionError(Exception):
    """Raised when JSON file is corrupted and cannot be recovered"""
    pass


def calculate_checksum(data: str) -> str:
    """Calculate SHA256 checksum of data"""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def validate_json(data: Any) -> bool:
    """Validate that data can be serialized to JSON"""
    try:
        json.dumps(data)
        return True
    except (TypeError, ValueError):
        return False


def create_file_backup(file_path: Path, max_backups: int = 5) -> Optional[Path]:
    """
    Create a backup of a file before modification
    
    Args:
        file_path: Path to file to backup
        max_backups: Maximum number of backups to keep
    
    Returns:
        Path to backup file, or None if backup failed
    """
    if not file_path.exists():
        return None
    
    try:
        # Create backup directory
        backup_dir = file_path.parent / ".backups"
        backup_dir.mkdir(exist_ok=True)
        
        # Create timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = backup_dir / backup_name
        
        # Copy file
        shutil.copy2(file_path, backup_path)
        logger.debug(f"Created backup: {backup_path}")
        
        # Clean up old backups (keep only max_backups most recent)
        backups = sorted(backup_dir.glob(f"{file_path.stem}_*{file_path.suffix}"), 
                        key=lambda p: p.stat().st_mtime, reverse=True)
        for old_backup in backups[max_backups:]:
            try:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup}")
            except Exception as e:
                logger.warning(f"Could not remove old backup {old_backup}: {e}")
        
        return backup_path
    except Exception as e:
        logger.warning(f"Could not create backup for {file_path}: {e}")
        return None


def safe_json_load(file_path: Path, default: Any = None, create_if_missing: bool = False) -> Any:
    """
    Safely load JSON file with automatic recovery from backups
    
    Args:
        file_path: Path to JSON file
        default: Default value if file doesn't exist and create_if_missing is False
        create_if_missing: If True, create file with default value if missing
    
    Returns:
        Loaded data, or default if file doesn't exist
    
    Raises:
        JSONCorruptionError: If file is corrupted and cannot be recovered
    """
    if not file_path.exists():
        if create_if_missing and default is not None:
            safe_json_save(file_path, default)
            return default
        return default
    
    # Try to load the file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.debug(f"Successfully loaded JSON: {file_path}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {e}")
        
        # Try to recover from backup
        backup_dir = file_path.parent / ".backups"
        if backup_dir.exists():
            backups = sorted(backup_dir.glob(f"{file_path.stem}_*{file_path.suffix}"), 
                           key=lambda p: p.stat().st_mtime, reverse=True)
            
            for backup in backups:
                try:
                    logger.info(f"Attempting recovery from backup: {backup}")
                    with open(backup, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Backup worked! Restore it
                    logger.info(f"Recovery successful! Restoring from {backup}")
                    shutil.copy2(backup, file_path)
                    return data
                except Exception as backup_error:
                    logger.warning(f"Backup {backup} also corrupted: {backup_error}")
                    continue
        
        # All backups failed, raise error
        raise JSONCorruptionError(f"JSON file {file_path} is corrupted and cannot be recovered")
    
    except Exception as e:
        logger.error(f"Unexpected error loading JSON {file_path}: {e}")
        raise


def safe_json_save(file_path: Path, data: Any, create_backup: bool = True, 
                   validate: bool = True, checksum: bool = False) -> bool:
    """
    Safely save JSON file with atomic write and backup
    
    Args:
        file_path: Path to save JSON file
        data: Data to save
        create_backup: If True, create backup before saving
        validate: If True, validate data before saving
        checksum: If True, save checksum file alongside JSON
    
    Returns:
        True if save was successful, False otherwise
    """
    try:
        # Validate data
        if validate and not validate_json(data):
            logger.error(f"Data validation failed for {file_path}")
            return False
        
        # Create backup if file exists
        if create_backup and file_path.exists():
            backup_path = create_file_backup(file_path)
        
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Atomic write: write to temp file, then rename
        temp_file = None
        try:
            # Create temp file in same directory (for atomic rename)
            temp_fd, temp_path = tempfile.mkstemp(
                suffix='.json.tmp',
                dir=file_path.parent,
                text=True
            )
            temp_file = Path(temp_path)
            
            # Write JSON to temp file
            with open(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Calculate checksum if requested
            if checksum:
                with open(temp_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                checksum_value = calculate_checksum(content)
                checksum_file = file_path.with_suffix(file_path.suffix + '.checksum')
                checksum_file.write_text(checksum_value)
            
            # Atomic rename (this is the critical step)
            temp_file.replace(file_path)
            
            logger.debug(f"Successfully saved JSON: {file_path}")
            return True
            
        except Exception as e:
            # Clean up temp file on error
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise
        
    except Exception as e:
        logger.error(f"Error saving JSON {file_path}: {e}", exc_info=True)
        return False


def verify_json_checksum(file_path: Path) -> bool:
    """
    Verify JSON file against checksum file
    
    Returns:
        True if checksum matches, False otherwise
    """
    checksum_file = file_path.with_suffix(file_path.suffix + '.checksum')
    if not checksum_file.exists():
        logger.warning(f"No checksum file for {file_path}")
        return False
    
    try:
        expected_checksum = checksum_file.read_text().strip()
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        actual_checksum = calculate_checksum(content)
        
        if expected_checksum == actual_checksum:
            logger.debug(f"Checksum verified for {file_path}")
            return True
        else:
            logger.warning(f"Checksum mismatch for {file_path}")
            return False
    except Exception as e:
        logger.error(f"Error verifying checksum for {file_path}: {e}")
        return False


def restore_from_backup(file_path: Path, backup_index: int = 0) -> bool:
    """
    Restore file from a specific backup
    
    Args:
        file_path: Path to file to restore
        backup_index: Index of backup to restore (0 = most recent)
    
    Returns:
        True if restore was successful, False otherwise
    """
    backup_dir = file_path.parent / ".backups"
    if not backup_dir.exists():
        logger.error(f"No backup directory found for {file_path}")
        return False
    
    backups = sorted(backup_dir.glob(f"{file_path.stem}_*{file_path.suffix}"), 
                    key=lambda p: p.stat().st_mtime, reverse=True)
    
    if backup_index >= len(backups):
        logger.error(f"Backup index {backup_index} out of range (found {len(backups)} backups)")
        return False
    
    try:
        backup = backups[backup_index]
        logger.info(f"Restoring {file_path} from backup: {backup}")
        shutil.copy2(backup, file_path)
        logger.info(f"Successfully restored {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error restoring {file_path} from backup: {e}")
        return False


def list_backups(file_path: Path) -> list[Path]:
    """List all available backups for a file"""
    backup_dir = file_path.parent / ".backups"
    if not backup_dir.exists():
        return []
    
    backups = sorted(backup_dir.glob(f"{file_path.stem}_*{file_path.suffix}"), 
                    key=lambda p: p.stat().st_mtime, reverse=True)
    return backups

