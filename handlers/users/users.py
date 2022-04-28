import time
from datetime import datetime, timedelta

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command, Text

from data.config import CONTACT_BOT
from filters import AdminFilter
from keyboards.default.admin_kb import admin_kb
from keyboards.default.back_kb import back_kb
from keyboards.default.elevated_kb import elevated_kb
from loader import dp, db
from states.access import ChangeMaxPlates, ChangePaidUntil
from utils.db_api.operations import change_max_plates, remove_extra_plates
from utils.schedulers import send_message_to_watchers, send_report_to_watchers
from utils.textprocessing import plates_rus, days_rus, dt_to_readable, max_plates_readable, parse_date


async def output_max_plates_change(message: types.Message, state: FSMContext, new_max_plates: int, user_id: int):
    new_max_plates_str, number_str = max_plates_readable(new_max_plates)
    await change_max_plates(db, new_max_plates, user_id)
    # echo admin
    await message.answer(
        f'Пользователь с Telegram ID {user_id} теперь может отслеживать '
        f'{new_max_plates_str} {number_str}.', reply_markup=admin_kb)

    # echo user
    await dp.bot.send_message(user_id, f'Теперь вы можете отслеживать {new_max_plates_str} {number_str}.')

    await state.reset_state()


@dp.message_handler(Text(equals='Пользователи'), AdminFilter())
async def get_users(message: types.Message):
    user_id = message.from_user.id
    all_users = await db.get_all_users()
    response = 'Список пользователей:\n'
    for user in all_users:
        if user['is_active']:
            response += (f'Telegram ID: {user["user_id"]}, username: {user["username"]}, '
                         f'администратор: {["нет", "да"][int(user["is_admin"])]}, '
                         f'продвинутый: {["нет", "да"][int(user["is_elevated"])]}, '
                         f'телефон: {user["phone"]}, отслеживает: {user["total_plates"]} '
                         f'{plates_rus(user["total_plates"])}, лимит номеров: '
                         f'{user["max_plates"] if user["max_plates"] != -1 else "нет"}, '
                         f'оплаченный период: '
                         f'{dt_to_readable(user["paid_until"], 1) if user["paid_until"].year != 9999 else "нет"}.\n')
    await db.add_operation(created_at=datetime.now(), operation='getallusers',
                           user_id=user_id, by_bot=False, plate=None)
    await message.answer(response, reply_markup=admin_kb)


@dp.message_handler(Text(equals='Неакт. пользователи'), AdminFilter())
async def get_dead_users(message: types.Message):
    user_id = message.from_user.id
    all_users = await db.get_all_users()
    response = ''
    for user_record in all_users:
        if not user_record['is_active']:
            response += (f'Telegram ID: {user_record["user_id"]}, username: {user_record["username"]}, '
                         f'администратор: {["нет", "да"][int(user_record["is_admin"])]}, '
                         f'продвинутый: {["нет", "да"][int(user_record["is_elevated"])]}, '
                         f'телефон: {user_record["phone"]}.\n')
    if len(response) > 0:
        response = 'Список пользователей:\n' + response
        await message.answer(response, reply_markup=admin_kb)
    else:
        await message.answer('Нет неактивных пользователей!', reply_markup=admin_kb)

    # log request
    await db.add_operation(created_at=datetime.now(), operation='getallusers', user_id=user_id, by_bot=False,
                           plate=None)


@dp.message_handler(Text(equals='Ред. кол-во номеров'), AdminFilter())
async def change_max_plates_handler(message: types.Message):
    await message.answer('Введите номер телефона пользователя, для которого нужно изменить количество номеров:',
                         reply_markup=back_kb)
    await ChangeMaxPlates.InputPhone.set()


@dp.message_handler(AdminFilter(), state=ChangeMaxPlates.InputPhone)
async def change_max_plates_state_1(message: types.Message, state: FSMContext):
    # get user data
    phone = message.text
    await state.set_data({'phone': phone})
    user = await db.get_user_by_phone(phone)

    if user is None:
        await message.answer('Вы ввели неправильный номер, либо такого пользователя не существует.',
                             reply_markup=back_kb)
    elif not user['is_elevated']:
        await message.answer('Для этого пользователя недоступны расширенные функции! Сначала дайте доступ.',
                             reply_markup=back_kb)
    else:
        # make readable string
        max_plates_str = user['max_plates']
        if max_plates_str == -1:
            max_plates_str = 'бесконечное'

        await message.answer(f'Текущее количество номеров: {max_plates_str}. Введите новое количество номеров,'
                             f' либо нажмите Назад. Чтобы убрать ограничение на количество номеров, введите '
                             f'"-1" (без кавычек).', reply_markup=back_kb)
        await ChangeMaxPlates.InputMaxPlates.set()


