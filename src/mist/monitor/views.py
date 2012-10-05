import os
import requests
from subprocess import call
from datetime import datetime
from time import time

import math
from random import gauss
from operator import *

import numpy
from scipy import interpolate

from logging import getLogger

from pyramid.view import view_config
from pyramid.response import Response

from pymongo import Connection
import pymongo

from mist.monitor.config import MONGODB


log = getLogger('mist.core')

@view_config(route_name='machines', request_method='GET', renderer='json')
def list_machines(request):
    file = open(os.getcwd()+'/conf/collectd.passwd')
    machines = file.read().split('\n')
    return machines


@view_config(route_name='machines', request_method='PUT', renderer='json')
def add_machine(request):
    """ add machine to monitored list """

    # get request params
    uuid = request.params.get('uuid', None)
    passwd = request.params.get('passwd', None)

    # check for errors
    if not uuid or not passwd:
        return Response('Unauthorized', 401)

    # check if uuid already in pass file
    try:
        f = open("conf/collectd.passwd")
        res = f.read()
        f.close()
        if uuid in res:
            return Response('Conflict', 409)

        # append collectd pw file
        f = open("conf/collectd.passwd", 'a')
        f.writelines(['\n'+ uuid + ': ' + passwd])
        f.close()
    except Exception as e:
        log.error('Error opening machines pw file: %s' % e)
        return Response('Service unavailable', 503)

    # create new collectd conf section for allowing machine stats
    config_append = """
        PreCacheChain "%sRule"
        <Chain "%sRule">
            <Rule "rule">
                <Match "regex">
                    Host "^%s$"
                </Match>
                Target return
            </Rule>
            Target stop
        </Chain>""" % (uuid, uuid, uuid)

    try:
        f = open("conf/collectd_%s.conf"%uuid,"w")
        f.write(config_append)
        f.close()

        # include the new file in the main config
        config_include = "conf/collectd_%s.conf" % uuid
        f = open("conf/collectd.conf.local", "a")
        f.write('\nInclude "%s"\n'% config_include)
        f.close()
    except Exception as e:
        log.error('Error opening collectd conf files: %s' % e)
        return Response('Service unavailable', 503)

    try:
        call(['/usr/bin/pkill','-HUP','collectd'])
    except Exception as e:
        log.error('Error restarting collectd: %s' % e)

    return {}


@view_config(route_name='machine', request_method='DELETE', renderer='json')
def remove_machine(request):
    """ remove machine from monitored list """
    # get request params
    try:
        uuid = request.matchdict['machine']

        # check for errors
        if not uuid:
            raise
    except Exception as e:
        return Response('Bad Request', 400)

    try:
        f = open("conf/collectd.passwd")
        res = f.read()
        f.close()
        if uuid not in res:
           return Response('Not Found', 404)
        lines = res.split('\n')
        for l in lines:
            if uuid in l:
                lines.remove(l)
        res = '\n' .join(lines)
        f = open("conf/collectd.passwd",'w')
        f.write(res)
        f.close()
    except Exception as e:
        log.error('Error opening machines pw file: %s' % e)
        return Response('Service unavailable', 503)

    try:
        f = open("conf/collectd.conf.local")
        res = f.read()
        f.close()
        if uuid not in res:
           return Response('Not Found', 404)
        lines = res.split('\n')
        for l in lines:
            if uuid in l:
                lines.remove(l)
        res = '\n' .join(lines)
        f = open("conf/collectd.conf.local",'w')
        f.write(res)
        f.close()
    except Exception as e:
        log.error('Error opening collectd conf file: %s' % e)
        return Response('Service unavailable', 503)


@view_config(route_name='teststats', request_method='GET', renderer='json')
def get_teststats(request):
    """Get all stats for this machine, the client will draw them

    TODO: return real values
    WARNING: copied from mist.core
    """
    interval = 5000 # in milliseconds
    timestamp = time() * 1000 # from seconds to milliseconds
    # check if you just need an update or the full list
    changes_since = request.GET.get('changes_since', None)

    if changes_since:
        # how many samples were created in this interval
        samples = timestamp - float(changes_since)
        samples = math.floor(samples / interval)
        samples = int(samples)
    else:
        # set maximum number of samples
        samples = 1000

    cpu = []
    load = []
    memory = []
    disk = []

    for i in range(0, samples):
        cpu.append(abs(gauss(70.0, 5.0)))
        load.append(abs(gauss(4.0, 0.02)))
        memory.append(abs(gauss(4000.0, 10.00)))
        disk.append(abs(gauss(40.0, 3.0)))

    ret = {'timestamp': timestamp,
           'interval': interval,
           'cpu': cpu,
           'load': load,
           'memory': memory,
           'disk': disk}

    return ret


