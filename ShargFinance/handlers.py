from time import sleep
from aiogram import types
from asyncpg import Connection, Record
from asyncpg.exceptions import UniqueViolationError
from load_all import bot, dp, db
from keyboards import ListOfButtons
from aiogram.types.reply_keyboard import ReplyKeyboardRemove
from filters import *
from aiogram.dispatcher.storage import FSMContext
from states import Coin
from asgiref.sync import sync_to_async

class DBCommands:
    pool: Connection = db
    ADD_NEW_USER_REFERRAL = "INSERT INTO users(chat_id, username, full_name, referral) " \
                            "VALUES ($1, $2, $3, $4) RETURNING id"
    ADD_NEW_USER = "INSERT INTO users(chat_id, username, full_name) VALUES ($1, $2, $3) RETURNING id"
    COUNT_USERS = "SELECT COUNT(*) FROM users"
    GET_ID = "SELECT id FROM users WHERE chat_id = $1"
    CHECK_REFERRALS = "SELECT chat_id FROM users WHERE referral=" \
                      "(SELECT id FROM users WHERE chat_id=$1)"
    CHECK_BALANCE = "SELECT balance FROM users WHERE chat_id = $1"
    ADD_MONEY = "UPDATE users SET balance=balance+$1 WHERE chat_id = $2"
    REDUCE_MONEY = "UPDATE users SET balance=balance-$1 WHERE chat_id = $2"
    ZERO_MONEY="UPDATE users SET balance=0 WHERE chat_id=$1"

    async def add_new_user(self, referral=None):
        user = types.User.get_current()

        chat_id = user.id
        username = user.username
        full_name = user.full_name
        args = chat_id, username, full_name

        if referral:
            args += (int(referral),)
            command = self.ADD_NEW_USER_REFERRAL
        else:
            command = self.ADD_NEW_USER

        try:
            record_id = await self.pool.fetchval(command, *args)
            return record_id
        except UniqueViolationError:
            pass

    async def count_users(self):
        record: Record = await self.pool.fetchval(self.COUNT_USERS)
        return record

    async def get_id(self):
        command = self.GET_ID
        user_id = types.User.get_current().id
        return await self.pool.fetchval(command, user_id)

    async def check_referrals(self):
        user_id = types.User.get_current().id
        command = self.CHECK_REFERRALS
        rows = await self.pool.fetch(command, user_id)
        return ", ".join([
            f"{num + 1}. " + (await bot.get_chat(user["chat_id"])).get_mention(as_html=True)
            for num, user in enumerate(rows)
        ])

    async def check_balance(self):
        command = self.CHECK_BALANCE
        user_id = types.User.get_current().id
        return await self.pool.fetchval(command, user_id)

    async def add_money(self, money):
        command = self.ADD_MONEY
        user_id = types.User.get_current().id
        return await self.pool.fetchval(command, money, user_id)

    async def reduce_money(self, money):
        command = self.REDUCE_MONEY
        user_id = types.User.get_current().id
        return await self.pool.fetchval(command, money, user_id)

    async def zero_money(self):
        command = self.ZERO_MONEY
        user_id = types.User.get_current().id
        return await self.pool.fetchval(command, user_id)


db = DBCommands()

#СТАРТ
@dp.message_handler(commands=["start"])
async def register_user(message: types.Message):
    chat_id = message.from_user.id
    referral = message.get_args()
    id = await db.add_new_user(referral=referral)
    count_users = await db.count_users()

    text = ""
    if not id:
        id = await db.get_id()
    else:
        text += "Recorded in the database!"

    bot_username = (await bot.me).username
    bot_link = f"https://t.me/{bot_username}?start={id}"
    text += f"""
Now there are {count_users} people in the database!
Your referral link: {bot_link}
"""
    keyboard = ListOfButtons(
        text=["Help", "Check balance", "Check referrals"],
        callback=["1", "2", "3"],
        align=[1, 2]
    ).inline_keyboard
    await bot.send_message(chat_id, text,reply_markup=keyboard)



#Просмотр реферралов
@dp.message_handler(commands=["referrals"])
async def check_referrals(message: types.Message):
    referrals = await db.check_referrals()
    text = f"Your referrals:\n{referrals}"
    await message.answer(text)

#добавление денег
@dp.message_handler(commands=["add"])
async def add_money(message: types.Message,state: FSMContext):
    await message.answer("How much do you want to add to your balance")
    await Coin.Add.set()

@dp.message_handler(state=Coin.Add)
async  def add_func(message:Message,state: FSMContext):
    amount_of_money = message.text
    amount_of_money=(int(amount_of_money))
    await db.add_money(amount_of_money)
    balance = await db.check_balance()

    text = f"""
You have been added {amount_of_money} coins.
Now your balance: {balance}
    """
    keyboard =  call_keyboard()
    await message.reply(text=text, reply_markup=keyboard, reply=False)
    await state.finish()

 #Уменьшение Денег