@dp.message_handler(AdminFilter(), state=ChangeMaxPlates.InputMaxPlates)
async def change_max_plates_state_2(message: types.Message, state: FSMContext):
    try:
        # get user data
        new_max_plates = int(message.text)
    except TypeError:
        await message.answer('Неверный ввод! Введите верное число, либо вернитесь назад.', reply_markup=back_kb)
        return
    phone = (await state.get_data())['phone']
    user = await db.get_user_by_phone(phone)
    old_max_plates = user['max_plates']

    if new_max_plates == -1 or new_max_plates >= old_max_plates:
        # we are increasing the number of plates; no other action is needed
        # remove any other notifications
        await db.remove_notification(user['user_id'], notification_type=0)
        await output_max_plates_change(message, state, new_max_plates, user['user_id'])
        await db.add_operation(created_at=datetime.now(),
                               operation=f'changemaxplates:{old_max_plates}->{new_max_plates}',
                               user_id=user['user_id'], by_bot=False, plate=None)
    else:
        # we are decreasing the number of plates; ask the admin how many days to give as a grace period
        await message.answer(f'Вы собираетесь уменьшить количество номеров для пользователя {user["user_id"]}. '
                             f'Сколько дней дать пользователю? Введите 0, чтобы удалить номера немедленно. '
                             f'Либо нажмите Назад для возвращения', reply_markup=back_kb)

        await state.update_data({'new_max_plates': new_max_plates, 'old_max_plates': old_max_plates})
        await ChangeMaxPlates.InputGracePeriod.set()


@dp.message_handler(AdminFilter(), state=ChangeMaxPlates.InputGracePeriod)
async def change_max_plates_state_3(message: types.Message, state: FSMContext):
    try:
        # get user data
        grace_period = int(message.text)
        phone = (await state.get_data())['phone']
        new_max_plates = (await state.get_data())['new_max_plates']
        old_max_plates = (await state.get_data())['old_max_plates']
        user = await db.get_user_by_phone(phone)
        dt_now = datetime.now()

        # remove any old notifications for this number
        await db.remove_notification(user['user_id'], notification_type=0)

        if grace_period == 0:
            await output_max_plates_change(message, state, new_max_plates, user['user_id'])

            # log
            await db.add_operation(created_at=datetime.now(),
                                   operation=f'changemaxplates:{old_max_plates}->{new_max_plates}',
                                   user_id=user['user_id'], by_bot=False, plate=None)

            # remove extra plates
            msg_text = await remove_extra_plates(db, user['user_id'], new_max_plates)
            if msg_text:
                await dp.bot.send_message(user['user_id'], msg_text, reply_markup=elevated_kb)

        else:
            # add a notification
            go_off_at = dt_now + timedelta(days=grace_period)
            await db.add_notification(user_id=user['user_id'], notification_type=0, added_by=message.from_user.id,
                                      added_at=dt_now, go_off_at=go_off_at, delta_days=grace_period,
                                      old_value=old_max_plates, new_value=new_max_plates)

            # notify admin
            await message.answer(f'Количество номеров будет изменено для пользователя {user["user_id"]} '
                                 f'{dt_to_readable(go_off_at, 0)}. Новое количество номеров: {new_max_plates}. '
                                 f'Нажмите Назад, чтобы вернуться.')

            # notify user
            await dp.bot.send_message(user['user_id'],
                                      f'Максимальное количество номеров, которое вы можете отслеживать, было '
                                      f'изменено на {new_max_plates}. У вас есть {grace_period} '
                                      f'{days_rus(grace_period)}, чтобы удалить лишние номера самостоятельно. '
                                      f'{dt_to_readable(go_off_at, 0)} лишние номера будут удалены автоматически, '
                                      f'и останутся только {new_max_plates} {plates_rus(new_max_plates)}, которые '
                                      f'были добавлены раньше всех.\nЕсли вы хотите изменить лимит номеров, '
                                      f'напишите нам: {CONTACT_BOT}')
            await state.reset_state()

    except ValueError:
        await message.answer('Неверный ввод! Введите верное число, либо вернитесь назад.', reply_markup=back_kb)


