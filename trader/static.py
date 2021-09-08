import datetime
import telegram
from threading import Thread

f = open('user.txt')
lines = f.readlines()
bot = lines[2].strip()
user_id = lines[3].strip()
f.close()


def telegram_msg(text):
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
