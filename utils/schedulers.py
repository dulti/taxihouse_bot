import asyncio
from datetime import datetime

from aiogram import Dispatcher
from aiogram.utils.exceptions import BotBlocked, ChatNotFound

from data import config
from data.config import CONTACT_BOT
from utils.db_api.operations import change_max_plates, remove_extra_plates
from utils.db_api.postgresql import Database
from utils.misc.plate_parser import get_status
from utils.textprocessing import chunks, days_rus, dt_to_readable, max_plates_readable, remaining_rus


async def send_message_to_watchers(dp: Dispatcher, db: Database):
    all_plates = await db.get_all_plates()
    changed_statuses = {}  # store changes

    new_statuses = await get_status([record['plate'] for record in all_plates],
                                    {
                                        record['plate']:
                                            (record['status'], record['status_date']) for record in all_plates
                                    }
                                    )

    for plate_record in all_plates:
        plate = plate_record['plate']
        old_status = plate_record['status']
        new_status, new_date_ = new_statuses[plate]
        if new_status != 'FAIL' and new_status != 'Запись не найдена' and new_status != old_status:
            changed_statuses[plate] = {'id': plate_record['id'], 'status': new_status, 'users': []}
            await db.update_plate(plate=plate, status=new_status, status_date=new_date_, updated_at=datetime.now(),
                                  users_watching=plate_record['users_watching'])
            # log plate update
            await db.add_operation(created_at=datetime.now(), operation=f'updremplate|status:{new_status}',
                                   user_id=None, by_bot=True, plate=plate)
    # iterate through users
    all_users = await db.get_all_users()
    for user_record in all_users:
        if user_record['is_active']:
            await asyncio.sleep(1)
            # string to hold message
            msg_text = ''
            user_id = user_record['user_id']
            user_plates = await db.get_plates_by_user(user_id=user_id)
            for plate_record in user_plates:
                plate = plate_record['plate']
                # if there was a change, add to message
                if plate in changed_statuses.keys():
                    msg_text += f'\n{plate} - {changed_statuses[plate]["status"]}'
                    # add user to changed_statuses
                    changed_statuses[plate]['users'].append(user_id)
                    # add report
                    existing_report = await db.get_report_by_plate_user(plate, user_id)
                    # check if already in report
                    if existing_report is not None:
                        await db.update_report(existing_report['id'], changed_statuses[plate]["status"])
                    else:
                        await db.add_report(created_at=datetime.now(), plate=plate, user_id=user_id,
                                            status=changed_statuses[plate]['status'])
            if len(msg_text) > 0:
                msg_text = f'Есть обновления!\n{msg_text}'
                # echo message
                try:
                    await dp.bot.send_message(user_id, msg_text)
                except BotBlocked:
                    await db.update_user(id_=user_record['id'], user_id=user_id, username=user_record['username'],
                                         is_elevated=user_record['is_elevated'], is_active=False,
                                         is_admin=user_record['is_admin'], watch_on=user_record['watch_on'],
                                         updated_at=datetime.now(), phone=user_record['phone'],
                                         max_plates=user_record['max_plates'], paid_until=user_record['paid_until'],
                                         delta_paid_until=user_record['delta_paid_until'])
                    # log operation
                    await db.add_operation(created_at=datetime.now(), operation='botblocked', user_id=user_id,
                                           by_bot=False, plate=None)
                except ChatNotFound:
                    print(user_id, flush=True)
                    print('Chat not found!', flush=True)
                    print(datetime.now(), flush=True)
                
    # remove updated plates from plates
    for plate in changed_statuses.keys():
        await db.remove_plate(id_=changed_statuses[plate]['id'])
        # and remove from watches
        plate_watches = await db.get_watch_by_plate(plate)
        for plate_watch in plate_watches:
            await db.remove_watch(plate_watch['id'])

    # notify admins of changes
    if len(changed_statuses) > 0:
        msg_text = 'Изменения статусов:'
        changed_statuses_by_user = {}
        for plate in changed_statuses.keys():
            for user in changed_statuses[plate]['users']:
                if user in changed_statuses_by_user.keys():
                    changed_statuses_by_user[user].append((plate, changed_statuses[plate]['status']))
                else:
                    changed_statuses_by_user[user] = [(plate, changed_statuses[plate]['status'])]
        for user in changed_statuses_by_user.keys():
            user_info = await db.get_user_by_user_id(user)
            phone = user_info['phone']
            msg_text += f'\nИзменения для пользователя {user} ({phone}):'
            for plate, status in changed_statuses_by_user[user]:
                msg_text += f'\n{plate} -> {status}'
        # send off
        for user_id in config.ADMINS:
            for chunk in chunks(msg_text, 4000):
                await dp.bot.send_message(user_id, text=chunk)


async def send_report_to_watchers(dp: Dispatcher, db: Database):
    # get all users
    all_users = await db.get_all_users()
    for user_record in all_users:
        if user_record['is_active']:
            await asyncio.sleep(1)
            # string to hold message
            msg_text = ''
            user_id = user_record['user_id']
            user_report = await db.get_report_by_user(user_id)
            for user_report_record in user_report:
                msg_text += f'\n{user_report_record["plate"]} - {user_report_record["status"]}'
            if len(msg_text) > 0:
                msg_text = f'Изменения с предыдущего отчета:{msg_text}'
                try:
                    await dp.bot.send_message(user_id, msg_text)
                    # log report
                    await db.add_operation(created_at=datetime.now(), operation='sendreport', user_id=user_id,
                                           by_bot=True, plate=None)
                except BotBlocked:
                    await db.update_user(id_=user_record['id'], user_id=user_record['user_id'],
                                         username=user_record['username'], is_elevated=user_record['is_elevated'],
                                         is_active=False, is_admin=user_record['is_admin'],
                                         watch_on=user_record['watch_on'],
                                         updated_at=datetime.now(), phone=user_record['phone'],
                                         max_plates=user_record['max_plates'], paid_until=user_record['paid_until'],
                                         delta_paid_until=user_record['delta_paid_until'])
                    # log operation
                    await db.add_operation(created_at=datetime.now(), operation='botblocked', user_id=user_id,
                                           by_bot=False, plate=None)
    await db.clean_report()


