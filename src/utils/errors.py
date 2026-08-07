class APIError(Exception):
    """Base exception class for all custom travel planner errors."""
    def __init__(self, message: str, status_code: int = 500, error_code: str = "INTERNAL_ERROR"):
        """Store the error message, HTTP status code, and machine-readable error code."""
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

class ValidationError(APIError):
    """Exception raised for invalid client inputs or query parameters."""
    def __init__(self, message: str):
        """Initialize with a 400 status code and VALIDATION_ERROR error code."""
        super().__init__(message, status_code=400, error_code="VALIDATION_ERROR")

class AuthenticationError(APIError):
    """Exception raised when credentials fail, are missing, or are expired."""
    def __init__(self, message: str = "Could not validate credentials"):
        """Initialize with a 401 status code and UNAUTHENTICATED error code."""
        super().__init__(message, status_code=401, error_code="UNAUTHENTICATED")

class AuthorizationError(APIError):
    """Exception raised when a user tries to access a resource they do not own (IDOR)."""
    def __init__(self, message: str = "Not authorized to access this resource"):
        """Initialize with a 403 status code and UNAUTHORIZED error code."""
        super().__init__(message, status_code=403, error_code="UNAUTHORIZED")

class NotFoundError(APIError):
    """Exception raised when a resource (e.g., User, Trip, Itinerary) cannot be found."""
    def __init__(self, message: str = "Requested resource not found"):
        """Initialize with a 404 status code and NOT_FOUND error code."""
        super().__init__(message, status_code=404, error_code="NOT_FOUND")

class ConflictError(APIError):
    """Exception raised when a state mismatch occurs (e.g. re-planning an in-progress trip)."""
    def __init__(self, message: str):
        """Initialize with a 409 status code and CONFLICT error code."""
        super().__init__(message, status_code=409, error_code="CONFLICT")

class AgentError(APIError):
    """Exception raised when a LangGraph node or LLM specialist agent fails."""
    def __init__(self, message: str):
        """Initialize with a 500 status code and AGENT_ERROR error code."""
        super().__init__(message, status_code=500, error_code="AGENT_ERROR")

class ExternalAPIError(APIError):
    """Exception raised when an external vendor API (Duffel, OSM, etc.) fails."""
    def __init__(self, message: str):
        """Initialize with a 502 status code and PROVIDER_ERROR error code."""
        super().__init__(message, status_code=502, error_code="PROVIDER_ERROR")
