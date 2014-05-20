"""This files configures bucky"""

# Standard debug and log level
#debug = False
log_level = "INFO"  # DEBUG adds a considerable ammount of load
log_fmt = "%(asctime)s [%(levelname)s] %(module)s - %(message)s"

# Whether to print the entire stack trace for errors encountered
# when loading the config file
full_trace = True

###### METRICSD ######
# Basic metricsd conifguration
#metricsd_ip = "127.0.0.1"
#metricsd_port = 23632
metricsd_enabled = False

# The default interval between flushes of metric data to Graphite
#metricsd_default_interval = 10.0

# You can specify the frequency of flushes to Graphite based on
# the metric name used for each metric. These are specified as
# regular expressions. An entry in this list should be a 3-tuple
# that is: (regexp, frequency, priority)
#
# The regexp is applied with the match method. Frequency should be
# in seconds. Priority is used to break ties when a metric name
# matches more than one handler. (The largest priority wins)
#metricsd_handlers = []

###### COLLECTD ######
# Basic collectd configuration
collectd_ip = "127.0.0.1"
collectd_port = 25827  # 25826 is used by the intermediate collectd server
collectd_enabled = True

# A list of file names for collectd types.db
# files.
collectd_types = ["parts/collectd/share/collectd/types.db"]

# A mapping of plugin names to converter callables. These are
# explained in more detail in the README.
## collectd_converters = {}

# Whether to load converters from entry points. The entry point
# used to define converters is 'bucky.collectd.converters'.
## collectd_use_entry_points = True

###### STATSD ######
# Basic statsd configuration
#statsd_ip = "127.0.0.1"
#statsd_port = 8125
statsd_enabled = False

# How often stats should be flushed to Graphite.
#statsd_flush_time = 10.0

# If the legacy namespace is enabled, the statsd backend uses the
# default prefixes except for counters, which are stored directly
# in stats.NAME for the rate and stats_counts.NAME for the
# absolute count.  If legacy names are disabled, the prefixes are
# configurable, and counters are stored under
# stats.counters.{rate,count} by default.  Any prefix can be set
# to None to skip it.
#statsd_legacy_namespace = True
#statsd_global_prefix = "stats"
#statsd_prefix_counter = "counters"
#statsd_prefix_timer = "timers"
#statsd_prefix_gauge = "gauges"

###### GRAPHITE ######
# Basic Graphite configuration
graphite_ip = "127.0.0.1"
graphite_port = 2014

# If the Graphite connection fails these numbers define how it
# will reconnect. The max reconnects applies each time a
# disconnect is encountered and the reconnect delay is the time
# in seconds between connection attempts. Setting max reconnects
# to a negative number removes the limit.
#graphite_max_reconnects = 3
#graphite_reconnect_delay = 5

# Configuration for sending metrics to Graphite via the pickle
# interface. Be sure to edit graphite_port to match the settings
# on your Graphite cache/relay.
graphite_pickle_enabled = True
#graphite_pickle_buffer_size = 500

###### GENERAL SETTINGS ######
# Bucky provides these settings to allow the system wide
# configuration of how metric names are processed before
# sending to Graphite.
#
# Prefix and postfix allow to tag all values with some value.
name_prefix = "bucky"
name_postfix = None

# The replacement character is used to munge any '.' characters
# in name components because it is special to Graphite. Setting
# this to None will prevent this step.
name_replace_char = '_'

# Optionally strip duplicates in path components. For instance
# a.a.b.c.c.b would be rewritten as a.b.c.b
name_strip_duplicates = True

# Bucky reverses hostname components to improve the locality
# of metric values in Graphite. For instance, "node.company.tld"
# would be rewritten as "tld.company.node". This setting allows
# for the specification of hostname components that should
# be stripped from hostnames. For instance, if "company.tld"
# were specified, the previous example would end up as "node".
#name_host_trim = []

# Processor is a callable that takes a (host, name, val, time) tuple as input
# and is expected to return a tuple of the same structure to forward the sample
# to the clients, or None to drop it.
#def debug_proc(host, name, val, time):
#    print host, name, val, time
#    return host, name, val, time
#processor = debug_proc
from mist.bucky_extras.processors.timeprocessor import TimeConverterSingleThread
processor = TimeConverterSingleThread(13)
