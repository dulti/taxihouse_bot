from aiogram import types
from aiogram.dispatcher.filters import BoundFilter

from data import config
from loader import db


class AdminFilter(BoundFilter):
    async def check(self, message: types.Message) -> bool:
        user_id = message.from_user.id
        return str(user_id) in config.ADMINS


class ElevatedFilter(BoundFilter):
    async def check(self, message: types.Message) -> bool:
        user_id = message.from_user.id
        user = await db.get_user_by_user_id(user_id)
        return user['is_elevated']
