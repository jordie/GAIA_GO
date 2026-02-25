"""
Curriculum Management Service for Basic Edu Apps.

Provides admin interface for managing educational curriculum including:
- Subjects (Math, Reading, Typing, Piano)
- Courses within subjects
- Lessons within courses
- Learning paths (sequences of courses)
- Progress tracking configuration
"""
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SubjectType(Enum):
    MATH = "math"
    READING = "reading"
    TYPING = "typing"
    PIANO = "piano"


class DifficultyLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class ContentType(Enum):
    VIDEO = "video"
    INTERACTIVE = "interactive"
    QUIZ = "quiz"
    PRACTICE = "practice"
    GAME = "game"
    READING = "reading"


class LessonStatus(Enum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass
class Subject:
    id: Optional[int]
    name: str
    subject_type: str
    description: str
    icon: str
    color: str
    display_order: int
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Course:
    id: Optional[int]
    subject_id: int
    name: str
    description: str
    difficulty: str
    estimated_hours: float
    prerequisites: str  # JSON list of course IDs
    learning_objectives: str  # JSON list
    display_order: int
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Lesson:
    id: Optional[int]
    course_id: int
    name: str
    description: str
    content_type: str
    content_data: str  # JSON with lesson content
    duration_minutes: int
    points: int
    display_order: int
    status: str = "draft"
    prerequisites: str = "[]"  # JSON list of lesson IDs
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    published_at: Optional[str] = None


@dataclass
class LearningPath:
    id: Optional[int]
    name: str
    description: str
    target_audience: str
    estimated_weeks: int
    courses: str  # JSON list of course IDs in order
    is_featured: bool = False
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# SQL Schema for curriculum tables
CURRICULUM_SCHEMA = """
-- Subjects (Math, Reading, Typing, Piano)
CREATE TABLE IF NOT EXISTS curriculum_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    subject_type TEXT NOT NULL,
    description TEXT,
    icon TEXT DEFAULT 'book',
    color TEXT DEFAULT '#3498db',
    display_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_curriculum_subjects_type ON curriculum_subjects(subject_type);
CREATE INDEX IF NOT EXISTS idx_curriculum_subjects_active ON curriculum_subjects(is_active);

-- Courses within subjects
CREATE TABLE IF NOT EXISTS curriculum_courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    difficulty TEXT DEFAULT 'beginner',
    estimated_hours REAL DEFAULT 1.0,
    prerequisites TEXT DEFAULT '[]',
    learning_objectives TEXT DEFAULT '[]',
    display_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES curriculum_subjects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_curriculum_courses_subject ON curriculum_courses(subject_id);
CREATE INDEX IF NOT EXISTS idx_curriculum_courses_difficulty ON curriculum_courses(difficulty);
CREATE INDEX IF NOT EXISTS idx_curriculum_courses_active ON curriculum_courses(is_active);

-- Lessons within courses
CREATE TABLE IF NOT EXISTS curriculum_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    content_type TEXT DEFAULT 'interactive',
    content_data TEXT DEFAULT '{}',
    duration_minutes INTEGER DEFAULT 15,
    points INTEGER DEFAULT 10,
    display_order INTEGER DEFAULT 0,
    status TEXT DEFAULT 'draft',
    prerequisites TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES curriculum_courses(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_curriculum_lessons_course ON curriculum_lessons(course_id);
CREATE INDEX IF NOT EXISTS idx_curriculum_lessons_status ON curriculum_lessons(status);
CREATE INDEX IF NOT EXISTS idx_curriculum_lessons_type ON curriculum_lessons(content_type);

-- Learning paths (curated sequences of courses)
CREATE TABLE IF NOT EXISTS curriculum_learning_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    target_audience TEXT,
    estimated_weeks INTEGER DEFAULT 4,
    courses TEXT DEFAULT '[]',
    is_featured INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_curriculum_paths_featured ON curriculum_learning_paths(is_featured);
CREATE INDEX IF NOT EXISTS idx_curriculum_paths_active ON curriculum_learning_paths(is_active);

-- Lesson resources (attachments, media)
CREATE TABLE IF NOT EXISTS curriculum_lesson_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id INTEGER NOT NULL,
    resource_type TEXT NOT NULL,
    name TEXT NOT NULL,
    url TEXT,
    file_path TEXT,
    metadata TEXT DEFAULT '{}',
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lesson_id) REFERENCES curriculum_lessons(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_curriculum_resources_lesson ON curriculum_lesson_resources(lesson_id);

-- Quiz questions for lessons
CREATE TABLE IF NOT EXISTS curriculum_quiz_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id INTEGER NOT NULL,
    question_type TEXT DEFAULT 'multiple_choice',
    question_text TEXT NOT NULL,
    options TEXT DEFAULT '[]',
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    points INTEGER DEFAULT 1,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lesson_id) REFERENCES curriculum_lessons(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_curriculum_questions_lesson ON curriculum_quiz_questions(lesson_id);

-- Curriculum version history for audit
CREATE TABLE IF NOT EXISTS curriculum_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    old_data TEXT,
    new_data TEXT,
    changed_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_curriculum_history_entity ON curriculum_history(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_curriculum_history_date ON curriculum_history(created_at);

-- Curriculum settings
CREATE TABLE IF NOT EXISTS curriculum_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT NOT NULL UNIQUE,
    setting_value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_curriculum_schema(conn: sqlite3.Connection) -> None:
    """Initialize curriculum tables in the database."""
    conn.executescript(CURRICULUM_SCHEMA)
    conn.commit()

    # Insert default subjects if not exist
    default_subjects = [
        (
            "Math",
            "math",
            "Learn mathematics from basic arithmetic to advanced concepts",
            "calculator",
            "#e74c3c",
            1,
        ),
        (
            "Reading",
            "reading",
            "Improve reading comprehension and vocabulary",
            "book-open",
            "#27ae60",
            2,
        ),
        (
            "Typing",
            "typing",
            "Master touch typing with keyboard exercises",
            "keyboard",
            "#3498db",
            3,
        ),
        (
            "Piano",
            "piano",
            "Learn piano with interactive lessons and practice",
            "music",
            "#9b59b6",
            4,
        ),
    ]

    for name, stype, desc, icon, color, order in default_subjects:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO curriculum_subjects
                (name, subject_type, description, icon, color, display_order)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (name, stype, desc, icon, color, order),
            )
        except sqlite3.IntegrityError:
            pass

    # Insert default settings
    default_settings = [
        ("points_per_lesson", "10", "Default points awarded per lesson completion"),
        ("min_pass_score", "70", "Minimum percentage to pass a quiz"),
        ("max_attempts", "3", "Maximum quiz attempts before lockout"),
        ("review_required", "true", "Require admin review before publishing"),
    ]

    for key, value, desc in default_settings:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO curriculum_settings
                (setting_key, setting_value, description)
                VALUES (?, ?, ?)
            """,
                (key, value, desc),
            )
        except sqlite3.IntegrityError:
            pass

    conn.commit()


