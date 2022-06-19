from aiogram.types import Message

from keyboards.default.get_kb import get_keyboard
from loader import dp


@dp.message_handler(state=None)
async def default_handler(message: Message):
    # get user data
    user_id = message.from_user.id
    keyboard = await get_keyboard(user_id)
    msg_text = 'Выберите команду из меню. Например, чтобы добавить новый номер к отслеживанию, выберите ' \
               'команду "Добавить".'
    await message.answer(msg_text, reply_markup=keyboard)
