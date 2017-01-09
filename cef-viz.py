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
zrStart = int(datetime.datetime(2017, 1, 6, 7, 0).strftime('%s'))
zrEnd = int(datetime.datetime(2017, 1, 7, 7, 0).strftime('%s'))


def getConsumers():
    return r.keys(pattern='cef_consumer:*')


def getStats(cef, zrstart, zrend):
    zldata = []
    zrData = []
    for reading in r.zrangebyscore(cef,zrStart,zrEnd):
        zldata.append(json.loads(bytes(reading).decode('utf-8')))

    for values in zldata:
        #  datetime.datetime.fromtimestamp(values['date']).strftime('%c')
        yield values['cef_consumerId'], values['count'], values['date']
        #zrData.append([values['cef_consumerId'], values['count'], values['date']])
    #return zrData

def allConsumersStats(zrstart, zrend):
    allConsumers = dict()
    for consumer in getConsumers():
        allConsumers[consumer] = []
        for record in getStats(consumer, zrStart, zrEnd):
            allConsumers[consumer].append(record)
    return allConsumers

for item in allConsumersStats(zrStart, zrEnd).items():
    # print item[0]
    for dp in item[1]:
        print([datetime.datetime.fromtimestamp(dp[2]).strftime('%Y, %m, %d, %H, %M'), dp[0], dp[1]])

#  store the call to getStats into var first and iterate over it for x,y values rather than call it twice.
#zrData = getStats("cef_consumer:docker1-1", zrStart, zrEnd)
#xdate = map(lambda d: d.strftime('%c'), [datetime.datetime.fromtimestamp(x[2]) for x in zrData])
#yvals = [int(y[1]) for y in zrData]




tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

# TODO def func to prepare data for the graph.


@app.route("/")
def cef_consumer_stats():
    # create a bar chart
    title = "CEF Consumer" #'Temps for %s, %s on %s'

    date_chart = pygal.Line(x_label_rotation=20)
    date_chart.x_labels = map(lambda d: d.strftime('%Y-%m-%d'), [
        datetime.datetime(2013, 1, 2),
        datetime.datetime(2013, 1, 12),
        datetime.datetime(2013, 2, 2),
        datetime.datetime(2013, 2, 22)])
    date_chart.add("Visits", [300, 412, 823, 672])
    date_chart.add("Dates", [320, 212, 623, 972])

    #date_chart.render()
    return render_template('cef_pygal.html',
                           title="Date", style=DarkSolarizedStyle,
                           date_chart=date_chart)



@app.route("/hello")
def hello():
    return "<h1>Hello</h1>"


if __name__ == "__main__":
    app.run(debug=True)