def get_mongocpustats_numpy(db, uuid, start, stop, step):

    res = {}
    nr_values_asked = int((stop - start)/step)
    ret = {'total': [],'util': [],'total_diff':[] ,'used_diff': [] ,
                'used' : [] }

    query_dict = {'host': uuid,
                  'time': {"$gte": datetime.fromtimestamp(int(start)),
                           "$lt": datetime.fromtimestamp(int(stop)) }}

    res = db.cpu.find(query_dict).sort('time', pymongo.DESCENDING)

    prev = None
    set_of_cpus = []
    for r in res:
        curr = r['time']
        index = r['type_instance']
        value = r['values']
        cpu_no = r['plugin_instance']
        if not ret.get(index, None):
            ret[index] = value
        else:
            ret[index].extend(value)

        if cpu_no not in set_of_cpus:
            set_of_cpus.append(cpu_no)

        if prev != curr:
            ret['total'].append(0)
            ret['used'].append(0)

        if index != 'idle':
            ret['used'][-1] += float(value[0])
        ret['total'][-1] += value[0]
        prev = curr

    for j in range(1, len(ret['total'])):
        i = len(ret['total']) -1 - j
        ret['total_diff'].append  (abs(ret['total'][i-1] - ret['total'][i]))
        ret['used_diff'].append(abs(ret['used'][i-1] - ret['used'][i]))

    used_diff = numpy.array(ret['used_diff'])
    total_diff = numpy.array(ret['total_diff'])
    util = used_diff / total_diff
    calc_util = util

    if util.shape[0] < nr_values_asked:
        calc_util = numpy.zeros(nr_values_asked)
        calc_util[-util.shape[0]::] = util
    elif util.shape[0] > nr_values_asked:
        x_axis = numpy.arange(util.shape[0])
        tck = interpolate.splrep(x_axis, util)
        new_x_axis = numpy.arange(0, util.shape[0], util.shape[0] * float(step)/(stop-start))
        calc_util = interpolate.splev(new_x_axis, tck, der=0)
        calc_util = numpy.abs(calc_util)

    ret['util'] = list(calc_util)

    return ret


def get_mongo_load_stats(db, start, stop, step):
    res = {}
    nr_values_asked = int((stop - start)/step)
    ret = {'shortterm': [], 'midterm': [], 'longterm':[]}

    query_dict = {'host': uuid,
                  'time': {"$gte": datetime.fromtimestamp(int(start)),
                           "$lt": datetime.fromtimestamp(int(stop)) }}

    res = db.load.find(query_dict).sort('time', pymongo.DESCENDING)

    for r in res:
        ret['shortterm'].append(r['values'][0])
        ret['midterm'].append(r['values'][1])
        ret['longterm'].append(r['values'][2])

    shortterm = numpy.array(ret['shortterm'])
    midterm = numpy.array(ret['midterm'])
    longterm = numpy.array(ret['longterm'])

    nr_returned = shortterm.shape[0]

    if nr_returned < nr_values_asked:
        calc_shortterm = numpy.zeros(nr_values_asked)
        calc_shortterm[-nr_returned::] = shortterm
        calc_midterm = numpy.zeros(nr_values_asked)
        calc_midterm[-nr_returned::] = midterm
        calc_longterm = numpy.zeros(nr_values_asked)
        calc_longterm[-nr_returned::] = longterm
    elif nr_returned > nr_values_asked:
        x_axis = numpy.arange(nr_returned)
        tck_short = interpolate.splrep(x_axis, shortterm)
        tck_mid = interpolate.splrep(x_axis, midterm)
        tck_long = interpolate.splrep(x_axis, longterm)
        new_x_axis = numpy.arange(0, nr_returned, nr_returned * float(step)/(stop-start))
        calc_shortterm = interpolate.splev(new_x_axis, tck_short, der=0)
        calc_shortterm = numpy.abs(calc_shortterm)
        calc_midterm = interpolate.splev(new_x_axis, tck_mid, der=0)
        calc_midterm = numpy.abs(calc_shortterm)
        calc_longterm = interpolate.splev(new_x_axis, tck_long, der=0)
        calc_longterm = numpy.abs(calc_shortterm)

    ret['shortterm'] = list(calc_shortterm)
    ret['midterm'] = list(calc_midterm)
    ret['longterm'] = list(calc_longterm)

    return ret


