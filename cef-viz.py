import os
import json
import redis
import pygal
from pygal.style import DarkSolarizedStyle
from datetime import datetime, timedelta
from flask import Flask, flash, redirect, render_template, request, session, abort, url_for
# from flask import Flask, render_template
from flask.ext.bootstrap import Bootstrap
# from flask.ext.wtf import Form
from flask_wtf import Form
# from wtforms import StringField
from wtforms import DateTimeField, SubmitField, SelectField
from wtforms.validators import Required, Length
from configparser import ConfigParser

app = Flask(__name__)
app.config['SECRET_KEY'] = 'top secret!'
bootstrap = Bootstrap(app)

# store the config in cefviz.ini
def get_config():
    conf = ConfigParser()
    conf.read('config/cefviz.ini')
    return conf

config = get_config()
rconfig = {
    'host': config.get('redis', 'host'),
    'port': config.get('redis', 'port'),
    'db': config.get('redis', 'db')
}

r = redis.StrictRedis(**rconfig)


def updateDateTime():
    global sEnd, sStart, zrEnd, zrStart
    sEnd = datetime.now()
    sStart = (sEnd - timedelta(minutes=60))
    zrEnd = int(sEnd.strftime('%s'))
    zrStart = int(sStart.strftime('%s'))

updateDateTime()


def get_all_consumers():

    return r.keys(pattern='cef_consumer:*')


def build_choices():

    return [((bytes(x).decode('utf-8')),(bytes(x).decode('utf-8'))) for x in get_all_consumers()]


cef_name = build_choices()[0][1]


class dataEntry(Form):
    uiStartDateTime = DateTimeField('Start date time', format='%Y-%m-%d %H:%M', default=sStart, validators=[Required()])
    uiEndDateTime = DateTimeField('End date time', format='%Y-%m-%d %H:%M', default=sEnd, validators=[Required()])
    # custom validator to check the end time date is greater than the start time date
    cef_consumer_instance = SelectField(
        'CEF Consumer',
        choices=build_choices())
    submit = SubmitField('Submit')


    def validate(self):
        """This function returns true or false. Start time must be less than end time by 10 mins and start time must be at
    least 10 minutes in the past"""
        if not super().validate():
            return False
        tmpStart = self.uiStartDateTime.data
        tmpEnd = self.uiEndDateTime.data
        cdiff = (tmpEnd - tmpStart)
        # Check that 10 mins or more occurs in the past
        ndiff = (datetime.now() - tmpStart)
        if cdiff <= timedelta(minutes=10):
            self.uiStartDateTime.errors.append('Start date time must precede End date time')
            result = False
        else:
            result = True
            if ndiff <= timedelta(minutes=10):
                message = 'Start date time must be at least 10 mins in the past {dt}'.format(dt=datetime.now().strftime('%H:%M'))
                self.uiStartDateTime.errors.append(message)
                result = False
        return result


def get_consumer(consumer_pattern):
    return r.keys(pattern=consumer_pattern)


def getStats(cef):
    zldata = []
    for reading in r.zrangebyscore(cef,zrStart,zrEnd):
        zldata.append(json.loads(bytes(reading).decode('utf-8')))

    for values in zldata:
        yield values['cef_consumerId'], values['count'], values['date']


def allConsumersStats():
    #global cef_name
    allConsumers = dict()
    for consumer in get_all_consumers():
        allConsumers[consumer] = []
        # Use a call to consumer_stats(consumer)
        for record in getStats(consumer):
            allConsumers[consumer].append(record)
    return allConsumers


def consumer_stats(cef=cef_name):
    constatdata = dict()
    constatdata[cef] = []
    for record in getStats(cef):
        constatdata[cef].append(record)

    return constatdata

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
        try:
            result[dp[0]] = total_events / (dcount * 600)
        except:
            result[dp[0]] = 0

    return result

def cef_consumer_chart():
    """Create a graph for the cef_consumer"""
    #global cef_name
    done = False
    date_chart = pygal.Line(x_label_rotation=20)
    date_chart.x_labels = []
    #for item in allConsumersStats().items():
    for item in consumer_stats(cef_name).items():
        # print item[0]
        nums = []
        for dp in item[1]:
            # Get dates once for x_labels align all samples to the first date-times returned by the first
            # cef_consumer through the loop,
            if not done:
                date_chart.x_labels.append(datetime.fromtimestamp(dp[2]).strftime('%Y-%m-%d %H:%M'))

            nums.append(dp[1])
        done = True
        date_chart.add(cef_name.split(':')[1], nums)

    return date_chart


@app.route('/', methods=('GET', 'POST'))
def index():
    global sStart, sEnd, zrStart, zrEnd, cef_name
    total_count = bytes(r.get(name='count')).decode()
    form = dataEntry()

    if form.validate_on_submit():
        sStart = form.uiStartDateTime.data
        sEnd = form.uiEndDateTime.data
        # StartDate = sStart.strftime('%Y-%m-%d %H:%M')
        # EndDate = sEnd.strftime('%Y-%m-%d %H:%M')
        zrEnd = int(sEnd.strftime('%s'))
        zrStart = int(sStart.strftime('%s'))
        cef_name = form.cef_consumer_instance.data

    return render_template('index.html', form=form, total_count=total_count,
                           date_chart=cef_consumer_chart(), eps_results=eps())

if __name__ == '__main__':
    app.run(debug=True)
