# Импортируем необходимые модули
from sqlalchemy import text  # Для безопасного выполнения SQL-запросов
from db.connection import engine  # Импортируем движок из connection.py

def test_connection():
    print("1. Проверка подключения к PostgreSQL...")
    
    try:
        # Открываем соединение с БД (контекстный менеджер сам закроет его)
        with engine.connect() as conn:
            # Простейший запрос для проверки соединения
            conn.execute(text("SELECT 1"))
            print("✅ Подключение успешно!")

            # Список таблиц, которые ДОЛЖНЫ существовать
            required_tables = {'users', 'favorites', 'blacklist', 'search_params'}
            
            # Запрос к системной таблице information_schema для получения списка таблиц
            # text() используется для безопасного выполнения SQL
            result = conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
            
            # Преобразуем результат в множество имен таблиц
            existing_tables = {row[0] for row in result}
            
            # Находим отсутствующие таблицы (разница множеств)
            missing_tables = required_tables - existing_tables

            if missing_tables:
                print(f"❌ Отсутствуют таблицы: {missing_tables}")
            else:
                print("✅ Все таблицы на месте!")

    except Exception as e:
        # Выводим тип и текст ошибки, если что-то пошло не так
        print(f"❌ Ошибка подключения: {type(e).__name__}: {e}")

# Точка входа (запускаем тест при прямом вызове файла)
if __name__ == "__main__":
    test_connection()
