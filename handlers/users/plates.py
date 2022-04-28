from datetime import datetime

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types import Message, InlineKeyboardMarkup

from data.config import TOTAL_PLATES, CONTACT_BOT
from filters import ElevatedFilter, AdminFilter
from keyboards.default.admin_kb import admin_kb
from keyboards.default.back_kb import back_kb
from keyboards.default.get_kb import get_keyboard
from loader import dp, db
from states.plates import PlatesAdd, PlatesForceDelete, PlatesDelete, PlatesStatus
from utils.db_api.operations import add_plate, force_delete_plate, delete_plate
from utils.textprocessing import users_rus, chunks, plates_rus, process_input
from utils.misc.plate_parser import get_status


async def output_plates(plates: list, message: types.Message, keyboard: InlineKeyboardMarkup, all_plates: bool):
    if len(plates) == 0:
        await message.answer('Ничего не отслеживается. Добавьте номер к отслеживанию', reply_markup=keyboard)
    else:
        response = 'Номер - Статус'
        if all_plates:
            response += '- Пользователи'
        for plate_record in plates:
            plate = plate_record['plate']
            status = plate_record['status']
            response += f'\n{plate} - {status}'
            if all_plates:
                users_watching = plate_record['users_watching']
                response += f' - {users_watching} {users_rus(users_watching)}'
        for chunk in chunks(response, 4000):
            await message.answer(chunk, reply_markup=keyboard)

    # log operation
    user_id = message.from_user.id
    operation_str = 'getallplates' if all_plates else 'getplates'
    await db.add_operation(created_at=datetime.now(), operation=operation_str, user_id=user_id,
                           by_bot=False, plate=None)


@dp.message_handler(Text(equals='Добавить'))
async def add_plate_handler(message: Message):
    await PlatesAdd.Input.set()
    await message.answer('Введите номера, разделенные новой строкой, '
                         'или нажмите Назад для выхода', reply_markup=back_kb)


@dp.message_handler(state=PlatesAdd.Input)
async def add_many_handler_state(message: types.Message, state: FSMContext):

    # process input
    correct_plates, incorrect_plates, plates_count = process_input(message.text)

    # get user data
    user_id = message.from_user.id
    user = await db.get_user_by_user_id(user_id)
    plates_watched = await db.count_watches_by_user(user_id)
    user_limit = user['max_plates']

    # check for TOTAL limit
    if plates_count > TOTAL_PLATES:
        await message.answer(f'Можно добавить не более {TOTAL_PLATES} номеров за один раз!', reply_markup=back_kb)

    # check for user-specific limit
    # user_limit is set to -1 when it's off (for admins)
    elif user_limit != -1 and plates_watched + plates_count > user_limit:
        plates_left = user_limit - plates_watched
        await message.answer(f'Вы можете отслеживать только {user_limit} {plates_rus(user_limit)}! '
                             f'Сейчас вы отслеживаете {plates_watched} {plates_rus(plates_watched)}. '
                             f'Вы можете добавить еще {plates_left} {plates_rus(plates_left)}. '
                             f'Чтобы отслеживать больше, напишите нам: {CONTACT_BOT}')

    else:
        # echo user the operation is underway
        response = await message.answer('Добавляю номера... Подождите')
        msg_text = ""

        # parse correct plates
        parsing_result = await get_status(correct_plates)

        # add correct plates
        for plate, (status, date_) in parsing_result.items():
            if status == 'FAIL':
                # log attempt
                await db.add_operation(created_at=datetime.now(), operation='watchplatemany|status:fail',
                                       user_id=user_id, by_bot=False, plate=plate)
                msg_text += f'\nНе удалось получить ответ от базы для номера {plate}! Попробуйте позднее.'
            else:
                msg_text += await add_plate(db, user_id, plate, status, date_)

        # now add incorrect plates
        for plate in incorrect_plates:
            msg_text += f'\nНомер {plate} введен неверно!'
            await db.add_operation(created_at=datetime.now(), operation='watchplate|status:fail',
                                   user_id=user_id, by_bot=False, plate=plate)
        # echo user: end operation
        keyboard = await get_keyboard(user_id)
        await response.delete()
        await message.answer(msg_text + '\n\nВсе номера добавлены!', reply_markup=keyboard)
        await state.reset_state()


@dp.message_handler(Text(equals='Номера всех'), AdminFilter())
async def get_all_plates_handler(message: types.Message):
    plates = await db.get_all_plates()

    await output_plates(plates, message, admin_kb, all_plates=True)


