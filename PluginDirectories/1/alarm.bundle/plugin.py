import datetime
import json
import os
import re
import string
import subprocess
import threading
import time

def block_for(seconds):
    """Wait at least seconds. This function should not be affected by the computer sleeping."""
    end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)

    while datetime.datetime.now() < end_time:
        time.sleep(1)

def seconds_to_text(seconds):
    """Return the user-friendly version of the time duration specified by seconds.

    Outputs should resemble:
        "3 hours and 30 minutes"
        "20 minutes"
        "1 minute and 30 seconds"
        "10 hours, 30 minutes and 10 seconds"
    """
    # Need the hours, minutes and seconds individually for putting into string
    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    seconds %= 60
    seconds = int(seconds)

    formatted_text = ""
    if hours > 0:
        formatted_text += str(hours) + " " + "hour" + ("s" if hours > 1 else "")
    if minutes > 0:
        if formatted_text.count(" ") > 0:
            formatted_text += (" and ", ", ")[seconds > 0]
        formatted_text += str(minutes) + " " + "minute" + ("s" if minutes > 1 else "")
    if seconds > 0:
        if formatted_text.count(" ") > 0:
            formatted_text += " and "
        formatted_text += str(seconds) + " " + "second" + ("s" if seconds > 1 else "")
    return formatted_text

def parse_time_span(time_string, time_span_pattern):
    """Convert an inputted string representing a timespan, like 3h30m15s, into a duration in seconds."""
    (hours, minutes, seconds) = re.match(time_span_pattern, time_string).groups()
    hours = 0 if hours is None else float(hours)
    minutes = 0 if minutes is None else float(minutes)
    seconds = 0 if seconds is None else float(seconds)
    total_seconds = datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds).total_seconds()
    return round(total_seconds)

def parse_absolute_time(time_string):
    """Convert an inputted string like '7:30PM' or '22:00' into the datetime object it represents.
    If the time is earlier in the day than the current time, take the same time tomorrow.
    """
    # As there are so many possible input formats, "19:30", "10", "6:00AM", etc. I thought a sensible
    # way to parse the inputs would be to use a dictionary which pairs patterns with parsing rules.
    time = None
    formats = {
        "^\d{1,2}$": "%H",
        "^\d{1,2}(AM|PM)$": "%I%p",
        "^\d{1,2}:\d{2}$": "%H:%M",
        "^\d{1,2}:\d{2}(AM|PM)$": "%I:%M%p"
        }
    for key, value in formats.items():
        if re.match(key, time_string, re.IGNORECASE):
            time = datetime.datetime.strptime(time_string, value).time()
    if time is None:
        # need to let the caller know that the time wasn't in a recognised format
        raise ValueError
    time = datetime.datetime.combine(datetime.datetime.today().date(), time)
    if datetime.datetime.now() > time:
        # it's likely the user wants to set an alarm for tomorrow
        time = time + datetime.timedelta(days = 1)
    return time

def seconds_until(time):
    """Return the number of seconds until a datetime."""
    total_seconds = (time - datetime.datetime.now()).total_seconds()
    return round(total_seconds)

def pretty_absolute_time(time_string):
    """Convert a string representing an absolute time, e.g. '1' or '3:30pm', into a human-readable format."""
    time = parse_absolute_time(time_string)
    formats = {
        "^\d{1,2}$": "%I o'clock",
        "^\d{1,2}(AM|PM)$": "%I o'clock",
        "^\d{1,2}:\d{2}$": "%H:%M",
        "^\d{1,2}:\d{2}(AM|PM)$": "%I:%M%p"
        }
    for key, value in formats.items():
        if re.match(key, time_string, re.IGNORECASE):
            return time.strftime(value).lstrip("0")

def show_alert(message):
    """Display a macOS dialog."""
    subprocess.call(["osascript", "dialog.scpt", str(message)])

def show_notification(message):
    """Display a macOS notification."""
    message = json.dumps(message)
    subprocess.call(["osascript", "-e", "display notification {}".format(message)])

class AlarmThread(threading.Thread):
    def __init__(self, file_name="beep.wav"):
        super(AlarmThread, self).__init__()
        self.file_name = file_name
        self.lock = threading.Lock()
        self.ongoing = False
        self.process = None

    def run(self):
        self.ongoing = True
        while True:
            with self.lock:
                if not self.ongoing:
                    break
                self.process = subprocess.Popen(["afplay", self.file_name])
            self.process.wait()

    def stop(self):
        with self.lock:
            if self.ongoing:
                self.ongoing = False
                if self.process:
                    self.process.kill()

def alert_after_timeout(timeout, message):
    """After timeout seconds, show an alert and play the alarm sound."""
    block_for(timeout)
    thread = AlarmThread()
    thread.start()

    show_alert(message)

    thread.stop()
    thread.join()

def results_dictionary(title, run_args, html):
    return {
        "title": title,
        "run_args": run_args,
        "html": html,
        "webview_transparent_background": True
        }

def erroneous_results():
    return {
        "title": "Don't understand.",
        "run_args": [],
        "html": "Make sure your input is formatted properly.",
        "webview_transparent_background": True
        }

def results(fields, original_query):
    arguments = fields["~arguments"].split(" ")
    time = arguments[0]
    message = " ".join(arguments[1:])
    if re.match("^AM|PM", message, re.IGNORECASE):
        time += message.split(" ", 1)[0]
        message = message.split(" ", 1)[1:]
    # which input format is the user trying to use?
    time_span_pattern = r"^(?:(?P<hours>[0-9]+(?:[,.][0-9]+)?)h)?(?:(?P<minutes>[0-9]+(?:[,.][0-9]+)?)m)?(?:(?P<seconds>[0-9]+(?:[,.][0-9]+)?)s)?$"
    if re.match(time_span_pattern, time):
        try:
            seconds = parse_time_span(time, time_span_pattern)
            html_results = None
            with open("relative_results.html") as html:
                html_results = string.Template(html.read()).substitute(
                    time_span = seconds,
                    message = message,
                    text_time_span = seconds_to_text(seconds))
            return results_dictionary("{} in {}".format(message or "Alarm", seconds_to_text(seconds)), [time, message or "{} alarm".format(seconds_to_text(seconds)), time_span_pattern], html_results)
        except AttributeError:
            return erroneous_results()
    else:
        try:
            html_results = None
            with open("absolute_results.html") as html:
                html_results = string.Template(html.read()).substitute(
                    absolute_time_stamp = int(parse_absolute_time(time).strftime("%s")) * 1000,
                    message = message)
            message = message or "{} alarm".format(pretty_absolute_time(time))
            return results_dictionary("Set an alarm for {}".format(pretty_absolute_time(time)), [time, message, time_span_pattern], html_results)
        except ValueError:
            return erroneous_results()

def run(time, message, time_span_pattern):
    seconds = None
    try:
        if re.match(time_span_pattern, time):
            seconds = parse_time_span(time, time_span_pattern)
            show_notification("An alarm for {} was successfully set.".format(seconds_to_text(seconds)))
        else:
            seconds = seconds_until(parse_absolute_time(time))
            show_notification("An alarm for {} was successfully set.".format(pretty_absolute_time(time)))
    except:
        show_notification("The alarm could not be set.")
        return
    # needs to fork itself into a child process so that the alarm can finish running. Flashlight would otherwise kill
    # the script after 30 seconds, cutting the alarm short or preventing it from ever running
    newpid = os.fork()
    if newpid == 0:
        alert_after_timeout(seconds, message)
        exit()

