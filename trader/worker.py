import time
import logging
import pyupbit
import pandas as pd
from PyQt5 import QtCore
from PyQt5.QtCore import QThread
from pyupbit import WebSocketManager
from setting import *
from static import now, timedelta_sec, strf_time, telegram_msg


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

        self.upbit = None                               # 매도수 주문 및 체결 확인용
        self.tickers = None                             # 관심종목 티커 리스트
        self.buy_uuid = None                            # 매수 주문용
        self.sell_uuid = None                           # 매도 주문용
        self.str_today = None                           # 당일 날짜
        self.df_cj = pd.DataFrame(columns=columns_cj)   # 체결목록
        self.df_jg = pd.DataFrame(columns=columns_jg)   # 잔고목록
        self.df_tj = pd.DataFrame(columns=columns_tj)   # 잔고평가
        self.df_td = pd.DataFrame(columns=columns_td)   # 거래목록
        self.df_tt = pd.DataFrame(columns=columns_tt)   # 실현손익
        self.dict_gj = {}                               # 관심종목 key: ticker, value: list
        self.dict_intg = {
            '예수금': 0,
            '종목당투자금': 0,                            # 종목당 투자금은 int(예수금 / 최대매수종목수)로 계산
            '전일등락율': 9,
            '최대매수종목수': 5,
            '업비트수수료': 0.                            # 0.5% 일경우 0.005로 입력
        }
        self.dict_bool = {
            '모의모드': True                             # 모의모드 False 상태시만 주문 전송
        }
        self.dict_time = {
            '체결확인': now(),
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
        """ user.txt 파일에서 업비트 access 키와 secret 키를 읽어 self.upbit 객체 생성 """
        f = open('user.txt')
        lines = f.readlines()
        access_key = lines[0].strip()
        secret_key = lines[1].strip()
        f.close()
        self.upbit = pyupbit.Upbit(access_key, secret_key)

    def GetBalances(self):
        """ 예수금 조회 및 종목당투자금 계산 """
        if self.dict_bool['모의모드']:
            self.dict_intg['예수금'] = 100000000
        else:
            self.dict_intg['예수금'] = int(float(self.upbit.get_balances()[0]['balance']))
        self.dict_intg['종목당투자금'] = int(self.dict_intg['예수금'] / self.dict_intg['최대매수종목수'])

    def GetVolatility(self):
        """
        전체 티커의 일봉을 조회하여 시가 및 변동성 계산, 날짜 변경 시 마다 실행된다.
        전날 등락율 조건을 만족한 종목과 잔고목록 종목만 관심종목으로 등록된다.
        """
        tickers = pyupbit.get_tickers(fiat="KRW")
        count = len(tickers)
        for i, ticker in enumerate(tickers):
            time.sleep(0.2)
            df = pyupbit.get_ohlcv(ticker)
            if df['close'][-2] >= df['close'][-3] * (1 + self.dict_intg['전일등락율'] / 100) or \
                    ticker in self.df_jg.index:
                c2, c1, c = df['close'][-3:]
                o2, o1, o = df['open'][-3:]
                h2, h1, h = df['high'][-3:]
                l2, l1, low = df['low'][-3:]
                v = int(df['volume'][-1])
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
            c = data['trade_price']
            o = data['opening_price']
            h = data['high_price']
            low = data['low_price']
            v = int(data['acc_trade_volume'])
            d = data['trade_date']
            t = data['trade_time']
            prec = self.dict_gj[ticker][0]
            k = self.dict_gj[ticker][-1]

            if d != self.str_today:
                """
                날짜 변경시 실시간 데이터 수신용 웹소켓큐 제거
                변동성 재계산
                웹소켓큐 생성
                전일실현손익 저장
                체결목록 및 거래목록 초기화
                """
                webq.terminate()
                self.GetVolatility()
                webq = WebSocketManager('ticker', self.tickers)
                self.queryQ.put([self.df_tt, 'totaltradelist', 'append'])
                self.df_cj = pd.DataFrame(columns=columns_cj)
                self.df_td = pd.DataFrame(columns=columns_td)
                telegram_msg('관심종목 및 거래정보를 업데이트하였습니다.')
            elif prec != c:
                """
                현재가가 직전 현재가와 다를 경우만 전략 연산 실행
                매도수 로직이 유사한 형태이므로 매수 시에는 당일 거래목록에 없어야하며
                매도 시에는 당일 체결목록에 없어야한다.
                당일 매수한 종목을 매도하지 아니하고 당일 매도한 종목을 매수하지 않기 위함이다.
                """
                self.dict_gj[ticker][:5] = c, o, h, low, v
                if c >= o + k > prec and self.buy_uuid is None and \
                        ticker not in self.df_jg.index and ticker not in self.df_td.index:
                    self.Buy(ticker, c, d, t)
                if c <= o - k < prec and self.sell_uuid is None and \
                        ticker in self.df_jg.index and ticker not in list(self.df_cj['종목명'].values):
                    self.Sell(ticker, c, d, t)

            """
            체결확인, 거래정보, 관심종목 정보는 1초마다 확인 및 갱신되며
            프로세스 정보가 담긴 부가정보는 2초마다 갱신된다.
            """
            if not self.dict_bool['모의모드'] and now() > self.dict_time['체결확인']:
                self.CheckChegeol(ticker, d, t)
                self.dict_time['체결확인'] = timedelta_sec(1)
            if now() > self.dict_time['거래정보']:
                self.UpdateTotaljango()
                self.dict_time['거래정보'] = timedelta_sec(1)
            if now() > self.dict_time['관심종목']:
                self.data1.emit([ui_num['관심종목'], self.dict_gj])
                self.dict_time['관심종목'] = timedelta_sec(1)
            if now() > self.dict_time['부가정보']:
                self.data2.emit([1, '부가정보업데이트'])
                self.dict_time['부가정보'] = timedelta_sec(2)

    """
    모의모드 시 실제 매도수 주문을 전송하지 않고 바로 체결목록, 잔고목록 등을 갱신한다.
    실매매 시 매도수 아이디 및 티커명을 매도, 매수 구분하여 변수에 저장하고
    해당 변수값이 None이 아닐 경우 get_order 함수로 체결확인을 1초마다 반복실행한다.
    체결이 완료되면 관련목록을 갱신하고 DB에 기록되며 매도수 아이디 및 티커명을 저장한 변수값이 다시 None으로 변경된다.     
    """

    def Buy(self, ticker, c, d, t):
        oc = int(self.dict_intg['종목당투자금'] / c)
        if oc == 0:
            return

        if self.dict_bool['모의모드']:
            self.UpdateBuy(ticker, c, oc, d, t)
        else:
            ret = self.upbit.buy_market_order(ticker, self.dict_intg['종목당투자금'])
            self.buy_uuid = [ticker, ret[0]['uuid']]
            self.dict_time['체결확인'] = timedelta_sec(1)

    def Sell(self, ticker, cc, d, t):
        oc = self.df_jg['보유수량'][ticker]
        if self.dict_bool['모의모드']:
            self.UpdateSell(ticker, cc, oc, d, t)
        else:
            ret = self.upbit.sell_market_order(ticker, oc)
            self.sell_uuid = [ticker, ret[0]['uuid']]
            self.dict_time['체결확인'] = timedelta_sec(1)

    def CheckChegeol(self, ticker, d, t):
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

    def UpdateBuy(self, ticker, cc, oc, d, t):
        bg = oc * cc
        pg, sg, sp = self.GetPgSgSp(bg, oc * cc)
        self.dict_intg['예수금'] -= bg
        self.df_jg.at[ticker] = ticker, cc, cc, sp, sg, bg, pg, oc
        self.df_cj.at[d + t] = ticker, '매수', oc, 0, cc, cc, d + t

        self.data0.emit([ui_num['체결목록'], self.df_cj])
        self.log.info(f'[{now()}] 매매 시스템 체결 알림 - {ticker} {oc}코인 매수')
        self.data2.emit([0, f'매매 시스템 체결 알림 - {ticker} {oc}코인 매수'])
        telegram_msg(f'매수 알림 - {ticker} {cc} {oc}')

        df = pd.DataFrame([[ticker, '매수', oc, 0, cc, cc, d + t]], columns=columns_cj, index=[d + t])
        self.queryQ.put([df, 'chegeollist', 'append'])
        self.queryQ.put([self.df_jg, 'jangolist', 'replace'])

    def UpdateSell(self, ticker, cc, oc, d, t):
        bp = self.df_jg['매입가'][ticker]
        bg = bp * cc
        pg, sg, sp = self.GetPgSgSp(bg, oc * cc)
        self.dict_intg['예수금'] += bg + sg
        self.df_jg.drop(index=ticker, inplace=True)
        self.df_cj.at[d + t] = ticker, '매도', oc, 0, cc, cc, d + t
        self.df_td.at[d + t] = ticker, bg, pg, oc, sp, sg, d + t
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
        telegram_msg(f'매도 알림 - {ticker} {cc} {bp}')
        telegram_msg(f'손익 알림 - 총매수금액 {tbg}, 총매도금액{tsg}, 수익 {tsig}, 손실 {tssg}, 수익급합계 {sg}')

        df = pd.DataFrame([[ticker, '매도', oc, 0, cc, cc, d + t]], columns=columns_cj, index=[d + t])
        self.queryQ.put([df, 'chegeollist', 'append'])
        df = pd.DataFrame([[ticker, bp, cc, oc, sp, sg, d + t]], columns=columns_td, index=[d + t])
        self.queryQ.put([df, 'tradelist', 'append'])

    # noinspection PyMethodMayBeStatic
    def GetPgSgSp(self, bg, cg):
        sfee = cg * self.dict_intg['업비트수수료']
        bfee = bg * self.dict_intg['업비트수수료']
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
