"""Common schema components."""

from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    
    data: list[T]
    pagination: "Pagination"


class Pagination(BaseModel):
    """Pagination info."""
    
    page: int
    page_size: int
    total: int
    total_pages: int
    
    model_config = {"from_attributes": True}
