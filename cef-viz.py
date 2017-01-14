import os
import json
import redis
import pygal
from datetime import datetime, timedelta
from flask import Flask, flash, redirect, render_template, request, session, abort, url_for
from flask_wtf import Form
from wtforms import DateTimeField
from pygal.style import DarkSolarizedStyle

app = Flask(__name__)
app.config.from_object('config')

rconfig = {
    'host': 'docker2',
    'port': 6379,
    'db': 0,
}

sEnd = datetime.now()
sStart = datetime.now()
zrEnd = 0
zrStart = 0

r = redis.StrictRedis(**rconfig)

def updateDateTime():
    global sEnd, sStart, zrEnd, zrStart
    sEnd = datetime.now()
    sStart = (sEnd - timedelta(minutes=60))
    zrEnd = int(sEnd.strftime('%s'))
    zrStart = int(sStart.strftime('%s'))

updateDateTime()


# Done. Create defaults for start and end = now() and start = now() - 1h


def chkTimeDelta(dtEnd: datetime, dtStart: datetime, diff: int = 10) -> bool:
    """
    This function returns true or false. Start time must be less than end time by amount diff and start time must be at
    least 10 minutes in the past
    :param dtEnd:
    :param dtStart:
    :param diff:
    :return: bool
    """
    cdiff = (dtEnd - dtStart)
    # Check that 10 mins or more occurs in the past
    ndiff = (datetime.now() - dtStart)
    if cdiff >= timedelta(minutes=diff) and ndiff >= timedelta(minutes=10):
        return True
    else:
        return False


class dataEntry(Form):
    uiStartDateTime = DateTimeField('Start date time', format='%Y-%m-%d %H:%M', default=datetime.now() - timedelta(minutes=60))
    uiEndDateTime = DateTimeField('End date time', format='%Y-%m-%d %H:%M', default=datetime.now())
    # custom validator to check the end time date is greater than the start time date uses chkTimeDelta in view


def getConsumers():
    return r.keys(pattern='cef_consumer:*')


def getStats(cef):
    zldata = []
    for reading in r.zrangebyscore(cef,zrStart,zrEnd):
        zldata.append(json.loads(bytes(reading).decode('utf-8')))

    for values in zldata:
        yield values['cef_consumerId'], values['count'], values['date']


def allConsumersStats():
    allConsumers = dict()
    for consumer in getConsumers():
        allConsumers[consumer] = []
        for record in getStats(consumer):
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
    for item in allConsumersStats().items():
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

    title = "CEF Consumer Graph"

    return render_template('cef_pygal.html',
                           title=title, StartDate=sStart.strftime('%Y-%m-%d %H:%M'),
                           EndDate=sEnd.strftime('%Y-%m-%d %H:%M'),
                           style=DarkSolarizedStyle,
                           date_chart=date_chart)



@app.route("/eps")
def eps():
    result = dict()
    for item in allConsumersStats().items():
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
    global zrStart, zrEnd, sStart, sEnd

    form = dataEntry(request.form, csrf_enabled=False)
    if request.method == 'POST' and form.validate():
        sStart = form.uiStartDateTime.data
        sEnd = form.uiEndDateTime.data
        if chkTimeDelta(sEnd, sStart):
            zrStart = int(sStart.strftime('%s'))
            zrEnd = int(sEnd.strftime('%s'))
            return redirect(url_for('cef_consumer_stats'))
    return render_template('submit.html', title='Date and Time Range', form=form)

if __name__ == "__main__":
    app.run(debug=True)
