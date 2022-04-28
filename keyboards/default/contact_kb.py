from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

contact_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1,
                                 keyboard=[
                                   [
                                       KeyboardButton(text='📱Отправить номер телефона',
                                                      request_contact=True)
                                   ]
                               ])