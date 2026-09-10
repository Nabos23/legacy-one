"""Shared pagination helpers for list endpoints."""

from dataclasses import dataclass
from typing import Generic, List, TypeVar

from fastapi import Query
from pydantic import BaseModel

from backend.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

T = TypeVar("T")


@dataclass
class Pagination:
    """Resolved pagination parameters for a request."""

    page: int
    page_size: int

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def pagination_params(
    page: int = Query(DEFAULT_PAGE, ge=1, description="1-based page number"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"
    ),
) -> Pagination:
    """FastAPI dependency that supplies pagination parameters."""
    return Pagination(page=page, page_size=page_size)


class Page(BaseModel, Generic[T]):
    """A paginated list response."""

    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


def build_page(items: List[T], total: int, pg: Pagination) -> Page[T]:
    """Assemble a Page envelope from items + total count."""
    total_pages = (total + pg.page_size - 1) // pg.page_size if total else 0
    return Page(
        items=items,
        total=total,
        page=pg.page,
        page_size=pg.page_size,
        total_pages=total_pages,
    )
