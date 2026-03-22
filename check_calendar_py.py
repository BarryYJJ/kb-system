#!/usr/bin/env python3
from Foundation import NSDate, NSPredicate, EKEventStore, EKEvent
import sys

# Create an event store
event_store = EKEventStore.alloc().init()

# Request access
try:
    accessGranted = event_store.requestAccessToEntityType_completion_(EKEvent.eventType(), None)
    if accessGranted[0]:
        print("Access granted")
    else:
        print("Access denied")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

# Get today's date
today = NSDate.date()
startOfDay = NSCalendar.currentCalendar().startOfDayForDate_(today)
endOfDay = NSCalendar.currentCalendar().dateByAddingUnit_toDate_options_(NSCalendar.Day, 1, startOfDay, 0)

# Create predicate
predicate = event_store.predicateForEventsWithStartDate_endDate_calendars_(startOfDay, endOfDay, None)

# Fetch events
events = event_store.eventsMatchingPredicate_(predicate)

if not events:
    print("今天没有日程")
else:
    for event in events:
        start = event.startDate()
        end = event.endDate()
        title = event.title()
        
        # Format time
        from Foundation import NSDateFormatter
        formatter = NSDateFormatter.alloc().init()
        formatter.setDateFormat_("HH:mm")
        
        startTime = formatter.stringFromDate_(start)
        endTime = formatter.stringFromDate_(end)
        
        print(f"{title} | {startTime} - {endTime}")
