from flask import Flask, flash, redirect, render_template, request, session, abort
app = Flask(__name__)

import os
import json
import urllib2
import redis
import datetime

rconfig = {
    'host': 'docker2',
    'port': 6379,
    'db': 0,
}

r = redis.StrictRedis(**rconfig)
# Time Range for Selection - hardcoded for now
zrStart = int(datetime.datetime(2017,01,06,7,00).strftime('%s'))
zrEnd = int(datetime.datetime(2017,01,07,7,00).strftime('%s'))

def getConsumers():
    return r.keys(pattern='cef_consumer:*')


def getStats(cef, zrstart, zrend):
    zldata = []
    zrData = []
    for reading in r.zrangebyscore(cef,zrStart,zrEnd):
        zldata.append(json.loads(reading))

    for values in zldata:
        #  datetime.datetime.fromtimestamp(values['date']).strftime('%c')
        # yield values['cef_consumerId'], values['count'], values['date']
        zrData.append([values['cef_consumerId'], values['count'], values['date']])
    return zrData

def allConsumersStats(zrstart,zrend):
    allConsumers = dict()
    for consumer in getConsumers():
        allConsumers[consumer] = []
        for record in getStats(consumer, zrStart, zrEnd):
            allConsumers[consumer].append(record)
    return allConsumers

for item in allConsumersStats(zrStart, zrEnd).items():
    # print item[0]
    for dp in item[1]:
        print [datetime.datetime.fromtimestamp(dp[2]).strftime('%Y, %m, %d, %H, %M'), dp[0], dp[1]]

#  store the call to getStats into var first and iterate over it for x,y values rather than call it twice.
#zrData = getStats("cef_consumer:docker1-1", zrStart, zrEnd)
#xdate = map(lambda d: d.strftime('%c'), [datetime.datetime.fromtimestamp(x[2]) for x in zrData])
#yvals = [int(y[1]) for y in zrData]

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

# TODO def func to prepare data for the graph.
def getExchangeRates():
    rates = []
    response = urllib2.urlopen('http://api.fixer.io/latest')
    data = response.read()
    rdata = json.loads(data, parse_float=float)

    rates.append( rdata['rates']['USD'] )
    rates.append( rdata['rates']['GBP'] )
    rates.append( rdata['rates']['HKD'] )
    rates.append( rdata['rates']['AUD'] )
    return rates

@app.route("/")
def index():
    rates = getExchangeRates()
    return render_template('gg.html',**locals())

@app.route("/hello")
def hello():
    return "Hello World!"





if __name__ == "__main__":
    app.run(debug=True)
