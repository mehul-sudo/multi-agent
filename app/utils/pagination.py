"""
Pagination utility helper for standard API responses.

Provides standard pagination metadata calculations and dictionary formatting:
  - items
  - page
  - page_size
  - total
  - total_pages
  - has_next
  - has_previous
"""

import math


def paginate_query(query, page: int = 1, page_size: int = 20, max_page_size: int = 100):
    """Paginate a SQLAlchemy query cleanly.

    Args:
        query: SQLAlchemy query object.
        page: Requested page number (1-indexed).
        page_size: Requested page size.
        max_page_size: Hard cap for maximum page size.

    Returns:
        dict containing pagination data with raw item entities.
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    page_size = min(page_size, max_page_size)

    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1 and total_pages > 0,
    }
