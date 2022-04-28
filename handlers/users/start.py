from datetime import datetime

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.builtin import CommandStart, Text
from aiogram.types import ContentType

from data import config
from keyboards.default.admin_kb import admin_kb
from keyboards.default.contact_kb import contact_kb
from keyboards.default.get_kb import get_keyboard
from keyboards.default.regular_kb import regular_kb
from loader import dp, db
from states.elevation import ElevationRequest


@dp.message_handler(CommandStart())
async def bot_start(message: types.Message):
    # on start:
    user_id = message.from_user.id
    user_info = await db.get_user_by_user_id(user_id)
    if user_info is None:
        if str(user_id) not in config.ADMINS:
            await message.answer('Привет, я - TaxiHouseBot!\nЧтобы начать, отправьте ваш номер телефона',
                                 reply_markup=contact_kb)
            await ElevationRequest.Phone.set()
        else:
            username = message.from_user.username
            await db.add_user(user_id=user_id, username=username, is_elevated=True, is_active=True,
                              is_admin=True, watch_on=True, created_at=datetime.now(), updated_at=datetime.now(),
                              phone=None, max_plates=-1, paid_until=datetime.max,
                              delta_paid_until=(datetime.max - datetime.now()).days)
            # log operation
            await db.add_operation(created_at=datetime.now(),
                                   operation=f'adduser|username:{username}|admin:1',
                                   user_id=user_id, by_bot=False, plate=None)
            await message.answer('Привет, я - TaxiHouseBot!', reply_markup=admin_kb)
    else:
        # activate user
        await db.update_user(user_info['id'], user_info['user_id'], user_info['username'], user_info['is_elevated'],
                             True, user_info['is_admin'], user_info['watch_on'], datetime.now(), user_info['phone'],
                             user_info['max_plates'], user_info['paid_until'], user_info['delta_paid_until'])
        keyboard = await get_keyboard(user_id)
        await message.answer('Привет, я - TaxiHouseBot!', reply_markup=keyboard)


@dp.message_handler(content_types=ContentType.CONTACT, state=ElevationRequest.Phone)
async def set_phone(message: types.Message, state: FSMContext):
    dt_now = datetime.now()
    phone = message.contact.phone_number
    user_id = message.from_user.id
    username = message.from_user.username
    await db.add_user(user_id=user_id, username=username, is_elevated=False, is_active=True,
                      is_admin=False, watch_on=True, created_at=datetime.now(), updated_at=datetime.now(),
                      phone=phone, max_plates=2, paid_until=datetime.max,
                      delta_paid_until=(datetime.max - dt_now).days)
    # log operation
    await db.add_operation(created_at=dt_now, operation=f'adduser|username:{username}|admin:0|phone:{phone}',
                           user_id=user_id, by_bot=False, plate=None)
    # notify user
    await message.answer('Привет, я - TaxiHouseBot!\nПриятного использования!', reply_markup=regular_kb)
    # notify admins
    for admin_user_id in config.ADMINS:
        await dp.bot.send_message(admin_user_id, text=f'Новый пользователь: ID {user_id}, телефон {phone}.')
    await state.reset_state()


@dp.message_handler(Text(equals='Назад'), state='*')
async def cancel(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    keyboard = await get_keyboard(user_id)
    await message.answer(text='Привет, я - TaxiHouseBot!', reply_markup=keyboard)
    await state.reset_state()
