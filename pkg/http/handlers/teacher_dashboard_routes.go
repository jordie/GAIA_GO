package handlers

import (
	"github.com/go-chi/chi/v5"

	"github.com/jgirmay/GAIA_GO/pkg/repository"
	"github.com/jgirmay/GAIA_GO/pkg/services/usability"
)

// RegisterTeacherDashboardRoutes registers all teacher dashboard routes
func RegisterTeacherDashboardRoutes(
	router *chi.Mux,
	metricsService *usability.UsabilityMetricsService,
	frustrationEngine *usability.FrustrationDetectionEngine,
	aggregator *usability.RealtimeMetricsAggregator,
	alertRepository repository.TeacherDashboardAlertRepository,
) {
	handlers := NewTeacherDashboardHandlers(
		metricsService,
		frustrationEngine,
		aggregator,
		alertRepository,
	)

	// Define routes under /api/dashboard prefix
	router.Route("/api/dashboard", func(r chi.Router) {
		// Classroom metrics
		r.Get("/classroom/{classroomID}/metrics", handlers.GetClassroomMetrics)

		// Student frustration metrics
		r.Get("/student/frustration", handlers.GetStudentFrustration)

		// Struggling students in classroom
		r.Get("/struggling-students", handlers.GetStrugglingSuppStudents)

		// Record intervention
		r.Post("/interventions", handlers.RecordIntervention)

		// Health check
		r.Get("/health", handlers.GetHealthStatus)
	})

	// Alternative routes under /api prefix (more RESTful)
	router.Route("/api", func(r chi.Router) {
		// Classroom routes
		r.Route("/classrooms/{classroomID}", func(r chi.Router) {
			r.Get("/metrics", handlers.GetClassroomMetrics)
			r.Get("/struggling-students", handlers.GetStrugglingSuppStudents)
		})

		// Student routes
		r.Route("/students/{studentID}", func(r chi.Router) {
			r.Get("/frustration", handlers.GetStudentFrustration)
		})

		// Intervention routes
		r.Route("/interventions", func(r chi.Router) {
			r.Post("/", handlers.RecordIntervention)
		})
	})
}
