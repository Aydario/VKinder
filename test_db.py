from db.connection import engine, get_db

def test_connection():
    print("1. Проверка подключения к PostgreSQL...")
    try:
        # Проверяем соединение с БД
        with engine.connect() as conn:
            print("✅ Подключение успешно!")
            
            # Проверяем существование таблиц
            tables = ['users', 'favorites', 'blacklist', 'search_params']
            existing_tables = conn.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """).fetchall()
            
            existing_tables = {t[0] for t in existing_tables}
            missing_tables = set(tables) - existing_tables
            
            if missing_tables:
                print(f"❌ Отсутствуют таблицы: {missing_tables}")
            else:
                print("✅ Все таблицы на месте!")
                
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

if __name__ == "__main__":
    test_connection()
    