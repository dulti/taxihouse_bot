from aiogram.dispatcher.filters.state import StatesGroup, State


class ChangeMaxPlates(StatesGroup):
    InputPhone = State()
    InputMaxPlates = State()
    InputGracePeriod = State()


class ChangePaidUntil(StatesGroup):
    InputPhone = State()
    InputNewTime = State()
