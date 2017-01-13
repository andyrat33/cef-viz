import os
import json
import redis
from datetime import datetime, timedelta

from flask import Flask, flash, redirect, render_template, request, session, abort, url_for
from flask_wtf import Form
from wtforms import StringField, BooleanField, DateField, DateTimeField
from wtforms.validators import DataRequired


import pygal
from pygal.style import DarkSolarizedStyle

app = Flask(__name__)
app.config.from_object('config')

print(app.secret_key)
rconfig = {
    'host': 'docker2',
    'port': 6379,
    'db': 0,
}

r = redis.StrictRedis(**rconfig)
# Time Range for Selection - hardcoded for now
print(datetime(2017, 1, 7))
zrStart = int(datetime(2017, 1, 11, 15, 0).strftime('%s'))
zrEnd = int(datetime(2017, 1, 11, 19, 0).strftime('%s'))
# TODO Create defaults for start and end = now() and start = now() - 2h


def chkTimeDelta(zrEnd, zrStart, diff=10):
    cdiff = (zrEnd - zrStart)
    # TODO Check that 10 mins or more occurs in the past
    if cdiff >= timedelta(minutes=diff):
        return True
    else:
        return False

class dataEntry(Form):
    uiStartDateTime = DateTimeField('Start date time', format='%Y-%m-%d %H:%M', default=datetime.now())
    uiEndDateTime = DateTimeField('End date time', format='%Y-%m-%d %H:%M', default=datetime.now())
    # custom validator to check the end time date is greater than the start time date uses chkTimeDelta in view
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
            # Get dates once for x_labels align all samples to the first date-times returned by the first
            # cef_consumer through the loop,
            if not done:
                date_chart.x_labels.append(datetime.fromtimestamp(dp[2]).strftime('%Y-%m-%d-%H-%M'))

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

@app.route("/total")
def total():
    total_count = bytes(r.get(name='count')).decode()
    return "<h1>Total Events Processed {}</h1>".format(total_count)


@app.route('/submit', methods=('GET', 'POST'))
def submit():
    global zrStart, zrEnd
    form = dataEntry(request.form, csrf_enabled=False)
    if request.method == 'POST' and form.validate():
        start = form.uiStartDateTime.data
        end = form.uiEndDateTime.data
        if chkTimeDelta(end, start):
            zrStart = int(start.strftime('%s'))
            zrEnd = int(end.strftime('%s'))
            return redirect(url_for('cef_consumer_stats'))
    return render_template('submit.html', title='Date and Time Range', form=form)

if __name__ == "__main__":
    app.run(debug=True)
