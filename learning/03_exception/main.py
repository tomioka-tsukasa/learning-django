import traceback

class MiunNumberException(Exception):
  def __init__(self, message, code):
    self.message = message
    self.code = code
    super().__init__(self.message, self.code)

message = '何の数字で10を割りたいか入力してください: '

while True:
  try:
    division_val = int(input(message))

    if (division_val < 0):
      raise MiunNumberException('正数で入力してください。', 410)

    result = 10 / division_val
    print(f'割った後の値: {result}')

  except ZeroDivisionError as e:
    traceback.print_exc()
    print(e, type(e))
    message = '0で割ることはできません: '

  except ValueError as e:
    traceback.print_exc()
    print(e, type(e))
    message = '数値で入力してください: '

  except MiunNumberException as e:
    traceback.print_exc()
    print(e, type(e))
    message = '正数で入力してください。'

  except Exception as e:
    traceback.print_exc()
    print('Exception: ', e, type(e))
    message = '不明なエラーが発生しました'

  else:
    print('処理終了')
    break

  finally:
    print('finnaly')
