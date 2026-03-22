#!/usr/bin/env python3
import subprocess
from datetime import datetime

today = datetime.now()
start = today.replace(hour=0, minute=0, second=0)
end = today.replace(hour=23, minute=59, second=59)

script = f'''
tell application "Calendar"
    tell calendar "即时提醒"
        set eventList to events where start date >= date "{start.strftime('%Y-%m-%d %H:%M:%S')}" and start date <= date "{end.strftime('%Y-%m-%d %H:%M:%S')}"
        if (count of eventList) is 0 then
            return "今天没有日程"
        else
            set output to ""
            repeat with evt in eventList
                set evtSummary to summary of evt
                set evtStart to start date of evt
                set evtEnd to end date of evt
                set output to output & evtSummary & " | " & (time string of evtStart) & " - " & (time string of evtEnd) & "
"
            end repeat
            return output
        end if
    end tell
end tell
'''

result = subprocess.run(['/usr/bin/osascript', '-e', script], capture_output=True, text=True, timeout=15)
print(result.stdout.strip())
if result.stderr:
    print("Error:", result.stderr.strip())
