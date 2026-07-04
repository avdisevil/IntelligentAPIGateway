from pydantic import BaseModel

class APIKeyMetadata(BaseModel):
    """
    Metadata associated with an API key.
    """
    plan_name: str
    default_qps: int
    burst_capacity: int
    hard_max_qps: int
