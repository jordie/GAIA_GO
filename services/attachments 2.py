"""
Task Attachments Service

Manages file uploads, storage, and previews for task attachments.

Usage:
    from services.attachments import get_attachment_service

    service = get_attachment_service(db_path, upload_dir)
    attachment = service.upload_file(file, task_id, task_type, user_id)
"""

import hashlib
import logging
import mimetypes
import os
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional

logger = logging.getLogger(__name__)

# Allowed file types and their categories
ALLOWED_EXTENSIONS = {
    # Images
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "gif": "image",
    "webp": "image",
    "svg": "image",
    "ico": "image",
    "bmp": "image",
    # Documents
    "pdf": "document",
    "doc": "document",
    "docx": "document",
    "xls": "document",
    "xlsx": "document",
    "ppt": "document",
    "pptx": "document",
    "txt": "text",
    "md": "text",
    "rst": "text",
    "csv": "text",
    # Code
    "py": "code",
    "js": "code",
    "ts": "code",
    "jsx": "code",
    "tsx": "code",
    "html": "code",
    "css": "code",
    "scss": "code",
    "less": "code",
    "json": "code",
    "yaml": "code",
    "yml": "code",
    "xml": "code",
    "sql": "code",
    "sh": "code",
    "bash": "code",
    "zsh": "code",
    "java": "code",
    "c": "code",
    "cpp": "code",
    "h": "code",
    "go": "code",
    "rs": "code",
    "rb": "code",
    "php": "code",
    # Archives
    "zip": "archive",
    "tar": "archive",
    "gz": "archive",
    "rar": "archive",
    # Data
    "log": "text",
    "ini": "text",
    "conf": "text",
    "env": "text",
}

# Max file size (50 MB)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Image extensions that support preview/thumbnail
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}