@dp.message_handler(Text(equals='Все номера'), ElevatedFilter())
async def get_plates_handler(message: types.Message):
    user_id = message.from_user.id
    plates = await db.get_plates_by_user(user_id=user_id)
    keyboard = await get_keyboard(user_id)

    await output_plates(plates, message, keyboard, all_plates=False)


@dp.message_handler(Text(equals='Удалить для всех'), AdminFilter())
async def force_remove_plate_handler(message: types.Message):
    await message.answer('Введите номера, разделенные новой строкой, или нажмите Назад для выхода',
                         reply_markup=back_kb)
    await PlatesForceDelete.Input.set()


@dp.message_handler(AdminFilter(), state=PlatesForceDelete.Input)
async def force_remove_plate_handler_state(message: types.Message, state: FSMContext):
    correct_plates, incorrect_plates, plates_count = process_input(message.text)

    user_id = message.from_user.id

    # echo user: start operation
    if plates_count > TOTAL_PLATES:
        await message.answer(f'Можно удалить не более {TOTAL_PLATES} номеров за один раз!', reply_markup=back_kb)
    else:
        response = await message.answer('Удаляю номера...')
        msg_text = ""
        for plate in correct_plates:
            msg_text += await force_delete_plate(db, plate, user_id)

        for plate in incorrect_plates:
            msg_text += f'Номер {plate} введен неверно!\n'
        # echo user: end operation
        keyboard = await get_keyboard(user_id)
        await response.delete()
        await message.answer(msg_text + '\n\nВсе номера удалены!', reply_markup=keyboard)
        await state.reset_state()


@dp.message_handler(Text(equals='Удалить'))
async def remove_plates_handler(message: Message):
    await message.answer('Введите номера, разделенные новой строкой, или нажмите Назад для выхода',
                         reply_markup=back_kb)
    await PlatesDelete.Input.set()


@dp.message_handler(state=PlatesDelete.Input)
async def remove_plate_handler_state(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    correct_plates, incorrect_plates, plates_count = process_input(message.text)

    if plates_count > TOTAL_PLATES:
        await message.answer(f'Можно удалить не более {TOTAL_PLATES} номеров за один раз!', reply_markup=back_kb)
    else:
        response = await message.answer('Удаляю номера...')
        msg_text = ""
        for plate in correct_plates:
            if await delete_plate(db, plate, user_id):
                msg_text += f'Номер {plate} удален из отслеживания.\n'
            else:
                msg_text += f'Вы не отслеживаете номер {plate}. Проверьте, правильно ли введен номер.\n'
        for plate in incorrect_plates:
            msg_text += f'Номер {plate} введен неверно!\n'
        # echo user: end operation
        keyboard = await get_keyboard(user_id)
        await response.delete()
        await message.answer(msg_text + '\n\nВсе номера удалены!', reply_markup=keyboard)
        await state.reset_state()


@dp.message_handler(Text(equals='Статус'))
async def get_status_handler(message: Message):
    await message.answer('Введите номера, разделенные новой строкой, или нажмите Назад для выхода',
                         reply_markup=back_kb)
    await PlatesStatus.Input.set()


@dp.message_handler(ElevatedFilter(), state=PlatesStatus.Input)
async def get_status_handler_state(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    correct_plates, incorrect_plates, plates_count = process_input(message.text)

    if plates_count >= TOTAL_PLATES:
        await message.answer('Можно добавить не более 30 номеров за один раз!', reply_markup=back_kb)
    else:
        await message.answer('Запрашиваю статус...')

        msg_text = ""

        # parse correct plates
        parsing_result = await get_status(correct_plates)

        # output correct statuses
        for plate, (status, _) in parsing_result.items():
            if status == 'FAIL':
                msg_text += f'Не получилось запросить статус для номера {plate}: ошибка базы.\n'
            else:
                msg_text += f'{plate} - {status}\n'
            # log checking
            await db.add_operation(created_at=datetime.now(), operation=f'checkstatus|{status}', user_id=user_id,
                                   by_bot=False, plate=plate)
        for plate in incorrect_plates:
            msg_text += f'Номер {plate} введен неверно!\n'
        # echo user: end operation
        keyboard = await get_keyboard(user_id)
        await message.answer(msg_text + '\nОперация завершена!', reply_markup=keyboard)
        await state.reset_state()
