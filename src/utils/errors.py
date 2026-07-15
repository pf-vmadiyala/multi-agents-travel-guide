class APIError(Exception):
    """Base exception class for all custom travel planner errors."""
    def __init__(self, message: str, status_code: int = 500, error_code: str = "INTERNAL_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

class ValidationError(APIError):
    """Exception raised for invalid client inputs or query parameters."""
    def __init__(self, message: str):
        super().__init__(message, status_code=400, error_code="VALIDATION_ERROR")

class AuthenticationError(APIError):
    """Exception raised when credentials fail, are missing, or are expired."""
    def __init__(self, message: str = "Could not validate credentials"):
        super().__init__(message, status_code=401, error_code="UNAUTHENTICATED")

class AuthorizationError(APIError):
    """Exception raised when a user tries to access a resource they do not own (IDOR)."""
    def __init__(self, message: str = "Not authorized to access this resource"):
        super().__init__(message, status_code=403, error_code="UNAUTHORIZED")

class NotFoundError(APIError):
    """Exception raised when a resource (e.g., User, Trip, Itinerary) cannot be found."""
    def __init__(self, message: str = "Requested resource not found"):
        super().__init__(message, status_code=404, error_code="NOT_FOUND")

class ConflictError(APIError):
    """Exception raised when a state mismatch occurs (e.g. re-planning an in-progress trip)."""
    def __init__(self, message: str):
        super().__init__(message, status_code=409, error_code="CONFLICT")

class AgentError(APIError):
    """Exception raised when a LangGraph node or LLM specialist agent fails."""
    def __init__(self, message: str):
        super().__init__(message, status_code=500, error_code="AGENT_ERROR")

class ExternalAPIError(APIError):
    """Exception raised when an external vendor API (Duffel, OSM, etc.) fails."""
    def __init__(self, message: str):
        super().__init__(message, status_code=502, error_code="PROVIDER_ERROR")