class AttachmentService:
    """Service for managing task attachments."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None, upload_dir: str = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None, upload_dir: str = None):
        if self._initialized:
            if db_path:
                self.db_path = db_path
            if upload_dir:
                self.upload_dir = Path(upload_dir)
            return

        self.db_path = db_path
        self.upload_dir = Path(upload_dir) if upload_dir else Path("data/attachments")
        self._ensure_upload_dirs()
        self._initialized = True

    def _ensure_upload_dirs(self):
        """Ensure upload directories exist."""
        dirs = [
            self.upload_dir,
            self.upload_dir / "files",
            self.upload_dir / "previews",
            self.upload_dir / "thumbnails",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_file_hash(self, file_content: bytes) -> str:
        """Calculate SHA-256 hash of file content."""
        return hashlib.sha256(file_content).hexdigest()

    def _get_extension(self, filename: str) -> str:
        """Get lowercase file extension."""
        return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    def _generate_filename(self, original_filename: str) -> str:
        """Generate a unique filename preserving extension."""
        ext = self._get_extension(original_filename)
        unique_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{unique_id}.{ext}" if ext else f"{timestamp}_{unique_id}"

    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type for a file."""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"

    def validate_file(self, filename: str, file_size: int) -> Dict:
        """Validate a file before upload.

        Returns:
            Dict with 'valid' boolean and 'error' message if invalid
        """
        ext = self._get_extension(filename)

        if not ext:
            return {"valid": False, "error": "File must have an extension"}

        if ext not in ALLOWED_EXTENSIONS:
            return {"valid": False, "error": f"File type .{ext} is not allowed"}

        if file_size > MAX_FILE_SIZE:
            max_mb = MAX_FILE_SIZE / (1024 * 1024)
            return {"valid": False, "error": f"File size exceeds {max_mb}MB limit"}

        if file_size == 0:
            return {"valid": False, "error": "File is empty"}

        return {"valid": True, "category": ALLOWED_EXTENSIONS[ext]}

    def upload_file(
        self,
        file_content: bytes,
        original_filename: str,
        task_id: int,
        task_type: str,
        user_id: str,
        description: str = None,
    ) -> Dict:
        """Upload a file attachment.

        Args:
            file_content: File content as bytes
            original_filename: Original filename
            task_id: ID of the task
            task_type: Type of task
            user_id: User uploading the file
            description: Optional description

        Returns:
            Attachment info dict
        """
        # Validate
        validation = self.validate_file(original_filename, len(file_content))
        if not validation["valid"]:
            raise ValueError(validation["error"])

        # Calculate hash for deduplication
        file_hash = self._get_file_hash(file_content)

        # Check for duplicate (same file already uploaded to same task)
        with self._get_connection() as conn:
            existing = conn.execute(
                """
                SELECT * FROM task_attachments
                WHERE task_id = ? AND task_type = ? AND file_hash = ?
            """,
                (task_id, task_type, file_hash),
            ).fetchone()

            if existing:
                return dict(existing)

        # Generate unique filename and save
        filename = self._generate_filename(original_filename)
        file_path = self.upload_dir / "files" / filename

        with open(file_path, "wb") as f:
            f.write(file_content)

        # Get MIME type
        mime_type = self._get_mime_type(original_filename)

        # Generate preview/thumbnail for images
        has_preview = False
        preview_path = None
        thumbnail_path = None

        ext = self._get_extension(original_filename)
        if ext in IMAGE_EXTENSIONS:
            try:
                preview_path, thumbnail_path = self._generate_image_previews(file_path, filename)
                has_preview = True
            except Exception as e:
                logger.warning(f"Failed to generate preview: {e}")

        # Save to database
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO task_attachments
                (task_id, task_type, filename, original_filename, file_path,
                 file_size, mime_type, file_hash, description, uploaded_by,
                 has_preview, preview_path, thumbnail_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task_id,
                    task_type,
                    filename,
                    original_filename,
                    str(file_path),
                    len(file_content),
                    mime_type,
                    file_hash,
                    description,
                    user_id,
                    has_preview,
                    preview_path,
                    thumbnail_path,
                ),
            )
            conn.commit()

            attachment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            attachment = conn.execute(
                "SELECT * FROM task_attachments WHERE id = ?", (attachment_id,)
            ).fetchone()

            logger.info(f"Uploaded attachment {filename} for {task_type} {task_id}")
            return dict(attachment)

    def _generate_image_previews(self, file_path: Path, filename: str) -> tuple:
        """Generate preview and thumbnail for an image.

        Returns:
            Tuple of (preview_path, thumbnail_path)
        """
        try:
            from PIL import Image

            with Image.open(file_path) as img:
                # Convert to RGB if necessary (for PNG with transparency)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Generate preview (max 1200px)
                preview = img.copy()
                preview.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                preview_filename = f"preview_{filename.rsplit('.', 1)[0]}.jpg"
                preview_path = self.upload_dir / "previews" / preview_filename
                preview.save(preview_path, "JPEG", quality=85)

                # Generate thumbnail (max 200px)
                thumbnail = img.copy()
                thumbnail.thumbnail((200, 200), Image.Resampling.LANCZOS)
                thumb_filename = f"thumb_{filename.rsplit('.', 1)[0]}.jpg"
                thumbnail_path = self.upload_dir / "thumbnails" / thumb_filename
                thumbnail.save(thumbnail_path, "JPEG", quality=80)

                return str(preview_path), str(thumbnail_path)

        except ImportError:
            logger.warning("PIL not installed, skipping preview generation")
            return None, None

    def get_attachment(self, attachment_id: int) -> Optional[Dict]:
        """Get attachment by ID."""
        with self._get_connection() as conn:
            attachment = conn.execute(
                "SELECT * FROM task_attachments WHERE id = ?", (attachment_id,)
            ).fetchone()
            return dict(attachment) if attachment else None

    def get_task_attachments(self, task_id: int, task_type: str) -> List[Dict]:
        """Get all attachments for a task."""
        with self._get_connection() as conn:
            attachments = conn.execute(
                """
                SELECT * FROM task_attachments
                WHERE task_id = ? AND task_type = ?
                ORDER BY created_at DESC
            """,
                (task_id, task_type),
            ).fetchall()
            return [dict(a) for a in attachments]

    def get_user_attachments(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get attachments uploaded by a user."""
        with self._get_connection() as conn:
            attachments = conn.execute(
                """
                SELECT * FROM task_attachments
                WHERE uploaded_by = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (user_id, limit),
            ).fetchall()
            return [dict(a) for a in attachments]

    def delete_attachment(self, attachment_id: int, user_id: str = None) -> bool:
        """Delete an attachment.

        Args:
            attachment_id: Attachment ID
            user_id: If provided, only delete if user is owner

        Returns:
            True if deleted, False if not found
        """
        with self._get_connection() as conn:
            # Get attachment info
            attachment = conn.execute(
                "SELECT * FROM task_attachments WHERE id = ?", (attachment_id,)
            ).fetchone()

            if not attachment:
                return False

            # Check ownership if user_id provided
            if user_id and attachment["uploaded_by"] != user_id:
                raise PermissionError("Cannot delete attachment uploaded by another user")

            # Delete files
            for path_key in ["file_path", "preview_path", "thumbnail_path"]:
                if attachment[path_key]:
                    try:
                        Path(attachment[path_key]).unlink(missing_ok=True)
                    except Exception as e:
                        logger.warning(f"Failed to delete file: {e}")

            # Delete from database
            conn.execute("DELETE FROM task_attachments WHERE id = ?", (attachment_id,))
            conn.commit()

            logger.info(f"Deleted attachment {attachment_id}")
            return True

    def get_file_path(self, attachment_id: int) -> Optional[Path]:
        """Get the file path for an attachment."""
        attachment = self.get_attachment(attachment_id)
        if attachment:
            return Path(attachment["file_path"])
        return None

    def get_preview_path(self, attachment_id: int) -> Optional[Path]:
        """Get the preview path for an attachment."""
        attachment = self.get_attachment(attachment_id)
        if attachment and attachment.get("preview_path"):
            return Path(attachment["preview_path"])
        return None

    def get_thumbnail_path(self, attachment_id: int) -> Optional[Path]:
        """Get the thumbnail path for an attachment."""
        attachment = self.get_attachment(attachment_id)
        if attachment and attachment.get("thumbnail_path"):
            return Path(attachment["thumbnail_path"])
        return None

    def add_comment(self, attachment_id: int, user_id: str, comment: str) -> Dict:
        """Add a comment to an attachment."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO attachment_comments (attachment_id, user_id, comment)
                VALUES (?, ?, ?)
            """,
                (attachment_id, user_id, comment),
            )
            conn.commit()

            comment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            result = conn.execute(
                "SELECT * FROM attachment_comments WHERE id = ?", (comment_id,)
            ).fetchone()
            return dict(result)

    def get_comments(self, attachment_id: int) -> List[Dict]:
        """Get comments for an attachment."""
        with self._get_connection() as conn:
            comments = conn.execute(
                """
                SELECT * FROM attachment_comments
                WHERE attachment_id = ?
                ORDER BY created_at ASC
            """,
                (attachment_id,),
            ).fetchall()
            return [dict(c) for c in comments]

    def get_stats(self, task_id: int = None, task_type: str = None) -> Dict:
        """Get attachment statistics."""
        with self._get_connection() as conn:
            if task_id and task_type:
                stats = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_count,
                        COALESCE(SUM(file_size), 0) as total_size,
                        COUNT(DISTINCT uploaded_by) as unique_uploaders
                    FROM task_attachments
                    WHERE task_id = ? AND task_type = ?
                """,
                    (task_id, task_type),
                ).fetchone()
            else:
                stats = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_count,
                        COALESCE(SUM(file_size), 0) as total_size,
                        COUNT(DISTINCT uploaded_by) as unique_uploaders,
                        COUNT(DISTINCT task_id || task_type) as tasks_with_attachments
                    FROM task_attachments
                """
                ).fetchone()

            result = dict(stats)
            result["total_size_mb"] = round(result["total_size"] / (1024 * 1024), 2)
            return result

    def search_attachments(
        self, query: str = None, task_type: str = None, mime_type: str = None, limit: int = 50
    ) -> List[Dict]:
        """Search attachments."""
        conditions = []
        params = []

        if query:
            conditions.append("(original_filename LIKE ? OR description LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        if task_type:
            conditions.append("task_type = ?")
            params.append(task_type)

        if mime_type:
            conditions.append("mime_type LIKE ?")
            params.append(f"{mime_type}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self._get_connection() as conn:
            attachments = conn.execute(
                f"""
                SELECT * FROM task_attachments
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
            """,
                params + [limit],
            ).fetchall()

            return [dict(a) for a in attachments]


# Singleton getter
_service_instance = None
_service_lock = threading.Lock()


def get_attachment_service(db_path: str = None, upload_dir: str = None) -> AttachmentService:
    global _service_instance
    if _service_instance is None or db_path:
        with _service_lock:
            if _service_instance is None or db_path:
                _service_instance = AttachmentService(db_path, upload_dir)
    return _service_instance
