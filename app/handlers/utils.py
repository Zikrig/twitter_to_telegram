# utils.py (оставляем без изменений)
from aiogram import Router, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..utils import *
router = Router()


def build_cancel_keyboard() -> types.InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с кнопкой отмены"""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_action")
    return builder.as_markup()


def build_editor_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить канал")],
            [KeyboardButton(text="➖ Удалить канал")],
            [KeyboardButton(text="📋 Мои каналы")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )
    
def build_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить канал"), KeyboardButton(text="➖ Удалить канал")],
            [KeyboardButton(text="📋 Мои каналы"), KeyboardButton(text="📋 Все каналы")],
            [KeyboardButton(text="➕ Добавить редактора"), KeyboardButton(text="➖ Удалить редактора")],
            [KeyboardButton(text="🗑️ Удалить канал из системы")],
            [KeyboardButton(text="⏰ Управление расписанием")]  # Новая кнопка
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )