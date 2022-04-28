from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

elevated_kb = ReplyKeyboardMarkup(resize_keyboard=True,
                                  keyboard=[
                                               [
                                                   KeyboardButton(text='Добавить'),  # add_plates
                                                   KeyboardButton(text='Удалить')  # remove_plates
                                               ],
                                               [
                                                   KeyboardButton(text='Все номера'),  # get_plates
                                                   KeyboardButton(text='Статус')  # get_status
                                               ]
                                           ]
                                  )

request_kb = ReplyKeyboardMarkup(resize_keyboard=True,
                                 keyboard=[
                                     [
                                         KeyboardButton(text='Запросить доступ')
                                     ]
                                 ])