@dp.message_handler(commands=["reduce"])
async def reduce_money(message: types.Message):
    await message.answer("How much do you want to reduce to your balance")
    await Coin.Reduce.set()


@dp.message_handler(state=Coin.Reduce)
async  def add_func(message:Message,state: FSMContext):
    amount_of_money = message.text
    amount_of_money = (int(amount_of_money))
    await db.reduce_money(amount_of_money)
    balance = await db.check_balance()
    text = f"""
You reduced {amount_of_money} coins.
Now your balance: {balance}
 """
    keyboard =  call_keyboard()
    await message.reply(text=text, reply_markup=keyboard, reply=False)
    await state.finish()

def call_keyboard():
    keyboard = ListOfButtons(
        text=["ADD", "REDUCE", "BALANCE", "HELP"],
        align=[2, 2]
    ).reply_keyboard
    return  keyboard

#Обнуление баланса
@dp.message_handler(commands=["zero"])
async def reduce_money(message: types.Message):
    await db.zero_money()
    balance = await db.check_balance()

    text = f"""
Now your balance: {balance}
    """
    keyboard = call_keyboard()
    await message.answer(text,reply_markup=keyboard)


#выводит реферальную ссылку
@dp.message_handler(commands=['link'])
async def check_link(message: types.Message):
    id = await db.get_id()
    bot_username = (await bot.me).username
    bot_link = f"https://t.me/{bot_username}?start={id}"
    text = f""" Your referral link: {bot_link} """
    await message.reply(text=text, reply=False)


#выводит список доступных команд
@dp.message_handler(commands=['help'])
async def process_help_command(message: types.Message):
    text = f"""You can:
1)Check commands: /help

2)Add money: /add 

3)Reduce money: /reduce

4)Check your balance: /balance

5)Zero balance: /zero

6)Check referrals: /referrals

7)Check my referral link /link
"""
    keyboard = call_keyboard()
    await message.reply(text=text,reply=False,reply_markup=keyboard)

@dp.callback_query_handler(Button("1"))
async def check_balance1(call: CallbackQuery):
    text = f"""You can:
1)Check commands: /help

2)Add money: /add

3)Reduce money: /reduce

4)Check your balance: /balance

5)Zero balance: /zero

6)Check referrals: /referrals

7)Check my referral link /link
"""
    await call.message.edit_reply_markup()
    keyboard = call_keyboard()
    await call.message.reply(text=text, reply=False,reply_markup=keyboard)

@dp.message_handler(commands=["balance"])
async def balance(message: types.Message):
    balance = await db.check_balance()
    text = f"Now your balance: {balance}"
    keyboard = call_keyboard()
    await message.answer(text,reply_markup=keyboard)


#Проверка баланса ЧЕРЕЗ КНОПКУ
@dp.callback_query_handler(Button("2"))
async def add_money1(call: CallbackQuery):
    balance = await db.check_balance()
    text = f"Now your balance: {balance}"
    await call.message.edit_reply_markup()
    await call.message.answer(text)

#ПРОВЕРКА РЕФЕРАЛЛОВ ЧЕРЕЗ КНОПКУ
@dp.callback_query_handler(Button("3"))
async def reduce_money(call:  CallbackQuery):
    referrals = await db.check_referrals()
    text = f"Your referrals:\n{referrals}"
    await call.message.edit_reply_markup()
    await call.message.answer(text)




@dp.message_handler(Button("ADD"))
async def add_money(message: types.Message,state: FSMContext):
    await message.answer("How much do you want to add to your balance",reply_markup=ReplyKeyboardRemove())
    await Coin.Add.set()


@dp.message_handler(Button("REDUCE"))
async def reduce_money(message: types.Message):
    await message.answer("How much do you want to reduce to your balance",reply_markup=ReplyKeyboardRemove())
    await Coin.Reduce.set()


@dp.message_handler(Button("BALANCE"))
async def balance(message: types.Message):
    balance = await db.check_balance()
    text = f"Now your balance: {balance}"
    await message.answer(text)

@dp.message_handler(Button("HELP"))
async def process_help_command(message: types.Message):
    text = f"""You can:
1)Check commands: /help

2)Add money: /add

3)Reduce money: /reduce

4)Check your balance: /balance

5)Zero balance: /zero

6)Check referrals: /referrals

7)Check my referral link /link
"""
    keyboard = call_keyboard()
    await message.reply(text=text,reply=False,reply_markup=keyboard)



@dp.message_handler()
async def keyboard(message: Message):
    text=f"What do you want?"
    keyboard=ListOfButtons(
        text=["ADD","REDUCE","BALANCE","HELP"],
        align=[2,2]
    ).reply_keyboard
    await message.reply(text=text,reply_markup=keyboard,reply=False)





