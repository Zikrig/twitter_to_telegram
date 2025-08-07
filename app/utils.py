from sqlalchemy.orm import Session, joinedload
 
from . import models

def get_all_editors(db: Session):
    return db.query(models.Editor).all()

def get_editor_by_id(db: Session, editor_id: int):
    return db.query(models.Editor).filter(models.Editor.id == editor_id).first()

def get_editor_by_telegram_id(db: Session, telegram_id: str):
    return db.query(models.Editor).filter(
        models.Editor.telegram_id == telegram_id
    ).first()
    

def create_editor(db: Session, telegram_id: str, name: str):
    existing_editor = db.query(models.Editor).filter(
        models.Editor.telegram_id == telegram_id
    ).first()
    
    if existing_editor:
        return None
    
    editor = models.Editor(telegram_id=telegram_id, name=name)
    db.add(editor)
    db.commit()
    db.refresh(editor)
    return editor

def delete_editor(db: Session, telegram_id: str):
    editor = db.query(models.Editor).filter(
        models.Editor.telegram_id == telegram_id
    ).first()
    
    if editor:
        db.delete(editor)
        db.commit()
        return True
    return False

def get_editor_channels(db: Session, editor_id: int):
    editor = db.query(models.Editor).filter(
        models.Editor.id == editor_id
    ).first()
    
    return editor.channels if editor else []

# НОВАЯ ФУНКЦИЯ: Получение всех каналов
def get_all_channels(db: Session):
    return db.query(models.Channel).all()

# НОВАЯ ФУНКЦИЯ: Получение канала по Twitter ID
def get_channel_by_twitter_id(db: Session, twitter_id: str):
    return db.query(models.Channel).filter(
        models.Channel.twitter_id == twitter_id
    ).first()

def add_channel_to_editor(db: Session, editor_id: int, channel_data: dict):
    editor = db.query(models.Editor).filter(
        models.Editor.id == editor_id
    ).first()
    
    if not editor:
        return None
    
    # Проверяем существование канала
    channel = get_channel_by_twitter_id(db, channel_data["twitter_id"])
    
    # Если канал не существует - создаем
    if not channel:
        channel = models.Channel(
            name=channel_data["name"],
            twitter_id=channel_data["twitter_id"],
            last_post_time=channel_data.get("last_post_time")
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
    
    # Проверяем связь редактора с каналом
    if channel not in editor.channels:
        editor.channels.append(channel)
        db.commit()
    
    return channel

def remove_channel_from_editor(db: Session, editor_id: int, channel_id: int):
    editor = db.query(models.Editor).filter(
        models.Editor.id == editor_id
    ).first()
    
    channel = db.query(models.Channel).filter(
        models.Channel.id == channel_id
    ).first()
    
    if not editor or not channel:
        return False
    
    if channel in editor.channels:
        editor.channels.remove(channel)
        db.commit()
        return True
    
    return False

def get_all_channels(db: Session):
    return db.query(models.Channel).options(joinedload(models.Channel.editors)).all()


def delete_channel(db: Session, channel_id: int) -> bool:
    """
    Полностью удаляет канал из системы по его ID
    :param db: Сессия базы данных
    :param channel_id: ID канала для удаления
    :return: True если удаление успешно, False если канал не найден
    """
    # Ищем канал по ID
    channel = db.query(models.Channel).filter(
        models.Channel.id == channel_id
    ).first()
    
    if not channel:
        return False
    
    try:
        # Удаляем канал
        db.delete(channel)
        db.commit()
        return True
    except Exception as e:
        # В случае ошибки откатываем изменения
        db.rollback()
        print(f"Error deleting channel: {e}")
        return False
    
    
def get_schedule_settings(db: Session) -> models.ScheduleSettings:
    settings = db.query(models.ScheduleSettings).first()
    if not settings:
        settings = models.ScheduleSettings(hours="9,12,15,18,21")
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

def update_schedule_settings(db: Session, hours: str) -> models.ScheduleSettings:
    settings = get_schedule_settings(db)
    settings.hours = hours
    db.commit()
    db.refresh(settings)
    return settings