import os
import time

from flask import Flask
from google.cloud import datastore
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Link


ds_client = datastore.Client()
KEY_TYPE = 'Record'

tracer_provider = TracerProvider()
cloud_trace_exporter = CloudTraceSpanExporter()
tracer_provider.add_span_processor(
    # BatchSpanProcessor buffers spans and sends them in batches in a
    # background thread. The default parameters are sensible, but can be
    # tweaked to optimize your performance
    BatchSpanProcessor(cloud_trace_exporter)
)
trace.set_tracer_provider(tracer_provider)

tracer = trace.get_tracer(__name__)

app = Flask(__name__)


def trace_span(func):
  def wrapper(*args, **kwargs):
    with tracer.start_as_current_span(func.__name__):
      return func(*args, **kwargs)
  return wrapper


def trace_decorator(trace_args):
  def decorator(func):
    def wrapper(*args, **kwargs):
      current_span = trace.get_current_span()
      trace_attributes = { 
        key: kwargs.get(key) for key in trace_args
        if key in kwargs
      }
      print(f"Kwargs: {kwargs} Trace attributes: {trace_attributes}")
      current_span.add_event(
        name=f"Started {func.__name__}",
        attributes=trace_attributes,
      )
      return_value = func(*args, **kwargs)
      current_span.add_event(f"Completed {func.__name__}")
      return return_value
    return wrapper
  return decorator


@trace_decorator([])
def insert(**data):
    entity = datastore.Entity(key=ds_client.key(KEY_TYPE))
    entity.update(**data)
    ds_client.put(entity)


@trace_decorator(["sleep_seconds"])
def slow_function(*, sleep_seconds=0):
  time.sleep(sleep_seconds)


@app.route("/")
@trace_span
def hello_world():
  name = os.environ.get("NAME", "World")
  slow_function(sleep_seconds=1)
  insert(field="value")
  return "Hello {}!".format(name)


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
