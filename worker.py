import time
import logging
import pyupbit
import pandas as pd
from PyQt5 import QtCore
from PyQt5.QtCore import QThread
from pyupbit import WebSocketManager
from setting import *
from static import now, timedelta_sec, strf_time


class Worker(QThread):
    data0 = QtCore.pyqtSignal(list)
    data1 = QtCore.pyqtSignal(list)
    data2 = QtCore.pyqtSignal(list)

    def __init__(self, queryQ):
        super().__init__()
        self.log = logging.getLogger('Worker')
        self.log.setLevel(logging.INFO)
        filehandler = logging.FileHandler(filename=f"{system_path}/log/{strf_time('%Y%m%d')}.txt", encoding='utf-8')
        self.log.addHandler(filehandler)
        self.queryQ = queryQ

        self.upbit = None
        self.tickers = None
        self.buy_uuid = None
        self.sell_uuid = None
        self.str_today = None
        self.df_cj = pd.DataFrame(columns=columns_cj)
        self.df_jg = pd.DataFrame(columns=columns_jg)
        self.df_tj = pd.DataFrame(columns=columns_tj)
        self.df_td = pd.DataFrame(columns=columns_td)
        self.df_tt = pd.DataFrame(columns=columns_tt)
        self.dict_gj = {}  # key: ticker, value: list
        self.dict_intg = {
            '예수금': 0,
            '추정예수금': 0,
            '종목당투자금': 0
        }
        self.dict_bool = {
            '모의모드': True
        }
        self.dict_time = {
            '관심종목': now(),
            '거래정보': now(),
            '부가정보': now()
        }

    def run(self):
        self.GetKey()
        self.GetBalances()
        self.GetVolatility()
        self.Loop()

    def GetKey(self):
        f = open(f'{system_path}/user.txt')
        lines = f.readlines()
        access_key = lines[0].strip()
        secret_key = lines[1].strip()
        f.close()
        self.upbit = pyupbit.Upbit(access_key, secret_key)

    def GetBalances(self):
        if self.dict_bool['모의모드']:
            self.dict_intg['예수금'] = 100000000
            self.dict_intg['추정예수금'] = self.dict_intg['예수금']
            self.dict_intg['종목당투자금'] = int(self.dict_intg['예수금'] / 3)
        else:
            self.dict_intg['예수금'] = int(float(self.upbit.get_balances()[0]['balance']))
            self.dict_intg['추정예수금'] = self.dict_intg['예수금']
            self.dict_intg['종목당투자금'] = int(self.dict_intg['예수금'] / 3)

    def GetVolatility(self):
        tickers = pyupbit.get_tickers(fiat="KRW")
        count = len(tickers)
        for i, ticker in enumerate(tickers):
            time.sleep(0.2)
            df = pyupbit.get_ohlcv(ticker)
            if df['close'][-2] >= df['close'][-3] * 1.25 or ticker in self.df_jg.index:
                c = df['close'][-1]
                o = df['open'][-1]
                h = df['high'][-1]
                low = df['low'][-1]
                v = int(df['volume'][-1])
                c1 = df['close'][-2]
                o1 = df['open'][-2]
                h1 = df['high'][-2]
                l1 = df['low'][-2]
                c2 = df['close'][-3]
                o2 = df['open'][-3]
                h2 = df['high'][-3]
                l2 = df['low'][-3]
                k = round((abs(c2 - o2) / (h2 - l2) + abs(c1 - o1) / (h1 - l1)) / 2, 2)
                k = round((h1 - l1) * k, 2)
                self.dict_gj[ticker] = [c, o, h, low, v, k]
            if i == count - 1:
                d = str(df.index[-1])
                d = d[:4] + d[5:7] + d[8:10]
                self.str_today = d
            self.log.info(f'[{now()}] 일봉 데이터 다운로드 중 ... {i + 1}/{count}')
            self.data2.emit([0, f'일봉 데이터 다운로드 중 ... {i + 1}/{count}'])
        self.tickers = list(self.dict_gj.keys())

    def Loop(self):
        webq = WebSocketManager('ticker', self.tickers)
        while True:
            data = webq.get()
            ticker = data['code']
            prec = self.dict_gj[ticker][0]
            c = data['trade_price']
            o = data['opening_price']
            h = data['high_price']
            low = data['low_price']
            v = int(data['acc_trade_volume'])
            k = self.dict_gj[ticker][-1]
            d = data['trade_date']
            t = data['trade_time']

            if d != self.str_today:
                webq.terminate()
                self.GetVolatility()
                webq = WebSocketManager('ticker', self.tickers)
                self.df_cj = pd.DataFrame(columns=columns_cj)
                self.df_td = pd.DataFrame(columns=columns_td)

            if prec != c:
                self.dict_gj[ticker][:5] = c, o, h, low, v
                if c >= o + k > prec and ticker not in self.df_td.index:
                    self.Buy(ticker, c, d, t)
                if c <= o - k < prec and ticker in self.df_jg.index and ticker not in list(self.df_cj['종목명'].values):
                    self.Sell(ticker, c, d, t)

            if not self.dict_bool['모의모드']:
                if self.buy_uuid is not None and ticker == self.buy_uuid[0]:
                    ret = self.upbit.get_order(self.buy_uuid[1])
                    if ret is not None and ret['state'] == 'done':
                        cp = ret['price']
                        cc = ret['executed_volume']
                        self.UpdateBuy(ticker, cp, cc, d, t)
                        self.buy_uuid = None
                if self.sell_uuid is not None and ticker == self.sell_uuid[0]:
                    ret = self.upbit.get_order(self.sell_uuid[1])
                    if ret is not None and ret['state'] == 'done':
                        cp = ret['price']
                        cc = ret['executed_volume']
                        self.UpdateSell(ticker, cp, cc, d, t)
                        self.sell_uuid = None

            if now() > self.dict_time['거래정보']:
                self.UpdateTotaljango()
                self.dict_time['거래정보'] = timedelta_sec(1)
            if now() > self.dict_time['관심종목']:
                self.data1.emit([ui_num['관심종목'], self.dict_gj])
                self.dict_time['관심종목'] = timedelta_sec(1)
            if now() > self.dict_time['부가정보']:
                self.data2.emit([1, '부가정보업데이트'])
                self.dict_time['부가정보'] = timedelta_sec(2)

    def Buy(self, ticker, c, d, t):
        oc = int(self.dict_intg['종목당투자금'] / c)
        if oc == 0:
            return

        if self.dict_bool['모의모드']:
            self.UpdateBuy(ticker, c, oc, d, t)
        else:
            ret = self.upbit.buy_market_order(ticker, self.dict_intg['종목당투자금'])
            self.buy_uuid = [ticker, ret[0]['uuid']]

    def Sell(self, ticker, c, d, t):
        oc = self.df_jg['보유수량'][ticker]
        if self.dict_bool['모의모드']:
            self.UpdateSell(ticker, c, oc, d, t)
        else:
            ret = self.upbit.sell_market_order(ticker, oc)
            self.sell_uuid = [ticker, ret[0]['uuid']]

    def UpdateBuy(self, ticker, c, oc, d, t):
        bg = oc * c
        pg, sg, sp = self.GetPgSgSp(bg, oc * c)
        self.dict_intg['예수금'] -= bg
        self.df_jg.at[ticker] = ticker, c, c, sp, sg, bg, pg, oc
        self.df_cj.at[d + t] = ticker, '매수', oc, 0, c, c, t
        self.data0.emit([ui_num['체결목록'], self.df_cj])
        self.log.info(f'[{now()}] 매매 시스템 체결 알림 - {ticker} {oc}코인 매수')
        self.data2.emit([0, f'매매 시스템 체결 알림 - {ticker} {oc}코인 매수'])

    def UpdateSell(self, ticker, c, oc, d, t):
        bp = self.df_jg['매입가'][ticker]
        bg = bp * c
        pg, sg, sp = self.GetPgSgSp(bg, oc * c)
        self.dict_intg['예수금'] += bg + sg
        self.df_jg.drop(index=ticker, inplace=True)
        self.df_cj.at[d + t] = ticker, '매도', oc, 0, c, c, t
        self.df_td.at[d + t] = ticker, bg, pg, oc, sp, sg, t
        tsg = self.df_td['매도금액'].sum()
        tbg = self.df_td['매수금액'].sum()
        tsig = self.df_td[self.df_td['수익금'] > 0]['수익금'].sum()
        tssg = self.df_td[self.df_td['수익금'] < 0]['수익금'].sum()
        sg = self.df_td['수익금'].sum()
        sp = round(sg / tbg * 100, 2)
        tdct = len(self.df_td)
        self.df_tt = pd.DataFrame([[tdct, tbg, tsg, tsig, tssg, sp, sg]], columns=columns_tt, index=[d])
        self.data0.emit([ui_num['체결목록'], self.df_cj])
        self.data0.emit([ui_num['거래목록'], self.df_td])
        self.data0.emit([ui_num['거래합계'], self.df_tt])
        self.log.info(f'[{now()}] 매매 시스템 체결 알림 - {ticker} {bp}코인 매도')
        self.data2.emit([0, f'매매 시스템 체결 알림 - {ticker} {bp}코인 매도'])

    # noinspection PyMethodMayBeStatic
    def GetPgSgSp(self, bg, cg):
        sfee = cg * 0.0005
        bfee = bg * 0.0005
        pg = int(cg - sfee - bfee)
        sg = pg - bg
        sp = round(sg / bg * 100, 2)
        return pg, sg, sp

    def UpdateTotaljango(self):
        if len(self.df_jg) > 0:
            tsg = self.df_jg['평가손익'].sum()
            tbg = self.df_jg['매입금액'].sum()
            tpg = self.df_jg['평가금액'].sum()
            bct = len(self.df_jg)
            tsp = round(tsg / tbg * 100, 2)
            ttg = self.dict_intg['예수금'] + tpg
            self.df_tj.at[self.str_today] = ttg, self.dict_intg['예수금'], bct, tsp, tsg, tbg, tpg
        else:
            self.df_tj.at[self.str_today] = self.dict_intg['예수금'], self.dict_intg['예수금'], 0, 0.0, 0, 0, 0
        self.data0.emit([ui_num['잔고목록'], self.df_jg])
        self.data0.emit([ui_num['잔고평가'], self.df_tj])
