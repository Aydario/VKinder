# В файле миграции alembic/versions/xxxx_.py
from sqlalchemy import Enum as SqlEnum
from utils.states import BotState

# Для Alembic
def upgrade():
    op.execute("CREATE TYPE bot_state AS ENUM ('MAIN_MENU', 'SEARCHING', 'VIEWING_CANDIDATE', 'FAVORITES', 'SEARCH_SETTINGS', 'PRIORITY_SETTINGS', 'AUTH_IN_PROGRESS')")
    op.alter_column('users', 'state', type_=sa.Enum('MAIN_MENU', 'SEARCHING', 'VIEWING_CANDIDATE', 'FAVORITES', 'SEARCH_SETTINGS', 'PRIORITY_SETTINGS', 'AUTH_IN_PROGRESS', name='bot_state'),
                   postgresql_using='state::text::bot_state')
                   
def downgrade():
    op.alter_column('users', 'state',
                   type_=sa.String(50),
                   postgresql_using='state::text')