@dp.message_handler(Text(equals='Ред. оплач. период'), AdminFilter())
async def change_paid_limit_handler(message: types.Message):
    await message.answer('Введите номер телефона пользователя, для которого нужно изменить количество номеров:',
                         reply_markup=back_kb)
    await ChangePaidUntil.InputPhone.set()


@dp.message_handler(AdminFilter(), state=ChangePaidUntil.InputPhone)
async def change_paid_limit_state_1(message: types.Message, state: FSMContext):
    # get user data
    phone = message.text
    await state.set_data({'phone': phone})
    user = await db.get_user_by_phone(phone)

    if user is None:
        await message.answer('Вы ввели неправильный номер, либо такого пользователя не существует.',
                             reply_markup=back_kb)
    elif not user['is_elevated']:
        await message.answer('Для этого пользователя недоступны расширенные функции! Сначала дайте доступ.',
                             reply_markup=back_kb)
    else:
        paid_until = user['paid_until']
        if paid_until.year != 9999:
            paid_until_str = f'Сейчас услуги оплачены до {dt_to_readable(paid_until, 1)}.'
        else:
            paid_until_str = 'Сейчас нет временного ограничения оплаченных услуг.'

        await message.answer(f'{paid_until_str} Введите новую дату в формате "дд.мм.гггг чч:мм" либо "дд.мм.гггг", '
                             f'либо нажмите Назад. Чтобы убрать ограничение на время использования, '
                             f'введите "-1".', reply_markup=back_kb)
        await ChangePaidUntil.InputNewTime.set()


@dp.message_handler(AdminFilter(), state=ChangePaidUntil.InputNewTime)
async def change_paid_limit_state_2(message: types.Message, state: FSMContext):
    dt_now = datetime.now()
    if message.text == '-1':  # limit off
        new_paid_until = datetime.max
        new_paid_until_str = 'без ограничений'
    else:
        # parse input
        try:
            new_paid_until = parse_date(message.text, dt_now)
            new_paid_until_str = 'до ' + dt_to_readable(new_paid_until, 1)
        except ValueError:
            await message.answer('Неверный ввод! Введите верную дату, либо вернитесь назад.', reply_markup=back_kb)
            return

    if new_paid_until < dt_now:
        await message.answer('Введенная дата не может быть раньше текущей. Попробуйте еще раз, или вернитесь назад.',
                             reply_markup=back_kb)
        return

    phone = (await state.get_data())['phone']
    user = await db.get_user_by_phone(phone)
    old_paid_until = user['paid_until']

    # we are increasing the time limit, no action is needed
    await db.update_user_paid_until(user['user_id'], new_paid_until, (new_paid_until - dt_now).days)

    # notify admin
    await message.answer(f'Вы изменили оплаченный период для пользователя {user["user_id"]}. '
                         f'Новый период: {new_paid_until_str}.', reply_markup=admin_kb)

    # notify user
    await dp.bot.send_message(user['user_id'], f'Оплаченный период услуг был изменен. Новый период: '
                                               f'{new_paid_until_str}. Если вы хотите продлить период, '
                                               f'свяжитесь с нами: {CONTACT_BOT}')

    # log
    await db.add_operation(created_at=dt_now,
                           operation=f'changepaiduntil:{dt_to_readable(old_paid_until, 1)}->'
                                     f'{dt_to_readable(new_paid_until, 1)}',
                           user_id=user['user_id'], by_bot=False, plate=None)

    await state.reset_state()


@dp.message_handler(Command('__debug_watch'), AdminFilter())
async def debug_watch(message: types.Message):
    await message.answer('Обновление...')
    start_time = time.time()
    await send_message_to_watchers(dp, db)
    end_time = time.time() - start_time
    await message.answer(f'Обновление закончено! {end_time:.2f} секунд.')


@dp.message_handler(Command('__debug_report'), AdminFilter())
async def debug_report():
    await send_report_to_watchers(dp, db)
