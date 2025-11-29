from .database.connection import Database
from .utils import log_message

def process_data(app_config, user):
  with Database(
    app_config['database_url'],
    app_config['api_key']
  ) as connection:
    result = {
      'processed': True,
      'user': user
    }
    log_message(f'データ処理完了')
    return result
    