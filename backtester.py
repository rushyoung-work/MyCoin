import sqlite3
import pyupbit
import datetime
import pandas as pd
from matplotlib import pyplot as plt


class BackTesterCoin:
    def __init__(self):
        columns = ['거래횟수', '평균보유기간', '익절', '손절', '승률', '수익률', '수익금']
        self.df_back = pd.DataFrame(columns=columns)
        self.df_tsg = pd.DataFrame(columns=['ticker', 'ttsg'])

        self.batting = 1000000
        self.preper = 10
        self.ticker = None
        self.df = None

        self.totalcount = 0
        self.totalcount_p = 0
        self.totalcount_m = 0
        self.totalholdday = 0
        self.totaleyun = 0
        self.totalper = 0.

        self.hold = False
        self.buycount = 0
        self.buyprice = 0
        self.sellprice = 0
        self.index = 0
        self.indexb = 0
        self.indexn = 0

        self.Start()

    def Start(self):
        tickers = pyupbit.get_tickers(fiat="KRW")
        tcount = len(tickers)
        for k, ticker in enumerate(tickers):
            self.ticker = ticker
            self.df = pyupbit.get_ohlcv(ticker, count=2000)
            self.df['고가저가폭'] = self.df['high'] - self.df['low']
            self.df['종가시가폭'] = self.df['close'] - self.df['open']
            self.df[['종가시가폭']] = self.df[['종가시가폭']].abs()
            self.df['돌파계수'] = self.df['종가시가폭'] / self.df['고가저가폭']
            self.df[['돌파계수']] = self.df[['돌파계수']].astype(float).round(2)
            self.df['평균돌파계수'] = self.df['돌파계수'].rolling(window=20).mean()
            self.df[['평균돌파계수']] = self.df[['평균돌파계수']].round(2)
            self.totalcount = 0
            self.totalcount_p = 0
            self.totalcount_m = 0
            self.totalholdday = 0
            self.totaleyun = 0
            self.totalper = 0.
            lasth = len(self.df) - 1
            for h, index in enumerate(list(self.df.index)):
                self.index = index
                self.indexn = h
                if not self.hold and self.BuyTerm():
                    self.Buy()
                elif self.hold and self.SellTerm():
                    self.Sell()
                if self.hold and h == lasth:
                    self.Sell()
            self.Report(k + 1, tcount)

        if len(self.df_back) > 0:
            tc = self.df_back['거래횟수'].sum()
            if tc != 0:
                pc = self.df_back['익절'].sum()
                mc = self.df_back['손절'].sum()
                pper = round(pc / tc * 100, 2)
                df_back_ = self.df_back[self.df_back['평균보유기간'] != 0]
                avghold = round(df_back_['평균보유기간'].sum() / len(df_back_), 2)
                avgsp = round(self.df_back['수익률'].sum() / tc, 2)
                tsg = int(self.df_back['수익금'].sum())
                onedaycount = round(tc / len(self.df_back), 2)
                onegm = int(self.batting * onedaycount * avghold)
                tsp = round(tsg / onegm * 100, 2)
                text = f" 종목당 배팅금액 {format(self.batting, ',')}원, 필요자금 {format(onegm, ',')}원, "\
                       f" 종목출현빈도수 {onedaycount}개/일, 거래횟수 {tc}회, 평균보유기간 {avghold}일, 익절 {pc}회, "\
                       f" 손절 {mc}회, 승률 {pper}%, 평균수익률 {avgsp}%, 수익률합계 {tsp}%, 수익금합계 {format(tsg, ',')}원"
                print(text)
                conn = sqlite3.connect('backtest.db')
                self.df_back.to_sql('ticker', conn, if_exists='replace', chunksize=1000)
                conn.close()

        if len(self.df_tsg) > 0:
            self.df_tsg['day'] = list(self.df_tsg.index)
            self.df_tsg['day'] = self.df_tsg['day'].apply(lambda x: str(x)[:10].strip('-'))
            self.df_tsg.sort_values(by=['day'], inplace=True)
            self.df_tsg = self.df_tsg.set_index('day')
            self.df_tsg['ttsg_cumsum'] = self.df_tsg['ttsg'].cumsum()
            self.df_tsg[['ttsg', 'ttsg_cumsum']] = self.df_tsg[['ttsg', 'ttsg_cumsum']].astype(int)
            conn = sqlite3.connect('backtest.db')
            self.df_tsg.to_sql('day', conn, if_exists='replace', chunksize=1000)
            conn.close()
            self.df_tsg.plot(figsize=(12, 9), rot=45)
            plt.savefig('coin.png')
            plt.show()

    def BuyTerm(self):
        # 전략 비공개
        return False

    def Buy(self):
        k = self.df['고가저가폭'][self.indexn - 1] * self.df['평균돌파계수'][self.indexn - 1]
        bp = self.df['open'][self.index] + k
        self.buycount = int(self.batting / bp)
        if self.buycount == 0:
            return
        self.buyprice = bp
        self.indexb = self.indexn
        self.hold = True

    def SellTerm(self):
        # 전략 비공개
        return False

    def Sell(self):
        self.hold = False
        self.CalculationEyun()

    def CalculationEyun(self):
        self.totalcount += 1
        bg = self.buycount * self.buyprice
        cg = self.buycount * self.sellprice
        eyun, per = self.GetEyunPer(bg, cg)
        holdday = self.indexn - self.indexb
        self.totalper = round(self.totalper + per, 2)
        self.totaleyun = int(self.totaleyun + eyun)
        self.totalholdday += holdday
        if per > 0:
            self.totalcount_p += 1
        else:
            self.totalcount_m += 1
        if self.index in self.df_tsg.index:
            name = self.df_tsg['ticker'][self.index] + ';' + self.ticker
            self.df_tsg.at[self.index] = name, self.df_tsg['ttsg'][self.index] + eyun
        else:
            self.df_tsg.at[self.index] = self.ticker, eyun

    # noinspection PyMethodMayBeStatic
    def GetEyunPer(self, bg, cg):
        gtexs = cg * 0.0023
        gsfee = cg * 0.00015
        gbfee = bg * 0.00015
        texs = gtexs - (gtexs % 1)
        sfee = gsfee - (gsfee % 10)
        bfee = gbfee - (gbfee % 10)
        pg = int(cg - texs - sfee - bfee)
        eyun = pg - bg
        per = round(eyun / bg * 100, 2)
        return eyun, per

    def Report(self, count, tcount):
        if self.totalcount > 0:
            plus_per = round((self.totalcount_p / self.totalcount) * 100, 2)
            avgholdday = round(self.totalholdday / self.totalcount, 2)
            self.df_back.at[self.ticker] = self.totalcount, avgholdday, self.totalcount_p, self.totalcount_m, \
                plus_per, self.totalper, self.totaleyun
            ticker, totalcount, avgholdday, totalcount_p, totalcount_m, plus_per, totalper, totaleyun = \
                self.GetTotal(plus_per, avgholdday)
            print(f" {ticker} | 평균보유기간 {avgholdday}일 | 거래횟수 {totalcount}회 | "
                  f" 익절 {totalcount_p}회 | 손절 {totalcount_m}회 | 승률 {plus_per}% |"
                  f" 수익률 {totalper}% | 수익금 {totaleyun}원 [{count}/{tcount}]")
        else:
            self.df_back.at[self.ticker] = 0, 0, 0, 0, 0., 0., 0

    def GetTotal(self, plus_per, avgholdday):
        ticker = str(self.ticker)
        ticker = ticker + '    ' if len(ticker) == 6 else ticker
        ticker = ticker + '   ' if len(ticker) == 7 else ticker
        ticker = ticker + '  ' if len(ticker) == 8 else ticker
        ticker = ticker + ' ' if len(ticker) == 9 else ticker
        totalcount = str(self.totalcount)
        totalcount = '  ' + totalcount if len(totalcount) == 1 else totalcount
        totalcount = ' ' + totalcount if len(totalcount) == 2 else totalcount
        avgholdday = str(avgholdday)
        avgholdday = '  ' + avgholdday if len(avgholdday.split('.')[0]) == 1 else avgholdday
        avgholdday = ' ' + avgholdday if len(avgholdday.split('.')[0]) == 2 else avgholdday
        avgholdday = avgholdday + '0' if len(avgholdday.split('.')[1]) == 1 else avgholdday
        totalcount_p = str(self.totalcount_p)
        totalcount_p = '  ' + totalcount_p if len(totalcount_p) == 1 else totalcount_p
        totalcount_p = ' ' + totalcount_p if len(totalcount_p) == 2 else totalcount_p
        totalcount_m = str(self.totalcount_m)
        totalcount_m = '  ' + totalcount_m if len(totalcount_m) == 1 else totalcount_m
        totalcount_m = ' ' + totalcount_m if len(totalcount_m) == 2 else totalcount_m
        plus_per = str(plus_per)
        plus_per = '  ' + plus_per if len(plus_per.split('.')[0]) == 1 else plus_per
        plus_per = ' ' + plus_per if len(plus_per.split('.')[0]) == 2 else plus_per
        plus_per = plus_per + '0' if len(plus_per.split('.')[1]) == 1 else plus_per
        totalper = str(self.totalper)
        totalper = '   ' + totalper if len(totalper.split('.')[0]) == 1 else totalper
        totalper = '  ' + totalper if len(totalper.split('.')[0]) == 2 else totalper
        totalper = ' ' + totalper if len(totalper.split('.')[0]) == 3 else totalper
        totalper = totalper + '0' if len(totalper.split('.')[1]) == 1 else totalper
        totaleyun = format(self.totaleyun, ',')
        if len(totaleyun.split(',')) == 1:
            totaleyun = '         ' + totaleyun if len(totaleyun.split(',')[0]) == 1 else totaleyun
            totaleyun = '        ' + totaleyun if len(totaleyun.split(',')[0]) == 2 else totaleyun
            totaleyun = '       ' + totaleyun if len(totaleyun.split(',')[0]) == 3 else totaleyun
            totaleyun = '      ' + totaleyun if len(totaleyun.split(',')[0]) == 4 else totaleyun
        elif len(totaleyun.split(',')) == 2:
            totaleyun = '     ' + totaleyun if len(totaleyun.split(',')[0]) == 1 else totaleyun
            totaleyun = '    ' + totaleyun if len(totaleyun.split(',')[0]) == 2 else totaleyun
            totaleyun = '   ' + totaleyun if len(totaleyun.split(',')[0]) == 3 else totaleyun
            totaleyun = '  ' + totaleyun if len(totaleyun.split(',')[0]) == 4 else totaleyun
        elif len(totaleyun.split(',')) == 3:
            totaleyun = ' ' + totaleyun if len(totaleyun.split(',')[0]) == 1 else totaleyun
        return ticker, totalcount, avgholdday, totalcount_p, totalcount_m, plus_per, totalper, totaleyun


if __name__ == "__main__":
    start = datetime.datetime.now()
    BackTesterCoin()
    end = datetime.datetime.now()
    print(f" 백테스팅 소요시간 {end - start}")