class CurriculumService:
    """Service for managing curriculum data."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    # ==================== SUBJECTS ====================

    def get_subjects(self, include_inactive: bool = False) -> List[Dict]:
        """Get all subjects."""
        query = "SELECT * FROM curriculum_subjects"
        if not include_inactive:
            query += " WHERE is_active = 1"
        query += " ORDER BY display_order, name"

        rows = self.conn.execute(query).fetchall()
        subjects = []
        for row in rows:
            subject = dict(row)
            # Get course count
            count = self.conn.execute(
                "SELECT COUNT(*) FROM curriculum_courses WHERE subject_id = ?", (row["id"],)
            ).fetchone()[0]
            subject["course_count"] = count
            subjects.append(subject)
        return subjects

    def get_subject(self, subject_id: int) -> Optional[Dict]:
        """Get a single subject by ID."""
        row = self.conn.execute(
            "SELECT * FROM curriculum_subjects WHERE id = ?", (subject_id,)
        ).fetchone()
        return dict(row) if row else None

    def create_subject(self, data: Dict, created_by: str = None) -> int:
        """Create a new subject."""
        cursor = self.conn.execute(
            """
            INSERT INTO curriculum_subjects
            (name, subject_type, description, icon, color, display_order, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["name"],
                data.get("subject_type", "custom"),
                data.get("description", ""),
                data.get("icon", "book"),
                data.get("color", "#3498db"),
                data.get("display_order", 0),
                1 if data.get("is_active", True) else 0,
            ),
        )
        self.conn.commit()

        subject_id = cursor.lastrowid
        self._log_history("subject", subject_id, "create", None, data, created_by)
        return subject_id

    def update_subject(self, subject_id: int, data: Dict, updated_by: str = None) -> bool:
        """Update a subject."""
        old_data = self.get_subject(subject_id)
        if not old_data:
            return False

        self.conn.execute(
            """
            UPDATE curriculum_subjects SET
                name = COALESCE(?, name),
                subject_type = COALESCE(?, subject_type),
                description = COALESCE(?, description),
                icon = COALESCE(?, icon),
                color = COALESCE(?, color),
                display_order = COALESCE(?, display_order),
                is_active = COALESCE(?, is_active),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (
                data.get("name"),
                data.get("subject_type"),
                data.get("description"),
                data.get("icon"),
                data.get("color"),
                data.get("display_order"),
                1 if data.get("is_active") else (0 if data.get("is_active") is False else None),
                subject_id,
            ),
        )
        self.conn.commit()

        self._log_history("subject", subject_id, "update", old_data, data, updated_by)
        return True

    def delete_subject(self, subject_id: int, deleted_by: str = None) -> bool:
        """Delete a subject (cascades to courses and lessons)."""
        old_data = self.get_subject(subject_id)
        if not old_data:
            return False

        self.conn.execute("DELETE FROM curriculum_subjects WHERE id = ?", (subject_id,))
        self.conn.commit()

        self._log_history("subject", subject_id, "delete", old_data, None, deleted_by)
        return True

    # ==================== COURSES ====================

    def get_courses(self, subject_id: int = None, include_inactive: bool = False) -> List[Dict]:
        """Get courses, optionally filtered by subject."""
        query = """
            SELECT c.*, s.name as subject_name
            FROM curriculum_courses c
            JOIN curriculum_subjects s ON c.subject_id = s.id
            WHERE 1=1
        """
        params = []

        if subject_id:
            query += " AND c.subject_id = ?"
            params.append(subject_id)
        if not include_inactive:
            query += " AND c.is_active = 1"

        query += " ORDER BY c.display_order, c.name"

        rows = self.conn.execute(query, params).fetchall()
        courses = []
        for row in rows:
            course = dict(row)
            # Get lesson count
            count = self.conn.execute(
                "SELECT COUNT(*) FROM curriculum_lessons WHERE course_id = ?", (row["id"],)
            ).fetchone()[0]
            course["lesson_count"] = count
            course["prerequisites"] = json.loads(course.get("prerequisites") or "[]")
            course["learning_objectives"] = json.loads(course.get("learning_objectives") or "[]")
            courses.append(course)
        return courses

    def get_course(self, course_id: int) -> Optional[Dict]:
        """Get a single course by ID."""
        row = self.conn.execute(
            """
            SELECT c.*, s.name as subject_name
            FROM curriculum_courses c
            JOIN curriculum_subjects s ON c.subject_id = s.id
            WHERE c.id = ?
        """,
            (course_id,),
        ).fetchone()

        if row:
            course = dict(row)
            course["prerequisites"] = json.loads(course.get("prerequisites") or "[]")
            course["learning_objectives"] = json.loads(course.get("learning_objectives") or "[]")
            return course
        return None

    def create_course(self, data: Dict, created_by: str = None) -> int:
        """Create a new course."""
        cursor = self.conn.execute(
            """
            INSERT INTO curriculum_courses
            (subject_id, name, description, difficulty, estimated_hours,
             prerequisites, learning_objectives, display_order, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["subject_id"],
                data["name"],
                data.get("description", ""),
                data.get("difficulty", "beginner"),
                data.get("estimated_hours", 1.0),
                json.dumps(data.get("prerequisites", [])),
                json.dumps(data.get("learning_objectives", [])),
                data.get("display_order", 0),
                1 if data.get("is_active", True) else 0,
            ),
        )
        self.conn.commit()

        course_id = cursor.lastrowid
        self._log_history("course", course_id, "create", None, data, created_by)
        return course_id

    def update_course(self, course_id: int, data: Dict, updated_by: str = None) -> bool:
        """Update a course."""
        old_data = self.get_course(course_id)
        if not old_data:
            return False

        # Handle JSON fields
        prerequisites = json.dumps(data["prerequisites"]) if "prerequisites" in data else None
        learning_objectives = (
            json.dumps(data["learning_objectives"]) if "learning_objectives" in data else None
        )

        self.conn.execute(
            """
            UPDATE curriculum_courses SET
                subject_id = COALESCE(?, subject_id),
                name = COALESCE(?, name),
                description = COALESCE(?, description),
                difficulty = COALESCE(?, difficulty),
                estimated_hours = COALESCE(?, estimated_hours),
                prerequisites = COALESCE(?, prerequisites),
                learning_objectives = COALESCE(?, learning_objectives),
                display_order = COALESCE(?, display_order),
                is_active = COALESCE(?, is_active),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (
                data.get("subject_id"),
                data.get("name"),
                data.get("description"),
                data.get("difficulty"),
                data.get("estimated_hours"),
                prerequisites,
                learning_objectives,
                data.get("display_order"),
                1 if data.get("is_active") else (0 if data.get("is_active") is False else None),
                course_id,
            ),
        )
        self.conn.commit()

        self._log_history("course", course_id, "update", old_data, data, updated_by)
        return True

    def delete_course(self, course_id: int, deleted_by: str = None) -> bool:
        """Delete a course (cascades to lessons)."""
        old_data = self.get_course(course_id)
        if not old_data:
            return False

        self.conn.execute("DELETE FROM curriculum_courses WHERE id = ?", (course_id,))
        self.conn.commit()

        self._log_history("course", course_id, "delete", old_data, None, deleted_by)
        return True

    # ==================== LESSONS ====================

    def get_lessons(self, course_id: int = None, status: str = None) -> List[Dict]:
        """Get lessons, optionally filtered by course or status."""
        query = """
            SELECT l.*, c.name as course_name, s.name as subject_name
            FROM curriculum_lessons l
            JOIN curriculum_courses c ON l.course_id = c.id
            JOIN curriculum_subjects s ON c.subject_id = s.id
            WHERE 1=1
        """
        params = []

        if course_id:
            query += " AND l.course_id = ?"
            params.append(course_id)
        if status:
            query += " AND l.status = ?"
            params.append(status)

        query += " ORDER BY l.display_order, l.name"

        rows = self.conn.execute(query, params).fetchall()
        lessons = []
        for row in rows:
            lesson = dict(row)
            lesson["content_data"] = json.loads(lesson.get("content_data") or "{}")
            lesson["prerequisites"] = json.loads(lesson.get("prerequisites") or "[]")
            lessons.append(lesson)
        return lessons

    def get_lesson(self, lesson_id: int) -> Optional[Dict]:
        """Get a single lesson by ID."""
        row = self.conn.execute(
            """
            SELECT l.*, c.name as course_name, s.name as subject_name
            FROM curriculum_lessons l
            JOIN curriculum_courses c ON l.course_id = c.id
            JOIN curriculum_subjects s ON c.subject_id = s.id
            WHERE l.id = ?
        """,
            (lesson_id,),
        ).fetchone()

        if row:
            lesson = dict(row)
            lesson["content_data"] = json.loads(lesson.get("content_data") or "{}")
            lesson["prerequisites"] = json.loads(lesson.get("prerequisites") or "[]")

            # Get resources
            resources = self.conn.execute(
                "SELECT * FROM curriculum_lesson_resources WHERE lesson_id = ? ORDER BY display_order",
                (lesson_id,),
            ).fetchall()
            lesson["resources"] = [dict(r) for r in resources]

            # Get quiz questions if applicable
            if lesson["content_type"] == "quiz":
                questions = self.conn.execute(
                    "SELECT * FROM curriculum_quiz_questions WHERE lesson_id = ? ORDER BY display_order",
                    (lesson_id,),
                ).fetchall()
                lesson["questions"] = [dict(q) for q in questions]

            return lesson
        return None

    def create_lesson(self, data: Dict, created_by: str = None) -> int:
        """Create a new lesson."""
        cursor = self.conn.execute(
            """
            INSERT INTO curriculum_lessons
            (course_id, name, description, content_type, content_data,
             duration_minutes, points, display_order, status, prerequisites)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["course_id"],
                data["name"],
                data.get("description", ""),
                data.get("content_type", "interactive"),
                json.dumps(data.get("content_data", {})),
                data.get("duration_minutes", 15),
                data.get("points", 10),
                data.get("display_order", 0),
                data.get("status", "draft"),
                json.dumps(data.get("prerequisites", [])),
            ),
        )
        self.conn.commit()

        lesson_id = cursor.lastrowid
        self._log_history("lesson", lesson_id, "create", None, data, created_by)
        return lesson_id

    def update_lesson(self, lesson_id: int, data: Dict, updated_by: str = None) -> bool:
        """Update a lesson."""
        old_data = self.get_lesson(lesson_id)
        if not old_data:
            return False

        # Handle JSON fields
        content_data = json.dumps(data["content_data"]) if "content_data" in data else None
        prerequisites = json.dumps(data["prerequisites"]) if "prerequisites" in data else None

        # Check if publishing
        published_at = None
        if data.get("status") == "published" and old_data.get("status") != "published":
            published_at = datetime.now().isoformat()

        self.conn.execute(
            """
            UPDATE curriculum_lessons SET
                course_id = COALESCE(?, course_id),
                name = COALESCE(?, name),
                description = COALESCE(?, description),
                content_type = COALESCE(?, content_type),
                content_data = COALESCE(?, content_data),
                duration_minutes = COALESCE(?, duration_minutes),
                points = COALESCE(?, points),
                display_order = COALESCE(?, display_order),
                status = COALESCE(?, status),
                prerequisites = COALESCE(?, prerequisites),
                published_at = COALESCE(?, published_at),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (
                data.get("course_id"),
                data.get("name"),
                data.get("description"),
                data.get("content_type"),
                content_data,
                data.get("duration_minutes"),
                data.get("points"),
                data.get("display_order"),
                data.get("status"),
                prerequisites,
                published_at,
                lesson_id,
            ),
        )
        self.conn.commit()

        self._log_history("lesson", lesson_id, "update", old_data, data, updated_by)
        return True

    def delete_lesson(self, lesson_id: int, deleted_by: str = None) -> bool:
        """Delete a lesson."""
        old_data = self.get_lesson(lesson_id)
        if not old_data:
            return False

        self.conn.execute("DELETE FROM curriculum_lessons WHERE id = ?", (lesson_id,))
        self.conn.commit()

        self._log_history("lesson", lesson_id, "delete", old_data, None, deleted_by)
        return True

    def publish_lesson(self, lesson_id: int, published_by: str = None) -> bool:
        """Publish a lesson."""
        return self.update_lesson(lesson_id, {"status": "published"}, published_by)

    # ==================== LEARNING PATHS ====================

    def get_learning_paths(
        self, featured_only: bool = False, include_inactive: bool = False
    ) -> List[Dict]:
        """Get learning paths."""
        query = "SELECT * FROM curriculum_learning_paths WHERE 1=1"
        params = []

        if featured_only:
            query += " AND is_featured = 1"
        if not include_inactive:
            query += " AND is_active = 1"

        query += " ORDER BY is_featured DESC, name"

        rows = self.conn.execute(query, params).fetchall()
        paths = []
        for row in rows:
            path = dict(row)
            path["courses"] = json.loads(path.get("courses") or "[]")
            # Get course details
            if path["courses"]:
                placeholders = ",".join("?" * len(path["courses"]))
                course_rows = self.conn.execute(
                    f"""
                    SELECT id, name, difficulty, estimated_hours
                    FROM curriculum_courses
                    WHERE id IN ({placeholders})
                """,
                    path["courses"],
                ).fetchall()
                path["course_details"] = [dict(c) for c in course_rows]
            else:
                path["course_details"] = []
            paths.append(path)
        return paths

    def get_learning_path(self, path_id: int) -> Optional[Dict]:
        """Get a single learning path by ID."""
        row = self.conn.execute(
            "SELECT * FROM curriculum_learning_paths WHERE id = ?", (path_id,)
        ).fetchone()

        if row:
            path = dict(row)
            path["courses"] = json.loads(path.get("courses") or "[]")
            return path
        return None

    def create_learning_path(self, data: Dict, created_by: str = None) -> int:
        """Create a new learning path."""
        cursor = self.conn.execute(
            """
            INSERT INTO curriculum_learning_paths
            (name, description, target_audience, estimated_weeks, courses, is_featured, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["name"],
                data.get("description", ""),
                data.get("target_audience", ""),
                data.get("estimated_weeks", 4),
                json.dumps(data.get("courses", [])),
                1 if data.get("is_featured", False) else 0,
                1 if data.get("is_active", True) else 0,
            ),
        )
        self.conn.commit()

        path_id = cursor.lastrowid
        self._log_history("learning_path", path_id, "create", None, data, created_by)
        return path_id

    def update_learning_path(self, path_id: int, data: Dict, updated_by: str = None) -> bool:
        """Update a learning path."""
        old_data = self.get_learning_path(path_id)
        if not old_data:
            return False

        courses = json.dumps(data["courses"]) if "courses" in data else None

        self.conn.execute(
            """
            UPDATE curriculum_learning_paths SET
                name = COALESCE(?, name),
                description = COALESCE(?, description),
                target_audience = COALESCE(?, target_audience),
                estimated_weeks = COALESCE(?, estimated_weeks),
                courses = COALESCE(?, courses),
                is_featured = COALESCE(?, is_featured),
                is_active = COALESCE(?, is_active),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (
                data.get("name"),
                data.get("description"),
                data.get("target_audience"),
                data.get("estimated_weeks"),
                courses,
                1 if data.get("is_featured") else (0 if data.get("is_featured") is False else None),
                1 if data.get("is_active") else (0 if data.get("is_active") is False else None),
                path_id,
            ),
        )
        self.conn.commit()

        self._log_history("learning_path", path_id, "update", old_data, data, updated_by)
        return True

    def delete_learning_path(self, path_id: int, deleted_by: str = None) -> bool:
        """Delete a learning path."""
        old_data = self.get_learning_path(path_id)
        if not old_data:
            return False

        self.conn.execute("DELETE FROM curriculum_learning_paths WHERE id = ?", (path_id,))
        self.conn.commit()

        self._log_history("learning_path", path_id, "delete", old_data, None, deleted_by)
        return True

    # ==================== QUIZ QUESTIONS ====================

    def add_quiz_question(self, lesson_id: int, data: Dict) -> int:
        """Add a quiz question to a lesson."""
        cursor = self.conn.execute(
            """
            INSERT INTO curriculum_quiz_questions
            (lesson_id, question_type, question_text, options, correct_answer, explanation, points, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                lesson_id,
                data.get("question_type", "multiple_choice"),
                data["question_text"],
                json.dumps(data.get("options", [])),
                data["correct_answer"],
                data.get("explanation", ""),
                data.get("points", 1),
                data.get("display_order", 0),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_quiz_question(self, question_id: int, data: Dict) -> bool:
        """Update a quiz question."""
        options = json.dumps(data["options"]) if "options" in data else None

        result = self.conn.execute(
            """
            UPDATE curriculum_quiz_questions SET
                question_type = COALESCE(?, question_type),
                question_text = COALESCE(?, question_text),
                options = COALESCE(?, options),
                correct_answer = COALESCE(?, correct_answer),
                explanation = COALESCE(?, explanation),
                points = COALESCE(?, points),
                display_order = COALESCE(?, display_order)
            WHERE id = ?
        """,
            (
                data.get("question_type"),
                data.get("question_text"),
                options,
                data.get("correct_answer"),
                data.get("explanation"),
                data.get("points"),
                data.get("display_order"),
                question_id,
            ),
        )
        self.conn.commit()
        return result.rowcount > 0

    def delete_quiz_question(self, question_id: int) -> bool:
        """Delete a quiz question."""
        result = self.conn.execute(
            "DELETE FROM curriculum_quiz_questions WHERE id = ?", (question_id,)
        )
        self.conn.commit()
        return result.rowcount > 0

    # ==================== RESOURCES ====================

    def add_lesson_resource(self, lesson_id: int, data: Dict) -> int:
        """Add a resource to a lesson."""
        cursor = self.conn.execute(
            """
            INSERT INTO curriculum_lesson_resources
            (lesson_id, resource_type, name, url, file_path, metadata, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                lesson_id,
                data["resource_type"],
                data["name"],
                data.get("url"),
                data.get("file_path"),
                json.dumps(data.get("metadata", {})),
                data.get("display_order", 0),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def delete_lesson_resource(self, resource_id: int) -> bool:
        """Delete a lesson resource."""
        result = self.conn.execute(
            "DELETE FROM curriculum_lesson_resources WHERE id = ?", (resource_id,)
        )
        self.conn.commit()
        return result.rowcount > 0

    # ==================== SETTINGS ====================

    def get_settings(self) -> Dict[str, str]:
        """Get all curriculum settings."""
        rows = self.conn.execute("SELECT * FROM curriculum_settings").fetchall()
        return {row["setting_key"]: row["setting_value"] for row in rows}

    def update_setting(self, key: str, value: str) -> bool:
        """Update a curriculum setting."""
        result = self.conn.execute(
            """
            UPDATE curriculum_settings SET
                setting_value = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE setting_key = ?
        """,
            (value, key),
        )
        self.conn.commit()
        return result.rowcount > 0

    # ==================== STATISTICS ====================

    def get_statistics(self) -> Dict:
        """Get curriculum statistics."""
        stats = {}

        # Subject count
        stats["subjects"] = self.conn.execute(
            "SELECT COUNT(*) FROM curriculum_subjects WHERE is_active = 1"
        ).fetchone()[0]

        # Course count by difficulty
        course_stats = self.conn.execute(
            """
            SELECT difficulty, COUNT(*) as count
            FROM curriculum_courses WHERE is_active = 1
            GROUP BY difficulty
        """
        ).fetchall()
        stats["courses"] = {
            "total": sum(r["count"] for r in course_stats),
            "by_difficulty": {r["difficulty"]: r["count"] for r in course_stats},
        }

        # Lesson count by status
        lesson_stats = self.conn.execute(
            """
            SELECT status, COUNT(*) as count
            FROM curriculum_lessons
            GROUP BY status
        """
        ).fetchall()
        stats["lessons"] = {
            "total": sum(r["count"] for r in lesson_stats),
            "by_status": {r["status"]: r["count"] for r in lesson_stats},
        }

        # Learning paths
        stats["learning_paths"] = self.conn.execute(
            "SELECT COUNT(*) FROM curriculum_learning_paths WHERE is_active = 1"
        ).fetchone()[0]

        # Total hours of content
        stats["total_hours"] = (
            self.conn.execute(
                "SELECT SUM(estimated_hours) FROM curriculum_courses WHERE is_active = 1"
            ).fetchone()[0]
            or 0
        )

        # Total lesson duration
        stats["total_lesson_minutes"] = (
            self.conn.execute(
                "SELECT SUM(duration_minutes) FROM curriculum_lessons WHERE status = 'published'"
            ).fetchone()[0]
            or 0
        )

        return stats

    def get_history(
        self, entity_type: str = None, entity_id: int = None, limit: int = 50
    ) -> List[Dict]:
        """Get curriculum change history."""
        query = "SELECT * FROM curriculum_history WHERE 1=1"
        params = []

        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        history = []
        for row in rows:
            entry = dict(row)
            entry["old_data"] = json.loads(entry["old_data"]) if entry["old_data"] else None
            entry["new_data"] = json.loads(entry["new_data"]) if entry["new_data"] else None
            history.append(entry)
        return history

    # ==================== HELPERS ====================

    def _log_history(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        old_data: Optional[Dict],
        new_data: Optional[Dict],
        changed_by: str = None,
    ):
        """Log a change to the curriculum history."""
        self.conn.execute(
            """
            INSERT INTO curriculum_history
            (entity_type, entity_id, action, old_data, new_data, changed_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                entity_type,
                entity_id,
                action,
                json.dumps(old_data) if old_data else None,
                json.dumps(new_data) if new_data else None,
                changed_by,
            ),
        )
        self.conn.commit()

    def reorder_items(self, table: str, items: List[Dict[str, int]]) -> bool:
        """Reorder items by updating display_order."""
        valid_tables = ["curriculum_subjects", "curriculum_courses", "curriculum_lessons"]
        if table not in valid_tables:
            return False

        for item in items:
            self.conn.execute(
                f"UPDATE {table} SET display_order = ? WHERE id = ?", (item["order"], item["id"])
            )
        self.conn.commit()
        return True
