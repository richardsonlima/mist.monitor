import os
from subprocess import call
from time import time

from logging import getLogger

from pyramid.view import view_config
from pyramid.response import Response

from mist.monitor.stats import mongo_get_stats
from mist.monitor.stats import graphite_get_stats, graphite_get_loadavg
from mist.monitor.stats import dummy_get_stats
from mist.monitor.rules import add_rule
from mist.monitor.rules import remove_rule

from mist.monitor.model import get_all_machines

from mist.monitor import methods
from mist.monitor import config

log = getLogger(__name__)
OK = Response(200, "OK")


@view_config(route_name='machines', request_method='GET', renderer='json')
def list_machines(request):
    """Lists machines with monitoring.

    Returns a dict with uuid's as keys and machine dicts as values.

    """
    return {machine.uuid: machine.as_dict() for machine in get_all_machines()}


@view_config(route_name='machines', request_method='PUT')
def add_machine(request):
    """Adds machine to monitored list."""
    uuid = request.params.get('uuid')
    passwd = request.params.get('passwd')
    log.info("Adding machine %s to monitor list" % (uuid))

    if not uuid:
        raise RequiredParameterMissingError('uuid')
    if not passwd:
        raise RequiredParameterMissingError('passwd')

    methods.add_machine(uuid, passwd)

    return OK


@view_config(route_name='machine', request_method='DELETE')
def remove_machine(request):
    """Removes machine from monitored list."""
    uuid = request.matchdict['machine']
    log.info("Removing machine %s from monitor list" % (uuid))

    machine = get_machine_from_uuid(uuid)
    if not machine:
        raise MachineNotFoundError(uuid)

    methods.remove_machine(uuid)
    return OK


@view_config(route_name='rules', request_method='PUT', renderer='json')
def update_rules(request):

    params = request.json_body
    action = params.get('rule_action')  #FIXME: use different HTTP method ffs!
    uuid = params.get("uuid")
    rule_id = params.get("rule_id")

    if action == 'add':
        metric = params.get("metric")
        operator = params.get("operator")
        value = params.get("value")
        time_to_wait = params.get("time_to_wait")
        if metric in ['network-tx', 'disk-write']:
            value = float(value) * 1000
        methods.update_rule(uuid, rule_id, metric, operator, value, time_to_wait)
    else:
        methods.remove_rule(uuid, rule_id)

    return OK


@view_config(route_name='stats', request_method='GET', renderer='json')
def get_stats(request):
    """
    Returns all stats for a machine, the client will draw them.
    """
    uuid = request.matchdict['machine']

    if not uuid:
        log.error("cannot find uuid %s" % uuid)
        return Response('Bad Request', 400)

    allowed_expression = ['cpu', 'load', 'memory', 'disk', 'network']

    expression = request.params.get('expression',
                                    ['cpu', 'load', 'memory', 'disk', 'network'])
    if expression.__class__ in [str,unicode]:
        #expression = [expression]
        expression = expression.split(',')

    for target in expression:
        if target not in allowed_expression:
            log.error("expression error '%s'" % target)
            return Response('Bad Request', 400)

    # step comes from the client in millisecs, convert it to secs
    step = int(request.params.get('step', 10000))
    if (step >= 5000):
        step = int(step/1000)
    elif step == 0:
        log.warn("We got step == 0, maybe the client is broken ;S, using default")
        step = 60
    else:
        log.warn("We got step < 1000, maybe the client meant seconds ;-)")

    stop = int(request.params.get('stop', int(time())))
    start = int(request.params.get('start', stop - step))

    stats = {}
    backend = request.registry.settings['backend']
    if backend['type'] == 'graphite':
        host = backend['host']
        port = backend['port']
        stats = graphite_get_stats(host, port, uuid, expression, start, stop, step)
    elif backend['type'] == 'dummy':
        stats = dummy_get_stats(expression, start, stop, step)
    else:
        log.error('Requested invalid monitoring backend: %s' % backend)
        return Response('Service unavailable', 503)

    return stats
