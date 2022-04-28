from aiogram.dispatcher.filters.state import StatesGroup, State


class PlatesAdd(StatesGroup):
    Input = State()


class PlatesDelete(StatesGroup):
    Input = State()


class PlatesForceDelete(StatesGroup):
    Input = State()


class PlatesStatus(StatesGroup):
    Input = State()
