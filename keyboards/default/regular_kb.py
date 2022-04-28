from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

regular_kb = ReplyKeyboardMarkup(resize_keyboard=True,
                                 keyboard=[
                                           [
                                               KeyboardButton(text='Добавить'),  # add_plates
                                               KeyboardButton(text='Удалить')  # remove_plates
                                           ]
                                       ]
                                )
