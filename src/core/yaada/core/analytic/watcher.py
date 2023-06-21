# Copyright (c) 2023 Aptima, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


def print_header(stdscr, mode):
    height, width = stdscr.getmaxyx()
    stdscr.clear()
    stdscr.addstr(
        0, 0, f"{mode} <'q' to exit, 'l' to display logs, 's' to display stats>"
    )
    stdscr.addstr(1, 0, "-" * width)


def print_status(stdscr, mode, status, logs):
    print_header(stdscr, mode)
    height, width = stdscr.getmaxyx()
    # height,width = stdscr.getmaxyx()
    if status:
        if mode == "STATS":
            if status.get("finished", False):
                stdscr.addstr(2, 0, "FINISHED")
            elif status.get("error", False):
                stdscr.addstr(2, 0, "ERROR")
            elif status.get("started", False):
                stdscr.addstr(2, 0, "RUNNING")
            stdscr.addstr(
                3,
                0,
                f"analytic_name:{status.get('analytic_name','none available')}",
            )
            stdscr.addstr(
                4,
                0,
                f"analytic_session_id:{status.get('analytic_session_id','none available')}",
            )
            stdscr.addstr(
                5,
                0,
                f"analytic_start_time:{status.get('analytic_start_time','none available')}",
            )
            stdscr.addstr(
                6,
                0,
                f"analytic_finish_time:{status.get('analytic_finish_time','none available')}",
            )
            stdscr.addstr(
                7,
                0,
                f"analytic_compute_duration_seconds:{status.get('analytic_compute_duration_seconds','none available')}",
            )
            stdscr.addstr(8, 0, f"input_stats:{status.get('input_stats',{})}")
            stdscr.addstr(9, 0, f"output_stats:{status.get('output_stats',{})}")
            stdscr.addstr(10, 0, f"message:{status.get('message','none available')}")

        elif mode == "LOGS":
            out = "\n".join(logs[-(height - 2) :])
            # out = f"{len(logs)}"
            stdscr.addstr(2, 0, out)


def watch_analytic_output(context, analytic_name, analytic_session_id):
    import curses
    import sys

    if not sys.stdout.isatty():
        print("Not available outside tty console")
        return
    context.msg_service.subscribe_analytic_status(analytic_name, analytic_session_id)

    def c(stdscr):
        stdscr.nodelay(1)
        stdscr.clear()
        mode = "STATS"
        status = None
        logs = []

        while True:
            c = stdscr.getch()
            if c == ord("q"):
                context.msg_service.unsubscribe_analytic_status(
                    analytic_name, analytic_session_id
                )
                context.msg_service.fetch()
                print(logs)
                break  # Exit the while loop
            elif c == ord("l"):
                mode = "LOGS"
            elif c == ord("s"):
                mode = "STATS"
            else:
                r = context.msg_service.fetch()
                for doc in r:
                    if "message" in doc and doc["message"]:
                        msg = doc["message"]
                        if len(logs) == 0 or msg != logs[-1]:
                            logs.append(doc["message"])
                if len(r) > 0:
                    status = r[-1]
                try:
                    print_status(stdscr, mode, status, logs)
                except curses.error:
                    pass
                    # print_status()
                    # stdscr.clear()
                    # out = json.dumps(status,indent=2)
                    # try:
                    #   stdscr.addstr(1,0,out)
                    # except curses.error:
                    #   pass
                stdscr.refresh()

    curses.wrapper(c)
