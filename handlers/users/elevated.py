from datetime import datetime

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text

from data import config
from data.config import CONTACT_BOT
from filters import AdminFilter
from keyboards.default.admin_kb import admin_kb
from keyboards.default.back_kb import back_kb
from keyboards.default.elevated_kb import elevated_kb, request_kb
from keyboards.default.get_kb import get_keyboard
from loader import dp, db
from states.elevation import ElevationAdd, ElevationRemove
from utils.db_api.operations import demote_user


@dp.message_handler(Text(equals='Дать доступ'), AdminFilter())
async def elevate_user_handler(message: types.Message):
    await message.answer('Введите номер телефона пользователя, которому нужно дать доступ:', reply_markup=back_kb)
    await ElevationAdd.Phone.set()


@dp.message_handler(AdminFilter(), state=ElevationAdd.Phone)
async def elevate_user_state_1(message: types.Message, state: FSMContext):
    phone = message.text
    user = await db.get_user_by_phone(phone)
    if user is None:
        await message.answer('Вы ввели неправильный номер.', reply_markup=back_kb)
    elif user['is_elevated']:
        await message.answer('Для этого пользователя уже доступны расширенные функции!', reply_markup=back_kb)
    else:
        await db.update_user(id_=user['id'], user_id=user['user_id'], username=user['username'], is_elevated=True,
                             is_active=True, is_admin=False, watch_on=user['watch_on'], updated_at=datetime.now(),
                             phone=phone, max_plates=2, paid_until=datetime.max,
                             delta_paid_until=(datetime.max - datetime.now()).days)
        await db.add_operation(created_at=datetime.now(), operation='elevateuser', user_id=message.from_user.id,
                               by_bot=False, plate=None)
        await message.answer(f'Пользователь с Telegram ID {user["user_id"]} теперь имеет доступ к продвинутым '
                             f'функциям! Сняты все ограничения на срок оплаты. При необходимости, установите '
                             f'ограничение вручную.', reply_markup=admin_kb)
        await dp.bot.send_message(user['user_id'], 'Вы получили доступ к расширенным функциям!',
                                  reply_markup=elevated_kb)
        await state.reset_state()


@dp.message_handler(Text(equals='Забрать доступ'), AdminFilter())
async def demote_user_handler(message: types.Message):
    await message.answer('Введите номер телефона пользователя, у которого нужно забрать доступ:', reply_markup=back_kb)
    await ElevationRemove.Phone.set()


@dp.message_handler(AdminFilter(), state=ElevationRemove.Phone)
async def demote_user_state_1(message: types.Message, state: FSMContext):
    phone = message.text
    user = await db.get_user_by_phone(phone)
    if user is None:
        await message.answer('Вы ввели неправильный номер.', reply_markup=back_kb)
    elif str(user['user_id']) in config.ADMINS:
        await message.answer('Нельзя ограничить доступ администратору!', reply_markup=back_kb)
    else:
        plates = await demote_user(db, user)
        await message.answer(f'Для пользователя с Telegram ID {user["user_id"]} теперь недоступны продвинутые функции!',
                             reply_markup=admin_kb)
        await state.reset_state()
        await dp.bot.send_message(user['user_id'], f'Теперь вам доступны только базовые функции! '
                                                   f'Были удалены все номера: {", ".join(plates)}.\n'
                                                   f'Чтобы восстановить доступ, напишите нам: {CONTACT_BOT}',
                                  reply_markup=request_kb)


@dp.message_handler(Text('Запросить доступ'))
async def rerequest_access(message: types.Message):
    # echo user
    await message.answer(f'Вы запросили доступ к расширенным функциям. Ожидайте ответа администратора, либо '
                         f'напишите нам: {CONTACT_BOT}')

    # echo admin
    phone = (await db.get_user_by_user_id(message.from_user.id))['phone']
    for user_id in config.ADMINS:
        await dp.bot.send_message(user_id, f'Пользователь {message.from_user.id} с номером телефона {phone} '
                                           f'запросил доступ к расширенным функциям.',
                                  reply_markup=await get_keyboard(user_id))
