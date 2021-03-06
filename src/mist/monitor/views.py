import os
import re
import logging
import traceback
from subprocess import call
from time import time

from pyramid.view import view_config
from pyramid.response import Response

from mist.monitor import config
from mist.monitor import methods
from mist.monitor import graphite

from mist.monitor.model import get_all_machines

from mist.monitor.exceptions import MistError
from mist.monitor.exceptions import RequiredParameterMissingError
from mist.monitor.exceptions import MachineNotFoundError
from mist.monitor.exceptions import ForbiddenError
from mist.monitor.exceptions import UnauthorizedError
from mist.monitor.exceptions import BadRequestError


log = logging.getLogger(__name__)
OK = Response("OK", 200)


@view_config(context=Exception)
def exception_handler_mist(exc, request):
    """Here we catch exceptions and transform them to proper http responses

    This is a special pyramid view that gets triggered whenever an exception
    is raised from any other view. It catches all exceptions exc where
    isinstance(exc, context) is True.

    """

    # non-mist exceptions. that shouldn't happen! never!
    if not isinstance(exc, MistError):
        trace = traceback.format_exc()
        log.critical("Uncaught non-mist exception? WTF!\n%s", trace)
        return Response("Internal Server Error", 500)

    # mist exceptions are ok.
    log.info("MistError: %r", exc)

    # translate it to HTTP response based on http_code attribute
    return Response(str(exc), exc.http_code)


@view_config(route_name='machines', request_method='GET', renderer='json')
def list_machines(request):
    """Lists machines with monitoring.

    Returns a dict with uuid's as keys and machine dicts as values.

    """
    return {machine.uuid: {'rules': [rule_id]}
            for machine in get_all_machines()
            for rule_id in machine.rules}


@view_config(route_name='machine', request_method='PUT')
def add_machine(request):
    """Adds machine to monitored list."""
    uuid = request.matchdict['machine']
    passwd = request.params.get('passwd')
    log.info("Adding machine %s to monitor list" % (uuid))
    if not passwd:
        raise RequiredParameterMissingError('passwd')

    methods.add_machine(uuid, passwd)
    return OK


@view_config(route_name='machine', request_method='DELETE')
def remove_machine(request):
    """Removes machine from monitored list."""
    uuid = request.matchdict['machine']
    log.info("Removing machine %s from monitor list" % (uuid))

    methods.remove_machine(uuid)
    return OK


@view_config(route_name='rule', request_method='PUT')
def add_rule(request):
    """Add or update rule.

    This will create a new condition that will start being checked with clear
    history, even if the rule is not actually being changed.

    """
    uuid = request.matchdict['machine']
    rule_id = request.matchdict['rule']

    params = request.json_body
    for key in ["metric", "operator", "value"]:
        if not params.get(key):
            raise RequiredParameterMissingError(key)
    metric = params["metric"]
    operator = params["operator"]
    value = params["value"]
    reminder_list = params.get("reminder_list")
    reminder_offset = params.get("reminder_offset")
    aggregate = params.get("aggregate")

    methods.add_rule(uuid, rule_id, metric, operator, value,
                     aggregate=aggregate, reminder_list=reminder_list,
                     reminder_offset=reminder_offset)
    return OK

@view_config(route_name='rule', request_method='DELETE')
def remove_rule(request):
    """Removes rule and corresponding condition."""
    uuid = request.matchdict['machine']
    rule_id = request.matchdict['rule']
    methods.remove_rule(uuid, rule_id)
    return OK


@view_config(route_name='stats', request_method='GET', renderer='json')
def get_stats(request):
    """Returns all stats for a machine, the client will draw them."""

    uuid = request.matchdict['machine']
    params = request.params
    metrics = params.getall('metric')
    start = params.get('start')
    stop = params.get('stop')
    interval_str = params.get('step')

    if re.match("^[0-9]+(\.[0-9]+)?$", interval_str):
        interval_str = int(interval_str)
        interval_str = "%ssec" % (interval_str)

    return methods.get_stats(uuid, metrics, start, stop, interval_str)


@view_config(route_name='find_metrics', request_method='GET', renderer='json')
def find_metrics(request):
    uuid = request.matchdict['machine']
    return methods.find_metrics(uuid)


@view_config(route_name='reset', request_method='POST')
def reset_hard(request):
    """Reset mist.monitor with data provided from mist.core

    This is a special view that will cause monitor to drop all known data
    for machines, rules and conditions, will repopulate itself with the data
    provided in the request and will restart collectd and mist.alert.

    For security reasons, a special non empty key needs to be specified in
    settings.py and sent along with the reset request.

    """
    params = request.json_body
    key, data = params.get('key'), params.get('data', {})
    if not config.RESET_KEY:
        raise ForbiddenError("Reset functionality not enabled.")
    if key != config.RESET_KEY:
        raise UnauthorizedError("Wrong reset key provided.")
    methods.reset_hard(params['data'])
    return OK