def get_mongocpustats(db, uuid, start, stop, step):

    res = {}
    nr_values_asked = int((stop - start)/step)
    ret = {'total': [],'util': [],'total_diff':[] ,'used_diff': [] ,
                'used' : [] }

    query_dict = {'host': uuid,
                  'time': {"$gte": datetime.fromtimestamp(int(start)),
                           "$lt": datetime.fromtimestamp(int(stop)) }}

    #XXX: No need to use limit, we just return all values in the requested time range
    res = db.cpu.find(query_dict).sort('time', pymongo.DESCENDING)
    #.limit(2*8*(int((stop-start)/step)))

    prev = None
    set_of_cpus = []
    for r in res:
        curr = r['time']
        index = r['type_instance']
        value = r['values']
        cpu_no = r['plugin_instance']
        if not ret.get(index, None):
            ret[index] = value
        else:
            ret[index].extend(value)

        if cpu_no not in set_of_cpus:
            set_of_cpus.append(cpu_no)

        if prev != curr:
            ret['total'].append(0)
            ret['used'].append(0)

        if index != 'idle':
            ret['used'][-1] += float(value[0])
        ret['total'][-1] += value[0]
        prev = curr

    for j in range(1, len(ret['total'])):
        i = len(ret['total']) -1 - j
        ret['total_diff'].append  (abs(ret['total'][i-1] - ret['total'][i]))
        ret['used_diff'].append(abs(ret['used'][i-1] - ret['used'][i]))
    #FIXME: the way we calculate CPU util leaves us with N-1 values to return to D3
    #Thus, we can cheat (if step is 1, we would be left with 0 values for util.
    #ret[col]['total_diff'].append(ret[col]['total_diff'][-1])
    #ret[col]['used_diff'].append(ret[col]['used_diff'][-1])

    ret['util'] = map(div, ret['used_diff'], ret['total_diff'])
    util_values = len(ret['util'])
    calc_util = []
    if util_values < nr_values_asked:
        calc_util = [0] * (nr_values_asked - util_values)
    calc_util.extend(ret['util'])

    #timestamp = time() * 1000
    #ret['timestamp'] = timestamp
    #ret['interval'] = step

    ret['util'] = calc_util
    return ret

@view_config(route_name='mongostats', request_method='GET', renderer='json')
def get_mongostats(request):
    """Get stats for this machine using the mongodb backend. Data is stored using a
    different format than the other get_stats functions, following the targets template
    below

    FIXME: We get a float division error sometimes. This may be due to our total_diff
    array handling or something else. We need to figure this out ASAP.
    """

    mongodb_hostname = MONGODB['host']
    mongodb_port = MONGODB['port']
    mongodb_name = MONGODB['dbname']
    # get request params
    try:
        uuid = request.matchdict['machine']

        # check for errors
        if not uuid:
            log.error("cannot find uuid %s" % uuid)
            raise
    except Exception as e:
        return Response('Bad Request', 400)

    expression = request.params.get('expression', ['cpu', 'load', 'memory', 'disk'])
    stop = int(request.params.get('stop', int(time())))
    step = int(request.params.get('step', 60000))
    start = int(request.params.get('start', stop - step))

    if not expression:
        expression = targets.keys()

    connection = Connection(mongodb_hostname, mongodb_port)
    db = connection[mongodb_name]
    step = int(step/1000)
    nr_values_asked = int((stop - start)/step)

    ret = { }

    if expression.__class__ in [str,unicode]:
        expression = [expression]

    for col in expression:
        #if col == 'cpu':
        #    ret[col] = get_mongocpustats(db, uuid, start, stop, step)
        if col == 'cpu':
            ret[col] = get_mongocpustats_numpy(db, uuid, start, stop, step)
        if col == 'load':
            ret[col] = get_mongo_load_stats(db, uuid, start, stop, step)
    #log.info(ret)
    return ret


@view_config(route_name='stats', request_method='GET', renderer='json')
def get_stats(request):
    """Get all stats for this machine, the client will draw them

    """

    #FIXME: default targets -- could be user customizable
    targets = ["cpu", "load", "memory", "disk"]

    # get request params
    try:
        uuid = request.matchdict['machine']

        # check for errors
        if not uuid:
            log.error("cannot find uuid %s" % uuid)
            raise
    except Exception as e:
        return Response('Bad Request', 400)


    changes_since = request.params.get('changes_since', None)
    if not changes_since:
        changes_since = "-1hours&"
    else:
        changes_since = "%d" %(int(float(changes_since)/1000))

    data_format = request.params.get('format', None)
    if not data_format:
        data_format = "format=json&"

    #FIXME: get rid of that, we are already on the monitoring server,
    #we should know better ;-)
    graphite_uri = "http://experiment.unweb.me:8080"

    data = {'cpu': [ ], 'load':  [ ], 'memory': [ ], 'disk': [ ] }
    interval = 1000

    for target in targets:
        target_uri = "target=servers." + uuid + "." + target + "*.*.*&"
        time_range = "from=%s&until=now" %(changes_since)
        #construct uri
        uri = graphite_uri + "/render?" + data_format + target_uri + time_range
        print uri

        r = requests.get(uri)
        if r.status_code == 200:
            log.info("connect OK")
        else:
            log.error("Status code = %d" %(r.status_code))

        if not len(r.json):
            continue

        for i in range (0, len(r.json[0]['datapoints'])):
            value = r.json[0]['datapoints'][i][0]
            if value:
                data[target].append(r.json[0]['datapoints'][i][0])
            else:
                data[target].append(1)

    #timestamp = r.json[0]['datapoints'][0][1] * 1000
    timestamp = time() * 1000

    ret = {'timestamp': timestamp,
           'interval': interval,
           'cpu': data['cpu'],
           'load': data['load'],
           'memory': data['memory'],
           'disk': data['disk']}

    log.info(ret)
    return ret
