from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

admin_kb = ReplyKeyboardMarkup(resize_keyboard=True,
                               keyboard=[
                                            [
                                                KeyboardButton(text='Добавить'),  # add_plates
                                                KeyboardButton(text='Удалить')  # remove_plates
                                            ],
                                            [
                                                KeyboardButton(text='Удалить для всех'),  # force_remove_plates
                                                KeyboardButton(text='Все номера')  # get_plates
                                            ],
                                            [
                                                KeyboardButton(text='Номера всех'),  # get_all_plates
                                                KeyboardButton(text='Статус')  # get_status
                                            ],
                                            [
                                                KeyboardButton(text='Дать доступ'),  # elevate_user
                                                KeyboardButton(text='Забрать доступ')  # demote_user
                                            ],
                                            [
                                                KeyboardButton(text='Пользователи'),  # get_users
                                                KeyboardButton(text='Неакт. пользователи')  # get_dead_users
                                            ],
                                            [
                                                KeyboardButton(text='Ред. кол-во номеров'),  # get_users
                                                KeyboardButton(text='Ред. оплач. период')  # get_dead_users
                                            ]
                                        ]
                               )
