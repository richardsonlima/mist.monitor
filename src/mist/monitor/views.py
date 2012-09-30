import os
from subprocess import call

from pyramid.view import view_config
from pyramid.response import Response

from random import gauss

@view_config(route_name='machines', request_method='GET', renderer='json')
def list_machines(request):
    file = open(os.getcwd()+'/conf/collectd.machines')
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
    f = open("conf/collectd.machines")
    res = f.read()
    f.close()
    if uuid in res:
        return Response('Conflict', 409)

    # append collectd pw file
    f = open("conf/collectd.machines", 'a')
    f.writelines(['\n'+ uuid + ': ' + passwd])
    f.close()


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

    f = open("conf/collectd_%s.conf"%uuid,"w")
    f.write(config_append)
    f.close()

    # include the new file in the main config
    config_include = "conf/collectd_%s.conf" % uuid
    f = open("conf/collectd.conf", "a")
    f.write('\nInclude "%s"\n'% config_include)
    f.close()

    call(['/usr/bin/pkill','-HUP','collectd'])

    return {}


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


@view_config(route_name='stats', request_method='GET', renderer='json')
def get_stats(request):
    """Get all stats for this machine, the client will draw them

    """

    #FIXME: default targets -- could be user customizable
    targets = ["cpu", "load", "memory", "disk"]

    uuid = request.params.get('uuid', None)
    changes_since = request.params.get('changes_since', None)
    if not changes_since:
        changes_since = "-2hours&"

    data_format = request.params.get('format', None)
    if not data_format:
        data_format = "format=json&"

    #FIXME: get rid of that, we are already on the monitoring server,
    #we should know better ;-)
    graphite_uri = "http://experiment.unweb.me:8080"

    data = {'cpu': [ ], 'load':  [ ], 'memory': [ ], 'disk': [ ] }
    interval = 5000

    for target in targets:
        target_uri = "target=servers." + uuid + "." + target + "*.*.*&"
        time_range = "from=" + changes_since + "until=now"
        #construct uri
        uri = graphite_uri + "/render?" + data_format + target_uri + time_range

        r = requests.get(uri)

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

    return ret
