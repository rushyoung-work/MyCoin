import os
import sys
import psutil
from static import *
from setting import *
from query import Query
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette
from multiprocessing import Queue, Process
from worker import Worker


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        def setPushbutton(name, groupbox, buttonclicked, cmd=None):
            pushbutton = QtWidgets.QPushButton(name, groupbox)
            pushbutton.setStyleSheet(style_bc_bt)
            pushbutton.setFont(qfont12)
            if cmd is not None:
                pushbutton.clicked.connect(lambda: buttonclicked(cmd))
            else:
                pushbutton.clicked.connect(lambda: buttonclicked(name))
            return pushbutton

        def setTablewidget(tab, columns, colcount, rowcount):
            tableWidget = QtWidgets.QTableWidget(tab)
            tableWidget.verticalHeader().setDefaultSectionSize(23)
            tableWidget.verticalHeader().setVisible(False)
            tableWidget.setAlternatingRowColors(True)
            tableWidget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
            tableWidget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            tableWidget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            tableWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            tableWidget.setColumnCount(len(columns))
            tableWidget.setRowCount(rowcount)
            tableWidget.setHorizontalHeaderLabels(columns)
            if colcount >= 7 and columns[-1] == '변동성':
                tableWidget.setColumnWidth(0, 126)
                tableWidget.setColumnWidth(1, 80)
                tableWidget.setColumnWidth(2, 80)
                tableWidget.setColumnWidth(3, 80)
                tableWidget.setColumnWidth(4, 80)
                tableWidget.setColumnWidth(5, 130)
                tableWidget.setColumnWidth(6, 90)
            elif colcount >= 7:
                tableWidget.setColumnWidth(0, 126)
                tableWidget.setColumnWidth(1, 90)
                tableWidget.setColumnWidth(2, 90)
                tableWidget.setColumnWidth(3, 90)
                tableWidget.setColumnWidth(4, 90)
                tableWidget.setColumnWidth(5, 90)
                tableWidget.setColumnWidth(6, 90)
            if colcount >= 8:
                tableWidget.setColumnWidth(7, 90)
            return tableWidget

        self.setFont(qfont12)
        self.setWindowFlags(Qt.FramelessWindowHint)

        self.table_tabWidget = QtWidgets.QTabWidget(self)
        self.td_tab = QtWidgets.QWidget()
        self.st_tab = QtWidgets.QWidget()
        self.sg_tab = QtWidgets.QWidget()

        self.tt_tableWidget = setTablewidget(self.td_tab, columns_tt, len(columns_tt), 1)
        self.td_tableWidget = setTablewidget(self.td_tab, columns_td, len(columns_td), 13)
        self.tj_tableWidget = setTablewidget(self.td_tab, columns_tj, len(columns_tj), 1)
        self.jg_tableWidget = setTablewidget(self.td_tab, columns_jg, len(columns_jg), 13)
        self.cj_tableWidget = setTablewidget(self.td_tab, columns_cj, len(columns_cj), 12)
        self.gj_tableWidget = setTablewidget(self.td_tab, columns_gj, len(columns_gj), 12)

        self.st_groupBox = QtWidgets.QGroupBox(self.st_tab)
        self.calendarWidget = QtWidgets.QCalendarWidget(self.st_groupBox)
        todayDate = QtCore.QDate.currentDate()
        self.calendarWidget.setCurrentPage(todayDate.year(), todayDate.month())
        self.calendarWidget.clicked.connect(self.CalendarClicked)
        self.stn_tableWidget = setTablewidget(self.st_tab, columns_sn, len(columns_sn), 1)
        self.stl_tableWidget = setTablewidget(self.st_tab, columns_st, len(columns_st), 44)

        self.sg_groupBox = QtWidgets.QGroupBox(self.sg_tab)
        self.sg_pushButton_01 = setPushbutton('일별집계', self.sg_groupBox, self.ButtonClicked)
        self.sg_pushButton_02 = setPushbutton('월별집계', self.sg_groupBox, self.ButtonClicked)
        self.sg_pushButton_03 = setPushbutton('연도별집계', self.sg_groupBox, self.ButtonClicked)
        self.sgt_tableWidget = setTablewidget(self.sg_tab, columns_ln, len(columns_ln), 1)
        self.sgl_tableWidget = setTablewidget(self.sg_tab, columns_lt, len(columns_lt), 54)

        self.table_tabWidget.addTab(self.td_tab, '계좌평가')
        self.table_tabWidget.addTab(self.st_tab, '거래목록')
        self.table_tabWidget.addTab(self.sg_tab, '수익현황')

        self.info_label = QtWidgets.QLabel(self)

        self.setGeometry(2056, 0, 692, 1400)
        self.table_tabWidget.setGeometry(5, 5, 682, 1390)
        self.info_label.setGeometry(220, 1, 400, 30)

        self.tt_tableWidget.setGeometry(5, 5, 668, 42)
        self.td_tableWidget.setGeometry(5, 52, 668, 320)
        self.tj_tableWidget.setGeometry(5, 377, 668, 42)
        self.jg_tableWidget.setGeometry(5, 424, 668, 320)
        self.cj_tableWidget.setGeometry(5, 749, 668, 320)
        self.gj_tableWidget.setGeometry(5, 1074, 668, 282)

        self.st_groupBox.setGeometry(5, 3, 668, 278)
        self.calendarWidget.setGeometry(5, 11, 658, 258)
        self.stn_tableWidget.setGeometry(5, 287, 668, 42)
        self.stl_tableWidget.setGeometry(5, 334, 668, 1022)

        self.sg_groupBox.setGeometry(5, 3, 668, 48)
        self.sg_pushButton_01.setGeometry(5, 11, 216, 30)
        self.sg_pushButton_02.setGeometry(226, 12, 216, 30)
        self.sg_pushButton_03.setGeometry(447, 12, 216, 30)
        self.sgt_tableWidget.setGeometry(5, 57, 668, 42)
        self.sgl_tableWidget.setGeometry(5, 104, 668, 1252)

        self.info = [0., 0, 0.]

        self.writer = Worker(queryQ)
        self.writer.data0.connect(self.UpdateTablewidget)
        self.writer.data1.connect(self.UpdateGoansimjongmok)
        self.writer.data2.connect(self.UpdateInfo)
        self.writer.start()

    def UpdateGoansimjongmok(self, data):
        gsjm = data[1]

        def changeFormat(text):
            text = str(text)
            try:
                format_data = format(int(text), ',')
            except ValueError:
                format_data = format(float(text), ',')
                if len(format_data.split('.')) >= 2:
                    if len(format_data.split('.')[1]) == 1:
                        format_data += '0'
            return format_data

        tableWidget = self.gj_tableWidget
        if len(gsjm) == 0:
            tableWidget.clearContents()
            return

        tableWidget.setRowCount(len(gsjm))
        for j, ticker in enumerate(list(gsjm.keys())):
            item = QtWidgets.QTableWidgetItem(ticker)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            tableWidget.setItem(j, 0, item)
            for i in [0, 1, 2, 3, 4, 5]:
                if i < 5:
                    item = QtWidgets.QTableWidgetItem(changeFormat(gsjm[ticker][i]).split('.')[0])
                else:
                    item = QtWidgets.QTableWidgetItem(changeFormat(gsjm[ticker][i]))
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                tableWidget.setItem(j, i + 1, item)

        if len(gsjm) < 12:
            tableWidget.setRowCount(12)

    def UpdateTablewidget(self, data):
        gubun = data[0]
        df = data[1]

        def changeFormat(text):
            text = str(text)
            try:
                format_data = format(int(text), ',')
            except ValueError:
                format_data = format(float(text), ',')
                if len(format_data.split('.')) >= 2:
                    if len(format_data.split('.')[1]) == 1:
                        format_data += '0'
            return format_data

        tableWidget = None
        if gubun == ui_num['거래합계']:
            tableWidget = self.tt_tableWidget
        elif gubun == ui_num['거래목록']:
            tableWidget = self.td_tableWidget
        elif gubun == ui_num['잔고평가']:
            tableWidget = self.tj_tableWidget
        elif gubun == ui_num['잔고목록']:
            tableWidget = self.jg_tableWidget
        elif gubun == ui_num['체결목록']:
            tableWidget = self.cj_tableWidget
        elif gubun == ui_num['당일합계']:
            tableWidget = self.stn_tableWidget
        elif gubun == ui_num['당일상세']:
            tableWidget = self.stl_tableWidget
        elif gubun == ui_num['누적합계']:
            tableWidget = self.sgt_tableWidget
        elif gubun == ui_num['누적상세']:
            tableWidget = self.sgl_tableWidget
        if tableWidget is None:
            return

        if len(df) == 0:
            tableWidget.clearContents()
            return

        tableWidget.setRowCount(len(df))
        for j, index in enumerate(df.index):
            for i, column in enumerate(df.columns):
                if column == '체결시간':
                    cgtime = df[column][index]
                    cgtime = f'{cgtime[8:10]}:{cgtime[10:12]}:{cgtime[12:14]}'
                    item = QtWidgets.QTableWidgetItem(cgtime)
                elif column in ['거래일자', '일자']:
                    day = df[column][index]
                    if '.' not in day:
                        day = day[:4] + '.' + day[4:6] + '.' + day[6:]
                    item = QtWidgets.QTableWidgetItem(day)
                elif column in ['종목명', '기간']:
                    item = QtWidgets.QTableWidgetItem(str(df[column][index]))
                elif column != '수익률':
                    item = QtWidgets.QTableWidgetItem(changeFormat(df[column][index]).split('.')[0])
                else:
                    item = QtWidgets.QTableWidgetItem(changeFormat(df[column][index]))

                if column == '종목명':
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                elif column in ['거래횟수', '추정예탁자산', '추정예수금', '보유종목수', '주문구분',
                                '체결시간', '거래일자', '기간', '일자']:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)

                if '수익률' in df.columns:
                    if df['수익률'][index] >= 0:
                        item.setForeground(color_fg_bt)
                    else:
                        item.setForeground(color_fg_dk)
                elif gubun == ui_num['체결목록']:
                    if df['주문구분'][index] == '매수':
                        item.setForeground(color_fg_bt)
                    elif df['주문구분'][index] == '매도':
                        item.setForeground(color_fg_dk)
                    elif df['주문구분'][index] in ['매도취소', '매수취소']:
                        item.setForeground(color_fg_bc)
                tableWidget.setItem(j, i, item)

        if len(df) < 13 and gubun in [ui_num['거래목록'], ui_num['잔고목록'], ui_num['체결목록']]:
            tableWidget.setRowCount(13)
        elif len(df) < 44 and gubun == ui_num['당일상세']:
            tableWidget.setRowCount(44)
        elif len(df) < 54 and gubun == ui_num['누적상세']:
            tableWidget.setRowCount(54)

    def UpdateInfo(self, data):
        if data[0] == 0:
            self.info_label.setText(data[1])
        elif data[0] == 1:
            text = f'Process Info - Memory: {self.info[0]}MB, Thread: {self.info[1]}EA, CPU {self.info[2]}%'
            self.info_label.setText(text)
            self.GetInfo()

    @thread_decorator
    def GetInfo(self):
        p = psutil.Process(os.getpid())
        memory = round(p.memory_info()[0] / 2 ** 20.86, 2)
        thread = p.num_threads()
        cpu = round(p.cpu_percent(interval=2) / 2, 2)
        self.info = [memory, thread, cpu]

    def CalendarClicked(self):
        date = self.calendarWidget.selectedDate()
        searchday = date.toString('yyyyMMdd')
        con = sqlite3.connect(db_stg)
        df = pd.read_sql(f"SELECT * FROM tradelist WHERE 체결시간 LIKE '{searchday}%'", con)
        con.close()
        if len(df) > 0:
            df = df.set_index('index')
            df.sort_values(by=['체결시간'], ascending=True, inplace=True)
            df = df[['체결시간', '종목명', '매수금액', '매도금액', '주문수량', '수익률', '수익금']].copy()
            nbg, nsg = df['매수금액'].sum(), df['매도금액'].sum()
            sp = round((nsg / nbg - 1) * 100, 2)
            npg, nmg, nsig = df[df['수익금'] > 0]['수익금'].sum(), df[df['수익금'] < 0]['수익금'].sum(), df['수익금'].sum()
            df2 = pd.DataFrame(columns=columns_sn)
            df2.at[0] = searchday, nbg, nsg, npg, nmg, sp, nsig
        else:
            df = pd.DataFrame(columns=columns_st)
            df2 = pd.DataFrame(columns=columns_sn)
        self.UpdateTablewidget([ui_num['당일합계'], df2])
        self.UpdateTablewidget([ui_num['당일상세'], df])

    def ButtonClicked(self, cmd):
        if '집계' in cmd:
            con = sqlite3.connect(db_stg)
            df = pd.read_sql('SELECT * FROM totaltradelist', con)
            con.close()
            df = df[::-1]
            if len(df) > 0:
                sd = strp_time('%Y%m%d', df['index'][df.index[0]])
                ld = strp_time('%Y%m%d', df['index'][df.index[-1]])
                pr = str((sd - ld).days + 1) + '일'
                nbg, nsg = df['총매수금액'].sum(), df['총매도금액'].sum()
                sp = round((nsg / nbg - 1) * 100, 2)
                npg, nmg = df['총수익금액'].sum(), df['총손실금액'].sum()
                nsig = df['수익금합계'].sum()
                df2 = pd.DataFrame(columns=columns_ln)
                df2.at[0] = pr, nbg, nsg, npg, nmg, sp, nsig
                self.UpdateTablewidget([ui_num['누적합계'], df2])
            else:
                return
            if cmd == '일별집계':
                df = df.rename(columns={'index': '일자'})
                self.UpdateTablewidget([ui_num['누적상세'], df])
            elif cmd == '월별집계':
                df['일자'] = df['index'].apply(lambda x: x[:6])
                df2 = pd.DataFrame(columns=columns_lt)
                lastmonth = df['일자'][df.index[-1]]
                month = strf_time('%Y%m')
                while int(month) >= int(lastmonth):
                    df3 = df[df['일자'] == month]
                    if len(df3) > 0:
                        tbg, tsg = df3['총매수금액'].sum(), df3['총매도금액'].sum()
                        sp = round((tsg / tbg - 1) * 100, 2)
                        tpg, tmg = df3['총수익금액'].sum(), df3['총손실금액'].sum()
                        ttsg = df3['수익금합계'].sum()
                        df2.at[month] = month, tbg, tsg, tpg, tmg, sp, ttsg
                    month = str(int(month) - 89) if int(month[4:]) == 1 else str(int(month) - 1)
                self.UpdateTablewidget([ui_num['누적상세'], df2])
            elif cmd == '연도별집계':
                df['일자'] = df['index'].apply(lambda x: x[:4])
                df2 = pd.DataFrame(columns=columns_lt)
                lastyear = df['일자'][df.index[-1]]
                year = strf_time('%Y')
                while int(year) >= int(lastyear):
                    df3 = df[df['일자'] == year]
                    if len(df3) > 0:
                        tbg, tsg = df3['총매수금액'].sum(), df3['총매도금액'].sum()
                        sp = round((tsg / tbg - 1) * 100, 2)
                        tpg, tmg = df3['총수익금액'].sum(), df3['총손실금액'].sum()
                        ttsg = df3['수익금합계'].sum()
                        df2.at[year] = year, tbg, tsg, tpg, tmg, sp, ttsg
                    year = str(int(year) - 1)
                self.UpdateTablewidget([ui_num['누적상세'], df2])


if __name__ == '__main__':
    queryQ = Queue()
    Process(target=Query, args=(queryQ,)).start()
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('fusion')
    palette = QPalette()
    palette.setColor(QPalette.Window, color_bg_bc)
    palette.setColor(QPalette.Background, color_bg_bc)
    palette.setColor(QPalette.WindowText, color_fg_bc)
    palette.setColor(QPalette.Base, color_bg_bc)
    palette.setColor(QPalette.AlternateBase, color_bg_dk)
    palette.setColor(QPalette.Text, color_fg_bc)
    palette.setColor(QPalette.Button, color_bg_bc)
    palette.setColor(QPalette.ButtonText, color_fg_bc)
    palette.setColor(QPalette.Link, color_fg_bk)
    palette.setColor(QPalette.Highlight, color_fg_bk)
    palette.setColor(QPalette.HighlightedText, color_bg_bk)
    app.setPalette(palette)
    window = Window()
    window.show()
    app.exec_()
