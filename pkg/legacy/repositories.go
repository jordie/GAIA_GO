package legacy

import (
	"context"

	"github.com/jgirmay/GAIA_GO/pkg/models"
)

// ClaudeSessionRepository interface for legacy API operations on ClaudeSession
type ClaudeSessionRepository interface {
	GetAll(ctx context.Context) ([]models.ClaudeSession, error)
	GetByID(ctx context.Context, id string) (*models.ClaudeSession, error)
	Create(ctx context.Context, session *models.ClaudeSession) (*models.ClaudeSession, error)
	Update(ctx context.Context, session *models.ClaudeSession) (*models.ClaudeSession, error)
	Delete(ctx context.Context, id string) error
}

// LessonRepository interface for legacy API operations on Lesson
type LessonRepository interface {
	GetAll(ctx context.Context) ([]models.Lesson, error)
	GetByID(ctx context.Context, id string) (*models.Lesson, error)
	Create(ctx context.Context, lesson *models.Lesson) (*models.Lesson, error)
	Update(ctx context.Context, lesson *models.Lesson) (*models.Lesson, error)
	Delete(ctx context.Context, id string) error
}
