import contextvars

# A context variable holds a value "for the current request", even across threads and awaits.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
