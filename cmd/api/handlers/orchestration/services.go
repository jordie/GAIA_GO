package orchestration

import (
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jgirmay/GAIA_GO/internal/api/dtos"
	"github.com/jgirmay/GAIA_GO/internal/orchestration/services"
)

// ServiceHandler handles service coordinator HTTP requests
type ServiceHandler struct {
	coordinator *services.Coordinator
}

// NewServiceHandler creates a new service handler
func NewServiceHandler(coordinator *services.Coordinator) *ServiceHandler {
	return &ServiceHandler{
		coordinator: coordinator,
	}
}

// RegisterRoutes registers service routes
func (h *ServiceHandler) RegisterRoutes(router *gin.RouterGroup) {
	svc := router.Group("/services")
	{
		svc.POST("", h.RegisterService)
		svc.GET("", h.ListServices)
		svc.GET("/:serviceID", h.GetService)
		svc.DELETE("/:serviceID", h.UnregisterService)

		svc.POST("/:serviceID/start", h.StartService)
		svc.POST("/:serviceID/stop", h.StopService)
		svc.POST("/:serviceID/restart", h.RestartService)

		svc.GET("/:serviceID/health", h.HealthCheck)
		svc.GET("/:serviceID/logs", h.GetLogs)
		svc.GET("/:serviceID/metrics", h.GetMetrics)
	}
}

// RegisterService registers a new service
// @Summary Register service
// @Description Registers a new service for management
// @Tags Services
// @Accept json
// @Produce json
// @Param request body dtos.RegisterServiceRequest true "Service configuration"
// @Success 201 {object} dtos.ServiceResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/services [post]
func (h *ServiceHandler) RegisterService(c *gin.Context) {
	var req dtos.RegisterServiceRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "invalid_request",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	config := services.ServiceConfig{
		Name:        req.Name,
		Type:        req.Type,
		Command:     req.Command,
		Args:        req.Args,
		WorkDir:     req.WorkDir,
		Port:        req.Port,
		Environment: req.Environment,
		AutoRestart: req.AutoRestart,
		Metadata:    req.Metadata,
	}

	// Convert health check config
	if req.HealthCheck != nil {
		config.HealthCheck = &services.HealthCheckConfig{
			Type:       services.HealthCheckType(req.HealthCheck.Type),
			Endpoint:   req.HealthCheck.Endpoint,
			Port:       req.HealthCheck.Port,
			Command:    req.HealthCheck.Command,
			Retries:    req.HealthCheck.Retries,
		}

		// Parse interval and timeout
		if req.HealthCheck.Interval != "" {
			if d, err := time.ParseDuration(req.HealthCheck.Interval); err == nil {
				config.HealthCheck.Interval = d
			}
		}
		if req.HealthCheck.Timeout != "" {
			if d, err := time.ParseDuration(req.HealthCheck.Timeout); err == nil {
				config.HealthCheck.Timeout = d
			}
		}
		if req.HealthCheck.StartDelay != "" {
			if d, err := time.ParseDuration(req.HealthCheck.StartDelay); err == nil {
				config.HealthCheck.StartDelay = d
			}
		}
	}

	service, err := h.coordinator.RegisterService(config)
	if err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "service_registration_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusCreated, serviceToResponse(service))
}

// ListServices lists all registered services
// @Summary List services
// @Description Returns all registered services
// @Tags Services
// @Produce json
// @Success 200 {array} dtos.ServiceResponse
// @Router /api/orchestration/services [get]
func (h *ServiceHandler) ListServices(c *gin.Context) {
	services, err := h.coordinator.ListServices()
	if err != nil {
		c.JSON(http.StatusInternalServerError, dtos.ErrorResponse{
			Error:      "list_services_failed",
			Message:    err.Error(),
			StatusCode: http.StatusInternalServerError,
			Timestamp:  time.Now(),
		})
		return
	}

	var responses []*dtos.ServiceResponse
	for _, svc := range services {
		responses = append(responses, serviceToResponse(svc))
	}

	c.JSON(http.StatusOK, responses)
}

// GetService retrieves a specific service
// @Summary Get service
// @Description Retrieves details of a specific service
// @Tags Services
// @Produce json
// @Param serviceID path string true "Service ID"
// @Success 200 {object} dtos.ServiceResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/services/{serviceID} [get]
func (h *ServiceHandler) GetService(c *gin.Context) {
	serviceID := c.Param("serviceID")

	service, err := h.coordinator.GetService(serviceID)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "service_not_found",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	c.JSON(http.StatusOK, serviceToResponse(service))
}

// UnregisterService removes a service
// @Summary Unregister service
// @Description Removes a service from management
// @Tags Services
// @Param serviceID path string true "Service ID"
// @Success 204
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/services/{serviceID} [delete]
func (h *ServiceHandler) UnregisterService(c *gin.Context) {
	serviceID := c.Param("serviceID")

	if err := h.coordinator.UnregisterService(serviceID); err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "service_unregistration_failed",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	c.Status(http.StatusNoContent)
}

// StartService starts a service
// @Summary Start service
// @Description Starts a registered service
// @Tags Services
// @Param serviceID path string true "Service ID"
// @Success 200 {object} dtos.ServiceResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/services/{serviceID}/start [post]
func (h *ServiceHandler) StartService(c *gin.Context) {
	serviceID := c.Param("serviceID")

	if err := h.coordinator.StartService(c.Request.Context(), serviceID); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "service_start_failed",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	service, _ := h.coordinator.GetService(serviceID)
	c.JSON(http.StatusOK, serviceToResponse(service))
}

