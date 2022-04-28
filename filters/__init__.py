from loader import dp
from .access_filters import ElevatedFilter, AdminFilter


if __name__ == "filters":
    dp.filters_factory.bind(AdminFilter)
    dp.filters_factory.bind(ElevatedFilter)
