
status_2XX = lambda status : 200 <= status < 300
status_3XX = lambda status : 300 <= status < 400
status_4XX = lambda status : 400 <= status < 500
status_5XX = lambda status : 500 <= status < 600

status_success = status_2XX
status_error = lambda status: status_4XX(status) or status_5XX(status)
status_non_error = lambda status : not status_error(status)

