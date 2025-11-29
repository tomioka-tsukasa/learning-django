from pprint import pprint
from config import get_config
from myapp.database.models import User
from myapp.utils import validate_user
from myapp.core import process_data

def main():
  app_config = get_config()

  print(f'デバックモード: {app_config["debug"]}')
  test_data = User(name='Taro', email='taro@mail.com')
  if (validate_user(test_data)):
    print('バリデーション完了')
    result = process_data(app_config, test_data)
    print(f'処理成功')
    print(result)

if __name__ == '__main__':
  main()
