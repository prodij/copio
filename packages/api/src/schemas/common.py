"""Common schema components."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Pagination(BaseModel):
    """Pagination info."""

    page: int
    page_size: int = Field(serialization_alias="pageSize")
    total: int
    total_pages: int = Field(serialization_alias="totalPages")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    data: list[T]
    pagination: Pagination
