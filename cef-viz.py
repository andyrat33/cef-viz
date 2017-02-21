import json
import redis
import pygal
from datetime import datetime, timedelta
from flask import Flask, render_template, g
from flask_bootstrap import Bootstrap
from flask_wtf import Form
from wtforms import DateTimeField, SubmitField, SelectField
from wtforms.validators import Required
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



def get_all_consumers():

    return r.keys(pattern='cef_consumer:*')


def build_choices():

    return [((bytes(x).decode('utf-8')),(bytes(x).decode('utf-8'))) for x in get_all_consumers()]


class dataEntry(Form):
    uiStartDateTime = DateTimeField('Start date time', format='%Y-%m-%d %H:%M', validators=[Required()])
    uiEndDateTime = DateTimeField('End date time', format='%Y-%m-%d %H:%M', validators=[Required()])

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


def getStats(cef, range_start, range_end):
    zldata = []
    for reading in r.zrangebyscore(cef, range_start, range_end):
        zldata.append(json.loads(bytes(reading).decode('utf-8')))

    for values in zldata:
        yield values['cef_consumerId'], values['count'], values['date']


def allConsumersStats(range_start, range_end):

    allConsumers = dict()
    for consumer in get_all_consumers():
        allConsumers[consumer] = []
        # Use a call to consumer_stats(consumer)
        for record in getStats(consumer,range_start, range_end):
            allConsumers[consumer].append(record)
    return allConsumers


def consumer_stats(cef, range_start, range_end):
    constatdata = dict()
    constatdata[cef] = []
    for record in getStats(cef,range_start, range_end):
        constatdata[cef].append(record)

    return constatdata

def eps(range_start, range_end):

    result = dict()
    for item in allConsumersStats(range_start, range_end).items():
        # print item[0]
        total_events = 0
        dcount = 0
        if item[1]:
            for dp in item[1]:
                # EPS = num events / divided by 600 seconds collection period
                total_events += dp[1]
                dcount += 1
            try:
                result[dp[0]] = total_events / (dcount * 600)
            except:
                result[dp[0]] = 0

    return result


def cef_consumer_chart(cef, range_start, range_end):
    """Create a graph for the cef_consumer"""

    date_chart = pygal.Line(x_label_rotation=20)
    date_chart.x_labels = []

    for item in consumer_stats(cef, range_start, range_end).items():
        # print item[0]
        nums = []
        for dp in item[1]:
            # Get dates once for x_labels align all samples to the first date-times returned by the first
            # cef_consumer through the loop,

            date_chart.x_labels.append(datetime.fromtimestamp(dp[2]).strftime('%Y-%m-%d %H:%M'))

            nums.append(dp[1])

        date_chart.add(cef.split(':')[1], nums)

    return date_chart





@app.route('/', methods=('GET', 'POST'))
def index():

    total_count = bytes(r.get(name='count')).decode()

    g.sEnd = datetime.now()
    g.sStart = (g.sEnd - timedelta(minutes=60))
    form = dataEntry(uiStartDateTime=g.sStart, uiEndDateTime=g.sEnd)
    g.zrEnd = int(g.sEnd.strftime('%s'))
    g.zrStart = int(g.sStart.strftime('%s'))
    g.cef_name = build_choices()[0][1]
    if form.validate_on_submit():
        g.sStart = form.uiStartDateTime.data
        g.sEnd = form.uiEndDateTime.data
        g.zrEnd = int(g.sEnd.strftime('%s'))
        g.zrStart = int(g.sStart.strftime('%s'))
        g.cef_name = form.cef_consumer_instance.data

    return render_template('index.html', form=form, total_count=total_count,
                           date_chart=cef_consumer_chart(g.cef_name, g.zrStart, g.zrEnd), eps_results=eps(g.zrStart, g.zrEnd))


@app.errorhandler(404)
def notfound(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)
