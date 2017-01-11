from flask import Flask, flash, redirect, render_template, request, session, abort
app = Flask(__name__)

import os
import json
import redis
import datetime
import pygal
from pygal.style import DarkSolarizedStyle

rconfig = {
    'host': 'docker2',
    'port': 6379,
    'db': 0,
}

r = redis.StrictRedis(**rconfig)
# Time Range for Selection - hardcoded for now
print(datetime.datetime(2017, 1, 7))
zrStart = int(datetime.datetime(2017, 1, 11, 15, 0).strftime('%s'))
zrEnd = int(datetime.datetime(2017, 1, 11, 19, 0).strftime('%s'))


def getConsumers():
    return r.keys(pattern='cef_consumer:*')


def getStats(cef, zrstart, zrend):
    zldata = []
    for reading in r.zrangebyscore(cef,zrStart,zrEnd):
        zldata.append(json.loads(bytes(reading).decode('utf-8')))

    for values in zldata:
        #  datetime.datetime.fromtimestamp(values['date']).strftime('%c')
        yield values['cef_consumerId'], values['count'], values['date']


def allConsumersStats(zrstart, zrend):
    allConsumers = dict()
    for consumer in getConsumers():
        allConsumers[consumer] = []
        for record in getStats(consumer, zrStart, zrEnd):
            allConsumers[consumer].append(record)
    return allConsumers

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)



@app.route("/")
def cef_consumer_stats():
    # create a bar chart
    done = False
    date_chart = pygal.Line(x_label_rotation=20)
    date_chart.x_labels = []
    for item in allConsumersStats(zrStart, zrEnd).items():
        # print item[0]
        nums = []
        for dp in item[1]:
            # TODO use a set for dates in x_labels
            if not done:
                date_chart.x_labels.append(datetime.datetime.fromtimestamp(dp[2]).strftime('%Y-%m-%d-%H-%M'))

            nums.append(dp[1])
            cefname = dp[0]
        done = True
        date_chart.add(cefname, nums)


    title = "CEF Consumer"


    return render_template('cef_pygal.html',
                           title=title, style=DarkSolarizedStyle,
                           date_chart=date_chart)



@app.route("/eps")
def eps():
    result = dict()
    for item in allConsumersStats(zrStart, zrEnd).items():
        # print item[0]
        total_events = 0
        dcount = 0
        for dp in item[1]:
           # EPS = num events / divided by 600 seconds collection period
            total_events += dp[1]
            dcount += 1

        result[dp[0]] = total_events / (dcount * 600)

    return render_template('cef_eps.html',
                           title='EPS', style=DarkSolarizedStyle,
                           results=result)

if __name__ == "__main__":
    app.run(debug=True)