// StopService stops a running service
// @Summary Stop service
// @Description Stops a running service
// @Tags Services
// @Param serviceID path string true "Service ID"
// @Success 200 {object} dtos.ServiceResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/services/{serviceID}/stop [post]
func (h *ServiceHandler) StopService(c *gin.Context) {
	serviceID := c.Param("serviceID")
	graceful := c.DefaultQuery("graceful", "true") == "true"

	if err := h.coordinator.StopService(serviceID, graceful); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "service_stop_failed",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	service, _ := h.coordinator.GetService(serviceID)
	c.JSON(http.StatusOK, serviceToResponse(service))
}

// RestartService restarts a service
// @Summary Restart service
// @Description Restarts a service (stops then starts)
// @Tags Services
// @Param serviceID path string true "Service ID"
// @Success 200 {object} dtos.ServiceResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/services/{serviceID}/restart [post]
func (h *ServiceHandler) RestartService(c *gin.Context) {
	serviceID := c.Param("serviceID")

	if err := h.coordinator.RestartService(c.Request.Context(), serviceID); err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "service_restart_failed",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	service, _ := h.coordinator.GetService(serviceID)
	c.JSON(http.StatusOK, serviceToResponse(service))
}

// HealthCheck performs a health check on a service
// @Summary Health check
// @Description Checks the health status of a service
// @Tags Services
// @Produce json
// @Param serviceID path string true "Service ID"
// @Success 200 {object} dtos.ServiceHealthResponse
// @Failure 400 {object} dtos.ErrorResponse
// @Router /api/orchestration/services/{serviceID}/health [get]
func (h *ServiceHandler) HealthCheck(c *gin.Context) {
	serviceID := c.Param("serviceID")

	status, err := h.coordinator.HealthCheck(serviceID)
	if err != nil {
		c.JSON(http.StatusBadRequest, dtos.ErrorResponse{
			Error:      "health_check_failed",
			Message:    err.Error(),
			StatusCode: http.StatusBadRequest,
			Timestamp:  time.Now(),
		})
		return
	}

	response := &dtos.ServiceHealthResponse{
		ServiceID:      status.ServiceID,
		IsHealthy:      status.IsHealthy,
		LastCheckTime:  status.LastCheckTime,
		FailureCount:   status.FailureCount,
		LastError:      status.LastError,
		ResponseTimeMs: status.ResponseTime,
	}

	c.JSON(http.StatusOK, response)
}

// GetLogs retrieves service logs
// @Summary Get logs
// @Description Retrieves the logs from a service
// @Tags Services
// @Produce json
// @Param serviceID path string true "Service ID"
// @Param lines query int false "Number of lines to retrieve (default: 100)"
// @Success 200 {object} dtos.ServiceLogsResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/services/{serviceID}/logs [get]
func (h *ServiceHandler) GetLogs(c *gin.Context) {
	serviceID := c.Param("serviceID")

	lines := 100
	if linesStr := c.Query("lines"); linesStr != "" {
		if n, err := strconv.Atoi(linesStr); err == nil {
			lines = n
		}
	}

	logs, err := h.coordinator.GetLogs(serviceID, lines)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "logs_retrieval_failed",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	response := &dtos.ServiceLogsResponse{
		ServiceID: serviceID,
		Logs:      logs,
		Lines:     lines,
	}

	c.JSON(http.StatusOK, response)
}

// GetMetrics retrieves service metrics
// @Summary Get metrics
// @Description Retrieves performance metrics for a service
// @Tags Services
// @Produce json
// @Param serviceID path string true "Service ID"
// @Success 200 {object} dtos.ServiceMetricsResponse
// @Failure 404 {object} dtos.ErrorResponse
// @Router /api/orchestration/services/{serviceID}/metrics [get]
func (h *ServiceHandler) GetMetrics(c *gin.Context) {
	serviceID := c.Param("serviceID")

	metrics, err := h.coordinator.GetMetrics(serviceID)
	if err != nil {
		c.JSON(http.StatusNotFound, dtos.ErrorResponse{
			Error:      "metrics_retrieval_failed",
			Message:    err.Error(),
			StatusCode: http.StatusNotFound,
			Timestamp:  time.Now(),
		})
		return
	}

	response := &dtos.ServiceMetricsResponse{
		ServiceID:     metrics.ServiceID,
		CPUPercent:    metrics.CPUPercent,
		MemoryMB:      metrics.MemoryMB,
		PID:           metrics.PID,
		UptimeSeconds: metrics.Uptime,
		RestartCount:  metrics.RestartCount,
		SuccessCount:  metrics.SuccessCount,
		FailureCount:  metrics.FailureCount,
	}

	c.JSON(http.StatusOK, response)
}

// Helper functions

func serviceToResponse(service *services.Service) *dtos.ServiceResponse {
	return &dtos.ServiceResponse{
		ID:              service.ID,
		Name:            service.Name,
		Type:            service.Type,
		Command:         service.Command,
		Status:          string(service.Status),
		Port:            service.Port,
		ProcessID:       service.ProcessID,
		Restarts:        service.Restarts,
		HealthStatus:    service.HealthStatus,
		StartedAt:       service.StartedAt,
		StoppedAt:       service.StoppedAt,
		LastHealthCheck: service.LastHealthCheck,
		Error:           service.Error,
		CreatedAt:       service.CreatedAt,
	}
}
