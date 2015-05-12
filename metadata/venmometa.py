from datetime import datetime, timedelta, date
from itertools import groupby

import pymongo
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

CLIENT = pymongo.MongoClient('localhost', 27017)
DB = CLIENT['venmo']
TRANS_COLLECTION = DB['trans']
TRANS_COLLECTION.create_index([('created_time', pymongo.ASCENDING)])

date_keyfunc = lambda tran: datetime.strptime(tran.get('created_time'), '%Y-%m-%dT%H:%M:%SZ').date()


def trans_iter():
    return TRANS_COLLECTION.find().sort('created_time', pymongo.ASCENDING)


def graph_daily_trans():
    trans_by_date = {}
    for key, group in groupby(trans_iter(), date_keyfunc):
        trans_by_date[key] = len(list(group))

    dates = sorted(trans_by_date.keys())
    min_date, max_date = min(dates), max(dates)
    one_day = timedelta(days=1)
    all_dates = [min_date + (i * one_day) for i in range((max_date - min_date).days)]

    tran_counts = [trans_by_date.get(day, 0) for day in all_dates]
    print 'Total dates: %d' % len(dates)
    print 'Total counts: %d' % len(tran_counts)
    print 'Between %s and %s' % (min_date, max_date)
    total_trans = sum(tran_counts)
    print 'Total trans: %d' % total_trans

    plot_trans(all_dates, tran_counts, None, sns.color_palette("Paired", 8))


def plot_trans(dates, tran_counts, cumulative_trans, pallette):
    fig, axes = plt.subplots(1, figsize=(16, 10))
    # fig, axes = plt.subplots(1)

    # Trans count plot
    axes.plot(dates, tran_counts, color=pallette[1], lw=0.2, label='Transactions')
    axes.fill_between(dates, 0, tran_counts, facecolor=pallette[0], alpha=0.8)

    # Labels and axes formatting
    axes.set_title('Venmo Transactions by Date')
    axes.set_xlabel('Dates')
    axes.set_ylabel('Transactions')
    fig.autofmt_xdate()
    axes.fmt_xdata = mdates.DateFormatter('%Y-%m-%d')
    handles, labels = axes.get_legend_handles_labels()
    axes.legend(handles, labels)

    plt.show()
    plt.savefig('daily_trans.png')


def main():
    graph_daily_trans()


if __name__ == '__main__':
    main()