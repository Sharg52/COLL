from aiogram.dispatcher.filters.state import State,StatesGroup

class Coin(StatesGroup):
    Add=State()
    Reduce=State()