async def notify_change_max_plates(dp: Dispatcher, db: Database):
    current_notifications = await db.get_notifications_by_type(notification_type=0)
    for record in current_notifications:
        new_delta = (record['go_off_at'] - datetime.now()).days
        # if the time's up, delete plates and notify user
        if new_delta < 0:
            # prepare data
            old_max_plates, new_max_plates = record['old_value'], record['new_value']
            new_max_plates_str, number_str = max_plates_readable(new_max_plates)

            # do the change
            await change_max_plates(db, new_max_plates, record['user_id'])

            # echo admin
            await dp.bot.send_message(record['added_by'],
                                      f'Для пользователя с Telegram ID {record["user_id"]} сработал таймер. '
                                      f'Количество номеров изменено с {old_max_plates} на {new_max_plates_str}.')
            # if changing down, delete extra plates and echo
            if new_max_plates != -1 and new_max_plates < old_max_plates:
                msg_text = await remove_extra_plates(db, record['user_id'], new_max_plates)
                if msg_text:
                    await dp.bot.send_message(record['user_id'], msg_text)

            # echo user about change
            await dp.bot.send_message(record['user_id'],
                                      f'Изменение: теперь вы можете отслеживать {new_max_plates_str} {number_str}.\n'
                                      f'Если вы хотите изменить лимит номеров, напишите нам: {CONTACT_BOT}')

            # remove notification
            await db.remove_notification(user_id=record['user_id'], notification_type=0)

            # log
            await db.add_operation(created_at=datetime.now(),
                                   operation=f'changemaxplates:{old_max_plates}->{new_max_plates}',
                                   user_id=record['user_id'], by_bot=False, plate=None)

        # otherwise, check if a day has passed
        if new_delta >= 0 and record['delta_days'] - new_delta > 1:
            await dp.bot.send_message(record['user_id'],
                                      f'У вас {remaining_rus(new_delta + 1)} {new_delta + 1} {days_rus(new_delta + 1)},'
                                      f' чтобы удалить лишние номера самостоятельно. '
                                      f'{dt_to_readable(record["go_off_at"], 0)} лишние номера будут удалены '
                                      f'автоматически.\nЕсли вы хотите изменить лимит номеров, напишите '
                                      f'нам: {CONTACT_BOT}')
            await db.update_notification(record['user_id'], 0, new_delta + 1)

            # if one day is left, notify admin too
            if new_delta == 0:
                await dp.bot.send_message(record['added_by'],
                                          f'Завтра ({dt_to_readable(record["go_off_at"], 0)}) для пользователя с '
                                          f'Телеграм ID {record["user_id"]} сработает таймер. Количество номеров'
                                          f'будет изменено с ({record["old_value"]} на {record["new_value"]}).')


async def notify_paid_until(dp: Dispatcher, db: Database):
    for user in await db.get_all_users():
        dt_now = datetime.now()
        if user['is_active'] and not user['is_admin'] and user['is_elevated']:
            new_delta = (user['paid_until'] - dt_now).days
            # update delta_paid_until
            await db.update_user_paid_until(user['user_id'], user['paid_until'], new_delta + 1)

            # if the time's up, demote user and notify all
            if new_delta == -1:
                # do the change
                await change_max_plates(db, 2, user['user_id'])

                # if changing down, delete extra plates and echo
                old_plates = await db.get_plates_by_user(user['user_id'])
                if len(old_plates) > 2:
                    msg_text = await remove_extra_plates(db, user['user_id'], 2)
                    if msg_text:
                        await dp.bot.send_message(user['user_id'], msg_text)

                # echo admins
                for user_id in config.ADMINS:
                    await dp.bot.send_message(user_id, f'Закончился оплаченный срок для пользователя '
                                                       f'{user["user_id"]}.')
                # echo user about change
                await dp.bot.send_message(user['user_id'], f'Закончился оплаченный период. '
                                                           f'Если хотите продлить период, напишите нам: {CONTACT_BOT}')

                # log
                await db.add_operation(created_at=dt_now, operation=f'paiddue',
                                       user_id=user['user_id'], by_bot=True, plate=None)

            # otherwise, check if a day has passed
            if new_delta >= 0 and user['delta_paid_until'] - new_delta > 1:

                # if under 10 days, start notifying
                if new_delta < 10:
                    await dp.bot.send_message(user['user_id'],
                                              f'Оплаченный период закончится в {dt_to_readable(user["paid_until"], 1)}'
                                              f'\nЕсли вы хотите продлить оплаченный период, напишите нам: '
                                              f'{CONTACT_BOT}')

                # if one day is left, notify admin too
                if new_delta == 0:
                    for user_id in config.ADMINS:
                        await dp.bot.send_message(user_id, f'Завтра ({dt_to_readable(user["paid_until"], 0)}) '
                                                           f'закончится оплаченный период для пользователя '
                                                           f'{user["user_id"]}.')
