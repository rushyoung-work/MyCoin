import sqlite3
import datetime
import telegram
import pandas as pd
from threading import Thread
from setting import db_stg

try:
    connn = sqlite3.connect(db_stg)
    df_tg = pd.read_sql('SELECT * FROM telegram', connn)
    connn.close()
except pd.io.sql.DatabaseError:
    bot = ''
    user_id = 0
else:
    bot = df_tg['str_bot'][0]
    user_id = int(df_tg['int_id'][0])


def telegram_msg(text):
    if bot == '':
        print('텔레그램 봇이 설정되지 않아 메세지를 보낼 수 없습니다.')
    else:
        try:
            telegram.Bot(bot).sendMessage(chat_id=user_id, text=text)
        except Exception as e:
            print(f'텔레그램 설정 오류 알림 - telegram_msg {e}')


def thread_decorator(func):
    def wrapper(*args):
        Thread(target=func, args=args, daemon=True).start()
    return wrapper


def now():
    return datetime.datetime.now()


def timedelta_sec(second, std_time=None):
    if std_time is None:
        next_time = now() + datetime.timedelta(seconds=second)
    else:
        next_time = std_time + datetime.timedelta(seconds=second)
    return next_time


def strp_time(timetype, str_time):
    return datetime.datetime.strptime(str_time, timetype)


def strf_time(timetype, std_time=None):
    if std_time is None:
        str_time = now().strftime(timetype)
    else:
        str_time = std_time.strftime(timetype)
    return str_time
