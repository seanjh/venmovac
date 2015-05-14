from datetime import datetime, timedelta, date
from itertools import groupby

import pymongo
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

CLIENT = pymongo.MongoClient('localhost', 27017)
DB = CLIENT['venmo']
TRANS_COLLECTION = DB['trans']
USER_PAIRS_COLLECTION = DB['user_pairs']
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

    for i, tc in enumerate(tran_counts):
        print '%s -- %s' % (all_dates[i], tc)

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


def pairs_iter():
    pipeline = [
        {"$unwind": "$targets"},
        {"$group": {
            "_id": "$_id",
            "unique_targets": { "$addToSet": "$targets" }
        }},
        {"$project": {
            "username": "$_id.username",
            "total_targets": {"$size": "$unique_targets"}
        }},
        {"$sort": {"total_targets": 1}}
    ]
    return USER_PAIRS_COLLECTION.aggregate(pipeline, allowDiskUse=True)


def make_labels(x_axis, multiple):
    labels = []
    for i, val in enumerate(x_axis):
        if i == 0:
            labels.append('<%d' % multiple)
        elif i == (len(x_axis) - 1):
            labels.append('>=%d' % (val * multiple))
        else:
            labels.append('%d-%d' % (x_axis[i] * multiple, x_axis[i+1] * multiple - 1))
    return labels


def graph_user_pair_counts():
    TARGETS_THRESHOLD = 30
    LABELS_MULTIPLE = 10

    pairs_by_count = {}
    # groupby(pairs_iter(), lambda r: r.get('total_targets'))
    for result in pairs_iter():
        key = result.get('total_targets') / LABELS_MULTIPLE
        pairs_by_count[key] = 1 + pairs_by_count.setdefault(key, 0)

    total_user_count = sum(pairs_by_count.values())
    print 'Total users: %d' % total_user_count

    targets = sorted(pairs_by_count.keys())
    users = [pairs_by_count.get(t) for t in targets]

    target_ratios = [float(u) / total_user_count for u in users]
    for i, t in enumerate(targets):
        print '%4d Targets: %-8d %0.6f%%' % (t, users[i], target_ratios[i]*100)

    total_included = sum([pairs_by_count.get(t) for t in targets if (t * LABELS_MULTIPLE) >= TARGETS_THRESHOLD])
    explode_mask = []
    for i, val in enumerate(targets):
        result = 0.1 if (val * LABELS_MULTIPLE) >= TARGETS_THRESHOLD else 0
        explode_mask.append(result)
    print 'Total included: %d (%0.6f%%)' % (total_included, float(total_included / total_user_count) * 100)

    labels = make_labels(targets, LABELS_MULTIPLE)
    pallette = sns.color_palette("Set2", len(target_ratios))
    plot_user_pair_counts(targets, users, target_ratios, labels, explode_mask, pallette)



def plot_user_pair_counts(targets, users, ratios, labels, explode, pallette):
    fig, axes = plt.subplots(1, figsize=(16, 10))

    # axes.pie(ratios, explode=explode, labels=labels, colors=pallette, autopct='%1.1f%%', shadow=True, startangle=90)
    axes.bar(targets, users, color=pallette[1], label='Unique Targets')
    axes.set_yscale('log')

    axes.xlabel('Unique Target Users')
    axes.ylabel('Total Users')
    axes.title('VenmoUusers by Total Number of Unique Targets')
    axes.grid(True)
    axes.xticks(targets + 0.5, labels)

    handles, labels = axes.get_legend_handles_labels()
    axes.legend(handles, labels)

    plt.show()
    # plt.savefig('target_ratios.png')
    plt.savefig('target_counts.png')



def main():
    # graph_daily_trans()
    graph_user_pair_counts()


if __name__ == '__main__':
    main()