from aiogram.dispatcher.filters.state import StatesGroup, State


class ElevationRequest(StatesGroup):
    Phone = State()


class ElevationAdd(StatesGroup):
    Phone = State()


class ElevationRemove(StatesGroup):
    Phone = State()
