from abc import abstractmethod, ABC
from typing import TypeVar, Generic, List

from pydantic.generics import GenericModel

T = TypeVar('T')


class Paginated(GenericModel, Generic[T]):
    current_page: int
    """The currently viewed page."""
    total_pages: int
    """The total number of pages."""
    results_count: int
    """The total number of entries across all pages."""
    entries: List[T]
    """The entries in this page."""

class PaginatedWithUrl(Paginated[T], Generic[T], ABC):

    @property
    def next_page_url(self):
        return None if self.current_page == self.total_pages else self.get_page_url(self.current_page + 1)

    @property
    def previous_page_url(self):
        return None if self.current_page == 1 else self.get_page_url(self.current_page - 1)

    @abstractmethod
    def get_page_url(self, page) -> str:
        raise NotImplementedError
